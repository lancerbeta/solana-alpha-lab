from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.quote_surface_projection import (  # noqa: E402
    ABSENT,
    NULL,
    OBSERVED,
    UNKNOWN,
    project_quote_surface,
    projection_never_zero_for_missing,
)


class QuoteSurfaceProjectionTests(unittest.TestCase):
    def test_absent_fee_impact_route_are_typed_not_zero(self) -> None:
        projection = project_quote_surface(
            {
                "inAmount": "10000000",
                "outAmount": "9900000",
                "router": "iris",
                "mode": "ultra",
            },
            response_sha256="a" * 64,
        )
        self.assertEqual(projection["fee_bps"]["status"], ABSENT)
        self.assertIsNone(projection["fee_bps"]["value"])
        self.assertEqual(projection["price_impact_pct"]["status"], ABSENT)
        self.assertEqual(projection["route_hop_count"]["status"], ABSENT)
        self.assertTrue(projection_never_zero_for_missing(projection))

    def test_null_platform_fee_is_null_not_zero(self) -> None:
        projection = project_quote_surface({"platformFee": None, "outAmount": "1"})
        self.assertEqual(projection["platform_fee"]["status"], NULL)
        self.assertIsNone(projection["platform_fee"]["value"])

    def test_unknown_route_plan_shape(self) -> None:
        projection = project_quote_surface({"routePlan": {"unexpected": True}})
        self.assertEqual(projection["route_hop_count"]["status"], UNKNOWN)
        self.assertIsNone(projection["route_hop_count"]["value"])

    def test_observed_zero_hop_is_allowed(self) -> None:
        projection = project_quote_surface({"routePlan": []})
        self.assertEqual(projection["route_hop_count"], {"status": OBSERVED, "value": "0"})
        self.assertEqual(
            projection["route_fee_amounts_present"],
            {"status": OBSERVED, "value": "false"},
        )

    def test_transaction_is_refused(self) -> None:
        with self.assertRaisesRegex(Exception, "QUOTE_RETURNED_TRANSACTION"):
            project_quote_surface({"transaction": "deadbeef"})


if __name__ == "__main__":
    unittest.main()
