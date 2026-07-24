from __future__ import annotations

import hashlib
import json
import re
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "task07" / "provider_smoke_contract_v1.json"
)
EVIDENCE_FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task07"
    / "provider_smoke_live_evidence_v1.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task07"
    / "provider_smoke_execution_receipt_v1.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task07"
    / "provider_smoke_execution_summary_v1.md"
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(value: Any) -> list[tuple[str | None, Any]]:
    found: list[tuple[str | None, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.append((key, child))
            found.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk(child))
    return found


class Task07ProviderSmokeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(EVIDENCE_FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.summary = SUMMARY_PATH.read_text(encoding="utf-8")
        cls.fields = cls.fixture["attempt_field_order"]
        cls.rows = [dict(zip(cls.fields, row, strict=True)) for row in cls.fixture["attempt_rows"]]

    def test_fixture_identity_and_attempt_inventory_are_exact(self) -> None:
        self.assertEqual(
            self.fixture["fixture_id"],
            "TASK07_PROVIDER_SMOKE_LIVE_EVIDENCE_V1",
        )
        self.assertEqual(self.fixture["fixture_version"], "1.0")
        self.assertEqual(
            [row["attempt_id"] for row in self.rows],
            self.contract["expected_attempt_ids"],
        )
        self.assertEqual(len(self.rows), 35)
        self.assertEqual(
            self.fields,
            [
                "attempt_id",
                "provider",
                "source_run_id",
                "source_terminal_class",
                "accepted_terminal_class",
                "source_error_class",
                "accepted_error_class",
                "status_code",
                "response_size_bytes",
                "response_complete_at",
                "response_content_sha256",
            ],
        )

    def test_provider_mapping_and_counts_match_the_frozen_plan(self) -> None:
        expected_counts = {
            "HELIUS_RPC": 11,
            "HELIUS_WSS": 2,
            "SOLANA_TRACKER_DATA": 8,
            "JUPITER_SWAP": 9,
            "RAPTOR_HOSTED": 5,
        }
        self.assertEqual(Counter(row["provider"] for row in self.rows), expected_counts)
        self.assertEqual(
            self.fixture["aggregate"]["provider_attempt_counts"],
            expected_counts,
        )

        for row in self.rows:
            case_id = row["attempt_id"].split("#", maxsplit=1)[0]
            if case_id == "H12":
                expected_provider = "HELIUS_WSS"
            elif case_id.startswith("H"):
                expected_provider = "HELIUS_RPC"
            elif case_id.startswith("ST"):
                expected_provider = "SOLANA_TRACKER_DATA"
            elif case_id.startswith("J"):
                expected_provider = "JUPITER_SWAP"
            else:
                expected_provider = "RAPTOR_HOSTED"
            self.assertEqual(row["provider"], expected_provider, row["attempt_id"])

    def test_source_and_accepted_terminal_counts_recompute_exactly(self) -> None:
        source_counts = Counter(row["source_terminal_class"] for row in self.rows)
        accepted_counts = Counter(row["accepted_terminal_class"] for row in self.rows)
        self.assertEqual(
            source_counts,
            {
                "SUCCESS": 29,
                "INVALID_REQUEST": 1,
                "PROVIDER_5XX": 2,
                "MALFORMED_PAYLOAD": 1,
                "SCHEMA_DRIFT": 2,
            },
        )
        self.assertEqual(
            accepted_counts,
            {"SUCCESS": 32, "INVALID_REQUEST": 1, "PROVIDER_5XX": 2},
        )
        self.assertEqual(
            self.fixture["aggregate"]["source_terminal_counts"],
            source_counts,
        )
        self.assertEqual(
            self.fixture["aggregate"]["accepted_terminal_counts"],
            accepted_counts,
        )
        self.assertEqual(
            self.receipt["accepted_result"]["terminal_counts"],
            accepted_counts,
        )

    def test_only_the_three_accepted_raptor_reclassifications_are_present(self) -> None:
        changed = {
            row["attempt_id"]
            for row in self.rows
            if (
                row["source_terminal_class"],
                row["source_error_class"],
            )
            != (
                row["accepted_terminal_class"],
                row["accepted_error_class"],
            )
        }
        expected = {"R01#1", "R02#1", "R03#1"}
        declared = {
            item["attempt_id"] for item in self.fixture["accepted_reclassifications"]
        }
        self.assertEqual(changed, expected)
        self.assertEqual(declared, expected)
        self.assertEqual(
            set(self.receipt["accepted_result"]["reclassified_attempts"]),
            expected,
        )

        rows = {row["attempt_id"]: row for row in self.rows}
        self.assertEqual(
            (
                rows["R01#1"]["source_terminal_class"],
                rows["R01#1"]["source_error_class"],
                rows["R01#1"]["accepted_terminal_class"],
                rows["R01#1"]["accepted_error_class"],
            ),
            ("MALFORMED_PAYLOAD", "response_not_json", "SUCCESS", None),
        )
        for attempt_id in ("R02#1", "R03#1"):
            self.assertEqual(
                (
                    rows[attempt_id]["source_terminal_class"],
                    rows[attempt_id]["source_error_class"],
                    rows[attempt_id]["accepted_terminal_class"],
                    rows[attempt_id]["accepted_error_class"],
                ),
                ("SCHEMA_DRIFT", "quote_output_amount_invalid", "SUCCESS", None),
            )

    def test_provider_failures_remain_failures_not_no_route_or_zero(self) -> None:
        rows = {row["attempt_id"]: row for row in self.rows}
        for attempt_id in ("J09#1", "R05#1"):
            row = rows[attempt_id]
            self.assertEqual(row["accepted_terminal_class"], "PROVIDER_5XX")
            self.assertEqual(row["accepted_error_class"], "http_500")
            self.assertEqual(row["status_code"], 500)
            self.assertGreater(row["response_size_bytes"], 0)
            self.assertNotIn("NO_ROUTE", json.dumps(row))
        self.assertEqual(
            set(self.receipt["accepted_result"]["retained_provider_failures"]),
            {"J09#1", "R05#1"},
        )

    def test_run_roots_counts_bytes_and_hashes_are_frozen(self) -> None:
        runs = {run["run_id"]: run for run in self.fixture["raw_runs"]}
        self.assertEqual(
            {
                run_id: (
                    run["attempt_count"],
                    run["file_count"],
                    run["raw_file_bytes"],
                    run["response_bytes"],
                    run["fileset_sha256"],
                )
                for run_id, run in runs.items()
            },
            {
                "t07a4b-20260724T132144Z": (
                    33,
                    99,
                    466676,
                    48777,
                    "cbf9d931a9337c67bceeb83887e8eca3fd326050f81266443f31cb3aeaffbf0c",
                ),
                "t07a4b-20260724T135632Z": (
                    2,
                    6,
                    22738,
                    827,
                    "729922dbf54b1b8e229119d65a11b2a69cc7283460335c5e1fa4c2bab61ea92c",
                ),
            },
        )
        self.assertEqual(sum(run["attempt_count"] for run in runs.values()), 35)
        self.assertEqual(sum(row["response_size_bytes"] for row in self.rows), 49604)
        self.assertEqual(self.fixture["aggregate"]["response_bytes"], 49604)

        receipt_runs = {
            run["run_id"]: run["fileset_sha256"]
            for run in self.receipt["source_runs"]
        }
        fixture_runs = {
            run_id: run["fileset_sha256"] for run_id, run in runs.items()
        }
        self.assertEqual(receipt_runs, fixture_runs)

    def test_timestamps_are_timezone_aware_and_monotonic(self) -> None:
        times = [
            datetime.fromisoformat(row["response_complete_at"]) for row in self.rows
        ]
        self.assertTrue(all(value.tzinfo is not None for value in times))
        self.assertEqual(times, sorted(times))

    def test_all_declared_sha256_values_are_lowercase_hex(self) -> None:
        for key, value in _walk(self.fixture):
            if key is not None and key.endswith("sha256"):
                self.assertIsInstance(value, str)
                self.assertRegex(value, SHA256_RE)
        for key, value in _walk(self.receipt):
            if key is not None and key.endswith("sha256"):
                self.assertIsInstance(value, str)
                self.assertRegex(value, SHA256_RE)

    def test_fixture_is_sanitized_and_clean_clone_portable(self) -> None:
        forbidden_keys = {
            "response_body",
            "request_body",
            "request_headers",
            "response_headers",
            "authorization",
            "api_key",
            "private_key",
            "seed_phrase",
        }
        keys = {key.lower() for key, _ in _walk(self.fixture) if key is not None}
        self.assertTrue(forbidden_keys.isdisjoint(keys))

        serialized = json.dumps(self.fixture, sort_keys=True).lower()
        for marker in (
            "c:\\\\users\\\\",
            "/home/",
            "bearer ",
            "x-api-key",
            "seed phrase",
            "private key",
        ):
            self.assertNotIn(marker, serialized)
        self.assertEqual(
            self.fixture["sanitization"],
            {
                "response_bodies_in_fixture": 0,
                "request_values_in_fixture": 0,
                "headers_in_fixture": 0,
                "credentials_in_fixture": 0,
                "absolute_paths_in_fixture": 0,
            },
        )

    def test_receipt_and_summary_bind_the_fixture_without_self_reference(self) -> None:
        fixture_sha256 = _sha256(EVIDENCE_FIXTURE_PATH)
        receipt_sha256 = _sha256(RECEIPT_PATH)
        self.assertEqual(
            self.receipt["tracked_fixture"]["sha256"],
            fixture_sha256,
        )
        self.assertIn(fixture_sha256, self.summary)
        self.assertIn(receipt_sha256, self.summary)
        self.assertEqual(
            self.receipt["status"],
            "PASS_WITH_PROVIDER_FAILURE_EVIDENCE",
        )
        self.assertEqual(
            self.receipt["catalog_status"],
            "CATALOG_GAP_PENDING_SEPARATE_ATOM",
        )
        self.assertEqual(self.receipt["state_change"], "NONE")

    def test_atom_authority_is_exact_and_records_no_side_effects(self) -> None:
        authority = self.receipt["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(
            authority["managed_files"],
            [
                "docs/evidence/task07/provider_smoke_execution_summary_v1.md",
                "docs/evidence/task07/provider_smoke_execution_receipt_v1.json",
                "tests/fixtures/task07/provider_smoke_live_evidence_v1.json",
                "tests/test_task07_provider_smoke_evidence.py",
            ],
        )
        self.assertEqual(authority["network_calls_during_atom"], 0)
        self.assertEqual(authority["raw_files_written_during_atom"], 0)
        self.assertEqual(authority["dependency_changes"], 0)
        self.assertEqual(authority["catalog_changes"], 0)
        self.assertFalse(authority["staged"])
        self.assertFalse(authority["committed"])
        self.assertFalse(authority["pushed"])


if __name__ == "__main__":
    unittest.main()
