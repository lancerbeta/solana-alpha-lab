from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "hypothesis_lifecycle_research_memory.schema.json"
)

RECORD_SPECS = (
    ("hypothesis_families", "family_id"),
    ("hypothesis_origins", "origin_id"),
    ("research_cycles", "research_cycle_id"),
    ("hypothesis_versions", "hypothesis_version_id"),
    ("research_artifacts", "research_artifact_id"),
    ("trials", "trial_id"),
    ("decision_events", "decision_event_id"),
    ("derivation_edges", "derivation_edge_id"),
    ("activation_epochs", "activation_epoch_id"),
)

QUERY_PREDICATES = {
    "hypothesis_version_ids",
    "mechanism_terms",
    "falsifier_terms",
    "regime_terms",
    "origin_kinds",
    "dataset_artifact_ids",
    "tool_capability_ids",
    "trial_outcomes",
    "decision_kinds",
}

STATE_BY_DECISION = {
    "REJECT": "REJECTED",
    "REVISE": "REVISION_REQUIRED",
    "PROMOTE": "PROMOTED",
    "PAUSE": "PAUSED",
    "MARK_DORMANT": "DORMANT",
    "RETIRE": "RETIRED",
    "REACTIVATE": "REACTIVATED",
}
ORIGIN_KINDS = {
    "OWNER_OBSERVATION",
    "DATA_ANALYSIS",
    "AI_ASSISTED_EXPLORATION",
    "EXTERNAL_RESEARCH",
    "TOOL_OR_FRAMEWORK",
    "DERIVED_FROM_EXISTING_HYPOTHESIS",
}
TRIAL_OUTCOMES = {"POSITIVE", "NEGATIVE", "INCONCLUSIVE", "INVALID"}
DECISION_KINDS = {
    "REJECT",
    "REVISE",
    "PROMOTE",
    "PAUSE",
    "MARK_DORMANT",
    "RETIRE",
    "REACTIVATE",
    "CLOSE_RESEARCH_CYCLE",
    "REOPEN_RESEARCH_CYCLE",
}
UTC_TIMESTAMP_PATTERN = re.compile(
    r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
STABLE_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
HYPOTHESIS_VERSION_ID_PATTERN = re.compile(
    r"^HYP-VERSION-[A-Z0-9]+(?:-[A-Z0-9]+)*-V[1-9][0-9]*$"
)
RESEARCH_ARTIFACT_ID_PATTERN = re.compile(
    r"^RESEARCH-ARTIFACT-[A-Z0-9]+(?:-[A-Z0-9]+)*$"
)


class MemoryValidationError(ValueError):
    pass


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_definition_payload(record: dict[str, Any]) -> dict[str, Any]:
    required = (
        "family_id",
        "version_ordinal",
        "research_cycle_id",
        "origin_id",
        "statement",
        "mechanism",
        "falsifier",
        "expected_regime_terms",
        "feature_definition_asset_ids",
        "label_definition_asset_ids",
        "named_consumer_ids",
    )
    optional = (
        "data_requirement_asset_id",
        "supersedes_hypothesis_version_id",
    )
    payload: dict[str, Any] = {}
    for key in (*required, *optional):
        if key not in record:
            continue
        value = record[key]
        payload[key] = sorted(value) if isinstance(value, list) else value
    return payload


def canonical_definition_sha256(record: dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(canonical_definition_payload(record))
    ).hexdigest()


def load_schema() -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise MemoryValidationError(f"memory_json_duplicate_key:{key}")
        document[key] = value
    return document


def _reject_json_constant(value: str) -> None:
    raise MemoryValidationError(f"memory_json_nonfinite_number:{value}")


def load_memory(path: Path) -> tuple[dict[str, Any], str]:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise MemoryValidationError(
            f"memory_path_outside_repository:{path}"
        ) from exc
    if not resolved.is_file():
        raise MemoryValidationError(f"memory_path_not_file:{path}")
    candidate = resolved.read_bytes()
    try:
        document = json.loads(
            candidate.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_json_constant,
        )
    except UnicodeDecodeError as exc:
        raise MemoryValidationError(
            f"memory_not_utf8:offset={exc.start}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise MemoryValidationError(
            f"memory_json_invalid:{exc.msg}:line={exc.lineno}:column={exc.colno}"
        ) from exc
    return document, hashlib.sha256(candidate).hexdigest()


def index_records(
    document: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    records: dict[str, dict[str, Any]] = {}
    kinds: dict[str, str] = {}
    for collection, id_field in RECORD_SPECS:
        for record in document[collection]:
            record_id = record[id_field]
            if record_id in records:
                raise MemoryValidationError(
                    f"duplicate_record_id:{record_id}:"
                    f"first={kinds[record_id]}:second={collection}"
                )
            records[record_id] = record
            kinds[record_id] = collection
    return records, kinds


def require_reference(
    records: dict[str, dict[str, Any]],
    expected_ids: set[str],
    source_id: str,
    field: str,
    target_id: str,
) -> None:
    if target_id not in expected_ids:
        raise MemoryValidationError(
            f"missing_reference:{source_id}:{field}:{target_id}"
        )
    if target_id not in records:
        raise MemoryValidationError(
            f"missing_global_reference:{source_id}:{field}:{target_id}"
        )


def require_references(
    records: dict[str, dict[str, Any]],
    expected_ids: set[str],
    source_id: str,
    field: str,
    target_ids: Iterable[str],
) -> None:
    for target_id in target_ids:
        require_reference(
            records,
            expected_ids,
            source_id,
            field,
            target_id,
        )


def _validate_no_derivation_cycles(
    derivation_edges: list[dict[str, Any]],
) -> None:
    graph: dict[str, set[str]] = defaultdict(set)
    for edge in derivation_edges:
        child = edge["child_hypothesis_version_id"]
        for parent in edge["parent_hypothesis_version_ids"]:
            if parent == child:
                raise MemoryValidationError(
                    f"derivation_self_reference:{edge['derivation_edge_id']}"
                )
            graph[parent].add(child)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise MemoryValidationError(f"derivation_cycle:{node}")
        if node in visited:
            return
        visiting.add(node)
        for child in sorted(graph.get(node, ())):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)


def validate_memory(document: dict[str, Any]) -> None:
    validator = Draft202012Validator(load_schema())
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        path = "/".join(str(part) for part in first.absolute_path) or "$"
        raise MemoryValidationError(
            f"memory_schema_invalid:{path}:{first.message}"
        )

    records, _ = index_records(document)
    snapshot_as_of = parse_timestamp(document["as_of"])
    for collection, id_field in RECORD_SPECS:
        for record in document[collection]:
            available_at = record.get("first_reliable_available_at")
            if available_at and parse_timestamp(available_at) > snapshot_as_of:
                raise MemoryValidationError(
                    f"record_after_snapshot:{record[id_field]}:{available_at}"
                )

    families = {
        record["family_id"]: record
        for record in document["hypothesis_families"]
    }
    origins = {
        record["origin_id"]: record
        for record in document["hypothesis_origins"]
    }
    cycles = {
        record["research_cycle_id"]: record
        for record in document["research_cycles"]
    }
    versions = {
        record["hypothesis_version_id"]: record
        for record in document["hypothesis_versions"]
    }
    artifacts = {
        record["research_artifact_id"]: record
        for record in document["research_artifacts"]
    }
    trials = {
        record["trial_id"]: record for record in document["trials"]
    }
    decisions = {
        record["decision_event_id"]: record
        for record in document["decision_events"]
    }
    epochs = {
        record["activation_epoch_id"]: record
        for record in document["activation_epochs"]
    }

    family_ids = set(families)
    origin_ids = set(origins)
    cycle_ids = set(cycles)
    version_ids = set(versions)
    artifact_ids = set(artifacts)
    trial_ids = set(trials)
    decision_ids = set(decisions)
    epoch_ids = set(epochs)

    for family_id, family in families.items():
        if parse_timestamp(family["created_at"]) > parse_timestamp(
            family["first_reliable_available_at"]
        ):
            raise MemoryValidationError(
                f"family_available_before_created:{family_id}"
            )

    versions_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for version_id, version in versions.items():
        require_reference(
            records,
            family_ids,
            version_id,
            "family_id",
            version["family_id"],
        )
        require_reference(
            records,
            cycle_ids,
            version_id,
            "research_cycle_id",
            version["research_cycle_id"],
        )
        require_reference(
            records,
            origin_ids,
            version_id,
            "origin_id",
            version["origin_id"],
        )
        suffix = re.search(r"-V([1-9][0-9]*)$", version_id)
        if suffix is None or int(suffix.group(1)) != version["version_ordinal"]:
            raise MemoryValidationError(
                f"hypothesis_version_ordinal_mismatch:{version_id}"
            )
        if canonical_definition_sha256(version) != version["definition_sha256"]:
            raise MemoryValidationError(
                f"hypothesis_definition_sha256_mismatch:{version_id}"
            )
        if origins[version["origin_id"]]["hypothesis_version_id"] != version_id:
            raise MemoryValidationError(
                f"hypothesis_origin_backreference_mismatch:{version_id}"
            )
        if version_id not in cycles[version["research_cycle_id"]][
            "hypothesis_version_ids"
        ]:
            raise MemoryValidationError(
                f"hypothesis_cycle_backreference_missing:{version_id}"
            )
        if parse_timestamp(version["created_at"]) > parse_timestamp(
            version["first_reliable_available_at"]
        ):
            raise MemoryValidationError(
                f"hypothesis_available_before_created:{version_id}"
            )
        supersedes = version.get("supersedes_hypothesis_version_id")
        if supersedes:
            require_reference(
                records,
                version_ids,
                version_id,
                "supersedes_hypothesis_version_id",
                supersedes,
            )
            if supersedes == version_id:
                raise MemoryValidationError(
                    f"hypothesis_version_self_supersession:{version_id}"
                )
            previous = versions[supersedes]
            if previous["family_id"] != version["family_id"]:
                raise MemoryValidationError(
                    f"hypothesis_version_cross_family_supersession:{version_id}"
                )
            if previous["version_ordinal"] >= version["version_ordinal"]:
                raise MemoryValidationError(
                    f"hypothesis_version_non_forward_supersession:{version_id}"
                )
        versions_by_family[version["family_id"]].append(version)

    for family_id, family_versions in versions_by_family.items():
        ordinals = [row["version_ordinal"] for row in family_versions]
        if len(ordinals) != len(set(ordinals)):
            raise MemoryValidationError(
                f"hypothesis_version_ordinal_reused:{family_id}"
            )

    for origin_id, origin in origins.items():
        require_reference(
            records,
            version_ids,
            origin_id,
            "hypothesis_version_id",
            origin["hypothesis_version_id"],
        )
        require_references(
            records,
            artifact_ids,
            origin_id,
            "artifact_ids",
            origin["artifact_ids"],
        )
        if parse_timestamp(origin["observed_at"]) > parse_timestamp(
            origin["recorded_at"]
        ):
            raise MemoryValidationError(
                f"origin_recorded_before_observed:{origin_id}"
            )
        if parse_timestamp(origin["recorded_at"]) > parse_timestamp(
            origin["first_reliable_available_at"]
        ):
            raise MemoryValidationError(
                f"origin_available_before_recorded:{origin_id}"
            )

    for cycle_id, cycle in cycles.items():
        require_references(
            records,
            version_ids,
            cycle_id,
            "hypothesis_version_ids",
            cycle["hypothesis_version_ids"],
        )
        if parse_timestamp(cycle["opened_at"]) > parse_timestamp(
            cycle["first_reliable_available_at"]
        ):
            raise MemoryValidationError(
                f"cycle_available_before_opened:{cycle_id}"
            )
        for version_id in cycle["hypothesis_version_ids"]:
            if versions[version_id]["research_cycle_id"] != cycle_id:
                raise MemoryValidationError(
                    f"cycle_hypothesis_backreference_mismatch:"
                    f"{cycle_id}:{version_id}"
                )

    for artifact_id, artifact in artifacts.items():
        require_references(
            records,
            version_ids,
            artifact_id,
            "hypothesis_version_ids",
            artifact["hypothesis_version_ids"],
        )
        if parse_timestamp(artifact["created_at"]) > parse_timestamp(
            artifact["first_reliable_available_at"]
        ):
            raise MemoryValidationError(
                f"artifact_available_before_created:{artifact_id}"
            )
        dataset_as_of = artifact.get("dataset_as_of")
        if dataset_as_of and parse_timestamp(dataset_as_of) > parse_timestamp(
            artifact["first_reliable_available_at"]
        ):
            raise MemoryValidationError(
                f"artifact_dataset_after_availability:{artifact_id}"
            )

    for trial_id, trial in trials.items():
        require_reference(
            records,
            version_ids,
            trial_id,
            "hypothesis_version_id",
            trial["hypothesis_version_id"],
        )
        require_reference(
            records,
            cycle_ids,
            trial_id,
            "research_cycle_id",
            trial["research_cycle_id"],
        )
        if (
            versions[trial["hypothesis_version_id"]]["research_cycle_id"]
            != trial["research_cycle_id"]
        ):
            raise MemoryValidationError(
                f"trial_hypothesis_cycle_mismatch:{trial_id}"
            )
        for field in (
            "control_artifact_ids",
            "dataset_artifact_ids",
            "method_artifact_ids",
            "result_artifact_ids",
        ):
            require_references(
                records,
                artifact_ids,
                trial_id,
                field,
                trial[field],
            )
        for field in (
            "population_artifact_id",
            "cost_assumptions_artifact_id",
        ):
            require_reference(
                records,
                artifact_ids,
                trial_id,
                field,
                trial[field],
            )
        budget = trial["search_budget"]
        if budget["executed_variants"] > budget["planned_variants"]:
            raise MemoryValidationError(
                f"trial_search_budget_exceeded:{trial_id}"
            )
        dataset_as_of = parse_timestamp(trial["dataset_as_of"])
        cutoff = parse_timestamp(trial["availability_cutoff"])
        completed = parse_timestamp(trial["completed_at"])
        available = parse_timestamp(trial["first_reliable_available_at"])
        prerequisite_artifact_ids = {
            trial["population_artifact_id"],
            trial["cost_assumptions_artifact_id"],
            *trial["control_artifact_ids"],
            *trial["dataset_artifact_ids"],
            *trial["method_artifact_ids"],
        }
        if any(
            parse_timestamp(
                artifacts[artifact_id]["first_reliable_available_at"]
            )
            > cutoff
            for artifact_id in prerequisite_artifact_ids
        ):
            raise MemoryValidationError(
                f"trial_prerequisite_artifact_after_cutoff:{trial_id}"
            )
        if any(
            parse_timestamp(
                artifacts[artifact_id]["first_reliable_available_at"]
            )
            > completed
            for artifact_id in trial["result_artifact_ids"]
        ):
            raise MemoryValidationError(
                f"trial_result_artifact_after_completion:{trial_id}"
            )
        if not dataset_as_of <= cutoff <= completed <= available:
            raise MemoryValidationError(
                f"trial_pit_order_invalid:{trial_id}"
            )

    for decision_id, decision in decisions.items():
        require_reference(
            records,
            version_ids,
            decision_id,
            "hypothesis_version_id",
            decision["hypothesis_version_id"],
        )
        require_references(
            records,
            trial_ids,
            decision_id,
            "trial_ids",
            decision["trial_ids"],
        )
        if "activation_epoch_id" in decision:
            require_reference(
                records,
                epoch_ids,
                decision_id,
                "activation_epoch_id",
                decision["activation_epoch_id"],
            )
        supersedes = decision.get("supersedes_decision_event_id")
        if supersedes:
            require_reference(
                records,
                decision_ids,
                decision_id,
                "supersedes_decision_event_id",
                supersedes,
            )
            if supersedes == decision_id:
                raise MemoryValidationError(
                    f"decision_event_self_supersession:{decision_id}"
                )
        decided = parse_timestamp(decision["decided_at"])
        effective = parse_timestamp(decision["effective_at"])
        available = parse_timestamp(decision["first_reliable_available_at"])
        if not decided <= effective <= available:
            raise MemoryValidationError(
                f"decision_time_order_invalid:{decision_id}"
            )

    for edge in document["derivation_edges"]:
        edge_id = edge["derivation_edge_id"]
        require_references(
            records,
            version_ids,
            edge_id,
            "parent_hypothesis_version_ids",
            edge["parent_hypothesis_version_ids"],
        )
        require_reference(
            records,
            version_ids,
            edge_id,
            "child_hypothesis_version_id",
            edge["child_hypothesis_version_id"],
        )
        if parse_timestamp(edge["created_at"]) > parse_timestamp(
            edge["first_reliable_available_at"]
        ):
            raise MemoryValidationError(
                f"derivation_available_before_created:{edge_id}"
            )
        related_versions = [
            *edge["parent_hypothesis_version_ids"],
            edge["child_hypothesis_version_id"],
        ]
        if any(
            parse_timestamp(
                versions[version_id]["first_reliable_available_at"]
            )
            > parse_timestamp(edge["first_reliable_available_at"])
            for version_id in related_versions
        ):
            raise MemoryValidationError(
                f"derivation_available_before_related_version:{edge_id}"
            )
    _validate_no_derivation_cycles(document["derivation_edges"])

    decisions_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions.values():
        family_id = versions[decision["hypothesis_version_id"]]["family_id"]
        decisions_by_family[family_id].append(decision)

    epochs_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for epoch_id, epoch in epochs.items():
        require_reference(
            records,
            version_ids,
            epoch_id,
            "hypothesis_version_id",
            epoch["hypothesis_version_id"],
        )
        require_reference(
            records,
            decision_ids,
            epoch_id,
            "activation_basis_decision_event_id",
            epoch["activation_basis_decision_event_id"],
        )
        previous = epoch.get("previous_activation_epoch_id")
        if previous:
            require_reference(
                records,
                epoch_ids,
                epoch_id,
                "previous_activation_epoch_id",
                previous,
            )
            if previous == epoch_id:
                raise MemoryValidationError(
                    f"activation_epoch_self_reference:{epoch_id}"
                )
        opened = parse_timestamp(epoch["opened_at"])
        available = parse_timestamp(epoch["first_reliable_available_at"])
        if opened > available:
            raise MemoryValidationError(
                f"epoch_available_before_opened:{epoch_id}"
            )
        basis = decisions[epoch["activation_basis_decision_event_id"]]
        if basis["decision_kind"] not in {"PROMOTE", "REACTIVATE"}:
            raise MemoryValidationError(
                f"epoch_basis_not_promotion_or_reactivation:{epoch_id}"
            )
        if basis["hypothesis_version_id"] != epoch["hypothesis_version_id"]:
            raise MemoryValidationError(
                f"epoch_basis_hypothesis_mismatch:{epoch_id}"
            )
        if parse_timestamp(basis["effective_at"]) > opened:
            raise MemoryValidationError(
                f"epoch_opened_before_basis_effective:{epoch_id}"
            )
        family_id = versions[epoch["hypothesis_version_id"]]["family_id"]
        epochs_by_family[family_id].append(epoch)

    for family_id, family_epochs in epochs_by_family.items():
        ordered = sorted(
            family_epochs,
            key=lambda row: (
                row["epoch_ordinal"],
                row["opened_at"],
                row["activation_epoch_id"],
            ),
        )
        ordinals = [row["epoch_ordinal"] for row in ordered]
        if len(ordinals) != len(set(ordinals)):
            raise MemoryValidationError(
                f"activation_epoch_ordinal_reused:{family_id}"
            )
        for index, epoch in enumerate(ordered):
            if index == 0:
                if epoch["epoch_ordinal"] != 1:
                    raise MemoryValidationError(
                        f"activation_epoch_first_ordinal_not_one:{family_id}"
                    )
                continue
            previous = ordered[index - 1]
            if epoch["epoch_ordinal"] <= previous["epoch_ordinal"]:
                raise MemoryValidationError(
                    f"activation_epoch_ordinal_not_increasing:{family_id}"
                )
            if (
                epoch.get("previous_activation_epoch_id")
                != previous["activation_epoch_id"]
            ):
                raise MemoryValidationError(
                    f"activation_epoch_previous_link_invalid:"
                    f"{epoch['activation_epoch_id']}"
                )

        family_decisions = decisions_by_family[family_id]
        for epoch in ordered:
            basis = decisions[epoch["activation_basis_decision_event_id"]]
            if basis["decision_kind"] != "REACTIVATE":
                continue
            basis_time = parse_timestamp(basis["effective_at"])
            prior_closure = any(
                row["decision_kind"] in {"PAUSE", "MARK_DORMANT"}
                and parse_timestamp(row["effective_at"]) < basis_time
                for row in family_decisions
            )
            if not prior_closure:
                raise MemoryValidationError(
                    f"reactivation_without_prior_pause_or_dormancy:"
                    f"{epoch['activation_epoch_id']}"
                )


def normalize_terms(values: Iterable[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        tokens.update(
            token
            for token in re.split(r"[^\w]+", value.casefold())
            if token
        )
    return tokens


def validate_query(query: dict[str, Any], document: dict[str, Any]) -> None:
    if not isinstance(query, dict):
        raise MemoryValidationError("query_not_object")
    allowed = {"query_id", "as_of", "max_results", "predicates"}
    if set(query) != allowed:
        raise MemoryValidationError(
            f"query_fields_invalid:{sorted(set(query) ^ allowed)}"
        )
    if not isinstance(query["query_id"], str) or not re.fullmatch(
        r"^PRIOR-WORK-QUERY-[A-Z0-9]+(?:-[A-Z0-9]+)*$",
        query["query_id"],
    ):
        raise MemoryValidationError("query_id_invalid")
    if not isinstance(query["as_of"], str):
        raise MemoryValidationError("query_as_of_not_string")
    if not UTC_TIMESTAMP_PATTERN.fullmatch(query["as_of"]):
        raise MemoryValidationError("query_as_of_invalid")
    try:
        cutoff = parse_timestamp(query["as_of"])
    except ValueError as exc:
        raise MemoryValidationError("query_as_of_invalid") from exc
    if cutoff > parse_timestamp(document["as_of"]):
        raise MemoryValidationError("query_as_of_after_memory_snapshot")
    max_results = query["max_results"]
    if not isinstance(max_results, int) or isinstance(max_results, bool):
        raise MemoryValidationError("query_max_results_not_integer")
    if not 1 <= max_results <= 50:
        raise MemoryValidationError("query_max_results_out_of_bounds")
    predicates = query["predicates"]
    if not isinstance(predicates, dict):
        raise MemoryValidationError("query_predicates_not_object")
    unknown = set(predicates) - QUERY_PREDICATES
    if unknown:
        raise MemoryValidationError(
            f"query_predicates_unknown:{sorted(unknown)}"
        )
    if not any(predicates.get(key) for key in QUERY_PREDICATES):
        raise MemoryValidationError("query_predicates_empty")
    for key, values in predicates.items():
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            raise MemoryValidationError(
                f"query_predicate_values_invalid:{key}"
            )
    enum_predicates = {
        "origin_kinds": ORIGIN_KINDS,
        "trial_outcomes": TRIAL_OUTCOMES,
        "decision_kinds": DECISION_KINDS,
    }
    for key, allowed_values in enum_predicates.items():
        invalid = set(predicates.get(key, [])) - allowed_values
        if invalid:
            raise MemoryValidationError(
                f"query_predicate_enum_invalid:{key}:{sorted(invalid)}"
            )
    pattern_predicates = {
        "hypothesis_version_ids": HYPOTHESIS_VERSION_ID_PATTERN,
        "dataset_artifact_ids": RESEARCH_ARTIFACT_ID_PATTERN,
        "tool_capability_ids": STABLE_ID_PATTERN,
    }
    for key, pattern in pattern_predicates.items():
        invalid = [
            value
            for value in predicates.get(key, [])
            if not pattern.fullmatch(value)
        ]
        if invalid:
            raise MemoryValidationError(
                f"query_predicate_id_invalid:{key}:{sorted(invalid)}"
            )


def current_state_as_of(
    decisions: Iterable[dict[str, Any]],
    cutoff: datetime,
) -> str:
    eligible = [
        decision
        for decision in decisions
        if parse_timestamp(decision["effective_at"]) <= cutoff
        and parse_timestamp(decision["first_reliable_available_at"]) <= cutoff
        and decision["decision_kind"] in STATE_BY_DECISION
    ]
    if not eligible:
        return "NO_DECISION"
    ordered = sorted(
        eligible,
        key=lambda row: (
            row["effective_at"],
            row["first_reliable_available_at"],
            row["decision_event_id"],
        ),
    )
    return STATE_BY_DECISION[ordered[-1]["decision_kind"]]


def query_prior_work(
    document: dict[str, Any],
    query: dict[str, Any],
    *,
    memory_content_sha256: str | None = None,
) -> dict[str, Any]:
    validate_memory(document)
    validate_query(query, document)
    cutoff = parse_timestamp(query["as_of"])
    predicates = query["predicates"]
    version_ids = set(predicates.get("hypothesis_version_ids", []))
    mechanism_terms = normalize_terms(predicates.get("mechanism_terms", []))
    falsifier_terms = normalize_terms(predicates.get("falsifier_terms", []))
    regime_terms = normalize_terms(predicates.get("regime_terms", []))
    origin_kinds = set(predicates.get("origin_kinds", []))
    dataset_artifact_ids = set(
        predicates.get("dataset_artifact_ids", [])
    )
    tool_capability_ids = set(predicates.get("tool_capability_ids", []))
    trial_outcomes = set(predicates.get("trial_outcomes", []))
    decision_kinds = set(predicates.get("decision_kinds", []))

    versions = {
        row["hypothesis_version_id"]: row
        for row in document["hypothesis_versions"]
        if parse_timestamp(row["first_reliable_available_at"]) <= cutoff
    }
    origins_by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    artifacts_by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    trials_by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    decisions_by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    edges_by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)
    epochs_by_version: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for origin in document["hypothesis_origins"]:
        if parse_timestamp(origin["first_reliable_available_at"]) <= cutoff:
            origins_by_version[origin["hypothesis_version_id"]].append(origin)
    for artifact in document["research_artifacts"]:
        if parse_timestamp(artifact["first_reliable_available_at"]) <= cutoff:
            for version_id in artifact["hypothesis_version_ids"]:
                artifacts_by_version[version_id].append(artifact)
    for trial in document["trials"]:
        if parse_timestamp(trial["first_reliable_available_at"]) <= cutoff:
            trials_by_version[trial["hypothesis_version_id"]].append(trial)
            referenced_artifact_ids = {
                trial["population_artifact_id"],
                trial["cost_assumptions_artifact_id"],
                *trial["control_artifact_ids"],
                *trial["dataset_artifact_ids"],
                *trial["method_artifact_ids"],
                *trial["result_artifact_ids"],
            }
            for artifact_id in sorted(referenced_artifact_ids):
                artifact = next(
                    row
                    for row in document["research_artifacts"]
                    if row["research_artifact_id"] == artifact_id
                )
                if (
                    parse_timestamp(
                        artifact["first_reliable_available_at"]
                    )
                    <= cutoff
                    and artifact
                    not in artifacts_by_version[
                        trial["hypothesis_version_id"]
                    ]
                ):
                    artifacts_by_version[
                        trial["hypothesis_version_id"]
                    ].append(artifact)
    for decision in document["decision_events"]:
        if parse_timestamp(decision["first_reliable_available_at"]) <= cutoff:
            decisions_by_version[decision["hypothesis_version_id"]].append(
                decision
            )
    for edge in document["derivation_edges"]:
        if parse_timestamp(edge["first_reliable_available_at"]) <= cutoff:
            related = [
                *edge["parent_hypothesis_version_ids"],
                edge["child_hypothesis_version_id"],
            ]
            for version_id in related:
                edges_by_version[version_id].append(edge)
    for epoch in document["activation_epochs"]:
        if parse_timestamp(epoch["first_reliable_available_at"]) <= cutoff:
            epochs_by_version[epoch["hypothesis_version_id"]].append(epoch)

    results: list[dict[str, Any]] = []
    for version_id, version in versions.items():
        score = 0
        matched_by: set[str] = set()

        if version_id in version_ids:
            score += 100
            matched_by.add("EXACT_HYPOTHESIS_VERSION")

        mechanism_overlap = mechanism_terms & normalize_terms(
            [version["mechanism"], version["statement"]]
        )
        if mechanism_overlap:
            score += 5 * len(mechanism_overlap)
            matched_by.add("MECHANISM_TERM")

        falsifier_overlap = falsifier_terms & normalize_terms(
            [version["falsifier"]]
        )
        if falsifier_overlap:
            score += 5 * len(falsifier_overlap)
            matched_by.add("FALSIFIER_TERM")

        regime_overlap = regime_terms & normalize_terms(
            version["expected_regime_terms"]
        )
        if regime_overlap:
            score += 5 * len(regime_overlap)
            matched_by.add("REGIME_TERM")

        origins = origins_by_version.get(version_id, [])
        matched_origin_kinds = {
            origin["origin_kind"] for origin in origins
        } & origin_kinds
        if matched_origin_kinds:
            score += 20 * len(matched_origin_kinds)
            matched_by.add("ORIGIN_KIND")

        artifacts = artifacts_by_version.get(version_id, [])
        matched_datasets = {
            artifact["research_artifact_id"]
            for artifact in artifacts
            if artifact["artifact_kind"] == "DATASET_SNAPSHOT"
        } & dataset_artifact_ids
        if matched_datasets:
            score += 40 * len(matched_datasets)
            matched_by.add("DATASET_ARTIFACT")

        matched_tools = {
            artifact.get("tool_capability_id")
            for artifact in artifacts
            if artifact.get("tool_capability_id")
        } & tool_capability_ids
        if matched_tools:
            score += 40 * len(matched_tools)
            matched_by.add("TOOL_CAPABILITY")

        trials = trials_by_version.get(version_id, [])
        matched_outcomes = {
            trial["outcome"] for trial in trials
        } & trial_outcomes
        if matched_outcomes:
            score += 20 * len(matched_outcomes)
            matched_by.add("TRIAL_OUTCOME")

        decisions = decisions_by_version.get(version_id, [])
        matched_decisions = {
            decision["decision_kind"] for decision in decisions
        } & decision_kinds
        if matched_decisions:
            score += 20 * len(matched_decisions)
            matched_by.add("DECISION_KIND")

        if not matched_by:
            continue

        edges = edges_by_version.get(version_id, [])
        epochs = epochs_by_version.get(version_id, [])
        evidence_asset_ids = sorted(
            {
                evidence_id
                for record in [version, *trials, *decisions, *edges]
                for evidence_id in record.get("evidence_asset_ids", [])
            }
        )
        results.append(
            {
                "hypothesis_version_id": version_id,
                "family_id": version["family_id"],
                "score": score,
                "matched_by": sorted(matched_by),
                "origin_ids": sorted(
                    origin["origin_id"] for origin in origins
                ),
                "research_artifact_ids": sorted(
                    artifact["research_artifact_id"]
                    for artifact in artifacts
                ),
                "artifact_content_sha256": sorted(
                    {
                        artifact["content_sha256"]
                        for artifact in artifacts
                    }
                ),
                "trial_ids": sorted(trial["trial_id"] for trial in trials),
                "trial_outcomes": sorted(
                    {trial["outcome"] for trial in trials}
                ),
                "decision_event_ids": sorted(
                    decision["decision_event_id"] for decision in decisions
                ),
                "derivation_edge_ids": sorted(
                    edge["derivation_edge_id"] for edge in edges
                ),
                "activation_epoch_ids": sorted(
                    epoch["activation_epoch_id"] for epoch in epochs
                ),
                "evidence_asset_ids": evidence_asset_ids,
                "current_state_as_of": current_state_as_of(
                    decisions,
                    cutoff,
                ),
                "repeat_or_extension_requires_what_changed": True,
            }
        )

    ordered_results = sorted(
        results,
        key=lambda row: (
            -row["score"],
            row["hypothesis_version_id"],
        ),
    )[: query["max_results"]]
    memory_sha256 = memory_content_sha256 or hashlib.sha256(
        canonical_json_bytes(document)
    ).hexdigest()
    return {
        "schema": "smial.prior_work_query_result.v1",
        "query_id": query["query_id"],
        "as_of": query["as_of"],
        "memory_id": document["memory_id"],
        "memory_content_sha256": memory_sha256,
        "result_count": len(ordered_results),
        "results": ordered_results,
        "automatic_reject_or_promotion": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and query the offline hypothesis research memory."
    )
    parser.add_argument("--memory", required=True, type=Path)
    parser.add_argument("--query-id", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--max-results", type=int, default=20)
    for predicate in sorted(QUERY_PREDICATES):
        parser.add_argument(
            f"--{predicate.replace('_', '-')}",
            action="append",
            default=[],
        )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    document, content_sha256 = load_memory(args.memory)
    predicates = {
        predicate: getattr(args, predicate)
        for predicate in QUERY_PREDICATES
        if getattr(args, predicate)
    }
    result = query_prior_work(
        document,
        {
            "query_id": args.query_id,
            "as_of": args.as_of,
            "max_results": args.max_results,
            "predicates": predicates,
        },
        memory_content_sha256=content_sha256,
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
