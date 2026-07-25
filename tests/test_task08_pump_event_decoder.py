from __future__ import annotations

import base64
import copy
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import LifecycleState  # noqa: E402
from solana_alpha_lab.pump_event_decoder import (  # noqa: E402
    FROZEN_EVENT_SUBSET_SHA256,
    MAX_STRING_BYTES,
    MAX_VECTOR_ITEMS,
    PROGRAM_DATA_PREFIX,
    PUMP_IDL_BLOB_SHA,
    PUMP_PROGRAM_ID,
    FieldSpec,
    PumpEventContractError,
    PumpEventDecodeError,
    PumpEventPlan,
    compile_pump_event_idl_subset,
    decode_pump_program_data,
    load_pinned_pump_event_plan,
)

FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "task08" / "pump_event_idl_subset_v1.json"
)
MODULE_PATH = SRC / "solana_alpha_lab" / "pump_event_decoder.py"


def _sample_value(field: FieldSpec, seed: int) -> object:
    if field.type_spec == "bool":
        return True
    if field.type_spec == "i64":
        return 1_721_888_000 + seed
    if field.type_spec == "pubkey":
        return bytes([seed % 251]) * 32
    if field.type_spec == "string":
        return f"synthetic-{field.name}-{seed}"
    if field.type_spec == "u16":
        return seed
    if field.type_spec == "u64":
        return 10_000 + seed
    if field.type_spec == ("vec_defined", "Shareholder"):
        return [
            {
                "address": bytes([(seed + 1) % 251]) * 32,
                "share_bps": 125,
            }
        ]
    raise AssertionError(f"unsupported_test_type:{field.type_spec!r}")


def _encode_type(
    plan: PumpEventPlan,
    type_spec: object,
    value: object,
) -> bytes:
    if type_spec == "bool":
        if isinstance(value, bool):
            return bytes([int(value)])
        if isinstance(value, int):
            return bytes([value])
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
        if not isinstance(value, list):
            raise AssertionError("test_vector_must_be_list")
        encoded = bytearray(struct.pack("<I", len(value)))
        for item in value:
            if not isinstance(item, dict):
                raise AssertionError("test_defined_value_must_be_mapping")
            for field in plan.defined_types["Shareholder"]:
                encoded.extend(
                    _encode_type(plan, field.type_spec, item[field.name])
                )
        return bytes(encoded)
    raise AssertionError(f"unsupported_test_type:{type_spec!r}")


def _event_payload(
    plan: PumpEventPlan,
    event_name: str,
    *,
    overrides: dict[str, object] | None = None,
) -> bytes:
    schema = next(event for event in plan.events if event.name == event_name)
    values = {
        field.name: _sample_value(field, index)
        for index, field in enumerate(schema.fields)
    }
    if overrides:
        values.update(overrides)
    body = b"".join(
        _encode_type(plan, field.type_spec, values[field.name])
        for field in schema.fields
    )
    return schema.discriminator + body


def _log_line(payload: bytes) -> str:
    return PROGRAM_DATA_PREFIX + base64.b64encode(payload).decode("ascii")


