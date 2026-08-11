"""Fail-closed pure policy and request planning for TASK-30 A11C."""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from typing import Any
from urllib.parse import urlencode
from urllib.parse import parse_qs, urlsplit


class TwoSlotShakedownRuntimeError(ValueError):
    """Raised before an unsafe plan can reach transport."""


EXPECTED_POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
EXPECTED_OFFSETS = [0, 15, 30, 60]
INTERVAL_SECONDS = 900
AUTHORITY_PREFIX = "T30-A11C_TWO_SLOT_SHAKEDOWN_EXECUTION_V1"
EXPECTED_AUTHORITY_KEYS = (
    "pool",
    "slot_starts_utc",
    "monitoring_owner",
    "max_gets",
    "retention",
    "retry",
    "fallback",
)
EXPECTED_ZERO_AUTHORITY_FIELDS = {
    "provider_api_rpc_wss_calls",
    "credential_use",
    "raw_data_writes",
    "scheduler_or_background_processes",
    "r2_r3_access",
    "wallet_signer_transaction_actions",
    "cash_spend_usd_cents",
    "task30_trial_or_acceptance_actions",
}
EXPECTED_NON_CLAIM_FIELDS = {
    "pit_admissible",
    "h07_h01_evidence",
    "task30_trial",
    "execution",
    "settlement",
    "pnl",
    "numeric_netreturn",
    "provider_selected",
    "external_capture_authorized",
    "twenty_four_hour_capture_authorized",
    "missing_is_zero_or_flat",
}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise TwoSlotShakedownRuntimeError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _exact(container: Mapping[str, Any], key: str, expected: object, code: str) -> None:
    _require(container.get(key) == expected, code)


def validate_runtime_policy(policy: Mapping[str, Any]) -> dict[str, object]:
    """Validate the tracked A11C policy without file, clock or network I/O."""

    _exact(policy, "schema", "smial.task30.two-slot-live-shakedown-runtime", "SCHEMA_INVALID")
    _exact(policy, "schema_version", "1.0", "SCHEMA_VERSION_INVALID")
    _exact(policy, "task_id", "TASK-30", "TASK_ID_INVALID")
    _exact(policy, "atom_id", "T30-A11C_TWO_SLOT_SHAKEDOWN_RUNTIME_HARNESS_V1", "ATOM_ID_INVALID")
    _exact(policy, "project_sources_disposition", "NO_CHANGE", "SOURCES_CHANGE_FORBIDDEN")

    frozen = _mapping(policy.get("frozen_candidate"), "FROZEN_CANDIDATE_REQUIRED")
    _exact(frozen, "provider", "GECKOTERMINAL_PUBLIC_KEYLESS", "PROVIDER_INVALID")
    _exact(frozen, "network", "solana", "NETWORK_INVALID")
    _exact(frozen, "pool_address", EXPECTED_POOL, "POOL_INVALID")
    _exact(frozen, "base_url", "https://api.geckoterminal.com/api/v2", "BASE_URL_INVALID")
    _exact(frozen, "path_template", "/networks/solana/pools/{pool}/ohlcv/minute", "PATH_INVALID")

    request = _mapping(policy.get("request"), "REQUEST_REQUIRED")
    for key, expected in {
        "method": "GET", "aggregate": "15", "currency": "usd", "token": "base",
        "include_empty_intervals": "false", "limit": "1", "request_timeout_seconds": 20,
        "response_bytes_max": 4194304, "retry": False, "fallback": False, "credentials": False,
    }.items():
        _exact(request, key, expected, "REQUEST_POLICY_INVALID")

    shape = _mapping(policy.get("shakedown_shape"), "SHAKEDOWN_SHAPE_REQUIRED")
    for key, expected in {
        "interval_seconds": INTERVAL_SECONDS, "offset_seconds": EXPECTED_OFFSETS,
        "requests_per_slot_max": 4, "requests_total_max": 8,
        "late_offset_seconds_max": 15, "scheduler": False,
    }.items():
        _exact(shape, key, expected, "SHAKEDOWN_POLICY_INVALID")

    retention = _mapping(policy.get("retention"), "RETENTION_REQUIRED")
    for key, expected in {
        "policy": "A4", "raw_json_outside_git": True,
        "raw_root_relative": "local/task30_two_slot_live_shakedown",
        "immediate_manifest_after_every_response": True,
        "immediate_health_receipt_after_every_response": True,
    }.items():
        _exact(retention, key, expected, "RETENTION_POLICY_INVALID")

    authority = _mapping(policy.get("authority"), "AUTHORITY_REQUIRED")
    _require(set(authority) == EXPECTED_ZERO_AUTHORITY_FIELDS, "AUTHORITY_FIELDS_INVALID")
    _require(all(value == 0 and not isinstance(value, bool) for value in authority.values()), "AUTHORITY_INVALID")
    non_claims = _mapping(policy.get("non_claims"), "NON_CLAIMS_REQUIRED")
    _require(set(non_claims) == EXPECTED_NON_CLAIM_FIELDS, "NON_CLAIMS_FIELDS_INVALID")
    _require(all(value is False for value in non_claims.values()), "NON_CLAIMS_INVALID")

    return {"policy_validated": True, "pool_address": EXPECTED_POOL, "interval_seconds": INTERVAL_SECONDS}


