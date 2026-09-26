"""Live cohort Discovery Evidence Release → versioned LIVE LIFECYCLE CORPUS.

Wraps Discovery Evidence Release / Tokens V2 / RDP manifests. Does not mutate
historical A3 singleton release bytes. Zero network.
"""

from __future__ import annotations

import json
import os
import pickle
import secrets
import shutil
import sqlite3
import tempfile
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.factory.discovery_evidence_release import (
    DiscoveryReleaseError,
    _publish_bytes,
    _render_utc,
    _require,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (
    BATCH_SIZE,
    CENSUS_RELEASE_SCHEMA,
    MEMBER_SCHEMA,
    OBS_RELEASE_SCHEMA,
    OBSERVATION_SCHEMA,
    RELEASE_PARQUET_WRITE_KWARGS,
    SOURCE_BUNDLE_SCHEMA,
    SOURCE_BUNDLE_SCHEMA_VERSION,
    SOURCE_BUNDLE_SCHEMA_VERSION_SELF_CONTAINED,
    SOURCE_MANIFEST_NAME,
    SOURCE_MEMBERS_NAME,
    SOURCE_OBSERVATIONS_NAME,
    SOURCE_SCHEDULE_NAME,
    SOURCE_REPRESENTATION_BUNDLE,
    SOURCE_REPRESENTATION_LEGACY_JSON,
    compact_source_view,
    commit_source_bundle,
    compute_source_identity,
    cohort_source_dir,
    discard_stale_staging,
    iter_parquet_row_batches,
    member_from_parquet_row,
    new_staging_dir,
    note_admission_probe_rows,
    note_member_checkpoint_hit,
    note_member_checkpoint_miss,
    note_member_target_cache_hit,
    note_counter,
    note_full_member_rows,
    note_member_file_open,
    note_member_full_column_scan,
    note_observation_rows,
    extraction_counters,
    reset_extraction_counters,
    observation_from_parquet_row,
    parquet_row_count,
    row_for_member_parquet,
    row_for_observation_parquet,
    sha256_file_streaming,
    sha256_files_concat_streaming,
    spill_sqlite,
    write_parquet_from_row_batches,
)
from solana_alpha_lab.factory.members_snapshot_delta import (
    LAYOUT_KIND,
    LEGACY_KIND,
    MembersDeltaError,
    canonical_unit_binding,
    canonical_unit_files_binding,
    canonical_unit_files_binding_fast,
    canonical_unit_noop_range,
    prefix_walk_unit,
    reconstruct_stats,
    reset_fingerprint_work,
    _contained_data_path,
    iter_member_row_batches_for_location,
    iter_spilled_member_rows,
    read_member_layout,
)
from solana_alpha_lab.factory.research_store import (
    ExistingResearchStoreReader,
    ResearchStoreBoundTelemetry,
    ResearchStoreError,
)
from solana_alpha_lab.factory.bounded_cohort_materialization import (
    BOUNDED_WORK_CLASS,
    BUILD_ALREADY_RUNNING,
    BoundedMaterializationError,
    CohortBuildLock,
    DEFAULT_WALL_BUDGET_S,
    MaterializationProgress,
    OBSERVATION_LINEAGE_INCOMPLETE,
    PROGRESS_NAME,
    UNBOUNDED_PLAN,
    WALL_BUDGET_EXCEEDED,
    WallBudget,
    file_size_for_rel,
    inspect_member_target,
    plan_is_unbounded,
    resolve_observation_panel_location,
    select_member_batches,
    select_observation_batches,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.factory.live_cohort_schedule_artifact import (
    CENSUS_SCHEDULE_SHA_MISMATCH,
    OBSERVATION_SCHEDULE_ARTIFACT_NAME,
    RELEASE_SCHEMA_VERSION_LEGACY,
    RELEASE_SCHEMA_VERSION_SELF_CONTAINED,
    SCHEDULE_ARTIFACT_HASH_MISMATCH,
    SCHEDULE_ARTIFACT_MISSING,
    SCHEDULE_DOCUMENT_CONFLICT,
    SCHEDULE_DOCUMENT_MISSING,
    SCHEDULE_PARSER_INVALID,
    SCHEDULE_SEMANTIC_SHA_MISMATCH,
    agree_schedule_documents,
    decode_schedule_artifact,
    encode_schedule_artifact,
    load_ops_schedule_document,
)
from solana_alpha_lab.factory.tokens_v2_typed_projection import (
    FEATURE_FAMILY_MISSINGNESS,
    FEATURE_FAMILY_ORDER,
    FIELD_TO_FAMILY,
    PROJECTION_ID,
    PROJECTION_VERSION,
    STATE_EXCLUDED,
    STATE_MISSING,
    STATE_OBSERVED,
)

CORPUS_DATASET_ID = "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"
_LAST_BOUNDED_RESEARCH_RELS: tuple[str, ...] = ()


def last_bounded_research_rels() -> tuple[str, ...]:
    """Partition parquet and manifest paths selected by the last bounded read."""

    return _LAST_BOUNDED_RESEARCH_RELS


CORPUS_SCHEMA_ID = "SCHEMA-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"
LIVE_EVIDENCE_ROLE = "EXPLORATORY_REUSE"
COMMIT_POINT_KIND = "LIVE_LIFECYCLE_DISCOVERY_CORPUS_PUBLICATION_V1"
COHORT_ADMISSION_FIELD = "discovery_first_reliable_available_at"
ADMISSION_REPRESENTATIONS = (
    COHORT_ADMISSION_FIELD,
    "first_reliable_available_at",
    "discovery_available_at",
)
COHORT_WINDOW_DAYS = 7
_MAX_LOCAL_UNIT_CONTEXTS = 8
_MAX_LOCAL_PREFIX_BINDINGS = 8
RELEASE_SCHEMA = "smial.live-cohort-discovery-release"
RELEASE_SCHEMA_VERSION = RELEASE_SCHEMA_VERSION_LEGACY
RELEASE_MANIFEST_NAME = "release_manifest.json"
CENSUS_NAME = "census.parquet"
OBSERVATIONS_NAME = "observations.parquet"
SOURCE_INVENTORY_NAME = "source_inventory.json"
OBSERVATION_RDP_REBUILD_NAME = "live_observation_rebuild/source_snapshot.json"
LEGACY_SOURCE_JSON_MAX_BYTES = 32 * 1024 * 1024

SEALABLE_READY = frozenset(
    {
        "READY_VALID",
        "READY_VALID_WITH_COVERAGE_LIMITATION",
    }
)
COVERAGE_LIMITED_CLASSES = frozenset(
    {
        "GAP_SUSPECTED",
        "DISCOVERY_COVERAGE_UNKNOWN",
    }
)
_COVERAGE_RANK = {
    "GAP_CONFIRMED": 0,
    "GAP_SUSPECTED": 1,
    "DISCOVERY_COVERAGE_UNKNOWN": 2,
    "EMPIRICAL_OVERLAP_ONLY": 3,
    "PROVIDER_CONTRACT_PROVEN": 4,
}


def cohort_snapshot_path(observation_rdp_root: Path, cohort_id: str) -> Path:
    _require(
        cohort_id.startswith("REL-") and cohort_id.count("-") == 2,
        "COHORT_ID_INVALID",
    )
    return Path(observation_rdp_root) / "live_observation_rebuild" / f"cohort={cohort_id}" / "source_snapshot.json"


def cohort_source_manifest_path(observation_rdp_root: Path, cohort_id: str) -> Path:
    _require(
        cohort_id.startswith("REL-") and cohort_id.count("-") == 2,
        "COHORT_ID_INVALID",
    )
    return cohort_source_dir(observation_rdp_root, cohort_id) / SOURCE_MANIFEST_NAME

REQUIRED_LABELS = {
    "evidence_role": LIVE_EVIDENCE_ROLE,
    "confirmatory_reuse_forbidden": True,
    "outcome_previously_consumed": False,
    "provider_calls_for_bind": 0,
    "projection_id": PROJECTION_ID,
    "projection_version": PROJECTION_VERSION,
    "logical_dataset_id": CORPUS_DATASET_ID,
}

DENOMINATOR_STATES = frozenset(
    {
        "discovered",
        "sampled",
        "hash_not_selected",
        "capacity_excluded",
        "x_ineligible",
        "observed",
        "disappeared",
        "censored_late",
        "typed_missing",
        "unknown",
    }
)

_SELECTED_CANDIDATE_STATES = frozenset({"ADMITTED", "SAMPLED_MEMBER"})
_HASH_EXCLUDE = frozenset({"NOT_SELECTED_HASH_SAMPLE"})
_CAPACITY_EXCLUDE = frozenset({"NOT_SELECTED_CAPACITY"})
_X_INELIGIBLE = frozenset({"X_POPULATION_INELIGIBLE"})
_PREDICATE_EXCLUDE = frozenset({"NOT_SELECTED_PREDICATE", "ANCHOR_UNKNOWN"})


class LiveCohortReleaseError(DiscoveryReleaseError):
    """Fail-closed live cohort / corpus errors."""


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise LiveCohortReleaseError("CLOCK_NOT_AWARE")
    return parsed.astimezone(UTC)


def _compact_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _rel_encoded_instant(value: datetime) -> datetime:
    """UTC instant at the second precision stored in a REL-* cohort id.

    Activation timestamps stay unchanged. Cohort identity bounds are the
    instants that round-trip through ``cohort_window_bounds``.
    """
    return datetime.strptime(_compact_utc(value), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def campaign_cohort_windows(
    starts_at: datetime,
    stops_admitting_at: datetime,
) -> list[tuple[str, datetime, datetime]]:
    """Half-open [S+k*7d, S+(k+1)*7d) windows until stops_admitting_at.

    Bounds use REL-* second precision so the generated id parses back to the
    same instants. Subsecond activation fields are not rewritten.
    """
    start = _rel_encoded_instant(starts_at)
    stop = _rel_encoded_instant(stops_admitting_at)
    _require(stop > start, "CAMPAIGN_WINDOW_INVALID")
    windows: list[tuple[str, datetime, datetime]] = []
    cursor = start
    while cursor < stop:
        end = min(cursor + timedelta(days=COHORT_WINDOW_DAYS), stop)
        cohort_id = f"REL-{_compact_utc(cursor)}-{_compact_utc(end)}"
        windows.append((cohort_id, cursor, end))
        cursor = end
    return windows


def cohort_id_for_admission(
    admission_at: datetime,
    *,
    starts_at: datetime,
    stops_admitting_at: datetime,
) -> str | None:
    """Campaign-relative cohort id, or None when outside the admission window."""
    instant = admission_at.astimezone(UTC)
    for cohort_id, start, end in campaign_cohort_windows(starts_at, stops_admitting_at):
        if start <= instant < end:
            return cohort_id
    return None


def cohort_window_bounds(cohort_id: str) -> tuple[datetime, datetime]:
    _require(cohort_id.startswith("REL-") and cohort_id.count("-") == 2, "COHORT_ID_INVALID")
    _, start_s, end_s = cohort_id.split("-", 2)
    start = datetime.strptime(start_s, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    end = datetime.strptime(end_s, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    _require(end > start, "COHORT_ID_INVALID")
    return start, end


def write_observation_rdp_source(
    observation_rdp_root: Path,
    snapshot: Mapping[str, Any],
    *,
    cohort_id: str | None = None,
) -> Path:
    root = Path(observation_rdp_root)
    cid = cohort_id or str(snapshot.get("cohort_id") or "")
    path = cohort_snapshot_path(root, cid) if cid else root / OBSERVATION_RDP_REBUILD_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(
            dict(snapshot), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    )
    return path


def _sha40(value: object) -> str | None:
    text = str(value or "")
    if len(text) == 40 and all(c in "0123456789abcdef" for c in text):
        return text
    return None


def _contributing_producers(payload: Mapping[str, Any]) -> list[str]:
    raw = payload.get("contributing_producer_git_shas")
    if isinstance(raw, list) and raw:
        out: list[str] = []
        for item in raw:
            digest = _sha40(item)
            _require(digest is not None, "RELEASE_INVALID_SOURCE_INTEGRITY")
            assert digest is not None
            out.append(digest)
        return sorted(dict.fromkeys(out))
    singular = _sha40(payload.get("producer_git_sha"))
    _require(singular is not None, "RELEASE_INVALID_SOURCE_INTEGRITY")
    assert singular is not None
    return [singular]


def _validate_source_payload(
    payload: Mapping[str, Any],
    *,
    source_sha256: str,
    require_row_lists: bool = True,
) -> dict[str, Any]:
    for key in (
        "schedule_sha256",
        "activation_id",
        "starts_at",
        "stops_admitting_at",
    ):
        _require(key in payload, "RELEASE_INVALID_SOURCE_INTEGRITY")
    members = payload.get("members")
    observations = payload.get("observations")
    if require_row_lists:
        _require(
            isinstance(members, list) and isinstance(observations, list),
            "RELEASE_INVALID_SOURCE_INTEGRITY",
        )
    schedule_sha = str(payload["schedule_sha256"])
    _require(
        len(schedule_sha) == 64
        and all(c in "0123456789abcdef" for c in schedule_sha),
        "RELEASE_INVALID_SOURCE_INTEGRITY",
    )
    contributing = _contributing_producers(payload)
    singular = _sha40(payload.get("producer_git_sha"))
    if len(contributing) == 1:
        if singular is None:
            singular = contributing[0]
        _require(singular == contributing[0], "RELEASE_INVALID_SOURCE_INTEGRITY")
    else:
        # Multi-producer: a singular SHA would be false; omit it.
        _require(singular is None, "LIVE_SOURCE_LINEAGE_CONFLICT")
        singular = None
    schedule_producer = _sha40(payload.get("schedule_producer_git_sha")) or (
        contributing[0] if len(contributing) == 1 else None
    )
    starts = str(payload["starts_at"])
    stops = str(payload["stops_admitting_at"])
    _parse_utc(starts)
    _parse_utc(stops)
    out = {
        "schedule_sha256": schedule_sha,
        "activation_id": str(payload["activation_id"]),
        "starts_at": starts,
        "stops_admitting_at": stops,
        "source_sha256": source_sha256,
        "discovery_coverage_class": str(
            payload.get("discovery_coverage_class") or "DISCOVERY_COVERAGE_UNKNOWN"
        ),
        "open_publication": _require_closure_flag(payload, "open_publication"),
        "unresolved_due": _require_closure_flag(payload, "unresolved_due"),
        "in_flight": _require_closure_flag(payload, "in_flight"),
        "budget_blocked": _require_closure_flag(payload, "budget_blocked"),
        "contributing_producer_git_shas": contributing,
        "schedule_producer_git_sha": schedule_producer,
        "release_builder_git_sha": _sha40(payload.get("release_builder_git_sha")),
        "cohort_id": payload.get("cohort_id"),
        "window_start": payload.get("window_start"),
        "window_end_exclusive": payload.get("window_end_exclusive"),
        "closure_receipt_sha256": payload.get("closure_receipt_sha256"),
        "closure_receipt": payload.get("closure_receipt"),
        "closure_cutoff_at": payload.get("closure_cutoff_at"),
        "pending_due_for_cohort": payload.get("pending_due_for_cohort"),
        "claimed_or_in_flight": payload.get("claimed_or_in_flight"),
        "member_count": payload.get("member_count"),
        "observation_count": payload.get("observation_count"),
        "members_sha256": payload.get("members_sha256"),
        "observations_sha256": payload.get("observations_sha256"),
        "members_partition": payload.get("members_partition"),
        "observations_partition": payload.get("observations_partition"),
        "observation_schedule_partition": payload.get("observation_schedule_partition"),
        "observation_schedule_sha256": payload.get("observation_schedule_sha256"),
        "schema_version": payload.get("schema_version"),
        "source_representation": payload.get("source_representation"),
        "source_dir": payload.get("source_dir"),
    }
    if require_row_lists:
        out["members"] = members
        out["observations"] = observations
        out["source_representation"] = payload.get(
            "source_representation"
        ) or SOURCE_REPRESENTATION_LEGACY_JSON
    else:
        out["source_representation"] = str(
            payload.get("source_representation") or SOURCE_REPRESENTATION_BUNDLE
        )
    if singular is not None:
        out["producer_git_sha"] = singular
    return out


def _require_closure_flag(payload: Mapping[str, Any], key: str) -> bool:
    _require(key in payload, "CLOSED_RECEIPT_MISSING")
    value = payload[key]
    _require(isinstance(value, bool), "CLOSED_RECEIPT_MISSING")
    return value


def iter_source_member_rows(source: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    members = source.get("members")
    if isinstance(members, list):
        for item in members:
            if isinstance(item, Mapping):
                yield dict(item)
        return
    path = _source_members_parquet(source)
    if path is None:
        return
    for batch in iter_parquet_row_batches(path):
        for row in batch:
            yield member_from_parquet_row(row)


def iter_source_observation_rows(source: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    observations = source.get("observations")
    if isinstance(observations, list):
        for item in observations:
            if isinstance(item, Mapping):
                yield dict(item)
        return
    path = _source_observations_parquet(source)
    if path is None:
        return
    for batch in iter_parquet_row_batches(path):
        for row in batch:
            yield observation_from_parquet_row(row)


def _source_members_parquet(source: Mapping[str, Any]) -> Path | None:
    raw = source.get("members_partition")
    if isinstance(raw, str) and raw:
        path = Path(raw)
        if path.is_file():
            return path
    directory = source.get("source_dir")
    if isinstance(directory, str) and directory:
        path = Path(directory) / SOURCE_MEMBERS_NAME
        if path.is_file():
            return path
    return None


def _source_observations_parquet(source: Mapping[str, Any]) -> Path | None:
    raw = source.get("observations_partition")
    if isinstance(raw, str) and raw:
        path = Path(raw)
        if path.is_file():
            return path
    directory = source.get("source_dir")
    if isinstance(directory, str) and directory:
        path = Path(directory) / SOURCE_OBSERVATIONS_NAME
        if path.is_file():
            return path
    return None


def _load_source_bundle(manifest_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY") from exc
    _require(isinstance(payload, Mapping), "RELEASE_INVALID_SOURCE_INTEGRITY")
    _require(payload.get("schema") == SOURCE_BUNDLE_SCHEMA, "RELEASE_INVALID_SOURCE_INTEGRITY")
    source_dir = manifest_path.parent
    members_path = source_dir / SOURCE_MEMBERS_NAME
    obs_path = source_dir / SOURCE_OBSERVATIONS_NAME
    _require(members_path.is_file() and not members_path.is_symlink(), "RELEASE_INVALID_SOURCE_INTEGRITY")
    _require(obs_path.is_file() and not obs_path.is_symlink(), "RELEASE_INVALID_SOURCE_INTEGRITY")
    members_sha = sha256_file_streaming(members_path)
    obs_sha = sha256_file_streaming(obs_path)
    _require(members_sha == payload.get("members_sha256"), "RELEASE_INVALID_SOURCE_INTEGRITY")
    _require(obs_sha == payload.get("observations_sha256"), "RELEASE_INVALID_SOURCE_INTEGRITY")
    _require(
        parquet_row_count(members_path) == int(payload.get("member_count") or 0)
        and payload.get("member_count") is not None,
        "RELEASE_INVALID_SOURCE_INTEGRITY",
    )
    _require(
        parquet_row_count(obs_path) == int(payload.get("observation_count") or 0)
        and payload.get("observation_count") is not None,
        "RELEASE_INVALID_SOURCE_INTEGRITY",
    )
    version = str(payload.get("schema_version") or SOURCE_BUNDLE_SCHEMA_VERSION)
    if version == SOURCE_BUNDLE_SCHEMA_VERSION_SELF_CONTAINED:
        schedule_path = source_dir / SOURCE_SCHEDULE_NAME
        _require(
            schedule_path.is_file() and not schedule_path.is_symlink(),
            SCHEDULE_ARTIFACT_MISSING,
        )
        schedule_sha = sha256_file_streaming(schedule_path)
        _require(
            schedule_sha == payload.get("observation_schedule_sha256"),
            SCHEDULE_ARTIFACT_HASH_MISMATCH,
        )
        wanted = str(payload.get("schedule_sha256") or "")
        try:
            decode_schedule_artifact(
                schedule_path.read_bytes(),
                wanted_sha=wanted,
                expected_byte_sha256=schedule_sha,
            )
        except ValueError as exc:
            raise LiveCohortReleaseError(str(exc)) from exc
        payload = dict(payload)
        payload["observation_schedule_partition"] = str(schedule_path)
    payload = dict(payload)
    payload["members_partition"] = str(members_path)
    payload["observations_partition"] = str(obs_path)
    payload["source_dir"] = str(source_dir)
    payload["source_representation"] = SOURCE_REPRESENTATION_BUNDLE
    source_sha = str(payload.get("source_sha256") or "")
    identity = compute_source_identity(payload)
    _require(source_sha == identity, "RELEASE_INVALID_SOURCE_INTEGRITY")
    return _validate_source_payload(payload, source_sha256=source_sha, require_row_lists=False)


def load_observation_rdp_source(
    observation_rdp_root: Path,
    *,
    cohort_id: str | None = None,
) -> dict[str, Any]:
    """Load previously built live source snapshot from Observation RDP."""
    root = Path(observation_rdp_root)
    if cohort_id:
        manifest_path = cohort_source_manifest_path(root, cohort_id)
        if manifest_path.is_file() and not manifest_path.is_symlink():
            return _load_source_bundle(manifest_path)
    path = (
        cohort_snapshot_path(root, cohort_id)
        if cohort_id
        else root / OBSERVATION_RDP_REBUILD_NAME
    )
    if (not path.is_file() or path.is_symlink()) and cohort_id:
        fallback = root / OBSERVATION_RDP_REBUILD_NAME
        if fallback.is_file() and not fallback.is_symlink():
            try:
                if fallback.stat().st_size > LEGACY_SOURCE_JSON_MAX_BYTES:
                    raise LiveCohortReleaseError("SOURCE_SNAPSHOT_JSON_UNSAFE")
                preview = json.loads(fallback.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY") from exc
            if not isinstance(preview, Mapping):
                raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY")
            labeled = str(preview.get("cohort_id") or "")
            if labeled and labeled != cohort_id:
                raise LiveCohortReleaseError("IDENTITY_CONFLICT")
            start, end = cohort_window_bounds(cohort_id)
            for member in preview.get("members") or []:
                if not isinstance(member, Mapping):
                    continue
                admission = _member_admission_instant(member)
                if admission is not None and not (start <= admission < end):
                    raise LiveCohortReleaseError("IDENTITY_CONFLICT")
            path = fallback
    if not path.is_file() or path.is_symlink():
        raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY")
    try:
        if path.stat().st_size > LEGACY_SOURCE_JSON_MAX_BYTES:
            raise LiveCohortReleaseError("SOURCE_SNAPSHOT_JSON_UNSAFE")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY") from exc
    _require(isinstance(payload, Mapping), "RELEASE_INVALID_SOURCE_INTEGRITY")
    return _validate_source_payload(
        payload, source_sha256=sha256_file_streaming(path), require_row_lists=True
    )


def _map_selected_or_excluded(candidate_state: str | None, membership_state: str | None) -> str:
    cand = str(candidate_state or "")
    memb = str(membership_state or "")
    if cand in _SELECTED_CANDIDATE_STATES or memb in {"ADMITTED", "SAMPLED_MEMBER", "SCHEDULED", "OBSERVED"}:
        if cand in _HASH_EXCLUDE | _CAPACITY_EXCLUDE | _PREDICATE_EXCLUDE | _X_INELIGIBLE:
            return "EXCLUDED"
        if memb in {
            "PREDICATE_REJECTED",
            "CAPACITY_EXCLUDED",
            "X_POPULATION_INELIGIBLE",
        }:
            return "EXCLUDED"
        if cand in _SELECTED_CANDIDATE_STATES or memb in {
            "ADMITTED",
            "SAMPLED_MEMBER",
            "SCHEDULED",
            "OBSERVED",
            "MISSING_TYPED",
            "DISAPPEARED",
            "CENSORED",
            "CENSORED_LATE",
        }:
            return "SELECTED"
    if cand in _HASH_EXCLUDE | _CAPACITY_EXCLUDE | _PREDICATE_EXCLUDE | _X_INELIGIBLE:
        return "EXCLUDED"
    if memb in {"PREDICATE_REJECTED", "CAPACITY_EXCLUDED", "X_POPULATION_INELIGIBLE", "DISCOVERED"}:
        return "EXCLUDED" if memb != "DISCOVERED" else "UNKNOWN"
    return "UNKNOWN"


def _map_denominator_state(
    *,
    candidate_state: str | None,
    membership_state: str | None,
    selected_or_excluded: str,
) -> str:
    cand = str(candidate_state or "")
    memb = str(membership_state or "")
    if memb == "OBSERVED":
        return "observed"
    if memb == "MISSING_TYPED":
        return "typed_missing"
    if memb == "DISAPPEARED":
        return "disappeared"
    if memb in {"CENSORED_LATE", "CENSORED"}:
        return "censored_late"
    if cand in _X_INELIGIBLE or memb == "X_POPULATION_INELIGIBLE":
        return "x_ineligible"
    if cand in _CAPACITY_EXCLUDE or memb == "CAPACITY_EXCLUDED":
        return "capacity_excluded"
    if cand in _HASH_EXCLUDE:
        return "hash_not_selected"
    if cand in _PREDICATE_EXCLUDE or memb == "PREDICATE_REJECTED":
        return "unknown"
    if selected_or_excluded == "SELECTED":
        return "sampled"
    if cand in {"CANDIDATE", "DISCOVERED"} or memb == "DISCOVERED":
        return "discovered"
    if selected_or_excluded in {"UNKNOWN", "EXCLUDED"}:
        return "unknown"
    return "unknown"


def _map_exclusion_reason(
    *,
    selected_or_excluded: str,
    candidate_state: str | None,
    membership_state: str | None,
    explicit: object,
) -> str | None:
    if explicit is not None and str(explicit):
        return str(explicit)
    if selected_or_excluded != "EXCLUDED":
        return None
    cand = str(candidate_state or "")
    memb = str(membership_state or "")
    if cand in _HASH_EXCLUDE:
        return "HASH_NOT_SELECTED"
    if cand in _CAPACITY_EXCLUDE or memb == "CAPACITY_EXCLUDED":
        return "CAPACITY_EXCLUDED"
    if cand in _X_INELIGIBLE or memb == "X_POPULATION_INELIGIBLE":
        return "X_POPULATION_INELIGIBLE"
    if cand in _PREDICATE_EXCLUDE or memb == "PREDICATE_REJECTED":
        return "PREDICATE_REJECTED"
    return "EXCLUDED"


def _normalize_member_row(
    row: Mapping[str, Any],
    *,
    schedule_sha256: str,
    activation_id: str,
    sampling_policy: str | None,
    sampling_seed_default: str | None,
    inclusion_probability_default: str | None,
) -> dict[str, Any] | None:
    if str(row.get("activation_id") or "") != activation_id:
        return None
    if str(row.get("schedule_sha256") or "") not in {"", schedule_sha256}:
        return None
    entity = str(row.get("entity_id") or row.get("mint") or "")
    if not entity:
        return None
    admission_instant = resolve_cohort_admission_instant(row)
    if admission_instant is None:
        return None
    admission = None
    for key in ADMISSION_REPRESENTATIONS:
        raw = row.get(key)
        if isinstance(raw, str) and raw:
            admission = raw
            break
    if admission is None:
        admission = _render_utc(admission_instant)
    candidate_state = row.get("candidate_state")
    membership_state = row.get("membership_state")
    selected = row.get("selected_or_excluded")
    if not isinstance(selected, str) or not selected:
        selected = _map_selected_or_excluded(
            str(candidate_state) if candidate_state is not None else None,
            str(membership_state) if membership_state is not None else None,
        )
    denom = row.get("denominator_state")
    if not isinstance(denom, str) or not denom:
        denom = _map_denominator_state(
            candidate_state=str(candidate_state) if candidate_state is not None else None,
            membership_state=str(membership_state) if membership_state is not None else None,
            selected_or_excluded=selected,
        )
    return {
        "mint": entity,
        "entity_id": entity,
        "activation_id": activation_id,
        COHORT_ADMISSION_FIELD: admission,
        "authoritative_anchor": row.get("authoritative_anchor") or row.get("event_time"),
        "candidate_state": candidate_state or "UNKNOWN",
        "membership_state": membership_state or "UNKNOWN",
        "denominator_state": denom,
        "sampling_policy": row.get("sampling_policy") or sampling_policy,
        "sampling_seed": row.get("sampling_seed") or sampling_seed_default,
        "inclusion_probability": str(
            (
                row.get("inclusion_probability")
                if row.get("inclusion_probability") not in (None, "")
                else (inclusion_probability_default or "")
            )
            or ""
        ),
        "selected_or_excluded": selected,
        "exclusion_reason": _map_exclusion_reason(
            selected_or_excluded=selected,
            candidate_state=str(candidate_state) if candidate_state is not None else None,
            membership_state=str(membership_state) if membership_state is not None else None,
            explicit=row.get("exclusion_reason"),
        ),
        "source_request_sha256": row.get("source_request_sha256")
        or row.get("request_sha256"),
        "source_response_sha256": row.get("source_response_sha256")
        or row.get("response_sha256"),
        "discovery_coverage_class": row.get("discovery_coverage_class"),
    }


def _explode_observation_rows(
    row: Mapping[str, Any],
    *,
    schedule_sha256: str,
    activation_id: str,
) -> list[dict[str, Any]]:
    if str(row.get("activation_id") or "") != activation_id:
        return []
    if str(row.get("schedule_sha256") or "") not in {"", schedule_sha256}:
        return []
    mint = str(row.get("entity_id") or row.get("mint") or "")
    if not mint:
        return []
    point_id = str(row.get("point_id") or "")
    if not point_id or point_id in {"R0", "MEMBER"}:
        return []
    primitive_id = str(row.get("primitive_id") or "")
    base = {
        "mint": mint,
        "entity_id": mint,
        "point_id": point_id,
        "primitive_id": primitive_id,
        "event_time": row.get("event_time"),
        "request_started_at": row.get("request_started_at"),
        "response_received_at": row.get("response_received_at"),
        "first_reliable_available_at": row.get("first_reliable_available_at"),
        "request_sha256": row.get("request_sha256"),
        "response_sha256": row.get("response_sha256"),
        "call_occurrence_id": row.get("call_occurrence_id"),
        "http_status": row.get("http_status"),
        "http_class": row.get("http_class"),
    }
    field_values = row.get("field_values")
    out: list[dict[str, Any]] = []
    if isinstance(field_values, list) and field_values:
        for value in field_values:
            if not isinstance(value, Mapping):
                continue
            field_id = str(value.get("field_id") or "")
            if not field_id:
                continue
            typed = value.get("typed_value_or_null")
            if "typed_value" in value and typed is None:
                typed = value.get("typed_value")
            if "missing_reason" in value:
                missing_reason = value.get("missing_reason")
            else:
                missing_reason = row.get("missing_reason")
            out.append(
                {
                    **base,
                    "field_id": field_id,
                    "value_kind": value.get("value_kind"),
                    "typed_value": typed,
                    "state": value.get("state") or row.get("state"),
                    "missing_reason": missing_reason,
                    "event_time": value.get("event_time", base["event_time"]),
                    "first_reliable_available_at": value.get(
                        "first_reliable_available_at",
                        base["first_reliable_available_at"],
                    ),
                    "request_sha256": value.get("request_sha256", base["request_sha256"]),
                    "call_occurrence_id": value.get(
                        "call_occurrence_id", base["call_occurrence_id"]
                    ),
                    "primitive_id": value.get("primitive_id") or primitive_id,
                    "point_id": value.get("point_id") or point_id,
                }
            )
        return out
    # Already-flat row (legacy snapshot helper).
    if row.get("field_id"):
        out.append(
            {
                **base,
                "field_id": row.get("field_id"),
                "value_kind": row.get("value_kind"),
                "typed_value": row.get("typed_value"),
                "state": row.get("state"),
                "missing_reason": row.get("missing_reason"),
            }
        )
    return out


def _event_activation_id(record: Any, payload: Mapping[str, Any]) -> str:
    """Prefer research-event run_id; fall back to payload activation_id only."""
    run_id = str(getattr(record, "run_id", None) or "").strip()
    if run_id:
        return run_id
    return str(payload.get("activation_id") or "").strip()


def _schedule_document_activation_id(document: Mapping[str, Any]) -> str:
    activation = document.get("activation")
    if not isinstance(activation, Mapping):
        return ""
    return str(activation.get("activation_id") or "").strip()


def _worst_coverage(classes: Sequence[str]) -> str:
    present = [item.strip() for item in classes if isinstance(item, str) and item.strip()]
    if not present:
        return "DISCOVERY_COVERAGE_UNKNOWN"
    return min(
        present,
        key=lambda item: _COVERAGE_RANK.get(item, _COVERAGE_RANK["DISCOVERY_COVERAGE_UNKNOWN"]),
    )


def resolve_cohort_admission_instant(row: Mapping[str, Any]) -> datetime | None:
    """Canonical cohort admission clock. `first_seen_at` is not a fallback."""
    seen: list[datetime] = []
    for key in ADMISSION_REPRESENTATIONS:
        raw = row.get(key)
        if raw is None or raw == "":
            continue
        if not isinstance(raw, str):
            return None
        try:
            instant = _parse_utc(raw)
        except Exception:
            return None
        seen.append(instant)
    if not seen:
        return None
    if any(item != seen[0] for item in seen):
        return None
    return seen[0]


def classify_cohort_admission_clock(row: Mapping[str, Any]) -> str:
    """Return ok, missing, or invalid. `first_seen_at` is not an admission key."""
    present = False
    for key in ADMISSION_REPRESENTATIONS:
        raw = row.get(key)
        if raw is None or raw == "":
            continue
        present = True
    if resolve_cohort_admission_instant(row) is not None:
        return "ok"
    return "invalid" if present else "missing"


def _member_admission_instant(row: Mapping[str, Any]) -> datetime | None:
    return resolve_cohort_admission_instant(row)


def _lifecycle_row_at_or_before_cutoff(
    row: Mapping[str, Any], cutoff_at: datetime | None
) -> bool:
    if cutoff_at is None:
        return True
    raw = row.get("effective_at")
    if not isinstance(raw, str) or not raw:
        return False
    try:
        instant = _parse_utc(raw)
    except Exception:
        return False
    return instant <= cutoff_at


def _producer_fields(source: Mapping[str, Any]) -> dict[str, Any]:
    contributing = list(
        source.get("contributing_producer_git_shas") or _contributing_producers(source)
    )
    out: dict[str, Any] = {
        "contributing_producer_git_shas": contributing,
        "schedule_producer_git_sha": source.get("schedule_producer_git_sha"),
        "release_builder_git_sha": source.get("release_builder_git_sha"),
    }
    if len(contributing) == 1:
        out["producer_git_sha"] = contributing[0]
    return out


def _apply_closure_receipt(
    *,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str,
    closure_receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    _require(isinstance(closure_receipt, Mapping), "CLOSED_RECEIPT_MISSING")
    assert closure_receipt is not None
    _require(
        str(closure_receipt.get("schedule_sha256") or "") == schedule_sha256
        and str(closure_receipt.get("activation_id") or "") == activation_id
        and str(closure_receipt.get("cohort_id") or "") == cohort_id,
        "CLOSED_RECEIPT_IDENTITY_MISMATCH",
    )
    receipt_sha = str(closure_receipt.get("closure_identity_sha256") or "")
    if len(receipt_sha) != 64:
        receipt_sha = str(closure_receipt.get("receipt_sha256") or "")
    _require(len(receipt_sha) == 64, "CLOSED_RECEIPT_IDENTITY_MISMATCH")
    cutoff_raw = str(closure_receipt.get("closure_cutoff_at") or "")
    _require(bool(cutoff_raw), "CLOSED_RECEIPT_INCOMPLETE")
    try:
        _parse_utc(cutoff_raw)
    except Exception as exc:
        raise LiveCohortReleaseError("CLOSED_RECEIPT_INCOMPLETE") from exc
    return {
        "open_publication": _require_closure_flag(closure_receipt, "open_publication"),
        "unresolved_due": _require_closure_flag(closure_receipt, "unresolved_due"),
        "in_flight": _require_closure_flag(closure_receipt, "in_flight"),
        "budget_blocked": _require_closure_flag(closure_receipt, "budget_blocked"),
        "closure_receipt_sha256": receipt_sha,
        "closure_cutoff_at": cutoff_raw,
        "pending_due_for_cohort": _require_closure_int(
            closure_receipt, "pending_due_for_cohort"
        ),
        "claimed_or_in_flight": _require_closure_int(
            closure_receipt, "claimed_or_in_flight"
        ),
    }


def _require_closure_int(payload: Mapping[str, Any], key: str) -> int:
    _require(key in payload, "CLOSED_RECEIPT_INCOMPLETE")
    value = payload[key]
    _require(isinstance(value, int) and not isinstance(value, bool), "CLOSED_RECEIPT_INCOMPLETE")
    return value


def bound_schedule_from_rdp(
    observation_rdp_root: Path,
    *,
    schedule_sha256: str,
    activation_id: str,
) -> tuple[dict[str, Any], str | None, list[dict[str, Any]]]:
    """Public schedule/activation bind used by list/publish."""
    return _lineage_from_rdp(
        observation_rdp_root,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        schedule_only=True,
    )


def _apply_research_bound_telemetry(telemetry: ResearchStoreBoundTelemetry) -> None:
    note_counter(
        "research_manifest_headers_scanned",
        telemetry.research_manifest_headers_scanned,
    )
    note_counter(
        "research_event_partitions_opened",
        telemetry.research_event_partitions_opened,
    )
    note_counter(
        "research_event_records_decoded",
        telemetry.research_event_records_decoded,
    )
    note_counter(
        "research_event_payload_bytes_read",
        telemetry.research_event_payload_bytes_read,
    )
    if telemetry.used_bounded_lifecycle_route:
        note_counter("research_store_bounded_route", 1)
    if telemetry.full_committed_payload_scan:
        note_counter("research_store_full_committed_scan", 1)
    note_counter(
        "research_event_partitions_skipped_by_time",
        telemetry.research_event_partitions_skipped_by_time,
    )
    note_counter(
        "research_event_partitions_opened_unknown_bounds",
        telemetry.research_event_partitions_opened_unknown_bounds,
    )
    note_counter(
        "research_event_lifecycle_partitions_total",
        telemetry.research_event_lifecycle_partitions_total,
    )


def _lineage_from_rdp(
    observation_rdp_root: Path,
    *,
    schedule_sha256: str,
    activation_id: str,
    window_start: datetime | None = None,
    closure_cutoff: datetime | None = None,
    schedule_only: bool = False,
) -> tuple[dict[str, Any], str | None, list[dict[str, Any]]]:
    """Bind schedule by digest using ResearchStore partition manifests.

    Full historical payload replay is not the operator path. When a cohort
    window is supplied, only overlapping partitions plus a newest-first
    predecessor search are verified/decoded.
    """
    global _LAST_BOUNDED_RESEARCH_RELS
    wanted = str(activation_id or "").strip()
    _require(bool(wanted), "LIVE_SOURCE_ACTIVATION_MISSING")
    try:
        store = ExistingResearchStoreReader(Path(observation_rdp_root))
    except ResearchStoreError as exc:
        raise LiveCohortReleaseError("LIVE_SOURCE_RDP_UNREADABLE") from exc
    try:
        records, telemetry = store.iter_lifecycle_records_bounded(
            schedule_sha256=schedule_sha256,
            activation_id=wanted,
            window_start=window_start,
            closure_cutoff=closure_cutoff,
            schedule_only=schedule_only,
        )
    except ResearchStoreError as exc:
        raise LiveCohortReleaseError("LIVE_SOURCE_RDP_UNREADABLE") from exc
    _LAST_BOUNDED_RESEARCH_RELS = tuple(telemetry.selected_parquet_locations) + tuple(
        telemetry.selected_partition_manifest_rels
    )
    _apply_research_bound_telemetry(telemetry)
    schedule_docs: list[dict[str, Any]] = []
    schedule_producers: set[str] = set()
    activation_evidence = False
    lifecycle_rows: list[dict[str, Any]] = []
    for record in records:
        kind = str(record.record_kind)
        try:
            payload = json.loads(record.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        digest = str(payload.get("schedule_sha256") or "")
        if digest != schedule_sha256:
            continue
        producer = _sha40(record.producer_git_sha)
        event_activation = _event_activation_id(record, payload)
        if kind == "OBSERVATION_SCHEDULE":
            document = payload.get("schedule")
            if not isinstance(document, Mapping):
                continue
            schedule_docs.append(dict(document))
            if producer:
                schedule_producers.add(producer)
            continue
        if kind in {
            "OBSERVATION_SCHEDULE_STATE",
            "OBSERVATION_BATCH",
            "OBSERVATION_MEMBER_BATCH",
            "OBSERVATION_PANEL_SNAPSHOT",
        }:
            if event_activation == wanted:
                activation_evidence = True
                lifecycle_rows.append(
                    {
                        "kind": kind,
                        "producer_git_sha": producer,
                        "effective_at": str(getattr(record, "effective_at", "") or ""),
                        "payload": dict(payload),
                    }
                )
    if len(schedule_docs) > 1:
        encoded = {
            json.dumps(item, sort_keys=True, separators=(",", ":"))
            for item in schedule_docs
        }
        if len(encoded) > 1:
            raise LiveCohortReleaseError("IDENTITY_CONFLICT")
    _require(bool(schedule_docs), "LIVE_SOURCE_SCHEDULE_MISSING")
    schedule_doc = schedule_docs[0]
    activation = schedule_doc.get("activation")
    _require(isinstance(activation, Mapping), "LIVE_SOURCE_ACTIVATION_MISSING")
    sched_activation = _schedule_document_activation_id(schedule_doc)
    if sched_activation and sched_activation != wanted:
        raise LiveCohortReleaseError("IDENTITY_CONFLICT")
    if sched_activation == wanted:
        activation_evidence = True
    if not schedule_only and not activation_evidence:
        raise LiveCohortReleaseError("LIVE_SOURCE_ACTIVATION_MISSING")
    schedule_producer = None
    if len(schedule_producers) == 1:
        schedule_producer = next(iter(schedule_producers))
    elif len(schedule_producers) > 1:
        raise LiveCohortReleaseError("IDENTITY_CONFLICT")
    return schedule_doc, schedule_producer, lifecycle_rows


def _encode_bound_schedule(
    document: Mapping[str, Any], *, wanted_sha: str
) -> tuple[dict[str, Any], bytes, str]:
    try:
        return encode_schedule_artifact(document, wanted_sha=wanted_sha)
    except ValueError as exc:
        raise LiveCohortReleaseError(str(exc)) from exc


def _try_resolve_schedule_for_seal(
    source: Mapping[str, Any],
    observation_rdp_root: Path,
    *,
    wanted_sha: str,
    activation_id: str,
) -> tuple[dict[str, Any], bytes, str] | None:
    """Prefer source-bundle artifact; RDP document is source-time fallback only."""

    source_dir = source.get("source_dir")
    if isinstance(source_dir, str) and source_dir:
        artifact = Path(source_dir) / SOURCE_SCHEDULE_NAME
        if artifact.is_file() and not artifact.is_symlink():
            expected = str(source.get("observation_schedule_sha256") or "") or None
            try:
                document = decode_schedule_artifact(
                    artifact.read_bytes(),
                    wanted_sha=wanted_sha,
                    expected_byte_sha256=expected,
                )
            except ValueError as exc:
                raise LiveCohortReleaseError(str(exc)) from exc
            return _encode_bound_schedule(document, wanted_sha=wanted_sha)
    embedded = source.get("observation_schedule")
    if isinstance(embedded, Mapping):
        return _encode_bound_schedule(embedded, wanted_sha=wanted_sha)
    try:
        rdp_doc, _, _ = _lineage_from_rdp(
            observation_rdp_root,
            schedule_sha256=wanted_sha,
            activation_id=activation_id,
        )
    except (LiveCohortReleaseError, DiscoveryReleaseError) as exc:
        code = str(exc)
        if code == "IDENTITY_CONFLICT":
            raise LiveCohortReleaseError(SCHEDULE_DOCUMENT_CONFLICT) from exc
        if code in {
            "LIVE_SOURCE_SCHEDULE_MISSING",
            "LIVE_SOURCE_RDP_UNREADABLE",
            "LIVE_SOURCE_ACTIVATION_MISSING",
        }:
            return None
        raise
    return _encode_bound_schedule(rdp_doc, wanted_sha=wanted_sha)


def _census_schedule_identity(census_path: Path, wanted_sha: str) -> None:
    table = pq.read_table(census_path, columns=["source_schedule_sha256"])
    unique = {
        str(value)
        for value in table.column("source_schedule_sha256").to_pylist()
        if value
    }
    _require(unique == {wanted_sha}, CENSUS_SCHEDULE_SHA_MISMATCH)


def _iter_member_batches(
    observation_rdp_root: Path,
    location: str,
    *,
    columns: Sequence[str] | None = None,
    removed_out: list[dict[str, Any]] | None = None,
) -> Iterator[list[dict[str, Any]]]:
    note_member_file_open()
    if columns is None:
        note_member_full_column_scan()
    try:
        for batch in iter_member_row_batches_for_location(
            Path(observation_rdp_root),
            location,
            columns=columns,
            removed_out=removed_out,
        ):
            if columns is None:
                note_full_member_rows(len(batch))
            else:
                note_admission_probe_rows(len(batch))
            yield batch
    except (MembersDeltaError, OSError, pa.ArrowException) as exc:
        raise LiveCohortReleaseError("LIVE_SOURCE_MEMBER_PROVENANCE_UNREADABLE") from exc


def _member_batch_window_flags(
    observation_rdp_root: Path,
    location: str,
    *,
    window_start: datetime,
    window_end: datetime,
    cached_flags: dict[str, tuple[bool, bool]] | None = None,
) -> tuple[bool, bool]:
    if cached_flags is not None and location in cached_flags:
        return cached_flags[location]
    has_in = False
    later = False
    columns = ("entity_id", "mint", *ADMISSION_REPRESENTATIONS)
    for batch in _iter_member_batches(observation_rdp_root, location, columns=columns):
        for member in batch:
            admission = resolve_cohort_admission_instant(member)
            if admission is None:
                continue
            if window_start <= admission < window_end:
                has_in = True
            elif admission >= window_end:
                later = True
            if has_in and later:
                if cached_flags is not None:
                    cached_flags[location] = (True, True)
                return True, True
    if cached_flags is not None:
        cached_flags[location] = (has_in, later)
    return has_in, later


def _cohort_contributing_lineage(
    observation_rdp_root: Path,
    *,
    lifecycle_rows: Sequence[Mapping[str, Any]],
    window_start: datetime,
    window_end: datetime,
    mint_is_member: Callable[[str], bool],
    cutoff_at: datetime | None = None,
    location_flags: dict[str, tuple[bool, bool]] | None = None,
    include_observations: bool = True,
) -> tuple[list[str], str, set[str]]:
    contributing: set[str] = set()
    coverages: list[str] = []
    contributing_manifests: set[str] = set()
    for row in lifecycle_rows:
        if str(row.get("kind") or "") != "OBSERVATION_MEMBER_BATCH":
            continue
        if not _lifecycle_row_at_or_before_cutoff(row, cutoff_at):
            continue
        payload = row.get("payload")
        producer = _sha40(row.get("producer_git_sha"))
        if not isinstance(payload, Mapping):
            continue
        location = str(payload.get("member_location") or "")
        if not location:
            continue
        if location_flags is not None and location not in location_flags:
            # Do not independently reconstruct uncached SNAPSHOT_PLUS_DELTA
            # locations on the bounded path.
            continue
        has_in, later = _member_batch_window_flags(
            observation_rdp_root,
            location,
            window_start=window_start,
            window_end=window_end,
            cached_flags=location_flags,
        )
        if not has_in:
            continue
        manifest = str(payload.get("dataset_manifest_id") or "")
        if manifest:
            contributing_manifests.add(manifest)
        raw = payload.get("discovery_coverage_class")
        if isinstance(raw, str) and raw.strip():
            coverages.append(raw.strip())
        if later:
            continue
        if producer:
            contributing.add(producer)
    if include_observations:
        for row in lifecycle_rows:
            kind = str(row.get("kind") or "")
            payload = row.get("payload")
            producer = _sha40(row.get("producer_git_sha"))
            if kind != "OBSERVATION_BATCH":
                continue
            if not _lifecycle_row_at_or_before_cutoff(row, cutoff_at):
                continue
            if not isinstance(payload, Mapping):
                continue
            location = str(
                payload.get("observation_location")
                or payload.get("logical_location")
                or ""
            )
            hits_c1 = False
            if location:
                try:
                    path = _contained_data_path(Path(observation_rdp_root), location)
                except MembersDeltaError as exc:
                    raise LiveCohortReleaseError(
                        "LIVE_SOURCE_MEMBER_PROVENANCE_UNREADABLE"
                    ) from exc
                if path.is_file():
                    try:
                        for batch in iter_parquet_row_batches(
                            path, columns=("entity_id", "mint")
                        ):
                            note_observation_rows(len(batch))
                            for item in batch:
                                mint = str(item.get("entity_id") or item.get("mint") or "")
                                if mint and mint_is_member(mint):
                                    hits_c1 = True
                                    break
                            if hits_c1:
                                break
                    except (OSError, pa.ArrowException) as exc:
                        raise LiveCohortReleaseError(
                            "LIVE_SOURCE_MEMBER_PROVENANCE_UNREADABLE"
                        ) from exc
            manifest = str(payload.get("dataset_manifest_id") or "")
            if manifest:
                contributing_manifests.add(manifest)
            if hits_c1 and producer:
                contributing.add(producer)
            raw = payload.get("discovery_coverage_class")
            if isinstance(raw, str) and raw.strip():
                coverages.append(raw.strip())
    if include_observations:
        _require(bool(contributing), "LIVE_SOURCE_PRODUCER_MISSING")
    return sorted(contributing), _worst_coverage(coverages), contributing_manifests


def _member_batch_is_cohort_pure(
    members: Sequence[Any],
    *,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    has_in = False
    later = False
    for member in members:
        if not isinstance(member, Mapping):
            continue
        admission = _member_admission_instant(member)
        if admission is None:
            continue
        if window_start <= admission < window_end:
            has_in = True
        elif admission >= window_end:
            later = True
    return has_in and not later


def _observation_instant(row: Mapping[str, Any]) -> datetime | None:
    for key in (
        COHORT_ADMISSION_FIELD,
        "first_reliable_available_at",
        "event_time",
        "response_received_at",
        "request_started_at",
    ):
        raw = row.get(key)
        if isinstance(raw, str) and raw:
            try:
                return _parse_utc(raw)
            except Exception:
                continue
    return None


def _cohort_members_into_sqlite(
    observation_rdp_root: Path,
    *,
    conn: Any,
    lifecycle_rows: Sequence[Mapping[str, Any]],
    window_start: datetime,
    window_end: datetime,
    schedule_sha256: str,
    activation_id: str,
    sampling_policy: str | None,
    sampling_seed: str | None,
    inclusion_probability: str | None,
    cutoff_at: datetime | None = None,
    location_flags: dict[str, tuple[bool, bool]] | None = None,
    replay_dir: Path | None = None,
    progress: MaterializationProgress | None = None,
    wall: WallBudget | None = None,
) -> tuple[set[str], int]:
    """Materialize window membership with one prefix walk per SNAPSHOT_PLUS_DELTA unit."""
    conn.execute(
        """
        CREATE TABLE members (
            mint TEXT PRIMARY KEY,
            admission TEXT NOT NULL,
            producer_git_sha TEXT,
            payload_json TEXT NOT NULL,
            source_effective_at TEXT NOT NULL,
            source_index INTEGER NOT NULL
        )
        """
    )
    flags = location_flags if location_flags is not None else {}
    selected, _predecessors = select_member_batches(
        lifecycle_rows,
        window_start=window_start,
        closure_cutoff=cutoff_at,
    )
    note_counter("pit_targets_after_bound", len(selected))
    winning_producers: set[str] = set()

    def _ingest(
        member: Mapping[str, Any],
        producer_sha: str | None,
        *,
        rank_effective: str,
        rank_index: int,
    ) -> tuple[bool, bool]:
        if not isinstance(member, Mapping):
            return False, False
        row = {
            key: value
            for key, value in member.items()
            if key != "_delta_removed_at_seq"
        }
        admission = resolve_cohort_admission_instant(row)
        loc_has_in = False
        loc_later = False
        if admission is not None:
            if window_start <= admission < window_end:
                loc_has_in = True
            elif admission >= window_end:
                loc_later = True
        if admission is None or not (window_start <= admission < window_end):
            return loc_has_in, loc_later
        normalized = _normalize_member_row(
            row,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            sampling_policy=sampling_policy,
            sampling_seed_default=sampling_seed,
            inclusion_probability_default=inclusion_probability,
        )
        if normalized is None:
            return loc_has_in, loc_later
        entity = str(normalized.get("mint") or "")
        if not entity:
            return loc_has_in, loc_later
        conn.execute(
            """
            INSERT INTO members(
                mint, admission, producer_git_sha, payload_json,
                source_effective_at, source_index
            ) VALUES (?,?,?,?,?,?)
            ON CONFLICT(mint) DO UPDATE SET
                admission=excluded.admission,
                producer_git_sha=excluded.producer_git_sha,
                payload_json=excluded.payload_json,
                source_effective_at=excluded.source_effective_at,
                source_index=excluded.source_index
            WHERE excluded.source_effective_at > members.source_effective_at
               OR (
                    excluded.source_effective_at = members.source_effective_at
                    AND excluded.source_index > members.source_index
               )
            """,
            (
                entity,
                str(normalized.get(COHORT_ADMISSION_FIELD) or ""),
                producer_sha,
                json.dumps(normalized, sort_keys=True, separators=(",", ":")),
                rank_effective,
                int(rank_index),
            ),
        )
        if int(conn.execute("SELECT changes()").fetchone()[0]) == 1 and producer_sha:
            winning_producers.add(producer_sha)
        note_counter("candidate_member_rows_consumed", 1)
        return loc_has_in, loc_later

    unit_groups: dict[str, dict[str, Any]] = {}
    legacy_seen: dict[str, list[dict[str, Any]]] = {}
    slow_targets: list[dict[str, Any]] = []
    for row in selected:
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            continue
        location = str(payload.get("member_location") or "")
        try:
            info = inspect_member_target(observation_rdp_root, location)
        except BoundedMaterializationError as exc:
            raise LiveCohortReleaseError(str(exc)) from exc
        rank_effective = str(row.get("effective_at") or "")
        rank_index = int(row.get("_source_index") or 0)
        producer = _sha40(row.get("producer_git_sha"))
        target = {
            "row": row,
            "location": location,
            "producer": producer,
            "rank_effective": rank_effective,
            "rank_index": rank_index,
            "info": info,
        }
        if info.get("snapshot_plus_delta") and info.get("seq") is not None:
            unit_rel = str(info.get("unit_rel") or "")
            group = unit_groups.setdefault(
                unit_rel,
                {"unit": info.get("unit"), "targets": []},
            )
            group["targets"].append(target)
            continue
        if info.get("legacy"):
            legacy_seen.setdefault(location, []).append(target)
            continue
        slow_targets.append(target)

    if slow_targets:
        raise LiveCohortReleaseError("UNBOUNDED_MATERIALIZATION_PLAN")

    note_counter("units_considered", len(unit_groups))
    if progress is not None:
        progress.units_total = len(unit_groups)
        progress.pit_targets_total = len(selected)
        progress.delta_files_planned = sum(
            max((int(t["info"]["seq"]) for t in group["targets"]), default=0)
            for group in unit_groups.values()
        )
        progress.stage = "members"
        progress.write()

    for unit_rel, group in unit_groups.items():
        if wall is not None:
            wall.check(stage="members_unit")
        unit = group["unit"]
        if not isinstance(unit, Mapping):
            raise LiveCohortReleaseError("LIVE_SOURCE_MEMBER_PROVENANCE_UNREADABLE")
        by_seq: dict[int, list[dict[str, Any]]] = {}
        for target in group["targets"]:
            seq = int(target["info"]["seq"])
            by_seq.setdefault(seq, []).append(target)
        seqs = sorted(by_seq)
        replay_path = None
        if replay_dir is not None:
            safe = unit_rel.replace("/", "_").replace("\\", "_")
            replay_path = Path(replay_dir) / f"replay-{safe}.sqlite"
        else:
            handle, name = tempfile.mkstemp(prefix="bounded-replay-", suffix=".sqlite")
            os.close(handle)
            replay_path = Path(name)
        replay_conn: Any = None
        last_bytes = 0
        try:
            walker = prefix_walk_unit(
                Path(observation_rdp_root),
                unit,
                seqs,
                spill_path=replay_path,
            )
            for seq, replay_conn, dirty, _fp, payload_bytes in walker:
                increment = max(0, int(payload_bytes) - last_bytes)
                last_bytes = int(payload_bytes)
                note_counter("member_payload_bytes_read", increment)
                if progress is not None:
                    progress.member_payload_bytes_read += increment
                    progress.pit_targets_consumed += len(by_seq.get(seq, ()))
                    progress.write()
                if dirty is None:
                    note_counter("full_population_scans", 1)
                    note_member_full_column_scan()
                    rows = [
                        dict(pickle.loads(blob))
                        for (blob,) in replay_conn.execute(
                            "SELECT payload FROM members ORDER BY entity_id"
                        )
                    ]
                    note_full_member_rows(len(rows))
                else:
                    rows = []
                    for entity_id in dirty:
                        loaded = replay_conn.execute(
                            "SELECT payload FROM members WHERE entity_id=?",
                            (entity_id,),
                        ).fetchone()
                        if loaded is None:
                            continue
                        rows.append(dict(pickle.loads(loaded[0])))
                for target in by_seq.get(seq, ()):
                    loc_has_in = False
                    loc_later = False
                    for member in rows:
                        if not isinstance(member, Mapping):
                            continue
                        has_in, later = _ingest(
                            member,
                            target["producer"],
                            rank_effective=target["rank_effective"],
                            rank_index=target["rank_index"],
                        )
                        loc_has_in = loc_has_in or has_in
                        loc_later = loc_later or later
                    loc_key = str(target["location"])
                    prev_in, prev_later = flags.get(loc_key, (False, False))
                    flags[loc_key] = (prev_in or loc_has_in, prev_later or loc_later)
                if progress is not None:
                    stats = reconstruct_stats()
                    progress.delta_files_applied = int(
                        stats.get("delta_files_applied") or 0
                    )
                    progress.write()
        finally:
            if replay_conn is not None:
                try:
                    replay_conn.close()
                except Exception:
                    pass
            if replay_dir is None:
                replay_path.unlink(missing_ok=True)
        if progress is not None:
            progress.units_completed += 1
            progress.write()

    for location, targets in legacy_seen.items():
        if wall is not None:
            wall.check(stage="members_legacy")
        note_counter("legacy_member_locations_read", 1)
        note_member_file_open()
        loc_has_in = False
        loc_later = False
        newest = max(targets, key=lambda item: (item["rank_effective"], item["rank_index"]))
        try:
            path = _contained_data_path(Path(observation_rdp_root), location)
            payload_bytes = int(path.stat().st_size) if path.is_file() else 0
        except (MembersDeltaError, OSError):
            payload_bytes = 0
        note_counter("member_payload_bytes_read", payload_bytes)
        for batch in iter_member_row_batches_for_location(
            observation_rdp_root, location, columns=None
        ):
            for member in batch:
                if not isinstance(member, Mapping):
                    continue
                has_in, later = _ingest(
                    member,
                    newest["producer"],
                    rank_effective=newest["rank_effective"],
                    rank_index=newest["rank_index"],
                )
                loc_has_in = loc_has_in or has_in
                loc_later = loc_later or later
        flags[location] = (loc_has_in, loc_later)
        for target in targets:
            flags[str(target["location"])] = (loc_has_in, loc_later)

    stats = reconstruct_stats()
    note_counter("anchor_loads", int(stats.get("anchor_loads") or 0))
    note_counter("delta_files_applied", int(stats.get("delta_files_applied") or 0))
    note_counter(
        "unique_target_seq_consumed",
        int(stats.get("unique_target_seq_consumed") or 0),
    )
    note_counter(
        "historical_independent_reconstruct_calls",
        int(stats.get("historical_independent_reconstruct_calls") or 0),
    )
    conn.commit()
    member_count = int(conn.execute("SELECT COUNT(*) FROM members").fetchone()[0])
    return winning_producers, member_count



def latest_c1_observation_manifest_at(
    observation_rdp_root: Path,
    *,
    schedule_sha256: str,
    activation_id: str,
    not_after: datetime,
    cohort_mints: set[str] | None = None,
    mint_is_member: Callable[[str], bool] | None = None,
    window_start: datetime | None = None,
) -> datetime | None:
    """First publication time of each C1 observation identity, max of those <= not_after.

    Republished C1 rows in a later mixed panel do not advance the freeze horizon.
    Operator path uses keyed OBSERVATION_BATCH + canonical partition identity.
    It does not glob dataset-*.published.
    """
    def _in_cohort(mint: str) -> bool:
        if mint_is_member is not None:
            return mint_is_member(mint)
        if cohort_mints is not None:
            return mint in cohort_mints
        return False

    if mint_is_member is None and not cohort_mints:
        return None
    if window_start is None:
        return None
    try:
        store = ExistingResearchStoreReader(Path(observation_rdp_root))
        records, _telemetry = store.iter_lifecycle_records_bounded(
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            window_start=window_start,
            closure_cutoff=not_after,
        )
    except ResearchStoreError:
        return None
    handle, name = tempfile.mkstemp(prefix="live-cohort-first-seen-", suffix=".sqlite")
    os.close(handle)
    spill = Path(name)
    conn = sqlite3.connect(str(spill))
    try:
        conn.execute(
            """
            CREATE TABLE first_seen (
                mint TEXT NOT NULL,
                point_id TEXT NOT NULL,
                primitive_id TEXT NOT NULL,
                field_id TEXT NOT NULL,
                call_occurrence_id TEXT NOT NULL,
                seen_at TEXT NOT NULL,
                PRIMARY KEY (mint, point_id, primitive_id, field_id, call_occurrence_id)
            )
            """
        )
        insert = conn.execute
        partition_index = None
        seen_locations: set[str] = set()
        panels: list[tuple[datetime, Path]] = []
        for record in records:
            if str(record.record_kind) != "OBSERVATION_BATCH":
                continue
            effective = getattr(record, "effective_at", None)
            if not isinstance(effective, datetime) or effective.tzinfo is None:
                raise LiveCohortReleaseError(OBSERVATION_LINEAGE_INCOMPLETE)
            effective = effective.astimezone(UTC)
            if effective < window_start or effective > not_after:
                continue
            try:
                payload = json.loads(record.payload_json)
            except (TypeError, json.JSONDecodeError) as exc:
                raise LiveCohortReleaseError(OBSERVATION_LINEAGE_INCOMPLETE) from exc
            if not isinstance(payload, Mapping):
                raise LiveCohortReleaseError(OBSERVATION_LINEAGE_INCOMPLETE)
            try:
                path, location = resolve_observation_panel_location(
                    Path(observation_rdp_root),
                    payload,
                    partition_index=partition_index,
                )
            except BoundedMaterializationError as exc:
                raise LiveCohortReleaseError(OBSERVATION_LINEAGE_INCOMPLETE) from exc
            if location in seen_locations:
                continue
            seen_locations.add(location)
            panels.append((effective, path))
        panels.sort(key=lambda item: item[0])
        for effective, path in panels:
            stamp = _render_utc(effective)
            try:
                for batch in iter_parquet_row_batches(path):
                    note_observation_rows(len(batch))
                    for row in batch:
                        if not isinstance(row, Mapping):
                            continue
                        if row.get("schedule_sha256") not in {None, "", schedule_sha256}:
                            continue
                        for item in _explode_observation_rows(
                            row, schedule_sha256=schedule_sha256, activation_id=activation_id
                        ):
                            mint = str(item.get("mint") or "")
                            if not _in_cohort(mint) or _observation_instant(item) is None:
                                continue
                            insert(
                                """
                                INSERT OR IGNORE INTO first_seen(
                                    mint, point_id, primitive_id, field_id, call_occurrence_id, seen_at
                                ) VALUES (?,?,?,?,?,?)
                                """,
                                (
                                    mint,
                                    str(item.get("point_id") or ""),
                                    str(item.get("primitive_id") or ""),
                                    str(item.get("field_id") or ""),
                                    str(item.get("call_occurrence_id") or ""),
                                    stamp,
                                ),
                            )
            except (OSError, pa.ArrowException) as exc:
                raise LiveCohortReleaseError(OBSERVATION_LINEAGE_INCOMPLETE) from exc
        conn.commit()
        row = conn.execute("SELECT MAX(seen_at) FROM first_seen").fetchone()
        if not row or row[0] is None:
            return None
        return _parse_utc(str(row[0]))
    finally:
        conn.close()
        spill.unlink(missing_ok=True)


def _cohort_observations_into_sqlite(
    observation_rdp_root: Path,
    *,
    conn: Any,
    schedule_sha256: str,
    activation_id: str,
    mint_is_member: Callable[[str], bool],
    cutoff_at: datetime | None = None,
    lifecycle_rows: Sequence[Mapping[str, Any]] | None = None,
    observation_lineage: dict[str, Any] | None = None,
    window_start: datetime | None = None,
    progress: MaterializationProgress | None = None,
    wall: WallBudget | None = None,
) -> int:
    """C1 observations via OBSERVATION_BATCH dataset_manifest_id routing."""
    conn.execute(
        """
        CREATE TABLE observations (
            mint TEXT NOT NULL,
            point_id TEXT NOT NULL,
            primitive_id TEXT NOT NULL,
            field_id TEXT NOT NULL,
            call_occurrence_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (mint, point_id, primitive_id, field_id, call_occurrence_id)
        )
        """
    )
    note_counter("global_manifest_markers_scanned", 0)
    lineage_producers: set[str] = set()
    lineage_coverages: list[str] = []
    lineage_manifests: set[str] = set()
    if window_start is None:
        member_ids = {
            str((row.get("payload") or {}).get("dataset_manifest_id") or "")
            for row in (lifecycle_rows or ())
            if str(row.get("kind") or "") == "OBSERVATION_MEMBER_BATCH"
            and isinstance(row.get("payload"), Mapping)
        }
    else:
        selected_members, _predecessors = select_member_batches(
            lifecycle_rows or (),
            window_start=window_start,
            closure_cutoff=cutoff_at,
        )
        member_ids = {
            str((row.get("payload") or {}).get("dataset_manifest_id") or "")
            for row in selected_members
            if isinstance(row.get("payload"), Mapping)
        }
    member_ids.discard("")
    if window_start is None:
        selected = [
            dict(row)
            for row in (lifecycle_rows or ())
            if str(row.get("kind") or "") == "OBSERVATION_BATCH"
            and _lifecycle_row_at_or_before_cutoff(row, cutoff_at)
        ]
    else:
        selected = select_observation_batches(
            lifecycle_rows or (),
            window_start=window_start,
            closure_cutoff=cutoff_at,
            member_dataset_ids=member_ids,
        )
    note_counter("observation_lineage_rows_selected", len(selected))
    if progress is not None:
        progress.observation_files_planned = len(selected)
        progress.stage = "observations"
        progress.write()

    def _safe_observation_batches(path: Path) -> Iterator[list[dict[str, Any]]]:
        try:
            yield from iter_parquet_row_batches(path)
        except (OSError, pa.ArrowException) as exc:
            raise LiveCohortReleaseError(
                "LIVE_SOURCE_MEMBER_PROVENANCE_UNREADABLE"
            ) from exc

    selected.sort(
        key=lambda row: (
            str(row.get("effective_at") or ""),
            int(row.get("_source_index") or 0),
        )
    )
    seen_locations: set[str] = set()
    partition_index = None
    for row in selected:
        if wall is not None:
            wall.check(stage="observations")
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            raise LiveCohortReleaseError(OBSERVATION_LINEAGE_INCOMPLETE)
        try:
            path, location = resolve_observation_panel_location(
                observation_rdp_root, payload, partition_index=partition_index
            )
        except BoundedMaterializationError as exc:
            raise LiveCohortReleaseError(str(exc) or OBSERVATION_LINEAGE_INCOMPLETE) from exc
        producer = _sha40(row.get("producer_git_sha"))
        manifest = str(payload.get("dataset_manifest_id") or "")
        if manifest:
            lineage_manifests.add(manifest)
        raw_coverage = payload.get("discovery_coverage_class")
        if isinstance(raw_coverage, str) and raw_coverage.strip():
            lineage_coverages.append(raw_coverage.strip())
        if location in seen_locations:
            if progress is not None:
                progress.observation_files_completed += 1
                progress.write()
            continue
        seen_locations.add(location)
        try:
            payload_bytes = int(path.stat().st_size)
        except OSError:
            payload_bytes = 0
        note_counter("observation_payload_bytes_read", payload_bytes)
        note_counter("unique_observation_locations_read", 1)
        if progress is not None:
            progress.observation_payload_bytes_read += payload_bytes
        hits_c1 = False
        for batch in _safe_observation_batches(path):
            note_observation_rows(len(batch))
            note_counter("observation_rows_decoded", len(batch))
            for item_row in batch:
                if not isinstance(item_row, Mapping):
                    continue
                mint = str(item_row.get("entity_id") or item_row.get("mint") or "")
                if mint and mint_is_member(mint):
                    hits_c1 = True
                if item_row.get("schedule_sha256") not in {None, "", schedule_sha256}:
                    continue
                for item in _explode_observation_rows(
                    item_row, schedule_sha256=schedule_sha256, activation_id=activation_id
                ):
                    mint = str(item.get("mint") or "")
                    if not mint or not mint_is_member(mint):
                        continue
                    if _observation_instant(item) is None:
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO observations(
                            mint, point_id, primitive_id, field_id, call_occurrence_id, payload_json
                        ) VALUES (?,?,?,?,?,?)
                        """,
                        (
                            mint,
                            str(item.get("point_id") or ""),
                            str(item.get("primitive_id") or ""),
                            str(item.get("field_id") or ""),
                            str(item.get("call_occurrence_id") or ""),
                            json.dumps(item, sort_keys=True, separators=(",", ":")),
                        ),
                    )
        if hits_c1 and producer:
            lineage_producers.add(producer)
        if progress is not None:
            progress.observation_files_completed += 1
            progress.observation_payload_bytes_read = int(
                extraction_counters().get("observation_payload_bytes_read") or 0
            )
            progress.write()
    conn.commit()
    if observation_lineage is not None:
        observation_lineage.update(
            {
                "producers": lineage_producers,
                "coverages": lineage_coverages,
                "manifests": lineage_manifests,
            }
        )
    return int(conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0])


def plan_live_source_materialization(
    *,
    observation_rdp_root: Path,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str,
    closure_receipt: Mapping[str, Any] | None = None,
    ops_store: Path | None = None,
) -> dict[str, Any]:
    """Deterministic work plan. Fail-closed before heavy payload replay."""
    reset_extraction_counters()
    reset_fingerprint_work()
    root = Path(observation_rdp_root)
    window_start, window_end = cohort_window_bounds(cohort_id)
    closure_flags = _apply_closure_receipt(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        cohort_id=cohort_id,
        closure_receipt=closure_receipt,
    )
    cutoff_at = None
    cutoff_raw = closure_flags.get("closure_cutoff_at")
    if isinstance(cutoff_raw, str) and cutoff_raw:
        cutoff_at = _parse_utc(cutoff_raw)
    schedule_doc, _producer, lifecycle_rows = _lineage_from_rdp(
        root,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        window_start=window_start,
        closure_cutoff=cutoff_at,
    )
    if ops_store is not None:
        bound_doc, _artifact_bytes, _artifact_sha = _encode_bound_schedule(
            schedule_doc, wanted_sha=schedule_sha256
        )
        ops_doc = load_ops_schedule_document(Path(ops_store), schedule_sha256)
        if ops_doc is not None:
            try:
                agree_schedule_documents(
                    bound_doc, ops_doc, wanted_sha=schedule_sha256
                )
            except ValueError as exc:
                raise LiveCohortReleaseError(SCHEDULE_DOCUMENT_CONFLICT) from exc
    selected_members, predecessors = select_member_batches(
        lifecycle_rows,
        window_start=window_start,
        closure_cutoff=cutoff_at,
    )
    member_ids = {
        str((row.get("payload") or {}).get("dataset_manifest_id") or "")
        for row in selected_members
        if isinstance(row.get("payload"), Mapping)
    }
    member_ids.discard("")
    selected_obs = select_observation_batches(
        lifecycle_rows,
        window_start=window_start,
        closure_cutoff=cutoff_at,
        member_dataset_ids=member_ids,
    )
    units: dict[str, dict[str, Any]] = {}
    legacy_locations: list[str] = []
    slow = False
    predicted_member_bytes = 0
    predicted_deltas = 0
    for row in selected_members:
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            slow = True
            continue
        location = str(payload.get("member_location") or "")
        try:
            info = inspect_member_target(root, location)
        except BoundedMaterializationError as exc:
            raise LiveCohortReleaseError(str(exc)) from exc
        if info.get("slow_fallback"):
            slow = True
            continue
        if info.get("legacy"):
            if location not in legacy_locations:
                legacy_locations.append(location)
                predicted_member_bytes += file_size_for_rel(root, location)
            continue
        unit_rel = str(info.get("unit_rel") or "")
        unit = info.get("unit")
        seq = info.get("seq")
        if not unit_rel or not isinstance(unit, Mapping) or seq is None:
            slow = True
            continue
        group = units.setdefault(unit_rel, {"unit": unit, "seqs": set()})
        group["seqs"].add(int(seq))
    snapshot_delta_targets = 0
    for group in units.values():
        seqs = sorted(group["seqs"])
        snapshot_delta_targets += len(seqs)
        max_seq = max(seqs) if seqs else 0
        predicted_deltas += max_seq
        unit = group["unit"]
        for publication in unit.get("publications") or []:
            if not isinstance(publication, Mapping):
                continue
            try:
                seq = int(publication.get("seq"))
            except (TypeError, ValueError):
                continue
            if seq > max_seq:
                continue
            rel = str(publication.get("rel") or "")
            if rel:
                predicted_member_bytes += file_size_for_rel(root, rel)
    predicted_obs_bytes = 0
    predicted_obs_locations = 0
    seen_obs: set[str] = set()
    global_glob = False
    partition_index = None
    for row in selected_obs:
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        try:
            path, location = resolve_observation_panel_location(
                root, payload, partition_index=partition_index
            )
        except BoundedMaterializationError as exc:
            raise LiveCohortReleaseError(str(exc) or OBSERVATION_LINEAGE_INCOMPLETE) from exc
        if location in seen_obs:
            continue
        seen_obs.add(location)
        predicted_obs_locations += 1
        try:
            predicted_obs_bytes += int(path.stat().st_size)
        except OSError:
            pass
    counters = extraction_counters()
    independent = int(
        reconstruct_stats().get("historical_independent_reconstruct_calls")
        or counters.get("historical_independent_reconstruct_calls")
        or 0
    )
    bounded_route = int(counters.get("research_store_bounded_route") or 0) > 0
    full_historical = (not bounded_route) or int(
        counters.get("research_store_full_committed_scan") or 0
    ) > 0
    markers = int(counters.get("global_manifest_markers_scanned") or 0)
    global_glob = bool(global_glob or markers > 0)
    if not selected_members:
        slow = True
    work_class = BOUNDED_WORK_CLASS
    if slow or global_glob or independent != 0 or full_historical:
        work_class = UNBOUNDED_PLAN
    plan = {
        "cohort_id": cohort_id,
        "window_start": _render_utc(window_start),
        "window_end": _render_utc(window_end),
        "closure_cutoff": _render_utc(cutoff_at) if cutoff_at is not None else None,
        "research_event_partitions_planned": int(
            counters.get("research_event_partitions_opened") or 0
        ),
        "member_batches_selected": len(selected_members),
        "predecessor_member_batches": len(predecessors),
        "snapshot_delta_units": len(units),
        "snapshot_delta_targets": snapshot_delta_targets,
        "predicted_delta_applications": predicted_deltas,
        "legacy_member_locations": len(legacy_locations),
        "observation_batches_selected": len(selected_obs),
        "predicted_observation_locations": predicted_obs_locations,
        "predicted_member_input_bytes": predicted_member_bytes,
        "predicted_observation_input_bytes": predicted_obs_bytes,
        "slow_fallback_required": slow,
        "work_class": work_class,
        "historical_independent_reconstruct_calls": independent,
        "global_manifest_markers_scanned": markers,
        "full_historical_research_payload_scan": full_historical,
        "global_historical_observation_glob": global_glob,
        "research_store_bounded_route": bounded_route,
        "research_event_partitions_skipped_by_time": int(
            counters.get("research_event_partitions_skipped_by_time") or 0
        ),
        "research_event_partitions_opened_unknown_bounds": int(
            counters.get("research_event_partitions_opened_unknown_bounds") or 0
        ),
        "research_manifest_headers_scanned": int(
            counters.get("research_manifest_headers_scanned") or 0
        ),
        "research_event_records_decoded": int(
            counters.get("research_event_records_decoded") or 0
        ),
        "research_event_payload_bytes_read": int(
            counters.get("research_event_payload_bytes_read") or 0
        ),
        "observation_partition_index_files_read": int(
            counters.get("observation_partition_index_files_read") or 0
        ),
    }
    return plan


def build_live_observation_source_from_rdp(
    *,
    observation_rdp_root: Path,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str,
    as_of: datetime | None = None,
    closure_receipt: Mapping[str, Any] | None = None,
    discovery_coverage_class: str | None = None,
    ops_store: Path | None = None,
    plan_only: bool = False,
    wall_budget_s: float = DEFAULT_WALL_BUDGET_S,
) -> dict[str, Any]:
    """Rebuild a cohort-scoped live source from immutable Observation RDP."""
    del as_of  # closure receipt already binds as_of; unused for scientific rows
    root = Path(observation_rdp_root)
    _require(
        len(schedule_sha256) == 64
        and all(c in "0123456789abcdef" for c in schedule_sha256),
        "RELEASE_INVALID_SOURCE_INTEGRITY",
    )
    plan = plan_live_source_materialization(
        observation_rdp_root=root,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        cohort_id=cohort_id,
        closure_receipt=closure_receipt,
        ops_store=ops_store,
    )
    if plan_only:
        return plan
    if plan_is_unbounded(plan):
        raise LiveCohortReleaseError(UNBOUNDED_PLAN)
    reset_extraction_counters()
    reset_fingerprint_work()
    window_start, window_end = cohort_window_bounds(cohort_id)
    closure_flags = _apply_closure_receipt(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        cohort_id=cohort_id,
        closure_receipt=closure_receipt,
    )
    cutoff_at = None
    cutoff_raw = closure_flags.get("closure_cutoff_at")
    if isinstance(cutoff_raw, str) and cutoff_raw:
        cutoff_at = _parse_utc(cutoff_raw)
    schedule_doc, schedule_producer, lifecycle_rows = _lineage_from_rdp(
        root,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        window_start=window_start,
        closure_cutoff=cutoff_at,
    )
    bound_doc, artifact_bytes, artifact_sha = _encode_bound_schedule(
        schedule_doc, wanted_sha=schedule_sha256
    )
    if ops_store is not None:
        ops_doc = load_ops_schedule_document(Path(ops_store), schedule_sha256)
        if ops_doc is not None:
            try:
                agree_schedule_documents(
                    bound_doc, ops_doc, wanted_sha=schedule_sha256
                )
            except ValueError as exc:
                raise LiveCohortReleaseError(SCHEDULE_DOCUMENT_CONFLICT) from exc
    activation = schedule_doc.get("activation")
    assert isinstance(activation, Mapping)
    starts_at = str(activation.get("starts_at") or "")
    stops_admitting_at = str(activation.get("stops_admitting_at") or "")
    _require(bool(starts_at) and bool(stops_admitting_at), "LIVE_SOURCE_ACTIVATION_MISSING")
    campaign_start = _parse_utc(starts_at)
    campaign_stop = _parse_utc(stops_admitting_at)
    allowed = {
        cid: (start, end)
        for cid, start, end in campaign_cohort_windows(campaign_start, campaign_stop)
    }
    if cohort_id not in allowed:
        raise LiveCohortReleaseError("COHORT_NOT_IN_CAMPAIGN_WINDOW")
    expected_start, expected_end = allowed[cohort_id]
    _require(
        expected_start == window_start and expected_end == window_end,
        "IDENTITY_CONFLICT",
    )
    sampling = schedule_doc.get("sampling") if isinstance(schedule_doc.get("sampling"), Mapping) else {}
    sampling_policy = str(sampling.get("policy") or "") or None
    sampling_seed = str(sampling.get("seed") or "") or None
    inclusion_probability = (
        str(sampling.get("inclusion_probability"))
        if sampling.get("inclusion_probability") is not None
        else None
    )
    cutoff_at = None
    cutoff_raw = closure_flags.get("closure_cutoff_at")
    if isinstance(cutoff_raw, str) and cutoff_raw:
        cutoff_at = _parse_utc(cutoff_raw)

    source_dir = cohort_source_dir(root, cohort_id)
    run_id = secrets.token_hex(8)
    lock = CohortBuildLock(
        root,
        cohort_id,
        run_id=run_id,
        command_identity=f"build-live-source:{cohort_id}",
    )
    try:
        lock.acquire()
    except BoundedMaterializationError as exc:
        raise LiveCohortReleaseError(str(exc)) from exc
    wall = WallBudget(limit_s=float(wall_budget_s))
    staging = new_staging_dir(source_dir)
    progress = MaterializationProgress(
        path=staging / PROGRESS_NAME,
        started_at=_render_utc(datetime.now(tz=UTC)),
        stage="locked",
        units_total=int(plan.get("snapshot_delta_units") or 0),
        pit_targets_total=int(plan.get("member_batches_selected") or 0),
        delta_files_planned=int(plan.get("predicted_delta_applications") or 0),
        observation_files_planned=int(plan.get("predicted_observation_locations") or 0),
    )
    progress.write(scratch_dir=staging)
    spill_path = staging / "extract.sqlite"
    conn = spill_sqlite(spill_path)
    location_flags: dict[str, tuple[bool, bool]] = {}
    telemetry: dict[str, Any] | None = None
    try:
        wall.check(stage="members")
        winning_producers, extracted_members = _cohort_members_into_sqlite(
            root,
            conn=conn,
            lifecycle_rows=lifecycle_rows,
            window_start=window_start,
            window_end=window_end,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            sampling_policy=sampling_policy,
            sampling_seed=sampling_seed,
            inclusion_probability=inclusion_probability,
            cutoff_at=cutoff_at,
            location_flags=location_flags,
            replay_dir=staging,
            progress=progress,
            wall=wall,
        )

        def _member_in_extract(mint: str) -> bool:
            return conn.execute("SELECT 1 FROM members WHERE mint=?", (mint,)).fetchone() is not None

        contributing, lineage_coverage, _pure_manifests = _cohort_contributing_lineage(
            root,
            lifecycle_rows=lifecycle_rows,
            window_start=window_start,
            window_end=window_end,
            mint_is_member=_member_in_extract,
            cutoff_at=cutoff_at,
            location_flags=location_flags,
            include_observations=False,
        )
        observation_lineage: dict[str, Any] = {}
        wall.check(stage="observations")
        extracted_observation_count = _cohort_observations_into_sqlite(
            root,
            conn=conn,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            mint_is_member=_member_in_extract,
            cutoff_at=cutoff_at,
            lifecycle_rows=lifecycle_rows,
            observation_lineage=observation_lineage,
            window_start=window_start,
            progress=progress,
            wall=wall,
        )
        contributing = sorted(
            set(contributing)
            | winning_producers
            | set(observation_lineage.get("producers") or ())
        )
        _require(bool(contributing), "LIVE_SOURCE_PRODUCER_MISSING")
        observed_classes = [lineage_coverage]
        observed_classes.extend(observation_lineage.get("coverages") or ())
        if isinstance(discovery_coverage_class, str) and discovery_coverage_class.strip():
            observed_classes.append(discovery_coverage_class.strip())
        resolved_coverage = _worst_coverage(observed_classes)

        def _member_batches() -> Iterator[list[dict[str, Any]]]:
            batch: list[dict[str, Any]] = []
            for payload_json, in conn.execute(
                "SELECT payload_json FROM members ORDER BY mint, admission"
            ):
                batch.append(row_for_member_parquet(json.loads(payload_json)))
                if len(batch) >= BATCH_SIZE:
                    yield batch
                    batch = []
            if batch:
                yield batch

        def _obs_batches() -> Iterator[list[dict[str, Any]]]:
            batch: list[dict[str, Any]] = []
            for payload_json, in conn.execute(
                """
                SELECT payload_json FROM observations
                ORDER BY mint, point_id, primitive_id, field_id, call_occurrence_id
                """
            ):
                batch.append(row_for_observation_parquet(json.loads(payload_json)))
                if len(batch) >= BATCH_SIZE:
                    yield batch
                    batch = []
            if batch:
                yield batch

        members_path = staging / SOURCE_MEMBERS_NAME
        obs_path = staging / SOURCE_OBSERVATIONS_NAME
        schedule_path = staging / SOURCE_SCHEDULE_NAME
        member_count = write_parquet_from_row_batches(
            members_path, _member_batches(), schema=MEMBER_SCHEMA
        )
        observation_count = write_parquet_from_row_batches(
            obs_path, _obs_batches(), schema=OBSERVATION_SCHEMA
        )
        _require(
            observation_count == extracted_observation_count,
            "RELEASE_INVALID_SOURCE_INTEGRITY",
        )
        _require(member_count == extracted_members, "RELEASE_INVALID_SOURCE_INTEGRITY")
        members_sha = sha256_file_streaming(members_path)
        observations_sha = sha256_file_streaming(obs_path)
        schedule_path.write_bytes(artifact_bytes)
        snapshot: dict[str, Any] = {
            "schema": SOURCE_BUNDLE_SCHEMA,
            "schema_version": SOURCE_BUNDLE_SCHEMA_VERSION_SELF_CONTAINED,
            "schedule_sha256": schedule_sha256,
            "activation_id": activation_id,
            "cohort_id": cohort_id,
            "window_start": _render_utc(window_start),
            "window_end_exclusive": _render_utc(window_end),
            "schedule_producer_git_sha": schedule_producer,
            "contributing_producer_git_shas": contributing,
            "starts_at": starts_at,
            "stops_admitting_at": stops_admitting_at,
            "discovery_coverage_class": resolved_coverage,
            "admission_field": COHORT_ADMISSION_FIELD,
            "member_count": member_count,
            "observation_count": observation_count,
            "members_sha256": members_sha,
            "observations_sha256": observations_sha,
            "observation_schedule_sha256": artifact_sha,
            "members_partition": SOURCE_MEMBERS_NAME,
            "observations_partition": SOURCE_OBSERVATIONS_NAME,
            "observation_schedule_partition": SOURCE_SCHEDULE_NAME,
            "source_representation": SOURCE_REPRESENTATION_BUNDLE,
            **closure_flags,
        }
        if len(contributing) == 1:
            snapshot["producer_git_sha"] = contributing[0]
        snapshot["source_sha256"] = compute_source_identity(snapshot)
        wall.check(stage="canonical_commit")
        progress.canonical_commit_started = True
        progress.stage = "canonical_commit"
        progress.write(scratch_dir=staging)
        conn.close()
        conn = None
        spill_path.unlink(missing_ok=True)
        reconstruct = reconstruct_stats()
        counters = extraction_counters()
        progress.canonical_commit_complete = True
        progress.write(scratch_dir=staging)
        telemetry = {
            "work_class": plan.get("work_class"),
            "slow_fallback_required": bool(plan.get("slow_fallback_required")),
            "historical_independent_reconstruct_calls": int(
                counters.get("historical_independent_reconstruct_calls")
                or reconstruct.get("historical_independent_reconstruct_calls")
                or 0
            ),
            "global_manifest_markers_scanned": int(
                counters.get("global_manifest_markers_scanned") or 0
            ),
            "legacy_member_locations_read": int(
                counters.get("legacy_member_locations_read") or 0
            ),
            "progress": progress.snapshot(),
            "counters": counters,
            "reconstruct": reconstruct,
            "owned_scratch_removed": True,
        }
        commit_source_bundle(source_dir=source_dir, staging=staging, manifest=snapshot)
    except BoundedMaterializationError as exc:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        raise LiveCohortReleaseError(str(exc)) from exc
    except Exception:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        raise
    finally:
        lock.release()
    if telemetry is None:
        raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY")
    loaded = load_observation_rdp_source(root, cohort_id=cohort_id)
    view = compact_source_view(loaded)
    view["materialization"] = telemetry
    return view


def _require_campaign_cohort(source: Mapping[str, Any], cohort_id: str) -> tuple[datetime, datetime]:
    starts = _parse_utc(str(source.get("starts_at") or ""))
    stops = _parse_utc(str(source.get("stops_admitting_at") or ""))
    allowed = {cid: (start, end) for cid, start, end in campaign_cohort_windows(starts, stops)}
    if cohort_id not in allowed:
        raise LiveCohortReleaseError("COHORT_NOT_IN_CAMPAIGN_WINDOW")
    return allowed[cohort_id]


def classify_cohort_readiness(
    source: Mapping[str, Any],
    *,
    cohort_id: str,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Deterministic readiness from immutable Observation RDP source only."""
    if source.get("source_sha256") is None:
        return {
            "cohort_id": cohort_id,
            "state": "RELEASE_INVALID_SOURCE_INTEGRITY",
            "sealable": False,
        }
    receipt = source.get("closure_receipt_sha256")
    if not (isinstance(receipt, str) and len(receipt) == 64):
        return {
            "cohort_id": cohort_id,
            "state": "CLOSED_RECEIPT_MISSING",
            "sealable": False,
        }
    try:
        open_publication = _require_closure_flag(source, "open_publication")
        budget_blocked = _require_closure_flag(source, "budget_blocked")
        unresolved_due = _require_closure_flag(source, "unresolved_due")
        in_flight = _require_closure_flag(source, "in_flight")
    except DiscoveryReleaseError:
        return {
            "cohort_id": cohort_id,
            "state": "CLOSED_RECEIPT_MISSING",
            "sealable": False,
        }
    if open_publication:
        return {
            "cohort_id": cohort_id,
            "state": "RELEASE_BLOCKED_OPEN_PUBLICATION",
            "sealable": False,
        }
    if budget_blocked:
        return {
            "cohort_id": cohort_id,
            "state": "RELEASE_BLOCKED_BUDGET",
            "sealable": False,
        }
    if unresolved_due:
        return {
            "cohort_id": cohort_id,
            "state": "RELEASE_BLOCKED_UNRESOLVED_DUE",
            "sealable": False,
        }
    if in_flight:
        return {
            "cohort_id": cohort_id,
            "state": "RELEASE_BLOCKED_IN_FLIGHT",
            "sealable": False,
        }

    now = (as_of or datetime.now(tz=UTC)).astimezone(UTC)
    start, end = _require_campaign_cohort(source, cohort_id)
    denom = {state: 0 for state in DENOMINATOR_STATES}
    member_count = 0
    for member in iter_source_member_rows(source):
        admission = member.get(COHORT_ADMISSION_FIELD)
        if not isinstance(admission, str):
            continue
        try:
            in_window = start <= _parse_utc(str(admission)) < end
        except Exception:
            continue
        if not in_window:
            continue
        member_count += 1
        state = str(member.get("denominator_state") or "unknown")
        if state in denom:
            denom[state] += 1
        else:
            denom["unknown"] += 1
    if member_count == 0:
        return {
            "cohort_id": cohort_id,
            "state": "COLLECTING",
            "sealable": False,
            "member_count": 0,
        }
    if now < end:
        return {
            "cohort_id": cohort_id,
            "state": "COLLECTING",
            "sealable": False,
            "member_count": member_count,
        }

    mature_at = end + timedelta(seconds=86400)
    if now < mature_at:
        return {
            "cohort_id": cohort_id,
            "state": "MATURING",
            "sealable": False,
            "member_count": member_count,
        }

    n = member_count
    observed = denom.get("observed", 0) + denom.get("typed_missing", 0)
    coverage = str(source.get("discovery_coverage_class") or "")
    if coverage == "GAP_CONFIRMED":
        return {
            "cohort_id": cohort_id,
            "state": "COVERAGE_CONFIRMED_BROKEN",
            "sealable": False,
            "member_count": n,
            "denominator": denom,
            "discovery_coverage_class": coverage,
            "admission_field": COHORT_ADMISSION_FIELD,
            "window_start": _render_utc(start),
            "window_end_exclusive": _render_utc(end),
        }
    coverage_limited = coverage in COVERAGE_LIMITED_CLASSES
    low_yield = n < 3 or observed == 0
    if low_yield:
        state = "READY_LOW_YIELD"
    elif coverage_limited:
        state = "READY_VALID_WITH_COVERAGE_LIMITATION"
    else:
        state = "READY_VALID"
    return {
        "cohort_id": cohort_id,
        "state": state,
        "sealable": state in SEALABLE_READY,
        "member_count": n,
        "denominator": denom,
        "discovery_coverage_class": source.get("discovery_coverage_class"),
        "admission_field": COHORT_ADMISSION_FIELD,
        "window_start": _render_utc(start),
        "window_end_exclusive": _render_utc(end),
    }


def release_id_for(source: Mapping[str, Any], cohort_id: str) -> str:
    producers = _producer_fields(source)
    artifact_sha = source.get("observation_schedule_sha256")
    self_contained = isinstance(artifact_sha, str) and len(artifact_sha) == 64
    body: dict[str, Any] = {
        "schema": RELEASE_SCHEMA,
        "schema_version": (
            RELEASE_SCHEMA_VERSION_SELF_CONTAINED
            if self_contained
            else RELEASE_SCHEMA_VERSION_LEGACY
        ),
        "cohort_id": cohort_id,
        "schedule_sha256": source["schedule_sha256"],
        "activation_id": source["activation_id"],
        "contributing_producer_git_shas": producers["contributing_producer_git_shas"],
        "schedule_producer_git_sha": producers.get("schedule_producer_git_sha"),
        "source_sha256": source["source_sha256"],
        "starts_at": source.get("starts_at"),
        "stops_admitting_at": source.get("stops_admitting_at"),
        "window_start": source.get("window_start"),
        "window_end_exclusive": source.get("window_end_exclusive"),
        "admission_field": COHORT_ADMISSION_FIELD,
        "projection_id": PROJECTION_ID,
        "projection_version": PROJECTION_VERSION,
    }
    if self_contained:
        body["observation_schedule_sha256"] = artifact_sha
    return canonical_sha256(body)


def _release_id_for(source: Mapping[str, Any], cohort_id: str) -> str:
    return release_id_for(source, cohort_id)


def _census_row_from_member(
    member: Mapping[str, Any],
    *,
    source: Mapping[str, Any],
    cohort_id: str,
    release_id: str,
    producers: Mapping[str, Any],
) -> dict[str, Any]:
    admission = member.get(COHORT_ADMISSION_FIELD)
    mint = str(member.get("mint") or member.get("entity_id") or "")
    selected = str(member.get("selected_or_excluded") or "UNKNOWN")
    return {
        "release_id": release_id,
        "cohort_id": cohort_id,
        "source_schedule_sha256": source["schedule_sha256"],
        "activation_id": source["activation_id"],
        "producer_git_sha": producers.get("producer_git_sha") or "",
        "mint": mint,
        "discovery_first_reliable_available_at": admission,
        "authoritative_anchor": member.get("authoritative_anchor"),
        "candidate_state": member.get("candidate_state") or "UNKNOWN",
        "membership_state": member.get("membership_state") or "UNKNOWN",
        "denominator_state": member.get("denominator_state") or "unknown",
        "sampling_policy": member.get("sampling_policy"),
        "sampling_seed": member.get("sampling_seed"),
        "inclusion_probability": str(member.get("inclusion_probability") or ""),
        "selected_or_excluded": selected,
        "exclusion_reason": member.get("exclusion_reason"),
        "discovery_coverage_class": source.get("discovery_coverage_class"),
        "source_request_sha256": member.get("source_request_sha256"),
        "source_response_sha256": member.get("source_response_sha256"),
        "evidence_role": LIVE_EVIDENCE_ROLE,
    }


def _observation_release_row(
    obs: Mapping[str, Any],
    *,
    cohort_id: str,
    release_id: str,
) -> dict[str, Any]:
    typed_value = obs.get("typed_value")
    if not isinstance(typed_value, str) and typed_value is not None:
        typed_value = json.dumps(typed_value, sort_keys=True)
    http_status = obs.get("http_status")
    if http_status not in (None, ""):
        try:
            http_status = int(http_status)
        except (TypeError, ValueError):
            http_status = None
    else:
        http_status = None
    return {
        "release_id": release_id,
        "cohort_id": cohort_id,
        "mint": str(obs.get("mint") or obs.get("entity_id") or ""),
        "point_id": str(obs.get("point_id") or ""),
        "primitive_id": obs.get("primitive_id"),
        "field_id": obs.get("field_id"),
        "value_kind": obs.get("value_kind"),
        "typed_value": typed_value,
        "state": obs.get("state"),
        "missing_reason": obs.get("missing_reason"),
        "event_time": obs.get("event_time"),
        "request_started_at": obs.get("request_started_at"),
        "response_received_at": obs.get("response_received_at"),
        "first_reliable_available_at": obs.get("first_reliable_available_at"),
        "request_sha256": obs.get("request_sha256"),
        "response_sha256": obs.get("response_sha256"),
        "call_occurrence_id": obs.get("call_occurrence_id"),
        "http_status": http_status,
        "http_class": obs.get("http_class"),
        "evidence_role": LIVE_EVIDENCE_ROLE,
        "confirmatory_reuse_forbidden": True,
    }


def _write_live_release_tables(
    source: Mapping[str, Any],
    *,
    cohort_id: str,
    release_id: str,
    census_path: Path,
    observations_path: Path,
) -> tuple[int, int, list[str], int, int]:
    start, end = _require_campaign_cohort(source, cohort_id)
    producers = _producer_fields(source)
    handle, name = tempfile.mkstemp(prefix="live-cohort-seal-mints-", suffix=".sqlite")
    os.close(handle)
    spill = Path(name)
    mint_conn = sqlite3.connect(str(spill))
    mint_conn.execute("CREATE TABLE mints (mint TEXT PRIMARY KEY)")
    yield_eligible = 0
    yield_missing = 0
    try:

        def _census_batches() -> Iterator[list[dict[str, Any]]]:
            nonlocal yield_eligible, yield_missing
            batch: list[dict[str, Any]] = []
            for member in iter_source_member_rows(source):
                admission = member.get(COHORT_ADMISSION_FIELD)
                if not isinstance(admission, str):
                    continue
                adm_dt = _parse_utc(admission)
                if not (start <= adm_dt < end):
                    continue
                mint = str(member.get("mint") or member.get("entity_id") or "")
                _require(bool(mint), "TOKEN_MINT_MISSING")
                selected = str(member.get("selected_or_excluded") or "UNKNOWN")
                _require(selected in {"SELECTED", "EXCLUDED", "UNKNOWN"}, "SELECTED_STATE_INVALID")
                mint_conn.execute("INSERT OR IGNORE INTO mints(mint) VALUES (?)", (mint,))
                row = _census_row_from_member(
                    member,
                    source=source,
                    cohort_id=cohort_id,
                    release_id=release_id,
                    producers=producers,
                )
                denom = str(row.get("denominator_state") or "")
                if denom == "observed":
                    yield_eligible += 1
                elif denom in {"typed_missing", "censored_late", "disappeared"}:
                    yield_missing += 1
                batch.append(
                    {
                        key: None if row.get(key) is None else str(row.get(key))
                        for key in CENSUS_RELEASE_SCHEMA.names
                    }
                )
                if len(batch) >= BATCH_SIZE:
                    yield batch
                    batch = []
            if batch:
                yield batch

        census_rows = write_parquet_from_row_batches(
            census_path,
            _census_batches(),
            schema=CENSUS_RELEASE_SCHEMA,
            write_kwargs=RELEASE_PARQUET_WRITE_KWARGS,
        )
        _require(census_rows > 0, "COHORT_EMPTY")
        observed_families: set[str] = set()
        missing_or_excluded = False

        def _obs_batches() -> Iterator[list[dict[str, Any]]]:
            nonlocal missing_or_excluded
            batch: list[dict[str, Any]] = []
            for obs in iter_source_observation_rows(source):
                mint = str(obs.get("mint") or obs.get("entity_id") or "")
                if mint_conn.execute("SELECT 1 FROM mints WHERE mint=?", (mint,)).fetchone() is None:
                    continue
                point_id = str(obs.get("point_id") or "")
                _require(point_id and point_id != "R0", "LIVE_POINT_ID_REQUIRED")
                field_id = str(obs.get("field_id") or "")
                state = str(obs.get("state") or "")
                family = FIELD_TO_FAMILY.get(field_id)
                if state == STATE_OBSERVED and family is not None:
                    observed_families.add(family)
                if state in {STATE_MISSING, STATE_EXCLUDED}:
                    missing_or_excluded = True
                batch.append(
                    _observation_release_row(obs, cohort_id=cohort_id, release_id=release_id)
                )
                if len(batch) >= BATCH_SIZE:
                    yield batch
                    batch = []
            if batch:
                yield batch

        observation_rows = write_parquet_from_row_batches(
            observations_path,
            _obs_batches(),
            schema=OBS_RELEASE_SCHEMA,
            write_kwargs=RELEASE_PARQUET_WRITE_KWARGS,
        )
        if missing_or_excluded:
            observed_families.add(FEATURE_FAMILY_MISSINGNESS)
        families = [item for item in FEATURE_FAMILY_ORDER if item in observed_families] or list(
            FEATURE_FAMILY_ORDER[:1]
        )
        return census_rows, observation_rows, families, yield_eligible, yield_missing
    finally:
        mint_conn.close()
        spill.unlink(missing_ok=True)


def seal_live_cohort(
    *,
    observation_rdp_root: Path,
    cohort_id: str,
    release_root: Path,
    sealed_at: datetime | None = None,
    as_of: datetime | None = None,
    release_builder_git_sha: str | None = None,
) -> dict[str, Any]:
    source = load_observation_rdp_source(observation_rdp_root, cohort_id=cohort_id)
    readiness = classify_cohort_readiness(source, cohort_id=cohort_id, as_of=as_of)
    _require(readiness.get("sealable") is True, str(readiness.get("state") or "NOT_READY"))
    wanted_sha = str(source["schedule_sha256"])
    source_version = str(source.get("schema_version") or SOURCE_BUNDLE_SCHEMA_VERSION)
    require_schedule = source_version == SOURCE_BUNDLE_SCHEMA_VERSION_SELF_CONTAINED
    bound = _try_resolve_schedule_for_seal(
        source,
        Path(observation_rdp_root),
        wanted_sha=wanted_sha,
        activation_id=str(source["activation_id"]),
    )
    if bound is None:
        _require(not require_schedule, SCHEDULE_DOCUMENT_MISSING)
        artifact_bytes = None
        artifact_sha = None
        schema_version = RELEASE_SCHEMA_VERSION_LEGACY
        source_for_id = source
    else:
        _document, artifact_bytes, artifact_sha = bound
        schema_version = RELEASE_SCHEMA_VERSION_SELF_CONTAINED
        source_for_id = dict(source)
        source_for_id["observation_schedule_sha256"] = artifact_sha
    release_id = _release_id_for(source_for_id, cohort_id)
    sealed = (sealed_at or datetime.now(tz=UTC)).astimezone(UTC)
    root = Path(release_root)
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".seal-{release_id[:12]}"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=False)
    census_tmp = staging / CENSUS_NAME
    obs_tmp = staging / OBSERVATIONS_NAME
    census_rows, observation_rows, families, yield_eligible, yield_missing = (
        _write_live_release_tables(
            source,
            cohort_id=cohort_id,
            release_id=release_id,
            census_path=census_tmp,
            observations_path=obs_tmp,
        )
    )
    census_sha = sha256_file_streaming(census_tmp)
    obs_sha = sha256_file_streaming(obs_tmp)
    producers = _producer_fields(source)
    inventory = {
        "cohort_id": cohort_id,
        "schedule_sha256": source["schedule_sha256"],
        "activation_id": source["activation_id"],
        "source_sha256": source["source_sha256"],
        "starts_at": source.get("starts_at"),
        "stops_admitting_at": source.get("stops_admitting_at"),
        "window_start": source.get("window_start"),
        "window_end_exclusive": source.get("window_end_exclusive"),
        "admission_field": COHORT_ADMISSION_FIELD,
        "readiness_state": readiness["state"],
        "discovery_coverage_class": source.get("discovery_coverage_class"),
        "closure_receipt_sha256": source.get("closure_receipt_sha256"),
        **producers,
    }
    builder = _sha40(release_builder_git_sha)
    if builder:
        inventory["release_builder_git_sha"] = builder
    if artifact_sha is not None:
        inventory["observation_schedule_artifact"] = OBSERVATION_SCHEDULE_ARTIFACT_NAME
        inventory["observation_schedule_sha256"] = artifact_sha
    manifest = {
        "schema": RELEASE_SCHEMA,
        "schema_version": schema_version,
        "release_id": release_id,
        "cohort_id": cohort_id,
        "sealed_at": _render_utc(sealed),
        "schedule_sha256": source["schedule_sha256"],
        "activation_id": source["activation_id"],
        "source_sha256": source["source_sha256"],
        "starts_at": source.get("starts_at"),
        "stops_admitting_at": source.get("stops_admitting_at"),
        "admission_field": COHORT_ADMISSION_FIELD,
        "evidence_role": LIVE_EVIDENCE_ROLE,
        "confirmatory_reuse_forbidden": True,
        "census_sha256": census_sha,
        "observations_sha256": obs_sha,
        "census_row_count": census_rows,
        "observation_row_count": observation_rows,
        "feature_families": families,
        "yield_eligible": yield_eligible,
        "yield_missing": yield_missing,
        "readiness_state": readiness["state"],
        "discovery_coverage_class": source.get("discovery_coverage_class"),
        "projection_id": PROJECTION_ID,
        "projection_version": PROJECTION_VERSION,
        "closure_receipt_sha256": source.get("closure_receipt_sha256"),
        **producers,
    }
    if builder:
        manifest["release_builder_git_sha"] = builder
    if artifact_sha is not None:
        manifest["observation_schedule_artifact"] = OBSERVATION_SCHEDULE_ARTIFACT_NAME
        manifest["observation_schedule_sha256"] = artifact_sha
    census_tmp.replace(root / CENSUS_NAME)
    obs_tmp.replace(root / OBSERVATIONS_NAME)
    if artifact_bytes is not None:
        _publish_bytes(root / OBSERVATION_SCHEDULE_ARTIFACT_NAME, artifact_bytes)
    _publish_bytes(
        root / SOURCE_INVENTORY_NAME,
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    _publish_bytes(
        root / RELEASE_MANIFEST_NAME,
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    shutil.rmtree(staging, ignore_errors=True)
    return manifest


def verify_live_cohort(release_root: Path) -> dict[str, Any]:
    root = Path(release_root)
    manifest_path = root / RELEASE_MANIFEST_NAME
    _require(
        manifest_path.is_file() and not manifest_path.is_symlink(),
        "RELEASE_MANIFEST_MISSING",
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveCohortReleaseError("RELEASE_MANIFEST_CORRUPT") from exc
    _require(isinstance(manifest, Mapping), "RELEASE_MANIFEST_CORRUPT")
    _require(manifest.get("schema") == RELEASE_SCHEMA, "RELEASE_SCHEMA_MISMATCH")
    census_path = root / CENSUS_NAME
    obs_path = root / OBSERVATIONS_NAME
    _require(census_path.is_file() and not census_path.is_symlink(), "CENSUS_HASH_MISMATCH")
    _require(obs_path.is_file() and not obs_path.is_symlink(), "OBSERVATIONS_HASH_MISMATCH")
    _require(
        sha256_file_streaming(census_path) == manifest.get("census_sha256"),
        "CENSUS_HASH_MISMATCH",
    )
    _require(
        sha256_file_streaming(obs_path) == manifest.get("observations_sha256"),
        "OBSERVATIONS_HASH_MISMATCH",
    )
    _require(
        manifest.get("confirmatory_reuse_forbidden") is True, "CONFIRM_FENCE_MISSING"
    )
    _require(manifest.get("evidence_role") == LIVE_EVIDENCE_ROLE, "EVIDENCE_ROLE_MISMATCH")
    version = str(manifest.get("schema_version") or RELEASE_SCHEMA_VERSION_LEGACY)
    _require(
        version
        in {RELEASE_SCHEMA_VERSION_LEGACY, RELEASE_SCHEMA_VERSION_SELF_CONTAINED},
        "RELEASE_SCHEMA_MISMATCH",
    )
    if version == RELEASE_SCHEMA_VERSION_SELF_CONTAINED:
        schedule_path = root / OBSERVATION_SCHEDULE_ARTIFACT_NAME
        _require(
            schedule_path.is_file() and not schedule_path.is_symlink(),
            SCHEDULE_ARTIFACT_MISSING,
        )
        byte_sha = sha256_file_streaming(schedule_path)
        _require(
            byte_sha == manifest.get("observation_schedule_sha256"),
            SCHEDULE_ARTIFACT_HASH_MISMATCH,
        )
        wanted = str(manifest.get("schedule_sha256") or "")
        try:
            decode_schedule_artifact(
                schedule_path.read_bytes(),
                wanted_sha=wanted,
                expected_byte_sha256=byte_sha,
            )
        except ValueError as exc:
            raise LiveCohortReleaseError(str(exc)) from exc
        _census_schedule_identity(census_path, wanted)
        inventory_path = root / SOURCE_INVENTORY_NAME
        _require(
            inventory_path.is_file() and not inventory_path.is_symlink(),
            "RELEASE_INVALID_SOURCE_INTEGRITY",
        )
        try:
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY") from exc
        _require(isinstance(inventory, Mapping), "RELEASE_INVALID_SOURCE_INTEGRITY")
        _require(
            inventory.get("schedule_sha256") == wanted, SCHEDULE_SEMANTIC_SHA_MISMATCH
        )
        _require(
            inventory.get("observation_schedule_sha256") == byte_sha,
            SCHEDULE_ARTIFACT_HASH_MISMATCH,
        )
        _require(
            inventory.get("activation_id") == manifest.get("activation_id"),
            "IDENTITY_CONFLICT",
        )
        _require(
            inventory.get("cohort_id") == manifest.get("cohort_id"), "IDENTITY_CONFLICT"
        )
    return dict(manifest)


def _corpus_lineage_path(data_root: Path) -> Path:
    return Path(data_root) / "datasets" / "live_lifecycle_corpus" / "lineage.json"


def _load_lineage(data_root: Path) -> dict[str, Any]:
    path = _corpus_lineage_path(data_root)
    if not path.is_file():
        return {"corpus_dataset_id": CORPUS_DATASET_ID, "versions": [], "cohorts": []}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveCohortReleaseError("CORPUS_LINEAGE_CORRUPT") from exc
    _require(isinstance(loaded, Mapping), "CORPUS_LINEAGE_CORRUPT")
    return dict(loaded)


def _write_lineage(data_root: Path, lineage: Mapping[str, Any]) -> None:
    """Lineage index is mutable bookkeeping; prior corpus bytes stay immutable."""
    path = _corpus_lineage_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(lineage), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def load_live_corpus_lineage(data_root: Path) -> dict[str, Any]:
    """Public lineage read for LIVE CORPUS publication."""

    return _load_lineage(data_root)


def write_live_corpus_lineage(
    data_root: Path, lineage: Mapping[str, Any]
) -> None:
    """Public lineage write for LIVE CORPUS publication."""

    _write_lineage(data_root, lineage)


def parse_live_corpus_utc(value: str) -> datetime:
    """Public UTC parser for LIVE CORPUS publication."""

    return _parse_utc(value)


def current_corpus_partition_rows(
    data_root: Path,
    *,
    kind: str = "census",
) -> list[dict[str, Any]]:
    """Read census/observation rows exposed by the current cumulative corpus version."""
    from solana_alpha_lab.factory.live_corpus_manifest_publish import inspect_canonical_root

    lineage = _load_lineage(data_root)
    current_mid = lineage.get("current_dataset_manifest_id")
    _require(isinstance(current_mid, str) and current_mid, "CURRENT_CORPUS_MISSING")
    inspection = inspect_canonical_root(data_root, str(current_mid))
    _require(bool(inspection.get("complete")), "DATASET_PUBLICATION_INCOMPLETE")
    partition_dir = Path(data_root) / "datasets" / "manifests" / "partitions"
    rows: list[dict[str, Any]] = []
    for path in sorted(partition_dir.glob("partition-*.json")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            part = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise LiveCohortReleaseError("CANONICAL_ROOT_INCOMPLETE")
        if not isinstance(part, Mapping):
            raise LiveCohortReleaseError("CANONICAL_ROOT_INCOMPLETE")
        if str(part.get("dataset_manifest_id") or "") != current_mid:
            continue
        partition_id = str(part.get("partition_id") or "")
        if kind == "census" and not partition_id.endswith("-CENSUS"):
            continue
        if kind == "observations" and not partition_id.endswith("-OBS"):
            continue
        location = str(part.get("logical_location") or "")
        parquet_path = Path(data_root) / location
        _require(
            parquet_path.is_file() and not parquet_path.is_symlink(),
            "LIVE_CORPUS_PARQUET_MISSING",
        )
        table = pq.read_table(parquet_path)
        rows.extend(table.to_pylist())
    _require(bool(rows), "CANONICAL_ROOT_INCOMPLETE")
    return rows


def import_live_cohort(
    *,
    release_root: Path,
    data_root: Path,
    import_time: datetime | None = None,
    fault_before_visibility=None,
) -> dict[str, Any]:
    """Import verified live cohort into cumulative LIVE CORPUS (idempotent)."""
    from solana_alpha_lab.factory.live_corpus_manifest_publish import (
        import_live_cohort_canonical,
    )

    return import_live_cohort_canonical(
        release_root=release_root,
        data_root=data_root,
        import_time=import_time,
        fault_before_visibility=fault_before_visibility,
    )


def repair_live_corpus_manifests(
    *,
    data_root: Path,
    published_at: datetime | None = None,
    fault_before_visibility=None,
) -> dict[str, Any]:
    """Metadata-only TASK-06 repair of the current LIVE CORPUS root."""
    from solana_alpha_lab.factory.live_corpus_manifest_publish import (
        repair_live_corpus_manifests as _repair,
    )

    return _repair(
        data_root=data_root,
        published_at=published_at,
        fault_before_visibility=fault_before_visibility,
    )


def live_cohort_status(
    *,
    observation_rdp_root: Path,
    cohort_id: str,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    source = load_observation_rdp_source(observation_rdp_root, cohort_id=cohort_id)
    readiness = classify_cohort_readiness(source, cohort_id=cohort_id, as_of=as_of)
    producers = _producer_fields(source)
    return {
        "schedule_sha256": source["schedule_sha256"],
        "activation_id": source["activation_id"],
        "cohort_id": source.get("cohort_id") or cohort_id,
        "starts_at": source.get("starts_at"),
        "stops_admitting_at": source.get("stops_admitting_at"),
        "admission_field": COHORT_ADMISSION_FIELD,
        "readiness": readiness,
        **producers,
    }


def select_current_datasets_for_forge(
    enumerated: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """One current version per logical dataset_id for bounded HFIC context."""
    by_logical: dict[str, list[dict[str, Any]]] = {}
    for item in enumerated:
        labels = item.get("labels") if isinstance(item.get("labels"), Mapping) else {}
        dataset_id = str(item.get("dataset_id") or "")
        logical = None
        if isinstance(labels, Mapping):
            logical = labels.get("logical_dataset_id")
        if not isinstance(logical, str) or not logical:
            logical = dataset_id or str(item.get("dataset_manifest_id") or "")
        if logical == CORPUS_DATASET_ID and dataset_id != CORPUS_DATASET_ID:
            logical = dataset_id or str(item.get("dataset_manifest_id") or "")
        by_logical.setdefault(logical, []).append(dict(item))

    selected: list[dict[str, Any]] = []
    for _logical, group in by_logical.items():
        if len(group) == 1:
            selected.append(group[0])
            continue

        def _rank(entry: Mapping[str, Any]) -> tuple[int, str]:
            labels_inner = (
                entry.get("labels") if isinstance(entry.get("labels"), Mapping) else {}
            )
            version = 0
            if isinstance(labels_inner, Mapping):
                raw = labels_inner.get("corpus_version")
                if isinstance(raw, int):
                    version = raw
                elif isinstance(raw, str) and raw.isdigit():
                    version = int(raw)
                if labels_inner.get("is_current_corpus_version") is True:
                    version = max(version, 10**9)
            return (version, str(entry.get("dataset_manifest_id") or ""))

        group.sort(key=_rank)
        selected.append(group[-1])
    selected.sort(key=lambda item: str(item.get("dataset_manifest_id") or ""))
    return selected
