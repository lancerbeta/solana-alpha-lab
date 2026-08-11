"""Fail-closed offline policy for a future bounded stream owner gate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


EXPECTED_TERMINALS = (
    "PILOT_NOT_AUTHORIZED",
    "CONNECTION_OR_AUTH_REJECTED",
    "SUBSCRIPTION_REJECTED",
    "NO_OBSERVED_TX_NO_EMPTY_CLAIM",
    "OBSERVATION_RETAINED_TECHNICAL_ONLY",
    "TRANSPORT_LOST_UNKNOWN",
    "RETENTION_FAILED_STOP",
)
_FORBIDDEN_DISCLOSURE_KEYS = frozenset(
    {
        "api_key",
        "api_key_value",
        "authorization",
        "credential",
        "endpoint",
        "endpoint_url",
        "password",
        "provider_url",
        "secret",
        "token",
        "url",
    }
)
_ZERO_AUTHORITY_FIELDS = (
    "credential_read",
    "dependency_changes",
    "project_sources_changes",
    "r2_r3_access",
    "raw_data_write",
    "task30_trial_or_acceptance",
    "wallet_signer_transaction_actions",
)
_NON_CLAIM_FIELDS = (
    "complete_coverage_claim",
    "empty_interval_claim",
    "execution_claim",
    "h07_h01_evidence_claim",
    "numeric_netreturn_claim",
    "pit_admissible_claim",
    "pnl_claim",
    "settlement_claim",
    "task30_trial_claim",
    "zero_volume_claim",
)
_FUTURE_PILOT_PHRASE = (
    "T30-A13P_FORWARD_STREAM_PILOT_V1; "
    "pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S; "
    "monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND; "
    "max_wss_connections=1; max_subscriptions=1; "
    "max_open_seconds=1200; max_notifications=500; "
    "retention=A4; retry=false; reconnect=false; fallback=false"
)
_ROOT_FIELDS = frozenset(
    {
        "atom_id",
        "authority",
        "candidate_subscription",
        "consumer",
        "contract_id",
        "decision",
        "execution_controls",
        "frozen_group",
        "non_claims",
        "owner_authority",
        "pilot_limits",
        "project_sources_disposition",
        "provider",
        "schema",
        "schema_version",
        "target",
        "task_id",
        "terminal_truth",
    }
)


class ForwardStreamOwnerPacketError(ValueError):
    """Raised when a packet widens beyond its offline owner-gate boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ForwardStreamOwnerPacketError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(isinstance(key, str) for key in value), code)
    return value


def _contains_forbidden_disclosure_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str) and key.casefold() in _FORBIDDEN_DISCLOSURE_KEYS:
                return True
            if _contains_forbidden_disclosure_key(nested):
                return True
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_disclosure_key(item) for item in value)
    return False


