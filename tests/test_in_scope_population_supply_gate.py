from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.in_scope_population_fit_reconciliation import (
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
)
from solana_alpha_lab.in_scope_population_supply_gate import (
    ATOM_ID,
    INSTANT_EMPTY,
    LIVE_BLOCKED,
    SUPPLY_PASS,
    SupplyGateError,
    load_config,
    product_eligible,
    quote_native_recent_age_proof,
    reconcile,
    score_supply,
    sha256_file,
)


class InScopePopulationSupplyGateTests(unittest.TestCase):
    def test_factory_runner_unchanged(self) -> None:
        self.assertEqual(sha256_file(ROOT / FACTORY_RUNNER), FACTORY_RUNNER_SHA256)

    def test_instant_recent_without_launchpad_is_not_product_early(self) -> None:
        scored = score_supply(
            [
                {
                    "mint": "a",
                    "source_stratum": "RECENT",
                    "age_seconds": "40",
                    "launchpad": None,
                    "liquidity_usd": "5000",
                }
            ],
            early_n_min=12,
            seasoned_n_min=12,
            launchpad="pump.fun",
            liquidity_usd_min=Decimal("1000"),
            consumed=set(),
        )
        self.assertEqual(scored["early_n"], 0)
        self.assertEqual(scored["excluded_no_launchpad_n"], 1)

    def test_wait_age_pump_fun_with_liquidity_is_product_early(self) -> None:
        self.assertEqual(
            product_eligible(
                {
                    "mint": "b",
                    "age_seconds": "320",
                    "launchpad": "pump.fun",
                    "liquidity_usd": "1500",
                },
                launchpad="pump.fun",
                liquidity_usd_min=Decimal("1000"),
                consumed=set(),
            ),
            "EARLY",
        )

    def test_traded_without_launchpad_is_not_product_seasoned(self) -> None:
        scored = score_supply(
            [
                {
                    "mint": "c",
                    "source_stratum": "TRADED",
                    "age_seconds": "4000",
                    "launchpad": None,
                    "liquidity_usd": "8000",
                }
            ],
            early_n_min=1,
            seasoned_n_min=1,
            launchpad="pump.fun",
            liquidity_usd_min=Decimal("1000"),
            consumed=set(),
        )
        self.assertEqual(scored["seasoned_n"], 0)

    def test_traded_reclassified_pump_fun_can_be_product_seasoned(self) -> None:
        self.assertEqual(
            product_eligible(
                {
                    "mint": "d",
                    "source_stratum": "TRADED",
                    "age_seconds": "4000",
                    "launchpad": "pump.fun",
                    "liquidity_usd": "2000",
                },
                launchpad="pump.fun",
                liquidity_usd_min=Decimal("1000"),
                consumed=set(),
            ),
            "SEASONED",
        )

    def test_twelve_plus_twelve_passes(self) -> None:
        rows = [
            {
                "mint": f"e{i}",
                "age_seconds": "400",
                "launchpad": "pump.fun",
                "liquidity_usd": "2000",
            }
            for i in range(12)
        ] + [
            {
                "mint": f"s{i}",
                "age_seconds": "3600",
                "launchpad": "pump.fun",
                "liquidity_usd": "2000",
            }
            for i in range(12)
        ]
        scored = score_supply(
            rows,
            early_n_min=12,
            seasoned_n_min=12,
            launchpad="pump.fun",
            liquidity_usd_min=Decimal("1000"),
            consumed=set(),
        )
        self.assertTrue(scored["pass"])
        self.assertEqual(scored["terminal"], SUPPLY_PASS)

    def test_missing_liquidity_does_not_pass(self) -> None:
        self.assertIsNone(
            product_eligible(
                {
                    "mint": "e",
                    "age_seconds": "320",
                    "launchpad": "pump.fun",
                    "liquidity_usd": None,
                },
                launchpad="pump.fun",
                liquidity_usd_min=Decimal("1000"),
                consumed=set(),
            )
        )

    def test_pinned_git_replay_forbids_instant_recent_early(self) -> None:
        config = load_config(ROOT)
        runtime = reconcile(ROOT, config)
        self.assertEqual(runtime["atom_id"], ATOM_ID)
        self.assertEqual(runtime["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(runtime["decision"]["terminal"], INSTANT_EMPTY)
        self.assertEqual(runtime["decision"]["next"], LIVE_BLOCKED)
        self.assertFalse(runtime["decision"]["stage_b_in_this_write_set"])
        self.assertEqual(runtime["instant_recent_supply"]["early_n"], 0)
        self.assertLess(Decimal(runtime["instant_recent_supply"]["max_age_seconds"]), Decimal("300"))
        self.assertGreaterEqual(runtime["instant_recent_supply"]["quote_native_recent_campaigns"], 1)
        self.assertGreaterEqual(runtime["harvest"]["wait_ages_in_early_band_n"], 12)
        self.assertEqual(runtime["harvest"]["wait_product_early_n_with_liquidity"], 0)
        self.assertEqual(runtime["harvest"]["early"], "WAIT_THEN_SEARCH")
        self.assertFalse(runtime["live_capture"]["executed"])

    def test_quote_native_recent_early_band_fails_closed(self) -> None:
        with self.assertRaisesRegex(SupplyGateError, "QUOTE_NATIVE_RECENT_EARLY_NOT_EMPTY"):
            quote_native_recent_age_proof(
                {
                    "campaign_matrix": [
                        {
                            "kind": "quote_native",
                            "by_source_stratum": {
                                "RECENT": {
                                    "population_bands": {"EARLY": 1, "ULTRA_FRESH": 0},
                                    "age_seconds": {"max": "400"},
                                }
                            },
                        }
                    ]
                }
            )

    def test_non_finite_liquidity_is_not_product(self) -> None:
        self.assertIsNone(
            product_eligible(
                {
                    "mint": "inf",
                    "age_seconds": "320",
                    "launchpad": "pump.fun",
                    "liquidity_usd": "Infinity",
                },
                launchpad="pump.fun",
                liquidity_usd_min=Decimal("1000"),
                consumed=set(),
            )
        )


if __name__ == "__main__":
    unittest.main()
