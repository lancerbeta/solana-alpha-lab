"""Closed offline policy and same-window classifier for TASK-30 A17."""

from __future__ import annotations

import json
import math
import re
import urllib.parse
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from .lifecycle_discovery_transport import BoundProbeRequest, HttpCapture, WssCapture
from .provider_route_capability_registry_v2 import resolve_provider_route_v2


POPCAT_MINT = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
WSOL_MINT = "So11111111111111111111111111111111111111112"
DISCOVERY_ROUTE_ID = "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001"
RPC_ROUTE_ID = "HELIUS-SOLANA-GET-SIGNATURES-001"
WSS_ROUTE_ID = "HELIUS-SOLANA-LOGS-SUBSCRIBE-001"
WSS_REQUEST_ID = "task30-a17-pool-logs-subscribe"
RPC_REQUEST_ID = "task30-a17-pool-activity"
OWNER_RUNTIME_PHRASE = (
    "T30-A17P_ACTIVE_POOL_ROUTE_YIELD_RUNTIME_V1; "
    f"token={POPCAT_MINT}; dex=orca; quote={WSOL_MINT}; "
    "monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND; max_dexscreener_gets=1; "
    "max_wss_connections=1; max_subscriptions=1; max_open_seconds=180; "
    "max_notifications=1; max_stream_bytes=300000; conditional_rpc_requests=1; "
    "rpc_limit=1000; estimated_helius_credit_cap=8; retention=A4; retry=false; "
    "reconnect=false; fallback=false; transaction_followups=0"
)

_BASE58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_ROOT = frozenset(
    {
        "schema", "schema_version", "task_id", "atom_id", "contract_id",
        "consumer", "spec_route", "upstream_evidence_ids", "route_registry", "discovery", "stream",
        "reconciliation", "runtime_limits", "execution_controls", "authority",
        "owner_authority", "terminal_outcomes", "replan", "decision",
        "project_sources_disposition",
    }
)


