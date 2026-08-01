"""Deterministic TASK-23 A4 analysis over content-addressed A3 outputs only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path, PurePosixPath
from statistics import median
from typing import Any, Iterable, Mapping


TASK_ID = "TASK-23"
ATOM_ID = "T23-A4_BOUNDED_ANALYSIS_AND_ADVERSARIAL_ACCEPTANCE_V1"
ANALYSIS_SCHEMA = "smial.task23.bounded-analysis"
ACCEPTANCE_SCHEMA = "smial.task23.adversarial-acceptance"
SCHEMA_VERSION = "1.0.0"
OWNER_DECISION = "DIAGNOSTICS_READY_WITH_LIMITATIONS"
EXPECTED_MANIFEST_SHA256 = (
    "06702bba94e9a895d340598f2fa722eeed6dd5ce9cd324d699918ac6a8a95ff9"
)
EXPECTED_OUTPUTS = {
    "panel_diagnostics_v1.csv": (
        "20cefa9332f2074042f9168ef2c1448bcbe8db281f49a55123f84d8389994c4d",
        9,
    ),
    "panel_inventory_v1.csv": (
        "a623b70543a74c63df41bb45c83074541fa98ac105fdeb611b7e02723014b4ec",
        9,
    ),
    "quote_pair_availability_v1.csv": (
        "5b525a9602f32b6c654a9bf87c0a783212046cee8f292d13838e160ec9788273",
        36,
    ),
}
EXPECTED_MEMBERS = {
    "T21-WATCH-29e2b75994975253bd74",
    "T21-WATCH-61ce24fc3fa04e3eaba7",
    "T21-WATCH-6f21dec76d05f5831216",
}
EXPECTED_PANELS = {"P0", "P1", "P2"}
EXPECTED_NOTIONALS = {Decimal("10"), Decimal("25"), Decimal("50"), Decimal("100")}
RETAINED_STATES = {
    "QUOTE_AVAILABLE",
    "NO_ROUTE",
    "PROVIDER_ERROR",
    "INVALID_RESPONSE",
    "TIMEOUT",
    "SELL_NOT_ATTEMPTED",
    "PANEL_MISSING",
    "CAPTURE_DEAD",
    "CAPTURE_STOPPED",
    "TIMESTAMP_INVALID",
}
PROHIBITED_CLAIMS = {
    "ALPHA_CONFIRMED",
    "NET_RETURN_POSITIVE",
    "FILLABLE_SIZE_CONFIRMED",
    "MARKET_DEPTH_MEASURED",
    "POPULATION_GENERALIZATION_VALID",
    "IID_SAMPLE",
    "R3_VALIDATED",
}


class Task23AnalysisError(RuntimeError):
    """Raised when an A4 input or conclusion violates a fail-closed invariant."""


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task23AnalysisError(f"json_root_not_mapping:{path.name}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _decimal(value: str, label: str) -> Decimal:
    try:
        result = Decimal(value)
    except Exception as exc:  # Decimal provides several parse exceptions.
        raise Task23AnalysisError(f"invalid_decimal:{label}") from exc
    if not result.is_finite():
        raise Task23AnalysisError(f"nonfinite_decimal:{label}")
    return result


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _summary(values: Iterable[Decimal]) -> dict[str, str]:
    materialized = sorted(values)
    if not materialized:
        raise Task23AnalysisError("empty_descriptive_series")
    return {
        "min": _decimal_text(materialized[0]),
        "median": _decimal_text(median(materialized)),
        "max": _decimal_text(materialized[-1]),
    }


def _check_unique(rows: list[dict[str, str]], fields: tuple[str, ...], label: str) -> None:
    keys = [tuple(row[field] for field in fields) for row in rows]
    if len(keys) != len(set(keys)):
        raise Task23AnalysisError(f"duplicate_rows:{label}")


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema") != "smial.task23.r2-diagnostic-projection":
        raise Task23AnalysisError("a3_manifest_schema_mismatch")
    if manifest.get("task_id") != TASK_ID:
        raise Task23AnalysisError("a3_manifest_task_mismatch")
    if manifest.get("status") != "MATERIALIZED_DETERMINISTIC_R2_ONLY":
        raise Task23AnalysisError("a3_manifest_not_accepted")
    summary = manifest.get("summary", {})
    required = {
        "members": 3,
        "capture_clusters": 1,
        "planned_panels": 9,
        "observed_panels": 9,
        "planned_buy_legs": 36,
        "observed_buy_legs": 36,
        "eligible_dependent_sell_legs": 36,
        "observed_dependent_sell_legs": 36,
        "r2_value_files_opened": 9,
        "r3_paths_discovered": 0,
        "r3_value_files_opened": 0,
        "outcome_paths_outside_r2_opened": 0,
        "inference_mode": "DESCRIPTIVE_ONLY",
        "validation_population": "NONE",
    }
    for key, expected in required.items():
        if summary.get(key) != expected:
            raise Task23AnalysisError(f"a3_summary_mismatch:{key}")
    policy = manifest.get("denominator_policy", {})
    if policy.get("missing_is_zero") is not False:
        raise Task23AnalysisError("missingness_coerced_to_zero")
    if policy.get("retain_negative_results") is not True:
        raise Task23AnalysisError("negative_results_not_retained")
    if set(policy.get("retained_states", [])) != RETAINED_STATES:
        raise Task23AnalysisError("typed_state_set_mismatch")
    member_set = manifest.get("bindings", {}).get("member_set", [])
    if len(member_set) != 3 or set(member_set) != EXPECTED_MEMBERS:
        raise Task23AnalysisError("member_set_mismatch")
    next_boundary = manifest.get("next_boundary", {})
    if next_boundary.get("r3_access") != "DENY":
        raise Task23AnalysisError("r3_access_not_denied")


def load_a3_bundle(projection_dir: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, str]]]]:
    """Open only the explicit manifest and its three accepted derived CSV outputs."""

    manifest_path = projection_dir / "projection_manifest_v1.json"
    if sha256_file(manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise Task23AnalysisError("a3_manifest_hash_mismatch")
    manifest = _read_json(manifest_path)
    _validate_manifest(manifest)

    declared_outputs = {item["path"]: item for item in manifest["outputs"]}
    tables: dict[str, list[dict[str, str]]] = {}
    for filename, (expected_hash, expected_rows) in EXPECTED_OUTPUTS.items():
        path = projection_dir / filename
        declared_path = next(
            (
                key
                for key in declared_outputs
                if PurePosixPath(key).name == filename
            ),
            None,
        )
        if declared_path is None:
            raise Task23AnalysisError(f"a3_output_not_declared:{filename}")
        declared = declared_outputs[declared_path]
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash or declared.get("sha256") != expected_hash:
            raise Task23AnalysisError(f"a3_output_hash_mismatch:{filename}")
        rows = _read_csv(path)
        if len(rows) != expected_rows or declared.get("rows") != expected_rows:
            raise Task23AnalysisError(f"a3_output_row_count_mismatch:{filename}")
        tables[filename] = rows
    return manifest, tables


def build_analysis(
    manifest: Mapping[str, Any], tables: Mapping[str, list[dict[str, str]]]
) -> dict[str, Any]:
    inventory = tables["panel_inventory_v1.csv"]
    pairs = tables["quote_pair_availability_v1.csv"]
    diagnostics = tables["panel_diagnostics_v1.csv"]
    _check_unique(inventory, ("member_id", "panel_id"), "panel_inventory")
    _check_unique(diagnostics, ("member_id", "panel_id"), "panel_diagnostics")
    _check_unique(
        pairs,
        ("member_id", "panel_id", "tested_notional_usd"),
        "quote_pairs",
    )

    expected_panel_keys = {
        (member, panel) for member in EXPECTED_MEMBERS for panel in EXPECTED_PANELS
    }
    for label, rows in (("inventory", inventory), ("diagnostics", diagnostics)):
        actual = {(row["member_id"], row["panel_id"]) for row in rows}
        if actual != expected_panel_keys:
            raise Task23AnalysisError(f"population_mismatch:{label}")
    expected_pair_keys = {
        (member, panel, notional)
        for member in EXPECTED_MEMBERS
        for panel in EXPECTED_PANELS
        for notional in EXPECTED_NOTIONALS
    }
    actual_pair_keys = {
        (row["member_id"], row["panel_id"], _decimal(row["tested_notional_usd"], "notional"))
        for row in pairs
    }
    if actual_pair_keys != expected_pair_keys:
        raise Task23AnalysisError("quote_pair_population_mismatch")

    if any(row["panel_state"] != "OBSERVED" for row in inventory + diagnostics):
        raise Task23AnalysisError("unexpected_panel_state")
    if any(row["inference_mode"] != "DESCRIPTIVE_ONLY" for row in diagnostics):
        raise Task23AnalysisError("inference_mode_drift")
    cluster_ids = {row["cluster_id"] for row in diagnostics}
    if len(cluster_ids) != 1:
        raise Task23AnalysisError("cluster_count_drift")
    if any(row["buy_status"] != "QUOTE_AVAILABLE" for row in pairs):
        raise Task23AnalysisError("unexpected_buy_state")
    if any(row["sell_eligible"] != "true" for row in pairs):
        raise Task23AnalysisError("unexpected_sell_eligibility")
    if any(row["sell_status"] != "QUOTE_AVAILABLE" for row in pairs):
        raise Task23AnalysisError("unexpected_sell_state")

    elapsed_by_panel: dict[str, list[Decimal]] = defaultdict(list)
    for row in diagnostics:
        elapsed = _decimal(row["actual_elapsed_from_member_p0_seconds"], "actual_elapsed")
        if elapsed < 0:
            raise Task23AnalysisError("negative_actual_elapsed")
        if row["panel_id"] == "P0" and elapsed != 0:
            raise Task23AnalysisError("p0_elapsed_not_zero")
        if row["panel_id"] != "P0" and elapsed == 0:
            raise Task23AnalysisError("later_panel_elapsed_zero")
        elapsed_by_panel[row["panel_id"]].append(elapsed)

    planned_buy = sum(int(row["planned_buy_legs"]) for row in diagnostics)
    observed_buy = sum(int(row["observed_buy_legs"]) for row in diagnostics)
    available_buy = sum(int(row["available_buy_routes"]) for row in diagnostics)
    eligible_sell = sum(int(row["eligible_dependent_sell_legs"]) for row in diagnostics)
    observed_sell = sum(int(row["observed_dependent_sell_legs"]) for row in diagnostics)
    available_sell = sum(int(row["available_dependent_sell_routes"]) for row in diagnostics)
    missing_buy = sum(int(row["missing_buy_legs"]) for row in diagnostics)
    missing_sell = sum(int(row["missing_eligible_sell_legs"]) for row in diagnostics)
    if (planned_buy, observed_buy, available_buy, eligible_sell, observed_sell, available_sell) != (
        36,
        36,
        36,
        36,
        36,
        36,
    ):
        raise Task23AnalysisError("denominator_totals_mismatch")
    if missing_buy != 0 or missing_sell != 0:
        raise Task23AnalysisError("unexpected_observed_missingness")

    capacities = {
        _decimal(row["quote_notional_capacity_proxy_usd"], "capacity_proxy")
        for row in diagnostics
    }
    if capacities != {Decimal("100")}:
        raise Task23AnalysisError("capacity_proxy_not_right_censored_at_test_max")

    retention_by_panel: dict[str, list[Decimal]] = defaultdict(list)
    retention_by_notional: dict[Decimal, list[Decimal]] = defaultdict(list)
    buy_impact_by_panel: dict[str, list[Decimal]] = defaultdict(list)
    sell_impact_by_panel: dict[str, list[Decimal]] = defaultdict(list)
    route_pairs: Counter[str] = Counter()
    for row in pairs:
        retention = _decimal(row["roundtrip_quote_retention_bps"], "retention_bps")
        buy_impact = _decimal(row["buy_price_impact_pct"], "buy_price_impact")
        sell_impact = _decimal(row["sell_price_impact_pct"], "sell_price_impact")
        if retention < 0 or buy_impact < 0 or sell_impact < 0:
            raise Task23AnalysisError("negative_quote_metric")
        panel = row["panel_id"]
        notional = _decimal(row["tested_notional_usd"], "notional")
        retention_by_panel[panel].append(retention)
        retention_by_notional[notional].append(retention)
        buy_impact_by_panel[panel].append(buy_impact)
        sell_impact_by_panel[panel].append(sell_impact)
        route_pairs[f"buy_{row['buy_route_count']}__sell_{row['sell_route_count']}"] += 1

    analysis: dict[str, Any] = {
        "schema": ANALYSIS_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": OWNER_DECISION,
        "evidence_as_of": manifest["created_at"],
        "owner_decision": {
            "decision": OWNER_DECISION,
            "meaning": "R2 diagnostics are reproducible enough to register and use for bounded next-step design, with the stated limitations.",
            "permits": ["T23_A5_REGISTRATION_AND_FACTORY_FIT_REVIEW"],
            "does_not_permit": [
                "ALPHA_OR_STRATEGY_PROMOTION",
                "EXECUTION_CAPACITY_OR_FILLABILITY_CLAIM",
                "NET_RETURN_CLAIM",
                "R3_OR_OUTCOME_ACCESS",
                "MARKET_WIDE_OR_CROSS_REGIME_GENERALIZATION",
            ],
        },
        "input_bindings": {
            "a3_manifest": {
                "path": "docs/evidence/task23/a3_projection_v1_attempt_02/projection_manifest_v1.json",
                "sha256": EXPECTED_MANIFEST_SHA256,
            },
            "a3_outputs": [
                {"filename": name, "sha256": value[0], "rows": value[1]}
                for name, value in sorted(EXPECTED_OUTPUTS.items())
            ],
            "raw_r2_value_files_opened_by_a4": 0,
            "r3_paths_discovered_by_a4": 0,
            "r3_value_files_opened_by_a4": 0,
            "outcome_paths_outside_r2_opened_by_a4": 0,
        },
        "population_and_dependence": {
            "members": 3,
            "panels": 9,
            "quote_pairs": 36,
            "capture_clusters": 1,
            "effective_independent_cluster_count_upper_bound": 1,
            "inference_mode": "DESCRIPTIVE_ONLY",
            "validation_population": "NONE",
            "iid_assumption": False,
            "interpretation": "The 3 members, 9 panels, and 36 quote pairs are repeated descriptive rows from one capture cluster, not independent n.",
        },
        "denominators": {
            "panels": {
                "numerator_observed": 9,
                "denominator_planned": 9,
                "definition": "all 3 frozen R2 members x P0/P1/P2",
                "excluded_typed_states": [],
            },
            "buy_route_availability_planned": {
                "numerator": available_buy,
                "denominator": planned_buy,
                "rate": "1.000000",
                "definition": "QUOTE_AVAILABLE buy legs / all planned buy legs",
                "excluded_typed_states": [],
            },
            "buy_route_availability_observed": {
                "numerator": available_buy,
                "denominator": observed_buy,
                "rate": "1.000000",
                "definition": "QUOTE_AVAILABLE buy legs / observed buy legs",
                "excluded_typed_states": [],
            },
            "sell_route_availability_eligible": {
                "numerator": available_sell,
                "denominator": eligible_sell,
                "rate": "1.000000",
                "definition": "QUOTE_AVAILABLE dependent sell legs / buy-success-eligible sell legs",
                "excluded_typed_states": [],
            },
            "sell_route_availability_observed": {
                "numerator": available_sell,
                "denominator": observed_sell,
                "rate": "1.000000",
                "definition": "QUOTE_AVAILABLE dependent sell legs / observed dependent sell legs",
                "excluded_typed_states": [],
            },
            "observed_missing": {
                "panels": 0,
                "buy_legs": missing_buy,
                "eligible_sell_legs": missing_sell,
                "missing_is_zero": False,
                "retained_states": sorted(RETAINED_STATES),
                "interpretation": "No typed failure or missing state was observed in R2; this is not an estimate of zero future failure probability.",
            },
        },
        "actual_time": {
            "semantic": "actual elapsed seconds from each member's first reliable P0 observation; panel IDs are labels, not nominal elapsed time",
            "by_panel_seconds": {
                panel: _summary(elapsed_by_panel[panel]) for panel in sorted(EXPECTED_PANELS)
            },
        },
        "descriptive_findings": {
            "quote_notional_capacity_proxy_usd": {
                "observed_all_panels": "100",
                "tested_max_usd": "100",
                "right_censored": True,
                "interpretation": "All panels returned quotes through the largest tested notional; the maximum is a test ceiling, not measured market depth or fillable size.",
            },
            "roundtrip_quote_retention_bps": {
                "all": _summary(
                    _decimal(row["roundtrip_quote_retention_bps"], "retention_bps")
                    for row in pairs
                ),
                "by_panel": {
                    panel: _summary(retention_by_panel[panel])
                    for panel in sorted(EXPECTED_PANELS)
                },
                "median_by_tested_notional_usd": {
                    _decimal_text(notional): _decimal_text(median(values))
                    for notional, values in sorted(retention_by_notional.items())
                },
                "interpretation": "Quote-only round-trip output/input ratio. It is not realized PnL, NetReturn, or evidence of executable profit.",
            },
            "provider_price_impact_pct_raw": {
                "unit_interpretation": "PROVIDER_FIELD_RETAINED_AS_IS_NO_UNIT_REINTERPRETATION",
                "buy_by_panel": {
                    panel: _summary(buy_impact_by_panel[panel])
                    for panel in sorted(EXPECTED_PANELS)
                },
                "sell_by_panel": {
                    panel: _summary(sell_impact_by_panel[panel])
                    for panel in sorted(EXPECTED_PANELS)
                },
            },
            "route_count_pair_distribution": dict(sorted(route_pairs.items())),
        },
        "negative_results_and_coverage_gaps": [
            {
                "id": "NO_FAILURE_STATE_OBSERVED",
                "finding": "No NO_ROUTE, provider error, invalid response, timeout, or missing panel/leg occurred in the accepted R2 projection.",
                "interpretation": "The failure taxonomy remains preserved, but failure probability cannot be estimated from this single all-success capture cluster.",
            },
            {
                "id": "NO_VALIDATION_POPULATION",
                "finding": "No R3 or other validation/outcome population was accessed.",
                "interpretation": "No out-of-sample or outcome claim is available.",
            },
            {
                "id": "ROUTE_ID_CONTINUITY_NOT_MATERIALIZED_NO_CLAIM",
                "finding": "A3 did not materialize route identifiers or a route-continuity metric.",
                "interpretation": "A4 makes no route-continuity claim; repairing this would require a separately authorized raw-R2 projection revision.",
            },
            {
                "id": "CATALOG_REGISTRATION_AND_INTEGRITY_REFRESH_DEFERRED_TO_A5",
                "finding": "A3/A4 evidence IDs and the append-only trial-ledger hash are not registered in Catalog during A4.",
                "interpretation": "Catalog integrity remains fail-closed until the separately authorized A5 registration and generated-consumer refresh.",
            },
        ],
        "limitations": [
            "ONE_DEPENDENT_CAPTURE_CLUSTER",
            "DESCRIPTIVE_ONLY_NO_P_VALUES_OR_CONFIDENCE_INTERVALS",
            "NO_R3_OR_OUTCOME_VALIDATION",
            "NO_OBSERVED_FAILURE_VARIATION",
            "CAPACITY_PROXY_RIGHT_CENSORED_AT_100_USD",
            "QUOTE_ONLY_NOT_TOUCH_FILLABLE_REALIZED_VWAP_OR_NET",
            "PROVIDER_PRICE_IMPACT_FIELD_NOT_REINTERPRETED",
            "ROUTE_ID_CONTINUITY_NOT_MATERIALIZED_NO_CLAIM",
            "CATALOG_REGISTRATION_AND_INTEGRITY_REFRESH_DEFERRED_TO_A5",
        ],
        "claims": [OWNER_DECISION],
        "prohibited_claims": sorted(PROHIBITED_CLAIMS),
        "next_boundary": {
            "atom_id": "T23-A5_REGISTER_ASSETS_UPDATE_CATALOG_AND_FULL_FACTORY_FIT_REVIEW_V1",
            "authorized_by_a4": False,
            "r3_access": "DENY",
        },
    }
    return analysis


def evaluate_adversarial_acceptance(analysis: Mapping[str, Any]) -> dict[str, Any]:
    checks = [
        ("A3_CONTENT_ADDRESSING", analysis["input_bindings"]["a3_manifest"]["sha256"] == EXPECTED_MANIFEST_SHA256),
        ("R2_POPULATION_EXACT", analysis["population_and_dependence"]["panels"] == 9 and analysis["population_and_dependence"]["quote_pairs"] == 36),
        ("R3_ZERO", analysis["input_bindings"]["r3_paths_discovered_by_a4"] == 0 and analysis["input_bindings"]["r3_value_files_opened_by_a4"] == 0),
        ("NO_SURVIVORSHIP_DENOMINATOR", analysis["denominators"]["buy_route_availability_planned"]["denominator"] == 36),
        ("MISSING_NOT_ZERO", analysis["denominators"]["observed_missing"]["missing_is_zero"] is False),
        ("ACTUAL_TIME_ONLY", "actual elapsed" in analysis["actual_time"]["semantic"] and "nominal elapsed" in analysis["actual_time"]["semantic"]),
        ("DEPENDENCE_EXPLICIT", analysis["population_and_dependence"]["effective_independent_cluster_count_upper_bound"] <= 1 and analysis["population_and_dependence"]["iid_assumption"] is False),
        ("NO_INVENTED_PRECISION", analysis["population_and_dependence"]["inference_mode"] == "DESCRIPTIVE_ONLY"),
        ("NO_EXECUTION_ALPHA_CLAIM", not (set(analysis["claims"]) & PROHIBITED_CLAIMS)),
        ("NEGATIVE_RESULTS_RETAINED", len(analysis["negative_results_and_coverage_gaps"]) >= 3),
        ("OWNER_DECISION_SINGLE", analysis["owner_decision"]["decision"] == OWNER_DECISION and analysis["claims"] == [OWNER_DECISION]),
        ("ROUTE_CONTINUITY_NO_CLAIM", "ROUTE_ID_CONTINUITY_NOT_MATERIALIZED_NO_CLAIM" in analysis["limitations"]),
        ("CATALOG_DEFERRED_EXPLICIT", "CATALOG_REGISTRATION_AND_INTEGRITY_REFRESH_DEFERRED_TO_A5" in analysis["limitations"]),
        ("CAPACITY_RIGHT_CENSORED", analysis["descriptive_findings"]["quote_notional_capacity_proxy_usd"]["right_censored"] is True),
        ("NEXT_BOUNDARY_NOT_SELF_AUTHORIZED", analysis["next_boundary"]["authorized_by_a4"] is False),
    ]
    failures = [check_id for check_id, passed in checks if not passed]
    if failures:
        raise Task23AnalysisError("adversarial_acceptance_failed:" + ",".join(failures))
    return {
        "schema": ACCEPTANCE_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": "PASS_WITH_DECLARED_LIMITATIONS",
        "owner_decision": OWNER_DECISION,
        "checks": [
            {"check_id": check_id, "status": "PASS"} for check_id, _ in checks
        ],
        "limitations_carried": list(analysis["limitations"]),
        "external_actions": {
            "network_calls": 0,
            "provider_calls": 0,
            "dependency_installs": 0,
            "wallet_or_transaction_actions": 0,
            "r3_path_discovery": 0,
            "r3_value_reads": 0,
        },
        "next_boundary": dict(analysis["next_boundary"]),
    }


def render_owner_report(analysis: Mapping[str, Any]) -> str:
    finding = analysis["descriptive_findings"]
    elapsed = analysis["actual_time"]["by_panel_seconds"]
    retention = finding["roundtrip_quote_retention_bps"]
    return f"""# TASK-23: bounded R2 cohort diagnostics

