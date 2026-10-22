"""Source-bound research fragments over native append-only research evidence.

This owner curates roles and bounded watch plans. It never owns a second
formula, numerical evaluator, accounting ledger, scheduler or strategy state.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStoreError
from solana_alpha_lab.factory.run_passport import canonical_sha256

CARD = "RESEARCH_FRAGMENT_V1"
PLAN = "RESEARCH_FRAGMENT_PLAN_V1"
CHECK = "RESEARCH_FRAGMENT_CHECK_V1"
KINDS = frozenset({CARD, PLAN, CHECK})
ROLES = frozenset({"CONTEXT_FILTER", "ENTRY", "EXIT", "RISK_CONSTRAINT"})


class FragmentError(ValueError):
    def __init__(self, code: str, detail: Mapping[str, Any] | None = None):
        self.code = code
        self.detail = dict(detail or {})
        super().__init__(code)


def source_detail(source: Any) -> dict[str, Any]:
    """Carry only the current-protection owner's public recovery metadata."""
    detail = source if isinstance(source, Mapping) else getattr(source, "detail", {})
    if not isinstance(detail, Mapping):
        return {}
    detail = detail.get("current_protection", detail)
    if not isinstance(detail, Mapping) or not detail.get("source_reason"):
        return {}
    return {key: detail[key] for key in ("source_reason", "owner", "source_ref", "observed_form", "observed_version", "next_action") if key in detail}


def _require(condition: Any, code: str) -> None:
    if not condition:
        raise FragmentError(code)


def _time(value: str | datetime) -> datetime:
    stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    _require(stamp.tzinfo is not None, "FRAGMENT_CLOCK_INVALID")
    return stamp.astimezone(UTC)


def _now(value: datetime | None = None) -> datetime:
    return _time(value or datetime.now(UTC))


def _canonical(body: Mapping[str, Any]) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def documents(store: Any, *, as_of: datetime | str | None = None) -> list[dict[str, Any]]:
    """Read verified fragment artifacts; preserve the ordinary memory cutoff."""
    cutoff = _time(as_of) if as_of else None
    result = []
    for record in store.iter_committed_records():
        if str(getattr(record.record_kind, "value", record.record_kind)) != "RESEARCH_ARTIFACT":
            continue
        if cutoff and (record.first_reliable_available_at > cutoff or record.effective_at > cutoff):
            continue
        try:
            wrapper = json.loads(record.payload_json)
        except (TypeError, ValueError):
            continue  # an unrelated generic artifact has no fragment identity
        if not isinstance(wrapper, Mapping):
            continue
        if not isinstance(wrapper.get("artifact_kind"), str) or wrapper["artifact_kind"] not in KINDS:
            continue
        fragment = str(record.entity_id or record.record_id)
        try:
            body = json.loads(wrapper["payload_canonical"])
            _require(isinstance(body, dict), "FRAGMENT_ARTIFACT_SHAPE_INVALID")
            proposed_id = body.get("fragment_version_id")
            if isinstance(proposed_id, str) and len(proposed_id) == 36 and proposed_id.startswith("RFV-"):
                fragment = proposed_id
            _require(isinstance(fragment, str) and len(fragment) == 36 and fragment.startswith("RFV-")
                     and all(c in "0123456789ABCDEF" for c in fragment[4:]), "FRAGMENT_IDENTITY_INVALID")
            _require(body.get("schema_version") == "1.0" and body.get("fragment_version_id") == fragment,
                     "FRAGMENT_ARTIFACT_SHAPE_INVALID")
            _require(canonical_sha256(body) == wrapper["payload_sha256"], "FRAGMENT_ARTIFACT_HASH_MISMATCH")
            _require(body["artifact_kind"] == wrapper["artifact_kind"], "FRAGMENT_ARTIFACT_KIND_MISMATCH")
            if body["artifact_kind"] == CARD:
                _require(body.get("role") in ROLES and isinstance(body.get("title"), str) and bool(body["title"])
                         and isinstance(body.get("source"), Mapping) and body.get("allowed_use") == "RESEARCH_ADVISORY",
                         "FRAGMENT_CARD_SHAPE_INVALID")
                expected = "RFV-" + canonical_sha256({"definition_sha256": body["source"]["definition_sha256"],
                                                     "declared_role": body["role"]})[:32].upper()
                _require(fragment == expected, "FRAGMENT_IDENTITY_INVALID")
            result.append({**body, "_record_id": record.record_id,
                           "_payload_sha256": wrapper["payload_sha256"],
                           "_available_at": record.first_reliable_available_at.isoformat()})
        except (KeyError, TypeError, ValueError):
            # An affected item stays visible without hiding unrelated cards.
            result.append({"artifact_kind": wrapper["artifact_kind"],
                           "fragment_version_id": str(fragment),
                           "_record_id": record.record_id,
                           "_error": "FRAGMENT_ARTIFACT_INTEGRITY_INVALID"})
    return result


class _AlreadyPresent(Exception):
    pass


def _append(store: Any, body: Mapping[str, Any], *, git_sha: str,
            now: datetime, check: Any = None) -> dict[str, Any]:
    digest = canonical_sha256(body)
    record_id = "RF-ART-" + digest[:40].upper()
    existing = next((r for r in documents(store) if r.get("_record_id") == record_id), None)
    if existing:
        return existing
    wrapper = {"research_artifact_id": record_id, "artifact_kind": body["artifact_kind"], "payload_canonical": _canonical(body),
               "payload_sha256": digest}
    payload = _canonical(wrapper)

    def guard():
        if any(r.get("_record_id") == record_id for r in documents(store)):
            raise _AlreadyPresent()
        if check is not None:
            check()

    event = ResearchEvent(record_id=record_id, record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=record_id, hypothesis_version_id=None, run_id=None,
        transaction_id="RESEARCH-TXN-RF-" + digest[:24].upper(), effective_at=now,
        first_reliable_available_at=now, supersedes_record_id=None,
        payload_json=payload, payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),
        schema_version="1.0", producer_capability_id="CAP-RESEARCH-FRAGMENTS-001",
        producer_git_sha=git_sha, created_at=now)
    try:
        store.append([event], transaction_id=event.transaction_id, before_commit=guard)
    except _AlreadyPresent:
        pass
    return next(r for r in documents(store) if r.get("_record_id") == record_id)


