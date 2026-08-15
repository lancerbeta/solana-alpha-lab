from __future__ import annotations

import base64
import hashlib
import json
import struct
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pumpswap_touch_decoder import (  # noqa: E402
    PROGRAM_DATA_PREFIX,
    PUMPSWAP_PROGRAM_ID,
    load_pinned_pumpswap_plan,
)
from solana_alpha_lab.task30_raw_to_pit_admissibility import (  # noqa: E402
    ATOM_ID,
    BASE58_ALPHABET,
    A24IntegrityError,
    audit_pit,
    build_panel,
    execute_admissibility,
    issue_decision,
    load_policy,
    reconcile_batch,
    sha256_bytes,
    verify_input_identity,
)

CONFIG_PATH = ROOT / "configs/task30_a24_raw_to_pit_admissibility_owner_panel_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_a24_raw_to_pit_admissibility_owner_panel.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/raw_to_pit_admissibility_v1.json"
IDL_PATH = ROOT / "tests/fixtures/task09/pumpswap_idl_subset_v1.json"
A22_RAW = ROOT / "local/task30_a22_helius_get_transactions_for_address/run=20260814T184209Z-7572a5c2/raw_response.json"
A23_RAW = ROOT / "local/task30_a23_helius_bounded_pagination/run=20260814T220124Z-e494b5aa/page=001/raw_response.json"
POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
BASE_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
QUOTE_MINT = "So11111111111111111111111111111111111111112"
SINCE = 1_786_492_800
OTHER_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def _b58encode(payload: bytes) -> str:
    number = int.from_bytes(payload, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    pad = len(payload) - len(payload.lstrip(b"\x00"))
    return ("1" * pad) + (encoded or "1")


def _b58decode(value: str) -> bytes:
    number = 0
    for character in value:
        number = number * 58 + BASE58_ALPHABET.index(character)
    payload = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\x00" * (len(value) - len(value.lstrip("1"))) + payload


def _encode_field(type_spec: str, value: object) -> bytes:
    if type_spec == "bool":
        return bytes([int(value)])
    if type_spec == "i64":
        return struct.pack("<q", int(value))
    if type_spec == "i128":
        return int(value).to_bytes(16, "little", signed=True)
    if type_spec == "pubkey":
        assert isinstance(value, bytes) and len(value) == 32
        return value
    if type_spec == "string":
        encoded = str(value).encode()
        return struct.pack("<I", len(encoded)) + encoded
    if type_spec == "u8":
        return struct.pack("<B", int(value))
    if type_spec == "u16":
        return struct.pack("<H", int(value))
    if type_spec == "u64":
        return struct.pack("<Q", int(value))
    raise AssertionError(type_spec)


def _buy_event_line(plan: object) -> str:
    schema = plan.events[0]
    chunks: list[bytes] = [schema.discriminator]
    pool = _b58decode(POOL)
    assert len(pool) == 32
    dummy = b"\x02" * 32
    for field in schema.fields:
        if field.name == "timestamp":
            chunks.append(_encode_field("i64", SINCE + 1000))
        elif field.name == "pool":
            chunks.append(pool)
        elif field.name == "ix_name":
            chunks.append(_encode_field("string", "buy"))
        elif field.type_spec == "pubkey":
            chunks.append(dummy)
        elif field.type_spec == "bool":
            chunks.append(_encode_field("bool", False))
        elif field.type_spec == "i128":
            chunks.append(_encode_field("i128", 7))
        elif field.type_spec == "i64":
            chunks.append(_encode_field("i64", SINCE + 1000))
        else:
            chunks.append(_encode_field(field.type_spec, 1000 if "amount" in field.name or "reserve" in field.name or "supply" in field.name or "volume" in field.name or "token" in field.name else 1))
    return PROGRAM_DATA_PREFIX + base64.b64encode(b"".join(chunks)).decode()


def _ix(program_index: int, digest_hex: str) -> dict[str, object]:
    return {
        "programIdIndex": program_index,
        "accounts": [0],
        "data": _b58encode(bytes.fromhex(digest_hex) + b"\x00" * 16),
        "stackHeight": 1,
    }


def _row(
    *,
    slot: int,
    index: int,
    signature: str,
    block_time: int,
    logs: list[str],
    instructions: list[dict[str, object]],
    inner: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "slot": slot,
        "transactionIndex": index,
        "blockTime": block_time,
        "version": 0,
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": [POOL, PUMPSWAP_PROGRAM_ID, OTHER_PROGRAM],
                "instructions": instructions,
                "recentBlockhash": "blockhash",
            },
        },
        "meta": {
            "err": None,
            "fee": 5000,
            "preBalances": [1, 1, 1],
            "postBalances": [1, 1, 1],
            "preTokenBalances": [
                {
                    "accountIndex": 0,
                    "mint": BASE_MINT,
                    "uiTokenAmount": {
                        "amount": "1",
                        "decimals": 6,
                        "uiAmount": 0.000001,
                        "uiAmountString": "0.000001",
                    },
                },
                {
                    "accountIndex": 0,
                    "mint": QUOTE_MINT,
                    "uiTokenAmount": {
                        "amount": "1",
                        "decimals": 9,
                        "uiAmount": 1e-9,
                        "uiAmountString": "0.000000001",
                    },
                },
            ],
            "postTokenBalances": [],
            "innerInstructions": inner or [],
            "logMessages": logs,
            "loadedAddresses": {"writable": [], "readonly": []},
        },
    }


