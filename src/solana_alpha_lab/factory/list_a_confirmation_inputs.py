"""Source-owned native confirmation port and metadata-only compiled binding.

Market tables and target state are never decoded by inspect/prepare/authorize.
Source authority, exposure inventory and purpose-specific protection are separate
durable records. A package or an arbitrary caller flag grants no consumption.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path, PureWindowsPath
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from pydantic import BaseModel, ConfigDict, Field

from solana_alpha_lab.factory.list_a_confirmation_method import (
    CORE_SHA, PARTITIONS, block_for, digest, finite_bytes, qualify_runtime,
)
from solana_alpha_lab.factory.opportunity_episodes import (
    cycle_start, episode_id_for, resolve_point, validate_episode_schedule,
    frame_receipt, inventory_from_documents, collection_lineage_id, episode_cohort_family_key,
    cohort_id_for_admission, cohort_day_bounds,
)
from solana_alpha_lab.factory.hfic_research_scope import (
    MembershipEvidence, ResolvedScope, add_admission_frame_membership, jupiter_definitions,
    canonical_scope, canonical_list_condition,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import canonical_temporal_spec
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore
from solana_alpha_lab.factory.run_passport import experiment_spec_sha256

CAPABILITY = "CAP-LIST-A-CHRONOLOGICAL-CONFIRMATION-001"
SOURCE_OWNER = "NATIVE_EPISODE_CONFIRMATION_SOURCE_V1"
DEFINITION = "configs/experiment_specs/list_a_chronological_confirmation_v1.yaml"
LIST_A = "JUPITER:toporganicscore:5m"
SOURCE_COLUMNS = ["episode_id", "mint", "t0", "cohort_id", "release_id", "round_id", "frame_sha256",
                  "admission_request_started_at", "admission_response_received_at", "admission_first_reliable_available_at"]
SOURCE_ROLE_COLUMNS = ["evidence_role", "confirmatory_reuse_forbidden"]
ADMISSION_COLUMNS = {"entity_id", "episode_id", "mint", "population", "population_contract", "anchor_kind",
    "collection_kind", "collection_lineage_id", "schedule_sha256", "activation_id", "cycle_start", "ticket_priority",
    "t0", "cohort_id", "membership_state", "witness_point_id", "witness_source_id", "witness_rank", "witness_object_sha256",
    "witness_call_occurrence_id", "witness_request_sha256", "witness_request_started_at", "witness_response_received_at",
    "witness_first_reliable_available_at", "witness_response_sha256", "witness_raw_body_rel", "asset_class",
    "frame_sha256", "protection_fingerprint", "round_id"}
IMPLEMENTATION_PATHS = (
    "src/solana_alpha_lab/factory/list_a_confirmation.py",
    "src/solana_alpha_lab/factory/list_a_confirmation_inputs.py",
    "src/solana_alpha_lab/factory/list_a_confirmation_method.py",
    "src/solana_alpha_lab/factory/opportunity_episodes.py",
    "src/solana_alpha_lab/factory/hfic_research_scope.py",
    "src/solana_alpha_lab/factory/hfic_temporal_discovery.py",
    "src/solana_alpha_lab/factory/research_store.py",
    "src/solana_alpha_lab/factory/run_passport.py",
    "src/solana_alpha_lab/factory/experiment_spec.py",
    "src/solana_alpha_lab/factory/lane_classifier.py",
    "src/solana_alpha_lab/factory/capabilities.py",
    "src/solana_alpha_lab/factory/document_runner.py",
    "src/solana_alpha_lab/factory/data_resolver.py",
    "src/solana_alpha_lab/factory/experiment_evidence.py",
    "src/solana_alpha_lab/factory/research_workbench.py",
    "catalog/schemas/experiment_spec_v1_5.schema.json",
    "catalog/schemas/list_a_confirmation_input_v1.schema.json",
    "catalog/schemas/list_a_confirmation_result_v1.schema.json",
    DEFINITION, "configs/list_a_chronological_confirmation_v1.yaml",
    "configs/experiment_capability_registry_v2.yaml", "uv.lock",
)


class ConfirmationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ConfirmationError(code)


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, serialize_by_alias=True)


class Exposure(ClosedModel):
    source_ids: list[str]
    ancestors: list[str]
    inventory_complete: bool
    confirmatory_reuse_forbidden: bool
    empirical_development: bool
    preregistered_at: str
    prior_exposure_end: str
    development_decision_max: str | None
    development_target_available_max: str | None


class SampleFields(ClosedModel):
    schema_tag: Literal["smial.list-a-confirmation-input"] = Field(alias="schema")
    source_id: str
    lineage_id: str
    namespace: str
    domain: Literal["SYNTHETIC", "REAL"]
    role: Literal["UNTOUCHED_FORWARD_HOLDOUT", "EXPLORATORY_REUSE"]
    interval_start: str
    interval_end_exclusive: str
    information_start: str
    data_cutoff: str
    census_rel: str
    observations_rel: str
    frames_rel: str
    admissions_rel: str
    protection_rel: str
    source_hashes: dict[str, str]
    exposure: Exposure
    frozen_protection_sha256: str
    universe_policy: Literal["EXACT_NATIVE_ADMISSIONS_KNOWN_REFERENCED"]
    purge_rule: Literal["INFORMATION_START_STRICT_AFTER_BOUNDARY"]


class Sample(SampleFields):
    schema_version: Literal["1.0"]
    schedule_rel: str


class ScheduleOwner(ClosedModel):
    schedule_rel: str
    activation_id: str


class MultiScheduleSample(SampleFields):
    schema_version: Literal["1.1"]
    schedule_set: list[ScheduleOwner] = Field(min_length=1)


def parse_sample(document: dict) -> Sample | MultiScheduleSample:
    model = MultiScheduleSample if document.get("schema_version") == "1.1" else Sample
    return model.model_validate(document)


def utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ConfirmationError("TIMESTAMP_INVALID") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), "UTC_REQUIRED")
    return parsed.astimezone(UTC)


def safe_path(data_root: Path, relative: str) -> Path:
    root = data_root.resolve(strict=True)
    win = PureWindowsPath(relative)
    require(isinstance(relative, str) and not win.drive and not win.root and
            not Path(relative).is_absolute() and "\\" not in relative and
            all(p not in {"", ".", ".."} for p in relative.split("/")), "INPUT_PATH_UNSAFE")
    path = root
    for part in relative.split("/"):
        path = path / part
        require(not path.is_symlink() and not path.is_junction(), "INPUT_REPARSE_UNSAFE")
    require(path.resolve().is_relative_to(root), "INPUT_PATH_UNSAFE")
    return path


def identifier(value: str) -> str:
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value)), "IDENTIFIER_INVALID")
    return value


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "DUPLICATE_JSON_KEY")
            out[key] = value
        return out
    def reject(_):
        raise ConfirmationError("NONFINITE_JSON")
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=unique, parse_constant=reject)
    except (OSError, ValueError) as exc:
        raise ConfirmationError("INPUT_DOCUMENT_INVALID") from exc


def publish(data_root: Path, relative: str, raw: bytes) -> None:
    """Public immutable owner publication using ResearchStore atomic semantics."""
    from solana_alpha_lab.factory.research_store import publish_immutable_artifact
    publish_immutable_artifact(data_root, relative, raw)


def event(root: Path, *, record_id: str, kind: RecordKind, transaction_id: str,
          payload: dict, run_id: str | None = None, now: datetime | None = None,
          producer: str = CAPABILITY) -> ResearchEvent:
    import subprocess
    now = now or datetime.now(UTC)
    git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                             check=True).stdout.decode("ascii").strip()
    raw = finite_bytes(payload)
    return ResearchEvent(record_id=record_id, record_kind=kind, entity_id=record_id,
        hypothesis_version_id=payload.get("hypothesis_version_id"), run_id=run_id,
        transaction_id=transaction_id, effective_at=now, first_reliable_available_at=now,
        supersedes_record_id=None, payload_json=raw.decode(), payload_sha256=hashlib.sha256(raw).hexdigest(),
        schema_version="1.0", producer_capability_id=producer, producer_git_sha=git_sha, created_at=now)


def records(store) -> list[dict]:
    return [{"record_id": r.record_id, "kind": str(r.record_kind), "payload": json.loads(r.payload_json),
             "transaction_id": r.transaction_id, "effective_at": r.effective_at.isoformat(),
             "producer": r.producer_capability_id}
            for r in store.iter_committed_records()]


def source_metadata(sample: Sample | MultiScheduleSample, *, root: Path, data_root: Path) -> dict:
    """Opaque hashes plus allowlisted census and list frames; no observations decoder."""
    multi = isinstance(sample, MultiScheduleSample)
    owners = sample.schedule_set if multi else [ScheduleOwner(schedule_rel=sample.schedule_rel, activation_id="LEGACY")]
    expected_paths = {sample.census_rel, sample.observations_rel, sample.frames_rel, sample.protection_rel, sample.admissions_rel,
                      *(o.schedule_rel for o in owners)}
    require(set(sample.source_hashes) == expected_paths, "SOURCE_SET_INCOMPLETE")
    for relative, sha in sample.source_hashes.items():
        require(file_sha(safe_path(data_root, relative)) == sha, "SOURCE_HASH_MISMATCH")
    # Source-owned role columns survive repackaging; external Sample/exposure
    # assertions cannot turn an exploratory release into an untouched source.
    # Read only provenance columns, never observation states or target values.
    for relative in (sample.census_rel, sample.observations_rel):
        with pq.ParquetFile(safe_path(data_root, relative)) as parquet:
            require(set(SOURCE_ROLE_COLUMNS) <= set(parquet.schema_arrow.names), "SOURCE_ROLE_PROVENANCE_UNBOUND")
            for batch in parquet.iter_batches(columns=SOURCE_ROLE_COLUMNS):
                for row in batch.to_pylist():
                    require(row["evidence_role"] in {"UNTOUCHED_FORWARD_HOLDOUT", "EXPLORATORY_REUSE"} and
                            isinstance(row["confirmatory_reuse_forbidden"], bool), "SOURCE_ROLE_PROVENANCE_INVALID")
                    require(row["evidence_role"] == "UNTOUCHED_FORWARD_HOLDOUT" and
                            row["confirmatory_reuse_forbidden"] is False, "CONFIRMATORY_REUSE_FORBIDDEN")
    schedules = [validate_episode_schedule(load_json(safe_path(data_root, o.schedule_rel)), root=root) for o in owners]
    by_sha = {s["schedule_sha256"]: (s, o.activation_id) for s, o in zip(schedules, owners)}
    if multi:
        require(len(by_sha) == len(owners) == len({o.schedule_rel for o in owners}) == len({o.activation_id for o in owners}),
                "NATIVE_SCHEDULE_OWNER_DUPLICATE")
        require([s["schedule_sha256"] for s in schedules] == sorted(by_sha), "NATIVE_SCHEDULE_SET_NOT_CANONICAL")
        first = schedules[0]
        # Same frozen-template compatibility used by the managed child producer;
        # no synthetic aggregate schedule and no relaxation of capture semantics.
        projection = lambda s: {k: v for k, v in s.items() if k not in {"activation", "schedule_sha256"}}
        require(all(collection_lineage_id(s) == sample.lineage_id and
                    episode_cohort_family_key(s) == episode_cohort_family_key(first) and
                    projection(s) == projection(first) for s in schedules), "NATIVE_SCHEDULE_FAMILY_CONFLICT")
        cohorts = set()
        for s in schedules:
            start, stop = (utc(s["activation"][k]) for k in ("starts_at", "stops_admitting_at"))
            cohort = cohort_id_for_admission(start)
            a, b = cohort_day_bounds(cohort)
            require(a <= start < stop <= b, "NATIVE_SCHEDULE_NOT_DAILY")
            require(cohort not in cohorts, "NATIVE_COHORT_MULTIPLE_OWNERS")
            cohorts.add(cohort)
    assignment_documents = load_json(safe_path(data_root, sample.protection_rel))["assignments"]
    inventory = inventory_from_documents(assignment_documents)
    require(inventory.status == "ALLOW", "NATIVE_FROZEN_PROTECTION_UNRESOLVED")
    require(all(sorted((i["assignment_id"], i["sha256"]) for i in s["protection"]["assignment_sources"]) ==
                sorted((i["assignment_id"], i["sha256"]) for i in inventory.sources) for s in schedules),
            "NATIVE_FROZEN_PROTECTION_MISMATCH")
    census = pq.read_table(safe_path(data_root, sample.census_rel), columns=SOURCE_COLUMNS).to_pylist()
    frames = load_json(safe_path(data_root, sample.frames_rel))
    admissions = load_json(safe_path(data_root, sample.admissions_rel))
    acquisition_keys = []
    unique = {}
    episode_schedule_bindings, schedule_census = {}, {sha: [] for sha in by_sha}
    for row in census:
        t0 = utc(row["t0"])
        require(utc(row["admission_request_started_at"]) <= utc(row["admission_response_received_at"]) <=
                utc(row["admission_first_reliable_available_at"]) <= t0, "ADMISSION_CLOCK_ORDER_INVALID")
        require(utc(row["admission_first_reliable_available_at"]) >= utc(sample.information_start),
                "ADMISSION_INFORMATION_OVERLAP")
        require(utc(sample.interval_start) <= t0 < utc(sample.interval_end_exclusive), "EPISODE_OUTSIDE_INTERVAL")
        require(row["episode_id"] == episode_id_for(lineage_id=sample.lineage_id,
                cycle=cycle_start(t0), mint=row["mint"]), "NATIVE_ADMISSION_IDENTITY_INVALID")
        key = (sample.namespace, row["episode_id"])
        frame = frames.get(row["round_id"], {})
        admission = admissions.get(row["episode_id"], {})
        require(admission.get("schedule_sha256") in by_sha, "NATIVE_ADMISSION_FOREIGN_SCHEDULE" if multi else
                "NATIVE_ADMISSION_SOURCE_CLOCK_CONFLICT")
        schedule, activation_id = by_sha[admission["schedule_sha256"]]
        schedule_binding = {**schedule["observation_schedule"],
                            "witness_max_age_seconds": schedule["nomination"]["witness_max_age_seconds"]}
        if multi:
            require(admission.get("activation_id") == activation_id == frame.get("activation_id"),
                    "NATIVE_ADMISSION_ACTIVATION_CONFLICT")
            require(row["cohort_id"] == cohort_id_for_admission(t0) ==
                    cohort_id_for_admission(utc(schedule["activation"]["starts_at"])), "NATIVE_COHORT_OWNER_CONFLICT")
        episode_schedule_bindings[row["episode_id"]] = schedule_binding
        require(all(admission.get(k) == row[k] for k in ("episode_id", "mint", "t0", "cohort_id", "round_id", "frame_sha256")) and
                admission.get("population") == "OPPORTUNITY_EPISODES" and admission.get("membership_state") == "ADMITTED" and
                admission.get("collection_lineage_id") == sample.lineage_id, "NATIVE_ADMISSION_WITNESS_CONFLICT")
        require(all(admission.get("witness_" + suffix) == row["admission_" + suffix] for suffix in
                ("request_started_at", "response_received_at", "first_reliable_available_at")), "NATIVE_ADMISSION_CLOCK_CONFLICT")
        candidates = [c for c in frame.get("candidates", []) if c.get("mint") == row["mint"]]
        require(len(candidates) == 1, "NATIVE_ADMISSION_CANDIDATE_CONFLICT")
        candidate = candidates[0]
        require(admission.get("witness_call_occurrence_id") == candidate.get("selected_call_occurrence_id") and
                admission.get("witness_object_sha256") == candidate.get("selected_object_sha256") and
                admission.get("witness_source_id") == candidate.get("selected_source_id"), "NATIVE_ADMISSION_OCCURRENCE_CONFLICT")
        sources = [s for s in frame.get("sources", []) if s.get("source_id") == admission["witness_source_id"]]
        require(len(sources) == 1 and sources[0].get("status") == "OBSERVED" and
                sources[0].get("call_occurrence_id") == admission["witness_call_occurrence_id"] and
                sources[0].get("response_sha256") == admission.get("witness_response_sha256") and
                sources[0].get("response_received_at") == admission["witness_response_received_at"] and
                admission.get("schedule_sha256") == schedule["schedule_sha256"] and
                admission.get("protection_fingerprint") == inventory.fingerprint(), "NATIVE_ADMISSION_SOURCE_CLOCK_CONFLICT")
        require(all(bool(re.fullmatch(r"[0-9a-f]{64}", str(admission.get(k, "")))) for k in
                    ("witness_call_occurrence_id", "witness_object_sha256", "witness_request_sha256")), "NATIVE_ADMISSION_OCCURRENCE_UNBOUND")
        acquisition_keys.append(digest({"mint": row["mint"], "occurrence": admission["witness_call_occurrence_id"],
            "object": admission["witness_object_sha256"], "source": admission["witness_source_id"]}))
        require(frame.get("protection_fingerprint") == inventory.fingerprint(), "ADMISSION_PROTECTION_MISMATCH")
        require(any(c.get("mint") == row["mint"] and c.get("status") == "PASS"
                    for c in frame.get("candidates", [])), "NATIVE_ADMISSION_NOT_PASS")
        require(utc(schedule["activation"]["starts_at"]) <= t0 < utc(schedule["activation"]["stops_admitting_at"]),
                "NATIVE_ACTIVATION_INTERVAL_MISMATCH")
        # Calendar maturity belongs to the authoritative metadata admission gate.
        # It is independent of target values, presence, missingness and statistics.
        require(resolve_point(schedule_binding, t0, "E14400").availability_deadline <= utc(sample.data_cutoff),
                "TARGET_NOT_MATURE_AT_CUTOFF")
        if key in unique:
            require(not multi, "NATIVE_ADMISSION_DUPLICATE")
            require(unique[key] == row, "DUPLICATE_EPISODE_CONFLICT")
        unique[key] = row
        schedule_census[schedule["schedule_sha256"]].append(row)
    census = sorted(unique.values(), key=lambda r: r["episode_id"])
    evidence = MembershipEvidence()
    require(not multi or all(schedule_census.values()), "NATIVE_SCHEDULE_OWNER_UNUSED")
    for sha, (schedule, _) in by_sha.items():
        add_admission_frame_membership(evidence, schedule_document=schedule, census=schedule_census[sha], frames=frames)
    definitions = jupiter_definitions(schedules[0])
    core = yaml.safe_load((root / "configs/list_a_chronological_confirmation_v1.yaml").read_text(encoding="utf-8"))["protocol_core"]
    require(digest(core) == CORE_SHA, "PROTOCOL_CORE_MISMATCH")
    require(definitions[LIST_A]["definition_sha256"] == core["question"]["list_definition_sha256"], "LIST_DEFINITION_MISMATCH")
    scope = canonical_scope({}, evidence)
    condition = canonical_list_condition({"clauses": [{"all_of": [LIST_A]}]}, evidence)
    resolved = ResolvedScope(scope=scope, list_condition=condition, evidence=evidence,
                             episode_ids=[r["episode_id"] for r in census])
    resolved.require_covered()
    query = {"schema": "smial.hfic-temporal-query", "schema_version": "1.2",
        "query_id": "QUERY-LIST-A-CONFIRMATION-V1", "population": "OPPORTUNITY_EPISODES",
        "anchor_kind": "NOMINATION_T0", "time_contract": {"schedule_contract": "OPPORTUNITY_EPISODE_SCHEDULE_V1",
            "time_feature_clock": "FIRST_RELIABLE_AVAILABLE_AT"}, "search_tier": "COMPOUND_SCREEN",
        "budget_allocation": "COMPOUND_FIRST", "decision": {"point_id": "E1800"}, "features": [], "all": [],
        "target": {"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E1800", "exit_point": "E14400",
                   "field_id": "FIELD-USD-PRICE-001"}, "entry_model": {"kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT",
                   "assumed_latency_seconds": 0}, "hypothesis_kind": "LIST_CONTRAST", "research_scope": scope,
        "list_condition": condition, "contrast": "MATCHED_VS_ELIGIBLE_COMPLEMENT"}
    compiled = canonical_temporal_spec(query)
    upper = {}
    for group, signal in (("A", "TRUE"), ("C", "FALSE")):
        rows = [r for r in census if resolved.signal[r["episode_id"]] == signal]
        upper[group] = {"mints": len({r["mint"] for r in rows}),
            "blocks": {str(h): len({block_for(resolve_point(episode_schedule_bindings[r["episode_id"]], utc(r["t0"]), "E1800").nominal_due, h)
                                   for r in rows}) for h in PARTITIONS}}
    require(all(v["mints"] >= 30 and all(n >= 30 for n in v["blocks"].values()) for v in upper.values()),
            "INSUFFICIENT_POTENTIAL_SUPPORT")
    acquisition_keys = sorted(set(acquisition_keys))
    require(set(admissions) == {r["episode_id"] for r in census}, "NATIVE_ADMISSION_INVENTORY_CONFLICT")
    metadata = {"census": census, "scope": resolved, "compiled_query": compiled,
            "acquisition_keys": acquisition_keys, "acquisition_identity_sha256": digest(acquisition_keys),
            "schedule_binding": {**schedules[0]["observation_schedule"], "witness_max_age_seconds": schedules[0]["nomination"]["witness_max_age_seconds"]},
            "episode_schedule_bindings": episode_schedule_bindings,
            "potential_support": upper, "census_semantic_sha256": digest(census)}
    purpose_protection(sample, metadata, inventory, "FROZEN")
    return metadata


def validate_exposure(sample: Sample) -> dict:
    e = sample.exposure
    require(e.inventory_complete and set(e.source_ids) == {sample.source_id} and
            len(set(e.ancestors)) == len(e.ancestors), "EXPOSURE_INVENTORY_INCOMPLETE")
    require(not e.confirmatory_reuse_forbidden and sample.role == "UNTOUCHED_FORWARD_HOLDOUT", "CONFIRMATORY_REUSE_FORBIDDEN")
    start = utc(sample.information_start)
    require(utc(sample.interval_start) >= start and utc(e.preregistered_at) < start and
            utc(e.prior_exposure_end) < start, "CHRONOLOGY_INVALID")
    if e.empirical_development:
        require(e.development_decision_max is not None and e.development_target_available_max is not None, "DEVELOPMENT_CLOCK_UNBOUND")
        # The bound E target horizon + worst grid allowance + visibility, once.
        boundary = max(utc(e.development_target_available_max),
                       utc(e.development_decision_max) + timedelta(seconds=14400 + 300 + 300))
        require(start > boundary, "CHRONOLOGY_INFORMATION_OVERLAP")
    else:
        require(e.development_decision_max is None and e.development_target_available_max is None, "FAKE_DEVELOPMENT_CLOCKS")
    require(utc(sample.interval_start) < utc(sample.interval_end_exclusive) <= utc(sample.data_cutoff), "INTERVAL_INVALID")
    return {"information_start": sample.information_start, "exposure_boundary": e.prior_exposure_end,
            "purged_episode_ids": [], "rule": sample.purge_rule}


def implementation_qualification(root: Path) -> dict:
    import subprocess
    from solana_alpha_lab.factory.data_resolver import verify_implementation_assets, EvidenceResolutionError
    registry = yaml.safe_load((root / "configs/experiment_capability_registry_v2.yaml").read_bytes())
    descriptors = [d for d in registry["capabilities"] if d["capability_id"] == CAPABILITY]
    require(len(descriptors) == 1, "CONFIRMATION_REGISTRY_ROUTE_UNBOUND")
    expected = {"status": "ACCEPTED", "entrypoint": "solana_alpha_lab.factory.list_a_confirmation:execute_list_a_confirmation",
        "parameter_schema_asset_id": "SCHEMA-EXPERIMENT-SPEC-V1-5-001", "effect_class": "OFFLINE_DATA_PLANE_WRITE",
        "output_zone": "DATA_ROOT_ONLY", "max_provider_calls": 0, "promotion_authority": "NONE",
        "provider_policy_asset_id": None, "supports_pit": True, "determinism_class": "DETERMINISTIC"}
    require(all(descriptors[0].get(k) == v for k, v in expected.items()), "CONFIRMATION_REGISTRY_ROUTE_CONFLICT")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, check=True).stdout.decode().strip()
    def git_bytes(repository, revision, relative):
        result = subprocess.run(["git", "show", f"{revision}:{relative}"], cwd=repository, capture_output=True)
        return result.stdout if result.returncode == 0 else None
    try:
        verify_implementation_assets(descriptors[0], root=root, runner_git_sha=head, git_show_bytes=git_bytes)
    except EvidenceResolutionError as exc:
        raise ConfirmationError("CONFIRMATION_IMPLEMENTATION_NOT_ACCEPTED") from exc
    return {"runtime": qualify_runtime(), "closure": {p: file_sha(root / p) for p in IMPLEMENTATION_PATHS}}


def qualify_local_storage(data_root: Path) -> str:
    """Read-only supported local filesystem check before scientific reservation."""
    require(not data_root.is_symlink() and not data_root.is_junction(), "DATA_ROOT_REPARSE_UNSAFE")
    if os.name == "nt":
        import ctypes
        volume, filesystem = ctypes.create_unicode_buffer(260), ctypes.create_unicode_buffer(64)
        kernel = ctypes.windll.kernel32
        require(bool(kernel.GetVolumePathNameW(str(data_root), volume, len(volume))), "STORAGE_QUALIFICATION_UNKNOWN")
        require(kernel.GetDriveTypeW(volume.value) == 3, "NONLOCAL_STORAGE_UNSUPPORTED")
        require(bool(kernel.GetVolumeInformationW(volume.value, None, 0, None, None, None, filesystem, len(filesystem))),
                "STORAGE_QUALIFICATION_UNKNOWN")
        require(filesystem.value in {"NTFS", "ReFS"}, "STORAGE_FILESYSTEM_UNSUPPORTED")
        return filesystem.value
    if os.name == "posix" and Path("/proc/self/mountinfo").is_file():
        matches = []
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            before, after = line.split(" - ", 1)
            mount = Path(before.split()[4].replace("\\040", " "))
            if data_root.resolve().is_relative_to(mount):
                matches.append((len(str(mount)), after.split()[0]))
        require(bool(matches), "STORAGE_QUALIFICATION_UNKNOWN")
        filesystem = max(matches)[1]
        require(filesystem in {"ext4", "xfs", "btrfs", "tmpfs", "overlay"}, "STORAGE_FILESYSTEM_UNSUPPORTED")
        return filesystem
    raise ConfirmationError("STORAGE_QUALIFICATION_UNKNOWN")


def validate_confirmation_result(result: dict, *, root: Path) -> None:
    """Cold typed consistency, never re-evaluates values or the bootstrap."""
    import jsonschema
    try:
        jsonschema.validate(result, load_json(root / "catalog/schemas/list_a_confirmation_result_v1.schema.json"))
    except jsonschema.ValidationError as exc:
        raise ConfirmationError("TYPED_RESULT_SCHEMA_INVALID") from exc
    m, p = result["method"], result["population"]
    rows = p["membership"]
    require(rows == sorted(rows, key=lambda r: r["episode_id"]) and len({r["episode_id"] for r in rows}) == len(rows),
            "RESULT_POPULATION_IDENTITY_CONFLICT")
    require(len(rows) == p["scope_known"] == p["admitted"] and digest(rows) == p["decision_mask_sha256"], "RESULT_POPULATION_MASK_CONFLICT")
    require(p["repeated_mints"] == len(rows) - len({r["mint"] for r in rows}), "RESULT_MINT_SUPPORT_CONFLICT")
    require(m["observed_mask_sha256"] == p["observed_mask_sha256"] and
            p["observed"] == sum(m["support"][g]["observed"] for g in ("A", "C")), "RESULT_OBSERVED_MASK_CONFLICT")
    for row in rows:
        require(all(row["blocks"][str(h)] == block_for(utc(row["decision_nominal_due"]), h) for h in PARTITIONS), "RESULT_BLOCK_CLOCK_CONFLICT")
    for g in ("A", "C"):
        s = m["support"][g]
        d = sum(r["group"] == g and r["decision_eligible"] for r in rows)
        require(d == p["decision_denominators"][g] == s["decision_denominator"] and
                s["observed"] <= d and s["mints"] <= s["observed"] and
                all(n <= s["observed"] for n in s["blocks"].values()), "RESULT_GROUP_SUPPORT_CONFLICT")
        require(m["coverage"][g] == (s["observed"] / d if d else None), "RESULT_COVERAGE_CONFLICT")
    require(sum(p["typed_missing_counts"].values()) == sum(p["decision_denominators"].values()) - p["observed"], "RESULT_MISSING_COUNTS_CONFLICT")
    if m["means"] is not None:
        require(math.isfinite(m["means"]["A"] - m["means"]["C"]) and
                m["contrast"] == m["means"]["A"] - m["means"]["C"], "RESULT_CONTRAST_CONFLICT")
    else:
        require(m["contrast"] is None, "RESULT_CONTRAST_CONFLICT")
    for h, part in m["partitions"].items():
        from solana_alpha_lab.factory.list_a_confirmation_method import seed_for
        require(part["seed"] == seed_for(int(h)) and part["valid_replicates"] + part["invalid_replicates"] == 4096,
                "RESULT_REPLICATE_CONFLICT")
        require((part["interval"] is None) == (part["invalid_replicates"] != 0), "RESULT_INTERVAL_CONFLICT")
        if part["interval"] is not None:
            require(part["interval"][0] <= part["interval"][1], "RESULT_INTERVAL_CONFLICT")
    terminal = m["terminal"]
    from solana_alpha_lab.factory.list_a_confirmation_method import NUMERIC_REFUSALS
    if set(m["reason_codes"]).intersection(NUMERIC_REFUSALS):
        require(terminal == "INSUFFICIENT" and m["means"] is None and m["contrast"] is None and
                not m["partitions"] and not m["leave_one"], "RESULT_NUMERIC_REFUSAL_CONFLICT")
    if terminal == "INSUFFICIENT":
        require(bool(m["reason_codes"]), "RESULT_INSUFFICIENT_REASON_MISSING")
        return
    require(not m["reason_codes"] and m["means"] is not None and set(m["partitions"]) == {str(h) for h in PARTITIONS}, "RESULT_STATISTICAL_STATE_CONFLICT")
    require(m["pooled_mints"] >= 30 and all(n >= 30 for n in m["pooled_blocks"].values()) and
            all(s["mints"] >= 30 and all(n >= 30 for n in s["blocks"].values()) for s in m["support"].values()), "RESULT_SUPPORT_FLOOR_CONFLICT")
    a, c = m["support"]["A"], m["support"]["C"]
    require(all(s["observed"] * 100 >= s["decision_denominator"] * 95 and s["decision_denominator"] > 0
                for s in (a, c)) and abs(a["observed"] * c["decision_denominator"] - c["observed"] * a["decision_denominator"]) * 100 <=
            5 * a["decision_denominator"] * c["decision_denominator"], "RESULT_COVERAGE_FLOOR_CONFLICT")
    loo = m["leave_one"]
    require(loo and loo["count"] == loo["valid_count"] == m["pooled_mints"] + sum(m["pooled_blocks"].values()) and
            loo["min"] is not None and loo["max"] is not None and loo["min"] <= loo["max"] and
            loo["min_labels"] and loo["max_labels"], "RESULT_LEAVE_ONE_CONFLICT")
    for key in ("min", "max"):
        require(all(label["contrast"] == loo[key] for label in loo[key + "_labels"]), "RESULT_LEAVE_ONE_CONFLICT")
    intervals = [m["partitions"][str(h)]["interval"] for h in PARTITIONS]
    require(all(v is not None for v in intervals), "RESULT_STATISTICAL_STATE_CONFLICT")
    expected = "ASSOCIATION_SUPPORTED_CONDITIONAL" if all(v[0] > 0 for v in intervals) and loo["min"] > 0 else (
        "ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY" if all(v[1] <= 0 for v in intervals) and loo["max"] <= 0 else
        "INCONCLUSIVE_DEPENDENCE_OR_CONCENTRATION")
    require(terminal == expected, "RESULT_TERMINAL_CONFLICT")


def purpose_protection(sample: Sample, metadata: dict, inventory, stage: str) -> None:
    require(inventory.status == "ALLOW", stage + "_NATIVE_PROTECTION_UNRESOLVED")
    start = utc(sample.information_start)
    end = max(utc(sample.interval_end_exclusive), *(resolve_point(metadata["episode_schedule_bindings"][r["episode_id"]], utc(r["t0"]), "E14400").availability_deadline
              + timedelta(microseconds=1) for r in metadata["census"]))
    for mint in {r["mint"] for r in metadata["census"]}:
        for entry in inventory.entries.get(mint, ()):
            scope = entry.get("scope", {})
            kind = scope.get("kind")
            require(kind in {"ALL_TIME", "INTERVAL"}, stage + "_NATIVE_PROTECTION_SCOPE_UNKNOWN")
            applies = kind == "ALL_TIME"
            if kind == "INTERVAL":
                a, b = utc(scope.get("start")), utc(scope.get("end"))
                require(a < b, stage + "_NATIVE_PROTECTION_SCOPE_INVALID")
                applies = a < end and start < b
            if applies:
                require(entry.get("role") == "UNTOUCHED_FORWARD_HOLDOUT" and
                        entry.get("confirmatory_reuse_forbidden") is False,
                        stage + "_NATIVE_PROTECTION_DENY")


def current_native_protection(sample: Sample, metadata: dict, data_root: Path) -> dict:
    """Purpose-specific native inventory: untouched holdout is never global ALLOW."""
    directory = safe_path(data_root, "protection/assignments")
    require(directory.is_dir(), "CURRENT_NATIVE_PROTECTION_UNBOUND")
    documents = [load_json(safe_path(data_root, "protection/assignments/" + p.name)) for p in sorted(directory.glob("*.json"))]
    inventory = inventory_from_documents(documents)
    require(inventory.status == "ALLOW", "CURRENT_NATIVE_PROTECTION_UNRESOLVED")
    expected = {i["assignment_id"] for i in load_json(safe_path(data_root, sample.protection_rel))["assignments"]}
    require(expected <= {i["assignment_id"] for i in inventory.sources}, "CURRENT_NATIVE_PROTECTION_INCOMPLETE")
    require(len(inventory.sources) == len({i["assignment_id"] for i in inventory.sources}), "CURRENT_NATIVE_PROTECTION_CONFLICT")
    purpose_protection(sample, metadata, inventory, "CURRENT")
    return {"fingerprint": inventory.fingerprint(), "sources": list(inventory.sources)}


def inspect_confirmation(definition: dict, sample_ref: str, *, root: Path, data_root: Path,
                         now: datetime) -> dict:
    from solana_alpha_lab.factory.experiment_spec import validate_experiment_document
    validate_experiment_document(definition, root=root)
    qualify_local_storage(data_root)
    require(now.tzinfo is not None, "TIMESTAMP_INVALID")
    try:
        sample = parse_sample(load_json(safe_path(data_root, sample_ref)))
    except ValueError as exc:
        raise ConfirmationError("INPUT_CONTRACT_INVALID") from exc
    validate_exposure(sample)
    require(utc(sample.data_cutoff) <= now, "CUTOFF_IN_FUTURE")
    store = ResearchStore(data_root, create_if_missing=False)
    history = records(store)
    source_sha = digest(sample.model_dump())
    authority = [r for r in history if r["payload"].get("type") == "SOURCE_AUTHORITY" and
                 r["payload"].get("sample_sha256") == source_sha and r["producer"] == SOURCE_OWNER]
    require(len(authority) == 1, "SOURCE_AUTHORITY_UNBOUND")
    metadata = source_metadata(sample, root=root, data_root=data_root)
    require(authority[0]["payload"].get("acquisition_identity_sha256") == metadata["acquisition_identity_sha256"] and
            authority[0]["payload"].get("exposure_sha256") == digest(sample.exposure.model_dump()), "SOURCE_AUTHORITY_CONFLICT")
    native_protection = current_native_protection(sample, metadata, data_root)
    protection = [r for r in history if r["payload"].get("type") == "PROTECTION" and
                  r["payload"].get("source_id") in {sample.source_id, *sample.exposure.ancestors}]
    require({p["payload"].get("source_id") for p in protection} == {sample.source_id, *sample.exposure.ancestors},
            "CURRENT_PROTECTION_INVENTORY_INCOMPLETE")
    require(protection and all(p["payload"].get("status") == "UNTOUCHED_FORWARD_HOLDOUT" for p in protection), "CURRENT_PROTECTION_DENY")
    for ancestor in sample.exposure.ancestors:
        sources = [r for r in history if r["payload"].get("type") == "SOURCE_AUTHORITY" and r["payload"].get("source_id") == ancestor]
        require(len(sources) == 1 and sources[0]["payload"].get("exposure", {}).get("inventory_complete") is True,
                "ANCESTOR_EXPOSURE_UNBOUND")
        require(not sources[0]["payload"].get("exposure", {}).get("confirmatory_reuse_forbidden", True),
                "ANCESTOR_CONFIRMATORY_REUSE_FORBIDDEN")
    require(any(p["payload"].get("protection_sha256") == sample.frozen_protection_sha256 for p in protection), "FROZEN_PROTECTION_UNBOUND")
    qualification = implementation_qualification(root)
    binding = {"type": "EXECUTION_BINDING", "experiment_id": definition["experiment_id"],
        "hypothesis_version_id": definition["hypothesis_version"], "experiment_spec_sha256": experiment_spec_sha256(definition),
        "protocol_core_sha256": CORE_SHA, "sample_ref": sample_ref, "sample_sha256": source_sha,
        "source_id": sample.source_id, "source_set_sha256": digest(sample.source_hashes), "source_hashes": sample.source_hashes,
        "namespace": sample.namespace, "domain": sample.domain, "role": sample.role,
        "interval_start": sample.interval_start, "interval_end_exclusive": sample.interval_end_exclusive,
        "data_cutoff": sample.data_cutoff, "query": metadata["compiled_query"],
        "scope_applied_sha256": metadata["scope"].applied_sha256,
        "census_semantic_sha256": metadata["census_semantic_sha256"], "potential_support": metadata["potential_support"],
        "chronology": validate_exposure(sample), "exposure_sha256": digest(sample.exposure.model_dump()),
        "frozen_protection_sha256": sample.frozen_protection_sha256,
        "current_protection_sha256": digest({"records": protection, "native": native_protection}), "qualification": qualification,
        "source_authority_id": authority[0]["record_id"], "lineage_id": sample.lineage_id,
        "acquisition_identity_sha256": metadata["acquisition_identity_sha256"], "acquisition_keys": metadata["acquisition_keys"],
        "study_budget_sha256": digest({"question": CORE_SHA, "native_acquisition": metadata["acquisition_identity_sha256"]}),
        "max_scientific_attempts": 1, "adaptive_allowance": 0}
    return {"binding": binding, "metadata": metadata, "sample": sample}


def spent_confirmation_checkpoint(store, binding_id: str, binding: dict) -> dict:
    """Project existing consumption even across metadata/implementation aliases."""
    spent = [r for r in records(store) if r["kind"] == "RESEARCH_ARTIFACT" and
             r["payload"].get("type") == "CONFIRMATION_RESERVATION" and
             (r["payload"].get("study_budget_sha256") == binding["study_budget_sha256"] or
              set(r["payload"].get("acquisition_keys", [])).intersection(binding["acquisition_keys"]))]
    require(len(spent) <= 1, "COMMITTED_RESERVATION_CONFLICT")
    # Exact projection avoids recursively resolving this same prepared binding.
    from solana_alpha_lab.factory.list_a_confirmation import confirmation_checkpoint
    return confirmation_checkpoint(store, spent[0]["payload"]["execution_binding_sha256"] if spent else binding_id)


def prepare_confirmation(definition: dict, sample_ref: str, *, root: Path, store: ResearchStore, now: datetime) -> dict:
    context = inspect_confirmation(definition, sample_ref, root=root, data_root=store.root, now=now)
    body = context["binding"]
    sha = digest(body)
    checkpoint = spent_confirmation_checkpoint(store, sha, body)
    if checkpoint["scientific_charge"] == 1:
        return {"status": "ALREADY_RESERVED", "binding_id": sha, "scientific_charge": 1,
                "prior_scientific_checkpoint": checkpoint, "next_action": "READ_ORIGINAL_TRIAL_KEEP_CONSUMED_ALLOWANCE"}
    relative = f"confirmation/bindings/{sha}.json"
    publish(store.root, relative, finite_bytes(body))
    txn = "RESEARCH-TXN-LA-PREPARE-" + sha[:24].upper()
    if not any(r["record_id"] == "LA-BINDING-" + sha for r in records(store)):
        store.append([event(root, record_id="LA-BINDING-" + sha, kind=RecordKind.RESEARCH_ARTIFACT,
            transaction_id=txn, payload={**body, "execution_binding_sha256": sha, "artifact_ref": relative})], transaction_id=txn)
    return {"status": "PREPARED", "binding_id": sha, "execution_binding_sha256": sha,
            "scientific_charge": 0, "request_sha256": digest({"binding": sha, "purpose": "ALLOW_EXACT_CONFIRMATION"}),
            "next_action": "AUTHORIZE_EXACT_SYNTHETIC_REQUEST"}


def authorize_confirmation(definition: dict, binding_id: str, *, root: Path, store: ResearchStore,
                           owner_phrase: str, valid_until: str, now: datetime) -> dict:
    require(bool(re.fullmatch(r"[0-9a-f]{64}", binding_id)), "BINDING_ID_INVALID")
    body = load_json(safe_path(store.root, f"confirmation/bindings/{binding_id}.json"))
    fresh = inspect_confirmation(definition, body["sample_ref"], root=root, data_root=store.root, now=now)["binding"]
    require(digest(body) == binding_id == digest(fresh), "EXECUTION_BINDING_STALE")
    request = digest({"binding": binding_id, "purpose": "ALLOW_EXACT_CONFIRMATION"})
    require(owner_phrase == f"AUTHORIZE {body['domain']} LIST A {request}", "EXACT_GRANT_PHRASE_REQUIRED")
    checkpoint = spent_confirmation_checkpoint(store, binding_id, body)
    if checkpoint["scientific_charge"] == 1:
        return {"status": "ALREADY_RESERVED", "binding_id": binding_id, "scientific_charge": 1,
                "prior_scientific_checkpoint": checkpoint, "next_action": "READ_ORIGINAL_TRIAL_KEEP_CONSUMED_ALLOWANCE"}
    require(utc(valid_until) > now, "GRANT_EXPIRED")
    grant = {"type": "CONFIRMATION_GRANT", "request_sha256": request,
        "execution_binding_sha256": binding_id, "study_budget_sha256": body["study_budget_sha256"],
        "source_set_sha256": body["source_set_sha256"], "source_id": body["source_id"], "role": body["role"],
        "protocol_core_sha256": CORE_SHA, "domain": body["domain"], "purpose": "ALLOW_EXACT_CONFIRMATION",
        "executor": CAPABILITY, "plane": "DATA_ROOT_ONLY", "max_scientific_attempts": 1,
        "valid_until": valid_until, "revocation_ref": "SOURCE_PROTECTION_HISTORY"}
    sha = digest(grant)
    txn = "RESEARCH-TXN-LA-GRANT-" + sha[:24].upper()
    if not any(r["record_id"] == "LA-GRANT-" + sha for r in records(store)):
        store.append([event(root, record_id="LA-GRANT-" + sha, kind=RecordKind.RESEARCH_ARTIFACT,
            transaction_id=txn, payload=grant)], transaction_id=txn)
    return {"status": "AUTHORIZED", "grant_id": "LA-GRANT-" + sha, "request_sha256": request, "scientific_charge": 0}


def revoke_confirmation(binding_id: str, *, root: Path, store: ResearchStore, owner_phrase: str | None = None) -> dict:
    """Exact owner revoke; available even when current execution is inadmissible."""
    from solana_alpha_lab.factory.list_a_confirmation import bound_confirmation_checkpoint
    require(bool(re.fullmatch(r"[0-9a-f]{64}", binding_id)), "BINDING_ID_INVALID")
    binding = load_json(safe_path(store.root, f"confirmation/bindings/{binding_id}.json"))
    require(digest(binding) == binding_id, "EXECUTION_BINDING_STALE")
    history = records(store)
    grants = [r for r in history if r["payload"].get("type") == "CONFIRMATION_GRANT" and
              r["payload"].get("execution_binding_sha256") == binding_id]
    require(len(grants) == 1, "EXACT_GRANT_UNBOUND_OR_CONFLICT")
    grant = grants[0]
    validate_exact_grant(grant, binding, binding_id)
    checkpoint = bound_confirmation_checkpoint(store, binding_id)
    request = digest({"binding": binding_id, "grant": grant["record_id"], "purpose": "REVOKE_EXACT_CONFIRMATION"})
    phrase = f"REVOKE {binding['domain']} LIST A {request}"
    response = {**checkpoint, "grant_id": grant["record_id"], "request_sha256": request}
    if owner_phrase is None:
        return {**response, "status": "REVOKE_REQUESTED", "owner_phrase": phrase,
                "next_action": "OWNER_EXACT_REVOKE_PHRASE_REQUIRED"}
    require(owner_phrase == phrase, "EXACT_REVOKE_PHRASE_REQUIRED")
    sha = digest({"grant": grant["record_id"], "purpose": "REVOKE_EXACT_CONFIRMATION"})
    txn = "RESEARCH-TXN-LA-REVOKE-" + sha[:24].upper()
    if not any(r["payload"].get("type") == "GRANT_REVOKED" and
               r["payload"].get("grant_id") == grant["record_id"] for r in history):
        store.append([event(root, record_id="LA-GRANT-REVOKED-" + sha, kind=RecordKind.RESEARCH_ARTIFACT,
            transaction_id=txn, payload={"type": "GRANT_REVOKED", "grant_id": grant["record_id"],
            "execution_binding_sha256": binding_id, "domain": binding["domain"],
            "purpose": "REVOKE_EXACT_CONFIRMATION", "request_sha256": request})], transaction_id=txn)
    return {**response, "status": "REVOKED", "next_action": "READ_SAVED_STATE_NO_NEW_EXECUTION_AUTHORITY"}


def validate_exact_grant(record: dict, binding: dict, binding_id: str) -> None:
    p = record["payload"]
    expected = {"type": "CONFIRMATION_GRANT", "execution_binding_sha256": binding_id,
        "request_sha256": digest({"binding": binding_id, "purpose": "ALLOW_EXACT_CONFIRMATION"}),
        **{k: binding[k] for k in ("study_budget_sha256", "source_set_sha256", "source_id", "role", "protocol_core_sha256", "domain")},
        "purpose": "ALLOW_EXACT_CONFIRMATION", "executor": CAPABILITY, "plane": "DATA_ROOT_ONLY",
        "max_scientific_attempts": 1, "revocation_ref": "SOURCE_PROTECTION_HISTORY"}
    require(record["producer"] == CAPABILITY and record["kind"] == "RESEARCH_ARTIFACT" and
            record["record_id"] == "LA-GRANT-" + digest(p) and set(p) == {*expected, "valid_until"} and
            all(p.get(k) == v for k, v in expected.items()), "EXACT_GRANT_INVALID")


def write_native_confirmation_sample(*, root: Path, store: ResearchStore, source_id: str,
        lineage_id: str, namespace: str, census: list[dict], observations: list[dict],
        schedule: dict | None = None, schedules: list[dict] | None = None, frames: dict, admission_documents: list[dict], protection_documents: list[dict], interval_start: str, interval_end_exclusive: str,
        information_start: str, data_cutoff: str, exposure: dict, domain: str,
        role: str = "UNTOUCHED_FORWARD_HOLDOUT") -> str:
    """Native source ingress only: no result, reservation, metric or decision."""
    identifier(source_id)
    identifier(lineage_id)
    identifier(namespace)
    require((schedule is None) != (schedules is None), "NATIVE_SCHEDULE_INPUT_AMBIGUOUS")
    prefix = f"confirmation/sources/{source_id}"
    frames = {key: frame_receipt(frame) for key, frame in frames.items()}
    admissions = {}
    for document in admission_documents:
        projected = {k: document.get(k) for k in ADMISSION_COLUMNS}
        eid = projected["episode_id"]
        require(schedules is None or eid not in admissions, "NATIVE_ADMISSION_DUPLICATE")
        require(eid not in admissions or admissions[eid] == projected, "NATIVE_ADMISSION_DUPLICATE_CONFLICT")
        admissions[eid] = projected
    source_hashes = {}
    import io
    for name, rows in (("census.parquet", census), ("observations.parquet", observations)):
        buffer = io.BytesIO()
        pq.write_table(pa.Table.from_pylist(rows), buffer, compression="zstd")
        raw = buffer.getvalue()
        relative = f"{prefix}/{name}"
        publish(store.root, relative, raw)
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
    schedule_documents, schedule_set = [], []
    if schedules is None:
        schedule_documents.append(("schedule.json", schedule))
    else:
        require(bool(schedules), "NATIVE_SCHEDULE_SET_EMPTY")
        for entry in schedules:
            require(set(entry) == {"document", "activation_id"}, "NATIVE_SCHEDULE_OWNER_INVALID")
            doc = validate_episode_schedule(entry["document"], root=root)
            name = "schedules/" + doc["schedule_sha256"] + ".json"
            schedule_documents.append((name, doc))
            schedule_set.append({"schedule_rel": f"{prefix}/{name}", "activation_id": identifier(entry["activation_id"])})
        schedule_set.sort(key=lambda o: o["schedule_rel"])
    for name, document in (*schedule_documents, ("frames.json", frames),
                           ("admissions.json", admissions),
                           ("protection.json", {"assignments": protection_documents})):
        relative, raw = f"{prefix}/{name}", finite_bytes(document)
        publish(store.root, relative, raw)
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
    protection_body = {"type": "PROTECTION", "source_id": source_id, "status": role, "namespace": namespace}
    protection_sha = digest(protection_body)
    schedule_fields = {"schema_version": "1.0", "schedule_rel": f"{prefix}/schedule.json"} if schedules is None else {
        "schema_version": "1.1", "schedule_set": schedule_set}
    sample = parse_sample({"schema": "smial.list-a-confirmation-input", **schedule_fields,
        "source_id": source_id, "lineage_id": lineage_id, "namespace": namespace, "domain": domain, "role": role,
        "interval_start": interval_start, "interval_end_exclusive": interval_end_exclusive,
        "information_start": information_start, "data_cutoff": data_cutoff,
        "census_rel": f"{prefix}/census.parquet", "observations_rel": f"{prefix}/observations.parquet",
        "frames_rel": f"{prefix}/frames.json",
        "protection_rel": f"{prefix}/protection.json",
        "admissions_rel": f"{prefix}/admissions.json",
        "source_hashes": source_hashes, "exposure": exposure, "frozen_protection_sha256": protection_sha,
        "universe_policy": "EXACT_NATIVE_ADMISSIONS_KNOWN_REFERENCED", "purge_rule": "INFORMATION_START_STRICT_AFTER_BOUNDARY"})
    source_metadata(sample, root=root, data_root=store.root)
    sha = digest(sample.model_dump())
    sample_ref = f"{prefix}/sample.json"
    publish(store.root, sample_ref, finite_bytes(sample.model_dump()))
    for document in protection_documents:
        assignment_id = identifier(document["assignment_id"])
        publish(store.root, f"protection/assignments/{assignment_id}.json", finite_bytes(document))
    txn = "RESEARCH-TXN-LA-INGRESS-" + sha[:24].upper()
    if not any(r["record_id"] == "LA-INGRESS-" + sha for r in records(store)):
        store.append([event(root, record_id="LA-INGRESS-" + sha, kind=RecordKind.RESEARCH_ARTIFACT,
            transaction_id=txn, payload={"type": "NATIVE_SOURCE_INGRESS", "sample_sha256": sha,
                "source_set_sha256": digest(source_hashes), "source_id": source_id, "domain": domain,
                "format": "VALUE_NEUTRAL_NATIVE_METADATA_V1"}, producer=SOURCE_OWNER)], transaction_id=txn)
    return sample_ref


def register_source_authority(sample_ref: str, *, root: Path, store: ResearchStore,
                              owner_phrase: str | None = None) -> dict:
    """Separate source-owner preview/authorize. Ingress and grant confer no source authority."""
    sample = parse_sample(load_json(safe_path(store.root, sample_ref)))
    validate_exposure(sample)
    history = records(store)
    require(any(r["record_id"] == "LA-INGRESS-" + digest(sample.model_dump()) and r["producer"] == SOURCE_OWNER and
        r["payload"].get("source_set_sha256") == digest(sample.source_hashes) and
        r["payload"].get("format") == "VALUE_NEUTRAL_NATIVE_METADATA_V1" for r in history), "NATIVE_SOURCE_INGRESS_UNBOUND")
    metadata = source_metadata(sample, root=root, data_root=store.root)
    current_native_protection(sample, metadata, store.root)
    sha = digest(sample.model_dump())
    authority = {"type": "SOURCE_AUTHORITY", "sample_sha256": sha, "source_id": sample.source_id,
        "source_set_sha256": digest(sample.source_hashes), "exposure_sha256": digest(sample.exposure.model_dump()),
        "exposure": sample.exposure.model_dump(), "domain": sample.domain, "role": sample.role,
        "acquisition_keys": metadata["acquisition_keys"], "acquisition_identity_sha256": metadata["acquisition_identity_sha256"]}
    request_sha = digest(authority)
    phrase = f"REGISTER {sample.domain} LIST A SOURCE {request_sha}"
    if owner_phrase is None:
        return {"status": "SOURCE_PREPARED", "sample_ref": sample_ref, "request_sha256": request_sha,
                "owner_phrase": phrase, "scientific_charge": 0}
    require(owner_phrase == phrase, "EXACT_SOURCE_OWNER_PHRASE_REQUIRED")
    # Same acquisition can have aliases, but its independent exposure assertion cannot improve.
    keys = set(metadata["acquisition_keys"])
    history = records(store)
    for record in history:
        p = record["payload"]
        if p.get("type") == "SOURCE_AUTHORITY" and keys.intersection(p.get("acquisition_keys", [])):
            require(p.get("role") == sample.role and p.get("exposure", {}).get("confirmatory_reuse_forbidden") is False,
                    "SOURCE_EXPOSURE_CONFLICT")
    if not any(r["record_id"] == "LA-SOURCE-" + sha for r in history):
        txn = "RESEARCH-TXN-LA-SOURCE-" + sha[:24].upper()
        protection = {"type": "PROTECTION", "source_id": sample.source_id, "status": sample.role,
                      "namespace": sample.namespace, "protection_sha256": sample.frozen_protection_sha256}
        store.append([event(root, record_id="LA-SOURCE-" + sha, kind=RecordKind.RESEARCH_ARTIFACT,
            transaction_id=txn, payload={**authority, "source_owner_request_sha256": request_sha}, producer=SOURCE_OWNER),
            event(root, record_id="LA-PROTECTION-" + sample.frozen_protection_sha256, kind=RecordKind.RESEARCH_ARTIFACT,
            transaction_id=txn, payload=protection, producer=SOURCE_OWNER)], transaction_id=txn)
    return {"status": "SOURCE_REGISTERED", "sample_ref": sample_ref, "source_authority_id": "LA-SOURCE-" + sha,
            "scientific_charge": 0, "request_sha256": request_sha}
