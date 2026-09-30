#!/usr/bin/env python3
"""Thin network-free CLI for Hypothesis Forge operational sessions."""

from __future__ import annotations

import argparse
import importlib.util
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

HFIC_REQUIRED_PYTHON = "3.13.14"
HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE = "HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE"


def running_python_release(version_info: Any = None) -> str:
    info = sys.version_info if version_info is None else version_info
    return "{}.{}.{}".format(info.major, info.minor, info.micro)


def hfic_runtime_python_terminal(version_info: Any = None) -> str | None:
    if running_python_release(version_info) != HFIC_REQUIRED_PYTHON:
        return HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE
    return None


def enforce_hfic_runtime_python(version_info: Any = None) -> None:
    terminal = hfic_runtime_python_terminal(version_info)
    if terminal is None:
        return
    print(terminal, file=sys.stderr)
    raise SystemExit(1)


enforce_hfic_runtime_python()

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_root import (  # noqa: E402
    DataRootError,
    resolve_active_data_root,
    resolve_existing_data_root,
)
from solana_alpha_lab.factory.document_runner import (  # noqa: E402
    repository_git_snapshot,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    HficPreflightError,
    build_offline_commission_packet,
    is_fast_lane_commissioned,
    run_preflight,
    store_inventory_digest,
)
from solana_alpha_lab.factory.hfic_prospects import (  # noqa: E402
    HficProspectError,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    PENDING_STATES,
    apply_classification,
    apply_revision,
    backfill_legacy,
    canonical_preflight_receipt_sha256,
    find_session_by_search_key,
    freeze_draft,
    list_hfic_sessions,
    lookup_prior,
    persist_generated_draft,
    prove_runtime,
    show_session,
)
from solana_alpha_lab.factory.hfic_provenance import (  # noqa: E402
    apply_provenance_correction,
    inventory_placeholder_hfic_records,
)
from solana_alpha_lab.factory.hfic_suppression_semantics import (  # noqa: E402
    HficSuppressionError,
    run_science_memory_rebase,
)
from solana_alpha_lab.factory.hfic_memory_policy import (  # noqa: E402
    HficMemoryPolicyError,
    REASON_OWNER_CALIBRATION_RESET,
    REASON_OWNER_MEMORY_RESTORE,
    REASON_PRE_CAPABILITY_BASELINE,
    apply_memory_policy,
    memory_policy_status,
    preview_memory_policy,
)
from solana_alpha_lab.factory.hfic_repair_continuation import (  # noqa: E402
    RepairContinuationError,
    apply_repair_continuation,
    close_repair_continuation,
    explain_target_exclusion,
    list_repair_continuation_dispositions,
    plan_repair_continuation,
)
from solana_alpha_lab.factory.hfic_reopened_prior_routing import (  # noqa: E402
    DEFECTIVE_CONTROL_SESSION_ID,
    ReopenedPriorRoutingError,
    commission_reopened_priors,
    preview_control_reconsideration,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    ResearchStore,
    ResearchStoreError,
)


MAX_JSON_BYTES = 262144
_WINDOWS_PHYSICAL_PATH_RE = re.compile(
    r"""
    (?:
        (?<![A-Za-z0-9+.-])[A-Za-z]:(?:(?!//)[\\/]|[^\s\\/:]+\\)
        | (?<!:)//[^/\\\s]+[\\/][^\\\s]+
        | \\\\[^\\/]+[\\/][^\\/]+
        | (?<!\\)\\[^\\/\s]+\\[^\\/\s]+
    )
    """,
    re.VERBOSE,
)


class HficCliError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def emit(payload: dict[str, Any], *, exit_code: int = 0) -> int:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(rendered)
    return exit_code


_TECHNICAL_STOPS = frozenset(
    {
        "SCHEDULE_CONTEXT_UNBOUND",
        "CANONICAL_X300_SCHEDULE_INCOMPATIBLE",
        "SEARCH_EXHAUSTED_WITHOUT_COMPOUND",
        "SCHEDULE_LATENESS_MISMATCH",
        "FROZEN_INPUT_MISMATCH",
        "FROZEN_INPUT_REQUIRED",
        "PREVIEW_ENVELOPE_EXHAUSTED",
        "PREVIEW_STORE_SCOPE_REQUIRED",
        "DATA_ROOT_REQUIRED",
        "TEMPORAL_RESULT_INCOHERENT",
        "CALCULATION_REVISION_INPUT_MISMATCH",
    }
)


def _look_counts(store: Any, journal_scope: str) -> dict[str, int]:
    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks

    looks = list_discovery_looks(store, journal_scope)
    return {
        "records": len(looks),
        "main": sum(1 for item in looks if item.get("look_class") == "MAIN" and item.get("new_look") is True),
        "adaptive": sum(
            1 for item in looks if item.get("look_class") == "ADAPTIVE" and item.get("new_look") is True
        ),
    }


def _saved_result_stop(
    code: str,
    readout: Mapping[str, Any] | None,
    *,
    values_loaded: bool,
) -> dict[str, Any]:
    """Technical stop on a saved result. Names the ref, fields and repair; not more looks."""

    body: dict[str, Any] = {
        "reason_code": code,
        "terminal": "TECHNICAL_STOP",
        "technical_failure": True,
        "scientific_negative": False,
        "values_loaded": values_loaded,
        "writes": False,
    }
    if isinstance(readout, Mapping):
        body["result_refs"] = [readout.get("result_ref")]
        body["result_sha256"] = readout.get("result_sha256")
        body["calculation_version"] = readout.get("calculation_version")
        body["incoherent_fields"] = list(readout.get("incoherent_fields") or [])
    if code == "TEMPORAL_RESULT_INCOHERENT":
        body["repair_action"] = "CALCULATION_REVISION"
        body["next_action"] = "CORRECT_CALCULATION_REVISION"
    return body


def emit_error(code: str, *, exit_code: int = 1) -> int:
    print(code, file=sys.stderr)
    if code in _TECHNICAL_STOPS:
        print("TECHNICAL_STOP scientific_negative=false", file=sys.stderr)
    return exit_code


def _published_file_hash_mismatch(root: Path) -> bool:
    """True when published cohort bytes disagree with their declared hashes."""

    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        GroundedDiscoveryError,
        resolve_published_discovery_binding,
    )

    try:
        resolve_published_discovery_binding(root)
    except GroundedDiscoveryError as exc:
        return str(exc) == "BINDING_HASH_MISMATCH"
    return False


_REPAIR_OWNER_NEXT = {
    "PARENT_SESSION_MISSING": "PROVIDE_PARENT_SESSION_ID_FROM_SHOW_SESSION",
    "PARENT_SESSION_REQUIRED": "SHOW_SESSION_THEN_REPAIR_CONTINUATION_DRAFT",
    "PARENT_SESSION_MISMATCH": "ALIGN_DRAFT_PARENT_SESSION_ID",
    "PARENT_RUN_REQUIRED": "PROVIDE_PARENT_RUN_ID_OR_ENSURE_FORGE_RUN_RECEIPT",
    "PARENT_RUN_MISMATCH": "ALIGN_DRAFT_PARENT_RUN_ID",
    "PARENT_RUN_UNPROVEN": "OMIT_CALLER_RUN_ID_AND_USE_DERIVED_BINDING",
    "PARENT_RECEIPT_CONFLICT": "INSPECT_CONTRADICTING_FORGE_RUN_RECEIPT",
    "PARENT_BINDING_MISMATCH": "ALIGN_DRAFT_LEGACY_PARENT_BINDING",
    "PARENT_AGGREGATE_PRESENT": "USE_STORED_FORGE_RUN_RECEIPT",
    "CORPUS_BINDING_UNPROVEN": "RESTORE_JOURNAL_CORPUS_BINDING",
    "CORPUS_BINDING_CONFLICT": "RESOLVE_JOURNAL_CORPUS_BINDING",
    "REPRESENTATION_SCOPE_UNPROVEN": "RESTORE_SLOT_ADMISSION_REPRESENTATION",
    "SLOT_IDENTITY_UNPROVEN": "RESTORE_SLOT_ADMISSION_IDENTITY",
    "FOCUS_IDENTITY_UNPROVEN": "RESTORE_SLOT_ADMISSION_FOCUS",
    "MARKET_IDENTITY_UNPROVEN": "RESTORE_MARKET_EPOCH_BINDING",
    "SPENT_BUDGET_EXHAUSTED": "STOP_LOOK_BUDGET_EXHAUSTED",
    "REPAIR_RESULT_UNREADABLE": "RETRY_CLOSE_UNTIL_REPAIR_RESULT_IS_READABLE",
    "PARENT_TERMINAL_RECEIPT_MISSING": "PROVIDE_TERMINAL_RECEIPT_FROM_SHOW_SESSION",
    "PARENT_TERMINAL_NOT_ELIGIBLE": "STOP_SCIENTIFIC_CLOSE_STANDS",
    "PARENT_HAS_SELECTED_CANDIDATE": "STOP_SELECTED_CANDIDATE_NOT_REPAIRABLE_HERE",
    "PARENT_NOT_COMPLETED_NO_WORTHY": "STOP_SCIENTIFIC_CLOSE_STANDS",
    "TERMINAL_RECEIPT_REQUIRED": "ENSURE_SESSION_RECEIPT_SHA256_ON_SHOW_SESSION",
    "TERMINAL_RECEIPT_MISMATCH": "ALIGN_DRAFT_TERMINAL_RECEIPT",
    "JOURNAL_SCOPE_REQUIRED": "ENSURE_SEARCH_KEY_SHA256_ON_SHOW_SESSION",
    "JOURNAL_SCOPE_MISMATCH": "ALIGN_DRAFT_JOURNAL_SCOPE",
    "SCIENTIFIC_SLOT_REQUIRED": "ENSURE_SCIENTIFIC_SLOT_ON_SHOW_SESSION",
    "PARENT_SLOT_MISMATCH": "ALIGN_DRAFT_SCIENTIFIC_SLOT",
    "SPENT_BUDGET_INVALID": "PASS_SPENT_LOOKS_OR_ENSURE_DISCOVERY_JOURNAL",
    "SPENT_BUDGET_MISMATCH": "ALIGN_DRAFT_SPENT_LOOKS_TO_JOURNAL",
    "DISPOSITION_ALREADY_CLOSED": "STOP_CONTINUATION_ALREADY_CONSUMED",
    "DISPOSITION_NOT_FOUND": "STOP_CONTINUATION_UNKNOWN_DISPOSITION",
    "DISPOSITION_NOT_AUTHORIZED": "STOP_CONTINUATION_NOT_AUTHORIZED",
    "DISPOSITION_INVALID": "FIX_DRAFT_JSON_OR_RERUN_DRAFT_BUILDER",
    "DISPOSITION_SCHEMA_INVALID": "FIX_DRAFT_JSON_OR_RERUN_DRAFT_BUILDER",
    "ALLOWED_LOOKS_INVALID": "FIX_DRAFT_JSON_OR_RERUN_DRAFT_BUILDER",
    "COMPETING_ACTIVE_DISPOSITION": "CLOSE_COMPETING_DISPOSITION_THEN_STOP",
    "COMPETING_DISPOSITION_APPLIED": "CLOSE_COMPETING_DISPOSITION_THEN_STOP",
    "REPAIR_CONTINUATION_CONFIRM_REQUIRED": "ADD_CONFIRM_APPEND_ONLY_WITH_OWNER_AUTHORITY",
    "REPAIR_CONTINUATION_DRAFT_INVALID": "FIX_DRAFT_JSON_OR_RERUN_DRAFT_BUILDER",
    "REPAIR_CONTINUATION_GIT_SHA_UNRESOLVED": "RESOLVE_REPO_GIT_SHA_THEN_RERUN",
    "REPAIR_CONTINUATION_DISPOSITION_SHA_INVALID": "PASS_DISPOSITION_SHA256_FROM_APPLY",
    "OWNER_AUTHORIZATION_REQUIRED": "PASS_OWNER_AUTHORIZATION_ID",
    "TECHNICAL_GAP_REQUIRED": "PASS_TECHNICAL_GAP_CODE",
    "REPAIR_CAPABILITY_REQUIRED": "USE_CAP_HFIC_TEMPORAL_OPERABILITY_REPAIR_001",
    "REPAIR_CAPABILITY_MISMATCH": "USE_CAP_HFIC_TEMPORAL_OPERABILITY_REPAIR_001",
    "REPAIR_EXECUTION_NOT_COMPLETE": "COMPLETE_DISPOSITION_BOUND_REPAIR_EXECUTION_THEN_CLOSE",
    "REPAIR_FORGE_RUN_PERSIST_FAILED": "INSPECT_PARENT_FORGE_RUN_THEN_RETRY_CLOSE",
}


def emit_repair_blocked(code: str, *, exit_code: int = 2) -> int:
    """Owner-readable JSON for repair-continuation failures (stdout)."""

    next_step = _REPAIR_OWNER_NEXT.get(str(code), "INSPECT_REASON_CODE_THEN_RERUN")
    payload = {
        "status": "NOT_APPLICABLE",
        "reason_code": str(code),
        "writes": False,
        "owner_status": "BLOCKED",
        "next_step": next_step,
        "owner_readout": {
            "status": "BLOCKED",
            "reason_code": str(code),
            "next": next_step,
            "writes": False,
        },
    }
    return emit(payload, exit_code=exit_code)


def _assert_no_path_leak(payload: dict[str, Any], *forbidden: str) -> None:
    needles = ("SMIAL_DATA_ROOT", *(item for item in forbidden if item))

    def assert_safe_text(value: str) -> None:
        if _WINDOWS_PHYSICAL_PATH_RE.search(value) or any(
            needle in value for needle in needles
        ):
            raise HficCliError("PHYSICAL_PATH_LEAK")

    def walk(value: Any) -> None:
        if isinstance(value, str):
            assert_safe_text(value)
            return
        if isinstance(value, dict):
            for key, child in value.items():
                assert_safe_text(str(key))
                walk(child)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk(payload)