def _parse_utc_timestamp(value: str) -> int:
    _require(value.endswith("Z"), "AUTHORITY_TIMESTAMP_NOT_UTC")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TwoSlotShakedownRuntimeError("AUTHORITY_TIMESTAMP_INVALID") from exc
    _require(parsed.tzinfo == UTC, "AUTHORITY_TIMESTAMP_NOT_UTC")
    return int(parsed.timestamp())


def parse_execution_authority(text: str) -> dict[str, object]:
    """Parse the only non-secret owner phrase that can unlock future execution."""

    _require(isinstance(text, str) and text, "AUTHORITY_TEXT_REQUIRED")
    parts = text.split(";")
    _require(parts[0] == AUTHORITY_PREFIX and len(parts) == len(EXPECTED_AUTHORITY_KEYS) + 1, "AUTHORITY_PREFIX_INVALID")
    terms: dict[str, str] = {}
    for part in parts[1:]:
        key, separator, value = part.partition("=")
        _require(separator == "=" and key in EXPECTED_AUTHORITY_KEYS and key not in terms and value, "AUTHORITY_TERM_INVALID")
        terms[key] = value
    _require(tuple(terms) == EXPECTED_AUTHORITY_KEYS, "AUTHORITY_TERM_ORDER_INVALID")
    _require(terms["pool"] == EXPECTED_POOL, "AUTHORITY_POOL_INVALID")
    _require(terms["monitoring_owner"] == "LOCAL_WORK_CODEX_FOREGROUND", "AUTHORITY_MONITORING_OWNER_INVALID")
    _require(terms["max_gets"] == "8", "AUTHORITY_CAP_INVALID")
    _require(terms["retention"] == "A4", "AUTHORITY_RETENTION_INVALID")
    _require(terms["retry"] == "false" and terms["fallback"] == "false", "AUTHORITY_RECOVERY_INVALID")
    slots = terms["slot_starts_utc"].split(",")
    _require(len(slots) == 2, "AUTHORITY_SLOT_COUNT_INVALID")
    epochs = [_parse_utc_timestamp(value) for value in slots]
    _require(epochs[0] % INTERVAL_SECONDS == 0 and epochs[1] - epochs[0] == INTERVAL_SECONDS, "AUTHORITY_SLOT_SEQUENCE_INVALID")
    return {
        "text": text,
        "fingerprint_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "pool": terms["pool"],
        "slot_starts_utc": slots,
        "slot_starts_epoch": epochs,
        "monitoring_owner": terms["monitoring_owner"],
        "max_gets": 8,
        "retention": "A4",
        "retry": False,
        "fallback": False,
    }


