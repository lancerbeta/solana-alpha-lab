"""Fail-closed offline decision for the TASK-30 Birdeye route and future panel."""

from __future__ import annotations

from typing import Any, Mapping


EXPECTED_DECISION = "HOLD_BIRDEYE_ROUTE_PREPARE_FORWARD_CAPTURE_CANDIDATE"
EXPECTED_NEXT_BOUNDARY = "EXACT_PROVIDER_SELECTION_AND_24H_CAPTURE_GATE_REQUIRED"
FROZEN_POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
EXPECTED_OBSERVATION_TIME_FIELDS = [
    "slot_open_at",
    "slot_close_at",
    "observed_at",
    "ingested_at",
    "request_identity",
    "response_hash",
    "provider_response_timestamp_if_present",
    "terminal_state",
]
EXPECTED_ADOPT = [
    "CONTENT_ADDRESSED_RAW_MANIFESTS",
    "IDEMPOTENT_SLOT_IDENTITY",
    "PHYSICAL_CAPS",
    "TYPED_GAPS",
    "RECOVERY_AND_DAILY_HEALTH",
]
EXPECTED_FORBIDDEN_REUSE = [
    "JUPITER_QUOTE_VALUES",
    "TASK21_TECHNICAL_PROBE_AS_ADMISSION",
    "TASK21_PROVIDER_ENDPOINT",
    "TASK21_EXECUTION_CAPACITY_RUN_PLAN",
]
FORBIDDEN_CREDENTIAL_KEYS = {
    "api_key",
    "api_key_value",
    "authorization",
    "token",
    "secret",
    "password",
}


