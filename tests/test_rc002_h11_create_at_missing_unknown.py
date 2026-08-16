from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.rc002_h11_create_at_missing_unknown import (  # noqa: E402
    ATOM_ID,
    CREATE_AT_STATUS,
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
    IDENTITY_RECEIPT_RELATIVE,
    LAYOUT_RECEIPT_RELATIVE,
    TASK40_ACCEPTANCE_RELATIVE,
    TERMINAL_OUTCOMES,
    bind_create_at_missing_unknown,
    decide_create_at_terminal,
)
from solana_alpha_lab.rc002_h11_create_early_six_field_layout import (  # noqa: E402
    GETTX_FIXTURE_RELATIVE,
)

CONTRACT_PATH = ROOT / "docs/tasks/RC002-H11-CREATE-AT-MISSING-UNKNOWN-OFFLINE-V1.md"
PINNED_DECODER = ROOT / "src/solana_alpha_lab/pump_event_decoder.py"
TASK37_POLICY = ROOT / "configs/task37_rc002_h11_migration_clock_capture_v1.yaml"
MODULE_PATH = ROOT / "src/solana_alpha_lab/rc002_h11_create_at_missing_unknown.py"


class CreateAtMissingUnknownTests(unittest.TestCase):
    def test_contract_names_owner_a_and_offline_caps(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: RC002-H11-CREATE-AT-MISSING-UNKNOWN-OFFLINE-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("CREATE_AT_MISSING_UNKNOWN", text)
        self.assertIn("CREATE_AT_PREREQUISITES_DRIFT", text)
        self.assertIn("CREATE_AT_FROM_BLOCKTIME", text)
        self.assertIn("TASK37_CLOCK_DEFINITION_REWRITE", text)
        self.assertIn("MISSING_UNKNOWN", text)
        self.assertEqual(ATOM_ID, "RC002-H11-CREATE-AT-MISSING-UNKNOWN-OFFLINE-V1")
        self.assertEqual(CREATE_AT_STATUS, "MISSING_UNKNOWN")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            ("CREATE_AT_MISSING_UNKNOWN", "CREATE_AT_PREREQUISITES_DRIFT"),
        )
        self.assertTrue(PINNED_DECODER.is_file())
        self.assertNotIn("pump_event_decoder.py", text.split("managed_write_set:")[1].split("external_caps:")[0])

    def test_git_prerequisites_bind_missing_unknown(self) -> None:
        result = bind_create_at_missing_unknown(ROOT)
        self.assertEqual(result["terminal"], "CREATE_AT_MISSING_UNKNOWN")
        self.assertEqual(result["create_at_status"], "MISSING_UNKNOWN")
        self.assertIsNone(result["create_at"])
        self.assertEqual(result["named_mint"], EXPECTED_NAMED_MINT)
        self.assertEqual(result["bonding_curve"], EXPECTED_BONDING_CURVE)
        self.assertNotIn("blockTime", result)
        self.assertEqual(
            result["identity_terminal"],
            "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE",
        )
        self.assertEqual(
            result["layout_terminal"],
            "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT",
        )

    def test_module_does_not_decode_or_read_blocktime(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("decode_pump_program_data", source)
        self.assertNotIn("blockTime", source)
        fixture = json.loads((ROOT / GETTX_FIXTURE_RELATIVE).read_text(encoding="utf-8"))
        self.assertIn("blockTime", fixture["result"])
        bound = bind_create_at_missing_unknown(ROOT)
        self.assertNotEqual(bound["create_at"], fixture["result"]["blockTime"])

    def test_task37_create_at_definition_is_not_rewritten(self) -> None:
        text = TASK37_POLICY.read_text(encoding="utf-8")
        self.assertIn("source_event: CreateEvent", text)
        self.assertIn("field: timestamp", text)
        self.assertNotIn(str(TASK37_POLICY.relative_to(ROOT)).replace("\\", "/"), MODULE_PATH.read_text(encoding="utf-8"))

    def test_drifted_identity_is_not_bindable(self) -> None:
        drifted = {
            "named_mint": EXPECTED_NAMED_MINT,
            "bonding_curve": EXPECTED_BONDING_CURVE,
            "identity_terminal": "CREATE_PUBKEYS_MISMATCH",
            "layout_terminal": "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT",
        }
        self.assertEqual(decide_create_at_terminal(drifted), "CREATE_AT_PREREQUISITES_DRIFT")

    def test_acceptance_receipt_is_json_object(self) -> None:
        path = ROOT / (
            "docs/evidence/rc002_h11_create_at_missing_unknown/"
            "a1_create_at_missing_unknown_acceptance_v1.json"
        )
        receipt = json.loads(path.read_text(encoding="utf-8"))
        bound = bind_create_at_missing_unknown(ROOT)
        self.assertEqual(receipt["atom_id"], ATOM_ID)
        self.assertEqual(receipt["terminal"], bound["terminal"])
        self.assertEqual(receipt["create_at_status"], bound["create_at_status"])
        self.assertIsNone(receipt["create_at"])
        self.assertEqual(receipt["named_mint"], bound["named_mint"])
        self.assertEqual(receipt["bonding_curve"], bound["bonding_curve"])
        self.assertEqual(receipt["identity_terminal"], bound["identity_terminal"])
        self.assertEqual(receipt["layout_terminal"], bound["layout_terminal"])
        self.assertEqual(receipt["terminal"], "CREATE_AT_MISSING_UNKNOWN")
        self.assertIn("NO_CREATE_AT_FROM_BLOCKTIME", receipt["non_claims"])
        self.assertFalse(receipt["live_PIT_claim"])
        identity = json.loads((ROOT / IDENTITY_RECEIPT_RELATIVE).read_text(encoding="utf-8"))
        layout = json.loads((ROOT / LAYOUT_RECEIPT_RELATIVE).read_text(encoding="utf-8"))
        task40 = json.loads((ROOT / TASK40_ACCEPTANCE_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(identity["named_mint"], task40["named_mint"])
        self.assertEqual(
            layout["gettransaction_fixture"]["terminal"],
            "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT",
        )


if __name__ == "__main__":
    unittest.main()
