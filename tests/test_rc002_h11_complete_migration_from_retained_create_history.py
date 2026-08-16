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
    PumpEventPlan,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.rc002_h11_complete_migration_from_retained_create_history import (  # noqa: E402
    ATOM_ID,
    CANDIDATE_ID,
    COMPLETE_EVENT,
    MIGRATION_EVENT,
    OLDER_IDL_RECEIPT_RELATIVE,
    TERMINAL_OUTCOMES,
    bind_complete_migration_from_retained_create_history,
    classify_rows_complete_migration,
    decide_complete_migration_terminal,
)
from solana_alpha_lab.rc002_h11_create_early_six_field_layout import (  # noqa: E402
    GETTX_FIXTURE_RELATIVE,
)
from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (  # noqa: E402
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
)
from solana_alpha_lab.rc002_h11_older_idl_clock_body import (  # noqa: E402
    candidate_drop_trailing_quote_mint,
)
from solana_alpha_lab.rc002_h11_truncation_vs_absence import IDL_RELATIVE  # noqa: E402

CONTRACT_PATH = ROOT / (
    "docs/tasks/RC002-H11-COMPLETE-MIGRATION-FROM-RETAINED-CREATE-HISTORY-OFFLINE-V1.md"
)
PINNED_DECODER = ROOT / "src/solana_alpha_lab/pump_event_decoder.py"
TASK37_POLICY = ROOT / "configs/task37_rc002_h11_migration_clock_capture_v1.yaml"
MODULE_PATH = ROOT / (
    "src/solana_alpha_lab/rc002_h11_complete_migration_from_retained_create_history.py"
)
IDL_PATH = ROOT / IDL_RELATIVE


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


