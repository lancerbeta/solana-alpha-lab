"""Fail-closed reuse decision for TASK-30 historical OHLCV routes."""

from __future__ import annotations

from typing import Any, Mapping


EXPECTED_DECISION = "T30_A0_REUSE_CLOSED_NO_PROVIDER_PILOT"
EXPECTED_NEXT_BOUNDARY = "NEW_NAMED_PROVIDER_CANDIDATE_REQUIRES_ENTRY_GATE"
EXPECTED_ROUTE_STATES = {
    "GECKO_T30_A0": "DOCUMENTED_START_LABEL_CONFLICTS_WITH_RETAINED_BOUNDARY",
    "SOLANA_TRACKER_PAIR": "OBSERVED_INSUFFICIENT_33_OF_96",
    "BIRDEYE_V3_PAIR": "CANDIDATE_NOT_READY",
}
FORBIDDEN_CREDENTIAL_KEYS = {
    "api_key",
    "api_key_value",
    "authorization",
    "token",
    "secret",
    "password",
}


class ReuseFirstHistoryRouteError(ValueError):
    """Raised when a frozen route decision is widened or contradicted."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReuseFirstHistoryRouteError(code)


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


def evaluate_reuse_first_history_route(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate frozen offline evidence and return the sole permitted result."""
    _require(
        config.get("schema") == "smial.task30.reuse-first-pit-history-route.policy",
        "SCHEMA_DRIFT",
    )
    _require(config.get("schema_version") == "1.0", "SCHEMA_VERSION_DRIFT")
    _require(config.get("task_id") == "TASK-30", "TASK_ID_DRIFT")
    _require(
        config.get("atom_id") == "T30-A4_REUSE_FIRST_PIT_HISTORY_ROUTE_DECISION_V1",
        "ATOM_ID_DRIFT",
    )
    _require(
        config.get("contract_id") == "TASK30-REUSE-FIRST-PIT-HISTORY-ROUTE-DECISION-V1",
        "CONTRACT_ID_DRIFT",
    )
    _require(
        config.get("consumer") == "FUTURE_NAMED_PROVIDER_ENTRY_GATE",
        "CONSUMER_DRIFT",
    )
    _require(config.get("evidence_as_of") == "2026-08-09", "EVIDENCE_AS_OF_DRIFT")
    _require(not _contains_credential_key(config), "CREDENTIAL_DISCLOSURE_FORBIDDEN")

    routes = _mapping(config.get("routes"), "ROUTES_REQUIRED")
    _require(set(routes) == set(EXPECTED_ROUTE_STATES), "ROUTE_SET_DRIFT")

    gecko = _mapping(routes.get("GECKO_T30_A0"), "GECKO_ROUTE_REQUIRED")
    _require(
        gecko.get("route_state") == EXPECTED_ROUTE_STATES["GECKO_T30_A0"],
        "GECKO_ROUTE_STATE_DRIFT",
    )
    _require(
        gecko.get("raw_sha256")
        == "cce29d4e175bc81a474c699e3bb465daf8cb864f3cb195a9812bd0d3c0ca4163",
        "GECKO_RAW_BINDING_DRIFT",
    )
    requested_window = _mapping(gecko.get("requested_window"), "GECKO_WINDOW_REQUIRED")
    _require(
        requested_window.get("start") == 1786100400
        and requested_window.get("end_exclusive") == 1786186800,
        "GECKO_WINDOW_DRIFT",
    )
    observed = _mapping(gecko.get("observed_response"), "GECKO_OBSERVED_REQUIRED")
    _require(
        observed.get("first_timestamp") == 1786101300
        and observed.get("newest_timestamp") == 1786186800,
        "GECKO_OBSERVED_BOUNDARY_DRIFT",
    )
    _require(
        observed.get("boundary_conflict") == "OBSERVED_CONFLICT",
        "GECKO_BOUNDARY_CONFLICT_REQUIRED",
    )
    gecko_docs = _mapping(gecko.get("documentation"), "GECKO_DOCUMENTATION_REQUIRED")
    _require(
        gecko_docs.get("url")
        == "https://docs.coingecko.com/reference/pool-ohlcv-contract-address",
        "GECKO_DOCUMENTATION_DRIFT",
    )
    _require(
        gecko_docs.get("candle_timestamp") == "START_OF_INTERVAL_DOCUMENTED"
        and gecko_docs.get("before_timestamp") == "STRICTLY_BEFORE_DOCUMENTED"
        and gecko_docs.get("include_empty_intervals")
        == "PRIOR_CLOSE_OHLC_ZERO_VOLUME_DOCUMENTED",
        "GECKO_DOCUMENTATION_FACT_DRIFT",
    )

    solana_tracker = _mapping(
        routes.get("SOLANA_TRACKER_PAIR"), "SOLANA_TRACKER_ROUTE_REQUIRED"
    )
    _require(
        solana_tracker.get("route_state") == EXPECTED_ROUTE_STATES["SOLANA_TRACKER_PAIR"],
        "SOLANA_TRACKER_ROUTE_STATE_DRIFT",
    )
    _require(
        solana_tracker.get("observed_bars") == 33
        and solana_tracker.get("required_bars") == 96,
        "SOLANA_TRACKER_INSUFFICIENT_SAMPLE_REQUIRED",
    )
    _require(
        solana_tracker.get("documentation_url")
        == "https://docs.solanatracker.io/data-api/chart/get-ohlcv-data-for-a-tokenpool-pair"
        and solana_tracker.get("interval_enum") == "15m_DOCUMENTED"
        and solana_tracker.get("identity_input") == "TOKEN_AND_POOL_DOCUMENTED",
        "SOLANA_TRACKER_DOCUMENTATION_DRIFT",
    )

    birdeye = _mapping(routes.get("BIRDEYE_V3_PAIR"), "BIRDEYE_ROUTE_REQUIRED")
    _require(
        birdeye.get("route_state") == EXPECTED_ROUTE_STATES["BIRDEYE_V3_PAIR"],
        "BIRDEYE_ROUTE_STATE_DRIFT",
    )
    _require(
        birdeye.get("documentation_url")
        == "https://docs.birdeye.so/reference/get-defi-v3-ohlcv-pair"
        and birdeye.get("padding") == "DOCUMENTED",
        "BIRDEYE_DOCUMENTATION_DRIFT",
    )
    _require(
        birdeye.get("rest_15m_enum") == "UNPROVEN"
        and birdeye.get("pair_identity") == "UNPROVEN"
        and birdeye.get("credential_presence") == "UNATTESTED"
        and birdeye.get("owner_call_authority") == "NOT_GRANTED",
        "BIRDEYE_CANDIDATE_PROMOTION_FORBIDDEN",
    )

    authority = _mapping(config.get("authority"), "AUTHORITY_REQUIRED")
    _require(
        authority.get("provider_api_rpc_wss_calls") == 0
        and not isinstance(authority.get("provider_api_rpc_wss_calls"), bool),
        "EXTERNAL_AUTHORITY_FORBIDDEN",
    )
    for field in (
        "credential_use",
        "raw_data_write",
        "r2_r3_access",
        "dependency_changes",
        "wallet_signer_transaction_actions",
        "cash_spend",
        "task30_trial_or_acceptance",
        "project_sources_changes",
    ):
        _require(authority.get(field) is False, "EXTERNAL_AUTHORITY_FORBIDDEN")

    non_claims = _mapping(config.get("non_claims"), "NON_CLAIMS_REQUIRED")
    for field in (
        "continuous_panel_claim",
        "pit_admissible_claim",
        "explicit_no_trade_claim",
        "alpha_claim",
        "strategy_claim",
        "execution_claim",
        "actual_fills_claim",
        "settlement_claim",
        "pnl_claim",
        "numeric_netreturn_claim",
    ):
        _require(non_claims.get(field) is False, "PROMOTION_CLAIM_FORBIDDEN")

    _require(
        config.get("decision") == EXPECTED_DECISION,
        "DECISION_PROMOTION_FORBIDDEN",
    )
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
        "route_states": dict(EXPECTED_ROUTE_STATES),
        "next_boundary": EXPECTED_NEXT_BOUNDARY,
        "project_sources_disposition": "NO_CHANGE",
    }
