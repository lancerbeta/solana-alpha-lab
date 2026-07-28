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
    / "task10"
    / "jupiter_quote_logger_live_evidence_v1.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task10"
    / "jupiter_quote_logger_execution_receipt_v1.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task10"
    / "jupiter_quote_logger_execution_summary_v1.md"
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


class Task10JupiterQuoteLoggerEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.summary = SUMMARY_PATH.read_text(encoding="utf-8")

    def test_identity_and_fail_closed_boundary_are_exact(self) -> None:
        self.assertEqual(
            self.fixture["fixture_id"],
            "TASK10_JUPITER_QUOTE_LOGGER_LIVE_EVIDENCE_V1",
        )
        self.assertEqual(self.fixture["fixture_version"], "1.0")
        self.assertEqual(
            self.fixture["source_atom"],
            "T10-A4_BOUNDED_EXTERNAL_QUOTE_PILOT",
        )
        self.assertEqual(
            self.fixture["repair_atom"],
            "T10-A4R_TYPED_ADDITIVE_QUOTE_SCHEMA",
        )
        self.assertEqual(
            self.receipt["status"],
            "STOPPED_FAIL_CLOSED_OFFLINE_REPLAY_CANDIDATE",
        )
        self.assertEqual(
            self.fixture["live_summary"]["stop_reason"],
            "UNCLASSIFIABLE_SCHEMA_DRIFT",
        )

    def test_raw_inventory_hashes_and_sizes_are_frozen(self) -> None:
        raw_run = self.fixture["raw_run"]
        self.assertEqual(raw_run["run_id"], "t10a4-20260728T011304Z")
        self.assertEqual(
            [
                (item["logical_path"], item["bytes"], item["sha256"])
                for item in raw_run["files"]
            ],
            [
                (
                    "partitions/quotes.parquet",
                    14811,
                    "eed05d3c5f65f5adf4e77c07e0fbbccd94856ecabfcb7c5b963e3c0611c8cb67",
                ),
                (
                    "projections/quotes.duckdb",
                    1355776,
                    "557692a5a37a6d30e8e7ed9e293e5ee24cb6315c9c8714b09e2d561a75d18f5b",
                ),
                (
                    "receipts/quotes.manifest.json",
                    742,
                    "40d836d273f90623b1cdc702f28e777e2699b6c6d44acd9db48a8e601e86e520",
                ),
                (
                    "receipts/run.receipt.json",
                    1779,
                    "6a25a37114de65c378b9de3ba4d8a130cd6553b9c908fc91e0dd68d7729b8059",
                ),
            ],
        )
        self.assertEqual(
            sum(item["bytes"] for item in raw_run["files"]),
            raw_run["files"][0]["bytes"]
            + raw_run["files"][1]["bytes"]
            + raw_run["files"][2]["bytes"]
            + raw_run["files"][3]["bytes"],
        )

    def test_live_counts_and_caps_reconcile(self) -> None:
        live = self.fixture["live_summary"]
        caps = self.fixture["frozen_caps"]
        self.assertEqual(live["provider_calls"], 1)
        self.assertEqual(live["buy_attempts"], 1)
        self.assertEqual(live["sell_attempts"], 0)
        self.assertEqual(live["retries"], 0)
        self.assertEqual(live["terminal_counts"], {"INVALID_RESPONSE": 1})
        self.assertLessEqual(
            live["provider_calls"],
            caps["http_requests_total_max"],
        )
        self.assertLessEqual(
            live["received_bytes"],
            caps["received_response_bytes_max"],
        )
        self.assertLessEqual(
            live["stored_bytes"],
            caps["durable_raw_bytes_max"],
        )
        self.assertEqual(live["execution_attempt_rows"], 0)

    def test_schema_repair_is_typed_and_history_is_immutable(self) -> None:
        extension = self.fixture["observed_schema_extension"]
        self.assertEqual(len(extension["top_level_additive_fields"]), 8)
        self.assertEqual(
            extension["swap_info_additive_fields"],
            {"updateContextSlot": "nonnegative_atomic_text"},
        )
        self.assertEqual(
            extension["swap_info_absent_field_pair"],
            ["feeAmount", "feeMint"],
        )
        self.assertFalse(
            extension["transaction_or_instruction_payload_observed"]
        )
        self.assertTrue(
            extension["raw_record_preserved_as_invalid_response"]
        )
        self.assertFalse(extension["historical_quote_attempt_rewritten"])
        self.assertFalse(
            extension["offline_replay_reclassified_historical_row"]
        )

    def test_offline_replay_is_candidate_only_and_fee_nulls_are_preserved(
        self,
    ) -> None:
        replay = self.fixture["offline_replay"]
        self.assertEqual(replay["status"], "PASS")
        self.assertEqual(
            replay["terminal"],
            "QUOTE_AVAILABLE_CANDIDATE_AFTER_TYPED_EXTENSION",
        )
        self.assertEqual(replay["output_quoted_atomic"], 3452264667206)
        self.assertEqual(replay["route_count"], 2)
        self.assertEqual(replay["context_slot"], 435648803)
        for field in (
            "provider_fee_atomic",
            "platform_fee_atomic",
            "fee_mint",
            "included_in_output_amount",
        ):
            self.assertIsNone(replay[field])
        self.assertTrue(replay["live_raw_hashes_unchanged"])
        self.assertEqual(replay["network_calls"], 0)
        self.assertEqual(replay["raw_writes"], 0)

    def test_quote_candidate_does_not_promote_execution_claims(self) -> None:
        boundary = self.fixture["decision_boundary"]
        self.assertTrue(boundary["one_legacy_buy_quote_candidate_observed"])
        for claim in (
            "all_buy_panels_observed",
            "reverse_sell_observed",
            "no_route_observed",
            "fillable_established",
            "realized_vwap_established",
            "net_return_established",
            "retry_authorized",
            "additional_external_call_authorized",
            "canonical_status_change_implied",
        ):
            self.assertFalse(boundary[claim], claim)

    def test_selection_is_pre_observation_and_bound_to_task09(self) -> None:
        selection = self.fixture["selection"]
        self.assertFalse(selection["price_or_route_observation_used"])
        self.assertEqual(
            selection["source_asset_id"],
            "DATA-T09-PUMPSWAP-TOUCH-PROBE-RAW-001",
        )
        self.assertEqual(selection["source_run_id"], "t09a4-20260727T184740Z")
        self.assertEqual(
            selection["source_partition_sha256"],
            "577e614c0b2f41b7a1e3ae92b6cfd965e87e4d4bca76070925873df1ef5b4466",
        )

    def test_timestamps_and_declared_hashes_are_valid(self) -> None:
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

    def test_tracked_artifacts_are_bound_and_sanitized(self) -> None:
        fixture_sha256 = _sha256(FIXTURE_PATH)
        receipt_sha256 = _sha256(RECEIPT_PATH)
        self.assertEqual(
            self.receipt["tracked_fixture"]["sha256"],
            fixture_sha256,
        )
        self.assertIn(fixture_sha256, self.summary)
        self.assertIn(receipt_sha256, self.summary)
        self.assertIn("t10a4-20260728T011304Z", self.summary)
        self.assertIn(
            "eed05d3c5f65f5adf4e77c07e0fbbccd94856ecabfcb7c5b963e3c0611c8cb67",
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
            "FIXTURE-T10-JUPITER-QUOTE-PILOT-PLAN-001",
            "MODULE-T10-JUPITER-QUOTE-TRANSPORT-001",
            "TEST-T10-JUPITER-QUOTE-TRANSPORT-001",
            "DATA-T10-JUPITER-QUOTE-PILOT-RAW-001",
            "DATA-T10-JUPITER-QUOTE-PROJECTION-001",
            "FIXTURE-T10-JUPITER-QUOTE-LIVE-EVIDENCE-001",
            "EVIDENCE-T10-JUPITER-QUOTE-RECEIPT-001",
            "EVIDENCE-T10-JUPITER-QUOTE-SUMMARY-001",
            "TEST-T10-JUPITER-QUOTE-EVIDENCE-001",
        }
        self.assertGreaterEqual(
            tuple(int(part) for part in manifest["catalog_version"].split(".")),
            (0, 12, 0),
        )
        self.assertTrue(expected.issubset(records))
        self.assertTrue(
            expected.issubset(set(manifest["mandatory_asset_ids"]))
        )
        raw = records["DATA-T10-JUPITER-QUOTE-PILOT-RAW-001"]
        projection = records["DATA-T10-JUPITER-QUOTE-PROJECTION-001"]
        for asset in (raw, projection):
            self.assertEqual(asset["location"]["kind"], "logical_only")
            self.assertNotIn("repository_path", asset["location"])

    def test_authority_receipt_has_zero_sensitive_actions(self) -> None:
        authority = self.receipt["authority"]
        self.assertEqual(authority["external_run_count"], 1)
        self.assertEqual(authority["external_provider_calls"], 1)
        self.assertEqual(authority["external_retries"], 0)
        self.assertEqual(
            authority["network_calls_during_repair_and_acceptance"],
            0,
        )
        for field in (
            "api_keys_used",
            "accounts_used",
            "provider_credits",
            "cash_spend_usd_cents",
            "wallet_signer_transaction_actions",
            "dependency_changes",
        ):
            self.assertEqual(authority[field], 0, field)
        for field in ("commit", "push", "pull_request", "merge", "ui_changes"):
            self.assertFalse(authority[field], field)


if __name__ == "__main__":
    unittest.main()
