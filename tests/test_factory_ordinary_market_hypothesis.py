from __future__ import annotations

import hashlib
import json
import subprocess
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
    resolve_feature_snapshot,
)
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.workbench import _page

SPEC = "configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml"
ARCHETYPE = "configs/experiment_specs/market_feature_price_path_archetype_v1.yaml"
LIQUIDITY_SPEC = "configs/experiment_specs/ordinary_liquidity_quote_pressure_v1.yaml"
LIQUIDITY_ARCHETYPE = "configs/experiment_specs/market_feature_liquidity_archetype_v1.yaml"
SCHEMA = ROOT / "catalog/schemas/experiment_spec.schema.json"
SCRIPT = ROOT / "scripts/run_factory_ordinary_market_hypothesis.py"
CLI_SHA256 = "72d479df06067bc4afae4b4a105e88825963b45b08a57747e64aa1e741a0df72"
FEATURE_CATALOG = ROOT / "registries/feature_catalog.yaml"
HYPOTHESES = ROOT / "registries/hypotheses.yaml"
RESEARCH_CYCLES = ROOT / "registries/research_cycles.yaml"
PRODUCT_TERMINAL = "ORDINARY_HYPOTHESIS_COMPOSED_NOT_PROMOTABLE"
FACTORY_CORE = {
    "src/solana_alpha_lab/factory/runner.py": "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f",
    "src/solana_alpha_lab/factory/capabilities.py": "906509c3176fa8aa92543f9252703387b96c501ac85154b0a3fd81e683d3935c",
    "src/solana_alpha_lab/factory/read_model.py": "1bdc9b61e5a4bb579d93f66d99eac9db7f6aaed44c9d79dcb781f89725d7fef1",
    "src/solana_alpha_lab/factory/workbench.py": "dd64cba42eb9280e9001247e6c79d352a06c47675fd2153457a95da0259b4bf3",
    "src/solana_alpha_lab/factory/market_feature_surface.py": "e6bbb655629da5582eaf30571a07ca37dac28aefdb93a4b808cf57ae45958e2b",
    "src/solana_alpha_lab/factory/application.py": "bfa2eec4e68b73c76dd87cba5325228e7a443156e17b531ca2f82b93f6e32b7f",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FactoryOrdinaryMarketHypothesisTests(unittest.TestCase):
    def test_spec_validates_and_is_not_a_fourth_archetype(self) -> None:
        spec = load_experiment_spec(ROOT, SPEC)
        jsonschema.validate(spec, json.loads(SCHEMA.read_text(encoding="utf-8")))
        archetype = load_experiment_spec(ROOT, ARCHETYPE)
        self.assertEqual(spec["experiment_id"], "EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001")
        self.assertEqual(
            spec["hypothesis_version"], "HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1"
        )
        self.assertNotEqual(spec["experiment_id"], archetype["experiment_id"])
        self.assertNotEqual(spec["hypothesis_version"], archetype["hypothesis_version"])
        self.assertNotEqual(spec["question"], archetype["question"])
        self.assertEqual(spec["parameters"]["next_safe_action"], "DO_NOT_PROMOTE")
        self.assertEqual(spec["parameters"]["product_terminal"], PRODUCT_TERMINAL)
        self.assertNotIn("FEAT-VOLUME-15M", spec["required_feature_ids"])
        self.assertNotIn("FEAT-AGE-SINCE-CREATION", spec["required_feature_ids"])

    def test_factory_core_python_unchanged(self) -> None:
        for relative, expected in FACTORY_CORE.items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)

    def test_runner_source_has_no_feature_ids(self) -> None:
        source = (ROOT / "src/solana_alpha_lab/factory/runner.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("required_feature_ids", source)
        self.assertNotIn("FEAT-", source)
        self.assertNotIn("market_feature_surface", source)

    def test_task28_skeletons_stay_empty(self) -> None:
        for path in (FEATURE_CATALOG, HYPOTHESES, RESEARCH_CYCLES):
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["records"], [])

    def test_buy_pressure_computes_and_returns_stay_unknown(self) -> None:
        spec = load_experiment_spec(ROOT, SPEC)
        snapshot = resolve_feature_snapshot(spec, root=ROOT)
        by_id = {row["feature_id"]: row for row in snapshot["features"]}
        self.assertEqual(by_id["FEAT-TARGET-TRADE-COUNT"]["value"], 149)
        self.assertEqual(by_id["FEAT-TARGET-TRADE-COUNT"]["value_status"], "COMPUTED")
        self.assertAlmostEqual(by_id["FEAT-BUY-SELL-COUNT-RATIO"]["value"], 96 / 53)
        for feature_id in (
            "FEAT-RETURN-15M",
            "FEAT-PEAK-RETURN-SINCE-START",
            "FEAT-DRAWDOWN-FROM-RUNNING-PEAK",
        ):
            self.assertEqual(by_id[feature_id]["value_status"], "UNKNOWN")
            self.assertIsNone(by_id[feature_id]["value"])
            self.assertNotEqual(by_id[feature_id]["value"], 0)
        self.assertEqual(snapshot["terminal"], PASS_TERMINAL)
        self.assertEqual(snapshot["pit_ready_count"], 0)

    def test_ordinary_hypothesis_composes_through_generic_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                app = FactoryApplication(root=ROOT, store=store, spec_relative=SPEC)
                model = app.start()
                self.assertEqual(model["status"], "COMPLETE", model)
                self.assertEqual(model["terminal_result"], PASS_TERMINAL)
                self.assertEqual(
                    model["hypothesis"], "HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1"
                )
                self.assertEqual(model["next_safe_action"], "DO_NOT_PROMOTE")
                body = _page(model, surface="HOME").decode("utf-8")
                self.assertIn("HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1", body)
                self.assertIn("DO_NOT_PROMOTE", body)
                self.assertIn("FEAT-TARGET-TRADE-COUNT", body)
                self.assertIn("FEAT-RETURN-15M", body)
            finally:
                store.close()

    def test_cli_classifies_not_promotable_without_runner_change(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(ROOT), "--spec", SPEC],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["capability_terminal"], PASS_TERMINAL)
        self.assertEqual(payload["product_terminal"], PRODUCT_TERMINAL)
        self.assertEqual(payload["next_safe_action"], "DO_NOT_PROMOTE")

    def test_same_cli_does_not_treat_coverage_archetype_as_promotion_stop(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(ROOT), "--spec", ARCHETYPE],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["capability_terminal"], PASS_TERMINAL)
        self.assertEqual(payload["product_terminal"], "NOT_AN_ORDINARY_PROMOTION_STOP")
        self.assertEqual(payload["next_safe_action"], "INSPECT_FEATURE_COVERAGE")

    def test_existing_experiment_cli_composes_the_ordinary_spec(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run_factory_experiment.py"),
                "--root",
                str(ROOT),
                "--spec",
                SPEC,
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "COMPLETE")
        self.assertEqual(payload["hypothesis"], "HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1")
        self.assertEqual(payload["next_safe_action"], "DO_NOT_PROMOTE")

    def test_ordinary_hypothesis_cli_bytes_unchanged(self) -> None:
        self.assertEqual(sha256(SCRIPT), CLI_SHA256)

    def test_liquidity_yaml_is_not_the_liquidity_archetype(self) -> None:
        spec = load_experiment_spec(ROOT, LIQUIDITY_SPEC)
        jsonschema.validate(spec, json.loads(SCHEMA.read_text(encoding="utf-8")))
        archetype = load_experiment_spec(ROOT, LIQUIDITY_ARCHETYPE)
        self.assertEqual(
            spec["experiment_id"], "EXP-ORDINARY-LIQUIDITY-QUOTE-HYPOTHESIS-001"
        )
        self.assertEqual(
            spec["hypothesis_version"], "HYP-ORDINARY-LIQUIDITY-QUOTE-PRESSURE-V1"
        )
        self.assertNotEqual(spec["experiment_id"], archetype["experiment_id"])
        self.assertNotEqual(spec["question"], archetype["question"])
        self.assertEqual(spec["parameters"]["next_safe_action"], "DO_NOT_PROMOTE")
        self.assertEqual(spec["parameters"]["product_terminal"], PRODUCT_TERMINAL)
        self.assertNotIn("FEAT-MCAP-TO-LIQUIDITY", spec["required_feature_ids"])
        self.assertNotIn("FEAT-ROUTE-STATUS", spec["required_feature_ids"])

    def test_liquidity_quote_is_forward_only_and_friction_stays_unknown(self) -> None:
        spec = load_experiment_spec(ROOT, LIQUIDITY_SPEC)
        snapshot = resolve_feature_snapshot(spec, root=ROOT)
        by_id = {row["feature_id"]: row for row in snapshot["features"]}
        self.assertEqual(by_id["FEAT-QUOTE-AVAILABILITY"]["value"], 1.0)
        self.assertEqual(by_id["FEAT-QUOTE-AVAILABILITY"]["availability_class"], "FORWARD_ONLY")
        self.assertEqual(
            by_id["FEAT-QUOTE-AVAILABILITY"]["available_to_strategy_semantics"],
            "HISTORICAL_CAPTURE_NOT_STRATEGY_AVAILABLE",
        )
        self.assertEqual(by_id["FEAT-QUOTED-ROUND-TRIP-FRICTION"]["value_status"], "UNKNOWN")
        self.assertIsNone(by_id["FEAT-QUOTED-ROUND-TRIP-FRICTION"]["value"])
        self.assertNotEqual(by_id["FEAT-QUOTED-ROUND-TRIP-FRICTION"]["value"], 0)
        self.assertEqual(by_id["FEAT-POOL-LIQUIDITY"]["value_status"], "UNKNOWN")
        self.assertEqual(snapshot["pit_ready_count"], 0)

    def test_existing_cli_classifies_liquidity_yaml_not_promotable(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(ROOT), "--spec", LIQUIDITY_SPEC],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["capability_terminal"], PASS_TERMINAL)
        self.assertEqual(payload["product_terminal"], PRODUCT_TERMINAL)
        self.assertEqual(payload["next_safe_action"], "DO_NOT_PROMOTE")
        self.assertEqual(
            payload["hypothesis_version"], "HYP-ORDINARY-LIQUIDITY-QUOTE-PRESSURE-V1"
        )


if __name__ == "__main__":
    unittest.main()
