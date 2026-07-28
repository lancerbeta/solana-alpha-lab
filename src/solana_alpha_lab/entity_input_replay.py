"""Fail-closed offline replay for one retained TASK-11 entity-input probe."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias

import pyarrow.parquet as pq

from solana_alpha_lab.contracts.schema_v1 import RawResponseStatus
from solana_alpha_lab.entity_input_transport import (
    EXPECTED_HOST,
    EXPECTED_METHODS,
    RUN_ID_RE,
    EntityPilotPlan,
    LargestAccountsObservation,
    OwnersObservation,
    TokenSupplyObservation,
    parse_largest_accounts,
    parse_owner_accounts,
    parse_token_supply,
)
from solana_alpha_lab.entity_inputs import (
    ConfidenceLevel,
    EvidenceClass,
    ExclusionAssessment,
    ExclusionDisposition,
    HolderAccountObservation,
    HolderSnapshotInput,
    calculate_holder_metrics,
    project_entity_snapshots,
    validate_durable_metadata,
)
from solana_alpha_lab.storage import canonical_raw_event_rows_bytes
from solana_alpha_lab.storage.parquet_store import _events_from_table

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

REPLAY_CONTRACT_VERSION = "1.0"
EXPECTED_RECEIPT_KEYS = frozenset(
    {
        "adjusted_concentration",
        "attempts",
        "cash_spend_usd_cents",
        "completed_calls",
        "context_slot_spread",
        "dataset_id",
        "dataset_version",
        "deployer_funder_bundler",
        "error_code",
        "largest_accounts_context_slot",
        "logical_root",
        "modeled_credits",
        "owner_resolution_count",
        "owners_context_slot",
        "planned_calls",
        "raw_event_ids",
        "raw_top_accounts_amount_atomic",
        "raw_top_accounts_supply_share",
        "received_bytes",
        "retries",
        "run_id",
        "selected_mint",
        "stored_partition_bytes",
        "supply_atomic",
        "supply_context_slot",
        "terminal",
        "top_account_count",
        "transport_contract_version",
        "wallet_signer_transaction_actions",
    }
)
EXPECTED_ATTEMPT_KEYS = frozenset(
    {
        "error_class",
        "logical_location",
        "method",
        "partition_bytes",
        "partition_content_sha256",
        "partition_file_sha256",
        "raw_event_id",
        "redacted_body_sha256",
        "response_bytes",
        "response_complete_at",
        "response_status",
        "rpc_id",
        "safe_request",
        "status_code",
        "terminal_class",
    }
)
EXPECTED_SAFE_REQUEST_KEYS = frozenset(
    {
        "attempt_id",
        "body_sha256",
        "case_id",
        "host",
        "method",
        "path",
        "provider",
        "query_keys",
        "transport",
    }
)


class EntityReplayContractError(ValueError):
    """Retained evidence no longer agrees with the frozen replay contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EntityReplayContractError(message)


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name}_must_be_mapping")
    return value


def _sequence(name: str, value: Any) -> Sequence[Any]:
    _require(
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray)),
        f"{name}_must_be_sequence",
    )
    return value


def _integer(name: str, value: Any) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{name}_must_be_integer",
    )
    return value


def _text(name: str, value: Any) -> str:
    _require(isinstance(value, str) and bool(value), f"{name}_must_be_text")
    return value


def _sha256(name: str, value: Any) -> str:
    text = _text(name, value)
    _require(
        len(text) == 64
        and all(character in "0123456789abcdef" for character in text),
        f"{name}_must_be_lowercase_sha256",
    )
    return text


