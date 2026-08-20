from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.market_feature_surface import (
    PASS_TERMINAL,
    load_surface_config,
    resolve_feature_snapshot,
)
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.runner import ExperimentRunner
from solana_alpha_lab.factory.workbench import _page


SURFACE_CONFIG = ROOT / "configs/factory_v1_common_market_feature_surface_v1.yaml"
SURFACE_SCHEMA = ROOT / "catalog/schemas/factory_v1_common_market_feature_surface.schema.json"
RUNNER = ROOT / "src/solana_alpha_lab/factory/runner.py"
FEATURE_CATALOG = ROOT / "registries/feature_catalog.yaml"
HYPOTHESES = ROOT / "registries/hypotheses.yaml"
RESEARCH_CYCLES = ROOT / "registries/research_cycles.yaml"
SPECS = (
    "configs/experiment_specs/market_feature_price_path_archetype_v1.yaml",
    "configs/experiment_specs/market_feature_liquidity_archetype_v1.yaml",
    "configs/experiment_specs/market_feature_creator_pressure_archetype_v1.yaml",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FactoryCommonMarketFeatureSurfaceTests(unittest.TestCase):
    def test_surface_config_validates_and_has_no_pit_ready(self) -> None:
        config = load_surface_config(ROOT)
        jsonschema.validate(
            config, json.loads(SURFACE_SCHEMA.read_text(encoding="utf-8"))
        )
        self.assertEqual(len(config["features"]), 18)
        self.assertFalse(
            any(item["availability_class"] == "PIT_READY" for item in config["features"])
        )
        cluster = next(
            item
            for item in config["features"]
            if item["feature_id"] == "FEAT-CREATOR-CLUSTER-SHARE"
        )
        self.assertEqual(cluster["availability_class"], "MISSING_CAPABILITY")

    def test_task28_skeletons_stay_empty(self) -> None:
        for path in (FEATURE_CATALOG, HYPOTHESES, RESEARCH_CYCLES):
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["records"], [])

    def test_runner_source_has_no_feature_ids(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertNotIn("required_feature_ids", source)
        self.assertNotIn("FEAT-", source)
        self.assertNotIn("market_feature_surface", source)

    def test_existing_offline_spec_still_validates_without_feature_ids(self) -> None:
        spec = load_experiment_spec(
            ROOT,
            "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml",
        )
        self.assertNotIn("required_feature_ids", spec)

    def test_price_path_computes_counts_and_keeps_returns_unknown(self) -> None:
        spec = load_experiment_spec(ROOT, SPECS[0])
        snapshot = resolve_feature_snapshot(spec, root=ROOT)
        by_id = {row["feature_id"]: row for row in snapshot["features"]}
        self.assertEqual(by_id["FEAT-TARGET-TRADE-COUNT"]["value"], 149)
        self.assertEqual(by_id["FEAT-TARGET-TRADE-COUNT"]["value_status"], "COMPUTED")
        self.assertAlmostEqual(by_id["FEAT-BUY-SELL-COUNT-RATIO"]["value"], 96 / 53)
        self.assertEqual(by_id["FEAT-RETURN-15M"]["value_status"], "UNKNOWN")
        self.assertIsNone(by_id["FEAT-RETURN-15M"]["value"])
        self.assertEqual(by_id["FEAT-AGE-SINCE-CREATION"]["value_status"], "NOT_AVAILABLE")
        self.assertEqual(
            by_id["FEAT-TARGET-TRADE-COUNT"]["available_to_strategy_semantics"],
            "RETROSPECTIVE_ONLY_NOT_PROSPECTIVE_PIT",
        )
        self.assertEqual(snapshot["pit_ready_count"], 0)

    def test_quote_share_is_forward_only_not_keep(self) -> None:
        spec = load_experiment_spec(ROOT, SPECS[1])
        snapshot = resolve_feature_snapshot(spec, root=ROOT)
        by_id = {row["feature_id"]: row for row in snapshot["features"]}
        self.assertEqual(by_id["FEAT-QUOTE-AVAILABILITY"]["value"], 1.0)
        self.assertEqual(by_id["FEAT-QUOTE-AVAILABILITY"]["availability_class"], "FORWARD_ONLY")
        self.assertEqual(
            by_id["FEAT-QUOTE-AVAILABILITY"]["available_to_strategy_semantics"],
            "HISTORICAL_CAPTURE_NOT_STRATEGY_AVAILABLE",
        )
        self.assertEqual(by_id["FEAT-QUOTED-ROUND-TRIP-FRICTION"]["value_status"], "UNKNOWN")

    def test_creator_cluster_is_missing_capability_not_zero(self) -> None:
        spec = load_experiment_spec(ROOT, SPECS[2])
        snapshot = resolve_feature_snapshot(spec, root=ROOT)
        by_id = {row["feature_id"]: row for row in snapshot["features"]}
        self.assertEqual(
            by_id["FEAT-CREATOR-CLUSTER-SHARE"]["value_status"], "MISSING_CAPABILITY"
        )
        self.assertIsNone(by_id["FEAT-CREATOR-CLUSTER-SHARE"]["value"])
        self.assertEqual(by_id["FEAT-CREATOR-DIRECT-SHARE"]["value_status"], "NOT_AVAILABLE")

    def test_three_archetypes_compose_through_generic_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                runner = ExperimentRunner(root=ROOT, store=store)
                terminals = []
                for relative in SPECS:
                    job = runner.start(relative)
                    self.assertEqual(job["status"], "COMPLETE", job)
                    self.assertEqual(job["terminal"], PASS_TERMINAL)
                    terminals.append(job["terminal"])
                self.assertEqual(terminals, [PASS_TERMINAL, PASS_TERMINAL, PASS_TERMINAL])
            finally:
                store.close()

    def test_unknown_is_not_zero_and_workbench_shows_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                app = FactoryApplication(
                    root=ROOT,
                    store=store,
                    spec_relative=SPECS[0],
                )
                started = app.start()
                self.assertEqual(started["status"], "COMPLETE")
                model = app.read_model()
                returns = next(
                    item
                    for item in model["required_features"]
                    if item["feature_id"] == "FEAT-RETURN-15M"
                )
                self.assertIsNone(returns["value"])
                self.assertNotEqual(returns["value"], 0)
                body = _page(model, surface="HOME").decode("utf-8")
                self.assertIn("Required features", body)
                self.assertIn("FEAT-RETURN-15M", body)
                self.assertIn("FEAT-BUY-SELL-COUNT-RATIO", body)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
