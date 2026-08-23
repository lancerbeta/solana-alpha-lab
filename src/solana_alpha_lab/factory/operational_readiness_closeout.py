"""FACTORY_V1 operational-readiness closeout predicate evaluator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

FACTORY_RUNNER_SHA256 = (
    "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"
)

A4_PIT_ACCEPTANCE_RELATIVE = (
    "docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_acceptance_v1.json"
)

A4_DATA_PREDICATE_IDS = frozenset(
    {
        "DATA_FACTORY_PIT_LINEAGE_RECEIPT",
        "DATA_EXPLICIT_MISSINGNESS",
        "TIME_TO_EVIDENCE_FIRST_BYTE",
    }
)

A5_LIVE_OPS_PREDICATE_IDS = frozenset(
    {
        "RUNTIME_LIVE_DEPLOY_ROLLBACK",
        "RUNTIME_LIVE_CLEAN_REHOST",
        "MONITORING_PROVIDER_FAILURE_ALERT",
        "MONITORING_LIVE_STALE_DATA_ALERT",
        "MONITORING_LIVE_BOT_STALL_ALERT",
        "DATA_PROVIDER_HEALTH_VISIBLE",
        "SECURITY_FINANCIAL_GATED",
    }
)


class CloseoutError(ValueError):
    """Fail-closed closeout evaluation error."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CloseoutError(f"YAML_NOT_OBJECT:{path.as_posix()}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CloseoutError(f"JSON_NOT_OBJECT:{path.as_posix()}")
    return payload


def _a4_replay_error(
    root: Path, evidence_relative: str, payload: dict[str, Any]
) -> str | None:
    if evidence_relative != A4_PIT_ACCEPTANCE_RELATIVE:
        return None
    try:
        from solana_alpha_lab.factory.pit_data_truth_canonicalization import (
            canonicalize_from_repository,
        )

        canonical = canonicalize_from_repository(root)
    except Exception:
        return "EVIDENCE_REPLAY_FAILED"
    return None if payload == canonical else "EVIDENCE_REPLAY_MISMATCH"


def _dig(payload: dict[str, Any], dotted: str) -> Any:
    cur: Any = payload
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def load_closeout_config(root: Path) -> dict[str, Any]:
    path = root / "configs/factory_v1_operational_readiness_closeout_v1.yaml"
    return _load_yaml(path)


