"""Deterministic TASK-24 entity-linkage projection from one accepted A5 raw run."""

from __future__ import annotations

import hashlib
import itertools
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from solana_alpha_lab.storage import canonical_raw_event_rows_bytes
from solana_alpha_lab.storage.parquet_store import _events_from_table
from solana_alpha_lab.task24_entity_linkage_capture import (
    A3_MANIFEST_SHA256,
    FrozenPopulation,
    FrozenSubject,
    HistoryCapturePlan,
    Task24HistoryCaptureError,
    _stable_node_id,
    load_frozen_population,
    parse_history_response,
)


PROJECTION_VERSION = "1.0"
RULE_VERSION = "TASK24_ENTITY_LINKAGE_RULE_V1.0"
PREFLIGHT_SHA256 = (
    "0493f62c9c91b38d483cac40abb25f585c0de316eec894e02309d62377866468"
)
A3_NODES_SHA256 = (
    "fdb169bd3f639c42b350de5eae41fc280061f5682fb3ea2605fcad2408ff3af7"
)
A3_EDGES_SHA256 = (
    "fa19151a85d43783c37f6d0d99101baeaf2c755e4fe9536792872451af3d39c4"
)
A3_ADJUSTED_SHA256 = (
    "644b148f17fe437118196dabdb4185886117086aab1fe1b77f7965621a06f4ad"
)
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
TOKEN_PROGRAM_IDS = frozenset(
    {
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    }
)
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class Task24LinkageProjectionError(ValueError):
    """Raw history or projected graph violates the A2/A4 boundary."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Task24LinkageProjectionError(message)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as exc:
        raise Task24LinkageProjectionError("json_canonicalization_failed") from exc


def _canonical_jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_json_bytes(row) for row in rows)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name}_must_be_mapping")
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


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        return _mapping("json", json.loads(path.read_bytes()))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task24LinkageProjectionError("json_input_invalid") from exc


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    try:
        for line in path.read_bytes().splitlines():
            result.append(dict(_mapping("jsonl_row", json.loads(line))))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task24LinkageProjectionError("jsonl_input_invalid") from exc
    return result


def _iso(value: datetime) -> str:
    _require(
        value.tzinfo is not None and value.utcoffset() is not None,
        "timestamp_must_be_aware",
    )
    return value.astimezone(UTC).isoformat()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(
        parsed.tzinfo is not None and parsed.utcoffset() is not None,
        "parsed_timestamp_naive",
    )
    return parsed


def _base58_decode(value: str) -> bytes:
    _require(isinstance(value, str) and bool(value), "base58_value_invalid")
    number = 0
    try:
        for character in value:
            number = number * 58 + BASE58_ALPHABET.index(character)
    except ValueError as exc:
        raise Task24LinkageProjectionError("base58_character_invalid") from exc
    decoded = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return b"\0" * leading_zeroes + decoded


@dataclass(frozen=True, slots=True)
class NativeTransfer:
    source: str = field(repr=False)
    target: str = field(repr=False)
    lamports: int


@dataclass(frozen=True, slots=True, repr=False)
class TransactionObservation:
    signature: str = field(repr=False)
    signature_digest: str
    slot: int
    transaction_index: int
    block_time: int | None
    account_keys: tuple[str, ...] = field(repr=False)
    signers: tuple[str, ...] = field(repr=False)
    native_transfers: tuple[NativeTransfer, ...] = field(repr=False)
    token_initialize_mints: tuple[str, ...] = field(repr=False)
    transaction_sha256: str
    batch_raw_event_ids: tuple[str, ...]
    observed_at: datetime
    ingested_at: datetime

    @property
    def chain_event_id(self) -> str:
        return f"t24-chain-tx-event-{self.signature_digest}"

    @property
    def transaction_node_id(self) -> str:
        return _stable_node_id("TRANSACTION", self.signature)

    @property
    def event_at(self) -> datetime:
        if self.block_time is None:
            return self.observed_at
        return datetime.fromtimestamp(self.block_time, tz=UTC)


@dataclass(frozen=True, slots=True)
class CapturedPage:
    subject: FrozenSubject
    raw_event_id: str
    observed_at: datetime
    ingested_at: datetime
    pagination_token_present: bool
    transactions: tuple[TransactionObservation, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class ImmediateFunderObservation:
    target_wallet_id: str
    source_raw: str = field(repr=False)
    transaction: TransactionObservation


def _account_keys(transaction: Mapping[str, Any]) -> tuple[str, ...]:
    envelope = _mapping("transaction", transaction["transaction"])
    message = _mapping("message", envelope["message"])
    static = tuple(str(value) for value in _sequence("accountKeys", message["accountKeys"]))
    meta = _mapping("meta", transaction["meta"])
    loaded = _mapping("loadedAddresses", meta.get("loadedAddresses") or {})
    writable = tuple(str(value) for value in _sequence("loaded.writable", loaded.get("writable") or ()))
    readonly = tuple(str(value) for value in _sequence("loaded.readonly", loaded.get("readonly") or ()))
    return (*static, *writable, *readonly)


def _compiled_instructions(transaction: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    envelope = _mapping("transaction", transaction["transaction"])
    message = _mapping("message", envelope["message"])
    result = [
        _mapping("instruction", value)
        for value in _sequence("instructions", message.get("instructions") or ())
    ]
    meta = _mapping("meta", transaction["meta"])
    for group in _sequence("innerInstructions", meta.get("innerInstructions") or ()):
        group_map = _mapping("inner_instruction_group", group)
        result.extend(
            _mapping("inner_instruction", value)
            for value in _sequence(
                "inner_instruction_group.instructions",
                group_map.get("instructions") or (),
            )
        )
    return tuple(result)


def parse_transaction_observation(
    value: Mapping[str, Any],
    *,
    batch_raw_event_id: str,
    observed_at: datetime,
    ingested_at: datetime,
) -> TransactionObservation:
    _require(_mapping("meta", value["meta"]).get("err") is None, "transaction_failed")
    envelope = _mapping("transaction", value["transaction"])
    signatures = _sequence("signatures", envelope["signatures"])
    _require(bool(signatures) and isinstance(signatures[0], str), "primary_signature_invalid")
    signature = str(signatures[0])
    message = _mapping("message", envelope["message"])
    header = _mapping("header", message["header"])
    required_signers = _integer(
        "numRequiredSignatures", header["numRequiredSignatures"]
    )
    keys = _account_keys(value)
    _require(required_signers <= len(keys), "required_signer_count_out_of_range")
    transfers: list[NativeTransfer] = []
    initialized: list[str] = []
    for instruction in _compiled_instructions(value):
        _require("parsed" not in instruction, "provider_parsed_instruction_forbidden")
        program_index = _integer("programIdIndex", instruction["programIdIndex"])
        _require(program_index < len(keys), "program_index_out_of_range")
        accounts = tuple(
            _integer("instruction_account", item)
            for item in _sequence("instruction.accounts", instruction["accounts"])
        )
        _require(all(item < len(keys) for item in accounts), "account_index_out_of_range")
        program_id = keys[program_index]
        if program_id not in TOKEN_PROGRAM_IDS and program_id != SYSTEM_PROGRAM_ID:
            continue
        data = _base58_decode(str(instruction["data"]))
        if program_id == SYSTEM_PROGRAM_ID:
            if len(data) >= 12 and int.from_bytes(data[:4], "little") == 2:
                _require(len(accounts) >= 2, "system_transfer_accounts_missing")
                lamports = int.from_bytes(data[4:12], "little")
                if lamports == 0:
                    continue
                transfers.append(
                    NativeTransfer(
                        source=keys[accounts[0]],
                        target=keys[accounts[1]],
                        lamports=lamports,
                    )
                )
        elif data and data[0] in (0, 20):
            _require(bool(accounts), "initialize_mint_account_missing")
            initialized.append(keys[accounts[0]])
    block_time = value.get("blockTime")
    _require(
        block_time is None
        or (isinstance(block_time, int) and not isinstance(block_time, bool)),
        "block_time_invalid",
    )
    transaction_bytes = _canonical_json_bytes(value)
    signature_digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return TransactionObservation(
        signature=signature,
        signature_digest=signature_digest,
        slot=_integer("slot", value["slot"]),
        transaction_index=_integer("transactionIndex", value["transactionIndex"]),
        block_time=block_time,
        account_keys=keys,
        signers=keys[:required_signers],
        native_transfers=tuple(transfers),
        token_initialize_mints=tuple(sorted(set(initialized))),
        transaction_sha256=_sha256_bytes(transaction_bytes),
        batch_raw_event_ids=(batch_raw_event_id,),
        observed_at=observed_at,
        ingested_at=ingested_at,
    )


def _load_capture_pages(
    *,
    repo_root: Path,
    raw_root: Path,
    run_id: str,
    receipt_sha256: str,
    population: FrozenPopulation,
    capture_logical_root: str,
    exact_wire_logical_root: str,
) -> tuple[Mapping[str, Any], tuple[CapturedPage, ...]]:
    receipt_path = (
        raw_root
        / capture_logical_root
        / f"run={run_id}"
        / "receipts/capture.receipt.json"
    )
    _require(receipt_path.is_file(), "capture_receipt_missing")
    _require(not receipt_path.is_symlink(), "capture_receipt_symlink_forbidden")
    _require(_sha256_file(receipt_path) == receipt_sha256, "capture_receipt_hash_drift")
    receipt = _load_json(receipt_path)
    _require(
        receipt["terminal"] == "RAW_HISTORY_CAPTURED_REQUIRES_PROJECTION",
        "capture_terminal_not_usable",
    )
    _require(receipt["run_id"] == run_id, "capture_run_id_drift")
    _require(receipt["provider_calls"] == 21, "capture_call_count_drift")
    _require(receipt["provider_credits_modeled"] == 210, "capture_credit_drift")
    _require(receipt["retries"] == 0, "capture_retry_drift")
    _require(receipt["cash_spend_usd_cents"] == 0, "capture_cash_drift")
    _require(receipt["credential_values_exposed"] == 0, "capture_secret_exposure")
    if capture_logical_root == "task24_entity_linkage_history_v1_1":
        _require(
            receipt.get("capture_contract_version") == "1.1",
            "capture_contract_version_drift",
        )
        _require(
            receipt.get("dataset_version") == "1.1",
            "capture_dataset_version_drift",
        )
        _require(
            receipt.get("stored_exact_wire_bytes") == receipt.get("received_bytes"),
            "capture_exact_wire_inventory_drift",
        )
    _require(receipt["population"]["fingerprint_sha256"] == population.fingerprint_sha256, "population_fingerprint_drift")
    attempts = sorted(receipt["attempts"], key=lambda item: item["rpc_id"])
    pages_receipt = sorted(receipt["pages"], key=lambda item: item["rpc_id"])
    _require(len(attempts) == len(pages_receipt) == len(population.subjects) == 21, "capture_inventory_count_drift")
    result: list[CapturedPage] = []
    for subject, attempt, page_receipt in zip(
        population.subjects, attempts, pages_receipt, strict=True
    ):
        rpc_id = attempt["rpc_id"]
        _require(attempt["subject_id"] == subject.subject_id, "capture_subject_order_drift")
        _require(attempt["terminal_class"] == "SUCCESS", "capture_attempt_not_success")
        _require(attempt["status_code"] == 200, "capture_http_status_drift")
        partition = raw_root / str(attempt["logical_location"])
        _require(partition.is_file(), "capture_partition_missing")
        _require(not partition.is_symlink(), "capture_partition_symlink_forbidden")
        _require(_sha256_file(partition) == attempt["partition_file_sha256"], "capture_partition_hash_drift")
        events = _events_from_table(pq.read_table(partition))
        _require(len(events) == 1, "capture_partition_row_count_drift")
        event = events[0]
        _require(event.raw_event_id == attempt["raw_event_id"], "capture_raw_event_id_drift")
        _require(event.content_sha256 == attempt["response_sha256"], "capture_response_hash_drift")
        _require(
            _sha256_bytes(canonical_raw_event_rows_bytes(events))
            == attempt["partition_content_sha256"],
            "capture_partition_content_drift",
        )
        exact_wire_location = attempt.get("exact_wire_logical_location")
        exact_wire_sha256 = attempt.get("exact_wire_response_sha256")
        exact_wire_bytes = attempt.get("exact_wire_response_bytes")
        _require(
            isinstance(exact_wire_location, str) and bool(exact_wire_location),
            "exact_wire_response_not_retained",
        )
        _require(
            exact_wire_location
            == (
                f"{exact_wire_logical_root}/"
                f"run={run_id}/{rpc_id:02d}-history.response.json"
            ),
            "exact_wire_response_location_drift",
        )
        _require(
            isinstance(exact_wire_sha256, str) and len(exact_wire_sha256) == 64,
            "exact_wire_response_hash_missing",
        )
        _require(
            isinstance(exact_wire_bytes, int)
            and not isinstance(exact_wire_bytes, bool)
            and exact_wire_bytes >= 0,
            "exact_wire_response_bytes_missing",
        )
        exact_wire_path = raw_root / exact_wire_location
        _require(exact_wire_path.is_file(), "exact_wire_response_missing")
        _require(not exact_wire_path.is_symlink(), "exact_wire_response_symlink_forbidden")
        exact_wire_body = exact_wire_path.read_bytes()
        _require(len(exact_wire_body) == exact_wire_bytes, "exact_wire_response_size_drift")
        _require(
            _sha256_bytes(exact_wire_body) == exact_wire_sha256,
            "exact_wire_response_hash_drift",
        )
        _require(
            json.loads(exact_wire_body) == json.loads(event.redacted_body),
            "wire_and_canonical_response_semantic_drift",
        )
        page = parse_history_response(
            exact_wire_body,
            expected_id=rpc_id,
            limit=HistoryCapturePlan().limit_each,
        )
        _require(
            page.response_sha256 == page_receipt["response_sha256"],
            "page_original_response_hash_drift",
        )
        _require(page.transaction_count == page_receipt["transaction_count"], "page_transaction_count_drift")
        _require(page.first_slot == page_receipt["first_slot"], "page_first_slot_drift")
        _require(page.last_slot == page_receipt["last_slot"], "page_last_slot_drift")
        _require(
            page.pagination_token_present == page_receipt["pagination_token_present"],
            "page_pagination_token_drift",
        )
        body = _mapping("history_response", json.loads(exact_wire_body))
        rows = _sequence("history_data", _mapping("history_result", body["result"])["data"])
        observations = tuple(
            parse_transaction_observation(
                _mapping("history_transaction", row),
                batch_raw_event_id=event.raw_event_id,
                observed_at=event.observed_at,
                ingested_at=event.ingested_at,
            )
            for row in rows
        )
        order = [(item.slot, item.transaction_index) for item in observations]
        _require(order == sorted(order), "slot_transaction_index_order_drift")
        result.append(
            CapturedPage(
                subject=subject,
                raw_event_id=event.raw_event_id,
                observed_at=event.observed_at,
                ingested_at=event.ingested_at,
                pagination_token_present=page.pagination_token_present,
                transactions=observations,
            )
        )
    return receipt, tuple(result)


def _merge_transactions(pages: Sequence[CapturedPage]) -> tuple[dict[str, TransactionObservation], int]:
    merged: dict[str, TransactionObservation] = {}
    conflicts = 0
    for page in pages:
        for transaction in page.transactions:
            existing = merged.get(transaction.signature)
            if existing is None:
                merged[transaction.signature] = transaction
                continue
            if existing.transaction_sha256 != transaction.transaction_sha256:
                conflicts += 1
                continue
            merged[transaction.signature] = replace(
                existing,
                batch_raw_event_ids=tuple(
                    sorted(
                        set(existing.batch_raw_event_ids)
                        | set(transaction.batch_raw_event_ids)
                    )
                ),
                observed_at=min(existing.observed_at, transaction.observed_at),
                ingested_at=max(existing.ingested_at, transaction.ingested_at),
            )
    return merged, conflicts


def _immediate_funders(
    pages: Sequence[CapturedPage],
) -> tuple[tuple[ImmediateFunderObservation, ...], int, int]:
    result: list[ImmediateFunderObservation] = []
    absent = 0
    ambiguous = 0
    for page in pages:
        if page.subject.node_type != "WALLET":
            continue
        found = False
        for transaction in page.transactions:
            incoming = tuple(
                item
                for item in transaction.native_transfers
                if item.target == page.subject.raw_public_key
                and item.source != item.target
            )
            if not incoming:
                continue
            sources = {item.source for item in incoming}
            if len(sources) == 1:
                result.append(
                    ImmediateFunderObservation(
                        target_wallet_id=page.subject.subject_id,
                        source_raw=next(iter(sources)),
                        transaction=transaction,
                    )
                )
            else:
                ambiguous += 1
            found = True
            break
        if not found:
            absent += 1
    return tuple(result), absent, ambiguous


def _mint_creator(
    mint: FrozenSubject, page: CapturedPage
) -> tuple[str, TransactionObservation] | None:
    _require(page.subject.subject_id == mint.subject_id, "mint_page_subject_drift")
    for transaction in page.transactions:
        if mint.raw_public_key not in transaction.token_initialize_mints:
            continue
        external_signers = tuple(
            signer for signer in transaction.signers if signer != mint.raw_public_key
        )
        if len(external_signers) == 1:
            return external_signers[0], transaction
        return None
    return None


def _raw_node(
    *,
    node_type: str,
    raw_public_key: str,
    transaction: TransactionObservation,
    quality_flags: Sequence[str],
) -> dict[str, Any]:
    node_id = _stable_node_id(node_type, raw_public_key)
    digest = node_id.rsplit("-", 1)[-1]
    payload: dict[str, Any] = {
        "node_id": node_id,
        "node_type": node_type,
        "business_key": f"{node_type}:{digest}",
        "event_at": _iso(transaction.event_at),
        "observed_at": _iso(transaction.observed_at),
        "first_reliable_available_at": _iso(transaction.observed_at),
        "available_to_strategy_at": _iso(transaction.observed_at),
        "ingested_at": _iso(transaction.ingested_at),
        "source": "HELIUS_GET_TRANSACTIONS_FOR_ADDRESS",
        "source_version": "helius-history-observed-2026-08-02",
        "evidence_class": "RAW_ONCHAIN",
        "revision_number": 1,
        "revision_of": None,
        "quality_flags": sorted(set(quality_flags)),
    }
    payload["content_sha256"] = _sha256_bytes(_canonical_json_bytes(payload))
    return payload


def _entity_candidate_node(
    *,
    candidate_key: str,
    member_edges: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    digest = hashlib.sha256(candidate_key.encode("utf-8")).hexdigest()
    availability = max(_parse_iso(str(edge["available_to_strategy_at"])) for edge in member_edges)
    observed = max(_parse_iso(str(edge["observed_at"])) for edge in member_edges)
    ingested = max(_parse_iso(str(edge["ingested_at"])) for edge in member_edges)
    event_at = max(_parse_iso(str(edge["event_at"])) for edge in member_edges)
    payload: dict[str, Any] = {
        "node_id": f"t24-entity-candidate-{digest}",
        "node_type": "ENTITY_CANDIDATE",
        "business_key": f"ENTITY_CANDIDATE:{digest}",
        "event_at": _iso(event_at),
        "observed_at": _iso(observed),
        "first_reliable_available_at": _iso(availability),
        "available_to_strategy_at": _iso(availability),
        "ingested_at": _iso(ingested),
        "source": "PROJECT_RULE",
        "source_version": RULE_VERSION,
        "evidence_class": "PROJECT_INFERENCE",
        "revision_number": 1,
        "revision_of": None,
        "quality_flags": ["REVERSIBLE_CANDIDATE", "SHARED_IMMEDIATE_FUNDER"],
    }
    payload["content_sha256"] = _sha256_bytes(_canonical_json_bytes(payload))
    return payload


def _edge(
    *,
    edge_type: str,
    source_node: Mapping[str, Any],
    target_node: Mapping[str, Any],
    evidence_class: str,
    confidence_class: str,
    event_at: datetime,
    observed_at: datetime,
    available_at: datetime,
    ingested_at: datetime,
    source: str,
    source_version: str,
    supporting_raw_event_ids: Sequence[str],
    supporting_edge_ids: Sequence[str],
    supporting_transaction_node_ids: Sequence[str],
    quality_flags: Sequence[str],
) -> dict[str, Any]:
    identity = "|".join(
        (
            RULE_VERSION,
            edge_type,
            str(source_node["node_id"]),
            str(target_node["node_id"]),
            *sorted(supporting_raw_event_ids),
            *sorted(supporting_edge_ids),
            *sorted(supporting_transaction_node_ids),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    payload: dict[str, Any] = {
        "edge_id": f"t24-edge-{digest}",
        "source_node_id": source_node["node_id"],
        "source_node_type": source_node["node_type"],
        "target_node_id": target_node["node_id"],
        "target_node_type": target_node["node_type"],
        "edge_type": edge_type,
        "evidence_class": evidence_class,
        "confidence_class": confidence_class,
        "rule_version": RULE_VERSION,
        "supporting_raw_event_ids": sorted(set(supporting_raw_event_ids)),
        "supporting_edge_ids": sorted(set(supporting_edge_ids)),
        "supporting_transaction_node_ids": sorted(
            set(supporting_transaction_node_ids)
        ),
        "event_at": _iso(event_at),
        "observed_at": _iso(observed_at),
        "first_reliable_available_at": _iso(available_at),
        "available_to_strategy_at": _iso(available_at),
        "ingested_at": _iso(ingested_at),
        "source": source,
        "source_version": source_version,
        "revision_number": 1,
        "revision_of": None,
        "quality_flags": sorted(set(quality_flags)),
        "conflict_set_id": None,
    }
    payload["content_sha256"] = _sha256_bytes(_canonical_json_bytes(payload))
    return payload


def _artifact_record(repo_root: Path, path: Path, rows: int) -> dict[str, Any]:
    return {
        "path": path.relative_to(repo_root).as_posix(),
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
        "rows": rows,
    }


def _write_bytes(output_dir: Path, name: str, payload: bytes) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    _require(not output_dir.is_symlink(), "output_directory_symlink_forbidden")
    path = output_dir / name
    if path.exists():
        _require(path.read_bytes() == payload, f"existing_output_drift:{name}")
        return path
    path.write_bytes(payload)
    return path


def build_task24_linkage_projection(
    *,
    repo_root: Path,
    raw_root: Path,
    run_id: str,
    receipt_sha256: str,
    output_dir: Path,
    capture_logical_root: str = "task24_entity_linkage_history_v1_1",
    exact_wire_logical_root: str = "task24_entity_linkage_history_wire_v1_1",
) -> Mapping[str, Any]:
    repo_root = repo_root.resolve()
    raw_root = raw_root.resolve()
    output_dir = output_dir.resolve()
    _require(raw_root == (repo_root / "data/raw").resolve(), "raw_root_drift")
    _require(output_dir.is_relative_to(repo_root), "output_outside_repository")
    preflight = repo_root / "docs/evidence/task24/a5_raw_history_capture_preflight_v1.json"
    _require(_sha256_file(preflight) == PREFLIGHT_SHA256, "preflight_hash_drift")
    population = load_frozen_population(repo_root)
    capture_receipt, pages = _load_capture_pages(
        repo_root=repo_root,
        raw_root=raw_root,
        run_id=run_id,
        receipt_sha256=receipt_sha256,
        population=population,
        capture_logical_root=capture_logical_root,
        exact_wire_logical_root=exact_wire_logical_root,
    )
    merged_transactions, duplicate_conflicts = _merge_transactions(pages)
    _require(duplicate_conflicts == 0, "duplicate_transaction_payload_conflict")
    funders, funder_absent, funder_ambiguous = _immediate_funders(pages)
    creator = _mint_creator(population.mint, pages[0])

    a3_root = repo_root / "docs/evidence/task24/a3_projection_v1"
    a3_nodes_path = a3_root / "entity_nodes_v1.jsonl"
    a3_edges_path = a3_root / "entity_edges_v1.jsonl"
    a3_adjusted_path = a3_root / "entity_adjusted_concentration_v1.json"
    _require(_sha256_file(a3_nodes_path) == A3_NODES_SHA256, "a3_nodes_hash_drift")
    _require(_sha256_file(a3_edges_path) == A3_EDGES_SHA256, "a3_edges_hash_drift")
    _require(_sha256_file(a3_adjusted_path) == A3_ADJUSTED_SHA256, "a3_adjusted_hash_drift")
    nodes_by_id = {row["node_id"]: row for row in _load_jsonl(a3_nodes_path)}
    edges: list[dict[str, Any]] = _load_jsonl(a3_edges_path)
    population_by_raw = {
        subject.raw_public_key: subject for subject in population.wallets
    }

    transaction_nodes: dict[str, dict[str, Any]] = {}
    funder_edges_by_wallet: dict[str, dict[str, Any]] = {}
    funder_transaction_by_wallet: dict[str, str] = {}
    groups: dict[str, list[str]] = defaultdict(list)
    for observation in funders:
        transaction = observation.transaction
        tx_node = _raw_node(
            node_type="TRANSACTION",
            raw_public_key=transaction.signature,
            transaction=transaction,
            quality_flags=("EXACT_CHAIN_TRANSACTION", "FUNDER_SUPPORT"),
        )
        transaction_nodes[tx_node["node_id"]] = tx_node
        nodes_by_id.setdefault(tx_node["node_id"], tx_node)
        funder_node = _raw_node(
            node_type="WALLET",
            raw_public_key=observation.source_raw,
            transaction=transaction,
            quality_flags=("IMMEDIATE_FUNDER_ROLE_ONLY",),
        )
        nodes_by_id.setdefault(funder_node["node_id"], funder_node)
        target_node = nodes_by_id[observation.target_wallet_id]
        raw_ids = (*transaction.batch_raw_event_ids, transaction.chain_event_id)
        edge = _edge(
            edge_type="RAW_IMMEDIATE_FUNDER",
            source_node=funder_node,
            target_node=target_node,
            evidence_class="RAW_ONCHAIN",
            confidence_class="DIRECT",
            event_at=transaction.event_at,
            observed_at=transaction.observed_at,
            available_at=transaction.observed_at,
            ingested_at=transaction.ingested_at,
            source="HELIUS_GET_TRANSACTIONS_FOR_ADDRESS",
            source_version="IMMEDIATE_FUNDER_V1",
            supporting_raw_event_ids=raw_ids,
            supporting_edge_ids=(),
            supporting_transaction_node_ids=(tx_node["node_id"],),
            quality_flags=(
                "EXPLICIT_NATIVE_SOL_TRANSFER",
                "FIRST_QUALIFYING_IN_OLDEST_100",
                "NOT_ULTIMATE_FUNDER_OR_OWNERSHIP",
            ),
        )
        edges.append(edge)
        funder_edges_by_wallet[observation.target_wallet_id] = edge
        funder_transaction_by_wallet[observation.target_wallet_id] = tx_node["node_id"]
        groups[funder_node["node_id"]].append(observation.target_wallet_id)

    common_signer_edges: dict[tuple[str, str], dict[str, Any]] = {}
    for transaction in merged_transactions.values():
        population_signers = tuple(
            sorted(
                {
                    population_by_raw[signer].subject_id
                    for signer in transaction.signers
                    if signer in population_by_raw
                }
            )
        )
        if len(population_signers) < 2:
            continue
        tx_node = _raw_node(
            node_type="TRANSACTION",
            raw_public_key=transaction.signature,
            transaction=transaction,
            quality_flags=("EXACT_CHAIN_TRANSACTION", "COMMON_SIGNER_SUPPORT"),
        )
        transaction_nodes[tx_node["node_id"]] = tx_node
        nodes_by_id.setdefault(tx_node["node_id"], tx_node)
        for wallet_id in population_signers:
            edge = _edge(
                edge_type="RAW_COMMON_TRANSACTION_SIGNER",
                source_node=nodes_by_id[wallet_id],
                target_node=tx_node,
                evidence_class="RAW_ONCHAIN",
                confidence_class="DIRECT",
                event_at=transaction.event_at,
                observed_at=transaction.observed_at,
                available_at=transaction.observed_at,
                ingested_at=transaction.ingested_at,
                source="HELIUS_GET_TRANSACTIONS_FOR_ADDRESS",
                source_version="COMMON_SIGNER_SEPARATE_EVENT_V1",
                supporting_raw_event_ids=(
                    *transaction.batch_raw_event_ids,
                    transaction.chain_event_id,
                ),
                supporting_edge_ids=(),
                supporting_transaction_node_ids=(tx_node["node_id"],),
                quality_flags=(
                    "REQUIRED_TRANSACTION_SIGNER",
                    "COMMON_SIGNER_NOT_OWNERSHIP",
                ),
            )
            edges.append(edge)
            common_signer_edges[(wallet_id, tx_node["node_id"])] = edge

    mint_creator_status = "NOT_TESTABLE_CREATOR_ROLE_AMBIGUOUS_OR_ABSENT"
    if creator is not None:
        creator_raw, transaction = creator
        tx_node = _raw_node(
            node_type="TRANSACTION",
            raw_public_key=transaction.signature,
            transaction=transaction,
            quality_flags=("EXACT_CHAIN_TRANSACTION", "MINT_CREATION_SUPPORT"),
        )
        nodes_by_id.setdefault(tx_node["node_id"], tx_node)
        creator_node = _raw_node(
            node_type="WALLET",
            raw_public_key=creator_raw,
            transaction=transaction,
            quality_flags=("IMMEDIATE_MINT_CREATOR_ROLE_ONLY",),
        )
        nodes_by_id.setdefault(creator_node["node_id"], creator_node)
        edges.append(
            _edge(
                edge_type="RAW_MINT_CREATED_BY_WALLET",
                source_node=nodes_by_id[population.mint.subject_id],
                target_node=creator_node,
                evidence_class="RAW_ONCHAIN",
                confidence_class="DIRECT",
                event_at=transaction.event_at,
                observed_at=transaction.observed_at,
                available_at=transaction.observed_at,
                ingested_at=transaction.ingested_at,
                source="HELIUS_GET_TRANSACTIONS_FOR_ADDRESS",
                source_version="MINT_CREATOR_V1",
                supporting_raw_event_ids=(
                    *transaction.batch_raw_event_ids,
                    transaction.chain_event_id,
                ),
                supporting_edge_ids=(),
                supporting_transaction_node_ids=(tx_node["node_id"],),
                quality_flags=(
                    "INITIALIZE_MINT_EXACT_TRANSACTION",
                    "SOLE_EXTERNAL_REQUIRED_SIGNER",
                    "NOT_BENEFICIAL_OWNERSHIP",
                ),
            )
        )
        mint_creator_status = "DIRECT_IMMEDIATE_CREATOR_ROLE_PROJECTED"

    candidate_records: list[dict[str, Any]] = []
    membership_edges: list[dict[str, Any]] = []
    derived_pair_edges: list[dict[str, Any]] = []
    for funder_node_id, member_ids_all in sorted(groups.items()):
        member_ids = sorted(member_ids_all)
        if len(member_ids) < 2:
            continue
        pair_edges_for_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for left_id, right_id in itertools.combinations(member_ids, 2):
            left_funder = funder_edges_by_wallet[left_id]
            right_funder = funder_edges_by_wallet[right_id]
            event_at = max(
                _parse_iso(left_funder["event_at"]),
                _parse_iso(right_funder["event_at"]),
            )
            observed = max(
                _parse_iso(left_funder["observed_at"]),
                _parse_iso(right_funder["observed_at"]),
            )
            available = max(
                _parse_iso(left_funder["available_to_strategy_at"]),
                _parse_iso(right_funder["available_to_strategy_at"]),
            )
            ingested = max(
                _parse_iso(left_funder["ingested_at"]),
                _parse_iso(right_funder["ingested_at"]),
            )
            pair_edge = _edge(
                edge_type="DERIVED_SHARED_IMMEDIATE_FUNDER",
                source_node=nodes_by_id[left_id],
                target_node=nodes_by_id[right_id],
                evidence_class="DERIVED_ADJUSTED",
                confidence_class="INFERRED",
                event_at=event_at,
                observed_at=observed,
                available_at=available,
                ingested_at=ingested,
                source="PROJECT_RULE",
                source_version="IMMEDIATE_FUNDER_V1",
                supporting_raw_event_ids=(
                    *left_funder["supporting_raw_event_ids"],
                    *right_funder["supporting_raw_event_ids"],
                ),
                supporting_edge_ids=(
                    left_funder["edge_id"],
                    right_funder["edge_id"],
                ),
                supporting_transaction_node_ids=(
                    *left_funder["supporting_transaction_node_ids"],
                    *right_funder["supporting_transaction_node_ids"],
                ),
                quality_flags=(
                    "SHARED_IMMEDIATE_FUNDER_RULE",
                    "NOT_COMMON_OWNERSHIP",
                ),
            )
            derived_pair_edges.append(pair_edge)
            pair_edges_for_member[left_id].append(pair_edge)
            pair_edges_for_member[right_id].append(pair_edge)
        candidate_key = f"{RULE_VERSION}|SHARED_FUNDER|{funder_node_id}"
        candidate_node = _entity_candidate_node(
            candidate_key=candidate_key,
            member_edges=[funder_edges_by_wallet[item] for item in member_ids],
        )
        nodes_by_id[candidate_node["node_id"]] = candidate_node
        record_members: list[dict[str, Any]] = []
        for member_id in member_ids:
            corroborating_signer_edges: list[dict[str, Any]] = []
            for (wallet_id, tx_node_id), signer_edge in common_signer_edges.items():
                if wallet_id != member_id:
                    continue
                if tx_node_id == funder_transaction_by_wallet[member_id]:
                    continue
                linked_fellows = [
                    other
                    for other in member_ids
                    if other != member_id
                    and (other, tx_node_id) in common_signer_edges
                    and tx_node_id != funder_transaction_by_wallet[other]
                ]
                if linked_fellows:
                    corroborating_signer_edges.extend(
                        [signer_edge]
                        + [common_signer_edges[(other, tx_node_id)] for other in linked_fellows]
                    )
            confidence = "CORROBORATED" if corroborating_signer_edges else "INFERRED"
            funder_edge = funder_edges_by_wallet[member_id]
            supporting_edges = [
                funder_edge,
                *pair_edges_for_member[member_id],
                *corroborating_signer_edges,
            ]
            event_at = max(_parse_iso(edge["event_at"]) for edge in supporting_edges)
            observed = max(_parse_iso(edge["observed_at"]) for edge in supporting_edges)
            available = max(
                _parse_iso(edge["available_to_strategy_at"])
                for edge in supporting_edges
            )
            ingested = max(_parse_iso(edge["ingested_at"]) for edge in supporting_edges)
            membership = _edge(
                edge_type="PROJECT_ENTITY_MEMBERSHIP_CANDIDATE",
                source_node=nodes_by_id[member_id],
                target_node=candidate_node,
                evidence_class="PROJECT_INFERENCE",
                confidence_class=confidence,
                event_at=event_at,
                observed_at=observed,
                available_at=available,
                ingested_at=ingested,
                source="PROJECT_RULE",
                source_version=RULE_VERSION,
                supporting_raw_event_ids=tuple(
                    raw_id
                    for edge in supporting_edges
                    for raw_id in edge["supporting_raw_event_ids"]
                ),
                supporting_edge_ids=tuple(
                    edge["edge_id"] for edge in supporting_edges
                ),
                supporting_transaction_node_ids=tuple(
                    tx_id
                    for edge in supporting_edges
                    for tx_id in edge["supporting_transaction_node_ids"]
                ),
                quality_flags=(
                    "REVERSIBLE_MEMBERSHIP_CANDIDATE",
                    "NO_DESTRUCTIVE_MERGE",
                    f"CONFIDENCE_{confidence}",
                ),
            )
            membership_edges.append(membership)
            record_members.append(
                {
                    "wallet_id": member_id,
                    "membership_edge_id": membership["edge_id"],
                    "confidence_class": confidence,
                    "supporting_edge_ids": membership["supporting_edge_ids"],
                    "supporting_transaction_node_ids": membership[
                        "supporting_transaction_node_ids"
                    ],
                }
            )
        candidate_records.append(
            {
                "candidate_id": candidate_node["node_id"],
                "rule_version": RULE_VERSION,
                "shared_immediate_funder_wallet_id": funder_node_id,
                "member_count": len(record_members),
                "members": sorted(record_members, key=lambda item: item["wallet_id"]),
                "reversible": True,
                "ownership_claimed": False,
            }
        )

    edges.extend(derived_pair_edges)
    edges.extend(membership_edges)
    nodes = sorted(nodes_by_id.values(), key=lambda row: (row["node_type"], row["node_id"]))
    edges.sort(key=lambda row: (row["edge_type"], row["edge_id"]))
    corroborated = sum(
        edge["confidence_class"] == "CORROBORATED" for edge in membership_edges
    )
    inferred = sum(
        edge["confidence_class"] in ("INFERRED", "VENDOR_ONLY")
        for edge in membership_edges
    )
    audit_capacity = min(corroborated, 8) + min(inferred, 8)
    owner_decision = "REDESIGN_DATA" if audit_capacity < 12 else "EXTEND_EVIDENCE"
    candidate_status = (
        "AUDIT_CANDIDATES_READY_FOR_FREEZE"
        if audit_capacity >= 12
        else "INSUFFICIENT_PREDICTED_POSITIVE_CAPACITY"
    )
    candidates = {
        "schema_version": PROJECTION_VERSION,
        "status": candidate_status,
        "rule_version": RULE_VERSION,
        "records": candidate_records,
        "counts": {
            "candidates": len(candidate_records),
            "membership_claims": len(membership_edges),
            "corroborated_positive_claims": corroborated,
            "inferred_or_vendor_positive_claims": inferred,
            "selected_predicted_positive_capacity": audit_capacity,
            "minimum_required_to_open_audit": 12,
        },
        "capacity_formula": "MIN(CORROBORATED_COUNT,8)+MIN(INFERRED_OR_VENDOR_COUNT,8)",
        "owner_decision": owner_decision,
        "raw_public_addresses_persisted": 0,
    }
    adjusted_bytes = a3_adjusted_path.read_bytes()

    nodes_path = _write_bytes(output_dir, "entity_nodes_v1.jsonl", _canonical_jsonl_bytes(nodes))
    edges_path = _write_bytes(output_dir, "entity_edges_v1.jsonl", _canonical_jsonl_bytes(edges))
    candidates_path = _write_bytes(output_dir, "entity_candidates_v1.json", _canonical_json_bytes(candidates))
    adjusted_path = _write_bytes(output_dir, "entity_adjusted_concentration_v1.json", adjusted_bytes)
    artifacts = {
        "entity_nodes_v1": _artifact_record(repo_root, nodes_path, len(nodes)),
        "entity_edges_v1": _artifact_record(repo_root, edges_path, len(edges)),
        "entity_candidates_v1": _artifact_record(repo_root, candidates_path, len(candidate_records)),
        "entity_adjusted_concentration_v1": _artifact_record(repo_root, adjusted_path, 1),
    }
    manifest: dict[str, Any] = {
        "manifest_id": (
            "T24-A5R1-EXACT-WIRE-RECAPTURE-PROJECTION-001"
            if capture_logical_root == "task24_entity_linkage_history_v1_1"
            else "T24-A5-BOUNDED-RAW-HISTORY-PROJECTION-001"
        ),
        "schema_version": PROJECTION_VERSION,
        "task_id": "TASK-24",
        "atom": (
            "T24-A5R1_EXACT_WIRE_RETENTION_RECAPTURE_V1"
            if capture_logical_root == "task24_entity_linkage_history_v1_1"
            else "T24-A5_BOUNDED_RAW_HISTORY_FEASIBILITY_CAPTURE_V1"
        ),
        "as_of": "2026-08-02",
        "status": "PASS_BOUNDED_HISTORY_PROJECTION_INSUFFICIENT_CAPACITY" if audit_capacity < 12 else "PASS_AUDIT_CAPACITY_READY",
        "owner_decision": owner_decision,
        "capture": {
            "run_id": run_id,
            "receipt_sha256": receipt_sha256,
            "provider_calls": capture_receipt["provider_calls"],
            "provider_credits_modeled": capture_receipt["provider_credits_modeled"],
            "cash_spend_usd_cents": capture_receipt["cash_spend_usd_cents"],
            "transactions_returned": sum(len(page.transactions) for page in pages),
            "unique_transactions": len(merged_transactions),
            "truncated_subjects": sum(page.pagination_token_present for page in pages),
            "retries": capture_receipt["retries"],
            "capture_contract_version": capture_receipt.get("capture_contract_version"),
            "exact_wire_files_verified": sum(
                "exact_wire_response_sha256" in item
                for item in capture_receipt["attempts"]
            ),
            "exact_wire_bytes_verified": capture_receipt.get(
                "stored_exact_wire_bytes", 0
            ),
            "wire_canonical_semantic_equalities_verified": sum(
                "exact_wire_response_sha256" in item
                for item in capture_receipt["attempts"]
            ),
        },
        "population": population.safe_receipt(),
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "raw_immediate_funder": len(funder_edges_by_wallet),
            "immediate_funder_absent": funder_absent,
            "immediate_funder_ambiguous": funder_ambiguous,
            "raw_common_transaction_signer": len(common_signer_edges),
            "raw_mint_created_by_wallet": int(creator is not None),
            "derived_shared_immediate_funder": len(derived_pair_edges),
            "entity_candidates": len(candidate_records),
            "membership_claims": len(membership_edges),
            "corroborated_positive_claims": corroborated,
            "inferred_or_vendor_positive_claims": inferred,
            "selected_predicted_positive_capacity": audit_capacity,
            "duplicate_transaction_payload_conflicts": duplicate_conflicts,
        },
        "mint_creator_status": mint_creator_status,
        "artifacts": artifacts,
        "false_positive_audit": {
            "status": "NOT_TESTABLE_INSUFFICIENT_PREDICTED_POSITIVES" if audit_capacity < 12 else "READY_FOR_FROZEN_SELECTION",
            "minimum_required": 12,
            "capacity": audit_capacity,
            "manual_labels_opened": 0,
        },
        "adjusted_concentration": {
            "status": "UNCHANGED_NOT_AVAILABLE_EXCLUSION_INVENTORY_INCOMPLETE",
            "holder_exclusions_changed": 0,
        },
        "privacy": {
            "raw_public_addresses_persisted": 0,
            "raw_transaction_signatures_persisted": 0,
            "pseudonym_rule": "SHA256(TASK24_ENTITY_GRAPH_V1|node_type|raw_public_key)",
        },
        "non_claims": [
            "BENEFICIAL_OWNERSHIP",
            "ULTIMATE_FUNDER",
            "AUTHORITATIVE_BUNDLE_MEMBERSHIP",
            "HOLDER_EXCLUSION_OR_STRATEGY_VETO",
            "ALPHA_OR_GENERALIZATION",
            "EXECUTION_PNL_NETRETURN_OR_CASHFLOW",
            "TASK24_DONE",
        ],
        "authority": {
            "provider_api_rpc_calls": 21,
            "provider_credits_modeled": 210,
            "credential_values_exposed": 0,
            "cash_spend_usd_cents": 0,
            "r3_or_outcome_reads": 0,
            "wallet_signer_transaction_actions": 0,
        },
        "next_boundary": {
            "recommended_atom": "T24-A6_BOUNDED_DATA_REDESIGN_OR_STOP_DECISION_V1" if audit_capacity < 12 else "T24-A6_FROZEN_FALSE_POSITIVE_AUDIT_V1",
            "authorized": False,
            "reason": "The bounded oldest-100 probe produced fewer than 12 selected predicted-positive claims." if audit_capacity < 12 else "The frozen predicted-positive capacity reached the audit minimum.",
        },
    }
    manifest_path = _write_bytes(output_dir, "projection_manifest_v1.json", _canonical_json_bytes(manifest))
    return {
        "status": manifest["status"],
        "owner_decision": owner_decision,
        "counts": manifest["counts"],
        "projection_manifest": _artifact_record(repo_root, manifest_path, 1),
    }
