"""Task-local ~30m seasoned H900 base-rate probe over the shared campaign."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from math import floor, inf
from statistics import median
from typing import Any

from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (
    MARKET_EXECUTION_UNAVAILABLE,
    OrganicPressureError,
    QUOTE_OBSERVED,
    run_campaign,
    validate_policy,
)

ATOM_ID = "SEASONED_30M_H900_BASE_RATE_PROBE_V1"
POPULATION_ID = "SEASONED_PUMPFUN_30M_PROBE_V1"
POLICY_SCHEMA = "smial.seasoned-30m-h900-base-rate-probe"
RECEIPT_SCHEMA = "smial.seasoned-30m-h900-base-rate-probe.runtime-receipt"
X_FORMULA = "SEASONED_DECISION_ELIGIBILITY_MARKER_CONSTANT_1.0"
ELIGIBILITY_MARKER_VALUE = 1.0
ELIGIBILITY_MARKER_ROLE = "NOT_A_SCIENTIFIC_X"
SCORE_KIND = "SEASONED_POSITIVE_EXECUTABLE_BASE_RATE"
EXPECTED_DIRECTION = "NOT_APPLICABLE"
SEASONING_SECONDS = 1800
AGE_MIN_SECONDS = 1800
AGE_MAX_EXCLUSIVE_SECONDS = 3600
LIQUIDITY_USD_MIN = 1000.0
NOTIONAL_ATOMIC = 10_000_000
FRICTION_FLOOR_LAMPORTS = 9_727_186
FRICTION_FLOOR_TOLERANCE_LAMPORTS = 20
NO_POSITIVE_MASS_TERMINAL = "SEASONED_30M_SURFACE_NO_POSITIVE_MASS"
SHOWS_POSITIVE_MASS_TERMINAL = "SEASONED_30M_SURFACE_SHOWS_POSITIVE_MASS"
INCONCLUSIVE_TERMINAL = "SEASONED_30M_SURFACE_INCONCLUSIVE"
INVALID_TERMINAL = "INVALID_EVIDENCE_REPLAN"
FACTORY_RUNNER = "src/solana_alpha_lab/factory/runner.py"
FACTORY_RUNNER_SHA256 = "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"
FIELD_PATHS = [
    "id",
    "launchpad",
    "liquidity",
    "firstPool.createdAt",
    "updatedAt",
]
AUTHORITY_PHRASE = (
    "OK SEASONED_30M_H900_BASE_RATE_PROBE_V1: one bounded Jupiter Free-key "
    "read-only campaign using a local process-environment key only; Tokens V2 "
    "/recent plus one bulk /tokens/v2/search for frozen mints plus quote-only "
    "/swap/v2/order; x-api-key header only; no .env read, no key in URL/log/"
    "receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid "
    "plan, second provider, retry or fallback; cash cap $0; call cap 60; "
    "global provider pace >=3s; task-local SEASONED_PUMPFUN_30M_PROBE_V1 "
    "population, not ICP-EARLY-PUMPFUN-V1; 24 fresh project-eligible recent "
    "candidates excluding all prior consumed research mints; wait until pool "
    "age >=1800s before the single bulk decision-time search snapshot; eligible "
    "only if 1800<=age<3600 and liquidity_usd>=1000 at that snapshot; no "
    "hypothesis X; quote-only BUY at decision and quote-only SELL at H900; one "
    "window only; positive-executable H900 base-rate probe; Factory runner "
    "unchanged; Strategy, Bot, Shadow, alpha and NetReturn forbidden."
)


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
    return value == value and value not in {inf, -inf}


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * q
    low = floor(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def project_seasoned_decision_eligibility(
    recent_row: Mapping[str, Any],
    t5_row: Mapping[str, Any] | None,
    snapshot_at: datetime,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "MISSING",
        "value": None,
        "field_paths": list(FIELD_PATHS),
        "inputs": {},
        "eligibility_marker_role": ELIGIBILITY_MARKER_ROLE,
        "population_id": POPULATION_ID,
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
        created_at = _parse_utc(pool.get("createdAt"), "FIRST_POOL_TIMESTAMP_INVALID")
        updated_at = _parse_utc(t5_row.get("updatedAt"), "UPDATED_TIMESTAMP_INVALID")
    except OrganicPressureError as exc:
        result["reason"] = str(exc)
        return result
    observed_at = snapshot_at.astimezone(UTC)
    age_seconds = (observed_at - created_at).total_seconds()
    result["age_seconds"] = age_seconds
    result["inputs"] = {
        "id": t5_row.get("id"),
        "launchpad": t5_row.get("launchpad"),
        "liquidity": t5_row.get("liquidity"),
        "firstPool.createdAt": pool.get("createdAt"),
        "updatedAt": t5_row.get("updatedAt"),
    }
    if created_at > observed_at:
        result["reason"] = "FIRST_POOL_TIMESTAMP_IN_FUTURE"
        return result
    if age_seconds < float(AGE_MIN_SECONDS):
        result["status"] = "TOO_YOUNG"
        result["reason"] = "POOL_AGE_BELOW_SEASONED_MIN"
        return result
    if age_seconds >= float(AGE_MAX_EXCLUSIVE_SECONDS):
        result["status"] = "TOO_OLD"
        result["reason"] = "POOL_AGE_OUTSIDE_SEASONED_MAX"
        return result
    if updated_at < created_at:
        result["reason"] = "UPDATED_TIMESTAMP_BEFORE_POOL_CREATION"
        return result
    if updated_at > observed_at:
        result["reason"] = "UPDATED_TIMESTAMP_IN_FUTURE"
        return result
    liquidity = t5_row.get("liquidity")
    if not _finite_number(liquidity) or float(liquidity) < LIQUIDITY_USD_MIN:
        result["reason"] = "LIQUIDITY_BELOW_MIN"
        return result
    result["status"] = "ELIGIBLE"
    result["value"] = ELIGIBILITY_MARKER_VALUE
    result["eligibility_marker"] = ELIGIBILITY_MARKER_VALUE
    return result


def summarize_predecision_attrition(
    candidate_observations: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    counts: dict[str, int] = {}
    eligible = 0
    for row in candidate_observations:
        status = str(row.get("x_status") or "MISSING")
        if status == "ELIGIBLE":
            eligible += 1
            continue
        reason = str(row.get("x_reason") or status)
        counts[reason] = counts.get(reason, 0) + 1
    return {
        "decision_time_eligible": eligible,
        "ineligible_count": sum(counts.values()),
        "reasons": dict(sorted(counts.items())),
    }


def score_seasoned_base_rate(rows: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    eligible = [row for row in rows if row.get("x_status") == "ELIGIBLE"]
    rankable = [
        row
        for row in eligible
        if row.get("h900_terminal") == QUOTE_OBSERVED and _finite_number(row.get("y"))
    ]
    meu = [row for row in eligible if row.get("h900_terminal") == MARKET_EXECUTION_UNAVAILABLE]
    y_values = [float(row["y"]) for row in rankable]
    positives = [value for value in y_values if value > 0]
    sell_out: list[int] = []
    near_floor = 0
    for row, value in zip(rankable, y_values, strict=True):
        h900 = row.get("h900")
        raw_out = h900.get("output_amount") if isinstance(h900, Mapping) else None
        if isinstance(raw_out, str) and raw_out.isdigit():
            lamports = int(raw_out)
        else:
            lamports = int(round((value + 1.0) * NOTIONAL_ATOMIC))
        sell_out.append(lamports)
        if abs(lamports - FRICTION_FLOOR_LAMPORTS) <= FRICTION_FLOOR_TOLERANCE_LAMPORTS:
            near_floor += 1
    median_y = median(y_values) if y_values else None
    payload: dict[str, object] = {
        "score_kind": SCORE_KIND,
        "eligibility_marker_role": ELIGIBILITY_MARKER_ROLE,
        "decision_time_eligible": len(eligible),
        "rankable_h900": len(rankable),
        "positive_executable_count": len(positives),
        "positive_executable_rate": (len(positives) / len(eligible)) if eligible else None,
        "rankable_positive_rate": (len(positives) / len(rankable)) if rankable else None,
        "median_y": median_y,
        "mean_y": (sum(y_values) / len(y_values)) if y_values else None,
        "p10_y": _percentile(y_values, 0.10),
        "p25_y": _percentile(y_values, 0.25),
        "p75_y": _percentile(y_values, 0.75),
        "p90_y": _percentile(y_values, 0.90),
        "min_y": min(y_values) if y_values else None,
        "max_y": max(y_values) if y_values else None,
        "distinct_y_count": len(set(y_values)),
        "meu_count": len(meu),
        "meu_rate": (len(meu) / len(eligible)) if eligible else None,
        "sell_out_lamports": sell_out,
        "near_friction_floor_count": near_floor,
        "near_friction_floor_share": (near_floor / len(rankable)) if rankable else None,
        "friction_floor_lamports": FRICTION_FLOOR_LAMPORTS,
        "invalid_class": None,
    }
    if len(eligible) < 18 or len(rankable) < 14:
        payload["terminal"] = INVALID_TERMINAL
        payload["invalid_class"] = "DATA"
        return payload
    if len(positives) == 0:
        payload["terminal"] = NO_POSITIVE_MASS_TERMINAL
        return payload
    if len(positives) >= 3 or (median_y is not None and median_y > 0):
        payload["terminal"] = SHOWS_POSITIVE_MASS_TERMINAL
        return payload
    payload["terminal"] = INCONCLUSIVE_TERMINAL
    return payload


def validate_seasoned_base_rate_policy(policy: Mapping[str, Any], *, root: Any) -> None:
    validate_policy(
        policy,
        root=root,
        expected_atom_id=ATOM_ID,
        expected_authority_phrase=AUTHORITY_PHRASE,
        expected_schema=POLICY_SCHEMA,
        expected_x_formula=X_FORMULA,
        require_legacy_decision_rule=False,
        expected_seasoning_seconds=SEASONING_SECONDS,
        expected_direction=EXPECTED_DIRECTION,
        expected_score_kind=SCORE_KIND,
    )
    population = policy.get("population")
    if not isinstance(population, Mapping):
        raise OrganicPressureError("POPULATION_INVALID")
    if population.get("icp_id") == "ICP-EARLY-PUMPFUN-V1":
        raise OrganicPressureError("ICP_EARLY_IDENTITY_FORBIDDEN")
    if population.get("population_id") != POPULATION_ID:
        raise OrganicPressureError("POPULATION_ID_DRIFT")
    if float(population.get("liquidity_usd_min", -1)) != LIQUIDITY_USD_MIN:
        raise OrganicPressureError("LIQUIDITY_MIN_DRIFT")
    band = population.get("age_band_seconds")
    if not isinstance(band, Mapping):
        raise OrganicPressureError("AGE_BAND_INVALID")
    if int(band.get("min", -1)) != AGE_MIN_SECONDS:
        raise OrganicPressureError("AGE_MIN_DRIFT")
    if int(band.get("max_exclusive", -1)) != AGE_MAX_EXCLUSIVE_SECONDS:
        raise OrganicPressureError("AGE_MAX_DRIFT")
    snapshot = policy.get("decision_snapshot")
    if not isinstance(snapshot, Mapping):
        raise OrganicPressureError("DECISION_SNAPSHOT_INVALID")
    if snapshot.get("hypothesis_x") != "forbidden":
        raise OrganicPressureError("HYPOTHESIS_X_NOT_FORBIDDEN")
    if snapshot.get("eligibility_marker_role") != ELIGIBILITY_MARKER_ROLE:
        raise OrganicPressureError("ELIGIBILITY_MARKER_ROLE_DRIFT")
    decision = policy.get("decision_rule")
    if not isinstance(decision, Mapping):
        raise OrganicPressureError("DECISION_RULE_INVALID")
    if decision.get("close_terminal") != NO_POSITIVE_MASS_TERMINAL:
        raise OrganicPressureError("CLOSE_TERMINAL_DRIFT")
    if decision.get("earn_terminal") != SHOWS_POSITIVE_MASS_TERMINAL:
        raise OrganicPressureError("EARN_TERMINAL_DRIFT")
    if decision.get("inconclusive_terminal") != INCONCLUSIVE_TERMINAL:
        raise OrganicPressureError("INCONCLUSIVE_TERMINAL_DRIFT")
    if decision.get("invalid_terminal") != INVALID_TERMINAL:
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


def classify_campaign_failure(receipt: Mapping[str, Any]) -> str:
    code = str(
        receipt.get("terminal_error_code")
        or receipt.get("terminal_error_code")
        or ""
    )
    discovery = receipt.get("discovery_observations")
    if isinstance(discovery, list):
        for row in discovery:
            if not isinstance(row, Mapping):
                continue
            code = f"{code} {row.get('terminal') or ''} {row.get('terminal_error') or ''}"
    for key in ("candidate_observations", "observations"):
        rows = receipt.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            code = (
                f"{code} {row.get('buy_terminal') or ''} "
                f"{row.get('h900_terminal') or ''} {row.get('terminal') or ''}"
            )
    if any(
        token in code
        for token in (
            "HTTP_",
            "TRANSPORT",
            "JSON",
            "PROVIDER",
            "PROVIDER_MEASUREMENT_FAILURE",
            "NOT_LIST",
        )
    ):
        return "PROVIDER"
    if any(token in code for token in ("CLOCK", "TIMESTAMP", "CONTRACT", "H900_EARLY", "H900_LATE")):
        return "TRUTH_SEMANTICS"
    if any(token in code for token in ("CALL_CAP", "CREDENTIAL", "RESERVATION", "JUPITER_API_KEY")):
        return "RUNTIME"
    return "DATA"


def run_seasoned_base_rate_campaign(policy: Mapping[str, Any], **kwargs: Any) -> dict[str, object]:
    receipt = run_campaign(
        policy,
        atom_id=ATOM_ID,
        expected_authority_phrase=AUTHORITY_PHRASE,
        expected_schema=POLICY_SCHEMA,
        expected_x_formula=X_FORMULA,
        receipt_schema=RECEIPT_SCHEMA,
        close_terminal=NO_POSITIVE_MASS_TERMINAL,
        project_x=project_seasoned_decision_eligibility,
        score_fn=score_seasoned_base_rate,
        require_legacy_decision_rule=False,
        insufficient_yield_terminal=INVALID_TERMINAL,
        expected_seasoning_seconds=SEASONING_SECONDS,
        expected_direction=EXPECTED_DIRECTION,
        expected_score_kind=SCORE_KIND,
        **kwargs,
    )
    observations = receipt.get("candidate_observations")
    if isinstance(observations, list):
        receipt["predecision_attrition"] = summarize_predecision_attrition(observations)
    receipt["population_id"] = POPULATION_ID
    receipt["eligibility_marker_role"] = ELIGIBILITY_MARKER_ROLE
    score = receipt.get("score")
    if receipt.get("terminal_outcome") == INVALID_TERMINAL:
        classified = classify_campaign_failure(receipt)
        scored_class = score.get("invalid_class") if isinstance(score, Mapping) else None
        if classified != "DATA":
            receipt["invalid_class"] = classified
        elif scored_class is not None:
            receipt["invalid_class"] = scored_class
        else:
            receipt["invalid_class"] = classified
    return receipt
