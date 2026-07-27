from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validate_catalog import load_and_validate  # noqa: E402

EXPECTED_FILE_ASSETS = {
    "CONTRACT-T08-LIFECYCLE-DISCOVERY-001": (
        "docs/contracts/lifecycle_discovery_contract_v1.md"
    ),
    "CONTRACT-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001": (
        "docs/contracts/lifecycle_discovery_probe_transport_contract_v1.md"
    ),
    "EVIDENCE-T08-LIFECYCLE-DISCOVERY-RECEIPT-001": (
        "docs/evidence/task08/"
        "lifecycle_discovery_probe_execution_receipt_v1.json"
    ),
    "EVIDENCE-T08-LIFECYCLE-DISCOVERY-SUMMARY-001": (
        "docs/evidence/task08/"
        "lifecycle_discovery_probe_execution_summary_v1.md"
    ),
    "SCRIPT-T08-LIFECYCLE-DISCOVERY-PROBE-001": (
        "scripts/run_task08_lifecycle_discovery_probe.py"
    ),
    "MODULE-T08-LIFECYCLE-DISCOVERY-001": (
        "src/solana_alpha_lab/lifecycle_discovery.py"
    ),
    "MODULE-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001": (
        "src/solana_alpha_lab/lifecycle_discovery_transport.py"
    ),
    "MODULE-T08-PUMP-EVENT-DECODER-001": (
        "src/solana_alpha_lab/pump_event_decoder.py"
    ),
    "FIXTURE-T08-LIFECYCLE-DISCOVERY-CONTRACT-001": (
        "tests/fixtures/task08/lifecycle_discovery_contract_v1.json"
    ),
    "FIXTURE-T08-PUMP-EVENT-IDL-001": (
        "tests/fixtures/task08/pump_event_idl_subset_v1.json"
    ),
    "FIXTURE-T08-LIFECYCLE-DISCOVERY-EVIDENCE-001": (
        "tests/fixtures/task08/"
        "lifecycle_discovery_probe_live_evidence_v1.json"
    ),
    "TEST-T08-LIFECYCLE-DISCOVERY-001": (
        "tests/test_task08_lifecycle_discovery.py"
    ),
    "TEST-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001": (
        "tests/test_task08_lifecycle_discovery_transport.py"
    ),
    "TEST-T08-PUMP-EVENT-DECODER-001": (
        "tests/test_task08_pump_event_decoder.py"
    ),
    "TEST-T08-LIFECYCLE-DISCOVERY-EVIDENCE-001": (
        "tests/test_task08_lifecycle_discovery_probe_evidence.py"
    ),
    "TEST-T08-CATALOG-001": "tests/test_task08_catalog.py",
}

RAW_ASSET_ID = "DATA-T08-LIFECYCLE-DISCOVERY-PROBE-RAW-001"
TASK08_ASSET_IDS = set(EXPECTED_FILE_ASSETS) | {RAW_ASSET_ID}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relation_pairs(asset: dict[str, object]) -> set[tuple[str, str]]:
    return {
        (relation["relation_type"], relation["target_asset_id"])
        for relation in asset["relations"]
    }


