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
CONTRACT_PATH = ROOT / "docs/contracts/task27_stage_b_exact_owner_packet_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_stage_b_exact_owner_packet_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_stage_b_exact_owner_packet.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/stage_b_exact_owner_packet_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task27/a1s1_stage_b_exact_owner_packet_acceptance_v1.json"
STAGE_A_RECEIPT_PATH = ROOT / "docs/evidence/task27/a1_stage_a_public_pair_identity_runtime_receipt_v1.json"
TWO_STAGE_CONFIG_PATH = ROOT / "configs/task27_two_stage_identity_and_history_route_contract_v1.yaml"
A7_CONFIG_PATH = ROOT / "configs/task27_exact_single_pool_selection_and_pilot_read_packet_v1.yaml"

REQUIRED_PATHS = (
    CONTRACT_PATH,
    CONFIG_PATH,
    SCHEMA_PATH,
    FIXTURE_PATH,
    ACCEPTANCE_PATH,
)

EXPECTED_ERRORS = {
    "STAGE_A_BINDING_MISMATCH",
    "IDENTITY_DRIFT",
    "WINDOW_DRIFT",
    "REQUEST_CAP_BREACH",
    "ENDPOINT_SCOPE_DRIFT",
    "TRANSFORMATION_OR_CACHE_DRIFT",
    "SECRET_EXPOSURE",
    "FALLBACK_OR_HELIUS_FORBIDDEN",
    "OFFLINE_AUTHORITY_PROMOTION",
    "PREMATURE_HISTORY_OR_ACCEPTANCE_CLAIM",
    "OWNER_APPROVAL_PROMOTION",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def apply_json_pointer(document: dict[str, Any], pointer: str, value: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.lstrip("/").split("/")]
    target: Any = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    if isinstance(target, list):
        target[int(parts[-1])] = value
    else:
        target[parts[-1]] = value


def packet_schema(schema: dict[str, Any]) -> dict[str, Any]:
    return {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/packet"}


def semantic_errors(packet: dict[str, Any], policy: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    identity = packet["identity"]
    window = packet["frozen_window"]
    requests = packet["requests"]
    authority = packet["authority"]
    claims = packet["claims"]
    approval = packet["future_owner_approval"]

    if packet["stage_a_receipt_sha256"] != policy["source_binding"]["stage_a_receipt"]["sha256"]:
        errors.add("STAGE_A_BINDING_MISMATCH")
    if identity != policy["frozen_identity"]:
        errors.add("IDENTITY_DRIFT")
    if window != policy["frozen_window"]:
        errors.add("WINDOW_DRIFT")
    if len(requests) != policy["request_cap"]:
        errors.add("REQUEST_CAP_BREACH")
    elif [request["url"] for request in requests] != policy["exact_urls"]:
        errors.add("ENDPOINT_SCOPE_DRIFT")
    if len(requests) == 2 and (
        requests[1]["query"] != policy["chart_query"]
        or requests[1]["query"]["removeOutliers"] is not False
        or requests[1]["query"]["fastCache"] is not False
    ):
        errors.add("TRANSFORMATION_OR_CACHE_DRIFT")
    serialized = json.dumps(packet, sort_keys=True).lower()
    if any(marker in serialized for marker in ("api-key", "api_key", "authorization", "private_key", "seed")):
        errors.add("SECRET_EXPOSURE")
    if packet["fallback_provider"] is not None or packet["helius_reconstruction"] != "FORBIDDEN":
        errors.add("FALLBACK_OR_HELIUS_FORBIDDEN")
    if authority["provider_api_rpc_wss_calls"] != 0 or authority["credential_use"]:
        errors.add("OFFLINE_AUTHORITY_PROMOTION")
    if (
        claims["history_grade"] != "NO_HISTORY_COLLECTED"
        or any(claims[field] for field in ("pit_admissible", "alpha", "execution", "pnl", "netreturn", "cashflow"))
        or packet["future_outcome"] != "OWNER_EXTERNAL_AUTHORITY_REQUIRED"
    ):
        errors.add("PREMATURE_HISTORY_OR_ACCEPTANCE_CLAIM")
    if approval["approval_granted"] or approval["stage_b_request_authorized"]:
        errors.add("OWNER_APPROVAL_PROMOTION")
    return errors


class StageBExactOwnerPacketTests(unittest.TestCase):
    def test_required_assets_exist_before_owner_packet_can_be_used(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)

    @unittest.skipUnless(all(path.is_file() for path in REQUIRED_PATHS), "owner packet assets not implemented")
    def test_valid_packet_is_schema_valid_and_remains_offline(self) -> None:
        schema = load_json(SCHEMA_PATH)
        fixture = load_json(FIXTURE_PATH)
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(fixture)), [])
        self.assertEqual(list(Draft202012Validator(packet_schema(schema)).iter_errors(fixture["valid_packet"])), [])
        self.assertEqual(fixture["valid_packet"]["authority"]["provider_api_rpc_wss_calls"], 0)
        self.assertFalse(fixture["valid_packet"]["authority"]["credential_use"])

    @unittest.skipUnless(all(path.is_file() for path in REQUIRED_PATHS), "owner packet assets not implemented")
    def test_valid_packet_binds_stage_a_and_freezes_the_prior_window(self) -> None:
        policy = load_yaml(CONFIG_PATH)
        packet = load_json(FIXTURE_PATH)["valid_packet"]
        self.assertEqual(sha256(STAGE_A_RECEIPT_PATH), policy["source_binding"]["stage_a_receipt"]["sha256"])
        self.assertEqual(sha256(TWO_STAGE_CONFIG_PATH), policy["source_binding"]["two_stage_config"]["sha256"])
        self.assertEqual(sha256(A7_CONFIG_PATH), policy["source_binding"]["a7_config"]["sha256"])
        self.assertEqual(semantic_errors(packet, policy), set())

    @unittest.skipUnless(all(path.is_file() for path in REQUIRED_PATHS), "owner packet assets not implemented")
    def test_each_adversarial_packet_is_rejected_at_its_named_boundary(self) -> None:
        schema = load_json(SCHEMA_PATH)
        fixture = load_json(FIXTURE_PATH)
        validator = Draft202012Validator(packet_schema(schema))
        policy = load_yaml(CONFIG_PATH)
        self.assertEqual({case["expected_error"] for case in fixture["adversarial_cases"]}, EXPECTED_ERRORS)
        for case in fixture["adversarial_cases"]:
            with self.subTest(case=case["case_id"]):
                packet = copy.deepcopy(fixture["valid_packet"])
                apply_json_pointer(packet, case["pointer"], case["value"])
                self.assertEqual(list(validator.iter_errors(packet)), [])
                errors = semantic_errors(packet, policy)
                self.assertIn(case["expected_error"], errors)
                self.assertTrue(errors <= EXPECTED_ERRORS)

    @unittest.skipUnless(all(path.is_file() for path in REQUIRED_PATHS), "owner packet assets not implemented")
    def test_acceptance_receipt_binds_all_assets_and_no_external_action(self) -> None:
        receipt = load_json(ACCEPTANCE_PATH)
        expected_bindings = {
            CONTRACT_PATH.relative_to(ROOT).as_posix(): sha256(CONTRACT_PATH),
            CONFIG_PATH.relative_to(ROOT).as_posix(): sha256(CONFIG_PATH),
            SCHEMA_PATH.relative_to(ROOT).as_posix(): sha256(SCHEMA_PATH),
            FIXTURE_PATH.relative_to(ROOT).as_posix(): sha256(FIXTURE_PATH),
        }
        actual_bindings = {binding["path"]: binding["sha256"] for binding in receipt["artifact_bindings"].values()}
        self.assertEqual(actual_bindings, expected_bindings)
        self.assertEqual(receipt["factory_fit_review"], "FULL_REVIEW")
        self.assertEqual(receipt["project_sources_disposition"]["kind"], "NO_CHANGE")
        self.assertEqual(receipt["state_change"], "NONE")
        for value in receipt["measured_boundary"].values():
            self.assertIn(value, (0, False))


if __name__ == "__main__":
    unittest.main()
