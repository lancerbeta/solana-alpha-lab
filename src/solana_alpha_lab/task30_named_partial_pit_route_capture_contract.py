"""Pure offline decision for a future named TASK-30 technical data-route pilot."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


FROZEN_GROUP_ID = "RC001-H07-H01-LIQUIDITY-RETENTION"
FROZEN_DEFINITION_HASH = (
    "14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7"
)
REFERENCE_POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
EXPECTED_INTERVALS = 96
DECISION = "OWNER_PACKET_READY_EXTERNAL_AUTHORITY_REQUIRED"
UPSTREAM_A8_DECISION = "PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT"
OWNER_INPUT_FIELDS = (
    "provider_selection",
    "endpoint",
    "verified_identity",
    "exact_utc_window",
    "named_lanes_and_notionals",
    "request_cap",
    "quota_and_credential_cap",
    "raw_retention_location_and_hash_plan",
    "backup_or_tracked_waiver",
    "monitoring_owner",
    "recovery_path",
    "non_claims_acknowledged",
)


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(code)
    return value


def _require_value(section: Mapping[str, Any], key: str, value: Any, code: str) -> None:
    if section.get(key) != value:
        raise ValueError(code)


def _require_zeroes(section: Mapping[str, Any]) -> None:
    for key, value in section.items():
        if value not in (0, False):
            raise ValueError(f"AUTHORITY_PROMOTION:{key}")


def validate_capture_contract(
    config: Mapping[str, Any], frozen_group: Mapping[str, Any]
) -> None:
    """Reject any implied authority or research promotion in the A9 contract."""
    _require_value(config, "schema", "smial.task30.named-partial-pit-route-capture.policy", "SCHEMA")
    _require_value(config, "schema_version", "1.0", "SCHEMA_VERSION")
    _require_value(config, "task_id", "TASK-30", "TASK_ID")
    _require_value(config, "atom_id", "T30-A9_NAMED_PARTIAL_PIT_AND_ROUTE_CAPTURE_CONTRACT_V1", "ATOM_ID")
    _require_value(config, "contract_id", "CONTRACT-T30-NAMED-PARTIAL-CAPTURE-001", "CONTRACT_ID")

    frozen = _mapping(config.get("frozen_definition"), "FROZEN_DEFINITION")
    _require_value(frozen, "group_id", FROZEN_GROUP_ID, "FROZEN_GROUP_ID_MISMATCH")
    _require_value(frozen, "definition_sha256", FROZEN_DEFINITION_HASH, "FROZEN_DEFINITION_HASH_MISMATCH")
    _require_value(frozen_group, "group_id", FROZEN_GROUP_ID, "FROZEN_GROUP_INPUT_MISMATCH")
    _require_value(frozen_group, "definition_sha256", FROZEN_DEFINITION_HASH, "FROZEN_GROUP_HASH_INPUT_MISMATCH")

    upstream = _mapping(config.get("upstream_a8"), "UPSTREAM_A8")
    _require_value(
        upstream,
        "path",
        "docs/evidence/task30/a8_h07_h01_exact_data_contract_entry_gate_acceptance_v1.json",
        "UPSTREAM_A8_PATH_MISMATCH",
    )
    _require_value(upstream, "decision", UPSTREAM_A8_DECISION, "UPSTREAM_A8_DECISION_MISMATCH")
    upstream_hash = upstream.get("sha256")
    if not isinstance(upstream_hash, str) or len(upstream_hash) != 64:
        raise ValueError("UPSTREAM_A8_HASH_MISMATCH")

    subject = _mapping(config.get("reference_subject"), "REFERENCE_SUBJECT")
    _require_value(subject, "pool_address", REFERENCE_POOL, "REFERENCE_POOL_MISMATCH")
    _require_value(subject, "target_role", "TECHNICAL_DATA_ROUTE_PILOT", "PILOT_ROLE_MISMATCH")
    _require_value(subject, "representativeness", "NOT_ESTABLISHED", "PILOT_PROMOTION")
    _require_value(subject, "identity_verification", "REQUIRED_AT_LATER_OWNER_GATE", "IDENTITY_GATE_MISMATCH")

    window = _mapping(config.get("pilot_window"), "PILOT_WINDOW")
    _require_value(window, "interval", "15m", "PANEL_SHAPE_MISMATCH")
    _require_value(window, "expected_closed_intervals", EXPECTED_INTERVALS, "PANEL_SHAPE_MISMATCH")
    _require_value(window, "duration_seconds", 86400, "PANEL_SHAPE_MISMATCH")
    _require_value(window, "slot_outcome_policy", "OBSERVATION_OR_TYPED_GAP_REQUIRED", "MISSINGNESS_COERCION")

    lanes = _mapping(config.get("lanes"), "LANES")
    pit_market = _mapping(lanes.get("PIT_MARKET"), "PIT_MARKET")
    _require_value(pit_market, "may_establish", "BOUNDED_MARKET_DATA_ROUTE_CAPABILITY", "PIT_MARKET_PROMOTION")
    _require_value(
        pit_market,
        "cannot_establish",
        ["REPRESENTATIVENESS", "ROUTE_PERSISTENCE", "FILL", "SETTLEMENT", "H07_H01_EVIDENCE"],
        "PILOT_PROMOTION",
    )
    route = _mapping(lanes.get("ROUTE_FEASIBILITY"), "ROUTE_FEASIBILITY")
    _require_value(route, "state", "CONDITIONAL_OWNER_PACKET", "ROUTE_CONDITION_MISMATCH")
    _require_value(route, "may_establish_after_later_gate", "MULTI_NOTIONAL_ROUTE_AVAILABILITY", "ROUTE_PROMOTION")
    _require_value(route, "cannot_establish", ["FILL", "SETTLEMENT", "NETRETURN"], "ROUTE_PROMOTION")
    execution = _mapping(lanes.get("OWNED_EXECUTION"), "OWNED_EXECUTION")
    _require_value(execution, "state", "FUTURE_CANARY_ONLY", "EXECUTION_PROMOTION")
    _require_value(execution, "available_in_this_atom", False, "EXECUTION_PROMOTION")

    route_feasibility = _mapping(config.get("route_feasibility"), "ROUTE_FEASIBILITY_POLICY")
    _require_value(route_feasibility, "state", "CONDITIONAL_OWNER_PACKET", "ROUTE_CONDITION_MISMATCH")
    _require_value(route_feasibility, "notional_buckets", "OWNER_INPUT_REQUIRED", "UNNAMED_NOTIONALS")
    _require_value(route_feasibility, "no_implicit_notional", True, "UNNAMED_NOTIONALS")

    owner_packet = _mapping(config.get("external_owner_packet"), "EXTERNAL_OWNER_PACKET")
    _require_value(owner_packet, "state", "OWNER_INPUT_REQUIRED", "OWNER_PACKET_STATE")
    for field in OWNER_INPUT_FIELDS:
        value = owner_packet.get(field)
        if field == "backup_or_tracked_waiver" and value != "OWNER_INPUT_REQUIRED":
            raise ValueError("RECOVERY_PROTECTION_REQUIRED")
        if field == "provider_selection" and value != "OWNER_INPUT_REQUIRED":
            raise ValueError("PROVIDER_PRESELECTION")
        if field not in {"backup_or_tracked_waiver", "provider_selection"} and value != "OWNER_INPUT_REQUIRED":
            raise ValueError(f"OWNER_INPUT_REQUIRED:{field}")
    _require_value(owner_packet, "fallback_policy", "FORBIDDEN", "FALLBACK_FORBIDDEN")
    _require_value(owner_packet, "provider_api_rpc_wss_calls_authorized", False, "AUTHORITY_PROMOTION")
    _require_value(owner_packet, "credential_use_authorized", False, "AUTHORITY_PROMOTION")

    authority = _mapping(config.get("authority"), "AUTHORITY")
    _require_zeroes(authority)

    non_claims = _mapping(config.get("non_claims"), "NON_CLAIMS")
    _require_value(non_claims, "technical_pilot_only", True, "PILOT_PROMOTION")
    for key, value in non_claims.items():
        if key != "technical_pilot_only" and value is not False:
            if key == "missing_is_zero_or_flat":
                raise ValueError("MISSINGNESS_COERCION")
            raise ValueError("PILOT_PROMOTION")

    decision_policy = _mapping(config.get("decision_policy"), "DECISION_POLICY")
    _require_value(decision_policy, "decision", DECISION, "DECISION_PROMOTION")
    _require_value(decision_policy, "trial_admissible", False, "PILOT_PROMOTION")
    _require_value(decision_policy, "next_boundary", "OWNER_GATE_FOR_NAMED_EXTERNAL_READ_PACKET", "NEXT_BOUNDARY_MISMATCH")
    _require_value(decision_policy, "state_change", "NONE", "STATE_CHANGE_PROMOTION")

    sources = _mapping(config.get("project_sources_disposition"), "PROJECT_SOURCES_DISPOSITION")
    _require_value(sources, "kind", "NO_CHANGE", "PROJECT_SOURCES_DISPOSITION")


def evaluate_capture_contract(
    config: Mapping[str, Any], frozen_group: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the future owner-packet decision without an external action."""
    validate_capture_contract(config, frozen_group)
    subject = config["reference_subject"]
    window = config["pilot_window"]
    return {
        "decision": DECISION,
        "technical_pilot_only": True,
        "external_capture_authorized": False,
        "trial_admissible": False,
        "reference_subject": {
            "pool_address": subject["pool_address"],
            "target_role": subject["target_role"],
            "representativeness": subject["representativeness"],
        },
        "pilot_window": {
            "interval": window["interval"],
            "expected_closed_intervals": window["expected_closed_intervals"],
            "duration_seconds": window["duration_seconds"],
            "slot_outcome_policy": window["slot_outcome_policy"],
        },
        "lanes": {
            "PIT_MARKET": "BOUNDED_MARKET_DATA_ROUTE_CAPABILITY",
            "ROUTE_FEASIBILITY": "CONDITIONAL_OWNER_PACKET",
            "OWNED_EXECUTION": "FUTURE_CANARY_ONLY",
        },
        "later_owner_inputs": list(OWNER_INPUT_FIELDS),
        "stop_conditions": [
            "IDENTITY_UNVERIFIED",
            "UNNAMED_NOTIONALS",
            "RECOVERY_PROTECTION_REQUIRED",
            "MONITORING_OWNER_REQUIRED",
            "FALLBACK_FORBIDDEN",
            "TYPED_GAP_REQUIRED",
        ],
        "non_claims": [
            "Technical data-route pilot is not representative evidence.",
            "Technical data-route pilot is not an H07/H01 trial.",
            "PIT market data and route feasibility do not prove execution or settlement.",
            "Missing data remains a typed gap.",
        ],
        "next_boundary": "OWNER_GATE_FOR_NAMED_EXTERNAL_READ_PACKET",
    }


