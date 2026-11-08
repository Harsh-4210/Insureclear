import threading
from contextlib import contextmanager

from pathlib import Path

from fastapi.testclient import TestClient

from tools.job_store import JobStore
from web import api


DENIAL_TEXT = "The insurer rejected the hospitalisation claim because the procedure was considered excluded."
LEGACY_KEY = 'synthetic-operator-key'
POLICY_TEXT = "The policy covers eligible hospitalisation subject to documented exclusions and limits."


def test_api_job_lifecycle(monkeypatch, tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_start_worker", lambda: None)
    monkeypatch.setenv("INSURECLEAR_AUTH_MODE", "legacy")
    monkeypatch.setenv("INSURECLEAR_API_KEY", LEGACY_KEY)
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

    with TestClient(api.app, headers={"X-API-Key": LEGACY_KEY}) as client:
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
    monkeypatch.setenv("INSURECLEAR_AUTH_MODE", "legacy")
    monkeypatch.setenv("INSURECLEAR_API_KEY", LEGACY_KEY)

    with TestClient(api.app, headers={"X-API-Key": LEGACY_KEY}) as client:
        response = client.post(
            "/api/analyze",
            data={"mode": "pdf"},
            files={
                "denial_pdf": ("denial.pdf", b"not a pdf", "application/pdf"),
                "policy_pdf": ("policy.pdf", b"%PDF-valid", "application/pdf"),
            },
        )

    assert response.status_code == 415


def test_waiting_worker_takes_over_existing_job_when_owner_exits(monkeypatch, tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create("handover_job", {"case_id": "handover_case"}, "text", "handover_case", False)
    assert store.claim_next()[0] == "handover_job"
    stop = threading.Event()
    blocked = threading.Event()
    completed = threading.Event()
    real_lock = store.worker_lock

    @contextmanager
    def observed_lock():
        with real_lock() as acquired:
            if not acquired:
                blocked.set()
            yield acquired

    def process(job_id, payload):
        store.update(job_id, status="completed")
        completed.set()
        stop.set()

    monkeypatch.setattr(store, "worker_lock", observed_lock)
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_worker_stop", stop)
    monkeypatch.setattr(api, "_run_job", process)
    worker = threading.Thread(target=api._worker_loop, daemon=True)
    try:
        with real_lock() as acquired:
            assert acquired
            worker.start()
            assert blocked.wait(5), "Standby worker must attempt ownership"
            assert not completed.is_set()
            assert store.get("handover_job")["status"] == "running"
        assert completed.wait(5), "Standby must recover work without a new submission"
        assert store.get("handover_job")["status"] == "completed"
    finally:
        stop.set()
        worker.join(timeout=5)


def test_worker_tolerates_input_already_removed_by_concurrent_cleanup(monkeypatch, tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    root = tmp_path / "inputs"; folder = root / "cleanup_job"; folder.mkdir(parents=True)
    payload = {"case_id": "cleanup_case", "denial_pdf": "unused", "policy_pdf": "unused", "input_dir": str(folder)}
    store.create("cleanup_job", payload, "pdf", "cleanup_case", False)
    assert store.claim_next()[0] == "cleanup_job"
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "JOB_INPUTS_DIR", root)
    monkeypatch.setattr(api, "run_pipeline", lambda **kwargs: {"appeal_letter": "Synthetic draft"})
    def already_removed(path): raise FileNotFoundError("Concurrent case cleanup already removed the directory")
    monkeypatch.setattr(api.shutil, "rmtree", already_removed)
    api._run_job("cleanup_job", payload)
    assert store.get("cleanup_job")["status"] == "completed"

def test_private_api_defaults_to_accounts_without_auth_configuration(monkeypatch):
    monkeypatch.delenv("INSURECLEAR_AUTH_MODE", raising=False)
    monkeypatch.delenv("INSURECLEAR_AUTH_DB", raising=False)
    monkeypatch.delenv("INSURECLEAR_API_KEY", raising=False)
    monkeypatch.delenv("INSURECLEAR_REQUIRE_AUTH", raising=False)
    client = TestClient(api.app)
    assert client.get("/api/jobs").status_code == 503
    assert client.get("/api/auth/session").status_code == 503


def test_legacy_requires_a_key_even_with_an_old_optional_auth_setting(monkeypatch):
    monkeypatch.setenv("INSURECLEAR_AUTH_MODE", "legacy")
    monkeypatch.setenv("INSURECLEAR_REQUIRE_AUTH", "false")
    monkeypatch.delenv("INSURECLEAR_API_KEY", raising=False)
    assert TestClient(api.app).get("/api/jobs").status_code == 503

def test_legacy_operator_cannot_read_account_owned_cases(monkeypatch, tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create("account-case", {}, "text", "case", False, owner_id="alice", org_id="org-a")
    store.create("legacy-case", {}, "text", "old", False)
    store.create("old-overlap", {}, "text", "JoB_account-case", False)
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setenv("INSURECLEAR_AUTH_MODE", "legacy")
    monkeypatch.setenv("INSURECLEAR_API_KEY", LEGACY_KEY)
    client = TestClient(api.app, headers={"X-API-Key": LEGACY_KEY})
    assert client.get("/api/jobs/account-case").status_code == 404
    assert client.get("/api/jobs/old-overlap").status_code == 404
    assert [job["job_id"] for job in client.get("/api/jobs").json()["jobs"]] == ["legacy-case"]
    assert client.get("/api/jobs/legacy-case").status_code == 200

def test_legacy_cannot_submit_with_a_reserved_account_checkpoint_name(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "job_store", JobStore(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(api, "_start_worker", lambda: None)
    monkeypatch.setenv("INSURECLEAR_AUTH_MODE", "legacy")
    monkeypatch.setenv("INSURECLEAR_API_KEY", LEGACY_KEY)
    client = TestClient(api.app, headers={"X-API-Key": LEGACY_KEY})
    result = client.post("/api/analyze", data={"mode": "demo", "case_id": "JoB_private", "fresh_run": "true"})
    assert result.status_code == 400


def test_worker_rejects_already_queued_legacy_checkpoint_collision(monkeypatch, tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    payload = {"case_id": "job_owned", "fresh_run": True, "denial_pdf": "demo", "policy_pdf": "demo"}
    store.create("old-legacy", payload, "demo", payload["case_id"], True)
    monkeypatch.setattr(api, "job_store", store)
    touched = []
    monkeypatch.setattr(api, "clear_session", touched.append)
    monkeypatch.setattr(api, "run_pipeline", lambda **kwargs: {"appeal_letter": "Synthetic"})
    api._run_job(*store.claim_next())
    assert store.get("old-legacy")["status"] == "failed"
    assert touched == []
