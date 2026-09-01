"""Live cohort Discovery Evidence Release → versioned LIVE LIFECYCLE CORPUS.

Wraps Discovery Evidence Release / Tokens V2 / RDP manifests. Does not mutate
historical A3 singleton release bytes. Zero network.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.discovery_evidence_release import (
    DiscoveryReleaseError,
    _parquet_bytes,
    _publish_bytes,
    _render_utc,
    _require,
    _schema_sha256,
    sha256_bytes,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.factory.tokens_v2_typed_projection import (
    FEATURE_FAMILY_ORDER,
    PROJECTION_ID,
    PROJECTION_VERSION,
    feature_families_from_typed_values,
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
COHORT_WINDOW_DAYS = 7
RELEASE_SCHEMA = "smial.live-cohort-discovery-release"
RELEASE_SCHEMA_VERSION = "1.0"
RELEASE_MANIFEST_NAME = "release_manifest.json"
CENSUS_NAME = "census.parquet"
OBSERVATIONS_NAME = "observations.parquet"
SOURCE_INVENTORY_NAME = "source_inventory.json"
OBSERVATION_RDP_REBUILD_NAME = "live_observation_rebuild/source_snapshot.json"

SEALABLE_READY = frozenset(
    {
        "READY_VALID",
        "READY_VALID_WITH_COVERAGE_LIMITATION",
        "READY_LOW_YIELD",
    }
)

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
    }
)


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


def cohort_id_for_admission(admission_at: datetime) -> str:
    day = admission_at.astimezone(UTC).date()
    epoch = datetime(1970, 1, 1, tzinfo=UTC).date()
    days = (day - epoch).days
    start_offset = days - (days % COHORT_WINDOW_DAYS)
    start = epoch + timedelta(days=start_offset)
    end = start + timedelta(days=COHORT_WINDOW_DAYS - 1)
    return f"UTC-{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"


def cohort_window_bounds(cohort_id: str) -> tuple[datetime, datetime]:
    _require(
        cohort_id.startswith("UTC-") and cohort_id.count("-") == 2,
        "COHORT_ID_INVALID",
    )
    _, start_s, end_s = cohort_id.split("-", 2)
    start = datetime.strptime(start_s, "%Y%m%d").replace(tzinfo=UTC)
    end_day = datetime.strptime(end_s, "%Y%m%d").replace(tzinfo=UTC)
    end = end_day + timedelta(days=1) - timedelta(microseconds=1)
    return start, end


def write_observation_rdp_source(
    observation_rdp_root: Path, snapshot: Mapping[str, Any]
) -> Path:
    root = Path(observation_rdp_root)
    path = root / OBSERVATION_RDP_REBUILD_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(
            dict(snapshot), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    )
    return path


def load_observation_rdp_source(observation_rdp_root: Path) -> dict[str, Any]:
    """Rebuild scientific source from immutable Observation RDP snapshot."""
    root = Path(observation_rdp_root)
    path = root / OBSERVATION_RDP_REBUILD_NAME
    if not path.is_file() or path.is_symlink():
        raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY") from exc
    _require(isinstance(payload, Mapping), "RELEASE_INVALID_SOURCE_INTEGRITY")
    for key in (
        "schedule_sha256",
        "activation_id",
        "producer_git_sha",
        "members",
        "observations",
    ):
        _require(key in payload, "RELEASE_INVALID_SOURCE_INTEGRITY")
    members = payload["members"]
    observations = payload["observations"]
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
    producer = str(payload["producer_git_sha"])
    _require(
        len(producer) == 40 and all(c in "0123456789abcdef" for c in producer),
        "RELEASE_INVALID_SOURCE_INTEGRITY",
    )
    return {
        "schedule_sha256": schedule_sha,
        "activation_id": str(payload["activation_id"]),
        "producer_git_sha": producer,
        "members": members,
        "observations": observations,
        "source_sha256": sha256_bytes(path.read_bytes()),
        "discovery_coverage_class": str(
            payload.get("discovery_coverage_class") or "GAP_SUSPECTED"
        ),
        "open_publication": bool(payload.get("open_publication") or False),
        "unresolved_due": bool(payload.get("unresolved_due") or False),
        "in_flight": bool(payload.get("in_flight") or False),
        "budget_blocked": bool(payload.get("budget_blocked") or False),
    }


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
    if source.get("open_publication"):
        return {
            "cohort_id": cohort_id,
            "state": "RELEASE_BLOCKED_OPEN_PUBLICATION",
            "sealable": False,
        }
    if source.get("budget_blocked"):
        return {
            "cohort_id": cohort_id,
            "state": "RELEASE_BLOCKED_BUDGET",
            "sealable": False,
        }
    if source.get("unresolved_due"):
        return {
            "cohort_id": cohort_id,
            "state": "RELEASE_BLOCKED_UNRESOLVED_DUE",
            "sealable": False,
        }
    if source.get("in_flight"):
        return {
            "cohort_id": cohort_id,
            "state": "RELEASE_BLOCKED_IN_FLIGHT",
            "sealable": False,
        }

    now = (as_of or datetime.now(tz=UTC)).astimezone(UTC)
    start, end = cohort_window_bounds(cohort_id)
    members = [
        m
        for m in source["members"]
        if isinstance(m, Mapping)
        and isinstance(m.get(COHORT_ADMISSION_FIELD), str)
        and start <= _parse_utc(str(m[COHORT_ADMISSION_FIELD])) <= end
    ]
    if not members:
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
            "member_count": len(members),
        }

    mature_at = end + timedelta(seconds=86400)
    if now < mature_at:
        return {
            "cohort_id": cohort_id,
            "state": "MATURING",
            "sealable": False,
            "member_count": len(members),
        }

    denom = {state: 0 for state in DENOMINATOR_STATES}
    for m in members:
        state = str(m.get("denominator_state") or "discovered")
        if state in denom:
            denom[state] += 1
        else:
            denom["discovered"] += 1

    n = len(members)
    observed = denom.get("observed", 0) + denom.get("typed_missing", 0)
    coverage_limited = str(source.get("discovery_coverage_class") or "") in {
        "GAP_SUSPECTED",
        "GAP_CONFIRMED",
        "DISCOVERY_COVERAGE_UNKNOWN",
    }
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
        "window_end": _render_utc(end),
    }


def _release_id_for(source: Mapping[str, Any], cohort_id: str) -> str:
    return canonical_sha256(
        {
            "schema": RELEASE_SCHEMA,
            "schema_version": RELEASE_SCHEMA_VERSION,
            "cohort_id": cohort_id,
            "schedule_sha256": source["schedule_sha256"],
            "activation_id": source["activation_id"],
            "producer_git_sha": source["producer_git_sha"],
            "source_sha256": source["source_sha256"],
            "admission_field": COHORT_ADMISSION_FIELD,
            "projection_id": PROJECTION_ID,
            "projection_version": PROJECTION_VERSION,
        }
    )


def _build_live_tables(
    source: Mapping[str, Any],
    *,
    cohort_id: str,
    release_id: str,
) -> tuple[pa.Table, pa.Table, list[str], int, int]:
    start, end = cohort_window_bounds(cohort_id)
    census_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    typed_for_families: list[dict[str, Any]] = []
    mints_in: set[str] = set()

    for member in source["members"]:
        if not isinstance(member, Mapping):
            continue
        admission = member.get(COHORT_ADMISSION_FIELD)
        if not isinstance(admission, str):
            continue
        adm_dt = _parse_utc(admission)
        if not (start <= adm_dt <= end):
            continue
        mint = str(member.get("mint") or "")
        _require(bool(mint), "TOKEN_MINT_MISSING")
        mints_in.add(mint)
        census_rows.append(
            {
                "release_id": release_id,
                "cohort_id": cohort_id,
                "source_schedule_sha256": source["schedule_sha256"],
                "activation_id": source["activation_id"],
                "producer_git_sha": source["producer_git_sha"],
                "mint": mint,
                "discovery_first_reliable_available_at": admission,
                "authoritative_anchor": member.get("authoritative_anchor"),
                "candidate_state": member.get("candidate_state") or "CANDIDATE",
                "membership_state": member.get("membership_state") or "INCLUDED",
                "denominator_state": member.get("denominator_state") or "discovered",
                "sampling_policy": member.get("sampling_policy"),
                "sampling_seed": member.get("sampling_seed"),
                "inclusion_probability": str(member.get("inclusion_probability") or ""),
                "selected_or_excluded": member.get("selected_or_excluded") or "SELECTED",
                "exclusion_reason": member.get("exclusion_reason"),
                "discovery_coverage_class": source.get("discovery_coverage_class"),
                "source_request_sha256": member.get("source_request_sha256"),
                "source_response_sha256": member.get("source_response_sha256"),
                "evidence_role": LIVE_EVIDENCE_ROLE,
            }
        )

    for obs in source["observations"]:
        if not isinstance(obs, Mapping):
            continue
        mint = str(obs.get("mint") or "")
        if mint not in mints_in:
            continue
        point_id = str(obs.get("point_id") or "")
        _require(point_id and point_id != "R0", "LIVE_POINT_ID_REQUIRED")
        typed = {
            "field_id": obs.get("field_id"),
            "value_kind": obs.get("value_kind"),
            "typed_value": obs.get("typed_value"),
            "state": obs.get("state"),
            "missing_reason": obs.get("missing_reason"),
        }
        typed_for_families.append(typed)
        typed_value = obs.get("typed_value")
        if not isinstance(typed_value, str):
            typed_value = json.dumps(typed_value, sort_keys=True)
        observation_rows.append(
            {
                "release_id": release_id,
                "cohort_id": cohort_id,
                "mint": mint,
                "point_id": point_id,
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
                "http_status": obs.get("http_status"),
                "http_class": obs.get("http_class"),
                "evidence_role": LIVE_EVIDENCE_ROLE,
                "confirmatory_reuse_forbidden": True,
            }
        )

    _require(bool(census_rows), "COHORT_EMPTY")
    families = feature_families_from_typed_values(typed_for_families)
    families = [f for f in FEATURE_FAMILY_ORDER if f in set(families)] or list(
        FEATURE_FAMILY_ORDER[:1]
    )
    yield_eligible = sum(
        1 for r in census_rows if str(r.get("denominator_state")) == "observed"
    )
    yield_missing = sum(
        1
        for r in census_rows
        if str(r.get("denominator_state"))
        in {"typed_missing", "censored_late", "disappeared"}
    )
    return (
        pa.Table.from_pylist(census_rows),
        pa.Table.from_pylist(observation_rows),
        families,
        yield_eligible,
        yield_missing,
    )


def seal_live_cohort(
    *,
    observation_rdp_root: Path,
    cohort_id: str,
    release_root: Path,
    sealed_at: datetime | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    source = load_observation_rdp_source(observation_rdp_root)
    readiness = classify_cohort_readiness(source, cohort_id=cohort_id, as_of=as_of)
    _require(readiness.get("sealable") is True, str(readiness.get("state") or "NOT_READY"))
    release_id = _release_id_for(source, cohort_id)
    census, observations, families, yield_eligible, yield_missing = _build_live_tables(
        source, cohort_id=cohort_id, release_id=release_id
    )
    sealed = (sealed_at or datetime.now(tz=UTC)).astimezone(UTC)
    root = Path(release_root)
    root.mkdir(parents=True, exist_ok=True)
    census_bytes = _parquet_bytes(census)
    obs_bytes = _parquet_bytes(observations)
    inventory = {
        "cohort_id": cohort_id,
        "schedule_sha256": source["schedule_sha256"],
        "activation_id": source["activation_id"],
        "producer_git_sha": source["producer_git_sha"],
        "source_sha256": source["source_sha256"],
        "admission_field": COHORT_ADMISSION_FIELD,
        "readiness_state": readiness["state"],
        "discovery_coverage_class": source.get("discovery_coverage_class"),
    }
    manifest = {
        "schema": RELEASE_SCHEMA,
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_id": release_id,
        "cohort_id": cohort_id,
        "sealed_at": _render_utc(sealed),
        "schedule_sha256": source["schedule_sha256"],
        "activation_id": source["activation_id"],
        "producer_git_sha": source["producer_git_sha"],
        "source_sha256": source["source_sha256"],
        "admission_field": COHORT_ADMISSION_FIELD,
        "evidence_role": LIVE_EVIDENCE_ROLE,
        "confirmatory_reuse_forbidden": True,
        "census_sha256": sha256_bytes(census_bytes),
        "observations_sha256": sha256_bytes(obs_bytes),
        "census_row_count": census.num_rows,
        "observation_row_count": observations.num_rows,
        "feature_families": families,
        "yield_eligible": yield_eligible,
        "yield_missing": yield_missing,
        "readiness_state": readiness["state"],
        "discovery_coverage_class": source.get("discovery_coverage_class"),
        "projection_id": PROJECTION_ID,
        "projection_version": PROJECTION_VERSION,
    }
    _publish_bytes(root / CENSUS_NAME, census_bytes)
    _publish_bytes(root / OBSERVATIONS_NAME, obs_bytes)
    _publish_bytes(
        root / SOURCE_INVENTORY_NAME,
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    _publish_bytes(
        root / RELEASE_MANIFEST_NAME,
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
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
    census_bytes = (root / CENSUS_NAME).read_bytes()
    obs_bytes = (root / OBSERVATIONS_NAME).read_bytes()
    _require(
        sha256_bytes(census_bytes) == manifest.get("census_sha256"),
        "CENSUS_HASH_MISMATCH",
    )
    _require(
        sha256_bytes(obs_bytes) == manifest.get("observations_sha256"),
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


def import_live_cohort(
    *,
    release_root: Path,
    data_root: Path,
    import_time: datetime | None = None,
) -> dict[str, Any]:
    """Import verified live cohort into versioned LIVE CORPUS (idempotent)."""
    manifest = verify_live_cohort(release_root)
    imported_at = (import_time or datetime.now(tz=UTC)).astimezone(UTC)
    sealed_at = _parse_utc(str(manifest["sealed_at"]))
    _require(imported_at >= sealed_at, "IMPORT_BEFORE_SEAL")
    release_id = str(manifest["release_id"])
    cohort_id = str(manifest["cohort_id"])
    census_bytes = (Path(release_root) / CENSUS_NAME).read_bytes()
    obs_bytes = (Path(release_root) / OBSERVATIONS_NAME).read_bytes()
    content_sha = sha256_bytes(census_bytes + obs_bytes)

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

    version_n = len(existing_cohorts) + 1
    dataset_version = f"corpus-v{version_n}-{cohort_id}"
    dataset_manifest_id = compute_dataset_manifest_id(CORPUS_DATASET_ID, dataset_version)
    census_part_id = f"PARTITION-LIVE-COHORT-{cohort_id}-CENSUS"
    obs_part_id = f"PARTITION-LIVE-COHORT-{cohort_id}-OBS"
    census_part_manifest_id = f"PARTITION-MANIFEST-LIVE-COHORT-{cohort_id}-CENSUS"
    obs_part_manifest_id = f"PARTITION-MANIFEST-LIVE-COHORT-{cohort_id}-OBS"
    date_key = imported_at.strftime("%Y-%m-%d")
    census_rel = (
        f"datasets/partitions/date={date_key}/{census_part_id}-{release_id[:16]}.parquet"
    )
    obs_rel = (
        f"datasets/partitions/date={date_key}/{obs_part_id}-{release_id[:16]}.parquet"
    )
    fingerprint = canonical_sha256(
        {
            "dataset_manifest_id": dataset_manifest_id,
            "release_id": release_id,
            "content_sha256": content_sha,
            "lineage_cohorts": [c.get("cohort_id") for c in existing_cohorts]
            + [cohort_id],
            "projection_id": PROJECTION_ID,
        }
    )
    available_at = imported_at
    created_at = imported_at
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
        content_sha256=content_sha,
    )
    census_part = PartitionManifest(
        partition_manifest_id=census_part_manifest_id,
        dataset_manifest_id=dataset_manifest_id,
        partition_id=census_part_id,
        logical_location=census_rel,
        file_sha256=sha256_bytes(census_bytes),
        content_sha256=sha256_bytes(census_bytes),
        row_count=int(manifest["census_row_count"]),
        min_event_time=sealed_at,
        max_event_time=sealed_at,
        min_available_to_strategy_at=available_at,
        max_available_to_strategy_at=available_at,
        first_reliable_available_at=available_at,
        created_at=created_at,
    )
    obs_part = PartitionManifest(
        partition_manifest_id=obs_part_manifest_id,
        dataset_manifest_id=dataset_manifest_id,
        partition_id=obs_part_id,
        logical_location=obs_rel,
        file_sha256=sha256_bytes(obs_bytes),
        content_sha256=sha256_bytes(obs_bytes),
        row_count=int(manifest["observation_row_count"]),
        min_event_time=sealed_at,
        max_event_time=sealed_at,
        min_available_to_strategy_at=available_at,
        max_available_to_strategy_at=available_at,
        first_reliable_available_at=available_at,
        created_at=created_at,
    )
    lineage_cohort_ids = [str(c.get("cohort_id")) for c in existing_cohorts] + [
        cohort_id
    ]
    labels = {
        **REQUIRED_LABELS,
        "release_id": release_id,
        "cohort_id": cohort_id,
        "corpus_version": version_n,
        "dataset_version": dataset_version,
        "cohort_lineage": lineage_cohort_ids,
        "feature_families": list(manifest["feature_families"]),
        "feature_hint": None,
        "yield_eligible": int(manifest["yield_eligible"]),
        "yield_missing": int(manifest["yield_missing"]),
        "dataset_terminal": "SAMPLE_VALID",
        "readiness_state": manifest.get("readiness_state"),
        "discovery_coverage_class": manifest.get("discovery_coverage_class"),
        "imported_at": _render_utc(imported_at),
        "accepted_hypothesis_id": None,
        "is_current_corpus_version": True,
    }
    published = {
        "commit_point": COMMIT_POINT_KIND,
        "dataset_manifest_id": dataset_manifest_id,
        "dataset_fingerprint": fingerprint,
        "release_id": release_id,
        "cohort_id": cohort_id,
        "corpus_version": version_n,
        "imported_at": _render_utc(imported_at),
    }
    root = Path(data_root)
    _publish_bytes(root / census_rel, census_bytes)
    _publish_bytes(root / obs_rel, obs_bytes)
    _publish_bytes(
        root / f"datasets/manifests/partitions/{census_part_manifest_id}.json",
        canonical_manifest_bytes(census_part),
    )
    _publish_bytes(
        root / f"datasets/manifests/partitions/{obs_part_manifest_id}.json",
        canonical_manifest_bytes(obs_part),
    )
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
        "feature_families": list(manifest["feature_families"]),
        "imported_at": _render_utc(imported_at),
        "epoch_bump": True,
    }


def live_cohort_status(
    *,
    observation_rdp_root: Path,
    cohort_id: str,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    source = load_observation_rdp_source(observation_rdp_root)
    readiness = classify_cohort_readiness(source, cohort_id=cohort_id, as_of=as_of)
    return {
        "schedule_sha256": source["schedule_sha256"],
        "activation_id": source["activation_id"],
        "producer_git_sha": source["producer_git_sha"],
        "admission_field": COHORT_ADMISSION_FIELD,
        "readiness": readiness,
    }


def select_current_datasets_for_forge(
    enumerated: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """One current version per logical dataset_id for bounded HFIC context."""
    by_logical: dict[str, list[dict[str, Any]]] = {}
    for item in enumerated:
        labels = item.get("labels") if isinstance(item.get("labels"), Mapping) else {}
        logical = None
        if isinstance(labels, Mapping):
            logical = labels.get("logical_dataset_id")
        if not isinstance(logical, str) or not logical:
            logical = str(item.get("dataset_id") or item.get("dataset_manifest_id") or "")
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
