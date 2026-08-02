"""Bounded TASK-24 Helius history capture with exact raw retention."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeAlias

import pyarrow.parquet as pq

from solana_alpha_lab.contracts.schema_v1 import RawResponseStatus
from solana_alpha_lab.entity_input_transport import (
    parse_largest_accounts,
    parse_owner_accounts,
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
    canonical_raw_event_rows_bytes,
    verify_raw_event_partition,
    write_budgeted_raw_event_partition,
)
from solana_alpha_lab.storage.parquet_store import _events_from_table


JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

CONTRACT_VERSION = "1.1"
EXTERNAL_AUTHORITY_PHRASE = "T24-A5R1_EXACT_WIRE_RETENTION_RECAPTURE_V1"
HELIUS_RPC_BASE_URL = "https://mainnet.helius-rpc.com/"
EXPECTED_HOST = "mainnet.helius-rpc.com"
METHOD = "getTransactionsForAddress"
PSEUDONYM_NAMESPACE = "TASK24_ENTITY_GRAPH_V1"
RUN_ID_RE = re.compile(r"t24a5-[0-9]{8}T[0-9]{6}Z")
PUBLIC_CODE_RE = re.compile(r"[A-Za-z0-9_.:-]{1,160}")

A4_CONFIG_SHA256 = (
    "2db333e179ecc54cced41128b5a8c97825fc970d46af66be8660db9ee963791b"
)
A4_RECEIPT_SHA256 = (
    "7169c2894929d8e5571635b11b75cb4ec7dbd89a543d164d54f8fab552504f1e"
)
A3_MANIFEST_SHA256 = (
    "f889c0f28d3259cc61681ba6cc56dc53686d2375ce98826ca572dc5d5720846d"
)


class Task24HistoryCaptureError(ValueError):
    """The frozen capture contract or provider payload is incoherent."""


class ExternalAuthorityRequiredError(Task24HistoryCaptureError):
    """The exact provider execution phrase is absent."""


class AccessAttestationError(Task24HistoryCaptureError):
    """Provider credit headroom was not locally attested."""


class RawCaptureStorageError(RuntimeError):
    """Immutable raw evidence could not be persisted safely."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Task24HistoryCaptureError(message)


def _canonical_json_bytes(value: object, *, newline: bool = False) -> bytes:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Task24HistoryCaptureError("json_canonicalization_failed") from exc
    return payload + (b"\n" if newline else b"")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _safe_code(value: str) -> str:
    return value if PUBLIC_CODE_RE.fullmatch(value) else "REDACTED"


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


def _integer(name: str, value: object) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        f"{name}_must_be_nonnegative_integer",
    )
    return value


def _stable_node_id(node_type: str, raw_public_key: str) -> str:
    material = f"{PSEUDONYM_NAMESPACE}|{node_type}|{raw_public_key}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"t24-{node_type.lower().replace('_', '-')}-{digest}"