def build_slot_plan(
    policy: Mapping[str, Any], authority: Mapping[str, object], *, slot_index: int, now_epoch: int
) -> list[dict[str, object]]:
    """Return exactly four allowed future GET descriptions for one foreground slot."""

    validate_runtime_policy(policy)
    _require(slot_index in (1, 2), "SLOT_INDEX_INVALID")
    _require(isinstance(now_epoch, int) and not isinstance(now_epoch, bool), "RUN_TIME_INVALID")
    _require(authority.get("pool") == EXPECTED_POOL and authority.get("max_gets") == 8, "AUTHORITY_BINDING_INVALID")
    _require(authority.get("monitoring_owner") == "LOCAL_WORK_CODEX_FOREGROUND", "AUTHORITY_MONITORING_OWNER_INVALID")
    _require(authority.get("retention") == "A4" and authority.get("retry") is False and authority.get("fallback") is False, "AUTHORITY_RECOVERY_INVALID")
    epochs = authority.get("slot_starts_epoch")
    _require(isinstance(epochs, list) and len(epochs) == 2 and all(isinstance(value, int) for value in epochs), "AUTHORITY_SLOT_SEQUENCE_INVALID")
    slot_start = epochs[slot_index - 1]
    slot_end = slot_start + INTERVAL_SECONDS
    _require(now_epoch <= slot_end, "SLOT_BOUNDARY_ALREADY_MISSED")

    frozen = _mapping(policy["frozen_candidate"], "FROZEN_CANDIDATE_REQUIRED")
    request = _mapping(policy["request"], "REQUEST_REQUIRED")
    query = {
        "aggregate": request["aggregate"], "currency": request["currency"], "token": request["token"],
        "include_empty_intervals": request["include_empty_intervals"], "limit": request["limit"],
        "before_timestamp": str(slot_end),
    }
    path = str(frozen["path_template"]).replace("{pool}", EXPECTED_POOL)
    url = f"{frozen['base_url']}{path}?{urlencode(query)}"
    return [
        {
            "ordinal": ordinal,
            "slot_index": slot_index,
            "slot_start": slot_start,
            "slot_end": slot_end,
            "offset_seconds": offset,
            "scheduled_epoch": slot_end + offset,
            "expected_interval_start": slot_start,
            "method": "GET",
            "host": "api.geckoterminal.com",
            "path": path,
            "query": query,
            "before_timestamp": slot_end,
            "url": url,
        }
        for ordinal, offset in enumerate(EXPECTED_OFFSETS, start=1)
    ]


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Return a deterministic hashable JSON representation for receipts."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_: object, **__: object) -> urllib.request.Request:
        raise TwoSlotShakedownRuntimeError("REDIRECT_FORBIDDEN")


class BoundedGeckoTransport:
    """Single-route, four-call maximum transport for a future authorized slot."""

    _SAFE_HEADERS = frozenset({"content-length", "content-type", "date", "retry-after"})

    def __init__(self, *, response_bytes_max: int, timeout_seconds: int, opener: object | None = None) -> None:
        _require(response_bytes_max == 4194304, "RESPONSE_CAP_INVALID")
        _require(timeout_seconds == 20, "REQUEST_TIMEOUT_INVALID")
        self._response_bytes_max = response_bytes_max
        self._timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.build_opener(_NoRedirect())
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    def _validate_request(self, request: Mapping[str, object]) -> str:
        _require(self._calls < 4, "REQUEST_CAP_EXCEEDED")
        _require(request.get("method") == "GET", "REQUEST_METHOD_INVALID")
        url = request.get("url")
        _require(isinstance(url, str), "REQUEST_URL_INVALID")
        parts = urlsplit(url)
        _require(parts.scheme == "https" and parts.hostname == "api.geckoterminal.com" and parts.port is None, "REQUEST_HOST_INVALID")
        _require(parts.path == f"/api/v2/networks/solana/pools/{EXPECTED_POOL}/ohlcv/minute", "REQUEST_PATH_INVALID")
        expected_query = {
            "aggregate": ["15"], "currency": ["usd"], "token": ["base"],
            "include_empty_intervals": ["false"], "limit": ["1"],
            "before_timestamp": [str(request.get("before_timestamp"))],
        }
        _require(parse_qs(parts.query, keep_blank_values=True) == expected_query, "REQUEST_QUERY_INVALID")
        return url

    def __call__(self, request: Mapping[str, object]) -> Mapping[str, object]:
        url = self._validate_request(request)
        self._calls += 1
        outgoing = urllib.request.Request(url, method="GET", headers={"Accept": "application/json", "User-Agent": "solana-alpha-lab-task30-a11c/1.0"})
        body = b""
        status: int | None = None
        headers: Mapping[str, str] = {}
        try:
            with self._opener.open(outgoing, timeout=self._timeout_seconds) as response:  # type: ignore[union-attr]
                status = int(response.status)
                body = response.read(self._response_bytes_max + 1)
                headers = {str(key).lower(): str(value) for key, value in response.headers.items() if str(key).lower() in self._SAFE_HEADERS}
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            body = exc.read(self._response_bytes_max + 1)
            headers = {str(key).lower(): str(value) for key, value in exc.headers.items() if str(key).lower() in self._SAFE_HEADERS}
        except (urllib.error.URLError, ssl.SSLError, socket.gaierror, socket.timeout, TimeoutError, OSError) as exc:
            raise RuntimeError("TRANSPORT_FAILURE") from exc
        _require(status is not None, "TRANSPORT_STATUS_INVALID")
        _require(len(body) <= self._response_bytes_max, "RESPONSE_BYTE_CAP_EXCEEDED")
        return {"http_status": status, "safe_response_headers": headers, "body": body}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _claims() -> dict[str, bool]:
    return {
        "pit_admissible": False,
        "h07_h01_evidence": False,
        "task30_trial": False,
        "execution": False,
        "settlement": False,
        "pnl": False,
        "numeric_netreturn": False,
        "provider_selected": False,
        "external_capture_authorized": False,
        "twenty_four_hour_capture_authorized": False,
        "missing_is_zero_or_flat": False,
    }


