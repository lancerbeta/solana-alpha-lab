from __future__ import annotations

import base64
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pump_event_decoder import (  # noqa: E402
    PROGRAM_DATA_PREFIX,
    PUMP_PROGRAM_ID,
    FieldSpec,
    PumpEventPlan,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.rc002_h11_truncation_vs_absence import (  # noqa: E402
    ATOM_ID,
    CLOCK_EVENTS,
    RETAINED_A4_RELATIVE,
    TERMINAL_OUTCOMES,
    classify_rows,
    decide_terminal,
    scan_retained_a4_pages,
)

IDL_PATH = ROOT / "tests/fixtures/task08/pump_event_idl_subset_v1.json"
CONTRACT_PATH = ROOT / "docs/tasks/RC002-H11-TRUNCATION-VS-ABSENCE-OFFLINE-V1.md"


def _encode_type(plan: PumpEventPlan, type_spec: object, value: object) -> bytes:
    if type_spec == "bool":
        return bytes([int(bool(value))])
    if type_spec == "i64":
        return struct.pack("<q", int(value))
    if type_spec == "pubkey":
        if not isinstance(value, bytes) or len(value) != 32:
            raise AssertionError("test_pubkey_must_be_32_bytes")
        return value
    if type_spec == "string":
        encoded = str(value).encode("utf-8")
        return struct.pack("<I", len(encoded)) + encoded
    if type_spec == "u16":
        return struct.pack("<H", int(value))
    if type_spec == "u64":
        return struct.pack("<Q", int(value))
    if type_spec == ("vec_defined", "Shareholder"):
        return struct.pack("<I", 0)
    raise AssertionError(f"unsupported_test_type:{type_spec!r}")


def _default_value(field: FieldSpec, seed: int) -> object:
    if field.type_spec == "bool":
        return False
    if field.type_spec == "i64":
        return 1_721_888_000 + seed
    if field.type_spec == "pubkey":
        return bytes([(seed + 1) % 251]) * 32
    if field.type_spec == "string":
        return f"synthetic-{field.name}"
    if field.type_spec == "u16":
        return seed
    if field.type_spec == "u64":
        return 10_000 + seed
    if field.type_spec == ("vec_defined", "Shareholder"):
        return []
    raise AssertionError(f"unsupported_test_type:{field.type_spec!r}")


def _event_payload(plan: PumpEventPlan, event_name: str) -> bytes:
    schema = next(event for event in plan.events if event.name == event_name)
    values = {field.name: _default_value(field, index) for index, field in enumerate(schema.fields)}
    return schema.discriminator + b"".join(
        _encode_type(plan, field.type_spec, values[field.name]) for field in schema.fields
    )


def _program_data_line(payload: bytes) -> str:
    return PROGRAM_DATA_PREFIX + base64.b64encode(payload).decode("ascii")


def _pump_logs(*payloads: bytes) -> list[str]:
    logs = [f"Program {PUMP_PROGRAM_ID} invoke [1]"]
    logs.extend(_program_data_line(payload) for payload in payloads)
    logs.append(f"Program {PUMP_PROGRAM_ID} success")
    return logs


def _tx_row(*, logs: list[str], sig: str, index: int = 0) -> dict[str, object]:
    return {
        "slot": 438709109 + index,
        "transactionIndex": index,
        "blockTime": 1786494563 + index,
        "transaction": {
            "signatures": [sig],
            "message": {"accountKeys": [PUMP_PROGRAM_ID, "11111111111111111111111111111111"]},
        },
        "meta": {"err": None, "logMessages": logs},
    }


class TruncationVsAbsenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_pinned_pump_event_plan(IDL_PATH)

    def test_contract_names_the_owner_atom_and_offline_caps(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: RC002-H11-TRUNCATION-VS-ABSENCE-OFFLINE-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("HISTORICAL_RECEIPT_REWRITE", text)
        self.assertIn("CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT", text)

    def test_truncated_create_is_hidden_clock_not_wrong_address(self) -> None:
        create = next(event for event in self.plan.events if event.name == "CreateEvent")
        payload = create.discriminator + b"\x01\x00\x00\x00"
        scan = classify_rows(
            [_tx_row(logs=_pump_logs(payload), sig="sig-create-trunc")],
            plan=self.plan,
        )
        self.assertEqual(scan["truncated_by_event"]["CreateEvent"], 1)
        self.assertEqual(scan["decoded_by_event"].get("CreateEvent", 0), 0)
        self.assertEqual(scan["terminal"], "CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT")

    def test_truncated_trade_only_does_not_hide_clocks(self) -> None:
        trade = next(event for event in self.plan.events if event.name == "TradeEvent")
        payload = trade.discriminator + b"\x00" * 8
        scan = classify_rows(
            [_tx_row(logs=_pump_logs(payload), sig="sig-trade-trunc")],
            plan=self.plan,
        )
        self.assertEqual(scan["truncated_by_event"]["TradeEvent"], 1)
        self.assertEqual(sum(scan["truncated_by_event"].get(name, 0) for name in CLOCK_EVENTS), 0)
        self.assertEqual(scan["terminal"], "CLOCK_EVENTS_ABSENT_TRUNCATION_IS_NON_CLOCK")

    def test_create_after_truncated_trade_is_visible_to_this_scan(self) -> None:
        trade = next(event for event in self.plan.events if event.name == "TradeEvent")
        truncated_trade = trade.discriminator + b"\x00" * 8
        full_create = _event_payload(self.plan, "CreateEvent")
        scan = classify_rows(
            [
                _tx_row(
                    logs=_pump_logs(truncated_trade, full_create),
                    sig="sig-trade-then-create",
                )
            ],
            plan=self.plan,
        )
        self.assertEqual(scan["truncated_by_event"]["TradeEvent"], 1)
        self.assertEqual(scan["decoded_by_event"]["CreateEvent"], 1)
        self.assertEqual(
            scan["terminal"],
            "CLOCK_EVENTS_PRESENT_AFTER_NON_CLOCK_TRUNCATION",
        )

    def test_unknown_discriminator_without_truncate_is_absent(self) -> None:
        payload = bytes([1, 2, 3, 4, 5, 6, 7, 8]) + b"\x00" * 16
        scan = classify_rows(
            [_tx_row(logs=_pump_logs(payload), sig="sig-unknown")],
            plan=self.plan,
        )
        self.assertEqual(scan["unknown_discriminator"], 1)
        self.assertEqual(scan["terminal"], "CLOCK_EVENTS_ABSENT_NO_CLOCK_DISCRIMINATOR")

    def test_decoded_create_is_clocks_present(self) -> None:
        scan = classify_rows(
            [
                _tx_row(
                    logs=_pump_logs(_event_payload(self.plan, "CreateEvent")),
                    sig="sig-create",
                )
            ],
            plan=self.plan,
        )
        self.assertEqual(scan["decoded_by_event"]["CreateEvent"], 1)
        self.assertEqual(scan["terminal"], "CLOCK_EVENTS_DECODED")

    def test_decide_terminal_priority_and_closed_enum(self) -> None:
        self.assertEqual(
            set(TERMINAL_OUTCOMES),
            {
                "CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT",
                "CLOCK_EVENTS_PRESENT_AFTER_NON_CLOCK_TRUNCATION",
                "CLOCK_EVENTS_ABSENT_TRUNCATION_IS_NON_CLOCK",
                "CLOCK_EVENTS_ABSENT_NO_CLOCK_DISCRIMINATOR",
                "CLOCK_EVENTS_DECODED",
            },
        )
        self.assertEqual(
            decide_terminal(
                {
                    "undecodable_clock": 1,
                    "decoded_clock": 1,
                    "truncated_non_clock": 1,
                    "decoded_non_clock": 0,
                    "clock_after_non_clock_truncation": 1,
                }
            ),
            "CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT",
        )

    def test_clock_discriminator_with_non_truncate_decode_error_is_hidden(self) -> None:
        create = next(event for event in self.plan.events if event.name == "CreateEvent")
        payload = create.discriminator + struct.pack("<I", 5000)
        scan = classify_rows(
            [_tx_row(logs=_pump_logs(payload), sig="sig-create-too-large")],
            plan=self.plan,
        )
        self.assertEqual(
            scan["other_decode_by_event"]["CreateEvent:borsh_string_too_large"],
            1,
        )
        self.assertEqual(scan["terminal"], "CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT")

    def test_decoded_trade_without_truncate_is_absent_no_clock_discriminator(self) -> None:
        scan = classify_rows(
            [
                _tx_row(
                    logs=_pump_logs(_event_payload(self.plan, "TradeEvent")),
                    sig="sig-trade-full",
                )
            ],
            plan=self.plan,
        )
        self.assertEqual(scan["decoded_by_event"]["TradeEvent"], 1)
        self.assertEqual(scan["truncated_non_clock"], 0)
        self.assertEqual(scan["terminal"], "CLOCK_EVENTS_ABSENT_NO_CLOCK_DISCRIMINATOR")

    def test_stack_error_drops_later_clock_in_same_transaction(self) -> None:
        full_create = _event_payload(self.plan, "CreateEvent")
        logs = [
            f"Program {PUMP_PROGRAM_ID} invoke [2]",
            _program_data_line(full_create),
            f"Program {PUMP_PROGRAM_ID} success",
        ]
        scan = classify_rows(
            [_tx_row(logs=logs, sig="sig-bad-depth")],
            plan=self.plan,
        )
        self.assertEqual(scan["decoded_by_event"].get("CreateEvent", 0), 0)
        self.assertEqual(scan["attribution_errors"]["program_invoke_depth_invalid"], 1)
        self.assertEqual(scan["terminal"], "CLOCK_EVENTS_ABSENT_NO_CLOCK_DISCRIMINATOR")

    def test_retained_a4_absent_is_explicit_gap(self) -> None:
        result = scan_retained_a4_pages(ROOT, plan=self.plan)
        self.assertEqual(result["raw_root"], RETAINED_A4_RELATIVE)
        self.assertEqual(ATOM_ID, "RC002-H11-TRUNCATION-VS-ABSENCE-OFFLINE-V1")
        if not (ROOT / RETAINED_A4_RELATIVE).exists():
            self.assertEqual(result["pages_status"], "RETAINED_A4_PAGES_NOT_IN_CHECKOUT")
            self.assertIsNone(result["scan"])
        else:
            self.assertEqual(result["pages_status"], "SCANNED")
            self.assertIn(result["scan"]["terminal"], TERMINAL_OUTCOMES)

    def test_acceptance_receipt_is_json_object(self) -> None:
        path = ROOT / "docs/evidence/rc002_h11_truncation_vs_absence/a1_truncation_vs_absence_acceptance_v1.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["atom_id"], ATOM_ID)
        self.assertEqual(
            receipt["fixture_terminal_create_truncated"],
            "CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT",
        )
        self.assertEqual(
            receipt["fixture_terminal_trade_truncated"],
            "CLOCK_EVENTS_ABSENT_TRUNCATION_IS_NON_CLOCK",
        )
        self.assertEqual(
            receipt["retained_a4"]["terminal"],
            "CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT",
        )
        self.assertEqual(receipt["retained_a4"]["truncated_by_event"]["CreateEvent"], 1)
        self.assertEqual(
            receipt["retained_a4"]["layout_claim"],
            "PINNED_DISCRIMINATOR_PRESENT_BODY_NOT_CONSUMED",
        )
        self.assertEqual(
            receipt["retained_a4"]["clock_undecodable_payload_bytes"],
            [195, 112, 168],
        )
        self.assertEqual(receipt["retained_a4"]["other_decode_by_event"], {})
        self.assertEqual(len(receipt["retained_a4"]["pages"]), 3)
        self.assertEqual(
            receipt["retained_a4"]["pages"][0]["response_bytes"],
            6478360,
        )
        self.assertIn("NO_EXCLUSIVE_XB_RPC_CUT_CLAIM", receipt["non_claims"])
        self.assertFalse(receipt["live_PIT_claim"])
        self.assertFalse(receipt["execution_claim"])


if __name__ == "__main__":
    unittest.main()
