"""Offline scan: Complete/Migration in git-retained Create 195 history.

No provider calls. Does not mutate the pinned TASK-08 decoder.
Does not fill migration_at from blockTime or CompleteEvent.timestamp.
TASK-37/39/40 receipts stay immutable.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from solana_alpha_lab.pump_event_decoder import (
    PROGRAM_DATA_PREFIX,
    PumpEventDecodeError,
    PumpEventPlan,
    decode_pump_program_data,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.rc002_h11_create_at_missing_unknown import (
    bind_create_at_missing_unknown,
)
from solana_alpha_lab.rc002_h11_create_early_six_field_layout import (
    GETTX_FIXTURE_RELATIVE,
    gettransaction_fixture_row,
)
from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (
    extract_create_payloads_from_logs,
    load_task40_named_identities,
)
from solana_alpha_lab.rc002_h11_older_idl_clock_body import (
    CANDIDATE_ID,
    candidate_drop_trailing_quote_mint,
    classify_clock_bodies,
)
from solana_alpha_lab.rc002_h11_truncation_vs_absence import (
    EXPECTED_PAGE_SHA256,
    IDL_RELATIVE,
    RETAINED_A4_RELATIVE,
    TASK40_RUNTIME_RELATIVE,
)

ATOM_ID = "RC002-H11-COMPLETE-MIGRATION-FROM-RETAINED-CREATE-HISTORY-OFFLINE-V1"
COMPLETE_EVENT = "CompleteEvent"
MIGRATION_EVENT = "CompletePumpAmmMigrationEvent"
COMPLETE_MIGRATION_EVENTS = frozenset({COMPLETE_EVENT, MIGRATION_EVENT})
OLDER_IDL_RECEIPT_RELATIVE = (
    "docs/evidence/rc002_h11_older_idl_clock_body/"
    "a1_older_idl_clock_body_acceptance_v1.json"
)
TERMINAL_OUTCOMES = (
    "COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX",
    "COMPLETE_MIGRATION_IDENTITY_MATCH",
    "COMPLETE_MIGRATION_STARTED_NOT_MIGRATED",
    "COMPLETE_MIGRATION_IDENTITY_MISMATCH",
    "COMPLETE_MIGRATION_LAYOUT_FAIL",
    "COMPLETE_MIGRATION_PREREQUISITES_DRIFT",
)


class CompleteMigrationScanError(ValueError):
    """A fixture, receipt or clock body cannot be classified fail-closed."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CompleteMigrationScanError(code)
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CompleteMigrationScanError(code) from exc
    return dict(_mapping(document, code))


def _row_logs(row: Mapping[str, Any]) -> tuple[list[str], bool]:
    mapping = dict(_mapping(row, "ROW_INVALID"))
    transaction = dict(_mapping(mapping.get("transaction") or {}, "TRANSACTION_INVALID"))
    dict(_mapping(transaction.get("message") or {}, "MESSAGE_INVALID"))
    meta = dict(_mapping(mapping.get("meta") or {}, "META_INVALID"))
    logs = meta.get("logMessages") or []
    if not isinstance(logs, Sequence) or isinstance(logs, (str, bytes)):
        raise CompleteMigrationScanError("LOG_MESSAGES_INVALID")
    return [str(item) for item in logs], meta.get("err") is None


def _event_counts(classified: Mapping[str, Any], key: str) -> dict[str, int]:
    raw = dict(classified.get(key) or {})
    return {
        name: int(raw[name])
        for name in COMPLETE_MIGRATION_EVENTS
        if int(raw.get(name) or 0) > 0
    }


def _discriminators(plan: PumpEventPlan) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for event in plan.events:
        if event.name in COMPLETE_MIGRATION_EVENTS:
            found[event.name] = event.discriminator
    if set(found) != COMPLETE_MIGRATION_EVENTS:
        raise CompleteMigrationScanError("PINNED_COMPLETE_MIGRATION_MISSING")
    return found


