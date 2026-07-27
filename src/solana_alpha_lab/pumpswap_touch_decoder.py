"""Pinned offline PumpSwap Touch decoder and canonical projector for TASK-09."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeAlias

from solana_alpha_lab.contracts.schema_v1 import (
    CanonicalObservation,
    PoolStateSnapshot,
    Side,
    TradeOrderflowInput,
)

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
BorshType: TypeAlias = str

PUMPSWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
PUMPSWAP_IDL_REPOSITORY = "pump-fun/pump-public-docs"
PUMPSWAP_IDL_COMMIT = "9c82f61cb711b044a17f770ab8ce9f9bdf78f333"
PUMPSWAP_IDL_PATH = "idl/pump_amm.json"
PUMPSWAP_IDL_GIT_BLOB_SHA1 = "a654b6f924c8e5458ba9b38c9e13a3980f5e9518"
PUMPSWAP_IDL_SHA256 = (
    "6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56"
)
FROZEN_PUMPSWAP_SUBSET_SHA256 = (
    "b33652ef0c1a44ac65c64ab0a399b4665a899da0c5f4c6c875e70aee373da53b"
)
PROGRAM_DATA_PREFIX = "Program data: "
MAX_EVENT_PAYLOAD_BYTES = 65_536
MAX_STRING_BYTES = 4_096
U64_MAX = (1 << 64) - 1
I128_MIN = -(1 << 127)
I128_MAX = (1 << 127) - 1

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "schema_version",
        "as_of",
        "status",
        "source",
        "program_id",
        "accounts",
        "events",
    }
)
_SOURCE = {
    "repository": PUMPSWAP_IDL_REPOSITORY,
    "commit": PUMPSWAP_IDL_COMMIT,
    "path": PUMPSWAP_IDL_PATH,
    "git_blob_sha1": PUMPSWAP_IDL_GIT_BLOB_SHA1,
    "content_sha256": PUMPSWAP_IDL_SHA256,
    "retrieval_mode": "GIT_LS_REMOTE_AND_RAW_READ_ONLY",
}
_EXPECTED_DISCRIMINATORS = {
    "Pool": bytes([241, 154, 109, 4, 17, 177, 109, 188]),
    "BuyEvent": bytes([103, 244, 82, 31, 44, 245, 119, 119]),
    "SellEvent": bytes([62, 47, 55, 10, 165, 3, 220, 42]),
}
_EXPECTED_FIELDS: dict[str, tuple[tuple[str, BorshType], ...]] = {
    "Pool": (
        ("pool_bump", "u8"),
        ("index", "u16"),
        ("creator", "pubkey"),
        ("base_mint", "pubkey"),
        ("quote_mint", "pubkey"),
        ("lp_mint", "pubkey"),
        ("pool_base_token_account", "pubkey"),
        ("pool_quote_token_account", "pubkey"),
        ("lp_supply", "u64"),
        ("coin_creator", "pubkey"),
        ("is_mayhem_mode", "bool"),
        ("is_cashback_coin", "bool"),
        ("virtual_quote_reserves", "i128"),
    ),
    "BuyEvent": (
        ("timestamp", "i64"),
        ("base_amount_out", "u64"),
        ("max_quote_amount_in", "u64"),
        ("user_base_token_reserves", "u64"),
        ("user_quote_token_reserves", "u64"),
        ("pool_base_token_reserves", "u64"),
        ("pool_quote_token_reserves", "u64"),
        ("quote_amount_in", "u64"),
        ("lp_fee_basis_points", "u64"),
        ("lp_fee", "u64"),
        ("protocol_fee_basis_points", "u64"),
        ("protocol_fee", "u64"),
        ("quote_amount_in_with_lp_fee", "u64"),
        ("user_quote_amount_in", "u64"),
        ("pool", "pubkey"),
        ("user", "pubkey"),
        ("user_base_token_account", "pubkey"),
        ("user_quote_token_account", "pubkey"),
        ("protocol_fee_recipient", "pubkey"),
        ("protocol_fee_recipient_token_account", "pubkey"),
        ("coin_creator", "pubkey"),
        ("coin_creator_fee_basis_points", "u64"),
        ("coin_creator_fee", "u64"),
        ("track_volume", "bool"),
        ("total_unclaimed_tokens", "u64"),
        ("total_claimed_tokens", "u64"),
        ("current_sol_volume", "u64"),
        ("last_update_timestamp", "i64"),
        ("min_base_amount_out", "u64"),
        ("ix_name", "string"),
        ("cashback_fee_basis_points", "u64"),
        ("cashback", "u64"),
        ("buyback_fee_basis_points", "u64"),
        ("buyback_fee", "u64"),
        ("virtual_quote_reserves", "i128"),
        ("can_boost", "bool"),
        ("base_supply", "u64"),
    ),
    "SellEvent": (
        ("timestamp", "i64"),
        ("base_amount_in", "u64"),
        ("min_quote_amount_out", "u64"),
        ("user_base_token_reserves", "u64"),
        ("user_quote_token_reserves", "u64"),
        ("pool_base_token_reserves", "u64"),
        ("pool_quote_token_reserves", "u64"),
        ("quote_amount_out", "u64"),
        ("lp_fee_basis_points", "u64"),
        ("lp_fee", "u64"),
        ("protocol_fee_basis_points", "u64"),
        ("protocol_fee", "u64"),
        ("quote_amount_out_without_lp_fee", "u64"),
        ("user_quote_amount_out", "u64"),
        ("pool", "pubkey"),
        ("user", "pubkey"),
        ("user_base_token_account", "pubkey"),
        ("user_quote_token_account", "pubkey"),
        ("protocol_fee_recipient", "pubkey"),
        ("protocol_fee_recipient_token_account", "pubkey"),
        ("coin_creator", "pubkey"),
        ("coin_creator_fee_basis_points", "u64"),
        ("coin_creator_fee", "u64"),
        ("cashback_fee_basis_points", "u64"),
        ("cashback", "u64"),
        ("buyback_fee_basis_points", "u64"),
        ("buyback_fee", "u64"),
        ("virtual_quote_reserves", "i128"),
        ("can_boost", "bool"),
        ("base_supply", "u64"),
    ),
}


class PumpSwapContractError(ValueError):
    """The frozen official PumpSwap subset is malformed or has drifted."""


class PumpSwapDecodeError(PumpSwapContractError):
    """PumpSwap account or event bytes fail the pinned layout."""


class PumpSwapProjectionError(PumpSwapContractError):
    """Decoded Touch evidence cannot fit the canonical schema losslessly."""


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    type_spec: BorshType


@dataclass(frozen=True, slots=True)
class LayoutSchema:
    name: str
    discriminator: bytes
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True, slots=True)
class PumpSwapIdlPlan:
    fixture_sha256: str
    source_commit: str
    source_content_sha256: str
    program_id: str
    pool: LayoutSchema
    events: tuple[LayoutSchema, ...]

    @property
    def event_by_discriminator(self) -> dict[bytes, LayoutSchema]:
        return {event.discriminator: event for event in self.events}


@dataclass(frozen=True, slots=True)
class DecodedPoolAccount:
    account_pubkey: str
    fields: dict[str, JsonValue]
    payload_sha256: str

    @property
    def base_mint(self) -> str:
        return _required_text(self.fields, "base_mint")

    @property
    def quote_mint(self) -> str:
        return _required_text(self.fields, "quote_mint")

    @property
    def virtual_quote_reserves(self) -> int:
        return _required_int(self.fields, "virtual_quote_reserves")

    @property
    def index(self) -> int:
        return _required_int(self.fields, "index")


@dataclass(frozen=True, slots=True)
class DecodedTradeEvent:
    event_name: str
    side: Side
    fields: dict[str, JsonValue]
    payload_sha256: str

    @property
    def pool_id(self) -> str:
        return _required_text(self.fields, "pool")

    @property
    def event_timestamp(self) -> int:
        return _required_int(self.fields, "timestamp")


@dataclass(frozen=True, slots=True)
class PoolTouchProjection:
    pool_snapshot: PoolStateSnapshot
    observations: tuple[CanonicalObservation, ...]
    universe_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TradeTouchProjection:
    pool_snapshot: PoolStateSnapshot
    trade: TradeOrderflowInput
    observations: tuple[CanonicalObservation, ...]
    universe_labels: tuple[str, ...]


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PumpSwapContractError(f"{name}_must_be_mapping")
    if not all(isinstance(key, str) for key in value):
        raise PumpSwapContractError(f"{name}_keys_must_be_text")
    return value


def _sequence(name: str, value: object) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PumpSwapContractError(f"{name}_must_be_sequence")
    return value


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PumpSwapContractError(f"{name}_must_be_nonempty_text")
    return value


def _exact(name: str, value: object, expected: object) -> None:
    if value != expected:
        raise PumpSwapContractError(f"{name}_drift")


def _required_text(fields: Mapping[str, JsonValue], name: str) -> str:
    value = fields.get(name)
    if not isinstance(value, str) or not value:
        raise PumpSwapDecodeError(f"decoded_{name}_invalid")
    return value


def _required_int(fields: Mapping[str, JsonValue], name: str) -> int:
    value = fields.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PumpSwapDecodeError(f"decoded_{name}_invalid")
    return value


def _compile_fields(name: str, value: object) -> tuple[FieldSpec, ...]:
    fields: list[FieldSpec] = []
    for index, item in enumerate(_sequence(name, value)):
        row = _mapping(f"{name}_{index}", item)
        _exact(f"{name}_{index}_keys", set(row), {"name", "type"})
        type_spec = _text(f"{name}_{index}_type", row["type"])
        if type_spec not in {
            "bool",
            "i64",
            "i128",
            "pubkey",
            "string",
            "u8",
            "u16",
            "u64",
        }:
            raise PumpSwapContractError(
                f"{name}_{index}_unsupported_type:{type_spec}"
            )
        fields.append(
            FieldSpec(
                name=_text(f"{name}_{index}_name", row["name"]),
                type_spec=type_spec,
            )
        )
    if len({field.name for field in fields}) != len(fields):
        raise PumpSwapContractError(f"{name}_duplicate_field")
    return tuple(fields)


def _compile_layout(name: str, value: object) -> LayoutSchema:
    row = _mapping(name, value)
    _exact(f"{name}_keys", set(row), {"name", "discriminator", "fields"})
    layout_name = _text(f"{name}_name", row["name"])
    if layout_name not in _EXPECTED_DISCRIMINATORS:
        raise PumpSwapContractError(f"unexpected_layout:{layout_name}")
    values = _sequence(f"{layout_name}_discriminator", row["discriminator"])
    if (
        len(values) != 8
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= 255
            for value in values
        )
    ):
        raise PumpSwapContractError(f"{layout_name}_discriminator_invalid")
    discriminator = bytes(values)
    _exact(
        f"{layout_name}_discriminator",
        discriminator,
        _EXPECTED_DISCRIMINATORS[layout_name],
    )
    fields = _compile_fields(f"{layout_name}_fields", row["fields"])
    _exact(
        f"{layout_name}_field_layout",
        tuple((field.name, field.type_spec) for field in fields),
        _EXPECTED_FIELDS[layout_name],
    )
    return LayoutSchema(
        name=layout_name,
        discriminator=discriminator,
        fields=fields,
    )


def compile_pumpswap_idl_subset(
    document: Mapping[str, Any],
    *,
    fixture_sha256: str = FROZEN_PUMPSWAP_SUBSET_SHA256,
) -> PumpSwapIdlPlan:
    """Compile the exact official Pool/BuyEvent/SellEvent subset."""

    root = _mapping("pumpswap_subset", document)
    _exact("top_level_keys", set(root), _TOP_LEVEL_KEYS)
    _exact("schema", root["schema"], "solana_alpha_lab.pumpswap_idl_subset")
    _exact("schema_version", root["schema_version"], "1.0")
    _exact("as_of", root["as_of"], "2026-07-27")
    _exact("status", root["status"], "PINNED_OFFICIAL_SUBSET")
    _exact("source", root["source"], _SOURCE)
    _exact("program_id", root["program_id"], PUMPSWAP_PROGRAM_ID)

    accounts = _sequence("accounts", root["accounts"])
    _exact("account_count", len(accounts), 1)
    pool = _compile_layout("account_0", accounts[0])
    _exact("account_inventory", pool.name, "Pool")

    events = tuple(
        _compile_layout(f"event_{index}", item)
        for index, item in enumerate(_sequence("events", root["events"]))
    )
    _exact(
        "event_inventory",
        tuple(event.name for event in events),
        ("BuyEvent", "SellEvent"),
    )
    if len({event.discriminator for event in events}) != len(events):
        raise PumpSwapContractError("event_discriminator_collision")
    return PumpSwapIdlPlan(
        fixture_sha256=fixture_sha256,
        source_commit=PUMPSWAP_IDL_COMMIT,
        source_content_sha256=PUMPSWAP_IDL_SHA256,
        program_id=PUMPSWAP_PROGRAM_ID,
        pool=pool,
        events=events,
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise PumpSwapContractError(f"duplicate_json_key:{key}")
        document[key] = value
    return document


def load_pinned_pumpswap_plan(path: Path) -> PumpSwapIdlPlan:
    """Verify exact fixture bytes before compiling the pinned subset."""

    payload = path.read_bytes()
    observed_hash = hashlib.sha256(payload).hexdigest()
    if observed_hash != FROZEN_PUMPSWAP_SUBSET_SHA256:
        raise PumpSwapContractError(
            f"pumpswap_subset_hash_mismatch:{observed_hash}"
        )
    try:
        document = json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PumpSwapContractError("pumpswap_subset_invalid_json") from exc
    return compile_pumpswap_idl_subset(
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
            raise PumpSwapDecodeError("borsh_payload_truncated")
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


def _decode_type(reader: _BorshReader, type_spec: BorshType) -> JsonValue:
    if type_spec == "bool":
        value = reader.unsigned(1)
        if value not in {0, 1}:
            raise PumpSwapDecodeError("borsh_bool_invalid")
        return bool(value)
    if type_spec == "i64":
        return reader.signed(8)
    if type_spec == "i128":
        return reader.signed(16)
    if type_spec == "pubkey":
        return _base58_encode(reader.take(32))
    if type_spec == "string":
        length = reader.unsigned(4)
        if length > MAX_STRING_BYTES:
            raise PumpSwapDecodeError("borsh_string_too_large")
        try:
            return reader.take(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PumpSwapDecodeError("borsh_string_invalid_utf8") from exc
    if type_spec == "u8":
        return reader.unsigned(1)
    if type_spec == "u16":
        return reader.unsigned(2)
    if type_spec == "u64":
        return reader.unsigned(8)
    raise PumpSwapDecodeError(f"borsh_type_unsupported:{type_spec}")


def _decode_layout(payload: bytes, schema: LayoutSchema) -> dict[str, JsonValue]:
    if len(payload) < 8:
        raise PumpSwapDecodeError("payload_missing_discriminator")
    if payload[:8] != schema.discriminator:
        raise PumpSwapDecodeError(f"{schema.name}_discriminator_mismatch")
    reader = _BorshReader(payload[8:])
    fields = {
        field.name: _decode_type(reader, field.type_spec)
        for field in schema.fields
    }
    if reader.remaining:
        raise PumpSwapDecodeError("borsh_payload_trailing_bytes")
    return fields


def decode_pumpswap_pool_account(
    plan: PumpSwapIdlPlan,
    *,
    account_data: bytes,
    account_pubkey: str,
    owner_program_id: str,
) -> DecodedPoolAccount:
    """Decode one exact PumpSwap Pool account without reading token balances."""

    if owner_program_id != plan.program_id:
        raise PumpSwapDecodeError("pool_owner_program_id_mismatch")
    if not isinstance(account_data, bytes):
        raise PumpSwapDecodeError("pool_account_data_must_be_bytes")
    fields = _decode_layout(account_data, plan.pool)
    decoded = DecodedPoolAccount(
        account_pubkey=_text("account_pubkey", account_pubkey),
        fields=fields,
        payload_sha256=hashlib.sha256(account_data).hexdigest(),
    )
    if decoded.base_mint == decoded.quote_mint:
        raise PumpSwapDecodeError("pool_mints_must_differ")
    if (
        _required_text(fields, "pool_base_token_account")
        == _required_text(fields, "pool_quote_token_account")
    ):
        raise PumpSwapDecodeError("pool_token_accounts_must_differ")
    return decoded


def decode_pumpswap_program_data(
    plan: PumpSwapIdlPlan,
    *,
    log_line: str,
    emitting_program_id: str,
    transaction_succeeded: bool,
) -> DecodedTradeEvent | None:
    """Decode one successful PumpSwap BuyEvent/SellEvent Anchor log."""

    if not transaction_succeeded:
        return None
    if emitting_program_id != plan.program_id:
        raise PumpSwapDecodeError("emitting_program_id_mismatch")
    if not isinstance(log_line, str) or not log_line.startswith(PROGRAM_DATA_PREFIX):
        raise PumpSwapDecodeError("program_data_prefix_invalid")
    encoded = log_line[len(PROGRAM_DATA_PREFIX) :]
    if not encoded or encoded.strip() != encoded:
        raise PumpSwapDecodeError("program_data_base64_not_canonical")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PumpSwapDecodeError("program_data_base64_invalid") from exc
    if len(payload) < 8:
        raise PumpSwapDecodeError("event_payload_missing_discriminator")
    if len(payload) > MAX_EVENT_PAYLOAD_BYTES:
        raise PumpSwapDecodeError("event_payload_too_large")
    schema = plan.event_by_discriminator.get(payload[:8])
    if schema is None:
        raise PumpSwapDecodeError("event_discriminator_unknown")
    fields = _decode_layout(payload, schema)
    decoded = DecodedTradeEvent(
        event_name=schema.name,
        side=Side.BUY if schema.name == "BuyEvent" else Side.SELL,
        fields=fields,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
    )
    decoded.pool_id
    decoded.event_timestamp
    return decoded


def effective_quote_reserves(
    *,
    raw_quote_reserve_atomic: int,
    virtual_quote_reserves_atomic: int,
) -> int:
    """Return lossless effective reserves or block canonicalization."""

    if (
        isinstance(raw_quote_reserve_atomic, bool)
        or not isinstance(raw_quote_reserve_atomic, int)
        or not 0 <= raw_quote_reserve_atomic <= U64_MAX
    ):
        raise PumpSwapProjectionError("raw_quote_reserve_out_of_range")
    if (
        isinstance(virtual_quote_reserves_atomic, bool)
        or not isinstance(virtual_quote_reserves_atomic, int)
        or not I128_MIN <= virtual_quote_reserves_atomic <= I128_MAX
    ):
        raise PumpSwapProjectionError("virtual_quote_reserve_out_of_range")
    effective = raw_quote_reserve_atomic + virtual_quote_reserves_atomic
    if not 0 <= effective <= U64_MAX:
        raise PumpSwapProjectionError("effective_quote_reserve_not_representable")
    return effective


def _as_utc(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise PumpSwapProjectionError(f"{name}_must_be_timezone_aware")
    return value.astimezone(timezone.utc)


def _validate_time_order(
    *,
    event_time: datetime,
    observed_at: datetime,
    first_reliable_available_at: datetime,
    available_at: datetime,
    ingested_at: datetime,
) -> tuple[datetime, datetime, datetime, datetime, datetime]:
    values = tuple(
        _as_utc(name, value)
        for name, value in (
            ("event_time", event_time),
            ("observed_at", observed_at),
            ("first_reliable_available_at", first_reliable_available_at),
            ("available_at", available_at),
            ("ingested_at", ingested_at),
        )
    )
    if tuple(sorted(values)) != values:
        raise PumpSwapProjectionError("timestamp_order_invalid")
    return values


def _stable_hash(*parts: object) -> str:
    payload = json.dumps(
        parts,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _observation(
    *,
    identity: str,
    pool_id: str,
    observation_type: str,
    value_decimal: Decimal | None,
    value_atomic: int | None,
    unit: str,
    amount_mint: str | None,
    amount_decimals: int | None,
    event_time: datetime,
    observed_at: datetime,
    available_at: datetime,
    ingested_at: datetime,
    first_reliable_available_at: datetime,
    source: str,
    source_version: str,
    raw_event_id: str,
    quality_flags: str | None,
) -> CanonicalObservation:
    digest = _stable_hash(identity, observation_type)
    return CanonicalObservation(
        observation_id=f"obs-t09-{digest}",
        idempotency_key=digest,
        business_key=f"{pool_id}:{observation_type}:{identity}",
        entity_type="PUMPSWAP_POOL",
        entity_id=pool_id,
        observation_type=observation_type,
        value_decimal=value_decimal,
        value_atomic=value_atomic,
        unit=unit,
        amount_mint=amount_mint,
        amount_decimals=amount_decimals,
        event_time=event_time,
        observed_at=observed_at,
        available_to_strategy_at=available_at,
        ingested_at=ingested_at,
        first_reliable_available_at=first_reliable_available_at,
        source=source,
        source_version=source_version,
        schema_version="1.0",
        revision_number=1,
        revision_of=None,
        raw_event_id=raw_event_id,
        content_sha256=_stable_hash(
            identity,
            observation_type,
            str(value_decimal) if value_decimal is not None else None,
            value_atomic,
            unit,
        ),
        quality_flags=quality_flags,
    )


def _pool_snapshot(
    *,
    identity: str,
    pool_id: str,
    base_mint: str,
    quote_mint: str,
    base_decimals: int,
    quote_decimals: int,
    base_reserve_atomic: int,
    quote_reserve_atomic: int,
    context_slot: int,
    event_time: datetime,
    observed_at: datetime,
    available_at: datetime,
    ingested_at: datetime,
    first_reliable_available_at: datetime,
    source: str,
    source_version: str,
    raw_event_id: str,
    quality_flags: str | None,
) -> PoolStateSnapshot:
    digest = _stable_hash(identity, "pool_state_snapshot")
    return PoolStateSnapshot(
        pool_snapshot_id=f"pool-snapshot-t09-{digest}",
        idempotency_key=digest,
        business_key=f"{pool_id}:{context_slot}:{identity}",
        pool_id=pool_id,
        base_mint=base_mint,
        quote_mint=quote_mint,
        base_decimals=base_decimals,
        quote_decimals=quote_decimals,
        base_reserve_atomic=base_reserve_atomic,
        quote_reserve_atomic=quote_reserve_atomic,
        context_slot=context_slot,
        event_time=event_time,
        observed_at=observed_at,
        available_to_strategy_at=available_at,
        ingested_at=ingested_at,
        first_reliable_available_at=first_reliable_available_at,
        source=source,
        source_version=source_version,
        schema_version="1.0",
        revision_number=1,
        revision_of=None,
        raw_event_id=raw_event_id,
        content_sha256=_stable_hash(
            identity,
            base_reserve_atomic,
            quote_reserve_atomic,
        ),
        quality_flags=quality_flags,
    )


def project_pool_touch(
    decoded: DecodedPoolAccount,
    *,
    raw_base_reserve_atomic: int,
    raw_quote_reserve_atomic: int,
    base_decimals: int,
    quote_decimals: int,
    context_slot: int,
    event_time: datetime,
    observed_at: datetime,
    first_reliable_available_at: datetime,
    available_at: datetime,
    ingested_at: datetime,
    raw_event_id: str,
    source: str = "SOLANA_RPC",
    source_version: str = PUMPSWAP_IDL_COMMIT,
) -> PoolTouchProjection:
    """Project a Pool account plus raw vault balances without reserve substitution."""

    event_time, observed_at, first_reliable_available_at, available_at, ingested_at = (
        _validate_time_order(
            event_time=event_time,
            observed_at=observed_at,
            first_reliable_available_at=first_reliable_available_at,
            available_at=available_at,
            ingested_at=ingested_at,
        )
    )
    effective = effective_quote_reserves(
        raw_quote_reserve_atomic=raw_quote_reserve_atomic,
        virtual_quote_reserves_atomic=decoded.virtual_quote_reserves,
    )
    identity = _stable_hash(decoded.payload_sha256, context_slot, raw_event_id)
    quality_flags = "TOUCH_ONLY;CANONICAL_INDEX_CANDIDATE" if decoded.index == 0 else "TOUCH_ONLY"
    snapshot = _pool_snapshot(
        identity=identity,
        pool_id=decoded.account_pubkey,
        base_mint=decoded.base_mint,
        quote_mint=decoded.quote_mint,
        base_decimals=base_decimals,
        quote_decimals=quote_decimals,
        base_reserve_atomic=raw_base_reserve_atomic,
        quote_reserve_atomic=raw_quote_reserve_atomic,
        context_slot=context_slot,
        event_time=event_time,
        observed_at=observed_at,
        available_at=available_at,
        ingested_at=ingested_at,
        first_reliable_available_at=first_reliable_available_at,
        source=source,
        source_version=source_version,
        raw_event_id=raw_event_id,
        quality_flags=quality_flags,
    )
    observations = (
        _observation(
            identity=identity,
            pool_id=decoded.account_pubkey,
            observation_type="virtual_quote_reserves_atomic",
            value_decimal=Decimal(decoded.virtual_quote_reserves),
            value_atomic=None,
            unit=f"signed_atomic:{decoded.quote_mint}:{quote_decimals}",
            amount_mint=None,
            amount_decimals=None,
            event_time=event_time,
            observed_at=observed_at,
            available_at=available_at,
            ingested_at=ingested_at,
            first_reliable_available_at=first_reliable_available_at,
            source=source,
            source_version=source_version,
            raw_event_id=raw_event_id,
            quality_flags=quality_flags,
        ),
        _observation(
            identity=identity,
            pool_id=decoded.account_pubkey,
            observation_type="effective_quote_reserves_atomic",
            value_decimal=None,
            value_atomic=effective,
            unit="atomic",
            amount_mint=decoded.quote_mint,
            amount_decimals=quote_decimals,
            event_time=event_time,
            observed_at=observed_at,
            available_at=available_at,
            ingested_at=ingested_at,
            first_reliable_available_at=first_reliable_available_at,
            source=source,
            source_version=source_version,
            raw_event_id=raw_event_id,
            quality_flags=quality_flags,
        ),
    )
    labels = ("PUMPSWAP_OBSERVED",)
    if decoded.index == 0:
        labels += ("CANONICAL_INDEX_CANDIDATE",)
    return PoolTouchProjection(
        pool_snapshot=snapshot,
        observations=observations,
        universe_labels=labels,
    )


_FEE_FIELDS = (
    ("lp_fee_basis_points", "lp_fee_bps", "BPS"),
    ("lp_fee", "lp_fee_atomic", "ATOMIC"),
    ("protocol_fee_basis_points", "protocol_fee_bps", "BPS"),
    ("protocol_fee", "protocol_fee_atomic", "ATOMIC"),
    ("coin_creator_fee_basis_points", "coin_creator_fee_bps", "BPS"),
    ("coin_creator_fee", "coin_creator_fee_atomic", "ATOMIC"),
    ("cashback_fee_basis_points", "cashback_fee_bps", "BPS"),
    ("cashback", "cashback_atomic", "ATOMIC"),
    ("buyback_fee_basis_points", "buyback_fee_bps", "BPS"),
    ("buyback_fee", "buyback_fee_atomic", "ATOMIC"),
)


def project_trade_touch(
    decoded: DecodedTradeEvent,
    *,
    pool: DecodedPoolAccount,
    base_decimals: int,
    quote_decimals: int,
    transaction_signature: str,
    instruction_index: int,
    event_index: int,
    context_slot: int,
    observed_at: datetime,
    first_reliable_available_at: datetime,
    available_at: datetime,
    ingested_at: datetime,
    raw_event_id: str,
    source: str = "SOLANA_LOGS_SUBSCRIBE",
    source_version: str = PUMPSWAP_IDL_COMMIT,
) -> TradeTouchProjection:
    """Project one successful observed trade without claiming our fill or route."""

    if decoded.pool_id != pool.account_pubkey:
        raise PumpSwapProjectionError("trade_pool_context_mismatch")
    try:
        event_time = datetime.fromtimestamp(decoded.event_timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise PumpSwapProjectionError("event_timestamp_out_of_range") from exc
    event_time, observed_at, first_reliable_available_at, available_at, ingested_at = (
        _validate_time_order(
            event_time=event_time,
            observed_at=observed_at,
            first_reliable_available_at=first_reliable_available_at,
            available_at=available_at,
            ingested_at=ingested_at,
        )
    )
    fields = decoded.fields
    raw_base = _required_int(fields, "pool_base_token_reserves")
    raw_quote = _required_int(fields, "pool_quote_token_reserves")
    virtual = _required_int(fields, "virtual_quote_reserves")
    effective = effective_quote_reserves(
        raw_quote_reserve_atomic=raw_quote,
        virtual_quote_reserves_atomic=virtual,
    )
    if decoded.side == Side.BUY:
        input_mint = pool.quote_mint
        input_amount = _required_int(fields, "user_quote_amount_in")
        input_decimals = quote_decimals
        output_mint = pool.base_mint
        output_amount = _required_int(fields, "base_amount_out")
        output_decimals = base_decimals
    else:
        input_mint = pool.base_mint
        input_amount = _required_int(fields, "base_amount_in")
        input_decimals = base_decimals
        output_mint = pool.quote_mint
        output_amount = _required_int(fields, "user_quote_amount_out")
        output_decimals = quote_decimals

    identity = _stable_hash(
        decoded.payload_sha256,
        transaction_signature,
        instruction_index,
        event_index,
        context_slot,
    )
    quality_flags = "TOUCH_ONLY;OBSERVED_TRADE_NOT_OUR_FILL"
    snapshot = _pool_snapshot(
        identity=identity,
        pool_id=pool.account_pubkey,
        base_mint=pool.base_mint,
        quote_mint=pool.quote_mint,
        base_decimals=base_decimals,
        quote_decimals=quote_decimals,
        base_reserve_atomic=raw_base,
        quote_reserve_atomic=raw_quote,
        context_slot=context_slot,
        event_time=event_time,
        observed_at=observed_at,
        available_at=available_at,
        ingested_at=ingested_at,
        first_reliable_available_at=first_reliable_available_at,
        source=source,
        source_version=source_version,
        raw_event_id=raw_event_id,
        quality_flags=quality_flags,
    )
    trade_digest = _stable_hash(identity, "trade_orderflow_input")
    trade = TradeOrderflowInput(
        trade_input_id=f"trade-input-t09-{trade_digest}",
        idempotency_key=trade_digest,
        business_key=(
            f"{transaction_signature}:{instruction_index}:{event_index}"
        ),
        pool_id=pool.account_pubkey,
        side=decoded.side,
        input_mint=input_mint,
        input_amount_atomic=input_amount,
        input_decimals=input_decimals,
        output_mint=output_mint,
        output_amount_atomic=output_amount,
        output_decimals=output_decimals,
        trader_entity_id=_required_text(fields, "user"),
        transaction_signature=transaction_signature,
        context_slot=context_slot,
        event_time=event_time,
        observed_at=observed_at,
        available_to_strategy_at=available_at,
        ingested_at=ingested_at,
        first_reliable_available_at=first_reliable_available_at,
        source=source,
        source_version=source_version,
        schema_version="1.0",
        revision_number=1,
        revision_of=None,
        raw_event_id=raw_event_id,
        content_sha256=_stable_hash(identity, input_amount, output_amount),
        quality_flags=quality_flags,
    )
    observations: list[CanonicalObservation] = [
        _observation(
            identity=identity,
            pool_id=pool.account_pubkey,
            observation_type="virtual_quote_reserves_atomic",
            value_decimal=Decimal(virtual),
            value_atomic=None,
            unit=f"signed_atomic:{pool.quote_mint}:{quote_decimals}",
            amount_mint=None,
            amount_decimals=None,
            event_time=event_time,
            observed_at=observed_at,
            available_at=available_at,
            ingested_at=ingested_at,
            first_reliable_available_at=first_reliable_available_at,
            source=source,
            source_version=source_version,
            raw_event_id=raw_event_id,
            quality_flags=quality_flags,
        ),
        _observation(
            identity=identity,
            pool_id=pool.account_pubkey,
            observation_type="effective_quote_reserves_atomic",
            value_decimal=None,
            value_atomic=effective,
            unit="atomic",
            amount_mint=pool.quote_mint,
            amount_decimals=quote_decimals,
            event_time=event_time,
            observed_at=observed_at,
            available_at=available_at,
            ingested_at=ingested_at,
            first_reliable_available_at=first_reliable_available_at,
            source=source,
            source_version=source_version,
            raw_event_id=raw_event_id,
            quality_flags=quality_flags,
        ),
    ]
    for source_field, observation_type, mode in _FEE_FIELDS:
        value = _required_int(fields, source_field)
        observations.append(
            _observation(
                identity=identity,
                pool_id=pool.account_pubkey,
                observation_type=observation_type,
                value_decimal=Decimal(value) if mode == "BPS" else None,
                value_atomic=value if mode == "ATOMIC" else None,
                unit="basis_points" if mode == "BPS" else "atomic",
                amount_mint=pool.quote_mint if mode == "ATOMIC" else None,
                amount_decimals=quote_decimals if mode == "ATOMIC" else None,
                event_time=event_time,
                observed_at=observed_at,
                available_at=available_at,
                ingested_at=ingested_at,
                first_reliable_available_at=first_reliable_available_at,
                source=source,
                source_version=source_version,
                raw_event_id=raw_event_id,
                quality_flags=quality_flags,
            )
        )
    return TradeTouchProjection(
        pool_snapshot=snapshot,
        trade=trade,
        observations=tuple(observations),
        universe_labels=("PUMPSWAP_OBSERVED",),
    )
