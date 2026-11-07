"""InsureClear FastAPI service with a durable SQLite-backed job queue."""

from __future__ import annotations

import copy
import hmac
import os
import re
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"
JOB_INPUTS_DIR = PROJECT_ROOT / "data" / "job_inputs"
MAX_UPLOAD_BYTES = int(os.getenv("INSURECLEAR_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
MAX_TEXT_CHARS = int(os.getenv("INSURECLEAR_MAX_TEXT_CHARS", "500000"))
RATE_LIMIT_REQUESTS = int(os.getenv("INSURECLEAR_RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("INSURECLEAR_RATE_LIMIT_WINDOW_SECONDS", "60"))

import sys

sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.main import run_pipeline  # noqa: E402
from tools.io_utils import clear_session  # noqa: E402
from tools.job_store import ACCOUNT_CASE_PREFIX, JobStore, QueueFull  # noqa: E402
from web import auth  # noqa: E402
from tools import io_utils, llm_client
from tools.regulatory_registry import load_registry
from tools.review_store import ReviewStore
from tools.case_lifecycle import delete_case, confined_path
from tools.runtime_control import RuntimeControl, PipelineCancelled, PipelineTimedOut



@asynccontextmanager
async def lifespan(_app: FastAPI):
    _start_worker()
    yield
    _worker_stop.set()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=2)


app = FastAPI(title="InsureClear API", version="1.1.0", lifespan=lifespan)
app.include_router(auth.router)
job_store = JobStore(os.getenv("INSURECLEAR_JOB_DB", str(PROJECT_ROOT / "data" / "jobs.sqlite3")))

def validated_origins() -> list[str]:
    from urllib.parse import urlsplit
    origins = auth.browser_origins()
    for origin in origins:
        parsed = urlsplit(origin)
        if "*" in origin or parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("CORS requires explicit HTTP(S) origins without paths or wildcards")
    if not origins:
        raise ValueError("CORS requires an explicit origin allowlist")
    return origins


allowed_origins = validated_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "X-CSRF-Token"],
)

@app.middleware("http")
async def private_response_headers(request: Request, call_next):
    request_id = uuid.uuid4().hex
    try:
        response = await call_next(request)
    except Exception as error:
        print({"event": "request_failed", "request_id": request_id, "error_type": type(error).__name__})
        response = JSONResponse({"detail": "Request failed; contact the operator with the request ID", "request_id": request_id}, status_code=500)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        vary = {value.strip() for value in response.headers.get("Vary", "").split(",") if value.strip()}
        response.headers["Vary"] = ", ".join(sorted(vary | {"Cookie"}))
    return response


_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None
_rate_lock = threading.Lock()
_rate_windows: dict[str, list[float]] = {}
CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _job_snapshot(job_id: str) -> dict[str, Any] | None:
    job = job_store.get(job_id)
    return copy.deepcopy(job) if job else None


def _update_job(job_id: str, **fields: Any) -> None:
    job_store.update(job_id, **fields)


def _load_sample_text(filename: str) -> str:
    path = SAMPLES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing sample file: {filename}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Sample file is empty: {filename}")
    return content


def _authenticate(request: Request, x_api_key: str | None = Header(default=None)) -> dict:
    mode = auth.auth_mode()
    if mode == "accounts":
        return auth.current_principal(request)
    if mode != "legacy":
        raise HTTPException(503, "Authentication mode is not configured")
    configured_key = os.getenv("INSURECLEAR_API_KEY")
    if not configured_key or configured_key == "replace_me_with_a_long_random_value":
        raise HTTPException(503, "API authentication is not configured")
    if not x_api_key:
        raise HTTPException(401, "X-API-Key header is required")
    if not hmac.compare_digest(x_api_key.encode(), configured_key.encode()):
        raise HTTPException(403, "Invalid API key")
    return {"user_id": "legacy", "org_id": "legacy", "role": "admin", "legacy": True}


def _mutation(request: Request, principal: dict) -> None:
    if not principal.get("legacy"):
        auth.require_mutation(request, principal)


def _guard(request: Request, x_api_key: str | None = Header(default=None)) -> dict:
    principal = _authenticate(request, x_api_key)
    _mutation(request, principal)
    identity = principal["user_id"] if not principal.get("legacy") else (request.client.host if request.client else "unknown")
    now = time.monotonic()
    with _rate_lock:
        recent = [timestamp for timestamp in _rate_windows.get(identity, []) if now - timestamp < RATE_LIMIT_WINDOW_SECONDS]
        if len(recent) >= RATE_LIMIT_REQUESTS:
            raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)})
        _rate_windows[identity] = recent + [now]
    return principal


