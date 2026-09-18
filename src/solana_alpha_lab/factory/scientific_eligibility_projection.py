"""Pure ScientificEligibilityProjection over a verified release.

Base scientific population is X300-valid X_ELIGIBLE. Y completeness never
shrinks that denominator. Outcome missingness is coverage, not a second
population. Never materializes Y typed values.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.factory.tokens_v2_typed_projection import STATE_OBSERVED

SPEC_RELATIVE = "configs/scientific_eligibility_projection_v1.yaml"
PROJECTION_SCHEMA = "smial.scientific-eligibility-projection"
PROJECTION_SCHEMA_VERSION = "1.0"
RULE_ID = "BASE_X_X300_VALID_X_ELIGIBLE_V1"
X_POINT_ID = "X300"
X_FIELD_ID = "FIELD-LIQUIDITY-USD-001"
X_DUE_OFFSET_SECONDS = 300
X_ALLOWED_LATENESS_SECONDS = 300
MIN_USABLE_BASE_X_POPULATION = 10
READINESS_COMPLETE = "COMPLETE"
READINESS_MISSINGNESS_UNRESOLVED = "MISSINGNESS_UNRESOLVED"
READINESS_UNSPECIFIED = "UNSPECIFIED"
ELIGIBILITY_SCOPE_FULL_LIFECYCLE = "FULL_LIFECYCLE_COMPLETENESS"
ELIGIBILITY_SCOPE_BASE_X = "BASE_X_POPULATION"
Y_POINT_PREFIX = "Y"
RESOLVED_OBSERVATION_STATES = frozenset(
    {
        "OBSERVED",
        "MISSING_TYPED",
        "CENSORED_LATE",
        "CENSORED",
        "DISAPPEARED",
        "EXCLUDED_AMBIGUOUS",
    }
)
C1_EXPECTED = {
    "base_x_n": 475,
    "lifecycle_observed_n": 148,
    "lifecycle_censored_late_n": 327,
}
CANONICAL_X300_SCHEDULE_INCOMPATIBLE = "CANONICAL_X300_SCHEDULE_INCOMPATIBLE"
CANONICAL_SCHEDULE_UNBOUND = "CANONICAL_SCHEDULE_UNBOUND"
CANONICAL_RELEASE_IDENTITY_UNBOUND = "CANONICAL_RELEASE_IDENTITY_UNBOUND"
CANONICAL_RELEASE_BIND_FAILED = "CANONICAL_RELEASE_BIND_FAILED"


class ScientificEligibilityError(ValueError):
    """Fail-closed projection error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_projection_spec(root: Path, relative: str = SPEC_RELATIVE) -> dict[str, Any]:
    path = Path(root) / relative
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScientificEligibilityError("PROJECTION_SPEC_MISSING") from exc
    if not isinstance(loaded, dict):
        raise ScientificEligibilityError("PROJECTION_SPEC_INVALID")
    return loaded


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _mint(row: Mapping[str, Any]) -> str:
    return str(row.get("mint") or row.get("entity_id") or "")


def _x300_pit_ok(
    *,
    available_at: object,
    anchor: object,
    due_offset_seconds: int,
    allowed_lateness_seconds: int,
) -> bool:
    observed_at = _parse_utc(available_at)
    member_anchor = _parse_utc(anchor)
    if observed_at is None or member_anchor is None:
        return False
    deadline = member_anchor + timedelta(
        seconds=int(due_offset_seconds) + int(allowed_lateness_seconds)
    )
    return observed_at <= deadline


def _available_at_rank(row: Mapping[str, Any]) -> datetime:
    parsed = _parse_utc(row.get("first_reliable_available_at"))
    if parsed is None:
        return datetime.min.replace(tzinfo=UTC)
    return parsed


def required_outcome_point_ids(spec: Mapping[str, Any] | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(item["point_id"] for item in required_outcomes_from_spec(spec))
    )


