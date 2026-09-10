"""Durable SQLite-backed job queue for InsureClear."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "jobs.sqlite3"


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
            connection.execute(
                "UPDATE jobs SET status = 'queued', stage = 'queued', message = 'Recovered after restart' WHERE status = 'running'"
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, job_id: str, payload: dict[str, Any], mode: str, case_id: str, fresh_run: bool) -> None:
        now = self._now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, payload_json, status, progress, stage, message, case_id,
                    mode, fresh_run, created_at, updated_at
                ) VALUES (?, ?, 'queued', 0, 'queued', 'Job queued', ?, ?, ?, ?, ?)
                """,
                (job_id, json.dumps(payload), case_id, mode, int(fresh_run), now, now),
            )

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

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
        result["result"] = json.loads(result.pop("result_json")) if result.get("result_json") else None
        result.pop("payload_json", None)
        return result
