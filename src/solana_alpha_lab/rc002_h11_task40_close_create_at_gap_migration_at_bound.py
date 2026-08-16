"""Offline successor-close: TASK-40 with create_at gap and bound migration_at.

No provider calls. Does not mutate the pinned TASK-08 decoder.
Does not fill clocks from a transaction clock. TASK-37/39/40 receipts stay immutable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from solana_alpha_lab.rc002_h11_create_at_missing_unknown import (
    bind_create_at_missing_unknown,
)
from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
    TASK40_ACCEPTANCE_RELATIVE,
    load_task40_named_identities,
)

ATOM_ID = "RC002-H11-TASK40-CLOSE-CREATE-AT-GAP-MIGRATION-AT-BOUND-V1"
CREATE_AT_STATUS = "MISSING_UNKNOWN"
TASK40_CAPTURE_TERMINAL = "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT"
TASK40_TRIAL_OUTCOME = "INCONCLUSIVE"
CREATE_AT_TERMINAL = "CREATE_AT_MISSING_UNKNOWN"
MIGRATION_TERMINAL = "COMPLETE_MIGRATION_IDENTITY_MATCH"
MIGRATION_AT_STATUS = "BOUND_FROM_EVENT_TIMESTAMP"
COMPLETE_EVENT_STATUS = "MIGRATION_STARTED"
CREATE_AT_RECEIPT_RELATIVE = (
    "docs/evidence/rc002_h11_create_at_missing_unknown/"
    "a1_create_at_missing_unknown_acceptance_v1.json"
)
MIGRATION_RECEIPT_RELATIVE = (
    "docs/evidence/rc002_h11_complete_migration_from_retained_create_history/"
    "a1_complete_migration_from_retained_create_history_acceptance_v1.json"
)
EXPECTED_TASK40_ACCEPTANCE_SHA256 = (
    "ce13526f883f0b25cc709d7afaf307c63d1c60d652c2ac0f54e5d6fcb753a895"
)
EXPECTED_CREATE_AT_RECEIPT_SHA256 = (
    "e78c16ff1329e32bf66d778a3bf0152fd949c08e49a639db3c5370effe2e7c14"
)
EXPECTED_MIGRATION_RECEIPT_SHA256 = (
    "e1d5a5c71fc03ce3b7963951fe9a5a0079baa7ea670f6150633360badce83022"
)
TERMINAL_OUTCOMES = (
    "TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND",
    "TASK40_CLOSE_PREREQUISITES_DRIFT",
)


class Task40CloseError(ValueError):
    """A prerequisite receipt cannot be bound fail-closed."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Task40CloseError(code)
    return value


