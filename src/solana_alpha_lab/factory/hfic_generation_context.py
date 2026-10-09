"""Pure bounded views over existing verified research-memory/guard owners.

This module owns selection, never eligibility, scientific closure or exposure.
Legacy full snapshots remain in hfic_prior_memory, with their original meaning.
"""
from __future__ import annotations

import json
import copy
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from solana_alpha_lab.factory.hfic_memory_policy import (
    iter_search_memory_hypothesis_payloads, research_memory_cutoff,
    research_record_visible_as_of,
)
from solana_alpha_lab.factory.hfic_prior_memory import (
    _capsule_from_payload, _fill_scope_from_session, _session_scope_index,
    latest_hypothesis_decisions, prior_memory_bounds, session_identity,
)
from solana_alpha_lab.factory.research_store import reuse_lifecycle_reads_within_packet
from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256

CONTRACT = "FORGE_EVIDENCE_GUIDED_GENERATION_V1"
REVISION = CONTRACT
SCHEMA = "smial.hfic-prior-memory-snapshot"
WORKING_VERSION = "1.1"
SCOPE_KEYS = ("population", "decision_timestamp", "target", "estimand",
              "explanatory_condition", "representation_scope", "research_scope_rule_sha256")
RECIPE_KEYS = ("field_id", "feature_id", "op", "start", "end", "point", "point_id")


class GenerationContextError(ValueError):
    def __init__(self, code: str, **detail: Any) -> None:
        self.code, self.detail = code, detail
        super().__init__(code)


def _terms(value: object) -> set[str]:
    return set(re.findall(r"[\w-]+", str(value or "").casefold()))


def structural_facets(value: Mapping[str, Any]) -> dict[str, str]:
    """Only declared typed axes. Narrative is not a machine semantic contract."""
    facets = {key: str(value[key]) for key in SCOPE_KEYS
              if isinstance(value.get(key), str) and value[key].strip()}
    for key in ("features", "list_condition", "list_scope", "research_scope", "feature_recipe",
                "temporal_recipe", "required_feature_ids"):
        item = value.get(key)
        if isinstance(item, (Mapping, list)) and item:
            facets[key] = canonical_json_bytes(item).decode("utf-8")
    for key in RECIPE_KEYS:
        if isinstance(value.get(key), str) and value[key].strip():
            facets[key] = value[key]
    return facets


def rank_structural_priors(payloads: Sequence[Mapping[str, Any]], *,
                           query: Mapping[str, Any], focus: str = "") -> list[str]:
    wanted = structural_facets(query)
    focus_terms = _terms(focus)
    groups: dict[tuple[int, int], dict[str, list[tuple[int, str]]]] = {}
    for payload in payloads:
        hyp = str(payload.get("hypothesis_version_id") or "")
        if not hyp:
            raise GenerationContextError("PRIOR_MEMORY_RECORD_UNIDENTIFIED")
        axes = structural_facets(payload)
        matches = {key for key in wanted if axes.get(key) == wanted[key]}
        structured = len(matches.intersection(set(RECIPE_KEYS) | {"features", "list_condition", "list_scope", "research_scope", "representation_scope"}))
        scope = len(matches.intersection(SCOPE_KEYS))
        words = _terms(" ".join(str(payload.get(k) or "") for k in
                               ("claim", "statement", "primary_x_family", "primary_y")))
        tier = (-structured, -scope)
        family = canonical_sha256(axes) if axes else hyp
        groups.setdefault(tier, {}).setdefault(family, []).append((-len(words & focus_terms), hyp))
    ordered: list[str] = []
    for tier in sorted(groups):
        families = sorted((sorted(ids) for ids in groups[tier].values()), key=lambda ids: ids[0])
        # Round-robin different declared structural families, then repetition.
        depth = 0
        while any(depth < len(ids) for ids in families):
            ordered.extend(ids[depth][1] for ids in families if depth < len(ids))
            depth += 1
    return ordered


