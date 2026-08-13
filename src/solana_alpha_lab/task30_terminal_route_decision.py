"""Fail-closed offline terminal decision for the current TASK-30 data route."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DECISION = "CLOSE_CURRENT_DATA_ROUTE_LIMITED_NEGATIVE_RESULT"
EXPECTED_CONSUMER = "RC001-H07-H01-LIQUIDITY-RETENTION"
EXPECTED_REOPEN_TRIGGER = "NAMED_CONSUMER_PLUS_REPRODUCIBLE_PIT_ROUTE_AND_EXECUTION_TRUTH"
EXPECTED_EVIDENCE = {
    "task30_a5r1_birdeye": {
        "path": "docs/evidence/task30/a5r1_birdeye_v3_external_read_runtime_receipt_v1.json",
        "sha256": "a4f69df4dcff2afe88c06828884ec9155af8bfe91b659080cfed74ab1acbcdf1",
        "observed_decision": "PAIR_IDENTITY_ACCEPTED_OHLCV_RATE_OR_QUOTA_LIMITED",
    },
    "task30_a11e_gecko": {
        "path": "docs/evidence/task30/a11e_gecko_15m_live_shakedown_runtime_receipt_v1.json",
        "sha256": "28d246c97a7e6866760683c6e63296f9d310a2cce35ac98be61e107af9f7bcdb",
        "observed_decision": "CLOSE_CURRENT_15M_FAST_FRESHNESS_ROUTE",
    },
    "task30_a14p_r2": {
        "path": "docs/evidence/task30/a14p_r2_forward_stream_external_capture_receipt_v1.json",
        "sha256": "179c2b26c6a6d325388ec04c388fae8efa4adc8ba01639c85c70e5626e405604",
        "observed_decision": "HELIUS_TRANSACTION_SUBSCRIBE_FREE_PLAN_NOT_AVAILABLE",
    },
    "task30_a15p": {
        "path": "docs/evidence/task30/a15p_standard_pool_logs_runtime_receipt_v1.json",
        "sha256": "ee40a42a49bb470b4cde81d5d7b59bbb3209ecfa8aecd9e73b92f01a0beffbf7",
        "observed_decision": "HELIUS_STANDARD_WSS_AVAILABLE_CAPTURE_YIELD_UNRESOLVED",
    },
    "task30_a16p": {
        "path": "docs/evidence/task30/a16p_pool_activity_discriminator_runtime_receipt_v2.json",
        "sha256": "32868bff924719ba364ec0ed07e63436764a4c86032b6624f1e6439656edfe52",
        "observed_decision": "NO_DIRECT_POOL_ACTIVITY_SUPPORTED",
    },
    "task30_a17": {
        "path": "docs/evidence/task30/a17_active_pool_route_yield_acceptance_v1.json",
        "sha256": "3647b41e13ed4e16da9927de196c39c4feac17bc062f8d17df22d61a2c1bc48e",
        "observed_decision": "OFFLINE_ACTIVE_POOL_ROUTE_YIELD_READY_FOR_OWNER_GATE",
    },
    "task30_a18_readiness": {
        "path": "docs/evidence/task30/a18_single_signature_transaction_readiness_acceptance_v1.json",
        "sha256": "fdad06e5e88f06334c31899416010980e3a2961820640f8e3af65f248a8e6c46",
        "observed_decision": "OFFLINE_CLASSIFIER_READY_FOR_OWNER_EXTERNAL_GATE",
    },
    "task30_a18_runtime": {
        "path": "docs/evidence/task30/a18_single_signature_transaction_readiness_runtime_receipt_v1.json",
        "sha256": "eea7b1e1a45aa862bd2a8fb65ba32e430ceeb525c8f8870169986930c6b67448",
        "observed_decision": "TRANSPORT_OR_COVERAGE_UNKNOWN",
    },
}
AUTHORITY_KEYS = (
    "provider_api_rpc_wss_calls",
    "credential_reads",
    "raw_external_data_writes",
    "scheduler_or_background_processes",
    "r2_r3_access",
    "wallet_signer_transaction_actions",
    "cash_spend_usd_cents",
    "task30_trial_or_acceptance_actions",
)
CLAIM_KEYS = (
    "pit_admissible",
    "h07_h01_evidence",
    "task30_trial",
    "price",
    "volume",
    "alpha",
    "strategy",
    "execution",
    "settlement",
    "pnl",
    "numeric_netreturn",
    "owner_cashflow",
    "missing_is_zero_or_flat",
)


class TerminalRouteDecisionError(ValueError):
    """Raised when the terminal route decision is weakened or detached."""


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TerminalRouteDecisionError(code)
    return value


def _exact(value: Any, expected: Any, code: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise TerminalRouteDecisionError(code)


def validate_terminal_decision(config: Mapping[str, Any]) -> None:
    """Validate the single permitted terminal decision without I/O."""
    for key, expected, code in (
        ("schema", "smial.task30.terminal-route-decision.policy", "SCHEMA_DRIFT"),
        ("schema_version", "1.0", "SCHEMA_VERSION_DRIFT"),
        ("task_id", "TASK-30", "TASK_ID_DRIFT"),
        ("atom_id", "T30-A19_TERMINAL_ROUTE_DECISION_V1", "ATOM_ID_DRIFT"),
        ("contract_id", "TASK30-A19-TERMINAL-ROUTE-DECISION-V1", "CONTRACT_ID_DRIFT"),
        ("spec_route", "PRD_LITE", "SPEC_ROUTE_DRIFT"),
        ("consumer", EXPECTED_CONSUMER, "CONSUMER_DRIFT"),
        ("route_scope", "TASK30_CURRENT_NAMED_PUBLIC_FREE_DATA_ROUTE", "ROUTE_SCOPE_DRIFT"),
        ("decision", DECISION, "DECISION_PROMOTION_OR_DRIFT"),
        ("route_closed", True, "ROUTE_NOT_CLOSED"),
        ("hypothesis_closed", False, "HYPOTHESIS_CLOSED_BY_ROUTE"),
        ("provider_globally_unavailable", False, "GLOBAL_PROVIDER_CLAIM"),
        ("h07_h01_state", "BLOCKED_DATA", "H07_H01_STATE_DRIFT"),
        ("trial_admissible", False, "TRIAL_PROMOTION"),
        ("next_owner_gate", "NONE_UNTIL_NAMED_REOPEN_TRIGGER", "NEXT_GATE_DRIFT"),
        ("reopen_trigger", EXPECTED_REOPEN_TRIGGER, "REOPEN_TRIGGER_DRIFT"),
        ("project_sources_disposition", "NO_CHANGE", "SOURCE_CHANGE_FORBIDDEN"),
        ("state_change", "NONE", "STATE_CHANGE_FORBIDDEN"),
    ):
        _exact(config.get(key), expected, code)

    evidence = _mapping(config.get("evidence"), "EVIDENCE_REQUIRED")
    _exact(set(evidence), set(EXPECTED_EVIDENCE), "EVIDENCE_SET_DRIFT")
    for evidence_id, expected in EXPECTED_EVIDENCE.items():
        item = _mapping(evidence.get(evidence_id), f"EVIDENCE_ITEM:{evidence_id}")
        _exact(dict(item), expected, f"EVIDENCE_BINDING_DRIFT:{evidence_id}")

    authority = _mapping(config.get("authority"), "AUTHORITY_REQUIRED")
    _exact(set(authority), set(AUTHORITY_KEYS), "AUTHORITY_SET_DRIFT")
    for key in AUTHORITY_KEYS:
        _exact(authority.get(key), 0, f"AUTHORITY_NONZERO:{key}")

    claims = _mapping(config.get("claims"), "CLAIMS_REQUIRED")
    _exact(set(claims), set(CLAIM_KEYS), "CLAIMS_SET_DRIFT")
    for key in CLAIM_KEYS:
        _exact(claims.get(key), False, f"CLAIM_PROMOTION:{key}")


def evaluate_terminal_decision(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable owner readout from the hash-bound offline policy."""
    validate_terminal_decision(config)
    return {
        "decision": DECISION,
        "route_scope": config["route_scope"],
        "h07_h01_state": config["h07_h01_state"],
        "hypothesis_closed": False,
        "provider_globally_unavailable": False,
        "next_owner_gate": config["next_owner_gate"],
        "reopen_trigger": config["reopen_trigger"],
        "summary": (
            "Текущий именованный public/free маршрут закрыт с ограниченным "
            "отрицательным результатом; H07/H01 остаются BLOCKED_DATA."
        ),
        "non_claims": [
            "Это не закрытие гипотезы и не доказательство непригодности всех провайдеров.",
            "UNKNOWN не означает inactive, zero, flat, no-trade или settled.",
            "Нет trial, price/volume panel, execution, settlement, PnL, NetReturn или cashflow.",
        ],
    }


def render_terminal_readout(result: Mapping[str, Any]) -> str:
    if result.get("decision") != DECISION or result.get("h07_h01_state") != "BLOCKED_DATA":
        raise TerminalRouteDecisionError("READOUT_INPUT")
    lines = [
        "# TASK-30 — terminal route decision",
        "",
        "## Решение",
        "",
        "`CLOSE_CURRENT_DATA_ROUTE_LIMITED_NEGATIVE_RESULT`",
        "",
        str(result["summary"]),
        "",
        "## Что это значит",
        "",
        "- Текущий именованный public/free data-route больше не продолжаем.",
        "- `RC001-H07-H01-LIQUIDITY-RETENTION` остаётся `BLOCKED_DATA`.",
        "- Новых provider/API/RPC/WSS-запросов не требуется.",
        "",
        "## Что не утверждается",
        "",
    ]
    lines.extend(f"- {item}" for item in result["non_claims"])
    lines.extend(
        [
            "",
            "## Когда можно открыть маршрут снова",
            "",
            f"Только при `{result['reopen_trigger']}` через новый owner gate.",
            "",
        ]
    )
    return "\n".join(lines)
