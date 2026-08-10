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
