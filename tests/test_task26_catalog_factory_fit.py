from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "docs/evidence/task26/a7_catalog_factory_fit_v1.json"
EXPECTED_RECEIPT_SHA256 = "74fc6fc5086014ca33a7db8bf5de566c7a7639dc2aced5f5c02253286cb7b1bc"
NEW_IDS = {
    "CONTRACT-T26-EXECUTION-COST-NETRETURN-001",
    "CONFIG-T26-EXECUTION-COST-NETRETURN-001",
    "SCHEMA-T26-EXECUTION-COST-NETRETURN-001",
    "FIXTURE-T26-EXECUTION-COST-NETRETURN-001",
    "TEST-T26-EXECUTION-COST-NETRETURN-001",
    "EVIDENCE-T26-A2-ACCEPTANCE-001",
    "MODULE-T26-EXECUTION-COST-MODEL-001",
    "TEST-T26-EXECUTION-COST-MODEL-001",
    "DATA-T26-SYNTHETIC-EXECUTION-COST-PROJECTION-001",
    "EVIDENCE-T26-A3-ACCEPTANCE-001",
    "MODULE-T26-ADVERSARIAL-ACCEPTANCE-001",
    "TEST-T26-ADVERSARIAL-ACCEPTANCE-001",
    "EVIDENCE-T26-A4-ACCEPTANCE-001",
    "MODULE-T26-R2-EXECUTION-COST-PROJECTION-001",
    "TEST-T26-R2-EXECUTION-COST-PROJECTION-001",
    "DATA-T26-R2-EXECUTION-COST-INPUT-PROJECTION-001",
    "EVIDENCE-T26-A5-ACCEPTANCE-001",
    "FIXTURE-T26-R2-EXECUTION-COST-ADVERSARIAL-MATRIX-001",
    "MODULE-T26-R2-ADVERSARIAL-ACCEPTANCE-001",
    "TEST-T26-R2-ADVERSARIAL-ACCEPTANCE-001",
    "EVIDENCE-T26-A6-ACCEPTANCE-001",
    "EVIDENCE-T26-A7-CATALOG-FACTORY-FIT-001",
    "TEST-T26-A7-CATALOG-FACTORY-FIT-001",
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
    if accepted["owner_decision"] != "EXTEND_EXECUTION_EVIDENCE":
        errors.add("OWNER_DECISION_DRIFT")
    if (accepted["quote_pairs"], accepted["quote_cost_input_ready_pairs"]) != (36, 35):
        errors.add("QUOTE_PAIR_DENOMINATOR_DRIFT")
    if accepted["latency_blocked_pairs"] != 1:
        errors.add("LATENCY_BLOCKER_ERASED")
    if accepted["modeled_numeric_netreturn_claims"] != 0 or accepted[
        "actual_fill_or_settlement_claims"
    ] != 0:
        errors.add("NETRETURN_OR_FILL_PROMOTION")
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
        errors.add("DELIVERY_AUTO_AUTHORIZED")
    return errors


class Task26CatalogFactoryFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_bytes())

    def test_01_receipt_hash_and_owner_result_are_exact(self) -> None:
        self.assertEqual(sha256(RECEIPT_PATH), EXPECTED_RECEIPT_SHA256)
        self.assertEqual(semantic_errors(self.receipt), set())
        accepted = self.receipt["accepted_result"]
        self.assertEqual(accepted["execution_cost_model"], "READY_WITH_LIMITATIONS")
        self.assertEqual(accepted["netreturn_surface"], "NOT_COMPUTABLE_FOR_36_OF_36_R2_PAIRS")

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
                self.assertEqual(sha256(ROOT / relative), record["integrity"]["sha256"])

    def test_04_schema_and_task27_consumer_are_registered(self) -> None:
        manifest, records = load_catalog()
        relative = "catalog/schemas/task26_execution_cost_and_netreturn.schema.json"
        self.assertIn(relative, manifest["root_resolver"]["schemas"])
        schema = records["SCHEMA-T26-EXECUTION-COST-NETRETURN-001"]
        self.assertEqual(schema["asset_type"], "schema")
        self.assertIn("TASK-27", schema["consumers"])
        self.assertIn(
            "CONTRACT-T26-EXECUTION-COST-NETRETURN-001",
            {row["target_asset_id"] for row in schema["relations"]},
        )

    def test_05_factory_fit_retains_the_execution_evidence_gap(self) -> None:
        critic = self.receipt["factory_fit"]
        self.assertEqual(critic["mode"], "FULL_REVIEW")
        self.assertEqual(critic["verdict"], "PASS_WITH_FOLLOWUP")
        self.assertEqual(len(critic["checks"]), 15)
        self.assertIn("TASK26_EXECUTION_EVIDENCE_EXTENSION_DECISION", critic["durable_followup"]["destination"])

    def test_06_navigation_contains_every_registered_asset(self) -> None:
        project_map = (ROOT / "docs/PROJECT_MAP.md").read_text(encoding="utf-8")
        edges = json.loads(
            (ROOT / "catalog/generated/asset_edges.json").read_text(encoding="utf-8")
        )
        edge_sources = {row["source_asset_id"] for row in edges["edges"]}
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, project_map)
                self.assertIn(asset_id, edge_sources)

    def test_07_authority_reconciliation_and_next_boundary_are_closed(self) -> None:
        authority = self.receipt["authority"]
        self.assertTrue(authority["local_write_only"])
        self.assertEqual(authority["catalog_mutations"], 1)
        for key, value in authority.items():
            if key not in {"local_write_only", "catalog_mutations"}:
                self.assertIn(value, (0, False), key)
        history = self.receipt["historical_contract_reconciliation"]
        self.assertEqual(history["actual_registration_atom"], self.receipt["atom_id"])
        self.assertFalse(self.receipt["next_boundary"]["authorized"])
        self.assertEqual(self.receipt["next_boundary"]["r3_access"], "DENY")

    def test_08_adversarial_receipt_mutations_fail_closed(self) -> None:
        mutations = [
            ("OWNER_DECISION_DRIFT", lambda value: value["accepted_result"].__setitem__("owner_decision", "PROMOTE")),
            ("QUOTE_PAIR_DENOMINATOR_DRIFT", lambda value: value["accepted_result"].__setitem__("quote_cost_input_ready_pairs", 36)),
            ("LATENCY_BLOCKER_ERASED", lambda value: value["accepted_result"].__setitem__("latency_blocked_pairs", 0)),
            ("NETRETURN_OR_FILL_PROMOTION", lambda value: value["accepted_result"].__setitem__("modeled_numeric_netreturn_claims", 1)),
            ("R3_BOUNDARY_BREACHED", lambda value: value["accepted_result"].__setitem__("r3_paths_or_values_read", 1)),
            ("CATALOG_GAP", lambda value: value["catalog"]["registered_asset_ids"].pop()),
            ("FACTORY_FIT_INCOMPLETE", lambda value: value["factory_fit"]["checks"].pop()),
            ("FOLLOWUP_ERASED", lambda value: value["factory_fit"].__setitem__("verdict", "PASS")),
            ("DELIVERY_AUTO_AUTHORIZED", lambda value: value["next_boundary"].__setitem__("authorized", True)),
        ]
        for expected, mutate in mutations:
            with self.subTest(expected=expected):
                changed = copy.deepcopy(self.receipt)
                mutate(changed)
                self.assertIn(expected, semantic_errors(changed))

    def test_09_hygiene_and_secret_boundaries_are_exact(self) -> None:
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
            self.assertTrue(all(line.rstrip(" \t") == line for line in text.splitlines()))
            for pattern in prohibited.values():
                self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
