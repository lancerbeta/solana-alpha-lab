"""Offline boundary for one future pool-targeted standard WSS log capture."""

from __future__ import annotations

import json
import hashlib
import math
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .lifecycle_discovery_transport import BoundProbeRequest
from .pumpswap_touch_decoder import PumpSwapIdlPlan
from .pumpswap_touch_probe import (
    TouchNotificationError,
    TouchProtocolDriftError,
    parse_logs_notification,
)


POOL_ADDRESS = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
BASE_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
QUOTE_MINT = "So11111111111111111111111111111111111111112"
HELIUS_WSS_BASE = "wss://mainnet.helius-rpc.com/"
REQUEST_ID = "task30-a15-pool-logs-subscribe"

OWNER_PILOT_PHRASE = (
    "T30-A15P_STANDARD_POOL_LOGS_RUNTIME_V1; "
    f"pool={POOL_ADDRESS}; provider=HELIUS_STANDARD_WSS; "
    "monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND; "
    "max_wss_connections=1; max_subscriptions=1; max_open_seconds=600; "
    "max_notifications=128; max_stream_bytes=1000000; "
    "estimated_credit_cap=21; retention=A4; rpc_followups=0; "
    "retry=false; reconnect=false; fallback=false"
)

_ROOT = frozenset(
    {
        "schema",
        "schema_version",
        "task_id",
        "atom_id",
        "contract_id",
        "consumer",
        "target",
        "wire",
        "runtime_limits",
        "execution_controls",
        "authority",
        "owner_authority",
        "decision",
        "project_sources_disposition",
    }
)
_TARGET = frozenset({"network", "pool_address", "base_mint", "quote_mint", "dex_id"})
_WIRE = frozenset({"provider", "method", "mentions", "commitment"})
_LIMITS = frozenset(
    {
        "effective_open_seconds",
        "max_notifications",
        "max_stream_bytes",
        "max_frame_bytes",
        "estimated_credit_cap",
        "credit_bytes_per_unit",
        "credits_per_unit",
        "connection_credits",
    }
)
_CONTROLS = frozenset(
    {
        "monitoring_owner",
        "retention_class",
        "wss_connections",
        "subscriptions",
        "rpc_followups",
        "retry",
        "reconnect",
        "fallback",
        "scheduler",
    }
)
_AUTHORITY = frozenset(
    {
        "provider_api_rpc_wss_calls",
        "credential_read",
        "raw_data_write",
        "cash_spend_usd",
        "task30_trial_or_acceptance",
    }
)
_OWNER = frozenset({"future_pilot_authorized", "future_pilot_phrase"})
_TERMINAL_CLASSES = frozenset(
    {
        "BOUND_REACHED",
        "DNS_OR_TLS",
        "REMOTE_CLOSED",
        "RESPONSE_TOO_LARGE",
        "TIMEOUT",
        "TRANSPORT_FAILURE",
    }
)


