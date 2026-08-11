from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "task20_coverage_retention_recovery_policy_v1.md"
)
MATRIX_PATH = (
    ROOT / "docs" / "architecture" / "hypothesis_data_coverage_matrix_v1.md"
)
POLICY_PATH = ROOT / "configs" / "task20_retention_recovery_policy_v1.yaml"
A2_CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "task20_collection_spec_contract_v1.md"
)
A2_SPEC_PATH = ROOT / "configs" / "collection_spec_v1.yaml"
A2_TEST_PATH = ROOT / "tests" / "test_task20_collection_spec_contract.py"

EXPECTED_CONTRACT_SHA256 = (
    "d10fe7bfb24c9e2ce1ccf1e219229b0d9f4e251c93ec2bc3c8101a4953409fe7"
)
EXPECTED_MATRIX_SHA256 = (
    "4c50a77333b1cdde42af8da09b1a27e34d3937cc9b8101351dc65884d08f8024"
)
EXPECTED_POLICY_SHA256 = (
    "3810a5674f2479e460c7b3883a58c0cf5d22f7902c0cfc8606aaeb990f95914f"
)
EXPECTED_A2_HASHES = {
    A2_CONTRACT_PATH: (
        "33a7317ade7ab0239c7ba7e84bbde02cf1f9d9a5199c713140388ab10b1b2d79"
    ),
    A2_SPEC_PATH: (
        "c8c734eb76a5c13e7c49d0954e10e777d2f2a1cfe858ed688146a7c84269199d"
    ),
    A2_TEST_PATH: (
        "21279e1aadbda01ee2a68c33799d4870ac8b6d144bada8ad4c04d84d18e91adb"
    ),
}
EXPECTED_MANAGED_FILES = [
    "docs/contracts/task20_coverage_retention_recovery_policy_v1.md",
    "docs/architecture/hypothesis_data_coverage_matrix_v1.md",
    "configs/task20_retention_recovery_policy_v1.yaml",
    "tests/test_task20_coverage_retention_recovery_policy.py",
]
REQUIRED_FIELD_METADATA = {
    "field_id",
    "description",
    "units",
    "natural_keys",
    "tier",
    "named_consumers",
    "source_asset_id",
    "source_version",
    "purpose_and_decision_impact",
    "event_time_semantics",
    "observed_time_semantics",
    "ingested_time_semantics",
    "first_reliable_available_at_semantics",
    "availability_class",
    "cadence_mode",
    "exact_cadence_if_scheduled",
    "retention_class",
    "revision_policy",
    "quality_checks",
    "freshness_rule",
    "missingness_policy",
    "request_credit_byte_storage_time_attribution",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deterministic_restore_indexes(
    partition_count: int,
    manifest_sha256: str,
) -> list[int]:
    if partition_count < 1:
        return []
    if partition_count < 3:
        return list(range(partition_count))
    indexes = {
        0,
        partition_count - 1,
        int(manifest_sha256, 16) % partition_count,
    }
    return sorted(indexes)


class Task20CoverageRetentionRecoveryPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_bytes = CONTRACT_PATH.read_bytes()
        cls.contract = cls.contract_bytes.decode("utf-8")
        cls.matrix_bytes = MATRIX_PATH.read_bytes()
        cls.matrix_text = cls.matrix_bytes.decode("utf-8")
        cls.policy_bytes = POLICY_PATH.read_bytes()
        cls.policy = yaml.safe_load(cls.policy_bytes)
        cls.fields = cls.policy["coverage_matrix"]

    def test_policy_identity_and_authored_hashes_are_exact(self) -> None:
        self.assertEqual(sha256(CONTRACT_PATH), EXPECTED_CONTRACT_SHA256)
        self.assertEqual(sha256(MATRIX_PATH), EXPECTED_MATRIX_SHA256)
        self.assertEqual(sha256(POLICY_PATH), EXPECTED_POLICY_SHA256)
        self.assertEqual(
            self.policy["schema"],
            "smial.coverage_retention_recovery_policy",
        )
        self.assertEqual(self.policy["policy_id"], "RETENTION-RECOVERY-T20-001")
        self.assertEqual(self.policy["policy_version"], "1.0")
        self.assertEqual(
            self.policy["atom_id"],
            "T20-A3_COVERAGE_RETENTION_AND_RECOVERY_POLICY_V1",
        )
        self.assertEqual(self.policy["status"], "FROZEN_POLICY_NO_COLLECTION")

    def test_a2_inputs_remain_byte_exact_and_bound(self) -> None:
        for path, expected_hash in EXPECTED_A2_HASHES.items():
            if path == A2_TEST_PATH:
                continue
            with self.subTest(path=path.name):
                self.assertEqual(sha256(path), expected_hash)
        frozen = self.policy["frozen_collection_spec"]
        self.assertEqual(frozen["spec_id"], "COLLECTION-SPEC-T20-001")
        self.assertEqual(frozen["spec_version"], "1.0")
        self.assertEqual(
            frozen["contract_sha256"],
            EXPECTED_A2_HASHES[A2_CONTRACT_PATH],
        )
        self.assertEqual(
            frozen["config_sha256"],
            EXPECTED_A2_HASHES[A2_SPEC_PATH],
        )
        self.assertEqual(
            frozen["test_sha256"],
            EXPECTED_A2_HASHES[A2_TEST_PATH],
        )

    def test_matrix_has_exactly_40_unique_fully_typed_fields(self) -> None:
        self.assertEqual(len(self.fields), 40)
        ids = [field["field_id"] for field in self.fields]
        self.assertEqual(len(ids), len(set(ids)))
        for field in self.fields:
            with self.subTest(field=field["field_id"]):
                self.assertTrue(
                    REQUIRED_FIELD_METADATA.issubset(field),
                    REQUIRED_FIELD_METADATA - set(field),
                )
                self.assertTrue(field["named_consumers"])
                self.assertTrue(field["natural_keys"])
                self.assertTrue(field["quality_checks"])
                self.assertNotEqual(
                    field["purpose_and_decision_impact"],
                    "UNSPECIFIED",
                )
                self.assertNotEqual(
                    field["request_credit_byte_storage_time_attribution"],
                    "UNSPECIFIED",
                )

    def test_tiers_are_exact_and_do_not_authorize_market_wide_capture(
        self,
    ) -> None:
        counts = {
            tier: sum(field["tier"] == tier for field in self.fields)
            for tier in ("T0", "T1", "T2")
        }
        self.assertEqual(counts, {"T0": 17, "T1": 11, "T2": 12})
        scope = self.policy["scope"]
        self.assertTrue(scope["matrix_is_exhaustive_for_spec_version"])
        self.assertTrue(scope["future_field_requires_new_collection_spec_version"])
        self.assertFalse(scope["global_solana_universe_authorized"])
        self.assertFalse(scope["market_wide_tick_capture_authorized"])
        self.assertFalse(scope["collector_or_scheduler_authorized"])

    def test_t0_is_only_the_thin_decision_ledger(self) -> None:
        t0 = {field["field_id"]: field for field in self.fields if field["tier"] == "T0"}
        self.assertEqual(
            set(t0),
            {
                "evaluated_at",
                "hypothesis_id",
                "hypothesis_version",
                "trial_id_or_activation_epoch",
                "policy_version",
                "mint",
                "pool_identity_if_applicable",
                "exact_rule_input_values",
                "input_feature_and_source_versions",
                "evaluation_result",
                "reason_codes",
                "missingness_codes",
                "coverage_gap_codes",
                "membership_transition",
                "first_reliable_available_at",
                "evidence_checkpoint",
                "quote_or_liquidity_snapshot_sha256",
            },
        )
        self.assertEqual(
            t0["quote_or_liquidity_snapshot_sha256"]["missingness_policy"],
            "ABSENT_UNLESS_SNAPSHOT_WAS_A_RULE_INPUT",
        )
        for field in t0.values():
            self.assertEqual(field["cadence_mode"], "EVENT_DRIVEN")
            self.assertEqual(field["retention_class"], "DECISION_LINEAGE")

    def test_t1_is_historical_on_demand_with_pt1m_only_as_candidate(
        self,
    ) -> None:
        t1 = [field for field in self.fields if field["tier"] == "T1"]
        bar_fields = [field for field in t1 if field["field_id"].startswith("bar_")]
        lifecycle_fields = [
            field for field in t1 if field["field_id"].startswith("lifecycle_")
        ]
        self.assertEqual(len(bar_fields), 8)
        self.assertEqual(len(lifecycle_fields), 3)
        for field in t1:
            with self.subTest(field=field["field_id"]):
                self.assertEqual(field["cadence_mode"], "HISTORICAL_BATCH_ON_DEMAND")
                self.assertIn("REG-RESEARCH-001", field["named_consumers"])
        for field in bar_fields:
            self.assertEqual(
                field["exact_cadence_if_scheduled"],
                "PT1M_CANDIDATE_ONLY_FOR_NAMED_INTRADAY_BAR_CONSUMER",
            )
            self.assertEqual(
                field["retention_class"],
                "RECONSTRUCTIBLE_CONTENT_CACHE",
            )

    def test_t2_is_named_forward_only_and_separately_authorized(self) -> None:
        t2 = [field for field in self.fields if field["tier"] == "T2"]
        self.assertEqual(len(t2), 12)
        for field in t2:
            with self.subTest(field=field["field_id"]):
                self.assertEqual(field["availability_class"], "FORWARD_ONLY")
                self.assertEqual(field["cadence_mode"], "TRIGGERED_LIVE_ONLY")
                self.assertEqual(field["retention_class"], "UNIQUE_RAW_EVIDENCE")
                self.assertIn(
                    "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1",
                    field["named_consumers"],
                )
                self.assertEqual(
                    field["source_asset_id"],
                    "SEPARATELY_AUTHORIZED_LIVE_QUOTE_SOURCE",
                )

    def test_retention_has_no_automatic_expiry_or_implicit_deletion(
        self,
    ) -> None:
        classes = self.policy["retention_classes"]
        for name, policy in classes.items():
            with self.subTest(retention_class=name):
                self.assertFalse(policy["automatic_expiry"])
        unique = classes["UNIQUE_RAW_EVIDENCE"]
        self.assertFalse(unique["eviction_allowed"])
        self.assertIn(
            "SEPARATE_OWNER_DELETION_DECISION",
            unique["deletion_requires"],
        )
        cache = classes["RECONSTRUCTIBLE_CONTENT_CACHE"]
        self.assertTrue(cache["eviction_allowed"])
        self.assertEqual(len(cache["eviction_requires"]), 5)
        self.assertIn(
            "SEPARATE_DESTRUCTIVE_AUTHORITY",
            cache["eviction_requires"],
        )

    def test_storage_and_remote_backup_are_no_clobber(self) -> None:
        storage = self.policy["immutable_storage"]
        self.assertEqual(
            storage["canonical_write_behavior"],
            "CREATE_ONLY_CONTENT_ADDRESSED",
        )
        self.assertEqual(
            storage["same_semantic_identity_different_bytes"],
            "FAIL_CLOSED_EVIDENCE_CONFLICT",
        )
        self.assertFalse(storage["accepted_bytes_overwrite_allowed"])
        self.assertFalse(storage["mutable_alias_selects_evidence"])
        self.assertFalse(storage["source_bytes_deleted_after_backup"])
        backup = self.policy["backup"]
        self.assertEqual(
            backup["remote_write_behavior"],
            "CREATE_ONLY_CONTENT_HASH_NAMED",
        )
        self.assertEqual(
            backup["existing_same_hash_behavior"],
            "DEDUPLICATE_ONLY_AFTER_EXACT_REMOTE_READBACK",
        )

    def test_backup_cadence_and_overdue_behavior_are_bounded(self) -> None:
        backup = self.policy["backup"]
        self.assertEqual(
            backup["trigger"],
            "EACH_CLOSED_IMMUTABLE_PARTITION_OR_24_HOURS_WHICHEVER_COMES_FIRST",
        )
        self.assertEqual(backup["maximum_age_hours"], 24)
        self.assertEqual(backup["grace_hours"], 2)
        self.assertEqual(backup["overdue_after_hours"], 26)
        self.assertEqual(
            backup["disable_new_t2_admissions_after_overdue_hours"],
            48,
        )
        self.assertEqual(
            set(backup["required_every_backup"]),
            {
                "EXACT_RAW_BYTE_READBACK",
                "SHA256_MATCH",
                "TYPED_MANIFEST_MATCH",
                "DESTINATION_IDENTITY_RECEIPT",
                "BACKUP_TIMESTAMP",
            },
        )
        degraded = self.policy["degraded_behavior"]
        self.assertIn(
            "NEW_T2_ADMISSIONS",
            degraded["BACKUP_OVERDUE_48H"]["disable"],
        )
        self.assertEqual(
            degraded["BACKUP_OVERDUE_48H"]["existing_active_capture"],
            "MAY_CONTINUE_ONLY_IF_PRIMARY_STORAGE_AND_INTEGRITY_ARE_HEALTHY",
        )

    def test_restore_sample_is_deterministic_but_not_full_proof(self) -> None:
        restore = self.policy["restore_proof"]
        sample = restore["routine_sample"]
        self.assertEqual(sample["cadence"], "P7D")
        self.assertEqual(sample["environment"], "ISOLATED_EMPTY_RESTORE_ROOT")
        self.assertEqual(sample["proves"], "SAMPLED_OBJECT_PERSISTENCE_ONLY")
        self.assertEqual(
            sample["does_not_prove"],
            "FULL_DATASET_RECOVERABILITY",
        )
        manifest_hash = hashlib.sha256(b"fixed-manifest").hexdigest()
        self.assertEqual(deterministic_restore_indexes(0, manifest_hash), [])
        self.assertEqual(deterministic_restore_indexes(1, manifest_hash), [0])
        self.assertEqual(deterministic_restore_indexes(2, manifest_hash), [0, 1])
        expected = sorted({0, 4, int(manifest_hash, 16) % 5})
        self.assertEqual(
            deterministic_restore_indexes(5, manifest_hash),
            expected,
        )

    def test_full_restore_is_required_for_freeze_and_promotion(self) -> None:
        full = self.policy["restore_proof"]["full_restore"]
        self.assertEqual(
            set(full["required_before"]),
            {"DATASET_FREEZE", "DATASET_PROMOTION"},
        )
        self.assertEqual(
            set(full["required_after"]),
            {
                "BACKUP_OR_RESTORE_INCIDENT",
                "BACKUP_POLICY_CHANGE",
                "BACKUP_RUNTIME_CHANGE",
            },
        )
        self.assertEqual(full["success_state"], "DATASET_RECOVERY_PROVEN")
        self.assertEqual(len(full["success_requires"]), 4)

    def test_health_states_and_owner_pulse_make_failure_visible(self) -> None:
        degraded = self.policy["degraded_behavior"]
        self.assertEqual(
            set(degraded["health_states"]),
            {
                "HEALTHY",
                "BACKUP_OVERDUE",
                "RESTORE_OVERDUE",
                "EVIDENCE_AT_RISK",
                "EVIDENCE_CONFLICT",
                "STORAGE_HARD_STOP",
            },
        )
        self.assertIn(
            "STOP_WRITES_TO_AFFECTED_DATASET",
            degraded["EVIDENCE_CONFLICT"]["action"],
        )
        self.assertIn(
            "STOP_NEW_CAPTURE",
            degraded["STORAGE_HARD_STOP"]["action"],
        )
        metrics = set(self.policy["owner_pulse"]["required_metrics"])
        self.assertTrue(
            {
                "backup_age_hours",
                "restore_proof_age_hours",
                "local_dataset_bytes",
                "free_disk_bytes",
                "provider_credits_used_and_cap",
                "coverage_by_required_field",
                "missingness_by_required_field",
                "freshness_by_required_field",
                "evidence_conflict_state",
            }.issubset(metrics)
        )

    def test_human_matrix_mentions_each_authoritative_field_once(self) -> None:
        for field in self.fields:
            marker = f"`{field['field_id']}`"
            with self.subTest(field=field["field_id"]):
                self.assertEqual(self.matrix_text.count(marker), 1)
        self.assertIn("Event time is not strategy availability", self.matrix_text)
        self.assertIn("requires a new version", self.matrix_text)

    def test_provider_is_neutral_and_policy_makes_no_execution_claim(self) -> None:
        destination = self.policy["backup"]["destination"]
        self.assertEqual(
            destination["topology"],
            "PRIVATE_SEPARATE_FAILURE_DOMAIN",
        )
        self.assertTrue(destination["provider_neutral"])
        self.assertTrue(destination["google_drive_is_candidate_not_required_provider"])
        self.assertFalse(destination["credentials_in_manifest_allowed"])
        self.assertEqual(
            set(self.policy["policy_non_claims"]),
            {
                "NO_BACKUP_EXECUTED",
                "NO_RESTORE_EXECUTED",
                "NO_COLLECTOR_OR_SCHEDULER_BUILT",
                "NO_FORWARD_COLLECTION_AUTHORIZED",
                "NO_PROVIDER_SELECTED",
                "NO_STORAGE_PURCHASE_JUSTIFIED",
                "NO_DATASET_RECOVERY_PROVEN_BY_POLICY_TEXT",
            },
        )

    def test_atom_authority_is_exact_local_write_only_and_zero_effect(
        self,
    ) -> None:
        authority = self.policy["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(
            authority["source"],
            "EXPLICIT_USER_APPROVAL_T20_A3",
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
            "backup_executions",
            "restore_executions",
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
            "wallet_actions",
            "signer_actions",
            "transaction_actions",
            "ui_changes",
            "destructive_actions",
        ):
            with self.subTest(field=field):
                self.assertFalse(authority[field])
        self.assertEqual(
            self.policy["next_atom"]["atom_id"],
            "T20-A4_DETERMINISTIC_ACCEPTANCE_CATALOG_AND_FACTORY_FIT_V1",
        )
        self.assertFalse(
            self.policy["next_atom"]["forward_collection_authorized"]
        )

    def test_contract_contains_decision_changing_boundaries(self) -> None:
        normalized = " ".join(self.contract.split())
        for marker in (
            "exactly 40 fields",
            "`PT1M` remains a candidate cadence",
            "A3 itself authorizes no deletion",
            "`EVIDENCE_CONFLICT`",
            "within 24 hours at the latest",
            "At 26 hours",
            "overdue condition lasts 48 hours",
            "sampled-object persistence only",
            "`DATASET_RECOVERY_PROVEN`",
            "Google Drive remains one possible",
            "T20-A4_DETERMINISTIC_ACCEPTANCE_CATALOG_AND_FACTORY_FIT_V1",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, normalized)

    def test_authored_files_are_sanitized_and_have_text_hygiene(self) -> None:
        candidates = {
            "contract": self.contract_bytes,
            "matrix": self.matrix_bytes,
            "policy": self.policy_bytes,
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