def get_authorized_job(job_id: str, principal: dict) -> dict:
    job = _job_snapshot(job_id)
    if not job or job.get("status") == "deleting":
        raise HTTPException(404, "Job not found")
    if principal.get("legacy"):
        if job.get("owner_id") is not None or job["case_id"].lower().startswith(ACCOUNT_CASE_PREFIX):
            raise HTTPException(404, "Job not found")
    else:
        same_org = job.get("org_id") == principal["org_id"] and job.get("owner_id") is not None
        allowed = same_org and (job.get("owner_id") == principal["user_id"] or principal["role"] in {"reviewer", "admin"})
        if not allowed:
            raise HTTPException(404, "Job not found")
    return job


def _public_report(report: dict) -> dict:
    report = copy.deepcopy(report)
    report.pop("artifacts", None)
    report.pop("inputs", None)
    return report


def _public_job(job: dict) -> dict:
    job = copy.deepcopy(job)
    job.pop("traceback", None)
    if job.get("error"):
        job["error"] = "Analysis failed. Contact the operator with the job ID."
    if job.get("result"):
        job["result"] = _public_report(job["result"])
    job["job_id"] = job["id"]
    return job


def _progress_callback(job_id: str):
    def emit(update: dict[str, Any]) -> None:
        _update_job(
            job_id,
            stage=update.get("stage", "running"),
            message=update.get("message", ""),
            progress=update.get("percent") or 0,
        )

    return emit


async def _read_pdf_upload(upload: UploadFile, destination: Path) -> None:
    if upload.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail=f"{upload.filename or 'Upload'} must be a PDF")
    total = 0
    first_chunk = b""
    with destination.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            if not first_chunk:
                first_chunk = chunk[:5]
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="PDF exceeds the configured upload limit")
            output.write(chunk)
    if first_chunk != b"%PDF-":
        raise HTTPException(status_code=415, detail=f"{upload.filename or 'Upload'} is not a valid PDF")


def _validate_text_input(value: str | None, name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"Text mode requires {name}")
    if len(cleaned) > MAX_TEXT_CHARS:
        raise HTTPException(status_code=413, detail=f"{name} exceeds the configured text limit")
    return cleaned


def _run_job(job_id: str, payload: dict[str, Any]) -> None:
    input_dir = payload.get("input_dir")
    case_id = payload["case_id"]
    try:
        if case_id.lower().startswith(ACCOUNT_CASE_PREFIX):
            job = job_store.get(job_id)
            if not job or job.get("owner_id") is None or case_id != ACCOUNT_CASE_PREFIX + job_id:
                raise ValueError("Invalid account checkpoint namespace")
        runtime = RuntimeControl(cancelled=lambda: (job_store.get(job_id) or {}).get("status") in {"cancelled", "cancellation_requested", "deleting"}, stats=llm_client.get_stats)
        runtime.check()
        if payload.get("fresh_run"):
            clear_session(case_id)
        run_result = run_pipeline(
            denial_pdf=payload["denial_pdf"],
            policy_pdf=payload["policy_pdf"],
            case_id=case_id,
            denial_text=payload.get("denial_text"),
            policy_text=payload.get("policy_text"),
            progress_callback=_progress_callback(job_id),
            control=runtime.check,
        )
        runtime.check()
        if not job_store.complete(job_id, run_result):
            raise PipelineCancelled("Completion was superseded by cancellation")
    except Exception as exc:
        job_store.stop(job_id, "cancelled" if isinstance(exc, PipelineCancelled) else "timed_out" if isinstance(exc, PipelineTimedOut) else "failed", "Pipeline stopped" if isinstance(exc, (PipelineCancelled, PipelineTimedOut)) else "Pipeline failed", type(exc).__name__)
    finally:
        if input_dir:
            safe_input = confined_path(JOB_INPUTS_DIR, input_dir)
            if safe_input.name != job_id:
                raise ValueError("Unsafe worker cleanup path")
            if safe_input.exists():
                try:
                    shutil.rmtree(safe_input)
                except FileNotFoundError:
                    pass  # A concurrent authorized cleanup already removed it.


def _worker_loop() -> None:
    # Only the lock owner may recover jobs or run the queue. Keep ownership
    # until the thread exits, even if API shutdown stops waiting after 2s.
    while not _worker_stop.is_set():
        with job_store.worker_lock() as acquired:
            if acquired:
                job_store.recover_running()
                while not _worker_stop.is_set():
                    claimed = job_store.claim_next()
                    if claimed:
                        job_id, payload = claimed
                        _run_job(job_id, payload)
                    else:
                        _worker_stop.wait(0.5)
        _worker_stop.wait(0.5)


