from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task13"
    / "pilot_audit_offline_acceptance_v1.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task13"
    / "pilot_audit_offline_acceptance_receipt_v1.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task13"
    / "pilot_audit_offline_acceptance_summary_v1.md"
)
FIXTURE_SHA256 = (
    "97885ea7b782c68a65ac27744bce6703300acfe76cfe20a7f4141767fdee77c5"
)
RECEIPT_SHA256 = (
    "d932512f861736944cbca3d184528dae0366afbfdb45e185f44ba245c85f752d"
)
SUMMARY_SHA256 = (
    "324a88724befed89222ac45fe51349d29b5f76b6d2ee8cfadec06abe026ebb03"
)
SOURCE_RESULT_SHA256 = (
    "688740fce2f4cd4b8181f2d7724ccca6281d6d0d09db4093a10cd3f7bfde1dc6"
)
EXPECTED_MANAGED_FILES = [
    "tests/fixtures/task13/pilot_audit_offline_acceptance_v1.json",
    "docs/evidence/task13/pilot_audit_offline_acceptance_receipt_v1.json",
    "docs/evidence/task13/pilot_audit_offline_acceptance_summary_v1.md",
    "tests/test_task13_pilot_audit_acceptance.py",
]


class Task13PilotAuditAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.fixture = json.loads(cls.fixture_bytes)
        cls.receipt_bytes = RECEIPT_PATH.read_bytes()
        cls.receipt = json.loads(cls.receipt_bytes)
        cls.summary_bytes = SUMMARY_PATH.read_bytes()
        cls.summary = cls.summary_bytes.decode("utf-8")

    def test_acceptance_artifact_fingerprints_and_identity(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            FIXTURE_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(self.receipt_bytes).hexdigest(),
            RECEIPT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(self.summary_bytes).hexdigest(),
            SUMMARY_SHA256,
        )
        self.assertEqual(self.fixture["task_id"], "TASK-13")
        self.assertEqual(
            self.fixture["atom_id"],
            "T13-A4_DETERMINISTIC_OFFLINE_ACCEPTANCE_V1",
        )
        self.assertEqual(
            self.fixture["accepted_claim"],
            "BOUNDED_HISTORICAL_EVIDENCE_QUALITY_ACCEPTANCE",
        )
        self.assertEqual(self.receipt["status"], "PASS")

    def test_source_fingerprints_match_exact_repository_bytes(self) -> None:
        fingerprints = self.fixture["source_fingerprints"]
        self.assertEqual(len(fingerprints), 6)
        for row in fingerprints:
            path = ROOT / row["path"]
            with self.subTest(asset_id=row["asset_id"]):
                self.assertTrue(path.is_file())
                self.assertFalse(Path(row["path"]).is_absolute())
                self.assertNotIn("..", Path(row["path"]).parts)
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    row["sha256"],
                )

    def test_accepted_totals_and_slice_denominators_reconcile(self) -> None:
        result = self.fixture["accepted_result"]
        self.assertEqual(result["data_files"], 9)
        self.assertEqual(result["input_bytes"], 4_466_708)
        self.assertEqual(result["raw_rows"], 658)
        self.assertEqual(result["identity_complete_rows"], 658)
        self.assertEqual(result["unique_raw_event_ids"], 658)
        self.assertEqual(result["unique_idempotency_keys"], 658)
        self.assertEqual(result["unique_content_sha256"], 657)

        slices = self.fixture["slice_results"]
        self.assertEqual(len(slices), 5)
        self.assertEqual(sum(row["raw_rows"] for row in slices), 658)
        self.assertEqual(
            sum(row["identity_complete_rows"] for row in slices),
            658,
        )
        self.assertEqual(
            sum(row["duplicate_raw_event_id_rows"] for row in slices),
            0,
        )
        self.assertEqual(
            sum(row["duplicate_idempotency_key_rows"] for row in slices),
            0,
        )

    def test_repeated_content_and_typed_failures_remain_distinct(self) -> None:
        result = self.fixture["accepted_result"]
        self.assertEqual(result["repeated_content_rows"], 1)
        self.assertEqual(result["typed_failure_rows"], 4)
        slices = {
            row["slice_id"]: row for row in self.fixture["slice_results"]
        }
        self.assertEqual(slices["T08_ACCEPTED"]["repeated_content_rows"], 1)
        self.assertEqual(slices["T08_ACCEPTED"]["typed_failure_rows"], 2)
        self.assertEqual(slices["T09_ACCEPTED"]["typed_failure_rows"], 1)
        self.assertEqual(
            slices["T10_FAIL_CLOSED_V1"]["typed_failure_rows"],
            1,
        )
        interpretations = {
            failure["interpretation"]
            for row in slices.values()
            for failure in row["typed_failures"]
        }
        self.assertIn(
            "ACCESS_FAILURE_NOT_RELIABILITY_OR_EMPTY_DATA",
            interpretations,
        )
        self.assertIn("PRESERVED_SCHEMA_DRIFT", interpretations)
        self.assertIn(
            "PRESERVED_FAIL_CLOSED_SCHEMA_MISMATCH",
            interpretations,
        )

    def test_pit_and_projection_acceptance_preserve_nonclaims(self) -> None:
        result = self.fixture["accepted_result"]
        self.assertEqual(result["pit_order_violations"], 0)
        self.assertEqual(result["rows_after_global_pit_cutoff"], 0)
        projections = self.fixture["projection_results"]
        self.assertEqual(len(projections), 2)
        self.assertEqual(
            sum(row["raw_api_events"] for row in projections),
            9,
        )
        self.assertEqual(
            sum(row["quote_attempts"] for row in projections),
            9,
        )
        self.assertEqual(
            sum(row["execution_attempts"] for row in projections),
            0,
        )
        self.assertTrue(
            all(row["raw_event_lineage_exact"] for row in projections)
        )
        self.assertTrue(
            all(row["quote_event_lineage_exact"] for row in projections)
        )
        self.assertFalse(any(row["quote_is_fill"] for row in projections))

    def test_decision_boundary_is_bounded_for_task14(self) -> None:
        boundary = self.fixture["decision_boundary"]
        self.assertEqual(
            boundary["task14_implication"],
            "PROVIDER_PURCHASE_REQUIREMENT_NOT_ESTABLISHED",
        )
        self.assertEqual(
            boundary["required_before_rate_or_coverage_claim"],
            "SUSTAINED_MEASUREMENT_UNDER_SEPARATE_AUTHORITY",
        )
        self.assertIn(
            "BOUNDED_RAW_EVIDENCE_INTEGRITY",
            boundary["valid_for"],
        )
        self.assertIn(
            "PROVIDER_PURCHASE_REQUIREMENT",
            boundary["not_valid_for"],
        )
        self.assertTrue(self.fixture["nonclaims"])
        self.assertFalse(any(self.fixture["nonclaims"].values()))
        accepted = self.fixture["accepted_result"]
        self.assertFalse(
            accepted["provider_purchase_requirement_established"]
        )
        self.assertFalse(accepted["sustained_reliability_rate_established"])
        self.assertFalse(accepted["sustained_coverage_established"])

    def test_receipt_binds_fixture_implementation_and_source_result(self) -> None:
        self.assertEqual(self.receipt["fixture"]["sha256"], FIXTURE_SHA256)
        source = self.fixture["source_result"]
        accepted = self.receipt["accepted_result"]
        self.assertEqual(source["result_sha256"], SOURCE_RESULT_SHA256)
        self.assertEqual(
            accepted["source_result_sha256"],
            SOURCE_RESULT_SHA256,
        )
        self.assertEqual(
            accepted["input_manifest_sha256"],
            source["input_manifest_sha256"],
        )
        self.assertEqual(
            accepted["accepted_claim"],
            self.fixture["accepted_claim"],
        )
        checks = self.receipt["checks"]
        self.assertEqual(
            checks["frozen_population_data_file_readback"],
            "PASS_9_OF_9",
        )
        self.assertEqual(
            checks["decision_boundary"],
            "PASS_BOUNDED_NOT_SUSTAINED",
        )

    def test_authority_and_catalog_deferral_are_exact(self) -> None:
        authority = self.fixture["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(authority["source"], "EXPLICIT_USER")
        self.assertEqual(authority["managed_files"], EXPECTED_MANAGED_FILES)
        zero_fields = (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "credential_use",
            "collector_executions",
            "raw_data_writes",
            "cash_spend_usd_cents",
            "provider_credits",
            "dependency_changes",
            "wallet_signer_transaction_actions",
        )
        self.assertTrue(all(authority[field] == 0 for field in zero_fields))
        for field in (
            "commit",
            "push",
            "pull_request",
            "merge",
            "ui_changes",
            "destructive_actions",
        ):
            self.assertFalse(authority[field])
        catalog = self.fixture["catalog"]
        self.assertFalse(catalog["changed_in_atom4"])
        self.assertTrue(catalog["blocks_task13_done"])
        self.assertFalse(catalog["blocks_atom4_acceptance"])
        self.assertEqual(
            self.fixture["next_atom"]["atom_id"],
            "T13-A5_CATALOG_REPOSITORY_FINALIZATION_V1",
        )

    def test_summary_is_sanitized_and_binds_acceptance_evidence(self) -> None:
        for marker in (
            FIXTURE_SHA256,
            RECEIPT_SHA256,
            SOURCE_RESULT_SHA256,
            "BOUNDED_HISTORICAL_EVIDENCE_QUALITY_ACCEPTANCE",
            "PROVIDER_PURCHASE_REQUIREMENT_NOT_ESTABLISHED",
            "31/31 PASS",
            "TASK-13 remains `IN_PROGRESS`",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.summary)
        texts = {
            "fixture": self.fixture_bytes.decode("utf-8"),
            "receipt": self.receipt_bytes.decode("utf-8"),
            "summary": self.summary,
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
            "raw_provider_body": re.compile(r'"redacted_body"\s*:'),
        }
        for label, text in texts.items():
            for pattern_name, pattern in prohibited.items():
                with self.subTest(file=label, pattern=pattern_name):
                    self.assertIsNone(pattern.search(text))

    def test_atom5_catalog_registration_is_exact(self) -> None:
        manifest = yaml.safe_load(
            (ROOT / "catalog" / "catalog_manifest.yaml").read_text(
                encoding="utf-8"
            )
        )
        asset_documents = [
            yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
            for relative in manifest["root_resolver"]["asset_registries"]
        ]
        records = {
            record["asset_id"]: record
            for document in asset_documents
            for record in document["records"]
        }
        expected = {
            "CONTRACT-T13-PILOT-AUDIT-001",
            "FIXTURE-T13-PILOT-AUDIT-POPULATION-001",
            "TEST-T13-PILOT-AUDIT-CONTRACT-001",
            "MODULE-T13-PILOT-AUDIT-001",
            "SCRIPT-T13-PILOT-AUDIT-001",
            "TEST-T13-PILOT-AUDIT-001",
            "FIXTURE-T13-PILOT-AUDIT-OFFLINE-ACCEPTANCE-001",
            "EVIDENCE-T13-PILOT-AUDIT-OFFLINE-ACCEPTANCE-001",
            "EVIDENCE-T13-PILOT-AUDIT-OFFLINE-SUMMARY-001",
            "TEST-T13-PILOT-AUDIT-ACCEPTANCE-001",
        }
        self.assertEqual(manifest["catalog_version"], "0.17.0")
        self.assertEqual(len(records), 266)
        self.assertTrue(expected.issubset(records))
        self.assertTrue(
            expected.issubset(set(manifest["mandatory_asset_ids"]))
        )
        population = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "task13"
                / "pilot_audit_population_v1.json"
            ).read_text(encoding="utf-8")
        )
        source_ids = {
            asset_id
            for slice_row in population["slices"]
            for asset_id in slice_row["asset_ids"]
        }
        for asset_id in source_ids:
            with self.subTest(source_asset_id=asset_id):
                self.assertIn("TASK-13", records[asset_id]["consumers"])
        self.assertEqual(
            self.receipt["catalog"]["status"],
            "REGISTERED_IN_TASK13_CATALOG_TRANSACTION",
        )
        self.assertTrue(self.receipt["catalog"]["changed_in_atom5"])


if __name__ == "__main__":
    unittest.main()
