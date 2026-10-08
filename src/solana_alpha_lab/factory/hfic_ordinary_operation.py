"""Ordinary owner-request binding for one journal.

This is operational metadata. Admission, journal budget and tier progress
stay in their existing owners. A hash is not owner will; the stored text is
the explicit request this call was given.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from solana_alpha_lab.factory.hfic_grounded_discovery import (
    POINT_OFFSET,
    GroundedDiscoveryError,
    _canonical,
    list_discovery_looks,
)
from solana_alpha_lab.factory.hfic_research_policy import (
    ensure_run_snapshot,
    epoch_limits,
    limits_or_defaults,
)

OPERATION_KIND = "ORDINARY_OPERATION_V1"
RESERVATION_KIND = "ORDINARY_LOOK_RESERVATION_V1"
LIMITED_RESULT = "LIMITED_RESULT"
REPRESENTATION_CONTINUATION = "REPRESENTATION_CONTINUATION"
SCIENTIFIC_TERMINAL = "SCIENTIFIC_TERMINAL"

# Persisted operation statuses. COMPLETED is never written: it is derived
# from the run's own persisted owner-final receipt.
STATUS_OPEN = "OPEN"
STATUS_PAUSED_CAP = "PAUSED_CAP"
STATUS_STOPPED = "STOPPED"
STATE_COMPLETED = "COMPLETED"
STOP_REASON_CODE = "OWNER_CANCELLED_EXECUTION"
STOP_PROPOSAL_SCHEMA = "smial.hfic-ordinary-operation-stop-proposal"
NEXT_PERSIST_OWNER_FINAL = "PERSIST_OWNER_FINAL"
NEXT_FINISH_OR_STOP = "FINISH_RUN_THEN_PERSIST_OWNER_FINAL_OR_STOP_OPERATION"
NEXT_LOOK_OR_STOP = "RUN_AUTHORIZED_LOOK_OR_STOP_OPERATION"
NEXT_STOP = "STOP_OPERATION"


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
            recorded = getattr(record, "created_at", None)
            body["_recorded_at"] = recorded.isoformat() if hasattr(recorded, "isoformat") else ""
            found.append(body)
    return found


def list_operations(store: Any) -> list[dict[str, Any]]:
    return _iter_kind(store, OPERATION_KIND)


def _latest_recorded(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return dict(max(rows, key=lambda item: str(item.get("_recorded_at") or "")))


def get_operation(store: Any, operation_sha256: str) -> dict[str, Any]:
    found = [item for item in list_operations(store) if item.get("operation_sha256") == operation_sha256]
    if not found:
        raise OrdinaryOperationError("ORDINARY_OPERATION_NOT_FOUND")
    latest = _latest_recorded(found)
    latest.pop("_recorded_at", None)
    return latest


def _cap_field(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OrdinaryOperationError("ORDINARY_OPERATION_CAP_INVALID")
    return value


def record_operation(
    store: Any, request: Mapping[str, Any], *, create_if_missing: bool = True
) -> dict[str, Any]:
    """Persist one explicit owner request. The same bytes return the same row."""

    text = request.get("owner_request_text")
    if not isinstance(text, str) or not text.strip():
        raise OrdinaryOperationError("ORDINARY_OPERATION_REQUEST_REQUIRED")
    spec = request.get("spec")
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
    exact = cap["main"] == 1
    validated = None
    if exact and not isinstance(spec, Mapping):
        raise OrdinaryOperationError("ORDINARY_OPERATION_SPEC_REQUIRED")
    if isinstance(spec, Mapping):
        from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query

        try:
            validated = validate_temporal_query(spec)
        except Exception as exc:
            code = getattr(exc, "code", None) or "QUERY_SPEC_INVALID"
            raise OrdinaryOperationError(str(code)) from exc
    parent = request.get("parent_operation_sha256")
    if parent is not None and (not isinstance(parent, str) or len(parent) != 64):
        raise OrdinaryOperationError("ORDINARY_OPERATION_PARENT_INVALID")
    cycle_probe = request.get("cycle_index")
    accounting_root = None
    lineage_kind = None
    continuation_blocker = None
    if isinstance(cycle_probe, int) and not isinstance(cycle_probe, bool) and cycle_probe > 1:
        accounting_root = _validated_lineage_link(
            store, request, journal=journal, focus=focus, market=market, cycle_index=int(cycle_probe)
        )
    elif isinstance(parent, str):
        prior = get_operation(store, parent)
        if prior.get("status") == "STOPPED":
            raise OrdinaryOperationError("ORDINARY_OPERATION_STOPPED")
        if prior.get("journal_scope") != journal or prior.get("owner_focus") != focus:
            raise OrdinaryOperationError("ORDINARY_OPERATION_CONTINUATION_MISMATCH")
    representation = request.get("representation")
    if representation is not None:
        # A later representation owns its own slot and journal; BASE stays untouched.
        if (
            not isinstance(representation, Mapping)
            or set(representation)
            != {"representation_id", "representation_semantic_version", "parent_session_id", "representation_payload_sha256", "scope_applied_sha256"}
            or any(not isinstance(value, str) or not value for value in representation.values())
            or len(str(representation["representation_payload_sha256"])) != 64
            or len(str(representation["scope_applied_sha256"])) != 64
        ):
            raise OrdinaryOperationError("ORDINARY_OPERATION_REPRESENTATION_INVALID")
        representation = {key: str(value) for key, value in representation.items()}
    cycle_index = request.get("cycle_index")
    if cycle_index is not None and (
        isinstance(cycle_index, bool) or not isinstance(cycle_index, int) or not 2 <= cycle_index <= 8
    ):
        raise OrdinaryOperationError("ORDINARY_OPERATION_CYCLE_INVALID")
    slot = str(request.get("scientific_slot_sha256") or "")
    if len(slot) != 64:
        from solana_alpha_lab.factory.hfic_evidence_identity import scientific_slot_sha256

        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id="BASE" if representation is None else representation["representation_id"],
            representation_semantic_version="HFIC-V1.2" if representation is None else representation["representation_semantic_version"],
            owner_focus=focus,
            cycle_index=cycle_index or 1,
        )
    identity_body = {
        "artifact_kind": OPERATION_KIND,
        "owner_request_text": text.strip(),
        "owner_focus": focus,
        "journal_scope": journal,
        "market_evidence_epoch_sha256": market,
        "scientific_slot_sha256": slot,
        "question_text": str(request.get("question_text") or text.strip()),
        "owner_cap": cap,
        "requested_completion": completion,
        "parent_operation_sha256": parent,
    }
    if representation is not None:
        identity_body["representation"] = representation
    if cycle_index:
        # Only an explicitly authorized additional AUTO cycle is marked; cycle 1 digests are unchanged.
        identity_body["cycle_index"] = cycle_index
        identity_body["accounting_root"] = accounting_root
    elif representation is not None:
        # A representation of an additional-cycle parent continues the representation's earlier spend.
        continuation, continuation_blocker = _representation_continuation_root(
            store, representation=representation, focus=focus, market=market, journal=journal
        )
        if continuation is not None:
            accounting_root, lineage_kind = continuation, REPRESENTATION_CONTINUATION
            identity_body["accounting_root"] = accounting_root
            identity_body["lineage_kind"] = lineage_kind
    digest = _sha(identity_body)
    for existing in list_operations(store):
        if existing.get("operation_sha256") == digest:
            return existing
    if not create_if_missing:
        raise OrdinaryOperationError("CALCULATION_REVISION_EXISTING_OPERATION_REQUIRED")
    if continuation_blocker:
        # A new segment never bypasses a stopped or unresolved member of its representation lineage,
        # and an earlier cycle never arrives after a later one.
        raise OrdinaryOperationError(continuation_blocker)
    stored = {
        **identity_body,
        "spec_sha256": None if not exact or validated is None else validated["spec_sha256"],
        "spec_canonical": None if not exact or not isinstance(spec, Mapping) else _canonical(dict(spec)),
        "operation_sha256": digest,
        "status": "OPEN",
        "schema": "smial.hfic-ordinary-operation",
        "schema_version": "1.0",
    }
    # The frozen accounting snapshot is stamped only on genuine creation. A
    # journal that already carries operations or looks pre-dates this runtime
    # and freezes at the shipped defaults, never at today's raised policy.
    if accounting_root is None:
        ensure_run_snapshot(store, journal, has_history=journal_has_history(store, journal))
    # A linked later cycle never freezes its own budget: it spends its lineage root's.
    _append(store, kind=OPERATION_KIND, body=stored, record_prefix="HFIC-ART-OP")
    stored["record_id"] = f"HFIC-ART-OP-{digest[:40].upper()}"
    return stored


def _validated_lineage_link(
    store: Any, request: Mapping[str, Any], *, journal: str, focus: str, market: str, cycle_index: int
) -> str:
    """A later AUTO cycle is a linked segment of one search: same market, focus and representation.

    The parent is an earlier operation of the same lineage. It may be completed (that is how the
    search continues), never stopped, and never with an unresolved reservation.
    """

    root = str(request.get("accounting_root") or "")
    parent = request.get("parent_operation_sha256")
    if len(root) != 64 or root == journal or not isinstance(parent, str) or len(parent) != 64:
        raise OrdinaryOperationError("ORDINARY_OPERATION_ACCOUNTING_ROOT_REQUIRED")
    from solana_alpha_lab.factory.hfic_memory_policy import cycle_search_key

    if journal != cycle_search_key(root, cycle_index):
        # Pure hash check, independent of any data root: the journal must be this root's cycle key.
        raise OrdinaryOperationError("ORDINARY_OPERATION_ACCOUNTING_ROOT_MISMATCH")
    lineage = [
        item
        for item in list_operations(store)
        if item.get("journal_scope") == root or (item.get("accounting_root") == root and _canonical_lineage_row(item))
    ]
    base = [item for item in lineage if item.get("journal_scope") == root and not item.get("accounting_root")]
    if not base:
        raise OrdinaryOperationError("ORDINARY_OPERATION_ACCOUNTING_ROOT_UNKNOWN")
    wanted_rep = request.get("representation")
    for item in base:
        if (
            item.get("owner_focus") != focus
            or item.get("market_evidence_epoch_sha256") != market
            or item.get("representation") != wanted_rep
        ):
            raise OrdinaryOperationError("ORDINARY_OPERATION_LINEAGE_MISMATCH")
    prior = next((item for item in lineage if item.get("operation_sha256") == parent), None)
    if prior is None:
        raise OrdinaryOperationError("ORDINARY_OPERATION_CONTINUATION_MISMATCH")
    prior = get_operation(store, parent)
    if prior.get("status") == STATUS_STOPPED:
        raise OrdinaryOperationError("ORDINARY_OPERATION_STOPPED")
    if _unresolved_reservations(store, prior):
        raise OrdinaryOperationError("EXTENSION_PARENT_HAS_PENDING_RESERVATION")
    return root


def _representation_continuation_root(
    store: Any, *, representation: Mapping[str, Any], focus: str, market: str, journal: str
) -> tuple[str | None, str | None]:
    """(root journal, blocker) of the representation lineage an additional-cycle representation continues.

    The root is the earliest root operation of the SAME representation, focus and market whose BASE parent
    belongs to an EARLIER cycle of the same (market, focus). Execution identity (parent session, payload,
    scope) stays the operation's own; only the budget is shared. BASE and other representations,
    focuses and markets are never merged. A stopped lineage member or an unresolved reservation refuses.
    """

    from solana_alpha_lab.factory.hfic_session import HficSessionError, load_session_bundle

    def _bundle(session_id: object) -> Mapping[str, Any] | None:
        if not isinstance(session_id, str) or not session_id:
            return None
        try:
            found = load_session_bundle(store, session_id)
        except HficSessionError:
            return None
        return found if isinstance(found, Mapping) else None

    def _cycle(bundle: Mapping[str, Any]) -> int:
        value = bundle.get("cycle_index")
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 1 else 1

    parent = _bundle(representation.get("parent_session_id"))
    if parent is None:
        return None, None
    members: list[Mapping[str, Any]] = []
    roots: list[Mapping[str, Any]] = []
    later_cycle_member = False
    for item in list_operations(store):
        rep = item.get("representation")
        if (
            not isinstance(rep, Mapping)
            or rep.get("representation_id") != representation.get("representation_id")
            or item.get("owner_focus") != focus
            or item.get("market_evidence_epoch_sha256") != market
            or item.get("journal_scope") == journal
        ):
            continue
        other = _bundle(rep.get("parent_session_id"))
        if other is None or str(other.get("owner_focus") or "") != focus:
            continue
        members.append(item)
        if _cycle(other) > _cycle(parent):
            later_cycle_member = True
        if not item.get("accounting_root") and _cycle(other) < _cycle(parent):
            roots.append((_cycle(other), item))
    if later_cycle_member:
        # An earlier cycle's child may not arrive after a later cycle's: that would give one
        # representation two independent budgets. The continuation runs forward in cycle order.
        return None, "ORDINARY_OPERATION_LINEAGE_OUT_OF_ORDER"
    if _cycle(parent) <= 1 or not roots:
        return None, None
    # The earliest cycle wins; within a cycle the earliest recorded. A missing timestamp sorts last.
    root = min(roots, key=lambda pair: (pair[0], str(pair[1].get("_recorded_at") or "~")))[1]
    blocker = None
    for item in members:
        if item.get("status") == STATUS_STOPPED:
            blocker = "ORDINARY_OPERATION_STOPPED"
            break
        if _unresolved_reservations(store, item):
            blocker = "EXTENSION_PARENT_HAS_PENDING_RESERVATION"
    return str(root["journal_scope"]), blocker


def journal_has_history(store: Any, journal_scope: str) -> bool:
    """True when this journal already spent or reserved something."""

    if any(item.get("journal_scope") == journal_scope for item in list_operations(store)):
        return True
    return bool(list_discovery_looks(store, journal_scope))


def _append(
    store: Any,
    *,
    kind: str,
    body: Mapping[str, Any],
    record_prefix: str,
    before_commit: Any = None,
) -> None:
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
    from solana_alpha_lab.factory.research_store import ResearchStoreError

    # Writer-lease contention is transient: retry a bounded number of times and
    # let the real compare-before-append rule decide (never a silent skip).
    for attempt in range(40):
        try:
            store.append([event], transaction_id=event.transaction_id, before_commit=before_commit)
            return
        except ResearchStoreError as exc:
            if getattr(exc, "code", str(exc)) != "WRITER_BUSY" or attempt >= 39:
                raise
            time.sleep(0.05)


def _append_transition(store: Any, updated: Mapping[str, Any], *, based_on_record_id: str) -> None:
    """Compare-before-append under the writer lease.

    A state row is written only while the row it was derived from is still the
    latest one, so a late landing or stamp cannot overwrite a newer stop.
    """

    digest = str(updated.get("operation_sha256") or "")
    body = {key: value for key, value in updated.items() if key not in {"record_id", "_recorded_at"}}

    def _check() -> None:
        if str(get_operation(store, digest).get("record_id") or "") != based_on_record_id:
            raise OrdinaryOperationError("ORDINARY_OPERATION_STATE_CHANGED")

    _append(store, kind=OPERATION_KIND, body=body, record_prefix="HFIC-ART-OP", before_commit=_check)


def _stamp_fingerprint(store: Any, operation_sha256: str, fingerprint: str) -> dict[str, Any]:
    """Record the first corpus fingerprint without reopening a stopped operation."""

    for _attempt in range(5):
        current = get_operation(store, operation_sha256)
        stamped = current.get("corpus_fingerprint")
        if stamped:
            if stamped != fingerprint:
                raise OrdinaryOperationError("ORDINARY_OPERATION_BINDING_MISMATCH")
            return current
        if current.get("status") == STATUS_STOPPED:
            raise OrdinaryOperationError("ORDINARY_OPERATION_STOPPED")
        updated = dict(current)
        updated["corpus_fingerprint"] = fingerprint
        try:
            _append_transition(store, updated, based_on_record_id=str(current.get("record_id") or ""))
        except OrdinaryOperationError as exc:
            if exc.code != "ORDINARY_OPERATION_STATE_CHANGED":
                raise
            continue
        return get_operation(store, operation_sha256)
    raise OrdinaryOperationError("ORDINARY_OPERATION_STATE_CHANGED")


def _refuse_stopped(operation: Mapping[str, Any]) -> None:
    if operation.get("status") == STATUS_STOPPED:
        raise OrdinaryOperationError("ORDINARY_OPERATION_STOPPED")


def _refuse_closed(store: Any, operation: Mapping[str, Any]) -> None:
    """No new or resumed evaluation once execution is over.

    A stopped operation and a completed one (its run's owner-final is saved and
    it no longer holds the research-universe gate) admit only replay of saved
    results and explicit calculation revisions; otherwise a look could land
    under a later profile than the one the run was frozen with.
    """

    _refuse_stopped(operation)
    if operation.get("status") == STATUS_OPEN and operation.get("requested_completion") == SCIENTIFIC_TERMINAL:
        if operation_lifecycle(store, operation)["effective_state"] == STATE_COMPLETED:
            raise OrdinaryOperationError("ORDINARY_OPERATION_COMPLETED")


def _canonical_lineage_row(item: Mapping[str, Any]) -> bool:
    """A row links a cycle to its root only when its journal IS cycle_search_key(root, cycle_index).

    Nothing else may borrow or poison a budget: an operation naming a wrong root is not a lineage member.
    """

    root = item.get("accounting_root")
    cycle = item.get("cycle_index")
    if (
        item.get("lineage_kind") == REPRESENTATION_CONTINUATION
        and isinstance(item.get("representation"), Mapping)
        and isinstance(root, str)
        and len(root) == 64
        and root != item.get("journal_scope")
    ):
        # A representation continuation is validated against the store when it is recorded; its journal is
        # the representation's own key (parent session, payload, scope), so there is no pure hash to recheck.
        return True
    if not isinstance(root, str) or len(root) != 64 or isinstance(cycle, bool) or not isinstance(cycle, int) or cycle < 2:
        return False
    from solana_alpha_lab.factory.hfic_memory_policy import cycle_search_key

    return item.get("journal_scope") == cycle_search_key(root, cycle)


def accounting_root_of(store: Any, journal: str) -> str:
    """The journal whose budget this journal spends. A cycle-1 or standalone journal is its own root."""

    for item in list_operations(store):
        if item.get("journal_scope") == journal and _canonical_lineage_row(item):
            return str(item["accounting_root"])
    return journal


def lineage_journals(store: Any, root: str) -> list[str]:
    """The root and every explicitly linked later-cycle journal. Execution identities stay separate."""

    journals = [root]
    for item in list_operations(store):
        scope = str(item.get("journal_scope") or "")
        if item.get("accounting_root") == root and _canonical_lineage_row(item) and scope and scope not in journals:
            journals.append(scope)
    return journals


def _looks(store: Any, journal: str) -> list[dict[str, Any]]:
    """Saved looks of the whole accounting lineage this journal belongs to."""

    journals = lineage_journals(store, accounting_root_of(store, journal))
    if journal not in journals:
        journals.append(journal)
    if len(journals) == 1:
        return list_discovery_looks(store, journal)
    combined: list[dict[str, Any]] = []
    for scope in journals:
        combined.extend(list_discovery_looks(store, scope))
    return combined


def _operation_result(
    looks: Sequence[Mapping[str, Any]],
    operation_sha256: str,
    spec_sha256: str | None = None,
) -> Mapping[str, Any] | None:
    """The result this operation reads: a current-version look, else the newest saved one.

    The earliest stored row must not shadow a later calculation revision.
    """

    from solana_alpha_lab.factory.hfic_temporal_discovery import (
        TEMPORAL_CALCULATION_VERSION,
        current_look_evidence,
    )

    owned = [
        item
        for item in looks
        if item.get("operation_sha256") == operation_sha256
        and isinstance(item.get("result"), Mapping)
        and (spec_sha256 is None or item.get("spec_sha256") == spec_sha256)
    ]
    current = [item for item in owned if item.get("calculation_version") == TEMPORAL_CALCULATION_VERSION]
    if current:
        return current[-1]
    return current_look_evidence(owned[-1], owned) if owned else None


def _same_active_profile_look(
    store: Any,
    looks: Sequence[Mapping[str, Any]],
    spec_sha256: str,
    *,
    fingerprint: str | None,
    census: Sequence[Mapping[str, Any]] | None = None,
    observations: Sequence[Mapping[str, Any]] | None = None,
    admitted: Mapping[str, Any] | None = None,
    scope_applied_sha256: str | None = None,
) -> Mapping[str, Any] | None:
    """A saved look of this spec, profile and rows. A new operation may read it."""

    from solana_alpha_lab.factory.hfic_research_universe_policy import effective_policy
    from solana_alpha_lab.factory.hfic_temporal_discovery import TEMPORAL_CURRENT_CALCULATION_VERSIONS

    active = effective_policy(store).get("semantic_sha256")
    if not isinstance(active, str) or not active:
        return None
    rows_known = census is not None and observations is not None and isinstance(admitted, Mapping)
    matched: list[Mapping[str, Any]] = []
    for item in looks:
        if item.get("spec_sha256") != spec_sha256 or item.get("new_look") is not True:
            continue
        if not isinstance(item.get("result"), Mapping):
            continue
        prior = ((item.get("result") or {}).get("universe_policy") or {}).get("semantic_sha256")
        if prior != active:
            continue
        if rows_known:
            from solana_alpha_lab.factory.hfic_grounded_discovery import same_rows_under_policy

            if not same_rows_under_policy(
                item,
                admitted=admitted,
                census=census,
                observations=observations,
                policy_sha=str(prior),
                scope_applied_sha256=scope_applied_sha256,
            ):
                continue
        else:
            prior_operation = item.get("operation_sha256")
            prior_fingerprint = None
            if isinstance(prior_operation, str) and prior_operation:
                prior_fingerprint = get_operation(store, prior_operation).get("corpus_fingerprint")
            if not (fingerprint and prior_fingerprint and fingerprint == prior_fingerprint):
                continue
        matched.append(item)
    # Only the live calculation version may cross-operation REPLAY.
    # An older saved version must fall through to classify_temporal_look so
    # CALCULATION_REVISION still requires an explicit correction (never a
    # silent spendable MAIN / free REPLAY of stale arithmetic).
    current = [item for item in matched if item.get("calculation_version") in TEMPORAL_CURRENT_CALCULATION_VERSIONS]
    return current[-1] if current else None


def result_readout(look: Mapping[str, Any]) -> dict[str, Any]:
    """Version, lineage and coherence of one saved result. Reads no values."""

    from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_result_coherence

    result = look.get("result") if isinstance(look.get("result"), Mapping) else {}
    from solana_alpha_lab.factory.hfic_grounded_discovery import descriptive_return_readout
    coherence = temporal_result_coherence(result)
    body: dict[str, Any] = {
        "result_ref": look.get("record_id"),
        "result_sha256": look.get("result_sha256"),
        "calculation_version": look.get("calculation_version"),
        "look_class": look.get("look_class"),
        "new_look": look.get("new_look"),
        "result_coherence": coherence["status"],
        "science_ready": coherence["status"] == "COHERENT" and result.get("technical_failure") is not True,
        "descriptive_readout": descriptive_return_readout(result),
    }
    if isinstance(look.get("revision_of"), Mapping):
        body["revision_of"] = dict(look["revision_of"])
        body["assessment_advisory"] = "REVIEW_REQUIRED_FOR_ASSESSMENT_BOUND_TO_SOURCE"
    if coherence["status"] != "COHERENT":
        body["incoherent_fields"] = coherence["issues"]
        body["repair_action"] = coherence["repair_action"]
        body["next_action"] = "CORRECT_CALCULATION_REVISION"
    return body


def binding_fingerprint(cohorts: Sequence[Mapping[str, Any]] | None) -> str | None:
    """Hash declared cohort metadata. Does not read parquet values."""

    if not cohorts:
        return None
    rows = []
    for item in cohorts:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "cohort_id": item.get("cohort_id"),
                "census_sha256": item.get("census_sha256"),
                "observations_sha256": item.get("observations_sha256"),
                "dataset_id": item.get("dataset_id"),
                "evidence_role": item.get("evidence_role"),
                "holdout": item.get("holdout"),
            }
        )
    if not rows or not any(row.get("census_sha256") for row in rows):
        return None
    return _sha({"cohorts": rows})


def _feature_previews(store: Any, journal: str) -> list[dict[str, Any]]:
    journals = set(lineage_journals(store, accounting_root_of(store, journal))) | {journal}
    return [
        item
        for item in _iter_kind(store, "DISCOVERY_FEATURE_PREVIEW")
        if item.get("journal_scope") in journals
    ]


def _assert_preflight_journal(
    store: Any,
    operation: Mapping[str, Any],
    journal_scope: str,
    *,
    repo_root: Any,
    data_root: Any,
) -> None:
    """Journal must be the preflight search key for this market and focus."""

    from pathlib import Path

    from solana_alpha_lab.factory.hfic_evidence_identity import (
        EvidenceIdentityError,
        compute_split_identity,
    )
    from solana_alpha_lab.factory.hfic_memory_policy import effective_policy
    from solana_alpha_lab.factory.hfic_session import PROMPT_VERSION, search_key_sha256

    try:
        split = compute_split_identity(Path(repo_root), Path(data_root), store=store)
    except EvidenceIdentityError as exc:
        raise OrdinaryOperationError(str(exc)) from exc
    epoch = str(split.get("market_evidence_epoch_sha256") or "")
    if epoch != str(operation.get("market_evidence_epoch_sha256") or ""):
        raise OrdinaryOperationError("ORDINARY_OPERATION_MARKET_MISMATCH")
    policy = effective_policy(store)
    memory = str(policy.get("memory_eligibility_sha256") or "")
    expected = search_key_sha256(
        epoch,
        str(operation.get("owner_focus") or ""),
        PROMPT_VERSION,
        memory or None,
        None,
    )
    representation = operation.get("representation")
    if isinstance(representation, Mapping):
        from solana_alpha_lab.factory.normalized_trajectory_episodes_v1 import (
            REPRESENTATION_ID,
            representation_search_key,
        )

        if representation.get("representation_id") != REPRESENTATION_ID:
            raise OrdinaryOperationError("ORDINARY_OPERATION_REPRESENTATION_INVALID")
        # The ladder keys a child from the receipt of the exact BASE parent it climbs from. For an
        # additional AUTO cycle that parent's own search key is the cycle key, not the cycle-1 key.
        base_key = expected
        parent_id = str(representation.get("parent_session_id") or "")
        if parent_id:
            from solana_alpha_lab.factory.hfic_session import HficSessionError, load_session_bundle

            try:
                parent_bundle = load_session_bundle(store, parent_id)
            except HficSessionError:
                parent_bundle = None
            if isinstance(parent_bundle, Mapping):
                parent_market = parent_bundle.get("market_evidence_epoch_sha256")
                if isinstance(parent_market, str) and parent_market and parent_market != epoch:
                    raise OrdinaryOperationError("ORDINARY_OPERATION_MARKET_MISMATCH")
                if str(parent_bundle.get("owner_focus") or "") != str(operation.get("owner_focus") or ""):
                    raise OrdinaryOperationError("ORDINARY_OPERATION_PARENT_FOCUS_MISMATCH")
                if parent_bundle.get("ladder_representation_id") not in (None, "", "BASE") or parent_bundle.get("control_session_id"):
                    raise OrdinaryOperationError("ORDINARY_OPERATION_PARENT_NOT_BASE")
                # Only the key the parent's own identity derives is inherited (its memory policy, and its
                # cycle key for an additional AUTO cycle); anything else keeps the strict current derivation.
                parent_derived = search_key_sha256(
                    epoch,
                    str(operation.get("owner_focus") or ""),
                    PROMPT_VERSION,
                    str(parent_bundle.get("memory_eligibility_sha256") or "") or None,
                    None,
                )
                parent_cycle = parent_bundle.get("cycle_index")
                if isinstance(parent_cycle, int) and not isinstance(parent_cycle, bool) and parent_cycle > 1:
                    from solana_alpha_lab.factory.hfic_memory_policy import cycle_search_key

                    parent_derived = cycle_search_key(parent_derived, parent_cycle)
                if parent_bundle.get("search_key_sha256") == parent_derived:
                    base_key = parent_derived
        expected = representation_search_key(
            base_key,
            str(representation.get("parent_session_id") or ""),
            str(representation.get("representation_payload_sha256") or ""),
            str(representation.get("scope_applied_sha256") or ""),
        )
    if isinstance(operation.get("cycle_index"), int):
        from solana_alpha_lab.factory.hfic_memory_policy import cycle_search_key

        if operation.get("accounting_root") != expected:
            # The additional cycle spends the lineage root's budget; the root is the key before the cycle suffix.
            raise OrdinaryOperationError("ORDINARY_OPERATION_ACCOUNTING_ROOT_MISMATCH")
        expected = cycle_search_key(expected, int(operation["cycle_index"]))
    if journal_scope != expected:
        raise OrdinaryOperationError("ORDINARY_OPERATION_JOURNAL_NOT_CANONICAL")


def _occupancy(
    store: Any,
    looks: Sequence[Mapping[str, Any]],
    kind: str,
    *,
    journal: str,
) -> dict[str, int]:
    """One arithmetic for every surface: occupied = completed + outstanding reservations."""

    limits = limits_or_defaults(store, journal)
    journals = set(lineage_journals(store, accounting_root_of(store, journal))) | {journal}
    if kind == "preview":
        previews = _feature_previews(store, journal)
        used = {
            str(item.get("preview_sha256") or "")
            for item in previews
            if item.get("preview_sha256")
        }
        landed_specs = {
            str(item.get("spec_sha256") or "")
            for item in previews
            if item.get("spec_sha256")
        }
        pending = {
            str(item.get("spec_sha256") or "")
            for item in _iter_kind(store, RESERVATION_KIND)
            if item.get("journal_scope") in journals
            and item.get("look_class") == "PREVIEW"
            and str(item.get("spec_sha256") or "") not in landed_specs
        }
        completed_n, pending_n, limit = len(used), len(pending), limits["preview_total"]
    else:
        look_class = "ADAPTIVE" if kind == "adaptive" else "MAIN"
        completed = {
            str(item.get("spec_sha256") or "")
            for item in looks
            if item.get("look_class") == look_class
            and item.get("new_look") is True
            and isinstance(item.get("result"), Mapping)
        }
        in_flight = {
            str(item.get("spec_sha256") or "")
            for item in _iter_kind(store, RESERVATION_KIND)
            if item.get("journal_scope") in journals
            and item.get("look_class") == look_class
            and str(item.get("spec_sha256") or "") not in completed
        }
        completed_n, pending_n = len(completed), len(in_flight)
        limit = limits["adaptive_total"] if kind == "adaptive" else limits["main_total"]
    occupied = completed_n + pending_n
    return {
        "limit": limit,
        "completed": completed_n,
        "pending": pending_n,
        "occupied": occupied,
        "remaining": max(0, limit - occupied),
        "deficit": max(0, occupied - limit),
    }


def journal_occupancy(store: Any, journal: str) -> dict[str, dict[str, int]]:
    """Owner readout: limit, completed, pending, remaining and deficit per budget kind."""

    looks = _looks(store, journal)
    return {kind: _occupancy(store, looks, kind, journal=journal) for kind in ("main", "adaptive", "preview")}


def _protocol_remaining(
    store: Any,
    looks: Sequence[Mapping[str, Any]],
    kind: str,
    *,
    journal: str,
) -> int:
    return _occupancy(store, looks, kind, journal=journal)["remaining"]


def extension_parent(store: Any, operation_sha256: str) -> dict[str, Any]:
    """The exact operation a scope extension may continue, or a typed refusal.

    A stopped run is never reopened by an extension, a completed run is not
    continued by it, and an unresolved reservation must be resumed first so a
    larger ceiling can never be used to abandon and replace pending work.
    """

    operation = get_operation(store, operation_sha256)
    if operation.get("status") == STATUS_STOPPED:
        raise OrdinaryOperationError("ORDINARY_OPERATION_STOPPED")
    lifecycle = operation_lifecycle(store, operation)
    if lifecycle.get("effective_state") == STATE_COMPLETED:
        raise OrdinaryOperationError("EXTENSION_PARENT_COMPLETED")
    if _unresolved_reservations(store, operation):
        raise OrdinaryOperationError("EXTENSION_PARENT_HAS_PENDING_RESERVATION")
    return operation


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
    if kind == "preview":
        done = {
            str(item.get("preview_sha256") or item.get("spec_sha256") or "")
            for item in _feature_previews(store, journal)
            if item.get("operation_sha256") == digest
        }
        done.discard("")
        pending = {
            str(item.get("spec_sha256") or "")
            for item in _reservations(store, digest)
            if item.get("look_class") == "PREVIEW"
            and str(item.get("spec_sha256") or "")
            not in {
                str(item.get("spec_sha256") or "")
                for item in _feature_previews(store, journal)
                if item.get("operation_sha256") == digest
            }
        }
        pending.discard("")
        return len(done) + len(pending)
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
    protocol = _protocol_remaining(
        store, looks, kind, journal=str(operation.get("journal_scope") or "")
    )
    explicit = (operation.get("owner_cap") or {}).get(kind)
    if explicit is None:
        return protocol
    spent = _spent_by_operation(store, operation, kind)
    return max(0, min(int(explicit) - spent, protocol))


def _admit(store: Any, operation: Mapping[str, Any], *, repo_root: Any = None, data_root: Any = None) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_evidence_identity import resolve_scientific_admission
    from solana_alpha_lab.factory.hfic_repair_continuation import (
        list_repair_continuation_dispositions,
    )
    from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

    sessions = list_hfic_sessions(store)
    # AUTO and distinct-focus are a pool shared by the whole market epoch, so
    # their cap comes from the epoch's own frozen scope, never from one journal.
    pool = epoch_limits(store, str(operation.get("market_evidence_epoch_sha256") or ""))
    market_basis = None
    if repo_root is not None and data_root is not None:
        from pathlib import Path
        from solana_alpha_lab.factory.hfic_evidence_identity import (
            EvidenceIdentityError, compute_market_epoch_for_data_root,
        )

        try:
            _epoch, market_basis = compute_market_epoch_for_data_root(Path(repo_root), Path(data_root))
        except EvidenceIdentityError as exc:
            raise OrdinaryOperationError(exc.code) from exc
        if _epoch != operation.get("market_evidence_epoch_sha256"):
            raise OrdinaryOperationError("ORDINARY_OPERATION_MARKET_MISMATCH")
    return resolve_scientific_admission(
        sessions,
        market_evidence_epoch=str(operation.get("market_evidence_epoch_sha256") or ""),
        market_evidence_basis=market_basis,
        representation_id=str((operation.get("representation") or {}).get("representation_id") or "BASE"),
        representation_semantic_version=str(
            (operation.get("representation") or {}).get("representation_semantic_version") or "HFIC-V1.2"
        ),
        owner_focus=str(operation.get("owner_focus") or ""),
        requested_cycle_index=int(operation.get("cycle_index") or 1),
        auto_sessions_per_market=pool["auto_cycles_per_market"],
        max_distinct_focuses=pool["distinct_focuses_per_market"],
        repair_continuations=list_repair_continuation_dispositions(store),
    )


def _search_terminal_conflict(
    operation: Mapping[str, Any], looks: Sequence[Mapping[str, Any]], spec: Mapping[str, Any], *, main_total: int
) -> None:
    if operation.get("requested_completion") != SCIENTIFIC_TERMINAL:
        return
    from solana_alpha_lab.factory.hfic_temporal_discovery import (
        assess_tier_progress,
        validate_temporal_query,
    )

    validated = validate_temporal_query(spec)
    progress = assess_tier_progress(looks, freeze_worthy=False, compound_applicable=True, main_total=main_total)
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


def _fresh_temporal_warnings(
    store: Any, validated: Mapping[str, Any], binding_cohorts: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Check bound metadata before spending a fresh look or loading values."""
    from solana_alpha_lab.factory.hfic_temporal_discovery import _require_bound_schedule, universe_question_guard
    from solana_alpha_lab.factory.hfic_research_universe_policy import effective_policy

    try:
        if binding_cohorts is not None:
            _require_bound_schedule(binding_cohorts, validated["scientific_body"], validated["scientific_body"].get("schedule_lateness_seconds"))
        return universe_question_guard(validated["scientific_body"], effective_policy(store)["definition"])
    except GroundedDiscoveryError as exc:
        raise OrdinaryOperationError(exc.code) from exc


