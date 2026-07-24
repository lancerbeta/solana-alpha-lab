"""Bounded transport binding for a separately authorized TASK-07 live smoke."""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, TypeAlias

from solana_alpha_lab.contracts.schema_v1 import (
    PartitionManifest,
    RawApiEvent,
    RawResponseStatus,
)
from solana_alpha_lab.provider_smoke import (
    EXPECTED_HELIUS_CREDIT_CAP,
    JsonValue,
    NetworkDisabledError,
    ProhibitedPayloadError,
    PROVIDER_POLICIES,
    RUNTIME_CONTRACT_VERSION,
    RUNTIME_EVIDENCE_AS_OF,
    SmokeContractError,
    SmokePlan,
    SmokeRunGuard,
    StopConditionError,
    materialize_case,
    validate_response_payload,
)
from solana_alpha_lab.storage import (
    StorageBudgetPolicy,
    build_raw_api_event,
    canonical_manifest_bytes,
    compute_dataset_manifest_id,
    verify_raw_event_partition,
    write_budgeted_raw_event_partition,
)

TRANSPORT_CONTRACT_VERSION = "1.0"
EXTERNAL_AUTHORITY_PHRASE = "TASK07_A4B_EXTERNAL_ACCOUNT_API_RPC_WSS"
RAPTOR_TAIL_AUTHORITY_PHRASE = (
    "TASK07_A4B_R6_RAPTOR_TAIL_EXTERNAL"
)
DATASET_ID = "SMIAL_TASK07_PROVIDER_SMOKE_RAW"
DATASET_VERSION = "1.0"
RAW_LOGICAL_ROOT = "task07_provider_smoke_v1"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 20.0
MAX_WSS_OPEN_SECONDS = 10.0
MAX_WSS_DATA_MESSAGES = 1

_BASE_URLS = {
    "HELIUS_RPC": "https://mainnet.helius-rpc.com/",
    "HELIUS_WSS": "wss://mainnet.helius-rpc.com/",
    "SOLANA_TRACKER_DATA": "https://data.solanatracker.io",
    "JUPITER_SWAP": "https://api.jup.ag",
    "RAPTOR_HOSTED": "https://raptor-beta.solanatracker.io",
}
_EXACT_HOSTS = {
    "HELIUS_RPC": ("https", "mainnet.helius-rpc.com"),
    "HELIUS_WSS": ("wss", "mainnet.helius-rpc.com"),
    "SOLANA_TRACKER_DATA": ("https", "data.solanatracker.io"),
    "JUPITER_SWAP": ("https", "api.jup.ag"),
    "RAPTOR_HOSTED": ("https", "raptor-beta.solanatracker.io"),
}
_EXACT_PATHS = {
    "HELIUS_RPC": frozenset({"/"}),
    "HELIUS_WSS": frozenset({"/"}),
    "JUPITER_SWAP": frozenset({"/swap/v2/order"}),
    "RAPTOR_HOSTED": frozenset({"/health", "/quote"}),
}
_SAFE_RESPONSE_HEADERS = frozenset(
    {
        "content-length",
        "content-type",
        "date",
        "retry-after",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
    }
)
_FORBIDDEN_PATH_MARKERS = (
    "execute",
    "submit",
    "send",
    "swap-instructions",
    "quote-and-swap",
    "transaction",
    "webhook",
    "payment",
    "x402",
)
_TERMINAL_CLASSES = frozenset(
    {
        "SUCCESS",
        "TIMEOUT",
        "DNS_OR_TLS",
        "AUTH",
        "RATE_LIMIT_429",
        "PROVIDER_4XX",
        "PROVIDER_5XX",
        "INVALID_REQUEST",
        "NO_ROUTE",
        "EMPTY_VALID",
        "MALFORMED_PAYLOAD",
        "SCHEMA_DRIFT",
        "RESPONSE_TOO_LARGE",
        "PROHIBITED_PAYLOAD",
        "STOP_CAP",
    }
)
_IMMEDIATE_STOP_TERMINALS = frozenset(
    {
        "AUTH",
        "DNS_OR_TLS",
        "PROHIBITED_PAYLOAD",
        "RATE_LIMIT_429",
        "RESPONSE_TOO_LARGE",
        "STOP_CAP",
        "TIMEOUT",
    }
)

JsonObject: TypeAlias = dict[str, JsonValue]


class TransportContractError(SmokeContractError):
    """The transport request or durable-output boundary is invalid."""


class ExternalAuthorityRequiredError(NetworkDisabledError):
    """The explicit later external-action gate is absent."""


class TransportExecutionError(RuntimeError):
    """A bounded transport operation failed before a provider response."""


class DynamicBindingError(TransportContractError):
    """A frozen downstream binding cannot be extracted from safe evidence."""


class RecoveryEvidenceError(TransportContractError):
    """An immutable parent run is not an exact recoverable prefix."""


