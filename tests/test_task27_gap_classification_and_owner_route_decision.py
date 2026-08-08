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
CONTRACT_PATH = ROOT / "docs/contracts/task27_gap_classification_and_owner_route_decision_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_gap_classification_and_owner_route_decision_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_gap_classification_and_owner_route_decision.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/gap_classification_and_owner_route_decision_v1.json"
STAGE_A_RECEIPT_PATH = ROOT / "docs/evidence/task27/a1_stage_a_public_pair_identity_runtime_receipt_v1.json"
STAGE_B_RECEIPT_PATH = ROOT / "docs/evidence/task27/a1s2_stage_b_pool_history_runtime_receipt_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task27/a1s3_gap_classification_and_owner_route_decision_acceptance_v1.json"

REQUIRED_PATHS = [CONTRACT_PATH, CONFIG_PATH, SCHEMA_PATH, FIXTURE_PATH]
EXPECTED_OBSERVATION = {
    "expected_natural_bars": 96,
    "observed_bars": 33,
    "missing_natural_bars": 63,
    "returned_zero_volume_bars": 18,
    "internal_gap_regions": 21,
    "largest_gap_seconds": 8100,
}
EXPECTED_ADVERSARIAL_ERRORS = {
    "missing-to-zero": "MISSING_TO_ZERO_FORBIDDEN",
    "trade-only-cause": "TRADE_ONLY_CAUSAL_OVERCLAIM",
    "proven-cause": "UNPROVEN_CAUSAL_ATTRIBUTION",
    "pit-promotion": "PIT_PROMOTION_FORBIDDEN",
    "automatic-provider": "EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN",
    "task-close-promotion": "TASK27_CLOSURE_PROMOTION_FORBIDDEN",
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
    observation = packet["observation"]
    explanations = {item["id"]: item for item in packet["explanations"]}
    decision = packet["decision"]
    claims = packet["claims"]

    if observation["missing_data_state"] != "MISSING_UNKNOWN" or observation["missing_as_zero"]:
        errors.add("MISSING_TO_ZERO_FORBIDDEN")
    if explanations["trade_only_endpoint_emission"]["classification"] != "NARROW_FORM_FALSIFIED":
        errors.add("TRADE_ONLY_CAUSAL_OVERCLAIM")
    if any(item["classification"] == "PROVEN_CAUSE" for item in explanations.values()):
        errors.add("UNPROVEN_CAUSAL_ATTRIBUTION")
    if claims["pit_admissible"] or any(
        claims[name] for name in ("alpha", "execution", "pnl", "netreturn", "cashflow")
    ):
        errors.add("PIT_PROMOTION_FORBIDDEN")
    if decision["provider_selected"] is not None or decision["provider_read_authority"]:
        errors.add("EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN")
    if decision["task27_status"] != "IN_PROGRESS_NO_ACCEPTANCE":
        errors.add("TASK27_CLOSURE_PROMOTION_FORBIDDEN")
    return errors


class Task27GapClassificationAndOwnerRouteDecisionTests(unittest.TestCase):
    def require_static_artifacts(self) -> None:
        missing_paths = [str(path) for path in REQUIRED_PATHS if not path.is_file()]
        self.assertFalse(missing_paths, f"missing required Task-27 A1S3 artifacts: {missing_paths}")

    def test_required_static_artifacts_exist(self) -> None:
        self.require_static_artifacts()

    def test_valid_packet_preserves_negative_evidence_without_causal_or_authority_promotion(self) -> None:
        self.require_static_artifacts()
        fixture = load_json(FIXTURE_PATH)
        policy = load_yaml(CONFIG_PATH)
        schema = load_json(SCHEMA_PATH)
        packet = fixture["valid_packets"][0]

        Draft202012Validator(schema).validate(packet)
        self.assertEqual(packet["fixture_kind"], "SYNTHETIC_GOLDEN_ONLY")
        self.assertEqual(packet["observation"], EXPECTED_OBSERVATION | {
            "missing_data_state": "MISSING_UNKNOWN",
            "missing_as_zero": False,
        })
        self.assertEqual(packet["observation"], policy["observation"])
        self.assertEqual(
            packet["source_bindings"]["stage_a_receipt"],
            {
                "path": STAGE_A_RECEIPT_PATH.relative_to(ROOT).as_posix(),
                "sha256": sha256(STAGE_A_RECEIPT_PATH),
            },
        )
        self.assertEqual(
            packet["source_bindings"]["stage_b_receipt"],
            {
                "path": STAGE_B_RECEIPT_PATH.relative_to(ROOT).as_posix(),
                "sha256": sha256(STAGE_B_RECEIPT_PATH),
            },
        )
        self.assertEqual(packet["decision"], policy["decision"])
        self.assertEqual(packet["claims"], policy["claims"])
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
                self.assertEqual(
                    semantic_errors(candidate),
                    {EXPECTED_ADVERSARIAL_ERRORS[case["case_id"]]},
                )

    def test_stage_b_receipt_remains_incomplete_and_not_pit_admissible(self) -> None:
        receipt = load_json(STAGE_B_RECEIPT_PATH)
        self.assertEqual(receipt["panel_observation"]["expected_natural_bars"], 96)
        self.assertEqual(receipt["panel_observation"]["observed_bars"], 33)
        self.assertEqual(receipt["panel_observation"]["missing_natural_bars"], 63)
        self.assertEqual(receipt["decision"]["terminal_disposition"], "INCOMPLETE_PANEL_NOT_FEASIBLE")
        self.assertFalse(receipt["claims"]["pit_admissible"])

    def test_acceptance_receipt_binds_offline_decision_without_task_closure(self) -> None:
        self.assertTrue(ACCEPTANCE_PATH.is_file(), f"missing Task-27 A1S3 acceptance receipt: {ACCEPTANCE_PATH}")
        receipt = load_json(ACCEPTANCE_PATH)

        self.assertEqual(receipt["schema"], "smial.task27.gap-classification-and-owner-route-decision.acceptance")
        self.assertEqual(receipt["task_id"], "TASK-27")
        self.assertEqual(receipt["atom_id"], "T27-A1S3_OFFLINE_GAP_CLASSIFICATION_AND_OWNER_ROUTE_DECISION_PACKET_V1")
        self.assertEqual(
            receipt["artifact_bindings"],
            {
                "contract": {
                    "path": CONTRACT_PATH.relative_to(ROOT).as_posix(),
                    "sha256": sha256(CONTRACT_PATH),
                },
                "config": {
                    "path": CONFIG_PATH.relative_to(ROOT).as_posix(),
                    "sha256": sha256(CONFIG_PATH),
                },
                "schema": {
                    "path": SCHEMA_PATH.relative_to(ROOT).as_posix(),
                    "sha256": sha256(SCHEMA_PATH),
                },
                "fixture": {
                    "path": FIXTURE_PATH.relative_to(ROOT).as_posix(),
                    "sha256": sha256(FIXTURE_PATH),
                },
                "stage_b_receipt": {
                    "path": STAGE_B_RECEIPT_PATH.relative_to(ROOT).as_posix(),
                    "sha256": sha256(STAGE_B_RECEIPT_PATH),
                },
            },
        )
        self.assertEqual(receipt["adversarial_rejection_count"], len(EXPECTED_ADVERSARIAL_ERRORS))
        self.assertEqual(receipt["decision"], {
            "current_route_disposition": "CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE",
            "future_boundary": "SEPARATE_OWNER_EXTERNAL_READ_DECISION_REQUIRED",
            "state_change": "NONE",
            "task27_acceptance": False,
        })
        self.assertEqual(receipt["authority"], {
            "provider_api_rpc_wss_calls": 0,
            "credential_use": False,
            "raw_provider_responses_retained": 0,
            "r2_value_reads": 0,
            "r3_value_or_path_reads": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd_cents": 0,
        })
        self.assertEqual(receipt["factory_fit_review"], "FULL_REVIEW")
        self.assertEqual(receipt["project_sources_disposition"], "NO_CHANGE")

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
