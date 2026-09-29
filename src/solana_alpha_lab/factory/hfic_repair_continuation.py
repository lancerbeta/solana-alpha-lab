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
LEGACY_PARENT_BINDING_SCHEMA = "smial.hfic-legacy-parent-binding"
LEGACY_PARENT_BINDING_VERSION = "1.0"
LEGACY_PARENT_BINDING_KEY = "legacy_parent_binding"
LEGACY_PARENT_PROVENANCE = "ESTABLISHED_NOW"
LEGACY_PARENT_AGGREGATE = "ABSENT"
LEGACY_PARENT_RUN_PREFIX = "LEGACY-PARENT-"
MAIN_LOOK_BUDGET = 6

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


def _legacy_binding_from_mapping(mapping: object) -> dict[str, Any] | None:
    if not isinstance(mapping, Mapping):
        return None
    raw = mapping.get(LEGACY_PARENT_BINDING_KEY)
    if not isinstance(raw, Mapping):
        return None
    return dict(raw)


def _pinned_legacy_binding(disposition: Mapping[str, Any]) -> dict[str, Any] | None:
    pinned = _legacy_binding_from_mapping(disposition.get("evidence_mapping"))
    if pinned is None:
        return None
    if (
        pinned.get("schema") != LEGACY_PARENT_BINDING_SCHEMA
        or pinned.get("schema_version") != LEGACY_PARENT_BINDING_VERSION
        or pinned.get("provenance") != LEGACY_PARENT_PROVENANCE
        or pinned.get("aggregate_receipt") != LEGACY_PARENT_AGGREGATE
        or _HEX64.fullmatch(str(pinned.get("binding_sha256") or "")) is None
    ):
        raise RepairContinuationError("PARENT_BINDING_MISMATCH")
    source = pinned.get("source")
    if not isinstance(source, Mapping):
        raise RepairContinuationError("PARENT_BINDING_MISMATCH")
    return pinned


def _iter_forge_run_bodies(store: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
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
        found.append(body)
    return found


def _classify_parent_aggregates(
    store: Any,
    *,
    session_id: str,
    scientific_slot_sha256: str,
) -> tuple[str, dict[str, Any] | None]:
    """Exact session+slot aggregate, a contradicting aggregate, or absence.

    A repair result receipt is not a parent aggregate. Slot-only or
    session-only matches are contradictions, not a fallback.
    """

    exact: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for body in _iter_forge_run_bodies(store):
        if body.get("repair_continuation_disposition_sha256"):
            continue
        session = body.get("session_id")
        slot = body.get("scientific_slot_sha256")
        session_present = isinstance(session, str) and bool(session.strip())
        slot_present = isinstance(slot, str) and _HEX64.fullmatch(slot) is not None
        session_match = session_present and session == session_id
        slot_match = slot_present and slot == scientific_slot_sha256
        if session_match and slot_match:
            run_id = body.get("run_id")
            identity = body.get("run_identity_sha256")
            if not isinstance(run_id, str) or not run_id.strip():
                conflicts.append(body)
                continue
            if identity not in (None, "") and (
                not isinstance(identity, str) or _HEX64.fullmatch(identity) is None
            ):
                conflicts.append(body)
                continue
            exact.append(body)
            continue
        if session_match or slot_match:
            conflicts.append(body)
    if conflicts:
        return "CONFLICT", conflicts[0]
    if not exact:
        return "ABSENT", None
    run_ids = {str(item.get("run_id") or "") for item in exact}
    if len(run_ids) != 1:
        return "CONFLICT", exact[0]
    chosen = next(
        (item for item in exact if item.get("owner_final")),
        exact[-1],
    )
    return "EXACT", chosen


def _journal_corpus_binding(store: Any, journal_scope: str) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks

    bindings: set[str] = set()
    cohorts: set[str] = set()
    for item in list_discovery_looks(store, journal_scope):
        if not isinstance(item, Mapping) or item.get("new_look") is False:
            continue
        digest = item.get("data_binding_sha256")
        if isinstance(digest, str) and _HEX64.fullmatch(digest) is not None:
            bindings.add(digest)
        refs = item.get("data_refs")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, Mapping) and isinstance(ref.get("cohort_id"), str):
                    cohort = str(ref["cohort_id"]).strip()
                    if cohort:
                        cohorts.add(cohort)
    if len(bindings) != 1 or not cohorts:
        raise RepairContinuationError(
            "CORPUS_BINDING_CONFLICT" if len(bindings) > 1 else "CORPUS_BINDING_UNPROVEN"
        )
    return {
        "data_binding_sha256": next(iter(bindings)),
        "cohort_ids": sorted(cohorts),
    }