def authorize_temporal_attempt(
    store: Any,
    *,
    operation_sha256: str,
    spec: Mapping[str, Any],
    journal_scope: str,
    binding_cohorts: Sequence[Mapping[str, Any]] | None = None,
    verified_market: str | None = None,
    look_kind: str = "main",
    repo_root: Any = None,
    data_root: Any = None,
) -> dict[str, Any]:
    """One admission contract for CLI execute/preview and recorded-query."""

    if look_kind == "preview":
        operation = get_operation(store, operation_sha256)
        if str(operation.get("journal_scope") or "") != journal_scope:
            raise OrdinaryOperationError("ORDINARY_OPERATION_JOURNAL_MISMATCH")
        if not isinstance(verified_market, str) or len(verified_market) != 64:
            raise OrdinaryOperationError("ORDINARY_OPERATION_MARKET_UNVERIFIED")
        if verified_market != operation.get("market_evidence_epoch_sha256"):
            raise OrdinaryOperationError("ORDINARY_OPERATION_MARKET_MISMATCH")
        if repo_root is not None and data_root is not None:
            _assert_preflight_journal(
                store, operation, journal_scope, repo_root=repo_root, data_root=data_root
            )
        spec_sha = hashlib.sha256(_canonical(dict(spec)).encode("utf-8")).hexdigest()
        owned = [
            item
            for item in _feature_previews(store, journal_scope)
            if item.get("operation_sha256") == operation.get("operation_sha256")
            and item.get("spec_sha256") == spec_sha
        ]
        if owned:
            from solana_alpha_lab.factory.hfic_temporal_discovery import saved_feature_preview
            try:
                payload = saved_feature_preview(store, journal_scope=journal_scope,
                    operation_sha256=operation_sha256, spec_sha256=spec_sha, binding=binding_cohorts or [])
            except GroundedDiscoveryError as exc:
                raise OrdinaryOperationError(exc.code) from exc
            return {
                "disposition": "REPLAY",
                "values_loaded": False,
                "writes": False,
                "operation": operation,
                "look_class": "PREVIEW",
                "preview_sha256": owned[-1].get("preview_sha256"),
                "replayed_without_loader": True,
                "preview_payload": payload,
            }
        # A stopped or completed operation replays saved previews, never a new one.
        _refuse_closed(store, operation)
        fingerprint = binding_fingerprint(binding_cohorts)
        stamped = operation.get("corpus_fingerprint")
        if fingerprint and stamped and fingerprint != stamped:
            raise OrdinaryOperationError("ORDINARY_OPERATION_BINDING_MISMATCH")
        admission = _admit(store, operation, repo_root=repo_root, data_root=data_root)
        if admission.get("action") == "STOP":
            raise OrdinaryOperationError(
                str(admission.get("reason_code") or "SCIENTIFIC_ADMISSION_STOP")
            )
        from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

        if _closed_slot(admission, list_hfic_sessions(store)):
            raise OrdinaryOperationError("ORDINARY_OPERATION_SLOT_CLOSED")
        if owner_allowance(store, operation, "preview") < 1:
            raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED")
        if spec.get("schema") == "smial.hfic-temporal-query":
            from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query
            try:
                warnings = _fresh_temporal_warnings(store, validate_temporal_query(spec), binding_cohorts)
            except GroundedDiscoveryError as exc:
                raise OrdinaryOperationError(exc.code) from exc
        else:
            warnings = []
        _require_published_logical_content(data_root)
        _reserve(store, operation, spec_sha256=spec_sha, look_class="preview")
        if fingerprint and not stamped:
            operation = _stamp_fingerprint(store, operation_sha256, fingerprint)
        return {
            "disposition": "EXECUTE",
            "values_loaded": False,
            "writes": False,
            "operation": operation,
            "admission": admission,
            "look_class": "PREVIEW",
            "query_warnings": warnings,
        }
    return gate_before_values(
        store,
        operation_sha256=operation_sha256,
        spec=spec,
        journal_scope=journal_scope,
        binding_cohorts=binding_cohorts,
        verified_market=verified_market,
        repo_root=repo_root,
        data_root=data_root,
    )


