from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/contracts/task27_permanent_sources_reconciliation_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_permanent_sources_reconciliation_contract_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_permanent_sources_reconciliation.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/permanent_sources_reconciliation_v1.json"
SOURCE_BUNDLE_ROOT = ROOT / "docs/project_sources/releases/PSR-0001-T27-A0-A5"
BUNDLE_MANIFEST_PATH = SOURCE_BUNDLE_ROOT / "canonical_manifest.yaml"
CHECKSUMS_PATH = SOURCE_BUNDLE_ROOT / "CHECKSUMS_SHA256.txt"
SMOKE_PATH = SOURCE_BUNDLE_ROOT / "FRESH_CHAT_SMOKE.md"
RECEIPT_PATH = ROOT / "docs/evidence/task27/a0a5_permanent_sources_reconciliation_acceptance_v1.json"
EXPECTED_SOURCE_FILES = {
    "canonical_manifest": "canonical_manifest.yaml",
    "roadmap": "roadmap.md",
    "current_system_state": "current_system_state.md",
    "phase_archive": "task_archive_P0_P1_v37.md",
    "active_task": "task_27_public_history_feasibility.md",
}
REQUIRED_PATHS = [CONTRACT_PATH, CONFIG_PATH, SCHEMA_PATH, FIXTURE_PATH]
EXPECTED_MUTABLE_ROLES = [
    "canonical_manifest",
    "roadmap",
    "current_system_state",
    "phase_archive",
    "active_task",
]
EXPECTED_ADVERSARIAL_ERRORS = {
    "MUTABLE_ROLE_SET_MISMATCH",
    "OLD_ACTIVE_TASK_FORBIDDEN",
    "IMMUTABLE_ROLE_HASH_DRIFT",
    "UI_ACTIVATION_CLAIM_FORBIDDEN",
    "SMOKE_PROMPT_REQUIRED",
    "REPOSITORY_EVIDENCE_MISMATCH",
    "EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN",
    "PIT_CLAIM_FORBIDDEN",
}


def apply_json_pointer(document: dict, pointer: str, value: object) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    target: object = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final = parts[-1]
    if isinstance(target, list):
        target[int(final)] = copy.deepcopy(value)
    else:
        target[final] = copy.deepcopy(value)


def semantic_errors(packet: dict) -> set[str]:
    errors: set[str] = set()
    if packet["mutable_roles"] != EXPECTED_MUTABLE_ROLES:
        errors.add("MUTABLE_ROLE_SET_MISMATCH")
    if packet["active_task_id"] != "TASK-27":
        errors.add("OLD_ACTIVE_TASK_FORBIDDEN")
    if packet["immutable_role_hashes"]["operating_system"] != (
        "187aa5d1405c55868d7147a7cdf9e0605a9a51f613ab5597ae44682fcbc67c84"
    ):
        errors.add("IMMUTABLE_ROLE_HASH_DRIFT")
    if packet["bundle_status"] != "VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING":
        errors.add("UI_ACTIVATION_CLAIM_FORBIDDEN")
    if not packet["smoke_prompt_id"]:
        errors.add("SMOKE_PROMPT_REQUIRED")
    if packet["repository_evidence"] != {
        "main_commit": "082f3f8184e84c31c876a484cf8e876a40691f62",
        "main_ci_run_id": 31224401848,
        "main_ci_conclusion": "success",
    }:
        errors.add("REPOSITORY_EVIDENCE_MISMATCH")
    if packet["authority"]["provider_read_authority"]:
        errors.add("EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN")
    if packet["claims"]["pit_admissible"]:
        errors.add("PIT_CLAIM_FORBIDDEN")
    return errors


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task27PermanentSourcesReconciliationContractTests(unittest.TestCase):
    def test_contract_artifacts_exist_and_do_not_grant_external_authority(self) -> None:
        missing = [str(path) for path in REQUIRED_PATHS if not path.exists()]
        self.assertEqual(missing, [])

        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["bundle_status"], "VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING")
        self.assertFalse(config["authority"]["provider_read_authority"])

    def test_synthetic_packet_rejects_source_and_authority_drift(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(fixture)), [])

        expected_errors = {case["expected_error"] for case in fixture["adversarial_cases"]}
        self.assertEqual(expected_errors, EXPECTED_ADVERSARIAL_ERRORS)
        base = fixture["valid_packets"][0]
        self.assertEqual(semantic_errors(base), set())
        for case in fixture["adversarial_cases"]:
            with self.subTest(case_id=case["case_id"]):
                changed = copy.deepcopy(base)
                for mutation in case["mutations"]:
                    apply_json_pointer(changed, mutation["json_pointer"], mutation["replacement"])
                self.assertIn(case["expected_error"], semantic_errors(changed))

    def test_bundle_has_exactly_five_replacements_and_retains_two_immutable_roles(self) -> None:
        self.assertTrue(BUNDLE_MANIFEST_PATH.exists(), BUNDLE_MANIFEST_PATH)
        self.assertTrue(CHECKSUMS_PATH.exists(), CHECKSUMS_PATH)
        self.assertTrue(SMOKE_PATH.exists(), SMOKE_PATH)

        bundle_manifest = yaml.safe_load(BUNDLE_MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(bundle_manifest["status"], "VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING")
        self.assertEqual(bundle_manifest["activation_map"]["replace_source_roles"], EXPECTED_MUTABLE_ROLES)
        self.assertEqual(
            bundle_manifest["activation_map"]["keep_byte_for_byte"],
            ["operating_system", "research_blueprint"],
        )
        self.assertEqual(bundle_manifest["current_state"]["active_task_id"], "TASK-27")
        self.assertEqual(
            bundle_manifest["current_state"]["last_validated_repository_commit"],
            "082f3f8184e84c31c876a484cf8e876a40691f62",
        )
        self.assertEqual(bundle_manifest["current_state"]["main_ci_run_id"], 31224401848)
        for role, filename in EXPECTED_SOURCE_FILES.items():
            with self.subTest(role=role):
                role_binding = bundle_manifest["canonical"][role]
                path = SOURCE_BUNDLE_ROOT / filename
                self.assertTrue(path.exists(), path)
                self.assertEqual(role_binding["current_filename"], filename)
                if role == "canonical_manifest":
                    self.assertEqual(role_binding["self_checksum_policy"], "CHECKSUMS_SHA256")
                else:
                    self.assertEqual(role_binding["sha256"], sha256(path))

    def test_acceptance_receipt_binds_bundle_and_stops_before_ui_activation(self) -> None:
        self.assertTrue(RECEIPT_PATH.exists(), RECEIPT_PATH)
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["state_change"], "NONE")
        self.assertEqual(receipt["ui_activation"], "PENDING_USER_REPLACEMENT_AND_SMOKE")
        self.assertFalse(receipt["next_boundary"]["provider_read_authority_granted"])
        self.assertEqual(
            receipt["repository_evidence"]["main_commit"],
            "082f3f8184e84c31c876a484cf8e876a40691f62",
        )
        self.assertEqual(receipt["repository_evidence"]["main_ci_run_id"], 31224401848)
        for path in [BUNDLE_MANIFEST_PATH, CHECKSUMS_PATH, SMOKE_PATH]:
            with self.subTest(path=path):
                binding = receipt["bundle_artifact_bindings"][path.name]
                self.assertEqual(binding["sha256"], sha256(path))


if __name__ == "__main__":
    unittest.main()
