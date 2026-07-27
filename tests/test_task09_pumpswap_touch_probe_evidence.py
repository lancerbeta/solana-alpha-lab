from __future__ import annotations

import hashlib
import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task09"
    / "pumpswap_touch_probe_live_evidence_v1.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task09"
    / "pumpswap_touch_probe_execution_receipt_v1.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task09"
    / "pumpswap_touch_probe_execution_summary_v1.md"
)
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "pumpswap_touch_observation_contract_v1.md"
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


class Task09PumpSwapTouchProbeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.summary = SUMMARY_PATH.read_text(encoding="utf-8")
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")

    def test_identity_and_acceptance_boundary_are_exact(self) -> None:
        self.assertEqual(
            self.fixture["fixture_id"],
            "TASK09_PUMPSWAP_TOUCH_PROBE_LIVE_EVIDENCE_V1",
        )
        self.assertEqual(self.fixture["fixture_version"], "1.0")
        self.assertEqual(
            self.fixture["source_atom"],
            "T09-A4_PUMPSWAP_TOUCH_EXTERNAL_RPC_WSS_RAW_WRITE",
        )
        self.assertEqual(
            self.receipt["status"],
            "PASS_WITH_FAIL_CLOSED_SCHEMA_EXTENSION_REPAIR",
        )
        self.assertEqual(
            self.fixture["coverage_disposition"],
            "BOUNDED_POST_MIGRATION_TOUCH_EVIDENCE_NOT_FILLABLE",
        )

    def test_raw_inventory_hashes_and_sizes_are_frozen(self) -> None:
        raw_run = self.fixture["raw_run"]
        self.assertEqual(raw_run["run_id"], "t09a4-20260727T184740Z")
        self.assertEqual(raw_run["transport_contract_version"], "1.0")
        self.assertEqual(
            [
                (item["logical_path"], item["bytes"], item["sha256"])
                for item in raw_run["files"]
            ],
            [
                (
                    "partitions/probe.parquet",
                    842679,
                    "577e614c0b2f41b7a1e3ae92b6cfd965e87e4d4bca76070925873df1ef5b4466",
                ),
                (
                    "receipts/probe.manifest.json",
                    742,
                    "2070c0d36aeb963be8e3e39628c2d7a032679dad34d4d6f9131951190bba6493",
                ),
                (
                    "receipts/probe.receipt.json",
                    380,
                    "6191f4b2434351dbfda4b8e4d0b57fd879bc62cdf1604460a52a7d5cf76b31be",
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
        self.assertEqual(raw_run["row_count"], 258)
        self.assertEqual(raw_run["event_count_received"], 258)
        self.assertEqual(raw_run["event_count_stored"], 258)
        self.assertEqual(raw_run["omitted_event_count"], 0)
        self.assertEqual(sum(raw_run["method_event_counts"].values()), 258)
        self.assertEqual(sum(raw_run["status_counts"].values()), 258)
        self.assertEqual(summary["evidence_records"], 258)
        self.assertEqual(
            raw_run["status_counts"]["INVALID_RESPONSE"],
            1,
        )

    def test_notification_and_decoder_counts_preserve_negative_evidence(
        self,
    ) -> None:
        summary = self.fixture["probe_summary"]
        self.assertEqual(summary["notifications"], 256)
        self.assertEqual(
            summary["successful_notifications"]
            + summary["failed_notifications"],
            summary["notifications"],
        )
        self.assertEqual(summary["failed_notifications"], 132)
        self.assertEqual(summary["decoded_events"], 75)
        self.assertEqual(
            summary["buy_events"] + summary["sell_events"],
            summary["decoded_events"],
        )
        self.assertEqual(summary["unsupported_program_data"], 6)
        self.assertEqual(summary["wss_stop_reason"], "NOTIFICATION_CAP")

    def test_schema_extension_repair_is_bounded_and_history_is_immutable(
        self,
    ) -> None:
        extension = self.fixture["observed_schema_extension"]
        self.assertEqual(extension["field"], "transactionIndex")
        self.assertEqual(extension["observed_type"], "nonnegative_integer")
        self.assertEqual(
            extension["live_error_class"],
            "get_transaction_result_keys_drift",
        )
        self.assertTrue(extension["raw_record_preserved_as_invalid_response"])
        self.assertFalse(extension["offline_replay_reclassified_raw_record"])
        self.assertEqual(
            self.fixture["probe_summary"]["offline_replay_terminal"],
            "FIELD_COVERAGE_CANDIDATE",
        )

    def test_touch_fields_do_not_promote_execution_claims(self) -> None:
        coverage = self.fixture["touch_field_coverage"]
        self.assertEqual(coverage["event_types"], ["BuyEvent", "SellEvent"])
        for field in (
            "pool_base_token_reserves",
            "pool_quote_token_reserves",
            "virtual_quote_reserves",
            "protocol_fee",
            "coin_creator_fee",
            "lp_fee",
        ):
            self.assertIn(field, coverage["required_observed_fields"])
        self.assertEqual(
            coverage["raw_virtual_effective_reserve_separation"],
            "PASS",
        )
        for claim in (
            "fillable_claim",
            "no_route_claim",
            "migration_claim",
            "net_return_claim",
        ):
            self.assertFalse(coverage[claim])

    def test_lineage_duplicates_revisions_and_ordering_are_explicit(
        self,
    ) -> None:
        lineage = self.fixture["lineage_and_ordering"]
        self.assertEqual(lineage["unique_raw_event_ids"], 258)
        self.assertEqual(lineage["unique_idempotency_keys"], 258)
        self.assertEqual(lineage["duplicate_event_count"], 0)
        self.assertEqual(lineage["revision_1_records"], 258)
        self.assertEqual(lineage["revision_link_records"], 0)
        self.assertFalse(lineage["file_row_order_is_source_order"])
        self.assertEqual(
            lineage["consumer_ordering_rule"],
            "SORT_BY_OBSERVED_AT_THEN_RAW_EVENT_ID",
        )
        self.assertTrue(lineage["ingested_not_before_observed"])

    def test_every_frozen_cap_and_authority_boundary_is_respected(
        self,
    ) -> None:
        summary = self.fixture["probe_summary"]
        caps = self.fixture["frozen_caps"]
        for field in (
            "wss_connections",
            "wss_subscriptions",
            "notifications",
            "rpc_followups",
            "concurrency",
            "retries",
            "cash_spend_usd_cents",
        ):
            self.assertLessEqual(summary[field], caps[field], field)
        self.assertEqual(summary["provider_credits"], 0)
        self.assertEqual(summary["restart_attempts"], 0)
        self.assertFalse(
            self.fixture["decision_boundary"][
                "additional_external_call_authorized"
            ]
        )

    def test_timestamps_and_all_declared_hashes_are_valid(self) -> None:
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
        for document in (self.fixture, self.receipt):
            for key, value in _walk(document):
                if key is not None and key.endswith("sha256"):
                    self.assertIsInstance(value, str)
                    self.assertRegex(value, SHA256_RE)

    def test_catalog_registration_is_exact_and_raw_is_logical_only(self) -> None:
        manifest = yaml.safe_load(
            (ROOT / "catalog" / "catalog_manifest.yaml").read_text(
                encoding="utf-8"
            )
        )
        registry = yaml.safe_load(
            (ROOT / "catalog" / "assets" / "core.yaml").read_text(
                encoding="utf-8"
            )
        )
        records = {
            record["asset_id"]: record
            for record in registry["records"]
        }
        expected = {
            "CONTRACT-T09-PUMPSWAP-TOUCH-001",
            "FIXTURE-T09-PUMPSWAP-TOUCH-001",
            "TEST-T09-PUMPSWAP-TOUCH-001",
            "MODULE-T09-PUMPSWAP-TOUCH-DECODER-001",
            "FIXTURE-T09-PUMPSWAP-IDL-SUBSET-001",
            "TEST-T09-PUMPSWAP-TOUCH-DECODER-001",
            "MODULE-T09-PUMPSWAP-TOUCH-PROBE-001",
            "SCRIPT-T09-PUMPSWAP-TOUCH-PROBE-001",
            "TEST-T09-PUMPSWAP-TOUCH-PROBE-001",
            "DATA-T09-PUMPSWAP-TOUCH-PROBE-RAW-001",
            "FIXTURE-T09-PUMPSWAP-TOUCH-EVIDENCE-001",
            "EVIDENCE-T09-PUMPSWAP-TOUCH-RECEIPT-001",
            "EVIDENCE-T09-PUMPSWAP-TOUCH-SUMMARY-001",
            "TEST-T09-PUMPSWAP-TOUCH-EVIDENCE-001",
        }
        self.assertEqual(manifest["catalog_version"], "0.9.0")
        self.assertTrue(expected.issubset(records))
        self.assertTrue(
            expected.issubset(set(manifest["mandatory_asset_ids"]))
        )
        raw = records["DATA-T09-PUMPSWAP-TOUCH-PROBE-RAW-001"]
        self.assertEqual(raw["location"]["kind"], "logical_only")
        self.assertTrue(raw["location"]["logical_uri"].startswith("raw://"))
        self.assertNotIn("repository_path", raw["location"])

    def test_tracked_artifacts_are_bound_and_sanitized(self) -> None:
        fixture_sha256 = _sha256(FIXTURE_PATH)
        receipt_sha256 = _sha256(RECEIPT_PATH)
        self.assertEqual(
            self.receipt["tracked_fixture"]["sha256"],
            fixture_sha256,
        )
        self.assertIn(fixture_sha256, self.summary)
        self.assertIn(receipt_sha256, self.summary)
        for text in (self.summary, self.contract):
            self.assertIn("t09a4-20260727T184740Z", text)
            self.assertIn("get_transaction_result_keys_drift", text)
        self.assertIn(
            "577e614c0b2f41b7a1e3ae92b6cfd965e87e4d4bca76070925873df1ef5b4466",
            self.summary,
        )

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
        keys = {
            key.lower()
            for key, _ in _walk(self.fixture)
            if key is not None
        }
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


if __name__ == "__main__":
    unittest.main()