def require_focus_population(owner_focus: object, spec: Mapping[str, Any]) -> None:
    """The focus owns the collection (receipt, packet, card, look budget); the
    query population must name that same corpus before any value is read."""

    from solana_alpha_lab.factory.opportunity_episodes import (
        COLLECTION as EPISODE_COLLECTION,
        POPULATION as EPISODE_POPULATION,
        collection_for_focus,
    )

    focus_is_episode = collection_for_focus(str(owner_focus or "")) == EPISODE_COLLECTION
    if focus_is_episode != (isinstance(spec, Mapping) and spec.get("population") == EPISODE_POPULATION):
        raise OrdinaryOperationError("FOCUS_POPULATION_MISMATCH")


EPISODE_VIEW_SCHEMA = "smial.episode-normalized-view-request"


def episode_view_descriptor_sha256(
    *,
    representation_id: str,
    representation_semantic_version: str,
    prefix_points: Sequence[str],
    scope_rule_sha256: str,
    scope_applied_sha256: str,
    parent_session_id: str,
    parent_search_key: str,
) -> str:
    """Identity of a prefix-view request, known before any value exists.

    A policy number, a preset display name or the form of the result never
    enters it; a changed scope rule, applied evidence or representation does.
    """

    return _sha(
        {
            "schema": EPISODE_VIEW_SCHEMA,
            "representation_id": representation_id,
            "representation_semantic_version": representation_semantic_version,
            "prefix_points": list(prefix_points),
            "scope_rule_sha256": scope_rule_sha256,
            "scope_applied_sha256": scope_applied_sha256,
            "parent_session_id": parent_session_id,
            "parent_search_key": parent_search_key,
        }
    )


