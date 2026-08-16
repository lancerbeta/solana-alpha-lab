"""Offline discriminator: truncated Pump events vs absent H11 clocks.

No provider calls. TASK-40/39 science receipts are not rewritten.
Does not import another task's private log parser.
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
    PUMP_PROGRAM_ID,
    PumpEventDecodeError,
    PumpEventPlan,
    decode_pump_program_data,
    load_pinned_pump_event_plan,
)

ATOM_ID = "RC002-H11-TRUNCATION-VS-ABSENCE-OFFLINE-V1"
CLOCK_EVENTS = frozenset(
    {"CreateEvent", "CompleteEvent", "CompletePumpAmmMigrationEvent"}
)
RETAINED_A4_RELATIVE = "local/task40_rc002_h11_bonding_curve_pda_gta"
IDL_RELATIVE = "tests/fixtures/task08/pump_event_idl_subset_v1.json"
TASK40_RUNTIME_RELATIVE = (
    "docs/evidence/task40/a1_h11_bonding_curve_pda_gta_runtime_receipt_v1.json"
)
LOG_TRUNCATED_MARKER = "Log truncated"
TERMINAL_OUTCOMES = (
    "CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT",
    "CLOCK_EVENTS_PRESENT_AFTER_NON_CLOCK_TRUNCATION",
    "CLOCK_EVENTS_ABSENT_TRUNCATION_IS_NON_CLOCK",
    "CLOCK_EVENTS_ABSENT_NO_CLOCK_DISCRIMINATOR",
    "CLOCK_EVENTS_DECODED",
)
EXPECTED_PAGE_SHA256 = {
    0: "720705bf74fb052122236bf976afec405dfa749a99b676a90c6f95d1eca9710e",
    1: "3db601e6b24e1adae952b0672b6469272902654fc373511f60c049f3d680e79d",
    2: "70fb3accfa83fe8e002134f76f6cfea5850834dc12c87ee38a361e2406f63df2",
}

_INVOKE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) invoke \[([1-9][0-9]*)\]$"
)
_COMPLETE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) "
    r"(?:success|failed(?:: .*)?)$"
)


class TruncationScanError(ValueError):
    """A retained page or row cannot be classified fail-closed."""


class _AttributionAbort(Exception):
    """Stack identity is corrupt; remaining logs of this transaction are dropped."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TruncationScanError(code)
    return value


def _account_keys(row: Mapping[str, Any]) -> list[str]:
    transaction = dict(_mapping(row.get("transaction") or {}, "TRANSACTION_INVALID"))
    message = dict(_mapping(transaction.get("message") or {}, "MESSAGE_INVALID"))
    keys = message.get("accountKeys") or []
    if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes)):
        raise TruncationScanError("ACCOUNT_KEYS_INVALID")
    return [str(item) for item in keys]


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _event_discriminator(log_line: str) -> bytes | None:
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
    return payload[:8]


def _payload_len(log_line: str) -> int:
    encoded = log_line[len(PROGRAM_DATA_PREFIX) :]
    return len(base64.b64decode(encoded, validate=True))


def classify_transaction_logs(
    plan: PumpEventPlan,
    logs: Sequence[str],
    *,
    transaction_succeeded: bool,
) -> dict[str, Any]:
    stack: list[str] = []
    decoded_by_event: dict[str, int] = {}
    truncated_by_event: dict[str, int] = {}
    other_decode_by_event: dict[str, int] = {}
    unknown_discriminator = 0
    attribution_errors: dict[str, int] = {}
    saw_non_clock_body_failure = False
    clock_after_non_clock_truncation = 0
    clock_undecodable_payload_bytes: list[int] = []
    known = plan.event_by_discriminator
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
            discriminator = _event_discriminator(line)
        except _AttributionAbort as exc:
            _bump(attribution_errors, str(exc))
            break
        if discriminator is None:
            continue
        if not stack:
            _bump(attribution_errors, "program_data_without_invocation")
            break
        if stack[-1] != plan.program_id:
            continue
        if not transaction_succeeded:
            continue
        schema = known.get(discriminator)
        if schema is None:
            unknown_discriminator += 1
            continue
        try:
            event = decode_pump_program_data(
                plan,
                log_line=line,
                emitting_program_id=stack[-1],
                transaction_succeeded=True,
            )
        except PumpEventDecodeError as exc:
            code = str(exc)
            if code == "borsh_payload_truncated":
                _bump(truncated_by_event, schema.name)
            else:
                _bump(other_decode_by_event, f"{schema.name}:{code}")
            if schema.name in CLOCK_EVENTS:
                clock_undecodable_payload_bytes.append(_payload_len(line))
            else:
                saw_non_clock_body_failure = True
            continue
        if event is None:
            _bump(attribution_errors, "successful_event_not_decoded")
            break
        _bump(decoded_by_event, event.event_name)
        if event.event_name in CLOCK_EVENTS and saw_non_clock_body_failure:
            clock_after_non_clock_truncation += 1
    return {
        "decoded_by_event": decoded_by_event,
        "truncated_by_event": truncated_by_event,
        "other_decode_by_event": other_decode_by_event,
        "unknown_discriminator": unknown_discriminator,
        "attribution_errors": attribution_errors,
        "clock_after_non_clock_truncation": clock_after_non_clock_truncation,
        "clock_undecodable_payload_bytes": clock_undecodable_payload_bytes,
    }