def _admission_for_parent(
    store: Any,
    *,
    session_id: str,
    scientific_slot_sha256: str,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_session import list_scientific_slot_admissions

    matches = [
        dict(row)
        for row in list_scientific_slot_admissions(store)
        if isinstance(row, Mapping)
        and row.get("session_id") == session_id
        and row.get("scientific_slot_sha256") == scientific_slot_sha256
        and row.get("identity_binding_status") != "CONFLICT"
    ]
    if len(matches) != 1:
        raise RepairContinuationError("REPRESENTATION_SCOPE_UNPROVEN")
    return matches[0]


def derive_legacy_parent_binding(
    store: Any,
    parent_session: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind a completed parent that has no aggregate FORGE_RUN_RECEIPT.

    The binding is established now from durable hashes. It is not a
    historical run receipt and does not reconstruct model or execution
    provenance. Only the representation recorded on the slot admission is
    treated as executed.
    """

    from solana_alpha_lab.factory.hfic_evidence_identity import scientific_slot_sha256
    from solana_alpha_lab.factory.hfic_identity import normalize_text
    from solana_alpha_lab.factory.hfic_session import load_session_bundle
    from solana_alpha_lab.factory.run_passport import canonical_sha256

    session_id = _require_text(
        parent_session.get("session_id"), "PARENT_SESSION_REQUIRED"
    )
    bundle = load_session_bundle(store, session_id, read_mode=True)
    if not isinstance(bundle, Mapping):
        raise RepairContinuationError("PARENT_SESSION_MISSING")
    slot = bundle.get("scientific_slot_sha256")
    if not isinstance(slot, str) or _HEX64.fullmatch(slot) is None:
        raise RepairContinuationError("SCIENTIFIC_SLOT_REQUIRED")
    terminal = bundle.get("session_receipt_sha256")
    if not isinstance(terminal, str) or _HEX64.fullmatch(terminal) is None:
        raise RepairContinuationError("TERMINAL_RECEIPT_REQUIRED")
    journal = str(bundle.get("search_key_sha256") or "")
    if _HEX64.fullmatch(journal) is None:
        raise RepairContinuationError("JOURNAL_SCOPE_REQUIRED")
    market = bundle.get("market_evidence_epoch_sha256")
    if not isinstance(market, str) or _HEX64.fullmatch(market) is None:
        raise RepairContinuationError("MARKET_IDENTITY_UNPROVEN")
    claimed_slot = parent_session.get("scientific_slot_sha256")
    claimed_terminal = (
        parent_session.get("terminal_receipt_sha256")
        or parent_session.get("session_receipt_sha256")
    )
    claimed_journal = parent_session.get("journal_scope") or parent_session.get(
        "search_key_sha256"
    )
    if isinstance(claimed_slot, str) and claimed_slot and claimed_slot != slot:
        raise RepairContinuationError("PARENT_SLOT_MISMATCH")
    if (
        isinstance(claimed_terminal, str)
        and claimed_terminal
        and claimed_terminal != terminal
    ):
        raise RepairContinuationError("TERMINAL_RECEIPT_MISMATCH")
    if isinstance(claimed_journal, str) and claimed_journal and claimed_journal != journal:
        raise RepairContinuationError("JOURNAL_SCOPE_MISMATCH")
    kind, aggregate = _classify_parent_aggregates(
        store, session_id=session_id, scientific_slot_sha256=slot
    )
    if kind == "CONFLICT":
        raise RepairContinuationError("PARENT_RECEIPT_CONFLICT")
    if kind == "EXACT":
        raise RepairContinuationError("PARENT_AGGREGATE_PRESENT")
    admission = _admission_for_parent(
        store, session_id=session_id, scientific_slot_sha256=slot
    )
    focus = admission.get("owner_focus")
    if not isinstance(focus, str) or not focus.strip():
        raise RepairContinuationError("FOCUS_IDENTITY_UNPROVEN")
    focus = focus.strip()
    focus_key = hashlib.sha256(normalize_text(focus).encode("utf-8")).hexdigest()
    admitted_focus = admission.get("focus_key_sha256")
    if isinstance(admitted_focus, str) and admitted_focus and admitted_focus != focus_key:
        raise RepairContinuationError("FOCUS_IDENTITY_UNPROVEN")
    admitted_market = admission.get("market_evidence_epoch_sha256")
    if admitted_market != market:
        raise RepairContinuationError("MARKET_IDENTITY_UNPROVEN")
    representation = admission.get("ladder_representation_id")
    version = admission.get("representation_semantic_version")
    if not isinstance(representation, str) or not representation.strip():
        raise RepairContinuationError("REPRESENTATION_SCOPE_UNPROVEN")
    if not isinstance(version, str) or not version.strip():
        raise RepairContinuationError("REPRESENTATION_SCOPE_UNPROVEN")
    representation = representation.strip()
    version = version.strip()
    bundle_representation = bundle.get("ladder_representation_id")
    if (
        isinstance(bundle_representation, str)
        and bundle_representation
        and bundle_representation != representation
    ):
        raise RepairContinuationError("REPRESENTATION_SCOPE_UNPROVEN")
    expected_slot = scientific_slot_sha256(
        market_evidence_epoch_sha256=market,
        representation_id=representation,
        representation_semantic_version=version,
        owner_focus=focus,
    )
    if expected_slot != slot:
        raise RepairContinuationError("SLOT_IDENTITY_UNPROVEN")
    corpus = _journal_corpus_binding(store, journal)
    source = {
        "aggregate_receipt": LEGACY_PARENT_AGGREGATE,
        "cohort_ids": list(corpus["cohort_ids"]),
        "data_binding_sha256": corpus["data_binding_sha256"],
        "executed_representation_ids": [representation],
        "execution_binding_status": "NOT_RECOVERED",
        "focus_key_sha256": focus_key,
        "journal_scope": journal,
        "market_evidence_epoch_sha256": market,
        "model_provenance_status": "NOT_RECOVERED",
        "owner_focus": focus,
        "parent_session_id": session_id,
        "provenance": LEGACY_PARENT_PROVENANCE,
        "representation_id": representation,
        "representation_semantic_version": version,
        "scientific_slot_sha256": slot,
        "terminal_receipt_sha256": terminal,
    }
    binding_sha = canonical_sha256(
        {
            "identity_version": "HFIC_LEGACY_PARENT_BINDING_V1",
            "source": source,
        }
    )
    public_run_id = f"{LEGACY_PARENT_RUN_PREFIX}{binding_sha[:16].upper()}"
    binding = {
        "aggregate_receipt": LEGACY_PARENT_AGGREGATE,
        "binding_sha256": binding_sha,
        "provenance": LEGACY_PARENT_PROVENANCE,
        "schema": LEGACY_PARENT_BINDING_SCHEMA,
        "schema_version": LEGACY_PARENT_BINDING_VERSION,
        "source": source,
    }
    return {
        "mode": "LEGACY_PARENT_BINDING",
        "parent_run_id": public_run_id,
        "binding": binding,
        "evidence_mapping": {LEGACY_PARENT_BINDING_KEY: binding},
    }


def _proof_next_step(code: str) -> str:
    return {
        "PARENT_RECEIPT_CONFLICT": "INSPECT_CONTRADICTING_FORGE_RUN_RECEIPT",
        "PARENT_RUN_UNPROVEN": "OMIT_CALLER_RUN_ID_AND_USE_DERIVED_BINDING",
        "PARENT_RUN_MISMATCH": "ALIGN_DRAFT_PARENT_RUN_ID",
        "PARENT_BINDING_MISMATCH": "ALIGN_DRAFT_LEGACY_PARENT_BINDING",
        "PARENT_AGGREGATE_PRESENT": "USE_STORED_FORGE_RUN_RECEIPT",
        "CORPUS_BINDING_UNPROVEN": "RESTORE_JOURNAL_CORPUS_BINDING",
        "CORPUS_BINDING_CONFLICT": "RESOLVE_JOURNAL_CORPUS_BINDING",
        "REPRESENTATION_SCOPE_UNPROVEN": "RESTORE_SLOT_ADMISSION_REPRESENTATION",
        "SLOT_IDENTITY_UNPROVEN": "RESTORE_SLOT_ADMISSION_IDENTITY",
        "FOCUS_IDENTITY_UNPROVEN": "RESTORE_SLOT_ADMISSION_FOCUS",
        "MARKET_IDENTITY_UNPROVEN": "RESTORE_MARKET_EPOCH_BINDING",
        "SPENT_BUDGET_EXHAUSTED": "STOP_LOOK_BUDGET_EXHAUSTED",
    }.get(code, "INSPECT_REASON_CODE_THEN_RERUN")


def resolve_repair_parent_proof(
    store: Any,
    parent_session: Mapping[str, Any],
    *,
    claimed_run_id: str | None = None,
) -> dict[str, Any]:
    """One parent contract for draft, plan, apply and completion."""

    session_id = _require_text(
        parent_session.get("session_id"), "PARENT_SESSION_REQUIRED"
    )
    slot = parent_session.get("scientific_slot_sha256")
    if not isinstance(slot, str) or _HEX64.fullmatch(slot) is None:
        from solana_alpha_lab.factory.hfic_session import load_session_bundle

        bundle = load_session_bundle(store, session_id, read_mode=True)
        slot = bundle.get("scientific_slot_sha256") if isinstance(bundle, Mapping) else None
    if not isinstance(slot, str) or _HEX64.fullmatch(slot) is None:
        raise RepairContinuationError("SCIENTIFIC_SLOT_REQUIRED")
    kind, aggregate = _classify_parent_aggregates(
        store, session_id=session_id, scientific_slot_sha256=slot
    )
    if kind == "CONFLICT":
        raise RepairContinuationError("PARENT_RECEIPT_CONFLICT")
    if kind == "EXACT" and isinstance(aggregate, Mapping):
        proven_run_id = str(aggregate.get("run_id") or "")
        if claimed_run_id and claimed_run_id != proven_run_id:
            raise RepairContinuationError("PARENT_RUN_MISMATCH")
        return {
            "mode": "AGGREGATE_RECEIPT",
            "parent_run_id": proven_run_id,
            "binding": None,
            "evidence_mapping": {},
            "receipt": dict(aggregate),
        }
    derived = derive_legacy_parent_binding(store, parent_session)
    if claimed_run_id and claimed_run_id != derived["parent_run_id"]:
        raise RepairContinuationError("PARENT_RUN_UNPROVEN")
    return derived


def read_repair_result_receipt(
    store: Any,
    disposition: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Read the repair result bound to this disposition, session and slot.

    A foreign receipt that matches only the slot or only the session is not
    this result. Legacy completions also require the pinned binding digest.
    """

    disposition_sha = str(disposition.get("disposition_sha256") or "")
    session_id = str(disposition.get("parent_session_id") or "")
    slot = str(disposition.get("scientific_slot_sha256") or "")
    if not disposition_sha or not session_id or _HEX64.fullmatch(slot) is None:
        return None
    pinned = None
    if _legacy_binding_from_mapping(disposition.get("evidence_mapping")) is not None:
        pinned = _pinned_legacy_binding(disposition)
    want_identity = (
        str(pinned.get("binding_sha256") or "") if isinstance(pinned, Mapping) else ""
    )
    found: list[dict[str, Any]] = []
    for body in _iter_forge_run_bodies(store):
        if str(body.get("repair_continuation_disposition_sha256") or "") != disposition_sha:
            continue
        if str(body.get("session_id") or "") != session_id:
            continue
        if str(body.get("scientific_slot_sha256") or "") != slot:
            continue
        if want_identity and str(body.get("run_identity_sha256") or "") != want_identity:
            continue
        found.append(body)
    if not found:
        return None
    digests = {str(item.get("receipt_sha256") or "") for item in found}
    if len(digests) != 1 or not next(iter(digests)):
        raise RepairContinuationError("PARENT_RECEIPT_CONFLICT")
    return dict(found[-1])


def disposition_identity(body: Mapping[str, Any]) -> str:
    mapping = body.get("evidence_mapping") or {}
    if not isinstance(mapping, Mapping):
        mapping = {}
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
            "evidence_mapping": dict(sorted((str(k), mapping[k]) for k in mapping)),
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
    store: Any | None = None,
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
    critic = str(parent_session.get("critic_terminal") or "")
    final_terminal = str(
        parent_session.get("final_session_terminal")
        or parent_session.get("owner_final")
        or ""
    )
    state = str(
        parent_session.get("session_state")
        or parent_session.get("phase")
        or ""
    )
    # Durable NO_WORTHY only — draft parent_terminal is not authority.
    durable_no_worthy = (
        critic == "NO_WORTHY_HYPOTHESIS"
        or final_terminal == "NO_WORTHY_HYPOTHESIS"
    )
    eligible = durable_no_worthy and (
        state in {"", "SYNTHESIS_COMPLETE", "SEARCH_EXHAUSTED_CURRENT_EVIDENCE"}
        or "NO_WORTHY" in state
        or critic == "NO_WORTHY_HYPOTHESIS"
    )
    if not eligible:
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
    parent_receipt = (
        parent_session.get("terminal_receipt_sha256")
        or parent_session.get("session_receipt_sha256")
    )
    if not isinstance(parent_receipt, str) or not parent_receipt:
        return _owner_plan(
            status="NOT_APPLICABLE",
            reason_code="PARENT_TERMINAL_RECEIPT_MISSING",
            writes=False,
            disposition=body,
            owner_status="BLOCKED",
            next_step="PROVIDE_TERMINAL_RECEIPT_FROM_SHOW_SESSION",
        )
    if parent_receipt != body["terminal_receipt_sha256"]:
        return _owner_plan(
            status="NOT_APPLICABLE",
            reason_code="TERMINAL_RECEIPT_MISMATCH",
            writes=False,
            disposition=body,
            owner_status="BLOCKED",
            next_step="ALIGN_DRAFT_TERMINAL_RECEIPT",
        )
    durable_parent = False
    if store is not None:
        from solana_alpha_lab.factory.hfic_session import load_session_bundle

        stored_bundle = load_session_bundle(store, session_id, read_mode=True)
        aggregate_kind, _aggregate = _classify_parent_aggregates(
            store,
            session_id=session_id,
            scientific_slot_sha256=str(body["scientific_slot_sha256"]),
        )
        durable_parent = aggregate_kind != "ABSENT" or (
            isinstance(stored_bundle, Mapping)
            and _HEX64.fullmatch(str(stored_bundle.get("session_receipt_sha256") or ""))
            is not None
        )
    if store is not None and durable_parent:
        try:
            proof = resolve_repair_parent_proof(
                store,
                parent_session,
                claimed_run_id=str(body["parent_run_id"]),
            )
        except RepairContinuationError as exc:
            return _owner_plan(
                status="NOT_APPLICABLE",
                reason_code=str(exc),
                writes=False,
                disposition=body,
                owner_status="BLOCKED",
                next_step=_proof_next_step(str(exc)),
            )
        if proof["parent_run_id"] != body["parent_run_id"]:
            return _owner_plan(
                status="NOT_APPLICABLE",
                reason_code="PARENT_RUN_MISMATCH",
                writes=False,
                disposition=body,
                owner_status="BLOCKED",
                next_step="ALIGN_DRAFT_PARENT_RUN_ID",
            )
        if proof["mode"] == "LEGACY_PARENT_BINDING":
            pinned = _legacy_binding_from_mapping(body.get("evidence_mapping"))
            if pinned != proof.get("binding"):
                return _owner_plan(
                    status="NOT_APPLICABLE",
                    reason_code="PARENT_BINDING_MISMATCH",
                    writes=False,
                    disposition=body,
                    owner_status="BLOCKED",
                    next_step="ALIGN_DRAFT_LEGACY_PARENT_BINDING",
                )
        elif _legacy_binding_from_mapping(body.get("evidence_mapping")) is not None:
            return _owner_plan(
                status="NOT_APPLICABLE",
                reason_code="PARENT_RECEIPT_CONFLICT",
                writes=False,
                disposition=body,
                owner_status="BLOCKED",
                next_step="DROP_LEGACY_BINDING_WHEN_AGGREGATE_RECEIPT_EXISTS",
            )
    else:
        parent_run = (
            parent_session.get("run_id")
            or parent_session.get("forge_run_id")
            or parent_session.get("parent_run_id")
        )
        if isinstance(parent_run, str) and parent_run and parent_run != body["parent_run_id"]:
            return _owner_plan(
                status="NOT_APPLICABLE",
                reason_code="PARENT_RUN_MISMATCH",
                writes=False,
                disposition=body,
                owner_status="BLOCKED",
                next_step="ALIGN_DRAFT_PARENT_RUN_ID",
            )
    parent_scope = (
        parent_session.get("journal_scope") or parent_session.get("search_key_sha256")
    )
    if (
        isinstance(parent_scope, str)
        and parent_scope
        and parent_scope != body["journal_scope"]
    ):
        return _owner_plan(
            status="NOT_APPLICABLE",
            reason_code="JOURNAL_SCOPE_MISMATCH",
            writes=False,
            disposition=body,
            owner_status="BLOCKED",
            next_step="ALIGN_DRAFT_JOURNAL_SCOPE",
        )
    # Same owner authorization is durable history. Match by authorization
    # identity (not only disposition_sha256): journal spent / allowed_look_ids
    # enrichment must not turn an idempotent replay into a second READY write.
    for item in existing_dispositions:
        if not isinstance(item, Mapping):
            continue
        same_auth = (
            item.get("owner_authorization_id") == body["owner_authorization_id"]
            and item.get("parent_session_id") == body["parent_session_id"]
            and item.get("scientific_slot_sha256") == body["scientific_slot_sha256"]
        )
        same_digest = item.get("disposition_sha256") == body["disposition_sha256"]
        if not same_auth and not same_digest:
            continue
        if item.get("status") == "CLOSED":
            return _owner_plan(
                status="NOT_APPLICABLE",
                reason_code="DISPOSITION_ALREADY_CLOSED",
                writes=False,
                disposition=dict(item),
                owner_status="BLOCKED",
                next_step="STOP_CONTINUATION_ALREADY_CONSUMED",
            )
        return _owner_plan(
            status="ALREADY_APPLIED",
            reason_code="IDEMPOTENT_REPLAY",
            writes=False,
            disposition=dict(item),
            owner_status="DONE",
            next_step="ORDINARY_TEMPORAL_QUERY_WITHIN_REMAINING_BUDGET",
            remaining_main_looks=max(
                0, 6 - int(item.get("spent_main_looks") or body["spent_main_looks"])
            ),
            remaining_adaptive_looks=max(
                0,
                2 - int(item.get("spent_adaptive_looks") or body["spent_adaptive_looks"]),
            ),
        )
    # Resolve spent looks from durable journal when store has looks.
    # Caller draft counts are assertions against the journal, not authority.
    if store is not None:
        spent = spent_looks_from_journal(store, body["journal_scope"])
        if int(spent["look_count"]) > 0:
            for key in (
                "spent_main_looks",
                "spent_adaptive_looks",
                "spent_preview_looks",
            ):
                if int(body[key]) != int(spent[key]):
                    return _owner_plan(
                        status="NOT_APPLICABLE",
                        reason_code="SPENT_BUDGET_MISMATCH",
                        writes=False,
                        disposition=body,
                        owner_status="BLOCKED",
                        next_step="ALIGN_DRAFT_SPENT_LOOKS_TO_JOURNAL",
                    )
            body = dict(body)
            body["spent_main_looks"] = int(spent["spent_main_looks"])
            body["spent_adaptive_looks"] = int(spent["spent_adaptive_looks"])
            body["spent_preview_looks"] = int(spent["spent_preview_looks"])
            if spent["allowed_look_ids"]:
                body["allowed_look_ids"] = list(spent["allowed_look_ids"])
            body["disposition_sha256"] = disposition_identity(body)
            # Re-check after enrichment: sha may now equal a stored disposition.
            for item in existing_dispositions:
                if not isinstance(item, Mapping):
                    continue
                if item.get("disposition_sha256") != body["disposition_sha256"]:
                    continue
                if item.get("status") == "CLOSED":
                    return _owner_plan(
                        status="NOT_APPLICABLE",
                        reason_code="DISPOSITION_ALREADY_CLOSED",
                        writes=False,
                        disposition=dict(item),
                        owner_status="BLOCKED",
                        next_step="STOP_CONTINUATION_ALREADY_CONSUMED",
                    )
                return _owner_plan(
                    status="ALREADY_APPLIED",
                    reason_code="IDEMPOTENT_REPLAY",
                    writes=False,
                    disposition=dict(item),
                    owner_status="DONE",
                    next_step="ORDINARY_TEMPORAL_QUERY_WITHIN_REMAINING_BUDGET",
                    remaining_main_looks=max(0, 6 - int(body["spent_main_looks"])),
                    remaining_adaptive_looks=max(
                        0, 2 - int(body["spent_adaptive_looks"])
                    ),
                )
        else:
            for key in (
                "spent_main_looks",
                "spent_adaptive_looks",
                "spent_preview_looks",
            ):
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
    else:
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
    if int(body["spent_main_looks"]) >= MAIN_LOOK_BUDGET:
        return _owner_plan(
            status="NOT_APPLICABLE",
            reason_code="SPENT_BUDGET_EXHAUSTED",
            writes=False,
            disposition=body,
            owner_status="BLOCKED",
            next_step="STOP_LOOK_BUDGET_EXHAUSTED",
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
        if (
            item.get("parent_session_id") == body["parent_session_id"]
            and item.get("status") == "AUTHORIZED"
            and item.get("disposition_sha256") != body["disposition_sha256"]
        ):
            competing = dict(item)
            competing_sha = str(competing.get("disposition_sha256") or "")
            return _owner_plan(
                status="CONFLICT",
                reason_code="COMPETING_ACTIVE_DISPOSITION",
                writes=False,
                disposition=competing,
                owner_status="BLOCKED",
                next_step=(
                    "CLOSE_COMPETING_DISPOSITION_THEN_STOP"
                    if competing_sha
                    else "RESOLVE_COMPETING_DISPOSITION_OR_STOP"
                ),
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
    "SOURCE_PRICE_EVENT_MALFORMED": (
        "A non-empty source price event could not be parsed; fail closed, not UNKNOWN."
    ),
    "SNAPSHOT_OCCURRENCE_UNBOUND": (
        "Snapshot exit lacks a registered PRIM-* primitive plus request/occurrence binding."
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
    repair_completed: dict[str, Any] | None = None
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
        if not body.get("owner_final"):
            continue
        if isinstance(body.get("repair_continuation_disposition_sha256"), str) and body.get(
            "repair_continuation_disposition_sha256"
        ):
            repair_completed = body
        else:
            completed = body
    return repair_completed or completed or latest


def _repair_completion_from_session(
    bundle: Mapping[str, Any],
) -> tuple[str, str] | None:
    """Map a completed repair session to (effective_terminal, owner_final).

    Uses canonical ``effective_control_terminal`` + ``resolve_next_action``.
    Incomplete critic/revision/classification/runner-up states return None.
    """

    from solana_alpha_lab.factory.hfic_control_integrity import effective_control_terminal
    from solana_alpha_lab.factory.hfic_representation_ladder import resolve_next_action

    terminal = effective_control_terminal(bundle)
    if not terminal:
        return None
    state = str(bundle.get("session_state") or "")
    decision = resolve_next_action(
        [
            {
                "representation_id": "BASE",
                "execution_status": "EXECUTED",
                "effective_terminal": terminal,
                "session_state": state,
                "runner_up_candidate_id": bundle.get("runner_up_candidate_id"),
            }
        ]
    )
    owner_final = decision.get("owner_final")
    if not isinstance(owner_final, str) or not owner_final:
        return None
    return terminal, owner_final


def _disposition_bound_repair_completion(
    bundle: Mapping[str, Any],
    disposition: Mapping[str, Any],
) -> tuple[str, str] | None:
    """Require a completed cycle bound to this disposition and new vs parent.

    Parent DONE without a repair marker, a foreign disposition marker, or a
    still-pending repair cycle must not authorize close. Uses existing session
    identities (disposition stamp + terminal receipt) — no new permission surface.
    """

    completion = _repair_completion_from_session(bundle)
    if completion is None:
        return None
    expected = disposition.get("disposition_sha256")
    if not (isinstance(expected, str) and expected):
        return None
    bound = bundle.get("repair_continuation_disposition_sha256")
    if bound != expected:
        return None
    parent_receipt = disposition.get("terminal_receipt_sha256")
    session_receipt = bundle.get("session_receipt_sha256") or bundle.get(
        "terminal_receipt_sha256"
    )
    if not (
        isinstance(parent_receipt, str)
        and parent_receipt
        and isinstance(session_receipt, str)
        and session_receipt
    ):
        # Fail closed: missing either identity cannot prove a new execution.
        return None
    if session_receipt == parent_receipt:
        # Same receipt as the authorized parent — no new repair execution yet.
        return None
    return completion


def _persist_repair_completion_forge_run(
    store: Any,
    *,
    disposition: Mapping[str, Any],
    git_sha: str,
    now: datetime,
) -> dict[str, Any] | None:
    """Append durable FORGE_RUN_RECEIPT for the repair terminal without rewriting parent."""

    from solana_alpha_lab.factory.hfic_session import list_hfic_sessions, load_session_bundle
    from solana_alpha_lab.factory.hfic_representation_ladder import FORGE_RUN_ARTIFACT_KIND
    from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256

    session_id = str(disposition.get("parent_session_id") or "")
    if not session_id:
        return None
    bundle = load_session_bundle(store, session_id, read_mode=True)
    if not isinstance(bundle, Mapping):
        return None
    pinned = None
    if _legacy_binding_from_mapping(disposition.get("evidence_mapping")) is not None:
        pinned = _pinned_legacy_binding(disposition)
    parent_run_id = str(disposition.get("parent_run_id") or "")
    if pinned is not None:
        source = pinned.get("source")
        if not isinstance(source, Mapping):
            raise RepairContinuationError("PARENT_BINDING_MISMATCH")
        representation = str(source.get("representation_id") or "")
        version = str(source.get("representation_semantic_version") or "")
        parent_identity = {
            "schema": "smial.forge-run-receipt",
            "schema_version": "1.0",
            "owner_focus": source.get("owner_focus"),
            "owner_class": "OWNER_FINAL",
            "market_evidence_epoch_sha256": source.get("market_evidence_epoch_sha256"),
            "frozen_representation_ids": list(
                source.get("executed_representation_ids") or []
            ),
            "frozen_representation_versions": [f"{representation}@{version}"],
            "visible_cohort_ids": list(source.get("cohort_ids") or []),
            "used_cohort_ids": list(source.get("cohort_ids") or []),
            "legacy_parent_binding_sha256": pinned.get("binding_sha256"),
            "parent_binding_provenance": LEGACY_PARENT_PROVENANCE,
        }
        run_identity = str(pinned.get("binding_sha256") or "")
    else:
        parent_run = _lookup_forge_run_for_parent(
            store,
            session_id=session_id,
            scientific_slot_sha256=(
                str(disposition.get("scientific_slot_sha256"))
                if isinstance(disposition.get("scientific_slot_sha256"), str)
                else None
            ),
        )
        parent_identity = None
        for body in _iter_forge_run_bodies(store):
            if body.get("repair_continuation_disposition_sha256"):
                continue
            if (
                parent_run_id
                and str(body.get("run_id") or "") == parent_run_id
                and str(body.get("session_id") or "") == session_id
                and str(body.get("scientific_slot_sha256") or "")
                == str(disposition.get("scientific_slot_sha256") or "")
            ):
                parent_identity = body
                break
        if parent_identity is None and isinstance(parent_run, Mapping):
            if (
                str(parent_run.get("session_id") or "") == session_id
                and str(parent_run.get("scientific_slot_sha256") or "")
                == str(disposition.get("scientific_slot_sha256") or "")
            ):
                parent_identity = parent_run
        if not isinstance(parent_identity, Mapping):
            return None
        run_identity = parent_identity.get("run_identity_sha256")
    if not (isinstance(run_identity, str) and _HEX64.match(run_identity)):
        return None
    existing_repair = read_repair_result_receipt(store, disposition)
    if (
        isinstance(existing_repair, Mapping)
        and existing_repair.get("repair_continuation_disposition_sha256")
        == disposition.get("disposition_sha256")
    ):
        return dict(existing_repair)
    completion = _disposition_bound_repair_completion(bundle, disposition)
    if completion is None:
        return None
    terminal, owner_final = completion
    listed = next(
        (
            item
            for item in list_hfic_sessions(store)
            if item.get("session_id") == session_id
        ),
        None,
    )
    stage = {
        "representation_id": (
            str(parent_identity.get("frozen_representation_ids")[0])
            if isinstance(parent_identity.get("frozen_representation_ids"), list)
            and parent_identity.get("frozen_representation_ids")
            else "BASE"
        ),
        "representation_semantic_version": (
            (pinned or {}).get("source", {}).get("representation_semantic_version")
            if isinstance(pinned, Mapping)
            and isinstance((pinned or {}).get("source"), Mapping)
            else None
        )
        or bundle.get("representation_semantic_version")
        or "HFIC-V1.2",
        "session_id": session_id,
        "session_state": bundle.get("session_state"),
        "effective_terminal": terminal,
        "critic_terminal": bundle.get("critic_terminal"),
        "final_session_terminal": bundle.get("final_session_terminal"),
        "execution_status": "EXECUTED",
        "scientific_slot_sha256": disposition.get("scientific_slot_sha256")
        or bundle.get("scientific_slot_sha256"),
        "capability_epoch_sha256": bundle.get("capability_epoch_sha256")
        or (listed or {}).get("capability_epoch_sha256"),
        "market_evidence_epoch_sha256": bundle.get("market_evidence_epoch_sha256")
        or parent_identity.get("market_evidence_epoch_sha256"),
        "execution_binding_sha256": bundle.get("execution_binding_sha256"),
        "used_cohort_ids": list(parent_identity.get("used_cohort_ids") or []),
        "stage_ref_sha256": bundle.get("session_receipt_sha256"),
        "selected_candidate_id": (
            bundle.get("final_survivor_candidate_id")
            or (
                (bundle.get("session_receipt") or {}).get("final_survivor_candidate_id")
                if isinstance(bundle.get("session_receipt"), Mapping)
                else None
            )
            or (
                bundle.get("runner_up_candidate_id")
                if bundle.get("runner_up_failover_used")
                or (
                    isinstance(bundle.get("session_receipt"), Mapping)
                    and (bundle.get("session_receipt") or {}).get("runner_up_failover_used")
                )
                else None
            )
            or bundle.get("selected_candidate_id")
            or bundle.get("runner_up_candidate_id")
        ),
    }
    run_id = f"FORGE-RUN-REPAIR-{str(disposition.get('disposition_sha256') or '')[:16].upper()}"
    unsigned = {
        "schema": parent_identity.get("schema") or "smial.forge-run-receipt",
        "schema_version": parent_identity.get("schema_version") or "1.0",
        "run_id": run_id,
        "run_identity_sha256": run_identity,
        "owner_focus": parent_identity.get("owner_focus") or "AUTO",
        "owner_class": parent_identity.get("owner_class"),
        "next_action": "RETURN_EXISTING",
        "owner_final": owner_final,
        "session_id": session_id,
        "scientific_slot_sha256": disposition.get("scientific_slot_sha256")
        or parent_identity.get("scientific_slot_sha256"),
        "market_evidence_epoch_sha256": parent_identity.get("market_evidence_epoch_sha256"),
        "capability_epoch_sha256": stage.get("capability_epoch_sha256")
        or parent_identity.get("capability_epoch_sha256"),
        "execution_binding_sha256": stage.get("execution_binding_sha256"),
        "stages": [stage],
        "repair_continuation_disposition_sha256": disposition.get("disposition_sha256"),
        "parent_run_id": parent_run_id or parent_identity.get("run_id"),
        "writes": {"research_store": 1, "forge_run": 1, "session": 0},
        "visible_cohort_ids": list(parent_identity.get("visible_cohort_ids") or []),
        "used_cohort_ids": list(parent_identity.get("used_cohort_ids") or []),
        "frozen_representation_ids": list(
            parent_identity.get("frozen_representation_ids") or ["BASE"]
        ),
        "frozen_representation_versions": list(
            parent_identity.get("frozen_representation_versions") or []
        ),
    }
    unsigned["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in unsigned.items() if key != "owner_readout"}
    )
    body = canonical_json_bytes(unsigned).decode("utf-8")
    digest = unsigned["receipt_sha256"]
    artifact = {
        "research_artifact_id": f"HFIC-ART-FORGE-RUN-{digest[:16].upper()}",
        "hfic_protocol": "HFIC-V1.2",
        "artifact_kind": FORGE_RUN_ARTIFACT_KIND,
        "payload_canonical": body,
        "payload_sha256": digest,
    }
    payload_json = json.dumps(
        artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    transaction_id = f"RESEARCH-TXN-FORGERUN-REPAIR-{digest[:12].upper()}"
    event = ResearchEvent(
        record_id=f"HFIC-ART-FORGE-RUN-{digest[:16].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"HFIC-ART-FORGE-RUN-{digest[:16].upper()}",
        hypothesis_version_id=None,
        run_id=run_id,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=REPAIR_CAPABILITY_ID,
        producer_git_sha=git_sha,
        created_at=now,
    )
    store.append([event], transaction_id=transaction_id)
    if pinned is not None:
        observed = read_repair_result_receipt(store, disposition)
        if not isinstance(observed, Mapping):
            raise RepairContinuationError("REPAIR_RESULT_UNREADABLE")
        if observed.get("receipt_sha256") != digest:
            raise RepairContinuationError("REPAIR_RESULT_UNREADABLE")
        return observed
    return unsigned


def spent_looks_from_journal(store: Any, journal_scope: str) -> dict[str, Any]:
    """Count spent discovery looks for one journal scope. No writes."""

    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
    from solana_alpha_lab.factory.hfic_temporal_discovery import stored_preview_hashes

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
    # Feature previews are separate DISCOVERY_FEATURE_PREVIEW artifacts.
    feature_previews = stored_preview_hashes(store, journal_scope)
    preview = max(preview, len(feature_previews))
    return {
        "spent_main_looks": main,
        "spent_adaptive_looks": adaptive,
        "spent_preview_looks": preview,
        "allowed_look_ids": look_ids,
        "look_count": len(looks) + len(feature_previews),
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
    evidence_mapping: Mapping[str, Any] | None = None,
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
    mapping = dict(evidence_mapping or parent_session.get("evidence_mapping") or {})
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
        "evidence_mapping": mapping,
    }
    if example_exclusion_code:
        draft["example_exclusion_code"] = str(example_exclusion_code)
    return draft


def list_repair_continuation_dispositions(store: Any) -> list[dict[str, Any]]:
    # CLOSED always dominates AUTHORIZED for the same digest, regardless of
    # ResearchStore iteration order (close artifact may appear before CONT).
    by_digest: dict[str, dict[str, Any]] = {}
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
        wrapper_kind = wrapper.get("artifact_kind")
        if wrapper_kind != DISPOSITION_ARTIFACT_KIND and body.get(
            "schema"
        ) != DISPOSITION_SCHEMA:
            continue
        digest = str(body.get("disposition_sha256") or "")
        if not digest:
            continue
        prior = by_digest.get(digest)
        if prior is not None and prior.get("status") == "CLOSED":
            continue
        if body.get("status") == "CLOSED" or prior is None:
            by_digest[digest] = body
            continue
        if prior.get("status") != "CLOSED":
            by_digest[digest] = body
    return list(by_digest.values())


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
        draft,
        parent_session=parent_session,
        existing_dispositions=existing,
        store=store,
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

    def _recheck_under_lease() -> None:
        latest = list_repair_continuation_dispositions(store)
        for item in latest:
            if not isinstance(item, Mapping):
                continue
            if item.get("disposition_sha256") == identity:
                if item.get("status") == "AUTHORIZED":
                    # Another writer already committed this authorization.
                    raise RepairContinuationError("IDEMPOTENT_REPLAY")
                raise RepairContinuationError("DISPOSITION_ALREADY_CLOSED")
            if (
                item.get("status") == "AUTHORIZED"
                and item.get("scientific_slot_sha256") == body["scientific_slot_sha256"]
                and item.get("parent_session_id") == body["parent_session_id"]
                and item.get("disposition_sha256") != identity
            ):
                raise RepairContinuationError("COMPETING_DISPOSITION_APPLIED")
        replan = plan_repair_continuation(
            draft,
            parent_session=parent_session,
            existing_dispositions=latest,
            store=store,
        )
        if replan["status"] == "ALREADY_APPLIED":
            raise RepairContinuationError("IDEMPOTENT_REPLAY")
        if replan["status"] == "CONFLICT":
            raise RepairContinuationError(
                str(replan.get("reason_code") or "COMPETING_ACTIVE_DISPOSITION")
            )
        if replan["status"] != "READY":
            raise RepairContinuationError(
                str(replan.get("reason_code") or "NOT_READY_UNDER_LEASE")
            )

    try:
        store.append(
            [event],
            transaction_id=event.transaction_id,
            before_commit=_recheck_under_lease,
        )
    except RepairContinuationError as exc:
        if str(exc) == "IDEMPOTENT_REPLAY":
            latest = list_repair_continuation_dispositions(store)
            matched = next(
                (
                    item
                    for item in latest
                    if isinstance(item, Mapping)
                    and item.get("disposition_sha256") == identity
                ),
                body,
            )
            return {
                **plan,
                "status": "ALREADY_APPLIED",
                "reason_code": "IDEMPOTENT_REPLAY",
                "applied": False,
                "idempotent": True,
                "writes": False,
                "owner_status": "DONE",
                "next_step": "ORDINARY_TEMPORAL_QUERY_WITHIN_REMAINING_BUDGET",
                "disposition": dict(matched) if isinstance(matched, Mapping) else body,
            }
        raise
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
    terminal = str(parent_terminal or "")
    # Overlay when parent is NO_WORTHY, or SYNTHESIS_COMPLETE bound by a
    # NO_WORTHY disposition (completed search without selected candidate).
    if not terminal:
        return result
    if "NO_WORTHY" not in terminal:
        if terminal == "SYNTHESIS_COMPLETE":
            if disposition.get("parent_terminal") != "NO_WORTHY_HYPOTHESIS":
                return result
        elif terminal not in {"SEARCH_EXHAUSTED_CURRENT_EVIDENCE"}:
            return result
        else:
            # SEARCH_EXHAUSTED alone is not NO_WORTHY; disposition must bind it.
            if disposition.get("parent_terminal") != "NO_WORTHY_HYPOTHESIS":
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


def close_repair_continuation(
    store: Any,
    disposition_sha256: str,
    *,
    git_sha: str,
    reason_code: str = "CONTINUATION_TERMINAL_REACHED",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Append-only CLOSE of an AUTHORIZED disposition after a new terminal."""

    existing = list_repair_continuation_dispositions(store)
    target = None
    for item in existing:
        if item.get("disposition_sha256") == disposition_sha256:
            target = dict(item)
            break
    if target is None:
        raise RepairContinuationError("DISPOSITION_NOT_FOUND")
    if target.get("status") == "CLOSED":
        # Crash recovery: CLOSED without a repair forge-run still needs the
        # durable owner result linked to this disposition.
        prior = _lookup_forge_run_for_parent(
            store,
            session_id=str(target.get("parent_session_id") or ""),
            scientific_slot_sha256=(
                str(target.get("scientific_slot_sha256"))
                if isinstance(target.get("scientific_slot_sha256"), str)
                else None
            ),
        )
        already_linked = (
            isinstance(prior, Mapping)
            and prior.get("repair_continuation_disposition_sha256")
            == disposition_sha256
        )
        repair_run = _persist_repair_completion_forge_run(
            store,
            disposition=target,
            git_sha=git_sha,
            now=now or datetime.now(timezone.utc),
        )
        wrote = isinstance(repair_run, Mapping) and not already_linked
        if _legacy_binding_from_mapping(target.get("evidence_mapping")) is not None:
            readable = read_repair_result_receipt(store, target)
            if not isinstance(readable, Mapping):
                raise RepairContinuationError("REPAIR_RESULT_UNREADABLE")
            repair_run = readable
            wrote = not already_linked
        return {
            "status": "ALREADY_CLOSED",
            "applied": False,
            "idempotent": True,
            "disposition": target,
            "writes": wrote,
            "owner_status": "DONE",
            "reason_code": reason_code,
            "forge_run_receipt_sha256": (
                repair_run.get("receipt_sha256") if isinstance(repair_run, Mapping) else None
            ),
        }
    if target.get("status") != "AUTHORIZED":
        raise RepairContinuationError("DISPOSITION_NOT_AUTHORIZED")
    # Refuse close until this disposition's repair session has a canonical
    # owner-final terminal bound to the disposition and new relative to the
    # parent receipt. Parent DONE / foreign marker / critic-only / intermediate
    # states are not a completion of the authorized continuation.
    from solana_alpha_lab.factory.hfic_session import load_session_bundle

    session_id = str(target.get("parent_session_id") or "")
    bundle = load_session_bundle(store, session_id, read_mode=True) if session_id else None
    if (
        not isinstance(bundle, Mapping)
        or _disposition_bound_repair_completion(bundle, target) is None
    ):
        raise RepairContinuationError("REPAIR_EXECUTION_NOT_COMPLETE")
    closed = dict(target)
    closed["status"] = "CLOSED"
    closed["closed_reason_code"] = reason_code
    moment = now or datetime.now(timezone.utc)
    repair_run = _persist_repair_completion_forge_run(
        store,
        disposition={**closed, "disposition_sha256": disposition_sha256},
        git_sha=git_sha,
        now=moment,
    )
    if _legacy_binding_from_mapping(closed.get("evidence_mapping")) is not None:
        if not isinstance(repair_run, Mapping) or not read_repair_result_receipt(
            store, {**closed, "disposition_sha256": disposition_sha256}
        ):
            raise RepairContinuationError("REPAIR_RESULT_UNREADABLE")
    elif repair_run is None:
        # Receipt-backed parents with a run identity must leave a readable
        # repair result. Older fixtures without that identity still close.
        parent_probe = _lookup_forge_run_for_parent(
            store,
            session_id=str(closed.get("parent_session_id") or ""),
            scientific_slot_sha256=(
                str(closed.get("scientific_slot_sha256"))
                if isinstance(closed.get("scientific_slot_sha256"), str)
                else None
            ),
        )
        if (
            isinstance(parent_probe, Mapping)
            and isinstance(parent_probe.get("run_identity_sha256"), str)
            and _HEX64.match(str(parent_probe.get("run_identity_sha256")))
        ):
            raise RepairContinuationError("REPAIR_FORGE_RUN_PERSIST_FAILED")
    canonical = _canonical(closed)
    payload = {
        "artifact_kind": DISPOSITION_ARTIFACT_KIND,
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    identity = str(disposition_sha256)
    event = ResearchEvent(
        record_id=f"HFIC-ART-REPAIR-CLOSE-{identity[:36].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"HFIC-ART-REPAIR-CLOSE-{identity[:36].upper()}",
        hypothesis_version_id=None,
        run_id=str(closed.get("parent_run_id") or ""),
        transaction_id=f"RESEARCH-TXN-REPAIR-CLOSE-{identity[:24].upper()}",
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
    return {
        "status": "CLOSED",
        "applied": True,
        "idempotent": False,
        "disposition": closed,
        "writes": True,
        "owner_status": "DONE",
        "reason_code": reason_code,
        "record_id": event.record_id,
        "forge_run_receipt_sha256": (
            repair_run.get("receipt_sha256") if isinstance(repair_run, Mapping) else None
        ),
    }
