"""Bounded keyless getTransaction of the retained H11 Create signature.

Adopts SOLANA-STANDARD-GET-TRANSACTION-001. No Helius, no credential, no retry.
Does not mutate the pinned TASK-08 decoder. TASK-40/39 receipts stay immutable.
"""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from solana_alpha_lab.pump_event_decoder import PumpEventPlan, load_pinned_pump_event_plan
from solana_alpha_lab.rc002_h11_create_without_virtual_quote import (
    CREATE_EVENT,
    candidate_drop_quote_mint_and_virtual_quote_reserves,
    classify_create_bodies,
)
from solana_alpha_lab.rc002_h11_truncation_vs_absence import IDL_RELATIVE

ATOM_ID = "RC002-H11-BOUNDED-GETTRANSACTION-CREATE-V1"
ROUTE_ID = "SOLANA-STANDARD-GET-TRANSACTION-001"
REQUEST_ID = "rc002-h11-bounded-gettransaction-create"
ENDPOINT = "https://api.mainnet-beta.solana.com/"
HOST = "api.mainnet-beta.solana.com"
PINNED_SIGNATURE = (
    "4fi62bv2A67i6rFh6naBrLyVoteXT4EnXaQzK7K2rboujxRy2AxEu5epesgG7hRcT3xhpZx15EKGG4BxxspX61EH"
)
GTA_CREATE_PAYLOAD_LEN = 195
MAX_RESPONSE_BYTES = 2_000_000
TIMEOUT_SECONDS = 15.0
TERMINAL_OUTCOMES = (
    "CREATE_GETTX_SAME_195_STILL_TRUNCATED",
    "CREATE_GETTX_SAME_195_CONSUMED",
    "CREATE_GETTX_LONGER_BODY_CONSUMED",
    "CREATE_GETTX_LONGER_BODY_STILL_TRUNCATED",
    "CREATE_GETTX_SHORTER_THAN_GTA",
    "CREATE_GETTX_CREATE_BODY_ABSENT",
    "CREATE_GETTX_NULL_OR_UNAVAILABLE",
    "PROVIDER_TYPED_FAILURE",
    "TRANSPORT_OR_COVERAGE_UNKNOWN",
)


class BoundedGetTransactionError(ValueError):
    """The bounded getTransaction contract cannot be satisfied."""


