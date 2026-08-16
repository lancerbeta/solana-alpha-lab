"""Offline H11 cohort eligibility after TASK-40 successor close.

No provider calls. Does not mutate the pinned TASK-08 decoder.
Does not fill clocks from a transaction clock. TASK-36/37/40 receipts stay immutable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
)
from solana_alpha_lab.rc002_h11_task40_close_create_at_gap_migration_at_bound import (
    bind_task40_close_create_at_gap_migration_at_bound,
)
from solana_alpha_lab.task37_h11_migration_clock_capture import load_policy

ATOM_ID = "RC002-H11-COHORT-ELIGIBILITY-AFTER-TASK40-CLOSE-OFFLINE-V1"
CLOSE_TERMINAL = "TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND"
TASK36_TERMINAL = "HISTORICAL_ROUTE_INADEQUATE_REPLAN"
TASK37_TERMINAL = "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT"
CREATE_AT_STATUS = "MISSING_UNKNOWN"
POLICY_RELATIVE = "configs/task37_rc002_h11_migration_clock_capture_v1.yaml"
CLOSE_ACCEPTANCE_RELATIVE = (
    "docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/"
    "a1_task40_close_create_at_gap_migration_at_bound_acceptance_v1.json"
)
TASK36_RUNTIME_RELATIVE = (
    "docs/evidence/task36/a1_h11_lifecycle_clock_screen_runtime_receipt_v1.json"
)
TASK37_ACCEPTANCE_RELATIVE = (
    "docs/evidence/task37/a1_h11_migration_clock_capture_acceptance_v1.json"
)
EXPECTED_CLOSE_ACCEPTANCE_SHA256 = (
    "a3270ec48a70ab500fa692b855b8ffa7454e8a84baebde28fd339b68188319e0"
)
EXPECTED_TASK36_RUNTIME_SHA256 = (
    "7cd6952156682bba773855097c39be67b584969a44624ae25bd5e9da2dbf9971"
)
EXPECTED_TASK37_ACCEPTANCE_SHA256 = (
    "4622f12d66ea34e6206c7df5adc6b92ab6ada0e2f40de3d3d7086d1f6c942f6c"
)
EXPECTED_TASK37_POLICY_SHA256 = (
    "1e97cae6e2f7c3cb83838ff73ce6652bdf245170d84a9112f6b9784c583c3f8a"
)
TERMINAL_OUTCOMES = (
    "H11_COHORT_NOT_READY_SCREEN_FORBIDDEN",
    "H11_COHORT_ELIGIBILITY_PREREQUISITES_DRIFT",
)


class CohortEligibilityError(ValueError):
    """A prerequisite receipt or policy cannot be bound fail-closed."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CohortEligibilityError(code)
    return value


