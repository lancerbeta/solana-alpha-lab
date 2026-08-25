"""Decision-time BUY-quote microstructure vs frozen H900 tails.

Offline. No provider. No selector. Direction is within-window group contrast
only. Better-than-floor and worse-than-floor are never pooled as NOT_FLOOR for
the mutex terminal. Drop-window sensitivity cannot upgrade a terminal.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any, Mapping

import yaml

ATOM_ID = "BUY_DECISION_TIME_QUOTE_MICROSTRUCTURE_ASSOCIATION_V1"
CONFIG_RELATIVE = "configs/buy_decision_time_quote_microstructure_association_v1.yaml"
EXTRACTOR_ID = "BUY_DT_QUOTE_MS_EXTRACTOR_V1"
EXTRACTOR_SCHEMA_VERSION = "1.0"
CAPSULE_SCHEMA_VERSION = "capsule.buy-dt-quote-ms.v1"
DECISION_TIME_LABEL = "BUY_T0"
QUOTE_OBSERVED = "QUOTE_OBSERVED"

SEMANTICS_BLOCKED = "SEMANTICS_BLOCKED"
LOCAL_ONLY_NONREPRODUCIBLE = "LOCAL_ONLY_NONREPRODUCIBLE"
NULL_CLOSE = "RETAINED_ASSOCIATION_NULL_CLOSE"
DIRECTIONAL_WATCH = "RETAINED_ASSOCIATION_DIRECTIONAL_WATCH"
REPLICATION_WORTHY = "RETAINED_ASSOCIATION_REPLICATION_WORTHY"
TERMINALS = (
    SEMANTICS_BLOCKED,
    LOCAL_ONLY_NONREPRODUCIBLE,
    NULL_CLOSE,
    DIRECTIONAL_WATCH,
    REPLICATION_WORTHY,
)
FAMILY_TERMINAL_RANK = {
    REPLICATION_WORTHY: 2,
    DIRECTIONAL_WATCH: 1,
    NULL_CLOSE: 0,
}
FAMILIES = ("BETTER", "WORSE")
FORBIDDEN_CAPSULE_KEYS = (
    "taker",
    "transaction",
    "p_value",
    "pvalue",
    "priceImpact",
    "routePlan",
    "usdPrice",
    "lastTrade",
)
BUY_T0_BODY_SUFFIX = "_BUY_T0.body"
MINT_FROM_BUY_T0 = re.compile(r"([^/\\]+)_BUY_T0\.body$")


class AssociationError(ValueError):
    """Fail-closed extractor / association error."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_association_config(root: Path, path: Path | None = None) -> dict[str, Any]:
    target = path if path is not None else root / CONFIG_RELATIVE
    loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssociationError("CONFIG_INVALID")
    if loaded.get("atom_id") != ATOM_ID:
        raise AssociationError("CONFIG_ATOM_MISMATCH")
    if loaded.get("terminal_thresholds", {}).get("drop_may_upgrade") is not False:
        raise AssociationError("DROP_MAY_UPGRADE_NOT_FROZEN_FALSE")
    if loaded.get("terminal_thresholds", {}).get("combined_not_floor_forbidden") is not True:
        raise AssociationError("COMBINED_NOT_FLOOR_MUST_BE_FORBIDDEN")
    if loaded.get("terminal_thresholds", {}).get("absolute_x_threshold_forbidden") is not True:
        raise AssociationError("ABSOLUTE_X_THRESHOLD_MUST_BE_FORBIDDEN")
    predictors = list(loaded.get("association_predictors") or [])
    if predictors != ["X_PRICE_IMPACT"]:
        raise AssociationError("PREDICTOR_SET_LOCKED")
    gates = list(loaded.get("routeplan_eligibility_gates") or [])
    if "RP_ROUTE_COUNT" not in gates or "RP_FIRST_LEG_PERCENT" not in gates:
        raise AssociationError("ROUTEPLAN_MUST_REMAIN_GATES")
    return loaded


