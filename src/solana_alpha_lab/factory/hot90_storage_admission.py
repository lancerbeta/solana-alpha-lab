"""97d same-volume storage admission / runway primitive. No Telegram."""

from __future__ import annotations

from typing import Any

TARGET_BYTES = 40 * 1024 ** 3
HARD_BYTES = 50 * 1024 ** 3
HORIZON_DAYS = 97


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
