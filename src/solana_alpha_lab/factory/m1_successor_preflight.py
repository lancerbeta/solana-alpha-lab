"""Zero-network M1 successor preflight composer/checker.

Given a fresh readback of the currently ACTIVE predecessor activation, its
immutable predecessor schedule and a bounded M1 campaign request, propose an
immutable successor schedule that preserves every predecessor semantic while
adding M1 USDC execution-calibration observations.

This composer performs no provider calls and no runtime mutation. It never
authorizes or activates anything; the authority-request material it returns
is input for the owner's exact schedule-authorization flow.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.m1_execution_reality import (
    M1_CAPABILITY_ID,
    NOTIONAL_10_USD,
    NOTIONAL_100_USD,
    NOTIONAL_ENTRY_BUNDLE,
    NOTIONAL_REVERSE_BUNDLE,
)
from solana_alpha_lab.factory.observation_schedule import (
    ObservationScheduleError,
    parse_utc,
    render_utc,
    schedule_sha256 as compute_schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (
    compile_schedule_document,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    build_authority_request,
)

M1_PREFLIGHT_SCHEMA_VERSION = "1.0"
MAX_BUNDLES_PER_POINT = 8
MIN_M1_TARGET_MEMBERS = 1
MAX_M1_TARGET_MEMBERS = 120
# M1 adds at most 4 provider calls per sampled eligible member
# ($10 entry, $10 reverse, $100 entry, $100 reverse).
M1_CALLS_PER_MEMBER_MAX = 4
M1_SUCCESSOR_KEY_SUFFIX = "M1-USDC-XCAL-001"

PREFLIGHT_BLOCKERS: frozenset[str] = frozenset(
    {
        "PREDECESSOR_READBACK_MISSING",
        "PREDECESSOR_READBACK_NOT_ACTIVE",
        "PREDECESSOR_SCHEDULE_MISSING",
        "PREDECESSOR_IDENTITY_MISMATCH",
        "M1_CAMPAIGN_REQUEST_INVALID",
        "M1_BUNDLE_CAPACITY_GAP",
        "M1_PROVIDER_BUDGET_GAP",
        "SUCCESSOR_COMPILE_FAILED",
        "SUCCESSOR_SEMANTIC_CONSERVATION_FAILED",
        "SUCCESSOR_AUTHORITY_MATERIAL_FAILED",
    }
)


class M1SuccessorPreflightError(ValueError):
    """Typed M1 successor preflight failure."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise M1SuccessorPreflightError(code)


def _point_bundle_ids(schedule: Mapping[str, Any], point_id: str) -> list[str]:
    for point in [schedule["x_point"], *schedule["y_points"]]:
        if str(point["point_id"]) == point_id:
            return [str(item) for item in point["bundle_ids"]]
    return []


def _blocked(reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "smial.m1-successor-preflight",
        "schema_version": M1_PREFLIGHT_SCHEMA_VERSION,
        "capability_id": M1_CAPABILITY_ID,
        "terminal": "M1_SUCCESSOR_PREFLIGHT_BLOCKED",
        "blocked_reason": reason,
        "compatible": False,
        "proposed_successor": None,
        "semantic_diff": None,
        "sampling_proposal": None,
        "provider_call_envelope": None,
        "cutover_proposal": None,
        "authority_request_material": None,
        "network_calls": 0,
        "runtime_mutations": 0,
    }
    payload.update(extra)
    return payload


def _collect_semantics(schedule: Mapping[str, Any]) -> dict[str, Any]:
    """Every predecessor semantic M1 must conserve (§16)."""

    return {
        "source_poll": deepcopy(schedule["source_poll"]),
        "population": deepcopy(schedule["population"]),
        "sampling_policy": deepcopy(schedule["sampling"]["policy"]),
        "sampling_seed": deepcopy(schedule["sampling"]["seed"]),
        "x_point_id": str(schedule["x_point"]["point_id"]),
        "x_point_offset": int(schedule["x_point"]["due_offset_seconds"]),
        "x_point_bundles": _point_bundle_ids(schedule, str(schedule["x_point"]["point_id"])),
        "y_points": [
            {
                "point_id": str(point["point_id"]),
                "due_offset_seconds": int(point["due_offset_seconds"]),
                "bundle_ids": [str(item) for item in point["bundle_ids"]],
            }
            for point in schedule["y_points"]
        ],
        "missingness": deepcopy(schedule["missingness"]),
        "disappearance": deepcopy(schedule["disappearance"]),
        "retention": deepcopy(schedule["retention"]),
        "authority": deepcopy(schedule["authority"]),
        "outputs": deepcopy(schedule["outputs"]),
        "budgets_retry": schedule["budgets"]["retry"],
        "budgets_fallback": schedule["budgets"]["fallback"],
        "budgets_cash_usd_max": str(schedule["budgets"]["cash_usd_max"]),
    }


