"""Zero-provider population-fit reconciliation over named Git receipts.

Not Factory core. Not live capture. Source stratum is not product population.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any, Mapping

import yaml

ATOM_ID = "IN_SCOPE_POPULATION_FIT_RECONCILIATION_V1"
CONFIG_RELATIVE = "configs/in_scope_population_fit_reconciliation_v1.yaml"
FACTORY_RUNNER = "src/solana_alpha_lab/factory/runner.py"
FACTORY_RUNNER_SHA256 = "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"
Y_FIELD = "y_quoted_liquidation_recovery"
Y_HORIZON_SECONDS = 900
NOTIONAL_ATOMIC = 10_000_000
EARLY_AGE = (300, 900)
SEASONED_AGE = (1800, 7201)
NOMINATE = "NOMINATE_IN_SCOPE_MATURITY_BOUNDARY_TEST"
STOP_BRANCH = "STOP_POPULATION_BRANCH"
INSUFFICIENT = "INSUFFICIENT_COMPARABLE_EVIDENCE"
REPLAN = "REPLAN_POPULATION_DEFINITION"
QUOTE_OBSERVED = "QUOTE_OBSERVED"
MEU = "MARKET_EXECUTION_UNAVAILABLE"
PROVIDER_FAIL = "PROVIDER_MEASUREMENT_FAILURE"
MISSING = "MISSING"


class PopulationFitError(ValueError):
    """Named Git receipts cannot be reconciled fail-closed."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PopulationFitError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _dec_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _quantile(values: list[Decimal], p: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = p * (len(ordered) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def population_band(age_seconds: Decimal | None) -> str:
    if age_seconds is None:
        return "UNKNOWN_AGE"
    if age_seconds < EARLY_AGE[0]:
        return "ULTRA_FRESH"
    if EARLY_AGE[0] <= age_seconds < EARLY_AGE[1]:
        return "EARLY"
    if EARLY_AGE[1] <= age_seconds < SEASONED_AGE[0]:
        return "BETWEEN_15_30"
    if SEASONED_AGE[0] <= age_seconds < SEASONED_AGE[1]:
        return "SEASONED"
    return "OLDER"


def classify_h900_terminal(raw: object) -> str:
    text = str(raw or "") or MISSING
    if text == QUOTE_OBSERVED:
        return QUOTE_OBSERVED
    if text == MEU:
        return MEU
    if text in {"PROVIDER_TYPED_FAILURE", "UNKNOWN_TYPED_FAILURE", PROVIDER_FAIL}:
        return PROVIDER_FAIL
    if text in {"", "None", MISSING, "NOT_ATTEMPTED", "EXPLICIT_GAP"}:
        return MISSING
    return PROVIDER_FAIL


def load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "CONFIG_INVALID")
    _require(loaded.get("atom_id") == ATOM_ID, "ATOM_DRIFT")
    _require(loaded.get("y_field") == Y_FIELD, "Y_FIELD_DRIFT")
    _require(int(loaded.get("y_horizon_seconds") or 0) == Y_HORIZON_SECONDS, "Y_HORIZON_DRIFT")
    _require(int(loaded.get("notional_atomic") or 0) == NOTIONAL_ATOMIC, "NOTIONAL_DRIFT")
    _require(
        tuple(int(v) for v in loaded.get("early_age_seconds") or ()) == EARLY_AGE,
        "EARLY_AGE_DRIFT",
    )
    _require(
        tuple(int(v) for v in loaded.get("seasoned_age_seconds") or ()) == SEASONED_AGE,
        "SEASONED_AGE_DRIFT",
    )
    _require(loaded.get("factory_runner") == FACTORY_RUNNER, "FACTORY_RUNNER_PATH_DRIFT")
    _require(
        str(loaded.get("factory_runner_sha256")) == FACTORY_RUNNER_SHA256,
        "FACTORY_RUNNER_SHA_DRIFT",
    )
    _require(
        sha256_file(root / FACTORY_RUNNER) == FACTORY_RUNNER_SHA256,
        "FACTORY_RUNNER_CHANGED",
    )
    _require(
        int((loaded.get("evidence_budget") or {}).get("provider_api_rpc_wss_calls", 1)) == 0,
        "PROVIDER_BUDGET_NOT_ZERO",
    )
    return loaded


