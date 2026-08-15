from __future__ import annotations

import base64
import json
import struct
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

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
from solana_alpha_lab.task30_helius_get_transactions_for_address import (  # noqa: E402
    EXPECTED_POOL,
    build_json_rpc_payload,
)
from solana_alpha_lab.task39_h11_named_mint_gta_clock_capture import (  # noqa: E402
    ATOM_ID,
    NAMED_MINT,
    OWNER_PHRASE,
    POOL_ADDRESS,
    OutcomeGuard,
    build_mint_gta_payload,
    execute_capture,
    load_policy,
)

CONFIG_PATH = ROOT / "configs/task39_rc002_h11_named_mint_gta_clock_capture_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task39_rc002_h11_named_mint_gta_clock_capture.schema.json"
IDL_PATH = ROOT / "tests/fixtures/task08/pump_event_idl_subset_v1.json"
A22_CONFIG = ROOT / "configs/task30_a22_helius_get_transactions_for_address_one_shot_v1.yaml"


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


def _event_line(plan: PumpEventPlan, event_name: str, overrides: dict[str, object] | None = None) -> str:
    schema = next(event for event in plan.events if event.name == event_name)
    values = {field.name: _default_value(field, index) for index, field in enumerate(schema.fields)}
    if overrides:
        values.update(overrides)
    payload = schema.discriminator + b"".join(
        _encode_type(plan, field.type_spec, values[field.name]) for field in schema.fields
    )
    return PROGRAM_DATA_PREFIX + base64.b64encode(payload).decode("ascii")


def _pump_logs(plan: PumpEventPlan, event_name: str) -> list[str]:
    return [
        f"Program {PUMP_PROGRAM_ID} invoke [1]",
        _event_line(plan, event_name),
        f"Program {PUMP_PROGRAM_ID} success",
    ]


def _tx_row(*, logs: list[str], keys: list[str], sig: str, index: int = 0) -> dict[str, object]:
    return {
        "slot": 438709109 + index,
        "transactionIndex": index,
        "blockTime": 1786494563 + index,
        "transaction": {"signatures": [sig], "message": {"accountKeys": keys}},
        "meta": {"err": None, "logMessages": logs},
    }


class Task39NamedMintGtaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy(CONFIG_PATH)
        cls.plan = load_pinned_pump_event_plan(IDL_PATH)
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_policy_matches_schema_and_owner_phrase(self) -> None:
        jsonschema.Draft202012Validator(self.schema).validate(
            yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        )
        self.assertEqual(self.policy["atom_id"], ATOM_ID)
        self.assertEqual(self.policy["external_authority"]["owner_phrase"], OWNER_PHRASE)
        self.assertEqual(self.policy["adopted_route"]["mint_address"], NAMED_MINT)
        self.assertNotEqual(NAMED_MINT, PUMP_PROGRAM_ID)
        self.assertNotEqual(NAMED_MINT, POOL_ADDRESS)

    def test_payload_is_a22_shape_with_mint_and_without_day_window(self) -> None:
        a22_policy = yaml.safe_load(A22_CONFIG.read_text(encoding="utf-8"))
        a22 = build_json_rpc_payload(a22_policy)
        mint = build_mint_gta_payload(self.policy, page_number=0)
        self.assertEqual(mint["method"], a22["method"])
        self.assertEqual(mint["params"][0], NAMED_MINT)
        self.assertNotEqual(mint["params"][0], EXPECTED_POOL)
        self.assertNotEqual(mint["params"][0], PUMP_PROGRAM_ID)
        a22_options = a22["params"][1]
        mint_options = mint["params"][1]
        self.assertEqual(mint_options["transactionDetails"], a22_options["transactionDetails"])
        self.assertEqual(mint_options["sortOrder"], "asc")
        self.assertEqual(mint_options["limit"], 1000)
        self.assertNotIn("blockTime", mint_options["filters"])
        self.assertIn("blockTime", a22_options["filters"])
        self.assertNotIn("paginationToken", mint_options)

    def test_trial_before_outcome(self) -> None:
        guard = OutcomeGuard()
        with self.assertRaisesRegex(Exception, "TRIAL_BEFORE_OUTCOME_VIOLATION"):
            guard.allow()

    def test_empty_history_is_wrong_address(self) -> None:
        result = execute_capture(
            repo_root=ROOT,
            policy=self.policy,
            pages=[
                _tx_row(
                    logs=["Program 11111111111111111111111111111111 success"],
                    keys=[NAMED_MINT],
                    sig="emptySig1111111111111111111111111111111111111111111111111111111",
                )
            ],
        )
        self.assertEqual(result["terminal_decision"], "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT")
        self.assertEqual(result["scan"]["create_events"], 0)
        self.assertEqual(result["scan"]["migration_events"], 0)

    def test_create_and_migration_below_h11_minima(self) -> None:
        pages = [
            _tx_row(
                logs=_pump_logs(self.plan, "CreateEvent"),
                keys=[PUMP_PROGRAM_ID, NAMED_MINT],
                sig="createSig111111111111111111111111111111111111111111111111111111",
                index=0,
            ),
            _tx_row(
                logs=_pump_logs(self.plan, "CompletePumpAmmMigrationEvent"),
                keys=[PUMP_PROGRAM_ID, NAMED_MINT, POOL_ADDRESS],
                sig="migrSig11111111111111111111111111111111111111111111111111111111",
                index=1,
            ),
        ]
        result = execute_capture(repo_root=ROOT, policy=self.policy, pages=pages)
        self.assertGreaterEqual(result["scan"]["create_events"], 1)
        self.assertGreaterEqual(result["scan"]["migration_events"], 1)
        self.assertEqual(result["terminal_decision"], "INSUFFICIENT_SCALE_WITHOUT_PAID_CAPTURE")
        self.assertFalse(result["live_PIT_claim"])


if __name__ == "__main__":
    unittest.main()