class StandardPoolLogsRouteError(ValueError):
    """The offline route is malformed, widened or semantically unsafe."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise StandardPoolLogsRouteError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(isinstance(key, str) for key in value), code)
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], code: str) -> None:
    _require(frozenset(value) == expected, code)


def _exact(value: object, expected: object, code: str) -> None:
    _require(type(value) is type(expected) and value == expected, code)


def _validate_policy(config: Mapping[str, Any]) -> None:
    _exact_keys(config, _ROOT, "ROOT_FIELDS_DRIFT")
    expected_root = {
        "schema": "smial.task30.standard-pool-logs-route.policy",
        "schema_version": "1.0",
        "task_id": "TASK-30",
        "atom_id": "T30-A15_STANDARD_WSS_POOL_TRADE_ROUTE_V1",
        "contract_id": "TASK30-STANDARD-POOL-LOGS-ROUTE-V1",
        "consumer": "RC001-H07-H01-LIQUIDITY-RETENTION",
        "decision": "OFFLINE_ROUTE_READY_FOR_OWNER_GATE",
        "project_sources_disposition": "NO_CHANGE",
    }
    for field, expected in expected_root.items():
        _exact(config.get(field), expected, "ROOT_VALUE_DRIFT")

    target = _mapping(config.get("target"), "TARGET_REQUIRED")
    _exact_keys(target, _TARGET, "TARGET_FIELDS_DRIFT")
    for field, expected in {
        "network": "solana",
        "pool_address": POOL_ADDRESS,
        "base_mint": BASE_MINT,
        "quote_mint": QUOTE_MINT,
        "dex_id": "pumpswap",
    }.items():
        _exact(target.get(field), expected, "TARGET_IDENTITY_DRIFT")

    wire = _mapping(config.get("wire"), "WIRE_REQUIRED")
    _exact_keys(wire, _WIRE, "WIRE_FIELDS_DRIFT")
    for field, expected in {
        "provider": "HELIUS_STANDARD_WSS",
        "method": "logsSubscribe",
        "mentions": [POOL_ADDRESS],
        "commitment": "confirmed",
    }.items():
        _exact(wire.get(field), expected, "WIRE_PROFILE_DRIFT")

    limits = _mapping(config.get("runtime_limits"), "LIMITS_REQUIRED")
    _exact_keys(limits, _LIMITS, "LIMIT_FIELDS_DRIFT")
    for field, expected in {
        "effective_open_seconds": 600,
        "max_notifications": 128,
        "max_stream_bytes": 1_000_000,
        "max_frame_bytes": 100_000,
        "estimated_credit_cap": 21,
        "credit_bytes_per_unit": 100_000,
        "credits_per_unit": 2,
        "connection_credits": 1,
    }.items():
        _exact(limits.get(field), expected, "RUNTIME_LIMIT_DRIFT")

    controls = _mapping(config.get("execution_controls"), "CONTROLS_REQUIRED")
    _exact_keys(controls, _CONTROLS, "CONTROL_FIELDS_DRIFT")
    for field, expected in {
        "monitoring_owner": "LOCAL_WORK_CODEX_FOREGROUND",
        "retention_class": "A4",
        "wss_connections": 1,
        "subscriptions": 1,
        "rpc_followups": 0,
        "retry": False,
        "reconnect": False,
        "fallback": False,
        "scheduler": False,
    }.items():
        _exact(controls.get(field), expected, "EXECUTION_CONTROL_DRIFT")

    authority = _mapping(config.get("authority"), "AUTHORITY_REQUIRED")
    _exact_keys(authority, _AUTHORITY, "AUTHORITY_FIELDS_DRIFT")
    for field, expected in {
        "provider_api_rpc_wss_calls": 0,
        "credential_read": False,
        "raw_data_write": False,
        "cash_spend_usd": 0,
        "task30_trial_or_acceptance": False,
    }.items():
        _exact(authority.get(field), expected, "ZERO_AUTHORITY_REQUIRED")

    owner = _mapping(config.get("owner_authority"), "OWNER_AUTHORITY_REQUIRED")
    _exact_keys(owner, _OWNER, "OWNER_AUTHORITY_FIELDS_DRIFT")
    _exact(owner.get("future_pilot_authorized"), False, "OWNER_AUTHORITY_FORBIDDEN")
    _exact(owner.get("future_pilot_phrase"), OWNER_PILOT_PHRASE, "OWNER_PHRASE_DRIFT")


def evaluate_standard_pool_logs_route(config: Mapping[str, Any]) -> dict[str, object]:
    """Validate the closed A15 route without credentials or external I/O."""

    _validate_policy(config)
    return {
        "terminal_state": "ROUTE_READY_OFFLINE",
        "decision": "OFFLINE_ROUTE_READY_FOR_OWNER_GATE",
        "external_action_authorized": False,
        "project_sources_disposition": "NO_CHANGE",
    }


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def bind_pool_logs_subscribe(api_key: str) -> BoundProbeRequest:
    """Bind one exact-pool request while keeping the key only in memory."""

    _require(
        type(api_key) is str
        and bool(api_key)
        and not any(character.isspace() for character in api_key),
        "CREDENTIAL_VALUE_INVALID",
    )
    body = _canonical_json(
        {
            "id": REQUEST_ID,
            "jsonrpc": "2.0",
            "method": "logsSubscribe",
            "params": [
                {"mentions": [POOL_ADDRESS]},
                {"commitment": "confirmed"},
            ],
        }
    )
    query = urllib.parse.urlencode((("api-key", api_key),))
    return BoundProbeRequest(
        request_id=REQUEST_ID,
        provider="HELIUS",
        transport="WSS",
        method="POST",
        url=f"{HELIUS_WSS_BASE}?{query}",
        headers=(
            ("accept", "application/json"),
            ("user-agent", "smial-task30-a15/1.0"),
        ),
        body=body,
        safe_query_keys=(),
    )


@dataclass(frozen=True, slots=True, repr=False)
class StandardPoolLogsCapture:
    """Sanitized in-memory adapter output for deterministic classification."""

    acknowledgement: bytes = field(repr=False)
    notifications: tuple[bytes, ...] = field(repr=False)
    terminal_class: str = "BOUND_REACHED"
    error_class: str | None = None

    def __post_init__(self) -> None:
        _require(self.terminal_class in _TERMINAL_CLASSES, "TERMINAL_CLASS_INVALID")
        _require(type(self.acknowledgement) is bytes, "ACK_BYTES_INVALID")
        _require(
            type(self.notifications) is tuple
            and all(type(item) is bytes for item in self.notifications),
            "NOTIFICATION_BYTES_INVALID",
        )
        if self.terminal_class == "BOUND_REACHED":
            _require(self.error_class is None, "BOUNDED_CAPTURE_HAS_ERROR")
        else:
            _require(type(self.error_class) is str and bool(self.error_class), "FAILED_CAPTURE_NEEDS_ERROR")

    def __repr__(self) -> str:
        return (
            "StandardPoolLogsCapture("
            f"acknowledgement_bytes={len(self.acknowledgement)}, "
            f"notifications={len(self.notifications)}, "
            f"terminal_class={self.terminal_class!r}, bodies=<redacted>)"
        )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise StandardPoolLogsRouteError("DUPLICATE_JSON_KEY")
        document[key] = value
    return document


def _parse_json(body: bytes, code: str) -> Mapping[str, Any]:
    try:
        document = json.loads(body, object_pairs_hook=_reject_duplicate_json_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StandardPoolLogsRouteError(code) from exc
    return _mapping(document, code)


def _subscription_ack(acknowledgement: bytes) -> tuple[str, int | None]:
    document = _parse_json(acknowledgement, "SUBSCRIPTION_ACK_INVALID")
    if frozenset(document) == frozenset({"error", "id", "jsonrpc"}):
        _exact(document.get("id"), REQUEST_ID, "SUBSCRIPTION_ACK_INVALID")
        _exact(document.get("jsonrpc"), "2.0", "SUBSCRIPTION_ACK_INVALID")
        _mapping(document.get("error"), "SUBSCRIPTION_ACK_INVALID")
        return "SUBSCRIPTION_REJECTED", None
    _exact_keys(
        document,
        frozenset({"id", "jsonrpc", "result"}),
        "SUBSCRIPTION_ACK_INVALID",
    )
    _exact(document.get("id"), REQUEST_ID, "SUBSCRIPTION_ACK_INVALID")
    _exact(document.get("jsonrpc"), "2.0", "SUBSCRIPTION_ACK_INVALID")
    subscription_id = document.get("result")
    _require(
        type(subscription_id) is int and subscription_id >= 0,
        "SUBSCRIPTION_ACK_INVALID",
    )
    return "ACKNOWLEDGED", subscription_id


def _classification(
    terminal_state: str,
    *,
    notifications: int,
    decoded_events: int = 0,
    signature_hashes: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "terminal_state": terminal_state,
        "notifications": notifications,
        "decoded_events": decoded_events,
        "signature_hashes": list(signature_hashes),
        "unknown": terminal_state.endswith("_UNKNOWN"),
        "retry": False,
        "reconnect": False,
        "rpc_followups": 0,
        "zero_volume": False,
        "empty_interval": False,
        "interval_complete": False,
        "pit_admissible": False,
        "task30_trial": False,
        "numeric_netreturn": False,
    }


def classify_standard_pool_logs_capture(
    config: Mapping[str, Any],
    capture: StandardPoolLogsCapture,
    plan: PumpSwapIdlPlan,
) -> dict[str, object]:
    """Classify one bounded capture without projecting interval completeness."""

    evaluate_standard_pool_logs_route(config)
    limits = _mapping(config["runtime_limits"], "LIMITS_REQUIRED")
    stream_bytes = len(capture.acknowledgement) + sum(
        len(item) for item in capture.notifications
    )
    _require(stream_bytes <= limits["max_stream_bytes"], "STREAM_BYTE_CAP_EXCEEDED")
    _require(len(capture.notifications) <= limits["max_notifications"], "NOTIFICATION_CAP_EXCEEDED")
    _require(len(capture.acknowledgement) <= limits["max_frame_bytes"], "ACK_FRAME_CAP_EXCEEDED")
    _require(
        all(len(item) <= limits["max_frame_bytes"] for item in capture.notifications),
        "NOTIFICATION_FRAME_CAP_EXCEEDED",
    )
    estimated_credits = limits["connection_credits"] + math.ceil(
        stream_bytes / limits["credit_bytes_per_unit"]
    ) * limits["credits_per_unit"]
    _require(estimated_credits <= limits["estimated_credit_cap"], "CREDIT_CAP_EXCEEDED")

    if capture.terminal_class != "BOUND_REACHED":
        return _classification(
            "TRANSPORT_LOST_UNKNOWN",
            notifications=len(capture.notifications),
        )

    acknowledgement_state, subscription_id = _subscription_ack(capture.acknowledgement)
    if acknowledgement_state == "SUBSCRIPTION_REJECTED":
        return _classification("SUBSCRIPTION_REJECTED", notifications=0)
    assert subscription_id is not None
    if not capture.notifications:
        return _classification("NO_OBSERVATION_UNKNOWN", notifications=0)

    signatures: set[str] = set()
    signature_hashes: list[str] = []
    decoded_events = 0
    observed_trade = False
    drift_unknown = False
    for body in capture.notifications:
        try:
            parsed = parse_logs_notification(
                body,
                expected_subscription_id=subscription_id,
                plan=plan,
            )
        except TouchProtocolDriftError:
            drift_unknown = True
            continue
        except TouchNotificationError as exc:
            raise StandardPoolLogsRouteError(f"NOTIFICATION_INVALID:{exc}") from exc
        _require(parsed.signature not in signatures, "DUPLICATE_SIGNATURE")
        signatures.add(parsed.signature)
        signature_hashes.append(hashlib.sha256(parsed.signature.encode()).hexdigest())
        if parsed.logs_truncated:
            drift_unknown = True
            continue
        for event in parsed.decoded_events:
            _require(event.pool_id == POOL_ADDRESS, "DECODED_POOL_MISMATCH")
            decoded_events += 1
            if event.event_name in {"BuyEvent", "SellEvent"}:
                observed_trade = True

    if drift_unknown:
        terminal_state = "TRUNCATED_OR_SCHEMA_DRIFT_UNKNOWN"
    elif observed_trade:
        terminal_state = "OBSERVED_POOL_TRADE"
    else:
        terminal_state = "OBSERVED_NON_TRADE_OR_UNSUPPORTED"
    return _classification(
        terminal_state,
        notifications=len(capture.notifications),
        decoded_events=decoded_events,
        signature_hashes=tuple(signature_hashes),
    )


def render_standard_pool_logs_route(config: Mapping[str, Any]) -> str:
    """Render stable owner-facing Russian text without an external surface."""

    evaluate_standard_pool_logs_route(config)
    limits = _mapping(config["runtime_limits"], "LIMITS_REQUIRED")
    stream_bytes = f"{limits['max_stream_bytes']:,}".replace(",", " ")
    return "\n".join(
        (
            "# Стандартный WSS-маршрут одного PumpSwap-пула",
            "",
            "Стандартный бесплатный WSS-маршрут подготовлен офлайн.",
            "Он слушает только зафиксированный пул и использует уже проверенный PumpSwap-декодер.",
            "Но реальный запуск пока не разрешён: соединение не открывалось и ключ не читался.",
            f"Будущий предел: {limits['effective_open_seconds']} секунд, {limits['max_notifications']} уведомлений и {stream_bytes} байт.",
            "Повтор, переподключение, fallback, scheduler и дополнительные RPC-запросы запрещены.",
            "Важно: отсутствие уведомлений не означает нулевой объём, пустой интервал или полное покрытие.",
            "Обрыв соединения или усечённые логи остаются UNKNOWN и останавливают выводы.",
            "Даже найденная сделка пока является техническим наблюдением, а не TASK-30 trial или alpha evidence.",
            "",
            "Следующая граница — отдельное точное разрешение владельца на один foreground-пилот.",
        )
    ) + "\n"
