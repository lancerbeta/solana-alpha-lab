"""Mutable-only backup source selection. Live package_backup topology unchanged until cutover."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from solana_alpha_lab.factory.hot90_activation import (
    STAGE_CURRENT_SAFE,
    STAGE_DURABILITY_CUTOVER,
    STAGE_RETENTION_ACTIVE,
    STAGE_WRITE_ONLY_SHADOW,
)

DEFAULT_MUTABLE_SOURCES = (
    "local/factory_v1/operational_state.sqlite",
    "local/factory_v1/paper_plane_state.sqlite",
    "local/factory_v1/observation_schedule_state.sqlite",
)
DEFAULT_MUTABLE_RECURSIVE = (
    "local/factory_v1/observation_rdp/datasets/publication_jobs",
)


def mutable_backup_sources(
    backup: Mapping[str, Any],
    *,
    activation_stage: str,
) -> dict[str, Any]:
    live_recursive = list(backup.get("recursive_relative_paths") or [])
    if activation_stage == STAGE_CURRENT_SAFE:
        return {
            "source_relative_paths": list(backup.get("source_relative_paths") or []),
            "recursive_relative_paths": live_recursive,
            "includes_full_observation_rdp": "local/factory_v1/observation_rdp" in live_recursive,
            "cutover": False,
        }
    if activation_stage not in {
        STAGE_WRITE_ONLY_SHADOW,
        STAGE_DURABILITY_CUTOVER,
        STAGE_RETENTION_ACTIVE,
    }:
        raise ValueError("HOT90_ACTIVATION_STAGE_INVALID")
    mutable_sources = list(backup.get("mutable_only_source_relative_paths") or DEFAULT_MUTABLE_SOURCES)
    mutable_recursive = list(
        backup.get("mutable_only_recursive_relative_paths") or list(DEFAULT_MUTABLE_RECURSIVE)
    )
    if activation_stage == STAGE_WRITE_ONLY_SHADOW:
        return {
            "source_relative_paths": list(backup.get("source_relative_paths") or []),
            "recursive_relative_paths": live_recursive,
            "shadow_mutable_only": {
                "source_relative_paths": mutable_sources,
                "recursive_relative_paths": mutable_recursive,
            },
            "includes_full_observation_rdp": "local/factory_v1/observation_rdp" in live_recursive,
            "cutover": False,
        }
    if "local/factory_v1/observation_rdp" in mutable_recursive:
        raise ValueError("MUTABLE_BACKUP_MUST_NOT_COPY_FULL_RDP")
    return {
        "source_relative_paths": mutable_sources,
        "recursive_relative_paths": mutable_recursive,
        "includes_full_observation_rdp": False,
        "cutover": True,
    }
