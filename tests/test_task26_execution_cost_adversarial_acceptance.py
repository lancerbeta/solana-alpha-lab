from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task26_adversarial_acceptance import (
    A3_BINDINGS,
    ACCEPTANCE_PATH,
    Task26AdversarialAcceptanceError,
    build_acceptance,
    check_stored_output,
    run_adversarial_cases,
)


class Task26ExecutionCostAdversarialAcceptanceTests(unittest.TestCase):
    def test_all_twelve_frozen_false_positives_are_rejected_exactly(self) -> None:
        outcomes = run_adversarial_cases(ROOT)
        self.assertEqual(len(outcomes), 12)
        self.assertEqual([outcome["mutation_id"] for outcome in outcomes], [f"m{index:02d}_" + suffix for index, suffix in enumerate((
            "quote_to_observed",
            "unknown_allows_retry",
            "unknown_closes_accounting",
            "dropped_assumed_zero",
            "partial_becomes_flat",
            "duplicate_retry_fee",
            "quote_embedded_double_count",
            "observed_without_actual_fill",
            "observed_without_settlement",
            "infra_in_trade_cashflow",
            "incomplete_numeric_net",
            "invalid_pit_order",
        ), start=1)])
        self.assertTrue(all(outcome["status"] == "PASS_EXACT_REJECTION" for outcome in outcomes))

    def test_receipt_preserves_a3_frozen_bindings_and_no_external_reads(self) -> None:
        acceptance = build_acceptance(ROOT)
        self.assertEqual(acceptance["a3_bindings"], A3_BINDINGS)
        self.assertEqual(acceptance["measured_boundary"]["r2_values_or_paths_read"], 0)
        self.assertEqual(acceptance["measured_boundary"]["r3_values_or_paths_read"], 0)
        self.assertEqual(acceptance["measured_boundary"]["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(acceptance["measured_boundary"]["wallet_signer_transaction_actions"], 0)

    def test_owner_decision_is_ready_with_limitations_and_does_not_open_r2(self) -> None:
        acceptance = build_acceptance(ROOT)
        self.assertEqual(acceptance["status"], "PASS_EXECUTION_COST_MODEL_READY_WITH_LIMITATIONS")
        self.assertEqual(acceptance["owner_decision"]["decision"], "EXECUTION_COST_MODEL_READY_WITH_LIMITATIONS")
        self.assertFalse(acceptance["next_boundary"]["authorized_by_a4"])
        self.assertIn("observed NetReturn", acceptance["owner_decision"]["does_not_establish"])

    def test_stored_receipt_is_exact(self) -> None:
        stored_hash = check_stored_output(ROOT)
        self.assertEqual(len(stored_hash), 64)
        self.assertTrue((ROOT / ACCEPTANCE_PATH).is_file())

    def test_missing_a3_binding_fails_closed(self) -> None:
        broken_root = ROOT / "does-not-exist"
        with self.assertRaises(Task26AdversarialAcceptanceError):
            build_acceptance(broken_root)


if __name__ == "__main__":
    unittest.main()
