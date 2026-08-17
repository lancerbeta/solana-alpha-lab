"""One authorized Jupiter Swap V2 quote-only GET without taker."""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

from solana_alpha_lab.pmf_quote_slice import (
    AUTHORITY_PHRASE as SLICE_PHRASE,
    CONFIG_RELATIVE as SLICE_CONFIG_RELATIVE,
    EXPECTED_ENDPOINT,
    EXPECTED_INPUT_MINT,
    EXPECTED_NOTIONAL,
    EXPECTED_OUTPUT_MINT,
    INTENDED_ROUTE_ID,
    NEXT_OWNER_PHRASE,
    bind_pmf_quote_slice,
)

ATOM_ID = "PMF-QUOTE-SLICE-ONE-SHOT-V1"
AUTHORITY_PHRASE = NEXT_OWNER_PHRASE
CONFIG_RELATIVE = "configs/pmf_quote_slice_one_shot_v1.yaml"
CREDENTIAL_NAME = "JUPITER_API_KEY"
CREDENTIAL_ALIAS = "JUPITER_PORTAL_API_KEY"
EXPECTED_HOST = "api.jup.ag"
USER_AGENT = "smial-pmf-quote-slice-one-shot/1.0"


class QuoteShotError(ValueError):
    """The bounded one-shot contract cannot be satisfied."""


class QuoteShotTerminalError(QuoteShotError):
    """A terminal one-request outcome with sanitized evidence."""

    def __init__(self, code: str, *, evidence: Mapping[str, object]) -> None:
        super().__init__(code)
        self.evidence = dict(evidence)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QuoteShotError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> urllib.request.Request | None:
        return None


