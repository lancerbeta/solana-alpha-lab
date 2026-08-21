"""Thin acceptance projector for the frozen EARLY ICP. Offline; no network.

Derives the canonical EARLY ICP freeze decision only from hash-pinned local
retained bytes of the already-run live Stage A attempt. Source channel and
population class are strictly different dimensions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

ATOM_ID = "EARLY_ICP_FREEZE_AND_MATURITY_BRANCH_CLOSE_V1"
CONFIG_RELATIVE = "configs/early_icp_freeze_and_maturity_branch_close_v1.yaml"

EARLY_ONLY_ICP_CONFIRMED = "EARLY_ONLY_ICP_CONFIRMED"
NOT_DURABLY_RETAINED = "LIVE_SUPPLY_EVIDENCE_NOT_DURABLY_RETAINED"
TOPTRADED_NOT_SAME_POPULATION = "TOPTRADED_NOT_SAME_POPULATION"
EXPLICIT_GAP_NO_BACKFILL = "EXPLICIT_GAP_NO_BACKFILL"

AGE_MIN_SECONDS = Decimal(300)
AGE_MAX_EXCLUSIVE_SECONDS = Decimal(900)
SEASONED_MIN_SECONDS = Decimal(1800)
SEASONED_MAX_INCLUSIVE_SECONDS = Decimal(7200)


class IcpFreezeError(ValueError):
    """Pinned retained evidence cannot prove the freeze fail-closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise IcpFreezeError(code)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _parse_utc(value: object) -> datetime:
    _require(isinstance(value, str) and value.endswith("Z"), "TIMESTAMP_NOT_UTC_Z")
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def load_config(root: Path) -> dict[str, Any]:
    payload = yaml.safe_load((root / CONFIG_RELATIVE).read_bytes())
    _require(isinstance(payload, dict), "CONFIG_NOT_MAPPING")
    _require(payload.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    runner = root / payload["factory_runner"]
    _require(runner.is_file(), "FACTORY_RUNNER_MISSING")
    _require(sha256_file(runner) == payload["factory_runner_sha256"], "FACTORY_RUNNER_DRIFT")
    for key, pin in payload["pins"].items():
        path = root / pin["path"]
        _require(path.is_file(), f"PIN_MISSING:{key}")
        _require(sha256_file(path) == pin["sha256"], f"PIN_HASH_MISMATCH:{key}")
    return payload


def canonical_candidate(
    *,
    mint: object,
    source_channel: str,
    observed_at: object,
    decision_time: datetime,
    row: dict[str, Any],
    liquidity_usd_min: Decimal,
) -> dict[str, Any] | None:
    """Project one raw provider row into canonical fields, or None if not a candidate.

    Population class derives only from launchpad + age band + liquidity at
    decision time. The source channel never grants membership.
    """
    launchpad = row.get("launchpad")
    liquidity = _decimal(row.get("liquidity"))
    created_raw = (row.get("firstPool") or {}).get("createdAt") if isinstance(row.get("firstPool"), dict) else None
    if not isinstance(created_raw, str):
        return None
    created = _parse_utc(created_raw)
    age_seconds = Decimal(str((decision_time - created).total_seconds()))
    if launchpad in (None, "", "UNKNOWN") or launchpad != "pump.fun":
        return None
    if liquidity is None or liquidity < liquidity_usd_min:
        return None
    if not (AGE_MIN_SECONDS <= age_seconds < AGE_MAX_EXCLUSIVE_SECONDS):
        return None
    return {
        "mint": str(mint),
        "source_channel": source_channel,
        "observed_at": observed_at,
        "pool_age_at_observation_seconds": str(age_seconds),
        "launchpad": launchpad,
        "liquidity_usd": str(liquidity),
        "population_class": "EARLY",
        "membership_reason": "LAUNCHPAD_AGE_LIQUIDITY_AT_DECISION_TIME",
    }


def project_cohort(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    search_body_path = root / config["pins"]["live_search_body"]["path"]
    rows = json.loads(search_body_path.read_text(encoding="utf-8"))
    _require(isinstance(rows, list), "SEARCH_BODY_NOT_LIST")
    decision_time = _parse_utc(config["decision_time_observed_at"])
    liquidity_min = Decimal(str(config["frozen_icp"]["liquidity_usd_min"]))

    candidates: list[dict[str, Any]] = []
    excluded_no_launchpad = 0
    excluded_older_than_120m = 0
    seen: set[str] = set()
    for row in rows:
        _require(isinstance(row, dict), "SEARCH_ROW_NOT_MAPPING")
        projected = canonical_candidate(
            mint=row.get("id"),
            source_channel="DISCOVERY:SEARCH_WAIT_THEN",
            observed_at=config["decision_time_observed_at"],
            decision_time=decision_time,
            row=row,
            liquidity_usd_min=liquidity_min,
        )
        if projected is None:
            launchpad = row.get("launchpad")
            created_raw = (row.get("firstPool") or {}).get("createdAt")
            if launchpad in (None, "", "UNKNOWN"):
                excluded_no_launchpad += 1
            elif isinstance(created_raw, str):
                age = Decimal(str((decision_time - _parse_utc(created_raw)).total_seconds()))
                if age > SEASONED_MAX_INCLUSIVE_SECONDS:
                    excluded_older_than_120m += 1
            continue
        mint = projected["mint"]
        if mint in seen:
            continue
        seen.add(mint)
        candidates.append(projected)

    early_n = len(candidates)
    _require(early_n >= int(config["supply_thresholds"]["early_n_min"]), "EARLY_N_BELOW_MINIMUM")
    return {
        "cohort_source_body_sha256": config["pins"]["live_search_body"]["sha256"],
        "decision_time_observed_at": config["decision_time_observed_at"],
        "candidates": candidates,
        "early_n": early_n,
        "excluded_no_launchpad_n": excluded_no_launchpad,
        "excluded_older_than_120m_n": excluded_older_than_120m,
    }


def project_seasoned_branch_close(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    traded_body_path = root / config["pins"]["live_traded_body"]["path"]
    rows = json.loads(traded_body_path.read_text(encoding="utf-8"))
    _require(isinstance(rows, list), "TRADED_BODY_NOT_LIST")
    decision_time = _parse_utc(config["decision_time_observed_at"])
    liquidity_min = Decimal(str(config["frozen_icp"]["liquidity_usd_min"]))

    total = 0
    product_seasoned_from_source = 0
    unknown_launchpad = 0
    for row in rows:
        _require(isinstance(row, dict), "TRADED_ROW_NOT_MAPPING")
        total += 1
        launchpad = row.get("launchpad")
        if launchpad in (None, "", "UNKNOWN"):
            unknown_launchpad += 1
            continue
        projected = canonical_candidate(
            mint=row.get("id"),
            source_channel="DISCOVERY:TRADED",
            observed_at=config["decision_time_observed_at"],
            decision_time=decision_time,
            row=row,
            liquidity_usd_min=liquidity_min,
        )
        if projected is not None:
            product_seasoned_from_source += 1
    return {
        "source_channel": "DISCOVERY:TRADED",
        "rows_n": total,
        "unknown_launchpad_n": unknown_launchpad,
        "product_seasoned_n_from_source_alone": product_seasoned_from_source,
        "terminal": TOPTRADED_NOT_SAME_POPULATION,
        "note": "source=/toptraded never grants population=SEASONED; acquisition design invalid, not seasoned supply failure",
    }


def project_maturity_probe(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    receipt_path = root / config["pins"]["maturity_probe_receipt"]["path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    _require(receipt.get("schema") == "smial.early-icp-freeze.maturity-probe-runtime-receipt", "PROBE_SCHEMA_DRIFT")
    _require(receipt.get("atom_id") == ATOM_ID, "PROBE_ATOM_ID_DRIFT")
    _require(receipt.get("cohort_source_body_sha256") == config["pins"]["live_search_body"]["sha256"], "PROBE_COHORT_DRIFT")
    _require(receipt.get("cohort_n") == 27, "PROBE_COHORT_N_DRIFT")
    _require(receipt.get("http_status") == 200, "PROBE_HTTP_NOT_200")
    decision_time = _parse_utc(config["decision_time_observed_at"])
    probe_time = _parse_utc(receipt["probe_observed_at"])
    elapsed_seconds = Decimal(str((probe_time - decision_time).total_seconds()))
    _require(elapsed_seconds >= 0, "PROBE_TIME_BEFORE_DECISION_TIME")
    inside_window = elapsed_seconds <= SEASONED_MAX_INCLUSIVE_SECONDS - AGE_MIN_SECONDS
    return {
        "executed_once": True,
        "probe_observed_at": receipt["probe_observed_at"],
        "alive_pumpfun_liq_ge_min_n": receipt["alive_pumpfun_liq_ge_min_n"],
        "same_population_seasoned_band_n": receipt["same_population_seasoned_band_n"],
        "inside_valid_observation_window": inside_window,
        "icp_change": "NONE",
        "note": "probe answers only whether maturity could matter later; frozen ICP stays EARLY either way",
    }


def reconcile(root: Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config(root)
    cohort = project_cohort(root, config)
    seasoned = project_seasoned_branch_close(root, config)
    probe = project_maturity_probe(root, config)
    live_receipt = json.loads(
        (root / config["pins"]["live_stage_a_receipt"]["path"]).read_text(encoding="utf-8")
    )
    _require(
        live_receipt.get("supply", {}).get("early_n") == cohort["early_n"],
        "RECEIPT_EARLY_N_MISMATCH",
    )
    return {
        "atom_id": ATOM_ID,
        "stage": config["stage"],
        "provider_api_rpc_wss_calls": 0,
        "factory_runner_sha256": config["factory_runner_sha256"],
        "frozen_icp": config["frozen_icp"],
        "early_cohort": {
            "acquisition": "WAIT_THEN_SEARCH",
            "early_n": cohort["early_n"],
            "excluded_no_launchpad_n": cohort["excluded_no_launchpad_n"],
            "excluded_older_than_120m_n": cohort["excluded_older_than_120m_n"],
            "cohort_source_body_sha256": cohort["cohort_source_body_sha256"],
        },
        "seasoned_branch_close": seasoned,
        "optional_maturity_probe": probe,
        "decision": {
            "terminal": EARLY_ONLY_ICP_CONFIRMED,
            "seasoned_branch_terminal": TOPTRADED_NOT_SAME_POPULATION,
            "maturity_on_critical_path": False,
        },
        "non_claims": [
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_QUOTES",
            "NO_STATE_RULES",
            "NO_STRATEGY_OR_BOT",
            "NO_NEW_PROVIDER",
            "NO_SECOND_TOPTRADED_ATTEMPT",
            "NO_THRESHOLD_RESCUE",
            "NO_CANONICAL_DONE",
        ],
    }


def build_acceptance(runtime: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "smial.early-icp-freeze.acceptance",
        "schema_version": "1.0",
        "acceptance_id": "EARLY-ICP-FREEZE-ACCEPTANCE-001",
        "as_of": "2026-08-21",
        "task_id": ATOM_ID,
        "verdict": runtime["decision"]["terminal"],
        "frozen_icp_id": runtime["frozen_icp"]["icp_id"],
        "seasoned_branch_terminal": runtime["decision"]["seasoned_branch_terminal"],
        "maturity_on_critical_path": runtime["decision"]["maturity_on_critical_path"],
        "next_safe_action": "ATOM2_EARLY_STATE_TO_PAPER_VERTICAL_SLICE_V1",
        "provider_api_rpc_wss_calls": 0,
        "promotable": False,
        "non_claims": list(runtime["non_claims"]),
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "project_sources_disposition": {"kind": "NO_CHANGE"},
    }