def _clock_epoch(now: Callable[[], int]) -> int:
    value = now()
    _require(isinstance(value, int) and not isinstance(value, bool), "CLOCK_INVALID")
    return value


def _write_exclusive(path: Path, body: bytes) -> str:
    with path.open("xb") as handle:
        handle.write(body)
    return _sha256(body)


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> str:
    return _write_exclusive(path, canonical_json_bytes(value) + b"\n")


def _relative_file(root: Path, value: Path) -> str:
    return value.relative_to(root).as_posix()


def _capture_parts(capture: object) -> tuple[int, Mapping[str, object], bytes]:
    value = _mapping(capture, "TRANSPORT_CAPTURE_INVALID")
    http_status = value.get("http_status")
    headers = value.get("safe_response_headers")
    body = value.get("body")
    _require(isinstance(http_status, int) and not isinstance(http_status, bool), "TRANSPORT_STATUS_INVALID")
    _require(isinstance(headers, Mapping), "TRANSPORT_HEADERS_INVALID")
    _require(isinstance(body, bytes), "TRANSPORT_BODY_INVALID")
    return http_status, headers, body


def _classify_capture(http_status: int, body: bytes, expected_interval_start: int) -> str:
    if http_status != 200:
        return "TYPED_GAP"
    try:
        parsed = json.loads(body.decode("utf-8"))
        data = _mapping(parsed, "RESPONSE_JSON_INVALID")
        attributes = _mapping(_mapping(data.get("data"), "RESPONSE_DATA_INVALID").get("attributes"), "RESPONSE_ATTRIBUTES_INVALID")
        rows = attributes.get("ohlcv_list")
        _require(isinstance(rows, list) and len(rows) == 1, "RESPONSE_ROWS_INVALID")
        row = rows[0]
        _require(isinstance(row, list) and bool(row), "RESPONSE_ROW_INVALID")
        observed_interval_start = row[0]
        _require(isinstance(observed_interval_start, int) and not isinstance(observed_interval_start, bool), "RESPONSE_INTERVAL_INVALID")
    except (UnicodeDecodeError, json.JSONDecodeError, TwoSlotShakedownRuntimeError):
        return "TYPED_GAP"
    return "RETAINED_EXPECTED_INTERVAL" if observed_interval_start == expected_interval_start else "TYPED_GAP"