@reuse_lifecycle_reads_within_packet
def collect_verified_priors(store: Any, *, as_of: str | datetime | None) -> dict[str, Any]:
    cutoff = research_memory_cutoff(as_of)
    payloads = iter_search_memory_hypothesis_payloads(store, as_of=cutoff)
    decisions = latest_hypothesis_decisions(store, as_of=cutoff)
    scopes = _session_scope_index(store, as_of=cutoff)
    sources: dict[tuple[str, str], list[dict[str, Any]]] = {}
    visible_records = [r for r in store.iter_committed_records() if research_record_visible_as_of(r, cutoff)]
    packet_sources: dict[tuple[str, str], list[tuple[Any, Mapping[str, Any]]]] = {}
    critic_sources: dict[tuple[str, str], list[dict[str, Any]]] = {}
    decision_sources: dict[tuple[str, str], list[tuple[Any, Mapping[str, Any]]]] = {}
    for record in visible_records:
        kind = str(getattr(record.record_kind, "value", record.record_kind))
        if kind == "RESEARCH_ARTIFACT":
            wrapper = json.loads(record.payload_json)
            if not isinstance(wrapper, Mapping):
                continue
            if wrapper.get("artifact_kind") in {"CRITIC_INPUT_PACKET", "CRITIC_RESULT"}:
                from solana_alpha_lab.factory.hfic_session import _load_artifact_by_sha, HficSessionError
                try:
                    _, body, _ = _load_artifact_by_sha(
                        [(dict(wrapper), wrapper.get("payload_canonical"))],
                        artifact_kind=wrapper["artifact_kind"], expected_sha=str(wrapper.get("payload_sha256") or ""),
                    )
                except HficSessionError as exc:
                    raise GenerationContextError("GENERATION_SAVED_SOURCE_INTEGRITY_FAILED", source_error=exc.code) from exc
            if wrapper.get("artifact_kind") == "CRITIC_INPUT_PACKET":
                selected = body.get("selected_candidate") or {}
                if not isinstance(selected, Mapping):
                    continue
                key = (str(body.get("session_id") or wrapper.get("session_id") or ""), str(selected.get("candidate_id") or ""))
                packet_sources.setdefault(key, []).append((record, body))
            elif wrapper.get("artifact_kind") == "CRITIC_RESULT":
                key = (str(body.get("session_id") or wrapper.get("session_id") or ""), str(body.get("selected_candidate_id") or ""))
                critic_sources.setdefault(key, []).append({"source_ref": {"record_id":record.record_id,"payload_sha256":record.payload_sha256},
                    "critic_terminal":body.get("critic_terminal"),"material_defects":body.get("material_defects") or [],
                    "next":body.get("next"), "revision_receipt":body.get("revision_receipt"),
                    "finding_authority":"MODEL_REVIEW_ONLY"})
        if kind == "DECISION_EVENT":
            body = json.loads(record.payload_json)
            key = (str(body.get("hypothesis_version_id") or record.hypothesis_version_id or ""),session_identity(body))
            decision_sources.setdefault(key, []).append((record,body))
        if kind != "HYPOTHESIS_VERSION":
            continue
        raw = json.loads(record.payload_json)
        key = (str(raw.get("hypothesis_version_id") or record.hypothesis_version_id or ""), canonical_sha256(raw))
        sources.setdefault(key, []).append({
            "record_id": record.record_id, "payload_sha256": record.payload_sha256,
            "first_reliable_available_at": record.first_reliable_available_at.isoformat(),
            "effective_at": record.effective_at.isoformat(),
        })
    capsules = []
    selection_payloads = []
    admitted_bindings: dict[str, list[dict[str, Any]]] = {}
    for payload in payloads:
        hyp = str(payload.get("hypothesis_version_id") or "")
        decision = decisions.get((hyp, session_identity(payload)))
        capsule = _capsule_from_payload(hyp, payload, decision)
        _fill_scope_from_session(capsule, payload, scopes)
        refs = sorted(sources.get((hyp, canonical_sha256(payload)), []), key=lambda r: r["record_id"])
        if not refs:
            raise GenerationContextError("GENERATION_SOURCE_BINDING_UNAVAILABLE", hypothesis_version_id=hyp)
        outcome = capsule.get("outcome_semantics") or {}
        capsule["source_detail"] = {
            "hypothesis_source_refs": refs,
            "source_outcome": capsule.get("reason_code"),
            "failure_boundary": "IMPLEMENTATION" if outcome.get("outcome_class") == "TECHNICAL_REFUSAL" else
                                "DESIGN" if str(outcome.get("outcome_class") or "").startswith("REVIEW_REJECTION") else "UNKNOWN",
            "finding": "NOT_RECORDED_IN_HYPOTHESIS_SOURCE",
            "surviving_observation": "NOT_RECORDED",
            "reconsideration_condition": "NOT_RECORDED",
            "authored_text_is_authority": False,
        }
        if decision:
            matches = [(r,b) for r,b in decision_sources.get((hyp,session_identity(payload)),[]) if b.get("reason_code")==decision.get("reason_code") and b.get("decision_kind")==decision.get("decision_kind")]
            capsule["source_detail"]["decision_source_refs"] = [{"record_id":r.record_id,"payload_sha256":r.payload_sha256,"effective_at":r.effective_at.isoformat(),"first_reliable_available_at":r.first_reliable_available_at.isoformat()} for r,_ in sorted(matches,key=lambda pair:(pair[0].effective_at,pair[0].record_id))]
        objections = critic_sources.get((session_identity(payload),hyp), [])
        if objections:
            capsule["source_detail"]["critic_objections"] = objections
        evidence = payload.get("saved_observation_evidence")
        own_packets = packet_sources.get((session_identity(payload), hyp), [])
        if not isinstance(evidence, Mapping) and own_packets:
            evidence = max(own_packets, key=lambda item: (item[0].first_reliable_available_at, item[0].effective_at, item[0].record_id))[1].get("grounded_evidence")
        selection_payload = dict(payload)
        if isinstance(evidence, Mapping):
            from solana_alpha_lab.factory.hfic_grounded_discovery import (
                GroundedDiscoveryError, assert_computed_grounded_evidence,
                descriptive_return_readout, resolve_published_episode_binding,
                resolve_published_discovery_binding,
            )
            from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_frozen_input
            population = str((evidence.get("result") or {}).get("population") or "BASE_X")
            try:
                if population not in admitted_bindings:
                    resolver = resolve_published_episode_binding if population == "OPPORTUNITY_EPISODES" else resolve_published_discovery_binding
                    data_root = store.root if hasattr(store, "root") else store._root
                    admitted_bindings[population] = temporal_frozen_input(resolver(data_root)["cohorts"])
                frozen = (evidence.get("result") or {}).get("experiment_recipe", {}).get("frozen_input")
                if not isinstance(frozen, list) or not frozen:
                    raise GroundedDiscoveryError("SAVED_RESULT_INPUT_UNVERIFIABLE")
                current = {(r["cohort_id"],r["release_id"]):r for r in admitted_bindings[population]}
                for row in frozen:
                    now = current.get((row.get("cohort_id"),row.get("release_id")))
                    # Publication manifest version may grow; the saved cohort,
                    # files, protection and schedule closure must stay exact.
                    if now is None or any(now.get(k) != v for k,v in row.items() if k != "dataset_manifest_id"):
                        raise GroundedDiscoveryError("SAVED_RESULT_INPUT_BINDING_CHANGED")
            except GroundedDiscoveryError as exc:
                raise GenerationContextError("GENERATION_SAVED_SOURCE_INADMISSIBLE", source_error=exc.code, hypothesis_version_id=hyp) from exc
            # Reuse the durable-result owner on a clock-filtered read projection.
            # No result is recomputed and no scientific slot is reserved here.
            class VisibleRead:
                def iter_committed_records(self):
                    return iter(visible_records)
            try:
                verified = assert_computed_grounded_evidence(VisibleRead(), evidence)
            except GroundedDiscoveryError as exc:
                raise GenerationContextError("GENERATION_SAVED_SOURCE_INTEGRITY_FAILED", source_error=exc.code, hypothesis_version_id=hyp) from exc
            capsule["source_detail"].update({
                "finding": descriptive_return_readout(verified["result"]),
                "saved_result_refs": list(verified["result_refs"]),
                "saved_result_sha256": verified["result_sha256"],
                "source_scope": dict(verified.get("candidate_scope") or {}),
                "finding_authority": "SAVED_DESCRIPTIVE_RESULT_ONLY",
            })
            # Saved recipes supply typed structural axes. Authored narrative
            # remains text; no recipe is reconstructed from primary_x prose.
            recipe = verified["result"].get("experiment_recipe") or {}
            scientific = (recipe.get("spec") or {}).get("scientific_body") or {}
            for key in ("features", "list_condition", "research_scope"):
                if isinstance(scientific.get(key), (Mapping, list)):
                    selection_payload[key] = scientific[key]
        capsules.append(capsule)
        selection_payloads.append(selection_payload)
    return {"payloads": payloads, "capsules": capsules,
            "selection_payloads": selection_payloads,
            "research_log_cutoff": cutoff.isoformat() if cutoff else None}


