"""Fail-closed cross-endpoint discriminator for TASK-30 A10.

This module deliberately has no network or file-system side effects.  It
validates the two exact public request shapes and compares a decoded OHLCV
response with decoded direct-trade timestamps and prices.
"""

from __future__ import annotations

import math
import urllib.parse
from collections.abc import Mapping
from datetime import UTC, datetime
from numbers import Real
from typing import Any


POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
NETWORK = "solana"
INTERVAL_SECONDS = 900
PUBLIC_BASE_URL = "https://api.geckoterminal.com/api/v2"
EXPECTED_REQUESTS = (
    (
        "OHLCV_15M",
        "/networks/solana/pools/{pool}/ohlcv/minute",
        {
            "aggregate": "15",
            "currency": "usd",
            "token": "base",
            "limit": "96",
            "include_empty_intervals": "false",
            "before_timestamp": "DYNAMIC_CLOSED_BOUNDARY",
        },
    ),
    ("POOL_TRADES", "/networks/solana/pools/{pool}/trades", {"token": "base"}),
)
MODEL_IDS = ("START_LABELED", "END_LABELED")
MIN_USABLE_TRADES = 2
MIN_DISTINCT_SLOTS = 2


class IntervalSemanticsError(ValueError):
    """The policy or response cannot support a safe A10 decision."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise IntervalSemanticsError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _exact_text(mapping: Mapping[str, Any], key: str, expected: str, code: str) -> None:
    _require(mapping.get(key) == expected, code)


def _policy(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    _exact_text(policy, "task_id", "TASK-30", "TASK_ID_INVALID")
    _exact_text(
        policy,
        "atom_id",
        "T30-A10_GECKO_INTERVAL_SEMANTICS_DISCRIMINATOR_V1",
        "ATOM_ID_INVALID",
    )
    _exact_text(policy, "frozen_pool_address", POOL, "POOL_INVALID")
    _exact_text(policy, "network", NETWORK, "NETWORK_INVALID")
    _require(policy.get("interval_seconds") == INTERVAL_SECONDS, "INTERVAL_INVALID")

    authority = _mapping(policy.get("authority"), "AUTHORITY_REQUIRED")
    _require(
        authority.get("provider_api_rpc_wss_calls_max") == 2,
        "EXTERNAL_CALL_CAP_INVALID",
    )
    for field in (
        "credential_use",
        "r2_r3_access",
        "scheduler_or_background_processes",
        "wallet_signer_transaction_actions",
        "task30_trial_or_acceptance",
    ):
        _require(authority.get(field) is False, "FORBIDDEN_AUTHORITY")
    _require(authority.get("cash_spend_usd_cents") == 0, "FORBIDDEN_AUTHORITY")

    external = _mapping(policy.get("external_read"), "EXTERNAL_READ_REQUIRED")
    _exact_text(
        external,
        "provider",
        "GECKOTERMINAL_PUBLIC_KEYLESS",
        "PROVIDER_INVALID",
    )
    _exact_text(external, "public_base_url", PUBLIC_BASE_URL, "PUBLIC_ENDPOINT_INVALID")
    _require(external.get("calls_max") == 2, "REQUEST_COUNT_INVALID")
    for field in ("credentials", "retry", "fallback", "scheduler"):
        _require(external.get(field) is False, "FORBIDDEN_EXTERNAL_MODE")
    return external


def build_request_plan(policy: Mapping[str, Any], *, before_timestamp: int) -> list[dict[str, Any]]:
    """Return the only permitted, sanitized pair of A10 request descriptions."""

    external = _policy(policy)
    _require(
        isinstance(before_timestamp, int)
        and not isinstance(before_timestamp, bool)
        and before_timestamp > INTERVAL_SECONDS
        and before_timestamp % INTERVAL_SECONDS == 0,
        "CLOSED_BOUNDARY_INVALID",
    )
    requests = external.get("requests")
    _require(isinstance(requests, list) and len(requests) == 2, "REQUEST_COUNT_INVALID")

    plan: list[dict[str, Any]] = []
    for request, expected in zip(requests, EXPECTED_REQUESTS, strict=True):
        request_mapping = _mapping(request, "REQUEST_INVALID")
        request_id, template, expected_query = expected
        _exact_text(request_mapping, "request_id", request_id, "REQUEST_ID_INVALID")
        _exact_text(request_mapping, "method", "GET", "REQUEST_METHOD_INVALID")
        _exact_text(request_mapping, "path_template", template, "REQUEST_PATH_INVALID")
        query = _mapping(request_mapping.get("query"), "REQUEST_QUERY_INVALID")
        _require(dict(query) == expected_query, "REQUEST_QUERY_INVALID")
        resolved_query = dict(expected_query)
        if request_id == "OHLCV_15M":
            resolved_query["before_timestamp"] = str(before_timestamp)
        path = "/api/v2" + template.format(pool=POOL)
        url = PUBLIC_BASE_URL + template.format(pool=POOL)
        if resolved_query:
            url += "?" + urllib.parse.urlencode(sorted(resolved_query.items()))
        parsed = urllib.parse.urlsplit(url)
        _require(
            parsed.scheme == "https"
            and parsed.hostname == "api.geckoterminal.com"
            and parsed.port is None
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment,
            "PUBLIC_ENDPOINT_INVALID",
        )
        plan.append(
            {
                "request_id": request_id,
                "method": "GET",
                "host": parsed.hostname,
                "path": path,
                "query": resolved_query,
                "url": url,
                "pool": POOL,
            }
        )
    return plan


def _number(value: object, code: str) -> float:
    if isinstance(value, bool):
        raise IntervalSemanticsError(code)
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise IntervalSemanticsError(code) from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise IntervalSemanticsError(code)
    return parsed


def _ohlcv_bars(payload: Mapping[str, Any]) -> tuple[dict[int, tuple[float, float]], str]:
    try:
        data = _mapping(payload.get("data"), "OHLCV_PAYLOAD_INVALID")
        attributes = _mapping(data.get("attributes"), "OHLCV_PAYLOAD_INVALID")
        rows = attributes.get("ohlcv_list")
        meta = _mapping(payload.get("meta"), "OHLCV_PAYLOAD_INVALID")
        base = _mapping(meta.get("base"), "OHLCV_PAYLOAD_INVALID")
        base_address = base.get("address")
    except IntervalSemanticsError:
        raise
    _require(isinstance(rows, list) and rows, "OHLCV_PAYLOAD_INVALID")
    _require(isinstance(base_address, str) and base_address, "OHLCV_PAYLOAD_INVALID")
    bars: dict[int, tuple[float, float]] = {}
    for row in rows:
        _require(isinstance(row, list) and len(row) == 6, "OHLCV_PAYLOAD_INVALID")
        timestamp = row[0]
        _require(
            isinstance(timestamp, int)
            and not isinstance(timestamp, bool)
            and timestamp >= 0
            and timestamp % INTERVAL_SECONDS == 0
            and timestamp not in bars,
            "OHLCV_PAYLOAD_INVALID",
        )
        high = _number(row[2], "OHLCV_PAYLOAD_INVALID")
        low = _number(row[3], "OHLCV_PAYLOAD_INVALID")
        _require(low <= high, "OHLCV_PAYLOAD_INVALID")
        bars[timestamp] = (low, high)
    return bars, base_address


def _trade_timestamp(value: object) -> int:
    _require(isinstance(value, str), "TRADE_PAYLOAD_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntervalSemanticsError("TRADE_PAYLOAD_INVALID") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "TRADE_PAYLOAD_INVALID")
    return int(parsed.astimezone(UTC).timestamp())


def _trades(payload: Mapping[str, Any], *, base_address: str) -> list[tuple[int, float]]:
    data = payload.get("data")
    _require(isinstance(data, list), "TRADE_PAYLOAD_INVALID")
    parsed: list[tuple[int, float]] = []
    for record in data:
        record_mapping = _mapping(record, "TRADE_PAYLOAD_INVALID")
        attributes = _mapping(record_mapping.get("attributes"), "TRADE_PAYLOAD_INVALID")
        timestamp = _trade_timestamp(attributes.get("block_timestamp"))
        from_address = attributes.get("from_token_address")
        to_address = attributes.get("to_token_address")
        if to_address == base_address:
            price = _number(attributes.get("price_to_in_usd"), "TRADE_PAYLOAD_INVALID")
        elif from_address == base_address:
            price = _number(attributes.get("price_from_in_usd"), "TRADE_PAYLOAD_INVALID")
        else:
            raise IntervalSemanticsError("TRADE_BASE_TOKEN_MISMATCH")
        parsed.append((timestamp, price))
    return parsed


def _in_range(price: float, low: float, high: float) -> bool:
    tolerance = max(1.0, abs(price), abs(low), abs(high)) * 1e-9
    return low - tolerance <= price <= high + tolerance


def _model_metrics(
    model_id: str,
    *,
    bars: Mapping[int, tuple[float, float]],
    trades: list[tuple[int, float]],
) -> dict[str, Any]:
    offset = 0 if model_id == "START_LABELED" else INTERVAL_SECONDS
    usable = 0
    contradictions = 0
    missing_bar = 0
    slots: set[int] = set()
    for timestamp, price in trades:
        slot = timestamp - (timestamp % INTERVAL_SECONDS)
        bar = bars.get(slot + offset)
        if bar is None:
            missing_bar += 1
            continue
        usable += 1
        slots.add(slot)
        if not _in_range(price, *bar):
            contradictions += 1
    return {
        "usable_trades": usable,
        "distinct_slots": len(slots),
        "contradictions": contradictions,
        "missing_mapped_bars": missing_bar,
    }


def evaluate_interval_semantics(
    policy: Mapping[str, Any],
    ohlcv_payload: Mapping[str, Any],
    trades_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the sole A10 technical claim with a fail-closed outcome."""

    _policy(policy)
    bars, base_address = _ohlcv_bars(ohlcv_payload)
    trades = _trades(trades_payload, base_address=base_address)
    metrics = {
        model_id: _model_metrics(model_id, bars=bars, trades=trades)
        for model_id in MODEL_IDS
    }
    viable = [
        model_id
        for model_id, result in metrics.items()
        if result["usable_trades"] >= MIN_USABLE_TRADES
        and result["distinct_slots"] >= MIN_DISTINCT_SLOTS
        and result["contradictions"] == 0
    ]
    selected_model: str | None = None
    if len(viable) == 1:
        candidate = viable[0]
        other = "END_LABELED" if candidate == "START_LABELED" else "START_LABELED"
        if metrics[other]["contradictions"] > 0:
            selected_model = candidate

    if selected_model is not None:
        decision = selected_model
    elif not trades or all(result["usable_trades"] < MIN_USABLE_TRADES for result in metrics.values()):
        decision = "INCONCLUSIVE_INSUFFICIENT_CROSS_ENDPOINT_EVIDENCE"
    else:
        decision = "INCONCLUSIVE_NO_UNIQUE_MODEL"

    return {
        "decision": decision,
        "selected_model": selected_model,
        "models": metrics,
        "trade_records_received": len(trades),
        "claims": {
            "interval_label_semantics_only": selected_model is not None,
            "continuous_panel": False,
            "empty_interval_semantics": False,
            "historical_panel": False,
            "pit_admissible": False,
            "h07_h01_evidence": False,
            "task30_trial": False,
            "execution": False,
            "numeric_netreturn": False,
        },
    }
