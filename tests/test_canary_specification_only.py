from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
TASK_DOC = ROOT / "docs/tasks/CANARY_SPECIFICATION_ONLY_V1.md"
CONTRACT = ROOT / "docs/contracts/canary_specification_only_contract_v1.md"
CONFIG = ROOT / "configs/canary_specification_only_v1.yaml"
SCHEMA = ROOT / "catalog/schemas/canary_specification_only.schema.json"
FIXTURE = (
    ROOT
    / "tests/fixtures/canary_specification_only/specification_negative_matrix_v1.json"
)
OWNER_AUTHORITY_CONTRACT = (
    ROOT / "docs/contracts/owner_authority_packet_binding_contract_v1.md"
)

REQUIRED_OWNER_INPUTS = {
    "token",
    "program",
    "route",
    "wallet_public_address",
    "proposed_notional_usd_cents",
    "maximum_separate_fees_usd_cents",
    "quote_basis",
    "expires_at",
    "monitoring_reference",
    "reconciliation_reference",
    "stop_and_recovery_procedure",
    "exact_owner_approval_phrase",
}

REQUIRED_NEGATIVE_CASE_CLASSES = {
    "NON_DRAFT_STATE",
    "NON_300_CASH_CAP",
    "MISSING_OWNER_INPUT",
    "TRUE_AUTHORITY",
    "NONZERO_PROVIDER_COUNT",
    "REAL_WALLET_OR_ENDPOINT_TEXT",
}

FORBIDDEN_MATERIAL_PATTERN = re.compile(
    r"(?im)^\s*(?:seed|private[_ -]?key|secret|transaction_signature)\s*:"
)
CONCRETE_ENDPOINT_PATTERN = re.compile(r"https://", re.IGNORECASE)


