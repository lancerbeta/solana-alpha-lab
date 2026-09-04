"""Fail-closed HOT scientific eviction planner. Production path stays disabled."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.hot90_activation import (
    STAGE_RETENTION_ACTIVE,
    load_hot90_activation,
)
from solana_alpha_lab.factory.hot90_remote_verify import (
    REMOTE_CONTENT_SHA256_VERIFIED,
    size_or_mtime_never_authorizes_delete,
)

EVICTION_FORBIDDEN = "SCIENTIFIC_RDP_LOCAL_EVICTION_FORBIDDEN_UNDER_CURRENT_IMMUTABLE_CONST"


class Hot90EvictionError(ValueError):
    """Typed eviction failure."""


def eligibility_clock(payload: Mapping[str, Any]) -> datetime:
    required = (
        "first_reliable_available_at",
        "max_available_to_strategy_at",
        "closed_at",
    )
    stamps: list[datetime] = []
    for key in required:
        raw = payload.get(key)
        if not raw:
            raise Hot90EvictionError("AVAILABILITY_CLOCK_MISSING")
        stamps.append(_parse_utc(str(raw)))
    return max(stamps)


def plan_exact_eviction(
    *,
    root: Path,
    retention: Mapping[str, Any],
    unit: Mapping[str, Any],
    now: datetime,
    unresolved_call_or_due: bool,
    open_publication: bool,
    remote_verify_terminal: str,
    source_paths: Sequence[str],
    data_root: Path,
    plan_hashes: Mapping[str, str],
    fixture_destructive: bool = False,
    uses_mtime: bool = False,
) -> dict[str, Any]:
    if uses_mtime:
        raise Hot90EvictionError("MTIME_AGE_FORBIDDEN")
    activation = load_hot90_activation(root)
    if fixture_destructive is not True:
        if activation.get("production_eviction_enabled") is not True:
            raise Hot90EvictionError("PRODUCTION_EVICTION_DISABLED")
        if activation.get("activation_stage") != STAGE_RETENTION_ACTIVE:
            raise Hot90EvictionError("PRODUCTION_EVICTION_DISABLED")
    if retention.get("canonical_panel_retention") != "IMMUTABLE":
        raise Hot90EvictionError("CONTENT_IMMUTABILITY_REQUIRED")
    if "hot_local_residency_days" not in retention:
        raise Hot90EvictionError(EVICTION_FORBIDDEN)
    days = retention.get("hot_local_residency_days")
    if days != 90:
        raise Hot90EvictionError("HOT_LOCAL_RESIDENCY_DAYS_INVALID")
    clock = eligibility_clock(unit)
    age = now.astimezone(UTC) - clock
    if age <= timedelta(days=90):
        raise Hot90EvictionError("UNIT_NOT_PAST_RESIDENCY")
    if unit.get("terminal") not in {"CLOSED", "TERMINAL"}:
        raise Hot90EvictionError("UNIT_NOT_CLOSED")
    if unresolved_call_or_due:
        raise Hot90EvictionError("UNRESOLVED_CALL_OR_DUE")
    if open_publication:
        raise Hot90EvictionError("OPEN_PUBLICATION_DEPENDENCY")
    if remote_verify_terminal != REMOTE_CONTENT_SHA256_VERIFIED:
        raise Hot90EvictionError("REMOTE_CONTENT_SHA256_REQUIRED")
    exact: list[str] = []
    for relative in source_paths:
        if any(token in relative for token in ("*", "?", "[", "]")):
            raise Hot90EvictionError("WILDCARD_DELETE_FORBIDDEN")
        if relative.endswith("/") or relative.endswith("\\"):
            raise Hot90EvictionError("PARENT_RECURSIVE_DELETE_FORBIDDEN")
        path = data_root / relative
        if path.is_file() is False:
            raise Hot90EvictionError("SOURCE_MISSING")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = plan_hashes.get(relative)
        if expected != digest:
            raise Hot90EvictionError("SOURCE_HASH_CHANGED_SINCE_PLAN")
        exact.append(relative)
    return {
        "eligible": True,
        "exact_paths": exact,
        "age_truth": "MAX_CANONICAL_AVAILABILITY_CLOCK",
        "insufficient_remote_proof": size_or_mtime_never_authorizes_delete(),
    }


def execute_exact_delete(
    *,
    data_root: Path,
    exact_paths: Sequence[str],
    fixture_destructive: bool,
) -> dict[str, Any]:
    if fixture_destructive is not True:
        raise Hot90EvictionError("PRODUCTION_EVICTION_DISABLED")
    deleted: list[str] = []
    for relative in exact_paths:
        if any(token in relative for token in ("*", "?", "[", "]")):
            raise Hot90EvictionError("WILDCARD_DELETE_FORBIDDEN")
        path = data_root / relative
        if path.is_file() is False:
            raise Hot90EvictionError("SOURCE_MISSING")
        if path.is_dir():
            raise Hot90EvictionError("PARENT_RECURSIVE_DELETE_FORBIDDEN")
        path.unlink()
        deleted.append(relative)
    return {"deleted": deleted, "readback": all((data_root / item).exists() is False for item in deleted)}


def _parse_utc(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    stamp = datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)
