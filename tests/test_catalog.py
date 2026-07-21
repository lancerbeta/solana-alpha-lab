from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_catalog.py"
CLI_PATH = ROOT / "scripts" / "catalog_cli.py"

spec = importlib.util.spec_from_file_location("validate_catalog", MODULE_PATH)
assert spec and spec.loader
catalog = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)


class CatalogFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = catalog.load_and_validate()

    def documents(self):
        return (
            copy.deepcopy(self.snapshot.manifest),
            copy.deepcopy(self.snapshot.assets_document),
            copy.deepcopy(self.snapshot.queries_document),
        )

    def test_real_catalog_passes(self) -> None:
        self.assertIn("CATALOG-ROOT-001", self.snapshot.assets)
        self.assertIn("QUERY-CATALOG-VALIDATE-001", self.snapshot.queries)

    def test_safe_relative_path(self) -> None:
        self.assertTrue(catalog.is_safe_relative_path("catalog/assets/core.yaml"))
        separator = chr(92)
        absolute = "C:" + separator + "Users" + separator + "Example" + separator + "file"
        self.assertFalse(catalog.is_safe_relative_path(absolute))

    def test_duplicate_asset_rejected(self) -> None:
        manifest, assets, queries = self.documents()
        assets["records"].append(copy.deepcopy(assets["records"][0]))
        with self.assertRaisesRegex(catalog.CatalogValidationError, "duplicate_asset_ids"):
            catalog.validate_semantics(manifest, assets, queries)

    def test_broken_relation_rejected(self) -> None:
        manifest, assets, queries = self.documents()
        assets["records"][0]["relations"].append(
            {"relation_type": "depends_on", "target_asset_id": "MISSING-ASSET-001"}
        )
        with self.assertRaisesRegex(catalog.CatalogValidationError, "broken_asset_relation"):
            catalog.validate_semantics(manifest, assets, queries)

    def test_missing_mandatory_rejected(self) -> None:
        manifest, assets, queries = self.documents()
        assets["records"] = [
            item for item in assets["records"] if item["asset_id"] != "CATALOG-ROOT-001"
        ]
        with self.assertRaisesRegex(catalog.CatalogValidationError, "catalog_gap_missing_mandatory"):
            catalog.validate_semantics(manifest, assets, queries)

    def test_hash_drift_rejected(self) -> None:
        manifest, assets, queries = self.documents()
        record = next(item for item in assets["records"] if item["integrity"]["kind"] == "sha256")
        record["integrity"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(catalog.CatalogValidationError, "sha256_mismatch"):
            catalog.validate_semantics(manifest, assets, queries)

    def test_query_write_effect_rejected(self) -> None:
        manifest, assets, queries = self.documents()
        queries["recipes"][0]["write_effects"] = "FILESYSTEM_WRITE"
        with self.assertRaisesRegex(catalog.CatalogValidationError, "query_write_effects"):
            catalog.validate_semantics(manifest, assets, queries)

    def test_broken_query_target_rejected(self) -> None:
        manifest, assets, queries = self.documents()
        queries["recipes"][0]["target_asset_ids"] = ["MISSING-ASSET-001"]
        with self.assertRaisesRegex(catalog.CatalogValidationError, "broken_query_target"):
            catalog.validate_semantics(manifest, assets, queries)

    def test_parameter_mismatch_rejected(self) -> None:
        manifest, assets, queries = self.documents()
        recipe = next(item for item in queries["recipes"] if item["parameters"])
        recipe["parameters"] = []
        with self.assertRaisesRegex(catalog.CatalogValidationError, "query_parameter_mismatch"):
            catalog.validate_semantics(manifest, assets, queries)


if __name__ == "__main__":
    unittest.main()
