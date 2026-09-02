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
import pyarrow.parquet as pq

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
from solana_alpha_lab.factory.observation_panel_publisher import (
    rebuild_observation_panel_from_rdp,
)
from solana_alpha_lab.factory.research_store import ResearchStore
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


def _validate_source_payload(payload: Mapping[str, Any], *, source_sha256: str) -> dict[str, Any]:
    for key in (
        "schedule_sha256",
        "activation_id",
        "producer_git_sha",
        "members",
        "observations",
        "starts_at",
        "stops_admitting_at",
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
    starts = str(payload["starts_at"])
    stops = str(payload["stops_admitting_at"])
    _parse_utc(starts)
    _parse_utc(stops)
    return {
        "schedule_sha256": schedule_sha,
        "activation_id": str(payload["activation_id"]),
        "producer_git_sha": producer,
        "starts_at": starts,
        "stops_admitting_at": stops,
        "members": members,
        "observations": observations,
        "source_sha256": source_sha256,
        "discovery_coverage_class": str(
            payload.get("discovery_coverage_class") or "GAP_SUSPECTED"
        ),
        "open_publication": bool(payload.get("open_publication") or False),
        "unresolved_due": bool(payload.get("unresolved_due") or False),
        "in_flight": bool(payload.get("in_flight") or False),
        "budget_blocked": bool(payload.get("budget_blocked") or False),
    }


def load_observation_rdp_source(observation_rdp_root: Path) -> dict[str, Any]:
    """Load previously built live source snapshot from Observation RDP."""
    root = Path(observation_rdp_root)
    path = root / OBSERVATION_RDP_REBUILD_NAME
    if not path.is_file() or path.is_symlink():
        raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveCohortReleaseError("RELEASE_INVALID_SOURCE_INTEGRITY") from exc
    _require(isinstance(payload, Mapping), "RELEASE_INVALID_SOURCE_INTEGRITY")
    return _validate_source_payload(payload, source_sha256=sha256_bytes(path.read_bytes()))


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
    admission = row.get(COHORT_ADMISSION_FIELD) or row.get("first_reliable_available_at")
    if not isinstance(admission, str) or not admission:
        return None
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


def _lineage_from_rdp(
    observation_rdp_root: Path,
    *,
    schedule_sha256: str,
    activation_id: str,
) -> tuple[dict[str, Any], str, str | None]:
    """Return schedule document, producer_git_sha, coverage class from RDP events."""
    wanted = str(activation_id or "").strip()
    _require(bool(wanted), "LIVE_SOURCE_ACTIVATION_MISSING")
    store = ResearchStore(Path(observation_rdp_root))
    schedule_doc: dict[str, Any] | None = None
    producers: set[str] = set()
    coverage: str | None = None
    for record in store.iter_committed_records():
        kind = str(record.record_kind)
        try:
            payload = json.loads(record.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        producer = str(record.producer_git_sha or "")
        digest = str(payload.get("schedule_sha256") or "")
        if digest != schedule_sha256:
            continue
        event_activation = _event_activation_id(record, payload)
        if kind == "OBSERVATION_SCHEDULE":
            document = payload.get("schedule")
            if not isinstance(document, Mapping):
                continue
            sched_activation = _schedule_document_activation_id(document)
            if sched_activation and sched_activation != wanted:
                continue
            if event_activation and event_activation != wanted:
                continue
            # Require an explicit activation bind via schedule document and/or run_id.
            if sched_activation != wanted and event_activation != wanted:
                continue
            schedule_doc = dict(document)
            if producer:
                producers.add(producer)
        elif kind == "OBSERVATION_SCHEDULE_AUTHORITY":
            # Authority is schedule-scoped; bind only when run_id matches activation.
            if event_activation == wanted and producer:
                producers.add(producer)
        elif kind in {
            "OBSERVATION_BATCH",
            "OBSERVATION_MEMBER_BATCH",
            "OBSERVATION_PANEL_SNAPSHOT",
        }:
            if event_activation == wanted and producer:
                producers.add(producer)
                if coverage is None:
                    raw = payload.get("discovery_coverage_class")
                    if isinstance(raw, str) and raw.strip():
                        coverage = raw.strip()
    _require(schedule_doc is not None, "LIVE_SOURCE_SCHEDULE_MISSING")
    assert schedule_doc is not None
    if len(producers) > 1:
        raise LiveCohortReleaseError("LIVE_SOURCE_LINEAGE_CONFLICT")
    _require(len(producers) == 1, "LIVE_SOURCE_PRODUCER_MISSING")
    producer_git_sha = next(iter(producers))
    activation = schedule_doc.get("activation")
    _require(isinstance(activation, Mapping), "LIVE_SOURCE_ACTIVATION_MISSING")
    sched_activation = _schedule_document_activation_id(schedule_doc)
    if sched_activation:
        _require(sched_activation == wanted, "LIVE_SOURCE_ACTIVATION_MISMATCH")
    return schedule_doc, producer_git_sha, coverage


def build_live_observation_source_from_rdp(
    *,
    observation_rdp_root: Path,
    schedule_sha256: str,
    activation_id: str,
    discovery_coverage_class: str | None = None,
    open_publication: bool = False,
    unresolved_due: bool = False,
    in_flight: bool = False,
    budget_blocked: bool = False,
) -> dict[str, Any]:
    """Deterministically rebuild live release source from immutable Observation RDP."""
    root = Path(observation_rdp_root)
    _require(
        len(schedule_sha256) == 64
        and all(c in "0123456789abcdef" for c in schedule_sha256),
        "RELEASE_INVALID_SOURCE_INTEGRITY",
    )
    schedule_doc, producer_git_sha, lineage_coverage = _lineage_from_rdp(
        root, schedule_sha256=schedule_sha256, activation_id=activation_id
    )
    activation = schedule_doc.get("activation")
    assert isinstance(activation, Mapping)
    starts_at = str(activation.get("starts_at") or "")
    stops_admitting_at = str(activation.get("stops_admitting_at") or "")
    _require(bool(starts_at) and bool(stops_admitting_at), "LIVE_SOURCE_ACTIVATION_MISSING")
    sampling = schedule_doc.get("sampling") if isinstance(schedule_doc.get("sampling"), Mapping) else {}
    sampling_policy = str(sampling.get("policy") or "") or None
    sampling_seed = str(sampling.get("seed") or "") or None
    inclusion_probability = (
        str(sampling.get("inclusion_probability"))
        if sampling.get("inclusion_probability") is not None
        else None
    )

    panel = rebuild_observation_panel_from_rdp(
        data_root=root, schedule_sha256=schedule_sha256
    )
    members: list[dict[str, Any]] = []
    for row in panel.get("members") or []:
        if not isinstance(row, Mapping):
            continue
        normalized = _normalize_member_row(
            row,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            sampling_policy=sampling_policy,
            sampling_seed_default=sampling_seed,
            inclusion_probability_default=inclusion_probability,
        )
        if normalized is not None:
            members.append(normalized)
    observations: list[dict[str, Any]] = []
    for row in panel.get("observations") or []:
        if not isinstance(row, Mapping):
            continue
        observations.extend(
            _explode_observation_rows(
                row, schedule_sha256=schedule_sha256, activation_id=activation_id
            )
        )
    members.sort(key=lambda item: (str(item.get("mint")), str(item.get(COHORT_ADMISSION_FIELD))))
    observations.sort(
        key=lambda item: (
            str(item.get("mint")),
            str(item.get("point_id")),
            str(item.get("primitive_id")),
            str(item.get("field_id")),
            str(item.get("call_occurrence_id") or ""),
        )
    )
    resolved_coverage = discovery_coverage_class or lineage_coverage or "GAP_SUSPECTED"
    snapshot = {
        "schedule_sha256": schedule_sha256,
        "activation_id": activation_id,
        "producer_git_sha": producer_git_sha,
        "starts_at": starts_at,
        "stops_admitting_at": stops_admitting_at,
        "discovery_coverage_class": resolved_coverage,
        "open_publication": open_publication,
        "unresolved_due": unresolved_due,
        "in_flight": in_flight,
        "budget_blocked": budget_blocked,
        "members": members,
        "observations": observations,
    }
    path = write_observation_rdp_source(root, snapshot)
    return _validate_source_payload(
        snapshot, source_sha256=sha256_bytes(path.read_bytes())
    )


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
    start, end = _require_campaign_cohort(source, cohort_id)
    members = [
        m
        for m in source["members"]
        if isinstance(m, Mapping)
        and isinstance(m.get(COHORT_ADMISSION_FIELD), str)
        and start <= _parse_utc(str(m[COHORT_ADMISSION_FIELD])) < end
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
        state = str(m.get("denominator_state") or "unknown")
        if state in denom:
            denom[state] += 1
        else:
            denom["unknown"] += 1

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
        "window_end_exclusive": _render_utc(end),
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
            "starts_at": source.get("starts_at"),
            "stops_admitting_at": source.get("stops_admitting_at"),
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
    start, end = _require_campaign_cohort(source, cohort_id)
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
        if not (start <= adm_dt < end):
            continue
        mint = str(member.get("mint") or member.get("entity_id") or "")
        _require(bool(mint), "TOKEN_MINT_MISSING")
        selected = str(member.get("selected_or_excluded") or "UNKNOWN")
        _require(selected in {"SELECTED", "EXCLUDED", "UNKNOWN"}, "SELECTED_STATE_INVALID")
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
        )

    for obs in source["observations"]:
        if not isinstance(obs, Mapping):
            continue
        mint = str(obs.get("mint") or obs.get("entity_id") or "")
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
        if not isinstance(typed_value, str) and typed_value is not None:
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
    if observation_rows:
        obs_table = pa.Table.from_pylist(observation_rows)
    else:
        obs_table = pa.table(
            {
                "release_id": pa.array([], type=pa.string()),
                "cohort_id": pa.array([], type=pa.string()),
                "mint": pa.array([], type=pa.string()),
                "point_id": pa.array([], type=pa.string()),
                "primitive_id": pa.array([], type=pa.string()),
                "field_id": pa.array([], type=pa.string()),
                "value_kind": pa.array([], type=pa.string()),
                "typed_value": pa.array([], type=pa.string()),
                "state": pa.array([], type=pa.string()),
                "missing_reason": pa.array([], type=pa.string()),
                "event_time": pa.array([], type=pa.string()),
                "request_started_at": pa.array([], type=pa.string()),
                "response_received_at": pa.array([], type=pa.string()),
                "first_reliable_available_at": pa.array([], type=pa.string()),
                "request_sha256": pa.array([], type=pa.string()),
                "response_sha256": pa.array([], type=pa.string()),
                "call_occurrence_id": pa.array([], type=pa.string()),
                "http_status": pa.array([], type=pa.int64()),
                "http_class": pa.array([], type=pa.string()),
                "evidence_role": pa.array([], type=pa.string()),
                "confirmatory_reuse_forbidden": pa.array([], type=pa.bool_()),
            }
        )
    return (
        pa.Table.from_pylist(census_rows),
        obs_table,
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
        "starts_at": source.get("starts_at"),
        "stops_admitting_at": source.get("stops_admitting_at"),
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
        "starts_at": source.get("starts_at"),
        "stops_admitting_at": source.get("stops_admitting_at"),
        "admission_field": COHORT_ADMISSION_FIELD,
        "evidence_role": LIVE_EVIDENCE_ROLE,
        "confirmatory_reuse_forbidden": True,
        "census_sha256": sha256_bytes(census_bytes),
        "observations_sha256": sha256_bytes(obs_bytes),
        "census_row_count": census.num_rows,
        "observation_row_count": observations.num_rows if observations.num_columns else 0,
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
            "census_sha256": sha256_bytes(census_bytes),
            "observations_sha256": sha256_bytes(obs_bytes),
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

    root = Path(data_root)
    _publish_bytes(root / census_rel, census_bytes)
    _publish_bytes(root / obs_rel, obs_bytes)

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
            "census_sha256": sha256_bytes(census_bytes),
            "observations_sha256": sha256_bytes(obs_bytes),
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
    source = load_observation_rdp_source(observation_rdp_root)
    readiness = classify_cohort_readiness(source, cohort_id=cohort_id, as_of=as_of)
    return {
        "schedule_sha256": source["schedule_sha256"],
        "activation_id": source["activation_id"],
        "producer_git_sha": source["producer_git_sha"],
        "starts_at": source.get("starts_at"),
        "stops_admitting_at": source.get("stops_admitting_at"),
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
