"""Live cohort Discovery Evidence Release → versioned LIVE LIFECYCLE CORPUS.

Wraps Discovery Evidence Release / Tokens V2 / RDP manifests. Does not mutate
historical A3 singleton release bytes. Zero network.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.discovery_evidence_release import (
    DiscoveryReleaseError,
    _publish_bytes,
    _render_utc,
    _require,
    _schema_sha256,
    sha256_bytes,
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
    SOURCE_MANIFEST_NAME,
    SOURCE_MEMBERS_NAME,
    SOURCE_OBSERVATIONS_NAME,
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
    note_full_member_rows,
    note_member_file_open,
    note_member_full_column_scan,
    note_observation_rows,
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
    MembersDeltaError,
    iter_member_row_batches_for_location,
    publication_seq_for_location,
    read_member_layout,
)
from solana_alpha_lab.factory.research_store import (
    ExistingResearchStoreReader,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256
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
from solana_alpha_lab.storage.manifests import (
    canonical_manifest_bytes,
    compute_dataset_manifest_id,
)

CORPUS_DATASET_ID = "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"
CORPUS_SCHEMA_ID = "SCHEMA-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"
GENERATION_TASK_ID = "LIVE_COHORT_DISCOVERY_RELEASE_SERIES_V1"
LIVE_EVIDENCE_ROLE = "EXPLORATORY_REUSE"
COMMIT_POINT_KIND = "LIVE_LIFECYCLE_DISCOVERY_CORPUS_PUBLICATION_V1"
COHORT_ADMISSION_FIELD = "discovery_first_reliable_available_at"
ADMISSION_REPRESENTATIONS = (
    COHORT_ADMISSION_FIELD,
    "first_reliable_available_at",
    "discovery_available_at",
)
COHORT_WINDOW_DAYS = 7
RELEASE_SCHEMA = "smial.live-cohort-discovery-release"
RELEASE_SCHEMA_VERSION = "1.0"
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


def campaign_cohort_windows(
    starts_at: datetime,
    stops_admitting_at: datetime,
) -> list[tuple[str, datetime, datetime]]:
    """Half-open [S+k*7d, S+(k+1)*7d) windows until stops_admitting_at."""
    start = starts_at.astimezone(UTC)
    stop = stops_admitting_at.astimezone(UTC)
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
    )


def _lineage_from_rdp(
    observation_rdp_root: Path,
    *,
    schedule_sha256: str,
    activation_id: str,
) -> tuple[dict[str, Any], str | None, list[dict[str, Any]]]:
    """Bind schedule by digest; require unambiguous activation-scoped lifecycle."""
    wanted = str(activation_id or "").strip()
    _require(bool(wanted), "LIVE_SOURCE_ACTIVATION_MISSING")
    try:
        store = ExistingResearchStoreReader(Path(observation_rdp_root))
    except ResearchStoreError as exc:
        raise LiveCohortReleaseError("LIVE_SOURCE_RDP_UNREADABLE") from exc
    schedule_docs: list[dict[str, Any]] = []
    schedule_producers: set[str] = set()
    activation_evidence = False
    seen_activations: set[str] = set()
    lifecycle_rows: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
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
            if event_activation:
                seen_activations.add(event_activation)
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
    if not activation_evidence:
        raise LiveCohortReleaseError("LIVE_SOURCE_ACTIVATION_MISSING")
    schedule_producer = None
    if len(schedule_producers) == 1:
        schedule_producer = next(iter(schedule_producers))
    elif len(schedule_producers) > 1:
        raise LiveCohortReleaseError("IDENTITY_CONFLICT")
    return schedule_doc, schedule_producer, lifecycle_rows


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
        location = str(payload.get("observation_location") or payload.get("logical_location") or "")
        hits_c1 = False
        if location:
            path = Path(observation_rdp_root) / location
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
) -> tuple[set[str], int]:
    """Latest-snapshot full scan; older same-unit SNAPSHOT_PLUS_DELTA uses removed rows."""
    conn.execute(
        """
        CREATE TABLE members (
            mint TEXT PRIMARY KEY,
            admission TEXT NOT NULL,
            producer_git_sha TEXT,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE TABLE needed (mint TEXT PRIMARY KEY)")
    flags = location_flags if location_flags is not None else {}
    batches: list[tuple[int, str, Mapping[str, Any], str | None]] = []
    for index, row in enumerate(lifecycle_rows):
        if str(row.get("kind") or "") != "OBSERVATION_MEMBER_BATCH":
            continue
        if not _lifecycle_row_at_or_before_cutoff(row, cutoff_at):
            continue
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            continue
        location = str(payload.get("member_location") or "")
        if not location:
            continue
        batches.append(
            (
                index,
                str(row.get("effective_at") or ""),
                payload,
                _sha40(row.get("producer_git_sha")),
            )
        )
    batches.sort(key=lambda item: (item[1], item[0]), reverse=True)
    winning_producers: set[str] = set()
    unit_removed: dict[str, list[dict[str, Any]]] = {}
    latest_has_in = False

    def _ingest(member: Mapping[str, Any], producer_sha: str | None) -> bool:
        if not isinstance(member, Mapping):
            return False
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
            return loc_later
        normalized = _normalize_member_row(
            row,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            sampling_policy=sampling_policy,
            sampling_seed_default=sampling_seed,
            inclusion_probability_default=inclusion_probability,
        )
        if normalized is None:
            return loc_later
        entity = str(normalized.get("mint") or "")
        if not entity:
            return loc_has_in or loc_later
        conn.execute(
            "INSERT OR IGNORE INTO members(mint, admission, producer_git_sha, payload_json) VALUES (?,?,?,?)",
            (
                entity,
                str(normalized.get(COHORT_ADMISSION_FIELD) or ""),
                producer_sha,
                json.dumps(normalized, sort_keys=True, separators=(",", ":")),
            ),
        )
        if int(conn.execute("SELECT changes()").fetchone()[0]) != 1:
            return loc_has_in or loc_later
        if producer_sha:
            winning_producers.add(producer_sha)
        return loc_has_in or loc_later

    for rank, (_index, _order, payload, producer) in enumerate(batches):
        location = str(payload.get("member_location") or "")
        layout = read_member_layout(observation_rdp_root, location)
        unit_rel = (
            str(layout.get("unit_rel") or "")
            if isinstance(layout, Mapping) and str(layout.get("kind") or "") == LAYOUT_KIND
            else ""
        )
        loc_seq = publication_seq_for_location(observation_rdp_root, location, layout)
        if rank > 0 and unit_rel and unit_rel in unit_removed:
            recovered: list[dict[str, Any]] = []
            for item in unit_removed[unit_rel]:
                removed_at = item.get("_delta_removed_at_seq")
                if loc_seq is not None and removed_at is not None:
                    try:
                        if int(removed_at) <= loc_seq:
                            continue
                    except (TypeError, ValueError):
                        pass
                recovered.append(item)
                _ingest(item, producer)
            has_in = latest_has_in
            later = False
            for member in recovered:
                admission = resolve_cohort_admission_instant(
                    {key: value for key, value in member.items() if key != "_delta_removed_at_seq"}
                )
                if admission is None:
                    continue
                if window_start <= admission < window_end:
                    has_in = True
                elif admission >= window_end:
                    later = True
            flags[location] = (has_in, later)
            continue
        if rank == 0:
            removed_acc: list[dict[str, Any]] = []
            loc_has_in = False
            loc_later = False
            for batch in _iter_member_batches(
                observation_rdp_root,
                location,
                columns=None,
                removed_out=removed_acc if unit_rel else None,
            ):
                for member in batch:
                    if not isinstance(member, Mapping):
                        continue
                    admission = resolve_cohort_admission_instant(member)
                    if admission is not None:
                        if window_start <= admission < window_end:
                            loc_has_in = True
                        elif admission >= window_end:
                            loc_later = True
                    _ingest(member, producer)
            flags[location] = (loc_has_in, loc_later)
            latest_has_in = loc_has_in
            if unit_rel:
                unit_removed[unit_rel] = removed_acc
            continue
        conn.execute("DELETE FROM needed")
        loc_has_in = False
        loc_later = False
        probe_cols = ("entity_id", "mint", *ADMISSION_REPRESENTATIONS)
        for batch in _iter_member_batches(
            observation_rdp_root, location, columns=probe_cols
        ):
            for member in batch:
                admission = resolve_cohort_admission_instant(member)
                if admission is None:
                    continue
                if window_start <= admission < window_end:
                    loc_has_in = True
                    entity = str(member.get("entity_id") or member.get("mint") or "")
                    if entity and conn.execute(
                        "SELECT 1 FROM members WHERE mint=?", (entity,)
                    ).fetchone() is None:
                        conn.execute(
                            "INSERT OR IGNORE INTO needed(mint) VALUES (?)", (entity,)
                        )
                elif admission >= window_end:
                    loc_later = True
        flags[location] = (loc_has_in, loc_later)
        if int(conn.execute("SELECT COUNT(*) FROM needed").fetchone()[0]) == 0:
            continue
        for batch in _iter_member_batches(observation_rdp_root, location, columns=None):
            for member in batch:
                if not isinstance(member, Mapping):
                    continue
                entity = str(member.get("entity_id") or member.get("mint") or "")
                if not entity:
                    continue
                if conn.execute("SELECT 1 FROM needed WHERE mint=?", (entity,)).fetchone() is None:
                    continue
                if conn.execute("SELECT 1 FROM members WHERE mint=?", (entity,)).fetchone() is not None:
                    continue
                admission = resolve_cohort_admission_instant(member)
                if admission is None or not (window_start <= admission < window_end):
                    continue
                _ingest(member, producer)
                conn.execute("DELETE FROM needed WHERE mint=?", (entity,))
            if int(conn.execute("SELECT COUNT(*) FROM needed").fetchone()[0]) == 0:
                break
    conn.execute("DELETE FROM needed")
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
) -> datetime | None:
    """First publication time of each C1 observation identity, max of those <= not_after.

    Republished C1 rows in a later mixed panel do not advance the freeze horizon.
    """
    def _in_cohort(mint: str) -> bool:
        if mint_is_member is not None:
            return mint_is_member(mint)
        if cohort_mints is not None:
            return mint in cohort_mints
        return False

    if mint_is_member is None and not cohort_mints:
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
        for manifest_order, _manifest_id, location in _iter_observation_panel_locations(
            observation_rdp_root, not_after=not_after, skip_unparseable=True
        ):
            path = Path(observation_rdp_root) / location
            if not path.is_file():
                continue
            stamp = _render_utc(manifest_order)
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
            except (OSError, pa.ArrowException):
                continue
        conn.commit()
        row = conn.execute("SELECT MAX(seen_at) FROM first_seen").fetchone()
        if not row or row[0] is None:
            return None
        return _parse_utc(str(row[0]))
    finally:
        conn.close()
        spill.unlink(missing_ok=True)


