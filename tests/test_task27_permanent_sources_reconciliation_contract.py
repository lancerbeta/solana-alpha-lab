from __future__ import annotations

import copy
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


if __name__ == "__main__":
    unittest.main()
