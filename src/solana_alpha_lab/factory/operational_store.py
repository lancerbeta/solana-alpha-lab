"""Minimal SQLite operational store. Owns job state only, never scientific truth."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping


class OperationalStoreError(ValueError):
    """Raised when operational state cannot be read or written safely."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class OperationalStore:
    def __init__(self, path: Path, *, readonly: bool = False) -> None:
        if path.is_absolute() is False:
            raise OperationalStoreError("OPS_STORE_PATH_NOT_ABSOLUTE")
        self.path = path
        self.readonly = readonly
        if readonly:
            if not path.is_file():
                raise OperationalStoreError("SOURCE_NOT_PRESENT")
            self._conn = sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro&immutable=1",
                uri=True,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connect()

    def _connect(self) -> None:
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                spec_relative TEXT NOT NULL,
                spec_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                blocker TEXT NOT NULL,
                terminal TEXT,
                evidence_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS commands (
                command_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acknowledgements (
                ack_id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                note TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        if not getattr(self, "readonly", False):
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._conn.close()

    def record_command(self, *, job_id: str, kind: str, payload: Mapping[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO commands(job_id, kind, created_at, payload_json) VALUES (?, ?, ?, ?)",
            (job_id, kind, _now(), json.dumps(dict(payload), sort_keys=True)),
        )
        self._conn.commit()

    def upsert_job(self, job: Mapping[str, Any]) -> None:
        now = _now()
        existing = self.get_job(str(job["job_id"]))
        created_at = str(existing["created_at"]) if existing else now
        self._conn.execute(
            """
            INSERT INTO jobs(
                job_id, experiment_id, spec_relative, spec_sha256, status,
                blocker, terminal, evidence_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                experiment_id=excluded.experiment_id,
                spec_relative=excluded.spec_relative,
                spec_sha256=excluded.spec_sha256,
                status=excluded.status,
                blocker=excluded.blocker,
                terminal=excluded.terminal,
                evidence_json=excluded.evidence_json,
                updated_at=excluded.updated_at
            """,
            (
                str(job["job_id"]),
                str(job["experiment_id"]),
                str(job["spec_relative"]),
                str(job["spec_sha256"]),
                str(job["status"]),
                str(job["blocker"]),
                job.get("terminal"),
                json.dumps(job.get("evidence") or {}, sort_keys=True),
                created_at,
                now,
            ),
        )
        self._conn.commit()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["evidence"] = json.loads(payload.pop("evidence_json"))
        return payload

    def latest_job(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM jobs ORDER BY updated_at DESC, job_id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["evidence"] = json.loads(payload.pop("evidence_json"))
        return payload

    def acknowledge(self, note: str) -> None:
        self._conn.execute(
            "INSERT INTO acknowledgements(created_at, note) VALUES (?, ?)",
            (_now(), note),
        )
        self._conn.commit()

    def record_runtime_event(self, *, kind: str, payload: Mapping[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO runtime_events(kind, created_at, payload_json) VALUES (?, ?, ?)",
            (kind, _now(), json.dumps(dict(payload), sort_keys=True)),
        )
        self._conn.commit()

    def runtime_events(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT event_id, kind, created_at, payload_json FROM runtime_events ORDER BY event_id ASC"
        ).fetchall()
        events = []
        for row in rows:
            payload = dict(row)
            payload["payload"] = json.loads(payload.pop("payload_json"))
            events.append(payload)
        return events

    def backup_to(self, dest: Path) -> None:
        if dest.is_absolute() is False:
            raise OperationalStoreError("OPS_STORE_PATH_NOT_ABSOLUTE")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        replica = sqlite3.connect(dest)
        try:
            self._conn.backup(replica)
            replica.commit()
        finally:
            replica.close()

    def restore_from(self, src: Path) -> None:
        if src.is_absolute() is False:
            raise OperationalStoreError("OPS_STORE_PATH_NOT_ABSOLUTE")
        if src.is_file() is False:
            raise OperationalStoreError("ROLLBACK_SNAPSHOT_MISSING")
        preserved_kinds = {str(event["kind"]) for event in self.runtime_events()}
        self._conn.close()
        shutil.copy2(src, self.path)
        wal = Path(str(self.path) + "-wal")
        shm = Path(str(self.path) + "-shm")
        if wal.exists():
            wal.unlink()
        if shm.exists():
            shm.unlink()
        self._connect()
        after_kinds = {str(event["kind"]) for event in self.runtime_events()}
        for kind in sorted(preserved_kinds - after_kinds):
            self.record_runtime_event(kind=kind, payload={"preserved_across_rollback": True})