def _sha256_file(path: Path, code: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise Task40CloseError(code) from exc


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task40CloseError(code) from exc
    return dict(_mapping(document, code))


def decide_task40_close_terminal(result: Mapping[str, Any]) -> str:
    if (
        result.get("named_mint") != EXPECTED_NAMED_MINT
        or result.get("bonding_curve") != EXPECTED_BONDING_CURVE
        or result.get("task40_capture_terminal") != TASK40_CAPTURE_TERMINAL
        or result.get("task40_trial_outcome") != TASK40_TRIAL_OUTCOME
        or result.get("create_at_terminal") != CREATE_AT_TERMINAL
        or result.get("create_at") is not None
        or result.get("create_at_status") != CREATE_AT_STATUS
        or result.get("migration_terminal") != MIGRATION_TERMINAL
        or not isinstance(result.get("migration_at"), int)
        or result.get("migration_at_status") != MIGRATION_AT_STATUS
        or result.get("complete_event_status") != COMPLETE_EVENT_STATUS
        or not isinstance(result.get("complete_event_timestamp"), int)
        or result.get("complete_event_timestamp") == result.get("migration_at")
        or result.get("task40_acceptance_sha256") != EXPECTED_TASK40_ACCEPTANCE_SHA256
        or result.get("create_at_receipt_sha256") != EXPECTED_CREATE_AT_RECEIPT_SHA256
        or result.get("migration_receipt_sha256") != EXPECTED_MIGRATION_RECEIPT_SHA256
    ):
        return "TASK40_CLOSE_PREREQUISITES_DRIFT"
    return "TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND"


def bind_task40_close_create_at_gap_migration_at_bound(repo_root: Path) -> dict[str, Any]:
    identities = load_task40_named_identities(repo_root)
    create_at = bind_create_at_missing_unknown(repo_root)
    task40_path = repo_root / TASK40_ACCEPTANCE_RELATIVE
    create_at_path = repo_root / CREATE_AT_RECEIPT_RELATIVE
    migration_path = repo_root / MIGRATION_RECEIPT_RELATIVE
    task40 = _load_json(task40_path, "TASK40_RECEIPT_INVALID")
    create_at_receipt = _load_json(create_at_path, "CREATE_AT_RECEIPT_INVALID")
    migration = _load_json(migration_path, "MIGRATION_RECEIPT_INVALID")
    if (
        identities["named_mint"] != EXPECTED_NAMED_MINT
        or identities["bonding_curve"] != EXPECTED_BONDING_CURVE
        or create_at.get("named_mint") != identities["named_mint"]
        or create_at.get("bonding_curve") != identities["bonding_curve"]
        or create_at_receipt.get("named_mint") != identities["named_mint"]
        or create_at_receipt.get("bonding_curve") != identities["bonding_curve"]
        or migration.get("named_mint") != identities["named_mint"]
        or migration.get("bonding_curve") != identities["bonding_curve"]
        or task40.get("named_mint") != identities["named_mint"]
        or task40.get("bonding_curve") != identities["bonding_curve"]
        or create_at.get("terminal") != create_at_receipt.get("terminal")
        or create_at.get("create_at") != create_at_receipt.get("create_at")
        or create_at.get("create_at_status") != create_at_receipt.get("create_at_status")
    ):
        raise Task40CloseError("IDENTITY_RECEIPT_DRIFT")
    result = {
        "named_mint": identities["named_mint"],
        "bonding_curve": identities["bonding_curve"],
        "task40_capture_terminal": task40.get("terminal_decision"),
        "task40_trial_outcome": task40.get("trial_outcome"),
        "create_at_terminal": create_at_receipt.get("terminal"),
        "create_at": create_at_receipt.get("create_at"),
        "create_at_status": create_at_receipt.get("create_at_status"),
        "migration_terminal": migration.get("terminal"),
        "migration_at": migration.get("migration_at"),
        "migration_at_status": migration.get("migration_at_status"),
        "complete_event_timestamp": migration.get("complete_event_timestamp"),
        "complete_event_status": migration.get("complete_event_status"),
        "destination_pool": migration.get("destination_pool"),
        "task40_acceptance": TASK40_ACCEPTANCE_RELATIVE,
        "create_at_receipt": CREATE_AT_RECEIPT_RELATIVE,
        "migration_receipt": MIGRATION_RECEIPT_RELATIVE,
        "task40_acceptance_sha256": _sha256_file(task40_path, "TASK40_RECEIPT_UNREADABLE"),
        "create_at_receipt_sha256": _sha256_file(
            create_at_path, "CREATE_AT_RECEIPT_UNREADABLE"
        ),
        "migration_receipt_sha256": _sha256_file(
            migration_path, "MIGRATION_RECEIPT_UNREADABLE"
        ),
    }
    result["terminal"] = decide_task40_close_terminal(result)
    if result["terminal"] != "TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND":
        result["create_at"] = None
        result["create_at_status"] = None
        result["migration_at"] = None
        result["migration_at_status"] = None
        result["complete_event_timestamp"] = None
        result["complete_event_status"] = None
        result["destination_pool"] = None
    return result
