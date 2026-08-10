"""Offline projection of the frozen TASK-30 H07/H01 data-contract decision."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


FROZEN_GROUP_ID = "RC001-H07-H01-LIQUIDITY-RETENTION"
FROZEN_DEFINITION_HASH = (
    "14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7"
)
CURRENT_DECISION = "PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT"
NEXT_BOUNDARY = "OWNER_GATE_FOR_NAMED_PARTIAL_PIT_OR_ROUTE_CAPTURE"
ALLOWED_DECISIONS = (
    "PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT",
    "REDESIGN_DATA",
    "CLOSE_ROUTE",
)
EXPECTED_INPUT_EVIDENCE = {
    "task27_route_close": {
        "path": "docs/evidence/task27/a1s4_owner_route_close_and_task_outcome_acceptance_v1.json",
        "sha256": "e901a59a72da29b3eb4a90e24a7d3bde91a4fc00c023310086376747ebe47e6d",
        "decision": "CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE",
    },
    "task26b_execution_witness": {
        "path": "docs/evidence/task26b/a1_execution_witness_route_acceptance_v1.json",
        "sha256": "86cd5d33f3e29f9c3d365afc1aca511b212d6a809fa7be3ea2c6e65ffebd4b73",
        "decision": "OWNED_CANARY_REQUIRED",
    },
    "task30_a6_forward_capture": {
        "path": "docs/evidence/task30/a6_birdeye_route_hold_forward_capture_decision_acceptance_v1.json",
        "sha256": "e40b3fc46762c015f439a453f68939859114f8f498e1791a0a68f1790829e036",
        "decision": "HOLD_BIRDEYE_ROUTE_PREPARE_FORWARD_CAPTURE_CANDIDATE",
    },
    "task30_a7_owner_visible": {
        "path": "docs/evidence/task30/a7_h07_h01_owner_visible_vertical_slice_acceptance_v1.json",
        "sha256": "394fdb8b767d0d172b5fe56cb6bf8e205fa4dcc27bec924494f3955ccf391a66",
        "decision": "CAPTURE_REQUIRED",
    },
}
EXPECTED_REQUIREMENTS = {
    "pit_liquidity_retention_state": ("PIT_MARKET", "MISSING_UNKNOWN", True),
    "multi_notional_route_persistence": (
        "ROUTE_FEASIBILITY",
        "MISSING_UNKNOWN",
        True,
    ),
    "post_migration_continuation_context": ("PIT_MARKET", "MISSING_UNKNOWN", True),
    "settled_execution_truth": ("OWNED_EXECUTION", "UNSUPPORTED", False),
}


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(name)
    return value


def _zero_values(section: Mapping[str, Any], name: str) -> None:
    for key, value in section.items():
        if value not in (0, False):
            raise ValueError(f"AUTHORITY_PROMOTION:{name}:{key}")


def _false_values(section: Mapping[str, Any], name: str) -> None:
    for key, value in section.items():
        if value is not False:
            raise ValueError(f"FALSE_PROMOTION:{name}:{key}")


def _require_fields(
    lane: Mapping[str, Any], expected: set[str], error_code: str
) -> None:
    fields = lane.get("required_fields")
    if not isinstance(fields, list) or set(fields) != expected:
        raise ValueError(error_code)


def validate_data_contract(
    config: Mapping[str, Any], frozen_group: Mapping[str, Any]
) -> None:
    """Reject any unstated promotion in the frozen H07/H01 data contract."""
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
    if set(input_evidence) != set(EXPECTED_INPUT_EVIDENCE):
        raise ValueError("INPUT_EVIDENCE_SET")
    for evidence_id, expected in EXPECTED_INPUT_EVIDENCE.items():
        evidence = _mapping(input_evidence.get(evidence_id), evidence_id)
        for field, expected_value in expected.items():
            if evidence.get(field) != expected_value:
                raise ValueError(f"SOURCE_BINDING_CONFLICT:{evidence_id}:{field}")

    lanes = _mapping(config.get("lanes"), "lanes")
    if set(lanes) != {"PIT_MARKET", "ROUTE_FEASIBILITY", "OWNED_EXECUTION"}:
        raise ValueError("LANE_SET")
    pit_lane = _mapping(lanes["PIT_MARKET"], "PIT_MARKET")
    if pit_lane.get("may_establish") != "BOUNDED_MARKET_HISTORY_INPUT":
        raise ValueError("PIT_MARKET_PROMOTION")
    if pit_lane.get("cannot_establish") != ["ROUTE_PERSISTENCE", "FILL", "SETTLEMENT"]:
        raise ValueError("FALSE_PROMOTION:PIT_MARKET")
    _require_fields(
        pit_lane,
        {
            "pool_identity",
            "mint_identity",
            "dex_or_program_identity",
            "closed_interval",
            "ohlcv",
            "liquidity_state",
            "observed_at",
            "available_at",
            "ingested_at",
            "source_or_raw_sha256",
            "typed_gap_or_failure",
        },
        "AMBIGUOUS_PIT_SEMANTICS:PIT_MARKET",
    )
    route_lane = _mapping(lanes["ROUTE_FEASIBILITY"], "ROUTE_FEASIBILITY")
    if route_lane.get("may_establish") != "MULTI_NOTIONAL_ROUTE_AVAILABILITY":
        raise ValueError("ROUTE_FEASIBILITY_PROMOTION")
    if route_lane.get("cannot_establish") != ["FILL", "SETTLEMENT"]:
        raise ValueError("FALSE_PROMOTION:ROUTE_FEASIBILITY")
    _require_fields(
        route_lane,
        {
            "evaluated_at",
            "input_mint",
            "output_mint",
            "notional",
            "route_identifier_or_status",
            "quoted_amounts",
            "price_impact",
            "separate_fees",
            "observed_at",
            "available_at",
            "ingested_at",
            "source_or_raw_sha256",
            "typed_gap_or_failure",
        },
        "AMBIGUOUS_PIT_SEMANTICS:ROUTE_FEASIBILITY",
    )
    execution_lane = _mapping(lanes["OWNED_EXECUTION"], "OWNED_EXECUTION")
    if execution_lane.get("may_establish") != "OWNER_ATTEMPT_INVENTORY_AND_SETTLEMENT":
        raise ValueError("OWNED_EXECUTION_SCOPE")
    if execution_lane.get("future_canary_only") is not True:
        raise ValueError("OWNED_EXECUTION_PROMOTION")
    if execution_lane.get("available_in_this_atom") is not False:
        raise ValueError("OWNED_EXECUTION_PROMOTION")
    _require_fields(
        execution_lane,
        {
            "stable_attempt_id",
            "retry_chain_id",
            "transaction_signature",
            "terminal_state",
            "terminal_at",
            "token_and_sol_deltas",
            "separate_fees",
            "inventory_before_after",
            "reconciliation_reference",
            "source_or_raw_hashes",
        },
        "OWNED_EXECUTION_FIELD_SET",
    )

    requirements = _mapping(config.get("requirements"), "requirements")
    if set(requirements) != set(EXPECTED_REQUIREMENTS):
        raise ValueError("UNMAPPED_REQUIREMENT")
    for requirement_id, (expected_lane, expected_state, expected_capture) in (
        EXPECTED_REQUIREMENTS.items()
    ):
        requirement = _mapping(requirements[requirement_id], requirement_id)
        if requirement.get("lane") != expected_lane:
            raise ValueError(f"UNMAPPED_REQUIREMENT:{requirement_id}:lane")
        if requirement.get("state") != expected_state:
            if requirement_id == "settled_execution_truth":
                raise ValueError("SETTLEMENT_PROMOTION")
            raise ValueError(f"UNMAPPED_REQUIREMENT:{requirement_id}:state")
        if requirement.get("future_capture_capable") is not expected_capture:
            raise ValueError(f"UNMAPPED_REQUIREMENT:{requirement_id}:capture")
    migration_context = _mapping(
        requirements["post_migration_continuation_context"],
        "post_migration_continuation_context",
    )
    if migration_context.get("required_context_fields") != [
        "migration_or_program_context",
        "pool_identity",
        "pre_and_post_boundary_continuity",
    ]:
        raise ValueError("UNMAPPED_REQUIREMENT:post_migration_context")

    decision_policy = _mapping(config.get("decision_policy"), "decision_policy")
    if decision_policy.get("allowed_terminal_decisions") != list(ALLOWED_DECISIONS):
        raise ValueError("TERMINAL_DECISION_SET")
    if decision_policy.get("current_decision") != CURRENT_DECISION:
        raise ValueError("CURRENT_DECISION_PROMOTION")
    if decision_policy.get("trial_admissible") is not False:
        raise ValueError("IMPLICIT_TRIAL_ADMISSION")
    if decision_policy.get("next_boundary") != NEXT_BOUNDARY:
        raise ValueError("NEXT_BOUNDARY_DRIFT")

    missingness = _mapping(config.get("missingness_policy"), "missingness_policy")
    if missingness != {
        "missing_to_zero": "FORBIDDEN",
        "quote_to_settlement": "FORBIDDEN",
        "price_to_trial": "FORBIDDEN",
        "continuity_imputation": "FORBIDDEN",
    }:
        raise ValueError("MISSINGNESS_COERCION")

    safety = _mapping(config.get("capture_safety"), "capture_safety")
    backup = _mapping(safety.get("backup_or_waiver"), "backup_or_waiver")
    if backup != {
        "required": True,
        "applies_before": "DECISION_CRITICAL_IRRECOVERABLE_FUTURE_CAPTURE",
        "registered_backup_or_restore_route": "REQUIRED",
        "tracked_waiver": "ALLOWED_IF_EXPLICIT",
    }:
        raise ValueError("UNRECOVERABLE_CAPTURE_WITHOUT_COVERAGE")
    reuse = _mapping(config.get("reuse_trigger"), "reuse_trigger")
    if reuse != {
        "required_before": "FUTURE_CAPTURE_IMPLEMENTATION",
        "orchestration_specific_line_threshold": 150,
        "second_new_capture_consumer": True,
        "required_assessment": "ADOPT_WRAP_FORK_BUILD",
    }:
        raise ValueError("REUSE_TRIGGER_UNRESOLVED")
    audit = _mapping(config.get("audit_assimilation"), "audit_assimilation")
    if audit != {
        "input_sha256": "9ef775756f35199b073acfea0e52db228da9b4d08c30b1194e3d7b1b88886da1",
        "accepted_now": [
            "PROSPECTIVE_CAPTURE_REUSE_TRIGGER",
            "BACKUP_OR_WAIVER_BEFORE_IRRECOVERABLE_CAPTURE",
        ],
        "deferred_trigger": "FAST_PATH_REPAIR_RECURRENCE_OR_MATERIAL_BASELINE_TOUCH",
    }:
        raise ValueError("AUDIT_ASSIMILATION_DRIFT")

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


def evaluate_data_contract(
    config: Mapping[str, Any], frozen_group: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the declared partial-PIT decision without external activity."""
    validate_data_contract(config, frozen_group)
    decision_policy = config["decision_policy"]
    requirements = config["requirements"]
    return {
        "decision": decision_policy["current_decision"],
        "trial_admissible": decision_policy["trial_admissible"],
        "next_boundary": decision_policy["next_boundary"],
        "requirements": {
            requirement_id: {
                "lane": requirement["lane"],
                "state": requirement["state"],
            }
            for requirement_id, requirement in requirements.items()
        },
        "retained_blockers": ["MISSING_UNKNOWN", "UNSUPPORTED"],
        "non_claims": [
            "Partial PIT capture is not a trial.",
            "Route feasibility is not settlement.",
            "Owned execution truth remains future-canary-only.",
        ],
    }


