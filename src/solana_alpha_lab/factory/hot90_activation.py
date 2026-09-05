"""Fail-closed HOT90 activation: Git policy/safe default, host runtime state."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

CONFIG_RELATIVE = "configs/factory_hot90_archive_activation_v1.yaml"
RUNTIME_RELATIVE = "local/factory_v1/hot90_activation_runtime.yaml"
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
SOURCE_OVERRIDE = "OVERRIDE"
SOURCE_RUNTIME = "RUNTIME"
SOURCE_GIT_DEFAULT = "GIT_DEFAULT"
ALLOWED_PAYLOAD_KEYS = frozenset(
    {
        "schema",
        "schema_version",
        "as_of",
        "note",
        "activation_stage",
        "production_compaction_enabled",
        "production_eviction_enabled",
        "drive_writes_enabled",
    }
)
SAFE_DEFAULT_PAYLOAD = {
    "activation_stage": STAGE_CURRENT_SAFE,
    "production_compaction_enabled": False,
    "production_eviction_enabled": False,
    "drive_writes_enabled": False,
}


class Hot90ActivationError(ValueError):
    """Typed HOT90 activation failure."""


def load_hot90_activation(
    root: Path,
    *,
    override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if override is not None:
        return _validated(dict(override), source=SOURCE_OVERRIDE)
    runtime_path = root / RUNTIME_RELATIVE
    if runtime_path.exists() or runtime_path.is_symlink():
        _assert_runtime_path_safe(runtime_path, root)
        try:
            loaded = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise Hot90ActivationError("HOT90_RUNTIME_INVALID") from exc
        if not isinstance(loaded, dict):
            raise Hot90ActivationError("HOT90_RUNTIME_INVALID")
        try:
            return _validated(loaded, source=SOURCE_RUNTIME)
        except Hot90ActivationError as exc:
            if str(exc) in {"HOT90_ACTIVATION_INVALID", "HOT90_ACTIVATION_STAGE_INVALID"}:
                raise Hot90ActivationError("HOT90_RUNTIME_INVALID") from exc
            raise
    path = root / CONFIG_RELATIVE
    if path.is_file() is False:
        return _validated(dict(SAFE_DEFAULT_PAYLOAD), source=SOURCE_GIT_DEFAULT)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise Hot90ActivationError("HOT90_ACTIVATION_INVALID")
    return _validated(loaded, source=SOURCE_GIT_DEFAULT)


def write_hot90_runtime_state(root: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    validated = _validated(dict(payload), source=SOURCE_RUNTIME)
    dest = root / RUNTIME_RELATIVE
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        _assert_runtime_path_safe(dest, root)
    document = {
        "schema": "smial.factory-hot90-archive-activation",
        "schema_version": "1.0",
        "activation_stage": validated["activation_stage"],
        "production_compaction_enabled": validated["production_compaction_enabled"],
        "production_eviction_enabled": validated["production_eviction_enabled"],
        "drive_writes_enabled": validated["drive_writes_enabled"],
        "note": "HOST RUNTIME STATE. Not Git policy. SET requires an exact owner gate.",
    }
    encoded = yaml.safe_dump(document, sort_keys=True, allow_unicode=False)
    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists() or tmp.is_symlink():
        if tmp.is_symlink():
            raise Hot90ActivationError("HOT90_RUNTIME_UNSAFE")
        tmp.unlink()
    tmp.write_text(encoded, encoding="utf-8")
    tmp.replace(dest)
    return load_hot90_activation(root)


def require_drive_writes_enabled(activation: Mapping[str, Any]) -> None:
    if activation.get("drive_writes_enabled") is True:
        return
    raise Hot90ActivationError("HOT90_DRIVE_WRITES_DISABLED")


def _validated(payload: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    if any(key not in ALLOWED_PAYLOAD_KEYS for key in payload):
        raise Hot90ActivationError(
            "HOT90_RUNTIME_INVALID" if source == SOURCE_RUNTIME else "HOT90_ACTIVATION_INVALID"
        )
    raw_stage = payload.get("activation_stage")
    if isinstance(raw_stage, str) is False or raw_stage == "":
        raise Hot90ActivationError("HOT90_ACTIVATION_STAGE_INVALID")
    stage = raw_stage
    if stage not in ALLOWED_STAGES:
        raise Hot90ActivationError("HOT90_ACTIVATION_STAGE_INVALID")
    compaction = payload.get("production_compaction_enabled") is True
    eviction = payload.get("production_eviction_enabled") is True
    drive = payload.get("drive_writes_enabled") is True
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
        "activation_source": source,
    }


def _assert_runtime_path_safe(path: Path, root: Path) -> None:
    expected = (root / RUNTIME_RELATIVE).resolve()
    cursor = path
    for _ in range(len(path.parts) + 1):
        if cursor.exists() and cursor.is_symlink():
            raise Hot90ActivationError("HOT90_RUNTIME_UNSAFE")
        if cursor == cursor.parent:
            break
        cursor = cursor.parent
    if path.exists() is False:
        raise Hot90ActivationError("HOT90_RUNTIME_UNSAFE")
    if path.is_file() is False:
        raise Hot90ActivationError("HOT90_RUNTIME_UNSAFE")
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise Hot90ActivationError("HOT90_RUNTIME_UNSAFE") from exc
    if resolved != expected:
        raise Hot90ActivationError("HOT90_RUNTIME_UNSAFE")
