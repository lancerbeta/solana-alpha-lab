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
    "CONTRACT-T07-PROVIDER-SMOKE-RUNTIME-001": (
        "docs/contracts/provider_smoke_runtime_contract_v1.md"
    ),
    "CONTRACT-T07-PROVIDER-SMOKE-TRANSPORT-001": (
        "docs/contracts/provider_smoke_transport_contract_v1.md"
    ),
    "EVIDENCE-T07-PROVIDER-SMOKE-RECEIPT-001": (
        "docs/evidence/task07/provider_smoke_execution_receipt_v1.json"
    ),
    "EVIDENCE-T07-PROVIDER-SMOKE-SUMMARY-001": (
        "docs/evidence/task07/provider_smoke_execution_summary_v1.md"
    ),
    "SCRIPT-T07-PROVIDER-SMOKE-LAUNCHER-001": (
        "scripts/run_task07_provider_smoke.py"
    ),
    "MODULE-T07-PROVIDER-SMOKE-001": (
        "src/solana_alpha_lab/provider_smoke.py"
    ),
    "MODULE-T07-PROVIDER-SMOKE-TRANSPORT-001": (
        "src/solana_alpha_lab/provider_smoke_transport.py"
    ),
    "FIXTURE-T07-PROVIDER-SMOKE-CONTRACT-001": (
        "tests/fixtures/task07/provider_smoke_contract_v1.json"
    ),
    "FIXTURE-T07-PROVIDER-SMOKE-EVIDENCE-001": (
        "tests/fixtures/task07/provider_smoke_live_evidence_v1.json"
    ),
    "TEST-T07-PROVIDER-SMOKE-001": (
        "tests/test_task07_provider_smoke.py"
    ),
    "TEST-T07-PROVIDER-SMOKE-EVIDENCE-001": (
        "tests/test_task07_provider_smoke_evidence.py"
    ),
    "TEST-T07-PROVIDER-SMOKE-TRANSPORT-001": (
        "tests/test_task07_provider_smoke_transport.py"
    ),
    "TEST-T07-CATALOG-001": "tests/test_task07_catalog.py",
}

TASK07_ASSET_IDS = set(EXPECTED_FILE_ASSETS)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relation_pairs(asset: dict[str, object]) -> set[tuple[str, str]]:
    return {
        (relation["relation_type"], relation["target_asset_id"])
        for relation in asset["relations"]
    }