def authorize_episode_view(
    store: Any,
    *,
    operation_sha256: str,
    journal_scope: str,
    descriptor_sha256: str,
    verified_market: str | None,
    repo_root: Any = None,
    data_root: Any = None,
) -> dict[str, Any]:
    """PREVIEW gate of a value-bearing prefix view. Runs before any value is read.

    The reservation is the request descriptor, so a result that does not exist
    yet is never needed to decide. The same descriptor again is a repeat: no
    new spend. Metadata-only scope counts and policy previews never come here.
    """

    operation = get_operation(store, operation_sha256)
    if str(operation.get("journal_scope") or "") != journal_scope:
        raise OrdinaryOperationError("ORDINARY_OPERATION_JOURNAL_MISMATCH")
    if not isinstance(verified_market, str) or len(verified_market) != 64:
        raise OrdinaryOperationError("ORDINARY_OPERATION_MARKET_UNVERIFIED")
    if verified_market != operation.get("market_evidence_epoch_sha256"):
        raise OrdinaryOperationError("ORDINARY_OPERATION_MARKET_MISMATCH")
    if repo_root is not None and data_root is not None:
        _assert_preflight_journal(store, operation, journal_scope, repo_root=repo_root, data_root=data_root)
    landed = {str(item.get("spec_sha256") or "") for item in _feature_previews(store, journal_scope)}
    if descriptor_sha256 in landed:
        # Exactly the same question, already landed, is not a new exposure. It is a rebuild of a disclosed view.
        return {
            "disposition": "REPEAT",
            "values_loaded": False,
            "writes": False,
            "operation": operation,
            "descriptor_sha256": descriptor_sha256,
        }
    reserved_by = {
        str(item.get("operation_sha256") or "")
        for item in _iter_kind(store, RESERVATION_KIND)
        if item.get("journal_scope") == journal_scope
        and item.get("look_class") == "PREVIEW"
        and str(item.get("spec_sha256") or "") == descriptor_sha256
    }
    if reserved_by:
        # Reserved but never landed (a crash after the reservation): finish it. It spends nothing new.
        if str(operation.get("operation_sha256") or "") not in reserved_by:
            raise OrdinaryOperationError("EPISODE_VIEW_PENDING_IN_OTHER_OPERATION")
        _refuse_closed(store, operation)
        return {
            "disposition": "RESUME",
            "values_loaded": False,
            "writes": True,
            "operation": operation,
            "descriptor_sha256": descriptor_sha256,
        }
    _refuse_closed(store, operation)
    if owner_allowance(store, operation, "preview") < 1:
        raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED")
    _reserve(store, operation, spec_sha256=descriptor_sha256, look_class="preview")
    return {
        "disposition": "EXECUTE",
        "values_loaded": False,
        "writes": True,
        "operation": operation,
        "descriptor_sha256": descriptor_sha256,
    }


