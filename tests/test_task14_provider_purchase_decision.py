from __future__ import annotations

import hashlib
import json
import re
import unittest
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = ROOT / "docs" / "decisions" / "provider_decision_v2.md"
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task14"
    / "provider_purchase_decision_v1.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task14"
    / "provider_purchase_decision_acceptance_receipt_v1.json"
)
EXPECTED_FIXTURE_SHA256 = (
    "572243a331b75a3723893e4fe24730c15af6dc7a77d7f0bfa2c96e968291eee1"
)
EXPECTED_DECISION_SHA256 = (
    "39dbf21501f950e0365b04668f10387d43cae2db66a997159b0061998c09fc41"
)
EXPECTED_RECEIPT_SHA256 = (
    "47d950c863822bcfa72ade4172d1b834f029ac1198e05af6986939c2de94eb9e"
)
TASK14_ASSET_IDS = {
    "DECISION-T14-PROVIDER-PURCHASE-001",
    "FIXTURE-T14-PROVIDER-PURCHASE-DECISION-001",
    "TEST-T14-PROVIDER-PURCHASE-DECISION-001",
    "EVIDENCE-T14-PROVIDER-PURCHASE-ACCEPTANCE-001",
}

EVIDENCE_PATHS = {
    "EVIDENCE-T07-PROVIDER-SMOKE-RECEIPT-001": (
        "docs/evidence/task07/provider_smoke_execution_receipt_v1.json",
        "900cf054916995e2b839fad3bf4873666bcd9ca635903d1a58937b346de27786",
    ),
    "EVIDENCE-T08-LIFECYCLE-DISCOVERY-RECEIPT-001": (
        "docs/evidence/task08/lifecycle_discovery_probe_execution_receipt_v1.json",
        "33a3f0b90de36c1543ee605eccc07685798f1b2e08ee6a5f494345d5cb19df40",
    ),
    "EVIDENCE-T10-JUPITER-QUOTE-RECEIPT-002": (
        "docs/evidence/task10/jupiter_quote_logger_execution_receipt_v2.json",
        "01c6392d38ab4fd8c67bead42a9a5013d2c82206a706cb50e9aac523560490ec",
    ),
    "EVIDENCE-T11-ENTITY-INPUT-RECEIPT-001": (
        "docs/evidence/task11/entity_input_pilot_execution_receipt_v1.json",
        "324c9ace8c49668864c274de19c09d42a7e794169f9a5ad619df8b47f3209ff4",
    ),
    "EVIDENCE-T13-PILOT-AUDIT-OFFLINE-ACCEPTANCE-001": (
        "docs/evidence/task13/pilot_audit_offline_acceptance_receipt_v1.json",
        "d932512f861736944cbca3d184528dae0366afbfdb45e185f44ba245c85f752d",
    ),
}


