from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    ROOT
    / "docs/evidence/task22/a6_split_resolution_acceptance_catalog_factory_fit_v1.json"
)
EXPECTED_RECEIPT_SHA256 = (
    "29c1ad28d06430b74864b745ef50bf0315fcbfcfb5a7534e54b1692a3f15a019"
)
NEW_IDS = {
    "CONFIG-T22-CONSUMER-TIME-PROFILE-001",
    "SCHEMA-T22-SPLIT-RESOLUTION-001",
    "MODULE-T22-SPLIT-RESOLUTION-001",
    "SCRIPT-T22-SPLIT-RESOLUTION-001",
    "DATA-T22-SPLIT-MANIFEST-002",
    "EVIDENCE-T22-HOLDOUT-LEDGER-002",
    "TEST-T22-SPLIT-RESOLUTION-001",
    "EVIDENCE-T22-A6-ACCEPTANCE-001",
    "TEST-T22-A6-ACCEPTANCE-001",
}
UPDATED_TESTS = {
    "TEST-T17A-EXECUTION-CAPACITY-AUDIT-001": (
        "tests/test_task17a_execution_capacity_audit.py",
        "26db813bea589de2e352f3cad6996b6e8ae24875989bfc8ebe63bfe2a82d8879",
    ),
    "TEST-T19-ACCEPTANCE-CATALOG-FACTORY-FIT-001": (
        "tests/test_task19_acceptance_catalog_factory_fit.py",
        "6abf34a1533c3f95c46ec48bdfeb93b2cdd27b54d8c757b41ad297c49338ee44",
    ),
    "TEST-T20-ACCEPTANCE-CATALOG-FACTORY-FIT-001": (
        "tests/test_task20_acceptance_catalog_factory_fit.py",
        "79f4d1fadd1ac8010d1a04d7354a9bd964ddd2995ae638d1a202c410e5cfa010",
    ),
    "TEST-T21-A7-ACCEPTANCE-001": (
        "tests/test_task21_dataset_freeze_acceptance.py",
        "654638663901460ca136e40d006632719d939e1a3f2dd064afaed5f881b04471",
    ),
    "TEST-T22-A4-ACCEPTANCE-001": (
        "tests/test_task22_acceptance_catalog_factory_fit.py",
        "8921fd3971dbee8eaa68b255300d8de4ae350998b325eda7b20265d12c1473f4",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_bytes())


def load_catalog() -> tuple[dict, dict[str, dict]]:
    manifest = yaml.safe_load(
        (ROOT / "catalog/catalog_manifest.yaml").read_bytes()
    )
    documents = [
        yaml.safe_load((ROOT / relative).read_bytes())
        for relative in manifest["root_resolver"]["asset_registries"]
    ]
    records = {
        record["asset_id"]: record
        for document in documents
        for record in document["records"]
    }
    return manifest, records


class Task22SplitResolutionAcceptanceCatalogFactoryFitTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = load_json(
            "docs/evidence/task22/a6_split_resolution_acceptance_catalog_factory_fit_v1.json"
        )
        cls.split = load_json(
            "docs/evidence/task22/dataset_split_manifest_v2.json"
        )
        cls.ledger = load_json(
            "docs/evidence/task22/holdout_access_ledger_v2.json"
        )

    def test_receipt_and_all_seven_a5_artifacts_are_exact(self) -> None:
        self.assertEqual(sha256(RECEIPT_PATH), EXPECTED_RECEIPT_SHA256)
        artifacts = self.receipt["frozen_a5_artifacts"]
        self.assertEqual(len(artifacts), 7)
        for artifact in artifacts:
            with self.subTest(asset_id=artifact["asset_id"]):
                self.assertEqual(
                    sha256(ROOT / artifact["path"]),
                    artifact["sha256"],
                )

    def test_split_is_ready_for_only_the_named_consumer(self) -> None:
        accepted = self.receipt["accepted_result"]
        self.assertEqual(accepted["owner_verdict"], "SPLIT_READY_WITH_LIMITATIONS")
        self.assertEqual(accepted["consumer_profile_id"], self.split["consumer_profile"]["profile_id"])
        self.assertEqual(accepted["development"], "T21-R2")
        self.assertEqual(accepted["validation"], "NONE")
        self.assertEqual(accepted["holdout"], "T21-R3")
        self.assertEqual(accepted["holdout_state"], "UNTOUCHED")
        self.assertEqual(accepted["holdout_access"], "DENY")
        self.assertFalse(accepted["task23_started"])
        self.assertFalse(accepted["task23_outcome_access_authorized"])
        self.assertFalse(accepted["additional_collection_required"])

    def test_outcomes_remain_unopened_and_first_access_is_append_only(self) -> None:
        accepted = self.receipt["accepted_result"]
        self.assertEqual(accepted["outcome_state"], "UNOPENED")
        self.assertFalse(accepted["outcome_values_read"])
        self.assertEqual(accepted["outcome_paths_opened"], [])
        self.assertEqual(self.ledger["state"]["current"], "UNTOUCHED")
        self.assertEqual(self.ledger["state"]["access_default"], "DENY")
        self.assertEqual(self.ledger["records"], [])
        self.assertFalse(
            self.ledger["registry_binding"][
                "consumption_record_appended_in_atom5"
            ]
        )
        followup = self.receipt["factory_fit"]["durable_followup"]
        self.assertIn("APPEND_CONSUMED_EVENT", followup["required_action"])

    def test_temporal_resolution_uses_measured_time_and_real_embargo(self) -> None:
        accepted = self.receipt["accepted_result"]
        temporal = self.split["temporal_resolution"]
        self.assertEqual(accepted["pre_embargo_gap_seconds"], 1701.306244)
        self.assertEqual(accepted["required_embargo_seconds"], 900)
        self.assertAlmostEqual(
            accepted["post_embargo_slack_seconds"],
            801.306244,
            places=6,
        )
        self.assertEqual(accepted["purged_development_members"], [])
        self.assertTrue(temporal["actual_timestamps_used"])
        self.assertFalse(temporal["source_start_gap_alone_used"])
        self.assertIn(
            "EXACT_15_MINUTE_OUTCOME",
            self.split["claim_boundary"]["forbidden"],
        )

    def test_catalog_transaction_is_exact_and_hash_bound(self) -> None:
        manifest, records = load_catalog()
        self.assertEqual(manifest["catalog_version"], "0.27.1")
        self.assertEqual(
            manifest["current_checkpoint"],
            {
                "assets": 396,
                "asset_registries": 4,
                "schemas": 7,
                "queries": 8,
                "lifecycle_registries": 9,
                "lifecycle_records": 52,
            },
        )
        self.assertEqual(len(records), 396)
        self.assertEqual(
            set(self.receipt["catalog"]["registered_asset_ids"]),
            NEW_IDS,
        )
        self.assertTrue(NEW_IDS.issubset(records))
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                record = records[asset_id]
                relative = record["location"]["repository_path"]
                self.assertEqual(
                    sha256(ROOT / relative),
                    record["integrity"]["sha256"],
                )

    def test_historical_catalog_tests_are_forward_compatible_and_registered(self) -> None:
        _, records = load_catalog()
        self.assertEqual(
            set(self.receipt["catalog"]["updated_forward_compatibility_asset_ids"]),
            set(UPDATED_TESTS),
        )
        for asset_id, (relative, expected_hash) in UPDATED_TESTS.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(sha256(ROOT / relative), expected_hash)
                self.assertEqual(
                    records[asset_id]["integrity"]["sha256"],
                    expected_hash,
                )
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertNotIn(
                    'assertEqual(checkpoint["schemas"], 4)',
                    text,
                )

    def test_factory_fit_authority_nonclaims_and_next_gate_are_bounded(self) -> None:
        critic = self.receipt["factory_fit"]
        self.assertEqual(critic["mode"], "FULL_REVIEW")
        self.assertEqual(
            critic["verdict"],
            "PASS_WITH_LIMITATIONS_AND_DURABLE_FOLLOWUP",
        )
        self.assertEqual(len(critic["checks"]), 15)
        self.assertTrue(
            all(
                row["status"]
                in {"PASS", "PASS_WITH_LIMITATION", "NOT_APPLICABLE"}
                for row in critic["checks"]
            )
        )
        authority = self.receipt["authority"]
        self.assertTrue(authority["local_write_only"])
        for field, value in authority.items():
            if field != "local_write_only":
                with self.subTest(field=field):
                    self.assertIn(value, (0, False))
        self.assertIn("NOT_OUTCOME_ANALYSIS", self.receipt["nonclaims"])
        self.assertFalse(self.receipt["next_gate"]["authorized"])
        self.assertFalse(self.receipt["next_gate"]["task23_authorized"])

    def test_generated_navigation_and_authored_file_hygiene_are_exact(self) -> None:
        project_map = (ROOT / "docs/PROJECT_MAP.md").read_text(
            encoding="utf-8"
        )
        edges = load_json("catalog/generated/asset_edges.json")
        edge_ids = {edge["source_asset_id"] for edge in edges["edges"]}
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, project_map)
                self.assertIn(asset_id, edge_ids)

        paths = [
            RECEIPT_PATH,
            Path(__file__),
            *[ROOT / relative for relative, _ in UPDATED_TESTS.values()],
        ]
        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\b[a-z]:[\\/]"),
            "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            "credential_assignment": re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)"
                r"\s*[:=]\s*[\"'][^\"']+[\"']"
            ),
        }
        for path in paths:
            with self.subTest(path=path.as_posix()):
                value = path.read_bytes()
                self.assertFalse(value.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", value)
                self.assertTrue(value.endswith(b"\n"))
                text = value.decode("utf-8")
                self.assertTrue(
                    all(
                        line.rstrip(" \t") == line
                        for line in text.splitlines()
                    )
                )
                for pattern in prohibited.values():
                    self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
