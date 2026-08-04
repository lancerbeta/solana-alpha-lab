"""Offline, non-authorizing readiness contract for one future owned canary."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


TASK_ID = "TASK-26C"
ATOM_ID = "T26C-A1_OFFLINE_CANARY_READINESS_AND_AUTHORITY_GATE_V1"
AS_OF = "2026-08-04"
CONFIG_PATH = Path("configs/task26c_owned_execution_canary_readiness_contract_v1.yaml")
FIXTURE_PATH = Path("tests/fixtures/task26c/owned_execution_canary_readiness_matrix_v1.json")
EVIDENCE_PATH = Path("docs/evidence/task26c/a2_owned_canary_readiness_acceptance_v1.json")


class CanaryReadinessError(ValueError):
    """Raised when a synthetic canary-readiness case crosses a safety boundary."""


class FakeSigner:
    """Test double that documents the signer boundary by refusing every signature."""

    def sign(self, _payload: bytes) -> bytes:
        raise CanaryReadinessError("fake_signer_never_signs")


class FakeTransport:
    """Test double that returns a preset terminal observation without any I/O."""

    def __init__(self, terminal_state: str) -> None:
        self._terminal_state = terminal_state

    def observe(self, attempt_id: str) -> dict[str, str]:
        return {"attempt_id": attempt_id, "terminal_state": self._terminal_state}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CanaryReadinessError(code)


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
    _require(config.get("atom_id") == ATOM_ID, "wrong_atom_id")
    _require(config["authority"]["canary_authority"] is False, "canary_authority_must_be_false")
    return config


def evaluate_case(case: Mapping[str, Any]) -> dict[str, str]:
    """Evaluate one fully synthetic terminal/retry path without performing an action."""

    attempt_id = str(case["stable_attempt_id"])
    action = str(case["action"])
    terminal_state = str(case["terminal_state"])
    seen_attempt_ids = {str(value) for value in case.get("seen_attempt_ids", [])}
    _require(attempt_id not in seen_attempt_ids, "duplicate_attempt_id")
    _require(
        terminal_state
        in {
            "REJECTED_BEFORE_SEND",
            "DROPPED_OR_EXPIRED_NOT_PROCESSED",
            "LANDED_FAILED",
            "LANDED_SUCCESS",
            "UNKNOWN_REQUIRES_RECONCILIATION",
        },
        "invalid_terminal_state",
    )
    if action == "RETRY":
        _require(bool(case["reconciled"]), "retry_before_reconciliation")
        _require(
            terminal_state != "UNKNOWN_REQUIRES_RECONCILIATION",
            "retry_before_reconciliation",
        )
    if not bool(case["monitoring_healthy"]):
        return {"outcome": "BLOCKED_MONITORING"}
    if not bool(case["allowlist_match"]):
        return {"outcome": "BLOCKED_ROUTE_MISMATCH"}
    if not bool(case["provider_agreement"]):
        return {"outcome": "BLOCKED_PROVIDER_DIVERGENCE"}
    if not bool(case["fee_cap_ok"]):
        return {"outcome": "BLOCKED_FEE_CAP"}
    if not bool(case["inventory_match"]):
        return {"outcome": "BLOCKED_INVENTORY_MISMATCH"}
    if terminal_state in {
        "DROPPED_OR_EXPIRED_NOT_PROCESSED",
        "LANDED_FAILED",
        "LANDED_SUCCESS",
        "UNKNOWN_REQUIRES_RECONCILIATION",
    } and not bool(case["reconciled"]):
        return {"outcome": "RECONCILIATION_REQUIRED"}
    if terminal_state == "REJECTED_BEFORE_SEND":
        return {"outcome": "REJECTED_BEFORE_SEND_RECORDED"}
    if terminal_state == "LANDED_SUCCESS":
        return {"outcome": "CLOSED_RECONCILED_NO_RETRY"}
    if terminal_state == "LANDED_FAILED":
        return {"outcome": "LANDED_FAILED_RECONCILED_NO_RETRY"}
    if terminal_state == "DROPPED_OR_EXPIRED_NOT_PROCESSED":
        return {"outcome": "DROPPED_RECONCILED_NO_RETRY"}
    return {"outcome": "UNKNOWN_REQUIRES_TERMINAL_RECLASSIFICATION"}


def _case_results(fixture: Mapping[str, Any]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for case in fixture["cases"]:
        case_id = str(case["case_id"])
        try:
            outcome = evaluate_case(case)["outcome"]
        except CanaryReadinessError as exc:
            results.append({"case_id": case_id, "result": "REJECTED", "code": str(exc)})
        else:
            results.append({"case_id": case_id, "result": "PASS", "outcome": outcome})
    return results


def build_readiness_evidence(repo_root: Path) -> dict[str, Any]:
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
    return {
        "schema": "smial.task26c.a1-owned-execution-canary-readiness",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "as_of": AS_OF,
        "status": "PASS_READY_FOR_OWNER_AUTHORITY_WITH_LIMITATIONS_NO_AUTHORITY",
        "input_bindings": bindings,
        "decision": {
            "result": "READY_FOR_OWNER_CANARY_AUTHORITY_WITH_LIMITATIONS",
            "canary_authority": False,
            "task27_authority": False,
            "numeric_netreturn": "FORBIDDEN",
        },
        "authority": config["authority"],
        "role_boundaries": {
            "research_process": "OFFLINE_EVALUATION_ONLY_NO_BUILD_SIGN_SEND",
            "transaction_builder": "FUTURE_SHAPE_VALIDATION_ONLY_NO_KEY_OR_SEND",
            "isolated_signer": "FUTURE_OWNER_CONTROLLED_BOUNDARY_NOT_CREATED_OR_ACTIVATED",
            "goal_owner": "EXACT_FUTURE_APPROVAL_REQUIRED",
        },
        "future_witness_contract": {
            "status": "FUTURE_ONLY_NO_ATTEMPT_OR_SIGNATURE",
            "required_fields": config["future_witness_required_fields"],
        },
        "reconciliation_before_retry": {
            "retry_requires_bound_reconciliation": True,
            "unknown_blocks_retry_and_new_action": True,
            "required_basis": ["terminal_state", "fee_treatment", "inventory_basis"],
        },
        "allowlist_policy": config["allowlist_policy"],
        "owner_approval_packet": config["owner_approval_packet"],
        "health_blocks": config["health_blocks"],
        "case_results": _case_results(fixture),
        "nonclaims": [
            "NO_PROVIDER_EXECUTION",
            "NO_WALLET",
            "NO_SIGNER",
            "NO_TRANSACTION_OR_SIGNED_BYTES",
            "NO_CASH_SPEND",
            "NO_R3",
            "NO_NUMERIC_NETRETURN",
            "NO_TASK27",
            "UNKNOWN_BLOCKS_RETRY",
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
    evidence = build_readiness_evidence(repo_root)
    path = repo_root / EVIDENCE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(evidence)
    path.write_bytes(payload)
    return sha256_bytes(payload)