class BoundedGetTransactionTerminal(BoundedGetTransactionError):
    """Typed one-shot outcome with sanitized evidence."""

    def __init__(self, code: str, *, evidence: Mapping[str, object]) -> None:
        super().__init__(code)
        self.evidence = dict(evidence)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BoundedGetTransactionError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def bind_get_transaction_request(*, signature: str = PINNED_SIGNATURE) -> dict[str, object]:
    _require(signature == PINNED_SIGNATURE, "SIGNATURE_NOT_PINNED")
    body = json.dumps(
        {
            "id": REQUEST_ID,
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
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "route_id": ROUTE_ID,
        "url": ENDPOINT,
        "method": "POST",
        "headers": {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "smial-rc002-h11-gettransaction/1.0",
        },
        "body": body,
        "body_sha256": _sha256_bytes(body),
    }


def dns_tcp_preflight(
    *,
    resolver=socket.getaddrinfo,
    connector=socket.create_connection,
) -> dict[str, object]:
    endpoint = urlsplit(ENDPOINT)
    _require(
        endpoint.scheme == "https"
        and endpoint.hostname == HOST
        and endpoint.port is None
        and (endpoint.path or "/") == "/"
        and not endpoint.query,
        "ENDPOINT_INVALID",
    )
    try:
        addresses = resolver(HOST, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise BoundedGetTransactionError("DNS_PREFLIGHT_FAILED") from exc
    _require(bool(addresses), "DNS_PREFLIGHT_FAILED")
    raw_socket: object | None = None
    try:
        raw_socket = connector((HOST, 443), timeout=5.0)
    except (socket.timeout, TimeoutError, OSError) as exc:
        raise BoundedGetTransactionError("TCP_PREFLIGHT_FAILED") from exc
    finally:
        close = getattr(raw_socket, "close", None)
        if callable(close):
            close()
    return {
        "host": HOST,
        "port": 443,
        "dns_resolved": True,
        "tcp_443": True,
        "credential_reads": 0,
        "provider_requests": 0,
    }


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> urllib.request.Request | None:
        return None


def perform_http_post_once(
    request: Mapping[str, object],
    *,
    opener: object | None = None,
) -> dict[str, object]:
    bound = bind_get_transaction_request()
    _require(request["body"] == bound["body"], "PAYLOAD_INVALID")
    _require(request["url"] == ENDPOINT, "ENDPOINT_INVALID")
    outgoing = urllib.request.Request(
        ENDPOINT,
        data=bytes(bound["body"]),
        method="POST",
        headers=dict(bound["headers"]),  # type: ignore[arg-type]
    )
    selected = opener or urllib.request.build_opener(_NoRedirectHandler())
    try:
        with selected.open(outgoing, timeout=TIMEOUT_SECONDS) as response:  # type: ignore[union-attr]
            status = int(response.getcode())
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, ssl.SSLError, socket.gaierror, socket.timeout, TimeoutError, OSError) as exc:
        raise BoundedGetTransactionTerminal(
            "TRANSPORT_OR_COVERAGE_UNKNOWN",
            evidence={
                "http_status": None,
                "response_bytes": None,
                "request_body_sha256": bound["body_sha256"],
                "request_count": 1,
            },
        ) from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise BoundedGetTransactionTerminal(
            "TRANSPORT_OR_COVERAGE_UNKNOWN",
            evidence={
                "http_status": status,
                "response_bytes": len(body),
                "request_body_sha256": bound["body_sha256"],
                "request_count": 1,
            },
        )
    return {
        "http_status": status,
        "body": body,
        "response_bytes": len(body),
        "response_sha256": _sha256_bytes(body),
        "request_body_sha256": bound["body_sha256"],
        "request_count": 1,
        "credential_reads": 0,
    }


def _parse_json(body: bytes) -> Mapping[str, Any]:
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BoundedGetTransactionError("JSON_INVALID") from exc
    return _mapping(document, "JSON_ROOT_INVALID")


def _row_from_result(result: Mapping[str, Any]) -> dict[str, Any]:
    transaction = dict(_mapping(result.get("transaction") or {}, "TRANSACTION_INVALID"))
    signatures = transaction.get("signatures") or []
    _require(
        isinstance(signatures, list)
        and signatures
        and signatures[0] == PINNED_SIGNATURE,
        "SIGNATURE_MISMATCH",
    )
    return {
        "slot": result.get("slot"),
        "blockTime": result.get("blockTime"),
        "transaction": transaction,
        "meta": dict(_mapping(result.get("meta") or {}, "META_INVALID")),
    }


def decide_gettx_terminal(scan: Mapping[str, Any], *, live_len: int | None) -> str:
    if live_len is None:
        return "CREATE_GETTX_CREATE_BODY_ABSENT"
    consumed = int(dict(scan.get("consumed_by_event") or {}).get(CREATE_EVENT, 0) or 0)
    failed = int(dict(scan.get("failed_by_event") or {}).get(CREATE_EVENT, 0) or 0)
    if live_len < GTA_CREATE_PAYLOAD_LEN:
        return "CREATE_GETTX_SHORTER_THAN_GTA"
    if live_len == GTA_CREATE_PAYLOAD_LEN:
        if consumed > 0 and failed == 0:
            return "CREATE_GETTX_SAME_195_CONSUMED"
        return "CREATE_GETTX_SAME_195_STILL_TRUNCATED"
    if consumed > 0 and failed == 0:
        return "CREATE_GETTX_LONGER_BODY_CONSUMED"
    return "CREATE_GETTX_LONGER_BODY_STILL_TRUNCATED"


def classify_gettransaction_body(
    body: bytes,
    *,
    pinned: PumpEventPlan,
) -> dict[str, Any]:
    document = _parse_json(body)
    if "error" in document:
        error = dict(_mapping(document.get("error"), "PROVIDER_ERROR_INVALID"))
        return {
            "terminal": "PROVIDER_TYPED_FAILURE",
            "provider_error_code": error.get("code"),
            "scan": None,
            "live_payload_len": None,
        }
    if document.get("result") is None:
        return {
            "terminal": "CREATE_GETTX_NULL_OR_UNAVAILABLE",
            "provider_error_code": None,
            "scan": None,
            "live_payload_len": None,
        }
    result = dict(_mapping(document.get("result"), "RESULT_INVALID"))
    row = _row_from_result(result)
    candidate = candidate_drop_quote_mint_and_virtual_quote_reserves(pinned)
    scan = classify_create_bodies([row], pinned=pinned, candidate=candidate)
    lengths = list(scan.get("payload_len_by_event", {}).get(CREATE_EVENT) or [])
    live_len = lengths[0] if len(lengths) == 1 else None
    if len(lengths) > 1:
        live_len = None
    return {
        "terminal": decide_gettx_terminal(scan, live_len=live_len),
        "provider_error_code": None,
        "scan": scan,
        "live_payload_len": live_len,
        "gta_payload_len": GTA_CREATE_PAYLOAD_LEN,
        "signature": PINNED_SIGNATURE,
        "candidate_id": scan.get("candidate_id"),
    }


def classify_transport_failure(exc: BoundedGetTransactionTerminal) -> dict[str, Any]:
    return {
        "terminal": "TRANSPORT_OR_COVERAGE_UNKNOWN",
        "provider_error_code": None,
        "scan": None,
        "live_payload_len": None,
        "transport": exc.evidence,
    }


def write_raw_a4(raw_root: Path, *, body: bytes) -> dict[str, str | int]:
    raw_root.mkdir(parents=True, exist_ok=True)
    path = raw_root / "raw_response.json"
    path.write_bytes(body)
    return {
        "path": "local/rc002_h11_bounded_gettransaction_create/raw_response.json",
        "response_bytes": len(body),
        "sha256": _sha256_bytes(body),
    }


def load_pinned_plan(repo_root: Path) -> PumpEventPlan:
    return load_pinned_pump_event_plan(repo_root / IDL_RELATIVE)
