from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    ROOT / "docs/evidence/task22/a4_acceptance_catalog_factory_fit_v1.json"
)
EXPECTED_RECEIPT_SHA256 = (
    "23e11802e9239f3f97b9395f28beffc190e85dcad2c51c7403a875077accd7c3"
)
EXPECTED_IDS = {
    "CONTRACT-T22-GROUP-AWARE-SPLIT-001",
    "CONFIG-T22-GROUP-AWARE-SPLIT-001",
    "TEST-T22-GROUP-AWARE-SPLIT-CONTRACT-001",
    "SCHEMA-T22-SPLIT-MANIFEST-001",
    "SCHEMA-T22-HOLDOUT-LEDGER-EXTENSION-001",
    "MODULE-T22-DATASET-SPLIT-001",
    "SCRIPT-T22-DATASET-SPLIT-001",
    "DATA-T22-SPLIT-MANIFEST-001",
    "EVIDENCE-T22-HOLDOUT-LEDGER-001",
    "EVIDENCE-T22-A3-ACCEPTANCE-001",
    "TEST-T22-DATASET-SPLIT-001",
    "EVIDENCE-T22-A4-ACCEPTANCE-001",
    "TEST-T22-A4-ACCEPTANCE-001",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def semantic_errors(receipt: dict) -> set[str]:
    errors: set[str] = set()
    result = receipt["accepted_result"]
    if result["outcome_values_read"] or result["outcome_paths_opened"]:
        errors.add("OUTCOME_LEAK")
    if result["validation"] != "NONE":
        errors.add("INVENTED_VALIDATION")
    if result["holdout_access"] != "DENY":
        errors.add("HOLDOUT_ACCESS_LEAK")
    if result["additional_collection_authorized"]:
        errors.add("COLLECTION_AUTHORITY_LEAK")
    followup = receipt["factory_fit"].get("durable_followup")
    if not followup or not followup.get("next_atom"):
        errors.add("DURABLE_ROUTE_MISSING")
    registered = set(receipt["catalog"]["registered_asset_ids"])
    if registered != EXPECTED_IDS:
        errors.add("CATALOG_GAP")
    return errors


class Task22AcceptanceCatalogFactoryFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt_bytes = RECEIPT_PATH.read_bytes()
        cls.receipt = json.loads(cls.receipt_bytes)

    def test_receipt_accepts_exact_a2_a3_candidate_without_outcome_access(
        self,
    ) -> None:
        self.assertEqual(sha256(RECEIPT_PATH), EXPECTED_RECEIPT_SHA256)
        self.assertEqual(
            self.receipt["status"],
            "PASS_WITH_DURABLE_FOLLOWUP",
        )
        result = self.receipt["accepted_result"]
        self.assertEqual(result["owner_verdict"], "EXTEND_EVIDENCE")
        self.assertEqual(result["development_candidate"], "T21-R2")
        self.assertEqual(result["validation"], "NONE")
        self.assertEqual(result["holdout_candidate"], "T21-R3")
        self.assertEqual(result["holdout_state"], "UNASSIGNED_UNOPENED")
        self.assertEqual(result["holdout_access"], "DENY")
        self.assertFalse(result["outcome_values_read"])
        self.assertEqual(result["outcome_paths_opened"], [])
        self.assertFalse(result["task23_outcome_analysis_authorized"])
        self.assertFalse(result["additional_collection_authorized"])

    def test_all_eleven_frozen_artifacts_match_exact_repository_bytes(
        self,
    ) -> None:
        artifacts = self.receipt["frozen_artifacts"]
        self.assertEqual(len(artifacts), 11)
        for artifact in artifacts:
            with self.subTest(asset_id=artifact["asset_id"]):
                self.assertEqual(
                    sha256(ROOT / artifact["path"]),
                    artifact["sha256"],
                )

    def test_six_adversarial_vectors_fail_closed(self) -> None:
        vectors: list[tuple[str, str, dict]] = []

        candidate = copy.deepcopy(self.receipt)
        candidate["accepted_result"]["outcome_values_read"] = True
        vectors.append(("outcome", "OUTCOME_LEAK", candidate))

        candidate = copy.deepcopy(self.receipt)
        candidate["accepted_result"]["validation"] = "T21-R1"
        vectors.append(("validation", "INVENTED_VALIDATION", candidate))

        candidate = copy.deepcopy(self.receipt)
        candidate["accepted_result"]["holdout_access"] = "ALLOW"
        vectors.append(("holdout", "HOLDOUT_ACCESS_LEAK", candidate))

        candidate = copy.deepcopy(self.receipt)
        candidate["accepted_result"]["additional_collection_authorized"] = True
        vectors.append(("collection", "COLLECTION_AUTHORITY_LEAK", candidate))

        candidate = copy.deepcopy(self.receipt)
        del candidate["factory_fit"]["durable_followup"]
        vectors.append(("followup", "DURABLE_ROUTE_MISSING", candidate))

        candidate = copy.deepcopy(self.receipt)
        candidate["catalog"]["registered_asset_ids"].pop()
        vectors.append(("catalog", "CATALOG_GAP", candidate))

        self.assertEqual(semantic_errors(self.receipt), set())
        self.assertEqual(len(vectors), 6)
        for vector_id, expected, candidate in vectors:
            with self.subTest(vector=vector_id):
                self.assertIn(expected, semantic_errors(candidate))

    def test_catalog_transaction_is_exact_and_hash_bound(self) -> None:
        manifest, records = load_catalog()
        self.assertGreaterEqual(
            tuple(map(int, manifest["catalog_version"].split("."))),
            (0, 27, 0),
        )
        checkpoint = manifest["current_checkpoint"]
        historical = {
            "assets": 387,
            "asset_registries": 4,
            "schemas": 6,
            "queries": 8,
            "lifecycle_registries": 9,
            "lifecycle_records": 52,
        }
        for field, value in historical.items():
            with self.subTest(field=field):
                self.assertGreaterEqual(checkpoint[field], value)
        self.assertEqual(len(records), checkpoint["assets"])
        self.assertEqual(
            set(self.receipt["catalog"]["registered_asset_ids"]),
            EXPECTED_IDS,
        )
        self.assertTrue(EXPECTED_IDS.issubset(records))
        for asset_id in EXPECTED_IDS:
            with self.subTest(asset_id=asset_id):
                record = records[asset_id]
                self.assertEqual(record["location"]["kind"], "git_path")
                relative = record["location"]["repository_path"]
                self.assertEqual(
                    sha256(ROOT / relative),
                    record["integrity"]["sha256"],
                )

    def test_factory_fit_routes_cheapest_honest_resolution_first(self) -> None:
        critic = self.receipt["factory_fit"]
        self.assertEqual(critic["mode"], "FULL_REVIEW")
        self.assertEqual(critic["verdict"], "PASS_WITH_DURABLE_FOLLOWUP")
        self.assertEqual(
            critic["bounded_correction"],
            "HORIZON_PROFILE_FIRST_NO_BLIND_RECOLLECTION",
        )
        self.assertEqual(len(critic["checks"]), 15)
        self.assertTrue(
            all(
                row["status"]
                in {"PASS", "PASS_WITH_LIMITATION", "NOT_APPLICABLE"}
                for row in critic["checks"]
            )
        )
        followup = critic["durable_followup"]
        self.assertEqual(
            followup["activation_trigger"],
            "BEFORE_ANY_OUTCOME_READ_OR_TASK23_OUTCOME_ANALYSIS",
        )
        self.assertEqual(
            followup["next_atom"],
            "T22-A5_CONSUMER_TIME_PROFILE_AND_SPLIT_RESOLUTION_V1",
        )
        self.assertEqual(len(followup["decision_branches"]), 3)

    def test_navigation_authority_nonclaims_and_hygiene_are_exact(self) -> None:
        project_map = (ROOT / "docs/PROJECT_MAP.md").read_text(
            encoding="utf-8"
        )
        edges = json.loads(
            (ROOT / "catalog/generated/asset_edges.json").read_bytes()
        )
        edge_ids = {edge["source_asset_id"] for edge in edges["edges"]}
        for asset_id in EXPECTED_IDS:
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, project_map)
                self.assertIn(asset_id, edge_ids)

        authority = self.receipt["authority"]
        self.assertTrue(authority["local_write_only"])
        for field, value in authority.items():
            if field != "local_write_only":
                with self.subTest(field=field):
                    self.assertIn(value, (0, False))
        self.assertIn("NOT_OUTCOME_ANALYSIS", self.receipt["nonclaims"])
        self.assertIn(
            "NOT_ADDITIONAL_COLLECTION_AUTHORITY",
            self.receipt["nonclaims"],
        )

        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\b[a-z]:[\\/]"),
            "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            "credential_assignment": re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)"
                r"\s*[:=]\s*[\"'][^\"']+[\"']"
            ),
        }
        for path in (RECEIPT_PATH, Path(__file__)):
            value = path.read_bytes()
            self.assertFalse(value.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r", value)
            self.assertTrue(value.endswith(b"\n"))
            text = value.decode("utf-8")
            self.assertTrue(
                all(line.rstrip(" \t") == line for line in text.splitlines())
            )
            for pattern in prohibited.values():
                self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
