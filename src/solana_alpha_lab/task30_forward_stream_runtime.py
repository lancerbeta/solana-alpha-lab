"""Offline safety boundary for a future bounded transaction stream pilot."""

from __future__ import annotations

import hashlib
import json
import math
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .lifecycle_discovery_transport import BoundProbeRequest


POOL_ADDRESS = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
BASE_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
HELIUS_WSS_BASE = "wss://mainnet.helius-rpc.com/"
REQUEST_ID = "task30-a14-transaction-subscribe"


def _owner_execution_phrase(version: str) -> str:
    return (
        f"T30-A14P_FORWARD_STREAM_RUNTIME_{version}; "
        f"pool={POOL_ADDRESS}; "
        "monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND; "
        "max_wss_connections=1; max_subscriptions=1; "
        "max_open_seconds=1200; max_notifications=500; "
        "max_stream_bytes=1000000; estimated_credit_cap=21; "
        "retention=A4; retry=false; reconnect=false; fallback=false"
    )


OWNER_EXECUTION_PHRASE = _owner_execution_phrase("V1")
OWNER_EXECUTION_PHRASE_V2 = _owner_execution_phrase("V2")
MAX_OPEN_SECONDS = 540
MAX_NOTIFICATIONS = 500
MAX_STREAM_BYTES = 1_000_000
MAX_FRAME_BYTES = 100_000
CREDIT_BYTES_PER_UNIT = 100_000
CREDITS_PER_UNIT = 2
CONNECTION_CREDITS = 1

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
_ROOT_FIELDS = frozenset(
    {
        "atom_id",
        "authority",
        "consumer",
        "contract_id",
        "decision",
        "execution_controls",
        "project_sources_disposition",
        "runtime_limits",
        "schema",
        "schema_version",
        "target",
        "task_id",
        "wire",
        "owner_authority",
    }
)
_TARGET_FIELDS = frozenset({"base_mint", "network", "pool_address"})
_WIRE_FIELDS = frozenset(
    {
        "commitment",
        "encoding",
        "failed",
        "max_supported_transaction_version",
        "method",
        "provider",
        "transaction_details",
        "vote",
    }
)
_LIMIT_FIELDS = frozenset(
    {
        "connection_credits",
        "credit_bytes_per_unit",
        "credits_per_unit",
        "effective_open_seconds",
        "estimated_credit_cap",
        "max_frame_bytes",
        "max_notifications",
        "max_stream_bytes",
    }
)
_CONTROL_FIELDS = frozenset(
    {
        "fallback",
        "monitoring_owner",
        "raw_root",
        "reconnect",
        "retention_class",
        "retry",
        "scheduler",
    }
)
_AUTHORITY_FIELDS = frozenset(
    {
        "cash_spend_usd",
        "credential_read",
        "provider_api_rpc_wss_calls",
        "raw_data_write",
        "task30_trial_or_acceptance",
    }
)
_OWNER_FIELDS = frozenset({"future_pilot_authorized", "future_pilot_phrase"})
_RUNTIME_PROFILES = {
    "T30-A14_FORWARD_STREAM_PILOT_RUNTIME_HARNESS_V1": (
        "TASK30-FORWARD-STREAM-RUNTIME-HARNESS-V1",
        OWNER_EXECUTION_PHRASE,
    ),
    "T30-A14_FORWARD_STREAM_PILOT_RUNTIME_HARNESS_V2": (
        "TASK30-FORWARD-STREAM-RUNTIME-HARNESS-V2",
        OWNER_EXECUTION_PHRASE_V2,
    ),
}


