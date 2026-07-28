from __future__ import annotations

import hashlib
import json
import re
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task10"
    / "jupiter_quote_logger_live_evidence_v2.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task10"
    / "jupiter_quote_logger_execution_receipt_v2.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task10"
    / "jupiter_quote_logger_execution_summary_v2.md"
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


class Task10JupiterQuoteLoggerEvidenceV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.summary = SUMMARY_PATH.read_text(encoding="utf-8")

    def test_identity_and_acceptance_boundary_are_exact(self) -> None:
        self.assertEqual(
            self.fixture["fixture_id"],
            "TASK10_JUPITER_QUOTE_LOGGER_LIVE_EVIDENCE_V2",
        )
        self.assertEqual(self.fixture["fixture_version"], "2.0")
        self.assertEqual(
            self.fixture["source_atom"],
            "T10-A6_BOUNDED_EXTERNAL_QUOTE_PILOT_V2",
        )
        self.assertEqual(
            self.fixture["status"],
            "PASS_BOUNDED_BUY_REVERSE_SELL_QUOTE_PANEL",
        )
        self.assertEqual(self.receipt["status"], self.fixture["status"])

    def test_raw_inventory_hashes_and_sizes_are_frozen(self) -> None:
        raw_run = self.fixture["raw_run"]
        self.assertEqual(raw_run["run_id"], "t10a6-20260728T015829Z")
        self.assertEqual(raw_run["dataset_version"], "2.0")
        self.assertEqual(
            [
                (item["logical_path"], item["bytes"], item["sha256"])
                for item in raw_run["files"]
            ],
            [
                (
                    "partitions/quotes.parquet",
                    31635,
                    "0648390ba3af49bacf804aafb7cc4788fbbb7040508cfef79f88c3d1ed188d1b",
                ),
                (
                    "projections/quotes.duckdb",
                    1372160,
                    "c1664a1180a525477d9beba5b5d13662cf9b5ae8721506363ce34d65af50ceda",
                ),
                (
                    "receipts/quotes.manifest.json",
                    742,
                    "84cf3cf6103cbf7e81e3ff05c76e363514b60a033149085a5e375e8b65e86ca4",
                ),
                (
                    "receipts/run.receipt.json",
                    1761,
                    "ac64469d0e0dd214aba775f625a90aec0006a3685921ab2234f49df89531f0a4",
                ),
            ],
        )
        self.assertEqual(
            sum(item["bytes"] for item in raw_run["files"]),
            self.fixture["run_summary"]["stored_bytes"],
        )

    def test_run_counts_caps_and_zero_execution_reconcile(self) -> None:
        summary = self.fixture["run_summary"]
        caps = self.fixture["frozen_caps"]
        self.assertEqual(summary["provider_calls"], 8)
        self.assertEqual(summary["buy_attempts"], 4)
        self.assertEqual(summary["sell_attempts"], 4)
        self.assertEqual(summary["sell_not_attempted"], 0)
        self.assertEqual(summary["retries"], 0)
        self.assertEqual(summary["terminal_counts"], {"QUOTE_AVAILABLE": 8})
        self.assertEqual(summary["raw_api_event_rows"], 8)
        self.assertEqual(summary["quote_attempt_rows"], 8)
        self.assertEqual(summary["execution_attempt_rows"], 0)
        self.assertLessEqual(
            summary["provider_calls"],
            caps["http_requests_total_max"],
        )
        self.assertLessEqual(
            summary["received_bytes"],
            caps["received_response_bytes_max"],
        )
        self.assertLessEqual(
            summary["stored_bytes"],
            caps["durable_raw_bytes_max"],
        )

    def test_all_exact_buy_and_reverse_sell_panels_are_bound(self) -> None:
        panels = self.fixture["panels"]
        self.assertEqual(
            [panel["usd_notional"] for panel in panels],
            [10, 25, 50, 100],
        )
        self.assertEqual(
            [panel["buy_input_usdc_atomic"] for panel in panels],
            [10_000_000, 25_000_000, 50_000_000, 100_000_000],
        )
        for panel in panels:
            self.assertTrue(panel["exact_reverse_input_match"])
            self.assertEqual(
                panel["sell_input_token_atomic"],
                panel["buy_output_token_atomic"],
            )
            self.assertGreater(panel["buy_route_count"], 0)
            self.assertGreater(panel["sell_route_count"], 0)
            self.assertRegex(panel["buy_route_id"], SHA256_RE)
            self.assertRegex(panel["sell_route_id"], SHA256_RE)

    def test_quote_only_round_trip_deterioration_is_exact(self) -> None:
        panels = self.fixture["panels"]
        deltas = [
            Decimal(panel["quote_round_trip_delta_bps"])
            for panel in panels
        ]
        self.assertEqual(
            deltas,
            [
                Decimal("-342.166000"),
                Decimal("-480.533200"),
                Decimal("-704.926400"),
                Decimal("-1118.882100"),
            ],
        )
        self.assertEqual(deltas, sorted(deltas, reverse=True))
        for panel in panels:
            expected_ratio = (
                Decimal(panel["sell_output_usdc_atomic"])
                / Decimal(panel["buy_input_usdc_atomic"])
            )
            self.assertEqual(
                Decimal(panel["quote_round_trip_ratio"]),
                expected_ratio,
            )
            self.assertEqual(
                panel["quote_round_trip_delta_usdc_atomic"],
                panel["sell_output_usdc_atomic"]
                - panel["buy_input_usdc_atomic"],
            )

    def test_pit_pacing_latency_and_context_observability_pass(self) -> None:
        observed = self.fixture["observability"]
        self.assertTrue(observed["pit_timestamp_ordering_pass"])
        self.assertTrue(observed["context_slots_strictly_increasing"])
        self.assertTrue(observed["quote_age_ms_all_zero"])
        self.assertGreaterEqual(
            observed["minimum_request_gap_seconds"],
            self.fixture["frozen_caps"]["minimum_interval_seconds"],
        )
        self.assertLessEqual(
            observed["provider_latency_ms_min"],
            observed["provider_latency_ms_median"],
        )
        self.assertLessEqual(
            observed["provider_latency_ms_median"],
            observed["provider_latency_ms_max"],
        )

    def test_fee_null_policy_and_forbidden_payload_boundary_hold(self) -> None:
        accounting = self.fixture["schema_and_accounting"]
        self.assertEqual(
            accounting["transaction_or_instruction_payload_occurrences"],
            0,
        )
        for field in (
            "provider_fee_atomic_nonnull_rows",
            "platform_fee_atomic_nonnull_rows",
            "fee_mint_nonnull_rows",
            "included_in_output_amount_nonnull_rows",
        ):
            self.assertEqual(accounting[field], 0)
        self.assertFalse(accounting["out_amount_subtracted_again"])
        self.assertFalse(accounting["slippage_limit_counted_as_cost"])

    def test_quote_availability_does_not_promote_fill_or_net_claims(
        self,
    ) -> None:
        boundary = self.fixture["decision_boundary"]
        self.assertTrue(
            boundary[
                "legacy_quote_compatibility_established_for_bounded_panel"
            ]
        )
        self.assertTrue(boundary["all_buy_panels_quote_available"])
        self.assertTrue(
            boundary["all_exact_reverse_sell_panels_quote_available"]
        )
        for claim in (
            "no_route_observed",
            "fillable_established",
            "realized_vwap_established",
            "net_return_established",
            "path_risk_established",
            "canonical_done_implied",
        ):
            self.assertFalse(boundary[claim], claim)

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
        self.assertIn("t10a6-20260728T015829Z", self.summary)
        self.assertIn(
            "0648390ba3af49bacf804aafb7cc4788fbbb7040508cfef79f88c3d1ed188d1b",
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
            "FIXTURE-T10-JUPITER-QUOTE-PILOT-PLAN-002",
            "DATA-T10-JUPITER-QUOTE-PILOT-RAW-002",
            "DATA-T10-JUPITER-QUOTE-PROJECTION-002",
            "FIXTURE-T10-JUPITER-QUOTE-LIVE-EVIDENCE-002",
            "EVIDENCE-T10-JUPITER-QUOTE-RECEIPT-002",
            "EVIDENCE-T10-JUPITER-QUOTE-SUMMARY-002",
            "TEST-T10-JUPITER-QUOTE-EVIDENCE-002",
        }
        self.assertGreaterEqual(
            tuple(int(part) for part in manifest["catalog_version"].split(".")),
            (0, 13, 0),
        )
        self.assertTrue(expected.issubset(records))
        self.assertTrue(
            expected.issubset(set(manifest["mandatory_asset_ids"]))
        )
        for asset_id in (
            "DATA-T10-JUPITER-QUOTE-PILOT-RAW-002",
            "DATA-T10-JUPITER-QUOTE-PROJECTION-002",
        ):
            asset = records[asset_id]
            self.assertEqual(asset["location"]["kind"], "logical_only")
            self.assertNotIn("repository_path", asset["location"])

    def test_authority_receipt_has_zero_sensitive_actions(self) -> None:
        authority = self.receipt["authority"]
        self.assertEqual(authority["external_provider_calls"], 8)
        self.assertEqual(authority["external_retries"], 0)
        self.assertEqual(authority["network_calls_during_acceptance"], 0)
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
