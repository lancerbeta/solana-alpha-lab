from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/validate_catalog.py"
spec = importlib.util.spec_from_file_location("validate_catalog", MODULE_PATH)
assert spec and spec.loader
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)


class CatalogImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = catalog.load_and_validate()

    def documents(self):
        return (
            copy.deepcopy(self.snapshot.manifest),
            copy.deepcopy(self.snapshot.assets_documents),
            copy.deepcopy(self.snapshot.queries_documents),
            copy.deepcopy(self.snapshot.lifecycle_documents),
        )

    def test_real_catalog_counts(self) -> None:
        self.assertEqual(len(self.snapshot.assets_documents), 4)
        self.assertEqual(len(self.snapshot.assets), 58)
        self.assertEqual(len(self.snapshot.queries), 4)
        self.assertEqual(len(self.snapshot.lifecycle_documents), 9)
        self.assertEqual(len(self.snapshot.lifecycle_records), 0)
        self.assertIn("ARCH-INTENT-001", self.snapshot.assets)

    def test_duplicate_across_registries_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        assets[1]["records"].append(copy.deepcopy(assets[0]["records"][0]))
        with self.assertRaisesRegex(catalog.CatalogValidationError, "duplicate_asset_ids"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_broken_relation_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        assets[1]["records"][0]["relations"].append({"relation_type":"depends_on","target_asset_id":"MISSING-ASSET-001"})
        with self.assertRaisesRegex(catalog.CatalogValidationError, "broken_asset_relation"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_missing_mandatory_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        assets[2]["records"] = []
        with self.assertRaisesRegex(catalog.CatalogValidationError, "catalog_gap_missing_mandatory"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_pre_git_available_before_bundle_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        target = next(r for d in assets for r in d["records"] if r["asset_id"] == "PRE-GIT-TASK02-ENV-REPORT-001")
        target["provenance"]["created_at"] = "2026-07-19"
        target["provenance"]["first_reliable_available_at"] = "2026-07-20"
        with self.assertRaisesRegex(catalog.CatalogValidationError, "pre_git_available_before_bundle"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_architecture_intent_cannot_claim_implemented(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        target = next(r for d in assets for r in d["records"] if r["asset_id"] == "ARCH-INTENT-001")
        target["status"] = "VALIDATED_ACTIVE"
        with self.assertRaisesRegex(catalog.CatalogValidationError, "architecture_intent_provenance_invalid"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_external_bundle_requires_external_retention(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        target = next(r for d in assets for r in d["records"] if r["asset_id"] == "BUNDLE-TASK01-COMPLETION-001")
        target["provenance"]["retention"] = "TRACKED_REFERENCE"
        with self.assertRaisesRegex(catalog.CatalogValidationError, "external_bundle_provenance_invalid"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_duplicate_lifecycle_record_ids_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        record = {
            "record_id": "SYNTHETIC-DUPLICATE-001",
            "evidence_asset_ids": [],
        }
        lifecycle[0]["records"] = [copy.deepcopy(record)]
        lifecycle[1]["records"] = [copy.deepcopy(record)]
        with self.assertRaisesRegex(
            catalog.CatalogValidationError,
            "duplicate_lifecycle_record_ids",
        ):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_broken_lifecycle_source_asset_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        lifecycle[0]["source_asset_ids"] = ["MISSING-ASSET-001"]
        with self.assertRaisesRegex(
            catalog.CatalogValidationError,
            "broken_lifecycle_source_asset",
        ):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_import_query_readonly(self) -> None:
        recipe = self.snapshot.queries["QUERY-PRE-GIT-VERIFY-001"]
        self.assertTrue(recipe["read_only"])
        self.assertTrue(recipe["bounded"])
        self.assertEqual(recipe["write_effects"], "NONE")


if __name__ == "__main__": unittest.main()
