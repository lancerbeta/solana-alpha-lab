from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "docs/evidence/task26c/a3_catalog_factory_fit_v1.json"
NEW_IDS = {
    "DOC-T26C-TASK-001",
    "CONTRACT-T26C-OWNED-CANARY-READINESS-001",
    "CONFIG-T26C-OWNED-CANARY-READINESS-001",
    "SCHEMA-T26C-OWNED-CANARY-READINESS-001",
    "MODULE-T26C-OWNED-CANARY-READINESS-001",
    "FIXTURE-T26C-OWNED-CANARY-READINESS-001",
    "TEST-T26C-OWNED-CANARY-READINESS-001",
    "EVIDENCE-T26C-A2-READINESS-001",
    "EVIDENCE-T26C-A3-CATALOG-FACTORY-FIT-001",
    "TEST-T26C-A3-CATALOG-FACTORY-FIT-001",
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


class Task26CCatalogFactoryFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_bytes())
        cls.manifest, cls.records = load_catalog()

    def test_01_receipt_integrity_and_full_review(self) -> None:
        payload = dict(self.receipt)
        del payload["receipt_sha256"]
        canonical = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), self.receipt["receipt_sha256"])
        self.assertEqual(self.receipt["factory_fit"]["mode"], "FULL_REVIEW")
        self.assertEqual(self.receipt["factory_fit"]["result"], "PASS_WITH_FOLLOWUP")
        self.assertEqual(
            self.receipt["accepted_result"]["decision"],
            "READY_FOR_OWNER_CANARY_AUTHORITY_WITH_LIMITATIONS",
        )
        self.assertFalse(self.receipt["accepted_result"]["canary_authority"])

    def test_02_catalog_transaction_is_exact(self) -> None:
        catalog = self.receipt["catalog"]
        self.assertGreaterEqual(
            tuple(map(int, self.manifest["catalog_version"].split("."))),
            tuple(map(int, catalog["after_version"].split("."))),
        )
        self.assertGreaterEqual(self.manifest["current_checkpoint"]["assets"], catalog["after_assets"])
        self.assertGreaterEqual(self.manifest["current_checkpoint"]["schemas"], catalog["after_schemas"])
        self.assertEqual(set(catalog["registered_asset_ids"]), NEW_IDS)
        self.assertTrue(NEW_IDS.issubset(self.records))
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                record = self.records[asset_id]
                self.assertEqual(
                    sha256(ROOT / record["location"]["repository_path"]),
                    record["integrity"]["sha256"],
                )

    def test_03_critical_bindings_and_non_authority_hold(self) -> None:
        for binding in self.receipt["critical_bindings"]:
            with self.subTest(asset_id=binding["asset_id"]):
                self.assertEqual(sha256(ROOT / binding["path"]), binding["sha256"])
        for value in self.receipt["side_effect_counters"].values():
            self.assertEqual(value, 0)
        self.assertEqual(self.receipt["next_boundary"]["authority"], "OWNER_INPUT_REQUIRED")
        self.assertIn("NO_TRANSACTION", self.receipt["confirmations"])
        self.assertIn("NO_TASK27", self.receipt["confirmations"])

    def test_04_product_horizon_is_one_now_and_one_watch(self) -> None:
        radar = self.receipt["product_horizon_radar"]
        self.assertEqual(set(radar), {"now", "watch"})
        self.assertEqual(radar["now"]["owner"], "goal_owner")
        self.assertEqual(radar["now"]["authority"], "OWNER_INPUT_REQUIRED")
        self.assertIn("OWNER_AUTHORITY", radar["now"]["candidate"])
        self.assertIn("trigger", radar["watch"])


if __name__ == "__main__":
    unittest.main()
