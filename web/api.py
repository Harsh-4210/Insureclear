"""InsureClear FastAPI service with a durable SQLite-backed job queue."""

from __future__ import annotations

import copy
import hmac
import os
import re
import shutil
import threading
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

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
from tools.job_store import JobStore  # noqa: E402



@asynccontextmanager
async def lifespan(_app: FastAPI):
    _start_worker()
    yield
    _worker_stop.set()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=2)


app = FastAPI(title="InsureClear API", version="1.1.0", lifespan=lifespan)
job_store = JobStore(os.getenv("INSURECLEAR_JOB_DB", str(PROJECT_ROOT / "data" / "jobs.sqlite3")))

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "INSURECLEAR_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

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


def _authenticate(x_api_key: str | None = Header(default=None)) -> None:
    configured_key = os.getenv("INSURECLEAR_API_KEY")
    auth_required = os.getenv("INSURECLEAR_REQUIRE_AUTH", "false").lower() == "true"
    if auth_required and not configured_key:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    if configured_key and not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header is required")
    if configured_key and not hmac.compare_digest(x_api_key or "", configured_key):
        raise HTTPException(status_code=403, detail="Invalid API key")


def _guard(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    _authenticate(x_api_key)

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _rate_lock:
        recent = [timestamp for timestamp in _rate_windows.get(client_ip, []) if now - timestamp < RATE_LIMIT_WINDOW_SECONDS]
        if len(recent) >= RATE_LIMIT_REQUESTS:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        recent.append(now)
        _rate_windows[client_ip] = recent


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
        if payload.get("fresh_run"):
            clear_session(case_id)
        run_result = run_pipeline(
            denial_pdf=payload["denial_pdf"],
            policy_pdf=payload["policy_pdf"],
            case_id=case_id,
            denial_text=payload.get("denial_text"),
            policy_text=payload.get("policy_text"),
            progress_callback=_progress_callback(job_id),
        )
        _update_job(
            job_id,
            status="completed",
            progress=100,
            stage="complete",
            message="Pipeline complete",
            result=run_result,
            error=None,
            traceback=None,
        )
    except Exception as exc:
        snapshot = _job_snapshot(job_id) or {}
        _update_job(
            job_id,
            status="failed",
            progress=snapshot.get("progress", 0),
            stage="failed",
            message="Pipeline failed",
            error=str(exc),
            traceback=traceback.format_exc(),
        )
    finally:
        if input_dir:
            shutil.rmtree(input_dir, ignore_errors=True)


def _worker_loop() -> None:
    while not _worker_stop.is_set():
        claimed = job_store.claim_next()
        if claimed:
            job_id, payload = claimed
            _run_job(job_id, payload)
        else:
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


@app.post("/api/analyze", dependencies=[Depends(_guard)])
async def analyze(
    mode: str = Form(...),
    case_id: str = Form(""),
    fresh_run: bool = Form(False),
    denial_text: str | None = Form(None),
    policy_text: str | None = Form(None),
    denial_pdf: UploadFile | None = File(None),
    policy_pdf: UploadFile | None = File(None),
) -> dict[str, Any]:
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"demo", "text", "pdf"}:
        raise HTTPException(status_code=400, detail="mode must be one of: demo, text, pdf")

    resolved_case_id = case_id.strip() or f"case_{uuid.uuid4().hex[:8]}"
    if not CASE_ID_PATTERN.fullmatch(resolved_case_id):
        raise HTTPException(status_code=400, detail="case_id contains unsupported characters")

    job_id = uuid.uuid4().hex
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

    job_store.create(job_id, payload, normalized_mode, resolved_case_id, fresh_run)
    _start_worker()
    return {
        "job_id": job_id,
        "case_id": resolved_case_id,
        "status": "queued",
        "mode": normalized_mode,
    }


@app.get("/api/jobs/{job_id}", dependencies=[Depends(_authenticate)])
def get_job(job_id: str) -> dict[str, Any]:
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs/{job_id}/report", dependencies=[Depends(_authenticate)])
def get_job_report(job_id: str) -> dict[str, Any]:
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.get("result"):
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    return job["result"]


@app.get("/api/jobs/{job_id}/letter", dependencies=[Depends(_authenticate)])
def get_job_letter(job_id: str) -> PlainTextResponse:
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.get("result"):
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    return PlainTextResponse(job["result"].get("appeal_letter", ""))


@app.get("/api/jobs/{job_id}/download/report", dependencies=[Depends(_authenticate)])
def download_report(job_id: str) -> FileResponse:
    job = _job_snapshot(job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Completed job not found")
    report_path = Path(job["result"].get("artifacts", {}).get("full_report_path", ""))
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(report_path, media_type="application/json", filename=report_path.name)


@app.get("/api/jobs/{job_id}/download/letter", dependencies=[Depends(_authenticate)])
def download_letter(job_id: str) -> FileResponse:
    job = _job_snapshot(job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Completed job not found")
    letter_path = Path(job["result"].get("artifacts", {}).get("appeal_letter_path", ""))
    if not letter_path.is_file():
        raise HTTPException(status_code=404, detail="Appeal letter file not found")
    return FileResponse(letter_path, media_type="text/plain", filename=letter_path.name)
