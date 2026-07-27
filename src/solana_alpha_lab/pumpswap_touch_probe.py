"""Bounded standard-Solana PumpSwap Touch probe for TASK-09."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypeAlias

from solana_alpha_lab.contracts.schema_v1 import RawResponseStatus
from solana_alpha_lab.pumpswap_touch_decoder import (
    MAX_EVENT_PAYLOAD_BYTES,
    PROGRAM_DATA_PREFIX,
    PUMPSWAP_IDL_COMMIT,
    PUMPSWAP_PROGRAM_ID,
    DecodedTradeEvent,
    PumpSwapDecodeError,
    PumpSwapIdlPlan,
    decode_pumpswap_program_data,
)
from solana_alpha_lab.storage import (
    StorageBudgetExceededError,
    StorageBudgetPolicy,
    build_raw_api_event,
    canonical_manifest_bytes,
    verify_raw_event_partition,
    write_budgeted_raw_event_partition,
)

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

TRANSPORT_CONTRACT_VERSION = "1.0"
TRANSPORT_AS_OF = "2026-07-27"
EXTERNAL_AUTHORITY_PHRASE = (
    "TASK09_A4_PUMPSWAP_TOUCH_EXTERNAL_RPC_WSS_RAW_WRITE"
)

SOLANA_MAINNET_HOST = "api.mainnet-beta.solana.com"
SOLANA_WSS_URL = f"wss://{SOLANA_MAINNET_HOST}/"
SOLANA_RPC_URL = f"https://{SOLANA_MAINNET_HOST}/"
LOGS_SUBSCRIBE_REQUEST_ID = "task09-logs-subscribe"

ELAPSED_SECONDS_CAP = 30
WSS_CAPTURE_SECONDS = 20
WSS_CONNECTION_CAP = 1
WSS_SUBSCRIPTION_CAP = 1
NOTIFICATION_CAP = 256
STREAM_BYTES_CAP = 1_500_000
GET_TRANSACTION_CAP = 8
MODELED_HELIUS_CREDITS_MAX = 39
HELIUS_CREDIT_CAP = 40
RECEIVED_AND_STORED_BYTES_CAP = 4_000_000
CONCURRENCY_CAP = 1
RETRY_CAP = 0
CASH_SPEND_USD_CENTS_CAP = 0

MAX_WSS_FRAME_BYTES = 100_000
MAX_HTTP_RESPONSE_BYTES = 128_000
STORAGE_METADATA_RESERVE_BYTES = 65_536
MAX_REDACTED_EXPANSION_FACTOR = 3
MAX_ADMITTED_RECEIVED_BYTES = (
    RECEIVED_AND_STORED_BYTES_CAP - STORAGE_METADATA_RESERVE_BYTES
) // (1 + MAX_REDACTED_EXPANSION_FACTOR)

DATASET_ID = "SMIAL_TASK09_PUMPSWAP_TOUCH_PROBE_RAW"
DATASET_VERSION = "1.0"
RAW_LOGICAL_ROOT = "task09_pumpswap_touch_probe_v1"

_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")
_INVOKE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) invoke \[([1-9][0-9]*)\]$"
)
_COMPLETE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) "
    r"(?:success|failed(?:: .*)?)$"
)
_LOG_TRUNCATED_MARKER = "Log truncated"
_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class TouchProbeContractError(ValueError):
    """The frozen probe boundary is invalid or has drifted."""


class ExternalAuthorityRequiredError(TouchProbeContractError):
    """The exact external-action tripwire was not satisfied."""


class TouchProbeStopError(RuntimeError):
    """A hard cap, provider failure or protocol drift stopped the probe."""


class TouchNotificationError(TouchProbeStopError):
    """A logsSubscribe acknowledgement or notification drifted."""


class TouchProtocolDriftError(TouchProbeStopError):
    """Pinned PumpSwap program-data decoding or attribution drifted."""


class TouchTransportError(TouchProbeStopError):
    """A concrete no-retry transport operation failed safely."""


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _parse_json(name: str, body: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TouchNotificationError(f"{name}_invalid_json") from exc
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise TouchNotificationError(f"{name}_must_be_object")
    return value


def _exact_keys(name: str, value: Mapping[str, Any], expected: set[str]) -> None:
    if set(value) != expected:
        raise TouchNotificationError(f"{name}_keys_drift")


def _safe_error_code(exc: BaseException) -> str:
    value = str(exc)
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        return value
    return type(exc).__name__


def _validate_signature(value: object) -> str:
    if (
        not isinstance(value, str)
        or not 64 <= len(value) <= 88
        or _BASE58_RE.fullmatch(value) is None
    ):
        raise TouchNotificationError("transaction_signature_invalid")
    return value


@dataclass(frozen=True, slots=True)
class ExternalExecutionGate:
    """Exact non-secret tripwire; authority remains outside the code."""

    authority_phrase: str

    def require(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise ExternalAuthorityRequiredError(
                "external_authority_phrase_mismatch"
            )


@dataclass(frozen=True, slots=True, repr=False)
class BoundRequest:
    """One allowlisted public Solana read request with no credential surface."""

    request_id: str
    transport: str
    method: str
    url: str = field(repr=False)
    headers: tuple[tuple[str, str], ...] = field(repr=False)
    body: bytes = field(repr=False)

    def __post_init__(self) -> None:
        split = urllib.parse.urlsplit(self.url)
        expected_scheme = "wss" if self.transport == "WSS" else "https"
        if (
            split.scheme != expected_scheme
            or split.hostname != SOLANA_MAINNET_HOST
            or (split.path or "/") != "/"
            or split.port is not None
            or split.username is not None
            or split.password is not None
            or split.query
            or split.fragment
        ):
            raise TouchProbeContractError("endpoint_not_allowlisted")
        if self.transport not in {"WSS", "HTTP"}:
            raise TouchProbeContractError("transport_not_allowlisted")
        if self.method != "POST":
            raise TouchProbeContractError("request_method_drift")
        expected_headers = (
            ("accept", "user-agent")
            if self.transport == "WSS"
            else ("accept", "content-type", "user-agent")
        )
        if tuple(key.casefold() for key, _ in self.headers) != expected_headers:
            raise TouchProbeContractError("request_headers_drift")
        document = _parse_json("request_body", self.body)
        if document.get("id") != self.request_id or document.get("jsonrpc") != "2.0":
            raise TouchProbeContractError("request_identity_drift")
        rpc_method = document.get("method")
        if self.transport == "WSS" and rpc_method != "logsSubscribe":
            raise TouchProbeContractError("wss_rpc_method_drift")
        if self.transport == "HTTP" and rpc_method != "getTransaction":
            raise TouchProbeContractError("http_rpc_method_drift")

    def __repr__(self) -> str:
        return (
            "BoundRequest("
            f"request_id={self.request_id!r}, transport={self.transport!r}, "
            f"method={self.method!r}, url=<redacted>, headers=<redacted>, "
            "body=<redacted>)"
        )

    def safe_receipt(self) -> dict[str, JsonValue]:
        document = json.loads(self.body)
        return {
            "body_bytes": len(self.body),
            "body_sha256": hashlib.sha256(self.body).hexdigest(),
            "host": SOLANA_MAINNET_HOST,
            "http_method": self.method,
            "path": "/",
            "request_id": self.request_id,
            "rpc_method": document["method"],
            "transport": self.transport,
        }


def bind_logs_subscribe() -> BoundRequest:
    body = _canonical_json_bytes(
        {
            "id": LOGS_SUBSCRIBE_REQUEST_ID,
            "jsonrpc": "2.0",
            "method": "logsSubscribe",
            "params": [
                {"mentions": [PUMPSWAP_PROGRAM_ID]},
                {"commitment": "confirmed"},
            ],
        }
    )
    return BoundRequest(
        request_id=LOGS_SUBSCRIBE_REQUEST_ID,
        transport="WSS",
        method="POST",
        url=SOLANA_WSS_URL,
        headers=(
            ("accept", "application/json"),
            ("user-agent", "smial-task09-touch-probe/1.0"),
        ),
        body=body,
    )


def bind_get_transaction(signature: str, ordinal: int) -> BoundRequest:
    _validate_signature(signature)
    if isinstance(ordinal, bool) or not 1 <= ordinal <= GET_TRANSACTION_CAP:
        raise TouchProbeContractError("followup_ordinal_invalid")
    request_id = f"task09-get-transaction-{ordinal:02d}"
    body = _canonical_json_bytes(
        {
            "id": request_id,
            "jsonrpc": "2.0",
            "method": "getTransaction",
            "params": [
                signature,
                {
                    "commitment": "confirmed",
                    "encoding": "json",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        }
    )
    return BoundRequest(
        request_id=request_id,
        transport="HTTP",
        method="POST",
        url=SOLANA_RPC_URL,
        headers=(
            ("accept", "application/json"),
            ("content-type", "application/json"),
            ("user-agent", "smial-task09-touch-probe/1.0"),
        ),
        body=body,
    )


@dataclass(frozen=True, slots=True, repr=False)
class WssCapture:
    acknowledgement: bytes = field(repr=False)
    notifications: tuple[bytes, ...] = field(repr=False)
    acknowledgement_observed_at: datetime | None
    notification_observed_at: tuple[datetime, ...]
    terminal_class: str
    error_class: str | None
    stop_reason: str


@dataclass(frozen=True, slots=True, repr=False)
class HttpCapture:
    status_code: int | None
    body: bytes = field(repr=False)
    terminal_class: str
    error_class: str | None
    received_bytes: int


class WssExchange(Protocol):
    def __call__(
        self,
        request: BoundRequest,
        *,
        max_open_seconds: int,
        max_stream_bytes: int,
        max_notifications: int,
    ) -> WssCapture: ...


class HttpExchange(Protocol):
    def __call__(
        self,
        request: BoundRequest,
        *,
        max_response_bytes: int,
    ) -> HttpCapture: ...


def _bounded_frame(value: object) -> bytes:
    if isinstance(value, str):
        body = value.encode("utf-8")
    elif isinstance(value, bytes):
        body = value
    else:
        raise TouchTransportError("websocket_message_type_invalid")
    if len(body) > MAX_WSS_FRAME_BYTES:
        raise TouchTransportError("wss_frame_too_large")
    return body


def websockets_wss_exchange(
    request: BoundRequest,
    *,
    max_open_seconds: int,
    max_stream_bytes: int,
    max_notifications: int,
) -> WssCapture:
    """Open one non-reconnecting WSS session and close it at the first cap."""

    if request.transport != "WSS":
        raise TouchProbeContractError("wss_request_expected")
    if max_open_seconds != WSS_CAPTURE_SECONDS:
        raise TouchProbeContractError("wss_elapsed_cap_drift")
    if not 1 <= max_stream_bytes <= min(
        STREAM_BYTES_CAP,
        MAX_ADMITTED_RECEIVED_BYTES,
    ):
        raise TouchProbeContractError("wss_stream_cap_drift")
    if max_notifications != NOTIFICATION_CAP:
        raise TouchProbeContractError("wss_notification_cap_drift")

    from websockets.exceptions import ConnectionClosed, PayloadTooBig
    from websockets.sync.client import connect

    acknowledgement = b""
    acknowledgement_at: datetime | None = None
    notifications: list[bytes] = []
    notification_times: list[datetime] = []
    stream_bytes = 0
    started = time.monotonic()
    websocket: Any | None = None

    def captured(
        terminal_class: str,
        error_class: str | None,
        stop_reason: str,
    ) -> WssCapture:
        return WssCapture(
            acknowledgement=acknowledgement,
            notifications=tuple(notifications),
            acknowledgement_observed_at=acknowledgement_at,
            notification_observed_at=tuple(notification_times),
            terminal_class=terminal_class,
            error_class=error_class,
            stop_reason=stop_reason,
        )

    try:
        websocket = connect(
            request.url,
            open_timeout=5.0,
            close_timeout=1.0,
            max_size=MAX_WSS_FRAME_BYTES,
            max_queue=1,
            compression=None,
            additional_headers=dict(request.headers),
            ping_interval=20.0,
            ping_timeout=10.0,
            proxy=None,
        )
        websocket.send(request.body.decode("utf-8"))
        acknowledgement = _bounded_frame(
            websocket.recv(timeout=min(5.0, max_open_seconds))
        )
        acknowledgement_at = datetime.now(UTC)
        stream_bytes = len(acknowledgement)
        while True:
            remaining = max_open_seconds - (time.monotonic() - started)
            if remaining <= 0:
                return captured("BOUND_REACHED", None, "ELAPSED_CAP")
            if len(notifications) >= max_notifications:
                return captured("BOUND_REACHED", None, "NOTIFICATION_CAP")
            if max_stream_bytes - stream_bytes < MAX_WSS_FRAME_BYTES:
                return captured("BOUND_REACHED", None, "STREAM_GUARD")
            try:
                frame = websocket.recv(timeout=remaining)
            except TimeoutError:
                return captured("BOUND_REACHED", None, "ELAPSED_CAP")
            body = _bounded_frame(frame)
            notifications.append(body)
            notification_times.append(datetime.now(UTC))
            stream_bytes += len(body)
    except PayloadTooBig:
        return captured(
            "RESPONSE_TOO_LARGE",
            "wss_frame_too_large",
            "FRAME_LIMIT",
        )
    except ConnectionClosed:
        return captured(
            "REMOTE_CLOSED",
            "wss_remote_closed",
            "REMOTE_CLOSED",
        )
    except (TimeoutError, socket.timeout):
        return captured(
            "TIMEOUT",
            "wss_open_or_ack_timeout",
            "OPEN_OR_ACK_TIMEOUT",
        )
    except (OSError, ssl.SSLError, ConnectionError):
        return captured(
            "DNS_OR_TLS",
            "wss_connection_failed",
            "CONNECTION_FAILURE",
        )
    except TouchTransportError as exc:
        return captured("RESPONSE_TOO_LARGE", str(exc), "FRAME_LIMIT")
    except Exception:
        return captured(
            "TRANSPORT_FAILURE",
            "wss_unclassified_transport_failure",
            "TRANSPORT_FAILURE",
        )
    finally:
        if websocket is not None:
            try:
                websocket.close()
            except Exception:
                pass


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        raise TouchTransportError("http_redirect_forbidden")


def stdlib_http_exchange(
    request: BoundRequest,
    *,
    max_response_bytes: int,
) -> HttpCapture:
    """Execute one bounded read-only RPC call with no redirect or retry."""

    if request.transport != "HTTP":
        raise TouchProbeContractError("http_request_expected")
    if not 1 <= max_response_bytes <= MAX_HTTP_RESPONSE_BYTES:
        raise TouchProbeContractError("http_response_cap_drift")
    outgoing = urllib.request.Request(
        request.url,
        data=request.body,
        headers=dict(request.headers),
        method=request.method,
    )
    try:
        with urllib.request.build_opener(_NoRedirectHandler()).open(
            outgoing,
            timeout=0.75,
        ) as response:
            body = response.read(max_response_bytes + 1)
            if len(body) > max_response_bytes:
                return HttpCapture(
                    status_code=int(response.status),
                    body=b"",
                    terminal_class="RESPONSE_TOO_LARGE",
                    error_class="http_response_too_large",
                    received_bytes=max_response_bytes + 1,
                )
            return HttpCapture(
                status_code=int(response.status),
                body=body,
                terminal_class="SUCCESS",
                error_class=None,
                received_bytes=len(body),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(max_response_bytes + 1)
        if len(body) > max_response_bytes:
            body = b""
        return HttpCapture(
            status_code=exc.code,
            body=body,
            terminal_class="HTTP_ERROR",
            error_class=f"http_status_{exc.code}",
            received_bytes=len(body),
        )
    except TouchTransportError as exc:
        return HttpCapture(
            status_code=None,
            body=b"",
            terminal_class="REDIRECT",
            error_class=str(exc),
            received_bytes=0,
        )
    except (TimeoutError, socket.timeout):
        return HttpCapture(
            status_code=None,
            body=b"",
            terminal_class="TIMEOUT",
            error_class="http_timeout",
            received_bytes=0,
        )
    except (
        urllib.error.URLError,
        ssl.SSLError,
        socket.gaierror,
        ConnectionError,
    ):
        return HttpCapture(
            status_code=None,
            body=b"",
            terminal_class="DNS_OR_TLS",
            error_class="http_connection_failed",
            received_bytes=0,
        )
    except OSError:
        return HttpCapture(
            status_code=None,
            body=b"",
            terminal_class="TRANSPORT_FAILURE",
            error_class="http_os_error",
            received_bytes=0,
        )


@dataclass(frozen=True, slots=True)
class ParsedTouchNotification:
    slot: int
    signature: str
    transaction_succeeded: bool
    logs_truncated: bool
    decoded_events: tuple[DecodedTradeEvent, ...]
    unsupported_pumpswap_program_data: int


def parse_subscription_ack(body: bytes) -> int:
    document = _parse_json("wss_ack", body)
    _exact_keys("wss_ack", document, {"id", "jsonrpc", "result"})
    if (
        document["id"] != LOGS_SUBSCRIBE_REQUEST_ID
        or document["jsonrpc"] != "2.0"
    ):
        raise TouchNotificationError("wss_ack_identity_drift")
    subscription_id = document["result"]
    if (
        isinstance(subscription_id, bool)
        or not isinstance(subscription_id, int)
        or subscription_id < 0
    ):
        raise TouchNotificationError("wss_subscription_id_invalid")
    return subscription_id


def _event_discriminator(line: str) -> bytes | None:
    if not line.startswith(PROGRAM_DATA_PREFIX):
        return None
    encoded = line[len(PROGRAM_DATA_PREFIX) :]
    if not encoded or encoded.strip() != encoded:
        raise TouchProtocolDriftError("program_data_base64_not_canonical")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TouchProtocolDriftError("program_data_base64_invalid") from exc
    if len(payload) < 8:
        raise TouchProtocolDriftError("program_data_discriminator_missing")
    if len(payload) > MAX_EVENT_PAYLOAD_BYTES:
        raise TouchProtocolDriftError("program_data_payload_too_large")
    return payload[:8]


def _decode_attributed_events(
    plan: PumpSwapIdlPlan,
    *,
    logs: Sequence[str],
    transaction_succeeded: bool,
    allow_unclosed_stack: bool,
) -> tuple[tuple[DecodedTradeEvent, ...], int]:
    stack: list[str] = []
    decoded: list[DecodedTradeEvent] = []
    unsupported = 0
    for line in logs:
        invoke = _INVOKE_RE.fullmatch(line)
        if invoke:
            if int(invoke.group(2)) != len(stack) + 1:
                raise TouchProtocolDriftError("program_invoke_depth_invalid")
            stack.append(invoke.group(1))
            continue
        complete = _COMPLETE_RE.fullmatch(line)
        if complete:
            if not stack or stack[-1] != complete.group(1):
                raise TouchProtocolDriftError(
                    "program_completion_stack_mismatch"
                )
            stack.pop()
            continue
        discriminator = _event_discriminator(line)
        if discriminator is None:
            continue
        if not stack:
            raise TouchProtocolDriftError("program_data_without_invocation")
        if stack[-1] != plan.program_id or not transaction_succeeded:
            continue
        if discriminator not in plan.event_by_discriminator:
            unsupported += 1
            continue
        try:
            event = decode_pumpswap_program_data(
                plan,
                log_line=line,
                emitting_program_id=stack[-1],
                transaction_succeeded=True,
            )
        except PumpSwapDecodeError as exc:
            raise TouchProtocolDriftError(
                f"pinned_event_decode_failed:{exc}"
            ) from exc
        if event is None:
            raise TouchProtocolDriftError("successful_event_not_decoded")
        decoded.append(event)
    if stack and not allow_unclosed_stack:
        raise TouchProtocolDriftError("program_invocation_unclosed")
    return tuple(decoded), unsupported


def parse_logs_notification(
    body: bytes,
    *,
    expected_subscription_id: int,
    plan: PumpSwapIdlPlan,
) -> ParsedTouchNotification:
    document = _parse_json("logs_notification", body)
    _exact_keys(
        "logs_notification",
        document,
        {"jsonrpc", "method", "params"},
    )
    if (
        document["jsonrpc"] != "2.0"
        or document["method"] != "logsNotification"
    ):
        raise TouchNotificationError("logs_notification_identity_drift")
    params = document["params"]
    if not isinstance(params, Mapping):
        raise TouchNotificationError("logs_notification_params_invalid")
    _exact_keys("logs_notification_params", params, {"result", "subscription"})
    if params["subscription"] != expected_subscription_id:
        raise TouchNotificationError("logs_subscription_id_mismatch")
    result = params["result"]
    if not isinstance(result, Mapping):
        raise TouchNotificationError("logs_notification_result_invalid")
    _exact_keys("logs_notification_result", result, {"context", "value"})
    context = result["context"]
    if not isinstance(context, Mapping) or not {"slot"} <= set(context) <= {
        "slot",
        "apiVersion",
    }:
        raise TouchNotificationError("logs_context_keys_drift")
    slot = context["slot"]
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise TouchNotificationError("logs_context_slot_invalid")
    value = result["value"]
    if not isinstance(value, Mapping):
        raise TouchNotificationError("logs_notification_value_invalid")
    _exact_keys("logs_notification_value", value, {"err", "logs", "signature"})
    signature = _validate_signature(value["signature"])
    logs = value["logs"]
    if (
        isinstance(logs, (str, bytes))
        or not isinstance(logs, Sequence)
        or not all(isinstance(line, str) for line in logs)
    ):
        raise TouchNotificationError("logs_value_invalid")
    truncation = [
        index for index, line in enumerate(logs) if line == _LOG_TRUNCATED_MARKER
    ]
    if truncation and truncation != [len(logs) - 1]:
        raise TouchProtocolDriftError("program_log_truncation_marker_invalid")
    succeeded = value["err"] is None
    decoded, unsupported = _decode_attributed_events(
        plan,
        logs=logs,
        transaction_succeeded=succeeded,
        allow_unclosed_stack=bool(truncation),
    )
    if truncation:
        decoded = ()
        unsupported = 0
    return ParsedTouchNotification(
        slot=slot,
        signature=signature,
        transaction_succeeded=succeeded,
        logs_truncated=bool(truncation),
        decoded_events=decoded,
        unsupported_pumpswap_program_data=unsupported,
    )


def validate_get_transaction_response(
    body: bytes,
    *,
    request_id: str,
    expected_signature: str | None = None,
) -> dict[str, JsonValue]:
    document = _parse_json("get_transaction_response", body)
    if set(document) not in (
        {"id", "jsonrpc", "result"},
        {"error", "id", "jsonrpc"},
    ):
        raise TouchNotificationError("get_transaction_response_keys_drift")
    if document["id"] != request_id or document["jsonrpc"] != "2.0":
        raise TouchNotificationError("get_transaction_response_identity_drift")
    if "error" in document:
        return {
            "result_present": False,
            "terminal": "TYPED_PROVIDER_FAILURE",
        }
    result = document["result"]
    if result is None:
        return {
            "result_present": False,
            "terminal": "FIELD_COVERAGE_GAP_OBSERVED",
        }
    if not isinstance(result, Mapping):
        raise TouchNotificationError("get_transaction_result_schema_drift")
    required_result_keys = {
        "blockTime",
        "meta",
        "slot",
        "transaction",
        "version",
    }
    if set(result) != required_result_keys:
        raise TouchNotificationError("get_transaction_result_keys_drift")
    slot = result["slot"]
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise TouchNotificationError("get_transaction_slot_invalid")
    block_time = result["blockTime"]
    if block_time is not None and (
        isinstance(block_time, bool) or not isinstance(block_time, int)
    ):
        raise TouchNotificationError("get_transaction_block_time_invalid")
    meta = result["meta"]
    if not isinstance(meta, Mapping):
        return {
            "result_present": True,
            "terminal": "FIELD_COVERAGE_GAP_OBSERVED",
        }
    if meta.get("err") is not None:
        raise TouchNotificationError("get_transaction_success_mismatch")
    transaction = result["transaction"]
    if not isinstance(transaction, Mapping):
        raise TouchNotificationError("get_transaction_transaction_invalid")
    message = transaction.get("message")
    signatures = transaction.get("signatures")
    if not isinstance(message, Mapping):
        raise TouchNotificationError("get_transaction_message_invalid")
    if (
        isinstance(signatures, (str, bytes))
        or not isinstance(signatures, Sequence)
        or not all(isinstance(item, str) for item in signatures)
    ):
        raise TouchNotificationError("get_transaction_signatures_invalid")
    if expected_signature is not None and expected_signature not in signatures:
        raise TouchNotificationError("get_transaction_signature_mismatch")
    account_keys = message.get("accountKeys")
    instructions = message.get("instructions")
    if (
        isinstance(account_keys, (str, bytes))
        or not isinstance(account_keys, Sequence)
        or not all(isinstance(item, str) for item in account_keys)
    ):
        raise TouchNotificationError("get_transaction_account_keys_invalid")
    if (
        isinstance(instructions, (str, bytes))
        or not isinstance(instructions, Sequence)
    ):
        raise TouchNotificationError("get_transaction_instructions_invalid")
    loaded = meta.get("loadedAddresses", {})
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, Mapping):
        raise TouchNotificationError("get_transaction_loaded_addresses_invalid")
    loaded_keys: list[str] = []
    for mode in ("writable", "readonly"):
        values = loaded.get(mode, [])
        if (
            isinstance(values, (str, bytes))
            or not isinstance(values, Sequence)
            or not all(isinstance(item, str) for item in values)
        ):
            raise TouchNotificationError(
                "get_transaction_loaded_addresses_invalid"
            )
        loaded_keys.extend(values)
    if PUMPSWAP_PROGRAM_ID not in tuple(account_keys) + tuple(loaded_keys):
        raise TouchNotificationError("get_transaction_pumpswap_program_missing")
    for name in ("preTokenBalances", "postTokenBalances", "logMessages"):
        values = meta.get(name)
        if (
            isinstance(values, (str, bytes))
            or not isinstance(values, Sequence)
        ):
            raise TouchNotificationError(f"get_transaction_{name}_invalid")
    return {
        "account_key_count": len(account_keys) + len(loaded_keys),
        "post_token_balance_count": len(meta["postTokenBalances"]),
        "pre_token_balance_count": len(meta["preTokenBalances"]),
        "result_present": True,
        "terminal": "FIELD_COVERAGE_CANDIDATE",
    }


@dataclass(frozen=True, slots=True, repr=False)
class ProbeEvidence:
    kind: str
    body: bytes = field(repr=False)
    request: dict[str, JsonValue]
    observed_at: datetime
    response_status: RawResponseStatus
    error_class: str | None
    metadata: dict[str, JsonValue]


class DurableTouchProbeSink:
    """Buffer redacted TASK-06 envelopes and publish one bounded partition."""

    def __init__(self, *, raw_root: Path, run_id: str) -> None:
        if not raw_root.is_absolute():
            raise TouchProbeContractError("raw_root_must_be_absolute")
        if _SAFE_RUN_ID_RE.fullmatch(run_id) is None:
            raise TouchProbeContractError("run_id_invalid")
        self.run_id = run_id
        self.run_directory = raw_root / RAW_LOGICAL_ROOT / f"run={run_id}"
        if self.run_directory.exists():
            raise TouchProbeContractError("run_output_already_exists")
        self.run_directory.mkdir(parents=True, exist_ok=False)
        self.receipt_directory = self.run_directory / "receipts"
        self.receipt_directory.mkdir()
        self._events: list[Any] = []
        self._finalized = False
        self._stored_bytes = 0
        self._stored_event_count = 0
        self._complete = False
        self._finalize_error_class: str | None = None

    @property
    def logical_root(self) -> str:
        return f"{RAW_LOGICAL_ROOT}/run={self.run_id}"

    def append(self, evidence: ProbeEvidence) -> None:
        if self._finalized:
            raise TouchProbeStopError("durable_sink_already_finalized")
        ingested_at = max(datetime.now(UTC), evidence.observed_at)
        event = build_raw_api_event(
            source="SOLANA_STANDARD_RPC",
            source_version=f"task09-probe-{TRANSPORT_CONTRACT_VERSION}",
            endpoint_or_method=(
                f"{evidence.request['transport']} "
                f"{evidence.request['rpc_method']}"
            ),
            request_identity={
                "kind": evidence.kind,
                "metadata": evidence.metadata,
                "request": evidence.request,
                "run_id": self.run_id,
            },
            response_body=evidence.body,
            response_status=evidence.response_status,
            error_class=evidence.error_class,
            observed_at=evidence.observed_at,
            available_to_strategy_at=evidence.observed_at,
            ingested_at=ingested_at,
            first_reliable_available_at=evidence.observed_at,
            provider_version=f"official-public-rpc-as-of-{TRANSPORT_AS_OF}",
            schema_version="1.0",
            protocol_version=PUMPSWAP_IDL_COMMIT,
            quality_flags="TASK09_TOUCH_ONLY_NOT_FILLABLE",
        )
        self._events.append(event)

    def finalize(self, *, max_stored_bytes: int) -> int:
        if self._finalized:
            return self._stored_bytes
        if max_stored_bytes <= STORAGE_METADATA_RESERVE_BYTES:
            raise TouchProbeStopError("stored_byte_allowance_insufficient")
        if not self._events:
            raise TouchProbeStopError("durable_sink_has_no_evidence")
        parquet_budget = max_stored_bytes - STORAGE_METADATA_RESERVE_BYTES
        policy = StorageBudgetPolicy(
            max_partition_bytes=parquet_budget,
            max_dataset_bytes=parquet_budget,
            min_free_bytes=1_073_741_824,
            warning_threshold_bps=9000,
            forecast_partition_count=1,
        )
        created_at = max(event.ingested_at for event in self._events)
        reliable_at = max(
            created_at,
            *(event.first_reliable_available_at for event in self._events),
        )
        candidate_count = len(self._events)
        result = None
        while candidate_count:
            try:
                result = write_budgeted_raw_event_partition(
                    root=self.run_directory,
                    dataset_id=DATASET_ID,
                    dataset_version=DATASET_VERSION,
                    partition_id=f"{self.run_id}-probe",
                    logical_location="partitions/probe.parquet",
                    events=self._events[:candidate_count],
                    created_at=created_at,
                    first_reliable_available_at=reliable_at,
                    budget_policy=policy,
                )
            except StorageBudgetExceededError as exc:
                self._finalize_error_class = str(exc)
                candidate_count = 0 if candidate_count == 1 else max(
                    1,
                    candidate_count // 2,
                )
                continue
            break
        observed: Sequence[Any] = ()
        partition_bytes = 0
        manifest_bytes = b""
        if result is not None:
            observed = verify_raw_event_partition(
                root=self.run_directory,
                manifest=result.manifest,
            )
            if len(observed) != candidate_count:
                raise TouchProbeStopError(
                    "durable_partition_row_count_mismatch"
                )
            partition_bytes = result.file_size_bytes
            manifest_bytes = canonical_manifest_bytes(result.manifest) + b"\n"
        self._stored_event_count = len(observed)
        self._complete = self._stored_event_count == len(self._events)
        if not self._complete and self._finalize_error_class is None:
            self._finalize_error_class = "durable_partition_incomplete"
        receipt_bytes = _canonical_json_bytes(
            {
                "cash_spend_usd_cents": 0,
                "complete": self._complete,
                "dataset_id": DATASET_ID,
                "dataset_version": DATASET_VERSION,
                "event_count_received": len(self._events),
                "event_count_stored": self._stored_event_count,
                "finalize_error_class": self._finalize_error_class,
                "logical_root": self.logical_root,
                "omitted_event_count": (
                    len(self._events) - self._stored_event_count
                ),
                "retries": 0,
                "run_id": self.run_id,
                "transport_contract_version": TRANSPORT_CONTRACT_VERSION,
            }
        ) + b"\n"
        metadata_bytes = len(manifest_bytes) + len(receipt_bytes)
        if metadata_bytes > STORAGE_METADATA_RESERVE_BYTES:
            raise TouchProbeStopError("storage_metadata_reserve_exceeded")
        total = partition_bytes + metadata_bytes
        if total > max_stored_bytes:
            raise TouchProbeStopError("stored_byte_allowance_exceeded")
        if manifest_bytes:
            (self.receipt_directory / "probe.manifest.json").write_bytes(
                manifest_bytes
            )
        (self.receipt_directory / "probe.receipt.json").write_bytes(
            receipt_bytes
        )
        self._stored_bytes = total
        self._finalized = True
        return total

    def safe_receipt(self) -> dict[str, JsonValue]:
        return {
            "complete": self._complete,
            "event_count": len(self._events),
            "finalize_error_class": self._finalize_error_class,
            "finalized": self._finalized,
            "logical_root": self.logical_root,
            "run_id": self.run_id,
            "stored_event_count": self._stored_event_count,
            "stored_bytes": self._stored_bytes,
        }


@dataclass(frozen=True, slots=True)
class ProbeSummary:
    status: str
    elapsed_seconds: float
    notifications: int
    successful_notifications: int
    failed_notifications: int
    truncated_notifications: int
    decoded_events: int
    unsupported_program_data: int
    unique_followup_candidates: int
    rpc_followups: int
    stream_bytes: int
    received_bytes: int
    stored_bytes: int
    wss_stop_reason: str
    stop_error_class: str | None

    def safe_receipt(self) -> dict[str, JsonValue]:
        return {
            "cash_spend_usd_cents": 0,
            "concurrency": 1,
            "decoded_events": self.decoded_events,
            "elapsed_seconds": self.elapsed_seconds,
            "failed_notifications": self.failed_notifications,
            "notifications": self.notifications,
            "credentials_used": False,
            "received_and_stored_bytes": self.received_bytes
            + self.stored_bytes,
            "received_bytes": self.received_bytes,
            "retries": 0,
            "rpc_followups": self.rpc_followups,
            "status": self.status,
            "stop_error_class": self.stop_error_class,
            "stored_bytes": self.stored_bytes,
            "stream_bytes": self.stream_bytes,
            "successful_notifications": self.successful_notifications,
            "truncated_notifications": self.truncated_notifications,
            "unique_followup_candidates": self.unique_followup_candidates,
            "unsupported_program_data": self.unsupported_program_data,
            "wss_stop_reason": self.wss_stop_reason,
        }


class TouchProbeRunner:
    """Execute exactly one public standard-RPC capture with no retry."""

    def __init__(
        self,
        *,
        plan: PumpSwapIdlPlan,
        gate: ExternalExecutionGate,
        sink: DurableTouchProbeSink,
        wss_exchange: WssExchange,
        http_exchange: HttpExchange,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.plan = plan
        self.gate = gate
        self.sink = sink
        self.wss_exchange = wss_exchange
        self.http_exchange = http_exchange
        self.now = now
        self.clock = clock

    def _append(
        self,
        *,
        kind: str,
        body: bytes,
        request: BoundRequest,
        observed_at: datetime,
        status: RawResponseStatus = RawResponseStatus.SUCCESS,
        error_class: str | None = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> None:
        self.sink.append(
            ProbeEvidence(
                kind=kind,
                body=body,
                request=request.safe_receipt(),
                observed_at=observed_at,
                response_status=status,
                error_class=error_class,
                metadata=metadata or {},
            )
        )

    def run(self) -> ProbeSummary:
        self.gate.require()
        if self.plan.program_id != PUMPSWAP_PROGRAM_ID:
            raise TouchProbeContractError("pumpswap_program_plan_drift")
        started = self.clock()
        request = bind_logs_subscribe()
        capture = self.wss_exchange(
            request,
            max_open_seconds=WSS_CAPTURE_SECONDS,
            max_stream_bytes=MAX_ADMITTED_RECEIVED_BYTES,
            max_notifications=NOTIFICATION_CAP,
        )
        if len(capture.notifications) > NOTIFICATION_CAP:
            raise TouchProbeStopError("notification_cap_exceeded")
        if len(capture.notifications) != len(capture.notification_observed_at):
            raise TouchProbeStopError("notification_timestamp_count_mismatch")
        if capture.acknowledgement and capture.acknowledgement_observed_at is None:
            raise TouchProbeStopError("acknowledgement_timestamp_missing")
        received = len(capture.acknowledgement) + sum(
            len(body) for body in capture.notifications
        )
        if received > MAX_ADMITTED_RECEIVED_BYTES:
            raise TouchProbeStopError("admission_received_bytes_exceeded")
        stream_bytes = received
        stop_error = capture.error_class
        successful = 0
        failed = 0
        truncated = 0
        decoded_events = 0
        unsupported = 0
        candidates: list[str] = []
        seen: set[str] = set()
        if capture.acknowledgement:
            observed = capture.acknowledgement_observed_at or self.now()
            try:
                subscription_id = parse_subscription_ack(
                    capture.acknowledgement
                )
                self._append(
                    kind="WSS_SUBSCRIPTION_ACK",
                    body=capture.acknowledgement,
                    request=request,
                    observed_at=observed,
                    metadata={"subscription_id": subscription_id},
                )
            except Exception as exc:
                self._append(
                    kind="WSS_SUBSCRIPTION_ACK",
                    body=capture.acknowledgement,
                    request=request,
                    observed_at=observed,
                    status=RawResponseStatus.INVALID_RESPONSE,
                    error_class=_safe_error_code(exc),
                )
                self._finalize(received)
                raise
        else:
            self._append(
                kind="WSS_TERMINAL",
                body=b"",
                request=request,
                observed_at=self.now(),
                status=RawResponseStatus.PROVIDER_ERROR,
                error_class=capture.error_class or "wss_no_ack",
                metadata={"stop_reason": capture.stop_reason},
            )
            stored = self._finalize(received)
            return ProbeSummary(
                status="TYPED_PROVIDER_FAILURE",
                elapsed_seconds=self.clock() - started,
                notifications=0,
                successful_notifications=0,
                failed_notifications=0,
                truncated_notifications=0,
                decoded_events=0,
                unsupported_program_data=0,
                unique_followup_candidates=0,
                rpc_followups=0,
                stream_bytes=stream_bytes,
                received_bytes=received,
                stored_bytes=stored,
                wss_stop_reason=capture.stop_reason,
                stop_error_class=capture.error_class or "wss_no_ack",
            )

        for body, observed in zip(
            capture.notifications,
            capture.notification_observed_at,
        ):
            try:
                parsed = parse_logs_notification(
                    body,
                    expected_subscription_id=subscription_id,
                    plan=self.plan,
                )
                if parsed.transaction_succeeded:
                    successful += 1
                else:
                    failed += 1
                if parsed.logs_truncated:
                    truncated += 1
                decoded_events += len(parsed.decoded_events)
                unsupported += parsed.unsupported_pumpswap_program_data
                self._append(
                    kind="WSS_LOGS_NOTIFICATION",
                    body=body,
                    request=request,
                    observed_at=observed,
                    metadata={
                        "decoded_event_names": [
                            event.event_name
                            for event in parsed.decoded_events
                        ],
                        "logs_truncated": parsed.logs_truncated,
                        "signature_sha256": hashlib.sha256(
                            parsed.signature.encode("ascii")
                        ).hexdigest(),
                        "slot": parsed.slot,
                        "transaction_succeeded": (
                            parsed.transaction_succeeded
                        ),
                        "unsupported_program_data": (
                            parsed.unsupported_pumpswap_program_data
                        ),
                    },
                )
                if (
                    parsed.transaction_succeeded
                    and parsed.decoded_events
                    and parsed.signature not in seen
                    and len(candidates) < GET_TRANSACTION_CAP
                ):
                    seen.add(parsed.signature)
                    candidates.append(parsed.signature)
            except (TouchProtocolDriftError, PumpSwapDecodeError) as exc:
                self._append(
                    kind="WSS_LOGS_NOTIFICATION",
                    body=body,
                    request=request,
                    observed_at=observed,
                    status=RawResponseStatus.INVALID_RESPONSE,
                    error_class=_safe_error_code(exc),
                )
                self._finalize(received)
                raise
            except TouchProbeStopError as exc:
                self._append(
                    kind="WSS_LOGS_NOTIFICATION",
                    body=body,
                    request=request,
                    observed_at=observed,
                    status=RawResponseStatus.INVALID_RESPONSE,
                    error_class=_safe_error_code(exc),
                )
                self._finalize(received)
                raise

        followups = 0
        followup_result_present = 0
        for ordinal, signature in enumerate(candidates, start=1):
            if self.clock() - started >= ELAPSED_SECONDS_CAP - 0.75:
                break
            remaining_admission = MAX_ADMITTED_RECEIVED_BYTES - received
            if remaining_admission <= 0:
                break
            response_cap = min(MAX_HTTP_RESPONSE_BYTES, remaining_admission)
            followup = bind_get_transaction(signature, ordinal)
            capture_http = self.http_exchange(
                followup,
                max_response_bytes=response_cap,
            )
            followups += 1
            received += capture_http.received_bytes
            observed = self.now()
            if capture_http.terminal_class != "SUCCESS":
                self._append(
                    kind="GET_TRANSACTION",
                    body=capture_http.body,
                    request=followup,
                    observed_at=observed,
                    status=RawResponseStatus.PROVIDER_ERROR,
                    error_class=capture_http.error_class,
                    metadata={
                        "signature_sha256": hashlib.sha256(
                            signature.encode("ascii")
                        ).hexdigest()
                    },
                )
                stop_error = capture_http.error_class
                continue
            try:
                coverage = validate_get_transaction_response(
                    capture_http.body,
                    request_id=followup.request_id,
                    expected_signature=signature,
                )
            except TouchProbeStopError as exc:
                self._append(
                    kind="GET_TRANSACTION",
                    body=capture_http.body,
                    request=followup,
                    observed_at=observed,
                    status=RawResponseStatus.INVALID_RESPONSE,
                    error_class=_safe_error_code(exc),
                    metadata={
                        "signature_sha256": hashlib.sha256(
                            signature.encode("ascii")
                        ).hexdigest()
                    },
                )
                self._finalize(received)
                raise
            followup_result_present += int(
                coverage["result_present"] is True
            )
            self._append(
                kind="GET_TRANSACTION",
                body=capture_http.body,
                request=followup,
                observed_at=observed,
                metadata={
                    "coverage_terminal": coverage["terminal"],
                    "signature_sha256": hashlib.sha256(
                        signature.encode("ascii")
                    ).hexdigest(),
                },
            )

        if capture.terminal_class != "BOUND_REACHED":
            self._append(
                kind="WSS_TERMINAL",
                body=b"",
                request=request,
                observed_at=self.now(),
                status=RawResponseStatus.PROVIDER_ERROR,
                error_class=capture.error_class,
                metadata={"stop_reason": capture.stop_reason},
            )
        stored = self._finalize(received)
        if capture.terminal_class != "BOUND_REACHED":
            status = "TYPED_PROVIDER_FAILURE"
        elif decoded_events == 0:
            status = (
                "FIELD_COVERAGE_GAP_OBSERVED"
                if unsupported
                else "NOT_TESTABLE_IN_WINDOW"
            )
        elif followup_result_present:
            status = "FIELD_COVERAGE_CANDIDATE"
        else:
            status = "FIELD_COVERAGE_GAP_OBSERVED"
        return ProbeSummary(
            status=status,
            elapsed_seconds=self.clock() - started,
            notifications=len(capture.notifications),
            successful_notifications=successful,
            failed_notifications=failed,
            truncated_notifications=truncated,
            decoded_events=decoded_events,
            unsupported_program_data=unsupported,
            unique_followup_candidates=len(candidates),
            rpc_followups=followups,
            stream_bytes=stream_bytes,
            received_bytes=received,
            stored_bytes=stored,
            wss_stop_reason=capture.stop_reason,
            stop_error_class=stop_error,
        )

    def _finalize(self, received_bytes: int) -> int:
        allowance = RECEIVED_AND_STORED_BYTES_CAP - received_bytes
        if allowance <= STORAGE_METADATA_RESERVE_BYTES:
            raise TouchProbeStopError("combined_byte_budget_exhausted")
        stored = self.sink.finalize(max_stored_bytes=allowance)
        if received_bytes + stored > RECEIVED_AND_STORED_BYTES_CAP:
            raise TouchProbeStopError("received_and_stored_cap_exceeded")
        return stored


def default_probe_run_id(now: datetime | None = None) -> str:
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise TouchProbeContractError("run_time_not_aware")
    return instant.astimezone(UTC).strftime("t09a4-%Y%m%dT%H%M%SZ")


def safe_preflight_summary(plan: PumpSwapIdlPlan) -> dict[str, JsonValue]:
    """Return the exact offline request plan without opening a socket."""

    if plan.program_id != PUMPSWAP_PROGRAM_ID:
        raise TouchProbeContractError("pumpswap_program_plan_drift")
    if MODELED_HELIUS_CREDITS_MAX > HELIUS_CREDIT_CAP:
        raise TouchProbeContractError("modeled_credit_cap_exceeded")
    return {
        "admission_received_bytes_cap": MAX_ADMITTED_RECEIVED_BYTES,
        "atom": "T09-A4",
        "cash_spend_usd_cents": CASH_SPEND_USD_CENTS_CAP,
        "concurrency": CONCURRENCY_CAP,
        "credentials_required": False,
        "durable_output_created": False,
        "durable_output_logical_root": RAW_LOGICAL_ROOT,
        "elapsed_seconds_cap": ELAPSED_SECONDS_CAP,
        "external_authority_required": True,
        "get_transaction_cap": GET_TRANSACTION_CAP,
        "helius_fallback_enabled": False,
        "modeled_helius_credits_max": MODELED_HELIUS_CREDITS_MAX,
        "network_authorized": False,
        "notification_cap": NOTIFICATION_CAP,
        "provider_requests_planned": 0,
        "public_endpoint_host": SOLANA_MAINNET_HOST,
        "received_and_stored_bytes_cap": RECEIVED_AND_STORED_BYTES_CAP,
        "retries": RETRY_CAP,
        "stream_bytes_cap": STREAM_BYTES_CAP,
        "transport_contract_version": TRANSPORT_CONTRACT_VERSION,
        "wss_capture_seconds": WSS_CAPTURE_SECONDS,
        "wss_connections_cap": WSS_CONNECTION_CAP,
        "wss_method": "logsSubscribe",
        "wss_program_id": PUMPSWAP_PROGRAM_ID,
        "wss_subscriptions_cap": WSS_SUBSCRIPTION_CAP,
    }