def sanitize_projection_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Drop Y/X typed values. Coverage uses state and clocks only."""

    return {key: value for key, value in row.items() if key != "typed_value"}


def required_outcomes_from_spec(spec: Mapping[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(spec, Mapping):
        return []
    raw = spec.get("required_outcomes")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        point_id = str(item.get("point_id") or "")
        role = str(item.get("role") or "PRIMARY")
        field_ids = item.get("field_ids")
        if not point_id or not isinstance(field_ids, list):
            continue
        for field_id in field_ids:
            text = str(field_id or "")
            key = (point_id, text)
            if not text or key in seen:
                continue
            seen.add(key)
            out.append({"point_id": point_id, "field_id": text, "role": role})
    return out


def full_lifecycle_scope_equivalent(
    required_point_ids: Sequence[str] | None,
    schedule_y_point_ids: Sequence[str] | None,
) -> bool:
    """True only when required Y points exactly equal the bound schedule Y set."""

    if not required_point_ids or not schedule_y_point_ids:
        return False
    required = {str(item) for item in required_point_ids if str(item).startswith(Y_POINT_PREFIX)}
    scheduled = {str(item) for item in schedule_y_point_ids if str(item).startswith(Y_POINT_PREFIX)}
    return bool(required) and required == scheduled


def schedule_y_point_ids(schedule: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(schedule, Mapping):
        return ()
    points = schedule.get("y_points")
    if not isinstance(points, list):
        return ()
    out: list[str] = []
    for item in points:
        if not isinstance(item, Mapping):
            continue
        point_id = str(item.get("point_id") or "")
        if point_id.startswith(Y_POINT_PREFIX):
            out.append(point_id)
    return tuple(out)


def bound_schedule_y_point_ids(root: Path | None = None) -> tuple[str, ...]:
    """Factory-bound lifecycle Y set. Never the experiment's own y_points."""

    loaded = load_projection_spec(Path(root) if root is not None else Path("."))
    raw = loaded.get("bound_schedule_y_point_ids")
    if not isinstance(raw, list):
        return ()
    return tuple(
        str(item)
        for item in raw
        if str(item).startswith(Y_POINT_PREFIX)
    )


def canonical_c1_identity(root: Path | None = None) -> dict[str, str]:
    loaded = load_projection_spec(Path(root) if root is not None else Path("."))
    c1 = loaded.get("canonical_c1")
    if not isinstance(c1, Mapping):
        raise ScientificEligibilityError(CANONICAL_RELEASE_IDENTITY_UNBOUND)
    dataset_id = str(c1.get("dataset_id") or "")
    cohort_id = str(c1.get("cohort_id") or "")
    release_id = str(c1.get("release_id") or "")
    if not dataset_id or not cohort_id or not release_id:
        raise ScientificEligibilityError(CANONICAL_RELEASE_IDENTITY_UNBOUND)
    return {
        "dataset_id": dataset_id,
        "cohort_id": cohort_id,
        "release_id": release_id,
    }


def verify_factory_x300_schedule(schedule: Mapping[str, Any] | None) -> dict[str, Any]:
    """Fail closed unless the bound collection schedule matches factory X300 PIT."""

    if not isinstance(schedule, Mapping):
        raise ScientificEligibilityError(CANONICAL_X300_SCHEDULE_INCOMPATIBLE)
    x_point = schedule.get("x_point")
    if not isinstance(x_point, Mapping):
        raise ScientificEligibilityError(CANONICAL_X300_SCHEDULE_INCOMPATIBLE)
    try:
        due = int(x_point.get("due_offset_seconds"))
        late = int(x_point.get("allowed_lateness_seconds"))
    except (TypeError, ValueError) as exc:
        raise ScientificEligibilityError(CANONICAL_X300_SCHEDULE_INCOMPATIBLE) from exc
    point_id = str(x_point.get("point_id") or "")
    if (
        point_id != X_POINT_ID
        or due != X_DUE_OFFSET_SECONDS
        or late != X_ALLOWED_LATENESS_SECONDS
    ):
        raise ScientificEligibilityError(CANONICAL_X300_SCHEDULE_INCOMPATIBLE)
    population = (
        schedule.get("population")
        if isinstance(schedule.get("population"), Mapping)
        else {}
    )
    predicates = population.get("x_eligibility_predicates") if isinstance(population, Mapping) else None
    field_ok = False
    if isinstance(predicates, list):
        for item in predicates:
            if isinstance(item, Mapping) and str(item.get("field_id") or "") == X_FIELD_ID:
                field_ok = True
                break
    if not field_ok:
        raise ScientificEligibilityError(CANONICAL_X300_SCHEDULE_INCOMPATIBLE)
    from solana_alpha_lab.factory.observation_schedule import (
        schedule_sha256 as hash_schedule,
    )

    return {
        "schedule_key": str(schedule.get("schedule_key") or schedule.get("schedule_id") or ""),
        "schedule_sha256": hash_schedule(schedule),
        "x_point_id": X_POINT_ID,
        "x_field_id": X_FIELD_ID,
        "x_due_offset_seconds": due,
        "x_allowed_lateness_seconds": late,
        "compatible": True,
    }