def evaluate_predicate(
    root: Path, predicate: dict[str, Any]
) -> dict[str, Any]:
    pred_id = str(predicate.get("id") or "")
    evidence_rel = str(predicate.get("evidence_path") or "")
    if not pred_id or not evidence_rel:
        raise CloseoutError("PREDICATE_SHAPE_INVALID")
    evidence_path = root / evidence_rel
    if not evidence_path.is_file():
        return {
            "id": pred_id,
            "dimension": predicate.get("dimension"),
            "verdict": "FAIL",
            "gap": f"MISSING_EVIDENCE:{evidence_rel}",
            "evidence_path": evidence_rel,
        }
    require = predicate.get("require")
    require_yaml = predicate.get("require_yaml")
    if require is not None and require_yaml is not None:
        raise CloseoutError(f"PREDICATE_DUAL_REQUIRE:{pred_id}")
    if require_yaml is not None:
        if not isinstance(require_yaml, dict) or not require_yaml:
            raise CloseoutError(f"PREDICATE_REQUIRE_YAML_INVALID:{pred_id}")
        payload = _load_yaml(evidence_path)
        for key, expected in require_yaml.items():
            observed = _dig(payload, str(key))
            if observed != expected:
                return {
                    "id": pred_id,
                    "dimension": predicate.get("dimension"),
                    "verdict": "FAIL",
                    "gap": f"YAML_MISMATCH:{key}:{observed!r}!={expected!r}",
                    "evidence_path": evidence_rel,
                }
        return {
            "id": pred_id,
            "dimension": predicate.get("dimension"),
            "verdict": "PASS",
            "gap": None,
            "evidence_path": evidence_rel,
        }
    if not isinstance(require, dict) or not require:
        raise CloseoutError(f"PREDICATE_REQUIRE_INVALID:{pred_id}")
    payload = _load_json(evidence_path)
    schema_rel = predicate.get("schema_path")
    schema_sha = predicate.get("schema_sha256")
    evidence_sha = predicate.get("evidence_sha256")
    if any(value is not None for value in (schema_rel, schema_sha, evidence_sha)):
        if not all(
            isinstance(value, str) and value
            for value in (schema_rel, schema_sha, evidence_sha)
        ):
            raise CloseoutError(f"PREDICATE_SCHEMA_BINDING_INVALID:{pred_id}")
        schema_path = root / str(schema_rel)
        if not schema_path.is_file():
            return {
                "id": pred_id,
                "dimension": predicate.get("dimension"),
                "verdict": "FAIL",
                "gap": f"MISSING_SCHEMA:{schema_rel}",
                "evidence_path": evidence_rel,
            }
        if _sha256(evidence_path) != evidence_sha:
            return {
                "id": pred_id,
                "dimension": predicate.get("dimension"),
                "verdict": "FAIL",
                "gap": "EVIDENCE_HASH_MISMATCH",
                "evidence_path": evidence_rel,
            }
        if _sha256(schema_path) != schema_sha:
            return {
                "id": pred_id,
                "dimension": predicate.get("dimension"),
                "verdict": "FAIL",
                "gap": "SCHEMA_HASH_MISMATCH",
                "evidence_path": evidence_rel,
            }
        try:
            schema_payload = _load_json(schema_path)
            jsonschema.validate(payload, schema_payload)
        except (
            OSError,
            json.JSONDecodeError,
            jsonschema.SchemaError,
            jsonschema.ValidationError,
        ):
            return {
                "id": pred_id,
                "dimension": predicate.get("dimension"),
                "verdict": "FAIL",
                "gap": "EVIDENCE_SCHEMA_INVALID",
                "evidence_path": evidence_rel,
            }
        replay_error = _a4_replay_error(root, evidence_rel, payload)
        if replay_error is not None:
            return {
                "id": pred_id,
                "dimension": predicate.get("dimension"),
                "verdict": "FAIL",
                "gap": replay_error,
                "evidence_path": evidence_rel,
            }
    for key, expected in require.items():
        observed = _dig(payload, str(key))
        if observed != expected:
            return {
                "id": pred_id,
                "dimension": predicate.get("dimension"),
                "verdict": "FAIL",
                "gap": f"FIELD_MISMATCH:{key}:{observed!r}!={expected!r}",
                "evidence_path": evidence_rel,
            }
    return {
        "id": pred_id,
        "dimension": predicate.get("dimension"),
        "verdict": "PASS",
        "gap": None,
        "evidence_path": evidence_rel,
    }


def assert_runner_pin(root: Path, config: dict[str, Any]) -> None:
    runner = root / str(config.get("runner_path") or "")
    expected = str(config.get("runner_pin_sha256") or "")
    if not runner.is_file() or expected != FACTORY_RUNNER_SHA256:
        raise CloseoutError("RUNNER_PIN_CONFIG_INVALID")
    if _sha256(runner) != FACTORY_RUNNER_SHA256:
        raise CloseoutError("FACTORY_RUNNER_CHANGED")


def evaluate_closeout(root: Path) -> dict[str, Any]:
    config = load_closeout_config(root)
    assert_runner_pin(root, config)
    predicates = config.get("predicates")
    if not isinstance(predicates, list) or not predicates:
        raise CloseoutError("PREDICATES_MISSING")
    results = [evaluate_predicate(root, item) for item in predicates]
    gaps = [item["gap"] for item in results if item["verdict"] != "PASS"]
    named_gaps = [
        f"{item['id']}:{item['gap']}"
        for item in results
        if item["verdict"] != "PASS"
    ]
    if gaps:
        terminal = "FACTORY_PRODUCTIZATION_REPLAN"
        ready = False
        failed_ids = {
            item["id"] for item in results if item["verdict"] != "PASS"
        }
        next_safe = (
            "PIT_CANONICALIZATION_EVIDENCE_INSUFFICIENT"
            if failed_ids & A4_DATA_PREDICATE_IDS
            else (
                "A5_LIVE_OPS_HARDENING_COMMISSIONING"
                if failed_ids & A5_LIVE_OPS_PREDICATE_IDS
                else "A6_READINESS_RECERTIFICATION_AND_FREEZE"
            )
        )
    else:
        terminal = "FACTORY_V1_OPERATIONAL_READY"
        ready = True
        named_gaps = []
        next_safe = "FOUNDATION_FREEZE_ACTIVE_ATOM4_ELIGIBLE_IF_KEPT"
    stage = config.get("reconciled_product_stage_on_any_closeout")
    if not isinstance(stage, dict):
        raise CloseoutError("STAGE_RECONCILE_MISSING")
    freeze_active = bool(ready and config.get("foundation_freeze_on_ready") is True)
    return {
        "schema": "smial.factory-v1-operational-readiness-closeout.gate",
        "schema_version": "1.0",
        "task_id": config.get("task_id"),
        "as_of": config.get("as_of"),
        "terminal": terminal,
        "factory_v1_operational_ready": ready,
        "foundation_freeze": "ACTIVE" if freeze_active else "INACTIVE",
        "named_gaps": named_gaps,
        "next_safe_action": next_safe,
        "ready_authority": config.get("ready_authority") or "CLOSEOUT_PREDICATE_SET_ONLY",
        "predicates": results,
        "reconciled_product_stage": stage,
        "factory_runner_sha256": FACTORY_RUNNER_SHA256,
        "non_claims": list(config.get("non_claims") or []),
    }


