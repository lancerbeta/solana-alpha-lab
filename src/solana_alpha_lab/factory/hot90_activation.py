"""Fail-closed HOT90 activation stages. Default preserves current live semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

CONFIG_RELATIVE = "configs/factory_hot90_archive_activation_v1.yaml"
STAGE_CURRENT_SAFE = "CURRENT_SAFE"
STAGE_WRITE_ONLY_SHADOW = "WRITE_ONLY_SHADOW"
STAGE_DURABILITY_CUTOVER = "DURABILITY_CUTOVER"
STAGE_RETENTION_ACTIVE = "RETENTION_ACTIVE"
ALLOWED_STAGES = frozenset(
    {
        STAGE_CURRENT_SAFE,
        STAGE_WRITE_ONLY_SHADOW,
        STAGE_DURABILITY_CUTOVER,
        STAGE_RETENTION_ACTIVE,
    }
)


class Hot90ActivationError(ValueError):
    """Typed HOT90 activation failure."""


def load_hot90_activation(
    root: Path,
    *,
    override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if override is not None:
        payload = dict(override)
    else:
        path = root / CONFIG_RELATIVE
        if path.is_file() is False:
            payload = {
                "activation_stage": STAGE_CURRENT_SAFE,
                "production_compaction_enabled": False,
                "production_eviction_enabled": False,
                "drive_writes_enabled": False,
            }
        else:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise Hot90ActivationError("HOT90_ACTIVATION_INVALID")
            payload = loaded
    stage = str(payload.get("activation_stage") or STAGE_CURRENT_SAFE)
    if stage not in ALLOWED_STAGES:
        raise Hot90ActivationError("HOT90_ACTIVATION_STAGE_INVALID")
    compaction = bool(payload.get("production_compaction_enabled") is True)
    eviction = bool(payload.get("production_eviction_enabled") is True)
    drive = bool(payload.get("drive_writes_enabled") is True)
    if stage == STAGE_CURRENT_SAFE and (compaction or eviction or drive):
        raise Hot90ActivationError("HOT90_CURRENT_SAFE_FORBIDS_DESTRUCTIVE_FLAGS")
    if eviction and stage != STAGE_RETENTION_ACTIVE:
        raise Hot90ActivationError("HOT90_EVICTION_REQUIRES_RETENTION_ACTIVE")
    if compaction and stage == STAGE_CURRENT_SAFE:
        raise Hot90ActivationError("HOT90_CURRENT_SAFE_FORBIDS_DESTRUCTIVE_FLAGS")
    if drive and stage == STAGE_CURRENT_SAFE:
        raise Hot90ActivationError("HOT90_CURRENT_SAFE_FORBIDS_DRIVE_WRITES")
    return {
        "activation_stage": stage,
        "production_compaction_enabled": compaction,
        "production_eviction_enabled": eviction,
        "drive_writes_enabled": drive,
        "members_layout": (
            "SNAPSHOT_PLUS_DELTA"
            if stage in {STAGE_WRITE_ONLY_SHADOW, STAGE_DURABILITY_CUTOVER, STAGE_RETENTION_ACTIVE}
            else "LEGACY_PER_PUBLICATION"
        ),
        "new_write_zstd": stage != STAGE_CURRENT_SAFE,
    }


def require_drive_writes_enabled(activation: Mapping[str, Any]) -> None:
    if activation.get("drive_writes_enabled") is True:
        return
    raise Hot90ActivationError("HOT90_DRIVE_WRITES_DISABLED")
