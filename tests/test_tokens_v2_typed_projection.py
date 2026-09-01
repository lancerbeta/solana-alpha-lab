"""Tokens V2 typed projection unit tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_scheduler import _row_field  # noqa: E402
from solana_alpha_lab.factory.tokens_v2_typed_projection import (  # noqa: E402
    STATE_EXCLUDED,
    STATE_MISSING,
    STATE_OBSERVED,
    feature_families_from_typed_values,
    project_tokens_v2_field,
    project_tokens_v2_row,
    project_tokens_v2_scalar,
)


class TokensV2TypedProjectionTests(unittest.TestCase):
    def test_fixture_row_maps_core_and_activity_fields(self) -> None:
        row = {
            "id": "Mint111111111111111111111111111111111111111",
            "liquidity": 2800.0,
            "mcap": 2600.0,
            "usdPrice": 0.001,
            "firstPool": {"createdAt": "2026-08-24T00:19:15Z"},
            "stats5m": {"buyVolume": 100.0, "sellVolume": 50.0},
        }
        typed = {item["field_id"]: item for item in project_tokens_v2_row(row)}
        self.assertEqual(typed["FIELD-USD-PRICE-001"]["state"], STATE_OBSERVED)
        self.assertEqual(typed["FIELD-USD-PRICE-001"]["typed_value_or_null"], 0.001)
        self.assertEqual(typed["FIELD-MARKET-CAP-USD-001"]["typed_value_or_null"], 2600.0)
        self.assertEqual(typed["FIELD-STATS5M-BUY-VOLUME-001"]["typed_value_or_null"], 100.0)
        self.assertEqual(typed["FIELD-R0-TAKER-VOLUME-MIX-001"]["typed_value_or_null"], 100.0 / 150.0)
        self.assertEqual(typed["FIELD-HOLDER-COUNT-001"]["state"], STATE_MISSING)
        self.assertEqual(
            typed["FIELD-STATS5M-NUM-TRADERS-001"]["state"], STATE_MISSING
        )

    def test_scheduler_and_projection_share_scalar_semantics(self) -> None:
        row = {
            "id": "MintA",
            "liquidity": 2500.0,
            "mcap": 2000.0,
            "usdPrice": 0.01,
            "stats5m": {"buyVolume": 20.0, "sellVolume": 5.0},
        }
        for field_id in (
            "FIELD-TOKEN-MINT-001",
            "FIELD-LIQUIDITY-USD-001",
            "FIELD-USD-PRICE-001",
            "FIELD-MARKET-CAP-USD-001",
            "FIELD-R0-TAKER-VOLUME-MIX-001",
        ):
            self.assertEqual(
                _row_field(row, field_id),
                project_tokens_v2_scalar(row, field_id),
            )

    def test_fdv_is_not_market_cap(self) -> None:
        value, state, reason = project_tokens_v2_field(
            {"id": "MintB", "fdv": 9999.0},
            "FIELD-MARKET-CAP-USD-001",
        )
        self.assertIsNone(value)
        self.assertEqual(state, STATE_EXCLUDED)
        self.assertEqual(reason, "FDV_NOT_MARKET_CAP")

    def test_taker_volume_not_inferred_from_buy_sell(self) -> None:
        value, state, reason = project_tokens_v2_field(
            {"id": "MintC", "stats5m": {"buyVolume": 1.0, "sellVolume": 1.0}},
            "FIELD-STATS5M-TAKER-VOLUME-001",
        )
        self.assertIsNone(value)
        self.assertEqual(state, STATE_EXCLUDED)
        self.assertEqual(reason, "TAKER_VOLUME_NOT_INFERRED_FROM_BUY_SELL")

    def test_launchpad_field_observed_from_provider_row(self) -> None:
        value, state, missing = project_tokens_v2_field(
            {
                "id": "MintE",
                "launchpad": "pump.fun",
                "firstPool": {"createdAt": "2026-08-24T00:00:00Z"},
            },
            "FIELD-LAUNCHPAD-001",
        )
        self.assertEqual(state, STATE_OBSERVED)
        self.assertEqual(value, "pump.fun")
        self.assertIsNone(missing)

    def test_feature_families_include_missingness(self) -> None:
        typed = project_tokens_v2_row(
            {
                "id": "MintD",
                "liquidity": 1.0,
                "mcap": 2.0,
                "usdPrice": 0.1,
                "firstPool": {"createdAt": "2026-08-24T00:00:00Z"},
                "stats5m": {"buyVolume": 1.0, "sellVolume": 1.0},
            }
        )
        families = feature_families_from_typed_values(typed)
        self.assertIn("PRICE_PATH", families)
        self.assertIn("LIQUIDITY_PATH", families)
        self.assertIn("VALUATION", families)
        self.assertIn("ACTIVITY_VOLUME", families)
        self.assertIn("LIFECYCLE_TIMING", families)
        self.assertIn("MISSINGNESS_AVAILABILITY", families)


if __name__ == "__main__":
    unittest.main()
