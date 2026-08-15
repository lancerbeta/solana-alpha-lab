"""Bounded Helius continuation primitives for TASK-30 A23."""

from __future__ import annotations

import hashlib
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.task30_helius_get_transactions_for_address import (
    build_json_rpc_payload,
    credential_free_preflight as _a22_credential_free_preflight,
)


EXPECTED_ENDPOINT = "https://mainnet.helius-rpc.com/"
EXPECTED_METHOD = "getTransactionsForAddress"
EXPECTED_POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
EXPECTED_SINCE = 1_786_492_800
EXPECTED_TILL = 1_786_579_200
A22_REQUEST_ID = "task30-a22-helius-get-transactions-for-address"
CURSOR_RE = re.compile(r"[0-9]+:[0-9]+\Z")
PAGE_REQUEST_ID_RE = re.compile(r"task30-a23-helius-page-([12])\Z")


class A23Error(ValueError):
    """The bounded A23 continuation contract cannot be satisfied."""


class A23TerminalError(A23Error):
    """A terminal bounded-pagination outcome with secret-safe evidence."""

    def __init__(self, code: str, *, evidence: Mapping[str, object]) -> None:
        super().__init__(code)
        self.evidence = dict(evidence)


@dataclass(frozen=True)
class ValidatedPage:
    transaction_count: int
    transaction_keys: tuple[tuple[int, int], ...]
    primary_signatures: tuple[str, ...]
    block_times: tuple[int, ...]
    cursor: str | None = field(repr=False)
    cursor_sha256: str | None
    credits_upper_bound: int
    raw_sha256: str
    response_bytes: int


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A23Error(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _parse_utc(value: object, code: str) -> datetime:
    _require(type(value) is str and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise A23Error(code) from exc
    _require(parsed.tzinfo == UTC, code)
    return parsed


def _sections(
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
    _require(
        _parse_utc(window.get("since_inclusive"), "WINDOW_INVALID").timestamp()
        == EXPECTED_SINCE,
        "WINDOW_INVALID",
    )
    _require(
        _parse_utc(window.get("till_exclusive"), "WINDOW_INVALID").timestamp()
        == EXPECTED_TILL,
        "WINDOW_INVALID",
    )
    _require(
        dict(request)
        == {
            "transaction_details": "full",
            "sort_order": "asc",
            "limit": 1000,
            "commitment": "finalized",
            "encoding": "json",
            "max_supported_transaction_version": 0,
            "status": "succeeded",
            "token_accounts": "none",
        },
        "REQUEST_POLICY_INVALID",
    )
    expected_limits = {
        "max_credential_free_preflights": 1,
        "max_continuation_requests": 2,
        "max_response_bytes_per_page": 25_000_000,
        "max_new_response_bytes_total": 50_000_000,
        "timeout_seconds": 30,
        "max_full_transactions_per_page": 1000,
        "max_helius_credits_per_page": 100,
        "max_helius_credits_total": 200,
    }
    _require(dict(limits) == expected_limits, "RUNTIME_LIMITS_INVALID")
    _require(controls.get("pagination") is True, "PAGINATION_REQUIRED")
    for key in ("retry", "fallback", "redirect", "scheduler", "background_process"):
        _require(controls.get(key) is False, f"{key.upper()}_FORBIDDEN")
    return route, subject, window, limits


def _a22_policy_view(policy: Mapping[str, Any]) -> dict[str, object]:
    route, subject, window, limits = _sections(policy)
    return {
        "provider_route": dict(route),
        "reference_subject": dict(subject),
        "request": dict(_mapping(policy.get("request"), "REQUEST_POLICY_INVALID")),
        "pilot_window": dict(window),
        "runtime_limits": {
            "max_provider_requests": 1,
            "max_response_bytes": limits["max_response_bytes_per_page"],
            "timeout_seconds": limits["timeout_seconds"],
            "max_full_transactions": limits["max_full_transactions_per_page"],
            "max_helius_credits": limits["max_helius_credits_per_page"],
        },
        "execution_controls": {
            "retry": False,
            "fallback": False,
            "redirect": False,
            "pagination": False,
        },
    }


def cursor_sha256(cursor: object) -> str:
    """Validate an opaque Helius cursor and return only its safe digest."""

    _require(type(cursor) is str and CURSOR_RE.fullmatch(cursor) is not None, "PAGINATION_CURSOR_MALFORMED")
    return hashlib.sha256(cursor.encode("utf-8")).hexdigest()


def build_continuation_payload(
    policy: Mapping[str, Any], cursor: str, *, page_number: int
) -> dict[str, object]:
    """Build one exact continuation body; only id and opaque cursor may vary."""

    cursor_sha256(cursor)
    _require(type(page_number) is int and page_number in (1, 2), "PAGE_NUMBER_INVALID")
    payload = build_json_rpc_payload(_a22_policy_view(policy))
    payload["id"] = f"task30-a23-helius-page-{page_number}"
    params = payload["params"]
    _require(type(params) is list and len(params) == 2, "PAYLOAD_INVALID")
    options = _mapping(params[1], "PAYLOAD_INVALID")
    params[1] = {**options, "paginationToken": cursor}
    return payload


def credential_free_preflight(
    policy: Mapping[str, Any], *, observed_at: str
) -> dict[str, object]:
    """Reuse the sealed A22 DNS/TCP/TLS preflight through an A22 policy view."""

    return _a22_credential_free_preflight(
        _a22_policy_view(policy),
        observed_at=observed_at,
    )


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
        raise A23Error("JSON_INVALID") from exc
    return _mapping(value, "JSON_ROOT_INVALID")


def _account_key(value: object) -> str:
    if type(value) is str:
        return value
    item = _mapping(value, "ACCOUNT_KEY_INVALID")
    _require(type(item.get("pubkey")) is str, "ACCOUNT_KEY_INVALID")
    return str(item["pubkey"])


def _credits_upper_bound(count: int) -> int:
    return max(10, ((count + 99) // 100) * 10)


def validate_full_page(
    policy: Mapping[str, Any], body: bytes, *, expected_request_id: str
) -> ValidatedPage:
    """Validate one full continuation page and retain cursor only in memory."""

    _route, subject, window, limits = _sections(policy)
    _require(type(body) is bytes, "RESPONSE_BODY_INVALID")
    _require(len(body) <= int(limits["max_response_bytes_per_page"]), "RESPONSE_PAGE_BYTES_EXCEEDED")
    _require(
        expected_request_id == A22_REQUEST_ID
        or PAGE_REQUEST_ID_RE.fullmatch(expected_request_id) is not None,
        "RESPONSE_IDENTITY_INVALID",
    )
    document = _parse_json(body)
    _require(
        document.get("jsonrpc") == "2.0" and document.get("id") == expected_request_id,
        "RESPONSE_IDENTITY_DRIFT",
    )
    if "error" in document:
        _require(set(document) == {"jsonrpc", "id", "error"}, "ERROR_RESPONSE_SHAPE_DRIFT")
        error = _mapping(document.get("error"), "PROVIDER_ERROR_INVALID")
        _require(type(error.get("code")) is int and type(error.get("message")) is str, "PROVIDER_ERROR_INVALID")
        raise A23TerminalError(
            "PROVIDER_TYPED_FAILURE",
            evidence={"provider_error_code": error["code"]},
        )
    _require(set(document) == {"jsonrpc", "id", "result"}, "RESPONSE_FIELDS_DRIFT")
    result = _mapping(document.get("result"), "RESULT_INVALID")
    _require(set(result) == {"data", "paginationToken"}, "RESULT_FIELDS_DRIFT")
    rows = result.get("data")
    _require(type(rows) is list, "RESULT_DATA_INVALID")
    _require(len(rows) <= int(limits["max_full_transactions_per_page"]), "RESULT_COUNT_EXCEEDS_CAP")
    token = result.get("paginationToken")
    _require(token is None or type(token) is str, "PAGINATION_CURSOR_MALFORMED")
    digest = cursor_sha256(token) if token is not None else None
    keys: list[tuple[int, int]] = []
    signatures: list[str] = []
    block_times: list[int] = []
    for value in rows:
        row = _mapping(value, "TRANSACTION_ROW_INVALID")
        block_time = row.get("blockTime")
        slot = row.get("slot")
        transaction_index = row.get("transactionIndex")
        _require(type(block_time) is int, "BLOCK_TIME_INVALID")
        _require(type(slot) is int and slot >= 0, "SLOT_INVALID")
        _require(type(transaction_index) is int and transaction_index >= 0, "TRANSACTION_INDEX_INVALID")
        _require(window["block_time_gte"] <= block_time < window["block_time_lt"], "BLOCK_TIME_OUTSIDE_WINDOW")
        key = (slot, transaction_index)
        _require(not keys or key > keys[-1], "TRANSACTION_KEY_ORDER_DRIFT")
        _require(not block_times or block_time >= block_times[-1], "BLOCK_TIME_ORDER_DRIFT")
        _require(key not in keys, "DUPLICATE_TRANSACTION_KEY")
        transaction = _mapping(row.get("transaction"), "TRANSACTION_INVALID")
        raw_signatures = transaction.get("signatures")
        _require(
            type(raw_signatures) is list
            and raw_signatures
            and all(type(item) is str and item for item in raw_signatures),
            "SIGNATURES_INVALID",
        )
        signature = raw_signatures[0]
        _require(signature not in signatures, "DUPLICATE_SIGNATURE")
        message = _mapping(transaction.get("message"), "MESSAGE_INVALID")
        account_keys = message.get("accountKeys")
        _require(type(account_keys) is list, "ACCOUNT_KEYS_INVALID")
        normalized = [_account_key(item) for item in account_keys]
        meta = _mapping(row.get("meta"), "META_INVALID")
        loaded = meta.get("loadedAddresses")
        if loaded is not None:
            loaded_map = _mapping(loaded, "LOADED_ADDRESSES_INVALID")
            _require(set(loaded_map) == {"writable", "readonly"}, "LOADED_ADDRESSES_INVALID")
            for group in (loaded_map.get("writable"), loaded_map.get("readonly")):
                _require(type(group) is list, "LOADED_ADDRESSES_INVALID")
                normalized.extend(_account_key(item) for item in group)
        _require(subject["pool_address"] in normalized, "TARGET_POOL_NOT_BOUND")
        _require(meta.get("err") is None, "FAILED_TRANSACTION_RETURNED")
        keys.append(key)
        signatures.append(signature)
        block_times.append(block_time)
    credits = _credits_upper_bound(len(rows))
    _require(credits <= int(limits["max_helius_credits_per_page"]), "PAGE_CREDIT_CAP_EXCEEDED")
    return ValidatedPage(
        transaction_count=len(rows),
        transaction_keys=tuple(keys),
        primary_signatures=tuple(signatures),
        block_times=tuple(block_times),
        cursor=token,
        cursor_sha256=digest,
        credits_upper_bound=credits,
        raw_sha256=hashlib.sha256(body).hexdigest(),
        response_bytes=len(body),
    )


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> urllib.request.Request | None:
        return None


def perform_continuation_post_once(
    policy: Mapping[str, Any],
    payload: Mapping[str, Any],
    api_key: str,
    *,
    opener: object | None = None,
) -> dict[str, object]:
    """Perform exactly one continuation POST and return secret-safe metadata."""

    route, _subject, _window, limits = _sections(policy)
    _require(type(api_key) is str and bool(api_key.strip()), "CREDENTIAL_REQUIRED")
    request_id = payload.get("id")
    _require(type(request_id) is str, "PAYLOAD_INVALID")
    match = PAGE_REQUEST_ID_RE.fullmatch(request_id)
    _require(match is not None, "PAYLOAD_INVALID")
    params = payload.get("params")
    _require(type(params) is list and len(params) == 2, "PAYLOAD_INVALID")
    options = _mapping(params[1], "PAYLOAD_INVALID")
    cursor = options.get("paginationToken")
    _require(
        dict(payload)
        == build_continuation_payload(policy, cursor, page_number=int(match.group(1))),  # type: ignore[arg-type]
        "PAYLOAD_INVALID",
    )
    request_body = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    request_body_sha256 = hashlib.sha256(request_body).hexdigest()
    endpoint = str(route["endpoint"]) + "?api-key=" + urllib.parse.quote(api_key, safe="")
    outgoing = urllib.request.Request(
        endpoint,
        data=request_body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "smial-task30-a23/1.0",
        },
    )
    selected_opener = opener or urllib.request.build_opener(_NoRedirectHandler())
    max_bytes = int(limits["max_response_bytes_per_page"])
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
        raise A23TerminalError(
            "TRANSPORT_ERROR",
            evidence={
                "transport": {
                    "http_status": None,
                    "content_type": None,
                    "response_bytes": None,
                    "request_body_sha256": request_body_sha256,
                    "request_count": 1,
                }
            },
        ) from exc
    if len(body) > max_bytes:
        raise A23TerminalError(
            "RESPONSE_PAGE_BYTES_EXCEEDED",
            evidence={
                "transport": {
                    "http_status": status,
                    "content_type": content_type,
                    "response_bytes": len(body),
                    "request_body_sha256": request_body_sha256,
                    "request_count": 1,
                }
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


def _write_page(
    run_root: Path,
    *,
    page_number: int,
    body: bytes,
    request_body_sha256: str,
    observed_at: str,
) -> dict[str, object]:
    page_root = run_root / f"page={page_number:03d}"
    try:
        page_root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise A23Error("PAGE_ALREADY_EXISTS") from exc
    raw_path = page_root / "raw_response.json"
    raw_path.write_bytes(body)
    manifest: dict[str, object] = {
        "schema": "smial.task30.helius-bounded-pagination.raw-page-manifest",
        "schema_version": "1.0",
        "page_number": page_number,
        "observed_at": observed_at,
        "raw_filename": raw_path.name,
        "response_bytes": len(body),
        "raw_sha256": hashlib.sha256(body).hexdigest(),
        "request_body_sha256": request_body_sha256,
        "retention_class": "A4_OUTSIDE_GIT",
    }
    (page_root / "raw_manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _safe_page_summary(page_number: int, page: ValidatedPage) -> dict[str, object]:
    return {
        "page_number": page_number,
        "transaction_count": page.transaction_count,
        "response_bytes": page.response_bytes,
        "raw_sha256": page.raw_sha256,
        "cursor_present": page.cursor is not None,
        "cursor_sha256": page.cursor_sha256,
        "credits_upper_bound": page.credits_upper_bound,
        "first_transaction_key": list(page.transaction_keys[0]) if page.transaction_keys else None,
        "last_transaction_key": list(page.transaction_keys[-1]) if page.transaction_keys else None,
        "first_block_time": page.block_times[0] if page.block_times else None,
        "last_block_time": page.block_times[-1] if page.block_times else None,
    }


def verify_first_page_binding(
    policy: Mapping[str, Any], a22_raw_path: Path
) -> ValidatedPage:
    """Verify the retained A22 page before any credential is read."""

    _sections(policy)
    _require(
        isinstance(a22_raw_path, Path) and a22_raw_path.is_file(),
        "A22_FIRST_PAGE_NOT_FOUND",
    )
    binding = _mapping(policy.get("first_page_binding"), "FIRST_PAGE_BINDING_INVALID")
    first_body = a22_raw_path.read_bytes()
    _require(
        hashlib.sha256(first_body).hexdigest() == binding.get("raw_sha256"),
        "A22_FIRST_PAGE_IDENTITY_DRIFT",
    )
    first = validate_full_page(
        policy,
        first_body,
        expected_request_id=str(binding.get("request_id")),
    )
    _require(
        first.transaction_count == binding.get("transaction_count"),
        "A22_FIRST_PAGE_IDENTITY_DRIFT",
    )
    _require(
        first.cursor is not None
        and first.cursor_sha256 == binding.get("cursor_sha256"),
        "A22_FIRST_PAGE_IDENTITY_DRIFT",
    )
    return first


def execute_bounded_pagination(
    policy: Mapping[str, Any],
    api_key: str,
    a22_raw_path: Path,
    raw_root: Path,
    *,
    run_id: str,
    observed_at: str,
    post_fn: Callable[[Mapping[str, Any], dict[str, object], str], Mapping[str, object]] = perform_continuation_post_once,
) -> dict[str, object]:
    """Reuse page 0 and execute at most two sequential continuation requests."""

    _route, _subject, _window, limits = _sections(policy)
    _require(type(api_key) is str and bool(api_key.strip()), "CREDENTIAL_REQUIRED")
    _require(isinstance(raw_root, Path), "RAW_ROOT_INVALID")
    _require(type(run_id) is str and run_id and "/" not in run_id and "\\" not in run_id, "RUN_ID_INVALID")
    _parse_utc(observed_at, "OBSERVED_AT_INVALID")
    first = verify_first_page_binding(policy, a22_raw_path)
    run_root = raw_root / f"run={run_id}"
    try:
        run_root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise A23Error("RUN_ALREADY_EXISTS") from exc
    seen_keys = set(first.transaction_keys)
    seen_signatures = set(first.primary_signatures)
    seen_cursor_hashes = {first.cursor_sha256}
    last_key = first.transaction_keys[-1] if first.transaction_keys else None
    last_block_time = first.block_times[-1] if first.block_times else None
    cursor = first.cursor
    page_summaries = [_safe_page_summary(0, first)]
    raw_manifests: list[dict[str, object]] = []
    provider_requests = 0
    new_response_bytes = 0
    credits_upper_bound = 0
    total_transaction_count = first.transaction_count
    for page_number in range(1, int(limits["max_continuation_requests"]) + 1):
        _require(cursor is not None, "PAGINATION_CURSOR_MISSING")
        payload = build_continuation_payload(policy, cursor, page_number=page_number)
        try:
            transport = dict(post_fn(policy, payload, api_key))
        except A23TerminalError as exc:
            evidence = dict(exc.evidence)
            evidence.update(
                {
                    "provider_requests": provider_requests + 1,
                    "new_response_bytes": new_response_bytes,
                    "credits_upper_bound": min(
                        int(limits["max_helius_credits_total"]),
                        credits_upper_bound + int(limits["max_helius_credits_per_page"]),
                    ),
                    "page_summaries": page_summaries,
                    "raw_manifests": raw_manifests,
                }
            )
            raise A23TerminalError(str(exc), evidence=evidence) from exc
        provider_requests += 1
        _require(provider_requests <= int(limits["max_continuation_requests"]), "PROVIDER_REQUEST_CAP_EXCEEDED")
        safe_transport = {
            key: transport.get(key)
            for key in (
                "http_status",
                "content_type",
                "response_bytes",
                "request_body_sha256",
                "request_count",
            )
        }
        bytes_before_page = new_response_bytes
        attempted_response_bytes = 0
        try:
            body = transport.get("body")
            _require(type(body) is bytes, "RESPONSE_BODY_INVALID")
            attempted_response_bytes = len(body)
            _require(transport.get("response_bytes") == len(body), "RESPONSE_BYTES_MISMATCH")
            new_response_bytes += len(body)
            _require(new_response_bytes <= int(limits["max_new_response_bytes_total"]), "RESPONSE_TOTAL_NEW_BYTES_EXCEEDED")
            manifest = _write_page(
                run_root,
                page_number=page_number,
                body=body,
                request_body_sha256=str(transport.get("request_body_sha256")),
                observed_at=observed_at,
            )
            raw_manifests.append(manifest)
        except (A23Error, OSError) as exc:
            code = str(exc) if isinstance(exc, A23Error) else "RAW_RETENTION_ERROR"
            raise A23TerminalError(
                code,
                evidence={
                    "provider_requests": provider_requests,
                    "new_response_bytes": (
                        new_response_bytes
                        if new_response_bytes > bytes_before_page
                        else bytes_before_page + attempted_response_bytes
                    ),
                    "credits_upper_bound": min(
                        int(limits["max_helius_credits_total"]),
                        credits_upper_bound + int(limits["max_helius_credits_per_page"]),
                    ),
                    "transport": safe_transport,
                    "page_summaries": page_summaries,
                    "raw_manifests": raw_manifests,
                },
            ) from exc
        if transport.get("http_status") != 200:
            raise A23TerminalError(
                "HTTP_STATUS_ERROR",
                evidence={
                    "provider_requests": provider_requests,
                    "new_response_bytes": new_response_bytes,
                    "credits_upper_bound": min(
                        int(limits["max_helius_credits_total"]),
                        credits_upper_bound + int(limits["max_helius_credits_per_page"]),
                    ),
                    "transport": safe_transport,
                    "page_summaries": page_summaries,
                    "raw_manifests": raw_manifests,
                },
            )
        try:
            page = validate_full_page(
                policy,
                body,
                expected_request_id=f"task30-a23-helius-page-{page_number}",
            )
            if page.transaction_keys:
                _require(last_key is None or page.transaction_keys[0] > last_key, "TRANSACTION_KEY_ORDER_DRIFT")
                _require(
                    last_block_time is None or page.block_times[0] >= last_block_time,
                    "BLOCK_TIME_ORDER_DRIFT",
                )
            _require(not seen_keys.intersection(page.transaction_keys), "DUPLICATE_TRANSACTION_KEY")
            _require(not seen_signatures.intersection(page.primary_signatures), "DUPLICATE_SIGNATURE")
            if page.cursor_sha256 is not None:
                _require(page.cursor_sha256 not in seen_cursor_hashes, "PAGINATION_CURSOR_REPEATED")
        except (A23Error, A23TerminalError) as exc:
            code = str(exc)
            provider_error = exc.evidence if isinstance(exc, A23TerminalError) else {}
            raise A23TerminalError(
                code,
                evidence={
                    **provider_error,
                    "provider_requests": provider_requests,
                    "new_response_bytes": new_response_bytes,
                    "credits_upper_bound": min(
                        int(limits["max_helius_credits_total"]),
                        credits_upper_bound + int(limits["max_helius_credits_per_page"]),
                    ),
                    "transport": safe_transport,
                    "page_summaries": page_summaries,
                    "raw_manifests": raw_manifests,
                },
            ) from exc
        seen_keys.update(page.transaction_keys)
        seen_signatures.update(page.primary_signatures)
        if page.cursor_sha256 is not None:
            seen_cursor_hashes.add(page.cursor_sha256)
        if page.transaction_keys:
            last_key = page.transaction_keys[-1]
            last_block_time = page.block_times[-1]
        total_transaction_count += page.transaction_count
        credits_upper_bound += page.credits_upper_bound
        _require(credits_upper_bound <= int(limits["max_helius_credits_total"]), "TOTAL_CREDIT_CAP_EXCEEDED")
        page_summaries.append(_safe_page_summary(page_number, page))
        cursor = page.cursor
        if cursor is None:
            terminal_outcome = "COMPLETE_RAW_BATCH_CANDIDATE"
            break
    else:
        terminal_outcome = "BOUNDED_PAGINATION_INCOMPLETE_STOP"
    return {
        "terminal_outcome": terminal_outcome,
        "provider_requests": provider_requests,
        "a22_first_page_reused": True,
        "a22_first_page_refetched": False,
        "total_transaction_count": total_transaction_count,
        "new_response_bytes": new_response_bytes,
        "credits_upper_bound": credits_upper_bound,
        "page_summaries": page_summaries,
        "raw_manifests": raw_manifests,
        "complete_raw_batch_candidate": terminal_outcome == "COMPLETE_RAW_BATCH_CANDIDATE",
        "pit_admissible": False,
        "h07_h01_evidence": False,
        "task30_acceptance": False,
    }