def _json_type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "str"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "other"


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    return parsed


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _mint_from_buy_t0_path(path: str) -> str | None:
    match = MINT_FROM_BUY_T0.search(path.replace("\\", "/"))
    return match.group(1) if match else None


def outcome_group(output_amount: int, floor: int, tolerance: int) -> str:
    if abs(output_amount - floor) <= tolerance:
        return "FLOOR"
    if output_amount < floor - tolerance:
        return "WORSE"
    return "BETTER"


def classify_family_signs(signs: list[int], *, min_w: int, majority_min: int) -> str:
    width = len(signs)
    n_plus = sum(1 for sign in signs if sign > 0)
    n_minus = sum(1 for sign in signs if sign < 0)
    majority = max(n_plus, n_minus)
    unanimous = width > 0 and (n_plus == width or n_minus == width)
    if width >= min_w and unanimous:
        return REPLICATION_WORTHY
    if width >= min_w and majority >= majority_min:
        return DIRECTIONAL_WATCH
    return NULL_CLOSE


def apply_drop_downgrade(full_terminal: str, remaining_signs: list[int], full_signs: list[int]) -> str:
    """Fragility test: may lower the full-cohort terminal, never raise it."""
    if full_terminal not in FAMILY_TERMINAL_RANK:
        raise AssociationError("FAMILY_TERMINAL_INVALID")
    if full_terminal == NULL_CLOSE:
        return NULL_CLOSE
    if not remaining_signs:
        return NULL_CLOSE
    n_plus = sum(1 for sign in remaining_signs if sign > 0)
    n_minus = sum(1 for sign in remaining_signs if sign < 0)
    remaining_unanimous = n_plus == len(remaining_signs) or n_minus == len(remaining_signs)
    remaining_direction = 1 if n_plus == len(remaining_signs) else -1 if n_minus == len(remaining_signs) else 0
    full_plus = sum(1 for sign in full_signs if sign > 0)
    full_minus = sum(1 for sign in full_signs if sign < 0)
    full_direction = 1 if full_plus > full_minus else -1 if full_minus > full_plus else 0
    if full_terminal == REPLICATION_WORTHY:
        if remaining_unanimous and remaining_direction == full_direction:
            return REPLICATION_WORTHY
        if remaining_direction == full_direction:
            return DIRECTIONAL_WATCH
        return NULL_CLOSE
    # DIRECTIONAL_WATCH: remaining unanimity must not upgrade.
    if remaining_direction == full_direction and remaining_direction != 0:
        return DIRECTIONAL_WATCH
    return NULL_CLOSE


def weaker_terminal(left: str, right: str) -> str:
    if FAMILY_TERMINAL_RANK[left] <= FAMILY_TERMINAL_RANK[right]:
        return left
    return right


