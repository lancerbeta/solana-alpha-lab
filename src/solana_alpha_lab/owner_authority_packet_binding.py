"""Offline validation for a future owner canary authority packet.

This module never creates a wallet, signer, transaction, quote, or network call.
It only classifies synthetic packet-shaped data for owner review.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


TASK_ID = "OWNER_AUTHORITY_PACKET_BINDING_V1"
ATOM_ID = "OWNER_AUTHORITY_PACKET_BINDING_V1"
AS_OF = "2026-08-05"
FLOW = "SOL_TO_EXACT_MEMECOIN_TO_SOL_IMMEDIATE_EXIT"
TOTAL_CASH_AT_RISK_CAP_USD_CENTS = 300
DRAFT_STATE = "DRAFT_OWNER_INPUT_REQUIRED"
READY_STATE = "READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION"
CONFIG_PATH = Path("configs/owner_authority_packet_binding_v1.yaml")
FIXTURE_PATH = Path(
    "tests/fixtures/owner_authority_packet_binding/packet_binding_matrix_v1.json"
)
EVIDENCE_PATH = Path(
    "docs/evidence/owner_authority_packet_binding/a1_offline_packet_binding_acceptance_v1.json"
)
REQUIRED_OWNER_INPUTS = frozenset(
    {
        "token",
        "program",
        "route",
        "wallet_public_address",
        "proposed_notional_usd_cents",
        "maximum_separate_fees_usd_cents",
        "quote_basis",
        "expires_at",
        "monitoring_reference",
        "reconciliation_reference",
        "stop_and_recovery_procedure",
        "exact_owner_approval_phrase",
    }
)


class PacketBindingError(ValueError):
    """Raised when a synthetic packet crosses a non-authorizing boundary."""


OwnerAuthorityPacketError = PacketBindingError


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PacketBindingError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _read_bound(repo_root: Path, path: str, expected_sha256: str) -> bytes:
    root = repo_root.resolve()
    candidate = (root / path).resolve()
    _require(candidate.is_relative_to(root), f"path_escape:{path}")
    _require(candidate.is_file() and not candidate.is_symlink(), f"input_missing:{path}")
    payload = candidate.read_bytes()
    _require(sha256_bytes(payload) == expected_sha256, f"input_hash_drift:{path}")
    return payload


def load_config(repo_root: Path) -> dict[str, Any]:
    config = yaml.safe_load((repo_root / CONFIG_PATH).read_text(encoding="utf-8"))
    _require(isinstance(config, dict), "config_not_mapping")
    _require(config.get("task_id") == TASK_ID, "wrong_task_id")
    _require(config.get("flow") == FLOW, "wrong_canary_flow")
    _require(
        config["cash_cap"]["total_cash_at_risk_usd_cents"]
        == TOTAL_CASH_AT_RISK_CAP_USD_CENTS,
        "cash_cap_must_equal_300",
    )
    _require(config["authority"]["canary_authority"] is False, "canary_authority_must_be_false")
    _require(config["authority"]["task27_authority"] is False, "task27_authority_must_be_false")
    return config


def _non_authorizing_result(packet_state: str, decision: str) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "packet_state": packet_state,
        "decision": decision,
        "canary_authority": False,
        "task27_authority": False,
        "execution_action": "NONE",
        "next_action": decision,
        "numeric_netreturn": "FORBIDDEN",
    }


def evaluate_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Classify a packet without conferring authority or touching external systems."""

    packet_state = str(packet["packet_state"])
    _require(packet.get("flow") == FLOW, "wrong_canary_flow")
    _require(
        packet.get("total_cash_at_risk_cap_usd_cents") == TOTAL_CASH_AT_RISK_CAP_USD_CENTS,
        "cash_cap_must_equal_300",
    )
    if packet_state == DRAFT_STATE:
        owner_input_fields = tuple(str(value) for value in packet["owner_input_fields"])
        _require(
            len(owner_input_fields) == len(set(owner_input_fields)),
            "duplicate_draft_owner_input",
        )
        _require(
            frozenset(owner_input_fields) == REQUIRED_OWNER_INPUTS,
            "draft_owner_inputs_mismatch",
        )
        return _non_authorizing_result(packet_state, "OWNER_INPUT_REQUIRED")
    _require(packet_state == READY_STATE, "invalid_packet_state")
    _require(
        not packet.get("owner_input_fields"),
        "ready_packet_has_unbound_owner_inputs",
    )
    for field in REQUIRED_OWNER_INPUTS:
        _require(
            field in packet and packet[field] not in (None, ""),
            f"ready_packet_missing_owner_input:{field}",
        )
    _require(
        packet["proposed_notional_usd_cents"] > 0,
        "proposed_notional_missing_or_zero",
    )
    _require(
        packet["estimated_total_cost_usd_cents"] <= TOTAL_CASH_AT_RISK_CAP_USD_CENTS,
        "cash_cap_breach",
    )
    _require(
        packet["maximum_separate_fees_usd_cents"] > 0,
        "separate_fee_cap_missing_or_zero",
    )
    return _non_authorizing_result(packet_state, "OWNER_EXACT_APPROVAL_REQUIRED")


