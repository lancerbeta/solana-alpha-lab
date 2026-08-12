"""One-shot guarded runtime for the TASK-30 pool activity discriminator."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .lifecycle_discovery_transport import BoundProbeRequest, HttpCapture
from .task30_pool_activity_discriminator import (
    build_pool_activity_request,
    classify_pool_activity_response,
    evaluate_pool_activity_policy,
)


LOGICAL_ROOT = "local/task30_pool_activity_discriminator"
LOGICAL_ROOT_V2 = "local/task30_pool_activity_discriminator_v2"
MAX_RESPONSE_BYTES = 2_000_000
AUTHORITY_PHRASE = (
    "T30-A16P_POOL_ACTIVITY_DISCRIMINATOR_RUNTIME_V1; "
    "pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S; "
    "provider=HELIUS_STANDARD_RPC; method=getSignaturesForAddress; "
    "capture_started_at=2026-08-12T09:27:52.749910Z; "
    "capture_terminal_at=2026-08-12T09:37:53.059095Z; "
    "max_requests=1; limit=1000; commitment=confirmed; "
    "estimated_credit_cap=1; retention=A4; retry=false; fallback=false; "
    "transaction_followups=0"
)
AUTHORITY_PHRASE_V2 = AUTHORITY_PHRASE.replace("RUNTIME_V1", "RUNTIME_V2")
_REQUEST_ID = "task30-a16-pool-activity-discriminator"
_HELIUS_HOST = "mainnet.helius-rpc.com"
_NONCE_RE = re.compile(r"[0-9a-f]{8}")


class PoolActivityRuntimeError(RuntimeError):
    """Fail-closed runtime contract violation."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PoolActivityRuntimeError(code)


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PoolActivityRuntimeError("JSON_VALUE_INVALID") from exc