def _sha256_file(path: Path, code: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CohortEligibilityError(code) from exc


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CohortEligibilityError(code) from exc
    return dict(_mapping(document, code))


def decide_cohort_eligibility_terminal(result: Mapping[str, Any]) -> str:
    required = dict(result.get("required_units") or {})
    reconstructed = dict(result.get("reconstructed_units") or {})
    if (
        result.get("named_mint") != EXPECTED_NAMED_MINT
        or result.get("bonding_curve") != EXPECTED_BONDING_CURVE
        or result.get("close_terminal") != CLOSE_TERMINAL
        or result.get("create_at") is not None
        or result.get("create_at_status") != CREATE_AT_STATUS
        or not isinstance(result.get("migration_at"), int)
        or not isinstance(result.get("destination_pool"), str)
        or not result.get("destination_pool")
        or result.get("task36_terminal") != TASK36_TERMINAL
        or result.get("task36_n") != 0
        or result.get("task37_capture_terminal") != TASK37_TERMINAL
        or result.get("h11_effect_screen_policy") is not False
        or required.get("pools") != 8
        or required.get("days") != 2
        or required.get("deployers") != 2
        or reconstructed.get("pools") != 1
        or reconstructed.get("days") != 0
        or reconstructed.get("deployers") != 0
        or result.get("close_acceptance_sha256") != EXPECTED_CLOSE_ACCEPTANCE_SHA256
        or result.get("task36_runtime_sha256") != EXPECTED_TASK36_RUNTIME_SHA256
        or result.get("task37_acceptance_sha256") != EXPECTED_TASK37_ACCEPTANCE_SHA256
        or result.get("task37_policy_sha256") != EXPECTED_TASK37_POLICY_SHA256
    ):
        return "H11_COHORT_ELIGIBILITY_PREREQUISITES_DRIFT"
    return "H11_COHORT_NOT_READY_SCREEN_FORBIDDEN"


def bind_cohort_eligibility_after_task40_close(repo_root: Path) -> dict[str, Any]:
    close = bind_task40_close_create_at_gap_migration_at_bound(repo_root)
    close_path = repo_root / CLOSE_ACCEPTANCE_RELATIVE
    task36_path = repo_root / TASK36_RUNTIME_RELATIVE
    task37_path = repo_root / TASK37_ACCEPTANCE_RELATIVE
    policy_path = repo_root / POLICY_RELATIVE
    close_receipt = _load_json(close_path, "CLOSE_RECEIPT_INVALID")
    task36 = _load_json(task36_path, "TASK36_RUNTIME_INVALID")
    task37 = _load_json(task37_path, "TASK37_RECEIPT_INVALID")
    policy = load_policy(policy_path)
    protocol = dict(_mapping(policy.get("capture_protocol"), "PROTOCOL_INVALID"))
    minima = dict(_mapping(protocol.get("minimum_independent_units"), "MINIMA_INVALID"))
    cohort = dict(_mapping(task36.get("cohort"), "TASK36_COHORT_INVALID"))
    destination_pool = close.get("destination_pool")
    reconstructed_pools = (
        1 if isinstance(destination_pool, str) and destination_pool else 0
    )
    if (
        close.get("named_mint") != EXPECTED_NAMED_MINT
        or close.get("bonding_curve") != EXPECTED_BONDING_CURVE
        or close_receipt.get("named_mint") != close.get("named_mint")
        or close_receipt.get("bonding_curve") != close.get("bonding_curve")
        or close_receipt.get("terminal") != close.get("terminal")
        or close.get("terminal") != CLOSE_TERMINAL
    ):
        raise CohortEligibilityError("CLOSE_RECEIPT_DRIFT")
    result = {
        "named_mint": close["named_mint"],
        "bonding_curve": close["bonding_curve"],
        "close_terminal": close.get("terminal"),
        "create_at": close.get("create_at"),
        "create_at_status": close.get("create_at_status"),
        "migration_at": close.get("migration_at"),
        "migration_at_status": close.get("migration_at_status"),
        "destination_pool": destination_pool,
        "task36_terminal": task36.get("terminal_decision"),
        "task36_n": cohort.get("n"),
        "task37_capture_terminal": task37.get("terminal_decision"),
        "h11_effect_screen_policy": protocol.get("h11_effect_screen"),
        "required_units": {
            "pools": minima.get("pools"),
            "days": minima.get("days"),
            "deployers": minima.get("deployers"),
        },
        "reconstructed_units": {
            "pools": reconstructed_pools,
            "days": 0,
            "deployers": 0,
        },
        "close_acceptance": CLOSE_ACCEPTANCE_RELATIVE,
        "task36_runtime": TASK36_RUNTIME_RELATIVE,
        "task37_acceptance": TASK37_ACCEPTANCE_RELATIVE,
        "task37_policy": POLICY_RELATIVE,
        "close_acceptance_sha256": _sha256_file(close_path, "CLOSE_RECEIPT_UNREADABLE"),
        "task36_runtime_sha256": _sha256_file(task36_path, "TASK36_RUNTIME_UNREADABLE"),
        "task37_acceptance_sha256": _sha256_file(
            task37_path, "TASK37_RECEIPT_UNREADABLE"
        ),
        "task37_policy_sha256": _sha256_file(policy_path, "TASK37_POLICY_UNREADABLE"),
    }
    result["terminal"] = decide_cohort_eligibility_terminal(result)
    result["effect_screen_eligible"] = False
    if result["terminal"] != "H11_COHORT_NOT_READY_SCREEN_FORBIDDEN":
        result["create_at"] = None
        result["create_at_status"] = None
        result["migration_at"] = None
        result["migration_at_status"] = None
        result["destination_pool"] = None
        result["required_units"] = None
        result["reconstructed_units"] = None
        result["h11_effect_screen_policy"] = None
    return result
