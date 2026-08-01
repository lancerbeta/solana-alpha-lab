from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "task22_group_aware_split_contract_v1.md"
)
SPEC_PATH = ROOT / "configs" / "task22_group_aware_split_v1.yaml"
EXPECTED_CONTRACT_SHA256 = (
    "75ecf347dc92e2ff7b08825e13be093a9f34f93b77dc989591d11083bd53c96f"
)
EXPECTED_SPEC_SHA256 = (
    "43e71918e4da1150defc97b812ea648fac9f3a3c567dba379f6948b0ac007272"
)
EXPECTED_MANAGED_FILES = [
    "docs/contracts/task22_group_aware_split_contract_v1.md",
    "configs/task22_group_aware_split_v1.yaml",
    "tests/test_task22_group_aware_split_contract.py",
]
EXPECTED_INPUTS = {
    "EVIDENCE-T21-FINAL-COHORT-FREEZE-001": (
        "configs/task21_final_cohort_freeze_v1.yaml",
        "d644c3432241a8ebbe74373038cfe0c15b87872e7afc6e96b6fade49e82d6fde",
    ),
    "DATA-T21-FINAL-DATASET-FREEZE-MANIFEST-001": (
        "docs/evidence/task21/final_dataset_freeze_manifest_v1.json",
        "295d29354554247e08ddd39cd9f6b642e262869f22a0da9925227e6fab378a0f",
    ),
    "EVIDENCE-T21-EFFECTIVE-SAMPLE-SUMMARY-001": (
        "docs/evidence/task21/effective_sample_summary_v1.json",
        "63ddb790dcd54191ac342aa8add5889c8647d2cf09d91c4d9ca14c67ca8b51fb",
    ),
    "EVIDENCE-T21-A7-ACCEPTANCE-001": (
        "docs/evidence/task21/a7_acceptance_catalog_factory_fit_v1.json",
        "e73f5b0c1f3b85ab19d7cf4a0ef460c681ce7b418a516db1a36b901d62b2454a",
    ),
    "EVIDENCE-T21-FINISH-GATE-001": (
        "docs/evidence/finish_gates/task21_finish_gate_reconciliation_v1.json",
        "2c268aa91f3eef0b1c81ede0f1d7ad51a5aae0bc6370b3cdf7f6d5e1d6524292",
    ),
    "HANDOFF-T21-TASK22-001": (
        "docs/handoffs/task21_to_task22_v1.md",
        "4c3863996cb91ae0600506fe1c8575795e6f6c2a725cfb4fa670fde2caf7bdeb",
    ),
    "REGISTRY-HOLDOUT-CONSUMPTION-001": (
        "registries/holdout_consumption.yaml",
        "863d68e53861c4aa30f6afa1a512ec5ab84c8966273cee6d42ca1519ef5fa07a",
    ),
    "CATALOG-SCHEMA-LIFECYCLE-001": (
        "catalog/schemas/lifecycle_registry.schema.json",
        "eeb60a4364e472f37eca323681bd5c14e98cc49199d9777c025a4f0e94798b80",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task22GroupAwareSplitContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_bytes = CONTRACT_PATH.read_bytes()
        cls.contract = cls.contract_bytes.decode("utf-8")
        cls.spec_bytes = SPEC_PATH.read_bytes()
        cls.spec = yaml.safe_load(cls.spec_bytes)

    def test_candidate_identity_and_entry_patch_are_exact(self) -> None:
        self.assertEqual(sha256(CONTRACT_PATH), EXPECTED_CONTRACT_SHA256)
        self.assertEqual(sha256(SPEC_PATH), EXPECTED_SPEC_SHA256)
        self.assertEqual(
            self.spec["contract_id"],
            "CONTRACT-T22-GROUP-AWARE-SPLIT-001",
        )
        self.assertEqual(
            self.spec["atom_id"],
            "T22-A2_FROZEN_GROUP_AWARE_SPLIT_CONTRACT_V1",
        )
        self.assertEqual(
            self.spec["status"],
            "FROZEN_CONTRACT_OUTCOMES_SEALED",
        )
        gate = self.spec["entry_gate"]
        self.assertEqual(gate["verdict"], "START_WITH_PATCH")
        self.assertEqual(
            gate["source_activation"],
            "ACTIVATION_CONFIRMED_USER_SMOKE",
        )
        self.assertEqual(
            gate["accepted_main_commit"],
            "2ff5a9de4e78a8e64b23754ff59680a33c01d3cc",
        )
        self.assertEqual(
            gate["accepted_main_tree"],
            "3af1179da534972ccf82073dfe1594858c69516e",
        )

    def test_frozen_input_hashes_match_repository_bytes(self) -> None:
        observed = {
            row["asset_id"]: (row["path"], row["sha256"])
            for row in self.spec["frozen_inputs"]
        }
        self.assertEqual(observed, EXPECTED_INPUTS)
        for asset_id, (relative_path, expected_hash) in EXPECTED_INPUTS.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(sha256(ROOT / relative_path), expected_hash)

    def test_exact_effective_sample_and_outcome_seal_are_preserved(self) -> None:
        dataset = self.spec["accepted_dataset"]
        self.assertEqual(dataset["complete_members"], 5)
        self.assertEqual(dataset["complete_member_clusters"], 2)
        self.assertEqual(dataset["incomplete_members"], 3)
        self.assertEqual(dataset["observed_panels"], 22)
        self.assertEqual(dataset["quote_pairs"], 88)
        self.assertEqual(dataset["quote_attempts"], 176)
        self.assertEqual(dataset["explicit_missing_panels"], 3)
        self.assertEqual(
            dataset["source_inventory_sha256"],
            "aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae",
        )
        seal = self.spec["outcome_seal"]
        self.assertEqual(seal["state"], "UNOPENED")
        self.assertFalse(seal["outcome_values_read"])
        self.assertEqual(seal["outcome_paths_opened"], [])
        self.assertTrue(seal["split_before_outcome_required"])
        self.assertFalse(seal["feature_threshold_or_strategy_tuning_allowed"])

    def test_two_clusters_never_force_three_independent_roles(self) -> None:
        patch = self.spec["contract_patch"]
        self.assertEqual(patch["observed_complete_cluster_count"], 2)
        self.assertFalse(patch["three_nonempty_independent_roles_required"])
        self.assertTrue(patch["validation_none_allowed"])
        self.assertTrue(patch["extend_evidence_allowed"])
        self.assertTrue(patch["dataset_not_splittable_allowed"])
        self.assertTrue(patch["force_three_way_split_forbidden"])

        two_group = self.spec["deterministic_candidate_rule"][
            "two_complete_groups"
        ]
        self.assertEqual(two_group["development"], "EARLIEST_COMPLETE_GROUP")
        self.assertEqual(two_group["validation"], "NONE")
        self.assertEqual(two_group["holdout"], "LATEST_COMPLETE_GROUP")
        self.assertTrue(two_group["provisional_assignment_only"])

    def test_grouping_is_batch_first_and_incomplete_evidence_is_retained(self) -> None:
        grouping = self.spec["grouping_contract"]
        self.assertEqual(grouping["primary_group_key"], "nomination_batch_id")
        self.assertEqual(grouping["nested_member_key"], "member_id")
        self.assertFalse(grouping["row_level_random_split_allowed"])
        self.assertFalse(grouping["member_cross_fold_allowed"])
        self.assertFalse(grouping["nomination_batch_cross_fold_allowed"])
        self.assertFalse(grouping["member_iid_assumption_allowed"])
        self.assertEqual(
            [row["batch_id"] for row in grouping["complete_groups"]],
            ["T21-R2", "T21-R3"],
        )
        self.assertEqual(
            [len(row["member_ids"]) for row in grouping["complete_groups"]],
            [3, 2],
        )
        incomplete = grouping["incomplete_groups"]
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0]["batch_id"], "T21-R1")
        self.assertEqual(incomplete[0]["member_count"], 3)
        self.assertFalse(incomplete[0]["eligible_for_outcome_evaluable_fold"])

    def test_chronology_requires_consumer_specific_purge_and_embargo(self) -> None:
        chronology = self.spec["chronology_and_purge_contract"]
        self.assertTrue(chronology["same_day_sequential_batches"])
        self.assertTrue(
            chronology["consumer_horizon_required_before_analysis_eligibility"]
        )
        self.assertEqual(
            set(chronology["required_consumer_fields"]),
            {
                "feature_max_lookback_seconds",
                "label_horizon_seconds",
                "label_first_reliable_available_at_rule",
                "execution_or_settlement_lag_seconds_if_applicable",
            },
        )
        self.assertEqual(
            chronology["project_horizon_bounds_seconds"],
            {"minimum": 900, "maximum": 14400},
        )
        self.assertEqual(
            chronology["unknown_or_infeasible_purge_result"],
            "EXTEND_EVIDENCE",
        )
        self.assertFalse(chronology["assumed_time_gap_grants_independence"])
        self.assertFalse(chronology["overlap_or_same_regime_claim_allowed"])

    def test_feasibility_rules_are_fail_closed_and_validation_none_is_real(self) -> None:
        rules = {
            row["when"]: row for row in self.spec["split_feasibility_rules"]
        }
        ready = rules["EXACT_TWO_COMPLETE_GROUPS_AND_TIME_RULES_PASS"]
        self.assertEqual(ready["verdict"], "SPLIT_READY_WITH_LIMITATIONS")
        self.assertEqual(ready["roles"]["validation"], "NONE")
        self.assertEqual(ready["roles"]["holdout"], "REQUIRED_UNTOUCHED")
        failed_time = rules[
            "EXACT_TWO_COMPLETE_GROUPS_BUT_TIME_RULES_UNKNOWN_OR_FAIL"
        ]
        self.assertEqual(failed_time["verdict"], "EXTEND_EVIDENCE")
        self.assertEqual(failed_time["roles"]["validation"], "NONE")
        self.assertEqual(failed_time["roles"]["holdout"], "UNASSIGNED_UNOPENED")
        self.assertEqual(
            rules["FEWER_THAN_TWO_COMPLETE_GROUPS_OR_IDENTITY_DRIFT"]["verdict"],
            "DATASET_NOT_SPLITTABLE",
        )

    def test_holdout_access_is_append_only_and_cannot_be_reset(self) -> None:
        holdout = self.spec["holdout_access_contract"]
        self.assertEqual(holdout["initial_state"], "UNTOUCHED")
        self.assertEqual(holdout["terminal_state_after_first_access"], "CONSUMED")
        self.assertFalse(holdout["reset_consumed_to_untouched_allowed"])
        self.assertEqual(holdout["event_model"], "APPEND_ONLY")
        self.assertEqual(holdout["access_default"], "DENY")
        self.assertTrue(
            {
                "split_id",
                "dataset_inventory_sha256",
                "holdout_partition_sha256",
                "research_cycle_id",
                "hypothesis_id",
                "hypothesis_version",
                "trial_id",
                "actor_id",
                "opened_at",
                "reason",
                "exact_query_or_code_sha256",
                "decision_receipt_id",
                "prior_state",
                "resulting_state",
            }.issubset(holdout["access_requires"])
        )
        self.assertEqual(
            holdout["existing_registry_fit"],
            "INSUFFICIENT_REQUIRES_ADDITIVE_TASK22_SCHEMA_OR_VALIDATED_COMPANION_RECORD",
        )
        self.assertFalse(holdout["historical_registry_bytes_mutable"])

    def test_claim_reuse_catalog_and_next_boundary_are_bounded(self) -> None:
        forbidden = set(self.spec["claim_boundary"]["forbidden"])
        self.assertTrue(
            {
                "STATISTICAL_POWER_SUFFICIENCY",
                "ALPHA",
                "EXECUTABLE_NET_RETURN",
                "POSITION_OR_PNL",
                "PRODUCTION_READINESS",
            }.issubset(forbidden)
        )
        reuse = self.spec["reuse"]
        self.assertEqual(reuse["fork"], [])
        self.assertEqual(reuse["build"], [])
        self.assertEqual(reuse["new_dependency_count"], 0)
        self.assertTrue(
            reuse["existing_holdout_registry_reused_as_append_only_destination"]
        )
        self.assertFalse(
            reuse["existing_holdout_schema_sufficient_without_additive_extension"]
        )
        catalog = self.spec["catalog"]
        self.assertFalse(catalog["registered_in_atom2"])
        self.assertEqual(catalog["status"], "CATALOG_TRANSACTION_PENDING_T22_A4")
        self.assertFalse(catalog["blocks_contract_freeze"])
        self.assertTrue(catalog["blocks_task22_done"])
        self.assertEqual(
            self.spec["next_atom"]["atom_id"],
            "T22-A3_DETERMINISTIC_SPLIT_AND_HOLDOUT_LEDGER_V1",
        )
        self.assertFalse(
            self.spec["next_atom"]["implementation_authorized_by_atom2"]
        )
        self.assertFalse(self.spec["next_atom"]["outcome_reads_authorized"])

    def test_atom_authority_is_exact_local_write_only(self) -> None:
        authority = self.spec["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(authority["source"], "EXPLICIT_USER")
        self.assertEqual(authority["managed_files"], EXPECTED_MANAGED_FILES)
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "drive_reads",
            "drive_writes",
            "credential_use",
            "outcome_reads",
            "raw_or_dataset_writes",
            "cash_spend_usd_cents",
            "dependency_changes",
            "wallet_signer_transaction_actions",
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

    def test_contract_contains_owner_visible_decision_boundaries(self) -> None:
        for marker in (
            "exam boundary before anyone sees the answers",
            "validation                 -> NONE",
            "`EXTEND_EVIDENCE`",
            "Members are not IID",
            "Batch order alone does not prove temporal independence",
            "The current state is `UNOPENED`",
            "`CONSUMED` never returns to `UNTOUCHED`",
            "Catalog registration is deferred to A4",
            "T22-A3_DETERMINISTIC_SPLIT_AND_HOLDOUT_LEDGER_V1",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)

    def test_authored_files_are_sanitized(self) -> None:
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