def _contains_forbidden_disclosure_value(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_forbidden_disclosure_value(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_disclosure_value(item) for item in value)
    if not isinstance(value, str):
        return False
    lowered = value.casefold()
    return any(
        marker in lowered
        for marker in (
            "://",
            "api_key=",
            "api-key=",
            "authorization:",
            "bearer ",
        )
    )


def _require_exact_keys(
    value: Mapping[str, Any], expected: frozenset[str], code: str
) -> None:
    _require(frozenset(value) == expected, code)


def _require_exact(
    value: object, expected: object, code: str
) -> None:
    _require(type(value) is type(expected) and value == expected, code)


def _require_identity(config: Mapping[str, Any]) -> None:
    _require_exact(
        config.get("schema"),
        "smial.task30.forward-stream-owner-packet.policy",
        "SCHEMA_DRIFT",
    )
    _require_exact(config.get("schema_version"), "1.0", "SCHEMA_VERSION_DRIFT")
    _require_exact(config.get("task_id"), "TASK-30", "TASK_ID_DRIFT")
    _require_exact(
        config.get("atom_id"),
        "T30-A13_FORWARD_STREAM_OWNER_PACKET_READINESS_V1",
        "ATOM_ID_DRIFT",
    )
    _require_exact(
        config.get("contract_id"),
        "TASK30-FORWARD-STREAM-OWNER-PACKET-V1",
        "CONTRACT_ID_DRIFT",
    )
    _require_exact(
        config.get("consumer"),
        "FUTURE_EXACT_OWNER_EXTERNAL_READ_GATE",
        "CONSUMER_DRIFT",
    )
    _require_exact(
        config.get("frozen_group"),
        "RC001-H07-H01-LIQUIDITY-RETENTION",
        "FROZEN_GROUP_DRIFT",
    )
    target = _mapping(config.get("target"), "TARGET_REQUIRED")
    _require_exact_keys(
        target,
        frozenset({"network", "pool_address", "base_mint", "dex_program_or_route"}),
        "TARGET_FIELDS_DRIFT",
    )
    _require_exact(target.get("network"), "solana", "TARGET_IDENTITY_DRIFT")
    _require_exact(
        target.get("pool_address"),
        "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
        "TARGET_IDENTITY_DRIFT",
    )
    _require_exact(
        target.get("base_mint"),
        "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK",
        "TARGET_IDENTITY_DRIFT",
    )
    _require_exact(
        target.get("dex_program_or_route"),
        "OWNER_VERIFIED_ROUTE_REQUIRED",
        "ROUTE_INFERENCE_FORBIDDEN",
    )


def _require_proposal_only(config: Mapping[str, Any]) -> None:
    provider = _mapping(config.get("provider"), "PROVIDER_REQUIRED")
    _require_exact_keys(
        provider,
        frozenset(
            {"provider_candidate", "provider_selection", "transport_candidate"}
        ),
        "PROVIDER_FIELDS_DRIFT",
    )
    _require_exact(
        provider.get("provider_candidate"),
        "HELIUS_TRANSACTION_SUBSCRIBE",
        "PROVIDER_CANDIDATE_DRIFT",
    )
    _require_exact(
        provider.get("provider_selection"),
        "PROPOSED_NOT_SELECTED",
        "PROVIDER_SELECTION_NOT_PROPOSED",
    )
    _require_exact(
        provider.get("transport_candidate"),
        "WSS_JSON_RPC",
        "TRANSPORT_CANDIDATE_DRIFT",
    )
    subscription = _mapping(
        config.get("candidate_subscription"), "CANDIDATE_SUBSCRIPTION_REQUIRED"
    )
    _require_exact_keys(
        subscription,
        frozenset(
            {
                "account_include",
                "commitment",
                "encoding",
                "failed",
                "max_supported_transaction_version",
                "method",
                "transaction_details",
                "vote",
            }
        ),
        "CANDIDATE_SUBSCRIPTION_FIELDS_DRIFT",
    )
    expected_subscription = {
        "method": "transactionSubscribe",
        "account_include": ["URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"],
        "commitment": "confirmed",
        "encoding": "jsonParsed",
        "transaction_details": "full",
        "max_supported_transaction_version": 0,
        "failed": False,
        "vote": False,
    }
    for field, expected in expected_subscription.items():
        code = (
            "SUBSCRIPTION_FILTER_DRIFT"
            if field == "account_include"
            else "CANDIDATE_SUBSCRIPTION_DRIFT"
        )
        _require_exact(subscription.get(field), expected, code)


def _require_limits_and_execution_controls(config: Mapping[str, Any]) -> None:
    limits = _mapping(config.get("pilot_limits"), "PILOT_LIMITS_REQUIRED")
    _require_exact_keys(
        limits,
        frozenset(
            {"connections", "subscriptions", "open_duration_seconds", "notifications"}
        ),
        "PILOT_LIMIT_FIELDS_DRIFT",
    )
    for field, expected in {
        "connections": 1,
        "subscriptions": 1,
        "open_duration_seconds": 1200,
        "notifications": 500,
    }.items():
        _require_exact(limits.get(field), expected, "PILOT_LIMIT_DRIFT")

    controls = _mapping(
        config.get("execution_controls"), "EXECUTION_CONTROLS_REQUIRED"
    )
    _require_exact_keys(
        controls,
        frozenset(
            {
                "absolute_raw_root",
                "fallback",
                "monitoring_owner",
                "reconnect",
                "retention_class",
                "retry",
                "scheduler",
            }
        ),
        "EXECUTION_CONTROL_FIELDS_DRIFT",
    )
    for field in ("retry", "reconnect", "fallback"):
        _require_exact(
            controls.get(field), False, "RETRY_RECONNECT_FALLBACK_FORBIDDEN"
        )
    _require_exact(
        controls.get("monitoring_owner"),
        "LOCAL_WORK_CODEX_FOREGROUND",
        "MONITORING_OWNER_DRIFT",
    )
    _require_exact(controls.get("scheduler"), False, "SCHEDULER_FORBIDDEN")
    _require_exact(controls.get("retention_class"), "A4", "RETENTION_CLASS_DRIFT")
    _require_exact(
        controls.get("absolute_raw_root"),
        "OWNER_INPUT_REQUIRED",
        "RAW_ROOT_DISCLOSURE_FORBIDDEN",
    )


def _require_zero_authority(config: Mapping[str, Any]) -> None:
    authority = _mapping(config.get("authority"), "AUTHORITY_REQUIRED")
    _require_exact_keys(
        authority,
        frozenset(
            {
                "cash_spend_usd",
                "credential_read",
                "dependency_changes",
                "project_sources_changes",
                "provider_api_rpc_wss_calls",
                "r2_r3_access",
                "raw_data_write",
                "task30_trial_or_acceptance",
                "wallet_signer_transaction_actions",
            }
        ),
        "AUTHORITY_FIELDS_DRIFT",
    )
    _require_exact(
        authority.get("provider_api_rpc_wss_calls"), 0, "ZERO_AUTHORITY_REQUIRED"
    )
    _require_exact(authority.get("cash_spend_usd"), 0, "ZERO_AUTHORITY_REQUIRED")
    for field in _ZERO_AUTHORITY_FIELDS:
        _require_exact(authority.get(field), False, "ZERO_AUTHORITY_REQUIRED")


def _require_terminal_truth(config: Mapping[str, Any]) -> None:
    terminal_truth = _mapping(config.get("terminal_truth"), "TERMINAL_TRUTH_REQUIRED")
    _require_exact_keys(
        terminal_truth,
        frozenset(
            {
                "allowed_terminal_states",
                "no_observation_disposition",
                "transport_loss_disposition",
                "unknown_recovery",
            }
        ),
        "TERMINAL_TRUTH_FIELDS_DRIFT",
    )
    _require_exact(
        tuple(terminal_truth.get("allowed_terminal_states", ())),
        EXPECTED_TERMINALS,
        "TERMINAL_ENUM_DRIFT",
    )
    _require_exact(
        terminal_truth.get("no_observation_disposition"),
        "NO_OBSERVED_TX_NO_EMPTY_CLAIM",
        "NO_OBSERVATION_PROMOTION_FORBIDDEN",
    )
    _require_exact(
        terminal_truth.get("transport_loss_disposition"),
        "TRANSPORT_LOST_UNKNOWN",
        "TRANSPORT_LOSS_PROMOTION_FORBIDDEN",
    )
    recovery = _mapping(
        terminal_truth.get("unknown_recovery"), "UNKNOWN_RECOVERY_REQUIRED"
    )
    _require_exact_keys(
        recovery,
        frozenset(
            {
                "automatic_reconciliation",
                "interval_projection",
                "reconciliation_reference",
                "retry_before_reconciliation",
            }
        ),
        "UNKNOWN_RECOVERY_FIELDS_DRIFT",
    )
    for field, expected in {
        "reconciliation_reference": "OWNER_AUTHORITY_REQUIRED",
        "automatic_reconciliation": False,
        "retry_before_reconciliation": False,
        "interval_projection": False,
    }.items():
        _require_exact(recovery.get(field), expected, "UNKNOWN_RECOVERY_DRIFT")


def _require_owner_and_non_claims(config: Mapping[str, Any]) -> None:
    owner_authority = _mapping(
        config.get("owner_authority"), "OWNER_AUTHORITY_REQUIRED"
    )
    _require_exact_keys(
        owner_authority,
        frozenset(
            {"future_pilot_authorized", "future_pilot_phrase", "stop_procedure"}
        ),
        "OWNER_AUTHORITY_FIELDS_DRIFT",
    )
    _require_exact(
        owner_authority.get("future_pilot_phrase"),
        _FUTURE_PILOT_PHRASE,
        "OWNER_PHRASE_DRIFT",
    )
    _require_exact(
        owner_authority.get("future_pilot_authorized"),
        False,
        "OWNER_AUTHORITY_PROMOTION_FORBIDDEN",
    )
    _require_exact(
        owner_authority.get("stop_procedure"),
        "STOP_AND_RETAIN_SAFE_RECEIPT",
        "STOP_PROCEDURE_DRIFT",
    )
    non_claims = _mapping(config.get("non_claims"), "NON_CLAIMS_REQUIRED")
    _require_exact_keys(non_claims, frozenset(_NON_CLAIM_FIELDS), "NON_CLAIM_FIELDS_DRIFT")
    for field in _NON_CLAIM_FIELDS:
        _require_exact(non_claims.get(field), False, "PROMOTION_CLAIM_FORBIDDEN")


def evaluate_forward_stream_owner_packet(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a no-I/O owner-gate packet and return its sole safe decision."""
    _require(
        not _contains_forbidden_disclosure_key(config)
        and not _contains_forbidden_disclosure_value(config),
        "CREDENTIAL_OR_ENDPOINT_DISCLOSURE_FORBIDDEN",
    )
    _require_exact_keys(config, _ROOT_FIELDS, "ROOT_FIELDS_DRIFT")
    _require_identity(config)
    _require_proposal_only(config)
    _require_limits_and_execution_controls(config)
    _require_zero_authority(config)
    _require_terminal_truth(config)
    _require_owner_and_non_claims(config)
    _require_exact(
        config.get("decision"),
        "READY_FOR_OWNER_EXTERNAL_READ_GATE_WITH_LIMITATIONS",
        "DECISION_PROMOTION_FORBIDDEN",
    )
    _require_exact(
        config.get("project_sources_disposition"),
        "NO_CHANGE",
        "SOURCE_DISPOSITION_DRIFT",
    )
    return {
        "decision": "READY_FOR_OWNER_EXTERNAL_READ_GATE_WITH_LIMITATIONS",
        "external_action_authorized": False,
        "next_action": "OWNER_EXTERNAL_READ_GATE_REQUIRED",
        "project_sources_disposition": "NO_CHANGE",
        "provider_selection": "PROPOSED_NOT_SELECTED",
    }


def render_forward_stream_owner_packet(config: Mapping[str, Any]) -> str:
    """Render the validated future gate in plain Russian without execution data."""
    evaluate_forward_stream_owner_packet(config)
    target = _mapping(config["target"], "TARGET_REQUIRED")
    limits = _mapping(config["pilot_limits"], "PILOT_LIMITS_REQUIRED")
    controls = _mapping(config["execution_controls"], "EXECUTION_CONTROLS_REQUIRED")
    owner_authority = _mapping(config["owner_authority"], "OWNER_AUTHORITY_REQUIRED")
    duration = f"{limits['open_duration_seconds']:,}".replace(",", " ")
    return "\n".join(
        (
            "# Пакет готовности будущего stream-пилота",
            "",
            "Это предложение одного технического чтения и не является сделкой.",
            f"Цель: пул {target['pool_address']} и base mint {target['base_mint']}.",
            "Возможный поставщик пока только предложен, но не выбран.",
            "Лимиты будущего запуска: 1 соединение, 1 подписка, "
            f"{duration} секунд и {limits['notifications']} уведомлений.",
            "Запуск только в foreground; retry, reconnect и fallback запрещены.",
            f"Raw-данные могут сохраняться только после отдельного gate по retention {controls['retention_class']} вне Git.",
            "Потеря транспорта остаётся UNKNOWN: остановиться, сохранить безопасный receipt и не повторять до отдельного reconcile gate.",
            "Ни пустой интервал, ни нулевой объём, ни полнота покрытия здесь не заявляются.",
            "",
            "Точная будущая фраза разрешения:",
            str(owner_authority["future_pilot_phrase"]),
        )
    ) + "\n"
