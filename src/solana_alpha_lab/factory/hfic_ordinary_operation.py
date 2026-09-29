"""Ordinary owner-request binding for one journal.

This is operational metadata. Admission, journal budget and tier progress
stay in their existing owners. A hash is not owner will; the stored text is
the explicit request this call was given.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from solana_alpha_lab.factory.hfic_grounded_discovery import (
    MAX_ADAPTIVE_REFINEMENTS,
    MAX_MAIN_QUERY_SPECS,
    POINT_OFFSET,
    _canonical,
    list_discovery_looks,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import MAX_PREVIEW_SPECS

OPERATION_KIND = "ORDINARY_OPERATION_V1"
RESERVATION_KIND = "ORDINARY_LOOK_RESERVATION_V1"
LIMITED_RESULT = "LIMITED_RESULT"
SCIENTIFIC_TERMINAL = "SCIENTIFIC_TERMINAL"


class OrdinaryOperationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _sha(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _load_body(record: Any) -> dict[str, Any] | None:
    try:
        wrapper = json.loads(record.payload_json)
        body = json.loads(str(wrapper.get("payload_canonical") or ""))
    except (TypeError, json.JSONDecodeError, AttributeError):
        return None
    return body if isinstance(body, dict) else None


def _iter_kind(store: Any, kind: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        record_kind = getattr(record.record_kind, "value", record.record_kind)
        if record_kind != "RESEARCH_ARTIFACT":
            continue
        body = _load_body(record)
        if isinstance(body, dict) and body.get("artifact_kind") == kind:
            body["record_id"] = str(getattr(record, "record_id", "") or "")
            found.append(body)
    return found


def list_operations(store: Any) -> list[dict[str, Any]]:
    return _iter_kind(store, OPERATION_KIND)


def get_operation(store: Any, operation_sha256: str) -> dict[str, Any]:
    found = [item for item in list_operations(store) if item.get("operation_sha256") == operation_sha256]
    if not found:
        raise OrdinaryOperationError("ORDINARY_OPERATION_NOT_FOUND")
    return found[-1]


def _cap_field(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OrdinaryOperationError("ORDINARY_OPERATION_CAP_INVALID")
    return value


def record_operation(store: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    """Persist one explicit owner request. The same bytes return the same row."""

    text = request.get("owner_request_text")
    if not isinstance(text, str) or not text.strip():
        raise OrdinaryOperationError("ORDINARY_OPERATION_REQUEST_REQUIRED")
    spec = request.get("spec")
    if not isinstance(spec, Mapping):
        raise OrdinaryOperationError("ORDINARY_OPERATION_SPEC_REQUIRED")
    journal = str(request.get("journal_scope") or "").strip()
    focus = str(request.get("owner_focus") or "").strip()
    market = str(request.get("market_evidence_epoch_sha256") or "").strip()
    if len(journal) != 64 or not focus or len(market) != 64:
        raise OrdinaryOperationError("ORDINARY_OPERATION_BINDING_INCOMPLETE")
    completion = str(request.get("requested_completion") or LIMITED_RESULT)
    if completion not in {LIMITED_RESULT, SCIENTIFIC_TERMINAL}:
        raise OrdinaryOperationError("ORDINARY_OPERATION_COMPLETION_INVALID")
    cap_in = request.get("owner_cap") if isinstance(request.get("owner_cap"), Mapping) else {}
    cap = {
        "main": _cap_field(cap_in.get("main")),
        "adaptive": _cap_field(cap_in.get("adaptive")),
        "preview": _cap_field(cap_in.get("preview")),
    }
    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query

    try:
        validated = validate_temporal_query(spec)
    except Exception as exc:
        code = getattr(exc, "code", None) or "QUERY_SPEC_INVALID"
        raise OrdinaryOperationError(str(code)) from exc
    parent = request.get("parent_operation_sha256")
    if parent is not None and (not isinstance(parent, str) or len(parent) != 64):
        raise OrdinaryOperationError("ORDINARY_OPERATION_PARENT_INVALID")
    if isinstance(parent, str):
        prior = get_operation(store, parent)
        if prior.get("status") == "STOPPED":
            raise OrdinaryOperationError("ORDINARY_OPERATION_STOPPED")
        if prior.get("journal_scope") != journal or prior.get("owner_focus") != focus:
            raise OrdinaryOperationError("ORDINARY_OPERATION_CONTINUATION_MISMATCH")
    slot = str(request.get("scientific_slot_sha256") or "")
    if len(slot) != 64:
        from solana_alpha_lab.factory.hfic_evidence_identity import scientific_slot_sha256

        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus=focus,
        )
    identity_body = {
        "artifact_kind": OPERATION_KIND,
        "owner_request_text": text.strip(),
        "owner_focus": focus,
        "journal_scope": journal,
        "market_evidence_epoch_sha256": market,
        "scientific_slot_sha256": slot,
        "spec_canonical": _canonical(dict(spec)),
        "spec_sha256": validated["spec_sha256"],
        "question_text": str(request.get("question_text") or text.strip()),
        "owner_cap": cap,
        "requested_completion": completion,
        "parent_operation_sha256": parent,
    }
    digest = _sha(identity_body)
    for existing in list_operations(store):
        if existing.get("operation_sha256") == digest:
            return existing
    stored = {
        **identity_body,
        "operation_sha256": digest,
        "status": "OPEN",
        "schema": "smial.hfic-ordinary-operation",
        "schema_version": "1.0",
    }
    _append(store, kind=OPERATION_KIND, body=stored, record_prefix="HFIC-ART-OP")
    stored["record_id"] = f"HFIC-ART-OP-{digest[:40].upper()}"
    return stored


def _append(store: Any, *, kind: str, body: Mapping[str, Any], record_prefix: str) -> None:
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = datetime.now(timezone.utc)
    canonical = _canonical(dict(body))
    identity = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    payload = {
        "artifact_kind": kind,
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    event = ResearchEvent(
        record_id=f"{record_prefix}-{identity[:40].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"{record_prefix}-{identity[:40].upper()}",
        hypothesis_version_id=None,
        run_id=f"HFIC-OP-{identity[:16].upper()}",
        transaction_id=f"RESEARCH-TXN-OP-{identity[:24].upper()}",
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-HFIC-ORDINARY-OPERATION-001",
        producer_git_sha="0" * 40,
        created_at=now,
    )
    store.append([event], transaction_id=event.transaction_id)


def _looks(store: Any, journal: str) -> list[dict[str, Any]]:
    return list_discovery_looks(store, journal)


def _protocol_remaining(looks: Sequence[Mapping[str, Any]], kind: str) -> int:
    if kind == "preview":
        used = sum(1 for item in looks if item.get("look_class") == "PREVIEW" and item.get("new_look") is True)
        return max(0, MAX_PREVIEW_SPECS - used)
    if kind == "adaptive":
        used = sum(1 for item in looks if item.get("look_class") == "ADAPTIVE" and item.get("new_look") is True)
        return max(0, MAX_ADAPTIVE_REFINEMENTS - used)
    used = sum(1 for item in looks if item.get("look_class") == "MAIN" and item.get("new_look") is True)
    return max(0, MAX_MAIN_QUERY_SPECS - used)


def _reservations(store: Any, operation_sha256: str) -> list[dict[str, Any]]:
    return [
        item
        for item in _iter_kind(store, RESERVATION_KIND)
        if item.get("operation_sha256") == operation_sha256
    ]


def _spent_by_operation(store: Any, operation: Mapping[str, Any], kind: str) -> int:
    journal = str(operation.get("journal_scope") or "")
    digest = str(operation.get("operation_sha256") or "")
    looks = [
        item
        for item in _looks(store, journal)
        if item.get("operation_sha256") == digest and item.get("new_look") is True
    ]
    look_class = {"main": "MAIN", "adaptive": "ADAPTIVE", "preview": "PREVIEW"}[kind]
    done = {str(item.get("spec_sha256") or "") for item in looks if item.get("look_class") == look_class}
    pending = {
        str(item.get("spec_sha256") or "")
        for item in _reservations(store, digest)
        if item.get("look_class") == look_class and str(item.get("spec_sha256") or "") not in done
    }
    return len(done) + len(pending)


def owner_allowance(store: Any, operation: Mapping[str, Any], kind: str) -> int:
    """Explicit cap wins when it is smaller than the protocol remainder."""

    looks = _looks(store, str(operation.get("journal_scope") or ""))
    protocol = _protocol_remaining(looks, kind)
    explicit = (operation.get("owner_cap") or {}).get(kind)
    if explicit is None:
        return protocol
    spent = _spent_by_operation(store, operation, kind)
    return max(0, min(int(explicit) - spent, protocol))


def _admit(store: Any, operation: Mapping[str, Any]) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_evidence_identity import resolve_scientific_admission
    from solana_alpha_lab.factory.hfic_preflight import (
        AUTO_SESSIONS_PER_EPOCH,
        MAX_DISTINCT_FOCUSES_PER_EPOCH,
    )
    from solana_alpha_lab.factory.hfic_repair_continuation import (
        list_repair_continuation_dispositions,
    )
    from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

    sessions = list_hfic_sessions(store)
    return resolve_scientific_admission(
        sessions,
        market_evidence_epoch=str(operation.get("market_evidence_epoch_sha256") or ""),
        representation_id="BASE",
        representation_semantic_version="HFIC-V1.2",
        owner_focus=str(operation.get("owner_focus") or ""),
        auto_sessions_per_market=AUTO_SESSIONS_PER_EPOCH,
        max_distinct_focuses=MAX_DISTINCT_FOCUSES_PER_EPOCH,
        repair_continuations=list_repair_continuation_dispositions(store),
    )


def _search_terminal_conflict(operation: Mapping[str, Any], looks: Sequence[Mapping[str, Any]], spec: Mapping[str, Any]) -> None:
    if operation.get("requested_completion") != SCIENTIFIC_TERMINAL:
        return
    from solana_alpha_lab.factory.hfic_temporal_discovery import (
        assess_tier_progress,
        validate_temporal_query,
    )

    validated = validate_temporal_query(spec)
    progress = assess_tier_progress(looks, freeze_worthy=False, compound_applicable=True)
    explicit_main = (operation.get("owner_cap") or {}).get("main")
    if (
        validated.get("search_tier") == "SIMPLE_SCREEN"
        and explicit_main == 1
        and progress.get("search_exhausted_allowed") is not True
        and progress.get("compound_executed") is not True
    ):
        raise OrdinaryOperationError("OPERATION_SEARCH_TERMINAL_CONFLICT")


def _closed_slot(admission: Mapping[str, Any], sessions: Sequence[Mapping[str, Any]]) -> bool:
    if admission.get("occupancy") == "REPAIR_CLOSED_READBACK":
        return True
    if admission.get("action") != "RETURN_EXISTING_SESSION":
        return False
    session_id = str(admission.get("session_id") or "")
    for item in sessions:
        if str(item.get("session_id") or "") != session_id:
            continue
        terminal = str(item.get("critic_terminal") or item.get("final_session_terminal") or "")
        if "NO_WORTHY" in terminal:
            return True
    return False


def gate_before_values(
    store: Any,
    *,
    operation_sha256: str,
    spec: Mapping[str, Any],
    journal_scope: str,
) -> dict[str, Any]:
    """Metadata, admission and cap. Does not load outcome rows."""

    operation = get_operation(store, operation_sha256)
    if operation.get("status") == "STOPPED":
        raise OrdinaryOperationError("ORDINARY_OPERATION_STOPPED")
    if str(operation.get("journal_scope") or "") != journal_scope:
        raise OrdinaryOperationError("ORDINARY_OPERATION_JOURNAL_MISMATCH")
    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query

    try:
        validated = validate_temporal_query(spec)
    except Exception as exc:
        code = getattr(exc, "code", None) or "QUERY_SPEC_INVALID"
        raise OrdinaryOperationError(str(code)) from exc
    if validated["spec_sha256"] != operation.get("spec_sha256"):
        raise OrdinaryOperationError("ORDINARY_OPERATION_SPEC_MISMATCH")
    if _canonical(dict(spec)) != operation.get("spec_canonical"):
        raise OrdinaryOperationError("ORDINARY_OPERATION_SPEC_MISMATCH")
    looks = _looks(store, journal_scope)
    _search_terminal_conflict(operation, looks, spec)
    from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

    admission = _admit(store, operation)
    if admission.get("action") == "STOP":
        raise OrdinaryOperationError(str(admission.get("reason_code") or "SCIENTIFIC_ADMISSION_STOP"))
    if _closed_slot(admission, list_hfic_sessions(store)):
        raise OrdinaryOperationError("ORDINARY_OPERATION_SLOT_CLOSED")
    stored = next(
        (
            item
            for item in looks
            if item.get("spec_sha256") == validated["spec_sha256"]
            and isinstance(item.get("result"), Mapping)
        ),
        None,
    )
    if stored is not None:
        return {
            "disposition": "REPLAY",
            "values_loaded": False,
            "operation": operation,
            "admission": admission,
            "evidence": {
                "replayed_without_evaluator": True,
                "result_sha256": stored.get("result_sha256"),
                "result_refs": [stored.get("record_id")],
                "result": stored.get("result"),
                "journal_scope": journal_scope,
                "spec_sha256": validated["spec_sha256"],
                "new_look": False,
            },
        }
    if owner_allowance(store, operation, "main") < 1:
        raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED")
    _reserve(store, operation, spec_sha256=validated["spec_sha256"])
    return {
        "disposition": "RESERVED",
        "values_loaded": False,
        "operation": get_operation(store, operation_sha256),
        "admission": admission,
        "spec_sha256": validated["spec_sha256"],
    }


def _reserve(store: Any, operation: Mapping[str, Any], *, spec_sha256: str) -> None:
    digest = str(operation.get("operation_sha256") or "")
    for item in _reservations(store, digest):
        if item.get("spec_sha256") == spec_sha256:
            return
    body = {
        "artifact_kind": RESERVATION_KIND,
        "operation_sha256": digest,
        "journal_scope": operation.get("journal_scope"),
        "spec_sha256": spec_sha256,
        "look_class": "MAIN",
        "schema": "smial.hfic-ordinary-look-reservation",
        "schema_version": "1.0",
    }

    def _check() -> None:
        current = get_operation(store, digest)
        if owner_allowance(store, current, "main") < 1:
            raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED")

    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = datetime.now(timezone.utc)
    canonical = _canonical(body)
    identity = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    payload = {
        "artifact_kind": RESERVATION_KIND,
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    event = ResearchEvent(
        record_id=f"HFIC-ART-OPRES-{identity[:40].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"HFIC-ART-OPRES-{identity[:40].upper()}",
        hypothesis_version_id=None,
        run_id=f"HFIC-OPRES-{identity[:16].upper()}",
        transaction_id=f"RESEARCH-TXN-OPRES-{identity[:24].upper()}",
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-HFIC-ORDINARY-OPERATION-001",
        producer_git_sha="0" * 40,
        created_at=now,
    )
    try:
        store.append([event], transaction_id=event.transaction_id, before_commit=_check)
    except OrdinaryOperationError:
        raise
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code == "OWNER_CAP_EXHAUSTED":
            raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED") from exc
        raise


def note_look_landed(store: Any, operation_sha256: str) -> dict[str, Any]:
    """Cap limits new looks. Landing a saved look may pause or stop the operation."""

    operation = get_operation(store, operation_sha256)
    looks = _looks(store, str(operation.get("journal_scope") or ""))
    from solana_alpha_lab.factory.hfic_temporal_discovery import assess_tier_progress

    progress = assess_tier_progress(looks, freeze_worthy=False, compound_applicable=True)
    status = operation.get("status")
    if operation.get("requested_completion") == SCIENTIFIC_TERMINAL and progress.get("search_exhausted_allowed") is True:
        status = "STOPPED"
    elif owner_allowance(store, operation, "main") < 1 and operation.get("requested_completion") == LIMITED_RESULT:
        status = "PAUSED_CAP"
    if status == operation.get("status"):
        return operation
    updated = dict(operation)
    updated["status"] = status
    _append(store, kind=OPERATION_KIND, body=updated, record_prefix="HFIC-ART-OP")
    return updated


def project_ordinary_operation(store: Any, *, owner_focus: str) -> dict[str, Any] | None:
    """Derived readout. Not a second persisted DONE."""

    rows = [item for item in list_operations(store) if item.get("owner_focus") == owner_focus]
    if not rows:
        return None
    rows.sort(key=lambda item: str(item.get("operation_sha256") or ""))
    current = rows[-1]
    journal = str(current.get("journal_scope") or "")
    looks = _looks(store, journal)
    from solana_alpha_lab.factory.hfic_temporal_discovery import assess_tier_progress, validate_temporal_query

    progress = assess_tier_progress(looks, freeze_worthy=False, compound_applicable=True)
    spec = json.loads(str(current.get("spec_canonical") or "{}"))
    validated = validate_temporal_query(spec) if spec else {}
    decision = str((validated.get("scientific_body") or {}).get("decision_point") or "")
    target = (validated.get("scientific_body") or {}).get("target") or {}
    reference = str(target.get("reference_point") or "")
    exit_point = str(target.get("exit_point") or "")
    age = POINT_OFFSET.get(decision)
    hold = None
    if reference in POINT_OFFSET and exit_point in POINT_OFFSET:
        hold = POINT_OFFSET[exit_point] - POINT_OFFSET[reference]
    latest = next(
        (
            item
            for item in reversed(looks)
            if item.get("operation_sha256") == current.get("operation_sha256")
            and isinstance(item.get("result"), Mapping)
        ),
        None,
    )
    if current.get("status") == "PAUSED_CAP":
        next_action = "AUTHORIZE_ADDITIONAL_LOOKS"
        next_needs_values = True
        next_needs_authority = True
    elif current.get("status") == "STOPPED":
        next_action = "READ_SAVED_RESULT"
        next_needs_values = False
        next_needs_authority = False
    else:
        next_action = "RUN_AUTHORIZED_LOOK"
        next_needs_values = True
        next_needs_authority = False
    return {
        "operation_sha256": current.get("operation_sha256"),
        "status": current.get("status"),
        "question_text": current.get("question_text"),
        "journal_scope": journal,
        "decision_point": decision,
        "decision_age_seconds": age,
        "hold_seconds": hold,
        "exit_point": exit_point,
        "completed": {
            "look": latest is not None,
            "operation": current.get("status") in {"PAUSED_CAP", "STOPPED"},
            "scientific_search": progress.get("search_exhausted_allowed") is True,
        },
        "result_refs": [latest.get("record_id")] if latest else [],
        "result_sha256": latest.get("result_sha256") if latest else None,
        "claim_boundary": "PRICE_RELATIVE_PROXY is not net return; cohorts are not independent replications",
        "protocol_main_remaining": _protocol_remaining(looks, "main"),
        "protocol_main_used": sum(1 for item in looks if item.get("look_class") == "MAIN" and item.get("new_look") is True),
        "owner_main_remaining": owner_allowance(store, current, "main"),
        "reserved_main": len(_reservations(store, str(current.get("operation_sha256") or ""))),
        "journal_result_refs": [item.get("record_id") for item in looks],
        "compound_status": progress.get("compound_status"),
        "next_action": next_action,
        "next_needs_new_values": next_needs_values,
        "next_needs_new_authority": next_needs_authority,
        "search_open": progress.get("search_exhausted_allowed") is not True and current.get("status") != "STOPPED",
    }
