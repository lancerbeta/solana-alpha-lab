from __future__ import annotations

import copy
import hashlib
import json
import unittest
from typing import Any
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/contracts/task27_exact_owner_external_read_review_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_exact_owner_external_read_review_contract_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_exact_owner_external_read_review.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/exact_owner_external_read_review_v1.json"
SOURCE_SMOKE_RECEIPT_PATH = ROOT / "docs/evidence/task27/a0a5r1_project_sources_activation_receipt_v1.json"
REQUIRED_PATHS = (
    CONTRACT_PATH,
    CONFIG_PATH,
    SCHEMA_PATH,
    FIXTURE_PATH,
)
EXPECTED_ERRORS = {
    "AUTHORITY_PROMOTION_FORBIDDEN",
    "EXTERNAL_ACTION_IN_A6_FORBIDDEN",
    "RAW_RETENTION_IN_A6_FORBIDDEN",
    "SOURCE_SMOKE_BINDING_REQUIRED",
    "UNBOUND_FUTURE_REQUEST_FORBIDDEN",
    "ACTUAL_EVIDENCE_CLAIM_FORBIDDEN",
    "FALLBACK_PROVIDER_FORBIDDEN",
    "INHERITED_CAP_BREACH",
    "FORBIDDEN_DECISION_CLAIM",
    "PREMATURE_APPROVAL_PHRASE_FORBIDDEN",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    return {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/packet",
    }


def semantic_errors(packet: dict[str, Any], policy: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    authority = packet["authority"]
    review = packet["review"]
    future_request = review["future_request"]
    caps = packet["inherited_capture"]
    claims = packet["claims"]
    approval = packet["future_owner_approval"]

    if authority["provider_read_authority"] is not False:
        errors.add("AUTHORITY_PROMOTION_FORBIDDEN")
    if authority["provider_api_rpc_wss_calls"] != 0:
        errors.add("EXTERNAL_ACTION_IN_A6_FORBIDDEN")
    if authority["raw_provider_responses_retained"] != 0:
        errors.add("RAW_RETENTION_IN_A6_FORBIDDEN")

    smoke = policy["source_smoke"]
    if (
        review["source_smoke_state"] != smoke["required_state"]
        or review["source_smoke_receipt_path"] != smoke["receipt_path"]
        or review["source_smoke_receipt_sha256"] != smoke["receipt_sha256"]
    ):
        errors.add("SOURCE_SMOKE_BINDING_REQUIRED")

    placeholder = policy["future_request"]["placeholder"]
    for field in policy["future_request"]["required_owner_input_fields"]:
        if future_request[field] != placeholder:
            error = "ACTUAL_EVIDENCE_CLAIM_FORBIDDEN" if field == "pool_identity" else "UNBOUND_FUTURE_REQUEST_FORBIDDEN"
            errors.add(error)

    if review["source_candidate"] != policy["source_candidate"] or review["fallback_provider"] is not None:
        errors.add("FALLBACK_PROVIDER_FORBIDDEN")

    policy_caps = policy["inherited_capture_caps"]
    if (
        caps["discovery_requests_max"] > policy_caps["discovery_requests_max"]
        or caps["ohlcv_requests_max"] > policy_caps["ohlcv_requests_max"]
        or caps["interval_seconds"] != policy_caps["interval_seconds"]
        or caps["panel_duration_hours"] != policy_caps["panel_duration_hours"]
        or caps["complete_panels_min"] < policy_caps["complete_panels_min"]
    ):
        errors.add("INHERITED_CAP_BREACH")

    forbidden_claims = (
        claims["alpha_claim"],
        claims["execution_claim"],
        claims["pnl_claim"],
        claims["netreturn_claim"],
        claims["cashflow_claim"],
    )
    if (
        claims["scope"] != policy["claim_scope"]
        or claims["history_grade"] != policy["history_grade"]
        or any(forbidden_claims)
    ):
        errors.add("FORBIDDEN_DECISION_CLAIM")

    if (
        approval["state"] != policy["future_request"]["approval_template_state"]
        or approval["approval_granted"] is not False
    ):
        errors.add("PREMATURE_APPROVAL_PHRASE_FORBIDDEN")
    return errors


class ExactOwnerExternalReadReviewContractTests(unittest.TestCase):
    def test_required_review_assets_exist(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)

    def test_policy_binds_current_source_smoke_and_a4_limits(self) -> None:
        policy = load_yaml(CONFIG_PATH)
        self.assertEqual(policy["consumer"], "OWNER_EXTERNAL_READ_REVIEW")
        self.assertEqual(policy["source_candidate"], "GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE")
        self.assertEqual(policy["source_smoke"]["receipt_path"], SOURCE_SMOKE_RECEIPT_PATH.relative_to(ROOT).as_posix())
        self.assertEqual(policy["source_smoke"]["receipt_sha256"], sha256(SOURCE_SMOKE_RECEIPT_PATH))
        self.assertEqual(
            policy["inherited_capture_caps"],
            {
                "discovery_requests_max": 6,
                "ohlcv_requests_max": 24,
                "interval_seconds": 900,
                "panel_duration_hours": 24,
                "complete_panels_min": 12,
            },
        )

    def test_valid_synthetic_packet_is_schema_valid_and_never_authorized(self) -> None:
        schema = load_json(SCHEMA_PATH)
        fixture = load_json(FIXTURE_PATH)
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(fixture)), [])
        self.assertEqual(list(Draft202012Validator(packet_schema(schema)).iter_errors(fixture["valid_packet"])), [])
        self.assertEqual(semantic_errors(fixture["valid_packet"], load_yaml(CONFIG_PATH)), set())
        self.assertFalse(fixture["valid_packet"]["authority"]["provider_read_authority"])

    def test_each_adversarial_case_rejects_one_specific_boundary_break(self) -> None:
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
                self.assertEqual(semantic_errors(packet, policy), {case["expected_error"]})


if __name__ == "__main__":
    unittest.main()
