"""Bounded event-triggered R2 P2 capture for TASK-21."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.jupiter_quote_transport import (
    EXTERNAL_AUTHORITY_PHRASE as JUPITER_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate as JupiterExecutionGate,
)
from solana_alpha_lab.task21_event_triggered_final_cohort import (
    Task21FinalCohortError,
    evaluate_panel_trigger,
)
from solana_alpha_lab.task21_event_triggered_followup_capture import (
    CALLS_PER_PANEL_MAX,
    CALLS_TOTAL_MAX,
    DURABLE_BYTES_MAX,
    MEMBERS_EXACT,
    MIN_FREE_SPACE_AFTER_WRITE,
    MINIMUM_INTERVAL_SECONDS,
    RECEIVED_BYTES_MAX,
    SCHEMA_VERSION,
    TASK_ID,
    WALL_SECONDS_MAX,
    Task21FollowupError,
    _capture_member,
    _directory_bytes,
    _inventory,
    _load_json,
    _load_members,
    _load_predecessors,
    _load_yaml,
    _protected_path,
    _repo_path,
    _utc_text,
    _verify_hash,
    _write_new,
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


ATOM_ID = "T21-A6S_R2_P2_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1"


class Task21P2Error(Task21FollowupError):
    """P2 cannot proceed without violating its frozen boundary."""


class Task21P2AuthorityRequired(Task21P2Error):
    """The exact P2 external authority phrase is absent."""


@dataclass(frozen=True, slots=True)
class Task21P2ExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != ATOM_ID:
            raise Task21P2AuthorityRequired("task21_p2_authority_phrase_mismatch")


def validate_p2_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if (
        config.get("schema")
        != "smial.task21_event_triggered_followup_capture"
        or config.get("schema_version") != SCHEMA_VERSION
        or config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
        or config.get("status")
        != "FROZEN_FOR_SEPARATE_EXACT_PROVIDER_AUTHORITY"
    ):
        raise Task21P2Error("p2_config_identity_drift")
    protected = config.get("protected_inputs")
    if not isinstance(protected, list) or len(protected) != 4:
        raise Task21P2Error("p2_protected_inputs_drift")
    roles = [item.get("role") for item in protected if isinstance(item, Mapping)]
    expected_roles = [
        "EVENT_TRIGGERED_RUNTIME_PLAN",
        "R2_P0_RUNTIME_ACCEPTANCE",
        "R2_P1_RUNTIME_ACCEPTANCE",
        "R2_ADMISSION_EVENTS",
    ]
    if roles != expected_roles:
        raise Task21P2Error("p2_protected_role_order_drift")
    for role in roles:
        _protected_path(config, repo_root, str(role))

    panel = config.get("panel", {})
    expected_panel = {
        "batch_id": "T21-R2",
        "panel_id": "P2",
        "predecessor_panel_id": "P1",
        "next_panel_id": None,
        "next_atom_id": None,
        "population_members_exact": MEMBERS_EXACT,
        "minimum_separation_seconds": 1801,
        "member_total_span_seconds_max": 86400,
        "narrow_expiry_window": None,
        "late_policy": "ALLOW_UNTIL_MEMBER_TOTAL_SPAN_DEADLINE",
        "admission_outcome_reselection_allowed": False,
    }
    if any(panel.get(key) != value for key, value in expected_panel.items()):
        raise Task21P2Error("p2_panel_contract_drift")

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
        raise Task21P2Error("p2_population_contract_drift")
    predecessor = config.get("predecessor_receipts")
    if not isinstance(predecessor, list) or len(predecessor) != MEMBERS_EXACT:
        raise Task21P2Error("p2_predecessor_receipts_drift")
    if [item.get("member_id") for item in predecessor] != member_ids:
        raise Task21P2Error("p2_predecessor_order_drift")
    for item in predecessor:
        path = _repo_path(
            repo_root,
            item.get("path") if isinstance(item, Mapping) else None,
            name="p2_predecessor_receipt",
        )
        _verify_hash(
            path,
            item.get("sha256") if isinstance(item, Mapping) else None,
            name="p2_predecessor_receipt",
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
        raise Task21P2Error("p2_capture_contract_drift")

    budget = config.get("budget", {})
    caps = budget.get("whole_task_caps", {})
    used = budget.get("used_before_p2", {})
    if (
        caps
        != {
            "external_requests": 192,
            "source_requests": 8,
            "quote_requests": 184,
            "response_bytes": 25_165_824,
            "stored_bytes": 125_829_120,
            "dataset_bytes": 268_435_456,
        }
        or used
        != {
            "external_requests": 110,
            "source_requests": 6,
            "quote_requests": 104,
            "response_bytes": 191_486,
        }
        or used["external_requests"] + CALLS_TOTAL_MAX
        > caps["external_requests"]
        or used["quote_requests"] + CALLS_TOTAL_MAX > caps["quote_requests"]
        or used["response_bytes"] + RECEIVED_BYTES_MAX > caps["response_bytes"]
        or budget.get("minimum_free_space_bytes_after_write")
        != MIN_FREE_SPACE_AFTER_WRITE
        or budget.get("cap_behavior") != "FAIL_CLOSED_NO_RETRY"
    ):
        raise Task21P2Error("p2_budget_contract_drift")

    recovery = config.get("recovery", {})
    if (
        recovery.get("required_health") != "HEALTHY"
        or recovery.get("backup_age_hours_max_at_start") != 24
        or recovery.get("restore_age_hours_max_at_start") != 168
        or recovery.get("drive_actions") != 0
    ):
        raise Task21P2Error("p2_recovery_contract_drift")
    recovery_path = _repo_path(
        repo_root, recovery.get("receipt_path"), name="p2_recovery_receipt"
    )
    _verify_hash(
        recovery_path,
        recovery.get("receipt_sha256"),
        name="p2_recovery_receipt",
    )

    runtime = config.get("runtime", {})
    if (
        runtime.get("output_root")
        != "local/task21_forward/final_cohort/r2/p2"
        or runtime.get("write_behavior") != "CREATE_ONLY_CONTENT_ADDRESSED"
        or runtime.get("all_members_eligible_before_first_provider_call")
        is not True
        or runtime.get("partial_failure_policy")
        != "RETAIN_EVIDENCE_AND_STOP_NO_RETRY"
        or runtime.get("scheduler_or_background_process") is not False
    ):
        raise Task21P2Error("p2_runtime_contract_drift")

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
        raise Task21P2Error("p2_authority_boundary_drift")
    next_boundary = config.get("next_boundary", {})
    if next_boundary != {
        "complete": "R2_COMPLETE_REVIEW_REQUIRED_FOR_R3_SOURCE_P0",
        "next_atom_id": None,
        "external_authority_granted": False,
        "stopped": "R2_P2_REVIEW_REQUIRED",
        "task22_authorized": False,
        "a7_authorized": False,
    }:
        raise Task21P2Error("p2_next_boundary_drift")


def _p0_history(
    config: Mapping[str, Any], repo_root: Path
) -> dict[str, str]:
    acceptance = _load_json(
        _protected_path(config, repo_root, "R2_P0_RUNTIME_ACCEPTANCE")
    )
    if acceptance.get("status") != "PASS":
        raise Task21P2Error("p2_p0_acceptance_not_pass")
    windows = acceptance.get("p0", {}).get("windows", [])
    result = {
        item.get("member_id"): item.get("completed_at")
        for item in windows
        if isinstance(item, Mapping)
    }
    if set(result) != set(config["population"]["member_ids"]):
        raise Task21P2Error("p2_p0_history_population_drift")
    if not all(isinstance(value, str) for value in result.values()):
        raise Task21P2Error("p2_p0_history_time_drift")
    return result  # type: ignore[return-value]


def _validate_p1_acceptance(
    config: Mapping[str, Any], repo_root: Path
) -> None:
    acceptance = _load_json(
        _protected_path(config, repo_root, "R2_P1_RUNTIME_ACCEPTANCE")
    )
    if (
        acceptance.get("status") != "PASS"
        or acceptance.get("population", {}).get("member_ids")
        != config["population"]["member_ids"]
        or acceptance.get("p1", {}).get("panels_complete") != MEMBERS_EXACT
        or acceptance.get("p1", {}).get("panels_stopped") != 0
    ):
        raise Task21P2Error("p2_p1_acceptance_drift")


def _preflight_p2(
    *,
    config: Mapping[str, Any],
    event_config: Mapping[str, Any],
    members: list[dict[str, Any]],
    predecessors: list[dict[str, Any]],
    p0_history: Mapping[str, str],
    observed_at: datetime,
    stored_bytes: int,
    free_bytes: int,
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    used = config["budget"]["used_before_p2"]
    remaining_calls = (
        config["budget"]["whole_task_caps"]["quote_requests"]
        - used["quote_requests"]
    )
    for member, predecessor in zip(members, predecessors, strict=True):
        member_id = member["member_id"]
        try:
            decision = evaluate_panel_trigger(
                config=event_config,
                member=member,
                panel_history=[
                    {"panel_id": "P0", "completed_at": p0_history[member_id]},
                    {"panel_id": "P1", "completed_at": predecessor["completed_at"]},
                ],
                requested_panel="P2",
                now=_utc_text(observed_at),
                recovery_health="HEALTHY",
                response_bytes_used=used["response_bytes"],
                stored_bytes_used=stored_bytes,
                dataset_bytes_used=stored_bytes,
                free_disk_bytes=free_bytes,
                remaining_reserved_provider_calls=remaining_calls,
            )
        except Task21FinalCohortError as exc:
            raise Task21P2Error(str(exc)) from exc
        decisions.append(decision)
    if any(
        item.get("status") != "READY_FOR_SEPARATE_EXTERNAL_AUTHORITY"
        for item in decisions
    ):
        details = ",".join(str(item.get("status")) for item in decisions)
        raise Task21P2Error(f"p2_population_not_ready:{details}")
    return decisions


def run_r2_p2_capture(
    *,
    gate: Task21P2ExecutionGate | None,
    repo_root: Path,
    config_path: Path,
    transport_factory: Callable[[Mapping[str, Any]], Any] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    available_disk_bytes: int | None = None,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(gate, Task21P2ExecutionGate):
        raise Task21P2AuthorityRequired("task21_p2_execution_gate_required")
    root = repo_root.resolve()
    if not config_path.resolve().is_relative_to(root):
        raise Task21P2Error("p2_config_outside_repository")
    config = _load_yaml(config_path)
    validate_p2_config(config, repo_root)
    observed_at = now()
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise Task21P2Error("p2_now_must_be_timezone_aware")
    observed_at = observed_at.astimezone(UTC)

    recovery_path = _repo_path(
        repo_root, config["recovery"]["receipt_path"], name="p2_recovery_receipt"
    )
    recovery = _load_json(recovery_path)
    try:
        validate_recovery_freshness(recovery, now=observed_at)
    except Task21LiveShakedownError as exc:
        raise Task21P2Error(str(exc)) from exc
    free_bytes = (
        available_disk_bytes
        if available_disk_bytes is not None
        else shutil.disk_usage(repo_root).free
    )
    if free_bytes - DURABLE_BYTES_MAX < MIN_FREE_SPACE_AFTER_WRITE:
        raise Task21P2Error("p2_disk_pressure")

    members = _load_members(config, repo_root)
    predecessors = _load_predecessors(config, repo_root)
    _validate_p1_acceptance(config, repo_root)
    p0_history = _p0_history(config, repo_root)
    event_config = _load_yaml(
        _protected_path(config, repo_root, "EVENT_TRIGGERED_RUNTIME_PLAN")
    )
    stored_before = _directory_bytes(repo_root / "local/task21_forward")
    decisions = _preflight_p2(
        config=config,
        event_config=event_config,
        members=members,
        predecessors=predecessors,
        p0_history=p0_history,
        observed_at=observed_at,
        stored_bytes=stored_before,
        free_bytes=free_bytes,
    )

    if output_root_override is not None and transport_factory is None:
        raise Task21P2Error("p2_output_override_requires_injected_transport")
    output_root = (
        output_root_override.resolve()
        if output_root_override is not None
        else _repo_path(
            repo_root, config["runtime"]["output_root"], name="p2_output_root"
        )
    )
    claim = {
        "atom_id": ATOM_ID,
        "config_sha256": sha256_file(config_path),
        "started_at": _utc_text(observed_at),
    }
    run_id = (
        "p2-"
        + observed_at.strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + sha256_bytes(canonical_json_bytes(claim))[:12]
    )
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21P2Error("p2_run_output_already_exists")

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
            atom_id=ATOM_ID,
            panel_id="P2",
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
        raise Task21P2Error("p2_total_call_cap_exceeded")
    if received > RECEIVED_BYTES_MAX:
        raise Task21P2Error("p2_total_received_cap_exceeded")
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
            or "P2_POPULATION_INCOMPLETE"
        )
    used = config["budget"]["used_before_p2"]
    receipt = {
        "schema": "smial.task21.r2-p2-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "batch_id": "T21-R2",
        "panel_id": "P2",
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
        "p2": {
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
        "budget_after_p2": {
            "external_requests": used["external_requests"] + calls,
            "source_requests": used["source_requests"],
            "quote_requests": used["quote_requests"] + calls,
            "response_bytes": used["response_bytes"] + received,
        },
        "next_boundary": {
            "status": (
                config["next_boundary"]["complete"]
                if complete
                else config["next_boundary"]["stopped"]
            ),
            "atom_id": None,
            "external_authority_granted": False,
            "r3_source_or_admission_authorized": False,
            "task22_authorized": False,
            "a7_authorized": False,
        },
        "non_claims": [
            "NO_TRADE_SWAP_FILL_POSITION_PNL_OR_ALPHA_CLAIM",
            "NO_OUTCOME_BASED_RESELECTION",
            "NO_R3_SOURCE_NOMINATION_OR_ADMISSION_ACTION",
            "NO_DRIVE_CATALOG_SOURCE_OR_DEPLOY_ACTION",
            "NO_TASK22_OR_A7_AUTHORITY",
        ],
    }
    receipt_path = run_root / "runtime_receipt.json"
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    if _directory_bytes(run_root) + len(receipt_bytes) > DURABLE_BYTES_MAX:
        raise Task21P2Error("p2_durable_cap_would_be_exceeded")
    _write_new(receipt_path, receipt_bytes)
    stored = _directory_bytes(run_root)
    if stored > DURABLE_BYTES_MAX:
        raise Task21P2Error("p2_durable_cap_exceeded")
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
