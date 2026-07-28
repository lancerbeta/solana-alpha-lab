"""Bounded Helius standard-RPC transport for TASK-11 entity inputs."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeAlias

from solana_alpha_lab.contracts.schema_v1 import RawResponseStatus
from solana_alpha_lab.entity_inputs import (
    ConfidenceLevel,
    EvidenceClass,
    ExclusionAssessment,
    ExclusionDisposition,
    HolderAccountObservation,
    HolderConcentrationMetrics,
    HolderSnapshotInput,
    calculate_holder_metrics,
)
from solana_alpha_lab.provider_smoke_transport import (
    BoundRequest,
    HttpExchange,
    TransportResponse,
    stdlib_http_exchange,
)
from solana_alpha_lab.storage import (
    StorageBudgetPolicy,
    build_raw_api_event,
    verify_raw_event_partition,
    write_budgeted_raw_event_partition,
)

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

TRANSPORT_CONTRACT_VERSION = "1.0"
PLAN_FIXTURE_SHA256 = (
    "ff0524ab2a77b517f8796ff54a753842306b83de9be6e8d4c391776afba0cf1d"
)
EXTERNAL_AUTHORITY_PHRASE = "T11-A3_HELIUS_3CALL_RAW_PILOT_V1"
HELIUS_RPC_BASE_URL = "https://mainnet.helius-rpc.com/"
EXPECTED_HOST = "mainnet.helius-rpc.com"
EXPECTED_METHODS = (
    "getTokenSupply",
    "getTokenLargestAccounts",
    "getMultipleAccounts",
)
EXPECTED_MANAGED_FILES = (
    "src/solana_alpha_lab/entity_input_transport.py",
    "scripts/run_task11_entity_input_probe.py",
    "tests/fixtures/task11/entity_input_pilot_plan_v1.json",
    "tests/test_task11_entity_input_transport.py",
)
RUN_ID_RE = re.compile(r"t11a3-[0-9]{8}T[0-9]{6}Z")
PUBLIC_CODE_RE = re.compile(r"[A-Za-z0-9_.:-]{1,160}")


class EntityTransportContractError(ValueError):
    """The frozen transport plan or provider payload is incoherent."""


class ExternalAuthorityRequiredError(EntityTransportContractError):
    """The exact external tripwire is absent."""


class AccessAttestationError(EntityTransportContractError):
    """The user has not attested enough dashboard headroom."""


class RpcProviderError(EntityTransportContractError):
    """A JSON-RPC error object was returned instead of a result."""


class RawStorageError(RuntimeError):
    """The immutable raw evidence could not be persisted safely."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EntityTransportContractError(message)


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name}_must_be_mapping")
    _require(
        all(isinstance(key, str) for key in value),
        f"{name}_keys_must_be_text",
    )
    return value


def _sequence(name: str, value: object) -> Sequence[Any]:
    _require(
        not isinstance(value, (str, bytes)) and isinstance(value, Sequence),
        f"{name}_must_be_sequence",
    )
    return value


def _text(name: str, value: object) -> str:
    _require(isinstance(value, str) and bool(value), f"{name}_must_be_text")
    return value


def _integer(name: str, value: object) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        f"{name}_must_be_nonnegative_integer",
    )
    return value


