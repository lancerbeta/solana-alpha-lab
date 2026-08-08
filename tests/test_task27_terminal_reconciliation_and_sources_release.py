from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/contracts/task27_terminal_reconciliation_and_sources_release_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_terminal_reconciliation_and_sources_release_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_terminal_reconciliation_and_sources_release.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/terminal_reconciliation_and_sources_release_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task27/a2_terminal_reconciliation_and_sources_release_acceptance_v1.json"
A1S4_ACCEPTANCE_PATH = ROOT / "docs/evidence/task27/a1s4_owner_route_close_and_task_outcome_acceptance_v1.json"
REGISTRY_PATH = ROOT / "docs/project_sources/release_registry_v1.yaml"
RELEASE_ROOT = ROOT / "docs/project_sources/releases/PSR-0002-T27-CLOSE"

TERMINAL_RESULT = "NO_FEASIBLE_PUBLIC_HISTORY_ROUTE_DEMONSTRATED_WITHIN_AUTHORIZED_SCOPE"
EXPECTED_ADVERSARIAL_ERRORS = {
    "a1s4-binding-drift": "A1S4_BINDING_DRIFT",
    "global-history": "GLOBAL_HISTORY_CLAIM_FORBIDDEN",
    "new-provider": "NEW_PROVIDER_AUTHORITY_FORBIDDEN",
    "missing-to-zero": "MISSING_TO_ZERO_FORBIDDEN",
    "premature-ui": "PREMATURE_UI_ACTIVATION_FORBIDDEN",
    "invented-next-task": "INVENTED_NEXT_TASK_FORBIDDEN",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def set_json_pointer(payload: dict[str, Any], pointer: str, value: Any) -> None:
    parts = pointer.lstrip("/").split("/")
    target: Any = payload
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    if isinstance(target, list):
        target[int(parts[-1])] = value
    else:
        target[parts[-1]] = value


def semantic_errors(packet: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    expected_a1s4 = {
        "path": A1S4_ACCEPTANCE_PATH.relative_to(ROOT).as_posix(),
        "sha256": sha256(A1S4_ACCEPTANCE_PATH),
    }
    if packet["source_bindings"]["a1s4_acceptance"] != expected_a1s4:
        errors.add("A1S4_BINDING_DRIFT")
    if packet["claims"]["public_history_globally_infeasible"]:
        errors.add("GLOBAL_HISTORY_CLAIM_FORBIDDEN")
    if packet["authority"]["provider_api_rpc_wss_calls"] or packet["authority"]["credential_use"]:
        errors.add("NEW_PROVIDER_AUTHORITY_FORBIDDEN")
    if packet["missingness"] != {"state": "MISSING_UNKNOWN", "missing_as_zero": False}:
        errors.add("MISSING_TO_ZERO_FORBIDDEN")
    if packet["source_release"]["activation_state"] != "UI_ACTIVATION_PENDING_OWNER_SMOKE":
        errors.add("PREMATURE_UI_ACTIVATION_FORBIDDEN")
    if packet["next_task"] != {"selected": False, "task_id": None}:
        errors.add("INVENTED_NEXT_TASK_FORBIDDEN")
    return errors


class Task27TerminalReconciliationAndSourcesReleaseTests(unittest.TestCase):
    def require_static_artifacts(self) -> bool:
        required = (CONTRACT_PATH, CONFIG_PATH, SCHEMA_PATH, FIXTURE_PATH, ACCEPTANCE_PATH)
        missing = [path for path in required if not path.is_file()]
        self.assertFalse(missing, f"missing required TASK-27 A2 artifacts: {missing}")
        return not missing

    def test_valid_terminal_packet_is_limited_and_authority_free(self) -> None:
        if not self.require_static_artifacts():
            return
        fixture = load_json(FIXTURE_PATH)
        packet = fixture["valid_packets"][0]
        Draft202012Validator(load_json(SCHEMA_PATH)).validate(packet)
        self.assertEqual(packet["result"], TERMINAL_RESULT)
        self.assertEqual(packet, load_yaml(CONFIG_PATH)["packet"])
        self.assertEqual(semantic_errors(packet), set())

    def test_adversarial_terminal_packets_are_rejected(self) -> None:
        if not self.require_static_artifacts():
            return
        fixture = load_json(FIXTURE_PATH)
        valid_packet = fixture["valid_packets"][0]
        self.assertEqual(
            {case["case_id"] for case in fixture["adversarial_cases"]},
            set(EXPECTED_ADVERSARIAL_ERRORS),
        )
        for case in fixture["adversarial_cases"]:
            with self.subTest(case_id=case["case_id"]):
                candidate = copy.deepcopy(valid_packet)
                set_json_pointer(candidate, case["pointer"], case["replacement"])
                self.assertEqual(
                    semantic_errors(candidate),
                    {EXPECTED_ADVERSARIAL_ERRORS[case["case_id"]]},
                )

    def test_terminal_receipt_binds_artifacts_and_preserves_limited_claims(self) -> None:
        if not self.require_static_artifacts():
            return
        receipt = load_json(ACCEPTANCE_PATH)
        self.assertEqual(
            receipt["schema"],
            "smial.task27.terminal-reconciliation-and-sources-release.acceptance",
        )
        self.assertEqual(
            receipt["decision"]["terminal_result"],
            TERMINAL_RESULT,
        )
        self.assertEqual(receipt["decision"]["task27_outcome"], "CLOSE_WITH_LIMITED_NEGATIVE_RESULT")
        self.assertEqual(receipt["decision"]["next_task_selected"], False)
        self.assertEqual(receipt["adversarial_rejection_count"], len(EXPECTED_ADVERSARIAL_ERRORS))
        self.assertEqual(receipt["factory_fit_review"], "FULL_REVIEW")
        self.assertEqual(receipt["factory_fit"]["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(receipt["project_sources_disposition"]["kind"], "RELEASE_CANDIDATE")
        for key, path in {
            "contract": CONTRACT_PATH,
            "config": CONFIG_PATH,
            "schema": SCHEMA_PATH,
            "fixture": FIXTURE_PATH,
            "a1s4_acceptance": A1S4_ACCEPTANCE_PATH,
        }.items():
            with self.subTest(binding=key):
                self.assertEqual(
                    receipt["artifact_bindings"][key],
                    {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)},
                )
        self.assertTrue(all(value == 0 for value in receipt["side_effect_counters"].values()))
        self.assertFalse(any(receipt["claims"].values()))

    def test_project_sources_candidate_is_pending_and_keeps_prior_release_active(self) -> None:
        self.assertTrue(REGISTRY_PATH.is_file(), REGISTRY_PATH)
        self.assertTrue(RELEASE_ROOT.is_dir(), RELEASE_ROOT)
        registry = load_yaml(REGISTRY_PATH)
        releases = {release["release_id"]: release for release in registry["releases"]}
        self.assertEqual(registry["active_ui_release_id"], "PSR-0001-T27-A0-A5")
        self.assertEqual(registry["latest_candidate_release_id"], "PSR-0002-T27-CLOSE")
        candidate = releases["PSR-0002-T27-CLOSE"]
        self.assertEqual(candidate["status"], "VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING")
        self.assertIsNone(candidate["activation_receipt"])


if __name__ == "__main__":
    unittest.main()
