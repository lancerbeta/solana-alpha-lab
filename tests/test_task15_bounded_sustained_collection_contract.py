from __future__ import annotations

import hashlib
import json
import math
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "bounded_sustained_collection_contract_v1.md"
)
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task15"
    / "bounded_sustained_collection_contract_v1.json"
)
EXPECTED_CONTRACT_SHA256 = (
    "65f0ca725e8e3a28976d3f7286c8f8cea49180588704b12d75ddc7d12be7310e"
)
EXPECTED_FIXTURE_SHA256 = (
    "a1258f56c7521922876c1edd73ca77125e31294b623b8b793d6d5cfe2542235b"
)
UPSTREAM = {
    "ARCH-INTENT-001": (
        (
            "docs/architecture/intents/"
            "ARCH-INTENT-001-hypothesis-factory-and-regime-aware-"
            "orchestration.md"
        ),
        "59f810a75bce0c9a55f3e7dd751744a06d2e4a19a0378f47b08fb2b2bc2edad6",
    ),
    "EVIDENCE-T01-HYPOTHESIS-DATA-COVERAGE-MATRIX-001": (
        (
            "docs/evidence/pre_git/task01/"
            "hypothesis_data_coverage_matrix_v1.md"
        ),
        "5ba0b904d4ca3942cb701fa28ccbc7c35c8ce580385c6766a2fc4596b2c16814",
    ),
    "EVIDENCE-T01-DATA-OPTION-TIERS-001": (
        "docs/evidence/pre_git/task01/data_option_tiers_v1.yaml",
        "f19c0263f94b19135d91d2e61f1f14d158b48c4bd030a514d640041df0210d13",
    ),
    "DECISION-T14-PROVIDER-PURCHASE-001": (
        "docs/decisions/provider_decision_v2.md",
        "39dbf21501f950e0365b04668f10387d43cae2db66a997159b0061998c09fc41",
    ),
    "FIXTURE-T14-PROVIDER-PURCHASE-DECISION-001": (
        "tests/fixtures/task14/provider_purchase_decision_v1.json",
        "572243a331b75a3723893e4fe24730c15af6dc7a77d7f0bfa2c96e968291eee1",
    ),
    "EVIDENCE-T14-PROVIDER-PURCHASE-ACCEPTANCE-001": (
        (
            "docs/evidence/task14/"
            "provider_purchase_decision_acceptance_receipt_v1.json"
        ),
        "47d950c863822bcfa72ade4172d1b834f029ac1198e05af6986939c2de94eb9e",
    ),
}


class Task15HypothesisDrivenAcquisitionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_bytes = CONTRACT_PATH.read_bytes()
        cls.contract = cls.contract_bytes.decode("utf-8")
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.fixture = json.loads(cls.fixture_bytes)

    def test_candidate_bytes_identity_and_current_disposition(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.contract_bytes).hexdigest(),
            EXPECTED_CONTRACT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            self.fixture["contract_id"],
            "CONTRACT-T15-BOUNDED-SUSTAINED-COLLECTION-001",
        )
        self.assertEqual(
            self.fixture["atom_id"],
            "T15-A2_FROZEN_BOUNDED_MEASUREMENT_CONTRACT_V1",
        )
        self.assertEqual(
            self.fixture["status"],
            "FROZEN_MEASUREMENT_NOT_DUE",
        )
        self.assertEqual(
            self.fixture["current_disposition"],
            {
                "acquisition_path": "MEASUREMENT_NOT_DUE",
                "provider_purchase": "DEFER",
                "reason": (
                    "NO_IMMUTABLE_NAMED_HYPOTHESIS_DATA_"
                    "REQUIREMENT_MANIFEST"
                ),
            },
        )

    def test_upstream_evidence_hashes_match_repository_bytes(self) -> None:
        observed = {
            item["asset_id"]: (item["repository_path"], item["sha256"])
            for item in self.fixture["upstream_evidence"]
        }
        self.assertEqual(observed, UPSTREAM)
        for asset_id, (relative_path, expected) in UPSTREAM.items():
            with self.subTest(asset_id=asset_id):
                actual = hashlib.sha256((ROOT / relative_path).read_bytes())
                self.assertEqual(actual.hexdigest(), expected)

    def test_previous_tasks_are_reused_without_global_collector_claim(
        self,
    ) -> None:
        compatibility = self.fixture["prior_task_compatibility"]
        self.assertIn(
            "TASK03_CATALOG_AND_LIFECYCLE_REGISTRIES",
            compatibility["neutral_or_reusable"],
        )
        self.assertIn(
            "TASK14_PROVIDER_PURCHASE_DEFER",
            compatibility["neutral_or_reusable"],
        )
        self.assertTrue(compatibility["historical_bytes_unchanged"])
        self.assertEqual(
            set(compatibility["superseded_operational_interpretation"]),
            {
                "T0_CORE_IMPLIES_GLOBAL_DENSE_OR_ALWAYS_ON_COLLECTION",
                (
                    "PROVISIONAL_CONTINUOUS_WHEN_COLLECTOR_RUNS_"
                    "IS_A_PRODUCTION_DEFAULT"
                ),
                (
                    "PROVISIONAL_RAW_RETENTION_IS_ENFORCED_"
                    "BEFORE_TASK16"
                ),
            },
        )

    def test_acquisition_precedence_is_batch_first_and_cache_reusing(
        self,
    ) -> None:
        self.assertEqual(
            self.fixture["acquisition_precedence"],
            [
                "THIN_ONLINE_DECISION_LEDGER",
                "HISTORICAL_BATCH_FIRST",
                "REUSABLE_CONTENT_ADDRESSED_CACHE",
                "HYPOTHESIS_DATASET",
                (
                    "TRIGGERED_LIVE_CAPTURE_ONLY_IF_HISTORY_"
                    "IS_INSUFFICIENT"
                ),
            ],
        )

    def test_watchlists_are_hypothesis_owned_and_reactivation_is_versioned(
        self,
    ) -> None:
        ownership = self.fixture["hypothesis_ownership"]
        self.assertFalse(ownership["global_detailed_watchlist"])
        self.assertTrue(ownership["multi_watchlist_membership_allowed"])
        self.assertFalse(ownership["cross_hypothesis_authority_inheritance"])
        self.assertEqual(
            ownership["reactivation"],
            "NEW_EPOCH_NO_HISTORICAL_REWRITE",
        )
        self.assertTrue(
            {
                "hypothesis_id",
                "hypothesis_version",
                "trial_id_or_activation_epoch",
                "falsifier",
                "control_spec",
                "regime_context_requirements",
            }.issubset(ownership["required_identity_fields"])
        )
        self.assertIn(
            "evaluation_result",
            ownership["membership_and_evaluation_fields"],
        )
        self.assertIn(
            "reason_codes",
            ownership["membership_and_evaluation_fields"],
        )

    def test_data_manifest_owns_fields_cadence_population_and_falsifier(
        self,
    ) -> None:
        manifest = self.fixture["hypothesis_data_requirement_manifest"]
        self.assertTrue(manifest["required_before_any_acquisition"])
        self.assertTrue(
            {
                "candidate_population_spec",
                "rejected_and_control_population_spec",
                "feature_definitions",
                "label_definitions",
                "cadence",
                "pit_and_leakage_rules",
                "coverage_class_per_field",
                "request_credit_storage_time_caps",
                "cheapest_falsifier",
                "live_capture_justification",
            }.issubset(manifest["required_fields"])
        )
        self.assertEqual(
            set(manifest["coverage_classes"]),
            {
                "RECONSTRUCTIBLE_LATER",
                "FORWARD_ONLY",
                "PARTIAL_OR_VENDOR_DEPENDENT",
                "DERIVED_PIT",
            },
        )
        self.assertEqual(
            manifest["field_or_cadence_without_named_consumer"],
            "EXCLUDED",
        )

    def test_thin_online_ledger_preserves_negative_decisions_not_ticks(
        self,
    ) -> None:
        ledger = self.fixture["thin_online_decision_ledger"]
        self.assertFalse(ledger["always_on_detailed_market_data"])
        self.assertTrue(ledger["append_only"])
        self.assertTrue(
            {
                "exact_rule_input_values",
                "admit_reject_or_not_evaluable",
                "reason_codes",
                "missingness_codes",
                "coverage_gaps",
                "watchlist_membership_transition",
            }.issubset(ledger["fields"])
        )
        self.assertIn(
            "CONTINUOUS_ALL_TOKEN_PRICE_TICKS",
            ledger["forbidden"],
        )
        self.assertIn(
            "RICH_DATA_FOR_EVERY_DISCOVERED_TOKEN",
            ledger["forbidden"],
        )

    def test_retrospective_batches_include_controls_and_preserve_pit(
        self,
    ) -> None:
        batch = self.fixture["historical_batch"]
        self.assertTrue(batch["default_for_reconstructible_fields"])
        self.assertEqual(
            set(batch["allowed_populations"]),
            {
                "ADMITTED_WATCHLIST_MEMBERS",
                "LATER_FILTER_REJECTIONS",
                "EXPLICIT_SAMPLED_CONTROL_COHORT",
                "BOUNDED_BROAD_HISTORICAL_UNIVERSE_FOR_PATTERN_DISCOVERY",
            },
        )
        self.assertFalse(batch["winner_only_population_allowed"])
        self.assertFalse(batch["selected_candidate_only_population_allowed"])
        self.assertTrue(batch["compatible_hypothesis_cache_reuse_required"])
        self.assertFalse(
            batch["historical_reconstruction_backdates_availability"]
        )

    def test_live_capture_requires_named_need_and_historical_falsifier(
        self,
    ) -> None:
        admission = set(self.fixture["live_capture_admission"]["all_required"])
        self.assertTrue(
            {
                "NAMED_IMMUTABLE_HYPOTHESIS_DATA_MANIFEST",
                "FIELD_FORWARD_ONLY_OR_HISTORICAL_SOURCE_INADEQUACY_PROVEN",
                "FIELD_CAN_CHANGE_HYPOTHESIS_OR_EXECUTION_VERDICT",
                "CHEAPER_CADENCE_FILTER_BATCH_AND_CACHE_PATHS_FALSIFIED",
                "FROZEN_WATCHLIST_AND_CONTROL_FIXTURE",
                "SEPARATE_EXPLICIT_EXTERNAL_ATOM",
            }.issubset(admission)
        )
        self.assertTrue(
            self.fixture["live_capture_admission"][
                "stop_with_hypothesis_or_epoch_by_default"
            ]
        )

    def test_fallback_live_measurement_is_a_ceiling_not_default(self) -> None:
        ceiling = self.fixture["future_live_measurement_ceiling"]
        self.assertFalse(ceiling["architecture_default"])
        self.assertTrue(ceiling["separate_external_authority_required"])
        self.assertEqual(ceiling["max_hypothesis_versions"], 1)
        self.assertEqual(ceiling["max_active_candidate_mints"], 10)
        self.assertEqual(ceiling["hard_credit_cap"], 40000)
        modeled = (
            ceiling["meter_credits"]
            * math.ceil(
                ceiling["max_metered_uncompressed_bytes"]
                / ceiling["meter_decimal_bytes"]
            )
            + ceiling["credit_guard"]
        )
        self.assertEqual(modeled, 39999)
        self.assertLess(modeled, ceiling["hard_credit_cap"])
        self.assertEqual(
            ceiling["max_local_dataset_bytes"],
            256 * 1024**2,
        )
        self.assertEqual(
            ceiling["min_free_disk_bytes_after_allocation"],
            2 * 1024**3,
        )

    def test_outcomes_do_not_turn_measurement_into_purchase_authority(
        self,
    ) -> None:
        self.assertEqual(
            set(self.fixture["acquisition_path_outcomes"]),
            {
                "HISTORICAL_BATCH_PATH_ACCEPTED",
                "LIVE_MEASUREMENT_ELIGIBLE",
                "MEASUREMENT_NOT_DUE",
                "ACQUISITION_PATH_INCONCLUSIVE",
            },
        )
        self.assertEqual(
            set(
                self.fixture[
                    "provider_decision_outcomes_after_eligible_live_measurement"
                ]
            ),
            {
                "FREE_TIER_SUFFICIENT_CANDIDATE",
                "PAID_PROPOSAL_ELIGIBLE_CANDIDATE",
                "MEASUREMENT_INCONCLUSIVE",
            },
        )

    def test_atom_has_zero_external_money_collection_and_git_authority(
        self,
    ) -> None:
        self.assertEqual(
            self.fixture["authority"],
            {
                "network_calls_in_atom": 0,
                "provider_api_rpc_wss_calls_in_atom": 0,
                "account_or_dashboard_actions": 0,
                "credential_use": 0,
                "dependency_changes": 0,
                "cash_spend_usd": 0,
                "collector_or_scheduler_actions": 0,
                "wallet_signer_transaction_actions": 0,
                "commit_push_pr_merge_actions": 0,
            },
        )
        self.assertEqual(
            self.fixture["catalog_transaction_status"],
            "DEFERRED_TO_T15_A3",
        )
        self.assertEqual(
            self.fixture["next_atom"],
            "T15-A3_DETERMINISTIC_ACCEPTANCE_AND_CATALOG_V1",
        )

    def test_files_have_repository_hygiene_and_no_machine_paths(self) -> None:
        for label, candidate in (
            ("contract", self.contract_bytes),
            ("fixture", self.fixture_bytes),
        ):
            with self.subTest(path=label):
                self.assertFalse(candidate.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", candidate)
                self.assertTrue(candidate.endswith(b"\n"))
                text = candidate.decode("utf-8")
                self.assertTrue(
                    all(
                        line.rstrip(" \t") == line
                        for line in text.splitlines()
                    )
                )
                self.assertIsNone(re.search(r"(?i)\b[a-z]:[\\/]", text))
                lowered = text.lower()
                self.assertFalse(
                    any(
                        token in lowered
                        for token in (
                            "api_key=",
                            "authorization:",
                            "private key",
                            "seed phrase",
                            "recovery phrase",
                        )
                    )
                )


if __name__ == "__main__":
    unittest.main()
