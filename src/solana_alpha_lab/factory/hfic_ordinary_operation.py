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
    MAX_ADAPTIVE_REFINEMENTS,
    MAX_MAIN_QUERY_SPECS,
    POINT_OFFSET,
    GroundedDiscoveryError,
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


def record_operation(store: Any, request: Mapping[str, Any]) -> dict[str, Any]:
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
        "spec_sha256": None if not exact or validated is None else validated["spec_sha256"],
        "spec_canonical": None if not exact or not isinstance(spec, Mapping) else _canonical(dict(spec)),
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


def _operation_result(
    looks: Sequence[Mapping[str, Any]],
    operation_sha256: str,
    spec_sha256: str | None = None,
) -> Mapping[str, Any] | None:
    """The result this operation reads: a current-version look, else the newest saved one.

    The earliest stored row must not shadow a later calculation revision.
    """

    from solana_alpha_lab.factory.hfic_temporal_discovery import TEMPORAL_CALCULATION_VERSION

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
    return owned[-1] if owned else None


def result_readout(look: Mapping[str, Any]) -> dict[str, Any]:
    """Version, lineage and coherence of one saved result. Reads no values."""

    from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_result_coherence

    result = look.get("result") if isinstance(look.get("result"), Mapping) else {}
    coherence = temporal_result_coherence(result)
    body: dict[str, Any] = {
        "result_ref": look.get("record_id"),
        "result_sha256": look.get("result_sha256"),
        "calculation_version": look.get("calculation_version"),
        "look_class": look.get("look_class"),
        "new_look": look.get("new_look"),
        "result_coherence": coherence["status"],
        "science_ready": coherence["status"] == "COHERENT" and result.get("technical_failure") is not True,
    }
    if isinstance(look.get("revision_of"), Mapping):
        body["revision_of"] = dict(look["revision_of"])
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
    return [
        item
        for item in _iter_kind(store, "DISCOVERY_FEATURE_PREVIEW")
        if item.get("journal_scope") == journal
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

    from solana_alpha_lab.factory.hfic_evidence_identity import compute_split_identity
    from solana_alpha_lab.factory.hfic_memory_policy import effective_policy
    from solana_alpha_lab.factory.hfic_session import PROMPT_VERSION, search_key_sha256

    split = compute_split_identity(Path(repo_root), Path(data_root), store=store)
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
    if journal_scope != expected:
        raise OrdinaryOperationError("ORDINARY_OPERATION_JOURNAL_NOT_CANONICAL")


def _protocol_remaining(
    store: Any,
    looks: Sequence[Mapping[str, Any]],
    kind: str,
    *,
    journal: str,
) -> int:
    if kind == "preview":
        used = {
            str(item.get("preview_sha256") or "")
            for item in _feature_previews(store, journal)
            if item.get("preview_sha256")
        }
        landed_specs = {
            str(item.get("spec_sha256") or "")
            for item in _feature_previews(store, journal)
            if item.get("spec_sha256")
        }
        pending = {
            str(item.get("spec_sha256") or "")
            for item in _iter_kind(store, RESERVATION_KIND)
            if item.get("journal_scope") == journal
            and item.get("look_class") == "PREVIEW"
            and str(item.get("spec_sha256") or "") not in landed_specs
        }
        return max(0, MAX_PREVIEW_SPECS - len(used) - len(pending))
    completed = {
        str(item.get("spec_sha256") or "")
        for item in looks
        if item.get("look_class") == ("ADAPTIVE" if kind == "adaptive" else "MAIN")
        and item.get("new_look") is True
        and isinstance(item.get("result"), Mapping)
    }
    in_flight = {
        str(item.get("spec_sha256") or "")
        for item in _iter_kind(store, RESERVATION_KIND)
        if item.get("journal_scope") == journal
        and item.get("look_class") == ("ADAPTIVE" if kind == "adaptive" else "MAIN")
        and str(item.get("spec_sha256") or "") not in completed
    }
    limit = MAX_ADAPTIVE_REFINEMENTS if kind == "adaptive" else MAX_MAIN_QUERY_SPECS
    return max(0, limit - len(completed) - len(in_flight))


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
            return {
                "disposition": "REPLAY",
                "values_loaded": False,
                "writes": False,
                "operation": operation,
                "look_class": "PREVIEW",
                "preview_sha256": owned[-1].get("preview_sha256"),
                "replayed_without_loader": True,
            }
        fingerprint = binding_fingerprint(binding_cohorts)
        stamped = operation.get("corpus_fingerprint")
        if fingerprint and stamped and fingerprint != stamped:
            raise OrdinaryOperationError("ORDINARY_OPERATION_BINDING_MISMATCH")
        admission = _admit(store, operation)
        if admission.get("action") == "STOP":
            raise OrdinaryOperationError(
                str(admission.get("reason_code") or "SCIENTIFIC_ADMISSION_STOP")
            )
        from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

        if _closed_slot(admission, list_hfic_sessions(store)):
            raise OrdinaryOperationError("ORDINARY_OPERATION_SLOT_CLOSED")
        if owner_allowance(store, operation, "preview") < 1:
            raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED")
        _reserve(store, operation, spec_sha256=spec_sha, look_class="preview")
        if fingerprint and not stamped:
            updated = dict(operation)
            updated["corpus_fingerprint"] = fingerprint
            _append(store, kind=OPERATION_KIND, body=updated, record_prefix="HFIC-ART-OP")
            operation = get_operation(store, operation_sha256)
        return {
            "disposition": "EXECUTE",
            "values_loaded": False,
            "writes": False,
            "operation": operation,
            "admission": admission,
            "look_class": "PREVIEW",
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
    _search_terminal_conflict(operation, looks, spec)
    from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

    admission = _admit(store, operation)
    if admission.get("action") == "STOP":
        raise OrdinaryOperationError(str(admission.get("reason_code") or "SCIENTIFIC_ADMISSION_STOP"))
    from solana_alpha_lab.factory.hfic_temporal_discovery import (
        TEMPORAL_CALCULATION_VERSION,
        verify_calculation_revision_source,
    )

    stored = _operation_result(looks, operation_sha256, validated["spec_sha256"])
    if (
        stored is not None
        and correction is not None
        and stored.get("calculation_version") != TEMPORAL_CALCULATION_VERSION
    ):
        stored = None
    if stored is not None:
        evidence: dict[str, Any] = {
            "replayed_without_evaluator": True,
            "calculation_version": stored.get("calculation_version"),
            "result_sha256": stored.get("result_sha256"),
            "result_refs": [stored.get("record_id")],
            "result": stored.get("result"),
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
    try:
        classified = classify_temporal_look(looks, spec)
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
    if owner_allowance(store, operation, kind) < 1:
        raise OrdinaryOperationError("OWNER_CAP_EXHAUSTED")
    if fingerprint and not stamped:
        updated = dict(operation)
        updated["corpus_fingerprint"] = fingerprint
        _append(store, kind=OPERATION_KIND, body=updated, record_prefix="HFIC-ART-OP")
        operation = get_operation(store, operation_sha256)
    _reserve(store, operation, spec_sha256=validated["spec_sha256"], look_class=kind)
    return {
        "disposition": "RESERVED",
        "values_loaded": False,
        "writes": True,
        "operation": get_operation(store, operation_sha256),
        "admission": admission,
        "spec_sha256": validated["spec_sha256"],
        "look_class": "ADAPTIVE" if kind == "adaptive" else "MAIN",
    }


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

    operation = get_operation(store, operation_sha256)
    status = operation.get("status")
    if owner_allowance(store, operation, "main") < 1 and operation.get("requested_completion") == LIMITED_RESULT:
        status = "PAUSED_CAP"
    if status == operation.get("status"):
        return operation
    updated = dict(operation)
    updated["status"] = status
    _append(store, kind=OPERATION_KIND, body=updated, record_prefix="HFIC-ART-OP")
    return updated


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
    current = _latest_recorded(rows)
    current.pop("_recorded_at", None)
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
    latest = _operation_result(looks, str(current.get("operation_sha256") or ""))
    readout = result_readout(latest) if latest is not None else None
    if readout is not None and readout.get("result_coherence") != "COHERENT":
        # A technical mismatch is repaired by a calculation revision, not by more looks.
        next_action = "CORRECT_CALCULATION_REVISION"
        next_needs_values = True
        next_needs_authority = False
    elif current.get("status") == "PAUSED_CAP":
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
            "scientific_search": False,
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
        "search_open": current.get("status") != "STOPPED",
        "candidate_ready": any(
            item.get("owner_focus") == owner_focus for item in _iter_kind(store, "FORGE_DRAFT")
        ),
    }


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
    if blocked:
        proj["next_action"] = str(payload.get("next_action") or "INPUT_NOT_READY")
        proj["next_needs_new_authority"] = False
        proj["search_open"] = False
    elif final in terminals:
        proj["next_action"] = "READ_SAVED_RESULT"
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
    return payload
