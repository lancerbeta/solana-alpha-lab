from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task17a_timing_repair import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    Task17ATimingRepairError,
    Task17ATimingRepairGate,
    load_repair_contract,
    repair_preflight,
)

CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "one_window_timing_repair_contract_v1.json"
)
RAW_ROOT = (ROOT / "data" / "raw").resolve()


class Task17ATimingRepairContractTests(unittest.TestCase):
    def test_contract_is_one_window_only_and_requires_separate_gate(self) -> None:
        contract = load_repair_contract(CONTRACT_PATH)
        self.assertEqual(contract["caps"]["provider_calls_max"], 8)
        self.assertEqual(
            contract["accepted_window_set_after_repair"],
            [
                "T17A-WINDOW-01",
                "T17A-WINDOW-03",
                "T17A-WINDOW-04-REPAIR-01",
            ],
        )
        self.assertFalse(contract["defect"]["post_hoc_tolerance_allowed"])
        self.assertFalse(contract["authority"]["network"])
        self.assertEqual(contract["authority"]["provider_calls"], 0)
        with self.assertRaisesRegex(
            Task17ATimingRepairError,
            "repair_external_authority_phrase_mismatch",
        ):
            Task17ATimingRepairGate(authority_phrase="wrong")
        gate = Task17ATimingRepairGate(
            authority_phrase=EXTERNAL_AUTHORITY_PHRASE
        )
        self.assertEqual(gate.authority_phrase, EXTERNAL_AUTHORITY_PHRASE)

    def test_preflight_binds_immutable_inputs_and_exact_earliest_time(self) -> None:
        preflight = repair_preflight(
            raw_root=RAW_ROOT,
            contract_path=CONTRACT_PATH,
            now=lambda: datetime(2026, 7, 29, 15, 46, 51, tzinfo=UTC),
        )
        self.assertEqual(
            preflight["earliest_replacement_trigger_at"],
            "2026-07-29T15:46:50.996379Z",
        )
        self.assertTrue(preflight["ready_by_wall_clock"])
        self.assertTrue(preflight["repair_output_exists"])
        self.assertEqual(preflight["provider_calls_max"], 8)
        self.assertFalse(preflight["network_enabled"])
        self.assertEqual(preflight["raw_live_writes"], 0)


if __name__ == "__main__":
    unittest.main()