@dataclass(frozen=True, slots=True)
class HistoryCapturePlan:
    provider_calls: int = 21
    provider_credits: int = 210
    returned_transactions: int = 2_100
    limit_each: int = 100
    retries: int = 0
    timeout_seconds_per_call: int = 30
    elapsed_seconds: int = 900
    response_bytes_each: int = 8 * 1024 * 1024
    received_bytes_total: int = 21 * 8 * 1024 * 1024
    partition_max_bytes: int = 9 * 1024 * 1024
    dataset_max_bytes: int = 200 * 1024 * 1024
    stored_bytes_total: int = 210 * 1024 * 1024
    minimum_free_bytes: int = 1024 * 1024 * 1024
    cash_spend_usd_cents: int = 0
    dataset_id: str = "SMIAL_TASK24_ENTITY_LINKAGE_HISTORY_RAW"
    dataset_version: str = "1.1"
    logical_root: str = "task24_entity_linkage_history_v1_1"

    def validate(self) -> None:
        _require(self.provider_calls == 21, "provider_call_cap_drift")
        _require(self.provider_credits == 210, "provider_credit_cap_drift")
        _require(self.returned_transactions == 2_100, "transaction_cap_drift")
        _require(self.limit_each == 100, "per_request_limit_drift")
        _require(self.retries == 0, "retry_cap_drift")
        _require(self.cash_spend_usd_cents == 0, "cash_cap_drift")
        _require(
            self.returned_transactions == self.provider_calls * self.limit_each,
            "transaction_cap_incoherent",
        )
        _require(
            self.received_bytes_total
            == self.provider_calls * self.response_bytes_each,
            "received_byte_cap_incoherent",
        )
        _require(
            self.partition_max_bytes > self.response_bytes_each,
            "partition_budget_missing_overhead",
        )
        _require(
            self.dataset_max_bytes < self.stored_bytes_total,
            "receipt_storage_reserve_missing",
        )

    def safe_preflight(self) -> dict[str, JsonValue]:
        self.validate()
        return {
            "cash_spend_usd_cents": self.cash_spend_usd_cents,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "elapsed_seconds": self.elapsed_seconds,
            "exact_wire_response_bytes": True,
            "limit_each": self.limit_each,
            "logical_root": self.logical_root,
            "method": METHOD,
            "pagination": False,
            "provider_calls": self.provider_calls,
            "provider_credits": self.provider_credits,
            "retries": self.retries,
            "returned_transactions": self.returned_transactions,
            "sort_order": "asc",
        }


@dataclass(frozen=True, slots=True, repr=False)
class FrozenSubject:
    subject_id: str
    node_type: str
    raw_public_key: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class FrozenPopulation:
    subjects: tuple[FrozenSubject, ...] = field(repr=False)
    fingerprint_sha256: str

    @property
    def mint(self) -> FrozenSubject:
        return self.subjects[0]

    @property
    def wallets(self) -> tuple[FrozenSubject, ...]:
        return self.subjects[1:]

    def safe_receipt(self) -> dict[str, JsonValue]:
        return {
            "fingerprint_sha256": self.fingerprint_sha256,
            "mint_subject_id": self.mint.subject_id,
            "subject_count": len(self.subjects),
            "wallet_subject_ids": [item.subject_id for item in self.wallets],
        }


def _load_raw_event(path: Path, expected: Mapping[str, Any]) -> Any:
    _require(path.is_file(), "raw_partition_missing")
    _require(not path.is_symlink(), "raw_partition_symlink_forbidden")
    _require(path.stat().st_size == expected["bytes"], "raw_partition_size_drift")
    _require(_sha256_file(path) == expected["sha256"], "raw_partition_sha256_drift")
    table = pq.read_table(path)
    events = _events_from_table(table)
    _require(len(events) == 1, "raw_partition_row_count_drift")
    event = events[0]
    _require(event.raw_event_id == expected["raw_event_id"], "raw_event_id_drift")
    _require(
        _sha256_bytes(canonical_raw_event_rows_bytes(events))
        == expected["content_sha256"],
        "raw_partition_content_drift",
    )
    return event


