"""Credential-safe transport primitives for one quote-native qualification."""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

import yaml

from solana_alpha_lab.pmf_quote_slice_one_shot import credential_free_preflight
from solana_alpha_lab.provider_route_capability_registry_v9 import (
    FREE_KEY_ROUTE_IDS,
    resolve_provider_route_v9,
)
from solana_alpha_lab.quote_native_evidence_fit_panel import PanelError, project_quote
from solana_alpha_lab.quote_native_live_variation_campaign import (
    H3600,
    H900,
    RECENT_ENDPOINT,
    TRADED_ENDPOINT,
    build_schedule,
    score_campaign,
    select_cohort,
)


API_HOST = "api.jup.ag"
ALLOWED_PATHS = frozenset(
    {
        "/tokens/v2/recent",
        "/tokens/v2/toptraded/1h",
        "/swap/v2/order",
    }
)
SAFE_RESPONSE_HEADERS = frozenset(
    {
        "retry-after",
        "x-api-gateway-request-id",
    }
)
USER_AGENT = "solana-alpha-lab/quote-native-evidence-qualification-v1"
ATOM_ID = "QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1"
AUTHORITY_PHRASE = (
    "OK QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1: one fresh Jupiter "
    "Free-key quote-native evidence campaign using a local process-environment "
    "key only; Tokens V2 /recent and /toptraded/1h plus quote-only "
    "/swap/v2/order; x-api-key header only; no .env read, no key in "
    "URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, "
    "transaction, paid plan, second provider, retry or fallback; cash cap $0; "
    "call cap 60; global provider pace >=3s; preserve the existing 6 RECENT + "
    "6 TRADED cohort and success/control-kill thresholds; any 429 or "
    "insufficient Free-key sample closes or pauses the current quote-native "
    "alpha route."
)
CALL_CAP = 60
MIN_INTERVAL_SECONDS = 3
H14400 = 14400
LATE_SLACK_SECONDS = 120
V6_REGISTRY_PATH = "configs/provider_route_capability_registry_v6.yaml"
V7_REGISTRY_PATH = "configs/provider_route_capability_registry_v7.yaml"
V8_REGISTRY_PATH = "configs/provider_route_capability_registry_v8.yaml"
V9_REGISTRY_PATH = "configs/provider_route_capability_registry_v9.yaml"


class QualificationError(ValueError):
    """Raised when the bounded qualification contract is violated."""

    def __init__(self, code: str, *, provider_requests: int | None = None) -> None:
        super().__init__(code)
        self.provider_requests = provider_requests


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        *_args: object,
        **_kwargs: object,
    ) -> urllib.request.Request | None:
        return None


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QualificationError(code)


def load_process_credential(environ: Mapping[str, str]) -> str:
    value = environ.get("JUPITER_API_KEY", "").strip()
    _require(bool(value), "JUPITER_API_KEY_MISSING_OR_EMPTY")
    return value


def _safe_response_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(name).casefold(): str(value)
        for name, value in headers.items()
        if str(name).casefold() in SAFE_RESPONSE_HEADERS
    }


def _validate_request_url(url: str) -> None:
    parsed = urlsplit(url)
    _require(parsed.scheme == "https", "ENDPOINT_SCHEME_DRIFT")
    _require(parsed.hostname == API_HOST, "ENDPOINT_HOST_DRIFT")
    _require(parsed.port is None, "ENDPOINT_PORT_DRIFT")
    _require(parsed.username is None and parsed.password is None, "ENDPOINT_USERINFO_FORBIDDEN")
    _require(parsed.path in ALLOWED_PATHS, "ENDPOINT_PATH_DRIFT")
    _require(not parsed.fragment, "QUERY_ALLOWLIST_DRIFT")
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query_keys = [name for name, _ in query_pairs]
    if parsed.path == "/swap/v2/order":
        _require(
            set(query_keys) == {"inputMint", "outputMint", "amount", "slippageBps"}
            and len(query_keys) == 4
            and all(bool(value) for _, value in query_pairs),
            "QUERY_ALLOWLIST_DRIFT",
        )
        return
    _require(not query_pairs, "QUERY_ALLOWLIST_DRIFT")