def _publish_new(path: Path, body: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(body)
    except (FileExistsError, OSError) as exc:
        raise PoolActivityRuntimeError("IMMUTABLE_WRITE_FAILED") from exc


def _utc_text(value: datetime) -> str:
    _require(value.tzinfo is not None, "AWARE_CLOCK_REQUIRED")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _validate_secret(value: object) -> str:
    _require(type(value) is str, "HELIUS_CREDENTIAL_INVALID")
    _require(value == value.strip(), "HELIUS_CREDENTIAL_INVALID")
    _require(8 <= len(value) <= 512, "HELIUS_CREDENTIAL_INVALID")
    _require(
        all(33 <= ord(character) < 127 for character in value),
        "HELIUS_CREDENTIAL_INVALID",
    )
    return value


def _bind_request(config: Mapping[str, Any], credential: str) -> BoundProbeRequest:
    body = _canonical_json(build_pool_activity_request(config))
    query = urllib.parse.urlencode((("api-key", credential),))
    return BoundProbeRequest(
        request_id=_REQUEST_ID,
        provider="HELIUS",
        transport="HTTP",
        method="POST",
        url=f"https://{_HELIUS_HOST}/?{query}",
        headers=(
            ("accept", "application/json"),
            ("content-type", "application/json"),
            ("user-agent", "smial-task30-a16p/1.0"),
        ),
        body=body,
        safe_query_keys=(),
    )


def _closed_json(body: bytes) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate key")
            value[key] = item
        return value

    try:
        return json.loads(body, object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None


def _safe_root(repository_root: Path, raw_root: Path, *, logical_root: str) -> None:
    _require(repository_root.is_absolute(), "REPOSITORY_ROOT_ABSOLUTE_REQUIRED")
    _require(raw_root.is_absolute(), "RAW_ROOT_ABSOLUTE_REQUIRED")
    expected = repository_root / Path(logical_root)
    _require(raw_root.resolve(strict=False) == expected.resolve(strict=False), "RAW_ROOT_DRIFT")
    current = repository_root
    for part in Path(logical_root).parts:
        current = current / part
        if current.exists():
            _require(not current.is_symlink(), "RAW_ROOT_SYMLINK_FORBIDDEN")


def execute_pool_activity_attempt(
    config: Mapping[str, Any],
    *,
    authority_phrase: str,
    execution_profile: str = "v1",
    repository_root: Path,
    raw_root: Path,
    route_preflight: Callable[[], Mapping[str, object]],
    credential_loader: Callable[[str], str],
    http_exchange: Callable[..., HttpCapture],
    clock: Callable[[], datetime],
    nonce_factory: Callable[[], str],
) -> dict[str, object]:
    """Execute and retain exactly one Helius RPC request without retry."""

    evaluate_pool_activity_policy(config)
    _require(execution_profile in {"v1", "v2"}, "EXECUTION_PROFILE_INVALID")
    expected_authority = AUTHORITY_PHRASE if execution_profile == "v1" else AUTHORITY_PHRASE_V2
    logical_root = LOGICAL_ROOT if execution_profile == "v1" else LOGICAL_ROOT_V2
    _require(authority_phrase == expected_authority, "OWNER_AUTHORITY_MISMATCH")
    _safe_root(repository_root, raw_root, logical_root=logical_root)
    preflight = route_preflight()
    _require(
        isinstance(preflight, Mapping)
        and set(preflight) == {"dns_resolved", "tcp_443"}
        and preflight.get("dns_resolved") is True
        and preflight.get("tcp_443") is True,
        "ROUTE_PREFLIGHT_FAILED_NO_ATTEMPT",
    )
    if raw_root.exists():
        _require(raw_root.is_dir(), "RAW_ROOT_NOT_DIRECTORY")
        _require(not any(raw_root.glob("run=*")), "PRIOR_ATTEMPT_REQUIRES_NEW_GATE")

    started_at = clock()
    nonce = nonce_factory()
    _require(type(nonce) is str and _NONCE_RE.fullmatch(nonce) is not None, "NONCE_INVALID")
    run_id = f"{started_at.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}-{nonce}"
    run_root = raw_root / f"run={run_id}"
    try:
        raw_root.mkdir(parents=True, exist_ok=True)
        run_root.mkdir(exist_ok=False)
    except OSError as exc:
        raise PoolActivityRuntimeError("ATTEMPT_ROOT_CREATE_FAILED") from exc

    request_body = _canonical_json(build_pool_activity_request(config))
    planned_request = {
        "body_bytes": len(request_body),
        "body_sha256": hashlib.sha256(request_body).hexdigest(),
        "host": _HELIUS_HOST,
        "method": "POST",
        "path": "/",
        "provider": "HELIUS",
        "query_keys": [],
        "request_id": _REQUEST_ID,
        "transport": "HTTP",
    }
    intent = {
        "schema": "smial.task30.pool-activity-discriminator-runtime-intent",
        "schema_version": "1.0",
        "run_id": run_id,
        "started_at": _utc_text(started_at),
        "authority_sha256": hashlib.sha256(authority_phrase.encode("utf-8")).hexdigest(),
        "request_count_planned": 1,
        "retry": False,
        "fallback": False,
        "transaction_followups": 0,
        "planned_request": planned_request,
    }
    intent_body = _canonical_json(intent)
    _publish_new(run_root / "intent.json", intent_body)

    credential = _validate_secret(credential_loader("HELIUS_API_KEY"))
    request = _bind_request(config, credential)
    _require(request.safe_receipt() == planned_request, "REQUEST_RECEIPT_DRIFT")

    capture = http_exchange(request, max_response_bytes=MAX_RESPONSE_BYTES)
    _require(type(capture) is HttpCapture, "HTTP_CAPTURE_TYPE_INVALID")
    observed_at = clock()
    raw_body = capture.body
    _publish_new(run_root / "raw_response.json", raw_body)

    raw_manifest = {
        "schema": "smial.task30.pool-activity-discriminator-raw-manifest",
        "schema_version": "1.0",
        "run_id": run_id,
        "retention_class": "A4",
        "raw_objects": [
            {
                "path": "intent.json",
                "bytes": len(intent_body),
                "sha256": hashlib.sha256(intent_body).hexdigest(),
                "observed_at": intent["started_at"],
            },
            {
                "path": "raw_response.json",
                "bytes": len(raw_body),
                "sha256": hashlib.sha256(raw_body).hexdigest(),
                "observed_at": _utc_text(observed_at),
            },
        ],
    }
    manifest_body = _canonical_json(raw_manifest)
    _publish_new(run_root / "raw_manifest.json", manifest_body)

    parsed = (
        _closed_json(raw_body)
        if capture.terminal_class == "SUCCESS" and capture.status_code == 200
        else None
    )
    classification = classify_pool_activity_response(config, parsed)
    receipt = {
        "schema": "smial.task30.pool-activity-discriminator-runtime-receipt",
        "schema_version": "1.0",
        "run_id": run_id,
        "logical_run_root": f"{logical_root}/run={run_id}",
        "terminal_at": _utc_text(clock()),
        "request_count": 1,
        "estimated_credits": 1,
        "http_status": capture.status_code,
        "transport_terminal_class": capture.terminal_class,
        "transport_error_class": capture.error_class,
        "raw_retention": "A4_EXACT_RETAINED",
        "raw_manifest": {
            "path": "raw_manifest.json",
            "bytes": len(manifest_body),
            "sha256": hashlib.sha256(manifest_body).hexdigest(),
        },
        **classification,
    }
    _publish_new(run_root / "terminal_receipt.json", _canonical_json(receipt))
    return receipt
