from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog_cli import search_assets  # noqa: E402
from validate_catalog import load_and_validate  # noqa: E402


class CatalogSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_and_validate()

    def test_search_finds_a17_by_pool_and_consumer(self) -> None:
        matches = search_assets(
            self.snapshot.assets,
            "AHTTzwf3GmVMJdxWM8v2MSxyjZj8rQR6hyAC3g9477Yj",
            consumer="RC001-H07-H01-LIQUIDITY-RETENTION",
        )
        self.assertTrue(matches)
        self.assertIn("EVIDENCE-T30-A17-ACTIVE-POOL-ROUTE-YIELD-001", {item["asset_id"] for item in matches})
        self.assertIn("RUNTIME-T30-A17-ACTIVE-POOL-ROUTE-YIELD-001", {item["asset_id"] for item in matches})
        self.assertTrue(all("asset_id" in item for item in matches))

    def test_search_is_case_insensitive_and_filterable(self) -> None:
        matches = search_assets(
            self.snapshot.assets,
            "active pool route yield",
            asset_type="evidence",
            status="VALIDATED_ACTIVE",
        )
        self.assertIn("EVIDENCE-T30-A17-ACTIVE-POOL-ROUTE-YIELD-001", {item["asset_id"] for item in matches})

    def test_empty_search_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "SEARCH_TEXT_REQUIRED"):
            search_assets(self.snapshot.assets, " ")


if __name__ == "__main__":
    unittest.main()