def perform_credentialed_get(
    url: str,
    *,
    api_key: str,
    limits: Mapping[str, Any],
    opener: object | None = None,
) -> dict[str, object]:
    _require(type(api_key) is str and bool(api_key.strip()), "API_KEY_INVALID")
    _validate_request_url(url)
    max_bytes = int(limits["max_response_bytes"])
    timeout_seconds = float(limits["timeout_seconds"])
    outgoing = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "x-api-key": api_key,
        },
    )
    selected = opener or urllib.request.build_opener(_NoRedirectHandler())
    try:
        with selected.open(outgoing, timeout=timeout_seconds) as response:  # type: ignore[union-attr]
            status = int(response.getcode())
            headers = response.headers
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        headers = exc.headers or {}
        body = exc.read(max_bytes + 1)
    except (
        urllib.error.URLError,
        ssl.SSLError,
        socket.gaierror,
        socket.timeout,
        TimeoutError,
        OSError,
    ) as exc:
        return {
            "http_status": None,
            "response_bytes": None,
            "response_sha256": None,
            "safe_response_headers": {},
            "url_has_api_key": False,
            "transport_error": type(exc).__name__,
            "body": None,
        }
    _require(len(body) <= max_bytes, "RESPONSE_BYTES_EXCEEDED")
    return {
        "http_status": status,
        "response_bytes": len(body),
        "response_sha256": hashlib.sha256(body).hexdigest(),
        "safe_response_headers": _safe_response_headers(headers),
        "url_has_api_key": _url_contains_credential(url, api_key),
        "body": body,
    }