class ActivePoolRouteYieldError(ValueError):
    """The A17 policy, target or retained capture is unsafe or ambiguous."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ActivePoolRouteYieldError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _exact(value: object, expected: object, code: str) -> None:
    _require(type(value) is type(expected) and value == expected, code)


def _closed(value: object, expected: Mapping[str, object], code: str) -> Mapping[str, Any]:
    candidate = _mapping(value, code)
    _require(frozenset(candidate) == frozenset(expected), code)
    for key, expected_value in expected.items():
        _exact(candidate.get(key), expected_value, code)
    return candidate


def evaluate_active_pool_route_yield_policy(
    config: Mapping[str, Any], registry: Mapping[str, Any]
) -> dict[str, object]:
    """Validate the complete zero-authority A17 policy and route bindings."""

    _require(frozenset(config) == _ROOT, "ROOT_FIELDS_DRIFT")
    for key, expected in {
        "schema": "smial.task30.active-pool-route-yield.policy",
        "schema_version": "1.0",
        "task_id": "TASK-30",
        "atom_id": "T30-A17_ACTIVE_POOL_ROUTE_YIELD_DISCRIMINATOR_V1",
        "contract_id": "TASK30-ACTIVE-POOL-ROUTE-YIELD-V1",
        "consumer": "RC001-H07-H01-LIQUIDITY-RETENTION",
        "spec_route": "DESIGN_SPEC",
        "decision": "OFFLINE_ACTIVE_POOL_ROUTE_YIELD_READY_FOR_OWNER_GATE",
        "project_sources_disposition": "NO_CHANGE",
    }.items():
        _exact(config.get(key), expected, "ROOT_VALUE_DRIFT")
    _exact(
        config.get("upstream_evidence_ids"),
        [
            "T30-A15P-STANDARD-POOL-LOGS-RUNTIME-001",
            "T30-A16P-POOL-ACTIVITY-DISCRIMINATOR-RUNTIME-002",
            "T30-A16R1-PROVIDER-ROUTE-CAPABILITY-REGISTRY-001",
        ],
        "UPSTREAM_EVIDENCE_DRIFT",
    )
    _closed(
        config.get("route_registry"),
        {
            "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-002",
            "schema_version": "2.0",
            "path": "configs/provider_route_capability_registry_v2.yaml",
        },
        "ROUTE_REGISTRY_DRIFT",
    )
    discovery = _closed(
        config.get("discovery"),
        {
            "route_id": DISCOVERY_ROUTE_ID,
            "provider": "DEXSCREENER",
            "network": "solana",
            "operation": "PUBLIC_TOKEN_PAIR_DISCOVERY",
            "token_mint": POPCAT_MINT,
            "dex_id": "orca",
            "quote_mint": WSOL_MINT,
            "minimum_m5_transactions": 1,
            "max_requests": 1,
        },
        "DISCOVERY_POLICY_DRIFT",
    )
    stream = _closed(
        config.get("stream"),
        {
            "provider_route_id": WSS_ROUTE_ID,
            "provider": "HELIUS_STANDARD_WSS",
            "method": "logsSubscribe",
            "commitment": "confirmed",
            "stop_after_first_notification": True,
        },
        "STREAM_POLICY_DRIFT",
    )
    reconciliation = _closed(
        config.get("reconciliation"),
        {
            "provider_route_id": RPC_ROUTE_ID,
            "provider": "HELIUS_STANDARD_RPC",
            "method": "getSignaturesForAddress",
            "commitment": "confirmed",
            "limit": 1000,
            "only_after_acknowledged_zero_notification_window": True,
        },
        "RECONCILIATION_POLICY_DRIFT",
    )
    limits = _closed(
        config.get("runtime_limits"),
        {
            "max_discovery_requests": 1,
            "max_wss_connections": 1,
            "max_subscriptions": 1,
            "max_wss_seconds": 180,
            "max_notifications": 1,
            "max_stream_bytes": 300000,
            "max_frame_bytes": 100000,
            "max_rpc_requests": 1,
            "max_rpc_response_bytes": 2000000,
            "estimated_helius_credit_cap": 8,
        },
        "RUNTIME_LIMIT_DRIFT",
    )
    controls = _closed(
        config.get("execution_controls"),
        {
            "monitoring_owner": "LOCAL_WORK_CODEX_FOREGROUND",
            "retention_class": "A4",
            "raw_root": "local/task30_active_pool_route_yield",
            "retry": False,
            "reconnect": False,
            "fallback": False,
            "scheduler": False,
            "transaction_followups": 0,
        },
        "EXECUTION_CONTROL_DRIFT",
    )
    authority = _closed(
        config.get("authority"),
        {
            "provider_api_rpc_wss_calls": 0,
            "credential_read": False,
            "raw_external_data_write": False,
            "cash_spend_usd": 0,
            "wallet_signer_transaction_actions": 0,
            "task30_trial_or_acceptance": False,
        },
        "ZERO_AUTHORITY_REQUIRED",
    )
    owner = _closed(
        config.get("owner_authority"),
        {"future_runtime_authorized": False, "future_runtime_phrase": OWNER_RUNTIME_PHRASE},
        "OWNER_AUTHORITY_DRIFT",
    )
    outcomes = [
        "ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY",
        "ACTIVE_BUT_NO_WSS_YIELD",
        "NO_ACTIVITY_DURING_WINDOW",
        "NO_ACTIVE_TARGET_STOP",
        "TRANSPORT_OR_COVERAGE_UNKNOWN",
    ]
    _exact(config.get("terminal_outcomes"), outcomes, "TERMINAL_OUTCOME_DRIFT")
    replan = _closed(
        config.get("replan"),
        {
            "terminal_atom": True,
            "automatic_suffix_atom": False,
            "allowed_next_decisions": ["PIVOT", "ACCEPT_UNKNOWN", "DEFER", "CLOSE"],
        },
        "REPLAN_POLICY_DRIFT",
    )
    discovery_route = resolve_provider_route_v2(registry, str(discovery["route_id"]))
    _exact(discovery_route.get("provider"), "DEXSCREENER", "DISCOVERY_ROUTE_DRIFT")
    _exact(discovery_route.get("operation"), "PUBLIC_TOKEN_PAIR_DISCOVERY", "DISCOVERY_ROUTE_DRIFT")
    _exact(discovery_route.get("protocol"), "HTTPS_GET", "DISCOVERY_ROUTE_DRIFT")
    _exact(discovery_route.get("access_class"), "KEYLESS", "DISCOVERY_ROUTE_DRIFT")
    stream_route = resolve_provider_route_v2(registry, str(stream["provider_route_id"]))
    _exact(stream_route.get("provider"), "HELIUS", "STREAM_ROUTE_DRIFT")
    _exact(stream_route.get("operation"), "LOGS_SUBSCRIBE_MENTIONS", "STREAM_ROUTE_DRIFT")
    _exact(stream_route.get("protocol"), "WSS_JSON_RPC", "STREAM_ROUTE_DRIFT")
    _exact(stream_route.get("access_class"), "LOCAL_ENV_CREDENTIAL", "STREAM_ROUTE_DRIFT")
    rpc_route = resolve_provider_route_v2(registry, str(reconciliation["provider_route_id"]))
    _exact(rpc_route.get("provider"), "HELIUS", "RPC_ROUTE_DRIFT")
    _exact(rpc_route.get("operation"), "GET_SIGNATURES_FOR_ADDRESS", "RPC_ROUTE_DRIFT")
    _exact(rpc_route.get("protocol"), "HTTPS_POST_JSON_RPC", "RPC_ROUTE_DRIFT")
    _exact(rpc_route.get("access_class"), "LOCAL_ENV_CREDENTIAL", "RPC_ROUTE_DRIFT")
    # Keep names referenced so dead-code cleanup cannot silently remove validation.
    _require(all(value is not None for value in (stream, limits, controls, authority, owner, replan)), "POLICY_SECTION_MISSING")
    return {
        "decision": "OFFLINE_ACTIVE_POOL_ROUTE_YIELD_READY_FOR_OWNER_GATE",
        "external_action_authorized": False,
        "project_sources_disposition": "NO_CHANGE",
        "spec_route": "DESIGN_SPEC",
        "terminal_atom": True,
    }


def _finite_number(value: object) -> float | None:
    if type(value) not in {int, float}:
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def select_active_pool(document: object) -> dict[str, object] | None:
    """Select one current active Orca POPCAT/SOL pool deterministically."""

    if type(document) is not list:
        return None
    candidates: list[dict[str, object]] = []
    for raw in document:
        if not isinstance(raw, Mapping):
            continue
        base = raw.get("baseToken")
        quote = raw.get("quoteToken")
        txns = raw.get("txns")
        liquidity = raw.get("liquidity")
        if not all(isinstance(value, Mapping) for value in (base, quote, txns, liquidity)):
            continue
        m5 = txns.get("m5")  # type: ignore[union-attr]
        if not isinstance(m5, Mapping):
            continue
        buys, sells = m5.get("buys"), m5.get("sells")
        pool = raw.get("pairAddress")
        if (
            raw.get("chainId") != "solana"
            or raw.get("dexId") != "orca"
            or base.get("address") != POPCAT_MINT  # type: ignore[union-attr]
            or quote.get("address") != WSOL_MINT  # type: ignore[union-attr]
            or type(buys) is not int
            or type(sells) is not int
            or buys < 0
            or sells < 0
            or buys + sells < 1
            or type(pool) is not str
            or _BASE58.fullmatch(pool) is None
        ):
            continue
        usd = _finite_number(liquidity.get("usd"))  # type: ignore[union-attr]
        candidates.append(
            {
                "pool_address": pool,
                "base_mint": POPCAT_MINT,
                "quote_mint": WSOL_MINT,
                "dex_id": "orca",
                "m5_transactions": buys + sells,
                "liquidity_usd": 0.0 if usd is None else usd,
            }
        )
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: (
            -int(row["m5_transactions"]),
            -float(row["liquidity_usd"]),
            str(row["pool_address"]),
        )
    )
    return candidates[0]


def _credential(value: object) -> str:
    _require(type(value) is str and value == value.strip(), "CREDENTIAL_VALUE_INVALID")
    _require(8 <= len(value) <= 512 and all(33 <= ord(char) < 127 for char in value), "CREDENTIAL_VALUE_INVALID")
    return value


def _pool(value: object) -> str:
    _require(type(value) is str and _BASE58.fullmatch(value) is not None, "POOL_ADDRESS_INVALID")
    return value


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise ActivePoolRouteYieldError("JSON_VALUE_INVALID") from exc


def _helius_request(request_id: str, body: Mapping[str, object], key: str, transport: str) -> BoundProbeRequest:
    query = urllib.parse.urlencode((("api-key", _credential(key)),))
    headers = (("accept", "application/json"), ("user-agent", "smial-task30-a17/1.0"))
    if transport == "HTTP":
        headers = (("accept", "application/json"), ("content-type", "application/json"), ("user-agent", "smial-task30-a17/1.0"))
    return BoundProbeRequest(
        request_id=request_id,
        provider="HELIUS",
        transport=transport,
        method="POST",
        url=("wss" if transport == "WSS" else "https") + f"://mainnet.helius-rpc.com/?{query}",
        headers=headers,
        body=_canonical(body),
        safe_query_keys=(),
    )


def bind_pool_logs_subscribe(pool: str, api_key: str) -> BoundProbeRequest:
    pool = _pool(pool)
    return _helius_request(
        WSS_REQUEST_ID,
        {"jsonrpc": "2.0", "id": WSS_REQUEST_ID, "method": "logsSubscribe", "params": [{"mentions": [pool]}, {"commitment": "confirmed"}]},
        api_key,
        "WSS",
    )


def bind_pool_activity_request(pool: str, api_key: str) -> BoundProbeRequest:
    pool = _pool(pool)
    return _helius_request(
        RPC_REQUEST_ID,
        {"jsonrpc": "2.0", "id": RPC_REQUEST_ID, "method": "getSignaturesForAddress", "params": [pool, {"commitment": "confirmed", "limit": 1000}]},
        api_key,
        "HTTP",
    )


def _parse_json(body: bytes) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        return json.loads(body, object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None


def _acknowledgement(capture: WssCapture) -> int | None:
    document = _parse_json(capture.acknowledgement)
    if not isinstance(document, Mapping) or frozenset(document) != frozenset({"jsonrpc", "id", "result"}):
        return None
    if document.get("jsonrpc") != "2.0" or document.get("id") != WSS_REQUEST_ID:
        return None
    subscription = document.get("result")
    return subscription if type(subscription) is int and subscription >= 0 else None


def acknowledged_zero_window(capture: WssCapture) -> bool:
    """Return true only for the exact branch allowed to spend the RPC call."""

    return (
        type(capture) is WssCapture
        and capture.terminal_class == "BOUND_REACHED"
        and capture.stop_reason == "ELAPSED_CAP"
        and not capture.notifications
        and capture.acknowledgement_observed_at is not None
        and _acknowledgement(capture) is not None
    )


def _valid_notification(body: bytes, subscription: int) -> bool:
    document = _parse_json(body)
    if not isinstance(document, Mapping) or frozenset(document) != frozenset({"jsonrpc", "method", "params"}):
        return False
    params = document.get("params")
    if document.get("jsonrpc") != "2.0" or document.get("method") != "logsNotification" or not isinstance(params, Mapping):
        return False
    if frozenset(params) != frozenset({"subscription", "result"}) or params.get("subscription") != subscription:
        return False
    result = params.get("result")
    if not isinstance(result, Mapping) or frozenset(result) != frozenset({"context", "value"}):
        return False
    context, value = result.get("context"), result.get("value")
    if not isinstance(context, Mapping) or frozenset(context) != frozenset({"slot"}) or type(context.get("slot")) is not int or context.get("slot", -1) < 0:
        return False
    if not isinstance(value, Mapping) or frozenset(value) != frozenset({"signature", "err", "logs"}):
        return False
    logs = value.get("logs")
    return (
        type(value.get("signature")) is str
        and bool(value.get("signature"))
        and type(logs) is list
        and all(type(line) is str for line in logs)
    )


def _classification(state: str, *, rpc_requests: int, interior: int = 0, bracketed: bool = False) -> dict[str, object]:
    return {
        "terminal_state": state,
        "unknown": state == "TRANSPORT_OR_COVERAGE_UNKNOWN",
        "rpc_requests": rpc_requests,
        "interior_signature_count": interior,
        "window_bracketed": bracketed,
        "route_yield": state == "ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY",
        "price": False,
        "volume": False,
        "zero_volume": False,
        "empty_interval": False,
        "interval_complete": False,
        "pit_admissible": False,
        "task30_trial": False,
        "task30_acceptance": False,
        "numeric_netreturn": False,
        "retry": False,
        "reconnect": False,
        "fallback": False,
        "replan": {
            "required": state != "ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY",
            "terminal_atom": True,
            "automatic_suffix_atom": False,
            "allowed_next_decisions": ["PIVOT", "ACCEPT_UNKNOWN", "DEFER", "CLOSE"],
        },
    }


def classify_route_window(
    config: Mapping[str, Any],
    registry: Mapping[str, Any],
    selection: Mapping[str, object],
    *,
    wss_capture: WssCapture,
    rpc_capture: HttpCapture | None,
    terminal_observed_at: datetime | None = None,
) -> dict[str, object]:
    """Classify one already captured same-window result without external I/O."""

    evaluate_active_pool_route_yield_policy(config, registry)
    limits = _mapping(config.get("runtime_limits"), "RUNTIME_LIMITS_REQUIRED")
    pool = _pool(selection.get("pool_address"))
    _require(selection.get("base_mint") == POPCAT_MINT and selection.get("quote_mint") == WSOL_MINT and selection.get("dex_id") == "orca", "SELECTED_TARGET_DRIFT")
    _require(type(wss_capture) is WssCapture, "WSS_CAPTURE_INVALID")
    stream_bytes = len(wss_capture.acknowledgement) + sum(len(item) for item in wss_capture.notifications)
    _require(stream_bytes <= limits.get("max_stream_bytes", -1), "STREAM_BYTE_CAP_EXCEEDED")
    _require(len(wss_capture.notifications) <= limits.get("max_notifications", -1), "NOTIFICATION_CAP_EXCEEDED")
    if wss_capture.terminal_class != "BOUND_REACHED" or wss_capture.acknowledgement_observed_at is None:
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=0)
    subscription = _acknowledgement(wss_capture)
    if subscription is None:
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=0)
    if wss_capture.notifications:
        if rpc_capture is not None or not all(_valid_notification(body, subscription) for body in wss_capture.notifications):
            return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=0)
        return _classification("ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY", rpc_requests=0)
    if rpc_capture is None:
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=0)
    if rpc_capture.terminal_class != "SUCCESS" or rpc_capture.status_code != 200:
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
    document = _parse_json(rpc_capture.body)
    if not isinstance(document, Mapping) or frozenset(document) != frozenset({"jsonrpc", "id", "result"}):
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
    if document.get("jsonrpc") != "2.0" or document.get("id") != RPC_REQUEST_ID or type(document.get("result")) is not list:
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
    records = document["result"]
    if len(records) > 1000:
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
    times: list[int] = []
    slots: list[int] = []
    signatures: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping) or frozenset(record) != frozenset({"signature", "slot", "err", "memo", "blockTime", "confirmationStatus"}):
            return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
        signature, slot, block_time = record.get("signature"), record.get("slot"), record.get("blockTime")
        if type(signature) is not str or not signature or signature in signatures or type(slot) is not int or slot < 0:
            return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
        if record.get("confirmationStatus") not in {"confirmed", "finalized"} or record.get("memo") is not None and type(record.get("memo")) is not str:
            return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
        if block_time is not None and (type(block_time) is not int or block_time < 0):
            return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
        signatures.add(signature)
        slots.append(slot)
        if block_time is not None:
            times.append(block_time)
    if any(newer < older for newer, older in zip(slots, slots[1:])) or not times:
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
    ack_second = math.floor(wss_capture.acknowledgement_observed_at.timestamp())
    if (
        wss_capture.stop_reason != "ELAPSED_CAP"
        or terminal_observed_at is None
        or terminal_observed_at.tzinfo is None
        or terminal_observed_at <= wss_capture.acknowledgement_observed_at
        or (terminal_observed_at - wss_capture.acknowledgement_observed_at).total_seconds()
        > int(limits["max_wss_seconds"])
    ):
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
    terminal_second = math.floor(terminal_observed_at.timestamp())
    bracketed = max(times) >= terminal_second and min(times) <= ack_second
    if not bracketed:
        return _classification("TRANSPORT_OR_COVERAGE_UNKNOWN", rpc_requests=1)
    interior = sum(ack_second < block_time < terminal_second for block_time in times)
    return _classification(
        "ACTIVE_BUT_NO_WSS_YIELD" if interior else "NO_ACTIVITY_DURING_WINDOW",
        rpc_requests=1,
        interior=interior,
        bracketed=True,
    )
