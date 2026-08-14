from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INTENT_PATH = ROOT / "docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md"
ARCHITECTURE_CATALOG_PATH = ROOT / "catalog/assets/architecture.yaml"
MANIFEST_PATH = ROOT / "catalog/catalog_manifest.yaml"
PROJECT_MAP_PATH = ROOT / "docs/PROJECT_MAP.md"
EDGE_PATH = ROOT / "catalog/generated/asset_edges.json"
INTENT_ID = "ARCH-INTENT-004"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontmatter(path: Path) -> dict:
    parts = path.read_text(encoding="utf-8").split("---", 2)
    if len(parts) != 3:
        raise AssertionError("frontmatter_missing")
    return yaml.safe_load(parts[1])


class ArchIntent004ContextCapsuleBoundaryTests(unittest.TestCase):
    def test_intent_is_content_bound_catalog_discoverable_and_bounded_implemented(self) -> None:
        self.assertTrue(INTENT_PATH.is_file(), INTENT_PATH)
        document = frontmatter(INTENT_PATH)
        self.assertEqual(document["intent_id"], INTENT_ID)
        self.assertEqual(document["intent_version"], "1.1")
        self.assertEqual(document["status"], "IMPLEMENTED_BOUNDED_READ_ONLY_PROJECTION")
        self.assertEqual(document["projection_kind"], "DERIVED_READ_ONLY_PROJECTION")
        self.assertEqual(document["context_map_id"], "DELIVERY_CONTEXT_MAP_V1")
        self.assertEqual(document["truth_owners"], {
            "bytes": "GIT",
            "discovery_and_relations": "CATALOG",
            "lifecycle": "REGISTRIES",
        })
        self.assertFalse(document["authority"]["provider_read"])
        self.assertFalse(document["authority"]["wallet_signer_transaction"])
        self.assertFalse(document["authority"]["cash_spend"])
        self.assertFalse(document["authority"]["project_source_mutation"])
        self.assertEqual(document["implementation"], "DELIVERY_HARNESS_V1")
        self.assertEqual(len(document["activation_evidence"]), 2)

        catalog = yaml.safe_load(ARCHITECTURE_CATALOG_PATH.read_text(encoding="utf-8"))
        record = next(item for item in catalog["records"] if item["asset_id"] == INTENT_ID)
        self.assertEqual(record["record_version"], "1.1")
        self.assertEqual(record["status"], "IMPLEMENTED_UNVERIFIED")
        self.assertEqual(record["integrity"]["sha256"], sha256(INTENT_PATH))
        self.assertEqual(
            {item["target_asset_id"] for item in record["relations"]},
            {
                "ARCH-INTENT-002",
                "ARCH-INTENT-T21-PRODUCT-VISION-001",
                "EVIDENCE-DELIVERY-HARNESS-ACCEPTANCE-001",
            },
        )
        self.assertIn("CTRL-DELIVERY-HARNESS-001", record["consumers"])

        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertIn(
            "catalog/assets/architecture.yaml",
            manifest["root_resolver"]["asset_registries"],
        )
        self.assertIn(INTENT_ID, PROJECT_MAP_PATH.read_text(encoding="utf-8"))
        self.assertIn(INTENT_ID, EDGE_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
