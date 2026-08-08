from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
A1_RECEIPT = (
    ROOT
    / "docs/evidence/canary_specification_only/a1_offline_specification_acceptance_v1.json"
)
A2_RECEIPT = (
    ROOT / "docs/evidence/canary_specification_only/a2_catalog_factory_fit_v1.json"
)
SCHEMA = ROOT / "catalog/schemas/canary_specification_only.schema.json"
GENERATED_EDGES = ROOT / "catalog/generated/asset_edges.json"
PROJECT_MAP = ROOT / "docs/PROJECT_MAP.md"
DECISION_REGISTRY = ROOT / "registries/decisions_negative_results.yaml"

NEW_IDS = {
    "DOC-CANARY-SPECIFICATION-ONLY-001",
    "CONTRACT-CANARY-SPECIFICATION-ONLY-001",
    "CONFIG-CANARY-SPECIFICATION-ONLY-001",
    "SCHEMA-CANARY-SPECIFICATION-ONLY-001",
    "FIXTURE-CANARY-SPECIFICATION-ONLY-001",
    "TEST-CANARY-SPECIFICATION-ONLY-001",
    "EVIDENCE-CANARY-SPECIFICATION-ONLY-A1-001",
    "EVIDENCE-CANARY-SPECIFICATION-ONLY-A2-001",
    "TEST-CANARY-SPECIFICATION-ONLY-A2-001",
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


class CanarySpecificationOnlyCatalogFactoryFitTests(unittest.TestCase):
    def _load_required_receipts(self) -> tuple[dict, dict]:
        for path in (A1_RECEIPT, A2_RECEIPT):
            if not path.is_file():
                self.fail(f"required canary specification receipt is missing: {path}")
        return (
            json.loads(A1_RECEIPT.read_text(encoding="utf-8")),
            json.loads(A2_RECEIPT.read_text(encoding="utf-8")),
        )

    def test_receipts_catalog_and_factory_fit_preserve_non_authority(self) -> None:
        a1, a2 = self._load_required_receipts()

        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(a1)
        self.assertEqual(
            a1["status"], "PASS_OFFLINE_SPECIFICATION_DRAFT_ONLY_NO_AUTHORITY"
        )
        for binding in a1["input_bindings"]:
            with self.subTest(a1_binding=binding["asset_id"]):
                self.assertEqual(
                    sha256(ROOT / binding["path"]),
                    binding["sha256"],
                )
        self.assertEqual(
            {case["case_class"] for case in a1["case_results"]},
            {
                "NON_DRAFT_STATE",
                "NON_300_CASH_CAP",
                "MISSING_OWNER_INPUT",
                "TRUE_AUTHORITY",
                "NONZERO_PROVIDER_COUNT",
                "REAL_WALLET_OR_ENDPOINT_TEXT",
            },
        )

        a2_without_hash = dict(a2)
        receipt_sha256 = a2_without_hash.pop("receipt_sha256", None)
        self.assertIsNotNone(receipt_sha256)
        canonical = (
            json.dumps(a2_without_hash, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), receipt_sha256)
        self.assertEqual(a2["factory_fit"]["mode"], "FULL_REVIEW")
        self.assertEqual(a2["factory_fit"]["result"], "PASS_WITH_FOLLOWUP")
        self.assertFalse(a2["accepted_result"]["canary_authority"])
        self.assertFalse(a2["accepted_result"]["task27_authority"])
        self.assertEqual(a2["accepted_result"]["execution_action"], "NONE")
        self.assertEqual(
            a2["accepted_result"]["total_cash_at_risk_usd_cents"],
            300,
        )
        self.assertTrue(
            all(value == 0 for value in a2["side_effect_counters"].values())
        )
        radar = a2["product_horizon_radar"]
        self.assertEqual(set(radar), {"now", "watch"})
        self.assertEqual(radar["now"]["authority"], "OWNER_INPUT_REQUIRED")
        self.assertEqual(
            radar["watch"]["candidate"], "SEPARATE_OWNED_CANARY_AUTHORITY_GATE"
        )

        manifest, records = load_catalog()
        self.assertGreaterEqual(
            tuple(map(int, manifest["catalog_version"].split("."))),
            tuple(map(int, a2["catalog"]["after_version"].split("."))),
        )
        self.assertGreaterEqual(
            manifest["current_checkpoint"]["assets"],
            a2["catalog"]["after_assets"],
        )
        # This receipt records the minimum inventory created by A2.  Later
        # bounded tasks may legitimately append schemas or lifecycle records;
        # treating this historical floor as a current exact total makes the
        # check fail for an unrelated, valid Catalog extension.
        self.assertGreaterEqual(
            manifest["current_checkpoint"]["schemas"],
            a2["catalog"]["after_schemas"],
        )
        self.assertGreaterEqual(
            manifest["current_checkpoint"]["lifecycle_records"],
            a2["catalog"]["after_lifecycle_records"],
        )
        self.assertEqual(set(a2["catalog"]["registered_asset_ids"]), NEW_IDS)
        self.assertTrue(NEW_IDS.issubset(records))

        generated_edges = json.dumps(
            json.loads(GENERATED_EDGES.read_text(encoding="utf-8")),
            sort_keys=True,
        )
        project_map = PROJECT_MAP.read_text(encoding="utf-8")
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                record = records[asset_id]
                self.assertEqual(
                    sha256(ROOT / record["location"]["repository_path"]),
                    record["integrity"]["sha256"],
                )
                self.assertIn(asset_id, generated_edges)
                self.assertIn(asset_id, project_map)

        registry = yaml.safe_load(DECISION_REGISTRY.read_text(encoding="utf-8"))
        record = next(
            item
            for item in registry["records"]
            if item["record_id"] == "DECISION-CANARY-SPECIFICATION-ONLY-001"
        )
        self.assertEqual(record["record_kind"], "decision")
        self.assertEqual(record["status"], "RECORDED")
        self.assertIn(
            "OFFLINE_SPECIFICATION_READY_NO_EXECUTION_AUTHORITY",
            record["summary"],
        )


if __name__ == "__main__":
    unittest.main()