def land_episode_view(
    store: Any,
    *,
    operation_sha256: str,
    journal_scope: str,
    descriptor_sha256: str,
    payload_sha256: str,
    git_sha: str,
) -> None:
    """Bind the computed payload hash to the reservation made from its request descriptor."""

    from solana_alpha_lab.factory.hfic_temporal_discovery import persist_feature_preview

    persist_feature_preview(
        store,
        journal_scope=journal_scope,
        preview={"preview_sha256": payload_sha256},
        git_sha=git_sha,
        input_sha256=descriptor_sha256,
        operation_sha256=operation_sha256,
        spec_sha256=descriptor_sha256,
    )


def gate_before_values(
    store: Any,
    *,
    operation_sha256: str,
    spec: Mapping[str, Any],
    journal_scope: str,
    binding_cohorts: Sequence[Mapping[str, Any]] | None = None,
    verified_market: str | None = None,
    repo_root: Any = None,
    data_root: Any = None,
    correction: Mapping[str, Any] | None = None,
    census: Sequence[Mapping[str, Any]] | None = None,
    observations: Sequence[Mapping[str, Any]] | None = None,
    admitted: Mapping[str, Any] | None = None,
    scope_applied_sha256: str | None = None,
) -> dict[str, Any]:
    """Metadata, admission and cap. Does not load outcome rows.

    An explicit ``correction`` of this operation's saved result is a
    CALCULATION_REVISION: no cap check and no reservation. The same spec
    without it reads the saved result as it is.
    """

    operation = get_operation(store, operation_sha256)
    if str(operation.get("journal_scope") or "") != journal_scope:
        raise OrdinaryOperationError("ORDINARY_OPERATION_JOURNAL_MISMATCH")
    if not isinstance(verified_market, str) or len(verified_market) != 64:
        raise OrdinaryOperationError("ORDINARY_OPERATION_MARKET_UNVERIFIED")
    if verified_market != operation.get("market_evidence_epoch_sha256"):
        raise OrdinaryOperationError("ORDINARY_OPERATION_MARKET_MISMATCH")
    require_focus_population(operation.get("owner_focus"), spec)
    if repo_root is not None and data_root is not None:
        _assert_preflight_journal(
            store, operation, journal_scope, repo_root=repo_root, data_root=data_root
        )
    from solana_alpha_lab.factory.hfic_temporal_discovery import (
        classify_temporal_look,
        validate_temporal_query,
    )

    try:
        validated = validate_temporal_query(spec)
    except Exception as exc:
        code = getattr(exc, "code", None) or "QUERY_SPEC_INVALID"
        raise OrdinaryOperationError(str(code)) from exc
    if operation.get("spec_sha256") and validated["spec_sha256"] != operation.get("spec_sha256"):
        raise OrdinaryOperationError("ORDINARY_OPERATION_SPEC_MISMATCH")
    if operation.get("spec_canonical") and _canonical(dict(spec)) != operation.get("spec_canonical"):
        raise OrdinaryOperationError("ORDINARY_OPERATION_SPEC_MISMATCH")
    fingerprint = binding_fingerprint(binding_cohorts)
    stamped = operation.get("corpus_fingerprint")
    if fingerprint and stamped and fingerprint != stamped:
        raise OrdinaryOperationError("ORDINARY_OPERATION_BINDING_MISMATCH")
    looks = _looks(store, journal_scope)
    _search_terminal_conflict(
        operation, looks, spec, main_total=limits_or_defaults(store, journal_scope)["main_total"]
    )
    from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

    admission = _admit(store, operation, repo_root=repo_root, data_root=data_root)
    if admission.get("action") == "STOP":
        raise OrdinaryOperationError(str(admission.get("reason_code") or "SCIENTIFIC_ADMISSION_STOP"))
    from solana_alpha_lab.factory.hfic_temporal_discovery import (
        TEMPORAL_CALCULATION_VERSION,
        TEMPORAL_CALCULATION_VERSION_V5,
        saved_downside_revision,
        verify_calculation_revision_source,
    )

    stored = _operation_result(looks, operation_sha256, validated["spec_sha256"])
    if stored is None and correction is None:
        stored = _same_active_profile_look(
            store,
            looks,
            validated["spec_sha256"],
            fingerprint=fingerprint,
            census=census,
            observations=observations,
            admitted=admitted,
            scope_applied_sha256=scope_applied_sha256,
        )
    target_version = TEMPORAL_CALCULATION_VERSION
    if correction is not None:
        saved = saved_downside_revision(
            [item for item in looks if item.get("operation_sha256") == operation_sha256
             and item.get("spec_sha256") == validated["spec_sha256"]],
            correction,
        )
        if saved is not None:
            stored = saved
            target_version = TEMPORAL_CALCULATION_VERSION_V5
    if stored is not None and correction is not None:
        # A correction request is checked even when its revision already exists.
        try:
            verify_calculation_revision_source(
                looks,
                correction=correction,
                spec=spec,
                operation_sha256=operation_sha256,
                target_calculation_version=target_version,
            )
        except GroundedDiscoveryError as exc:
            raise OrdinaryOperationError(exc.code) from exc
        if stored.get("calculation_version") != target_version:
            stored = None
    if stored is not None:
        evidence: dict[str, Any] = {
            "replayed_without_evaluator": True,
            "calculation_version": stored.get("calculation_version"),
            "result_sha256": stored.get("result_sha256"),
            "result_refs": [stored.get("record_id")],
            "result": stored.get("result"),
            "descriptive_readout": result_readout(stored)["descriptive_readout"],
            "journal_scope": journal_scope,
            "spec_sha256": validated["spec_sha256"],
            "data_binding_sha256": stored.get("data_binding_sha256"),
            "new_look": False,
            "writes": False,
            "values_loaded": False,
            "queries": [
                {
                    "query_id": (stored.get("result") or {}).get("query_id"),
                    "spec_sha256": validated["spec_sha256"],
                    "record_id": stored.get("record_id"),
                    "look_class": "RETRY_SAME_BYTES",
                    "new_look": False,
                }
            ],
        }
        if isinstance(stored.get("revision_of"), Mapping):
            evidence["revision_of"] = dict(stored["revision_of"])
            evidence["assessment_advisory"] = "REVIEW_REQUIRED_FOR_ASSESSMENT_BOUND_TO_SOURCE"
        if correction is not None:
            evidence["correction_already_applied"] = True
        return {
            "disposition": "REPLAY",
            "values_loaded": False,
            "writes": False,
            "operation": operation,
            "admission": admission,
            "result_readout": result_readout(stored),
            "evidence": evidence,
        }
    if correction is not None:
        try:
            source = verify_calculation_revision_source(
                looks,
                correction=correction,
                spec=spec,
                operation_sha256=operation_sha256,
            )
        except GroundedDiscoveryError as exc:
            raise OrdinaryOperationError(exc.code) from exc
        if _closed_slot(admission, list_hfic_sessions(store)):
            from solana_alpha_lab.factory.hfic_temporal_discovery import (
                TEMPORAL_CALCULATION_VERSION_V4,
                temporal_result_coherence,
            )

            # The slot remains closed to science. Only a source-bound,
            # output-only enrichment of a coherent V4 result may pass.
            if not (
                source.get("calculation_version") == TEMPORAL_CALCULATION_VERSION_V4
                and TEMPORAL_CALCULATION_VERSION == TEMPORAL_CALCULATION_VERSION_V5
                and temporal_result_coherence(source["result"])["status"] == "COHERENT"
            ):
                raise OrdinaryOperationError("ORDINARY_OPERATION_SLOT_CLOSED")
        return {
            "disposition": "CORRECTION",
            "values_loaded": False,
            "writes": False,
            "operation": operation,
            "admission": admission,
            "spec_sha256": validated["spec_sha256"],
            "look_class": "CALCULATION_REVISION",
            "source_result_ref": source.get("record_id"),
            "source_result_sha256": source.get("result_sha256"),
            "source_calculation_version": source.get("calculation_version"),
        }
    # Saved results and owner corrections stay readable after a stop or
    # completion; a new or resumed evaluation does not start.
    _refuse_closed(store, operation)
    pending = [
        item
        for item in _reservations(store, operation_sha256)
        if item.get("spec_sha256") == validated["spec_sha256"]
    ]
    if pending:
        return {
            "disposition": "RESUME",
            "values_loaded": False,
            "writes": False,
            "operation": operation,
            "admission": admission,
            "spec_sha256": validated["spec_sha256"],
            "look_class": pending[0].get("look_class"),
        }
    if _closed_slot(admission, list_hfic_sessions(store)):
        raise OrdinaryOperationError("ORDINARY_OPERATION_SLOT_CLOSED")
    warnings = _fresh_temporal_warnings(store, validated, binding_cohorts)
    try:
        from solana_alpha_lab.factory.hfic_research_universe_policy import effective_policy

        active_policy = effective_policy(store).get("semantic_sha256")
        classify_looks = []
        policy_shift = False
        rows_known = census is not None and observations is not None and isinstance(admitted, Mapping)
        for item in looks:
            prior_policy = ((item.get("result") or {}).get("universe_policy") or {}).get("semantic_sha256")
            policy_differs = (
                item.get("spec_sha256") == validated["spec_sha256"]
                and prior_policy
                and active_policy
                and prior_policy != active_policy
            )
            if not policy_differs:
                classify_looks.append(item)
                continue
            if rows_known:
                from solana_alpha_lab.factory.hfic_grounded_discovery import same_rows_under_policy

                pure_policy = same_rows_under_policy(
                    item,
                    admitted=admitted,
                    census=census,
                    observations=observations,
                    policy_sha=str(prior_policy),
                    scope_applied_sha256=scope_applied_sha256,
                )
            else:
                prior_operation = item.get("operation_sha256")
                prior_fingerprint = None
                if isinstance(prior_operation, str) and prior_operation:
                    prior_fingerprint = get_operation(store, prior_operation).get("corpus_fingerprint")
                pure_policy = bool(fingerprint and prior_fingerprint and fingerprint == prior_fingerprint)
            if pure_policy:
                policy_shift = True
            classify_looks.append({**item, "spec_sha256": "DATA_BINDING_CHANGED"})
        classify_spec = spec
        if policy_shift:
            classify_spec = dict(spec)
            classify_spec["adaptation_of"] = validated["spec_sha256"]
        classified = classify_temporal_look(
            classify_looks, classify_spec, limits=limits_or_defaults(store, journal_scope)
        )
    except Exception as exc:
        code = getattr(exc, "code", None) or "QUERY_SPEC_INVALID"
        raise OrdinaryOperationError(str(code)) from exc
    look_class = str(classified.get("look_class") or "MAIN")
    if look_class == "CALCULATION_REVISION":
        # Never convert a revision into a spendable MAIN.
        raise OrdinaryOperationError("CALCULATION_REVISION_REQUIRES_EXPLICIT_CORRECTION")
    if look_class not in {"MAIN", "ADAPTIVE"}:
        look_class = "ADAPTIVE" if validated.get("adaptation_of") else "MAIN"
    kind = "adaptive" if look_class == "ADAPTIVE" else "main"
    # A lowered slice ceiling refuses a NEW look before any value is read; a saved
    # result above replays regardless of what the policy says today.
    planned_slices = len(validated.get("scientific_body", {}).get("diagnostic_slices") or [])
    slice_ceiling = limits_or_defaults(store, journal_scope)["max_diagnostic_slices"]
    if planned_slices > slice_ceiling:
        raise OrdinaryOperationError("DIAGNOSTIC_SLICES_EXCEED_POLICY")
    if owner_allowance(store, operation, kind) < 1:
        raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED")
    if fingerprint and not stamped:
        operation = _stamp_fingerprint(store, operation_sha256, fingerprint)
    _require_published_logical_content(data_root)
    _reserve(store, operation, spec_sha256=validated["spec_sha256"], look_class=kind)
    return {
        "disposition": "RESERVED",
        "values_loaded": False,
        "writes": True,
        "operation": get_operation(store, operation_sha256),
        "admission": admission,
        "spec_sha256": validated["spec_sha256"],
        "look_class": "ADAPTIVE" if kind == "adaptive" else "MAIN",
        "query_warnings": warnings,
    }