def _decode_payload(
    payload: bytes,
    *,
    candidate: PumpEventPlan,
) -> dict[str, Any] | None:
    line = PROGRAM_DATA_PREFIX + base64.b64encode(payload).decode("ascii")
    try:
        decoded = decode_pump_program_data(
            candidate,
            log_line=line,
            emitting_program_id=candidate.program_id,
            transaction_succeeded=True,
        )
    except PumpEventDecodeError:
        return None
    if decoded is None or decoded.event_name not in COMPLETE_MIGRATION_EVENTS:
        return None
    bonding_curve = decoded.fields.get("bonding_curve")
    if not isinstance(bonding_curve, str) or not bonding_curve:
        return None
    observed = {
        "event_name": decoded.event_name,
        "mint": decoded.mint,
        "bonding_curve": bonding_curve,
        "timestamp": decoded.event_timestamp,
        "payload_len": len(payload),
    }
    if decoded.event_name == MIGRATION_EVENT:
        observed["pool"] = decoded.destination_pool
    return observed


def _collect_observed(
    rows: Sequence[Mapping[str, Any]],
    *,
    pinned: PumpEventPlan,
    candidate: PumpEventPlan,
) -> list[dict[str, Any]]:
    discs = _discriminators(pinned)
    observed: list[dict[str, Any]] = []
    for row in rows:
        logs, succeeded = _row_logs(row)
        for event_name, discriminator in discs.items():
            extracted = extract_create_payloads_from_logs(
                logs,
                program_id=pinned.program_id,
                discriminator=discriminator,
                transaction_succeeded=succeeded,
            )
            for payload in extracted["payloads"]:
                decoded = _decode_payload(payload, candidate=candidate)
                if decoded is None:
                    continue
                if decoded["event_name"] != event_name:
                    raise CompleteMigrationScanError("CLOCK_EVENT_NAME_DRIFT")
                observed.append(decoded)
    return observed


def decide_source_terminal(result: Mapping[str, Any]) -> str:
    consumed = dict(result.get("consumed_by_event") or {})
    failed = dict(result.get("failed_by_event") or {})
    observed = list(result.get("observed") or [])
    named_mint = result.get("named_mint")
    bonding_curve = result.get("bonding_curve")
    consumed_n = sum(int(value) for value in consumed.values())
    failed_n = sum(int(value) for value in failed.values())
    if failed_n > 0 and consumed_n == 0:
        return "COMPLETE_MIGRATION_LAYOUT_FAIL"
    if consumed_n == 0:
        return "COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX"
    mismatches = [
        item
        for item in observed
        if item.get("mint") != named_mint or item.get("bonding_curve") != bonding_curve
    ]
    if mismatches:
        return "COMPLETE_MIGRATION_IDENTITY_MISMATCH"
    if any(item.get("event_name") == MIGRATION_EVENT for item in observed):
        return "COMPLETE_MIGRATION_IDENTITY_MATCH"
    return "COMPLETE_MIGRATION_STARTED_NOT_MIGRATED"


def decide_complete_migration_terminal(result: Mapping[str, Any]) -> str:
    if (
        result.get("create_at_terminal") != "CREATE_AT_MISSING_UNKNOWN"
        or int(result.get("older_idl_complete_consumed") or 0) != 1
        or int(result.get("older_idl_migration_consumed") or 0) != 1
    ):
        return "COMPLETE_MIGRATION_PREREQUISITES_DRIFT"
    terminal = result.get("fixture_terminal")
    if not isinstance(terminal, str) or not terminal:
        raise CompleteMigrationScanError("FIXTURE_TERMINAL_INVALID")
    return terminal


