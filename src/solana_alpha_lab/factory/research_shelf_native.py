"""Narrow read-only adapters and exact shelf/native/strategy relations.

Imports native owners lazily. No evaluator, runner, reservation, Git transport,
promotion or write API is called here. Missing lineage remains an explicit gap.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime
from typing import Any, Callable, Mapping

from . import research_shelf as wire

RISK_FIELDS = ("confounders", "pit_leakage_survivorship_risks", "execution_capacity_risks", "missing_or_forward_only_data")


class _SavedRead:
    """One metadata read set; expose the legacy root alias to existing readers."""
    def __init__(self, store: Any):
        wire.require(store is not None and hasattr(store, "root"), "NATIVE_SOURCE_UNAVAILABLE")
        self.root = store.root
        self._root = self.root  # Existing frozen-context reader's compatibility seam.
        self.records = tuple(store.iter_committed_records())

    def iter_committed_records(self):
        return iter(self.records)


def _saved_read(store: Any) -> _SavedRead:
    return store if isinstance(store, _SavedRead) else _SavedRead(store)


def _utc(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    wire.require(parsed.tzinfo is not None, "NATIVE_CLOCK_INVALID")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def record_ref(record: Any) -> dict[str, Any]:
    return dict(kind="NATIVE", owner="SMIAL", entity_kind=str(getattr(record.record_kind, "value", record.record_kind)),
                entity_id=record.record_id, payload_sha256=record.payload_sha256,
                locator="smial-data://research/records/" + record.record_id)


def record_index(store: Any) -> dict[str, tuple[Any, dict[str, Any]]]:
    result = {}
    for record in store.iter_committed_records():
        wire.require(wire.sha256(record.payload_json.encode("utf-8")) == record.payload_sha256, "NATIVE_RECORD_HASH_MISMATCH")
        payload = json.loads(record.payload_json)
        wire.require(isinstance(payload, dict), "NATIVE_RECORD_INVALID")
        wire.require(record.record_id not in result, "AMBIGUOUS_NATIVE_RECORD")
        result[record.record_id] = record, payload
    return result


def event_read(event: Mapping[str, Any], *, now: str, store: Any = None,
               saved_sources: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Two source owners only: SMIAL saved fragment view and Scout saved status."""
    unknown = dict(status="UNKNOWN", as_of=now, evidence_ref=None, reason="SOURCE_UNAVAILABLE")
    source = event.get("source")
    if event.get("kind") == "MANUAL" or not isinstance(source, dict):
        return dict(unknown, reason="MANUAL_OR_UNSUPPORTED_EVENT")
    try:
        if source.get("kind") == "NATIVE_ENTITY" and source.get("owner") == "SMIAL" and source.get("entity_kind") == "RESEARCH_FRAGMENT":
            if store is None:
                return unknown
            from . import research_fragments as fragments
            store = _saved_read(store)
            views = [v for v in fragments.source_snapshot(store, now=wire.clock(now))
                     if v["fragment_version_id"] == source["entity_id"]]
            if len(views) != 1 or views[0].get("error"):
                return dict(unknown, reason="FRAGMENT_SOURCE_UNAVAILABLE")
            view = views[0]
            state = view["check"]
            if state["status"] == "BLOCKED":
                return dict(unknown, reason=state.get("reason", "FRAGMENT_SOURCE_UNAVAILABLE"))
            plan = view.get("plan") or {}
            # A CHECK alone is not the identity of a current PLAN projection.
            # This rebuildable metadata reference covers every contributing
            # saved ref and the native owner's derived state (including spend).
            records = record_index(store)
            ids = {view["source_ref"]} | {b["source_ref"] for b in view["evidence_blocks"] if b.get("source_ref")}
            if plan.get("_record_id"):
                ids.add(plan["_record_id"])
            source_refs = sorted((record_ref(records[key][0]) for key in ids), key=wire.canonical)
            basis = dict(source_refs=source_refs, native_check=state, execution_deadline=plan.get("execution_deadline"))
            digest = wire.sha256(wire.canonical(basis))
            observed_at = max(records[key][0].first_reliable_available_at for key in ids)
            evidence = dict(kind="REFERENCE", locator="smial-shelf://fragment-state/" + digest,
                description="Derived fragment/plan/check baseline; not a native artifact or scientific evidence.",
                observed_at=_utc(observed_at.isoformat()), verification="VERIFIED")
            observed = dict(native_status=state["status"], native_reason=state.get("reason"),
                execution_deadline=_utc(plan.get("execution_deadline")), native_next_action=copy.deepcopy(state.get("attempts_without_result", [])),
                source_refs=source_refs, source_state_sha256=digest)
            supported = {"DISABLED", "DUE", "FUTURE_WAIT", "COMPLETE", "EXPIRED"}
        elif source.get("kind") == "GIT_PATH" and source.get("repository") == "lancerbeta/marcopolo-scout":
            supplied = (saved_sources or {}).get(wire.canonical(source).decode("utf-8"))
            if not isinstance(supplied, dict):
                return dict(unknown, reason="SCOUT_SAVED_SOURCE_UNAVAILABLE")
            if not isinstance(source.get("ref"), str) or not re.fullmatch(r"[0-9a-f]{40}", source["ref"]):
                return dict(unknown, reason="SCOUT_MOVING_REF_OBSERVATION_REQUIRED")
            wire.require(isinstance(supplied.get("raw"), str) and isinstance(supplied.get("evidence_ref"), dict),
                         "SCOUT_SOURCE_BUNDLE_INVALID")
            evidence, raw = supplied["evidence_ref"], supplied["raw"].encode("utf-8")
            wire.require(evidence["kind"] == "GIT" and evidence["repository"] == source["repository"]
                and evidence["path"] == source["path"] and evidence["sha256"] == wire.sha256(raw)
                and isinstance(evidence.get("commit"), str) and re.fullmatch(r"[0-9a-f]{40}", evidence["commit"]),
                "SCOUT_SOURCE_BINDING_MISMATCH")
            # A source selector may move; only this immutable Git ref is evidence.
            wire.require(source["ref"] == evidence["commit"], "SCOUT_SOURCE_BINDING_MISMATCH")
            payload = json.loads(raw)
            wire.require(isinstance(payload, dict), "SCOUT_SOURCE_PAYLOAD_INVALID")
            if payload.get("schema") != "marcopolo.concurrent-choice-feasibility":
                return dict(unknown, reason="UNSUPPORTED_SCOUT_SAVED_STATUS")
            observed = dict(native_status=payload.get("status"), native_reason="SAVED_PREFIX_FEASIBILITY_ONLY",
                            execution_deadline=None, native_next_action=None)
            supported = {"PASS", "DATA_LIMITED"}
        else:
            return dict(unknown, reason="UNSUPPORTED_SOURCE_ADAPTER")
        if observed["native_status"] not in supported:
            return dict(unknown, **observed, reason="UNSUPPORTED_SAVED_STATUS")
        if event["kind"] == "SOURCE_CHANGED":
            baseline = event.get("acknowledged_ref")
            if baseline is None:
                return dict(unknown, **observed, evidence_ref=evidence, reason="SOURCE_BASELINE_REQUIRED")
            met = evidence != baseline
        elif event["kind"] == "NATIVE_STATUS" and event.get("condition") in supported:
            met = observed["native_status"] == event["condition"]
        else:
            return dict(unknown, **observed, reason="UNSUPPORTED_CONDITION")
        return dict(status="MET" if met else "NOT_MET", as_of=now, evidence_ref=evidence,
                    reason="SAVED_SOURCE_READBACK", **observed)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError):
        return dict(unknown, reason="SOURCE_READBACK_INVALID")


