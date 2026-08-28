"""Dedicated SQLite due-work store for ObservationSchedule. Not scientific truth."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.observation_schedule import render_utc

LEASE_SECONDS = 55
GLOBAL_LEASE_ID = "observation-scheduler"
_TERMINAL_DUE_STATES = frozenset(
    {
        "OBSERVED",
        "MISSING_TYPED",
        "DISAPPEARED",
        "CENSORED",
        "IN_FLIGHT_CALL_INDETERMINATE",
        "DEPENDENCY_MISSING",
    }
)


class ObservationScheduleStoreError(ValueError):
    """Typed operational store failure."""


def _now(clock: datetime | None = None) -> str:
    value = clock.astimezone(UTC) if clock is not None else datetime.now(UTC)
    return render_utc(value)


class ObservationScheduleStore:
    def __init__(self, path: Path) -> None:
        if path.is_absolute() is False:
            raise ObservationScheduleStoreError("OPS_STORE_PATH_NOT_ABSOLUTE")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._connect()

    def _connect(self) -> None:
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schedule_activations (
                schedule_sha256 TEXT NOT NULL,
                activation_id TEXT NOT NULL,
                schedule_key TEXT NOT NULL,
                state TEXT NOT NULL,
                authority_receipt_sha256 TEXT,
                starts_at TEXT NOT NULL,
                stops_admitting_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (schedule_sha256, activation_id)
            );
            CREATE TABLE IF NOT EXISTS candidate_members (
                schedule_sha256 TEXT NOT NULL,
                activation_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                state TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (schedule_sha256, activation_id, entity_id)
            );
            CREATE TABLE IF NOT EXISTS due_observations (
                schedule_sha256 TEXT NOT NULL,
                activation_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                point_id TEXT NOT NULL,
                primitive_id TEXT NOT NULL,
                state TEXT NOT NULL,
                due_at TEXT NOT NULL,
                deadline_at TEXT NOT NULL,
                request_sha256 TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (
                    schedule_sha256, activation_id, entity_id, point_id, primitive_id
                )
            );
            CREATE TABLE IF NOT EXISTS call_ledger (
                request_sha256 TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                state TEXT NOT NULL,
                primitive_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (request_sha256, attempt_id)
            );
            CREATE TABLE IF NOT EXISTS scheduler_leases (
                lease_id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS publication_batches (
                batch_content_sha256 TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runtime_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS restore_markers (
                marker_id TEXT PRIMARY KEY,
                recovery_epoch TEXT NOT NULL,
                resolved INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS registered_schedules (
                schedule_sha256 TEXT PRIMARY KEY,
                schedule_key TEXT NOT NULL,
                document_json TEXT NOT NULL,
                document_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS authority_receipts (
                receipt_sha256 TEXT PRIMARY KEY,
                authority_id TEXT NOT NULL,
                schedule_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS accounting_counters (
                schedule_sha256 TEXT NOT NULL,
                activation_id TEXT NOT NULL,
                utc_day TEXT NOT NULL,
                provider_calls INTEGER NOT NULL,
                modeled_credits INTEGER NOT NULL,
                candidates INTEGER NOT NULL,
                members INTEGER NOT NULL,
                raw_bytes INTEGER NOT NULL,
                canonical_bytes INTEGER NOT NULL,
                last_provider_call_at TEXT,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (schedule_sha256, activation_id, utc_day)
            );
            CREATE TABLE IF NOT EXISTS lifetime_counters (
                schedule_sha256 TEXT NOT NULL,
                activation_id TEXT NOT NULL,
                provider_calls INTEGER NOT NULL,
                canonical_bytes INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (schedule_sha256, activation_id)
            );
            CREATE TABLE IF NOT EXISTS poll_slots (
                poll_slot_id TEXT PRIMARY KEY,
                request_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS publication_jobs (
                content_sha256 TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record_event(self, kind: str, payload: Mapping[str, Any], *, clock: datetime | None = None) -> None:
        self._conn.execute(
            "INSERT INTO runtime_events(kind, created_at, payload_json) VALUES (?, ?, ?)",
            (kind, _now(clock), json.dumps(dict(payload), sort_keys=True)),
        )
        self._conn.commit()

    def acquire_lease(self, owner: str, *, clock: datetime | None = None) -> bool:
        now = clock.astimezone(UTC) if clock is not None else datetime.now(UTC)
        now_text = render_utc(now)
        expires = render_utc(now.replace(microsecond=0) + __import__("datetime").timedelta(seconds=LEASE_SECONDS))
        row = self._conn.execute(
            "SELECT owner, expires_at FROM scheduler_leases WHERE lease_id = ?",
            (GLOBAL_LEASE_ID,),
        ).fetchone()
        if row is not None and str(row["expires_at"]) > now_text and str(row["owner"]) != owner:
            return False
        self._conn.execute(
            """
            INSERT INTO scheduler_leases(lease_id, owner, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(lease_id) DO UPDATE SET owner=excluded.owner, expires_at=excluded.expires_at
            """,
            (GLOBAL_LEASE_ID, owner, expires, now_text),
        )
        self._conn.commit()
        return True

    def release_lease(self, owner: str) -> None:
        self._conn.execute(
            "DELETE FROM scheduler_leases WHERE lease_id = ? AND owner = ?",
            (GLOBAL_LEASE_ID, owner),
        )
        self._conn.commit()

    def upsert_activation(self, row: Mapping[str, Any], *, clock: datetime | None = None) -> None:
        now = _now(clock)
        self._conn.execute(
            """
            INSERT INTO schedule_activations(
                schedule_sha256, activation_id, schedule_key, state,
                authority_receipt_sha256, starts_at, stops_admitting_at,
                payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(schedule_sha256, activation_id) DO UPDATE SET
                state=excluded.state,
                authority_receipt_sha256=excluded.authority_receipt_sha256,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                str(row["schedule_sha256"]),
                str(row["activation_id"]),
                str(row["schedule_key"]),
                str(row["state"]),
                row.get("authority_receipt_sha256"),
                str(row["starts_at"]),
                str(row["stops_admitting_at"]),
                json.dumps(dict(row.get("payload") or {}), sort_keys=True),
                now,
                now,
            ),
        )
        self._conn.commit()

    def get_activation(self, schedule_sha256: str, activation_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM schedule_activations WHERE schedule_sha256 = ? AND activation_id = ?",
            (schedule_sha256, activation_id),
        ).fetchone()
        return dict(row) if row is not None else None

    def insert_candidate(self, row: Mapping[str, Any], *, clock: datetime | None = None) -> bool:
        now = _now(clock)
        try:
            self._conn.execute(
                """
                INSERT INTO candidate_members(
                    schedule_sha256, activation_id, entity_id, state,
                    payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["schedule_sha256"]),
                    str(row["activation_id"]),
                    str(row["entity_id"]),
                    str(row["state"]),
                    json.dumps(dict(row.get("payload") or {}), sort_keys=True),
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def set_candidate_state(self, row: Mapping[str, Any], *, clock: datetime | None = None) -> None:
        now = _now(clock)
        cursor = self._conn.execute(
            """
            UPDATE candidate_members
            SET state = ?, payload_json = ?, updated_at = ?
            WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
            """,
            (
                str(row["state"]),
                json.dumps(dict(row.get("payload") or {}), sort_keys=True),
                now,
                str(row["schedule_sha256"]),
                str(row["activation_id"]),
                str(row["entity_id"]),
            ),
        )
        if cursor.rowcount != 1:
            raise ObservationScheduleStoreError("CANDIDATE_MISSING")
        self._conn.commit()

    def insert_due(self, row: Mapping[str, Any], *, clock: datetime | None = None) -> None:
        now = _now(clock)
        existing = self._conn.execute(
            """
            SELECT state FROM due_observations
            WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
              AND point_id = ? AND primitive_id = ?
            """,
            (
                str(row["schedule_sha256"]),
                str(row["activation_id"]),
                str(row["entity_id"]),
                str(row["point_id"]),
                str(row["primitive_id"]),
            ),
        ).fetchone()
        if existing is not None and str(existing["state"]) in _TERMINAL_DUE_STATES:
            new_state = str(row["state"])
            if new_state != str(existing["state"]):
                raise ObservationScheduleStoreError("DENY_RETROACTIVE_MUTATION")
        self._conn.execute(
            """
            INSERT INTO due_observations(
                schedule_sha256, activation_id, entity_id, point_id, primitive_id,
                state, due_at, deadline_at, request_sha256, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(schedule_sha256, activation_id, entity_id, point_id, primitive_id)
            DO UPDATE SET
                state=excluded.state,
                request_sha256=COALESCE(excluded.request_sha256, due_observations.request_sha256),
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                str(row["schedule_sha256"]),
                str(row["activation_id"]),
                str(row["entity_id"]),
                str(row["point_id"]),
                str(row["primitive_id"]),
                str(row["state"]),
                str(row["due_at"]),
                str(row["deadline_at"]),
                row.get("request_sha256"),
                json.dumps(dict(row.get("payload") or {}), sort_keys=True),
                now,
                now,
            ),
        )
        self._conn.commit()

    def claim_due(
        self,
        *,
        limit: int,
        now: datetime,
        owner: str,
    ) -> list[dict[str, Any]]:
        now_text = render_utc(now)
        rows = self._conn.execute(
            """
            SELECT * FROM due_observations
            WHERE state IN ('PENDING', 'DUE')
              AND due_at <= ?
            ORDER BY deadline_at ASC, due_at ASC, schedule_sha256 ASC, entity_id ASC, point_id ASC
            LIMIT ?
            """,
            (now_text, limit),
        ).fetchall()
        claimed: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            cursor = self._conn.execute(
                """
                UPDATE due_observations
                SET state = 'CLAIMED', updated_at = ?
                WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
                  AND point_id = ? AND primitive_id = ? AND state IN ('PENDING', 'DUE')
                """,
                (
                    now_text,
                    payload["schedule_sha256"],
                    payload["activation_id"],
                    payload["entity_id"],
                    payload["point_id"],
                    payload["primitive_id"],
                ),
            )
            if cursor.rowcount == 1:
                payload["state"] = "CLAIMED"
                payload["payload"] = json.loads(payload.pop("payload_json"))
                payload["claimed_by"] = owner
                claimed.append(payload)
        self._conn.commit()
        return claimed

    def due_in_states(
        self,
        states: Sequence[str],
        *,
        due_at_max: datetime | None = None,
    ) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in states)
        params: list[Any] = list(states)
        extra = ""
        if due_at_max is not None:
            extra = " AND due_at <= ?"
            params.append(render_utc(due_at_max))
        rows = self._conn.execute(
            f"""
            SELECT * FROM due_observations
            WHERE state IN ({placeholders}){extra}
            ORDER BY deadline_at ASC, due_at ASC, schedule_sha256 ASC, entity_id ASC, point_id ASC
            """,
            params,
        ).fetchall()
        decoded: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["payload"] = json.loads(payload.pop("payload_json"))
            decoded.append(payload)
        return decoded

    def merge_due_payload(
        self,
        row: Mapping[str, Any],
        extra: Mapping[str, Any],
        *,
        clock: datetime | None = None,
    ) -> None:
        now = _now(clock)
        current = self._conn.execute(
            """
            SELECT payload_json, state FROM due_observations
            WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
              AND point_id = ? AND primitive_id = ?
            """,
            (
                str(row["schedule_sha256"]),
                str(row["activation_id"]),
                str(row["entity_id"]),
                str(row["point_id"]),
                str(row["primitive_id"]),
            ),
        ).fetchone()
        if current is None:
            return
        if str(current["state"]) in _TERMINAL_DUE_STATES:
            return
        payload = json.loads(current["payload_json"])
        payload.update(dict(extra))
        self._conn.execute(
            """
            UPDATE due_observations
            SET payload_json = ?, updated_at = ?
            WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
              AND point_id = ? AND primitive_id = ?
            """,
            (
                json.dumps(payload, sort_keys=True),
                now,
                str(row["schedule_sha256"]),
                str(row["activation_id"]),
                str(row["entity_id"]),
                str(row["point_id"]),
                str(row["primitive_id"]),
            ),
        )
        self._conn.commit()

    def mark_recovery_gap(self, *, cutoff: datetime) -> int:
        rows = self.due_in_states(("PENDING", "DUE", "CLAIMED"), due_at_max=cutoff)
        for payload in rows:
            new_state = (
                "IN_FLIGHT_CALL_INDETERMINATE"
                if payload["state"] == "CLAIMED"
                else "CENSORED"
            )
            self.insert_due(
                {
                    "schedule_sha256": payload["schedule_sha256"],
                    "activation_id": payload["activation_id"],
                    "entity_id": payload["entity_id"],
                    "point_id": payload["point_id"],
                    "primitive_id": payload["primitive_id"],
                    "state": new_state,
                    "due_at": payload["due_at"],
                    "deadline_at": payload["deadline_at"],
                    "payload": {"missing_reason": "RECOVERY_GAP_INDETERMINATE"},
                },
                clock=cutoff,
            )
        return len(rows)

    def start_call(
        self,
        *,
        request_sha256: str,
        attempt_id: str,
        primitive_id: str,
        payload: Mapping[str, Any],
        clock: datetime | None = None,
    ) -> str:
        existing = self._conn.execute(
            """
            SELECT state FROM call_ledger
            WHERE request_sha256 = ?
            ORDER BY updated_at DESC, attempt_id DESC
            LIMIT 1
            """,
            (request_sha256,),
        ).fetchone()
        if existing is not None:
            state = str(existing["state"])
            if state == "COMPLETED":
                return "COMPLETED"
            return "IN_FLIGHT_CALL_INDETERMINATE"
        now = _now(clock)
        self._conn.execute(
            """
            INSERT INTO call_ledger(
                request_sha256, attempt_id, state, primitive_id, payload_json, created_at, updated_at
            ) VALUES (?, ?, 'STARTED', ?, ?, ?, ?)
            """,
            (
                request_sha256,
                attempt_id,
                primitive_id,
                json.dumps(dict(payload), sort_keys=True),
                now,
                now,
            ),
        )
        self._conn.commit()
        return "STARTED"

    def complete_call(
        self,
        *,
        request_sha256: str,
        attempt_id: str,
        payload: Mapping[str, Any],
        clock: datetime | None = None,
    ) -> None:
        now = _now(clock)
        self._conn.execute(
            """
            UPDATE call_ledger
            SET state = 'COMPLETED', payload_json = ?, updated_at = ?
            WHERE request_sha256 = ? AND attempt_id = ?
            """,
            (json.dumps(dict(payload), sort_keys=True), now, request_sha256, attempt_id),
        )
        self._conn.commit()

    def call_state(self, request_sha256: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT state FROM call_ledger
            WHERE request_sha256 = ?
            ORDER BY updated_at DESC, attempt_id DESC
            LIMIT 1
            """,
            (request_sha256,),
        ).fetchone()
        return str(row["state"]) if row is not None else None

    def call_payload(self, request_sha256: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT payload_json FROM call_ledger
            WHERE request_sha256 = ?
            ORDER BY updated_at DESC, attempt_id DESC
            LIMIT 1
            """,
            (request_sha256,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def record_batch(self, batch_content_sha256: str, payload: Mapping[str, Any], *, clock: datetime | None = None) -> None:
        try:
            self._conn.execute(
                """
                INSERT INTO publication_batches(batch_content_sha256, payload_json, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    batch_content_sha256,
                    json.dumps(dict(payload), sort_keys=True),
                    _now(clock),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            return

    def set_restore_marker(self, recovery_epoch: str, *, clock: datetime | None = None) -> None:
        now = _now(clock)
        self._conn.execute(
            """
            INSERT INTO restore_markers(marker_id, recovery_epoch, resolved, payload_json, created_at)
            VALUES ('UNRESOLVED', ?, 0, ?, ?)
            ON CONFLICT(marker_id) DO UPDATE SET recovery_epoch=excluded.recovery_epoch, resolved=0
            """,
            (recovery_epoch, json.dumps({"recovery_epoch": recovery_epoch}, sort_keys=True), now),
        )
        self._conn.commit()

    def restore_marker_unresolved(self) -> bool:
        row = self._conn.execute(
            "SELECT resolved FROM restore_markers WHERE marker_id = 'UNRESOLVED'"
        ).fetchone()
        return row is not None and int(row["resolved"]) == 0

    def resolve_restore_marker(self) -> None:
        self._conn.execute(
            "UPDATE restore_markers SET resolved = 1 WHERE marker_id = 'UNRESOLVED'"
        )
        self._conn.commit()

    def due_counts(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT state, COUNT(*) AS n FROM due_observations GROUP BY state"
        ).fetchall()
        return {str(row["state"]): int(row["n"]) for row in rows}

    def persist_registered_schedule(
        self,
        *,
        schedule_sha256: str,
        schedule_key: str,
        document: Mapping[str, Any],
        clock: datetime | None = None,
    ) -> str:
        now = _now(clock)
        payload = json.dumps(dict(document), sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        existing = self._conn.execute(
            "SELECT document_sha256 FROM registered_schedules WHERE schedule_sha256 = ?",
            (schedule_sha256,),
        ).fetchone()
        if existing is not None:
            if str(existing["document_sha256"]) != digest:
                raise ObservationScheduleStoreError("SCHEDULE_IDENTITY_CONFLICT")
            return "REGISTER_REPLAY"
        self._conn.execute(
            """
            INSERT INTO registered_schedules(
                schedule_sha256, schedule_key, document_json, document_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (schedule_sha256, schedule_key, payload, digest, now),
        )
        self._conn.commit()
        return "REGISTERED"

    def get_registered_schedule(self, schedule_sha256: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM registered_schedules WHERE schedule_sha256 = ?",
            (schedule_sha256,),
        ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["document"] = json.loads(payload.pop("document_json"))
        return payload

    def persist_authority(self, receipt: Mapping[str, Any], *, clock: datetime | None = None) -> str:
        now = _now(clock)
        digest = str(receipt["receipt_sha256"])
        existing = self._conn.execute(
            "SELECT payload_json FROM authority_receipts WHERE receipt_sha256 = ?",
            (digest,),
        ).fetchone()
        encoded = json.dumps(dict(receipt), sort_keys=True, ensure_ascii=False)
        if existing is not None:
            if str(existing["payload_json"]) != encoded:
                raise ObservationScheduleStoreError("AUTHORITY_IDENTITY_CONFLICT")
            return "AUTHORIZE_REPLAY"
        self._conn.execute(
            """
            INSERT INTO authority_receipts(
                receipt_sha256, authority_id, schedule_sha256, payload_json, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                digest,
                str(receipt["authority_id"]),
                str(receipt["schedule_sha256"]),
                encoded,
                str(receipt["expires_at"]),
                now,
            ),
        )
        self._conn.commit()
        return "AUTHORIZED"

    def get_authority(self, receipt_sha256: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload_json FROM authority_receipts WHERE receipt_sha256 = ?",
            (receipt_sha256,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def latest_authority_for_schedule(self, schedule_sha256: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT payload_json FROM authority_receipts
            WHERE schedule_sha256 = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (schedule_sha256,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def list_activations(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM schedule_activations ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def list_candidates(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM candidate_members
            WHERE schedule_sha256 = ? AND activation_id = ?
            ORDER BY entity_id ASC
            """,
            (schedule_sha256, activation_id),
        ).fetchall()
        decoded: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["payload"] = json.loads(payload.pop("payload_json"))
            decoded.append(payload)
        return decoded

    def load_accounting(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
        utc_day: str,
    ) -> dict[str, Any]:
        row = self._conn.execute(
            """
            SELECT * FROM accounting_counters
            WHERE schedule_sha256 = ? AND activation_id = ? AND utc_day = ?
            """,
            (schedule_sha256, activation_id, utc_day),
        ).fetchone()
        if row is None:
            return {
                "provider_calls": 0,
                "modeled_credits": 0,
                "candidates": 0,
                "members": 0,
                "raw_bytes": 0,
                "canonical_bytes": 0,
                "last_provider_call_at": None,
            }
        payload = dict(row)
        payload["payload"] = json.loads(payload.pop("payload_json"))
        return payload

    def save_accounting(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
        utc_day: str,
        values: Mapping[str, Any],
        clock: datetime | None = None,
    ) -> None:
        now = _now(clock)
        self._conn.execute(
            """
            INSERT INTO accounting_counters(
                schedule_sha256, activation_id, utc_day, provider_calls, modeled_credits,
                candidates, members, raw_bytes, canonical_bytes, last_provider_call_at,
                payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(schedule_sha256, activation_id, utc_day) DO UPDATE SET
                provider_calls=excluded.provider_calls,
                modeled_credits=excluded.modeled_credits,
                candidates=excluded.candidates,
                members=excluded.members,
                raw_bytes=excluded.raw_bytes,
                canonical_bytes=excluded.canonical_bytes,
                last_provider_call_at=excluded.last_provider_call_at,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                schedule_sha256,
                activation_id,
                utc_day,
                int(values.get("provider_calls") or 0),
                int(values.get("modeled_credits") or 0),
                int(values.get("candidates") or 0),
                int(values.get("members") or 0),
                int(values.get("raw_bytes") or 0),
                int(values.get("canonical_bytes") or 0),
                values.get("last_provider_call_at"),
                json.dumps(dict(values.get("payload") or {}), sort_keys=True),
                now,
            ),
        )
        self._conn.commit()

    def load_lifetime(self, *, schedule_sha256: str, activation_id: str) -> dict[str, int]:
        row = self._conn.execute(
            """
            SELECT provider_calls, canonical_bytes FROM lifetime_counters
            WHERE schedule_sha256 = ? AND activation_id = ?
            """,
            (schedule_sha256, activation_id),
        ).fetchone()
        if row is None:
            return {"provider_calls": 0, "canonical_bytes": 0}
        return {
            "provider_calls": int(row["provider_calls"]),
            "canonical_bytes": int(row["canonical_bytes"]),
        }

    def save_lifetime(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
        provider_calls: int,
        canonical_bytes: int,
        clock: datetime | None = None,
    ) -> None:
        now = _now(clock)
        self._conn.execute(
            """
            INSERT INTO lifetime_counters(
                schedule_sha256, activation_id, provider_calls, canonical_bytes, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(schedule_sha256, activation_id) DO UPDATE SET
                provider_calls=excluded.provider_calls,
                canonical_bytes=excluded.canonical_bytes,
                updated_at=excluded.updated_at
            """,
            (schedule_sha256, activation_id, provider_calls, canonical_bytes, now),
        )
        self._conn.commit()

    def load_poll_slot(self, poll_slot_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM poll_slots WHERE poll_slot_id = ?",
            (poll_slot_id,),
        ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["payload"] = json.loads(payload.pop("payload_json"))
        return payload

    def save_poll_slot(
        self,
        *,
        poll_slot_id: str,
        request_sha256: str,
        payload: Mapping[str, Any],
        clock: datetime | None = None,
    ) -> None:
        now = _now(clock)
        encoded = json.dumps(dict(payload), sort_keys=True)
        existing = self._conn.execute(
            "SELECT payload_json FROM poll_slots WHERE poll_slot_id = ?",
            (poll_slot_id,),
        ).fetchone()
        if existing is not None:
            if str(existing["payload_json"]) != encoded:
                raise ObservationScheduleStoreError("POLL_SLOT_CONFLICT")
            return
        self._conn.execute(
            """
            INSERT INTO poll_slots(poll_slot_id, request_sha256, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (poll_slot_id, request_sha256, encoded, now),
        )
        self._conn.commit()

    def load_publication_job(self, content_sha256: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM publication_jobs WHERE content_sha256 = ?",
            (content_sha256,),
        ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["payload"] = json.loads(payload.pop("payload_json"))
        return payload

    def save_publication_job(
        self,
        *,
        content_sha256: str,
        stage: str,
        payload: Mapping[str, Any],
        clock: datetime | None = None,
    ) -> None:
        now = _now(clock)
        self._conn.execute(
            """
            INSERT INTO publication_jobs(content_sha256, stage, payload_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(content_sha256) DO UPDATE SET
                stage=excluded.stage,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (content_sha256, stage, json.dumps(dict(payload), sort_keys=True), now),
        )
        self._conn.commit()

    def backup_to(self, dest: Path) -> None:
        if dest.is_absolute() is False:
            raise ObservationScheduleStoreError("OPS_STORE_PATH_NOT_ABSOLUTE")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        replica = sqlite3.connect(dest)
        try:
            self._conn.backup(replica)
            replica.commit()
        finally:
            replica.close()

    def restore_from(self, src: Path, *, recovery_epoch: str) -> None:
        if src.is_absolute() is False:
            raise ObservationScheduleStoreError("OPS_STORE_PATH_NOT_ABSOLUTE")
        if src.is_file() is False:
            raise ObservationScheduleStoreError("ROLLBACK_SNAPSHOT_MISSING")
        self._conn.close()
        import shutil

        shutil.copy2(src, self.path)
        for suffix in ("-wal", "-shm"):
            extra = Path(str(self.path) + suffix)
            if extra.exists():
                extra.unlink()
        self._connect()
        self.set_restore_marker(recovery_epoch)
        self.mark_recovery_gap(cutoff=datetime.now(UTC))
