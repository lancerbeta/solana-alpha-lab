"""Bounded Helius getTransactionsForAddress primitives for TASK-30 A22."""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


EXPECTED_ENDPOINT = "https://mainnet.helius-rpc.com/"
EXPECTED_METHOD = "getTransactionsForAddress"
EXPECTED_POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
EXPECTED_SINCE = 1_786_492_800
EXPECTED_TILL = 1_786_579_200
EXPECTED_LIMIT = 1000
EXPECTED_MAX_BYTES = 25_000_000
REQUEST_ID = "task30-a22-helius-get-transactions-for-address"


class A22Error(ValueError):
    """The bounded A22 contract cannot be satisfied."""


class A22TerminalError(A22Error):
    """A terminal one-request outcome with sanitized evidence."""

    def __init__(self, code: str, *, evidence: Mapping[str, object]) -> None:
        super().__init__(code)
        self.evidence = dict(evidence)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A22Error(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _parse_utc(value: object, code: str) -> datetime:
    _require(type(value) is str and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise A22Error(code) from exc
    _require(parsed.tzinfo == UTC, code)
    return parsed


def _policy_sections(
    policy: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    route = _mapping(policy.get("provider_route"), "PROVIDER_ROUTE_INVALID")
    subject = _mapping(policy.get("reference_subject"), "REFERENCE_SUBJECT_INVALID")
    request = _mapping(policy.get("request"), "REQUEST_POLICY_INVALID")
    window = _mapping(policy.get("pilot_window"), "PILOT_WINDOW_INVALID")
    limits = _mapping(policy.get("runtime_limits"), "RUNTIME_LIMITS_INVALID")
    controls = _mapping(policy.get("execution_controls"), "EXECUTION_CONTROLS_INVALID")
    _require(route.get("endpoint") == EXPECTED_ENDPOINT, "ENDPOINT_INVALID")
    _require(route.get("method") == EXPECTED_METHOD, "METHOD_INVALID")
    _require(subject.get("pool_address") == EXPECTED_POOL, "POOL_INVALID")
    _require(window.get("block_time_gte") == EXPECTED_SINCE, "WINDOW_INVALID")
    _require(window.get("block_time_lt") == EXPECTED_TILL, "WINDOW_INVALID")
    _require(_parse_utc(window.get("since_inclusive"), "WINDOW_INVALID").timestamp() == EXPECTED_SINCE, "WINDOW_INVALID")
    _require(_parse_utc(window.get("till_exclusive"), "WINDOW_INVALID").timestamp() == EXPECTED_TILL, "WINDOW_INVALID")
    expected_request = {
        "transaction_details": "full",
        "sort_order": "asc",
        "limit": EXPECTED_LIMIT,
        "commitment": "finalized",
        "encoding": "json",
        "max_supported_transaction_version": 0,
        "status": "succeeded",
        "token_accounts": "none",
    }
    _require(dict(request) == expected_request, "REQUEST_POLICY_INVALID")
    _require(limits.get("max_provider_requests") == 1, "REQUEST_CAP_INVALID")
    _require(limits.get("max_response_bytes") == EXPECTED_MAX_BYTES, "RESPONSE_CAP_INVALID")
    _require(limits.get("timeout_seconds") == 30, "TIMEOUT_INVALID")
    _require(limits.get("max_full_transactions") == EXPECTED_LIMIT, "TRANSACTION_CAP_INVALID")
    _require(limits.get("max_helius_credits") == 100, "CREDIT_CAP_INVALID")
    for key in ("retry", "fallback", "redirect", "pagination"):
        _require(controls.get(key) is False, f"{key.upper()}_FORBIDDEN")
    return route, subject, window, limits


def build_json_rpc_payload(policy: Mapping[str, Any]) -> dict[str, object]:
    """Build the only JSON-RPC body authorized by A22."""

    _route, subject, window, _limits = _policy_sections(policy)
    return {
        "jsonrpc": "2.0",
        "id": REQUEST_ID,
        "method": EXPECTED_METHOD,
        "params": [
            subject["pool_address"],
            {
                "transactionDetails": "full",
                "sortOrder": "asc",
                "limit": EXPECTED_LIMIT,
                "commitment": "finalized",
                "encoding": "json",
                "maxSupportedTransactionVersion": 0,
                "filters": {
                    "blockTime": {
                        "gte": window["block_time_gte"],
                        "lt": window["block_time_lt"],
                    },
                    "status": "succeeded",
                    "tokenAccounts": "none",
                },
            },
        ],
    }


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_json(body: bytes) -> Mapping[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(body, object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise A22Error("JSON_INVALID") from exc
    return _mapping(value, "JSON_ROOT_INVALID")


def _account_key(value: object) -> str:
    if type(value) is str:
        return value
    item = _mapping(value, "ACCOUNT_KEY_INVALID")
    pubkey = item.get("pubkey")
    _require(type(pubkey) is str, "ACCOUNT_KEY_INVALID")
    return pubkey


def _projection_base(
    policy: Mapping[str, Any],
    *,
    observed_at: str,
    raw_sha256: str,
    response_bytes: int,
) -> dict[str, object]:
    route, subject, window, _limits = _policy_sections(policy)
    _parse_utc(observed_at, "OBSERVED_AT_INVALID")
    _require(type(raw_sha256) is str and len(raw_sha256) == 64, "RAW_SHA256_INVALID")
    _require(type(response_bytes) is int and response_bytes >= 0, "RESPONSE_BYTES_INVALID")
    return {
        "schema": "smial.task30.helius-get-transactions-for-address.runtime-projection",
        "schema_version": "1.0",
        "task_id": "TASK-30",
        "atom_id": policy.get("atom_id"),
        "route_id": route.get("route_id"),
        "observed_at": observed_at,
        "raw_sha256": raw_sha256,
        "response_bytes": response_bytes,
        "pool_address": subject.get("pool_address"),
        "window": {
            "block_time_gte": window.get("block_time_gte"),
            "block_time_lt": window.get("block_time_lt"),
        },
        "pit_admissible": False,
        "h07_h01_evidence": False,
        "task30_acceptance": False,
        "zero_activity_claim": False,
    }


def classify_full_response(
    policy: Mapping[str, Any],
    body: bytes,
    *,
    raw_sha256: str,
    response_bytes: int,
    observed_at: str,
) -> dict[str, object]:
    """Validate one full-mode response and classify its bounded route outcome."""

    _require(type(body) is bytes, "RESPONSE_BODY_INVALID")
    _require(hashlib.sha256(body).hexdigest() == raw_sha256, "RAW_SHA256_MISMATCH")
    _require(len(body) == response_bytes, "RESPONSE_BYTES_MISMATCH")
    base = _projection_base(
        policy,
        observed_at=observed_at,
        raw_sha256=raw_sha256,
        response_bytes=response_bytes,
    )
    document = _parse_json(body)
    _require(document.get("jsonrpc") == "2.0" and document.get("id") == REQUEST_ID, "RESPONSE_IDENTITY_DRIFT")
    if "error" in document:
        _require(set(document) == {"jsonrpc", "id", "error"}, "ERROR_RESPONSE_SHAPE_DRIFT")
        error = _mapping(document.get("error"), "PROVIDER_ERROR_INVALID")
        _require(type(error.get("code")) is int and type(error.get("message")) is str, "PROVIDER_ERROR_INVALID")
        return {
            **base,
            "terminal_outcome": "PROVIDER_TYPED_FAILURE",
            "provider_error_code": error["code"],
            "transaction_count": None,
            "pagination_token_present": None,
            "route_fit_for_raw_batch": False,
        }
    _require(set(document) == {"jsonrpc", "id", "result"}, "RESPONSE_FIELDS_DRIFT")
    result = _mapping(document.get("result"), "RESULT_INVALID")
    _require(set(result) == {"data", "paginationToken"}, "RESULT_FIELDS_DRIFT")
    rows = result.get("data")
    _require(type(rows) is list, "RESULT_DATA_INVALID")
    _require(len(rows) <= EXPECTED_LIMIT, "RESULT_COUNT_EXCEEDS_CAP")
    token = result.get("paginationToken")
    _require(token is None or type(token) is str, "PAGINATION_TOKEN_INVALID")
    subject = _mapping(policy.get("reference_subject"), "REFERENCE_SUBJECT_INVALID")
    window = _mapping(policy.get("pilot_window"), "PILOT_WINDOW_INVALID")
    prior_order: tuple[int, int, int] | None = None
    signatures_seen: set[str] = set()
    first_block_time: int | None = None
    last_block_time: int | None = None
    for value in rows:
        row = _mapping(value, "TRANSACTION_ROW_INVALID")
        block_time, slot, transaction_index = row.get("blockTime"), row.get("slot"), row.get("transactionIndex")
        _require(type(block_time) is int, "BLOCK_TIME_INVALID")
        _require(type(slot) is int and slot >= 0, "SLOT_INVALID")
        _require(type(transaction_index) is int and transaction_index >= 0, "TRANSACTION_INDEX_INVALID")
        _require(window["block_time_gte"] <= block_time < window["block_time_lt"], "BLOCK_TIME_OUTSIDE_WINDOW")
        order = (block_time, slot, transaction_index)
        _require(prior_order is None or order >= prior_order, "RESULT_ORDER_DRIFT")
        prior_order = order
        transaction = _mapping(row.get("transaction"), "TRANSACTION_INVALID")
        signatures = transaction.get("signatures")
        _require(type(signatures) is list and signatures and all(type(item) is str for item in signatures), "SIGNATURES_INVALID")
        primary_signature = signatures[0]
        _require(primary_signature not in signatures_seen, "DUPLICATE_TRANSACTION")
        signatures_seen.add(primary_signature)
        message = _mapping(transaction.get("message"), "MESSAGE_INVALID")
        account_keys = message.get("accountKeys")
        _require(type(account_keys) is list, "ACCOUNT_KEYS_INVALID")
        keys = [_account_key(item) for item in account_keys]
        meta = _mapping(row.get("meta"), "META_INVALID")
        loaded = meta.get("loadedAddresses")
        if loaded is not None:
            loaded_map = _mapping(loaded, "LOADED_ADDRESSES_INVALID")
            _require(set(loaded_map) == {"writable", "readonly"}, "LOADED_ADDRESSES_INVALID")
            for group in (loaded_map.get("writable"), loaded_map.get("readonly")):
                _require(type(group) is list, "LOADED_ADDRESSES_INVALID")
                keys.extend(_account_key(item) for item in group)
        _require(subject["pool_address"] in keys, "TARGET_POOL_NOT_BOUND")
        _require(meta.get("err") is None, "FAILED_TRANSACTION_RETURNED")
        first_block_time = block_time if first_block_time is None else first_block_time
        last_block_time = block_time
    count = len(rows)
    if count == EXPECTED_LIMIT:
        terminal = "TRUNCATED_AT_1000_STOP"
        route_fit = False
    elif token is not None:
        terminal = "PAGINATION_REQUIRED_STOP"
        route_fit = False
    elif count == 0:
        terminal = "ZERO_RESULT_TYPED_GAP"
        route_fit = False
    else:
        terminal = "BATCH_OBSERVED_LT_1000"
        route_fit = True
    return {
        **base,
        "terminal_outcome": terminal,
        "provider_error_code": None,
        "transaction_count": count,
        "pagination_token_present": token is not None,
        "first_block_time": first_block_time,
        "last_block_time": last_block_time,
        "route_fit_for_raw_batch": route_fit,
    }


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> urllib.request.Request | None:
        return None


def perform_http_post_once(
    policy: Mapping[str, Any],
    payload: Mapping[str, Any],
    api_key: str,
    *,
    opener: object | None = None,
) -> dict[str, object]:
    """Perform the single authorized POST and return only safe metadata."""

    route, _subject, _window, limits = _policy_sections(policy)
    _require(type(api_key) is str and bool(api_key.strip()), "CREDENTIAL_REQUIRED")
    _require(dict(payload) == build_json_rpc_payload(policy), "PAYLOAD_INVALID")
    request_body = _canonical_json_bytes(payload)
    endpoint = str(route["endpoint"]) + "?api-key=" + urllib.parse.quote(api_key, safe="")
    outgoing = urllib.request.Request(
        endpoint,
        data=request_body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "smial-task30-a22/1.0",
        },
    )
    selected_opener = opener or urllib.request.build_opener(_NoRedirectHandler())
    max_bytes = int(limits["max_response_bytes"])
    request_body_sha256 = hashlib.sha256(request_body).hexdigest()
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
        raise A22TerminalError(
            "TRANSPORT_ERROR",
            evidence={
                "transport": {
                    "http_status": None,
                    "content_type": None,
                    "response_bytes": None,
                    "request_body_sha256": request_body_sha256,
                    "request_count": 1,
                },
                "raw_manifest": None,
            },
        ) from exc
    if len(body) > max_bytes:
        raise A22TerminalError(
            "RESPONSE_BYTES_EXCEEDED",
            evidence={
                "transport": {
                    "http_status": status,
                    "content_type": content_type,
                    "response_bytes": len(body),
                    "request_body_sha256": request_body_sha256,
                    "request_count": 1,
                },
                "raw_manifest": None,
            },
        )
    return {
        "body": body,
        "http_status": status,
        "content_type": content_type,
        "response_bytes": len(body),
        "request_body_sha256": request_body_sha256,
        "request_count": 1,
    }


def write_raw_artifacts(
    raw_root: Path,
    *,
    run_id: str,
    response_body: bytes,
    request_body_sha256: str,
    observed_at: str,
) -> dict[str, object]:
    """Persist exact response bytes and a create-only, secret-free manifest."""

    _require(isinstance(raw_root, Path), "RAW_ROOT_INVALID")
    _require(type(run_id) is str and run_id and "/" not in run_id and "\\" not in run_id, "RUN_ID_INVALID")
    _require(type(response_body) is bytes, "RESPONSE_BODY_INVALID")
    _require(type(request_body_sha256) is str and len(request_body_sha256) == 64, "REQUEST_SHA256_INVALID")
    _parse_utc(observed_at, "OBSERVED_AT_INVALID")
    run_root = raw_root / f"run={run_id}"
    try:
        run_root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise A22Error("RUN_ALREADY_EXISTS") from exc
    raw_path = run_root / "raw_response.json"
    raw_path.write_bytes(response_body)
    manifest: dict[str, object] = {
        "schema": "smial.task30.helius-get-transactions-for-address.raw-manifest",
        "schema_version": "1.0",
        "run_id": run_id,
        "observed_at": observed_at,
        "raw_filename": raw_path.name,
        "response_bytes": len(response_body),
        "raw_sha256": hashlib.sha256(response_body).hexdigest(),
        "request_body_sha256": request_body_sha256,
        "retention_class": "A4_OUTSIDE_GIT",
    }
    (run_root / "raw_manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def credential_free_preflight(
    policy: Mapping[str, Any],
    *,
    observed_at: str,
    resolver: Callable[..., object] = socket.getaddrinfo,
    connector: Callable[..., object] = socket.create_connection,
    context_factory: Callable[[], object] = ssl.create_default_context,
) -> dict[str, object]:
    """Verify DNS, TCP and hostname-checked TLS before any credential read."""

    route, _subject, _window, _limits = _policy_sections(policy)
    _parse_utc(observed_at, "OBSERVED_AT_INVALID")
    endpoint = urlsplit(str(route["endpoint"]))
    _require(
        endpoint.scheme == "https"
        and endpoint.hostname == "mainnet.helius-rpc.com"
        and endpoint.port is None
        and endpoint.path == "/"
        and not endpoint.query,
        "ENDPOINT_INVALID",
    )
    host, port = endpoint.hostname, 443
    try:
        addresses = resolver(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise A22Error("DNS_PREFLIGHT_FAILED") from exc
    _require(bool(addresses), "DNS_PREFLIGHT_FAILED")
    raw_socket: object | None = None
    try:
        raw_socket = connector((host, port), timeout=5.0)
    except (socket.timeout, TimeoutError, OSError) as exc:
        raise A22Error("TCP_PREFLIGHT_FAILED") from exc
    try:
        context = context_factory()
        with context.wrap_socket(raw_socket, server_hostname=host) as tls_socket:  # type: ignore[union-attr]
            tls_version = str(tls_socket.version())
    except (ssl.SSLError, socket.timeout, TimeoutError, OSError) as exc:
        raise A22Error("TLS_PREFLIGHT_FAILED") from exc
    finally:
        close = getattr(raw_socket, "close", None)
        if callable(close):
            close()
    _require(bool(tls_version), "TLS_PREFLIGHT_FAILED")
    return {
        "schema": "smial.task30.helius-get-transactions-for-address.credential-free-preflight",
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


def execute_once(
    policy: Mapping[str, Any],
    api_key: str,
    raw_root: Path,
    *,
    run_id: str,
    observed_at: str,
    opener: object | None = None,
) -> dict[str, object]:
    """Execute and retain the single provider response."""

    payload = build_json_rpc_payload(policy)
    transport = perform_http_post_once(policy, payload, api_key, opener=opener)
    body = transport["body"]
    _require(type(body) is bytes, "RESPONSE_BODY_INVALID")
    manifest = write_raw_artifacts(
        raw_root,
        run_id=run_id,
        response_body=body,
        request_body_sha256=str(transport["request_body_sha256"]),
        observed_at=observed_at,
    )
    safe_transport = {key: value for key, value in transport.items() if key != "body"}
    evidence = {"transport": safe_transport, "raw_manifest": manifest}
    if transport["http_status"] != 200:
        raise A22TerminalError("HTTP_STATUS_ERROR", evidence=evidence)
    try:
        projection = classify_full_response(
            policy,
            body,
            raw_sha256=str(manifest["raw_sha256"]),
            response_bytes=int(manifest["response_bytes"]),
            observed_at=observed_at,
        )
    except A22Error as exc:
        raise A22TerminalError(str(exc), evidence=evidence) from exc
    return {"transport": safe_transport, "raw_manifest": manifest, "projection": projection}