def lineage_canonical_corpus_pins(
    data_root: Path,
    *,
    repo_root: Path,
) -> dict[str, str]:
    """Resolve expected C1 identity through current lineage hashes, not ExperimentSpec."""

    expected = canonical_c1_identity(repo_root)
    from solana_alpha_lab.factory.live_cohort_discovery_release import (
        load_live_corpus_lineage,
    )

    try:
        lineage = load_live_corpus_lineage(Path(data_root))
    except Exception as exc:
        raise ScientificEligibilityError(CANONICAL_RELEASE_IDENTITY_UNBOUND) from exc
    if str(lineage.get("corpus_dataset_id") or "") != expected["dataset_id"]:
        raise ScientificEligibilityError(CANONICAL_RELEASE_IDENTITY_UNBOUND)
    matches = [
        item
        for item in (lineage.get("cohorts") or [])
        if isinstance(item, Mapping)
        and str(item.get("cohort_id") or "") == expected["cohort_id"]
    ]
    if len(matches) != 1:
        raise ScientificEligibilityError(CANONICAL_RELEASE_IDENTITY_UNBOUND)
    component = matches[0]
    if str(component.get("release_id") or "") != expected["release_id"]:
        raise ScientificEligibilityError(CANONICAL_RELEASE_IDENTITY_UNBOUND)
    census_sha = str(component.get("census_sha256") or "")
    obs_sha = str(component.get("observations_sha256") or "")
    if len(census_sha) != 64 or len(obs_sha) != 64:
        raise ScientificEligibilityError(CANONICAL_RELEASE_IDENTITY_UNBOUND)
    if any(char not in "0123456789abcdef" for char in census_sha + obs_sha):
        raise ScientificEligibilityError(CANONICAL_RELEASE_IDENTITY_UNBOUND)
    return {
        "dataset_id": expected["dataset_id"],
        "cohort_id": expected["cohort_id"],
        "release_id": expected["release_id"],
        "census_sha256": census_sha,
        "observations_sha256": obs_sha,
    }


def _schedule_document_from_ops_store(
    data_root: Path, wanted: str
) -> dict[str, Any] | None:
    """Read-only lookup of the registered schedule on this data_root."""

    from solana_alpha_lab.factory.observation_schedule_lifecycle import (
        observation_ops_store_path,
    )
    from solana_alpha_lab.factory.observation_schedule_store import (
        ObservationScheduleStore,
        ObservationScheduleStoreError,
    )

    path = observation_ops_store_path(Path(data_root))
    try:
        store = ObservationScheduleStore(path, readonly=True)
    except ObservationScheduleStoreError:
        return None
    try:
        row = store.get_registered_schedule(wanted)
    finally:
        store._conn.close()
    if not isinstance(row, Mapping):
        return None
    document = row.get("document")
    if not isinstance(document, Mapping):
        return None
    return dict(document)


