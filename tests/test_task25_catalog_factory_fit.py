from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "docs/evidence/task25/a6_catalog_factory_fit_v1.json"
EXPECTED_RECEIPT_SHA256 = (
    "187a508abb78b9f5548ec0d9677424ddfc60c746b51ee3975c5794b30745b41a"
)
NEW_IDS = {
    "CONTRACT-T25-OUTCOME-LABEL-PIT-001",
    "CONFIG-T25-OUTCOME-LABEL-PIT-001",
    "SCHEMA-T25-OUTCOME-EVIDENCE-001",
    "FIXTURE-T25-OUTCOME-LABEL-CONTRACT-001",
    "TEST-T25-OUTCOME-LABEL-PIT-CONTRACT-001",
    "EVIDENCE-T25-A2-ACCEPTANCE-001",
    "MODULE-T25-OUTCOME-ENGINE-001",
    "TEST-T25-OUTCOME-ENGINE-001",
    "DATA-T25-GOLDEN-OUTCOME-PROJECTION-001",
    "EVIDENCE-T25-A3-ACCEPTANCE-001",
    "MODULE-T25-R2-OUTCOME-PROJECTION-001",
    "TEST-T25-R2-OUTCOME-PROJECTION-001",
    "EVIDENCE-T25-A4-PRE-READ-MANIFEST-001",
    "DATA-T25-R2-OUTCOME-PROJECTION-001",
    "EVIDENCE-T25-A4-ACCEPTANCE-001",
    "DECISION-T25-R2-OUTCOME-REDESIGN-001",
    "FIXTURE-T25-A5-ADVERSARIAL-MATRIX-001",
    "MODULE-T25-ADVERSARIAL-ACCEPTANCE-001",
    "TEST-T25-ADVERSARIAL-ACCEPTANCE-001",
    "EVIDENCE-T25-A5-DECISION-001",
    "EVIDENCE-T25-A5R1-PRE-READ-MANIFEST-001",
    "MODULE-T25-EXACT-R2-OUTCOME-REPROJECTION-001",
    "FIXTURE-T25-A5R1-QUOTE-CLASSIFIER-001",
    "TEST-T25-EXACT-R2-OUTCOME-REPROJECTION-001",
    "DATA-T25-EXACT-R2-OUTCOME-SURFACE-001",
    "EVIDENCE-T25-A5R1-ACCEPTANCE-001",
    "EVIDENCE-T25-A6-CATALOG-FACTORY-FIT-001",
    "TEST-T25-A6-CATALOG-FACTORY-FIT-001",
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
    if accepted["owner_decision"] != (
        "R2_OUTCOME_SURFACE_READY_FOR_BOUNDED_OWNER_COMPARISON_WITH_LIMITATIONS"
    ):
        errors.add("OWNER_DECISION_DRIFT")
    if (accepted["supported"], accepted["unknown"]) != (80, 28):
        errors.add("OUTCOME_DENOMINATOR_DRIFT")
    if accepted["actual_fills_observed"] != 0 or accepted[
        "strategy_or_live_promotion_admissibility"
    ] != "NOT_ADMISSIBLE":
        errors.add("QUOTE_PROMOTED_TO_EXECUTION")
    if accepted["r3_paths_or_values_read"] != 0:
        errors.add("R3_BOUNDARY_BREACHED")
    if set(receipt["catalog"]["registered_asset_ids"]) != NEW_IDS:
        errors.add("CATALOG_GAP")
    critic = receipt["factory_fit"]
    if critic["mode"] != "FULL_REVIEW" or len(critic["checks"]) != 15:
        errors.add("FACTORY_FIT_INCOMPLETE")
    if critic["verdict"] != "PASS_WITH_FOLLOWUP" or not critic.get(
        "durable_followup"
    ):
        errors.add("FOLLOWUP_ERASED")
    if receipt["next_boundary"]["authorized"]:
        errors.add("A7_AUTO_AUTHORIZED")
    return errors


class Task25CatalogFactoryFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_bytes())

    def test_01_receipt_hash_and_owner_result_are_exact(self) -> None:
        self.assertEqual(sha256(RECEIPT_PATH), EXPECTED_RECEIPT_SHA256)
        self.assertEqual(semantic_errors(self.receipt), set())
        accepted = self.receipt["accepted_result"]
        self.assertEqual(accepted["fillable_supported"], 35)
        self.assertEqual(accepted["fillable_unknown"], 1)
        self.assertEqual(accepted["quote_exit_supported"], 36)
        self.assertEqual(accepted["path_risk_discrete_supported"], 9)

    def test_02_critical_bindings_are_hash_exact(self) -> None:
        for binding in self.receipt["critical_bindings"]:
            with self.subTest(asset_id=binding["asset_id"]):
                self.assertEqual(sha256(ROOT / binding["path"]), binding["sha256"])

    def test_03_catalog_transaction_and_registered_hashes_are_exact(self) -> None:
        manifest, records = load_catalog()
        transaction = self.receipt["catalog"]
        self.assertGreaterEqual(
            tuple(map(int, manifest["catalog_version"].split("."))),
            tuple(map(int, transaction["after_version"].split("."))),
        )
        checkpoint = manifest["current_checkpoint"]
        self.assertGreaterEqual(checkpoint["assets"], transaction["after_assets"])
        self.assertGreaterEqual(checkpoint["schemas"], transaction["after_schemas"])
        self.assertEqual(len(records), checkpoint["assets"])
        self.assertEqual(set(transaction["registered_asset_ids"]), NEW_IDS)
        self.assertTrue(NEW_IDS.issubset(records))
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                record = records[asset_id]
                relative = record["location"]["repository_path"]
                self.assertEqual(
                    sha256(ROOT / relative), record["integrity"]["sha256"]
                )

    def test_04_schema_is_registered_as_a_catalog_schema(self) -> None:
        manifest, records = load_catalog()
        relative = "catalog/schemas/task25_outcome_evidence.schema.json"
        self.assertIn(relative, manifest["root_resolver"]["schemas"])
        schema = records["SCHEMA-T25-OUTCOME-EVIDENCE-001"]
        self.assertEqual(schema["asset_type"], "schema")
        self.assertEqual(schema["location"]["repository_path"], relative)
        self.assertIn(
            "CONTRACT-T25-OUTCOME-LABEL-PIT-001",
            {row["target_asset_id"] for row in schema["relations"]},
        )

    def test_05_exact_surface_retains_truth_boundaries(self) -> None:
        _, records = load_catalog()
        surface_record = records["DATA-T25-EXACT-R2-OUTCOME-SURFACE-001"]
        targets = {row["target_asset_id"] for row in surface_record["relations"]}
        self.assertIn("EVIDENCE-T25-A5R1-PRE-READ-MANIFEST-001", targets)
        self.assertIn("EVIDENCE-T25-A5R1-ACCEPTANCE-001", targets)
        surface = json.loads(
            (ROOT / surface_record["location"]["repository_path"]).read_bytes()
        )
        self.assertEqual(surface["summary"]["assessments"], {"SUPPORTED": 80, "UNKNOWN": 28})
        self.assertEqual(surface["summary"]["r3_paths_or_values_read"], 0)
        self.assertEqual(surface["summary"]["unknown_values_coerced_to_zero"], 0)

    def test_06_full_factory_fit_and_followup_are_complete(self) -> None:
        critic = self.receipt["factory_fit"]
        self.assertEqual(critic["mode"], "FULL_REVIEW")
        self.assertEqual(critic["verdict"], "PASS_WITH_FOLLOWUP")
        self.assertEqual(len(critic["checks"]), 15)
        self.assertTrue(
            all(
                row["status"] in {"PASS", "FOLLOWUP", "NOT_APPLICABLE"}
                for row in critic["checks"]
            )
        )
        followup = critic["durable_followup"]
        self.assertEqual(followup["owner"], "TASK-26_ENTRY_GATE")
        self.assertEqual(
            followup["destination"], "TASK-26_EXECUTION_COST_AND_NETRETURN_MODEL"
        )

    def test_07_navigation_contains_every_new_asset_and_relation_source(self) -> None:
        project_map = (ROOT / "docs/PROJECT_MAP.md").read_text(encoding="utf-8")
        edges = json.loads(
            (ROOT / "catalog/generated/asset_edges.json").read_text(encoding="utf-8")
        )
        edge_sources = {row["source_asset_id"] for row in edges["edges"]}
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, project_map)
                self.assertIn(asset_id, edge_sources)

    def test_08_authority_finish_state_and_next_boundary_are_closed(self) -> None:
        authority = self.receipt["authority"]
        self.assertTrue(authority["local_write_only"])
        for key, value in authority.items():
            if key not in {"local_write_only", "catalog_mutations"}:
                self.assertIn(value, (0, False), key)
        self.assertEqual(authority["catalog_mutations"], 1)
        self.assertEqual(self.receipt["finish_gate"], "CONTINUE_CURRENT_TASK")
        self.assertEqual(
            self.receipt["next_boundary"]["atom"],
            "T25-A7_REPOSITORY_DELIVERY_V1",
        )
        self.assertFalse(self.receipt["next_boundary"]["authorized"])
        self.assertEqual(self.receipt["next_boundary"]["r3_access"], "DENY")

    def test_09_adversarial_receipt_mutations_fail_closed(self) -> None:
        mutations = [
            ("OWNER_DECISION_DRIFT", lambda value: value["accepted_result"].__setitem__("owner_decision", "PROMOTE")),
            ("OUTCOME_DENOMINATOR_DRIFT", lambda value: value["accepted_result"].__setitem__("supported", 81)),
            ("QUOTE_PROMOTED_TO_EXECUTION", lambda value: value["accepted_result"].__setitem__("actual_fills_observed", 1)),
            ("R3_BOUNDARY_BREACHED", lambda value: value["accepted_result"].__setitem__("r3_paths_or_values_read", 1)),
            ("CATALOG_GAP", lambda value: value["catalog"]["registered_asset_ids"].pop()),
            ("FACTORY_FIT_INCOMPLETE", lambda value: value["factory_fit"]["checks"].pop()),
            ("FOLLOWUP_ERASED", lambda value: value["factory_fit"].__setitem__("verdict", "PASS")),
            ("A7_AUTO_AUTHORIZED", lambda value: value["next_boundary"].__setitem__("authorized", True)),
        ]
        for expected, mutate in mutations:
            with self.subTest(expected=expected):
                changed = copy.deepcopy(self.receipt)
                mutate(changed)
                self.assertIn(expected, semantic_errors(changed))

    def test_10_hygiene_and_secret_boundaries_are_exact(self) -> None:
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
