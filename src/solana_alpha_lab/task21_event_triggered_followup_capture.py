"""Outcome-blind foreground follow-up panels for TASK-21 final cohorts."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.jupiter_quote_logger import (
    DEFAULT_SLIPPAGE_BPS,
    PROVIDER,
    PROVIDER_VERSION,
    QuoteProjection,
    build_buy_panel_requests,
    decide_dependent_sell,
    project_quote_observation,
)
from solana_alpha_lab.jupiter_quote_transport import (
    EXTERNAL_AUTHORITY_PHRASE as JUPITER_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate as JupiterExecutionGate,
    HttpCapture,
)
from solana_alpha_lab.task21_event_triggered_final_cohort import (
    Task21FinalCohortError,
    evaluate_panel_trigger,
)
from solana_alpha_lab.task21_live_shakedown import (
    Task21LiveShakedownError,
    validate_recovery_freshness,
)
from solana_alpha_lab.task21_multi_horizon_capture import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)


TASK_ID = "TASK-21"
ATOM_ID = "T21-A6S_R2_P1_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1"
SCHEMA_VERSION = "1.0"
MEMBERS_EXACT = 3
CALLS_PER_PANEL_MAX = 8
CALLS_TOTAL_MAX = 24
DURABLE_BYTES_MAX = 16_777_216
RECEIVED_BYTES_MAX = 9_437_184
MIN_FREE_SPACE_AFTER_WRITE = 2_147_483_648
WALL_SECONDS_MAX = 300
MINIMUM_INTERVAL_SECONDS = 2.2


class Task21FollowupError(RuntimeError):
    """A follow-up panel cannot proceed inside the frozen boundary."""


class Task21FollowupAuthorityRequired(Task21FollowupError):
    """The exact follow-up external authority phrase is absent."""


@dataclass(frozen=True, slots=True)
class Task21FollowupExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != ATOM_ID:
            raise Task21FollowupAuthorityRequired(
                "task21_followup_authority_phrase_mismatch"
            )


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21FollowupError("followup_config_root_invalid")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21FollowupError("followup_json_root_invalid")
    return value


def _utc(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise Task21FollowupError(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21FollowupError(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Task21FollowupError(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise Task21FollowupError("datetime_must_be_timezone_aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _repo_path(repo_root: Path, relative: object, *, name: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise Task21FollowupError(f"{name}_path_invalid")
    raw = Path(relative)
    if raw.is_absolute():
        raise Task21FollowupError(f"{name}_path_must_be_relative")
    root = repo_root.resolve()
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise Task21FollowupError(f"{name}_path_outside_repository") from exc
    return candidate


def _verify_hash(path: Path, expected: object, *, name: str) -> None:
    if (
        not isinstance(expected, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected) is None
    ):
        raise Task21FollowupError(f"{name}_sha256_invalid")
    if not path.is_file():
        raise Task21FollowupError(f"{name}_missing")
    if sha256_file(path) != expected:
        raise Task21FollowupError(f"{name}_hash_drift")


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise Task21FollowupError("followup_create_only_collision") from exc


def _directory_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _protected_path(
    config: Mapping[str, Any], repo_root: Path, role: str
) -> Path:
    matches = [
        item
        for item in config.get("protected_inputs", [])
        if isinstance(item, Mapping) and item.get("role") == role
    ]
    if len(matches) != 1:
        raise Task21FollowupError(f"followup_protected_role_drift:{role}")
    item = matches[0]
    path = _repo_path(repo_root, item.get("path"), name=role.lower())
    _verify_hash(path, item.get("sha256"), name=role.lower())
    return path


def validate_followup_config(
    config: Mapping[str, Any], repo_root: Path
) -> None:
    """Validate the generic contract and the exact current P1 binding."""

    if (
        config.get("schema")
        != "smial.task21_event_triggered_followup_capture"
        or config.get("schema_version") != SCHEMA_VERSION
        or config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
        or config.get("status")
        != "FROZEN_FOR_SEPARATE_EXACT_PROVIDER_AUTHORITY"
    ):
        raise Task21FollowupError("followup_config_identity_drift")
    protected = config.get("protected_inputs")
    if not isinstance(protected, list) or len(protected) != 3:
        raise Task21FollowupError("followup_protected_inputs_drift")
    roles = [item.get("role") for item in protected if isinstance(item, Mapping)]
    if roles != [
        "EVENT_TRIGGERED_RUNTIME_PLAN",
        "R2_P0_RUNTIME_ACCEPTANCE",
        "R2_ADMISSION_EVENTS",
    ]:
        raise Task21FollowupError("followup_protected_role_order_drift")
    for role in roles:
        _protected_path(config, repo_root, str(role))

    panel = config.get("panel", {})
    expected_panel = {
        "batch_id": "T21-R2",
        "panel_id": "P1",
        "predecessor_panel_id": "P0",
        "next_panel_id": "P2",
        "next_atom_id": "T21-A6S_R2_P2_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1",
        "population_members_exact": MEMBERS_EXACT,
        "minimum_separation_seconds": 1801,
        "member_total_span_seconds_max": 86400,
        "narrow_expiry_window": None,
        "late_policy": "ALLOW_UNTIL_MEMBER_TOTAL_SPAN_DEADLINE",
        "admission_outcome_reselection_allowed": False,
    }
    if any(panel.get(key) != value for key, value in expected_panel.items()):
        raise Task21FollowupError("followup_panel_contract_drift")

    population = config.get("population", {})
    member_ids = population.get("member_ids")
    if (
        not isinstance(member_ids, list)
        or len(member_ids) != MEMBERS_EXACT
        or len(set(member_ids)) != MEMBERS_EXACT
        or population.get("deterministic_order")
        != ["entered_at", "nomination_event_id", "mint"]
        or population.get("outcome_or_route_input_used") is not False
    ):
        raise Task21FollowupError("followup_population_contract_drift")
    predecessor = config.get("predecessor_receipts")
    if not isinstance(predecessor, list) or len(predecessor) != MEMBERS_EXACT:
        raise Task21FollowupError("followup_predecessor_receipts_drift")
    if [item.get("member_id") for item in predecessor] != member_ids:
        raise Task21FollowupError("followup_predecessor_order_drift")
    for item in predecessor:
        path = _repo_path(
            repo_root,
            item.get("path") if isinstance(item, Mapping) else None,
            name="predecessor_receipt",
        )
        _verify_hash(
            path,
            item.get("sha256") if isinstance(item, Mapping) else None,
            name="predecessor_receipt",
        )

    capture = config.get("capture", {})
    expected_capture = {
        "provider": "JUPITER",
        "endpoint": "https://api.jup.ag/swap/v1/quote",
        "authentication": "NONE",
        "notionals_usd": [10, 25, 50, 100],
        "quote_pairs_per_panel": 4,
        "provider_calls_per_panel_max": CALLS_PER_PANEL_MAX,
        "provider_calls_total_max": CALLS_TOTAL_MAX,
        "modeled_provider_credits_max": CALLS_TOTAL_MAX,
        "received_response_bytes_max": RECEIVED_BYTES_MAX,
        "durable_local_bytes_max": DURABLE_BYTES_MAX,
        "wall_seconds_max": WALL_SECONDS_MAX,
        "minimum_interval_seconds": MINIMUM_INTERVAL_SECONDS,
        "retries": 0,
        "concurrency": 1,
    }
    if any(capture.get(key) != value for key, value in expected_capture.items()):
        raise Task21FollowupError("followup_capture_contract_drift")

    budget = config.get("budget", {})
    caps = budget.get("whole_task_caps", {})
    used = budget.get("used_before_p1", {})
    if (
        caps.get("external_requests") != 192
        or caps.get("source_requests") != 8
        or caps.get("quote_requests") != 184
        or caps.get("response_bytes") != 25_165_824
        or caps.get("stored_bytes") != 125_829_120
        or caps.get("dataset_bytes") != 268_435_456
        or used
        != {
            "external_requests": 86,
            "source_requests": 6,
            "quote_requests": 80,
            "response_bytes": 154_740,
        }
        or used["external_requests"] + CALLS_TOTAL_MAX
        > caps["external_requests"]
        or used["quote_requests"] + CALLS_TOTAL_MAX > caps["quote_requests"]
        or used["response_bytes"] + RECEIVED_BYTES_MAX
        > caps["response_bytes"]
        or budget.get("minimum_free_space_bytes_after_write")
        != MIN_FREE_SPACE_AFTER_WRITE
        or budget.get("cap_behavior") != "FAIL_CLOSED_NO_RETRY"
    ):
        raise Task21FollowupError("followup_budget_contract_drift")

    recovery = config.get("recovery", {})
    if (
        recovery.get("required_health") != "HEALTHY"
        or recovery.get("backup_age_hours_max_at_start") != 24
        or recovery.get("restore_age_hours_max_at_start") != 168
        or recovery.get("drive_actions") != 0
    ):
        raise Task21FollowupError("followup_recovery_contract_drift")
    recovery_path = _repo_path(
        repo_root, recovery.get("receipt_path"), name="recovery_receipt"
    )
    _verify_hash(
        recovery_path, recovery.get("receipt_sha256"), name="recovery_receipt"
    )

    runtime = config.get("runtime", {})
    if (
        runtime.get("output_root")
        != "local/task21_forward/final_cohort/r2/p1"
        or runtime.get("write_behavior") != "CREATE_ONLY_CONTENT_ADDRESSED"
        or runtime.get("all_members_eligible_before_first_provider_call")
        is not True
        or runtime.get("partial_failure_policy")
        != "RETAIN_EVIDENCE_AND_STOP_NO_RETRY"
        or runtime.get("scheduler_or_background_process") is not False
    ):
        raise Task21FollowupError("followup_runtime_contract_drift")

    authority = config.get("authority", {})
    expected_authority = {
        "source": "AUTHORIZATION_REQUIRED",
        "exact_phrase": ATOM_ID,
        "provider_api_rpc_wss_calls_max": CALLS_TOTAL_MAX,
        "jupiter_calls_max": CALLS_TOTAL_MAX,
        "nominations": 0,
        "admissions": 0,
        "retries": 0,
        "concurrency": 1,
        "drive_reads": 0,
        "drive_writes": 0,
        "credentials": 0,
        "cash_spend_usd_cents": 0,
        "scheduler_or_background_process": False,
        "deploy": False,
        "catalog_mutation": False,
        "source_mutation": False,
        "wallet_signer_transaction_actions": 0,
        "destructive_actions": False,
        "merge": False,
    }
    if any(authority.get(key) != value for key, value in expected_authority.items()):
        raise Task21FollowupError("followup_authority_boundary_drift")


def _load_members(
    config: Mapping[str, Any], repo_root: Path
) -> list[dict[str, Any]]:
    path = _protected_path(config, repo_root, "R2_ADMISSION_EVENTS")
    members: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Task21FollowupError("followup_admission_event_invalid")
        members.append(value)
    expected = config["population"]["member_ids"]
    if [item.get("member_id") for item in members] != expected:
        raise Task21FollowupError("followup_population_order_drift")
    for member in members:
        if (
            member.get("batch_id") != "T21-R2"
            or not isinstance(member.get("mint"), str)
            or not isinstance(member.get("mint_decimals"), int)
            or not isinstance(member.get("entered_at"), str)
            or not isinstance(member.get("nomination_event_id"), str)
            or not isinstance(member.get("hypothesis_version_id"), str)
        ):
            raise Task21FollowupError("followup_member_contract_drift")
    return members


def _load_predecessors(
    config: Mapping[str, Any], repo_root: Path
) -> list[dict[str, Any]]:
    panel = config["panel"]
    results: list[dict[str, Any]] = []
    for item in config["predecessor_receipts"]:
        path = _repo_path(repo_root, item["path"], name="predecessor_receipt")
        receipt = _load_json(path)
        if (
            receipt.get("task_id") != TASK_ID
            or receipt.get("batch_id") != panel["batch_id"]
            or receipt.get("horizon_id") != panel["predecessor_panel_id"]
            or receipt.get("member_id") != item["member_id"]
            or receipt.get("status") != "COMPLETE"
            or receipt.get("stop_reason") is not None
            or not isinstance(receipt.get("completed_at"), str)
        ):
            raise Task21FollowupError("followup_predecessor_receipt_drift")
        results.append(receipt)
    return results


def _projection_envelope(
    projection: QuoteProjection,
    *,
    atom_id: str,
    panel_id: str,
    member: Mapping[str, Any],
    window_id: str,
    ordinal: int,
) -> dict[str, Any]:
    quote = projection.quote_attempt
    raw = projection.raw_event
    enum = lambda value: getattr(value, "value", str(value))
    return {
        "schema": "smial.task21.forward-quote-panel-raw",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": atom_id,
        "hypothesis_version_id": member["hypothesis_version_id"],
        "batch_id": "T21-R2",
        "member_id": member["member_id"],
        "nomination_event_id": member["nomination_event_id"],
        "horizon_id": panel_id,
        "window_id": window_id,
        "call_ordinal": ordinal,
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "request_hash": quote.request_hash,
        "idempotency_key": quote.idempotency_key,
        "raw_content_sha256": raw.content_sha256,
        "requested_at": _utc_text(quote.requested_at),
        "response_at": (
            None if quote.response_at is None else _utc_text(quote.response_at)
        ),
        "first_reliable_available_at": _utc_text(
            quote.first_reliable_available_at
        ),
        "available_to_strategy_at": _utc_text(quote.available_to_strategy_at),
        "ingested_at": _utc_text(quote.ingested_at),
        "latency_ms": quote.provider_latency_ms,
        "response_status": enum(raw.response_status),
        "terminal_class": enum(quote.status),
        "error_class": quote.error_class,
        "route_id": quote.route_id,
        "route_count": quote.route_count,
        "context_slot": quote.context_slot,
        "stop_reason": projection.stop_reason,
        "raw_event": raw.model_dump(mode="json"),
        "quote_attempt": quote.model_dump(mode="json"),
    }


def _capture_member(
    *,
    run_root: Path,
    config_hash: str,
    atom_id: str,
    panel_id: str,
    member: Mapping[str, Any],
    transport: Any,
    now: Callable[[], datetime],
    clock: Callable[[], float],
) -> dict[str, Any]:
    started = clock()
    triggered_at = _utc_text(now())
    projections: list[QuoteProjection] = []
    terminal_counts: Counter[str] = Counter()
    buy_attempts = 0
    sell_attempts = 0
    sell_not_attempted = 0
    stop_reason: str | None = None
    for index, buy_request in enumerate(
        build_buy_panel_requests(
            selected_output_mint=member["mint"],
            output_decimals=member["mint_decimals"],
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
        )
    ):
        if clock() - started >= WALL_SECONDS_MAX:
            stop_reason = "WALL_TIME_CAP_EXHAUSTED"
            break
        buy_capture: HttpCapture = transport.execute(buy_request)
        buy_attempts += 1
        buy_projection = project_quote_observation(
            buy_request, buy_capture.observation
        )
        projections.append(buy_projection)
        terminal = getattr(
            buy_projection.quote_attempt.status,
            "value",
            str(buy_projection.quote_attempt.status),
        )
        terminal_counts[terminal] += 1
        stop_reason = buy_capture.transport_stop_reason or buy_projection.stop_reason
        if stop_reason is not None:
            break
        sell = decide_dependent_sell(buy_projection, attempt_ordinal=5 + index)
        if sell.request is None:
            sell_not_attempted += 1
            continue
        sell_capture: HttpCapture = transport.execute(sell.request)
        sell_attempts += 1
        sell_projection = project_quote_observation(
            sell.request, sell_capture.observation
        )
        projections.append(sell_projection)
        terminal = getattr(
            sell_projection.quote_attempt.status,
            "value",
            str(sell_projection.quote_attempt.status),
        )
        terminal_counts[terminal] += 1
        stop_reason = (
            sell_capture.transport_stop_reason or sell_projection.stop_reason
        )
        if stop_reason is not None:
            break
    if transport.attempts > CALLS_PER_PANEL_MAX:
        raise Task21FollowupError("followup_panel_call_cap_exceeded")
    if not projections:
        raise Task21FollowupError("followup_panel_has_no_evidence")

    member_id = member["member_id"]
    window_id = f"{member_id}-{panel_id}"
    window_root = run_root / f"member={member_id}" / f"horizon={panel_id}"
    envelopes = [
        _projection_envelope(
            projection,
            atom_id=atom_id,
            panel_id=panel_id,
            member=member,
            window_id=window_id,
            ordinal=ordinal,
        )
        for ordinal, projection in enumerate(projections, start=1)
    ]
    raw_bytes = b"".join(
        canonical_json_bytes(item) + b"\n" for item in envelopes
    )
    manifest = {
        "schema": "smial.task21.forward-quote-panel-manifest",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": atom_id,
        "batch_id": "T21-R2",
        "horizon_id": panel_id,
        "config_sha256": config_hash,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "triggered_at": triggered_at,
        "files": [
            {
                "logical_path": "raw_events.jsonl",
                "bytes": len(raw_bytes),
                "sha256": sha256_bytes(raw_bytes),
            }
        ],
    }
    manifest_bytes = canonical_json_bytes(manifest) + b"\n"
    completed_at = _utc_text(now())
    receipt = {
        "schema": "smial.task21.forward-quote-panel-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": atom_id,
        "batch_id": "T21-R2",
        "horizon_id": panel_id,
        "window_id": window_id,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "status": "COMPLETE" if stop_reason is None else "STOPPED",
        "stop_reason": stop_reason,
        "triggered_at": triggered_at,
        "completed_at": completed_at,
        "provider_calls": transport.attempts,
        "modeled_provider_credits": transport.attempts,
        "provider_billed_credit_claim": "NOT_AVAILABLE_KEYLESS_NO_ACCOUNT",
        "received_bytes": transport.received_bytes,
        "buy_attempts": buy_attempts,
        "sell_attempts": sell_attempts,
        "sell_not_attempted": sell_not_attempted,
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "raw_events_sha256": sha256_bytes(raw_bytes),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "cash_spend_usd_cents": 0,
        "credentials_used": 0,
        "wallet_signer_transaction_actions": 0,
    }
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    if (
        _directory_bytes(run_root)
        + len(raw_bytes)
        + len(manifest_bytes)
        + len(receipt_bytes)
        > DURABLE_BYTES_MAX
    ):
        raise Task21FollowupError("followup_durable_cap_would_be_exceeded")
    _write_new(window_root / "raw_events.jsonl", raw_bytes)
    _write_new(window_root / "manifest.json", manifest_bytes)
    receipt_path = window_root / "receipt.json"
    _write_new(receipt_path, receipt_bytes)
    return {
        **receipt,
        "stored_bytes": _directory_bytes(window_root),
        "receipt_sha256": sha256_file(receipt_path),
    }


def _preflight_triggers(
    *,
    config: Mapping[str, Any],
    event_config: Mapping[str, Any],
    members: list[dict[str, Any]],
    predecessors: list[dict[str, Any]],
    observed_at: datetime,
    stored_bytes: int,
    free_bytes: int,
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    used = config["budget"]["used_before_p1"]
    remaining_calls = (
        config["budget"]["whole_task_caps"]["quote_requests"]
        - used["quote_requests"]
    )
    for member, predecessor in zip(members, predecessors, strict=True):
        try:
            decision = evaluate_panel_trigger(
                config=event_config,
                member=member,
                panel_history=[
                    {
                        "panel_id": config["panel"]["predecessor_panel_id"],
                        "completed_at": predecessor["completed_at"],
                    }
                ],
                requested_panel=config["panel"]["panel_id"],
                now=_utc_text(observed_at),
                recovery_health="HEALTHY",
                response_bytes_used=used["response_bytes"],
                stored_bytes_used=stored_bytes,
                dataset_bytes_used=stored_bytes,
                free_disk_bytes=free_bytes,
                remaining_reserved_provider_calls=remaining_calls,
            )
        except Task21FinalCohortError as exc:
            raise Task21FollowupError(str(exc)) from exc
        decisions.append(decision)
    if any(
        item.get("status") != "READY_FOR_SEPARATE_EXTERNAL_AUTHORITY"
        for item in decisions
    ):
        details = ",".join(str(item.get("status")) for item in decisions)
        raise Task21FollowupError(f"followup_population_not_ready:{details}")
    return decisions


def run_event_triggered_followup_capture(
    *,
    gate: Task21FollowupExecutionGate | None,
    repo_root: Path,
    config_path: Path,
    transport_factory: Callable[[Mapping[str, Any]], Any] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    available_disk_bytes: int | None = None,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    """Capture the exact next panel after all members pass the same preflight."""

    if not isinstance(gate, Task21FollowupExecutionGate):
        raise Task21FollowupAuthorityRequired(
            "task21_followup_execution_gate_required"
        )
    root = repo_root.resolve()
    if not config_path.resolve().is_relative_to(root):
        raise Task21FollowupError("followup_config_outside_repository")
    config = _load_yaml(config_path)
    validate_followup_config(config, repo_root)
    observed_at = now()
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise Task21FollowupError("followup_now_must_be_timezone_aware")
    observed_at = observed_at.astimezone(UTC)

    recovery_path = _repo_path(
        repo_root, config["recovery"]["receipt_path"], name="recovery_receipt"
    )
    recovery = _load_json(recovery_path)
    try:
        validate_recovery_freshness(recovery, now=observed_at)
    except Task21LiveShakedownError as exc:
        raise Task21FollowupError(str(exc)) from exc
    free_bytes = (
        available_disk_bytes
        if available_disk_bytes is not None
        else shutil.disk_usage(repo_root).free
    )
    if free_bytes - DURABLE_BYTES_MAX < MIN_FREE_SPACE_AFTER_WRITE:
        raise Task21FollowupError("followup_disk_pressure")

    members = _load_members(config, repo_root)
    predecessors = _load_predecessors(config, repo_root)
    r2_acceptance = _load_json(
        _protected_path(config, repo_root, "R2_P0_RUNTIME_ACCEPTANCE")
    )
    admission = r2_acceptance.get("admission", {})
    accepted_member_ids = admission.get("member_ids")
    if accepted_member_ids is None:
        accepted_member_ids = [
            item.get("member_id") for item in admission.get("members", [])
        ]
    if (
        r2_acceptance.get("status") != "PASS"
        or accepted_member_ids != config["population"]["member_ids"]
    ):
        raise Task21FollowupError("followup_r2_acceptance_drift")
    event_config = _load_yaml(
        _protected_path(config, repo_root, "EVENT_TRIGGERED_RUNTIME_PLAN")
    )
    task_root = repo_root / "local/task21_forward"
    stored_before = _directory_bytes(task_root)
    decisions = _preflight_triggers(
        config=config,
        event_config=event_config,
        members=members,
        predecessors=predecessors,
        observed_at=observed_at,
        stored_bytes=stored_before,
        free_bytes=free_bytes,
    )

    if output_root_override is not None and transport_factory is None:
        raise Task21FollowupError(
            "followup_output_override_requires_injected_transport"
        )
    output_root = (
        output_root_override.resolve()
        if output_root_override is not None
        else _repo_path(
            repo_root, config["runtime"]["output_root"], name="output_root"
        )
    )
    claim = {
        "atom_id": config["atom_id"],
        "config_sha256": sha256_file(config_path),
        "started_at": _utc_text(observed_at),
    }
    run_id = (
        config["panel"]["panel_id"].lower()
        + "-"
        + observed_at.strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + sha256_bytes(canonical_json_bytes(claim))[:12]
    )
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21FollowupError("followup_run_output_already_exists")

    summaries: list[dict[str, Any]] = []
    started = clock()
    for index, member in enumerate(members):
        if index:
            sleeper(MINIMUM_INTERVAL_SECONDS)
        if clock() - started >= WALL_SECONDS_MAX:
            break
        transport = (
            transport_factory(member)
            if transport_factory is not None
            else BoundedQuoteTransport(
                gate=JupiterExecutionGate(JUPITER_AUTHORITY)
            )
        )
        summary = _capture_member(
            run_root=run_root,
            config_hash=sha256_file(config_path),
            atom_id=config["atom_id"],
            panel_id=config["panel"]["panel_id"],
            member=member,
            transport=transport,
            now=now,
            clock=clock,
        )
        summaries.append(summary)
        if summary["status"] != "COMPLETE":
            break

    calls = sum(int(item["provider_calls"]) for item in summaries)
    received = sum(int(item["received_bytes"]) for item in summaries)
    if calls > CALLS_TOTAL_MAX:
        raise Task21FollowupError("followup_total_call_cap_exceeded")
    if received > RECEIVED_BYTES_MAX:
        raise Task21FollowupError("followup_total_received_cap_exceeded")
    complete = len(summaries) == MEMBERS_EXACT and all(
        item["status"] == "COMPLETE" for item in summaries
    )
    stop_reason = None
    if not complete:
        stop_reason = (
            next(
                (item["stop_reason"] for item in summaries if item["stop_reason"]),
                None,
            )
            or "FOLLOWUP_POPULATION_INCOMPLETE"
        )
    next_members = [
        {
            "member_id": item["member_id"],
            "not_before_at": _utc_text(
                _utc("completed_at", item["completed_at"])
                + timedelta(seconds=config["panel"]["minimum_separation_seconds"])
            ),
        }
        for item in summaries
        if item["status"] == "COMPLETE"
    ]
    receipt = {
        "schema": "smial.task21.event-triggered-followup-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": config["atom_id"],
        "batch_id": config["panel"]["batch_id"],
        "panel_id": config["panel"]["panel_id"],
        "run_id": run_id,
        "status": "PASS" if complete else "STOPPED",
        "stop_reason": stop_reason,
        "started_at": _utc_text(observed_at),
        "population": {
            "member_ids": list(config["population"]["member_ids"]),
            "changed": False,
            "outcome_or_route_selection_used": False,
            "all_members_eligible_before_first_provider_call": True,
            "trigger_decisions": decisions,
        },
        "capture": {
            "panels_complete": sum(
                item["status"] == "COMPLETE" for item in summaries
            ),
            "panels_stopped": sum(
                item["status"] != "COMPLETE" for item in summaries
            ),
            "windows": summaries,
        },
        "actual_actions": {
            "provider_api_rpc_wss_calls": calls,
            "jupiter_calls": calls,
            "modeled_provider_credits": calls,
            "received_bytes": received,
            "candidate_nominations": 0,
            "candidate_admissions": 0,
            "retries": 0,
            "concurrency": 1,
            "cash_spend_usd_cents": 0,
            "credentials_used": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "scheduler_or_background_process": False,
            "deploy": False,
            "catalog_mutation": False,
            "source_mutation": False,
            "wallet_signer_transaction_actions": 0,
            "destructive_actions": False,
            "merge": False,
        },
        "budget_after": {
            "external_requests": config["budget"]["used_before_p1"][
                "external_requests"
            ]
            + calls,
            "source_requests": config["budget"]["used_before_p1"][
                "source_requests"
            ],
            "quote_requests": config["budget"]["used_before_p1"][
                "quote_requests"
            ]
            + calls,
            "response_bytes": config["budget"]["used_before_p1"][
                "response_bytes"
            ]
            + received,
        },
        "next_boundary": {
            "status": (
                "P2_EVENT_TRIGGER_READY_AFTER_MINIMUM_SEPARATION"
                if complete
                else "R2_P1_REVIEW_REQUIRED"
            ),
            "atom_id": config["panel"]["next_atom_id"] if complete else None,
            "member_not_before": next_members,
            "narrow_expiry_window": None,
            "external_authority_granted": False,
            "task22_authorized": False,
            "a7_authorized": False,
        },
        "non_claims": [
            "NO_TRADE_SWAP_FILL_POSITION_PNL_OR_ALPHA_CLAIM",
            "NO_OUTCOME_BASED_RESELECTION",
            "NO_MARKET_WIDE_OR_CROSS_REGIME_CLAIM",
            "NO_DRIVE_CATALOG_SOURCE_OR_DEPLOY_ACTION",
            "NO_TASK22_OR_A7_AUTHORITY",
        ],
    }
    receipt_path = run_root / "runtime_receipt.json"
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    if _directory_bytes(run_root) + len(receipt_bytes) > DURABLE_BYTES_MAX:
        raise Task21FollowupError("followup_durable_cap_would_be_exceeded")
    _write_new(receipt_path, receipt_bytes)
    stored = _directory_bytes(run_root)
    if stored > DURABLE_BYTES_MAX:
        raise Task21FollowupError("followup_durable_cap_exceeded")
    result = dict(receipt)
    result["local_evidence"] = {
        "root": (
            f"TEST_OUTPUT_ROOT/{run_root.name}"
            if output_root_override is not None
            else run_root.relative_to(repo_root).as_posix()
        ),
        "stored_bytes": stored,
        "runtime_receipt_sha256": sha256_file(receipt_path),
        "files": _inventory(run_root),
        "tracked_in_git": False,
        "create_only": True,
    }
    return result
