"""Offline trial: consume retained Create 195 without quote_mint and virtual_quote_reserves.

No provider calls. Does not mutate the pinned TASK-08 decoder.
TASK-40/39 and older-IDL science receipts are not rewritten.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from solana_alpha_lab.pump_event_decoder import (
    EventSchema,
    PumpEventPlan,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.rc002_h11_older_idl_clock_body import (
    OlderIdlScanError,
    candidate_drop_trailing_quote_mint,
    classify_clock_bodies,
    classify_transaction_clock_bodies,
)
from solana_alpha_lab.rc002_h11_truncation_vs_absence import (
    EXPECTED_PAGE_SHA256,
    IDL_RELATIVE,
    RETAINED_A4_RELATIVE,
    TASK40_RUNTIME_RELATIVE,
)

ATOM_ID = "RC002-H11-CREATE-WITHOUT-VIRTUAL-QUOTE-OFFLINE-V1"
CANDIDATE_ID = "DROP_QUOTE_MINT_AND_VIRTUAL_QUOTE_RESERVES"
CREATE_EVENT = "CreateEvent"
CREATE_DROP_FIELDS = ("quote_mint", "virtual_quote_reserves")
TERMINAL_OUTCOMES = (
    "CREATE_CONSUMED_WITHOUT_REMAINDER",
    "CREATE_STILL_TRUNCATED_NEED_GETTRANSACTION",
    "CREATE_BODY_ABSENT",
)


class CreateWithoutVirtualQuoteError(OlderIdlScanError):
    """A retained page or Create candidate cannot be classified fail-closed."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CreateWithoutVirtualQuoteError(code)
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def candidate_drop_quote_mint_and_virtual_quote_reserves(
    pinned: PumpEventPlan,
) -> PumpEventPlan:
    events: list[EventSchema] = []
    for event in pinned.events:
        if event.name == CREATE_EVENT:
            names = [field.name for field in event.fields]
            missing = [name for name in CREATE_DROP_FIELDS if name not in names]
            if missing:
                raise CreateWithoutVirtualQuoteError(
                    f"PINNED_CREATE_MISSING_QUOTE_FIELDS:{','.join(missing)}"
                )
            drop = set(CREATE_DROP_FIELDS)
            fields = tuple(field for field in event.fields if field.name not in drop)
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


def _merge_int_map(left: dict[str, int], right: Mapping[str, int]) -> None:
    for key, value in right.items():
        left[key] = left.get(key, 0) + int(value)


def classify_create_bodies(
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
        transaction = dict(_mapping(mapping.get("transaction") or {}, "TRANSACTION_INVALID"))
        dict(_mapping(transaction.get("message") or {}, "MESSAGE_INVALID"))
        meta = dict(_mapping(mapping.get("meta") or {}, "META_INVALID"))
        logs = meta.get("logMessages") or []
        if not isinstance(logs, Sequence) or isinstance(logs, (str, bytes)):
            raise CreateWithoutVirtualQuoteError("LOG_MESSAGES_INVALID")
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
        "consumed_by_event": _create_only_int_map(consumed_by_event),
        "failed_by_event": _create_only_int_map(failed_by_event),
        "payload_len_by_event": _create_only_len_map(payload_len_by_event),
        "fail_codes_by_event": _create_only_code_map(fail_codes_by_event),
        "attribution_errors": attribution_errors,
    }
    result["terminal"] = decide_create_terminal(result)
    return result


def _create_only_int_map(counts: Mapping[str, int]) -> dict[str, int]:
    if CREATE_EVENT not in counts:
        return {}
    return {CREATE_EVENT: int(counts[CREATE_EVENT])}


def _create_only_len_map(lengths: Mapping[str, list[int]]) -> dict[str, list[int]]:
    if CREATE_EVENT not in lengths:
        return {}
    return {CREATE_EVENT: list(lengths[CREATE_EVENT])}


def _create_only_code_map(
    codes: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, int]]:
    if CREATE_EVENT not in codes:
        return {}
    return {CREATE_EVENT: dict(codes[CREATE_EVENT])}


def decide_create_terminal(counts: Mapping[str, Any]) -> str:
    consumed = int(dict(counts.get("consumed_by_event") or {}).get(CREATE_EVENT, 0) or 0)
    failed = int(dict(counts.get("failed_by_event") or {}).get(CREATE_EVENT, 0) or 0)
    if consumed > 0 and failed == 0:
        return "CREATE_CONSUMED_WITHOUT_REMAINDER"
    if failed > 0:
        return "CREATE_STILL_TRUNCATED_NEED_GETTRANSACTION"
    return "CREATE_BODY_ABSENT"


