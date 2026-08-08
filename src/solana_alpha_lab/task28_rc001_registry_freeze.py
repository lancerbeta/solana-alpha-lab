"""Deterministic offline admissibility for the frozen TASK-28 RC-001 groups."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


ADMISSIBILITY_STATES = frozenset(
    {"READY", "LIMITED_DIAGNOSTIC_ONLY", "BLOCKED_DATA", "BLOCKED_EXECUTION_TRUTH"}
)
DATA_DOMAINS = frozenset({"DATA", "ENTITY"})
AVAILABLE = "AVAILABLE"


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, list):
        normalized = [_canonicalize(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(
                item, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ),
        )
    return value


def canonical_definition_hash(group: Mapping[str, Any]) -> str:
    """Return a stable hash for a frozen group definition.

    Arrays are semantic sets in this control record, so their order cannot
    create a second definition. A future persistent definition hash is excluded
    from its own digest to avoid self-reference.
    """
    definition = {
        str(key): value
        for key, value in group.items()
        if key != "definition_sha256"
    }
    encoded = json.dumps(
        _canonicalize(definition),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate_admissibility(group: Mapping[str, Any]) -> dict[str, Any]:
    """Return the fail-closed admissibility state for one frozen group.

    Data and entity evidence takes precedence over an execution-truth gap: a
    trial cannot become executable merely because its deeper data dependency is
    still missing. Blocker order follows the frozen configuration order.
    """
    requirements = group.get("requirements")
    if not isinstance(requirements, list):
        raise ValueError("requirements")

    blocker_codes: list[str] = []
    blocker_domains: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, Mapping):
            raise ValueError("requirement")
        requirement_id = requirement.get("requirement_id")
        domain = requirement.get("domain")
        state = requirement.get("state")
        if not isinstance(requirement_id, str) or not isinstance(domain, str):
            raise ValueError("requirement_identity")
        if state != AVAILABLE:
            blocker_codes.append(requirement_id)
            blocker_domains.append(domain)

    if any(domain in DATA_DOMAINS for domain in blocker_domains):
        state = "BLOCKED_DATA"
    elif blocker_codes:
        state = "BLOCKED_EXECUTION_TRUTH"
    else:
        state = "READY"

    return {"state": state, "blocker_codes": blocker_codes}


def validate_rc001_snapshot(
    config: Mapping[str, Any], registries: Mapping[str, Mapping[str, Any]]
) -> None:
    """Fail closed when a frozen RC-001 snapshot drifts or promotes evidence.

    The legacy lifecycle skeletons are read-only historical inputs. RC-001 is
    represented only by this task-owned config/evidence pair, so validation
    fails if a caller attempts to turn the old empty skeletons into synthetic
    research history.
    """
    authority = config.get("authority")
    if not isinstance(authority, Mapping):
        raise ValueError("authority")
    for name, value in authority.items():
        if value is not False:
            raise ValueError(str(name))

    non_claims = config.get("non_claims")
    if not isinstance(non_claims, Mapping):
        raise ValueError("non_claims")
    for name, value in non_claims.items():
        if value is not True:
            raise ValueError(str(name))

    expectations = config.get("admissibility_expectations")
    if not isinstance(expectations, Mapping):
        raise ValueError("admissibility_expectations")
    if (
        expectations.get("missingness_state") != "MISSING_UNKNOWN"
        or expectations.get("missing_to_zero_forbidden") is not True
    ):
        raise ValueError("missing_to_zero")

    policy = config.get("global_search_policy")
    if not isinstance(policy, Mapping):
        raise ValueError("global_search_policy")
    for field in (
        "trial_record_creation",
        "holdout_consumption",
        "parameter_tuning",
        "feature_expansion",
        "metric_expansion",
        "cross_group_combination",
    ):
        if policy.get(field) != "FORBIDDEN":
            raise ValueError(field)
    registered_parameter_ids = policy.get("registered_parameter_ids")
    if not isinstance(registered_parameter_ids, list) or not all(
        isinstance(parameter_id, str) for parameter_id in registered_parameter_ids
    ):
        raise ValueError("registered_parameter_ids")
    registered_parameter_id_set = set(registered_parameter_ids)
    declared_feature_ids = policy.get("declared_feature_ids")
    if not isinstance(declared_feature_ids, list) or not all(
        isinstance(feature_id, str) for feature_id in declared_feature_ids
    ):
        raise ValueError("declared_feature_ids")
    if len(set(declared_feature_ids)) != len(declared_feature_ids):
        raise ValueError("DUPLICATE_DECLARED_FEATURE_ID")

    groups = config.get("hypothesis_groups")
    if not isinstance(groups, list) or len(groups) != 3:
        raise ValueError("hypothesis_groups")
    group_ids = [group.get("group_id") for group in groups if isinstance(group, Mapping)]
    if group_ids != [
        "RC001-H13-COMPOSITE-VETO",
        "RC001-H07-H01-LIQUIDITY-RETENTION",
        "RC001-H02-H10-H14-PULLBACK-RECLAIM",
    ]:
        raise ValueError("group_order_or_identity")

    frozen_definition_ids: set[str] = set()
    feature_ids: set[str] = set()
    for group in groups:
        if not isinstance(group, Mapping):
            raise ValueError("group")
        frozen_definition_id = group.get("frozen_definition_id")
        feature_id = group.get("feature_id")
        if not isinstance(frozen_definition_id, str) or not isinstance(feature_id, str):
            raise ValueError("group_frozen_identity")
        if frozen_definition_id in frozen_definition_ids:
            raise ValueError("DUPLICATE_IMMUTABLE_DEFINITION_ID")
        if feature_id in feature_ids:
            raise ValueError("DUPLICATE_FEATURE_ID")
        frozen_definition_ids.add(frozen_definition_id)
        feature_ids.add(feature_id)

        parameter_policy = group.get("parameter_policy")
        if not isinstance(parameter_policy, Mapping):
            raise ValueError("parameter_policy")
        allowed_parameter_ids = parameter_policy.get("allowed_parameter_ids")
        if not isinstance(allowed_parameter_ids, list) or not all(
            isinstance(parameter_id, str) for parameter_id in allowed_parameter_ids
        ):
            raise ValueError("allowed_parameter_ids")
        if not set(allowed_parameter_ids).issubset(registered_parameter_id_set):
            raise ValueError("UNREGISTERED_PARAMETER")

        result = evaluate_admissibility(group)
        expected = group.get("expected_admissibility")
        if not isinstance(expected, Mapping):
            raise ValueError("expected_admissibility")
        if expected.get("state") != result["state"]:
            first_blocker = result["blocker_codes"][0] if result["blocker_codes"] else "READY_DRIFT"
            raise ValueError(first_blocker)
        if expected.get("blocker_codes") != result["blocker_codes"]:
            raise ValueError("ADMISSIBILITY_BLOCKER_DRIFT")

    if feature_ids != set(declared_feature_ids):
        raise ValueError("FOREIGN_FEATURE_WITHOUT_VERSIONED_LINK")

    for registry_type in (
        "research_cycles",
        "hypotheses",
        "feature_catalog",
        "global_trial_ledger",
    ):
        if registry_type not in registries:
            raise ValueError(f"missing_registry:{registry_type}")

    research_cycle = config.get("research_cycle")
    if not isinstance(research_cycle, Mapping):
        raise ValueError("research_cycle")
    research_cycle_id = research_cycle.get("research_cycle_id")
    if research_cycle_id != "RESEARCH-CYCLE-RC001-001":
        raise ValueError("research_cycle_id")
    if research_cycle.get("task_owned_register_id") != "TASK28-RC001-REGISTER-001":
        raise ValueError("task_owned_register_id")
    if research_cycle.get("register_kind") != "TASK_OWNED_CONFIG_EVIDENCE":
        raise ValueError("register_kind")

    def record_index(registry_type: str) -> dict[str, Mapping[str, Any]]:
        document = registries[registry_type]
        records = document.get("records")
        if not isinstance(records, list):
            raise ValueError(f"records:{registry_type}")
        indexed: dict[str, Mapping[str, Any]] = {}
        for record in records:
            if not isinstance(record, Mapping) or not isinstance(record.get("record_id"), str):
                raise ValueError(f"record:{registry_type}")
            record_id = record["record_id"]
            if record_id in indexed:
                raise ValueError(f"duplicate_registry_record:{registry_type}")
            indexed[record_id] = record
        return indexed

    for registry_type in ("research_cycles", "hypotheses", "feature_catalog"):
        if record_index(registry_type):
            raise ValueError("LEGACY_LIFECYCLE_SKELETON_REWRITE_FORBIDDEN")

    for group in groups:
        assert isinstance(group, Mapping)
        stored_hash = group.get("definition_sha256")
        if not isinstance(stored_hash, str) or stored_hash != canonical_definition_hash(group):
            raise ValueError("UNREGISTERED_PARAMETER_OR_DEFINITION_DRIFT")

    ledger_records = record_index("global_trial_ledger")
    if any(
        record.get("record_id", "").startswith("TRIAL-RC001")
        or record.get("hypothesis_id") in frozen_definition_ids
        for record in ledger_records.values()
    ):
        raise ValueError("RC001_TRIAL_RECORD_FORBIDDEN")
