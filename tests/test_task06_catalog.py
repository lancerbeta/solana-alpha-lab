from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validate_catalog import load_and_validate  # noqa: E402

EXPECTED_FILE_ASSETS = {
    "CTRL-TASK-06-001": "docs/tasks/TASK-06.md",
    "CONTRACT-T06-RAW-STORAGE-001": (
        "docs/contracts/raw_storage_contract_v1.md"
    ),
    "CONTRACT-T06-DATASET-MANIFEST-001": (
        "docs/contracts/dataset_manifest_contract_v1.md"
    ),
    "CONTRACT-T06-RAW-PARQUET-001": (
        "docs/contracts/raw_parquet_store_contract_v1.md"
    ),
    "CONTRACT-T06-STORAGE-BUDGET-001": (
        "docs/contracts/storage_budget_contract_v1.md"
    ),
    "MODULE-T06-STORAGE-API-001": (
        "src/solana_alpha_lab/storage/__init__.py"
    ),
    "SCRIPT-T06-RAW-ENVELOPE-001": (
        "src/solana_alpha_lab/storage/raw_envelope.py"
    ),
    "SCRIPT-T06-MANIFESTS-001": (
        "src/solana_alpha_lab/storage/manifests.py"
    ),
    "SCRIPT-T06-PARQUET-STORE-001": (
        "src/solana_alpha_lab/storage/parquet_store.py"
    ),
    "SCRIPT-T06-STORAGE-BUDGET-001": (
        "src/solana_alpha_lab/storage/budget.py"
    ),
    "FIXTURE-T06-RAW-ENVELOPE-001": (
        "tests/fixtures/task06/raw_envelope_v1.json"
    ),
    "FIXTURE-T06-MANIFEST-IDENTITY-001": (
        "tests/fixtures/task06/manifest_identity_v1.json"
    ),
    "TEST-T06-RAW-ENVELOPE-001": (
        "tests/test_task06_raw_envelope.py"
    ),
    "TEST-T06-MANIFESTS-001": "tests/test_task06_manifests.py",
    "TEST-T06-PARQUET-STORE-001": (
        "tests/test_task06_parquet_store.py"
    ),
    "TEST-T06-STORAGE-BUDGET-001": (
        "tests/test_task06_storage_budget.py"
    ),
    "TEST-T06-CATALOG-001": "tests/test_task06_catalog.py",
}

TASK06_ASSET_IDS = set(EXPECTED_FILE_ASSETS)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relation_pairs(asset: dict[str, object]) -> set[tuple[str, str]]:
    return {
        (relation["relation_type"], relation["target_asset_id"])
        for relation in asset["relations"]
    }