def _page_rows(body: bytes) -> list[dict[str, Any]]:
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CreateWithoutVirtualQuoteError("RAW_PAGE_JSON_INVALID") from exc
    payload = dict(_mapping(document, "RAW_PAGE_ROOT_INVALID"))
    if "error" in payload:
        return []
    result = dict(_mapping(payload.get("result"), "RAW_PAGE_RESULT_INVALID"))
    rows = result.get("data")
    if not isinstance(rows, list):
        raise CreateWithoutVirtualQuoteError("RAW_PAGE_DATA_INVALID")
    return [dict(_mapping(row, "ROW_INVALID")) for row in rows]


def _expected_page_bytes(repo_root: Path) -> dict[int, int]:
    receipt = json.loads((repo_root / TASK40_RUNTIME_RELATIVE).read_text(encoding="utf-8"))
    pages = receipt["scan"]["pages"]
    expected: dict[int, int] = {}
    for page in pages:
        expected[int(page["page_number"])] = int(page["response_bytes"])
    return expected


def _load_retained_a4_rows(repo_root: Path) -> dict[str, Any]:
    raw_root = repo_root / RETAINED_A4_RELATIVE
    if not raw_root.exists():
        return {
            "pages_status": "RETAINED_A4_PAGES_NOT_IN_CHECKOUT",
            "raw_root": RETAINED_A4_RELATIVE,
            "rows": None,
            "page_count": 0,
            "pages": [],
        }
    bodies = sorted(raw_root.rglob("raw_response.json"))
    if not bodies:
        return {
            "pages_status": "RETAINED_A4_PAGES_NOT_IN_CHECKOUT",
            "raw_root": RETAINED_A4_RELATIVE,
            "rows": None,
            "page_count": 0,
            "pages": [],
        }
    expected_bytes = _expected_page_bytes(repo_root)
    if set(expected_bytes) != set(EXPECTED_PAGE_SHA256):
        raise CreateWithoutVirtualQuoteError("TASK40_PAGE_SET_DRIFT")
    observed_pages: dict[int, Path] = {}
    for path in bodies:
        match = re.search(r"page=(\d+)", path.as_posix())
        if match is None:
            raise CreateWithoutVirtualQuoteError("RAW_PAGE_NUMBER_MISSING")
        observed_pages[int(match.group(1))] = path
    if set(observed_pages) != set(expected_bytes):
        raise CreateWithoutVirtualQuoteError(
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
            raise CreateWithoutVirtualQuoteError(
                f"RAW_PAGE_SIZE_DRIFT:{page_number}:{expected}:{observed}"
            )
        if digest != EXPECTED_PAGE_SHA256[page_number]:
            raise CreateWithoutVirtualQuoteError(f"RAW_PAGE_HASH_DRIFT:{page_number}")
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
        "rows": rows,
        "page_count": len(bodies),
        "pages": page_bindings,
    }


def scan_retained_a4_create_without_virtual_quote(
    repo_root: Path,
    *,
    pinned: PumpEventPlan | None = None,
) -> dict[str, Any]:
    loaded = pinned or load_pinned_pump_event_plan(repo_root / IDL_RELATIVE)
    loaded_pages = _load_retained_a4_rows(repo_root)
    if loaded_pages["pages_status"] != "SCANNED":
        return {
            "pages_status": loaded_pages["pages_status"],
            "raw_root": loaded_pages["raw_root"],
            "scan": None,
            "quote_mint_only_regression": None,
            "page_count": 0,
            "pages": [],
        }
    rows = list(loaded_pages["rows"] or [])
    candidate = candidate_drop_quote_mint_and_virtual_quote_reserves(loaded)
    scan = classify_create_bodies(rows, pinned=loaded, candidate=candidate)
    regression = classify_clock_bodies(
        rows,
        pinned=loaded,
        candidate=candidate_drop_trailing_quote_mint(loaded),
    )
    return {
        "pages_status": "SCANNED",
        "raw_root": loaded_pages["raw_root"],
        "page_count": loaded_pages["page_count"],
        "pages": loaded_pages["pages"],
        "scan": scan,
        "quote_mint_only_regression": regression,
    }