def read_events(snapshot: Mapping[str, Any], *, now: str, store: Any = None,
                saved_sources: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {item_id: dict(event_read(row["current"]["review"]["event"], now=now, store=store, saved_sources=saved_sources),
                         item_revision_sha256=row["current"]["revision_sha256"],
                         event_sha256=wire.sha256(wire.canonical(row["current"]["review"]["event"])))
            for item_id, row in snapshot["items"].items() if row["current"] and row["current"]["state"] != "CLOSED"
            and row["current"]["review"]["event"] is not None}


def native_dossier(store: Any, identity: Mapping[str, Any]) -> dict[str, Any]:
    from .hfic_session import load_session_bundle
    from .research_fragments import source_evidence
    store = _saved_read(store)
    session, candidate, definition = (identity.get(k) for k in ("session_id", "candidate_id", "definition_sha256"))
    wire.require(all(isinstance(v, str) and v for v in (session, candidate, definition)), "EXACT_NATIVE_IDENTITY_REQUIRED")
    identity = dict(session_id=session, candidate_id=candidate, definition_sha256=definition)
    bundle = load_session_bundle(store, session)
    wire.require(bundle is not None, "NATIVE_SESSION_UNAVAILABLE")
    wire.require((bundle.get("selected_candidate_id"), bundle.get("selected_definition_sha256")) == (candidate, definition),
                 "NATIVE_IDENTITY_MISMATCH")
    packet = bundle.get("critic_input_packet") or {}
    grounded = packet.get("grounded_evidence") or {}
    refs, gaps, artifacts = [], [], []
    records = record_index(store)
    hypotheses = [record_ref(r) for r, p in records.values() if str(getattr(r.record_kind, "value", r.record_kind)) == "HYPOTHESIS_VERSION"
                  and p.get("session_id") == session and p.get("hypothesis_version_id") == candidate and p.get("definition_sha256") == definition]
    if len(hypotheses) != 1:
        gaps.append("EXACT_HYPOTHESIS_VERSION_RECORD_UNRESOLVED")
    refs.extend(hypotheses)
    required_artifacts = {"CRITIC_INPUT_PACKET": bundle.get("critic_input_packet_sha256"), "CRITIC_RESULT": bundle.get("critic_result_sha256")}
    for record, payload in records.values():
        if payload.get("session_id") != session or "payload_canonical" not in payload:
            continue
        kind = payload.get("artifact_kind")
        if kind == "FORGE_DRAFT" or (kind in required_artifacts and payload.get("payload_sha256") == required_artifacts[kind]):
            wire.require(wire.sha256(payload["payload_canonical"].encode("utf-8")) == payload["payload_sha256"], "NATIVE_ARTIFACT_HASH_MISMATCH")
            ref = record_ref(record)
            refs.append(ref)
            artifacts.append(dict(artifact_kind=kind, artifact_sha256=payload["payload_sha256"], record_ref=ref))
    for kind in ("FORGE_DRAFT", "CRITIC_INPUT_PACKET", "CRITIC_RESULT"):
        if not any(a["artifact_kind"] == kind for a in artifacts):
            gaps.append(kind + "_UNAVAILABLE")
    if bundle.get("session_state") != "SYNTHESIS_COMPLETE":
        gaps.append("NATIVE_SESSION_NOT_COMPLETE")
    result_refs = grounded.get("result_refs") or []
    evidence = None
    if len(result_refs) == 1 and grounded.get("result_sha256"):
        exact = dict(session_id=session, candidate_id=candidate, definition_sha256=definition,
                     result_ref=result_refs[0], result_sha256=grounded["result_sha256"])
        evidence = source_evidence(store, exact)
        wire.require(result_refs[0] in records, "SAVED_RESULT_RECORD_UNAVAILABLE")
        refs.append(record_ref(records[result_refs[0]][0]))
    else:
        gaps.append("EXACT_GROUNDED_RESULT_UNAVAILABLE")
    source_definition = copy.deepcopy(packet.get("selected_candidate"))
    return dict(status="COMPLETE_SOURCE_TRACE" if not gaps else "PARTIAL", identity=dict(identity),
        source_definition=source_definition, source_restrictions={k: copy.deepcopy((source_definition or {}).get(k)) for k in RISK_FIELDS},
        prior_memory=copy.deepcopy(packet.get("prior_memory")), known_unknowns=copy.deepcopy(packet.get("known_unknowns")),
        artifacts=artifacts, destination_refs=sorted(refs, key=wire.canonical), candidate_record_refs=hypotheses,
        critic_terminal=bundle.get("critic_terminal"), critic_result_sha256=bundle.get("critic_result_sha256"),
        critic_input_packet_sha256=bundle.get("critic_input_packet_sha256"),
        market_evidence_epoch_sha256=bundle.get("market_evidence_epoch_sha256"),
        grounded_result_sha256=grounded.get("result_sha256"), grounded_result_refs=result_refs,
        grounded_result=copy.deepcopy((evidence or {}).get("evidence", {}).get("result")),
        grounded_evidence=copy.deepcopy((evidence or {}).get("evidence")),
        availability_gaps=copy.deepcopy((evidence or {}).get("availability_gap", [])), gaps=gaps,
        scientific_admission="SOURCE_OWNED_NOT_GRANTED_BY_LINK")


def adoption_key(item_id: str, revision: str, *, owner: str, route: str, request_id: str) -> str:
    wire.require(bool(request_id), "STABLE_REQUEST_ID_REQUIRED")
    return wire.sha256(wire.canonical(dict(item_id=item_id, adopted_revision=revision,
        destination_owner=owner, destination_route=route, request_id=request_id)))


def adopted_ref(snapshot: Mapping[str, Any], item_id: str, revision: str) -> dict[str, Any]:
    wire.require(snapshot.get("complete") and snapshot.get("commit"), "PINNED_COMPLETE_SNAPSHOT_REQUIRED")
    row = snapshot["items"].get(item_id)
    wire.require(row is not None and revision in row["revisions"], "ADOPTED_REVISION_UNAVAILABLE")
    body = row["revisions"][revision]
    return dict(kind="GIT", repository="lancerbeta/solana-alpha-lab", commit=snapshot["commit"],
                path=wire.revision_path(body), sha256=wire.sha256(wire.canonical(body) + b"\n"))


def prepare_link(snapshot: Mapping[str, Any], item_id: str, revision: str, *, store: Any,
                 identity: Mapping[str, Any], request_id: str, now: str, mutation_id: str) -> dict[str, Any]:
    """Recover/save a metadata relation using an already-existing exact native target."""
    adopted = adopted_ref(snapshot, item_id, revision)
    key = adoption_key(item_id, revision, owner="SMIAL", route="HFIC", request_id=request_id)
    try:
        dossier = native_dossier(store, identity)
    except (ValueError, OSError, RuntimeError) as error:
        return dict(status="LINK_PENDING", adoption_key=key, prepared=None, missing_identity=dict(identity),
                    reason=getattr(error, "code", "NATIVE_TARGET_READBACK_UNAVAILABLE"), next_action="READ_EXACT_SAVED_NATIVE_TARGET")
    wire.require(bool(dossier["destination_refs"]), "LINK_PENDING_NATIVE_IDENTITY_UNAVAILABLE")
    wire.require(len(dossier["candidate_record_refs"]) == 1, "LINK_PENDING_NATIVE_CANDIDATE_UNAVAILABLE")
    link = dict(relation="INSPIRED_BY", adopted_item_revision=adopted, destination_refs=dossier["destination_refs"],
                adoption_key=key, verification="VERIFIED" if not dossier["gaps"] else "PARTIAL", gaps=dossier["gaps"])
    current = snapshot["items"][item_id]["current"]
    wire.require(current is not None, "ITEM_NOT_WRITABLE")
    existing = [l for l in current["native_links"] if l["adoption_key"] == key]
    links = current["native_links"] + [link]
    if existing:
        # Commit in the original adopted ref stays fixed across later shelf commits.
        link["adopted_item_revision"] = existing[0]["adopted_item_revision"]
        wire.require(len(existing) == 1, "ADOPTION_KEY_CONFLICT")
        old = existing[0]
        if old == link:
            return dict(status="ALREADY_LINKED", adoption_key=key, prepared=None, dossier=dossier)
        old_refs, new_refs = ({wire.canonical(r) for r in row["destination_refs"]} for row in (old, link))
        wire.require(old["verification"] == "PARTIAL" and old_refs <= new_refs and
            set(link["gaps"]) <= set(old["gaps"]) and
            wire.canonical(dossier["candidate_record_refs"][0]) in old_refs, "ADOPTION_KEY_CONFLICT")
        links = [link if row["adoption_key"] == key else row for row in current["native_links"]]
    raw = wire.revise(snapshot, item_id, dict(state=current["state"] if existing else "FOLLOWING", native_links=links,
        change_reason="Link exact existing native evidence; no research execution."), now=now, mutation_id=mutation_id)
    return dict(status="PREPARED_LOCAL_ONLY", adoption_key=key, prepared=raw, dossier=dossier)


def find_native(snapshot: Mapping[str, Any], native_ref: Mapping[str, Any]) -> dict[str, Any]:
    """Historical lookup includes CLOSED items and explicitly retracted relations."""
    groups = {}
    for item_id, row in snapshot["items"].items():
        for revision in row["revisions"].values():
            for link in revision["native_links"]:
                if not any(all(ref.get(k) == native_ref.get(k) for k in ("owner", "entity_kind", "entity_id", "payload_sha256"))
                           for ref in link["destination_refs"]):
                    continue
                targets = sorted((ref for ref in link["destination_refs"] if ref.get("kind") == "NATIVE"
                    and ref.get("entity_kind") == "HYPOTHESIS_VERSION"), key=wire.canonical)
                association = (dict(adoption_key=link["adoption_key"], adopted=link["adopted_item_revision"],
                    relation=link["relation"], targets=targets) if link["adoption_key"] and targets else link)
                key = wire.canonical(dict(item_id=item_id, association=association))
                group = groups.setdefault(key, dict(item_id=item_id, versions={}, active={}, row_status=row["status"],
                    has_current=row["current"] is not None))
                version = wire.canonical(link)
                group["versions"][version] = link
                if row["current"] is not None and link in row["current"]["native_links"]:
                    group["active"][version] = link
    values = []
    for key in sorted(groups):
        group = groups[key]
        active = list(group["active"].values())
        history = [copy.deepcopy(link) for version, link in sorted(group["versions"].items()) if version not in group["active"]]
        status = ("AMBIGUOUS_SOURCE_LINK" if len(active) > 1 else "CURRENT_SOURCE_LINK" if active else
                  "RETRACTED_SOURCE_LINK" if group["has_current"] else group["row_status"])
        values.append(dict(item_id=group["item_id"], status=status, relation=copy.deepcopy(active[0]) if len(active) == 1 else
            copy.deepcopy(next(iter(group["versions"].values()))) if len(group["versions"]) == 1 else None,
            historical_relations=history))
    return dict(status="INCOMPLETE" if not snapshot["complete"] else "AMBIGUOUS_SOURCE_LINK" if
                sum(row["status"] == "CURRENT_SOURCE_LINK" for row in values) > 1 or
                any(row["status"] not in {"CURRENT_SOURCE_LINK", "RETRACTED_SOURCE_LINK"} for row in values) else
                "FOUND" if values else "UNRESOLVED", matches=values, reason=snapshot.get("reason"),
                snapshot_commit=snapshot.get("commit"), source_freshness=snapshot.get("source_freshness"))


def resolve_item(snapshot: Mapping[str, Any], item_id: str, *, git_read: Callable[[dict], bytes] | None = None) -> dict[str, Any]:
    if not snapshot["complete"]:
        return dict(status=snapshot["status"] if snapshot["status"] in {"UNAVAILABLE", "NOT_INITIALIZED"} else "INCOMPLETE",
            reason=snapshot.get("reason"), item_id=item_id, adopted_sources=[], gaps=["SHELF_SNAPSHOT_INCOMPLETE"],
            next_action="REFRESH_SEPARATE_METADATA_CACHE_THEN_READ_PINNED_SNAPSHOT")
    row = snapshot["items"].get(item_id)
    wire.require(row is not None, "ITEM_NOT_FOUND")
    result = dict(status=row["status"], item_id=item_id, current=copy.deepcopy(row["current"]), adopted_sources=[], gaps=[])
    if row["current"] is None:
        return result
    for link in row["current"]["native_links"]:
        ref = link["adopted_item_revision"]
        try:
            wire.require(ref["repository"] == "lancerbeta/solana-alpha-lab" and git_read is not None, "ADOPTED_COMMIT_READBACK_REQUIRED")
            raw = git_read(ref)
            wire.require(wire.sha256(raw) == ref["sha256"], "ADOPTED_FILE_HASH_MISMATCH")
            adopted = wire.decode(raw)
            wire.require(adopted["item_id"] == item_id and wire.revision_path(adopted) == ref["path"], "ADOPTED_IDENTITY_MISMATCH")
            result["adopted_sources"].append(dict(ref=copy.deepcopy(ref), revision=adopted, relation=copy.deepcopy(link)))
        except (ValueError, KeyError, OSError):
            result["gaps"].append("ADOPTED_SOURCE_UNRESOLVED")
    result["status"] = "UNRESOLVED" if result["gaps"] or not snapshot["complete"] else "RESOLVED"
    return result


def resolve_strategy(snapshot: Mapping[str, Any], strategy: Mapping[str, Any], *, store: Any, root: Any,
                     git_read: Callable[[dict], bytes] | None = None) -> dict[str, Any]:
    """Exact StrategyVersion decision -> direct passport -> native candidate -> shelf."""
    from .promotion_handoff import validate_promotion_handoff_manifest, verify_strategy_version
    from .experiment_spec import load_experiment_spec, spec_sha256
    from .run_passport import validate_run_passport, experiment_spec_sha256
    result = dict(status="UNRESOLVED", gaps=[], strategy_source_decision=strategy.get("source_decision_asset_id"),
                  scientific_admission="SOURCE_OWNED_NOT_GRANTED_BY_SHELF")
    try:
        store = _saved_read(store)
        records = record_index(store)
        decision_id = strategy.get("source_decision_asset_id")
        candidates = [(r, p) for r, p in records.values() if str(getattr(r.record_kind, "value", r.record_kind)) == "DECISION_EVENT"
                      and (r.record_id == decision_id or p.get("decision_event_id") == decision_id)]
        wire.require(len(candidates) == 1, "EXACT_STRATEGY_DECISION_UNAVAILABLE")
        decision, payload = candidates[0]
        wire.require(payload.get("decision_kind") == "PROMOTE", "STRATEGY_SOURCE_NOT_PROMOTE")
        manifest = validate_promotion_handoff_manifest(payload["promotion_handoff_manifest"], root=root)
        verify_strategy_version(root, strategy, manifest=manifest, decision_event_id=decision_id,
                                execution_evidence_binding=payload.get("execution_evidence_binding"))
        wire.require(str(manifest["decision_effective_at"]).replace("Z", "+00:00") == decision.effective_at.isoformat(), "DECISION_CLOCK_MISMATCH")
        spec_path = manifest["experiment_spec_source_value"]
        wire.require(wire.relative_path(spec_path), "EXPERIMENT_SPEC_PATH_UNSAFE")
        wire.require(spec_sha256(root, spec_path) == manifest["experiment_spec_sha256"], "EXPERIMENT_SPEC_HASH_MISMATCH")
        spec = load_experiment_spec(root, spec_path)
        wire.require(spec.get("experiment_id") == manifest["experiment_id"] and
                     spec.get("hypothesis_version") == manifest["hypothesis_version_id"] and
                     spec.get("population") == manifest["population_ref"], "SPEC_MANIFEST_IDENTITY_MISMATCH")
        passports = []
        for ref in manifest["direct_evidence"]:
            wire.require(ref["record_id"] in records, "DIRECT_EVIDENCE_UNAVAILABLE")
            record, saved = records[ref["record_id"]]
            wire.require(record.payload_sha256 == ref["payload_sha256"], "DIRECT_EVIDENCE_HASH_MISMATCH")
            if str(getattr(record.record_kind, "value", record.record_kind)) == "RUN_COMPLETED" and saved.get("source_lineage"):
                passport = validate_run_passport({k: v for k, v in saved.items() if k != "git_mutation_count"}).model_dump(mode="json")
                # Native passports hash canonical scientific content; the
                # promotion manifest separately pins the original file bytes.
                wire.require(passport["experiment_spec_sha256"] == experiment_spec_sha256(spec) and
                             passport["experiment_id"] == manifest["experiment_id"] and
                             passport["hypothesis_version_id"] == manifest["hypothesis_version_id"], "PASSPORT_SPEC_MISMATCH")
                passports.append((record, passport))
        wire.require(len(passports) == 1, "LEGACY_OR_AMBIGUOUS_PASSPORT_LINEAGE")
        record, passport = passports[0]
        lineage = passport["source_lineage"]
        wire.require(lineage["execution_kind"] == "FROZEN_EVIDENCE_REPLAY" and lineage["new_scientific_look"] is False,
                     "UNSUPPORTED_PASSPORT_LINEAGE")
        identity = {k: lineage[k] for k in ("session_id", "candidate_id", "definition_sha256")}
        dossier = native_dossier(store, identity)
        wire.require(passport["hypothesis_definition_sha256"] == identity["definition_sha256"], "PASSPORT_DEFINITION_MISMATCH")
        for key in ("critic_input_packet_sha256", "critic_result_sha256", "grounded_result_sha256"):
            wire.require(lineage[key] == dossier[key], "PASSPORT_NATIVE_HASH_MISMATCH")
        wire.require(lineage["scientific_terminal"] == dossier["critic_terminal"] and
                     lineage["market_evidence_epoch_sha256"] == dossier["market_evidence_epoch_sha256"] and
                     lineage["existing_look_ref"] in dossier["grounded_result_refs"], "PASSPORT_NATIVE_IDENTITY_MISMATCH")
        wire.require((spec.get("parameters") or {}).get("hfic_replay_session_id") == identity["session_id"] and
                     (spec.get("parameters") or {}).get("temporal_recipe") == (dossier["grounded_result"] or {}).get("experiment_recipe"),
                     "SPEC_NATIVE_LINEAGE_MISMATCH")
        wire.require(len(dossier["candidate_record_refs"]) == 1, "NATIVE_CANDIDATE_RECORD_UNRESOLVED")
        found = find_native(snapshot, dossier["candidate_record_refs"][0])
        wire.require(found["status"] == "FOUND", found["status"] if found["status"] != "FOUND" else "SOURCE_LINK_UNRESOLVED")
        active = [row for row in found["matches"] if row["status"] == "CURRENT_SOURCE_LINK"]
        wire.require(len(active) == 1, "SOURCE_LINK_NOT_CURRENT")
        match = active[0]
        adopted = resolve_item(snapshot, match["item_id"], git_read=git_read)
        wire.require(adopted["status"] == "RESOLVED", "ADOPTED_SOURCE_UNRESOLVED")
        result.update(status="COMPLETE_SOURCE_TRACE" if not dossier["gaps"] else "PARTIAL",
            decision_ref=record_ref(decision), manifest_sha256=manifest["manifest_sha256"],
            passport_ref=record_ref(record), passport=passport, native=dossier,
            experiment_spec=copy.deepcopy(spec),
            shelf=dict(item_id=match["item_id"], adopted_sources=adopted["adopted_sources"]), gaps=dossier["gaps"])
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as error:
        result["gaps"].append(getattr(error, "code", "SAVED_LINEAGE_UNAVAILABLE_OR_INVALID"))
    return result