def _require_published_logical_content(data_root: Any) -> None:
    """A published corpus is checked before a look slot is reserved."""

    if data_root is None:
        return
    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        GroundedDiscoveryError,
        require_published_logical_content,
    )

    try:
        require_published_logical_content(data_root)
    except GroundedDiscoveryError as exc:
        raise OrdinaryOperationError(exc.code) from exc


def _reserve(store: Any, operation: Mapping[str, Any], *, spec_sha256: str, look_class: str = "main") -> None:
    digest = str(operation.get("operation_sha256") or "")
    stored_class = {"adaptive": "ADAPTIVE", "preview": "PREVIEW"}.get(look_class, "MAIN")
    for item in _reservations(store, digest):
        if item.get("spec_sha256") == spec_sha256:
            return
    body = {
        "artifact_kind": RESERVATION_KIND,
        "operation_sha256": digest,
        "journal_scope": operation.get("journal_scope"),
        "spec_sha256": spec_sha256,
        "look_class": stored_class,
        "schema": "smial.hfic-ordinary-look-reservation",
        "schema_version": "1.0",
    }

    def _check() -> None:
        current = get_operation(store, digest)
        if any(item.get("spec_sha256") == spec_sha256 for item in _reservations(store, digest)):
            return
        _refuse_closed(store, current)
        if owner_allowance(store, current, look_class) < 1:
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
    from solana_alpha_lab.factory.research_store import ResearchStoreError

    for attempt in range(40):
        try:
            store.append([event], transaction_id=event.transaction_id, before_commit=_check)
            return
        except OrdinaryOperationError:
            raise
        except ResearchStoreError as exc:
            if exc.code != "WRITER_BUSY":
                raise
            if any(item.get("spec_sha256") == spec_sha256 for item in _reservations(store, digest)):
                return
            current = get_operation(store, digest)
            if owner_allowance(store, current, look_class) < 1:
                raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED")
            if attempt >= 39:
                raise
            time.sleep(0.05)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == "OWNER_CAP_EXHAUSTED":
                raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED") from exc
            raise


def note_look_landed(store: Any, operation_sha256: str) -> dict[str, Any]:
    """Cap limits new looks. Landing a saved look may pause or stop the operation."""

    for _attempt in range(5):
        operation = get_operation(store, operation_sha256)
        if operation.get("status") != STATUS_OPEN:
            return operation
        if not (
            owner_allowance(store, operation, "main") < 1
            and operation.get("requested_completion") == LIMITED_RESULT
        ):
            return operation
        updated = dict(operation)
        updated["status"] = STATUS_PAUSED_CAP
        try:
            _append_transition(store, updated, based_on_record_id=str(operation.get("record_id") or ""))
        except OrdinaryOperationError as exc:
            if exc.code != "ORDINARY_OPERATION_STATE_CHANGED":
                raise
            continue
        return get_operation(store, operation_sha256)
    return get_operation(store, operation_sha256)


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _operation_opened_at(store: Any, operation_sha256: str) -> datetime | None:
    times = [
        _parse_time(item.get("_recorded_at"))
        for item in list_operations(store)
        if item.get("operation_sha256") == operation_sha256
    ]
    known = [item for item in times if item is not None]
    return min(known) if known else None


