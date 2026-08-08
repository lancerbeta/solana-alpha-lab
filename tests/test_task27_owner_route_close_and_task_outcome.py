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
CONTRACT_PATH = ROOT / "docs/contracts/task27_owner_route_close_and_task_outcome_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_owner_route_close_and_task_outcome_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_owner_route_close_and_task_outcome.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/owner_route_close_and_task_outcome_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task27/a1s4_owner_route_close_and_task_outcome_acceptance_v1.json"
A1S3_POLICY_PATH = ROOT / "configs/task27_gap_classification_and_owner_route_decision_v1.yaml"
A1S3_ACCEPTANCE_PATH = ROOT / "docs/evidence/task27/a1s3_gap_classification_and_owner_route_decision_acceptance_v1.json"

REQUIRED_PATHS = [CONTRACT_PATH, CONFIG_PATH, SCHEMA_PATH, FIXTURE_PATH, ACCEPTANCE_PATH]
EXPECTED_ADVERSARIAL_ERRORS = {
    "binding-drift": "SOURCE_BINDING_DRIFT",
    "provider-read": "UNAUTHORIZED_PROVIDER_READ",
    "market-wide-close": "MARKET_WIDE_CONCLUSION_FORBIDDEN",
    "task-done": "PREMATURE_TASK27_DONE_FORBIDDEN",
    "missing-to-zero": "MISSING_TO_ZERO_FORBIDDEN",
    "claim-promotion": "RESEARCH_EXECUTION_ECONOMIC_PROMOTION_FORBIDDEN",
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
    bindings = packet["source_bindings"]
    owner_decision = packet["owner_decision"]
    missingness = packet["missingness"]
    decision = packet["decision"]
    authority = packet["authority"]
    claims = packet["claims"]

    expected_bindings = {
        "a1s3_policy": {
            "path": A1S3_POLICY_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256(A1S3_POLICY_PATH),
        },
        "a1s3_acceptance": {
            "path": A1S3_ACCEPTANCE_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256(A1S3_ACCEPTANCE_PATH),
        },
    }
    if bindings != expected_bindings:
        errors.add("SOURCE_BINDING_DRIFT")
    if owner_decision != {
        "route_close": "ROUTE_CLOSE_ACCEPTED",
        "new_provider_read": "NO_NEW_PROVIDER_READ",
    } or authority["provider_api_rpc_wss_calls"] != 0 or authority["credential_use"]:
        errors.add("UNAUTHORIZED_PROVIDER_READ")
    if (
        missingness["state"] != "MISSING_UNKNOWN"
        or missingness["missing_as_zero"]
    ):
        errors.add("MISSING_TO_ZERO_FORBIDDEN")
    if claims["public_history_globally_infeasible"]:
        errors.add("MARKET_WIDE_CONCLUSION_FORBIDDEN")
    if decision["task27_status"] == "DONE":
        errors.add("PREMATURE_TASK27_DONE_FORBIDDEN")
    if any(claims[name] for name in ("pit_admissible", "alpha", "execution", "pnl", "netreturn", "cashflow")):
        errors.add("RESEARCH_EXECUTION_ECONOMIC_PROMOTION_FORBIDDEN")
    return errors


class Task27OwnerRouteCloseAndTaskOutcomeTests(unittest.TestCase):
    def require_static_artifacts(self) -> None:
        missing_paths = [str(path) for path in REQUIRED_PATHS if not path.is_file()]
        self.assertFalse(missing_paths, f"missing required Task-27 A1S4 artifacts: {missing_paths}")

    def test_required_static_artifacts_exist(self) -> None:
        self.require_static_artifacts()

    def test_valid_packet_binds_owner_route_close_without_authority_or_task_completion_promotion(self) -> None:
        self.require_static_artifacts()
        fixture = load_json(FIXTURE_PATH)
        policy = load_yaml(CONFIG_PATH)
        schema = load_json(SCHEMA_PATH)
        packet = fixture["valid_packets"][0]

        Draft202012Validator(schema).validate(packet)
        self.assertEqual(packet["fixture_kind"], "SYNTHETIC_GOLDEN_ONLY")
        self.assertEqual(packet, policy["packet"])
        self.assertEqual(semantic_errors(packet), set())

    def test_adversarial_cases_are_rejected(self) -> None:
        self.require_static_artifacts()
        fixture = load_json(FIXTURE_PATH)
        valid_packet = fixture["valid_packets"][0]
        cases = fixture["adversarial_cases"]

        self.assertEqual({case["case_id"] for case in cases}, set(EXPECTED_ADVERSARIAL_ERRORS))
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                candidate = copy.deepcopy(valid_packet)
                set_json_pointer(candidate, case["pointer"], case["replacement"])
                self.assertEqual(semantic_errors(candidate), {EXPECTED_ADVERSARIAL_ERRORS[case["case_id"]]})

    def test_acceptance_receipt_binds_exact_artifacts_and_preserves_no_change_state(self) -> None:
        self.require_static_artifacts()
        receipt = load_json(ACCEPTANCE_PATH)

        self.assertEqual(receipt["schema"], "smial.task27.owner-route-close-and-task-outcome.acceptance")
        self.assertEqual(receipt["task_id"], "TASK-27")
        self.assertEqual(receipt["atom_id"], "T27-A1S4_OWNER_ROUTE_CLOSE_BINDING_AND_TASK_OUTCOME_DECISION_V1")
        self.assertEqual(receipt["artifact_bindings"], {
            "contract": {"path": CONTRACT_PATH.relative_to(ROOT).as_posix(), "sha256": sha256(CONTRACT_PATH)},
            "config": {"path": CONFIG_PATH.relative_to(ROOT).as_posix(), "sha256": sha256(CONFIG_PATH)},
            "schema": {"path": SCHEMA_PATH.relative_to(ROOT).as_posix(), "sha256": sha256(SCHEMA_PATH)},
            "fixture": {"path": FIXTURE_PATH.relative_to(ROOT).as_posix(), "sha256": sha256(FIXTURE_PATH)},
            "a1s3_policy": {"path": A1S3_POLICY_PATH.relative_to(ROOT).as_posix(), "sha256": sha256(A1S3_POLICY_PATH)},
            "a1s3_acceptance": {"path": A1S3_ACCEPTANCE_PATH.relative_to(ROOT).as_posix(), "sha256": sha256(A1S3_ACCEPTANCE_PATH)},
        })
        self.assertEqual(receipt["adversarial_rejection_count"], len(EXPECTED_ADVERSARIAL_ERRORS))
        self.assertEqual(receipt["decision"]["task27_acceptance"], False)
        self.assertEqual(receipt["decision"]["state_change"], "NONE")
        self.assertEqual(receipt["project_sources_disposition"]["kind"], "NO_CHANGE")

    def test_static_artifacts_do_not_contain_secret_markers(self) -> None:
        self.require_static_artifacts()
        forbidden_markers = (
            "api-key",
            "api_key",
            "authorization: bearer",
            "authorization=bearer",
            "private_key",
            "seed phrase",
        )
        for path in REQUIRED_PATHS:
            serialized = path.read_text(encoding="utf-8").lower()
            for marker in forbidden_markers:
                with self.subTest(path=path, marker=marker):
                    self.assertNotIn(marker, serialized)


if __name__ == "__main__":
    unittest.main()