def _clocks_from_observed(
    observed: Sequence[Mapping[str, Any]],
    *,
    terminal: str,
) -> dict[str, Any]:
    complete_ts = None
    migration_at = None
    pool = None
    for item in observed:
        if item.get("event_name") == COMPLETE_EVENT:
            complete_ts = item.get("timestamp")
        if item.get("event_name") == MIGRATION_EVENT:
            migration_at = item.get("timestamp")
            pool = item.get("pool")
    if terminal == "COMPLETE_MIGRATION_IDENTITY_MATCH":
        return {
            "migration_at": migration_at,
            "migration_at_status": "BOUND_FROM_EVENT_TIMESTAMP"
            if isinstance(migration_at, int)
            else "MIGRATION_BODY_ABSENT",
            "complete_event_timestamp": complete_ts if isinstance(complete_ts, int) else None,
            "complete_event_status": "MIGRATION_STARTED"
            if isinstance(complete_ts, int)
            else None,
            "destination_pool": pool if isinstance(pool, str) else None,
        }
    if terminal == "COMPLETE_MIGRATION_STARTED_NOT_MIGRATED":
        return {
            "migration_at": None,
            "migration_at_status": "MIGRATION_BODY_ABSENT",
            "complete_event_timestamp": complete_ts if isinstance(complete_ts, int) else None,
            "complete_event_status": "MIGRATION_STARTED"
            if isinstance(complete_ts, int)
            else None,
            "destination_pool": None,
        }
    return {
        "migration_at": None,
        "migration_at_status": "NOT_IN_CREATE_GETTX"
        if terminal == "COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX"
        else None,
        "complete_event_timestamp": None,
        "complete_event_status": None,
        "destination_pool": None,
    }


def classify_rows_complete_migration(
    rows: Sequence[Mapping[str, Any]],
    *,
    pinned: PumpEventPlan,
    candidate: PumpEventPlan,
    named_mint: str,
    bonding_curve: str,
) -> dict[str, Any]:
    classified = classify_clock_bodies(rows, pinned=pinned, candidate=candidate)
    observed = _collect_observed(rows, pinned=pinned, candidate=candidate)
    result = {
        "candidate_id": CANDIDATE_ID,
        "named_mint": named_mint,
        "bonding_curve": bonding_curve,
        "consumed_by_event": _event_counts(classified, "consumed_by_event"),
        "failed_by_event": _event_counts(classified, "failed_by_event"),
        "observed": observed,
    }
    result["terminal"] = decide_source_terminal(result)
    result.update(_clocks_from_observed(observed, terminal=result["terminal"]))
    return result


def _load_older_idl_consumed(repo_root: Path) -> dict[str, int]:
    receipt = _load_json(repo_root / OLDER_IDL_RECEIPT_RELATIVE, "OLDER_IDL_RECEIPT_INVALID")
    if receipt.get("candidate_id") != CANDIDATE_ID:
        raise CompleteMigrationScanError("OLDER_IDL_CANDIDATE_DRIFT")
    retained = dict(_mapping(receipt.get("retained_a4"), "OLDER_IDL_A4_INVALID"))
    consumed = dict(_mapping(retained.get("consumed_by_event"), "OLDER_IDL_CONSUMED_INVALID"))
    lengths = dict(_mapping(retained.get("payload_len_by_event"), "OLDER_IDL_LENGTHS_INVALID"))
    complete_len = list(lengths.get(COMPLETE_EVENT) or [])
    migration_len = list(lengths.get(MIGRATION_EVENT) or [])
    if complete_len != [112] or migration_len != [168]:
        raise CompleteMigrationScanError("OLDER_IDL_PAYLOAD_LEN_DRIFT")
    return {
        "complete": int(consumed.get(COMPLETE_EVENT) or 0),
        "migration": int(consumed.get(MIGRATION_EVENT) or 0),
    }


def _page_rows(body: bytes) -> list[dict[str, Any]]:
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CompleteMigrationScanError("RAW_PAGE_JSON_INVALID") from exc
    payload = dict(_mapping(document, "RAW_PAGE_ROOT_INVALID"))
    if "error" in payload:
        return []
    result = dict(_mapping(payload.get("result"), "RAW_PAGE_RESULT_INVALID"))
    rows = result.get("data")
    if not isinstance(rows, list):
        raise CompleteMigrationScanError("RAW_PAGE_DATA_INVALID")
    return [dict(_mapping(row, "ROW_INVALID")) for row in rows]