class Task14ProviderPurchaseDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.fixture = json.loads(cls.fixture_bytes)
        cls.decision_bytes = DECISION_PATH.read_bytes()
        cls.decision = cls.decision_bytes.decode("utf-8")
        cls.receipt_bytes = RECEIPT_PATH.read_bytes()
        cls.receipt = json.loads(cls.receipt_bytes)

    def test_fixture_identity_is_frozen(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            self.fixture["decision_id"],
            "DEC-T14-PROVIDER-PURCHASE-001",
        )
        self.assertEqual(self.fixture["decision_version"], "2.0")
        self.assertEqual(
            self.fixture["atom_id"],
            "T14-A2_FROZEN_DEFERRED_PURCHASE_DECISION_V1",
        )

    def test_defer_is_the_only_decision_valid_alternative(self) -> None:
        self.assertEqual(self.fixture["status"], "DEFER")
        self.assertEqual(
            self.fixture["accepted_claim"],
            "PROVIDER_PURCHASE_DECISION_REQUIRES_BOUNDED_USAGE_MEASUREMENT",
        )
        self.assertEqual(self.fixture["entry_verdict"], "START_AS_WRITTEN")
        alternatives = self.fixture["alternatives"]
        self.assertFalse(alternatives["NO_PURCHASE"]["decision_valid"])
        self.assertTrue(alternatives["DEFER"]["decision_valid"])
        self.assertFalse(
            alternatives["PROPOSE_BOUNDED_PURCHASE"]["decision_valid"]
        )
        self.assertEqual(
            self.fixture["next_atom"],
            "T14-A3_DETERMINISTIC_DEFER_ACCEPTANCE_V1",
        )

    def test_local_evidence_fingerprints_match_repository_bytes(self) -> None:
        observed = {
            item["asset_id"]: item["sha256"]
            for item in self.fixture["local_evidence"]
        }
        self.assertEqual(
            observed,
            {
                asset_id: expected
                for asset_id, (_, expected) in EVIDENCE_PATHS.items()
            },
        )
        for asset_id, (relative_path, expected) in EVIDENCE_PATHS.items():
            with self.subTest(asset_id=asset_id):
                actual = hashlib.sha256((ROOT / relative_path).read_bytes())
                self.assertEqual(actual.hexdigest(), expected)

    def test_helius_sensitivity_reproduces_without_becoming_a_forecast(
        self,
    ) -> None:
        estimate = self.fixture["directional_helius_capacity_estimate"]
        stream_bytes = Decimal(estimate["stream_bytes"])
        observed_seconds = Decimal(estimate["observed_seconds"])
        meter_credits = Decimal(estimate["meter_credits"])
        meter_bytes = Decimal(estimate["meter_decimal_bytes"])

        for days in (1, 7, 30):
            seconds = Decimal(days * 86_400)
            sensitivity_bytes = stream_bytes / observed_seconds * seconds
            sensitivity_credits = (
                sensitivity_bytes / meter_bytes
            ).to_integral_value(rounding=ROUND_CEILING) * meter_credits + 1
            with self.subTest(days=days):
                self.assertEqual(
                    sensitivity_bytes.to_integral_value(
                        rounding=ROUND_CEILING
                    ),
                    Decimal(estimate[f"sensitivity_{days}d_bytes"]),
                )
                self.assertEqual(
                    sensitivity_credits,
                    Decimal(estimate[f"sensitivity_{days}d_credits"]),
                )

        self.assertEqual(
            Decimal(estimate["free_monthly_credits"])
            - Decimal(estimate["sensitivity_7d_credits"]),
            Decimal(estimate["sensitivity_7d_free_headroom_credits"]),
        )
        self.assertEqual(
            estimate["sensitivity_30d_free_tier_multiple"],
            "4.445193",
        )
        self.assertEqual(
            estimate["confidence"],
            "NON_DECISION_VALID_SENSITIVITY_ONLY",
        )
        self.assertFalse(estimate["purchase_trigger"])

    def test_official_snapshot_is_dated_scoped_and_fail_closed(self) -> None:
        self.assertEqual(self.fixture["as_of"], "2026-07-29")
        self.assertEqual(self.fixture["pricing_snapshot_ttl_days"], 30)
        self.assertEqual(
            self.fixture["reconsideration_gate"]["pricing_snapshot_expiry"],
            "2026-08-28",
        )
        self.assertEqual(len(self.fixture["official_snapshot"]), 5)

        allowed_hosts = {
            "www.helius.dev",
            "docs.solanatracker.io",
            "developers.jup.ag",
            "docs.birdeye.so",
        }
        for provider in self.fixture["official_snapshot"]:
            self.assertTrue(provider["official_sources"])
            for source in provider["official_sources"]:
                parsed = urlparse(source)
                self.assertEqual(parsed.scheme, "https")
                self.assertIn(parsed.hostname, allowed_hosts)

        cancellation = {
            provider["provider"]: provider["cancellation"][
                "public_terms_complete_for_reference"
            ]
            for provider in self.fixture["official_snapshot"]
        }
        self.assertEqual(
            cancellation,
            {
                "HELIUS": True,
                "SOLANA_TRACKER": False,
                "JUPITER": False,
                "BIRDEYE": False,
                "RAPTOR": False,
            },
        )

    def test_reconsideration_requires_every_frozen_condition(self) -> None:
        gate = self.fixture["reconsideration_gate"]
        self.assertEqual(
            gate["all_conditions_required"],
            [
                "NAMED_CONSUMER_BLOCKED_BY_EXACT_PROVIDER_LIMIT",
                "DECISION_VALID_BOUNDED_MEASUREMENT",
                "FREE_OR_CHEAPER_PATH_FALSIFIED",
                "CURRENT_CHECKOUT_AND_CANCELLATION_READBACK",
                "OWNER_APPROVED_EXACT_PLAN_AND_CASH_CAP",
            ],
        )
        self.assertEqual(gate["default_before_all_conditions"], "DEFER")

    def test_observation_universe_is_watchlist_scoped(self) -> None:
        direction = self.fixture["observation_universe_direction"]
        self.assertEqual(
            direction["status"],
            "FROZEN_DOWNSTREAM_BOUNDARY_NOT_IMPLEMENTED",
        )
        self.assertEqual(
            direction["detailed_observation_layer"],
            "VERSIONED_WATCHLIST_MEMBERS_ONLY",
        )
        self.assertEqual(
            direction["policy_evolution"],
            "FORWARD_ONLY_NO_HISTORICAL_REWRITE",
        )
        self.assertEqual(
            direction["downstream_owners"],
            ["TASK-15", "TASK-17"],
        )
        self.assertIn("hypothesis_ids", direction["watchlist_membership_fields"])
        self.assertIn("ALL_SOLANA_TOKEN_TICKS", direction["excluded"])
        self.assertIn("ULTRA_LOW_LATENCY_HFT", direction["excluded"])

    def test_atom_has_zero_external_and_money_authority(self) -> None:
        self.assertEqual(
            self.fixture["authority"],
            {
                "network_calls_in_atom": 0,
                "provider_api_rpc_wss_calls_in_atom": 0,
                "account_or_dashboard_actions": 0,
                "credential_use": 0,
                "dependency_changes": 0,
                "cash_spend_usd": 0,
                "wallet_signer_transaction_actions": 0,
            },
        )

    def test_acceptance_receipt_binds_defer_and_zero_effects(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.decision_bytes).hexdigest(),
            EXPECTED_DECISION_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(self.receipt_bytes).hexdigest(),
            EXPECTED_RECEIPT_SHA256,
        )
        self.assertEqual(self.receipt["verdict"], "PASS")
        self.assertEqual(
            self.receipt["accepted_decision"],
            {
                "asset_id": "DECISION-T14-PROVIDER-PURCHASE-001",
                "decision_id": "DEC-T14-PROVIDER-PURCHASE-001",
                "decision_version": "2.0",
                "status": "DEFER",
                "accepted_claim": (
                    "PROVIDER_PURCHASE_DECISION_REQUIRES_"
                    "BOUNDED_USAGE_MEASUREMENT"
                ),
                "repository_path": (
                    "docs/decisions/provider_decision_v2.md"
                ),
                "sha256": EXPECTED_DECISION_SHA256,
            },
        )
        self.assertEqual(
            self.receipt["frozen_fixture"]["sha256"],
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            self.receipt["acceptance"]["detailed_observation_layer"],
            "VERSIONED_WATCHLIST_MEMBERS_ONLY",
        )
        self.assertEqual(
            self.receipt["acceptance"]["watchlist_policy_evolution"],
            "FORWARD_ONLY_NO_HISTORICAL_REWRITE",
        )
        self.assertFalse(
            self.receipt["acceptance"]["all_solana_token_ticks_authorized"]
        )
        self.assertTrue(
            all(value == 0 for value in self.receipt["authority"].values())
        )
        self.assertEqual(
            self.receipt["next_atom"],
            "T14-A4_REPOSITORY_DELIVERY_V1",
        )

    def test_catalog_registration_is_exact(self) -> None:
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
        self.assertEqual(manifest["catalog_version"], "0.17.0")
        self.assertEqual(len(records), 266)
        self.assertTrue(TASK14_ASSET_IDS.issubset(records))
        self.assertTrue(
            TASK14_ASSET_IDS.issubset(
                set(manifest["mandatory_asset_ids"])
            )
        )
        catalog = self.receipt["catalog"]
        self.assertEqual(
            (
                catalog["catalog_version"],
                catalog["assets"],
                catalog["shards"],
                catalog["schemas"],
                catalog["queries"],
            ),
            ("0.17.0", 266, 4, 4, 7),
        )

    def test_decision_document_preserves_scope_and_hygiene(self) -> None:
        self.assertFalse(self.decision_bytes.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", self.decision_bytes)
        self.assertTrue(self.decision_bytes.endswith(b"\n"))
        self.assertTrue(
            all(
                line.rstrip(" \t") == line
                for line in self.decision.splitlines()
            )
        )
        self.assertIn("`DEFER`", self.decision)
        self.assertIn(
            "`NON_DECISION_VALID_SENSITIVITY_ONLY`",
            self.decision,
        )
        self.assertIn("cash cap USD 0", self.decision)
        self.assertIn(
            "T14-A3_DETERMINISTIC_DEFER_ACCEPTANCE_V1",
            self.decision,
        )
        self.assertIn("versioned watchlist", self.decision)
        self.assertIsNone(re.search(r"(?i)\b[a-z]:[\\/]", self.decision))

        forbidden = (
            "api_key=",
            "authorization:",
            "private key",
            "seed phrase",
            "recovery phrase",
        )
        lowered = self.decision.lower()
        self.assertFalse(any(token in lowered for token in forbidden))

        self.assertFalse(self.receipt_bytes.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", self.receipt_bytes)
        self.assertTrue(self.receipt_bytes.endswith(b"\n"))
        receipt_text = self.receipt_bytes.decode("utf-8")
        self.assertTrue(
            all(
                line.rstrip(" \t") == line
                for line in receipt_text.splitlines()
            )
        )
        self.assertIsNone(re.search(r"(?i)\b[a-z]:[\\/]", receipt_text))
        lowered_receipt = receipt_text.lower()
        self.assertFalse(
            any(token in lowered_receipt for token in forbidden)
        )


if __name__ == "__main__":
    unittest.main()