def _terminal_receipt(
    *,
    authority: Mapping[str, object],
    slot_index: int,
    plan: list[dict[str, object]],
    terminal_state: str,
    stop_reason: str | None,
    checkpoints: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema": "smial.task30.two-slot-live-shakedown.slot-receipt",
        "schema_version": "1.0",
        "authority_fingerprint_sha256": authority["fingerprint_sha256"],
        "slot_index": slot_index,
        "slot_start": plan[0]["slot_start"],
        "slot_end": plan[0]["slot_end"],
        "terminal_state": terminal_state,
        "stop_reason": stop_reason,
        "requests_planned": len(plan),
        "requests_completed": len(checkpoints),
        "checkpoint_artifacts": checkpoints,
        "claims": _claims(),
    }


def _try_write_stop_receipt(
    root: Path,
    receipt: Mapping[str, Any],
) -> dict[str, object]:
    result = dict(receipt)
    try:
        root.mkdir(parents=True, exist_ok=True)
        _write_json_exclusive(root / "slot_receipt_v1.json", result)
        result["receipt_written"] = True
    except OSError:
        result["receipt_written"] = False
    return result


def _path_from_receipt_root(root: Path, value: object, code: str) -> Path:
    _require(isinstance(value, str) and value, code)
    candidate = (root / value).resolve()
    _require(candidate.is_relative_to(root.resolve()), code)
    return candidate


