"""Owner-authorized repair continuation after completed NO_WORTHY.

Append-only disposition binds one completed parent search to a one-shot
continuation that inherits the spent look ledger. It does not rewrite the
terminal, refresh budget, or open an unrelated slot.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

DISPOSITION_SCHEMA = "smial.hfic-repair-continuation-disposition"
DISPOSITION_SCHEMA_VERSION = "1.0"
DISPOSITION_ARTIFACT_KIND = "REPAIR_CONTINUATION_DISPOSITION_V1"
REPAIR_CAPABILITY_ID = "CAP-HFIC-TEMPORAL-OPERABILITY-REPAIR-001"
ACTION_RESUME_REPAIR_CONTINUATION = "RESUME_REPAIR_CONTINUATION"
REASON_OWNER_AUTHORIZED_REPAIR_CONTINUATION = "OWNER_AUTHORIZED_REPAIR_CONTINUATION"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class RepairContinuationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _require_hex64(value: object, code: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise RepairContinuationError(code)
    return value


def _require_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RepairContinuationError(code)
    return value.strip()


def disposition_identity(body: Mapping[str, Any]) -> str:
    return _sha256(
        {
            "schema": DISPOSITION_SCHEMA,
            "schema_version": DISPOSITION_SCHEMA_VERSION,
            "parent_run_id": body.get("parent_run_id"),
            "parent_session_id": body.get("parent_session_id"),
            "scientific_slot_sha256": body.get("scientific_slot_sha256"),
            "terminal_receipt_sha256": body.get("terminal_receipt_sha256"),
            "journal_scope": body.get("journal_scope"),
            "technical_gap_code": body.get("technical_gap_code"),
            "repair_capability_id": body.get("repair_capability_id"),
            "allowed_look_ids": list(body.get("allowed_look_ids") or []),
            "spent_main_looks": body.get("spent_main_looks"),
            "spent_adaptive_looks": body.get("spent_adaptive_looks"),
            "spent_preview_looks": body.get("spent_preview_looks"),
            "owner_authorization_id": body.get("owner_authorization_id"),
        }
    )


def validate_disposition_draft(draft: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(draft, Mapping):
        raise RepairContinuationError("DISPOSITION_INVALID")
    if draft.get("schema") not in (None, DISPOSITION_SCHEMA):
        raise RepairContinuationError("DISPOSITION_SCHEMA_INVALID")
    if draft.get("schema_version") not in (None, DISPOSITION_SCHEMA_VERSION):
        raise RepairContinuationError("DISPOSITION_SCHEMA_INVALID")
    parent_run_id = _require_text(draft.get("parent_run_id"), "PARENT_RUN_REQUIRED")
    parent_session_id = _require_text(
        draft.get("parent_session_id"), "PARENT_SESSION_REQUIRED"
    )
    slot = _require_hex64(
        draft.get("scientific_slot_sha256"), "SCIENTIFIC_SLOT_REQUIRED"
    )
    terminal = _require_hex64(
        draft.get("terminal_receipt_sha256"), "TERMINAL_RECEIPT_REQUIRED"
    )
    journal_scope = _require_text(draft.get("journal_scope"), "JOURNAL_SCOPE_REQUIRED")
    gap = _require_text(draft.get("technical_gap_code"), "TECHNICAL_GAP_REQUIRED")
    capability = _require_text(
        draft.get("repair_capability_id"), "REPAIR_CAPABILITY_REQUIRED"
    )
    if capability != REPAIR_CAPABILITY_ID:
        raise RepairContinuationError("REPAIR_CAPABILITY_MISMATCH")
    auth = _require_text(
        draft.get("owner_authorization_id"), "OWNER_AUTHORIZATION_REQUIRED"
    )
    terminal_kind = str(draft.get("parent_terminal") or "NO_WORTHY_HYPOTHESIS")
    if terminal_kind != "NO_WORTHY_HYPOTHESIS":
        raise RepairContinuationError("PARENT_TERMINAL_NOT_ELIGIBLE")
    if draft.get("selected_candidate_id") not in (None, ""):
        raise RepairContinuationError("PARENT_HAS_SELECTED_CANDIDATE")
    allowed_looks = draft.get("allowed_look_ids") or []
    if not isinstance(allowed_looks, list):
        raise RepairContinuationError("ALLOWED_LOOKS_INVALID")
    looks = [str(item) for item in allowed_looks if isinstance(item, str) and item]
    spent_main = draft.get("spent_main_looks")
    spent_adaptive = draft.get("spent_adaptive_looks")
    spent_preview = draft.get("spent_preview_looks")
    for label, value in (
        ("spent_main_looks", spent_main),
        ("spent_adaptive_looks", spent_adaptive),
        ("spent_preview_looks", spent_preview),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RepairContinuationError("SPENT_BUDGET_INVALID")
    body = {
        "schema": DISPOSITION_SCHEMA,
        "schema_version": DISPOSITION_SCHEMA_VERSION,
        "artifact_kind": DISPOSITION_ARTIFACT_KIND,
        "parent_run_id": parent_run_id,
        "parent_session_id": parent_session_id,
        "scientific_slot_sha256": slot,
        "terminal_receipt_sha256": terminal,
        "parent_terminal": terminal_kind,
        "journal_scope": journal_scope,
        "technical_gap_code": gap,
        "repair_capability_id": capability,
        "allowed_look_ids": looks,
        "spent_main_looks": int(spent_main),
        "spent_adaptive_looks": int(spent_adaptive),
        "spent_preview_looks": int(spent_preview),
        "owner_authorization_id": auth,
        "status": "AUTHORIZED",
        "evidence_mapping": dict(draft.get("evidence_mapping") or {}),
        "non_claims": [
            "NO_BUDGET_REFRESH",
            "NO_TERMINAL_REWRITE",
            "NO_LIVE_APPLY_IN_REPAIR_ATOM",
            "NO_MEMORY_RESET",
        ],
    }
    body["disposition_sha256"] = disposition_identity(body)
    return body


def plan_repair_continuation(
    draft: Mapping[str, Any],
    *,
    parent_session: Mapping[str, Any] | None,
    existing_dispositions: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """No-write readiness plan for one repair continuation."""

    body = validate_disposition_draft(draft)
    if not isinstance(parent_session, Mapping):
        return _owner_plan(
            status="NOT_APPLICABLE",
            reason_code="PARENT_SESSION_MISSING",
            writes=False,
            disposition=body,
            owner_status="BLOCKED",
            next_step="PROVIDE_PARENT_SESSION_ID_FROM_SHOW_SESSION",
        )
    session_id = str(parent_session.get("session_id") or "")
    if session_id != body["parent_session_id"]:
        return _owner_plan(
            status="NOT_APPLICABLE",
            reason_code="PARENT_SESSION_MISMATCH",
            writes=False,
            disposition=body,
            owner_status="BLOCKED",
            next_step="ALIGN_DRAFT_PARENT_SESSION_ID",
        )
    terminal = str(
        parent_session.get("critic_terminal")
        or parent_session.get("final_session_terminal")
        or parent_session.get("owner_final")
        or parent_session.get("session_state")
        or parent_session.get("phase")
        or ""
    )
    # Strict eligibility: parent must be a completed NO_WORTHY close.
    # Broad COMPLETED/DONE alone is not enough — that would reopen chosen work.
    if terminal != "NO_WORTHY_HYPOTHESIS" and "NO_WORTHY" not in terminal:
        return _owner_plan(
            status="NOT_APPLICABLE",
            reason_code="PARENT_NOT_COMPLETED_NO_WORTHY",
            writes=False,
            disposition=body,
            owner_status="BLOCKED",
            next_step="STOP_SCIENTIFIC_CLOSE_STANDS",
        )
    parent_slot = parent_session.get("scientific_slot_sha256")
    if (
        isinstance(parent_slot, str)
        and parent_slot
        and parent_slot != body["scientific_slot_sha256"]
    ):
        return _owner_plan(
            status="NOT_APPLICABLE",
            reason_code="PARENT_SLOT_MISMATCH",
            writes=False,
            disposition=body,
            owner_status="BLOCKED",
            next_step="ALIGN_DRAFT_SCIENTIFIC_SLOT",
        )
    # Prefer store-declared spent counts when the parent already recorded them.
    for key in ("spent_main_looks", "spent_adaptive_looks", "spent_preview_looks"):
        observed = parent_session.get(key)
        if (
            isinstance(observed, int)
            and not isinstance(observed, bool)
            and int(observed) != int(body[key])
        ):
            return _owner_plan(
                status="NOT_APPLICABLE",
                reason_code="SPENT_BUDGET_MISMATCH",
                writes=False,
                disposition=body,
                owner_status="BLOCKED",
                next_step="ALIGN_DRAFT_SPENT_LOOKS_TO_PARENT",
            )
    if parent_session.get("selected_candidate_id") not in (None, ""):
        return _owner_plan(
            status="NOT_APPLICABLE",
            reason_code="PARENT_HAS_SELECTED_CANDIDATE",
            writes=False,
            disposition=body,
            owner_status="BLOCKED",
            next_step="STOP_SELECTED_CANDIDATE_NOT_REPAIRABLE_HERE",
        )
    for item in existing_dispositions:
        if not isinstance(item, Mapping):
            continue
        if item.get("disposition_sha256") == body["disposition_sha256"]:
            return _owner_plan(
                status="ALREADY_APPLIED",
                reason_code="IDEMPOTENT_REPLAY",
                writes=False,
                disposition=dict(item),
                owner_status="DONE",
                next_step="ORDINARY_TEMPORAL_QUERY_WITHIN_REMAINING_BUDGET",
                remaining_main_looks=max(0, 6 - int(body["spent_main_looks"])),
                remaining_adaptive_looks=max(0, 2 - int(body["spent_adaptive_looks"])),
            )
        if (
            item.get("parent_session_id") == body["parent_session_id"]
            and item.get("status") == "AUTHORIZED"
            and item.get("disposition_sha256") != body["disposition_sha256"]
        ):
            return _owner_plan(
                status="CONFLICT",
                reason_code="COMPETING_ACTIVE_DISPOSITION",
                writes=False,
                disposition=body,
                owner_status="BLOCKED",
                next_step="RESOLVE_COMPETING_DISPOSITION_OR_STOP",
            )
    return _owner_plan(
        status="READY",
        reason_code=REASON_OWNER_AUTHORIZED_REPAIR_CONTINUATION,
        writes=False,
        disposition=body,
        owner_status="READY",
        next_step="APPLY_WITH_EXPLICIT_CONFIRM_APPEND_ONLY",
        remaining_main_looks=max(0, 6 - int(body["spent_main_looks"])),
        remaining_adaptive_looks=max(0, 2 - int(body["spent_adaptive_looks"])),
        remaining_preview_looks=max(0, 2 - int(body["spent_preview_looks"])),
        apply_requires="EXPLICIT_OWNER_APPLY_AUTHORITY",
    )


def _owner_plan(
    *,
    status: str,
    reason_code: str,
    writes: bool,
    disposition: Mapping[str, Any],
    owner_status: str,
    next_step: str,
    remaining_main_looks: int | None = None,
    remaining_adaptive_looks: int | None = None,
    remaining_preview_looks: int | None = None,
    apply_requires: str | None = None,
) -> dict[str, Any]:
    """Machine plan plus owner-facing DONE/BLOCKED/READY/NEXT fields."""

    payload: dict[str, Any] = {
        "status": status,
        "reason_code": reason_code,
        "writes": writes,
        "disposition": dict(disposition),
        "owner_status": owner_status,
        "next_step": next_step,
        "owner_readout": {
            "status": owner_status,
            "reason_code": reason_code,
            "next": next_step,
            "writes": writes,
        },
    }
    if remaining_main_looks is not None:
        payload["remaining_main_looks"] = remaining_main_looks
    if remaining_adaptive_looks is not None:
        payload["remaining_adaptive_looks"] = remaining_adaptive_looks
    if remaining_preview_looks is not None:
        payload["remaining_preview_looks"] = remaining_preview_looks
    if apply_requires is not None:
        payload["apply_requires"] = apply_requires
    return payload


TARGET_EXCLUSION_OWNER_GLOSSARY = {
    "REQUEST_NOT_AFTER_ENTRY": (
        "Exit snapshot request did not start after entry (decision cutoff + assumed latency)."
    ),
    "ACQUISITION_BEFORE_POINT_DUE": (
        "Snapshot request started before the exit point due; early scrape cannot stand in for a later Y."
    ),
    "AVAILABILITY_AFTER_DEADLINE": (
        "First reliable availability arrived after the exit point deadline."
    ),
    "CLOCK_ORDER_INVALID": (
        "Required order due ≤ request ≤ response ≤ availability was broken."
    ),
    "MISSING_ACQUISITION_CLOCK": (
        "Request, response or availability clock missing; treat as UNKNOWN, not a negative return."
    ),
    "SOURCE_PRICE_EVENT_STALE": (
        "A proven source price event is outside the exit deadline; not hidden by HTTP timing."
    ),
    "EVENT_NOT_AFTER_ENTRY": (
        "Legacy EVENT_TIME_V1: event_time was not after entry (often member anchor)."
    ),
    "REFERENCE_NOT_AVAILABLE": (
        "Reference snapshot was not available by decision cutoff and its own point deadline."
    ),
    "EXIT_ABSENT": "No exit observation rows for the target point.",
    "EXIT_NOT_OBSERVED": "Exit row present but not OBSERVED.",
    "TARGET_UNOBSERVED": "Matched member without an observed target for another reason.",
}


def explain_target_exclusion(code: str) -> str:
    return TARGET_EXCLUSION_OWNER_GLOSSARY.get(
        str(code), "Unknown target exclusion; inspect result.target_exclusion_reasons."
    )


def _lookup_forge_run_for_parent(
    store: Any,
    *,
    session_id: str,
    scientific_slot_sha256: str | None,
) -> dict[str, Any] | None:
    """Latest FORGE_RUN_RECEIPT matching session or scientific slot."""

    latest: dict[str, Any] | None = None
    completed: dict[str, Any] | None = None
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        try:
            wrapper = json.loads(record.payload_json)
            body = json.loads(str(wrapper.get("payload_canonical") or ""))
        except (TypeError, json.JSONDecodeError, AttributeError):
            continue
        if not isinstance(body, dict):
            continue
        if wrapper.get("artifact_kind") != "FORGE_RUN_RECEIPT":
            continue
        match_session = str(body.get("session_id") or "") == session_id
        match_slot = (
            isinstance(scientific_slot_sha256, str)
            and scientific_slot_sha256
            and body.get("scientific_slot_sha256") == scientific_slot_sha256
        )
        if not (match_session or match_slot):
            continue
        latest = body
        if body.get("owner_final"):
            completed = body
    return completed or latest


def spent_looks_from_journal(store: Any, journal_scope: str) -> dict[str, Any]:
    """Count spent discovery looks for one journal scope. No writes."""

    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks

    looks = list_discovery_looks(store, journal_scope)
    main = 0
    adaptive = 0
    preview = 0
    look_ids: list[str] = []
    for item in looks:
        if not isinstance(item, Mapping):
            continue
        if item.get("new_look") is False:
            continue
        look_class = str(item.get("look_class") or "")
        record_id = str(item.get("record_id") or item.get("spec_sha256") or "")
        if record_id:
            look_ids.append(record_id)
        if look_class == "MAIN":
            main += 1
        elif look_class == "ADAPTIVE":
            adaptive += 1
        elif look_class == "PREVIEW":
            preview += 1
    return {
        "spent_main_looks": main,
        "spent_adaptive_looks": adaptive,
        "spent_preview_looks": preview,
        "allowed_look_ids": look_ids,
        "look_count": len(looks),
    }


def enrich_parent_for_repair_draft(
    store: Any,
    parent_session: Mapping[str, Any],
) -> dict[str, Any]:
    """Fill run_id / terminal receipt / spent looks from store when absent."""

    parent = dict(parent_session)
    session_id = str(parent.get("session_id") or "")
    slot = parent.get("scientific_slot_sha256")
    if not parent.get("run_id") and not parent.get("forge_run_id"):
        receipt = _lookup_forge_run_for_parent(
            store,
            session_id=session_id,
            scientific_slot_sha256=str(slot) if isinstance(slot, str) else None,
        )
        if isinstance(receipt, Mapping):
            if receipt.get("run_id"):
                parent["run_id"] = receipt.get("run_id")
                parent["forge_run_id"] = receipt.get("run_id")
            if (
                not parent.get("scientific_slot_sha256")
                and isinstance(receipt.get("scientific_slot_sha256"), str)
            ):
                parent["scientific_slot_sha256"] = receipt.get("scientific_slot_sha256")
    if not parent.get("terminal_receipt_sha256"):
        parent["terminal_receipt_sha256"] = parent.get("session_receipt_sha256")
    scope = (
        parent.get("journal_scope")
        or parent.get("search_key_sha256")
    )
    if isinstance(scope, str) and scope.strip():
        parent.setdefault("journal_scope", scope.strip())
        spent = spent_looks_from_journal(store, scope.strip())
        for key in (
            "spent_main_looks",
            "spent_adaptive_looks",
            "spent_preview_looks",
        ):
            if parent.get(key) is None:
                parent[key] = spent[key]
        if not parent.get("allowed_look_ids"):
            parent["allowed_look_ids"] = list(spent["allowed_look_ids"])
        parent["spent_looks_source"] = "DISCOVERY_JOURNAL"
    return parent


def build_repair_continuation_draft(
    parent_session: Mapping[str, Any],
    *,
    owner_authorization_id: str,
    technical_gap_code: str,
    parent_run_id: str | None = None,
    terminal_receipt_sha256: str | None = None,
    journal_scope: str | None = None,
    spent_main_looks: int | None = None,
    spent_adaptive_looks: int | None = None,
    spent_preview_looks: int | None = None,
    allowed_look_ids: Sequence[str] | None = None,
    example_exclusion_code: str | None = None,
) -> dict[str, Any]:
    """Build a disposition draft from show-session fields. No store writes."""

    session_id = _require_text(
        parent_session.get("session_id"), "PARENT_SESSION_REQUIRED"
    )
    slot = parent_session.get("scientific_slot_sha256")
    if not isinstance(slot, str) or _HEX64.fullmatch(slot) is None:
        raise RepairContinuationError("SCIENTIFIC_SLOT_REQUIRED")
    run_id = parent_run_id or parent_session.get("run_id") or parent_session.get(
        "forge_run_id"
    )
    if not isinstance(run_id, str) or not run_id.strip():
        raise RepairContinuationError("PARENT_RUN_REQUIRED")
    receipt = terminal_receipt_sha256 or parent_session.get(
        "terminal_receipt_sha256"
    ) or parent_session.get("session_receipt_sha256") or parent_session.get(
        "critic_result_sha256"
    )
    if not isinstance(receipt, str) or _HEX64.fullmatch(receipt) is None:
        raise RepairContinuationError("TERMINAL_RECEIPT_REQUIRED")
    scope = journal_scope or parent_session.get("journal_scope") or parent_session.get(
        "search_key_sha256"
    )
    if not isinstance(scope, str) or not scope.strip():
        raise RepairContinuationError("JOURNAL_SCOPE_REQUIRED")
    main = (
        spent_main_looks
        if spent_main_looks is not None
        else parent_session.get("spent_main_looks")
    )
    adaptive = (
        spent_adaptive_looks
        if spent_adaptive_looks is not None
        else parent_session.get("spent_adaptive_looks")
    )
    preview = (
        spent_preview_looks
        if spent_preview_looks is not None
        else parent_session.get("spent_preview_looks")
    )
    for label, value in (
        ("spent_main_looks", main),
        ("spent_adaptive_looks", adaptive),
        ("spent_preview_looks", preview),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RepairContinuationError("SPENT_BUDGET_INVALID")
    looks = list(allowed_look_ids or parent_session.get("allowed_look_ids") or [])
    draft = {
        "schema": DISPOSITION_SCHEMA,
        "schema_version": DISPOSITION_SCHEMA_VERSION,
        "parent_run_id": str(run_id).strip(),
        "parent_session_id": session_id,
        "scientific_slot_sha256": slot,
        "terminal_receipt_sha256": receipt,
        "journal_scope": str(scope).strip(),
        "technical_gap_code": _require_text(technical_gap_code, "TECHNICAL_GAP_REQUIRED"),
        "repair_capability_id": REPAIR_CAPABILITY_ID,
        "allowed_look_ids": [str(item) for item in looks if isinstance(item, str) and item],
        "spent_main_looks": int(main),
        "spent_adaptive_looks": int(adaptive),
        "spent_preview_looks": int(preview),
        "owner_authorization_id": _require_text(
            owner_authorization_id, "OWNER_AUTHORIZATION_REQUIRED"
        ),
        "parent_terminal": "NO_WORTHY_HYPOTHESIS",
    }
    if example_exclusion_code:
        draft["example_exclusion_code"] = str(example_exclusion_code)
    return draft


def list_repair_continuation_dispositions(store: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        try:
            wrapper = json.loads(record.payload_json)
            body = json.loads(str(wrapper.get("payload_canonical") or ""))
        except (TypeError, json.JSONDecodeError, AttributeError):
            continue
        if not isinstance(body, dict):
            continue
        if body.get("artifact_kind") != DISPOSITION_ARTIFACT_KIND:
            continue
        rows.append(body)
    return rows


def apply_repair_continuation(
    store: Any,
    draft: Mapping[str, Any],
    *,
    parent_session: Mapping[str, Any] | None,
    git_sha: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Append one disposition. Repeat with the same authorization is idempotent."""

    existing = list_repair_continuation_dispositions(store)
    plan = plan_repair_continuation(
        draft, parent_session=parent_session, existing_dispositions=existing
    )
    if plan["status"] == "ALREADY_APPLIED":
        return {**plan, "applied": False, "idempotent": True}
    if plan["status"] != "READY":
        raise RepairContinuationError(str(plan.get("reason_code") or "NOT_READY"))
    body = dict(plan["disposition"])
    moment = now or datetime.now(timezone.utc)
    canonical = _canonical(body)
    payload = {
        "artifact_kind": DISPOSITION_ARTIFACT_KIND,
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    identity = body["disposition_sha256"]
    event = ResearchEvent(
        record_id=f"HFIC-ART-REPAIR-CONT-{identity[:40].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"HFIC-ART-REPAIR-CONT-{identity[:40].upper()}",
        hypothesis_version_id=None,
        run_id=str(body["parent_run_id"]),
        transaction_id=f"RESEARCH-TXN-REPAIR-CONT-{identity[:24].upper()}",
        effective_at=moment,
        first_reliable_available_at=moment,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=REPAIR_CAPABILITY_ID,
        producer_git_sha=git_sha,
        created_at=moment,
    )
    store.append([event], transaction_id=event.transaction_id)
    applied_plan = {
        **plan,
        "status": "APPLIED",
        "applied": True,
        "idempotent": False,
        "record_id": event.record_id,
        "writes": True,
        "owner_status": "DONE",
        "next_step": "ORDINARY_TEMPORAL_QUERY_WITHIN_REMAINING_BUDGET",
    }
    applied_plan["owner_readout"] = {
        "status": "DONE",
        "reason_code": REASON_OWNER_AUTHORIZED_REPAIR_CONTINUATION,
        "next": applied_plan["next_step"],
        "writes": True,
    }
    return applied_plan


def active_repair_continuation_for_slot(
    dispositions: Sequence[Mapping[str, Any]],
    *,
    scientific_slot_sha256: str,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    matches = []
    for item in dispositions:
        if not isinstance(item, Mapping):
            continue
        if item.get("status") != "AUTHORIZED":
            continue
        if item.get("scientific_slot_sha256") != scientific_slot_sha256:
            continue
        if session_id and item.get("parent_session_id") != session_id:
            continue
        matches.append(item)
    if not matches:
        return None
    matches.sort(key=lambda row: str(row.get("disposition_sha256") or ""))
    return dict(matches[0])


def admission_with_repair_continuation(
    admission: Mapping[str, Any],
    *,
    dispositions: Sequence[Mapping[str, Any]],
    parent_terminal: str | None = None,
) -> dict[str, Any]:
    """Overlay slot admission when an authorized repair continuation is active."""

    result = dict(admission)
    if result.get("action") not in {"RETURN_EXISTING_SESSION", "STOP"}:
        return result
    slot = str(result.get("scientific_slot_sha256") or "")
    session_id = result.get("session_id")
    if not slot:
        return result
    disposition = active_repair_continuation_for_slot(
        dispositions,
        scientific_slot_sha256=slot,
        session_id=str(session_id) if session_id else None,
    )
    if disposition is None:
        return result
    # Overlay only when the occupied parent is a NO_WORTHY close.
    if parent_terminal is not None and "NO_WORTHY" not in str(parent_terminal):
        return result
    result["action"] = ACTION_RESUME_REPAIR_CONTINUATION
    result["reason_code"] = REASON_OWNER_AUTHORIZED_REPAIR_CONTINUATION
    result["occupancy"] = "REPAIR_CONTINUATION"
    result["repair_continuation_disposition_sha256"] = disposition.get(
        "disposition_sha256"
    )
    result["spent_main_looks"] = disposition.get("spent_main_looks")
    result["spent_adaptive_looks"] = disposition.get("spent_adaptive_looks")
    result["spent_preview_looks"] = disposition.get("spent_preview_looks")
    return result
