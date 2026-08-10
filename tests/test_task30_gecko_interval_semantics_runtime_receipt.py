from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "docs" / "evidence" / "task30" / "a10_gecko_interval_semantics_runtime_receipt_v1.json"
FACTORY_FIT = ROOT / "docs" / "evidence" / "task30" / "a10_gecko_interval_semantics_factory_fit_v1.json"
CONFIG = ROOT / "configs" / "task30_gecko_interval_semantics_v1.yaml"
CONTRACT = ROOT / "docs" / "contracts" / "task30_gecko_interval_semantics_contract_v1.md"
CATALOG = ROOT / "catalog" / "assets" / "core.yaml"
LIFECYCLE_CATALOG = ROOT / "catalog" / "assets" / "lifecycle.yaml"


class Task30GeckoIntervalSemanticsRuntimeReceiptTests(unittest.TestCase):
    def test_exact_two_read_runtime_receipt_is_bound_and_keeps_all_product_claims_closed(self) -> None:
        receipt = json.loads(RUNTIME.read_text(encoding="utf-8"))

        self.assertEqual(receipt["provider_calls_attempted"], 2)
        self.assertEqual([entry["http_status"] for entry in receipt["reads"]], [200, 200])
        self.assertEqual(receipt["decision"], "START_LABELED")
        self.assertEqual(receipt["selected_model"], "START_LABELED")
        self.assertEqual(receipt["runtime_result"]["models"]["START_LABELED"]["contradictions"], 0)
        self.assertGreater(receipt["runtime_result"]["models"]["END_LABELED"]["contradictions"], 0)
        self.assertEqual(receipt["config_sha256"], hashlib.sha256(CONFIG.read_bytes()).hexdigest())
        self.assertEqual(receipt["contract_sha256"], hashlib.sha256(CONTRACT.read_bytes()).hexdigest())
        self.assertEqual(receipt["raw_manifest"]["sha256"], "86e5483c5c1da610cc65e0de1b8aeb441f716a0c7553372769c3c5ae8e255899")
        self.assertTrue(receipt["claims"]["interval_label_semantics_only"])
        self.assertFalse(receipt["claims"]["continuous_panel"])
        self.assertFalse(receipt["claims"]["historical_panel"])
        self.assertFalse(receipt["claims"]["pit_admissible"])
        self.assertFalse(receipt["claims"]["task30_trial"])
        self.assertEqual(receipt["side_effects"]["cash_spend_usd_cents"], 0)
        self.assertEqual(receipt["project_sources_disposition"], "NO_CHANGE")
        self.assertEqual(receipt["state_change"], "NONE")

    def test_full_factory_fit_and_catalog_preserve_the_limited_external_read_boundary(self) -> None:
        runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
        factory_fit = json.loads(FACTORY_FIT.read_text(encoding="utf-8"))
        catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
        asset_ids = {record["asset_id"] for record in catalog["records"]}

        self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
        self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(factory_fit["runtime_receipt_sha256"], hashlib.sha256(RUNTIME.read_bytes()).hexdigest())
        self.assertEqual(runtime["next_boundary"], "OWNER_DECISION_AFTER_TECHNICAL_SEMANTICS_RESULT")
        self.assertTrue(
            {
                "CONTRACT-T30-GECKO-INTERVAL-SEMANTICS-001",
                "CONFIG-T30-GECKO-INTERVAL-SEMANTICS-001",
                "MODULE-T30-GECKO-INTERVAL-SEMANTICS-001",
                "SCRIPT-T30-GECKO-INTERVAL-SEMANTICS-001",
                "EVIDENCE-T30-A10-GECKO-INTERVAL-SEMANTICS-RUNTIME-001",
                "EVIDENCE-T30-A10-GECKO-INTERVAL-SEMANTICS-FACTORY-FIT-001",
            }.issubset(asset_ids)
        )

    def test_generated_navigation_hashes_are_rebound_after_a_catalog_addition(self) -> None:
        lifecycle = yaml.safe_load(LIFECYCLE_CATALOG.read_text(encoding="utf-8"))
        records = {record["asset_id"]: record for record in lifecycle["records"]}
        expected = {
            "GENERATED-PROJECT-MAP-001": ROOT / "docs" / "PROJECT_MAP.md",
            "GENERATED-EDGE-PROJECTION-001": ROOT / "catalog" / "generated" / "asset_edges.json",
        }

        for asset_id, path in expected.items():
            self.assertEqual(
                records[asset_id]["integrity"]["sha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