def bind_lineage_canonical_release(data_root: Path, *, repo_root: Path) -> Any:
    """Reuse canonical hash-bind machinery on lineage pins for the expected C1."""

    from solana_alpha_lab.factory.hfic_censoring_ignorability_diagnostic import (
        bind_canonical_censoring_inputs,
    )

    pins = lineage_canonical_corpus_pins(data_root, repo_root=repo_root)
    return bind_canonical_censoring_inputs(Path(data_root), pins)


def resolve_canonical_release_schedule(
    data_root: Path,
    census_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Load the release-bound schedule document. Never trust ExperimentSpec."""

    digests: list[str] = []
    seen: set[str] = set()
    for row in census_rows:
        if not isinstance(row, Mapping):
            continue
        digest = str(row.get("source_schedule_sha256") or row.get("schedule_sha256") or "")
        if len(digest) == 64 and digest not in seen:
            seen.add(digest)
            digests.append(digest)
    if len(digests) != 1:
        raise ScientificEligibilityError(CANONICAL_SCHEDULE_UNBOUND)
    wanted = digests[0]
    from solana_alpha_lab.factory.observation_schedule import (
        schedule_sha256 as hash_schedule,
    )
    from solana_alpha_lab.factory.research_store import (
        ExistingResearchStoreReader,
        ResearchStoreError,
    )

    documents: list[dict[str, Any]] = []
    encoded: set[str] = set()
    try:
        store = ExistingResearchStoreReader(Path(data_root))
    except ResearchStoreError:
        store = None
    if store is not None:
        for record in store.iter_committed_records():
            if str(getattr(record, "record_kind", "") or "") != "OBSERVATION_SCHEDULE":
                continue
            try:
                payload = json.loads(record.payload_json)
            except (TypeError, json.JSONDecodeError, AttributeError):
                continue
            if not isinstance(payload, Mapping):
                continue
            if str(payload.get("schedule_sha256") or "") != wanted:
                continue
            document = payload.get("schedule")
            if not isinstance(document, Mapping):
                continue
            as_dict = dict(document)
            marker = json.dumps(as_dict, sort_keys=True, separators=(",", ":"))
            if marker in encoded:
                continue
            encoded.add(marker)
            documents.append(as_dict)
    if len(documents) != 1:
        ops_document = _schedule_document_from_ops_store(Path(data_root), wanted)
        documents = [] if ops_document is None else [ops_document]
    if len(documents) != 1:
        raise ScientificEligibilityError(CANONICAL_SCHEDULE_UNBOUND)
    document = documents[0]
    if hash_schedule(document) != wanted:
        raise ScientificEligibilityError(CANONICAL_X300_SCHEDULE_INCOMPATIBLE)
    verify_factory_x300_schedule(document)
    return document


def project_scientific_eligibility(
    census_rows: Sequence[Mapping[str, Any]],
    observation_rows: Sequence[Mapping[str, Any]],
    *,
    spec: Mapping[str, Any] | None = None,
    schedule: Mapping[str, Any] | None = None,
    release_binding: Mapping[str, Any] | None = None,
    canonical_schedule: Mapping[str, Any] | None = None,
    require_canonical_schedule: bool = False,
    x_due_offset_seconds: int = X_DUE_OFFSET_SECONDS,
    x_allowed_lateness_seconds: int = X_ALLOWED_LATENESS_SECONDS,
) -> dict[str, Any]:
    """Project base_x, lifecycle coverage, and typed outcome readiness.

    Observation rows may carry only mint/point_id/field_id/state/clocks.
    Y ``typed_value`` is never read. ExperimentSpec ``schedule`` never
    widens factory X300 PIT. Canonical consume-time must pass the
    release-bound schedule and fail closed on geometry mismatch.
    """

    _ = schedule
    x_due_offset_seconds = X_DUE_OFFSET_SECONDS
    x_allowed_lateness_seconds = X_ALLOWED_LATENESS_SECONDS
    schedule_identity: dict[str, Any] | None = None
    if require_canonical_schedule or canonical_schedule is not None:
        schedule_identity = verify_factory_x300_schedule(canonical_schedule)

    census_by_mint: dict[str, Mapping[str, Any]] = {}
    for row in census_rows:
        if not isinstance(row, Mapping):
            continue
        mint = _mint(row)
        if mint and mint not in census_by_mint:
            census_by_mint[mint] = row

    x300_by_mint: dict[str, Mapping[str, Any]] = {}
    obs_index: dict[tuple[str, str, str], str] = {}
    obs_rank: dict[tuple[str, str, str], datetime] = {}
    for row in observation_rows:
        if not isinstance(row, Mapping):
            continue
        mint = _mint(row)
        point_id = str(row.get("point_id") or "")
        field_id = str(row.get("field_id") or "")
        if not mint or not point_id or not field_id:
            continue
        state = str(row.get("state") or "")
        key = (mint, point_id, field_id)
        rank = _available_at_rank(row)
        previous_rank = obs_rank.get(key)
        if previous_rank is None or rank >= previous_rank:
            obs_index[key] = state
            obs_rank[key] = rank
        if point_id == X_POINT_ID and field_id == X_FIELD_ID:
            census = census_by_mint.get(mint)
            if census is None:
                continue
            if not _x300_pit_ok(
                available_at=row.get("first_reliable_available_at"),
                anchor=census.get("authoritative_anchor"),
                due_offset_seconds=x_due_offset_seconds,
                allowed_lateness_seconds=x_allowed_lateness_seconds,
            ):
                continue
            previous = x300_by_mint.get(mint)
            if previous is None or rank >= _available_at_rank(previous):
                x300_by_mint[mint] = row

    base_mints: list[str] = []
    seen_mints: set[str] = set()
    lifecycle = {
        "n_observed": 0,
        "n_censored_late": 0,
        "n_typed_missing": 0,
        "n_other": 0,
    }
    for row in census_rows:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("candidate_state") or "") != "X_ELIGIBLE":
            continue
        mint = _mint(row)
        if not mint or mint in seen_mints:
            continue
        x300 = x300_by_mint.get(mint)
        if x300 is None:
            continue
        if str(x300.get("state") or "") != STATE_OBSERVED:
            continue
        if not _x300_pit_ok(
            available_at=x300.get("first_reliable_available_at"),
            anchor=row.get("authoritative_anchor"),
            due_offset_seconds=x_due_offset_seconds,
            allowed_lateness_seconds=x_allowed_lateness_seconds,
        ):
            continue
        seen_mints.add(mint)
        base_mints.append(mint)
        denom = str(row.get("denominator_state") or "")
        if denom == "observed":
            lifecycle["n_observed"] += 1
        elif denom == "censored_late":
            lifecycle["n_censored_late"] += 1
        elif denom == "typed_missing":
            lifecycle["n_typed_missing"] += 1
        else:
            lifecycle["n_other"] += 1

    base_mints = sorted(base_mints)
    required = required_outcomes_from_spec(spec)
    coverage: list[dict[str, Any]] = []
    unresolved = 0
    if spec is None or (
        isinstance(spec, Mapping) and spec.get("schema_version") not in {"1.3"}
        and not required
    ):
        readiness = READINESS_UNSPECIFIED
    elif not required:
        readiness = READINESS_UNSPECIFIED
    else:
        for item in required:
            n_observed = 0
            n_censored_late = 0
            n_typed_missing = 0
            n_absent = 0
            n_other = 0
            for mint in base_mints:
                state = obs_index.get((mint, item["point_id"], item["field_id"]))
                if state is None:
                    n_absent += 1
                    unresolved += 1
                    continue
                if state == STATE_OBSERVED:
                    n_observed += 1
                    continue
                unresolved += 1
                if state in {"CENSORED_LATE", "CENSORED"}:
                    n_censored_late += 1
                elif state == "MISSING_TYPED":
                    n_typed_missing += 1
                else:
                    n_other += 1
            coverage.append(
                {
                    "point_id": item["point_id"],
                    "field_id": item["field_id"],
                    "role": item["role"],
                    "n_observed": n_observed,
                    "n_censored_late": n_censored_late,
                    "n_typed_missing": n_typed_missing,
                    "n_absent": n_absent,
                    "n_other": n_other,
                    "denominator_n": len(base_mints),
                }
            )
        if not base_mints or unresolved:
            readiness = READINESS_MISSINGNESS_UNRESOLVED
        else:
            readiness = READINESS_COMPLETE

    member_ids_sha256 = hashlib.sha256(
        ("\n".join(base_mints)).encode("utf-8")
    ).hexdigest()
    payload = {
        "schema": PROJECTION_SCHEMA,
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "rule_id": RULE_ID,
        "release_binding": {
            **dict(release_binding or {}),
            **({} if schedule_identity is None else {"canonical_schedule": schedule_identity}),
        },
        "experiment_spec_sha256": (
            None
            if spec is None
            else canonical_sha256(dict(spec))
        ),
        "base_x_population": {
            "rule_id": RULE_ID,
            "n": len(base_mints),
            "member_ids_sha256": member_ids_sha256,
            "x_point_id": X_POINT_ID,
            "x_field_id": X_FIELD_ID,
            "x_due_offset_seconds": int(x_due_offset_seconds),
            "x_allowed_lateness_seconds": int(x_allowed_lateness_seconds),
        },
        "lifecycle_coverage": {
            "owner": "membership_state/denominator_state",
            **lifecycle,
            "denominator_n": len(base_mints),
        },
        "outcome_coverage": coverage,
        "outcome_readiness": readiness,
        "invariants": {
            "missing_y_never_shrinks_base_x": True,
            "no_complete_case_population": True,
            "no_y_typed_value_read": True,
        },
    }
    payload["projection_sha256"] = canonical_sha256(payload)
    return payload


def load_projection_tables(
    census_path: Path,
    observations_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load census + observation states. Never selects typed_value."""

    import duckdb

    census_columns = (
        "mint",
        "entity_id",
        "candidate_state",
        "denominator_state",
        "authoritative_anchor",
        "source_schedule_sha256",
        "schedule_sha256",
        "activation_id",
    )
    obs_columns = (
        "mint",
        "entity_id",
        "point_id",
        "field_id",
        "state",
        "first_reliable_available_at",
    )
    if not Path(census_path).is_file() or Path(census_path).is_symlink():
        raise ScientificEligibilityError("CENSUS_PARQUET_MISSING")
    if not Path(observations_path).is_file() or Path(observations_path).is_symlink():
        raise ScientificEligibilityError("OBSERVATIONS_PARQUET_MISSING")
    connection = duckdb.connect(database=":memory:")
    try:
        def _select(path: Path, wanted: Sequence[str]) -> list[dict[str, Any]]:
            described = connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)",
                [str(path)],
            ).fetchall()
            available = {str(item[0]) for item in described}
            if "typed_value" in available:
                available.discard("typed_value")
            selected = [name for name in wanted if name in available]
            if "mint" not in selected and "entity_id" not in selected:
                raise ScientificEligibilityError("PROJECTION_TABLE_SCHEMA_INVALID")
            quoted = ", ".join(f'"{name}"' for name in selected)
            relation = connection.execute(
                f"SELECT {quoted} FROM read_parquet(?)",
                [str(path)],
            )
            names = [item[0] for item in relation.description]
            return [dict(zip(names, row, strict=True)) for row in relation.fetchall()]

        return _select(Path(census_path), census_columns), _select(
            Path(observations_path), obs_columns
        )
    except ScientificEligibilityError:
        raise
    except Exception as exc:
        raise ScientificEligibilityError("PROJECTION_TABLE_UNREADABLE") from exc
    finally:
        connection.close()


