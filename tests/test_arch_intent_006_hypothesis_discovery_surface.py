from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INTENT_PATH = (
    ROOT
    / "docs/architecture/intents/ARCH-INTENT-006-hypothesis-discovery-and-opportunity-surface.md"
)
ARCHITECTURE_CATALOG_PATH = ROOT / "catalog/assets/architecture.yaml"
MANIFEST_PATH = ROOT / "catalog/catalog_manifest.yaml"
PROJECT_MAP_PATH = ROOT / "docs/PROJECT_MAP.md"
EDGE_PATH = ROOT / "catalog/generated/asset_edges.json"
INTENT_ID = "ARCH-INTENT-006"
LAYER_ID = "HYPOTHESIS_DISCOVERY_AND_OPPORTUNITY_SURFACE"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontmatter(path: Path) -> dict:
    parts = path.read_text(encoding="utf-8").split("---", 2)
    if len(parts) != 3:
        raise AssertionError("frontmatter_missing")
    return yaml.safe_load(parts[1])


class ArchIntent006HypothesisDiscoverySurfaceTests(unittest.TestCase):
    def test_intent_is_horizon_memory_not_implementation(self) -> None:
        document = frontmatter(INTENT_PATH)
        self.assertEqual(document["intent_id"], INTENT_ID)
        self.assertEqual(document["intent_version"], "1.1")
        self.assertEqual(document["status"], "ACCEPTED_DIRECTION_NOT_IMPLEMENTED")
        self.assertEqual(document["implementation"], "NOT_IMPLEMENTED")
        self.assertEqual(document["projection_kind"], "PRODUCT_HORIZON_NOT_IMPLEMENTATION")
        self.assertEqual(document["product_layer_id"], LAYER_ID)
        self.assertEqual(document["activation_mode"], "WATCH_ONLY_UNTIL_ENTRY_GATE")
        self.assertEqual(
            set(document["named_consumers"]),
            {
                "FUTURE_DISCOVERY_RANKER_ENTRY_GATE",
                "GOAL_OWNER_HYPOTHESIS_PRIORITIZATION",
                "HFIC-POST-NO-WORTHY-ROUTER",
            },
        )
        self.assertFalse(document["authority"]["provider_read"])
        self.assertFalse(document["authority"]["wallet_signer_transaction"])
        self.assertFalse(document["authority"]["cash_spend"])
        self.assertFalse(document["authority"]["holdout_consumption"])
        self.assertFalse(document["authority"]["trial_creation"])
        self.assertFalse(document["authority"]["next_hypothesis_selection"])

        text = INTENT_PATH.read_text(encoding="utf-8")
        self.assertIn(LAYER_ID, text)
        self.assertIn("expected information gain", text.lower())
        self.assertIn("EXOGENOUS_CHEAP_CONTEXT", text)
        self.assertIn("MECHANISM_PRIOR", text)
        self.assertIn("PIT_READY", text)
        self.assertIn("HISTORICAL_RECONSTRUCTIBLE", text)
        self.assertIn("factory_v1_common_market_feature_surface_v1.yaml", text)
        self.assertIn("not use the holdout", text.lower())
        self.assertIn("spray LLM ideas", text)
        self.assertIn("vector DB / RAG", text)
        self.assertIn("WATCH-only", text)
        self.assertIn("does not advise or insert roadmap items", text)
        self.assertIn("`mechanism`", text)
        self.assertIn("MARKET_OBSERVABLE", text)
        self.assertIn("does not prove", text.lower())
        self.assertNotIn("AUTHORIZED_TO_BUILD_NOW", text)

    def test_catalog_registration_is_content_bound(self) -> None:
        catalog = yaml.safe_load(ARCHITECTURE_CATALOG_PATH.read_text(encoding="utf-8"))
        record = next(item for item in catalog["records"] if item["asset_id"] == INTENT_ID)
        self.assertEqual(record["status"], "ACCEPTED_DIRECTION_NOT_IMPLEMENTED")
        self.assertEqual(record["integrity"]["sha256"], sha256(INTENT_PATH))
        self.assertEqual(
            {item["target_asset_id"] for item in record["relations"]},
            {"ARCH-INTENT-001", "ARCH-INTENT-002", "ARCH-INTENT-005"},
        )
        self.assertTrue(
            all(
                not str(item["target_asset_id"]).startswith("ROADMAP-")
                for item in record["relations"]
            )
        )
        self.assertEqual(
            set(record["consumers"]),
            {"GOAL-OWNER", "REG-RESEARCH-001", "HFIC-POST-NO-WORTHY-ROUTER"},
        )

        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertIn(INTENT_ID, manifest["mandatory_asset_ids"])
        self.assertIn(INTENT_ID, PROJECT_MAP_PATH.read_text(encoding="utf-8"))
        self.assertIn(INTENT_ID, EDGE_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
