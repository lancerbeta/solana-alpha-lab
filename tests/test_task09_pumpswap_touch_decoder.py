from __future__ import annotations

import base64
import copy
import json
import struct
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import Side  # noqa: E402
from solana_alpha_lab.pumpswap_touch_decoder import (  # noqa: E402
    FROZEN_PUMPSWAP_SUBSET_SHA256,
    PROGRAM_DATA_PREFIX,
    PUMPSWAP_IDL_COMMIT,
    PUMPSWAP_IDL_GIT_BLOB_SHA1,
    PUMPSWAP_IDL_SHA256,
    PUMPSWAP_PROGRAM_ID,
    U64_MAX,
    DecodedPoolAccount,
    FieldSpec,
    LayoutSchema,
    PumpSwapContractError,
    PumpSwapDecodeError,
    PumpSwapIdlPlan,
    PumpSwapProjectionError,
    compile_pumpswap_idl_subset,
    decode_pumpswap_pool_account,
    decode_pumpswap_program_data,
    effective_quote_reserves,
    load_pinned_pumpswap_plan,
    project_pool_touch,
    project_trade_touch,
)

FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "task09" / "pumpswap_idl_subset_v1.json"
)
MODULE_PATH = SRC / "solana_alpha_lab" / "pumpswap_touch_decoder.py"
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58(value: bytes) -> str:
    zero_prefix = len(value) - len(value.lstrip(b"\0"))
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58_ALPHABET[remainder] + encoded
    return ("1" * zero_prefix) + encoded


def _sample_value(field: FieldSpec, seed: int) -> object:
    if field.type_spec == "bool":
        return seed % 2 == 0
    if field.type_spec == "i64":
        return 1_720_000_000 + seed
    if field.type_spec == "i128":
        return 500 + seed
    if field.type_spec == "pubkey":
        return bytes([(seed % 250) + 1]) * 32
    if field.type_spec == "string":
        return "buy" if field.name == "ix_name" else f"synthetic-{seed}"
    if field.type_spec == "u8":
        return (seed + 1) % 256
    if field.type_spec == "u16":
        return 100 + seed
    if field.type_spec == "u64":
        return 1_000 + seed
    raise AssertionError(f"unsupported_test_type:{field.type_spec}")


def _encode_type(type_spec: str, value: object) -> bytes:
    if type_spec == "bool":
        if isinstance(value, bool):
            return bytes([int(value)])
        return bytes([int(value)])
    if type_spec == "i64":
        return struct.pack("<q", int(value))
    if type_spec == "i128":
        return int(value).to_bytes(16, "little", signed=True)
    if type_spec == "pubkey":
        if not isinstance(value, bytes) or len(value) != 32:
            raise AssertionError("test_pubkey_must_be_32_bytes")
        return value
    if type_spec == "string":
        encoded = str(value).encode("utf-8")
        return struct.pack("<I", len(encoded)) + encoded
    if type_spec == "u8":
        return struct.pack("<B", int(value))
    if type_spec == "u16":
        return struct.pack("<H", int(value))
    if type_spec == "u64":
        return struct.pack("<Q", int(value))
    raise AssertionError(f"unsupported_test_type:{type_spec}")


def _layout_payload(
    schema: LayoutSchema,
    *,
    overrides: dict[str, object] | None = None,
) -> bytes:
    values = {
        field.name: _sample_value(field, index)
        for index, field in enumerate(schema.fields)
    }
    if overrides:
        values.update(overrides)
    body = b"".join(
        _encode_type(field.type_spec, values[field.name])
        for field in schema.fields
    )
    return schema.discriminator + body


def _log_line(payload: bytes) -> str:
    return PROGRAM_DATA_PREFIX + base64.b64encode(payload).decode("ascii")


