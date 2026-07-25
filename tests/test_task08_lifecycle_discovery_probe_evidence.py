from __future__ import annotations

import hashlib
import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task08"
    / "lifecycle_discovery_probe_live_evidence_v1.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task08"
    / "lifecycle_discovery_probe_execution_receipt_v1.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task08"
    / "lifecycle_discovery_probe_execution_summary_v1.md"
)
TRANSPORT_CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "lifecycle_discovery_probe_transport_contract_v1.md"
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


class Task08LifecycleDiscoveryProbeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.summary = SUMMARY_PATH.read_text(encoding="utf-8")
        cls.transport_contract = TRANSPORT_CONTRACT_PATH.read_text(encoding="utf-8")

    def test_fixture_identity_and_acceptance_boundary_are_exact(self) -> None:
        self.assertEqual(
            self.fixture["fixture_id"],
            "TASK08_LIFECYCLE_DISCOVERY_PROBE_LIVE_EVIDENCE_V1",
        )
        self.assertEqual(self.fixture["fixture_version"], "1.0")
        self.assertEqual(self.fixture["source_atom"], "T08-A5U-PROBE")
        self.assertEqual(self.fixture["transport_acceptance_status"], "PASS")
        self.assertEqual(
            self.fixture["lifecycle_coverage_status"],
            "NOT_TESTABLE_IN_WINDOW",
        )
        self.assertEqual(
            self.receipt["status"],
            "PASS_WITH_EXPLICIT_COVERAGE_BLOCKER_EVIDENCE",
        )

    def test_raw_inventory_hashes_and_sizes_are_frozen(self) -> None:
        raw_run = self.fixture["raw_run"]
        self.assertEqual(raw_run["run_id"], "t08a5-20260725T084127Z")
        self.assertEqual(raw_run["transport_contract_version"], "1.1")
        self.assertEqual(
            [
                (item["logical_path"], item["bytes"], item["sha256"])
                for item in raw_run["files"]
            ],
            [
                (
                    "partitions/probe.parquet",
                    798206,
                    "079dc1401b4da3cf0e1d63d2b20210e017252f26d93c4dd2afd8af7d950fcb6a",
                ),
                (
                    "receipts/probe.manifest.json",
                    742,
                    "8872648a10ca39b6b9cdf3f10dba75dc51bef8083ddd768dca221720dab6ea98",
                ),
                (
                    "receipts/probe.receipt.json",
                    817,
                    "d1fb206fceb9a0277e65ae36f99ed245f1d82200d1b3d7fc0ce7d4b906d42598",
                ),
            ],
        )
        self.assertEqual(
            sum(item["bytes"] for item in raw_run["files"]),
            raw_run["stored_file_bytes"],
        )

    def test_partition_manifest_receipt_counts_reconcile(self) -> None:
        raw_run = self.fixture["raw_run"]
        summary = self.fixture["probe_summary"]
        self.assertEqual(raw_run["row_count"], 388)
        self.assertEqual(raw_run["event_count_received"], 388)
        self.assertEqual(raw_run["event_count_stored"], 388)
        self.assertEqual(raw_run["omitted_event_count"], 0)
        self.assertEqual(sum(raw_run["provider_events_stored"].values()), 388)
        self.assertEqual(sum(raw_run["status_counts"].values()), 388)
        self.assertEqual(summary["evidence_records"], 388)
        self.assertEqual(summary["stored_bytes"], raw_run["stored_file_bytes"])
        self.assertEqual(
            summary["received_and_stored_bytes"],
            summary["received_bytes"] + summary["stored_bytes"],
        )

    def test_notification_and_decoder_counts_preserve_negative_evidence(self) -> None:
        summary = self.fixture["probe_summary"]
        self.assertEqual(summary["notifications"], 385)
        self.assertEqual(
            summary["successful_notifications"] + summary["failed_notifications"],
            summary["notifications"],
        )
        self.assertEqual(summary["decoded_events"], 101)
        self.assertEqual(summary["create_events"], 0)
        self.assertEqual(summary["unsupported_pump_program_data"], 15)
        self.assertEqual(summary["unique_followup_candidates"], 0)
        self.assertEqual(summary["rpc_followups"], 0)
        self.assertEqual(summary["wss_stop_reason"], "STREAM_GUARD")

    def test_tracker_failures_are_not_empty_zero_or_no_route(self) -> None:
        failures = self.fixture["retained_failure_evidence"]
        self.assertEqual(
            failures,
            [
                {
                    "provider": "SOLANA_TRACKER",
                    "terminal_class": "HTTP_ERROR",
                    "error_class": "http_status_not_success:401",
                    "count": 2,
                    "accepted_semantics": (
                        "ACCESS_FAILURE_NOT_EMPTY_NOT_ZERO_NOT_NO_ROUTE"
                    ),
                }
            ],
        )
        self.assertEqual(self.fixture["probe_summary"]["solana_tracker_failures"], 2)
        self.assertEqual(
            self.receipt["accepted_result"]["solana_tracker_terminal_class"],
            "HTTP_ERROR",
        )

    def test_every_frozen_cap_is_respected(self) -> None:
        summary = self.fixture["probe_summary"]
        caps = self.fixture["frozen_caps"]
        for field in (
            "elapsed_seconds",
            "notifications",
            "stream_bytes",
            "rpc_followups",
            "helius_credits",
            "solana_tracker_requests",
            "received_and_stored_bytes",
            "concurrency",
            "retries",
            "cash_spend_usd_cents",
        ):
            self.assertLessEqual(summary[field], caps[field], field)
        self.assertLessEqual(summary["received_bytes"], caps["admission_received_bytes"])

    def test_timestamps_are_utc_aware_and_monotonic(self) -> None:
        raw_run = self.fixture["raw_run"]
        timestamps = [
            datetime.fromisoformat(raw_run[field].replace("Z", "+00:00"))
            for field in (
                "min_available_to_strategy_at",
                "max_available_to_strategy_at",
                "first_reliable_available_at",
            )
        ]
        self.assertTrue(all(value.tzinfo is not None for value in timestamps))
        self.assertEqual(timestamps, sorted(timestamps))

    def test_all_declared_sha256_values_are_lowercase_hex(self) -> None:
        for document in (self.fixture, self.receipt):
            for key, value in _walk(document):
                if key is not None and key.endswith("sha256"):
                    self.assertIsInstance(value, str)
                    self.assertRegex(value, SHA256_RE)

    def test_fixture_receipt_summary_and_contract_are_bound(self) -> None:
        fixture_sha256 = _sha256(FIXTURE_PATH)
        receipt_sha256 = _sha256(RECEIPT_PATH)
        self.assertEqual(self.receipt["tracked_fixture"]["sha256"], fixture_sha256)
        self.assertIn(fixture_sha256, self.summary)
        self.assertIn(receipt_sha256, self.summary)
        for text in (self.summary, self.transport_contract):
            self.assertIn("t08a5-20260725T084127Z", text)
            self.assertIn("NOT_TESTABLE_IN_WINDOW", text)
            self.assertIn(
                "079dc1401b4da3cf0e1d63d2b20210e017252f26d93c4dd2afd8af7d950fcb6a",
                text,
            )

    def test_sanitization_and_authority_are_exact(self) -> None:
        forbidden_keys = {
            "provider_body",
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
            self.receipt["authority"]["managed_files"],
            [
                "docs/contracts/lifecycle_discovery_probe_transport_contract_v1.md",
                "docs/evidence/task08/lifecycle_discovery_probe_execution_summary_v1.md",
                "docs/evidence/task08/lifecycle_discovery_probe_execution_receipt_v1.json",
                "tests/fixtures/task08/lifecycle_discovery_probe_live_evidence_v1.json",
                "tests/test_task08_lifecycle_discovery_probe_evidence.py",
            ],
        )
        for field in (
            "network_calls_during_atom",
            "raw_files_written_during_atom",
            "dependency_changes",
            "catalog_changes",
            "canonical_status_changes",
        ):
            self.assertEqual(self.receipt["authority"][field], 0)
        self.assertFalse(self.receipt["authority"]["staged"])
        self.assertFalse(self.receipt["authority"]["committed"])
        self.assertFalse(self.receipt["authority"]["pushed"])
        self.assertEqual(self.receipt["state_change"], "NONE")


if __name__ == "__main__":
    unittest.main()
