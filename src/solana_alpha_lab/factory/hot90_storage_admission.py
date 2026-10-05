"""97d same-volume storage admission / runway primitive. No Telegram."""

from __future__ import annotations

from typing import Any

TARGET_BYTES = 40 * 1024 ** 3
HARD_BYTES = 50 * 1024 ** 3
HORIZON_DAYS = 97

# Frozen conservative LOCAL_MODEL, not a measured compression guarantee.
# Producer, publication, export/staging, backup and workstation copies plus
# one spare copy; commissioning must also approve the whole Factory scope.
EPISODE_RESERVE_COPIES = 6
EPISODE_SAFETY_BYTES = 256 * 1024 ** 2


def episode_drain_reserve(*, remaining_slots: int, prospective_slots: int,
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
