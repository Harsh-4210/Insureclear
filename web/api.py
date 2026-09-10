"""
InsureClear API
FastAPI wrapper around the existing pipeline so a React UI can submit jobs,
track progress, and download outputs without depending on Streamlit.
"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"

import sys

sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.main import run_pipeline  # noqa: E402
from tools.io_utils import clear_session  # noqa: E402

app = FastAPI(title="InsureClear API", version="1.0.0")

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_jobs: dict[str, dict[str, Any]] = {}
_job_lock = threading.Lock()


def _job_snapshot(job_id: str) -> dict[str, Any] | None:
    with _job_lock:
        job = _jobs.get(job_id)
        return copy.deepcopy(job) if job else None


def _update_job(job_id: str, **fields: Any) -> None:
    with _job_lock:
        job = _jobs.setdefault(job_id, {"id": job_id})
        job.update(fields)


def _load_sample_text(filename: str) -> str:
    path = SAMPLES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing sample file: {filename}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Sample file is empty: {filename}")
    return content


def _progress_callback(job_id: str):
    def emit(update: dict[str, Any]) -> None:
        payload = {
            "stage": update.get("stage"),
            "message": update.get("message"),
            "progress": update.get("percent"),
            "state": update.get("state"),
        }
        _update_job(job_id, **payload)

    return emit


def _run_job(job_id: str, payload: dict[str, Any]) -> None:
    temp_dir = payload.get("temp_dir")
    case_id = payload["case_id"]

    try:
        if payload.get("fresh_run"):
            clear_session(case_id)

        _update_job(
            job_id,
            status="running",
            progress=0,
            stage="starting",
            message="Preparing pipeline",
            result=None,
            error=None,
        )

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
            output_dir=run_result.get("artifacts", {}).get("output_dir"),
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            progress=_job_snapshot(job_id).get("progress", 0) if _job_snapshot(job_id) else 0,
            stage="failed",
            message="Pipeline failed",
            error=str(exc),
            traceback=traceback.format_exc(),
        )
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


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
) -> dict[str, Any]:
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"demo", "text", "pdf"}:
        raise HTTPException(status_code=400, detail="mode must be one of: demo, text, pdf")

    resolved_case_id = case_id.strip() or f"case_{uuid.uuid4().hex[:8]}"
    job_id = uuid.uuid4().hex

    payload: dict[str, Any] = {
        "case_id": resolved_case_id,
        "fresh_run": fresh_run,
    }

    temp_dir: str | None = None

    if normalized_mode == "demo":
        try:
            payload["denial_text"] = _load_sample_text("sample_denial.txt")
            payload["policy_text"] = _load_sample_text("sample_policy.txt")
            payload["denial_pdf"] = str(SAMPLES_DIR / "sample_denial.txt")
            payload["policy_pdf"] = str(SAMPLES_DIR / "sample_policy.txt")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Demo mode is unavailable: {exc}") from exc
    elif normalized_mode == "text":
        cleaned_denial = (denial_text or "").strip()
        cleaned_policy = (policy_text or "").strip()
        if not cleaned_denial or not cleaned_policy:
            raise HTTPException(status_code=400, detail="Text mode requires both denial_text and policy_text")
        payload["denial_text"] = cleaned_denial
        payload["policy_text"] = cleaned_policy
        payload["denial_pdf"] = "text_input"
        payload["policy_pdf"] = "text_input"
    else:
        if denial_pdf is None or policy_pdf is None:
            raise HTTPException(status_code=400, detail="PDF mode requires both denial_pdf and policy_pdf files")

        temp_dir = tempfile.mkdtemp(prefix=f"insureclear_{job_id}_")
        temp_path = Path(temp_dir)
        denial_path = temp_path / "denial.pdf"
        policy_path = temp_path / "policy.pdf"

        try:
            denial_path.write_bytes(await denial_pdf.read())
            policy_path.write_bytes(await policy_pdf.read())
        except Exception as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"Failed to store uploaded PDF files: {exc}") from exc

        payload["denial_pdf"] = str(denial_path)
        payload["policy_pdf"] = str(policy_path)
        payload["temp_dir"] = temp_dir

    _update_job(
        job_id,
        id=job_id,
        status="queued",
        progress=0,
        stage="queued",
        message="Job queued",
        case_id=resolved_case_id,
        mode=normalized_mode,
        fresh_run=fresh_run,
        result=None,
        error=None,
        traceback=None,
    )

    thread = threading.Thread(target=_run_job, args=(job_id, payload), daemon=True)
    thread.start()

    return {
        "job_id": job_id,
        "case_id": resolved_case_id,
        "status": "queued",
        "mode": normalized_mode,
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs/{job_id}/report")
def get_job_report(job_id: str) -> dict[str, Any]:
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.get("result")
    if not result:
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    return result


@app.get("/api/jobs/{job_id}/letter")
def get_job_letter(job_id: str) -> PlainTextResponse:
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.get("result")
    if not result:
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    letter = result.get("appeal_letter", "")
    return PlainTextResponse(letter)


@app.get("/api/jobs/{job_id}/download/report")
def download_report(job_id: str) -> FileResponse:
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.get("result")
    if not result:
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    output_dir = Path(result.get("artifacts", {}).get("output_dir", ""))
    report_path = output_dir / "full_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(report_path, media_type="application/json", filename=report_path.name)


@app.get("/api/jobs/{job_id}/download/letter")
def download_letter(job_id: str) -> FileResponse:
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.get("result")
    if not result:
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    output_dir = Path(result.get("artifacts", {}).get("output_dir", ""))
    letter_path = output_dir / "appeal_letter.txt"
    if not letter_path.exists():
        raise HTTPException(status_code=404, detail="Appeal letter file not found")
    return FileResponse(letter_path, media_type="text/plain", filename=letter_path.name)