- Evidence as of: `{analysis['evidence_as_of']}`
- Atom: `{ATOM_ID}`
- Decision: `{OWNER_DECISION}`

## Owner decision

R2 diagnostics are reproducible enough to register and use for bounded next-step design. This permits only A5 registration and Factory Fit review. It does **not** establish alpha, execution capacity, fillability, realized VWAP, NetReturn, market-wide validity, or authority to inspect R3/outcomes.

## What was actually observed

- Frozen population: 3 members, 9 planned/observed panels, 36 planned/observed buy legs, and 36 eligible/observed dependent sell legs.
- Quote availability: buy 36/36 planned and 36/36 observed; dependent sell 36/36 eligible and 36/36 observed.
- Actual elapsed seconds from each member's reliable P0: P0 {elapsed['P0']['min']}–{elapsed['P0']['max']}; P1 {elapsed['P1']['min']}–{elapsed['P1']['max']}; P2 {elapsed['P2']['min']}–{elapsed['P2']['max']}. P0/P1/P2 are labels, not substituted nominal horizons.
- Quote-notional capacity proxy reached the tested ceiling of $100 in every panel. This is right-censored at the largest tested size; it is not measured market depth or fillable size.
- Quote-only round-trip retention across 36 pairs: min {retention['all']['min']} bps, median {retention['all']['median']} bps, max {retention['all']['max']} bps. Values above 10,000 bps are still quote ratios, not profit after costs or execution evidence.

