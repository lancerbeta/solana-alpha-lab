#!/usr/bin/env python3
"""Thin network-free CLI for Hypothesis Forge operational sessions."""

from __future__ import annotations

import argparse
import importlib.util
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


def emit_error(code: str, *, exit_code: int = 1) -> int:
    print(code, file=sys.stderr)
    return exit_code


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


def cmd_preflight(
    repo_root: Path,
    *,
    owner_focus: str,
    auto_commission: bool,
    explicit_data_root: Path | None,
    control_current_representation: bool = False,
) -> int:
    _assert_no_path_leak({"owner_focus": owner_focus}, str(repo_root))
    try:
        active = _active_root(repo_root, explicit_data_root)
        data_root = active.root
    except DataRootError as exc:
        payload = {
            "action": "STOP",
            "terminal": str(exc),
            "owner_focus": owner_focus,
            "data_root_instance_fingerprint": None,
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
        )
    except HficPreflightError as exc:
        payload = {
            "action": "STOP",
            "terminal": str(exc),
            "owner_focus": owner_focus,
            **active.redacted_receipt(),
        }
        _assert_no_path_leak(payload, str(data_root), str(repo_root))
        return emit(payload, exit_code=2)
    payload = {
        **active.redacted_receipt(),
        **receipt,
    }
    payload["preflight_receipt_sha256"] = canonical_preflight_receipt_sha256(payload)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    exit_code = 0 if receipt["action"] != "STOP" else 2
    return emit(payload, exit_code=exit_code)


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
            "packet_within_bound": packet_bytes <= 16384,
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


def cmd_prove_runtime(
    repo_root: Path,
    session_id: str,
    explicit_data_root: Path | None,
) -> int:
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = prove_runtime(store, session_id, repo_root=repo_root)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


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
    )

    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    try:
        receipts = collect_session_receipts(store)
        payload = aggregate_diagnostics(receipts, last_n)
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
    census: Path,
    observations: Path,
) -> int:
    from solana_alpha_lab.factory.hfic_censoring_ignorability_diagnostic import (
        CensoringDiagnosticError,
        EXPLICIT_RELEASE_PATHS_REQUIRED,
        run_censoring_ignorability_diagnostic,
    )

    if census is None or observations is None:
        raise HficCliError(EXPLICIT_RELEASE_PATHS_REQUIRED)
    try:
        receipt = run_censoring_ignorability_diagnostic(
            root=repo_root,
            census_path=census,
            observations_path=observations,
        )
    except CensoringDiagnosticError as exc:
        raise HficCliError(str(exc)) from exc
    _assert_no_path_leak(receipt, str(repo_root), str(census), str(observations))
    return emit(receipt)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hypothesis_forge")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--data-root", type=Path, default=None)
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
        help="offline X300 selection diagnostic; requires explicit census and observations parquet; never defaults to active RDP",
    )
    censoring.add_argument("--census", type=Path, required=True)
    censoring.add_argument("--observations", type=Path, required=True)
    censoring.add_argument("--format", choices=("json",), default="json")

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
        raise HficCliError(f"HFIC_COMMAND_NOT_READY:{args.command}")
    except (HficCliError, HficSessionError, HficPreflightError, HficProspectError, HficSuppressionError, HficMemoryPolicyError, ReopenedPriorRoutingError, DataRootError, ResearchStoreError) as exc:
        return emit_error(str(exc))
    except (OSError, ValueError, json.JSONDecodeError):
        return emit_error("HFIC_PROTOCOL_INVALID")


if __name__ == "__main__":
    sys.exit(main())
