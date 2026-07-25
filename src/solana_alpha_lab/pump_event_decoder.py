"""Pinned, fail-closed offline decoder for the TASK-08 Pump event subset."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeAlias

from solana_alpha_lab.contracts.schema_v1 import LifecycleState

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
BorshType: TypeAlias = str | tuple[str, str]

PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_IDL_REPOSITORY = "pump-fun/pump-public-docs"
PUMP_IDL_PATH = "idl/pump.json"
PUMP_IDL_REF = "main"
PUMP_IDL_BLOB_SHA = "062e66f032bb9f295353b573be3400070bd55e5b"
FROZEN_EVENT_SUBSET_SHA256 = (
    "a81246032718a61fdc0e4cd3e3628bcbf8c7a07ec59de4e528f0acb6e5e9eba7"
)
PROGRAM_DATA_PREFIX = "Program data: "
MAX_EVENT_PAYLOAD_BYTES = 65_536
MAX_STRING_BYTES = 4_096
MAX_VECTOR_ITEMS = 64

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "schema_version",
        "as_of",
        "status",
        "source",
        "program_id",
        "defined_types",
        "events",
    }
)
_EXPECTED_DISCRIMINATORS = {
    "CreateEvent": bytes([27, 114, 169, 77, 222, 235, 99, 118]),
    "TradeEvent": bytes([189, 219, 127, 211, 78, 230, 97, 238]),
    "CompleteEvent": bytes([95, 114, 97, 156, 212, 46, 152, 8]),
    "CompletePumpAmmMigrationEvent": bytes(
        [189, 233, 93, 185, 92, 148, 234, 148]
    ),
}
_EXPECTED_LIFECYCLE_STATES = {
    "CreateEvent": LifecycleState.CREATED,
    "TradeEvent": LifecycleState.ACTIVE,
    "CompleteEvent": LifecycleState.MIGRATION_STARTED,
    "CompletePumpAmmMigrationEvent": LifecycleState.MIGRATED,
}
_EXPECTED_DEFINED_TYPES: dict[str, tuple[tuple[str, BorshType], ...]] = {
    "Shareholder": (
        ("address", "pubkey"),
        ("share_bps", "u16"),
    ),
}
_EXPECTED_EVENT_FIELDS: dict[str, tuple[tuple[str, BorshType], ...]] = {
    "CreateEvent": (
        ("name", "string"),
        ("symbol", "string"),
        ("uri", "string"),
        ("mint", "pubkey"),
        ("bonding_curve", "pubkey"),
        ("user", "pubkey"),
        ("creator", "pubkey"),
        ("timestamp", "i64"),
        ("virtual_token_reserves", "u64"),
        ("virtual_sol_reserves", "u64"),
        ("real_token_reserves", "u64"),
        ("token_total_supply", "u64"),
        ("token_program", "pubkey"),
        ("is_mayhem_mode", "bool"),
        ("is_cashback_enabled", "bool"),
        ("quote_mint", "pubkey"),
        ("virtual_quote_reserves", "u64"),
    ),
    "TradeEvent": (
        ("mint", "pubkey"),
        ("sol_amount", "u64"),
        ("token_amount", "u64"),
        ("is_buy", "bool"),
        ("user", "pubkey"),
        ("timestamp", "i64"),
        ("virtual_sol_reserves", "u64"),
        ("virtual_token_reserves", "u64"),
        ("real_sol_reserves", "u64"),
        ("real_token_reserves", "u64"),
        ("fee_recipient", "pubkey"),
        ("fee_basis_points", "u64"),
        ("fee", "u64"),
        ("creator", "pubkey"),
        ("creator_fee_basis_points", "u64"),
        ("creator_fee", "u64"),
        ("track_volume", "bool"),
        ("total_unclaimed_tokens", "u64"),
        ("total_claimed_tokens", "u64"),
        ("current_sol_volume", "u64"),
        ("last_update_timestamp", "i64"),
        ("ix_name", "string"),
        ("mayhem_mode", "bool"),
        ("cashback_fee_basis_points", "u64"),
        ("cashback", "u64"),
        ("buyback_fee_basis_points", "u64"),
        ("buyback_fee", "u64"),
        ("shareholders", ("vec_defined", "Shareholder")),
        ("quote_mint", "pubkey"),
        ("quote_amount", "u64"),
        ("virtual_quote_reserves", "u64"),
        ("real_quote_reserves", "u64"),
    ),
    "CompleteEvent": (
        ("user", "pubkey"),
        ("mint", "pubkey"),
        ("bonding_curve", "pubkey"),
        ("timestamp", "i64"),
        ("quote_mint", "pubkey"),
    ),
    "CompletePumpAmmMigrationEvent": (
        ("user", "pubkey"),
        ("mint", "pubkey"),
        ("mint_amount", "u64"),
        ("sol_amount", "u64"),
        ("pool_migration_fee", "u64"),
        ("bonding_curve", "pubkey"),
        ("timestamp", "i64"),
        ("pool", "pubkey"),
        ("quote_mint", "pubkey"),
    ),
}


class PumpEventContractError(ValueError):
    """The pinned Pump event subset is malformed or has drifted."""


class PumpEventDecodeError(PumpEventContractError):
    """A candidate Pump log cannot be decoded under the pinned subset."""


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    type_spec: BorshType


@dataclass(frozen=True, slots=True)
class EventSchema:
    name: str
    discriminator: bytes
    lifecycle_state: LifecycleState
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True, slots=True)
class PumpEventPlan:
    fixture_sha256: str
    source_blob_sha: str
    program_id: str
    defined_types: Mapping[str, tuple[FieldSpec, ...]]
    events: tuple[EventSchema, ...]

    @property
    def event_by_discriminator(self) -> dict[bytes, EventSchema]:
        return {event.discriminator: event for event in self.events}


@dataclass(frozen=True, slots=True)
class DecodedPumpEvent:
    event_name: str
    lifecycle_state: LifecycleState
    fields: dict[str, JsonValue]
    payload_sha256: str

    @property
    def mint(self) -> str:
        value = self.fields.get("mint")
        if not isinstance(value, str):
            raise PumpEventDecodeError("decoded_event_missing_mint")
        return value

    @property
    def event_timestamp(self) -> int:
        value = self.fields.get("timestamp")
        if isinstance(value, bool) or not isinstance(value, int):
            raise PumpEventDecodeError("decoded_event_missing_timestamp")
        return value

    @property
    def destination_pool(self) -> str | None:
        value = self.fields.get("pool")
        if value is None:
            return None
        if not isinstance(value, str):
            raise PumpEventDecodeError("decoded_event_pool_invalid")
        return value


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PumpEventContractError(f"{name}_must_be_mapping")
    if not all(isinstance(key, str) for key in value):
        raise PumpEventContractError(f"{name}_keys_must_be_text")
    return value


def _sequence(name: str, value: object) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PumpEventContractError(f"{name}_must_be_sequence")
    return value


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PumpEventContractError(f"{name}_must_be_nonempty_text")
    return value


def _exact(name: str, value: object, expected: object) -> None:
    if value != expected:
        raise PumpEventContractError(f"{name}_drift")


def _compile_type(name: str, value: object) -> BorshType:
    if isinstance(value, str):
        if value not in {"bool", "i64", "pubkey", "string", "u16", "u64"}:
            raise PumpEventContractError(f"{name}_unsupported_primitive:{value}")
        return value
    document = _mapping(name, value)
    _exact(f"{name}_keys", set(document), {"vec"})
    vector = _mapping(f"{name}_vec", document["vec"])
    _exact(f"{name}_vec_keys", set(vector), {"defined"})
    return ("vec_defined", _text(f"{name}_defined", vector["defined"]))


def _compile_fields(name: str, value: object) -> tuple[FieldSpec, ...]:
    rows = _sequence(name, value)
    fields: list[FieldSpec] = []
    for index, item in enumerate(rows):
        row = _mapping(f"{name}_{index}", item)
        _exact(f"{name}_{index}_keys", set(row), {"name", "type"})
        fields.append(
            FieldSpec(
                name=_text(f"{name}_{index}_name", row["name"]),
                type_spec=_compile_type(f"{name}_{index}_type", row["type"]),
            )
        )
    field_names = [field.name for field in fields]
    if len(field_names) != len(set(field_names)):
        raise PumpEventContractError(f"{name}_duplicate_field")
    return tuple(fields)


def compile_pump_event_idl_subset(
    document: Mapping[str, Any],
    *,
    fixture_sha256: str = FROZEN_EVENT_SUBSET_SHA256,
) -> PumpEventPlan:
    """Compile only the exact source-pinned Pump event subset."""

    root = _mapping("event_subset", document)
    _exact("top_level_keys", set(root), _TOP_LEVEL_KEYS)
    _exact("schema", root["schema"], "solana_alpha_lab.pump_event_idl_subset")
    _exact("schema_version", root["schema_version"], "1.0")
    _exact("as_of", root["as_of"], "2026-07-25")
    _exact("status", root["status"], "PINNED_OFFICIAL_SUBSET")
    _exact(
        "source",
        root["source"],
        {
            "repository": PUMP_IDL_REPOSITORY,
            "ref": PUMP_IDL_REF,
            "path": PUMP_IDL_PATH,
            "blob_sha": PUMP_IDL_BLOB_SHA,
            "retrieval_mode": "GITHUB_CONTENTS_READ_ONLY",
        },
    )
    _exact("program_id", root["program_id"], PUMP_PROGRAM_ID)

    defined_document = _mapping("defined_types", root["defined_types"])
    _exact("defined_type_inventory", tuple(defined_document), ("Shareholder",))
    defined_types = {
        name: _compile_fields(f"defined_type_{name}", fields)
        for name, fields in defined_document.items()
    }
    normalized_defined = {
        name: tuple((field.name, field.type_spec) for field in fields)
        for name, fields in defined_types.items()
    }
    _exact("defined_type_layouts", normalized_defined, _EXPECTED_DEFINED_TYPES)

    rows = _sequence("events", root["events"])
    events: list[EventSchema] = []
    for index, item in enumerate(rows):
        row = _mapping(f"event_{index}", item)
        _exact(
            f"event_{index}_keys",
            set(row),
            {"name", "discriminator", "lifecycle_state", "fields"},
        )
        event_name = _text(f"event_{index}_name", row["name"])
        if event_name not in _EXPECTED_DISCRIMINATORS:
            raise PumpEventContractError(f"unexpected_event:{event_name}")
        discriminator_values = _sequence(
            f"event_{event_name}_discriminator",
            row["discriminator"],
        )
        if (
            len(discriminator_values) != 8
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= 255
                for value in discriminator_values
            )
        ):
            raise PumpEventContractError(
                f"event_{event_name}_discriminator_invalid"
            )
        discriminator = bytes(discriminator_values)
        _exact(
            f"event_{event_name}_discriminator",
            discriminator,
            _EXPECTED_DISCRIMINATORS[event_name],
        )
        expected_state = _EXPECTED_LIFECYCLE_STATES[event_name]
        _exact(
            f"event_{event_name}_lifecycle_state",
            row["lifecycle_state"],
            expected_state.value,
        )
        fields = _compile_fields(f"event_{event_name}_fields", row["fields"])
        normalized_fields = tuple(
            (field.name, field.type_spec) for field in fields
        )
        _exact(
            f"event_{event_name}_field_layout",
            normalized_fields,
            _EXPECTED_EVENT_FIELDS[event_name],
        )
        events.append(
            EventSchema(
                name=event_name,
                discriminator=discriminator,
                lifecycle_state=expected_state,
                fields=fields,
            )
        )

    _exact(
        "event_inventory",
        tuple(event.name for event in events),
        tuple(_EXPECTED_EVENT_FIELDS),
    )
    if len({event.discriminator for event in events}) != len(events):
        raise PumpEventContractError("event_discriminator_collision")
    return PumpEventPlan(
        fixture_sha256=fixture_sha256,
        source_blob_sha=PUMP_IDL_BLOB_SHA,
        program_id=PUMP_PROGRAM_ID,
        defined_types=MappingProxyType(dict(defined_types)),
        events=tuple(events),
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise PumpEventContractError(f"duplicate_json_key:{key}")
        document[key] = value
    return document


def load_pinned_pump_event_plan(path: Path) -> PumpEventPlan:
    """Verify the fixture bytes and compile the exact official event subset."""

    payload = path.read_bytes()
    observed_hash = hashlib.sha256(payload).hexdigest()
    if observed_hash != FROZEN_EVENT_SUBSET_SHA256:
        raise PumpEventContractError(
            f"event_subset_hash_mismatch:{observed_hash}"
        )
    try:
        document = json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PumpEventContractError("event_subset_invalid_json") from exc
    return compile_pump_event_idl_subset(
        document,
        fixture_sha256=observed_hash,
    )


class _BorshReader:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._offset = 0

    @property
    def remaining(self) -> int:
        return len(self._payload) - self._offset

    def take(self, size: int) -> bytes:
        if size < 0 or size > self.remaining:
            raise PumpEventDecodeError("borsh_payload_truncated")
        start = self._offset
        self._offset += size
        return self._payload[start : start + size]

    def unsigned(self, size: int) -> int:
        return int.from_bytes(self.take(size), "little", signed=False)

    def signed(self, size: int) -> int:
        return int.from_bytes(self.take(size), "little", signed=True)


def _base58_encode(value: bytes) -> str:
    zero_prefix = len(value) - len(value.lstrip(b"\0"))
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58_ALPHABET[remainder] + encoded
    return ("1" * zero_prefix) + encoded


def _decode_type(
    reader: _BorshReader,
    type_spec: BorshType,
    *,
    plan: PumpEventPlan,
) -> JsonValue:
    if type_spec == "bool":
        value = reader.unsigned(1)
        if value not in {0, 1}:
            raise PumpEventDecodeError("borsh_bool_invalid")
        return bool(value)
    if type_spec == "i64":
        return reader.signed(8)
    if type_spec == "pubkey":
        return _base58_encode(reader.take(32))
    if type_spec == "string":
        length = reader.unsigned(4)
        if length > MAX_STRING_BYTES:
            raise PumpEventDecodeError("borsh_string_too_large")
        try:
            return reader.take(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PumpEventDecodeError("borsh_string_invalid_utf8") from exc
    if type_spec == "u16":
        return reader.unsigned(2)
    if type_spec == "u64":
        return reader.unsigned(8)
    if (
        isinstance(type_spec, tuple)
        and len(type_spec) == 2
        and type_spec[0] == "vec_defined"
    ):
        length = reader.unsigned(4)
        if length > MAX_VECTOR_ITEMS:
            raise PumpEventDecodeError("borsh_vector_too_large")
        type_name = type_spec[1]
        if type_name not in plan.defined_types:
            raise PumpEventDecodeError(f"borsh_defined_type_unknown:{type_name}")
        values: list[JsonValue] = []
        for _ in range(length):
            item = {
                field.name: _decode_type(
                    reader,
                    field.type_spec,
                    plan=plan,
                )
                for field in plan.defined_types[type_name]
            }
            values.append(item)
        return values
    raise PumpEventDecodeError(f"borsh_type_unsupported:{type_spec!r}")


def decode_pump_program_data(
    plan: PumpEventPlan,
    *,
    log_line: str,
    emitting_program_id: str,
    transaction_succeeded: bool,
) -> DecodedPumpEvent | None:
    """Decode one Pump Anchor event line with no transport or future inference."""

    if not transaction_succeeded:
        return None
    if emitting_program_id != plan.program_id:
        raise PumpEventDecodeError("emitting_program_id_mismatch")
    if not isinstance(log_line, str) or not log_line.startswith(
        PROGRAM_DATA_PREFIX
    ):
        raise PumpEventDecodeError("program_data_prefix_invalid")
    encoded = log_line[len(PROGRAM_DATA_PREFIX) :]
    if not encoded or encoded.strip() != encoded:
        raise PumpEventDecodeError("program_data_base64_not_canonical")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PumpEventDecodeError("program_data_base64_invalid") from exc
    if len(payload) < 8:
        raise PumpEventDecodeError("event_payload_missing_discriminator")
    if len(payload) > MAX_EVENT_PAYLOAD_BYTES:
        raise PumpEventDecodeError("event_payload_too_large")

    discriminator = payload[:8]
    schema = plan.event_by_discriminator.get(discriminator)
    if schema is None:
        raise PumpEventDecodeError("event_discriminator_unknown")
    reader = _BorshReader(payload[8:])
    fields = {
        field.name: _decode_type(reader, field.type_spec, plan=plan)
        for field in schema.fields
    }
    if reader.remaining:
        raise PumpEventDecodeError("event_payload_trailing_bytes")
    decoded = DecodedPumpEvent(
        event_name=schema.name,
        lifecycle_state=schema.lifecycle_state,
        fields=fields,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
    )
    decoded.mint
    decoded.event_timestamp
    if schema.name == "CompletePumpAmmMigrationEvent":
        if decoded.destination_pool is None:
            raise PumpEventDecodeError("migration_event_missing_pool")
    elif decoded.destination_pool is not None:
        raise PumpEventDecodeError("unexpected_destination_pool")
    return decoded
