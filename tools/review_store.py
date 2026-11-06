"""SQLite review history; authorization and evidence validation belong to the API.

Every edit and decision is a revision. Initialization is idempotent only for the
same immutable organization/source. Deletion retains only an opaque job-ID fence.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any


class ReviewConflict(Exception):
    """The review is missing, deleted, stale, or bound to a different source."""


class ReviewStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction(write=True) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS review_tombstones (
                    job_id TEXT PRIMARY KEY
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS review_sources (
                    job_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS review_versions (
                    job_id TEXT NOT NULL REFERENCES review_sources(job_id),
                    version INTEGER NOT NULL CHECK (version > 0),
                    letter TEXT NOT NULL,
                    letter_sha256 TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'changes_requested')),
                    action TEXT NOT NULL,
                    actor_id TEXT,
                    created_at TEXT NOT NULL,
                    note TEXT NOT NULL,
                    checks_json TEXT NOT NULL,
                    approval_json TEXT,
                    PRIMARY KEY (job_id, version)
                )
            """)

    @contextmanager
    def _transaction(self, *, write: bool = False):
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA secure_delete = ON")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _not_deleted(connection: sqlite3.Connection, job_id: str) -> None:
        if connection.execute(
            "SELECT 1 FROM review_tombstones WHERE job_id = ?", (job_id,)
        ).fetchone():
            raise ReviewConflict("Review was deleted")

    @staticmethod
    def _read(connection: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
        source = connection.execute(
            "SELECT * FROM review_sources WHERE job_id = ?", (job_id,)
        ).fetchone()
        if source is None:
            return None
        rows = connection.execute(
            "SELECT * FROM review_versions WHERE job_id = ? ORDER BY version", (job_id,)
        ).fetchall()
        history = []
        for row in rows:
            event = dict(row)
            event["checks"] = json.loads(event.pop("checks_json"))
            approval_json = event.pop("approval_json")
            event["approval"] = json.loads(approval_json) if approval_json else None
            history.append(event)
        if not history:
            raise ReviewConflict("Review history is missing")
        current = dict(history[-1])
        if current["source_fingerprint"] != source["source_fingerprint"]:
            raise ReviewConflict("Review source changed")
        current.update(org_id=source["org_id"], history=history)
        return current

    @staticmethod
    def _append(connection: sqlite3.Connection, *, job_id: str, version: int,
                letter: str, source_fingerprint: str, status: str, action: str,
                actor_id: str | None, note: str, checks: dict[str, bool],
                approved: bool = False) -> None:
        created_at = ReviewStore._now()
        letter_sha256 = hashlib.sha256(letter.encode("utf-8")).hexdigest()
        approval = None
        if approved:
            approval = dict(version=version, reviewed_version=version - 1,
                            letter_sha256=letter_sha256,
                            source_fingerprint=source_fingerprint, actor_id=actor_id,
                            created_at=created_at, checks=checks)
        connection.execute("""
            INSERT INTO review_versions (
                job_id, version, letter, letter_sha256, source_fingerprint, status,
                action, actor_id, created_at, note, checks_json, approval_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, version, letter, letter_sha256, source_fingerprint, status,
              action, actor_id, created_at, note, json.dumps(checks),
              json.dumps(approval) if approval else None))

    def initialize(self, job_id: str, org_id: str, letter: str,
                   source_fingerprint: str) -> dict[str, Any]:
        with self._transaction(write=True) as connection:
            self._not_deleted(connection, job_id)
            current = self._read(connection, job_id)
            if current is not None:
                if (current["source_fingerprint"] != source_fingerprint
                        or current["org_id"] != org_id):
                    raise ReviewConflict("Review source or organization changed")
                return current
            connection.execute(
                "INSERT INTO review_sources (job_id, org_id, source_fingerprint, created_at) VALUES (?, ?, ?, ?)",
                (job_id, org_id, source_fingerprint, self._now()),
            )
            self._append(connection, job_id=job_id, version=1, letter=letter,
                         source_fingerprint=source_fingerprint, status="draft",
                         action="initialized", actor_id=None, note="", checks={})
            return self._read(connection, job_id)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._transaction() as connection:
            return self._read(connection, job_id)

    def _current(self, connection: sqlite3.Connection, job_id: str,
                 expected_version: int) -> dict[str, Any]:
        self._not_deleted(connection, job_id)
        if type(expected_version) is not int or expected_version < 1:
            raise ReviewConflict("Expected version must be a positive integer")
        current = self._read(connection, job_id)
        if current is None or current["version"] != expected_version:
            raise ReviewConflict("Review version changed or is missing")
        return current

    def edit(self, job_id: str, actor_id: str, expected_version: int,
             letter: str, note: str) -> dict[str, Any]:
        with self._transaction(write=True) as connection:
            current = self._current(connection, job_id, expected_version)
            self._append(connection, job_id=job_id, version=current["version"] + 1,
                         letter=letter, source_fingerprint=current["source_fingerprint"],
                         status="draft", action="edited", actor_id=actor_id,
                         note=note, checks={})
            return self._read(connection, job_id)

    def decide(self, job_id: str, actor_id: str, expected_version: int,
               decision: str, note: str,
               checks: dict[str, bool]) -> dict[str, Any]:
        with self._transaction(write=True) as connection:
            current = self._current(connection, job_id, expected_version)
            if decision not in ("approved", "changes_requested"):
                raise ValueError("Unknown review decision")
            required = ("facts_checked", "coverage_checked", "legal_checked")
            if decision == "approved":
                if not current["letter"].strip():
                    raise ValueError("Approval requires a nonempty letter")
                if not isinstance(checks, dict) or not all(
                    checks.get(key) is True for key in required
                ):
                    raise ValueError("Approval requires all three explicit confirmations")
            confirmations = {
                key: checks[key] is True for key in required if key in checks
            } if isinstance(checks, dict) else {}
            self._append(connection, job_id=job_id, version=current["version"] + 1,
                         letter=current["letter"],
                         source_fingerprint=current["source_fingerprint"],
                         status=decision, action=decision, actor_id=actor_id,
                         note=note, checks=confirmations, approved=decision == "approved")
            return self._read(connection, job_id)

    def delete(self, job_id: str) -> None:
        """Purge private review rows, retaining an irreversible opaque-ID fence.

        This does not erase filesystem outputs, backups, or other databases.
        The job lifecycle controller must fence workers before private cleanup.
        """
        with self._transaction(write=True) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO review_tombstones (job_id) VALUES (?)", (job_id,)
            )
            connection.execute("DELETE FROM review_versions WHERE job_id = ?", (job_id,))
            connection.execute("DELETE FROM review_sources WHERE job_id = ?", (job_id,))