def _load_json_file(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    data = path.read_bytes()
    if len(data) > MAX_JSON_BYTES:
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    loaded = json.loads(data.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    return loaded


def _load_fast_lane():
    path = ROOT / "scripts" / "hypothesis_fast_lane.py"
    spec = importlib.util.spec_from_file_location("hfic_fast_lane_helper", path)
    if spec is None or spec.loader is None:
        raise HficCliError("FAST_LANE_NOT_COMMISSIONABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _commission_offline(repo_root: Path, data_root: Path) -> dict[str, Any]:
    module = _load_fast_lane()
    packet = build_offline_commission_packet(repo_root)
    with tempfile.TemporaryDirectory() as tmp:
        packet_path = Path(tmp) / "offline_commission.json"
        packet_path.write_text(
            json.dumps(packet, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        git_before = repository_git_snapshot(repo_root)
        try:
            payload = module.execute_commission_offline(repo_root, data_root, packet_path)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise HficCliError(code) from exc
            raise HficCliError("FAST_LANE_NOT_COMMISSIONABLE") from exc
        git_after = repository_git_snapshot(repo_root)
        if not git_before.unchanged(git_after):
            raise HficCliError("GIT_MUTATION_DETECTED")
    if payload.get("provider_calls_actual") not in {0, None}:
        raise HficCliError("PROVIDER_CALLS_FORBIDDEN")
    return payload


def _active_root(repo_root: Path, explicit_data_root: Path | None):
    return resolve_active_data_root(
        repo_root,
        explicit_data_root=explicit_data_root,
        is_commissioned=is_fast_lane_commissioned,
        inventory_digest=store_inventory_digest,
    )


def _owner_class_for_preflight_stop(body: Mapping[str, Any]) -> str:
    terminal = str(body.get("terminal") or "")
    router = str(body.get("router_decision") or "")
    if terminal in {
        "SEARCH_BUDGET_EXHAUSTED",
        "SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING",
        "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
        "SCIENTIFIC_IDENTITY_CONFLICT",
        "BLOCK_FORGE_EVIDENCE_GAP",
        "SELECTION_GATE_RECEIPT_UNUSABLE",
        "SELECTION_GATE_RECEIPT_INPUT_IDENTITY_MISMATCH",
    } or router == "BLOCK_FORGE_EVIDENCE_GAP":
        return "OBSERVABILITY_BLOCKED"
    return "INPUT_NOT_READY"


def _preflight_writes_note(body: Mapping[str, Any]) -> str:
    writes = body.get("writes") if isinstance(body.get("writes"), Mapping) else {}
    return (
        "writes: research_store={research_store} forge_context={forge_context} "
        "session={session}".format(
            research_store=int(writes.get("research_store") or 0),
            forge_context=int(writes.get("forge_context") or 0),
            session=int(writes.get("session") or 0),
        )
    )


def _preflight_owner_readout(body: Mapping[str, Any]) -> str:
    terminal = str(body.get("terminal") or "PREFLIGHT_BLOCKED")
    owner_class = str(body.get("owner_class") or "INPUT_NOT_READY")
    selection_gate = (
        body.get("selection_gate")
        if isinstance(body.get("selection_gate"), Mapping)
        else {}
    )
    selection_router = str(
        body.get("router_decision") or selection_gate.get("router_decision") or ""
    )
    selection_caveat = bool(selection_gate.get("caveat"))
    if selection_gate.get("integrity_invalid") or terminal in {
        "SELECTION_GATE_RECEIPT_UNUSABLE",
        "SELECTION_GATE_RECEIPT_INPUT_IDENTITY_MISMATCH",
    }:
        next_line = (
            "next: RESTORE_SELECTION_GATE — STOP; не создавайте trial, "
            "не сбрасывайте budget и не редактируйте receipt. Следуйте "
            "owning procedure "
            "docs/reports/hfic_selection_robustness_gate/a1_owner_readout_v1.md "
            "только после отдельной авторизации; не запускайте diagnostic "
            "в рамках A5. После восстановления повторите canonical preflight"
        )
    elif terminal == "SEARCH_BUDGET_EXHAUSTED":
        next_line = (
            "next: BUDGET_EXHAUSTED — не повторяйте тот же market/focus, "
            "не сбрасывайте budget и не создавайте новый trial; дождитесь "
            "нового market evidence или отдельного owner решения"
        )
    elif terminal == "SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING":
        next_line = (
            "next: RESTORE_SLOT_READBACK — восстановите read-only session "
            "readback; occupied slot не свободен, не создавайте новый trial "
            "и не переписывайте receipt"
        )
    elif terminal == "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING":
        next_line = (
            "next: RESOLVE_EXECUTION_BINDING — восстановите authoritative "
            "capability/model/payload readback; не перебинживайте старый "
            "результат и не создавайте новый trial"
        )
    elif terminal == "SCIENTIFIC_IDENTITY_CONFLICT":
        next_line = (
            "next: RESOLVE_IDENTITY_CONFLICT — восстановите согласованный "
            "market/representation/focus readback; не регенерируйте и не "
            "сбрасывайте budget"
        )
    elif owner_class == "OBSERVABILITY_BLOCKED":
        next_line = (
            "next: STOP_TYPED_PREFLIGHT_BLOCK — не повторяйте вход, "
            "не сбрасывайте budget и не создавайте новый trial"
        )
    elif selection_router == "BLOCK_FORGE_SELECTION_RISK" or selection_caveat:
        next_line = (
            "next: RESOLVE_SELECTION_GATE — normal entry остаётся "
            "заблокированным до разрешения selection gate; не запускайте "
            "Forge, не повторяйте trial и не трактуйте caveat как scientific "
            "negative"
        )
    elif terminal == "MARKET_EVIDENCE_BASIS_INCOMPLETE":
        next_line = (
            "next: RESTORE_CURRENT_EVIDENCE — восстановите decision-bearing "
            "datasets/lineage и повторите normal entry"
        )
    else:
        next_line = (
            "next: RESOLVE_TYPED_PREFLIGHT_BLOCK — восстановите указанный "
            "input/readback и повторите normal entry"
        )
    selection_line = (
        f"selection_router: {selection_router}\n"
        f"selection_caveat: {str(selection_caveat).lower()}\n"
        if selection_router or selection_caveat
        else ""
    )
    return (
        "PREFLIGHT\n"
        "status: BLOCKED — preflight не разрешил scientific admission; "
        "это не научный negative\n"
        f"reason: {terminal}\n"
        + selection_line
        + f"{next_line}; не создавайте trial вручную\n"
        + _preflight_writes_note(body)
    )


def cmd_preflight(
    repo_root: Path,
    *,
    owner_focus: str,
    auto_commission: bool,
    explicit_data_root: Path | None,
    control_current_representation: bool = False,
    model_provenance_sha256: str | None = None,
) -> int:
    _assert_no_path_leak(
        {
            "owner_focus": owner_focus,
            "model_provenance_sha256": model_provenance_sha256,
        },
        str(repo_root),
    )
    try:
        active = _active_root(repo_root, explicit_data_root)
        data_root = active.root
    except DataRootError as exc:
        payload = {
            "action": "STOP",
            "terminal": str(exc),
            "owner_class": "INPUT_NOT_READY",
            "owner_focus": owner_focus,
            "data_root_instance_fingerprint": None,
            "owner_readout": (
                "PREFLIGHT\n"
                "status: BLOCKED — canonical current corpus/data root unavailable; "
                "scientific admission did not start\n"
                f"reason: {exc}\n"
                "next: RESTORE_CURRENT_DATA_ROOT — restore the canonical current "
                "corpus/data root, then retry normal /hypothesis-forge; do not "
                "create a trial manually\n"
                "writes: research_store=0 forge_context=0 session=0"
            ),
        }
        _assert_no_path_leak(payload, str(repo_root))
        return emit(payload, exit_code=2)
    snap = repository_git_snapshot(repo_root)
    try:
        from solana_alpha_lab.factory.hfic_control_integrity import (
            CURRENT_REPRESENTATION_CONTROL_V1,
        )

        receipt = run_preflight(
            repo_root,
            data_root,
            owner_focus=owner_focus,
            auto_commission=auto_commission,
            commission_fn=_commission_offline if auto_commission else None,
            git_snapshot={
                "head_sha": snap.head_sha,
                "composite_sha256": snap.composite_sha256,
            },
            evidence_surface_mode=(
                CURRENT_REPRESENTATION_CONTROL_V1
                if control_current_representation
                else None
            ),
            model_provenance_sha256=model_provenance_sha256,
            persist=auto_commission,
        )
    except HficPreflightError as exc:
        payload = {
            "action": "STOP",
            "terminal": str(exc),
            "owner_class": _owner_class_for_preflight_stop({"terminal": str(exc)}),
            "owner_focus": owner_focus,
            **active.redacted_receipt(),
            "next": "RESOLVE_TYPED_PREFLIGHT_BLOCK",
            "writes": {
                "research_store": int(auto_commission),
                "forge_context": 0,
                "session": 0,
            },
        }
        payload["owner_readout"] = _preflight_owner_readout(payload)
        _assert_no_path_leak(payload, str(data_root), str(repo_root))
        return emit(payload, exit_code=2)
    payload = {
        **active.redacted_receipt(),
        **receipt,
    }
    if (
        not control_current_representation
        and payload.get("evidence_surface_mode") != "CURRENT_REPRESENTATION_CONTROL_V1"
    ):
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            DISCOVERY_CONTRACT_VERSION,
        )

        payload["discovery_contract_version"] = DISCOVERY_CONTRACT_VERSION
    if payload.get("action") == "STOP":
        payload["owner_class"] = _owner_class_for_preflight_stop(payload)
        payload["owner_readout"] = _preflight_owner_readout(payload)
    elif isinstance(payload.get("selection_gate"), Mapping) and payload["selection_gate"].get("caveat"):
        router = str(payload["selection_gate"].get("router_decision") or "UNKNOWN")
        payload["owner_readout"] = (
            "PREFLIGHT\n"
            "status: READY — normal admission may continue with a scoped "
            "selection caveat; this is not a selection-robustness claim\n"
            f"selection_router: {router}\n"
            "next: CONTINUE_WITH_SCOPED_SELECTION_CAVEAT — run the canonical "
            "forge-run no-write/readback path; do not launch a new diagnostic "
            "or treat the caveat as a scientific terminal\n"
            + _preflight_writes_note(payload)
        )
    # Stamp and readout edits are inside the receipt hash.
    payload["preflight_receipt_sha256"] = canonical_preflight_receipt_sha256(payload)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    exit_code = 0 if receipt["action"] != "STOP" else 2
    return emit(payload, exit_code=exit_code)


def cmd_forge_input(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    owner_focus: str = "AUTO",
) -> int:
    """No-write Forge input/visibility receipt. Never starts a session."""
    from solana_alpha_lab.factory.forge_input_receipt import (
        OWNER_CLASS_INPUT_NOT_READY,
        build_forge_input_receipt,
        format_forge_input_owner_block,
        forge_input_owner_next,
    )

    try:
        resolved = resolve_existing_data_root(
            repo_root, explicit_data_root=explicit_data_root
        )
    except DataRootError as exc:
        payload = {
            "schema": "smial.forge-input-receipt",
            "schema_version": "1.0",
            "owner_class": OWNER_CLASS_INPUT_NOT_READY,
            "forge_runnable": False,
            "blocking_reason_codes": [str(exc)],
            "session_id": None,
            "writes": {"research_store": 0, "forge_context": 0, "session": 0},
        }
        payload["forge_input_next"] = forge_input_owner_next(payload)
        payload["owner_forge_input"] = format_forge_input_owner_block(payload)
        _assert_no_path_leak(payload, str(repo_root))
        return emit(payload, exit_code=2)
    if resolved.status != "PRESENT" or resolved.root is None:
        payload = {
            "schema": "smial.forge-input-receipt",
            "schema_version": "1.0",
            "owner_class": OWNER_CLASS_INPUT_NOT_READY,
            "forge_runnable": False,
            "blocking_reason_codes": [resolved.error or "CURRENT_CORPUS_MISSING"],
            "session_id": None,
            "writes": {"research_store": 0, "forge_context": 0, "session": 0},
        }
        payload["forge_input_next"] = forge_input_owner_next(payload)
        payload["owner_forge_input"] = format_forge_input_owner_block(payload)
        _assert_no_path_leak(payload, str(repo_root))
        return emit(payload, exit_code=2)
    receipt = build_forge_input_receipt(
        resolved.root,
        repo_root=repo_root,
        owner_focus=owner_focus if owner_focus.strip() else "AUTO",
    )
    payload = {
        **receipt,
        "owner_forge_input": format_forge_input_owner_block(receipt),
        "forge_input_next": forge_input_owner_next(receipt),
        "session_id": None,
        "no_write": True,
        "selection_reason": resolved.selection_reason,
    }
    _assert_no_path_leak(payload, str(resolved.root), str(repo_root))
    exit_code = 0 if receipt["forge_runnable"] else 2
    return emit(payload, exit_code=exit_code)


def cmd_forge_run(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    owner_focus: str = "AUTO",
    persist: bool = False,
    saved_draft_sha256: str | None = None,
    model_provenance_sha256: str | None = None,
    control_current_representation: bool = False,
) -> int:
    """Bounded Forge run receipt. persist=False never writes."""
    from solana_alpha_lab.factory.hfic_representation_ladder import (
        LadderError,
        evaluate_forge_run,
        format_forge_run_owner_readout,
    )

    def _emit_run(payload: dict[str, Any], *, exit_code: int) -> int:
        existing = str(payload.get("owner_readout") or "")
        history = next(
            (line for line in existing.splitlines() if line.startswith("history:")),
            "",
        )
        if payload.get("no_write") is True or not existing:
            payload["owner_readout"] = format_forge_run_owner_readout(payload)
        if history and "history:" not in str(payload.get("owner_readout") or ""):
            payload["owner_readout"] = str(payload.get("owner_readout") or "").rstrip() + "\n" + history
        _assert_no_path_leak(payload, str(repo_root))
        readout = payload.get("owner_readout")
        if isinstance(readout, str) and readout.strip():
            print(readout, file=sys.stderr)
        return emit(payload, exit_code=exit_code)

    from solana_alpha_lab.factory.run_passport import canonical_sha256

    def _blocked_run_payload(code: str, owner_class: str) -> dict[str, Any]:
        run_identity = canonical_sha256(
            {"kind": "FORGE_RUN_BLOCKED", "owner_class": owner_class, "code": code}
        )
        body: dict[str, Any] = {
            "schema": "smial.forge-run-receipt",
            "schema_version": "1.0",
            "run_id": f"HFIC-RUN-BLOCKED-{run_identity[:16].upper()}",
            "run_identity_sha256": run_identity,
            "owner_focus": owner_focus if owner_focus.strip() else "AUTO",
            "owner_class": owner_class,
            "next_action": owner_class,
            "owner_final": owner_class,
            "input_receipt_sha256": None,
            "visible_cohort_ids": [],
            "frozen_representation_ids": ["BASE"],
            "stages": [],
            "legacy_epoch_sha256": None,
            "blocking_reason_codes": [code],
            "writes": {"research_store": 0, "forge_run": 0, "session": 0},
        }
        body["receipt_sha256"] = canonical_sha256(body)
        return body

    def _ladder_error_payload(code: str) -> dict[str, Any]:
        input_codes = {
            "MARKET_EVIDENCE_BASIS_INCOMPLETE",
            "CURRENT_CORPUS_MISSING",
            "CAPABILITY_PROTOCOL_SURFACE_INCOMPLETE",
            "CAPABILITY_SEMANTIC_SURFACE_INCOMPLETE",
            "CAPABILITY_IDENTITY_UNAVAILABLE",
        }
        owner_class = "INPUT_NOT_READY" if code in input_codes else "OBSERVABILITY_BLOCKED"
        return _blocked_run_payload(code, owner_class)

    execution_context = (
        {"model_provenance_sha256": model_provenance_sha256}
        if model_provenance_sha256
        else None
    )

    try:
        resolved = resolve_existing_data_root(
            repo_root, explicit_data_root=explicit_data_root
        )
    except DataRootError as exc:
        reason = str(exc)
        payload = _blocked_run_payload(reason, "INPUT_NOT_READY")
        payload["owner_readout"] = (
            "FORGE RUN\n"
            "status: BLOCKED — current corpus/data root unavailable; no scientific admission\n"
            f"blocking: {reason}\n"
            "NEXT — restore the canonical current corpus/data root, then retry /hypothesis-forge\n"
            "writes: store=0 forge_run=0 session=0"
        )
        return _emit_run(payload, exit_code=2)
    if resolved.status != "PRESENT" or resolved.root is None:
        reason = resolved.error or "CURRENT_CORPUS_MISSING"
        payload = _blocked_run_payload(reason, "INPUT_NOT_READY")
        payload["owner_readout"] = (
            "FORGE RUN\n"
            "status: BLOCKED — current corpus/data root unavailable; no scientific admission\n"
            f"blocking: {reason}\n"
            "NEXT — restore/import the canonical current corpus, then retry /hypothesis-forge\n"
            "writes: store=0 forge_run=0 session=0"
        )
        return _emit_run(payload, exit_code=2)
    from solana_alpha_lab.factory.hfic_control_integrity import (
        CURRENT_REPRESENTATION_CONTROL_V1,
    )

    requested_surface = (
        CURRENT_REPRESENTATION_CONTROL_V1
        if control_current_representation
        else None
    )
    try:
        receipt = evaluate_forge_run(
            repo_root,
            resolved.root,
            owner_focus=owner_focus if owner_focus.strip() else "AUTO",
            persist=False,
            saved_draft_sha256=saved_draft_sha256,
            execution_context=execution_context,
            requested_surface=requested_surface,
        )
    except LadderError as exc:
        payload = _ladder_error_payload(str(exc))
        from solana_alpha_lab.factory.hfic_ordinary_operation import project_ordinary_operation
        from solana_alpha_lab.factory.research_store import ResearchStore

        if resolved.status == "PRESENT" and resolved.root is not None:
            try:
                projection = project_ordinary_operation(
                    ResearchStore(resolved.root, create_if_missing=False),
                    owner_focus=owner_focus if owner_focus.strip() else "AUTO",
                )
            except Exception:
                projection = None
            if projection is not None:
                payload["ordinary_operation"] = projection
        payload["owner_readout"] = format_forge_run_owner_readout(payload)
        return _emit_run(payload, exit_code=2)
    payload = {**receipt, "no_write": not persist, "selection_reason": resolved.selection_reason}
    from solana_alpha_lab.factory.hfic_representation_ladder import (
        attach_ladder_freeze_preflight,
    )
    from solana_alpha_lab.factory.research_store import ResearchStore

    store = ResearchStore(resolved.root, create_if_missing=False)
    payload = attach_ladder_freeze_preflight(
        payload,
        data_root=resolved.root,
        store=store,
        execution_context=execution_context,
    )
    if persist and payload.get("owner_class") not in {
        "INPUT_NOT_READY",
        "OBSERVABILITY_BLOCKED",
    }:
        try:
            receipt = evaluate_forge_run(
                repo_root,
                resolved.root,
                owner_focus=owner_focus if owner_focus.strip() else "AUTO",
                persist=True,
                saved_draft_sha256=saved_draft_sha256,
                execution_context=execution_context,
                requested_surface=requested_surface,
            )
        except LadderError as exc:
            payload = _ladder_error_payload(str(exc))
            payload["owner_readout"] = format_forge_run_owner_readout(payload)
            return _emit_run(payload, exit_code=2)
        payload = {**receipt, "no_write": False, "selection_reason": resolved.selection_reason}
        payload = attach_ladder_freeze_preflight(
            payload,
            data_root=resolved.root,
            store=store,
            execution_context=execution_context,
        )
    from solana_alpha_lab.factory.hfic_ordinary_operation import (
        merge_ordinary_readout,
        project_ordinary_operation,
    )

    projection = project_ordinary_operation(
        store,
        owner_focus=owner_focus if owner_focus.strip() else "AUTO",
    )
    payload = merge_ordinary_readout(payload, projection)
    _assert_no_path_leak(payload, str(resolved.root), str(repo_root))
    return _emit_run(payload, exit_code=(
        0 if payload.get("owner_class") not in {"INPUT_NOT_READY", "OBSERVABILITY_BLOCKED"} else 2
    ))


def cmd_discovery_binding(repo_root: Path, explicit_data_root: Path | None) -> int:
    """No-write admission binding for the published discovery corpus."""

    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        GroundedDiscoveryError,
        resolve_published_discovery_binding,
    )

    git_before = repository_git_snapshot(repo_root)
    try:
        data_root = _existing_data_root(repo_root, explicit_data_root)
    except HficCliError as exc:
        return emit_error(str(exc))
    try:
        payload = resolve_published_discovery_binding(data_root)
    except GroundedDiscoveryError as exc:
        return emit_error(exc.code)
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        return emit_error("GIT_MUTATION_DETECTED")
    payload["scientific_writes"] = 0
    payload["values_loaded"] = False
    payload["authority"] = {
        "git_mutation": 0,
        "experiment_execution": 0,
        "provider_api_rpc_wss_calls": 0,
    }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_discovery_execute(
    repo_root: Path,
    *,
    store_root: Path,
    census_path: Path | None,
    observations_path: Path | None,
    binding_path: Path | None,
    spec_path: Path,
    journal_scope: str,
    candidate_scope_path: Path,
    cohort_partitions: list[tuple[str, Path, Path]] | None = None,
    explicit_data_root: Path | None = None,
    operation_path: Path | None = None,
    operation_sha256: str | None = None,
    correct_result_ref: str | None = None,
    correct_result_sha256: str | None = None,
) -> int:
    """Compute one ordinary discovery query into a caller-selected store.

    Does not default to the live ResearchStore and does not reserve a slot.
    Omitting ``--binding`` resolves the published corpus at ``--data-root``.
    ``--correct-result-ref`` with ``--correct-result-sha256`` writes one
    CALCULATION_REVISION of that saved result; it spends no look.
    """

    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        GroundedDiscoveryError,
        list_discovery_looks,
        load_admitted_partition_rows,
        run_recorded_discovery_query,
    )

    git_before = repository_git_snapshot(repo_root)
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        candidate_scope = json.loads(candidate_scope_path.read_text(encoding="utf-8"))
        binding_doc = None
        if binding_path is not None:
            binding_doc = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return emit_error("DISCOVERY_INPUT_INVALID")
    if not isinstance(spec, dict) or not isinstance(candidate_scope, dict):
        return emit_error("DISCOVERY_INPUT_INVALID")
    if binding_doc is not None and not isinstance(binding_doc, dict):
        return emit_error("DISCOVERY_INPUT_INVALID")
    from solana_alpha_lab.factory.hfic_ordinary_operation import (
        OrdinaryOperationError,
        gate_before_values,
        get_operation,
        list_operations,
        note_look_landed,
        record_operation,
    )
    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query
    from solana_alpha_lab.factory.research_store import ResearchStore

    try:
        validate_temporal_query(spec)
        temporal_query = True
    except Exception:
        temporal_query = False
    if spec.get("schema") == "smial.hfic-temporal-query" and not temporal_query:
        return emit(
            {
                "reason_code": "QUERY_SPEC_INVALID",
                "values_loaded": False,
                "writes": False,
                "scientific_negative": False,
            },
            exit_code=2,
        )
    if temporal_query and operation_path is None and not operation_sha256:
        return emit(
            {"reason_code": "ORDINARY_OPERATION_REQUIRED", "values_loaded": False, "writes": False},
            exit_code=2,
        )
    correction: dict[str, str] | None = None
    if correct_result_ref or correct_result_sha256:
        if not (correct_result_ref and correct_result_sha256):
            return emit(
                {"reason_code": "CALCULATION_REVISION_SOURCE_REQUIRED", "values_loaded": False, "writes": False},
                exit_code=2,
            )
        if not temporal_query:
            return emit(
                {"reason_code": "CALCULATION_REVISION_UNSUPPORTED", "values_loaded": False, "writes": False},
                exit_code=2,
            )
        correction = {
            "source_result_ref": str(correct_result_ref),
            "source_result_sha256": str(correct_result_sha256),
        }
    gate: dict[str, object] = {"disposition": "EXECUTE"}
    if temporal_query:
        from solana_alpha_lab.factory.hfic_evidence_identity import (
            EvidenceIdentityError,
            compute_market_epoch_for_data_root,
        )

        values_follow_data_root = explicit_data_root is not None and census_path is None and observations_path is None and not cohort_partitions
        corpus_candidates = []
        for root in (store_root, explicit_data_root):
            if root is None or root in corpus_candidates:
                continue
            corpus_candidates.append(root)
        epochs: list[str] = []
        for root in corpus_candidates:
            try:
                found, _basis = compute_market_epoch_for_data_root(repo_root, root)
            except EvidenceIdentityError:
                if _published_file_hash_mismatch(root):
                    return emit_error("BINDING_HASH_MISMATCH")
                if values_follow_data_root and root == explicit_data_root:
                    return emit(
                        {
                            "reason_code": "MARKET_EVIDENCE_BASIS_INCOMPLETE",
                            "values_loaded": False,
                            "writes": False,
                            "scientific_negative": False,
                        },
                        exit_code=2,
                    )
                continue
            if found not in epochs:
                epochs.append(found)
        if not epochs:
            return emit(
                {
                    "reason_code": "MARKET_EVIDENCE_BASIS_INCOMPLETE",
                    "values_loaded": False,
                    "writes": False,
                    "scientific_negative": False,
                },
                exit_code=2,
            )
        if len(epochs) > 1:
            return emit(
                {
                    "reason_code": "ORDINARY_OPERATION_MARKET_MISMATCH",
                    "values_loaded": False,
                    "writes": False,
                    "scientific_negative": False,
                },
                exit_code=2,
            )
        epoch = epochs[0]
        claimed_market = ""
        service_writes = 0
        if operation_path is not None:
            try:
                preview_request = json.loads(operation_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                return emit_error("DISCOVERY_INPUT_INVALID")
            if isinstance(preview_request, dict):
                claimed_market = str(preview_request.get("market_evidence_epoch_sha256") or "")
        if claimed_market and claimed_market != epoch:
            for root in corpus_candidates:
                if _published_file_hash_mismatch(root):
                    return emit_error("BINDING_HASH_MISMATCH")
            return emit(
                {
                    "reason_code": "ORDINARY_OPERATION_MARKET_MISMATCH",
                    "values_loaded": False,
                    "writes": False,
                    "scientific_negative": False,
                },
                exit_code=2,
            )
        op_store = ResearchStore(store_root)
        try:
            if operation_path is not None:
                request = preview_request
                if not isinstance(request, dict):
                    raise OrdinaryOperationError("ORDINARY_OPERATION_REQUEST_REQUIRED")
                before_records = len(list_operations(op_store))
                operation = record_operation(op_store, request)
                service_writes = int(len(list_operations(op_store)) > before_records)
                operation_sha256 = str(operation.get("operation_sha256") or "")
            elif claimed_market == "":
                existing = get_operation(op_store, str(operation_sha256))
                if str(existing.get("market_evidence_epoch_sha256") or "") != epoch:
                    return emit(
                        {
                            "reason_code": "ORDINARY_OPERATION_MARKET_MISMATCH",
                            "values_loaded": False,
                            "writes": False,
                            "scientific_negative": False,
                        },
                        exit_code=2,
                    )
            cohorts = []
            if isinstance(binding_doc, dict):
                cohorts = list(binding_doc.get("cohorts") or [])
            elif explicit_data_root is not None:
                from solana_alpha_lab.factory.hfic_grounded_discovery import (
                    resolve_published_discovery_binding,
                )

                try:
                    published = resolve_published_discovery_binding(explicit_data_root)
                    cohorts = list(published.get("cohorts") or [])
                except Exception:
                    cohorts = []
            gate = gate_before_values(
                op_store,
                operation_sha256=str(operation_sha256),
                spec=spec,
                journal_scope=journal_scope,
                binding_cohorts=cohorts,
                verified_market=epoch,
                repo_root=repo_root,
                data_root=store_root or explicit_data_root,
                correction=correction,
            )
        except OrdinaryOperationError as exc:
            return emit(
                {
                    "reason_code": exc.code,
                    "values_loaded": False,
                    "writes": bool(service_writes) or gate.get("disposition") == "RESERVED",
                    "scientific_negative": False,
                },
                exit_code=2,
            )
    if gate.get("disposition") == "REPLAY":
        readout = gate.get("result_readout") if isinstance(gate.get("result_readout"), dict) else None
        if readout is not None and readout.get("result_coherence") != "COHERENT":
            # Matching hashes do not make an inconsistent summary evidence.
            stop = _saved_result_stop("TEMPORAL_RESULT_INCOHERENT", readout, values_loaded=False)
            stop["operation_sha256"] = (gate.get("operation") or {}).get("operation_sha256")
            _assert_no_path_leak(stop, str(store_root), str(repo_root))
            return emit(stop, exit_code=2)
        evidence = dict(gate.get("evidence") or {})
        evidence["values_loaded"] = False
        evidence["writes"] = False
        evidence["scientific_negative"] = False
        if operation_sha256:
            evidence["ordinary_operation"] = note_look_landed(op_store, str(operation_sha256)).get("status")
        evidence["operation_sha256"] = (gate.get("operation") or {}).get("operation_sha256")
        _assert_no_path_leak(evidence, str(store_root), str(repo_root))
        return emit(evidence)
    data_root = explicit_data_root
    try:
        loaded = load_admitted_partition_rows(
            data_root=data_root,
            binding_doc=binding_doc,
            partitions=cohort_partitions,
            census_path=census_path,
            observations_path=observations_path,
        )
    except GroundedDiscoveryError as exc:
        return emit_error(exc.code)
    except (OSError, ValueError):
        return emit_error("DISCOVERY_ROWS_UNREADABLE")
    store = ResearchStore(store_root)
    priors = []
    if isinstance(binding_doc, dict):
        priors = binding_doc.get("priors") or []
    counts_before = _look_counts(store, journal_scope) if temporal_query else None
    inventory_before = store.diagnostics().committed_inventory_sha256 if temporal_query else None
    try:
        evidence = run_recorded_discovery_query(
            store,
            census=loaded["census"],
            observations=loaded["observations"],
            spec=spec,
            binding=loaded["cohorts"],
            journal_scope=journal_scope,
            candidate_scope=candidate_scope,
            priors=priors,
            git_sha=git_before.head_sha,
            operation_sha256=str(operation_sha256) if operation_sha256 else None,
            verified_market=epoch if temporal_query else None,
            correction=correction,
        )
    except GroundedDiscoveryError as exc:
        if temporal_query and (
            exc.code == "TEMPORAL_RESULT_INCOHERENT" or exc.code.startswith("CALCULATION_REVISION_")
        ):
            from solana_alpha_lab.factory.hfic_ordinary_operation import (
                _operation_result,
                result_readout,
            )
            from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query as _validate

            saved = _operation_result(
                list_discovery_looks(store, journal_scope),
                str(operation_sha256 or ""),
                _validate(spec)["spec_sha256"],
            )
            readout = result_readout(saved) if saved is not None else None
            if readout is not None and readout.get("result_coherence") == "COHERENT":
                # The stop is about this computation, not the saved result.
                readout = None
            stop = _saved_result_stop(exc.code, readout, values_loaded=True)
            if exc.code == "TEMPORAL_RESULT_INCOHERENT" and readout is None:
                stop.pop("repair_action", None)
                stop.pop("next_action", None)
            stop["writes"] = store.diagnostics().committed_inventory_sha256 != inventory_before
            _assert_no_path_leak(stop, str(store_root), str(repo_root))
            return emit(stop, exit_code=2)
        return emit_error(exc.code)
    git_after = repository_git_snapshot(repo_root)
    if git_before.head_sha != git_after.head_sha:
        return emit_error("GIT_MUTATION_FORBIDDEN")
    evidence["scientific_writes"] = 0
    if temporal_query:
        query_rows = evidence.get("queries") if isinstance(evidence.get("queries"), list) else []
        first_query = query_rows[0] if query_rows and isinstance(query_rows[0], dict) else {}
        counts_after = _look_counts(store, journal_scope)
        record_delta = counts_after["records"] - int((counts_before or {}).get("records") or 0)
        evidence["writes"] = bool(service_writes) or bool(first_query.get("new_look")) or record_delta > 0
        evidence["record_delta"] = {"discovery_look_records": record_delta}
        evidence["scientific_look_delta"] = {
            "main": counts_after["main"] - int((counts_before or {}).get("main") or 0),
            "adaptive": counts_after["adaptive"] - int((counts_before or {}).get("adaptive") or 0),
        }
    evidence["live_store_selected"] = False
    evidence["duplicate_partitions_eliminated"] = loaded["duplicate_partitions_eliminated"]
    evidence["authority_source"] = (loaded["binding"] or {}).get("authority_source")
    evidence["values_loaded"] = True
    if operation_sha256:
        evidence["ordinary_operation"] = note_look_landed(op_store, str(operation_sha256)).get("status")
    _assert_no_path_leak(evidence, str(store_root), str(repo_root))
    if data_root is not None:
        _assert_no_path_leak(evidence, str(data_root))
    return emit(evidence)


def cmd_discovery_preview(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    spec_path: Path,
    binding_path: Path | None,
    census_path: Path | None,
    observations_path: Path | None,
    cohort_partitions: list[tuple[str, Path, Path]] | None,
    prior_preview_hash: list[str] | None,
    store_root: Path | None = None,
    journal_scope: str | None = None,
    operation_path: Path | None = None,
    operation_sha256: str | None = None,
) -> int:
    """Feature-only preview. Store memory is written only when store and journal are both set."""

    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        GroundedDiscoveryError,
        load_admitted_partition_rows,
    )
    from solana_alpha_lab.factory.hfic_temporal_discovery import build_feature_preview

    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        binding_doc = None
        if binding_path is not None:
            binding_doc = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return emit_error("DISCOVERY_INPUT_INVALID")
    if not isinstance(spec, dict):
        return emit_error("DISCOVERY_INPUT_INVALID")
    if binding_doc is not None and not isinstance(binding_doc, dict):
        return emit_error("DISCOVERY_INPUT_INVALID")
    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query

    try:
        validate_temporal_query(spec)
        temporal_preview = True
    except Exception:
        temporal_preview = False
    if spec.get("schema") == "smial.hfic-temporal-query" and not temporal_preview:
        return emit(
            {
                "reason_code": "QUERY_SPEC_INVALID",
                "values_loaded": False,
                "writes": False,
                "scientific_negative": False,
            },
            exit_code=2,
        )
    if temporal_preview and (
        store_root is None
        or not journal_scope
        or (operation_path is None and not operation_sha256)
    ):
        return emit(
            {
                "reason_code": "ORDINARY_OPERATION_REQUIRED",
                "values_loaded": False,
                "writes": False,
                "scientific_negative": False,
            },
            exit_code=2,
        )
    preview_service_writes = 0
    preview_store = None
    if store_root is not None and journal_scope:
        from solana_alpha_lab.factory.hfic_evidence_identity import (
            EvidenceIdentityError,
            compute_market_epoch_for_data_root,
        )
        from solana_alpha_lab.factory.hfic_ordinary_operation import (
            OrdinaryOperationError,
            authorize_temporal_attempt,
            get_operation,
            list_operations,
            owner_allowance,
            record_operation,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore

        if operation_path is None and not operation_sha256:
            return emit(
                {"reason_code": "ORDINARY_OPERATION_REQUIRED", "values_loaded": False, "writes": False},
                exit_code=2,
            )
        preview_store = ResearchStore(store_root, create_if_missing=False)
        try:
            if operation_path is not None:
                request = json.loads(operation_path.read_text(encoding="utf-8"))
                before_records = len(list_operations(preview_store))
                operation = record_operation(preview_store, request)
                preview_service_writes = int(len(list_operations(preview_store)) > before_records)
                operation_sha256 = str(operation.get("operation_sha256") or "")
            else:
                operation = get_operation(preview_store, str(operation_sha256))
            if str(operation.get("journal_scope") or "") != journal_scope:
                raise OrdinaryOperationError("ORDINARY_OPERATION_JOURNAL_MISMATCH")
            from solana_alpha_lab.factory.hfic_ordinary_operation import (
                _canonical as _op_canonical,
                _feature_previews,
                owner_allowance,
            )

            preview_spec_sha = hashlib.sha256(_op_canonical(dict(spec)).encode("utf-8")).hexdigest()
            already_owned = any(
                item.get("operation_sha256") == operation.get("operation_sha256")
                and item.get("spec_sha256") == preview_spec_sha
                for item in _feature_previews(preview_store, journal_scope)
            )
            if not already_owned and owner_allowance(preview_store, operation, "preview") < 1:
                raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED")
            epochs: list[str] = []
            if explicit_data_root is not None:
                try:
                    found, _basis = compute_market_epoch_for_data_root(
                        repo_root, explicit_data_root
                    )
                    epochs.append(found)
                except EvidenceIdentityError:
                    if _published_file_hash_mismatch(explicit_data_root):
                        return emit_error("BINDING_HASH_MISMATCH")
                    return emit(
                        {
                            "reason_code": "MARKET_EVIDENCE_BASIS_INCOMPLETE",
                            "values_loaded": False,
                            "writes": bool(preview_service_writes),
                            "scientific_negative": False,
                        },
                        exit_code=2,
                    )
            if not epochs:
                return emit(
                    {
                        "reason_code": "MARKET_EVIDENCE_BASIS_INCOMPLETE",
                        "values_loaded": False,
                        "writes": bool(preview_service_writes),
                        "scientific_negative": False,
                    },
                    exit_code=2,
                )
            epoch = epochs[0]
            binding_cohorts: list[dict[str, Any]] = []
            if binding_doc is not None and isinstance(binding_doc, dict):
                binding_cohorts = list(binding_doc.get("cohorts") or [])
            elif explicit_data_root is not None:
                from solana_alpha_lab.factory.hfic_grounded_discovery import (
                    resolve_published_discovery_binding,
                )

                try:
                    binding_cohorts = list(
                        resolve_published_discovery_binding(explicit_data_root).get("cohorts")
                        or []
                    )
                except Exception:
                    binding_cohorts = []
            preview_gate = authorize_temporal_attempt(
                preview_store,
                operation_sha256=str(operation_sha256),
                spec=spec,
                journal_scope=journal_scope,
                binding_cohorts=binding_cohorts,
                verified_market=epoch,
                look_kind="preview",
                repo_root=repo_root,
                data_root=store_root or explicit_data_root,
            )
            if isinstance(preview_gate, dict) and preview_gate.get("disposition") == "REPLAY":
                return emit(
                    {
                        "disposition": "REPLAY",
                        "preview_sha256": preview_gate.get("preview_sha256"),
                        "replayed_without_loader": True,
                        "values_loaded": False,
                        "writes": bool(preview_service_writes),
                        "scientific_negative": False,
                    }
                )
        except OrdinaryOperationError as exc:
            return emit(
                {
                    "reason_code": exc.code,
                    "values_loaded": False,
                    "writes": bool(preview_service_writes),
                    "scientific_negative": False,
                },
                exit_code=2,
            )
    try:
        loaded = load_admitted_partition_rows(
            data_root=explicit_data_root,
            binding_doc=binding_doc,
            partitions=cohort_partitions,
            census_path=census_path,
            observations_path=observations_path,
        )
        if (store_root is None) != (not journal_scope):
            return emit_error("PREVIEW_STORE_SCOPE_REQUIRED")
        remembered = list(prior_preview_hash or [])
        if store_root is not None and journal_scope:
            from solana_alpha_lab.factory.hfic_temporal_discovery import stored_preview_hashes
            from solana_alpha_lab.factory.research_store import ResearchStore

            remembered = stored_preview_hashes(ResearchStore(store_root), journal_scope)
        payload = build_feature_preview(
            loaded["census"],
            loaded["observations"],
            spec,
            loaded["cohorts"],
            prior_preview_hashes=remembered,
        )
        if store_root is not None and journal_scope:
            from solana_alpha_lab.factory.hfic_temporal_discovery import persist_feature_preview
            from solana_alpha_lab.factory.research_store import ResearchStore

            input_identity = hashlib.sha256(
                json.dumps(
                    [
                        (
                            str(item.get("cohort_id")),
                            str(item.get("release_id")),
                            str(item.get("observations_sha256")),
                        )
                        for item in loaded["cohorts"]
                    ],
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            from solana_alpha_lab.factory.hfic_ordinary_operation import _canonical as _op_canonical

            persisted_spec = hashlib.sha256(_op_canonical(dict(spec)).encode("utf-8")).hexdigest()
            persist_feature_preview(
                ResearchStore(store_root),
                journal_scope=journal_scope,
                preview=payload,
                git_sha="0" * 40,
                input_sha256=input_identity,
                operation_sha256=str(operation_sha256) if operation_sha256 else None,
                spec_sha256=persisted_spec or None,
            )
    except GroundedDiscoveryError as exc:
        return emit_error(exc.code)
    except (OSError, ValueError):
        return emit_error("DISCOVERY_ROWS_UNREADABLE")
    payload["values_are_features_only"] = True
    payload["scientific_writes"] = 0
    _assert_no_path_leak(payload, str(repo_root))
    if explicit_data_root is not None:
        _assert_no_path_leak(payload, str(explicit_data_root))
    return emit(payload)


def cmd_discovery_coverage(repo_root: Path, explicit_data_root: Path | None) -> int:
    """State-only joint coverage. Writes nothing and does not reserve a slot."""

    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        GroundedDiscoveryError,
        live_state_only_coverage,
    )

    git_before = repository_git_snapshot(repo_root)
    try:
        data_root = _existing_data_root(repo_root, explicit_data_root)
    except HficCliError as exc:
        return emit_error(str(exc))
    try:
        payload = live_state_only_coverage(data_root)
    except GroundedDiscoveryError as exc:
        return emit_error(exc.code)
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        return emit_error("GIT_MUTATION_DETECTED")
    payload["authority"] = {
        "git_mutation": 0,
        "experiment_execution": 0,
        "provider_api_rpc_wss_calls": 0,
    }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def _store_root(repo_root: Path, explicit_data_root: Path | None) -> Path:
    return _active_root(repo_root, explicit_data_root).root


def _existing_data_root(repo_root: Path, explicit_data_root: Path | None) -> Path:
    resolved = resolve_existing_data_root(repo_root, explicit_data_root=explicit_data_root)
    if resolved.status != "PRESENT" or resolved.root is None:
        raise HficCliError(resolved.error or "RESEARCH_STORE_NOT_PRESENT")
    return resolved.root


def cmd_memory_policy_status(
    repo_root: Path,
    explicit_data_root: Path | None,
) -> int:
    data_root = _existing_data_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    payload = memory_policy_status(store, repo_root=repo_root)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_memory_policy_preview(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    quarantine_session_ids: list[str],
    restore_session_ids: list[str],
    quarantine_all_current_hfic: bool,
    reason_code: str,
) -> int:
    data_root = _existing_data_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    payload = preview_memory_policy(
        store,
        repo_root=repo_root,
        quarantine_session_ids=quarantine_session_ids,
        restore_session_ids=restore_session_ids,
        quarantine_all_current_hfic=quarantine_all_current_hfic,
        reason_code=reason_code,
    )
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_memory_policy_apply(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    proposal_path: Path,
    confirm_append_only: bool,
) -> int:
    data_root = _existing_data_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    proposal = _load_json_file(proposal_path)
    nested = proposal.get("proposal")
    body = nested if isinstance(nested, dict) else proposal
    payload = apply_memory_policy(
        store,
        repo_root=repo_root,
        proposal=body,
        confirm_append_only=confirm_append_only,
    )
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_preview_reopened_prior_routing(
    repo_root: Path,
    explicit_data_root: Path | None,
) -> int:
    data_root = _existing_data_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    payload = preview_control_reconsideration(
        store,
        repo_root,
        data_root=data_root,
        defective_session_id=DEFECTIVE_CONTROL_SESSION_ID,
    )
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    exit_code = 0 if payload.get("terminal") == (
        "CONTROL_RECONSIDERATION_READY_AFTER_COMMISSION"
    ) else 2
    return emit(payload, exit_code=exit_code)


FORGE_VISION_BLOCKED_CODE = "FORGE_VISION_INTEGRITY_BLOCKED"
INVALID_PROJECTION_CODE = "INVALID_PROJECTION_PROVENANCE"


def cmd_vision_acceptance(
    repo_root: Path,
    explicit_data_root: Path | None,
    *,
    release_root: Path | None = None,
) -> int:
    """Read-only FORGE_VISION_ACCEPTANCE machine evidence aggregate."""
    from solana_alpha_lab.factory.hfic_control_integrity import (
        control_packet_has_raw_sequences,
    )
    from solana_alpha_lab.factory.hfic_control_integrity import (
        CURRENT_REPRESENTATION_CONTROL_V1,
    )
    from solana_alpha_lab.factory.run_passport import canonical_json_bytes
    from solana_alpha_lab.factory.hfic_preflight import (
        FORGE_OPERATIONAL_PACKET_MAX_BYTES,
        FORGE_PACKET_GROWTH_WARNING_BYTES,
        build_forge_context_packet,
        enumerate_rdp_datasets,
    )
    from solana_alpha_lab.factory.hfic_reopened_prior_routing import (
        DEFECTIVE_CONTROL_SESSION_ID,
        overlay_search_payloads,
        preview_control_reconsideration,
        resolve_all_reopened_priors,
    )
    from solana_alpha_lab.factory.hfic_suppression_semantics import (
        enumerate_closed_park_terminals_with_authority,
    )
    from solana_alpha_lab.factory.hfic_vision_integrity import (
        compute_vision_integrity,
    )
    from solana_alpha_lab.factory.live_cohort_discovery_release import (
        CORPUS_DATASET_ID,
    )
    from solana_alpha_lab.factory.hfic_control_integrity import (
        resolve_control_corpus_yield,
    )
    from solana_alpha_lab.factory import hfic_released_trajectory_projection

    data_root = _existing_data_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    evidence: dict[str, Any] = {"schema": "smial.hfic-vision-acceptance", "schema_version": "1.0"}

    # SUPPRESSION
    ledger = enumerate_closed_park_terminals_with_authority(
        repo_root, data_root
    )
    hard_family = [
        item
        for item in ledger
        if item.get("reopen_forbidden") is True and item.get("scope_kind") == "FAMILY"
    ]
    unauthorized = [
        item["terminal"]
        for item in hard_family
        if (item.get("family_close_authority") or {}).get("class") != "POSITIVE"
    ]
    ambiguous_hard = [
        item["terminal"]
        for item in ledger
        if str(item.get("suppression_class") or "").startswith("AMBIGUOUS")
        and item.get("reopen_forbidden") is True
    ]
    parks_hard = [
        item["terminal"]
        for item in ledger
        if str(item.get("suppression_class") or "") == "OWNER_PRIORITY_PARK"
        and item.get("reopen_forbidden") is True
    ]
    scope_widened = [
        item["terminal"]
        for item in ledger
        if str(item.get("suppression_class") or "") == "SCOPE_LIMITED_CLOSE"
        and item.get("scope_kind") == "FAMILY"
    ]
    evidence["suppression"] = {
        "family_hard_closes": len(hard_family),
        "reopen_forbidden_by_scope": {
            kind: sum(
                1
                for item in ledger
                if item.get("reopen_forbidden") is True
                and str(item.get("scope_kind") or "") == kind
            )
            for kind in sorted(
                {
                    str(item.get("scope_kind") or "")
                    for item in ledger
                    if item.get("reopen_forbidden") is True
                }
            )
        },
        "not_portable_acting_as_hard_close": len(unauthorized),
        "ambiguous_acting_as_hard_close": len(ambiguous_hard),
        "parks_acting_as_hard_close": len(parks_hard),
        "scope_overclosure": len(scope_widened),
        "terminals": {
            str(item.get("terminal")): {
                "scope_kind": item.get("scope_kind"),
                "reopen_forbidden": item.get("reopen_forbidden"),
                "authority": (item.get("family_close_authority") or {}).get("class"),
                "source": item.get("source_receipt"),
            }
            for item in ledger
        },
    }

    # CALIBRATION / POST-STATE
    preview = preview_control_reconsideration(
        store,
        repo_root,
        data_root=data_root,
        defective_session_id=DEFECTIVE_CONTROL_SESSION_ID,
    )
    trunc = preview.get("POST_PLAN_TRUNCATION") or {}
    ranked_count = len(preview.get("POST_PLAN_RANKING") or [])
    bodies = list(preview.get("POST_PLAN_PRIOR_BODIES") or [])
    evidence["priors"] = {
        "h11_visible_body_ranked": preview.get("H11_IN_PROMPT_A_SET") is True,
        "h13_visible_body_ranked": preview.get("H13_IN_PROMPT_A_SET") is True,
        "ranked_body_mismatch": abs(ranked_count - len(bodies)),
        "dropped_material_priors": int(trunc.get("dropped_priors") or 0),
        "prior_bodies": bodies,
        "basis": "planned_post_commission_overlay",
    }
    current_memory = preview.get("CURRENT_SEARCH_MEMORY") or {}
    evidence["calibration"] = {
        "defective_session": DEFECTIVE_CONTROL_SESSION_ID,
        "planned_exact_session_quarantine": [DEFECTIVE_CONTROL_SESSION_ID],
        "planned_terminal": preview.get("terminal"),
        "quarantine_removes_calibration_hfic": True,
        "commission_applied": bool(
            current_memory.get("h11") and current_memory.get("h13")
        ),
        "store_h11_present": current_memory.get("h11") is True,
        "store_h13_present": current_memory.get("h13") is True,
    }

    # FEATURE/CAPABILITY VISION + PACKET + CONTROL
    datasets, _warnings = enumerate_rdp_datasets(data_root)
    gate, yield_eligible = resolve_control_corpus_yield(
        datasets,
        corpus_dataset_id=CORPUS_DATASET_ID,
        min_usable_yield_eligible=0,
    )
    extras = [item["payload"] for item in resolve_all_reopened_priors(repo_root)]
    planned = overlay_search_payloads(
        store, extras, [DEFECTIVE_CONTROL_SESSION_ID]
    )
    try:
        ctx_packet, _digest = build_forge_context_packet(
            repo_root,
            data_root,
            owner_focus=str(preview.get("owner_focus") or "AUTO"),
            evidence_epoch=str(
                preview.get("PLANNED_NEW_EVIDENCE_EPOCH") or ("aa" * 32)
            ),
            search_key=str(preview.get("PLANNED_NEW_EVIDENCE_EPOCH") or ("bb" * 32)),
            commissioning_status="FAST_LANE_COMMISSIONED",
            research_memory_as_of=str(
                preview.get("research_memory_as_of") or "2026-09-15T00:00:00Z"
            ),
            store=store,
            persist=False,
            search_payloads=planned,
            evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
        )
        vision = ctx_packet.get("vision_integrity") or {}
        packet_bytes = len(canonical_json_bytes(ctx_packet))
        control_ok = {
            # Single positive field: raw trajectory leak is blocked (i.e.
            # preview fence CONTROL_TRAJECTORY_BLIND_FENCE is True).
            "trajectory_blind": preview.get("CONTROL_TRAJECTORY_BLIND_FENCE")
            is True,
            "packet_bytes": packet_bytes,
            "packet_within_bound": packet_bytes <= FORGE_OPERATIONAL_PACKET_MAX_BYTES,
            "growth_warning": packet_bytes > FORGE_PACKET_GROWTH_WARNING_BYTES,
            "evidence_surface_mode": ctx_packet.get("evidence_surface_mode"),
        }
    except Exception as exc:  # noqa: BLE001
        # Exception text never enters receipts: typed code only.
        vision = {"status": "BLOCKED", "reason": FORGE_VISION_BLOCKED_CODE}
        control_ok = {"packet_error": FORGE_VISION_BLOCKED_CODE}
    evidence["vision"] = {
        "status": vision.get("status"),
        "material_information_loss": vision.get("material_information_loss"),
        "material_capability_information_loss": 0
        if vision.get("status") == "PASS"
        else vision.get("material_information_loss"),
        "unknown_omission": vision.get("unknown_omission"),
    }
    evidence["packet_control"] = {
        **control_ok,
        "control_yield_gate": gate,
        "yield_eligible": yield_eligible,
        "planned_action": preview.get("PLANNED_PREFLIGHT_ACTION"),
        "search_budget": "available",
    }

    # CHALLENGER OPERABILITY (metadata/provenance only, no motif projection)
    challenger: dict[str, Any] = {
        "runtime_seam": "resolve_release_projection_input",
        "seam_module": "solana_alpha_lab.factory.hfic_released_trajectory_projection",
        "non_synthetic_input_receipt_schema": (
            "smial.normalized-trajectory-v1-projection-input-receipt"
        ),
        "terminal": "NORMALIZED_TRAJECTORY_V1_RUNTIME_READY_NOT_EXECUTED",
        "probe_executed": False,
        "no_future_git_atom_required": True,
    }
    if release_root is not None:
        if not Path(release_root).is_dir():
            challenger["seam_status"] = "BLOCKED:RELEASE_ROOT_NOT_FOUND"
        else:
            try:
                result = hfic_released_trajectory_projection.resolve_release_projection_input(
                    Path(release_root)
                )
                receipt = result["projection_input_receipt"]
                challenger["verified_release_binding"] = receipt["corpus_binding"]
                challenger["observation_row_count"] = receipt.get(
                    "observation_row_count"
                )
                challenger["projected_observation_count"] = receipt.get(
                    "projected_observation_count"
                )
                challenger["seam_status"] = "VERIFIED"
            except Exception as exc:  # noqa: BLE001
                code = getattr(exc, "code", None)
                if not isinstance(code, str) or not code:
                    code = INVALID_PROJECTION_CODE
                challenger["seam_status"] = f"BLOCKED:{code}"
    else:
        challenger["seam_status"] = "NOT_REQUESTED"
    evidence["challenger_operability"] = challenger

    suppression_ok = (
        not unauthorized and not ambiguous_hard and not parks_hard and not scope_widened
    )
    priors_ok = (
        evidence["priors"]["h11_visible_body_ranked"]
        and evidence["priors"]["h13_visible_body_ranked"]
        and evidence["priors"]["ranked_body_mismatch"] == 0
        and evidence["priors"]["dropped_material_priors"] == 0
    )
    vision_ok = vision.get("status") == "PASS"
    packet_ok = (
        control_ok.get("packet_within_bound") is True
        and control_ok.get("trajectory_blind") is True
    )
    calibration_ok = (
        evidence["calibration"]["planned_terminal"]
        == "CONTROL_RECONSIDERATION_READY_AFTER_COMMISSION"
    )
    challenger_ok = challenger["seam_status"] == "VERIFIED"
    checks = {
        "suppression": suppression_ok,
        "priors": priors_ok,
        "vision": vision_ok,
        "packet": packet_ok,
        "calibration": calibration_ok,
        "challenger": challenger_ok,
    }
    failed = [name for name, ok in checks.items() if not ok]
    evidence["checks"] = checks
    evidence["failed_checks"] = failed
    evidence["next_hint"] = (
        None
        if not failed
        else _VISION_ACCEPTANCE_HINTS.get(failed[0], "See failed_checks fields.")
    )
    passed = not failed
    evidence["terminal"] = (
        "FORGE_VISION_ACCEPTANCE_PASS" if passed else "FORGE_VISION_ACCEPTANCE_BLOCKED"
    )
    _assert_no_path_leak(evidence, str(data_root), str(repo_root))
    return emit(evidence, exit_code=0 if passed else 2)


_VISION_ACCEPTANCE_HINTS = {
    "suppression": "Unauthorized hard close in ledger; inspect suppression.terminals authority values.",
    "priors": "Run preview-reopened-prior-routing and read BLOCKER_NEXT.",
    "vision": "Packet vision integrity blocked; inspect vision.status and material losses.",
    "packet": "Packet over bound or not trajectory-blind; inspect packet_control fields.",
    "calibration": "Run preview-reopened-prior-routing; commission APPLY not yet ready.",
    "challenger": "Pass --release-root <live_cohort_releases dir> or fix the release path; seam must be VERIFIED for PASS.",
}


def cmd_commission_reopened_priors(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    confirm_append_only: bool,
) -> int:
    data_root = _existing_data_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    git_sha = repository_git_snapshot(repo_root).head_sha.lower()
    payload = commission_reopened_priors(
        store,
        repo_root,
        git_sha=git_sha,
        confirm_append_only=confirm_append_only,
    )
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_freeze(
    repo_root: Path,
    draft_path: Path,
    preflight_path: Path | None,
    explicit_data_root: Path | None,
    next_action_path: Path | None = None,
) -> int:
    git_before = repository_git_snapshot(repo_root)
    draft = _load_json_file(draft_path)
    _assert_no_path_leak(draft, str(repo_root))
    if preflight_path is None:
        raise HficCliError("PREFLIGHT_RECEIPT_REQUIRED")
    receipt = _load_json_file(preflight_path)
    _assert_no_path_leak(receipt, str(repo_root))
    next_action_draft = None
    if next_action_path is not None:
        next_action_draft = _load_json_file(next_action_path)
        _assert_no_path_leak(next_action_draft, str(repo_root))
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    frozen = freeze_draft(
        draft,
        preflight_receipt=receipt,
        store=store,
        repo_root=repo_root,
        next_action_draft=next_action_draft,
        # A production freeze must re-read the current A3 market surface
        # before writing lifecycle bytes.  Fixture/unit callers retain the
        # explicit default and do not gain a synthetic market authority.
        verify_current_market_identity=True,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    frozen["authority"] = {
        "git_mutation": 0,
        "experiment_execution": 0,
        "provider_api_rpc_wss_calls": 0,
    }
    _assert_no_path_leak(frozen, str(data_root), str(repo_root))
    return emit(frozen)


def cmd_persist_draft(
    repo_root: Path,
    draft_path: Path,
    preflight_path: Path,
    explicit_data_root: Path | None,
    *,
    representation_id: str,
    model_provenance_sha256: str | None,
) -> int:
    git_before = repository_git_snapshot(repo_root)
    draft = _load_json_file(draft_path)
    receipt = _load_json_file(preflight_path)
    _assert_no_path_leak(draft, str(repo_root))
    _assert_no_path_leak(receipt, str(repo_root))
    data_root = _existing_data_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    before_digest = store.diagnostics().committed_inventory_sha256
    generated = persist_generated_draft(
        store,
        draft,
        preflight_receipt=receipt,
        repo_root=repo_root,
        representation_id=representation_id,
        model_provenance_sha256=model_provenance_sha256,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    after_digest = ResearchStore(data_root, create_if_missing=False).diagnostics().committed_inventory_sha256
    payload = {
        **generated,
        "writes": {
            "research_store": int(after_digest != before_digest),
            "forge_context": 0,
            "session": 0,
        },
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "model_provenance_semantics": "CALLER_SUPPLIED_DIGEST_NOT_MODEL_ATTESTATION",
    }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_prospects(
    repo_root: Path,
    *,
    trigger: str,
    max_results: int,
) -> int:
    from solana_alpha_lab.factory.hfic_prospects import query_prospects

    git_before = repository_git_snapshot(repo_root)
    payload = query_prospects(
        repo_root,
        trigger=trigger,
        max_results=max_results,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    _assert_no_path_leak(payload, str(repo_root))
    return emit(payload)


def cmd_finalize(
    repo_root: Path,
    session_id: str,
    critic_path: Path,
    explicit_data_root: Path | None,
) -> int:
    from solana_alpha_lab.factory.hfic_session import finalize_session, load_session_bundle

    git_before = repository_git_snapshot(repo_root)
    critic_result = _load_json_file(critic_path)
    _assert_no_path_leak(critic_result, str(repo_root))
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    frozen = load_session_bundle(store, session_id)
    if frozen is None:
        raise HficCliError("SESSION_NOT_FOUND")
    receipt = finalize_session(
        frozen,
        critic_result,
        store=store,
        repo_root=repo_root,
        data_root=data_root,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    _assert_no_path_leak(receipt, str(data_root), str(repo_root))
    return emit(receipt)


def cmd_revise(
    repo_root: Path,
    session_id: str,
    draft_path: Path,
    explicit_data_root: Path | None,
) -> int:
    from solana_alpha_lab.factory.hfic_session import load_session_bundle

    git_before = repository_git_snapshot(repo_root)
    draft = _load_json_file(draft_path)
    _assert_no_path_leak(draft, str(repo_root))
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    frozen = load_session_bundle(store, session_id)
    if frozen is None:
        raise HficCliError("SESSION_NOT_FOUND")
    payload = apply_revision(
        frozen,
        draft,
        store=store,
        repo_root=repo_root,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_classify(
    repo_root: Path,
    session_id: str,
    spec_path: Path,
    explicit_data_root: Path | None,
) -> int:
    from solana_alpha_lab.factory.hfic_session import load_session_bundle

    git_before = repository_git_snapshot(repo_root)
    packet = _load_json_file(spec_path)
    _assert_no_path_leak(packet, str(repo_root))
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    frozen = load_session_bundle(store, session_id)
    if frozen is None:
        raise HficCliError("SESSION_NOT_FOUND")
    payload = apply_classification(
        frozen,
        packet,
        store=store,
        repo_root=repo_root,
        data_root=data_root,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_show_session(
    repo_root: Path,
    *,
    session_id: str | None,
    search_key: str | None,
    explicit_data_root: Path | None,
) -> int:
    if bool(session_id) == bool(search_key):
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    if search_key:
        bundle = find_session_by_search_key(store, search_key)
        if bundle is None:
            raise HficCliError("SESSION_NOT_FOUND")
        session_id = str(bundle["session_id"])
    payload = show_session(store, str(session_id), repo_root=repo_root)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_pending(
    repo_root: Path,
    *,
    search_key: str,
    explicit_data_root: Path | None,
) -> int:
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    pending = [
        {
            "session_id": item.get("session_id"),
            "session_state": item.get("session_state"),
            "search_key_sha256": item.get("search_key_sha256"),
            "evidence_epoch_sha256": item.get("evidence_epoch_sha256"),
            "focus_key_sha256": item.get("focus_key_sha256"),
        }
        for item in list_hfic_sessions(store)
        if item.get("search_key_sha256") == search_key
        and item.get("session_state") in PENDING_STATES
    ]
    payload = {
        "match_count": len(pending),
        "sessions": pending,
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
    }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_prior(
    repo_root: Path,
    *,
    candidate_raw: str | None,
    query: str | None,
    explicit_data_root: Path | None,
) -> int:
    if not candidate_raw and not query:
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    candidate = None
    if candidate_raw:
        loaded = json.loads(candidate_raw)
        if not isinstance(loaded, dict):
            raise HficCliError("HFIC_PROTOCOL_INVALID")
        candidate = loaded
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = lookup_prior(store, candidate=candidate, query=query)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_repair_continuation_draft(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    parent_session_id: str,
    owner_authorization_id: str,
    technical_gap_code: str,
    spent_main_looks: int | None,
    spent_adaptive_looks: int | None,
    spent_preview_looks: int | None,
    parent_run_id: str | None,
    terminal_receipt_sha256: str | None,
    journal_scope: str | None,
    output_path: Path | None,
) -> int:
    """No-write draft builder from show-session + store enrichment."""

    from solana_alpha_lab.factory.hfic_repair_continuation import (
        build_repair_continuation_draft,
        enrich_parent_for_repair_draft,
        resolve_repair_parent_proof,
    )

    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    try:
        parent = show_session(store, parent_session_id, repo_root=repo_root)
    except HficSessionError as exc:
        raise RepairContinuationError("PARENT_SESSION_MISSING") from exc
    parent = enrich_parent_for_repair_draft(store, parent)
    proof = resolve_repair_parent_proof(
        store,
        parent,
        claimed_run_id=parent_run_id,
    )
    mapping = dict(proof.get("evidence_mapping") or {})
    draft = build_repair_continuation_draft(
        parent,
        owner_authorization_id=owner_authorization_id,
        technical_gap_code=technical_gap_code,
        parent_run_id=str(proof["parent_run_id"]),
        terminal_receipt_sha256=terminal_receipt_sha256,
        journal_scope=journal_scope,
        spent_main_looks=spent_main_looks,
        spent_adaptive_looks=spent_adaptive_looks,
        spent_preview_looks=spent_preview_looks,
        evidence_mapping=mapping or None,
    )
    if output_path is not None:
        output_path.write_text(
            json.dumps(draft, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    payload = {
        "command": "repair-continuation-draft",
        "writes": False,
        "parent_proof_mode": proof.get("mode"),
        "owner_status": "READY",
        "next_step": "REPAIR_CONTINUATION_PLAN_WITH_DRAFT",
        "draft": draft,
        "draft_path": str(output_path.name) if output_path is not None else None,
        "spent_looks_source": parent.get("spent_looks_source") or "EXPLICIT_FLAGS",
        "remaining_main_looks": max(0, 6 - int(draft["spent_main_looks"])),
        "remaining_adaptive_looks": max(0, 2 - int(draft["spent_adaptive_looks"])),
        "remaining_preview_looks": max(0, 2 - int(draft["spent_preview_looks"])),
        "owner_readout": {
            "status": "READY",
            "next": "REPAIR_CONTINUATION_PLAN_WITH_DRAFT",
            "writes": False,
            "spent_main_looks": draft["spent_main_looks"],
            "remaining_main_looks": max(0, 6 - int(draft["spent_main_looks"])),
        },
    }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_repair_continuation_plan(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    draft_path: Path,
    parent_session_id: str | None,
) -> int:
    """No-write owner plan for one repair continuation disposition draft."""

    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HficCliError("REPAIR_CONTINUATION_DRAFT_INVALID") from exc
    if not isinstance(draft, dict):
        raise HficCliError("REPAIR_CONTINUATION_DRAFT_INVALID")
    session_id = str(parent_session_id or draft.get("parent_session_id") or "")
    parent = None
    if session_id:
        parent = next(
            (
                item
                for item in list_hfic_sessions(store)
                if str(item.get("session_id") or "") == session_id
            ),
            None,
        )
        if parent is None:
            try:
                parent = show_session(store, session_id, repo_root=repo_root)
            except HficSessionError:
                parent = {"session_id": session_id}
        else:
            # Enrich list projection with critic/selected fields from show-session.
            try:
                shown = show_session(store, session_id, repo_root=repo_root)
                parent = {**parent, **{
                    key: shown.get(key)
                    for key in (
                        "critic_terminal",
                        "final_session_terminal",
                        "selected_candidate_id",
                        "scientific_slot_sha256",
                        "session_receipt_sha256",
                        "terminal_receipt_sha256",
                        "journal_scope",
                        "search_key_sha256",
                        "run_id",
                        "forge_run_id",
                        "spent_main_looks",
                        "spent_adaptive_looks",
                        "spent_preview_looks",
                    )
                    if shown.get(key) is not None
                }}
                if not parent.get("terminal_receipt_sha256"):
                    parent["terminal_receipt_sha256"] = parent.get(
                        "session_receipt_sha256"
                    )
                if not parent.get("journal_scope"):
                    parent["journal_scope"] = parent.get("search_key_sha256")
            except HficSessionError:
                pass
    existing = list_repair_continuation_dispositions(store)
    plan = plan_repair_continuation(
        draft,
        parent_session=parent,
        existing_dispositions=existing,
        store=store,
    )
    reasons = draft.get("technical_gap_code")
    payload = {
        **plan,
        "command": "repair-continuation-plan",
        "writes": False,
        "technical_gap_code": reasons,
        "exclusion_glossary_hint": explain_target_exclusion(
            str(draft.get("example_exclusion_code") or "REQUEST_NOT_AFTER_ENTRY")
        ),
    }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    exit_code = 0 if plan.get("owner_status") in {"READY", "DONE"} else 2
    return emit(payload, exit_code=exit_code)


def cmd_repair_continuation_apply(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    draft_path: Path,
    parent_session_id: str | None,
    confirm_append_only: bool,
) -> int:
    """Append-only repair continuation. Requires --confirm-append-only."""

    if not confirm_append_only:
        raise HficCliError("REPAIR_CONTINUATION_CONFIRM_REQUIRED")
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HficCliError("REPAIR_CONTINUATION_DRAFT_INVALID") from exc
    if not isinstance(draft, dict):
        raise HficCliError("REPAIR_CONTINUATION_DRAFT_INVALID")
    session_id = str(parent_session_id or draft.get("parent_session_id") or "")
    parent = None
    if session_id:
        parent = next(
            (
                item
                for item in list_hfic_sessions(store)
                if str(item.get("session_id") or "") == session_id
            ),
            None,
        )
        if parent is None:
            try:
                parent = show_session(store, session_id, repo_root=repo_root)
            except HficSessionError:
                parent = {"session_id": session_id}
        else:
            try:
                shown = show_session(store, session_id, repo_root=repo_root)
                parent = {
                    **parent,
                    **{
                        key: shown.get(key)
                        for key in (
                            "critic_terminal",
                            "final_session_terminal",
                            "selected_candidate_id",
                            "scientific_slot_sha256",
                            "session_receipt_sha256",
                            "terminal_receipt_sha256",
                            "journal_scope",
                            "search_key_sha256",
                            "run_id",
                            "forge_run_id",
                            "spent_main_looks",
                            "spent_adaptive_looks",
                            "spent_preview_looks",
                        )
                        if shown.get(key) is not None
                    },
                }
                if not parent.get("terminal_receipt_sha256"):
                    parent["terminal_receipt_sha256"] = parent.get(
                        "session_receipt_sha256"
                    )
                if not parent.get("journal_scope"):
                    parent["journal_scope"] = parent.get("search_key_sha256")
            except HficSessionError:
                pass
    snapshot = repository_git_snapshot(repo_root)
    git_sha = str(snapshot.head_sha or "").lower()
    if len(git_sha) != 40:
        raise HficCliError("REPAIR_CONTINUATION_GIT_SHA_UNRESOLVED")
    try:
        result = apply_repair_continuation(
            store,
            draft,
            parent_session=parent,
            git_sha=git_sha,
        )
    except RepairContinuationError as exc:
        code = str(exc)
        if code in {
            "COMPETING_ACTIVE_DISPOSITION",
            "COMPETING_DISPOSITION_APPLIED",
        }:
            conflict = plan_repair_continuation(
                draft,
                parent_session=parent,
                existing_dispositions=list_repair_continuation_dispositions(store),
                store=store,
            )
            payload = {
                **conflict,
                "command": "repair-continuation-apply",
                "owner_status": "BLOCKED",
                "reason_code": code,
                "next_step": conflict.get("next_step")
                or _REPAIR_OWNER_NEXT.get(code, "CLOSE_COMPETING_DISPOSITION_THEN_STOP"),
            }
            payload["owner_readout"] = {
                "status": "BLOCKED",
                "reason_code": code,
                "next": payload["next_step"],
                "writes": False,
                "competing_disposition_sha256": (
                    (conflict.get("disposition") or {}).get("disposition_sha256")
                    if isinstance(conflict.get("disposition"), dict)
                    else None
                ),
            }
            _assert_no_path_leak(payload, str(data_root), str(repo_root))
            return emit(payload, exit_code=2)
        return emit_repair_blocked(code)
    payload = {
        **result,
        "command": "repair-continuation-apply",
        "owner_status": (
            "DONE"
            if result.get("status") in {"APPLIED", "ALREADY_APPLIED"}
            else result.get("owner_status") or "BLOCKED"
        ),
        "next_step": result.get("next_step")
        or "ORDINARY_TEMPORAL_QUERY_WITHIN_REMAINING_BUDGET",
    }
    if payload["owner_status"] == "DONE":
        payload["owner_readout"] = {
            "status": "DONE",
            "reason_code": result.get("reason_code"),
            "next": payload["next_step"],
            "writes": bool(result.get("writes")),
        }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_repair_continuation_close(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    disposition_sha256: str,
    reason_code: str,
    confirm_append_only: bool,
) -> int:
    """Append-only CLOSE after a new terminal. Requires --confirm-append-only."""

    if not confirm_append_only:
        raise HficCliError("REPAIR_CONTINUATION_CONFIRM_REQUIRED")
    digest = str(disposition_sha256 or "").strip().lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise HficCliError("REPAIR_CONTINUATION_DISPOSITION_SHA_INVALID")
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root, create_if_missing=False)
    snapshot = repository_git_snapshot(repo_root)
    git_sha = str(snapshot.head_sha or "").lower()
    if len(git_sha) != 40:
        raise HficCliError("REPAIR_CONTINUATION_GIT_SHA_UNRESOLVED")
    result = close_repair_continuation(
        store,
        digest,
        git_sha=git_sha,
        reason_code=str(reason_code or "CONTINUATION_TERMINAL_REACHED"),
    )
    payload = {
        **result,
        "command": "repair-continuation-close",
        "owner_status": "DONE",
        "next_step": "STOP_CONTINUATION_CONSUMED",
        "owner_readout": {
            "status": "DONE",
            "reason_code": result.get("reason_code"),
            "next": "STOP_CONTINUATION_CONSUMED",
            "writes": bool(result.get("writes")),
        },
    }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_prove_runtime(
    repo_root: Path,
    session_id: str,
    explicit_data_root: Path | None,
) -> int:
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = prove_runtime(store, session_id, repo_root=repo_root)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    exit_code = 1 if payload.get("proof_status") == "NOT_A_PROOF" else 0
    return emit(payload, exit_code=exit_code)


def cmd_inventory_placeholder_times(
    repo_root: Path,
    explicit_data_root: Path | None,
) -> int:
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = inventory_placeholder_hfic_records(store)
    public = {
        "record_count": payload["record_count"],
        "counts_by_session_id": payload["counts_by_session_id"],
        "counts_by_record_kind": payload["counts_by_record_kind"],
        "counts_by_artifact_kind": payload["counts_by_artifact_kind"],
        "counts_by_affected_field": payload["counts_by_affected_field"],
        "inventory_sha256": payload["inventory_sha256"],
        "original_placeholder_value": payload["original_placeholder_value"],
        "original_exact_time_status": "UNKNOWN",
        "chronological_use_forbidden": True,
        "records": [
            {
                "record_id": item["record_id"],
                "payload_sha256": item["payload_sha256"],
                "record_kind": item["record_kind"],
                "artifact_kind": item.get("artifact_kind"),
                "session_id": item.get("session_id"),
                "affected_fields": item["affected_fields"],
            }
            for item in payload["records"]
        ],
        "authority": payload["authority"],
    }
    _assert_no_path_leak(public, str(data_root), str(repo_root))
    return emit(public)


def cmd_apply_provenance_correction(
    repo_root: Path,
    explicit_data_root: Path | None,
    *,
    confirm_append_only: bool,
) -> int:
    if not confirm_append_only:
        raise HficCliError("PROVENANCE_CORRECTION_CONFIRM_REQUIRED")
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = apply_provenance_correction(store, repo_root=repo_root)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_rebase_science_memory(
    repo_root: Path,
    *,
    explicit_data_root: Path | None,
    confirm_append_only: bool,
) -> int:
    if not confirm_append_only:
        raise HficCliError("SCIENCE_REBASE_CONFIRM_REQUIRED")
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = run_science_memory_rebase(
        store,
        repo_root=repo_root,
        data_root=data_root,
    )
    safe = {
        key: value
        for key, value in payload.items()
        if key != "after_ledger"
    }
    safe["suppressors_total"] = int(
        (payload.get("after_counts") or {}).get("suppressors_total") or 0
    )
    _assert_no_path_leak(safe, str(data_root), str(repo_root))
    return emit(safe)


def cmd_backfill(
    packet_path: Path,
    *,
    persist: bool,
    repo_root: Path,
    explicit_data_root: Path | None,
) -> int:
    packet = _load_json_file(packet_path)
    _assert_no_path_leak(packet, str(repo_root))
    preview = backfill_legacy(packet, persist=False)
    _assert_no_path_leak(preview, str(repo_root))
    if not persist:
        return emit(preview)

    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    result = backfill_legacy(
        packet,
        persist=True,
        store=store,
        repo_root=repo_root,
    )
    _assert_no_path_leak(result, str(data_root), str(repo_root))
    return emit(result)


def cmd_diagnostics(
    repo_root: Path,
    *,
    last_n: int,
    explicit_data_root: Path | None,
) -> int:
    from solana_alpha_lab.factory.hfic_grounding import (
        HficGroundingError,
        aggregate_diagnostics,
        collect_session_receipts,
        session_read_census,
    )

    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    try:
        receipts = collect_session_receipts(store)
        payload = aggregate_diagnostics(receipts, last_n)
        payload.update(session_read_census(store))
    except HficGroundingError as exc:
        raise HficCliError(str(exc)) from exc
    payload["action"] = "DIAGNOSTICS"
    payload["authority"] = {
        "git_mutation": 0,
        "experiment_execution": 0,
        "provider_api_rpc_wss_calls": 0,
    }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_censoring_ignorability_diagnostic(
    repo_root: Path,
    *,
    census: Path | None,
    observations: Path | None,
    data_root: Path | None,
) -> int:
    from solana_alpha_lab.factory.hfic_censoring_ignorability_diagnostic import (
        CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED,
        CANONICAL_MODE_EXPLICIT_PATH_CONFLICT,
        CensoringDiagnosticError,
        run_censoring_ignorability_diagnostic,
    )

    if data_root is not None and (census is not None or observations is not None):
        raise HficCliError(CANONICAL_MODE_EXPLICIT_PATH_CONFLICT)
    if data_root is None and (census is None or observations is None):
        raise HficCliError(CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED)
    try:
        receipt = run_censoring_ignorability_diagnostic(
            root=repo_root,
            census_path=census,
            observations_path=observations,
            data_root=data_root,
        )
    except CensoringDiagnosticError as exc:
        raise HficCliError(str(exc)) from exc
    leak = [str(repo_root)]
    if census is not None:
        leak.append(str(census))
    if observations is not None:
        leak.append(str(observations))
    if data_root is not None:
        leak.append(str(data_root))
    _assert_no_path_leak(receipt, *leak)
    return emit(receipt)


def cmd_selection_robustness_gate(
    repo_root: Path,
    *,
    census: Path | None,
    observations: Path | None,
    data_root: Path | None,
) -> int:
    from solana_alpha_lab.factory.hfic_selection_robustness_gate import (
        CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED,
        CANONICAL_MODE_EXPLICIT_PATH_CONFLICT,
        SelectionRobustnessGateError,
        run_selection_robustness_gate,
    )

    if data_root is not None and (census is not None or observations is not None):
        raise HficCliError(CANONICAL_MODE_EXPLICIT_PATH_CONFLICT)
    if data_root is None and (census is None or observations is None):
        raise HficCliError(CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED)
    try:
        receipt = run_selection_robustness_gate(
            root=repo_root,
            census_path=census,
            observations_path=observations,
            data_root=data_root,
        )
    except SelectionRobustnessGateError as exc:
        raise HficCliError(str(exc)) from exc
    leak = [str(repo_root)]
    if census is not None:
        leak.append(str(census))
    if observations is not None:
        leak.append(str(observations))
    if data_root is not None:
        leak.append(str(data_root))
    _assert_no_path_leak(receipt, *leak)
    return emit(receipt)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hypothesis_forge")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help=(
            "factory data_root; for censoring-ignorability-diagnostic and "
            "selection-robustness-gate this must be an imported LIVE CORPUS "
            "(datasets/live_lifecycle_corpus/lineage.json), never Observation RDP"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--owner-focus", default="AUTO")
    preflight.add_argument("--format", choices=("json",), default="json")
    preflight.add_argument("--no-auto-commission", action="store_true")
    preflight.add_argument(
        "--control-current-representation",
        action="store_true",
        help="CURRENT_REPRESENTATION_CONTROL_V1 evidence-surface mode",
    )
    preflight.add_argument(
        "--discovery-contract",
        action="store_true",
        help=(
            "Accepted on ordinary preflight. Non-CONTROL receipts always "
            "carry FORGE_GROUNDED_DISCOVERY_V1; this flag does not toggle it."
        ),
    )
    preflight.add_argument(
        "--model-provenance-sha256",
        default=None,
        help=(
            "Caller-supplied model/reasoning provenance digest; retained for "
            "reuse checks, not an attestation of the model actually used"
        ),
    )

    forge_input = subparsers.add_parser(
        "forge-input",
        help="No-write FORGE_INPUT_RECEIPT; never starts a session",
    )
    forge_input.add_argument("--format", choices=("json",), default="json")
    forge_input.add_argument("--owner-focus", default="AUTO")
    forge_input.add_argument(
        "--no-write",
        action="store_true",
        default=True,
        help="Accepted and always true; forge-input never persists",
    )

    forge_run = subparsers.add_parser(
        "forge-run",
        help="Bounded representation-ladder run receipt; default no-write",
    )
    forge_run.add_argument("--format", choices=("json",), default="json")
    forge_run.add_argument("--owner-focus", default="AUTO")
    forge_run.add_argument(
        "--no-write",
        action="store_true",
        default=True,
        help="Default; never persist the aggregate run",
    )
    forge_run.add_argument(
        "--persist",
        action="store_true",
        help="Append FORGE_RUN_RECEIPT on an already-authorized slash store",
    )
    forge_run.add_argument(
        "--saved-draft-sha256",
        default=None,
        help="Resume the exact saved draft; do not regenerate",
    )
    forge_run.add_argument(
        "--model-provenance-sha256",
        default=None,
        help=(
            "Optional caller-supplied model/reasoning provenance for admission "
            "readback; mismatch blocks reuse and never resets market budget"
        ),
    )
    forge_run.add_argument(
        "--control-current-representation",
        action="store_true",
        help="Explicit CURRENT_REPRESENTATION_CONTROL_V1. Ordinary forge-run does not imply it.",
    )
    discovery_coverage = subparsers.add_parser(
        "discovery-coverage",
        help="No-write state-only joint coverage. Never selects typed_value.",
    )
    discovery_coverage.add_argument("--format", choices=("json",), default="json")
    discovery_binding = subparsers.add_parser(
        "discovery-binding",
        help=(
            "No-write discovery admission binding from the published corpus. "
            "Does not read parquet values."
        ),
    )
    discovery_binding.add_argument("--format", choices=("json",), default="json")
    discovery_execute = subparsers.add_parser(
        "discovery-execute",
        help=(
            "Compute one BASE_X price/liquidity query from census and observation "
            "rows into an explicit store. Does not select the live store."
        ),
    )
    discovery_execute.add_argument("--store", type=Path, required=True)
    discovery_execute.add_argument("--census", type=Path)
    discovery_execute.add_argument("--observations", type=Path)
    discovery_execute.add_argument(
        "--cohort-partition",
        action="append",
        nargs=3,
        metavar=("COHORT", "CENSUS", "OBSERVATIONS"),
        default=None,
    )
    discovery_execute.add_argument(
        "--binding",
        type=Path,
        help="Optional explicit binding. Omit to resolve the published corpus.",
    )
    discovery_execute.add_argument("--spec", type=Path, required=True)
    discovery_execute.add_argument("--candidate-scope", type=Path, required=True)
    discovery_execute.add_argument("--journal-scope", required=True)
    discovery_execute.add_argument("--operation", type=Path, default=None)
    discovery_execute.add_argument("--operation-sha256", default=None)
    discovery_execute.add_argument(
        "--correct-result-ref",
        default=None,
        help="Saved result to revise. Same spec and frozen input; no new look.",
    )
    discovery_execute.add_argument(
        "--correct-result-sha256",
        default=None,
        help="Exact result_sha256 of --correct-result-ref.",
    )
    discovery_preview = subparsers.add_parser(
        "discovery-preview",
        help="Feature-only temporal preview. Writes store memory only when --store and --journal-scope are both set. Does not read a target.",
    )
    discovery_preview.add_argument("--spec", type=Path, required=True)
    discovery_preview.add_argument("--binding", type=Path)
    discovery_preview.add_argument("--census", type=Path)
    discovery_preview.add_argument("--observations", type=Path)
    discovery_preview.add_argument(
        "--cohort-partition",
        action="append",
        nargs=3,
        metavar=("COHORT", "CENSUS", "OBSERVATIONS"),
        default=None,
    )
    discovery_preview.add_argument("--prior-preview-hash", action="append", default=None)
    discovery_preview.add_argument("--store", type=Path)
    discovery_preview.add_argument("--journal-scope")
    discovery_preview.add_argument("--operation", type=Path, default=None)
    discovery_preview.add_argument("--operation-sha256", default=None)
    discovery_preview.add_argument("--format", choices=("json",), default="json")
    discovery_execute.add_argument("--format", choices=("json",), default="json")

    persist_draft = subparsers.add_parser(
        "persist-draft",
        help="Durably bind generated draft bytes to their source preflight before freeze",
    )
    persist_draft.add_argument("--draft", type=Path, required=True)
    persist_draft.add_argument("--preflight-receipt", type=Path, required=True)
    persist_draft.add_argument("--representation-id", default="BASE")
    persist_draft.add_argument(
        "--model-provenance-sha256",
        default=None,
        help="Caller-supplied digest, not model attestation",
    )
    persist_draft.add_argument("--format", choices=("json",), default="json")

    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--draft", type=Path, required=True)
    freeze.add_argument("--preflight-receipt", type=Path, required=True)
    freeze.add_argument("--next-action", type=Path, default=None)
    freeze.add_argument("--format", choices=("json",), default="json")

    prospects = subparsers.add_parser("prospects")
    prospects.add_argument("--trigger", required=True)
    prospects.add_argument("--max-results", type=int, default=3)
    prospects.add_argument("--format", choices=("json",), default="json")

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--session-id", required=True)
    finalize.add_argument("--critic-result", type=Path, required=True)
    finalize.add_argument("--format", choices=("json",), default="json")

    revise = subparsers.add_parser("revise")
    revise.add_argument("--session-id", required=True)
    revise.add_argument("--draft", type=Path, required=True)
    revise.add_argument("--format", choices=("json",), default="json")

    classify_cmd = subparsers.add_parser("classify")
    classify_cmd.add_argument("--session-id", required=True)
    classify_cmd.add_argument("--experiment-spec", type=Path, required=True)
    classify_cmd.add_argument("--format", choices=("json",), default="json")

    show_session_cmd = subparsers.add_parser("show-session")
    show_session_cmd.add_argument("--session-id", default=None)
    show_session_cmd.add_argument("--search-key", default=None)
    show_session_cmd.add_argument("--format", choices=("json",), default="json")

    pending = subparsers.add_parser("pending")
    pending.add_argument("--search-key", required=True)
    pending.add_argument("--format", choices=("json",), default="json")

    prior = subparsers.add_parser("prior")
    prior.add_argument("--candidate", default=None)
    prior.add_argument("--query", default=None)
    prior.add_argument("--format", choices=("json",), default="json")

    diagnostics = subparsers.add_parser("diagnostics")
    diagnostics.add_argument("--last", type=int, required=True)
    diagnostics.add_argument("--format", choices=("json",), default="json")

    censoring = subparsers.add_parser(
        "censoring-ignorability-diagnostic",
        help=(
            "offline X300 selection diagnostic; canonical LIVE CORPUS via parent "
            "--data-root, or explicit parquet paths which stay noncanonical"
        ),
        description=(
            "Canonical mode: pass parent --data-root pointing at an imported LIVE "
            "CORPUS data_root that contains datasets/live_lifecycle_corpus/lineage.json. "
            "Do not pass Observation RDP. Bind FAIL is a typed CANONICAL_* token and "
            "does not fall back to parquet paths. Explicit --census and --observations "
            "stay SYNTHETIC_OR_NONCANONICAL_POPULATION even if bytes match frozen "
            "hashes. Mixing parent --data-root with --census/--observations fails as "
            "CANONICAL_MODE_EXPLICIT_PATH_CONFLICT. Empty invocation fails as "
            "CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED."
        ),
    )
    censoring.add_argument("--census", type=Path, default=None)
    censoring.add_argument("--observations", type=Path, default=None)
    censoring.add_argument("--format", choices=("json",), default="json")

    selection_gate = subparsers.add_parser(
        "selection-robustness-gate",
        help=(
            "offline two-stage selection gate; reuses Stage 1 then optional Block-A "
            "logistic OOF-AUC; owner-facing field is router_decision"
        ),
        description=(
            "Canonical mode: parent --data-root pointing at an imported LIVE CORPUS "
            "data_root that contains datasets/live_lifecycle_corpus/lineage.json. "
            "Do not pass Observation RDP. Bind FAIL is a typed CANONICAL_* token and "
            "does not fall back to parquet paths. Explicit --census and --observations "
            "stay SYNTHETIC_OR_NONCANONICAL_POPULATION and do not write latest.json. "
            "Mixing parent --data-root with --census/--observations fails as "
            "CANONICAL_MODE_EXPLICIT_PATH_CONFLICT. Empty invocation fails as "
            "CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED. Owner-facing field is "
            "router_decision. Does not auto-run Forge. A later OPERATE on --data-root "
            "is required before ordinary preflight consumes the gate."
        ),
    )
    selection_gate.add_argument("--census", type=Path, default=None)
    selection_gate.add_argument("--observations", type=Path, default=None)
    selection_gate.add_argument("--format", choices=("json",), default="json")

    backfill = subparsers.add_parser("backfill-legacy")
    backfill.add_argument("--packet", type=Path, required=True)
    backfill.add_argument("--persist", action="store_true")
    backfill.add_argument("--format", choices=("json",), default="json")

    prove = subparsers.add_parser("prove-runtime")
    prove.add_argument("--session-id", required=True)
    prove.add_argument("--format", choices=("json",), default="json")

    inventory = subparsers.add_parser(
        "inventory-placeholder-times",
        help="read-only counts of HFIC records with placeholder provenance times",
    )
    inventory.add_argument("--format", choices=("json",), default="json")

    correction = subparsers.add_parser(
        "apply-provenance-correction",
        help="append-only HFIC provenance-time correction; requires --confirm-append-only after merge phrase",
    )
    correction.add_argument("--format", choices=("json",), default="json")
    correction.add_argument(
        "--confirm-append-only",
        action="store_true",
        help="required; does not rewrite RDP bytes or recover an exact original time",
    )

    rebase = subparsers.add_parser(
        "rebase-science-memory",
        help="append-only science-memory suppression rebase; requires --confirm-append-only",
    )
    rebase.add_argument("--format", choices=("json",), default="json")
    rebase.add_argument(
        "--confirm-append-only",
        action="store_true",
        help="required; appends DECISION_EVENT only; never rewrites historical RDP bytes",
    )
    status_cmd = subparsers.add_parser(
        "memory-policy-status",
        help="read-only HFIC search-memory policy and prior-memory capacity",
    )
    status_cmd.add_argument("--format", choices=("json",), default="json")
    preview_cmd = subparsers.add_parser(
        "memory-policy-preview",
        help="read-only preview of an append-only HFIC search-memory policy",
    )
    preview_cmd.add_argument("--quarantine-session", action="append", default=[])
    preview_cmd.add_argument("--restore-session", action="append", default=[])
    preview_cmd.add_argument("--quarantine-all-current-hfic", action="store_true")
    preview_cmd.add_argument(
        "--reason",
        default=REASON_OWNER_CALIBRATION_RESET,
        choices=sorted(
            {
                REASON_OWNER_CALIBRATION_RESET,
                REASON_OWNER_MEMORY_RESTORE,
                REASON_PRE_CAPABILITY_BASELINE,
            }
        ),
    )
    preview_cmd.add_argument("--format", choices=("json",), default="json")
    apply_cmd = subparsers.add_parser(
        "memory-policy-apply",
        help="append-only HFIC search-memory policy; requires --confirm-append-only",
    )
    apply_cmd.add_argument("--proposal", type=Path, required=True)
    apply_cmd.add_argument(
        "--confirm-append-only",
        action="store_true",
        help="required; appends policy only; never rewrites historical RDP bytes",
    )
    apply_cmd.add_argument("--format", choices=("json",), default="json")
    reopen_preview = subparsers.add_parser(
        "preview-reopened-prior-routing",
        help="read-only CONTROL reconsideration preview after planned legacy-prior commission and exact-session quarantine",
    )
    reopen_preview.add_argument("--format", choices=("json",), default="json")
    vision_cmd = subparsers.add_parser(
        "vision-acceptance",
        help="read-only FORGE_VISION_ACCEPTANCE machine evidence over suppression/priors/vision/packet/challenger",
    )
    vision_cmd.add_argument(
        "--release-root",
        type=Path,
        default=None,
        help="verified live-cohort release directory (live_cohort_releases/<cohort_id>); required for challenger seam VERIFIED and acceptance PASS",
    )
    vision_cmd.add_argument("--format", choices=("json",), default="json")
    reopen_apply = subparsers.add_parser(
        "commission-reopened-priors",
        help="append-only legacy reopenable prior HYPOTHESIS_VERSION records; requires --confirm-append-only",
    )
    reopen_apply.add_argument("--format", choices=("json",), default="json")
    reopen_apply.add_argument(
        "--confirm-append-only",
        action="store_true",
        help="required; appends non-HFIC HYPOTHESIS_VERSION only; never rewrites historical RDP bytes",
    )
    repair_draft = subparsers.add_parser(
        "repair-continuation-draft",
        help="no-write draft builder from show-session; spent looks default from journal",
    )
    repair_draft.add_argument("--parent-session-id", required=True)
    repair_draft.add_argument("--owner-authorization-id", required=True)
    repair_draft.add_argument("--technical-gap-code", required=True)
    repair_draft.add_argument(
        "--spent-main-looks",
        type=int,
        default=None,
        help="optional override; default = discovery journal MAIN count for search_key",
    )
    repair_draft.add_argument(
        "--spent-adaptive-looks",
        type=int,
        default=None,
        help="optional override; default = discovery journal ADAPTIVE count",
    )
    repair_draft.add_argument(
        "--spent-preview-looks",
        type=int,
        default=None,
        help="optional override; default = discovery journal PREVIEW count",
    )
    repair_draft.add_argument("--parent-run-id", default=None)
    repair_draft.add_argument("--terminal-receipt-sha256", default=None)
    repair_draft.add_argument("--journal-scope", default=None)
    repair_draft.add_argument(
        "--output",
        type=Path,
        default=None,
        help="optional path to write draft JSON",
    )
    repair_draft.add_argument("--format", choices=("json",), default="json")
    repair_plan = subparsers.add_parser(
        "repair-continuation-plan",
        help="no-write owner plan for repair continuation after completed NO_WORTHY",
    )
    repair_plan.add_argument(
        "--draft",
        type=Path,
        required=True,
        help="JSON disposition draft (parent run/session/slot/terminal/gap/authorization)",
    )
    repair_plan.add_argument(
        "--parent-session-id",
        default=None,
        help="optional override; defaults to draft.parent_session_id",
    )
    repair_plan.add_argument("--format", choices=("json",), default="json")
    repair_apply = subparsers.add_parser(
        "repair-continuation-apply",
        help="append-only repair continuation; requires --confirm-append-only; separate from plan",
    )
    repair_apply.add_argument("--draft", type=Path, required=True)
    repair_apply.add_argument("--parent-session-id", default=None)
    repair_apply.add_argument(
        "--confirm-append-only",
        action="store_true",
        help="required; appends disposition only; does not refresh budget or rewrite NO_WORTHY",
    )
    repair_apply.add_argument("--format", choices=("json",), default="json")
    repair_close = subparsers.add_parser(
        "repair-continuation-close",
        help="append-only CLOSE after a new terminal; requires --confirm-append-only",
    )
    repair_close.add_argument(
        "--disposition-sha256",
        required=True,
        help="exact disposition_sha256 from apply / plan readout",
    )
    repair_close.add_argument(
        "--reason-code",
        default="CONTINUATION_TERMINAL_REACHED",
        help="close reason; default CONTINUATION_TERMINAL_REACHED",
    )
    repair_close.add_argument(
        "--confirm-append-only",
        action="store_true",
        help="required; appends CLOSED disposition; does not rewrite history",
    )
    repair_close.add_argument("--format", choices=("json",), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.root.resolve()
    try:
        if args.command == "preflight":
            return cmd_preflight(
                repo_root,
                owner_focus=args.owner_focus,
                auto_commission=not args.no_auto_commission,
                explicit_data_root=args.data_root,
                control_current_representation=bool(
                    getattr(args, "control_current_representation", False)
                ),
                model_provenance_sha256=getattr(
                    args, "model_provenance_sha256", None
                ),
            )
        if args.command == "forge-input":
            return cmd_forge_input(
                repo_root,
                explicit_data_root=args.data_root,
                owner_focus=str(getattr(args, "owner_focus", "AUTO") or "AUTO"),
            )
        if args.command == "forge-run":
            return cmd_forge_run(
                repo_root,
                explicit_data_root=args.data_root,
                owner_focus=str(getattr(args, "owner_focus", "AUTO") or "AUTO"),
                persist=bool(getattr(args, "persist", False)),
                saved_draft_sha256=getattr(args, "saved_draft_sha256", None),
                model_provenance_sha256=getattr(
                    args, "model_provenance_sha256", None
                ),
                control_current_representation=bool(
                    getattr(args, "control_current_representation", False)
                ),
            )
        if args.command == "discovery-coverage":
            return cmd_discovery_coverage(repo_root, args.data_root)
        if args.command == "discovery-binding":
            return cmd_discovery_binding(repo_root, args.data_root)
        if args.command == "discovery-preview":
            return cmd_discovery_preview(
                repo_root,
                explicit_data_root=args.data_root,
                spec_path=args.spec,
                binding_path=args.binding,
                census_path=args.census,
                observations_path=args.observations,
                cohort_partitions=[
                    (str(item[0]), Path(item[1]), Path(item[2]))
                    for item in (args.cohort_partition or [])
                ],
                prior_preview_hash=args.prior_preview_hash,
                store_root=args.store,
                journal_scope=args.journal_scope,
                operation_path=args.operation,
                operation_sha256=args.operation_sha256,
            )
        if args.command == "discovery-execute":
            return cmd_discovery_execute(
                repo_root,
                store_root=args.store,
                census_path=args.census,
                observations_path=args.observations,
                binding_path=args.binding,
                spec_path=args.spec,
                journal_scope=str(args.journal_scope),
                candidate_scope_path=args.candidate_scope,
                cohort_partitions=[
                    (str(item[0]), Path(item[1]), Path(item[2]))
                    for item in (args.cohort_partition or [])
                ],
                explicit_data_root=args.data_root,
                operation_path=args.operation,
                operation_sha256=args.operation_sha256,
                correct_result_ref=args.correct_result_ref,
                correct_result_sha256=args.correct_result_sha256,
            )
        if args.command == "persist-draft":
            return cmd_persist_draft(
                repo_root,
                args.draft,
                args.preflight_receipt,
                args.data_root,
                representation_id=str(args.representation_id),
                model_provenance_sha256=getattr(
                    args, "model_provenance_sha256", None
                ),
            )
        if args.command == "freeze":
            return cmd_freeze(
                repo_root,
                args.draft,
                args.preflight_receipt,
                args.data_root,
                next_action_path=getattr(args, "next_action", None),
            )
        if args.command == "prospects":
            return cmd_prospects(
                repo_root,
                trigger=args.trigger,
                max_results=args.max_results,
            )
        if args.command == "backfill-legacy":
            return cmd_backfill(
                args.packet,
                persist=bool(args.persist),
                repo_root=repo_root,
                explicit_data_root=args.data_root,
            )
        if args.command == "finalize":
            return cmd_finalize(
                repo_root,
                args.session_id,
                args.critic_result,
                args.data_root,
            )
        if args.command == "revise":
            return cmd_revise(
                repo_root,
                args.session_id,
                args.draft,
                args.data_root,
            )
        if args.command == "classify":
            return cmd_classify(
                repo_root,
                args.session_id,
                args.experiment_spec,
                args.data_root,
            )
        if args.command == "show-session":
            return cmd_show_session(
                repo_root,
                session_id=args.session_id,
                search_key=getattr(args, "search_key", None),
                explicit_data_root=args.data_root,
            )
        if args.command == "pending":
            return cmd_pending(
                repo_root,
                search_key=args.search_key,
                explicit_data_root=args.data_root,
            )
        if args.command == "prior":
            return cmd_prior(
                repo_root,
                candidate_raw=args.candidate,
                query=args.query,
                explicit_data_root=args.data_root,
            )
        if args.command == "diagnostics":
            return cmd_diagnostics(
                repo_root,
                last_n=int(args.last),
                explicit_data_root=args.data_root,
            )
        if args.command == "censoring-ignorability-diagnostic":
            return cmd_censoring_ignorability_diagnostic(
                repo_root,
                census=args.census,
                observations=args.observations,
                data_root=args.data_root,
            )
        if args.command == "selection-robustness-gate":
            return cmd_selection_robustness_gate(
                repo_root,
                census=args.census,
                observations=args.observations,
                data_root=args.data_root,
            )
        if args.command == "prove-runtime":
            return cmd_prove_runtime(repo_root, args.session_id, args.data_root)
        if args.command == "inventory-placeholder-times":
            return cmd_inventory_placeholder_times(repo_root, args.data_root)
        if args.command == "apply-provenance-correction":
            return cmd_apply_provenance_correction(
                repo_root,
                args.data_root,
                confirm_append_only=bool(args.confirm_append_only),
            )
        if args.command == "rebase-science-memory":
            return cmd_rebase_science_memory(
                repo_root,
                explicit_data_root=args.data_root,
                confirm_append_only=bool(args.confirm_append_only),
            )
        if args.command == "memory-policy-status":
            return cmd_memory_policy_status(repo_root, args.data_root)
        if args.command == "memory-policy-preview":
            return cmd_memory_policy_preview(
                repo_root,
                explicit_data_root=args.data_root,
                quarantine_session_ids=list(args.quarantine_session or []),
                restore_session_ids=list(args.restore_session or []),
                quarantine_all_current_hfic=bool(args.quarantine_all_current_hfic),
                reason_code=str(args.reason),
            )
        if args.command == "memory-policy-apply":
            return cmd_memory_policy_apply(
                repo_root,
                explicit_data_root=args.data_root,
                proposal_path=args.proposal,
                confirm_append_only=bool(args.confirm_append_only),
            )
        if args.command == "preview-reopened-prior-routing":
            return cmd_preview_reopened_prior_routing(repo_root, args.data_root)
        if args.command == "vision-acceptance":
            return cmd_vision_acceptance(
                repo_root,
                args.data_root,
                release_root=getattr(args, "release_root", None),
            )
        if args.command == "commission-reopened-priors":
            return cmd_commission_reopened_priors(
                repo_root,
                explicit_data_root=args.data_root,
                confirm_append_only=bool(args.confirm_append_only),
            )
        if args.command == "repair-continuation-draft":
            return cmd_repair_continuation_draft(
                repo_root,
                explicit_data_root=args.data_root,
                parent_session_id=args.parent_session_id,
                owner_authorization_id=args.owner_authorization_id,
                technical_gap_code=args.technical_gap_code,
                spent_main_looks=getattr(args, "spent_main_looks", None),
                spent_adaptive_looks=getattr(args, "spent_adaptive_looks", None),
                spent_preview_looks=getattr(args, "spent_preview_looks", None),
                parent_run_id=getattr(args, "parent_run_id", None),
                terminal_receipt_sha256=getattr(args, "terminal_receipt_sha256", None),
                journal_scope=getattr(args, "journal_scope", None),
                output_path=getattr(args, "output", None),
            )
        if args.command == "repair-continuation-plan":
            return cmd_repair_continuation_plan(
                repo_root,
                explicit_data_root=args.data_root,
                draft_path=args.draft,
                parent_session_id=getattr(args, "parent_session_id", None),
            )
        if args.command == "repair-continuation-apply":
            return cmd_repair_continuation_apply(
                repo_root,
                explicit_data_root=args.data_root,
                draft_path=args.draft,
                parent_session_id=getattr(args, "parent_session_id", None),
                confirm_append_only=bool(args.confirm_append_only),
            )
        if args.command == "repair-continuation-close":
            return cmd_repair_continuation_close(
                repo_root,
                explicit_data_root=args.data_root,
                disposition_sha256=str(getattr(args, "disposition_sha256", "") or ""),
                reason_code=str(
                    getattr(args, "reason_code", None) or "CONTINUATION_TERMINAL_REACHED"
                ),
                confirm_append_only=bool(args.confirm_append_only),
            )
        raise HficCliError(f"HFIC_COMMAND_NOT_READY:{args.command}")
    except RepairContinuationError as exc:
        return emit_repair_blocked(str(exc))
    except (
        HficCliError,
        HficSessionError,
        HficPreflightError,
        HficProspectError,
        HficSuppressionError,
        HficMemoryPolicyError,
        ReopenedPriorRoutingError,
        DataRootError,
        ResearchStoreError,
    ) as exc:
        code = str(exc)
        if str(getattr(args, "command", "") or "").startswith("repair-continuation"):
            return emit_repair_blocked(code)
        return emit_error(code)
    except (OSError, ValueError, json.JSONDecodeError):
        return emit_error("HFIC_PROTOCOL_INVALID")


if __name__ == "__main__":
    sys.exit(main())