def _start_worker() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_stop.clear()
    _worker_thread = threading.Thread(target=_worker_loop, name="insureclear-job-worker", daemon=True)
    _worker_thread.start()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(
    mode: str = Form(...),
    case_id: str = Form(""),
    fresh_run: bool = Form(False),
    denial_text: str | None = Form(None),
    policy_text: str | None = Form(None),
    denial_pdf: UploadFile | None = File(None),
    policy_pdf: UploadFile | None = File(None),
    principal: dict = Depends(_guard),
) -> dict[str, Any]:
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"demo", "text", "pdf"}:
        raise HTTPException(status_code=400, detail="mode must be one of: demo, text, pdf")

    resolved_case_id = case_id.strip() or f"case_{uuid.uuid4().hex[:8]}"
    if not CASE_ID_PATTERN.fullmatch(resolved_case_id):
        raise HTTPException(status_code=400, detail="case_id contains unsupported characters")

    job_id = uuid.uuid4().hex
    case_label = resolved_case_id
    if principal.get("legacy"):
        if resolved_case_id.lower().startswith(ACCOUNT_CASE_PREFIX):
            raise HTTPException(400, "case_id uses a reserved prefix")
    else:
        resolved_case_id = ACCOUNT_CASE_PREFIX + job_id
    payload: dict[str, Any] = {
        "case_id": resolved_case_id,
        "fresh_run": fresh_run,
    }
    input_dir: Path | None = None

    if normalized_mode == "demo":
        try:
            payload["denial_text"] = _load_sample_text("sample_denial.txt")
            payload["policy_text"] = _load_sample_text("sample_policy.txt")
            payload["denial_pdf"] = str(SAMPLES_DIR / "sample_denial.txt")
            payload["policy_pdf"] = str(SAMPLES_DIR / "sample_policy.txt")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Demo mode is unavailable: {exc}") from exc
    elif normalized_mode == "text":
        payload["denial_text"] = _validate_text_input(denial_text, "denial_text")
        payload["policy_text"] = _validate_text_input(policy_text, "policy_text")
        payload["denial_pdf"] = "text_input"
        payload["policy_pdf"] = "text_input"
    else:
        if denial_pdf is None or policy_pdf is None:
            raise HTTPException(status_code=400, detail="PDF mode requires both denial_pdf and policy_pdf files")
        input_dir = JOB_INPUTS_DIR / job_id
        input_dir.mkdir(parents=True, exist_ok=False)
        try:
            denial_path = input_dir / "denial.pdf"
            policy_path = input_dir / "policy.pdf"
            await _read_pdf_upload(denial_pdf, denial_path)
            await _read_pdf_upload(policy_pdf, policy_path)
            payload["denial_pdf"] = str(denial_path)
            payload["policy_pdf"] = str(policy_path)
            payload["input_dir"] = str(input_dir)
        except Exception:
            shutil.rmtree(input_dir, ignore_errors=True)
            raise

    try:
        job_store.create(job_id, payload, normalized_mode, resolved_case_id, fresh_run,
                         owner_id=None if principal.get("legacy") else principal["user_id"],
                         org_id=None if principal.get("legacy") else principal["org_id"], case_label=case_label)
    except QueueFull as error:
        if input_dir:
            shutil.rmtree(input_dir, ignore_errors=True)
        raise HTTPException(429, str(error), headers={"Retry-After": "30"}) from None
    _start_worker()
    return {
        "job_id": job_id,
        "case_id": resolved_case_id,
        "status": "queued",
        "mode": normalized_mode,
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, principal: dict = Depends(_authenticate)) -> dict[str, Any]:
    job = get_authorized_job(job_id, principal)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _public_job(job)


@app.get("/api/jobs/{job_id}/report")
def get_job_report(job_id: str, principal: dict = Depends(_authenticate)) -> dict[str, Any]:
    job = get_authorized_job(job_id, principal)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.get("result"):
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    return _public_report(job["result"])


@app.get("/api/jobs/{job_id}/letter")
def get_job_letter(job_id: str, principal: dict = Depends(_authenticate)) -> PlainTextResponse:
    job = get_authorized_job(job_id, principal)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.get("result"):
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    return PlainTextResponse(job["result"].get("appeal_letter", ""))


