from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from solana_alpha_lab.task26b_execution_witness_route import (
    ACCEPTANCE_PATH,
    DECISION_PATH,
    EVIDENCE_CLASSES,
    FIXTURE_PATH,
    ROUTES,
    build_acceptance,
    build_decision,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]


class Task26BExecutionWitnessRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        write_outputs(ROOT)
        cls.decision = json.loads((ROOT / DECISION_PATH).read_text(encoding="utf-8"))
        cls.acceptance = json.loads((ROOT / ACCEPTANCE_PATH).read_text(encoding="utf-8"))
        cls.fixture = json.loads((ROOT / FIXTURE_PATH).read_text(encoding="utf-8"))
        cls.schema = json.loads(
            (
                ROOT / "catalog/schemas/task26b_execution_witness_route.schema.json"
            ).read_text(encoding="utf-8")
        )

    def test_01_schema_and_decision(self) -> None:
        Draft202012Validator(self.schema).validate(self.decision)
        self.assertEqual(self.decision["decision"]["result"], "OWNED_CANARY_REQUIRED")
        self.assertFalse(self.decision["decision"]["canary_authority"])
        self.assertFalse(self.decision["decision"]["task27_authority"])
        self.assertEqual(
            self.decision["route_evaluation_order"][0],
            "HISTORICAL_THIRD_PARTY_CHAIN",
        )

    def test_02_matrix_covers_all_cells(self) -> None:
        cells = {
            (row["route"], row["evidence_class"])
            for row in self.decision["route_matrix"]
        }
        expected = {(route, cls) for route in ROUTES for cls in EVIDENCE_CLASSES}
        self.assertEqual(cells, expected)
        self.assertEqual(len(self.decision["route_matrix"]), 24)

    def test_03_historical_falsifier(self) -> None:
        hist = self.decision["historical_cache_first_falsifier"]
        self.assertEqual(hist["route_tested_first"], "HISTORICAL_THIRD_PARTY_CHAIN")
        self.assertFalse(hist["closes_all_required_classes"])
        self.assertIn("INVENTORY", hist["insufficient_or_non_owner_classes"])
        self.assertIn("SETTLEMENT", hist["insufficient_or_non_owner_classes"])
        self.assertIn("SEND_ATTEMPT", hist["insufficient_or_non_owner_classes"])

    def test_04_task26a_facts_and_zeros(self) -> None:
        facts = self.decision["task26a_facts"]
        self.assertEqual(facts["quote_pairs"], 36)
        self.assertEqual(facts["quote_cost_input_ready_pairs"], 35)
        self.assertEqual(facts["latency_blocked_pairs"], 1)
        self.assertEqual(facts["pairs_with_complete_fee_evidence"], 0)
        self.assertEqual(facts["pairs_with_settled_cashflow"], 0)
        self.assertEqual(facts["numeric_modeled_netreturn_claims"], 0)
        self.assertEqual(facts["observed_netreturn_claims"], 0)
        for value in self.decision["side_effect_counters"].values():
            self.assertEqual(value, 0)

    def test_05_future_witness_has_no_authority(self) -> None:
        witness = self.decision["future_owned_witness"]
        self.assertEqual(witness["status"], "SPEC_ONLY_NO_AUTHORITY")
        created = witness["created_by_this_atom"]
        self.assertFalse(created["wallet"])
        self.assertFalse(created["signer"])
        self.assertFalse(created["send_path"])
        self.assertFalse(created["canary_authority"])
        self.assertIn("stable_attempt_id", witness["required_fields"])
        self.assertIn("threat_model", witness["separate_gate_prerequisites"])

    def test_06_acceptance_and_fixture_align(self) -> None:
        rebuilt = build_acceptance(build_decision(ROOT))
        self.assertEqual(rebuilt["decision"]["result"], "OWNED_CANARY_REQUIRED")
        self.assertFalse(rebuilt["decision"]["canary_authority"])
        self.assertEqual(self.fixture["expected_decision"], "OWNED_CANARY_REQUIRED")
        self.assertFalse(self.fixture["expected_canary_authority"])
        self.assertEqual(
            self.acceptance["status"],
            "PASS_ROUTE_DECISION_OWNED_CANARY_REQUIRED",
        )


if __name__ == "__main__":
    unittest.main()
