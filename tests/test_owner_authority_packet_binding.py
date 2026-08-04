from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from solana_alpha_lab.owner_authority_packet_binding import (
        OwnerAuthorityPacketError,
        build_binding_evidence,
        evaluate_exit_precondition,
        evaluate_packet,
        write_outputs,
    )
except ModuleNotFoundError:
    OwnerAuthorityPacketError = ValueError
    build_binding_evidence = None
    evaluate_exit_precondition = None
    evaluate_packet = None
    write_outputs = None


REQUIRED_OWNER_INPUTS = [
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
]

CONFIG = ROOT / "configs/owner_authority_packet_binding_v1.yaml"
CONTRACT = ROOT / "docs/contracts/owner_authority_packet_binding_contract_v1.md"
TASK_DOC = ROOT / "docs/tasks/OWNER_AUTHORITY_PACKET_BINDING_V1.md"
SCHEMA = ROOT / "catalog/schemas/owner_authority_packet_binding.schema.json"
FIXTURE = ROOT / "tests/fixtures/owner_authority_packet_binding/packet_binding_matrix_v1.json"
EVIDENCE = (
    ROOT
    / "docs/evidence/owner_authority_packet_binding/a1_offline_packet_binding_acceptance_v1.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

COMPLETE_PACKET = {
    "packet_state": "READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION",
    "flow": "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT",
    "total_cash_at_risk_cap_usd_cents": 300,
    "token": "SYNTHETIC_EXACT_TOKEN",
    "program": "SYNTHETIC_ALLOWED_PROGRAM",
    "route": "SYNTHETIC_ALLOWED_ROUTE",
    "wallet_public_address": "SYNTHETIC_OWNER_CONTROLLED_PUBLIC_ADDRESS",
    "proposed_notional_usd_cents": 250,
    "estimated_total_cost_usd_cents": 300,
    "maximum_separate_fees_usd_cents": 1,
    "quote_basis": "SYNTHETIC_BOUND_QUOTE_BASIS",
    "expires_at": "SYNTHETIC_EXPIRY",
    "monitoring_reference": "SYNTHETIC_MONITORING_REFERENCE",
    "reconciliation_reference": "SYNTHETIC_RECONCILIATION_REFERENCE",
    "stop_and_recovery_procedure": "SYNTHETIC_STOP_AND_RECOVERY",
    "exact_owner_approval_phrase": "SYNTHETIC_OWNER_APPROVAL_PHRASE",
}


class OwnerAuthorityPacketBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) if CONFIG.is_file() else None
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else None

    def test_contract_and_task26c_bindings_are_exact(self) -> None:
        self.assertTrue(CONTRACT.is_file())
        self.assertTrue(TASK_DOC.is_file())
        self.assertIsNotNone(self.config)
        self.assertEqual(self.config["task_id"], "OWNER_AUTHORITY_PACKET_BINDING_V1")
        self.assertEqual(self.config["cash_cap"]["total_cash_at_risk_usd_cents"], 300)
        self.assertFalse(self.config["authority"]["canary_authority"])
        self.assertFalse(self.config["authority"]["task27_authority"])
        for binding in self.config["frozen_input_bindings"]:
            with self.subTest(asset_id=binding["asset_id"]):
                self.assertEqual(sha256(ROOT / binding["path"]), binding["sha256"])

    def test_draft_remains_owner_input_required_without_authority(self) -> None:
        self.assertIsNotNone(evaluate_packet, "offline packet evaluator must exist")
        result = evaluate_packet(
            {
                "packet_state": "DRAFT_OWNER_INPUT_REQUIRED",
                "flow": "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT",
                "total_cash_at_risk_cap_usd_cents": 300,
                "owner_input_fields": REQUIRED_OWNER_INPUTS,
            }
        )
        self.assertEqual(result["packet_state"], "DRAFT_OWNER_INPUT_REQUIRED")
        self.assertEqual(result["decision"], "OWNER_INPUT_REQUIRED")
        self.assertFalse(result["canary_authority"])
        self.assertFalse(result["task27_authority"])
        self.assertEqual(result["execution_action"], "NONE")

    def test_complete_packet_is_review_only_without_authority(self) -> None:
        self.assertIsNotNone(evaluate_packet, "offline packet evaluator must exist")
        result = evaluate_packet(COMPLETE_PACKET)
        self.assertEqual(
            result["packet_state"], "READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION"
        )
        self.assertEqual(result["next_action"], "OWNER_EXACT_APPROVAL_REQUIRED")
        self.assertFalse(result["canary_authority"])
        self.assertFalse(result["task27_authority"])
        self.assertEqual(result["execution_action"], "NONE")

    def test_ready_packet_rejects_cap_breach_and_zero_separate_fee_cap(self) -> None:
        self.assertIsNotNone(evaluate_packet, "offline packet evaluator must exist")
        over_cap = {**COMPLETE_PACKET, "estimated_total_cost_usd_cents": 301}
        with self.assertRaisesRegex(OwnerAuthorityPacketError, "cash_cap_breach"):
            evaluate_packet(over_cap)
        zero_fee_cap = {**COMPLETE_PACKET, "maximum_separate_fees_usd_cents": 0}
        with self.assertRaisesRegex(
            OwnerAuthorityPacketError, "separate_fee_cap_missing_or_zero"
        ):
            evaluate_packet(zero_fee_cap)

    def test_packet_rejects_ambiguous_draft_and_missing_ready_owner_input(self) -> None:
        self.assertIsNotNone(evaluate_packet, "offline packet evaluator must exist")
        duplicate_draft = {
            "packet_state": "DRAFT_OWNER_INPUT_REQUIRED",
            "flow": "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT",
            "total_cash_at_risk_cap_usd_cents": 300,
            "owner_input_fields": [*REQUIRED_OWNER_INPUTS, "token"],
        }
        with self.assertRaisesRegex(
            OwnerAuthorityPacketError, "duplicate_draft_owner_input"
        ):
            evaluate_packet(duplicate_draft)
        incomplete_ready_packet = {key: value for key, value in COMPLETE_PACKET.items() if key != "route"}
        with self.assertRaisesRegex(
            OwnerAuthorityPacketError, "ready_packet_missing_owner_input:route"
        ):
            evaluate_packet(incomplete_ready_packet)

    def test_exit_requires_reconciled_healthy_first_leg(self) -> None:
        self.assertIsNotNone(
            evaluate_exit_precondition, "offline exit precondition evaluator must exist"
        )
        with self.assertRaisesRegex(
            OwnerAuthorityPacketError, "exit_before_first_leg_reconciliation"
        ):
            evaluate_exit_precondition(
                {"terminal_state": "LANDED_SUCCESS", "reconciled": False}
            )

    def test_exit_blocks_unknown_and_all_critical_health_failures(self) -> None:
        self.assertIsNotNone(
            evaluate_exit_precondition, "offline exit precondition evaluator must exist"
        )
        baseline = {
            "terminal_state": "LANDED_SUCCESS",
            "reconciled": True,
            "monitoring_healthy": True,
            "inventory_match": True,
            "allowlist_match": True,
            "fee_cap_ok": True,
        }
        negative_cases = (
            ("terminal_state", "UNKNOWN_REQUIRES_RECONCILIATION", "exit_requires_landed_success_first_leg"),
            ("monitoring_healthy", False, "exit_blocked_monitoring_loss"),
            ("inventory_match", False, "exit_blocked_inventory_mismatch"),
            ("allowlist_match", False, "exit_blocked_route_program_mismatch"),
            ("fee_cap_ok", False, "exit_blocked_fee_cap_breach"),
        )
        for field, value, code in negative_cases:
            with self.subTest(field=field):
                with self.assertRaisesRegex(OwnerAuthorityPacketError, code):
                    evaluate_exit_precondition({**baseline, field: value})

    def test_fixture_and_evidence_are_deterministic_and_non_authorizing(self) -> None:
        self.assertIsNotNone(build_binding_evidence, "offline evidence builder must exist")
        self.assertIsNotNone(write_outputs, "offline evidence writer must exist")
        self.assertIsNotNone(self.fixture)
        evidence = build_binding_evidence(ROOT)
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(evidence)
        self.assertEqual(evidence["owner_packet"]["status"], "DRAFT_OWNER_INPUT_REQUIRED")
        self.assertFalse(evidence["decision"]["canary_authority"])
        self.assertFalse(evidence["decision"]["task27_authority"])
        self.assertEqual(evidence["decision"]["execution_action"], "NONE")
        self.assertEqual(len(evidence["case_results"]), len(self.fixture["cases"]))
        self.assertTrue(all(value == 0 for value in evidence["side_effect_counters"].values()))
        write_outputs(ROOT)
        self.assertEqual(json.loads(EVIDENCE.read_text(encoding="utf-8")), evidence)


if __name__ == "__main__":
    unittest.main()
