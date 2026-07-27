from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import (  # noqa: E402
    CanonicalObservation,
    PoolStateSnapshot,
    TradeOrderflowInput,
)

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task09"
    / "pumpswap_touch_observation_contract_v1.json"
)
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "pumpswap_touch_observation_contract_v1.md"
)
EXPECTED_FIXTURE_SHA256 = (
    "6d6100c6a228c263dee09839fb7e08d0f79f6e7d1be184e7ad99be06f0781a5b"
)
EXPECTED_MANAGED_FILES = [
    "docs/contracts/pumpswap_touch_observation_contract_v1.md",
    "tests/fixtures/task09/pumpswap_touch_observation_contract_v1.json",
    "tests/test_task09_pumpswap_touch_observation_contract.py",
]
EXPECTED_UNIVERSES = [
    "PUMPSWAP_OBSERVED",
    "PUMP_MIGRATION_CONFIRMED",
    "CANONICAL_INDEX_CANDIDATE",
]
PUMPSWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"


class Task09PumpSwapTouchObservationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.document = json.loads(cls.fixture_bytes)
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")

    def test_fixture_hash_identity_and_authorized_inventory_are_exact(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            self.document["schema"],
            "solana_alpha_lab.pumpswap_touch_observation_contract",
        )
        self.assertEqual(self.document["task_id"], "TASK-09")
        self.assertEqual(self.document["atom_id"], "T09-A2")
        self.assertEqual(
            self.document["authority"]["managed_files"],
            EXPECTED_MANAGED_FILES,
        )
        self.assertEqual(
            self.document["authority"]["class"],
            "LOCAL_WRITE_AND_EXACT_STAGE_ONLY",
        )

    def test_touch_boundary_excludes_fill_route_and_execution_claims(self) -> None:
        estimand = self.document["estimand"]
        self.assertEqual(estimand["accepted_claim"], "TOUCH")
        self.assertEqual(
            set(estimand["forbidden_claims"]),
            {
                "FILLABLE",
                "NO_ROUTE",
                "EXECUTABLE_QUOTE",
                "REALIZED_VWAP",
                "NET_RETURN",
                "MIGRATION_FROM_POOL_OBSERVATION",
                "MIGRATION_FROM_INDEX_ZERO",
            },
        )
        touch = self.document["touch_semantics"]
        self.assertFalse(touch["observed_trade_is_our_fill"])
        self.assertFalse(touch["provider_failure_is_no_route"])
        self.assertEqual(
            touch["failed_transaction_disposition"],
            "TYPED_RAW_EVIDENCE_ONLY",
        )

    def test_universes_are_separate_and_migration_inference_fails_closed(
        self,
    ) -> None:
        universes = self.document["universes"]
        self.assertEqual(
            [universe["universe_id"] for universe in universes],
            EXPECTED_UNIVERSES,
        )
        by_id = {
            universe["universe_id"]: universe for universe in universes
        }
        self.assertFalse(by_id["PUMPSWAP_OBSERVED"]["proves_migration"])
        self.assertFalse(
            by_id["PUMP_MIGRATION_CONFIRMED"]["pool_observation_sufficient"]
        )
        self.assertFalse(
            by_id["PUMP_MIGRATION_CONFIRMED"]["index_zero_sufficient"]
        )
        self.assertTrue(
            by_id["CANONICAL_INDEX_CANDIDATE"]["candidate_only"]
        )
        relationship = self.document["universe_relationship"]
        self.assertTrue(relationship["labels_are_independent"])
        self.assertTrue(relationship["implicit_subset_claims_forbidden"])
        self.assertEqual(
            relationship["launch_universe"],
            "UNAVAILABLE_NOT_INFERRED",
        )

    def test_task08_coverage_blocker_does_not_authorize_retry(self) -> None:
        boundary = self.document["inherited_task08_boundary"]
        self.assertEqual(
            boundary["lifecycle_coverage_status"],
            "NOT_TESTABLE_IN_WINDOW",
        )
        self.assertEqual(boundary["retained_records"], 388)
        self.assertEqual(boundary["accepted_create_events"], 0)
        self.assertFalse(boundary["retry_authorized"])
        self.assertFalse(boundary["longer_pilot_authorized"])

    def test_protocol_requires_exact_future_idl_pin(self) -> None:
        protocol = self.document["protocol"]
        self.assertEqual(protocol["program_id"], PUMPSWAP_PROGRAM_ID)
        self.assertFalse(protocol["mutable_upstream_ref_is_decoder_pin"])
        self.assertEqual(
            protocol["exact_idl_blob_required_before_atom"],
            "T09-A3",
        )
        self.assertEqual(
            protocol["required_idl_subset"],
            [
                "Pool",
                "BuyEvent",
                "SellEvent",
                "NESTED_TYPES_REFERENCED_BY_REQUIRED_SUBSET",
            ],
        )

    def test_raw_virtual_and_effective_quote_reserves_remain_distinct(
        self,
    ) -> None:
        reserves = self.document["reserve_semantics"]
        self.assertTrue(
            reserves["virtual_quote_reserves"]["must_be_retained_separately"]
        )
        self.assertTrue(reserves["effective_must_not_replace_raw"])
        self.assertEqual(
            reserves["effective_quote_reserves_formula"],
            "RAW_QUOTE_VAULT_BALANCE_ATOMIC + "
            "VIRTUAL_QUOTE_RESERVES_ATOMIC",
        )
        for vector in reserves["test_vectors"]:
            effective = (
                vector["raw_quote_vault_balance_atomic"]
                + vector["virtual_quote_reserves_atomic"]
            )
            self.assertEqual(
                effective,
                vector["effective_quote_reserves_atomic"],
            )
            self.assertEqual(vector["canonicalizable"], effective >= 0)

    def test_schema_mapping_keeps_raw_quote_and_reserves_quotes_for_task10(
        self,
    ) -> None:
        mapping = self.document["schema_mapping"]
        self.assertEqual(
            mapping["pool_state_snapshots"][
                "quote_reserve_atomic_semantics"
            ],
            "RAW_QUOTE_VAULT_BALANCE_ATOMIC",
        )
        self.assertTrue(
            mapping["pool_state_snapshots"][
                "effective_reserve_substitution_forbidden"
            ]
        )
        self.assertEqual(mapping["quote_attempts"]["task09_mode"], "FORBIDDEN")
        self.assertEqual(
            mapping["quote_attempts"]["first_writer_for_route_evidence"],
            "TASK-10",
        )
        self.assertTrue(mapping["quote_attempts"]["no_route_forbidden"])
        self.assertEqual(
            mapping["token_lifecycle_events"]["task09_mode"],
            "READ_ONLY",
        )

    def test_existing_task05_models_accept_exact_projection_examples(
        self,
    ) -> None:
        examples = self.document["schema_projection_examples"]
        pool = PoolStateSnapshot.model_validate_json(
            json.dumps(examples["pool_state_snapshots"])
        )
        trade = TradeOrderflowInput.model_validate_json(
            json.dumps(examples["trade_orderflow_inputs"])
        )
        observations = [
            CanonicalObservation.model_validate_json(json.dumps(row))
            for row in examples["canonical_observations"]
        ]

        self.assertEqual(pool.quote_reserve_atomic, 4_000_000_000)
        self.assertEqual(trade.side, "BUY")
        self.assertIn("NOT_FILL", trade.quality_flags or "")
        self.assertEqual(
            [row.observation_type for row in observations],
            [
                "PUMPSWAP_VIRTUAL_QUOTE_RESERVES",
                "PUMPSWAP_EFFECTIVE_QUOTE_RESERVES",
            ],
        )
        self.assertIsNone(observations[0].value_atomic)
        self.assertEqual(observations[1].value_atomic, 4_000_000_000)

    def test_timestamp_order_and_mapping_are_point_in_time_safe(self) -> None:
        self.assertEqual(
            self.document["timestamps"],
            [
                "event_at",
                "observed_at",
                "first_reliable_available_at",
                "available_at",
                "ingested_at",
            ],
        )
        mapping = self.document["timestamp_mapping"]
        self.assertEqual(
            mapping["available_at"],
            "available_to_strategy_at",
        )
        examples = self.document["schema_projection_examples"]
        for relation in ("pool_state_snapshots", "trade_orderflow_inputs"):
            row = examples[relation]
            ordered = [
                datetime.fromisoformat(row["event_time"].replace("Z", "+00:00")),
                datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00")),
                datetime.fromisoformat(
                    row["first_reliable_available_at"].replace("Z", "+00:00")
                ),
                datetime.fromisoformat(
                    row["available_to_strategy_at"].replace("Z", "+00:00")
                ),
                datetime.fromisoformat(row["ingested_at"].replace("Z", "+00:00")),
            ]
            self.assertEqual(ordered, sorted(ordered))

    def test_primary_transport_is_standard_and_fallback_is_disabled(self) -> None:
        roles = self.document["provider_roles"]
        primary = roles["SOLANA_STANDARD_WSS_PRIMARY"]
        self.assertEqual(primary["method"], "logsSubscribe")
        self.assertEqual(primary["mentions"], [PUMPSWAP_PROGRAM_ID])
        self.assertEqual(primary["commitment"], "confirmed")
        self.assertEqual(primary["followup_method"], "getTransaction")
        fallback = roles[
            "HELIUS_TRANSACTION_SUBSCRIBE_CONDITIONAL_FALLBACK"
        ]
        self.assertFalse(fallback["enabled_for_first_probe"])
        self.assertEqual(fallback["minimum_documented_plan"], "DEVELOPER")
        self.assertFalse(fallback["purchase_or_upgrade_authorized"])

    def test_cheapest_falsifier_credit_math_and_caps_are_exact(self) -> None:
        budget = self.document["cheapest_falsifier"]
        credits = (
            math.ceil(budget["uncompressed_stream_bytes"] / 100_000) * 2
            + budget["get_transaction_followups"]
            + budget["wss_connections"]
        )
        self.assertEqual(credits, 39)
        self.assertEqual(credits, budget["modeled_helius_credits"])
        self.assertLessEqual(credits, budget["helius_credit_cap"])
        self.assertEqual(budget["concurrency"], 1)
        self.assertEqual(budget["retries"], 0)
        self.assertEqual(budget["cash_spend_usd_cents"], 0)
        self.assertFalse(budget["extension_or_retry_authorized"])
        self.assertEqual(
            budget["no_event_disposition"],
            "NOT_TESTABLE_IN_WINDOW",
        )

    def test_atom2_has_no_external_or_git_publication_authority(self) -> None:
        authority = self.document["authority"]
        self.assertFalse(authority["network_after_git_fetch"])
        self.assertEqual(authority["dependency_changes"], 0)
        self.assertEqual(authority["provider_api_rpc_wss_calls"], 0)
        self.assertFalse(authority["credential_use"])
        self.assertEqual(authority["cash_spend_usd_cents"], 0)
        for field in ("commit", "push", "pull_request", "merge"):
            with self.subTest(field=field):
                self.assertFalse(authority[field])

    def test_contract_records_required_nonclaims_and_catalog_gap(self) -> None:
        for marker in (
            "Touch",
            "PUMPSWAP_OBSERVED",
            "PUMP_MIGRATION_CONFIRMED",
            "CANONICAL_INDEX_CANDIDATE",
            "virtual_quote_reserves",
            "`quote_attempts`",
            "NOT_TESTABLE_IN_WINDOW",
            "CATALOG_GAP_PENDING_T09_RECONCILIATION",
            "USD 0",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)
        self.assertEqual(
            self.document["catalog"]["status"],
            "CATALOG_GAP_PENDING_T09_RECONCILIATION",
        )

    def test_artifacts_contain_no_secret_or_machine_path(self) -> None:
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
