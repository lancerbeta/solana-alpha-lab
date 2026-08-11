"""Pure offline validation for the TASK-30 forward raw-trade route."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


FROZEN_GROUP_ID = "RC001-H07-H01-LIQUIDITY-RETENTION"
FROZEN_PARAMETER_ID = "OBSERVATION_WINDOW_15M"
REFERENCE_POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
EXPECTED_COVERAGE_STATES = [
    "COMPLETE",
    "GAP_SUSPECTED",
    "UNKNOWN",
    "RECONCILED",
    "INVALID",
    "STOPPED",
]
OBSERVED_FIELDS = (
    "connection_epoch",
    "signature",
    "pool_address",
    "source_route",
    "observed_at",
    "available_at",
    "ingested_at",
    "slot",
    "interval_start",
    "raw_sha256",
)
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ForwardRawTradeRouteError(ValueError):
    """Raised when an offline record weakens a forward-route invariant."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ForwardRawTradeRouteError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _exact(mapping: Mapping[str, Any], key: str, expected: object, code: str) -> None:
    _require(mapping.get(key) == expected, code)


def _require_zero_authority(policy: Mapping[str, Any]) -> None:
    authority = _mapping(policy.get("authority"), "AUTHORITY_INVALID")
    for value in authority.values():
        _require(value in (0, False), "AUTHORITY_PROMOTION")


def validate_forward_raw_trade_route_policy(
    policy: Mapping[str, Any],
    frozen_group: Mapping[str, Any],
) -> None:
    """Fail closed unless the tracked policy remains an offline contract."""

    _exact(policy, "schema", "smial.task30.forward-raw-trade-route.policy", "SCHEMA_INVALID")
    _exact(policy, "schema_version", "1.0", "SCHEMA_VERSION_INVALID")
    _exact(policy, "task_id", "TASK-30", "TASK_ID_INVALID")
    _exact(
        policy,
        "atom_id",
        "T30-A12_FORWARD_RAW_TRADE_ROUTE_OFFLINE_CONTRACT_V1",
        "ATOM_ID_INVALID",
    )
    _exact(
        policy,
        "consumer",
        "RC001-H07-H01-LIQUIDITY-RETENTION_FORWARD_DATA_ENTRY_GATE",
        "CONSUMER_INVALID",
    )

    frozen = _mapping(policy.get("frozen_definition"), "FROZEN_DEFINITION_INVALID")
    _exact(frozen, "group_id", FROZEN_GROUP_ID, "FROZEN_GROUP_INVALID")
    _exact(frozen, "parameter_id", FROZEN_PARAMETER_ID, "FROZEN_PARAMETER_INVALID")
    _exact(frozen, "interval_seconds", 900, "INTERVAL_INVALID")
    _exact(frozen_group, "group_id", FROZEN_GROUP_ID, "FROZEN_GROUP_MISMATCH")

    subject = _mapping(policy.get("reference_subject"), "REFERENCE_SUBJECT_INVALID")
    _exact(subject, "pool_address", REFERENCE_POOL, "POOL_IDENTITY")
    _exact(subject, "representativeness", "NOT_ESTABLISHED", "REPRESENTATIVENESS_PROMOTION")

    route = _mapping(policy.get("future_route"), "FUTURE_ROUTE_INVALID")
    for field in ("selected_provider", "selected_endpoint", "selected_transport"):
        _exact(route, field, None, "PROVIDER_SELECTION_FORBIDDEN")
    _exact(route, "external_owner_packet", "REQUIRED", "OWNER_PACKET_INVALID")

    _exact(policy, "coverage_states", EXPECTED_COVERAGE_STATES, "COVERAGE_STATES_INVALID")
    reconciliation = _mapping(policy.get("reconciliation"), "RECONCILIATION_INVALID")
    _exact(reconciliation, "unresolved_transport_loss", "UNKNOWN_STOP_RUN", "LOSS_POLICY_INVALID")
    _exact(reconciliation, "reconnect_before_reconciliation", "FORBIDDEN", "RECONNECT_POLICY_INVALID")
    _exact(reconciliation, "projection_from_unknown", "FORBIDDEN", "UNKNOWN_PROJECTION_INVALID")

    _require_zero_authority(policy)
    claims = _mapping(policy.get("non_claims"), "NON_CLAIMS_INVALID")
    _require(all(value is False for value in claims.values()), "CLAIM_PROMOTION")
    _exact(policy, "project_sources_disposition", "NO_CHANGE", "SOURCES_CHANGE_FORBIDDEN")


def _require_observed(event: Mapping[str, Any], signatures: set[tuple[str, str]]) -> None:
    for field in OBSERVED_FIELDS:
        if field == "raw_sha256":
            continue
        _require(field in event, f"OBSERVED_FIELD:{field}")
    for field in ("connection_epoch", "signature", "source_route"):
        _require(isinstance(event[field], str) and event[field], f"OBSERVED_TEXT:{field}")
    _exact(event, "pool_address", REFERENCE_POOL, "POOL_IDENTITY")
    _exact(event, "source_route", "SYNTHETIC_FORWARD_ROUTE", "SOURCE_ROUTE_INVALID")

    epoch = event["connection_epoch"]
    signature = event["signature"]
    assert isinstance(epoch, str)
    assert isinstance(signature, str)
    identity = (epoch, signature)
    _require(identity not in signatures, "DUPLICATE_SIGNATURE")
    signatures.add(identity)

    for field in ("observed_at", "available_at", "ingested_at", "slot", "interval_start"):
        _require(isinstance(event[field], int) and not isinstance(event[field], bool), f"OBSERVED_INT:{field}")
    _require(event["observed_at"] <= event["available_at"] <= event["ingested_at"], "TIME_ORDER")
    _require(event["slot"] >= 0, "SLOT_INVALID")
    _require(event["interval_start"] >= 0 and event["interval_start"] % 900 == 0, "INTERVAL_INVALID")

    raw_hash = event.get("raw_sha256")
    _require(isinstance(raw_hash, str) and HEX_SHA256.fullmatch(raw_hash) is not None, "RAW_HASH")


