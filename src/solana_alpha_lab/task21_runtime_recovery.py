"""Deterministic pre-collection recovery helpers for TASK-21."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]
PROBE_FILENAME_PREFIX = "TASK21_RUNTIME_RECOVERY_PROBE_v1"
BACKUP_MAXIMUM_AGE_HOURS = 24
BACKUP_OVERDUE_AFTER_HOURS = 26
DISABLE_NEW_T2_AFTER_OVERDUE_HOURS = 48
RESTORE_OVERDUE_AFTER_HOURS = 7 * 24


class Task21RecoveryError(RuntimeError):
    """Recovery evidence does not satisfy the frozen TASK-21 gate."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def content_addressed_filename(value: bytes) -> str:
    return f"{PROBE_FILENAME_PREFIX}_{sha256_bytes(value)}.json"


def _load_probe(value: bytes) -> JsonObject:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task21RecoveryError("probe_json_invalid") from exc
    if not isinstance(parsed, dict):
        raise Task21RecoveryError("probe_root_invalid")
    return parsed


def validate_probe_bytes(value: bytes) -> JsonObject:
    """Fail closed unless bytes are the bounded, non-secret TASK-21 probe."""

    probe = _load_probe(value)
    required = {
        "schema": "smial.task21.runtime-recovery-probe",
        "schema_version": "1.0",
        "task_id": "TASK-21",
        "atom_id": "T21-A3_PRE_COLLECTION_RUNTIME_RECOVERY_GATE_V1",
        "probe_id": "TASK21_PRE_COLLECTION_RUNTIME_RECOVERY_GATE",
        "purpose": "NON_SECRET_CREATE_ONLY_READBACK_RESTORE_PROBE",
        "contains_secrets": False,
        "contains_personal_data": False,
        "contains_market_data": False,
        "authorizes_forward_collection": False,
        "authorizes_provider_calls": False,
    }
    for key, expected in required.items():
        if probe.get(key) != expected:
            raise Task21RecoveryError(f"probe_contract_drift:{key}")
    if probe.get("payload") != {
        "ordinal": 1,
        "sentinel": "SOLANA_ALPHA_LAB_TASK21_RECOVERY_V1",
    }:
        raise Task21RecoveryError("probe_payload_drift")
    return probe


def materialize_content_addressed_probe(
    *,
    source_path: Path,
    output_directory: Path,
) -> JsonObject:
    """Materialize one deterministic file without replacing existing bytes."""

    value = source_path.read_bytes()
    validate_probe_bytes(value)
    filename = content_addressed_filename(value)
    output_directory.mkdir(parents=True, exist_ok=True)
    destination = output_directory / filename
    if destination.exists():
        if destination.read_bytes() != value:
            raise Task21RecoveryError("existing_probe_bytes_drift")
    else:
        with destination.open("xb") as handle:
            handle.write(value)
    return {
        "path": destination,
        "filename": filename,
        "bytes": len(value),
        "sha256": sha256_bytes(value),
    }


def restore_probe(
    *,
    downloaded_path: Path,
    restore_root: Path,
    expected_sha256: str,
) -> JsonObject:
    """Restore raw read-back bytes to an isolated create-only root."""

    value = downloaded_path.read_bytes()
    actual_sha256 = sha256_bytes(value)
    if actual_sha256 != expected_sha256:
        raise Task21RecoveryError("remote_readback_hash_drift")
    probe = validate_probe_bytes(value)
    filename = content_addressed_filename(value)
    restore_root.mkdir(parents=True, exist_ok=True)
    destination = restore_root / filename
    if destination.exists():
        if destination.read_bytes() != value:
            raise Task21RecoveryError("existing_restore_bytes_drift")
    else:
        with destination.open("xb") as handle:
            handle.write(value)
    return {
        "restored_path": destination,
        "filename": filename,
        "bytes": len(value),
        "sha256": actual_sha256,
        "probe_id": probe["probe_id"],
        "contains_secrets": probe["contains_secrets"],
        "source_mutations": 0,
        "source_deletions": 0,
    }


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise Task21RecoveryError("naive_datetime")
    return value.astimezone(timezone.utc)


def _age_hours(observed_at: datetime, event_at: datetime) -> float:
    seconds = (_utc(observed_at) - _utc(event_at)).total_seconds()
    if seconds < 0:
        raise Task21RecoveryError("future_health_event")
    return seconds / 3600


def evaluate_recovery_health(
    *,
    observed_at: datetime,
    last_successful_backup_at: datetime,
    last_successful_restore_at: datetime,
    exact_readback_ok: bool,
    restore_ok: bool,
    consecutive_failed_backups: int = 0,
    evidence_conflict: bool = False,
    storage_hard_stop: bool = False,
) -> JsonObject:
    """Emit deterministic health state, alerts and admission controls."""

    if consecutive_failed_backups < 0:
        raise Task21RecoveryError("negative_failed_backup_count")
    backup_age = _age_hours(observed_at, last_successful_backup_at)
    restore_age = _age_hours(observed_at, last_successful_restore_at)
    alerts: list[str] = []

    if evidence_conflict:
        health_state = "EVIDENCE_CONFLICT"
        alerts.append("STOP_AFFECTED_WRITES_AND_REQUIRE_OWNER_RECONCILIATION")
    elif storage_hard_stop:
        health_state = "STORAGE_HARD_STOP"
        alerts.append("STOP_NEW_CAPTURE_AND_PRESERVE_ACCEPTED_BYTES")
    elif not exact_readback_ok or not restore_ok or consecutive_failed_backups:
        health_state = "EVIDENCE_AT_RISK"
        alerts.append("DISABLE_NEW_T2_ADMISSIONS_AND_ESCALATE_WITHIN_2H")
    elif backup_age > BACKUP_OVERDUE_AFTER_HOURS:
        health_state = "BACKUP_OVERDUE"
        alerts.append("BLOCK_FREEZE_PROMOTION_AND_DELETION")
        alerts.append("OWNER_ESCALATION_DUE_WITHIN_2H")
    elif restore_age > RESTORE_OVERDUE_AFTER_HOURS:
        health_state = "RESTORE_OVERDUE"
        alerts.append("BLOCK_FREEZE_AND_PROMOTION")
        alerts.append("OWNER_ESCALATION_DUE_WITHIN_24H")
    else:
        health_state = "HEALTHY"
        if backup_age > BACKUP_MAXIMUM_AGE_HOURS:
            alerts.append("BACKUP_GRACE_WINDOW")

    admissions_disabled = (
        health_state
        in {
            "EVIDENCE_AT_RISK",
            "EVIDENCE_CONFLICT",
            "STORAGE_HARD_STOP",
        }
        or backup_age
        >= BACKUP_OVERDUE_AFTER_HOURS
        + DISABLE_NEW_T2_AFTER_OVERDUE_HOURS
    )
    return {
        "health_state": health_state,
        "alerts": alerts,
        "backup_age_hours": round(backup_age, 6),
        "restore_proof_age_hours": round(restore_age, 6),
        "new_t2_admissions_allowed": not admissions_disabled,
        "dataset_freeze_allowed": health_state == "HEALTHY",
        "dataset_promotion_allowed": health_state == "HEALTHY",
    }