class Task08CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_and_validate()

    def test_catalog_checkpoint_and_mandatory_inventory_are_exact(self) -> None:
        self.assertEqual(self.snapshot.manifest["catalog_version"], "0.9.0")
        self.assertEqual(len(self.snapshot.assets), 205)
        self.assertEqual(len(self.snapshot.queries), 7)
        self.assertTrue(
            TASK08_ASSET_IDS.issubset(
                set(self.snapshot.manifest["mandatory_asset_ids"])
            )
        )
        self.assertEqual(
            {
                asset_id
                for asset_id, asset in self.snapshot.assets.items()
                if asset["truth_owner"] == "TASK-08"
            },
            TASK08_ASSET_IDS,
        )

    def test_every_task08_file_resolves_by_stable_id_and_hash(self) -> None:
        for asset_id, relative in EXPECTED_FILE_ASSETS.items():
            with self.subTest(asset_id=asset_id):
                asset = self.snapshot.assets[asset_id]
                self.assertEqual(asset["truth_owner"], "TASK-08")
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
            "CONTRACT-T08-LIFECYCLE-DISCOVERY-001": {
                ("depends_on", "CONTRACT-T05-DATA-001"),
                ("derived_from", "PRE-GIT-TASK01-A019"),
                ("validated_by", "TEST-T08-LIFECYCLE-DISCOVERY-001"),
            },
            "CONTRACT-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001": {
                (
                    "depends_on",
                    "CONTRACT-T08-LIFECYCLE-DISCOVERY-001",
                ),
                ("depends_on", "CONTRACT-T06-RAW-STORAGE-001"),
                ("derived_from", "PRE-GIT-TASK01-A023"),
                (
                    "validated_by",
                    "TEST-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001",
                ),
                (
                    "evidenced_by",
                    "EVIDENCE-T08-LIFECYCLE-DISCOVERY-RECEIPT-001",
                ),
            },
            "MODULE-T08-LIFECYCLE-DISCOVERY-001": {
                (
                    "depends_on",
                    "CONTRACT-T08-LIFECYCLE-DISCOVERY-001",
                ),
                ("depends_on", "SCHEMA-T05-PYDANTIC-BOUNDARIES-001"),
                ("validated_by", "TEST-T08-LIFECYCLE-DISCOVERY-001"),
            },
            "MODULE-T08-PUMP-EVENT-DECODER-001": {
                (
                    "depends_on",
                    "FIXTURE-T08-PUMP-EVENT-IDL-001",
                ),
                ("depends_on", "SCHEMA-T05-PYDANTIC-BOUNDARIES-001"),
                ("validated_by", "TEST-T08-PUMP-EVENT-DECODER-001"),
            },
            "MODULE-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001": {
                (
                    "depends_on",
                    "CONTRACT-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001",
                ),
                (
                    "depends_on",
                    "MODULE-T08-LIFECYCLE-DISCOVERY-001",
                ),
                ("depends_on", "MODULE-T08-PUMP-EVENT-DECODER-001"),
                ("depends_on", "MODULE-T06-STORAGE-API-001"),
                (
                    "validated_by",
                    "TEST-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001",
                ),
            },
            "SCRIPT-T08-LIFECYCLE-DISCOVERY-PROBE-001": {
                (
                    "depends_on",
                    "MODULE-T08-LIFECYCLE-DISCOVERY-001",
                ),
                (
                    "depends_on",
                    "MODULE-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001",
                ),
                ("depends_on", "MODULE-T08-PUMP-EVENT-DECODER-001"),
                (
                    "validated_by",
                    "TEST-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001",
                ),
            },
        }
        for asset_id, expected in expected_edges.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(
                    relation_pairs(self.snapshot.assets[asset_id]),
                    expected,
                )

    def test_raw_pointer_is_logical_read_only_and_hash_bound(self) -> None:
        asset = self.snapshot.assets[RAW_ASSET_ID]
        self.assertEqual(asset["origin"], "RUNTIME")
        self.assertEqual(asset["status"], "IMPLEMENTED_UNVERIFIED")
        self.assertEqual(asset["location"]["kind"], "logical_only")
        self.assertNotIn("repository_path", asset["location"])
        self.assertEqual(
            asset["location"]["logical_uri"],
            "raw://task08_lifecycle_discovery_probe_v1/"
            "run=t08a5-20260725T084127Z/partitions/probe.parquet",
        )
        self.assertEqual(
            asset["integrity"]["sha256"],
            "079dc1401b4da3cf0e1d63d2b20210e017252f26d93c4dd2afd8af7d950fcb6a",
        )
        self.assertEqual(asset["access"]["mode"], "read_only")
        self.assertEqual(asset["access"]["method"], "runtime_attestation")
        self.assertFalse(asset["access"]["network_required"])
        self.assertFalse(asset["access"]["secrets_required"])
        self.assertFalse(asset["classification"]["contains_raw_data"])
        self.assertEqual(
            set(asset["consumers"]),
            {"TASK-08", "TASK-09", "TASK-11", "TASK-12"},
        )
        self.assertEqual(
            set(
                self.snapshot.assets[
                    "CONTRACT-T08-LIFECYCLE-DISCOVERY-001"
                ]["consumers"]
            ),
            {"TASK-08", "TASK-09", "TASK-11", "TASK-12"},
        )
        self.assertEqual(
            relation_pairs(asset),
            {
                (
                    "derived_from",
                    "MODULE-T08-LIFECYCLE-DISCOVERY-TRANSPORT-001",
                ),
                (
                    "evidenced_by",
                    "EVIDENCE-T08-LIFECYCLE-DISCOVERY-RECEIPT-001",
                ),
                (
                    "validated_by",
                    "TEST-T08-LIFECYCLE-DISCOVERY-EVIDENCE-001",
                ),
            },
        )

    def test_sanitized_evidence_lineage_is_explicit(self) -> None:
        fixture = relation_pairs(
            self.snapshot.assets[
                "FIXTURE-T08-LIFECYCLE-DISCOVERY-EVIDENCE-001"
            ]
        )
        receipt = relation_pairs(
            self.snapshot.assets[
                "EVIDENCE-T08-LIFECYCLE-DISCOVERY-RECEIPT-001"
            ]
        )
        summary = relation_pairs(
            self.snapshot.assets[
                "EVIDENCE-T08-LIFECYCLE-DISCOVERY-SUMMARY-001"
            ]
        )
        self.assertEqual(
            fixture,
            {
                ("derived_from", RAW_ASSET_ID),
                (
                    "validated_by",
                    "TEST-T08-LIFECYCLE-DISCOVERY-EVIDENCE-001",
                ),
            },
        )
        self.assertEqual(
            receipt,
            {
                (
                    "derived_from",
                    "FIXTURE-T08-LIFECYCLE-DISCOVERY-EVIDENCE-001",
                ),
                ("derived_from", RAW_ASSET_ID),
                (
                    "validated_by",
                    "TEST-T08-LIFECYCLE-DISCOVERY-EVIDENCE-001",
                ),
            },
        )
        self.assertEqual(
            summary,
            {
                (
                    "derived_from",
                    "FIXTURE-T08-LIFECYCLE-DISCOVERY-EVIDENCE-001",
                ),
                (
                    "evidenced_by",
                    "EVIDENCE-T08-LIFECYCLE-DISCOVERY-RECEIPT-001",
                ),
            },
        )

    def test_generated_navigation_contains_every_task08_asset(self) -> None:
        projection = json.loads(
            (ROOT / "catalog/generated/asset_edges.json").read_text(
                encoding="utf-8"
            )
        )
        projected_ids = {
            edge["source_asset_id"] for edge in projection["edges"]
        } | {
            edge["target_asset_id"] for edge in projection["edges"]
        }
        project_map = (ROOT / "docs/PROJECT_MAP.md").read_text(
            encoding="utf-8"
        )
        for asset_id in TASK08_ASSET_IDS:
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, projected_ids)
                self.assertIn(f"| {asset_id} |", project_map)


if __name__ == "__main__":
    unittest.main()
