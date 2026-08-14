#!/usr/bin/env python3
"""Deterministic evaluator for versioned owner-attention policies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "control" / "owner_attention_gate_v2.yaml"
V2_SCHEMA = ROOT / "catalog" / "schemas" / "owner_attention_gate_v2.schema.json"
REQUEST_SCHEMA = "smial.owner-attention-request"
REQUEST_VERSION = "1.0"


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run_read(args: list[str], cwd: Path) -> bytes:
    completed = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, shell=False)
    if completed.returncode != 0:
        raise ValueError("LIVE_READBACK_FAILED")
    return completed.stdout


def decode_json_mapping(value: bytes, code: str) -> dict[str, Any]:
    try:
        document = json.loads(value.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(code) from None
    if not isinstance(document, dict):
        raise ValueError(code)
    return document


def verify_context_receipt(root: Path, receipt: dict[str, Any]) -> None:
    try:
        schema = json.loads(
            (root / "catalog/schemas/delivery_harness_context_receipt.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.validate(receipt, schema)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError):
        raise ValueError("CONTEXT_RECEIPT_INVALID") from None
    unsigned = dict(receipt)
    observed = unsigned.pop("receipt_sha256", None)
    if observed != sha256_bytes(canonical_json_bytes(unsigned)):
        raise ValueError("CONTEXT_RECEIPT_HASH_MISMATCH")


def bound_factory_fit_pass(root: Path, receipt: dict[str, Any]) -> bool:
    task = receipt.get("task")
    if not isinstance(task, dict):
        return False
    for selected in receipt.get("selected", []):
        if not isinstance(selected, dict) or selected.get("semantic_role") != "DELIVERY_EVIDENCE":
            continue
        relative = selected.get("path")
        if not isinstance(relative, str):
            continue
        path = (root / relative).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != selected.get("sha256"):
            continue
        try:
            evidence = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(evidence, dict) or evidence.get("task_id") != task.get("task_id"):
            continue
        binding = evidence.get("factory_fit")
        if not isinstance(binding, dict) or binding.get("verdict") != "PASS":
            continue
        fit_relative = binding.get("path")
        if not isinstance(fit_relative, str):
            continue
        fit_path = (root / fit_relative).resolve()
        if root.resolve() not in fit_path.parents or not fit_path.is_file():
            continue
        payload = fit_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != binding.get("sha256"):
            continue
        try:
            fit = json.loads(payload.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if (
            isinstance(fit, dict)
            and fit.get("task_id") == task.get("task_id")
            and fit.get("mode") == "FULL_REVIEW"
            and fit.get("verdict") == "PASS"
        ):
            return True
    return False


def github_review_threads_resolved(
    repository: str, pr_number: int, root: Path, runner=run_read
) -> bool:
    owner, name = repository.split("/", 1)
    query = (
        "query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){"
        "pullRequest(number:$number){reviewThreads(first:100){nodes{isResolved}pageInfo{hasNextPage}}}}}"
    )
    value = decode_json_mapping(
        runner(
            [
                "gh", "api", "graphql", "-f", f"query={query}",
                "-F", f"owner={owner}", "-F", f"name={name}",
                "-F", f"number={pr_number}",
            ],
            root,
        ),
        "PR_REVIEW_THREADS_INVALID",
    )
    try:
        threads = value["data"]["repository"]["pullRequest"]["reviewThreads"]
        nodes = threads["nodes"]
        has_next = threads["pageInfo"]["hasNextPage"]
    except (KeyError, TypeError):
        raise ValueError("PR_REVIEW_THREADS_INVALID") from None
    return has_next is False and isinstance(nodes, list) and all(
        isinstance(item, dict) and item.get("isResolved") is True for item in nodes
    )


def build_grounded_merge_request(
    root: Path,
    *,
    repository: str,
    pr_number: int,
    route: str,
    actor: str,
    approval_phrase: str,
    context_receipt: dict[str, Any],
    runner=run_read,
) -> dict[str, Any]:
    if type(pr_number) is not int or pr_number < 1:
        raise ValueError("PR_NUMBER_INVALID")
    origin = runner(["git", "remote", "get-url", "origin"], root).decode("utf-8", errors="strict").strip()
    allowed_origins = {f"git@github.com:{repository}.git", f"https://github.com/{repository}.git", f"https://github.com/{repository}"}
    local_head = runner(["git", "rev-parse", "HEAD"], root).decode("ascii", errors="strict").strip()
    local_tree = runner(["git", "rev-parse", "HEAD^{tree}"], root).decode("ascii", errors="strict").strip()
    dirty = bool(runner(["git", "status", "--porcelain=v1"], root).strip())
    if origin not in allowed_origins or dirty:
        raise ValueError("LOCAL_REPOSITORY_IDENTITY_MISMATCH")
    verify_context_receipt(root, context_receipt)
    pr = decode_json_mapping(runner(["gh", "pr", "view", str(pr_number), "--repo", repository, "--json", "number,headRefOid,mergeable,reviewDecision,state,isDraft"], root), "PR_READBACK_INVALID")
    checks_value = json.loads(runner(["gh", "pr", "checks", str(pr_number), "--repo", repository, "--json", "name,state,bucket"], root).decode("utf-8", errors="strict"))
    if not isinstance(checks_value, list):
        raise ValueError("PR_READBACK_INVALID")
    policy = load_mapping(DEFAULT_POLICY)
    required_names = policy["github_checks"]["required"]
    checks_by_name = {
        item.get("name"): item for item in checks_value
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    ci_pass = all(
        name in checks_by_name
        and (
            checks_by_name[name].get("bucket") in {"pass", "skipping"}
            or checks_by_name[name].get("state") in {"SUCCESS", "NEUTRAL", "SKIPPED"}
        )
        for name in required_names
    )
    no_unresolved = github_review_threads_resolved(repository, pr_number, root, runner)
    receipt_repository = context_receipt.get("repository") if isinstance(context_receipt, dict) else None
    receipt_route = context_receipt.get("route") if isinstance(context_receipt, dict) else None
    receipt_hash = context_receipt.get("receipt_sha256") if isinstance(context_receipt, dict) else None
    context_bound = isinstance(receipt_repository, dict) and receipt_repository.get("name") == repository and receipt_repository.get("head") == local_head and receipt_repository.get("tree") == local_tree and receipt_route == route and isinstance(receipt_hash, str) and bool(re.fullmatch(r"[0-9a-f]{64}", receipt_hash))
    exact_head = pr.get("number") == pr_number and pr.get("headRefOid") == local_head
    machine = {
        "pr_number": pr_number, "observed_head_sha": str(pr.get("headRefOid", "")), "observed_tree_sha": local_tree,
        "context_receipt_sha256": receipt_hash if isinstance(receipt_hash, str) else "0" * 64, "context_route": receipt_route if receipt_route in {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY"} else route,
        "exact_pr_head_bound": exact_head, "context_receipt_bound": context_bound,
        "required_tests_pass": ci_pass,
        "ci_exact_head_pass": exact_head and ci_pass,
        "full_gate_pass": ci_pass,
        "factory_fit_pass": bound_factory_fit_pass(root, context_receipt),
        "write_set_pass": ci_pass,
        "secret_scan_pass": ci_pass,
        "mergeable": pr.get("mergeable") == "MERGEABLE" and pr.get("state") == "OPEN" and pr.get("isDraft") is False,
        "no_unresolved_reviews": no_unresolved,
        "standard_merge": True, "branch_preserved": True, "settings_unchanged": True,
    }
    phrase_match = re.search(r"PR #([1-9][0-9]*), head ([0-9a-f]{40})", approval_phrase)
    approval_pr = int(phrase_match.group(1)) if phrase_match else pr_number
    approval_head = phrase_match.group(2) if phrase_match else local_head
    return {
        "schema": "smial.owner-attention-request", "schema_version": "2.0", "repository": repository,
        "route": route, "actor": actor, "action_class": "MERGE_PULL_REQUEST", "scope_bound": True,
        "stricter_stop_active": False,
        "triggers": {"auth_or_access_recovery": False, "material_owner_decision": False, "user_only_activation": False, "external_material_action": False, "unresolved_safety_or_truth_conflict": False},
        "owner_approval": {
            "phrase": approval_phrase,
            "pr_number": approval_pr,
            "head_sha": approval_head,
            "context_receipt_sha256": receipt_hash if isinstance(receipt_hash, str) else "0" * 64,
            "context_route": receipt_route if receipt_route in {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY"} else route,
        },
        "merge_checks": machine,
    }


def build_post_merge_receipt(
    root: Path,
    *,
    repository: str,
    pr_number: int,
    approved_head: str,
    expected_main: str,
    runner=run_read,
) -> dict[str, Any]:
    main = runner(["git", "rev-parse", "origin/main"], root).decode("ascii", errors="strict").strip()
    runs_value = json.loads(runner(["gh", "run", "list", "--repo", repository, "--commit", main, "--limit", "20", "--json", "headSha,status,conclusion,databaseId"], root).decode("utf-8", errors="strict"))
    if not isinstance(runs_value, list):
        raise ValueError("MAIN_CI_READBACK_INVALID")
    run = next((item for item in runs_value if isinstance(item, dict) and item.get("headSha") == main and item.get("status") == "completed" and item.get("conclusion") == "success"), None)
    if main != expected_main or run is None:
        raise ValueError("POST_MERGE_READBACK_FAILED")
    receipt: dict[str, Any] = {"schema": "smial.delivery-post-merge-receipt", "schema_version": "1.0", "repository": repository, "pr_number": pr_number, "approved_head": approved_head, "main": main, "main_ci": {"run_id": run.get("databaseId"), "conclusion": run.get("conclusion")}}
    receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    return receipt


def execute_guarded_merge(
    root: Path,
    *,
    repository: str,
    pr_number: int,
    route: str,
    actor: str,
    approval_phrase: str,
    context_receipt: dict[str, Any],
    runner=run_read,
) -> dict[str, Any]:
    request = build_grounded_merge_request(
        root,
        repository=repository,
        pr_number=pr_number,
        route=route,
        actor=actor,
        approval_phrase=approval_phrase,
        context_receipt=context_receipt,
        runner=runner,
    )
    result = evaluate(request, load_mapping(DEFAULT_POLICY))
    if result["decision"] != "AUTONOMOUS":
        return {
            "schema": "smial.guarded-merge-submission",
            "schema_version": "1.0",
            "decision": result["decision"],
            "reasons": result["reasons"],
            "merge_submitted": False,
        }
    runner(
        ["gh", "pr", "merge", str(pr_number), "--repo", repository, "--merge"],
        root,
    )
    merged = decode_json_mapping(
        runner(
            [
                "gh", "pr", "view", str(pr_number), "--repo", repository,
                "--json", "state,mergedAt,mergeCommit",
            ],
            root,
        ),
        "POST_MERGE_READBACK_INVALID",
    )
    commit = merged.get("mergeCommit")
    merge_oid = commit.get("oid") if isinstance(commit, dict) else None
    if (
        merged.get("state") != "MERGED"
        or not isinstance(merged.get("mergedAt"), str)
        or not isinstance(merge_oid, str)
        or re.fullmatch(r"[0-9a-f]{40}", merge_oid) is None
    ):
        raise ValueError("POST_MERGE_READBACK_FAILED")
    receipt: dict[str, Any] = {
        "schema": "smial.guarded-merge-submission",
        "schema_version": "1.0",
        "decision": "AUTONOMOUS",
        "reasons": result["reasons"],
        "repository": repository,
        "pr_number": pr_number,
        "approved_head": request["merge_checks"]["observed_head_sha"],
        "context_receipt_sha256": request["merge_checks"]["context_receipt_sha256"],
        "route": route,
        "merge_submitted": True,
        "merge_commit": merge_oid,
        "post_merge_ci": "PENDING_EXACT_MAIN_READBACK",
        "branch_deleted": False,
        "settings_changed": False,
    }
    receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    return receipt


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
        and approval["context_receipt_sha256"] == checks["context_receipt_sha256"]
        and approval["context_route"] == checks["context_route"] == request["route"]
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
            if key not in {"pr_number", "observed_head_sha", "observed_tree_sha", "context_receipt_sha256", "context_route"} and type(value) is not bool:
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

    if action_class == "MERGE_PULL_REQUEST":
        if route_policy["ordinary_merge"] == "FORBIDDEN":
            return decision("DENY", "ROUTE_MERGE_FORBIDDEN", version="2.0")
        checks = request["merge_checks"]
        if checks is not None:
            assert isinstance(checks, dict)
            for check in policy["merge_preconditions"]:
                if checks.get(check) is not True:
                    return decision(
                        "DENY", f"MERGE_CHECK_FAILED:{check}", version="2.0"
                    )
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
        return decision(
            "AUTONOMOUS", "DIRECT_AGENT_EXACT_MERGE_GATE_PASS", version="2.0"
        )

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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--request", type=Path)
    mode.add_argument("--guarded-merge", action="store_true")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--repository")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--route")
    parser.add_argument("--actor")
    parser.add_argument("--approval-phrase")
    parser.add_argument("--context-receipt", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.guarded_merge:
        required = (
            args.repository,
            args.pr_number,
            args.route,
            args.actor,
            args.approval_phrase,
            args.context_receipt,
        )
        if any(value is None for value in required):
            raise ValueError("GUARDED_MERGE_ARGUMENTS_REQUIRED")
        receipt = json.loads(args.context_receipt.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            raise ValueError("CONTEXT_RECEIPT_INVALID")
        result = execute_guarded_merge(
            args.root.resolve(),
            repository=args.repository,
            pr_number=args.pr_number,
            route=args.route,
            actor=args.actor,
            approval_phrase=args.approval_phrase,
            context_receipt=receipt,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("merge_submitted") is True else 2
    if args.request is None:
        raise ValueError("REQUEST_REQUIRED")
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    result = evaluate(request, load_mapping(args.policy))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] != "DENY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