class ForwardStreamRuntimeError(ValueError):
    """Raised when the future stream runtime boundary is widened or malformed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ForwardStreamRuntimeError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(isinstance(key, str) for key in value), code)
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], code: str) -> None:
    _require(frozenset(value) == expected, code)


def _exact(value: object, expected: object, code: str) -> None:
    _require(type(value) is type(expected) and value == expected, code)


def _runtime_profile(config: Mapping[str, Any]) -> tuple[str, str]:
    atom_id = config.get("atom_id")
    profile = _RUNTIME_PROFILES.get(atom_id) if type(atom_id) is str else None
    _require(profile is not None, "ATOM_ID_DRIFT")
    return profile


def _validate_policy_shape(config: Mapping[str, Any]) -> None:
    _exact_keys(config, _ROOT_FIELDS, "ROOT_FIELDS_DRIFT")
    _exact(config.get("schema"), "smial.task30.forward-stream-runtime.policy", "SCHEMA_DRIFT")
    _exact(config.get("schema_version"), "1.0", "SCHEMA_VERSION_DRIFT")
    _exact(config.get("task_id"), "TASK-30", "TASK_ID_DRIFT")
    expected_contract_id, expected_phrase = _runtime_profile(config)
    _exact(config.get("contract_id"), expected_contract_id, "CONTRACT_ID_DRIFT")
    _exact(config.get("consumer"), "FUTURE_EXACT_OWNER_EXTERNAL_READ_GATE", "CONSUMER_DRIFT")

    target = _mapping(config.get("target"), "TARGET_REQUIRED")
    _exact_keys(target, _TARGET_FIELDS, "TARGET_FIELDS_DRIFT")
    _exact(target.get("network"), "solana", "TARGET_IDENTITY_DRIFT")
    _exact(target.get("pool_address"), POOL_ADDRESS, "TARGET_IDENTITY_DRIFT")
    _exact(target.get("base_mint"), BASE_MINT, "TARGET_IDENTITY_DRIFT")

    wire = _mapping(config.get("wire"), "WIRE_REQUIRED")
    _exact_keys(wire, _WIRE_FIELDS, "WIRE_FIELDS_DRIFT")
    expected_wire = {
        "provider": "HELIUS",
        "method": "transactionSubscribe",
        "commitment": "confirmed",
        "encoding": "jsonParsed",
        "transaction_details": "full",
        "max_supported_transaction_version": 0,
        "failed": False,
        "vote": False,
    }
    for field, expected in expected_wire.items():
        _exact(wire.get(field), expected, "WIRE_PROFILE_DRIFT")

    limits = _mapping(config.get("runtime_limits"), "RUNTIME_LIMITS_REQUIRED")
    _exact_keys(limits, _LIMIT_FIELDS, "RUNTIME_LIMIT_FIELDS_DRIFT")
    expected_limits = {
        "effective_open_seconds": MAX_OPEN_SECONDS,
        "max_notifications": MAX_NOTIFICATIONS,
        "max_stream_bytes": MAX_STREAM_BYTES,
        "max_frame_bytes": MAX_FRAME_BYTES,
        "credit_bytes_per_unit": CREDIT_BYTES_PER_UNIT,
        "credits_per_unit": CREDITS_PER_UNIT,
        "connection_credits": CONNECTION_CREDITS,
        "estimated_credit_cap": CONNECTION_CREDITS
        + math.ceil(MAX_STREAM_BYTES / CREDIT_BYTES_PER_UNIT) * CREDITS_PER_UNIT,
    }
    for field, expected in expected_limits.items():
        _exact(limits.get(field), expected, "RUNTIME_LIMIT_DRIFT")

    controls = _mapping(config.get("execution_controls"), "EXECUTION_CONTROLS_REQUIRED")
    _exact_keys(controls, _CONTROL_FIELDS, "EXECUTION_CONTROL_FIELDS_DRIFT")
    for field in ("retry", "reconnect", "fallback", "scheduler"):
        _exact(controls.get(field), False, "RETRY_RECONNECT_SCHEDULER_FORBIDDEN")
    _exact(controls.get("monitoring_owner"), "LOCAL_WORK_CODEX_FOREGROUND", "MONITORING_OWNER_DRIFT")
    _exact(controls.get("retention_class"), "A4", "RETENTION_CLASS_DRIFT")
    _exact(controls.get("raw_root"), "OWNER_INPUT_REQUIRED", "RAW_ROOT_DISCLOSURE_FORBIDDEN")

    authority = _mapping(config.get("authority"), "AUTHORITY_REQUIRED")
    _exact_keys(authority, _AUTHORITY_FIELDS, "AUTHORITY_FIELDS_DRIFT")
    _exact(authority.get("provider_api_rpc_wss_calls"), 0, "ZERO_AUTHORITY_REQUIRED")
    _exact(authority.get("cash_spend_usd"), 0, "ZERO_AUTHORITY_REQUIRED")
    for field in ("credential_read", "raw_data_write", "task30_trial_or_acceptance"):
        _exact(authority.get(field), False, "ZERO_AUTHORITY_REQUIRED")
    owner = _mapping(config.get("owner_authority"), "OWNER_AUTHORITY_REQUIRED")
    _exact_keys(owner, _OWNER_FIELDS, "OWNER_AUTHORITY_FIELDS_DRIFT")
    _exact(owner.get("future_pilot_authorized"), False, "OWNER_AUTHORITY_PROMOTION_FORBIDDEN")
    _exact(owner.get("future_pilot_phrase"), expected_phrase, "OWNER_PHRASE_DRIFT")
    _exact(config.get("decision"), "OFFLINE_RUNTIME_HARNESS_VALIDATED", "DECISION_DRIFT")
    _exact(config.get("project_sources_disposition"), "NO_CHANGE", "SOURCE_DISPOSITION_DRIFT")


def evaluate_forward_stream_runtime(config: Mapping[str, Any]) -> dict[str, object]:
    """Validate the A14 policy without reading credentials or performing I/O."""

    _validate_policy_shape(config)
    return {
        "decision": "OFFLINE_RUNTIME_HARNESS_VALIDATED",
        "external_action_authorized": False,
        "project_sources_disposition": "NO_CHANGE",
        "provider": "HELIUS",
    }


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def bind_transaction_subscribe(api_key: str) -> BoundProbeRequest:
    """Bind one target-locked request; the key remains only in memory."""

    _require(
        isinstance(api_key, str)
        and bool(api_key)
        and not any(character.isspace() for character in api_key),
        "CREDENTIAL_VALUE_INVALID",
    )
    body = _canonical_json(
        {
            "id": REQUEST_ID,
            "jsonrpc": "2.0",
            "method": "transactionSubscribe",
            "params": [
                {
                    "accountInclude": [POOL_ADDRESS],
                    "failed": False,
                    "vote": False,
                },
                {
                    "commitment": "confirmed",
                    "encoding": "jsonParsed",
                    "transactionDetails": "full",
                    "maxSupportedTransactionVersion": 0,
                },
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
            ("user-agent", "smial-task30-a14/1.0"),
        ),
        body=body,
        safe_query_keys=(),
    )


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeCapture:
    """Sanitized adapter output used by the offline classifier and fake tests."""

    acknowledgement: bytes = field(repr=False)
    notifications: tuple[bytes, ...] = field(repr=False)
    terminal_class: str = "BOUND_REACHED"
    error_class: str | None = None

    def __post_init__(self) -> None:
        _require(self.terminal_class in _TERMINAL_CLASSES, "WSS_TERMINAL_CLASS_INVALID")
        _require(isinstance(self.acknowledgement, bytes), "ACK_BYTES_INVALID")
        _require(
            isinstance(self.notifications, tuple)
            and all(isinstance(item, bytes) for item in self.notifications),
            "NOTIFICATION_BYTES_INVALID",
        )
        if self.terminal_class == "BOUND_REACHED":
            _require(self.error_class is None, "BOUNDED_CAPTURE_HAS_ERROR")
        else:
            _require(bool(self.error_class), "FAILED_CAPTURE_NEEDS_ERROR")

    def __repr__(self) -> str:
        return (
            "RuntimeCapture("
            f"acknowledgement_bytes={len(self.acknowledgement)}, "
            f"notifications={len(self.notifications)}, "
            f"terminal_class={self.terminal_class!r}, bodies=<redacted>)"
        )


def _parse_json(body: bytes, code: str) -> Mapping[str, Any]:
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError) as exc:
        raise ForwardStreamRuntimeError(code) from exc
    return _mapping(parsed, code)


def _subscription_id(acknowledgement: bytes) -> int:
    document = _parse_json(acknowledgement, "SUBSCRIPTION_ACK_INVALID")
    _exact(document.get("jsonrpc"), "2.0", "SUBSCRIPTION_ACK_INVALID")
    _exact(document.get("id"), REQUEST_ID, "SUBSCRIPTION_ACK_INVALID")
    if "error" in document:
        raise ForwardStreamRuntimeError("SUBSCRIPTION_REJECTED")
    value = document.get("result")
    _require(type(value) is int and value >= 0, "SUBSCRIPTION_ACK_INVALID")
    return value


def _validate_notification(body: bytes, expected_subscription: int) -> None:
    document = _parse_json(body, "NOTIFICATION_SCHEMA_INVALID")
    _exact(document.get("jsonrpc"), "2.0", "NOTIFICATION_SCHEMA_INVALID")
    _exact(document.get("method"), "transactionNotification", "NOTIFICATION_SCHEMA_INVALID")
    params = _mapping(document.get("params"), "NOTIFICATION_SCHEMA_INVALID")
    _exact(params.get("subscription"), expected_subscription, "NOTIFICATION_SUBSCRIPTION_DRIFT")
    result = _mapping(params.get("result"), "NOTIFICATION_SCHEMA_INVALID")
    context = _mapping(result.get("context"), "NOTIFICATION_SCHEMA_INVALID")
    slot = context.get("slot")
    _require(type(slot) is int and slot >= 0, "NOTIFICATION_SCHEMA_INVALID")
    _mapping(result.get("value"), "NOTIFICATION_SCHEMA_INVALID")


def classify_forward_stream_capture(
    config: Mapping[str, Any], capture: RuntimeCapture
) -> dict[str, object]:
    """Classify one bounded capture without projecting it into market truth."""

    evaluate_forward_stream_runtime(config)
    limits = _mapping(config["runtime_limits"], "RUNTIME_LIMITS_REQUIRED")
    stream_bytes = len(capture.acknowledgement) + sum(
        len(item) for item in capture.notifications
    )
    _require(stream_bytes <= limits["max_stream_bytes"], "STREAM_BYTE_CAP_EXCEEDED")
    _require(
        len(capture.notifications) <= limits["max_notifications"],
        "NOTIFICATION_CAP_EXCEEDED",
    )
    _require(
        len(capture.acknowledgement) <= limits["max_frame_bytes"],
        "ACK_FRAME_CAP_EXCEEDED",
    )
    _require(
        all(len(item) <= limits["max_frame_bytes"] for item in capture.notifications),
        "NOTIFICATION_FRAME_CAP_EXCEEDED",
    )

    if not capture.acknowledgement:
        if capture.terminal_class == "BOUND_REACHED":
            raise ForwardStreamRuntimeError("SUBSCRIPTION_ACK_INVALID")
        terminal = "CONNECTION_OR_AUTH_REJECTED"
        return {
            "terminal_state": terminal,
            "notifications": 0,
            "stream_bytes": stream_bytes,
            "estimated_credits": CONNECTION_CREDITS,
            "unknown": False,
            "retry": False,
            "reconnect": False,
            "interval_projectable": False,
            "zero_volume": False,
            "empty_interval": False,
            "task30_trial": False,
            "raw_retention": "OWNER_EXTERNAL_GATE_REQUIRED",
        }

    subscription_id = _subscription_id(capture.acknowledgement)
    for body in capture.notifications:
        _validate_notification(body, subscription_id)
    estimated_credits = CONNECTION_CREDITS + math.ceil(
        stream_bytes / limits["credit_bytes_per_unit"]
    ) * limits["credits_per_unit"]
    _require(
        estimated_credits <= limits["estimated_credit_cap"],
        "CREDIT_CAP_EXCEEDED",
    )

    if capture.terminal_class == "REMOTE_CLOSED":
        terminal_state = "TRANSPORT_LOST_UNKNOWN"
        unknown = True
    elif capture.terminal_class in {"DNS_OR_TLS", "TIMEOUT", "TRANSPORT_FAILURE"}:
        terminal_state = "TRANSPORT_LOST_UNKNOWN"
        unknown = True
    elif not capture.notifications:
        terminal_state = "NO_OBSERVED_TX_NO_EMPTY_CLAIM"
        unknown = False
    else:
        terminal_state = "OBSERVATION_RETAINED_TECHNICAL_ONLY"
        unknown = False

    return {
        "terminal_state": terminal_state,
        "notifications": len(capture.notifications),
        "stream_bytes": stream_bytes,
        "stream_sha256": hashlib.sha256(
            capture.acknowledgement + b"".join(capture.notifications)
        ).hexdigest(),
        "estimated_credits": estimated_credits,
        "unknown": unknown,
        "retry": False,
        "reconnect": False,
        "interval_projectable": False,
        "zero_volume": False,
        "empty_interval": False,
        "task30_trial": False,
        "raw_retention": "OWNER_EXTERNAL_GATE_REQUIRED",
    }


def execute_forward_stream_capture(
    config: Mapping[str, Any],
    *,
    api_key: str,
    authority_phrase: str,
    wss_exchange: Any,
) -> dict[str, object]:
    """Run one injected bounded exchange after the exact future owner gate.

    The production default is intentionally not wired here. A future external
    caller must supply a transport and the owner phrase; tests use a fake
    exchange so this module itself never contacts Helius.
    """

    evaluate_forward_stream_runtime(config)
    _, expected_phrase = _runtime_profile(config)
    _exact(authority_phrase, expected_phrase, "EXTERNAL_OWNER_GATE_REQUIRED")
    request = bind_transaction_subscribe(api_key)
    capture = wss_exchange(
        request,
        max_open_seconds=MAX_OPEN_SECONDS,
        max_stream_bytes=MAX_STREAM_BYTES,
        max_notifications=MAX_NOTIFICATIONS,
    )
    _require(isinstance(capture, RuntimeCapture), "WSS_CAPTURE_TYPE_INVALID")
    return classify_forward_stream_capture(config, capture)


def render_forward_stream_runtime(config: Mapping[str, Any]) -> str:
    """Render a non-technical owner summary without endpoint or credential data."""

    evaluate_forward_stream_runtime(config)
    limits = _mapping(config["runtime_limits"], "RUNTIME_LIMITS_REQUIRED")
    stream_bytes = f"{limits['max_stream_bytes']:,}".replace(",", " ")
    return "\n".join(
        (
            "# Офлайн-пакет runtime для будущего stream-пилота",
            "",
            "Этот пакет только проверяет предохранители и не открывает соединение.",
            "Пул и фильтр transactionSubscribe зафиксированы в коде; провайдерский ключ не читается.",
            f"Локальный runtime-лимит: {limits['effective_open_seconds']} секунд, {limits['max_notifications']} уведомлений, "
            f"{stream_bytes} байт.",
            f"Консервативный расчёт бюджета: не более {limits['estimated_credit_cap']} условных credits; это оценка, не billing-claim.",
            "Retry, reconnect, fallback и scheduler запрещены.",
            "Нет наблюдений = NO_OBSERVED_TX_NO_EMPTY_CLAIM; потеря транспорта = UNKNOWN.",
            "Raw retention A4 остаётся отдельным owner gate вне Git.",
            "",
            "Внешний запуск потребует точной owner-фразы A14 и отдельного разрешения.",
        )
    ) + "\n"