## Effective sample and dependence

All rows belong to one capture cluster. Therefore the effective independent cluster count is at most 1. The 3 members, 9 panels, and 36 quote pairs are repeated descriptive observations—not independent sample size. No p-values, confidence intervals, IID assumption, or population generalization are valid here.

## Negative results and limitations

- No `NO_ROUTE`, provider error, invalid response, timeout, or missing panel/leg appeared. Typed missing/failure states were retained, but zero observed failures does not mean zero future failure probability.
- No validation population was used: R3 path discovery/read = 0; outcome paths outside R2 opened = 0. There is no OOS or outcome claim.
- A3 did not materialize route IDs or route-continuity diagnostics. This report makes no route-continuity claim; repair would require separately authorized raw-R2 reprojection.
- Catalog registration of A3/A4 evidence IDs and the append-only trial-ledger hash refresh are deferred to A5. Until then, full Catalog-integrity validation must fail closed; this A4 acceptance applies only to the bounded analysis and its adversarial checks.
- The provider `priceImpactPct` field is reported only as the raw provider field. Its units were not reinterpreted.
- All capacity and retention findings are quote-only: neither `Touch`, `Fillable`, `RealizedVWAP`, nor `NetReturn` was measured.

## Denominator contract

Missing is never coerced to zero. Every rate above publishes its planned, observed, or eligibility denominator. The retained typed states are: {', '.join(analysis['denominators']['observed_missing']['retained_states'])}.

