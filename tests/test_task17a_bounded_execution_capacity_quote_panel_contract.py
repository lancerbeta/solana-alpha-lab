from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from scripts import validate_catalog as catalog

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "bounded_execution_capacity_quote_panel_contract_v1.md"
)
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "bounded_execution_capacity_quote_panel_contract_v1.json"
)
TASK10_PLAN_PATH = (
    ROOT / "tests" / "fixtures" / "task10" / "jupiter_quote_pilot_plan_v2.json"
)
TASK17_MEMORY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17"
    / "first_bounded_hypothesis_cycle_v1.json"
)
TASK17_ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17"
    / "first_bounded_hypothesis_cycle_acceptance_v1.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task17ABoundedExecutionCapacityQuotePanelContractTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.task10_plan = json.loads(
            TASK10_PLAN_PATH.read_text(encoding="utf-8")
        )
        cls.task17_memory = json.loads(
            TASK17_MEMORY_PATH.read_text(encoding="utf-8")
        )
        cls.task17_acceptance = json.loads(
            TASK17_ACCEPTANCE_PATH.read_text(encoding="utf-8")
        )
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")

    def test_entry_gate_preserves_exact_hypothesis_and_data_need(self) -> None:
        gate = self.fixture["entry_gate"]
        hypothesis = self.fixture["hypothesis"]
        self.assertEqual(gate["verdict"], "START_WITH_PATCH")
        self.assertEqual(
            gate["historical_data_verdict"],
            "LIVE_NON_RECONSTRUCTABLE_NEED",
        )
        self.assertEqual(
            hypothesis["memory_sha256"],
            sha256(TASK17_MEMORY_PATH),
        )
        accepted = self.task17_acceptance["hypothesis_acceptance"]
        self.assertEqual(
            hypothesis["hypothesis_version_id"],
            accepted["hypothesis_version_id"],
        )
        self.assertEqual(
            hypothesis["definition_sha256"],
            accepted["definition_sha256"],
        )
        self.assertEqual(hypothesis["current_state"], "PAUSED")
        self.assertFalse(hypothesis["cross_token_generalization_authorized"])

    def test_watchlist_has_one_provenance_safe_member(self) -> None:
        watchlist = self.fixture["watchlist"]
        self.assertEqual(watchlist["current_member_count"], 1)
        self.assertEqual(watchlist["outer_member_ceiling"], 8)
        self.assertFalse(watchlist["unused_slots_authorize_discovery"])
        self.assertEqual(
            watchlist["membership_policy"],
            "FORWARD_ONLY_NEW_VERSION_REQUIRED",
        )
        member = watchlist["members"][0]
        selection = self.task10_plan["selection"]
        self.assertEqual(member["mint"], selection["mint"])
        self.assertEqual(member["decimals"], selection["decimals"])
        self.assertEqual(member["selection_rule"], selection["rule"])
        self.assertFalse(
            member["price_profitability_or_route_selection_used"]
        )

    def test_three_windows_are_foreground_and_temporally_distinct(self) -> None:
        windows = self.fixture["trigger_windows"]
        self.assertEqual(
            windows["window_ids"],
            [
                "T17A-WINDOW-01",
                "T17A-WINDOW-02",
                "T17A-WINDOW-03",
            ],
        )
        self.assertEqual(
            windows["trigger_kind"],
            "FOREGROUND_CONTROL_PLANE_INVOCATION",
        )
        self.assertFalse(windows["background_process"])
        self.assertFalse(windows["scheduler"])
        self.assertFalse(windows["always_on_collection"])
        self.assertGreaterEqual(windows["minimum_separation_seconds"], 1800)
        self.assertLessEqual(windows["total_span_seconds_max"], 86400)

    def test_current_panel_is_exact_24_call_pareto_slice(self) -> None:
        caps = self.fixture["caps"]
        calculated = (
            caps["current_members"]
            * caps["windows_per_member"]
            * caps["notionals_per_window"]
            * caps["legs_per_notional"]
        )
        self.assertEqual(calculated, 24)
        self.assertEqual(caps["provider_calls_current_max"], calculated)
        self.assertEqual(caps["outer_provider_call_ceiling"], 192)
        self.assertLess(
            caps["provider_calls_current_max"],
            caps["outer_provider_call_ceiling"],
        )
        self.assertEqual(caps["provider_calls_per_window_max"], 8)
        self.assertEqual(caps["concurrency"], 1)
        self.assertEqual(caps["retries"], 0)

    def test_provider_route_is_keyless_rate_limited_and_fail_closed(self) -> None:
        provider = self.fixture["provider_surface"]
        self.assertEqual(provider["provider"], "JUPITER_METIS")
        self.assertEqual(provider["method"], "GET")
        self.assertEqual(provider["path"], "/swap/v1/quote")
        self.assertEqual(
            provider["maintenance_status"],
            "SUPERSEDED_NOT_ACTIVELY_MAINTAINED",
        )
        self.assertTrue(provider["keyless_allowed"])
        self.assertEqual(provider["keyless_rate_limit_rps"], 0.5)
        self.assertGreaterEqual(provider["minimum_interval_seconds"], 2.0)
        self.assertEqual(provider["credentials"], 0)
        self.assertEqual(provider["accounts"], 0)
        self.assertEqual(provider["fallback_hosts"], [])
        self.assertFalse(provider["v2_fallback"])

    def test_buy_and_reverse_sell_semantics_reuse_task10(self) -> None:
        panel = self.fixture["panel"]
        task10_panel = self.task10_plan["panels"]
        self.assertEqual(
            panel["buy_input_usdc_atomic"],
            task10_panel["buy_input_atomic"],
        )
        self.assertEqual(
            panel["sell_input_rule"],
            "EXACT_ACCEPTED_BUY_OUT_AMOUNT_ATOMIC",
        )
        self.assertEqual(
            panel["sell_after_unavailable_buy"],
            "NOT_ATTEMPTED_BUY_PREREQUISITE_FAILED",
        )
        self.assertFalse(panel["float_or_decimal_rerounding"])
        self.assertEqual(
            set(self.fixture["terminal_classes"]),
            {
                "QUOTE_AVAILABLE",
                "NO_ROUTE",
                "PROVIDER_ERROR",
                "INVALID_RESPONSE",
                "TIMEOUT",
                "NOT_ATTEMPTED_BUY_PREREQUISITE_FAILED",
            },
        )

    def test_raw_identity_retention_and_usage_are_explicit(self) -> None:
        raw = self.fixture["raw_evidence"]
        retention = self.fixture["retention"]
        usage = self.fixture["usage_accounting"]
        self.assertFalse(raw["raw_bytes_in_git"])
        self.assertTrue(raw["tracked_fixtures_are_synthetic"])
        self.assertIn("window_id", raw["required_identity_fields"])
        self.assertIn("terminal_class", raw["required_observability_fields"])
        self.assertEqual(retention["policy_id"], "R1_T0_RAW")
        self.assertEqual(retention["raw_hot_days"], 90)
        self.assertFalse(retention["deletion_in_atom"])
        self.assertEqual(usage["authoritative_meter"], "EXACT_ATTEMPT_LEDGER")
        self.assertEqual(usage["modeled_credits_current_max"], 24)
        self.assertEqual(usage["cash_spend_usd_cents"], 0)

    def test_a2_has_zero_external_or_trading_authority(self) -> None:
        authority = self.fixture["authority"]
        self.assertTrue(authority["local_write"])
        self.assertFalse(authority["network"])
        self.assertEqual(authority["provider_api_rpc_wss_calls"], 0)
        self.assertFalse(authority["raw_live_write"])
        self.assertEqual(authority["dependency_changes"], 0)
        self.assertFalse(authority["credential_use"])
        self.assertEqual(authority["cash_spend_usd_cents"], 0)
        self.assertEqual(
            authority["wallet_signer_transaction_actions"],
            0,
        )
        self.assertTrue(
            authority["next_external_atom_separate_owner_gate_required"]
        )
        self.assertEqual(
            authority["next_external_atom_provider_calls_max"],
            24,
        )
        for forbidden_claim in (
            "authorizes no",
            "signal",
            "position",
            "NetReturn",
            "alpha claim",
        ):
            with self.subTest(forbidden_claim=forbidden_claim):
                self.assertIn(forbidden_claim, self.contract)

    def test_catalog_registers_exact_a2_assets(self) -> None:
        snapshot = catalog.load_and_validate()
        expected = {
            "CONTRACT-T17A-EXECUTION-CAPACITY-QUOTE-PANEL-001": CONTRACT_PATH,
            "FIXTURE-T17A-EXECUTION-CAPACITY-QUOTE-PANEL-001": FIXTURE_PATH,
            "TEST-T17A-EXECUTION-CAPACITY-QUOTE-PANEL-001": Path(__file__),
        }
        for asset_id, path in expected.items():
            with self.subTest(asset_id=asset_id):
                asset = snapshot.assets[asset_id]
                self.assertEqual(
                    asset["location"]["repository_path"],
                    path.relative_to(ROOT).as_posix(),
                )
                self.assertEqual(asset["integrity"]["sha256"], sha256(path))


if __name__ == "__main__":
    unittest.main()
