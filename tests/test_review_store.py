"""Synthetic, temporary-database review persistence contract tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import importlib
import importlib.util
import sqlite3
import threading

import pytest


CHECKS = {"facts_checked": True, "coverage_checked": True, "legal_checked": True}


@pytest.fixture
def module():
    assert importlib.util.find_spec("tools.review_store") is not None, "review persistence module is not implemented"
    return importlib.import_module("tools.review_store")


@pytest.fixture
def store(module, tmp_path):
    return module.ReviewStore(tmp_path / "reviews.sqlite3")


def initialize(store, job_id="job"):
    return store.initialize(job_id, "org", "Original fictional letter", "source-a")


def test_initial_draft_persists_without_approval(module, store):
    state = initialize(store)
    assert state is not None, "initialization must persist an unapproved draft"
    assert state["version"] == 1
    assert state["status"] == "draft"
    assert state["approval"] is None
    assert state["letter"] == "Original fictional letter"
    assert state["letter_sha256"] == hashlib.sha256(b"Original fictional letter").hexdigest()
    assert state["source_fingerprint"] == "source-a"
    assert state["org_id"] == "org"
    assert module.ReviewStore(store.db_path).get("job") == state
    assert store.get("unknown") is None


def test_reinitializing_preserves_current_draft_and_immutable_source(module, store):
    initialize(store)
    edited = store.edit("job", "author", 1, "Correction", "corrected typo")
    assert store.initialize("job", "org", "Different ignored generation", "source-a") == edited
    for org, fingerprint in [("org", "source-b"), ("other-org", "source-a")]:
        with pytest.raises(module.ReviewConflict):
            store.initialize("job", org, "Replacement", fingerprint)
    assert store.get("job") == edited


def test_edit_preserves_original_history_and_actor_reason_time(store):
    original = initialize(store)
    changed = store.edit("job", "actor-1", 1, "Corrected fictional letter", "corrected facts")
    assert changed["version"] == 2
    assert changed["history"][:1] == original["history"]
    event = changed["history"][-1]
    assert event["letter"] == "Corrected fictional letter"
    assert event["actor_id"] == "actor-1"
    assert event["note"] == "corrected facts"
    assert event["source_fingerprint"] == "source-a"
    assert event["letter_sha256"] == hashlib.sha256(b"Corrected fictional letter").hexdigest()
    assert datetime.fromisoformat(event["created_at"]).utcoffset().total_seconds() == 0
    assert [event["version"] for event in changed["history"]] == [1, 2]
    changed["history"][0]["letter"] = "local tampering"
    assert store.get("job")["history"][0]["letter"] == "Original fictional letter"


def test_approval_binds_exact_letter_source_and_version(store):
    initialize(store)
    approved = store.decide("job", "reviewer", 1, "approved", "checked evidence", CHECKS)
    assert approved["version"] == 2
    assert approved["status"] == "approved"
    assert approved["approval"]["version"] == 2
    assert approved["approval"]["reviewed_version"] == 1
    assert approved["approval"]["letter_sha256"] == hashlib.sha256(b"Original fictional letter").hexdigest()
    assert approved["approval"]["source_fingerprint"] == "source-a"
    assert approved["approval"]["checks"] == CHECKS
    assert approved["history"][-1]["actor_id"] == "reviewer"
    assert approved["history"][-1]["note"] == "checked evidence"
    assert approved["history"][-1]["action"] == "approved"


def test_edit_even_same_letter_invalidates_approval_and_advances_version(module, store):
    initialize(store)
    approved = store.decide("job", "reviewer", 1, "approved", "checked", CHECKS)
    edited = store.edit("job", "author", 2, approved["letter"], "reopened")
    assert edited["version"] == 3
    assert edited["status"] == "draft"
    assert edited["approval"] is None
    assert edited["history"][:2] == approved["history"]
    with pytest.raises(module.ReviewConflict):
        store.decide("job", "reviewer", 2, "approved", "stale", CHECKS)


def test_each_decision_invalidates_stale_tabs(module, store):
    initialize(store)
    requested = store.decide("job", "reviewer", 1, "changes_requested", "missing facts", {})
    assert requested["version"] == 2
    assert requested["status"] == "changes_requested"
    assert requested["approval"] is None
    with pytest.raises(module.ReviewConflict):
        store.edit("job", "author", 1, "Stale correction", "stale")
    with pytest.raises(module.ReviewConflict):
        store.decide("job", "other-reviewer", 1, "approved", "stale", CHECKS)
    approved = store.decide("job", "reviewer", 2, "approved", "checked", CHECKS)
    requested_again = store.decide("job", "reviewer", 3, "changes_requested", "reopen", {})
    assert requested_again["version"] == 4
    assert requested_again["approval"] is None
    assert requested_again["history"][:3] == approved["history"]


@pytest.mark.parametrize("checks", [{}, {**CHECKS, "facts_checked": False}, {**CHECKS, "coverage_checked": 1}, {**CHECKS, "legal_checked": "yes"}, None])
def test_approval_requires_three_explicit_boolean_confirmations(store, checks):
    before = initialize(store)
    with pytest.raises(ValueError):
        store.decide("job", "reviewer", 1, "approved", "unchecked", checks)
    assert store.get("job") == before


def test_empty_letter_and_unknown_decision_cannot_be_approved(store):
    store.initialize("job", "org", " \n\t", "source-a")
    with pytest.raises(ValueError):
        store.decide("job", "reviewer", 1, "approved", "empty", CHECKS)
    with pytest.raises(ValueError):
        store.decide("job", "reviewer", 1, "sent", "unknown", {})
    assert store.get("job")["version"] == 1


@pytest.mark.parametrize("action", ["edit", "decision", "mixed"])
def test_concurrent_store_instances_allow_exactly_one_current_mutation(module, store, action):
    initialize(store)
    second = module.ReviewStore(store.db_path)
    barrier = threading.Barrier(2)

    def mutate(instance, index):
        barrier.wait(timeout=5)
        try:
            if action == "edit" or (action == "mixed" and index == 0):
                return instance.edit("job", str(index), 1, f"Correction {index}", "edit")
            return instance.decide("job", str(index), 1, "approved", "checked", CHECKS)
        except module.ReviewConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(mutate, instance, index) for index, instance in enumerate((store, second))]
        results = [future.result(timeout=10) for future in futures]
    assert sum(result == "conflict" for result in results) == 1
    assert store.get("job")["version"] == 2
    assert len(store.get("job")["history"]) == 2


def test_deletion_is_isolated_durable_and_content_free(module, store):
    initialize(store)
    other = initialize(store, "other")
    store.decide("job", "reviewer", 1, "approved", "checked", CHECKS)
    store.delete("job")
    store.delete("job")
    assert store.get("job") is None
    assert store.get("other") == other
    reopened = module.ReviewStore(store.db_path)
    for operation in [lambda: reopened.initialize("job", "org", "Sensitive replacement", "source-a"), lambda: reopened.edit("job", "actor", 2, "Correction", "reason"), lambda: reopened.decide("job", "reviewer", 2, "approved", "checked", CHECKS)]:
        with pytest.raises(module.ReviewConflict):
            operation()
    with sqlite3.connect(store.db_path) as connection:
        dump = "\n".join(connection.iterdump())
    assert "Original fictional letter" in dump  # only the other job remains
    assert "Sensitive replacement" not in dump
    assert "reviewer" not in dump
    assert "checked" not in dump
    assert "('job', 'org'" not in dump


@pytest.mark.parametrize("action", ["initialize", "edit", "decision"])
def test_delete_racing_each_writer_cannot_recreate_private_rows(module, store, action):
    second = module.ReviewStore(store.db_path)
    for index in range(12):
        job_id = f"race-{index}"
        if action != "initialize":
            initialize(store, job_id)
        barrier = threading.Barrier(2)

        def write():
            barrier.wait(timeout=5)
            try:
                if action == "initialize":
                    second.initialize(job_id, "org", "Fictional sensitive text", "source-a")
                elif action == "edit":
                    second.edit(job_id, "actor", 1, "Fictional sensitive correction", "reason")
                else:
                    second.decide(job_id, "reviewer", 1, "approved", "checked", CHECKS)
            except module.ReviewConflict:
                pass

        def delete():
            barrier.wait(timeout=5)
            store.delete(job_id)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write), pool.submit(delete)]
            for future in futures:
                future.result(timeout=10)
        assert store.get(job_id) is None
        with pytest.raises(module.ReviewConflict):
            second.initialize(job_id, "org", "Late resurrection", "source-a")


def test_missing_review_writes_fail_without_creating_state(module, store):
    with pytest.raises(module.ReviewConflict):
        store.edit("missing", "actor", 1, "letter", "note")
    with pytest.raises(module.ReviewConflict):
        store.decide("missing", "reviewer", 1, "approved", "note", CHECKS)
    assert store.get("missing") is None


def test_identifiers_and_letters_are_bound_sql_values(store):
    job_id = "job'); DROP TABLE review_versions; --"
    letter = "Fictional O'Brien's policy\nUnicode: कवरेज"
    store.initialize(job_id, "org'", letter, "source'")
    state = store.edit(job_id, "actor'", 1, letter + " correction", "reason'")
    assert state["letter"] == letter + " correction"
    assert state["history"][0]["letter"] == letter
    assert initialize(store)["version"] == 1


@pytest.mark.parametrize("action", ["initialize", "edit", "decision"])
def test_inflight_deletion_fences_writer_after_it_obtains_the_write_lock(module, store, monkeypatch, action):
    """Pause real SQLite deletion while its tombstone remains uncommitted.

    A write that checks the tombstone before obtaining its transaction sees the
    old state and either resurrects it or fails incorrectly after deletion.
    """
    if action != "initialize":
        initialize(store)
    second = module.ReviewStore(store.db_path)
    deletion_held = threading.Event()
    writer_attempting_lock = threading.Event()
    release_deletion = threading.Event()
    real_connect = sqlite3.connect

    class ScheduledConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            name = threading.current_thread().name
            if name.startswith("deleting") and sql.startswith("DELETE FROM review_versions"):
                deletion_held.set()
                assert release_deletion.wait(timeout=10)
            if name.startswith("writing") and sql == "BEGIN IMMEDIATE":
                writer_attempting_lock.set()
            return super().execute(sql, parameters)

    def connect(*args, **kwargs):
        return real_connect(*args, **kwargs, factory=ScheduledConnection)

    monkeypatch.setattr(module.sqlite3, "connect", connect)

    def write():
        with pytest.raises(module.ReviewConflict):
            if action == "initialize":
                second.initialize("job", "org", "Late private text", "source-a")
            elif action == "edit":
                second.edit("job", "actor", 1, "Late private edit", "reason")
            else:
                second.decide("job", "reviewer", 1, "approved", "checked", CHECKS)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="deleting") as deleting:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="writing") as writing:
            deletion = deleting.submit(store.delete, "job")
            try:
                assert deletion_held.wait(timeout=5)
                mutation = writing.submit(write)
                assert writer_attempting_lock.wait(timeout=5)
            finally:
                release_deletion.set()
            deletion.result(timeout=10)
            mutation.result(timeout=10)
    assert second.get("job") is None


def test_deletion_writes_tombstone_before_purging_private_history(store):
    initialize(store)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("""
            CREATE TRIGGER require_fence_before_purge BEFORE DELETE ON review_versions
            WHEN NOT EXISTS (SELECT 1 FROM review_tombstones WHERE job_id = OLD.job_id)
            BEGIN SELECT RAISE(ABORT, 'missing deletion fence'); END
        """)
    store.delete("job")
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT * FROM review_tombstones").fetchall() == [("job",)]
        assert connection.execute("SELECT COUNT(*) FROM review_sources").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM review_versions").fetchone()[0] == 0


@pytest.mark.parametrize("expected_version", [True, 1.0, "1", 0, -1])
def test_revision_tokens_require_an_exact_positive_integer(module, store, expected_version):
    before = initialize(store)
    with pytest.raises(module.ReviewConflict):
        store.edit("job", "actor", expected_version, "Correction", "reason")
    with pytest.raises(module.ReviewConflict):
        store.decide("job", "reviewer", expected_version, "approved", "checked", CHECKS)
    assert store.get("job") == before