class Task09PumpSwapTouchDecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.plan = load_pinned_pumpswap_plan(FIXTURE_PATH)
        cls.pool_pubkey_bytes = b"\x09" * 32
        cls.pool_pubkey = _base58(cls.pool_pubkey_bytes)
        cls.base_mint_bytes = b"\x0a" * 32
        cls.quote_mint_bytes = b"\x0b" * 32
        cls.pool = cls.decode_pool(index=0, virtual=500)

    @classmethod
    def decode_pool(
        cls,
        *,
        index: int,
        virtual: int,
    ) -> DecodedPoolAccount:
        payload = _layout_payload(
            cls.plan.pool,
            overrides={
                "index": index,
                "base_mint": cls.base_mint_bytes,
                "quote_mint": cls.quote_mint_bytes,
                "pool_base_token_account": b"\x0c" * 32,
                "pool_quote_token_account": b"\x0d" * 32,
                "virtual_quote_reserves": virtual,
            },
        )
        return decode_pumpswap_pool_account(
            cls.plan,
            account_data=payload,
            account_pubkey=cls.pool_pubkey,
            owner_program_id=PUMPSWAP_PROGRAM_ID,
        )

    def test_source_pin_fixture_hash_and_inventory_are_exact(self) -> None:
        self.assertEqual(
            self.plan.fixture_sha256,
            FROZEN_PUMPSWAP_SUBSET_SHA256,
        )
        self.assertEqual(self.plan.source_commit, PUMPSWAP_IDL_COMMIT)
        self.assertEqual(self.plan.source_content_sha256, PUMPSWAP_IDL_SHA256)
        self.assertEqual(
            self.document["source"]["git_blob_sha1"],
            PUMPSWAP_IDL_GIT_BLOB_SHA1,
        )
        self.assertEqual(self.plan.program_id, PUMPSWAP_PROGRAM_ID)
        self.assertEqual(self.plan.pool.name, "Pool")
        self.assertEqual(
            tuple(event.name for event in self.plan.events),
            ("BuyEvent", "SellEvent"),
        )

    def test_source_discriminator_and_field_drift_fail_closed(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["source"]["commit"] = "0" * 40
        with self.assertRaisesRegex(PumpSwapContractError, "source_drift"):
            compile_pumpswap_idl_subset(changed)

        changed = copy.deepcopy(self.document)
        changed["accounts"][0]["discriminator"][0] += 1
        with self.assertRaisesRegex(
            PumpSwapContractError,
            "Pool_discriminator_drift",
        ):
            compile_pumpswap_idl_subset(changed)

        changed = copy.deepcopy(self.document)
        changed["events"][0]["fields"][0:2] = reversed(
            changed["events"][0]["fields"][0:2]
        )
        with self.assertRaisesRegex(
            PumpSwapContractError,
            "BuyEvent_field_layout_drift",
        ):
            compile_pumpswap_idl_subset(changed)

    def test_pool_account_decodes_raw_identity_without_vault_substitution(self) -> None:
        self.assertEqual(self.pool.account_pubkey, self.pool_pubkey)
        self.assertEqual(self.pool.base_mint, _base58(self.base_mint_bytes))
        self.assertEqual(self.pool.quote_mint, _base58(self.quote_mint_bytes))
        self.assertEqual(self.pool.index, 0)
        self.assertEqual(self.pool.virtual_quote_reserves, 500)
        self.assertEqual(len(self.pool.payload_sha256), 64)

        payload = _layout_payload(self.plan.pool)
        with self.assertRaisesRegex(
            PumpSwapDecodeError,
            "pool_owner_program_id_mismatch",
        ):
            decode_pumpswap_pool_account(
                self.plan,
                account_data=payload,
                account_pubkey=self.pool_pubkey,
                owner_program_id="synthetic-other-program",
            )

    def test_buy_and_sell_decode_exact_user_amounts(self) -> None:
        expected = {
            "BuyEvent": (
                Side.BUY,
                {"base_amount_out": 125, "user_quote_amount_in": 250},
            ),
            "SellEvent": (
                Side.SELL,
                {"base_amount_in": 175, "user_quote_amount_out": 300},
            ),
        }
        for event_name, (side, amounts) in expected.items():
            schema = next(
                event for event in self.plan.events if event.name == event_name
            )
            overrides: dict[str, object] = {
                "timestamp": 1_720_000_000,
                "pool": self.pool_pubkey_bytes,
                "pool_base_token_reserves": 10_000,
                "pool_quote_token_reserves": 20_000,
                "virtual_quote_reserves": 500,
                **amounts,
            }
            decoded = decode_pumpswap_program_data(
                self.plan,
                log_line=_log_line(_layout_payload(schema, overrides=overrides)),
                emitting_program_id=PUMPSWAP_PROGRAM_ID,
                transaction_succeeded=True,
            )
            self.assertIsNotNone(decoded)
            assert decoded is not None
            self.assertEqual(decoded.event_name, event_name)
            self.assertEqual(decoded.side, side)
            self.assertEqual(decoded.pool_id, self.pool_pubkey)

    def test_failed_transaction_never_promotes_trade_touch(self) -> None:
        schema = self.plan.events[0]
        self.assertIsNone(
            decode_pumpswap_program_data(
                self.plan,
                log_line=_log_line(_layout_payload(schema)),
                emitting_program_id=PUMPSWAP_PROGRAM_ID,
                transaction_succeeded=False,
            )
        )

    def test_unknown_truncated_trailing_and_invalid_bool_fail_closed(self) -> None:
        schema = self.plan.events[0]
        cases = (
            (b"\0" * 8, "event_discriminator_unknown"),
            (schema.discriminator, "borsh_payload_truncated"),
            (_layout_payload(schema) + b"\0", "borsh_payload_trailing_bytes"),
            (
                _layout_payload(schema, overrides={"track_volume": 2}),
                "borsh_bool_invalid",
            ),
        )
        for payload, error in cases:
            with self.subTest(error=error), self.assertRaisesRegex(
                PumpSwapDecodeError,
                error,
            ):
                decode_pumpswap_program_data(
                    self.plan,
                    log_line=_log_line(payload),
                    emitting_program_id=PUMPSWAP_PROGRAM_ID,
                    transaction_succeeded=True,
                )

    def test_effective_reserves_preserve_raw_virtual_and_bounds(self) -> None:
        self.assertEqual(
            effective_quote_reserves(
                raw_quote_reserve_atomic=1_000,
                virtual_quote_reserves_atomic=-250,
            ),
            750,
        )
        for raw, virtual in ((100, -101), (U64_MAX, 1), (-1, 0)):
            with self.subTest(raw=raw, virtual=virtual), self.assertRaises(
                PumpSwapProjectionError
            ):
                effective_quote_reserves(
                    raw_quote_reserve_atomic=raw,
                    virtual_quote_reserves_atomic=virtual,
                )

    def test_pool_projection_is_touch_only_and_index_zero_is_not_migration(self) -> None:
        times = self._times()
        projection = project_pool_touch(
            self.pool,
            raw_base_reserve_atomic=10_000,
            raw_quote_reserve_atomic=20_000,
            base_decimals=6,
            quote_decimals=9,
            context_slot=123,
            raw_event_id="raw-synthetic-pool",
            **times,
        )
        self.assertEqual(projection.pool_snapshot.base_reserve_atomic, 10_000)
        self.assertEqual(projection.pool_snapshot.quote_reserve_atomic, 20_000)
        self.assertEqual(
            projection.universe_labels,
            ("PUMPSWAP_OBSERVED", "CANONICAL_INDEX_CANDIDATE"),
        )
        self.assertNotIn("PUMP_MIGRATION_CONFIRMED", projection.universe_labels)
        values = {
            observation.observation_type: observation
            for observation in projection.observations
        }
        self.assertEqual(
            values["virtual_quote_reserves_atomic"].value_decimal,
            500,
        )
        self.assertEqual(
            values["effective_quote_reserves_atomic"].value_atomic,
            20_500,
        )

    def test_buy_sell_projection_maps_touch_without_quote_or_fill_claim(self) -> None:
        expected = {
            "BuyEvent": (Side.BUY, self.pool.quote_mint, 250, self.pool.base_mint, 125),
            "SellEvent": (Side.SELL, self.pool.base_mint, 175, self.pool.quote_mint, 300),
        }
        for event_name, expected_trade in expected.items():
            schema = next(
                event for event in self.plan.events if event.name == event_name
            )
            amounts = (
                {"base_amount_out": 125, "user_quote_amount_in": 250}
                if event_name == "BuyEvent"
                else {"base_amount_in": 175, "user_quote_amount_out": 300}
            )
            payload = _layout_payload(
                schema,
                overrides={
                    "timestamp": 1_720_000_000,
                    "pool": self.pool_pubkey_bytes,
                    "pool_base_token_reserves": 10_000,
                    "pool_quote_token_reserves": 20_000,
                    "virtual_quote_reserves": 500,
                    **amounts,
                },
            )
            decoded = decode_pumpswap_program_data(
                self.plan,
                log_line=_log_line(payload),
                emitting_program_id=PUMPSWAP_PROGRAM_ID,
                transaction_succeeded=True,
            )
            assert decoded is not None
            projection = project_trade_touch(
                decoded,
                pool=self.pool,
                base_decimals=6,
                quote_decimals=9,
                transaction_signature=f"synthetic-signature-{event_name}",
                instruction_index=1,
                event_index=0,
                context_slot=123,
                raw_event_id=f"raw-synthetic-{event_name}",
                observed_at=self._times()["observed_at"],
                first_reliable_available_at=self._times()[
                    "first_reliable_available_at"
                ],
                available_at=self._times()["available_at"],
                ingested_at=self._times()["ingested_at"],
            )
            side, in_mint, in_amount, out_mint, out_amount = expected_trade
            self.assertEqual(projection.trade.side, side)
            self.assertEqual(projection.trade.input_mint, in_mint)
            self.assertEqual(projection.trade.input_amount_atomic, in_amount)
            self.assertEqual(projection.trade.output_mint, out_mint)
            self.assertEqual(projection.trade.output_amount_atomic, out_amount)
            self.assertEqual(
                projection.universe_labels,
                ("PUMPSWAP_OBSERVED",),
            )
            self.assertIn("NOT_OUR_FILL", projection.trade.quality_flags)
            self.assertEqual(len(projection.observations), 12)
            self.assertEqual(
                projection.pool_snapshot.quote_reserve_atomic,
                20_000,
            )

    def test_projection_is_deterministic_and_pit_order_fails_closed(self) -> None:
        kwargs = {
            "raw_base_reserve_atomic": 10_000,
            "raw_quote_reserve_atomic": 20_000,
            "base_decimals": 6,
            "quote_decimals": 9,
            "context_slot": 123,
            "raw_event_id": "raw-synthetic-pool",
            **self._times(),
        }
        first = project_pool_touch(self.pool, **kwargs)
        second = project_pool_touch(self.pool, **kwargs)
        self.assertEqual(first, second)

        broken = dict(kwargs)
        broken["observed_at"] = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with self.assertRaisesRegex(
            PumpSwapProjectionError,
            "timestamp_order_invalid",
        ):
            project_pool_touch(self.pool, **broken)

    def test_module_is_offline_and_forbids_execution_quote_surfaces(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        for marker in (
            "import httpx",
            "import requests",
            "import urllib",
            "import websockets",
            "socket.",
            "os.environ",
            "getenv(",
            "QuoteAttempt",
            "quote_attempts",
            "Transaction",
            "Keypair",
        ):
            self.assertNotIn(marker, source)

    @staticmethod
    def _times() -> dict[str, datetime]:
        return {
            "event_time": datetime(2024, 7, 3, tzinfo=timezone.utc),
            "observed_at": datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
            "first_reliable_available_at": datetime(
                2026,
                7,
                27,
                10,
                0,
                1,
                tzinfo=timezone.utc,
            ),
            "available_at": datetime(
                2026,
                7,
                27,
                10,
                0,
                2,
                tzinfo=timezone.utc,
            ),
            "ingested_at": datetime(
                2026,
                7,
                27,
                10,
                0,
                3,
                tzinfo=timezone.utc,
            ),
        }


if __name__ == "__main__":
    unittest.main()