def _exact_keys(
    name: str,
    value: Mapping[str, Any],
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    keys = frozenset(value)
    _require(required.issubset(keys), f"{name}_required_keys_missing")
    _require(keys.issubset(required | optional), f"{name}_unknown_keys")


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
        raise EntityTransportContractError(
            "json_canonicalization_failed"
        ) from exc


def _safe_code(value: str) -> str:
    return value if PUBLIC_CODE_RE.fullmatch(value) else "REDACTED"


@dataclass(frozen=True, slots=True)
class EntityPilotPlan:
    selected_mint: str
    selected_mint_decimals: int
    provider_id: str
    methods: tuple[str, str, str]
    commitment: str
    provider_calls: int
    retries: int
    timeout_seconds_per_call: int
    elapsed_seconds: int
    response_bytes_each: int
    received_bytes_total: int
    stored_bytes_total: int
    modeled_credits_per_call: int
    modeled_credits_total: int
    minimum_free_bytes: int
    concurrency: int
    cash_spend_usd_cents: int
    dataset_id: str
    dataset_version: str
    logical_root: str
    partition_max_bytes: int
    parquet_dataset_max_bytes: int
    authority_phrase: str

    def safe_preflight(self) -> dict[str, JsonValue]:
        return {
            "authority_phrase": self.authority_phrase,
            "cash_spend_usd_cents": self.cash_spend_usd_cents,
            "commitment": self.commitment,
            "dataset_id": self.dataset_id,
            "elapsed_seconds": self.elapsed_seconds,
            "logical_root": self.logical_root,
            "methods": list(self.methods),
            "modeled_credits_total": self.modeled_credits_total,
            "provider_calls": self.provider_calls,
            "provider_id": self.provider_id,
            "received_bytes_total": self.received_bytes_total,
            "retries": self.retries,
            "selected_mint": self.selected_mint,
            "stored_bytes_total": self.stored_bytes_total,
            "timeout_seconds_per_call": self.timeout_seconds_per_call,
        }


def load_entity_pilot_plan(path: Path) -> EntityPilotPlan:
    payload = path.read_bytes()
    _require(
        hashlib.sha256(payload).hexdigest() == PLAN_FIXTURE_SHA256,
        "pilot_plan_sha256_drift",
    )
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise EntityTransportContractError("pilot_plan_json_invalid") from exc
    root = _mapping("plan", document)
    _require(
        root.get("schema") == "solana_alpha_lab.entity_input_pilot_plan",
        "pilot_plan_schema_drift",
    )
    _require(root.get("schema_version") == "1.0", "pilot_plan_version_drift")
    _require(root.get("task_id") == "TASK-11", "pilot_plan_task_drift")
    _require(root.get("atom_id") == "T11-A3", "pilot_plan_atom_drift")
    provider = _mapping("provider", root.get("provider"))
    caps = _mapping("caps", root.get("caps"))
    storage = _mapping("storage", root.get("storage"))
    authority = _mapping("authority", root.get("authority"))
    managed_files = tuple(
        _text("managed_tracked_file", value)
        for value in _sequence(
            "managed_tracked_files",
            root.get("managed_tracked_files"),
        )
    )
    _require(
        managed_files == EXPECTED_MANAGED_FILES,
        "managed_tracked_file_inventory_drift",
    )
    methods = tuple(
        _text("provider.method", value)
        for value in _sequence("provider.methods", provider.get("methods"))
    )
    _require(methods == EXPECTED_METHODS, "provider_method_inventory_drift")
    plan = EntityPilotPlan(
        selected_mint=_text("selected_mint", root.get("selected_mint")),
        selected_mint_decimals=_integer(
            "selected_mint_decimals",
            root.get("selected_mint_decimals"),
        ),
        provider_id=_text("provider_id", provider.get("provider_id")),
        methods=methods,
        commitment=_text("commitment", provider.get("commitment")),
        provider_calls=_integer("provider_calls", caps.get("provider_calls")),
        retries=_integer("retries", caps.get("retries")),
        timeout_seconds_per_call=_integer(
            "timeout_seconds_per_call",
            caps.get("timeout_seconds_per_call"),
        ),
        elapsed_seconds=_integer(
            "elapsed_seconds",
            caps.get("elapsed_seconds"),
        ),
        response_bytes_each=_integer(
            "response_bytes_each",
            caps.get("response_bytes_each"),
        ),
        received_bytes_total=_integer(
            "received_bytes_total",
            caps.get("received_bytes_total"),
        ),
        stored_bytes_total=_integer(
            "stored_bytes_total",
            caps.get("stored_bytes_total"),
        ),
        modeled_credits_per_call=_integer(
            "modeled_credits_per_call",
            caps.get("modeled_credits_per_call"),
        ),
        modeled_credits_total=_integer(
            "modeled_credits_total",
            caps.get("modeled_credits_total"),
        ),
        minimum_free_bytes=_integer(
            "minimum_free_bytes",
            caps.get("minimum_free_bytes"),
        ),
        concurrency=_integer("concurrency", caps.get("concurrency")),
        cash_spend_usd_cents=_integer(
            "cash_spend_usd_cents",
            caps.get("cash_spend_usd_cents"),
        ),
        dataset_id=_text("dataset_id", storage.get("dataset_id")),
        dataset_version=_text(
            "dataset_version",
            storage.get("dataset_version"),
        ),
        logical_root=_text("logical_root", storage.get("logical_root")),
        partition_max_bytes=_integer(
            "partition_max_bytes",
            storage.get("partition_max_bytes"),
        ),
        parquet_dataset_max_bytes=_integer(
            "parquet_dataset_max_bytes",
            storage.get("parquet_dataset_max_bytes"),
        ),
        authority_phrase=_text(
            "authority_phrase",
            authority.get("authority_phrase"),
        ),
    )
    _require(plan.selected_mint_decimals <= 30, "mint_decimals_out_of_range")
    _require(plan.provider_id == "HELIUS_STANDARD_SOLANA_RPC", "provider_drift")
    _require(plan.commitment == "confirmed", "commitment_drift")
    _require(plan.provider_calls == 3, "provider_call_cap_drift")
    _require(plan.retries == 0, "retry_cap_drift")
    _require(plan.concurrency == 1, "concurrency_drift")
    _require(plan.cash_spend_usd_cents == 0, "cash_cap_drift")
    _require(
        plan.modeled_credits_total
        == plan.provider_calls * plan.modeled_credits_per_call,
        "modeled_credit_cap_incoherent",
    )
    _require(
        plan.authority_phrase == EXTERNAL_AUTHORITY_PHRASE,
        "authority_phrase_drift",
    )
    _require(
        plan.partition_max_bytes <= plan.parquet_dataset_max_bytes,
        "partition_budget_exceeds_dataset_budget",
    )
    _require(
        plan.parquet_dataset_max_bytes < plan.stored_bytes_total,
        "receipt_storage_reserve_missing",
    )
    return plan


@dataclass(frozen=True, slots=True)
class ExternalExecutionGate:
    authority_phrase: str

    def require(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise ExternalAuthorityRequiredError(
                "external_authority_phrase_mismatch"
            )


@dataclass(frozen=True, slots=True, repr=False)
class HeliusCredential:
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        _require(
            isinstance(self.value, str)
            and self.value == self.value.strip()
            and 8 <= len(self.value) <= 512
            and all(32 < ord(character) < 127 for character in self.value),
            "helius_credential_invalid",
        )

    def __repr__(self) -> str:
        return "HeliusCredential(<redacted>)"


@dataclass(frozen=True, slots=True)
class AccessAttestation:
    dashboard_readback_completed: bool
    helius_credits_remaining: int

    def require(self, plan: EntityPilotPlan) -> None:
        if not self.dashboard_readback_completed:
            raise AccessAttestationError("dashboard_readback_required")
        if (
            isinstance(self.helius_credits_remaining, bool)
            or not isinstance(self.helius_credits_remaining, int)
            or self.helius_credits_remaining < plan.modeled_credits_total
        ):
            raise AccessAttestationError("helius_credit_headroom_insufficient")


@dataclass(frozen=True, slots=True)
class TokenSupplyObservation:
    amount_atomic: int
    decimals: int
    context_slot: int


@dataclass(frozen=True, slots=True)
class LargestTokenAccount:
    address: str
    amount_atomic: int
    decimals: int


@dataclass(frozen=True, slots=True)
class LargestAccountsObservation:
    accounts: tuple[LargestTokenAccount, ...]
    context_slot: int


@dataclass(frozen=True, slots=True)
class OwnerResolution:
    token_account: str
    owner: str
    amount_atomic: int
    decimals: int


@dataclass(frozen=True, slots=True)
class OwnersObservation:
    owners: tuple[OwnerResolution, ...]
    context_slot: int


def _rpc_result(body: bytes, *, expected_id: int) -> Mapping[str, Any]:
    try:
        document = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EntityTransportContractError("rpc_response_json_invalid") from exc
    root = _mapping("rpc_response", document)
    _exact_keys(
        "rpc_response",
        root,
        required=frozenset({"jsonrpc", "id"}),
        optional=frozenset({"result", "error"}),
    )
    _require(root.get("jsonrpc") == "2.0", "rpc_jsonrpc_version_drift")
    _require(root.get("id") == expected_id, "rpc_response_id_drift")
    _require(
        ("result" in root) != ("error" in root),
        "rpc_result_error_exclusivity_violation",
    )
    if "error" in root:
        error = _mapping("rpc_error", root["error"])
        code = error.get("code")
        _require(
            isinstance(code, int) and not isinstance(code, bool),
            "rpc_error_code_invalid",
        )
        _text("rpc_error.message", error.get("message"))
        raise RpcProviderError(f"rpc_error_{code}")
    return _mapping("rpc_result", root["result"])


def _context_slot(result: Mapping[str, Any]) -> int:
    context = _mapping("rpc_context", result.get("context"))
    _exact_keys(
        "rpc_context",
        context,
        required=frozenset({"slot"}),
        optional=frozenset({"apiVersion"}),
    )
    return _integer("rpc_context.slot", context["slot"])


def parse_token_supply(
    body: bytes,
    *,
    expected_id: int,
    expected_decimals: int,
) -> TokenSupplyObservation:
    result = _rpc_result(body, expected_id=expected_id)
    _exact_keys(
        "token_supply_result",
        result,
        required=frozenset({"context", "value"}),
    )
    value = _mapping("token_supply_value", result["value"])
    _exact_keys(
        "token_supply_value",
        value,
        required=frozenset(
            {"amount", "decimals", "uiAmount", "uiAmountString"}
        ),
    )
    amount = _text("token_supply.amount", value["amount"])
    _require(amount.isdigit(), "token_supply_amount_invalid")
    decimals = _integer("token_supply.decimals", value["decimals"])
    _require(decimals == expected_decimals, "mint_decimals_drift")
    return TokenSupplyObservation(
        amount_atomic=int(amount),
        decimals=decimals,
        context_slot=_context_slot(result),
    )


def parse_largest_accounts(
    body: bytes,
    *,
    expected_id: int,
    expected_decimals: int,
) -> LargestAccountsObservation:
    result = _rpc_result(body, expected_id=expected_id)
    _exact_keys(
        "largest_accounts_result",
        result,
        required=frozenset({"context", "value"}),
    )
    values = _sequence("largest_accounts_value", result["value"])
    _require(1 <= len(values) <= 20, "largest_account_count_out_of_range")
    accounts: list[LargestTokenAccount] = []
    for index, item in enumerate(values):
        row = _mapping(f"largest_account_{index}", item)
        _exact_keys(
            f"largest_account_{index}",
            row,
            required=frozenset(
                {
                    "address",
                    "amount",
                    "decimals",
                    "uiAmount",
                    "uiAmountString",
                }
            ),
        )
        amount = _text(f"largest_account_{index}.amount", row["amount"])
        _require(amount.isdigit(), "largest_account_amount_invalid")
        decimals = _integer(
            f"largest_account_{index}.decimals",
            row["decimals"],
        )
        _require(decimals == expected_decimals, "mint_decimals_drift")
        accounts.append(
            LargestTokenAccount(
                address=_text(
                    f"largest_account_{index}.address",
                    row["address"],
                ),
                amount_atomic=int(amount),
                decimals=decimals,
            )
        )
    _require(
        len({item.address for item in accounts}) == len(accounts),
        "duplicate_largest_token_account",
    )
    return LargestAccountsObservation(
        accounts=tuple(accounts),
        context_slot=_context_slot(result),
    )


def parse_owner_accounts(
    body: bytes,
    *,
    expected_id: int,
    expected_mint: str,
    expected_accounts: Sequence[LargestTokenAccount],
) -> OwnersObservation:
    result = _rpc_result(body, expected_id=expected_id)
    _exact_keys(
        "owners_result",
        result,
        required=frozenset({"context", "value"}),
    )
    values = _sequence("owners_value", result["value"])
    _require(
        len(values) == len(expected_accounts),
        "incomplete_owner_response",
    )
    owners: list[OwnerResolution] = []
    for index, (item, expected) in enumerate(
        zip(values, expected_accounts, strict=True)
    ):
        _require(item is not None, "owner_account_missing")
        account = _mapping(f"owner_account_{index}", item)
        _exact_keys(
            f"owner_account_{index}",
            account,
            required=frozenset(
                {"data", "executable", "lamports", "owner", "rentEpoch"}
            ),
            optional=frozenset({"space"}),
        )
        data = _mapping(f"owner_account_{index}.data", account["data"])
        _exact_keys(
            f"owner_account_{index}.data",
            data,
            required=frozenset({"program", "parsed", "space"}),
        )
        _require(
            data["program"] in {"spl-token", "spl-token-2022"},
            "owner_account_program_invalid",
        )
        parsed = _mapping(
            f"owner_account_{index}.parsed",
            data["parsed"],
        )
        _exact_keys(
            f"owner_account_{index}.parsed",
            parsed,
            required=frozenset({"info", "type"}),
        )
        _require(parsed["type"] == "account", "parsed_account_type_invalid")
        info = _mapping(f"owner_account_{index}.info", parsed["info"])
        _require(
            {"mint", "owner", "tokenAmount"}.issubset(info),
            "parsed_account_info_required_keys_missing",
        )
        _require(info["mint"] == expected_mint, "owner_account_mint_drift")
        token_amount = _mapping(
            f"owner_account_{index}.tokenAmount",
            info["tokenAmount"],
        )
        amount = _text(
            f"owner_account_{index}.tokenAmount.amount",
            token_amount.get("amount"),
        )
        _require(amount.isdigit(), "owner_account_amount_invalid")
        decimals = _integer(
            f"owner_account_{index}.tokenAmount.decimals",
            token_amount.get("decimals"),
        )
        _require(
            int(amount) == expected.amount_atomic
            and decimals == expected.decimals,
            "owner_account_balance_disagreement",
        )
        owners.append(
            OwnerResolution(
                token_account=expected.address,
                owner=_text(
                    f"owner_account_{index}.owner",
                    info.get("owner"),
                ),
                amount_atomic=int(amount),
                decimals=decimals,
            )
        )
    return OwnersObservation(
        owners=tuple(owners),
        context_slot=_context_slot(result),
    )


@dataclass(frozen=True, slots=True)
class TransportAttempt:
    request: BoundRequest
    response: TransportResponse


class BoundedEntityTransport:
    """Three-call JSON-RPC transport with no retry path."""

    def __init__(
        self,
        *,
        plan: EntityPilotPlan,
        credential: HeliusCredential,
        gate: ExternalExecutionGate,
        http_exchange: HttpExchange = stdlib_http_exchange,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.plan = plan
        self.credential = credential
        self.gate = gate
        self.http_exchange = http_exchange
        self.clock = clock
        self.started_at = clock()
        self.call_count = 0
        self.received_bytes = 0

    def call(
        self,
        *,
        rpc_id: int,
        method: str,
        params: Sequence[object],
    ) -> TransportAttempt:
        self.gate.require()
        _require(method in self.plan.methods, "method_not_in_frozen_plan")
        _require(self.call_count < self.plan.provider_calls, "provider_call_cap")
        _require(
            self.clock() - self.started_at <= self.plan.elapsed_seconds,
            "elapsed_time_cap",
        )
        body = _canonical_json_bytes(
            {
                "id": rpc_id,
                "jsonrpc": "2.0",
                "method": method,
                "params": list(params),
            }
        )
        url = (
            HELIUS_RPC_BASE_URL
            + "?api-key="
            + urllib.parse.quote(self.credential.value, safe="")
        )
        request = BoundRequest(
            attempt_id=f"T11-A3-R{rpc_id:02d}",
            case_id=method,
            provider=self.plan.provider_id,
            transport="HTTP",
            method="POST",
            url=url,
            headers=(
                ("Accept", "application/json"),
                ("Accept-Encoding", "identity"),
                ("Content-Type", "application/json"),
            ),
            body=body,
            timeout_seconds=float(self.plan.timeout_seconds_per_call),
            safe_query_keys=("api-key",),
        )
        self.call_count += 1
        try:
            response = self.http_exchange(
                request,
                max_response_bytes=self.plan.response_bytes_each,
            )
        except Exception as exc:
            now = datetime.now(UTC)
            response = TransportResponse(
                status_code=None,
                body=b"",
                safe_headers=(),
                terminal_class="STOP_CAP",
                error_class=_safe_code(type(exc).__name__),
                request_started_at=now,
                request_sent_at=now,
                response_headers_at=None,
                response_complete_at=now,
            )
        self.received_bytes += len(response.body)
        _require(
            self.received_bytes <= self.plan.received_bytes_total,
            "received_bytes_cap",
        )
        _require(
            self.clock() - self.started_at <= self.plan.elapsed_seconds,
            "elapsed_time_cap",
        )
        return TransportAttempt(request=request, response=response)


@dataclass(frozen=True, slots=True)
class StoredAttemptReceipt:
    rpc_id: int
    method: str
    terminal_class: str
    response_status: str
    error_class: str | None
    status_code: int | None
    response_bytes: int
    raw_event_id: str
    redacted_body_sha256: str
    partition_file_sha256: str
    partition_content_sha256: str
    partition_bytes: int
    logical_location: str
    response_complete_at: str
    safe_request: dict[str, JsonValue]

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "error_class": self.error_class,
            "logical_location": self.logical_location,
            "method": self.method,
            "partition_bytes": self.partition_bytes,
            "partition_content_sha256": self.partition_content_sha256,
            "partition_file_sha256": self.partition_file_sha256,
            "raw_event_id": self.raw_event_id,
            "redacted_body_sha256": self.redacted_body_sha256,
            "response_bytes": self.response_bytes,
            "response_complete_at": self.response_complete_at,
            "response_status": self.response_status,
            "rpc_id": self.rpc_id,
            "safe_request": self.safe_request,
            "status_code": self.status_code,
            "terminal_class": self.terminal_class,
        }


def _raw_status_for_response(response: TransportResponse) -> RawResponseStatus:
    if response.terminal_class == "SUCCESS" and response.status_code == 200:
        return RawResponseStatus.SUCCESS
    if response.terminal_class == "TIMEOUT":
        return RawResponseStatus.TIMEOUT
    if response.status_code is not None:
        return RawResponseStatus.HTTP_ERROR
    return RawResponseStatus.PROVIDER_ERROR


class DurableEntityProbeSink:
    """One immutable Parquet partition per attempted RPC call."""

    def __init__(
        self,
        *,
        raw_root: Path,
        run_id: str,
        plan: EntityPilotPlan,
        credential: HeliusCredential,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        _require(raw_root.is_absolute(), "raw_root_must_be_absolute")
        _require(RUN_ID_RE.fullmatch(run_id) is not None, "run_id_invalid")
        self.raw_root = raw_root
        self.run_id = run_id
        self.plan = plan
        self.credential = credential
        self.now = now
        self.receipts: list[StoredAttemptReceipt] = []
        self.stored_partition_bytes = 0
        self.final_receipt_sha256: str | None = None
        self.final_receipt_bytes = 0

    @property
    def logical_root(self) -> str:
        return f"{self.plan.logical_root}/run={self.run_id}"

    def record(
        self,
        *,
        rpc_id: int,
        method: str,
        attempt: TransportAttempt,
        response_status: RawResponseStatus,
        error_class: str | None,
    ) -> StoredAttemptReceipt:
        _require(
            len(self.receipts) < self.plan.provider_calls,
            "stored_attempt_cap",
        )
        self.raw_root.mkdir(parents=True, exist_ok=True)
        _require(not self.raw_root.is_symlink(), "raw_root_symlink_forbidden")
        observed_at = attempt.response.response_complete_at
        ingested_at = self.now()
        if ingested_at < observed_at:
            ingested_at = observed_at
        request_identity = json.loads(attempt.request.body)
        event = build_raw_api_event(
            source="HELIUS_STANDARD_SOLANA_RPC",
            source_version="helius-standard-rpc-observed-2026-07-28",
            endpoint_or_method=method,
            request_identity=request_identity,
            response_body=attempt.response.body,
            response_status=response_status,
            error_class=error_class,
            event_time=observed_at,
            observed_at=observed_at,
            first_reliable_available_at=observed_at,
            available_to_strategy_at=observed_at,
            ingested_at=ingested_at,
            provider_version="helius-managed-mainnet",
            schema_version=TRANSPORT_CONTRACT_VERSION,
            protocol_version="solana-json-rpc",
            quality_flags=(
                "CURRENT_SNAPSHOT;"
                "EVENT_TIME_PROXY_OBSERVED_AT_NO_BLOCK_TIME"
            ),
            explicit_secret_values=(self.credential.value,),
        )
        logical_location = (
            f"{self.logical_root}/partitions/"
            f"{rpc_id:02d}-{method}.parquet"
        )
        result = write_budgeted_raw_event_partition(
            root=self.raw_root,
            dataset_id=self.plan.dataset_id,
            dataset_version=self.plan.dataset_version,
            partition_id=f"{self.run_id}-{rpc_id:02d}-{method}",
            logical_location=logical_location,
            events=(event,),
            created_at=ingested_at,
            first_reliable_available_at=ingested_at,
            budget_policy=StorageBudgetPolicy(
                max_partition_bytes=self.plan.partition_max_bytes,
                max_dataset_bytes=self.plan.parquet_dataset_max_bytes,
                min_free_bytes=self.plan.minimum_free_bytes,
                forecast_partition_count=1,
            ),
        )
        verified = verify_raw_event_partition(
            root=self.raw_root,
            manifest=result.manifest,
        )
        if verified != (event,):
            raise RawStorageError("raw_partition_roundtrip_mismatch")
        receipt = StoredAttemptReceipt(
            rpc_id=rpc_id,
            method=method,
            terminal_class=attempt.response.terminal_class,
            response_status=str(response_status),
            error_class=error_class,
            status_code=attempt.response.status_code,
            response_bytes=len(attempt.response.body),
            raw_event_id=event.raw_event_id,
            redacted_body_sha256=event.content_sha256,
            partition_file_sha256=result.manifest.file_sha256,
            partition_content_sha256=result.manifest.content_sha256,
            partition_bytes=result.file_size_bytes,
            logical_location=logical_location,
            response_complete_at=observed_at.isoformat(),
            safe_request=attempt.request.safe_receipt(),
        )
        self.receipts.append(receipt)
        self.stored_partition_bytes += result.file_size_bytes
        return receipt

    def finalize(self, receipt: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        payload = {
            **receipt,
            "attempts": [item.as_dict() for item in self.receipts],
            "dataset_id": self.plan.dataset_id,
            "dataset_version": self.plan.dataset_version,
            "logical_root": self.logical_root,
            "stored_partition_bytes": self.stored_partition_bytes,
            "transport_contract_version": TRANSPORT_CONTRACT_VERSION,
        }
        receipt_bytes = _canonical_json_bytes(payload) + b"\n"
        projected = self.stored_partition_bytes + len(receipt_bytes)
        if projected > self.plan.stored_bytes_total:
            raise RawStorageError("stored_bytes_cap")
        receipt_dir = (
            self.raw_root
            / self.plan.logical_root
            / f"run={self.run_id}"
            / "receipts"
        )
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt_path = receipt_dir / "probe.receipt.json"
        try:
            with receipt_path.open("xb") as handle:
                handle.write(receipt_bytes)
        except FileExistsError as exc:
            raise RawStorageError("final_receipt_already_exists") from exc
        self.final_receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
        self.final_receipt_bytes = len(receipt_bytes)
        return {
            **payload,
            "receipt_bytes": self.final_receipt_bytes,
            "receipt_sha256": self.final_receipt_sha256,
            "stored_bytes_total": projected,
        }

    def safe_partial_receipt(self) -> dict[str, JsonValue]:
        return {
            "attempts": [item.as_dict() for item in self.receipts],
            "logical_root": self.logical_root,
            "receipt_sha256": self.final_receipt_sha256,
            "run_id": self.run_id,
            "stored_partition_bytes": self.stored_partition_bytes,
        }


def default_run_id(now: datetime) -> str:
    _require(
        now.tzinfo is not None and now.utcoffset() is not None,
        "run_time_must_be_aware",
    )
    return now.astimezone(UTC).strftime("t11a3-%Y%m%dT%H%M%SZ")


def _response_error_code(response: TransportResponse) -> str:
    if response.error_class:
        return _safe_code(response.error_class)
    return _safe_code(response.terminal_class.lower())


class EntityProbeRunner:
    """Execute the exact three-call graph and stop on the first bad edge."""

    def __init__(
        self,
        *,
        plan: EntityPilotPlan,
        transport: BoundedEntityTransport,
        sink: DurableEntityProbeSink,
        access: AccessAttestation,
    ) -> None:
        self.plan = plan
        self.transport = transport
        self.sink = sink
        self.access = access

    def _record_non_success(
        self,
        *,
        rpc_id: int,
        method: str,
        attempt: TransportAttempt,
    ) -> dict[str, JsonValue] | None:
        response = attempt.response
        if response.terminal_class == "SUCCESS" and response.status_code == 200:
            return None
        status = _raw_status_for_response(response)
        error_code = _response_error_code(response)
        self.sink.record(
            rpc_id=rpc_id,
            method=method,
            attempt=attempt,
            response_status=status,
            error_class=error_code,
        )
        return self._finish(
            terminal="STOPPED_PROVIDER_TRANSPORT",
            error_code=error_code,
            snapshot=None,
            metrics=None,
        )

    def _parse_and_record(
        self,
        *,
        rpc_id: int,
        method: str,
        attempt: TransportAttempt,
        parser: Callable[[], object],
    ) -> tuple[object | None, dict[str, JsonValue] | None]:
        stopped = self._record_non_success(
            rpc_id=rpc_id,
            method=method,
            attempt=attempt,
        )
        if stopped is not None:
            return None, stopped
        try:
            parsed = parser()
        except RpcProviderError as exc:
            code = _safe_code(str(exc))
            self.sink.record(
                rpc_id=rpc_id,
                method=method,
                attempt=attempt,
                response_status=RawResponseStatus.PROVIDER_ERROR,
                error_class=code,
            )
            return None, self._finish(
                terminal="STOPPED_PROVIDER_RPC_ERROR",
                error_code=code,
                snapshot=None,
                metrics=None,
            )
        except EntityTransportContractError as exc:
            code = _safe_code(str(exc))
            self.sink.record(
                rpc_id=rpc_id,
                method=method,
                attempt=attempt,
                response_status=RawResponseStatus.INVALID_RESPONSE,
                error_class=code,
            )
            return None, self._finish(
                terminal="STOPPED_SCHEMA_DRIFT",
                error_code=code,
                snapshot=None,
                metrics=None,
            )
        self.sink.record(
            rpc_id=rpc_id,
            method=method,
            attempt=attempt,
            response_status=RawResponseStatus.SUCCESS,
            error_class=None,
        )
        return parsed, None

    def _finish(
        self,
        *,
        terminal: str,
        error_code: str | None,
        snapshot: HolderSnapshotInput | None,
        metrics: HolderConcentrationMetrics | None,
    ) -> dict[str, JsonValue]:
        receipt: dict[str, JsonValue] = {
            "adjusted_concentration": (
                str(metrics.adjusted_top_accounts_supply_share)
                if metrics is not None
                and metrics.adjusted_top_accounts_supply_share is not None
                else None
            ),
            "cash_spend_usd_cents": 0,
            "completed_calls": self.transport.call_count,
            "deployer_funder_bundler": "NOT_TESTED",
            "error_code": error_code,
            "modeled_credits": (
                self.transport.call_count
                * self.plan.modeled_credits_per_call
            ),
            "owner_resolution_count": (
                len(
                    {
                        account.owner
                        for account in snapshot.accounts
                        if account.owner is not None
                    }
                )
                if snapshot is not None
                else 0
            ),
            "context_slot_spread": (
                max(
                    snapshot.supply_context_slot,
                    snapshot.largest_accounts_context_slot,
                    snapshot.owners_context_slot,
                )
                - min(
                    snapshot.supply_context_slot,
                    snapshot.largest_accounts_context_slot,
                    snapshot.owners_context_slot,
                )
                if snapshot is not None
                else None
            ),
            "largest_accounts_context_slot": (
                snapshot.largest_accounts_context_slot
                if snapshot is not None
                else None
            ),
            "owners_context_slot": (
                snapshot.owners_context_slot
                if snapshot is not None
                else None
            ),
            "planned_calls": self.plan.provider_calls,
            "raw_event_ids": [
                item.raw_event_id for item in self.sink.receipts
            ],
            "raw_top_accounts_amount_atomic": (
                metrics.raw_top_accounts_amount_atomic
                if metrics is not None
                else None
            ),
            "raw_top_accounts_supply_share": (
                str(metrics.raw_top_accounts_supply_share)
                if metrics is not None
                and metrics.raw_top_accounts_supply_share is not None
                else None
            ),
            "received_bytes": self.transport.received_bytes,
            "retries": 0,
            "run_id": self.sink.run_id,
            "selected_mint": self.plan.selected_mint,
            "supply_atomic": (
                snapshot.supply_atomic if snapshot is not None else None
            ),
            "supply_context_slot": (
                snapshot.supply_context_slot
                if snapshot is not None
                else None
            ),
            "terminal": terminal,
            "top_account_count": (
                len(snapshot.accounts) if snapshot is not None else 0
            ),
            "wallet_signer_transaction_actions": 0,
        }
        return self.sink.finalize(receipt)

    def run(self) -> dict[str, JsonValue]:
        self.transport.gate.require()
        self.access.require(self.plan)
        commitment = {"commitment": self.plan.commitment}

        supply_attempt = self.transport.call(
            rpc_id=1,
            method="getTokenSupply",
            params=(self.plan.selected_mint, commitment),
        )
        supply_value, stopped = self._parse_and_record(
            rpc_id=1,
            method="getTokenSupply",
            attempt=supply_attempt,
            parser=lambda: parse_token_supply(
                supply_attempt.response.body,
                expected_id=1,
                expected_decimals=self.plan.selected_mint_decimals,
            ),
        )
        if stopped is not None:
            return stopped
        assert isinstance(supply_value, TokenSupplyObservation)

        largest_attempt = self.transport.call(
            rpc_id=2,
            method="getTokenLargestAccounts",
            params=(self.plan.selected_mint, commitment),
        )
        largest_value, stopped = self._parse_and_record(
            rpc_id=2,
            method="getTokenLargestAccounts",
            attempt=largest_attempt,
            parser=lambda: parse_largest_accounts(
                largest_attempt.response.body,
                expected_id=2,
                expected_decimals=self.plan.selected_mint_decimals,
            ),
        )
        if stopped is not None:
            return stopped
        assert isinstance(largest_value, LargestAccountsObservation)

        owner_attempt = self.transport.call(
            rpc_id=3,
            method="getMultipleAccounts",
            params=(
                [item.address for item in largest_value.accounts],
                {
                    "commitment": self.plan.commitment,
                    "encoding": "jsonParsed",
                },
            ),
        )
        owner_value, stopped = self._parse_and_record(
            rpc_id=3,
            method="getMultipleAccounts",
            attempt=owner_attempt,
            parser=lambda: parse_owner_accounts(
                owner_attempt.response.body,
                expected_id=3,
                expected_mint=self.plan.selected_mint,
                expected_accounts=largest_value.accounts,
            ),
        )
        if stopped is not None:
            return stopped
        assert isinstance(owner_value, OwnersObservation)

        joined_at = owner_attempt.response.response_complete_at
        accounts = tuple(
            HolderAccountObservation(
                token_account=owner.token_account,
                owner=owner.owner,
                amount_atomic=owner.amount_atomic,
                context_slot=owner_value.context_slot,
            )
            for owner in owner_value.owners
        )
        raw_ids = tuple(item.raw_event_id for item in self.sink.receipts)
        _require(len(raw_ids) == 3, "raw_event_lineage_incomplete")
        snapshot = HolderSnapshotInput(
            snapshot_id=f"{self.sink.run_id}-holder-snapshot",
            mint=self.plan.selected_mint,
            decimals=supply_value.decimals,
            supply_atomic=supply_value.amount_atomic,
            supply_context_slot=supply_value.context_slot,
            largest_accounts_context_slot=largest_value.context_slot,
            owners_context_slot=owner_value.context_slot,
            accounts=accounts,
            event_time=joined_at,
            observed_at=joined_at,
            first_reliable_available_at=joined_at,
            available_to_strategy_at=joined_at,
            ingested_at=max(datetime.now(UTC), joined_at),
            source=self.plan.provider_id,
            source_version="helius-standard-rpc-observed-2026-07-28",
            revision_number=1,
            revision_of=None,
            raw_event_ids=(raw_ids[0], raw_ids[1], raw_ids[2]),
        )
        assessments = tuple(
            ExclusionAssessment(
                token_account=account.token_account,
                disposition=ExclusionDisposition.UNRESOLVED,
                reason="exclusion_inventory_not_collected",
                evidence_ref=None,
                evidence_class=EvidenceClass.RAW_ONCHAIN,
                confidence=ConfidenceLevel.UNKNOWN,
            )
            for account in accounts
        )
        metrics = calculate_holder_metrics(
            snapshot,
            assessments,
            exclusion_inventory_complete=False,
            excluded_supply_atomic_total=None,
            exclusion_inventory_evidence_ref=None,
        )
        return self._finish(
            terminal="RAW_TOP20_FEASIBILITY_CAPTURED",
            error_code=None,
            snapshot=snapshot,
            metrics=metrics,
        )