def validate_policy(policy: Mapping[str, Any], slice_result: Mapping[str, Any]) -> None:
    authority = _mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    route = _mapping(policy.get("provider_route"), "ROUTE_INVALID")
    request = _mapping(policy.get("request"), "REQUEST_INVALID")
    limits = _mapping(policy.get("runtime_limits"), "LIMITS_INVALID")
    controls = _mapping(policy.get("execution_controls"), "CONTROLS_INVALID")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_DRIFT")
    _require(authority.get("capture_authorized") is True, "CAPTURE_NOT_AUTHORIZED")
    _require(authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_POLICY_DRIFT")
    _require(authority.get("credential") == CREDENTIAL_NAME, "CREDENTIAL_NAME_DRIFT")
    _require(authority.get("execute") is False, "EXECUTE_NOT_FORBIDDEN")
    _require(authority.get("build") is False, "BUILD_NOT_FORBIDDEN")
    _require(authority.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(route.get("route_id") == INTENDED_ROUTE_ID, "ROUTE_ID_DRIFT")
    _require(route.get("endpoint") == EXPECTED_ENDPOINT, "ENDPOINT_DRIFT")
    _require(route.get("method") == "GET", "METHOD_DRIFT")
    _require(route.get("host") == EXPECTED_HOST, "HOST_DRIFT")
    _require(request.get("inputMint") == EXPECTED_INPUT_MINT, "INPUT_MINT_DRIFT")
    _require(request.get("outputMint") == EXPECTED_OUTPUT_MINT, "OUTPUT_MINT_DRIFT")
    _require(str(request.get("amount")) == EXPECTED_NOTIONAL, "NOTIONAL_DRIFT")
    _require("taker" not in request, "TAKER_IN_REQUEST")
    _require(controls.get("persist_transaction_bytes") is False, "TX_PERSIST_NOT_FORBIDDEN")
    _require(controls.get("retries") == 0, "RETRY_NOT_FORBIDDEN")
    _require(int(controls.get("provider_requests_max", 0)) == 1, "REQUEST_BUDGET_DRIFT")
    _require(float(limits.get("timeout_seconds", 0)) > 0, "TIMEOUT_INVALID")
    _require(int(limits.get("max_response_bytes", 0)) > 0, "MAX_BYTES_INVALID")
    _require(slice_result.get("owner_phrase") == SLICE_PHRASE, "SLICE_PHRASE_DRIFT")
    _require(slice_result.get("call_authorized") is False, "SLICE_ALREADY_AUTHORIZED")
    _require(
        slice_result.get("terminal") == "PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED",
        "SLICE_NOT_BOUND",
    )
    _require(slice_result.get("next_owner_phrase") == AUTHORITY_PHRASE, "NEXT_PHRASE_DRIFT")


def build_order_url(policy: Mapping[str, Any]) -> str:
    route = _mapping(policy.get("provider_route"), "ROUTE_INVALID")
    request = _mapping(policy.get("request"), "REQUEST_INVALID")
    query = urllib.parse.urlencode(
        [
            ("inputMint", str(request["inputMint"])),
            ("outputMint", str(request["outputMint"])),
            ("amount", str(request["amount"])),
            ("slippageBps", str(request["slippageBps"])),
        ]
    )
    url = f"{route['endpoint']}?{query}"
    _require("taker" not in url.lower(), "TAKER_IN_URL")
    parsed = urlsplit(url)
    _require(parsed.scheme == "https", "ENDPOINT_DRIFT")
    _require(parsed.hostname == EXPECTED_HOST, "HOST_DRIFT")
    _require(parsed.path == "/swap/v2/order", "ENDPOINT_DRIFT")
    return url


def credential_free_preflight(
    policy: Mapping[str, Any],
    *,
    observed_at: str,
    resolver: Callable[..., object] = socket.getaddrinfo,
    connector: Callable[..., object] = socket.create_connection,
    context_factory: Callable[[], object] = ssl.create_default_context,
) -> dict[str, object]:
    route = _mapping(policy.get("provider_route"), "ROUTE_INVALID")
    endpoint = urlsplit(str(route["endpoint"]))
    _require(
        endpoint.scheme == "https"
        and endpoint.hostname == EXPECTED_HOST
        and endpoint.port is None
        and not endpoint.query,
        "ENDPOINT_DRIFT",
    )
    host, port = endpoint.hostname, 443
    try:
        addresses = resolver(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise QuoteShotError("DNS_PREFLIGHT_FAILED") from exc
    _require(bool(addresses), "DNS_PREFLIGHT_FAILED")
    raw_socket: object | None = None
    try:
        raw_socket = connector((host, port), timeout=5.0)
    except (socket.timeout, TimeoutError, OSError) as exc:
        raise QuoteShotError("TCP_PREFLIGHT_FAILED") from exc
    try:
        context = context_factory()
        with context.wrap_socket(raw_socket, server_hostname=host) as tls_socket:  # type: ignore[union-attr]
            tls_version = str(tls_socket.version())
    except (ssl.SSLError, socket.timeout, TimeoutError, OSError) as exc:
        raise QuoteShotError("TLS_PREFLIGHT_FAILED") from exc
    finally:
        close = getattr(raw_socket, "close", None)
        if callable(close):
            close()
    _require(bool(tls_version), "TLS_PREFLIGHT_FAILED")
    return {
        "schema": "smial.pmf-quote-slice-one-shot.credential-free-preflight",
        "schema_version": "1.0",
        "observed_at": observed_at,
        "host": host,
        "port": port,
        "dns_resolved": True,
        "tcp_443": True,
        "tls_verified": True,
        "tls_version": tls_version,
        "credential_reads": 0,
        "provider_requests": 0,
    }


def perform_http_get_once(
    policy: Mapping[str, Any],
    api_key: str,
    *,
    opener: object | None = None,
) -> dict[str, object]:
    _require(type(api_key) is str, "CREDENTIAL_TYPE_INVALID")
    limits = _mapping(policy.get("runtime_limits"), "LIMITS_INVALID")
    url = build_order_url(policy)
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if api_key.strip():
        headers["x-api-key"] = api_key
    outgoing = urllib.request.Request(
        url,
        method="GET",
        headers=headers,
    )
    _require("taker" not in outgoing.full_url.lower(), "TAKER_IN_URL")
    selected_opener = opener or urllib.request.build_opener(_NoRedirectHandler())
    max_bytes = int(limits["max_response_bytes"])
    try:
        with selected_opener.open(outgoing, timeout=float(limits["timeout_seconds"])) as response:  # type: ignore[union-attr]
            status = int(response.getcode())
            body = response.read(max_bytes + 1)
            content_type = str(response.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read(max_bytes + 1)
        content_type = str(exc.headers.get("Content-Type", "")) if exc.headers is not None else ""
    except (urllib.error.URLError, ssl.SSLError, socket.gaierror, socket.timeout, TimeoutError, OSError) as exc:
        raise QuoteShotTerminalError(
            "TRANSPORT_ERROR",
            evidence={
                "transport": {
                    "http_status": None,
                    "content_type": None,
                    "response_bytes": None,
                    "response_sha256": None,
                    "request_count": 1,
                    "url_has_taker": False,
                    "url_has_api_key": "api-key" in url.lower() or "x-api-key" in url.lower(),
                },
                "body": None,
            },
        ) from exc
    if len(body) > max_bytes:
        raise QuoteShotTerminalError(
            "RESPONSE_BYTES_EXCEEDED",
            evidence={
                "transport": {
                    "http_status": status,
                    "content_type": content_type,
                    "response_bytes": len(body),
                    "response_sha256": None,
                    "request_count": 1,
                    "url_has_taker": False,
                    "url_has_api_key": False,
                },
                "body": None,
            },
        )
    return {
        "http_status": status,
        "content_type": content_type,
        "body": body,
        "response_bytes": len(body),
        "response_sha256": hashlib.sha256(body).hexdigest(),
        "request_count": 1,
        "url": url,
    }


def project_quote(body: bytes) -> dict[str, object]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QuoteShotError("QUOTE_JSON_INVALID") from exc
    _require(isinstance(payload, dict), "QUOTE_JSON_INVALID")
    transaction = payload.get("transaction")
    _require(transaction is None, "QUOTE_RETURNED_TRANSACTION")
    in_amount = payload.get("inAmount")
    out_amount = payload.get("outAmount")
    _require(type(in_amount) is str and bool(in_amount), "QUOTE_IN_AMOUNT_MISSING")
    _require(type(out_amount) is str and bool(out_amount), "QUOTE_OUT_AMOUNT_MISSING")
    router = payload.get("router")
    mode = payload.get("mode")
    _require(type(router) is str and bool(router), "QUOTE_ROUTER_MISSING")
    _require(type(mode) is str and bool(mode), "QUOTE_MODE_MISSING")
    return {
        "in_amount": in_amount,
        "out_amount": out_amount,
        "router": router,
        "mode": mode,
        "transaction_present": False,
        "request_id_present": type(payload.get("requestId")) is str and bool(payload.get("requestId")),
        "error_code": payload.get("errorCode"),
    }


def execute_once(
    policy: Mapping[str, Any],
    api_key: str,
    *,
    opener: object | None = None,
) -> dict[str, object]:
    raw = perform_http_get_once(policy, api_key, opener=opener)
    transport = {
        "http_status": raw["http_status"],
        "content_type": raw["content_type"],
        "response_bytes": raw["response_bytes"],
        "response_sha256": raw["response_sha256"],
        "request_count": 1,
        "url_has_taker": "taker" in str(raw["url"]).lower(),
        "url_has_api_key": False,
    }
    if raw["http_status"] != 200:
        raise QuoteShotTerminalError(
            "HTTP_STATUS_ERROR",
            evidence={"transport": transport, "body": raw["body"]},
        )
    try:
        quote = project_quote(raw["body"])
    except QuoteShotError as exc:
        raise QuoteShotTerminalError(
            str(exc),
            evidence={"transport": transport, "body": raw["body"]},
        ) from exc
    return {
        "transport": transport,
        "quote": quote,
        "body": raw["body"],
        "terminal_outcome": "QUOTE_OBSERVED",
    }


def bind_one_shot_prerequisites(root: Any, policy: Mapping[str, Any]) -> Mapping[str, Any]:
    from pathlib import Path

    slice_result = bind_pmf_quote_slice(Path(root))
    validate_policy(policy, slice_result)
    _require(SLICE_CONFIG_RELATIVE == "configs/pmf_quote_slice_v1.yaml", "SLICE_CONFIG_DRIFT")
    return slice_result
