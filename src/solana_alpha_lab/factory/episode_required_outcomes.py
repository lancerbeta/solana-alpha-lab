"""Spec 1.4 episode readiness: exact sources, native prefix, metadata targets.

This artifact is not scientific evidence. No outcome evaluator or target-value
reader is reachable from this projection. Legacy raw projections are unchanged.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from solana_alpha_lab.factory.data_resolver import _safe_relative_path
from solana_alpha_lab.factory.hfic_grounded_discovery import (
    GroundedDiscoveryError, _parse_time, admit_discovery_binding, resolve_research_scope,
)
from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
from solana_alpha_lab.factory.opportunity_episodes import (
    ALLOW, ASSIGNMENT_DIR, DENY_PROTECTED, cohort_day_bounds,
    inventory_from_documents, point_offset, resolve_point, schedule_binding,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256, experiment_spec_sha256

CONTRACT = "EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1"
METADATA_COLUMNS = (
    "cohort_id", "release_id", "episode_id", "mint", "point_id", "field_id",
    "value_kind", "state", "missing_reason", "primitive_id", "call_occurrence_id",
    "request_sha256", "response_sha256", "observation_clock_policy", "source_price_event_time",
    "request_started_at", "response_received_at", "first_reliable_available_at",
    "nominal_due_at", "assigned_at", "request_not_before", "availability_deadline",
    "member_anchor", "evidence_role", "confirmatory_reuse_forbidden",
)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise GroundedDiscoveryError(code)


def _contained(root: Path, relative: object) -> Path:
    path = root / _safe_relative_path(relative)
    _require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
             "EPISODE_SOURCE_BINDING_CONFLICT")
    return path


def _json(root: Path, relative: str) -> dict[str, Any]:
    loaded = json.loads(_contained(root, relative).read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "EPISODE_SOURCE_BINDING_CONFLICT")
    return loaded


def verify_frozen_episode_sources(data_root: Path, frozen: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Adapt native integrity failures to the shared typed consumer boundary."""
    try:
        return _verify_frozen_episode_sources(data_root, frozen)
    except GroundedDiscoveryError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise GroundedDiscoveryError(str(getattr(exc, "code", "EPISODE_SOURCE_BINDING_CONFLICT"))) from exc