def _b58_decode(text: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    for char in text:
        number = number * 58 + alphabet.index(char)
    return number.to_bytes(32, "big")


def _event_payload(
    plan: PumpEventPlan,
    event_name: str,
    *,
    mint: bytes,
    bonding_curve: bytes,
    timestamp: int,
) -> bytes:
    schema = next(event for event in plan.events if event.name == event_name)
    body = b""
    for index, field in enumerate(schema.fields):
        if field.name == "mint":
            value: object = mint
        elif field.name == "bonding_curve":
            value = bonding_curve
        elif field.name == "timestamp":
            value = timestamp
        elif field.type_spec == "pubkey":
            value = bytes([(index + 3) % 251]) * 32
        elif field.type_spec == "i64":
            value = timestamp
        elif field.type_spec == "u64":
            value = 10_000 + index
        else:
            raise AssertionError(f"unsupported_test_field:{field.name}")
        body += _encode_type(plan, field.type_spec, value)
    return schema.discriminator + body


def _pump_logs(payload: bytes) -> list[str]:
    encoded = base64.b64encode(payload).decode("ascii")
    return [
        f"Program {PUMP_PROGRAM_ID} invoke [1]",
        f"{PROGRAM_DATA_PREFIX}{encoded}",
        f"Program {PUMP_PROGRAM_ID} success",
    ]


def _row(logs: list[str]) -> dict[str, object]:
    return {
        "transaction": {"message": {"accountKeys": [PUMP_PROGRAM_ID]}},
        "meta": {"err": None, "logMessages": logs},
    }


class CompleteMigrationFromRetainedCreateHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pinned = load_pinned_pump_event_plan(IDL_PATH)
        self.candidate = candidate_drop_trailing_quote_mint(self.pinned)
        self.mint = _b58_decode(EXPECTED_NAMED_MINT)
        self.curve = _b58_decode(EXPECTED_BONDING_CURVE)

    def test_contract_names_offline_caps_and_clock_stops(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "task_id: RC002-H11-COMPLETE-MIGRATION-FROM-RETAINED-CREATE-HISTORY-OFFLINE-V1",
            text,
        )
        self.assertIn("network: false", text)
        self.assertIn("COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX", text)
        self.assertIn("COMPLETE_MIGRATION_IDENTITY_MATCH", text)
        self.assertIn("COMPLETE_MIGRATION_STARTED_NOT_MIGRATED", text)
        self.assertIn("MIGRATION_AT_FROM_BLOCKTIME", text)
        self.assertIn("COMPLETE_EVENT_AS_MIGRATION_AT", text)
        self.assertIn("DROP_TRAILING_QUOTE_MINT", text)
        self.assertEqual(
            ATOM_ID,
            "RC002-H11-COMPLETE-MIGRATION-FROM-RETAINED-CREATE-HISTORY-OFFLINE-V1",
        )
        self.assertEqual(CANDIDATE_ID, "DROP_TRAILING_QUOTE_MINT")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX",
                "COMPLETE_MIGRATION_IDENTITY_MATCH",
                "COMPLETE_MIGRATION_STARTED_NOT_MIGRATED",
                "COMPLETE_MIGRATION_IDENTITY_MISMATCH",
                "COMPLETE_MIGRATION_LAYOUT_FAIL",
                "COMPLETE_MIGRATION_PREREQUISITES_DRIFT",
            ),
        )
        self.assertTrue(PINNED_DECODER.is_file())
        write_set = text.split("managed_write_set:")[1].split("external_caps:")[0]
        self.assertNotIn("pump_event_decoder.py", write_set)

    def test_git_create_gettx_has_no_complete_or_migration(self) -> None:
        result = bind_complete_migration_from_retained_create_history(ROOT)
        fixture_scan = result["gettransaction_fixture"]
        self.assertEqual(
            fixture_scan["terminal"],
            "COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX",
        )
        self.assertEqual(fixture_scan["consumed_by_event"], {})
        self.assertIsNone(fixture_scan["migration_at"])
        self.assertEqual(fixture_scan["migration_at_status"], "NOT_IN_CREATE_GETTX")
        self.assertEqual(result["named_mint"], EXPECTED_NAMED_MINT)
        self.assertEqual(result["bonding_curve"], EXPECTED_BONDING_CURVE)
        self.assertEqual(result["create_at_terminal"], "CREATE_AT_MISSING_UNKNOWN")
        self.assertNotIn("blockTime", result)
        fixture = json.loads((ROOT / GETTX_FIXTURE_RELATIVE).read_text(encoding="utf-8"))
        self.assertIn("blockTime", fixture["result"])
        self.assertNotEqual(result.get("migration_at"), fixture["result"]["blockTime"])
        if result["retained_a4"]["pages_status"] != "SCANNED":
            self.assertEqual(
                result["terminal"],
                "COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX",
            )
            self.assertIsNone(result["migration_at"])

    def test_matching_bodies_bind_migration_at_not_complete_timestamp(self) -> None:
        complete = _event_payload(
            self.candidate,
            COMPLETE_EVENT,
            mint=self.mint,
            bonding_curve=self.curve,
            timestamp=1_721_000_111,
        )
        migration = _event_payload(
            self.candidate,
            MIGRATION_EVENT,
            mint=self.mint,
            bonding_curve=self.curve,
            timestamp=1_721_000_222,
        )
        classified = classify_rows_complete_migration(
            [_row(_pump_logs(complete)), _row(_pump_logs(migration))],
            pinned=self.pinned,
            candidate=self.candidate,
            named_mint=EXPECTED_NAMED_MINT,
            bonding_curve=EXPECTED_BONDING_CURVE,
        )
        self.assertEqual(classified["terminal"], "COMPLETE_MIGRATION_IDENTITY_MATCH")
        self.assertEqual(classified["migration_at"], 1_721_000_222)
        self.assertEqual(classified["complete_event_timestamp"], 1_721_000_111)
        self.assertEqual(classified["complete_event_status"], "MIGRATION_STARTED")
        self.assertNotEqual(
            classified["migration_at"],
            classified["complete_event_timestamp"],
        )
        self.assertIsInstance(classified["destination_pool"], str)

    def test_complete_only_is_started_not_migrated(self) -> None:
        complete = _event_payload(
            self.candidate,
            COMPLETE_EVENT,
            mint=self.mint,
            bonding_curve=self.curve,
            timestamp=1_721_000_111,
        )
        classified = classify_rows_complete_migration(
            [_row(_pump_logs(complete))],
            pinned=self.pinned,
            candidate=self.candidate,
            named_mint=EXPECTED_NAMED_MINT,
            bonding_curve=EXPECTED_BONDING_CURVE,
        )
        self.assertEqual(
            classified["terminal"],
            "COMPLETE_MIGRATION_STARTED_NOT_MIGRATED",
        )
        self.assertIsNone(classified["migration_at"])
        self.assertEqual(classified["complete_event_timestamp"], 1_721_000_111)
        self.assertEqual(classified["complete_event_status"], "MIGRATION_STARTED")

    def test_mismatched_mint_is_not_this_clock(self) -> None:
        other_mint = bytes([9]) * 32
        migration = _event_payload(
            self.candidate,
            MIGRATION_EVENT,
            mint=other_mint,
            bonding_curve=self.curve,
            timestamp=1_721_000_222,
        )
        classified = classify_rows_complete_migration(
            [_row(_pump_logs(migration))],
            pinned=self.pinned,
            candidate=self.candidate,
            named_mint=EXPECTED_NAMED_MINT,
            bonding_curve=EXPECTED_BONDING_CURVE,
        )
        self.assertEqual(classified["terminal"], "COMPLETE_MIGRATION_IDENTITY_MISMATCH")
        self.assertIsNone(classified["migration_at"])

    def test_pinned_layout_without_quote_mint_drop_is_layout_fail(self) -> None:
        body = _event_payload(
            self.candidate,
            MIGRATION_EVENT,
            mint=self.mint,
            bonding_curve=self.curve,
            timestamp=1_721_000_222,
        )
        classified = classify_rows_complete_migration(
            [_row(_pump_logs(body))],
            pinned=self.pinned,
            candidate=self.pinned,
            named_mint=EXPECTED_NAMED_MINT,
            bonding_curve=EXPECTED_BONDING_CURVE,
        )
        self.assertEqual(classified["terminal"], "COMPLETE_MIGRATION_LAYOUT_FAIL")
        self.assertIsNone(classified["migration_at"])

    def test_drifted_prereq_is_not_bindable(self) -> None:
        drifted = {
            "create_at_terminal": "CREATE_AT_PREREQUISITES_DRIFT",
            "older_idl_complete_consumed": 1,
            "older_idl_migration_consumed": 1,
            "fixture_terminal": "COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX",
        }
        self.assertEqual(
            decide_complete_migration_terminal(drifted),
            "COMPLETE_MIGRATION_PREREQUISITES_DRIFT",
        )

    def test_task37_migration_definition_is_not_rewritten(self) -> None:
        text = TASK37_POLICY.read_text(encoding="utf-8")
        self.assertIn("source_event: CompletePumpAmmMigrationEvent", text)
        self.assertIn("field: timestamp", text)
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn(str(TASK37_POLICY.relative_to(ROOT)).replace("\\", "/"), source)
        self.assertIn("decode_pump_program_data", source)

    def test_optional_a4_is_explicit_gap_or_identity(self) -> None:
        result = bind_complete_migration_from_retained_create_history(ROOT)
        if result["retained_a4"]["pages_status"] == "RETAINED_A4_PAGES_NOT_IN_CHECKOUT":
            self.assertIsNone(result["retained_a4"]["scan"])
            self.assertEqual(
                result["terminal"],
                "COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX",
            )
            return
        scan = result["retained_a4"]["scan"]
        assert scan is not None
        self.assertIn(scan["terminal"], TERMINAL_OUTCOMES)
        if scan["terminal"] == "COMPLETE_MIGRATION_IDENTITY_MATCH":
            self.assertEqual(result["terminal"], "COMPLETE_MIGRATION_IDENTITY_MATCH")
            self.assertIsInstance(result["migration_at"], int)
            self.assertNotEqual(
                result["migration_at"],
                result["complete_event_timestamp"],
            )

    def test_acceptance_receipt_matches_binder(self) -> None:
        path = ROOT / (
            "docs/evidence/rc002_h11_complete_migration_from_retained_create_history/"
            "a1_complete_migration_from_retained_create_history_acceptance_v1.json"
        )
        receipt = json.loads(path.read_text(encoding="utf-8"))
        bound = bind_complete_migration_from_retained_create_history(ROOT)
        older = json.loads((ROOT / OLDER_IDL_RECEIPT_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(receipt["atom_id"], ATOM_ID)
        self.assertEqual(
            receipt["gettransaction_fixture"]["terminal"],
            bound["gettransaction_fixture"]["terminal"],
        )
        self.assertEqual(
            receipt["gettransaction_fixture"]["terminal"],
            "COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX",
        )
        self.assertEqual(receipt["named_mint"], bound["named_mint"])
        self.assertEqual(receipt["bonding_curve"], bound["bonding_curve"])
        self.assertEqual(receipt["terminal"], "COMPLETE_MIGRATION_IDENTITY_MATCH")
        self.assertEqual(receipt["migration_at"], 1756321522)
        self.assertEqual(receipt["complete_event_timestamp"], 1756321521)
        self.assertEqual(receipt["complete_event_status"], "MIGRATION_STARTED")
        self.assertEqual(
            receipt["destination_pool"],
            "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
        )
        self.assertIsNone(receipt["create_at"])
        self.assertNotEqual(receipt["migration_at"], receipt["complete_event_timestamp"])
        self.assertEqual(
            older["retained_a4"]["consumed_by_event"]["CompleteEvent"],
            1,
        )
        self.assertEqual(
            older["retained_a4"]["consumed_by_event"]["CompletePumpAmmMigrationEvent"],
            1,
        )
        self.assertIn("NO_MIGRATION_AT_FROM_BLOCKTIME", receipt["non_claims"])
        self.assertIn("NO_COMPLETE_EVENT_AS_MIGRATION_AT", receipt["non_claims"])
        self.assertFalse(receipt["live_PIT_claim"])
        if bound["retained_a4"]["pages_status"] == "SCANNED":
            self.assertEqual(bound["terminal"], receipt["terminal"])
            self.assertEqual(bound["migration_at"], receipt["migration_at"])
            self.assertEqual(
                bound["complete_event_timestamp"],
                receipt["complete_event_timestamp"],
            )
            self.assertEqual(bound["destination_pool"], receipt["destination_pool"])
            self.assertIsNone(bound["create_at"])


if __name__ == "__main__":
    unittest.main()
