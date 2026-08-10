from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class TwoSlotOwnerPacketError(ValueError):
    """Raised when an offline owner packet weakens a safety boundary."""


_EXPECTED_POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
_EXPECTED_OFFSETS = [0, 15, 30, 60]
_ZERO_AUTHORITY = {
    "provider_api_rpc_wss_calls": 0,
    "credential_use": 0,
    "raw_data_writes": 0,
    "scheduler_or_background_processes": 0,
    "r2_r3_access": 0,
    "wallet_signer_transaction_actions": 0,
    "cash_spend_usd_cents": 0,
    "task30_trial_or_acceptance_actions": 0,
}
_FALSE_NON_CLAIMS = (
    "pit_admissible",
    "h07_h01_evidence",
    "task30_trial",
    "execution",
    "settlement",
    "pnl",
    "numeric_netreturn",
    "provider_selected",
    "external_capture_authorized",
    "twenty_four_hour_capture_authorized",
    "missing_is_zero_or_flat",
)


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TwoSlotOwnerPacketError(f"{path}: expected mapping")
    return value


def _expect(mapping: Mapping[str, Any], key: str, expected: object, path: str) -> None:
    actual = mapping.get(key)
    if actual != expected:
        raise TwoSlotOwnerPacketError(
            f"{path}.{key}: expected {expected!r}, got {actual!r}"
        )


def validate_owner_packet(packet: Mapping[str, Any]) -> dict[str, object]:
    """Return a non-executable owner-review result or fail closed."""

    root = _mapping(packet, "packet")
    expected_root = {
        "schema": "smial.task30.two-slot-live-shakedown-owner-packet",
        "schema_version": "1.0",
        "task_id": "TASK-30",
        "atom_id": "T30-A11B_TWO_SLOT_LIVE_SHAKEDOWN_OWNER_PACKET_V1",
        "status": "OWNER_APPROVAL_REQUIRED",
        "provider_candidate": "GECKOTERMINAL_PUBLIC_KEYLESS",
        "provider_selected": False,
        "external_capture_authorized": False,
        "project_sources_disposition": "NO_CHANGE",
    }
    for key, expected in expected_root.items():
        _expect(root, key, expected, "packet")

    binding = _mapping(root.get("frozen_binding"), "packet.frozen_binding")
    for key, expected in {
        "group_id": "RC001-H07-H01-LIQUIDITY-RETENTION",
        "interval_seconds": 900,
        "pool_address": _EXPECTED_POOL,
        "network": "solana",
    }.items():
        _expect(binding, key, expected, "packet.frozen_binding")
    _expect(
        _mapping(binding.get("upstream_a10"), "packet.frozen_binding.upstream_a10"),
        "decision",
        "START_LABELED",
        "packet.frozen_binding.upstream_a10",
    )
    _expect(
        _mapping(binding.get("upstream_a11a"), "packet.frozen_binding.upstream_a11a"),
        "decision",
        "OFFLINE_PROBE_POLICY_VALIDATED",
        "packet.frozen_binding.upstream_a11a",
    )

    request = _mapping(root.get("future_request_proposal"), "packet.future_request_proposal")
    for key, expected in {
        "method": "GET",
        "public_base_url": "https://api.geckoterminal.com/api/v2",
        "path_template": "/networks/solana/pools/{pool}/ohlcv/minute",
        "credentials": False,
        "retry": False,
        "fallback": False,
    }.items():
        _expect(request, key, expected, "packet.future_request_proposal")
    query = _mapping(request.get("query"), "packet.future_request_proposal.query")
    for key, expected in {
        "aggregate": "15",
        "currency": "usd",
        "token": "base",
        "include_empty_intervals": "false",
        "limit": "1",
        "before_timestamp": "OWNER_BOUND_SLOT_END_UTC",
    }.items():
        _expect(query, key, expected, "packet.future_request_proposal.query")

    shape = _mapping(root.get("shakedown_shape"), "packet.shakedown_shape")
    for key, expected in {
        "slot_count": 2,
        "interval_seconds": 900,
        "offset_seconds": _EXPECTED_OFFSETS,
        "max_provider_gets": 8,
        "separate_foreground_starts": True,
        "second_slot_requires_prior_receipt": True,
        "future_slot_starts_utc": "OWNER_INPUT_REQUIRED",
    }.items():
        _expect(shape, key, expected, "packet.shakedown_shape")

    retention = _mapping(root.get("retention"), "packet.retention")
    for key, expected in {
        "policy": "A4",
        "raw_json_outside_git": True,
        "raw_manifest_required_after_every_response": True,
        "immediate_hash_required": True,
    }.items():
        _expect(retention, key, expected, "packet.retention")

    monitoring = _mapping(root.get("monitoring"), "packet.monitoring")
    for key, expected in {
        "owner": "OWNER_INPUT_REQUIRED",
        "health_receipt_required": True,
        "stop_on_monitoring_loss": True,
    }.items():
        _expect(monitoring, key, expected, "packet.monitoring")

    recovery = _mapping(root.get("recovery"), "packet.recovery")
    for key in (
        "stop_on_process_not_started",
        "stop_on_receipt_write_failed",
        "stop_on_prior_manifest_unreadable",
        "stop_on_monitoring_lost",
    ):
        _expect(recovery, key, True, "packet.recovery")
    for key in ("retry_allowed", "fallback_allowed", "silent_restart_allowed"):
        _expect(recovery, key, False, "packet.recovery")

    authority = _mapping(root.get("current_atom_authority"), "packet.current_atom_authority")
    for key, expected in _ZERO_AUTHORITY.items():
        _expect(authority, key, expected, "packet.current_atom_authority")

    non_claims = _mapping(root.get("non_claims"), "packet.non_claims")
    for key in _FALSE_NON_CLAIMS:
        _expect(non_claims, key, False, "packet.non_claims")

    return {
        "status": "OWNER_APPROVAL_REQUIRED",
        "external_capture_authorized": False,
        "max_provider_gets": 8,
        "provider_candidate": "GECKOTERMINAL_PUBLIC_KEYLESS",
        "next_boundary": "EXACT_OWNER_EXTERNAL_READ_AUTHORIZATION",
    }


