"""T01–T06 and T08 for compound temporal discovery. No live store and no provider."""

from __future__ import annotations

import importlib.util
import random
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_ORACLE_PATH = Path(__file__).with_name("oracle_temporal_arithmetic_v1.py")
_ORACLE_SPEC = importlib.util.spec_from_file_location("oracle_temporal_arithmetic_v1", _ORACLE_PATH)
assert _ORACLE_SPEC is not None and _ORACLE_SPEC.loader is not None
_ORACLE = importlib.util.module_from_spec(_ORACLE_SPEC)
_ORACLE_SPEC.loader.exec_module(_ORACLE)
break_even_haircut = _ORACLE.break_even_haircut
estimated_net_proxy = _ORACLE.estimated_net_proxy
grid_drawdown = _ORACLE.grid_drawdown
missing_break_even_mean = _ORACLE.missing_break_even_mean
missing_stress_mean = _ORACLE.missing_stress_mean
price_return = _ORACLE.price_return
retention = _ORACLE.retention

from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    CALCULATION_VERSION,
    GroundedDiscoveryError,
    execute_discovery_from_rows,
    format_discovery_readout,
    run_recorded_discovery_query,
    validate_query_spec,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    TEMPORAL_CALCULATION_VERSION,
    TEMPORAL_CALCULATION_VERSION_V1,
    assess_tier_progress,
    assert_search_exhaustion_claim,
    build_feature_preview,
    classify_temporal_look,
    default_assumption_stress_profile,
    execute_temporal_discovery,
    technical_stop_record,
    temporal_target_label,
    validate_temporal_query,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402

PRICE = "FIELD-USD-PRICE-001"
LIQ = "FIELD-LIQUIDITY-USD-001"
COHORT = "REL-20260902T111900Z-20260909T111900Z"
RELEASE = "aa" * 32
ANCHOR = datetime(2026, 9, 3, tzinfo=UTC)
OFFSETS = {"X300": 300, "Y900": 900, "Y1800": 1800, "Y3600": 3600, "Y7200": 7200}
GIT_SHA = "ab" * 20
TOLERANCE = 1e-12
SYNTH_JOURNAL = "11" * 32
REV_JOURNAL = "33" * 32
SYNTH_MARKET = "ab" * 32


def _ordinary_gate(store, journal: str) -> dict[str, str]:
    from solana_alpha_lab.factory.hfic_ordinary_operation import list_operations, record_operation

    found = [
        item
        for item in list_operations(store)
        if item.get("journal_scope") == journal and item.get("market_evidence_epoch_sha256") == SYNTH_MARKET
    ]
    if found:
        return {
            "operation_sha256": str(found[-1]["operation_sha256"]),
            "verified_market": SYNTH_MARKET,
        }
    recorded = record_operation(
        store,
        {
            "owner_request_text": "synthetic recorded-query gate",
            "owner_focus": "SYNTHETIC_RECORDED_GATE",
            "journal_scope": journal,
            "market_evidence_epoch_sha256": SYNTH_MARKET,
            "owner_cap": {"main": None, "adaptive": None, "preview": None},
            "requested_completion": "LIMITED_RESULT",
        },
    )
    return {
        "operation_sha256": str(recorded["operation_sha256"]),
        "verified_market": SYNTH_MARKET,
    }


def _stamp(point: str, lateness: int = 300) -> str:
    moment = ANCHOR + timedelta(seconds=OFFSETS[point] + lateness)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _binding() -> list[dict]:
    return [
        {
            "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
            "evidence_role": "EXPLORATORY_REUSE",
            "holdout": False,
            "cohort_id": COHORT,
            "release_id": RELEASE,
            "census_sha256": "bb" * 32,
            "observations_sha256": "cc" * 32,
            "schedule_lateness_seconds": 300,
            "window_start": "2026-09-02T11:19:00Z",
            "window_end": "2026-09-09T11:19:00Z",
        }
    ]


def _census(mint: str, state: str = "X_ELIGIBLE") -> dict:
    return {
        "mint": mint,
        "cohort_id": COHORT,
        "release_id": RELEASE,
        "candidate_state": state,
        "authoritative_anchor": "2026-09-03T00:00:00Z",
    }


def _obs(mint: str, point: str, field: str, value: float | None, *, at: str | None = None, state: str = "OBSERVED") -> dict:
    available = at or _stamp(point)
    return {
        "mint": mint,
        "cohort_id": COHORT,
        "release_id": RELEASE,
        "point_id": point,
        "field_id": field,
        "state": state,
        "first_reliable_available_at": available,
        "event_time": available,
        "typed_value": value,
    }


def _profile(**overrides: object) -> dict:
    profile = default_assumption_stress_profile()
    profile.update(overrides)
    return profile


def _explicit_cost() -> dict:
    profile = _profile()
    profile["scenarios"] = {
        "LOW": {"h": 0.03, "q": 0.0, "f": 0.0, "r_fail": -1.0},
        "BASE": {"h": 0.1, "q": 0.05, "f": 0.0, "r_fail": -1.0},
        "STRESS": {"h": 0.25, "q": 0.2, "f": 0.02, "r_fail": -1.0},
    }
    return profile


def _spec(tier: str = "COMPOUND_SCREEN", **overrides: object) -> dict:
    spec = {
        "schema": "smial.hfic-temporal-query",
        "schema_version": "1.0",
        "query_id": "impulse_pullback_liquidity",
        "population": "BASE_X",
        "search_tier": tier,
        "budget_allocation": "AUTO",
        "decision": {"point_id": "Y3600", "time_policy": "BOUND_SCHEDULE_CUTOFF"},
        "schedule": {"lateness_seconds": 300},
        "features": [
            {"name": "impulse", "op": "return_ratio", "field_id": PRICE, "start": "X300", "end": "Y1800"},
            {
                "name": "pullback",
                "op": "drawdown_from_grid_max",
                "field_id": PRICE,
                "points": ["X300", "Y900", "Y1800", "Y3600"],
                "at": "Y3600",
            },
            {
                "name": "retention",
                "op": "ratio",
                "field_id": LIQ,
                "numerator": "Y3600",
                "denominator": "Y1800",
            },
        ],
        "all": [
            {"feature": "impulse", "op": "between", "lower": 0.25, "upper": 2.0, "closed": "left"},
            {"feature": "pullback", "op": "between", "lower": -0.40, "upper": -0.10, "closed": "left"},
            {"feature": "retention", "op": "gte", "value": 0.70},
        ],
        "target": {
            "kind": "PRICE_RELATIVE_PROXY",
            "reference_point": "Y3600",
            "exit_point": "Y7200",
            "field_id": PRICE,
        },
        "entry_model": {"kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT", "assumed_latency_seconds": 30},
        "evaluation": {
            "calendar_block": "UTC_DAY_OF_DECISION",
            "baseline": "SAME_DECISION_ELIGIBLE",
            "ablations": "DROP_ONE_CONDITION",
        },
        "cost_profile": _explicit_cost(),
    }
    spec.update(overrides)
    return spec


