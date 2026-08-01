"""Bounded outcome-blind R3 source and P0 capture for TASK-21."""

from __future__ import annotations

import json
import re
import shutil
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from solana_alpha_lab.jupiter_quote_transport import (
    EXTERNAL_AUTHORITY_PHRASE as JUPITER_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate as JupiterExecutionGate,
)
from solana_alpha_lab.task21_event_triggered_final_cohort import (
    Task21FinalCohortError,
    evaluate_nomination_observation,
    evaluate_panel_trigger,
    initial_runtime_state,
    validate_protected_inputs as validate_final_cohort_inputs,
)
from solana_alpha_lab.task21_event_triggered_panel_capture import (
    EventPanelCaptureError,
    capture_quote_panel,
    directory_bytes,
    inventory,
    utc_text,
    write_new,
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
from solana_alpha_lab.task21_r2_event_triggered_capture import (
    BoundedSourceTransport,
    SourceTransport,
    _json_document,
    _load_json,
    _load_yaml,
    _rpc_request_bytes,
    _source_helper_config,
)
from solana_alpha_lab.task21_real_nomination_source import (
    DEXSCREENER_URL,
    SOLANA_RPC_URL,
    StructuralCandidate,
    select_profile_mints,
    validate_rpc_mints,
)


TASK_ID = "TASK-21"
ATOM_ID = "T21-A6S_R3_EVENT_TRIGGERED_SOURCE_AND_P0_CAPTURE_V1"
BATCH_ID = "T21-R3"
SCHEMA_VERSION = "1.0"
OUTPUT_RELATIVE_ROOT = "local/task21_forward/final_cohort/r3"
HYPOTHESIS_ID = "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1"
MEMBERS_MAX = 2
SOURCE_CALLS_MAX = 2
JUPITER_CALLS_MAX = 16
EXTERNAL_CALLS_MAX = 18
DURABLE_BYTES_MAX = 16_777_216
MIN_FREE_SPACE_AFTER_WRITE = 2_147_483_648
WALL_SECONDS_MAX = 300
MINIMUM_INTERVAL_SECONDS = 2.2
JUPITER_RECEIVED_BYTES_PER_PANEL_MAX = 3_145_728
PRIOR_SEEN_MINTS = [
    "2MUB7LUviPc5hmEKKuogxdDQhEAEC3QRBbeTB7bUpump",
    "2zRj2vtREeogejN4zuYtBd9drCma7GtaWmUSdz28pump",
    "35CeebrkDFt6RhtpkAj19f7JStnxBjkyVcuLDH2dpump",
    "2Ezm4w3gFdymRAyhx9KEsbJV9NA79Y7UoiNWeXNFpump",
    "2HU2VftbJ7Fp9P5pEbneNsRhax8boHhTVS1KLnYrpump",
    "2JdM5MHiXjsQz5QgnSQfbidZDTVXCLki74jMYgJapump",
]


class Task21R3Error(RuntimeError):
    """R3 cannot proceed without violating its frozen boundary."""


class Task21R3AuthorityRequired(Task21R3Error):
    """The exact R3 external authority phrase is absent."""


@dataclass(frozen=True, slots=True)
class Task21R3ExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != ATOM_ID:
            raise Task21R3AuthorityRequired("task21_r3_authority_phrase_mismatch")


def _protected_path(
    config: Mapping[str, Any], repo_root: Path, role: str
) -> Path:
    matches = [
        item for item in config["protected_inputs"] if item.get("role") == role
    ]
    if len(matches) != 1:
        raise Task21R3Error(f"r3_protected_role_drift:{role}")
    return repo_root / matches[0]["path"]


def validate_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if (
        config.get("schema") != "smial.task21_r3_event_triggered_source_p0"
        or config.get("schema_version") != SCHEMA_VERSION
        or config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
        or config.get("status")
        != "FROZEN_FOR_SEPARATE_EXACT_PROVIDER_AUTHORITY"
    ):
        raise Task21R3Error("r3_config_identity_drift")
    protected = config.get("protected_inputs")
    if not isinstance(protected, list) or len(protected) != 7:
        raise Task21R3Error("r3_protected_inputs_drift")
    root = repo_root.resolve()
    for item in protected:
        relative = item.get("path") if isinstance(item, Mapping) else None
        expected = item.get("sha256") if isinstance(item, Mapping) else None
        if (
            not isinstance(relative, str)
            or re.fullmatch(r"[0-9a-f]{64}", str(expected)) is None
        ):
            raise Task21R3Error("r3_protected_input_identity_invalid")
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise Task21R3Error("r3_protected_input_outside_repo") from exc
        if not path.is_file() or sha256_file(path) != expected:
            raise Task21R3Error(
                f"r3_protected_input_hash_drift:{item.get('role')}"
            )

    source = config.get("source", {})
    profile = source.get("profile_endpoint", {})
    rpc = source.get("mint_validation_rpc", {})
    selection = source.get("selection", {})
    if (
        source.get("authentication") != "NONE"
        or profile.get("url") != DEXSCREENER_URL
        or profile.get("method") != "GET"
        or profile.get("response_rows_max") != 200
        or profile.get("response_bytes_max") != 2_097_152
        or rpc.get("url") != SOLANA_RPC_URL
        or rpc.get("method") != "getMultipleAccounts"
        or rpc.get("data_slice") != {"offset": 0, "length": 82}
        or rpc.get("account_count_max") != 100
        or rpc.get("response_bytes_max") != 6_291_456
        or selection.get("rpc_candidate_mints_max") != 100
        or selection.get("structural_candidates_max") != 100
        or selection.get("outcome_or_route_inputs_allowed") is not False
    ):
        raise Task21R3Error("r3_source_contract_drift")
    cohort = config.get("cohort", {})
    novelty = cohort.get("novelty", {})
    if (
        cohort.get("batch_id") != BATCH_ID
        or cohort.get("nomination_cap") != MEMBERS_MAX
        or cohort.get("admission_cap") != MEMBERS_MAX
        or cohort.get("prior_seen_mints") != PRIOR_SEEN_MINTS
        or novelty.get("prior_source_observation_id")
        != "T21-R2-SOURCE-8b4ef3fefa34efd6d56e"
        or novelty.get("prior_source_content_sha256")
        != "9d0ed987289b32a899fe08bfcddecc952ed80ef69c338429a79de8e16a315a9f"
        or novelty.get("prior_observed_at")
        != "2026-08-01T11:46:58.123523Z"
    ):
        raise Task21R3Error("r3_cohort_contract_drift")
    p0 = config.get("p0", {})
    if (
        p0.get("horizon_id") != "P0"
        or p0.get("notionals_usd") != [10, 25, 50, 100]
        or p0.get("provider_calls_per_panel_max") != 8
        or p0.get("provider_calls_total_max") != JUPITER_CALLS_MAX
        or p0.get("endpoint") != "https://api.jup.ag/swap/v1/quote"
        or p0.get("authentication") != "NONE"
        or p0.get("retries") != 0
        or p0.get("concurrency") != 1
    ):
        raise Task21R3Error("r3_p0_contract_drift")
    budget = config.get("budget", {})
    caps = budget.get("whole_task_caps", {})
    used = budget.get("used_before_r3", {})
    atom_caps = budget.get("this_atom_caps", {})
    followup = budget.get("remaining_followup_reservation", {})
    if (
        caps.get("external_requests") != 192
        or caps.get("source_requests") != 8
        or caps.get("quote_requests") != 184
        or used.get("external_requests") != 134
        or used.get("source_requests") != 6
        or used.get("quote_requests") != 128
        or atom_caps
        != {
            "external_requests": 18,
            "source_requests": 2,
            "quote_requests": 16,
            "durable_local_bytes": DURABLE_BYTES_MAX,
        }
        or followup != {"external_requests": 32, "quote_requests": 32}
        or used["external_requests"]
        + atom_caps["external_requests"]
        + followup["external_requests"]
        > caps["external_requests"]
        or used["quote_requests"]
        + atom_caps["quote_requests"]
        + followup["quote_requests"]
        > caps["quote_requests"]
    ):
        raise Task21R3Error("r3_budget_contract_drift")
    authority = config.get("authority", {})
    expected = {
        "exact_phrase": ATOM_ID,
        "provider_api_rpc_wss_calls_max": EXTERNAL_CALLS_MAX,
        "dexscreener_calls_max": 1,
        "solana_public_rpc_calls_max": 1,
        "jupiter_calls_max": JUPITER_CALLS_MAX,
        "nominations_max": MEMBERS_MAX,
        "admissions_max": MEMBERS_MAX,
        "durable_local_bytes_max": DURABLE_BYTES_MAX,
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
    if any(authority.get(key) != value for key, value in expected.items()):
        raise Task21R3Error("r3_authority_boundary_drift")
    review = _load_json(
        _protected_path(config, repo_root, "R2_COMPLETE_REVIEW")
    )
    if (
        review.get("status") != "PASS"
        or review.get("verdict") != "PROCEED_TO_R3_SOURCE_P0_PREP"
        or review.get("review", {}).get(
            "r2_quote_route_price_or_cost_values_read_for_r3_selection"
        )
        is not False
    ):
        raise Task21R3Error("r3_entry_review_drift")


def _candidate_event(
    *, candidate: StructuralCandidate, source_hash: str, observed_at: str
) -> dict[str, Any]:
    identity = sha256_bytes(
        canonical_json_bytes({"mint": candidate.mint, "source": source_hash})
    )[:20]
    return {
        "nomination_event_id": f"T21-R3-NOM-{identity}",
        "mint": candidate.mint,
        "mint_decimals": candidate.mint_decimals,
        "eligible": True,
        "observed_at": observed_at,
        "first_reliable_available_at": observed_at,
        "exact_rule_input_values": {
            "source_class": "PREDECLARED_CONTROL_COHORT",
            "structural_mint_initialized": True,
            "token_program": candidate.token_program,
            "prior_relevant_quote_outcome_exposure": False,
            "uses_task21_quote_route_or_price_outcome": False,
        },
    }


def _replay_r2_state(
    *, config: Mapping[str, Any], event_config: Mapping[str, Any], repo_root: Path
) -> dict[str, Any]:
    review = _load_json(
        _protected_path(config, repo_root, "R2_COMPLETE_REVIEW")
    )
    seed = review["r2_outcome_blind_replay_seed"]
    observation = {
        "batch_id": seed["batch_id"],
        "source_calls": seed["source_calls"],
        "source_observation_id": seed["source_observation_id"],
        "source_content_sha256": seed["source_content_sha256"],
        "observed_at": seed["observed_at"],
        "candidates": seed["candidates"],
    }
    try:
        result = evaluate_nomination_observation(
            config=event_config,
            state=initial_runtime_state(event_config),
            observation=observation,
            admitted_at=seed["admitted_at"],
        )
    except Task21FinalCohortError as exc:
        raise Task21R3Error(str(exc)) from exc
    accepted = _load_json(
        _protected_path(config, repo_root, "R2_SOURCE_P0_RUNTIME_ACCEPTANCE")
    )
    expected_ids = [item["member_id"] for item in accepted["admission"]["members"]]
    actual_ids = [item["member_id"] for item in result["members"]]
    if result.get("status") != "ADMITTED_OFFLINE_PLAN_ONLY" or actual_ids != expected_ids:
        raise Task21R3Error("r3_r2_state_replay_drift")
    return result["state"]


def _finalize(
    *, run_root: Path, receipt: dict[str, Any], repo_root: Path, test_output: bool
) -> dict[str, Any]:
    receipt_path = run_root / "runtime_receipt.json"
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    if directory_bytes(run_root) + len(receipt_bytes) > DURABLE_BYTES_MAX:
        raise Task21R3Error("r3_durable_byte_cap_would_be_exceeded")
    try:
        write_new(receipt_path, receipt_bytes)
    except EventPanelCaptureError as exc:
        raise Task21R3Error(str(exc)) from exc
    stored = directory_bytes(run_root)
    if stored > DURABLE_BYTES_MAX:
        raise Task21R3Error("r3_durable_byte_cap_exceeded")
    result = dict(receipt)
    result["local_evidence"] = {
        "root": (
            f"TEST_OUTPUT_ROOT/{run_root.name}"
            if test_output
            else run_root.relative_to(repo_root).as_posix()
        ),
        "stored_bytes": stored,
        "runtime_receipt_sha256": sha256_file(receipt_path),
        "files": inventory(run_root),
        "tracked_in_git": False,
        "create_only": True,
    }
    return result


def run_r3_source_p0_capture(
    *,
    gate: Task21R3ExecutionGate | None,
    repo_root: Path,
    config_path: Path,
    source_transport: SourceTransport | None = None,
    quote_transport_factory: Callable[[Mapping[str, Any]], Any] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    available_disk_bytes: int | None = None,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(gate, Task21R3ExecutionGate):
        raise Task21R3AuthorityRequired("task21_r3_execution_gate_required")
    root = repo_root.resolve()
    config = _load_yaml(config_path)
    validate_config(config, root)
    event_config = _load_yaml(
        _protected_path(config, root, "EVENT_TRIGGERED_RUNTIME_PLAN")
    )
    try:
        validate_final_cohort_inputs(repo_root=root, config=event_config)
    except Task21FinalCohortError as exc:
        raise Task21R3Error(str(exc)) from exc
    r2_state = _replay_r2_state(
        config=config, event_config=event_config, repo_root=root
    )
    started_at = now()
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise Task21R3Error("r3_runtime_now_must_be_timezone_aware")
    started_at = started_at.astimezone(UTC)
    recovery = _load_json(
        _protected_path(config, root, "CURRENT_RECOVERY_PROOF")
    )
    try:
        validate_recovery_freshness(recovery, now=started_at)
    except Task21LiveShakedownError as exc:
        raise Task21R3Error(str(exc)) from exc
    free_bytes = (
        available_disk_bytes
        if available_disk_bytes is not None
        else shutil.disk_usage(root).free
    )
    if free_bytes - DURABLE_BYTES_MAX < MIN_FREE_SPACE_AFTER_WRITE:
        raise Task21R3Error("r3_disk_pressure")
    if output_root_override is not None and (
        source_transport is None or quote_transport_factory is None
    ):
        raise Task21R3Error("r3_output_override_requires_injected_transports")
    output_root = (
        output_root_override.resolve()
        if output_root_override is not None
        else (root / OUTPUT_RELATIVE_ROOT).resolve()
    )
    claim = {
        "atom_id": ATOM_ID,
        "config_sha256": sha256_file(config_path),
        "started_at": utc_text(started_at),
    }
    run_id = (
        "r3-"
        + started_at.strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + sha256_bytes(canonical_json_bytes(claim))[:12]
    )
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21R3Error("r3_run_output_already_exists")

    transport = source_transport or BoundedSourceTransport(now=now)
    profile_cfg = config["source"]["profile_endpoint"]
    profile_capture = transport.execute(
        request_kind="DEXSCREENER_LATEST_TOKEN_PROFILES",
        method="GET",
        url=profile_cfg["url"],
        request_body=b"",
        response_bytes_max=profile_cfg["response_bytes_max"],
    )
    captures = [profile_capture]
    requested_mints: list[str] = []
    structural: list[StructuralCandidate] = []
    rpc_slot: int | None = None
    if profile_capture.stop_reason is None:
        profiles = _json_document(
            "r3_dexscreener_response", profile_capture.response_body
        )
        helper_config = _source_helper_config(config)
        requested_mints = select_profile_mints(
            profile_document=profiles, config=helper_config
        )
        if requested_mints:
            rpc_cfg = config["source"]["mint_validation_rpc"]
            rpc_capture = transport.execute(
                request_kind="SOLANA_GET_MULTIPLE_ACCOUNTS",
                method="POST",
                url=rpc_cfg["url"],
                request_body=_rpc_request_bytes(requested_mints),
                response_bytes_max=rpc_cfg["response_bytes_max"],
            )
            captures.append(rpc_capture)
            if rpc_capture.stop_reason is None:
                structural, rpc_slot = validate_rpc_mints(
                    rpc_document=_json_document(
                        "r3_solana_rpc_response", rpc_capture.response_body
                    ),
                    requested_mints=requested_mints,
                    config=helper_config,
                )
    observed_at = utc_text(max(item.response_at for item in captures))
    content_identity = {
        "source_version": config["source"]["source_version"],
        "captures": [
            {
                "request_kind": item.request_kind,
                "request_sha256": sha256_bytes(item.request_body),
                "status": item.status,
                "response_sha256": sha256_bytes(item.response_body),
            }
            for item in captures
        ],
        "requested_mints": requested_mints,
        "rpc_context_slot": rpc_slot,
    }
    source_hash = sha256_bytes(canonical_json_bytes(content_identity))
    source_id = "T21-R3-SOURCE-" + sha256_bytes(
        canonical_json_bytes({"content": source_hash, "observed_at": observed_at})
    )[:20]
    source_partition = {
        "schema": "smial.task21.r3-source-partition",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "run_id": run_id,
        "batch_id": BATCH_ID,
        "source_observation_id": source_id,
        "source_content_identity": content_identity,
        "source_content_sha256": source_hash,
        "observed_at": observed_at,
        "captures": [item.raw_envelope() for item in captures],
        "contains_secrets": False,
    }
    source_path = run_root / "source" / "source_partition.json"
    source_bytes = canonical_json_bytes(source_partition) + b"\n"
    if len(source_bytes) > DURABLE_BYTES_MAX:
        raise Task21R3Error("r3_source_partition_would_exceed_durable_cap")
    try:
        write_new(source_path, source_bytes)
    except EventPanelCaptureError as exc:
        raise Task21R3Error(str(exc)) from exc

    actions = {
        "provider_api_rpc_wss_calls": transport.attempts,
        "dexscreener_calls": sum(
            item.request_kind.startswith("DEXSCREENER") for item in captures
        ),
        "solana_public_rpc_calls": sum(
            item.request_kind.startswith("SOLANA") for item in captures
        ),
        "jupiter_calls": 0,
        "modeled_provider_credits": 0,
        "received_bytes": transport.received_bytes,
        "nominations": 0,
        "admissions": 0,
        "cash_spend_usd_cents": 0,
        "credentials_used": 0,
        "drive_reads": 0,
        "drive_writes": 0,
        "scheduler_or_background_process": False,
        "wallet_signer_transaction_actions": 0,
    }
    prior_seen = set(config["cohort"]["prior_seen_mints"])
    unseen = [item for item in structural if item.mint not in prior_seen][
        :MEMBERS_MAX
    ]
    source_stop = next(
        (item.stop_reason for item in captures if item.stop_reason), None
    )
    source_summary = {
        "source_observation_id": source_id,
        "source_content_sha256": source_hash,
        "observed_at": observed_at,
        "rpc_context_slot": rpc_slot,
        "requested_mints": len(requested_mints),
        "structurally_valid_mints": len(structural),
        "unseen_eligible_mints": len(unseen),
        "partition_sha256": sha256_file(source_path),
    }
    if source_stop is not None or not requested_mints or not unseen:
        reason = source_stop or (
            "NO_SOURCE_MINT_IDENTITIES"
            if not requested_mints
            else "NO_PREVIOUSLY_UNSEEN_ELIGIBLE_MINT"
        )
        return _finalize(
            run_root=run_root,
            repo_root=root,
            test_output=output_root_override is not None,
            receipt={
                "schema": "smial.task21.r3-source-p0-runtime-receipt",
                "schema_version": SCHEMA_VERSION,
                "task_id": TASK_ID,
                "atom_id": ATOM_ID,
                "run_id": run_id,
                "status": "STOPPED_NO_ADMISSION",
                "stop_reason": reason,
                "started_at": utc_text(started_at),
                "source": source_summary,
                "admission": {"candidate_states": [], "members": []},
                "p0": {"panels_complete": 0, "panels_stopped": 0, "windows": []},
                "actual_actions": actions,
                "next_boundary": {
                    "status": "R3_REVIEW_REQUIRED",
                    "external_authority_granted": False,
                },
                "non_claims": [
                    "NO_TRADE_OR_SWAP",
                    "NO_ALPHA_PNL_OR_MARKET_WIDE_CLAIM",
                    "NO_CATALOG_OR_SOURCE_MUTATION",
                ],
            },
        )

    candidates = [
        _candidate_event(
            candidate=item, source_hash=source_hash, observed_at=observed_at
        )
        for item in unseen
    ]
    candidates.sort(
        key=lambda item: (
            item["first_reliable_available_at"],
            item["observed_at"],
            item["nomination_event_id"],
            item["mint"],
        )
    )
    observation = {
        "batch_id": BATCH_ID,
        "source_calls": transport.attempts,
        "source_observation_id": source_id,
        "source_content_sha256": source_hash,
        "observed_at": observed_at,
        "candidates": candidates,
    }
    admitted_at = utc_text(now())
    try:
        admission = evaluate_nomination_observation(
            config=event_config,
            state=r2_state,
            observation=observation,
            admitted_at=admitted_at,
        )
    except Task21FinalCohortError as exc:
        raise Task21R3Error(str(exc)) from exc
    nomination_path = run_root / "admission" / "nomination_events.jsonl"
    nomination_bytes = b"".join(
        canonical_json_bytes(item) + b"\n" for item in candidates
    )
    try:
        write_new(nomination_path, nomination_bytes)
    except EventPanelCaptureError as exc:
        raise Task21R3Error(str(exc)) from exc
    actions["nominations"] = len(candidates)
    members = [
        dict(item, hypothesis_version_id=HYPOTHESIS_ID)
        for item in admission["members"]
    ]
    if not members:
        actions["provider_api_rpc_wss_calls"] = transport.attempts
        return _finalize(
            run_root=run_root,
            repo_root=root,
            test_output=output_root_override is not None,
            receipt={
                "schema": "smial.task21.r3-source-p0-runtime-receipt",
                "schema_version": SCHEMA_VERSION,
                "task_id": TASK_ID,
                "atom_id": ATOM_ID,
                "run_id": run_id,
                "status": "STOPPED_NO_ADMISSION",
                "stop_reason": admission.get("reason"),
                "started_at": utc_text(started_at),
                "source": source_summary,
                "admission": {
                    "candidate_states": admission["candidate_states"],
                    "members": [],
                },
                "p0": {"panels_complete": 0, "panels_stopped": 0, "windows": []},
                "actual_actions": actions,
                "next_boundary": {
                    "status": "R3_REVIEW_REQUIRED",
                    "external_authority_granted": False,
                },
                "non_claims": [
                    "NO_TRADE_OR_SWAP",
                    "NO_ALPHA_PNL_OR_MARKET_WIDE_CLAIM",
                    "NO_CATALOG_OR_SOURCE_MUTATION",
                ],
            },
        )

    admission_path = run_root / "admission" / "admission_events.jsonl"
    admission_bytes = b"".join(
        canonical_json_bytes(item) + b"\n" for item in members
    )
    try:
        write_new(admission_path, admission_bytes)
    except EventPanelCaptureError as exc:
        raise Task21R3Error(str(exc)) from exc
    admission_receipt = {
        "schema": "smial.task21.r3-admission-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "batch_id": BATCH_ID,
        "status": admission["status"],
        "admitted_at": admitted_at,
        "source_observation_id": source_id,
        "source_content_sha256": source_hash,
        "candidate_states": admission["candidate_states"],
        "member_ids": [item["member_id"] for item in members],
        "nomination_events_sha256": sha256_file(nomination_path),
        "admission_events_sha256": sha256_file(admission_path),
        "provider_calls_before_admission_persisted": transport.attempts,
        "jupiter_calls_before_admission_persisted": 0,
        "outcome_or_route_input_used": False,
    }
    admission_receipt_path = run_root / "admission" / "receipt.json"
    try:
        write_new(
            admission_receipt_path,
            canonical_json_bytes(admission_receipt) + b"\n",
        )
    except EventPanelCaptureError as exc:
        raise Task21R3Error(str(exc)) from exc
    actions["admissions"] = len(members)

    windows: list[dict[str, Any]] = []
    started_clock = clock()
    for index, member in enumerate(members):
        if index:
            sleeper(MINIMUM_INTERVAL_SECONDS)
        if clock() - started_clock >= WALL_SECONDS_MAX:
            break
        if (
            config["budget"]["used_before_r3"]["response_bytes"]
            + actions["received_bytes"]
            + JUPITER_RECEIVED_BYTES_PER_PANEL_MAX
            > config["budget"]["whole_task_caps"]["response_bytes"]
        ):
            break
        trigger = evaluate_panel_trigger(
            config=event_config,
            member=member,
            panel_history=[],
            requested_panel="P0",
            now=utc_text(now()),
            recovery_health="HEALTHY",
            response_bytes_used=(
                config["budget"]["used_before_r3"]["response_bytes"]
                + actions["received_bytes"]
            ),
            stored_bytes_used=directory_bytes(root / "local/task21_forward"),
            dataset_bytes_used=(
                config["budget"]["used_before_r3"]["dataset_bytes"]
                + directory_bytes(run_root)
            ),
            free_disk_bytes=free_bytes,
            remaining_reserved_provider_calls=len(members) * 24,
        )
        if trigger["status"] != "READY_FOR_SEPARATE_EXTERNAL_AUTHORITY":
            break
        quote_transport = (
            quote_transport_factory(member)
            if quote_transport_factory is not None
            else BoundedQuoteTransport(
                gate=JupiterExecutionGate(JUPITER_AUTHORITY)
            )
        )
        try:
            window = capture_quote_panel(
                run_root=run_root,
                task_id=TASK_ID,
                atom_id=ATOM_ID,
                batch_id=BATCH_ID,
                panel_id="P0",
                hypothesis_version_id=HYPOTHESIS_ID,
                config_hash=sha256_file(config_path),
                member=member,
                transport=quote_transport,
                now=now,
                clock=clock,
                wall_seconds_max=WALL_SECONDS_MAX,
                durable_bytes_max=DURABLE_BYTES_MAX,
            )
        except EventPanelCaptureError as exc:
            raise Task21R3Error(str(exc)) from exc
        windows.append(window)
        actions["jupiter_calls"] += int(window["provider_calls"])
        actions["modeled_provider_credits"] += int(window["provider_calls"])
        actions["received_bytes"] += int(window["received_bytes"])
        if window["status"] != "COMPLETE":
            break
    actions["provider_api_rpc_wss_calls"] = (
        transport.attempts + actions["jupiter_calls"]
    )
    if actions["provider_api_rpc_wss_calls"] > EXTERNAL_CALLS_MAX:
        raise Task21R3Error("r3_external_call_cap_exceeded")
    if actions["jupiter_calls"] > JUPITER_CALLS_MAX:
        raise Task21R3Error("r3_jupiter_call_cap_exceeded")
    complete = len(windows) == len(members) and all(
        item["status"] == "COMPLETE" for item in windows
    )
    stop_reason = None
    if not complete:
        stop_reason = (
            next(
                (item["stop_reason"] for item in windows if item["stop_reason"]),
                None,
            )
            or "P0_POPULATION_INCOMPLETE"
        )
    used = config["budget"]["used_before_r3"]
    receipt = {
        "schema": "smial.task21.r3-source-p0-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "run_id": run_id,
        "status": "PASS" if complete else "STOPPED",
        "stop_reason": stop_reason,
        "started_at": utc_text(started_at),
        "source": source_summary,
        "admission": {
            "candidate_states": admission["candidate_states"],
            "member_ids": [item["member_id"] for item in members],
            "receipt_sha256": sha256_file(admission_receipt_path),
            "persisted_before_first_jupiter_call": True,
            "outcome_or_route_input_used": False,
        },
        "p0": {
            "panels_complete": sum(
                item["status"] == "COMPLETE" for item in windows
            ),
            "panels_stopped": sum(
                item["status"] != "COMPLETE" for item in windows
            ),
            "windows": windows,
        },
        "actual_actions": actions,
        "budget_after_r3_p0": {
            "external_requests": (
                used["external_requests"]
                + actions["provider_api_rpc_wss_calls"]
            ),
            "source_requests": used["source_requests"] + transport.attempts,
            "quote_requests": used["quote_requests"] + actions["jupiter_calls"],
            "response_bytes": used["response_bytes"] + actions["received_bytes"],
        },
        "next_boundary": {
            "status": (
                "P1_EVENT_TRIGGER_READY_AFTER_MINIMUM_SEPARATION"
                if complete
                else "R3_REVIEW_REQUIRED"
            ),
            "atom_id": (
                "T21-A6S_R3_P1_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1"
                if complete
                else None
            ),
            "member_not_before": [
                {
                    "member_id": item["member_id"],
                    "not_before_at": utc_text(
                        datetime.fromisoformat(
                            item["completed_at"].replace("Z", "+00:00")
                        )
                        + timedelta(seconds=1801)
                    ),
                }
                for item in windows
                if item["status"] == "COMPLETE"
            ],
            "external_authority_granted": False,
            "task22_authorized": False,
            "a7_authorized": False,
        },
        "non_claims": [
            "NO_TRADE_OR_SWAP_EXECUTED",
            "NO_FILL_POSITION_PNL_OR_ALPHA_CLAIM",
            "NO_MARKET_WIDE_OR_CROSS_REGIME_CLAIM",
            "NO_DRIVE_CATALOG_SOURCE_OR_DEPLOY_ACTION",
            "NO_TASK22_OR_A7_AUTHORITY",
        ],
    }
    return _finalize(
        run_root=run_root,
        receipt=receipt,
        repo_root=root,
        test_output=output_root_override is not None,
    )