def verify_prior_slot_receipt(path: Path, authority: Mapping[str, object]) -> dict[str, object]:
    """Verify the immutable healthy first-slot chain before slot two opens transport."""

    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TwoSlotShakedownRuntimeError("PRIOR_RECEIPT_UNREADABLE") from exc
    value = _mapping(receipt, "PRIOR_RECEIPT_INVALID")
    _require(value.get("schema") == "smial.task30.two-slot-live-shakedown.slot-receipt", "PRIOR_RECEIPT_SCHEMA_INVALID")
    _require(value.get("slot_index") == 1, "PRIOR_RECEIPT_SLOT_INVALID")
    _require(value.get("terminal_state") == "SLOT_TECHNICAL_HEALTHY", "PRIOR_RECEIPT_NOT_HEALTHY")
    _require(value.get("authority_fingerprint_sha256") == authority.get("fingerprint_sha256"), "PRIOR_RECEIPT_AUTHORITY_INVALID")
    checkpoints = value.get("checkpoint_artifacts")
    _require(isinstance(checkpoints, list) and len(checkpoints) == 4, "PRIOR_RECEIPT_CHECKPOINTS_INVALID")
    root = path.parent.resolve()
    for ordinal, checkpoint in enumerate(checkpoints, start=1):
        item = _mapping(checkpoint, "PRIOR_RECEIPT_CHECKPOINT_INVALID")
        _require(item.get("ordinal") == ordinal, "PRIOR_RECEIPT_ORDINAL_INVALID")
        raw_path = _path_from_receipt_root(root, item.get("raw_path"), "PRIOR_RECEIPT_RAW_PATH_INVALID")
        manifest_path = _path_from_receipt_root(root, item.get("manifest_path"), "PRIOR_RECEIPT_MANIFEST_PATH_INVALID")
        health_path = _path_from_receipt_root(root, item.get("health_path"), "PRIOR_RECEIPT_HEALTH_PATH_INVALID")
        try:
            raw_bytes = raw_path.read_bytes()
            manifest_bytes = manifest_path.read_bytes()
            manifest = json.loads(manifest_bytes.decode("utf-8"))
            health_bytes = health_path.read_bytes()
            health = json.loads(health_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TwoSlotShakedownRuntimeError("PRIOR_RECEIPT_CHAIN_UNREADABLE") from exc
        _require(_sha256(raw_bytes) == item.get("raw_sha256"), "PRIOR_RECEIPT_RAW_HASH_INVALID")
        _require(_sha256(manifest_bytes) == item.get("manifest_sha256"), "PRIOR_RECEIPT_MANIFEST_HASH_INVALID")
        manifest_value = _mapping(manifest, "PRIOR_RECEIPT_MANIFEST_INVALID")
        _require(manifest_value.get("schema") == "smial.task30.two-slot-live-shakedown.raw-manifest", "PRIOR_RECEIPT_MANIFEST_SCHEMA_INVALID")
        _require(manifest_value.get("ordinal") == ordinal, "PRIOR_RECEIPT_MANIFEST_ORDINAL_INVALID")
        raw_files = manifest_value.get("raw_files")
        _require(isinstance(raw_files, list) and len(raw_files) == ordinal, "PRIOR_RECEIPT_MANIFEST_CONTENTS_INVALID")
        for raw_ordinal, raw_file in enumerate(raw_files, start=1):
            raw_file_value = _mapping(raw_file, "PRIOR_RECEIPT_MANIFEST_ENTRY_INVALID")
            _require(raw_file_value.get("ordinal") == raw_ordinal, "PRIOR_RECEIPT_MANIFEST_ENTRY_ORDINAL_INVALID")
            listed_path = _path_from_receipt_root(root, raw_file_value.get("path"), "PRIOR_RECEIPT_MANIFEST_ENTRY_PATH_INVALID")
            try:
                listed_bytes = listed_path.read_bytes()
            except OSError as exc:
                raise TwoSlotShakedownRuntimeError("PRIOR_RECEIPT_MANIFEST_ENTRY_UNREADABLE") from exc
            _require(_sha256(listed_bytes) == raw_file_value.get("sha256"), "PRIOR_RECEIPT_MANIFEST_ENTRY_HASH_INVALID")
        last_raw_file = _mapping(raw_files[-1], "PRIOR_RECEIPT_MANIFEST_ENTRY_INVALID")
        _require(last_raw_file.get("path") == item.get("raw_path"), "PRIOR_RECEIPT_MANIFEST_CURRENT_PATH_INVALID")
        _require(last_raw_file.get("sha256") == item.get("raw_sha256"), "PRIOR_RECEIPT_MANIFEST_CURRENT_HASH_INVALID")
        _require(_sha256(health_bytes) == item.get("health_sha256"), "PRIOR_RECEIPT_HEALTH_HASH_INVALID")
        health_value = _mapping(health, "PRIOR_RECEIPT_HEALTH_INVALID")
        _require(health_value.get("raw_sha256") == item.get("raw_sha256"), "PRIOR_RECEIPT_HEALTH_RAW_INVALID")
        _require(health_value.get("raw_manifest_sha256") == item.get("manifest_sha256"), "PRIOR_RECEIPT_HEALTH_MANIFEST_INVALID")
        _require(health_value.get("classification") == item.get("classification"), "PRIOR_RECEIPT_HEALTH_CLASSIFICATION_INVALID")
    return dict(value)


def run_slot(
    policy: Mapping[str, Any],
    authority: Mapping[str, object],
    *,
    slot_index: int,
    raw_root: Path,
    transport: Callable[[Mapping[str, object]], Mapping[str, object]],
    now: Callable[[], int],
    sleep: Callable[[float], None],
    prior_receipt: Path | None = None,
    monitoring: Callable[[], bool] = lambda: True,
) -> dict[str, object]:
    """Run exactly one pre-authorized slot using only the injected transport."""

    if slot_index == 1:
        _require(prior_receipt is None, "PRIOR_RECEIPT_UNEXPECTED")
    else:
        _require(prior_receipt is not None, "PRIOR_RECEIPT_REQUIRED")
        verify_prior_slot_receipt(prior_receipt, authority)

    initial_epoch = _clock_epoch(now)
    slot_epochs = authority.get("slot_starts_epoch")
    _require(isinstance(slot_epochs, list) and len(slot_epochs) == 2 and isinstance(slot_epochs[slot_index - 1], int), "AUTHORITY_SLOT_SEQUENCE_INVALID")
    slot_end = slot_epochs[slot_index - 1] + INTERVAL_SECONDS
    plan = build_slot_plan(policy, authority, slot_index=slot_index, now_epoch=min(initial_epoch, slot_end))
    root = raw_root.resolve()
    checkpoints: list[dict[str, object]] = []
    raw_entries: list[dict[str, object]] = []
    try:
        root.mkdir(parents=True, exist_ok=True)
        raw_directory = root / "raw"
        raw_directory.mkdir(exist_ok=False)
    except OSError as exc:
        raise TwoSlotShakedownRuntimeError("RAW_ROOT_INITIALIZATION_FAILED") from exc

    late_offset_seconds_max = 15
    for request in plan:
        if not monitoring():
            receipt = _terminal_receipt(authority=authority, slot_index=slot_index, plan=plan, terminal_state="STOP_RUN", stop_reason="MONITORING_LOST", checkpoints=checkpoints)
            return _try_write_stop_receipt(root, receipt)
        scheduled_epoch = request["scheduled_epoch"]
        _require(isinstance(scheduled_epoch, int), "SCHEDULE_INVALID")
        current_epoch = _clock_epoch(now)
        if current_epoch < scheduled_epoch:
            sleep(scheduled_epoch - current_epoch)
            current_epoch = _clock_epoch(now)
        if current_epoch > scheduled_epoch + late_offset_seconds_max:
            receipt = _terminal_receipt(authority=authority, slot_index=slot_index, plan=plan, terminal_state="STOP_RUN", stop_reason="LATE_OFFSET", checkpoints=checkpoints)
            return _try_write_stop_receipt(root, receipt)
        try:
            http_status, safe_headers, body = _capture_parts(transport(request))
        except (OSError, TimeoutError, ConnectionError, RuntimeError, TwoSlotShakedownRuntimeError) as exc:
            receipt = _terminal_receipt(authority=authority, slot_index=slot_index, plan=plan, terminal_state="STOP_RUN", stop_reason=f"TRANSPORT_ERROR:{type(exc).__name__}", checkpoints=checkpoints)
            return _try_write_stop_receipt(root, receipt)

        ordinal = request["ordinal"]
        _require(isinstance(ordinal, int), "ORDINAL_INVALID")
        raw_path = raw_directory / f"response_{ordinal:02d}.json"
        try:
            raw_sha256 = _write_exclusive(raw_path, body)
            raw_entries.append({"ordinal": ordinal, "path": _relative_file(root, raw_path), "sha256": raw_sha256, "bytes": len(body)})
            manifest_path = root / f"raw_manifest_{ordinal:02d}.json"
            manifest_sha256 = _write_json_exclusive(manifest_path, {"schema": "smial.task30.two-slot-live-shakedown.raw-manifest", "schema_version": "1.0", "ordinal": ordinal, "raw_files": raw_entries})
            classification = _classify_capture(http_status, body, int(request["expected_interval_start"]))
            health_path = root / f"health_receipt_{ordinal:02d}.json"
            health_sha256 = _write_json_exclusive(health_path, {"schema": "smial.task30.two-slot-live-shakedown.health-receipt", "schema_version": "1.0", "ordinal": ordinal, "http_status": http_status, "safe_response_headers": dict(safe_headers), "raw_sha256": raw_sha256, "raw_manifest_sha256": manifest_sha256, "classification": classification})
            checkpoints.append({"ordinal": ordinal, "raw_path": _relative_file(root, raw_path), "raw_sha256": raw_sha256, "manifest_path": _relative_file(root, manifest_path), "manifest_sha256": manifest_sha256, "health_path": _relative_file(root, health_path), "health_sha256": health_sha256, "classification": classification})
        except OSError:
            receipt = _terminal_receipt(authority=authority, slot_index=slot_index, plan=plan, terminal_state="STOP_RUN", stop_reason="RECEIPT_WRITE_FAILED", checkpoints=checkpoints)
            return _try_write_stop_receipt(root, receipt)

    terminal_state = "SLOT_TECHNICAL_HEALTHY" if all(item["classification"] == "RETAINED_EXPECTED_INTERVAL" for item in checkpoints) else "SLOT_TECHNICAL_INCONCLUSIVE"
    receipt = _terminal_receipt(authority=authority, slot_index=slot_index, plan=plan, terminal_state=terminal_state, stop_reason=None, checkpoints=checkpoints)
    try:
        _write_json_exclusive(root / "slot_receipt_v1.json", receipt)
    except OSError as exc:
        raise TwoSlotShakedownRuntimeError("RECEIPT_WRITE_FAILED") from exc
    return receipt
