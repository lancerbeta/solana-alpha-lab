"""Fail-closed, offline owner readout for frozen TASK-30 H07/H01 evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


FROZEN_GROUP_ID = "RC001-H07-H01-LIQUIDITY-RETENTION"
FROZEN_DEFINITION_HASH = (
    "14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7"
)
CURRENT_DECISION = "CAPTURE_REQUIRED"
NEXT_BOUNDARY = "EXACT_H07_H01_DATA_CONTRACT_ENTRY_GATE"
ALLOWED_DECISIONS = (
    "RUN_LIMITED_DIAGNOSTIC",
    "CAPTURE_REQUIRED",
    "REDESIGN_DATA",
    "CLOSE_ROUTE",
)
EXPECTED_REQUIREMENT_STATES = {
    "CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE": "MISSING_UNKNOWN",
    "SETTLED_EXECUTION_TRUTH_UNAVAILABLE": "UNSUPPORTED",
}
EXPECTED_BLOCKERS = list(EXPECTED_REQUIREMENT_STATES)
EXPECTED_EVIDENCE = {
    "task27_route_close": {
        "path": "docs/evidence/task27/a1s4_owner_route_close_and_task_outcome_acceptance_v1.json",
        "sha256": "e901a59a72da29b3eb4a90e24a7d3bde91a4fc00c023310086376747ebe47e6d",
    },
    "task26b_execution_witness": {
        "path": "docs/evidence/task26b/a1_execution_witness_route_acceptance_v1.json",
        "sha256": "86cd5d33f3e29f9c3d365afc1aca511b212d6a809fa7be3ea2c6e65ffebd4b73",
    },
    "task30_a6_forward_capture": {
        "path": "docs/evidence/task30/a6_birdeye_route_hold_forward_capture_decision_acceptance_v1.json",
        "sha256": "e40b3fc46762c015f439a453f68939859114f8f498e1791a0a68f1790829e036",
    },
}


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(name)
    return value


def _zero_values(section: Mapping[str, Any], name: str) -> None:
    for key, value in section.items():
        if value not in (0, False):
            raise ValueError(f"{name}:{key}")


def _false_values(section: Mapping[str, Any], name: str) -> None:
    for key, value in section.items():
        if value is not False:
            raise ValueError(f"{name}:{key}")


def validate_owner_visible_slice(
    config: Mapping[str, Any], frozen_group: Mapping[str, Any]
) -> None:
    """Reject any unstated promotion of frozen H07/H01 evidence."""
    frozen_definition = _mapping(config.get("frozen_definition"), "frozen_definition")
    if frozen_definition.get("group_id") != FROZEN_GROUP_ID:
        raise ValueError("FROZEN_GROUP_ID_MISMATCH")
    if frozen_definition.get("definition_sha256") != FROZEN_DEFINITION_HASH:
        raise ValueError("FROZEN_DEFINITION_HASH_MISMATCH")
    if frozen_group.get("group_id") != FROZEN_GROUP_ID:
        raise ValueError("FROZEN_GROUP_INPUT_MISMATCH")
    if frozen_group.get("definition_sha256") != FROZEN_DEFINITION_HASH:
        raise ValueError("FROZEN_GROUP_HASH_INPUT_MISMATCH")
    if frozen_definition.get("definition_inputs") != frozen_group.get(
        "definition_inputs"
    ):
        raise ValueError("FROZEN_INPUTS_MISMATCH")

    input_evidence = _mapping(config.get("input_evidence"), "input_evidence")
    if set(input_evidence) != set(EXPECTED_EVIDENCE):
        raise ValueError("INPUT_EVIDENCE_SET")
    for evidence_id, expected in EXPECTED_EVIDENCE.items():
        evidence = _mapping(input_evidence.get(evidence_id), evidence_id)
        for field, expected_value in expected.items():
            if evidence.get(field) != expected_value:
                raise ValueError(f"INPUT_EVIDENCE:{evidence_id}:{field}")

    evidence = _mapping(config.get("current_evidence"), "current_evidence")
    if evidence.get("requirement_states") != EXPECTED_REQUIREMENT_STATES:
        raise ValueError("FROZEN_REQUIREMENT_STATE_MISMATCH")
    if evidence.get("settled_execution_truth") != "UNSUPPORTED":
        raise ValueError("SETTLEMENT_PROMOTION")
    if evidence.get("trial_admissible") is not False:
        raise ValueError("IMPLICIT_TRIAL_ADMISSION")
    if evidence.get("provider_selection") != "NOT_SELECTED":
        raise ValueError("PROVIDER_SELECTION_PROMOTION")
    if evidence.get("forward_capture_state") != "PLANNED_NOT_STARTED":
        raise ValueError("FORWARD_CAPTURE_STATE_PROMOTION")
    if evidence.get("background_collection") is not False:
        raise ValueError("BACKGROUND_COLLECTION_PROMOTION")

    missingness = _mapping(config.get("missingness_policy"), "missingness_policy")
    expected_missingness = {
        "missing_to_zero": "FORBIDDEN",
        "unknown_to_settled": "FORBIDDEN",
        "continuity_imputation": "FORBIDDEN",
    }
    if missingness != expected_missingness:
        raise ValueError("MISSINGNESS_COERCION")

    decision_policy = _mapping(config.get("decision_policy"), "decision_policy")
    if decision_policy.get("allowed_terminal_decisions") != list(ALLOWED_DECISIONS):
        raise ValueError("TERMINAL_DECISION_SET")
    if decision_policy.get("current_decision") != CURRENT_DECISION:
        raise ValueError("CURRENT_DECISION_PROMOTION")
    if decision_policy.get("next_boundary") != NEXT_BOUNDARY:
        raise ValueError("NEXT_BOUNDARY_DRIFT")
    if decision_policy.get("external_read_authority") != "REQUIRED_NOT_GRANTED":
        raise ValueError("EXTERNAL_READ_AUTHORITY_PROMOTION")

    _zero_values(_mapping(config.get("authority"), "authority"), "authority")
    _zero_values(
        _mapping(config.get("side_effect_counters"), "side_effect_counters"),
        "side_effect_counters",
    )
    _false_values(_mapping(config.get("non_claims"), "non_claims"), "non_claims")

    sources = _mapping(
        config.get("project_sources_disposition"), "project_sources_disposition"
    )
    if sources.get("kind") != "NO_CHANGE":
        raise ValueError("PROJECT_SOURCES_DISPOSITION")


def evaluate_owner_visible_slice(
    config: Mapping[str, Any], frozen_group: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the only current owner decision from the frozen evidence state."""
    validate_owner_visible_slice(config, frozen_group)
    return {
        "decision": CURRENT_DECISION,
        "blocker_codes": EXPECTED_BLOCKERS,
        "next_boundary": NEXT_BOUNDARY,
        "summary": (
            "Для H07/H01 пока нужен точный gate на недостающие данные; "
            "исследовательский trial не готов к запуску."
        ),
        "missing_evidence": [
            "Непрерывная PIT history для liquidity-retention состояния.",
            "Settled execution truth для проверки route-aware outcome.",
        ],
        "non_claims": [
            "Текущая price/transport feasibility не является research trial.",
            "Quote или plan не являются settlement.",
            "Missing/UNKNOWN не являются zero, no-trade, flat или settled.",
            "Провайдер не выбран, forward capture не начат.",
        ],
    }