def _expected_page_bytes(repo_root: Path) -> dict[int, int]:
    receipt = _load_json(repo_root / TASK40_RUNTIME_RELATIVE, "TASK40_RUNTIME_INVALID")
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
        raise CompleteMigrationScanError("TASK40_PAGE_SET_DRIFT")
    observed_pages: dict[int, Path] = {}
    for path in bodies:
        match = re.search(r"page=(\d+)", path.as_posix())
        if match is None:
            raise CompleteMigrationScanError("RAW_PAGE_NUMBER_MISSING")
        observed_pages[int(match.group(1))] = path
    if set(observed_pages) != set(expected_bytes):
        raise CompleteMigrationScanError(
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
            raise CompleteMigrationScanError(
                f"RAW_PAGE_SIZE_DRIFT:{page_number}:{expected}:{observed}"
            )
        if digest != EXPECTED_PAGE_SHA256[page_number]:
            raise CompleteMigrationScanError(f"RAW_PAGE_HASH_DRIFT:{page_number}")
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


def classify_gettransaction_fixture_complete_migration(
    repo_root: Path,
    *,
    pinned: PumpEventPlan,
    candidate: PumpEventPlan,
    named_mint: str,
    bonding_curve: str,
) -> dict[str, Any]:
    path = repo_root / GETTX_FIXTURE_RELATIVE
    document = _load_json(path, "GETTX_FIXTURE_JSON_INVALID")
    row = gettransaction_fixture_row(document)
    return classify_rows_complete_migration(
        [row],
        pinned=pinned,
        candidate=candidate,
        named_mint=named_mint,
        bonding_curve=bonding_curve,
    )


def bind_complete_migration_from_retained_create_history(repo_root: Path) -> dict[str, Any]:
    identities = load_task40_named_identities(repo_root)
    create_at = bind_create_at_missing_unknown(repo_root)
    older = _load_older_idl_consumed(repo_root)
    pinned = load_pinned_pump_event_plan(repo_root / IDL_RELATIVE)
    candidate = candidate_drop_trailing_quote_mint(pinned)
    fixture = classify_gettransaction_fixture_complete_migration(
        repo_root,
        pinned=pinned,
        candidate=candidate,
        named_mint=identities["named_mint"],
        bonding_curve=identities["bonding_curve"],
    )
    loaded_pages = _load_retained_a4_rows(repo_root)
    if loaded_pages["pages_status"] != "SCANNED":
        a4: dict[str, Any] = {
            "pages_status": loaded_pages["pages_status"],
            "raw_root": loaded_pages["raw_root"],
            "scan": None,
            "page_count": 0,
            "pages": [],
        }
        source = fixture
    else:
        scan = classify_rows_complete_migration(
            list(loaded_pages["rows"] or []),
            pinned=pinned,
            candidate=candidate,
            named_mint=identities["named_mint"],
            bonding_curve=identities["bonding_curve"],
        )
        a4 = {
            "pages_status": "SCANNED",
            "raw_root": loaded_pages["raw_root"],
            "scan": scan,
            "page_count": loaded_pages["page_count"],
            "pages": loaded_pages["pages"],
        }
        source = scan
    decided = {
        "create_at_terminal": create_at.get("terminal"),
        "older_idl_complete_consumed": older["complete"],
        "older_idl_migration_consumed": older["migration"],
        "fixture_terminal": fixture["terminal"],
    }
    overall = decide_complete_migration_terminal(decided)
    if overall != "COMPLETE_MIGRATION_PREREQUISITES_DRIFT":
        overall = source["terminal"]
    clocks = _clocks_from_observed(source.get("observed") or [], terminal=overall)
    return {
        "named_mint": identities["named_mint"],
        "bonding_curve": identities["bonding_curve"],
        "candidate_id": CANDIDATE_ID,
        "create_at": create_at.get("create_at"),
        "create_at_status": create_at.get("create_at_status"),
        "create_at_terminal": create_at.get("terminal"),
        "older_idl_complete_consumed": older["complete"],
        "older_idl_migration_consumed": older["migration"],
        "gettransaction_fixture": fixture,
        "retained_a4": a4,
        "terminal": overall,
        **clocks,
    }