def _m1_bundles() -> list[str]:
    return [
        NOTIONAL_ENTRY_BUNDLE[NOTIONAL_10_USD],
        NOTIONAL_REVERSE_BUNDLE[NOTIONAL_10_USD],
        NOTIONAL_ENTRY_BUNDLE[NOTIONAL_100_USD],
        NOTIONAL_REVERSE_BUNDLE[NOTIONAL_100_USD],
    ]


def run_m1_successor_preflight(
    *,
    root: Path,
    predecessor_readback: Mapping[str, Any],
    predecessor_schedule: Mapping[str, Any],
    m1_campaign_request: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Compose and check the M1 successor. Zero network, zero mutation."""

    _require(isinstance(predecessor_readback, Mapping), "PREDECESSOR_READBACK_MISSING")
    _require(isinstance(predecessor_schedule, Mapping), "PREDECESSOR_SCHEDULE_MISSING")
    _require(isinstance(m1_campaign_request, Mapping), "M1_CAMPAIGN_REQUEST_INVALID")

    # --- Readback gating (fail closed) ---------------------------------
    activation_state = str(predecessor_readback.get("activation_state") or "")
    if activation_state != "ACTIVE":
        return _blocked(
            "PREDECESSOR_READBACK_NOT_ACTIVE",
            observed_activation_state=activation_state or None,
        )
    readback_digest = str(
        predecessor_readback.get("schedule_sha256") or ""
    )
    registered_digest = str(predecessor_schedule.get("schedule_sha256") or "")
    if not readback_digest or readback_digest != registered_digest:
        # Recompute when the caller passed an unhashed document.
        try:
            registered_digest = compute_schedule_sha256(predecessor_schedule)
        except ObservationScheduleError:
            return _blocked("PREDECESSOR_SCHEDULE_MISSING")
        if readback_digest and readback_digest != registered_digest:
            return _blocked(
                "PREDECESSOR_IDENTITY_MISMATCH",
                readback_schedule_sha256=readback_digest or None,
                predecessor_schedule_sha256=registered_digest,
            )

    # --- Campaign request bounds ---------------------------------------
    try:
        target_members = int(m1_campaign_request["target_members"])
        campaign_days = int(m1_campaign_request["campaign_days"])
    except (KeyError, TypeError, ValueError):
        return _blocked("M1_CAMPAIGN_REQUEST_INVALID")
    if target_members < MIN_M1_TARGET_MEMBERS or target_members > MAX_M1_TARGET_MEMBERS:
        return _blocked("M1_CAMPAIGN_REQUEST_INVALID")
    if campaign_days < 1 or campaign_days > 30:
        return _blocked("M1_CAMPAIGN_REQUEST_INVALID")
    inclusion_probability = str(
        m1_campaign_request.get("inclusion_probability", "1.0")
    )

    # --- Conservation baseline -----------------------------------------
    predecessor_semantics = _collect_semantics(predecessor_schedule)

    # --- Compose successor ---------------------------------------------
    successor = deepcopy(dict(predecessor_schedule))
    successor.pop("schedule_sha256", None)
    successor["schedule_key"] = (
        f"{predecessor_schedule['schedule_key']}-{M1_SUCCESSOR_KEY_SUFFIX}"
    )
    successor["activation"] = {
        "starts_at": render_utc(now.astimezone(UTC)),
        "stops_admitting_at": render_utc(
            now.astimezone(UTC) + timedelta(days=campaign_days)
        ),
        "cadence_alignment": predecessor_schedule["activation"]["cadence_alignment"],
    }
    # Additive M1: attach the four USDC bundles to the decision-time X point
    # only (X eligibility gates the M1 primary denominator; Y horizons and
    # every other semantic are preserved untouched).
    x_id = predecessor_semantics["x_point_id"]
    added_bundles_by_point: dict[str, list[str]] = {x_id: []}
    m1_bundles = _m1_bundles()
    for point in [successor["x_point"]]:
        point_id = str(point["point_id"])
        bundles = [str(item) for item in point["bundle_ids"]]
        candidate_ids = bundles + [
            item for item in m1_bundles if item not in bundles
        ]
        if len(candidate_ids) > MAX_BUNDLES_PER_POINT:
            return _blocked(
                "M1_BUNDLE_CAPACITY_GAP",
                point_id=point_id,
                existing_bundles=len(bundles),
                needed_bundles=len(candidate_ids),
                max_bundles_per_point=MAX_BUNDLES_PER_POINT,
            )
        point["bundle_ids"] = candidate_ids
        added_bundles_by_point[point_id] = [
            item for item in candidate_ids if item not in bundles
        ]
    # Successor must still validate and compile under current semantics.
    try:
        validated = validate_observation_schedule(successor, root=root)
        digest = compute_schedule_sha256(validated)
        validated["schedule_sha256"] = digest
    except ObservationScheduleError as exc:
        return _blocked(
            "SUCCESSOR_COMPILE_FAILED",
            compile_error=str(exc),
        )
    compiled = compile_schedule_document(validated, root=root)
    if compiled.terminal != "SCHEDULE_ACTIVATION_REQUIRED":
        return _blocked(
            "SUCCESSOR_COMPILE_FAILED",
            compiler_terminal=compiled.terminal,
            compiler_reason_codes=list(compiled.reason_codes),
        )

    # --- Budget envelope -------------------------------------------------
    per_member_day = M1_CALLS_PER_MEMBER_MAX * target_members
    lifetime = per_member_day * campaign_days
    declared_day = int(validated["budgets"]["provider_calls_per_utc_day_max"])
    declared_life = int(validated["budgets"]["provider_calls_lifetime_max"])
    if declared_day < per_member_day or declared_life < lifetime:
        return _blocked(
            "M1_PROVIDER_BUDGET_GAP",
            m1_incremental_per_utc_day_max=per_member_day,
            m1_incremental_lifetime_max=lifetime,
            declared_per_utc_day_max=declared_day,
            declared_lifetime_max=declared_life,
        )

    # --- Conservation verification ---------------------------------------
    successor_semantics = _collect_semantics(validated)
    preserved_keys = [
        "source_poll",
        "population",
        "missingness",
        "disappearance",
        "retention",
        "authority",
        "outputs",
    ]
    semantic_diff: dict[str, Any] = {"changed": [], "added_m1_bundles_by_point": added_bundles_by_point}
    for key in preserved_keys:
        if successor_semantics[key] != predecessor_semantics[key]:
            return _blocked("SUCCESSOR_SEMANTIC_CONSERVATION_FAILED", semantic_key=key)
    if successor_semantics["x_point_id"] != predecessor_semantics["x_point_id"]:
        return _blocked("SUCCESSOR_SEMANTIC_CONSERVATION_FAILED", semantic_key="x_point_id")
    if successor_semantics["x_point_offset"] != predecessor_semantics["x_point_offset"]:
        return _blocked("SUCCESSOR_SEMANTIC_CONSERVATION_FAILED", semantic_key="x_point_offset")
    if successor_semantics["y_points"] != predecessor_semantics["y_points"][: len(successor_semantics["y_points"])]:
        return _blocked("SUCCESSOR_SEMANTIC_CONSERVATION_FAILED", semantic_key="y_points")
    semantic_diff["changed"] = [
        "schedule_key",
        "activation",
        "x_point.bundle_ids",
    ]

    # --- Sampling proposal ------------------------------------------------
    sampling_proposal = {
        "policy": validated["sampling"]["policy"],
        "seed": validated["sampling"]["seed"],
        "inclusion_probability": inclusion_probability,
        "target_members": target_members,
        "max_members_per_utc_day": int(validated["sampling"]["max_members_per_utc_day"]),
    }

    # --- Authority material (reuses lifecycle builder) ---------------------
    try:
        authority = build_authority_request(root=root, document=validated)
    except ObservationScheduleError as exc:
        return _blocked(
            "SUCCESSOR_AUTHORITY_MATERIAL_FAILED",
            authority_error=str(exc),
        )

    cutover_start = parse_utc(validated["activation"]["starts_at"])
    cutover_proposal = {
        "predecessor_schedule_sha256": registered_digest,
        "predecessor_activation_id": str(
            predecessor_readback.get("activation_id") or ""
        ) or None,
        "successor_schedule_sha256": digest,
        "cutover_at": render_utc(cutover_start),
        "mechanism": "EXISTING_ROLLOVER_LIFECYCLE",
        "requires_owner_authorization": True,
    }
    return {
        "schema": "smial.m1-successor-preflight",
        "schema_version": M1_PREFLIGHT_SCHEMA_VERSION,
        "capability_id": M1_CAPABILITY_ID,
        "terminal": "M1_SUCCESSOR_PREFLIGHT_COMPATIBLE",
        "compatible": True,
        "proposed_successor": {
            "schedule_key": str(validated["schedule_key"]),
            "schedule_sha256": digest,
            "activation": deepcopy(validated["activation"]),
            "document": validated,
        },
        "semantic_diff": semantic_diff,
        "sampling_proposal": sampling_proposal,
        "provider_call_envelope": {
            "m1_calls_per_member_max": M1_CALLS_PER_MEMBER_MAX,
            "m1_incremental_per_utc_day_max": per_member_day,
            "m1_incremental_lifetime_max": lifetime,
            "resulting_declared_per_utc_day_max": declared_day,
            "resulting_declared_lifetime_max": declared_life,
        },
        "cutover_proposal": cutover_proposal,
        "authority_request_material": authority,
        "network_calls": 0,
        "runtime_mutations": 0,
    }


__all__ = [
    "M1_PREFLIGHT_SCHEMA_VERSION",
    "M1SuccessorPreflightError",
    "PREFLIGHT_BLOCKERS",
    "run_m1_successor_preflight",
]
