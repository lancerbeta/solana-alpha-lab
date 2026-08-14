#!/usr/bin/env python3
"""Portable Git-native Delivery Harness check and bounded-context CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import jsonschema
import yaml


ROUTES = {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY", "DESIGN_ONLY"}


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("UNSAFE_RELATIVE_PATH")
    normalized = value.replace("\\", "/")
    if PurePosixPath(normalized).is_absolute() or PureWindowsPath(value).is_absolute():
        raise ValueError("UNSAFE_RELATIVE_PATH")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("UNSAFE_RELATIVE_PATH")
    return PurePosixPath(*parts).as_posix()


def bounded(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / safe_relative(relative)).resolve()
    if root not in candidate.parents:
        raise ValueError("UNSAFE_RELATIVE_PATH")
    return candidate


def load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("MAPPING_REQUIRED")
    return value


def closed(root: Path, relative: str, schema: str) -> dict[str, Any]:
    value = load(bounded(root, relative))
    jsonschema.validate(value, json.loads(bounded(root, schema).read_text(encoding="utf-8")))
    return value


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False, shell=False)
    if result.returncode != 0:
        raise ValueError("GIT_IDENTITY_UNKNOWN")
    return result.stdout.decode("utf-8", errors="strict").strip()


def check(root: Path) -> dict[str, Any]:
    root = root.resolve()
    pairs = [
        ("delivery-harness/harness.yaml", "catalog/schemas/delivery_harness.schema.json"),
        ("delivery-harness/project-profile.yaml", "catalog/schemas/delivery_harness_project_profile.schema.json"),
        ("delivery-harness/context-map.yaml", "catalog/schemas/delivery_harness_context_map.schema.json"),
        ("delivery-harness/capability-radar.yaml", "catalog/schemas/delivery_harness_capability_radar.schema.json"),
        ("control/owner_attention_gate_v2.yaml", "catalog/schemas/owner_attention_gate_v2.schema.json"),
    ]
    errors: list[str] = []
    for relative, schema in pairs:
        try:
            closed(root, relative, schema)
        except Exception:
            errors.append("CONTRACT_INVALID:" + relative)
    required = (
        "AGENTS.md",
        ".agents/skills/delivery-harness/SKILL.md",
        ".cursor/commands/delivery-start.md",
        ".cursor/commands/delivery-status.md",
        ".cursor/commands/delivery-review.md",
        ".cursor/commands/delivery-finish.md",
    )
    for relative in required:
        if not bounded(root, relative).is_file():
            errors.append("ACTIVE_ADAPTER_MISSING:" + relative)
    return {
        "schema": "delivery-harness.check",
        "status": "PASS" if not errors else "PENDING",
        "errors": sorted(set(errors)),
        "side_effects": {"writes": 0, "network": 0},
    }


def parse_task(root: Path, task_id: str, relative: str) -> tuple[dict[str, Any], Path]:
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,127}", task_id):
        raise ValueError("TASK_ID_INVALID")
    path = bounded(root, relative)
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if match is None:
        raise ValueError("TASK_CONTRACT_SCHEMA_INVALID")
    metadata = yaml.safe_load(match.group(1))
    schema = json.loads(bounded(root, "catalog/schemas/delivery_harness_task_contract.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(metadata, schema)
    if not isinstance(metadata, dict) or metadata["task_id"] != task_id:
        raise ValueError("TASK_CONTRACT_MISMATCH")
    return metadata, path


def selected(root: Path, relative: str, *, role: str, lane: str, owner: str, stable_id: str | None = None) -> dict[str, Any]:
    path = bounded(root, relative)
    if not path.is_file():
        raise ValueError("REQUIRED_CONTEXT_MISSING")
    return {
        "semantic_role": role,
        "lane": lane,
        "truth_owner": owner,
        "path": safe_relative(relative),
        "stable_id": stable_id,
        "sha256": sha256(path),
        "state": "RESOLVED",
        "inclusion": "METADATA_ONLY" if path.stat().st_size <= 102400 else "REFERENCE_ONLY",
    }


def context(root: Path, task_id: str, contract: str, route: str) -> dict[str, Any]:
    root = root.resolve()
    if route not in ROUTES:
        raise ValueError("ACTIVE_ROUTE_UNKNOWN")
    harness = closed(root, "delivery-harness/harness.yaml", "catalog/schemas/delivery_harness.schema.json")
    profile = closed(root, "delivery-harness/project-profile.yaml", "catalog/schemas/delivery_harness_project_profile.schema.json")
    metadata, task_path = parse_task(root, task_id, contract)
    if route not in harness["active_routes"] or route not in metadata["allowed_routes"]:
        raise ValueError("TASK_ROUTE_NOT_ALLOWED")
    if profile["repository"]["name"] != metadata["expected_repository"]:
        raise ValueError("TASK_REPOSITORY_MISMATCH")
    head = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    branch = git(root, "branch", "--show-current") or "DETACHED"
    dirty = bool(git(root, "status", "--porcelain=v1"))
    binding = metadata["git_binding"]
    if git(root, "merge-base", "HEAD", binding["expected_base"]) != binding["expected_base"]:
        raise ValueError("TASK_EXPECTED_BASE_MISMATCH")
    if git(root, "rev-parse", binding["expected_upstream"]) != binding["expected_upstream_oid"]:
        raise ValueError("TASK_UPSTREAM_OID_MISMATCH")
    if branch != binding["expected_branch"]:
        raise ValueError("TASK_BRANCH_MISMATCH")
    if dirty and binding["dirty_mode"] == "FORBIDDEN":
        raise ValueError("TASK_DIRTY_STATE_FORBIDDEN")
    refs = [
        selected(root, "AGENTS.md", role="MISSION_AND_INVARIANTS", lane="L0", owner="REPOSITORY_POLICY"),
        selected(root, "delivery-harness/project-profile.yaml", role="MISSION_AND_INVARIANTS", lane="L0", owner="REPOSITORY_POLICY"),
        selected(root, safe_relative(contract), role="ACTIVE_BOUNDED_WORK", lane="L1", owner="EXACT_TASK_CONTRACT"),
    ]
    gaps = [{"semantic_role": "PRODUCT_ROADMAP", "lane": "L1", "truth_owner": "EXACT_GIT_ROADMAP_BINDING", "state": "EXPLICIT_GAP", "reason_code": "NO_EXACT_GIT_ROADMAP_BOUND"}]
    if metadata["context_requirements"]["roadmap_path"] is not None:
        gaps = []
        refs.append(selected(root, metadata["context_requirements"]["roadmap_path"], role="PRODUCT_ROADMAP", lane="L1", owner="EXACT_GIT_ROADMAP_BINDING"))
    receipt: dict[str, Any] = {
        "schema": "smial.delivery-context-receipt",
        "schema_version": "1.0",
        "harness_id": "DELIVERY_HARNESS_V1",
        "route": route,
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "repository": {"name": profile["repository"]["name"], "head": head, "tree": tree, "branch": branch, "dirty": dirty},
        "task": {"task_id": task_id, "path": safe_relative(contract), "sha256": sha256(task_path)},
        "selected": sorted(refs, key=lambda item: (item["lane"], item["semantic_role"], item["path"])),
        "gaps": gaps,
        "budgets": profile["context_budgets"],
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical_json(receipt)).hexdigest()
    jsonschema.validate(receipt, json.loads(bounded(root, "catalog/schemas/delivery_harness_context_receipt.schema.json").read_text(encoding="utf-8")))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--root", type=Path, default=Path.cwd())
    context_parser = sub.add_parser("context")
    context_parser.add_argument("--root", type=Path, default=Path.cwd())
    context_parser.add_argument("--task-id", required=True)
    context_parser.add_argument("--contract", required=True)
    context_parser.add_argument("--route", required=True)
    args = parser.parse_args()
    try:
        result = check(args.root) if args.command == "check" else context(args.root, args.task_id, args.contract, args.route)
    except Exception as exc:
        result = {"schema": "delivery-harness.error", "status": "BLOCKED", "reason": str(exc) if str(exc).isupper() else "STABLE_VALIDATION_ERROR"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") not in {"PENDING", "BLOCKED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
