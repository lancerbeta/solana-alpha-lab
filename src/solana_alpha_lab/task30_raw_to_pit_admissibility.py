"""Offline A22+A23 raw-to-PIT admissibility panel for TASK-30 A24."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from solana_alpha_lab.pumpswap_touch_decoder import (
    PUMPSWAP_PROGRAM_ID,
    load_pinned_pumpswap_plan,
)
from solana_alpha_lab.pumpswap_touch_probe import (
    TouchProtocolDriftError,
    attribute_pumpswap_program_data_logs,
)
from solana_alpha_lab.task28_rc001_registry_freeze import canonical_definition_hash

ATOM_ID = "T30-A24_RAW_TO_PIT_ADMISSIBILITY_OWNER_PANEL_V1"
SCHEMA = "smial.task30.raw-to-pit-admissibility-owner-panel.policy"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ANCHOR_EVENT_CPI = bytes.fromhex("e445a52e51cb9a1d")
SLOT_STATES = (
    "OBSERVED_TARGET_TRADES",
    "PROVEN_NO_TARGET_TRADE",
    "STATE_PERSISTENCE_PROVEN",
    "UNKNOWN_COVERAGE",
)
TERMINAL_OUTCOMES = (
    "LIMITED_DIAGNOSTIC_PANEL_READY",
    "TARGETED_PROVIDER_CAPABILITY_GAP_PROVEN",
    "REDESIGN_DATA",
    "STOP_INTEGRITY_CONFLICT",
)


class A24Error(ValueError):
    """Policy, input or projection identity is invalid."""


class A24IntegrityError(A24Error):
    """Retained bytes cannot be reconciled without inventing observations."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A24Error(code)


def _integrity(condition: bool, code: str) -> None:
    if not condition:
        raise A24IntegrityError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _text(value: object, code: str) -> str:
    _require(isinstance(value, str) and bool(value), code)
    return value


