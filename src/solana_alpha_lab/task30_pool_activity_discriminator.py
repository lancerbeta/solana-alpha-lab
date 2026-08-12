"""Fail-closed offline discriminator for the frozen TASK-30 A15P window."""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from solders.rpc.responses import GetSignaturesForAddressResp


POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
REQUEST_ID = "task30-a16-pool-activity-discriminator"
START_FLOOR = 1786526872
ACKNOWLEDGEMENT_FLOOR = 1786526873
TERMINAL_FLOOR = 1786527473
PAGE_LIMIT = 1000


class PoolActivityDiscriminatorError(ValueError):
    """Raised when the offline policy widens or drifts."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PoolActivityDiscriminatorError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _require_exact(value: object, expected: object, code: str) -> None:
    _require(type(value) is type(expected) and value == expected, code)


def _require_keys(
    value: Mapping[str, Any], expected: frozenset[str], code: str
) -> None:
    _require(frozenset(value) == expected, code)


def _require_exact_mapping(
    value: object, expected: Mapping[str, object], code: str
) -> Mapping[str, Any]:
    candidate = _mapping(value, code)
    _require_keys(candidate, frozenset(expected), code)
    for field, expected_value in expected.items():
        _require_exact(candidate.get(field), expected_value, code)
    return candidate


def _contains_secret_or_url(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str) and key.casefold() in {
                "api_key",
                "apikey",
                "authorization",
                "secret",
                "token",
            }:
                return True
            if _contains_secret_or_url(nested):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_or_url(item) for item in value)
    if isinstance(value, str):
        lowered = value.casefold()
        return any(
            marker in lowered
            for marker in ("://", "api_key=", "api-key=", "bearer ")
        )
    return False


def evaluate_pool_activity_policy(config: Mapping[str, Any]) -> dict[str, object]:
    """Validate the complete zero-authority policy using type-strict equality."""

    _require_keys(
        config,
        frozenset(
            {
                "schema",
                "schema_version",
                "task_id",
                "atom_id",
                "contract_id",
                "consumer",
                "upstream_evidence_id",
                "target",
                "capture_window",
                "request",
                "runtime_limits",
                "execution_controls",
                "authority",
                "owner_authority",
                "decision",
                "project_sources_disposition",
            }
        ),
        "POLICY_FIELDS_DRIFT",
    )
    for field, expected in {
        "schema": "smial.task30.pool-activity-discriminator.policy",
        "schema_version": "1.0",
        "task_id": "TASK-30",
        "atom_id": "T30-A16_ONE_BOUNDED_POOL_ACTIVITY_DISCRIMINATOR_V1",
        "contract_id": "TASK30-POOL-ACTIVITY-DISCRIMINATOR-V1",
        "consumer": "RC001-H07-H01-LIQUIDITY-RETENTION",
        "upstream_evidence_id": "T30-A15P-STANDARD-POOL-LOGS-RUNTIME-001",
        "decision": "OFFLINE_DISCRIMINATOR_READY_FOR_OWNER_GATE",
        "project_sources_disposition": "NO_CHANGE",
    }.items():
        _require_exact(config.get(field), expected, "POLICY_IDENTITY_DRIFT")

    target = _require_exact_mapping(
        config.get("target"),
        {
            "network": "solana",
            "pool_address": POOL,
            "base_mint": "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK",
            "quote_mint": "So11111111111111111111111111111111111111112",
            "dex_id": "pumpswap",
        },
        "TARGET_DRIFT",
    )
    window = _require_exact_mapping(
        config.get("capture_window"),
        {
            "started_at": "2026-08-12T09:27:52.749910Z",
            "subscription_acknowledged_at": "2026-08-12T09:27:53.436278Z",
            "terminal_at": "2026-08-12T09:37:53.059095Z",
            "start_floor_unix": START_FLOOR,
            "acknowledgement_floor_unix": ACKNOWLEDGEMENT_FLOOR,
            "terminal_floor_unix": TERMINAL_FLOOR,
        },
        "CAPTURE_WINDOW_DRIFT",
    )
    request = _require_exact_mapping(
        config.get("request"),
        {
            "provider": "HELIUS_STANDARD_RPC",
            "jsonrpc": "2.0",
            "id": REQUEST_ID,
            "method": "getSignaturesForAddress",
            "commitment": "confirmed",
            "limit": PAGE_LIMIT,
        },
        "REQUEST_DRIFT",
    )
    limits = _require_exact_mapping(
        config.get("runtime_limits"),
        {
            "max_requests": 1,
            "estimated_credit_cap": 1,
            "transaction_followups": 0,
        },
        "RUNTIME_LIMIT_DRIFT",
    )
    controls = _require_exact_mapping(
        config.get("execution_controls"),
        {
            "monitoring_owner": "LOCAL_WORK_CODEX_FOREGROUND",
            "retention_class": "A4",
            "retry": False,
            "fallback": False,
            "scheduler": False,
        },
        "EXECUTION_CONTROL_DRIFT",
    )
    authority = _require_exact_mapping(
        config.get("authority"),
        {
            "provider_api_rpc_wss_calls": 0,
            "credential_read": False,
            "raw_external_data_write": False,
            "cash_spend_usd": 0,
            "wallet_signer_transaction_actions": 0,
            "task30_trial_or_acceptance": False,
        },
        "AUTHORITY_NOT_ZERO",
    )
    owner = _mapping(config.get("owner_authority"), "OWNER_AUTHORITY_REQUIRED")
    _require_keys(
        owner,
        frozenset({"future_runtime_authorized", "future_runtime_phrase"}),
        "OWNER_AUTHORITY_FIELDS_DRIFT",
    )
    _require_exact(
        owner.get("future_runtime_authorized"), False, "RUNTIME_AUTHORITY_FORBIDDEN"
    )
    expected_phrase = (
        "T30-A16P_POOL_ACTIVITY_DISCRIMINATOR_RUNTIME_V1; "
        f"pool={POOL}; provider=HELIUS_STANDARD_RPC; "
        "method=getSignaturesForAddress; "
        "capture_started_at=2026-08-12T09:27:52.749910Z; "
        "capture_terminal_at=2026-08-12T09:37:53.059095Z; "
        "max_requests=1; limit=1000; commitment=confirmed; "
        "estimated_credit_cap=1; retention=A4; retry=false; fallback=false; "
        "transaction_followups=0"
    )
    _require_exact(
        owner.get("future_runtime_phrase"), expected_phrase, "OWNER_PHRASE_DRIFT"
    )
    _require(not _contains_secret_or_url(config), "SECRET_OR_URL_DISCLOSURE_FORBIDDEN")

    return {
        "pool_address": target["pool_address"],
        "started_at": window["started_at"],
        "terminal_at": window["terminal_at"],
        "method": request["method"],
        "max_requests": limits["max_requests"],
        "transaction_followups": limits["transaction_followups"],
        "retry": controls["retry"],
        "provider_calls_authorized": authority["provider_api_rpc_wss_calls"],
    }


def build_pool_activity_request(config: Mapping[str, Any]) -> dict[str, object]:
    """Build only the secret-free JSON-RPC body; no transport is performed."""

    evaluate_pool_activity_policy(config)
    return {
        "jsonrpc": "2.0",
        "id": REQUEST_ID,
        "method": "getSignaturesForAddress",
        "params": [POOL, {"commitment": "confirmed", "limit": PAGE_LIMIT}],
    }


def _result(state: str, *, count: int = 0) -> dict[str, object]:
    unknown = state.endswith("_UNKNOWN")
    observed = state == "POOL_ADDRESS_ACTIVITY_OBSERVED_ROUTE_REVIEW_REQUIRED"
    return {
        "terminal_state": state,
        "unknown": unknown,
        "interior_signature_count": count,
        "pool_address_activity_observed": observed,
        "pool_inactive": False,
        "pumpswap_trade": False,
        "price": False,
        "volume": False,
        "zero_volume": False,
        "empty_interval": False,
        "interval_complete": False,
        "pit_admissible": False,
        "task30_trial": False,
        "task30_acceptance": False,
        "numeric_netreturn": False,
    }


@lru_cache(maxsize=256)
def _pinned_transaction_error_is_valid(encoded_error: str) -> bool:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": [
            {
                "signature": "1" * 64,
                "slot": 1,
                "err": json.loads(encoded_error),
                "memo": None,
                "blockTime": 1,
                "confirmationStatus": "confirmed",
            }
        ],
    }
    try:
        GetSignaturesForAddressResp.from_json(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    except Exception:
        # solders exposes its Rust serde failure as a non-exported exception;
        # any parser failure is conservatively schema drift for this classifier.
        return False
    return True


def _valid_transaction_error(value: object) -> bool:
    if isinstance(value, Mapping) and frozenset(value) == frozenset({"InstructionError"}):
        instruction_error = value["InstructionError"]
        if (
            type(instruction_error) is not list
            or len(instruction_error) != 2
            or type(instruction_error[0]) is not int
            or not 0 <= instruction_error[0] <= 0xFF
        ):
            return False
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return False
    return _pinned_transaction_error_is_valid(encoded)


def _valid_record(record: object) -> bool:
    if not isinstance(record, Mapping):
        return False
    if frozenset(record) != frozenset(
        {"signature", "slot", "err", "memo", "blockTime", "confirmationStatus"}
    ):
        return False
    signature = record.get("signature")
    slot = record.get("slot")
    memo = record.get("memo")
    block_time = record.get("blockTime")
    status = record.get("confirmationStatus")
    if type(signature) is not str or not signature:
        return False
    if type(slot) is not int or slot < 0:
        return False
    if memo is not None and type(memo) is not str:
        return False
    if block_time is not None and (type(block_time) is not int or block_time < 0):
        return False
    if not _valid_transaction_error(record.get("err")):
        return False
    if type(status) is not str or status not in {"confirmed", "finalized"}:
        return False
    return True


def classify_pool_activity_response(
    config: Mapping[str, Any], response: object
) -> dict[str, object]:
    """Classify one already-captured response without external side effects."""

    evaluate_pool_activity_policy(config)
    if not isinstance(response, Mapping):
        return _result("MALFORMED_OR_RPC_ERROR_UNKNOWN")
    keys = frozenset(response)
    if keys == frozenset({"jsonrpc", "id", "error"}):
        if (
            type(response.get("jsonrpc")) is str
            and response.get("jsonrpc") == "2.0"
            and type(response.get("id")) is str
            and response.get("id") == REQUEST_ID
            and isinstance(response.get("error"), Mapping)
        ):
            return _result("MALFORMED_OR_RPC_ERROR_UNKNOWN")
        return _result("MALFORMED_OR_RPC_ERROR_UNKNOWN")
    if keys != frozenset({"jsonrpc", "id", "result"}):
        return _result("MALFORMED_OR_RPC_ERROR_UNKNOWN")
    if (
        type(response.get("jsonrpc")) is not str
        or response.get("jsonrpc") != "2.0"
        or type(response.get("id")) is not str
        or response.get("id") != REQUEST_ID
        or type(response.get("result")) is not list
    ):
        return _result("MALFORMED_OR_RPC_ERROR_UNKNOWN")

    records = response["result"]
    if len(records) > PAGE_LIMIT or any(not _valid_record(item) for item in records):
        return _result("ORDERING_OR_SCHEMA_DRIFT_UNKNOWN")

    signatures = [item["signature"] for item in records]
    if len(signatures) != len(set(signatures)):
        return _result("ORDERING_OR_SCHEMA_DRIFT_UNKNOWN")
    slots = [item["slot"] for item in records]
    if any(
        newer < older
        for newer, older in zip(slots, slots[1:])
    ):
        return _result("ORDERING_OR_SCHEMA_DRIFT_UNKNOWN")
    slot_times: dict[int, int | None] = {}
    for item in records:
        slot = item["slot"]
        block_time = item["blockTime"]
        if slot in slot_times and slot_times[slot] != block_time:
            return _result("ORDERING_OR_SCHEMA_DRIFT_UNKNOWN")
        slot_times[slot] = block_time

    interior = [
        item
        for item in records
        if item["blockTime"] is not None
        and ACKNOWLEDGEMENT_FLOOR < item["blockTime"] < TERMINAL_FLOOR
    ]
    if interior:
        return _result(
            "POOL_ADDRESS_ACTIVITY_OBSERVED_ROUTE_REVIEW_REQUIRED",
            count=len(interior),
        )
    if any(item["blockTime"] is None for item in records):
        return _result("NULL_BLOCK_TIME_UNKNOWN")
    if any(
        item["blockTime"]
        in {ACKNOWLEDGEMENT_FLOOR, TERMINAL_FLOOR}
        for item in records
    ):
        return _result("BOUNDARY_TIME_AMBIGUOUS_UNKNOWN")
    if records and records[-1]["blockTime"] < ACKNOWLEDGEMENT_FLOOR:
        return _result("NO_DIRECT_POOL_ACTIVITY_SUPPORTED")
    if len(records) == PAGE_LIMIT:
        return _result("PAGE_TRUNCATED_UNKNOWN")
    return _result("HISTORY_COVERAGE_UNKNOWN")
