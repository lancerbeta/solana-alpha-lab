from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime, timedelta
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
AUDIT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17a"
    / "execution_capacity_quote_panel_audit_v1.json"
)


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
        original_raw_available = (
            RAW_ROOT
            / "task17a_execution_capacity_quote_panel_v1"
            / "window=T17A-WINDOW-01"
            / "raw_events.jsonl"
        ).is_file()
        if not original_raw_available:
            contract = load_repair_contract(CONTRACT_PATH)
            audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
            accepted_by_window = {
                window["window_id"]: window for window in audit["windows"]
            }
            for item in contract["accepted_input_windows"]:
                observed = accepted_by_window[item["window_id"]]
                for field in (
                    "raw_events_sha256",
                    "manifest_sha256",
                    "receipt_sha256",
                ):
                    self.assertEqual(observed[field], item[field])
            window3_trigger = datetime.fromisoformat(
                accepted_by_window["T17A-WINDOW-03"]["triggered_at"].replace(
                    "Z", "+00:00"
                )
            )
            earliest = window3_trigger + timedelta(seconds=1801)
            self.assertEqual(
                earliest.isoformat(timespec="microseconds").replace(
                    "+00:00", "Z"
                ),
                "2026-07-29T15:46:50.996379Z",
            )
            self.assertEqual(contract["caps"]["provider_calls_max"], 8)
            self.assertFalse(contract["authority"]["network"])
            self.assertEqual(contract["authority"]["raw_live_write"], False)
            return
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
