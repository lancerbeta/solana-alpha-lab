from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.rc002_h11_cohort_eligibility_after_task40_close import (  # noqa: E402
    ATOM_ID,
    CLOSE_ACCEPTANCE_RELATIVE,
    CREATE_AT_STATUS,
    EXPECTED_CLOSE_ACCEPTANCE_SHA256,
    EXPECTED_TASK36_RUNTIME_SHA256,
    EXPECTED_TASK37_ACCEPTANCE_SHA256,
    EXPECTED_TASK37_POLICY_SHA256,
    POLICY_RELATIVE,
    TASK36_RUNTIME_RELATIVE,
    TASK37_ACCEPTANCE_RELATIVE,
    TERMINAL_OUTCOMES,
    bind_cohort_eligibility_after_task40_close,
    decide_cohort_eligibility_terminal,
)
from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (  # noqa: E402
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
)

CONTRACT_PATH = ROOT / (
    "docs/tasks/RC002-H11-COHORT-ELIGIBILITY-AFTER-TASK40-CLOSE-OFFLINE-V1.md"
)
PINNED_DECODER = ROOT / "src/solana_alpha_lab/pump_event_decoder.py"
TASK37_POLICY = ROOT / POLICY_RELATIVE
MODULE_PATH = ROOT / (
    "src/solana_alpha_lab/rc002_h11_cohort_eligibility_after_task40_close.py"
)
ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/"
    "a1_cohort_eligibility_after_task40_close_acceptance_v1.json"
)


