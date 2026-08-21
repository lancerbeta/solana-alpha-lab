"""Frozen EARLY decision-time state hypothesis over Atom-1 retained bytes.

Offline; no network. The scientific question, bins and promotion gate are
pre-declared in the task contract and are not fitted to outcomes here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

ATOM_ID = "EARLY_STATE_TO_PAPER_VERTICAL_SLICE_V1"
CONFIG_RELATIVE = "configs/early_state_to_paper_vertical_slice_v1.yaml"

PROMOTION_CANDIDATE = "EARLY_STATE_SIGNAL_PROMOTION_CANDIDATE"
NO_DECISION_VALUE = "EARLY_STATE_NO_DECISION_VALUE"
TOO_SPARSE = "EXECUTION_SURFACE_TOO_SPARSE"
MIN_COHORT = 12
MIN_BIN_N = 8
MIN_COVERAGE = Decimal("0.7")


class EarlyStateError(ValueError):
    """Raised when the frozen evaluation cannot proceed fail-closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EarlyStateError(code)


def sha256_file(path: Path) -> str:
    return hashlib_sha256(path.read_bytes())


def hashlib_sha256(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()


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
    payload = yaml.safe_load((root / CONFIG_RELATIVE).read_bytes())
    _require(isinstance(payload, dict), "CONFIG_NOT_MAPPING")
    _require(payload.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    return payload


def verify_local_pins(root: Path, config: dict[str, Any]) -> None:
    """Fail-closed over retained A4_OUTSIDE_GIT bytes; absent bytes are an explicit gap."""

    for key, pin in config["pins"].items():
        path = root / pin["path"]
        _require(path.is_file(), f"PIN_MISSING:{key}")
        _require(sha256_file(path) == pin["sha256"], f"PIN_HASH_MISMATCH:{key}")


def build_cohort(
    root: Path,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Join decision-time snapshot rows with later-search rows by mint."""

    decision_body = json.loads(
        (root / config["pins"]["decision_search_body"]["path"]).read_text(encoding="utf-8")
    )
    later_body = json.loads(
        (root / config["pins"]["later_search_body"]["path"]).read_text(encoding="utf-8")
    )
    _require(isinstance(decision_body, list), "DECISION_BODY_NOT_LIST")
    _require(isinstance(later_body, list), "LATER_BODY_NOT_LIST")

    decision_time = datetime.fromisoformat(
        str(config["decision_time_observed_at"]).replace("Z", "+00:00")
    )
    liq_min = Decimal(str(config["icp"]["liquidity_usd_min"]))

    decision_rows: dict[str, dict[str, Any]] = {}
    for row in decision_body:
        if row.get("launchpad") != "pump.fun":
            continue
        liquidity = _decimal(row.get("liquidity"))
        created_raw = (row.get("firstPool") or {}).get("createdAt") if isinstance(row.get("firstPool"), dict) else None
        if liquidity is None or liquidity < liq_min or not isinstance(created_raw, str):
            continue
        created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        age = (decision_time - created).total_seconds()
        if not 300 <= age < 900:
            continue
        mint = str(row.get("id") or "")
        _require(bool(mint), "DECISION_ROW_MINT_MISSING")
        buys = _decimal((row.get("stats5m") or {}).get("buyOrganicVolume"))
        sells = _decimal((row.get("stats5m") or {}).get("sellOrganicVolume"))
        netflow_share: Decimal | None = None
        if buys is not None and sells is not None:
            denominator = buys + sells
            netflow_share = (buys - sells) / denominator if denominator > 0 else None
        decision_rows[mint] = {
            "mint": mint,
            "X_LIQUIDITY_USD": liquidity,
            "X_NETFLOW_SHARE": netflow_share,
            "decision_price_usd": price_of(row),
        }

    later_rows: dict[str, dict[str, Any]] = {}
    for row in later_body:
        mint = str(row.get("id") or "")
        if mint:
            later_rows[mint] = {"liquidity": _decimal(row.get("liquidity"))}

    cohort: list[dict[str, Any]] = []
    excluded_unknown_flow = 0
    for mint, drow in sorted(decision_rows.items()):
        later = later_rows.get(mint)
        later_liq = later["liquidity"] if later else None
        alive = (
            later is not None
            and row_is_pumpfun(later_body_by_mint(later_body, mint))
            and later_liq is not None
            and later_liq >= liq_min
        )
        ratio: Decimal | None = None
        if alive and drow["X_LIQUIDITY_USD"] > 0 and later_liq is not None:
            ratio = later_liq / drow["X_LIQUIDITY_USD"]
        entry = {
            **drow,
            "alive_and_liquid": alive,
            "Y_LIQUIDITY_RATIO": ratio,
        }
        if entry["X_NETFLOW_SHARE"] is None:
            excluded_unknown_flow += 1
        cohort.append(entry)
    return cohort, [excluded_unknown_flow]


def row_is_pumpfun(row: dict[str, Any] | None) -> bool:
    return isinstance(row, dict) and row.get("launchpad") == "pump.fun"


def later_body_by_mint(later_body: list[dict[str, Any]], mint: str) -> dict[str, Any] | None:
    for row in later_body:
        if str(row.get("id") or "") == mint:
            return row
    return None


def price_of(row: dict[str, Any]) -> Decimal | None:
    return _decimal(row.get("usdPrice"))


def bin_of(feature: str, op: str, threshold: Decimal, value: Decimal | None) -> str | None:
    if value is None:
        return None
    if op == ">=":
        return "HIGH" if value >= threshold else "LOW"
    if op == ">":
        return "HIGH" if value > threshold else "LOW"
    raise EarlyStateError("BIN_OP_INVALID")


def evaluate(root: Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config(root)
    for key, pin in config["pins"].items():
        path = root / pin["path"]
        _require(path.is_file(), f"PIN_MISSING:{key}")
        _require(sha256_file(path) == pin["sha256"], f"PIN_HASH_MISMATCH:{key}")
    verify_factory_runner(root, config)
    cohort, extras = build_cohort(root, config)
    joined_n = len(cohort)
    if joined_n < MIN_COHORT:
        return {
            "atom_id": ATOM_ID,
            "terminal": TOO_SPARSE,
            "joined_n": joined_n,
            "provider_api_rpc_wss_calls": 0,
            "non_claims": NON_CLAIMS(),
        }
    alive_n = sum(1 for row in cohort if row["alive_and_liquid"])
    rule = config["frozen_rule"]
    feature = str(rule["feature"])
    op = str(rule["bin_op"])
    threshold = Decimal(str(rule["bin_threshold"]))
    bins: dict[str, list[Decimal]] = {"HIGH": [], "LOW": []}
    unknown_excluded = int(extras[0])
    for row in cohort:
        label = bin_of(feature, op, threshold, row[feature])
        if label is None or row["Y_LIQUIDITY_RATIO"] is None:
            continue
        bins[label].append(row["Y_LIQUIDITY_RATIO"])
    stats: dict[str, Any] = {}
    for label in ("HIGH", "LOW"):
        values = bins[label]
        n = len(values)
        median = median_of(values)
        coverage = Decimal(n) / Decimal(joined_n) if joined_n else Decimal(0)
        spread_ok = len(set(values)) >= 2 if n else False
        stats[label] = {
            "n": n,
            "median_y": str(median) if median is not None else None,
            "coverage": str(coverage),
            "non_degenerate_spread": spread_ok,
        }
    high_first = stats["HIGH"]["n"] >= MIN_BIN_N and bool(stats["HIGH"]["non_degenerate_spread"])
    low_first = stats["LOW"]["n"] >= MIN_BIN_N and bool(stats["LOW"]["non_degenerate_spread"])
    coverage_ok = all(
        Decimal(s["coverage"]) >= MIN_COVERAGE for s in stats.values()
    )
    medians_comparable = (
        stats["HIGH"]["median_y"] is not None
        and stats["LOW"]["median_y"] is not None
    )
    higher_better = (
        medians_comparable
        and Decimal(stats["HIGH"]["median_y"]) > Decimal(stats["LOW"]["median_y"])
    )
    promoted = high_first and low_first and coverage_ok and higher_better
    terminal = PROMOTION_CANDIDATE if promoted else NO_DECISION_VALUE
    return {
        "atom_id": ATOM_ID,
        "stage": "FROZEN_STATE_EVALUATION",
        "terminal": terminal,
        "feature": feature,
        "bin_op": op,
        "bin_threshold": str(threshold),
        "joined_n": joined_n,
        "alive_and_liquid_n": alive_n,
        "unknown_netflow_excluded_n": unknown_excluded,
        "bins": stats,
        "promotion_gate": {
            "min_bin_n": MIN_BIN_N,
            "min_coverage": str(MIN_COVERAGE),
            "higher_bin_strictly_better_required": True,
            "passed": promoted,
        },
        "provider_api_rpc_wss_calls": 0,
        "credential_reads": 0,
        "non_claims": NON_CLAIMS(),
    }


def NON_CLAIMS() -> list[str]:
    return [
        "NO_ALPHA",
        "NO_NETRETURN",
        "NO_REAL_FILLS",
        "NO_MICRO_LIVE",
        "NO_THRESHOLD_SEARCH",
        "NO_ML",
        "SIMULATED_FILL_NEVER_REAL_FILL",
        "NO_CANONICAL_DONE",
    ]


def verify_factory_runner(root: Path, config: dict[str, Any]) -> None:
    runner_path = root / config["factory_runner"]
    _require(runner_path.is_file(), "FACTORY_RUNNER_MISSING")
    _require(
        sha256_file(runner_path) == config["factory_runner_sha256"],
        "FACTORY_RUNNER_DRIFT",
    )


def median_of(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def project_operational_view(
    root: Path,
    config: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    """Nine owner fields from the paper-plane runtime packet."""

    bots = runtime.get("bot_instances") or []
    positions = runtime.get("positions") or []
    open_positions = [
        p for p in positions if p.get("state") in {"OPEN", "PARTIAL", "ATTEMPTING"}
    ]
    unreconciled = [
        p for p in positions if p.get("state") not in {"CLOSED", "RECONCILED"}
    ]
    blocker = "NONE" if not unreconciled else "UNRECONCILED_POSITIONS_PRESENT"
    next_action = (
        "RESOLVE_UNRECONCILED_POSITIONS"
        if unreconciled
        else ("CONTINUE_PAPER_OBSERVATION" if bots else "START_PAPER_BOT")
    )
    return {
        "strategy": "; ".join(sorted({str(b.get("strategy_version")) for b in bots})) or "NONE",
        "bot": "; ".join(str(b.get("bot_instance_id")) for b in bots) or "NONE",
        "mode": "; ".join(str(b.get("mode")) for b in bots) or "NONE",
        "signal": runtime.get("last_signal_kind") or "UNKNOWN",
        "position": f"{len(open_positions)} open / {len(positions)} total",
        "exit_readiness": "READY_NEXT_OBSERVATION" if open_positions else "NOT_APPLICABLE",
        "reconciliation": "CLEAN" if not unreconciled else f"{len(unreconciled)} UNRECONCILED",
        "blocker": blocker,
        "next_safe_action": next_action,
    }