def render_data_contract_readout(result: Mapping[str, Any]) -> str:
    """Render one stable Russian owner readout from the offline result."""
    requirements = _mapping(result.get("requirements"), "OWNER_READOUT_REQUIREMENTS")
    settlement = _mapping(
        requirements.get("settled_execution_truth"), "OWNER_READOUT_SETTLEMENT"
    )
    if (
        result.get("decision") != CURRENT_DECISION
        or result.get("trial_admissible") is not False
        or result.get("next_boundary") != NEXT_BOUNDARY
        or settlement.get("state") != "UNSUPPORTED"
    ):
        raise ValueError("OWNER_READOUT_INPUT")

    return "\n".join(
        [
            "# TASK-30 — H07/H01: какие данные нужны дальше",
            "",
            "## Решение",
            "",
            "Можно подготовить только частичный PIT-capture contract.",
            "Он не является trial и не открывает внешние действия.",
            "",
            "## Что такой capture может дать",
            "",
            "- PIT market: наблюдаемую историю цены и liquidity с явными gaps.",
            "- Route feasibility: доступность route для named notionals.",
            "",
            "## Что он не доказывает",
            "",
            "- Quote или route feasibility не доказывает settlement.",
            "- Owned execution truth остаётся отдельным future-canary blocker.",
            "- Missing/UNKNOWN не становятся нулём, no-trade или settled.",
            "",
            "## Безопасность будущего capture",
            "",
            "Decision-critical невосстановимые raw требуют backup/restore route или explicit waiver до owner gate.",
            "",
            "## Единственный следующий шаг",
            "",
            f"`{NEXT_BOUNDARY}`.",
        ]
    )
