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
CONTRACT_PATH = ROOT / "docs/contracts/task27_exact_single_pool_selection_and_pilot_read_packet_v1.md"
CONFIG_PATH = ROOT / "configs/task27_exact_single_pool_selection_and_pilot_read_packet_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_exact_single_pool_selection_and_pilot_read_packet.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/exact_single_pool_selection_and_pilot_read_packet_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task27/a0a7_exact_single_pool_selection_and_pilot_read_packet_acceptance_v1.json"
A6_CONTRACT_PATH = ROOT / "docs/contracts/task27_exact_owner_external_read_review_contract_v1.md"
A6_CONFIG_PATH = ROOT / "configs/task27_exact_owner_external_read_review_contract_v1.yaml"
SOURCE_SMOKE_RECEIPT_PATH = ROOT / "docs/evidence/task27/a0a5r1_project_sources_activation_receipt_v1.json"
REQUIRED_PATHS = (
    CONTRACT_PATH,
    CONFIG_PATH,
    SCHEMA_PATH,
    FIXTURE_PATH,
)
EXPECTED_ERRORS = {
    "WRONG_NETWORK",
    "WRONG_POOL",
    "UNVERIFIED_HINT_PROMOTION",
    "SELECTION_HASH_MISMATCH",
    "UNALIGNED_BEFORE_TIMESTAMP",
    "FLOATING_WINDOW_FORBIDDEN",
    "REQUEST_COUNT_MISMATCH",
    "NON_GET_METHOD",
    "REQUEST_URL_MISMATCH",
    "EMPTY_INTERVAL_IMPUTATION_FORBIDDEN",
    "PANEL_RULE_RELAXATION_FORBIDDEN",
    "RAW_MANIFEST_REQUIRED",
    "FALLBACK_PROVIDER_FORBIDDEN",
    "AUTHORITY_PROMOTION_FORBIDDEN",
    "EXTERNAL_ACTION_IN_A7_FORBIDDEN",
    "RAW_RETENTION_IN_A7_FORBIDDEN",
    "FORBIDDEN_DECISION_CLAIM",
    "PREMATURE_APPROVAL_FORBIDDEN",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
    selection = packet["selection_snapshot"]
    pilot = packet["pilot"]
    acceptance = packet["future_acceptance"]
    authority = packet["authority"]
    claims = packet["claims"]
    approval = packet["future_owner_approval"]

    expected_selection = policy["selection_snapshot"]
    expected_content = expected_selection["content"]
    content = selection["content"]
    if content["network"] != expected_content["network"]:
        errors.add("WRONG_NETWORK")
    if content["pool_address"] != expected_content["pool_address"]:
        errors.add("WRONG_POOL")
    if selection["page_hints"]["state"] != "UNVERIFIED_HINT_ONLY":
        errors.add("UNVERIFIED_HINT_PROMOTION")
    if (
        selection["sha256"] != expected_selection["sha256"]
        or canonical_json_sha256(content) != selection["sha256"]
    ):
        errors.add("SELECTION_HASH_MISMATCH")

    expected_pilot = policy["pilot"]
    if pilot["before_timestamp"] % pilot["interval_seconds"] != 0:
        errors.add("UNALIGNED_BEFORE_TIMESTAMP")
    if pilot["window_mode"] != "FROZEN_BEFORE_TIMESTAMP":
        errors.add("FLOATING_WINDOW_FORBIDDEN")
    if pilot["request_count"] != 2 or len(pilot["requests"]) != 2:
        errors.add("REQUEST_COUNT_MISMATCH")
    if any(request["method"] != "GET" for request in pilot["requests"]):
        errors.add("NON_GET_METHOD")
    if (
        pilot["provider"] != expected_pilot["provider"]
        or pilot["base_url"] != expected_pilot["base_url"]
        or [request["kind"] for request in pilot["requests"]]
        != [request["kind"] for request in expected_pilot["requests"]]
        or [request["url"] for request in pilot["requests"]]
        != [request["url"] for request in expected_pilot["requests"]]
    ):
        errors.add("REQUEST_URL_MISMATCH")
    if pilot["include_empty_intervals"] is not False:
        errors.add("EMPTY_INTERVAL_IMPUTATION_FORBIDDEN")
    if pilot["raw_evidence_manifest_id"] != expected_pilot["raw_evidence_manifest_id"]:
        errors.add("RAW_MANIFEST_REQUIRED")
    if pilot["automatic_fallback_provider"] is not None:
        errors.add("FALLBACK_PROVIDER_FORBIDDEN")

    expected_acceptance = policy["future_acceptance"]
    panel_rule_fields = (
        "timestamps_unique_required",
        "timestamps_ascending_required",
        "timestamps_aligned_required",
        "natural_observations_only",
        "ohlc_positive_required",
        "ohlc_consistent_required",
        "carried_forward_forbidden",
    )
    if (
        acceptance["runtime_outcomes"] != expected_acceptance["runtime_outcomes"]
        or acceptance["current_state"] != expected_acceptance["current_state"]
        or acceptance["gaps_allowed"] is not False
        or acceptance["duplicates_allowed"] is not False
        or acceptance["volume_currency"] != expected_acceptance["volume_currency"]
        or acceptance["missing_result"] != "UNKNOWN"
        or any(acceptance[field] is not True for field in panel_rule_fields)
    ):
        errors.add("PANEL_RULE_RELAXATION_FORBIDDEN")

    if authority["provider_read_authority"] is not False:
        errors.add("AUTHORITY_PROMOTION_FORBIDDEN")
    if authority["provider_api_rpc_wss_calls"] != 0:
        errors.add("EXTERNAL_ACTION_IN_A7_FORBIDDEN")
    if authority["raw_provider_responses_retained"] != 0:
        errors.add("RAW_RETENTION_IN_A7_FORBIDDEN")

    forbidden_claims = (
        claims["representative_sample"],
        claims["pit_admissible"],
        claims["alpha"],
        claims["execution"],
        claims["pnl"],
        claims["netreturn"],
        claims["cashflow"],
    )
    if (
        claims["scope"] != policy["claims"]["scope"]
        or claims["history_grade"] != policy["claims"]["history_grade"]
        or any(forbidden_claims)
    ):
        errors.add("FORBIDDEN_DECISION_CLAIM")

    expected_approval = policy["future_owner_approval"]
    if (
        approval["state"] != expected_approval["state"]
        or approval["approval_granted"] is not False
        or approval["phrase"] != expected_approval["phrase"]
    ):
        errors.add("PREMATURE_APPROVAL_FORBIDDEN")
    return errors


class ExactSinglePoolSelectionAndPilotReadPacketTests(unittest.TestCase):
    def test_required_assets_exist(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)

    def test_policy_binds_a6_source_smoke_selection_and_exact_urls(self) -> None:
        policy = load_yaml(CONFIG_PATH)
        selection = policy["selection_snapshot"]
        pilot = policy["pilot"]

        self.assertEqual(sha256(A6_CONTRACT_PATH), policy["inherits"]["a6_contract"]["sha256"])
        self.assertEqual(sha256(A6_CONFIG_PATH), policy["inherits"]["a6_config"]["sha256"])
        self.assertEqual(
            policy["source_smoke"]["receipt_sha256"],
            sha256(SOURCE_SMOKE_RECEIPT_PATH),
        )
        self.assertEqual(canonical_json_sha256(selection["content"]), selection["sha256"])
        self.assertEqual(
            selection["sha256"],
            "922e2b1f529d5e1d2beab34c93320914a0ac9670a956c0123fb69ba5ad5315a2",
        )
        self.assertEqual(pilot["request_count"], 2)
        self.assertEqual(pilot["before_timestamp"], 1786186800)
        self.assertEqual(pilot["before_timestamp"] % 900, 0)
        self.assertEqual(pilot["window_mode"], "FROZEN_BEFORE_TIMESTAMP")
        self.assertFalse(pilot["include_empty_intervals"])

    def test_valid_offline_packet_is_schema_valid_and_never_authorized(self) -> None:
        schema = load_json(SCHEMA_PATH)
        fixture = load_json(FIXTURE_PATH)

        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(fixture)), [])
        self.assertEqual(
            list(Draft202012Validator(packet_schema(schema)).iter_errors(fixture["valid_packet"])),
            [],
        )
        self.assertEqual(semantic_errors(fixture["valid_packet"], load_yaml(CONFIG_PATH)), set())
        self.assertFalse(fixture["valid_packet"]["authority"]["provider_read_authority"])

    def test_each_adversarial_case_rejects_one_specific_boundary_break(self) -> None:
        schema = load_json(SCHEMA_PATH)
        fixture = load_json(FIXTURE_PATH)
        validator = Draft202012Validator(packet_schema(schema))
        policy = load_yaml(CONFIG_PATH)

        self.assertEqual(
            {case["expected_error"] for case in fixture["adversarial_cases"]},
            EXPECTED_ERRORS,
        )
        for case in fixture["adversarial_cases"]:
            with self.subTest(case=case["case_id"]):
                packet = copy.deepcopy(fixture["valid_packet"])
                apply_json_pointer(packet, case["pointer"], case["value"])
                self.assertEqual(list(validator.iter_errors(packet)), [])
                errors = semantic_errors(packet, policy)
                self.assertIn(case["expected_error"], errors)
                self.assertTrue(errors <= EXPECTED_ERRORS)


if __name__ == "__main__":
    unittest.main()