class Task30A24RawToPitAdmissibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy(CONFIG_PATH)
        cls.plan = load_pinned_pumpswap_plan(IDL_PATH)
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.measured = datetime(2026, 8, 15, 3, 0, tzinfo=UTC)
        cls.buy_logs = [
            f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]",
            _buy_event_line(cls.plan),
            f"Program {PUMPSWAP_PROGRAM_ID} success",
        ]
        cls.buy_disc = cls.policy["instruction_discriminators"]["buy"]

    def test_policy_matches_closed_schema_and_anchor_bindings(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(
            yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        )
        self.assertEqual(self.policy["atom_id"], ATOM_ID)
        self.assertEqual(
            self.policy["non_market_events"]["CloseUserVolumeAccumulatorEvent"][
                "discriminator_hex"
            ],
            hashlib.sha256(b"event:CloseUserVolumeAccumulatorEvent").digest()[:8].hex(),
        )

    def test_hash_drift_is_stop_integrity_conflict(self) -> None:
        result = execute_admissibility(
            repo_root=ROOT,
            policy=self.policy,
            a22_payload=b'{"jsonrpc":"2.0","id":"x","result":{"data":[],"paginationToken":"x"}}',
            a23_payload=b'{"jsonrpc":"2.0","id":"y","result":{"data":[],"paginationToken":null}}',
            measured_as_of=self.measured,
        )
        self.assertEqual(result["terminal_decision"], "STOP_INTEGRITY_CONFLICT")
        self.assertIn("A22_HASH_DRIFT", result["decision"]["integrity_error"])

    def test_other_program_program_data_does_not_poison_pumpswap_event(self) -> None:
        buy_ix = _ix(1, self.buy_disc)
        logs = [
            f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]",
            self.buy_logs[1],
            f"Program {PUMPSWAP_PROGRAM_ID} success",
            f"Program {OTHER_PROGRAM} invoke [1]",
            PROGRAM_DATA_PREFIX + "Synopsis not-valid-base64-payload",
            f"Program {OTHER_PROGRAM} success",
        ]
        row = _row(
            slot=1,
            index=0,
            signature="1" * 64,
            block_time=SINCE + 1000,
            logs=logs,
            instructions=[buy_ix],
        )
        recon = reconcile_batch(self.policy, [row], plan=self.plan)
        self.assertEqual(recon["decoded_buy_sell_events"], 1)

    def test_unknown_pumpswap_discriminator_stops(self) -> None:
        row = _row(
            slot=1,
            index=0,
            signature="2" * 64,
            block_time=SINCE + 1000,
            logs=[
                f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]",
                f"Program {PUMPSWAP_PROGRAM_ID} success",
            ],
            instructions=[_ix(1, "deadbeefdeadbeef")],
        )
        with self.assertRaises(A24IntegrityError):
            reconcile_batch(self.policy, [row], plan=self.plan)

    def test_instruction_event_mismatch_stops(self) -> None:
        row = _row(
            slot=1,
            index=0,
            signature="3" * 64,
            block_time=SINCE + 1000,
            logs=[
                f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]",
                f"Program {PUMPSWAP_PROGRAM_ID} success",
            ],
            instructions=[_ix(1, self.buy_disc)],
        )
        with self.assertRaises(A24IntegrityError):
            reconcile_batch(self.policy, [row], plan=self.plan)

    def test_empty_slot_is_not_implicit_zero_ohlc(self) -> None:
        identity = {
            "a22_sha256": "a" * 64,
            "a23_sha256": "b" * 64,
        }
        recon = {
            "target_trades": reconcile_batch(
                self.policy,
                [
                    _row(
                        slot=9,
                        index=1,
                        signature="4" * 64,
                        block_time=SINCE + 1000,
                        logs=self.buy_logs,
                        instructions=[_ix(1, self.buy_disc)],
                    )
                ],
                plan=self.plan,
            )["target_trades"]
        }
        panel = build_panel(
            self.policy,
            recon,
            identity=identity,
            measured_as_of=self.measured,
        )
        self.assertEqual(len(panel), 96)
        first = panel[0]
        self.assertEqual(first["state"], "PROVEN_NO_TARGET_TRADE")
        self.assertEqual(first["volume_base_atomic"], 0)
        self.assertIsNone(first["ohlc"]["open"])
        traded = next(item for item in panel if item["target_trade_count"])
        self.assertEqual(traded["state"], "OBSERVED_TARGET_TRADES")
        self.assertIsNotNone(traded["ohlc"]["open"])
        later = panel[traded["slot_index"] + 1]
        self.assertEqual(later["state"], "STATE_PERSISTENCE_PROVEN")
        self.assertTrue(later["reserves"]["carry_forward"])
        self.assertIsNone(later["ohlc"]["close"])

    def test_pit_does_not_backdate_retrieval_to_block_time(self) -> None:
        identity = {
            "a22_ingested_at": "2026-08-14T18:42:09Z",
            "completeness_available_at": "2026-08-14T22:01:24Z",
        }
        pit = audit_pit(self.policy, identity, measured_as_of=self.measured)
        self.assertFalse(pit["chain_block_time_used_as_availability"])
        self.assertTrue(pit["retrospective_market_history_usable"])
        self.assertFalse(pit["prospective_pit_route_usable"])
        self.assertEqual(pit["observed_at"], "2026-08-14T18:42:09Z")
        self.assertEqual(pit["first_reliable_available_at"], "2026-08-14T22:01:24Z")
        self.assertNotEqual(pit["first_reliable_available_at"][:10], "2026-08-12")

    def test_truncated_keep_events_when_instructions_match(self) -> None:
        logs = list(self.buy_logs) + ["Log truncated"]
        row = _row(
            slot=2,
            index=0,
            signature="5" * 64,
            block_time=SINCE + 2000,
            logs=logs,
            instructions=[_ix(1, self.buy_disc)],
        )
        recon = reconcile_batch(self.policy, [row], plan=self.plan)
        self.assertEqual(recon["log_truncated_transactions"], 1)
        self.assertEqual(recon["target_pool_trade_events"], 1)

    def test_decision_requires_one_terminal_outcome(self) -> None:
        identity = {"a22_sha256": "a" * 64, "a23_sha256": "b" * 64}
        recon = reconcile_batch(
            self.policy,
            [
                _row(
                    slot=3,
                    index=0,
                    signature="6" * 64,
                    block_time=SINCE + 3000,
                    logs=self.buy_logs,
                    instructions=[_ix(1, self.buy_disc)],
                )
            ],
            plan=self.plan,
        )
        panel = build_panel(
            self.policy, recon, identity=identity, measured_as_of=self.measured
        )
        pit = audit_pit(
            self.policy,
            {
                "a22_ingested_at": "2026-08-14T18:42:09Z",
                "completeness_available_at": "2026-08-14T22:01:24Z",
            },
            measured_as_of=self.measured,
        )
        decision = issue_decision(panel=panel, reconciliation=recon, pit=pit)
        self.assertEqual(decision["terminal_decision"], "LIMITED_DIAGNOSTIC_PANEL_READY")
        self.assertIsNone(decision["provider_gap"])

    def test_fixture_orientation_constants_are_fail_closed(self) -> None:
        expected = self.fixture["orientation_if_live_bytes_present"]
        self.assertEqual(expected["raw_transactions"], 520)
        self.assertEqual(expected["target_buy_events"], 96)
        self.assertEqual(expected["target_sell_events"], 53)
        self.assertEqual(expected["slots_with_target_trades"], 35)
        self.assertEqual(expected["log_truncated_transactions"], 14)

    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/task30/a24_raw_to_pit_admissibility_runtime_receipt_v1.json
    @unittest.skipUnless(A22_RAW.is_file() and A23_RAW.is_file(), "retained raw is local-only")
    def test_live_retained_batch_reproduces_orientation(self) -> None:
        a22 = A22_RAW.read_bytes()
        a23 = A23_RAW.read_bytes()
        identity = verify_input_identity(self.policy, a22_payload=a22, a23_payload=a23)
        recon = reconcile_batch(
            self.policy,
            [_row_from_live(row) for row in identity["rows"]],
            plan=self.plan,
        )
        expected = self.fixture["orientation_if_live_bytes_present"]
        self.assertEqual(recon["successful_transactions"], expected["raw_transactions"])
        self.assertEqual(recon["target_buy_events"], expected["target_buy_events"])
        self.assertEqual(recon["target_sell_events"], expected["target_sell_events"])
        self.assertEqual(
            recon["log_truncated_transactions"],
            expected["log_truncated_transactions"],
        )
        result = execute_admissibility(
            repo_root=ROOT,
            policy=self.policy,
            a22_payload=a22,
            a23_payload=a23,
            measured_as_of=self.measured,
        )
        self.assertEqual(len(result["panel_96_slots"]), 96)
        self.assertEqual(
            result["terminal_decision"], "LIMITED_DIAGNOSTIC_PANEL_READY"
        )
        self.assertFalse(result["pit"]["prospective_pit_route_usable"])
        self.assertEqual(result["side_effects"]["provider_requests"], 0)

    def test_tracked_acceptance_declares_no_source_change(self) -> None:
        receipt = json.loads(
            (
                ROOT
                / "docs/evidence/task30/a24_raw_to_pit_admissibility_acceptance_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            receipt["project_sources_disposition"],
            {"kind": "NO_CHANGE"},
        )


def _row_from_live(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise AssertionError("live_row_must_be_object")
    return row


if __name__ == "__main__":
    unittest.main()
