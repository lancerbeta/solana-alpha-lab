"""Fail-closed offline readiness boundary for a future Birdeye OHLCV pilot."""

from __future__ import annotations

from typing import Any, Mapping


EXPECTED_DECISION = "NOT_READY_FOR_PROVIDER_PILOT"
EXPECTED_BLOCKERS = (
    "BIRDEYE_REST_15M_ENUM_UNPROVEN",
    "BIRDEYE_PAIR_IDENTITY_UNPROVEN",
    "BIRDEYE_API_KEY_LOCAL_PRESENCE_UNATTESTED",
    "OWNER_ONE_CALL_AUTHORITY_NOT_GRANTED",
)
FORBIDDEN_CREDENTIAL_KEYS = {
    "api_key",
    "api_key_value",
    "authorization",
    "token",
    "secret",
    "password",
}


class PilotReadinessError(ValueError):
    """Raised when an offline readiness record widens into provider activity."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PilotReadinessError(code)


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


def evaluate_pilot_readiness(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return the sole permitted result for the unresolved Birdeye readiness state."""
    _require(
        config.get("schema") == "smial.task30.birdeye-pair-ohlcv-pilot-readiness.policy",
        "SCHEMA_DRIFT",
    )
    _require(config.get("schema_version") == "1.0", "SCHEMA_VERSION_DRIFT")
    _require(config.get("task_id") == "TASK-30", "TASK_ID_DRIFT")
    _require(
        config.get("atom_id") == "T30-A3_BIRDEYE_PAIR_OHLCV_PILOT_READINESS_BOUNDARY_V1",
        "ATOM_ID_DRIFT",
    )
    _require(
        config.get("contract_id") == "TASK30-BIRDEYE-PAIR-OHLCV-PILOT-READINESS-V1",
        "CONTRACT_ID_DRIFT",
    )
    _require(
        config.get("consumer") == "FUTURE_EXACT_OWNER_PROVIDER_AUTHORITY_GATE",
        "CONSUMER_DRIFT",
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

    _require(not _contains_credential_key(config), "CREDENTIAL_DISCLOSURE_FORBIDDEN")

    evidence = _mapping(config.get("evidence"), "EVIDENCE_REQUIRED")
    _require(evidence.get("as_of") == "2026-08-09", "EVIDENCE_AS_OF_DRIFT")
    rest = _mapping(
        evidence.get("historical_rest_pair_ohlcv"), "REST_EVIDENCE_REQUIRED"
    )
    _require(
        rest.get("documentation_url")
        == "https://docs.birdeye.so/reference/get-defi-v3-ohlcv-pair",
        "REST_DOCUMENTATION_DRIFT",
    )
    _require(rest.get("time_parameters") == "DOCUMENTED_UNIX_SECONDS", "REST_EVIDENCE_DRIFT")
    _require(rest.get("api_key_requirement") == "DOCUMENTED", "REST_EVIDENCE_DRIFT")
    _require(rest.get("padding_parameter") == "DOCUMENTED", "REST_EVIDENCE_DRIFT")
    _require(
        evidence.get("rest_15m_enum") == "UNPROVEN", "REST_15M_ENUM_UNPROVEN"
    )
    _require(
        evidence.get("websocket_15m") == "OBSERVED_NOT_REST_ADMISSIBLE",
        "WEBSOCKET_NOT_REST_EVIDENCE",
    )

    pair_identity = _mapping(config.get("pair_identity"), "PAIR_IDENTITY_REQUIRED")
    _require(
        pair_identity.get("candidate_pool_address")
        == "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
        "CANDIDATE_POOL_DRIFT",
    )
    _require(pair_identity.get("birdeye_pair_address") is None, "PAIR_IDENTITY_UNPROVEN")
    _require(pair_identity.get("status") == "UNPROVEN", "PAIR_IDENTITY_UNPROVEN")

    credential_probe = _mapping(
        config.get("credential_probe"), "CREDENTIAL_PROBE_REQUIRED"
    )
    _require(
        credential_probe.get("local_presence_attestation") == "UNATTESTED",
        "BIRDEYE_API_KEY_LOCAL_PRESENCE_UNATTESTED",
    )
    owner_authority = _mapping(
        config.get("owner_authority"), "OWNER_AUTHORITY_REQUIRED"
    )
    _require(
        owner_authority.get("one_call_authority") == "NOT_GRANTED",
        "OWNER_ONE_CALL_AUTHORITY_NOT_GRANTED",
    )

    request_shape = _mapping(config.get("request_shape"), "REQUEST_SHAPE_REQUIRED")
    _require(
        request_shape.get("construction") == "FORBIDDEN",
        "REQUEST_CONSTRUCTION_FORBIDDEN",
    )
    _require(request_shape.get("raw_data_path") is None, "RAW_DATA_FORBIDDEN")
    _require(request_shape.get("retry_count") == 0, "RETRY_OR_FALLBACK_FORBIDDEN")
    _require(
        request_shape.get("fallback_provider") is None,
        "RETRY_OR_FALLBACK_FORBIDDEN",
    )
    _require(
        request_shape.get("provider_call_cap") == 0,
        "EXTERNAL_AUTHORITY_FORBIDDEN",
    )

    non_claims = _mapping(config.get("non_claims"), "NON_CLAIMS_REQUIRED")
    for field in (
        "continuous_panel_claim",
        "pit_admissible_claim",
        "alpha_claim",
        "task30_trial_claim",
        "numeric_netreturn_claim",
        "actual_fills_claim",
        "settlement_claim",
    ):
        _require(non_claims.get(field) is False, "PROMOTION_CLAIM_FORBIDDEN")

    _require(
        config.get("decision") == EXPECTED_DECISION,
        "DECISION_PROMOTION_FORBIDDEN",
    )
    _require(
        config.get("required_next_evidence")
        == ["BIRDEYE_REST_15M_ENUM_PROOF", "BIRDEYE_PAIR_IDENTITY_PROOF"],
        "REQUIRED_NEXT_EVIDENCE_DRIFT",
    )
    _require(
        config.get("project_sources_disposition") == "NO_CHANGE",
        "SOURCE_DISPOSITION_DRIFT",
    )

    return {
        "decision": EXPECTED_DECISION,
        "blockers": list(EXPECTED_BLOCKERS),
        "project_sources_disposition": "NO_CHANGE",
    }