@app.get("/api/jobs/{job_id}/download/report")
def download_report(job_id: str, principal: dict = Depends(_authenticate)) -> FileResponse:
    job = get_authorized_job(job_id, principal)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Completed job not found")
    report_path = artifact_path(job, "full_report_path")
    return JSONResponse(_public_report(job["result"]), headers={"Content-Disposition": "attachment; filename=full_report.json"})


@app.get("/api/jobs/{job_id}/download/letter")
def download_letter(job_id: str, principal: dict = Depends(_authenticate)) -> FileResponse:
    job = get_authorized_job(job_id, principal)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Completed job not found")
    letter_path = artifact_path(job, "appeal_letter_path")
    return FileResponse(letter_path, media_type="text/plain", filename="draft-appeal-letter.txt")


@app.get("/api/jobs")
def list_jobs(principal: dict = Depends(_authenticate)) -> dict:
    return {"jobs": [{**job, "job_id": job["id"]} for job in job_store.list_for(principal)]}


from web.reviews import router as review_router
app.include_router(review_router)


def artifact_path(job, key):
    value = job["result"].get("artifacts", {}).get(key)
    if not value:
        raise HTTPException(404, "Artifact unavailable")
    try:
        path = confined_path(io_utils.OUTPUT_DIR, value)
    except ValueError:
        raise HTTPException(404, "Artifact unavailable") from None
    if not path.is_file():
        raise HTTPException(404, "Artifact unavailable")
    return path


def _provider_configured():
    if llm_client.PROVIDER == "groq":
        return llm_client.get_stats().get("groq_configured_key_count", 0) > 0
    return llm_client.PROVIDER == "gemini" and bool(os.getenv("GEMINI_API_KEY"))


@app.get("/ready")
def ready():
    checks = {}
    try:
        with job_store._connect() as db: db.execute("SELECT 1").fetchone()
        checks["database"] = True
    except Exception: checks["database"] = False
    try:
        load_registry(); checks["registry"] = True
    except Exception: checks["registry"] = False
    try:
        validated_origins()
        RuntimeControl()
        if min(int(os.getenv("INSURECLEAR_MAX_PENDING_JOBS", "100")), int(os.getenv("INSURECLEAR_MAX_PENDING_PER_USER", "3"))) < 1:
            raise ValueError("Queue configuration invalid")
        if auth.auth_mode() == "accounts":
            auth.secure_cookie()
            with auth.get_store()._connect() as db: db.execute("SELECT 1").fetchone()
        elif auth.auth_mode() != "legacy" or os.getenv("INSURECLEAR_API_KEY") in (None, "", "replace_me_with_a_long_random_value"):
            raise ValueError("Authentication configuration invalid")
        checks["auth_configuration"] = True
    except Exception: checks["auth_configuration"] = False
    checks["provider_configured"] = bool(_provider_configured())
    ok = all(checks.values())
    return JSONResponse({"status": "ready" if ok else "not_ready", "checks": checks, "provider_availability_tested": False}, status_code=200 if ok else 503)


def _owner_or_admin(job, principal):
    if principal.get("legacy") or (job.get("owner_id") != principal["user_id"] and principal["role"] != "admin"):
        raise HTTPException(403, "Case owner or organization admin required")


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, request: Request, principal: dict = Depends(_authenticate)):
    _mutation(request, principal)
    job = get_authorized_job(job_id, principal)
    _owner_or_admin(job, principal)
    return {"job_id": job_id, "status": job_store.cancel(job_id)}


@app.delete("/api/jobs/{job_id}")
def remove_job(job_id: str, request: Request, principal: dict = Depends(_authenticate)):
    _mutation(request, principal)
    job = get_authorized_job(job_id, principal)
    _owner_or_admin(job, principal)
    try:
        delete_case(job_store, ReviewStore(job_store.db_path), job_id, {"sessions": io_utils.SESSIONS_DIR, "outputs": io_utils.OUTPUT_DIR, "inputs": JOB_INPUTS_DIR})
    except ValueError as error:
        raise HTTPException(409, "Case cleanup refused; active work or unsafe artifact paths require operator attention") from None
    return {"deleted": True, "job_id": job_id}


@app.get("/api/operations")
def operations(principal: dict = Depends(_authenticate)):
    if principal.get("legacy") or principal["role"] != "admin":
        raise HTTPException(403, "Named organization admin required")
    with job_store._connect() as db:
        counts = {row[0]: row[1] for row in db.execute("SELECT status,COUNT(*) FROM jobs WHERE org_id=? GROUP BY status", (principal["org_id"],))}
    return {"status_counts": counts, "in_flight_cancellation": "cooperative_stage_boundaries"}
