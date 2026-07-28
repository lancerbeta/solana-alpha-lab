"""Bounded keyless transport and durable sink for TASK-10 Atom 4."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypeAlias

import duckdb
from solders.pubkey import Pubkey

from solana_alpha_lab.jupiter_quote_logger import (
    BUY_PANELS,
    DEFAULT_SLIPPAGE_BPS,
    ENDPOINT,
    PROVIDER,
    PROVIDER_VERSION,
    USDC_MINT,
    DependentSellDecision,
    QuoteProjection,
    QuoteRequest,
    TransportObservation,
    build_buy_panel_requests,
    decide_dependent_sell,
    project_quote_observation,
)
from solana_alpha_lab.storage import (
    StorageBudgetExceededError,
    StorageBudgetPolicy,
    canonical_manifest_bytes,
    verify_raw_event_partition,
    write_budgeted_raw_event_partition,
)

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

PILOT_PLAN_SHA256 = (
    "b76c11f19f8244d6b2dfa5c4bb6c8594a5e790f22eef5010117d21b475243833"
)
EXTERNAL_AUTHORITY_PHRASE = "T10-A6_BOUNDED_EXTERNAL_QUOTE_PILOT_V2"
BASE_URL = "https://api.jup.ag"
RAW_LOGICAL_ROOT = "task10_jupiter_quote_pilot_v2"
DATASET_ID = "SMIAL_TASK10_JUPITER_QUOTE_PILOT_V2_RAW"
DATASET_VERSION = "2.0"
TRANSPORT_VERSION = "2.0"
MAX_HTTP_REQUESTS = 8
MAX_WALL_SECONDS = 600
MAX_RECEIVED_BYTES = 1_048_576
MAX_DURABLE_BYTES = 5_242_880
MAX_RAW_PARTITION_BYTES = 2_621_440
MAX_PROJECTION_DATABASE_BYTES = 2_490_000
METADATA_RESERVE_BYTES = (
    MAX_DURABLE_BYTES
    - MAX_RAW_PARTITION_BYTES
    - MAX_PROJECTION_DATABASE_BYTES
)
REQUEST_TIMEOUT_SECONDS = 20
MINIMUM_INTERVAL_SECONDS = 2.2
RETRIES = 0
_SAFE_RUN_ID_RE = re.compile(r"t10a6-[0-9]{8}T[0-9]{6}Z")


class QuoteTransportError(RuntimeError):
    """Base failure for the bounded TASK-10 external atom."""


class ExternalAuthorityRequiredError(QuoteTransportError):
    """The runtime gate is absent or does not match the approved atom."""


class QuoteTransportContractError(QuoteTransportError):
    """The frozen plan, request, or persistence target is incoherent."""


class QuoteTransportStopError(QuoteTransportError):
    """A hard cap or explicit stop condition ended the pilot."""


@dataclass(frozen=True, slots=True)
class PilotCaps:
    http_requests_total_max: int
    concurrency: int
    retries: int
    wall_seconds_max: int
    request_timeout_seconds: int
    minimum_interval_seconds: float
    received_response_bytes_max: int
    durable_raw_bytes_max: int
    api_keys: int
    accounts: int
    provider_credits: int
    cash_spend_usd_cents: int
    wallet_signer_transaction_actions: int


@dataclass(frozen=True, slots=True)
class PilotPlan:
    atom_id: str
    run_id: str
    selected_mint: str
    selected_mint_decimals: int
    selection_rule: str
    source_asset_id: str
    source_run_id: str
    source_partition_sha256: str
    source_raw_event_id: str
    source_slot: int
    base_url: str
    path: str
    quote_mint: str
    quote_decimals: int
    slippage_bps: int
    buy_input_atomic: tuple[int, ...]
    caps: PilotCaps
    logical_root: str
    raw_partition: str
    projection_database: str
    manifest_location: str
    receipt_location: str
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class ExternalExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise ExternalAuthorityRequiredError(
                "external_authority_phrase_mismatch"
            )


@dataclass(frozen=True, slots=True)
class HttpCapture:
    observation: TransportObservation
    received_bytes: int
    transport_stop_reason: str | None


@dataclass(frozen=True, slots=True)
class PilotRunSummary:
    run_id: str
    status: str
    stop_reason: str | None
    provider_calls: int
    received_bytes: int
    elapsed_seconds: float
    buy_attempts: int
    sell_attempts: int
    sell_not_attempted: int
    terminal_counts: dict[str, int]
    logical_root: str
    stored_events: int = 0
    stored_bytes: int = 0
    raw_partition_sha256: str | None = None
    raw_content_sha256: str | None = None
    projection_database_sha256: str | None = None

    def safe_receipt(self) -> dict[str, JsonValue]:
        return {
            "accounts_used": 0,
            "api_keys_used": 0,
            "buy_attempts": self.buy_attempts,
            "cash_spend_usd_cents": 0,
            "concurrency": 1,
            "elapsed_seconds": self.elapsed_seconds,
            "logical_root": self.logical_root,
            "projection_database_sha256": (
                self.projection_database_sha256
            ),
            "provider_calls": self.provider_calls,
            "provider_credits": 0,
            "raw_content_sha256": self.raw_content_sha256,
            "raw_partition_sha256": self.raw_partition_sha256,
            "received_bytes": self.received_bytes,
            "retries": 0,
            "run_id": self.run_id,
            "sell_attempts": self.sell_attempts,
            "sell_not_attempted": self.sell_not_attempted,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "stored_bytes": self.stored_bytes,
            "stored_events": self.stored_events,
            "terminal_counts": dict(sorted(self.terminal_counts.items())),
            "wallet_signer_transaction_actions": 0,
        }


class QuoteTransport(Protocol):
    @property
    def attempts(self) -> int: ...

    @property
    def received_bytes(self) -> int: ...

    def execute(self, request: QuoteRequest) -> HttpCapture: ...


class QuoteSink(Protocol):
    @property
    def logical_root(self) -> str: ...

    def append(self, projection: QuoteProjection) -> None: ...

    def finalize(self, summary: PilotRunSummary) -> PilotRunSummary: ...


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise QuoteTransportContractError(f"{name}_must_be_mapping")
    if not all(isinstance(key, str) for key in value):
        raise QuoteTransportContractError(f"{name}_keys_must_be_text")
    return value


def _sequence(name: str, value: object) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise QuoteTransportContractError(f"{name}_must_be_sequence")
    return value


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise QuoteTransportContractError(f"{name}_must_be_integer")
    return value


def _number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QuoteTransportContractError(f"{name}_must_be_number")
    return float(value)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise QuoteTransportContractError(f"{name}_must_be_nonempty_text")
    return value


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise QuoteTransportContractError(
            "json_canonicalization_failed"
        ) from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def load_pilot_plan(path: Path) -> PilotPlan:
    """Verify the frozen pre-observation plan and compile exact caps."""

    if not isinstance(path, Path):
        raise QuoteTransportContractError("plan_path_must_be_path")
    payload = path.read_bytes()
    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != PILOT_PLAN_SHA256:
        raise QuoteTransportContractError("pilot_plan_hash_mismatch")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise QuoteTransportContractError("pilot_plan_json_invalid") from exc
    root = _mapping("plan", document)
    if set(root) != {
        "schema",
        "schema_version",
        "task_id",
        "atom_id",
        "status",
        "run_id",
        "selection",
        "provider_surface",
        "panels",
        "caps",
        "stop_conditions",
        "storage",
        "authority",
    }:
        raise QuoteTransportContractError("pilot_plan_fields_mismatch")
    expected_root = {
        "schema": "solana_alpha_lab.jupiter_quote_pilot_plan",
        "schema_version": "2.0",
        "task_id": "TASK-10",
        "atom_id": "T10-A6_BOUNDED_EXTERNAL_QUOTE_PILOT_V2",
        "status": "FROZEN_BEFORE_EXTERNAL_OBSERVATION",
    }
    for name, expected in expected_root.items():
        if root[name] != expected:
            raise QuoteTransportContractError(f"pilot_plan_{name}_drift")

    run_id = _text("run_id", root["run_id"])
    if _SAFE_RUN_ID_RE.fullmatch(run_id) is None:
        raise QuoteTransportContractError("run_id_invalid")

    selection = _mapping("selection", root["selection"])
    mint = _text("selection.mint", selection.get("mint"))
    try:
        Pubkey.from_string(mint)
    except ValueError as exc:
        raise QuoteTransportContractError("selected_mint_invalid") from exc
    if selection.get("price_or_route_observation_used") is not False:
        raise QuoteTransportContractError("selection_lookahead_forbidden")
    if (
        selection.get("rule")
        != "SOLE_NON_WSOL_MINT_IN_ACCEPTED_TASK09_GETTRANSACTION_TOKEN_BALANCES"
    ):
        raise QuoteTransportContractError("selection_rule_drift")
    if (
        selection.get("source_partition_sha256")
        != "577e614c0b2f41b7a1e3ae92b6cfd965e87e4d4bca76070925873df1ef5b4466"
    ):
        raise QuoteTransportContractError("task09_partition_hash_drift")

    surface = _mapping("provider_surface", root["provider_surface"])
    if surface != {
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "base_url": BASE_URL,
        "method": "GET",
        "path": ENDPOINT,
        "claim": "LEGACY_QUOTE_COMPATIBILITY_ONLY",
        "credentials": 0,
        "accounts": 0,
        "fallback_hosts": [],
        "v2_fallback": False,
    }:
        raise QuoteTransportContractError("provider_surface_drift")

    panels = _mapping("panels", root["panels"])
    buy_input_atomic = tuple(
        _integer(f"buy_input_atomic_{index}", value)
        for index, value in enumerate(
            _sequence(
                "panels.buy_input_atomic",
                panels.get("buy_input_atomic"),
            )
        )
    )
    if buy_input_atomic != tuple(atomic for _, atomic in BUY_PANELS):
        raise QuoteTransportContractError("buy_panel_drift")
    if (
        panels.get("quote_mint") != USDC_MINT
        or panels.get("quote_decimals") != 6
        or panels.get("slippage_bps") != DEFAULT_SLIPPAGE_BPS
        or panels.get("sell_input_rule")
        != "EXACT_ACCEPTED_BUY_OUT_AMOUNT_ATOMIC"
        or panels.get("sell_after_unavailable_buy")
        != "NOT_ATTEMPTED_BUY_PREREQUISITE_FAILED"
    ):
        raise QuoteTransportContractError("panel_contract_drift")

    raw_caps = _mapping("caps", root["caps"])
    caps = PilotCaps(
        http_requests_total_max=_integer(
            "http_requests_total_max",
            raw_caps.get("http_requests_total_max"),
        ),
        concurrency=_integer("concurrency", raw_caps.get("concurrency")),
        retries=_integer("retries", raw_caps.get("retries")),
        wall_seconds_max=_integer(
            "wall_seconds_max",
            raw_caps.get("wall_seconds_max"),
        ),
        request_timeout_seconds=_integer(
            "request_timeout_seconds",
            raw_caps.get("request_timeout_seconds"),
        ),
        minimum_interval_seconds=_number(
            "minimum_interval_seconds",
            raw_caps.get("minimum_interval_seconds"),
        ),
        received_response_bytes_max=_integer(
            "received_response_bytes_max",
            raw_caps.get("received_response_bytes_max"),
        ),
        durable_raw_bytes_max=_integer(
            "durable_raw_bytes_max",
            raw_caps.get("durable_raw_bytes_max"),
        ),
        api_keys=_integer("api_keys", raw_caps.get("api_keys")),
        accounts=_integer("accounts", raw_caps.get("accounts")),
        provider_credits=_integer(
            "provider_credits",
            raw_caps.get("provider_credits"),
        ),
        cash_spend_usd_cents=_integer(
            "cash_spend_usd_cents",
            raw_caps.get("cash_spend_usd_cents"),
        ),
        wallet_signer_transaction_actions=_integer(
            "wallet_signer_transaction_actions",
            raw_caps.get("wallet_signer_transaction_actions"),
        ),
    )
    if caps != PilotCaps(
        http_requests_total_max=MAX_HTTP_REQUESTS,
        concurrency=1,
        retries=RETRIES,
        wall_seconds_max=MAX_WALL_SECONDS,
        request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        minimum_interval_seconds=MINIMUM_INTERVAL_SECONDS,
        received_response_bytes_max=MAX_RECEIVED_BYTES,
        durable_raw_bytes_max=MAX_DURABLE_BYTES,
        api_keys=0,
        accounts=0,
        provider_credits=0,
        cash_spend_usd_cents=0,
        wallet_signer_transaction_actions=0,
    ):
        raise QuoteTransportContractError("pilot_caps_drift")
    if (
        raw_caps.get("selected_mints") != 1
        or raw_caps.get("buy_requests") != 4
        or raw_caps.get("dependent_sell_requests_max") != 4
    ):
        raise QuoteTransportContractError("pilot_request_panel_caps_drift")

    storage = _mapping("storage", root["storage"])
    logical_root = _text("storage.logical_root", storage.get("logical_root"))
    if logical_root != f"{RAW_LOGICAL_ROOT}/run={run_id}":
        raise QuoteTransportContractError("logical_root_drift")
    authority = _mapping("authority", root["authority"])
    if (
        authority.get("source") != "EXPLICIT_USER"
        or authority.get("approved_phrase") != EXTERNAL_AUTHORITY_PHRASE
        or authority.get("network") is not True
        or authority.get("public_keyless_provider_calls") is not True
        or authority.get("raw_write") is not True
        or authority.get("credential_use") is not False
        or authority.get("commit") is not False
        or authority.get("push") is not False
        or authority.get("pull_request") is not False
        or authority.get("merge") is not False
    ):
        raise QuoteTransportContractError("pilot_authority_drift")
    return PilotPlan(
        atom_id=_text("atom_id", root["atom_id"]),
        run_id=run_id,
        selected_mint=mint,
        selected_mint_decimals=_integer(
            "selection.decimals",
            selection.get("decimals"),
        ),
        selection_rule=_text("selection.rule", selection.get("rule")),
        source_asset_id=_text(
            "selection.source_asset_id",
            selection.get("source_asset_id"),
        ),
        source_run_id=_text(
            "selection.source_run_id",
            selection.get("source_run_id"),
        ),
        source_partition_sha256=_text(
            "selection.source_partition_sha256",
            selection.get("source_partition_sha256"),
        ),
        source_raw_event_id=_text(
            "selection.source_raw_event_id",
            selection.get("source_raw_event_id"),
        ),
        source_slot=_integer(
            "selection.source_slot",
            selection.get("source_slot"),
        ),
        base_url=_text(
            "provider_surface.base_url",
            surface.get("base_url"),
        ),
        path=_text("provider_surface.path", surface.get("path")),
        quote_mint=_text("panels.quote_mint", panels.get("quote_mint")),
        quote_decimals=_integer(
            "panels.quote_decimals",
            panels.get("quote_decimals"),
        ),
        slippage_bps=_integer(
            "panels.slippage_bps",
            panels.get("slippage_bps"),
        ),
        buy_input_atomic=buy_input_atomic,
        caps=caps,
        logical_root=logical_root,
        raw_partition=_text(
            "storage.raw_partition",
            storage.get("raw_partition"),
        ),
        projection_database=_text(
            "storage.projection_database",
            storage.get("projection_database"),
        ),
        manifest_location=_text(
            "storage.manifest",
            storage.get("manifest"),
        ),
        receipt_location=_text(
            "storage.receipt",
            storage.get("receipt"),
        ),
        plan_sha256=actual_hash,
    )


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise QuoteTransportStopError("redirect_forbidden")


def _request_url(request: QuoteRequest) -> str:
    query = urllib.parse.urlencode(
        [
            ("inputMint", request.input_mint),
            ("outputMint", request.output_mint),
            ("amount", str(request.input_requested_atomic)),
            ("slippageBps", str(request.slippage_bps)),
            ("swapMode", "ExactIn"),
        ],
        quote_via=urllib.parse.quote,
    )
    url = f"{BASE_URL}{ENDPOINT}?{query}"
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.jup.ag"
        or parsed.port is not None
        or parsed.path != ENDPOINT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise QuoteTransportContractError("request_url_scope_drift")
    return url


def _response_body(
    response: Any,
    *,
    remaining_bytes: int,
) -> tuple[bytes, bool]:
    if remaining_bytes <= 0:
        return b"", True
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            return b"", True
        if declared < 0 or declared > remaining_bytes:
            return b"", True
    body = response.read(remaining_bytes)
    if len(body) > remaining_bytes:
        raise QuoteTransportStopError("response_read_exceeded_bound")
    exhausted = len(body) == remaining_bytes and (
        content_length is None or int(content_length) > remaining_bytes
    )
    return body, exhausted


class BoundedQuoteTransport:
    """Sequential zero-retry HTTPS transport scoped to one exact host/path."""

    def __init__(
        self,
        *,
        gate: ExternalExecutionGate,
        opener: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not isinstance(gate, ExternalExecutionGate):
            raise ExternalAuthorityRequiredError(
                "external_execution_gate_required"
            )
        self._opener = (
            opener
            if opener is not None
            else urllib.request.build_opener(_NoRedirectHandler())
        )
        self._clock = clock
        self._sleeper = sleeper
        self._now = now
        self._started = clock()
        self._last_attempt_started: float | None = None
        self._attempts = 0
        self._received_bytes = 0

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def received_bytes(self) -> int:
        return self._received_bytes

    def _pace_and_reserve(self) -> datetime:
        if self._attempts >= MAX_HTTP_REQUESTS:
            raise QuoteTransportStopError("http_request_cap_exhausted")
        elapsed = self._clock() - self._started
        if elapsed >= MAX_WALL_SECONDS:
            raise QuoteTransportStopError("wall_time_cap_exhausted")
        if self._last_attempt_started is not None:
            wait = MINIMUM_INTERVAL_SECONDS - (
                self._clock() - self._last_attempt_started
            )
            if wait > 0:
                self._sleeper(wait)
        if self._clock() - self._started >= MAX_WALL_SECONDS:
            raise QuoteTransportStopError("wall_time_cap_exhausted")
        self._last_attempt_started = self._clock()
        self._attempts += 1
        return self._now()

    def execute(self, request: QuoteRequest) -> HttpCapture:
        requested_at = self._pace_and_reserve()
        remaining = MAX_RECEIVED_BYTES - self._received_bytes
        if remaining <= 0:
            raise QuoteTransportStopError("response_byte_cap_exhausted")
        outgoing = urllib.request.Request(
            _request_url(request),
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "solana-alpha-lab-task10/2.0",
            },
        )
        status_code: int | None = None
        body: JsonValue | bytes | str | None
        timed_out = False
        stop_reason: str | None = None
        try:
            with self._opener.open(
                outgoing,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                status_code = int(response.status)
                captured, exhausted = _response_body(
                    response,
                    remaining_bytes=remaining,
                )
                self._received_bytes += len(captured)
                if exhausted:
                    body = {
                        "response_body_present": bool(captured),
                        "response_bytes_retained": len(captured),
                        "transport_disposition": (
                            "RESPONSE_BYTE_CAP_EXHAUSTED"
                        ),
                    }
                    stop_reason = "RESPONSE_BYTE_CAP_EXHAUSTED"
                else:
                    body = captured
        except urllib.error.HTTPError as exc:
            status_code = int(exc.code)
            captured, exhausted = _response_body(
                exc,
                remaining_bytes=remaining,
            )
            self._received_bytes += len(captured)
            if exhausted:
                body = {
                    "http_status": status_code,
                    "response_body_present": bool(captured),
                    "response_bytes_retained": len(captured),
                    "transport_disposition": (
                        "RESPONSE_BYTE_CAP_EXHAUSTED"
                    ),
                }
                stop_reason = "RESPONSE_BYTE_CAP_EXHAUSTED"
            else:
                body = captured
        except QuoteTransportStopError:
            raise
        except (TimeoutError, socket.timeout):
            body = None
            timed_out = True
        except (
            urllib.error.URLError,
            ssl.SSLError,
            socket.gaierror,
            ConnectionError,
            OSError,
        ):
            body = {
                "response_body_present": False,
                "transport_disposition": "DNS_TLS_OR_TRANSPORT_FAILURE",
            }
        response_at = None if timed_out else self._now()
        reliable_at = response_at if response_at is not None else self._now()
        available_at = max(reliable_at, self._now())
        ingested_at = max(available_at, self._now())
        return HttpCapture(
            observation=TransportObservation(
                requested_at=requested_at,
                response_at=response_at,
                first_reliable_available_at=reliable_at,
                available_to_strategy_at=available_at,
                ingested_at=ingested_at,
                http_status_code=status_code,
                response_body=body,
                timed_out=timed_out,
                stale=False,
            ),
            received_bytes=(
                0
                if body is None or isinstance(body, Mapping)
                else len(body.encode("utf-8"))
                if isinstance(body, str)
                else len(body)
            ),
            transport_stop_reason=stop_reason,
        )


def _insert_model(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    model: Any,
) -> None:
    payload = model.model_dump(mode="python")
    columns = tuple(payload)
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO {relation} ({', '.join(columns)}) "
        f"VALUES ({placeholders})",
        [payload[name] for name in columns],
    )


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise QuoteTransportContractError(
            "immutable_output_already_exists"
        ) from exc


class DurableQuotePilotSink:
    """Persist raw envelopes and QuoteAttempt rows inside one capped run."""

    def __init__(
        self,
        *,
        raw_root: Path,
        schema_path: Path,
        plan: PilotPlan,
    ) -> None:
        if not raw_root.is_absolute():
            raise QuoteTransportContractError("raw_root_must_be_absolute")
        if not schema_path.is_absolute() or not schema_path.is_file():
            raise QuoteTransportContractError(
                "schema_path_must_be_existing_absolute_file"
            )
        self.plan = plan
        self.raw_root = raw_root
        self.schema_path = schema_path
        self.run_directory = (
            raw_root / RAW_LOGICAL_ROOT / f"run={plan.run_id}"
        )
        if self.run_directory.exists():
            raise QuoteTransportContractError(
                "run_output_already_exists"
            )
        self._projections: list[QuoteProjection] = []
        self._finalized = False

    @property
    def logical_root(self) -> str:
        return self.plan.logical_root

    def append(self, projection: QuoteProjection) -> None:
        if self._finalized:
            raise QuoteTransportContractError("sink_already_finalized")
        if not isinstance(projection, QuoteProjection):
            raise QuoteTransportContractError(
                "projection_must_be_quote_projection"
            )
        if any(
            item.quote_attempt.idempotency_key
            == projection.quote_attempt.idempotency_key
            for item in self._projections
        ):
            raise QuoteTransportContractError(
                "duplicate_quote_idempotency_key"
            )
        self._projections.append(projection)

    def _write_projection_database(self, path: Path) -> tuple[str, int]:
        connection = duckdb.connect(
            str(path),
            config={"default_block_size": "16384"},
        )
        try:
            connection.execute(
                self.schema_path.read_text(encoding="utf-8")
            )
            for projection in self._projections:
                _insert_model(
                    connection,
                    "raw_api_events",
                    projection.raw_event,
                )
                _insert_model(
                    connection,
                    "quote_attempts",
                    projection.quote_attempt,
                )
            connection.execute("CHECKPOINT")
        finally:
            connection.close()
        size = path.stat().st_size
        if size > MAX_PROJECTION_DATABASE_BYTES:
            raise QuoteTransportStopError(
                "projection_database_byte_cap_exhausted"
            )
        connection = duckdb.connect(str(path), read_only=True)
        try:
            raw_count = connection.execute(
                "SELECT COUNT(*) FROM raw_api_events"
            ).fetchone()[0]
            quote_count = connection.execute(
                "SELECT COUNT(*) FROM quote_attempts"
            ).fetchone()[0]
            joined = connection.execute(
                """
                SELECT COUNT(*)
                FROM quote_attempts AS q
                JOIN raw_api_events AS r USING (raw_event_id)
                """
            ).fetchone()[0]
            execution_count = connection.execute(
                "SELECT COUNT(*) FROM execution_attempts"
            ).fetchone()[0]
        finally:
            connection.close()
        expected = len(self._projections)
        if (
            raw_count != expected
            or quote_count != expected
            or joined != expected
            or execution_count != 0
        ):
            raise QuoteTransportContractError(
                "projection_database_readback_mismatch"
            )
        return _sha256_file(path), size

    def finalize(self, summary: PilotRunSummary) -> PilotRunSummary:
        if self._finalized:
            raise QuoteTransportContractError("sink_already_finalized")
        if not self._projections:
            raise QuoteTransportContractError("sink_has_no_evidence")
        self.run_directory.mkdir(parents=True, exist_ok=False)
        raw_policy = StorageBudgetPolicy(
            max_partition_bytes=MAX_RAW_PARTITION_BYTES,
            max_dataset_bytes=MAX_RAW_PARTITION_BYTES,
            min_free_bytes=1_073_741_824,
            warning_threshold_bps=9000,
            forecast_partition_count=1,
        )
        created_at = max(
            item.raw_event.ingested_at for item in self._projections
        )
        reliable_at = max(
            created_at,
            *(
                item.raw_event.first_reliable_available_at
                for item in self._projections
            ),
        )
        try:
            raw_result = write_budgeted_raw_event_partition(
                root=self.run_directory,
                dataset_id=DATASET_ID,
                dataset_version=DATASET_VERSION,
                partition_id=f"{self.plan.run_id}-quotes",
                logical_location=self.plan.raw_partition,
                events=[
                    item.raw_event for item in self._projections
                ],
                created_at=created_at,
                first_reliable_available_at=reliable_at,
                budget_policy=raw_policy,
            )
        except StorageBudgetExceededError as exc:
            raise QuoteTransportStopError(
                "raw_partition_byte_cap_exhausted"
            ) from exc
        observed = verify_raw_event_partition(
            root=self.run_directory,
            manifest=raw_result.manifest,
        )
        if len(observed) != len(self._projections):
            raise QuoteTransportContractError(
                "raw_partition_readback_count_mismatch"
            )
        database_path = self.run_directory / self.plan.projection_database
        database_path.parent.mkdir(parents=True, exist_ok=False)
        database_hash, database_size = self._write_projection_database(
            database_path
        )
        manifest_bytes = (
            canonical_manifest_bytes(raw_result.manifest) + b"\n"
        )
        manifest_path = self.run_directory / self.plan.manifest_location
        _write_new(manifest_path, manifest_bytes)

        provisional = replace(
            summary,
            stored_events=len(observed),
            raw_partition_sha256=raw_result.manifest.file_sha256,
            raw_content_sha256=raw_result.manifest.content_sha256,
            projection_database_sha256=database_hash,
        )
        receipt_claim = {
            "atom_id": self.plan.atom_id,
            "dataset_id": DATASET_ID,
            "dataset_version": DATASET_VERSION,
            "files": [
                {
                    "bytes": raw_result.file_size_bytes,
                    "logical_path": self.plan.raw_partition,
                    "sha256": raw_result.manifest.file_sha256,
                },
                {
                    "bytes": database_size,
                    "logical_path": self.plan.projection_database,
                    "sha256": database_hash,
                },
                {
                    "bytes": len(manifest_bytes),
                    "logical_path": self.plan.manifest_location,
                    "sha256": hashlib.sha256(
                        manifest_bytes
                    ).hexdigest(),
                },
            ],
            "plan_sha256": self.plan.plan_sha256,
            "provider": PROVIDER,
            "provider_version": PROVIDER_VERSION,
            "selected_mint": self.plan.selected_mint,
            "selected_mint_decimals": (
                self.plan.selected_mint_decimals
            ),
            "source_asset_id": self.plan.source_asset_id,
            "source_raw_event_id": self.plan.source_raw_event_id,
            "source_run_id": self.plan.source_run_id,
        }
        stored_without_receipt = (
            raw_result.file_size_bytes
            + database_size
            + len(manifest_bytes)
        )
        expected_total = stored_without_receipt
        receipt_bytes = b""
        for _ in range(8):
            receipt = {
                **replace(
                    provisional,
                    stored_bytes=expected_total,
                ).safe_receipt(),
                **receipt_claim,
            }
            receipt_bytes = _canonical_json_bytes(receipt) + b"\n"
            candidate_total = stored_without_receipt + len(receipt_bytes)
            if candidate_total == expected_total:
                break
            expected_total = candidate_total
        else:
            raise QuoteTransportContractError(
                "receipt_size_fixed_point_failed"
            )
        if len(manifest_bytes) + len(receipt_bytes) > METADATA_RESERVE_BYTES:
            raise QuoteTransportStopError(
                "storage_metadata_reserve_exhausted"
            )
        receipt_path = self.run_directory / self.plan.receipt_location
        _write_new(receipt_path, receipt_bytes)
        stored_bytes = sum(
            path.stat().st_size
            for path in self.run_directory.rglob("*")
            if path.is_file()
        )
        if stored_bytes > MAX_DURABLE_BYTES:
            raise QuoteTransportStopError(
                "durable_raw_byte_cap_exhausted"
            )
        self._finalized = True
        if stored_bytes != expected_total:
            raise QuoteTransportContractError(
                "durable_byte_readback_mismatch"
            )
        return replace(provisional, stored_bytes=stored_bytes)


@dataclass(slots=True)
class InMemoryQuoteSink:
    """Test sink that preserves the same append/finalize interface."""

    run_id: str = "t10a6-20260728T000000Z"
    projections: list[QuoteProjection] = field(default_factory=list)

    @property
    def logical_root(self) -> str:
        return f"{RAW_LOGICAL_ROOT}/run={self.run_id}"

    def append(self, projection: QuoteProjection) -> None:
        self.projections.append(projection)

    def finalize(self, summary: PilotRunSummary) -> PilotRunSummary:
        return replace(summary, stored_events=len(self.projections))


class QuotePilotRunner:
    """Execute the frozen buy/reverse-sell panel under exact caps."""

    def __init__(
        self,
        *,
        plan: PilotPlan,
        transport: QuoteTransport,
        sink: QuoteSink,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.plan = plan
        self.transport = transport
        self.sink = sink
        self.clock = clock

    def run(self) -> PilotRunSummary:
        started = self.clock()
        terminal_counts: Counter[str] = Counter()
        buy_attempts = 0
        sell_attempts = 0
        sell_not_attempted = 0
        stop_reason: str | None = None
        requests = build_buy_panel_requests(
            selected_output_mint=self.plan.selected_mint,
            output_decimals=self.plan.selected_mint_decimals,
            slippage_bps=self.plan.slippage_bps,
        )
        if tuple(
            request.input_requested_atomic for request in requests
        ) != self.plan.buy_input_atomic:
            raise QuoteTransportContractError("runtime_buy_panel_drift")

        for panel_index, buy_request in enumerate(requests):
            if self.clock() - started >= self.plan.caps.wall_seconds_max:
                stop_reason = "WALL_TIME_CAP_EXHAUSTED"
                break
            capture = self.transport.execute(buy_request)
            buy_attempts += 1
            buy_projection = project_quote_observation(
                buy_request,
                capture.observation,
            )
            self.sink.append(buy_projection)
            terminal_counts[str(buy_projection.quote_attempt.status)] += 1
            stop_reason = (
                capture.transport_stop_reason
                or buy_projection.stop_reason
            )
            if stop_reason is not None:
                break

            sell_decision: DependentSellDecision = decide_dependent_sell(
                buy_projection,
                attempt_ordinal=5 + panel_index,
            )
            if sell_decision.request is None:
                sell_not_attempted += 1
                continue
            capture = self.transport.execute(sell_decision.request)
            sell_attempts += 1
            sell_projection = project_quote_observation(
                sell_decision.request,
                capture.observation,
            )
            self.sink.append(sell_projection)
            terminal_counts[str(sell_projection.quote_attempt.status)] += 1
            stop_reason = (
                capture.transport_stop_reason
                or sell_projection.stop_reason
            )
            if stop_reason is not None:
                break

        elapsed = self.clock() - started
        if self.transport.attempts > self.plan.caps.http_requests_total_max:
            raise QuoteTransportContractError("request_cap_exceeded")
        if self.transport.received_bytes > (
            self.plan.caps.received_response_bytes_max
        ):
            raise QuoteTransportContractError(
                "response_byte_cap_exceeded"
            )
        if elapsed > self.plan.caps.wall_seconds_max:
            stop_reason = stop_reason or "WALL_TIME_CAP_EXHAUSTED"
        status = "COMPLETE" if stop_reason is None else "STOPPED"
        summary = PilotRunSummary(
            run_id=self.plan.run_id,
            status=status,
            stop_reason=stop_reason,
            provider_calls=self.transport.attempts,
            received_bytes=self.transport.received_bytes,
            elapsed_seconds=round(elapsed, 6),
            buy_attempts=buy_attempts,
            sell_attempts=sell_attempts,
            sell_not_attempted=sell_not_attempted,
            terminal_counts=dict(terminal_counts),
            logical_root=self.sink.logical_root,
        )
        return self.sink.finalize(summary)


def safe_preflight_summary(plan: PilotPlan) -> dict[str, JsonValue]:
    return {
        "accounts": plan.caps.accounts,
        "api_keys": plan.caps.api_keys,
        "cash_spend_usd_cents": plan.caps.cash_spend_usd_cents,
        "http_requests_total_max": plan.caps.http_requests_total_max,
        "network_authorized_only_after_runtime_gate": True,
        "provider_credits": plan.caps.provider_credits,
        "raw_write_authorized_only_after_runtime_gate": True,
        "received_response_bytes_max": (
            plan.caps.received_response_bytes_max
        ),
        "retries": plan.caps.retries,
        "run_id": plan.run_id,
        "selected_mint": plan.selected_mint,
        "wallet_signer_transaction_actions": (
            plan.caps.wallet_signer_transaction_actions
        ),
    }