def _int(value: object, code: str) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), code)
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None, "TIMESTAMP_INVALID")
    return parsed.astimezone(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _anchor_ix(name: str) -> str:
    return hashlib.sha256(f"global:{name}".encode("utf-8")).digest()[:8].hex()


def _anchor_event(name: str) -> str:
    return hashlib.sha256(f"event:{name}".encode("utf-8")).digest()[:8].hex()


def _b58decode(value: str) -> bytes:
    number = 0
    try:
        for character in value:
            number = number * 58 + BASE58_ALPHABET.index(character)
    except ValueError as exc:
        raise A24IntegrityError("INSTRUCTION_DATA_BASE58_INVALID") from exc
    payload = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\x00" * (len(value) - len(value.lstrip("1"))) + payload


def load_policy(path: Path) -> dict[str, Any]:
    import yaml

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    policy = dict(_mapping(document, "POLICY_INVALID"))
    _require(policy.get("schema") == SCHEMA, "POLICY_SCHEMA_DRIFT")
    _require(policy.get("schema_version") == "1.0", "POLICY_VERSION_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "POLICY_ATOM_DRIFT")
    discs = _mapping(policy.get("instruction_discriminators"), "IX_DISC_INVALID")
    expected = {
        "buy": _anchor_ix("buy"),
        "buy_exact_quote_in": _anchor_ix("buy_exact_quote_in"),
        "sell": _anchor_ix("sell"),
        "close_user_volume_accumulator": _anchor_ix("close_user_volume_accumulator"),
        "anchor_self_cpi_event": ANCHOR_EVENT_CPI.hex(),
    }
    for name, digest in expected.items():
        _require(discs.get(name) == digest, f"IX_DISC_DRIFT:{name}")
    events = _mapping(policy.get("non_market_events"), "NON_MARKET_INVALID")
    close = _mapping(
        events.get("CloseUserVolumeAccumulatorEvent"),
        "CLOSE_EVENT_INVALID",
    )
    _require(
        close.get("discriminator_hex")
        == _anchor_event("CloseUserVolumeAccumulatorEvent"),
        "CLOSE_EVENT_IDL_BINDING_DRIFT",
    )
    return policy


def verify_frozen_definition(repo_root: Path, policy: Mapping[str, Any]) -> None:
    import yaml

    frozen = _mapping(policy.get("frozen_definition"), "FROZEN_DEFINITION_INVALID")
    path = repo_root / _text(frozen.get("path"), "FROZEN_DEFINITION_PATH")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    groups = _mapping(document, "RC001_FREEZE_INVALID").get("hypothesis_groups")
    _require(isinstance(groups, list), "RC001_GROUPS_INVALID")
    match = None
    for group in groups:
        mapped = _mapping(group, "RC001_GROUP_INVALID")
        if mapped.get("group_id") == frozen.get("group_id"):
            match = mapped
            break
    _require(match is not None, "RC001_GROUP_MISSING")
    _require(
        match.get("definition_sha256") == frozen.get("definition_sha256"),
        "RC001_DEFINITION_DRIFT",
    )
    _require(
        canonical_definition_hash(match) == frozen.get("definition_sha256"),
        "RC001_CANONICAL_HASH_DRIFT",
    )
    _require(
        frozen.get("group_id") == "RC001-H07-H01-LIQUIDITY-RETENTION",
        "RC001_GROUP_DRIFT",
    )


def _page_rows(payload: bytes, *, expected_id: str | None = None) -> tuple[list[Any], Any]:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise A24Error("RAW_JSON_INVALID") from exc
    parsed = _mapping(document, "RAW_JSON_INVALID")
    _require(parsed.get("jsonrpc") == "2.0", "RAW_JSONRPC_DRIFT")
    if expected_id is not None:
        _require(parsed.get("id") == expected_id, "RAW_REQUEST_ID_DRIFT")
    result = _mapping(parsed.get("result"), "RAW_RESULT_INVALID")
    data = result.get("data")
    _require(isinstance(data, list), "RAW_DATA_INVALID")
    return list(data), result.get("paginationToken")


def verify_input_identity(
    policy: Mapping[str, Any],
    *,
    a22_payload: bytes,
    a23_payload: bytes,
) -> dict[str, Any]:
    bindings = _mapping(policy.get("input_bindings"), "INPUT_BINDINGS_INVALID")
    a22 = _mapping(bindings.get("a22_raw"), "A22_BINDING_INVALID")
    a23 = _mapping(bindings.get("a23_terminal_page"), "A23_BINDING_INVALID")
    _integrity(sha256_bytes(a22_payload) == a22.get("sha256"), "A22_HASH_DRIFT")
    _integrity(len(a22_payload) == a22.get("bytes"), "A22_BYTES_DRIFT")
    _integrity(sha256_bytes(a23_payload) == a23.get("sha256"), "A23_HASH_DRIFT")
    _integrity(len(a23_payload) == a23.get("bytes"), "A23_BYTES_DRIFT")
    rows, cursor = _page_rows(a22_payload)
    _integrity(len(rows) == 520, "A22_ROW_COUNT_DRIFT")
    _integrity(cursor is not None and cursor != "", "A22_CURSOR_MISSING")
    terminal_rows, terminal_cursor = _page_rows(a23_payload)
    _integrity(terminal_rows == [], "A23_TERMINAL_ROWS_DRIFT")
    _integrity(terminal_cursor is None, "A23_TERMINAL_CURSOR_DRIFT")
    _integrity(a23.get("expected_rows") == 0, "A23_EXPECTED_ROWS_DRIFT")
    _integrity(a23.get("expected_cursor") is None, "A23_EXPECTED_CURSOR_DRIFT")
    return {
        "a22_sha256": a22["sha256"],
        "a23_sha256": a23["sha256"],
        "transaction_count": len(rows),
        "terminal_cursor": None,
        "a22_ingested_at": a22["ingested_at"],
        "completeness_available_at": a23["completeness_available_at"],
        "rows": rows,
    }


def _resolved_keys(row: Mapping[str, Any]) -> list[str]:
    transaction = _mapping(row.get("transaction"), "TRANSACTION_INVALID")
    message = _mapping(transaction.get("message"), "MESSAGE_INVALID")
    meta = _mapping(row.get("meta"), "META_INVALID")
    account_keys = message.get("accountKeys")
    _require(
        isinstance(account_keys, Sequence) and not isinstance(account_keys, (str, bytes)),
        "ACCOUNT_KEYS_INVALID",
    )
    loaded = meta.get("loadedAddresses") or {}
    loaded_map = _mapping(loaded, "LOADED_ADDRESSES_INVALID")
    keys = [str(item) for item in account_keys]
    for mode in ("writable", "readonly"):
        values = loaded_map.get(mode) or []
        _require(
            isinstance(values, Sequence) and not isinstance(values, (str, bytes)),
            "LOADED_ADDRESSES_INVALID",
        )
        keys.extend(str(item) for item in values)
    return keys


def _instruction_program(keys: Sequence[str], instruction: Mapping[str, Any]) -> str:
    index = _int(instruction.get("programIdIndex"), "PROGRAM_ID_INDEX_INVALID")
    _require(0 <= index < len(keys), "PROGRAM_ID_INDEX_RANGE")
    return keys[index]


def _instruction_disc(instruction: Mapping[str, Any]) -> str:
    data = instruction.get("data") or ""
    _require(isinstance(data, str), "INSTRUCTION_DATA_INVALID")
    if not data:
        raise A24IntegrityError("INSTRUCTION_DATA_EMPTY")
    payload = _b58decode(data)
    _require(len(payload) >= 8, "INSTRUCTION_DISCRIMINATOR_MISSING")
    return payload[:8].hex()


def _iter_pumpswap_instructions(
    row: Mapping[str, Any],
    *,
    program_id: str,
) -> list[tuple[str, str]]:
    keys = _resolved_keys(row)
    found: list[tuple[str, str]] = []
    message = _mapping(
        _mapping(row.get("transaction"), "TRANSACTION_INVALID").get("message"),
        "MESSAGE_INVALID",
    )
    for instruction in message.get("instructions") or []:
        mapped = _mapping(instruction, "INSTRUCTION_INVALID")
        if _instruction_program(keys, mapped) == program_id:
            found.append(("outer", _instruction_disc(mapped)))
    meta = _mapping(row.get("meta"), "META_INVALID")
    for group in meta.get("innerInstructions") or []:
        mapped_group = _mapping(group, "INNER_GROUP_INVALID")
        for instruction in mapped_group.get("instructions") or []:
            mapped = _mapping(instruction, "INNER_INSTRUCTION_INVALID")
            if _instruction_program(keys, mapped) == program_id:
                found.append(("inner", _instruction_disc(mapped)))
    return found


def _classify_ix(
    digest: str,
    *,
    discs: Mapping[str, str],
    close_event_hex: str,
) -> str:
    if digest == discs["buy"]:
        return "buy"
    if digest == discs["buy_exact_quote_in"]:
        return "buy_exact_quote_in"
    if digest == discs["sell"]:
        return "sell"
    if digest == discs["close_user_volume_accumulator"]:
        return "close_user_volume_accumulator"
    if digest == discs["anchor_self_cpi_event"]:
        return "anchor_self_cpi_event"
    raise A24IntegrityError(f"UNKNOWN_MARKET_DISCRIMINATOR:{digest}")


def _token_decimals(row: Mapping[str, Any], mint: str) -> set[int]:
    observed: set[int] = set()
    meta = _mapping(row.get("meta"), "META_INVALID")
    for name in ("preTokenBalances", "postTokenBalances"):
        for item in meta.get(name) or []:
            mapped = _mapping(item, "TOKEN_BALANCE_INVALID")
            if mapped.get("mint") != mint:
                continue
            amount = _mapping(mapped.get("uiTokenAmount"), "TOKEN_AMOUNT_INVALID")
            observed.add(_int(amount.get("decimals"), "TOKEN_DECIMALS_INVALID"))
    return observed


@dataclass(frozen=True, slots=True)
class TargetTrade:
    signature: str
    slot: int
    transaction_index: int
    block_time: int
    event_at: datetime
    side: str
    pool_id: str
    base_amount_atomic: int
    quote_amount_atomic: int
    raw_base_reserve_atomic: int
    raw_quote_reserve_atomic: int
    virtual_quote_reserves: int
    price_quote_per_base: str
    logs_truncated: bool
    payload_sha256: str


def _trade_price(
    *,
    base_atomic: int,
    quote_atomic: int,
    base_decimals: int,
    quote_decimals: int,
) -> str:
    try:
        base = Decimal(base_atomic) / (Decimal(10) ** base_decimals)
        quote = Decimal(quote_atomic) / (Decimal(10) ** quote_decimals)
        if base <= 0:
            raise A24IntegrityError("TRADE_BASE_AMOUNT_NON_POSITIVE")
        return format(quote / base, "f")
    except (InvalidOperation, ZeroDivisionError) as exc:
        raise A24IntegrityError("TRADE_PRICE_INVALID") from exc


def reconcile_batch(
    policy: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    plan: Any,
) -> dict[str, Any]:
    subject = _mapping(policy.get("reference_subject"), "SUBJECT_INVALID")
    window = _mapping(policy.get("pilot_window"), "WINDOW_INVALID")
    discs = _mapping(policy.get("instruction_discriminators"), "IX_DISC_INVALID")
    close_hex = _text(
        _mapping(
            _mapping(policy.get("non_market_events"), "NON_MARKET_INVALID").get(
                "CloseUserVolumeAccumulatorEvent"
            ),
            "CLOSE_EVENT_INVALID",
        ).get("discriminator_hex"),
        "CLOSE_EVENT_HEX_INVALID",
    )
    target_pool = _text(subject.get("pool_address"), "POOL_INVALID")
    program_id = _text(subject.get("program_address"), "PROGRAM_INVALID")
    _require(program_id == PUMPSWAP_PROGRAM_ID, "PROGRAM_DRIFT")
    base_mint = _text(subject.get("base_mint"), "BASE_MINT_INVALID")
    quote_mint = _text(subject.get("quote_mint"), "QUOTE_MINT_INVALID")
    base_decimals = _int(subject.get("base_decimals"), "BASE_DECIMALS_INVALID")
    quote_decimals = _int(subject.get("quote_decimals"), "QUOTE_DECIMALS_INVALID")
    gte = _int(window.get("block_time_gte"), "WINDOW_GTE_INVALID")
    lt = _int(window.get("block_time_lt"), "WINDOW_LT_INVALID")

    seen_keys: set[tuple[int, int]] = set()
    seen_sigs: set[str] = set()
    previous_key: tuple[int, int] | None = None
    target_trades: list[TargetTrade] = []
    excluded_trades = 0
    close_events = 0
    truncated = 0
    pumpswap_ix_rows = 0
    pumpswap_ix_count = 0
    attributed_events = 0
    successful = 0
    observed_base_decimals: set[int] = set()
    observed_quote_decimals: set[int] = set()

    for row in rows:
        mapped = _mapping(row, "ROW_INVALID")
        meta = _mapping(mapped.get("meta"), "META_INVALID")
        _require(meta.get("err") is None, "UNSUCCESSFUL_TRANSACTION")
        successful += 1
        slot = _int(mapped.get("slot"), "SLOT_INVALID")
        index = _int(mapped.get("transactionIndex"), "TX_INDEX_INVALID")
        block_time = _int(mapped.get("blockTime"), "BLOCK_TIME_INVALID")
        _require(gte <= block_time < lt, "BLOCK_TIME_OUTSIDE_WINDOW")
        key = (slot, index)
        _require(key not in seen_keys, "DUPLICATE_TRANSACTION_KEY")
        if previous_key is not None:
            _require(key > previous_key, "TRANSACTION_ORDER_DRIFT")
        previous_key = key
        seen_keys.add(key)
        signatures = _mapping(mapped.get("transaction"), "TRANSACTION_INVALID").get(
            "signatures"
        )
        _require(
            isinstance(signatures, Sequence)
            and signatures
            and isinstance(signatures[0], str),
            "SIGNATURES_INVALID",
        )
        signature = signatures[0]
        _require(signature not in seen_sigs, "DUPLICATE_SIGNATURE")
        seen_sigs.add(signature)
        observed_base_decimals |= _token_decimals(mapped, base_mint)
        observed_quote_decimals |= _token_decimals(mapped, quote_mint)

        instructions = _iter_pumpswap_instructions(mapped, program_id=program_id)
        if instructions:
            pumpswap_ix_rows += 1
        pumpswap_ix_count += len(instructions)
        market_buy = 0
        market_sell = 0
        close_ix = 0
        for _kind, digest in instructions:
            classified = _classify_ix(
                digest, discs=discs, close_event_hex=close_hex
            )
            if classified in {"buy", "buy_exact_quote_in"}:
                market_buy += 1
            elif classified == "sell":
                market_sell += 1
            elif classified == "close_user_volume_accumulator":
                close_ix += 1

        logs = meta.get("logMessages") or []
        _require(
            isinstance(logs, Sequence) and not isinstance(logs, (str, bytes)),
            "LOGS_INVALID",
        )
        try:
            attributed = attribute_pumpswap_program_data_logs(
                plan,
                logs=[str(line) for line in logs],
                transaction_succeeded=True,
                allow_unclosed_stack=True,
            )
        except TouchProtocolDriftError as exc:
            raise A24IntegrityError(f"LOG_ATTRIBUTION_DRIFT:{exc}") from exc
        if attributed.logs_truncated:
            truncated += 1
        attributed_events += len(attributed.decoded_events)
        attributed_events += attributed.unsupported_pumpswap_program_data
        buy_events = 0
        sell_events = 0
        for digest in attributed.unsupported_discriminators_hex:
            if digest != close_hex:
                raise A24IntegrityError(f"UNKNOWN_MARKET_DISCRIMINATOR:{digest}")
            close_events += 1
        for event in attributed.decoded_events:
            if event.event_name == "BuyEvent":
                buy_events += 1
                base_amount = int(event.fields["base_amount_out"])
                quote_amount = int(event.fields["user_quote_amount_in"])
                side = "buy"
            elif event.event_name == "SellEvent":
                sell_events += 1
                base_amount = int(event.fields["base_amount_in"])
                quote_amount = int(event.fields["user_quote_amount_out"])
                side = "sell"
            else:
                raise A24IntegrityError("UNEXPECTED_TRADE_EVENT")
            if event.pool_id != target_pool:
                excluded_trades += 1
                continue
            event_at = datetime.fromtimestamp(event.event_timestamp, tz=UTC)
            target_trades.append(
                TargetTrade(
                    signature=signature,
                    slot=slot,
                    transaction_index=index,
                    block_time=block_time,
                    event_at=event_at,
                    side=side,
                    pool_id=event.pool_id,
                    base_amount_atomic=base_amount,
                    quote_amount_atomic=quote_amount,
                    raw_base_reserve_atomic=int(event.fields["pool_base_token_reserves"]),
                    raw_quote_reserve_atomic=int(event.fields["pool_quote_token_reserves"]),
                    virtual_quote_reserves=int(event.fields["virtual_quote_reserves"]),
                    price_quote_per_base=_trade_price(
                        base_atomic=base_amount,
                        quote_atomic=quote_amount,
                        base_decimals=base_decimals,
                        quote_decimals=quote_decimals,
                    ),
                    logs_truncated=attributed.logs_truncated,
                    payload_sha256=event.payload_sha256,
                )
            )
        if market_buy != buy_events or market_sell != sell_events:
            raise A24IntegrityError("MARKET_INSTRUCTION_EVENT_MISMATCH")
        if close_ix != len(
            [
                digest
                for digest in attributed.unsupported_discriminators_hex
                if digest == close_hex
            ]
        ):
            raise A24IntegrityError("CLOSE_ACCUMULATOR_EVENT_MISMATCH")
        if attributed.logs_truncated and (
            market_buy + market_sell != buy_events + sell_events
        ):
            raise A24IntegrityError("TRUNCATED_MARKET_COVERAGE_UNRECONCILED")

    if observed_base_decimals and observed_base_decimals != {base_decimals}:
        raise A24IntegrityError("BASE_DECIMALS_METADATA_DRIFT")
    if observed_quote_decimals and observed_quote_decimals != {quote_decimals}:
        raise A24IntegrityError("QUOTE_DECIMALS_METADATA_DRIFT")
    _require(successful == len(rows), "SUCCESS_COUNT_DRIFT")
    buy_target = sum(1 for trade in target_trades if trade.side == "buy")
    sell_target = sum(1 for trade in target_trades if trade.side == "sell")
    return {
        "successful_transactions": successful,
        "pumpswap_instruction_rows": pumpswap_ix_rows,
        "pumpswap_program_instructions": pumpswap_ix_count,
        "attributed_pumpswap_events": attributed_events,
        "decoded_buy_sell_events": buy_target + sell_target + excluded_trades,
        "target_pool_trade_events": buy_target + sell_target,
        "target_buy_events": buy_target,
        "target_sell_events": sell_target,
        "other_pool_trade_events": excluded_trades,
        "close_user_volume_accumulator_events": close_events,
        "log_truncated_transactions": truncated,
        "target_trades": target_trades,
    }


def _slot_bounds(window: Mapping[str, Any]) -> list[tuple[int, datetime, datetime]]:
    start = _parse_utc(_text(window.get("since_inclusive"), "WINDOW_START_INVALID"))
    interval = _int(window.get("interval_seconds"), "INTERVAL_INVALID")
    expected = _int(window.get("expected_slots"), "SLOT_COUNT_INVALID")
    _require(expected == 96 and interval == 900, "SLOT_GRID_DRIFT")
    bounds: list[tuple[int, datetime, datetime]] = []
    for index in range(expected):
        slot_start = start + timedelta(seconds=index * interval)
        slot_end = slot_start + timedelta(seconds=interval)
        bounds.append((index, slot_start, slot_end))
    return bounds


def build_panel(
    policy: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    *,
    identity: Mapping[str, Any],
    measured_as_of: datetime,
) -> list[dict[str, Any]]:
    window = _mapping(policy.get("pilot_window"), "WINDOW_INVALID")
    trades: Sequence[TargetTrade] = reconciliation["target_trades"]
    grouped: dict[int, list[TargetTrade]] = {index: [] for index in range(96)}
    for trade in trades:
        offset = trade.block_time - _int(window.get("block_time_gte"), "WINDOW_GTE_INVALID")
        slot_index = offset // _int(window.get("interval_seconds"), "INTERVAL_INVALID")
        _require(0 <= slot_index < 96, "TRADE_SLOT_OUT_OF_RANGE")
        grouped[slot_index].append(trade)

    a22_hash = identity["a22_sha256"]
    a23_hash = identity["a23_sha256"]
    last_state: tuple[int, int, int] | None = None
    panel: list[dict[str, Any]] = []
    for index, start, end in _slot_bounds(window):
        slot_trades = sorted(
            grouped[index],
            key=lambda item: (item.event_at, item.signature, item.payload_sha256),
        )
        truncated = sum(1 for item in slot_trades if item.logs_truncated)
        if slot_trades:
            state = "OBSERVED_TARGET_TRADES"
            prices = [Decimal(item.price_quote_per_base) for item in slot_trades]
            volume_base = sum(item.base_amount_atomic for item in slot_trades)
            volume_quote = sum(item.quote_amount_atomic for item in slot_trades)
            last = slot_trades[-1]
            last_state = (
                last.raw_base_reserve_atomic,
                last.raw_quote_reserve_atomic,
                last.virtual_quote_reserves,
            )
            ohlc = {
                "open": format(prices[0], "f"),
                "high": format(max(prices), "f"),
                "low": format(min(prices), "f"),
                "close": format(prices[-1], "f"),
            }
            reserves = {
                "raw_base_reserve_atomic": last.raw_base_reserve_atomic,
                "raw_quote_reserve_atomic": last.raw_quote_reserve_atomic,
                "virtual_quote_reserves": last.virtual_quote_reserves,
                "carry_forward": False,
            }
        elif last_state is not None:
            state = "STATE_PERSISTENCE_PROVEN"
            volume_base = 0
            volume_quote = 0
            ohlc = {"open": None, "high": None, "low": None, "close": None}
            reserves = {
                "raw_base_reserve_atomic": last_state[0],
                "raw_quote_reserve_atomic": last_state[1],
                "virtual_quote_reserves": last_state[2],
                "carry_forward": True,
            }
        else:
            state = "PROVEN_NO_TARGET_TRADE"
            volume_base = 0
            volume_quote = 0
            ohlc = {"open": None, "high": None, "low": None, "close": None}
            reserves = {
                "raw_base_reserve_atomic": None,
                "raw_quote_reserve_atomic": None,
                "virtual_quote_reserves": None,
                "carry_forward": False,
            }
        panel.append(
            {
                "slot_index": index,
                "start_at": _format_utc(start),
                "end_at": _format_utc(end),
                "state": state,
                "target_trade_count": len(slot_trades),
                "buy_count": sum(1 for item in slot_trades if item.side == "buy"),
                "sell_count": sum(1 for item in slot_trades if item.side == "sell"),
                "volume_base_atomic": volume_base,
                "volume_quote_atomic": volume_quote,
                "ohlc": ohlc,
                "reserves": reserves,
                "log_truncated_transactions": truncated,
                "source_hashes": {
                    "a22_raw_sha256": a22_hash,
                    "a23_terminal_sha256": a23_hash,
                },
                "measured_as_of": _format_utc(measured_as_of),
            }
        )
    _require(len(panel) == 96, "PANEL_SLOT_COUNT_DRIFT")
    _require(
        all(item["state"] in SLOT_STATES for item in panel),
        "PANEL_STATE_DRIFT",
    )
    return panel


def audit_pit(
    policy: Mapping[str, Any],
    identity: Mapping[str, Any],
    *,
    measured_as_of: datetime,
) -> dict[str, Any]:
    ingested = _parse_utc(_text(identity.get("a22_ingested_at"), "A22_INGESTED_INVALID"))
    completeness = _parse_utc(
        _text(
            identity.get("completeness_available_at"),
            "A23_AVAILABLE_INVALID",
        )
    )
    first_reliable = max(ingested, completeness)
    window = _mapping(policy.get("pilot_window"), "WINDOW_INVALID")
    measured_cutoff = _parse_utc(
        _text(window.get("till_exclusive"), "WINDOW_END_INVALID")
    )
    available_to_strategy = max(first_reliable, measured_as_of)
    _require(ingested <= first_reliable <= available_to_strategy, "PIT_ORDER_INVALID")
    _require(
        measured_cutoff <= available_to_strategy,
        "PIT_MEASURED_AS_OF_AFTER_AVAILABLE",
    )
    return {
        "event_at_basis": "on_chain_buy_sell_event_timestamp",
        "observed_at": _format_utc(ingested),
        "first_reliable_available_at": _format_utc(first_reliable),
        "available_to_strategy_at": _format_utc(available_to_strategy),
        "ingested_at": _format_utc(ingested),
        "measured_as_of": _format_utc(measured_cutoff),
        "chain_block_time_used_as_availability": False,
        "retrospective_market_history_usable": True,
        "prospective_pit_route_usable": False,
        "unknown_earlier_availability": True,
    }


def issue_decision(
    *,
    panel: Sequence[Mapping[str, Any]],
    reconciliation: Mapping[str, Any],
    pit: Mapping[str, Any],
) -> dict[str, Any]:
    states = [item["state"] for item in panel]
    _require(len(panel) == 96, "DECISION_PANEL_LENGTH")
    unknown = sum(1 for state in states if state == "UNKNOWN_COVERAGE")
    observed = sum(1 for state in states if state == "OBSERVED_TARGET_TRADES")
    limitations = [
        "RETROSPECTIVE_ONLY_FIRST_RELIABLE_AVAILABILITY_IS_CAPTURE_TIME",
        "NO_PROSPECTIVE_PIT_ROUTE",
        "NO_MULTI_NOTIONAL_ROUTE_PERSISTENCE",
        "NO_POST_MIGRATION_CONTINUATION_PROOF",
        "NO_CONTINUOUS_PRICE_PATH",
        "OHLC_NULL_WHEN_NO_TARGET_TRADE",
        "RESERVE_CARRY_FORWARD_ONLY_WHEN_STATE_PERSISTENCE_PROVEN",
    ]
    if unknown:
        return {
            "terminal_decision": "TARGETED_PROVIDER_CAPABILITY_GAP_PROVEN",
            "provider_gap": {
                "missing_capability": "COMPLETE_EVENT_COVERAGE_FOR_UNKNOWN_SLOTS",
                "unknown_slots": unknown,
            },
            "limitations": limitations,
            "observed_trade_slots": observed,
            "proven_empty_or_persistent_slots": 96 - observed - unknown,
        }
    return {
        "terminal_decision": "LIMITED_DIAGNOSTIC_PANEL_READY",
        "provider_gap": None,
        "limitations": limitations,
        "observed_trade_slots": observed,
        "proven_empty_or_persistent_slots": 96 - observed,
        "next_owner_action": (
            "Decide whether to run one frozen H07/H01 limited diagnostic "
            "under a new exact contract. Do not call it a trial or alpha."
        ),
    }


def execute_admissibility(
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    a22_payload: bytes,
    a23_payload: bytes,
    measured_as_of: datetime,
) -> dict[str, Any]:
    try:
        verify_frozen_definition(repo_root, policy)
        identity = verify_input_identity(
            policy, a22_payload=a22_payload, a23_payload=a23_payload
        )
        decoder = _mapping(policy.get("decoder_binding"), "DECODER_BINDING_INVALID")
        plan = load_pinned_pumpswap_plan(
            repo_root / _text(decoder.get("idl_subset_path"), "IDL_PATH_INVALID")
        )
        _require(plan.program_id == PUMPSWAP_PROGRAM_ID, "IDL_PROGRAM_DRIFT")
        rows = [
            _mapping(row, "ROW_INVALID") for row in identity["rows"]
        ]
        reconciliation = reconcile_batch(policy, rows, plan=plan)
        panel = build_panel(
            policy,
            reconciliation,
            identity=identity,
            measured_as_of=measured_as_of,
        )
        pit = audit_pit(policy, identity, measured_as_of=measured_as_of)
        decision = issue_decision(
            panel=panel, reconciliation=reconciliation, pit=pit
        )
        terminal = decision["terminal_decision"]
    except (A24IntegrityError, A24Error) as exc:
        if str(exc) in {"POLICY_SCHEMA_DRIFT", "POLICY_VERSION_DRIFT", "POLICY_ATOM_DRIFT"}:
            raise
        terminal = "STOP_INTEGRITY_CONFLICT"
        identity = {
            "a22_sha256": sha256_bytes(a22_payload),
            "a23_sha256": sha256_bytes(a23_payload),
            "a22_ingested_at": policy["input_bindings"]["a22_raw"]["ingested_at"],
            "completeness_available_at": policy["input_bindings"]["a23_terminal_page"][
                "completeness_available_at"
            ],
        }
        reconciliation = {
            "integrity_error": str(exc),
            "successful_transactions": None,
            "target_pool_trade_events": None,
            "target_buy_events": None,
            "target_sell_events": None,
            "other_pool_trade_events": None,
            "log_truncated_transactions": None,
            "target_trades": [],
        }
        panel = []
        pit = {
            "retrospective_market_history_usable": False,
            "prospective_pit_route_usable": False,
        }
        decision = {
            "terminal_decision": terminal,
            "provider_gap": None,
            "integrity_error": str(exc),
            "limitations": ["STOP_NO_HEURISTIC_RECOVERY"],
        }
    counts = {
        key: reconciliation.get(key)
        for key in (
            "successful_transactions",
            "pumpswap_instruction_rows",
            "pumpswap_program_instructions",
            "attributed_pumpswap_events",
            "decoded_buy_sell_events",
            "target_pool_trade_events",
            "target_buy_events",
            "target_sell_events",
            "other_pool_trade_events",
            "close_user_volume_accumulator_events",
            "log_truncated_transactions",
        )
    }
    return {
        "schema": "smial.task30.a24-raw-to-pit-admissibility.result",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_decision": terminal,
        "identity": {
            "a22_sha256": identity.get("a22_sha256"),
            "a23_sha256": identity.get("a23_sha256"),
            "transaction_count": identity.get("transaction_count", len(identity.get("rows", []))),
        },
        "reconciliation": counts,
        "panel_96_slots": panel,
        "pit": pit,
        "decision": decision,
        "claims": dict(_mapping(policy.get("claims"), "CLAIMS_INVALID")),
        "side_effects": {
            "provider_requests": 0,
            "credential_reads": 0,
            "retries": 0,
            "fallbacks": 0,
            "cash_spend_usd_cents": 0,
        },
    }


def write_local_projection(
    result: Mapping[str, Any],
    directory: Path,
    *,
    repo_root: Path,
) -> dict[str, str]:
    if directory.exists():
        raise A24Error("LOCAL_PROJECTION_ALREADY_EXISTS")
    directory.mkdir(parents=True, exist_ok=False)
    panel_path = directory / "panel_96_slots.json"
    recon_path = directory / "event_reconciliation.json"
    manifest_path = directory / "projection_manifest.json"
    panel_path.write_bytes(_canonical_json(result["panel_96_slots"]))
    recon_path.write_bytes(_canonical_json(result["reconciliation"]))
    manifest = {
        "schema": "smial.task30.a24-raw-to-pit-admissibility.projection-manifest",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_decision": result["terminal_decision"],
        "identity": result["identity"],
        "panel_sha256": sha256_bytes(panel_path.read_bytes()),
        "reconciliation_sha256": sha256_bytes(recon_path.read_bytes()),
        "create_only": True,
    }
    manifest_path.write_bytes(_canonical_json(manifest))

    def _relative(path: Path) -> str:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()

    return {
        "panel_96_slots": _relative(panel_path),
        "event_reconciliation": _relative(recon_path),
        "projection_manifest": _relative(manifest_path),
    }
