"""Durable SQLite-backed job queue for InsureClear."""

from __future__ import annotations

import errno
import json
import os
import sqlite3
from contextlib import contextmanager
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "jobs.sqlite3"
ACCOUNT_CASE_PREFIX = "job_"


class QueueFull(ValueError):
    pass


class JobStore:
    """Persist queued and completed jobs so API restarts do not lose state."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT 'queued',
                    message TEXT NOT NULL DEFAULT '',
                    case_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    fresh_run INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    error TEXT,
                    traceback TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
            for column in ("owner_id", "org_id", "case_label"):
                if column not in columns:
                    connection.execute(f"ALTER TABLE jobs ADD COLUMN {column} TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS job_owners ON jobs(org_id, owner_id, created_at)")

    @contextmanager
    def worker_lock(self):
        """Hold the single-worker process lock through execution and upload cleanup."""
        lock_path = Path(str(self.db_path.resolve()) + ".worker.lock")
        with lock_path.open("a+b") as handle:
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                yield False
                return
            try:
                yield True
            finally:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def recover_running(self) -> None:
        """Recover orphaned jobs after obtaining the exclusive worker lock."""
        with self._lock, self._connect() as connection:
            connection.execute("UPDATE jobs SET status='cancelled',stage='cancelled',message='Cancelled during restart',updated_at=? WHERE status='cancellation_requested'", (self._now(),))
            connection.execute(
                "UPDATE jobs SET status = 'queued', stage = 'queued', "
                "message = 'Recovered after restart', updated_at = ? WHERE status = 'running'",
                (self._now(),),
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, job_id: str, payload: dict[str, Any], mode: str, case_id: str, fresh_run: bool, owner_id: str | None = None, org_id: str | None = None, case_label: str | None = None) -> None:
        now = self._now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            maximum = int(os.getenv("INSURECLEAR_MAX_PENDING_JOBS", "100"))
            per_owner = int(os.getenv("INSURECLEAR_MAX_PENDING_PER_USER", "3"))
            if maximum < 1 or per_owner < 1:
                raise ValueError("Queue limits must be positive")
            pending = "status IN ('queued','running','cancellation_requested')"
            if connection.execute(f"SELECT COUNT(*) FROM jobs WHERE {pending}").fetchone()[0] >= maximum:
                raise QueueFull("Queue admission limit reached")
            if owner_id and connection.execute(f"SELECT COUNT(*) FROM jobs WHERE {pending} AND org_id=? AND owner_id=?", (org_id, owner_id)).fetchone()[0] >= per_owner:
                raise QueueFull("Account pending-case limit reached")
            connection.execute(
                """
                INSERT INTO jobs (
                    id, payload_json, status, progress, stage, message, case_id,
                    mode, fresh_run, created_at, updated_at, owner_id, org_id, case_label
                ) VALUES (?, ?, 'queued', 0, 'queued', 'Job queued', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, json.dumps(payload), case_id, mode, int(fresh_run), now, now, owner_id, org_id, case_label),
            )

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def list_for(self, principal: dict) -> list[dict]:
        columns = "id,status,progress,stage,message,case_id,case_label,mode,created_at,updated_at,owner_id,org_id"
        if principal.get("legacy"):
            where = "owner_id IS NULL AND lower(substr(case_id, 1, ?)) != ?"
            values = (len(ACCOUNT_CASE_PREFIX), ACCOUNT_CASE_PREFIX)
        elif principal.get("role") in {"reviewer", "admin"}:
            where, values = "org_id = ? AND owner_id IS NOT NULL", (principal["org_id"],)
        else:
            where, values = "org_id = ? AND owner_id = ?", (principal["org_id"], principal["user_id"])
        with self._connect() as db:
            return [dict(row) for row in db.execute(f"SELECT {columns} FROM jobs WHERE ({where}) AND status != 'deleting' ORDER BY created_at DESC LIMIT 200", values)]

    def get_payload(self, job_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT payload_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def update(self, job_id: str, **fields: Any) -> None:
        allowed = {
            "status", "progress", "stage", "message", "result", "error", "traceback"
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        values: list[Any] = []
        assignments: list[str] = []
        for key, value in updates.items():
            column = "result_json" if key == "result" else key
            assignments.append(f"{column} = ?")
            values.append(json.dumps(value) if key == "result" else value)
        assignments.append("updated_at = ?")
        values.append(self._now())
        values.append(job_id)
        with self._lock, self._connect() as connection:
            connection.execute(f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", values)

    def stop(self, job_id: str, status: str, message: str, error_type: str) -> bool:
        if status not in {"failed", "cancelled", "timed_out"}:
            raise ValueError("Unknown terminal stop status")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row[0] not in {"running", "cancellation_requested"}:
                return False
            status = "cancelled" if row[0] == "cancellation_requested" else status
            db.execute("UPDATE jobs SET status=?,stage=?,message=?,error=?,traceback=NULL,updated_at=? WHERE id=?", (status, status, message, error_type, self._now(), job_id))
            return True

    def complete(self, job_id: str, result: dict) -> bool:
        """Completion and cancellation contend for the same durable write lock."""
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return False
            if row[0] == "cancellation_requested":
                db.execute("UPDATE jobs SET status='cancelled',stage='cancelled',message='Cancelled',updated_at=? WHERE id=?", (self._now(), job_id))
                return False
            if row[0] != "running":
                return False
            db.execute("UPDATE jobs SET status='completed',stage='complete',progress=100,message='Pipeline complete',result_json=?,error=NULL,traceback=NULL,updated_at=? WHERE id=?", (json.dumps(result), self._now(), job_id))
            return True

    def cancel(self, job_id: str) -> str:
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise ValueError("Unknown job")
            status = {"queued": "cancelled", "running": "cancellation_requested"}.get(row[0], row[0])
            db.execute("UPDATE jobs SET status=?,stage=?,message=?,updated_at=? WHERE id=?", (status, status, "Cancellation requested" if status == "cancellation_requested" else "Job cancelled" if status == "cancelled" else "Job unchanged", self._now(), job_id))
            return status

    def begin_delete(self, job_id: str) -> dict:
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise ValueError("Unknown job")
            if row["status"] in {"running", "cancellation_requested"}:
                raise ValueError("Cannot delete active work")
            snapshot = self._row_to_job(row)
            snapshot["payload"] = json.loads(row["payload_json"])
            db.execute("UPDATE jobs SET status='deleting',stage='deleting',message='Deleting private records',updated_at=? WHERE id=?", (self._now(), job_id))
            return snapshot

    def finish_delete(self, job_id: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("DELETE FROM jobs WHERE id=? AND status='deleting'", (job_id,))

    def claim_next(self) -> tuple[str, dict[str, Any]] | None:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, payload_json FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not row:
                connection.commit()
                return None
            connection.execute(
                "UPDATE jobs SET status = 'running', stage = 'starting', message = 'Preparing pipeline', updated_at = ? WHERE id = ?",
                (self._now(), row["id"]),
            )
            connection.commit()
        return row["id"], json.loads(row["payload_json"])

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["fresh_run"] = bool(result["fresh_run"])
        raw_result = result.pop("result_json", None)
        result["result"] = json.loads(raw_result) if raw_result else None
        result.pop("payload_json", None)
        return result