def source_evidence(store: Any, source: Mapping[str, Any]) -> dict[str, Any]:
    """Exact existing candidate/result only. No evaluator or market-value loader."""
    from solana_alpha_lab.factory.hfic_session import load_session_bundle
    from solana_alpha_lab.factory.hfic_grounded_discovery import assert_computed_grounded_evidence

    bundle = load_session_bundle(store, str(source.get("session_id") or ""))
    _require(bundle is not None, "FRAGMENT_SOURCE_SESSION_UNAVAILABLE")
    _require(bundle.get("selected_candidate_id") == source.get("candidate_id"), "FRAGMENT_CANDIDATE_MISMATCH")
    _require(bundle.get("selected_definition_sha256") == source.get("definition_sha256"), "FRAGMENT_DEFINITION_MISMATCH")
    packet = bundle.get("critic_input_packet") or {}
    evidence = packet.get("grounded_evidence") or {}
    _require(source.get("result_ref") in (evidence.get("result_refs") or []), "FRAGMENT_RESULT_REF_MISMATCH")
    _require(evidence.get("result_sha256") == source.get("result_sha256"), "FRAGMENT_RESULT_HASH_MISMATCH")
    verified = assert_computed_grounded_evidence(store, evidence)
    return {"candidate": copy.deepcopy(packet["selected_candidate"]), "evidence": verified,
            "session_terminal": bundle.get("final_session_terminal"),
            "availability_gap": (bundle.get("classifier_receipt") or {}).get("reason_codes") or [],
            "source_packet_sha256": bundle.get("critic_input_packet_sha256")}


