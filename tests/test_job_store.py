from tools.job_store import JobStore


def test_opening_a_second_store_does_not_requeue_a_live_job(tmp_path):
    first = JobStore(tmp_path / "jobs.sqlite3")
    first.create("job", {"case_id": "case"}, "text", "case", False)
    assert first.claim_next()[0] == "job"
    second = JobStore(tmp_path / "jobs.sqlite3")
    assert second.get("job")["status"] == "running"
    assert second.claim_next() is None


def test_worker_lock_prevents_competing_recovery_and_releases_on_exit(tmp_path):
    first = JobStore(tmp_path / "jobs.sqlite3")
    second = JobStore(tmp_path / "jobs.sqlite3")
    first.create("job", {"case_id": "case"}, "text", "case", False)
    with first.worker_lock() as acquired:
        assert acquired
        assert first.claim_next()[0] == "job"
        with second.worker_lock() as competing:
            assert not competing
        assert second.get("job")["status"] == "running"
    with second.worker_lock() as acquired:
        assert acquired
        second.recover_running()
        assert second.claim_next()[0] == "job"
