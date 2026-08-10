"""Pure validation for the TASK-30 offline availability-probe policy."""

from collections.abc import Mapping
from typing import Any


class RouteAvailabilityProbeError(ValueError):
    """Raised when a policy weakens a fail-closed probe invariant."""


EXPECTED_GROUP = "RC001-H07-H01-LIQUIDITY-RETENTION"
EXPECTED_PARAMETER = "OBSERVATION_WINDOW_15M"
EXPECTED_OFFSETS = [0, 15, 30, 60]
EXPECTED_HEALTH_FAILURES = [
    "PROCESS_NOT_STARTED",
    "RECEIPT_WRITE_FAILED",
    "PRIOR_MANIFEST_UNREADABLE",
    "MONITORING_LOST",
]
EXPECTED_TERMINAL_DECISIONS = [
    "READY_FOR_FIXED_DELAY_24H_TECHNICAL_CAPTURE",
    "ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE",
    "INCONCLUSIVE",
]


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RouteAvailabilityProbeError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _exact(policy: Mapping[str, Any], key: str, expected: object, code: str) -> None:
    _require(policy.get(key) == expected, code)


def validate_probe_policy(policy: Mapping[str, Any], frozen_group: Mapping[str, Any]) -> None:
    """Fail closed unless the tracked offline probe policy is exact."""

    _exact(policy, "task_id", "TASK-30", "TASK_ID_INVALID")
    _exact(policy, "atom_id", "T30-A11A_ROUTE_AVAILABILITY_PROBE_OFFLINE_V1", "ATOM_ID_INVALID")
    _exact(policy, "frozen_group_id", EXPECTED_GROUP, "FROZEN_GROUP_INVALID")
    _exact(policy, "frozen_parameter_id", EXPECTED_PARAMETER, "FROZEN_PARAMETER_INVALID")
    _exact(policy, "interval_seconds", 900, "INTERVAL_INVALID")
    _exact(policy, "upstream_a10_decision", "START_LABELED", "A10_DECISION_INVALID")

    _exact(frozen_group, "group_id", EXPECTED_GROUP, "FROZEN_GROUP_MISMATCH")
    parameter_policy = _mapping(frozen_group.get("parameter_policy"), "FROZEN_PARAMETER_POLICY_INVALID")
    _require(
        parameter_policy.get("allowed_parameter_ids") == ["OBSERVATION_WINDOW_15M", "NOTIONAL_BUCKET_SET_V1"],
        "FROZEN_PARAMETER_MISMATCH",
    )

    probe_shape = _mapping(policy.get("probe_shape"), "PROBE_SHAPE_REQUIRED")
    _exact(probe_shape, "boundaries", 3, "BOUNDARY_COUNT_INVALID")
    _exact(probe_shape, "offset_seconds", EXPECTED_OFFSETS, "OFFSET_GRID_INVALID")
    _exact(probe_shape, "max_ohlcv_reads", 12, "READ_CAP_INVALID")

    external = _mapping(policy.get("future_external_read"), "FUTURE_EXTERNAL_REQUIRED")
    _exact(external, "selected_provider", None, "PROVIDER_SELECTION_FORBIDDEN")
    for field in ("retry", "fallback", "scheduler"):
        _exact(external, field, False, "FORBIDDEN_EXTERNAL_MODE")
    _exact(external, "raw_retention", "OWNER_PACKET_REQUIRED", "RETENTION_POLICY_INVALID")

    capture_states = _mapping(policy.get("capture_states"), "CAPTURE_STATES_REQUIRED")
    _exact(capture_states, "valid", "VALID_OBSERVATION", "VALID_STATE_INVALID")
    _exact(capture_states, "typed_gap", "TYPED_GAP", "TYPED_GAP_INVALID")
    _exact(capture_states, "health_failures", EXPECTED_HEALTH_FAILURES, "HEALTH_FAILURE_STATES_INVALID")
    _exact(policy, "terminal_decisions", EXPECTED_TERMINAL_DECISIONS, "TERMINAL_DECISIONS_INVALID")

    authority = _mapping(policy.get("authority"), "AUTHORITY_REQUIRED")
    for field in (
        "provider_api_rpc_wss_calls",
        "scheduler_or_background_processes",
        "raw_data_writes",
        "credential_use",
        "r2_r3_access",
        "wallet_signer_transaction_actions",
        "cash_spend_usd_cents",
        "task30_trial_or_acceptance_actions",
    ):
        _exact(authority, field, 0, "FORBIDDEN_AUTHORITY")

    claims = _mapping(policy.get("claims"), "CLAIMS_REQUIRED")
    for field in (
        "technical_route_only",
        "pit_admissible",
        "h07_h01_evidence",
        "task30_trial",
        "execution",
        "numeric_netreturn",
    ):
        _exact(claims, field, False, "PROMOTED_CLAIM_FORBIDDEN")
    _exact(policy, "project_sources_disposition", "NO_CHANGE", "SOURCES_CHANGE_FORBIDDEN")


def _result_claims() -> dict[str, bool]:
    return {
        "technical_route_only": True,
        "pit_admissible": False,
        "h07_h01_evidence": False,
        "task30_trial": False,
        "execution": False,
        "numeric_netreturn": False,
    }


def _result(
    decision: str,
    execution_disposition: str,
    recommended_fixed_delay_seconds: int | None,
    slots: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "decision": decision,
        "execution_disposition": execution_disposition,
        "recommended_fixed_delay_seconds": recommended_fixed_delay_seconds,
        "slots": slots,
        "claims": _result_claims(),
    }


