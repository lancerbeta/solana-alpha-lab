#!/usr/bin/env python3
"""Deterministic evaluator for OWNER_ATTENTION_GATE_V1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "control" / "owner_attention_gate_v1.yaml"
REQUEST_SCHEMA = "smial.owner-attention-request"
REQUEST_VERSION = "1.0"


def decision(value: str, *reasons: str) -> dict[str, Any]:
    return {
        "schema": "smial.owner-attention-decision",
        "schema_version": "1.0",
        "decision": value,
        "reasons": list(reasons),
    }


def evaluate(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
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
