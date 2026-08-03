from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task26_execution_cost_model import (
    ACCEPTANCE_PATH,
    FROZEN_INPUTS,
    PROJECTION_PATH,
    Task26ExecutionCostModelError,
    build_acceptance,
    build_projection,
    canonical_json_bytes,
    check_stored_outputs,
    evaluate_scenario,
)

FIXTURE_PATH = ROOT / "tests/fixtures/task26/execution_cost_and_netreturn_contract_v1.json"
CONFIG_PATH = ROOT / "configs/task26_execution_cost_and_netreturn_contract_v1.yaml"


def apply_json_pointer(payload: dict[str, Any], pointer: str, replacement: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.lstrip("/").split("/")]
    target: Any = payload
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    last = parts[-1]
    if isinstance(target, list):
        target[int(last)] = replacement
    else:
        target[last] = replacement


class Task26ExecutionCostModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.scenarios = {row["scenario_id"]: row for row in cls.fixture["scenarios"]}

    def test_projection_binds_exact_a2_inputs_and_is_synthetic_only(self) -> None:
        projection = build_projection(ROOT)
        self.assertEqual(projection["input_bindings"], FROZEN_INPUTS)
        self.assertEqual(projection["status"], "PASS_SYNTHETIC_EXECUTION_COST_MODEL_WITH_LIMITATIONS")
        self.assertEqual(projection["summary"]["input_scenarios"], 9)
        self.assertEqual(projection["summary"]["scenarios_dropped"], 0)
        self.assertEqual(projection["summary"]["r2_values_read"], 0)
        self.assertEqual(projection["summary"]["r3_paths_or_values_read"], 0)
        self.assertEqual(projection["summary"]["provider_api_rpc_wss_calls"], 0)

    def test_projection_preserves_model_observed_and_unknown_boundaries(self) -> None:
        projection = build_projection(ROOT)
        summary = projection["summary"]
        self.assertEqual(summary["classifications"], {"MODELED": 3, "NOT_COMPUTABLE": 5, "OBSERVED": 1})
        self.assertEqual(summary["modeled_netreturn_scenarios"], 3)
        self.assertEqual(summary["synthetic_observed_semantic_cases"], 1)
        self.assertEqual(summary["observed_netreturn_claims"], 0)
        results = {row["scenario_id"]: row for row in projection["projection_results"]}
        self.assertEqual(results["quote_only_not_computable"]["result_state"], "NOT_COMPUTABLE")
        self.assertEqual(results["quote_only_not_computable"]["blocked_reason"], "QUOTE_ONLY_NO_ATTEMPT")
        self.assertEqual(results["synthetic_observed_complete_reconciliation"]["result_state"], "SYNTHETIC_OBSERVED_SEMANTICS_ONLY")
        self.assertEqual(results["synthetic_observed_complete_reconciliation"]["classification"], "OBSERVED")

    def test_projection_is_byte_deterministic(self) -> None:
        first = canonical_json_bytes(build_projection(ROOT))
        second = canonical_json_bytes(build_projection(ROOT))
        self.assertEqual(first, second)

    def test_normalized_cashflow_is_the_only_netreturn_arithmetic_surface(self) -> None:
        projection = build_projection(ROOT)
        results = {row["scenario_id"]: row for row in projection["projection_results"]}
        infrastructure = results["infrastructure_cost_separate_from_trade_cashflow"]
        self.assertEqual(infrastructure["cashflow_currency"], "SYNTHETIC_USDC")
        self.assertEqual(infrastructure["cashflow_decimals"], 6)
        self.assertEqual(infrastructure["trade_cashflow_atomic"], "9000")
        self.assertEqual(infrastructure["infrastructure_cashflow_atomic"], "-2000")
        self.assertEqual(infrastructure["net_return_atomic"], "7000")

    def test_engine_rejects_every_frozen_adversarial_mutation(self) -> None:
        for mutation in self.fixture["adversarial_mutations"]:
            with self.subTest(mutation_id=mutation["mutation_id"]):
                changed = copy.deepcopy(self.scenarios[mutation["base_scenario_id"]])
                apply_json_pointer(changed, mutation["json_pointer"], mutation["replacement"])
                with self.assertRaises(Task26ExecutionCostModelError):
                    evaluate_scenario(changed)

    def test_unknown_and_partial_states_remain_operationally_blocked(self) -> None:
        projection = build_projection(ROOT)
        results = {row["scenario_id"]: row for row in projection["projection_results"]}
        self.assertEqual(results["unknown_terminal_blocks_retry_and_closure"]["blocked_reason"], "UNKNOWN_TERMINAL_REQUIRES_RECONCILIATION")
        self.assertEqual(results["partial_fill_residual_inventory"]["blocked_reason"], "OPEN_OR_UNRESOLVED_INVENTORY")
        self.assertIsNone(results["partial_fill_residual_inventory"]["net_return_atomic"])

    def test_a2r1_currency_repair_is_bound_to_the_engine(self) -> None:
        contract = self.config["execution_contract"]
        self.assertTrue(contract["cashflow"]["normalized_accounting_currency_required"])
        self.assertTrue(contract["cashflow"]["normalized_accounting_decimals_required"])
        self.assertEqual(self.config["next_boundary"]["atom"], "T26-A3_DETERMINISTIC_EXECUTION_COST_AND_GOLDEN_ACCEPTANCE_V1")

    def test_acceptance_receipt_is_complete_and_fail_closed(self) -> None:
        projection = build_projection(ROOT)
        acceptance = build_acceptance(ROOT, projection)
        self.assertEqual(acceptance["status"], "PASS_SYNTHETIC_EXECUTION_COST_MODEL_WITH_LIMITATIONS")
        self.assertTrue(all(check["status"] == "PASS" for check in acceptance["checks"]))
        self.assertEqual(acceptance["measured_boundary"]["r2_values_or_paths_read"], 0)
        self.assertEqual(acceptance["measured_boundary"]["r3_values_or_paths_read"], 0)
        self.assertFalse(acceptance["next_boundary"]["authorized_by_a3"])
        self.assertEqual(acceptance["next_boundary"]["r3_access"], "DENY")

    def test_stored_projection_and_receipt_are_exact(self) -> None:
        hashes = check_stored_outputs(ROOT)
        self.assertIn(PROJECTION_PATH.as_posix(), hashes)
        self.assertIn(ACCEPTANCE_PATH.as_posix(), hashes)


if __name__ == "__main__":
    unittest.main()