def registration_preview(store: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    _require(request.get("role") in ROLES, "FRAGMENT_DECLARED_ROLE_REQUIRED")
    _require(isinstance(request.get("title"), str) and 0 < len(request["title"]) <= 200, "FRAGMENT_TITLE_REQUIRED")
    source = {k: request.get(k) for k in ("session_id", "candidate_id", "definition_sha256", "result_ref", "result_sha256")}
    verified = source_evidence(store, source)
    identity = {"definition_sha256": source["definition_sha256"], "declared_role": request["role"]}
    fragment = "RFV-" + canonical_sha256(identity)[:32].upper()
    supersedes = request.get("supersedes")
    if supersedes:
        _require(any(r.get("fragment_version_id") == supersedes and r["artifact_kind"] == CARD for r in documents(store)),
                 "FRAGMENT_SUPERSEDED_SOURCE_UNAVAILABLE")
        _require(supersedes != fragment, "FRAGMENT_SUPERSEDES_SELF")
    body = {"artifact_kind": CARD, "schema_version": "1.0", "fragment_version_id": fragment,
            "title": request["title"], "role": request["role"], "source": source,
            "supersedes": supersedes, "allowed_use": "RESEARCH_ADVISORY",
            "source_packet_sha256": verified["source_packet_sha256"]}
    return {"proposal": body, "proposal_sha256": canonical_sha256(body),
            "new_look": False, "writes": False}


def register(store: Any, request: Mapping[str, Any], *, git_sha: str,
             now: datetime | None = None) -> dict[str, Any]:
    body = registration_preview(store, request)["proposal"]
    prior = next((r for r in documents(store) if r["artifact_kind"] == CARD
                  and r.get("fragment_version_id") == body["fragment_version_id"]), None)
    if prior:
        _require(not prior.get("_error"), "FRAGMENT_ARTIFACT_INTEGRITY_INVALID")
        _require({k: v for k, v in prior.items() if not k.startswith("_")} == body,
                 "FRAGMENT_IDENTITY_ALREADY_REGISTERED_DIFFERENT_METADATA")
        return {"status": "ALREADY_PRESENT_EXACT", "fragment": prior, "new_look": False}
    def guard():
        if any(r["artifact_kind"] == CARD and r.get("fragment_version_id") == body["fragment_version_id"]
               for r in documents(store)):
            raise FragmentError("FRAGMENT_REGISTRATION_CHANGED_RETRY_READBACK")
        source_evidence(store, body["source"])
    saved = _append(store, body, git_sha=git_sha, now=_now(now), check=guard)
    return {"status": "REGISTERED", "fragment": saved, "new_look": False}


def _card(store: Any, fragment: str, *, as_of: datetime | str | None = None) -> dict[str, Any]:
    matches = [r for r in documents(store, as_of=as_of)
               if r["artifact_kind"] == CARD and r.get("fragment_version_id") == fragment]
    _require(len(matches) == 1 and not matches[0].get("_error"), "FRAGMENT_SOURCE_UNAVAILABLE")
    return matches[0]


def current_plan(rows: list[dict[str, Any]], fragment: str) -> dict[str, Any] | None:
    plans = [r for r in rows if r["artifact_kind"] == PLAN and r.get("fragment_version_id") == fragment]
    if not plans:
        return None
    _require(not any(r.get("_error") for r in plans), "FRAGMENT_PLAN_INTEGRITY_INVALID")
    for plan in plans:
        _require(type(plan.get("enabled")) is bool and type(plan.get("max_evaluations")) is int
                 and 1 <= plan["max_evaluations"] <= 16 and type(plan.get("max_input_rows")) is int
                 and 1 <= plan["max_input_rows"] <= 20_000_000 and isinstance(plan.get("windows"), list)
                 and 1 <= len(plan["windows"]) <= 16, "FRAGMENT_PLAN_SHAPE_INVALID")
        unsigned = {k: v for k, v in plan.items() if not k.startswith("_") and k != "plan_sha256"}
        _require(canonical_sha256(unsigned) == plan.get("plan_sha256"), "FRAGMENT_PLAN_HASH_MISMATCH")
    superseded = {r.get("previous_plan_sha256") for r in plans}
    heads = [r for r in plans if r["plan_sha256"] not in superseded]
    _require(len(heads) == 1, "FRAGMENT_PLAN_FORK")
    chain, cursor = set(), heads[0]
    by_sha = {p["plan_sha256"]: p for p in plans}
    while cursor:
        _require(cursor["plan_sha256"] not in chain, "FRAGMENT_PLAN_FORK")
        chain.add(cursor["plan_sha256"])
        parent = cursor.get("previous_plan_sha256")
        _require(parent is None or parent in by_sha, "FRAGMENT_PLAN_PARENT_UNAVAILABLE")
        cursor = by_sha.get(parent)
    _require(len(chain) == len(plans), "FRAGMENT_PLAN_FORK")
    return heads[0]


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_grounded_discovery import descriptive_return_readout
    readout = descriptive_return_readout(result)
    summary = {k: copy.deepcopy(readout.get(k)) for k in (
        "status", "matched", "baseline", "missingness", "tail_support", "baseline_may_include_matched",
        "details", "detail_truncation", "selection_policy")}
    # A list contrast keeps its own comparator: the pool baseline includes the
    # matched side and is never a complement. Legacy results stay UNKNOWN.
    for key in ("research_scope", "scientific_identity"):
        summary[key] = copy.deepcopy(readout.get(key)) if readout.get(key) is not None else "UNKNOWN"
    # Only a result that saved the paired block carries it. No default is written for older results:
    # their frozen capsules and archive fingerprints stay byte-identical.
    if readout.get("block_comparator") is not None:
        summary["block_comparator"] = copy.deepcopy(readout["block_comparator"])
    # Saved native dependency markers only. Absence is UNKNOWN, never a new
    # mint-overlap calculation or a claim of independent calendar replication.
    summary["dependence"] = {k: copy.deepcopy(result.get(k)) for k in (
        "mint_overlap_known", "overlap_exposed_base_x", "overlap_is_not_independent_replication",
        "calendar_overlap_is_not_independent_replication", "cohort_independent_replication",
        "cohort_slices_are_descriptive", "independence", "independent_replication", "unique_mint_n", "unique_decision_n")}
    summary["dependence"]["episode_counts"] = copy.deepcopy(result.get("episode_counts"))
    return summary


def _information_basis(result: Mapping[str, Any], rule: Mapping[str, Any]) -> dict[str, Any]:
    """Explain the existing rule using saved native quantities, without new stats."""
    matched = result.get("downside") or {}
    blocks = result.get("by_calendar_block")
    counts = [(b.get("downside") or {}).get("observed_n") for b in blocks] if isinstance(blocks, list) else None
    days = sum(n > 0 for n in counts) if counts is not None and all(type(n) is int for n in counts) else None
    observed = {"min_matched": matched.get("observed_n"), "min_days": days,
                "min_tail_mass": matched.get("es10_tail_mass_n")}
    criteria = {key: {"observed": value, "required": rule[key],
                      "met": value >= rule[key] if value is not None else None,
                      "reason": "SOURCE_UNAVAILABLE" if value is None else "MET" if value >= rule[key] else "BELOW_REQUIRED"}
                for key, value in observed.items()}
    return {"criteria": criteria, "enough": all(c["met"] is True for c in criteria.values()),
            "adverse_es10_delta": rule["adverse_es10_delta"], "source": "SAVED_NATIVE_RESULT"}


def _fragment_operations(store: Any, fragment: str) -> list[dict[str, Any]]:
    from solana_alpha_lab.factory.hfic_ordinary_operation import list_operations, get_operation
    return [get_operation(store, digest) for digest in sorted({o["operation_sha256"] for o in list_operations(store)
            if (o.get("fragment_check") or {}).get("fragment_version_id") == fragment})]


def _plan_by_sha(rows: list[dict[str, Any]], digest: str) -> dict[str, Any] | None:
    matches = [p for p in rows if p["artifact_kind"] == PLAN and p.get("plan_sha256") == digest]
    _require(len(matches) <= 1, "FRAGMENT_PLAN_SOURCE_AMBIGUOUS")
    if not matches or matches[0].get("_error"):
        return None
    plan = matches[0]
    unsigned = {k: v for k, v in plan.items() if not k.startswith("_") and k != "plan_sha256"}
    return plan if canonical_sha256(unsigned) == digest else None


def _saved_check_basis(result: Mapping[str, Any], check: Mapping[str, Any],
                       rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Unavailable execution metadata cannot erase independently verified results."""
    try:
        plan = _plan_by_sha(rows, check["plan_sha256"])
        _require(plan is not None, "FRAGMENT_INFORMATION_RULE_SOURCE_UNAVAILABLE")
        return {"status": "AVAILABLE", **_information_basis(result, plan["information_rule"])}
    except (StopIteration, KeyError, TypeError, ValueError):
        return {"status": "UNKNOWN", "reason": "FRAGMENT_INFORMATION_RULE_SOURCE_UNAVAILABLE",
                "source_plan_sha256": check["plan_sha256"], "criteria": None, "enough": None}


def _fragment_cards(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards = [r for r in rows if r["artifact_kind"] == CARD]
    known = {r.get("fragment_version_id") for r in cards}
    # Execution metadata errors belong to their card's dependent gate, not
    # a competing error-card whose partition order could hide trusted evidence.
    return cards + [r for r in rows if r.get("_error") and r["artifact_kind"] != CARD
                    and r.get("fragment_version_id") not in known]


def source_snapshot(store: Any, *, as_of: datetime | str | None = None,
                    now: datetime | None = None) -> list[dict[str, Any]]:
    """One read-only source snapshot for UI, CLI and ordinary prior consumers."""
    rows = documents(store, as_of=as_of)
    if as_of and any(r["artifact_kind"] == CARD for r in rows):
        # Both the descriptive sources and native spend must obey the saved
        # cutoff. A future result/reservation must not alter a frozen capsule.
        from solana_alpha_lab.factory.hfic_memory_policy import research_record_visible_as_of
        visible = [r for r in store.iter_committed_records() if research_record_visible_as_of(r, _time(as_of))]
        class VisibleRead:
            root = store.root
            _root = store.root  # existing immutable context-artifact reader contract
            def iter_committed_records(self):
                return iter(visible)
        store = VisibleRead()
    views = []
    for card in _fragment_cards(rows):
        fragment = card.get("fragment_version_id")
        try:
            _require(not card.get("_error"), "FRAGMENT_ARTIFACT_INTEGRITY_INVALID")
            source = source_evidence(store, card["source"])
            _require(source["source_packet_sha256"] == card["source_packet_sha256"], "FRAGMENT_SOURCE_PACKET_CHANGED")
            checks = [r for r in rows if r["artifact_kind"] == CHECK and r.get("fragment_version_id") == fragment]
            _require(not any(r.get("_error") for r in checks), "FRAGMENT_CHECK_INTEGRITY_INVALID")
            blocks = [{"kind": "DISCOVERY", "result_ref": card["source"]["result_ref"],
                       "result_sha256": card["source"]["result_sha256"],
                       "summary": _summary(source["evidence"]["result"]),
                       "assessment": "PRELIMINARY_OBSERVATION", "exposure": "EXPLORATORY_REUSE"}]
            for check in sorted(checks, key=lambda r: (r["window"]["start"], r["_record_id"])):
                from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
                look = next((x for x in list_discovery_looks(store, check["journal_scope"])
                             if x.get("record_id") == check["result_ref"]), None)
                _require(look and look.get("result_sha256") == check["result_sha256"], "FRAGMENT_CHECK_SOURCE_UNAVAILABLE")
                from solana_alpha_lab.factory.hfic_grounded_discovery import result_sha256
                _require(result_sha256(look["result"]) == check["result_sha256"], "FRAGMENT_CHECK_RESULT_HASH_MISMATCH")
                blocks.append({**{k: check[k] for k in ("window", "result_ref", "result_sha256", "assessment", "attention")},
                               "kind": "MONITORING", "summary": _summary(look["result"]),
                               "information_basis": _saved_check_basis(look["result"], check, rows),
                               "exposure": "EXPLORATORY_MONITORING", "source_ref": check["_record_id"]})
            plan = None
            try:
                plan = current_plan(rows, str(fragment))
                freshness = plan_status(store, card, plan, rows=rows, now=_time(as_of) if as_of else _now(now))
            except (ValueError, KeyError, TypeError, OSError, ResearchStoreError) as exc:
                # Execution metadata cannot erase already verified evidence.
                freshness = {"status": "BLOCKED", "reason": getattr(exc, "code", "FRAGMENT_EXECUTION_UNAVAILABLE"), **source_detail(exc), "new_look": False}
            if freshness["status"] != "BLOCKED" and any(
                    (b.get("information_basis") or {}).get("status") == "UNKNOWN" for b in blocks):
                freshness = {**freshness, "status": "BLOCKED", "reason": "FRAGMENT_INFORMATION_RULE_SOURCE_UNAVAILABLE"}
            if (not as_of and plan and plan.get("enabled") and freshness["status"] in {"DUE", "FUTURE_WAIT"}
                    and freshness.get("reason") != "FRAGMENT_RECOVER_LANDED_RESULT"):
                protection = current_protection_status(store)
                if protection["status"] != "ALLOW":
                    freshness = {**freshness, "status": "BLOCKED", "reason": "HOLDOUT_UNRESOLVED", **source_detail(protection)}
                else:
                    try:
                        from solana_alpha_lab.factory.hfic_evidence_identity import compute_capability_epoch_for_repo
                        _require(compute_capability_epoch_for_repo(Path(__file__).resolve().parents[3])[0] == plan["capability_epoch_sha256"],
                                 "FRAGMENT_EXECUTION_BINDING_CHANGED")
                        recheck_spec(store, card)
                    except (ValueError, KeyError, TypeError, OSError, ResearchStoreError) as exc:
                        # A dependent execution gate never hides saved evidence.
                        freshness = {**freshness, "status": "BLOCKED", "reason": getattr(exc, "code", "FRAGMENT_EXECUTION_UNAVAILABLE"), **source_detail(exc)}
            restrictions = {k: copy.deepcopy(source["candidate"].get(k)) for k in (
                "confounders", "pit_leakage_survivorship_risks", "execution_capacity_risks", "missing_or_forward_only_data")}
            views.append({"fragment_version_id": fragment, "title": card["title"], "role": card["role"],
                "source": card["source"], "source_ref": card["_record_id"], "source_sha256": card["_payload_sha256"],
                "first_reliable_available_at": card["_available_at"], "supersedes": card.get("supersedes"),
                "allowed_use": card["allowed_use"], "evidence_blocks": blocks, "plan": plan,
                "check": freshness, "source_candidate": source["candidate"],
                "source_restrictions": restrictions,
                "attention": any(b.get("attention") == "ADVERSE_REVIEW_REQUIRED" for b in blocks),
                "source_terminal": source["session_terminal"], "source_availability_gaps": source["availability_gap"],
                "claim_boundary": "RESEARCH_ADVISORY_NO_CONFIRMATION_NO_STRATEGY_ACTIVATION"})
        except (ValueError, KeyError, TypeError, OSError, ResearchStoreError) as exc:
            views.append({"fragment_version_id": fragment, "title": card.get("title") or str(fragment),
                          "source_ref": card["_record_id"], "error": getattr(exc, "code", "FRAGMENT_SOURCE_INVALID"),
                          "allowed_use": "BLOCKED_DEPENDENT_USE"})
    return sorted(views, key=lambda r: str(r["fragment_version_id"]))


def plan_status(store: Any, card: Mapping[str, Any], plan: Mapping[str, Any] | None,
                *, rows: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    if plan is None:
        return {"status": "DISABLED", "reason": "NO_ENABLED_PLAN", "new_look": False}
    completed = {r.get("window_key") for r in rows if r["artifact_kind"] == CHECK
                 and r.get("fragment_version_id") == card["fragment_version_id"]}
    from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy, operation_lifecycle, _unresolved_reservations
    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
    spent = journal_occupancy(store, plan["journal_scope"])["main"]
    looks = list_discovery_looks(store, plan["journal_scope"])
    attempts = []
    for operation in _fragment_operations(store, card["fragment_version_id"]):
        if any(l.get("operation_sha256") == operation["operation_sha256"] for l in looks):
            continue
        state = operation_lifecycle(store, operation)["effective_state"]
        context = operation["fragment_check"]
        original = _plan_by_sha(rows, context["plan_sha256"])
        matches = context["capability_epoch_sha256"] == plan["capability_epoch_sha256"]
        contract_allows = (original is not None and matches and context["window"] in plan["windows"]
                           and now <= min(_time(plan["execution_deadline"]), _time(original["execution_deadline"])))
        next_action = ("CONTINUE_ALLOWED_WINDOWS" if state == "STOPPED" else
                       "KEEP_PAUSED_OR_EXPLICIT_NATIVE_STOP" if not plan.get("enabled") else
                       "EXPLICIT_NATIVE_STOP" if not contract_allows else "RESUME_OR_EXPLICIT_NATIVE_STOP")
        attempts.append({"operation_sha256": operation["operation_sha256"], "record_id": operation["record_id"],
            "window": operation["fragment_check"]["window"], "window_key": operation["fragment_check"]["window_key"],
            "effective_state": state, "unresolved_reservation_spec_sha256": _unresolved_reservations(store, operation),
            "holds_universe_gate": state == "OPEN", "scientific_verdict": None, "quota_returned": False,
            "execution_binding_matches_plan": matches, "next_action": next_action,
            "resume_contract_allows_now": bool(plan.get("enabled") and contract_allows and state == "OPEN"),
            "stop_preview_args": ["operation-stop-preview", "--operation-sha256", operation["operation_sha256"],
                                  "--owner-request-text", "<explicit reason for ending this attempt>"]})
    common = {"native_spend": spent, "attempts_without_result": attempts, "new_look": False}
    if spent["completed"] > len(completed):
        return {**common, "status": "DUE", "reason": "FRAGMENT_RECOVER_LANDED_RESULT"}
    if not plan.get("enabled"):
        return {**common, "status": "DISABLED", "reason": "NO_ENABLED_PLAN"}
    if now > _time(plan["execution_deadline"]):
        return {**common, "status": "EXPIRED", "reason": "PLAN_DEADLINE_PASSED"}
    pending = [a for a in attempts if a["effective_state"] != "STOPPED"]
    if pending:
        attempt = pending[0]
        if not attempt["resume_contract_allows_now"]:
            return {**common, "status": "BLOCKED", "reason": "FRAGMENT_PENDING_NATIVE_STOP_REQUIRED"}
        return {**common, "status": "DUE", "window": attempt["window"],
                "window_index": plan["windows"].index(attempt["window"]), "reason": "FRAGMENT_RESUME_PENDING_ATTEMPT"}
    if spent["occupied"] >= min(plan["max_evaluations"], spent["limit"]):
        return {**common, "status": "COMPLETE", "reason": "PLAN_CAP_SPENT" if plan["max_evaluations"] <= spent["limit"] else "NATIVE_CAP_SPENT"}
    stopped = {a["window_key"] for a in attempts if a["effective_state"] == "STOPPED"}
    for index, window in enumerate(plan["windows"]):
        if canonical_sha256(window) not in completed | stopped:
            due = _time(window["input_closed_at"])
            return {**common, "status": "DUE" if now >= due else "FUTURE_WAIT", "window_index": index,
                    "window": window, "next_trigger": due.isoformat()}
    return {**common, "status": "COMPLETE", "reason": "ALL_WINDOWS_RECORDED_OR_EXPLICITLY_STOPPED"}


def journal_for(fragment: str) -> str:
    return canonical_sha256({"purpose": CHECK, "fragment_version_id": fragment})


def root_identity(store: Any) -> str:
    return canonical_sha256({"data_root": str(store.root.resolve())})


def current_protection_status(store: Any) -> dict[str, Any]:
    """Read-only source-owned current proof; historical pins cannot fill it."""
    from solana_alpha_lab.factory.episode_current_protection import resolve_current_research_protection
    return resolve_current_research_protection(store.root)[0]


def plan_preview(store: Any, request: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    stamp = _now(now)
    fragment = str(request.get("fragment_version_id") or "")
    rows = documents(store)
    previous = current_plan(rows, fragment)
    pausing = request.get("enabled") is False and previous is not None
    # Revocation is metadata, and remains possible after source/profile/code
    # drift. Enabling always revalidates the actual scientific sources.
    if pausing:
        card = {"source": {"definition_sha256": previous["source_definition_sha256"]}}
        saved_source = None
    else:
        card = _card(store, fragment)
        saved_source = source_evidence(store, card["source"])
        recheck_spec(store, card)
    _require(request.get("scientific_use") == "EXPLORATORY_MONITORING", "FRAGMENT_CONFIRMATORY_PLAN_NOT_SUPPORTED")
    _require(request.get("source_roles") == ["EXPLORATORY_REUSE"], "FRAGMENT_SOURCE_ROLES_INVALID")
    _require(request.get("data_root_identity_sha256") == root_identity(store), "FRAGMENT_DATA_ROOT_MISMATCH")
    _require(request.get("access_boundary") == {"forge": "EXPOSED_OR_UNKNOWN", "scout": "EXPOSED_OR_UNKNOWN",
              "confirmatory_claims": False, "protected_holdouts": "EXCLUDE"}, "FRAGMENT_ACCESS_BOUNDARY_REQUIRED")
    _require(isinstance(request.get("enabled"), bool), "FRAGMENT_PLAN_ENABLED_REQUIRED")
    _require(isinstance(request.get("owner_scope_ref"), str) and bool(request["owner_scope_ref"].strip()),
             "FRAGMENT_OWNER_SCOPE_REQUIRED")
    windows = request.get("windows")
    _require(isinstance(windows, list) and 1 <= len(windows) <= 16, "FRAGMENT_WINDOWS_INVALID")
    normalized = []
    prior_end = None
    from solana_alpha_lab.factory.opportunity_episodes import V1_HORIZON
    source_inputs = saved_source["evidence"]["result"]["experiment_recipe"]["frozen_input"] if saved_source else []
    drain = max([V1_HORIZON, *(V1_HORIZON + int(i["schedule_binding"]["dispatch_window_seconds"])
                + int(i["schedule_binding"]["availability_grace_seconds"]) for i in source_inputs)])
    for window in windows:
        _require(isinstance(window, Mapping) and set(window) == {"start", "end", "input_closed_at"}, "FRAGMENT_WINDOW_INVALID")
        start, end, closed = (_time(window[k]) for k in ("start", "end", "input_closed_at"))
        _require(start < end <= start + timedelta(days=64) and (prior_end is None or start >= prior_end), "FRAGMENT_WINDOW_OVERLAP_OR_SIZE")
        _require(start.hour == end.hour == 0 and start.minute == end.minute == 0
                 and start.second == end.second == start.microsecond == end.microsecond == 0,
                 "FRAGMENT_ADMISSION_WINDOW_MUST_BE_UTC_DAYS")
        _require(closed >= end + timedelta(seconds=drain), "FRAGMENT_INPUT_NOT_MATURE")
        normalized.append({"start": start.isoformat(), "end": end.isoformat(), "input_closed_at": closed.isoformat()})
        prior_end = end
    unchanged_schedule = previous is not None and previous["windows"] == normalized
    if not unchanged_schedule:
        frozen = [w for w in previous["windows"] if _time(w["start"]) <= stamp] if previous else []
        _require(normalized[:len(frozen)] == frozen and all(_time(w["start"]) > stamp for w in normalized[len(frozen):]),
                 "FRAGMENT_PLAN_NOT_PROSPECTIVE")
    deadline = _time(request["execution_deadline"])
    _require(_time(normalized[-1]["input_closed_at"]) <= deadline <= _time(normalized[-1]["end"]) + timedelta(days=14),
             "FRAGMENT_PLAN_DEADLINE_INVALID")
    _require(not request["enabled"] or deadline > stamp, "FRAGMENT_PLAN_EXPIRED")
    max_evaluations = request.get("max_evaluations")
    max_rows = request.get("max_input_rows")
    _require(type(max_evaluations) is int and 1 <= max_evaluations <= 16, "FRAGMENT_EVALUATION_CAP_INVALID")
    _require(type(max_rows) is int and 1 <= max_rows <= 20_000_000, "FRAGMENT_COMPUTE_CAP_INVALID")
    rules = request.get("information_rule")
    _require(isinstance(rules, Mapping) and set(rules) == {"min_matched", "min_days", "min_tail_mass", "adverse_es10_delta"},
             "FRAGMENT_INFORMATION_RULE_REQUIRED")
    _require(type(rules["min_matched"]) is int and rules["min_matched"] >= 1
             and type(rules["min_days"]) is int and rules["min_days"] >= 1
             and isinstance(rules["min_tail_mass"], (int, float)) and rules["min_tail_mass"] > 0
             and isinstance(rules["adverse_es10_delta"], (int, float)) and rules["adverse_es10_delta"] >= 0,
             "FRAGMENT_INFORMATION_RULE_INVALID")
    _require(all(type(rules[k]) in (int, float) and math.isfinite(rules[k]) for k in ("min_tail_mass", "adverse_es10_delta")),
             "FRAGMENT_INFORMATION_RULE_INVALID")
    if previous and _time(previous["windows"][0]["start"]) <= stamp:
        _require(rules == previous["information_rule"], "FRAGMENT_RULE_ALREADY_FROZEN")
    body = {"artifact_kind": PLAN, "schema_version": "1.0", "fragment_version_id": fragment,
            "source_definition_sha256": card["source"]["definition_sha256"],
            "data_root_identity_sha256": root_identity(store), "collection": "OPPORTUNITY_EPISODES",
            "journal_scope": journal_for(fragment), "previous_plan_sha256": previous["plan_sha256"] if previous else None,
            "enabled": request["enabled"], "windows": normalized, "execution_deadline": deadline.isoformat(),
            "max_evaluations": max_evaluations, "max_input_rows": max_rows,
            "information_rule": dict(rules), "source_roles": list(request["source_roles"]),
            "scientific_use": request["scientific_use"], "access_boundary": dict(request["access_boundary"]),
            "owner_scope_ref": request["owner_scope_ref"], "prepared_at": stamp.isoformat()}
    from solana_alpha_lab.factory.hfic_evidence_identity import compute_capability_epoch_for_repo
    body["capability_epoch_sha256"] = previous["capability_epoch_sha256"] if pausing else compute_capability_epoch_for_repo(Path(__file__).resolve().parents[3])[0]
    body["plan_sha256"] = canonical_sha256(body)
    return {"proposal": body, "proposal_sha256": canonical_sha256(body),
            "writes": False, "new_look": False, "activation": "REQUIRES_EXACT_OWNER_SCOPE",
            "current_protection": current_protection_status(store)}


def apply_plan(store: Any, proposal: Mapping[str, Any], *, git_sha: str,
               now: datetime | None = None) -> dict[str, Any]:
    stamp = _now(now)
    body = dict(proposal.get("proposal") or {})
    _require(canonical_sha256(body) == proposal.get("proposal_sha256"), "FRAGMENT_PLAN_PROPOSAL_CHANGED")
    unsigned = {k: v for k, v in body.items() if k != "plan_sha256"}
    _require(canonical_sha256(unsigned) == body.get("plan_sha256"), "FRAGMENT_PLAN_HASH_MISMATCH")
    existing = next((r for r in documents(store) if r["artifact_kind"] == PLAN
                     and r.get("plan_sha256") == body["plan_sha256"]), None)
    if existing:
        return {"status": "ALREADY_APPLIED", "plan": existing, "new_look": False}
    # Revalidate authority/clock/shape at application, never trust an edited preview.
    rebuilt = plan_preview(store, body, now=stamp)["proposal"]
    for field in ("prepared_at", "plan_sha256"):
        rebuilt[field] = body[field]
    _require(rebuilt == body, "FRAGMENT_PLAN_PROPOSAL_STALE")
    def guard():
        head = current_plan(documents(store), body["fragment_version_id"])
        _require((head["plan_sha256"] if head else None) == body["previous_plan_sha256"], "FRAGMENT_PLAN_CHANGED")
        if body["enabled"]:
            _card(store, body["fragment_version_id"])
            protection = current_protection_status(store)
            if protection["status"] != "ALLOW":
                raise FragmentError("HOLDOUT_UNRESOLVED", {"current_protection": protection})
            from solana_alpha_lab.factory.hfic_evidence_identity import compute_capability_epoch_for_repo
            _require(compute_capability_epoch_for_repo(Path(__file__).resolve().parents[3])[0] == body["capability_epoch_sha256"],
                     "FRAGMENT_EXECUTION_BINDING_CHANGED")
    saved = _append(store, body, git_sha=git_sha, now=stamp, check=guard)
    return {"status": "APPLIED", "plan": saved, "new_look": False}


def recheck_spec(store: Any, card: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Derive from the immutable native query, never a second editable formula."""
    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query, _public_query_from_recipe
    source = source_evidence(store, card["source"])
    _require(card.get("source_packet_sha256") == source["source_packet_sha256"], "FRAGMENT_SOURCE_PACKET_CHANGED")
    recipe = source["evidence"]["result"]["experiment_recipe"]
    from solana_alpha_lab.factory.hfic_research_universe_policy import effective_policy
    frozen_policy = source["evidence"]["result"].get("universe_policy") or {}
    _require(frozen_policy.get("semantic_sha256") == effective_policy(store).get("semantic_sha256"),
             "FRAGMENT_UNIVERSE_POLICY_CHANGED")
    spec = copy.deepcopy(_public_query_from_recipe(recipe))
    # Monitoring does not add the discovery ablation family to every window.
    _require(spec.get("population") == "OPPORTUNITY_EPISODES", "FRAGMENT_NATIVE_EPISODE_QUERY_REQUIRED")
    spec["evaluation"]["ablations"] = "NONE"
    validate_temporal_query(spec)
    return spec, copy.deepcopy(source["evidence"]["candidate_scope"])


def _window_spec(store: Any, card: Mapping[str, Any], binding: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    spec, scope = recheck_spec(store, card)
    selection = spec.setdefault("research_scope", {})
    selection["evidence_selection"] = {"kind": "EXPLICIT_VERIFIED_RELEASE_SET",
        "cohort_ids": sorted(r["cohort_id"] for r in binding)}
    # The native spec owner canonicalizes this exact input scope into identity;
    # the condition, metric, baseline, clock and missingness remain source-owned.
    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query
    validate_temporal_query(spec)
    from solana_alpha_lab.factory.hfic_grounded_discovery import validate_discovery_request_scope
    machine_axes = {"population", "decision_timestamp", "target", "research_scope_rule_sha256", "research_scope_statement"}
    scope = validate_discovery_request_scope(spec, {k: v for k, v in scope.items() if k not in machine_axes})
    return spec, scope


def _window_binding(data_root: Path, window: Mapping[str, Any]) -> list[dict[str, Any]]:
    from solana_alpha_lab.factory.opportunity_episode_release import load_episode_lineage
    from solana_alpha_lab.factory.opportunity_episodes import cohort_day_bounds
    from solana_alpha_lab.factory.hfic_grounded_discovery import resolve_published_episode_binding
    start, end = _time(window["start"]), _time(window["end"])
    selected = []
    days = []
    for item in load_episode_lineage(data_root).get("cohorts") or []:
        a, b = cohort_day_bounds(str(item["cohort_id"]))
        if start <= a and b <= end:
            selected.append(str(item["cohort_id"]))
            days.append(a)
    expected = [start + timedelta(days=n) for n in range((end-start).days)]
    _require(sorted(days) == expected, "FRAGMENT_WINDOW_INPUTS_NOT_COMPLETE")
    return resolve_published_episode_binding(data_root, cohort_ids=selected)["cohorts"]


def _verify_inputs(data_root: Path, binding: list[dict[str, Any]], max_rows: int) -> None:
    from solana_alpha_lab.factory.episode_required_outcomes import verify_frozen_episode_sources
    from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_frozen_input
    from solana_alpha_lab.factory.data_resolver import _safe_relative_path
    import pyarrow.parquet as pq
    rows = 0
    for item in binding:
        for key in ("census_rel", "observations_rel"):
            path = data_root / _safe_relative_path(item[key])
            _require(path.resolve().is_relative_to(data_root.resolve()) and not path.is_symlink(), "FRAGMENT_SOURCE_PATH_INVALID")
            rows += pq.ParquetFile(path).metadata.num_rows
    _require(rows <= max_rows, "FRAGMENT_COMPUTE_ROW_CAP_EXCEEDED")
    verify_frozen_episode_sources(data_root, temporal_frozen_input(binding))


def _value_points(spec: Mapping[str, Any]) -> list[str]:
    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query, _feature_dependencies
    body = validate_temporal_query(spec)["scientific_body"]
    points = {body["decision_point"], body["target"]["reference_point"], body["target"]["exit_point"]}
    points.update(point for feature in body["features"] for point, _field in _feature_dependencies(feature))
    return sorted(points)


def validate_operation(store: Any, operation: Mapping[str, Any], *, data_root: Path | None = None,
                       repo_root: Path | None = None) -> None:
    """Source/authority gate, also called under the native reservation writer lease.

    It reads identities/protection/row-count metadata only. All numerical work
    remains behind ordinary authorize_temporal_attempt and the recorded runner.
    """
    from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy, effective_open_operations, list_operations, _reservations
    context = operation["fragment_check"]
    rows = documents(store)
    fragment = context["fragment_version_id"]
    card = _card(store, fragment)
    plan = current_plan(rows, fragment)
    original = _plan_by_sha(rows, context["plan_sha256"])
    _require(plan and original and plan.get("enabled"), "FRAGMENT_PLAN_DISABLED_OR_UNAVAILABLE")
    _require(plan["source_definition_sha256"] == original["source_definition_sha256"] == card["source"]["definition_sha256"],
             "FRAGMENT_DEFINITION_MISMATCH")
    _require(plan["data_root_identity_sha256"] == root_identity(store), "FRAGMENT_DATA_ROOT_MISMATCH")
    root = Path(data_root or store.root).resolve()
    _require(root == store.root.resolve(), "FRAGMENT_DATA_ROOT_MISMATCH")
    _require(context["window"] in plan["windows"] and context["window"] in original["windows"], "FRAGMENT_WINDOW_NO_LONGER_AUTHORIZED")
    _require(canonical_sha256(context["window"]) == context["window_key"], "FRAGMENT_WINDOW_KEY_INVALID")
    _require(operation["journal_scope"] == plan["journal_scope"] == journal_for(fragment), "FRAGMENT_JOURNAL_MISMATCH")
    _require(operation["owner_focus"] == "OPPORTUNITY_EPISODES:FRAGMENT:" + fragment, "FRAGMENT_FOCUS_MISMATCH")
    _require(operation["requested_completion"] == "LIMITED_RESULT" and operation["owner_cap"] == {"main": 1, "adaptive": 0, "preview": 0},
             "FRAGMENT_OPERATION_CAP_MISMATCH")
    _require(not any(operation.get(k) for k in ("representation", "cycle_index", "parent_operation_sha256", "accounting_root")),
             "FRAGMENT_OPERATION_LINEAGE_UNSUPPORTED")
    stamp = _now()
    _require(_time(context["window"]["input_closed_at"]) <= stamp <= min(_time(plan["execution_deadline"]), _time(original["execution_deadline"])),
             "FRAGMENT_WINDOW_NOT_EXECUTABLE_NOW")
    occupied = journal_occupancy(store, plan["journal_scope"])["main"]
    owned = bool(operation.get("operation_sha256") and _reservations(store, operation["operation_sha256"]))
    limit = min(plan["max_evaluations"], original["max_evaluations"])
    _require(occupied["occupied"] <= limit and (occupied["occupied"] < limit or owned),
             "FRAGMENT_PLAN_CAP_SPENT")
    for other in list_operations(store):
        prior = other.get("fragment_check") or {}
        if prior.get("fragment_version_id") == fragment and prior.get("window_key") == context["window_key"]:
            _require(other["operation_sha256"] == operation.get("operation_sha256"), "FRAGMENT_WINDOW_ALREADY_OWNED")
    for item in effective_open_operations(store):
        _require(item["operation_sha256"] == operation.get("operation_sha256"), "FRAGMENT_CONFLICTING_OPERATION")
    _verify_inputs(root, context["binding"], min(plan["max_input_rows"], original["max_input_rows"]))
    from solana_alpha_lab.factory.opportunity_episodes import cohort_day_bounds
    days = sorted(cohort_day_bounds(r["cohort_id"])[0] for r in context["binding"])
    start, end = _time(context["window"]["start"]), _time(context["window"]["end"])
    _require(days == [start + timedelta(days=n) for n in range((end-start).days)], "FRAGMENT_WINDOW_BINDING_INVALID")
    maturation = max(int(r["schedule_binding"]["horizon_seconds"]) + int(r["schedule_binding"]["dispatch_window_seconds"])
                     + int(r["schedule_binding"]["availability_grace_seconds"]) for r in context["binding"])
    _require(_time(context["window"]["input_closed_at"]) >= end + timedelta(seconds=maturation), "FRAGMENT_INPUT_CLOSURE_BEFORE_NATIVE_DRAIN")
    spec, _ = _window_spec(store, card, context["binding"])
    _require(operation["spec_canonical"] == _canonical(spec), "FRAGMENT_IMMUTABLE_QUERY_MISMATCH")
    # The frozen input may survive additional compatible imports; it never
    # survives arbitrary code/policy replacement without an explicit review.
    from solana_alpha_lab.factory.hfic_evidence_identity import compute_split_identity, market_evidence_epoch_sha256
    split = compute_split_identity(Path(repo_root or Path(__file__).resolve().parents[3]), root, store=store)
    _require(market_evidence_epoch_sha256(context["market_evidence_basis"]) == operation["market_evidence_epoch_sha256"],
             "FRAGMENT_MARKET_BINDING_INVALID")
    _require(split["capability_epoch_sha256"] == context["capability_epoch_sha256"], "FRAGMENT_EXECUTION_BINDING_CHANGED")
    _require(context["capability_epoch_sha256"] == original["capability_epoch_sha256"] == plan["capability_epoch_sha256"],
             "FRAGMENT_EXECUTION_BINDING_CHANGED")


def _link_check(store: Any, operation: Mapping[str, Any], look: Mapping[str, Any], *, git_sha: str) -> dict[str, Any]:
    context = operation["fragment_check"]
    rows = documents(store)
    plan = _plan_by_sha(rows, context["plan_sha256"])
    _require(plan is not None, "FRAGMENT_INFORMATION_RULE_SOURCE_UNAVAILABLE")
    readout = _summary(look["result"])
    matched = (readout.get("matched") or {}).get("downside") or {}
    baseline = (readout.get("baseline") or {}).get("downside") or {}
    rule = plan["information_rule"]
    # Native descriptive quantities, never a pooled estimate or a new verdict.
    enough = _information_basis(look["result"], rule)["enough"]
    delta = matched.get("es10_return")
    base = baseline.get("es10_return")
    adverse = enough and delta is not None and base is not None and delta - base < -rule["adverse_es10_delta"]
    body = {"artifact_kind": CHECK, "schema_version": "1.0", "fragment_version_id": context["fragment_version_id"],
            "plan_sha256": context["plan_sha256"], "window": context["window"], "window_key": context["window_key"],
            "journal_scope": operation["journal_scope"], "operation_sha256": operation["operation_sha256"],
            "result_ref": look["record_id"], "result_sha256": look["result_sha256"],
            "assessment": "DESCRIPTIVE_CHECK_RECORDED" if enough else "INCONCLUSIVE",
            "attention": "ADVERSE_REVIEW_REQUIRED" if adverse else "NO_AUTOMATIC_PROMOTION_OR_KILL",
            "scientific_use": "EXPLORATORY_MONITORING"}
    return _append(store, body, git_sha=git_sha, now=_now())


def run_due(store: Any, *, repo_root: Path, git_sha: str) -> dict[str, Any]:
    """Actual import follow-up / explicit cold resume. At most one new evaluation.

    No durable poll records; linking a landed result is metadata-only recovery.
    An authorized plan is the durable pending intent, native operations retain
    frozen inputs and native reservations retain spend across process crashes.
    """
    from solana_alpha_lab.factory.hfic_ordinary_operation import (
        record_operation, authorize_temporal_attempt, note_look_landed)
    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        list_discovery_looks, load_admitted_partition_rows, run_recorded_discovery_query)
    from solana_alpha_lab.factory.hfic_evidence_identity import compute_split_identity
    rows = documents(store)
    reports = []
    for card in _fragment_cards(rows):
        fragment = card.get("fragment_version_id") or card["_record_id"]
        values_loaded = False
        status = {}
        try:
            _require(not card.get("_error"), "FRAGMENT_ARTIFACT_INTEGRITY_INVALID")
            operations = _fragment_operations(store, fragment)
            for operation in operations:
                look = next((l for l in list_discovery_looks(store, operation["journal_scope"])
                             if l.get("operation_sha256") == operation["operation_sha256"]), None)
                if look and not any(r.get("operation_sha256") == operation["operation_sha256"] and r["artifact_kind"] == CHECK for r in rows):
                    note_look_landed(store, operation["operation_sha256"])
                    saved = _link_check(store, operation, look, git_sha=git_sha)
                    return {"status": "RECOVERED_LANDED_RESULT", "source_ref": saved["_record_id"], "new_look": False, "values_loaded": False}
            plan = current_plan(rows, fragment)
            status = plan_status(store, card, plan, rows=rows, now=_now())
            if status["status"] != "DUE":
                reports.append({"fragment_version_id": fragment, **status})
                continue
            window = status["window"]
            key = canonical_sha256(window)
            operation = next((o for o in operations if o["fragment_check"]["window_key"] == key), None)
            if operation is None:
                binding = _window_binding(store.root, window)
                _verify_inputs(store.root, binding, plan["max_input_rows"])
                spec, scope = _window_spec(store, card, binding)
                split = compute_split_identity(repo_root, store.root, store=store)
                operation = record_operation(store, {"owner_request_text": "Approved fragment monitoring: " + plan["owner_scope_ref"],
                    "owner_focus": "OPPORTUNITY_EPISODES:FRAGMENT:" + fragment,
                    "journal_scope": plan["journal_scope"], "market_evidence_epoch_sha256": split["market_evidence_epoch_sha256"],
                    "question_text": card["title"], "owner_cap": {"main": 1, "adaptive": 0, "preview": 0},
                    "requested_completion": "LIMITED_RESULT", "spec": spec,
                    "fragment_check": {"fragment_version_id": fragment, "plan_sha256": plan["plan_sha256"], "window": window,
                        "window_key": key, "binding": binding, "market_evidence_basis": split["market_evidence_basis"],
                        "capability_epoch_sha256": split["capability_epoch_sha256"]}})
            else:
                binding = operation["fragment_check"]["binding"]
                spec, scope = _window_spec(store, card, binding)
            validate_operation(store, operation, repo_root=repo_root)
            authorize_temporal_attempt(store, operation_sha256=operation["operation_sha256"], spec=spec,
                journal_scope=operation["journal_scope"], binding_cohorts=binding,
                verified_market=operation["market_evidence_epoch_sha256"], repo_root=repo_root, data_root=store.root)
            # A change after native reservation must still stop before the
            # first value loader. Reservation/accounting survives this refusal.
            _verify_inputs(store.root, binding, plan["max_input_rows"])
            # Frozen verified partitions: later publication pointers cannot
            # replace their manifest ids or widen the denominator at load time.
            values_loaded = True
            loaded = load_admitted_partition_rows(data_root=None, binding_doc={"cohorts": binding},
                partitions=[(b["cohort_id"], store.root / b["census_rel"], store.root / b["observations_rel"]) for b in binding],
                census_path=None, observations_path=None, population="OPPORTUNITY_EPISODES",
                observation_filters=[("point_id", "in", _value_points(spec))])
            evidence = run_recorded_discovery_query(store, census=loaded["census"], observations=loaded["observations"],
                spec=spec, binding=binding, journal_scope=operation["journal_scope"], candidate_scope=scope, git_sha=git_sha,
                operation_sha256=operation["operation_sha256"], verified_market=operation["market_evidence_epoch_sha256"],
                repo_root=repo_root, data_root=store.root)
            note_look_landed(store, operation["operation_sha256"])
            look = next(l for l in list_discovery_looks(store, operation["journal_scope"]) if l["record_id"] in evidence["result_refs"])
            saved = _link_check(store, operation, look, git_sha=git_sha)
            return {"status": "CHECK_RECORDED", "fragment_version_id": fragment, "source_ref": saved["_record_id"],
                    "result_ref": look["record_id"], "new_look": evidence.get("new_look"), "values_loaded": True}
        except (ValueError, KeyError, TypeError, OSError, ResearchStoreError) as exc:
            reports.append({**status, "fragment_version_id": fragment, "status": "BLOCKED",
                            "reason": getattr(exc, "code", "FRAGMENT_SOURCE_INVALID"), **source_detail(exc),
                            "new_look": "UNKNOWN" if values_loaded else False, "values_loaded": values_loaded})
            if values_loaded:
                return {"status": "BLOCKED_AFTER_VALUE_ATTEMPT", "fragments": reports, "new_look": "UNKNOWN", "values_loaded": True}
    return {"status": "NO_EVALUATION", "fragments": reports, "new_look": False, "values_loaded": False}


def enrich_prior_capsules(store: Any, capsules: list[dict[str, Any]], *, as_of: datetime | str | None) -> None:
    """Typed material sources inside the ordinary bounded hypothesis capsule."""
    by_candidate = {c["hypothesis_version_id"]: c for c in capsules}
    for fragment in source_snapshot(store, as_of=as_of):
        if fragment.get("error"):
            continue
        cap = by_candidate.get(fragment["source"]["candidate_id"])
        if cap is None:
            continue
        cap["source_detail"].setdefault("research_fragments", []).append({
            k: copy.deepcopy(fragment[k]) for k in ("fragment_version_id", "title", "role", "source_ref",
                "source_sha256", "first_reliable_available_at", "allowed_use", "evidence_blocks", "check", "claim_boundary", "source_restrictions")})