class Task08PumpEventDecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.plan = load_pinned_pump_event_plan(FIXTURE_PATH)

    def test_frozen_source_pin_hash_and_inventory_compile_exactly(self) -> None:
        self.assertEqual(self.plan.fixture_sha256, FROZEN_EVENT_SUBSET_SHA256)
        self.assertEqual(self.plan.source_blob_sha, PUMP_IDL_BLOB_SHA)
        self.assertEqual(self.plan.program_id, PUMP_PROGRAM_ID)
        self.assertEqual(
            tuple(event.name for event in self.plan.events),
            (
                "CreateEvent",
                "TradeEvent",
                "CompleteEvent",
                "CompletePumpAmmMigrationEvent",
            ),
        )
        self.assertEqual(
            tuple(event.lifecycle_state for event in self.plan.events),
            (
                LifecycleState.CREATED,
                LifecycleState.ACTIVE,
                LifecycleState.MIGRATION_STARTED,
                LifecycleState.MIGRATED,
            ),
        )

    def test_source_discriminator_and_field_drift_fail_closed(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["source"]["blob_sha"] = "0" * 40
        with self.assertRaisesRegex(PumpEventContractError, "source_drift"):
            compile_pump_event_idl_subset(changed)

    def test_compiled_plan_cannot_mutate_defined_layouts(self) -> None:
        with self.assertRaises(TypeError):
            self.plan.defined_types["Synthetic"] = ()  # type: ignore[index]

        changed = copy.deepcopy(self.document)
        changed["events"][0]["discriminator"][0] += 1
        with self.assertRaisesRegex(
            PumpEventContractError,
            "event_CreateEvent_discriminator_drift",
        ):
            compile_pump_event_idl_subset(changed)

        changed = copy.deepcopy(self.document)
        changed["events"][1]["fields"][0:2] = reversed(
            changed["events"][1]["fields"][0:2]
        )
        with self.assertRaisesRegex(
            PumpEventContractError,
            "event_TradeEvent_field_layout_drift",
        ):
            compile_pump_event_idl_subset(changed)

    def test_all_four_events_decode_to_exact_lifecycle_state(self) -> None:
        expected = {
            "CreateEvent": LifecycleState.CREATED,
            "TradeEvent": LifecycleState.ACTIVE,
            "CompleteEvent": LifecycleState.MIGRATION_STARTED,
            "CompletePumpAmmMigrationEvent": LifecycleState.MIGRATED,
        }
        for event_name, lifecycle_state in expected.items():
            with self.subTest(event_name=event_name):
                decoded = decode_pump_program_data(
                    self.plan,
                    log_line=_log_line(_event_payload(self.plan, event_name)),
                    emitting_program_id=PUMP_PROGRAM_ID,
                    transaction_succeeded=True,
                )
                self.assertIsNotNone(decoded)
                assert decoded is not None
                self.assertEqual(decoded.event_name, event_name)
                self.assertEqual(decoded.lifecycle_state, lifecycle_state)
                self.assertIsInstance(decoded.mint, str)
                self.assertIsInstance(decoded.event_timestamp, int)
                self.assertEqual(len(decoded.payload_sha256), 64)
                if event_name == "CompletePumpAmmMigrationEvent":
                    self.assertIsInstance(decoded.destination_pool, str)
                else:
                    self.assertIsNone(decoded.destination_pool)

    def test_failed_transaction_never_promotes_event(self) -> None:
        self.assertIsNone(
            decode_pump_program_data(
                self.plan,
                log_line=_log_line(
                    _event_payload(self.plan, "CreateEvent")
                ),
                emitting_program_id=PUMP_PROGRAM_ID,
                transaction_succeeded=False,
            )
        )

    def test_program_scope_prefix_and_base64_are_fail_closed(self) -> None:
        line = _log_line(_event_payload(self.plan, "CreateEvent"))
        with self.assertRaisesRegex(
            PumpEventDecodeError,
            "emitting_program_id_mismatch",
        ):
            decode_pump_program_data(
                self.plan,
                log_line=line,
                emitting_program_id="synthetic-other-program",
                transaction_succeeded=True,
            )
        with self.assertRaisesRegex(
            PumpEventDecodeError,
            "program_data_prefix_invalid",
        ):
            decode_pump_program_data(
                self.plan,
                log_line="Program log: synthetic",
                emitting_program_id=PUMP_PROGRAM_ID,
                transaction_succeeded=True,
            )
        with self.assertRaisesRegex(
            PumpEventDecodeError,
            "program_data_base64_invalid",
        ):
            decode_pump_program_data(
                self.plan,
                log_line=PROGRAM_DATA_PREFIX + "***",
                emitting_program_id=PUMP_PROGRAM_ID,
                transaction_succeeded=True,
            )
        with self.assertRaisesRegex(
            PumpEventDecodeError,
            "program_data_base64_not_canonical",
        ):
            decode_pump_program_data(
                self.plan,
                log_line=line + " ",
                emitting_program_id=PUMP_PROGRAM_ID,
                transaction_succeeded=True,
            )

    def test_unknown_truncated_and_trailing_payloads_fail_closed(self) -> None:
        for payload, error in (
            (b"\0" * 8, "event_discriminator_unknown"),
            (
                next(
                    event.discriminator
                    for event in self.plan.events
                    if event.name == "CreateEvent"
                ),
                "borsh_payload_truncated",
            ),
            (
                _event_payload(self.plan, "CompleteEvent") + b"\0",
                "event_payload_trailing_bytes",
            ),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(
                PumpEventDecodeError,
                error,
            ):
                decode_pump_program_data(
                    self.plan,
                    log_line=_log_line(payload),
                    emitting_program_id=PUMP_PROGRAM_ID,
                    transaction_succeeded=True,
                )

    def test_bool_string_and_vector_caps_fail_closed(self) -> None:
        invalid_bool = _event_payload(
            self.plan,
            "CreateEvent",
            overrides={"is_mayhem_mode": 2},
        )
        with self.assertRaisesRegex(PumpEventDecodeError, "borsh_bool_invalid"):
            decode_pump_program_data(
                self.plan,
                log_line=_log_line(invalid_bool),
                emitting_program_id=PUMP_PROGRAM_ID,
                transaction_succeeded=True,
            )

        create_discriminator = next(
            event.discriminator
            for event in self.plan.events
            if event.name == "CreateEvent"
        )
        oversized_string = create_discriminator + struct.pack(
            "<I",
            MAX_STRING_BYTES + 1,
        )
        with self.assertRaisesRegex(
            PumpEventDecodeError,
            "borsh_string_too_large",
        ):
            decode_pump_program_data(
                self.plan,
                log_line=_log_line(oversized_string),
                emitting_program_id=PUMP_PROGRAM_ID,
                transaction_succeeded=True,
            )

        oversized_vector = _event_payload(
            self.plan,
            "TradeEvent",
            overrides={
                "shareholders": [
                    {"address": b"\1" * 32, "share_bps": 1}
                    for _ in range(MAX_VECTOR_ITEMS + 1)
                ]
            },
        )
        with self.assertRaisesRegex(
            PumpEventDecodeError,
            "borsh_vector_too_large",
        ):
            decode_pump_program_data(
                self.plan,
                log_line=_log_line(oversized_vector),
                emitting_program_id=PUMP_PROGRAM_ID,
                transaction_succeeded=True,
            )

    def test_zero_pubkey_uses_canonical_base58(self) -> None:
        decoded = decode_pump_program_data(
            self.plan,
            log_line=_log_line(
                _event_payload(
                    self.plan,
                    "CompleteEvent",
                    overrides={"mint": b"\0" * 32},
                )
            ),
            emitting_program_id=PUMP_PROGRAM_ID,
            transaction_succeeded=True,
        )
        self.assertIsNotNone(decoded)
        assert decoded is not None
        self.assertEqual(decoded.mint, "1" * 32)

    def test_module_is_offline_and_has_no_secret_or_transport_boundary(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        for marker in (
            "import httpx",
            "import requests",
            "import urllib",
            "import websockets",
            "socket.",
            "os.environ",
            "getenv(",
            "HELIUS_API_KEY",
            "SOLANA_TRACKER_API_KEY",
        ):
            self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()
