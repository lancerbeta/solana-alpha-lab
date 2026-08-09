"""Fail-closed offline packet for a future Birdeye V3 pair-history pilot."""

from __future__ import annotations

from typing import Any, Mapping


EXPECTED_DECISION = "OFFLINE_PACKET_READY_FOR_OWNER_AUTHORITY_GATE"
EXPECTED_FUTURE_READ_IDS = (
    "PAIR_OVERVIEW_IDENTITY_READ",
    "PAIR_OHLCV_RANGE_READ",
)
FORBIDDEN_CREDENTIAL_KEYS = {
    "api_key",
    "api_key_value",
    "authorization",
    "token",
    "secret",
    "password",
}


class BirdeyeV3PairHistoryPilotError(ValueError):
    """Raised when the offline packet drifts into external-provider activity."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BirdeyeV3PairHistoryPilotError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _list(value: object, code: str) -> list[Any]:
    _require(isinstance(value, list), code)
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


def _require_exact_read(
    read: Mapping[str, Any],
    *,
    read_id: str,
    endpoint_path: str,
    query: Mapping[str, Any],
    prior_condition: str | None,
) -> None:
    _require(read.get("read_id") == read_id, "REQUEST_SHAPE_DRIFT")
    _require(read.get("method") == "GET", "REQUEST_SHAPE_DRIFT")
    _require(read.get("endpoint_path") == endpoint_path, "REQUEST_SHAPE_DRIFT")
    _require(read.get("header_policy") == {
        "x_chain": "solana",
        "credential_transport": "LOCAL_HEADER_ONLY_NO_VALUE",
    }, "REQUEST_SHAPE_DRIFT")
    _require(read.get("query") == query, "REQUEST_SHAPE_DRIFT")
    _require(read.get("max_attempts") == 1, "RETRY_OR_FALLBACK_FORBIDDEN")
    _require(read.get("fallback_provider") is None, "RETRY_OR_FALLBACK_FORBIDDEN")
    _require(read.get("stop_chain_on_non_200") is True, "SEQUENCE_GUARD_DRIFT")
    _require(read.get("execute_only_if_prior") == prior_condition, "SEQUENCE_GUARD_DRIFT")
    _require(
        read.get("raw_retention") == "OUTSIDE_GIT_A4_IF_LATER_AUTHORIZED",
        "RAW_DATA_FORBIDDEN",
    )


def evaluate_birdeye_v3_pair_history_pilot(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate the sole permitted result for the offline Birdeye owner packet."""
    _require(not _contains_credential_key(policy), "CREDENTIAL_DISCLOSURE_FORBIDDEN")
    _require(
        policy.get("schema") == "smial.task30.birdeye-v3-pair-history-pilot.policy",
        "SCHEMA_DRIFT",
    )
    _require(policy.get("schema_version") == "1.0", "SCHEMA_VERSION_DRIFT")
    _require(policy.get("task_id") == "TASK-30", "TASK_ID_DRIFT")
    _require(
        policy.get("atom_id") == "T30-A5_BOUNDED_BIRDEYE_V3_PAIR_HISTORY_PILOT_PREPARATION_V1",
        "ATOM_ID_DRIFT",
    )
    _require(
        policy.get("contract_id") == "TASK30-BIRDEYE-V3-PAIR-HISTORY-PILOT-V1",
        "CONTRACT_ID_DRIFT",
    )
    _require(
        policy.get("consumer") == "FUTURE_EXACT_OWNER_EXTERNAL_READ_GATE",
        "CONSUMER_DRIFT",
    )

    identity = _mapping(policy.get("frozen_identity"), "IDENTITY_REQUIRED")
    _require(identity == {
        "network": "solana",
        "pool_address": "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
        "base_mint": "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK",
        "quote_mint": "So11111111111111111111111111111111111111112",
        "dex_id": "pumpswap",
        "source_receipt": "docs/evidence/task27/a1_stage_a_public_pair_identity_runtime_receipt_v1.json",
    }, "IDENTITY_DRIFT")

    authority = _mapping(policy.get("authority"), "AUTHORITY_REQUIRED")
    _require(
        authority == {
            "provider_api_rpc_wss_calls": 0,
            "credential_use": False,
            "raw_data_write": False,
            "r2_r3_access": False,
            "dependency_changes": False,
            "wallet_signer_transaction_actions": False,
            "cash_spend": False,
            "task30_trial_or_acceptance": False,
            "project_sources_changes": False,
        },
        "EXTERNAL_AUTHORITY_FORBIDDEN",
    )
    owner_authority = _mapping(policy.get("owner_authority"), "OWNER_AUTHORITY_REQUIRED")
    _require(owner_authority.get("status") == "NOT_GRANTED", "OWNER_AUTHORITY_DRIFT")
    _require(
        owner_authority.get("future_request_cap") == 2,
        "OWNER_AUTHORITY_DRIFT",
    )
    local_credential_presence = _mapping(
        policy.get("local_credential_presence"), "CREDENTIAL_PRESENCE_REQUIRED"
    )
    _require(
        local_credential_presence.get("status") == "UNATTESTED",
        "CREDENTIAL_PRESENCE_DRIFT",
    )

    future_reads = _list(policy.get("future_reads"), "FUTURE_READS_REQUIRED")
    _require(len(future_reads) == 2, "FUTURE_REQUEST_CAP_DRIFT")
    first = _mapping(future_reads[0], "FUTURE_READ_REQUIRED")
    second = _mapping(future_reads[1], "FUTURE_READ_REQUIRED")
    _require_exact_read(
        first,
        read_id=EXPECTED_FUTURE_READ_IDS[0],
        endpoint_path="/defi/v3/pair/overview/single",
        query={
            "address": "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
            "ui_amount_mode": "raw",
        },
        prior_condition=None,
    )
    _require_exact_read(
        second,
        read_id=EXPECTED_FUTURE_READ_IDS[1],
        endpoint_path="/defi/v3/ohlcv/pair",
        query={
            "address": "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
            "type": "15m",
            "time_from": 1786100400,
            "time_to": 1786186800,
            "mode": "range",
            "padding": True,
            "outlier": True,
            "inversion": False,
        },
        prior_condition="IDENTITY_READ_HTTP_200",
    )

    semantic_state = _mapping(policy.get("semantic_state"), "SEMANTIC_STATE_REQUIRED")
    _require(
        semantic_state == {
            "rest_15m_enum": "UNPROVEN_PENDING_RESPONSE",
            "birdeye_pair_indexing": "UNPROVEN_PENDING_RESPONSE",
            "price_unit": "UNPROVEN_PENDING_RESPONSE",
            "empty_interval_meaning": "UNPROVEN_PENDING_RESPONSE",
            "panel_completeness": "UNPROVEN_PENDING_RESPONSE",
            "pit_admissibility": "UNPROVEN",
        },
        "SEMANTIC_PROMOTION_FORBIDDEN",
    )
    non_claims = _mapping(policy.get("non_claims"), "NON_CLAIMS_REQUIRED")
    for field in (
        "continuous_panel",
        "explicit_no_trade",
        "pit_admissible",
        "alpha",
        "task30_trial",
        "numeric_netreturn",
        "execution",
        "actual_fills",
        "settlement",
    ):
        _require(non_claims.get(field) is False, "PROMOTION_CLAIM_FORBIDDEN")

    _require(policy.get("decision") == EXPECTED_DECISION, "DECISION_PROMOTION_FORBIDDEN")
    _require(
        policy.get("project_sources_disposition") == "NO_CHANGE",
        "SOURCE_DISPOSITION_DRIFT",
    )

    return {
        "decision": EXPECTED_DECISION,
        "future_external_authority": "NOT_GRANTED",
        "future_request_cap": 2,
        "future_read_ids": list(EXPECTED_FUTURE_READ_IDS),
        "project_sources_disposition": "NO_CHANGE",
    }
