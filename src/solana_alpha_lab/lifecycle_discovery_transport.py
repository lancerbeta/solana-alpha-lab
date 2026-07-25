"""Offline-tested transport boundary for the TASK-08 cheapest probe."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
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
from types import MappingProxyType
from typing import Any, Protocol, TypeAlias

from solana_alpha_lab.contracts.schema_v1 import RawResponseStatus
from solana_alpha_lab.lifecycle_discovery import (
    DiscoveryPlan,
    JsonValue,
    validate_durable_metadata,
    validate_probe_usage,
)
from solana_alpha_lab.pump_event_decoder import (
    MAX_EVENT_PAYLOAD_BYTES,
    PROGRAM_DATA_PREFIX,
    PUMP_PROGRAM_ID,
    DecodedPumpEvent,
    PumpEventDecodeError,
    PumpEventPlan,
    decode_pump_program_data,
)
from solana_alpha_lab.storage import (
    StorageBudgetPolicy,
    StorageBudgetExceededError,
    build_raw_api_event,
    canonical_manifest_bytes,
    verify_raw_event_partition,
    write_budgeted_raw_event_partition,
)

TRANSPORT_CONTRACT_VERSION = "1.1"
TRANSPORT_AS_OF = "2026-07-25"
EXTERNAL_AUTHORITY_PHRASE = (
    "TASK08_A5_CHEAPEST_PROBE_EXTERNAL_ACCOUNT_API_RPC_WSS_RAW_WRITE"
)
NETWORK_DISABLED_IN_ATOM4 = True
NETWORK_DISABLED_BY_DEFAULT = True
WSS_CAPTURE_SECONDS = 540
TRACKER_PACING_SECONDS = 1.0
MAX_HTTP_RESPONSE_BYTES = 1_000_000
MAX_WSS_FRAME_BYTES = 100_000
DEFAULT_HTTP_TIMEOUT_SECONDS = 1.5
MAX_ADMITTED_RECEIVED_BYTES = 900_000
TRACKER_MAX_RESPONSE_BYTES = 200_000
TRACKER_OVERVIEW_LIMIT = 10
MAX_EVIDENCE_RECORDS = 528
MAX_REDACTED_EXPANSION_FACTOR = 3
PARQUET_ROW_RESERVE_BYTES = 2_048
PARQUET_CONTAINER_RESERVE_BYTES = 65_536
DATASET_ID = "SMIAL_TASK08_LIFECYCLE_DISCOVERY_PROBE_RAW"
DATASET_VERSION = "1.0"
RAW_LOGICAL_ROOT = "task08_lifecycle_discovery_probe_v1"
STORAGE_METADATA_RESERVE_BYTES = 65_536
LOGS_SUBSCRIBE_REQUEST_ID = "task08-logs-subscribe"
TRACKER_PATHS = (
    "/tokens/multi/all",
)
TRACKER_PHASES = ("OPEN", "CLOSE")

_HELIUS_HOST = "mainnet.helius-rpc.com"
_TRACKER_HOST = "data.solanatracker.io"
_HELIUS_WSS_BASE = f"wss://{_HELIUS_HOST}/"
_HELIUS_RPC_BASE = f"https://{_HELIUS_HOST}/"
_TRACKER_BASE = f"https://{_TRACKER_HOST}"
_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")
_INVOKE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) invoke \[([1-9][0-9]*)\]$"
)
_COMPLETE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) "
    r"(?:success|failed(?:: .*)?)$"
)
_LOG_TRUNCATED_MARKER = "Log truncated"
_FORBIDDEN_RPC_METHOD_MARKERS = (
    "send",
    "simulate",
    "sign",
    "transactioncount",
)
_FORBIDDEN_DURABLE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "password",
        "secret",
        "token",
        "url",
    }
)

JsonObject: TypeAlias = dict[str, JsonValue]


class ProbeTransportContractError(ValueError):
    """A frozen request, response or evidence boundary is invalid."""


class ExternalAuthorityRequiredError(ProbeTransportContractError):
    """The future external-action tripwire was not satisfied."""


class ProbeStopError(RuntimeError):
    """A hard cap, provider failure or schema drift stopped the probe."""


class NotificationSchemaError(ProbeStopError):
    """A WebSocket acknowledgement or notification drifted."""


class ProgramLogAttributionError(ProbeStopError):
    """A Program data line cannot be attributed to an invocation stack."""


class TransportExecutionError(ProbeStopError):
    """A concrete no-retry transport operation failed safely."""


class TrackerSnapshotError(ProbeStopError):
    """An auxiliary Tracker snapshot failed after retaining typed evidence."""


def admission_budget_proof() -> dict[str, int]:
    """Return a conservative proof that admitted evidence fits five MB."""

    admitted_body_and_wire = MAX_ADMITTED_RECEIVED_BYTES * (
        1 + MAX_REDACTED_EXPANSION_FACTOR
    )
    row_reserve = MAX_EVIDENCE_RECORDS * PARQUET_ROW_RESERVE_BYTES
    worst_case = (
        admitted_body_and_wire
        + row_reserve
        + PARQUET_CONTAINER_RESERVE_BYTES
        + STORAGE_METADATA_RESERVE_BYTES
    )
    hard_cap = 5_000_000
    if worst_case > hard_cap:
        raise ProbeTransportContractError(
            "admission_budget_proof_exceeds_hard_cap"
        )
    return {
        "admitted_received_bytes": MAX_ADMITTED_RECEIVED_BYTES,
        "hard_cap_bytes": hard_cap,
        "parquet_container_reserve_bytes": (
            PARQUET_CONTAINER_RESERVE_BYTES
        ),
        "parquet_row_reserve_bytes": row_reserve,
        "redacted_body_reserve_bytes": (
            MAX_ADMITTED_RECEIVED_BYTES
            * MAX_REDACTED_EXPANSION_FACTOR
        ),
        "remaining_safety_bytes": hard_cap - worst_case,
        "storage_metadata_reserve_bytes": STORAGE_METADATA_RESERVE_BYTES,
        "worst_case_combined_bytes": worst_case,
    }


def _validate_secret(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ProbeTransportContractError(f"{name}_must_be_text")
    if value != value.strip() or not 8 <= len(value) <= 512:
        raise ProbeTransportContractError(f"{name}_invalid")
    if any(ord(character) < 33 or ord(character) == 127 for character in value):
        raise ProbeTransportContractError(f"{name}_invalid")
    return value


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProbeTransportContractError("json_value_invalid") from exc


def _reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NotificationSchemaError("json_duplicate_key")
        result[key] = value
    return result


def _parse_json_bytes(name: str, body: bytes) -> JsonValue:
    if not isinstance(body, bytes):
        raise NotificationSchemaError(f"{name}_must_be_bytes")
    try:
        value = json.loads(
            body,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NotificationSchemaError(f"{name}_not_json") from exc
    return value


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NotificationSchemaError(f"{name}_must_be_mapping")
    if not all(isinstance(key, str) for key in value):
        raise NotificationSchemaError(f"{name}_keys_must_be_text")
    return value


def _exact_keys(
    name: str,
    value: Mapping[str, Any],
    expected: set[str],
) -> None:
    if set(value) != expected:
        raise NotificationSchemaError(f"{name}_keys_drift")


def _safe_metadata(value: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    for key in value:
        if key.casefold().replace("-", "_") in _FORBIDDEN_DURABLE_KEYS:
            raise ProbeTransportContractError("durable_auth_or_url_key_forbidden")
    document = dict(value)
    try:
        validate_durable_metadata(document)
    except ValueError as exc:
        raise ProbeTransportContractError(str(exc)) from exc
    return document


@dataclass(frozen=True, slots=True, repr=False)
class ProbeCredentials:
    """In-memory provider credentials with a redacted representation."""

    helius_api_key: str = field(repr=False)
    solana_tracker_api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        _validate_secret("helius_credential", self.helius_api_key)
        _validate_secret(
            "solana_tracker_credential",
            self.solana_tracker_api_key,
        )

    def __repr__(self) -> str:
        return "ProbeCredentials(<redacted>)"

    @property
    def explicit_secret_values(self) -> tuple[str, str]:
        return (self.helius_api_key, self.solana_tracker_api_key)


@dataclass(frozen=True, slots=True)
class ProbeAccessAttestation:
    """Local dashboard read-back required before a future external run."""

    dashboard_readback_completed: bool
    helius_credits_remaining: int
    solana_tracker_requests_remaining: int
    cash_spend_usd_cents: int = 0

    def require(self, plan: DiscoveryPlan) -> None:
        if not self.dashboard_readback_completed:
            raise ProbeTransportContractError(
                "provider_dashboard_readback_required"
            )
        values = (
            self.helius_credits_remaining,
            self.solana_tracker_requests_remaining,
            self.cash_spend_usd_cents,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ProbeTransportContractError("access_attestation_value_invalid")
        if self.helius_credits_remaining < plan.probe_budget["helius_credits"]:
            raise ProbeTransportContractError("helius_credit_headroom_insufficient")
        if (
            self.solana_tracker_requests_remaining
            < plan.probe_budget["solana_tracker_requests"]
        ):
            raise ProbeTransportContractError(
                "solana_tracker_request_headroom_insufficient"
            )
        if self.cash_spend_usd_cents != 0:
            raise ProbeTransportContractError("cash_spend_forbidden")


@dataclass(frozen=True, slots=True)
class ExternalExecutionGate:
    """Exact non-secret tripwire; human authority remains outside the code."""

    authority_phrase: str

    def require(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise ExternalAuthorityRequiredError(
                "external_authority_phrase_mismatch"
            )


@dataclass(frozen=True, slots=True, repr=False)
class BoundProbeRequest:
    """One allowlisted request whose representation never exposes secrets."""

    request_id: str
    provider: str
    transport: str
    method: str
    url: str = field(repr=False)
    headers: tuple[tuple[str, str], ...] = field(repr=False)
    body: bytes = field(repr=False)
    safe_query_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_bound_request(self)

    def __repr__(self) -> str:
        return (
            "BoundProbeRequest("
            f"request_id={self.request_id!r}, "
            f"provider={self.provider!r}, "
            f"transport={self.transport!r}, "
            f"method={self.method!r}, "
            "url=<redacted>, headers=<redacted>, body=<redacted>)"
        )

    def safe_receipt(self) -> dict[str, JsonValue]:
        split = urllib.parse.urlsplit(self.url)
        return {
            "body_bytes": len(self.body),
            "body_sha256": hashlib.sha256(self.body).hexdigest(),
            "host": split.hostname,
            "method": self.method,
            "path": split.path or "/",
            "provider": self.provider,
            "query_keys": list(self.safe_query_keys),
            "request_id": self.request_id,
            "transport": self.transport,
        }


def _validate_bound_request(request: BoundProbeRequest) -> None:
    try:
        split = urllib.parse.urlsplit(request.url)
    except ValueError as exc:
        raise ProbeTransportContractError("bound_url_invalid") from exc
    if (
        split.port is not None
        or split.username is not None
        or split.password is not None
        or split.fragment
    ):
        raise ProbeTransportContractError("bound_endpoint_not_allowlisted")
    query = urllib.parse.parse_qsl(
        split.query,
        keep_blank_values=True,
        strict_parsing=True,
    )
    query_keys = tuple(key for key, _ in query)
    if request.provider == "HELIUS":
        expected_scheme = "wss" if request.transport == "WSS" else "https"
        if (
            split.scheme != expected_scheme
            or split.hostname != _HELIUS_HOST
            or (split.path or "/") != "/"
            or query_keys != ("api-key",)
            or request.safe_query_keys
        ):
            raise ProbeTransportContractError("helius_endpoint_drift")
    elif request.provider == "SOLANA_TRACKER":
        if (
            split.scheme != "https"
            or split.hostname != _TRACKER_HOST
            or (split.path or "/") not in TRACKER_PATHS
            or query != [("limit", str(TRACKER_OVERVIEW_LIMIT))]
            or request.safe_query_keys != ("limit",)
        ):
            raise ProbeTransportContractError("tracker_endpoint_drift")
    else:
        raise ProbeTransportContractError("provider_not_allowlisted")

    header_names = tuple(key.casefold() for key, _ in request.headers)
    if request.provider == "HELIUS":
        expected_headers = (
            ("accept", "content-type", "user-agent")
            if request.transport == "HTTP"
            else ("accept", "user-agent")
        )
    else:
        expected_headers = ("accept", "user-agent", "x-api-key")
    if header_names != expected_headers:
        raise ProbeTransportContractError("request_header_set_drift")

    if request.transport == "WSS":
        if request.method != "POST":
            raise ProbeTransportContractError("wss_method_drift")
    elif request.transport == "HTTP":
        if request.provider == "HELIUS" and request.method != "POST":
            raise ProbeTransportContractError("helius_http_method_drift")
        if request.provider == "SOLANA_TRACKER" and request.method != "GET":
            raise ProbeTransportContractError("tracker_http_method_drift")
    else:
        raise ProbeTransportContractError("transport_not_allowlisted")


def _helius_url(base: str, credential: str) -> str:
    query = urllib.parse.urlencode((("api-key", credential),))
    return f"{base}?{query}"


def bind_logs_subscribe(credentials: ProbeCredentials) -> BoundProbeRequest:
    """Bind the one exact Pump logsSubscribe request."""

    body = _canonical_json_bytes(
        {
            "id": LOGS_SUBSCRIBE_REQUEST_ID,
            "jsonrpc": "2.0",
            "method": "logsSubscribe",
            "params": [
                {"mentions": [PUMP_PROGRAM_ID]},
                {"commitment": "confirmed"},
            ],
        }
    )
    return BoundProbeRequest(
        request_id=LOGS_SUBSCRIBE_REQUEST_ID,
        provider="HELIUS",
        transport="WSS",
        method="POST",
        url=_helius_url(_HELIUS_WSS_BASE, credentials.helius_api_key),
        headers=(
            ("accept", "application/json"),
            ("user-agent", "smial-task08-probe/1.0"),
        ),
        body=body,
        safe_query_keys=(),
    )


def bind_get_transaction(
    credentials: ProbeCredentials,
    *,
    signature: str,
    ordinal: int,
) -> BoundProbeRequest:
    """Bind one read-only getTransaction follow-up after a pinned event."""

    _validate_signature(signature)
    if isinstance(ordinal, bool) or not 1 <= ordinal <= 20:
        raise ProbeTransportContractError("followup_ordinal_invalid")
    request_id = f"task08-get-transaction-{ordinal:02d}"
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
    lowered = json.loads(body)["method"].casefold()
    if any(marker in lowered for marker in _FORBIDDEN_RPC_METHOD_MARKERS):
        raise ProbeTransportContractError("state_changing_rpc_method_forbidden")
    return BoundProbeRequest(
        request_id=request_id,
        provider="HELIUS",
        transport="HTTP",
        method="POST",
        url=_helius_url(_HELIUS_RPC_BASE, credentials.helius_api_key),
        headers=(
            ("accept", "application/json"),
            ("content-type", "application/json"),
            ("user-agent", "smial-task08-probe/1.0"),
        ),
        body=body,
        safe_query_keys=(),
    )


def bind_tracker_snapshot(
    credentials: ProbeCredentials,
    *,
    phase: str,
) -> BoundProbeRequest:
    """Bind one bounded read-only Solana Tracker overview snapshot."""

    if phase not in TRACKER_PHASES:
        raise ProbeTransportContractError("tracker_phase_invalid")
    path = TRACKER_PATHS[0]
    slug = path.strip("/").replace("/", "-")
    query = urllib.parse.urlencode(
        (("limit", str(TRACKER_OVERVIEW_LIMIT)),)
    )
    return BoundProbeRequest(
        request_id=(
            f"task08-tracker-{phase.casefold()}-{slug}"
            f"-limit-{TRACKER_OVERVIEW_LIMIT}"
        ),
        provider="SOLANA_TRACKER",
        transport="HTTP",
        method="GET",
        url=f"{_TRACKER_BASE}{path}?{query}",
        headers=(
            ("accept", "application/json"),
            ("user-agent", "smial-task08-probe/1.0"),
            ("x-api-key", credentials.solana_tracker_api_key),
        ),
        body=b"",
        safe_query_keys=("limit",),
    )


@dataclass(frozen=True, slots=True, repr=False)
class WssCapture:
    """One closed, non-reconnecting WSS capture returned by an adapter."""

    acknowledgement: bytes = field(repr=False)
    notifications: tuple[bytes, ...] = field(repr=False)
    acknowledgement_observed_at: datetime | None = None
    notification_observed_at: tuple[datetime, ...] = ()
    terminal_class: str = "BOUND_REACHED"
    error_class: str | None = None
    stop_reason: str = "ADAPTER_BOUND"

    def __post_init__(self) -> None:
        allowed = {
            "BOUND_REACHED",
            "DNS_OR_TLS",
            "REMOTE_CLOSED",
            "RESPONSE_TOO_LARGE",
            "TIMEOUT",
            "TRANSPORT_FAILURE",
        }
        if self.terminal_class not in allowed:
            raise ProbeTransportContractError("wss_terminal_class_invalid")
        if self.terminal_class == "BOUND_REACHED":
            if self.error_class is not None:
                raise ProbeTransportContractError(
                    "bounded_wss_capture_cannot_have_error"
                )
        elif not self.error_class:
            raise ProbeTransportContractError(
                "failed_wss_capture_requires_error"
            )
        if (
            not isinstance(self.stop_reason, str)
            or not self.stop_reason
            or len(self.stop_reason) > 80
        ):
            raise ProbeTransportContractError("wss_stop_reason_invalid")
        if self.acknowledgement:
            if self.acknowledgement_observed_at is None:
                raise ProbeTransportContractError(
                    "wss_ack_observed_at_missing"
                )
        elif self.acknowledgement_observed_at is not None:
            raise ProbeTransportContractError(
                "wss_ack_observed_at_without_frame"
            )
        if (
            not isinstance(self.notification_observed_at, tuple)
            or len(self.notification_observed_at) != len(self.notifications)
        ):
            raise ProbeTransportContractError(
                "wss_notification_observed_at_count_mismatch"
            )
        ordered_timestamps = (
            (
                ()
                if self.acknowledgement_observed_at is None
                else (self.acknowledgement_observed_at,)
            )
            + self.notification_observed_at
        )
        previous: datetime | None = None
        for observed_at in ordered_timestamps:
            if (
                not isinstance(observed_at, datetime)
                or observed_at.tzinfo is None
                or observed_at.utcoffset() is None
                or observed_at.utcoffset().total_seconds() != 0
            ):
                raise ProbeTransportContractError(
                    "wss_frame_observed_at_not_utc_aware"
                )
            if previous is not None and observed_at < previous:
                raise ProbeTransportContractError(
                    "wss_frame_observed_at_order_invalid"
                )
            previous = observed_at

    def __repr__(self) -> str:
        return (
            "WssCapture("
            f"acknowledgement_bytes={len(self.acknowledgement)}, "
            f"notifications={len(self.notifications)}, "
            f"terminal_class={self.terminal_class!r}, "
            f"error_class={self.error_class!r}, bodies=<redacted>)"
        )


@dataclass(frozen=True, slots=True, repr=False)
class HttpCapture:
    """One no-redirect HTTP response returned by an adapter."""

    status_code: int | None
    body: bytes = field(repr=False)
    response_url: str = field(repr=False)
    terminal_class: str = "SUCCESS"
    error_class: str | None = None
    received_bytes: int | None = None

    def __post_init__(self) -> None:
        allowed = {
            "SUCCESS",
            "DNS_OR_TLS",
            "REDIRECT",
            "RESPONSE_TOO_LARGE",
            "TIMEOUT",
            "TRANSPORT_FAILURE",
        }
        if self.terminal_class not in allowed:
            raise ProbeTransportContractError("http_terminal_class_invalid")
        if self.terminal_class == "SUCCESS":
            if (
                isinstance(self.status_code, bool)
                or not isinstance(self.status_code, int)
                or not 100 <= self.status_code <= 599
                or self.error_class is not None
            ):
                raise ProbeTransportContractError(
                    "successful_http_capture_invalid"
                )
        elif not self.error_class:
            raise ProbeTransportContractError(
                "failed_http_capture_requires_error"
            )
        received = (
            len(self.body)
            if self.received_bytes is None
            else self.received_bytes
        )
        if (
            isinstance(received, bool)
            or not isinstance(received, int)
            or received < len(self.body)
            or received < 0
        ):
            raise ProbeTransportContractError(
                "http_received_byte_count_invalid"
            )
        object.__setattr__(self, "received_bytes", received)

    def __repr__(self) -> str:
        return (
            "HttpCapture("
            f"status_code={self.status_code}, "
            f"body_bytes={len(self.body)}, "
            f"received_bytes={self.received_bytes}, "
            f"terminal_class={self.terminal_class!r}, "
            f"error_class={self.error_class!r}, response_url=<redacted>)"
        )


class WssExchange(Protocol):
    def __call__(
        self,
        request: BoundProbeRequest,
        *,
        max_open_seconds: int,
        max_stream_bytes: int,
        max_notifications: int,
    ) -> WssCapture: ...


class HttpExchange(Protocol):
    def __call__(
        self,
        request: BoundProbeRequest,
        *,
        max_response_bytes: int,
    ) -> HttpCapture: ...


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
        raise TransportExecutionError("http_redirect_forbidden")


def _read_bounded_http_body(stream: Any, maximum: int) -> bytes:
    body = stream.read(maximum + 1)
    if len(body) > maximum:
        raise TransportExecutionError("http_response_too_large")
    return body


def stdlib_http_exchange(
    request: BoundProbeRequest,
    *,
    max_response_bytes: int,
) -> HttpCapture:
    """Execute one no-redirect HTTP request without retry."""

    if request.transport != "HTTP":
        raise ProbeTransportContractError("http_request_expected")
    outgoing = urllib.request.Request(
        request.url,
        data=request.body if request.method == "POST" else None,
        headers=dict(request.headers),
        method=request.method,
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(
            outgoing,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        ) as response:
            body = _read_bounded_http_body(response, max_response_bytes)
            return HttpCapture(
                status_code=int(response.status),
                body=body,
                response_url=str(response.geturl()),
            )
    except urllib.error.HTTPError as exc:
        try:
            body = _read_bounded_http_body(exc, max_response_bytes)
        except TransportExecutionError:
            return HttpCapture(
                status_code=exc.code,
                body=b"",
                response_url=request.url,
                terminal_class="RESPONSE_TOO_LARGE",
                error_class="http_error_body_too_large",
                received_bytes=max_response_bytes + 1,
            )
        return HttpCapture(
            status_code=exc.code,
            body=body,
            response_url=str(exc.geturl()),
        )
    except TransportExecutionError as exc:
        terminal = (
            "REDIRECT"
            if str(exc) == "http_redirect_forbidden"
            else "RESPONSE_TOO_LARGE"
        )
        return HttpCapture(
            status_code=None,
            body=b"",
            response_url=request.url,
            terminal_class=terminal,
            error_class=str(exc),
            received_bytes=(
                max_response_bytes + 1
                if terminal == "RESPONSE_TOO_LARGE"
                else 0
            ),
        )
    except (TimeoutError, socket.timeout):
        return HttpCapture(
            status_code=None,
            body=b"",
            response_url=request.url,
            terminal_class="TIMEOUT",
            error_class="http_timeout",
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
            response_url=request.url,
            terminal_class="DNS_OR_TLS",
            error_class="http_connection_failed",
        )
    except OSError:
        return HttpCapture(
            status_code=None,
            body=b"",
            response_url=request.url,
            terminal_class="TRANSPORT_FAILURE",
            error_class="http_os_error",
        )


def _bounded_wss_frame(value: object) -> bytes:
    if isinstance(value, str):
        body = value.encode("utf-8")
    elif isinstance(value, bytes):
        body = value
    else:
        raise TransportExecutionError("websocket_message_type_invalid")
    if len(body) > MAX_WSS_FRAME_BYTES:
        raise TransportExecutionError("wss_frame_too_large")
    return body


def websockets_wss_exchange(
    request: BoundProbeRequest,
    *,
    max_open_seconds: int,
    max_stream_bytes: int,
    max_notifications: int,
) -> WssCapture:
    """Capture one bounded Helius session with pings and no reconnect."""

    if request.transport != "WSS":
        raise ProbeTransportContractError("wss_request_expected")
    if max_open_seconds != WSS_CAPTURE_SECONDS:
        raise ProbeTransportContractError("wss_open_limit_drift")
    if (
        isinstance(max_stream_bytes, bool)
        or not isinstance(max_stream_bytes, int)
        or not 1 <= max_stream_bytes <= 1_000_000
    ):
        raise ProbeTransportContractError("wss_stream_limit_drift")
    if max_notifications != 500:
        raise ProbeTransportContractError("wss_notification_limit_drift")

    from websockets.exceptions import ConnectionClosed, PayloadTooBig
    from websockets.sync.client import connect

    acknowledgement = b""
    acknowledgement_observed_at: datetime | None = None
    notifications: list[bytes] = []
    notification_observed_at: list[datetime] = []
    started = time.monotonic()
    websocket: Any | None = None

    def capture(
        terminal_class: str,
        *,
        error_class: str | None,
        stop_reason: str,
    ) -> WssCapture:
        return WssCapture(
            acknowledgement=acknowledgement,
            notifications=tuple(notifications),
            acknowledgement_observed_at=acknowledgement_observed_at,
            notification_observed_at=tuple(notification_observed_at),
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
            ping_interval=60.0,
            ping_timeout=20.0,
            proxy=None,
        )
        websocket.send(request.body.decode("utf-8"))
        acknowledgement_frame = websocket.recv(
            timeout=min(10.0, max_open_seconds)
        )
        acknowledgement_received_at = datetime.now(UTC)
        acknowledgement = _bounded_wss_frame(acknowledgement_frame)
        acknowledgement_observed_at = acknowledgement_received_at
        while True:
            elapsed = time.monotonic() - started
            remaining_seconds = max_open_seconds - elapsed
            if remaining_seconds <= 0:
                return capture(
                    "BOUND_REACHED",
                    error_class=None,
                    stop_reason="ELAPSED_CAP",
                )
            if len(notifications) >= max_notifications:
                return capture(
                    "BOUND_REACHED",
                    error_class=None,
                    stop_reason="NOTIFICATION_CAP",
                )
            stream_bytes = len(acknowledgement) + sum(
                len(item) for item in notifications
            )
            if max_stream_bytes - stream_bytes < MAX_WSS_FRAME_BYTES:
                return capture(
                    "BOUND_REACHED",
                    error_class=None,
                    stop_reason="STREAM_GUARD",
                )
            try:
                frame = websocket.recv(timeout=remaining_seconds)
            except TimeoutError:
                return capture(
                    "BOUND_REACHED",
                    error_class=None,
                    stop_reason="ELAPSED_CAP",
                )
            frame_observed_at = datetime.now(UTC)
            notifications.append(_bounded_wss_frame(frame))
            notification_observed_at.append(frame_observed_at)
    except PayloadTooBig:
        return capture(
            "RESPONSE_TOO_LARGE",
            error_class="wss_frame_too_large",
            stop_reason="FRAME_LIMIT",
        )
    except ConnectionClosed:
        return capture(
            "REMOTE_CLOSED",
            error_class="wss_remote_closed",
            stop_reason="REMOTE_CLOSED",
        )
    except (TimeoutError, socket.timeout):
        return capture(
            "TIMEOUT",
            error_class="wss_open_or_ack_timeout",
            stop_reason="OPEN_OR_ACK_TIMEOUT",
        )
    except (OSError, ssl.SSLError, ConnectionError):
        return capture(
            "DNS_OR_TLS",
            error_class="wss_connection_failed",
            stop_reason="CONNECTION_FAILURE",
        )
    except TransportExecutionError as exc:
        return capture(
            "RESPONSE_TOO_LARGE",
            error_class=str(exc),
            stop_reason="FRAME_LIMIT",
        )
    except Exception:
        return capture(
            "TRANSPORT_FAILURE",
            error_class="wss_unclassified_transport_failure",
            stop_reason="TRANSPORT_FAILURE",
        )
    finally:
        if websocket is not None:
            try:
                websocket.close()
            except Exception:
                pass


@dataclass(frozen=True, slots=True, repr=False)
class ProbeEvidence:
    """Raw response bytes plus only sanitized classification metadata."""

    provider: str
    kind: str
    body: bytes = field(repr=False)
    observed_at: datetime
    metadata: Mapping[str, JsonValue]
    response_status: RawResponseStatus = RawResponseStatus.SUCCESS
    error_class: str | None = None

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ProbeTransportContractError("evidence_timestamp_not_aware")
        try:
            status = RawResponseStatus(self.response_status)
        except ValueError as exc:
            raise ProbeTransportContractError(
                "evidence_response_status_invalid"
            ) from exc
        object.__setattr__(self, "response_status", status)
        if status == RawResponseStatus.SUCCESS:
            if self.error_class is not None:
                raise ProbeTransportContractError(
                    "successful_evidence_cannot_have_error"
                )
        elif not self.error_class:
            raise ProbeTransportContractError(
                "failed_evidence_requires_error"
            )
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(_safe_metadata(self.metadata)),
        )

    def __repr__(self) -> str:
        return (
            "ProbeEvidence("
            f"provider={self.provider!r}, kind={self.kind!r}, "
            f"body_bytes={len(self.body)}, body=<redacted>)"
        )

    def safe_receipt(self) -> dict[str, JsonValue]:
        return {
            "body_bytes": len(self.body),
            "body_sha256": hashlib.sha256(self.body).hexdigest(),
            "error_class": self.error_class,
            "kind": self.kind,
            "metadata": dict(self.metadata),
            "observed_at": self.observed_at.isoformat(),
            "provider": self.provider,
            "response_status": str(self.response_status),
        }


class EvidenceSink(Protocol):
    def __call__(self, evidence: ProbeEvidence) -> int: ...

    def finalize(self, *, max_stored_bytes: int) -> int: ...

    @property
    def complete(self) -> bool: ...


class InMemoryEvidenceSink:
    """Test-only sink; Atom 4 intentionally has no durable sink."""

    def __init__(self) -> None:
        self.records: list[ProbeEvidence] = []

    def __call__(self, evidence: ProbeEvidence) -> int:
        self.records.append(evidence)
        return len(evidence.body) + len(
            _canonical_json_bytes(evidence.safe_receipt())
        )

    def finalize(self, *, max_stored_bytes: int) -> int:
        if isinstance(max_stored_bytes, bool) or max_stored_bytes < 0:
            raise ProbeStopError("stored_byte_allowance_invalid")
        return 0

    @property
    def complete(self) -> bool:
        return True


def _safe_run_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"t08a5-[0-9]{8}T[0-9]{6}Z", value) is None
    ):
        raise ProbeTransportContractError("run_id_invalid")
    return value


def default_probe_run_id(now: datetime | None = None) -> str:
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ProbeTransportContractError("run_time_not_aware")
    return instant.astimezone(UTC).strftime("t08a5-%Y%m%dT%H%M%SZ")


class DurableProbeSink:
    """Buffer redacted TASK-06 events and atomically publish one partition."""

    def __init__(
        self,
        *,
        raw_root: Path,
        run_id: str,
        credentials: ProbeCredentials,
    ) -> None:
        if not isinstance(raw_root, Path) or not raw_root.is_absolute():
            raise ProbeTransportContractError("raw_root_must_be_absolute")
        self.raw_root = raw_root
        self.run_id = _safe_run_id(run_id)
        self.credentials = credentials
        self.run_directory = (
            raw_root / RAW_LOGICAL_ROOT / f"run={self.run_id}"
        )
        if self.run_directory.exists():
            raise ProbeTransportContractError("run_output_already_exists")
        self.run_directory.mkdir(parents=True, exist_ok=False)
        self.receipt_directory = self.run_directory / "receipts"
        self.receipt_directory.mkdir()
        self._events: list[Any] = []
        self._finalized = False
        self._complete = False
        self._finalize_error_class: str | None = None
        self._stored_event_count = 0
        self._stored_bytes = 0

    @property
    def logical_root(self) -> str:
        return f"{RAW_LOGICAL_ROOT}/run={self.run_id}"

    def __call__(self, evidence: ProbeEvidence) -> int:
        if self._finalized:
            raise ProbeStopError("durable_sink_already_finalized")
        request = evidence.metadata.get("request")
        if isinstance(request, Mapping):
            method = request.get("method")
            path = request.get("path")
        else:
            method = "WSS"
            path = "/"
        if not isinstance(method, str) or not isinstance(path, str):
            raise ProbeTransportContractError(
                "evidence_request_identity_missing"
            )
        ingested_at = max(datetime.now(UTC), evidence.observed_at)
        event = build_raw_api_event(
            source=evidence.provider,
            source_version=f"task08-probe-runtime-{TRANSPORT_CONTRACT_VERSION}",
            endpoint_or_method=f"{method} {path}",
            request_identity={
                "evidence_kind": evidence.kind,
                "metadata": dict(evidence.metadata),
                "run_id": self.run_id,
            },
            response_body=evidence.body,
            response_status=evidence.response_status,
            error_class=evidence.error_class,
            observed_at=evidence.observed_at,
            available_to_strategy_at=evidence.observed_at,
            ingested_at=ingested_at,
            first_reliable_available_at=evidence.observed_at,
            provider_version=f"evidence-as-of-{TRANSPORT_AS_OF}",
            schema_version="1.0",
            protocol_version=f"task08-probe-transport-{TRANSPORT_CONTRACT_VERSION}",
            quality_flags="task08_bounded_discovery_probe",
            explicit_secret_values=self.credentials.explicit_secret_values,
        )
        self._events.append(event)
        return 0

    def finalize(self, *, max_stored_bytes: int) -> int:
        if self._finalized:
            return 0
        if (
            isinstance(max_stored_bytes, bool)
            or not isinstance(max_stored_bytes, int)
            or max_stored_bytes <= STORAGE_METADATA_RESERVE_BYTES
        ):
            raise ProbeStopError("stored_byte_allowance_insufficient")
        if not self._events:
            raise ProbeStopError("durable_sink_has_no_evidence")

        parquet_budget = max_stored_bytes - STORAGE_METADATA_RESERVE_BYTES
        created_at = max(event.ingested_at for event in self._events)
        reliable_at = max(
            created_at,
            *(event.first_reliable_available_at for event in self._events),
        )
        policy = StorageBudgetPolicy(
            max_partition_bytes=parquet_budget,
            max_dataset_bytes=parquet_budget,
            min_free_bytes=1_073_741_824,
            warning_threshold_bps=9000,
            forecast_partition_count=1,
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
                if candidate_count == 1:
                    candidate_count = 0
                else:
                    candidate_count = max(1, candidate_count // 2)
                continue
            break

        if result is not None:
            observed = verify_raw_event_partition(
                root=self.run_directory,
                manifest=result.manifest,
            )
            if len(observed) != candidate_count:
                raise ProbeStopError(
                    "durable_partition_row_count_mismatch"
                )
            manifest_bytes = (
                canonical_manifest_bytes(result.manifest) + b"\n"
            )
            partition_bytes = result.file_size_bytes
        else:
            observed = ()
            manifest_bytes = b""
            partition_bytes = 0

        self._stored_event_count = len(observed)
        self._complete = self._stored_event_count == len(self._events)
        if not self._complete and self._finalize_error_class is None:
            self._finalize_error_class = (
                "durable_partition_incomplete_unclassified"
            )

        received_source_counts: dict[str, int] = {}
        stored_source_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        received_raw_body_bytes = 0
        for event in self._events:
            received_source_counts[event.source] = (
                received_source_counts.get(event.source, 0) + 1
            )
            status = str(event.response_status)
            status_counts[status] = status_counts.get(status, 0) + 1
            received_raw_body_bytes += len(event.redacted_body)
        stored_raw_body_bytes = 0
        for event in observed:
            stored_source_counts[event.source] = (
                stored_source_counts.get(event.source, 0) + 1
            )
            stored_raw_body_bytes += len(event.redacted_body)
        receipt_bytes = _canonical_json_bytes(
            {
                "cash_spend_usd_cents": 0,
                "complete": self._complete,
                "content_sha256": (
                    result.manifest.content_sha256
                    if result is not None
                    else None
                ),
                "dataset_id": DATASET_ID,
                "dataset_version": DATASET_VERSION,
                "event_count_received": len(self._events),
                "event_count_stored": self._stored_event_count,
                "file_sha256": (
                    result.manifest.file_sha256
                    if result is not None
                    else None
                ),
                "finalize_error_class": self._finalize_error_class,
                "first_reliable_available_at": reliable_at.isoformat(),
                "omitted_event_count": (
                    len(self._events) - self._stored_event_count
                ),
                "partition_id": (
                    result.manifest.partition_id
                    if result is not None
                    else None
                ),
                "provider_events_received": received_source_counts,
                "provider_events_stored": stored_source_counts,
                "raw_body_bytes_received": received_raw_body_bytes,
                "raw_body_bytes_stored": stored_raw_body_bytes,
                "retries": 0,
                "run_id": self.run_id,
                "status_counts": status_counts,
                "transport_contract_version": TRANSPORT_CONTRACT_VERSION,
            }
        ) + b"\n"
        metadata_bytes = len(manifest_bytes) + len(receipt_bytes)
        if metadata_bytes > STORAGE_METADATA_RESERVE_BYTES:
            raise ProbeStopError("storage_metadata_reserve_exceeded")
        total_bytes = partition_bytes + metadata_bytes
        if total_bytes > max_stored_bytes:
            raise ProbeStopError("stored_byte_allowance_exceeded")

        manifest_path = self.receipt_directory / "probe.manifest.json"
        receipt_path = self.receipt_directory / "probe.receipt.json"
        if manifest_bytes:
            with manifest_path.open("xb") as handle:
                handle.write(manifest_bytes)
        with receipt_path.open("xb") as handle:
            handle.write(receipt_bytes)
        self._stored_bytes = total_bytes
        self._finalized = True
        return total_bytes

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

    @property
    def complete(self) -> bool:
        return self._complete


@dataclass(frozen=True, slots=True)
class ParsedLogsNotification:
    subscription_id: int
    slot: int
    signature: str
    transaction_succeeded: bool
    logs_truncated: bool
    decoded_events: tuple[DecodedPumpEvent, ...]
    unsupported_pump_program_data: int

    @property
    def is_followup_candidate(self) -> bool:
        return self.transaction_succeeded and any(
            event.event_name == "CreateEvent"
            for event in self.decoded_events
        )


def _validate_signature(value: object) -> str:
    if (
        not isinstance(value, str)
        or not 64 <= len(value) <= 88
        or _BASE58_RE.fullmatch(value) is None
    ):
        raise NotificationSchemaError("transaction_signature_invalid")
    return value


def parse_subscription_ack(body: bytes) -> int:
    """Validate the exact JSON-RPC acknowledgement and return its id."""

    document = _mapping("wss_ack", _parse_json_bytes("wss_ack", body))
    _exact_keys("wss_ack", document, {"id", "jsonrpc", "result"})
    if document["jsonrpc"] != "2.0" or document["id"] != LOGS_SUBSCRIBE_REQUEST_ID:
        raise NotificationSchemaError("wss_ack_identity_drift")
    subscription_id = document["result"]
    if (
        isinstance(subscription_id, bool)
        or not isinstance(subscription_id, int)
        or subscription_id < 0
    ):
        raise NotificationSchemaError("wss_subscription_id_invalid")
    return subscription_id


def _event_discriminator(
    log_line: str,
) -> bytes | None:
    if not log_line.startswith(PROGRAM_DATA_PREFIX):
        return None
    encoded = log_line[len(PROGRAM_DATA_PREFIX) :]
    if not encoded or encoded.strip() != encoded:
        raise ProgramLogAttributionError("program_data_base64_not_canonical")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProgramLogAttributionError("program_data_base64_invalid") from exc
    if len(payload) < 8:
        raise ProgramLogAttributionError("program_data_discriminator_missing")
    if len(payload) > MAX_EVENT_PAYLOAD_BYTES:
        raise ProgramLogAttributionError("program_data_payload_too_large")
    return payload[:8]


def _decode_attributed_events(
    plan: PumpEventPlan,
    *,
    logs: Sequence[str],
    transaction_succeeded: bool,
    allow_unclosed_stack: bool = False,
) -> tuple[tuple[DecodedPumpEvent, ...], int]:
    stack: list[str] = []
    decoded: list[DecodedPumpEvent] = []
    unsupported = 0
    known_discriminators = plan.event_by_discriminator
    for line in logs:
        invoke = _INVOKE_RE.fullmatch(line)
        if invoke:
            program_id = invoke.group(1)
            depth = int(invoke.group(2))
            if depth != len(stack) + 1:
                raise ProgramLogAttributionError("program_invoke_depth_invalid")
            stack.append(program_id)
            continue
        complete = _COMPLETE_RE.fullmatch(line)
        if complete:
            program_id = complete.group(1)
            if not stack or stack[-1] != program_id:
                raise ProgramLogAttributionError(
                    "program_completion_stack_mismatch"
                )
            stack.pop()
            continue
        discriminator = _event_discriminator(line)
        if discriminator is None:
            continue
        if not stack:
            raise ProgramLogAttributionError(
                "program_data_without_invocation"
            )
        if stack[-1] != plan.program_id:
            continue
        if not transaction_succeeded:
            continue
        if discriminator not in known_discriminators:
            unsupported += 1
            continue
        try:
            event = decode_pump_program_data(
                plan,
                log_line=line,
                emitting_program_id=stack[-1],
                transaction_succeeded=True,
            )
        except PumpEventDecodeError as exc:
            raise ProgramLogAttributionError(
                f"pinned_event_decode_failed:{exc}"
            ) from exc
        if event is None:
            raise ProgramLogAttributionError("successful_event_not_decoded")
        decoded.append(event)
    if stack and not allow_unclosed_stack:
        raise ProgramLogAttributionError("program_invocation_unclosed")
    return tuple(decoded), unsupported


def parse_logs_notification(
    body: bytes,
    *,
    expected_subscription_id: int,
    event_plan: PumpEventPlan,
) -> ParsedLogsNotification:
    """Validate one logsNotification and decode only attributed pinned events."""

    document = _mapping(
        "logs_notification",
        _parse_json_bytes("logs_notification", body),
    )
    _exact_keys(
        "logs_notification",
        document,
        {"jsonrpc", "method", "params"},
    )
    if (
        document["jsonrpc"] != "2.0"
        or document["method"] != "logsNotification"
    ):
        raise NotificationSchemaError("logs_notification_identity_drift")
    params = _mapping("logs_notification_params", document["params"])
    _exact_keys(
        "logs_notification_params",
        params,
        {"result", "subscription"},
    )
    if params["subscription"] != expected_subscription_id:
        raise NotificationSchemaError("logs_subscription_id_mismatch")
    result = _mapping("logs_notification_result", params["result"])
    _exact_keys(
        "logs_notification_result",
        result,
        {"context", "value"},
    )
    context = _mapping("logs_notification_context", result["context"])
    if not {"slot"} <= set(context) <= {"slot", "apiVersion"}:
        raise NotificationSchemaError("logs_context_keys_drift")
    slot = context["slot"]
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise NotificationSchemaError("logs_context_slot_invalid")
    value = _mapping("logs_notification_value", result["value"])
    _exact_keys(
        "logs_notification_value",
        value,
        {"err", "logs", "signature"},
    )
    signature = _validate_signature(value["signature"])
    log_value = value["logs"]
    if (
        isinstance(log_value, (str, bytes))
        or not isinstance(log_value, Sequence)
        or not all(isinstance(line, str) for line in log_value)
    ):
        raise NotificationSchemaError("logs_value_invalid")
    truncation_indexes = [
        index
        for index, line in enumerate(log_value)
        if line == _LOG_TRUNCATED_MARKER
    ]
    logs_truncated = bool(truncation_indexes)
    if logs_truncated and truncation_indexes != [len(log_value) - 1]:
        raise ProgramLogAttributionError(
            "program_log_truncation_marker_invalid"
        )
    transaction_succeeded = value["err"] is None
    decoded, unsupported = _decode_attributed_events(
        event_plan,
        logs=log_value,
        transaction_succeeded=transaction_succeeded,
        allow_unclosed_stack=logs_truncated,
    )
    if logs_truncated:
        decoded = ()
        unsupported = 0
    return ParsedLogsNotification(
        subscription_id=expected_subscription_id,
        slot=slot,
        signature=signature,
        transaction_succeeded=transaction_succeeded,
        logs_truncated=logs_truncated,
        decoded_events=decoded,
        unsupported_pump_program_data=unsupported,
    )


@dataclass(frozen=True, slots=True)
class ProbeSummary:
    """Sanitized bounded-run receipt; it contains no bodies or endpoints."""

    status: str
    elapsed_seconds: int
    notifications: int
    successful_notifications: int
    failed_notifications: int
    truncated_notifications: int
    decoded_events: int
    create_events: int
    unsupported_pump_program_data: int
    unique_followup_candidates: int
    rpc_followups: int
    solana_tracker_requests: int
    solana_tracker_failures: int
    stream_bytes: int
    received_bytes: int
    stored_bytes: int
    received_and_stored_bytes: int
    helius_credits: int
    evidence_records: int
    wss_stop_reason: str
    retries: int
    concurrency: int
    cash_spend_usd_cents: int

    def safe_receipt(self) -> dict[str, JsonValue]:
        return {
            "cash_spend_usd_cents": self.cash_spend_usd_cents,
            "concurrency": self.concurrency,
            "create_events": self.create_events,
            "decoded_events": self.decoded_events,
            "elapsed_seconds": self.elapsed_seconds,
            "evidence_records": self.evidence_records,
            "failed_notifications": self.failed_notifications,
            "helius_credits": self.helius_credits,
            "notifications": self.notifications,
            "received_and_stored_bytes": self.received_and_stored_bytes,
            "received_bytes": self.received_bytes,
            "retries": self.retries,
            "rpc_followups": self.rpc_followups,
            "solana_tracker_failures": self.solana_tracker_failures,
            "solana_tracker_requests": self.solana_tracker_requests,
            "status": self.status,
            "stored_bytes": self.stored_bytes,
            "stream_bytes": self.stream_bytes,
            "successful_notifications": self.successful_notifications,
            "truncated_notifications": self.truncated_notifications,
            "unique_followup_candidates": self.unique_followup_candidates,
            "unsupported_pump_program_data": (
                self.unsupported_pump_program_data
            ),
            "wss_stop_reason": self.wss_stop_reason,
        }


class _UsageGuard:
    def __init__(
        self,
        *,
        plan: DiscoveryPlan,
        clock: Callable[[], float],
        sink: EvidenceSink,
    ) -> None:
        self.plan = plan
        self.clock = clock
        self.sink = sink
        self.started = clock()
        self.wss_connections = 0
        self.wss_subscriptions = 0
        self.notifications = 0
        self.truncated_notifications = 0
        self.stream_bytes = 0
        self.wss_captured_bytes = 0
        self.wss_captured_notifications = 0
        self.rpc_followups = 0
        self.solana_tracker_requests = 0
        self.http_received_bytes = 0
        self.received_bytes = 0
        self.stored_bytes = 0
        self.evidence_records = 0
        self._finalized = False

    @property
    def elapsed_seconds(self) -> int:
        elapsed = self.clock() - self.started
        if elapsed < 0:
            raise ProbeStopError("monotonic_clock_moved_backwards")
        return math.ceil(elapsed)

    def validate(self) -> dict[str, int]:
        if self.received_bytes > MAX_ADMITTED_RECEIVED_BYTES:
            raise ProbeStopError(
                "probe_admitted_received_bytes_exceeded"
            )
        if self.evidence_records > MAX_EVIDENCE_RECORDS:
            raise ProbeStopError("probe_evidence_record_cap_exceeded")
        try:
            return validate_probe_usage(
                self.plan,
                elapsed_seconds=self.elapsed_seconds,
                wss_connections=self.wss_connections,
                wss_subscriptions=self.wss_subscriptions,
                notifications=self.notifications,
                stream_bytes=self.stream_bytes,
                rpc_followups=self.rpc_followups,
                solana_tracker_requests=self.solana_tracker_requests,
                received_and_stored_bytes=(
                    self.received_bytes + self.stored_bytes
                ),
                concurrency=1,
                retries=0,
                cash_spend_usd_cents=0,
            )
        except ValueError as exc:
            raise ProbeStopError(str(exc)) from exc

    def safe_usage_receipt(
        self,
        *,
        tracker_failures: int,
        stop_error_class: str,
        finalize_error_class: str | None,
    ) -> dict[str, JsonValue]:
        elapsed = self.clock() - self.started
        clock_valid = elapsed >= 0
        elapsed_seconds = max(0, math.ceil(elapsed))
        helius_credits = (
            math.ceil(self.wss_captured_bytes / 100_000) * 2
            + self.rpc_followups
            + self.wss_connections
        )
        return {
            "cash_spend_usd_cents": 0,
            "concurrency": 1,
            "elapsed_clock_valid": clock_valid,
            "elapsed_seconds": elapsed_seconds,
            "evidence_admitted_bytes": self.received_bytes,
            "evidence_records": self.evidence_records,
            "finalize_error_class": finalize_error_class,
            "helius_credits": helius_credits,
            "http_received_bytes": self.http_received_bytes,
            "network_received_bytes": (
                self.http_received_bytes + self.wss_captured_bytes
            ),
            "notifications_processed": self.notifications,
            "receipt_type": "CONTROLLED_STOP_USAGE",
            "received_and_stored_bytes": (
                self.received_bytes + self.stored_bytes
            ),
            "retries": 0,
            "rpc_followups": self.rpc_followups,
            "solana_tracker_failures": tracker_failures,
            "solana_tracker_requests": self.solana_tracker_requests,
            "stop_error_class": stop_error_class,
            "stored_bytes": self.stored_bytes,
            "stream_admitted_bytes": self.stream_bytes,
            "truncated_notifications": self.truncated_notifications,
            "wss_captured_bytes": self.wss_captured_bytes,
            "wss_captured_notifications": (
                self.wss_captured_notifications
            ),
            "wss_connections": self.wss_connections,
            "wss_subscriptions": self.wss_subscriptions,
        }

    @property
    def remaining_admission_bytes(self) -> int:
        return max(0, MAX_ADMITTED_RECEIVED_BYTES - self.received_bytes)

    def persist(
        self,
        evidence: ProbeEvidence,
        *,
        stream: bool,
        received_bytes: int | None = None,
    ) -> None:
        body_bytes = len(evidence.body)
        observed_bytes = (
            body_bytes if received_bytes is None else received_bytes
        )
        if (
            isinstance(observed_bytes, bool)
            or not isinstance(observed_bytes, int)
            or observed_bytes < body_bytes
            or observed_bytes < 0
        ):
            raise ProbeStopError("received_byte_count_invalid")
        if self.evidence_records >= MAX_EVIDENCE_RECORDS:
            raise ProbeStopError("probe_evidence_record_cap_exceeded")
        if stream:
            self.stream_bytes += body_bytes
        self.received_bytes += observed_bytes
        self.validate()
        stored = self.sink(evidence)
        if isinstance(stored, bool) or not isinstance(stored, int) or stored < 0:
            raise ProbeStopError("evidence_sink_byte_count_invalid")
        self.stored_bytes += stored
        self.evidence_records += 1
        self.validate()

    def finalize(self) -> None:
        if self._finalized:
            return
        if self.evidence_records == 0:
            self._finalized = True
            return
        remaining = self.plan.probe_budget["received_and_stored_bytes"] - (
            self.received_bytes + self.stored_bytes
        )
        if remaining <= 0:
            raise ProbeStopError("durable_storage_allowance_exhausted")
        stored = self.sink.finalize(max_stored_bytes=remaining)
        if isinstance(stored, bool) or not isinstance(stored, int) or stored < 0:
            raise ProbeStopError("evidence_sink_final_byte_count_invalid")
        self.stored_bytes += stored
        self._finalized = True
        if not self.sink.complete:
            raise ProbeStopError(
                "durable_evidence_partial_due_storage_budget"
            )


class ProbeTransportRunner:
    """Sequential orchestration over injected exchanges; Atom 4 uses mocks."""

    def __init__(
        self,
        *,
        plan: DiscoveryPlan,
        event_plan: PumpEventPlan,
        credentials: ProbeCredentials,
        access: ProbeAccessAttestation,
        gate: ExternalExecutionGate,
        wss_exchange: WssExchange,
        http_exchange: HttpExchange,
        evidence_sink: EvidenceSink,
        clock: Callable[[], float],
        pace: Callable[[float], None],
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.plan = plan
        self.event_plan = event_plan
        self.credentials = credentials
        self.access = access
        self.gate = gate
        self.wss_exchange = wss_exchange
        self.http_exchange = http_exchange
        self.evidence_sink = evidence_sink
        self.clock = clock
        self.pace = pace
        self.now = now or (lambda: datetime.now(UTC))
        self._last_safe_failure_receipt: dict[str, JsonValue] | None = None

    def safe_failure_receipt(self) -> dict[str, JsonValue] | None:
        if self._last_safe_failure_receipt is None:
            return None
        return dict(self._last_safe_failure_receipt)

    def _evidence(
        self,
        *,
        provider: str,
        kind: str,
        body: bytes,
        metadata: Mapping[str, JsonValue],
        observed_at: datetime | None = None,
        response_status: RawResponseStatus = RawResponseStatus.SUCCESS,
        error_class: str | None = None,
    ) -> ProbeEvidence:
        return ProbeEvidence(
            provider=provider,
            kind=kind,
            body=body,
            observed_at=self.now() if observed_at is None else observed_at,
            metadata=_safe_metadata(metadata),
            response_status=response_status,
            error_class=error_class,
        )

    @staticmethod
    def _safe_error_class(error: BaseException) -> str:
        value = str(error)
        if re.fullmatch(r"[a-z0-9_.:-]{1,120}", value):
            return value
        return type(error).__name__.casefold()

    @staticmethod
    def _terminal_status(terminal_class: str) -> RawResponseStatus:
        if terminal_class == "TIMEOUT":
            return RawResponseStatus.TIMEOUT
        if terminal_class in {"REDIRECT", "RESPONSE_TOO_LARGE"}:
            return RawResponseStatus.INVALID_RESPONSE
        return RawResponseStatus.PROVIDER_ERROR

    def _http(
        self,
        guard: _UsageGuard,
        request: BoundProbeRequest,
        *,
        kind: str,
        metadata: Mapping[str, JsonValue],
        validate_body: Callable[[bytes], None],
        response_byte_cap: int = MAX_HTTP_RESPONSE_BYTES,
        failure_type: type[ProbeStopError] = ProbeStopError,
    ) -> bytes:
        guard.validate()
        if (
            isinstance(response_byte_cap, bool)
            or not isinstance(response_byte_cap, int)
            or not 1 <= response_byte_cap <= MAX_HTTP_RESPONSE_BYTES
        ):
            raise ProbeTransportContractError(
                "http_response_byte_cap_invalid"
            )
        if (
            not isinstance(failure_type, type)
            or not issubclass(failure_type, ProbeStopError)
        ):
            raise ProbeTransportContractError(
                "http_failure_type_invalid"
            )
        remaining = self.plan.probe_budget["received_and_stored_bytes"] - (
            guard.received_bytes + guard.stored_bytes
        )
        admission_remaining = guard.remaining_admission_bytes
        if remaining <= 0:
            raise ProbeStopError("probe_received_and_stored_bytes_exceeded")
        if admission_remaining <= 1:
            raise ProbeStopError(
                "probe_admission_allowance_exhausted"
            )
        maximum = min(
            response_byte_cap,
            remaining,
            admission_remaining - 1,
        )
        capture = self.http_exchange(
            request,
            max_response_bytes=maximum,
        )
        if len(capture.body) > maximum:
            raise ProbeStopError("http_response_too_large")
        assert capture.received_bytes is not None
        guard.http_received_bytes += capture.received_bytes
        if capture.received_bytes > admission_remaining:
            raise ProbeStopError(
                "http_received_bytes_exceed_admission_allowance"
            )
        evidence_metadata = {
            **metadata,
            "request": request.safe_receipt(),
            "status_code": capture.status_code,
        }
        if capture.response_url != request.url:
            guard.persist(
                self._evidence(
                    provider=request.provider,
                    kind=kind,
                    body=capture.body,
                    metadata=evidence_metadata,
                    response_status=RawResponseStatus.INVALID_RESPONSE,
                    error_class="http_redirect_or_target_drift",
                ),
                stream=False,
                received_bytes=capture.received_bytes,
            )
            raise failure_type("http_redirect_or_target_drift")
        if capture.terminal_class != "SUCCESS":
            error_class = capture.error_class or "http_transport_failure"
            guard.persist(
                self._evidence(
                    provider=request.provider,
                    kind=kind,
                    body=capture.body,
                    metadata=evidence_metadata,
                    response_status=self._terminal_status(
                        capture.terminal_class
                    ),
                    error_class=error_class,
                ),
                stream=False,
                received_bytes=capture.received_bytes,
            )
            raise failure_type(error_class)
        if capture.status_code != 200:
            error_class = f"http_status_not_success:{capture.status_code}"
            guard.persist(
                self._evidence(
                    provider=request.provider,
                    kind=kind,
                    body=capture.body,
                    metadata=evidence_metadata,
                    response_status=RawResponseStatus.HTTP_ERROR,
                    error_class=error_class,
                ),
                stream=False,
                received_bytes=capture.received_bytes,
            )
            raise failure_type(error_class)
        try:
            validate_body(capture.body)
        except (ProbeStopError, ProbeTransportContractError) as exc:
            error_class = self._safe_error_class(exc)
            guard.persist(
                self._evidence(
                    provider=request.provider,
                    kind=kind,
                    body=capture.body,
                    metadata=evidence_metadata,
                    response_status=RawResponseStatus.INVALID_RESPONSE,
                    error_class=error_class,
                ),
                stream=False,
                received_bytes=capture.received_bytes,
            )
            if failure_type is ProbeStopError:
                raise
            raise failure_type(error_class) from exc
        guard.persist(
            self._evidence(
                provider=request.provider,
                kind=kind,
                body=capture.body,
                metadata=evidence_metadata,
            ),
            stream=False,
            received_bytes=capture.received_bytes,
        )
        return capture.body

    def _tracker_phase(
        self,
        guard: _UsageGuard,
        *,
        phase: str,
    ) -> int:
        request = bind_tracker_snapshot(
            self.credentials,
            phase=phase,
        )
        guard.solana_tracker_requests += 1
        try:
            self._http(
                guard,
                request,
                kind="TRACKER_DISCOVERY_SNAPSHOT",
                metadata={
                    "category_limit": TRACKER_OVERVIEW_LIMIT,
                    "phase": phase,
                    "path": TRACKER_PATHS[0],
                },
                validate_body=self._validate_tracker_response,
                response_byte_cap=TRACKER_MAX_RESPONSE_BYTES,
                failure_type=TrackerSnapshotError,
            )
        except TrackerSnapshotError:
            return 1
        return 0

    @staticmethod
    def _validate_tracker_response(body: bytes) -> None:
        payload = _mapping(
            "tracker_response",
            _parse_json_bytes("tracker_response", body),
        )
        _exact_keys(
            "tracker_response",
            payload,
            {"graduated", "graduating", "latest"},
        )
        for category in ("latest", "graduating", "graduated"):
            tokens = payload[category]
            if (
                isinstance(tokens, (str, bytes))
                or not isinstance(tokens, Sequence)
            ):
                raise ProbeStopError(
                    f"tracker_{category}_must_be_sequence"
                )
            if len(tokens) > TRACKER_OVERVIEW_LIMIT:
                raise ProbeStopError(
                    f"tracker_{category}_limit_exceeded"
                )

    def _followup(
        self,
        guard: _UsageGuard,
        *,
        signature: str,
        ordinal: int,
    ) -> None:
        request = bind_get_transaction(
            self.credentials,
            signature=signature,
            ordinal=ordinal,
        )
        guard.rpc_followups += 1
        self._http(
            guard,
            request,
            kind="HELIUS_GET_TRANSACTION",
            metadata={
                "request_id": request.request_id,
                "signature_sha256": hashlib.sha256(
                    signature.encode("ascii")
                ).hexdigest(),
            },
            validate_body=lambda body: self._validate_get_transaction_response(
                body,
                request=request,
            ),
        )

    @staticmethod
    def _validate_get_transaction_response(
        body: bytes,
        *,
        request: BoundProbeRequest,
    ) -> None:
        document = _mapping(
            "get_transaction_response",
            _parse_json_bytes("get_transaction_response", body),
        )
        if set(document) not in (
            {"id", "jsonrpc", "result"},
            {"error", "id", "jsonrpc"},
        ):
            raise ProbeStopError("get_transaction_response_keys_drift")
        if (
            document["id"] != request.request_id
            or document["jsonrpc"] != "2.0"
        ):
            raise ProbeStopError("get_transaction_response_identity_drift")
        if "error" in document:
            raise ProbeStopError("get_transaction_typed_error")
        if document["result"] is not None and not isinstance(
            document["result"],
            Mapping,
        ):
            raise ProbeStopError("get_transaction_result_schema_drift")

    def run(self) -> ProbeSummary:
        """Run two bounded Tracker audits around one primary Helius capture."""

        self.gate.require()
        self.access.require(self.plan)
        if self.event_plan.program_id != PUMP_PROGRAM_ID:
            raise ProbeTransportContractError("pump_program_plan_drift")
        guard = _UsageGuard(
            plan=self.plan,
            clock=self.clock,
            sink=self.evidence_sink,
        )
        tracker_failures = 0
        self._last_safe_failure_receipt = None
        try:
            tracker_failures = self._tracker_phase(guard, phase="OPEN")

            request = bind_logs_subscribe(self.credentials)
            guard.wss_connections = 1
            guard.wss_subscriptions = 1
            guard.validate()
            tracker_close_reserve = TRACKER_MAX_RESPONSE_BYTES + 1
            wss_stream_allowance = min(
                self.plan.probe_budget["stream_bytes"],
                max(
                    0,
                    guard.remaining_admission_bytes
                    - tracker_close_reserve,
                ),
            )
            if wss_stream_allowance < MAX_WSS_FRAME_BYTES:
                raise ProbeStopError(
                    "wss_admission_allowance_insufficient"
                )
            capture = self.wss_exchange(
                request,
                max_open_seconds=WSS_CAPTURE_SECONDS,
                max_stream_bytes=wss_stream_allowance,
                max_notifications=self.plan.probe_budget["notifications"],
            )
            if (
                len(capture.notifications)
                > self.plan.probe_budget["notifications"]
            ):
                raise ProbeStopError("probe_notifications_exceeded")
            stream_total = len(capture.acknowledgement) + sum(
                len(item) for item in capture.notifications
            )
            guard.wss_captured_bytes = stream_total
            guard.wss_captured_notifications = len(capture.notifications)
            if stream_total > wss_stream_allowance:
                raise ProbeStopError("probe_stream_bytes_exceeded")
            if (
                not capture.acknowledgement
                and capture.terminal_class != "BOUND_REACHED"
            ):
                error_class = capture.error_class or "wss_transport_failure"
                guard.persist(
                    self._evidence(
                        provider="HELIUS",
                        kind="WSS_TERMINAL",
                        body=b"",
                        metadata={
                            "request": request.safe_receipt(),
                            "stop_reason": capture.stop_reason,
                        },
                        response_status=self._terminal_status(
                            capture.terminal_class
                        ),
                        error_class=error_class,
                    ),
                    stream=False,
                )
                raise ProbeStopError(error_class)
            try:
                subscription_id = parse_subscription_ack(
                    capture.acknowledgement
                )
            except (ProbeStopError, ProbeTransportContractError) as exc:
                guard.persist(
                    self._evidence(
                        provider="HELIUS",
                        kind="WSS_SUBSCRIPTION_ACK",
                        body=capture.acknowledgement,
                        metadata={"request": request.safe_receipt()},
                        observed_at=(
                            capture.acknowledgement_observed_at
                        ),
                        response_status=RawResponseStatus.INVALID_RESPONSE,
                        error_class=self._safe_error_class(exc),
                    ),
                    stream=True,
                )
                raise
            guard.persist(
                self._evidence(
                    provider="HELIUS",
                    kind="WSS_SUBSCRIPTION_ACK",
                    body=capture.acknowledgement,
                    metadata={
                        "request": request.safe_receipt(),
                        "subscription_id": subscription_id,
                    },
                    observed_at=capture.acknowledgement_observed_at,
                ),
                stream=True,
            )

            candidate_signatures: list[str] = []
            seen_signatures: set[str] = set()
            successful_notifications = 0
            failed_notifications = 0
            decoded_events = 0
            create_events = 0
            unsupported = 0
            for body, observed_at in zip(
                capture.notifications,
                capture.notification_observed_at,
            ):
                guard.notifications += 1
                try:
                    parsed = parse_logs_notification(
                        body,
                        expected_subscription_id=subscription_id,
                        event_plan=self.event_plan,
                    )
                except (ProbeStopError, ProbeTransportContractError) as exc:
                    guard.persist(
                        self._evidence(
                            provider="HELIUS",
                            kind="WSS_LOGS_NOTIFICATION",
                            body=body,
                            metadata={"request": request.safe_receipt()},
                            observed_at=observed_at,
                            response_status=(
                                RawResponseStatus.INVALID_RESPONSE
                            ),
                            error_class=self._safe_error_class(exc),
                        ),
                        stream=True,
                    )
                    raise
                metadata: dict[str, JsonValue] = {
                    "decoded_event_names": [
                        event.event_name for event in parsed.decoded_events
                    ],
                    "logs_truncated": parsed.logs_truncated,
                    "request": request.safe_receipt(),
                    "signature_sha256": hashlib.sha256(
                        parsed.signature.encode("ascii")
                    ).hexdigest(),
                    "slot": parsed.slot,
                    "transaction_succeeded": parsed.transaction_succeeded,
                    "unsupported_pump_program_data": (
                        parsed.unsupported_pump_program_data
                    ),
                }
                if parsed.logs_truncated:
                    guard.truncated_notifications += 1
                    guard.persist(
                        self._evidence(
                            provider="HELIUS",
                            kind="WSS_LOGS_NOTIFICATION",
                            body=body,
                            metadata=metadata,
                            observed_at=observed_at,
                            response_status=(
                                RawResponseStatus.INVALID_RESPONSE
                            ),
                            error_class="program_logs_truncated",
                        ),
                        stream=True,
                    )
                    continue
                if parsed.transaction_succeeded:
                    successful_notifications += 1
                else:
                    failed_notifications += 1
                decoded_events += len(parsed.decoded_events)
                create_events += sum(
                    event.event_name == "CreateEvent"
                    for event in parsed.decoded_events
                )
                unsupported += parsed.unsupported_pump_program_data
                guard.persist(
                    self._evidence(
                        provider="HELIUS",
                        kind="WSS_LOGS_NOTIFICATION",
                        body=body,
                        metadata=metadata,
                        observed_at=observed_at,
                    ),
                    stream=True,
                )
                if (
                    parsed.is_followup_candidate
                    and parsed.signature not in seen_signatures
                ):
                    seen_signatures.add(parsed.signature)
                    candidate_signatures.append(parsed.signature)

            if capture.terminal_class != "BOUND_REACHED":
                error_class = capture.error_class or "wss_transport_failure"
                guard.persist(
                    self._evidence(
                        provider="HELIUS",
                        kind="WSS_TERMINAL",
                        body=b"",
                        metadata={
                            "request": request.safe_receipt(),
                            "stop_reason": capture.stop_reason,
                        },
                        response_status=self._terminal_status(
                            capture.terminal_class
                        ),
                        error_class=error_class,
                    ),
                    stream=False,
                )
                raise ProbeStopError(error_class)

            if (
                len(candidate_signatures)
                > self.plan.probe_budget["rpc_followups"]
            ):
                raise ProbeStopError("rpc_followup_candidate_cap_exceeded")
            tracker_failures += self._tracker_phase(
                guard,
                phase="CLOSE",
            )
            for ordinal, signature in enumerate(
                candidate_signatures,
                start=1,
            ):
                self._followup(
                    guard,
                    signature=signature,
                    ordinal=ordinal,
                )
            guard.finalize()
            usage = guard.validate()
        except Exception as exc:
            finalize_error: Exception | None = None
            try:
                guard.finalize()
            except Exception as finalize_exc:
                finalize_error = finalize_exc
            self._last_safe_failure_receipt = guard.safe_usage_receipt(
                tracker_failures=tracker_failures,
                stop_error_class=self._safe_error_class(exc),
                finalize_error_class=(
                    None
                    if finalize_error is None
                    else self._safe_error_class(finalize_error)
                ),
            )
            if finalize_error is not None:
                raise ProbeStopError(
                    "probe_failed_and_durable_finalize_failed:"
                    f"{type(exc).__name__}"
                ) from finalize_error
            raise
        return ProbeSummary(
            status=(
                "COMPLETE_REQUIRES_ACCEPTANCE"
                if create_events
                else "NOT_TESTABLE_IN_WINDOW"
            ),
            elapsed_seconds=guard.elapsed_seconds,
            notifications=guard.notifications,
            successful_notifications=successful_notifications,
            failed_notifications=failed_notifications,
            truncated_notifications=guard.truncated_notifications,
            decoded_events=decoded_events,
            create_events=create_events,
            unsupported_pump_program_data=unsupported,
            unique_followup_candidates=len(candidate_signatures),
            rpc_followups=guard.rpc_followups,
            solana_tracker_requests=guard.solana_tracker_requests,
            solana_tracker_failures=tracker_failures,
            stream_bytes=guard.stream_bytes,
            received_bytes=guard.received_bytes,
            stored_bytes=guard.stored_bytes,
            received_and_stored_bytes=(
                guard.received_bytes + guard.stored_bytes
            ),
            helius_credits=usage["helius_credits"],
            evidence_records=guard.evidence_records,
            wss_stop_reason=capture.stop_reason,
            retries=0,
            concurrency=1,
            cash_spend_usd_cents=0,
        )


def safe_preflight_summary(
    plan: DiscoveryPlan,
    event_plan: PumpEventPlan,
) -> dict[str, JsonValue]:
    """Return the exact offline request plan without credentials or endpoints."""

    if event_plan.program_id != PUMP_PROGRAM_ID:
        raise ProbeTransportContractError("pump_program_plan_drift")
    expected_budget = {
        "elapsed_seconds": 600,
        "wss_connections": 1,
        "wss_subscriptions": 1,
        "notifications": 500,
        "stream_bytes": 1_000_000,
        "rpc_followups": 20,
        "helius_credits": 41,
        "solana_tracker_requests": 8,
        "received_and_stored_bytes": 5_000_000,
        "concurrency": 1,
        "retries": 0,
        "cash_spend_usd_cents": 0,
    }
    if plan.probe_budget != expected_budget:
        raise ProbeTransportContractError("probe_budget_drift")
    proof = admission_budget_proof()
    return {
        "admission_budget_proof": proof,
        "admission_received_bytes_cap": MAX_ADMITTED_RECEIVED_BYTES,
        "atom": "T08-A5U",
        "cash_spend_usd_cents": 0,
        "concurrency": 1,
        "credential_prompted": False,
        "concrete_adapters_ready": True,
        "durable_output_created": False,
        "durable_output_logical_root": RAW_LOGICAL_ROOT,
        "external_authority_required": True,
        "followup_method": "getTransaction",
        "network_authorized": False,
        "provider_requests_planned": 0,
        "pump_event_inventory": [
            event.name for event in event_plan.events
        ],
        "retries": 0,
        "tracker_paths": list(TRACKER_PATHS),
        "tracker_category_limit": TRACKER_OVERVIEW_LIMIT,
        "tracker_max_response_bytes": TRACKER_MAX_RESPONSE_BYTES,
        "tracker_planned_requests": len(TRACKER_PATHS) * len(TRACKER_PHASES),
        "transport_contract_version": TRANSPORT_CONTRACT_VERSION,
        "wss_capture_seconds": WSS_CAPTURE_SECONDS,
        "wss_commitment": "confirmed",
        "wss_method": "logsSubscribe",
        "wss_program_id": PUMP_PROGRAM_ID,
    }


def assert_atom4_offline_boundary(
    *,
    network_requested: bool = False,
    credential_use_requested: bool = False,
    local_data_write_requested: bool = False,
    dependency_change_requested: bool = False,
) -> None:
    """Keep every real side effect outside the T08-A4 authority envelope."""

    requested = {
        "network": network_requested,
        "credential_use": credential_use_requested,
        "local_data_write": local_data_write_requested,
        "dependency_change": dependency_change_requested,
    }
    for name, enabled in requested.items():
        if enabled:
            raise ExternalAuthorityRequiredError(
                f"atom4_{name}_requires_later_authority"
            )
