"""Offline Stage A supply gate for frozen EARLY/SEASONED. No network."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.in_scope_population_fit_reconciliation import (
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    population_band,
)

ATOM_ID = "IN_SCOPE_POPULATION_AND_STATE_DISCOVERY_V1"
CONFIG_RELATIVE = "configs/in_scope_population_and_state_discovery_v1.yaml"
INSTANT_EMPTY = "INSTANT_RECENT_CANNOT_FILL_EARLY"
INSUFFICIENT = "INSUFFICIENT_IN_SCOPE_POPULATION_SUPPLY"
SUPPLY_PASS = "SUPPLY_GATE_PASS"
LIVE_BLOCKED = "LIVE_CAPTURE_BLOCKED_NO_OWNER_PHRASE"


class SupplyGateError(ValueError):
    """Pinned Git evidence cannot classify supply fail-closed."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SupplyGateError(code)


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


def load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE
    payload = yaml.safe_load(path.read_bytes())
    _require(isinstance(payload, dict), "CONFIG_NOT_MAPPING")
    _require(payload.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    runner = root / FACTORY_RUNNER
    _require(runner.is_file(), "FACTORY_RUNNER_MISSING")
    _require(sha256_file(runner) == FACTORY_RUNNER_SHA256, "FACTORY_RUNNER_DRIFT")
    _require(payload.get("factory_runner_sha256") == FACTORY_RUNNER_SHA256, "FACTORY_RUNNER_PIN_DRIFT")
    frozen_meta = payload["frozen_population"]
    frozen_path = root / frozen_meta["path"]
    _require(sha256_file(frozen_path) == frozen_meta["sha256"], "FROZEN_POPULATION_HASH_MISMATCH")
    for key in ("atom1_runtime", "early_path_runtime"):
        pin = payload["pins"][key]
        _require(sha256_file(root / pin["path"]) == pin["sha256"], f"PIN_HASH_MISMATCH:{key}")
    _require(payload.get("live_capture", {}).get("authorized") is False, "LIVE_CAPTURE_NOT_OFFLINE")
    return payload


def product_eligible(
    row: dict[str, Any],
    *,
    launchpad: str,
    liquidity_usd_min: Decimal,
    consumed: set[str],
) -> str | None:
    mint = str(row.get("mint") or "")
    if mint and mint in consumed:
        return None
    if row.get("launchpad") != launchpad:
        return None
    liquidity = _decimal(row.get("liquidity_usd"))
    if liquidity is None or liquidity < liquidity_usd_min:
        return None
    band = population_band(_decimal(row.get("age_seconds")))
    if band in {"EARLY", "SEASONED"}:
        return band
    return None


def score_supply(
    rows: list[dict[str, Any]],
    *,
    early_n_min: int,
    seasoned_n_min: int,
    launchpad: str,
    liquidity_usd_min: Decimal,
    consumed: set[str],
) -> dict[str, Any]:
    early: list[str] = []
    seasoned: list[str] = []
    seen: set[str] = set(consumed)
    excluded_no_launchpad = 0
    for row in rows:
        mint = str(row.get("mint") or "")
        if mint and mint in seen:
            continue
        if row.get("launchpad") in (None, "", "UNKNOWN"):
            excluded_no_launchpad += 1
        label = product_eligible(
            row,
            launchpad=launchpad,
            liquidity_usd_min=liquidity_usd_min,
            consumed=seen,
        )
        if not mint:
            mint = f"row-{len(early) + len(seasoned)}"
        if label == "EARLY":
            early.append(mint)
            seen.add(mint)
        elif label == "SEASONED":
            seasoned.append(mint)
            seen.add(mint)
    passed = len(early) >= early_n_min and len(seasoned) >= seasoned_n_min
    return {
        "pass": passed,
        "early_n": len(early),
        "seasoned_n": len(seasoned),
        "excluded_no_launchpad_n": excluded_no_launchpad,
        "terminal": SUPPLY_PASS if passed else INSUFFICIENT,
    }


def quote_native_recent_age_proof(atom1: dict[str, Any]) -> dict[str, Any]:
    campaigns = 0
    ultra_fresh_n = 0
    early_n = 0
    max_age: Decimal | None = None
    for campaign in atom1["campaign_matrix"]:
        if campaign.get("kind") != "quote_native":
            continue
        recent = campaign.get("by_source_stratum", {}).get("RECENT")
        _require(isinstance(recent, dict), "QUOTE_NATIVE_RECENT_MISSING")
        bands = recent.get("population_bands") or {}
        ages = recent.get("age_seconds") or {}
        band_early = int(bands.get("EARLY") or 0)
        band_ultra = int(bands.get("ULTRA_FRESH") or 0)
        age_max = _decimal(ages.get("max"))
        _require(age_max is not None, "QUOTE_NATIVE_RECENT_AGE_MISSING")
        _require(band_early == 0, "QUOTE_NATIVE_RECENT_EARLY_NOT_EMPTY")
        _require(age_max < Decimal("300"), "QUOTE_NATIVE_RECENT_NOT_ULTRA_FRESH")
        campaigns += 1
        ultra_fresh_n += band_ultra
        early_n += band_early
        max_age = age_max if max_age is None else max(max_age, age_max)
    _require(campaigns >= 1, "QUOTE_NATIVE_CAMPAIGN_MISSING")
    _require(ultra_fresh_n >= 1, "QUOTE_NATIVE_RECENT_ULTRA_FRESH_MISSING")
    return {
        "quote_native_recent_campaigns": campaigns,
        "early_n": early_n,
        "ultra_fresh_n": ultra_fresh_n,
        "max_age_seconds": str(max_age),
        "pass": False,
        "terminal": INSUFFICIENT,
    }


def _early_path_wait_rows(early_path: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in early_path.get("candidate_observations") or []:
        rows.append(
            {
                "mint": item.get("mint"),
                "source_stratum": "RECENT",
                "age_seconds": item.get("age_seconds"),
                "launchpad": None,
                "liquidity_usd": None,
            }
        )
    return rows


def reconcile(root: Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config(root)
    atom1 = json.loads((root / config["pins"]["atom1_runtime"]["path"]).read_text(encoding="utf-8"))
    early_path = json.loads((root / config["pins"]["early_path_runtime"]["path"]).read_text(encoding="utf-8"))
    supply_cfg = config["supply"]
    kwargs = {
        "early_n_min": int(supply_cfg["early_n_min"]),
        "seasoned_n_min": int(supply_cfg["seasoned_n_min"]),
        "launchpad": str(supply_cfg["launchpad"]),
        "liquidity_usd_min": Decimal(str(supply_cfg["liquidity_usd_min"])),
        "consumed": set(),
    }
    instant = quote_native_recent_age_proof(atom1)
    wait_rows = _early_path_wait_rows(early_path)
    wait_product = score_supply(wait_rows, **kwargs)
    wait_age_early_n = sum(
        1 for row in wait_rows if population_band(_decimal(row.get("age_seconds"))) == "EARLY"
    )
    _require(instant["early_n"] == 0, "INSTANT_RECENT_EARLY_NOT_EMPTY")
    harvest = {
        "instant_three_call": "FORBIDDEN_FOR_EARLY",
        "early": "WAIT_THEN_SEARCH",
        "seasoned": "TOPTRADED_SEARCH_RECLASSIFY",
        "wait_ages_in_early_band_n": wait_age_early_n,
        "wait_product_early_n_with_liquidity": wait_product["early_n"],
        "note": "early-path compact Git rows have EARLY ages; launchpad and liquidity are absent so they are not product EARLY yet",
    }
    _require(wait_age_early_n >= 12, "EARLY_PATH_WAIT_AGES_NOT_EARLY")
    _require(wait_product["pass"] is False, "MISSING_LIQUIDITY_MUST_NOT_PASS")
    _require(wait_product["early_n"] == 0, "MISSING_LIQUIDITY_COUNTED_AS_PRODUCT")
    return {
        "atom_id": ATOM_ID,
        "stage": "SUPPLY_GATE_OFFLINE",
        "provider_api_rpc_wss_calls": 0,
        "factory_runner_sha256": FACTORY_RUNNER_SHA256,
        "instant_recent_supply": instant,
        "wait_harvest_supply": wait_product,
        "harvest": harvest,
        "live_capture": {"authorized": False, "executed": False},
        "decision": {
            "terminal": INSTANT_EMPTY,
            "next": LIVE_BLOCKED,
            "stage_b_in_this_write_set": False,
        },
        "non_claims": [
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_QUOTES",
            "NO_STATE_RULES",
            "NO_LIVE_PROVIDER",
            "NO_CANONICAL_DONE",
        ],
    }


def build_acceptance(runtime: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "smial.in-scope-population-and-state-discovery.acceptance",
        "schema_version": "1.0",
        "acceptance_id": "IN-SCOPE-POPULATION-AND-STATE-DISCOVERY-ACCEPTANCE-001",
        "as_of": "2026-08-21",
        "task_id": ATOM_ID,
        "verdict": runtime["decision"]["terminal"],
        "harvest": runtime["harvest"],
        "next_safe_action": LIVE_BLOCKED,
        "stage_b_authorized": False,
        "provider_api_rpc_wss_calls": 0,
        "promotable": False,
        "non_claims": list(runtime["non_claims"]),
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "project_sources_disposition": {"kind": "NO_CHANGE"},
    }
