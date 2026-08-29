"""Dedicated SQLite due-work store for ObservationSchedule. Not scientific truth."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from solana_alpha_lab.factory.observation_schedule import (
    canonical_json_bytes,
    collection_projection,
    parse_utc,
    render_utc,
)

LEASE_SECONDS = 120
GLOBAL_LEASE_ID = "observation-scheduler"
_TERMINAL_DUE_STATES = frozenset(
    {
        "OBSERVED",
        "MISSING_TYPED",
        "DISAPPEARED",
        "CENSORED",
        "CENSORED_LATE",
        "X_POPULATION_INELIGIBLE",
        "IN_FLIGHT_CALL_INDETERMINATE",
        "DEPENDENCY_MISSING",
        "BLOCKED_BUDGET",
    }
)
_ALLOWED_ACTIVATION_TRANSITIONS = {
    "UNREGISTERED": frozenset({"ACTIVE"}),
    "ACTIVE": frozenset({"PAUSED_OPERATOR", "DRAINING", "ABORTED_SAFETY"}),
    "PAUSED_OPERATOR": frozenset({"ACTIVE", "ABORTED_SAFETY"}),
    "DRAINING": frozenset({"COMPLETE", "ABORTED_SAFETY"}),
    "ABORTED_SAFETY": frozenset(),
    "BLOCKED_AUTHORITY": frozenset(),
    "BLOCKED_BUDGET": frozenset(),
    "COMPLETE": frozenset(),
}


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
        self._lease_token: str | None = None
        try:
            self._connect()
        except Exception:
            connection = getattr(self, "_conn", None)
            if connection is not None:
                connection.close()
            raise

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
                transition_sequence INTEGER NOT NULL DEFAULT 0,
                last_transition_event_id TEXT,
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
                call_occurrence_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (
                    schedule_sha256, activation_id, entity_id, point_id, primitive_id
                )
            );
            CREATE TABLE IF NOT EXISTS call_ledger (
                request_sha256 TEXT NOT NULL,
                call_occurrence_id TEXT NOT NULL PRIMARY KEY
                    CHECK (length(call_occurrence_id) > 0),
                attempt_id TEXT NOT NULL,
                state TEXT NOT NULL,
                primitive_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_call_ledger_request_sha256
                ON call_ledger(request_sha256);
            CREATE TABLE IF NOT EXISTS scheduler_leases (
                lease_id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                lease_token TEXT NOT NULL DEFAULT '',
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
            CREATE TABLE IF NOT EXISTS schedule_aliases (
                schedule_sha256 TEXT NOT NULL,
                schedule_key TEXT NOT NULL,
                alias_binding_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (schedule_sha256, schedule_key)
            );
            CREATE TABLE IF NOT EXISTS schedule_rollovers (
                rollover_id TEXT PRIMARY KEY,
                predecessor_schedule_sha256 TEXT NOT NULL,
                predecessor_activation_id TEXT NOT NULL,
                successor_schedule_sha256 TEXT NOT NULL,
                successor_activation_id TEXT NOT NULL,
                cutover_at TEXT NOT NULL,
                authority_receipt_sha256 TEXT NOT NULL,
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
        self._ensure_column(
            "schedule_activations",
            "transition_sequence",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column("schedule_activations", "last_transition_event_id", "TEXT")
        self._ensure_column("due_observations", "call_occurrence_id", "TEXT")
        self._ensure_column("call_ledger", "call_occurrence_id", "TEXT")
        self._ensure_column("scheduler_leases", "lease_token", "TEXT NOT NULL DEFAULT ''")
        self._migrate_call_ledger_to_occurrence_primary_key()
        registered_rows = self._conn.execute(
            "SELECT schedule_sha256, schedule_key, created_at FROM registered_schedules"
        ).fetchall()
        for row in registered_rows:
            schedule_digest = str(row["schedule_sha256"])
            schedule_key = str(row["schedule_key"])
            alias_digest = hashlib.sha256(
                canonical_json_bytes(
                    {
                        "schedule_key": schedule_key,
                        "schedule_sha256": schedule_digest,
                    }
                )
            ).hexdigest()
            self._conn.execute(
                """
                INSERT OR IGNORE INTO schedule_aliases(
                    schedule_sha256, schedule_key, alias_binding_sha256, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (schedule_digest, schedule_key, alias_digest, str(row["created_at"])),
            )
        self._conn.commit()

    def _migrate_call_ledger_to_occurrence_primary_key(self) -> None:
        """Migrate pre-occurrence ledgers without retaining request-global identity."""
        columns = self._conn.execute("PRAGMA table_info(call_ledger)").fetchall()
        occurrence_pk = next(
            (
                row
                for row in columns
                if str(row["name"]) == "call_occurrence_id"
                and int(row["pk"]) == 1
            ),
            None,
        )
        if occurrence_pk is not None:
            return

        rows = self._conn.execute(
            """
            SELECT request_sha256, COALESCE(call_occurrence_id, '') AS call_occurrence_id,
                   attempt_id, state, primitive_id, payload_json, created_at, updated_at
            FROM call_ledger
            ORDER BY request_sha256 ASC, attempt_id ASC
            """
        ).fetchall()
        normalized: list[tuple[str, sqlite3.Row]] = []
        seen: set[str] = set()
        for row in rows:
            occurrence = str(row["call_occurrence_id"] or "")
            if not occurrence:
                raise ObservationScheduleStoreError(
                    "CALL_LEDGER_MIGRATION_OCCURRENCE_REQUIRED"
                )
            if occurrence in seen:
                raise ObservationScheduleStoreError(
                    "CALL_LEDGER_MIGRATION_AMBIGUOUS"
                )
            seen.add(occurrence)
            normalized.append((occurrence, row))

        try:
            self._conn.commit()
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute("ALTER TABLE call_ledger RENAME TO call_ledger_legacy")
            self._conn.execute(
                "DROP INDEX IF EXISTS idx_call_ledger_request_sha256"
            )
            self._conn.execute(
                """
                CREATE TABLE call_ledger (
                    request_sha256 TEXT NOT NULL,
                    call_occurrence_id TEXT NOT NULL PRIMARY KEY
                        CHECK (length(call_occurrence_id) > 0),
                    attempt_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    primitive_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX idx_call_ledger_request_sha256
                    ON call_ledger(request_sha256)
                """
            )
            for occurrence, row in normalized:
                self._conn.execute(
                    """
                    INSERT INTO call_ledger(
                        request_sha256, call_occurrence_id, attempt_id, state,
                        primitive_id, payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(row["request_sha256"]),
                        occurrence,
                        str(row["attempt_id"]),
                        str(row["state"]),
                        str(row["primitive_id"]),
                        str(row["payload_json"]),
                        str(row["created_at"]),
                        str(row["updated_at"]),
                    ),
                )
            self._conn.execute("DROP TABLE call_ledger_legacy")
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            str(row["name"])
            for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def close(self) -> None:
        self._conn.close()

    def _require_write_lease(self, clock: datetime | None = None) -> None:
        """Fence mutations after another process replaces or expires our lease.

        While this process holds the token, every write renews expires_at so a
        long tick cannot lose the fence mid-mutation against the 60s timer.
        """
        now_text = _now(clock)
        if self._lease_token is None:
            active = self._conn.execute(
                """
                SELECT expires_at
                FROM scheduler_leases
                WHERE lease_id = ?
                """,
                (GLOBAL_LEASE_ID,),
            ).fetchone()
            if active is not None and str(active["expires_at"]) > now_text:
                raise ObservationScheduleStoreError("WRITER_BUSY")
            return
        row = self._conn.execute(
            """
            SELECT lease_token, expires_at
            FROM scheduler_leases
            WHERE lease_id = ?
            """,
            (GLOBAL_LEASE_ID,),
        ).fetchone()
        if (
            row is None
            or str(row["lease_token"]) != self._lease_token
            or str(row["expires_at"]) <= now_text
        ):
            raise ObservationScheduleStoreError("LEASE_FENCED")
        expires = render_utc(
            parse_utc(now_text) + timedelta(seconds=LEASE_SECONDS)
        )
        self._conn.execute(
            """
            UPDATE scheduler_leases
            SET expires_at = ?
            WHERE lease_id = ? AND lease_token = ?
            """,
            (expires, GLOBAL_LEASE_ID, self._lease_token),
        )
        self._conn.commit()

    def record_event(self, kind: str, payload: Mapping[str, Any], *, clock: datetime | None = None) -> None:
        self._require_write_lease(clock)
        self._conn.execute(
            "INSERT INTO runtime_events(kind, created_at, payload_json) VALUES (?, ?, ?)",
            (kind, _now(clock), json.dumps(dict(payload), sort_keys=True)),
        )
        self._conn.commit()

    def acquire_lease(self, owner: str, *, clock: datetime | None = None) -> str | None:
        now = clock.astimezone(UTC) if clock is not None else datetime.now(UTC)
        now_text = render_utc(now)
        expires = render_utc(now + timedelta(seconds=LEASE_SECONDS))
        lease_token = f"{owner}-{uuid4().hex}"
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT expires_at FROM scheduler_leases WHERE lease_id = ?",
                (GLOBAL_LEASE_ID,),
            ).fetchone()
            if row is not None and str(row["expires_at"]) > now_text:
                self._conn.rollback()
                return None
            self._conn.execute(
                """
                INSERT INTO scheduler_leases(
                    lease_id, owner, lease_token, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(lease_id) DO UPDATE SET
                    owner=excluded.owner,
                    lease_token=excluded.lease_token,
                    expires_at=excluded.expires_at,
                    created_at=excluded.created_at
                """,
                (GLOBAL_LEASE_ID, owner, lease_token, expires, now_text),
            )
            self._conn.commit()
            self._lease_token = lease_token
            return lease_token
        except sqlite3.OperationalError:
            self._conn.rollback()
            return None

    def release_lease(self, lease_token: str) -> None:
        cursor = self._conn.execute(
            "DELETE FROM scheduler_leases WHERE lease_id = ? AND lease_token = ?",
            (GLOBAL_LEASE_ID, lease_token),
        )
        self._conn.commit()
        if cursor.rowcount == 1 and lease_token == self._lease_token:
            self._lease_token = None

    def upsert_activation(self, row: Mapping[str, Any], *, clock: datetime | None = None) -> None:
        self._require_write_lease(clock)
        now = _now(clock)
        payload = dict(row.get("payload") or {})
        if not payload and row.get("payload_json"):
            payload = json.loads(str(row["payload_json"]))
        self._conn.execute(
            """
            INSERT INTO schedule_activations(
                schedule_sha256, activation_id, schedule_key, state,
                authority_receipt_sha256, starts_at, stops_admitting_at,
                payload_json, created_at, updated_at,
                transition_sequence, last_transition_event_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(schedule_sha256, activation_id) DO UPDATE SET
                state=excluded.state,
                authority_receipt_sha256=excluded.authority_receipt_sha256,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at,
                transition_sequence=MAX(
                    schedule_activations.transition_sequence,
                    excluded.transition_sequence
                ),
                last_transition_event_id=COALESCE(
                    excluded.last_transition_event_id,
                    schedule_activations.last_transition_event_id
                )
            """,
            (
                str(row["schedule_sha256"]),
                str(row["activation_id"]),
                str(row["schedule_key"]),
                str(row["state"]),
                row.get("authority_receipt_sha256"),
                str(row["starts_at"]),
                str(row["stops_admitting_at"]),
                json.dumps(payload, sort_keys=True),
                now,
                now,
                int(row.get("transition_sequence") or 0),
                row.get("last_transition_event_id"),
            ),
        )
        self._conn.commit()

    def transition_activation(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
        new_state: str,
        authority_receipt_sha256: str | None = None,
        effective_at: str | None = None,
        starts_at: str | None = None,
        stops_admitting_at: str | None = None,
        schedule_key: str | None = None,
        payload: Mapping[str, Any] | None = None,
        clock: datetime | None = None,
    ) -> dict[str, Any]:
        """Apply one append-only lifecycle transition under a SQLite lock."""
        self._require_write_lease(clock)
        if new_state not in _ALLOWED_ACTIVATION_TRANSITIONS or new_state == "UNREGISTERED":
            raise ObservationScheduleStoreError("INVALID_STATE_TRANSITION")
        now = _now(clock)
        effective = effective_at or now
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                """
                SELECT * FROM schedule_activations
                WHERE schedule_sha256 = ? AND activation_id = ?
                """,
                (schedule_sha256, activation_id),
            ).fetchone()
            if row is None:
                if not starts_at or not stops_admitting_at or not schedule_key:
                    self._conn.rollback()
                    raise ObservationScheduleStoreError("ACTIVATION_BINDING_MISSING")
                prior_state = "UNREGISTERED"
                sequence = 1
                previous_payload: dict[str, Any] = {}
                actual_schedule_key = schedule_key
                actual_starts_at = starts_at
                actual_stops_at = stops_admitting_at
            else:
                prior_state = str(row["state"])
                if prior_state == new_state:
                    result = dict(row)
                    result["payload"] = json.loads(str(row["payload_json"]))
                    original_prior_state = str(
                        result["payload"].get("prior_state") or prior_state
                    )
                    result.update(
                        {
                            "prior_state": original_prior_state,
                            "state": new_state,
                            "transition_sequence": int(
                                result["payload"].get(
                                    "transition_sequence",
                                    row["transition_sequence"],
                                )
                            ),
                            "event_id": row["last_transition_event_id"],
                            "replayed": True,
                        }
                    )
                    self._conn.rollback()
                    return result
                if new_state not in _ALLOWED_ACTIVATION_TRANSITIONS.get(
                    prior_state, frozenset()
                ):
                    self._conn.rollback()
                    raise ObservationScheduleStoreError("INVALID_STATE_TRANSITION")
                sequence = int(row["transition_sequence"]) + 1
                previous_payload = json.loads(str(row["payload_json"]))
                actual_schedule_key = str(row["schedule_key"])
                actual_starts_at = str(row["starts_at"])
                actual_stops_at = str(row["stops_admitting_at"])
                if authority_receipt_sha256 is None:
                    authority_receipt_sha256 = row["authority_receipt_sha256"]
            transition_identity = {
                "schedule_sha256": schedule_sha256,
                "activation_id": activation_id,
                "prior_state": prior_state,
                "new_state": new_state,
                "transition_sequence": sequence,
                "effective_at": effective,
                "authority_receipt_sha256": authority_receipt_sha256 or "",
            }
            event_id = "OBS-TRANS-" + hashlib.sha256(
                canonical_json_bytes(transition_identity)
            ).hexdigest()
            transition_payload = dict(previous_payload)
            transition_payload.update(dict(payload or {}))
            transition_payload.update(
                {
                    "prior_state": prior_state,
                    "new_state": new_state,
                    "transition_sequence": sequence,
                    "transition_effective_at": effective,
                    "transition_event_id": event_id,
                    "authority_receipt_sha256": authority_receipt_sha256,
                }
            )
            if row is None:
                self._conn.execute(
                    """
                    INSERT INTO schedule_activations(
                        schedule_sha256, activation_id, schedule_key, state,
                        authority_receipt_sha256, starts_at, stops_admitting_at,
                        payload_json, created_at, updated_at,
                        transition_sequence, last_transition_event_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        schedule_sha256,
                        activation_id,
                        actual_schedule_key,
                        new_state,
                        authority_receipt_sha256,
                        actual_starts_at,
                        actual_stops_at,
                        json.dumps(transition_payload, sort_keys=True),
                        now,
                        now,
                        sequence,
                        event_id,
                    ),
                )
            else:
                self._conn.execute(
                    """
                    UPDATE schedule_activations
                    SET state = ?, authority_receipt_sha256 = ?,
                        payload_json = ?, updated_at = ?,
                        transition_sequence = ?, last_transition_event_id = ?
                    WHERE schedule_sha256 = ? AND activation_id = ?
                    """,
                    (
                        new_state,
                        authority_receipt_sha256,
                        json.dumps(transition_payload, sort_keys=True),
                        now,
                        sequence,
                        event_id,
                        schedule_sha256,
                        activation_id,
                    ),
                )
            self._conn.commit()
            return {
                "schedule_sha256": schedule_sha256,
                "activation_id": activation_id,
                "schedule_key": actual_schedule_key,
                "prior_state": prior_state,
                "state": new_state,
                "authority_receipt_sha256": authority_receipt_sha256,
                "starts_at": actual_starts_at,
                "stops_admitting_at": actual_stops_at,
                "transition_sequence": sequence,
                "event_id": event_id,
                "payload": transition_payload,
                "replayed": False,
            }
        except Exception:
            self._conn.rollback()
            raise

    def persist_rollover(
        self,
        *,
        predecessor_schedule_sha256: str,
        predecessor_activation_id: str,
        successor_schedule_sha256: str,
        successor_activation_id: str,
        cutover_at: str,
        authority_receipt_sha256: str,
        clock: datetime | None = None,
    ) -> str:
        self._require_write_lease(clock)
        identity = {
            "predecessor_schedule_sha256": predecessor_schedule_sha256,
            "predecessor_activation_id": predecessor_activation_id,
            "successor_schedule_sha256": successor_schedule_sha256,
            "successor_activation_id": successor_activation_id,
            "cutover_at": cutover_at,
            "authority_receipt_sha256": authority_receipt_sha256,
        }
        rollover_id = "OBS-ROLLOVER-" + hashlib.sha256(
            canonical_json_bytes(identity)
        ).hexdigest()
        self._conn.execute(
            """
            INSERT OR IGNORE INTO schedule_rollovers(
                rollover_id, predecessor_schedule_sha256, predecessor_activation_id,
                successor_schedule_sha256, successor_activation_id, cutover_at,
                authority_receipt_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rollover_id,
                predecessor_schedule_sha256,
                predecessor_activation_id,
                successor_schedule_sha256,
                successor_activation_id,
                cutover_at,
                authority_receipt_sha256,
                _now(clock),
            ),
        )
        self._conn.commit()
        return rollover_id

    def list_rollovers(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM schedule_rollovers ORDER BY cutover_at ASC, rollover_id ASC"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_activation(self, schedule_sha256: str, activation_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM schedule_activations WHERE schedule_sha256 = ? AND activation_id = ?",
            (schedule_sha256, activation_id),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(str(result["payload_json"]))
        return result

    def insert_candidate(self, row: Mapping[str, Any], *, clock: datetime | None = None) -> bool:
        self._require_write_lease(clock)
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
        self._require_write_lease(clock)
        now = _now(clock)
        existing = self._conn.execute(
            """
            SELECT payload_json FROM candidate_members
            WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
            """,
            (
                str(row["schedule_sha256"]),
                str(row["activation_id"]),
                str(row["entity_id"]),
            ),
        ).fetchone()
        if existing is None:
            raise ObservationScheduleStoreError("CANDIDATE_MISSING")
        payload = json.loads(str(existing["payload_json"]))
        payload.update(dict(row.get("payload") or {}))
        cursor = self._conn.execute(
            """
            UPDATE candidate_members
            SET state = ?, payload_json = ?, updated_at = ?
            WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
            """,
            (
                str(row["state"]),
                json.dumps(payload, sort_keys=True),
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
        self._require_write_lease(clock)
        now = _now(clock)
        existing = self._conn.execute(
            """
            SELECT state, due_at, deadline_at, request_sha256,
                   call_occurrence_id, payload_json
            FROM due_observations
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
            if str(row["state"]) != str(existing["state"]):
                raise ObservationScheduleStoreError("DENY_RETROACTIVE_MUTATION")
            for key in ("due_at", "deadline_at", "request_sha256", "call_occurrence_id"):
                requested = row.get(key)
                if requested is not None and str(requested) != str(existing[key]):
                    raise ObservationScheduleStoreError("DENY_RETROACTIVE_MUTATION")
            requested_payload = row.get("payload")
            if requested_payload:
                current_payload = json.loads(str(existing["payload_json"]))
                if dict(requested_payload) != current_payload:
                    raise ObservationScheduleStoreError("DENY_RETROACTIVE_MUTATION")
            return
        self._conn.execute(
            """
            INSERT INTO due_observations(
                schedule_sha256, activation_id, entity_id, point_id, primitive_id,
                state, due_at, deadline_at, request_sha256, payload_json, created_at, updated_at
                , call_occurrence_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(schedule_sha256, activation_id, entity_id, point_id, primitive_id)
            DO UPDATE SET
                state=excluded.state,
                request_sha256=COALESCE(excluded.request_sha256, due_observations.request_sha256),
                call_occurrence_id=COALESCE(
                    excluded.call_occurrence_id,
                    due_observations.call_occurrence_id
                ),
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
                row.get("call_occurrence_id"),
            ),
        )
        self._conn.commit()

    def claim_due(
        self,
        *,
        limit: int,
        now: datetime,
        owner: str,
        schedule_sha256: str | None = None,
        activation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self._require_write_lease(now)
        now_text = render_utc(now)
        predicates = ["state IN ('PENDING', 'DUE')", "due_at <= ?"]
        parameters: list[Any] = [now_text]
        if schedule_sha256 is not None:
            predicates.append("schedule_sha256 = ?")
            parameters.append(schedule_sha256)
        if activation_id is not None:
            predicates.append("activation_id = ?")
            parameters.append(activation_id)
        parameters.append(limit)
        rows = self._conn.execute(
            f"""
            SELECT * FROM due_observations
            WHERE {" AND ".join(predicates)}
            ORDER BY deadline_at ASC, due_at ASC, schedule_sha256 ASC, entity_id ASC, point_id ASC
            LIMIT ?
            """,
            parameters,
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
        self._require_write_lease(clock)
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

    def has_prior_observation(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
        entity_id: str,
    ) -> bool:
        row = self._conn.execute(
            """
            SELECT 1 FROM due_observations
            WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
              AND state = 'OBSERVED'
            LIMIT 1
            """,
            (schedule_sha256, activation_id, entity_id),
        ).fetchone()
        return row is not None

    def censor_remaining_points(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
        entity_id: str,
        reason: str,
        exclude_point_id: str | None = None,
        exclude_primitive_id: str | None = None,
        clock: datetime | None = None,
    ) -> list[dict[str, Any]]:
        self._require_write_lease(clock)
        now = _now(clock)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            exclusion = ""
            query_params: list[Any] = [schedule_sha256, activation_id, entity_id]
            if exclude_point_id is not None and exclude_primitive_id is not None:
                exclusion += " AND NOT (point_id = ? AND primitive_id = ?)"
                query_params.extend([exclude_point_id, exclude_primitive_id])
            elif exclude_point_id is not None:
                exclusion += " AND point_id <> ?"
                query_params.append(exclude_point_id)
            if exclude_primitive_id is not None:
                if exclude_point_id is None:
                    exclusion += " AND primitive_id <> ?"
                    query_params.append(exclude_primitive_id)
            rows = self._conn.execute(
                f"""
                SELECT * FROM due_observations
                WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
                  {exclusion}
                  AND state NOT IN (
                      'OBSERVED', 'MISSING_TYPED', 'DISAPPEARED', 'CENSORED',
                      'CENSORED_LATE', 'X_POPULATION_INELIGIBLE',
                      'IN_FLIGHT_CALL_INDETERMINATE', 'DEPENDENCY_MISSING',
                      'BLOCKED_BUDGET'
                  )
                ORDER BY due_at ASC, point_id ASC, primitive_id ASC
                """,
                query_params,
            ).fetchall()
            censored: list[dict[str, Any]] = []
            for row in rows:
                payload = json.loads(str(row["payload_json"]))
                payload.update(
                    {
                        "missing_reason": reason,
                        "terminal_reason": reason,
                    }
                )
                update_exclusion = ""
                update_params: list[Any] = [
                    json.dumps(payload, sort_keys=True),
                    now,
                    row["schedule_sha256"],
                    row["activation_id"],
                    row["entity_id"],
                    row["point_id"],
                    row["primitive_id"],
                ]
                if exclude_point_id is not None and exclude_primitive_id is not None:
                    update_exclusion = " AND NOT (point_id = ? AND primitive_id = ?)"
                    update_params.extend([exclude_point_id, exclude_primitive_id])
                elif exclude_point_id is not None:
                    update_exclusion = " AND point_id <> ?"
                    update_params.append(exclude_point_id)
                if exclude_primitive_id is not None and exclude_point_id is None:
                    update_exclusion += " AND primitive_id <> ?"
                    update_params.append(exclude_primitive_id)
                self._conn.execute(
                    f"""
                    UPDATE due_observations
                    SET state = 'CENSORED', payload_json = ?, updated_at = ?
                    WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
                      AND point_id = ? AND primitive_id = ?
                      {update_exclusion}
                      AND state NOT IN (
                          'OBSERVED', 'MISSING_TYPED', 'DISAPPEARED', 'CENSORED',
                          'CENSORED_LATE', 'X_POPULATION_INELIGIBLE',
                          'IN_FLIGHT_CALL_INDETERMINATE', 'DEPENDENCY_MISSING',
                          'BLOCKED_BUDGET'
                      )
                    """,
                    update_params,
                )
                item = dict(row)
                item["state"] = "CENSORED"
                item["payload"] = payload
                censored.append(item)
            self._conn.commit()
            return censored
        except Exception:
            self._conn.rollback()
            raise

    def reanchor_candidate(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
        entity_id: str,
        authoritative_anchor: str,
        due_times: Mapping[str, tuple[str, str]],
        exclude_point_id: str | None = None,
        exclude_primitive_id: str | None = None,
        clock: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Atomically replace provisional timing for nonterminal points."""
        self._require_write_lease(clock)
        now = _now(clock)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            candidate = self._conn.execute(
                """
                SELECT payload_json FROM candidate_members
                WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
                """,
                (schedule_sha256, activation_id, entity_id),
            ).fetchone()
            if candidate is None:
                self._conn.rollback()
                raise ObservationScheduleStoreError("CANDIDATE_MISSING")
            candidate_payload = json.loads(str(candidate["payload_json"]))
            candidate_payload.update(
                {
                    "authoritative_anchor": authoritative_anchor,
                    "provisional_schedule_anchor": None,
                    "provisional": False,
                    "provisional_due": False,
                    "provisional_due_at": None,
                }
            )
            self._conn.execute(
                """
                UPDATE candidate_members
                SET payload_json = ?, updated_at = ?
                WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
                """,
                (
                    json.dumps(candidate_payload, sort_keys=True),
                    now,
                    schedule_sha256,
                    activation_id,
                    entity_id,
                ),
            )
            rows = self._conn.execute(
                """
                SELECT * FROM due_observations
                WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
                ORDER BY due_at ASC, point_id ASC, primitive_id ASC
                """,
                (schedule_sha256, activation_id, entity_id),
            ).fetchall()
            censored: list[dict[str, Any]] = []
            for row in rows:
                if (
                    exclude_point_id is not None
                    and exclude_primitive_id is not None
                    and str(row["point_id"]) == exclude_point_id
                    and str(row["primitive_id"]) == exclude_primitive_id
                ) or (
                    exclude_point_id is not None
                    and exclude_primitive_id is None
                    and str(row["point_id"]) == exclude_point_id
                ) or (
                    exclude_primitive_id is not None
                    and exclude_point_id is None
                    and str(row["primitive_id"]) == exclude_primitive_id
                ):
                    continue
                point_id = str(row["point_id"])
                if point_id not in due_times:
                    raise ObservationScheduleStoreError("REANCHOR_POINT_MISSING")
                current_state = str(row["state"])
                current_payload = json.loads(str(row["payload_json"]))
                if current_state in _TERMINAL_DUE_STATES:
                    if not current_payload.get("provisional_due"):
                        continue
                    new_due, new_deadline = due_times[point_id]
                    observed_raw = (
                        current_payload.get("first_reliable_available_at")
                        or current_payload.get("response_received_at")
                    )
                    try:
                        observed_at = (
                            parse_utc(str(observed_raw))
                            if observed_raw
                            else None
                        )
                    except Exception:
                        observed_at = None
                    if (
                        observed_at is not None
                        and parse_utc(new_due)
                        <= observed_at
                        <= parse_utc(new_deadline)
                    ):
                        continue
                    current_payload.update(
                        {
                            "missing_reason": "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                            "terminal_reason": "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                            "scientific_valid": False,
                            "provisional_due": True,
                        }
                    )
                    self._conn.execute(
                        """
                        UPDATE due_observations
                        SET state = 'CENSORED_LATE', payload_json = ?, updated_at = ?
                        WHERE schedule_sha256 = ? AND activation_id = ?
                          AND entity_id = ? AND point_id = ? AND primitive_id = ?
                          AND state IN (
                              'OBSERVED', 'MISSING_TYPED', 'DISAPPEARED',
                              'CENSORED', 'IN_FLIGHT_CALL_INDETERMINATE',
                              'DEPENDENCY_MISSING', 'BLOCKED_BUDGET'
                          )
                        """,
                        (
                            json.dumps(current_payload, sort_keys=True),
                            now,
                            schedule_sha256,
                            activation_id,
                            entity_id,
                            row["point_id"],
                            row["primitive_id"],
                        ),
                    )
                    item = dict(row)
                    item.update(
                        {
                            "state": "CENSORED_LATE",
                            "payload": current_payload,
                            "due_at": str(row["due_at"]),
                            "deadline_at": str(row["deadline_at"]),
                        }
                    )
                    censored.append(item)
                    continue
                due_at, deadline_at = due_times[point_id]
                payload = json.loads(str(row["payload_json"]))
                payload.update(
                    {
                        "authoritative_anchor": authoritative_anchor,
                        "provisional_schedule_anchor": None,
                        "provisional": False,
                    "provisional_due": False,
                    }
                )
                new_state = "PENDING"
                if parse_utc(str(deadline_at)) <= parse_utc(now):
                    new_state = "CENSORED_LATE"
                    payload.update(
                        {
                            "missing_reason": "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                            "terminal_reason": "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                        }
                    )
                self._conn.execute(
                    """
                    UPDATE due_observations
                    SET state = ?, due_at = ?, deadline_at = ?, payload_json = ?, updated_at = ?
                    WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
                      AND point_id = ? AND primitive_id = ?
                    """,
                    (
                        new_state,
                        due_at,
                        deadline_at,
                        json.dumps(payload, sort_keys=True),
                        now,
                        schedule_sha256,
                        activation_id,
                        entity_id,
                        row["point_id"],
                        row["primitive_id"],
                    ),
                )
                if new_state == "CENSORED_LATE":
                    item = dict(row)
                    item.update(
                        {
                            "state": new_state,
                            "due_at": due_at,
                            "deadline_at": deadline_at,
                            "payload": payload,
                        }
                    )
                    censored.append(item)
            self._conn.commit()
            return censored
        except Exception:
            self._conn.rollback()
            raise

    def mark_recovery_gap(self, *, cutoff: datetime) -> int:
        self._require_write_lease(cutoff)
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

    def mark_point_censored_late(
        self,
        row: Mapping[str, Any],
        *,
        reason: str,
        clock: datetime | None = None,
    ) -> dict[str, Any]:
        self._require_write_lease(clock)
        now = _now(clock)
        keys = (
            str(row["schedule_sha256"]),
            str(row["activation_id"]),
            str(row["entity_id"]),
            str(row["point_id"]),
            str(row["primitive_id"]),
        )
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            current = self._conn.execute(
                """
                SELECT * FROM due_observations
                WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
                  AND point_id = ? AND primitive_id = ?
                """,
                keys,
            ).fetchone()
            if current is None:
                self._conn.rollback()
                raise ObservationScheduleStoreError("DUE_OBSERVATION_MISSING")
            payload = json.loads(str(current["payload_json"]))
            payload.update(
                {
                    "missing_reason": reason,
                    "terminal_reason": reason,
                    "scientific_valid": False,
                }
            )
            changed = str(current["state"]) in {"OBSERVED", "CLAIMED", "PENDING", "DUE"}
            if changed:
                self._conn.execute(
                    """
                    UPDATE due_observations
                    SET state = 'CENSORED_LATE',
                        request_sha256 = COALESCE(?, request_sha256),
                        call_occurrence_id = COALESCE(?, call_occurrence_id),
                        payload_json = ?, updated_at = ?
                    WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
                      AND point_id = ? AND primitive_id = ?
                      AND state IN ('OBSERVED', 'CLAIMED', 'PENDING', 'DUE')
                    """,
                    (
                        row.get("request_sha256"),
                        row.get("call_occurrence_id"),
                        json.dumps(payload, sort_keys=True),
                        now,
                        *keys,
                    ),
                )
            self._conn.commit()
            result = dict(current)
            result["state"] = "CENSORED_LATE" if changed else str(current["state"])
            result["payload"] = payload
            return result
        except Exception:
            self._conn.rollback()
            raise

    def start_call(
        self,
        *,
        request_sha256: str,
        attempt_id: str,
        call_occurrence_id: str | None = None,
        primitive_id: str,
        payload: Mapping[str, Any],
        clock: datetime | None = None,
    ) -> str:
        if not isinstance(call_occurrence_id, str) or not call_occurrence_id.strip():
            raise ObservationScheduleStoreError("CALL_OCCURRENCE_REQUIRED")
        self._require_write_lease(clock)
        occurrence_id = call_occurrence_id
        now = _now(clock)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            existing = self._conn.execute(
                """
                SELECT request_sha256, primitive_id, state FROM call_ledger
                WHERE call_occurrence_id = ?
                LIMIT 1
                """,
                (occurrence_id,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["request_sha256"]) != request_sha256
                    or str(existing["primitive_id"]) != primitive_id
                ):
                    self._conn.rollback()
                    raise ObservationScheduleStoreError(
                        "CALL_OCCURRENCE_IDENTITY_CONFLICT"
                    )
                state = str(existing["state"])
                self._conn.rollback()
                if state == "COMPLETED":
                    return "COMPLETED"
                return "IN_FLIGHT_CALL_INDETERMINATE"
            self._conn.execute(
                """
                INSERT INTO call_ledger(
                    request_sha256, call_occurrence_id, attempt_id, state,
                    primitive_id, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, 'STARTED', ?, ?, ?, ?)
                """,
                (
                    request_sha256,
                    occurrence_id,
                    attempt_id,
                    primitive_id,
                    json.dumps(dict(payload), sort_keys=True),
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return "STARTED"
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            self._conn.rollback()
            return "IN_FLIGHT_CALL_INDETERMINATE"

    def complete_call(
        self,
        *,
        request_sha256: str,
        attempt_id: str,
        call_occurrence_id: str | None = None,
        payload: Mapping[str, Any],
        clock: datetime | None = None,
    ) -> None:
        if not isinstance(call_occurrence_id, str) or not call_occurrence_id.strip():
            raise ObservationScheduleStoreError("CALL_OCCURRENCE_REQUIRED")
        self._require_write_lease(clock)
        now = _now(clock)
        occurrence_id = call_occurrence_id
        encoded = json.dumps(dict(payload), sort_keys=True)
        current = self._conn.execute(
            """
            SELECT state, payload_json
            FROM call_ledger
            WHERE call_occurrence_id = ? AND request_sha256 = ? AND attempt_id = ?
            """,
            (occurrence_id, request_sha256, attempt_id),
        ).fetchone()
        if current is None:
            self._conn.rollback()
            raise ObservationScheduleStoreError("CALL_OCCURRENCE_MISSING")
        if str(current["state"]) == "COMPLETED":
            if str(current["payload_json"]) != encoded:
                self._conn.rollback()
                raise ObservationScheduleStoreError("CALL_OCCURRENCE_IDENTITY_CONFLICT")
            self._conn.rollback()
            return
        if str(current["state"]) != "STARTED":
            self._conn.rollback()
            raise ObservationScheduleStoreError("CALL_OCCURRENCE_STATE_CONFLICT")
        self._conn.execute(
            """
            UPDATE call_ledger
            SET state = 'COMPLETED', payload_json = ?, updated_at = ?
            WHERE call_occurrence_id = ? AND request_sha256 = ? AND attempt_id = ?
              AND state = 'STARTED'
            """,
            (encoded, now, occurrence_id, request_sha256, attempt_id),
        )
        self._conn.commit()

    def call_state(self, call_occurrence_id: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT state FROM call_ledger
            WHERE call_occurrence_id = ?
            LIMIT 1
            """,
            (call_occurrence_id,),
        ).fetchone()
        return str(row["state"]) if row is not None else None

    def call_payload(self, call_occurrence_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT payload_json FROM call_ledger
            WHERE call_occurrence_id = ?
            LIMIT 1
            """,
            (call_occurrence_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def record_batch(self, batch_content_sha256: str, payload: Mapping[str, Any], *, clock: datetime | None = None) -> None:
        self._require_write_lease(clock)
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
        self._require_write_lease(clock)
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
        self._require_write_lease()
        self._conn.execute(
            "UPDATE restore_markers SET resolved = 1 WHERE marker_id = 'UNRESOLVED'"
        )
        self._conn.commit()

    def due_counts(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT state, COUNT(*) AS n FROM due_observations GROUP BY state"
        ).fetchall()
        return {str(row["state"]): int(row["n"]) for row in rows}

    def due_state(self, row: Mapping[str, Any]) -> str | None:
        current = self._conn.execute(
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
        return str(current["state"]) if current is not None else None

    def get_due(self, row: Mapping[str, Any]) -> dict[str, Any] | None:
        current = self._conn.execute(
            """
            SELECT * FROM due_observations
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
            return None
        result = dict(current)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def persist_registered_schedule(
        self,
        *,
        schedule_sha256: str,
        schedule_key: str,
        document: Mapping[str, Any],
        clock: datetime | None = None,
    ) -> str:
        self._require_write_lease(clock)
        now = _now(clock)
        payload = json.dumps(dict(document), sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(
            canonical_json_bytes(collection_projection(document))
        ).hexdigest()
        if digest != schedule_sha256:
            raise ObservationScheduleStoreError("INVALID_IDENTITY")
        existing = self._conn.execute(
            "SELECT document_sha256 FROM registered_schedules WHERE schedule_sha256 = ?",
            (schedule_sha256,),
        ).fetchone()
        if existing is not None:
            if str(existing["document_sha256"]) != digest:
                raise ObservationScheduleStoreError("SCHEDULE_IDENTITY_CONFLICT")
            alias = self._conn.execute(
                """
                SELECT 1 FROM schedule_aliases
                WHERE schedule_sha256 = ? AND schedule_key = ?
                """,
                (schedule_sha256, schedule_key),
            ).fetchone()
            if alias is not None:
                return "REGISTER_REPLAY"
            alias_digest = hashlib.sha256(
                canonical_json_bytes(
                    {"schedule_key": schedule_key, "schedule_sha256": schedule_sha256}
                )
            ).hexdigest()
            self._conn.execute(
                """
                INSERT INTO schedule_aliases(
                    schedule_sha256, schedule_key, alias_binding_sha256, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (schedule_sha256, schedule_key, alias_digest, now),
            )
            self._conn.commit()
            return "ATTACHED_TO_EXISTING_PLAN"
        self._conn.execute(
            """
            INSERT INTO registered_schedules(
                schedule_sha256, schedule_key, document_json, document_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (schedule_sha256, schedule_key, payload, digest, now),
        )
        alias_digest = hashlib.sha256(
            canonical_json_bytes(
                {"schedule_key": schedule_key, "schedule_sha256": schedule_sha256}
            )
        ).hexdigest()
        self._conn.execute(
            """
            INSERT INTO schedule_aliases(
                schedule_sha256, schedule_key, alias_binding_sha256, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (schedule_sha256, schedule_key, alias_digest, now),
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
        payload["aliases"] = [
            dict(alias)
            for alias in self._conn.execute(
                """
                SELECT schedule_key, alias_binding_sha256, created_at
                FROM schedule_aliases
                WHERE schedule_sha256 = ?
                ORDER BY schedule_key ASC
                """,
                (schedule_sha256,),
            ).fetchall()
        ]
        return payload

    def get_registered_schedule_by_key(self, schedule_key: str) -> dict[str, Any] | None:
        rows = self._conn.execute(
            """
            SELECT schedule_sha256 FROM schedule_aliases
            WHERE schedule_key = ?
            ORDER BY created_at ASC, schedule_sha256 ASC
            """,
            (schedule_key,),
        ).fetchall()
        if not rows:
            return None
        digests = {str(row["schedule_sha256"]) for row in rows}
        if len(digests) != 1:
            raise ObservationScheduleStoreError("SCHEDULE_KEY_AMBIGUOUS")
        return self.get_registered_schedule(next(iter(digests)))

    def persist_authority(self, receipt: Mapping[str, Any], *, clock: datetime | None = None) -> str:
        self._require_write_lease(clock)
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
            ORDER BY created_at DESC, receipt_sha256 DESC
            LIMIT 1
            """,
            (schedule_sha256,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def list_activations(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM schedule_activations
            ORDER BY schedule_sha256 ASC, activation_id ASC
            """
        ).fetchall()
        decoded: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["payload"] = json.loads(payload["payload_json"])
            decoded.append(payload)
        return decoded

    def list_calls(self, *, primitive_id: str | None = None) -> list[dict[str, Any]]:
        if primitive_id:
            rows = self._conn.execute(
                """
                SELECT request_sha256, call_occurrence_id, attempt_id,
                       state, primitive_id, payload_json
                FROM call_ledger
                WHERE primitive_id = ?
                ORDER BY updated_at ASC
                """,
                (primitive_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT request_sha256, call_occurrence_id, attempt_id,
                       state, primitive_id, payload_json
                FROM call_ledger
                ORDER BY updated_at ASC
                """
            ).fetchall()
        decoded: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["payload"] = json.loads(payload.pop("payload_json") or "{}")
            decoded.append(payload)
        return decoded

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

    def candidate_exists(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
        entity_id: str,
    ) -> bool:
        row = self._conn.execute(
            """
            SELECT 1 FROM candidate_members
            WHERE schedule_sha256 = ? AND activation_id = ? AND entity_id = ?
            """,
            (schedule_sha256, activation_id, entity_id),
        ).fetchone()
        return row is not None

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
        self._require_write_lease(clock)
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

    def latest_provider_call_at(
        self,
        *,
        schedule_sha256: str,
        activation_id: str,
    ) -> str | None:
        rows = self._conn.execute(
            """
            SELECT last_provider_call_at
            FROM accounting_counters
            WHERE schedule_sha256 = ? AND activation_id = ?
              AND last_provider_call_at IS NOT NULL
            """,
            (schedule_sha256, activation_id),
        ).fetchall()
        stamps = [str(row["last_provider_call_at"]) for row in rows]
        if not stamps:
            return None
        try:
            return max(stamps, key=parse_utc)
        except Exception:
            return max(stamps)

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
        self._require_write_lease(clock)
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
        self._require_write_lease(clock)
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
        self._require_write_lease()
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
