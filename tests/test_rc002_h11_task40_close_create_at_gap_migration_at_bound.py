from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.rc002_h11_create_early_six_field_layout import (  # noqa: E402
    GETTX_FIXTURE_RELATIVE,
)
from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (  # noqa: E402
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
    TASK40_ACCEPTANCE_RELATIVE,
)
from solana_alpha_lab.rc002_h11_task40_close_create_at_gap_migration_at_bound import (  # noqa: E402
    ATOM_ID,
    CREATE_AT_RECEIPT_RELATIVE,
    CREATE_AT_STATUS,
    EXPECTED_CREATE_AT_RECEIPT_SHA256,
    EXPECTED_MIGRATION_RECEIPT_SHA256,
    EXPECTED_TASK40_ACCEPTANCE_SHA256,
    MIGRATION_RECEIPT_RELATIVE,
    TASK40_CAPTURE_TERMINAL,
    TASK40_TRIAL_OUTCOME,
    TERMINAL_OUTCOMES,
    bind_task40_close_create_at_gap_migration_at_bound,
    decide_task40_close_terminal,
)

CONTRACT_PATH = ROOT / (
    "docs/tasks/RC002-H11-TASK40-CLOSE-CREATE-AT-GAP-MIGRATION-AT-BOUND-V1.md"
)
PINNED_DECODER = ROOT / "src/solana_alpha_lab/pump_event_decoder.py"
TASK37_POLICY = ROOT / "configs/task37_rc002_h11_migration_clock_capture_v1.yaml"
TASK40_LEDGER = ROOT / "registries/global_trial_ledger.yaml"
MODULE_PATH = ROOT / (
    "src/solana_alpha_lab/rc002_h11_task40_close_create_at_gap_migration_at_bound.py"
)
ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/"
    "a1_task40_close_create_at_gap_migration_at_bound_acceptance_v1.json"
)


