from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "docs/evidence/task24/a7_catalog_factory_fit_v1.json"
EXPECTED_RECEIPT_SHA256 = "63b6feb5a1d084e27a51a40c3223c06a298cdb74ef40f85107221ce57b4b9fec"
NEW_IDS = {
    "CONTRACT-T24-ENTITY-GRAPH-001",
    "CONFIG-T24-ENTITY-GRAPH-001",
    "TEST-T24-ENTITY-GRAPH-CONTRACT-001",
    "EVIDENCE-T24-A2-ACCEPTANCE-001",
    "MODULE-T24-ENTITY-EVIDENCE-PROJECTION-001",
    "TEST-T24-ENTITY-EVIDENCE-PROJECTION-001",
    "EVIDENCE-T24-A3-PRE-READ-MANIFEST-001",
    "EVIDENCE-T24-A3-PROJECTION-MANIFEST-001",
    "EVIDENCE-T24-A3-ACCEPTANCE-001",
    "DECISION-T24-ENTITY-LINKAGE-EXTENSION-001",
    "CONFIG-T24-ENTITY-LINKAGE-EXTENSION-001",
    "TEST-T24-ENTITY-LINKAGE-EXTENSION-001",
    "EVIDENCE-T24-A4-DECISION-001",
    "MODULE-T24-ENTITY-LINKAGE-CAPTURE-001",
    "TEST-T24-ENTITY-LINKAGE-CAPTURE-001",
    "MODULE-T24-ENTITY-LINKAGE-PROJECTION-001",
    "TEST-T24-ENTITY-LINKAGE-PROJECTION-001",
    "EVIDENCE-T24-A5-CAPTURE-FAILURE-001",
    "EVIDENCE-T24-A5-QUARANTINED-PROJECTION-001",
    "EVIDENCE-T24-A5R1-PREFLIGHT-001",
    "TEST-T24-A5R1-RECAPTURE-001",
    "DATA-T24-ENTITY-NODES-001",
    "DATA-T24-ENTITY-EDGES-001",
    "DATA-T24-ENTITY-CANDIDATES-001",
    "DATA-T24-ADJUSTED-CONCENTRATION-001",
    "EVIDENCE-T24-A5R1-PROJECTION-MANIFEST-001",
    "EVIDENCE-T24-A5R1-ACCEPTANCE-001",
    "DECISION-T24-DATA-REDESIGN-OR-STOP-001",
    "CONFIG-T24-DATA-REDESIGN-OR-STOP-001",
    "TEST-T24-DATA-REDESIGN-OR-STOP-001",
    "EVIDENCE-T24-A6-STOP-DECISION-001",
    "EVIDENCE-T24-A7-CATALOG-FACTORY-FIT-001",
    "TEST-T24-A7-CATALOG-FACTORY-FIT-001",
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
    if accepted["owner_decision"] != "STOP_NO_RELIABLE_ENTITY_SIGNAL":
        errors.add("STOP_DECISION_ERASED")
    if accepted["selected_predicted_positive_capacity"] >= accepted[
        "false_positive_minimum_reviewed_positive"
    ]:
        errors.add("AUDIT_FALSELY_OPENED")
    if accepted["downstream_decision_admissibility"] != "NOT_ADMISSIBLE":
        errors.add("PARTIAL_GRAPH_PROMOTED")
    if set(receipt["catalog"]["registered_asset_ids"]) != NEW_IDS:
        errors.add("CATALOG_GAP")
    critic = receipt["factory_fit"]
    if critic["mode"] != "FULL_REVIEW" or len(critic["checks"]) != 15:
        errors.add("FACTORY_FIT_INCOMPLETE")
    if critic["verdict"] != "PASS_WITH_FOLLOWUP":
        errors.add("FOLLOWUP_ERASED")
    if receipt["next_boundary"]["authorized"]:
        errors.add("A8_AUTO_AUTHORIZED")
    return errors


class Task24CatalogFactoryFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_bytes())

    def test_receipt_hash_and_stop_result_are_exact(self) -> None:
        self.assertEqual(sha256(RECEIPT_PATH), EXPECTED_RECEIPT_SHA256)
        accepted = self.receipt["accepted_result"]
        self.assertEqual(
            accepted["owner_decision"], "STOP_NO_RELIABLE_ENTITY_SIGNAL"
        )
        self.assertEqual(accepted["selected_predicted_positive_capacity"], 4)
        self.assertEqual(accepted["false_positive_minimum_reviewed_positive"], 12)
        self.assertEqual(accepted["corroborated_positive_claims"], 0)
        self.assertEqual(accepted["inferred_positive_claims"], 4)
        self.assertEqual(
            accepted["downstream_decision_admissibility"], "NOT_ADMISSIBLE"
        )
        self.assertFalse(accepted["false_positive_audit_opened"])

    def test_catalog_transaction_and_all_registered_hashes_are_exact(self) -> None:
        manifest, records = load_catalog()
        self.assertEqual(manifest["catalog_version"], "0.29.0")
        self.assertEqual(
            manifest["current_checkpoint"],
            {
                "assets": 448,
                "asset_registries": 4,
                "schemas": 7,
                "queries": 8,
                "lifecycle_registries": 9,
                "lifecycle_records": 56,
            },
        )
        self.assertEqual(len(records), 448)
        self.assertEqual(set(self.receipt["catalog"]["registered_asset_ids"]), NEW_IDS)
        self.assertTrue(NEW_IDS.issubset(records))
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                record = records[asset_id]
                relative = record["location"]["repository_path"]
                self.assertEqual(sha256(ROOT / relative), record["integrity"]["sha256"])

    def test_negative_result_registry_is_append_only_and_resolves(self) -> None:
        _, records = load_catalog()
        registry = yaml.safe_load(
            (ROOT / "registries/decisions_negative_results.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(registry["records"]), 1)
        row = registry["records"][0]
        self.assertEqual(row["record_id"], "NEGATIVE-T24-ENTITY-SIGNAL-V1-001")
        self.assertEqual(row["record_kind"], "negative_result")
        self.assertEqual(row["status"], "RECORDED")
        self.assertIn("4/12", row["summary"])
        for asset_id in row["evidence_asset_ids"]:
            self.assertIn(asset_id, records)

    def test_current_projection_is_partial_and_legacy_projection_is_quarantined(self) -> None:
        _, records = load_catalog()
        current = records["DATA-T24-ENTITY-CANDIDATES-001"]
        legacy = records["EVIDENCE-T24-A5-QUARANTINED-PROJECTION-001"]
        self.assertEqual(current["status"], "IMPLEMENTED_UNVERIFIED")
        self.assertIn(
            "EVIDENCE-T24-A6-STOP-DECISION-001",
            {relation["target_asset_id"] for relation in current["relations"]},
        )
        self.assertEqual(legacy["status"], "DEPRECATED")
        self.assertIn("quarantined", legacy["purpose"].lower())

    def test_full_factory_fit_and_reactivation_followup_are_complete(self) -> None:
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
        self.assertEqual(followup["owner"], "FUTURE_ENTITY_EVIDENCE_ENTRY_GATE")
        self.assertEqual(
            followup["activation_trigger"],
            "NAMED_CONSUMER_AND_SECOND_INDEPENDENT_RAW_EVENT_FAMILY_AVAILABLE",
        )
        self.assertEqual(
            followup["destination"], "NEW_VERSIONED_ENTITY_EVIDENCE_OBJECTIVE"
        )

    def test_navigation_contains_every_new_asset_and_relation_source(self) -> None:
        project_map = (ROOT / "docs/PROJECT_MAP.md").read_text(encoding="utf-8")
        edges = json.loads(
            (ROOT / "catalog/generated/asset_edges.json").read_text(encoding="utf-8")
        )
        edge_sources = {edge["source_asset_id"] for edge in edges["edges"]}
        for asset_id in NEW_IDS:
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, project_map)
                self.assertIn(asset_id, edge_sources)

    def test_authority_finish_state_and_next_boundary_are_closed(self) -> None:
        authority = self.receipt["authority"]
        self.assertTrue(authority["local_write_only"])
        for key, value in authority.items():
            if key not in {"local_write_only", "catalog_or_registry_mutations"}:
                self.assertIn(value, (0, False), key)
        self.assertEqual(authority["catalog_or_registry_mutations"], 1)
        self.assertEqual(self.receipt["finish_gate"], "CONTINUE_CURRENT_TASK")
        self.assertEqual(
            self.receipt["next_boundary"]["atom"],
            "T24-A8_REPOSITORY_DELIVERY_V1",
        )
        self.assertFalse(self.receipt["next_boundary"]["authorized"])
        self.assertIn("CANONICAL_TASK24_DONE", self.receipt["nonclaims"])

    def test_adversarial_mutations_fail_closed(self) -> None:
        self.assertEqual(semantic_errors(self.receipt), set())
        mutations = [
            ("stop", "STOP_DECISION_ERASED", lambda value: value["accepted_result"].__setitem__("owner_decision", "ENTITY_EVIDENCE_READY_WITH_LIMITATIONS")),
            ("audit", "AUDIT_FALSELY_OPENED", lambda value: value["accepted_result"].__setitem__("selected_predicted_positive_capacity", 12)),
            ("promotion", "PARTIAL_GRAPH_PROMOTED", lambda value: value["accepted_result"].__setitem__("downstream_decision_admissibility", "ADMISSIBLE")),
            ("catalog", "CATALOG_GAP", lambda value: value["catalog"]["registered_asset_ids"].pop()),
            ("critic", "FACTORY_FIT_INCOMPLETE", lambda value: value["factory_fit"]["checks"].pop()),
            ("followup", "FOLLOWUP_ERASED", lambda value: value["factory_fit"].__setitem__("verdict", "PASS")),
            ("authority", "A8_AUTO_AUTHORIZED", lambda value: value["next_boundary"].__setitem__("authorized", True)),
        ]
        for label, expected, mutate in mutations:
            with self.subTest(vector=label):
                changed = copy.deepcopy(self.receipt)
                mutate(changed)
                self.assertIn(expected, semantic_errors(changed))

    def test_hygiene_and_secret_boundaries_are_exact(self) -> None:
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
