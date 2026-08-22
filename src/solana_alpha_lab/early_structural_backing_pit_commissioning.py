"""EARLY structural-backing PIT commissioning: ICP-aware liquidity/mcap projector."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from solana_alpha_lab.early_icp_freeze_acceptance import (
    AGE_MAX_EXCLUSIVE_SECONDS,
    AGE_MIN_SECONDS,
)
from solana_alpha_lab.ordinary_market_pit_primary_x import (
    PRIMARY_X_BOUND,
    PRIMARY_X_UNKNOWN,
    bind_primary_x,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (
    OrganicPressureError,
    SEASONING_SECONDS,
    _parse_datetime,
    run_campaign,
    score_audition,
    validate_policy,
)

ATOM_ID = "EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1"
POLICY_SCHEMA = "smial.early-structural-backing-pit-commissioning"
RECEIPT_SCHEMA = "smial.early-structural-backing-pit-commissioning.runtime-receipt"
X_FORMULA = "liquidity / mcap"
CLOSE_TERMINAL = "CLOSE_EARLY_STRUCTURAL_BACKING_FAMILY"
EARN_WINDOW = "EARN_FRESH_OOS"
EARN_SHADOW = "EARN_SHADOW"
ICP_ID = "ICP-EARLY-PUMPFUN-V1"
LIQUIDITY_USD_MIN = 1000.0
FIELD_PATHS = ["liquidity", "mcap", "firstPool.createdAt", "updatedAt", "launchpad"]
FACTORY_RUNNER = "src/solana_alpha_lab/factory/runner.py"
FACTORY_RUNNER_SHA256 = "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"
AUTHORITY_PHRASE = (
    "OK EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1: one bounded Jupiter "
    "Free-key read-only PIT commissioning campaign using a local "
    "process-environment key only; Tokens V2 /recent plus one bulk "
    "/tokens/v2/search for frozen mints plus quote-only /swap/v2/order; "
    "x-api-key header only; no .env read, no key in URL/log/receipt/Git, no "
    "taker, /build, /execute, wallet, signer, transaction, paid plan, second "
    "provider, retry or fallback; cash cap $0; call cap 60; global provider "
    "pace >=3s; ICP-EARLY-PUMPFUN-V1 population; 24 fresh project-eligible "
    "recent candidates excluding all prior consumed mints; wait until pool "
    "age >=5m before the single bulk decision-time search snapshot; X = "
    "liquidity / mcap from that search snapshot only (mcap != fdv; UNKNOWN "
    "never zero); quote-only BUY at T0 and quote-only SELL at H900; Window A "
    "then conditional Window B only if A is not "
    "CLOSE_EARLY_STRUCTURAL_BACKING_FAMILY; no third window; Factory runner "
    "unchanged; Strategy, Bot, Shadow, alpha and NetReturn forbidden."
)


def project_structural_backing(
    recent_row: Mapping[str, Any],
    t5_row: Mapping[str, Any] | None,
    snapshot_at: datetime,
    *,
    seasoning_seconds: int = SEASONING_SECONDS,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "MISSING",
        "value": None,
        "field_paths": list(FIELD_PATHS),
        "inputs": {},
        "icp_id": ICP_ID,
    }
    if not isinstance(recent_row, Mapping) or not isinstance(t5_row, Mapping):
        result["reason"] = "SEARCH_MINT_NOT_RETURNED"
        return result
    if recent_row.get("launchpad") != "pump.fun" or t5_row.get("launchpad") != "pump.fun":
        result["reason"] = "PROJECT_PREDICATE_FALSE"
        return result
    if recent_row.get("id") != t5_row.get("id"):
        result["reason"] = "RECENT_T5_MINT_MISMATCH"
        return result
    pool = t5_row.get("firstPool")
    if not isinstance(pool, Mapping):
        result["reason"] = "REQUIRED_OBJECT_ABSENT"
        return result
    try:
        created_at = _parse_datetime(pool.get("createdAt"), "FIRST_POOL_TIMESTAMP_INVALID")
        updated_at = _parse_datetime(t5_row.get("updatedAt"), "UPDATED_TIMESTAMP_INVALID")
    except OrganicPressureError as exc:
        result["reason"] = str(exc)
        return result
    observed_at = snapshot_at.astimezone(UTC)
    age_seconds = (observed_at - created_at).total_seconds()
    result["age_seconds"] = age_seconds
    result["inputs"] = {
        "liquidity": t5_row.get("liquidity"),
        "mcap": t5_row.get("mcap"),
        "firstPool.createdAt": pool.get("createdAt"),
        "updatedAt": t5_row.get("updatedAt"),
        "launchpad": t5_row.get("launchpad"),
    }
    if created_at > observed_at:
        result["reason"] = "FIRST_POOL_TIMESTAMP_IN_FUTURE"
        return result
    if age_seconds < float(AGE_MIN_SECONDS) or age_seconds < seasoning_seconds:
        result["status"] = "TOO_YOUNG"
        result["reason"] = "POOL_AGE_BELOW_ICP_MIN"
        return result
    if age_seconds >= float(AGE_MAX_EXCLUSIVE_SECONDS):
        result["status"] = "TOO_OLD"
        result["reason"] = "POOL_AGE_OUTSIDE_ICP_MAX"
        return result
    if updated_at < created_at:
        result["reason"] = "UPDATED_TIMESTAMP_BEFORE_POOL_CREATION"
        return result
    if updated_at > observed_at:
        result["reason"] = "UPDATED_TIMESTAMP_IN_FUTURE"
        return result
    observed_at_text = observed_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    bound = bind_primary_x(t5_row, observed_at=observed_at_text)
    result["liquidity"] = bound.get("liquidity")
    result["mcap"] = bound.get("mcap")
    result["substitute_rejected"] = bound.get("substitute_rejected")
    if bound.get("substitute_rejected") is True:
        result["reason"] = "FDV_OR_SUBSTITUTE_REJECTED"
        return result
    liquidity = bound.get("liquidity")
    if liquidity is None or float(liquidity) < LIQUIDITY_USD_MIN:
        result["reason"] = "LIQUIDITY_BELOW_ICP_MIN"
        return result
    if bound.get("status") != PRIMARY_X_BOUND:
        result["reason"] = "MCAP_OR_LIQUIDITY_MISSING" if bound.get("status") == PRIMARY_X_UNKNOWN else "PRIMARY_X_UNKNOWN"
        return result
    result["status"] = "ELIGIBLE"
    result["value"] = bound.get("value")
    result["x_available_at"] = observed_at_text
    return result


def validate_structural_backing_policy(policy: Mapping[str, Any], *, root: Any) -> None:
    validate_policy(
        policy,
        root=root,
        expected_atom_id=ATOM_ID,
        expected_authority_phrase=AUTHORITY_PHRASE,
        expected_schema=POLICY_SCHEMA,
        expected_x_formula=X_FORMULA,
    )


def run_structural_backing_campaign(policy: Mapping[str, Any], **kwargs: Any) -> dict[str, object]:
    return run_campaign(
        policy,
        atom_id=ATOM_ID,
        expected_authority_phrase=AUTHORITY_PHRASE,
        expected_schema=POLICY_SCHEMA,
        expected_x_formula=X_FORMULA,
        receipt_schema=RECEIPT_SCHEMA,
        close_terminal=CLOSE_TERMINAL,
        project_x=project_structural_backing,
        **kwargs,
    )


def decide_family(
    window_a: Mapping[str, Any],
    window_b: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Map Window A(+B) campaign terminals into one family decision."""
    terminal_a = str(window_a.get("terminal") or window_a.get("score", {}).get("terminal") or "")
    score_a = window_a.get("score") if isinstance(window_a.get("score"), Mapping) else window_a
    tau_a = score_a.get("tau_b") if isinstance(score_a, Mapping) else None

    if terminal_a == CLOSE_TERMINAL:
        return {
            "family_decision": CLOSE_TERMINAL,
            "window_b_required": False,
            "window_b_ran": False,
            "reason": "WINDOW_A_SCIENTIFIC_KILL",
            "tau_b_window_a": tau_a,
            "tau_b_window_b": None,
        }
    if terminal_a in {"INVALID_EVIDENCE_YIELD", "INVALID_EVIDENCE_REPLAN"}:
        if window_b is None:
            return {
                "family_decision": "RUN_WINDOW_B",
                "window_b_required": True,
                "window_b_ran": False,
                "reason": "WINDOW_A_EVIDENCE_INCOMPLETE",
                "tau_b_window_a": tau_a,
                "tau_b_window_b": None,
            }
        terminal_b = str(window_b.get("terminal") or window_b.get("score", {}).get("terminal") or "")
        score_b = window_b.get("score") if isinstance(window_b.get("score"), Mapping) else window_b
        tau_b = score_b.get("tau_b") if isinstance(score_b, Mapping) else None
        if terminal_b == CLOSE_TERMINAL:
            return {
                "family_decision": CLOSE_TERMINAL,
                "window_b_required": True,
                "window_b_ran": True,
                "reason": "WINDOW_B_SCIENTIFIC_KILL",
                "tau_b_window_a": tau_a,
                "tau_b_window_b": tau_b,
            }
        return {
            "family_decision": "INVALID_EVIDENCE_YIELD",
            "window_b_required": True,
            "window_b_ran": True,
            "reason": "TWO_WINDOWS_WITHOUT_REPLICABLE_SIGNAL",
            "tau_b_window_a": tau_a,
            "tau_b_window_b": tau_b,
        }
    if terminal_a == EARN_WINDOW:
        if window_b is None:
            return {
                "family_decision": "RUN_WINDOW_B",
                "window_b_required": True,
                "window_b_ran": False,
                "reason": "WINDOW_A_PASS_NEEDS_REPLICATION",
                "tau_b_window_a": tau_a,
                "tau_b_window_b": None,
            }
        terminal_b = str(window_b.get("terminal") or window_b.get("score", {}).get("terminal") or "")
        score_b = window_b.get("score") if isinstance(window_b.get("score"), Mapping) else window_b
        tau_b = score_b.get("tau_b") if isinstance(score_b, Mapping) else None
        if terminal_b == CLOSE_TERMINAL:
            return {
                "family_decision": CLOSE_TERMINAL,
                "window_b_required": True,
                "window_b_ran": True,
                "reason": "WINDOW_B_KILL_AFTER_A_PASS",
                "tau_b_window_a": tau_a,
                "tau_b_window_b": tau_b,
            }
        if terminal_b == EARN_WINDOW and tau_a is not None and tau_b is not None and float(tau_a) > 0 and float(tau_b) > 0:
            return {
                "family_decision": EARN_SHADOW,
                "window_b_required": True,
                "window_b_ran": True,
                "reason": "REPLICATED_POSITIVE_DIRECTION",
                "tau_b_window_a": tau_a,
                "tau_b_window_b": tau_b,
            }
        if terminal_b == EARN_WINDOW and (
            tau_a is None or tau_b is None or float(tau_a) <= 0 or float(tau_b) <= 0 or (float(tau_a) > 0) != (float(tau_b) > 0)
        ):
            return {
                "family_decision": CLOSE_TERMINAL,
                "window_b_required": True,
                "window_b_ran": True,
                "reason": "SIGN_FLIP_OR_NONPOSITIVE_REPLICATION",
                "tau_b_window_a": tau_a,
                "tau_b_window_b": tau_b,
            }
        return {
            "family_decision": "INVALID_EVIDENCE_YIELD",
            "window_b_required": True,
            "window_b_ran": True,
            "reason": "WINDOW_B_DID_NOT_REPLICATE",
            "tau_b_window_a": tau_a,
            "tau_b_window_b": tau_b,
        }
    return {
        "family_decision": "INVALID_EVIDENCE_REPLAN",
        "window_b_required": False,
        "window_b_ran": window_b is not None,
        "reason": "UNTYPED_WINDOW_A_TERMINAL",
        "tau_b_window_a": tau_a,
        "tau_b_window_b": None,
    }


__all__ = [
    "ATOM_ID",
    "AUTHORITY_PHRASE",
    "CLOSE_TERMINAL",
    "EARN_SHADOW",
    "FACTORY_RUNNER",
    "FACTORY_RUNNER_SHA256",
    "X_FORMULA",
    "decide_family",
    "project_structural_backing",
    "run_structural_backing_campaign",
    "score_audition",
    "validate_structural_backing_policy",
]
