"""Offline TASK-10 projection for bounded Jupiter quote observations.

This module intentionally has no network transport and performs no file writes.
It converts an already-observed response into the TASK-05 ``QuoteAttempt``
contract plus a TASK-06 in-memory redacted raw envelope.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypeAlias

from solana_alpha_lab.contracts.schema_v1 import (
    QuoteAttempt,
    QuoteStatus,
    RawApiEvent,
    RawResponseStatus,
    Side,
)
from solana_alpha_lab.storage.raw_envelope import build_raw_api_event

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

CONTRACT_VERSION = "task10_jupiter_quote_observation_v1"
PROVIDER = "JUPITER_METIS"
PROVIDER_VERSION = "legacy_metis_v1_quote"
ENDPOINT = "/swap/v1/quote"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_DECIMALS = 6
BUY_PANELS = (
    (10, 10_000_000),
    (25, 25_000_000),
    (50, 50_000_000),
    (100, 100_000_000),
)
DEFAULT_SLIPPAGE_BPS = 100
MAX_RESPONSE_BYTES = 1_048_576
NETWORK_ENABLED = False
RETRIES = 0

_TOP_LEVEL_QUOTE_KEYS = frozenset(
    {
        "inputMint",
        "inAmount",
        "outputMint",
        "outAmount",
        "otherAmountThreshold",
        "swapMode",
        "slippageBps",
        "platformFee",
        "priceImpactPct",
        "routePlan",
        "contextSlot",
        "timeTaken",
    }
)
_TOP_LEVEL_QUOTE_ADDITIVE_KEYS = frozenset(
    {
        "instructionVersion",
        "loadedLongtailToken",
        "longtailMarketQuoteReport",
        "mostReliableAmmsQuoteReport",
        "otherRoutePlans",
        "swapUsdValue",
        "useIncurredSlippageForQuoting",
        "useRewards",
    }
)
_TOP_LEVEL_QUOTE_ALLOWED_KEYS = (
    _TOP_LEVEL_QUOTE_KEYS | _TOP_LEVEL_QUOTE_ADDITIVE_KEYS
)
_ROUTE_KEYS = frozenset({"swapInfo", "percent", "bps"})
_SWAP_INFO_REQUIRED_KEYS = frozenset(
    {
        "ammKey",
        "label",
        "inputMint",
        "outputMint",
        "inAmount",
        "outAmount",
    }
)
_SWAP_INFO_FEE_KEYS = frozenset(
    {
        "feeAmount",
        "feeMint",
    }
)
_SWAP_INFO_ADDITIVE_KEYS = frozenset({"updateContextSlot"})
_SWAP_INFO_ALLOWED_KEYS = (
    _SWAP_INFO_REQUIRED_KEYS
    | _SWAP_INFO_FEE_KEYS
    | _SWAP_INFO_ADDITIVE_KEYS
)
_NO_ROUTE_CODES = frozenset({"COULD_NOT_FIND_ANY_ROUTE"})
_FORBIDDEN_RESPONSE_KEYS = frozenset(
    {
        "transaction",
        "signedtransaction",
        "swaptransaction",
        "transactionmessage",
        "instruction",
        "instructions",
        "swapinstruction",
        "swapinstructions",
    }
)


class QuoteLoggerContractError(ValueError):
    """An input cannot be represented under the frozen TASK-10 contract."""


@dataclass(frozen=True, slots=True)
class QuoteRequest:
    """One exact ExactIn quote request prepared without external I/O."""

    side: Side
    input_mint: str
    output_mint: str
    input_requested_atomic: int
    input_decimals: int
    output_decimals: int
    slippage_bps: int
    attempt_ordinal: int
    business_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.side, Side):
            raise QuoteLoggerContractError("side_must_be_side_enum")
        if self.input_mint == self.output_mint:
            raise QuoteLoggerContractError("quote_mints_must_differ")
        for name, value in (
            ("input_mint", self.input_mint),
            ("output_mint", self.output_mint),
            ("business_key", self.business_key),
        ):
            if not isinstance(value, str) or not value:
                raise QuoteLoggerContractError(f"{name}_must_be_nonempty_text")
        if (
            isinstance(self.input_requested_atomic, bool)
            or not isinstance(self.input_requested_atomic, int)
            or self.input_requested_atomic <= 0
        ):
            raise QuoteLoggerContractError(
                "input_requested_atomic_must_be_positive_integer"
            )
        for name, value in (
            ("input_decimals", self.input_decimals),
            ("output_decimals", self.output_decimals),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise QuoteLoggerContractError(f"{name}_must_be_integer")
            if not 0 <= value <= 30:
                raise QuoteLoggerContractError(f"{name}_out_of_range")
        if (
            isinstance(self.slippage_bps, bool)
            or not isinstance(self.slippage_bps, int)
            or not 0 <= self.slippage_bps <= 10_000
        ):
            raise QuoteLoggerContractError("slippage_bps_out_of_range")
        if (
            isinstance(self.attempt_ordinal, bool)
            or not isinstance(self.attempt_ordinal, int)
            or self.attempt_ordinal < 1
        ):
            raise QuoteLoggerContractError(
                "attempt_ordinal_must_be_positive_integer"
            )

    @property
    def canonical_request(self) -> dict[str, JsonValue]:
        return {
            "amount": str(self.input_requested_atomic),
            "inputMint": self.input_mint,
            "outputMint": self.output_mint,
            "slippageBps": self.slippage_bps,
            "swapMode": "ExactIn",
        }

    @property
    def request_hash(self) -> str:
        return _sha256_json(self.canonical_request)

    @property
    def idempotency_key(self) -> str:
        claim: dict[str, JsonValue] = {
            "attempt_ordinal": self.attempt_ordinal,
            "input_mint": self.input_mint,
            "input_requested_atomic": self.input_requested_atomic,
            "output_mint": self.output_mint,
            "provider_contract_version": CONTRACT_VERSION,
            "side": self.side.value,
        }
        return f"qidem-{_sha256_json(claim)}"


@dataclass(frozen=True, slots=True)
class TransportObservation:
    """Already-observed transport result; never performs transport itself."""

    requested_at: datetime
    response_at: datetime | None
    first_reliable_available_at: datetime
    available_to_strategy_at: datetime
    ingested_at: datetime
    http_status_code: int | None
    response_body: JsonValue | bytes | str | None
    timed_out: bool = False
    stale: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.timed_out, bool):
            raise QuoteLoggerContractError("timed_out_must_be_boolean")
        if not isinstance(self.stale, bool):
            raise QuoteLoggerContractError("stale_must_be_boolean")
        timestamps = (
            ("requested_at", self.requested_at),
            ("first_reliable_available_at", self.first_reliable_available_at),
            ("available_to_strategy_at", self.available_to_strategy_at),
            ("ingested_at", self.ingested_at),
        )
        for name, value in timestamps:
            _require_aware_datetime(name, value)
        if self.response_at is not None:
            _require_aware_datetime("response_at", self.response_at)
            if self.response_at < self.requested_at:
                raise QuoteLoggerContractError("response_before_request")
            if self.response_at > self.first_reliable_available_at:
                raise QuoteLoggerContractError(
                    "response_after_first_reliable_availability"
                )
        if (
            self.first_reliable_available_at
            > self.available_to_strategy_at
        ):
            raise QuoteLoggerContractError(
                "first_reliable_after_strategy_availability"
            )
        if self.available_to_strategy_at > self.ingested_at:
            raise QuoteLoggerContractError(
                "strategy_availability_after_ingestion"
            )
        if self.timed_out:
            if self.response_at is not None or self.response_body is not None:
                raise QuoteLoggerContractError(
                    "timeout_cannot_have_response"
                )
            if self.http_status_code is not None:
                raise QuoteLoggerContractError(
                    "timeout_cannot_have_http_status"
                )
        elif self.response_at is None:
            raise QuoteLoggerContractError(
                "non_timeout_requires_response_timestamp"
            )
        if self.http_status_code is not None and (
            isinstance(self.http_status_code, bool)
            or not isinstance(self.http_status_code, int)
            or not 100 <= self.http_status_code <= 599
        ):
            raise QuoteLoggerContractError("http_status_code_out_of_range")


@dataclass(frozen=True, slots=True)
class QuoteProjection:
    """One in-memory raw event and its normalized TASK-05 projection."""

    raw_event: RawApiEvent
    quote_attempt: QuoteAttempt
    stop_reason: str | None


@dataclass(frozen=True, slots=True)
class DependentSellDecision:
    """Explicitly records whether an exact reverse-sell may be attempted."""

    request: QuoteRequest | None
    disposition: str


@dataclass(frozen=True, slots=True)
class _Classification:
    status: QuoteStatus
    error_class: str | None
    output_quoted_atomic: int | None
    route_id: str | None
    route_count: int | None
    context_slot: int | None
    quality_flags: str
    raw_status: RawResponseStatus
    raw_body: JsonValue | bytes | str
    stop_reason: str | None = None


def _require_aware_datetime(name: str, value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise QuoteLoggerContractError(f"{name}_must_be_timezone_aware")
    return value.astimezone(timezone.utc)


def _canonical_json_bytes(value: JsonValue) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise QuoteLoggerContractError(
            "value_must_be_canonical_json"
        ) from exc


def _sha256_json(value: JsonValue) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _normalize_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _contains_forbidden_response_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                return True
            if _normalize_key(key) in _FORBIDDEN_RESPONSE_KEYS:
                return True
            if _contains_forbidden_response_key(item):
                return True
        return False
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return any(_contains_forbidden_response_key(item) for item in value)
    return False


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise QuoteLoggerContractError("duplicate_json_key")
        result[key] = value
    return result


def _body_bytes(value: JsonValue | bytes | str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return _canonical_json_bytes(value)


def _parse_json_body(value: JsonValue | bytes | str) -> JsonValue:
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise QuoteLoggerContractError("response_not_utf8") from exc
        try:
            parsed = json.loads(
                text,
                object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=lambda _value: (_ for _ in ()).throw(
                    QuoteLoggerContractError("non_finite_json_number")
                ),
            )
        except json.JSONDecodeError as exc:
            raise QuoteLoggerContractError("response_not_json") from exc
        return parsed
    if isinstance(value, str):
        return _parse_json_body(value.encode("utf-8"))
    _canonical_json_bytes(value)
    return value


def _nonnegative_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QuoteLoggerContractError(f"{name}_must_be_nonnegative_integer")
    return value


def _positive_atomic_text(name: str, value: object) -> int:
    if not isinstance(value, str) or not value.isdecimal():
        raise QuoteLoggerContractError(f"{name}_must_be_atomic_text")
    result = int(value)
    if result <= 0:
        raise QuoteLoggerContractError(f"{name}_must_be_positive")
    return result


def _nonnegative_atomic_text(name: str, value: object) -> int:
    if not isinstance(value, str) or not value.isdecimal():
        raise QuoteLoggerContractError(f"{name}_must_be_atomic_text")
    return int(value)


def _validate_optional_decimal_text(name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise QuoteLoggerContractError(f"{name}_must_be_decimal_text")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise QuoteLoggerContractError(
            f"{name}_must_be_decimal_text"
        ) from exc
    if not parsed.is_finite():
        raise QuoteLoggerContractError(f"{name}_must_be_finite")


def _validate_nonnegative_decimal_text(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise QuoteLoggerContractError(f"{name}_must_be_decimal_text")
    _validate_optional_decimal_text(name, value)
    if Decimal(value) < 0:
        raise QuoteLoggerContractError(f"{name}_must_be_nonnegative")


def _validate_typed_quote_extensions(value: Mapping[str, object]) -> None:
    if (
        "instructionVersion" in value
        and value["instructionVersion"] is not None
    ):
        raise QuoteLoggerContractError(
            "instruction_version_extension_must_be_null"
        )
    if "loadedLongtailToken" in value and not isinstance(
        value["loadedLongtailToken"],
        bool,
    ):
        raise QuoteLoggerContractError(
            "loaded_longtail_token_extension_must_be_boolean"
        )
    for field in (
        "longtailMarketQuoteReport",
        "otherRoutePlans",
        "useIncurredSlippageForQuoting",
        "useRewards",
    ):
        if field in value and value[field] is not None:
            raise QuoteLoggerContractError(
                f"{field}_extension_must_be_null"
            )
    if "swapUsdValue" in value:
        _validate_nonnegative_decimal_text(
            "swapUsdValue",
            value["swapUsdValue"],
        )
    if "mostReliableAmmsQuoteReport" in value:
        report = value["mostReliableAmmsQuoteReport"]
        if not isinstance(report, Mapping) or set(report) != {"info"}:
            raise QuoteLoggerContractError(
                "reliable_amms_report_shape_invalid"
            )
        info = report["info"]
        if not isinstance(info, Mapping) or not all(
            isinstance(key, str)
            and bool(key)
            and isinstance(item, str)
            and bool(item)
            for key, item in info.items()
        ):
            raise QuoteLoggerContractError(
                "reliable_amms_report_info_invalid"
            )


def _validate_route_plan(value: object) -> tuple[list[JsonValue], bool]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise QuoteLoggerContractError("route_plan_must_be_sequence")
    if not value:
        raise QuoteLoggerContractError("route_plan_must_be_nonempty")
    result: list[JsonValue] = []
    fees_absent = False
    for route in value:
        if not isinstance(route, Mapping):
            raise QuoteLoggerContractError("route_entry_must_be_mapping")
        if not all(isinstance(key, str) for key in route):
            raise QuoteLoggerContractError("route_entry_keys_must_be_text")
        if not set(route).issubset(_ROUTE_KEYS):
            raise QuoteLoggerContractError("unexpected_route_entry_key")
        if set(route) != _ROUTE_KEYS:
            raise QuoteLoggerContractError("route_entry_fields_missing")
        percent = _nonnegative_integer("route_percent", route["percent"])
        bps_value = route["bps"]
        bps = (
            None
            if bps_value is None
            else _nonnegative_integer("route_bps", bps_value)
        )
        if not 1 <= percent <= 100 or (
            bps is not None and not 1 <= bps <= 10_000
        ):
            raise QuoteLoggerContractError("route_weight_out_of_range")
        swap_info = route["swapInfo"]
        if not isinstance(swap_info, Mapping):
            raise QuoteLoggerContractError("swap_info_must_be_mapping")
        if not all(isinstance(key, str) for key in swap_info):
            raise QuoteLoggerContractError("swap_info_keys_must_be_text")
        swap_info_keys = set(swap_info)
        if not swap_info_keys.issubset(_SWAP_INFO_ALLOWED_KEYS):
            raise QuoteLoggerContractError("swap_info_fields_mismatch")
        if not _SWAP_INFO_REQUIRED_KEYS.issubset(swap_info_keys):
            raise QuoteLoggerContractError("swap_info_fields_mismatch")
        present_fee_keys = swap_info_keys & _SWAP_INFO_FEE_KEYS
        if present_fee_keys not in (frozenset(), _SWAP_INFO_FEE_KEYS):
            raise QuoteLoggerContractError("swap_info_fee_pair_incomplete")
        for field in (
            "ammKey",
            "label",
            "inputMint",
            "outputMint",
        ):
            if not isinstance(swap_info[field], str) or not swap_info[field]:
                raise QuoteLoggerContractError(
                    f"swap_info_{field}_must_be_nonempty_text"
                )
        for field in ("inAmount", "outAmount"):
            _positive_atomic_text(f"swap_info_{field}", swap_info[field])
        if present_fee_keys:
            if (
                not isinstance(swap_info["feeMint"], str)
                or not swap_info["feeMint"]
            ):
                raise QuoteLoggerContractError(
                    "swap_info_feeMint_must_be_nonempty_text"
                )
            _nonnegative_atomic_text(
                "swap_info_feeAmount",
                swap_info["feeAmount"],
            )
        else:
            fees_absent = True
        if "updateContextSlot" in swap_info:
            _nonnegative_atomic_text(
                "swap_info_updateContextSlot",
                swap_info["updateContextSlot"],
            )
        result.append(json.loads(_canonical_json_bytes(route)))
    return result, fees_absent


def build_buy_panel_requests(
    *,
    selected_output_mint: str,
    output_decimals: int,
    slippage_bps: int = DEFAULT_SLIPPAGE_BPS,
) -> tuple[QuoteRequest, ...]:
    """Build the exact USD 10/25/50/100 USDC ExactIn panel."""

    return tuple(
        QuoteRequest(
            side=Side.BUY,
            input_mint=USDC_MINT,
            output_mint=selected_output_mint,
            input_requested_atomic=atomic,
            input_decimals=USDC_DECIMALS,
            output_decimals=output_decimals,
            slippage_bps=slippage_bps,
            attempt_ordinal=index,
            business_key=f"task10-panel-usd-{usd}",
        )
        for index, (usd, atomic) in enumerate(BUY_PANELS, start=1)
    )


def decide_dependent_sell(
    buy_projection: QuoteProjection,
    *,
    attempt_ordinal: int,
) -> DependentSellDecision:
    """Use the exact buy ``outAmount`` or record an explicit non-attempt."""

    buy = buy_projection.quote_attempt
    if buy.side != Side.BUY:
        raise QuoteLoggerContractError("dependent_sell_requires_buy_projection")
    if buy.status != QuoteStatus.QUOTE_AVAILABLE:
        return DependentSellDecision(
            request=None,
            disposition="NOT_ATTEMPTED_BUY_PREREQUISITE_FAILED",
        )
    assert buy.output_quoted_atomic is not None
    return DependentSellDecision(
        request=QuoteRequest(
            side=Side.SELL,
            input_mint=buy.output_mint,
            output_mint=buy.input_mint,
            input_requested_atomic=buy.output_quoted_atomic,
            input_decimals=buy.output_decimals,
            output_decimals=buy.input_decimals,
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
            attempt_ordinal=attempt_ordinal,
            business_key=buy.business_key,
        ),
        disposition="ATTEMPT_EXACT_BUY_OUTPUT_ATOMIC",
    )


def _explicit_no_route(value: JsonValue) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("errorCode") in _NO_ROUTE_CODES
        and isinstance(value.get("error"), str)
        and bool(value["error"])
        and set(value).issubset({"error", "errorCode"})
    )


def _provider_error_class(status_code: int) -> tuple[str, str | None]:
    if status_code in {401, 403}:
        return "AUTHENTICATION_REQUIRED", "AUTHENTICATION_OR_ACCOUNT_REQUIRED"
    if status_code == 429:
        return "RATE_LIMITED", None
    if 400 <= status_code <= 499:
        return "HTTP_4XX", None
    if 500 <= status_code <= 599:
        return "HTTP_5XX", None
    return "PROVIDER_CONTRACT_BLOCKED", None


def _invalid(
    *,
    error_class: str,
    raw_body: JsonValue | bytes | str,
    stop_reason: str | None = None,
) -> _Classification:
    return _Classification(
        status=QuoteStatus.INVALID_RESPONSE,
        error_class=error_class,
        output_quoted_atomic=None,
        route_id=None,
        route_count=None,
        context_slot=None,
        quality_flags=f"{error_class}_FAIL_CLOSED",
        raw_status=RawResponseStatus.INVALID_RESPONSE,
        raw_body=raw_body,
        stop_reason=stop_reason,
    )


def _classify(
    request: QuoteRequest,
    observation: TransportObservation,
) -> _Classification:
    if observation.timed_out:
        return _Classification(
            status=QuoteStatus.TIMEOUT,
            error_class="TIMEOUT",
            output_quoted_atomic=None,
            route_id=None,
            route_count=None,
            context_slot=None,
            quality_flags="TIMEOUT_NO_RESPONSE",
            raw_status=RawResponseStatus.TIMEOUT,
            raw_body={
                "response_body_present": False,
                "terminal_class": "TIMEOUT",
            },
        )
    if observation.response_body is None:
        return _invalid(
            error_class="SCHEMA_MISMATCH",
            raw_body={
                "response_body_present": False,
                "terminal_class": "INVALID_RESPONSE",
            },
        )
    try:
        body_bytes = _body_bytes(observation.response_body)
    except QuoteLoggerContractError:
        return _invalid(
            error_class="SCHEMA_MISMATCH",
            raw_body={
                "body_retained": False,
                "response_body_present": True,
                "response_disposition": "NON_CANONICAL_JSON",
            },
        )
    if len(body_bytes) > MAX_RESPONSE_BYTES:
        return _invalid(
            error_class="SCHEMA_MISMATCH",
            raw_body={
                "body_retained": False,
                "response_body_present": True,
                "response_bytes": len(body_bytes),
            },
            stop_reason="RESPONSE_BYTE_CAP_EXHAUSTED",
        )
    try:
        parsed = _parse_json_body(observation.response_body)
    except QuoteLoggerContractError:
        status_code = observation.http_status_code
        if status_code is not None and status_code != 200:
            error_class, stop_reason = _provider_error_class(status_code)
            return _Classification(
                status=QuoteStatus.PROVIDER_ERROR,
                error_class=error_class,
                output_quoted_atomic=None,
                route_id=None,
                route_count=None,
                context_slot=None,
                quality_flags=f"HTTP_STATUS_{status_code}_NON_JSON",
                raw_status=RawResponseStatus.HTTP_ERROR,
                raw_body=observation.response_body,
                stop_reason=stop_reason,
            )
        return _invalid(
            error_class="SCHEMA_MISMATCH",
            raw_body=observation.response_body,
        )
    if _contains_forbidden_response_key(parsed):
        return _invalid(
            error_class="TRANSACTION_PAYLOAD_FORBIDDEN",
            raw_body={
                "body_retained": False,
                "response_body_present": True,
                "response_disposition": "TRANSACTION_PAYLOAD_FORBIDDEN",
            },
            stop_reason="V2_TRANSACTION_OR_INSTRUCTION_SURFACE_REQUIRED",
        )
    if _explicit_no_route(parsed):
        return _Classification(
            status=QuoteStatus.NO_ROUTE,
            error_class=None,
            output_quoted_atomic=None,
            route_id=None,
            route_count=0,
            context_slot=None,
            quality_flags="EXPLICIT_NO_ROUTE",
            raw_status=RawResponseStatus.SUCCESS,
            raw_body=observation.response_body,
        )
    status_code = observation.http_status_code
    if status_code is None:
        return _Classification(
            status=QuoteStatus.PROVIDER_ERROR,
            error_class="PROVIDER_CONTRACT_BLOCKED",
            output_quoted_atomic=None,
            route_id=None,
            route_count=None,
            context_slot=None,
            quality_flags="MISSING_HTTP_STATUS",
            raw_status=RawResponseStatus.PROVIDER_ERROR,
            raw_body=observation.response_body,
        )
    if status_code != 200:
        error_class, stop_reason = _provider_error_class(status_code)
        return _Classification(
            status=QuoteStatus.PROVIDER_ERROR,
            error_class=error_class,
            output_quoted_atomic=None,
            route_id=None,
            route_count=None,
            context_slot=None,
            quality_flags=f"HTTP_STATUS_{status_code}",
            raw_status=RawResponseStatus.HTTP_ERROR,
            raw_body=observation.response_body,
            stop_reason=stop_reason,
        )
    if observation.stale:
        return _invalid(
            error_class="STALE_RESPONSE",
            raw_body=observation.response_body,
        )
    if not isinstance(parsed, Mapping):
        return _invalid(
            error_class="SCHEMA_MISMATCH",
            raw_body=observation.response_body,
        )
    if not all(isinstance(key, str) for key in parsed):
        return _invalid(
            error_class="SCHEMA_MISMATCH",
            raw_body=observation.response_body,
        )
    if not set(parsed).issubset(_TOP_LEVEL_QUOTE_ALLOWED_KEYS):
        return _invalid(
            error_class="SCHEMA_MISMATCH",
            raw_body=observation.response_body,
            stop_reason="UNCLASSIFIABLE_SCHEMA_DRIFT",
        )
    if not _TOP_LEVEL_QUOTE_KEYS.issubset(set(parsed)):
        return _invalid(
            error_class="SCHEMA_MISMATCH",
            raw_body=observation.response_body,
            stop_reason="UNCLASSIFIABLE_SCHEMA_DRIFT",
        )
    try:
        _validate_typed_quote_extensions(parsed)
        if parsed["inputMint"] != request.input_mint:
            raise QuoteLoggerContractError("response_input_mint_mismatch")
        if parsed["outputMint"] != request.output_mint:
            raise QuoteLoggerContractError("response_output_mint_mismatch")
        if (
            _positive_atomic_text("inAmount", parsed["inAmount"])
            != request.input_requested_atomic
        ):
            raise QuoteLoggerContractError("response_input_amount_mismatch")
        output = _positive_atomic_text("outAmount", parsed["outAmount"])
        _nonnegative_atomic_text(
            "otherAmountThreshold",
            parsed["otherAmountThreshold"],
        )
        if parsed["swapMode"] != "ExactIn":
            raise QuoteLoggerContractError("response_swap_mode_mismatch")
        if parsed["slippageBps"] != request.slippage_bps:
            raise QuoteLoggerContractError("response_slippage_mismatch")
        if parsed["platformFee"] is not None and not isinstance(
            parsed["platformFee"],
            Mapping,
        ):
            raise QuoteLoggerContractError("platform_fee_shape_invalid")
        _validate_optional_decimal_text(
            "priceImpactPct",
            parsed["priceImpactPct"],
        )
        if (
            isinstance(parsed["timeTaken"], bool)
            or not isinstance(parsed["timeTaken"], (int, float))
            or not math.isfinite(parsed["timeTaken"])
            or parsed["timeTaken"] < 0
        ):
            raise QuoteLoggerContractError("time_taken_invalid")
        context_slot = parsed["contextSlot"]
        if context_slot is not None:
            context_slot = _nonnegative_integer(
                "contextSlot",
                context_slot,
            )
        route_plan, route_fees_absent = _validate_route_plan(
            parsed["routePlan"]
        )
    except QuoteLoggerContractError:
        return _invalid(
            error_class="SCHEMA_MISMATCH",
            raw_body=observation.response_body,
            stop_reason="UNCLASSIFIABLE_SCHEMA_DRIFT",
        )
    return _Classification(
        status=QuoteStatus.QUOTE_AVAILABLE,
        error_class=None,
        output_quoted_atomic=output,
        route_id=_sha256_json(route_plan),
        route_count=len(route_plan),
        context_slot=context_slot,
        quality_flags=(
            "PROVIDER_ROUTE_FEE_FIELDS_ABSENT_RAW_ONLY"
            if route_fees_absent
            else "PROVIDER_ROUTE_FEE_DETAIL_RAW_ONLY"
        ),
        raw_status=RawResponseStatus.SUCCESS,
        raw_body=observation.response_body,
    )


def _elapsed_ms(start: datetime, end: datetime) -> int:
    delta = end - start
    if delta < timedelta(0):
        raise QuoteLoggerContractError("negative_elapsed_time")
    return delta // timedelta(milliseconds=1)


def project_quote_observation(
    request: QuoteRequest,
    observation: TransportObservation,
) -> QuoteProjection:
    """Project one offline observation without transport or persistence."""

    classification = _classify(request, observation)
    raw_observed_at = (
        observation.response_at
        if observation.response_at is not None
        else observation.first_reliable_available_at
    )
    raw_event = build_raw_api_event(
        source=PROVIDER,
        source_version=PROVIDER_VERSION,
        endpoint_or_method=f"GET {ENDPOINT}",
        request_identity=request.canonical_request,
        response_body=classification.raw_body,
        response_status=classification.raw_status,
        error_class=classification.error_class,
        observed_at=raw_observed_at,
        available_to_strategy_at=observation.available_to_strategy_at,
        ingested_at=observation.ingested_at,
        first_reliable_available_at=(
            observation.first_reliable_available_at
        ),
        provider_version=PROVIDER_VERSION,
        schema_version="1.0",
        protocol_version="legacy_metis_v1_quote",
        quality_flags=classification.quality_flags,
    )
    identity_claim: dict[str, JsonValue] = {
        "idempotency_key": request.idempotency_key,
        "request_hash": request.request_hash,
        "requested_at": request_timestamp(observation.requested_at),
    }
    quote_attempt_id = f"quote-{_sha256_json(identity_claim)}"
    response_at = observation.response_at
    provider_latency_ms = (
        None
        if response_at is None
        else _elapsed_ms(observation.requested_at, response_at)
    )
    quote_age_ms = (
        _elapsed_ms(response_at, observation.available_to_strategy_at)
        if response_at is not None
        and classification.status
        in {QuoteStatus.QUOTE_AVAILABLE, QuoteStatus.NO_ROUTE}
        else None
    )
    quote_attempt = QuoteAttempt(
        quote_attempt_id=quote_attempt_id,
        idempotency_key=request.idempotency_key,
        business_key=request.business_key,
        request_hash=request.request_hash,
        provider=PROVIDER,
        provider_version=PROVIDER_VERSION,
        side=request.side,
        input_mint=request.input_mint,
        input_requested_atomic=request.input_requested_atomic,
        input_decimals=request.input_decimals,
        output_mint=request.output_mint,
        output_quoted_atomic=classification.output_quoted_atomic,
        output_decimals=request.output_decimals,
        route_id=classification.route_id,
        route_count=classification.route_count,
        context_slot=classification.context_slot,
        requested_at=observation.requested_at,
        response_at=response_at,
        available_to_strategy_at=observation.available_to_strategy_at,
        ingested_at=observation.ingested_at,
        first_reliable_available_at=(
            observation.first_reliable_available_at
        ),
        quote_age_ms=quote_age_ms,
        provider_latency_ms=provider_latency_ms,
        provider_fee_atomic=None,
        platform_fee_atomic=None,
        fee_mint=None,
        included_in_output_amount=None,
        status=classification.status,
        error_class=classification.error_class,
        raw_event_id=raw_event.raw_event_id,
        response_content_sha256=raw_event.content_sha256,
        schema_version="1.0",
        revision_number=1,
        revision_of=None,
        quality_flags=classification.quality_flags,
    )
    return QuoteProjection(
        raw_event=raw_event,
        quote_attempt=quote_attempt,
        stop_reason=classification.stop_reason,
    )


def request_timestamp(value: datetime) -> str:
    return (
        _require_aware_datetime("requested_at", value)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _parse_datetime(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise QuoteLoggerContractError(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QuoteLoggerContractError(f"{name}_invalid") from exc
    return _require_aware_datetime(name, parsed)


def request_from_mapping(value: object) -> QuoteRequest:
    if not isinstance(value, Mapping):
        raise QuoteLoggerContractError("fixture_request_must_be_mapping")
    expected = {
        "side",
        "input_mint",
        "output_mint",
        "input_requested_atomic",
        "input_decimals",
        "output_decimals",
        "slippage_bps",
        "attempt_ordinal",
        "business_key",
    }
    if set(value) != expected:
        raise QuoteLoggerContractError("fixture_request_fields_mismatch")
    try:
        side = Side(value["side"])
    except (TypeError, ValueError) as exc:
        raise QuoteLoggerContractError("fixture_request_side_invalid") from exc
    return QuoteRequest(
        side=side,
        input_mint=value["input_mint"],
        output_mint=value["output_mint"],
        input_requested_atomic=value["input_requested_atomic"],
        input_decimals=value["input_decimals"],
        output_decimals=value["output_decimals"],
        slippage_bps=value["slippage_bps"],
        attempt_ordinal=value["attempt_ordinal"],
        business_key=value["business_key"],
    )


def observation_from_mapping(value: object) -> TransportObservation:
    if not isinstance(value, Mapping):
        raise QuoteLoggerContractError("fixture_observation_must_be_mapping")
    expected = {
        "requested_at",
        "response_at",
        "first_reliable_available_at",
        "available_to_strategy_at",
        "ingested_at",
        "http_status_code",
        "response_body",
        "timed_out",
        "stale",
    }
    if set(value) != expected:
        raise QuoteLoggerContractError("fixture_observation_fields_mismatch")
    response_at_value = value["response_at"]
    return TransportObservation(
        requested_at=_parse_datetime("requested_at", value["requested_at"]),
        response_at=(
            None
            if response_at_value is None
            else _parse_datetime("response_at", response_at_value)
        ),
        first_reliable_available_at=_parse_datetime(
            "first_reliable_available_at",
            value["first_reliable_available_at"],
        ),
        available_to_strategy_at=_parse_datetime(
            "available_to_strategy_at",
            value["available_to_strategy_at"],
        ),
        ingested_at=_parse_datetime("ingested_at", value["ingested_at"]),
        http_status_code=value["http_status_code"],
        response_body=value["response_body"],
        timed_out=value["timed_out"],
        stale=value["stale"],
    )


def load_synthetic_fixture(path: Path) -> dict[str, Any]:
    """Load a tracked synthetic fixture under a strict, offline schema."""

    if not isinstance(path, Path):
        raise QuoteLoggerContractError("fixture_path_must_be_path")
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuoteLoggerContractError("fixture_load_failed") from exc
    if not isinstance(document, dict):
        raise QuoteLoggerContractError("fixture_root_must_be_mapping")
    if document.get("schema") != "solana_alpha_lab.jupiter_quote_logger_cases":
        raise QuoteLoggerContractError("fixture_schema_mismatch")
    if document.get("schema_version") != "1.0":
        raise QuoteLoggerContractError("fixture_schema_version_mismatch")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise QuoteLoggerContractError("fixture_cases_missing")
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping) or set(case) != {
            "case_id",
            "expected_status",
            "expected_error_class",
            "expected_stop_reason",
            "request",
            "observation",
        }:
            raise QuoteLoggerContractError("fixture_case_fields_mismatch")
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not case_id:
            raise QuoteLoggerContractError("fixture_case_id_invalid")
        if case_id in case_ids:
            raise QuoteLoggerContractError("fixture_case_id_duplicate")
        case_ids.add(case_id)
        request_from_mapping(case["request"])
        observation_from_mapping(case["observation"])
    return document


def project_fixture_case(case: Mapping[str, Any]) -> QuoteProjection:
    return project_quote_observation(
        request_from_mapping(case["request"]),
        observation_from_mapping(case["observation"]),
    )


def safe_preflight_summary(document: Mapping[str, Any]) -> dict[str, JsonValue]:
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise QuoteLoggerContractError("fixture_cases_missing")
    return {
        "case_count": len(cases),
        "cash_spend_usd_cents": 0,
        "network_enabled": NETWORK_ENABLED,
        "provider_api_rpc_wss_calls": 0,
        "raw_data_writes": 0,
        "retries": RETRIES,
        "wallet_signer_transaction_actions": 0,
    }
