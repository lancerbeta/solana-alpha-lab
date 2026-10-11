"""Source-bound episode decisions, upstream of the feature-agnostic engine.

The frozen ExperimentSpec owns the query. Existing scope, feature, field and
clock owners interpret it; this adapter only loads its admissible prefix.
"""
from __future__ import annotations

import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

import yaml

from solana_alpha_lab.factory import hfic_research_scope as scope
from solana_alpha_lab.factory.experiment_spec import spec_sha256
from solana_alpha_lab.factory.hfic_temporal_discovery import scientific_body, evaluate_episode_prefix, evaluate_episode_features
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.opportunity_episodes import admission_content_sha256, resolve_point, schedule_binding
from solana_alpha_lab.factory.opportunity_episode_release import project_prefix_observations, read_timely_episode_publications
from solana_alpha_lab.factory.promotion_handoff import verify_strategy_version
from solana_alpha_lab.factory.strategy_runtime import PaperPlaneError, validate_signal_decision, validate_exit_decision


def _serial(value: Any) -> Any:
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, dict):
        return {key: _serial(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serial(item) for item in value]
    return value


class _Prefix:
    """Lazy field loader: no numeric read is possible before scope coverage."""
    def __init__(self, source, admission, binding, cutoff, source_root):
        self.source, self.admission, self.binding, self.cutoff = source, admission, binding, cutoff
        self.source_root = source_root
        self.read_set: list[dict[str, Any]] = []
        self.cache: dict[str, list[dict[str, Any]]] = {}
        self.visibility: dict[str, str | None] = {}

    def window(self, point):
        resolved = resolve_point(self.binding, parse_utc(self.admission["t0"]), point)
        return resolved.request_not_before, resolved.availability_deadline

    def get(self, key, default=()):
        cohort, projection, episode, point, field = key
        if (cohort, projection, episode) != (self.admission["cohort_id"], "TIMELY_PREFIX", self.admission["episode_id"]):
            raise PaperPlaneError("PREFIX_IDENTITY_MISMATCH")
        _, deadline = self.window(point)
        if deadline > self.cutoff:
            raise PaperPlaneError("PREFIX_FUTURE_READ_FORBIDDEN")
        if point not in self.cache:
            records = self.source.read_episode_observations(
                schedule_sha256=self.admission["schedule_sha256"],
                activation_id=self.admission["activation_id"], episode_id=episode,
                point_ids=[point], visible_by=deadline,
            )
            records += read_timely_episode_publications(self.source, data_root=self.source_root,
                admission=self.admission, point_id=point, visible_by=deadline)
            self.visibility[point] = min((record["visible_at"] for record in records), default=None)
            raw = []
            for record in records:
                row = record["row"]
                if (str(row.get("episode_id") or row.get("entity_id")), row.get("mint"), row.get("point_id")) != (episode, self.admission["mint"], point):
                    raise PaperPlaneError("PREFIX_OBSERVATION_IDENTITY_MISMATCH")
                # A pending/published exact copy may coexist across the mark
                # boundary. Different copies are a conflict, not another vote.
                row = dict(row)
                row["ingested_visible_at"] = record["visible_at"]
                raw.append(row)
            flattened = project_prefix_observations(raw, cohort_id=cohort)
            unique = {}
            for row in flattened:
                identity = (row["point_id"], row["field_id"])
                previous = unique.get(identity)
                if previous is not None and previous != row:
                    raise PaperPlaneError("PREFIX_OBSERVATION_COPY_CONFLICT")
                unique[identity] = row
            self.cache[point] = list(unique.values())
        rows = [row for row in self.cache[point] if row["field_id"] == field]
        read = {"point_id": point, "field_id": field, "availability_deadline": render_utc(deadline),
                "rows_sha256": scope.sha256_of(rows), "rows_n": len(rows),
                "ingested_visible_at_floor": self.visibility[point],
                "source_clocks": [{key: row.get(key) for key in ("event_time", "request_started_at",
                    "response_received_at", "first_reliable_available_at", "call_occurrence_id", "response_sha256")}
                    for row in rows]}
        if read not in self.read_set:
            self.read_set.append(read)
        return rows or default


def load_bound_recipe(root: Path, *, strategy, manifest, execution_binding):
    verify_strategy_version(root, strategy, manifest=manifest,
                            decision_event_id=manifest["decision_event_id"],
                            execution_evidence_binding=execution_binding)
    relative = Path(manifest["experiment_spec_source_value"])
    if relative.is_absolute() or ".." in relative.parts:
        raise PaperPlaneError("EXPERIMENT_SPEC_PATH_UNSAFE")
    if spec_sha256(root, relative.as_posix()) != manifest["experiment_spec_sha256"]:
        raise PaperPlaneError("EXPERIMENT_SPEC_HASH_CONFLICT")
    document = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    return bound_recipe_body(document, strategy=strategy)


def bound_recipe_body(document, *, strategy):
    """Derive the runtime recipe only from the exact promoted spec bytes."""
    query = (document.get("parameters") or {}).get("episode_query")
    if not isinstance(query, Mapping) or query.get("schema_version") != "1.2":
        raise PaperPlaneError("BOUND_EPISODE_RECIPE_REQUIRED")
    body = scientific_body(query)
    if scope.selected_cohort_ids(body["research_scope"]) is not None:
        raise PaperPlaneError("RUNTIME_COHORT_SELECTION_UNSUPPORTED")
    if strategy["population_ref"] != body["population"] or document["population"] != body["population"]:
        raise PaperPlaneError("RECIPE_POPULATION_MISMATCH")
    shas = (document.get("parameters") or {}).get("membership_snapshot_shas", [])
    if not isinstance(shas, list) or len(shas) > 32 or any(not isinstance(item, str) or len(item) != 64 or any(ch not in "0123456789abcdef" for ch in item) for item in shas):
        raise PaperPlaneError("RECIPE_MEMBERSHIP_DEPENDENCIES_INVALID")
    body["membership_snapshot_shas"] = sorted(set(shas))
    # Evaluation targets alone do not authorize unattended exits. This explicit
    # spec field is frozen by the same scientific spec hash, never inferred.
    body["executable_exit"] = (document.get("parameters") or {}).get("runtime_execution")
    return body


def produce_episode_decision(root: Path, *, source_path: Path, strategy: Mapping[str, Any],
                             manifest: Mapping[str, Any], execution_binding: Mapping[str, Any],
                             epoch_id: str, episode_id: str, as_of: str,
                             frozen_recipe=None) -> dict[str, Any]:
    body = frozen_recipe if frozen_recipe is not None else load_bound_recipe(root, strategy=strategy, manifest=manifest, execution_binding=execution_binding)
    source = ObservationScheduleStore(source_path, readonly=True, immutable=False)
    try:
        with source.read_snapshot():
            stored = source.get_episode_admission(episode_id)
            if stored is None:
                raise PaperPlaneError("EPISODE_ADMISSION_MISSING")
            admission = stored["record"]
            if admission_content_sha256(admission) != stored["content_sha256"]:
                raise PaperPlaneError("EPISODE_ADMISSION_HASH_CONFLICT")
            registered = source.get_registered_schedule(admission["schedule_sha256"])
            if registered is None:
                raise PaperPlaneError("EPISODE_SCHEDULE_BINDING_MISSING")
            binding = schedule_binding(registered["document"])
            cutoff = resolve_point(binding, parse_utc(admission["t0"]), body["decision_point"]).availability_deadline
            if parse_utc(as_of) < cutoff:
                raise PaperPlaneError("EPISODE_DECISION_NOT_DUE")
            if parse_utc(stored["created_at"]) > cutoff:
                raise PaperPlaneError("EPISODE_ADMISSION_NOT_VISIBLE")
            round_row = source.get_episode_round(admission["round_id"])
            evidence = scope.MembershipEvidence()
            scope.add_admission_frame_membership(
                evidence, schedule_document=registered["document"], census=[admission],
                frames={} if round_row is None else {admission["round_id"]: round_row["frame"]},
            )
            if body["membership_snapshot_shas"]:
                scope.add_local_snapshots(evidence, source_path.parent, snapshot_shas=body["membership_snapshot_shas"])
            resolved = scope.ResolvedScope(scope=body["research_scope"], list_condition=body["list_condition"],
                                           evidence=evidence, episode_ids=[episode_id], slices=body["diagnostic_slices"])
            prefix = _Prefix(source, admission, binding, cutoff, source_path.parent)
            numeric: dict[str, Any] = {}
            try:
                resolved.require_covered()
                member = resolved.universe[episode_id] == scope.TRUE and resolved.signal.get(episode_id, scope.TRUE) == scope.TRUE
                numeric = evaluate_episode_prefix(body, grouped=prefix, cohort=admission["cohort_id"],
                    episode_id=episode_id, t0=parse_utc(admission["t0"]), decision_deadline=cutoff,
                    point_window=prefix.window) if member else {"action": "NO_ENTER"}
                action, reason = numeric["action"], numeric.get("reason_code", "EPISODE_RULE_" + numeric["action"])
            except scope.ResearchScopeError as exc:
                action, reason = "BLOCKED" if "INVALID" in exc.code else "UNKNOWN", exc.code
            recipe_sha = scope.sha256_of(body)
            logical = {"strategy_id": strategy["strategy_id"], "strategy_version": strategy["strategy_version"],
                       "activation_epoch_id": epoch_id, "episode_id": episode_id,
                       "recipe_sha256": recipe_sha, "decision_slot": body["decision_point"]}
            identity = "SIGDEC-" + scope.sha256_of(logical).upper()
            provenance = _serial({"schema": "smial.episode-decision-prefix", "schema_version": "1.0",
                "logical_key": logical, "strategy_sha256": strategy["spec_sha256"],
                "promotion_handoff_manifest_sha256": manifest["manifest_sha256"],
                "experiment_spec_sha256": manifest["experiment_spec_sha256"],
                "admission_content_sha256": stored["content_sha256"], "frame_sha256": admission["frame_sha256"],
                "origin_admission": admission,
                "schedule_binding": binding, "membership": evidence.episode_states(episode_id),
                "decision_cutoff": render_utc(cutoff), "numeric": numeric,
                "read_set": sorted(prefix.read_set, key=lambda item: (item["point_id"], item["field_id"]))})
            digest = scope.sha256_of(provenance)
            decision = validate_signal_decision(root, {
                "schema": "smial.signal-decision", "schema_version": "1.0", "signal_decision_id": identity,
                "strategy_id": strategy["strategy_id"], "strategy_version": strategy["strategy_version"],
                "activation_epoch_id": epoch_id, "source_hypothesis_refs": strategy["source_hypothesis_refs"],
                "mint": admission["mint"], "decision_at": render_utc(cutoff),
                "first_reliable_available_at": render_utc(cutoff), "action": action, "reason_code": reason,
                "evidence_refs": ["execution-event:SRC-" + identity + ":sha256:" + digest],
            })
            return {"decision": decision, "provenance": provenance, "provenance_sha256": digest}
    finally:
        source.close()


def produce_frozen_time_exit(root: Path, *, strategy, position, origin_packet, frozen_recipe, as_of):
    """A due obligation survives missing quotes, retired feeds and old science."""
    rule = frozen_recipe.get("executable_exit")
    if not isinstance(rule, dict) or rule != {"kind": "FROZEN_TIME_EXIT", "exit_point": frozen_recipe["target"]["exit_point"]}:
        raise PaperPlaneError("EXECUTABLE_EXIT_BINDING_REQUIRED")
    provenance = origin_packet["provenance"]
    admission = provenance.get("origin_admission")
    if not isinstance(admission, dict) or admission_content_sha256(admission) != provenance["admission_content_sha256"]:
        raise PaperPlaneError("EXIT_ORIGIN_SOURCE_CONFLICT")
    cutoff = resolve_point(provenance["schedule_binding"], parse_utc(admission["t0"]), rule["exit_point"]).availability_deadline
    if parse_utc(as_of) < cutoff:
        raise PaperPlaneError("EPISODE_EXIT_NOT_DUE")
    identity = "EXITDEC-" + scope.sha256_of({"position_id": position["position_id"], "slot": rule["exit_point"]}).upper()
    proof = {"origin_signal_decision_id": position["signal_decision_id"],
             "recipe_sha256": provenance["logical_key"]["recipe_sha256"],
             "origin_admission_sha256": provenance["admission_content_sha256"],
             "cutoff": render_utc(cutoff), "executable_exit": rule, "price_status": "NOT_REQUIRED_FOR_OBLIGATION"}
    digest = scope.sha256_of(proof)
    decision = validate_exit_decision(root, {"schema": "smial.exit-decision", "schema_version": "1.0",
        "exit_decision_id": identity, "position_id": position["position_id"],
        "strategy_id": strategy["strategy_id"], "strategy_version": strategy["strategy_version"],
        "activation_epoch_id": position["activation_epoch_id"], "decision_at": render_utc(cutoff),
        "first_reliable_available_at": render_utc(cutoff), "action": "EXIT", "reason_code": "FROZEN_TIME_EXIT_DUE",
        "evidence_refs": ["execution-event:SRC-" + identity + ":sha256:" + digest]})
    return {"decision": decision, "provenance": proof, "provenance_sha256": digest}


def produce_originating_exit(root: Path, *, source_path: Path, strategy, manifest, execution_binding,
                             position, origin_packet, as_of: str):
    """The frozen target of the originating recipe; list disappearance is irrelevant."""
    body = load_bound_recipe(root, strategy=strategy, manifest=manifest, execution_binding=execution_binding)
    episode_id = origin_packet["provenance"]["logical_key"]["episode_id"]
    if (position["strategy_id"], position["strategy_version_label"], position["activation_epoch_id"]) != (
        strategy["strategy_id"], strategy["strategy_version"], origin_packet["decision"]["activation_epoch_id"]):
        raise PaperPlaneError("EXIT_ORIGIN_BINDING_CONFLICT")
    source = ObservationScheduleStore(source_path, readonly=True, immutable=False)
    try:
        with source.read_snapshot():
            stored = source.get_episode_admission(episode_id)
            if (stored is None
                or admission_content_sha256(stored["record"]) != stored["content_sha256"]
                or stored["content_sha256"] != origin_packet["provenance"]["admission_content_sha256"]):
                raise PaperPlaneError("EXIT_ORIGIN_SOURCE_CONFLICT")
            admission = stored["record"]
            binding = origin_packet["provenance"]["schedule_binding"]
            point = body["target"]["exit_point"]
            cutoff = resolve_point(binding, parse_utc(admission["t0"]), point).availability_deadline
            if parse_utc(as_of) < cutoff:
                raise PaperPlaneError("EPISODE_EXIT_NOT_DUE")
            prefix = _Prefix(source, admission, binding, cutoff, source_path.parent)
            target = evaluate_episode_features({**body,
                "features": [{"name": "exit_price", "op": "point_value", "field_id": body["target"]["field_id"], "point": point}],
                "predicates": [{"feature": "exit_price", "op": "gt", "value": 0}]},
                grouped=prefix, cohort=admission["cohort_id"], episode_id=episode_id,
                t0=parse_utc(admission["t0"]), decision_deadline=cutoff, point_window=prefix.window)
            identity = "EXITDEC-" + scope.sha256_of({"position_id": position["position_id"], "slot": point}).upper()
            provenance = {"origin_signal_decision_id": position["signal_decision_id"],
                          "recipe_sha256": origin_packet["provenance"]["logical_key"]["recipe_sha256"],
                          "cutoff": render_utc(cutoff), "read_set": prefix.read_set, "target": target}
            digest = scope.sha256_of(provenance)
            decision = validate_exit_decision(root, {"schema": "smial.exit-decision", "schema_version": "1.0",
                "exit_decision_id": identity, "position_id": position["position_id"],
                "strategy_id": strategy["strategy_id"], "strategy_version": strategy["strategy_version"],
                "activation_epoch_id": position["activation_epoch_id"], "decision_at": render_utc(cutoff),
                "first_reliable_available_at": render_utc(cutoff),
                "action": "EXIT" if target["action"] == "ENTER" else "UNKNOWN",
                "reason_code": "ORIGINATING_TARGET_" + target["action"],
                "evidence_refs": ["execution-event:SRC-" + identity + ":sha256:" + digest]})
            return {"decision": decision, "provenance": provenance, "provenance_sha256": digest}
    finally:
        source.close()
