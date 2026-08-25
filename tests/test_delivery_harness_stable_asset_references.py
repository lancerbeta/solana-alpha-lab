from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/delivery_harness.py"
RECEIPT_SCHEMA = ROOT / "catalog/schemas/delivery_harness_context_receipt.schema.json"
TASK_CONTRACT_SCHEMA = ROOT / "catalog/schemas/delivery_harness_task_contract.schema.json"
TASK_CONTRACT = "docs/tasks/CTRL-DELIVERY-HARNESS-V1.md"
TASK_ID = "CTRL-DELIVERY-HARNESS-V1"
REGISTRY_010 = "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010"
REGISTRY_010_PATH = "configs/provider_route_capability_registry_v10.yaml"
REGISTRY_003 = "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003"
EMPTY_ROLE_ASSETS = {
    "LIFECYCLE": [],
    "EXTERNAL_ROUTE_KNOWLEDGE": [],
    "ARCHITECTURE_DECISIONS": [],
    "DELIVERY_EVIDENCE": [],
    "HISTORICAL_CONTEXT": [],
}


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("delivery_harness", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("delivery harness script is not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeliveryHarnessStableAssetReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.receipt_schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
        cls.task_schema = json.loads(TASK_CONTRACT_SCHEMA.read_text(encoding="utf-8"))
        cls.context_map = cls.module.load_closed_document(
            ROOT / "delivery-harness/context-map.yaml",
            ROOT / "catalog/schemas/delivery_harness_context_map.schema.json",
        )
        cls.records = cls.module.load_catalog_records(
            ROOT, "catalog/catalog_manifest.yaml"
        )

    def metadata(self) -> dict:
        return self.module.parse_task_contract(ROOT, TASK_CONTRACT, TASK_ID)

    def resolve(self, metadata: dict, *, records=None) -> tuple[list[dict], list[dict]]:
        return self.module.resolve_required_context(
            ROOT,
            metadata,
            self.context_map,
            records=self.records if records is None else records,
            max_inline_bytes=102400,
        )

    def test_path_only_contract_remains_valid_without_asset_ids(self) -> None:
        metadata = self.metadata()
        self.assertNotIn("exact_role_asset_ids", metadata["context_requirements"])
        jsonschema.validate(metadata, self.task_schema)
        selected, gaps = self.resolve(metadata)
        evidence = [
            item
            for item in selected
            if item["semantic_role"] == "DELIVERY_EVIDENCE"
        ]
        self.assertEqual(
            [item["path"] for item in evidence],
            ["docs/evidence/control/delivery_harness_acceptance_v1.json"],
        )
        self.assertEqual(evidence[0]["resolution_method"], "EXACT_PATH")
        self.assertIsNone(evidence[0]["stable_id"])
        self.assertRegex(evidence[0]["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn(
            "EXTERNAL_ROUTE_KNOWLEDGE",
            {gap["semantic_role"] for gap in gaps},
        )

    def test_receipt_schema_accepts_legacy_selected_without_resolution_method(self) -> None:
        sample = {
            "semantic_role": "DELIVERY_EVIDENCE",
            "lane": "L2",
            "truth_owner": "EXACT_CANDIDATE_EVIDENCE",
            "path": "docs/evidence/control/delivery_harness_acceptance_v1.json",
            "stable_id": None,
            "sha256": "0" * 64,
            "state": "RESOLVED",
            "inclusion": "METADATA_ONLY",
        }
        jsonschema.validate(sample, self.receipt_schema["$defs"]["selected"])

    def test_asset_id_role_resolves_exact_path_hash_and_method(self) -> None:
        metadata = self.metadata()
        requirements = metadata["context_requirements"]
        requirements["l2_roles"] = ["EXTERNAL_ROUTE_KNOWLEDGE"]
        requirements["exact_role_paths"]["ARCHITECTURE_DECISIONS"] = []
        requirements["exact_role_paths"]["DELIVERY_EVIDENCE"] = []
        requirements["exact_role_paths"]["EXTERNAL_ROUTE_KNOWLEDGE"] = []
        requirements["exact_role_asset_ids"] = {
            **EMPTY_ROLE_ASSETS,
            "EXTERNAL_ROUTE_KNOWLEDGE": [REGISTRY_010],
        }
        jsonschema.validate(metadata, self.task_schema)
        selected, _gaps = self.resolve(metadata)
        match = [
            item
            for item in selected
            if item["semantic_role"] == "EXTERNAL_ROUTE_KNOWLEDGE"
        ]
        self.assertEqual(len(match), 1)
        item = match[0]
        self.assertEqual(item["path"], REGISTRY_010_PATH)
        self.assertEqual(item["stable_id"], REGISTRY_010)
        self.assertEqual(item["resolution_method"], "CATALOG_ASSET_ID")
        self.assertEqual(
            item["sha256"],
            self.module.sha256_file(ROOT / REGISTRY_010_PATH),
        )

    def test_multiple_role_asset_ids_preserve_declared_order(self) -> None:
        metadata = self.metadata()
        requirements = metadata["context_requirements"]
        requirements["l2_roles"] = ["EXTERNAL_ROUTE_KNOWLEDGE"]
        requirements["exact_role_paths"]["ARCHITECTURE_DECISIONS"] = []
        requirements["exact_role_paths"]["DELIVERY_EVIDENCE"] = []
        requirements["exact_role_asset_ids"] = {
            **EMPTY_ROLE_ASSETS,
            "EXTERNAL_ROUTE_KNOWLEDGE": [REGISTRY_003, REGISTRY_010],
        }
        selected, _gaps = self.resolve(metadata)
        ids = [
            item["stable_id"]
            for item in selected
            if item["semantic_role"] == "EXTERNAL_ROUTE_KNOWLEDGE"
        ]
        self.assertEqual(ids, [REGISTRY_003, REGISTRY_010])

    def test_duplicate_concrete_path_in_one_role_fails_closed(self) -> None:
        metadata = self.metadata()
        requirements = metadata["context_requirements"]
        requirements["l2_roles"] = ["EXTERNAL_ROUTE_KNOWLEDGE"]
        requirements["exact_role_paths"]["ARCHITECTURE_DECISIONS"] = []
        requirements["exact_role_paths"]["DELIVERY_EVIDENCE"] = []
        requirements["exact_role_paths"]["EXTERNAL_ROUTE_KNOWLEDGE"] = [
            REGISTRY_010_PATH
        ]
        requirements["exact_role_asset_ids"] = {
            **EMPTY_ROLE_ASSETS,
            "EXTERNAL_ROUTE_KNOWLEDGE": [REGISTRY_010],
        }
        with self.assertRaisesRegex(ValueError, "CONTEXT_REFERENCE_DUPLICATE"):
            self.resolve(metadata)

    def test_missing_catalog_asset_fails_before_task_body(self) -> None:
        metadata = self.metadata()
        requirements = metadata["context_requirements"]
        requirements["l2_roles"] = ["EXTERNAL_ROUTE_KNOWLEDGE"]
        requirements["exact_role_paths"]["ARCHITECTURE_DECISIONS"] = []
        requirements["exact_role_paths"]["DELIVERY_EVIDENCE"] = []
        requirements["exact_role_asset_ids"] = {
            **EMPTY_ROLE_ASSETS,
            "EXTERNAL_ROUTE_KNOWLEDGE": ["CONFIG-DOES-NOT-EXIST-001"],
        }
        with self.assertRaisesRegex(ValueError, "CONTEXT_ASSET_NOT_FOUND"):
            self.resolve(metadata)

    def test_missing_asset_path_fails_closed(self) -> None:
        metadata = self.metadata()
        requirements = metadata["context_requirements"]
        requirements["l2_roles"] = ["EXTERNAL_ROUTE_KNOWLEDGE"]
        requirements["exact_role_paths"]["ARCHITECTURE_DECISIONS"] = []
        requirements["exact_role_paths"]["DELIVERY_EVIDENCE"] = []
        requirements["exact_role_asset_ids"] = {
            **EMPTY_ROLE_ASSETS,
            "EXTERNAL_ROUTE_KNOWLEDGE": [REGISTRY_010],
        }
        records = copy.deepcopy(self.records)
        records[REGISTRY_010]["location"]["repository_path"] = (
            "configs/provider_route_capability_registry_missing.yaml"
        )
        with self.assertRaisesRegex(ValueError, "CONTEXT_ASSET_PATH_MISSING"):
            self.resolve(metadata, records=records)

    def test_catalog_integrity_mismatch_fails_closed(self) -> None:
        metadata = self.metadata()
        requirements = metadata["context_requirements"]
        requirements["l2_roles"] = ["EXTERNAL_ROUTE_KNOWLEDGE"]
        requirements["exact_role_paths"]["ARCHITECTURE_DECISIONS"] = []
        requirements["exact_role_paths"]["DELIVERY_EVIDENCE"] = []
        requirements["exact_role_asset_ids"] = {
            **EMPTY_ROLE_ASSETS,
            "EXTERNAL_ROUTE_KNOWLEDGE": [REGISTRY_010],
        }
        records = copy.deepcopy(self.records)
        records[REGISTRY_010]["integrity"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "CONTEXT_HASH_MISMATCH"):
            self.resolve(metadata, records=records)

    def test_binding_move_does_not_move_pinned_task(self) -> None:
        metadata = self.metadata()
        requirements = metadata["context_requirements"]
        requirements["l2_roles"] = ["EXTERNAL_ROUTE_KNOWLEDGE"]
        requirements["exact_role_paths"]["ARCHITECTURE_DECISIONS"] = []
        requirements["exact_role_paths"]["DELIVERY_EVIDENCE"] = []
        requirements["exact_role_asset_ids"] = {
            **EMPTY_ROLE_ASSETS,
            "EXTERNAL_ROUTE_KNOWLEDGE": [REGISTRY_010],
        }
        first, _ = self.resolve(metadata)
        pinned = [
            item
            for item in first
            if item["semantic_role"] == "EXTERNAL_ROUTE_KNOWLEDGE"
        ][0]
        moved = copy.deepcopy(self.records)
        synthetic = "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-011"
        moved[synthetic] = copy.deepcopy(moved[REGISTRY_003])
        moved[synthetic]["asset_id"] = synthetic
        second, _ = self.resolve(metadata, records=moved)
        still = [
            item
            for item in second
            if item["semantic_role"] == "EXTERNAL_ROUTE_KNOWLEDGE"
        ][0]
        self.assertEqual(still["stable_id"], REGISTRY_010)
        self.assertEqual(still["path"], pinned["path"])
        self.assertEqual(still["sha256"], pinned["sha256"])
        new_task = copy.deepcopy(metadata)
        new_task["context_requirements"]["exact_role_asset_ids"][
            "EXTERNAL_ROUTE_KNOWLEDGE"
        ] = [synthetic]
        designed, _ = self.resolve(new_task, records=moved)
        fresh = [
            item
            for item in designed
            if item["semantic_role"] == "EXTERNAL_ROUTE_KNOWLEDGE"
        ][0]
        self.assertEqual(fresh["stable_id"], synthetic)
        self.assertEqual(fresh["path"], moved[synthetic]["location"]["repository_path"])
        self.assertNotEqual(fresh["path"], pinned["path"])

    def test_same_asset_in_catalog_ids_and_role_keeps_both_purposes(self) -> None:
        metadata = self.metadata()
        requirements = metadata["context_requirements"]
        requirements["catalog_asset_ids"] = [REGISTRY_010]
        requirements["l2_roles"] = ["EXTERNAL_ROUTE_KNOWLEDGE"]
        requirements["exact_role_paths"]["ARCHITECTURE_DECISIONS"] = []
        requirements["exact_role_paths"]["DELIVERY_EVIDENCE"] = []
        requirements["exact_role_asset_ids"] = {
            **EMPTY_ROLE_ASSETS,
            "EXTERNAL_ROUTE_KNOWLEDGE": [REGISTRY_010],
        }
        catalog_selected, _ = self.module.catalog_relation_references(
            ROOT, self.records, [REGISTRY_010], max_inline_bytes=102400
        )
        role_selected, _ = self.resolve(metadata)
        self.assertEqual(catalog_selected[0]["semantic_role"], "STABLE_ASSETS_AND_RELATIONS")
        self.assertEqual(catalog_selected[0]["path"], REGISTRY_010_PATH)
        match = [
            item
            for item in role_selected
            if item["semantic_role"] == "EXTERNAL_ROUTE_KNOWLEDGE"
        ]
        self.assertEqual(match[0]["path"], REGISTRY_010_PATH)
        self.assertEqual(match[0]["sha256"], catalog_selected[0]["sha256"])

    def test_context_guidance_has_no_hardcoded_registry_v3_path(self) -> None:
        context = (ROOT / "delivery-harness/context-map.yaml").read_text(encoding="utf-8")
        policy = (ROOT / "delivery-harness/policies/solana-alpha-lab.md").read_text(
            encoding="utf-8"
        )
        portable = (
            ROOT / "delivery-harness/templates/portable-core/delivery-harness/context-map.yaml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("provider_route_capability_registry_v3.yaml", context)
        self.assertNotIn("provider_route_capability_registry_v3.yaml", policy)
        self.assertNotIn("provider_route_capability_registry_v3.yaml", portable)
        mapped = yaml.safe_load(context)
        external = next(
            role
            for role in mapped["roles"]
            if role["semantic_role"] == "EXTERNAL_ROUTE_KNOWLEDGE"
        )
        self.assertEqual(external["resolver"]["kind"], "CATALOG_QUERY")
        self.assertNotIn(
            "configs/provider_route_capability_registry_v3.yaml",
            external["resolver"]["paths"],
        )


if __name__ == "__main__":
    unittest.main()
