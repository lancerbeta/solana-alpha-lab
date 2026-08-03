"""Tests for TASK-26 A6 adversarial R2 execution-cost acceptance."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from solana_alpha_lab.task26_r2_adversarial_acceptance import (  # noqa: E402
    EXPECTED_BLOCKED_PAIR_ID,
    EXPECTED_READY_PAIR_COUNT,
    Task26R2AdversarialAcceptanceError,
    build_acceptance,
    check_stored_output,
    run_adversarial_cases,
    validate_projection,
    _load_frozen_context,
)


class Task26R2AdversarialAcceptanceTests(unittest.TestCase):
    def test_all_twelve_mutations_are_rejected_with_the_declared_code(self) -> None:
        outcomes = run_adversarial_cases(REPO_ROOT)

        self.assertEqual(len(outcomes), 12)
        self.assertTrue(all(row["status"] == "PASS_EXACT_REJECTION" for row in outcomes))
        self.assertEqual(
            [row["mutation_id"] for row in outcomes],
            [f"m{index:02d}_{suffix}" for index, suffix in enumerate((
                "quote_to_actual_fill",
                "claim_actual_settlement",
                "emit_numeric_netreturn",
                "reclassify_netreturn_observed",
                "erase_latency_unknown",
                "open_raw_r2",
                "open_r3",
                "allow_r3_boundary",
                "self_authorize_next",
                "drop_pair",
                "duplicate_ready_pair",
                "clear_latency_blocker",
            ), start=1)],
        )

    def test_baseline_retains_quote_only_and_not_computable_boundaries(self) -> None:
        projection, _ = _load_frozen_context(REPO_ROOT)
        validate_projection(projection)

        self.assertEqual(projection["truth_boundary"]["quote_truth"], "POINT_IN_TIME_QUOTE_ONLY")
        self.assertFalse(projection["truth_boundary"]["actual_fill_or_settlement_observed"])
        self.assertIsNone(projection["net_return_surface"]["amount_atomic"])
        self.assertEqual(projection["summary"]["execution_cost_input_states"]["QUOTE_COST_INPUT_READY"], EXPECTED_READY_PAIR_COUNT)

    def test_duplicate_pair_is_rejected_without_accepting_the_changed_surface(self) -> None:
        projection, _ = _load_frozen_context(REPO_ROOT)
        changed = copy.deepcopy(projection)
        changed["pair_readiness"]["quote_cost_input_ready_pair_ids"][1] = changed["pair_readiness"]["quote_cost_input_ready_pair_ids"][0]

        with self.assertRaisesRegex(Task26R2AdversarialAcceptanceError, "ready_pair_id_duplicate"):
            validate_projection(changed)

    def test_owner_decision_extends_evidence_without_opening_r3(self) -> None:
        receipt = build_acceptance(REPO_ROOT)

        self.assertEqual(receipt["owner_decision"]["decision"], "EXTEND_EXECUTION_EVIDENCE")
        self.assertEqual(receipt["next_boundary"]["r3_access"], "DENY")
        self.assertEqual(receipt["measured_boundary"]["r3_paths_or_values_read"], 0)
        self.assertEqual(EXPECTED_BLOCKED_PAIR_ID, "T25-R2-PAIR-1afd5c77ae7cfe7c5287cf66")

    def test_stored_receipt_is_exact(self) -> None:
        self.assertRegex(check_stored_output(REPO_ROOT), r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
