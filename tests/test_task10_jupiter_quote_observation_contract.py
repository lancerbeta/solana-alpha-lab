from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import QuoteAttempt  # noqa: E402

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task10"
    / "jupiter_quote_observation_contract_v1.json"
)
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "jupiter_quote_observation_contract_v1.md"
)
EXPECTED_FIXTURE_SHA256 = (
    "097ffed63c5a6950403966325c79f8c514f800cbbc2766eb8528c77e30db87aa"
)
EXPECTED_MANAGED_FILES = [
    "docs/contracts/jupiter_quote_observation_contract_v1.md",
    "tests/fixtures/task10/jupiter_quote_observation_contract_v1.json",
    "tests/test_task10_jupiter_quote_observation_contract.py",
    "catalog/assets/core.yaml",
    "catalog/assets/lifecycle.yaml",
    "catalog/catalog_manifest.yaml",
    "catalog/generated/asset_edges.json",
    "docs/PROJECT_MAP.md",
    "tests/test_catalog.py",
    "tests/test_baton_repository_policy.py",
]
EXPECTED_STATES = {
    "QUOTE_AVAILABLE",
    "NO_ROUTE",
    "PROVIDER_ERROR",
    "INVALID_RESPONSE",
    "TIMEOUT",
}


class Task10JupiterQuoteObservationContractTests(unittest.TestCase):
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
            "solana_alpha_lab.jupiter_quote_observation_contract",
        )
        self.assertEqual(self.document["task_id"], "TASK-10")
        self.assertEqual(self.document["atom_id"], "T10-A2")
        self.assertEqual(self.document["entry_verdict"], "START_WITH_PATCH")
        self.assertEqual(
            self.document["authority"]["managed_files"],
            EXPECTED_MANAGED_FILES,
        )

    def test_current_v2_is_blocked_and_legacy_surface_is_compatibility_only(
        self,
    ) -> None:
        decision = self.document["provider_surface_decision"]
        current = decision["current_v2"]
        self.assertTrue(current["order_returns_assembled_transaction"])
        self.assertTrue(current["order_taker_coupled"])
        self.assertTrue(current["build_returns_transaction_instructions"])
        self.assertFalse(current["eligible_for_first_quote_only_pilot"])
        candidate = decision["compatibility_candidate"]
        self.assertEqual(candidate["method"], "GET")
        self.assertEqual(candidate["path"], "/swap/v1/quote")
        self.assertEqual(
            candidate["maintenance_status"],
            "LEGACY_NOT_ACTIVELY_MAINTAINED",
        )
        self.assertFalse(candidate["current_production_path_proven"])
        self.assertFalse(decision["automatic_fallback_to_v2"])

    def test_buy_panels_use_exact_usdc_atomics_and_sell_uses_buy_output(
        self,
    ) -> None:
        panels = self.document["quote_panels"]
        self.assertEqual(panels["input_quote_decimals"], 6)
        self.assertEqual(
            [(row["usd"], row["buy_input_atomic"]) for row in panels["notionals"]],
            [
                (10, 10_000_000),
                (25, 25_000_000),
                (50, 50_000_000),
                (100, 100_000_000),
            ],
        )
        self.assertEqual(
            panels["sell_input_rule"],
            "EXACT_BUY_OUTPUT_QUOTED_ATOMIC",
        )
        self.assertTrue(panels["float_arithmetic_forbidden"])
        self.assertEqual(
            panels["sell_after_unavailable_buy"],
            "NOT_ATTEMPTED_BUY_PREREQUISITE_FAILED",
        )

    def test_terminal_states_preserve_missing_no_route_and_failure_distinctions(
        self,
    ) -> None:
        self.assertEqual(set(self.document["terminal_states"]), EXPECTED_STATES)
        invariants = self.document["state_invariants"]
        self.assertFalse(invariants["missing_is_zero"])
        self.assertFalse(invariants["provider_failure_is_no_route"])
        self.assertFalse(invariants["timeout_is_no_route"])
        self.assertFalse(invariants["stale_is_quote_available"])
        self.assertFalse(invariants["unavailable_buy_creates_sell_attempt"])
        self.assertEqual(invariants["retry_count"], 0)

    def test_existing_quote_attempt_model_accepts_all_five_state_examples(
        self,
    ) -> None:
        rows = [
            QuoteAttempt.model_validate_json(json.dumps(row))
            for row in self.document["quote_attempt_projection_examples"]
        ]
        self.assertEqual({row.status for row in rows}, EXPECTED_STATES)
        by_status = {row.status: row for row in rows}
        self.assertGreater(by_status["QUOTE_AVAILABLE"].route_count or 0, 0)
        self.assertEqual(by_status["NO_ROUTE"].route_count, 0)
        self.assertIsNone(by_status["TIMEOUT"].response_at)
        self.assertEqual(
            by_status["PROVIDER_ERROR"].error_class,
            "HTTP_5XX",
        )
        self.assertEqual(
            by_status["INVALID_RESPONSE"].error_class,
            "TRANSACTION_PAYLOAD_FORBIDDEN",
        )

    def test_provider_error_cannot_be_relabelled_no_route(self) -> None:
        provider_error = copy.deepcopy(
            self.document["quote_attempt_projection_examples"][2]
        )
        provider_error["status"] = "NO_ROUTE"
        provider_error["error_class"] = "HTTP_5XX"
        provider_error["route_count"] = 0
        with self.assertRaisesRegex(
            ValidationError,
            "no_route_state_incoherent",
        ):
            QuoteAttempt.model_validate_json(json.dumps(provider_error))

    def test_missing_output_cannot_be_relabelled_available(self) -> None:
        no_route = copy.deepcopy(
            self.document["quote_attempt_projection_examples"][1]
        )
        no_route["status"] = "QUOTE_AVAILABLE"
        with self.assertRaisesRegex(
            ValidationError,
            "quote_available_state_incoherent",
        ):
            QuoteAttempt.model_validate_json(json.dumps(no_route))

    def test_timestamp_mapping_and_pit_order_are_frozen(self) -> None:
        mapping = self.document["timestamp_mapping"]
        self.assertEqual(mapping["event_at"], "requested_at")
        self.assertEqual(mapping["observed_at"], "response_at")
        self.assertEqual(
            mapping["available_at"],
            "available_to_strategy_at",
        )
        for row in self.document["quote_attempt_projection_examples"]:
            requested = datetime.fromisoformat(
                row["requested_at"].replace("Z", "+00:00")
            )
            first = datetime.fromisoformat(
                row["first_reliable_available_at"].replace("Z", "+00:00")
            )
            available = datetime.fromisoformat(
                row["available_to_strategy_at"].replace("Z", "+00:00")
            )
            ingested = datetime.fromisoformat(
                row["ingested_at"].replace("Z", "+00:00")
            )
            self.assertLessEqual(requested, first)
            self.assertLessEqual(first, available)
            self.assertLessEqual(available, ingested)
            if row["response_at"] is not None:
                response = datetime.fromisoformat(
                    row["response_at"].replace("Z", "+00:00")
                )
                self.assertLessEqual(requested, response)
                self.assertLessEqual(response, first)

    def test_fee_and_price_impact_policy_prevents_double_counting(self) -> None:
        policy = self.document["fee_accounting"]
        self.assertTrue(policy["provider_out_amount_stored_exactly"])
        self.assertFalse(policy["embedded_economics_subtracted_again"])
        self.assertFalse(policy["price_impact_subtracted_again"])
        self.assertFalse(policy["slippage_limit_is_realized_cost"])
        self.assertEqual(
            set(policy["unknown_fee_projection"].values()),
            {None, "PROVIDER_ROUTE_FEE_DETAIL_RAW_ONLY"},
        )

    def test_execution_relation_and_transaction_actions_remain_forbidden(
        self,
    ) -> None:
        mapping = self.document["schema_mapping"]
        execution = mapping["execution_attempts"]
        self.assertEqual(execution["task10_atom2_mode"], "FORBIDDEN")
        self.assertEqual(execution["quote_only_pilot_mode"], "FORBIDDEN")
        self.assertFalse(
            self.document["raw_boundary"][
                "transaction_decode_construct_simulate_sign_send"
            ]
        )
        self.assertFalse(
            mapping["task09_touch"]["fillable_inference_forbidden"] is False
        )
        self.assertTrue(mapping["task09_touch"]["no_route_inference_forbidden"])

    def test_future_external_caps_are_exact_and_still_unauthorized(self) -> None:
        caps = self.document["future_external_caps"]
        self.assertEqual(caps["http_requests_total_max"], 8)
        self.assertEqual(
            caps["buy_requests"] + caps["dependent_sell_requests_max"],
            caps["http_requests_total_max"],
        )
        self.assertEqual(caps["concurrency"], 1)
        self.assertEqual(caps["retries"], 0)
        self.assertEqual(caps["wall_seconds_max"], 600)
        self.assertEqual(caps["cash_spend_usd_cents"], 0)
        self.assertEqual(caps["wallet_signer_transaction_actions"], 0)
        authority = self.document["authority"]
        self.assertFalse(authority["network"])
        self.assertEqual(authority["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(authority["raw_data_writes"], 0)

    def test_atom2_has_no_dependency_git_publication_or_ui_authority(self) -> None:
        authority = self.document["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(authority["dependency_changes"], 0)
        self.assertFalse(authority["credential_use"])
        self.assertEqual(authority["cash_spend_usd_cents"], 0)
        for field in ("commit", "push", "pull_request", "merge", "ui_changes"):
            with self.subTest(field=field):
                self.assertFalse(authority[field])
        self.assertFalse(
            self.document["next_atom"]["external_calls_authorized"]
        )

    def test_contract_records_required_nonclaims_and_stable_ids(self) -> None:
        for marker in (
            "START_WITH_PATCH",
            "LEGACY_QUOTE_COMPATIBILITY_ONLY",
            "`QUOTE_AVAILABLE`",
            "`NO_ROUTE`",
            "`PROVIDER_ERROR`",
            "`INVALID_RESPONSE`",
            "`TIMEOUT`",
            "missing is not zero",
            "CONTRACT-T10-JUPITER-QUOTE-OBSERVATION-001",
            "SCHEMA-T05-REL-QUOTE-ATTEMPTS-001",
            "SCHEMA-T05-REL-EXECUTION-ATTEMPTS-001",
            "USD 0",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)

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
