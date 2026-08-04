from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "docs/evidence/owner_authority_packet_binding/a2_catalog_factory_fit_v1.json"
GENERATED_EDGES = ROOT / "catalog/generated/asset_edges.json"
PROJECT_MAP = ROOT / "docs/PROJECT_MAP.md"
DECISION_REGISTRY = ROOT / "registries/decisions_negative_results.yaml"
NEW_IDS = {
    "DOC-OWNER-AUTHORITY-PACKET-001",
    "CONTRACT-OWNER-AUTHORITY-PACKET-001",
    "CONFIG-OWNER-AUTHORITY-PACKET-001",
    "SCHEMA-OWNER-AUTHORITY-PACKET-001",
    "FIXTURE-OWNER-AUTHORITY-PACKET-001",
    "MODULE-OWNER-AUTHORITY-PACKET-001",
    "TEST-OWNER-AUTHORITY-PACKET-001",
    "EVIDENCE-OWNER-AUTHORITY-PACKET-A1-001",
    "EVIDENCE-OWNER-AUTHORITY-PACKET-A2-001",
    "TEST-OWNER-AUTHORITY-PACKET-A2-001",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_catalog() -> tuple[dict, dict[str, dict]]:
    manifest = yaml.safe_load(
        (ROOT / "catalog/catalog_manifest.yaml").read_text(encoding="utf-8")
    )
    documents = [
        yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
        for relative in manifest["root_resolver"]["asset_registries"]
    ]
    records = {
        record["asset_id"]: record
        for document in documents
        for record in document["records"]
    }
    return manifest, records


class OwnerAuthorityPacketBindingCatalogFactoryFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_bytes())
        cls.manifest, cls.records = load_catalog()

    def test_receipt_integrity_and_full_review_hold_non_authority(self) -> None:
        payload = dict(self.receipt)
        del payload["receipt_sha256"]
        canonical = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), self.receipt["receipt_sha256"])
        self.assertEqual(self.receipt["factory_fit"]["mode"], "FULL_REVIEW")
        self.assertEqual(self.receipt["factory_fit"]["result"], "PASS_WITH_FOLLOWUP")
        self.assertFalse(self.receipt["accepted_result"]["canary_authority"])
        self.assertFalse(self.receipt["accepted_result"]["task27_authority"])
        self.assertEqual(self.receipt["owner_packet"]["status"], "DRAFT_OWNER_INPUT_REQUIRED")
        self.assertEqual(self.receipt["owner_packet"]["all_in_cash_at_risk_cap_usd_cents"], 300)

    def test_catalog_transaction_and_generated_navigation_are_exact(self) -> None:
        catalog = self.receipt["catalog"]
        self.assertGreaterEqual(
            tuple(map(int, self.manifest["catalog_version"].split("."))),
            tuple(map(int, catalog["after_version"].split("."))),
        )
        self.assertGreaterEqual(self.manifest["current_checkpoint"]["assets"], catalog["after_assets"])
        self.assertGreaterEqual(self.manifest["current_checkpoint"]["schemas"], catalog["after_schemas"])
        self.assertEqual(set(catalog["registered_asset_ids"]), NEW_IDS)
        self.assertTrue(NEW_IDS.issubset(self.records))
        generated_edges = json.loads(GENERATED_EDGES.read_text(encoding="utf-8"))
        generated_text = json.dumps(generated_edges, sort_keys=True)
        project_map = PROJECT_MAP.read_text(encoding="utf-8")
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                record = self.records[asset_id]
                self.assertEqual(
                    sha256(ROOT / record["location"]["repository_path"]),
                    record["integrity"]["sha256"],
                )
                self.assertIn(asset_id, generated_text)
                self.assertIn(asset_id, project_map)

    def test_zero_side_effects_and_one_now_one_watch(self) -> None:
        self.assertTrue(
            all(value == 0 for value in self.receipt["side_effect_counters"].values())
        )
        radar = self.receipt["product_horizon_radar"]
        self.assertEqual(set(radar), {"now", "watch"})
        self.assertEqual(radar["now"]["owner"], "goal_owner")
        self.assertEqual(radar["now"]["authority"], "OWNER_INPUT_REQUIRED")
        self.assertEqual(radar["watch"]["candidate"], "TASK-27_EXECUTION_TRUTH_EVALUATION")

    def test_lifecycle_decision_records_the_non_authority_boundary(self) -> None:
        registry = yaml.safe_load(DECISION_REGISTRY.read_text(encoding="utf-8"))
        record = next(
            item
            for item in registry["records"]
            if item["record_id"] == "DECISION-OWNER-AUTHORITY-PACKET-001"
        )
        self.assertEqual(record["record_kind"], "decision")
        self.assertEqual(record["status"], "RECORDED")
        self.assertIn("OFFLINE_OWNER_PACKET_READY_NO_EXECUTION_AUTHORITY", record["summary"])


if __name__ == "__main__":
    unittest.main()
