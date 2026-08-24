"""EARLY holder-concentration H900 falsifier: thin X projector over shared campaign."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from solana_alpha_lab.early_icp_freeze_acceptance import (
    AGE_MAX_EXCLUSIVE_SECONDS,
    AGE_MIN_SECONDS,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (
    OrganicPressureError,
    SEASONING_SECONDS,
    run_campaign,
    score_sign_only_kendall,
    validate_policy,
)

ATOM_ID = "EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1"
CONFIRMATORY_ATOM_ID = "EARLY_HOLDER_CONCENTRATION_H900_CONFIRMATORY_OOS_V1"
POLICY_SCHEMA = "smial.early-holder-concentration-h900-falsifier"
RECEIPT_SCHEMA = "smial.early-holder-concentration-h900-falsifier.runtime-receipt"
X_FORMULA = "audit.topHoldersPercentage"
CLOSE_TERMINAL = "CLOSE_HOLDER_CONCENTRATION_FAMILY"
EARN_TERMINAL = "EARN_ONE_CONFIRMATORY_FRESH_OOS"
CONFIRMATORY_CLOSE_TERMINAL = "CLOSE_HOLDER_CONCENTRATION_AFTER_FAILED_CONFIRMATION"
CONFIRMATORY_EARN_TERMINAL = "HOLDER_CONCENTRATION_MECHANISM_REPLICATED"
INVALID_TERMINAL = "INVALID_EVIDENCE_REPLAN"
ICP_ID = "ICP-EARLY-PUMPFUN-V1"
LIQUIDITY_USD_MIN = 1000.0
X_MIN = 0.0
X_MAX = 100.0
FIELD_PATHS = [
    "audit.topHoldersPercentage",
    "liquidity",
    "firstPool.createdAt",
    "updatedAt",
    "launchpad",
]
FACTORY_RUNNER = "src/solana_alpha_lab/factory/runner.py"
FACTORY_RUNNER_SHA256 = "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"
JUPITER_TOP_HOLDERS_POOL_EXCLUSION = "UNKNOWN"
AUTHORITY_PHRASE = (
    "OK EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1: one bounded Jupiter "
    "Free-key read-only campaign using a local process-environment key only; "
    "Tokens V2 /recent plus one bulk /tokens/v2/search for frozen mints plus "
    "quote-only /swap/v2/order; x-api-key header only; no .env read, no key in "
    "URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, "
    "transaction, paid plan, second provider, retry or fallback; cash cap $0; "
    "call cap 60; global provider pace >=3s; ICP-EARLY-PUMPFUN-V1 population; "
    "24 fresh project-eligible recent candidates excluding all prior consumed "
    "mints including EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1; "
    "wait until pool age >=5m before the single bulk decision-time search "
    "snapshot; X = audit.topHoldersPercentage from that search snapshot only "
    "(ABSENT never zero; scale 0-100); quote-only BUY at decision and "
    "quote-only SELL at H900; one window only; sign-only Kendall tau_b < 0; "
    "no threshold, quartile, LOO, smoothing or second snapshot; Factory "
    "runner unchanged; Strategy, Bot, Shadow, alpha and NetReturn forbidden."
)
CONFIRMATORY_AUTHORITY_PHRASE = (
    "OK EARLY_HOLDER_CONCENTRATION_H900_CONFIRMATORY_OOS_V1: one bounded "
    "Jupiter Free-key read-only confirmatory campaign using a local "
    "process-environment key only; Tokens V2 /recent plus one bulk "
    "/tokens/v2/search for frozen mints plus quote-only /swap/v2/order; "
    "x-api-key header only; no .env read, no key in URL/log/receipt/Git, no "
    "taker, /build, /execute, wallet, signer, transaction, paid plan, second "
    "provider, retry or fallback; cash cap $0; call cap 60; global provider "
    "pace >=3s; ICP-EARLY-PUMPFUN-V1 population; 24 fresh project-eligible "
    "recent candidates excluding all prior consumed mints including "
    "EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1; wait until pool age >=5m "
    "before the single bulk decision-time search snapshot; X = "
    "audit.topHoldersPercentage from that search snapshot only (ABSENT never "
    "zero; scale 0-100); quote-only BUY at decision and quote-only SELL at "
    "H900; one confirmatory window only; sign-only Kendall tau_b < 0; no "
    "threshold, quartile, LOO, smoothing or second snapshot; Factory runner "
    "unchanged; Strategy, Bot, Shadow, alpha and NetReturn forbidden."
)


def holder_identity(policy: Mapping[str, Any]) -> dict[str, str]:
    atom_id = policy.get("atom_id")
    if atom_id == ATOM_ID:
        return {
            "atom_id": ATOM_ID,
            "phrase": AUTHORITY_PHRASE,
            "close": CLOSE_TERMINAL,
            "earn": EARN_TERMINAL,
            "invalid": INVALID_TERMINAL,
            "receipt_id": "EVIDENCE-EARLY-HOLDER-CONCENTRATION-H900-RUNTIME-001",
            "raw_root": "local/early_holder_concentration_h900_falsifier",
            "evidence_dir": "docs/evidence/early_holder_concentration_h900_falsifier",
        }
    if atom_id == CONFIRMATORY_ATOM_ID:
        return {
            "atom_id": CONFIRMATORY_ATOM_ID,
            "phrase": CONFIRMATORY_AUTHORITY_PHRASE,
            "close": CONFIRMATORY_CLOSE_TERMINAL,
            "earn": CONFIRMATORY_EARN_TERMINAL,
            "invalid": INVALID_TERMINAL,
            "receipt_id": "EVIDENCE-EARLY-HOLDER-CONCENTRATION-H900-CONFIRMATORY-RUNTIME-001",
            "raw_root": "local/early_holder_concentration_h900_confirmatory_oos",
            "evidence_dir": "docs/evidence/early_holder_concentration_h900_confirmatory_oos",
        }
    raise OrganicPressureError("ATOM_ID_NOT_IN_HOLDER_IDENTITY_ALLOWLIST")


def holder_identity_for_phrase(phrase: str) -> dict[str, str] | None:
    for atom_id in (ATOM_ID, CONFIRMATORY_ATOM_ID):
        identity = holder_identity({"atom_id": atom_id})
        if phrase == identity["phrase"]:
            return identity
    return None


def _parse_utc(value: object, code: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise OrganicPressureError(code)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise OrganicPressureError(code) from exc
    if parsed.tzinfo is None:
        raise OrganicPressureError(code)
    return parsed.astimezone(UTC)


def _finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    return value == value and value not in {float("inf"), float("-inf")}


def project_holder_concentration(
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
    audit = t5_row.get("audit")
    if not isinstance(pool, Mapping):
        result["reason"] = "REQUIRED_OBJECT_ABSENT"
        return result
    try:
        created_at = _parse_utc(pool.get("createdAt"), "FIRST_POOL_TIMESTAMP_INVALID")
        updated_at = _parse_utc(t5_row.get("updatedAt"), "UPDATED_TIMESTAMP_INVALID")
    except OrganicPressureError as exc:
        result["reason"] = str(exc)
        return result
    observed_at = snapshot_at.astimezone(UTC)
    age_seconds = (observed_at - created_at).total_seconds()
    result["age_seconds"] = age_seconds
    top_holders = audit.get("topHoldersPercentage") if isinstance(audit, Mapping) else None
    result["inputs"] = {
        "audit.topHoldersPercentage": top_holders,
        "liquidity": t5_row.get("liquidity"),
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
    liquidity = t5_row.get("liquidity")
    if not _finite_number(liquidity) or float(liquidity) < LIQUIDITY_USD_MIN:
        result["reason"] = "LIQUIDITY_BELOW_ICP_MIN"
        return result
    if not isinstance(audit, Mapping) or "topHoldersPercentage" not in audit:
        result["reason"] = "TOP_HOLDERS_PERCENTAGE_ABSENT"
        return result
    if not _finite_number(top_holders):
        result["reason"] = "TOP_HOLDERS_PERCENTAGE_INVALID"
        return result
    value = float(top_holders)
    if value < X_MIN or value > X_MAX:
        result["reason"] = "TOP_HOLDERS_PERCENTAGE_OUT_OF_RANGE"
        return result
    result["status"] = "ELIGIBLE"
    result["value"] = value
    result["x_available_at"] = observed_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    return result


def score_holder_campaign(rows: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    """Falsifier-only helper. Live path uses identity score_fn, not this function."""
    return score_sign_only_kendall(
        rows,
        min_decision_time_eligible=18,
        min_rankable_h900=14,
        expected_direction="NEGATIVE",
        close_terminal=CLOSE_TERMINAL,
        earn_terminal=EARN_TERMINAL,
        invalid_terminal=INVALID_TERMINAL,
    )


def validate_holder_concentration_policy(policy: Mapping[str, Any], *, root: Any) -> None:
    identity = holder_identity(policy)
    validate_policy(
        policy,
        root=root,
        expected_atom_id=identity["atom_id"],
        expected_authority_phrase=identity["phrase"],
        expected_schema=POLICY_SCHEMA,
        expected_x_formula=X_FORMULA,
        require_legacy_decision_rule=False,
    )
    population = policy.get("population")
    if not isinstance(population, Mapping):
        raise OrganicPressureError("POPULATION_INVALID")
    if population.get("icp_id") != ICP_ID:
        raise OrganicPressureError("ICP_ID_DRIFT")
    if float(population.get("liquidity_usd_min", -1)) != LIQUIDITY_USD_MIN:
        raise OrganicPressureError("LIQUIDITY_MIN_DRIFT")
    band = population.get("age_band_seconds")
    if not isinstance(band, Mapping):
        raise OrganicPressureError("AGE_BAND_INVALID")
    if int(band.get("min", -1)) != int(AGE_MIN_SECONDS):
        raise OrganicPressureError("AGE_MIN_DRIFT")
    if int(band.get("max_exclusive", -1)) != int(AGE_MAX_EXCLUSIVE_SECONDS):
        raise OrganicPressureError("AGE_MAX_DRIFT")
    snapshot = policy.get("decision_snapshot")
    if not isinstance(snapshot, Mapping):
        raise OrganicPressureError("DECISION_SNAPSHOT_INVALID")
    if snapshot.get("holder_count_surrogate") != "forbidden":
        raise OrganicPressureError("HOLDER_COUNT_SURROGATE_DRIFT")
    if snapshot.get("smoothing") != "forbidden":
        raise OrganicPressureError("SMOOTHING_DRIFT")
    decision = policy.get("decision_rule")
    if not isinstance(decision, Mapping):
        raise OrganicPressureError("DECISION_RULE_INVALID")
    if decision.get("close_terminal") != identity["close"]:
        raise OrganicPressureError("CLOSE_TERMINAL_DRIFT")
    if decision.get("earn_terminal") != identity["earn"]:
        raise OrganicPressureError("EARN_TERMINAL_DRIFT")
    if decision.get("invalid_terminal") != identity["invalid"]:
        raise OrganicPressureError("INVALID_TERMINAL_DRIFT")
    windows = policy.get("windows")
    if not isinstance(windows, Mapping):
        raise OrganicPressureError("WINDOWS_INVALID")
    if int(windows.get("max_windows", -1)) != 1 or windows.get("window_b") != "forbidden":
        raise OrganicPressureError("WINDOW_BUDGET_DRIFT")
    if windows.get("third_window") != "forbidden":
        raise OrganicPressureError("THIRD_WINDOW_DRIFT")
    if policy.get("factory_runner") != FACTORY_RUNNER:
        raise OrganicPressureError("FACTORY_RUNNER_PATH_DRIFT")
    if policy.get("factory_runner_sha256") != FACTORY_RUNNER_SHA256:
        raise OrganicPressureError("FACTORY_RUNNER_HASH_DRIFT")
    limitations = policy.get("limitations")
    if not isinstance(limitations, Mapping):
        raise OrganicPressureError("LIMITATIONS_INVALID")
    if limitations.get("jupiter_top_holders_pool_exclusion") != JUPITER_TOP_HOLDERS_POOL_EXCLUSION:
        raise OrganicPressureError("TOP_HOLDERS_POOL_EXCLUSION_LIMITATION_DRIFT")


def run_holder_concentration_campaign(policy: Mapping[str, Any], **kwargs: Any) -> dict[str, object]:
    identity = holder_identity(policy)

    def score_fn(rows: Sequence[Mapping[str, Any]]) -> dict[str, object]:
        return score_sign_only_kendall(
            rows,
            min_decision_time_eligible=18,
            min_rankable_h900=14,
            expected_direction="NEGATIVE",
            close_terminal=identity["close"],
            earn_terminal=identity["earn"],
            invalid_terminal=identity["invalid"],
        )

    receipt = run_campaign(
        policy,
        atom_id=identity["atom_id"],
        expected_authority_phrase=identity["phrase"],
        expected_schema=POLICY_SCHEMA,
        expected_x_formula=X_FORMULA,
        receipt_schema=RECEIPT_SCHEMA,
        close_terminal=identity["close"],
        project_x=project_holder_concentration,
        score_fn=score_fn,
        require_legacy_decision_rule=False,
        insufficient_yield_terminal=INVALID_TERMINAL,
        **kwargs,
    )
    receipt["limitations"] = {
        "jupiter_top_holders_pool_exclusion": JUPITER_TOP_HOLDERS_POOL_EXCLUSION,
    }
    return receipt