class Task07CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_and_validate()

    def test_catalog_checkpoint_and_mandatory_inventory_are_exact(self) -> None:
        self.assertGreaterEqual(
            tuple(
                int(part)
                for part in self.snapshot.manifest["catalog_version"].split(".")
            ),
            (0, 9, 0),
        )
        checkpoint = self.snapshot.manifest["current_checkpoint"]
        self.assertEqual(len(self.snapshot.assets), checkpoint["assets"])
        self.assertEqual(len(self.snapshot.queries), checkpoint["queries"])
        self.assertTrue(
            TASK07_ASSET_IDS.issubset(
                set(self.snapshot.manifest["mandatory_asset_ids"])
            )
        )
        self.assertEqual(
            {
                asset_id
                for asset_id, asset in self.snapshot.assets.items()
                if asset["truth_owner"] == "TASK-07"
            },
            TASK07_ASSET_IDS,
        )

    def test_every_task07_file_resolves_by_stable_id_and_hash(self) -> None:
        for asset_id, relative in EXPECTED_FILE_ASSETS.items():
            with self.subTest(asset_id=asset_id):
                asset = self.snapshot.assets[asset_id]
                self.assertEqual(asset["truth_owner"], "TASK-07")
                self.assertEqual(asset["status"], "IMPLEMENTED_UNVERIFIED")
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

    def test_contract_module_launcher_and_test_edges_are_exact(self) -> None:
        expected_edges = {
            "CONTRACT-T07-PROVIDER-SMOKE-RUNTIME-001": {
                ("derived_from", "PRE-GIT-TASK01-A023"),
                ("validated_by", "TEST-T07-PROVIDER-SMOKE-001"),
            },
            "CONTRACT-T07-PROVIDER-SMOKE-TRANSPORT-001": {
                ("derived_from", "PRE-GIT-TASK01-A023"),
                ("depends_on", "CONTRACT-T06-RAW-STORAGE-001"),
                ("validated_by", "TEST-T07-PROVIDER-SMOKE-TRANSPORT-001"),
            },
            "MODULE-T07-PROVIDER-SMOKE-001": {
                ("depends_on", "CONTRACT-T07-PROVIDER-SMOKE-RUNTIME-001"),
                ("depends_on", "MODULE-T06-STORAGE-API-001"),
                ("validated_by", "TEST-T07-PROVIDER-SMOKE-001"),
            },
            "MODULE-T07-PROVIDER-SMOKE-TRANSPORT-001": {
                ("depends_on", "CONTRACT-T07-PROVIDER-SMOKE-TRANSPORT-001"),
                ("depends_on", "MODULE-T07-PROVIDER-SMOKE-001"),
                ("depends_on", "MODULE-T06-STORAGE-API-001"),
                ("validated_by", "TEST-T07-PROVIDER-SMOKE-TRANSPORT-001"),
            },
            "SCRIPT-T07-PROVIDER-SMOKE-LAUNCHER-001": {
                ("depends_on", "MODULE-T07-PROVIDER-SMOKE-001"),
                ("depends_on", "MODULE-T07-PROVIDER-SMOKE-TRANSPORT-001"),
                ("validated_by", "TEST-T07-PROVIDER-SMOKE-TRANSPORT-001"),
            },
        }
        for asset_id, expected in expected_edges.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(
                    relation_pairs(self.snapshot.assets[asset_id]),
                    expected,
                )

    def test_sanitized_evidence_lineage_is_explicit(self) -> None:
        fixture = relation_pairs(
            self.snapshot.assets[
                "FIXTURE-T07-PROVIDER-SMOKE-EVIDENCE-001"
            ]
        )
        receipt = relation_pairs(
            self.snapshot.assets[
                "EVIDENCE-T07-PROVIDER-SMOKE-RECEIPT-001"
            ]
        )
        summary = relation_pairs(
            self.snapshot.assets[
                "EVIDENCE-T07-PROVIDER-SMOKE-SUMMARY-001"
            ]
        )
        self.assertEqual(
            fixture,
            {
                ("derived_from", "FIXTURE-T07-PROVIDER-SMOKE-CONTRACT-001"),
                ("validated_by", "TEST-T07-PROVIDER-SMOKE-EVIDENCE-001"),
            },
        )
        self.assertEqual(
            receipt,
            {
                ("derived_from", "FIXTURE-T07-PROVIDER-SMOKE-EVIDENCE-001"),
                ("validated_by", "TEST-T07-PROVIDER-SMOKE-EVIDENCE-001"),
            },
        )
        self.assertEqual(
            summary,
            {
                ("derived_from", "FIXTURE-T07-PROVIDER-SMOKE-EVIDENCE-001"),
                ("evidenced_by", "EVIDENCE-T07-PROVIDER-SMOKE-RECEIPT-001"),
            },
        )

    def test_catalog_contains_no_raw_bytes_or_physical_data_path(self) -> None:
        for asset_id in TASK07_ASSET_IDS:
            asset = self.snapshot.assets[asset_id]
            repository_path = asset["location"]["repository_path"]
            self.assertFalse(repository_path.endswith(".parquet"))
            self.assertFalse(repository_path.startswith("data/raw/"))
            self.assertNotIn(":\\", repository_path)
            self.assertFalse(
                asset["classification"]["contains_raw_data"]
            )


if __name__ == "__main__":
    unittest.main()