def original_working_view(store: Any, *, search_key: str) -> dict[str, Any] | None:
    """Recover the first saved context for this run, never refresh its cutoff."""
    candidates = []
    for record in store.iter_committed_records():
        if str(getattr(record.record_kind, "value", record.record_kind)) != "RESEARCH_ARTIFACT":
            continue
        wrapper = json.loads(record.payload_json)
        if not isinstance(wrapper, Mapping) or wrapper.get("artifact_kind") != "FORGE_CONTEXT_PACKET":
            continue
        raw = wrapper.get("payload_canonical")
        if not isinstance(raw, str):
            continue
        packet = json.loads(raw)
        if not isinstance(packet, Mapping) or packet.get("search_key_sha256") != search_key:
            continue
        memory = packet.get("prior_memory_working_view")
        if isinstance(memory, Mapping) and memory.get("schema_version") == WORKING_VERSION:
            if wrapper.get("payload_sha256") != canonical_sha256(packet):
                raise GenerationContextError("GENERATION_CONTEXT_RECEIPT_BINDING_MISMATCH")
            from solana_alpha_lab.factory.hfic_preflight import verify_forge_context_packet, HficPreflightError, FORGE_CONTEXT_ARTIFACT_DIR
            digest = canonical_sha256(packet)
            try:
                verify_forge_context_packet(store.root if hasattr(store, "root") else store._root, digest)
            except HficPreflightError as exc:
                raise GenerationContextError(exc.code, required_context_sha256=digest,
                    relative_locator=f"{FORGE_CONTEXT_ARTIFACT_DIR}/{digest}.json",
                    next_action="RESTORE_EXACT_SAVED_CONTEXT_DEPENDENCY") from exc
            candidates.append((record.first_reliable_available_at, record.record_id, dict(memory)))
    return min(candidates, key=lambda item: item[:2])[2] if candidates else None