def render_owner_readout(result: Mapping[str, Any]) -> str:
    """Render one stable Russian owner readout from evaluated offline evidence."""
    decision = result.get("decision")
    blockers = result.get("blocker_codes")
    next_boundary = result.get("next_boundary")
    summary = result.get("summary")
    missing_evidence = result.get("missing_evidence")
    non_claims = result.get("non_claims")
    if (
        decision != CURRENT_DECISION
        or blockers != EXPECTED_BLOCKERS
        or next_boundary != NEXT_BOUNDARY
        or not isinstance(summary, str)
        or not isinstance(missing_evidence, list)
        or not isinstance(non_claims, list)
    ):
        raise ValueError("OWNER_READOUT_INPUT")

    lines = [
        "# TASK-30 — H07/H01: что нужно дальше",
        "",
        "## Решение",
        "",
        "Нужен точный gate на получение данных (`CAPTURE_REQUIRED`).",
        "",
        summary,
        "",
        "## Чего не хватает",
        "",
    ]
    lines.extend(f"- {item}" for item in missing_evidence)
    lines.extend(
        [
            "",
            "## Что из этого не следует",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in non_claims)
    lines.extend(
        [
            "",
            "## Единственный следующий шаг",
            "",
            f"`{next_boundary}`. Он потребует отдельного owner gate; этот readout ничего не запускает.",
        ]
    )
    return "\n".join(lines)