class CanarySpecificationOnlyTests(unittest.TestCase):
    def _load_contract_inputs(self) -> tuple[dict, dict, dict]:
        for path in (TASK_DOC, CONTRACT, CONFIG, SCHEMA, FIXTURE):
            if not path.is_file():
                self.fail(f"required offline specification artifact is missing: {path}")
        return (
            yaml.safe_load(CONFIG.read_text(encoding="utf-8")),
            json.loads(SCHEMA.read_text(encoding="utf-8")),
            json.loads(FIXTURE.read_text(encoding="utf-8")),
        )

    def test_draft_specification_is_offline_only_and_schema_constrained(self) -> None:
        config, schema, fixture = self._load_contract_inputs()

        self.assertEqual(config["task_id"], "CANARY_SPECIFICATION_ONLY_V1")
        self.assertEqual(
            config["safety_truth_owner"]["task_id"],
            "OWNER_AUTHORITY_PACKET_BINDING_V1",
        )
        self.assertEqual(
            config["safety_truth_owner"]["contract_sha256"],
            hashlib.sha256(OWNER_AUTHORITY_CONTRACT.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            config["specification_state"], "DRAFT_OWNER_INPUT_REQUIRED"
        )
        self.assertEqual(
            config["flow"], "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT"
        )
        self.assertEqual(config["cash_cap"]["total_cash_at_risk_usd_cents"], 300)
        self.assertEqual(set(config["owner_input_required"]), REQUIRED_OWNER_INPUTS)
        self.assertEqual(
            config["technical_wallet"],
            {
                "alias": "OWNER_LOCAL_ONLY",
                "public_address": "OWNER_LOCAL_ONLY",
                "verification_hash": "OWNER_LOCAL_ONLY",
            },
        )
        self.assertFalse(config["authority"]["canary_authority"])
        self.assertFalse(config["authority"]["task27_authority"])
        self.assertEqual(config["authority"]["execution_action"], "NONE")
        self.assertEqual(config["authority"]["numeric_netreturn"], "FORBIDDEN")
        self.assertTrue(
            all(value == 0 for value in config["side_effect_counters"].values())
        )
        self.assertEqual(
            {case["case_class"] for case in fixture["cases"]},
            REQUIRED_NEGATIVE_CASE_CLASSES,
        )

        tracked_machine_text = "\n".join(
            (
                CONFIG.read_text(encoding="utf-8"),
                FIXTURE.read_text(encoding="utf-8"),
            )
        )
        self.assertIsNone(FORBIDDEN_MATERIAL_PATTERN.search(tracked_machine_text))
        self.assertIsNone(CONCRETE_ENDPOINT_PATTERN.search(tracked_machine_text))

        acceptance_example = {
            "schema": "smial.canary-specification-only.a1",
            "schema_version": "1.0",
            "task_id": "CANARY_SPECIFICATION_ONLY_V1",
            "atom_id": "CANARY_SPECIFICATION_ONLY_V1",
            "as_of": "2026-08-06",
            "status": "PASS_OFFLINE_SPECIFICATION_DRAFT_ONLY_NO_AUTHORITY",
            "input_bindings": [
                {
                    "asset_id": "CONTRACT-CANARY-SPECIFICATION-ONLY-001",
                    "path": "docs/contracts/canary_specification_only_contract_v1.md",
                    "sha256": "0" * 64,
                }
            ],
            "decision": {
                "specification_state": "DRAFT_OWNER_INPUT_REQUIRED",
                "canary_authority": False,
                "task27_authority": False,
                "execution_action": "NONE",
                "numeric_netreturn": "FORBIDDEN",
            },
            "specification": {
                "flow": "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT",
                "total_cash_at_risk_usd_cents": 300,
                "owner_input_required": sorted(REQUIRED_OWNER_INPUTS),
                "technical_wallet": {
                    "alias": "OWNER_LOCAL_ONLY",
                    "public_address": "OWNER_LOCAL_ONLY",
                    "verification_hash": "OWNER_LOCAL_ONLY",
                },
            },
            "case_results": [
                {"case_class": case_class, "result": "REJECTED"}
                for case_class in sorted(REQUIRED_NEGATIVE_CASE_CLASSES)
            ],
            "nonclaims": [
                "NO_PROVIDER_API_RPC_WSS",
                "NO_WALLET_OR_SIGNER",
                "NO_TRANSACTION_ACTION",
                "NO_CASH_SPEND",
                "NO_TASK27_AUTHORITY",
            ],
            "side_effect_counters": {
                "provider_api_rpc_wss_calls": 0,
                "r3_paths_or_values_read": 0,
                "wallet_signer_transaction_actions": 0,
                "transaction_build_sign_simulate_send": 0,
                "cash_spend_usd_cents": 0,
                "dependency_changes": 0,
            },
        }
        errors = sorted(Draft202012Validator(schema).iter_errors(acceptance_example), key=str)
        self.assertEqual(errors, [])

    def test_draft_specification_binds_the_existing_offline_evaluator(self) -> None:
        config, _, _ = self._load_contract_inputs()
        self.assertIn("evaluator_module", config["safety_truth_owner"])

        evaluator = importlib.import_module(
            config["safety_truth_owner"]["evaluator_module"]
        )
        draft_packet = {
            "packet_state": config["specification_state"],
            "flow": config["flow"],
            "total_cash_at_risk_cap_usd_cents": config["cash_cap"][
                "total_cash_at_risk_usd_cents"
            ],
            "owner_input_fields": config["owner_input_required"],
        }
        result = evaluator.evaluate_packet(draft_packet)
        self.assertEqual(result["decision"], "OWNER_INPUT_REQUIRED")
        self.assertFalse(result["canary_authority"])
        self.assertFalse(result["task27_authority"])
        self.assertEqual(result["execution_action"], "NONE")

        negative_packets = (
            (
                {**draft_packet, "packet_state": "UNSAFE_NON_DRAFT_STATE"},
                "invalid_packet_state",
            ),
            (
                {**draft_packet, "total_cash_at_risk_cap_usd_cents": 301},
                "cash_cap_must_equal_300",
            ),
            (
                {
                    **draft_packet,
                    "owner_input_fields": draft_packet["owner_input_fields"][1:],
                },
                "draft_owner_inputs_mismatch",
            ),
        )
        for packet, expected_error in negative_packets:
            with self.subTest(expected_error=expected_error):
                with self.assertRaisesRegex(
                    evaluator.OwnerAuthorityPacketError, f"^{expected_error}$"
                ):
                    evaluator.evaluate_packet(packet)


if __name__ == "__main__":
    unittest.main()
