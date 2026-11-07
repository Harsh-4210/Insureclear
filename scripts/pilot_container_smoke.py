"""Synthetic-only container/volume smoke test; never run against operator data.

Feed this script to a network-isolated candidate image on a newly created test
volume. It creates temporary fictional accounts and validates actual API/review
persistence. It never dispatches a provider call or accepts a real-data root.
"""
import json
import os
from pathlib import Path
import sqlite3
import sys


def main(mode):
    if not Path("/.dockerenv").is_file() or os.getenv("INSURECLEAR_SYNTHETIC_SMOKE") != "1":
        raise RuntimeError("Synthetic container-only smoke flag required")
    root = Path("/app/data")
    marker = root / ".insureclear-synthetic-smoke"
    if mode != "inspect":
        if list(root.iterdir()):
            raise RuntimeError("Refusing a populated volume; use a fresh named test volume with volume-nocopy")
        marker.write_text("Synthetic smoke fixtures only", encoding="utf-8")
    elif not marker.is_file():
        raise RuntimeError("Synthetic volume marker missing")
    os.environ.update(INSURECLEAR_AUTH_MODE="accounts", INSURECLEAR_AUTH_DB=str(root / "smoke-auth.sqlite3"), INSURECLEAR_JOB_DB=str(root / "smoke-jobs.sqlite3"), INSURECLEAR_CORS_ORIGINS="https://pilot.example.test", INSURECLEAR_AUTH_COOKIE_SECURE="true")
    if mode == "upgrade":
        with sqlite3.connect(os.environ["INSURECLEAR_JOB_DB"]) as db:
            db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY,payload_json TEXT NOT NULL,status TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,stage TEXT NOT NULL DEFAULT 'queued',message TEXT NOT NULL DEFAULT '',case_id TEXT NOT NULL,mode TEXT NOT NULL,fresh_run INTEGER NOT NULL DEFAULT 0,result_json TEXT,error TEXT,traceback TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)")
            db.execute("INSERT INTO jobs(id,payload_json,status,case_id,mode,created_at,updated_at) VALUES('legacy','{}','completed','legacy','text','2000-01-01','2000-01-01')")
        old_corpus = root / "regulatory"; old_corpus.mkdir()
        (old_corpus / "registry.json").write_text("{}", encoding="utf-8")
    from fastapi.testclient import TestClient
    from tools.auth_store import AuthStore
    from tools.review_store import ReviewStore
    from tools.regulatory_registry import load_registry
    from web import api
    api._start_worker = lambda: None
    store = AuthStore(os.environ["INSURECLEAR_AUTH_DB"])
    password = "synthetic smoke phrase 2026"
    if mode != "inspect":
        store.create_user("alice", password, "smoke-org", "claimant")
        store.create_user("bob", password, "smoke-org", "claimant")
        store.create_user("reviewer", password, "smoke-org", "reviewer")
    clients = {}
    for name in ("alice", "bob", "reviewer"):
        client = TestClient(api.app, base_url="https://pilot.example.test")
        response = client.post("/api/auth/login", headers={"Origin": "https://pilot.example.test"}, json={"username": name, "password": password})
        assert response.status_code == 200
        client.headers.update({"Origin": "https://pilot.example.test", "X-CSRF-Token": response.json()["csrf_token"]})
        clients[name] = client
    registry = load_registry()
    assert len(registry.sources) == 3 and len(registry.clauses) == 9
    if mode == "inspect":
        job_id = (root / ".smoke-job-id").read_text()
        assert ReviewStore(api.job_store.db_path).get(job_id)["status"] == "approved"
        assert clients["alice"].get(f"/api/jobs/{job_id}/download/approved-letter").status_code == 200
        assert clients["bob"].get(f"/api/jobs/{job_id}").status_code == 404
    else:
        response = clients["alice"].post("/api/analyze", data={"mode": "text", "case_id": "synthetic_smoke", "denial_text": "The insurer denied the synthetic claim because of an alleged treatment exclusion.", "policy_text": "The synthetic policy covers hospital treatment subject to the stated exclusions and limits."})
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        letter = "Please review the synthetic claim using the supplied policy wording."
        report = {"appeal_letter": letter, "source_evidence": {"denial": "Synthetic denial concerning hospital treatment.", "policy": "Hospital treatment is covered subject to stated exclusions.", "regulatory": ""}, "evidence_validation": {"valid": True, "errors": []}, "regulatory_evidence": {"registry_fingerprint": registry.fingerprint}, "pipeline_stats": {"final_recommendation": "REVIEW_REQUIRED"}}
        claimed = api.job_store.claim_next(); assert claimed[0] == job_id
        api.run_pipeline = lambda **kwargs: report
        api._run_job(*claimed)
        assert clients["alice"].get(f"/api/jobs/{job_id}").json()["status"] == "completed"
        assert clients["bob"].get(f"/api/jobs/{job_id}/report").status_code == 404
        assert clients["reviewer"].get(f"/api/jobs/{job_id}/review").json()["version"] == 1
        checks = dict(facts_checked=True, coverage_checked=True, legal_checked=True)
        approved = clients["reviewer"].post(f"/api/jobs/{job_id}/review/decision", json={"expected_version": 1, "decision": "approved", "checks": checks})
        assert approved.status_code == 200
        exported = clients["alice"].get(f"/api/jobs/{job_id}/download/approved-letter")
        assert exported.text == letter and exported.headers["cache-control"] == "no-store"
        (root / ".smoke-job-id").write_text(job_id)
        if mode == "upgrade":
            assert api.job_store.get("legacy")["owner_id"] is None
            assert clients["reviewer"].get("/api/jobs/legacy").status_code == 404
    print(json.dumps({"mode": mode, "result": "passed", "registry_fingerprint": registry.fingerprint, "real_provider_calls": 0}), flush=True)
    if mode == "serve":
        # Explicit loopback-only synthetic browser fixture; not production TLS.
        os.environ["INSURECLEAR_CORS_ORIGINS"] = "http://127.0.0.1:18772"
        os.environ["INSURECLEAR_AUTH_COOKIE_SECURE"] = "false"
        import uvicorn
        uvicorn.run(api.app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main(sys.argv[1])