def _load_pinned(root: Path, spec: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    rel = spec.get("path")
    expected = spec.get("sha256")
    _require(isinstance(rel, str) and isinstance(expected, str), f"{label}_PIN_INVALID")
    path = root / rel
    _require(path.is_file(), f"{label}_MISSING")
    payload = path.read_bytes()
    digest = sha256_bytes(payload)
    _require(digest == expected, f"{label}_SHA256_MISMATCH")
    loaded = json.loads(payload.decode("utf-8"))
    _require(isinstance(loaded, dict), f"{label}_JSON_INVALID")
    return loaded


def _stats(values: list[Decimal]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "median": None,
            "positive_share": None,
            "p25": None,
            "p75": None,
            "worst": None,
        }
    positives = sum(1 for value in values if value > 0)
    return {
        "n": len(values),
        "median": _dec_str(Decimal(str(median(values)))),
        "positive_share": _dec_str(Decimal(positives) / Decimal(len(values))),
        "p25": _dec_str(_quantile(values, Decimal("0.25"))),
        "p75": _dec_str(_quantile(values, Decimal("0.75"))),
        "worst": _dec_str(min(values)),
    }


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["mint"]),
        str(row["source_receipt_sha256"]),
        str(row["campaign_id"]),
        str(row["identity_id"]),
    )


def _overlay_index(overlay: Mapping[str, Any], *, expected_source_sha: str) -> dict[str, str]:
    _require(
        overlay.get("source_runtime_receipt_sha256") == expected_source_sha,
        "OVERLAY_SOURCE_SHA_DRIFT",
    )
    _require(
        overlay.get("source_atom_id") == "ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1",
        "OVERLAY_SOURCE_ATOM_DRIFT",
    )
    out: dict[str, str] = {}
    for item in overlay.get("observations") or []:
        row = _mapping(item, "OVERLAY_ROW_INVALID")
        mint = str(row.get("mint") or "")
        _require(mint != "", "OVERLAY_MINT_MISSING")
        out[mint] = classify_h900_terminal(row.get("h900_terminal"))
    return out


