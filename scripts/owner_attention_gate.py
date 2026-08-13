#!/usr/bin/env python3
"""Deterministic evaluator for versioned owner-attention policies."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "control" / "owner_attention_gate_v2.yaml"
V2_SCHEMA = ROOT / "catalog" / "schemas" / "owner_attention_gate_v2.schema.json"
REQUEST_SCHEMA = "smial.owner-attention-request"
REQUEST_VERSION = "1.0"


def decision(value: str, *reasons: str, version: str = "1.0") -> dict[str, Any]:
    return {
        "schema": "smial.owner-attention-decision",
        "schema_version": version,
        "decision": value,
        "reasons": list(reasons),
    }


def _evaluate_v1(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if request.get("schema") != REQUEST_SCHEMA:
        return decision("DENY", "INVALID_REQUEST_SCHEMA")
    if str(request.get("schema_version")) != REQUEST_VERSION:
        return decision("DENY", "INVALID_REQUEST_VERSION")

    route = request.get("route")
    actor = request.get("actor")
    action_class = request.get("action_class")
    route_policy = policy.get("route_authority", {}).get(route)
    if not isinstance(route_policy, dict):
        return decision("DENY", "UNKNOWN_ROUTE")
    if actor not in route_policy.get("allowed_actors", []):
        return decision("DENY", "ACTOR_NOT_ALLOWED_FOR_ROUTE")
    if request.get("scope_bound") is not True:
        return decision("DENY", "SCOPE_NOT_BOUND")

    if action_class == "MERGE_PULL_REQUEST" and actor == "CURSOR":
        return decision("DENY", "CURSOR_MERGE_FORBIDDEN")

    triggers = request.get("triggers")
    if not isinstance(triggers, dict):
        return decision("DENY", "TRIGGERS_NOT_BOUND")
    triggered_reasons = [
        trigger_policy["reason"]
        for trigger, trigger_policy in policy.get(
            "owner_attention_triggers", {}
        ).items()
        if triggers.get(trigger) is True
    ]
    if triggered_reasons:
        return decision("OWNER_ATTENTION_REQUIRED", *triggered_reasons)
    if request.get("stricter_stop_active") is True:
        return decision("OWNER_ATTENTION_REQUIRED", "STRICTER_STOP_ACTIVE")

    if action_class == "MERGE_PULL_REQUEST":
        checks = request.get("merge_checks")
        if not isinstance(checks, dict):
            return decision("DENY", "MERGE_CHECKS_NOT_BOUND")
        for check in policy.get("merge_preconditions", []):
            if checks.get(check) is not True:
                return decision("DENY", f"MERGE_CHECK_FAILED:{check}")
        if (
            route == "LOCAL_WORK_CODEX"
            and actor == "CODEX"
            and route_policy.get("ordinary_merge")
            == "AUTONOMOUS_AFTER_MACHINE_GATE"
        ):
            return decision("AUTONOMOUS", "LOCAL_CODEX_MERGE_GATE_PASS")
        return decision(
            "OWNER_ATTENTION_REQUIRED", "ROUTE_HAS_NO_CODEX_AUTO_MERGE"
        )

    if action_class not in route_policy.get("autonomous_action_classes", []):
        return decision("DENY", "ACTION_CLASS_NOT_AUTONOMOUS_FOR_ROUTE")
    return decision("AUTONOMOUS", "ROUTINE_IN_ENVELOPE")


def _v2_schema_branch(name: str) -> dict[str, Any]:
    document = json.loads(V2_SCHEMA.read_text(encoding="utf-8"))
    branch = document.get("$defs", {}).get(name)
    if not isinstance(branch, dict):
        raise ValueError("OWNER_ATTENTION_V2_SCHEMA_BRANCH_MISSING")
    branch = dict(branch)
    branch["$defs"] = document["$defs"]
    return branch


def validate_exact_merge_approval(
    request: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    approval = request.get("owner_approval")
    checks = request.get("merge_checks")
    if not isinstance(approval, dict):
        return ["EXACT_MERGE_APPROVAL_REQUIRED"]
    if not isinstance(checks, dict):
        return ["MERGE_CHECKS_NOT_BOUND"]
    pattern = policy["merge_approval"]["exact_phrase_pattern"]
    match = re.fullmatch(pattern, approval["phrase"])
    if match is None:
        return ["MERGE_APPROVAL_PHRASE_MISMATCH"]
    phrase_pr = int(match.group(1))
    phrase_head = match.group(2)
    if request["repository"] != policy["repository"]:
        return ["MERGE_REPOSITORY_MISMATCH"]
    if not (
        phrase_pr == approval["pr_number"] == checks["pr_number"]
        and phrase_head == approval["head_sha"] == checks["observed_head_sha"]
    ):
        return ["MERGE_IDENTITY_MISMATCH"]
    return []


def _request_v2_has_exact_types(request: dict[str, Any]) -> bool:
    if type(request.get("scope_bound")) is not bool:
        return False
    if type(request.get("stricter_stop_active")) is not bool:
        return False
    triggers = request.get("triggers")
    if not isinstance(triggers, dict) or any(
        type(value) is not bool for value in triggers.values()
    ):
        return False
    approval = request.get("owner_approval")
    if isinstance(approval, dict) and type(approval.get("pr_number")) is not int:
        return False
    checks = request.get("merge_checks")
    if isinstance(checks, dict):
        if type(checks.get("pr_number")) is not int:
            return False
        for key, value in checks.items():
            if key not in {"pr_number", "observed_head_sha"} and type(value) is not bool:
                return False
    return True


def _evaluate_v2(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    try:
        jsonschema.validate(policy, _v2_schema_branch("policyV2"))
    except (OSError, ValueError, json.JSONDecodeError, jsonschema.ValidationError):
        return decision("DENY", "INVALID_POLICY_SCHEMA", version="2.0")
    try:
        jsonschema.validate(request, _v2_schema_branch("requestV2"))
    except (ValueError, jsonschema.ValidationError):
        return decision("DENY", "INVALID_REQUEST_SCHEMA", version="2.0")
    if not _request_v2_has_exact_types(request):
        return decision("DENY", "INVALID_REQUEST_SCHEMA", version="2.0")

    route = request["route"]
    actor = request["actor"]
    action_class = request["action_class"]
    route_policy = policy["route_authority"].get(route)
    if not isinstance(route_policy, dict):
        return decision("DENY", "UNKNOWN_ROUTE", version="2.0")
    if actor not in route_policy["allowed_actors"]:
        return decision("DENY", "ACTOR_NOT_ALLOWED_FOR_ROUTE", version="2.0")
    if request["scope_bound"] is not True:
        return decision("DENY", "SCOPE_NOT_BOUND", version="2.0")

    reasons = [
        reason
        for trigger, reason in policy["owner_attention_triggers"].items()
        if request["triggers"][trigger] is True
    ]
    if reasons:
        return decision("OWNER_ATTENTION_REQUIRED", *reasons, version="2.0")
    if request["stricter_stop_active"] is True:
        return decision(
            "OWNER_ATTENTION_REQUIRED", "STRICTER_STOP_ACTIVE", version="2.0"
        )

    if action_class == "MERGE_PULL_REQUEST":
        if route_policy["ordinary_merge"] == "FORBIDDEN":
            return decision("DENY", "ROUTE_MERGE_FORBIDDEN", version="2.0")
        if request["owner_approval"] is None:
            return decision(
                "OWNER_ATTENTION_REQUIRED",
                "EXACT_MERGE_APPROVAL_REQUIRED",
                version="2.0",
            )
        approval_errors = validate_exact_merge_approval(request, policy)
        if approval_errors:
            return decision("DENY", *approval_errors, version="2.0")
        checks = request["merge_checks"]
        assert isinstance(checks, dict)
        for check in policy["merge_preconditions"]:
            if checks.get(check) is not True:
                return decision(
                    "DENY", f"MERGE_CHECK_FAILED:{check}", version="2.0"
                )
        return decision(
            "AUTONOMOUS", "DIRECT_AGENT_EXACT_MERGE_GATE_PASS", version="2.0"
        )

    if action_class not in route_policy["autonomous_action_classes"]:
        return decision("DENY", "ACTION_CLASS_NOT_AUTONOMOUS_FOR_ROUTE", version="2.0")
    return decision("AUTONOMOUS", "ROUTINE_IN_ENVELOPE", version="2.0")


def evaluate(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if str(policy.get("schema_version")) == "1.0":
        return _evaluate_v1(request, policy)
    if str(policy.get("schema_version")) == "2.0":
        return _evaluate_v2(request, policy)
    return decision("DENY", "UNSUPPORTED_POLICY_VERSION", version="2.0")


def load_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"mapping required: {path}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    result = evaluate(request, load_mapping(args.policy))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] != "DENY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
