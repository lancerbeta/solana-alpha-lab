"""Deterministic scoring and DuckDB adapters for prior research memory."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb


MAX_RESULTS = 50
STATE_BY_DECISION = {
    "REJECT": "REJECTED",
    "REVISE": "REVISION_REQUIRED",
    "PROMOTE": "PROMOTED",
    "PAUSE": "PAUSED",
    "MARK_DORMANT": "DORMANT",
    "RETIRE": "RETIRED",
    "REACTIVATE": "REACTIVATED",
}
QUERY_PREDICATES = frozenset(
    {
        "hypothesis_version_ids",
        "hypothesis_definition_sha256s",
        "mechanism_terms",
        "falsifier_terms",
        "regime_terms",
        "origin_kinds",
        "dataset_artifact_ids",
        "dataset_manifest_ids",
        "dataset_fingerprints",
        "tool_capability_ids",
        "capability_ids",
        "query_recipe_ids",
        "trial_outcomes",
        "scientific_terminals",
        "decision_kinds",
        "what_changed_terms",
    }
)
_UTC_TIMESTAMP = re.compile(
    r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
_HASH64 = re.compile(r"^[0-9a-f]{64}$")


class PriorWorkError(ValueError):
    """Fail-closed prior-work query or cross-plane contract violation."""


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        raise PriorWorkError("QUERY_AS_OF_INVALID")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise PriorWorkError("QUERY_AS_OF_INVALID") from exc
    return parsed.astimezone(UTC)


def normalize_terms(values: Iterable[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        tokens.update(token for token in re.split(r"[^\w]+", value.casefold()) if token)
    return tokens


def _string_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {value}
        if isinstance(decoded, list):
            return {item for item in decoded if isinstance(item, str)}
        return {value}
    if isinstance(value, (list, tuple, set, frozenset)):
        return {item for item in value if isinstance(item, str)}
    return set()


def _validate_string_list(name: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise PriorWorkError(f"QUERY_PREDICATE_VALUES_INVALID:{name}")
    return value


def validate_prior_work_query(query: Mapping[str, Any]) -> datetime:
    if not isinstance(query, Mapping):
        raise PriorWorkError("QUERY_NOT_OBJECT")
    if set(query) != {"query_id", "as_of", "max_results", "predicates"}:
        raise PriorWorkError("QUERY_FIELDS_INVALID")
    if not isinstance(query["query_id"], str) or not query["query_id"]:
        raise PriorWorkError("QUERY_ID_INVALID")
    cutoff = parse_timestamp(query["as_of"])
    max_results = query["max_results"]
    if (
        not isinstance(max_results, int)
        or isinstance(max_results, bool)
        or not 1 <= max_results <= MAX_RESULTS
    ):
        raise PriorWorkError("QUERY_MAX_RESULTS_OUT_OF_BOUNDS")
    predicates = query["predicates"]
    if not isinstance(predicates, Mapping):
        raise PriorWorkError("QUERY_PREDICATES_NOT_OBJECT")
    unknown = set(predicates) - QUERY_PREDICATES
    if unknown:
        raise PriorWorkError(f"QUERY_PREDICATES_UNKNOWN:{sorted(unknown)}")
    if not predicates or not any(predicates.values()):
        raise PriorWorkError("QUERY_PREDICATES_EMPTY")
    for name, values in predicates.items():
        _validate_string_list(name, values)
    for value in predicates.get("hypothesis_definition_sha256s", []):
        if _HASH64.fullmatch(value) is None:
            raise PriorWorkError("QUERY_DEFINITION_HASH_INVALID")
    return cutoff


def score_prior_work_candidate(
    candidate: Mapping[str, Any],
    predicates: Mapping[str, Sequence[str]],
) -> tuple[int, list[str]]:
    """Apply frozen T16 weights and return stable reason labels."""

    score = 0
    matched_by: set[str] = set()

    if candidate.get("hypothesis_version_id") in set(
        predicates.get("hypothesis_version_ids", ())
    ):
        score += 100
        matched_by.add("EXACT_HYPOTHESIS_VERSION")
    if candidate.get("definition_sha256") in set(
        predicates.get("hypothesis_definition_sha256s", ())
    ):
        score += 100
        matched_by.add("EXACT_DEFINITION_HASH")

    term_specs = (
        (
            "mechanism_terms",
            [candidate.get("mechanism", ""), candidate.get("statement", "")],
            "MECHANISM_TERM",
        ),
        (
            "falsifier_terms",
            [candidate.get("falsifier", "")],
            "FALSIFIER_TERM",
        ),
        (
            "regime_terms",
            sorted(_string_set(candidate.get("regime_terms"))),
            "REGIME_TERM",
        ),
        (
            "what_changed_terms",
            [candidate.get("what_changed", "")],
            "WHAT_CHANGED",
        ),
    )
    for predicate, values, reason in term_specs:
        requested = normalize_terms(predicates.get(predicate, ()))
        overlap = requested & normalize_terms(
            value for value in values if isinstance(value, str)
        )
        if overlap:
            score += 5 * len(overlap)
            matched_by.add(reason)

    set_specs = (
        ("origin_kinds", "origin_kinds", "ORIGIN_KIND", 20),
        (
            "dataset_artifact_ids",
            "dataset_artifact_ids",
            "DATASET_ARTIFACT",
            40,
        ),
        (
            "dataset_manifest_ids",
            "dataset_manifest_ids",
            "DATASET_MANIFEST",
            40,
        ),
        (
            "dataset_fingerprints",
            "dataset_fingerprints",
            "DATASET_FINGERPRINT",
            40,
        ),
        (
            "tool_capability_ids",
            "capability_ids",
            "TOOL_CAPABILITY",
            40,
        ),
        ("capability_ids", "capability_ids", "CAPABILITY", 40),
        ("query_recipe_ids", "query_recipe_ids", "QUERY_RECIPE", 40),
        ("trial_outcomes", "trial_outcomes", "TRIAL_OUTCOME", 20),
        (
            "scientific_terminals",
            "scientific_terminals",
            "SCIENTIFIC_TERMINAL",
            20,
        ),
        ("decision_kinds", "decision_kinds", "DECISION_KIND", 20),
    )
    for predicate, field, reason, weight in set_specs:
        overlap = set(predicates.get(predicate, ())) & _string_set(candidate.get(field))
        if overlap:
            score += weight * len(overlap)
            matched_by.add(reason)
    return score, sorted(matched_by)


def legacy_outcome_semantics(label: str) -> dict[str, str | None]:
    if label in {"POSITIVE", "NEGATIVE", "INCONCLUSIVE", "INVALID"}:
        return {
            "legacy_outcome": label,
            "trial_outcome": label,
            "diagnostic": None,
        }
    return {
        "legacy_outcome": label,
        "trial_outcome": None,
        "diagnostic": "LEGACY_OUTCOME_UNRESOLVED",
    }


def _connect_readonly(path: Path) -> duckdb.DuckDBPyConnection:
    if not isinstance(path, Path) or path.suffix.lower() != ".duckdb":
        raise PriorWorkError("PROJECTION_PATH_INVALID")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PriorWorkError("PROJECTION_NOT_FOUND") from exc
    connection = duckdb.connect(
        str(resolved),
        read_only=True,
        config={
            "enable_external_access": "false",
            "allow_unsigned_extensions": "false",
        },
    )
    connection.execute("SET TimeZone = 'UTC'")
    connection.execute("SET lock_configuration = true")
    return connection


def _rows(
    connection: duckdb.DuckDBPyConnection,
    sql: str,
    parameters: Sequence[Any],
) -> list[dict[str, Any]]:
    cursor = connection.execute(sql, list(parameters))
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _timestamp_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _eligible_rows(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    cutoff: datetime,
    *,
    order_by: str,
) -> list[dict[str, Any]]:
    allowed = {
        "prior_work",
        "experiment_runs",
        "hypothesis_events",
        "evidence_bindings",
        "capability_gaps",
    }
    if relation not in allowed:
        raise PriorWorkError("RELATION_NOT_ALLOWED")
    return _rows(
        connection,
        f"""
        SELECT *
        FROM "{relation}"
        WHERE first_reliable_available_at <= ?
        ORDER BY {order_by}
        """,
        [cutoff.replace(tzinfo=None)],
    )


def _derived_state(
    hypothesis_version_id: str,
    *,
    decisions: Sequence[Mapping[str, Any]],
    runs: Sequence[Mapping[str, Any]],
) -> str:
    eligible_decisions = [
        row
        for row in decisions
        if row.get("hypothesis_version_id") == hypothesis_version_id
        and row.get("decision_kind") in STATE_BY_DECISION
    ]
    if eligible_decisions:
        latest = max(
            eligible_decisions,
            key=lambda row: (
                row["effective_at"],
                row["first_reliable_available_at"],
                row["hypothesis_event_id"],
            ),
        )
        return STATE_BY_DECISION[str(latest["decision_kind"])]
    eligible_runs = [
        row
        for row in runs
        if row.get("hypothesis_version_id") == hypothesis_version_id
        and row.get("scientific_terminal")
        and row.get("run_event_kind") in {"RUN_COMPLETED", "RUN_INVALID"}
    ]
    if eligible_runs:
        latest = max(
            eligible_runs,
            key=lambda row: (
                row["effective_at"],
                row["first_reliable_available_at"],
                row["record_id"],
            ),
        )
        return str(latest["scientific_terminal"])
    return "NO_DECISION"


def query_hypotheses(
    projection_path: Path,
    as_of: str,
) -> list[dict[str, Any]]:
    cutoff = parse_timestamp(as_of)
    connection = _connect_readonly(projection_path)
    try:
        hypotheses = _eligible_rows(
            connection,
            "prior_work",
            cutoff,
            order_by="hypothesis_version_id, record_id",
        )
        runs = _eligible_rows(
            connection,
            "experiment_runs",
            cutoff,
            order_by=("effective_at, first_reliable_available_at, record_id"),
        )
        decisions = _eligible_rows(
            connection,
            "hypothesis_events",
            cutoff,
            order_by=("effective_at, first_reliable_available_at, hypothesis_event_id"),
        )
    except duckdb.Error as exc:
        raise PriorWorkError("PROJECTION_QUERY_FAILED") from exc
    finally:
        connection.close()
    return [
        {
            **row,
            "effective_at": _timestamp_text(row["effective_at"]),
            "first_reliable_available_at": _timestamp_text(
                row["first_reliable_available_at"]
            ),
            "derived_state": _derived_state(
                row["hypothesis_version_id"],
                decisions=decisions,
                runs=runs,
            ),
        }
        for row in hypotheses
    ]


def query_data_plane_prior_work(
    projection_path: Path,
    query: Mapping[str, Any],
) -> dict[str, Any]:
    cutoff = validate_prior_work_query(query)
    connection = _connect_readonly(projection_path)
    try:
        hypotheses = _eligible_rows(
            connection,
            "prior_work",
            cutoff,
            order_by="hypothesis_version_id, record_id",
        )
        runs = _eligible_rows(
            connection,
            "experiment_runs",
            cutoff,
            order_by="run_id, record_id",
        )
        events = _eligible_rows(
            connection,
            "hypothesis_events",
            cutoff,
            order_by="hypothesis_event_id",
        )
        evidence = _eligible_rows(
            connection,
            "evidence_bindings",
            cutoff,
            order_by="evidence_binding_id",
        )
        gaps = _eligible_rows(
            connection,
            "capability_gaps",
            cutoff,
            order_by="capability_gap_id",
        )
        metadata = _rows(
            connection,
            """
            SELECT projection_digest_sha256
            FROM _projection_metadata
            WHERE singleton = TRUE
            """,
            [],
        )
    except duckdb.Error as exc:
        raise PriorWorkError("PROJECTION_QUERY_FAILED") from exc
    finally:
        connection.close()

    predicates = query["predicates"]
    results: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        version_id = hypothesis["hypothesis_version_id"]
        related_runs = [
            row for row in runs if row["hypothesis_version_id"] == version_id
        ]
        related_events = [
            row for row in events if row["hypothesis_version_id"] == version_id
        ]
        related_evidence = [
            row
            for row in evidence
            if row["hypothesis_version_id"] == version_id
            or any(row["run_id"] == run["run_id"] for run in related_runs)
        ]
        related_gaps = [
            row for row in gaps if row["hypothesis_version_id"] == version_id
        ]
        candidate = {
            **hypothesis,
            "regime_terms": hypothesis.get("regime_terms"),
            "origin_kinds": _string_set(hypothesis.get("origin_kind")),
            "dataset_artifact_ids": set(),
            "dataset_manifest_ids": {
                item
                for run in related_runs
                for item in _string_set(run.get("dataset_manifest_ids"))
            },
            "dataset_fingerprints": {
                item
                for run in related_runs
                for item in _string_set(run.get("dataset_fingerprints"))
            },
            "capability_ids": {
                item
                for run in related_runs
                for item in _string_set(run.get("runner_capability_id"))
            }
            | {
                item
                for gap in related_gaps
                for item in _string_set(gap.get("capability_id"))
            },
            "query_recipe_ids": {
                item
                for run in related_runs
                for item in _string_set(run.get("query_recipe_ids"))
            },
            "trial_outcomes": {
                item
                for run in related_runs
                for item in _string_set(run.get("trial_outcome"))
            },
            "scientific_terminals": {
                item
                for run in related_runs
                for item in _string_set(run.get("scientific_terminal"))
            },
            "decision_kinds": {
                item
                for event in related_events
                for item in _string_set(event.get("decision_kind"))
            },
        }
        score, matched_by = score_prior_work_candidate(candidate, predicates)
        if not matched_by:
            continue
        results.append(
            {
                "hypothesis_version_id": version_id,
                "family_id": hypothesis.get("family_id"),
                "definition_sha256": hypothesis.get("definition_sha256"),
                "score": score,
                "matched_by": matched_by,
                "run_ids": sorted(
                    {str(row["run_id"]) for row in related_runs if row.get("run_id")}
                ),
                "trial_outcomes": sorted(candidate["trial_outcomes"]),
                "scientific_terminals": sorted(candidate["scientific_terminals"]),
                "decision_kinds": sorted(candidate["decision_kinds"]),
                "decision_event_ids": sorted(
                    str(row["hypothesis_event_id"])
                    for row in related_events
                    if row.get("decision_kind")
                ),
                "evidence_binding_ids": sorted(
                    str(row["evidence_binding_id"]) for row in related_evidence
                ),
                "evidence_content_sha256": sorted(
                    {
                        str(row["content_sha256"])
                        for row in related_evidence
                        if row.get("content_sha256")
                    }
                ),
                "capability_gap_ids": sorted(
                    str(row["capability_gap_id"]) for row in related_gaps
                ),
                "current_state_as_of": _derived_state(
                    version_id,
                    decisions=related_events,
                    runs=related_runs,
                ),
                "what_changed": hypothesis.get("what_changed"),
                "repeat_or_extension_requires_what_changed": True,
                "source_plane": "DATA_PLANE",
            }
        )
    ordered = sorted(
        results,
        key=lambda row: (-row["score"], row["hypothesis_version_id"]),
    )[: int(query["max_results"])]
    digest = metadata[0]["projection_digest_sha256"] if metadata else None
    return {
        "schema": "smial.prior_work_query_result.v1",
        "query_id": query["query_id"],
        "as_of": query["as_of"],
        "memory_id": "RESEARCH_DATA_PLANE_V1",
        "memory_content_sha256": digest,
        "result_count": len(ordered),
        "results": ordered,
        "automatic_reject_or_promotion": False,
    }


def _result_hash(row: Mapping[str, Any]) -> str | None:
    for name in (
        "definition_sha256",
        "payload_sha256",
        "content_sha256",
    ):
        value = row.get(name)
        if isinstance(value, str) and _HASH64.fullmatch(value):
            return value
    return None


def merge_plane_results(
    legacy: Mapping[str, Any],
    data_plane: Mapping[str, Any],
    *,
    max_results: int,
) -> dict[str, Any]:
    if (
        not isinstance(max_results, int)
        or isinstance(max_results, bool)
        or not 1 <= max_results <= MAX_RESULTS
    ):
        raise PriorWorkError("QUERY_MAX_RESULTS_OUT_OF_BOUNDS")
    indexed: dict[str, dict[str, Any]] = {}
    for plane, packet in (("LEGACY", legacy), ("DATA_PLANE", data_plane)):
        rows = packet.get("results")
        if not isinstance(rows, list):
            raise PriorWorkError("PLANE_RESULTS_INVALID")
        for raw in rows:
            if not isinstance(raw, Mapping):
                raise PriorWorkError("PLANE_RESULT_INVALID")
            stable_id = raw.get("hypothesis_version_id")
            if not isinstance(stable_id, str) or not stable_id:
                raise PriorWorkError("PLANE_STABLE_ID_MISSING")
            row = dict(raw)
            row.setdefault("source_plane", plane)
            previous = indexed.get(stable_id)
            if previous is not None:
                previous_hash = _result_hash(previous)
                row_hash = _result_hash(row)
                if (
                    previous_hash is None
                    or row_hash is None
                    or previous_hash != row_hash
                ):
                    raise PriorWorkError(f"CROSS_PLANE_ID_CONFLICT:{stable_id}")
                combined_planes = sorted(
                    _string_set(previous.get("source_planes"))
                    | _string_set(previous.get("source_plane"))
                    | {plane}
                )
                previous["source_planes"] = combined_planes
                previous["matched_by"] = sorted(
                    _string_set(previous.get("matched_by"))
                    | _string_set(row.get("matched_by"))
                )
                previous["score"] = max(
                    int(previous.get("score", 0)),
                    int(row.get("score", 0)),
                )
                continue
            indexed[stable_id] = row
    ordered = sorted(
        indexed.values(),
        key=lambda row: (
            -int(row.get("score", 0)),
            str(row["hypothesis_version_id"]),
        ),
    )[:max_results]
    canonical = json.dumps(
        ordered,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "schema": "smial.prior_work_union_result.v1",
        "result_count": len(ordered),
        "results": ordered,
        "union_content_sha256": hashlib.sha256(canonical).hexdigest(),
        "automatic_reject_or_promotion": False,
    }


__all__ = [
    "MAX_RESULTS",
    "PriorWorkError",
    "legacy_outcome_semantics",
    "merge_plane_results",
    "normalize_terms",
    "query_data_plane_prior_work",
    "query_hypotheses",
    "score_prior_work_candidate",
    "validate_prior_work_query",
]
