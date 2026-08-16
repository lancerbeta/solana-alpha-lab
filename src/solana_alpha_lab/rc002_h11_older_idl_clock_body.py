"""Offline trial: consume retained H11 clock bodies without trailing quote_mint.

No provider calls. Does not mutate the pinned TASK-08 decoder.
TASK-40/39 science receipts are not rewritten.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from solana_alpha_lab.pump_event_decoder import (
    MAX_EVENT_PAYLOAD_BYTES,
    PROGRAM_DATA_PREFIX,
    EventSchema,
    PumpEventDecodeError,
    PumpEventPlan,
    decode_pump_program_data,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.rc002_h11_truncation_vs_absence import (
    EXPECTED_PAGE_SHA256,
    IDL_RELATIVE,
    RETAINED_A4_RELATIVE,
    TASK40_RUNTIME_RELATIVE,
)

ATOM_ID = "RC002-H11-OLDER-IDL-CLOCK-BODY-OFFLINE-V1"
CANDIDATE_ID = "DROP_TRAILING_QUOTE_MINT"
CLOCK_EVENTS = frozenset(
    {"CreateEvent", "CompleteEvent", "CompletePumpAmmMigrationEvent"}
)
LOG_TRUNCATED_MARKER = "Log truncated"
TERMINAL_OUTCOMES = (
    "LAYOUT_CONSUMED_WITHOUT_REMAINDER",
    "NO_CANDIDATE_LAYOUT_CONSUMES",
    "MIXED_CLOCK_BODIES_NOT_UNIFORM",
)

_INVOKE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) invoke \[([1-9][0-9]*)\]$"
)
_COMPLETE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) "
    r"(?:success|failed(?:: .*)?)$"
)


class OlderIdlScanError(ValueError):
    """A retained page or row cannot be classified fail-closed."""


class _AttributionAbort(Exception):
    """Stack identity is corrupt; remaining logs of this transaction are dropped."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OlderIdlScanError(code)
    return value


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _account_keys(row: Mapping[str, Any]) -> list[str]:
    transaction = dict(_mapping(row.get("transaction") or {}, "TRANSACTION_INVALID"))
    message = dict(_mapping(transaction.get("message") or {}, "MESSAGE_INVALID"))
    keys = message.get("accountKeys") or []
    if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes)):
        raise OlderIdlScanError("ACCOUNT_KEYS_INVALID")
    return [str(item) for item in keys]


def _event_payload(log_line: str) -> bytes | None:
    if not log_line.startswith(PROGRAM_DATA_PREFIX):
        return None
    encoded = log_line[len(PROGRAM_DATA_PREFIX) :]
    if not encoded or encoded.strip() != encoded:
        raise _AttributionAbort("program_data_base64_not_canonical")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _AttributionAbort("program_data_base64_invalid") from exc
    if len(payload) < 8:
        raise _AttributionAbort("program_data_discriminator_missing")
    if len(payload) > MAX_EVENT_PAYLOAD_BYTES:
        raise _AttributionAbort("program_data_payload_too_large")
    return payload


def candidate_drop_trailing_quote_mint(pinned: PumpEventPlan) -> PumpEventPlan:
    events: list[EventSchema] = []
    for event in pinned.events:
        if event.name in CLOCK_EVENTS:
            if not any(field.name == "quote_mint" for field in event.fields):
                raise OlderIdlScanError(f"PINNED_CLOCK_MISSING_QUOTE_MINT:{event.name}")
            fields = tuple(field for field in event.fields if field.name != "quote_mint")
        else:
            fields = event.fields
        events.append(
            EventSchema(
                name=event.name,
                discriminator=event.discriminator,
                lifecycle_state=event.lifecycle_state,
                fields=fields,
            )
        )
    return PumpEventPlan(
        fixture_sha256=pinned.fixture_sha256,
        source_blob_sha=pinned.source_blob_sha,
        program_id=pinned.program_id,
        defined_types=pinned.defined_types,
        events=tuple(events),
    )


