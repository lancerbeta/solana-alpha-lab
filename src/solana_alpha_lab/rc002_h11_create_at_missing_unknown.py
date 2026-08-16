"""Offline bind: this TASK-40 mint's create_at is MISSING_UNKNOWN.

No provider calls. Does not mutate the pinned TASK-08 decoder.
Does not fill create_at from a transaction clock. TASK-37/39/40 receipts
stay immutable.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
    TASK40_ACCEPTANCE_RELATIVE,
    load_task40_named_identities,
)

ATOM_ID = "RC002-H11-CREATE-AT-MISSING-UNKNOWN-OFFLINE-V1"
CREATE_AT_STATUS = "MISSING_UNKNOWN"
IDENTITY_RECEIPT_RELATIVE = (
    "docs/evidence/rc002_h11_create_six_field_pubkey_identity/"
    "a1_create_six_field_pubkey_identity_acceptance_v1.json"
)
LAYOUT_RECEIPT_RELATIVE = (
    "docs/evidence/rc002_h11_create_early_six_field_layout/"
    "a1_create_early_six_field_layout_acceptance_v1.json"
)
IDENTITY_TERMINAL = "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE"
LAYOUT_TERMINAL = "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT"
TERMINAL_OUTCOMES = (
    "CREATE_AT_MISSING_UNKNOWN",
    "CREATE_AT_PREREQUISITES_DRIFT",
)


class CreateAtMissingUnknownError(ValueError):
    """A prerequisite receipt cannot be bound fail-closed."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CreateAtMissingUnknownError(code)
    return value


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CreateAtMissingUnknownError(code) from exc
    return dict(_mapping(document, code))


def _fixture_terminal(receipt: Mapping[str, Any], code: str) -> str:
    fixture = dict(_mapping(receipt.get("gettransaction_fixture"), code))
    terminal = fixture.get("terminal")
    if not isinstance(terminal, str) or not terminal:
        raise CreateAtMissingUnknownError(code)
    return terminal


def decide_create_at_terminal(result: Mapping[str, Any]) -> str:
    if (
        result.get("named_mint") != EXPECTED_NAMED_MINT
        or result.get("bonding_curve") != EXPECTED_BONDING_CURVE
        or result.get("identity_terminal") != IDENTITY_TERMINAL
        or result.get("layout_terminal") != LAYOUT_TERMINAL
    ):
        return "CREATE_AT_PREREQUISITES_DRIFT"
    return "CREATE_AT_MISSING_UNKNOWN"


def bind_create_at_missing_unknown(repo_root: Path) -> dict[str, Any]:
    identities = load_task40_named_identities(repo_root)
    identity = _load_json(repo_root / IDENTITY_RECEIPT_RELATIVE, "IDENTITY_RECEIPT_INVALID")
    layout = _load_json(repo_root / LAYOUT_RECEIPT_RELATIVE, "LAYOUT_RECEIPT_INVALID")
    if (
        identity.get("named_mint") != identities["named_mint"]
        or identity.get("bonding_curve") != identities["bonding_curve"]
        or identity.get("create_at") is not None
    ):
        raise CreateAtMissingUnknownError("IDENTITY_RECEIPT_DRIFT")
    result = {
        "named_mint": identities["named_mint"],
        "bonding_curve": identities["bonding_curve"],
        "identity_terminal": _fixture_terminal(identity, "IDENTITY_TERMINAL_INVALID"),
        "layout_terminal": _fixture_terminal(layout, "LAYOUT_TERMINAL_INVALID"),
        "create_at": None,
        "create_at_status": CREATE_AT_STATUS,
        "task40_acceptance": TASK40_ACCEPTANCE_RELATIVE,
        "identity_receipt": IDENTITY_RECEIPT_RELATIVE,
        "layout_receipt": LAYOUT_RECEIPT_RELATIVE,
    }
    result["terminal"] = decide_create_at_terminal(result)
    if result["terminal"] != "CREATE_AT_MISSING_UNKNOWN":
        result["create_at_status"] = None
    return result
