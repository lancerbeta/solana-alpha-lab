from __future__ import annotations

import hashlib
import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "task18_narrow_data_quality_contract_v1.md"
)
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task18"
    / "narrow_data_quality_contract_v1.json"
)
AUDIT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17a"
    / "execution_capacity_quote_panel_audit_v1.json"
)
SOURCE_CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "bounded_execution_capacity_quote_panel_contract_v1.json"
)
EXPECTED_FIXTURE_SHA256 = (
    "1842df2ef349d9506ff612c3faf3c943a1a218f6c6a7e266c5af5f0f5578b3a6"
)
EXPECTED_MANAGED_FILES = [
    "docs/contracts/task18_narrow_data_quality_contract_v1.md",
    "tests/fixtures/task18/narrow_data_quality_contract_v1.json",
    "tests/test_task18_narrow_data_quality_contract.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task18NarrowDataQualityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.fixture = json.loads(cls.fixture_bytes)
        cls.audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        cls.source_contract = json.loads(
            SOURCE_CONTRACT_PATH.read_text(encoding="utf-8")
        )
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")

    def test_fixture_identity_and_fingerprint_are_frozen(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            self.fixture["contract_id"],
            "CONTRACT-T18-NARROW-DATA-QUALITY-001",
        )
        self.assertEqual(self.fixture["task_id"], "TASK-18")
        self.assertEqual(
            self.fixture["atom_id"],
            "T18-A2_FROZEN_NARROW_QUALITY_CONTRACT_V1",
        )
        self.assertEqual(self.fixture["status"], "FROZEN_OFFLINE_CONTRACT")

    def test_entry_gate_binds_exact_accepted_base_and_catalog(self) -> None:
        gate = self.fixture["entry_gate"]
        self.assertEqual(gate["verdict"], "START_AS_WRITTEN")
        self.assertEqual(
            gate["source_activation"],
            "ACTIVATION_CONFIRMED_USER_SMOKE",
        )
        self.assertEqual(
            gate["accepted_base_commit"],
            "67fdb73127cd837174e9e20a057c413928c3628a",
        )
        self.assertEqual(
            gate["accepted_base_tree"],
            "d74d3fa8e32192a492576938332832228fa5d7ce",
        )
        self.assertEqual(
            (
                gate["catalog_version"],
                gate["catalog_assets"],
                gate["catalog_shards"],
                gate["catalog_schemas"],
                gate["catalog_queries"],
            ),
            ("0.22.0", 303, 4, 4, 8),
        )
        self.assertTrue(gate["raw_availability_observed"])
        self.assertEqual(
            gate["raw_availability_scope"],
            "CURRENT_LOCAL_WORKSPACE_ONLY",
        )

    def test_tracked_inputs_match_repository_bytes(self) -> None:
        expected = {
            "docs/evidence/task17a/execution_capacity_quote_panel_audit_v1.json": (
                AUDIT_PATH
            ),
            (
                "tests/fixtures/task17a/"
                "bounded_execution_capacity_quote_panel_contract_v1.json"
            ): SOURCE_CONTRACT_PATH,
        }
        for row in self.fixture["tracked_inputs"]:
            with self.subTest(asset_id=row["asset_id"]):
                path = expected[row["path"]]
                self.assertEqual(row["sha256"], sha256(path))

        self.assertEqual(
            self.audit["contract_sha256"],
            sha256(SOURCE_CONTRACT_PATH),
        )

    def test_estimand_and_excluded_window_remain_exact(self) -> None:
        estimand = self.fixture["estimand"]
        self.assertEqual(
            estimand["hypothesis_version_id"],
            self.audit["hypothesis_version_id"],
        )
        self.assertEqual(
            estimand["accepted_windows"],
            [
                "T17A-WINDOW-01",
                "T17A-WINDOW-03",
                "T17A-WINDOW-04-REPAIR-01",
            ],
        )
        self.assertEqual(
            estimand["excluded_retained_windows"],
            ["T17A-WINDOW-02"],
        )
        self.assertEqual(estimand["accepted_provider_calls"], 24)
        self.assertEqual(estimand["excluded_retained_provider_calls"], 8)
        self.assertEqual(estimand["total_provider_calls"], 32)
        self.assertEqual(estimand["complete_quote_pairs"], 12)
        self.assertFalse(estimand["cross_token_generalization"])
        self.assertFalse(estimand["quote_as_fill"])

        temporal = self.fixture["quality_dimensions"][
            "temporal_membership"
        ]
        self.assertEqual(temporal["excluded_window_id"], "T17A-WINDOW-02")
        self.assertEqual(
            temporal["excluded_trigger_shortfall_seconds"],
            0.007854,
        )
        self.assertFalse(temporal["post_hoc_tolerance_allowed"])
        self.assertFalse(temporal["excluded_window_reclassification_allowed"])

    def test_raw_inventory_is_exact_relative_and_content_addressed(self) -> None:
        inventory = self.fixture["raw_inventory"]
        files = inventory["files"]
        self.assertFalse(inventory["raw_bytes_in_git"])
        self.assertEqual(inventory["window_count"], 4)
        self.assertEqual(inventory["file_count"], 12)
        self.assertEqual(inventory["jsonl_attempt_rows"], 32)
        self.assertEqual(inventory["stored_bytes"], 179_208)
        self.assertEqual(len(files), 12)
        self.assertEqual(sum(row["bytes"] for row in files), 179_208)
        self.assertEqual(
            sum(
                row["rows"]
                for row in files
                if row["kind"] == "RAW_EVENTS_JSONL"
            ),
            32,
        )

        per_window = Counter(row["window_id"] for row in files)
        self.assertEqual(set(per_window.values()), {3})
        for row in files:
            with self.subTest(path=row["path"]):
                path = Path(row["path"])
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
                self.assertGreater(row["bytes"], 0)
                self.assertGreater(row["rows"], 0)

    def test_quality_dimensions_freeze_hard_fail_closed_semantics(self) -> None:
        dimensions = self.fixture["quality_dimensions"]
        required = {
            "inventory_integrity",
            "attempt_completeness",
            "stable_identity",
            "point_in_time",
            "temporal_membership",
            "provider_and_schema",
            "bytes_and_caps",
            "revision_and_overwrite",
            "retention_and_restore",
        }
        self.assertEqual(set(dimensions), required)
        for name in required - {"retention_and_restore"}:
            with self.subTest(dimension=name):
                self.assertTrue(dimensions[name]["hard_gate"])

        identity = dimensions["stable_identity"]
        self.assertEqual(
            identity["composite_key"],
            [
                "hypothesis_version_id",
                "watchlist_id",
                "watchlist_version",
                "window_id",
                "member_id",
                "call_ordinal",
                "request_hash",
                "idempotency_key",
            ],
        )
        self.assertFalse(identity["duplicate_equal_bytes_allowed"])
        self.assertFalse(identity["duplicate_changed_bytes_allowed"])

        pit = dimensions["point_in_time"]
        self.assertEqual(
            pit["ordered_fields"],
            [
                "requested_at",
                "response_at",
                "first_reliable_available_at",
                "available_to_strategy_at",
                "ingested_at",
            ],
        )
        self.assertTrue(pit["backfill_availability_forbidden"])
        self.assertFalse(pit["negative_lag_allowed"])
        self.assertEqual(pit["latency_tolerance_ms"], 1.0)

    def test_revision_retention_and_restore_cannot_overclaim(self) -> None:
        revision = self.fixture["quality_dimensions"][
            "revision_and_overwrite"
        ]
        retention = self.fixture["quality_dimensions"][
            "retention_and_restore"
        ]
        self.assertEqual(revision["expected_revision_number"], 1)
        self.assertIsNone(revision["expected_revision_of"])
        self.assertEqual(
            revision["changed_content_under_same_identity"],
            "NOT_FIT",
        )
        self.assertFalse(
            revision["overwrite_prevention_claim_from_current_hash_only"]
        )
        self.assertTrue(retention["current_local_availability_observed"])
        self.assertFalse(retention["backup_inventory_observed"])
        self.assertFalse(retention["restore_test_observed"])
        self.assertEqual(
            retention["missing_backup_or_restore_outcome"],
            "FIT_WITH_LIMITATIONS_IF_ALL_HARD_REPLAY_INVARIANTS_PASS",
        )
        self.assertFalse(retention["file_mutation_allowed"])

    def test_verdict_precedence_is_exhaustive_and_outcome_independent(
        self,
    ) -> None:
        verdicts = self.fixture["verdicts"]
        self.assertEqual(
            verdicts["precedence"],
            [
                "EVIDENCE_UNAVAILABLE",
                "NOT_FIT",
                "FIT_WITH_LIMITATIONS",
                "FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND",
            ],
        )
        self.assertFalse(verdicts["hypothesis_result_may_select_verdict"])
        self.assertFalse(verdicts["majority_vote_allowed"])
        for verdict in verdicts["precedence"]:
            self.assertIn(verdict, verdicts)

    def test_reuse_is_thin_and_catalog_is_deferred(self) -> None:
        reuse = self.fixture["reuse"]
        self.assertIn("TASK13_DETERMINISTIC_AUDIT_PATTERN", reuse["adopt"])
        self.assertIn(
            "EVIDENCE-T17A-EXECUTION-CAPACITY-AUDIT-001",
            reuse["wrap"],
        )
        self.assertEqual(reuse["fork"], [])
        self.assertEqual(reuse["new_dependency_count"], 0)
        self.assertFalse(reuse["general_data_quality_framework"])

        catalog = self.fixture["catalog"]
        self.assertFalse(catalog["registered_in_atom2"])
        self.assertEqual(
            catalog["status"],
            "CATALOG_TRANSACTION_PENDING_T18_A4",
        )
        self.assertFalse(catalog["blocks_contract_freeze"])
        self.assertTrue(catalog["blocks_task18_done"])

    def test_a2_authority_is_local_write_only_and_zero_effect(self) -> None:
        authority = self.fixture["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(authority["source"], "EXPLICIT_USER")
        self.assertEqual(authority["managed_files"], EXPECTED_MANAGED_FILES)
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "credential_use",
            "collector_executions",
            "raw_data_writes",
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

        next_atom = self.fixture["next_atom"]
        self.assertEqual(
            next_atom["atom_id"],
            "T18-A3_DETERMINISTIC_OFFLINE_QUALITY_AUDIT_V1",
        )
        self.assertFalse(next_atom["implementation_authorized"])
        self.assertFalse(next_atom["external_calls_authorized"])
        self.assertFalse(next_atom["raw_mutation_authorized"])

    def test_contract_contains_decision_changing_boundaries(self) -> None:
        for marker in (
            "EVIDENCE_UNAVAILABLE",
            "NOT_FIT",
            "FIT_WITH_LIMITATIONS",
            "FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND",
            "0.007854 seconds",
            "179,208 stored bytes",
            "Missing is never zero",
            "Current local availability proves neither durable backup",
            "general data-quality framework",
            "T18-A3_DETERMINISTIC_OFFLINE_QUALITY_AUDIT_V1",
            "authorizes no provider/API/RPC/WSS call",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)

    def test_tracked_contract_artifacts_are_sanitized(self) -> None:
        texts = {
            "contract": self.contract,
            "fixture": self.fixture_bytes.decode("utf-8"),
            "test": Path(__file__).read_text(encoding="utf-8"),
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
        for label, text in texts.items():
            for pattern_name, pattern in prohibited.items():
                with self.subTest(file=label, pattern=pattern_name):
                    self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
