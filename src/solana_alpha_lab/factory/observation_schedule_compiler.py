"""Compile ExperimentSpec v1.2 observation requests into ObservationSchedule v1.0."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.observation_panel_coverage import (
    CoverageIndex,
    compute_evidence_role,
    resolve_authoritative_hypothesis_registered_at,
)
from solana_alpha_lab.factory.observation_primitive_registry import (
    ObservationPrimitiveRegistry,
    PrimitiveRegistryError,
    load_observation_primitive_registry,
)
from solana_alpha_lab.factory.observation_schedule import (
    MAX_OFFSET_SECONDS,
    ObservationScheduleError,
    parse_utc,
    schedule_from_observation_request,
    schedule_sha256,
    validate_observation_schedule,
)

COMPILER_TERMINALS = (
    "PANEL_REUSE_READY",
    "ATTACHED_TO_ACTIVE_SCHEDULE",
    "SCHEDULE_ACTIVATION_REQUIRED",
    "NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED",
    "CHANGE_LANE_PRIMITIVE_GAP",
    "CHANGE_LANE_ESTIMATOR_GAP",
    "CHANGE_LANE_SAFETY_CONTRACT_GAP",
    "BLOCKED_BUDGET",
    "BLOCKED_AUTHORITY",
    "DENY_OUTCOME_LEAKAGE",
    "DENY_RETROACTIVE_MUTATION",
    "DENY_UNSAFE_RUNTIME_CODE",
)

Y_FIELD_CLASSES = frozenset({"Y_TIME"})


@dataclass(frozen=True, slots=True)
class BudgetEnvelope:
    discovery_calls: int
    batch_snapshot_calls: int
    x_point_calls: int
    y_point_calls: int
    provider_calls_per_tick_max: int
    provider_calls_per_utc_day_max: int
    provider_calls_lifetime_max: int
    modeled_credits_per_utc_day_max: int
    raw_bytes_per_utc_day_max: int
    canonical_bytes_lifetime_max: int
    min_raw_retention_days: int
    max_members_per_utc_day: int
    latest_final_due_offset_seconds: int


@dataclass(frozen=True, slots=True)
class CompilerResult:
    terminal: str
    reason_codes: tuple[str, ...]
    schedule: dict[str, Any] | None
    schedule_sha256: str | None
    covering_schedule_sha256: str | None
    snapshot_sha256: str | None
    evidence_role: str | None
    budget: BudgetEnvelope | None
    next_action: str
    hypothesis_registered_at: datetime | None = None
    experiment_as_of: datetime | None = None
    classifier_evaluated_at: datetime | None = None


def _deny(terminal: str, *reasons: str) -> CompilerResult:
    return CompilerResult(
        terminal=terminal,
        reason_codes=reasons or (terminal,),
        schedule=None,
        schedule_sha256=None,
        covering_schedule_sha256=None,
        snapshot_sha256=None,
        evidence_role=None,
        budget=None,
        next_action="STOP",
    )


def _compute_budget(
    schedule: Mapping[str, Any],
    registry: ObservationPrimitiveRegistry,
) -> BudgetEnvelope:
    members = int(schedule["sampling"]["max_members_per_utc_day"])
    discovery = registry.require_primitive(str(schedule["source_poll"]["primitive_id"]))
    starts_at = parse_utc(str(schedule["activation"]["starts_at"]))
    stops_at = parse_utc(str(schedule["activation"]["stops_admitting_at"]))
    period_seconds = max(1, int(schedule["source_poll"]["period_seconds"]))
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    period_micros = period_seconds * 1_000_000
    start_micros = int((starts_at - epoch).total_seconds() * 1_000_000)
    stop_micros = int((stops_at - epoch).total_seconds() * 1_000_000)
    start_tick = math.ceil(start_micros / period_micros)
    last_tick = (stop_micros - 1) // period_micros
    discovery_slots = max(0, last_tick - start_tick + 1)
    if discovery_slots:
        first_slot = epoch + timedelta(seconds=start_tick * period_seconds)
        last_slot = epoch + timedelta(seconds=last_tick * period_seconds)
        admission_days = (last_slot.date() - first_slot.date()).days + 1
    else:
        admission_days = 0
    poll_enabled = bool(schedule.get("source_poll", {}).get("enabled", True))
    if not poll_enabled:
        discovery_slots = 0
    discovery_calls = discovery_slots * int(discovery["call_cost"]["calls_per_request"])
    max_slots_per_utc_day = min(
        discovery_slots,
        (86400 + period_seconds - 1) // period_seconds,
    )
    discovery_calls_per_day = max_slots_per_utc_day * int(
        discovery["call_cost"]["calls_per_request"]
    )
    batch_calls = 0
    x_calls = 0
    y_calls = 0
    member_calls_per_admission_day = 0
    point_primitives: list[tuple[Mapping[str, Any], int]] = []
    for point in [schedule["x_point"], *schedule["y_points"]]:
        for bundle_id in point["bundle_ids"]:
            bundle = registry.require_bundle(str(bundle_id))
            primitive = registry.require_primitive(str(bundle["primitive_id"]))
            if primitive["kind"] == "BATCH_SNAPSHOT":
                requests = math.ceil(
                    members / max(1, int(primitive["max_batch_size"]))
                )
            else:
                requests = members
            calls = requests * int(primitive["call_cost"]["calls_per_request"])
            point_primitives.append((primitive, calls))
            if primitive["kind"] == "BATCH_SNAPSHOT":
                batch_calls += calls
            elif str(point["point_id"]) == str(schedule["x_point"]["point_id"]):
                x_calls += calls
            else:
                y_calls += calls
            member_calls_per_admission_day += calls

    def credits_for(primitive: Mapping[str, Any], requests: int) -> int:
        model = primitive.get("modeled_credit_cost") or {}
        if model.get("status") != "ACCEPTED":
            raise ObservationScheduleError("PROVIDER_CREDIT_MODEL_UNPROVED")
        return int(model["credits_per_request"]) * requests

    credits = credits_for(discovery, discovery_calls_per_day)
    for primitive, calls in point_primitives:
        credits += credits_for(primitive, calls)
    per_day = discovery_calls_per_day + member_calls_per_admission_day
    lifetime = discovery_calls + member_calls_per_admission_day * admission_days
    max_y = int(schedule["y_points"][-1]["due_offset_seconds"])
    return BudgetEnvelope(
        discovery_calls=discovery_calls_per_day,
        batch_snapshot_calls=batch_calls,
        x_point_calls=x_calls,
        y_point_calls=y_calls,
        provider_calls_per_tick_max=min(60, per_day),
        provider_calls_per_utc_day_max=per_day,
        provider_calls_lifetime_max=lifetime,
        modeled_credits_per_utc_day_max=credits,
        raw_bytes_per_utc_day_max=int(schedule["budgets"]["raw_bytes_per_utc_day_max"]),
        canonical_bytes_lifetime_max=int(
            schedule["budgets"]["canonical_bytes_lifetime_max"]
        ),
        min_raw_retention_days=math.ceil(max_y / 86400) + 7,
        max_members_per_utc_day=members,
        latest_final_due_offset_seconds=max_y,
    )


def _resolve_registered(
    schedule: Mapping[str, Any],
    registry: ObservationPrimitiveRegistry,
) -> None:
    registry.require_field(str(schedule["population"]["entity_key_field_id"]))
    registry.require_field(str(schedule["population"]["anchor_field_id"]))
    registry.require_primitive(str(schedule["source_poll"]["primitive_id"]))
    registry.require_query_profile(
        str(schedule["source_poll"]["query_profile_id"]),
        str(schedule["source_poll"]["primitive_id"]),
    )
    authority_profile = registry.require_authority_profile(
        str(schedule["authority"]["profile_id"])
    )
    used_primitive_ids = [str(schedule["source_poll"]["primitive_id"])]
    for point in [schedule["x_point"], *list(schedule["y_points"])]:
        for bundle_id in point["bundle_ids"]:
            used_primitive_ids.append(
                str(registry.require_bundle(str(bundle_id))["primitive_id"])
            )
    used_routes = {
        str(route)
        for primitive_id in set(used_primitive_ids)
        for route in registry.require_primitive(primitive_id)["provider_route_ids"]
    }
    allowed_routes = {
        str(route) for route in authority_profile.get("allowed_route_ids") or []
    }
    if not used_routes.issubset(allowed_routes):
        raise ObservationScheduleError("BLOCKED_AUTHORITY")
    for predicate in schedule["population"]["source_predicates"]:
        field = registry.require_field(str(predicate["field_id"]))
        if field["availability_class"] in Y_FIELD_CLASSES or field["availability_class"] == "X_TIME":
            raise ObservationScheduleError("DENY_OUTCOME_LEAKAGE")
    for predicate in schedule["population"]["x_eligibility_predicates"]:
        field = registry.require_field(str(predicate["field_id"]))
        if field["availability_class"] in Y_FIELD_CLASSES:
            raise ObservationScheduleError("DENY_OUTCOME_LEAKAGE")
    for bundle_id in list(schedule["x_point"]["bundle_ids"]):
        registry.require_bundle(str(bundle_id))
    for point in schedule["y_points"]:
        for bundle_id in point["bundle_ids"]:
            registry.require_bundle(str(bundle_id))


def _budget_fits(declared: Mapping[str, Any], envelope: BudgetEnvelope) -> bool:
    return (
        int(declared["provider_calls_per_tick_max"]) >= envelope.provider_calls_per_tick_max
        and int(declared["provider_calls_per_utc_day_max"])
        >= envelope.provider_calls_per_utc_day_max
        and int(declared["provider_calls_lifetime_max"])
        >= envelope.provider_calls_lifetime_max
        and int(declared["modeled_provider_credits_per_utc_day_max"])
        >= envelope.modeled_credits_per_utc_day_max
        and int(declared["raw_bytes_per_utc_day_max"]) >= envelope.raw_bytes_per_utc_day_max
        and int(declared["canonical_bytes_lifetime_max"])
        >= envelope.canonical_bytes_lifetime_max
    )


def _compiler_result(
    *,
    terminal: str,
    reason_codes: tuple[str, ...],
    schedule: dict[str, Any] | None,
    schedule_sha256: str | None,
    covering_schedule_sha256: str | None,
    snapshot_sha256: str | None,
    evidence_role: str | None,
    budget: BudgetEnvelope | None,
    next_action: str,
    hypothesis_registered_at: datetime | None,
    experiment_as_of: datetime | None,
    classifier_evaluated_at: datetime | None,
) -> CompilerResult:
    return CompilerResult(
        terminal=terminal,
        reason_codes=reason_codes,
        schedule=schedule,
        schedule_sha256=schedule_sha256,
        covering_schedule_sha256=covering_schedule_sha256,
        snapshot_sha256=snapshot_sha256,
        evidence_role=evidence_role,
        budget=budget,
        next_action=next_action,
        hypothesis_registered_at=hypothesis_registered_at,
        experiment_as_of=experiment_as_of,
        classifier_evaluated_at=classifier_evaluated_at,
    )


def compile_observation_request(
    spec: Mapping[str, Any],
    *,
    root,
    coverage: CoverageIndex | None = None,
    hypothesis_registered_at: datetime | None = None,
    closed_family: bool = False,
    data_root=None,
    now: datetime | None = None,
    hypothesis_version_id: str | None = None,
    hypothesis_definition_sha256: str | None = None,
) -> CompilerResult:
    try:
        request = spec["observation_request"]
        if not isinstance(request, Mapping):
            return _deny("DENY_UNSAFE_RUNTIME_CODE")
        if request.get("estimator_id"):
            return _deny("CHANGE_LANE_ESTIMATOR_GAP", "ESTIMATOR_NOT_RUNTIME")
        document = schedule_from_observation_request(request)
        registry = load_observation_primitive_registry(root)
        registry.verify_implementation_hashes()
        validated = validate_observation_schedule(document, root=root)
        _resolve_registered(validated, registry)
        envelope = _compute_budget(validated, registry)
        if not _budget_fits(validated["budgets"], envelope):
            return _deny("BLOCKED_BUDGET")
        digest = str(validated["schedule_sha256"])
        mode = str(request["collection_mode"])
        cutoff = parse_utc(spec["availability_cutoff"])
        experiment_as_of = parse_utc(spec["as_of"])
        classifier_evaluated_at = now.astimezone(UTC) if now is not None else experiment_as_of
        if classifier_evaluated_at.tzinfo is None:
            return _deny("DENY_UNSAFE_RUNTIME_CODE")
        registered_at = hypothesis_registered_at
        if registered_at is None and data_root is not None:
            registered_at = resolve_authoritative_hypothesis_registered_at(
                data_root,
                hypothesis_version_id=hypothesis_version_id
                or (str(spec["hypothesis_version"]) if spec.get("hypothesis_version") else None),
                hypothesis_definition_sha256=hypothesis_definition_sha256,
            )
        due_rows: list[dict[str, Any]] = []
        if data_root is not None:
            from solana_alpha_lab.factory.observation_panel_coverage import (
                SCIENTIFIC_CLOSED_DUE_STATES,
                UNRESOLVED_REQUIRED_DUE_STATES,
                load_coverage_from_rdp,
            )
            from solana_alpha_lab.factory.observation_schedule_store import (
                ObservationScheduleStore,
            )

            index = load_coverage_from_rdp(data_root)
            sqlite_path = Path(data_root) / "observation_schedule_state.sqlite"
            if sqlite_path.is_file():
                store = ObservationScheduleStore(sqlite_path)
                try:
                    due_rows = store.due_in_states(
                        tuple(
                            SCIENTIFIC_CLOSED_DUE_STATES
                            | UNRESOLVED_REQUIRED_DUE_STATES
                            | {"BLOCKED_BUDGET"}
                        )
                    )
                finally:
                    store.close()
        else:
            index = coverage or CoverageIndex()
        snapshot_record = index.covering_snapshot_record(
            validated,
            cutoff,
            data_root=data_root,
            due_rows=due_rows,
        )
        y_proven = False
        first_y = None
        if snapshot_record is not None and data_root is not None:
            from solana_alpha_lab.factory.observation_panel_coverage import (
                derive_first_y_available_at,
            )

            covering_digest = str(
                snapshot_record["schedule"].get("schedule_sha256")
                or schedule_sha256(snapshot_record["schedule"])
            )
            first_y, y_proven = derive_first_y_available_at(data_root, covering_digest)
        role = compute_evidence_role(
            hypothesis_registered_at=registered_at,
            first_admission_at=parse_utc(validated["activation"]["starts_at"]),
            first_y_available_at=first_y if isinstance(first_y, datetime) else None,
            closed_or_consumed=closed_family,
            y_availability_proven=y_proven if snapshot_record is not None else True,
        )
        if snapshot_record is not None and mode in {"REUSE_ONLY", "REUSE_OR_SCHEDULE"}:
            covering_digest = str(
                snapshot_record["schedule"].get("schedule_sha256")
                or schedule_sha256(snapshot_record["schedule"])
            )
            return _compiler_result(
                terminal="PANEL_REUSE_READY",
                reason_codes=(),
                schedule=validated,
                schedule_sha256=digest,
                covering_schedule_sha256=covering_digest,
                snapshot_sha256=str(snapshot_record["snapshot_sha256"]),
                evidence_role=role,
                budget=envelope,
                next_action="BIND_PANEL_SNAPSHOT",
                hypothesis_registered_at=registered_at,
                experiment_as_of=experiment_as_of,
                classifier_evaluated_at=classifier_evaluated_at,
            )
        if mode == "REUSE_ONLY":
            return _deny("BLOCKED_BUDGET", "NO_COVERING_SNAPSHOT")
        active = index.covering_active_schedule(validated, now=classifier_evaluated_at)
        if active is not None:
            return _compiler_result(
                terminal="ATTACHED_TO_ACTIVE_SCHEDULE",
                reason_codes=(),
                schedule=validated,
                schedule_sha256=digest,
                covering_schedule_sha256=active,
                snapshot_sha256=None,
                evidence_role=role,
                budget=envelope,
                next_action="ATTACH_HYPOTHESIS_BINDING",
                hypothesis_registered_at=registered_at,
                experiment_as_of=experiment_as_of,
                classifier_evaluated_at=classifier_evaluated_at,
            )
        predecessor = index.admission_overlap_predecessor(validated)
        if predecessor is not None and predecessor != digest:
            return _compiler_result(
                terminal="NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED",
                reason_codes=("FORWARD_ROLLOVER",),
                schedule=validated,
                schedule_sha256=digest,
                covering_schedule_sha256=predecessor,
                snapshot_sha256=None,
                evidence_role=role,
                budget=envelope,
                next_action="AUTHORIZE_SUCCESSOR_SCHEDULE",
                hypothesis_registered_at=registered_at,
                experiment_as_of=experiment_as_of,
                classifier_evaluated_at=classifier_evaluated_at,
            )
        return _compiler_result(
            terminal="SCHEDULE_ACTIVATION_REQUIRED",
            reason_codes=(),
            schedule=validated,
            schedule_sha256=digest,
            covering_schedule_sha256=None,
            snapshot_sha256=None,
            evidence_role=role,
            budget=envelope,
            next_action="AUTHORIZE_COMPILED_SCHEDULE",
            hypothesis_registered_at=registered_at,
            experiment_as_of=experiment_as_of,
            classifier_evaluated_at=classifier_evaluated_at,
        )
    except PrimitiveRegistryError as exc:
        code = str(exc)
        if code in {"BLOCKED_AUTHORITY"}:
            return _deny(code)
        if code == "IMPLEMENTATION_HASH_DRIFT":
            return _deny("CHANGE_LANE_PRIMITIVE_GAP", code)
        return _deny("CHANGE_LANE_PRIMITIVE_GAP", code)
    except ObservationScheduleError as exc:
        code = str(exc)
        if code in COMPILER_TERMINALS:
            return _deny(code)
        if code == "PROVIDER_CREDIT_MODEL_UNPROVED":
            return _deny("BLOCKED_AUTHORITY", code)
        if code in {
            "OBSERVATION_SCHEDULE_SCHEMA_INVALID",
            "CHANGE_LANE_SAFETY_CONTRACT_GAP",
        }:
            return _deny("CHANGE_LANE_SAFETY_CONTRACT_GAP", code)
        if code == "DENY_UNSAFE_RUNTIME_CODE":
            return _deny("DENY_UNSAFE_RUNTIME_CODE")
        if code == "DENY_OUTCOME_LEAKAGE":
            return _deny("DENY_OUTCOME_LEAKAGE")
        if code == "BLOCKED_BUDGET":
            return _deny("BLOCKED_BUDGET")
        return _deny("CHANGE_LANE_SAFETY_CONTRACT_GAP", code)


def compile_schedule_document(document: Mapping[str, Any], *, root) -> CompilerResult:
    spec = {
        "observation_request": {
            **dict(document),
            "collection_mode": "SCHEDULE_ONLY",
            "requested_evidence_role": "EXPLORATORY_REUSE",
        },
        "availability_cutoff": document["activation"]["starts_at"],
        "as_of": document["activation"]["starts_at"],
    }
    spec["observation_request"]["schedule_key"] = document["schedule_key"]
    return compile_observation_request(spec, root=root)


__all__ = [
    "BudgetEnvelope",
    "COMPILER_TERMINALS",
    "CompilerResult",
    "compile_observation_request",
    "compile_schedule_document",
    "schedule_sha256",
]