def evaluate_exit_precondition(first_leg: Mapping[str, Any]) -> dict[str, str]:
    """Validate only the safety shape of a future exit; never authorize an exit."""

    _require(
        first_leg.get("terminal_state") == "LANDED_SUCCESS",
        "exit_requires_landed_success_first_leg",
    )
    _require(
        first_leg.get("reconciled") is True,
        "exit_before_first_leg_reconciliation",
    )
    _require(
        first_leg.get("monitoring_healthy") is True,
        "exit_blocked_monitoring_loss",
    )
    _require(
        first_leg.get("inventory_match") is True,
        "exit_blocked_inventory_mismatch",
    )
    _require(
        first_leg.get("allowlist_match") is True,
        "exit_blocked_route_program_mismatch",
    )
    _require(first_leg.get("fee_cap_ok") is True, "exit_blocked_fee_cap_breach")
    return {"outcome": "EXIT_LEG_SHAPE_VALIDATED_NOT_AUTHORIZED"}


def _evaluate_fixture_case(case: Mapping[str, Any]) -> dict[str, str]:
    case_id = str(case["case_id"])
    try:
        if case["kind"] == "packet":
            result = evaluate_packet(case["input"])
        elif case["kind"] == "exit_precondition":
            result = evaluate_exit_precondition(case["input"])
        else:
            raise PacketBindingError("invalid_fixture_case_kind")
    except PacketBindingError as exc:
        _require("expected_error" in case, f"unexpected_fixture_error:{case_id}")
        _require(
            str(exc) == case["expected_error"],
            f"fixture_error_mismatch:{case_id}",
        )
        return {"case_id": case_id, "result": "REJECTED", "code": str(exc)}
    _require("expected_error" not in case, f"fixture_expected_error_missing:{case_id}")
    for key, expected in case["expected_values"].items():
        _require(result.get(key) == expected, f"fixture_result_mismatch:{case_id}:{key}")
    outcome = result["outcome"] if "outcome" in result else result["decision"]
    return {"case_id": case_id, "result": "PASS", "outcome": str(outcome)}


def build_binding_evidence(repo_root: Path) -> dict[str, Any]:
    """Build a deterministic, non-authorizing receipt from tracked synthetic inputs."""

    config = load_config(repo_root)
    bindings: list[dict[str, Any]] = []
    for binding in config["frozen_input_bindings"]:
        payload = _read_bound(repo_root, binding["path"], binding["sha256"])
        bindings.append(
            {
                "asset_id": binding["asset_id"],
                "path": binding["path"],
                "sha256": binding["sha256"],
                "bytes": len(payload),
            }
        )
    fixture = json.loads((repo_root / FIXTURE_PATH).read_text(encoding="utf-8"))
    _require(isinstance(fixture, dict), "fixture_not_mapping")
    return {
        "schema": "smial.owner-authority-packet-binding.a1",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "as_of": AS_OF,
        "status": "PASS_OFFLINE_OWNER_PACKET_REVIEW_ONLY_NO_AUTHORITY",
        "input_bindings": bindings,
        "decision": _non_authorizing_result(DRAFT_STATE, "OWNER_INPUT_REQUIRED"),
        "owner_packet": {
            "status": DRAFT_STATE,
            "flow": FLOW,
            "all_in_cash_at_risk_cap_usd_cents": TOTAL_CASH_AT_RISK_CAP_USD_CENTS,
            "required_owner_input_fields": sorted(REQUIRED_OWNER_INPUTS),
            "synthetic_values_only": True,
        },
        "exit_policy": {
            "first_leg_requires": "LANDED_SUCCESS_AND_RECONCILED",
            "exit_shape_only": "EXIT_LEG_SHAPE_VALIDATED_NOT_AUTHORIZED",
            "unknown_blocks_exit_and_retry": True,
        },
        "case_results": [_evaluate_fixture_case(case) for case in fixture["cases"]],
        "nonclaims": [
            "NO_PROVIDER_API_RPC_WSS",
            "NO_WALLET",
            "NO_SIGNER",
            "NO_TRANSACTION_OR_SIGNED_BYTES",
            "NO_SIMULATION_OR_SEND",
            "NO_CASH_SPEND",
            "NO_R3",
            "NO_NUMERIC_NETRETURN",
            "NO_TASK27",
            "READY_DOES_NOT_GRANT_AUTHORITY",
            "UNKNOWN_BLOCKS_EXIT_AND_RETRY",
        ],
        "side_effect_counters": {
            "provider_api_rpc_wss_calls": 0,
            "r3_paths_or_values_read": 0,
            "wallet_signer_transaction_actions": 0,
            "transaction_build_sign_simulate_send": 0,
            "cash_spend_usd_cents": 0,
            "dependency_changes": 0,
        },
    }


def write_outputs(repo_root: Path) -> str:
    evidence = build_binding_evidence(repo_root)
    path = repo_root / EVIDENCE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(evidence)
    path.write_bytes(payload)
    return sha256_bytes(payload)
