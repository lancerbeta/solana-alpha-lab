"""Safe operational retention for ObservationSchedule SQLite.

Scientific Observation RDP / Parquet, sealed live releases/corpus, candidate
denominator truth, authority/activation/accounting identity are NEVER deleted.

Compacts aged COMPLETED call_ledger provider bodies to provenance metadata.
Optionally removes aged poll_slot cache bodies when they cannot participate in
current scheduling/recovery.

Substrate truth: decoded/canonical provider JSON in call_ledger — NOT
byte-identical original HTTP response bytes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from solana_alpha_lab.factory.observation_panel_coverage import (
    SCIENTIFIC_CLOSED_DUE_STATES,
    UNRESOLVED_REQUIRED_DUE_STATES,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
)

COMPACTION_MARKER = "COMPACTED_PROVENANCE_ONLY"
PROVENANCE_KEEP_KEYS = frozenset(
    {
        "http_class",
        "response_sha256",
        "request_sha256",
        "status",
        "missing_reason",
        "latency_ms",
        "started_at",
        "completed_at",
        "observed_at",
        "error_class",
        "primitive_id",
        "attempt_id",
        "call_occurrence_id",
        "url_digest",
        "transport_class",
        "request_started_at",
        "response_received_at",
        "first_reliable_available_at",
        "http_status",
    }
)
BODY_KEYS = frozenset({"rows", "body", "raw_body", "response_body", "payload_rows"})


class ObservationScheduleRetentionError(ValueError):
    """Typed retention failure."""


def _safe_parse(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return parse_utc(raw)
    except Exception:
        return None


def _payload_has_compactable_body(payload: Mapping[str, Any]) -> bool:
    if str(payload.get("raw_payload_retention") or "") == COMPACTION_MARKER:
        return False
    for key in BODY_KEYS:
        if key in payload and payload[key] not in (None, [], {}, ""):
            return True
    # Large unexplained nested blobs beyond provenance
    encoded = json.dumps(dict(payload), sort_keys=True, default=str)
    if len(encoded) > 2048 and any(k not in PROVENANCE_KEEP_KEYS for k in payload):
        return True
    return False


def compact_payload(payload: Mapping[str, Any], *, compacted_at: str) -> dict[str, Any]:
    kept: dict[str, Any] = {}
    for key, value in payload.items():
        if key in PROVENANCE_KEEP_KEYS:
            kept[key] = value
    kept["raw_payload_retention"] = COMPACTION_MARKER
    kept["raw_payload_compacted_at"] = compacted_at
    kept["raw_retention_substrate"] = (
        "DECODED_CANONICAL_PROVIDER_JSON_NOT_BYTE_IDENTICAL_HTTP"
    )
    # Preserve sha of pre-compaction body when present for audit without retaining body.
    if "response_sha256" not in kept and isinstance(payload.get("response_sha256"), str):
        kept["response_sha256"] = payload["response_sha256"]
    return kept


def retention_cutoff(*, now: datetime, raw_retention_days: int) -> datetime:
    if raw_retention_days < 1:
        raise ObservationScheduleRetentionError("RAW_RETENTION_DAYS_INVALID")
    clock = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return clock.astimezone(UTC) - timedelta(days=int(raw_retention_days))


def _request_sha_has_unresolved_due(
    store: ObservationScheduleStore, request_sha256: str
) -> bool:
    rows = store._conn.execute(  # noqa: SLF001
        """
        SELECT state FROM due_observations
        WHERE request_sha256 = ?
        """,
        (request_sha256,),
    ).fetchall()
    if not rows:
        return False
    for row in rows:
        state = str(row["state"] or "")
        if state in UNRESOLVED_REQUIRED_DUE_STATES or state == "BLOCKED_BUDGET":
            return True
        if state not in SCIENTIFIC_CLOSED_DUE_STATES:
            return True
    return False


def _has_started_call(store: ObservationScheduleStore, request_sha256: str) -> bool:
    row = store._conn.execute(  # noqa: SLF001
        """
        SELECT 1 FROM call_ledger
        WHERE request_sha256 = ? AND state = 'STARTED'
        LIMIT 1
        """,
        (request_sha256,),
    ).fetchone()
    return row is not None


def evaluate_retention(
    store: ObservationScheduleStore,
    *,
    now: datetime,
    raw_retention_days: int,
) -> dict[str, Any]:
    cutoff = retention_cutoff(now=now, raw_retention_days=raw_retention_days)
    cutoff_text = render_utc(cutoff)
    eligible_calls: list[dict[str, Any]] = []
    protected_calls: list[dict[str, Any]] = []
    eligible_payload_bytes = 0
    protected_payload_bytes = 0

    rows = store._conn.execute(  # noqa: SLF001
        """
        SELECT call_occurrence_id, request_sha256, attempt_id, state,
               primitive_id, payload_json, created_at, updated_at
        FROM call_ledger
        ORDER BY updated_at ASC
        """
    ).fetchall()
    for row in rows:
        payload = json.loads(str(row["payload_json"] or "{}"))
        size = len(str(row["payload_json"] or ""))
        meta = {
            "call_occurrence_id": row["call_occurrence_id"],
            "request_sha256": row["request_sha256"],
            "state": row["state"],
            "primitive_id": row["primitive_id"],
            "updated_at": row["updated_at"],
            "payload_bytes": size,
        }
        state = str(row["state"])
        updated = _safe_parse(row["updated_at"])
        if state != "COMPLETED":
            meta["protect_reason"] = "NOT_COMPLETED"
            protected_calls.append(meta)
            protected_payload_bytes += size
            continue
        if updated is None or updated >= cutoff:
            meta["protect_reason"] = "YOUNGER_THAN_RETENTION"
            protected_calls.append(meta)
            protected_payload_bytes += size
            continue
        if not _payload_has_compactable_body(payload):
            meta["protect_reason"] = "ALREADY_COMPACT_OR_NO_BODY"
            protected_calls.append(meta)
            protected_payload_bytes += size
            continue
        if _has_started_call(store, str(row["request_sha256"])):
            meta["protect_reason"] = "STARTED_CALL_SAME_REQUEST"
            protected_calls.append(meta)
            protected_payload_bytes += size
            continue
        if _request_sha_has_unresolved_due(store, str(row["request_sha256"])):
            meta["protect_reason"] = "UNRESOLVED_OR_NONTERMINAL_DUE"
            protected_calls.append(meta)
            protected_payload_bytes += size
            continue
        eligible_calls.append(meta)
        eligible_payload_bytes += size

    eligible_polls: list[dict[str, Any]] = []
    protected_polls: list[dict[str, Any]] = []
    poll_rows = store._conn.execute(  # noqa: SLF001
        """
        SELECT poll_slot_id, request_sha256, payload_json, created_at
        FROM poll_slots
        ORDER BY created_at ASC
        """
    ).fetchall()
    for row in poll_rows:
        size = len(str(row["payload_json"] or ""))
        meta = {
            "poll_slot_id": row["poll_slot_id"],
            "request_sha256": row["request_sha256"],
            "created_at": row["created_at"],
            "payload_bytes": size,
        }
        created = _safe_parse(row["created_at"])
        if created is None or created >= cutoff:
            meta["protect_reason"] = "YOUNGER_THAN_RETENTION"
            protected_polls.append(meta)
            continue
        if _has_started_call(store, str(row["request_sha256"])):
            meta["protect_reason"] = "STARTED_CALL_SAME_REQUEST"
            protected_polls.append(meta)
            continue
        if _request_sha_has_unresolved_due(store, str(row["request_sha256"])):
            meta["protect_reason"] = "UNRESOLVED_OR_NONTERMINAL_DUE"
            protected_polls.append(meta)
            continue
        # Empty / already-cleared bodies
        payload = json.loads(str(row["payload_json"] or "{}"))
        if not payload or payload.get("poll_slot_retention") == COMPACTION_MARKER:
            meta["protect_reason"] = "ALREADY_COMPACT_OR_EMPTY"
            protected_polls.append(meta)
            continue
        eligible_polls.append(meta)

    sqlite_bytes = int(store.path.stat().st_size) if store.path.is_file() else 0
    wal = Path(str(store.path) + "-wal")
    wal_bytes = int(wal.stat().st_size) if wal.is_file() else 0

    return {
        "schema": "smial.observation-schedule-retention-status",
        "schema_version": "1.0",
        "mode": "status",
        "raw_retention_days": int(raw_retention_days),
        "retention_cutoff_at": cutoff_text,
        "raw_retention_substrate": (
            "DECODED_CANONICAL_PROVIDER_JSON_IN_CALL_LEDGER_NOT_BYTE_IDENTICAL_HTTP"
        ),
        "never_deleted": [
            "observation_rdp_parquet",
            "sealed_live_releases_corpus",
            "candidate_member_denominator",
            "authority_receipts_activation_accounting",
            "call_occurrence_identity_and_http_class_timing_hashes",
        ],
        "eligible_call_compactions": len(eligible_calls),
        "eligible_call_payload_bytes": eligible_payload_bytes,
        "protected_calls": len(protected_calls),
        "protected_call_payload_bytes": protected_payload_bytes,
        "eligible_poll_slot_compactions": len(eligible_polls),
        "protected_poll_slots": len(protected_polls),
        "sqlite_file_bytes": sqlite_bytes,
        "sqlite_wal_bytes": wal_bytes,
        "expected_reclaim_reuse_class": (
            "SQLITE_FREELIST_REUSE_WITHOUT_VACUUM"
            if eligible_calls or eligible_polls
            else "NONE"
        ),
        "eligible_call_ids": [c["call_occurrence_id"] for c in eligible_calls],
        "eligible_poll_slot_ids": [p["poll_slot_id"] for p in eligible_polls],
        "protected_sample": protected_calls[:20],
        "observed_at": render_utc(now if now.tzinfo else now.replace(tzinfo=UTC)),
    }


def apply_retention(
    store: ObservationScheduleStore,
    *,
    now: datetime,
    raw_retention_days: int,
    dry_run: bool = True,
) -> dict[str, Any]:
    status = evaluate_retention(
        store, now=now, raw_retention_days=raw_retention_days
    )
    if dry_run:
        status["mode"] = "dry-run"
        status["applied_call_compactions"] = 0
        status["applied_poll_slot_compactions"] = 0
        return status

    clock = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    clock = clock.astimezone(UTC)
    compacted_at = render_utc(clock)
    applied_calls = 0
    applied_polls = 0

    lease = store.acquire_lease("observation-schedule-retention", clock=clock)
    if lease is None:
        raise ObservationScheduleRetentionError("WRITER_BUSY")
    try:
        # Re-evaluate under exclusive lease so protect predicates cannot race a tick.
        status = evaluate_retention(
            store, now=clock, raw_retention_days=raw_retention_days
        )
        for occurrence_id in list(status["eligible_call_ids"]):
            row = store._conn.execute(  # noqa: SLF001
                """
                SELECT request_sha256, attempt_id, state, payload_json, updated_at
                FROM call_ledger WHERE call_occurrence_id = ?
                """,
                (occurrence_id,),
            ).fetchone()
            if row is None or str(row["state"]) != "COMPLETED":
                continue
            if _has_started_call(store, str(row["request_sha256"])):
                continue
            if _request_sha_has_unresolved_due(store, str(row["request_sha256"])):
                continue
            updated = _safe_parse(row["updated_at"])
            cutoff = retention_cutoff(now=clock, raw_retention_days=raw_retention_days)
            if updated is None or updated >= cutoff:
                continue
            payload = json.loads(str(row["payload_json"] or "{}"))
            if not _payload_has_compactable_body(payload):
                continue
            new_payload = compact_payload(payload, compacted_at=compacted_at)
            encoded = json.dumps(new_payload, sort_keys=True)
            # Preserve original updated_at so 24h / freshness windows are not falsified.
            store._conn.execute(  # noqa: SLF001
                """
                UPDATE call_ledger
                SET payload_json = ?
                WHERE call_occurrence_id = ? AND state = 'COMPLETED'
                """,
                (encoded, occurrence_id),
            )
            applied_calls += 1

        empty_poll = json.dumps(
            {
                "poll_slot_retention": COMPACTION_MARKER,
                "raw_payload_compacted_at": compacted_at,
            },
            sort_keys=True,
        )
        for poll_id in list(status["eligible_poll_slot_ids"]):
            row = store._conn.execute(  # noqa: SLF001
                """
                SELECT request_sha256, created_at, payload_json
                FROM poll_slots WHERE poll_slot_id = ?
                """,
                (poll_id,),
            ).fetchone()
            if row is None:
                continue
            if _has_started_call(store, str(row["request_sha256"])):
                continue
            if _request_sha_has_unresolved_due(store, str(row["request_sha256"])):
                continue
            created = _safe_parse(row["created_at"])
            cutoff = retention_cutoff(now=clock, raw_retention_days=raw_retention_days)
            if created is None or created >= cutoff:
                continue
            store._conn.execute(  # noqa: SLF001
                """
                UPDATE poll_slots
                SET payload_json = ?
                WHERE poll_slot_id = ?
                """,
                (empty_poll, poll_id),
            )
            applied_polls += 1

        store._conn.commit()  # noqa: SLF001
    finally:
        store.release_lease(lease)

    status["mode"] = "apply"
    status["applied_call_compactions"] = applied_calls
    status["applied_poll_slot_compactions"] = applied_polls
    status["idempotent"] = True
    return status


__all__ = [
    "COMPACTION_MARKER",
    "ObservationScheduleRetentionError",
    "apply_retention",
    "compact_payload",
    "evaluate_retention",
    "retention_cutoff",
]
