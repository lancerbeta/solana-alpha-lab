from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "docs/evidence/task26a/a3_catalog_factory_fit_v1.json"
NEW_IDS = {
    "DOC-T26A-TASK-001",
    "CONTRACT-T26A-EXECUTION-EVIDENCE-001",
    "CONFIG-T26A-EXECUTION-EVIDENCE-001",
    "SCHEMA-T26A-EXECUTION-EVIDENCE-001",
    "MODULE-T26A-EXECUTION-EVIDENCE-INVENTORY-001",
    "MODULE-T26A-ADVERSARIAL-ACCEPTANCE-001",
    "FIXTURE-T26A-EXECUTION-EVIDENCE-INVENTORY-001",
    "FIXTURE-T26A-EXECUTION-EVIDENCE-ADVERSARIAL-MATRIX-001",
    "TEST-T26A-EXECUTION-EVIDENCE-CONTRACT-001",
    "TEST-T26A-EXECUTION-EVIDENCE-INVENTORY-001",
    "TEST-T26A-ADVERSARIAL-ACCEPTANCE-001",
    "EVIDENCE-T26A-A1-INVENTORY-001",
    "EVIDENCE-T26A-A1-ACCEPTANCE-001",
    "EVIDENCE-T26A-A2-ADVERSARIAL-001",
    "EVIDENCE-T26A-A3-CATALOG-FACTORY-FIT-001",
    "TEST-T26A-A3-CATALOG-FACTORY-FIT-001",
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


class Task26ACatalogFactoryFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_bytes())
        cls.manifest, cls.records = load_catalog()

    def test_01_receipt_decision_and_counts(self) -> None:
        accepted = self.receipt["accepted_result"]
        self.assertEqual(accepted["decision"], "EXTEND_EXECUTION_EVIDENCE")
        self.assertEqual(accepted["quote_pairs"], 36)
        self.assertEqual(accepted["quote_cost_input_ready_pairs"], 35)
        self.assertEqual(accepted["pairs_with_complete_fee_evidence"], 0)
        self.assertEqual(accepted["numeric_modeled_netreturn_claims"], 0)
        self.assertEqual(accepted["observed_netreturn_claims"], 0)
        self.assertFalse(accepted["task27_authority"])
        payload = dict(self.receipt)
        del payload["receipt_sha256"]
        canonical = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), self.receipt["receipt_sha256"])

    def test_02_catalog_transaction_exact(self) -> None:
        catalog = self.receipt["catalog"]
        self.assertGreaterEqual(
            tuple(map(int, self.manifest["catalog_version"].split("."))),
            tuple(map(int, catalog["after_version"].split("."))),
        )
        self.assertGreaterEqual(
            self.manifest["current_checkpoint"]["assets"],
            catalog["after_assets"],
        )
        self.assertGreaterEqual(
            self.manifest["current_checkpoint"]["schemas"],
            catalog["after_schemas"],
        )
        self.assertEqual(set(catalog["registered_asset_ids"]), NEW_IDS)
        self.assertTrue(NEW_IDS.issubset(self.records))
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                record = self.records[asset_id]
                path = ROOT / record["location"]["repository_path"]
                self.assertEqual(sha256(path), record["integrity"]["sha256"])

    def test_03_critical_bindings_hash_exact(self) -> None:
        for binding in self.receipt["critical_bindings"]:
            with self.subTest(asset_id=binding["asset_id"]):
                self.assertEqual(sha256(ROOT / binding["path"]), binding["sha256"])

    def test_04_side_effects_and_boundaries(self) -> None:
        counters = self.receipt["side_effect_counters"]
        for key, value in counters.items():
            with self.subTest(key=key):
                self.assertEqual(value, 0)
        self.assertFalse(self.receipt["next_boundary"]["authorized"])
        self.assertEqual(self.receipt["next_boundary"]["r3_access"], "DENY")
        self.assertIn("NO_NUMERIC_NETRETURN", self.receipt["confirmations"])
        self.assertIn("NO_TASK27", self.receipt["confirmations"])
        self.assertIn("NO_MERGE", self.receipt["confirmations"])


if __name__ == "__main__":
    unittest.main()