def _format_utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _policy_mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _validate_policy_shape(policy: Mapping[str, Any]) -> None:
    authority = _policy_mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    controls = _policy_mapping(policy.get("execution_controls"), "CONTROLS_INVALID")
    quote_route = _policy_mapping(policy.get("quote_route"), "QUOTE_ROUTE_INVALID")
    discovery = _policy_mapping(policy.get("discovery_routes"), "DISCOVERY_INVALID")
    recent = _policy_mapping(discovery.get("recent"), "DISCOVERY_RECENT_INVALID")
    traded = _policy_mapping(discovery.get("traded"), "DISCOVERY_TRADED_INVALID")
    success = _policy_mapping(policy.get("success"), "SUCCESS_INVALID")
    control_kill = _policy_mapping(policy.get("control_kill"), "CONTROL_KILL_INVALID")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    _require(
        authority.get("owner_phrase") == AUTHORITY_PHRASE,
        "AUTHORITY_PHRASE_DRIFT",
    )
    _require(authority.get("credential_name") == "JUPITER_API_KEY", "CREDENTIAL_NAME_DRIFT")
    _require(authority.get("credential_reads") == 1, "CREDENTIAL_READ_BUDGET_DRIFT")
    _require(authority.get("dotenv_reads") is False, "DOTENV_READ_NOT_FORBIDDEN")
    _require(authority.get("execute") is False, "EXECUTE_NOT_FORBIDDEN")
    _require(authority.get("build") is False, "BUILD_NOT_FORBIDDEN")
    _require(authority.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(authority.get("cash_cap_usd_cents") == 0, "CASH_CAP_DRIFT")
    _require(authority.get("call_cap") == CALL_CAP, "CALL_CAP_DRIFT")
    _require(quote_route.get("endpoint") == "https://api.jup.ag/swap/v2/order", "QUOTE_ENDPOINT_DRIFT")
    _require(quote_route.get("host") == API_HOST, "QUOTE_HOST_DRIFT")
    _require(quote_route.get("method") == "GET", "QUOTE_METHOD_DRIFT")
    _require(recent.get("endpoint") == RECENT_ENDPOINT, "RECENT_ENDPOINT_DRIFT")
    _require(traded.get("endpoint") == TRADED_ENDPOINT, "TRADED_ENDPOINT_DRIFT")
    _require(policy.get("recent_cell_count") == 6, "RECENT_COUNT_DRIFT")
    _require(policy.get("traded_cell_count") == 6, "TRADED_COUNT_DRIFT")
    _require(policy.get("liquidity_floor_usd") == 1000, "LIQUIDITY_FLOOR_DRIFT")
    _require(policy.get("notional_atomic") == "10000000", "NOTIONAL_DRIFT")
    _require(policy.get("slippage_bps") == "100", "SLIPPAGE_DRIFT")
    _require(policy.get("min_interval_seconds") == MIN_INTERVAL_SECONDS, "PACE_DRIFT")
    _require(policy.get("observable_horizon_seconds") == [H900, H3600], "HORIZON_DRIFT")
    _require(policy.get("gap_horizon_seconds") == [H14400], "GAP_HORIZON_DRIFT")
    _require(policy.get("lateness_slack_seconds") == LATE_SLACK_SECONDS, "SLACK_DRIFT")
    _require(success.get("min_complete_xy") == 10, "SUCCESS_COMPLETE_DRIFT")
    _require(success.get("min_time_separated") == 6, "SUCCESS_SEPARATED_DRIFT")
    _require(control_kill.get("min_complete_cells") == 6, "KILL_COMPLETE_DRIFT")
    _require(control_kill.get("min_time_separated_share") == "0.5", "KILL_SHARE_DRIFT")
    _require(controls.get("retries") == 0, "RETRY_NOT_FORBIDDEN")
    _require(controls.get("fallback") is False, "FALLBACK_NOT_FORBIDDEN")
    _require(
        controls.get("persist_transaction_bytes") is False,
        "TX_PERSIST_NOT_FORBIDDEN",
    )
    _require(controls.get("provider_requests_max") == CALL_CAP, "REQUEST_BUDGET_DRIFT")
    _require(controls.get("background_scheduler") is False, "SCHEDULER_NOT_FORBIDDEN")
    _require(controls.get("second_provider") is False, "SECOND_PROVIDER_NOT_FORBIDDEN")
    _require(controls.get("paid_plan") is False, "PAID_PLAN_NOT_FORBIDDEN")


def validate_policy(policy: Mapping[str, Any], *, root: Path) -> None:
    _validate_policy_shape(policy)
    _require(policy.get("registry") == V9_REGISTRY_PATH, "REGISTRY_BIND_DRIFT")
    quote_route = _policy_mapping(policy.get("quote_route"), "QUOTE_ROUTE_INVALID")
    discovery = _policy_mapping(policy.get("discovery_routes"), "DISCOVERY_INVALID")
    recent = _policy_mapping(discovery.get("recent"), "DISCOVERY_RECENT_INVALID")
    traded = _policy_mapping(discovery.get("traded"), "DISCOVERY_TRADED_INVALID")
    _require(
        tuple(
            (
                str(recent.get("route_id")),
                str(traded.get("route_id")),
                str(quote_route.get("route_id")),
            )
        )
        == FREE_KEY_ROUTE_IDS,
        "FREE_KEY_ROUTE_BIND_DRIFT",
    )

    def load_yaml(relative: str) -> Mapping[str, Any]:
        loaded = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        _require(isinstance(loaded, Mapping), "REGISTRY_DOCUMENT_INVALID")
        return loaded

    v6_path = root / V6_REGISTRY_PATH
    v7_path = root / V7_REGISTRY_PATH
    v8_path = root / V8_REGISTRY_PATH
    v9_path = root / V9_REGISTRY_PATH
    v6 = load_yaml(V6_REGISTRY_PATH)
    v7 = load_yaml(V7_REGISTRY_PATH)
    v8 = load_yaml(V8_REGISTRY_PATH)
    v9 = load_yaml(V9_REGISTRY_PATH)
    v6_sha = hashlib.sha256(v6_path.read_bytes()).hexdigest()
    v7_sha = hashlib.sha256(v7_path.read_bytes()).hexdigest()
    v8_sha = hashlib.sha256(v8_path.read_bytes()).hexdigest()
    for route_id in FREE_KEY_ROUTE_IDS:
        resolve_provider_route_v9(
            v9,
            route_id,
            predecessor=v8,
            predecessor_sha256=v8_sha,
            v7_registry=v7,
            v7_sha256=v7_sha,
            v6_registry=v6,
            v6_sha256=v6_sha,
        )


def _transport_view(result: Mapping[str, object]) -> dict[str, object]:
    return {
        "http_status": result.get("http_status"),
        "response_bytes": result.get("response_bytes"),
        "response_sha256": result.get("response_sha256"),
        "safe_response_headers": result.get("safe_response_headers"),
        "request_count": 1,
        "url_has_api_key": bool(result.get("url_has_api_key")),
        "url_has_taker": False,
    }


def _halted(row: Mapping[str, object]) -> dict[str, object]:
    recorded = dict(row)
    recorded["consumed_call"] = False
    if recorded.get("wave") == "gap":
        recorded["terminal"] = "EXPLICIT_GAP"
    elif recorded.get("wave") == "horizon":
        recorded["terminal"] = "SCHEDULED"
    else:
        recorded["terminal"] = "NOT_REACHED"
    return recorded


def _cancel_pending_horizons(
    *,
    schedule: list[dict[str, object]],
    results: dict[str, dict[str, object]],
) -> None:
    for row in schedule:
        observation_id = str(row["observation_id"])
        if (
            row["wave"] == "horizon"
            and results[observation_id].get("terminal") == "SCHEDULED"
        ):
            results[observation_id] = {
                **row,
                "terminal": "CANCELLED_AFTER_TERMINAL",
                "consumed_call": False,
            }


def _classify_quote(
    result: Mapping[str, object],
) -> tuple[str, str | None, dict[str, object] | None]:
    if result.get("http_status") is None:
        return (
            "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
            str(result.get("transport_error") or "TRANSPORT_ERROR"),
            None,
        )
    status = int(result["http_status"])
    if status in {401, 403}:
        return "CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED", f"HTTP_{status}", None
    if status == 429:
        return "RATE_LIMITED", "HTTP_429", None
    if status != 200:
        return "PROVIDER_TYPED_FAILURE", f"HTTP_{status}", None
    try:
        quote = project_quote(result["body"])  # type: ignore[arg-type]
    except PanelError as exc:
        return "PROVIDER_TYPED_FAILURE", str(exc), None
    return str(quote["surface"]), None, quote


def _url_contains_credential(url: str, api_key: str) -> bool:
    if not api_key:
        return False
    parsed = urlsplit(url)
    if parsed.username == api_key or parsed.password == api_key:
        return True
    if api_key in url:
        return True
    return False


def _payload_contains_transaction(payload: object) -> bool:
    if isinstance(payload, Mapping):
        if payload.get("transaction") not in {None, ""}:
            return True
        return any(_payload_contains_transaction(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_payload_contains_transaction(item) for item in payload)
    return False


def _body_contains_transaction(body: object) -> bool:
    if not isinstance(body, bytes):
        return False
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return _payload_contains_transaction(payload)


def _body_contains_secret(body: object, secret: str) -> bool:
    if not isinstance(body, bytes) or not secret:
        return False
    return secret.encode("utf-8") in body


def _classify_discovery(
    result: Mapping[str, object],
) -> tuple[str, str | None, list[Mapping[str, Any]] | None]:
    if result.get("http_status") is None:
        return (
            "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
            str(result.get("transport_error") or "TRANSPORT_ERROR"),
            None,
        )
    status = int(result["http_status"])
    if status in {401, 403}:
        return "CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED", f"HTTP_{status}", None
    if status == 429:
        return "RATE_LIMITED", "HTTP_429", None
    if status != 200:
        return "PROVIDER_TYPED_FAILURE", f"HTTP_{status}", None
    try:
        payload = json.loads(bytes(result["body"]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return "TOKEN_LIST_SHAPE_INVALID", "JSON", None
    if not isinstance(payload, list):
        return "TOKEN_LIST_SHAPE_INVALID", "NOT_LIST", None
    return (
        "TOKEN_LIST_OBSERVED",
        None,
        [item for item in payload if isinstance(item, Mapping)],
    )


def _order_url(
    *,
    input_mint: str,
    output_mint: str,
    amount: str,
    slippage_bps: str,
) -> str:
    query = urlencode(
        [
            ("inputMint", input_mint),
            ("outputMint", output_mint),
            ("amount", amount),
            ("slippageBps", slippage_bps),
        ]
    )
    return f"https://api.jup.ag/swap/v2/order?{query}"


def run_campaign(
    policy: Mapping[str, Any],
    *,
    credential_loader: Callable[[], str],
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    opener: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] | None = None,
    monotonic_clock: Callable[[], float] | None = None,
    raw_sink: Callable[[str, bytes, str], None] | None = None,
) -> dict[str, object]:
    _validate_policy_shape(policy)
    limits = _policy_mapping(policy.get("runtime_limits"), "LIMITS_INVALID")
    quote_route = _policy_mapping(policy.get("quote_route"), "QUOTE_ROUTE_INVALID")
    discovery = _policy_mapping(policy.get("discovery_routes"), "DISCOVERY_INVALID")
    waiter = time.sleep if sleeper is None else sleeper
    monotonic = time.monotonic if monotonic_clock is None else monotonic_clock
    started_at = clock()
    preflight = dict(
        preflight_fn(
            {"provider_route": {"endpoint": quote_route["endpoint"]}},
            observed_at=_format_utc(started_at),
        )
    )
    _require(preflight.get("credential_reads") == 0, "PREFLIGHT_CREDENTIAL_READ_DRIFT")
    credential = credential_loader()
    _require(bool(credential.strip()), "JUPITER_API_KEY_MISSING_OR_EMPTY")
    credential_reads = 1
    provider_requests = 0
    last_call_monotonic: float | None = None

    def call(url: str, observation_id: str) -> dict[str, object]:
        nonlocal provider_requests, last_call_monotonic
        if last_call_monotonic is not None:
            elapsed = monotonic() - last_call_monotonic
            if elapsed < MIN_INTERVAL_SECONDS:
                waiter(MIN_INTERVAL_SECONDS - elapsed)
        if provider_requests >= CALL_CAP:
            raise QualificationError(
                "CALL_CAP_EXCEEDED",
                provider_requests=provider_requests,
            )
        provider_requests += 1
        try:
            observed = perform_credentialed_get(
                url,
                api_key=credential,
                limits=limits,
                opener=opener,
            )
        except QualificationError as exc:
            last_call_monotonic = monotonic()
            raise QualificationError(
                str(exc),
                provider_requests=provider_requests,
            ) from exc
        last_call_monotonic = monotonic()
        if observed.get("url_has_api_key") is True:
            raise QualificationError(
                "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
                provider_requests=provider_requests,
            )
        completed_at = clock()
        observed["observed_at"] = _format_utc(completed_at)
        return observed

    def retain_raw(
        observation_id: str,
        observed: Mapping[str, object],
        *,
        reject_transaction_body: bool,
    ) -> None:
        body = observed.get("body")
        if raw_sink is None or not isinstance(body, bytes):
            return
        if reject_transaction_body and _body_contains_transaction(body):
            return
        if _body_contains_secret(body, credential):
            raise QualificationError(
                "RAW_BODY_CONTAINS_CREDENTIAL",
                provider_requests=provider_requests,
            )
        observed_at = observed.get("observed_at")
        _require(isinstance(observed_at, str), "OBSERVED_AT_MISSING")
        raw_sink(observation_id, body, observed_at)

    discovery_rows: list[dict[str, object]] = []
    result = call(str(_policy_mapping(discovery["recent"], "DISCOVERY_RECENT_INVALID")["endpoint"]), "DISCOVERY:RECENT")
    retain_raw("DISCOVERY:RECENT", result, reject_transaction_body=True)
    terminal, error, recent_payload = _classify_discovery(result)
    discovery_rows.append(
        {
            "observation_id": "DISCOVERY:RECENT",
            "kind": "DISCOVERY_RECENT",
            "terminal": terminal,
            "terminal_error": error,
            "observed_at": result["observed_at"],
            "transport": _transport_view(result),
            "consumed_call": True,
        }
    )
    if terminal != "TOKEN_LIST_OBSERVED":
        return _terminal_receipt(
            terminal=terminal,
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_rows=discovery_rows,
            observations=[],
        )
    result = call(str(_policy_mapping(discovery["traded"], "DISCOVERY_TRADED_INVALID")["endpoint"]), "DISCOVERY:TRADED")
    retain_raw("DISCOVERY:TRADED", result, reject_transaction_body=True)
    terminal, error, traded_payload = _classify_discovery(result)
    discovery_rows.append(
        {
            "observation_id": "DISCOVERY:TRADED",
            "kind": "DISCOVERY_TRADED",
            "terminal": terminal,
            "terminal_error": error,
            "observed_at": result["observed_at"],
            "transport": _transport_view(result),
            "consumed_call": True,
        }
    )
    if terminal != "TOKEN_LIST_OBSERVED":
        return _terminal_receipt(
            terminal=terminal,
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_rows=discovery_rows,
            observations=[],
        )
    cohort = select_cohort(recent_payload or [], traded_payload or [])
    cells = cohort["cells"]
    if not cohort["sufficient"] or not isinstance(cells, list):
        return _terminal_receipt(
            terminal="PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_rows=discovery_rows,
            observations=[],
            frozen_cells=cells if isinstance(cells, list) else [],
        )

    panel_started_at = clock()
    panel_started_monotonic = monotonic()
    schedule = build_schedule(cells, panel_started_at=panel_started_at)
    observations = _execute_schedule(
        schedule=schedule,
        policy=policy,
        call=call,
        clock=clock,
        sleeper=waiter,
        panel_started_at=panel_started_at,
        panel_started_monotonic=panel_started_monotonic,
        monotonic_clock=monotonic,
        retain_order_raw=lambda observation_id, observed: retain_raw(
            observation_id,
            observed,
            reject_transaction_body=True,
        ),
    )
    terminal_outcome = _terminal_from_observations(observations)
    campaign = score_campaign(observations)
    if terminal_outcome == "COMPLETE":
        terminal_outcome = (
            "QUOTE_NATIVE_EVIDENCE_FIT_PASS"
            if campaign["campaign_verdict"] == "VARIATION_PRESENT_NOT_MECHANISM"
            else "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
        )
    return {
        "schema": "smial.quote-native-evidence-channel-qualification.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_outcome": terminal_outcome,
        "preflight": preflight,
        "credential_reads": credential_reads,
        "provider_requests": provider_requests,
        "retries": 0,
        "fallbacks": 0,
        "execute_calls": 0,
        "frozen_cells": cells,
        "discovery_observations": discovery_rows,
        "panel_started_at": _format_utc(panel_started_at),
        "observations": observations,
        "campaign": campaign,
        "non_claims": [
            "NO_EXECUTE",
            "NO_TAKER_OR_SIGNER",
            "NO_TRANSACTION_BYTES_IN_GIT",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_MOVE_2",
            "NO_PAID_PLAN",
            "NO_SECOND_PROVIDER",
        ],
    }


def _terminal_receipt(
    *,
    terminal: str,
    preflight: Mapping[str, Any],
    credential_reads: int,
    provider_requests: int,
    discovery_rows: list[dict[str, object]],
    observations: list[dict[str, object]],
    frozen_cells: list[object] | None = None,
) -> dict[str, object]:
    mapped_terminal = (
        "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
        if terminal in {"RATE_LIMITED", "PROVIDER_TYPED_FAILURE", "TOKEN_LIST_SHAPE_INVALID"}
        else terminal
    )
    return {
        "schema": "smial.quote-native-evidence-channel-qualification.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_outcome": mapped_terminal,
        "preflight": dict(preflight),
        "credential_reads": credential_reads,
        "provider_requests": provider_requests,
        "retries": 0,
        "fallbacks": 0,
        "execute_calls": 0,
        "frozen_cells": list(frozen_cells or []),
        "discovery_observations": discovery_rows,
        "observations": observations,
        "campaign": {
            "campaign_verdict": mapped_terminal,
            "complete_xy_count": 0,
            "time_separated_complete_xy_count": 0,
        },
        "non_claims": [
            "NO_EXECUTE",
            "NO_TAKER_OR_SIGNER",
            "NO_TRANSACTION_BYTES_IN_GIT",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_MOVE_2",
            "NO_PAID_PLAN",
            "NO_SECOND_PROVIDER",
        ],
    }


def _execute_schedule(
    *,
    schedule: list[dict[str, object]],
    policy: Mapping[str, Any],
    call: Callable[[str, str], dict[str, object]],
    clock: Callable[[], datetime],
    sleeper: Callable[[float], None],
    panel_started_at: datetime,
    panel_started_monotonic: float,
    monotonic_clock: Callable[[], float],
    retain_order_raw: Callable[[str, Mapping[str, object]], None],
) -> list[dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for row in schedule:
        recorded = dict(row)
        recorded["consumed_call"] = False
        if recorded["wave"] == "gap":
            recorded["terminal"] = "EXPLICIT_GAP"
        elif recorded["wave"] == "horizon":
            recorded["terminal"] = "SCHEDULED"
        else:
            recorded["terminal"] = "NOT_REACHED"
        results[str(row["observation_id"])] = recorded

    stopped = False
    for row in schedule:
        if row["wave"] != "t0":
            continue
        observation_id = str(row["observation_id"])
        if stopped:
            results[observation_id] = _halted(row)
            continue
        parent_id = row.get("parent_id")
        parent = results.get(str(parent_id)) if parent_id else None
        amount = str(row["amount"]) if row.get("amount") is not None else None
        if parent is not None:
            parent_quote = parent.get("quote")
            if parent.get("terminal") != "QUOTE_OBSERVED" or not isinstance(parent_quote, Mapping):
                recorded = dict(row)
                recorded["terminal"] = "SKIPPED_NO_ENTRY"
                recorded["consumed_call"] = False
                results[observation_id] = recorded
                continue
            amount = str(parent_quote["out_amount"])
        _require(amount is not None, "AMOUNT_MISSING")
        result = call(
            _order_url(
                input_mint=str(row["input_mint"]),
                output_mint=str(row["output_mint"]),
                amount=amount,
                slippage_bps=str(policy["slippage_bps"]),
            ),
            observation_id,
        )
        terminal, error, quote = _classify_quote(result)
        retain_order_raw(observation_id, result)
        results[observation_id] = {
            **row,
            "amount": amount,
            "terminal": terminal,
            "terminal_error": error,
            "observed_at": result["observed_at"],
            "transport": _transport_view(result),
            "quote": quote,
            "consumed_call": True,
        }
        if terminal in {
            "RATE_LIMITED",
            "CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED",
            "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
        }:
            stopped = True

    if stopped:
        _cancel_pending_horizons(schedule=schedule, results=results)
        return [results[str(row["observation_id"])] for row in schedule]

    for horizon in (H900, H3600):
        due_at = panel_started_at + timedelta(seconds=horizon)
        due_monotonic = panel_started_monotonic + horizon
        wait_seconds = due_monotonic - monotonic_clock()
        if wait_seconds > 0:
            sleeper(wait_seconds)
        for row in schedule:
            if row["horizon_seconds"] != horizon:
                continue
            observation_id = str(row["observation_id"])
            slack = int(row["lateness_slack_seconds"])
            if monotonic_clock() > due_monotonic + slack:
                for pending in schedule:
                    pending_id = str(pending["observation_id"])
                    if (
                        pending["wave"] == "horizon"
                        and results[pending_id].get("terminal") == "SCHEDULED"
                    ):
                        results[pending_id] = {
                            **pending,
                            "terminal": "MISSED_OFFSET",
                            "consumed_call": False,
                        }
                return [results[str(item["observation_id"])] for item in schedule]
            parent = results.get(str(row["parent_id"]))
            if parent is None or parent.get("terminal") != "QUOTE_OBSERVED":
                results[observation_id] = _halted(row)
                continue
            parent_quote = parent.get("quote")
            if not isinstance(parent_quote, Mapping):
                results[observation_id] = _halted(row)
                continue
            result = call(
                _order_url(
                    input_mint=str(row["input_mint"]),
                    output_mint=str(row["output_mint"]),
                    amount=str(parent_quote["out_amount"]),
                    slippage_bps=str(policy["slippage_bps"]),
                ),
                observation_id,
            )
            if monotonic_clock() > due_monotonic + slack:
                results[observation_id] = {
                    **row,
                    "terminal": "MISSED_OFFSET",
                    "consumed_call": True,
                    "observed_at": result.get("observed_at"),
                    "transport": _transport_view(result),
                }
                for pending in schedule:
                    pending_id = str(pending["observation_id"])
                    if (
                        pending["wave"] == "horizon"
                        and results[pending_id].get("terminal") == "SCHEDULED"
                    ):
                        results[pending_id] = {
                            **pending,
                            "terminal": "MISSED_OFFSET",
                            "consumed_call": False,
                        }
                return [results[str(item["observation_id"])] for item in schedule]
            terminal, error, quote = _classify_quote(result)
            retain_order_raw(observation_id, result)
            results[observation_id] = {
                **row,
                "amount": str(parent_quote["out_amount"]),
                "terminal": terminal,
                "terminal_error": error,
                "observed_at": result["observed_at"],
                "transport": _transport_view(result),
                "quote": quote,
                "consumed_call": True,
            }
            if terminal in {
                "RATE_LIMITED",
                "CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED",
                "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
            }:
                stopped = True
                break
        if stopped:
            break

    if stopped:
        _cancel_pending_horizons(schedule=schedule, results=results)

    for row in schedule:
        observation_id = str(row["observation_id"])
        if observation_id not in results:
            results[observation_id] = _halted(row)
    return [results[str(row["observation_id"])] for row in schedule]


def _terminal_from_observations(observations: list[Mapping[str, object]]) -> str:
    terminals = {str(row.get("terminal")) for row in observations}
    if "RATE_LIMITED" in terminals or "MISSED_OFFSET" in terminals:
        return "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
    if "CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED" in terminals:
        return "CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED"
    if "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED" in terminals:
        return "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED"
    return "COMPLETE"
