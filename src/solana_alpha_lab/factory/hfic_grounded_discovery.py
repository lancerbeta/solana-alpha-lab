"""Ordinary grounded discovery.

The numeric recipe reads production-shaped census and observation rows.
It does not accept pre-labeled ``in_base_x`` or ``synthetic_target`` as the
production entry. Live market Forge is not this module's job. A recorded
look is a ResearchStore artifact, not a scientific-slot reservation.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ORDINARY_GROUNDED_DISCOVERY_V1 = "ORDINARY_GROUNDED_DISCOVERY_V1"
DISCOVERY_CONTRACT_VERSION = "FORGE_GROUNDED_DISCOVERY_V1"
ORDINARY_DISCOVERY_READY = "ORDINARY_DISCOVERY_READY"
LIVE_DATASET_ID = "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"
LIVE_EVIDENCE_ROLE = "EXPLORATORY_REUSE"
PRICE = "FIELD-USD-PRICE-001"
LIQUIDITY = "FIELD-LIQUIDITY-USD-001"
ALLOWED_FIELDS = frozenset({PRICE, LIQUIDITY})
POINT_OFFSET = {
    "X300": 300,
    "Y900": 900,
    "Y1800": 1800,
    "Y3600": 3600,
    "Y7200": 7200,
    "Y14400": 14400,
    "Y43200": 43200,
    "Y86400": 86400,
}
MAX_MAIN_QUERY_SPECS = 6
MAX_ADAPTIVE_REFINEMENTS = 2
MAX_EXPLANATORY = 3
CALCULATION_VERSION = "FORGE_GROUNDED_DISCOVERY_CALC_V1"
PIT_LATENESS_SECONDS = 300
_CONTENT_AXES = (
    "population",
    "decision_timestamp",
    "target",
    "estimand",
    "explanatory_condition",
)
_BLOCKING_RELATIONS = frozenset({"EXACT_SCOPE_MATCH", "EXACT_VALID_CLOSE"})
_REL_RE = re.compile(
    r"^REL-(\d{8}T\d{6}Z)-(\d{8}T\d{6}Z)$"
)


class GroundedDiscoveryError(ValueError):
    def __init__(self, code: str, detail: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.detail = dict(detail or {})
        super().__init__(code)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def query_spec_sha256(spec: Mapping[str, Any]) -> str:
    body = {key: spec[key] for key in sorted(spec) if key != "spec_sha256"}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _point_offset(point_id: object) -> int:
    if not isinstance(point_id, str) or point_id not in POINT_OFFSET:
        raise GroundedDiscoveryError("POINT_NOT_IN_ALLOWLIST")
    return POINT_OFFSET[point_id]


def _is_temporal_query(spec: object) -> bool:
    return isinstance(spec, Mapping) and spec.get("schema") == "smial.hfic-temporal-query"


def validate_query_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed before any value read. Cohort id is not an explanatory feature."""

    if _is_temporal_query(spec):
        from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query

        return validate_temporal_query(spec)
    if not isinstance(spec, Mapping):
        raise GroundedDiscoveryError("QUERY_SPEC_INVALID")
    decision_points = spec.get("decision_points")
    decision_fields = spec.get("decision_fields")
    explanatory = spec.get("explanatory") or []
    if not isinstance(decision_points, list) or not decision_points:
        raise GroundedDiscoveryError("DECISION_POINTS_REQUIRED")
    if not isinstance(decision_fields, list) or not decision_fields:
        raise GroundedDiscoveryError("DECISION_FIELDS_REQUIRED")
    if len(decision_points) + len(decision_fields) > 6:
        raise GroundedDiscoveryError("QUERY_TOO_WIDE")
    if not isinstance(explanatory, list) or len(explanatory) > MAX_EXPLANATORY:
        raise GroundedDiscoveryError("EXPLANATORY_LIMIT")
    if any(str(item) == "cohort_id" for item in explanatory):
        raise GroundedDiscoveryError("COHORT_NOT_A_FEATURE")
    for point in decision_points:
        _point_offset(point)
    for field in decision_fields:
        if field not in ALLOWED_FIELDS:
            raise GroundedDiscoveryError("FIELD_NOT_IN_ALLOWLIST")
    target_point = spec.get("target_point")
    target_field = spec.get("target_field")
    target_offset = _point_offset(target_point)
    if target_field not in ALLOWED_FIELDS:
        raise GroundedDiscoveryError("FIELD_NOT_IN_ALLOWLIST")
    if target_offset <= max(_point_offset(point) for point in decision_points):
        raise GroundedDiscoveryError("TARGET_NOT_AFTER_DECISION")
    query_id = spec.get("query_id")
    if not isinstance(query_id, str) or not query_id.strip():
        raise GroundedDiscoveryError("QUERY_ID_REQUIRED")
    population = spec.get("population")
    if population != "BASE_X":
        raise GroundedDiscoveryError("POPULATION_NOT_BASE_X")
    return {
        "query_id": query_id,
        "decision_points": list(decision_points),
        "decision_fields": list(decision_fields),
        "target_point": target_point,
        "target_field": target_field,
        "explanatory": [str(item) for item in explanatory],
        "population": "BASE_X",
        "spec_sha256": query_spec_sha256(spec),
    }


EPISODE_DATASET_ID = "DATASET-OPPORTUNITY-EPISODES-DISCOVERY-CORPUS-001"
EPISODE_POPULATION = "OPPORTUNITY_EPISODES"