def _run_receipts(store: Any) -> list[dict[str, Any]]:
    """Persisted forge-run receipts with their record time. Reads no values."""

    from solana_alpha_lab.factory.hfic_representation_ladder import FORGE_RUN_ARTIFACT_KIND

    found: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        if getattr(record.record_kind, "value", record.record_kind) != "RESEARCH_ARTIFACT":
            continue
        try:
            wrapper = json.loads(record.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(wrapper, dict) or wrapper.get("artifact_kind") != FORGE_RUN_ARTIFACT_KIND:
            continue
        body = _load_body(record)
        if body is None:
            continue
        found.append(
            {
                "body": body,
                "record_id": str(getattr(record, "record_id", "") or ""),
                "recorded_at": _parse_time(getattr(record, "created_at", None)),
            }
        )
    return found


def _session_search_keys(store: Any) -> dict[str, set[str]]:
    from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

    keys: dict[str, set[str]] = {}
    for row in list_hfic_sessions(store):
        session_id = str(row.get("session_id") or "")
        search_key = str(row.get("search_key_sha256") or "")
        if session_id and search_key:
            keys.setdefault(session_id, set()).add(search_key)
    return keys


def _run_completion(
    operation: Mapping[str, Any],
    *,
    opened_at: datetime | None,
    receipts: Sequence[Mapping[str, Any]],
    session_keys: Mapping[str, set[str]],
) -> tuple[dict[str, Any] | None, str]:
    """The bound run's owner-final, or the exact reason it is not proven.

    Bound means: same focus, market epoch and scientific slot; recorded at or
    after this operation; OWNER_FINAL; and its BASE stage session carries this
    operation's journal. A name match is not enough. Completion is monotone:
    the earliest bound owner-final stays the proof, so a later in-progress or
    blocked receipt for the same slot cannot reopen the operation.
    """

    from solana_alpha_lab.factory.hfic_representation_ladder import (
        ACTION_NON_SCIENTIFIC_STOP,
        ACTION_OWNER_CANDIDATE,
        ACTION_SEARCH_EXHAUSTED,
        OWNER_CLASS_FINAL,
    )

    focus = str(operation.get("owner_focus") or "")
    market = str(operation.get("market_evidence_epoch_sha256") or "")
    slot = str(operation.get("scientific_slot_sha256") or "")
    journal = str(operation.get("journal_scope") or "")
    finals = {ACTION_OWNER_CANDIDATE, ACTION_SEARCH_EXHAUSTED, ACTION_NON_SCIENTIFIC_STOP}
    same_run = [
        item
        for item in receipts
        if item["body"].get("owner_focus") == focus
        and item["body"].get("market_evidence_epoch_sha256") == market
        and item["body"].get("scientific_slot_sha256") == slot
        and item.get("recorded_at") is not None
    ]
    if opened_at is None:
        return None, "OPERATION_TIME_UNKNOWN"
    def _final(item: Mapping[str, Any]) -> bool:
        return (
            item["body"].get("owner_class") == OWNER_CLASS_FINAL
            and item["body"].get("owner_final") in finals
        )

    def _bound_session(body: Mapping[str, Any]) -> str | None:
        for stage in body.get("stages") or []:
            if not isinstance(stage, Mapping) or stage.get("representation_id") != "BASE":
                continue
            session_id = str(stage.get("session_id") or "")
            if (
                session_id
                and journal in session_keys.get(session_id, set())
                and stage.get("scientific_slot_sha256") in (None, slot)
            ):
                return session_id
        return None

    after = sorted(
        (item for item in same_run if item["recorded_at"] >= opened_at),
        key=lambda item: item["recorded_at"],
    )
    finals_after = [item for item in after if _final(item)]
    bound = [(item, _bound_session(item["body"])) for item in finals_after]
    bound = [(item, session_id) for item, session_id in bound if session_id is not None]
    if not bound:
        if finals_after:
            return None, "RECEIPT_JOURNAL_UNBOUND"
        if after:
            return None, "LATEST_RECEIPT_NOT_FINAL"
        if any(_final(item) for item in same_run):
            return None, "OWNER_FINAL_BEFORE_OPERATION"
        return None, "NO_OWNER_FINAL_RECEIPT"
    proof, session_id = bound[0]
    body = proof["body"]
    return (
        {
            "kind": "RUN_OWNER_FINAL_RECEIPT",
            "receipt_ref": proof["record_id"],
            "receipt_sha256": body.get("receipt_sha256"),
            "run_id": body.get("run_id"),
            "owner_final": body.get("owner_final"),
            "session_id": session_id,
            "scientific": body.get("owner_final") != ACTION_NON_SCIENTIFIC_STOP,
        },
        "",
    )


def operation_lifecycle(
    store: Any,
    operation: Mapping[str, Any],
    *,
    receipts: Sequence[Mapping[str, Any]] | None = None,
    session_keys: Mapping[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Effective state of one operation. The only lifecycle owner; never writes."""

    persisted = str(operation.get("status") or "")
    if persisted == STATUS_STOPPED:
        return {
            "effective_state": STATUS_STOPPED,
            "persisted_status": persisted,
            "basis": {"kind": "OWNER_STOP", **dict(operation.get("lifecycle_event") or {})},
        }
    if persisted == STATUS_PAUSED_CAP:
        return {"effective_state": STATUS_PAUSED_CAP, "persisted_status": persisted, "basis": {"kind": "OWNER_CAP"}}
    if operation.get("requested_completion") != SCIENTIFIC_TERMINAL:
        return {"effective_state": STATUS_OPEN, "persisted_status": persisted, "basis": None, "gap": "LIMITED_RESULT_OPEN"}
    basis, gap = _run_completion(
        operation,
        opened_at=_operation_opened_at(store, str(operation.get("operation_sha256") or "")),
        receipts=_run_receipts(store) if receipts is None else receipts,
        session_keys=_session_search_keys(store) if session_keys is None else session_keys,
    )
    if basis is not None:
        return {"effective_state": STATE_COMPLETED, "persisted_status": persisted, "basis": basis}
    return {"effective_state": STATUS_OPEN, "persisted_status": persisted, "basis": None, "gap": gap}


def _unresolved_reservations(store: Any, operation: Mapping[str, Any]) -> list[str]:
    digest = str(operation.get("operation_sha256") or "")
    landed = {
        str(item.get("spec_sha256") or "")
        for item in _looks(store, str(operation.get("journal_scope") or ""))
        if item.get("operation_sha256") == digest and isinstance(item.get("result"), Mapping)
    }
    landed |= {
        str(item.get("spec_sha256") or "")
        for item in _feature_previews(store, str(operation.get("journal_scope") or ""))
        if item.get("operation_sha256") == digest
    }
    return sorted(
        {
            str(item.get("spec_sha256") or "")
            for item in _reservations(store, digest)
            if str(item.get("spec_sha256") or "") not in landed
        }
        - {""}
    )


UNFINISHABLE_GAPS = frozenset({"OWNER_FINAL_BEFORE_OPERATION", "RECEIPT_JOURNAL_UNBOUND", "OPERATION_TIME_UNKNOWN"})


def _blocking_next_action(
    operation: Mapping[str, Any], lifecycle: Mapping[str, Any], *, profile_active: bool
) -> str:
    """STOP when the run cannot finish here; otherwise finish-or-stop.

    Without an active profile no new look is admitted, so an open run cannot
    reach its owner-final; persist cannot bind an unbound or earlier receipt.
    """

    if not profile_active or lifecycle.get("gap") in UNFINISHABLE_GAPS:
        return NEXT_STOP
    if operation.get("requested_completion") != SCIENTIFIC_TERMINAL:
        return NEXT_LOOK_OR_STOP
    return NEXT_FINISH_OR_STOP


def effective_open_operations(store: Any) -> list[dict[str, Any]]:
    """Operations that still hold the research-universe gate, with their lifecycle."""

    latest: dict[str, dict[str, Any]] = {}
    for item in list_operations(store):
        digest = str(item.get("operation_sha256") or "")
        previous = latest.get(digest)
        if previous is None or str(item.get("_recorded_at") or "") >= str(previous.get("_recorded_at") or ""):
            latest[digest] = item
    candidates = [dict(item) for item in latest.values() if item.get("status") == STATUS_OPEN]
    if not candidates:
        return []
    receipts = _run_receipts(store)
    session_keys = _session_search_keys(store)
    found: list[dict[str, Any]] = []
    for operation in candidates:
        operation.pop("_recorded_at", None)
        lifecycle = operation_lifecycle(store, operation, receipts=receipts, session_keys=session_keys)
        if lifecycle["effective_state"] == STATUS_OPEN:
            found.append({**operation, "_lifecycle": lifecycle})
    return found


def describe_blocking_operations(
    store: Any, operations: Sequence[Mapping[str, Any]], *, profile_active: bool
) -> list[dict[str, Any]]:
    """Owner-facing rows: which operation, why it blocks, and the exact next command."""

    rows = []
    for operation in operations:
        lifecycle = operation.get("_lifecycle") or operation_lifecycle(store, operation)
        digest = str(operation.get("operation_sha256") or "")
        rows.append(
            {
                "operation_sha256": digest,
                "owner_focus": operation.get("owner_focus"),
                "requested_completion": operation.get("requested_completion"),
                "persisted_status": operation.get("status"),
                "effective_state": lifecycle.get("effective_state"),
                "completion_gap": lifecycle.get("gap"),
                "market_evidence_epoch_sha256": operation.get("market_evidence_epoch_sha256"),
                "journal_scope": operation.get("journal_scope"),
                "unresolved_reservations": len(_unresolved_reservations(store, operation)),
                "preview_allowance": owner_allowance(store, operation, "preview"),
                "next_action": _blocking_next_action(operation, lifecycle, profile_active=profile_active),
                "stop_preview": f"operation-stop-preview --operation-sha256 {digest} --owner-request-text <owner text>",
            }
        )
    return rows


def _stop_proposal_body(operation: Mapping[str, Any], *, owner_request_text: str, unresolved: Sequence[str]) -> dict[str, Any]:
    return {
        "schema": STOP_PROPOSAL_SCHEMA,
        "schema_version": "1.0",
        "operation_sha256": operation.get("operation_sha256"),
        "base_record_id": operation.get("record_id"),
        "base_status": operation.get("status"),
        "owner_request_text": owner_request_text,
        "reason_code": STOP_REASON_CODE,
        "unresolved_reservation_spec_sha256": list(unresolved),
    }


def _stop_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrdinaryOperationError("OPERATION_STOP_REQUEST_REQUIRED")
    return value.strip()


def _operation_id(value: object) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise OrdinaryOperationError("ORDINARY_OPERATION_ID_INVALID")
    return text


def preview_operation_stop(store: Any, *, operation_sha256: object, owner_request_text: object) -> dict[str, Any]:
    """Read-only proposal to cancel one exact operation's remaining execution."""

    digest = _operation_id(operation_sha256)
    text = _stop_text(owner_request_text)
    operation = get_operation(store, digest)
    lifecycle = operation_lifecycle(store, operation)
    if lifecycle["effective_state"] == STATE_COMPLETED:
        raise OrdinaryOperationError("OPERATION_ALREADY_COMPLETED")
    landed = [
        item.get("record_id")
        for item in _looks(store, str(operation.get("journal_scope") or ""))
        if item.get("operation_sha256") == digest and isinstance(item.get("result"), Mapping)
    ]
    base = {
        "operation_sha256": digest,
        "owner_focus": operation.get("owner_focus"),
        "requested_completion": operation.get("requested_completion"),
        "persisted_status": operation.get("status"),
        "effective_state": lifecycle["effective_state"],
        "saved_result_refs": landed,
        "authority": {"experiment_execution": 0, "git_mutation": 0, "provider_api_rpc_wss_calls": 0},
        "writes": {"research_store": 0},
    }
    if lifecycle["effective_state"] == STATUS_STOPPED:
        return {
            "action": "OPERATION_STOP_PREVIEW",
            "status": "NO_CHANGE",
            **base,
            "stop": lifecycle["basis"],
            "next_action": "READ_SAVED_RESULT",
        }
    unresolved = _unresolved_reservations(store, operation)
    proposal = _stop_proposal_body(operation, owner_request_text=text, unresolved=unresolved)
    proposal["proposal_sha256"] = _sha(proposal)
    return {
        "action": "OPERATION_STOP_PREVIEW",
        "status": "PROPOSED",
        **base,
        "unresolved_reservation_spec_sha256": unresolved,
        "effect": {
            "scientific_verdict": None,
            "quota_returned": False,
            "saved_results_kept": True,
            "new_looks_after_stop": "REFUSED",
            "saved_result_replay_after_stop": "ALLOWED",
        },
        "claim_boundary": "A stop ends execution. It is not a negative result and does not free spent looks.",
        "proposal": proposal,
        "proposal_sha256": proposal["proposal_sha256"],
        "next_action": "AUTHORIZED_STOP_APPLY",
    }


def apply_operation_stop(store: Any, *, proposal: Mapping[str, Any], confirm_append_only: bool) -> dict[str, Any]:
    """Append one owner stop. Re-checks the exact target under the writer lease."""

    if not confirm_append_only:
        raise OrdinaryOperationError("OPERATION_STOP_CONFIRM_REQUIRED")
    body = dict(proposal)
    observed = body.pop("proposal_sha256", None)
    if (
        body.get("schema") != STOP_PROPOSAL_SCHEMA
        or body.get("reason_code") != STOP_REASON_CODE
        or not isinstance(observed, str)
        or _sha(body) != observed
    ):
        raise OrdinaryOperationError("OPERATION_STOP_PROPOSAL_INVALID")
    digest = _operation_id(body.get("operation_sha256"))
    text = _stop_text(body.get("owner_request_text"))
    operation = get_operation(store, digest)
    lifecycle = operation_lifecycle(store, operation)
    if lifecycle["effective_state"] == STATUS_STOPPED:
        event = dict(operation.get("lifecycle_event") or {})
        return {
            "action": "OPERATION_STOP_APPLY",
            "status": "NO_CHANGE",
            "same_proposal": event.get("proposal_sha256") == observed,
            "operation_sha256": digest,
            "stop": event,
            "next_action": "READ_SAVED_RESULT",
            "writes": {"research_store": 0},
        }
    if lifecycle["effective_state"] == STATE_COMPLETED:
        raise OrdinaryOperationError("OPERATION_ALREADY_COMPLETED")
    base_record = str(body.get("base_record_id") or "")
    unresolved = _unresolved_reservations(store, operation)
    if (
        str(operation.get("record_id") or "") != base_record
        or list(body.get("unresolved_reservation_spec_sha256") or []) != unresolved
    ):
        raise OrdinaryOperationError("OPERATION_STOP_PREVIEW_STALE")
    updated = {key: value for key, value in operation.items() if key != "record_id"}
    updated["status"] = STATUS_STOPPED
    updated["lifecycle_event"] = {
        "kind": "OWNER_STOP",
        "reason_code": STOP_REASON_CODE,
        "owner_request_text": text,
        "proposal_sha256": observed,
        "previous_record_id": base_record,
        "previous_status": operation.get("status"),
        "unresolved_reservation_spec_sha256": unresolved,
        "scientific_verdict": None,
        "quota_returned": False,
    }

    def _check() -> None:
        current = get_operation(store, digest)
        if str(current.get("record_id") or "") != base_record:
            raise OrdinaryOperationError("OPERATION_STOP_PREVIEW_STALE")
        if _unresolved_reservations(store, current) != unresolved:
            raise OrdinaryOperationError("OPERATION_STOP_PREVIEW_STALE")
        if operation_lifecycle(store, current)["effective_state"] == STATE_COMPLETED:
            raise OrdinaryOperationError("OPERATION_ALREADY_COMPLETED")

    _append(store, kind=OPERATION_KIND, body=updated, record_prefix="HFIC-ART-OP", before_commit=_check)
    stored = get_operation(store, digest)
    return {
        "action": "OPERATION_STOP_APPLY",
        "status": "APPENDED",
        "operation_sha256": digest,
        "persisted_status": stored.get("status"),
        "record_id": stored.get("record_id"),
        "stop": stored.get("lifecycle_event"),
        "next_action": "READ_UNIVERSE_POLICY_STATUS",
        "writes": {"research_store": 1},
    }


def project_ordinary_operation(
    store: Any,
    *,
    owner_focus: str,
    market_evidence_epoch_sha256: str | None = None,
) -> dict[str, Any] | None:
    """Derived readout. Not a second persisted DONE."""

    rows = [item for item in list_operations(store) if item.get("owner_focus") == owner_focus]
    if isinstance(market_evidence_epoch_sha256, str) and len(market_evidence_epoch_sha256) == 64:
        rows = [item for item in rows if item.get("market_evidence_epoch_sha256") == market_evidence_epoch_sha256]
    if not rows:
        return None
    # The newest operation is the one opened last; a later stop row of an older
    # operation must not hide it.
    opened: dict[str, str] = {}
    for item in rows:
        digest = str(item.get("operation_sha256") or "")
        stamp = str(item.get("_recorded_at") or "")
        if digest not in opened or stamp < opened[digest]:
            opened[digest] = stamp
    newest = max(opened, key=lambda digest: opened[digest])
    current = _latest_recorded([item for item in rows if item.get("operation_sha256") == newest])
    current.pop("_recorded_at", None)
    journal = str(current.get("journal_scope") or "")
    looks = _looks(store, journal)
    from solana_alpha_lab.factory.hfic_temporal_discovery import assess_tier_progress, validate_temporal_query

    progress = assess_tier_progress(
        looks,
        freeze_worthy=False,
        compound_applicable=True,
        main_total=limits_or_defaults(store, journal)["main_total"],
    )
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
    latest = _operation_result(looks, str(current.get("operation_sha256") or ""))
    readout = result_readout(latest) if latest is not None else None
    lifecycle = operation_lifecycle(store, current)
    effective = lifecycle["effective_state"]
    if readout is not None and readout.get("result_coherence") != "COHERENT":
        # A technical mismatch is repaired by a calculation revision, not by more looks.
        next_action = "CORRECT_CALCULATION_REVISION"
        next_needs_values = True
        next_needs_authority = False
    elif effective == STATUS_PAUSED_CAP:
        next_action = "AUTHORIZE_ADDITIONAL_LOOKS"
        next_needs_values = True
        next_needs_authority = True
    elif effective in {STATUS_STOPPED, STATE_COMPLETED}:
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
        "effective_state": effective,
        "lifecycle_basis": lifecycle.get("basis"),
        "completion_gap": lifecycle.get("gap"),
        "requested_completion": current.get("requested_completion"),
        "market_evidence_epoch_sha256": current.get("market_evidence_epoch_sha256"),
        "question_text": current.get("question_text"),
        "journal_scope": journal,
        "decision_point": decision,
        "decision_age_seconds": age,
        "hold_seconds": hold,
        "exit_point": exit_point,
        "completed": {
            "look": latest is not None,
            "operation": effective in {STATUS_PAUSED_CAP, STATUS_STOPPED, STATE_COMPLETED},
            "scientific_search": effective == STATE_COMPLETED
            and bool((lifecycle.get("basis") or {}).get("scientific")),
        },
        "result_refs": [latest.get("record_id")] if latest else [],
        "result_sha256": latest.get("result_sha256") if latest else None,
        "result": readout,
        "claim_boundary": "PRICE_RELATIVE_PROXY is not net return; cohorts are not independent replications",
        "protocol_main_remaining": _protocol_remaining(store, looks, "main", journal=journal),
        "protocol_main_used": sum(1 for item in looks if item.get("look_class") == "MAIN" and item.get("new_look") is True),
        "owner_main_remaining": owner_allowance(store, current, "main"),
        "reserved_main": len(_reservations(store, str(current.get("operation_sha256") or ""))),
        "journal_result_refs": [item.get("record_id") for item in looks],
        "compound_status": progress.get("compound_status"),
        "next_action": next_action,
        "next_needs_new_values": next_needs_values,
        "next_needs_new_authority": next_needs_authority,
        "search_open": effective not in {STATUS_STOPPED, STATE_COMPLETED},
        "candidate_ready": any(
            item.get("owner_focus") == owner_focus for item in _iter_kind(store, "FORGE_DRAFT")
        ),
    }


def operation_readout_line(projection: Mapping[str, Any], owner_focus: object) -> str:
    """One owner line: which operation, its effective state and the exact next step."""

    digest = str(projection.get("operation_sha256") or "")
    line = f"operation: {digest} state={projection.get('effective_state')} next={projection.get('next_action')}"
    if projection.get("next_action") == NEXT_PERSIST_OWNER_FINAL:
        line += (
            " — the run is owner-final; record it with forge-run --persist --owner-focus "
            f"{owner_focus or ''}; that releases the operation"
        )
    elif projection.get("next_action") == NEXT_STOP:
        line += (
            " — this run cannot finish here; stop it with operation-stop-preview "
            f"--operation-sha256 {digest} --owner-request-text <owner text>, then operation-stop"
        )
    elif projection.get("effective_state") == STATUS_STOPPED:
        line += (
            " — stopped by the owner; not a scientific result; saved looks stay spent; "
            "more research needs a new owner request"
        )
    return line


def merge_ordinary_readout(payload: dict[str, Any], projection: Mapping[str, Any] | None) -> dict[str, Any]:
    """One operator next. A blocker or a scientific terminal is not a second menu."""

    if projection is None:
        return payload
    proj = dict(projection)
    blocked = payload.get("owner_class") in {"INPUT_NOT_READY", "OBSERVABILITY_BLOCKED"}
    final = str(payload.get("owner_final") or "")
    terminals = {
        "SEARCH_EXHAUSTED_CURRENT_EVIDENCE",
        "NO_WORTHY_HYPOTHESIS",
        "OWNER_CANDIDATE",
        "RETURN_EXISTING_RUN",
        "NON_SCIENTIFIC_STOP",
    }
    effective = proj.get("effective_state")
    if effective in {STATUS_STOPPED, STATE_COMPLETED}:
        # The operation itself is over; a run-level blocker does not reopen it.
        proj["next_action"] = "READ_SAVED_RESULT"
        proj["next_needs_new_authority"] = False
        proj["search_open"] = False
    elif blocked:
        codes = {str(item) for item in payload.get("blocking_reason_codes") or []}
        if effective == STATUS_OPEN and "UNIVERSE_POLICY_REQUIRED" in codes:
            # Without a profile this run cannot finish, and the profile cannot be
            # applied while it is open: the executable step is the owner stop.
            proj["next_action"] = NEXT_STOP
        else:
            proj["next_action"] = str(payload.get("next_action") or "INPUT_NOT_READY")
        proj["next_needs_new_authority"] = False
        proj["search_open"] = False
    elif final in terminals:
        proj["next_action"] = "READ_SAVED_RESULT"
        if effective == STATUS_OPEN:
            # The gate still counts this operation; the readback must say how to release it.
            persistable = (
                proj.get("requested_completion") == SCIENTIFIC_TERMINAL
                and payload.get("owner_class") == "OWNER_FINAL"
                and payload.get("market_evidence_epoch_sha256") == proj.get("market_evidence_epoch_sha256")
                and proj.get("completion_gap") in {"NO_OWNER_FINAL_RECEIPT", "LATEST_RECEIPT_NOT_FINAL"}
            )
            proj["next_action"] = NEXT_PERSIST_OWNER_FINAL if persistable else NEXT_STOP
        proj["next_needs_new_authority"] = False
        proj["search_open"] = False
    elif str(payload.get("next_action") or "").startswith("RESUME_"):
        proj["next_action"] = str(payload.get("next_action"))
        proj["next_needs_new_authority"] = False
        proj["search_open"] = False
    elif proj.get("next_action") == "CORRECT_CALCULATION_REVISION":
        payload["next_action"] = "CORRECT_CALCULATION_REVISION"
        payload["owner_final"] = "SAVED_RESULT_NEEDS_CALCULATION_REVISION"
    elif proj.get("candidate_ready") and proj.get("owner_main_remaining") == 0:
        proj["next_action"] = "FORMAT_SAVED_CANDIDATE"
        proj["next_needs_new_authority"] = False
        payload["next_action"] = "FORMAT_SAVED_CANDIDATE"
        payload["owner_final"] = "CANDIDATE_READY_CAP_EXHAUSTED"
    elif proj.get("status") == "PAUSED_CAP" and proj.get("owner_main_remaining") == 0:
        payload["next_action"] = "AUTHORIZE_ADDITIONAL_LOOKS"
        payload["owner_final"] = "OPERATION_PAUSED_SEARCH_OPEN"
    payload["ordinary_operation"] = proj
    payload["owner_readout"] = (
        str(payload.get("owner_readout") or "") + "\n" + operation_readout_line(proj, payload.get("owner_focus"))
    )
    readout = (proj.get("result") or {}).get("descriptive_readout")
    if isinstance(readout, Mapping):
        if readout.get("status") == "LEGACY_READOUT_UNAVAILABLE":
            line = str(readout.get("message") or "")
        else:
            parts = []
            for label in ("matched", "baseline"):
                row = readout.get(label) or {}
                tail = row.get("downside") or {}
                parts.append(
                    f"{label}: observed/eligible/missing={tail.get('observed_n')}/{row.get('eligible_n')}/{tail.get('missing_n')}, "
                    f"mean={row.get('mean_target')}, median={row.get('median_target')}, "
                    f"<=-20%={tail.get('le_minus_20_n')}/{tail.get('le_minus_20_rate')}, "
                    f"<=-50%={tail.get('le_minus_50_n')}/{tail.get('le_minus_50_rate')}, "
                    f"ES10={tail.get('es10_return')}, worst_negative_share={tail.get('worst_negative_share')}"
                )
            line = "\n".join(parts)
        if line:
            payload["owner_readout"] = str(payload.get("owner_readout") or "") + "\n" + line
    return payload