def _require_transport_loss(event: Mapping[str, Any]) -> None:
    _require(isinstance(event.get("connection_epoch"), str) and event["connection_epoch"], "LOSS_EPOCH")
    for field in ("lost_at", "last_observed_slot"):
        _require(isinstance(event.get(field), int) and not isinstance(event[field], bool), f"LOSS_FIELD:{field}")


def evaluate_forward_coverage(
    policy: Mapping[str, Any],
    frozen_group: Mapping[str, Any],
    events: object,
) -> dict[str, object]:
    """Evaluate only synthetic route coverage; this function performs no I/O."""

    validate_forward_raw_trade_route_policy(policy, frozen_group)
    _require(isinstance(events, list) and events, "EVENTS_INVALID")

    signatures: set[tuple[str, str]] = set()
    unresolved_loss = False
    observed_records = 0
    for raw_event in events:
        event = _mapping(raw_event, "EVENT_INVALID")
        _require(event.get("retry", False) is False, "RETRY_FORBIDDEN")
        _require(event.get("fallback", False) is False, "FALLBACK_FORBIDDEN")
        state = event.get("state")
        if state == "OBSERVED":
            _require(not unresolved_loss, "OBSERVED_BEFORE_RECONCILIATION")
            _require_observed(event, signatures)
            observed_records += 1
        elif state == "TRANSPORT_LOST":
            _require(not unresolved_loss, "DUPLICATE_TRANSPORT_LOSS")
            _require_transport_loss(event)
            unresolved_loss = True
        elif state == "RECONCILIATION":
            _require(unresolved_loss, "RECONCILIATION_WITHOUT_LOSS")
            _require(
                isinstance(event.get("reconciliation_id"), str) and event["reconciliation_id"],
                "RECONCILIATION_ID",
            )
            _exact(event, "coverage_state", "RECONCILED", "RECONCILIATION_STATE")
            unresolved_loss = False
        elif state == "RECONNECTED":
            _require(not unresolved_loss, "RECONNECT_BEFORE_RECONCILIATION")
            _require(
                isinstance(event.get("connection_epoch"), str) and event["connection_epoch"],
                "RECONNECT_EPOCH",
            )
        elif state == "EMPTY_INTERVAL":
            raise ForwardRawTradeRouteError("EMPTY_COERCION")
        else:
            raise ForwardRawTradeRouteError("EVENT_STATE_INVALID")

    if unresolved_loss:
        return {
            "coverage_state": "UNKNOWN",
            "projection_state": "UNKNOWN",
            "interval_projectable": False,
            "external_capture_authorized": False,
            "execution_disposition": "STOP_RUN",
            "observed_record_count": observed_records,
            "claims": _non_claims(),
        }

    _require(observed_records > 0, "OBSERVED_RECORD_REQUIRED")
    return {
        "coverage_state": "COMPLETE",
        "projection_state": "OFFLINE_CONTRACT_VALIDATED",
        "interval_projectable": False,
        "external_capture_authorized": False,
        "execution_disposition": "OWNER_PACKET_REQUIRED",
        "observed_record_count": observed_records,
        "claims": _non_claims(),
    }


def _non_claims() -> dict[str, bool]:
    return {
        "provider_selected": False,
        "pit_admissible": False,
        "h07_h01_evidence": False,
        "task30_trial": False,
        "execution": False,
        "settlement": False,
        "pnl": False,
        "numeric_netreturn": False,
        "missing_is_zero_or_flat": False,
    }


def render_forward_raw_trade_route_readout(result: Mapping[str, Any]) -> str:
    """Render a deterministic Russian explanation of an offline outcome."""

    projection_state = result.get("projection_state")
    disposition = result.get("execution_disposition")
    _require(projection_state in {"OFFLINE_CONTRACT_VALIDATED", "UNKNOWN"}, "READOUT_STATE_INVALID")
    _require(disposition in {"OWNER_PACKET_REQUIRED", "STOP_RUN"}, "READOUT_DISPOSITION_INVALID")
    _require(result.get("external_capture_authorized") is False, "READOUT_AUTHORITY_PROMOTION")

    if projection_state == "UNKNOWN":
        status = "Статус: покрытие неизвестно; маршрут остановлен до reconciliation."
        next_step = "Нужен отдельный reconciliation boundary, а не reconnect или повтор."
    else:
        status = "Статус: офлайн-контракт проверен; будущий owner packet ещё обязателен."
        next_step = "Следующая граница — отдельное решение owner о внешнем техническом pilot."

    return "\n".join(
        [
            "# TASK-30 — forward raw trade route",
            "",
            "## Решение",
            "",
            status,
            "Он не разрешает внешний запрос, выбор провайдера или использование ключа.",
            "",
            "## Что зафиксировано",
            "",
            "- Наблюдение, transport loss и unknown coverage различаются явно.",
            "- Unknown не становится пустым интервалом, нулём или complete data.",
            "- Дубликат signature, неверный pool, retry, fallback и reconnect до reconciliation блокируются.",
            "",
            "## Следующая граница",
            "",
            next_step,
        ]
    )
