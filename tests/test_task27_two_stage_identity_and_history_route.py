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
CONTRACT_PATH = ROOT / "docs/contracts/task27_two_stage_identity_and_history_route_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_two_stage_identity_and_history_route_contract_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_two_stage_identity_and_history_route.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/two_stage_identity_and_history_route_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task27/a1r1_two_stage_identity_and_history_route_acceptance_v1.json"
A7_CONFIG_PATH = ROOT / "configs/task27_exact_single_pool_selection_and_pilot_read_packet_v1.yaml"
SOURCE_SMOKE_RECEIPT_PATH = ROOT / "docs/evidence/task27/a0a5r1_project_sources_activation_receipt_v1.json"
REQUIRED_PATHS = (
    CONTRACT_PATH,
    CONFIG_PATH,
    SCHEMA_PATH,
    FIXTURE_PATH,
    ACCEPTANCE_PATH,
)

EXPECTED_ERRORS = {
    "DEXSCREENER_URL_DRIFT",
    "STAGE_A_REQUEST_CAP_BREACH",
    "STAGE_A_IDENTITY_MISMATCH",
    "STAGE_B_BEFORE_FROZEN_IDENTITY",
    "TOKEN_ONLY_OR_DYNAMIC_POOL_FORBIDDEN",
    "HIDDEN_TRANSFORMATION_FORBIDDEN",
    "SECRET_TRANSPORT_FORBIDDEN",
    "UNBOUNDED_QUOTA_FORBIDDEN",
    "AUTOMATIC_FALLBACK_FORBIDDEN",
    "HELIUS_RECONSTRUCTION_FORBIDDEN",
    "RAW_MANIFEST_REQUIRED",
    "PANEL_RULE_RELAXATION_FORBIDDEN",
    "OFFLINE_AUTHORITY_PROMOTION_FORBIDDEN",
    "EXTERNAL_ACTION_IN_OFFLINE_ATOM",
    "RAW_RETENTION_IN_OFFLINE_ATOM",
    "FORBIDDEN_DECISION_CLAIM",
    "PREMATURE_OWNER_APPROVAL_FORBIDDEN",
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
    stage_a = packet["stage_a"]
    stage_b = packet["stage_b"]
    future_acceptance = packet["future_acceptance"]
    authority = packet["authority"]
    claims = packet["claims"]
    approval = packet["future_owner_approval"]
    nominated = policy["owner_nominated_pool"]

    if (
        stage_a["provider"] != policy["stage_a"]["provider"]
        or stage_a["method"] != policy["stage_a"]["method"]
        or stage_a["url"] != policy["stage_a"]["url"]
    ):
        errors.add("DEXSCREENER_URL_DRIFT")
    if stage_a["request_count"] != policy["stage_a"]["request_count"]:
        errors.add("STAGE_A_REQUEST_CAP_BREACH")
    if (
        stage_a["identity_state"] != policy["stage_a"]["output"]
        or stage_a["identity"]["network"] != nominated["network"]
        or stage_a["identity"]["pool_address"] != nominated["pool_address"]
        or not stage_a["identity"]["base_mint"]
        or not stage_a["identity"]["quote_mint"]
        or not stage_a["identity"]["dex_id"]
    ):
        errors.add("STAGE_A_IDENTITY_MISMATCH")
    if stage_b["activation_state"] != policy["stage_b"]["activation_state"]:
        errors.add("STAGE_B_BEFORE_FROZEN_IDENTITY")
    if stage_b["route_kind"] != policy["stage_b"]["route_kind"] or stage_b["dynamic_pool_selection"]:
        errors.add("TOKEN_ONLY_OR_DYNAMIC_POOL_FORBIDDEN")
    if stage_b["removeOutliers"] is not False or stage_b["fastCache"] is not False:
        errors.add("HIDDEN_TRANSFORMATION_FORBIDDEN")
    secret_markers = ("api-key", "api_key", "key=")
    endpoint_values = (stage_b["token_endpoint_template"], stage_b["pool_chart_endpoint_template"])
    if (
        stage_b["credential_transport"] != policy["stage_b"]["credential_transport"]
        or any(marker in endpoint.lower() for endpoint in endpoint_values for marker in secret_markers)
    ):
        errors.add("SECRET_TRANSPORT_FORBIDDEN")
    if stage_b["quota_state"] != policy["stage_b"]["quota_and_cost"]["state"] or stage_b["cash_cost_claim"] != "NOT_MADE":
        errors.add("UNBOUNDED_QUOTA_FORBIDDEN")
    if stage_a["automatic_fallback_provider"] is not None or stage_b["automatic_fallback_provider"] is not None:
        errors.add("AUTOMATIC_FALLBACK_FORBIDDEN")
    if stage_b["helius_transaction_reconstruction"] != policy["stage_b"]["helius_transaction_reconstruction"]:
        errors.add("HELIUS_RECONSTRUCTION_FORBIDDEN")
    if (
        not stage_a["raw_manifest"]["id"]
        or not stage_b["raw_manifest"]["id"]
        or stage_a["raw_manifest"]["state"] != "FUTURE_EXTERNAL_RAW_MANIFEST_REQUIRED"
        or stage_b["raw_manifest"]["state"] != "FUTURE_EXTERNAL_RAW_MANIFEST_REQUIRED"
    ):
        errors.add("RAW_MANIFEST_REQUIRED")
    if (
        stage_b["request_count_max"] != policy["stage_b"]["request_count_max"]
        or stage_b["type"] != policy["stage_b"]["chart_parameters"]["type"]
        or stage_b["time_from"] != policy["stage_b"]["chart_parameters"]["time_from"]
        or stage_b["time_to"] != policy["stage_b"]["chart_parameters"]["time_to"]
        or stage_b["currency"] != policy["stage_b"]["chart_parameters"]["currency"]
        or stage_b["timezone"] != policy["stage_b"]["chart_parameters"]["timezone"]
        or stage_b["interval_seconds"] != 900
        or stage_b["panel_duration_hours"] != 24
        or stage_b["required_natural_bars"] != 96
        or future_acceptance["runtime_outcomes"] != policy["future_acceptance"]["runtime_outcomes"]
        or future_acceptance["missing_result"] != "UNKNOWN"
        or future_acceptance["gaps_allowed"]
        or future_acceptance["duplicates_allowed"]
        or not all(
            future_acceptance[field]
            for field in (
                "timestamps_unique_required",
                "timestamps_ascending_required",
                "timestamps_aligned_required",
                "natural_observations_only",
                "ohlc_positive_required",
                "ohlc_consistent_required",
                "carried_forward_forbidden",
            )
        )
        or future_acceptance["volume_currency"] != "usd"
    ):
        errors.add("PANEL_RULE_RELAXATION_FORBIDDEN")
    if authority["provider_read_authority"]:
        errors.add("OFFLINE_AUTHORITY_PROMOTION_FORBIDDEN")
    if authority["provider_api_rpc_wss_calls"] != 0:
        errors.add("EXTERNAL_ACTION_IN_OFFLINE_ATOM")
    if authority["raw_provider_responses_retained"] != 0:
        errors.add("RAW_RETENTION_IN_OFFLINE_ATOM")
    if (
        claims["scope"] != policy["claims"]["scope"]
        or claims["history_grade"] != policy["claims"]["history_grade"]
        or any(
            claims[field]
            for field in (
                "representative_sample",
                "pit_admissible",
                "alpha",
                "execution",
                "pnl",
                "netreturn",
                "cashflow",
            )
        )
    ):
        errors.add("FORBIDDEN_DECISION_CLAIM")
    if (
        approval["state"] != policy["future_owner_approval"]["state"]
        or approval["approval_granted"]
        or approval["stage_a_request_authorized"]
        or approval["stage_b_request_authorized"]
    ):
        errors.add("PREMATURE_OWNER_APPROVAL_FORBIDDEN")
    return errors


class TwoStageIdentityAndHistoryRouteTests(unittest.TestCase):
    def test_required_assets_exist(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)

    def test_policy_binds_a7_and_freezes_stage_a_only(self) -> None:
        policy = load_yaml(CONFIG_PATH)
        self.assertEqual(sha256(A7_CONFIG_PATH), policy["source_binding"]["a7_config"]["sha256"])
        self.assertEqual(
            sha256(SOURCE_SMOKE_RECEIPT_PATH),
            policy["source_binding"]["source_smoke_receipt"]["sha256"],
        )
        self.assertEqual(
            policy["owner_nominated_pool"]["selection_snapshot_sha256"],
            "922e2b1f529d5e1d2beab34c93320914a0ac9670a956c0123fb69ba5ad5315a2",
        )
        self.assertEqual(policy["stage_a"]["request_count"], 1)
        self.assertFalse(policy["stage_a"]["provider_read_authority"])
        self.assertEqual(policy["stage_b"]["request_count_max"], 2)
        self.assertFalse(policy["stage_b"]["provider_read_authority"])
        self.assertEqual(policy["stage_b"]["route_kind"], "POOL_SPECIFIC_ONLY")
        self.assertFalse(policy["stage_b"]["dynamic_pool_selection"])

    def test_valid_packet_is_schema_valid_and_offline(self) -> None:
        schema = load_json(SCHEMA_PATH)
        fixture = load_json(FIXTURE_PATH)
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(fixture)), [])
        self.assertEqual(
            list(Draft202012Validator(packet_schema(schema)).iter_errors(fixture["valid_packet"])),
            [],
        )
        self.assertFalse(fixture["valid_packet"]["authority"]["provider_read_authority"])
        self.assertEqual(fixture["valid_packet"]["authority"]["provider_api_rpc_wss_calls"], 0)

    def test_semantic_invariants_accept_the_valid_packet(self) -> None:
        fixture = load_json(FIXTURE_PATH)
        self.assertEqual(semantic_errors(fixture["valid_packet"], load_yaml(CONFIG_PATH)), set())

    def test_each_adversarial_case_breaks_its_named_boundary(self) -> None:
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

    def test_acceptance_receipt_binds_assets_and_preserves_full_review(self) -> None:
        self.assertTrue(ACCEPTANCE_PATH.is_file(), ACCEPTANCE_PATH)
        receipt = load_json(ACCEPTANCE_PATH)
        expected_bindings = {
            CONTRACT_PATH.relative_to(ROOT).as_posix(): sha256(CONTRACT_PATH),
            CONFIG_PATH.relative_to(ROOT).as_posix(): sha256(CONFIG_PATH),
            SCHEMA_PATH.relative_to(ROOT).as_posix(): sha256(SCHEMA_PATH),
            FIXTURE_PATH.relative_to(ROOT).as_posix(): sha256(FIXTURE_PATH),
        }
        actual_bindings = {
            binding["path"]: binding["sha256"]
            for binding in receipt["artifact_bindings"].values()
        }
        self.assertEqual(actual_bindings, expected_bindings)
        self.assertEqual(receipt["factory_fit_review"], "FULL_REVIEW")
        self.assertEqual(receipt["validation"]["targeted_tests_run"], 6)
        self.assertEqual(receipt["validation"]["adversarial_cases_rejected"], 17)
        self.assertEqual(receipt["project_sources_disposition"]["kind"], "NO_CHANGE")
        self.assertEqual(receipt["state_change"], "NONE")
        self.assertFalse(receipt["next_boundary"]["provider_read_authority_granted"])
        self.assertFalse(receipt["next_boundary"]["solana_tracker_stage_b_authorized"])
        for value in receipt["measured_boundary"].values():
            self.assertIn(value, (0, False))


if __name__ == "__main__":
    unittest.main()
