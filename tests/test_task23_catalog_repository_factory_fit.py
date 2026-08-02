from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "docs/evidence/task23/a5_catalog_repository_factory_fit_v1.json"
EXPECTED_RECEIPT_SHA256 = (
    "7f840ac5fbdc6481dec592e529588b99d53a65e314587adeee98605dc94bab14"
)
NEW_IDS = {
    "CONTRACT-T23-BOUNDED-DIAGNOSTICS-001",
    "CONFIG-T23-BOUNDED-DIAGNOSTICS-001",
    "TEST-T23-BOUNDED-DIAGNOSTICS-CONTRACT-001",
    "QUERY-T23-R2-DIAGNOSTIC-PROJECTION-001",
    "EVIDENCE-T23-A3-PRE-READ-RECEIPT-001",
    "EVIDENCE-T23-A3-ATTEMPT-01-FAILURE-001",
    "EVIDENCE-T23-A3-PRE-READ-RECEIPT-002",
    "DATA-T23-PANEL-INVENTORY-001",
    "DATA-T23-QUOTE-PAIR-AVAILABILITY-001",
    "DATA-T23-PANEL-DIAGNOSTICS-001",
    "EVIDENCE-T23-A3-PROJECTION-MANIFEST-001",
    "TEST-T23-DIAGNOSTIC-PROJECTION-001",
    "MODULE-T23-BOUNDED-ANALYSIS-001",
    "EVIDENCE-T23-A4-BOUNDED-ANALYSIS-001",
    "REPORT-T23-COHORT-DIAGNOSTICS-001",
    "EVIDENCE-T23-A4-ADVERSARIAL-ACCEPTANCE-001",
    "TEST-T23-BOUNDED-ANALYSIS-001",
    "EVIDENCE-T23-A5-CATALOG-FACTORY-FIT-001",
    "TEST-T23-A5-CATALOG-FACTORY-FIT-001",
}
UPDATED_FILES = {
    "VALIDATOR-T04-ARCHITECTURE-001": (
        "scripts/validate_task04.py",
        "c8ab8c3f7116050f20cdbc6cf5aa708de4a3c6e01912670970c167087020c06b",
    ),
    "TEST-T16-HYPOTHESIS-RESEARCH-MEMORY-ACCEPTANCE-001": (
        "tests/test_task16_hypothesis_research_memory_acceptance.py",
        "aa905aba09ca05b53f3c1c47e8cd0b6ba470e915d4615235e703e5e198336bee",
    ),
    "TEST-T18-CATALOG-REPOSITORY-FINALIZATION-001": (
        "tests/test_task18_catalog_repository_finalization.py",
        "5f585b803715bdb752de534fdebbc39131644af3e94d5375592cf7480a5eeb16",
    ),
    "TEST-T20-ACCEPTANCE-CATALOG-FACTORY-FIT-001": (
        "tests/test_task20_acceptance_catalog_factory_fit.py",
        "c3a53a72560f10af982ac95919b9952434036e170aa1188d1c08ed8f02e38928",
    ),
    "TEST-T22-A6-ACCEPTANCE-001": (
        "tests/test_task22_split_resolution_acceptance_catalog_factory_fit.py",
        "60cf774bbe2bebc0df014baa17b0ecfccb6fb5d2b0ee726f34a3cdbcc02d9cb2",
    ),
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


def semantic_errors(receipt: dict) -> set[str]:
    errors: set[str] = set()
    accepted = receipt["accepted_result"]
    if accepted["r3_paths_discovered"] or accepted["r3_value_files_opened"]:
        errors.add("R3_LEAK")
    if accepted["validation"] != "NONE":
        errors.add("INVENTED_VALIDATION")
    if accepted["effective_independent_cluster_count_upper_bound"] > 1:
        errors.add("INVENTED_INDEPENDENCE")
    if accepted["route_id_continuity_claim"]:
        errors.add("ROUTE_CONTINUITY_OVERCLAIM")
    if set(receipt["catalog"]["registered_asset_ids"]) != NEW_IDS:
        errors.add("CATALOG_GAP")
    if receipt["next_gate"]["authorized"] or receipt["next_gate"]["r3_access_authorized"]:
        errors.add("AUTHORITY_LEAK")
    critic = receipt["factory_fit"]
    if critic["mode"] != "FULL_REVIEW" or len(critic["checks"]) != 15:
        errors.add("FACTORY_FIT_INCOMPLETE")
    return errors


class Task23CatalogRepositoryFactoryFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    def test_receipt_and_all_seventeen_a1_a4_assets_are_exact(self) -> None:
        self.assertEqual(sha256(RECEIPT_PATH), EXPECTED_RECEIPT_SHA256)
        artifacts = self.receipt["frozen_a1_a4_artifacts"]
        self.assertEqual(len(artifacts), 17)
        for artifact in artifacts:
            with self.subTest(asset_id=artifact["asset_id"]):
                self.assertEqual(
                    sha256(ROOT / artifact["path"]), artifact["sha256"]
                )

    def test_owner_decision_and_r3_boundary_remain_exact(self) -> None:
        accepted = self.receipt["accepted_result"]
        self.assertEqual(
            accepted["owner_decision"], "DIAGNOSTICS_READY_WITH_LIMITATIONS"
        )
        self.assertEqual(accepted["development"], "T21-R2")
        self.assertEqual(accepted["validation"], "NONE")
        self.assertEqual(accepted["holdout"], "T21-R3")
        self.assertEqual(accepted["holdout_state"], "UNTOUCHED")
        self.assertEqual(accepted["holdout_access"], "DENY")
        self.assertEqual(accepted["r3_paths_discovered"], 0)
        self.assertEqual(accepted["r3_value_files_opened"], 0)
        self.assertEqual(
            accepted["effective_independent_cluster_count_upper_bound"], 1
        )
        self.assertTrue(accepted["capacity_proxy_right_censored"])
        self.assertFalse(accepted["route_id_continuity_claim"])

    def test_catalog_transaction_is_exact_and_hash_bound(self) -> None:
        manifest, records = load_catalog()
        self.assertGreaterEqual(
            tuple(int(part) for part in manifest["catalog_version"].split(".")),
            (0, 28, 0),
        )
        checkpoint = manifest["current_checkpoint"]
        self.assertGreaterEqual(checkpoint["assets"], 415)
        self.assertEqual(checkpoint["asset_registries"], 4)
        self.assertEqual(checkpoint["schemas"], 7)
        self.assertEqual(checkpoint["queries"], 8)
        self.assertEqual(checkpoint["lifecycle_registries"], 9)
        self.assertGreaterEqual(checkpoint["lifecycle_records"], 55)
        self.assertEqual(len(records), checkpoint["assets"])
        self.assertEqual(set(self.receipt["catalog"]["registered_asset_ids"]), NEW_IDS)
        self.assertTrue(NEW_IDS.issubset(records))
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                record = records[asset_id]
                relative = record["location"]["repository_path"]
                self.assertEqual(sha256(ROOT / relative), record["integrity"]["sha256"])

    def test_trials_are_append_only_and_all_evidence_ids_resolve(self) -> None:
        _, records = load_catalog()
        ledger = yaml.safe_load(
            (ROOT / "registries/global_trial_ledger.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(len(ledger["records"]), 3)
        self.assertEqual(
            [record["outcome"] for record in ledger["records"]],
            ["FAIL", "INCONCLUSIVE", "INCONCLUSIVE"],
        )
        for record in ledger["records"]:
            for evidence_asset_id in record["evidence_asset_ids"]:
                with self.subTest(evidence_asset_id=evidence_asset_id):
                    self.assertIn(evidence_asset_id, records)

    def test_historical_consumers_are_monotonic_and_catalog_bound(self) -> None:
        _, records = load_catalog()
        self.assertEqual(set(UPDATED_FILES), set(self.receipt["catalog"]["updated_asset_ids"]) - {
            "REGISTRY-GLOBAL-TRIAL-LEDGER-001",
            "GENERATED-PROJECT-MAP-001",
            "GENERATED-EDGE-PROJECTION-001",
        })
        for asset_id, (relative, expected_hash) in UPDATED_FILES.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(sha256(ROOT / relative), expected_hash)
                self.assertEqual(records[asset_id]["integrity"]["sha256"], expected_hash)

    def test_full_factory_fit_and_durable_holdout_gate_are_complete(self) -> None:
        critic = self.receipt["factory_fit"]
        self.assertEqual(critic["mode"], "FULL_REVIEW")
        self.assertEqual(
            critic["verdict"], "PASS_WITH_LIMITATIONS_AND_DURABLE_FOLLOWUP"
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
            "BEFORE_FIRST_EXACT_R3_OUTCOME_VALUE_READ",
        )
        self.assertIn("APPEND_CONSUMED_EVENT", followup["required_action"])

    def test_seven_adversarial_vectors_fail_closed(self) -> None:
        vectors: list[tuple[str, str, dict]] = []
        for label, expected, mutate in (
            ("r3", "R3_LEAK", lambda value: value["accepted_result"].__setitem__("r3_paths_discovered", 1)),
            ("validation", "INVENTED_VALIDATION", lambda value: value["accepted_result"].__setitem__("validation", "T21-R3")),
            ("independence", "INVENTED_INDEPENDENCE", lambda value: value["accepted_result"].__setitem__("effective_independent_cluster_count_upper_bound", 36)),
            ("continuity", "ROUTE_CONTINUITY_OVERCLAIM", lambda value: value["accepted_result"].__setitem__("route_id_continuity_claim", True)),
            ("catalog", "CATALOG_GAP", lambda value: value["catalog"]["registered_asset_ids"].pop()),
            ("authority", "AUTHORITY_LEAK", lambda value: value["next_gate"].__setitem__("r3_access_authorized", True)),
            ("factory_fit", "FACTORY_FIT_INCOMPLETE", lambda value: value["factory_fit"]["checks"].pop()),
        ):
            candidate = copy.deepcopy(self.receipt)
            mutate(candidate)
            vectors.append((label, expected, candidate))
        self.assertEqual(semantic_errors(self.receipt), set())
        self.assertEqual(len(vectors), 7)
        for label, expected, candidate in vectors:
            with self.subTest(vector=label):
                self.assertIn(expected, semantic_errors(candidate))

    def test_navigation_authority_nonclaims_and_hygiene_are_exact(self) -> None:
        project_map = (ROOT / "docs/PROJECT_MAP.md").read_text(encoding="utf-8")
        edges = json.loads(
            (ROOT / "catalog/generated/asset_edges.json").read_text(encoding="utf-8")
        )
        edge_ids = {edge["source_asset_id"] for edge in edges["edges"]}
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, project_map)
                self.assertIn(asset_id, edge_ids)

        authority = self.receipt["authority"]
        self.assertTrue(authority["local_write_only"])
        for field, value in authority.items():
            if field != "local_write_only":
                with self.subTest(field=field):
                    self.assertIn(value, (0, False))
        self.assertIn("NOT_R3_OR_OUTCOME_ANALYSIS", self.receipt["nonclaims"])
        self.assertFalse(self.receipt["next_gate"]["authorized"])

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