def _quote_native_rows(
    receipt: Mapping[str, Any],
    *,
    campaign_id: str,
    source_sha: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    capture = _mapping(receipt.get("capture") or {}, "CAPTURE_MISSING")
    _require(capture.get("accepted") is True, f"{campaign_id}_CAPTURE_NOT_ACCEPTED")
    _require(int(receipt.get("retries") or 0) == 0, f"{campaign_id}_RETRIES_PRESENT")
    cells = receipt.get("campaign", {}).get("cells") if isinstance(receipt.get("campaign"), dict) else None
    _require(isinstance(cells, list) and cells, f"{campaign_id}_CELLS_MISSING")
    frozen = {
        str(item.get("identity_id")): item
        for item in receipt.get("frozen_cells") or []
        if isinstance(item, Mapping)
    }
    buy_at: dict[str, datetime] = {}
    for obs in receipt.get("observations") or []:
        if not isinstance(obs, Mapping):
            continue
        ident = str(obs.get("identity_id") or "")
        kind = str(obs.get("kind") or "")
        observation_id = str(obs.get("observation_id") or "")
        horizon = obs.get("horizon_seconds")
        if kind == "SELL_H3600" or "SELL_H3600" in observation_id or horizon == 3600:
            continue
        if kind == "BUY_T0" or observation_id.endswith(":BUY_T0"):
            parsed = _parse_dt(obs.get("observed_at"))
            if parsed is not None:
                buy_at[ident] = parsed
    capture_at = str(
        receipt.get("panel_started_at")
        or _mapping(receipt.get("attempt_reservation") or {}, "RESERVATION_MISSING").get("started_at")
        or ""
    )
    rows: list[dict[str, Any]] = []
    for cell in cells:
        item = _mapping(cell, f"{campaign_id}_CELL_INVALID")
        ident = str(item.get("identity_id") or "")
        frozen_row = frozen.get(ident) or {}
        mint = str(frozen_row.get("mint") or "")
        _require(mint != "", f"{campaign_id}_{ident}_MINT_MISSING")
        notional = int(frozen_row.get("notional_atomic") or 0)
        _require(notional == NOTIONAL_ATOMIC, f"{campaign_id}_{ident}_NOTIONAL_DRIFT")
        stratum = str(frozen_row.get("stratum") or ident.split("_", 1)[0])
        created = _parse_dt(frozen_row.get("first_pool_created_at"))
        decision_at = buy_at.get(ident)
        age = None
        if created is not None and decision_at is not None:
            age = Decimal(str((decision_at - created).total_seconds()))
        y_status = str(item.get("y_status") or MISSING)
        y_equals_x = item.get("y_equals_x") is True
        y_value = _decimal(item.get(Y_FIELD)) if y_status == "OBSERVED" else None
        if y_status != "OBSERVED":
            y_value = None
        h900 = classify_h900_terminal(item.get("h900_terminal"))
        time_separated = bool(y_value is not None and not y_equals_x and h900 == QUOTE_OBSERVED)
        rows.append(
            {
                "source_receipt_sha256": source_sha,
                "campaign_id": campaign_id,
                "capture_at": capture_at,
                "identity_id": ident,
                "mint": mint,
                "source_stratum": stratum,
                "source_kind": str(frozen_row.get("source_kind") or ""),
                "launchpad_known": False,
                "population_admissibility": population_band(age),
                "age_seconds": _dec_str(age),
                "h900_terminal": h900,
                "y_if_numeric": _dec_str(y_value),
                "y_equals_x": y_equals_x,
                "time_separated": time_separated,
                "decision_time_eligible": True,
            }
        )
    overlay = receipt.get("veto") if isinstance(receipt.get("veto"), dict) else None
    if overlay is None and isinstance(receipt.get("t0_screen"), dict):
        overlay = receipt["t0_screen"]
    meta = {
        "campaign_id": campaign_id,
        "kind": "quote_native",
        "terminal_outcome": str(receipt.get("terminal_outcome") or receipt.get("terminal") or ""),
        "stratum_unstable": bool((overlay or {}).get("stratum_unstable")),
        "kept_strata": list((overlay or {}).get("kept_strata") or []),
        "capture_accepted": True,
        "searchable_y_kind": str(receipt.get("searchable_y_kind") or "SELL_H900"),
    }
    return rows, meta


def _early_path_rows(
    receipt: Mapping[str, Any],
    *,
    campaign_id: str,
    source_sha: str,
    overlay_by_mint: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _require(int(receipt.get("retries") or 0) == 0, f"{campaign_id}_RETRIES_PRESENT")
    observations = {
        str(item.get("mint")): item
        for item in receipt.get("observations") or []
        if isinstance(item, Mapping) and item.get("mint")
    }
    candidates = receipt.get("candidate_observations") or []
    _require(isinstance(candidates, list) and candidates, f"{campaign_id}_CANDIDATES_MISSING")
    capture_at = str(
        receipt.get("t0_reference_at")
        or _mapping(receipt.get("attempt_reservation") or {}, "RESERVATION_MISSING").get("started_at")
        or ""
    )
    rows: list[dict[str, Any]] = []
    for item in candidates:
        cand = _mapping(item, f"{campaign_id}_CANDIDATE_INVALID")
        mint = str(cand.get("mint") or "")
        _require(mint != "", f"{campaign_id}_CANDIDATE_MINT_MISSING")
        obs = observations.get(mint) or {}
        eligible = str(cand.get("x_status") or obs.get("x_status") or "") == "ELIGIBLE"
        age = _decimal(obs.get("age_seconds") if obs else cand.get("age_seconds"))
        raw_terminal = overlay_by_mint.get(mint) or classify_h900_terminal(obs.get("h900_terminal"))
        y_value = _decimal(obs.get("y")) if obs else None
        if raw_terminal != QUOTE_OBSERVED:
            y_value = None
        time_separated = bool(eligible and y_value is not None and raw_terminal == QUOTE_OBSERVED)
        rows.append(
            {
                "source_receipt_sha256": source_sha,
                "campaign_id": campaign_id,
                "capture_at": capture_at,
                "identity_id": mint,
                "mint": mint,
                "source_stratum": "RECENT",
                "source_kind": "LIVE_TOKENS_V2_RECENT",
                "launchpad_known": True,
                "population_admissibility": population_band(age),
                "age_seconds": _dec_str(age),
                "h900_terminal": raw_terminal if eligible else MISSING,
                "y_if_numeric": _dec_str(y_value) if eligible else None,
                "y_equals_x": False,
                "time_separated": time_separated,
                "decision_time_eligible": eligible,
            }
        )
    meta = {
        "campaign_id": campaign_id,
        "kind": "early_path",
        "terminal_outcome": str(receipt.get("terminal_outcome") or ""),
        "scientific_terminal_before_overlay": str((receipt.get("score") or {}).get("terminal") or ""),
        "stratum_unstable": False,
        "kept_strata": [],
        "capture_accepted": True,
        "searchable_y_kind": "SELL_H900",
        "one_arm_recent_corroboration": True,
    }
    return rows, meta


def _summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    numeric = [_decimal(row["y_if_numeric"]) for row in rows if row.get("time_separated")]
    values = [value for value in numeric if value is not None]
    ages = [
        value
        for value in (_decimal(row.get("age_seconds")) for row in rows)
        if value is not None
    ]
    return {
        "decision_time_eligible_n": sum(1 for row in rows if row.get("decision_time_eligible")),
        "time_separated_numeric_H900_n": len(values),
        "QUOTE_OBSERVED_n": sum(1 for row in rows if row.get("h900_terminal") == QUOTE_OBSERVED),
        "MARKET_EXECUTION_UNAVAILABLE_n": sum(1 for row in rows if row.get("h900_terminal") == MEU),
        "PROVIDER_MEASUREMENT_FAILURE_n": sum(
            1 for row in rows if row.get("h900_terminal") == PROVIDER_FAIL
        ),
        "y_equals_x_excluded_n": sum(1 for row in rows if row.get("y_equals_x")),
        "Y": _stats(values),
        "age_seconds": {
            "n": len(ages),
            "min": _dec_str(min(ages) if ages else None),
            "median": _dec_str(Decimal(str(median(ages))) if ages else None),
            "max": _dec_str(max(ages) if ages else None),
        },
        "population_bands": {
            band: sum(1 for row in rows if row.get("population_admissibility") == band)
            for band in (
                "ULTRA_FRESH",
                "EARLY",
                "BETWEEN_15_30",
                "SEASONED",
                "OLDER",
                "UNKNOWN_AGE",
            )
        },
    }


def _decide(rows: list[dict[str, Any]], campaigns: list[dict[str, Any]]) -> dict[str, Any]:
    y_kinds = {item.get("searchable_y_kind") for item in campaigns}
    comparable = y_kinds <= {"SELL_H900"} and len(campaigns) >= 3
    unstable = [item for item in campaigns if item.get("stratum_unstable")]
    early_rows = [
        row
        for row in rows
        if row.get("population_admissibility") == "EARLY"
        and row.get("time_separated")
        and row.get("source_stratum") != "TRADED"
        and row.get("source_kind") != "LIVE_TOKENS_V2_TOPTRADED"
    ]
    early_y = [_decimal(row["y_if_numeric"]) for row in early_rows]
    early_y = [value for value in early_y if value is not None]
    traded_in_early_age_n = sum(
        1
        for row in rows
        if row.get("population_admissibility") == "EARLY" and row.get("source_stratum") == "TRADED"
    )
    ultra_recent = [
        row
        for row in rows
        if row.get("source_stratum") == "RECENT"
        and row.get("population_admissibility") == "ULTRA_FRESH"
        and row.get("time_separated")
    ]
    ultra_y = [_decimal(row["y_if_numeric"]) for row in ultra_recent]
    ultra_y = [value for value in ultra_y if value is not None]
    early_geometry_poor = bool(early_y) and median(early_y) < 0 and all(value <= 0 for value in early_y)
    ultra_geometry_poor = bool(ultra_y) and median(ultra_y) < 0
    traded = [row for row in rows if row.get("source_stratum") == "TRADED"]
    traded_ages = [_decimal(row["age_seconds"]) for row in traded]
    traded_ages = [value for value in traded_ages if value is not None]
    traded_max = max(traded_ages) if traded_ages else None
    traded_not_product = bool(traded) and (
        any(row.get("source_kind") == "LIVE_TOKENS_V2_TOPTRADED" for row in traded)
        and (traded_max is None or traded_max > Decimal("14400") or not any(row.get("launchpad_known") for row in traded))
    )
    missing_age_n = sum(1 for row in rows if row.get("age_seconds") is None)
    pre_outcome_age = bool(rows) and missing_age_n == 0
    seasoned_source_n = sum(1 for row in rows if row.get("population_admissibility") == "SEASONED")
    criteria = {
        "independent_valid_windows": {
            "pass": len(campaigns) >= 3,
            "n": len(campaigns),
        },
        "material_source_stratum_instability": {
            "pass": len(unstable) >= 2,
            "campaigns": [item["campaign_id"] for item in unstable],
            "kept_strata": {item["campaign_id"]: item.get("kept_strata") for item in unstable},
        },
        "very_early_not_positive": {
            "pass": early_geometry_poor and ultra_geometry_poor,
            "early_n": len(early_y),
            "early_median": _dec_str(Decimal(str(median(early_y))) if early_y else None),
            "early_positive_n": sum(1 for value in early_y if value > 0),
            "traded_in_early_age_excluded_n": traded_in_early_age_n,
            "ultra_fresh_recent_n": len(ultra_y),
            "ultra_fresh_recent_median": _dec_str(Decimal(str(median(ultra_y))) if ultra_y else None),
        },
        "traded_not_product_population": {
            "pass": traded_not_product and len(unstable) >= 1,
            "traded_n": len(traded),
            "traded_age_max_seconds": _dec_str(traded_max),
            "launchpad_known_on_traded": False,
        },
        "maturity_definable_pre_outcome": {
            "pass": pre_outcome_age,
            "missing_age_n": missing_age_n,
            "seasoned_source_supply_n": seasoned_source_n,
            "bounds_changed_by_y": False,
        },
    }
    all_pass = all(item["pass"] for item in criteria.values())
    if not comparable:
        terminal = INSUFFICIENT
    elif all_pass:
        terminal = NOMINATE
    elif not criteria["maturity_definable_pre_outcome"]["pass"]:
        terminal = REPLAN
    else:
        terminal = STOP_BRANCH
    frozen = None
    if terminal == NOMINATE:
        frozen = {
            "immutable_for": "IN_SCOPE_POPULATION_AND_STATE_DISCOVERY_V1",
            "domain": {"network": "Solana", "launchpad": "pump.fun"},
            "EARLY": {"pool_age_seconds": [EARLY_AGE[0], EARLY_AGE[1]], "inclusive": "[5m, 15m)"},
            "SEASONED": {
                "pool_age_seconds": [SEASONED_AGE[0], SEASONED_AGE[1] - 1],
                "inclusive": "[30m, 120m]",
            },
            "COMMON": {
                "liquidity_usd_min": 1000,
                "quote_notional_sol": "0.01",
                "notional_atomic": NOTIONAL_ATOMIC,
                "exclude_consumed_mints": True,
                "decision_time_fields_only": True,
            },
            "source_does_not_define_population": True,
            "candidate_sources_allowed": ["/recent", "/toptraded/1h"],
            "reclassify_via": "tokens_v2_search_bulk",
        }
    return {
        "comparable_y_surface": comparable,
        "criteria": criteria,
        "terminal": terminal,
        "frozen_atom2_population": frozen,
    }


def reconcile(root: Path, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    loaded = dict(config or load_config(root))
    overlay_spec = _mapping(loaded.get("classification_overlay"), "OVERLAY_SPEC_MISSING")
    overlay = _load_pinned(root, overlay_spec, label="OVERLAY")
    market = loaded.get("market_receipts")
    _require(isinstance(market, list) and len(market) == 6, "MARKET_RECEIPT_COUNT")
    all_rows: list[dict[str, Any]] = []
    campaigns: list[dict[str, Any]] = []
    overlay_by_mint: dict[str, str] = {}
    seen: set[tuple[str, str, str, str]] = set()
    for spec in market:
        item = _mapping(spec, "MARKET_SPEC_INVALID")
        receipt = _load_pinned(root, item, label=str(item.get("campaign_id")))
        campaign_id = str(item.get("campaign_id"))
        source_sha = str(item.get("sha256"))
        kind = str(item.get("kind"))
        if kind == "quote_native":
            rows, meta = _quote_native_rows(receipt, campaign_id=campaign_id, source_sha=source_sha)
        elif kind == "early_path":
            overlay_by_mint = _overlay_index(overlay, expected_source_sha=source_sha)
            rows, meta = _early_path_rows(
                receipt,
                campaign_id=campaign_id,
                source_sha=source_sha,
                overlay_by_mint=overlay_by_mint,
            )
        else:
            raise PopulationFitError("UNKNOWN_RECEIPT_KIND")
        for row in rows:
            key = _row_key(row)
            _require(key not in seen, "DUPLICATE_OBSERVATION")
            seen.add(key)
        all_rows.extend(rows)
        campaigns.append(meta)
    matrix = []
    for campaign in campaigns:
        campaign_rows = [row for row in all_rows if row["campaign_id"] == campaign["campaign_id"]]
        strata = sorted({row["source_stratum"] for row in campaign_rows})
        by_stratum = {
            stratum: _summarize_group([row for row in campaign_rows if row["source_stratum"] == stratum])
            for stratum in strata
        }
        paired = None
        if set(strata) >= {"RECENT", "TRADED"}:
            recent = by_stratum["RECENT"]["Y"]
            traded = by_stratum["TRADED"]["Y"]
            if recent["median"] is not None and traded["median"] is not None:
                paired = {
                    "delta_median_Y": _dec_str(Decimal(traded["median"]) - Decimal(recent["median"])),
                    "delta_positive_share": _dec_str(
                        Decimal(traded["positive_share"] or "0") - Decimal(recent["positive_share"] or "0")
                    )
                    if recent["positive_share"] is not None and traded["positive_share"] is not None
                    else None,
                    "delta_MEU_rate": _dec_str(
                        (
                            Decimal(by_stratum["TRADED"]["MARKET_EXECUTION_UNAVAILABLE_n"])
                            / Decimal(max(1, by_stratum["TRADED"]["decision_time_eligible_n"]))
                        )
                        - (
                            Decimal(by_stratum["RECENT"]["MARKET_EXECUTION_UNAVAILABLE_n"])
                            / Decimal(max(1, by_stratum["RECENT"]["decision_time_eligible_n"]))
                        )
                    ),
                }
        matrix.append(
            {
                **campaign,
                "n_rows": len(campaign_rows),
                "by_source_stratum": by_stratum,
                "paired_source_deltas": paired,
            }
        )
    decision = _decide(all_rows, campaigns)
    mints = [row["mint"] for row in all_rows]
    return {
        "schema": "smial.in-scope-population-fit-reconciliation.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "provider_api_rpc_wss_calls": 0,
        "credential_reads": 0,
        "cash_spend_usd_cents": 0,
        "factory_runner_sha256": FACTORY_RUNNER_SHA256,
        "classification_overlay_used_as_market_observation": False,
        "duplicate_accounting": "PASS",
        "mint_reuse_across_campaigns": len(mints) - len(set(mints)),
        "row_count": len(all_rows),
        "campaign_matrix": matrix,
        "decision": decision,
        "rows": all_rows,
        "non_claims": list(loaded.get("non_claims") or []),
    }


def build_acceptance(runtime: Mapping[str, Any]) -> dict[str, Any]:
    decision = _mapping(runtime.get("decision"), "DECISION_MISSING")
    terminal = str(decision.get("terminal"))
    next_action = (
        "IN_SCOPE_POPULATION_AND_STATE_DISCOVERY_V1"
        if terminal == NOMINATE
        else "DO_NOT_START_ATOM_2"
    )
    return {
        "schema": "smial.in-scope-population-fit-reconciliation.acceptance",
        "schema_version": "1.0",
        "acceptance_id": "IN-SCOPE-POPULATION-FIT-RECONCILIATION-ACCEPTANCE-001",
        "as_of": "2026-08-21",
        "task_id": ATOM_ID,
        "verdict": terminal,
        "frozen_atom2_population": decision.get("frozen_atom2_population"),
        "next_safe_action": next_action,
        "provider_api_rpc_wss_calls": 0,
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "project_sources_disposition": {"kind": "NO_CHANGE"},
        "promotable": False,
        "non_claims": list(runtime.get("non_claims") or []),
    }