class BirdeyeRouteHoldForwardCaptureError(ValueError):
    """Raised when the offline route-hold decision is widened or contradicted."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BirdeyeRouteHoldForwardCaptureError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _contains_credential_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key.lower() in FORBIDDEN_CREDENTIAL_KEYS:
                return True
            if _contains_credential_key(child):
                return True
    if isinstance(value, (list, tuple)):
        return any(_contains_credential_key(item) for item in value)
    return False


def evaluate_birdeye_route_hold_forward_capture(
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the sole permitted offline hold-and-forward-capture decision."""
    _require(
        config.get("schema") == "smial.task30.birdeye-route-hold-forward-capture.policy",
        "SCHEMA_DRIFT",
    )
    _require(config.get("schema_version") == "1.0", "SCHEMA_VERSION_DRIFT")
    _require(config.get("task_id") == "TASK-30", "TASK_ID_DRIFT")
    _require(
        config.get("atom_id")
        == "T30-A6_BIRDEYE_ROUTE_HOLD_AND_FORWARD_PRICE_CAPTURE_DECISION_V1",
        "ATOM_ID_DRIFT",
    )
    _require(
        config.get("contract_id")
        == "TASK30-BIRDEYE-ROUTE-HOLD-FORWARD-CAPTURE-DECISION-V1",
        "CONTRACT_ID_DRIFT",
    )
    _require(
        config.get("consumer") == "FUTURE_TASK30_FORWARD_PRICE_CAPTURE_ENTRY_GATE",
        "CONSUMER_DRIFT",
    )
    _require(config.get("evidence_as_of") == "2026-08-10", "EVIDENCE_AS_OF_DRIFT")
    _require(not _contains_credential_key(config), "CREDENTIAL_DISCLOSURE_FORBIDDEN")

    route = _mapping(config.get("birdeye_route"), "BIRDEYE_ROUTE_REQUIRED")
    _require(route.get("state") == "HOLD_NO_AUTORETRY", "BIRDEYE_AUTORETRY_FORBIDDEN")
    _require(
        route.get("observed_ohlcv_http_status") == 429
        and not isinstance(route.get("observed_ohlcv_http_status"), bool),
        "BIRDEYE_RUNTIME_EVIDENCE_DRIFT",
    )
    _require(route.get("historical_panel_claim") is False, "PROMOTION_CLAIM_FORBIDDEN")
    _require(
        route.get("provider_or_pair_unsupported_claim") is False,
        "PROVIDER_REJECTION_PROMOTION_FORBIDDEN",
    )
    _require(
        route.get("reopen_requires")
        == [
            "DOCUMENTED_QUOTA_OR_ACCESS_RECOVERY",
            "NEW_EXACT_OWNER_EXTERNAL_AUTHORIZATION",
        ],
        "BIRDEYE_REOPEN_GATE_DRIFT",
    )

    candidate = _mapping(
        config.get("forward_capture_candidate"), "FORWARD_CAPTURE_CANDIDATE_REQUIRED"
    )
    _require(candidate.get("pool_address") == FROZEN_POOL, "POOL_EXPANSION_FORBIDDEN")
    _require(
        candidate.get("slot_seconds") == 900
        and not isinstance(candidate.get("slot_seconds"), bool),
        "CADENCE_DRIFT",
    )
    _require(
        candidate.get("initial_horizon_seconds") == 86400
        and not isinstance(candidate.get("initial_horizon_seconds"), bool),
        "HORIZON_DRIFT",
    )
    _require(
        candidate.get("max_observation_slots") == 96
        and not isinstance(candidate.get("max_observation_slots"), bool),
        "SLOT_CAP_DRIFT",
    )
    _require(
        candidate.get("provider_selection") == "NOT_SELECTED",
        "PROVIDER_PROMOTION_FORBIDDEN",
    )
    _require(
        candidate.get("scheduler_state") == "PLANNED_NOT_BUILT",
        "SCHEDULER_ACTIVATION_FORBIDDEN",
    )
    _require(
        candidate.get("candle_label_policy")
        == "RETAIN_AS_RECEIVED_NO_START_END_PROMOTION",
        "CANDLE_LABEL_PROMOTION_FORBIDDEN",
    )
    _require(
        candidate.get("missing_slot_policy") == "RETAIN_TYPED_GAP_NO_BACKFILL",
        "MISSING_SLOT_PROMOTION_FORBIDDEN",
    )
    _require(
        candidate.get("observation_time_fields") == EXPECTED_OBSERVATION_TIME_FIELDS,
        "OBSERVATION_TIME_FIELDS_DRIFT",
    )

    reuse = _mapping(config.get("reuse_boundary"), "REUSE_BOUNDARY_REQUIRED")
    _require(reuse.get("adopt") == EXPECTED_ADOPT, "REUSE_ADOPT_DRIFT")
    _require(
        reuse.get("forbidden_reuse") == EXPECTED_FORBIDDEN_REUSE,
        "REUSE_FORBIDDEN_BOUNDARY_DRIFT",
    )

    authority = _mapping(config.get("authority"), "AUTHORITY_REQUIRED")
    _require(
        authority.get("provider_api_rpc_wss_calls") == 0
        and not isinstance(authority.get("provider_api_rpc_wss_calls"), bool),
        "EXTERNAL_AUTHORITY_FORBIDDEN",
    )
    _require(
        authority.get("cash_spend_usd_cents") == 0
        and not isinstance(authority.get("cash_spend_usd_cents"), bool),
        "CASH_AUTHORITY_FORBIDDEN",
    )
    _require(
        authority.get("scheduler_or_background_process") is False,
        "SCHEDULER_ACTIVATION_FORBIDDEN",
    )
    for field in (
        "credential_use",
        "raw_data_write",
        "dependency_changes",
        "wallet_signer_transaction_actions",
        "task30_trial_or_acceptance",
        "project_sources_changes",
    ):
        _require(authority.get(field) is False, "EXTERNAL_AUTHORITY_FORBIDDEN")

    non_claims = _mapping(config.get("non_claims"), "NON_CLAIMS_REQUIRED")
    for field in (
        "continuous_panel_claim",
        "pit_admissible_claim",
        "explicit_no_trade_claim",
        "provider_selected_claim",
        "scheduler_running_claim",
        "alpha_claim",
        "numeric_netreturn_claim",
    ):
        _require(non_claims.get(field) is False, "PROMOTION_CLAIM_FORBIDDEN")

    _require(config.get("decision") == EXPECTED_DECISION, "DECISION_PROMOTION_FORBIDDEN")
    _require(
        config.get("next_boundary") == EXPECTED_NEXT_BOUNDARY,
        "NEXT_BOUNDARY_PROMOTION_FORBIDDEN",
    )
    _require(
        config.get("project_sources_disposition") == "NO_CHANGE",
        "SOURCE_DISPOSITION_DRIFT",
    )

    return {
        "decision": EXPECTED_DECISION,
        "birdeye_route_state": "HOLD_NO_AUTORETRY",
        "forward_capture_candidate": {
            "pool_address": FROZEN_POOL,
            "slot_seconds": 900,
            "initial_horizon_seconds": 86400,
            "max_observation_slots": 96,
            "provider_selection": "NOT_SELECTED",
            "scheduler_state": "PLANNED_NOT_BUILT",
        },
        "next_boundary": EXPECTED_NEXT_BOUNDARY,
        "project_sources_disposition": "NO_CHANGE",
    }
