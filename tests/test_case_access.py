import hashlib
import pytest
from fastapi.testclient import TestClient
from tools.auth_store import AuthStore
from tools.job_store import JobStore
from web import api, auth

ORIGIN = "https://pilot.example.test"
PASSWORD = "synthetic password 19"

@pytest.fixture
def access(monkeypatch, tmp_path):
    monkeypatch.setattr(AuthStore, "_hash", staticmethod(lambda password, salt: hashlib.sha256(password + salt).digest()))
    identities = AuthStore(tmp_path / "auth.sqlite3")
    users = {name: identities.create_user(name, PASSWORD, org, role) for name, org, role in [("alice", "org-a", "claimant"), ("bob", "org-a", "claimant"), ("reviewer", "org-a", "reviewer"), ("outsider", "org-b", "admin")]}
    store = JobStore(tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(auth, "get_store", lambda: identities)
    monkeypatch.setattr(api, "_start_worker", lambda: None)
    monkeypatch.setenv("INSURECLEAR_AUTH_MODE", "accounts")
    monkeypatch.setenv("INSURECLEAR_CORS_ORIGINS", ORIGIN)
    clients = {}
    for name in users:
        client = TestClient(api.app, base_url=ORIGIN)
        response = client.post("/api/auth/login", headers={"Origin": ORIGIN}, json={"username": name, "password": PASSWORD})
        assert response.status_code == 200
        client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]})
        clients[name] = client
    return store, clients, users


def submit(client):
    return client.post("/api/analyze", data={"mode": "text", "case_id": "same_label", "denial_text": "The insurer denied this claim because it says the treatment was excluded.", "policy_text": "This policy covers eligible inpatient treatment subject to listed exclusions and limits."})


def test_accounts_ignore_shared_key_and_require_cookie(access):
    _, clients, _ = access
    unauth = TestClient(api.app, base_url=ORIGIN)
    assert unauth.post("/api/analyze", headers={"X-API-Key": "shared"}, data={"mode": "demo"}).status_code == 401
    assert clients["alice"].get("/api/jobs").status_code == 200


def test_all_job_reads_and_downloads_enforce_owner_and_org(access):
    store, clients, users = access
    response = submit(clients["alice"])
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    for suffix in ["", "/report", "/letter", "/download/report", "/download/letter"]:
        assert clients["bob"].get(f"/api/jobs/{job_id}{suffix}").status_code == 404
        assert clients["outsider"].get(f"/api/jobs/{job_id}{suffix}").status_code == 404
    assert clients["reviewer"].get(f"/api/jobs/{job_id}").status_code == 200
    assert store.get(job_id)["owner_id"] == users["alice"]["user_id"]
    assert clients["bob"].get("/api/jobs").json()["jobs"] == []


def test_display_labels_do_not_share_checkpoints_or_legacy_rows(access):
    store, clients, _ = access
    first = submit(clients["alice"]).json(); second = submit(clients["bob"]).json()
    assert store.get(first["job_id"])["case_id"] != store.get(second["job_id"])["case_id"]
    store.create("legacy", {"case_id": "old"}, "text", "old", False)
    assert clients["reviewer"].get("/api/jobs/legacy").status_code == 404
    store.update(first["job_id"], error="private sensitive error", traceback="secret source text")
    snapshot = clients["alice"].get(f"/api/jobs/{first['job_id']}").json()
    assert "traceback" not in snapshot and "private sensitive error" not in str(snapshot)


def test_case_creation_requires_session_csrf(access):
    _, clients, _ = access
    clients["alice"].headers.pop("X-CSRF-Token")
    assert submit(clients["alice"]).status_code == 403


def test_credentialed_cors_rejects_wildcard_configuration(monkeypatch):
    monkeypatch.setenv("INSURECLEAR_CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="explicit"):
        api.validated_origins()


def test_completed_private_reads_and_downloads_are_not_cacheable(access, tmp_path):
    store, clients, _ = access
    job_id = submit(clients["alice"]).json()["job_id"]
    letter = tmp_path / "appeal_letter.txt"; letter.write_text("Private draft", encoding="utf-8")
    report = tmp_path / "full_report.json"; report.write_text("{}", encoding="utf-8")
    store.update(job_id, status="completed", result={"appeal_letter": "Private draft", "artifacts": {"appeal_letter_path": str(letter), "full_report_path": str(report)}})
    for suffix in ["", "/report", "/letter", "/download/report", "/download/letter"]:
        response = clients["alice"].get(f"/api/jobs/{job_id}{suffix}")
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "no-store"
        assert "Cookie" in response.headers.get("vary", "")
        assert clients["bob"].get(f"/api/jobs/{job_id}{suffix}").status_code == 404
