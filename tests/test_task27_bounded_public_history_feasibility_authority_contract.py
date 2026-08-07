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
CONTRACT_PATH = ROOT / "docs/contracts/task27_bounded_public_history_feasibility_authority_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_bounded_public_history_feasibility_authority_contract_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_bounded_public_history_feasibility_authority.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/bounded_public_history_feasibility_authority_v1.json"
REQUIRED_PATHS = [CONTRACT_PATH, CONFIG_PATH, SCHEMA_PATH, FIXTURE_PATH]
EXPECTED_WRITE_SET = [
    "docs/contracts/task27_bounded_public_history_feasibility_authority_contract_v1.md",
    "configs/task27_bounded_public_history_feasibility_authority_contract_v1.yaml",
    "catalog/schemas/task27_bounded_public_history_feasibility_authority.schema.json",
    "tests/fixtures/task27/bounded_public_history_feasibility_authority_v1.json",
    "tests/test_task27_bounded_public_history_feasibility_authority_contract.py",
    "docs/evidence/task27/a0a4_bounded_public_history_feasibility_authority_acceptance_v1.json",
]
EXPECTED_ADVERSARIAL_ERRORS = {
    "SOURCE_ALIGNMENT_REQUIRED",
    "DISCOVERY_CAP_EXCEEDED",
    "OHLCV_CAP_EXCEEDED",
    "INSUFFICIENT_COMPLETE_PANELS",
    "UNFROZEN_SELECTION_SNAPSHOT",
    "AUTO_FALLBACK_PROVIDER_FORBIDDEN",
    "RAW_EVIDENCE_MANIFEST_REQUIRED",
    "PIT_CLAIM_WITHOUT_AVAILABILITY_PROOF",
    "FORBIDDEN_CLAIM_SCOPE",
    "EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN",
}


def apply_json_pointer(document: dict[str, Any], pointer: str, value: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    target: Any = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final = parts[-1]
    if isinstance(target, list):
        target[int(final)] = copy.deepcopy(value)
    else:
        target[final] = copy.deepcopy(value)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(packet: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    proposal = packet["proposal"]
    evidence = packet["evidence"]
    source_binding = packet["source_binding"]
    decision = packet["decision"]

    if decision["outcome"] == "READY_FOR_EXACT_OWNER_EXTERNAL_READ_REVIEW" and (
        source_binding["state"] != "ACTIVATION_CONFIRMED_USER_SMOKE"
        or not source_binding["receipt_reference"]
    ):
        errors.add("SOURCE_ALIGNMENT_REQUIRED")
    if proposal["discovery_requests"] > 6:
        errors.add("DISCOVERY_CAP_EXCEEDED")
    if proposal["ohlcv_requests"] > 24:
        errors.add("OHLCV_CAP_EXCEEDED")
    if proposal["complete_panels"] < 12:
        errors.add("INSUFFICIENT_COMPLETE_PANELS")
    if not proposal["selection_snapshot_sha256"]:
        errors.add("UNFROZEN_SELECTION_SNAPSHOT")
    if proposal["automatic_fallback_provider"]:
        errors.add("AUTO_FALLBACK_PROVIDER_FORBIDDEN")
    if not evidence["raw_evidence_manifest_id"]:
        errors.add("RAW_EVIDENCE_MANIFEST_REQUIRED")
    if evidence["grade"] == "PIT_ADMISSIBLE" and not evidence["availability_proof"]:
        errors.add("PIT_CLAIM_WITHOUT_AVAILABILITY_PROOF")
    if decision["claim_scope"] != "HISTORICAL_FEASIBILITY_ONLY":
        errors.add("FORBIDDEN_CLAIM_SCOPE")
    if decision["provider_read_authority"]:
        errors.add("EXTERNAL_AUTHORITY_PROMOTION_FORBIDDEN")
    return errors


class Task27BoundedPublicHistoryFeasibilityAuthorityContractTests(unittest.TestCase):
    def test_all_required_contract_artifacts_exist(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), path)

    def test_fixture_passes_schema_and_is_synthetic_only(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(fixture)), [])
        self.assertEqual(fixture["fixture_kind"], "SYNTHETIC_GOLDEN_ONLY")

    def test_ready_packet_remains_descriptive_and_has_no_provider_authority(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        packet = fixture["valid_packets"][0]
        self.assertEqual(packet["evidence"]["grade"], "DESCRIPTIVE_ONLY")
        self.assertIsNone(packet["evidence"]["availability_proof"])
        self.assertEqual(packet["source_binding"]["state"], "ACTIVATION_CONFIRMED_USER_SMOKE")
        self.assertFalse(packet["decision"]["provider_read_authority"])
        self.assertEqual(semantic_errors(packet), set())

    def test_ready_packet_binds_selection_time_and_universe_description(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        proposal = fixture["valid_packets"][0]["proposal"]
        self.assertIn("selection_snapshot_at", proposal)
        self.assertIn("universe_description", proposal)
        self.assertTrue(proposal["selection_snapshot_at"])
        self.assertTrue(proposal["universe_description"])

    def test_ready_packet_requires_a_source_smoke_reference(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        packet = copy.deepcopy(fixture["valid_packets"][0])
        packet["source_binding"]["receipt_reference"] = None
        self.assertEqual(semantic_errors(packet), {"SOURCE_ALIGNMENT_REQUIRED"})

    def test_adversarial_packets_reject_each_authority_expansion(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        expected_errors = {case["expected_error"] for case in fixture["adversarial_cases"]}
        self.assertEqual(expected_errors, EXPECTED_ADVERSARIAL_ERRORS)
        base = fixture["valid_packets"][0]
        for case in fixture["adversarial_cases"]:
            with self.subTest(case_id=case["case_id"]):
                changed = copy.deepcopy(base)
                for mutation in case["mutations"]:
                    apply_json_pointer(changed, mutation["json_pointer"], mutation["replacement"])
                self.assertIn(case["expected_error"], semantic_errors(changed))

    def test_config_freezes_source_binding_caps_and_zero_authority(self) -> None:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["managed_write_set"], EXPECTED_WRITE_SET)
        self.assertEqual(config["source_candidate"], "GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE")
        self.assertEqual(
            config["source_binding"]["required_ready_state"],
            "ACTIVATION_CONFIRMED_USER_SMOKE",
        )
        self.assertEqual(config["sampling_plan"]["discovery_requests_max"], 6)
        self.assertEqual(config["sampling_plan"]["ohlcv_requests_max"], 24)
        self.assertEqual(config["sampling_plan"]["complete_panels_min"], 12)
        self.assertEqual(config["sampling_plan"]["panel_duration_hours"], 24)
        self.assertEqual(config["sampling_plan"]["interval_seconds"], 900)
        for key in (
            "provider_api_rpc_wss_calls",
            "r2_value_reads",
            "r3_value_or_path_reads",
            "wallet_signer_transaction_actions",
            "cash_spend_usd_cents",
            "raw_provider_responses_retained",
        ):
            self.assertEqual(config["authority"][key], 0, key)
        self.assertFalse(config["authority"]["provider_read_authority"])
        self.assertFalse(config["authority"]["catalog_or_registry_mutation"])
        self.assertFalse(config["authority"]["project_source_changes"])

    def test_artifacts_are_normalized(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertNotIn(b"\r\n", payload)
                self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
