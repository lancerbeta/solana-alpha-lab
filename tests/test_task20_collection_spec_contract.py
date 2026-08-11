from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "task20_collection_spec_contract_v1.md"
)
SPEC_PATH = ROOT / "configs" / "collection_spec_v1.yaml"
EXPECTED_CONTRACT_SHA256 = (
    "33a7317ade7ab0239c7ba7e84bbde02cf1f9d9a5199c713140388ab10b1b2d79"
)
EXPECTED_SPEC_SHA256 = (
    "c8c734eb76a5c13e7c49d0954e10e777d2f2a1cfe858ed688146a7c84269199d"
)
EXPECTED_MANAGED_FILES = [
    "docs/contracts/task20_collection_spec_contract_v1.md",
    "configs/collection_spec_v1.yaml",
    "tests/test_task20_collection_spec_contract.py",
]
EXPECTED_INPUTS = {
    "ARCH-INTENT-002": (
        (
            "docs/architecture/intents/"
            "ARCH-INTENT-002-hypothesis-factory-operating-model.md"
        ),
        "ea094d88abf635fbe4df3b1ff9b3f0e80cb87dfa836f67505173766e69708639",
    ),
    "CONTRACT-T15-BOUNDED-SUSTAINED-COLLECTION-001": (
        "docs/contracts/bounded_sustained_collection_contract_v1.md",
        "65f0ca725e8e3a28976d3f7286c8f8cea49180588704b12d75ddc7d12be7310e",
    ),
    "CONTRACT-T06-RAW-STORAGE-001": (
        "docs/contracts/raw_storage_contract_v1.md",
        "4a87ffa1abad5b14fedd5af315794155f076a3c8269b6eb4a3259323f5c77a84",
    ),
    "CONTRACT-T06-DATASET-MANIFEST-001": (
        "docs/contracts/dataset_manifest_contract_v1.md",
        "6482e695f39985e93a729ea7846347daaf4949dfa40a0da9fb187af5f72d1769",
    ),
    "CONTRACT-T06-STORAGE-BUDGET-001": (
        "docs/contracts/storage_budget_contract_v1.md",
        "40ccbf82b55004fdd34632f99ef645d4d44c49e9eb3b6811f32f56653b966815",
    ),
    "CONTRACT-T18-CONTENT-ADDRESSED-BACKUP-RESTORE-001": (
        "docs/contracts/task18_content_addressed_backup_restore_contract_v1.md",
        "dec80ed2e4f340668663f9431f01bdca1d31dcd767666a34b89a964566293f23",
    ),
    "EVIDENCE-T19-ACCEPTANCE-CATALOG-FACTORY-FIT-001": (
        "docs/evidence/task19/acceptance_catalog_factory_fit_v1.json",
        "fd1a18a6439c040a0b9b1fab6f175643969629c94249db0fe6ebcb2daad2b735",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task20CollectionSpecContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_bytes = CONTRACT_PATH.read_bytes()
        cls.contract = cls.contract_bytes.decode("utf-8")
        cls.spec_bytes = SPEC_PATH.read_bytes()
        cls.spec = yaml.safe_load(cls.spec_bytes)

    def test_candidate_identity_and_entry_gate_are_exact(self) -> None:
        self.assertEqual(sha256(CONTRACT_PATH), EXPECTED_CONTRACT_SHA256)
        self.assertEqual(sha256(SPEC_PATH), EXPECTED_SPEC_SHA256)
        self.assertEqual(self.spec["spec_id"], "COLLECTION-SPEC-T20-001")
        self.assertEqual(self.spec["spec_version"], "1.0")
        self.assertEqual(
            self.spec["atom_id"],
            "T20-A2_FROZEN_COLLECTION_SPEC_CONTRACT_V1",
        )
        self.assertEqual(
            self.spec["status"],
            "FROZEN_CONTRACT_NO_COLLECTION",
        )
        gate = self.spec["entry_gate"]
        self.assertEqual(gate["verdict"], "START_AS_WRITTEN")
        self.assertEqual(
            gate["source_activation"],
            "ACTIVATION_CONFIRMED_USER_SMOKE",
        )
        self.assertEqual(
            gate["accepted_main_commit"],
            "0284a684c8791b8a06296e6c5f8546c8dd913198",
        )
        self.assertEqual(
            gate["accepted_main_tree"],
            "8837e888559be8945fffb4d4110268cc44ad2848",
        )
        self.assertEqual(
            gate["catalog"],
            {
                "version": "0.24.0",
                "assets": 331,
                "asset_registries": 4,
                "schemas": 4,
                "queries": 8,
            },
        )

    def test_frozen_input_hashes_preserve_historical_snapshots(self) -> None:
        observed = {
            row["asset_id"]: (row["path"], row["sha256"])
            for row in self.spec["frozen_inputs"]
        }
        self.assertEqual(observed, EXPECTED_INPUTS)
        for asset_id, (relative_path, expected_hash) in EXPECTED_INPUTS.items():
            if asset_id == "ARCH-INTENT-002":
                continue
            with self.subTest(asset_id=asset_id):
                self.assertEqual(sha256(ROOT / relative_path), expected_hash)

    def test_acquisition_precedence_remains_hypothesis_driven(self) -> None:
        self.assertEqual(
            self.spec["acquisition_precedence"],
            [
                "THIN_ONLINE_DECISION_LEDGER",
                "HISTORICAL_BATCH_FIRST",
                "REUSABLE_CONTENT_ADDRESSED_CACHE",
                "HYPOTHESIS_DATASET",
                (
                    "TRIGGERED_LIVE_CAPTURE_ONLY_IF_"
                    "HISTORY_IS_INSUFFICIENT"
                ),
            ],
        )
        universe = self.spec["universe_contract"]
        self.assertFalse(universe["global_solana_universe_authorized"])
        self.assertFalse(universe["market_wide_tick_capture_authorized"])
        self.assertFalse(
            universe["detailed_data_authority_inherits_across_hypotheses"]
        )
        self.assertTrue(universe["multi_hypothesis_membership_allowed"])
        self.assertEqual(
            universe["admission_unit"],
            "NAMED_HYPOTHESIS_VERSION_EVALUATES_MINT_OR_POOL",
        )

    def test_membership_lifecycle_is_append_only_and_versioned(self) -> None:
        lifecycle = self.spec["membership_lifecycle"]
        self.assertEqual(lifecycle["event_model"], "APPEND_ONLY")
        self.assertEqual(lifecycle["initial_state"], "OUTSIDE")
        self.assertEqual(
            set(lifecycle["states"]),
            {
                "OUTSIDE",
                "EVALUATED_REJECTED",
                "EVALUATED_NOT_EVALUABLE",
                "WATCHLIST_ACTIVE",
                "WATCHLIST_EXITED",
            },
        )
        exited = next(
            row
            for row in lifecycle["allowed_transitions"]
            if row["from"] == "WATCHLIST_EXITED"
        )
        self.assertEqual(exited["to"], ["WATCHLIST_EXITED"])
        self.assertEqual(
            lifecycle["reactivation_after_exit"],
            "NEW_ACTIVATION_EPOCH_STARTS_FROM_OUTSIDE",
        )
        self.assertFalse(lifecycle["historical_transition_rewrite_allowed"])
        self.assertTrue(lifecycle["rejected_and_not_evaluable_retained"])

    def test_t0_is_a_thin_decision_ledger_not_a_market_recorder(self) -> None:
        tier = self.spec["data_tiers"]["T0"]
        self.assertEqual(tier["mode"], "EVENT_DRIVEN")
        self.assertFalse(tier["global_always_on_feed"])
        self.assertEqual(
            tier["eligibility"],
            "CANDIDATE_EVALUATED_BY_NAMED_HYPOTHESIS",
        )
        self.assertEqual(
            tier["conditional_fields"]["quote_or_liquidity_snapshot"],
            "ONLY_IF_USED_BY_DECISION",
        )
        self.assertTrue(
            {
                "exact_rule_input_values",
                "evaluation_result",
                "reason_codes",
                "missingness_codes",
                "membership_transition",
                "first_reliable_available_at",
            }.issubset(tier["required_fields"])
        )
        self.assertIn(
            "CONTINUOUS_ALL_TOKEN_PRICE_TICKS",
            tier["forbidden"],
        )

    def test_t1_is_historical_cache_first_without_global_minute_cadence(
        self,
    ) -> None:
        tier = self.spec["data_tiers"]["T1"]
        self.assertEqual(tier["mode"], "HYDRATE_ON_DEMAND")
        self.assertTrue(tier["named_consumer_required"])
        self.assertEqual(
            tier["source_precedence"],
            [
                "HISTORICAL_BATCH",
                "CONTENT_ADDRESSED_CACHE",
                "NEW_FETCH_ONLY_IF_CACHE_INCOMPATIBLE",
            ],
        )
        self.assertEqual(tier["default_bar_candidate"]["cadence"], "PT1M")
        self.assertEqual(
            tier["default_bar_candidate"]["authority"],
            "CANDIDATE_ONLY_NOT_GLOBAL_DEFAULT",
        )
        self.assertFalse(tier["winner_only_population_allowed"])
        self.assertFalse(tier["historical_availability_backdating_allowed"])

    def test_t2_requires_all_live_capture_admission_conditions(self) -> None:
        tier = self.spec["data_tiers"]["T2"]
        self.assertFalse(tier["speculative_collection_allowed"])
        self.assertFalse(tier["market_wide_capture_allowed"])
        self.assertEqual(
            set(tier["all_admission_conditions"]),
            {
                "NAMED_IMMUTABLE_HYPOTHESIS_DATA_REQUIREMENT_MANIFEST",
                "FIELD_FORWARD_ONLY_OR_HISTORICAL_INADEQUACY_PROVEN",
                "FIELD_CAN_CHANGE_HYPOTHESIS_OR_EXECUTION_VERDICT",
                (
                    "CHEAPER_CADENCE_NARROWER_POPULATION_"
                    "BATCH_AND_CACHE_FALSIFIED"
                ),
                "EXACT_WATCHLIST_OR_CONTROL_MEMBERSHIP",
                "HARD_PHYSICAL_BUDGETS_FROZEN",
                "SEPARATE_EXTERNAL_ATOM_AUTHORIZED",
            },
        )
        self.assertEqual(
            tier["stop_policy"],
            (
                "STOP_WITH_HYPOTHESIS_OR_EPOCH_UNLESS_"
                "ANOTHER_IMMUTABLE_CONSUMER_EXISTS"
            ),
        )

    def test_every_field_requires_consumer_availability_and_cost_truth(
        self,
    ) -> None:
        contract = self.spec["field_contract"]
        self.assertTrue(
            {
                "field_id",
                "units",
                "natural_keys",
                "tier",
                "named_consumers",
                "purpose_and_decision_impact",
                "first_reliable_available_at_semantics",
                "availability_class",
                "cadence_mode",
                "retention_class",
                "revision_policy",
                "quality_checks",
                "freshness_rule",
                "missingness_policy",
                "request_credit_byte_storage_time_attribution",
            }.issubset(contract["every_field_requires"])
        )
        self.assertEqual(
            set(contract["availability_classes"]),
            {
                "RECONSTRUCTIBLE_LATER",
                "FORWARD_ONLY",
                "PARTIAL_OR_VENDOR_DEPENDENT",
                "DERIVED_PIT",
            },
        )
        for key in (
            "missing_named_consumer",
            "missing_decision_impact",
            "missing_availability_semantics",
            "missing_bounded_cost_attribution",
        ):
            with self.subTest(key=key):
                self.assertEqual(contract[key], "EXCLUDED")

    def test_availability_is_point_in_time_and_fail_closed(self) -> None:
        availability = self.spec["availability_contract"]
        self.assertEqual(availability["timezone"], "UTC")
        self.assertEqual(
            availability["required_time_axes"],
            [
                "event_at",
                "observed_at",
                "first_reliable_available_at",
                "available_to_strategy_at",
                "ingested_at",
            ],
        )
        self.assertFalse(availability["event_time_grants_strategy_availability"])
        self.assertFalse(availability["historical_fetch_backdates_availability"])
        self.assertFalse(availability["runtime_maximum_selects_cutoff"])
        self.assertEqual(
            availability["late_revised_duplicate_unavailable_rows"],
            "RETAIN_TYPED_STATE",
        )

    def test_budget_uses_physical_caps_not_plan_names_or_usd(self) -> None:
        budget = self.spec["budget_contract"]
        self.assertFalse(budget["unlimited_or_missing_cap_allowed"])
        self.assertTrue(
            {
                "provider_requests",
                "provider_credits",
                "response_bytes",
                "stored_bytes",
                "active_entities",
                "wall_clock_seconds",
                "concurrency",
                "retry_count",
                "dataset_bytes",
                "minimum_free_space_bytes",
            }.issubset(budget["physical_units_are_authority"])
        )
        volatile = budget["volatile_price_metadata"]
        self.assertEqual(volatile["authority"], "ADVISORY_ONLY")
        self.assertFalse(volatile["purchase_authority"])
        inherited = budget["inherited_pre_task21_measurement_ceiling"]
        self.assertEqual(
            inherited["status"],
            "REFERENCE_MAXIMUM_NOT_TASK21_BUDGET_OR_AUTHORITY",
        )
        self.assertEqual(inherited["max_provider_credits"], 40_000)
        self.assertEqual(inherited["max_local_dataset_bytes"], 256 * 1024**2)
        self.assertEqual(
            inherited["min_free_disk_bytes_after_allocation"],
            2 * 1024**3,
        )

    def test_identity_and_recovery_obligations_bind_future_runs(self) -> None:
        identity = self.spec["identity_and_change_policy"]
        self.assertEqual(
            identity["semantic_change"],
            "NEW_SPEC_VERSION_DECISION_AND_CONTENT_HASH",
        )
        self.assertFalse(identity["accepted_prior_bytes_mutable"])
        self.assertFalse(identity["mutable_alias_selects_runtime_contract"])
        self.assertFalse(identity["ui_filename_suffix_is_version"])
        self.assertTrue(
            {
                "collection_spec_sha256",
                "hypothesis_data_manifest_sha256",
                "membership_evidence_id",
                "availability_contract_version",
                "budget_policy_version",
                "observed_consumption",
            }.issubset(
                identity["future_plan_run_dataset_partition_and_backup_bind"]
            )
        )
        recovery = self.spec["recovery_policy_handoff"]
        self.assertEqual(
            recovery["status"],
            "REQUIRED_IN_T20_A3_BEFORE_ANY_FORWARD_COLLECTION",
        )
        self.assertIn(
            "isolated_restore_test_cadence",
            recovery["required_dimensions"],
        )
        self.assertIn(
            "degraded_overdue_and_evidence_loss_states",
            recovery["required_dimensions"],
        )

    def test_reuse_and_catalog_boundaries_are_small_and_explicit(self) -> None:
        reuse = self.spec["reuse"]
        self.assertIn(
            "CONTRACT-T15-BOUNDED-SUSTAINED-COLLECTION-001",
            reuse["adopt"],
        )
        self.assertIn(
            "CONTRACT-T18-CONTENT-ADDRESSED-BACKUP-RESTORE-001",
            reuse["adopt"],
        )
        self.assertEqual(reuse["fork"], [])
        self.assertEqual(reuse["build"], [])
        self.assertEqual(reuse["new_dependency_count"], 0)
        self.assertFalse(reuse["collector_built"])
        self.assertFalse(reuse["scheduler_built"])
        self.assertFalse(reuse["generic_data_platform_built"])

        catalog = self.spec["catalog"]
        self.assertFalse(catalog["registered_in_atom2"])
        self.assertEqual(
            catalog["status"],
            "CATALOG_TRANSACTION_PENDING_T20_A4",
        )
        self.assertFalse(catalog["blocks_contract_freeze"])
        self.assertTrue(catalog["blocks_task20_done"])

    def test_atom_authority_is_local_write_only_and_zero_effect(self) -> None:
        authority = self.spec["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(
            authority["source"],
            "REPO_STANDING_AUTONOMY_AFTER_EXPLICIT_CONTINUE",
        )
        self.assertEqual(authority["managed_files"], EXPECTED_MANAGED_FILES)
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "drive_reads",
            "drive_writes",
            "credential_use",
            "collector_executions",
            "raw_or_dataset_writes",
            "cash_spend_usd_cents",
            "provider_credits",
            "dependency_changes",
        ):
            with self.subTest(field=field):
                self.assertEqual(authority[field], 0)
        for field in (
            "commit",
            "push",
            "pull_request",
            "merge",
            "ui_changes",
            "destructive_actions",
        ):
            with self.subTest(field=field):
                self.assertFalse(authority[field])
        self.assertEqual(
            self.spec["next_atom"]["atom_id"],
            "T20-A3_COVERAGE_RETENTION_AND_RECOVERY_POLICY_V1",
        )
        self.assertFalse(
            self.spec["next_atom"]["forward_collection_authorized"]
        )

    def test_contract_contains_decision_changing_boundaries(self) -> None:
        for marker in (
            "The collection universe is not all Solana tokens",
            "`PT1M` is not a global cadence",
            "Speculative T2 and market-wide tick",
            "capture are forbidden",
            "first_reliable_available_at",
            "UNLIMITED",
            "not a TASK-21 budget and not collection authority",
            "TASK-20 A3 must therefore freeze",
            "no collector, scheduler, data warehouse",
            "T20-A3_COVERAGE_RETENTION_AND_RECOVERY_POLICY_V1",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)

    def test_authored_files_are_sanitized_and_repository_clean(self) -> None:
        candidates = {
            "contract": self.contract_bytes,
            "spec": self.spec_bytes,
            "test": Path(__file__).read_bytes(),
        }
        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\b[a-z]:[\\/]"),
            "user_home_path": re.compile(r"(?i)/(?:users|home)/[^/\s]+"),
            "private_key_block": re.compile(
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            ),
            "credential_assignment": re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)"
                r"\s*[:=]\s*[\"'][^\"']+[\"']"
            ),
        }
        for label, candidate in candidates.items():
            with self.subTest(file=label):
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
                for pattern_name, pattern in prohibited.items():
                    with self.subTest(pattern=pattern_name):
                        self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