def load_frozen_population(repo_root: Path) -> FrozenPopulation:
    """Recover the A3 mint and 20 owners without persisting raw addresses."""

    repo_root = repo_root.resolve()
    a4_config = repo_root / "configs/task24_entity_linkage_evidence_extension_v1.yaml"
    a4_receipt = (
        repo_root
        / "docs/evidence/task24/a4_bounded_entity_linkage_evidence_extension_decision_v1.json"
    )
    a3_manifest_path = (
        repo_root / "docs/evidence/task24/a3_entity_evidence_pre_read_manifest_v1.json"
    )
    _require(_sha256_file(a4_config) == A4_CONFIG_SHA256, "a4_config_hash_drift")
    _require(_sha256_file(a4_receipt) == A4_RECEIPT_SHA256, "a4_receipt_hash_drift")
    _require(
        _sha256_file(a3_manifest_path) == A3_MANIFEST_SHA256,
        "a3_manifest_hash_drift",
    )
    manifest = _mapping("a3_manifest", json.loads(a3_manifest_path.read_bytes()))
    _require(manifest["status"] == "PASS_ADMISSIBLE_LOCAL_INPUTS", "a3_not_pass")
    privacy = _mapping("privacy", manifest["privacy_and_output_policy"])
    _require(
        privacy["raw_owner_addresses_may_be_read_offline"] is True,
        "raw_owner_read_not_allowed",
    )
    _require(
        privacy["raw_owner_addresses_may_be_persisted_in_git"] is False,
        "raw_owner_git_persistence_enabled",
    )
    boundary = _mapping("boundary", manifest["no_r3_no_outcome_assertion"])
    _require(not any(boundary.values()), "forbidden_a3_boundary_enabled")
    by_role = {item["role"]: item for item in manifest["inputs"]}
    largest_meta = _mapping("largest_meta", by_role["LARGEST_TOKEN_ACCOUNTS_RAW_EVENT"])
    owner_meta = _mapping("owner_meta", by_role["TOKEN_ACCOUNT_OWNER_RAW_EVENT"])
    largest_event = _load_raw_event(
        repo_root / str(largest_meta["exact_local_path"]), largest_meta
    )
    owner_event = _load_raw_event(
        repo_root / str(owner_meta["exact_local_path"]), owner_meta
    )
    scope = _mapping("scope", manifest["scope"])
    mint_raw = str(scope["selected_mint"])
    largest = parse_largest_accounts(
        largest_event.redacted_body,
        expected_id=2,
        expected_decimals=6,
    )
    owners = parse_owner_accounts(
        owner_event.redacted_body,
        expected_id=3,
        expected_mint=mint_raw,
        expected_accounts=largest.accounts,
    )
    raw_owners = tuple(item.owner for item in owners.owners)
    _require(len(raw_owners) == 20, "owner_population_count_drift")
    _require(len(set(raw_owners)) == 20, "owner_population_not_unique")
    mint = FrozenSubject(
        subject_id=_stable_node_id("TOKEN_MINT", mint_raw),
        node_type="TOKEN_MINT",
        raw_public_key=mint_raw,
    )
    wallets = tuple(
        sorted(
            (
                FrozenSubject(
                    subject_id=_stable_node_id("WALLET", raw),
                    node_type="WALLET",
                    raw_public_key=raw,
                )
                for raw in raw_owners
            ),
            key=lambda item: item.subject_id,
        )
    )
    subjects = (mint, *wallets)
    fingerprint = _sha256_bytes(
        _canonical_json_bytes([item.subject_id for item in subjects])
    )
    return FrozenPopulation(subjects=subjects, fingerprint_sha256=fingerprint)