def _path(mint: str, prices: list[float], liquidity: tuple[float, float], exit_price: float) -> list[dict]:
    points = ["X300", "Y900", "Y1800", "Y3600"]
    rows = [_obs(mint, "X300", LIQ, 1000.0)]
    for point, price in zip(points, prices, strict=True):
        rows.append(_obs(mint, point, PRICE, price))
    rows.append(_obs(mint, "Y1800", LIQ, liquidity[0]))
    rows.append(_obs(mint, "Y3600", LIQ, liquidity[1]))
    exit_row = _obs(mint, "Y7200", PRICE, exit_price)
    exit_row["event_time"] = exit_row["first_reliable_available_at"]
    rows.append(exit_row)
    return rows


def _scope(spec: dict) -> dict:
    return {
        "population": "BASE_X",
        "decision_timestamp": "Y3600",
        "target": temporal_target_label(spec),
        "estimand": "price_relative_proxy",
        "explanatory_condition": "compound",
        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
        "representation_scope": "TEMPORAL_PRICE_LIQUIDITY",
    }


class TemporalArithmeticTests(unittest.TestCase):
    def test_t01_relative_return_is_unit_invariant_and_v1_stays_raw(self) -> None:
        spec = _spec(
            search_tier="SIMPLE_SCREEN",
            features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
            all=[{"feature": "mark", "op": "gte", "value": 0.0}],
            cost_profile=None,
        )
        census = [_census("a")]
        observations = _path("a", [1.0, 1.0, 1.0, 1.0], (10000.0, 9000.0), 2.0)
        first = execute_discovery_from_rows(census, observations, spec, _binding())["summary"]
        scaled = _path("a", [1000.0, 1000.0, 1000.0, 1000.0], (10000.0, 9000.0), 2000.0)
        second = execute_discovery_from_rows(census, scaled, spec, _binding())["summary"]
        self.assertAlmostEqual(first["mean_target"], price_return(1.0, 2.0), delta=TOLERANCE)
        self.assertAlmostEqual(second["mean_target"], price_return(1.0, 2.0), delta=TOLERANCE)
        self.assertEqual(first["target_kind"], "PRICE_RELATIVE_PROXY")
        self.assertFalse(first["labeled_net_return"])
        other = execute_discovery_from_rows(
            [_census("b")],
            _path("b", [100.0, 100.0, 100.0, 100.0], (10000.0, 9000.0), 110.0),
            spec,
            _binding(),
        )["summary"]
        self.assertAlmostEqual(other["mean_target"], price_return(100.0, 110.0), delta=TOLERANCE)
        legacy = {
            "query_id": "raw-v1",
            "decision_points": ["X300"],
            "decision_fields": [PRICE, LIQ],
            "target_point": "Y7200",
            "target_field": PRICE,
            "explanatory": [],
            "population": "BASE_X",
        }
        raw = execute_discovery_from_rows(census, observations, legacy, _binding())["summary"]
        raw_scaled = execute_discovery_from_rows(census, scaled, legacy, _binding())["summary"]
        self.assertEqual(raw["calculation_version"], CALCULATION_VERSION)
        self.assertNotEqual(raw["pooled"]["mean_target"], first["mean_target"])
        self.assertNotEqual(raw["pooled"]["mean_target"], raw_scaled["pooled"]["mean_target"])
        self.assertNotIn("target_kind", raw)

    def test_t02_pit_conflict_zero_and_order(self) -> None:
        spec = _spec()
        census = [_census("a"), _census("zero"), _census("bad")]
        base = _path("a", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92)
        base.append(_obs("a", "Y3600", PRICE, 999.0, at="2026-09-03T05:00:00Z"))
        base.append(
            {
                **_obs("a", "X300", PRICE, 50.0, at="2026-09-03T05:00:00Z"),
                "event_time": "2026-09-03T00:00:01Z",
            }
        )
        zero = _path("zero", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92)
        zero[0] = _obs("zero", "X300", LIQ, 0.0)
        bad = _path("bad", [0.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92)
        conflict = [
            _obs("a", "Y900", PRICE, 1.5),
            _obs("a", "Y900", PRICE, 9.0),
        ]
        quiet = execute_discovery_from_rows(census, base + zero + bad, spec, _binding())["summary"]
        shuffled = list(base + zero + bad)
        random.Random(7).shuffle(shuffled)
        again = execute_discovery_from_rows(census, shuffled, spec, _binding())["summary"]
        self.assertAlmostEqual(quiet["matched_feature_means"]["impulse"], 1.0, delta=TOLERANCE)
        self.assertAlmostEqual(quiet["matched_feature_means"]["pullback"], -0.2, delta=TOLERANCE)
        self.assertEqual(quiet["mean_target"], again["mean_target"])
        self.assertGreaterEqual(quiet["population_n"], 2)
        self.assertNotIn("zero", quiet["exclusion_reasons"])
        tied = execute_discovery_from_rows([_census("a")], conflict + base, spec, _binding())["summary"]
        tied_reversed = execute_discovery_from_rows(
            [_census("a")], list(reversed(conflict + base)), spec, _binding()
        )["summary"]
        self.assertEqual(tied["feature_unknown_n"], tied_reversed["feature_unknown_n"])
        self.assertEqual(tied["matched_n"], 0)
        self.assertEqual(quiet["feature_unknown_n"], 1)
        exit_tie = [
            *_path("a", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92),
            _obs("a", "Y7200", PRICE, 9.0),
        ]
        forward = execute_discovery_from_rows([_census("a")], exit_tie, spec, _binding())["summary"]
        backward = execute_discovery_from_rows(
            [_census("a")], list(reversed(exit_tie)), spec, _binding()
        )["summary"]
        self.assertEqual(forward["observed_target_n"], 0)
        self.assertEqual(backward["observed_target_n"], 0)
        self.assertEqual(forward["mean_target"], backward["mean_target"])

    def test_t03_compound_expression_has_no_marginal_gate(self) -> None:
        spec = _spec(cost_profile=None)
        other = _spec(
            query_id="other_compound",
            cost_profile=None,
            all=[
                {"feature": "retention", "op": "gte", "value": 0.70},
                {"feature": "pullback", "op": "between", "lower": -0.40, "upper": -0.10, "closed": "left"},
                {"feature": "impulse", "op": "between", "lower": 0.25, "upper": 2.0, "closed": "left"},
            ],
        )
        census = [_census("a"), _census("scaled"), _census("small"), _census("flat")]
        observations = []
        observations.extend(_path("a", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92))
        observations.extend(_path("scaled", [10.0, 15.0, 20.0, 16.0], (100000.0, 90000.0), 19.2))
        observations.extend(_path("small", [1.0, 1.1, 1.2, 1.15], (10000.0, 9000.0), 1.2))
        observations.extend(_path("flat", [1.0, 1.0, 1.0, 1.0], (10000.0, 10000.0), 1.0))
        summary = execute_discovery_from_rows(census, observations, spec, _binding())["summary"]
        self.assertAlmostEqual(summary["matched_feature_means"]["impulse"], price_return(1.0, 2.0), delta=TOLERANCE)
        self.assertAlmostEqual(
            summary["matched_feature_means"]["pullback"],
            grid_drawdown([1.0, 1.5, 2.0, 1.6], 1.6),
            delta=TOLERANCE,
        )
        self.assertAlmostEqual(summary["matched_feature_means"]["retention"], retention(9000.0, 10000.0), delta=TOLERANCE)
        self.assertEqual(summary["matched_n"], 2)
        self.assertEqual(validate_temporal_query(spec)["spec_sha256"], validate_temporal_query(other)["spec_sha256"])
        self.assertTrue(summary["ablations"])
        self.assertEqual(summary["cost"]["status"], "ABSENT")
        self.assertFalse(summary["labeled_net_return"])

    def test_t04_denominators_duplicate_and_missing_stress(self) -> None:
        spec = _spec(
            search_tier="SIMPLE_SCREEN",
            features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
            all=[{"feature": "mark", "op": "gte", "value": 1.0}],
            cost_profile=None,
        )
        census = [_census(f"m{index}") for index in range(10)]
        census.append(_census("m0"))
        observations = []
        returns = [0.2, 0.4, -0.1, 0.3]
        for index in range(10):
            mint = f"m{index}"
            observations.append(_obs(mint, "X300", LIQ, 1000.0))
            observations.append(_obs(mint, "X300", PRICE, 1.0))
            if index < 8:
                price = 1.0 if index < 6 else 0.5
                observations.append(_obs(mint, "Y3600", PRICE, price))
                observations.append(_obs(mint, "Y1800", LIQ, 1000.0))
                observations.append(_obs(mint, "Y3600", LIQ, 1000.0))
            if index < 4:
                exit_row = _obs(mint, "Y7200", PRICE, 1.0 + returns[index])
                exit_row["event_time"] = exit_row["first_reliable_available_at"]
                observations.append(exit_row)
        summary = execute_discovery_from_rows(census, observations, spec, _binding())["summary"]
        self.assertEqual(summary["population_n"], 10)
        self.assertEqual(summary["decision_eligible_n"], 8)
        self.assertEqual(summary["matched_n"], 6)
        self.assertEqual(summary["observed_target_n"], 4)
        self.assertEqual(summary["missing_target_n"], 2)
        self.assertEqual(summary["duplicate_delivery_count"], 1)
        self.assertAlmostEqual(summary["mean_target"], 0.2, delta=TOLERANCE)
        self.assertAlmostEqual(summary["missing_stress_model"]["mean_target"], missing_stress_mean(returns, 2), delta=TOLERANCE)
        self.assertEqual(summary["missing_stress_model"]["label"], "MODEL")
        self.assertFalse(summary["missing_stress_model"]["writes_raw_history"])
        self.assertAlmostEqual(summary["missing_target_mean_to_zero"], missing_break_even_mean(returns, 2), delta=TOLERANCE)
        self.assertEqual(summary["unique_decision_n"], 10)
        self.assertEqual(summary["independence"], "UNKNOWN")
        self.assertIsNone(summary["independent_replication"])

    def test_conflicting_copy_is_excluded_and_reorder_is_stable(self) -> None:
        spec = _spec(
            search_tier="SIMPLE_SCREEN",
            features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
            all=[{"feature": "mark", "op": "gte", "value": 0.0}],
            cost_profile=None,
        )
        other_release = "dd" * 32
        census = [_census("a"), {**_census("a"), "release_id": other_release}]
        observations = _path("a", [1.0, 1.0, 1.0, 1.0], (1000.0, 1000.0), 1.2)
        conflict = []
        for row in observations:
            copied = dict(row)
            copied["release_id"] = other_release
            if copied["point_id"] == "Y7200":
                copied["typed_value"] = 9.0
            conflict.append(copied)
        binding = _binding() + [{**_binding()[0], "release_id": other_release}]
        rows = observations + conflict
        first = execute_discovery_from_rows(census, rows, spec, binding)["summary"]
        self.assertEqual(first["integrity_conflict_count"], 1)
        self.assertIsNone(first["mean_target"])
        self.assertEqual(first["unique_decision_n"], 1)
        second = execute_discovery_from_rows(
            list(reversed(census)),
            list(reversed(rows)),
            spec,
            binding,
        )["summary"]
        self.assertEqual(second["integrity_conflict_count"], first["integrity_conflict_count"])
        self.assertEqual(second["mean_target"], first["mean_target"])
        self.assertEqual(second["unique_decision_n"], first["unique_decision_n"])
        identical = [dict(row) | {"release_id": other_release} for row in observations]
        same = execute_discovery_from_rows(census, observations + identical, spec, binding)["summary"]
        alone = execute_discovery_from_rows([_census("a")], observations, spec, _binding())["summary"]
        self.assertEqual(same["integrity_conflict_count"], 0)
        self.assertEqual(same["duplicate_delivery_count"], 1)
        self.assertAlmostEqual(same["mean_target"], alone["mean_target"], delta=TOLERANCE)
        outsider = {**_census("a"), "cohort_id": "OTHER", "release_id": "ff" * 32}
        kept = execute_discovery_from_rows(
            [outsider, _census("a")],
            observations,
            spec,
            _binding(),
        )["summary"]
        self.assertEqual(kept["observed_target_n"], alone["observed_target_n"])
        self.assertAlmostEqual(kept["mean_target"], alone["mean_target"], delta=TOLERANCE)
        doubled = execute_discovery_from_rows(
            [outsider, _census("a"), {**_census("a"), "release_id": other_release}],
            observations + identical,
            spec,
            binding,
        )["summary"]
        self.assertEqual(doubled["observed_target_n"], alone["observed_target_n"])
        self.assertEqual(doubled["duplicate_delivery_count"], 1)
        self.assertAlmostEqual(doubled["mean_target"], alone["mean_target"], delta=TOLERANCE)

    def test_t05_cost_oracle_does_not_double_count_or_pretend_calibration(self) -> None:
        spec = _spec(
            search_tier="SIMPLE_SCREEN",
            features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
            all=[{"feature": "mark", "op": "gte", "value": 1.0}],
        )
        census = [_census("a")]
        observations = _path("a", [1.0, 1.0, 1.0, 1.0], (1000.0, 1000.0), 1.2)
        summary = execute_discovery_from_rows(census, observations, spec, _binding())["summary"]
        success, proxy = estimated_net_proxy(0.2, 0.1, 0.05, -1.0, 0.0)
        base = summary["cost"]["scenarios"]["BASE"]
        self.assertAlmostEqual(summary["mean_target"], 0.2, delta=TOLERANCE)
        self.assertAlmostEqual(base["r_success"], success, delta=TOLERANCE)
        self.assertAlmostEqual(base["estimated_net_proxy"], proxy, delta=TOLERANCE)
        self.assertAlmostEqual(base["h_break_even"], break_even_haircut(0.2, 0.05, 0.0), delta=TOLERANCE)
        self.assertEqual(base["label"], "ESTIMATED_NET_PROXY")
        self.assertNotEqual(base["label"], "NetReturn")
        self.assertEqual(summary["cost"]["decision_sensitivity"], "FRAGILE")
        self.assertEqual(summary["cost"]["source_status"], "ASSUMPTION_NOT_CALIBRATED")
        quoted = _explicit_cost()
        quoted["haircut_basis"] = "QUOTE_ALREADY_NET"
        with self.assertRaises(GroundedDiscoveryError) as double:
            validate_temporal_query(_spec(cost_profile=quoted))
        self.assertEqual(double.exception.code, "COST_DOUBLE_COUNT")
        cash = _explicit_cost()
        cash["haircut_basis"] = "QUOTE_ALREADY_NET"
        cash["scenarios"]["BASE"] = {"h": 0.0, "q": 0.0, "f": 0.01, "r_fail": -1.0}
        cash["scenarios"]["LOW"] = {"h": 0.0, "q": 0.0, "f": 0.0, "r_fail": -1.0}
        cash["scenarios"]["STRESS"] = {"h": 0.0, "q": 0.0, "f": 0.02, "r_fail": -1.0}
        cash_summary = execute_discovery_from_rows(
            census,
            observations,
            _spec(
                search_tier="SIMPLE_SCREEN",
                features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
                all=[{"feature": "mark", "op": "gte", "value": 1.0}],
                cost_profile=cash,
            ),
            _binding(),
        )["summary"]
        _, cash_proxy = estimated_net_proxy(0.2, 0.0, 0.0, -1.0, 0.01)
        self.assertAlmostEqual(
            cash_summary["cost"]["scenarios"]["BASE"]["estimated_net_proxy"],
            cash_proxy,
            delta=TOLERANCE,
        )

    def test_t06_identity_budget_retry_and_new_epoch(self) -> None:
        renamed = _spec(query_id="renamed_question")
        reordered = _spec(
            query_id="reordered",
            all=list(reversed(_spec()["all"])),
        )
        self.assertEqual(validate_temporal_query(_spec())["spec_sha256"], validate_temporal_query(renamed)["spec_sha256"])
        self.assertEqual(validate_temporal_query(_spec())["spec_sha256"], validate_temporal_query(reordered)["spec_sha256"])
        anchor = classify_temporal_look([], _spec())
        retry = classify_temporal_look([anchor], renamed)
        self.assertFalse(retry["new_look"])
        stale = dict(anchor)
        stale["calculation_version"] = "HFIC_TEMPORAL_DISCOVERY_CALC_V0"
        revised = classify_temporal_look([stale], _spec())
        self.assertEqual(revised["look_class"], "CALCULATION_REVISION")
        self.assertFalse(revised["new_look"])
        self.assertEqual(revised["main_count"], anchor["main_count"])

        def _simple(index: int) -> dict:
            return _spec(
                search_tier="SIMPLE_SCREEN",
                query_id=f"simple-{index}",
                features=[_spec()["features"][0]],
                all=[{"feature": "impulse", "op": "gte", "value": 0.1 * index}],
            )

        first = classify_temporal_look([], _simple(1))
        changed = _simple(2)
        changed["adaptation_of"] = first["spec_sha256"]
        second = classify_temporal_look([first], changed)
        self.assertEqual(second["look_class"], "ADAPTIVE")
        third = classify_temporal_look([first, second], _simple(3))
        fourth = classify_temporal_look([first, second, third], _simple(4))
        with self.assertRaises(GroundedDiscoveryError) as reserved:
            classify_temporal_look([first, second, third, fourth], _simple(5))
        self.assertEqual(reserved.exception.code, "SIMPLE_BUDGET_RESERVED_FOR_COMPOUND")
        compound = classify_temporal_look([first, second, third, fourth], _spec())
        self.assertEqual(compound["look_class"], "MAIN")
        self.assertEqual(compound["compound_main_count"], 1)
        census = [_census("a")]
        observations = _path("a", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92)
        spec = _spec()
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            clock = datetime(2026, 9, 27, tzinfo=UTC)
            opened = run_recorded_discovery_query(
                store,
                census=census,
                observations=observations,
                spec=spec,
                binding=_binding(),
                journal_scope=SYNTH_JOURNAL,
                candidate_scope=_scope(spec),
                git_sha=GIT_SHA,
                clock=clock,
                **_ordinary_gate(store, SYNTH_JOURNAL),
            )
            self.assertTrue(opened["queries"][0]["new_look"])
            resumed = run_recorded_discovery_query(
                ResearchStore(Path(raw)),
                census=census,
                observations=observations,
                spec=renamed,
                binding=_binding(),
                journal_scope=SYNTH_JOURNAL,
                candidate_scope=_scope(spec),
                git_sha="cd" * 20,
                clock=clock,
                **_ordinary_gate(ResearchStore(Path(raw)), SYNTH_JOURNAL),
            )
            self.assertFalse(resumed["queries"][0]["new_look"])
            self.assertEqual(resumed["result_refs"], opened["result_refs"])
            changed_rows = observations + [_obs("a", "Y7200", PRICE, 9.0, at=_stamp("Y7200"))]
            # A second legal exit at the same availability conflicts; use a new price
            # on a copied mint epoch by changing the exit before the deadline only
            # when the bytes differ through an added earlier cell that changes the binding.
            epoch = observations + [_obs("a", "X300", PRICE, 1.0)]
            fresh = run_recorded_discovery_query(
                ResearchStore(Path(raw)),
                census=census,
                observations=epoch,
                spec=spec,
                binding=_binding(),
                journal_scope=SYNTH_JOURNAL,
                candidate_scope=_scope(spec),
                git_sha=GIT_SHA,
                clock=clock,
                **_ordinary_gate(ResearchStore(Path(raw)), SYNTH_JOURNAL),
            )
            self.assertTrue(fresh["queries"][0]["new_look"])
            self.assertNotEqual(fresh["result_refs"], opened["result_refs"])
            self.assertNotEqual(fresh["result"]["mean_target"], None)
        # Tier progress consumes discovery look results (classification metadata
        # alone is not scientific evidence — see look_counts_toward_scientific_search).
        scientific_result = opened["result"]
        first_look = {**first, "result": scientific_result}
        compound_look = {**compound, "result": scientific_result}
        progress = assess_tier_progress([first_look], freeze_worthy=False)
        self.assertEqual(progress["action"], "ESCALATE_COMPOUND")
        self.assertFalse(progress["compound_executed"])
        with self.assertRaises(GroundedDiscoveryError):
            assert_search_exhaustion_claim(progress, claim_search_exhausted=True)
        done = assess_tier_progress([first_look, compound_look], freeze_worthy=True)
        self.assertTrue(done["compound_executed"])
        self.assertNotEqual(changed_rows, observations)


class TemporalRepairTests(unittest.TestCase):
    def test_p2_exit_event_before_entry_is_not_an_outcome(self) -> None:
        spec = _spec(
            search_tier="SIMPLE_SCREEN",
            features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
            all=[{"feature": "mark", "op": "gte", "value": 0.0}],
            entry_model={"kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT", "assumed_latency_seconds": 3500},
            cost_profile=None,
        )
        rows = _path("a", [1.0, 1.0, 1.0, 1.0], (1000.0, 1000.0), 2.0)
        for row in rows:
            if row["point_id"] == "Y7200":
                row["event_time"] = "2026-09-03T02:00:00Z"
                row["first_reliable_available_at"] = "2026-09-03T02:05:00Z"
        summary = execute_discovery_from_rows([_census("a")], rows, spec, _binding())["summary"]
        self.assertEqual(summary["observed_target_n"], 0)

    def test_p2_lateness_mismatch_stops_before_values(self) -> None:
        class Boom(list):
            def __iter__(self):
                raise AssertionError("values read")

        binding = _binding()
        binding[0]["schedule_lateness_seconds"] = 100
        with self.assertRaises(GroundedDiscoveryError) as exc:
            execute_discovery_from_rows([_census("a")], Boom(), _spec(), binding)
        self.assertEqual(exc.exception.code, "SCHEDULE_LATENESS_MISMATCH")

    def test_p3_generalized_break_even_and_overlap(self) -> None:
        edge = break_even_haircut(1.0, 0.2, 0.0, -0.5)
        self.assertAlmostEqual(edge, 0.4375, delta=TOLERANCE)
        from solana_alpha_lab.factory.hfic_temporal_discovery import break_even_haircut as impl

        produced = impl(1.0, q=0.2, f=0.0, r_fail=-0.5)
        self.assertAlmostEqual(produced["h_break_even"], 0.4375, delta=TOLERANCE)
        success, net_old = estimated_net_proxy(1.0, 0.375, 0.2, -0.5, 0.0)
        del success
        self.assertAlmostEqual(net_old, 0.10, delta=TOLERANCE)
        _success, net_new = estimated_net_proxy(1.0, 0.4375, 0.2, -0.5, 0.0)
        self.assertAlmostEqual(net_new, 0.0, delta=TOLERANCE)


class TemporalBoundaryTests(unittest.TestCase):
    def test_t08_negative_routing_leaves_price_path_and_v1_intact(self) -> None:
        class Boom(list):
            def __iter__(self):
                raise AssertionError("values read")

        blocked = _binding()
        blocked[0]["holdout"] = None
        with self.assertRaises(GroundedDiscoveryError) as holdout:
            execute_discovery_from_rows([_census("a")], Boom(), _spec(), blocked)
        self.assertEqual(holdout.exception.code, "HOLDOUT_UNRESOLVED")
        with self.assertRaises(GroundedDiscoveryError) as volume:
            validate_temporal_query(
                _spec(
                    features=[{"name": "vol", "op": "point_value", "field_id": "FIELD-VOLUME-USD-001", "point": "X300"}],
                    all=[{"feature": "vol", "op": "gte", "value": 1.0}],
                )
            )
        self.assertEqual(volume.exception.code, "UNSUPPORTED_REQUIREMENT")
        still = execute_discovery_from_rows(
            [_census("a")],
            _path("a", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92),
            _spec(),
            _binding(),
        )
        self.assertEqual(still["summary"]["target_kind"], "PRICE_RELATIVE_PROXY")
        with self.assertRaises(GroundedDiscoveryError) as stop:
            validate_temporal_query(
                _spec(target={**_spec()["target"], "kind": "INTRABAR_STOP"})
            )
        self.assertEqual(stop.exception.code, "UNSUPPORTED_REQUIREMENT")
        technical = technical_stop_record("MODEL_ERROR")
        self.assertFalse(technical["scientific_negative"])
        self.assertNotEqual(technical["terminal"], "NO_WORTHY_HYPOTHESIS")
        legacy = validate_query_spec(
            {
                "query_id": "legacy",
                "decision_points": ["X300"],
                "decision_fields": [PRICE],
                "target_point": "Y1800",
                "target_field": PRICE,
                "explanatory": [],
                "population": "BASE_X",
            }
        )
        self.assertNotIn("target_label", legacy)
        preview = build_feature_preview(
            [_census("secret-mint")],
            _path("secret-mint", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92),
            {
                "decision": {"point_id": "Y3600"},
                "schedule": {"lateness_seconds": 300, "points": ["X300", "Y900", "Y1800", "Y3600"]},
                "seed": "frozen-seed",
            },
            _binding(),
        )
        self.assertNotIn("secret-mint", str(preview))
        self.assertFalse(preview["target_included"])
        self.assertEqual(preview["selected_count"], 1)
        with self.assertRaises(GroundedDiscoveryError) as extra:
            build_feature_preview(
                [_census("secret-mint")],
                _path("secret-mint", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92),
                {
                    "decision": {"point_id": "Y3600"},
                    "schedule": {"lateness_seconds": 300, "points": ["X300"]},
                    "seed": "other-seed",
                },
                _binding(),
                prior_preview_hashes=["a" * 64, "b" * 64],
            )
        self.assertEqual(extra.exception.code, "PREVIEW_ENVELOPE_EXHAUSTED")


COHORT_B = "REL-20260909T111900Z-20260916T111900Z"
COHORT_C = "REL-20260914T173510Z-20260921T173510Z"
COHORT_EMPTY = "REL-20260921T173510Z-20260928T173510Z"
RELEASE_B = "bb" * 32
RELEASE_C = "cc" * 32
RELEASE_EMPTY = "dd" * 32
ANCHOR_LATER = datetime(2026, 9, 10, tzinfo=UTC)


def _bind(cohort: str, release: str) -> dict:
    row = dict(_binding()[0])
    row["cohort_id"] = cohort
    row["release_id"] = release
    return row


def _move(row: dict, cohort: str, release: str) -> dict:
    copied = dict(row)
    copied["cohort_id"] = cohort
    copied["release_id"] = release
    return copied


def _at(anchor: datetime, point: str) -> str:
    return (anchor + timedelta(seconds=OFFSETS[point] + 300)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _member_path(
    mint: str,
    cohort: str,
    release: str,
    anchor: datetime,
    prices: list[float],
    liquidity: tuple[float, float],
    exit_price: float | None,
) -> tuple[dict, list[dict]]:
    census = _move(_census(mint), cohort, release)
    census["authoritative_anchor"] = anchor.strftime("%Y-%m-%dT%H:%M:%SZ")
    points = ["X300", "Y900", "Y1800", "Y3600"]
    rows = [_move(_obs(mint, "X300", LIQ, 1000.0, at=_at(anchor, "X300")), cohort, release)]
    for point, price in zip(points, prices, strict=True):
        rows.append(_move(_obs(mint, point, PRICE, price, at=_at(anchor, point)), cohort, release))
    rows.append(_move(_obs(mint, "Y1800", LIQ, liquidity[0], at=_at(anchor, "Y1800")), cohort, release))
    rows.append(_move(_obs(mint, "Y3600", LIQ, liquidity[1], at=_at(anchor, "Y3600")), cohort, release))
    if exit_price is not None:
        rows.append(
            _move(_obs(mint, "Y7200", PRICE, exit_price, at=_at(anchor, "Y7200")), cohort, release)
        )
    return census, rows


def _simple() -> dict:
    return _spec(
        search_tier="SIMPLE_SCREEN",
        query_id="cohort-slice",
        features=[_spec()["features"][0]],
        all=[{"feature": "impulse", "op": "gte", "value": 0.0}],
        cost_profile=None,
    )


def _row(summary: dict, cohort: str) -> dict:
    return next(item for item in summary["by_cohort"] if item["cohort_id"] == cohort)


class TemporalCohortSliceTests(unittest.TestCase):
    def _conflict_fingerprint(self, summary: dict) -> dict:
        return {
            "observed_target_n": summary["observed_target_n"],
            "mean_target": summary["mean_target"],
            "population_n": summary["population_n"],
            "integrity_conflict_count": summary["integrity_conflict_count"],
            "duplicate_delivery_count": summary["duplicate_delivery_count"],
            "INTEGRITY_CONFLICT": summary["exclusion_reasons"].get("INTEGRITY_CONFLICT", 0),
            "cohorts": {
                row["cohort_id"]: {
                    "population_n": row["population_n"],
                    "observed_target_n": row["observed_target_n"],
                    "mean_target": row["mean_target"],
                    "INTEGRITY_CONFLICT": row["exclusion_reasons"].get("INTEGRITY_CONFLICT", 0),
                }
                for row in summary["by_cohort"]
            },
        }

    def test_s2_means_keep_missing_cohort_and_null_mean(self) -> None:
        binding = [
            _bind(COHORT, RELEASE),
            _bind(COHORT_B, RELEASE_B),
            _bind(COHORT_C, RELEASE_C),
            _bind(COHORT_EMPTY, RELEASE_EMPTY),
        ]
        parts = [
            _member_path("pos", COHORT, RELEASE, ANCHOR, [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), 1.44),
            _member_path("neg", COHORT_B, RELEASE_B, ANCHOR, [1.0, 1.0, 1.5, 2.0], (10000.0, 9000.0), 1.0),
            _member_path("gap", COHORT_C, RELEASE_C, ANCHOR, [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), None),
        ]
        census = [item[0] for item in parts]
        observations = [row for item in parts for row in item[1]]
        summary = execute_temporal_discovery(census, observations, _simple(), binding)["summary"]
        self.assertAlmostEqual(summary["pooled"]["mean_target"], -0.15, places=9)
        self.assertEqual(summary["observed_target_n"], 2)
        self.assertEqual(summary["missing_target_n"], 1)
        positive = _row(summary, COHORT)
        negative = _row(summary, COHORT_B)
        missing = _row(summary, COHORT_C)
        empty = _row(summary, COHORT_EMPTY)
        self.assertAlmostEqual(positive["mean_target"], price_return(1.2, 1.44), places=9)
        self.assertAlmostEqual(negative["mean_target"], price_return(2.0, 1.0), places=9)
        self.assertEqual(missing["matched_n"], 1)
        self.assertEqual(missing["missing_target_n"], 1)
        self.assertIsNone(missing["mean_target"])
        self.assertEqual(empty["population_n"], 0)
        self.assertIsNone(empty["mean_target"])
        self.assertFalse(summary["cohort_independent_replication"])
        self.assertTrue(all(item["independent_replication"] is False for item in summary["by_cohort"]))
        readout = format_discovery_readout(
            {
                "result": summary,
                "result_refs": ["HFIC-ART-DISCOVERY-TEST"],
                "calculation_version": summary["calculation_version"],
                "queries": [{"look_class": "MAIN", "new_look": True}],
            }
        )
        self.assertIsNone(_row({"by_cohort": readout["by_cohort"]}, COHORT_C)["mean_target"])
        self.assertEqual(readout["look_class"], "MAIN")
        self.assertTrue(readout["new_look"])
        self.assertEqual(readout["calculation_version"], TEMPORAL_CALCULATION_VERSION)

    def test_cohort_dates_and_shared_calendar_block_stay_distinct(self) -> None:
        binding = [_bind(COHORT, RELEASE), _bind(COHORT_B, RELEASE_B)]
        parts = [
            _member_path("early", COHORT, RELEASE, ANCHOR, [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), 1.44),
            _member_path("late", COHORT, RELEASE, ANCHOR_LATER, [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), 1.8),
            _member_path("peer", COHORT_B, RELEASE_B, ANCHOR, [1.0, 1.0, 1.5, 2.0], (10000.0, 9000.0), 1.0),
        ]
        census = [item[0] for item in parts]
        observations = [row for item in parts for row in item[1]]
        summary = execute_temporal_discovery(census, observations, _simple(), binding)["summary"]
        cohort = _row(summary, COHORT)
        self.assertEqual(cohort["observed_target_n"], 2)
        self.assertAlmostEqual(cohort["mean_target"], (price_return(1.2, 1.44) + price_return(1.2, 1.8)) / 2, places=9)
        day = ANCHOR.date().isoformat()
        block = next(item for item in summary["by_calendar_block"] if item["view"] == day)
        self.assertEqual(block["observed_n"], 2)
        self.assertNotAlmostEqual(block["mean_target"], cohort["mean_target"], places=9)

    def test_condition_frequency_differs_by_cohort(self) -> None:
        spec = _spec(
            search_tier="SIMPLE_SCREEN",
            query_id="frequency",
            features=[_spec()["features"][0]],
            all=[{"feature": "impulse", "op": "gte", "value": 0.4}],
            cost_profile=None,
        )
        binding = [_bind(COHORT, RELEASE), _bind(COHORT_B, RELEASE_B)]
        grid = [
            ("a1", COHORT, RELEASE, [1.0, 1.2, 1.5, 1.2], 1.44),
            ("a2", COHORT, RELEASE, [1.0, 1.0, 1.1, 1.05], 1.0),
            ("b1", COHORT_B, RELEASE_B, [1.0, 1.2, 1.5, 1.2], 0.6),
            ("b2", COHORT_B, RELEASE_B, [1.0, 1.0, 1.1, 1.0], 0.5),
            ("b3", COHORT_B, RELEASE_B, [1.0, 1.0, 1.05, 1.0], 0.4),
        ]
        census = []
        observations = []
        for mint, cohort, release, prices, exit_price in grid:
            member, rows = _member_path(mint, cohort, release, ANCHOR, prices, (10000.0, 9000.0), exit_price)
            census.append(member)
            observations.extend(rows)
        summary = execute_temporal_discovery(census, observations, spec, binding)["summary"]
        left = _row(summary, COHORT)
        right = _row(summary, COHORT_B)
        self.assertEqual(left["decision_eligible_n"], 2)
        self.assertEqual(left["matched_n"], 1)
        self.assertEqual(right["decision_eligible_n"], 3)
        self.assertEqual(right["matched_n"], 1)
        self.assertNotAlmostEqual(left["mean_target"], summary["pooled"]["mean_target"], places=9)
        self.assertLess(summary["pooled"]["mean_target"], 0)

    def test_overlap_duplicate_and_conflict_are_stable(self) -> None:
        binding = [_bind(COHORT, RELEASE), _bind(COHORT_B, RELEASE_B)]
        shared_a = _member_path("shared", COHORT, RELEASE, ANCHOR, [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), 1.44)
        shared_b = _member_path("shared", COHORT_B, RELEASE_B, ANCHOR, [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), 1.44)
        census = [shared_a[0], shared_b[0]]
        observations = shared_a[1] + shared_b[1]
        summary = execute_temporal_discovery(census, observations, _simple(), binding)["summary"]
        self.assertEqual(summary["observed_target_n"], 1)
        self.assertEqual(summary["duplicate_delivery_count"], 1)
        self.assertEqual(_row(summary, COHORT)["observed_target_n"], 1)
        self.assertEqual(_row(summary, COHORT_B)["observed_target_n"], 1)
        self.assertEqual(_row(summary, COHORT)["shared_decision_n"], 1)
        self.assertGreater(
            _row(summary, COHORT)["observed_target_n"] + _row(summary, COHORT_B)["observed_target_n"],
            summary["observed_target_n"],
        )
        twin = _member_path("shared", COHORT_B, RELEASE_B, ANCHOR, [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), 9.0)
        conflicted = execute_temporal_discovery(
            [shared_a[0], twin[0]],
            shared_a[1] + twin[1],
            _simple(),
            binding,
        )["summary"]
        self.assertEqual(conflicted["integrity_conflict_count"], 1)
        self.assertEqual(conflicted["observed_target_n"], 0)
        self.assertEqual(conflicted["population_n"], 0)
        self.assertEqual(_row(conflicted, COHORT)["population_n"], 0)
        self.assertEqual(_row(conflicted, COHORT_B)["population_n"], 0)
        self.assertEqual(_row(conflicted, COHORT)["observed_target_n"], 0)
        self.assertGreater(_row(conflicted, COHORT_B)["exclusion_reasons"].get("INTEGRITY_CONFLICT", 0), 0)
        reversed_summary = execute_temporal_discovery(
            list(reversed([shared_a[0], twin[0]])),
            list(reversed(shared_a[1] + twin[1])),
            _simple(),
            binding,
        )["summary"]
        self.assertEqual(reversed_summary["observed_target_n"], conflicted["observed_target_n"])
        self.assertEqual(
            _row(reversed_summary, COHORT)["exclusion_reasons"],
            _row(conflicted, COHORT)["exclusion_reasons"],
        )
        orders = (("A", "A", "B"), ("A", "B", "A"), ("B", "A", "A"))
        copies = {"A": shared_a, "B": twin}
        fingerprints = [
            self._conflict_fingerprint(
                execute_temporal_discovery(
                    [copies[label][0] for label in order],
                    shared_a[1] + twin[1],
                    _simple(),
                    binding,
                )["summary"]
            )
            for order in orders
        ]
        self.assertEqual(fingerprints[0]["observed_target_n"], 0)
        self.assertIsNone(fingerprints[0]["mean_target"])
        self.assertEqual(fingerprints[0]["population_n"], 0)
        self.assertEqual(fingerprints[0]["integrity_conflict_count"], 1)
        self.assertGreater(fingerprints[0]["INTEGRITY_CONFLICT"], 0)
        self.assertTrue(all(item == fingerprints[0] for item in fingerprints[1:]))
        for cohort in (COHORT, COHORT_B):
            self.assertGreater(fingerprints[0]["cohorts"][cohort]["INTEGRITY_CONFLICT"], 0)
            self.assertEqual(fingerprints[0]["cohorts"][cohort]["population_n"], 0)
            self.assertEqual(fingerprints[0]["cohorts"][cohort]["observed_target_n"], 0)
            self.assertIsNone(fingerprints[0]["cohorts"][cohort]["mean_target"])
        visible = execute_temporal_discovery(
            [shared_a[0], twin[0], shared_a[0]],
            shared_a[1] + twin[1],
            _simple(),
            binding,
        )
        readout = format_discovery_readout(
            {
                "result": visible["summary"],
                "result_refs": ["HFIC-ART-DISCOVERY-TEST"],
                "calculation_version": visible["summary"]["calculation_version"],
                "queries": [{"look_class": "MAIN", "new_look": True}],
            }
        )
        self.assertGreater(readout["exclusion_reasons"].get("INTEGRITY_CONFLICT", 0), 0)
        self.assertGreater(_row(readout, COHORT_B)["exclusion_reasons"].get("INTEGRITY_CONFLICT", 0), 0)
        aligned = _member_path(
            "shared", COHORT_C, RELEASE_C, ANCHOR, [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), 1.44
        )
        trio = {"A": shared_a, "B": twin, "C": aligned}
        trio_binding = binding + [_bind(COHORT_C, RELEASE_C)]
        trio_rows = shared_a[1] + twin[1] + aligned[1]
        trio_prints = []
        labels = ("A", "B", "C")
        for left in labels:
            for middle in labels:
                if middle == left:
                    continue
                for right in labels:
                    if right in {left, middle}:
                        continue
                    trio_prints.append(
                        self._conflict_fingerprint(
                            execute_temporal_discovery(
                                [trio[left][0], trio[middle][0], trio[right][0]],
                                trio_rows,
                                _simple(),
                                trio_binding,
                            )["summary"]
                        )
                    )
        self.assertEqual(len(trio_prints), 6)
        self.assertEqual(trio_prints[0]["observed_target_n"], 0)
        self.assertIsNone(trio_prints[0]["mean_target"])
        self.assertGreater(trio_prints[0]["INTEGRITY_CONFLICT"], 0)
        self.assertTrue(all(item == trio_prints[0] for item in trio_prints[1:]))
        for cohort in (COHORT, COHORT_B, COHORT_C):
            self.assertGreater(trio_prints[0]["cohorts"][cohort]["INTEGRITY_CONFLICT"], 0)
            self.assertEqual(trio_prints[0]["cohorts"][cohort]["observed_target_n"], 0)
        blocked = dict(shared_a[0])
        blocked["candidate_state"] = "SCREENED_OUT"
        replaced = execute_temporal_discovery(
            [blocked, shared_a[0]],
            shared_a[1],
            _simple(),
            [_bind(COHORT, RELEASE)],
        )["summary"]
        self.assertEqual(replaced["integrity_conflict_count"], 0)
        self.assertEqual(replaced["observed_target_n"], 1)
        self.assertAlmostEqual(replaced["mean_target"], price_return(1.2, 1.44), places=9)
        self.assertEqual(_row(replaced, COHORT)["population_n"], 1)
        kept = execute_temporal_discovery(
            [shared_a[0], blocked],
            shared_a[1],
            _simple(),
            [_bind(COHORT, RELEASE)],
        )["summary"]
        self.assertEqual(kept["observed_target_n"], 1)
        self.assertAlmostEqual(kept["mean_target"], replaced["mean_target"], places=9)
        unrestored = execute_temporal_discovery(
            [blocked, twin[0], shared_a[0]],
            shared_a[1] + twin[1],
            _simple(),
            binding,
        )["summary"]
        self.assertEqual(unrestored["observed_target_n"], 0)
        self.assertIsNone(unrestored["mean_target"])
        self.assertEqual(unrestored["population_n"], 0)

    def test_v1_revision_replays_v2_without_evaluator_or_new_look(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            _append_discovery_look,
            _look_identity,
            data_binding_sha256,
            result_sha256,
        )

        census = [_census("a")]
        observations = _path("a", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92)
        spec = _spec(cost_profile=None)
        computed = execute_temporal_discovery(census, observations, spec, _binding())
        legacy = dict(computed["summary"])
        legacy.pop("by_cohort", None)
        legacy.pop("cohort_slices_are_descriptive", None)
        legacy.pop("cohort_independent_replication", None)
        legacy["calculation_version"] = TEMPORAL_CALCULATION_VERSION_V1
        self.assertNotIn("by_cohort", legacy)
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            clock = datetime(2026, 9, 27, tzinfo=UTC)
            binding_sha = data_binding_sha256(computed["admitted"], census, observations)
            identity = _look_identity(
                legacy["spec_sha256"],
                binding_sha,
                "TEMPORAL-REV",
                calculation_version=TEMPORAL_CALCULATION_VERSION_V1,
            )
            v1_id = f"HFIC-ART-DISCOVERY-{identity[:40].upper()}"
            _append_discovery_look(
                store,
                record_id=v1_id,
                journal_scope=REV_JOURNAL,
                spec=legacy["experiment_recipe"]["spec"],
                spec_sha256=legacy["spec_sha256"],
                binding_sha=binding_sha,
                data_refs=list(computed["admitted"]["cohorts"]),
                digest=result_sha256(legacy),
                identity=identity,
                summary=legacy,
                look={
                    "look_class": "MAIN",
                    "new_look": True,
                    "search_tier": legacy["search_tier"],
                    "main_count": 1,
                    "adaptive_count": 0,
                    "simple_main_count": 0,
                    "compound_main_count": 1,
                },
                git_sha=GIT_SHA,
                clock=clock,
                candidate_scope=_scope(spec),
            )
            v1_payload = next(
                record.payload_json
                for record in store.iter_committed_records()
                if record.record_id == v1_id
            )
            # An ordinary request never turns a revision into a spendable look.
            with self.assertRaises(GroundedDiscoveryError) as silent:
                run_recorded_discovery_query(
                    ResearchStore(Path(raw)),
                    census=census,
                    observations=observations,
                    spec=spec,
                    binding=_binding(),
                    journal_scope=REV_JOURNAL,
                    candidate_scope=_scope(spec),
                    git_sha=GIT_SHA,
                    clock=clock,
                    **_ordinary_gate(ResearchStore(Path(raw)), REV_JOURNAL),
                )
            self.assertEqual(silent.exception.code, "CALCULATION_REVISION_REQUIRES_EXPLICIT_CORRECTION")
            revised = run_recorded_discovery_query(
                ResearchStore(Path(raw)),
                census=census,
                observations=observations,
                spec=spec,
                binding=_binding(),
                journal_scope=REV_JOURNAL,
                candidate_scope=_scope(spec),
                git_sha=GIT_SHA,
                clock=clock,
                correction={"source_result_ref": v1_id, "source_result_sha256": result_sha256(legacy)},
                **_ordinary_gate(ResearchStore(Path(raw)), REV_JOURNAL),
            )
            self.assertEqual(revised["revision_of"]["record_id"], v1_id)
            self.assertEqual(revised["revision_of"]["reason"]["code"], "CALCULATION_VERSION_SUPERSEDED")
            self.assertEqual(revised["calculation_version"], TEMPORAL_CALCULATION_VERSION)
            self.assertFalse(revised["queries"][0]["new_look"])
            self.assertEqual(revised["queries"][0]["look_class"], "CALCULATION_REVISION")
            self.assertEqual(revised["budget"]["main_count"], 1)
            self.assertNotEqual(revised["result_refs"], [v1_id])
            self.assertIn("by_cohort", revised["result"])
            self.assertEqual(
                next(record.payload_json for record in ResearchStore(Path(raw)).iter_committed_records() if record.record_id == v1_id),
                v1_payload,
            )
            from unittest import mock

            with mock.patch(
                "solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery",
                side_effect=AssertionError("evaluator must not rerun"),
            ):
                replayed = run_recorded_discovery_query(
                    ResearchStore(Path(raw)),
                    census=census,
                    observations=observations,
                    spec=spec,
                    binding=_binding(),
                    journal_scope=REV_JOURNAL,
                    candidate_scope=_scope(spec),
                    git_sha=GIT_SHA,
                    clock=clock,
                    **_ordinary_gate(ResearchStore(Path(raw)), REV_JOURNAL),
                )
            self.assertEqual(replayed["result_refs"], revised["result_refs"])
            self.assertEqual(replayed["result_sha256"], revised["result_sha256"])


if __name__ == "__main__":
    unittest.main()
