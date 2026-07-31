"""Deterministic provider-neutral TASK-21 collector dry run.

The module exercises the forward-collection shape with synthetic observations
only.  It has no network transport and materializes only create-once local
evidence when explicitly asked by the caller.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeAlias

import yaml

from solana_alpha_lab.jupiter_quote_logger import (
    PROVIDER,
    PROVIDER_VERSION,
    QuoteProjection,
    QuoteRequest,
    TransportObservation,
    build_buy_panel_requests,
    decide_dependent_sell,
    project_quote_observation,
)
from solana_alpha_lab.pilot_supervisor import SupervisorLimits

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

TASK_ID = "TASK-21"
ATOM_ID = "T21-A4_THIN_COLLECTOR_AND_OFFLINE_DRY_RUN_V1"
SCHEMA_VERSION = "1.0"
WINDOW_OFFSETS_SECONDS = (0, 1801, 3602)
PLAN_PROVIDER_CALL_CAP = 192
MIN_FREE_SPACE_AFTER_WRITE = 2_147_483_648
MATERIALIZED_BYTES_MAX = 4_194_304
OUTPUT_FILENAMES = ("records.jsonl", "manifest.json", "receipt.json")
REQUIRED_RECOVERY_EVIDENCE = frozenset(
    {
        "PRIVATE_SEPARATE_FAILURE_DOMAIN_DESTINATION",
        "CREATE_ONLY_CONTENT_ADDRESSED_BACKUP",
        "EXACT_REMOTE_READBACK",
        "ISOLATED_SAMPLE_RESTORE",
        "BACKUP_AND_RESTORE_HEALTH_ALERTS",
        "NO_SECRET_MATERIAL_IN_EVIDENCE",
    }
)
ALLOWED_EVALUATION_STATES = frozenset(
    {
        "EVALUATED_REJECTED",
        "EVALUATED_NOT_EVALUABLE",
        "WATCHLIST_ACTIVE",
        "WATCHLIST_EXITED",
    }
)
FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "alpha",
        "costbps",
        "hypothesisverdict",
        "pnl",
        "profit",
        "rank",
        "return",
        "roi",
        "score",
        "sharpe",
        "target",
    }
)


class Task21CollectorError(RuntimeError):
    """A frozen offline collector invariant was violated."""


@dataclass(frozen=True, slots=True)
class OfflineRun:
    """Pure deterministic result before any materialization."""

    records_bytes: bytes
    manifest_bytes: bytes
    receipt_bytes: bytes

    @property
    def file_bytes(self) -> dict[str, bytes]:
        return {
            "records.jsonl": self.records_bytes,
            "manifest.json": self.manifest_bytes,
            "receipt.json": self.receipt_bytes,
        }

    @property
    def manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_bytes)

    @property
    def receipt(self) -> dict[str, Any]:
        return json.loads(self.receipt_bytes)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Task21CollectorError("value_must_be_canonical_json") from exc


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21CollectorError("yaml_document_must_be_mapping")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21CollectorError("json_document_must_be_mapping")
    return value


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _reject_outcome_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise Task21CollectorError("population_key_must_be_text")
            normalized = _normalized_key(key)
            if any(
                normalized == forbidden
                or (
                    forbidden != "target"
                    and normalized.startswith(forbidden)
                )
                for forbidden in FORBIDDEN_OUTCOME_KEYS
            ):
                raise Task21CollectorError("outcome_field_forbidden")
            _reject_outcome_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_outcome_fields(item)


def _aware_utc(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise Task21CollectorError(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21CollectorError(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Task21CollectorError(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _enum_text(value: object) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str):
        raise Task21CollectorError("enum_text_invalid")
    return raw


def _validate_hash(name: str, value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise Task21CollectorError(f"{name}_invalid")
    return value


def validate_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if config.get("task_id") != TASK_ID or config.get("atom_id") != ATOM_ID:
        raise Task21CollectorError("config_identity_drift")
    authority = config.get("authority")
    if not isinstance(authority, Mapping):
        raise Task21CollectorError("config_authority_missing")
    zero_fields = (
        "network_calls",
        "provider_api_rpc_wss_calls",
        "drive_reads",
        "drive_writes",
        "credential_use",
        "real_candidate_admissions",
        "live_collector_executions",
        "forward_raw_or_dataset_writes",
        "cash_spend_usd_cents",
        "provider_credits",
        "dependency_changes",
    )
    if any(authority.get(field) != 0 for field in zero_fields):
        raise Task21CollectorError("config_external_authority_nonzero")
    frozen = config.get("frozen_inputs")
    if not isinstance(frozen, list) or not frozen:
        raise Task21CollectorError("frozen_inputs_missing")
    for item in frozen:
        if not isinstance(item, Mapping):
            raise Task21CollectorError("frozen_input_invalid")
        relative = item.get("path")
        if not isinstance(relative, str):
            raise Task21CollectorError("frozen_input_path_invalid")
        expected = _validate_hash("frozen_input_sha256", item.get("sha256"))
        actual = sha256_file(repo_root / relative)
        if actual != expected:
            raise Task21CollectorError(
                f"frozen_input_hash_drift:{relative}:{expected}:{actual}"
            )
    population = config.get("population")
    if not isinstance(population, Mapping):
        raise Task21CollectorError("population_config_missing")
    fixture_path = population.get("fixture_path")
    if not isinstance(fixture_path, str):
        raise Task21CollectorError("population_fixture_path_invalid")
    path = repo_root / fixture_path
    if path.stat().st_size != population.get("bytes"):
        raise Task21CollectorError("population_fixture_size_drift")
    if sha256_file(path) != population.get("sha256"):
        raise Task21CollectorError("population_fixture_hash_drift")


def validate_population(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    if (
        document.get("task_id") != TASK_ID
        or document.get("atom_id") != ATOM_ID
        or document.get("synthetic_only") is not True
        or document.get("contains_market_data") is not False
    ):
        raise Task21CollectorError("population_identity_or_scope_invalid")
    _reject_outcome_fields(document)
    candidates = document.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 8:
        raise Task21CollectorError("population_must_have_exactly_eight_candidates")
    active: list[dict[str, Any]] = []
    nomination_ids: set[str] = set()
    member_ids: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise Task21CollectorError("candidate_must_be_mapping")
        if set(candidate) != {"nomination", "evaluation_state", "member"}:
            raise Task21CollectorError("candidate_fields_drift")
        nomination = candidate["nomination"]
        if not isinstance(nomination, dict):
            raise Task21CollectorError("nomination_must_be_mapping")
        required_nomination = {
            "nomination_event_id",
            "source_asset_id",
            "source_version",
            "source_content_sha256",
            "observed_at",
            "first_reliable_available_at",
            "hypothesis_version_id",
            "watchlist_policy_version",
            "exact_rule_input_values",
            "reason_codes",
            "evidence_checkpoint",
        }
        if set(nomination) != required_nomination:
            raise Task21CollectorError("nomination_fields_drift")
        nomination_id = nomination["nomination_event_id"]
        if not isinstance(nomination_id, str) or not nomination_id:
            raise Task21CollectorError("nomination_id_invalid")
        if nomination_id in nomination_ids:
            raise Task21CollectorError("duplicate_nomination_id")
        nomination_ids.add(nomination_id)
        _validate_hash("source_content_sha256", nomination["source_content_sha256"])
        observed = _aware_utc("nomination_observed_at", nomination["observed_at"])
        reliable = _aware_utc(
            "nomination_first_reliable_available_at",
            nomination["first_reliable_available_at"],
        )
        if reliable < observed:
            raise Task21CollectorError("nomination_availability_before_observation")
        state = candidate["evaluation_state"]
        if state not in ALLOWED_EVALUATION_STATES:
            raise Task21CollectorError("evaluation_state_invalid")
        member = candidate["member"]
        if state == "WATCHLIST_ACTIVE":
            if not isinstance(member, dict):
                raise Task21CollectorError("active_candidate_member_missing")
            required_member = {
                "member_id",
                "mint",
                "mint_decimals",
                "nomination_event_id",
                "hypothesis_version_id",
                "policy_version",
                "entered_at",
                "exited_at",
                "first_reliable_available_at",
                "reason_codes",
                "evidence_checkpoint",
            }
            if set(member) != required_member:
                raise Task21CollectorError("member_fields_drift")
            member_id = member["member_id"]
            if not isinstance(member_id, str) or not member_id:
                raise Task21CollectorError("member_id_invalid")
            if member_id in member_ids:
                raise Task21CollectorError("duplicate_member_id")
            member_ids.add(member_id)
            if member["nomination_event_id"] != nomination_id:
                raise Task21CollectorError("member_nomination_mismatch")
            if member["exited_at"] is not None:
                raise Task21CollectorError("active_member_must_not_be_exited")
            if (
                not isinstance(member["mint"], str)
                or not member["mint"]
                or isinstance(member["mint_decimals"], bool)
                or not isinstance(member["mint_decimals"], int)
                or not 0 <= member["mint_decimals"] <= 30
            ):
                raise Task21CollectorError("member_mint_invalid")
            _aware_utc("member_entered_at", member["entered_at"])
            _aware_utc(
                "member_first_reliable_available_at",
                member["first_reliable_available_at"],
            )
            active.append(member)
        elif member is not None:
            raise Task21CollectorError("inactive_candidate_member_must_be_null")
    if len(active) != 5:
        raise Task21CollectorError("population_must_have_five_active_members")
    return active


def validate_recovery_receipt(receipt: Mapping[str, Any]) -> None:
    if (
        receipt.get("task_id") != TASK_ID
        or receipt.get("verdict") != "PASS"
        or receipt.get("gate_id") != "TASK21_PRE_COLLECTION_RUNTIME_RECOVERY_GATE"
    ):
        raise Task21CollectorError("recovery_gate_not_passed")
    satisfied = receipt.get("satisfied_evidence")
    if not isinstance(satisfied, list) or set(satisfied) != REQUIRED_RECOVERY_EVIDENCE:
        raise Task21CollectorError("recovery_gate_evidence_incomplete")
    health = receipt.get("health")
    if not isinstance(health, Mapping) or health.get("health_state") != "HEALTHY":
        raise Task21CollectorError("recovery_gate_unhealthy")
    if receipt.get("provider_api_rpc_wss_calls") != 0:
        raise Task21CollectorError("recovery_receipt_provider_calls_nonzero")
    probe = receipt.get("probe")
    if not isinstance(probe, Mapping) or probe.get("contains_secrets") is not False:
        raise Task21CollectorError("recovery_receipt_secret_safety_unproven")


def _synthetic_observation(
    request: QuoteRequest,
    *,
    requested_at: datetime,
    sequence: int,
    late: bool,
) -> TransportObservation:
    output_atomic = max(1, request.input_requested_atomic // 2 + sequence)
    lag = timedelta(seconds=900 if late else 0)
    response_at = requested_at + timedelta(milliseconds=10)
    reliable_at = response_at + timedelta(milliseconds=1) + lag
    available_at = reliable_at + timedelta(milliseconds=1)
    ingested_at = available_at + timedelta(milliseconds=1)
    body: dict[str, JsonValue] = {
        "inputMint": request.input_mint,
        "inAmount": str(request.input_requested_atomic),
        "outputMint": request.output_mint,
        "outAmount": str(output_atomic),
        "otherAmountThreshold": str(max(0, output_atomic - 1)),
        "swapMode": "ExactIn",
        "slippageBps": request.slippage_bps,
        "platformFee": None,
        "priceImpactPct": "0.001",
        "routePlan": [
            {
                "swapInfo": {
                    "ammKey": f"task21-synthetic-amm-{sequence:03d}",
                    "label": "TASK21_SYNTHETIC_OFFLINE",
                    "inputMint": request.input_mint,
                    "outputMint": request.output_mint,
                    "inAmount": str(request.input_requested_atomic),
                    "outAmount": str(output_atomic),
                    "feeAmount": "0",
                    "feeMint": request.input_mint,
                },
                "percent": 100,
                "bps": 10000,
            }
        ],
        "contextSlot": 300_000_000 + sequence,
        "timeTaken": 0.01,
    }
    return TransportObservation(
        requested_at=requested_at,
        response_at=response_at,
        first_reliable_available_at=reliable_at,
        available_to_strategy_at=available_at,
        ingested_at=ingested_at,
        http_status_code=200,
        response_body=body,
        timed_out=False,
        stale=False,
    )


def _projection_record(
    projection: QuoteProjection,
    *,
    member_id: str,
    window_id: str,
    call_ordinal: int,
    late_evidence: bool,
) -> dict[str, JsonValue]:
    return {
        "call_ordinal": call_ordinal,
        "late_evidence": late_evidence,
        "member_id": member_id,
        "provider_contract": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "quote_attempt": projection.quote_attempt.model_dump(mode="json"),
        "raw_event": projection.raw_event.model_dump(mode="json"),
        "stop_reason": projection.stop_reason,
        "window_id": window_id,
    }


def _validate_limits(*, available_disk_bytes: int) -> None:
    limits = SupervisorLimits(
        predicted_child_write_bytes_max=MATERIALIZED_BYTES_MAX,
        start_reserve_fixed_bytes=536_870_912,
        runtime_reserve_fixed_bytes=268_435_456,
    )
    limits.validate()
    if (
        isinstance(available_disk_bytes, bool)
        or not isinstance(available_disk_bytes, int)
        or available_disk_bytes
        < MIN_FREE_SPACE_AFTER_WRITE + limits.start_required_bytes
    ):
        raise Task21CollectorError("disk_pressure_blocks_before_execution")


def _run_identity(
    *,
    config_sha256: str,
    plan_sha256: str,
    recovery_sha256: str,
    population_sha256: str,
) -> str:
    claim = {
        "atom_id": ATOM_ID,
        "config_sha256": config_sha256,
        "plan_sha256": plan_sha256,
        "population_sha256": population_sha256,
        "recovery_sha256": recovery_sha256,
        "task_id": TASK_ID,
    }
    return f"t21-offline-{sha256_bytes(canonical_json_bytes(claim))}"


def build_offline_run(
    *,
    repo_root: Path,
    config_path: Path,
    population_path: Path,
    recovery_receipt_path: Path,
    available_disk_bytes: int = 10 * 1024 * 1024 * 1024,
    call_cap: int = PLAN_PROVIDER_CALL_CAP,
    missing_windows: frozenset[str] = frozenset(),
    late_slots: frozenset[int] = frozenset(),
    population_override: Mapping[str, Any] | None = None,
    recovery_override: Mapping[str, Any] | None = None,
) -> OfflineRun:
    """Build one pure deterministic synthetic run without file or network I/O."""

    config = load_yaml(config_path)
    validate_config(config, repo_root)
    population = (
        deepcopy(population_override)
        if population_override is not None
        else load_json(population_path)
    )
    recovery = (
        deepcopy(recovery_override)
        if recovery_override is not None
        else load_json(recovery_receipt_path)
    )
    active_members = validate_population(population)
    validate_recovery_receipt(recovery)
    _validate_limits(available_disk_bytes=available_disk_bytes)
    if (
        isinstance(call_cap, bool)
        or not isinstance(call_cap, int)
        or call_cap < 0
        or call_cap > PLAN_PROVIDER_CALL_CAP
    ):
        raise Task21CollectorError("call_cap_invalid")

    valid_window_ids = frozenset(
        f"{member['member_id']}-W{window_ordinal}"
        for member in active_members
        for window_ordinal in range(1, len(WINDOW_OFFSETS_SECONDS) + 1)
    )
    if not missing_windows.issubset(valid_window_ids):
        raise Task21CollectorError("missing_window_identity_invalid")
    if any(
        isinstance(slot, bool)
        or not isinstance(slot, int)
        or not 1 <= slot <= 120
        for slot in late_slots
    ):
        raise Task21CollectorError("late_slot_invalid")
    expected_calls = (
        len(active_members) * len(WINDOW_OFFSETS_SECONDS) * 4 * 2
        - len(missing_windows) * 4 * 2
    )
    if expected_calls > call_cap:
        raise Task21CollectorError("call_cap_exhaustion_blocks_before_materialization")

    config_sha256 = sha256_file(config_path)
    plan_sha256 = sha256_file(repo_root / "configs/task21_forward_collection_run_plan_v1.yaml")
    recovery_sha256 = sha256_file(recovery_receipt_path)
    population_sha256 = sha256_file(population_path)
    run_id = _run_identity(
        config_sha256=config_sha256,
        plan_sha256=plan_sha256,
        recovery_sha256=recovery_sha256,
        population_sha256=population_sha256,
    )

    records: list[dict[str, JsonValue]] = []
    missing: list[dict[str, JsonValue]] = []
    terminal_counts: Counter[str] = Counter()
    complete_panels = 0
    quote_pairs = 0
    call_ordinal = 0
    late_evidence_count = 0
    for member in active_members:
        entered_at = _aware_utc("member_entered_at", member["entered_at"])
        member_id = member["member_id"]
        for window_ordinal, offset in enumerate(WINDOW_OFFSETS_SECONDS, start=1):
            window_id = f"{member_id}-W{window_ordinal}"
            triggered_at = entered_at + timedelta(seconds=offset)
            if window_id in missing_windows:
                missing.append(
                    {
                        "disposition": "RETAIN_EXPLICIT_COVERAGE_LOSS_NO_SILENT_RESCHEDULE",
                        "member_id": member_id,
                        "scheduled_at": _utc_text(triggered_at),
                        "window_id": window_id,
                    }
                )
                continue
            complete_panels += 1
            requests = build_buy_panel_requests(
                selected_output_mint=member["mint"],
                output_decimals=member["mint_decimals"],
            )
            for pair_ordinal, buy_request in enumerate(requests, start=1):
                call_ordinal += 1
                is_late = call_ordinal in late_slots
                buy_projection = project_quote_observation(
                    buy_request,
                    _synthetic_observation(
                        buy_request,
                        requested_at=triggered_at
                        + timedelta(milliseconds=call_ordinal * 20),
                        sequence=call_ordinal,
                        late=is_late,
                    ),
                )
                terminal_counts[
                    _enum_text(buy_projection.quote_attempt.status)
                ] += 1
                sell = decide_dependent_sell(
                    buy_projection,
                    attempt_ordinal=5 + pair_ordinal,
                )
                if sell.request is None:
                    raise Task21CollectorError("synthetic_buy_prerequisite_failed")
                call_ordinal += 1
                sell_late = call_ordinal in late_slots
                sell_projection = project_quote_observation(
                    sell.request,
                    _synthetic_observation(
                        sell.request,
                        requested_at=triggered_at
                        + timedelta(milliseconds=call_ordinal * 20),
                        sequence=call_ordinal,
                        late=sell_late,
                    ),
                )
                terminal_counts[
                    _enum_text(sell_projection.quote_attempt.status)
                ] += 1
                if (
                    sell.request.input_requested_atomic
                    != buy_projection.quote_attempt.output_quoted_atomic
                ):
                    raise Task21CollectorError("dependent_sell_input_drift")
                late_evidence_count += int(is_late) + int(sell_late)
                quote_pairs += 1
                records.append(
                    {
                        "buy": _projection_record(
                            buy_projection,
                            member_id=member_id,
                            window_id=window_id,
                            call_ordinal=call_ordinal - 1,
                            late_evidence=is_late,
                        ),
                        "pair_ordinal": pair_ordinal,
                        "sell": _projection_record(
                            sell_projection,
                            member_id=member_id,
                            window_id=window_id,
                            call_ordinal=call_ordinal,
                            late_evidence=sell_late,
                        ),
                        "synthetic_only": True,
                    }
                )

    records_bytes = b"".join(canonical_json_bytes(row) + b"\n" for row in records)
    if len(records_bytes) > MATERIALIZED_BYTES_MAX:
        raise Task21CollectorError("synthetic_materialized_byte_cap_exhausted")
    manifest = {
        "schema": "smial.task21.thin-forward-collector-offline-manifest",
        "schema_version": SCHEMA_VERSION,
        "atom_id": ATOM_ID,
        "config_sha256": config_sha256,
        "files": [
            {
                "bytes": len(records_bytes),
                "logical_path": "records.jsonl",
                "sha256": sha256_bytes(records_bytes),
            }
        ],
        "plan_sha256": plan_sha256,
        "population_sha256": population_sha256,
        "recovery_receipt_sha256": recovery_sha256,
        "run_id": run_id,
        "synthetic_only": True,
        "task_id": TASK_ID,
    }
    manifest_bytes = canonical_json_bytes(manifest) + b"\n"
    receipt = {
        "schema": "smial.task21.thin-forward-collector-offline-receipt",
        "schema_version": SCHEMA_VERSION,
        "atom_id": ATOM_ID,
        "evaluated_candidates": len(population["candidates"]),
        "active_members": len(active_members),
        "complete_panels": complete_panels,
        "complete_quote_pairs": quote_pairs,
        "offline_adapter_calls": call_ordinal,
        "provider_api_rpc_wss_calls": 0,
        "provider_credits": 0,
        "cash_spend_usd_cents": 0,
        "wallet_signer_transaction_actions": 0,
        "drive_reads": 0,
        "drive_writes": 0,
        "forward_raw_or_dataset_writes": 0,
        "real_candidate_admissions": 0,
        "late_evidence_count": late_evidence_count,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "missing_windows": missing,
        "network_calls": 0,
        "provider_selected": None,
        "records_sha256": sha256_bytes(records_bytes),
        "retries": 0,
        "run_id": run_id,
        "status": "PASS",
        "synthetic_only": True,
        "task_id": TASK_ID,
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "theoretical_task_provider_call_cap": PLAN_PROVIDER_CALL_CAP,
    }
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    return OfflineRun(
        records_bytes=records_bytes,
        manifest_bytes=manifest_bytes,
        receipt_bytes=receipt_bytes,
    )


def materialize_create_once(run: OfflineRun, output_root: Path) -> str:
    """Create exact artifacts once or read back an exact complete duplicate."""

    expected = run.file_bytes
    if output_root.exists():
        actual_files = {
            path.name: path
            for path in output_root.iterdir()
            if path.is_file()
        }
        if set(actual_files) != set(OUTPUT_FILENAMES):
            raise Task21CollectorError("incomplete_or_extra_restart_artifacts")
        for name, payload in expected.items():
            if actual_files[name].read_bytes() != payload:
                raise Task21CollectorError("conflicting_restart_artifact")
        return "EXACT_DUPLICATE_RESTART_DEDUPLICATED"
    output_root.mkdir(parents=True, exist_ok=False)
    for name in OUTPUT_FILENAMES:
        path = output_root / name
        with path.open("xb") as handle:
            handle.write(expected[name])
    for name, payload in expected.items():
        if sha256_file(output_root / name) != sha256_bytes(payload):
            raise Task21CollectorError("materialized_readback_hash_mismatch")
    return "CREATED_AND_READBACK_VERIFIED"
