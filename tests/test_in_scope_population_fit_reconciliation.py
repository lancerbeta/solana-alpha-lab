from __future__ import annotations

import hashlib
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.in_scope_population_fit_reconciliation import (
    ATOM_ID,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    INSUFFICIENT,
    MEU,
    NOMINATE,
    REPLAN,
    PopulationFitError,
    Y_FIELD,
    _decide,
    classify_h900_terminal,
    load_config,
    population_band,
    reconcile,
    sha256_bytes,
)

FEATURE_CATALOG = ROOT / "registries/feature_catalog.yaml"
HYPOTHESES = ROOT / "registries/hypotheses.yaml"
RESEARCH_CYCLES = ROOT / "registries/research_cycles.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InScopePopulationFitReconciliationTests(unittest.TestCase):
    def test_factory_runner_unchanged(self) -> None:
        self.assertEqual(sha256(ROOT / FACTORY_RUNNER), FACTORY_RUNNER_SHA256)

    def test_task28_skeletons_stay_empty(self) -> None:
        import yaml

        for path in (FEATURE_CATALOG, HYPOTHESES, RESEARCH_CYCLES):
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["records"], [])

    def test_population_bands(self) -> None:
        self.assertEqual(population_band(Decimal("40")), "ULTRA_FRESH")
        self.assertEqual(population_band(Decimal("305")), "EARLY")
        self.assertEqual(population_band(Decimal("899")), "EARLY")
        self.assertEqual(population_band(Decimal("1800")), "SEASONED")
        self.assertEqual(population_band(Decimal("7200")), "SEASONED")
        self.assertEqual(population_band(Decimal("7201")), "OLDER")
        self.assertEqual(population_band(None), "UNKNOWN_AGE")

    def test_meu_is_not_missing_and_unknown_is_not_zero(self) -> None:
        self.assertEqual(classify_h900_terminal("MARKET_EXECUTION_UNAVAILABLE"), MEU)
        self.assertEqual(classify_h900_terminal("UNKNOWN_TYPED_FAILURE"), "PROVIDER_MEASUREMENT_FAILURE")
        self.assertEqual(classify_h900_terminal(None), "MISSING")
        self.assertNotEqual(classify_h900_terminal(None), "0")

    def test_y_equals_x_excluded_from_time_separated_decision(self) -> None:
        rows = [
            {
                "source_stratum": "RECENT",
                "population_admissibility": "ULTRA_FRESH",
                "time_separated": False,
                "y_if_numeric": "-0.02",
                "y_equals_x": True,
                "age_seconds": "40",
                "launchpad_known": False,
                "source_kind": "LIVE_TOKENS_V2_RECENT",
            },
            {
                "source_stratum": "RECENT",
                "population_admissibility": "EARLY",
                "time_separated": True,
                "y_if_numeric": "-0.04",
                "y_equals_x": False,
                "age_seconds": "320",
                "launchpad_known": True,
                "source_kind": "LIVE_TOKENS_V2_RECENT",
            },
            {
                "source_stratum": "TRADED",
                "population_admissibility": "OLDER",
                "time_separated": True,
                "y_if_numeric": "0.01",
                "y_equals_x": False,
                "age_seconds": "200000",
                "launchpad_known": False,
                "source_kind": "LIVE_TOKENS_V2_TOPTRADED",
            },
        ]
        campaigns = [
            {"campaign_id": "A", "searchable_y_kind": "SELL_H900", "stratum_unstable": True, "kept_strata": ["TRADED"]},
            {"campaign_id": "B", "searchable_y_kind": "SELL_H900", "stratum_unstable": True, "kept_strata": ["TRADED"]},
            {"campaign_id": "C", "searchable_y_kind": "SELL_H900", "stratum_unstable": False, "kept_strata": []},
        ]
        # Add ultra-fresh numeric so very-early criterion can pass.
        rows.append(
            {
                "source_stratum": "RECENT",
                "population_admissibility": "ULTRA_FRESH",
                "time_separated": True,
                "y_if_numeric": "-0.08",
                "y_equals_x": False,
                "age_seconds": "40",
                "launchpad_known": False,
                "source_kind": "LIVE_TOKENS_V2_RECENT",
            }
        )
        # A young TRADED row must not enter product EARLY Y, even if Y is positive.
        rows.append(
            {
                "source_stratum": "TRADED",
                "population_admissibility": "EARLY",
                "time_separated": True,
                "y_if_numeric": "0.40",
                "y_equals_x": False,
                "age_seconds": "426",
                "launchpad_known": False,
                "source_kind": "LIVE_TOKENS_V2_TOPTRADED",
            }
        )
        decision = _decide(rows, campaigns)
        self.assertEqual(decision["terminal"], NOMINATE)
        self.assertEqual(decision["criteria"]["very_early_not_positive"]["early_n"], 1)
        self.assertEqual(
            decision["criteria"]["very_early_not_positive"]["traded_in_early_age_excluded_n"],
            1,
        )

    def test_missing_decision_time_age_replans(self) -> None:
        rows = [
            {
                "source_stratum": "RECENT",
                "population_admissibility": "EARLY",
                "time_separated": True,
                "y_if_numeric": "-0.04",
                "y_equals_x": False,
                "age_seconds": None,
                "launchpad_known": True,
                "source_kind": "LIVE_TOKENS_V2_RECENT",
            },
            {
                "source_stratum": "RECENT",
                "population_admissibility": "ULTRA_FRESH",
                "time_separated": True,
                "y_if_numeric": "-0.08",
                "y_equals_x": False,
                "age_seconds": "40",
                "launchpad_known": False,
                "source_kind": "LIVE_TOKENS_V2_RECENT",
            },
            {
                "source_stratum": "TRADED",
                "population_admissibility": "OLDER",
                "time_separated": True,
                "y_if_numeric": "0.01",
                "y_equals_x": False,
                "age_seconds": "200000",
                "launchpad_known": False,
                "source_kind": "LIVE_TOKENS_V2_TOPTRADED",
            },
        ]
        campaigns = [
            {"campaign_id": "A", "searchable_y_kind": "SELL_H900", "stratum_unstable": True, "kept_strata": ["TRADED"]},
            {"campaign_id": "B", "searchable_y_kind": "SELL_H900", "stratum_unstable": True, "kept_strata": ["TRADED"]},
            {"campaign_id": "C", "searchable_y_kind": "SELL_H900", "stratum_unstable": False, "kept_strata": []},
        ]
        decision = _decide(rows, campaigns)
        self.assertEqual(decision["terminal"], REPLAN)
        self.assertEqual(decision["criteria"]["maturity_definable_pre_outcome"]["missing_age_n"], 1)
        self.assertIsNone(decision["frozen_atom2_population"])

    def test_incomparable_y_is_insufficient(self) -> None:
        decision = _decide(
            [],
            [
                {"campaign_id": "A", "searchable_y_kind": "SELL_H3600", "stratum_unstable": False},
                {"campaign_id": "B", "searchable_y_kind": "SELL_H900", "stratum_unstable": False},
                {"campaign_id": "C", "searchable_y_kind": "SELL_H900", "stratum_unstable": False},
            ],
        )
        self.assertEqual(decision["terminal"], INSUFFICIENT)

    def test_pinned_receipts_reconcile_without_provider(self) -> None:
        config = load_config(ROOT)
        runtime = reconcile(ROOT, config)
        self.assertEqual(runtime["atom_id"], ATOM_ID)
        self.assertEqual(runtime["provider_api_rpc_wss_calls"], 0)
        self.assertFalse(runtime["classification_overlay_used_as_market_observation"])
        self.assertEqual(runtime["duplicate_accounting"], "PASS")
        self.assertEqual(len(runtime["campaign_matrix"]), 6)
        self.assertEqual(runtime["decision"]["terminal"], NOMINATE)
        frozen = runtime["decision"]["frozen_atom2_population"]
        self.assertEqual(frozen["domain"]["launchpad"], "pump.fun")
        self.assertTrue(frozen["source_does_not_define_population"])
        early = [
            campaign
            for campaign in runtime["campaign_matrix"]
            if campaign["campaign_id"] == "ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1"
        ][0]
        self.assertGreaterEqual(early["by_source_stratum"]["RECENT"]["MARKET_EXECUTION_UNAVAILABLE_n"], 4)
        self.assertEqual(early["by_source_stratum"]["RECENT"]["Y"]["n"], 17)
        early_geom = runtime["decision"]["criteria"]["very_early_not_positive"]
        self.assertEqual(early_geom["early_n"], 17)
        self.assertEqual(early_geom["early_positive_n"], 0)
        self.assertEqual(early_geom["traded_in_early_age_excluded_n"], 1)
        maturity = runtime["decision"]["criteria"]["maturity_definable_pre_outcome"]
        self.assertEqual(maturity["missing_age_n"], 0)
        self.assertTrue(maturity["pass"])
        audition = [
            campaign
            for campaign in runtime["campaign_matrix"]
            if campaign["campaign_id"] == "QUOTE_NATIVE_ADMISSIBLE_FRICTION_AUDITION_V1"
        ][0]
        self.assertEqual(
            audition["by_source_stratum"]["RECENT"]["population_bands"]["ULTRA_FRESH"],
            6,
        )
        veto = [
            campaign
            for campaign in runtime["campaign_matrix"]
            if campaign["campaign_id"] == "FRESH_OOS_BASELINE_VS_FRICTION_VETO_V1"
        ][0]
        self.assertTrue(veto["stratum_unstable"])
        self.assertEqual(veto["kept_strata"], ["TRADED"])
        for row in runtime["rows"]:
            if row.get("y_equals_x"):
                self.assertFalse(row["time_separated"])
            if row["y_if_numeric"] is None:
                self.assertNotEqual(row["y_if_numeric"], "0")
        self.assertEqual(config["y_field"], Y_FIELD)

    def test_hash_mismatch_fails_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / "src/solana_alpha_lab/factory/runner.py").write_text("unchanged\n", encoding="utf-8")
            bogus = root / "overlay.json"
            bogus.write_text("{}", encoding="utf-8")
            config = {
                "atom_id": ATOM_ID,
                "y_field": Y_FIELD,
                "y_horizon_seconds": 900,
                "notional_atomic": 10_000_000,
                "early_age_seconds": [300, 900],
                "seasoned_age_seconds": [1800, 7201],
                "factory_runner": FACTORY_RUNNER,
                "factory_runner_sha256": sha256_bytes(b"unchanged\n"),
                "evidence_budget": {"provider_api_rpc_wss_calls": 0},
                "classification_overlay": {
                    "path": "overlay.json",
                    "sha256": "0" * 64,
                },
                "market_receipts": [],
            }
            with self.assertRaises(PopulationFitError):
                reconcile(root, config)


if __name__ == "__main__":
    unittest.main()
