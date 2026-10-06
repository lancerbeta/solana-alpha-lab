"""97d same-volume storage admission / runway primitive. No Telegram."""

from __future__ import annotations

from typing import Any
from pathlib import Path
from collections.abc import Mapping
import re

from solana_alpha_lab.factory.observation_schedule import canonical_sha256

TARGET_BYTES = 40 * 1024 ** 3
HARD_BYTES = 50 * 1024 ** 3
HORIZON_DAYS = 97

# Frozen conservative LOCAL_MODEL, not a measured compression guarantee.
# Producer, publication, export/staging, backup and workstation copies plus
# one spare copy; commissioning must also approve the whole Factory scope.
EPISODE_RESERVE_COPIES = 6
EPISODE_SAFETY_BYTES = 256 * 1024 ** 2


def episode_factory_storage_forecast(*, remaining_slots: int, prospective_slots: int,
                          response_cap_bytes: int, free_bytes: int | None) -> dict[str, Any]:
    if min(remaining_slots, prospective_slots, response_cap_bytes) < 0:
        raise ValueError("DRAIN_RESERVE_INPUT_INVALID")
    committed = remaining_slots * response_cap_bytes * EPISODE_RESERVE_COPIES
    prospective = prospective_slots * response_cap_bytes * EPISODE_RESERVE_COPIES
    required = committed + prospective + EPISODE_SAFETY_BYTES
    status = "UNKNOWN" if free_bytes is None else ("STOP_NEW_INTAKE" if free_bytes < required else "MODEL_HEADROOM")
    return {"status": status, "evidence_class": "MODEL", "free_bytes": free_bytes,
            "remaining_slots": remaining_slots, "committed_drain_reserve_bytes": committed,
            "prospective_reserve_bytes": prospective, "publication_export_backup_copy_factor": EPISODE_RESERVE_COPIES,
            "safety_margin_bytes": EPISODE_SAFETY_BYTES, "required_free_bytes": required,
            "factory_scope_policy": "UNKNOWN_REQUIRES_COMMISSIONING",
            "sampling_auto_reduce": False}


EPISODE_STORAGE_KIND = "EPISODE_PRODUCER_STORAGE_COMMISSIONING_V1"


class EpisodeStorageError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def producer_root_identity(data_root: Path) -> dict[str, int]:
    info = Path(data_root).stat()
    return {"device": info.st_dev, "inode": info.st_ino}