def render_owner_packet_markdown(packet: Mapping[str, Any]) -> str:
    """Render the validated offline owner packet without enabling a request."""

    result = validate_owner_packet(packet)
    binding = _mapping(packet.get("frozen_binding"), "packet.frozen_binding")
    shape = _mapping(packet.get("shakedown_shape"), "packet.shakedown_shape")
    return "\n".join(
        (
            "# TASK-30: пакет owner-review для двухслотового shakedown",
            "",
            "## Что подготовлено",
            "",
            "Офлайн-пакет для двух независимых foreground-проверок "
            "закрытой 15-минутной свечи.",
            "",
            "## Предлагаемая граница будущего запроса",
            "",
            f"- Candidate: {result['provider_candidate']} для pool {binding['pool_address']}.",
            f"- Ровно {shape['slot_count']} closed slots и {result['max_provider_gets']} публичных GET максимум.",
            "- Offsets: 0, 15, 30 и 60 секунд; retry и fallback запрещены.",
            "- Raw JSON будет храниться вне Git по A4 с manifest/hash после каждого ответа.",
            "",
            "## Что это не разрешает",
            "",
            "Этот пакет не разрешает внешний запрос, не выбирает provider и не запускает scheduler.",
            "Точные UTC slots и monitoring owner остаются OWNER_INPUT_REQUIRED.",
            "Потеря monitoring или отсутствующий prior receipt означает STOP_RUN, а не тихий restart.",
            "",
            "## Следующая граница",
            "",
            f"Статус: {result['status']}. Нужен отдельный owner gate: {result['next_boundary']}.",
            "Ни один результат будущего shakedown сам по себе не разрешит 24-hour capture.",
            "",
        )
    )