def archive_fingerprint(inventory: Mapping[str, Any]) -> str:
    return canonical_sha256(sorted(inventory["capsules"], key=lambda c: c["hypothesis_version_id"]))


def reissue_working_view(original: Mapping[str, Any], inventory: Mapping[str, Any], *, inventory_digest: str) -> dict[str, Any]:
    if archive_fingerprint(inventory) != original.get("eligible_archive_sha256"):
        raise GenerationContextError("GENERATION_CONTEXT_MATERIAL_SOURCE_CHANGED")
    refreshed = copy.deepcopy(dict(original))
    refreshed["source_store_inventory_digest"] = inventory_digest
    return _seal(refreshed)


def check_full_prior_scope(inventory: Mapping[str, Any], *, evidence: Mapping[str, Any],
                          inventory_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Existing guard executes on every eligible capsule before any ranking."""
    from solana_alpha_lab.factory.hfic_grounded_discovery import bind_prior_scope_evidence
    guarded = bind_prior_scope_evidence(evidence, canonical_priors=inventory["capsules"])
    receipt = {
        "owner": "hfic_grounded_discovery.bind_prior_scope_evidence",
        "status": "PASS", "scope": "FULL_ELIGIBLE_ARCHIVE",
        "considered_count": len(inventory["capsules"]),
        "candidate_scope_sha256": canonical_sha256(evidence.get("candidate_scope") or {}),
        "source_store_inventory_digest": inventory_digest,
        "research_log_cutoff": inventory["research_log_cutoff"],
        "relations_sha256": canonical_sha256(guarded.get("prior_scope_relations") or []),
        "authority_granted": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return guarded, receipt


def _seal(body: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = {**body, "bytes": 0, "snapshot_sha256": "0" * 64}
    for _ in range(8):
        size = len(canonical_json_bytes(snapshot))
        if snapshot["bytes"] == size:
            break
        snapshot["bytes"] = size
    snapshot["snapshot_sha256"] = canonical_sha256({k: v for k, v in snapshot.items() if k != "snapshot_sha256"})
    return snapshot


def _consulted_hypothesis_ids(by_id: Mapping[str, Mapping[str, Any]],
                              consulted_refs: Sequence[str]) -> set[str]:
    ref_to_ids: dict[str, set[str]] = {}
    for hyp, cap in by_id.items():
        detail = cap["source_detail"]
        for ref in [r["record_id"] for r in detail["hypothesis_source_refs"]] + list(detail.get("saved_result_refs") or []):
            ref_to_ids.setdefault(ref, set()).add(hyp)
    required: set[str] = set()
    for ref in consulted_refs:
        if ref in by_id: required.add(ref)
        elif ref in ref_to_ids: required.update(ref_to_ids[ref])
        else: raise GenerationContextError("GENERATION_CONSULTED_SOURCE_UNAVAILABLE", source_ref=ref)
    return required


def select_working_snapshot(inventory: Mapping[str, Any], *, query: Mapping[str, Any],
                            inventory_digest: str, focus: str = "",
                            consulted_refs: Sequence[str] = (), mandatory_ids: Sequence[str] = (),
                            safety_receipt: Mapping[str, Any] | None = None,
                            max_records: int = 64, max_bytes: int = 65536,
                            parent_budget_bytes: int | None = None) -> dict[str, Any]:
    payloads = inventory.get("selection_payloads", inventory["payloads"])
    eligible_sha = archive_fingerprint(inventory)
    by_id = {c["hypothesis_version_id"]: c for c in inventory["capsules"]}
    required = set(mandatory_ids) | _consulted_hypothesis_ids(by_id, consulted_refs)
    missing = required.difference(by_id)
    if missing:
        raise GenerationContextError("GENERATION_CONSULTED_SOURCE_UNAVAILABLE", hypothesis_version_ids=sorted(missing))
    order = sorted(required) + [hyp for hyp in rank_structural_priors(payloads, query=query, focus=focus) if hyp not in required]
    selected: list[dict[str, Any]] = []
    bound = min(max_bytes, parent_budget_bytes) if parent_budget_bytes is not None else max_bytes
    def envelope():
        count = len(selected)
        body = {
            "schema": SCHEMA, "schema_version": WORKING_VERSION,
            "view_kind": "BOUNDED_WORKING_SET",
            "research_log_cutoff": inventory["research_log_cutoff"],
            "source_store_inventory_digest": inventory_digest,
            "eligible_archive_sha256": eligible_sha,
            "eligibility_policy_ref": "hfic_memory_policy.iter_search_memory_hypothesis_payloads",
            "selection_policy_revision": REVISION,
            "selection_query": {"query": dict(query), "focus": focus, "consulted_refs": sorted(consulted_refs)},
            "selection_query_sha256": canonical_sha256({"query": query, "focus": focus, "consulted_refs": sorted(consulted_refs)}),
            "candidate_scope_ref": (safety_receipt or {}).get("candidate_scope_sha256"),
            "archive_eligible_count": len(by_id), "considered_count": len(by_id),
            "emitted_count": count, "omitted_count": len(by_id)-count,
            "mandatory_count": len(required), "selection_complete": True,
            "archive_complete_in_packet": count == len(by_id),
            "safety_check_receipt_ref": (safety_receipt or {}).get("receipt_sha256"),
            "consulted_source_refs": sorted(set(consulted_refs)),
            "omission_summary": {"reason": "OPTIONAL_WORKING_SET_BOUND", "count": len(by_id)-count},
            "exact_detail_locator": {"command": "prior", "mode": "context-view", "selection_query_sha256": canonical_sha256({"query": query, "focus": focus, "consulted_refs": sorted(consulted_refs)})},
            "capsules": selected, "max_records": max_records, "max_bytes": max_bytes,
        }
        return _seal(body)
    current = envelope()
    if len(required) > max_records or current["bytes"] > bound:
        raise GenerationContextError("GENERATION_MANDATORY_CONTEXT_EXCEEDS_BOUND", mandatory_count=len(required), max_records=max_records, max_bytes=bound)
    for hyp in order:
        if len(selected) == max_records:
            break
        item = {**by_id[hyp], "selection_reason": "MANDATORY_SOURCE_REF" if hyp in required else "STRUCTURAL_DIVERSITY_THEN_TEXT"}
        # Reject clearly oversized optional entries without repeatedly encoding
        # the already full working set for every archive entry.
        if hyp not in required and selected and current["bytes"] + len(canonical_json_bytes(item)) > bound + 32:
            continue
        selected.append(item)
        trial = envelope()
        if len(selected) > max_records or trial["bytes"] > bound:
            selected.pop()
            if hyp in required:
                raise GenerationContextError("GENERATION_MANDATORY_CONTEXT_EXCEEDS_BOUND", mandatory_count=len(required), max_records=max_records, max_bytes=bound)
        else:
            current = trial
    return current


def generation_brief(*, memory: Mapping[str, Any], safety: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "contract": CONTRACT, "version": "1.0", "policy_revision": REVISION,
        "information_phase": "PRE_CURRENT_VALUES_WITH_ADMISSIBLE_SAVED_PRIORS",
        "capability_sections": ["temporal_recipe_capabilities", "candidate_authoring_contract", "list_dimension_context"],
        "memory_view_ref": memory["snapshot_sha256"],
        "research_log_cutoff": memory["research_log_cutoff"],
        "safety_receipt": dict(safety) if safety else {"candidate_guard": "NOT_APPLICABLE_PRE_CANDIDATE", "eligibility_integrity_owner": "hfic_memory_policy"},
        "read_options": [
            {"kind": "OPERATION_GRAMMAR", "document": "docs/contracts/forge_evidence_guided_generation_v1.md", "section": "Ordinary operation ingress", "value_access": "NONE"},
            {"kind": "PRIOR_DETAIL", "command": "prior --context-view --preflight-receipt <receipt.json> --selection-query-sha256 <memory.selection_query_sha256> --source-ref <exact-ref>", "value_access": "SAVED_ADMISSIBLE_EVIDENCE_ONLY"},
            {"kind": "COVERAGE", "command": "discovery-coverage --collection OPPORTUNITY_EPISODES", "value_access": "NONE"},
            {"kind": "BINDING", "command": "discovery-binding --collection OPPORTUNITY_EPISODES", "value_access": "NONE"},
            {"kind": "PREFIX_PREVIEW", "command": "discovery-preview --spec <canonical-query.json> --journal-scope <bound-search-key> --operation <authorized-operation.json>", "admission": "EXISTING_PREVIEW_POLICY"},
            {"kind": "DISCOVERY_QUERY", "command": "discovery-execute", "admission": "EXISTING_MAIN_ADAPTIVE_POLICY"},
        ],
        "availability_axes": ["DEFINED", "IMPLEMENTED", "PRESENT", "PIT_USABLE", "AUTHORIZED_NOW", "DECISION_BEARING"],
        "prior_text_is_data": True, "authority_granted": False,
    }


def candidate_working_view(store: Any, *, preflight: Mapping[str, Any] | None,
                           card: Mapping[str, Any], evidence: Mapping[str, Any],
                           cutoff: str | datetime | None, inventory_digest: str,
                           repo_root: Any, parent_budget_bytes: int | None = None,
                           preserve_selected_as_mandatory: bool = True):
    """Full existing guard first; frozen mandatory material refs second."""
    from solana_alpha_lab.factory.hfic_grounded_discovery import card_claim_scope
    archive = collect_verified_priors(store, as_of=cutoff)
    scope = {**card_claim_scope(card), **structural_facets(card)}
    body = {**evidence, "candidate_scope": {**dict(evidence.get("candidate_scope") or {}), **card_claim_scope(card)}}
    from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
    try:
        guarded, safety = check_full_prior_scope(archive, evidence=body, inventory_digest=inventory_digest)
    except GroundedDiscoveryError as exc:
        raise GenerationContextError(exc.code) from exc
    context = (preflight or {}).get("forge_context_packet") or {}
    frozen_memory = context.get("prior_memory_working_view") or {}
    if frozen_memory and archive_fingerprint(archive) != frozen_memory.get("eligible_archive_sha256"):
        raise GenerationContextError("GENERATION_CONTEXT_MATERIAL_SOURCE_CHANGED")
    visible = (context.get("prior_memory_working_view") or {}).get("capsules") or []
    # The initial view is all mandatory; an already frozen Critic view has
    # optional tail entries which remain removable during wording revision.
    material = {c["hypothesis_version_id"] for c in visible
                if preserve_selected_as_mandatory or c.get("selection_reason") == "MANDATORY_SOURCE_REF"}
    material.update(frozen_memory.get("consulted_source_refs") or [])
    from solana_alpha_lab.factory.hfic_grounded_discovery import _valid_close
    relation_by_id = {r.get("hypothesis_version_id"): r.get("relation") for r in guarded.get("prior_scope_relations") or []}
    for cap in archive["capsules"]:
        # These are restrictions already typed by the guard owner. A shared
        # field in narrative is never enough to create a material restriction.
        if relation_by_id.get(cap["hypothesis_version_id"]) == "SCOPED_CONTROL_DOES_NOT_BLOCK" or (
            _valid_close(cap) and all(scope.get(axis) and scope.get(axis) == cap.get(axis) for axis in ("population", "decision_timestamp", "target"))
        ):
            material.add(cap["hypothesis_version_id"])
    known_refs = {c["hypothesis_version_id"] for c in archive["capsules"]}
    known_refs.update(r["record_id"] for c in archive["capsules"] for r in c["source_detail"]["hypothesis_source_refs"])
    known_refs.update(r for c in archive["capsules"] for r in c["source_detail"].get("saved_result_refs") or [])
    for ref in card.get("prior_work_refs") or []:
        if ref in known_refs or str(ref).startswith(("HYP-", "REC-", "HFIC-ART-")):
            material.add(ref)
    records_bound, bytes_bound = prior_memory_bounds(repo_root)
    view = select_working_snapshot(archive, query=scope, focus=str(card.get("claim") or ""),
                                  inventory_digest=inventory_digest, consulted_refs=sorted(material),
                                  safety_receipt=safety, max_records=records_bound, max_bytes=bytes_bound,
                                  parent_budget_bytes=parent_budget_bytes)
    chosen = {c["hypothesis_version_id"] for c in view["capsules"]}
    guarded["prior_scope_relations"] = [r for r in guarded.get("prior_scope_relations") or [] if r.get("hypothesis_version_id") in chosen]
    brief = generation_brief(memory=view, safety=safety)
    brief["information_phase"] = "AFTER_CURRENT_ADMITTED_LOOK" if evidence.get("result_refs") and evidence.get("look_confirms_selected") is not False else "PRE_CURRENT_VALUES_WITH_ADMISSIBLE_SAVED_PRIORS"
    return guarded, view, brief


def read_context_view(store: Any, *, receipt: Mapping[str, Any], query_sha256: str,
                      source_ref: str | None = None) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_session import canonical_preflight_receipt_sha256, _verify_required_context_dependency, HficSessionError
    if receipt.get("preflight_receipt_sha256") != canonical_preflight_receipt_sha256(receipt):
        raise GenerationContextError("GENERATION_CONTEXT_RECEIPT_BINDING_MISMATCH")
    memory = ((receipt.get("forge_context_packet") or {}).get("prior_memory_working_view") or {})
    if memory.get("schema_version") != WORKING_VERSION or query_sha256 != memory.get("selection_query_sha256"):
        raise GenerationContextError("GENERATION_CONTEXT_QUERY_BINDING_MISMATCH")
    from solana_alpha_lab.factory.research_store import ResearchStore
    data_root = store.root if hasattr(store, "root") else store._root
    active = ResearchStore(data_root, create_if_missing=False)
    try:
        _verify_required_context_dependency(active, receipt)
    except HficSessionError as exc:
        raise GenerationContextError(exc.code, **exc.detail) from exc
    digest = active.diagnostics().committed_inventory_sha256
    # Context is appended after its source view is built. The receipt owns the
    # post-append inventory; the view records the pre-append source inventory.
    if digest != receipt.get("store_inventory_digest"):
        raise GenerationContextError("GENERATION_CONTEXT_STALE_STORE_BINDING")
    archive = collect_verified_priors(store, as_of=memory["research_log_cutoff"])
    if archive_fingerprint(archive) != memory.get("eligible_archive_sha256"):
        raise GenerationContextError("GENERATION_CONTEXT_MATERIAL_SOURCE_CHANGED")
    descriptor = memory["selection_query"]
    detail_bound = 8
    if source_ref:
        # A saved result can be cited by several hypotheses. Keep its entire
        # mandatory source closure, without unrelated optional entries or a
        # higher global count/byte cap. Oversized closure still fails closed.
        by_id = {cap["hypothesis_version_id"]: cap for cap in archive["capsules"]}
        detail_bound = min(64, len(_consulted_hypothesis_ids(by_id, [source_ref])))
    chosen = select_working_snapshot(archive, query=descriptor["query"], focus=descriptor["focus"], inventory_digest=digest,
                                    consulted_refs=[source_ref] if source_ref else [], max_records=detail_bound)
    return {"schema": "smial.generation-context-detail", "status": "READ_ONLY",
            "bound_selection_query_sha256": query_sha256,
            "source_preflight_receipt_sha256": receipt["preflight_receipt_sha256"],
            "consulted_source_refs": chosen["consulted_source_refs"],
            "saved_admissible_evidence_only": True, "new_look": False,
            "view": chosen, "authority_granted": False}


def fit_working_packet(packet: Mapping[str, Any], *, max_bytes: int = 65536) -> dict[str, Any]:
    """Drop only optional tail entries against the complete serialized parent."""
    result = copy.deepcopy(dict(packet))
    while len(canonical_json_bytes(result)) > max_bytes:
        memory = result["prior_memory"]
        capsules = memory["capsules"]
        removable = [i for i,c in enumerate(capsules) if c["selection_reason"] != "MANDATORY_SOURCE_REF"]
        if not removable:
            raise GenerationContextError("GENERATION_MANDATORY_CONTEXT_EXCEEDS_BOUND", mandatory_count=memory["mandatory_count"], packet_bytes=len(canonical_json_bytes(result)), max_bytes=max_bytes)
        capsules.pop(removable[-1])
        memory.update(emitted_count=len(capsules), omitted_count=memory["archive_eligible_count"]-len(capsules), archive_complete_in_packet=False)
        memory["omission_summary"] = {"reason":"OPTIONAL_PARENT_PACKET_BOUND", "count":memory["omitted_count"]}
        memory = _seal(memory)
        result["prior_memory"] = memory
        result["generation_context"]["memory_view_ref"] = memory["snapshot_sha256"]
        chosen = {c["hypothesis_version_id"] for c in capsules}
        grounded = result.get("grounded_evidence")
        if isinstance(grounded, dict):
            grounded["prior_scope_relations"] = [r for r in grounded.get("prior_scope_relations") or [] if r.get("hypothesis_version_id") in chosen]
    return result