@dataclass(frozen=True, slots=True)
class ExternalExecutionGate:
    authority_phrase: str

    def require(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise ExternalAuthorityRequiredError("external_authority_phrase_mismatch")


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

    def require(self, plan: HistoryCapturePlan) -> None:
        if not self.dashboard_readback_completed:
            raise AccessAttestationError("dashboard_readback_required")
        if (
            isinstance(self.helius_credits_remaining, bool)
            or not isinstance(self.helius_credits_remaining, int)
            or self.helius_credits_remaining < plan.provider_credits
        ):
            raise AccessAttestationError("helius_credit_headroom_insufficient")


@dataclass(frozen=True, slots=True)
class HistoryPage:
    rpc_id: int
    transaction_count: int
    first_slot: int | None
    last_slot: int | None
    pagination_token_present: bool
    response_sha256: str

    def safe_receipt(self) -> dict[str, JsonValue]:
        return {
            "first_slot": self.first_slot,
            "last_slot": self.last_slot,
            "pagination_token_present": self.pagination_token_present,
            "response_sha256": self.response_sha256,
            "rpc_id": self.rpc_id,
            "transaction_count": self.transaction_count,
        }


def parse_history_response(body: bytes, *, expected_id: int, limit: int) -> HistoryPage:
    try:
        root = _mapping("rpc_response", json.loads(body))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task24HistoryCaptureError("rpc_response_json_invalid") from exc
    _require(root.get("jsonrpc") == "2.0", "rpc_jsonrpc_version_drift")
    _require(root.get("id") == expected_id, "rpc_response_id_drift")
    _require(("result" in root) != ("error" in root), "rpc_result_error_invalid")
    if "error" in root:
        error = _mapping("rpc_error", root["error"])
        code = error.get("code")
        _require(isinstance(code, int) and not isinstance(code, bool), "rpc_error_code")
        raise Task24HistoryCaptureError(f"rpc_error_{code}")
    result = _mapping("rpc_result", root["result"])
    data = _sequence("rpc_result.data", result.get("data"))
    _require(len(data) <= limit, "returned_transaction_cap")
    slots: list[int] = []
    for index, value in enumerate(data):
        tx = _mapping(f"transaction_{index}", value)
        slots.append(_integer(f"transaction_{index}.slot", tx.get("slot")))
        block_time = tx.get("blockTime")
        _require(
            block_time is None
            or (isinstance(block_time, int) and not isinstance(block_time, bool)),
            f"transaction_{index}.block_time_invalid",
        )
        transaction = _mapping(f"transaction_{index}.transaction", tx.get("transaction"))
        signatures = _sequence(
            f"transaction_{index}.signatures", transaction.get("signatures")
        )
        _require(
            bool(signatures)
            and all(isinstance(item, str) and item for item in signatures),
            f"transaction_{index}.signatures_invalid",
        )
        meta = _mapping(f"transaction_{index}.meta", tx.get("meta"))
        _require(meta.get("err") is None, f"transaction_{index}.not_succeeded")
    _require(slots == sorted(slots), "oldest_first_order_drift")
    pagination_token = result.get("paginationToken")
    _require(
        pagination_token is None
        or (isinstance(pagination_token, str) and bool(pagination_token)),
        "pagination_token_invalid",
    )
    return HistoryPage(
        rpc_id=expected_id,
        transaction_count=len(data),
        first_slot=slots[0] if slots else None,
        last_slot=slots[-1] if slots else None,
        pagination_token_present=pagination_token is not None,
        response_sha256=_sha256_bytes(body),
    )


@dataclass(frozen=True, slots=True)
class TransportAttempt:
    request: BoundRequest
    response: TransportResponse


class BoundedHistoryTransport:
    """Exactly 21 oldest-first Helius history calls with no retry path."""

    def __init__(
        self,
        *,
        plan: HistoryCapturePlan,
        credential: HeliusCredential,
        gate: ExternalExecutionGate,
        http_exchange: HttpExchange = stdlib_http_exchange,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        plan.validate()
        self.plan = plan
        self.credential = credential
        self.gate = gate
        self.http_exchange = http_exchange
        self.clock = clock
        self.started_at = clock()
        self.call_count = 0
        self.received_bytes = 0

    def call(self, *, rpc_id: int, subject: FrozenSubject) -> TransportAttempt:
        self.gate.require()
        _require(self.call_count < self.plan.provider_calls, "provider_call_cap")
        _require(
            self.clock() - self.started_at <= self.plan.elapsed_seconds,
            "elapsed_time_cap",
        )
        body = _canonical_json_bytes(
            {
                "id": rpc_id,
                "jsonrpc": "2.0",
                "method": METHOD,
                "params": [
                    subject.raw_public_key,
                    {
                        "commitment": "finalized",
                        "encoding": "json",
                        "filters": {
                            "status": "succeeded",
                            "tokenAccounts": "none",
                        },
                        "limit": self.plan.limit_each,
                        "maxSupportedTransactionVersion": 0,
                        "sortOrder": "asc",
                        "transactionDetails": "full",
                    },
                ],
            }
        )
        url = (
            HELIUS_RPC_BASE_URL
            + "?api-key="
            + urllib.parse.quote(self.credential.value, safe="")
        )
        request = BoundRequest(
            attempt_id=f"T24-A5-R{rpc_id:02d}",
            case_id=f"history-{rpc_id:02d}",
            provider="HELIUS_GET_TRANSACTIONS_FOR_ADDRESS",
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
        _require(self.received_bytes <= self.plan.received_bytes_total, "received_bytes_cap")
        _require(
            self.clock() - self.started_at <= self.plan.elapsed_seconds,
            "elapsed_time_cap",
        )
        return TransportAttempt(request=request, response=response)


def _raw_status(response: TransportResponse) -> RawResponseStatus:
    if response.terminal_class == "SUCCESS" and response.status_code == 200:
        return RawResponseStatus.SUCCESS
    if response.terminal_class == "TIMEOUT":
        return RawResponseStatus.TIMEOUT
    if response.status_code is not None:
        return RawResponseStatus.HTTP_ERROR
    return RawResponseStatus.PROVIDER_ERROR


@dataclass(frozen=True, slots=True)
class StoredHistoryAttempt:
    rpc_id: int
    subject_id: str
    status_code: int | None
    terminal_class: str
    error_class: str | None
    response_bytes: int
    raw_event_id: str
    response_sha256: str
    exact_wire_response_sha256: str
    exact_wire_response_bytes: int
    exact_wire_logical_location: str
    partition_file_sha256: str
    partition_content_sha256: str
    partition_bytes: int
    logical_location: str
    response_complete_at: str
    ingested_at: str
    safe_request: dict[str, JsonValue]

    def safe_receipt(self) -> dict[str, JsonValue]:
        return {
            "error_class": self.error_class,
            "ingested_at": self.ingested_at,
            "logical_location": self.logical_location,
            "partition_bytes": self.partition_bytes,
            "partition_content_sha256": self.partition_content_sha256,
            "partition_file_sha256": self.partition_file_sha256,
            "raw_event_id": self.raw_event_id,
            "response_bytes": self.response_bytes,
            "response_complete_at": self.response_complete_at,
            "response_sha256": self.response_sha256,
            "exact_wire_response_sha256": self.exact_wire_response_sha256,
            "exact_wire_response_bytes": self.exact_wire_response_bytes,
            "exact_wire_logical_location": self.exact_wire_logical_location,
            "rpc_id": self.rpc_id,
            "safe_request": self.safe_request,
            "status_code": self.status_code,
            "subject_id": self.subject_id,
            "terminal_class": self.terminal_class,
        }


class DurableHistorySink:
    """Persist canonical raw envelopes plus immutable exact provider wire bytes."""

    def __init__(
        self,
        *,
        raw_root: Path,
        run_id: str,
        plan: HistoryCapturePlan,
        population: FrozenPopulation,
        credential: HeliusCredential,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        _require(raw_root.is_absolute(), "raw_root_must_be_absolute")
        _require(RUN_ID_RE.fullmatch(run_id) is not None, "run_id_invalid")
        plan.validate()
        self.raw_root = raw_root
        self.run_id = run_id
        self.plan = plan
        self.population = population
        self.credential = credential
        self.now = now
        self.attempts: list[StoredHistoryAttempt] = []
        self.stored_partition_bytes = 0
        self.stored_exact_wire_bytes = 0

    @property
    def logical_run_root(self) -> str:
        return f"{self.plan.logical_root}/run={self.run_id}"

    def record(
        self,
        *,
        rpc_id: int,
        subject: FrozenSubject,
        attempt: TransportAttempt,
    ) -> StoredHistoryAttempt:
        _require(len(self.attempts) < self.plan.provider_calls, "stored_attempt_cap")
        self.raw_root.mkdir(parents=True, exist_ok=True)
        _require(not self.raw_root.is_symlink(), "raw_root_symlink_forbidden")
        observed_at = attempt.response.response_complete_at
        ingested_at = max(self.now(), observed_at)
        request_identity = json.loads(attempt.request.body)
        event = build_raw_api_event(
            source="HELIUS_GET_TRANSACTIONS_FOR_ADDRESS",
            source_version="helius-history-observed-2026-08-02",
            endpoint_or_method=METHOD,
            request_identity=request_identity,
            response_body=attempt.response.body,
            response_status=_raw_status(attempt.response),
            error_class=attempt.response.error_class,
            event_time=observed_at,
            observed_at=observed_at,
            first_reliable_available_at=observed_at,
            available_to_strategy_at=observed_at,
            ingested_at=ingested_at,
            provider_version="helius-managed-mainnet",
            schema_version=CONTRACT_VERSION,
            protocol_version="helius-json-rpc",
            quality_flags="HISTORICAL_BATCH_EXACT_RESPONSE;OLDEST_FIRST_LIMIT_100",
            explicit_secret_values=(self.credential.value,),
        )
        logical_location = (
            f"{self.logical_run_root}/partitions/{rpc_id:02d}-history.parquet"
        )
        result = write_budgeted_raw_event_partition(
            root=self.raw_root,
            dataset_id=self.plan.dataset_id,
            dataset_version=self.plan.dataset_version,
            partition_id=f"{self.run_id}-{rpc_id:02d}-history",
            logical_location=logical_location,
            events=(event,),
            created_at=ingested_at,
            first_reliable_available_at=ingested_at,
            budget_policy=StorageBudgetPolicy(
                max_partition_bytes=self.plan.partition_max_bytes,
                max_dataset_bytes=self.plan.dataset_max_bytes,
                min_free_bytes=self.plan.minimum_free_bytes,
                forecast_partition_count=1,
            ),
        )
        verified = verify_raw_event_partition(root=self.raw_root, manifest=result.manifest)
        if verified != (event,):
            raise RawCaptureStorageError("raw_partition_roundtrip_mismatch")
        exact_wire_logical_location = (
            "task24_entity_linkage_history_wire_v1_1/"
            f"run={self.run_id}/{rpc_id:02d}-history.response.json"
        )
        exact_wire_path = self.raw_root / exact_wire_logical_location
        exact_wire_path.parent.mkdir(parents=True, exist_ok=True)
        _require(
            self.credential.value.encode("utf-8") not in attempt.response.body,
            "credential_in_provider_response",
        )
        exact_wire_sha256 = _sha256_bytes(attempt.response.body)
        try:
            with exact_wire_path.open("xb") as handle:
                handle.write(attempt.response.body)
        except FileExistsError as exc:
            raise RawCaptureStorageError("exact_wire_response_already_exists") from exc
        _require(
            _sha256_file(exact_wire_path) == exact_wire_sha256,
            "exact_wire_response_hash_drift",
        )
        stored = StoredHistoryAttempt(
            rpc_id=rpc_id,
            subject_id=subject.subject_id,
            status_code=attempt.response.status_code,
            terminal_class=attempt.response.terminal_class,
            error_class=attempt.response.error_class,
            response_bytes=len(attempt.response.body),
            raw_event_id=event.raw_event_id,
            response_sha256=event.content_sha256,
            exact_wire_response_sha256=exact_wire_sha256,
            exact_wire_response_bytes=len(attempt.response.body),
            exact_wire_logical_location=exact_wire_logical_location,
            partition_file_sha256=result.manifest.file_sha256,
            partition_content_sha256=result.manifest.content_sha256,
            partition_bytes=result.file_size_bytes,
            logical_location=logical_location,
            response_complete_at=observed_at.isoformat(),
            ingested_at=ingested_at.isoformat(),
            safe_request=attempt.request.safe_receipt(),
        )
        self.attempts.append(stored)
        self.stored_partition_bytes += result.file_size_bytes
        self.stored_exact_wire_bytes += len(attempt.response.body)
        return stored

    def finalize(self, receipt: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            **receipt,
            "attempts": [item.safe_receipt() for item in self.attempts],
            "capture_contract_version": CONTRACT_VERSION,
            "dataset_id": self.plan.dataset_id,
            "dataset_version": self.plan.dataset_version,
            "logical_root": self.logical_run_root,
            "population": self.population.safe_receipt(),
            "stored_exact_wire_bytes": self.stored_exact_wire_bytes,
            "stored_partition_bytes": self.stored_partition_bytes,
        }
        receipt_bytes = _canonical_json_bytes(payload, newline=True)
        projected = (
            self.stored_partition_bytes
            + self.stored_exact_wire_bytes
            + len(receipt_bytes)
        )
        if projected > self.plan.stored_bytes_total:
            raise RawCaptureStorageError("stored_bytes_cap")
        receipt_dir = self.raw_root / self.logical_run_root / "receipts"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt_path = receipt_dir / "capture.receipt.json"
        try:
            with receipt_path.open("xb") as handle:
                handle.write(receipt_bytes)
        except FileExistsError as exc:
            raise RawCaptureStorageError("final_receipt_already_exists") from exc
        return {
            **payload,
            "receipt_bytes": len(receipt_bytes),
            "receipt_sha256": _sha256_bytes(receipt_bytes),
            "stored_bytes_total": projected,
        }

    def safe_partial_receipt(self) -> dict[str, JsonValue]:
        return {
            "attempts": [item.safe_receipt() for item in self.attempts],
            "logical_root": self.logical_run_root,
            "population_fingerprint_sha256": self.population.fingerprint_sha256,
            "run_id": self.run_id,
            "stored_exact_wire_bytes": self.stored_exact_wire_bytes,
            "stored_partition_bytes": self.stored_partition_bytes,
        }


class HistoryCaptureRunner:
    def __init__(
        self,
        *,
        plan: HistoryCapturePlan,
        population: FrozenPopulation,
        transport: BoundedHistoryTransport,
        sink: DurableHistorySink,
        access: AccessAttestation,
    ) -> None:
        self.plan = plan
        self.population = population
        self.transport = transport
        self.sink = sink
        self.access = access

    def _finish(
        self,
        *,
        terminal: str,
        error_code: str | None,
        pages: Sequence[HistoryPage],
    ) -> dict[str, JsonValue]:
        return self.sink.finalize(
            {
                "cash_spend_usd_cents": 0,
                "credential_values_exposed": 0,
                "error_code": error_code,
                "pages": [item.safe_receipt() for item in pages],
                "planned_calls": self.plan.provider_calls,
                "provider_calls": self.transport.call_count,
                "provider_credits_modeled": self.transport.call_count * 10,
                "received_bytes": self.transport.received_bytes,
                "retries": 0,
                "r3_or_outcome_reads": 0,
                "run_id": self.sink.run_id,
                "terminal": terminal,
                "wallet_signer_transaction_actions": 0,
            }
        )

    def run(self) -> dict[str, JsonValue]:
        self.plan.validate()
        self.transport.gate.require()
        self.access.require(self.plan)
        _require(len(self.population.subjects) == self.plan.provider_calls, "population_call_drift")
        pages: list[HistoryPage] = []
        for rpc_id, subject in enumerate(self.population.subjects, start=1):
            attempt = self.transport.call(rpc_id=rpc_id, subject=subject)
            self.sink.record(
                rpc_id=rpc_id,
                subject=subject,
                attempt=attempt,
            )
            if not (
                attempt.response.terminal_class == "SUCCESS"
                and attempt.response.status_code == 200
            ):
                return self._finish(
                    terminal="STOP_PROVIDER_TRANSPORT",
                    error_code=attempt.response.error_class or "provider_transport_error",
                    pages=pages,
                )
            try:
                page = parse_history_response(
                    attempt.response.body,
                    expected_id=rpc_id,
                    limit=self.plan.limit_each,
                )
            except Task24HistoryCaptureError as exc:
                return self._finish(
                    terminal="STOP_PROVIDER_PAYLOAD",
                    error_code=_safe_code(str(exc)),
                    pages=pages,
                )
            pages.append(page)
        _require(self.transport.call_count == self.plan.provider_calls, "call_count_incomplete")
        _require(len(pages) == self.plan.provider_calls, "page_count_incomplete")
        return self._finish(
            terminal="RAW_HISTORY_CAPTURED_REQUIRES_PROJECTION",
            error_code=None,
            pages=pages,
        )


def default_run_id(now: datetime) -> str:
    _require(now.tzinfo is not None and now.utcoffset() is not None, "run_time_naive")
    return "t24a5-" + now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
