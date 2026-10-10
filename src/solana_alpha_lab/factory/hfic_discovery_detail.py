"""Read a native discovery result's original request and assessment lineage.

This is a projection of committed records, not a writer or another ledger.
The saved-recipe and scientific-disposition owners retain their semantics.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .hfic_grounded_discovery import result_sha256
from .hfic_ordinary_operation import OPERATION_KIND, RESERVATION_KIND, _sha, result_readout
from .hfic_scientific_disposition import _View, _applicability, resolve_subject, subject_key
from .hfic_temporal_discovery import _public_query_from_recipe, canonical_temporal_spec, current_look_evidence, validate_temporal_query


class DiscoveryDetailError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _Snapshot:
    def __init__(self, store: Any) -> None:
        self.records = tuple(store.iter_committed_records())

    def iter_committed_records(self):
        return iter(self.records)


def _original_request(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    row = min(rows, key=lambda item: item["_recorded_at"])
    keys = ("artifact_kind", "owner_request_text", "owner_focus", "journal_scope",
        "market_evidence_epoch_sha256", "scientific_slot_sha256", "question_text",
        "owner_cap", "requested_completion", "parent_operation_sha256")
    identity = {key: row.get(key) for key in keys}
    identity.update({key: row[key] for key in ("representation", "cycle_index", "accounting_root", "lineage_kind") if key in row})
    if row.get("schema_version") != "1.0" or _sha(identity) != row.get("operation_sha256"):
        raise DiscoveryDetailError("DISCOVERY_DETAIL_OPERATION_IDENTITY_MISMATCH")
    return {**identity, "operation_sha256": row["operation_sha256"], "record_id": row["record_id"],
        "spec_canonical": row.get("spec_canonical"), "spec_sha256": row.get("spec_sha256")}


def discovery_detail(
    store: Any, *, result_ref: str | None = None, operation_sha256: str | None = None,
    current_market: str | None = None, offset: int = 0, limit: int = 20,
) -> dict[str, Any]:
    """One archive enumeration; no outcome rows, admission, accounting or writes."""
    if not result_ref and not operation_sha256:
        raise DiscoveryDetailError("DISCOVERY_DETAIL_LOCATOR_REQUIRED")
    if operation_sha256 and not re.fullmatch(r"[0-9a-f]{64}", operation_sha256):
        raise DiscoveryDetailError("DISCOVERY_DETAIL_OPERATION_INVALID")
    if result_ref and not re.fullmatch(r"HFIC-ART-DISCOVERY-[A-Z0-9-]+", result_ref):
        raise DiscoveryDetailError("DISCOVERY_DETAIL_RESULT_REF_INVALID")
    if offset < 0 or not 1 <= limit <= 100:
        raise DiscoveryDetailError("DISCOVERY_DETAIL_PAGE_INVALID")
    snapshot = _Snapshot(store)
    bodies: dict[str, dict[str, Any]] = {}
    invalid: set[str] = set()
    unreadable_discovery = False
    operations: dict[str, list[dict[str, Any]]] = {}
    reservations = []
    looks = []
    candidate_sources = []
    for record in snapshot.records:
        ref = str(record.record_id)
        if getattr(record.record_kind, "value", record.record_kind) != "RESEARCH_ARTIFACT":
            continue
        is_discovery = ref.startswith("HFIC-ART-DISCOVERY-")
        try:
            wrapper = json.loads(record.payload_json)
            if not isinstance(wrapper, dict):
                raise TypeError("ARTIFACT_WRAPPER_NOT_OBJECT")
            kind = wrapper.get("artifact_kind")
            is_discovery = is_discovery or kind == "DISCOVERY_QUERY_LOOK"
            canonical = wrapper["payload_canonical"]
            body = json.loads(canonical)
            if (not isinstance(body, dict)
                or hashlib.sha256(canonical.encode("utf-8")).hexdigest() != wrapper["payload_sha256"]
                or is_discovery and kind != "DISCOVERY_QUERY_LOOK"):
                invalid.add(ref)
                unreadable_discovery = unreadable_discovery or is_discovery
                continue
        except (KeyError, TypeError, ValueError):
            invalid.add(ref)
            unreadable_discovery = unreadable_discovery or is_discovery
            continue
        body = {**body, "record_id": ref}
        bodies[ref] = body
        if kind == OPERATION_KIND:
            body["_recorded_at"] = record.created_at.isoformat()
            operations.setdefault(str(body.get("operation_sha256")), []).append(body)
        elif kind == RESERVATION_KIND:
            reservations.append(body)
        elif kind == "DISCOVERY_QUERY_LOOK":
            looks.append(body)
        elif kind in {"FORGE_DRAFT", "CRITIC_INPUT_PACKET"}:
            candidate_sources.append({"body": body, "wrapper": wrapper, "ref": ref})
    # An unreadable look has no verified operation/journal affiliation. It
    # cannot safely be omitted from a page, current-look or pending calculation.
    if unreadable_discovery or result_ref in invalid:
        raise DiscoveryDetailError("DISCOVERY_DETAIL_SOURCE_UNREADABLE")
    for look in looks:
        result = look.get("result")
        if not isinstance(result, Mapping) or result_sha256(result) != look.get("result_sha256"):
            raise DiscoveryDetailError("DISCOVERY_DETAIL_RESULT_HASH_MISMATCH")
    selected = [look for look in looks if (not result_ref or look["record_id"] == result_ref)
        and (not operation_sha256 or look.get("operation_sha256") == operation_sha256)]
    if result_ref and not selected:
        code = "DISCOVERY_DETAIL_LOCATOR_MISMATCH" if result_ref in bodies else "DISCOVERY_DETAIL_RESULT_NOT_FOUND"
        raise DiscoveryDetailError(code)
    if operation_sha256 and operation_sha256 not in operations and not selected:
        raise DiscoveryDetailError("DISCOVERY_DETAIL_OPERATION_NOT_FOUND")
    selected.sort(key=lambda row: row["record_id"])
    view = _View(snapshot)
    grouped = view.by_subject()
    entries = []
    for look in selected[offset:offset + limit]:
        digest = str(look.get("operation_sha256") or "")
        rows = operations.get(digest, [])
        # Immutable request fields are identical across lifecycle snapshots.
        operation = _original_request(rows)
        if digest and operation is None:
            raise DiscoveryDetailError("DISCOVERY_DETAIL_OPERATION_SOURCE_MISSING")
        matches = [row for row in reservations if row.get("operation_sha256") == digest
            and row.get("spec_sha256") == look.get("spec_sha256")]
        if operation and operation.get("journal_scope") != look.get("journal_scope"):
            raise DiscoveryDetailError("DISCOVERY_DETAIL_OPERATION_BINDING_MISMATCH")
        if operation and len(matches) != 1:
            raise DiscoveryDetailError("DISCOVERY_DETAIL_RESERVATION_BINDING_MISMATCH")
        if matches and matches[0].get("journal_scope") != look.get("journal_scope"):
            raise DiscoveryDetailError("DISCOVERY_DETAIL_RESERVATION_BINDING_MISMATCH")
        try:
            saved = operation.get("spec_canonical") if operation else None
            public_query = json.loads(saved) if saved else _public_query_from_recipe({"spec": look["spec"]})
            if validate_temporal_query(public_query)["spec_sha256"] != look.get("spec_sha256"):
                raise DiscoveryDetailError("DISCOVERY_DETAIL_QUERY_BINDING_MISMATCH")
            if canonical_temporal_spec(public_query) != look.get("spec"):
                raise DiscoveryDetailError("DISCOVERY_DETAIL_QUERY_BINDING_MISMATCH")
        except DiscoveryDetailError:
            raise
        except Exception as exc:
            raise DiscoveryDetailError("DISCOVERY_DETAIL_QUERY_UNAVAILABLE") from exc
        parent_ref = operation.get("parent_operation_sha256") if operation else None
        parent_rows = operations.get(str(parent_ref), []) if parent_ref else []
        parent = _original_request(parent_rows)
        subject = {"subject_kind": "QUESTION", "question_spec_sha256": look.get("spec_sha256"),
            "owner_focus": operation.get("owner_focus") if operation else None,
            "market_evidence_epoch_sha256": operation.get("market_evidence_epoch_sha256") if operation else None,
            "journal_scope": look.get("journal_scope")}
        assessments = grouped.get(subject_key(subject), []) if operation else []
        resolved = resolve_subject(view, assessments, current_market=current_market,
            current_journal=str(look.get("journal_scope"))) if assessments else {"status": "NOT_RECORDED"}
        history = []
        for assessment in assessments:
            item = dict(assessment)
            if item["readable"] and item["body"].get("entry") == "ASSESSMENT":
                status, reasons = _applicability(view, item["body"], current_market=current_market,
                    current_journal=str(look.get("journal_scope")))
                item.update({"applicability": status, "applicability_reasons": reasons})
            elif item["readable"]:
                item.update({"applicability": "NOT_APPLICABLE_WITHDRAWAL", "applicability_reasons": []})
            history.append(item)
        current = current_look_evidence(look, [row for row in looks if row.get("journal_scope") == look.get("journal_scope")])
        source_links = []
        for source in candidate_sources:
            body, wrapper = source["body"], source["wrapper"]
            evidence = body.get("grounded_evidence")
            if not isinstance(evidence, Mapping):
                continue
            refs = evidence.get("result_refs")
            if (not isinstance(refs, list) or look["record_id"] not in refs
                or evidence.get("result_sha256") != look["result_sha256"]):
                continue
            kind = wrapper["artifact_kind"]
            # A runner-up's look_context_result_refs are context, not support.
            if kind == "CRITIC_INPUT_PACKET" and evidence.get("look_confirms_selected") is not True:
                continue
            session_id = wrapper.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                continue
            if body.get("session_id", session_id) != session_id:
                raise DiscoveryDetailError("DISCOVERY_DETAIL_SESSION_SOURCE_BINDING_MISMATCH")
            selected_card = body.get("selected_candidate")
            source_links.append({"artifact_kind": kind, "artifact_ref": source["ref"],
                "artifact_sha256": wrapper["payload_sha256"], "session_id": session_id,
                "selected_candidate_id": selected_card.get("candidate_id") if isinstance(selected_card, Mapping) else None,
                "look_confirms_selected": evidence.get("look_confirms_selected") if kind == "CRITIC_INPUT_PACKET" else None,
                "next_read": {"command": "show-session", "session_id": session_id}})
        source_links.sort(key=lambda item: item["artifact_ref"])
        entries.append({"result_ref": look["record_id"], "result_sha256": look["result_sha256"],
            "spec_sha256": look.get("spec_sha256"), "look_class": look.get("look_class"),
            "operation_sha256": digest or None, "operation_ref": operation.get("record_id") if operation else None,
            "operation_request": operation, "authored_basis_status": "RECORDED_REQUEST" if operation else "NOT_RECORDED",
            "reservation_ref": matches[0]["record_id"] if len(matches) == 1 else None,
            "parent_operation": parent, "parent_status": "RECORDED" if parent else "NOT_RECORDED" if parent_ref else "NOT_APPLICABLE",
            "canonical_query": public_query,
            "query_provenance": "EXACT_SAVED_PUBLIC_QUERY" if saved else "SOURCE_DERIVED_CANONICAL_QUERY",
            "original_query_bytes": "NOT_RECORDED", "result_readout": result_readout(look),
            "current_result_ref": current.get("record_id"), "is_current_result": current.get("record_id") == look["record_id"],
            "scientific_disposition": resolved, "assessment_history": history,
            "source_links": source_links,
            "source_link_status": "RECORDED" if source_links else "NOT_RECORDED"})
    landed = {(row.get("operation_sha256"), row.get("spec_sha256")) for row in looks if isinstance(row.get("result"), Mapping)}
    pending = [row for row in reservations if operation_sha256 and row.get("operation_sha256") == operation_sha256
        and (row.get("operation_sha256"), row.get("spec_sha256")) not in landed]
    return {"schema": "smial.hfic-discovery-detail", "schema_version": "1.0", "advisory_only": True,
        "authority_granted": False, "values_loaded": False, "writes": {"research_store": 0},
        "market_verified": current_market is not None, "total_results": len(selected), "offset": offset,
        "limit": limit, "next_offset": offset + len(entries) if offset + len(entries) < len(selected) else None,
        "entries": entries, "pending_reservations": pending,
        "operation_request": _original_request(operations.get(operation_sha256, [])) if operation_sha256 else None}