class CohortEligibilityAfterTask40CloseTests(unittest.TestCase):
    def test_contract_names_offline_caps_and_eligibility_stops(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "task_id: RC002-H11-COHORT-ELIGIBILITY-AFTER-TASK40-CLOSE-OFFLINE-V1",
            text,
        )
        self.assertIn("network: false", text)
        self.assertIn("H11_COHORT_NOT_READY_SCREEN_FORBIDDEN", text)
        self.assertIn("H11_COHORT_ELIGIBILITY_PREREQUISITES_DRIFT", text)
        self.assertIn("H11_EFFECT_SCREEN_RERUN", text)
        self.assertIn("COHORT_READY_INFERENCE_FROM_N1", text)
        self.assertIn("CLOCKS_RECONSTRUCTED_COHORT_READY", text)
        self.assertEqual(
            ATOM_ID, "RC002-H11-COHORT-ELIGIBILITY-AFTER-TASK40-CLOSE-OFFLINE-V1"
        )
        self.assertEqual(CREATE_AT_STATUS, "MISSING_UNKNOWN")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "H11_COHORT_NOT_READY_SCREEN_FORBIDDEN",
                "H11_COHORT_ELIGIBILITY_PREREQUISITES_DRIFT",
            ),
        )
        write_set = text.split("managed_write_set:")[1].split("external_caps:")[0]
        self.assertNotIn("pump_event_decoder.py", write_set)
        self.assertNotIn("task37_rc002_h11_migration_clock_capture_v1.yaml", write_set)
        self.assertNotIn("global_trial_ledger.yaml", write_set)
        self.assertTrue(PINNED_DECODER.is_file())

    def test_git_prerequisites_bind_cohort_not_ready(self) -> None:
        result = bind_cohort_eligibility_after_task40_close(ROOT)
        self.assertEqual(result["terminal"], "H11_COHORT_NOT_READY_SCREEN_FORBIDDEN")
        self.assertFalse(result["effect_screen_eligible"])
        self.assertEqual(result["named_mint"], EXPECTED_NAMED_MINT)
        self.assertEqual(result["bonding_curve"], EXPECTED_BONDING_CURVE)
        self.assertEqual(
            result["close_terminal"], "TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND"
        )
        self.assertIsNone(result["create_at"])
        self.assertEqual(result["create_at_status"], "MISSING_UNKNOWN")
        self.assertEqual(result["migration_at"], 1756321522)
        self.assertEqual(
            result["destination_pool"],
            "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
        )
        self.assertEqual(result["task36_terminal"], "HISTORICAL_ROUTE_INADEQUATE_REPLAN")
        self.assertEqual(result["task36_n"], 0)
        self.assertEqual(
            result["task37_capture_terminal"],
            "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT",
        )
        self.assertIs(result["h11_effect_screen_policy"], False)
        self.assertEqual(result["required_units"], {"pools": 8, "days": 2, "deployers": 2})
        self.assertEqual(
            result["reconstructed_units"],
            {"pools": 1, "days": 0, "deployers": 0},
        )
        self.assertNotIn("blockTime", result)
        self.assertEqual(result["close_acceptance_sha256"], EXPECTED_CLOSE_ACCEPTANCE_SHA256)
        self.assertEqual(result["task36_runtime_sha256"], EXPECTED_TASK36_RUNTIME_SHA256)
        self.assertEqual(
            result["task37_acceptance_sha256"], EXPECTED_TASK37_ACCEPTANCE_SHA256
        )
        self.assertEqual(result["task37_policy_sha256"], EXPECTED_TASK37_POLICY_SHA256)

    def test_module_does_not_decode_or_load_live_pages(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("decode_pump_program_data", source)
        self.assertNotIn("load_live_pages", source)
        self.assertNotIn("blockTime", source)
        self.assertIn("load_policy", source)
        self.assertIn("bind_task40_close_create_at_gap_migration_at_bound", source)

    def test_task37_policy_is_not_rewritten(self) -> None:
        text = TASK37_POLICY.read_text(encoding="utf-8")
        self.assertIn("h11_effect_screen: false", text)
        self.assertIn("pools: 8", text)
        write_set = CONTRACT_PATH.read_text(encoding="utf-8").split("managed_write_set:")[
            1
        ].split("external_caps:")[0]
        self.assertNotIn(POLICY_RELATIVE, write_set)

    def test_drifted_close_is_not_eligible(self) -> None:
        bound = bind_cohort_eligibility_after_task40_close(ROOT)
        drifted = dict(bound)
        drifted["close_terminal"] = "TASK40_CLOSE_PREREQUISITES_DRIFT"
        self.assertEqual(
            decide_cohort_eligibility_terminal(drifted),
            "H11_COHORT_ELIGIBILITY_PREREQUISITES_DRIFT",
        )
        drifted = dict(bound)
        drifted["reconstructed_units"] = {"pools": 8, "days": 2, "deployers": 2}
        self.assertEqual(
            decide_cohort_eligibility_terminal(drifted),
            "H11_COHORT_ELIGIBILITY_PREREQUISITES_DRIFT",
        )
        drifted = dict(bound)
        drifted["h11_effect_screen_policy"] = True
        self.assertEqual(
            decide_cohort_eligibility_terminal(drifted),
            "H11_COHORT_ELIGIBILITY_PREREQUISITES_DRIFT",
        )

    def test_acceptance_receipt_is_json_object(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        bound = bind_cohort_eligibility_after_task40_close(ROOT)
        self.assertEqual(receipt["atom_id"], ATOM_ID)
        self.assertEqual(receipt["terminal"], bound["terminal"])
        self.assertFalse(receipt["effect_screen_eligible"])
        self.assertEqual(receipt["named_mint"], bound["named_mint"])
        self.assertEqual(receipt["reconstructed_units"], bound["reconstructed_units"])
        self.assertEqual(receipt["required_units"], bound["required_units"])
        self.assertIsNone(receipt["create_at"])
        self.assertEqual(receipt["migration_at"], bound["migration_at"])
        self.assertEqual(
            receipt["terminal"], "H11_COHORT_NOT_READY_SCREEN_FORBIDDEN"
        )
        self.assertIn("NO_H11_EFFECT_SCREEN", receipt["non_claims"])
        self.assertIn("NO_COHORT_READY_FROM_N1", receipt["non_claims"])
        self.assertFalse(receipt["live_PIT_claim"])
        close = json.loads((ROOT / CLOSE_ACCEPTANCE_RELATIVE).read_text(encoding="utf-8"))
        task36 = json.loads((ROOT / TASK36_RUNTIME_RELATIVE).read_text(encoding="utf-8"))
        task37 = json.loads((ROOT / TASK37_ACCEPTANCE_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(
            close["terminal"], "TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND"
        )
        self.assertEqual(task36["cohort"]["n"], 0)
        self.assertEqual(
            task37["terminal_decision"], "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT"
        )


if __name__ == "__main__":
    unittest.main()