def _iter_observation_panel_locations(
    observation_rdp_root: Path,
    *,
    not_after: datetime | None,
    newest_first: bool = False,
    skip_unparseable: bool = False,
) -> Iterator[tuple[datetime, str, str]]:
    manifests_dir = Path(observation_rdp_root) / "datasets" / "manifests"
    if not manifests_dir.is_dir():
        return
    found: list[tuple[datetime, str, str]] = []
    for marker in sorted(manifests_dir.glob("dataset-*.published")):
        try:
            marker_payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        manifest_id = str(marker_payload.get("dataset_manifest_id") or "")
        manifest_path = manifests_dir / f"{manifest_id}.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, Mapping):
            continue
        if str(manifest.get("dataset_id") or "").startswith("observation-panel-") is False:
            continue
        try:
            manifest_order = _parse_utc(
                str(manifest.get("created_at") or manifest.get("first_reliable_available_at"))
            )
        except Exception:
            if skip_unparseable:
                continue
            manifest_order = datetime.min.replace(tzinfo=UTC)
        if not_after is not None and manifest_order > not_after:
            continue
        partitions = list(manifest.get("partitions") or [])
        if not partitions:
            partitions_dir = manifests_dir / "partitions"
            if partitions_dir.is_dir():
                for partition_path in sorted(partitions_dir.glob("partition-*.json")):
                    try:
                        partition = json.loads(partition_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    if (
                        isinstance(partition, Mapping)
                        and str(partition.get("dataset_manifest_id") or "") == manifest_id
                    ):
                        partitions.append(partition)
        for partition in partitions:
            if str(partition.get("partition_id") or "").endswith("-members"):
                continue
            location = str(partition.get("logical_location") or "")
            if location:
                found.append((manifest_order, manifest_id, location))
    found.sort(key=lambda item: (item[0], item[1]), reverse=newest_first)
    yield from found


def _cohort_observations_into_sqlite(
    observation_rdp_root: Path,
    *,
    conn: Any,
    schedule_sha256: str,
    activation_id: str,
    mint_is_member: Callable[[str], bool],
    cutoff_at: datetime | None = None,
) -> int:
    """C1 observations by member mint identity; newest panel wins."""
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
    for _order, _manifest_id, location in _iter_observation_panel_locations(
        observation_rdp_root, not_after=cutoff_at, newest_first=False
    ):
        path = Path(observation_rdp_root) / location
        if not path.is_file():
            continue
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
    conn.commit()
    return int(conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0])


