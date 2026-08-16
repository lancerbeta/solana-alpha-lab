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
from solana_alpha_lab.rc002_h11_create_early_six_field_layout import (  # noqa: E402
    ATOM_ID,
    CANDIDATE_ID,
    CREATE_EVENT,
    CREATE_KEEP_FIELDS,
    GETTX_FIXTURE_RELATIVE,
    TERMINAL_OUTCOMES,
    TIMESTAMP_INVARIANT_CODE,
    candidate_drop_create_fields_after_user,
    classify_create_bodies,
    classify_gettransaction_fixture,
    decide_create_terminal,
    scan_retained_a4_create_early_six_field_layout,
)
from solana_alpha_lab.rc002_h11_older_idl_clock_body import (  # noqa: E402
    candidate_drop_trailing_quote_mint,
    classify_clock_bodies,
)

IDL_PATH = ROOT / "tests/fixtures/task08/pump_event_idl_subset_v1.json"
CONTRACT_PATH = ROOT / "docs/tasks/RC002-H11-CREATE-EARLY-SIX-FIELD-LAYOUT-OFFLINE-V1.md"
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


class CreateEarlySixFieldLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pinned = load_pinned_pump_event_plan(IDL_PATH)
        cls.candidate = candidate_drop_create_fields_after_user(cls.pinned)
        cls.quote_mint_only = candidate_drop_trailing_quote_mint(cls.pinned)

    def test_contract_names_the_owner_atom_and_offline_caps(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: RC002-H11-CREATE-EARLY-SIX-FIELD-LAYOUT-OFFLINE-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("DROP_CREATE_FIELDS_AFTER_USER", text)
        self.assertIn("PINNED_PUMP_DECODER_MUTATION", text)
        self.assertIn("CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT", text)
        self.assertIn("CREATE_EARLY_LAYOUT_STILL_TRUNCATED", text)
        self.assertIn("decoded_event_missing_timestamp", text)
        self.assertEqual(ATOM_ID, "RC002-H11-CREATE-EARLY-SIX-FIELD-LAYOUT-OFFLINE-V1")
        self.assertEqual(CANDIDATE_ID, "DROP_CREATE_FIELDS_AFTER_USER")
        self.assertEqual(
            CREATE_KEEP_FIELDS,
            ("name", "symbol", "uri", "mint", "bonding_curve", "user"),
        )

    def test_candidate_keeps_six_create_fields_only(self) -> None:
        pinned_create = next(
            event.fields for event in self.pinned.events if event.name == CREATE_EVENT
        )
        candidate_create = next(
            event.fields for event in self.candidate.events if event.name == CREATE_EVENT
        )
        self.assertEqual(
            [field.name for field in candidate_create],
            list(CREATE_KEEP_FIELDS),
        )
        self.assertEqual(
            [field.name for field in pinned_create[:6]],
            list(CREATE_KEEP_FIELDS),
        )
        self.assertGreater(len(pinned_create), 6)
        for name in ("CompleteEvent", "CompletePumpAmmMigrationEvent", "TradeEvent"):
            pinned_fields = next(
                event.fields for event in self.pinned.events if event.name == name
            )
            candidate_fields = next(
                event.fields for event in self.candidate.events if event.name == name
            )
            self.assertEqual(
                [field.name for field in pinned_fields],
                [field.name for field in candidate_fields],
            )
        self.assertTrue(PINNED_DECODER.is_file())

    def test_synthetic_six_field_create_hits_timestamp_invariant(self) -> None:
        payload = _event_payload(self.candidate, CREATE_EVENT)
        with self.assertRaises(PumpEventDecodeError) as raised:
            decode_pump_program_data(
                self.candidate,
                log_line=_program_data_line(payload),
                emitting_program_id=PUMP_PROGRAM_ID,
                transaction_succeeded=True,
            )
        self.assertEqual(str(raised.exception), TIMESTAMP_INVARIANT_CODE)

    def test_pinned_create_fails_on_candidate_plan(self) -> None:
        payload = _event_payload(self.pinned, CREATE_EVENT)
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

    def test_create_six_field_is_timestamp_invariant_terminal(self) -> None:
        rows = [
            _tx_row(
                logs=_pump_logs(_event_payload(self.candidate, CREATE_EVENT)),
                sig="sig-create",
            )
        ]
        result = classify_create_bodies(
            rows, pinned=self.pinned, candidate=self.candidate
        )
        self.assertEqual(result["consumed_by_event"], {})
        self.assertEqual(result["failed_by_event"][CREATE_EVENT], 1)
        self.assertEqual(
            result["fail_codes_by_event"][CREATE_EVENT],
            {TIMESTAMP_INVARIANT_CODE: 1},
        )
        self.assertEqual(
            decide_create_terminal(result),
            "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT",
        )

    def test_create_trailing_is_trailing_terminal(self) -> None:
        rows = [
            _tx_row(
                logs=_pump_logs(_event_payload(self.pinned, CREATE_EVENT)),
                sig="sig-pinned-create",
            )
        ]
        result = classify_create_bodies(
            rows, pinned=self.pinned, candidate=self.candidate
        )
        self.assertEqual(result["failed_by_event"][CREATE_EVENT], 1)
        self.assertEqual(
            decide_create_terminal(result),
            "CREATE_EARLY_LAYOUT_TRAILING_BYTES",
        )
        self.assertEqual(
            result["fail_codes_by_event"][CREATE_EVENT],
            {"event_payload_trailing_bytes": 1},
        )

    def test_no_create_body_is_absent_terminal(self) -> None:
        rows = [
            _tx_row(
                logs=_pump_logs(_event_payload(self.quote_mint_only, "CompleteEvent")),
                sig="sig-complete-only",
            )
        ]
        result = classify_create_bodies(
            rows, pinned=self.pinned, candidate=self.candidate
        )
        self.assertEqual(decide_create_terminal(result), "CREATE_BODY_ABSENT")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT",
                "CREATE_EARLY_LAYOUT_CONSUMED_WITHOUT_REMAINDER",
                "CREATE_EARLY_LAYOUT_TRAILING_BYTES",
                "CREATE_EARLY_LAYOUT_STILL_TRUNCATED",
                "CREATE_EARLY_LAYOUT_DECODE_FAILED",
                "CREATE_BODY_ABSENT",
            ),
        )

    def test_complete_migration_still_consume_on_quote_mint_only(self) -> None:
        rows = [
            _tx_row(
                logs=_pump_logs(_event_payload(self.quote_mint_only, "CompleteEvent")),
                sig="sig-complete",
                index=0,
            ),
            _tx_row(
                logs=_pump_logs(
                    _event_payload(self.quote_mint_only, "CompletePumpAmmMigrationEvent")
                ),
                sig="sig-migration",
                index=1,
            ),
        ]
        result = classify_clock_bodies(
            rows, pinned=self.pinned, candidate=self.quote_mint_only
        )
        self.assertEqual(result["consumed_by_event"]["CompleteEvent"], 1)
        self.assertEqual(result["consumed_by_event"]["CompletePumpAmmMigrationEvent"], 1)
        self.assertEqual(result["failed_by_event"], {})

    def test_git_gettransaction_fixture_is_six_field_borsh_then_timestamp_invariant(self) -> None:
        self.assertTrue((ROOT / GETTX_FIXTURE_RELATIVE).is_file())
        result = classify_gettransaction_fixture(
            ROOT, pinned=self.pinned, candidate=self.candidate
        )
        self.assertEqual(result["payload_len_by_event"], {CREATE_EVENT: [195]})
        self.assertEqual(result["consumed_by_event"], {})
        self.assertEqual(result["failed_by_event"], {CREATE_EVENT: 1})
        self.assertEqual(
            result["fail_codes_by_event"][CREATE_EVENT],
            {TIMESTAMP_INVARIANT_CODE: 1},
        )
        self.assertEqual(
            result["terminal"],
            "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT",
        )

    def test_retained_a4_absent_or_borsh_then_timestamp_invariant(self) -> None:
        result = scan_retained_a4_create_early_six_field_layout(ROOT, pinned=self.pinned)
        self.assertEqual(
            result["gettransaction_fixture"]["terminal"],
            "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT",
        )
        if result["pages_status"] == "RETAINED_A4_PAGES_NOT_IN_CHECKOUT":
            self.assertIsNone(result["scan"])
            return
        self.assertEqual(result["pages_status"], "SCANNED")
        scan = result["scan"]
        assert scan is not None
        self.assertEqual(scan["payload_len_by_event"], {CREATE_EVENT: [195]})
        self.assertEqual(
            scan["terminal"],
            "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT",
        )
        self.assertEqual(scan["consumed_by_event"], {})
        self.assertEqual(scan["failed_by_event"], {CREATE_EVENT: 1})
        self.assertEqual(
            scan["fail_codes_by_event"][CREATE_EVENT],
            {TIMESTAMP_INVARIANT_CODE: 1},
        )
        regression = result["quote_mint_only_regression"]
        self.assertEqual(regression["consumed_by_event"].get("CompleteEvent"), 1)
        self.assertEqual(
            regression["consumed_by_event"].get("CompletePumpAmmMigrationEvent"),
            1,
        )

    def test_acceptance_receipt_is_json_object(self) -> None:
        path = ROOT / (
            "docs/evidence/rc002_h11_create_early_six_field_layout/"
            "a1_create_early_six_field_layout_acceptance_v1.json"
        )
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["atom_id"], ATOM_ID)
        self.assertEqual(receipt["candidate_id"], CANDIDATE_ID)
        self.assertEqual(
            receipt["gettransaction_fixture"]["terminal"],
            "CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT",
        )
        self.assertEqual(
            receipt["gettransaction_fixture"]["create_fail_code"],
            TIMESTAMP_INVARIANT_CODE,
        )
        self.assertIn("NO_EXCLUSIVE_XB_RPC_CUT_CLAIM", receipt["non_claims"])
        self.assertIn("NO_PINNED_DECODER_MUTATION", receipt["non_claims"])
        self.assertFalse(receipt["live_PIT_claim"])
        self.assertFalse(receipt["pinned_decoder_mutated"])


if __name__ == "__main__":
    unittest.main()