def _merge_counts(left: dict[str, int], right: Mapping[str, int]) -> None:
    for key, value in right.items():
        left[key] = left.get(key, 0) + int(value)


def decide_terminal(counts: Mapping[str, int]) -> str:
    if int(counts.get("undecodable_clock") or 0) > 0:
        return "CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT"
    if int(counts.get("clock_after_non_clock_truncation") or 0) > 0:
        return "CLOCK_EVENTS_PRESENT_AFTER_NON_CLOCK_TRUNCATION"
    if int(counts.get("decoded_clock") or 0) > 0:
        return "CLOCK_EVENTS_DECODED"
    if int(counts.get("truncated_non_clock") or 0) > 0:
        return "CLOCK_EVENTS_ABSENT_TRUNCATION_IS_NON_CLOCK"
    return "CLOCK_EVENTS_ABSENT_NO_CLOCK_DISCRIMINATOR"


def classify_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    plan: PumpEventPlan,
) -> dict[str, Any]:
    decoded_by_event: dict[str, int] = {}
    truncated_by_event: dict[str, int] = {}
    other_decode_by_event: dict[str, int] = {}
    attribution_errors: dict[str, int] = {}
    unknown_discriminator = 0
    clock_after_non_clock_truncation = 0
    clock_undecodable_payload_bytes: list[int] = []
    pump_in_keys = 0
    for raw in rows:
        row = dict(_mapping(raw, "ROW_INVALID"))
        if PUMP_PROGRAM_ID in _account_keys(row):
            pump_in_keys += 1
        meta = dict(_mapping(row.get("meta") or {}, "META_INVALID"))
        logs = meta.get("logMessages") or []
        if not isinstance(logs, Sequence) or isinstance(logs, (str, bytes)):
            logs = []
        classified = classify_transaction_logs(
            plan,
            [str(item) for item in logs],
            transaction_succeeded=meta.get("err") is None,
        )
        _merge_counts(decoded_by_event, classified["decoded_by_event"])
        _merge_counts(truncated_by_event, classified["truncated_by_event"])
        _merge_counts(other_decode_by_event, classified["other_decode_by_event"])
        _merge_counts(attribution_errors, classified["attribution_errors"])
        unknown_discriminator += int(classified["unknown_discriminator"])
        clock_after_non_clock_truncation += int(
            classified["clock_after_non_clock_truncation"]
        )
        clock_undecodable_payload_bytes.extend(
            classified["clock_undecodable_payload_bytes"]
        )
    truncated_clock = sum(truncated_by_event.get(name, 0) for name in CLOCK_EVENTS)
    other_clock = sum(
        count
        for key, count in other_decode_by_event.items()
        if key.split(":", 1)[0] in CLOCK_EVENTS
    )
    decoded_clock = sum(decoded_by_event.get(name, 0) for name in CLOCK_EVENTS)
    truncated_non_clock = sum(
        count for name, count in truncated_by_event.items() if name not in CLOCK_EVENTS
    )
    decoded_non_clock = sum(
        count for name, count in decoded_by_event.items() if name not in CLOCK_EVENTS
    )
    undecodable_clock = truncated_clock + other_clock
    terminal = decide_terminal(
        {
            "undecodable_clock": undecodable_clock,
            "decoded_clock": decoded_clock,
            "truncated_non_clock": truncated_non_clock,
            "decoded_non_clock": decoded_non_clock,
            "clock_after_non_clock_truncation": clock_after_non_clock_truncation,
        }
    )
    return {
        "transaction_count": len(rows),
        "pump_program_in_account_keys": pump_in_keys,
        "decoded_by_event": decoded_by_event,
        "truncated_by_event": truncated_by_event,
        "other_decode_by_event": other_decode_by_event,
        "unknown_discriminator": unknown_discriminator,
        "attribution_errors": attribution_errors,
        "clock_after_non_clock_truncation": clock_after_non_clock_truncation,
        "clock_undecodable_payload_bytes": clock_undecodable_payload_bytes,
        "truncated_clock": truncated_clock,
        "undecodable_clock": undecodable_clock,
        "decoded_clock": decoded_clock,
        "truncated_non_clock": truncated_non_clock,
        "decoded_non_clock": decoded_non_clock,
        "terminal": terminal,
        "layout_claim": (
            "PINNED_DISCRIMINATOR_PRESENT_BODY_NOT_CONSUMED"
            if undecodable_clock
            else (
                "PINNED_CLOCK_LAYOUT_CONSUMED"
                if decoded_clock
                else "NO_PINNED_CLOCK_DISCRIMINATOR"
            )
        ),
    }