def apply_stage_reconciliation(root: Path, gate: dict[str, Any]) -> dict[str, Any]:
    """Rewrite current_product_stage (+ READY promotion only if all predicates PASS)."""
    path = root / "configs/factory_v1_operational_readiness_v1.yaml"
    document = _load_yaml(path)
    stage = gate.get("reconciled_product_stage")
    if not isinstance(stage, dict):
        raise CloseoutError("STAGE_RECONCILE_INVALID")
    current = document.get("current_product_stage")
    if not isinstance(current, dict):
        raise CloseoutError("CURRENT_PRODUCT_STAGE_MISSING")
    text = path.read_text(encoding="utf-8")
    for key, value in stage.items():
        key_s = str(key)
        if key_s not in current:
            raise CloseoutError(f"STAGE_KEY_UNKNOWN:{key_s}")
        pattern = f"  {key_s}: "
        start = text.find(pattern)
        if start < 0:
            raise CloseoutError(f"STAGE_LINE_MISSING:{key_s}")
        line_end = text.find("\n", start)
        if line_end < 0:
            raise CloseoutError(f"STAGE_LINE_EOF:{key_s}")
        text = text[:start] + f"  {key_s}: {value}" + text[line_end:]
        current[key_s] = value
    document["current_product_stage"] = current
    closeout_block = (
        "closeout:\n"
        f"  task_id: {gate.get('task_id')}\n"
        f"  terminal: {gate.get('terminal')}\n"
        f"  factory_v1_operational_ready: {str(bool(gate.get('factory_v1_operational_ready'))).lower()}\n"
        f"  foundation_freeze: {gate.get('foundation_freeze')}\n"
        f"  named_gap_count: {len(gate.get('named_gaps') or [])}\n"
        f"  ready_authority: CLOSEOUT_PREDICATE_SET_ONLY\n"
    )
    marker = "capability_radar:\n"
    if "\ncloseout:\n" in text:
        start = text.find("\ncloseout:\n")
        end = text.find(marker, start)
        if end < 0:
            raise CloseoutError("CAPABILITY_RADAR_MARKER_MISSING")
        text = text[: start + 1] + closeout_block + text[end:]
    else:
        insert_at = text.find(marker)
        if insert_at < 0:
            raise CloseoutError("CAPABILITY_RADAR_MARKER_MISSING")
        text = text[:insert_at] + closeout_block + text[insert_at:]
    # Keep direction status until READY; REPLAN must not fake implementation.
    if gate.get("factory_v1_operational_ready") is True:
        replacements = {
            "status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED": "status: IMPLEMENTED_VALIDATED",
            "implementation: NOT_IMPLEMENTED": "implementation: OPERATIONAL_READY",
            "mode: DESIGN_ONLY": "mode: DIRECT_CURSOR_DELIVERY",
            "  status: TRIGGERED": "  status: PASS",
        }
        for old, new in replacements.items():
            if old not in text:
                raise CloseoutError(f"READY_PROMOTION_LINE_MISSING:{old}")
            text = text.replace(old, new, 1)
        document["status"] = "IMPLEMENTED_VALIDATED"
        document["implementation"] = "OPERATIONAL_READY"
        document["mode"] = "DIRECT_CURSOR_DELIVERY"
        document["milestone"]["status"] = "PASS"
    path.write_text(text, encoding="utf-8")
    document["closeout"] = {
        "task_id": gate.get("task_id"),
        "terminal": gate.get("terminal"),
        "factory_v1_operational_ready": bool(gate.get("factory_v1_operational_ready")),
        "foundation_freeze": gate.get("foundation_freeze"),
        "named_gap_count": len(gate.get("named_gaps") or []),
    }
    return document
