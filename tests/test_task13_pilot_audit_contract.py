from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task13"
    / "pilot_audit_population_v1.json"
)
CONTRACT_PATH = ROOT / "docs" / "contracts" / "pilot_audit_contract_v1.md"
EXPECTED_FIXTURE_SHA256 = (
    "873cb9e17ee341fe0163e7dbef0a35559bc7f3fc0b5807418051a90d9c64e7e0"
)
EXPECTED_MANAGED_FILES = [
    "docs/contracts/pilot_audit_contract_v1.md",
    "tests/fixtures/task13/pilot_audit_population_v1.json",
    "tests/test_task13_pilot_audit_contract.py",
]


class Task13PilotAuditContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.document = json.loads(cls.fixture_bytes)
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")

    def test_fixture_identity_and_fingerprint_are_frozen(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            self.document["contract_id"],
            "CONTRACT-T13-PILOT-AUDIT-001",
        )
        self.assertEqual(
            self.document["population_id"],
            "POPULATION-T13-BOUNDED-HISTORICAL-EVIDENCE-001",
        )
        self.assertEqual(self.document["population_version"], "1.0")
        self.assertEqual(
            self.document["accepted_claim"],
            "BOUNDED_HISTORICAL_EVIDENCE_AUDIT_CONTRACT_FROZEN",
        )
        self.assertFalse(self.document["sustained_pilot_claim"])
        self.assertFalse(self.document["provider_purchase_claim"])

    def test_repository_and_catalog_checkpoint_are_exact(self) -> None:
        checkpoint = self.document["repository_checkpoint"]
        self.assertEqual(
            checkpoint["accepted_main_commit"],
            "2ebef3f7f8c22c4a2f5dc2a47b3149cc4497e274",
        )
        self.assertEqual(
            checkpoint["accepted_tree"],
            "e2e3080260c1be4ba44d99e3bfe0c9be4dfc0766",
        )
        self.assertEqual(
            (
                checkpoint["catalog_version"],
                checkpoint["catalog_assets"],
                checkpoint["catalog_shards"],
                checkpoint["catalog_schemas"],
                checkpoint["catalog_queries"],
            ),
            ("0.15.0", 252, 4, 4, 7),
        )

    def test_population_totals_and_scope_reconcile(self) -> None:
        population = self.document["population"]
        self.assertEqual(
            population["class"],
            "BOUNDED_HISTORICAL_EVIDENCE_NOT_SUSTAINED_PILOT",
        )
        self.assertEqual(population["primary_slice_id"], "T08_ACCEPTED")
        self.assertEqual(population["primary_consumer"], "TASK-14")
        self.assertEqual(population["raw_rows"], 658)
        self.assertEqual(population["raw_parquet_files"], 7)
        self.assertEqual(population["raw_parquet_bytes"], 1_738_772)
        self.assertEqual(population["projection_files"], 2)
        self.assertEqual(population["projection_bytes"], 2_727_936)
        self.assertEqual(population["data_files"], 9)
        self.assertEqual(population["data_bytes"], 4_466_708)
        self.assertEqual(population["unique_raw_event_ids"], 658)
        self.assertEqual(population["unique_idempotency_keys"], 658)
        self.assertEqual(population["unique_content_sha256"], 657)
        self.assertEqual(
            population["global_pit_cutoff"],
            "2026-07-28T10:25:42.035105Z",
        )

        slices = self.document["slices"]
        self.assertEqual(sum(row["raw_rows"] for row in slices), 658)
        self.assertEqual(
            {row["slice_id"] for row in slices},
            {
                "T08_ACCEPTED",
                "T09_ACCEPTED",
                "T10_FAIL_CLOSED_V1",
                "T10_ACCEPTED_V2",
                "T11_ACCEPTED",
            },
        )

    def test_data_file_manifest_reconciles_without_requiring_raw_in_ci(
        self,
    ) -> None:
        files = self.document["data_files"]
        raw_files = [row for row in files if row["kind"] == "RAW_PARQUET"]
        projections = [
            row for row in files if row["kind"] == "DUCKDB_PROJECTION"
        ]
        self.assertEqual(len(files), 9)
        self.assertEqual(len(raw_files), 7)
        self.assertEqual(len(projections), 2)
        self.assertEqual(sum(row["rows"] for row in raw_files), 658)
        self.assertEqual(
            sum(row["bytes"] for row in raw_files),
            1_738_772,
        )
        self.assertEqual(
            sum(row["bytes"] for row in projections),
            2_727_936,
        )
        for row in files:
            with self.subTest(path=row["path"]):
                self.assertFalse(Path(row["path"]).is_absolute())
                self.assertNotIn("..", Path(row["path"]).parts)
                self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
                self.assertGreater(row["bytes"], 0)
                self.assertGreater(row["rows"], 0)

    def test_slice_baselines_preserve_typed_failures(self) -> None:
        slices = {row["slice_id"]: row for row in self.document["slices"]}
        expected = {
            "T08_ACCEPTED": (388, 388, 387, 0),
            "T09_ACCEPTED": (258, 258, 258, 0),
            "T10_FAIL_CLOSED_V1": (1, 1, 1, 0),
            "T10_ACCEPTED_V2": (8, 8, 8, 0),
            "T11_ACCEPTED": (3, 3, 3, 0),
        }
        for slice_id, baseline in expected.items():
            with self.subTest(slice_id=slice_id):
                row = slices[slice_id]
                self.assertEqual(
                    (
                        row["raw_rows"],
                        row["unique_raw_event_ids"],
                        row["unique_content_sha256"],
                        row["pit_order_violations"],
                    ),
                    baseline,
                )
                self.assertEqual(row["missing_identity_rows"], 0)

        t08_statuses = {
            (
                row["source"],
                row["response_status"],
                row["error_class"],
            ): row["rows"]
            for row in slices["T08_ACCEPTED"]["status_counts"]
        }
        self.assertEqual(
            t08_statuses,
            {
                ("HELIUS", "SUCCESS", None): 386,
                (
                    "SOLANA_TRACKER",
                    "HTTP_ERROR",
                    "http_status_not_success:401",
                ): 2,
            },
        )
        all_status_rows = sum(
            status["rows"]
            for row in slices.values()
            for status in row["status_counts"]
        )
        self.assertEqual(all_status_rows, 658)

    def test_task10_projection_denominators_are_quotes_not_fills(self) -> None:
        slices = {row["slice_id"]: row for row in self.document["slices"]}
        v1 = slices["T10_FAIL_CLOSED_V1"]["projection_rows"]
        v2 = slices["T10_ACCEPTED_V2"]["projection_rows"]
        self.assertEqual(v1["raw_api_events"], 1)
        self.assertEqual(v1["quote_attempts"], 1)
        self.assertEqual(v1["execution_attempts"], 0)
        self.assertEqual(v2["raw_api_events"], 8)
        self.assertEqual(v2["quote_attempts"], 8)
        self.assertEqual(v2["execution_attempts"], 0)
        self.assertFalse(self.document["pit"]["quote_as_fill"])

    def test_metric_denominators_and_typed_states_fail_closed(self) -> None:
        metrics = self.document["metrics"]
        self.assertEqual(
            metrics["typed_failure_rate"]["denominator"],
            "RAW_ROWS_PER_SLICE",
        )
        self.assertEqual(
            metrics["availability_lag"]["unit"],
            "milliseconds",
        )
        states = self.document["typed_states"]
        self.assertIn("HTTP_ERROR", states)
        self.assertIn("INVALID_RESPONSE", states)
        self.assertIn("NO_ROUTE", states)
        self.assertIn("AUDIT_INPUT_MISSING_OR_DRIFTED", states)
        self.assertIn("NOT_TESTABLE", states)
        pit = self.document["pit"]
        self.assertFalse(pit["missing_as_zero"])
        self.assertFalse(pit["provider_failure_as_no_route"])
        self.assertTrue(pit["backfill_availability_forbidden"])

    def test_tracked_lineage_hashes_match_repository_bytes(self) -> None:
        self.assertEqual(len(self.document["tracked_evidence"]), 12)
        for row in self.document["tracked_evidence"]:
            path = ROOT / row["path"]
            with self.subTest(asset_id=row["asset_id"]):
                self.assertTrue(path.is_file())
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    row["sha256"],
                )

    def test_reuse_is_thin_and_catalog_deferral_is_explicit(self) -> None:
        reuse = self.document["reuse"]
        self.assertEqual(reuse["new_dependency_count"], 0)
        self.assertFalse(reuse["general_data_quality_framework"])
        self.assertEqual(reuse["fork"], [])
        self.assertIn("QUERY-T05-PIT-RELATION-001", reuse["adopt"])
        self.assertIn("CONTRACT-T06-RAW-PARQUET-001", reuse["wrap"])

        catalog = self.document["catalog"]
        self.assertFalse(catalog["registered_in_atom2"])
        self.assertEqual(
            catalog["status"],
            "CATALOG_TRANSACTION_PENDING_TASK13_FINAL_RECONCILIATION",
        )
        self.assertTrue(catalog["blocks_task13_done"])
        self.assertFalse(catalog["blocks_contract_freeze"])

    def test_atom2_authority_is_exact_and_zero_effect(self) -> None:
        authority = self.document["authority"]
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
        self.assertFalse(
            self.document["next_atom"]["implementation_authorized"]
        )
        self.assertFalse(
            self.document["next_atom"]["external_calls_authorized"]
        )

    def test_contract_contains_decision_changing_boundaries(self) -> None:
        for marker in (
            "BOUNDED_HISTORICAL_EVIDENCE_AUDIT_CONTRACT_FROZEN",
            "POPULATION-T13-BOUNDED-HISTORICAL-EVIDENCE-001",
            "658 rows",
            "4,466,708 bytes",
            "`T08_ACCEPTED`",
            "`AUDIT_INPUT_MISSING_OR_DRIFTED`",
            "`NO_ROUTE`",
            "TASK-14",
            "general data-quality framework",
            "USD 0",
            "T13-A3_THIN_DETERMINISTIC_AUDITOR_V1",
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