class Task40CloseCreateAtGapMigrationAtBoundTests(unittest.TestCase):
    def test_contract_names_offline_caps_and_close_stops(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "task_id: RC002-H11-TASK40-CLOSE-CREATE-AT-GAP-MIGRATION-AT-BOUND-V1",
            text,
        )
        self.assertIn("network: false", text)
        self.assertIn("TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND", text)
        self.assertIn("TASK40_CLOSE_PREREQUISITES_DRIFT", text)
        self.assertIn("TASK40_RECEIPT_REWRITE", text)
        self.assertIn("H11_EFFECT_SCREEN_RERUN", text)
        self.assertIn("MORE_CREATES_OPTION_C", text)
        self.assertIn("COMPLETE_EVENT_AS_MIGRATION_AT", text)
        self.assertEqual(ATOM_ID, "RC002-H11-TASK40-CLOSE-CREATE-AT-GAP-MIGRATION-AT-BOUND-V1")
        self.assertEqual(CREATE_AT_STATUS, "MISSING_UNKNOWN")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND",
                "TASK40_CLOSE_PREREQUISITES_DRIFT",
            ),
        )
        write_set = text.split("managed_write_set:")[1].split("external_caps:")[0]
        self.assertNotIn("pump_event_decoder.py", write_set)
        self.assertNotIn("a1_h11_bonding_curve_pda_gta_acceptance_v1.json", write_set)
        self.assertNotIn("global_trial_ledger.yaml", write_set)
        self.assertTrue(PINNED_DECODER.is_file())

    def test_git_prerequisites_bind_successor_close(self) -> None:
        result = bind_task40_close_create_at_gap_migration_at_bound(ROOT)
        self.assertEqual(result["terminal"], "TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND")
        self.assertEqual(result["named_mint"], EXPECTED_NAMED_MINT)
        self.assertEqual(result["bonding_curve"], EXPECTED_BONDING_CURVE)
        self.assertEqual(result["task40_capture_terminal"], TASK40_CAPTURE_TERMINAL)
        self.assertEqual(result["task40_trial_outcome"], TASK40_TRIAL_OUTCOME)
        self.assertEqual(result["create_at_terminal"], "CREATE_AT_MISSING_UNKNOWN")
        self.assertIsNone(result["create_at"])
        self.assertEqual(result["create_at_status"], "MISSING_UNKNOWN")
        self.assertEqual(result["migration_terminal"], "COMPLETE_MIGRATION_IDENTITY_MATCH")
        self.assertEqual(result["migration_at"], 1756321522)
        self.assertEqual(result["migration_at_status"], "BOUND_FROM_EVENT_TIMESTAMP")
        self.assertEqual(result["complete_event_timestamp"], 1756321521)
        self.assertEqual(result["complete_event_status"], "MIGRATION_STARTED")
        self.assertNotEqual(result["complete_event_timestamp"], result["migration_at"])
        self.assertEqual(
            result["destination_pool"],
            "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
        )
        self.assertNotIn("blockTime", result)
        self.assertEqual(result["task40_acceptance_sha256"], EXPECTED_TASK40_ACCEPTANCE_SHA256)
        self.assertEqual(result["create_at_receipt_sha256"], EXPECTED_CREATE_AT_RECEIPT_SHA256)
        self.assertEqual(result["migration_receipt_sha256"], EXPECTED_MIGRATION_RECEIPT_SHA256)

    def test_module_does_not_decode_or_read_blocktime(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("decode_pump_program_data", source)
        self.assertNotIn("blockTime", source)
        self.assertNotIn("bind_complete_migration", source)
        fixture = json.loads((ROOT / GETTX_FIXTURE_RELATIVE).read_text(encoding="utf-8"))
        self.assertIn("blockTime", fixture["result"])
        bound = bind_task40_close_create_at_gap_migration_at_bound(ROOT)
        self.assertNotEqual(bound["create_at"], fixture["result"]["blockTime"])
        self.assertNotEqual(bound["migration_at"], fixture["result"]["blockTime"])

    def test_task37_and_task40_science_are_not_rewritten(self) -> None:
        text = TASK37_POLICY.read_text(encoding="utf-8")
        self.assertIn("source_event: CreateEvent", text)
        self.assertIn("source_event: CompletePumpAmmMigrationEvent", text)
        module = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn(str(TASK37_POLICY.relative_to(ROOT)).replace("\\", "/"), module)
        self.assertNotIn("global_trial_ledger.yaml", module)
        ledger = TASK40_LEDGER.read_text(encoding="utf-8")
        self.assertIn("TRIAL-RC002-H11-BONDING-CURVE-PDA-GTA-001", ledger)
        self.assertIn("outcome: INCONCLUSIVE", ledger)

    def test_drifted_capture_terminal_is_not_closeable(self) -> None:
        bound = bind_task40_close_create_at_gap_migration_at_bound(ROOT)
        drifted = dict(bound)
        drifted["task40_capture_terminal"] = "CLOCKS_RECONSTRUCTED"
        self.assertEqual(
            decide_task40_close_terminal(drifted),
            "TASK40_CLOSE_PREREQUISITES_DRIFT",
        )
        drifted = dict(bound)
        drifted["create_at"] = 1750000000
        self.assertEqual(
            decide_task40_close_terminal(drifted),
            "TASK40_CLOSE_PREREQUISITES_DRIFT",
        )
        drifted = dict(bound)
        drifted["complete_event_timestamp"] = drifted["migration_at"]
        self.assertEqual(
            decide_task40_close_terminal(drifted),
            "TASK40_CLOSE_PREREQUISITES_DRIFT",
        )
        drifted = dict(bound)
        drifted["migration_at"] = None
        self.assertEqual(
            decide_task40_close_terminal(drifted),
            "TASK40_CLOSE_PREREQUISITES_DRIFT",
        )

    def test_acceptance_receipt_is_json_object(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        bound = bind_task40_close_create_at_gap_migration_at_bound(ROOT)
        self.assertEqual(receipt["atom_id"], ATOM_ID)
        self.assertEqual(receipt["terminal"], bound["terminal"])
        self.assertEqual(receipt["create_at_status"], bound["create_at_status"])
        self.assertIsNone(receipt["create_at"])
        self.assertEqual(receipt["migration_at"], bound["migration_at"])
        self.assertEqual(receipt["named_mint"], bound["named_mint"])
        self.assertEqual(receipt["bonding_curve"], bound["bonding_curve"])
        self.assertEqual(receipt["task40_capture_terminal"], bound["task40_capture_terminal"])
        self.assertEqual(receipt["task40_trial_outcome"], bound["task40_trial_outcome"])
        self.assertEqual(
            receipt["task40_acceptance_sha256"],
            bound["task40_acceptance_sha256"],
        )
        self.assertEqual(receipt["terminal"], "TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND")
        self.assertIn("NO_TASK40_RECEIPT_REWRITE", receipt["non_claims"])
        self.assertIn("NO_H11_EFFECT_SCREEN", receipt["non_claims"])
        self.assertFalse(receipt["live_PIT_claim"])
        task40 = json.loads((ROOT / TASK40_ACCEPTANCE_RELATIVE).read_text(encoding="utf-8"))
        create_at = json.loads((ROOT / CREATE_AT_RECEIPT_RELATIVE).read_text(encoding="utf-8"))
        migration = json.loads((ROOT / MIGRATION_RECEIPT_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(task40["terminal_decision"], "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT")
        self.assertEqual(create_at["terminal"], "CREATE_AT_MISSING_UNKNOWN")
        self.assertEqual(migration["terminal"], "COMPLETE_MIGRATION_IDENTITY_MATCH")
        self.assertEqual(migration["migration_at"], receipt["migration_at"])


if __name__ == "__main__":
    unittest.main()