def _aware_timestamp(name: str, value: Any) -> datetime:
    text = _text(name, value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EntityReplayContractError(f"{name}_invalid") from exc
    _require(
        parsed.tzinfo is not None and parsed.utcoffset() is not None,
        f"{name}_must_be_aware",
    )
    return parsed


def _exact_keys(
    name: str,
    value: Mapping[str, Any],
    expected: frozenset[str],
) -> None:
    actual = set(value)
    _require(not (expected - actual), f"{name}_required_keys_missing")
    _require(not (actual - expected), f"{name}_unknown_keys")


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
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


def _receipt_path(raw_root: Path, plan: EntityPilotPlan, run_id: str) -> Path:
    _require(RUN_ID_RE.fullmatch(run_id) is not None, "run_id_invalid")
    logical = Path(plan.logical_root) / f"run={run_id}"
    path = raw_root / logical / "receipts" / "probe.receipt.json"
    resolved_root = raw_root.resolve()
    resolved_path = path.resolve()
    _require(
        resolved_path.is_relative_to(resolved_root),
        "receipt_path_escapes_raw_root",
    )
    _require(
        path.is_file() and not path.is_symlink(),
        "receipt_missing_or_unsafe",
    )
    return path


def _read_receipt(
    raw_root: Path,
    plan: EntityPilotPlan,
    run_id: str,
) -> tuple[Mapping[str, Any], bytes, str]:
    path = _receipt_path(raw_root, plan, run_id)
    data = path.read_bytes()
    _require(data.endswith(b"\n"), "receipt_final_newline_required")
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EntityReplayContractError("receipt_json_invalid") from exc
    receipt = _mapping("receipt", document)
    _exact_keys("receipt", receipt, EXPECTED_RECEIPT_KEYS)
    _require(
        data == _canonical_json_bytes(receipt),
        "receipt_not_canonical_json",
    )
    return receipt, data, hashlib.sha256(data).hexdigest()


def _verify_receipt_summary(
    receipt: Mapping[str, Any],
    plan: EntityPilotPlan,
    run_id: str,
) -> Sequence[Any]:
    checks = (
        (receipt["run_id"] == run_id, "receipt_run_id_drift"),
        (
            receipt["logical_root"] == f"{plan.logical_root}/run={run_id}",
            "receipt_logical_root_drift",
        ),
        (
            receipt["dataset_id"] == plan.dataset_id,
            "receipt_dataset_id_drift",
        ),
        (
            receipt["dataset_version"] == plan.dataset_version,
            "receipt_dataset_version_drift",
        ),
        (
            receipt["selected_mint"] == plan.selected_mint,
            "receipt_selected_mint_drift",
        ),
        (
            receipt["transport_contract_version"] == "1.0",
            "receipt_transport_version_drift",
        ),
        (
            receipt["terminal"] == "RAW_TOP20_FEASIBILITY_CAPTURED",
            "receipt_terminal_not_accepted",
        ),
        (receipt["error_code"] is None, "receipt_error_present"),
        (
            receipt["adjusted_concentration"] is None,
            "receipt_adjusted_concentration_forbidden",
        ),
        (
            receipt["deployer_funder_bundler"] == "NOT_TESTED",
            "receipt_entity_claim_drift",
        ),
        (
            _integer("planned_calls", receipt["planned_calls"])
            == plan.provider_calls,
            "receipt_planned_calls_drift",
        ),
        (
            _integer("completed_calls", receipt["completed_calls"])
            == plan.provider_calls,
            "receipt_completed_calls_drift",
        ),
        (
            _integer("retries", receipt["retries"]) == 0,
            "receipt_retries_drift",
        ),
        (
            _integer("modeled_credits", receipt["modeled_credits"])
            == plan.modeled_credits_total,
            "receipt_modeled_credits_drift",
        ),
        (
            _integer(
                "cash_spend_usd_cents",
                receipt["cash_spend_usd_cents"],
            )
            == 0,
            "receipt_cash_spend_drift",
        ),
        (
            _integer(
                "wallet_signer_transaction_actions",
                receipt["wallet_signer_transaction_actions"],
            )
            == 0,
            "receipt_wallet_action_drift",
        ),
        (
            0
            <= _integer("received_bytes", receipt["received_bytes"])
            <= plan.received_bytes_total,
            "receipt_received_bytes_cap",
        ),
        (
            0
            <= _integer(
                "stored_partition_bytes",
                receipt["stored_partition_bytes"],
            )
            <= plan.stored_bytes_total,
            "receipt_stored_bytes_cap",
        ),
    )
    for condition, message in checks:
        _require(condition, message)
    attempts = _sequence("attempts", receipt["attempts"])
    _require(
        len(attempts) == plan.provider_calls,
        "receipt_attempt_count_drift",
    )
    return attempts


def _verify_safe_request(
    value: Any,
    *,
    rpc_id: int,
    method: str,
    plan: EntityPilotPlan,
) -> Mapping[str, Any]:
    safe = _mapping("safe_request", value)
    _exact_keys("safe_request", safe, EXPECTED_SAFE_REQUEST_KEYS)
    expected = {
        "attempt_id": f"T11-A3-R{rpc_id:02d}",
        "case_id": method,
        "host": EXPECTED_HOST,
        "method": "POST",
        "path": "/",
        "provider": plan.provider_id,
        "query_keys": ["api-key"],
        "transport": "HTTP",
    }
    for key, expected_value in expected.items():
        _require(safe[key] == expected_value, f"safe_request_{key}_drift")
    _sha256("safe_request.body_sha256", safe["body_sha256"])
    _require(
        not any(
            key in safe
            for key in (
                "api_key",
                "api-key",
                "authorization",
                "query",
                "url",
            )
        ),
        "credential_value_field_forbidden",
    )
    return safe


def _load_attempt_events(
    raw_root: Path,
    plan: EntityPilotPlan,
    run_id: str,
    attempts: Sequence[Any],
) -> tuple[tuple[Any, ...], list[dict[str, JsonValue]]]:
    events: list[Any] = []
    evidence: list[dict[str, JsonValue]] = []
    partition_bytes_total = 0
    response_bytes_total = 0
    resolved_root = raw_root.resolve()
    for index, (raw_attempt, expected_method) in enumerate(
        zip(attempts, EXPECTED_METHODS, strict=True),
        start=1,
    ):
        attempt = _mapping(f"attempt_{index}", raw_attempt)
        _exact_keys(f"attempt_{index}", attempt, EXPECTED_ATTEMPT_KEYS)
        _require(
            _integer(f"attempt_{index}.rpc_id", attempt["rpc_id"]) == index,
            "attempt_rpc_id_drift",
        )
        method = _text(f"attempt_{index}.method", attempt["method"])
        _require(method == expected_method, "attempt_method_drift")
        _require(attempt["error_class"] is None, "attempt_error_present")
        _require(attempt["status_code"] == 200, "attempt_http_status_drift")
        _require(
            attempt["terminal_class"] == "SUCCESS",
            "attempt_terminal_class_drift",
        )
        _require(
            attempt["response_status"] == str(RawResponseStatus.SUCCESS),
            "attempt_response_status_drift",
        )
        _verify_safe_request(
            attempt["safe_request"],
            rpc_id=index,
            method=method,
            plan=plan,
        )
        expected_location = (
            f"{plan.logical_root}/run={run_id}/partitions/"
            f"{index:02d}-{method}.parquet"
        )
        location = _text(
            f"attempt_{index}.logical_location",
            attempt["logical_location"],
        )
        _require(location == expected_location, "attempt_location_drift")
        path = raw_root / Path(location)
        resolved_path = path.resolve()
        _require(
            resolved_path.is_relative_to(resolved_root),
            "partition_path_escapes_raw_root",
        )
        _require(
            path.is_file() and not path.is_symlink(),
            "partition_missing_or_unsafe",
        )
        data = path.read_bytes()
        claimed_size = _integer(
            f"attempt_{index}.partition_bytes",
            attempt["partition_bytes"],
        )
        _require(len(data) == claimed_size, "partition_size_mismatch")
        _require(
            len(data) <= plan.partition_max_bytes,
            "partition_size_cap",
        )
        file_sha = hashlib.sha256(data).hexdigest()
        claimed_file_sha = _sha256(
            f"attempt_{index}.partition_file_sha256",
            attempt["partition_file_sha256"],
        )
        _require(file_sha == claimed_file_sha, "partition_file_hash_mismatch")
        try:
            event_rows = _events_from_table(pq.ParquetFile(path).read())
        except Exception as exc:
            raise EntityReplayContractError("partition_decode_failed") from exc
        _require(len(event_rows) == 1, "partition_row_count_mismatch")
        content_sha = hashlib.sha256(
            canonical_raw_event_rows_bytes(event_rows)
        ).hexdigest()
        claimed_content_sha = _sha256(
            f"attempt_{index}.partition_content_sha256",
            attempt["partition_content_sha256"],
        )
        _require(
            content_sha == claimed_content_sha,
            "partition_content_hash_mismatch",
        )
        event = event_rows[0]
        _require(
            event.raw_event_id == attempt["raw_event_id"],
            "raw_event_id_mismatch",
        )
        _require(
            event.content_sha256 == attempt["redacted_body_sha256"],
            "redacted_body_hash_mismatch",
        )
        _require(event.endpoint_or_method == method, "event_method_mismatch")
        _require(event.source == plan.provider_id, "event_source_mismatch")
        _require(
            str(event.response_status) == attempt["response_status"],
            "event_response_status_mismatch",
        )
        _require(
            event.observed_at
            == _aware_timestamp(
                f"attempt_{index}.response_complete_at",
                attempt["response_complete_at"],
            ),
            "event_observed_at_mismatch",
        )
        _require(
            b"?api-key=" not in data and b"api-key=" not in data,
            "credential_url_material_forbidden",
        )
        partition_bytes_total += len(data)
        response_bytes = _integer(
            f"attempt_{index}.response_bytes",
            attempt["response_bytes"],
        )
        _require(
            0 < response_bytes <= plan.response_bytes_each,
            "response_size_cap",
        )
        response_bytes_total += response_bytes
        events.append(event)
        evidence.append(
            {
                "content_sha256": content_sha,
                "file_sha256": file_sha,
                "logical_location": location,
                "method": method,
                "partition_bytes": len(data),
                "raw_event_id": event.raw_event_id,
                "redacted_body_sha256": event.content_sha256,
                "response_bytes": response_bytes,
                "response_complete_at": event.observed_at.isoformat(),
                "rpc_id": index,
            }
        )
    _require(
        partition_bytes_total
        == sum(_integer("partition_bytes", item["partition_bytes"]) for item in attempts),
        "partition_bytes_total_mismatch",
    )
    _require(
        response_bytes_total
        == sum(_integer("response_bytes", item["response_bytes"]) for item in attempts),
        "response_bytes_total_mismatch",
    )
    return tuple(events), evidence


def replay_entity_probe(
    *,
    raw_root: Path,
    plan: EntityPilotPlan,
    run_id: str,
) -> dict[str, JsonValue]:
    """Replay one immutable run and return portable aggregate evidence only."""

    _require(raw_root.is_absolute(), "raw_root_must_be_absolute")
    receipt, receipt_bytes, receipt_sha = _read_receipt(
        raw_root,
        plan,
        run_id,
    )
    attempts = _verify_receipt_summary(receipt, plan, run_id)
    events, attempt_evidence = _load_attempt_events(
        raw_root,
        plan,
        run_id,
        attempts,
    )
    supply = parse_token_supply(
        events[0].redacted_body,
        expected_id=1,
        expected_decimals=plan.selected_mint_decimals,
    )
    largest = parse_largest_accounts(
        events[1].redacted_body,
        expected_id=2,
        expected_decimals=plan.selected_mint_decimals,
    )
    owners = parse_owner_accounts(
        events[2].redacted_body,
        expected_id=3,
        expected_mint=plan.selected_mint,
        expected_accounts=largest.accounts,
    )
    _require(isinstance(supply, TokenSupplyObservation), "supply_type_drift")
    _require(
        isinstance(largest, LargestAccountsObservation),
        "largest_accounts_type_drift",
    )
    _require(isinstance(owners, OwnersObservation), "owners_type_drift")

    joined_at = events[2].observed_at
    snapshot = HolderSnapshotInput(
        snapshot_id=f"{run_id}-holder-snapshot",
        mint=plan.selected_mint,
        decimals=supply.decimals,
        supply_atomic=supply.amount_atomic,
        supply_context_slot=supply.context_slot,
        largest_accounts_context_slot=largest.context_slot,
        owners_context_slot=owners.context_slot,
        accounts=tuple(
            HolderAccountObservation(
                token_account=owner.token_account,
                owner=owner.owner,
                amount_atomic=owner.amount_atomic,
                context_slot=owners.context_slot,
            )
            for owner in owners.owners
        ),
        event_time=joined_at,
        observed_at=joined_at,
        first_reliable_available_at=joined_at,
        available_to_strategy_at=joined_at,
        ingested_at=max(event.ingested_at for event in events),
        source=plan.provider_id,
        source_version="helius-standard-rpc-observed-2026-07-28",
        revision_number=1,
        revision_of=None,
        raw_event_ids=(
            events[0].raw_event_id,
            events[1].raw_event_id,
            events[2].raw_event_id,
        ),
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
        for account in snapshot.accounts
    )
    metrics = calculate_holder_metrics(
        snapshot,
        assessments,
        exclusion_inventory_complete=False,
        excluded_supply_atomic_total=None,
        exclusion_inventory_evidence_ref=None,
    )
    projection = project_entity_snapshots(snapshot, metrics)

    replay_checks = (
        (
            snapshot.supply_atomic == receipt["supply_atomic"],
            "replay_supply_mismatch",
        ),
        (
            snapshot.supply_context_slot == receipt["supply_context_slot"],
            "replay_supply_slot_mismatch",
        ),
        (
            snapshot.largest_accounts_context_slot
            == receipt["largest_accounts_context_slot"],
            "replay_largest_slot_mismatch",
        ),
        (
            snapshot.owners_context_slot == receipt["owners_context_slot"],
            "replay_owner_slot_mismatch",
        ),
        (
            len(snapshot.accounts) == receipt["top_account_count"],
            "replay_top_account_count_mismatch",
        ),
        (
            len({account.owner for account in snapshot.accounts})
            == receipt["owner_resolution_count"],
            "replay_owner_count_mismatch",
        ),
        (
            metrics.raw_top_accounts_amount_atomic
            == receipt["raw_top_accounts_amount_atomic"],
            "replay_raw_amount_mismatch",
        ),
        (
            str(metrics.raw_top_accounts_supply_share)
            == receipt["raw_top_accounts_supply_share"],
            "replay_raw_share_mismatch",
        ),
        (
            metrics.context_slot_spread == receipt["context_slot_spread"],
            "replay_context_slot_spread_mismatch",
        ),
        (
            metrics.adjusted_top_accounts_supply_share is None,
            "replay_adjusted_concentration_forbidden",
        ),
        (
            receipt["received_bytes"]
            == sum(item["response_bytes"] for item in attempt_evidence),
            "replay_received_bytes_mismatch",
        ),
        (
            receipt["stored_partition_bytes"]
            == sum(item["partition_bytes"] for item in attempt_evidence),
            "replay_stored_partition_bytes_mismatch",
        ),
    )
    for condition, message in replay_checks:
        _require(condition, message)

    result: dict[str, JsonValue] = {
        "accepted_claim": "RAW_TOP20_ACCOUNT_CONCENTRATION_FEASIBILITY",
        "attempts": attempt_evidence,
        "availability_class": str(metrics.availability_class),
        "cash_spend_usd_cents": 0,
        "context_slots": {
            "largest_accounts": snapshot.largest_accounts_context_slot,
            "owners": snapshot.owners_context_slot,
            "spread": metrics.context_slot_spread,
            "supply": snapshot.supply_context_slot,
        },
        "dataset_id": plan.dataset_id,
        "dataset_version": plan.dataset_version,
        "deployer_funder_bundler": "NOT_TESTED",
        "exclusion_inventory_complete": False,
        "logical_root": f"{plan.logical_root}/run={run_id}",
        "modeled_credits": plan.modeled_credits_total,
        "owner_resolution_count": len(
            {account.owner for account in snapshot.accounts}
        ),
        "projection": {
            "content_sha256": [row.content_sha256 for row in projection],
            "entity_snapshot_ids": [
                row.entity_snapshot_id for row in projection
            ],
            "metric_names": [row.metric_name for row in projection],
            "row_count": len(projection),
        },
        "provider_calls": plan.provider_calls,
        "quality_flags": list(metrics.quality_flags),
        "raw_event_ids": list(snapshot.raw_event_ids),
        "raw_top_accounts_amount_atomic": (
            metrics.raw_top_accounts_amount_atomic
        ),
        "raw_top_accounts_supply_share": (
            str(metrics.raw_top_accounts_supply_share)
            if metrics.raw_top_accounts_supply_share is not None
            else None
        ),
        "received_bytes": receipt["received_bytes"],
        "receipt_bytes": len(receipt_bytes),
        "receipt_sha256": receipt_sha,
        "replay_contract_version": REPLAY_CONTRACT_VERSION,
        "retries": 0,
        "run_id": run_id,
        "selected_mint": plan.selected_mint,
        "snapshot_available_at": snapshot.available_to_strategy_at.isoformat(),
        "snapshot_ingested_at": snapshot.ingested_at.isoformat(),
        "stored_partition_bytes": receipt["stored_partition_bytes"],
        "supply_atomic": snapshot.supply_atomic,
        "top_account_count": len(snapshot.accounts),
        "unresolved_exclusion_account_count": (
            metrics.unresolved_exclusion_account_count
        ),
        "unresolved_owner_account_count": (
            metrics.unresolved_owner_account_count
        ),
        "adjusted_top_accounts_supply_share": None,
        "wallet_signer_transaction_actions": 0,
    }
    validate_durable_metadata(result)
    return result
