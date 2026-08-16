from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (  # noqa: E402
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
)
from solana_alpha_lab.rc002_h11_park_from_priority import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    COHORT_ACCEPTANCE_RELATIVE,
    EXPECTED_COHORT_ACCEPTANCE_SHA256,
    FORBIDDEN_FOLLOW_ONS,
    RETURN_TRIGGER,
    TERMINAL_OUTCOMES,
    bind_h11_park_from_priority,
    format_owner_readout,
)

CONTRACT_PATH = ROOT / "docs/tasks/RC002-H11-PARK-FROM-PRIORITY-OFFLINE-V1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/rc002_h11_park_from_priority.py"
ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/rc002_h11_park_from_priority/"
    "a1_h11_park_from_priority_acceptance_v1.json"
)
READOUT_PATH = ROOT / (
    "docs/reports/rc002_h11_park_from_priority/a1_owner_readout_v1.md"
)
REGISTRY_PATH = ROOT / "registries/decisions_negative_results.yaml"
PINNED_DECODER = ROOT / "src/solana_alpha_lab/pump_event_decoder.py"
TRIAL_LEDGER = ROOT / "registries/global_trial_ledger.yaml"
TASK36_YAML = ROOT / "configs/task36_rc002_h11_lifecycle_clock_screen_v1.yaml"
TASK37_YAML = ROOT / "configs/task37_rc002_h11_migration_clock_capture_v1.yaml"


class H11ParkFromPriorityTests(unittest.TestCase):
    def test_contract_names_park_caps_and_return_stops(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: RC002-H11-PARK-FROM-PRIORITY-OFFLINE-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED", text)
        self.assertIn("H11_PARK_PREREQUISITES_DRIFT", text)
        self.assertIn("OWNER_CAPTURE_PHRASE=H11 паркуем", text)
        self.assertIn("H11_EFFECT_SCREEN_RERUN", text)
        self.assertIn("PAID_CAPTURE_ON_FALSIFIED_ROUTES", text)
        self.assertIn("H13_OR_H02_TRIAL_STARTED", text)
        self.assertIn("HYPOTHESIS_NEGATIVE_OR_POSITIVE_INFERENCE", text)
        self.assertIn("TRIAL_LEDGER_REWRITE", text)
        self.assertEqual(ATOM_ID, "RC002-H11-PARK-FROM-PRIORITY-OFFLINE-V1")
        self.assertEqual(AUTHORITY_PHRASE, "H11 паркуем")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
                "H11_PARK_PREREQUISITES_DRIFT",
            ),
        )
        write_set = text.split("managed_write_set:")[1].split("external_caps:")[0]
        self.assertNotIn("pump_event_decoder.py", write_set)
        self.assertNotIn("task36_rc002_h11_lifecycle_clock_screen_v1.yaml", write_set)
        self.assertNotIn("task37_rc002_h11_migration_clock_capture_v1.yaml", write_set)
        self.assertNotIn("global_trial_ledger.yaml", write_set)
        self.assertTrue(PINNED_DECODER.is_file())
        self.assertTrue(TASK36_YAML.is_file())
        self.assertTrue(TASK37_YAML.is_file())
        self.assertTrue(TRIAL_LEDGER.is_file())

    def test_module_does_not_name_transaction_wall_clock_field(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("blockTime", source)
        self.assertIn("bind_cohort_eligibility_after_task40_close", source)
        self.assertNotIn("load_live_pages", source)

    def test_git_prerequisites_bind_park_from_priority(self) -> None:
        result = bind_h11_park_from_priority(ROOT)
        self.assertEqual(result["terminal"], "H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED")
        self.assertEqual(result["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(result["priority_disposition"], "PARKED_FROM_PRIORITY")
        self.assertEqual(result["science_disposition"], "RETAINED")
        self.assertFalse(result["deletion"])
        self.assertEqual(
            result["hypothesis_verdict"], "NOT_REFUTED_NOT_SUPPORTED"
        )
        self.assertEqual(
            result["family_status"], "PARKED_FROM_PRIORITY_NOT_CANONICAL_DONE"
        )
        self.assertEqual(result["named_mint"], EXPECTED_NAMED_MINT)
        self.assertEqual(result["bonding_curve"], EXPECTED_BONDING_CURVE)
        self.assertEqual(
            result["cohort_terminal"], "H11_COHORT_NOT_READY_SCREEN_FORBIDDEN"
        )
        self.assertEqual(result["task36_terminal"], "HISTORICAL_ROUTE_INADEQUATE_REPLAN")
        self.assertEqual(result["task36_n"], 0)
        self.assertEqual(
            result["task37_capture_terminal"],
            "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT",
        )
        self.assertFalse(result["effect_screen_eligible"])
        self.assertEqual(
            result["cohort_acceptance_sha256"], EXPECTED_COHORT_ACCEPTANCE_SHA256
        )
        self.assertEqual(result["return_trigger"], RETURN_TRIGGER)
        self.assertEqual(result["forbidden_follow_ons"], list(FORBIDDEN_FOLLOW_ONS))
        self.assertFalse(result["calendar_elapsed_is_return_trigger"])
        self.assertFalse(result["h13_or_h02_started"])
        self.assertFalse(result["paid_capture_authorized"])

    def test_acceptance_and_readout_match_binder(self) -> None:
        result = bind_h11_park_from_priority(ROOT)
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["terminal"], result["terminal"])
        self.assertEqual(acceptance["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(
            acceptance["hypothesis_verdict"], "NOT_REFUTED_NOT_SUPPORTED"
        )
        self.assertEqual(acceptance["return_trigger"], RETURN_TRIGGER)
        self.assertEqual(acceptance["forbidden_follow_ons"], list(FORBIDDEN_FOLLOW_ONS))
        self.assertFalse(acceptance["calendar_elapsed_is_return_trigger"])
        self.assertEqual(
            acceptance["cohort_acceptance"], COHORT_ACCEPTANCE_RELATIVE
        )
        readout = READOUT_PATH.read_text(encoding="utf-8")
        self.assertEqual(readout, format_owner_readout(result))
        self.assertIn("H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED", readout)
        self.assertIn("H11 паркуем", readout)
        self.assertIn("не опровержение гипотезы", readout)
        self.assertIn("не canonical DONE", readout)
        self.assertIn("Календарь сам по себе не триггер", readout)
        self.assertIn("H11_COHORT_NOT_READY_SCREEN_FORBIDDEN", readout)
        self.assertIn("BLOCKED_DATA", readout)

    def test_lifecycle_registry_records_park_decision(self) -> None:
        text = REGISTRY_PATH.read_text(encoding="utf-8")
        self.assertIn("DECISION-RC002-H11-PARK-FROM-PRIORITY-001", text)
        self.assertIn("H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED", text)
        self.assertIn("H11 паркуем", text)
        self.assertIn("EVIDENCE-RC002-H11-PARK-FROM-PRIORITY-001", text)


if __name__ == "__main__":
    unittest.main()
