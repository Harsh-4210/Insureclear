from pathlib import Path
import pytest
from tools.job_store import JobStore
from tools.review_store import ReviewStore, ReviewConflict
from tools.case_lifecycle import delete_case, retention_candidates


def make_job(tmp_path, status="queued"):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create("job1", {"case_id": "job_job1"}, "text", "job_job1", False, owner_id="alice", org_id="org")
    if status != "queued": store.update("job1", status=status)
    roots = {key: tmp_path / key for key in ["sessions", "inputs", "outputs"]}
    for root in roots.values(): root.mkdir()
    return store, ReviewStore(store.db_path), roots


def test_cancelled_job_is_never_claimed_and_restart_finishes_cancellation(tmp_path):
    store, _, _ = make_job(tmp_path)
    assert store.cancel("job1") == "cancelled"
    assert store.claim_next() is None
    store.update("job1", status="running")
    assert store.cancel("job1") == "cancellation_requested"
    store.recover_running()
    assert store.get("job1")["status"] == "cancelled"


def test_delete_fences_queue_cleans_only_case_roots_and_prevents_review_recreation(tmp_path):
    store, reviews, roots = make_job(tmp_path)
    for key, name in [("sessions", "job_job1"), ("inputs", "job1"), ("outputs", "job_job1_stamp")]:
        folder = roots[key] / name; folder.mkdir(); (folder / "private.txt").write_text("private")
    store.update("job1", result={"artifacts": {"output_dir": str(roots["outputs"] / "job_job1_stamp")}})
    reviews.initialize("job1", "org", "Private draft", "source")
    delete_case(store, reviews, "job1", roots)
    assert store.get("job1") is None and store.claim_next() is None
    assert reviews.get("job1") is None
    assert all(not list(root.iterdir()) for root in roots.values())
    with pytest.raises(ReviewConflict): reviews.initialize("job1", "org", "Late draft", "source")


def test_running_delete_and_output_escape_are_refused(tmp_path):
    store, reviews, roots = make_job(tmp_path, "running")
    with pytest.raises(ValueError, match="active"): delete_case(store, reviews, "job1", roots)
    assert store.get("job1")["status"] == "running"
    store.update("job1", status="completed", result={"artifacts": {"output_dir": str(tmp_path)}})
    with pytest.raises(ValueError, match="path"): delete_case(store, reviews, "job1", roots)
    assert tmp_path.exists()


def test_retention_is_preview_only_and_excludes_active_unowned_and_recent(tmp_path):
    store, _, _ = make_job(tmp_path, "completed")
    old = "2000-01-01T00:00:00+00:00"
    with store._connect() as db: db.execute("UPDATE jobs SET updated_at=? WHERE id='job1'", (old,))
    store.create("running", {"case_id": "running"}, "text", "running", False, owner_id="alice", org_id="org")
    store.create("legacy", {"case_id": "legacy"}, "text", "legacy", False)
    assert [job["id"] for job in retention_candidates(store, 30)] == ["job1"]
    assert store.get("job1") is not None


def test_cancellation_wins_completion_race_without_persisting_result(tmp_path):
    store, _, _ = make_job(tmp_path, "running")
    store.cancel("job1")
    assert store.complete("job1", {"appeal_letter": "Private late result"}) is False
    assert store.get("job1")["status"] == "cancelled"
    assert store.get("job1")["result"] is None


def test_cleanup_rejects_a_symlink_before_deleting_any_target(tmp_path):
    from tools.case_lifecycle import confined_path
    root = tmp_path / "root"; root.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    link = root / "link"
    try: link.symlink_to(outside, target_is_directory=True)
    except OSError: pytest.skip("Windows account cannot create a symlink")
    with pytest.raises(ValueError, match="path"): confined_path(root, link / "private")
    assert outside.exists()


def test_worker_stop_cannot_overwrite_deletion_fence(tmp_path):
    store, _, _ = make_job(tmp_path, "running")
    store.cancel("job1")
    assert store.complete("job1", {"appeal_letter": "Late result"}) is False
    store.begin_delete("job1")
    assert store.stop("job1", "cancelled", "Cancelled", "PipelineCancelled") is False
    assert store.get("job1")["status"] == "deleting"
    store.finish_delete("job1")
    assert store.get("job1") is None