def classify_transaction_clock_bodies(
    *,
    pinned: PumpEventPlan,
    candidate: PumpEventPlan,
    logs: Sequence[str],
    transaction_succeeded: bool,
) -> dict[str, Any]:
    stack: list[str] = []
    consumed_by_event: dict[str, int] = {}
    failed_by_event: dict[str, int] = {}
    payload_len_by_event: dict[str, list[int]] = {}
    fail_codes_by_event: dict[str, dict[str, int]] = {}
    attribution_errors: dict[str, int] = {}
    known = pinned.event_by_discriminator
    for line in logs:
        if line == LOG_TRUNCATED_MARKER:
            _bump(attribution_errors, "log_truncated_marker")
            break
        invoke = _INVOKE_RE.fullmatch(line)
        if invoke:
            program_id = invoke.group(1)
            depth = int(invoke.group(2))
            if depth != len(stack) + 1:
                _bump(attribution_errors, "program_invoke_depth_invalid")
                break
            stack.append(program_id)
            continue
        complete = _COMPLETE_RE.fullmatch(line)
        if complete:
            program_id = complete.group(1)
            if not stack or stack[-1] != program_id:
                _bump(attribution_errors, "program_completion_stack_mismatch")
                break
            stack.pop()
            continue
        try:
            payload = _event_payload(line)
        except _AttributionAbort as exc:
            _bump(attribution_errors, str(exc))
            break
        if payload is None:
            continue
        if not stack:
            _bump(attribution_errors, "program_data_without_invocation")
            break
        if stack[-1] != pinned.program_id:
            continue
        if not transaction_succeeded:
            continue
        schema = known.get(payload[:8])
        if schema is None or schema.name not in CLOCK_EVENTS:
            continue
        payload_len_by_event.setdefault(schema.name, []).append(len(payload))
        try:
            decoded = decode_pump_program_data(
                candidate,
                log_line=line,
                emitting_program_id=stack[-1],
                transaction_succeeded=True,
            )
        except PumpEventDecodeError as exc:
            _bump(failed_by_event, schema.name)
            codes = fail_codes_by_event.setdefault(schema.name, {})
            _bump(codes, str(exc))
            continue
        if decoded is None:
            _bump(attribution_errors, "successful_event_not_decoded")
            break
        _bump(consumed_by_event, decoded.event_name)
    return {
        "consumed_by_event": consumed_by_event,
        "failed_by_event": failed_by_event,
        "payload_len_by_event": payload_len_by_event,
        "fail_codes_by_event": fail_codes_by_event,
        "attribution_errors": attribution_errors,
    }


def _merge_int_map(left: dict[str, int], right: Mapping[str, int]) -> None:
    for key, value in right.items():
        left[key] = left.get(key, 0) + int(value)


def classify_clock_bodies(
    rows: Sequence[Mapping[str, Any]],
    *,
    pinned: PumpEventPlan,
    candidate: PumpEventPlan,
) -> dict[str, Any]:
    consumed_by_event: dict[str, int] = {}
    failed_by_event: dict[str, int] = {}
    payload_len_by_event: dict[str, list[int]] = {}
    fail_codes_by_event: dict[str, dict[str, int]] = {}
    attribution_errors: dict[str, int] = {}
    for row in rows:
        mapping = dict(_mapping(row, "ROW_INVALID"))
        _account_keys(mapping)
        meta = dict(_mapping(mapping.get("meta") or {}, "META_INVALID"))
        logs = meta.get("logMessages") or []
        if not isinstance(logs, Sequence) or isinstance(logs, (str, bytes)):
            raise OlderIdlScanError("LOG_MESSAGES_INVALID")
        classified = classify_transaction_clock_bodies(
            pinned=pinned,
            candidate=candidate,
            logs=[str(item) for item in logs],
            transaction_succeeded=meta.get("err") is None,
        )
        _merge_int_map(consumed_by_event, classified["consumed_by_event"])
        _merge_int_map(failed_by_event, classified["failed_by_event"])
        _merge_int_map(attribution_errors, classified["attribution_errors"])
        for name, lengths in classified["payload_len_by_event"].items():
            payload_len_by_event.setdefault(name, []).extend(lengths)
        for name, codes in classified["fail_codes_by_event"].items():
            bucket = fail_codes_by_event.setdefault(name, {})
            _merge_int_map(bucket, codes)
    result = {
        "candidate_id": CANDIDATE_ID,
        "consumed_by_event": consumed_by_event,
        "failed_by_event": failed_by_event,
        "payload_len_by_event": payload_len_by_event,
        "fail_codes_by_event": fail_codes_by_event,
        "attribution_errors": attribution_errors,
    }
    result["terminal"] = decide_terminal(result)
    return result