def validate_episode_storage_commissioning(envelope: object, *, data_root: Path,
                                          schedule_sha256: str, activation_id: str) -> dict[str, Any]:
    """Validate exact operator-approved bindings, not grant OPERATE authority."""
    if not isinstance(envelope, Mapping):
        raise EpisodeStorageError("EPISODE_STORAGE_COMMISSIONING_REQUIRED")
    body = dict(envelope)
    sha = body.pop("envelope_sha256", None)
    expected_keys = {"kind", "schedule_sha256", "activation_id", "producer_root_identity",
                     "factory_storage_gate", "verified_backup_sha256", "copy_rehearsal_sha256",
                     "factory_storage_receipt_sha256", "volume_bindings_sha256", "operate_authority_ref",
                     "search_call_local_bytes_max", "nomination_call_local_bytes_max",
                     "slot_metadata_local_bytes_max", "fixed_local_reserve_bytes", "local_safety_bytes"}
    try:
        actual_identity = producer_root_identity(data_root)
        actual_sha = canonical_sha256(body)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        raise EpisodeStorageError("EPISODE_STORAGE_BINDING_INVALID") from exc
    identity = body.get("producer_root_identity")
    if (not isinstance(identity, dict) or set(identity) != {"device", "inode"}
            or any(type(value) is not int or value < 0 for value in identity.values())):
        raise EpisodeStorageError("EPISODE_STORAGE_BINDING_INVALID")
    if (set(body) != expected_keys or body.get("kind") != EPISODE_STORAGE_KIND or actual_sha != sha
            or body.get("schedule_sha256") != schedule_sha256
            or body.get("activation_id") != activation_id
            or body.get("producer_root_identity") != actual_identity):
        raise EpisodeStorageError("EPISODE_STORAGE_BINDING_INVALID")
    if body.get("factory_storage_gate") != "PASS":
        raise EpisodeStorageError("FACTORY_STORAGE_COMMISSIONING_REQUIRED")
    for key in ("verified_backup_sha256", "copy_rehearsal_sha256",
                "factory_storage_receipt_sha256", "volume_bindings_sha256"):
        if not isinstance(body.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", body[key]):
            raise EpisodeStorageError("EPISODE_STORAGE_PROOF_BINDING_REQUIRED")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", str(body.get("operate_authority_ref") or "")):
        raise EpisodeStorageError("EPISODE_STORAGE_OPERATE_AUTHORITY_REQUIRED")
    for key in ("search_call_local_bytes_max", "nomination_call_local_bytes_max",
                "slot_metadata_local_bytes_max", "fixed_local_reserve_bytes", "local_safety_bytes"):
        value = body.get(key)
        if type(value) is not int or not 0 < value < 2**63:
            raise EpisodeStorageError("EPISODE_STORAGE_LOCAL_ENVELOPE_INVALID")
    return dict(envelope)


def episode_drain_reserve(*, remaining_slots: int, prospective_slots: int,
                          remaining_call_groups: int, prospective_call_groups: int,
                          remaining_nomination_calls: int, local_envelope: Mapping[str, Any],
                          free_bytes: int | None) -> dict[str, Any]:
    """Producer-local control. Whole-Factory copies never enter this decision."""
    if min(remaining_slots, prospective_slots, remaining_call_groups,
           prospective_call_groups, remaining_nomination_calls) < 0:
        raise ValueError("DRAIN_RESERVE_INPUT_INVALID")
    per_call = int(local_envelope["search_call_local_bytes_max"])
    per_slot = int(local_envelope["slot_metadata_local_bytes_max"])
    committed = remaining_call_groups * per_call + remaining_slots * per_slot
    prospective = prospective_call_groups * per_call + prospective_slots * per_slot
    nomination = remaining_nomination_calls * int(local_envelope["nomination_call_local_bytes_max"])
    fixed = int(local_envelope["fixed_local_reserve_bytes"])
    safety = int(local_envelope["local_safety_bytes"])
    required = committed + prospective + nomination + fixed + safety
    status = "UNKNOWN_LOCAL_FREE_SPACE" if free_bytes is None else (
        "STOP_NEW_INTAKE" if free_bytes < required else "LOCAL_HEADROOM")
    return {"status": status, "evidence_class": "COMMISSIONING_BOUND_LOCAL_CONTROL",
            "envelope_sha256": local_envelope["envelope_sha256"], "free_bytes": free_bytes,
            "remaining_slots": remaining_slots, "remaining_call_groups": remaining_call_groups,
            "committed_drain_reserve_bytes": committed, "prospective_reserve_bytes": prospective,
            "future_nomination_reserve_bytes": nomination, "fixed_local_reserve_bytes": fixed,
            "safety_margin_bytes": safety, "required_free_bytes": required,
            "factory_scope_policy": "SEPARATE_PRE_ACTIVATION_GATE", "sampling_auto_reduce": False}


def project_storage_runway(
    *,
    incremental_compressed_bytes_per_day: int,
    current_same_volume_factory_bytes: int,
    mutable_backup_peak_bytes: int,
    staging_peak_bytes: int,
    retention_class: str,
) -> dict[str, Any]:
    if incremental_compressed_bytes_per_day < 0:
        raise ValueError("INCREMENTAL_BYTES_INVALID")
    incremental_97d = incremental_compressed_bytes_per_day * HORIZON_DAYS
    projected = (
        current_same_volume_factory_bytes
        + incremental_97d
        + mutable_backup_peak_bytes
        + staging_peak_bytes
    )
    if projected > HARD_BYTES:
        status = "ACTION_REQUIRED"
    elif projected > TARGET_BYTES:
        status = "DEGRADED"
    else:
        status = "OK"
    return {
        "schema": "smial.factory-hot90-storage-runway",
        "schema_version": "1.0",
        "incremental_compressed_bytes_per_day": incremental_compressed_bytes_per_day,
        "incremental_97d_resident_bytes": incremental_97d,
        "mutable_backup_peak_bytes": mutable_backup_peak_bytes,
        "staging_peak_bytes": staging_peak_bytes,
        "current_same_volume_factory_bytes": current_same_volume_factory_bytes,
        "projected_total_same_volume_bytes": projected,
        "target_bytes": TARGET_BYTES,
        "hard_bytes": HARD_BYTES,
        "retention_class": retention_class,
        "status": status,
        "sampling_auto_reduce": False,
        "telegram": False,
    }
