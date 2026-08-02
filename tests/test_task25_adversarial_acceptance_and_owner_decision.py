from __future__ import annotations

import unittest
from pathlib import Path

from src.solana_alpha_lab import task25_adversarial_acceptance as acceptance


REPO_ROOT = Path(__file__).resolve().parents[1]


class Task25AdversarialAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projection, cls.matrix = acceptance.load_frozen_inputs(REPO_ROOT)
        cls.receipt = acceptance.build_acceptance(REPO_ROOT)

    def _mutation(self, mutation_id: str) -> dict:
        matches = [
            item
            for item in self.matrix["mutations"]
            if item["mutation_id"] == mutation_id
        ]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def _assert_mutation_error(self, mutation_id: str) -> None:
        mutation = self._mutation(mutation_id)
        mutated = acceptance.apply_mutation(self.projection, mutation)
        with self.assertRaisesRegex(
            acceptance.Task25AdversarialAcceptanceError,
            f"^{mutation['expected_error']}$",
        ):
            acceptance.validate_projection(mutated)

    def test_01_all_frozen_inputs_are_hash_exact(self) -> None:
        for binding in acceptance.FROZEN_INPUTS.values():
            path = REPO_ROOT / binding["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(acceptance.sha256_file(path), binding["sha256"])

    def test_02_owner_decision_is_exactly_one(self) -> None:
        acceptance.validate_owner_decision(REPO_ROOT)
        self.assertEqual(self.receipt["owner_decision"]["count"], 1)
        self.assertEqual(
            self.receipt["owner_decision"]["decision"], acceptance.DECISION
        )

    def test_03_upstream_field_capability_is_hash_bound_code_evidence(self) -> None:
        checks = acceptance.validate_upstream_field_capability(REPO_ROOT)
        self.assertEqual(len(checks), 3)
        self.assertIn("EXACT_MINT_AND_ATOMIC_AMOUNT_VALIDATION_PRESENT", checks)
        self.assertEqual(
            self.receipt["upstream_capability"]["status"],
            "PRESENT_IN_HASH_BOUND_CODE_NOT_REOPENED_AS_RAW_VALUES",
        )

    def test_04_a4_baseline_is_accepted_without_promotion(self) -> None:
        acceptance.validate_projection(self.projection)
        baseline = self.receipt["baseline_acceptance"]
        self.assertEqual(baseline["outcomes"], 108)
        self.assertEqual(baseline["supported"], 9)
        self.assertEqual(baseline["unknown"], 99)
        self.assertEqual(baseline["fillable_supported"], 0)
        self.assertEqual(baseline["quote_exit_supported"], 0)

    def test_05_all_fourteen_adversarial_mutations_are_rejected(self) -> None:
        results = acceptance.run_adversarial_matrix(self.projection, self.matrix)
        self.assertEqual(len(results), 14)
        self.assertTrue(all(item["status"] == "PASS_REJECTED" for item in results))
        self.assertEqual(
            [item["expected_error"] for item in results],
            [item["observed_error"] for item in results],
        )

    def test_06_fillable_promotion_is_rejected(self) -> None:
        self._assert_mutation_error("A5-MUT-001")

    def test_07_quote_exit_promotion_is_rejected(self) -> None:
        self._assert_mutation_error("A5-MUT-002")

    def test_08_quote_cannot_become_realized_vwap(self) -> None:
        self._assert_mutation_error("A5-MUT-003")

    def test_09_quote_cannot_become_net(self) -> None:
        self._assert_mutation_error("A5-MUT-004")

    def test_10_sparse_panel_cannot_become_continuous_path(self) -> None:
        self._assert_mutation_error("A5-MUT-005")

    def test_11_touch_requires_frozen_threshold_evidence(self) -> None:
        self._assert_mutation_error("A5-MUT-006")

    def test_12_unknown_cannot_become_zero(self) -> None:
        self._assert_mutation_error("A5-MUT-007")

    def test_13_actual_panel_time_cannot_become_nominal_horizon(self) -> None:
        self._assert_mutation_error("A5-MUT-008")

    def test_14_provider_error_cannot_become_no_route(self) -> None:
        self._assert_mutation_error("A5-MUT-009")

    def test_15_records_cannot_be_dropped_or_identity_invented(self) -> None:
        self._assert_mutation_error("A5-MUT-010")
        self._assert_mutation_error("A5-MUT-011")

    def test_16_quote_cannot_become_fill_or_settlement(self) -> None:
        self._assert_mutation_error("A5-MUT-012")

    def test_17_r3_and_raw_reopen_mutations_are_rejected(self) -> None:
        self._assert_mutation_error("A5-MUT-013")
        self._assert_mutation_error("A5-MUT-014")

    def test_18_rejected_alternatives_are_explicit(self) -> None:
        self.assertEqual(
            self.receipt["rejected_alternatives"],
            [
                "ACCEPT_CURRENT_TRACKED_PROJECTION_FOR_OWNER_COMPARISON",
                "STOP_UNDERLYING_R2_AS_INFEASIBLE",
                "OPEN_R3_OR_COLLECT_MORE_DATA",
            ],
        )

    def test_19_next_reprojection_is_not_self_authorized(self) -> None:
        boundary = self.receipt["next_boundary"]
        self.assertEqual(boundary["candidate_atom"], acceptance.NEXT_ATOM)
        self.assertFalse(boundary["authorized_by_a5"])
        self.assertTrue(boundary["requires_new_pre_read_receipt"])
        self.assertEqual(boundary["r3_access"], "DENY")

    def test_20_a5_has_zero_external_and_data_side_effects(self) -> None:
        side_effects = self.receipt["side_effects"]
        self.assertTrue(all(value == 0 for value in side_effects.values()))
        self.assertEqual(
            self.receipt["owner_decision"]["current_projection_disposition"],
            "ACCEPT_AS_NEGATIVE_RESULT_NOT_DECISION_SURFACE",
        )

    def test_21_acceptance_is_deterministic_and_stored(self) -> None:
        expected = acceptance.build_acceptance_bytes(REPO_ROOT)
        self.assertEqual(
            expected,
            acceptance.canonical_json_bytes(acceptance.build_acceptance(REPO_ROOT)),
        )
        self.assertEqual(
            acceptance.check_stored_output(REPO_ROOT),
            acceptance.sha256_bytes(expected),
        )


if __name__ == "__main__":
    unittest.main()