## Stop boundary

Next candidate atom: `T23-A5_REGISTER_ASSETS_UPDATE_CATALOG_AND_FULL_FACTORY_FIT_REVIEW_V1`. A4 does not authorize it and does not authorize R3, provider, wallet, transaction, deployment, merge, or release actions.
"""


def generate(repo_root: Path) -> tuple[Path, Path, Path]:
    projection_dir = repo_root / "docs/evidence/task23/a3_projection_v1_attempt_02"
    manifest, tables = load_a3_bundle(projection_dir)
    analysis = build_analysis(manifest, tables)
    acceptance = evaluate_adversarial_acceptance(analysis)
    analysis_bytes = canonical_json_bytes(analysis)
    report_bytes = render_owner_report(analysis).encode("utf-8")
    acceptance["output_bindings"] = {
        "analysis_sha256": sha256_bytes(analysis_bytes),
        "owner_report_sha256": sha256_bytes(report_bytes),
    }

    analysis_path = repo_root / "docs/evidence/task23/a4_bounded_analysis_v1.json"
    acceptance_path = repo_root / "docs/evidence/task23/a4_adversarial_acceptance_v1.json"
    report_path = repo_root / "docs/reports/task23_cohort_diagnostics_v1.md"
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    acceptance_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.write_bytes(analysis_bytes)
    acceptance_path.write_bytes(canonical_json_bytes(acceptance))
    report_path.write_bytes(report_bytes)
    return analysis_path, acceptance_path, report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    paths = generate(args.repo_root.resolve())
    print(json.dumps({path.name: sha256_file(path) for path in paths}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