def _load_receipt(root: Path, relative: str, expected_sha256: str) -> dict[str, Any]:
    path = root / relative
    payload = path.read_bytes()
    digest = sha256_bytes(payload)
    if digest != expected_sha256:
        raise AssociationError(f"GIT_RECEIPT_HASH_MISMATCH:{relative}")
    loaded = json.loads(payload.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise AssociationError("GIT_RECEIPT_INVALID")
    return loaded


def _buy_t0_manifests(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    retention = receipt.get("raw_retention")
    if not isinstance(retention, dict):
        return []
    manifests = retention.get("manifests")
    if not isinstance(manifests, list):
        return []
    out: list[dict[str, Any]] = []
    for item in manifests:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if isinstance(path, str) and path.replace("\\", "/").endswith(BUY_T0_BODY_SUFFIX):
            out.append(item)
    return out


def _parse_quote_features(body: object) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"status": "QUOTE_JSON_INVALID"}
    if "error" in body and "priceImpactPct" not in body:
        return {"status": "BUY_QUOTE_ERROR"}
    if "priceImpactPct" not in body or "routePlan" not in body:
        return {"status": "QUOTE_JSON_INVALID"}
    raw = body["priceImpactPct"]
    route_plan = body["routePlan"]
    parsed = _decimal_or_none(raw)
    route_count = len(route_plan) if isinstance(route_plan, list) else None
    first_percent = None
    if isinstance(route_plan, list) and route_plan and isinstance(route_plan[0], dict):
        percent = route_plan[0].get("percent")
        if isinstance(percent, int) and not isinstance(percent, bool):
            first_percent = percent
        elif isinstance(percent, str) and percent.isdigit():
            first_percent = int(percent)
    route_hash = None
    if isinstance(route_plan, list):
        route_hash = sha256_bytes(_canonical_json_bytes(route_plan))
    return {
        "status": "PARSED",
        "json_type": _json_type_name(raw),
        "x": parsed,
        "route_count": route_count,
        "first_percent": first_percent,
        "route_plan_content_sha256": route_hash,
    }


def _semantics_ok(parsed: Mapping[str, Any], *, require_unit_magnitude: bool = True) -> bool:
    x = parsed.get("x")
    magnitude_ok = True if not require_unit_magnitude else (isinstance(x, Decimal) and abs(x) < Decimal("1"))
    return (
        parsed.get("status") == "PARSED"
        and parsed.get("json_type") == "str"
        and isinstance(x, Decimal)
        and magnitude_ok
        and parsed.get("route_count") == 1
        and parsed.get("first_percent") == 100
    )


def _git_observation_map(receipt: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = receipt.get("observations")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("mint"), str):
            out[row["mint"]] = row
    return out


def _h900_output_amount(row: Mapping[str, Any]) -> int | None:
    h900 = row.get("h900")
    if not isinstance(h900, dict):
        return None
    raw = h900.get("output_amount")
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def extract_window_rows(
    root: Path,
    window: Mapping[str, Any],
    *,
    primary: bool,
    floor: int,
    tolerance: int,
) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (run_blocker, semantics_candidates, capsule_rows)."""
    window_id = str(window["window_id"])
    receipt = _load_receipt(root, str(window["git_receipt_path"]), str(window["git_receipt_sha256"]))
    a4_root = root / str(window["a4_root"])
    manifests = _buy_t0_manifests(receipt)
    observations = _git_observation_map(receipt)
    if not a4_root.is_dir():
        return LOCAL_ONLY_NONREPRODUCIBLE, [], []
    run_dirs = {(a4_root / item["path"]).parent for item in manifests if isinstance(item.get("path"), str)}
    if manifests and any(not path.is_dir() for path in run_dirs):
        return LOCAL_ONLY_NONREPRODUCIBLE, [], []

    present_mismatch = False
    semantics_candidates: list[dict[str, Any]] = []
    by_mint: dict[str, dict[str, Any]] = {}
    for item in manifests:
        rel = str(item["path"]).replace("\\", "/")
        mint = _mint_from_buy_t0_path(rel)
        if mint is None:
            continue
        body_path = a4_root / rel
        record = {
            "window_id": window_id,
            "mint": mint,
            "raw_retention_path": rel,
            "raw_body_sha256": item.get("sha256") if isinstance(item.get("sha256"), str) else None,
            "manifest_sha256": item.get("sha256") if isinstance(item.get("sha256"), str) else None,
        }
        if not body_path.is_file():
            record["file_status"] = "MISSING"
            by_mint[mint] = record
            continue
        digest = sha256_file(body_path)
        record["file_sha256"] = digest
        if digest != item.get("sha256"):
            present_mismatch = True
            record["file_status"] = "HASH_MISMATCH"
            by_mint[mint] = record
            continue
        record["file_status"] = "HASH_BOUND"
        try:
            body = json.loads(body_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            record["parsed"] = {"status": "QUOTE_JSON_INVALID"}
            by_mint[mint] = record
            continue
        parsed = _parse_quote_features(body)
        record["parsed"] = parsed
        by_mint[mint] = record
        if parsed.get("status") == "PARSED":
            semantics_candidates.append(parsed)

    if present_mismatch:
        return LOCAL_ONLY_NONREPRODUCIBLE, semantics_candidates, []

    mints = sorted(set(observations) | set(by_mint))
    rows: list[dict[str, Any]] = []
    for mint in mints:
        local = by_mint.get(mint, {})
        git_row = observations.get(mint)
        parsed = local.get("parsed") if isinstance(local.get("parsed"), dict) else {}
        exclusion = None
        if not primary:
            exclusion = "WINDOW_NOT_PRIMARY"
        elif mint not in by_mint:
            exclusion = "NO_LITERAL_BUY_T0"
        elif local.get("file_status") == "MISSING":
            exclusion = "A4_BODY_MISSING"
        elif local.get("file_status") == "HASH_MISMATCH":
            exclusion = "HASH_MISMATCH"
        elif parsed.get("status") == "QUOTE_JSON_INVALID":
            exclusion = "QUOTE_JSON_INVALID"
        elif parsed.get("status") == "BUY_QUOTE_ERROR":
            exclusion = "BUY_QUOTE_ERROR"
        elif git_row is None:
            exclusion = "GIT_ROW_MISSING"
        elif git_row.get("h900_terminal") != QUOTE_OBSERVED or git_row.get("y") is None:
            exclusion = "NOT_RANKABLE_H900"
        else:
            amount = _h900_output_amount(git_row)
            if amount is None:
                exclusion = "OUTPUT_AMOUNT_MISSING"

        amount = _h900_output_amount(git_row) if git_row is not None else None
        group = None
        if exclusion is None and amount is not None:
            group = outcome_group(amount, floor, tolerance)
        x_value = parsed.get("x") if isinstance(parsed, dict) else None
        in_primary = (
            primary
            and exclusion is None
            and group in {"FLOOR", "WORSE", "BETTER"}
            and _semantics_ok(parsed if isinstance(parsed, dict) else {})
        )
        rows.append(
            {
                "schema_version": CAPSULE_SCHEMA_VERSION,
                "window_id": window_id,
                "mint": mint,
                "decision_time_label": DECISION_TIME_LABEL,
                "git_receipt_path": window["git_receipt_path"],
                "git_receipt_sha256": window["git_receipt_sha256"],
                "raw_retention_path": local.get("raw_retention_path"),
                "raw_body_sha256": local.get("file_sha256") or local.get("raw_body_sha256"),
                "extractor_id": EXTRACTOR_ID,
                "extractor_schema_version": EXTRACTOR_SCHEMA_VERSION,
                "x_price_impact_raw_json_type": parsed.get("json_type") if parsed else None,
                "x_price_impact_decimal": format(x_value, "f") if isinstance(x_value, Decimal) else None,
                "rp_route_count": parsed.get("route_count") if parsed else None,
                "rp_first_leg_percent": parsed.get("first_percent") if parsed else None,
                "route_plan_content_sha256": parsed.get("route_plan_content_sha256") if parsed else None,
                "y_h900": git_row.get("y") if git_row is not None else None,
                "h900_output_amount": amount,
                "outcome_group": group,
                "exclusion_reason": exclusion,
                "in_primary_analysis": in_primary,
            }
        )
    return None, semantics_candidates, rows


def _window_family_stats(rows: list[dict[str, Any]], family: str, min_rows: int, min_floor: int, min_family: int) -> dict[str, Any]:
    analysis = [row for row in rows if row.get("in_primary_analysis") is True]
    floor_x = [Decimal(str(row["x_price_impact_decimal"])) for row in analysis if row.get("outcome_group") == "FLOOR"]
    family_x = [Decimal(str(row["x_price_impact_decimal"])) for row in analysis if row.get("outcome_group") == family]
    n_worse = sum(1 for row in analysis if row.get("outcome_group") == "WORSE")
    n_better = sum(1 for row in analysis if row.get("outcome_group") == "BETTER")
    delta = None
    sign: int | None = None
    if floor_x and family_x:
        delta = median(family_x) - median(floor_x)
        if delta > 0:
            sign = 1
        elif delta < 0:
            sign = -1
    informative = (
        len(analysis) >= min_rows
        and len(floor_x) >= min_floor
        and len(family_x) >= min_family
        and sign is not None
    )
    return {
        "n_rows": len(analysis),
        "n_tokens": len({row["mint"] for row in analysis}),
        "n_floor": len(floor_x),
        "n_family": len(family_x),
        "n_worse": n_worse,
        "n_better": n_better,
        "delta": format(delta, "f") if isinstance(delta, Decimal) else None,
        "sign": sign,
        "informative": informative,
    }


def _row_semantics_parsed(row: Mapping[str, Any]) -> dict[str, Any]:
    x = _decimal_or_none(row.get("x_price_impact_decimal"))
    json_type = row.get("x_price_impact_raw_json_type")
    status = "PARSED" if x is not None or json_type else "QUOTE_JSON_INVALID"
    return {
        "status": status,
        "json_type": json_type,
        "x": x,
        "route_count": row.get("rp_route_count"),
        "first_percent": row.get("rp_first_leg_percent"),
    }


def _row_outcome_group(row: Mapping[str, Any], floor: int, tolerance: int) -> str | None:
    amount = row.get("h900_output_amount")
    if isinstance(amount, bool) or amount is None:
        return None
    if isinstance(amount, int):
        return outcome_group(amount, floor, tolerance)
    if isinstance(amount, str) and amount.lstrip("-").isdigit():
        return outcome_group(int(amount), floor, tolerance)
    return None


def capsule_semantics_blocked(
    rows: list[dict[str, Any]],
    primary_ids: list[str],
    *,
    require_unit_magnitude: bool = True,
) -> bool:
    skip = {
        "WINDOW_NOT_PRIMARY",
        "NO_LITERAL_BUY_T0",
        "A4_BODY_MISSING",
        "HASH_MISMATCH",
        "QUOTE_JSON_INVALID",
        "BUY_QUOTE_ERROR",
    }
    for row in rows:
        if str(row.get("window_id")) not in primary_ids:
            continue
        if row.get("exclusion_reason") in skip:
            continue
        if not _semantics_ok(
            _row_semantics_parsed(row), require_unit_magnitude=require_unit_magnitude
        ):
            return True
    return False


def load_capsule_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return rows
    for line in text.splitlines():
        if not line.strip():
            continue
        loaded = json.loads(line)
        if not isinstance(loaded, dict):
            raise AssociationError("CAPSULE_ROW_INVALID")
        _forbid_capsule_keys(loaded)
        rows.append(loaded)
    return rows


def associate_from_capsule(
    rows: list[dict[str, Any]],
    config: Mapping[str, Any],
    *,
    semantics_blocked: bool = False,
    local_only: bool = False,
    require_unit_magnitude: bool = True,
) -> dict[str, Any]:
    if local_only:
        return _blocked_result(LOCAL_ONLY_NONREPRODUCIBLE, config, rows)
    primary_ids = [str(item["window_id"]) for item in config["primary_windows"]]
    if semantics_blocked or capsule_semantics_blocked(
        rows, primary_ids, require_unit_magnitude=require_unit_magnitude
    ):
        return _blocked_result(SEMANTICS_BLOCKED, config, rows)
    if any(key in json.dumps(rows) for key in ("p_value", "pvalue")):
        raise AssociationError("P_VALUE_THEATRE_FORBIDDEN")
    floor = int(config["floor"]["lamports"])
    tolerance = int(config["floor"]["tolerance_lamports"])
    normalized: list[dict[str, Any]] = []
    for row in rows:
        copy = dict(row)
        group = _row_outcome_group(copy, floor, tolerance)
        copy["outcome_group"] = group
        copy["in_primary_analysis"] = (
            str(copy.get("window_id")) in primary_ids
            and copy.get("exclusion_reason") is None
            and group in {"FLOOR", "WORSE", "BETTER"}
            and _semantics_ok(
                _row_semantics_parsed(copy), require_unit_magnitude=require_unit_magnitude
            )
        )
        normalized.append(copy)
    rows = normalized
    thresholds = config["terminal_thresholds"]
    informative_cfg = config["informative_window"]
    min_w = int(thresholds["min_informative_windows"])
    majority_min = int(thresholds["majority_min"])
    by_window: dict[str, list[dict[str, Any]]] = {window_id: [] for window_id in primary_ids}
    for row in rows:
        if row.get("window_id") in by_window:
            by_window[str(row["window_id"])].append(row)
    if any(str(row.get("window_id")) == "W-VL" and row.get("in_primary_analysis") is True for row in rows):
        raise AssociationError("W_VL_IN_PRIMARY")

    family_results: dict[str, Any] = {}
    family_terminals: dict[str, str] = {}
    for family in FAMILIES:
        per_window = []
        signs: list[int] = []
        informative_meta: list[dict[str, Any]] = []
        for window_id in primary_ids:
            stats = _window_family_stats(
                by_window[window_id],
                family,
                int(informative_cfg["min_analysis_rows"]),
                int(informative_cfg["min_floor_n"]),
                int(informative_cfg["min_family_n"]),
            )
            stats["window_id"] = window_id
            per_window.append(stats)
            if stats["informative"] is True and isinstance(stats["sign"], int):
                signs.append(int(stats["sign"]))
                informative_meta.append(
                    {
                        "window_id": window_id,
                        "sign": int(stats["sign"]),
                        "n_family": int(stats["n_family"]),
                    }
                )
        full_terminal = classify_family_signs(signs, min_w=min_w, majority_min=majority_min)
        dropped_window = None
        remaining_signs = list(signs)
        if informative_meta:
            dropped = min(informative_meta, key=lambda item: (item["n_family"], item["window_id"]))
            dropped_window = dropped["window_id"]
            remaining_signs = [item["sign"] for item in informative_meta if item["window_id"] != dropped_window]
        family_terminal = apply_drop_downgrade(full_terminal, remaining_signs, signs)
        family_results[family] = {
            "full_cohort_terminal": full_terminal,
            "terminal": family_terminal,
            "n_informative_windows": len(signs),
            "n_plus": sum(1 for sign in signs if sign > 0),
            "n_minus": sum(1 for sign in signs if sign < 0),
            "dropped_window_id": dropped_window,
            "per_window": per_window,
        }
        family_terminals[family] = family_terminal

    overall = weaker_terminal(family_terminals["BETTER"], family_terminals["WORSE"])
    analysis_rows = [row for row in rows if row.get("in_primary_analysis") is True]
    payload = {
        "atom_id": ATOM_ID,
        "terminal": overall,
        "family_terminals": family_terminals,
        "families": family_results,
        "n_rows_extracted": len(rows),
        "n_rows_primary_analysis": len(analysis_rows),
        "n_tokens": len({row["mint"] for row in analysis_rows}),
        "n_informative_windows_better": family_results["BETTER"]["n_informative_windows"],
        "n_informative_windows_worse": family_results["WORSE"]["n_informative_windows"],
        "association_predictors": list(config["association_predictors"]),
        "routeplan_eligibility_gates": list(config["routeplan_eligibility_gates"]),
        "next_action": config["next_by_terminal"][overall],
        "production_selector_authorized": False,
        "unit_assumption": config["unit_assumption"],
        "unit_assumption_is_fact": False,
    }
    _assert_single_terminal(payload)
    return payload


def _blocked_result(terminal: str, config: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "atom_id": ATOM_ID,
        "terminal": terminal,
        "family_terminals": {"BETTER": None, "WORSE": None},
        "families": {},
        "n_rows_extracted": len(rows),
        "n_rows_primary_analysis": 0,
        "n_tokens": 0,
        "n_informative_windows_better": 0,
        "n_informative_windows_worse": 0,
        "association_predictors": list(config["association_predictors"]),
        "routeplan_eligibility_gates": list(config["routeplan_eligibility_gates"]),
        "next_action": config["next_by_terminal"][terminal],
        "production_selector_authorized": False,
        "unit_assumption": config["unit_assumption"],
        "unit_assumption_is_fact": False,
    }
    _assert_single_terminal(payload)
    return payload


def _assert_single_terminal(payload: Mapping[str, Any]) -> None:
    found = [key for key in TERMINALS if payload.get("terminal") == key]
    if len(found) != 1:
        raise AssociationError("TERMINAL_MUTEX")
    if payload.get("production_selector_authorized") is not False:
        raise AssociationError("SELECTOR_FORBIDDEN")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if "p_value" in encoded or "pvalue" in encoded:
        raise AssociationError("P_VALUE_THEATRE_FORBIDDEN")


def rescale_invariant(rows: list[dict[str, Any]], config: Mapping[str, Any], factor: int = 100) -> bool:
    base = associate_from_capsule(rows, config)
    scaled: list[dict[str, Any]] = []
    for row in rows:
        copy = dict(row)
        raw = copy.get("x_price_impact_decimal")
        if isinstance(raw, str):
            copy["x_price_impact_decimal"] = format(Decimal(raw) * Decimal(factor), "f")
        scaled.append(copy)
    other = associate_from_capsule(scaled, config, require_unit_magnitude=False)
    return (
        base["terminal"] == other["terminal"]
        and base["family_terminals"] == other["family_terminals"]
        and base["n_informative_windows_better"] == other["n_informative_windows_better"]
        and base["n_informative_windows_worse"] == other["n_informative_windows_worse"]
    )


def _forbid_capsule_keys(row: Mapping[str, Any]) -> None:
    encoded = json.dumps(row, ensure_ascii=False)
    for key in FORBIDDEN_CAPSULE_KEYS:
        if f'"{key}"' in encoded:
            raise AssociationError(f"FORBIDDEN_CAPSULE_KEY:{key}")


def run_association(root: Path, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    loaded = dict(config or load_association_config(root))
    floor = int(loaded["floor"]["lamports"])
    tolerance = int(loaded["floor"]["tolerance_lamports"])
    rows: list[dict[str, Any]] = []
    semantics_pool: list[dict[str, Any]] = []
    local_only = False
    for window in loaded["primary_windows"]:
        blocker, candidates, window_rows = extract_window_rows(
            root, window, primary=True, floor=floor, tolerance=tolerance
        )
        if blocker == LOCAL_ONLY_NONREPRODUCIBLE:
            local_only = True
        semantics_pool.extend(candidates)
        rows.extend(window_rows)
    semantics_blocked = (not local_only) and any(not _semantics_ok(item) for item in semantics_pool)
    for row in rows:
        _forbid_capsule_keys(row)
        if row.get("decision_time_label") != DECISION_TIME_LABEL:
            raise AssociationError("DECISION_TIME_LABEL_LOCKED")
    primary_locked = associate_from_capsule(
        rows, loaded, semantics_blocked=semantics_blocked, local_only=local_only
    )
    appendix = None
    sensitivity = loaded.get("sensitivity_window")
    if isinstance(sensitivity, dict) and primary_locked["terminal"] not in {SEMANTICS_BLOCKED, LOCAL_ONLY_NONREPRODUCIBLE}:
        _blocker, _cand, vl_rows = extract_window_rows(
            root,
            {
                "window_id": sensitivity["window_id"],
                "git_receipt_path": sensitivity["git_receipt_path"],
                "git_receipt_sha256": sensitivity["git_receipt_sha256"],
                "a4_root": sensitivity["a4_root"],
            },
            primary=False,
            floor=floor,
            tolerance=tolerance,
        )
        appendix = {
            "window_id": "W-VL",
            "quote_tag": sensitivity.get("quote_tag"),
            "n_rows": len(vl_rows),
            "in_primary_analysis_count": sum(1 for row in vl_rows if row.get("in_primary_analysis") is True),
            "may_change_primary_terminal": False,
        }
        if appendix["in_primary_analysis_count"] != 0:
            raise AssociationError("W_VL_IN_PRIMARY")
    if not rescale_invariant(rows, loaded) and primary_locked["terminal"] not in {
        SEMANTICS_BLOCKED,
        LOCAL_ONLY_NONREPRODUCIBLE,
    }:
        raise AssociationError("RESCALE_INVARIANCE_BROKEN")
    association_input = {
        "atom_id": ATOM_ID,
        "extractor_id": EXTRACTOR_ID,
        "extractor_schema_version": EXTRACTOR_SCHEMA_VERSION,
        "decision_time_label": DECISION_TIME_LABEL,
        "unit_assumption": loaded["unit_assumption"],
        "unit_assumption_is_fact": False,
        "association_predictors": loaded["association_predictors"],
        "routeplan_eligibility_gates": loaded["routeplan_eligibility_gates"],
        "floor": loaded["floor"],
        "informative_window": loaded["informative_window"],
        "terminal_thresholds": loaded["terminal_thresholds"],
        "primary_windows": [
            {
                "window_id": item["window_id"],
                "git_receipt_path": item["git_receipt_path"],
                "git_receipt_sha256": item["git_receipt_sha256"],
            }
            for item in loaded["primary_windows"]
        ],
        "w_vl_in_primary": False,
        "combined_not_floor_forbidden": True,
        "drop_may_upgrade": False,
    }
    receipt = {
        "schema": "smial.buy-decision-time-quote-microstructure-association.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal": primary_locked["terminal"],
        "next_action": primary_locked["next_action"],
        "automatic_next_started": False,
        "production_selector_authorized": False,
        "family_terminals": primary_locked["family_terminals"],
        "families": primary_locked["families"],
        "n_rows_extracted": primary_locked["n_rows_extracted"],
        "n_rows_primary_analysis": primary_locked["n_rows_primary_analysis"],
        "n_tokens": primary_locked["n_tokens"],
        "n_informative_windows_better": primary_locked["n_informative_windows_better"],
        "n_informative_windows_worse": primary_locked["n_informative_windows_worse"],
        "association_predictors": primary_locked["association_predictors"],
        "routeplan_eligibility_gates": primary_locked["routeplan_eligibility_gates"],
        "unit_assumption": loaded["unit_assumption"],
        "unit_assumption_is_fact": False,
        "w_vl_appendix": appendix,
        "provider_api_rpc_wss_calls": 0,
        "non_claims": list(loaded["non_claims"]),
        "capsule_row_count": len(rows),
        "capsule_sha256": None,
        "association_input_sha256": None,
    }
    _assert_single_terminal(receipt)
    return {
        "rows": rows,
        "association_input": association_input,
        "receipt": receipt,
        "result": primary_locked,
    }


def write_outputs(root: Path, bundle: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, str]:
    outputs = config["outputs"]
    capsule_path = root / outputs["capsule_jsonl"]
    input_path = root / outputs["association_input"]
    receipt_path = root / outputs["runtime_receipt"]
    capsule_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in bundle["rows"]
    ]
    capsule_bytes = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    capsule_path.write_bytes(capsule_bytes)
    input_bytes = (json.dumps(bundle["association_input"], ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    input_path.write_bytes(input_bytes)
    receipt = dict(bundle["receipt"])
    receipt["capsule_sha256"] = sha256_bytes(capsule_bytes)
    receipt["association_input_sha256"] = sha256_bytes(input_bytes)
    receipt_path.write_bytes(
        (json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return {
        "capsule_jsonl": str(outputs["capsule_jsonl"]),
        "association_input": str(outputs["association_input"]),
        "runtime_receipt": str(outputs["runtime_receipt"]),
    }
