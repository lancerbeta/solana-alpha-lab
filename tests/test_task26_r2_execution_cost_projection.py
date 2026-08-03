from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task26_r2_execution_cost_projection import (
    ACCEPTANCE_PATH,
    FROZEN_INPUTS,
    PROJECTION_PATH,
    Task26R2ExecutionCostProjectionError,
    build_acceptance,
    build_projection,
    check_stored_outputs,
)


class Task26R2ExecutionCostProjectionTests(unittest.TestCase):
    def test_exact_task25_r2_surface_and_a4_receipt_are_bound(self) -> None:
        projection = build_projection(ROOT)
        self.assertEqual(projection["input_bindings"], FROZEN_INPUTS)
        self.assertEqual(projection["summary"]["r2_surface_files_read"], 1)
        self.assertEqual(projection["summary"]["r2_raw_files_opened"], 0)

    def test_all_pairs_are_retained_and_only_supported_entry_pairs_are_ready(self) -> None:
        projection = build_projection(ROOT)
        self.assertEqual(projection["summary"]["pairs_input"], 36)
        self.assertEqual(projection["summary"]["pairs_output"], 36)
        self.assertEqual(projection["summary"]["records_dropped"], 0)
        self.assertEqual(
            projection["summary"]["execution_cost_input_states"],
            {"NOT_COMPUTABLE": 1, "QUOTE_COST_INPUT_READY": 35},
        )

    def test_quote_truth_never_becomes_fill_settlement_or_numeric_netreturn(self) -> None:
        projection = build_projection(ROOT)
        self.assertEqual(len(projection["pair_readiness"]["quote_cost_input_ready_pair_ids"]), 35)
        self.assertEqual(len(projection["pair_readiness"]["projection_records_sha256"]), 64)
        self.assertEqual(projection["truth_boundary"]["quote_truth"], "POINT_IN_TIME_QUOTE_ONLY")
        self.assertFalse(projection["truth_boundary"]["actual_fill_or_settlement_observed"])
        self.assertEqual(projection["net_return_surface"]["classification"], "NOT_COMPUTABLE")
        self.assertIsNone(projection["net_return_surface"]["amount_atomic"])
        self.assertIsNone(projection["net_return_surface"]["currency"])

    def test_latency_breach_pair_remains_not_computable(self) -> None:
        projection = build_projection(ROOT)
        blocked = projection["pair_readiness"]["not_computable_pairs"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["entry_assessment_reason"], "PROVIDER_LATENCY_LIMIT_EXCEEDED")
        self.assertEqual(blocked[0]["blocked_reason"], "ENTRY_PROVIDER_LATENCY_LIMIT_EXCEEDED")

    def test_acceptance_and_stored_outputs_are_exact(self) -> None:
        projection = build_projection(ROOT)
        acceptance = build_acceptance(ROOT, projection)
        self.assertEqual(acceptance["status"], "PASS_BOUNDED_R2_QUOTE_EXECUTION_COST_INPUT_SURFACE_WITH_LIMITATIONS")
        self.assertTrue(all(check["status"] == "PASS" for check in acceptance["checks"]))
        hashes = check_stored_outputs(ROOT)
        self.assertIn(PROJECTION_PATH.as_posix(), hashes)
        self.assertIn(ACCEPTANCE_PATH.as_posix(), hashes)

    def test_missing_bound_input_fails_closed(self) -> None:
        with self.assertRaises(Task26R2ExecutionCostProjectionError):
            build_projection(ROOT / "missing-root")


if __name__ == "__main__":
    unittest.main()