def build_live_observation_source_from_rdp(
    *,
    observation_rdp_root: Path,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str,
    as_of: datetime | None = None,
    closure_receipt: Mapping[str, Any] | None = None,
    discovery_coverage_class: str | None = None,
) -> dict[str, Any]:
    """Rebuild a cohort-scoped live source from immutable Observation RDP."""
    del as_of  # closure receipt already binds as_of; unused for scientific rows
    root = Path(observation_rdp_root)
    _require(
        len(schedule_sha256) == 64
        and all(c in "0123456789abcdef" for c in schedule_sha256),
        "RELEASE_INVALID_SOURCE_INTEGRITY",
    )
    window_start, window_end = cohort_window_bounds(cohort_id)
    closure_flags = _apply_closure_receipt(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        cohort_id=cohort_id,
        closure_receipt=closure_receipt,
    )
    schedule_doc, schedule_producer, lifecycle_rows = _lineage_from_rdp(
        root, schedule_sha256=schedule_sha256, activation_id=activation_id
    )
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
    discard_stale_staging(source_dir)
    staging = new_staging_dir(source_dir)
    spill_path = staging / "extract.sqlite"
    conn = spill_sqlite(spill_path)
    location_flags: dict[str, tuple[bool, bool]] = {}
    try:
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
        )
        contributing = sorted(set(contributing) | winning_producers)
        _cohort_observations_into_sqlite(
            root,
            conn=conn,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            mint_is_member=_member_in_extract,
            cutoff_at=cutoff_at,
        )
        observed_classes = [lineage_coverage]
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
        member_count = write_parquet_from_row_batches(
            members_path, _member_batches(), schema=MEMBER_SCHEMA
        )
        observation_count = write_parquet_from_row_batches(
            obs_path, _obs_batches(), schema=OBSERVATION_SCHEMA
        )
        _require(member_count == extracted_members, "RELEASE_INVALID_SOURCE_INTEGRITY")
        members_sha = sha256_file_streaming(members_path)
        observations_sha = sha256_file_streaming(obs_path)
        snapshot: dict[str, Any] = {
            "schema": SOURCE_BUNDLE_SCHEMA,
            "schema_version": SOURCE_BUNDLE_SCHEMA_VERSION,
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
            "members_partition": SOURCE_MEMBERS_NAME,
            "observations_partition": SOURCE_OBSERVATIONS_NAME,
            "source_representation": SOURCE_REPRESENTATION_BUNDLE,
            **closure_flags,
        }
        if len(contributing) == 1:
            snapshot["producer_git_sha"] = contributing[0]
        snapshot["source_sha256"] = compute_source_identity(snapshot)
        conn.close()
        conn = None
        spill_path.unlink(missing_ok=True)
        commit_source_bundle(source_dir=source_dir, staging=staging, manifest=snapshot)
    except Exception:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        discard_stale_staging(source_dir)
        raise
    loaded = load_observation_rdp_source(root, cohort_id=cohort_id)
    return compact_source_view(loaded)


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
    return canonical_sha256(
        {
            "schema": RELEASE_SCHEMA,
            "schema_version": RELEASE_SCHEMA_VERSION,
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
    )


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
    release_id = _release_id_for(source, cohort_id)
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
    manifest = {
        "schema": RELEASE_SCHEMA,
        "schema_version": RELEASE_SCHEMA_VERSION,
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
    census_tmp.replace(root / CENSUS_NAME)
    obs_tmp.replace(root / OBSERVATIONS_NAME)
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


def _partition_rebind_id(dataset_manifest_id: str, partition_id: str) -> str:
    digest = sha256_bytes(f"{dataset_manifest_id}:{partition_id}".encode("utf-8"))
    return f"partition-{digest}"


def current_corpus_partition_rows(
    data_root: Path,
    *,
    kind: str = "census",
) -> list[dict[str, Any]]:
    """Read census/observation rows exposed by the current cumulative corpus version."""
    lineage = _load_lineage(data_root)
    current_mid = lineage.get("current_dataset_manifest_id")
    _require(isinstance(current_mid, str) and current_mid, "CURRENT_CORPUS_MISSING")
    partition_dir = Path(data_root) / "datasets" / "manifests" / "partitions"
    rows: list[dict[str, Any]] = []
    for path in sorted(partition_dir.glob("partition-*.json")):
        try:
            part = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(part, Mapping):
            continue
        if str(part.get("dataset_manifest_id") or "") != current_mid:
            continue
        partition_id = str(part.get("partition_id") or "")
        if kind == "census" and not partition_id.endswith("-CENSUS"):
            continue
        if kind == "observations" and not partition_id.endswith("-OBS"):
            continue
        location = str(part.get("logical_location") or "")
        parquet_path = Path(data_root) / location
        if not parquet_path.is_file():
            continue
        table = pq.read_table(parquet_path)
        rows.extend(table.to_pylist())
    return rows


def import_live_cohort(
    *,
    release_root: Path,
    data_root: Path,
    import_time: datetime | None = None,
) -> dict[str, Any]:
    """Import verified live cohort into cumulative LIVE CORPUS (idempotent)."""
    manifest = verify_live_cohort(release_root)
    imported_at = (import_time or datetime.now(tz=UTC)).astimezone(UTC)
    sealed_at = _parse_utc(str(manifest["sealed_at"]))
    _require(imported_at >= sealed_at, "IMPORT_BEFORE_SEAL")
    release_id = str(manifest["release_id"])
    cohort_id = str(manifest["cohort_id"])
    census_path = Path(release_root) / CENSUS_NAME
    obs_path = Path(release_root) / OBSERVATIONS_NAME
    content_sha = sha256_files_concat_streaming([census_path, obs_path])
    census_sha = sha256_file_streaming(census_path)
    obs_sha = sha256_file_streaming(obs_path)

    lineage = _load_lineage(data_root)
    existing_cohorts = list(lineage.get("cohorts") or [])
    for prior in existing_cohorts:
        if not isinstance(prior, Mapping):
            continue
        if prior.get("release_id") == release_id:
            if prior.get("content_sha256") != content_sha:
                raise LiveCohortReleaseError("CANONICAL_TARGET_CONFLICT")
            return {
                "status": "IDEMPOTENT_REIMPORT",
                "cohort_id": cohort_id,
                "release_id": release_id,
                "corpus_version": prior.get("corpus_version"),
                "dataset_manifest_id": prior.get("dataset_manifest_id"),
                "evidence_role": LIVE_EVIDENCE_ROLE,
                "epoch_bump": False,
            }
        if prior.get("cohort_id") == cohort_id:
            raise LiveCohortReleaseError("COHORT_ALREADY_IMPORTED")

    for prior in existing_cohorts:
        if not isinstance(prior, Mapping):
            continue
        for key in (
            "census_rel",
            "obs_rel",
            "census_sha256",
            "observations_sha256",
            "sealed_at",
        ):
            _require(prior.get(key), "CORPUS_LINEAGE_INCOMPLETE")

    version_n = len(existing_cohorts) + 1
    dataset_version = f"corpus-v{version_n}-{cohort_id}"
    dataset_manifest_id = compute_dataset_manifest_id(CORPUS_DATASET_ID, dataset_version)
    census_part_id = f"PARTITION-LIVE-COHORT-{cohort_id}-CENSUS"
    obs_part_id = f"PARTITION-LIVE-COHORT-{cohort_id}-OBS"
    date_key = imported_at.strftime("%Y-%m-%d")
    census_rel = (
        f"datasets/partitions/date={date_key}/{census_part_id}-{release_id[:16]}.parquet"
    )
    obs_rel = (
        f"datasets/partitions/date={date_key}/{obs_part_id}-{release_id[:16]}.parquet"
    )
    available_at = imported_at
    created_at = imported_at

    cumulative_components = [
        {
            "cohort_id": str(c.get("cohort_id")),
            "release_id": str(c.get("release_id")),
            "content_sha256": str(c.get("content_sha256")),
            "census_rel": c.get("census_rel"),
            "obs_rel": c.get("obs_rel"),
            "census_sha256": c.get("census_sha256"),
            "observations_sha256": c.get("observations_sha256"),
            "census_row_count": c.get("census_row_count"),
            "observation_row_count": c.get("observation_row_count"),
            "feature_families": list(c.get("feature_families") or []),
            "yield_eligible": int(c.get("yield_eligible") or 0),
            "yield_missing": int(c.get("yield_missing") or 0),
            "sealed_at": c.get("sealed_at"),
            "first_reliable_available_at": c.get("first_reliable_available_at"),
        }
        for c in existing_cohorts
        if isinstance(c, Mapping)
    ]
    cumulative_components.append(
        {
            "cohort_id": cohort_id,
            "release_id": release_id,
            "content_sha256": content_sha,
            "census_rel": census_rel,
            "obs_rel": obs_rel,
            "census_sha256": census_sha,
            "observations_sha256": obs_sha,
            "census_row_count": int(manifest["census_row_count"]),
            "observation_row_count": int(manifest["observation_row_count"]),
            "feature_families": list(manifest["feature_families"]),
            "yield_eligible": int(manifest["yield_eligible"]),
            "yield_missing": int(manifest["yield_missing"]),
            "sealed_at": _render_utc(sealed_at),
            "first_reliable_available_at": _render_utc(available_at),
        }
    )
    fingerprint = canonical_sha256(
        {
            "dataset_manifest_id": dataset_manifest_id,
            "cumulative_components": cumulative_components,
            "projection_id": PROJECTION_ID,
        }
    )
    cumulative_content_sha = canonical_sha256(
        {"ordered_component_content": [c["content_sha256"] for c in cumulative_components]}
    )
    dataset = DatasetManifest(
        dataset_manifest_id=dataset_manifest_id,
        dataset_id=CORPUS_DATASET_ID,
        dataset_version=dataset_version,
        schema_id=CORPUS_SCHEMA_ID,
        schema_sha256=_schema_sha256(),
        dataset_fingerprint=fingerprint,
        generation_task_id=GENERATION_TASK_ID,
        generation_run_id=f"import-{release_id[:16]}",
        validation_receipt_sha256=sha256_bytes(
            (Path(release_root) / RELEASE_MANIFEST_NAME).read_bytes()
        ),
        first_reliable_available_at=available_at,
        created_at=created_at,
        content_sha256=cumulative_content_sha,
    )

    dest_census = Path(data_root) / census_rel
    dest_obs = Path(data_root) / obs_rel
    dest_census.parent.mkdir(parents=True, exist_ok=True)
    dest_obs.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(census_path, dest_census)
    shutil.copyfile(obs_path, dest_obs)
    root = Path(data_root)

    # Rebind all cumulative cohort partitions onto the new current dataset id.
    # Parquet bytes for prior cohorts are referenced in place (no O(N²) copy).
    for component in cumulative_components:
        for kind, rel_key, sha_key, count_key, part_suffix in (
            (
                "CENSUS",
                "census_rel",
                "census_sha256",
                "census_row_count",
                "-CENSUS",
            ),
            (
                "OBS",
                "obs_rel",
                "observations_sha256",
                "observation_row_count",
                "-OBS",
            ),
        ):
            del kind
            part_id = f"PARTITION-LIVE-COHORT-{component['cohort_id']}{part_suffix}"
            part_manifest_id = _partition_rebind_id(dataset_manifest_id, part_id)
            event_clock = _parse_utc(str(component.get("sealed_at") or _render_utc(sealed_at)))
            avail_clock = _parse_utc(
                str(
                    component.get("first_reliable_available_at")
                    or component.get("sealed_at")
                    or _render_utc(available_at)
                )
            )
            # Partition contract requires first_reliable_available_at >= created_at.
            part_created = min(avail_clock, event_clock, created_at)
            part_available = max(avail_clock, part_created)
            part = PartitionManifest(
                partition_manifest_id=part_manifest_id,
                dataset_manifest_id=dataset_manifest_id,
                partition_id=part_id,
                logical_location=str(component[rel_key]),
                file_sha256=str(component[sha_key]),
                content_sha256=str(component[sha_key]),
                row_count=int(component[count_key] or 0),
                min_event_time=event_clock,
                max_event_time=event_clock,
                min_available_to_strategy_at=part_available,
                max_available_to_strategy_at=part_available,
                first_reliable_available_at=part_available,
                created_at=part_created,
            )
            _publish_bytes(
                root / f"datasets/manifests/partitions/{part_manifest_id}.json",
                canonical_manifest_bytes(part),
            )

    lineage_cohort_ids = [str(c["cohort_id"]) for c in cumulative_components]
    feature_union: list[str] = []
    seen_families: set[str] = set()
    for component in cumulative_components:
        for family in component.get("feature_families") or []:
            if family not in seen_families:
                seen_families.add(str(family))
                feature_union.append(str(family))
    feature_union = [f for f in FEATURE_FAMILY_ORDER if f in set(feature_union)] or feature_union
    yield_eligible_sum = sum(int(c.get("yield_eligible") or 0) for c in cumulative_components)
    yield_missing_sum = sum(int(c.get("yield_missing") or 0) for c in cumulative_components)
    census_rows_sum = sum(int(c.get("census_row_count") or 0) for c in cumulative_components)
    obs_rows_sum = sum(int(c.get("observation_row_count") or 0) for c in cumulative_components)

    labels = {
        **REQUIRED_LABELS,
        "release_id": release_id,
        "cohort_id": cohort_id,
        "corpus_version": version_n,
        "dataset_version": dataset_version,
        "cohort_lineage": lineage_cohort_ids,
        "feature_families": feature_union,
        "feature_hint": None,
        "yield_eligible": yield_eligible_sum,
        "yield_missing": yield_missing_sum,
        "census_row_count_cumulative": census_rows_sum,
        "observation_row_count_cumulative": obs_rows_sum,
        "dataset_terminal": "SAMPLE_VALID",
        "readiness_state": manifest.get("readiness_state"),
        "discovery_coverage_class": manifest.get("discovery_coverage_class"),
        "imported_at": _render_utc(imported_at),
        "accepted_hypothesis_id": None,
        "is_current_corpus_version": True,
        "cumulative_composition": True,
    }
    published = {
        "commit_point": COMMIT_POINT_KIND,
        "dataset_manifest_id": dataset_manifest_id,
        "dataset_fingerprint": fingerprint,
        "release_id": release_id,
        "cohort_id": cohort_id,
        "corpus_version": version_n,
        "imported_at": _render_utc(imported_at),
        "cumulative_cohort_count": len(cumulative_components),
    }

    for prior in existing_cohorts:
        if not isinstance(prior, Mapping):
            continue
        prior_mid = prior.get("dataset_manifest_id")
        if not isinstance(prior_mid, str):
            continue
        labels_path = root / f"datasets/manifests/{prior_mid}.labels.json"
        if labels_path.is_file():
            try:
                old = json.loads(labels_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(old, dict):
                old["is_current_corpus_version"] = False
                labels_path.write_bytes(
                    json.dumps(old, sort_keys=True, separators=(",", ":")).encode(
                        "utf-8"
                    )
                )

    _publish_bytes(
        root / f"datasets/manifests/{dataset_manifest_id}.labels.json",
        json.dumps(labels, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    _publish_bytes(
        root / f"datasets/manifests/{dataset_manifest_id}.json",
        canonical_manifest_bytes(dataset),
    )
    _publish_bytes(
        root / f"datasets/manifests/{dataset_manifest_id}.published",
        json.dumps(published, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )

    existing_cohorts.append(
        {
            "cohort_id": cohort_id,
            "release_id": release_id,
            "content_sha256": content_sha,
            "corpus_version": version_n,
            "dataset_manifest_id": dataset_manifest_id,
            "dataset_version": dataset_version,
            "imported_at": _render_utc(imported_at),
            "census_rel": census_rel,
            "obs_rel": obs_rel,
            "census_sha256": census_sha,
            "observations_sha256": obs_sha,
            "census_row_count": int(manifest["census_row_count"]),
            "observation_row_count": int(manifest["observation_row_count"]),
            "feature_families": list(manifest["feature_families"]),
            "yield_eligible": int(manifest["yield_eligible"]),
            "yield_missing": int(manifest["yield_missing"]),
            "sealed_at": _render_utc(sealed_at),
            "first_reliable_available_at": _render_utc(available_at),
        }
    )
    lineage_out = {
        "corpus_dataset_id": CORPUS_DATASET_ID,
        "current_corpus_version": version_n,
        "current_dataset_manifest_id": dataset_manifest_id,
        "cohorts": existing_cohorts,
        "versions": [
            {
                "corpus_version": c["corpus_version"],
                "dataset_manifest_id": c["dataset_manifest_id"],
                "cohort_id": c["cohort_id"],
            }
            for c in existing_cohorts
        ],
    }
    _write_lineage(data_root, lineage_out)
    return {
        "status": "IMPORTED",
        "cohort_id": cohort_id,
        "release_id": release_id,
        "corpus_version": version_n,
        "dataset_id": CORPUS_DATASET_ID,
        "dataset_version": dataset_version,
        "dataset_manifest_id": dataset_manifest_id,
        "dataset_fingerprint": fingerprint,
        "cohort_lineage": lineage_cohort_ids,
        "evidence_role": LIVE_EVIDENCE_ROLE,
        "feature_families": feature_union,
        "imported_at": _render_utc(imported_at),
        "epoch_bump": True,
        "cumulative_census_rows": census_rows_sum,
        "cumulative_observation_rows": obs_rows_sum,
    }


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