def _verify_frozen_episode_sources(data_root: Path, frozen: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Source/protection gate shared by classifier and fixed-time binder.

    Frozen paths and manifests select the scope; the current corpus pointer never
    selects or shrinks it. Release verification hashes opaque files, reads identity
    columns, and verifies the native schedule and admission protection.
    """
    from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
    from solana_alpha_lab.storage.manifests import verify_dataset_manifest, verify_partition_manifest
    from solana_alpha_lab.factory.live_cohort_schedule_artifact import (
        OBSERVATION_SCHEDULE_ARTIFACT_NAME, decode_schedule_artifact,
    )
    from solana_alpha_lab.factory.opportunity_episode_release import (
        REQUIRED_EPISODE_LABELS, CORPUS_SCHEMA_ID, episode_corpus_schema_sha256,
        frozen_protection_from_release, verify_episode_release,
    )

    admit_discovery_binding(frozen)
    assignment_dir = _contained(data_root, ASSIGNMENT_DIR)
    current = [_json(data_root, str(path.relative_to(data_root)).replace("\\", "/"))
               for path in sorted(assignment_dir.glob("*.json"))] if assignment_dir.is_dir() else []
    manifest_parts: dict[str, list[Any]] = {}
    protection = []
    source_refs = []
    for item in frozen:
        census = _contained(data_root, item["census_rel"])
        observations = _contained(data_root, item["observations_rel"])
        _require(census.name == "census.parquet" and observations == census.with_name("observations.parquet"),
                 "EPISODE_SOURCE_BINDING_CONFLICT")
        release = verify_episode_release(census.parent)
        for key in ("cohort_id", "release_id", "census_sha256", "observations_sha256", "schedule_sha256", "schedule_binding"):
            _require(release.get(key) == item.get(key), "EPISODE_SOURCE_BINDING_CONFLICT")
        document = decode_schedule_artifact(
            (census.parent / OBSERVATION_SCHEDULE_ARTIFACT_NAME).read_bytes(),
            wanted_sha=str(item["schedule_sha256"]),
        )
        _require(schedule_binding(document) == item["schedule_binding"], "FROZEN_INPUT_SCHEDULE_MISMATCH")
        manifest_id = str(item["dataset_manifest_id"])
        if manifest_id not in manifest_parts:
            prefix = f"datasets/manifests/{manifest_id}"
            dataset = DatasetManifest.model_validate_json(_contained(data_root, prefix + ".json").read_bytes())
            validation_bytes = _contained(data_root, prefix + ".validation.json").read_bytes()
            import hashlib
            _require(hashlib.sha256(validation_bytes).hexdigest() == dataset.validation_receipt_sha256,
                     "EPISODE_SOURCE_BINDING_CONFLICT")
            validation = json.loads(validation_bytes)
            labels = _json(data_root, prefix + ".labels.json")
            published = _json(data_root, prefix + ".published")
            composition = validation.get("corpus_composition") or []
            _require(dataset.schema_id == CORPUS_SCHEMA_ID
                     and dataset.schema_sha256 == episode_corpus_schema_sha256()
                     and validation.get("dataset_id") == dataset.dataset_id
                     and validation.get("dataset_version") == dataset.dataset_version
                     and labels.get("dataset_version") == dataset.dataset_version
                     and labels.get("cohort_lineage") == [c["cohort_id"] for c in composition]
                     and published.get("dataset_manifest_id") == manifest_id
                     and published.get("dataset_fingerprint") == dataset.dataset_fingerprint,
                     "CANONICAL_METADATA_CONFLICT")
            _require(all(labels.get(k) == v for k, v in REQUIRED_EPISODE_LABELS.items()), "DISCOVERY_AUTHORITY_ABSENT")
            parts = []
            for part_id in validation["partition_manifest_ids"]:
                part = PartitionManifest.model_validate_json(
                    _contained(data_root, f"datasets/manifests/partitions/{part_id}.json").read_bytes())
                verify_partition_manifest(part)
                parts.append(part)
            verify_dataset_manifest(dataset, partitions=parts)
            _require(dataset.dataset_manifest_id == manifest_id and dataset.dataset_id == item["dataset_id"],
                     "EPISODE_SOURCE_BINDING_CONFLICT")
            manifest_parts[manifest_id] = parts
        composition = _json(data_root, f"datasets/manifests/{manifest_id}.validation.json")["corpus_composition"]
        _require({"cohort_id": item["cohort_id"], "release_id": item["release_id"],
                  "content_sha256": release["source_sha256"]} in composition,
                 "CANONICAL_METADATA_CONFLICT")
        for rel_key, hash_key in (("census_rel", "census_sha256"), ("observations_rel", "observations_sha256")):
            matching = [p for p in manifest_parts[manifest_id] if p.logical_location == item[rel_key]]
            _require(len(matching) == 1 and matching[0].file_sha256 == item[hash_key]
                     and matching[0].content_sha256 == item[hash_key], "EPISODE_SOURCE_BINDING_CONFLICT")
        inventory = inventory_from_documents([
            *frozen_protection_from_release(census.parent, expected_schedule_sha256=str(item["schedule_sha256"])), *current,
        ])
        start, end = cohort_day_bounds(str(item["cohort_id"]))
        for mint in pq.read_table(census, columns=["mint"]).column("mint").to_pylist():
            verdict, _ = protection_decision_for_source(inventory, mint, start, end)
            _require(verdict != DENY_PROTECTED, "HOLDOUT_PROTECTED")
            _require(verdict == ALLOW, "HOLDOUT_UNRESOLVED")
        protection.append(inventory.fingerprint())
        source_refs.append({k: item[k] for k in ("cohort_id", "release_id", "dataset_manifest_id", "census_sha256", "observations_sha256", "schedule_sha256", "schedule_binding")})
    return {"sources": source_refs, "current_protection_sha256": canonical_sha256(protection)}


def protection_decision_for_source(inventory, mint, start, end):
    from datetime import timedelta
    from solana_alpha_lab.factory.opportunity_episodes import protection_decision
    return protection_decision(inventory, str(mint), interval_start=start - timedelta(days=1), interval_end=end + timedelta(days=4))


def required_cells(spec: Mapping[str, Any], body: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    target = body["target"]
    _require(target.get("kind") == "PRICE_RELATIVE_PROXY" and target.get("field_id") == temporal.PRICE,
             "EPISODE_TARGET_UNSUPPORTED")
    expected = (str(target["exit_point"]), str(target["field_id"]))
    cells = []
    seen = set()
    for item in spec["required_outcomes"]:
        point_offset(item["point_id"])
        for field in item["field_ids"]:
            key = (item["point_id"], field)
            _require(key not in seen and key == expected and item["role"] == "PRIMARY",
                     "EPISODE_REQUIRED_OUTCOME_INVALID")
            seen.add(key)
            cells.append((*key, item["role"]))
    _require(expected in seen, "EPISODE_PRIMARY_TARGET_UNBOUND")
    return sorted(cells)


def _metadata_status(row: Mapping[str, Any], item: Mapping[str, Any], t0, cutoff) -> str:
    window = resolve_point(item["schedule_binding"], t0, row["point_id"])
    clocks = {"nominal_due_at": window.nominal_due, "assigned_at": window.assigned_at,
              "request_not_before": window.request_not_before, "availability_deadline": window.availability_deadline}
    if any(_parse_time(row.get(k)) != v for k, v in clocks.items()):
        return "INVALID"
    # Native closure can censor an unexecuted slot: no acquisition occurred.
    # Such metadata never qualifies as an observed outcome.
    if row.get("state") in {"CENSORED", "CENSORED_LATE"}:
        return "CENSORED" if row.get("missing_reason") else "INVALID"
    if row.get("state") in {"DEPENDENCY_MISSING", "BLOCKED_BUDGET", "IN_FLIGHT_CALL_INDETERMINATE"}:
        return "MISSING_TYPED" if row.get("missing_reason") else "INVALID"
    reason = temporal._snapshot_lineage_reason(
        row, query_policy=temporal.OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        point_due_at=window.request_not_before, outer_deadline=min(window.availability_deadline, cutoff))
    if reason in {"AVAILABILITY_AFTER_DEADLINE", "ACQUISITION_AFTER_CUTOFF"}:
        return "LATE"
    if reason is not None:
        return "INVALID"
    if row.get("state") == "OBSERVED" and row.get("value_kind") == "DECIMAL":
        return "OBSERVED"
    if row.get("state") in {"MISSING_TYPED", "DISAPPEARED", "DEPENDENCY_MISSING", "BLOCKED_BUDGET", "IN_FLIGHT_CALL_INDETERMINATE"}:
        return "MISSING_TYPED"
    return "INVALID"


def project_episode_required_outcomes(spec: Mapping[str, Any], *, data_root: Path, definition_sha256: str) -> dict[str, Any]:
    """Compute a new authoritative projection; caller projections are never read."""
    _require(spec.get("schema_version") == "1.4", "EPISODE_SPEC_VERSION_UNSUPPORTED")
    public, pre, partitions, bindings = temporal.bind_frozen_fixed_time_inputs(spec, data_root=data_root)
    body = pre["scientific_body"]
    _require(public.get("schema_version") == "1.2" and temporal.is_episode_body(body), "EPISODE_QUERY_UNSUPPORTED")
    recipe = spec["parameters"]["temporal_recipe"]
    _require(recipe.get("scientific_identity") == pre["spec_sha256"], "EXPERIMENT_RECIPE_IDENTITY_MISMATCH")
    cells = required_cells(spec, body)
    source = verify_frozen_episode_sources(data_root, bindings)
    census = []
    metadata = []
    for _cohort, census_path, obs_path in partitions:
        from solana_alpha_lab.factory.opportunity_episode_release import EPISODE_CENSUS_COLUMNS
        census.extend(pq.read_table(census_path, columns=list(EPISODE_CENSUS_COLUMNS)).to_pylist())
        metadata.extend(pq.read_table(obs_path, columns=list(METADATA_COLUMNS)).to_pylist())
    by_source = {(b["cohort_id"], b["release_id"]): b for b in bindings}
    identities = {}
    for row in census:
        identity = str(row.get("episode_id") or "")
        _require(identity and identity not in identities, "EPISODE_ADMISSION_IDENTITY_CONFLICT")
        item = by_source.get((row["cohort_id"], row["release_id"]))
        _require(item is not None and row["schedule_sha256"] == item["schedule_sha256"]
                 and row["anchor_kind"] == "NOMINATION_T0" and row["population"] == "OPPORTUNITY_EPISODES",
                 "EPISODE_SOURCE_BINDING_CONFLICT")
        _require(_parse_time(row["t0"]) is not None, "EPISODE_ANCHOR_INVALID")
        identities[identity] = row
    scope = resolve_research_scope(body, data_root, census, bindings, frozen_evidence=recipe["research_scope_evidence"])
    temporal.require_episode_scope(scope, body, census)
    from solana_alpha_lab.factory.hfic_research_universe_policy import recipe_policy
    policy = recipe_policy(recipe)
    _require(policy is not None, "UNIVERSE_POLICY_BINDING_MISMATCH")
    cutoff = _parse_time(spec["availability_cutoff"])
    _require(cutoff is not None, "CUTOFF_REJECTED")
    grouped = defaultdict(list)
    for row in metadata:
        admission = identities.get(row["episode_id"])
        _require(admission is not None and all(row[k] == admission[k] for k in ("mint", "cohort_id", "release_id"))
                 and row["evidence_role"] == "EXPLORATORY_REUSE" and row["confirmatory_reuse_forbidden"] is True,
                 "EPISODE_SOURCE_BINDING_CONFLICT")
        key = (row["episode_id"], row["point_id"], row["field_id"])
        _require(not grouped[key], "EPISODE_CELL_IDENTITY_CONFLICT")
        grouped[key].append(row)
    prefix = []
    prefix_cells = 0
    dependencies = {(body["decision_point"], f) for f in (temporal.PRICE, temporal.HOLDER_COUNT, temporal.LIQUIDITY)}
    for feature in body["features"]:
        dependencies.update(temporal._feature_dependencies(feature))
    for admission in census:
        episode = admission["episode_id"]
        if scope.universe[episode] != "TRUE":
            continue
        item = by_source[(admission["cohort_id"], admission["release_id"])]
        t0 = _parse_time(admission["t0"])
        decision_cutoff = min(resolve_point(item["schedule_binding"], t0, body["decision_point"]).availability_deadline, cutoff)
        obs_path = _contained(data_root, item["observations_rel"])
        for point, field in sorted(dependencies):
            _require(point_offset(point) <= point_offset(body["decision_point"]), "EPISODE_PREFIX_OUTCOME_LEAKAGE")
            rows = grouped.get((episode, point, field), [])
            prefix.extend(rows)
            if not rows or _metadata_status(rows[0], item, t0, decision_cutoff) != "OBSERVED":
                continue
            # Exact keys and availability filter precede numeric materialization.
            selected = pq.read_table(obs_path, columns=[*METADATA_COLUMNS, "typed_value"], filters=[
                ("episode_id", "=", episode), ("point_id", "=", point), ("field_id", "=", field),
                ("first_reliable_available_at", "<=", str(rows[0]["first_reliable_available_at"])),
            ]).to_pylist()
            _require(len(selected) == 1, "EPISODE_CELL_IDENTITY_CONFLICT")
            prefix[-1] = selected[0]
            prefix_cells += 1
    members = temporal.project_episode_decision_prefix(census, prefix, body, bindings, universe_policy=policy, scope=scope)
    membership = []
    unknown = 0
    for member in members:
        eligible = bool(member["decision_eligible"])
        matched = eligible and bool(member["matched"])
        comparator = eligible and (body.get("contrast") == "MATCHED_VS_DECISION_ELIGIBLE" or not matched)
        unknown += int(member.get("feature_unknown") is True or member.get("universe_status") == "UNKNOWN")
        membership.append({"episode_id": member["episode_id"], "cohort_id": member["cohort_id"], "release_id": member["release_id"],
                           "decision_eligible": eligible, "matched": matched, "comparator": comparator,
                           "reason": member.get("exclusion"), "universe_status": member.get("universe_status")})
    membership.sort(key=lambda row: row["episode_id"])
    decision = [m for m in membership if m["decision_eligible"]]
    coverage = []
    for point, field, role in cells:
        counts = Counter({state: 0 for state in ("OBSERVED", "MISSING_TYPED", "LATE", "CENSORED", "ABSENT", "INVALID")})
        for m in decision:
            admission = identities[m["episode_id"]]
            item = by_source[(admission["cohort_id"], admission["release_id"])]
            rows = grouped.get((m["episode_id"], point, field), [])
            status = _metadata_status(rows[0], item, _parse_time(admission["t0"]), cutoff) if rows else "ABSENT"
            counts[status] += 1
        coverage.append({"point_id": point, "field_id": field, "role": role, "denominator_n": len(decision), "counts": dict(counts)})
    complete = bool(decision) and unknown == 0 and all(c["counts"]["OBSERVED"] == len(decision) for c in coverage)
    temporal.bind_frozen_fixed_time_inputs(spec, data_root=data_root)
    _require(verify_frozen_episode_sources(data_root, bindings) == source, "EPISODE_SOURCE_CHANGED_DURING_READ")
    result = {"schema": "smial.episode-required-outcome-binding", "schema_version": "1.0", "contract": CONTRACT,
              "experiment_spec_sha256": experiment_spec_sha256(spec), "definition_sha256": definition_sha256,
              "recipe_scientific_identity": pre["spec_sha256"], **source,
              "anchor_kind": body["anchor_kind"], "time_contract": body["time_contract"],
              "scope_rule_sha256": scope.rule_sha256, "scope_applied_sha256": scope.applied_sha256,
              "universe_policy": recipe["universe_policy"], "admissions_n": len(census), "decision_n": len(decision),
              "matched_n": sum(m["matched"] for m in membership), "comparator_n": sum(m["comparator"] for m in membership),
              "unresolved_n": unknown, "membership": membership, "membership_sha256": canonical_sha256(membership),
              "required_coverage": coverage, "readiness": "COMPLETE" if complete else "UNRESOLVED",
              "reads": {"prefix_value_cells_read": prefix_cells, "target_value_cells_materialized": 0,
                        "outcome_evaluations": 0, "new_scientific_looks": 0},
              "non_claims": ["NO_SCIENTIFIC_ACCEPTANCE", "NO_CHRONOLOGICAL_CONFIRMATION", "NO_PROMOTION_AUTHORITY"]}
    result["binding_sha256"] = canonical_sha256(result)
    return result