def decide_terminal(counts: Mapping[str, Any]) -> str:
    consumed = {
        name
        for name, value in dict(counts.get("consumed_by_event") or {}).items()
        if int(value) > 0
    }
    failed = {
        name
        for name, value in dict(counts.get("failed_by_event") or {}).items()
        if int(value) > 0
    }
    if consumed == CLOCK_EVENTS and not failed:
        return "LAYOUT_CONSUMED_WITHOUT_REMAINDER"
    if consumed and failed:
        return "MIXED_CLOCK_BODIES_NOT_UNIFORM"
    if consumed and not failed:
        return "MIXED_CLOCK_BODIES_NOT_UNIFORM"
    return "NO_CANDIDATE_LAYOUT_CONSUMES"


def _page_rows(body: bytes) -> list[dict[str, Any]]:
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OlderIdlScanError("RAW_PAGE_JSON_INVALID") from exc
    payload = dict(_mapping(document, "RAW_PAGE_ROOT_INVALID"))
    if "error" in payload:
        return []
    result = dict(_mapping(payload.get("result"), "RAW_PAGE_RESULT_INVALID"))
    rows = result.get("data")
    if not isinstance(rows, list):
        raise OlderIdlScanError("RAW_PAGE_DATA_INVALID")
    return [dict(_mapping(row, "ROW_INVALID")) for row in rows]


def _expected_page_bytes(repo_root: Path) -> dict[int, int]:
    receipt = json.loads((repo_root / TASK40_RUNTIME_RELATIVE).read_text(encoding="utf-8"))
    pages = receipt["scan"]["pages"]
    expected: dict[int, int] = {}
    for page in pages:
        expected[int(page["page_number"])] = int(page["response_bytes"])
    return expected


def scan_retained_a4_clock_bodies(
    repo_root: Path,
    *,
    pinned: PumpEventPlan | None = None,
) -> dict[str, Any]:
    loaded = pinned or load_pinned_pump_event_plan(repo_root / IDL_RELATIVE)
    candidate = candidate_drop_trailing_quote_mint(loaded)
    raw_root = repo_root / RETAINED_A4_RELATIVE
    if not raw_root.exists():
        return {
            "pages_status": "RETAINED_A4_PAGES_NOT_IN_CHECKOUT",
            "raw_root": RETAINED_A4_RELATIVE,
            "scan": None,
            "page_count": 0,
            "pages": [],
        }
    bodies = sorted(raw_root.rglob("raw_response.json"))
    if not bodies:
        return {
            "pages_status": "RETAINED_A4_PAGES_NOT_IN_CHECKOUT",
            "raw_root": RETAINED_A4_RELATIVE,
            "scan": None,
            "page_count": 0,
            "pages": [],
        }
    expected_bytes = _expected_page_bytes(repo_root)
    if set(expected_bytes) != set(EXPECTED_PAGE_SHA256):
        raise OlderIdlScanError("TASK40_PAGE_SET_DRIFT")
    observed_pages: dict[int, Path] = {}
    for path in bodies:
        match = re.search(r"page=(\d+)", path.as_posix())
        if match is None:
            raise OlderIdlScanError("RAW_PAGE_NUMBER_MISSING")
        observed_pages[int(match.group(1))] = path
    if set(observed_pages) != set(expected_bytes):
        raise OlderIdlScanError(
            f"RAW_PAGE_SET_INCOMPLETE:{sorted(observed_pages)}:{sorted(expected_bytes)}"
        )
    rows: list[dict[str, Any]] = []
    page_bindings: list[dict[str, Any]] = []
    for page_number in sorted(observed_pages):
        path = observed_pages[page_number]
        payload = path.read_bytes()
        observed = len(payload)
        expected = expected_bytes[page_number]
        digest = _sha256_bytes(payload)
        if expected != observed:
            raise OlderIdlScanError(
                f"RAW_PAGE_SIZE_DRIFT:{page_number}:{expected}:{observed}"
            )
        if digest != EXPECTED_PAGE_SHA256[page_number]:
            raise OlderIdlScanError(f"RAW_PAGE_HASH_DRIFT:{page_number}")
        page_bindings.append(
            {
                "page_number": page_number,
                "response_bytes": observed,
                "raw_sha256": digest,
            }
        )
        rows.extend(_page_rows(payload))
    scan = classify_clock_bodies(rows, pinned=loaded, candidate=candidate)
    return {
        "pages_status": "SCANNED",
        "raw_root": RETAINED_A4_RELATIVE,
        "page_count": len(bodies),
        "pages": page_bindings,
        "scan": scan,
    }
