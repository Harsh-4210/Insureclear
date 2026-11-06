from test_case_access import access, submit
from web import api


def test_lifecycle_routes_enforce_owner_and_preserve_running_cases(access, monkeypatch, tmp_path):
    from tools import io_utils
    store, clients, _ = access
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(api, "JOB_INPUTS_DIR", tmp_path / "inputs")
    job_id = submit(clients["alice"]).json()["job_id"]
    assert clients["bob"].post(f"/api/jobs/{job_id}/cancel").status_code == 404
    assert clients["bob"].delete(f"/api/jobs/{job_id}").status_code == 404
    store.update(job_id, status="running")
    assert clients["alice"].delete(f"/api/jobs/{job_id}").status_code == 409
    assert clients["alice"].post(f"/api/jobs/{job_id}/cancel").json()["status"] == "cancellation_requested"
    store.recover_running()
    assert clients["alice"].delete(f"/api/jobs/{job_id}").status_code == 200
    assert store.get(job_id) is None


def test_request_ids_readiness_and_exception_privacy(access, monkeypatch):
    _, clients, _ = access
    client = clients["alice"]
    first = client.get("/health"); second = client.get("/health")
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    monkeypatch.setattr(api, "_provider_configured", lambda: False)
    readiness = client.get("/ready")
    assert readiness.status_code == 503 and readiness.json()["checks"]["provider_configured"] is False
    def fail(*args): raise RuntimeError("SECRET-PRIVATE-DOCUMENT")
    monkeypatch.setattr(api.job_store, "list_for", fail)
    response = client.get("/api/jobs")
    assert response.status_code == 500
    assert "SECRET-PRIVATE" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_queue_admission_is_bounded(access, monkeypatch):
    _, clients, _ = access
    monkeypatch.setenv("INSURECLEAR_MAX_PENDING_JOBS", "1")
    assert submit(clients["alice"]).status_code == 200
    response = submit(clients["bob"])
    assert response.status_code == 429 and "Retry-After" in response.headers
