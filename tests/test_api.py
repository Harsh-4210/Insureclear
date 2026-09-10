from pathlib import Path

from fastapi.testclient import TestClient

from tools.job_store import JobStore
from web import api


DENIAL_TEXT = "The insurer rejected the hospitalisation claim because the procedure was considered excluded."
POLICY_TEXT = "The policy covers eligible hospitalisation subject to documented exclusions and limits."


def test_api_job_lifecycle(monkeypatch, tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_start_worker", lambda: None)
    monkeypatch.delenv("INSURECLEAR_API_KEY", raising=False)
    monkeypatch.setattr(
        api,
        "run_pipeline",
        lambda **kwargs: {
            "appeal_letter": "Generated letter",
            "artifacts": {
                "output_dir": str(tmp_path),
                "appeal_letter_path": str(tmp_path / "appeal_letter.txt"),
                "full_report_path": str(tmp_path / "full_report.json"),
            },
            "pipeline_stats": {"final_score": 0.9},
        },
    )

    with TestClient(api.app) as client:
        response = client.post(
            "/api/analyze",
            data={"mode": "text", "case_id": "api_test"},
            files={
                "denial_text": (None, DENIAL_TEXT),
                "policy_text": (None, POLICY_TEXT),
            },
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "queued"

        claimed = store.claim_next()
        assert claimed is not None
        api._run_job(*claimed)

        completed = client.get(f"/api/jobs/{job_id}")
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert client.get(f"/api/jobs/{job_id}/report").json()["pipeline_stats"]["final_score"] == 0.9


def test_api_rejects_unsafe_pdf_upload(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "job_store", JobStore(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(api, "_start_worker", lambda: None)
    monkeypatch.delenv("INSURECLEAR_API_KEY", raising=False)

    with TestClient(api.app) as client:
        response = client.post(
            "/api/analyze",
            data={"mode": "pdf"},
            files={
                "denial_pdf": ("denial.pdf", b"not a pdf", "application/pdf"),
                "policy_pdf": ("policy.pdf", b"%PDF-valid", "application/pdf"),
            },
        )

    assert response.status_code == 415