def _validate_secret(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise TransportContractError(f"{name}_must_be_text")
    if value != value.strip() or not 8 <= len(value) <= 512:
        raise TransportContractError(f"{name}_invalid")
    if any(ord(character) < 33 or ord(character) == 127 for character in value):
        raise TransportContractError(f"{name}_invalid")
    return value


@dataclass(frozen=True, slots=True, repr=False)
class ProviderCredentials:
    """In-memory provider secrets with a permanently redacted representation."""

    helius_api_key: str = field(repr=False)
    solana_tracker_api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        _validate_secret("helius_credential", self.helius_api_key)
        _validate_secret(
            "solana_tracker_credential",
            self.solana_tracker_api_key,
        )

    def __repr__(self) -> str:
        return "ProviderCredentials(<redacted>)"

    @property
    def explicit_secret_values(self) -> tuple[str, str]:
        return (self.helius_api_key, self.solana_tracker_api_key)


@dataclass(frozen=True, slots=True)
class ExternalExecutionGate:
    """Exact non-secret tripwire; it does not replace human authority."""

    authority_phrase: str

    def require(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise ExternalAuthorityRequiredError(
                "external_authority_phrase_mismatch"
            )

    @property
    def authority_scope(self) -> str:
        return EXTERNAL_AUTHORITY_PHRASE


@dataclass(frozen=True, slots=True)
class RaptorTailExecutionGate:
    """Separate tripwire for the exact keyless R04/R05 recovery."""

    authority_phrase: str

    def require(self) -> None:
        if self.authority_phrase != RAPTOR_TAIL_AUTHORITY_PHRASE:
            raise ExternalAuthorityRequiredError(
                "raptor_tail_authority_phrase_mismatch"
            )

    @property
    def authority_scope(self) -> str:
        return RAPTOR_TAIL_AUTHORITY_PHRASE



@dataclass(frozen=True, slots=True, repr=False)
class BoundRequest:
    """One secret-bound request whose representation is always sanitized."""

    attempt_id: str
    case_id: str
    provider: str
    transport: str
    method: str
    url: str = field(repr=False)
    headers: tuple[tuple[str, str], ...] = field(repr=False)
    body: bytes = field(repr=False)
    timeout_seconds: float
    safe_query_keys: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "BoundRequest("
            f"attempt_id={self.attempt_id!r}, "
            f"provider={self.provider!r}, "
            f"transport={self.transport!r}, "
            f"method={self.method!r}, "
            "url=<redacted>, headers=<redacted>, body=<redacted>)"
        )

    def safe_receipt(self) -> dict[str, JsonValue]:
        parsed = urllib.parse.urlsplit(self.url)
        return {
            "attempt_id": self.attempt_id,
            "body_sha256": hashlib.sha256(self.body).hexdigest(),
            "case_id": self.case_id,
            "host": parsed.hostname,
            "method": self.method,
            "path": parsed.path or "/",
            "provider": self.provider,
            "query_keys": list(self.safe_query_keys),
            "transport": self.transport,
        }


@dataclass(frozen=True, slots=True, repr=False)
class TransportResponse:
    """Bounded provider observation; the response body is never represented."""

    status_code: int | None
    body: bytes = field(repr=False)
    safe_headers: tuple[tuple[str, str], ...]
    terminal_class: str
    error_class: str | None
    request_started_at: datetime
    request_sent_at: datetime
    response_headers_at: datetime | None
    response_complete_at: datetime

    def __post_init__(self) -> None:
        if self.terminal_class not in _TERMINAL_CLASSES:
            raise TransportContractError("unknown_terminal_class")
        for value in (
            self.request_started_at,
            self.request_sent_at,
            self.response_complete_at,
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise TransportContractError("transport_timestamp_not_aware")
        if (
            self.response_headers_at is not None
            and (
                self.response_headers_at.tzinfo is None
                or self.response_headers_at.utcoffset() is None
            )
        ):
            raise TransportContractError("transport_timestamp_not_aware")
        if not (
            self.request_started_at
            <= self.request_sent_at
            <= self.response_complete_at
        ):
            raise TransportContractError("transport_timestamp_order_invalid")
        if (
            self.response_headers_at is not None
            and not (
                self.request_sent_at
                <= self.response_headers_at
                <= self.response_complete_at
            )
        ):
            raise TransportContractError("response_header_time_invalid")

    def __repr__(self) -> str:
        return (
            "TransportResponse("
            f"status_code={self.status_code!r}, "
            f"terminal_class={self.terminal_class!r}, "
            f"error_class={self.error_class!r}, body=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class AttemptReceipt:
    """Sanitized per-attempt receipt safe for local evidence."""

    attempt_id: str
    case_id: str
    provider: str
    terminal_class: str
    response_status: str
    error_class: str | None
    status_code: int | None
    response_size_bytes: int
    redacted_body_sha256: str
    request_started_at: str
    request_sent_at: str
    response_headers_at: str | None
    response_complete_at: str
    safe_request: dict[str, JsonValue]
    safe_response_headers: tuple[tuple[str, str], ...]

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            {
                "attempt_id": self.attempt_id,
                "case_id": self.case_id,
                "error_class": self.error_class,
                "provider": self.provider,
                "redacted_body_sha256": self.redacted_body_sha256,
                "request_sent_at": self.request_sent_at,
                "request_started_at": self.request_started_at,
                "response_complete_at": self.response_complete_at,
                "response_headers_at": self.response_headers_at,
                "response_size_bytes": self.response_size_bytes,
                "response_status": self.response_status,
                "safe_request": self.safe_request,
                "safe_response_headers": [
                    list(item) for item in self.safe_response_headers
                ],
                "status_code": self.status_code,
                "terminal_class": self.terminal_class,
                "transport_contract_version": TRANSPORT_CONTRACT_VERSION,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Sanitized result of one bounded live run."""

    run_id: str
    planned_attempts: int
    completed_attempts: int
    terminal_counts: dict[str, int]
    helius_credits: int
    response_bytes: int
    cash_spend_usd: float
    output_logical_root: str


@dataclass(frozen=True, slots=True)
class RaptorTailRecovery:
    """Offline-verified parent prefix and exact missing Raptor suffix."""

    parent_run_id: str
    parent_run_directory: Path
    verified_attempts: tuple[str, ...]
    pending_attempts: tuple[str, ...]
    produced_bindings: tuple[tuple[str, JsonValue], ...]
    reclassified_attempts: tuple[tuple[str, str], ...]
    verified_file_count: int

    @property
    def bindings(self) -> dict[str, JsonValue]:
        return dict(self.produced_bindings)


@dataclass(frozen=True, slots=True)
class RaptorTailSummary:
    """Sanitized result of one exact two-attempt recovery child run."""

    parent_run_id: str
    child_run_id: str
    planned_attempts: int
    completed_attempts: int
    terminal_counts: dict[str, int]
    response_bytes: int
    cash_spend_usd: float
    output_logical_root: str


class ExecutionGate(Protocol):
    @property
    def authority_scope(self) -> str: ...

    def require(self) -> None: ...


class HttpExchange(Protocol):
    def __call__(
        self,
        request: BoundRequest,
        *,
        max_response_bytes: int,
    ) -> TransportResponse: ...


class WssSession(Protocol):
    def subscribe(
        self,
        request: BoundRequest,
        *,
        max_response_bytes: int,
        max_open_seconds: float,
        max_data_messages: int,
    ) -> tuple[TransportResponse, int | None]: ...

    def unsubscribe(
        self,
        request: BoundRequest,
        *,
        max_response_bytes: int,
    ) -> TransportResponse: ...

    def close(self) -> None: ...


EventSink = Callable[[RawApiEvent, AttemptReceipt], None]


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TransportContractError("request_json_invalid") from exc


def _scalar_query_pairs(query: object) -> list[tuple[str, str]]:
    if not isinstance(query, Mapping):
        raise TransportContractError("query_must_be_mapping")
    pairs: list[tuple[str, str]] = []
    for key in sorted(query):
        value = query[key]
        if not isinstance(key, str) or not key:
            raise TransportContractError("query_key_invalid")
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise TransportContractError("query_value_not_scalar")
        pairs.append((key, str(value)))
    return pairs


def _validate_bound_target(
    *,
    provider: str,
    url: str,
    expected_path: str,
    expected_query_keys: Sequence[str],
) -> None:
    try:
        split = urllib.parse.urlsplit(url)
    except ValueError as exc:
        raise TransportContractError("bound_url_invalid") from exc
    expected_scheme, expected_host = _EXACT_HOSTS[provider]
    if (
        split.scheme != expected_scheme
        or split.hostname != expected_host
        or split.port is not None
        or split.username is not None
        or split.password is not None
        or split.fragment
    ):
        raise TransportContractError("bound_endpoint_not_allowlisted")
    path = split.path or "/"
    if path != expected_path:
        raise TransportContractError("bound_path_mismatch")
    allowed_paths = _EXACT_PATHS.get(provider)
    if allowed_paths is not None and path not in allowed_paths:
        raise TransportContractError("bound_path_not_allowlisted")
    lowered = path.casefold()
    if any(marker in lowered for marker in _FORBIDDEN_PATH_MARKERS):
        raise ProhibitedPayloadError("forbidden_transport_path")
    parsed_query = urllib.parse.parse_qsl(
        split.query,
        keep_blank_values=True,
        strict_parsing=True,
    )
    if sorted(key for key, _ in parsed_query) != sorted(expected_query_keys):
        raise TransportContractError("bound_query_key_mismatch")


def bind_request(
    plan: SmokePlan,
    *,
    attempt_id: str,
    materialized_request: Mapping[str, Any],
    credentials: ProviderCredentials | None,
    wss_subscription_id: int | None = None,
    produced_bindings: Mapping[str, JsonValue] | None = None,
) -> BoundRequest:
    """Bind one exact frozen request to an allowlisted in-memory transport."""

    if attempt_id not in plan.attempt_ids:
        raise TransportContractError("attempt_not_in_plan")
    case_id, separator, attempt_text = attempt_id.rpartition("#")
    if not separator or not attempt_text.isdigit():
        raise TransportContractError("attempt_id_invalid")
    try:
        case = plan.case_by_id[case_id]
    except KeyError as exc:
        raise TransportContractError("attempt_case_unknown") from exc
    if materialized_request.get("case_id") != case_id:
        raise TransportContractError("materialized_case_mismatch")
    if materialized_request.get("provider") != case.provider:
        raise TransportContractError("materialized_provider_mismatch")
    expected_materialized = materialize_case(
        plan,
        case_id,
        produced_bindings=produced_bindings,
    )
    if materialized_request != expected_materialized:
        if materialized_request.get("path") != expected_materialized.get(
            "path"
        ):
            raise TransportContractError("materialized_path_mismatch")
        raise TransportContractError("materialized_request_mismatch")
    materialized_path = materialized_request.get("path")
    if not isinstance(materialized_path, str):
        raise TransportContractError("materialized_path_mismatch")

    base_url = _BASE_URLS[case.provider]
    headers: list[tuple[str, str]] = [
        ("accept", "application/json"),
        ("user-agent", "smial-task07-smoke/1.0"),
    ]
    safe_query_pairs: list[tuple[str, str]] = []
    secret_query_pairs: list[tuple[str, str]] = []
    body = b""
    transport = "HTTP"
    method = "GET"

    if case.provider == "HELIUS_RPC":
        if credentials is None:
            raise TransportContractError("helius_credential_required")
        method = "POST"
        headers.append(("content-type", "application/json"))
        secret_query_pairs.append(("api-key", credentials.helius_api_key))
        body = _json_bytes(
            {
                "id": attempt_id,
                "jsonrpc": "2.0",
                "method": materialized_request.get("rpc_method"),
                "params": materialized_request.get("params", []),
            }
        )
    elif case.provider == "HELIUS_WSS":
        if credentials is None:
            raise TransportContractError("helius_credential_required")
        transport = "WSS"
        method = "POST"
        secret_query_pairs.append(("api-key", credentials.helius_api_key))
        attempt_number = int(attempt_text)
        if attempt_number == 1:
            rpc_method = "accountSubscribe"
            params = materialized_request.get("params", [])
            if wss_subscription_id is not None:
                raise TransportContractError(
                    "subscription_id_for_subscribe_forbidden"
                )
        elif attempt_number == 2:
            rpc_method = "accountUnsubscribe"
            if (
                isinstance(wss_subscription_id, bool)
                or not isinstance(wss_subscription_id, int)
                or wss_subscription_id < 0
            ):
                raise TransportContractError(
                    "unsubscribe_subscription_id_invalid"
                )
            params = [wss_subscription_id]
        else:
            raise TransportContractError("unexpected_wss_attempt_number")
        body = _json_bytes(
            {
                "id": attempt_id,
                "jsonrpc": "2.0",
                "method": rpc_method,
                "params": params,
            }
        )
    else:
        safe_query_pairs = _scalar_query_pairs(
            materialized_request.get("query", {})
        )
        if case.provider == "SOLANA_TRACKER_DATA":
            if credentials is None:
                raise TransportContractError(
                    "solana_tracker_credential_required"
                )
            headers.append(
                ("x-api-key", credentials.solana_tracker_api_key)
            )

    encoded_path = urllib.parse.quote(materialized_path, safe="/")
    query_pairs = safe_query_pairs + secret_query_pairs
    query = urllib.parse.urlencode(query_pairs)
    url = f"{base_url.rstrip('/')}{encoded_path}"
    if query:
        url = f"{url}?{query}"
    expected_query_keys = [key for key, _ in query_pairs]
    _validate_bound_target(
        provider=case.provider,
        url=url,
        expected_path=materialized_path,
        expected_query_keys=expected_query_keys,
    )
    return BoundRequest(
        attempt_id=attempt_id,
        case_id=case_id,
        provider=case.provider,
        transport=transport,
        method=method,
        url=url,
        headers=tuple(headers),
        body=body,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        safe_query_keys=tuple(key for key, _ in safe_query_pairs),
    )


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
        raise TransportExecutionError("redirect_forbidden")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_headers(headers: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                key.casefold(),
                value,
            )
            for key, value in headers.items()
            if key.casefold() in _SAFE_RESPONSE_HEADERS
        )
    )


def _read_bounded(stream: Any, maximum: int) -> bytes:
    body = stream.read(maximum + 1)
    if len(body) > maximum:
        raise StopConditionError("response_too_large")
    return body


def _http_terminal(status_code: int, body: bytes) -> tuple[str, str | None]:
    if status_code in {401, 403}:
        return "AUTH", f"http_{status_code}"
    if status_code == 429:
        return "RATE_LIMIT_429", "http_429"
    if 400 <= status_code < 500:
        if status_code in {400, 404, 409, 422}:
            return "INVALID_REQUEST", f"http_{status_code}"
        return "PROVIDER_4XX", f"http_{status_code}"
    if status_code >= 500:
        return "PROVIDER_5XX", f"http_{status_code}"
    if not body:
        return "EMPTY_VALID", "empty_response"
    return "SUCCESS", None


def _classified(
    response: TransportResponse,
    terminal_class: str,
    error_class: str | None,
) -> TransportResponse:
    return replace(
        response,
        terminal_class=terminal_class,
        error_class=error_class,
    )


def classify_response(
    plan: SmokePlan,
    *,
    request: BoundRequest,
    materialized_request: Mapping[str, Any],
    response: TransportResponse,
) -> TransportResponse:
    """Classify safe response shape without retry or durable mutation."""

    if response.terminal_class != "SUCCESS":
        return response
    if request.provider == "HELIUS_WSS":
        return response
    case = plan.case_by_id[request.case_id]
    if (
        request.provider == "RAPTOR_HOSTED"
        and request.case_id == "R01"
        and "INDEXED_BASE" in case.assertion_sets
    ):
        if response.body == b"OK":
            return response
        return _classified(
            response,
            "SCHEMA_DRIFT",
            "raptor_health_body_invalid",
        )
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _classified(
            response,
            "MALFORMED_PAYLOAD",
            "response_not_json",
        )

    if "JSON_RPC_BASE" in case.assertion_sets:
        if not isinstance(payload, dict):
            return _classified(
                response,
                "SCHEMA_DRIFT",
                "json_rpc_response_not_mapping",
            )
        if payload.get("jsonrpc") != "2.0":
            return _classified(
                response,
                "SCHEMA_DRIFT",
                "json_rpc_version_mismatch",
            )
        if payload.get("id") != request.attempt_id:
            return _classified(
                response,
                "SCHEMA_DRIFT",
                "json_rpc_id_mismatch",
            )
        result_present = "result" in payload
        error_present = payload.get("error") not in (None, "")
        if result_present == error_present:
            return _classified(
                response,
                "SCHEMA_DRIFT",
                "json_rpc_result_error_incoherent",
            )
        if error_present:
            return _classified(
                response,
                "INVALID_REQUEST",
                "json_rpc_typed_error",
            )
    elif "INDEXED_BASE" in case.assertion_sets:
        if not isinstance(payload, (dict, list)):
            return _classified(
                response,
                "SCHEMA_DRIFT",
                "indexed_response_not_json_container",
            )
        if payload in ({}, []):
            return _classified(
                response,
                "EMPTY_VALID",
                "indexed_response_empty",
            )
    elif "QUOTE_BASE" in case.assertion_sets:
        if not isinstance(payload, dict):
            return _classified(
                response,
                "SCHEMA_DRIFT",
                "quote_response_not_mapping",
            )
        error_value = payload.get("error")
        if error_value not in (None, ""):
            error_text = json.dumps(
                error_value,
                ensure_ascii=False,
                sort_keys=True,
            ).casefold()
            terminal = (
                "NO_ROUTE"
                if "route" in error_text
                else "INVALID_REQUEST"
            )
            return _classified(
                response,
                terminal,
                "quote_typed_error",
            )
        output_keys = (
            ("amountOut",)
            if request.provider == "RAPTOR_HOSTED"
            else ("outAmount", "outputAmount", "out_amount")
        )
        output_amount = next(
            (
                payload[key]
                for key in output_keys
                if key in payload
            ),
            None,
        )
        if (
            not isinstance(output_amount, str)
            or not output_amount.isdigit()
        ):
            return _classified(
                response,
                "SCHEMA_DRIFT",
                "quote_output_amount_invalid",
            )

    expected_terminal = materialized_request.get("expected_terminal")
    if expected_terminal is not None:
        return _classified(
            response,
            "SCHEMA_DRIFT",
            "negative_case_unexpected_success",
        )
    return response


def stdlib_http_exchange(
    request: BoundRequest,
    *,
    max_response_bytes: int,
) -> TransportResponse:
    """Execute one no-redirect HTTP exchange after the outer authority gate."""

    if request.transport != "HTTP":
        raise TransportContractError("http_exchange_requires_http_request")
    started = _utc_now()
    outgoing = urllib.request.Request(
        request.url,
        data=request.body if request.method == "POST" else None,
        headers=dict(request.headers),
        method=request.method,
    )
    sent = _utc_now()
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(outgoing, timeout=request.timeout_seconds) as response:
            headers_at = _utc_now()
            body = _read_bounded(response, max_response_bytes)
            completed = _utc_now()
            status_code = int(response.status)
            terminal, error_class = _http_terminal(status_code, body)
            return TransportResponse(
                status_code=status_code,
                body=body,
                safe_headers=_safe_headers(response.headers),
                terminal_class=terminal,
                error_class=error_class,
                request_started_at=started,
                request_sent_at=sent,
                response_headers_at=headers_at,
                response_complete_at=completed,
            )
    except urllib.error.HTTPError as exc:
        headers_at = _utc_now()
        body = _read_bounded(exc, max_response_bytes)
        completed = _utc_now()
        terminal, error_class = _http_terminal(exc.code, body)
        return TransportResponse(
            status_code=exc.code,
            body=body,
            safe_headers=_safe_headers(exc.headers),
            terminal_class=terminal,
            error_class=error_class,
            request_started_at=started,
            request_sent_at=sent,
            response_headers_at=headers_at,
            response_complete_at=completed,
        )
    except StopConditionError:
        raise
    except (TimeoutError, socket.timeout) as exc:
        completed = _utc_now()
        return TransportResponse(
            status_code=None,
            body=b"",
            safe_headers=(),
            terminal_class="TIMEOUT",
            error_class=type(exc).__name__,
            request_started_at=started,
            request_sent_at=sent,
            response_headers_at=None,
            response_complete_at=completed,
        )
    except (
        urllib.error.URLError,
        ssl.SSLError,
        socket.gaierror,
        ConnectionError,
    ) as exc:
        completed = _utc_now()
        return TransportResponse(
            status_code=None,
            body=b"",
            safe_headers=(),
            terminal_class="DNS_OR_TLS",
            error_class=type(exc).__name__,
            request_started_at=started,
            request_sent_at=sent,
            response_headers_at=None,
            response_complete_at=completed,
        )


def _bounded_wss_message(value: object, maximum: int) -> bytes:
    if isinstance(value, str):
        body = value.encode("utf-8")
    elif isinstance(value, bytes):
        body = value
    else:
        raise TransportExecutionError("websocket_message_type_invalid")
    if len(body) > maximum:
        raise StopConditionError("response_too_large")
    return body


def _wss_subscription_id(body: bytes) -> int:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportExecutionError("wss_subscribe_ack_invalid") from exc
    result = payload.get("result") if isinstance(payload, dict) else None
    if isinstance(result, bool) or not isinstance(result, int) or result < 0:
        raise TransportExecutionError("wss_subscription_id_invalid")
    return result


def _wss_failure_response(
    *,
    started: datetime,
    sent: datetime,
    terminal_class: str,
    error_class: str,
    body: bytes = b"",
) -> TransportResponse:
    completed = _utc_now()
    return TransportResponse(
        status_code=None,
        body=body,
        safe_headers=(),
        terminal_class=terminal_class,
        error_class=error_class,
        request_started_at=started,
        request_sent_at=sent,
        response_headers_at=None,
        response_complete_at=completed,
    )


class WebsocketsSyncSession:
    """One non-reconnecting Helius WSS session with a shared ten-second cap."""

    def __init__(self) -> None:
        self._websocket: Any | None = None
        self._started_monotonic: float | None = None
        self._max_open_seconds: float | None = None

    def _remaining(self) -> float:
        if (
            self._started_monotonic is None
            or self._max_open_seconds is None
        ):
            return 0.0
        return max(
            0.0,
            self._max_open_seconds
            - (time.monotonic() - self._started_monotonic),
        )

    def subscribe(
        self,
        request: BoundRequest,
        *,
        max_response_bytes: int,
        max_open_seconds: float,
        max_data_messages: int,
    ) -> tuple[TransportResponse, int | None]:
        if request.transport != "WSS":
            raise TransportContractError(
                "wss_session_requires_wss_request"
            )
        if max_open_seconds != MAX_WSS_OPEN_SECONDS:
            raise TransportContractError("wss_open_limit_mismatch")
        if max_data_messages != MAX_WSS_DATA_MESSAGES:
            raise TransportContractError("wss_data_message_limit_mismatch")
        if self._websocket is not None:
            raise TransportContractError("wss_session_already_open")

        from websockets.exceptions import PayloadTooBig
        from websockets.sync.client import connect

        started = _utc_now()
        sent = started
        self._started_monotonic = time.monotonic()
        self._max_open_seconds = max_open_seconds
        try:
            self._websocket = connect(
                request.url,
                open_timeout=min(request.timeout_seconds, 5.0),
                close_timeout=0.2,
                max_size=max_response_bytes,
                compression=None,
                additional_headers=dict(request.headers),
                ping_interval=None,
                proxy=None,
            )
            self._websocket.send(request.body)
            sent = _utc_now()
            remaining = self._remaining()
            if remaining <= 2.5:
                return (
                    _wss_failure_response(
                        started=started,
                        sent=sent,
                        terminal_class="STOP_CAP",
                        error_class="wss_open_budget_exhausted",
                    ),
                    None,
                )
            ack = _bounded_wss_message(
                self._websocket.recv(timeout=remaining - 2.0),
                max_response_bytes,
            )
            headers_at = _utc_now()
            try:
                subscription_id = _wss_subscription_id(ack)
                parsed_ack = json.loads(ack)
            except TransportExecutionError:
                return (
                    TransportResponse(
                        status_code=101,
                        body=ack,
                        safe_headers=(),
                        terminal_class="SCHEMA_DRIFT",
                        error_class="wss_subscribe_ack_invalid",
                        request_started_at=started,
                        request_sent_at=sent,
                        response_headers_at=headers_at,
                        response_complete_at=_utc_now(),
                    ),
                    None,
                )

            data_messages: list[JsonValue] = []
            notification_wait = max(0.0, self._remaining() - 2.0)
            if notification_wait > 0 and max_data_messages:
                try:
                    message = _bounded_wss_message(
                        self._websocket.recv(timeout=notification_wait),
                        max_response_bytes,
                    )
                    data_messages.append(json.loads(message))
                except TimeoutError:
                    pass
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return (
                        _wss_failure_response(
                            started=started,
                            sent=sent,
                            terminal_class="SCHEMA_DRIFT",
                            error_class="wss_notification_invalid",
                            body=ack,
                        ),
                        None,
                    )
            combined = _json_bytes(
                {
                    "data_messages": data_messages,
                    "subscribe_ack": parsed_ack,
                }
            )
            if len(combined) > max_response_bytes:
                return (
                    _wss_failure_response(
                        started=started,
                        sent=sent,
                        terminal_class="RESPONSE_TOO_LARGE",
                        error_class="wss_combined_response_too_large",
                    ),
                    None,
                )
            return (
                TransportResponse(
                    status_code=101,
                    body=combined,
                    safe_headers=(),
                    terminal_class="SUCCESS",
                    error_class=None,
                    request_started_at=started,
                    request_sent_at=sent,
                    response_headers_at=headers_at,
                    response_complete_at=_utc_now(),
                ),
                subscription_id,
            )
        except (TimeoutError, socket.timeout):
            return (
                _wss_failure_response(
                    started=started,
                    sent=sent,
                    terminal_class="TIMEOUT",
                    error_class="wss_subscribe_timeout",
                ),
                None,
            )
        except PayloadTooBig:
            return (
                _wss_failure_response(
                    started=started,
                    sent=sent,
                    terminal_class="RESPONSE_TOO_LARGE",
                    error_class="wss_response_too_large",
                ),
                None,
            )
        except (OSError, ssl.SSLError, ConnectionError):
            return (
                _wss_failure_response(
                    started=started,
                    sent=sent,
                    terminal_class="DNS_OR_TLS",
                    error_class="wss_connection_failed",
                ),
                None,
            )

    def unsubscribe(
        self,
        request: BoundRequest,
        *,
        max_response_bytes: int,
    ) -> TransportResponse:
        started = _utc_now()
        sent = started
        if self._websocket is None:
            return _wss_failure_response(
                started=started,
                sent=sent,
                terminal_class="STOP_CAP",
                error_class="wss_session_not_open",
            )
        remaining = self._remaining()
        if remaining <= 0:
            return _wss_failure_response(
                started=started,
                sent=sent,
                terminal_class="STOP_CAP",
                error_class="wss_open_budget_exhausted",
            )
        try:
            self._websocket.send(request.body)
            sent = _utc_now()
            ack = _bounded_wss_message(
                self._websocket.recv(timeout=min(remaining, 2.0)),
                max_response_bytes,
            )
            try:
                payload = json.loads(ack)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return _wss_failure_response(
                    started=started,
                    sent=sent,
                    terminal_class="SCHEMA_DRIFT",
                    error_class="wss_unsubscribe_ack_invalid",
                    body=ack,
                )
            if not isinstance(payload, dict) or payload.get("result") is not True:
                return _wss_failure_response(
                    started=started,
                    sent=sent,
                    terminal_class="SCHEMA_DRIFT",
                    error_class="wss_unsubscribe_not_confirmed",
                    body=ack,
                )
            return TransportResponse(
                status_code=101,
                body=ack,
                safe_headers=(),
                terminal_class="SUCCESS",
                error_class=None,
                request_started_at=started,
                request_sent_at=sent,
                response_headers_at=sent,
                response_complete_at=_utc_now(),
            )
        except (TimeoutError, socket.timeout):
            return _wss_failure_response(
                started=started,
                sent=sent,
                terminal_class="TIMEOUT",
                error_class="wss_unsubscribe_timeout",
            )
        except (OSError, ssl.SSLError, ConnectionError):
            return _wss_failure_response(
                started=started,
                sent=sent,
                terminal_class="DNS_OR_TLS",
                error_class="wss_unsubscribe_failed",
            )

    def close(self) -> None:
        websocket = self._websocket
        self._websocket = None
        if websocket is None:
            return
        try:
            websocket.close()
        except Exception:
            return


def _parsed_json(body: bytes) -> JsonValue:
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DynamicBindingError("dynamic_response_not_json") from exc


def _nested_value(value: JsonValue, path: Sequence[str]) -> JsonValue:
    current = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _first_mapping_sequence(value: JsonValue) -> list[JsonObject]:
    candidates: JsonValue = value
    if isinstance(value, dict):
        for key in ("data", "tokens", "result"):
            nested = value.get(key)
            if isinstance(nested, list):
                candidates = nested
                break
    if not isinstance(candidates, list):
        raise DynamicBindingError("dynamic_list_missing")
    return [item for item in candidates if isinstance(item, dict)]


def extract_dynamic_binding(
    case_id: str,
    redacted_body: bytes,
) -> tuple[str, JsonValue] | None:
    """Extract only the three frozen public downstream values."""

    value = _parsed_json(redacted_body)
    if case_id == "H08":
        result = value.get("result") if isinstance(value, dict) else None
        if not isinstance(result, list):
            raise DynamicBindingError("h08_result_missing")
        for item in result:
            if isinstance(item, dict):
                signature = item.get("signature")
                if isinstance(signature, str) and signature:
                    return "RAPTOR_RECENT_SIGNATURE", signature
        raise DynamicBindingError("h08_signature_missing")
    if case_id == "ST03":
        for item in _first_mapping_sequence(value):
            candidates = (
                item.get("mint"),
                item.get("address"),
                _nested_value(item, ("token", "mint")),
                _nested_value(item, ("token", "address")),
            )
            for mint in candidates:
                if isinstance(mint, str) and mint:
                    return "RECENT_PUMP_MINT", mint
        raise DynamicBindingError("st03_mint_missing")
    if case_id == "ST06":
        candidates = (
            value.get("decimals") if isinstance(value, dict) else None,
            _nested_value(value, ("token", "decimals")),
            _nested_value(value, ("data", "decimals")),
            _nested_value(value, ("data", "token", "decimals")),
        )
        for decimals in candidates:
            if (
                isinstance(decimals, int)
                and not isinstance(decimals, bool)
                and 0 <= decimals <= 18
            ):
                return "RECENT_PUMP_DECIMALS", decimals
        pools = value.get("pools") if isinstance(value, dict) else None
        pool_decimals = {
            item.get("decimals")
            for item in pools
            if isinstance(item, dict)
            and isinstance(item.get("decimals"), int)
            and not isinstance(item.get("decimals"), bool)
            and 0 <= item["decimals"] <= 18
        } if isinstance(pools, list) else set()
        if len(pool_decimals) == 1:
            return "RECENT_PUMP_DECIMALS", pool_decimals.pop()
        if len(pool_decimals) > 1:
            raise DynamicBindingError("st06_pool_decimals_ambiguous")
        raise DynamicBindingError("st06_decimals_missing")
    return None


def _response_status(response: TransportResponse) -> RawResponseStatus:
    if response.terminal_class == "SUCCESS":
        return RawResponseStatus.SUCCESS
    if response.terminal_class == "TIMEOUT":
        return RawResponseStatus.TIMEOUT
    if response.status_code is not None and response.status_code >= 400:
        return RawResponseStatus.HTTP_ERROR
    if response.terminal_class in {
        "EMPTY_VALID",
        "MALFORMED_PAYLOAD",
        "SCHEMA_DRIFT",
        "RESPONSE_TOO_LARGE",
        "PROHIBITED_PAYLOAD",
    }:
        return RawResponseStatus.INVALID_RESPONSE
    return RawResponseStatus.PROVIDER_ERROR


def _failure_body(
    *,
    attempt_id: str,
    terminal_class: str,
    error_class: str,
) -> bytes:
    return _json_bytes(
        {
            "attempt_id": attempt_id,
            "error_class": error_class,
            "terminal_class": terminal_class,
        }
    )


def _build_transport_raw_event(
    plan: SmokePlan,
    *,
    request: BoundRequest,
    materialized_request: Mapping[str, Any],
    response_body: bytes,
    response_status: RawResponseStatus,
    error_class: str | None,
    observed_at: datetime,
    ingested_at: datetime,
    credentials: ProviderCredentials | None,
) -> RawApiEvent:
    case = plan.case_by_id[request.case_id]
    explicit_secret_values = (
        credentials.explicit_secret_values
        if credentials is not None
        else ()
    )
    safe_body = validate_response_payload(
        plan,
        request.case_id,
        response_body,
        explicit_secret_values=explicit_secret_values,
    )
    request_identity: dict[str, Any] = dict(materialized_request)
    safe_request = request.safe_receipt()
    request_identity.update(
        {
            "transport_attempt_id": request.attempt_id,
            "transport_body_sha256": safe_request["body_sha256"],
            "transport_host": safe_request["host"],
            "transport_method": request.method,
            "transport_path": safe_request["path"],
            "transport_query_keys": safe_request["query_keys"],
        }
    )
    return build_raw_api_event(
        source=case.provider,
        source_version=f"task07-runtime-{RUNTIME_CONTRACT_VERSION}",
        endpoint_or_method=f"{case.method} {safe_request['path']}",
        request_identity=request_identity,
        response_body=safe_body,
        response_status=response_status,
        error_class=error_class,
        observed_at=observed_at,
        available_to_strategy_at=observed_at,
        ingested_at=ingested_at,
        first_reliable_available_at=observed_at,
        provider_version=f"evidence-as-of-{RUNTIME_EVIDENCE_AS_OF}",
        schema_version="1.0",
        protocol_version="task07-smoke-transport-1.0",
        quality_flags="task07_controlled_smoke",
        explicit_secret_values=explicit_secret_values,
    )


def _attempt_evidence(
    plan: SmokePlan,
    *,
    request: BoundRequest,
    materialized_request: Mapping[str, Any],
    response: TransportResponse,
    credentials: ProviderCredentials | None,
) -> tuple[RawApiEvent, AttemptReceipt, bytes]:
    terminal = response.terminal_class
    error_class = response.error_class
    response_status = _response_status(response)
    body = response.body
    try:
        event = _build_transport_raw_event(
            plan,
            request=request,
            materialized_request=materialized_request,
            response_body=body,
            response_status=response_status,
            error_class=error_class,
            observed_at=response.response_complete_at,
            ingested_at=_utc_now(),
            credentials=credentials,
        )
    except (ProhibitedPayloadError, StopConditionError) as exc:
        terminal = (
            "RESPONSE_TOO_LARGE"
            if isinstance(exc, StopConditionError)
            else "PROHIBITED_PAYLOAD"
        )
        error_class = type(exc).__name__
        response_status = RawResponseStatus.INVALID_RESPONSE
        body = _failure_body(
            attempt_id=request.attempt_id,
            terminal_class=terminal,
            error_class=error_class,
        )
        event = _build_transport_raw_event(
            plan,
            request=request,
            materialized_request=materialized_request,
            response_body=body,
            response_status=response_status,
            error_class=error_class,
            observed_at=response.response_complete_at,
            ingested_at=_utc_now(),
            credentials=credentials,
        )
    receipt = AttemptReceipt(
        attempt_id=request.attempt_id,
        case_id=request.case_id,
        provider=request.provider,
        terminal_class=terminal,
        response_status=str(response_status),
        error_class=error_class,
        status_code=response.status_code,
        response_size_bytes=len(event.redacted_body),
        redacted_body_sha256=event.content_sha256,
        request_started_at=response.request_started_at.isoformat(),
        request_sent_at=response.request_sent_at.isoformat(),
        response_headers_at=(
            response.response_headers_at.isoformat()
            if response.response_headers_at is not None
            else None
        ),
        response_complete_at=response.response_complete_at.isoformat(),
        safe_request=request.safe_receipt(),
        safe_response_headers=response.safe_headers,
    )
    return event, receipt, event.redacted_body


class BoundedProviderTransport:
    """Authority-gated transport with injectable offline test exchanges."""

    def __init__(
        self,
        *,
        gate: ExecutionGate,
        http_exchange: HttpExchange = stdlib_http_exchange,
        wss_session_factory: Callable[[], WssSession] = WebsocketsSyncSession,
    ) -> None:
        gate.require()
        self.authority_scope = gate.authority_scope
        self._http_exchange = http_exchange
        self._wss_session_factory = wss_session_factory

    def execute_http(
        self,
        request: BoundRequest,
        *,
        max_response_bytes: int,
    ) -> TransportResponse:
        if request.transport != "HTTP":
            raise TransportContractError("http_request_expected")
        return self._http_exchange(
            request,
            max_response_bytes=max_response_bytes,
        )

    def open_wss_session(self) -> WssSession:
        return self._wss_session_factory()


class SmokeTransportRunner:
    """Execute the frozen order once and persist each safe observation."""

    def __init__(
        self,
        *,
        plan: SmokePlan,
        credentials: ProviderCredentials,
        transport: BoundedProviderTransport,
        event_sink: EventSink,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if transport.authority_scope != EXTERNAL_AUTHORITY_PHRASE:
            raise ExternalAuthorityRequiredError(
                "full_run_authority_scope_mismatch"
            )
        self.plan = plan
        self.credentials = credentials
        self.transport = transport
        self.event_sink = event_sink
        self.monotonic = monotonic
        self.sleeper = sleeper
        self.guard = SmokeRunGuard(plan, network_authorized=True)
        self.bindings: dict[str, JsonValue] = {}
        self.receipts: list[AttemptReceipt] = []
        self._last_started_by_group: dict[str, float] = {}

    def _pace(self, attempt_id: str) -> None:
        case_id = attempt_id.rsplit("#", 1)[0]
        case = self.plan.case_by_id[case_id]
        group = PROVIDER_POLICIES[case.provider].pacing_group
        previous = self._last_started_by_group.get(group)
        if previous is None:
            return
        minimum = PROVIDER_POLICIES[
            case.provider
        ].minimum_interval_seconds
        remaining = minimum - (self.monotonic() - previous)
        if remaining > 0:
            self.sleeper(remaining)

    def _authorize(self, attempt_id: str) -> None:
        self._pace(attempt_id)
        started = self.monotonic()
        case = self.guard.authorize_attempt(
            attempt_id,
            monotonic_seconds=started,
        )
        group = PROVIDER_POLICIES[case.provider].pacing_group
        self._last_started_by_group[group] = started

    def _record(
        self,
        *,
        attempt_id: str,
        request: BoundRequest,
        materialized: Mapping[str, Any],
        response: TransportResponse,
        credit_cost: int,
    ) -> AttemptReceipt:
        classified = classify_response(
            self.plan,
            request=request,
            materialized_request=materialized,
            response=response,
        )
        pending_binding: tuple[str, JsonValue] | None = None
        if (
            classified.terminal_class == "SUCCESS"
            and self.plan.case_by_id[request.case_id].output_binding is not None
        ):
            try:
                pending_binding = extract_dynamic_binding(
                    request.case_id,
                    classified.body,
                )
            except DynamicBindingError as exc:
                classified = _classified(
                    classified,
                    "SCHEMA_DRIFT",
                    str(exc),
                )
        event, receipt, _ = _attempt_evidence(
            self.plan,
            request=request,
            materialized_request=materialized,
            response=classified,
            credentials=self.credentials,
        )
        if (
            receipt.response_size_bytes
            > self.plan.max_response_bytes_per_attempt
        ):
            raise StopConditionError("response_too_large")
        if (
            self.guard.response_bytes_total + receipt.response_size_bytes
            > self.plan.max_total_response_bytes
        ):
            raise StopConditionError("total_response_bytes_exceeded")
        case = self.plan.case_by_id[request.case_id]
        group = PROVIDER_POLICIES[case.provider].pacing_group
        if (
            group == "HELIUS"
            and self.guard.helius_credits + credit_cost
            > EXPECTED_HELIUS_CREDIT_CAP
        ):
            raise StopConditionError("helius_credit_cap_exceeded")
        self.event_sink(event, receipt)
        self.guard.record_attempt(
            attempt_id,
            response_size_bytes=receipt.response_size_bytes,
            terminal_class=receipt.terminal_class,
            credit_cost=credit_cost,
            cash_cost_usd=0,
        )
        self.receipts.append(receipt)
        if receipt.terminal_class == "SUCCESS" and pending_binding is not None:
            self.bindings[pending_binding[0]] = pending_binding[1]
        if receipt.terminal_class in _IMMEDIATE_STOP_TERMINALS:
            raise StopConditionError(
                f"terminal_stop:{receipt.terminal_class}"
            )
        if (
            receipt.terminal_class != "SUCCESS"
            and case.output_binding is not None
        ):
            raise StopConditionError(
                "required_dynamic_binding_failed_after_persist"
            )
        return receipt

    def run(self, *, run_id: str) -> RunSummary:
        terminal_counts: dict[str, int] = {}
        attempt_index = 0
        while attempt_index < len(self.plan.attempt_ids):
            attempt_id = self.plan.attempt_ids[attempt_index]
            case_id = attempt_id.rsplit("#", 1)[0]
            materialized = materialize_case(
                self.plan,
                case_id,
                produced_bindings=self.bindings,
            )
            self._authorize(attempt_id)
            request = bind_request(
                self.plan,
                attempt_id=attempt_id,
                materialized_request=materialized,
                credentials=self.credentials,
                produced_bindings=self.bindings,
            )

            if request.transport == "WSS":
                second_attempt = self.plan.attempt_ids[attempt_index + 1]
                session = self.transport.open_wss_session()
                try:
                    first_response, subscription_id = session.subscribe(
                        request,
                        max_response_bytes=(
                            self.plan.max_response_bytes_per_attempt
                        ),
                        max_open_seconds=MAX_WSS_OPEN_SECONDS,
                        max_data_messages=MAX_WSS_DATA_MESSAGES,
                    )
                    first_receipt = self._record(
                        attempt_id=attempt_id,
                        request=request,
                        materialized=materialized,
                        response=first_response,
                        credit_cost=2,
                    )
                    terminal_counts[first_receipt.terminal_class] = (
                        terminal_counts.get(
                            first_receipt.terminal_class,
                            0,
                        )
                        + 1
                    )
                    if (
                        first_receipt.terminal_class != "SUCCESS"
                        or subscription_id is None
                    ):
                        raise StopConditionError(
                            "wss_subscribe_failed_after_persist"
                        )
                    self._authorize(second_attempt)
                    unsubscribe = bind_request(
                        self.plan,
                        attempt_id=second_attempt,
                        materialized_request=materialized,
                        credentials=self.credentials,
                        wss_subscription_id=subscription_id,
                        produced_bindings=self.bindings,
                    )
                    second_response = session.unsubscribe(
                        unsubscribe,
                        max_response_bytes=(
                            self.plan.max_response_bytes_per_attempt
                        ),
                    )
                    second_receipt = self._record(
                        attempt_id=second_attempt,
                        request=unsubscribe,
                        materialized=materialized,
                        response=second_response,
                        credit_cost=2,
                    )
                    terminal_counts[second_receipt.terminal_class] = (
                        terminal_counts.get(
                            second_receipt.terminal_class,
                            0,
                        )
                        + 1
                    )
                finally:
                    session.close()
                attempt_index += 2
                continue

            response = self.transport.execute_http(
                request,
                max_response_bytes=self.plan.max_response_bytes_per_attempt,
            )
            credit_cost = 1 if request.provider == "HELIUS_RPC" else 0
            receipt = self._record(
                attempt_id=attempt_id,
                request=request,
                materialized=materialized,
                response=response,
                credit_cost=credit_cost,
            )
            terminal_counts[receipt.terminal_class] = (
                terminal_counts.get(receipt.terminal_class, 0) + 1
            )
            attempt_index += 1

        return RunSummary(
            run_id=run_id,
            planned_attempts=len(self.plan.attempt_ids),
            completed_attempts=len(self.receipts),
            terminal_counts=terminal_counts,
            helius_credits=self.guard.helius_credits,
            response_bytes=self.guard.response_bytes_total,
            cash_spend_usd=self.guard.cash_spend_usd,
            output_logical_root=f"{RAW_LOGICAL_ROOT}/run={run_id}",
        )


def _safe_run_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("t07a4b-")
        or len(value) > 64
        or any(
            not (character.isascii() and (character.isalnum() or character in "-_"))
            for character in value
        )
    ):
        raise TransportContractError("run_id_invalid")
    return value


_RECEIPT_KEYS = frozenset(
    {
        "attempt_id",
        "case_id",
        "error_class",
        "provider",
        "redacted_body_sha256",
        "request_sent_at",
        "request_started_at",
        "response_complete_at",
        "response_headers_at",
        "response_size_bytes",
        "response_status",
        "safe_request",
        "safe_response_headers",
        "status_code",
        "terminal_class",
        "transport_contract_version",
    }
)
_SAFE_REQUEST_KEYS = frozenset(
    {
        "attempt_id",
        "body_sha256",
        "case_id",
        "host",
        "method",
        "path",
        "provider",
        "query_keys",
        "transport",
    }
)
_RAPTOR_REPAIR_ORIGINAL_CLASSIFICATIONS = {
    "R01#1": ("MALFORMED_PAYLOAD", "response_not_json"),
    "R02#1": ("SCHEMA_DRIFT", "quote_output_amount_invalid"),
    "R03#1": ("SCHEMA_DRIFT", "quote_output_amount_invalid"),
}
_RAPTOR_REPAIR_RECLASSIFY_ATTEMPTS = tuple(
    _RAPTOR_REPAIR_ORIGINAL_CLASSIFICATIONS
)
_RAPTOR_TAIL_ATTEMPTS = ("R04#1", "R05#1")


def _read_immutable_file(path: Path, error_code: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RecoveryEvidenceError(error_code)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise RecoveryEvidenceError(error_code) from exc


def _aware_datetime(value: object, error_code: str) -> datetime:
    if not isinstance(value, str):
        raise RecoveryEvidenceError(error_code)
    try:
        observed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RecoveryEvidenceError(error_code) from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise RecoveryEvidenceError(error_code)
    return observed


def _load_parent_receipt(path: Path, attempt_id: str) -> AttemptReceipt:
    data = _read_immutable_file(path, "parent_receipt_missing_or_unsafe")
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryEvidenceError("parent_receipt_not_json") from exc
    if not isinstance(value, dict) or set(value) != _RECEIPT_KEYS:
        raise RecoveryEvidenceError("parent_receipt_shape_invalid")
    if value.get("transport_contract_version") != TRANSPORT_CONTRACT_VERSION:
        raise RecoveryEvidenceError("parent_transport_version_mismatch")
    safe_request = value.get("safe_request")
    if (
        not isinstance(safe_request, dict)
        or set(safe_request) != _SAFE_REQUEST_KEYS
    ):
        raise RecoveryEvidenceError("parent_safe_request_shape_invalid")
    safe_response_headers = value.get("safe_response_headers")
    if not isinstance(safe_response_headers, list) or any(
        not isinstance(item, list)
        or len(item) != 2
        or not all(isinstance(part, str) for part in item)
        for item in safe_response_headers
    ):
        raise RecoveryEvidenceError("parent_safe_headers_invalid")
    try:
        receipt = AttemptReceipt(
            attempt_id=value["attempt_id"],
            case_id=value["case_id"],
            provider=value["provider"],
            terminal_class=value["terminal_class"],
            response_status=value["response_status"],
            error_class=value["error_class"],
            status_code=value["status_code"],
            response_size_bytes=value["response_size_bytes"],
            redacted_body_sha256=value["redacted_body_sha256"],
            request_started_at=value["request_started_at"],
            request_sent_at=value["request_sent_at"],
            response_headers_at=value["response_headers_at"],
            response_complete_at=value["response_complete_at"],
            safe_request=safe_request,
            safe_response_headers=tuple(
                (item[0], item[1]) for item in safe_response_headers
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RecoveryEvidenceError("parent_receipt_value_invalid") from exc
    if receipt.attempt_id != attempt_id:
        raise RecoveryEvidenceError("parent_receipt_attempt_mismatch")
    if data != receipt.canonical_bytes() + b"\n":
        raise RecoveryEvidenceError("parent_receipt_not_canonical")
    return receipt


def _validate_safe_parent_request(
    plan: SmokePlan,
    *,
    receipt: AttemptReceipt,
    materialized_request: Mapping[str, Any],
) -> None:
    case = plan.case_by_id[receipt.case_id]
    safe_request = receipt.safe_request
    expected_scheme, expected_host = _EXACT_HOSTS[case.provider]
    del expected_scheme
    expected_transport = (
        "WSS" if case.provider == "HELIUS_WSS" else "HTTP"
    )
    expected_method = (
        "POST"
        if case.provider in {"HELIUS_RPC", "HELIUS_WSS"}
        else "GET"
    )
    materialized_path = materialized_request.get("path")
    query = materialized_request.get("query", {})
    expected_query_keys = (
        sorted(query)
        if isinstance(query, dict)
        else []
    )
    expected = {
        "attempt_id": receipt.attempt_id,
        "case_id": receipt.case_id,
        "host": expected_host,
        "method": expected_method,
        "path": materialized_path,
        "provider": case.provider,
        "query_keys": expected_query_keys,
        "transport": expected_transport,
    }
    for key, expected_value in expected.items():
        observed = safe_request.get(key)
        if key == "query_keys" and isinstance(observed, list):
            observed = sorted(observed)
        if observed != expected_value:
            raise RecoveryEvidenceError(
                f"parent_safe_request_{key}_mismatch"
            )
    body_sha256 = safe_request.get("body_sha256")
    if (
        not isinstance(body_sha256, str)
        or len(body_sha256) != 64
        or any(character not in "0123456789abcdef" for character in body_sha256)
    ):
        raise RecoveryEvidenceError("parent_request_body_hash_invalid")


def _bound_request_from_parent_receipt(
    receipt: AttemptReceipt,
) -> BoundRequest:
    safe_request = receipt.safe_request
    host = safe_request["host"]
    path = safe_request["path"]
    transport = safe_request["transport"]
    scheme = "wss" if transport == "WSS" else "https"
    query_keys = safe_request["query_keys"]
    assert isinstance(host, str)
    assert isinstance(path, str)
    assert isinstance(query_keys, list)
    return BoundRequest(
        attempt_id=receipt.attempt_id,
        case_id=receipt.case_id,
        provider=receipt.provider,
        transport=transport,
        method=safe_request["method"],
        url=f"{scheme}://{host}{path}",
        headers=(),
        body=b"",
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        safe_query_keys=tuple(query_keys),
    )


def _response_from_parent_evidence(
    receipt: AttemptReceipt,
    body: bytes,
) -> TransportResponse:
    if (
        receipt.status_code is None
        or not 200 <= receipt.status_code < 400
        or not body
    ):
        raise RecoveryEvidenceError(
            "repair_source_not_successful_http_response"
        )
    return TransportResponse(
        status_code=receipt.status_code,
        body=body,
        safe_headers=receipt.safe_response_headers,
        terminal_class="SUCCESS",
        error_class=None,
        request_started_at=_aware_datetime(
            receipt.request_started_at,
            "parent_request_started_at_invalid",
        ),
        request_sent_at=_aware_datetime(
            receipt.request_sent_at,
            "parent_request_sent_at_invalid",
        ),
        response_headers_at=(
            _aware_datetime(
                receipt.response_headers_at,
                "parent_response_headers_at_invalid",
            )
            if receipt.response_headers_at is not None
            else None
        ),
        response_complete_at=_aware_datetime(
            receipt.response_complete_at,
            "parent_response_complete_at_invalid",
        ),
    )


def prepare_raptor_tail_recovery(
    plan: SmokePlan,
    *,
    raw_root: Path,
    parent_run_id: str,
) -> RaptorTailRecovery:
    """Verify an immutable 33-attempt prefix without writes or network I/O."""

    if not isinstance(raw_root, Path) or not raw_root.is_absolute():
        raise RecoveryEvidenceError("raw_root_must_be_absolute_path")
    safe_parent_run_id = _safe_run_id(parent_run_id)
    if tuple(plan.attempt_ids[-2:]) != _RAPTOR_TAIL_ATTEMPTS:
        raise RecoveryEvidenceError("frozen_tail_attempts_mismatch")
    expected_prefix = tuple(plan.attempt_ids[:-2])
    if len(expected_prefix) != 33:
        raise RecoveryEvidenceError("frozen_parent_prefix_length_mismatch")

    run_directory = (
        raw_root
        / RAW_LOGICAL_ROOT
        / f"run={safe_parent_run_id}"
    )
    if run_directory.is_symlink() or not run_directory.is_dir():
        raise RecoveryEvidenceError("parent_run_missing_or_unsafe")
    partition_directory = run_directory / "partitions"
    receipt_directory = run_directory / "receipts"
    if (
        partition_directory.is_symlink()
        or not partition_directory.is_dir()
        or receipt_directory.is_symlink()
        or not receipt_directory.is_dir()
    ):
        raise RecoveryEvidenceError("parent_run_layout_invalid")
    if {item.name for item in run_directory.iterdir()} != {
        "partitions",
        "receipts",
    }:
        raise RecoveryEvidenceError("parent_run_inventory_invalid")

    safe_attempts = {
        attempt_id: attempt_id.replace("#", "_")
        for attempt_id in expected_prefix
    }
    expected_partitions = {
        f"attempt={safe_attempt}.parquet"
        for safe_attempt in safe_attempts.values()
    }
    expected_receipts = {
        f"{safe_attempt}.manifest.json"
        for safe_attempt in safe_attempts.values()
    } | {
        f"{safe_attempt}.receipt.json"
        for safe_attempt in safe_attempts.values()
    }
    if {item.name for item in partition_directory.iterdir()} != (
        expected_partitions
    ):
        raise RecoveryEvidenceError("parent_partition_inventory_mismatch")
    if {item.name for item in receipt_directory.iterdir()} != (
        expected_receipts
    ):
        raise RecoveryEvidenceError("parent_receipt_inventory_mismatch")

    bindings: dict[str, JsonValue] = {}
    reclassified_attempts: list[tuple[str, str]] = []
    dataset_manifest_id = compute_dataset_manifest_id(
        DATASET_ID,
        DATASET_VERSION,
    )
    for attempt_id in expected_prefix:
        case_id = attempt_id.rsplit("#", 1)[0]
        case = plan.case_by_id[case_id]
        safe_attempt = safe_attempts[attempt_id]
        manifest_path = (
            receipt_directory / f"{safe_attempt}.manifest.json"
        )
        manifest_data = _read_immutable_file(
            manifest_path,
            "parent_manifest_missing_or_unsafe",
        )
        try:
            manifest = PartitionManifest.model_validate_json(manifest_data)
        except Exception as exc:
            raise RecoveryEvidenceError("parent_manifest_invalid") from exc
        if manifest_data != canonical_manifest_bytes(manifest) + b"\n":
            raise RecoveryEvidenceError("parent_manifest_not_canonical")
        if manifest.logical_location != (
            f"partitions/attempt={safe_attempt}.parquet"
        ):
            raise RecoveryEvidenceError(
                "parent_manifest_location_mismatch"
            )
        if manifest.partition_id != (
            f"{safe_parent_run_id}-{safe_attempt}"
        ):
            raise RecoveryEvidenceError("parent_partition_id_mismatch")
        if manifest.dataset_manifest_id != dataset_manifest_id:
            raise RecoveryEvidenceError(
                "parent_dataset_manifest_id_mismatch"
            )
        try:
            events = verify_raw_event_partition(
                root=run_directory,
                manifest=manifest,
            )
        except Exception as exc:
            raise RecoveryEvidenceError(
                "parent_partition_verification_failed"
            ) from exc
        if len(events) != 1:
            raise RecoveryEvidenceError("parent_partition_row_count_invalid")
        event = events[0]
        receipt = _load_parent_receipt(
            receipt_directory / f"{safe_attempt}.receipt.json",
            attempt_id,
        )
        if receipt.case_id != case_id or receipt.provider != case.provider:
            raise RecoveryEvidenceError("parent_receipt_identity_mismatch")
        if (
            event.source != case.provider
            or event.content_sha256 != receipt.redacted_body_sha256
            or len(event.redacted_body) != receipt.response_size_bytes
            or str(event.response_status) != receipt.response_status
            or event.error_class != receipt.error_class
        ):
            raise RecoveryEvidenceError("parent_event_receipt_mismatch")

        materialized = materialize_case(
            plan,
            case_id,
            produced_bindings=bindings,
        )
        _validate_safe_parent_request(
            plan,
            receipt=receipt,
            materialized_request=materialized,
        )
        if (
            receipt.terminal_class == "SUCCESS"
            and case.output_binding is not None
        ):
            binding = extract_dynamic_binding(
                case_id,
                event.redacted_body,
            )
            if binding is None or binding[0] != case.output_binding:
                raise RecoveryEvidenceError(
                    "parent_dynamic_binding_mismatch"
                )
            bindings[binding[0]] = binding[1]

        if attempt_id in _RAPTOR_REPAIR_RECLASSIFY_ATTEMPTS:
            expected_original = (
                _RAPTOR_REPAIR_ORIGINAL_CLASSIFICATIONS[attempt_id]
            )
            if (
                receipt.terminal_class,
                receipt.error_class,
            ) != expected_original:
                raise RecoveryEvidenceError(
                    "parent_repair_classification_mismatch"
                )
            repaired = classify_response(
                plan,
                request=_bound_request_from_parent_receipt(receipt),
                materialized_request=materialized,
                response=_response_from_parent_evidence(
                    receipt,
                    event.redacted_body,
                ),
            )
            if repaired.terminal_class != "SUCCESS":
                raise RecoveryEvidenceError(
                    "parent_reclassification_failed"
                )
            reclassified_attempts.append(
                (attempt_id, repaired.terminal_class)
            )

    expected_bindings = {
        "RAPTOR_RECENT_SIGNATURE",
        "RECENT_PUMP_MINT",
        "RECENT_PUMP_DECIMALS",
    }
    if set(bindings) != expected_bindings:
        raise RecoveryEvidenceError("parent_binding_inventory_mismatch")
    for attempt_id in _RAPTOR_TAIL_ATTEMPTS:
        materialize_case(
            plan,
            attempt_id.rsplit("#", 1)[0],
            produced_bindings=bindings,
        )
    return RaptorTailRecovery(
        parent_run_id=safe_parent_run_id,
        parent_run_directory=run_directory,
        verified_attempts=expected_prefix,
        pending_attempts=_RAPTOR_TAIL_ATTEMPTS,
        produced_bindings=tuple(
            (name, bindings[name]) for name in sorted(bindings)
        ),
        reclassified_attempts=tuple(reclassified_attempts),
        verified_file_count=(
            len(expected_partitions) + len(expected_receipts)
        ),
    )


class RaptorTailRunner:
    """Execute only the offline-verified keyless R04/R05 child suffix."""

    def __init__(
        self,
        *,
        plan: SmokePlan,
        recovery: RaptorTailRecovery,
        transport: BoundedProviderTransport,
        event_sink: EventSink,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if transport.authority_scope != RAPTOR_TAIL_AUTHORITY_PHRASE:
            raise ExternalAuthorityRequiredError(
                "raptor_tail_authority_scope_mismatch"
            )
        if recovery.pending_attempts != _RAPTOR_TAIL_ATTEMPTS:
            raise RecoveryEvidenceError("recovery_tail_attempts_mismatch")
        if recovery.verified_attempts != tuple(plan.attempt_ids[:-2]):
            raise RecoveryEvidenceError("recovery_prefix_attempts_mismatch")
        self.plan = plan
        self.recovery = recovery
        self.transport = transport
        self.event_sink = event_sink
        self.monotonic = monotonic
        self.sleeper = sleeper

    def run(self, *, child_run_id: str) -> RaptorTailSummary:
        safe_child_run_id = _safe_run_id(child_run_id)
        if safe_child_run_id == self.recovery.parent_run_id:
            raise TransportContractError("child_run_must_differ_from_parent")
        terminal_counts: dict[str, int] = {}
        response_bytes = 0
        completed_attempts = 0
        previous_started: float | None = None
        bindings = self.recovery.bindings
        for attempt_id in _RAPTOR_TAIL_ATTEMPTS:
            if previous_started is not None:
                minimum = PROVIDER_POLICIES[
                    "RAPTOR_HOSTED"
                ].minimum_interval_seconds
                remaining = minimum - (
                    self.monotonic() - previous_started
                )
                if remaining > 0:
                    self.sleeper(remaining)
            previous_started = self.monotonic()
            case_id = attempt_id.rsplit("#", 1)[0]
            materialized = materialize_case(
                self.plan,
                case_id,
                produced_bindings=bindings,
            )
            request = bind_request(
                self.plan,
                attempt_id=attempt_id,
                materialized_request=materialized,
                credentials=None,
                produced_bindings=bindings,
            )
            if (
                request.provider != "RAPTOR_HOSTED"
                or request.transport != "HTTP"
                or request.method != "GET"
            ):
                raise TransportContractError(
                    "raptor_tail_request_scope_mismatch"
                )
            response = self.transport.execute_http(
                request,
                max_response_bytes=(
                    self.plan.max_response_bytes_per_attempt
                ),
            )
            classified = classify_response(
                self.plan,
                request=request,
                materialized_request=materialized,
                response=response,
            )
            event, receipt, _ = _attempt_evidence(
                self.plan,
                request=request,
                materialized_request=materialized,
                response=classified,
                credentials=None,
            )
            if (
                response_bytes + receipt.response_size_bytes
                > self.plan.max_total_response_bytes
            ):
                raise StopConditionError(
                    "total_response_bytes_exceeded"
                )
            self.event_sink(event, receipt)
            response_bytes += receipt.response_size_bytes
            completed_attempts += 1
            terminal_counts[receipt.terminal_class] = (
                terminal_counts.get(receipt.terminal_class, 0) + 1
            )
            if receipt.terminal_class in _IMMEDIATE_STOP_TERMINALS:
                raise StopConditionError(
                    f"terminal_stop:{receipt.terminal_class}"
                )
        return RaptorTailSummary(
            parent_run_id=self.recovery.parent_run_id,
            child_run_id=safe_child_run_id,
            planned_attempts=len(_RAPTOR_TAIL_ATTEMPTS),
            completed_attempts=completed_attempts,
            terminal_counts=terminal_counts,
            response_bytes=response_bytes,
            cash_spend_usd=0.0,
            output_logical_root=(
                f"{RAW_LOGICAL_ROOT}/run={safe_child_run_id}"
            ),
        )


class DurableAttemptSink:
    """Write one immutable Parquet partition and safe receipt per attempt."""

    def __init__(self, *, raw_root: Path, run_id: str) -> None:
        if not isinstance(raw_root, Path) or not raw_root.is_absolute():
            raise TransportContractError("raw_root_must_be_absolute_path")
        self.raw_root = raw_root
        self.run_id = _safe_run_id(run_id)
        self.run_directory = (
            raw_root / RAW_LOGICAL_ROOT / f"run={self.run_id}"
        )
        if self.run_directory.exists():
            raise TransportContractError("run_output_already_exists")
        self.run_directory.mkdir(parents=True, exist_ok=False)
        self.partition_directory = self.run_directory / "partitions"
        self.partition_directory.mkdir()
        self.receipt_directory = self.run_directory / "receipts"
        self.receipt_directory.mkdir()
        self.policy = StorageBudgetPolicy(
            max_partition_bytes=3_000_000,
            max_dataset_bytes=32_000_000,
            min_free_bytes=1_073_741_824,
            warning_threshold_bps=8000,
            forecast_partition_count=35,
        )

    def __call__(self, event: RawApiEvent, receipt: AttemptReceipt) -> None:
        safe_attempt = receipt.attempt_id.replace("#", "_")
        logical_location = f"partitions/attempt={safe_attempt}.parquet"
        partition_reliable_at = max(
            event.first_reliable_available_at,
            event.ingested_at,
        )
        result = write_budgeted_raw_event_partition(
            root=self.run_directory,
            dataset_id=DATASET_ID,
            dataset_version=DATASET_VERSION,
            partition_id=f"{self.run_id}-{safe_attempt}",
            logical_location=logical_location,
            events=[event],
            created_at=event.ingested_at,
            first_reliable_available_at=partition_reliable_at,
            budget_policy=self.policy,
        )
        manifest_path = self.receipt_directory / f"{safe_attempt}.manifest.json"
        receipt_path = self.receipt_directory / f"{safe_attempt}.receipt.json"
        with manifest_path.open("xb") as handle:
            handle.write(canonical_manifest_bytes(result.manifest))
            handle.write(b"\n")
        with receipt_path.open("xb") as handle:
            handle.write(receipt.canonical_bytes())
            handle.write(b"\n")


def default_run_id(now: datetime | None = None) -> str:
    instant = now or _utc_now()
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise TransportContractError("run_time_not_aware")
    return instant.astimezone(timezone.utc).strftime("t07a4b-%Y%m%dT%H%M%SZ")


def safe_preflight_summary(plan: SmokePlan) -> dict[str, JsonValue]:
    """Return a zero-I/O, zero-secret plan summary."""

    return {
        "attempt_count": len(plan.attempt_ids),
        "case_count": len(plan.cases),
        "cash_cap_usd": 0,
        "credentials_read": False,
        "network_authorized": False,
        "output_created": False,
        "providers": sorted(PROVIDER_POLICIES),
        "transport_contract_version": TRANSPORT_CONTRACT_VERSION,
    }
