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
    PumpEventDecodeError,
    PumpEventPlan,
    decode_pump_program_data,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.rc002_h11_older_idl_clock_body import (  # noqa: E402
    ATOM_ID,
    CANDIDATE_ID,
    CLOCK_EVENTS,
    TERMINAL_OUTCOMES,
    candidate_drop_trailing_quote_mint,
    classify_clock_bodies,
    decide_terminal,
    scan_retained_a4_clock_bodies,
)

IDL_PATH = ROOT / "tests/fixtures/task08/pump_event_idl_subset_v1.json"
CONTRACT_PATH = ROOT / "docs/tasks/RC002-H11-OLDER-IDL-CLOCK-BODY-OFFLINE-V1.md"
PINNED_DECODER = ROOT / "src/solana_alpha_lab/pump_event_decoder.py"


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
    values = {
        field.name: _default_value(field, index) for index, field in enumerate(schema.fields)
    }
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


class OlderIdlClockBodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pinned = load_pinned_pump_event_plan(IDL_PATH)
        cls.candidate = candidate_drop_trailing_quote_mint(cls.pinned)

    def test_contract_names_the_owner_atom_and_offline_caps(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: RC002-H11-OLDER-IDL-CLOCK-BODY-OFFLINE-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("DROP_TRAILING_QUOTE_MINT", text)
        self.assertIn("PINNED_PUMP_DECODER_MUTATION", text)
        self.assertIn("LAYOUT_CONSUMED_WITHOUT_REMAINDER", text)
        self.assertEqual(ATOM_ID, "RC002-H11-OLDER-IDL-CLOCK-BODY-OFFLINE-V1")
        self.assertEqual(CANDIDATE_ID, "DROP_TRAILING_QUOTE_MINT")

    def test_candidate_drops_quote_mint_only_on_clock_events(self) -> None:
        for name in CLOCK_EVENTS:
            pinned_fields = next(event.fields for event in self.pinned.events if event.name == name)
            candidate_fields = next(
                event.fields for event in self.candidate.events if event.name == name
            )
            self.assertIn("quote_mint", [field.name for field in pinned_fields])
            self.assertNotIn("quote_mint", [field.name for field in candidate_fields])
            self.assertEqual(
                [field.name for field in candidate_fields],
                [field.name for field in pinned_fields if field.name != "quote_mint"],
            )
        trade_pinned = next(event for event in self.pinned.events if event.name == "TradeEvent")
        trade_candidate = next(
            event for event in self.candidate.events if event.name == "TradeEvent"
        )
        self.assertEqual(
            [field.name for field in trade_pinned.fields],
            [field.name for field in trade_candidate.fields],
        )
        self.assertTrue(PINNED_DECODER.is_file())

    def test_complete_without_quote_mint_payload_is_112_bytes_and_consumes(self) -> None:
        payload = _event_payload(self.candidate, "CompleteEvent")
        self.assertEqual(len(payload), 112)
        decoded = decode_pump_program_data(
            self.candidate,
            log_line=_program_data_line(payload),
            emitting_program_id=PUMP_PROGRAM_ID,
            transaction_succeeded=True,
        )
        assert decoded is not None
        self.assertEqual(decoded.event_name, "CompleteEvent")
        self.assertNotIn("quote_mint", decoded.fields)

    def test_pinned_complete_fails_on_candidate_plan(self) -> None:
        payload = _event_payload(self.pinned, "CompleteEvent")
        with self.assertRaises(PumpEventDecodeError) as raised:
            decode_pump_program_data(
                self.candidate,
                log_line=_program_data_line(payload),
                emitting_program_id=PUMP_PROGRAM_ID,
                transaction_succeeded=True,
            )
        self.assertIn(
            str(raised.exception),
            {"event_payload_trailing_bytes", "borsh_payload_truncated"},
        )

    def test_migration_without_quote_mint_payload_is_168_bytes_and_consumes(self) -> None:
        payload = _event_payload(self.candidate, "CompletePumpAmmMigrationEvent")
        self.assertEqual(len(payload), 168)
        decoded = decode_pump_program_data(
            self.candidate,
            log_line=_program_data_line(payload),
            emitting_program_id=PUMP_PROGRAM_ID,
            transaction_succeeded=True,
        )
        assert decoded is not None
        self.assertEqual(decoded.event_name, "CompletePumpAmmMigrationEvent")

    def test_create_without_quote_mint_consumes_on_candidate(self) -> None:
        payload = _event_payload(self.candidate, "CreateEvent")
        decoded = decode_pump_program_data(
            self.candidate,
            log_line=_program_data_line(payload),
            emitting_program_id=PUMP_PROGRAM_ID,
            transaction_succeeded=True,
        )
        assert decoded is not None
        self.assertEqual(decoded.event_name, "CreateEvent")
        self.assertIn("virtual_quote_reserves", decoded.fields)

    def test_all_three_clock_bodies_consuming_is_remainder_terminal(self) -> None:
        rows = [
            _tx_row(
                logs=_pump_logs(_event_payload(self.candidate, name)),
                sig=f"sig-{name}",
                index=index,
            )
            for index, name in enumerate(
                ("CreateEvent", "CompleteEvent", "CompletePumpAmmMigrationEvent")
            )
        ]
        result = classify_clock_bodies(rows, pinned=self.pinned, candidate=self.candidate)
        self.assertEqual(result["consumed_by_event"]["CreateEvent"], 1)
        self.assertEqual(result["consumed_by_event"]["CompleteEvent"], 1)
        self.assertEqual(result["consumed_by_event"]["CompletePumpAmmMigrationEvent"], 1)
        self.assertEqual(result["failed_by_event"], {})
        self.assertEqual(decide_terminal(result), "LAYOUT_CONSUMED_WITHOUT_REMAINDER")

    def test_mixed_create_fail_is_not_uniform_consume(self) -> None:
        rows = [
            _tx_row(
                logs=_pump_logs(_event_payload(self.pinned, "CreateEvent")),
                sig="sig-create",
                index=0,
            ),
            _tx_row(
                logs=_pump_logs(_event_payload(self.candidate, "CompleteEvent")),
                sig="sig-complete",
                index=1,
            ),
        ]
        result = classify_clock_bodies(rows, pinned=self.pinned, candidate=self.candidate)
        self.assertEqual(decide_terminal(result), "MIXED_CLOCK_BODIES_NOT_UNIFORM")

    def test_no_clock_body_consuming_is_no_candidate(self) -> None:
        rows = [
            _tx_row(
                logs=_pump_logs(_event_payload(self.pinned, name)),
                sig=f"sig-{name}",
                index=index,
            )
            for index, name in enumerate(("CompleteEvent", "CompletePumpAmmMigrationEvent"))
        ]
        result = classify_clock_bodies(rows, pinned=self.pinned, candidate=self.candidate)
        self.assertEqual(decide_terminal(result), "NO_CANDIDATE_LAYOUT_CONSUMES")

    def test_complete_cpi_without_pump_in_account_keys_still_consumes(self) -> None:
        payload = _event_payload(self.candidate, "CompleteEvent")
        logs = [
            "Program 11111111111111111111111111111111 invoke [1]",
            f"Program {PUMP_PROGRAM_ID} invoke [2]",
            _program_data_line(payload),
            f"Program {PUMP_PROGRAM_ID} success",
            "Program 11111111111111111111111111111111 success",
        ]
        row = _tx_row(logs=logs, sig="sig-cpi-complete")
        row["transaction"]["message"]["accountKeys"] = [
            "11111111111111111111111111111111",
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        ]
        result = classify_clock_bodies(
            [row], pinned=self.pinned, candidate=self.candidate
        )
        self.assertEqual(result["consumed_by_event"].get("CompleteEvent"), 1)
        self.assertEqual(result["payload_len_by_event"]["CompleteEvent"], [112])
        self.assertEqual(decide_terminal(result), "MIXED_CLOCK_BODIES_NOT_UNIFORM")

    def test_incomplete_consume_set_is_mixed_not_remainder_terminal(self) -> None:
        rows = [
            _tx_row(
                logs=_pump_logs(_event_payload(self.candidate, "CompleteEvent")),
                sig="sig-only-complete",
            )
        ]
        result = classify_clock_bodies(rows, pinned=self.pinned, candidate=self.candidate)
        self.assertEqual(result["consumed_by_event"], {"CompleteEvent": 1})
        self.assertEqual(decide_terminal(result), "MIXED_CLOCK_BODIES_NOT_UNIFORM")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "LAYOUT_CONSUMED_WITHOUT_REMAINDER",
                "NO_CANDIDATE_LAYOUT_CONSUMES",
                "MIXED_CLOCK_BODIES_NOT_UNIFORM",
            ),
        )

    def test_retained_a4_absent_is_explicit_gap(self) -> None:
        result = scan_retained_a4_clock_bodies(ROOT, pinned=self.pinned)
        self.assertEqual(ATOM_ID, "RC002-H11-OLDER-IDL-CLOCK-BODY-OFFLINE-V1")
        if result["pages_status"] == "RETAINED_A4_PAGES_NOT_IN_CHECKOUT":
            self.assertIsNone(result["scan"])
            return
        self.assertEqual(result["pages_status"], "SCANNED")
        scan = result["scan"]
        assert scan is not None
        self.assertEqual(
            sorted(scan["payload_len_by_event"]),
            ["CompleteEvent", "CompletePumpAmmMigrationEvent", "CreateEvent"],
        )
        self.assertEqual(scan["payload_len_by_event"]["CreateEvent"], [195])
        self.assertEqual(scan["payload_len_by_event"]["CompleteEvent"], [112])
        self.assertEqual(
            scan["payload_len_by_event"]["CompletePumpAmmMigrationEvent"],
            [168],
        )
        self.assertEqual(scan["terminal"], "MIXED_CLOCK_BODIES_NOT_UNIFORM")
        self.assertEqual(scan["consumed_by_event"].get("CompleteEvent"), 1)
        self.assertEqual(scan["consumed_by_event"].get("CompletePumpAmmMigrationEvent"), 1)
        self.assertEqual(scan["failed_by_event"].get("CreateEvent"), 1)
        self.assertEqual(
            scan["fail_codes_by_event"]["CreateEvent"],
            {"borsh_payload_truncated": 1},
        )

    def test_acceptance_receipt_is_json_object(self) -> None:
        path = ROOT / (
            "docs/evidence/rc002_h11_older_idl_clock_body/"
            "a1_older_idl_clock_body_acceptance_v1.json"
        )
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["atom_id"], ATOM_ID)
        self.assertEqual(receipt["candidate_id"], CANDIDATE_ID)
        self.assertIn(receipt["fixture_terminal_all_consumed"], TERMINAL_OUTCOMES)
        self.assertEqual(receipt["retained_a4"]["terminal"], "MIXED_CLOCK_BODIES_NOT_UNIFORM")
        self.assertEqual(receipt["retained_a4"]["create_fail_code"], "borsh_payload_truncated")
        self.assertIn("NO_EXCLUSIVE_XB_RPC_CUT_CLAIM", receipt["non_claims"])


if __name__ == "__main__":
    unittest.main()