def try_project_scientific_eligibility_from_data_root(
    data_root: Path,
    *,
    repo_root: Path,
    spec: Mapping[str, Any] | None = None,
    schedule: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Consume-time projection over the bound canonical release.

    Unbound identity (this data_root is not the expected C1) returns None.
    Bound identity with unproven or incompatible X300 geometry raises a typed
    error instead of silently applying factory 300+300.
    """

    try:
        pins = lineage_canonical_corpus_pins(
            Path(data_root), repo_root=Path(repo_root)
        )
    except ScientificEligibilityError as exc:
        if exc.code == CANONICAL_RELEASE_IDENTITY_UNBOUND:
            return None
        raise
    from solana_alpha_lab.factory.hfic_censoring_ignorability_diagnostic import (
        bind_canonical_censoring_inputs,
    )

    try:
        binding = bind_canonical_censoring_inputs(Path(data_root), pins)
    except ScientificEligibilityError:
        raise
    except Exception as exc:
        code = getattr(exc, "code", None)
        raise ScientificEligibilityError(
            str(code)
            if isinstance(code, str) and code
            else CANONICAL_RELEASE_BIND_FAILED
        ) from exc
    try:
        census_rows, observation_rows = load_projection_tables(
            binding.census_path,
            binding.observations_path,
        )
        canonical_schedule = resolve_canonical_release_schedule(
            Path(data_root),
            census_rows,
        )
        return project_scientific_eligibility(
            census_rows,
            observation_rows,
            spec=spec,
            schedule=schedule,
            canonical_schedule=canonical_schedule,
            require_canonical_schedule=True,
            release_binding={
                "release_id": binding.release_id,
                "cohort_id": binding.cohort_id,
                "dataset_id": binding.dataset_id,
                "dataset_manifest_id": binding.dataset_manifest_id,
                "census_sha256": binding.census_sha256,
                "observations_sha256": binding.observations_sha256,
            },
        )
    except ScientificEligibilityError:
        raise
    except Exception as exc:
        raise ScientificEligibilityError("PROJECTION_TABLE_UNREADABLE") from exc


def _projection_structurally_valid(projection: Mapping[str, Any]) -> bool:
    required = (
        "schema",
        "schema_version",
        "rule_id",
        "base_x_population",
        "lifecycle_coverage",
        "outcome_coverage",
        "outcome_readiness",
        "invariants",
        "projection_sha256",
    )
    if any(key not in projection for key in required):
        return False
    invariants = projection.get("invariants")
    population = projection.get("base_x_population")
    lifecycle = projection.get("lifecycle_coverage")
    coverage = projection.get("outcome_coverage")
    if not isinstance(invariants, Mapping):
        return False
    if invariants.get("missing_y_never_shrinks_base_x") is not True:
        return False
    if invariants.get("no_complete_case_population") is not True:
        return False
    if invariants.get("no_y_typed_value_read") is not True:
        return False
    if not isinstance(population, Mapping) or not isinstance(lifecycle, Mapping):
        return False
    if not isinstance(coverage, list):
        return False
    try:
        n = int(population["n"])
        denom = int(lifecycle["denominator_n"])
    except (KeyError, TypeError, ValueError):
        return False
    return n == denom and n >= 0


def validated_projection_readiness(
    spec: Mapping[str, Any],
    projection: Mapping[str, Any] | None,
) -> str:
    """Accept COMPLETE only from a structurally valid spec-bound projection."""

    if spec.get("schema_version") != "1.3":
        return READINESS_UNSPECIFIED
    if not isinstance(projection, Mapping):
        return READINESS_MISSINGNESS_UNRESOLVED
    if (
        projection.get("schema") != PROJECTION_SCHEMA
        or projection.get("schema_version") != PROJECTION_SCHEMA_VERSION
        or projection.get("rule_id") != RULE_ID
    ):
        return READINESS_MISSINGNESS_UNRESOLVED
    if not _projection_structurally_valid(projection):
        return READINESS_MISSINGNESS_UNRESOLVED
    population = projection.get("base_x_population")
    if isinstance(population, Mapping):
        try:
            due = population.get("x_due_offset_seconds", X_DUE_OFFSET_SECONDS)
            late = population.get("x_allowed_lateness_seconds", X_ALLOWED_LATENESS_SECONDS)
            if int(due) != X_DUE_OFFSET_SECONDS or int(late) != X_ALLOWED_LATENESS_SECONDS:
                return READINESS_MISSINGNESS_UNRESOLVED
        except (TypeError, ValueError):
            return READINESS_MISSINGNESS_UNRESOLVED
    body = {key: value for key, value in projection.items() if key != "projection_sha256"}
    if projection.get("projection_sha256") != canonical_sha256(body):
        return READINESS_MISSINGNESS_UNRESOLVED
    expected = canonical_sha256(dict(spec))
    if projection.get("experiment_spec_sha256") != expected:
        return READINESS_MISSINGNESS_UNRESOLVED
    readiness = projection.get("outcome_readiness")
    if readiness not in {
        READINESS_COMPLETE,
        READINESS_MISSINGNESS_UNRESOLVED,
        READINESS_UNSPECIFIED,
    }:
        return READINESS_MISSINGNESS_UNRESOLVED
    if readiness == READINESS_COMPLETE:
        try:
            n = int(projection["base_x_population"]["n"])
        except (KeyError, TypeError, ValueError):
            return READINESS_MISSINGNESS_UNRESOLVED
        if n < 1:
            return READINESS_MISSINGNESS_UNRESOLVED
    return str(readiness)


def y_columns_forbidden(row: Mapping[str, Any]) -> None:
    """Guard test/helpers: Y typed values must not enter the working set."""

    point_id = str(row.get("point_id") or "")
    if point_id.startswith(Y_POINT_PREFIX) and "typed_value" in row:
        raise ScientificEligibilityError("Y_TYPED_VALUE_READ")


def assert_c1_shape(projection: Mapping[str, Any]) -> None:
    base_n = int(projection["base_x_population"]["n"])
    life = projection["lifecycle_coverage"]
    if (
        base_n != C1_EXPECTED["base_x_n"]
        or int(life["n_observed"]) != C1_EXPECTED["lifecycle_observed_n"]
        or int(life["n_censored_late"]) != C1_EXPECTED["lifecycle_censored_late_n"]
    ):
        raise ScientificEligibilityError("C1_SHAPE_MISMATCH")
    if base_n != int(life["denominator_n"]):
        raise ScientificEligibilityError("BASE_X_LIFECYCLE_DENOMINATOR_DRIFT")


__all__ = [
    "C1_EXPECTED",
    "CANONICAL_RELEASE_BIND_FAILED",
    "CANONICAL_RELEASE_IDENTITY_UNBOUND",
    "CANONICAL_SCHEDULE_UNBOUND",
    "CANONICAL_X300_SCHEDULE_INCOMPATIBLE",
    "ELIGIBILITY_SCOPE_BASE_X",
    "ELIGIBILITY_SCOPE_FULL_LIFECYCLE",
    "MIN_USABLE_BASE_X_POPULATION",
    "READINESS_COMPLETE",
    "READINESS_MISSINGNESS_UNRESOLVED",
    "READINESS_UNSPECIFIED",
    "RULE_ID",
    "SPEC_RELATIVE",
    "ScientificEligibilityError",
    "X_ALLOWED_LATENESS_SECONDS",
    "X_DUE_OFFSET_SECONDS",
    "X_FIELD_ID",
    "X_POINT_ID",
    "assert_c1_shape",
    "bind_lineage_canonical_release",
    "bound_schedule_y_point_ids",
    "canonical_c1_identity",
    "full_lifecycle_scope_equivalent",
    "lineage_canonical_corpus_pins",
    "load_projection_spec",
    "load_projection_tables",
    "project_scientific_eligibility",
    "required_outcome_point_ids",
    "required_outcomes_from_spec",
    "resolve_canonical_release_schedule",
    "sanitize_projection_row",
    "schedule_y_point_ids",
    "try_project_scientific_eligibility_from_data_root",
    "validated_projection_readiness",
    "verify_factory_x300_schedule",
    "y_columns_forbidden",
]