class Task06CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_and_validate()

    def test_catalog_checkpoint_and_mandatory_inventory_are_exact(
        self,
    ) -> None:
        self.assertGreaterEqual(
            tuple(
                int(part)
                for part in self.snapshot.manifest["catalog_version"].split(".")
            ),
            (0, 9, 0),
        )
        self.assertEqual(len(self.snapshot.assets), 228)
        self.assertEqual(len(self.snapshot.queries), 7)
        self.assertTrue(
            TASK06_ASSET_IDS.issubset(
                set(self.snapshot.manifest["mandatory_asset_ids"])
            )
        )

    def test_every_task06_file_resolves_by_stable_id_and_hash(
        self,
    ) -> None:
        for asset_id, relative in EXPECTED_FILE_ASSETS.items():
            with self.subTest(asset_id=asset_id):
                asset = self.snapshot.assets[asset_id]
                self.assertEqual(asset["truth_owner"], "TASK-06")
                self.assertEqual(
                    asset["status"],
                    "IMPLEMENTED_UNVERIFIED",
                )
                self.assertEqual(
                    asset["location"]["repository_path"],
                    relative,
                )
                self.assertEqual(
                    asset["integrity"]["sha256"],
                    sha256(ROOT / relative),
                )
                self.assertFalse(
                    asset["classification"]["contains_secrets"]
                )
                self.assertFalse(
                    asset["classification"]["contains_raw_data"]
                )

    def test_task_contains_contracts_and_public_storage_api(self) -> None:
        task_relations = relation_pairs(
            self.snapshot.assets["CTRL-TASK-06-001"]
        )
        for target in (
            "CONTRACT-T06-RAW-STORAGE-001",
            "CONTRACT-T06-DATASET-MANIFEST-001",
            "CONTRACT-T06-RAW-PARQUET-001",
            "CONTRACT-T06-STORAGE-BUDGET-001",
            "MODULE-T06-STORAGE-API-001",
        ):
            self.assertIn(("contains", target), task_relations)
        self.assertIn(
            ("depends_on", "SCHEMA-T05-PYDANTIC-BOUNDARIES-001"),
            task_relations,
        )
        self.assertIn(
            ("validated_by", "TEST-T06-CATALOG-001"),
            task_relations,
        )

    def test_latest_handoff_is_owned_by_task06_and_targets_task07(self) -> None:
        handoff = self.snapshot.assets["CTRL-LATEST-HANDOFF-001"]
        self.assertEqual(handoff["truth_owner"], "TASK-06")
        self.assertEqual(
            handoff["location"]["repository_path"],
            "docs/handoffs/latest.md",
        )
        self.assertEqual(
            handoff["integrity"]["sha256"],
            sha256(ROOT / "docs/handoffs/latest.md"),
        )
        self.assertEqual(
            relation_pairs(handoff),
            {
                ("governed_by", "CTRL-TASK-06-001"),
                ("depends_on", "CONTRACT-T06-RAW-STORAGE-001"),
                ("depends_on", "CONTRACT-T06-DATASET-MANIFEST-001"),
                ("depends_on", "CONTRACT-T06-RAW-PARQUET-001"),
                ("depends_on", "CONTRACT-T06-STORAGE-BUDGET-001"),
                ("validated_by", "TEST-T06-CATALOG-001"),
            },
        )
        self.assertEqual(set(handoff["consumers"]), {"TASK-06", "TASK-07"})

    def test_implementation_and_contract_validation_edges_are_exact(
        self,
    ) -> None:
        expected_edges = {
            "SCRIPT-T06-RAW-ENVELOPE-001": (
                "CONTRACT-T06-RAW-STORAGE-001",
                "TEST-T06-RAW-ENVELOPE-001",
            ),
            "SCRIPT-T06-MANIFESTS-001": (
                "CONTRACT-T06-DATASET-MANIFEST-001",
                "TEST-T06-MANIFESTS-001",
            ),
            "SCRIPT-T06-PARQUET-STORE-001": (
                "CONTRACT-T06-RAW-PARQUET-001",
                "TEST-T06-PARQUET-STORE-001",
            ),
            "SCRIPT-T06-STORAGE-BUDGET-001": (
                "CONTRACT-T06-STORAGE-BUDGET-001",
                "TEST-T06-STORAGE-BUDGET-001",
            ),
        }
        for asset_id, (contract_id, test_id) in expected_edges.items():
            with self.subTest(asset_id=asset_id):
                relations = relation_pairs(
                    self.snapshot.assets[asset_id]
                )
                self.assertIn(("depends_on", contract_id), relations)
                self.assertIn(("validated_by", test_id), relations)
                self.assertIn(
                    ("governed_by", "CTRL-TASK-06-001"),
                    relations,
                )

    def test_catalog_contains_no_raw_bytes_or_physical_data_path(
        self,
    ) -> None:
        for asset_id in TASK06_ASSET_IDS:
            asset = self.snapshot.assets[asset_id]
            repository_path = asset["location"]["repository_path"]
            self.assertFalse(repository_path.endswith(".parquet"))
            self.assertNotIn(":\\", repository_path)
            self.assertFalse(
                asset["classification"]["contains_raw_data"]
            )


if __name__ == "__main__":
    unittest.main()