def _page_rows(body: bytes) -> list[dict[str, Any]]:
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TruncationScanError("RAW_PAGE_JSON_INVALID") from exc
    payload = dict(_mapping(document, "RAW_PAGE_ROOT_INVALID"))
    if "error" in payload:
        return []
    result = dict(_mapping(payload.get("result"), "RAW_PAGE_RESULT_INVALID"))
    rows = result.get("data")
    if not isinstance(rows, list):
        raise TruncationScanError("RAW_PAGE_DATA_INVALID")
    return [dict(_mapping(row, "ROW_INVALID")) for row in rows]


def _expected_page_bytes(repo_root: Path) -> dict[int, int]:
    receipt = json.loads((repo_root / TASK40_RUNTIME_RELATIVE).read_text(encoding="utf-8"))
    pages = receipt["scan"]["pages"]
    expected: dict[int, int] = {}
    for page in pages:
        expected[int(page["page_number"])] = int(page["response_bytes"])
    return expected


def scan_retained_a4_pages(
    repo_root: Path,
    *,
    plan: PumpEventPlan | None = None,
) -> dict[str, Any]:
    raw_root = repo_root / RETAINED_A4_RELATIVE
    loaded_plan = plan or load_pinned_pump_event_plan(repo_root / IDL_RELATIVE)
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
        raise TruncationScanError("TASK40_PAGE_SET_DRIFT")
    rows: list[dict[str, Any]] = []
    page_bindings: list[dict[str, Any]] = []
    observed_pages: dict[int, Path] = {}
    for path in bodies:
        match = re.search(r"page=(\d+)", path.as_posix())
        if match is None:
            raise TruncationScanError("RAW_PAGE_NUMBER_MISSING")
        page_number = int(match.group(1))
        observed_pages[page_number] = path
    if set(observed_pages) != set(expected_bytes):
        raise TruncationScanError(
            f"RAW_PAGE_SET_INCOMPLETE:{sorted(observed_pages)}:{sorted(expected_bytes)}"
        )
    for page_number in sorted(observed_pages):
        path = observed_pages[page_number]
        payload = path.read_bytes()
        observed = len(payload)
        expected = expected_bytes[page_number]
        digest = _sha256_bytes(payload)
        if expected != observed:
            raise TruncationScanError(
                f"RAW_PAGE_SIZE_DRIFT:{page_number}:{expected}:{observed}"
            )
        if digest != EXPECTED_PAGE_SHA256[page_number]:
            raise TruncationScanError(f"RAW_PAGE_HASH_DRIFT:{page_number}")
        page_bindings.append(
            {
                "page_number": page_number,
                "response_bytes": observed,
                "raw_sha256": digest,
            }
        )
        rows.extend(_page_rows(payload))
    return {
        "pages_status": "SCANNED",
        "raw_root": RETAINED_A4_RELATIVE,
        "page_count": len(bodies),
        "pages": page_bindings,
        "scan": classify_rows(rows, plan=loaded_plan),
    }