def _admit_episode_binding(cohorts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """OPPORTUNITY_EPISODES metadata gate; never a BASE_X disguise."""

    admitted = []
    for item in cohorts:
        if (
            item.get("evidence_role") != LIVE_EVIDENCE_ROLE
            or item.get("dataset_id") != EPISODE_DATASET_ID
            or item.get("population") != EPISODE_POPULATION
        ):
            raise GroundedDiscoveryError("DISCOVERY_ROLE_AMBIGUOUS")
        for key in ("cohort_id", "release_id", "census_sha256", "observations_sha256"):
            value = item.get(key)
            if not isinstance(value, str) or not value:
                raise GroundedDiscoveryError("DISCOVERY_BINDING_INCOMPLETE")
        if not isinstance(item.get("schedule_binding"), Mapping):
            raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND")
        if item.get("holdout") is not False:
            raise GroundedDiscoveryError("HOLDOUT_UNRESOLVED")
        admitted.append(
            {
                "cohort_id": item["cohort_id"],
                "release_id": item["release_id"],
                "census_sha256": item["census_sha256"],
                "observations_sha256": item["observations_sha256"],
                "evidence_role": LIVE_EVIDENCE_ROLE,
            }
        )
    return {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "population": EPISODE_POPULATION,
        "not_all_census_rows": False,
        "allowed_fields": sorted(ALLOWED_FIELDS | {"FIELD-HOLDER-COUNT-001"}),
        "cohorts": admitted,
        "holdouts_not_touched": ["UNTOUCHED_FORWARD_HOLDOUT"],
    }


def resolve_published_episode_binding(data_root: Path) -> dict[str, Any]:
    """Episode corpus binding from metadata only; protection precedes values.

    Each run re-reads the frozen release protection sources and every current
    registered assignment in this data root. DENY is ``HOLDOUT_PROTECTED``;
    an unproven scope is ``HOLDOUT_UNRESOLVED``. No value column is read.
    """

    import pyarrow.parquet as pq

    from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming
    from solana_alpha_lab.factory.opportunity_episode_release import (
        REQUIRED_EPISODE_LABELS,
        EpisodeReleaseError,
        frozen_protection_from_release,
        load_episode_lineage,
    )
    from solana_alpha_lab.factory.opportunity_episodes import (
        ALLOW,
        ASSIGNMENT_DIR,
        DENY_PROTECTED,
        cohort_day_bounds,
        inventory_from_documents,
        protection_decision,
    )

    root = Path(data_root)
    try:
        lineage = load_episode_lineage(root)
    except Exception as exc:
        raise GroundedDiscoveryError("DISCOVERY_IDENTITY_MISMATCH") from exc
    manifest_id = lineage.get("current_dataset_manifest_id")
    if not isinstance(manifest_id, str) or not manifest_id:
        raise GroundedDiscoveryError("DISCOVERY_ARTIFACT_MISSING")
    labels_path = root / "datasets" / "manifests" / f"{manifest_id}.labels.json"
    if not labels_path.is_file() or labels_path.is_symlink():
        raise GroundedDiscoveryError("DISCOVERY_ARTIFACT_MISSING")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(labels, Mapping) or any(
        labels.get(key) != value for key, value in REQUIRED_EPISODE_LABELS.items()
    ):
        raise GroundedDiscoveryError("DISCOVERY_AUTHORITY_ABSENT")
    # Only the lineage-current version binds; a torn import never reads values.
    if labels.get("is_current_corpus_version") is not True or labels.get("corpus_version") != lineage.get(
        "current_corpus_version"
    ):
        raise GroundedDiscoveryError("DISCOVERY_IDENTITY_MISMATCH")
    raw_cohorts = [item for item in lineage.get("cohorts") or [] if isinstance(item, Mapping)]
    if not raw_cohorts:
        raise GroundedDiscoveryError("DISCOVERY_BINDING_EMPTY")
    if {str(item.get("cohort_id")) for item in raw_cohorts} != {
        str(item) for item in labels.get("cohort_lineage") or []
    }:
        raise GroundedDiscoveryError("DISCOVERY_SCOPE_UNSUPPORTED")
    current_documents = []
    assignment_dir = root / ASSIGNMENT_DIR
    if assignment_dir.is_dir():
        for path in sorted(assignment_dir.glob("*.json")):
            if path.is_symlink():
                raise GroundedDiscoveryError("HOLDOUT_UNRESOLVED")
            current_documents.append(json.loads(path.read_text(encoding="utf-8")))
    bound: list[dict[str, Any]] = []
    for item in sorted(raw_cohorts, key=lambda row: int(row.get("corpus_version") or 0)):
        census_rel = str(item.get("census_rel") or "")
        obs_rel = str(item.get("obs_rel") or "")
        for rel, expected in ((census_rel, item.get("census_sha256")), (obs_rel, item.get("observations_sha256"))):
            path = root / rel
            if not rel or path.is_symlink() or not path.is_file():
                raise GroundedDiscoveryError("DISCOVERY_ARTIFACT_MISSING")
            if sha256_file_streaming(path) != expected:
                raise GroundedDiscoveryError("BINDING_HASH_MISMATCH")
        release_dir = root / str(item.get("release_dir_rel") or "")
        try:
            # Exactly the pinned admission-time assignments; nothing else binds.
            frozen_documents = frozen_protection_from_release(
                release_dir, expected_schedule_sha256=str(item.get("schedule_sha256") or "")
            )
        except (EpisodeReleaseError, OSError, ValueError):
            raise GroundedDiscoveryError("HOLDOUT_UNRESOLVED") from None
        inventory = inventory_from_documents([*frozen_documents, *current_documents])
        start, end = cohort_day_bounds(str(item["cohort_id"]))
        mints = pq.read_table(root / census_rel, columns=["mint"]).column("mint").to_pylist()
        for mint in mints:
            decision, _reason = protection_decision(
                inventory,
                str(mint),
                interval_start=start - timedelta(days=1),
                interval_end=end + timedelta(days=4),
            )
            if decision == DENY_PROTECTED:
                raise GroundedDiscoveryError("HOLDOUT_PROTECTED")
            if decision != ALLOW:
                raise GroundedDiscoveryError("HOLDOUT_UNRESOLVED")
        bound.append(
            {
                "dataset_id": EPISODE_DATASET_ID,
                "dataset_manifest_id": manifest_id,
                "dataset_version": str(labels.get("dataset_version") or ""),
                "evidence_role": LIVE_EVIDENCE_ROLE,
                "holdout": False,
                "population": EPISODE_POPULATION,
                "cohort_id": item["cohort_id"],
                "release_id": item["release_id"],
                "census_sha256": item["census_sha256"],
                "observations_sha256": item["observations_sha256"],
                "census_rel": census_rel,
                "observations_rel": obs_rel,
                "schedule_sha256": item.get("schedule_sha256"),
                "schedule_binding": dict(item.get("schedule_binding") or {}),
            }
        )
    admitted = admit_discovery_binding(bound)
    return {
        **admitted,
        "authority_source": "PUBLISHED_EPISODE_LABELS_V1",
        "holdout_derived_from_discovery_contract": True,
        "protected_holdout_assignment": False,
        "dataset_manifest_id": manifest_id,
        "dataset_version": str(labels.get("dataset_version") or ""),
        "cohorts": bound,
    }


def admit_discovery_binding(cohorts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Metadata gate. Ambiguous role stops before value read and before a slot."""

    if not cohorts:
        raise GroundedDiscoveryError("DISCOVERY_BINDING_EMPTY")
    episode_flags = {
        item.get("dataset_id") == EPISODE_DATASET_ID for item in cohorts if isinstance(item, Mapping)
    }
    if len(episode_flags) != 1:
        raise GroundedDiscoveryError("DISCOVERY_ROLE_AMBIGUOUS")
    if episode_flags == {True}:
        return _admit_episode_binding(cohorts)
    admitted = []
    for item in cohorts:
        role = item.get("evidence_role")
        dataset_id = item.get("dataset_id")
        if role != LIVE_EVIDENCE_ROLE or dataset_id != LIVE_DATASET_ID:
            raise GroundedDiscoveryError("DISCOVERY_ROLE_AMBIGUOUS")
        for key in ("cohort_id", "release_id", "census_sha256", "observations_sha256"):
            value = item.get(key)
            if not isinstance(value, str) or not value:
                raise GroundedDiscoveryError("DISCOVERY_BINDING_INCOMPLETE")
        if item.get("holdout") is not False:
            raise GroundedDiscoveryError("HOLDOUT_UNRESOLVED")
        admitted.append(
            {
                "cohort_id": item["cohort_id"],
                "release_id": item["release_id"],
                "census_sha256": item["census_sha256"],
                "observations_sha256": item["observations_sha256"],
                "evidence_role": LIVE_EVIDENCE_ROLE,
            }
        )
    return {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "population": "BASE_X",
        "not_all_census_rows": True,
        "allowed_fields": sorted(ALLOWED_FIELDS),
        "cohorts": admitted,
        "holdouts_not_touched": ["UNTOUCHED_FORWARD_HOLDOUT"],
    }


_AUTHORITY_SOURCE = "PUBLISHED_DISCOVERY_LABELS_V1"
_NON_BLOCKING_MEMORY = frozenset({"PARK", "NOT_SELECTED_IN_SESSION"})
_NON_BLOCKING_REASONS = frozenset(
    {
        "NOT_SELECTED_IN_SESSION",
        "NO_WORTHY_HYPOTHESIS",
        "OWNER_PRIORITY_PARK",
    }
)


def _labels_authority_or_raise(labels: Mapping[str, Any]) -> None:
    """Positive discovery contract. A role string alone does not derive holdout."""

    from solana_alpha_lab.factory.live_cohort_discovery_release import REQUIRED_LABELS

    if "evidence_role" not in labels or labels.get("evidence_role") in (None, ""):
        raise GroundedDiscoveryError("DISCOVERY_ROLE_UNKNOWN")
    if labels.get("evidence_role") != REQUIRED_LABELS["evidence_role"]:
        raise GroundedDiscoveryError("DISCOVERY_ROLE_FORBIDDEN")
    if labels.get("outcome_previously_consumed") is True:
        raise GroundedDiscoveryError("DISCOVERY_ROLE_FORBIDDEN")
    for key, expected in REQUIRED_LABELS.items():
        if key not in labels or labels.get(key) != expected:
            raise GroundedDiscoveryError("DISCOVERY_AUTHORITY_ABSENT")


def _explicit_holdout_or_raise(sources: Sequence[Mapping[str, Any]]) -> None:
    for source in sources:
        if "holdout" not in source:
            continue
        value = source.get("holdout")
        if value is True:
            raise GroundedDiscoveryError("HOLDOUT_PROTECTED")
        if value is not False:
            raise GroundedDiscoveryError("HOLDOUT_UNRESOLVED")


def schedule_projection_for_census(data_root: Path, census_path: Path) -> dict[str, Any]:
    """Project point clocks from the verified schedule. Does not write parquet or run a look."""

    import pyarrow as pa
    import pyarrow.parquet as pq

    from solana_alpha_lab.factory.hfic_temporal_discovery import project_schedule_points
    from solana_alpha_lab.factory.scientific_eligibility_projection import (
        CANONICAL_SCHEDULE_UNBOUND,
        CANONICAL_X300_SCHEDULE_INCOMPATIBLE,
        ScientificEligibilityError,
        load_hashed_schedule_document,
        verify_factory_x300_schedule,
    )

    try:
        table = pq.read_table(census_path, columns=["source_schedule_sha256"])
    except (OSError, pa.ArrowException):
        return {"schedule_context_gap": CANONICAL_SCHEDULE_UNBOUND}
    shas = {
        str(value)
        for value in table.column("source_schedule_sha256").to_pylist()
        if isinstance(value, str) and value
    }
    if len(shas) != 1 or len(next(iter(shas))) != 64:
        return {"schedule_context_gap": CANONICAL_SCHEDULE_UNBOUND}
    wanted = next(iter(shas))
    try:
        document = load_hashed_schedule_document(data_root, wanted)
    except ScientificEligibilityError:
        return {"schedule_context_gap": CANONICAL_SCHEDULE_UNBOUND, "schedule_sha256": wanted}
    try:
        verify_factory_x300_schedule(document)
    except ScientificEligibilityError:
        return {
            "schedule_context_gap": CANONICAL_X300_SCHEDULE_INCOMPATIBLE,
            "schedule_sha256": wanted,
            "schedule_hash_matches": True,
        }
    try:
        projected = project_schedule_points(document)
    except GroundedDiscoveryError:
        return {
            "schedule_context_gap": CANONICAL_SCHEDULE_UNBOUND,
            "schedule_sha256": wanted,
            "schedule_hash_matches": True,
        }
    return {
        "schedule_sha256": wanted,
        "schedule_hash_matches": True,
        "schedule_x300_compatible": True,
        **projected,
    }


def _attach_verified_schedule(root: Path, cohorts: list[dict[str, Any]]) -> None:
    for cohort in cohorts:
        census_rel = cohort.get("census_rel")
        if not isinstance(census_rel, str):
            cohort["schedule_context_gap"] = "CANONICAL_SCHEDULE_UNBOUND"
            continue
        projected = schedule_projection_for_census(root, root / census_rel)
        declared = cohort.get("schedule_lateness_seconds")
        point_lateness = projected.get("schedule_point_lateness")
        # Query scalar is the X300 envelope only. Mixed non-X300 point maps
        # are legal and must not trip SCHEDULE_LATENESS_MISMATCH here.
        x300_late = (
            point_lateness.get("X300") if isinstance(point_lateness, Mapping) else None
        )
        if (
            isinstance(declared, int)
            and not isinstance(declared, bool)
            and isinstance(x300_late, int)
            and not isinstance(x300_late, bool)
            and x300_late != declared
        ):
            projected["schedule_context_gap"] = "SCHEDULE_LATENESS_MISMATCH"
        cohort.update(projected)


_publication_cache: contextvars.ContextVar[dict[str, dict[str, Any]] | None] = contextvars.ContextVar(
    "published_binding_cache",
    default=None,
)
_logical_verify_counts: contextvars.ContextVar[dict[str, int] | None] = contextvars.ContextVar(
    "logical_verify_counts",
    default=None,
)


@contextmanager
def publication_verification_scope():
    """One public command verifies each published partition once, then reuses it."""

    cache_token = _publication_cache.set({})
    count_token = _logical_verify_counts.set({})
    try:
        yield
    finally:
        _publication_cache.reset(cache_token)
        _logical_verify_counts.reset(count_token)


def logical_verify_counts() -> dict[str, int]:
    counts = _logical_verify_counts.get()
    return dict(counts) if isinstance(counts, dict) else {}


def resolve_published_discovery_binding(data_root: Path) -> dict[str, Any]:
    """Published admission binding. Inside a command scope the logical scan runs once."""

    root = Path(data_root)
    cache = _publication_cache.get()
    key = str(root)
    if isinstance(cache, dict) and key in cache:
        return cache[key]
    resolved = _resolve_published_discovery_binding(root)
    if isinstance(cache, dict):
        cache[key] = resolved
    return resolved


def _resolve_published_discovery_binding(data_root: Path) -> dict[str, Any]:
    """Build the admission binding from a canonical publication.

    Does not read parquet values. Hashes are streamed. ``holdout=false`` is
    derived only after REQUIRED_LABELS match and no protected holdout
    assignment is present on those labels or cohort records.
    """

    from solana_alpha_lab.factory.live_cohort_discovery_release import (
        CORPUS_DATASET_ID,
        LIVE_EVIDENCE_ROLE,
        load_live_corpus_lineage,
    )
    from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming

    root = Path(data_root)
    lineage = load_live_corpus_lineage(root)
    if lineage.get("corpus_dataset_id") != CORPUS_DATASET_ID:
        raise GroundedDiscoveryError("DISCOVERY_IDENTITY_MISMATCH")
    manifest_id = lineage.get("current_dataset_manifest_id")
    if not isinstance(manifest_id, str) or not manifest_id:
        raise GroundedDiscoveryError("DISCOVERY_ARTIFACT_MISSING")
    labels_path = root / "datasets" / "manifests" / f"{manifest_id}.labels.json"
    if not labels_path.is_file() or labels_path.is_symlink():
        raise GroundedDiscoveryError("DISCOVERY_ARTIFACT_MISSING")
    try:
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GroundedDiscoveryError("DISCOVERY_ARTIFACT_MISSING") from exc
    if not isinstance(labels, Mapping):
        raise GroundedDiscoveryError("DISCOVERY_AUTHORITY_ABSENT")
    _labels_authority_or_raise(labels)
    raw_cohorts = [
        item for item in (lineage.get("cohorts") or []) if isinstance(item, Mapping)
    ]
    if not raw_cohorts:
        raise GroundedDiscoveryError("DISCOVERY_BINDING_EMPTY")
    _explicit_holdout_or_raise([labels, *raw_cohorts])
    label_lineage = labels.get("cohort_lineage")
    if not isinstance(label_lineage, list):
        raise GroundedDiscoveryError("DISCOVERY_SCOPE_UNSUPPORTED")
    label_ids = {str(item) for item in label_lineage}
    bound_cohorts: list[dict[str, Any]] = []
    for item in sorted(raw_cohorts, key=lambda row: int(row.get("corpus_version") or 0)):
        cohort_id = item.get("cohort_id")
        release_id = item.get("release_id")
        census_sha = item.get("census_sha256")
        observations_sha = item.get("observations_sha256")
        census_rel = item.get("census_rel")
        obs_rel = item.get("obs_rel")
        if not all(
            isinstance(value, str) and value
            for value in (
                cohort_id,
                release_id,
                census_sha,
                observations_sha,
                census_rel,
                obs_rel,
            )
        ):
            raise GroundedDiscoveryError("DISCOVERY_IDENTITY_MISMATCH")
        if str(cohort_id) not in label_ids:
            raise GroundedDiscoveryError("DISCOVERY_SCOPE_UNSUPPORTED")
        cohort_role = item.get("evidence_role")
        if cohort_role not in (None, "") and cohort_role != LIVE_EVIDENCE_ROLE:
            raise GroundedDiscoveryError("DISCOVERY_ROLE_CONFLICT")
        for rel, expected in ((census_rel, census_sha), (obs_rel, observations_sha)):
            path = root / str(rel)
            if path.is_symlink() or not path.is_file():
                raise GroundedDiscoveryError("DISCOVERY_ARTIFACT_MISSING")
            if sha256_file_streaming(path) != expected:
                raise GroundedDiscoveryError("BINDING_HASH_MISMATCH")
        bound_cohorts.append(
            {
                "dataset_id": CORPUS_DATASET_ID,
                "dataset_manifest_id": manifest_id,
                "dataset_version": str(item.get("dataset_version") or labels.get("dataset_version") or ""),
                "evidence_role": LIVE_EVIDENCE_ROLE,
                "holdout": False,
                "cohort_id": cohort_id,
                "release_id": release_id,
                "census_sha256": census_sha,
                "observations_sha256": observations_sha,
                "census_rel": census_rel,
                "observations_rel": obs_rel,
                **(
                    {"schedule_lateness_seconds": int(item["allowed_lateness_seconds"])}
                    if isinstance(item.get("allowed_lateness_seconds"), int)
                    and not isinstance(item.get("allowed_lateness_seconds"), bool)
                    else {}
                ),
            }
        )
    _attach_verified_schedule(root, bound_cohorts)
    admitted = admit_discovery_binding(bound_cohorts)
    _assert_published_logical_content(root, bound_cohorts)
    return {
        **admitted,
        "authority_source": _AUTHORITY_SOURCE,
        "holdout_derived_from_discovery_contract": True,
        "protected_holdout_assignment": False,
        "dataset_manifest_id": manifest_id,
        "dataset_version": str(labels.get("dataset_version") or ""),
        "cohorts": bound_cohorts,
    }


def require_published_logical_content(data_root: Any) -> None:
    """Check a published corpus before a look is reserved. No lineage file means nothing to check."""

    if data_root is None:
        return
    root = Path(data_root)
    if not (root / "datasets" / "live_lifecycle_corpus" / "lineage.json").is_file():
        return
    resolve_published_discovery_binding(root)


def _assert_published_logical_content(data_root: Path, cohorts: Sequence[Mapping[str, Any]]) -> None:
    """Reject a partition whose logical content hash no longer matches its bytes."""

    from solana_alpha_lab.factory.live_corpus_logical_rows import (
        KIND_CENSUS,
        KIND_OBS,
        LiveCorpusLogicalRowError,
        measure_live_corpus_parquet,
    )
    from solana_alpha_lab.storage.manifests import PartitionManifest

    partition_dir = data_root / "datasets" / "manifests" / "partitions"
    if not partition_dir.is_dir():
        raise GroundedDiscoveryError("LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE")
    by_location: dict[str, Any] = {}
    for path in partition_dir.glob("partition-*.json"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            part = PartitionManifest.model_validate_json(path.read_bytes())
        except (OSError, UnicodeDecodeError, ValueError):
            raise GroundedDiscoveryError("LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE")
        by_location[str(part.logical_location).replace("\\", "/")] = part
    for cohort in cohorts:
        for rel, kind in (
            (cohort.get("census_rel"), KIND_CENSUS),
            (cohort.get("observations_rel") or cohort.get("obs_rel"), KIND_OBS),
        ):
            if not isinstance(rel, str) or not rel:
                continue
            part = by_location.get(rel.replace("\\", "/"))
            if part is None:
                raise GroundedDiscoveryError("LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE")
            counts = _logical_verify_counts.get()
            if isinstance(counts, dict):
                part_id = str(part.partition_id)
                counts[part_id] = counts.get(part_id, 0) + 1
            try:
                measured = measure_live_corpus_parquet(
                    data_root / rel,
                    kind=kind,
                    partition_id=part.partition_id,
                    logical_location=rel,
                )
            except (LiveCorpusLogicalRowError, OSError, ValueError) as exc:
                raise GroundedDiscoveryError("LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE") from exc
            if measured.content_sha256 != part.content_sha256 or measured.file_sha256 != part.file_sha256:
                raise GroundedDiscoveryError("LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE")


def collapse_exact_partition_duplicates(
    partitions: Sequence[tuple[str, Path, Path]],
) -> tuple[list[tuple[str, Path, Path]], int]:
    """Drop an exact repeated cohort path. A different path for the same cohort fails."""

    seen: dict[str, tuple[str, str]] = {}
    unique: list[tuple[str, Path, Path]] = []
    eliminated = 0
    for cohort_id, census_file, obs_file in partitions:
        key = str(cohort_id)
        signature = (str(Path(census_file)), str(Path(obs_file)))
        previous = seen.get(key)
        if previous is not None:
            if previous == signature:
                eliminated += 1
                continue
            raise GroundedDiscoveryError("DUPLICATE_COHORT_PARTITION")
        seen[key] = signature
        unique.append((key, Path(census_file), Path(obs_file)))
    return unique, eliminated


def load_admitted_partition_rows(
    *,
    data_root: Path | None,
    binding_doc: Mapping[str, Any] | None,
    partitions: Sequence[tuple[str, Path, Path]] | None,
    census_path: Path | None,
    observations_path: Path | None,
    observation_filters: list[tuple[str, str, Any]] | None = None,
    population: str | None = None,
) -> dict[str, Any]:
    """Admit, then hash-check, then load. Authority failures do not call the loader.

    ``population=OPPORTUNITY_EPISODES`` resolves the separate episode corpus;
    the default keeps the legacy LIVE corpus resolution unchanged.
    """

    from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming

    episode_scope = population == EPISODE_POPULATION or (
        isinstance(binding_doc, Mapping)
        and any(
            isinstance(item, Mapping) and item.get("dataset_id") == EPISODE_DATASET_ID
            for item in binding_doc.get("cohorts") or []
        )
    )
    if binding_doc is None:
        if data_root is None:
            raise GroundedDiscoveryError("DISCOVERY_AUTHORITY_ABSENT")
        binding_doc = (
            resolve_published_episode_binding(data_root)
            if episode_scope
            else resolve_published_discovery_binding(data_root)
        )
    if not isinstance(binding_doc, Mapping):
        raise GroundedDiscoveryError("DISCOVERY_INPUT_INVALID")
    cohorts = binding_doc.get("cohorts")
    if not isinstance(cohorts, list):
        raise GroundedDiscoveryError("DISCOVERY_INPUT_INVALID")
    if binding_doc is not None and data_root is not None:
        lineage_path = Path(data_root) / (
            "datasets/opportunity_episodes_corpus/lineage.json"
            if episode_scope
            else "datasets/live_lifecycle_corpus/lineage.json"
        )
        if lineage_path.is_file() and not lineage_path.is_symlink():
            published = (
                resolve_published_episode_binding(data_root)
                if episode_scope
                else resolve_published_discovery_binding(data_root)
            )
            published_pairs = {
                (
                    str(item.get("cohort_id")),
                    str(item.get("census_sha256")),
                    str(item.get("observations_sha256")),
                )
                for item in published["cohorts"]
            }
            verified_cohorts: list[Mapping[str, Any]] = []
            published_by_pair = {
                (
                    str(item.get("cohort_id")),
                    str(item.get("census_sha256")),
                    str(item.get("observations_sha256")),
                ): item
                for item in published["cohorts"]
                if isinstance(item, Mapping)
            }
            for item in cohorts:
                if not isinstance(item, Mapping):
                    raise GroundedDiscoveryError("DISCOVERY_BINDING_INCOMPLETE")
                pair = (
                    str(item.get("cohort_id")),
                    str(item.get("census_sha256")),
                    str(item.get("observations_sha256")),
                )
                match = published_by_pair.get(pair)
                if match is None:
                    raise GroundedDiscoveryError("DISCOVERY_AUTHORITY_ABSENT")
                # Keep the caller cohort set. Do not silently widen a verified
                # subset back to the full published corpus.
                verified_cohorts.append(match)
            cohorts = list(verified_cohorts)
            binding_doc = {**dict(binding_doc), "cohorts": cohorts}
    admit_discovery_binding(cohorts)
    by_cohort = {str(item.get("cohort_id")): item for item in cohorts if isinstance(item, Mapping)}
    supplied = list(partitions or [])
    if not supplied and data_root is not None:
        for item in cohorts:
            if not isinstance(item, Mapping):
                continue
            census_rel = item.get("census_rel")
            obs_rel = item.get("observations_rel") or item.get("obs_rel")
            if isinstance(census_rel, str) and isinstance(obs_rel, str):
                supplied.append(
                    (
                        str(item.get("cohort_id")),
                        Path(data_root) / census_rel,
                        Path(data_root) / obs_rel,
                    )
                )
    unique, eliminated = collapse_exact_partition_duplicates(supplied)
    census: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    if unique:
        for cohort_id, census_file, obs_file in unique:
            binding_row = by_cohort.get(cohort_id)
            if binding_row is None:
                raise GroundedDiscoveryError("BINDING_COHORT_MISMATCH")
            census_sha = sha256_file_streaming(Path(census_file))
            observations_sha = sha256_file_streaming(Path(obs_file))
            if (
                binding_row.get("census_sha256") != census_sha
                or binding_row.get("observations_sha256") != observations_sha
            ):
                raise GroundedDiscoveryError("BINDING_HASH_MISMATCH")
        for cohort_id, census_file, obs_file in unique:
            binding_row = by_cohort[cohort_id]
            for row in load_parquet_rows(census_file):
                stamped = dict(row)
                stamped["cohort_id"] = cohort_id
                stamped["release_id"] = binding_row.get("release_id")
                census.append(stamped)
            for row in (load_parquet_rows(obs_file, filters=observation_filters) if observation_filters is not None else load_parquet_rows(obs_file)):
                stamped = dict(row)
                stamped["cohort_id"] = cohort_id
                stamped["release_id"] = binding_row.get("release_id")
                observations.append(stamped)
    else:
        if census_path is None or observations_path is None:
            raise GroundedDiscoveryError("BINDING_PARTITION_REQUIRED")
        distinct = {
            (item.get("census_sha256"), item.get("observations_sha256"))
            for item in cohorts
            if isinstance(item, Mapping)
        }
        if len(distinct) != 1:
            raise GroundedDiscoveryError("BINDING_PARTITION_REQUIRED")
        census_sha = sha256_file_streaming(census_path)
        observations_sha = sha256_file_streaming(observations_path)
        if distinct != {(census_sha, observations_sha)}:
            raise GroundedDiscoveryError("BINDING_HASH_MISMATCH")
        census = load_parquet_rows(census_path)
        observations = (load_parquet_rows(observations_path, filters=observation_filters) if observation_filters is not None else load_parquet_rows(observations_path))
    return {
        "binding": dict(binding_doc),
        "cohorts": cohorts,
        "census": census,
        "observations": observations,
        "duplicate_partitions_eliminated": eliminated,
        "values_loaded": True,
    }


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _flag_token(flags: Mapping[str, Any], name: str) -> str:
    if name not in flags or flags.get(name) is None:
        return "MISSING"
    value = flags.get(name)
    if value is True:
        return "True"
    if value is False:
        return "False"
    raise GroundedDiscoveryError("EXPLANATORY_INVALID")


def summarize_discovery_query(
    members: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    *,
    overlap_members: Sequence[str] | None = None,
    required_cohorts: Sequence[str] | None = None,
    overlapping_cohorts: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Pooled, cohort, and calendar summaries. Never emits an alpha claim.

    Every requested cohort stays in the table, including a zero usable count.
    A missing explanatory flag stays ``MISSING`` and is not coerced to false.
    """

    bound = validate_query_spec(spec)
    overlap_known = overlap_members is not None
    overlap = set(overlap_members or [])
    blocked = set(overlapping_cohorts or [])
    missing = {"absent": 0, "censored_late": 0, "missing_typed": 0, "other": 0, "leaked": 0}
    exclusions: dict[str, int] = defaultdict(int)
    by_cohort: dict[str, list[float]] = defaultdict(list)
    by_block: dict[str, list[float]] = defaultdict(list)
    by_flag: dict[str, list[float]] = defaultdict(list)
    cohort_denoms: dict[str, int] = defaultdict(int)
    block_denoms: dict[str, int] = defaultdict(int)
    flag_denoms: dict[str, int] = defaultdict(int)
    cohort_admissible: dict[str, int] = defaultdict(int)
    block_admissible: dict[str, int] = defaultdict(int)
    flag_admissible: dict[str, int] = defaultdict(int)
    cohort_overlap: dict[str, int] = defaultdict(int)
    block_overlap: dict[str, int] = defaultdict(int)
    for cohort in required_cohorts or []:
        cohort_denoms.setdefault(str(cohort), 0)
    base_n = 0
    admissible_n = 0
    pooled_values: list[float] = []
    for member in members:
        if member.get("in_base_x") is not True:
            reason = str(member.get("exclusion_reason") or "NOT_BASE_X")
            exclusions[reason] += 1
            continue
        base_n += 1
        cohort = str(member.get("cohort_id") or "UNKNOWN")
        block = str(member.get("calendar_block") or "UNBLOCKED")
        cohort_denoms[cohort] += 1
        block_denoms[block] += 1
        if str(member.get("member_id") or "") in overlap:
            cohort_overlap[cohort] += 1
            block_overlap[block] += 1
        flags = member.get("explanatory") or {}
        if not isinstance(flags, Mapping):
            raise GroundedDiscoveryError("EXPLANATORY_INVALID")
        flag_key = ",".join(
            f"{name}={_flag_token(flags, name)}" for name in bound["explanatory"]
        ) or "NONE"
        flag_denoms[flag_key] += 1
        if member.get("decision_ready") is not True:
            exclusions["DECISION_NOT_READY"] += 1
            continue
        admissible_n += 1
        cohort_admissible[cohort] += 1
        block_admissible[block] += 1
        flag_admissible[flag_key] += 1
        decision_at = _parse_time(member.get("decision_at"))
        target_at = _parse_time(member.get("target_at"))
        state = str(member.get("target_state") or "ABSENT")
        if decision_at is None:
            missing["other"] += 1
            exclusions["DECISION_TIME_MISSING"] += 1
            continue
        if target_at is not None and target_at <= decision_at:
            missing["leaked"] += 1
            exclusions["LEAKED"] += 1
            continue
        if state == "ABSENT":
            missing["absent"] += 1
            exclusions["ABSENT"] += 1
            continue
        if state == "CENSORED_LATE":
            missing["censored_late"] += 1
            exclusions["CENSORED_LATE"] += 1
            continue
        if state == "MISSING_TYPED":
            missing["missing_typed"] += 1
            exclusions["MISSING_TYPED"] += 1
            continue
        if state != "OBSERVED" or target_at is None:
            missing["other"] += 1
            exclusions["TARGET_NOT_OBSERVED"] += 1
            continue
        raw = member.get("target_value", member.get("synthetic_target"))
        if raw is None:
            missing["missing_typed"] += 1
            exclusions["MISSING_TYPED"] += 1
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise GroundedDiscoveryError("TARGET_VALUE_INVALID") from exc
        pooled_values.append(value)
        by_cohort[cohort].append(value)
        by_block[block].append(value)
        by_flag[flag_key].append(value)

    def _view(
        name: str,
        values: Sequence[float],
        denominator: int,
        *,
        independent: bool,
        admissible: int | None = None,
    ) -> dict[str, Any]:
        mean = _mean(list(values))
        return {
            "view": name,
            "denominator_base_x": denominator,
            "feature_admissible": denominator if admissible is None else admissible,
            "target_observed_after_decision": len(values),
            "mean_target": mean,
            "mean_synthetic_target": mean,
            "independent_replication": independent,
        }

    overlap_n = sum(
        1
        for item in members
        if item.get("in_base_x") is True and str(item.get("member_id") or "") in overlap
    )
    calendar_overlap = bool(blocked)
    return {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "query_id": bound["query_id"],
        "spec_sha256": bound["spec_sha256"],
        "population": "BASE_X",
        "base_x_n": base_n,
        "feature_admissible_n": admissible_n,
        "later_target_observed_n": len(pooled_values),
        "not_per_cell_denominator": True,
        "engine_emits_alpha": False,
        "missing_is_not_zero": True,
        "cohort_id_is_not_a_feature": True,
        "missing": missing,
        "exclusion_reasons": dict(sorted(exclusions.items())),
        "pooled": _view(
            "pooled",
            pooled_values,
            base_n,
            independent=overlap_known and overlap_n == 0 and not calendar_overlap,
            admissible=admissible_n,
        ),
        "by_cohort": [
            _view(
                key,
                by_cohort.get(key, []),
                cohort_denoms[key],
                independent=(
                    overlap_known
                    and cohort_overlap[key] == 0
                    and key not in blocked
                    and not calendar_overlap
                ),
                admissible=cohort_admissible[key],
            )
            for key in sorted(cohort_denoms)
        ],
        "by_calendar_block": [
            _view(
                key,
                by_block.get(key, []),
                block_denoms[key],
                independent=overlap_known and block_overlap[key] == 0 and not calendar_overlap,
                admissible=block_admissible[key],
            )
            for key in sorted(block_denoms)
        ],
        "by_explanatory": [
            _view(
                key,
                by_flag.get(key, []),
                flag_denoms[key],
                independent=False,
                admissible=flag_admissible[key],
            )
            for key in sorted(flag_denoms)
        ],
        "overlap_exposed_base_x": overlap_n,
        "overlap_is_not_independent_replication": overlap_n > 0 or calendar_overlap,
        "calendar_overlap_is_not_independent_replication": calendar_overlap,
    }


def classify_query_look(
    previous: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    """Cost budget. Same bytes are a retry. A changed question is a new variant."""

    if _is_temporal_query(spec):
        from solana_alpha_lab.factory.hfic_temporal_discovery import classify_temporal_look

        return classify_temporal_look(previous, spec)
    bound = validate_query_spec(spec)
    digest = bound["spec_sha256"]
    mains = [
        item
        for item in previous
        if item.get("look_class") == "MAIN" and item.get("new_look") is True
    ]
    adaptive = [
        item
        for item in previous
        if item.get("look_class") == "ADAPTIVE" and item.get("new_look") is True
    ]
    if any(item.get("spec_sha256") == digest for item in previous):
        return {
            "spec_sha256": digest,
            "new_look": False,
            "look_class": "RETRY_SAME_BYTES",
            "main_count": len(mains),
            "adaptive_count": len(adaptive),
        }
    same_family = [
        item for item in previous if item.get("query_id") == bound["query_id"] and item.get("new_look") is True
    ]
    look_class = "ADAPTIVE" if same_family else "MAIN"
    if look_class == "MAIN" and len(mains) >= MAX_MAIN_QUERY_SPECS:
        raise GroundedDiscoveryError("QUERY_MAIN_BUDGET_EXHAUSTED")
    if look_class == "ADAPTIVE" and len(adaptive) >= MAX_ADAPTIVE_REFINEMENTS:
        raise GroundedDiscoveryError("QUERY_ADAPTIVE_BUDGET_EXHAUSTED")
    return {
        "query_id": bound["query_id"],
        "spec_sha256": digest,
        "new_look": True,
        "look_class": look_class,
        "main_count": len(mains) + int(look_class == "MAIN"),
        "adaptive_count": len(adaptive) + int(look_class == "ADAPTIVE"),
    }


_MACHINE_LOOK_AXES = (
    "population",
    "decision_timestamp",
)
_SEMANTIC_LOOK_AXES = (
    "target",
    "estimand",
    "explanatory_condition",
    "representation_scope",
    # A different list scope is a different question: priors and cards relate by it.
    "research_scope_rule_sha256",
)
_LOOK_CLAIM_AXES = _MACHINE_LOOK_AXES + _SEMANTIC_LOOK_AXES


def _axis_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def relate_look_scope(
    look_scope: Mapping[str, Any] | None,
    card_scope: Mapping[str, Any] | None,
) -> str:
    """How a candidate's claim axes sit on the scope bound to a computed look.

    LOOK_SCOPE_MATCH: every stored machine and semantic axis is on the card and equal.
    LOOK_SCOPE_NARROWER: a semantic axis differs, or either side names an axis the other lacks.
    LOOK_SCOPE_CONTRADICTION: both sides name population or decision_timestamp differently.
    LOOK_SCOPE_UNBOUND: the look has no stored claim scope.
    """

    look = look_scope if isinstance(look_scope, Mapping) else {}
    card = card_scope if isinstance(card_scope, Mapping) else {}
    if not any(_axis_text(look.get(key)) for key in _LOOK_CLAIM_AXES):
        return "LOOK_SCOPE_UNBOUND"
    machine_shared = False
    semantic_shared = False
    semantic_context = False
    for key in _MACHINE_LOOK_AXES:
        look_value = _axis_text(look.get(key))
        card_value = _axis_text(card.get(key))
        if look_value and card_value and look_value != card_value:
            return "LOOK_SCOPE_CONTRADICTION"
        if look_value and card_value:
            machine_shared = True
        elif look_value or card_value:
            semantic_context = True
    for key in _SEMANTIC_LOOK_AXES:
        look_value = _axis_text(look.get(key))
        card_value = _axis_text(card.get(key))
        if look_value and card_value and look_value != card_value:
            semantic_context = True
        elif look_value and card_value:
            semantic_shared = True
        elif look_value or card_value:
            semantic_context = True
    if semantic_context or not machine_shared:
        if machine_shared or semantic_shared or semantic_context:
            return "LOOK_SCOPE_NARROWER"
        return "LOOK_SCOPE_UNBOUND"
    if semantic_shared or machine_shared:
        return "LOOK_SCOPE_MATCH"
    return "LOOK_SCOPE_UNBOUND"


def stored_look_scope(store: Any, evidence: Mapping[str, Any]) -> dict[str, Any] | None:
    """Scope bound to the durable look, not a later label on the evidence object."""

    refs = evidence.get("result_refs")
    journal = str(evidence.get("journal_scope") or "")
    if not isinstance(refs, list) or not refs or not journal:
        return None
    looks = {str(item.get("record_id") or ""): item for item in list_discovery_looks(store, journal)}
    last = looks.get(str(refs[-1]))
    if not isinstance(last, Mapping):
        return None
    scope = last.get("candidate_scope")
    if not isinstance(scope, Mapping):
        return None
    return {key: value for key, value in scope.items() if _axis_text(value)}


def _last_decision_point(points: Sequence[str]) -> str:
    """The decision moment the numeric recipe actually uses.

    Features may be read at earlier points. The decision deadline is the
    latest point in the spec, so an earlier label is a different question.
    """

    return max((str(point) for point in points), key=_scope_point_offset)


def _scope_point_offset(point_id: object) -> int:
    """Ordering for candidate scope labels only; the evaluators keep their own allowlists."""

    if isinstance(point_id, str) and point_id.startswith("E"):
        from solana_alpha_lab.factory.opportunity_episodes import OpportunityEpisodeError, point_offset

        try:
            return point_offset(point_id)
        except OpportunityEpisodeError as exc:
            raise GroundedDiscoveryError("POINT_NOT_IN_ALLOWLIST") from exc
    return _point_offset(point_id)


def measured_target_label(spec: Mapping[str, Any]) -> str:
    """Target identity the spec computed: ``target_point:target_field``."""

    validated = validate_query_spec(spec)
    if validated.get("target_label"):
        return str(validated["target_label"])
    return f"{validated['target_point']}:{validated['target_field']}"


def scope_bound_to_spec(
    spec: Mapping[str, Any],
    candidate_scope: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Confirming look fields come from the spec, not from a free label.

    Population is the spec population. The decision moment is the latest
    decision point the recipe uses. The confirming target is
    ``target_point:target_field``. A declared earlier decision point, or a
    target string that does not name that pair, is not stored as confirmation.
    """

    validated = validate_query_spec(spec)
    declared = candidate_scope if isinstance(candidate_scope, Mapping) else {}
    spec_population = _axis_text(validated.get("population"))
    declared_population = _axis_text(declared.get("population"))
    if declared_population and declared_population != spec_population:
        raise GroundedDiscoveryError("LOOK_SPEC_SCOPE_MISMATCH")
    points = [str(item) for item in validated["decision_points"]]
    last_decision = _last_decision_point(points)
    declared_decision = _axis_text(declared.get("decision_timestamp"))
    if declared_decision and declared_decision != last_decision:
        raise GroundedDiscoveryError("LOOK_SPEC_SCOPE_MISMATCH")
    bound = {
        key: value
        for key, value in declared.items()
        if _axis_text(value) and key not in {"target", "population", "decision_timestamp"}
    }
    scientific_body = validated.get("scientific_body")
    if isinstance(scientific_body, Mapping) and "research_scope" in scientific_body:
        from solana_alpha_lab.factory.hfic_research_scope import rule_sha256_of_body

        bound["research_scope_rule_sha256"] = rule_sha256_of_body(scientific_body)
    bound["population"] = spec_population
    bound["decision_timestamp"] = last_decision
    bound["target"] = (
        str(validated["target_label"])
        if validated.get("target_label")
        else measured_target_label(validated)
    )
    return bound


def card_claim_scope(card: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(card, Mapping):
        return {}
    kept: dict[str, str] = {}
    for key in _LOOK_CLAIM_AXES:
        value = _axis_text(card.get(key))
        if value:
            kept[key] = value
    return kept


def validate_fresh_card_scope(
    card: Mapping[str, Any],
    *,
    look_scope: Mapping[str, Any] | None = None,
    require_look_axes: bool = False,
) -> dict[str, str]:
    """Check declared fresh transport, never infer intent or repair saved bytes."""

    nested = card.get("candidate_scope")
    declared_keys = _LOOK_CLAIM_AXES + ("research_scope_statement", "evidence_surface_mode")
    if "candidate_scope" in card:
        if not isinstance(nested, Mapping):
            raise GroundedDiscoveryError("CANDIDATE_SCOPE_INVALID", {
                "invalid_fields": ["candidate_scope"], "expected_type": "object",
                "next_action": "CORRECT_DECLARED_FIELD_TYPES_REUSE_SAVED_LOOK",
            })
        invalid = ["candidate_scope." + key for key in declared_keys
                   if key in nested and not _axis_text(nested[key])]
        if invalid:
            raise GroundedDiscoveryError("CANDIDATE_SCOPE_INVALID", {
                "invalid_fields": invalid, "expected_type": "non_empty_string",
                "next_action": "CORRECT_DECLARED_FIELD_TYPES_REUSE_SAVED_LOOK",
            })
        conflicts = [
            key for key in declared_keys
            if key in nested and key in card and _axis_text(nested[key]) != _axis_text(card[key])
        ]
        if conflicts:
            raise GroundedDiscoveryError("CANDIDATE_SCOPE_FIELDS_CONFLICT", {
                "conflicting_fields": conflicts,
                "next_action": "RESOLVE_DECLARED_SCOPE_CONFLICT_REUSE_SAVED_LOOK",
            })
    invalid = [key for key in declared_keys if key in card and not _axis_text(card[key])]
    if invalid:
        raise GroundedDiscoveryError("CANDIDATE_SCOPE_INVALID", {
            "invalid_fields": invalid, "expected_type": "non_empty_string",
            "next_action": "CORRECT_DECLARED_FIELD_TYPES_REUSE_SAVED_LOOK",
        })
    required = list(_CONTENT_AXES) if require_look_axes or bool(nested) else []
    look = look_scope if isinstance(look_scope, Mapping) else {}
    for key in ("representation_scope", "research_scope_rule_sha256"):
        if (require_look_axes and _axis_text(look.get(key))) or (isinstance(nested, Mapping) and key in nested):
            required.append(key)
    if "research_scope_rule_sha256" in required or card.get("research_scope_rule_sha256") is not None:
        required.append("research_scope_statement")
    missing = [key for key in required if not _axis_text(card.get(key))]
    if missing:
        raise GroundedDiscoveryError("CANDIDATE_SCOPE_FIELDS_REQUIRED", {
            "missing_top_level": missing,
            "nested_scope_present": "candidate_scope" in card,
            "scientific_result_created": False,
            "next_action": "CORRECT_DECLARED_FIELD_PLACEMENT_REUSE_SAVED_LOOK",
        })
    return card_claim_scope(card)


def _scope_missing(scope: Mapping[str, Any], *, prefix: str) -> list[str]:
    missing = [
        f"{prefix}{key}"
        for key in _CONTENT_AXES
        if scope.get(key) in (None, "")
    ]
    if scope.get("evidence_surface_mode") in (None, ""):
        missing.append(f"{prefix}evidence_surface_mode")
    return missing


def _non_blocking_prior(prior: Mapping[str, Any]) -> bool:
    """PARK, not-selected, scoped no-worthy and technical stops do not ban a family."""

    status = str(prior.get("memory_status") or "")
    reason = str(prior.get("reason_code") or "")
    if status in _NON_BLOCKING_MEMORY:
        return True
    if reason in _NON_BLOCKING_REASONS or reason.startswith("PARK_"):
        return True
    if reason in {
        "OBSERVABILITY_BLOCKED",
        "INPUT_NOT_READY",
        "HOLDOUT_UNRESOLVED",
        "KILL_UNBOUND_EVIDENCE",
    }:
        return True
    if status == "TECHNICAL_STOP":
        return True
    return False


def _valid_close(prior: Mapping[str, Any]) -> bool:
    if _non_blocking_prior(prior):
        return False
    status = str(prior.get("memory_status") or "")
    reason = str(prior.get("reason_code") or "")
    if status == "HARD_CLOSE":
        return True
    return reason.startswith("KILL_") or reason.startswith("CLOSE_")


def _near_close_unresolved(candidate: Mapping[str, Any], prior: Mapping[str, Any]) -> bool:
    """A close with several matching axes and one gap is not a free pass."""

    if not _valid_close(prior):
        return False
    content_present = [
        key for key in _CONTENT_AXES if prior.get(key) not in (None, "")
    ]
    if not content_present:
        return False
    if not all(candidate.get(key) == prior.get(key) for key in content_present):
        return False
    if len(content_present) < len(_CONTENT_AXES):
        return len(content_present) >= 3
    return prior.get("evidence_surface_mode") in (None, "")


def _merge_scope_priors(
    caller: Sequence[Mapping[str, Any]],
    canonical: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Canonical memory stays in the comparison. A caller list cannot erase it."""

    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in list(canonical) + list(caller):
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("hypothesis_version_id") or item.get("question_id") or "")
        if not key:
            key = _canonical(item)
        if key in by_id:
            merged = dict(by_id[key])
            for field, value in item.items():
                if merged.get(field) in (None, "") and value not in (None, ""):
                    merged[field] = value
            by_id[key] = merged
            continue
        by_id[key] = dict(item)
        order.append(key)
    return [by_id[key] for key in order]


def bind_prior_scope_evidence(
    evidence: Mapping[str, Any],
    canonical_priors: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach relations from caller priors plus canonical memory.

    An incomplete candidate scope stops. An incomplete unrelated prior is
    recorded as unresolved and does not ban the forge. A valid same-scope
    close still stops. An empty caller list does not skip canonical memory.
    """

    body = dict(evidence)
    candidate_scope = body.get("candidate_scope")
    caller = body.get("priors") if isinstance(body.get("priors"), list) else []
    merged = _merge_scope_priors(caller, list(canonical_priors or []))
    if not merged:
        return body
    if not isinstance(candidate_scope, Mapping) or _scope_missing(candidate_scope, prefix=""):
        raise GroundedDiscoveryError("UNKNOWN_PRIOR_SCOPE")
    relations = []
    for prior in merged:
        relation = prior_scope_relation(candidate_scope, prior)
        if relation in _BLOCKING_RELATIONS:
            raise GroundedDiscoveryError("EXACT_PRIOR_SCOPE_MATCH")
        if relation == "UNKNOWN_SCOPE_NEEDS_RESOLUTION" and _near_close_unresolved(
            candidate_scope, prior
        ):
            raise GroundedDiscoveryError("UNKNOWN_PRIOR_SCOPE")
        if _non_blocking_prior(prior) and relation == "UNKNOWN_SCOPE_NEEDS_RESOLUTION":
            relation = "NON_BLOCKING_PRIOR"
        relations.append(
            {
                "question_id": prior.get("question_id"),
                "hypothesis_version_id": prior.get("hypothesis_version_id"),
                "relation": relation,
                "question_id_is_not_a_scientific_difference": True,
            }
        )
    body["prior_scope_relations"] = relations
    body["canonical_prior_comparison"] = True
    return body


def prior_scope_relation(
    candidate: Mapping[str, Any],
    prior: Mapping[str, Any],
) -> str:
    """Question id is not a scientific axis.

    A missing required axis is unresolved, not a match and not a free pass.
    A CONTROL representation-bound negative does not close an unseen richer
    ordinary scope. The same content on the same surface still blocks,
    including a rename of ``question_id``.
    """

    missing = _scope_missing(candidate, prefix="") + _scope_missing(prior, prefix="prior.")
    if missing:
        return "UNKNOWN_SCOPE_NEEDS_RESOLUTION"
    content_same = all(candidate.get(key) == prior.get(key) for key in _CONTENT_AXES)
    surface_same = candidate.get("evidence_surface_mode") == prior.get("evidence_surface_mode")
    prior_surface = str(prior.get("evidence_surface_mode") or "")
    candidate_surface = str(candidate.get("evidence_surface_mode") or "")
    candidate_scope = candidate.get("representation_scope")
    prior_scope = prior.get("representation_scope")
    richer_ordinary = (
        prior_surface == "CURRENT_REPRESENTATION_CONTROL_V1"
        and candidate_surface == ORDINARY_GROUNDED_DISCOVERY_V1
        and candidate_scope not in (None, "")
        and candidate_scope != prior_scope
    )
    if content_same and _non_blocking_prior(prior):
        return "NON_BLOCKING_PRIOR"
    if content_same and surface_same:
        if _valid_close(prior):
            return "EXACT_VALID_CLOSE"
        return "EXACT_SCOPE_MATCH"
    if content_same and not richer_ordinary:
        if _valid_close(prior):
            return "EXACT_VALID_CLOSE"
        return "EXACT_SCOPE_MATCH"
    if not content_same:
        return "SCOPE_DISTINCT"
    if richer_ordinary:
        return "SCOPED_CONTROL_DOES_NOT_BLOCK"
    return "SCOPE_DISTINCT"


def _cohort_window(cohort_id: str) -> tuple[datetime, datetime] | None:
    match = _REL_RE.match(cohort_id)
    if match is None:
        return None
    start = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ")
    end = datetime.strptime(match.group(2), "%Y%m%dT%H%M%SZ")
    return start, end


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _deadline(anchor: datetime, offset_seconds: int) -> datetime:
    return anchor + timedelta(seconds=offset_seconds + PIT_LATENESS_SECONDS)


def _grouped_cells(
    observations: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str, str, str], list[Mapping[str, Any]]]:
    grouped: dict[tuple[str, str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in observations:
        cohort = str(row.get("cohort_id") or "")
        release = str(row.get("release_id") or "")
        mint = str(row.get("mint") or "")
        point = str(row.get("point_id") or "")
        field = str(row.get("field_id") or "")
        if not cohort or not release or not mint or not point or not field:
            continue
        grouped[(cohort, release, mint, point, field)].append(row)
    return grouped


def _universe_cell(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {"status": "ABSENT"}
    if str(row.get("state") or "") != "OBSERVED":
        return {"status": "MISSING"}
    try:
        number = float(row.get("typed_value"))
    except (TypeError, ValueError):
        return {"status": "MISSING"}
    if number != number or number in {float("inf"), float("-inf")}:
        return {"status": "MISSING"}
    return {"status": "OBSERVED", "value": number}


def _pit_cell(
    grouped: Mapping[tuple[str, str, str, str, str], Sequence[Mapping[str, Any]]],
    key: tuple[str, str, str, str, str],
    deadline: datetime,
) -> Mapping[str, Any] | None:
    """Latest revision among rows already available at the deadline."""

    chosen: tuple[datetime, Mapping[str, Any]] | None = None
    for row in grouped.get(key, ()):
        available = _parse_time(row.get("first_reliable_available_at"))
        if available is None or available > deadline:
            continue
        if chosen is None or available >= chosen[0]:
            chosen = (available, row)
    return None if chosen is None else chosen[1]


def _window_overlaps(cohorts: Sequence[Mapping[str, Any]]) -> set[str]:
    parsed: list[tuple[str, datetime, datetime]] = []
    for item in cohorts:
        cohort_id = str(item.get("cohort_id") or "")
        start = _parse_time(item.get("window_start"))
        end = _parse_time(item.get("window_end"))
        if start is None or end is None:
            inferred = _cohort_window(cohort_id)
            if inferred is None:
                continue
            start, end = inferred
        parsed.append((cohort_id, start, end))
    blocked: set[str] = set()
    for index, (left_id, left_start, left_end) in enumerate(parsed):
        for right_id, right_start, right_end in parsed[index + 1 :]:
            if max(left_start, right_start) < min(left_end, right_end):
                blocked.add(left_id)
                blocked.add(right_id)
    return blocked


def _explanatory_flags(
    grouped: Mapping[tuple[str, str, str, str, str], Sequence[Mapping[str, Any]]],
    *,
    cohort: str,
    release: str,
    mint: str,
    rules: Sequence[Mapping[str, Any]],
    anchor: datetime,
) -> dict[str, bool | None]:
    flags: dict[str, bool | None] = {}
    for rule in rules:
        name = str(rule.get("name") or "")
        if not name or name == "cohort_id":
            raise GroundedDiscoveryError("COHORT_NOT_A_FEATURE")
        point = str(rule.get("point_id") or "X300")
        field = str(rule.get("field_id") or "")
        if field not in ALLOWED_FIELDS:
            raise GroundedDiscoveryError("FIELD_NOT_IN_ALLOWLIST")
        cell = _pit_cell(
            grouped,
            (cohort, release, mint, point, field),
            _deadline(anchor, _point_offset(point)),
        )
        if cell is None or str(cell.get("state") or "") != "OBSERVED":
            flags[name] = None
            continue
        observed = _as_float(cell.get("typed_value"))
        threshold = rule.get("threshold")
        if observed is None or threshold is None:
            flags[name] = None
            continue
        op = str(rule.get("op") or "gte")
        if op == "gte":
            flags[name] = observed >= float(threshold)
        elif op == "lt":
            flags[name] = observed < float(threshold)
        else:
            raise GroundedDiscoveryError("EXPLANATORY_INVALID")
    return flags


def execute_discovery_from_rows(
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    binding: Sequence[Mapping[str, Any]],
    *,
    universe_policy: Mapping[str, Any] | None = None,
    research_scope: Any = None,
) -> dict[str, Any]:
    """Compute BASE_X, PIT features and a later target from production-shaped rows.

    Role and holdout come from ``binding``. They are not defaulted here.
    Eligibility does not look at the target. Traders are not required.
    """

    if _is_temporal_query(spec):
        from solana_alpha_lab.factory.hfic_temporal_discovery import execute_temporal_discovery

        return execute_temporal_discovery(
            census, observations, spec, binding, universe_policy=universe_policy, research_scope=research_scope
        )
    bound_spec = validate_query_spec(spec)
    for item in binding:
        if "holdout" not in item:
            raise GroundedDiscoveryError("HOLDOUT_UNRESOLVED")
        if "evidence_role" not in item:
            raise GroundedDiscoveryError("DISCOVERY_ROLE_AMBIGUOUS")
    admitted = admit_discovery_binding(binding)
    # The grounded BASE_X evaluator never reads an episode corpus; episode
    # questions run through temporal query 1.1 only.
    if admitted.get("population") == EPISODE_POPULATION:
        raise GroundedDiscoveryError("POPULATION_BINDING_MISMATCH")
    rules = spec.get("explanatory_rules") or []
    if not isinstance(rules, list):
        raise GroundedDiscoveryError("EXPLANATORY_INVALID")
    rule_names = [str(item.get("name")) for item in rules if isinstance(item, Mapping)]
    if rule_names != list(bound_spec["explanatory"]):
        raise GroundedDiscoveryError("EXPLANATORY_INVALID")
    decision_max = max(_point_offset(point) for point in bound_spec["decision_points"])
    for rule in rules:
        if not isinstance(rule, Mapping):
            raise GroundedDiscoveryError("EXPLANATORY_INVALID")
        if _point_offset(rule.get("point_id") or "X300") > decision_max:
            raise GroundedDiscoveryError("EXPLANATORY_AFTER_DECISION")
    grouped = _grouped_cells(observations)
    decision_offset = max(_point_offset(point) for point in bound_spec["decision_points"])
    members: list[dict[str, Any]] = []
    universe_counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    cohort_ids = [str(item["cohort_id"]) for item in admitted["cohorts"]]
    admitted_pairs = {
        (str(item["cohort_id"]), str(item["release_id"])) for item in admitted["cohorts"]
    }
    for row in census:
        mint = str(row.get("mint") or "")
        if not mint:
            continue
        cohort = str(row.get("cohort_id") or "")
        release = str(row.get("release_id") or "")
        anchor = _parse_time(row.get("authoritative_anchor"))
        state = str(row.get("candidate_state") or "")
        block = str(row.get("calendar_block") or "")
        if not block and anchor is not None:
            block = anchor.date().isoformat()
        if not block:
            block = "UNANCHORED"
        exclusion = None
        in_base = False
        if (cohort, release) not in admitted_pairs:
            exclusion = "BINDING_COHORT_MISMATCH"
        elif state != "X_ELIGIBLE" or anchor is None:
            exclusion = "NOT_X_ELIGIBLE" if state != "X_ELIGIBLE" else "ANCHOR_MISSING"
        else:
            liquidity = _pit_cell(
                grouped,
                (cohort, release, mint, "X300", LIQUIDITY),
                _deadline(anchor, 300),
            )
            if not isinstance(liquidity, Mapping) or str(liquidity.get("state") or "") != "OBSERVED":
                exclusion = "PIT_LIQUIDITY_MISSING"
            else:
                in_base = True
        universe_pass = True
        if in_base and universe_policy is not None and anchor is not None:
            from solana_alpha_lab.factory.hfic_research_universe_policy import (
                HOLDER_FIELD_ID,
                classify_universe_cells,
            )

            decision_deadline = _deadline(anchor, decision_offset)
            decision_point = max(
                (str(point) for point in bound_spec["decision_points"]),
                key=_point_offset,
            )
            verdict = classify_universe_cells(
                _universe_cell(
                    _pit_cell(
                        grouped,
                        (cohort, release, mint, decision_point, HOLDER_FIELD_ID),
                        decision_deadline,
                    )
                ),
                _universe_cell(
                    _pit_cell(
                        grouped,
                        (cohort, release, mint, decision_point, LIQUIDITY),
                        decision_deadline,
                    )
                ),
                universe_policy,
            )
            universe_counts[str(verdict["status"])] += 1
            universe_pass = verdict["status"] == "PASS"
        decision_ready = False
        decision_at = None
        flags: dict[str, bool | None] = {}
        if in_base and universe_pass and anchor is not None:
            decision_at = _deadline(anchor, decision_offset).strftime("%Y-%m-%dT%H:%M:%SZ")
            decision_ready = True
            for point in bound_spec["decision_points"]:
                for field in bound_spec["decision_fields"]:
                    cell = _pit_cell(
                        grouped,
                        (cohort, release, mint, str(point), str(field)),
                        _deadline(anchor, _point_offset(point)),
                    )
                    if not isinstance(cell, Mapping) or str(cell.get("state") or "") != "OBSERVED":
                        decision_ready = False
            flags = _explanatory_flags(
                grouped,
                cohort=cohort,
                release=release,
                mint=mint,
                rules=[item for item in rules if isinstance(item, Mapping)],
                anchor=anchor,
            )
        target_state = "ABSENT"
        target_at = None
        target_value = None
        if in_base and universe_pass and anchor is not None:
            deadline = _deadline(anchor, decision_offset)
            due = anchor + timedelta(
                seconds=_point_offset(bound_spec["target_point"]) + PIT_LATENESS_SECONDS
            )
            target_key = (
                cohort,
                release,
                mint,
                str(bound_spec["target_point"]),
                str(bound_spec["target_field"]),
            )
            valid_targets = []
            leaked_row = None
            censored_row = None
            for target_row in grouped.get(target_key, ()):
                target_at_dt = _parse_time(target_row.get("first_reliable_available_at"))
                if target_at_dt is None:
                    continue
                if target_at_dt <= deadline:
                    leaked_row = target_row
                elif target_at_dt <= due:
                    valid_targets.append((target_at_dt, target_row))
                else:
                    censored_row = target_row
            if valid_targets:
                valid_targets.sort(key=lambda item: item[0])
                target_at_dt, target = valid_targets[-1]
                target_state = str(target.get("state") or "ABSENT")
                target_at = target_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                if target_state == "OBSERVED":
                    target_value = _as_float(target.get("typed_value"))
                    if target_value is None:
                        target_state = "MISSING_TYPED"
            elif leaked_row is not None:
                target_state = "LEAKED"
                leaked_at = _parse_time(leaked_row.get("first_reliable_available_at"))
                target_at = leaked_at.strftime("%Y-%m-%dT%H:%M:%SZ") if leaked_at else None
            elif censored_row is not None:
                target_state = "CENSORED_LATE"
                censored_at = _parse_time(censored_row.get("first_reliable_available_at"))
                target_at = censored_at.strftime("%Y-%m-%dT%H:%M:%SZ") if censored_at else None
        members.append(
            {
                "member_id": mint,
                "cohort_id": cohort,
                "calendar_block": block,
                "in_base_x": in_base,
                "decision_ready": decision_ready,
                "decision_at": decision_at,
                "target_state": target_state if in_base else "ABSENT",
                "target_at": target_at,
                "target_value": target_value,
                "explanatory": flags,
                "exclusion_reason": exclusion,
            }
        )
    summary = summarize_discovery_query(
        members,
        spec,
        overlap_members=None,
        required_cohorts=cohort_ids,
        overlapping_cohorts=sorted(_window_overlaps(binding)),
    )
    summary["mint_overlap_known"] = False
    summary["traders_complete_required"] = False
    summary["eligibility_uses_target"] = False
    summary["calculation_version"] = CALCULATION_VERSION
    if universe_policy is not None:
        from solana_alpha_lab.factory.hfic_research_universe_policy import snapshot

        summary["universe_policy"] = {
            **snapshot(universe_policy),
            "n_base": sum(universe_counts.values()),
            "n_pass": universe_counts["PASS"],
            "n_fail": universe_counts["FAIL"],
            "n_unknown": universe_counts["UNKNOWN"],
        }
    from solana_alpha_lab.factory.hfic_research_universe_policy import admitted_with_policy

    return {
        "admitted": admitted_with_policy(admitted, universe_policy),
        "summary": summary,
        "members_projected": len(members),
    }


def result_sha256(summary: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(summary).encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def data_binding_sha256(
    admitted: Mapping[str, Any],
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
) -> str:
    body = {
        "admitted": admitted,
        "calculation_version": CALCULATION_VERSION,
        "census": _jsonable(list(census)),
        "observations": _jsonable(list(observations)),
    }
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def same_rows_under_policy(
    look: Mapping[str, Any],
    *,
    admitted: Mapping[str, Any],
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    policy_sha: str,
    scope_applied_sha256: str | None = None,
) -> bool:
    """True when this look's binding is the current rows stamped with ``policy_sha``.

    A scoped look is bound to rows + applied list masks: the comparison uses the CURRENT
    applied masks, so changed list evidence is never mistaken for a pure policy change, and
    without current masks a scoped look cannot be proven "same rows".
    """

    stamped = dict(admitted)
    stamped["universe_policy_semantic_sha256"] = policy_sha
    expected = data_binding_sha256(stamped, census, observations)
    if isinstance((look.get("result") or {}).get("research_scope"), Mapping):
        if not scope_applied_sha256:
            return False
        expected = scoped_binding_sha256(expected, scope_applied_sha256)
    return look.get("data_binding_sha256") == expected


def _look_identity(
    spec_sha: str,
    binding_sha: str,
    journal_scope: str,
    calculation_version: str = CALCULATION_VERSION,
) -> str:
    return hashlib.sha256(
        _canonical(
            {
                "spec_sha256": spec_sha,
                "data_binding_sha256": binding_sha,
                "calculation_version": calculation_version,
                "journal_scope": journal_scope,
            }
        ).encode("utf-8")
    ).hexdigest()


def list_discovery_looks(store: Any, journal_scope: str) -> list[dict[str, Any]]:
    """Read committed discovery looks. Does not reserve a scientific slot."""

    found: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        try:
            wrapper = json.loads(record.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(wrapper, Mapping):
            continue
        if wrapper.get("artifact_kind") != "DISCOVERY_QUERY_LOOK":
            continue
        try:
            body = json.loads(str(wrapper.get("payload_canonical") or ""))
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(body, dict) and body.get("journal_scope") == journal_scope:
            body["record_id"] = str(getattr(record, "record_id", "") or "")
            found.append(body)
    return found


def assert_computed_grounded_evidence(
    store: Any,
    evidence: Mapping[str, Any],
    *,
    expected_journal_scope: str | None = None,
) -> dict[str, Any]:
    """Freeze gate: evidence refs must match a durable computed artifact."""

    bound = bind_prior_scope_evidence(evidence)
    refs = bound.get("result_refs")
    if not isinstance(refs, list) or not refs:
        raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    summary = bound.get("result")
    if not isinstance(summary, Mapping):
        raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    expected = result_sha256(summary)
    if bound.get("result_sha256") != expected:
        raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
    from solana_alpha_lab.factory.hfic_temporal_discovery import (
        TEMPORAL_CALCULATION_VERSIONS_READABLE,
    )

    if bound.get("calculation_version") not in {
        CALCULATION_VERSION,
        *TEMPORAL_CALCULATION_VERSIONS_READABLE,
    }:
        raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
    journal_scope = str(bound.get("journal_scope") or "")
    if expected_journal_scope and journal_scope != expected_journal_scope:
        raise GroundedDiscoveryError("JOURNAL_SCOPE_MISMATCH")
    journal_looks = list_discovery_looks(store, journal_scope)
    looks = {item.get("record_id"): item for item in journal_looks}
    last = looks.get(str(refs[-1]))
    if not isinstance(last, Mapping):
        raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    if last.get("result_sha256") != expected:
        raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
    if last.get("data_binding_sha256") != bound.get("data_binding_sha256"):
        raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
    for ref in refs:
        if str(ref) not in looks:
            raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    if summary.get("schema") == "smial.hfic-temporal-query":
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            current_look_evidence,
            require_coherent_temporal_result,
        )

        # Matching hashes prove the bytes, not that the views agree.
        require_coherent_temporal_result(summary)
        # Draft transport is not a second owner of the compact statistics.
        # V5 requires its exact projection; legacy drafts may omit that field.
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            TEMPORAL_CALCULATION_VERSION_V5,
        )

        if "descriptive_readout" in bound or summary.get("calculation_version") == TEMPORAL_CALCULATION_VERSION_V5:
            try:
                matches = _canonical(bound.get("descriptive_readout")) == _canonical(descriptive_return_readout(summary))
            except (TypeError, ValueError):
                matches = False
            if not matches:
                raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
        current = current_look_evidence(last, journal_looks)
        if str(current.get("record_id") or "") != str(last.get("record_id") or ""):
            raise GroundedDiscoveryError("GROUNDED_RESULT_SUPERSEDED")
    return bound


def no_worthy_scope_record(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """A no-candidate stop keeps the computed scope. It is not a raw-corpus negative."""

    return {
        "terminal": "NO_WORTHY_HYPOTHESIS",
        "technical_failure": False,
        "raw_corpus_negative": False,
        "not_run": False,
        "journal_scope": evidence.get("journal_scope"),
        "result_refs": list(evidence.get("result_refs") or []),
        "queries": list(evidence.get("queries") or []),
        "budget": evidence.get("budget"),
        "candidate_scope": evidence.get("candidate_scope"),
        "result_sha256": evidence.get("result_sha256"),
        "viewed_queries": list(evidence.get("viewed_queries") or []),
    }


def descriptive_return_readout(result: Mapping[str, Any], *, detail_limit: int = 4) -> dict[str, Any]:
    """Bounded model/owner view; the full immutable result remains at its ref."""

    if result.get("schema") != "smial.hfic-temporal-query":
        return {}
    if not isinstance(result.get("downside"), Mapping):
        return {
            "status": "LEGACY_READOUT_UNAVAILABLE",
            "message": "Хвостовые метрики не были рассчитаны этой версией. Для tail/veto-оценки требуется явное дополнение exact saved result.",
        }

    def view(row: Mapping[str, Any], *, matched: bool = False) -> dict[str, Any]:
        block = dict(row.get("downside") or {})
        return {
            "view": "MATCHED_OBSERVED" if matched else (row.get("view") or row.get("cohort_id")),
            "mean_target": row.get("mean_target"),
            "median_target": row.get("median_target"),
            "eligible_n": block.get("observed_n", 0) + block.get("missing_n", 0),
            "downside": block,
        }

    details = {}
    truncation = {}
    for key in ("ablations", "by_cohort", "by_calendar_block"):
        rows = [row for row in (result.get(key) or []) if isinstance(row, Mapping)]
        details[key] = [view(row) for row in rows[:detail_limit]]
        truncation[key] = {"total": len(rows), "included": min(len(rows), detail_limit), "truncated": len(rows) > detail_limit}
    from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_holder_claim_identity
    identity = temporal_holder_claim_identity(result)
    scope_block = result.get("research_scope")
    return {
        "status": "DESCRIPTIVE_PROXY",
        **({"scientific_identity": identity} if identity else {}),
        # List scope, support and attrition of both sides travel with the readout (bounded by the 8 slices cap).
        **({"research_scope": dict(scope_block)} if isinstance(scope_block, Mapping) else {}),
        "matched": view(result, matched=True),
        "baseline": view(result.get("baseline") or {}),
        "details": details,
        "detail_truncation": truncation,
        "selection_policy": "CANONICAL_ORDER_PREFIX",
        "baseline_may_include_matched": True,
        "assessment": "DESCRIPTIVE_ONLY_NO_AUTOMATIC_VERDICT",
        "missingness": "OBSERVED_DENOMINATOR_ONLY_NO_MAR_ASSUMPTION",
        "tail_support": "DESCRIPTIVE_ESTIMATE_NOT_CONFIDENCE_INTERVAL",
    }


def format_discovery_readout(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Owner readout for one computed query. Does not claim alpha."""

    result = evidence.get("result")
    if not isinstance(result, Mapping):
        raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    payload = {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "engine_emits_alpha": False,
        "result_refs": list(evidence.get("result_refs") or []),
        "calculation_version": evidence.get("calculation_version") or result.get("calculation_version"),
        "look_class": (
            (evidence.get("queries") or [{}])[0].get("look_class")
            if isinstance(evidence.get("queries"), list) and evidence.get("queries")
            else None
        ),
        "new_look": (
            (evidence.get("queries") or [{}])[0].get("new_look")
            if isinstance(evidence.get("queries"), list) and evidence.get("queries")
            else None
        ),
        "pooled_mean_target": (result.get("pooled") or {}).get("mean_target"),
        "median_target": result.get("median_target"),
        "baseline": result.get("baseline"),
        "descriptive_readout": descriptive_return_readout(result),
        "by_cohort": result.get("by_cohort"),
        "by_calendar_block": result.get("by_calendar_block"),
        "cohort_independent_replication": result.get("cohort_independent_replication"),
        "cohort_slices_are_descriptive": result.get("cohort_slices_are_descriptive"),
        "by_explanatory": result.get("by_explanatory"),
        "exclusion_reasons": result.get("exclusion_reasons"),
        "calendar_overlap_is_not_independent_replication": result.get(
            "calendar_overlap_is_not_independent_replication"
        ),
        "non_claims": ["NO_ALPHA", "NO_CAUSAL_IDENTIFICATION", "NO_MARKET_FORGE"],
    }
    policy = result.get("universe_policy")
    if isinstance(policy, Mapping):
        payload["universe_policy"] = {
            "semantic_sha256": policy.get("semantic_sha256"),
            "min_holders": policy.get("min_holders"),
            "min_liquidity_usd": policy.get("min_liquidity_usd"),
            "n_pass": policy.get("n_pass"),
            "n_fail": policy.get("n_fail"),
            "n_unknown": policy.get("n_unknown"),
            "n_base": policy.get("n_base"),
        }
    if result.get("target_kind"):
        payload["target_kind"] = result.get("target_kind")
        payload["mean_target_units"] = result.get("mean_target_units")
        payload["claim_level"] = result.get("claim_level")
        payload["labeled_net_return"] = result.get("labeled_net_return")
        payload["search_tier"] = result.get("search_tier")
    if result.get("observation_clock_policy"):
        payload["observation_clock_policy"] = result.get("observation_clock_policy")
    if result.get("target_exclusion_reasons") is not None:
        payload["target_exclusion_reasons"] = result.get("target_exclusion_reasons")
    if result.get("source_price_event_time") is not None:
        payload["source_price_event_time"] = result.get("source_price_event_time")
    if result.get("technical_stop") is not None:
        payload["technical_stop"] = result.get("technical_stop")
    if result.get("technical_failure") is not None:
        payload["technical_failure"] = result.get("technical_failure")
    if result.get("scientific_negative") is not None:
        payload["scientific_negative"] = result.get("scientific_negative")
    if result.get("schema") == "smial.hfic-temporal-query":
        from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_result_coherence

        coherence = temporal_result_coherence(result)
        payload["result_coherence"] = coherence["status"]
        if coherence["status"] != "COHERENT":
            payload["incoherent_fields"] = coherence["issues"]
            payload["repair_action"] = coherence["repair_action"]
            payload["science_ready"] = False
    if isinstance(evidence.get("revision_of"), Mapping):
        payload["revision_of"] = dict(evidence["revision_of"])
        payload["assessment_advisory"] = "REVIEW_REQUIRED_FOR_ASSESSMENT_BOUND_TO_SOURCE"
    return payload


def _append_temporal_intent(
    store: Any,
    *,
    journal_scope: str,
    spec_sha256: str,
    binding_sha: str,
    search_tier: str,
    git_sha: str,
) -> None:
    """Record the question before evaluation. A repeat of the same intent is not a new look."""

    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        try:
            wrapper = json.loads(record.payload_json)
            body = json.loads(str(wrapper.get("payload_canonical") or ""))
        except (TypeError, json.JSONDecodeError):
            continue
        if (
            isinstance(body, dict)
            and body.get("artifact_kind") == "DISCOVERY_QUERY_INTENT"
            and body.get("journal_scope") == journal_scope
            and body.get("spec_sha256") == spec_sha256
            and body.get("data_binding_sha256") == binding_sha
        ):
            return
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = datetime.now(timezone.utc)
    identity = hashlib.sha256(
        _canonical(
            {
                "spec_sha256": spec_sha256,
                "data_binding_sha256": binding_sha,
                "journal_scope": journal_scope,
                "artifact_kind": "DISCOVERY_QUERY_INTENT",
            }
        ).encode("utf-8")
    ).hexdigest()
    body = {
        "artifact_kind": "DISCOVERY_QUERY_INTENT",
        "journal_scope": journal_scope,
        "spec_sha256": spec_sha256,
        "data_binding_sha256": binding_sha,
        "search_tier": search_tier,
        "scientific_slot_reserved": False,
    }
    canonical = _canonical(body)
    payload = {
        "artifact_kind": "DISCOVERY_QUERY_INTENT",
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    event = ResearchEvent(
        record_id=f"HFIC-ART-INTENT-{identity[:40].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"HFIC-ART-INTENT-{identity[:40].upper()}",
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=f"RESEARCH-TXN-INTENT-{identity[:24].upper()}",
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha=git_sha,
        created_at=now,
    )
    store.append([event], transaction_id=event.transaction_id)


def resolve_research_scope(
    body: Mapping[str, Any], data_root: Path | None, census, binding, *, frozen_evidence: Mapping[str, Any] | None = None
) -> Any:
    """ResolvedScope for one scoped query over the admitted cohorts of this binding.

    `frozen_evidence` (a saved recipe's closure) pins the exact local snapshots and the evidence
    digest; the live registry is not consulted beyond them.
    """

    from solana_alpha_lab.factory import hfic_research_scope as scope_owner

    if data_root is None:
        raise GroundedDiscoveryError("RESEARCH_SCOPE_DATA_ROOT_REQUIRED")
    releases = {str(item.get("release_id")) for item in binding}
    try:
        frozen_shas = None
        if frozen_evidence is not None:
            frozen_shas = [
                str(item["snapshot_sha256"])
                for item in frozen_evidence.get("bindings") or []
                if item.get("adapter") == scope_owner.LOCAL_ADAPTER
            ]
        evidence = scope_owner.load_corpus_membership(
            Path(data_root),
            only_release_ids=releases,
            local_list_ids=scope_owner.referenced_list_ids(body),
            local_snapshot_shas=frozen_shas,
        )
        resolved = scope_owner.ResolvedScope(
            scope=body["research_scope"],
            list_condition=body.get("list_condition"),
            evidence=evidence,
            episode_ids=sorted({str(row.get("episode_id") or "") for row in census}),
            slices=body.get("diagnostic_slices") or [],
        )
        if frozen_evidence is not None and resolved.evidence_sha256 != frozen_evidence.get("evidence_sha256"):
            raise GroundedDiscoveryError("RESEARCH_SCOPE_EVIDENCE_DRIFT")
        return resolved
    except scope_owner.ResearchScopeError as exc:
        raise GroundedDiscoveryError(exc.code) from exc
    except GroundedDiscoveryError:
        raise
    except (OSError, ValueError, KeyError) as exc:
        raise GroundedDiscoveryError("RESEARCH_SCOPE_EVIDENCE_UNREADABLE") from exc


def scoped_binding_sha256(binding_sha: str, applied_sha256: str) -> str:
    """The one durable binding of a scoped look: rows + applied list masks."""

    from solana_alpha_lab.factory import hfic_research_scope as scope_owner

    return scope_owner.sha256_of({"data_binding_sha256": binding_sha, "research_scope_applied_sha256": applied_sha256})


def _apply_cohort_selection(spec: Mapping[str, Any], census, observations, binding):
    """Rows of the declared covered cohorts only (unscoped or undeclared: unchanged)."""

    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query

    body = validate_temporal_query(spec)["scientific_body"]
    if "research_scope" not in body:
        return census, observations, binding
    from solana_alpha_lab.factory.hfic_research_scope import selected_cohort_ids

    wanted = selected_cohort_ids(body["research_scope"])
    if wanted is None:
        return census, observations, binding
    if not set(wanted) <= {str(item.get("cohort_id")) for item in binding}:
        raise GroundedDiscoveryError("SCOPE_COHORT_NOT_IN_BINDING")
    keep = set(wanted)
    return (
        [row for row in census if str(row.get("cohort_id")) in keep],
        [row for row in observations if str(row.get("cohort_id")) in keep],
        [item for item in binding if str(item.get("cohort_id")) in keep],
    )


def _early_scope_applied_sha256(spec: Mapping[str, Any], data_root: Path | None, census, binding) -> str | None:
    """Current applied masks of a scoped query for the pre-values gate (None for unscoped)."""

    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query

    body = validate_temporal_query(spec)["scientific_body"]
    if "research_scope" not in body or data_root is None:
        return None
    from solana_alpha_lab.factory.hfic_research_scope import selected_cohort_ids

    wanted = selected_cohort_ids(body["research_scope"])
    if wanted is not None:
        census = [row for row in census if str(row.get("cohort_id")) in set(wanted)]
        binding = [item for item in binding if str(item.get("cohort_id")) in set(wanted)]
    return resolve_research_scope(body, data_root, census, binding).applied_sha256


def _scoped_binding_sha(binding_sha: str, resolved: Any) -> str:
    return scoped_binding_sha256(binding_sha, resolved.applied_sha256)


def run_recorded_discovery_query(
    store: Any,
    *,
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    binding: Sequence[Mapping[str, Any]],
    journal_scope: str,
    candidate_scope: Mapping[str, Any],
    priors: Sequence[Mapping[str, Any]] | None = None,
    git_sha: str,
    clock: datetime | None = None,
    operation_sha256: str | None = None,
    verified_market: str | None = None,
    correction: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
    data_root: Path | None = None,
) -> dict[str, Any]:
    """Public production entry: compute, persist or resume, return evidence refs.

    A saved older-version result is read as it is, without the evaluator.
    Only an explicit ``correction`` bound to that source ref and hash writes
    a CALCULATION_REVISION, on the same spec and frozen input.
    """

    if not isinstance(journal_scope, str) or not journal_scope.strip():
        raise GroundedDiscoveryError("JOURNAL_SCOPE_REQUIRED")
    if not isinstance(git_sha, str) or len(git_sha) != 40:
        raise GroundedDiscoveryError("GIT_SHA_REQUIRED")
    bound_scope = scope_bound_to_spec(spec, candidate_scope)
    if _is_temporal_query(spec):
        if not isinstance(operation_sha256, str) or not operation_sha256.strip():
            raise GroundedDiscoveryError("ORDINARY_OPERATION_REQUIRED")
        if not isinstance(verified_market, str) or len(verified_market) != 64:
            raise GroundedDiscoveryError("ORDINARY_OPERATION_MARKET_UNVERIFIED")
        from solana_alpha_lab.factory.hfic_ordinary_operation import (
            OrdinaryOperationError,
            gate_before_values,
        )

        from solana_alpha_lab.factory.hfic_research_universe_policy import (
            UniversePolicyError,
            admitted_with_policy,
            effective_policy,
        )

        policy_error: UniversePolicyError | None = None
        try:
            policy_head = effective_policy(store)
        except UniversePolicyError as exc:
            policy_error = exc
            policy_head = {"definition": None}
        gate_policy = policy_head.get("definition")
        if (gate_policy is None or policy_error is not None) and correction is None:
            from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query

            early_spec = validate_temporal_query(spec)["spec_sha256"]
            owned_now = [
                item
                for item in list_discovery_looks(store, journal_scope)
                if item.get("operation_sha256") == operation_sha256
                and item.get("spec_sha256") == early_spec
                and isinstance(item.get("result"), Mapping)
            ]
            if not owned_now:
                raise GroundedDiscoveryError(
                    policy_error.code if policy_error is not None else "UNIVERSE_POLICY_REQUIRED"
                )
        # A declared covered subset is applied before the gate, so gate, intent and look see the same rows.
        full_binding = list(binding)  # the operation fingerprint is stamped over the published cohorts
        census, observations, binding = _apply_cohort_selection(spec, census, observations, binding)
        gate_scope_applied = _early_scope_applied_sha256(spec, data_root, census, binding)
        try:
            gate_before_values(
                store,
                operation_sha256=operation_sha256,
                spec=spec,
                journal_scope=journal_scope,
                scope_applied_sha256=gate_scope_applied,
                binding_cohorts=full_binding,
                verified_market=verified_market,
                correction=correction,
                repo_root=repo_root,
                data_root=data_root,
                census=census,
                observations=observations,
                admitted=admitted_with_policy(admit_discovery_binding(binding), gate_policy),
            )
        except OrdinaryOperationError as exc:
            raise GroundedDiscoveryError(str(exc.code)) from exc
    elif correction is not None:
        raise GroundedDiscoveryError("CALCULATION_REVISION_UNSUPPORTED")
    replayed = None
    source_look: Mapping[str, Any] | None = None
    from solana_alpha_lab.factory.hfic_research_universe_policy import (
        UniversePolicyError,
        admitted_with_policy,
        effective_policy,
    )

    if not _is_temporal_query(spec):
        policy_error = None
        try:
            policy_head = effective_policy(store)
        except UniversePolicyError as exc:
            policy_error = exc
            policy_head = {"definition": None}
    policy_definition = policy_head.get("definition")
    revising_legacy = False
    research_scope = None
    if _is_temporal_query(spec):
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            TEMPORAL_CALCULATION_VERSION,
            TEMPORAL_CALCULATION_VERSION_V5,
            TEMPORAL_CALCULATION_VERSIONS_READABLE,
            current_look_evidence,
            saved_downside_revision,
            validate_temporal_query,
            verify_calculation_revision_source,
        )

        prevalidated = validate_temporal_query(spec)
        selected_cohorts = None
        if "research_scope" in prevalidated["scientific_body"]:
            from solana_alpha_lab.factory.hfic_research_scope import selected_cohort_ids

            selected_cohorts = selected_cohort_ids(prevalidated["scientific_body"]["research_scope"])
        if selected_cohorts is not None:
            # A declared covered subset is part of the question, fixed before any outcome is read.
            present = {str(item.get("cohort_id")) for item in binding}
            if not set(selected_cohorts) <= present:
                raise GroundedDiscoveryError("SCOPE_COHORT_NOT_IN_BINDING")
            wanted = set(selected_cohorts)
            binding = [item for item in binding if str(item.get("cohort_id")) in wanted]
            census = [row for row in census if str(row.get("cohort_id")) in wanted]
            observations = [row for row in observations if str(row.get("cohort_id")) in wanted]
        bare_admitted = admit_discovery_binding(binding)
        bare_binding_sha = data_binding_sha256(bare_admitted, census, observations)
        admitted_meta = admitted_with_policy(bare_admitted, policy_definition)
        pre_binding_sha = data_binding_sha256(admitted_meta, census, observations)
        if "research_scope" in prevalidated["scientific_body"]:
            # Masks come only from verified release files + registered snapshots; a changed
            # list evidence is a different applied input, never a stale same-question replay.
            research_scope = resolve_research_scope(prevalidated["scientific_body"], data_root, census, binding)
            bare_binding_sha = _scoped_binding_sha(bare_binding_sha, research_scope)
            pre_binding_sha = _scoped_binding_sha(pre_binding_sha, research_scope)

        def _same_question_binding(item: Mapping[str, Any]) -> bool:
            stored_sha = item.get("data_binding_sha256")
            if stored_sha == pre_binding_sha:
                return True
            # Pre-policy looks carry the bare admission hash. Today's profile
            # stamps universe_policy_semantic_sha256 into admitted metadata even
            # at 0/0, so revision/readback must still recognize those rows —
            # but only for this operation, an explicit correction, or when
            # today's profile is absent (history readback). A fresh operation
            # under an active profile must not free-replay another look's
            # unfiltered legacy result.
            if stored_sha != bare_binding_sha:
                return False
            if isinstance((item.get("result") or {}).get("universe_policy"), Mapping):
                return False
            if correction is not None:
                return True
            if policy_definition is None or policy_error is not None:
                return True
            return item.get("operation_sha256") == operation_sha256

        journal_looks = list_discovery_looks(store, journal_scope)
        same_question = [
            item
            for item in journal_looks
            if item.get("spec_sha256") == prevalidated["spec_sha256"]
            and _same_question_binding(item)
            and isinstance(item.get("result"), Mapping)
        ]
        replayed = next(
            (item for item in same_question if item.get("calculation_version") == TEMPORAL_CALCULATION_VERSION),
            None,
        )
        if correction is not None:
            saved = saved_downside_revision(
                [item for item in same_question if item.get("operation_sha256") == operation_sha256],
                correction,
            )
            if saved is not None:
                replayed = saved
            source_look = verify_calculation_revision_source(
                journal_looks,
                correction=correction,
                spec=spec,
                binding=list(binding),
                operation_sha256=operation_sha256,
                target_calculation_version=(
                    TEMPORAL_CALCULATION_VERSION_V5 if saved is not None else TEMPORAL_CALCULATION_VERSION
                ),
            )
            allowed_source_bindings = {pre_binding_sha}
            if not isinstance((source_look.get("result") or {}).get("universe_policy"), Mapping):
                allowed_source_bindings.add(bare_binding_sha)
            if source_look.get("data_binding_sha256") not in allowed_source_bindings:
                raise GroundedDiscoveryError("CALCULATION_REVISION_INPUT_MISMATCH")
            if replayed is not None:
                # Already applied: the verified request reads the saved revision.
                source_look = None
        elif replayed is None:
            # Ordinary readback of a saved older version: exact bytes, no evaluator.
            historical = [
                item
                for item in same_question
                if item.get("calculation_version") in TEMPORAL_CALCULATION_VERSIONS_READABLE
            ]
            replayed = current_look_evidence(historical[-1], historical) if historical else None
            if replayed is None and (policy_definition is None or policy_error is not None):
                # Today's profile is not required to read this operation's saved result.
                owned = [
                    item
                    for item in journal_looks
                    if item.get("operation_sha256") == operation_sha256
                    and item.get("spec_sha256") == prevalidated["spec_sha256"]
                    and isinstance(item.get("result"), Mapping)
                ]
                current = next(
                    (
                        item
                        for item in owned
                        if item.get("calculation_version") == TEMPORAL_CALCULATION_VERSION
                    ),
                    None,
                )
                if current is not None:
                    replayed = current
                elif owned:
                    readable = [
                        item
                        for item in owned
                        if item.get("calculation_version") in TEMPORAL_CALCULATION_VERSIONS_READABLE
                    ]
                    replayed = current_look_evidence(readable[-1], readable) if readable else None
    readback_look = None
    revising_legacy = source_look is not None and not isinstance(
        (source_look.get("result") or {}).get("universe_policy"), Mapping
    )
    if replayed is None:
        if policy_error is not None and not revising_legacy:
            raise GroundedDiscoveryError(policy_error.code)
        if policy_definition is None and not revising_legacy:
            raise GroundedDiscoveryError("UNIVERSE_POLICY_REQUIRED")
        if _is_temporal_query(spec):
            from solana_alpha_lab.factory.hfic_temporal_discovery import classify_temporal_look

            classify_temporal_look(list_discovery_looks(store, journal_scope), spec)
            if source_look is None:
                _append_temporal_intent(
                    store,
                    journal_scope=journal_scope,
                    spec_sha256=prevalidated["spec_sha256"],
                    binding_sha=pre_binding_sha,
                    search_tier=str(prevalidated["search_tier"]),
                    git_sha=git_sha,
                )
        computed = execute_discovery_from_rows(
            census,
            observations,
            spec,
            binding,
            universe_policy=None if revising_legacy else policy_definition,
            research_scope=research_scope,
        )
        if source_look is not None:
            recipe = computed["summary"].get("experiment_recipe") or {}
            stored_recipe = source_look["result"].get("experiment_recipe") or {}
            if (
                recipe.get("spec") != stored_recipe.get("spec")
                or recipe.get("frozen_input") != stored_recipe.get("frozen_input")
                or recipe.get("scientific_identity") != stored_recipe.get("scientific_identity")
            ):
                raise GroundedDiscoveryError("CALCULATION_REVISION_INPUT_MISMATCH")
            from solana_alpha_lab.factory.hfic_temporal_discovery import (
                assert_downside_revision_preserves_v4,
            )

            assert_downside_revision_preserves_v4(source_look["result"], computed["summary"])
    else:
        computed = {
            "admitted": admitted_meta,
            "summary": replayed["result"],
            "members_projected": 0,
            "replayed_without_evaluator": True,
        }
        # Always keep the saved look's binding/identity. Recomputing the
        # admission hash under today's profile would mint a second record for
        # the same summary (legacy bare bindings and frozen snapshots).
        readback_look = replayed
    summary = computed["summary"]
    calc_version = str(summary.get("calculation_version") or CALCULATION_VERSION)
    temporal = summary.get("schema") == "smial.hfic-temporal-query"
    binding_sha = data_binding_sha256(computed["admitted"], census, observations)
    if research_scope is not None:
        # One identity owner end to end: the durable look keeps the applied list masks, as the intent did.
        binding_sha = _scoped_binding_sha(binding_sha, research_scope)
    digest = result_sha256(summary)
    identity = _look_identity(
        summary["spec_sha256"],
        binding_sha,
        journal_scope,
        calculation_version=calc_version,
    )
    previous = list_discovery_looks(store, journal_scope)
    existing = next(
        (
            item
            for item in previous
            if item.get("spec_sha256") == summary["spec_sha256"]
            and item.get("data_binding_sha256") == binding_sha
            and item.get("calculation_version") == calc_version
        ),
        None,
    )
    if readback_look is not None:
        binding_sha = str(readback_look.get("data_binding_sha256") or binding_sha)
        digest = str(readback_look.get("result_sha256") or digest)
        existing = readback_look
    if existing is not None and temporal and isinstance(existing.get("result"), Mapping):
        summary = existing["result"]
        digest = str(existing.get("result_sha256") or result_sha256(summary))
    budget_history = []
    policy_shift = False
    current_policy = (summary.get("universe_policy") or {}).get("semantic_sha256")
    for item in previous:
        same_spec = item.get("spec_sha256") == summary["spec_sha256"]
        changed_binding = item.get("data_binding_sha256") != binding_sha
        prior_policy = ((item.get("result") or {}).get("universe_policy") or {}).get("semantic_sha256")
        policy_only = (
            same_spec
            and changed_binding
            and prior_policy
            and current_policy
            and prior_policy != current_policy
            and same_rows_under_policy(
                item,
                admitted=computed["admitted"],
                census=census,
                observations=observations,
                policy_sha=str(prior_policy),
                scope_applied_sha256=research_scope.applied_sha256 if research_scope is not None else None,
            )
        )
        if policy_only:
            policy_shift = True
            budget_history.append({**item, "spec_sha256": "DATA_BINDING_CHANGED"})
        elif same_spec and changed_binding:
            budget_history.append({**item, "spec_sha256": "DATA_BINDING_CHANGED"})
        else:
            budget_history.append(item)
    classify_spec = spec
    if policy_shift and _is_temporal_query(spec):
        classify_spec = dict(spec)
        classify_spec["adaptation_of"] = summary["spec_sha256"]
    look = classify_query_look(budget_history, classify_spec)
    revision_of: dict[str, Any] | None = None
    if source_look is not None:
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            calculation_revision_reason,
            look_revision_root,
        )

        if look.get("new_look") is not False or look.get("look_class") != "CALCULATION_REVISION":
            raise GroundedDiscoveryError("CALCULATION_REVISION_NOT_A_REVISION")
        revision_of = {
            "record_id": str(source_look.get("record_id") or ""),
            "root_record_id": look_revision_root(source_look),
            "result_sha256": source_look.get("result_sha256"),
            "calculation_version": source_look.get("calculation_version"),
            "data_binding_sha256": source_look.get("data_binding_sha256"),
            "reason": calculation_revision_reason(source_look["result"]),
        }
    if existing is not None:
        record_id = str(existing.get("record_id") or "")
        budget = {
            "spec_sha256": summary["spec_sha256"],
            "new_look": False,
            "look_class": "RETRY_SAME_BYTES",
            "search_tier": look.get("search_tier"),
            "main_count": look["main_count"],
            "adaptive_count": look["adaptive_count"],
            "simple_main_count": look.get("simple_main_count"),
            "compound_main_count": look.get("compound_main_count"),
        }
        stored = existing.get("candidate_scope") if isinstance(existing, Mapping) else None
        relation = relate_look_scope(
            stored if isinstance(stored, Mapping) else {},
            candidate_scope,
        )
        if isinstance(stored, Mapping) and any(
            _axis_text(stored.get(key)) for key in _LOOK_CLAIM_AXES
        ):
            confirming = {key: value for key, value in stored.items() if _axis_text(value)}
        else:
            confirming = {}
            relation = "LOOK_SCOPE_UNBOUND"
    else:
        record_id = f"HFIC-ART-DISCOVERY-{identity[:40].upper()}"
        budget = look
        if source_look is not None:
            # A revision answers the saved question; its claim scope is the source's.
            bound_scope = {
                key: value
                for key, value in dict(source_look.get("candidate_scope") or {}).items()
                if _axis_text(value)
            }
        _append_discovery_look(
            store,
            record_id=record_id,
            journal_scope=journal_scope,
            spec=_stored_query_spec(spec),
            spec_sha256=summary["spec_sha256"],
            binding_sha=binding_sha,
            data_refs=list(computed["admitted"]["cohorts"]),
            digest=digest,
            identity=identity,
            summary=summary,
            look=look,
            git_sha=git_sha,
            clock=clock,
            candidate_scope=bound_scope,
            operation_sha256=operation_sha256,
            revision_of=revision_of,
        )
        confirming = dict(bound_scope)
        relation = (
            "LOOK_SCOPE_MATCH"
            if source_look is None
            else relate_look_scope(bound_scope, candidate_scope)
        )
    evidence = {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "calculation_version": calc_version,
        "journal_scope": journal_scope,
        "data_binding_sha256": binding_sha,
        "result_sha256": digest,
        "result": summary,
        "descriptive_readout": descriptive_return_readout(summary),
        "result_refs": [record_id],
        "queries": [
            {
                "query_id": summary["query_id"],
                "spec_sha256": summary["spec_sha256"],
                "record_id": record_id,
                "look_class": budget["look_class"],
                "new_look": budget["new_look"],
                **(
                    {"search_tier": budget.get("search_tier") or summary.get("search_tier")}
                    if summary.get("search_tier")
                    else {}
                ),
            }
        ],
        "budget": {
            "main_count": budget["main_count"],
            "adaptive_count": budget["adaptive_count"],
            "main_limit": MAX_MAIN_QUERY_SPECS,
            "adaptive_limit": MAX_ADAPTIVE_REFINEMENTS,
        },
        "candidate_scope": confirming,
        "look_scope_relation": relation,
        **(
            {"universe_population": "LEGACY_FROZEN_POPULATION"}
            if revising_legacy
            else {}
        ),
        "priors": [dict(item) for item in (priors or [])],
        "scientific_slot_reserved": False,
    }
    if summary.get("search_tier"):
        from solana_alpha_lab.factory.hfic_temporal_discovery import assess_tier_progress

        evidence["budget"]["simple_main_count"] = budget.get("simple_main_count")
        evidence["budget"]["compound_main_count"] = budget.get("compound_main_count")
        evidence["budget"]["viewed_variants"] = list(summary.get("viewed_variants") or [])
        evidence["tier_progress"] = assess_tier_progress(
            list_discovery_looks(store, journal_scope),
            freeze_worthy=False,
        )
    lineage = existing.get("revision_of") if existing is not None else revision_of
    if isinstance(lineage, Mapping):
        evidence["revision_of"] = dict(lineage)
        evidence["assessment_advisory"] = "REVIEW_REQUIRED_FOR_ASSESSMENT_BOUND_TO_SOURCE"
    if existing is not None:
        evidence["requested_candidate_scope"] = dict(candidate_scope)
    return assert_computed_grounded_evidence(store, evidence)


def _stored_query_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    if _is_temporal_query(spec):
        from solana_alpha_lab.factory.hfic_temporal_discovery import canonical_temporal_spec

        return canonical_temporal_spec(spec)
    stored = validate_query_spec(spec)
    stored["explanatory_rules"] = _jsonable(spec.get("explanatory_rules") or [])
    return stored


def _append_discovery_look(
    store: Any,
    *,
    record_id: str,
    journal_scope: str,
    spec: Mapping[str, Any],
    spec_sha256: str,
    binding_sha: str,
    data_refs: Sequence[Mapping[str, Any]],
    digest: str,
    identity: str,
    summary: Mapping[str, Any],
    look: Mapping[str, Any],
    git_sha: str,
    clock: datetime | None,
    candidate_scope: Mapping[str, Any] | None = None,
    operation_sha256: str | None = None,
    revision_of: Mapping[str, Any] | None = None,
) -> None:
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise GroundedDiscoveryError("CLOCK_NAIVE")
    body = {
        "schema": "smial.discovery-query-look",
        "schema_version": "1.0",
        "journal_scope": journal_scope,
        "calculation_version": str(summary.get("calculation_version") or CALCULATION_VERSION),
        "query_id": summary.get("query_id"),
        "spec": dict(spec),
        "spec_sha256": spec_sha256,
        "data_refs": [dict(item) for item in data_refs],
        "data_binding_sha256": binding_sha,
        "result_sha256": digest,
        "result": summary,
        "look_class": look.get("look_class"),
        "new_look": bool(look.get("new_look", True)),
        "scientific_slot_reserved": False,
        "candidate_scope": {
            key: value
            for key, value in dict(candidate_scope or {}).items()
            if _axis_text(value)
        },
    }
    if isinstance(operation_sha256, str) and operation_sha256:
        body["operation_sha256"] = operation_sha256
    if isinstance(revision_of, Mapping):
        body["revision_of"] = dict(revision_of)
    if summary.get("search_tier"):
        body["search_tier"] = summary.get("search_tier")
    if summary.get("target_kind"):
        body["target_kind"] = summary.get("target_kind")
    if summary.get("viewed_variants"):
        body["viewed_variants"] = list(summary["viewed_variants"])
    canonical = _canonical(body)
    payload = {
        "research_artifact_id": record_id,
        "session_id": f"HFIC-DISCOVERY-{journal_scope}",
        "hfic_protocol": "HFIC-V1.2",
        "artifact_kind": "DISCOVERY_QUERY_LOOK",
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    event = ResearchEvent(
        record_id=record_id,
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=record_id,
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=f"RESEARCH-TXN-DISCOVERY-{identity[:24].upper()}",
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha=git_sha,
        created_at=now,
    )
    store.append([event], transaction_id=event.transaction_id)


def load_parquet_rows(path: Path, *, filters: list[tuple[str, str, Any]] | None = None) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    table = pq.read_table(Path(path), filters=filters)
    return table.to_pylist()


def live_state_only_coverage(data_root: Path) -> dict[str, Any]:
    """No-write joint coverage. Never selects typed_value."""

    import duckdb

    from solana_alpha_lab.factory.live_cohort_discovery_release import (
        load_live_corpus_lineage,
    )

    lineage = load_live_corpus_lineage(Path(data_root))
    binding = resolve_published_discovery_binding(Path(data_root))
    cohorts = [
        item
        for item in (lineage.get("cohorts") or [])
        if isinstance(item, Mapping)
    ]
    cohorts.sort(key=lambda item: int(item.get("corpus_version") or 0))
    reports = []
    connection = duckdb.connect(database=":memory:")
    try:
        for item in cohorts:
            census = Path(data_root) / str(item["census_rel"])
            obs = Path(data_root) / str(item["obs_rel"])
            columns = {
                str(row[0])
                for row in connection.execute(
                    "DESCRIBE SELECT * FROM read_parquet(?)",
                    [str(obs)],
                ).fetchall()
            }
            if "typed_value" in columns:
                columns.discard("typed_value")
            headline = connection.execute(
                f"""
                WITH census AS (
                  SELECT mint, candidate_state, authoritative_anchor
                  FROM read_parquet(?)
                ), x_elig AS (
                  SELECT mint, authoritative_anchor
                  FROM census WHERE candidate_state = 'X_ELIGIBLE'
                ), latest AS (
                  SELECT mint, point_id, field_id, state,
                         first_reliable_available_at AS available_at,
                         row_number() OVER (
                           PARTITION BY mint, point_id, field_id
                           ORDER BY first_reliable_available_at DESC NULLS LAST
                         ) AS rn
                  FROM read_parquet(?)
                  WHERE field_id IN ('{PRICE}', '{LIQUIDITY}')
                    AND point_id IN ('X300', 'Y900', 'Y1800', 'Y3600')
                ), cell AS (
                  SELECT * FROM latest WHERE rn = 1
                ), base AS (
                  SELECT x.mint
                  FROM x_elig x
                  JOIN cell liq
                    ON liq.mint = x.mint AND liq.point_id = 'X300'
                   AND liq.field_id = '{LIQUIDITY}' AND liq.state = 'OBSERVED'
                  WHERE try_cast(liq.available_at AS TIMESTAMPTZ)
                        <= try_cast(x.authoritative_anchor AS TIMESTAMPTZ)
                           + INTERVAL 600 SECOND
                ), joint AS (
                  SELECT b.mint
                  FROM base b
                  JOIN cell price
                    ON price.mint = b.mint AND price.point_id = 'X300'
                   AND price.field_id = '{PRICE}' AND price.state = 'OBSERVED'
                   AND price.available_at IS NOT NULL
                )
                SELECT
                  (SELECT count(*) FROM census),
                  (SELECT count(*) FROM x_elig),
                  (SELECT count(*) FROM base),
                  (SELECT count(*) FROM joint)
                """,
                [str(census), str(obs)],
            ).fetchone()
            prefix = connection.execute(
                f"""
                WITH census AS (
                  SELECT mint, candidate_state, authoritative_anchor
                  FROM read_parquet(?)
                ), x_elig AS (
                  SELECT mint, authoritative_anchor
                  FROM census WHERE candidate_state = 'X_ELIGIBLE'
                ), latest AS (
                  SELECT mint, point_id, field_id, state,
                         first_reliable_available_at AS available_at,
                         row_number() OVER (
                           PARTITION BY mint, point_id, field_id
                           ORDER BY first_reliable_available_at DESC NULLS LAST
                         ) AS rn
                  FROM read_parquet(?)
                  WHERE field_id IN ('{PRICE}', '{LIQUIDITY}')
                    AND point_id IN ('X300', 'Y900', 'Y1800')
                ), cell AS (
                  SELECT * FROM latest WHERE rn = 1
                ), base AS (
                  SELECT x.mint
                  FROM x_elig x
                  JOIN cell liq
                    ON liq.mint = x.mint AND liq.point_id = 'X300'
                   AND liq.field_id = '{LIQUIDITY}' AND liq.state = 'OBSERVED'
                  WHERE try_cast(liq.available_at AS TIMESTAMPTZ)
                        <= try_cast(x.authoritative_anchor AS TIMESTAMPTZ)
                           + INTERVAL 600 SECOND
                )
                SELECT count(*) FROM (
                  SELECT cell.mint
                  FROM cell
                  JOIN base ON base.mint = cell.mint
                  WHERE cell.state = 'OBSERVED' AND cell.available_at IS NOT NULL
                  GROUP BY cell.mint
                  HAVING count(*) = 6
                )
                """,
                [str(census), str(obs)],
            ).fetchone()
            reports.append(
                {
                    "cohort_id": item.get("cohort_id"),
                    "release_id": item.get("release_id"),
                    "evidence_role": LIVE_EVIDENCE_ROLE,
                    "census_rows": int(headline[0]),
                    "x_eligible": int(headline[1]),
                    "base_x_like": int(headline[2]),
                    "joint_x300_price_and_liquidity": int(headline[3]),
                    "joint_prefix_price_liquidity_through_y1800": int(prefix[0]),
                    "typed_value_selected": False,
                }
            )
    finally:
        connection.close()
    windows = []
    for item in cohorts:
        parsed = _cohort_window(str(item.get("cohort_id") or ""))
        if parsed is not None:
            windows.append((str(item.get("cohort_id")), parsed[0], parsed[1]))
    overlaps = []
    for index, (left_id, left_start, left_end) in enumerate(windows):
        for right_id, right_start, right_end in windows[index + 1 :]:
            start = max(left_start, right_start)
            end = min(left_end, right_end)
            if start < end:
                overlaps.append(
                    {
                        "left_cohort_id": left_id,
                        "right_cohort_id": right_id,
                        "overlap_start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "overlap_end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "independent_replication": False,
                    }
                )
    return {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "scientific_writes": 0,
        "typed_value_selected": False,
        "binding": binding,
        "cohorts": reports,
        "collection_window_overlaps": overlaps,
        "first_supported_scope": [
            "X300_PRICE_LIQUIDITY_BASELINE",
            "PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800",
        ],
        "excluded_from_first_scope": ["TRADERS_COMPLETE_PREFIX"],
        "denominator_note": "joint counts are inside base_x-like PIT liquidity, not census rows and not per-cell margins",
    }