def render_capture_contract_readout(result: Mapping[str, Any]) -> str:
    """Render a Russian owner-facing description of the offline decision."""
    if (
        result.get("decision") != DECISION
        or result.get("technical_pilot_only") is not True
        or result.get("external_capture_authorized") is not False
        or result.get("trial_admissible") is not False
    ):
        raise ValueError("OWNER_READOUT_PROMOTION")
    window = _mapping(result.get("pilot_window"), "OWNER_READOUT_WINDOW")
    if window.get("expected_closed_intervals") != EXPECTED_INTERVALS:
        raise ValueError("OWNER_READOUT_PANEL_SHAPE")
    return "\n".join(
        [
            "# TASK-30 — пакет будущего технического data-route pilot",
            "",
            "## Решение",
            "",
            "Статус: готово к рассмотрению внешнего owner gate.",
            "Он не разрешает внешний запрос, выбор провайдера или использование ключа.",
            "",
            "## Что именно будет проверяться позже",
            "",
            "- Только техническая пригодность одного data route для указанного pool.",
            "- 96 закрытых 15-минутных UTC интервалов за 24 часа.",
            "- В каждом интервале: наблюдение либо типизированный gap; пропуск не становится нулём.",
            "",
            "## Чего это не доказывает",
            "",
            "- Это не H07/H01 trial и не доказательство репрезентативности.",
            "- PIT market и route feasibility не доказывают execution, fill или settlement.",
            "",
            "## Что должен отдельно связать owner packet",
            "",
            "- Провайдер и endpoint, подтверждённая identity, окно UTC и именованные notionals.",
            "- Лимиты запросов, quota/credential, хранение raw с хешами, backup/waiver.",
            "- Monitoring owner, recovery path и подтверждение non-claims.",
            "",
            "## Стоп",
            "",
            "Без этих значений, при fallback или без typed gap новый запрос блокируется.",
            "",
            "## Следующая граница",
            "",
            "`OWNER_GATE_FOR_NAMED_EXTERNAL_READ_PACKET`.",
        ]
    )