def _records_by_slot(
    policy: Mapping[str, Any],
    records: object,
) -> dict[int, dict[int, Mapping[str, Any]]]:
    _require(isinstance(records, list), "RECORDS_INVALID")
    offsets = _mapping(policy.get("probe_shape"), "PROBE_SHAPE_REQUIRED").get("offset_seconds")
    _require(isinstance(offsets, list), "OFFSET_GRID_INVALID")
    expected_count = _mapping(policy.get("probe_shape"), "PROBE_SHAPE_REQUIRED").get("boundaries")
    _require(isinstance(expected_count, int), "BOUNDARY_COUNT_INVALID")
    _require(len(records) == expected_count * len(offsets), "RECORD_COUNT_INVALID")

    allowed_states = {"VALID_OBSERVATION", "TYPED_GAP", *EXPECTED_HEALTH_FAILURES}
    by_slot: dict[int, dict[int, Mapping[str, Any]]] = {}
    for record in records:
        value = _mapping(record, "RECORD_INVALID")
        slot_start = value.get("slot_start")
        offset_seconds = value.get("offset_seconds")
        capture_state = value.get("capture_state")
        _require(
            isinstance(slot_start, int)
            and not isinstance(slot_start, bool)
            and slot_start >= 0
            and slot_start % 900 == 0,
            "SLOT_START_INVALID",
        )
        _require(offset_seconds in offsets, "OFFSET_OUT_OF_GRID")
        _require(capture_state in allowed_states, "CAPTURE_STATE_INVALID")
        _require(value.get("retry", False) is False, "RETRY_FORBIDDEN")
        _require(value.get("fallback", False) is False, "FALLBACK_FORBIDDEN")
        slot = by_slot.setdefault(slot_start, {})
        _require(offset_seconds not in slot, "DUPLICATE_SLOT_OFFSET")
        slot[offset_seconds] = value

    _require(len(by_slot) == expected_count, "SLOT_COUNT_INVALID")
    ordered_slots = sorted(by_slot)
    _require(
        all(later - earlier == 900 for earlier, later in zip(ordered_slots, ordered_slots[1:])),
        "SLOT_SEQUENCE_INVALID",
    )
    expected_offsets = set(offsets)
    for slot in by_slot.values():
        _require(set(slot) == expected_offsets, "OFFSET_GRID_INCOMPLETE")
    return by_slot


def _valid_observation(record: Mapping[str, Any], slot_start: int) -> tuple[bool, str | None]:
    expected = record.get("expected_interval_start")
    observed = record.get("observed_interval_start")
    fingerprint = record.get("candle_fingerprint")
    _require(
        isinstance(expected, int)
        and not isinstance(expected, bool)
        and isinstance(observed, int)
        and not isinstance(observed, bool)
        and isinstance(fingerprint, str)
        and fingerprint,
        "VALID_OBSERVATION_INVALID",
    )
    return expected == slot_start and observed == slot_start, fingerprint


def evaluate_probe(
    policy: Mapping[str, Any],
    frozen_group: Mapping[str, Any],
    records: object,
) -> dict[str, Any]:
    """Evaluate synthetic probe records without I/O, provider choice or capture."""

    validate_probe_policy(policy, frozen_group)
    by_slot = _records_by_slot(policy, records)
    ordered_offsets = _mapping(policy.get("probe_shape"), "PROBE_SHAPE_REQUIRED")["offset_seconds"]
    _require(isinstance(ordered_offsets, list), "OFFSET_GRID_INVALID")

    if any(
        record.get("capture_state") in EXPECTED_HEALTH_FAILURES
        for slot in by_slot.values()
        for record in slot.values()
    ):
        return _result("INCONCLUSIVE", "STOP_RUN", None, [])

    slot_results: list[dict[str, Any]] = []
    first_visible_offsets: list[int] = []
    for slot_start in sorted(by_slot):
        slot = by_slot[slot_start]
        valid_offsets = [
            offset
            for offset in ordered_offsets
            if slot[offset].get("capture_state") == "VALID_OBSERVATION"
        ]
        if not valid_offsets:
            return _result("INCONCLUSIVE", "CONTINUE", None, [])
        first_visible = valid_offsets[0]
        fingerprint: str | None = None
        for offset in ordered_offsets:
            record = slot[offset]
            state = record.get("capture_state")
            if offset < first_visible:
                _require(state == "TYPED_GAP", "PREPUBLICATION_STATE_INVALID")
                continue
            if state == "TYPED_GAP":
                return _result("INCONCLUSIVE", "CONTINUE", None, [])
            exact_interval, observed_fingerprint = _valid_observation(record, slot_start)
            if not exact_interval:
                return _result("ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE", "CONTINUE", None, [])
            if fingerprint is None:
                fingerprint = observed_fingerprint
            elif observed_fingerprint != fingerprint:
                return _result("ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE", "CONTINUE", None, [])
        first_visible_offsets.append(first_visible)
        slot_results.append(
            {
                "slot_start": slot_start,
                "first_valid_offset_seconds": first_visible,
                "candle_fingerprint": fingerprint,
                "stable_after_first_valid": True,
            }
        )

    return _result(
        "READY_FOR_FIXED_DELAY_24H_TECHNICAL_CAPTURE",
        "CONTINUE",
        max(first_visible_offsets),
        slot_results,
    )
