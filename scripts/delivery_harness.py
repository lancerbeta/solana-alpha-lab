#!/usr/bin/env python3
"""Deterministic Git-native Delivery Harness context and control CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = "delivery-harness/harness.yaml"
PROFILE_PATH = "delivery-harness/project-profile.yaml"
CONTEXT_MAP_PATH = "delivery-harness/context-map.yaml"
RADAR_PATH = "delivery-harness/capability-radar.yaml"
CONTEXT_RECEIPT_SCHEMA = "catalog/schemas/delivery_harness_context_receipt.schema.json"
SAFE_TASK_ID = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
FORBIDDEN_DISCOVERY_NAMES = {"latest", "newest", "current", "last-modified"}
CAPABILITY_EVENT_TYPES = {
    "first_unattended_runtime": bool,
    "named_incident_consumer": bool,
    "owner_cockpit_workflow": bool,
    "named_behavior_question": bool,
    "measured_duckdb_boundary": bool,
    "second_analytics_consumer": bool,
    "material_version_documentation_delays": int,
}
PORTABLE_TEMPLATE_MAP = {
    "delivery-harness/templates/portable-project-profile.yaml": (
        "delivery-harness/project-profile.yaml"
    ),
    "delivery-harness/templates/bootstrap-prompt.md": (
        "delivery-harness/bootstrap-prompt.md"
    ),
}
CURRENT_REPOSITORY_URL = "https://github.com/lancerbeta/solana-alpha-lab"


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def safe_relative_path(value: str, *, code: str = "UNSAFE_RELATIVE_PATH") -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(code)
    normalized = value.replace("\\", "/")
    if PurePosixPath(normalized).is_absolute() or PureWindowsPath(value).is_absolute():
        raise ValueError(code)
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(code)
    return PurePosixPath(*parts).as_posix()


def resolve_bounded(root: Path, relative: str, *, code: str) -> Path:
    normalized = safe_relative_path(relative, code=code)
    resolved_root = root.resolve()
    candidate = (resolved_root / normalized).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError(code)
    return candidate


def load_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("MAPPING_REQUIRED")
    return value


def load_closed_document(path: Path, schema_path: Path) -> dict[str, Any]:
    document = load_mapping(path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ValueError("SCHEMA_MAPPING_REQUIRED")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(document, schema)
    return document


def git_text(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise ValueError("GIT_IDENTITY_UNKNOWN")
    return completed.stdout.decode("utf-8", errors="strict").strip()


def git_identity(root: Path) -> dict[str, Any]:
    head = git_text(root, "rev-parse", "HEAD")
    tree = git_text(root, "rev-parse", "HEAD^{tree}")
    branch = git_text(root, "branch", "--show-current") or "DETACHED"
    dirty = bool(git_text(root, "status", "--porcelain=v1"))
    if not re.fullmatch(r"[0-9a-f]{40}", head) or not re.fullmatch(
        r"[0-9a-f]{40}", tree
    ):
        raise ValueError("GIT_IDENTITY_UNKNOWN")
    return {"head": head, "tree": tree, "branch": branch, "dirty": dirty}


def reference_for_path(
    root: Path,
    relative: str,
    *,
    semantic_role: str,
    lane: str,
    truth_owner: str,
    stable_id: str | None,
    max_inline_bytes: int,
) -> dict[str, Any]:
    normalized = safe_relative_path(relative)
    path = resolve_bounded(root, normalized, code="UNSAFE_RELATIVE_PATH")
    if not path.is_file():
        raise FileNotFoundError(normalized)
    return {
        "semantic_role": semantic_role,
        "lane": lane,
        "truth_owner": truth_owner,
        "path": normalized,
        "stable_id": stable_id,
        "sha256": sha256_file(path),
        "state": "RESOLVED",
        "inclusion": (
            "REFERENCE_ONLY"
            if path.stat().st_size > max_inline_bytes
            else "METADATA_ONLY"
        ),
    }


def metadata_reference(
    *,
    semantic_role: str,
    lane: str,
    truth_owner: str,
    path: str,
    stable_id: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "semantic_role": semantic_role,
        "lane": lane,
        "truth_owner": truth_owner,
        "path": path,
        "stable_id": stable_id,
        "sha256": sha256_bytes(canonical_json_bytes(payload)),
        "state": "RESOLVED",
        "inclusion": "METADATA_ONLY",
    }


def explicit_gap(role: dict[str, Any], reason_code: str) -> dict[str, Any]:
    return {
        "semantic_role": role["semantic_role"],
        "lane": role["lane"],
        "truth_owner": role["truth_owner"],
        "state": "EXPLICIT_GAP",
        "reason_code": reason_code,
    }


def validate_task_contract(value: str) -> str:
    if not isinstance(value, str) or value.casefold() in FORBIDDEN_DISCOVERY_NAMES:
        raise ValueError("TASK_CONTRACT_EXACT_PATH_REQUIRED")
    try:
        normalized = safe_relative_path(value, code="TASK_CONTRACT_UNSAFE_PATH")
    except ValueError as exc:
        raise ValueError("TASK_CONTRACT_UNSAFE_PATH") from exc
    if any(part.casefold() in FORBIDDEN_DISCOVERY_NAMES for part in normalized.split("/")):
        raise ValueError("TASK_CONTRACT_DISCOVERY_FORBIDDEN")
    return normalized


def build_context_receipt(
    root: Path,
    *,
    task_id: str,
    task_contract: str,
    route: str,
    profile_path: str = PROFILE_PATH,
) -> dict[str, Any]:
    root = root.resolve()
    if not SAFE_TASK_ID.fullmatch(task_id):
        raise ValueError("TASK_ID_INVALID")
    contract_relative = validate_task_contract(task_contract)
    contract_path = resolve_bounded(
        root, contract_relative, code="TASK_CONTRACT_UNSAFE_PATH"
    )
    if not contract_path.is_file():
        raise ValueError("TASK_CONTRACT_NOT_FOUND")

    harness = load_closed_document(
        root / HARNESS_PATH,
        root / "catalog/schemas/delivery_harness.schema.json",
    )
    if route not in harness["active_routes"]:
        raise ValueError("ACTIVE_ROUTE_UNKNOWN")
    profile_relative = safe_relative_path(profile_path)
    profile = load_closed_document(
        root / profile_relative,
        root / "catalog/schemas/delivery_harness_project_profile.schema.json",
    )
    context_map = load_closed_document(
        root / profile["bindings"]["context_map"],
        root / "catalog/schemas/delivery_harness_context_map.schema.json",
    )
    budgets = profile["context_budgets"]
    max_inline = budgets["auto_inline_file_max_bytes"]
    identity = git_identity(root)
    selected: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    role_by_id = {role["semantic_role"]: role for role in context_map["roles"]}
    for relative in ("AGENTS.md", profile_relative):
        selected.append(
            reference_for_path(
                root,
                relative,
                semantic_role="MISSION_AND_INVARIANTS",
                lane="L0",
                truth_owner="REPOSITORY_POLICY",
                stable_id=("CTRL-AGENTS-001" if relative == "AGENTS.md" else "SOLANA_ALPHA_LAB_V1"),
                max_inline_bytes=max_inline,
            )
        )

    gaps.append(
        explicit_gap(
            role_by_id["PRODUCT_ROADMAP"],
            "NO_EXACT_GIT_ROADMAP_BOUND",
        )
    )
    selected.append(
        reference_for_path(
            root,
            contract_relative,
            semantic_role="ACTIVE_BOUNDED_WORK",
            lane="L1",
            truth_owner="EXACT_TASK_CONTRACT",
            stable_id=task_id,
            max_inline_bytes=max_inline,
        )
    )
    selected.append(
        metadata_reference(
            semantic_role="IMPLEMENTATION_STATE",
            lane="L1",
            truth_owner="GIT",
            path="git/HEAD",
            stable_id=identity["head"],
            payload=identity,
        )
    )
    selected.append(
        reference_for_path(
            root,
            profile["bindings"]["catalog_manifest"],
            semantic_role="STABLE_ASSETS_AND_RELATIONS",
            lane="L1",
            truth_owner="CATALOG",
            stable_id="SMIAL-PROJECT-ASSET-CATALOG",
            max_inline_bytes=max_inline,
        )
    )
    selected.append(
        reference_for_path(
            root,
            "configs/provider_route_capability_registry_v3.yaml",
            semantic_role="EXTERNAL_ROUTE_KNOWLEDGE",
            lane="L2",
            truth_owner="PROVIDER_ROUTE_REGISTRY",
            stable_id="PROVIDER_ROUTE_CAPABILITY_REGISTRY_V3",
            max_inline_bytes=max_inline,
        )
    )

    for role_id, reason in (
        ("LIFECYCLE", "NO_EXACT_LIFECYCLE_ID_REQUESTED"),
        ("ARCHITECTURE_DECISIONS", "NO_EXACT_ARCHITECTURE_ID_REQUESTED"),
        ("DELIVERY_EVIDENCE", "CANDIDATE_EVIDENCE_NOT_YET_BOUND"),
        ("HISTORICAL_CONTEXT", "DEFERRED_ON_DEMAND"),
    ):
        gaps.append(explicit_gap(role_by_id[role_id], reason))

    selected.sort(
        key=lambda item: (
            item["lane"],
            item["semantic_role"],
            item["stable_id"] or "",
            item["path"],
        )
    )
    gaps.sort(key=lambda item: (item["lane"], item["semantic_role"]))
    receipt: dict[str, Any] = {
        "schema": "smial.delivery-context-receipt",
        "schema_version": "1.0",
        "harness_id": harness["harness_id"],
        "route": route,
        "cloud_bundle_mode": harness["cloud_bundle"]["mode"],
        "repository": {"name": profile["repository"]["name"], **identity},
        "task": {
            "task_id": task_id,
            "path": contract_relative,
            "sha256": sha256_file(contract_path),
        },
        "selected": selected,
        "gaps": gaps,
        "budgets": budgets,
    }
    receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    errors = validate_context_receipt(receipt, root=root)
    if errors:
        raise ValueError(errors[0])
    if len(canonical_json_bytes(receipt)) > budgets["ordinary_receipt_max_bytes"]:
        raise ValueError("CONTEXT_RECEIPT_BUDGET_EXCEEDED")
    return receipt


def validate_context_receipt(
    receipt: dict[str, Any], *, root: Path = ROOT
) -> list[str]:
    try:
        schema = json.loads((root / CONTEXT_RECEIPT_SCHEMA).read_text(encoding="utf-8"))
        jsonschema.validate(receipt, schema)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError):
        return ["CONTEXT_RECEIPT_SCHEMA_INVALID"]
    unsigned = dict(receipt)
    observed = unsigned.pop("receipt_sha256", None)
    if observed != sha256_bytes(canonical_json_bytes(unsigned)):
        return ["CONTEXT_RECEIPT_HASH_MISMATCH"]
    return []


def write_context_receipt(root: Path, receipt: dict[str, Any]) -> Path:
    errors = validate_context_receipt(receipt, root=root)
    if errors:
        raise ValueError(errors[0])
    task_id = receipt["task"]["task_id"]
    if not SAFE_TASK_ID.fullmatch(task_id):
        raise ValueError("TASK_ID_INVALID")
    directory = root.resolve() / "local/delivery_harness/context"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{task_id.lower()}-{receipt['receipt_sha256'][:12]}.json"
    path.write_bytes(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
    return path


def check_harness(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    documents = (
        (HARNESS_PATH, "catalog/schemas/delivery_harness.schema.json"),
        (PROFILE_PATH, "catalog/schemas/delivery_harness_project_profile.schema.json"),
        (CONTEXT_MAP_PATH, "catalog/schemas/delivery_harness_context_map.schema.json"),
        (RADAR_PATH, "catalog/schemas/delivery_harness_capability_radar.schema.json"),
    )
    for document, schema in documents:
        try:
            load_closed_document(root / document, root / schema)
        except (OSError, ValueError, jsonschema.ValidationError):
            errors.append(f"CONTRACT_INVALID:{document}")
    active_baton_paths = [
        ".cursor/rules/50-github-baton.mdc",
        ".cursor/commands/baton-preflight.md",
    ]
    if any((root / path).exists() for path in active_baton_paths):
        errors.append("ACTIVE_ADAPTER_MIGRATION_PENDING")
    return {
        "schema": "smial.delivery-harness-check",
        "schema_version": "1.0",
        "harness_id": "DELIVERY_HARNESS_V1",
        "status": "PASS" if not errors else "PENDING",
        "errors": sorted(errors),
        "side_effects": {"local_writes": 0, "network_calls": 0},
    }


def validate_capability_events(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "schema_version",
        "events",
    }:
        raise ValueError("CAPABILITY_EVENTS_INVALID")
    if value["schema"] != "smial.delivery-harness-capability-events":
        raise ValueError("CAPABILITY_EVENTS_INVALID")
    if str(value["schema_version"]) != "1.0":
        raise ValueError("CAPABILITY_EVENTS_INVALID")
    events = value["events"]
    if not isinstance(events, dict) or not set(events).issubset(CAPABILITY_EVENT_TYPES):
        raise ValueError("CAPABILITY_EVENTS_INVALID")
    for key, item in events.items():
        expected = CAPABILITY_EVENT_TYPES[key]
        if expected is bool and type(item) is not bool:
            raise ValueError("CAPABILITY_EVENTS_INVALID")
        if expected is int and (type(item) is not int or item < 0):
            raise ValueError("CAPABILITY_EVENTS_INVALID")
    return events


def capability_condition_met(condition: str, events: dict[str, Any]) -> bool:
    if condition == "two_material_version_documentation_delays":
        return events.get("material_version_documentation_delays", 0) >= 2
    return events.get(condition) is True


def evaluate_capability_radar(
    radar: dict[str, Any], events_document: dict[str, Any]
) -> dict[str, Any]:
    events = validate_capability_events(events_document)
    matches = [
        candidate
        for candidate in radar["candidates"]
        if all(
            capability_condition_met(condition, events)
            for condition in candidate["conditions_all"]
        )
    ]
    match_ids = sorted(candidate["candidate_id"] for candidate in matches)
    base = {"install_authority": False, "matched_candidates": match_ids}
    if not matches:
        return {"decision": radar["default_decision"], "candidate": None, **base}
    if len(matches) > radar["max_candidates"]:
        return {
            "decision": "RADAR_REPLAN_REQUIRED",
            "candidate": None,
            **base,
        }
    return {"decision": "CANDIDATE", "candidate": matches[0], **base}


def portable_template_bytes(source_relative: str, template_root: Path) -> bytes:
    source = resolve_bounded(
        template_root, source_relative, code="PORTABLE_TEMPLATE_PATH_INVALID"
    )
    value = source.read_bytes()
    if source_relative.endswith("bootstrap-prompt.md"):
        value = value.replace(CURRENT_REPOSITORY_URL.encode("utf-8"), b"REPOSITORY_URL_REQUIRED")
    return value


def target_state(target: Path, destination: str) -> dict[str, Any]:
    path = resolve_bounded(target, destination, code="INITIALIZATION_PATH_INVALID")
    if not path.exists():
        return {"state": "MISSING", "sha256": None}
    if not path.is_file() or path.is_symlink():
        return {"state": "CONFLICT", "sha256": None}
    return {"state": "FILE", "sha256": sha256_file(path)}


def validate_initialization_target(target: Path) -> Path:
    if target.name.casefold() in {".cursor", ".codex", ".agents"}:
        raise ValueError("GLOBAL_CONFIG_TARGET_FORBIDDEN")
    if target.is_symlink():
        raise ValueError("INITIALIZATION_SYMLINK_TARGET_FORBIDDEN")
    resolved = target.resolve()
    if not resolved.is_dir():
        raise ValueError("INITIALIZATION_TARGET_DIRECTORY_REQUIRED")
    return resolved


def initialization_plan_hash(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("plan_sha256", None)
    return sha256_bytes(canonical_json_bytes(unsigned))


def plan_initialization(target: Path, template_root: Path) -> dict[str, Any]:
    target = validate_initialization_target(target)
    template_root = template_root.resolve()
    files: list[dict[str, Any]] = []
    creates: list[str] = []
    conflicts: list[str] = []
    for source, destination in sorted(PORTABLE_TEMPLATE_MAP.items()):
        payload = portable_template_bytes(source, template_root)
        payload_hash = sha256_bytes(payload)
        preimage = target_state(target, destination)
        if preimage["state"] == "MISSING":
            creates.append(destination)
        elif preimage["state"] != "FILE" or preimage["sha256"] != payload_hash:
            conflicts.append(destination)
        files.append(
            {
                "source": source,
                "destination": destination,
                "payload_utf8": payload.decode("utf-8"),
                "payload_sha256": payload_hash,
                "preimage": preimage,
            }
        )
    idempotent = not creates and not conflicts
    plan: dict[str, Any] = {
        "schema": "delivery-harness.initialization-plan",
        "schema_version": "1.0",
        "decision": "CONFLICT_REFUSAL" if conflicts else "APPLY_ALLOWED",
        "idempotent": idempotent,
        "creates": creates,
        "replaces": [],
        "removes": [],
        "conflicts": conflicts,
        "files": files,
    }
    plan["plan_sha256"] = initialization_plan_hash(plan)
    return plan


def apply_initialization(target: Path, plan: dict[str, Any]) -> dict[str, Any]:
    target = validate_initialization_target(target)
    if plan.get("decision") != "APPLY_ALLOWED":
        raise ValueError("INITIALIZATION_NOT_ALLOWED")
    if plan.get("plan_sha256") != initialization_plan_hash(plan):
        raise ValueError("INITIALIZATION_PLAN_HASH_INVALID")
    for item in plan.get("files", []):
        if not isinstance(item, dict):
            raise ValueError("INITIALIZATION_PLAN_INVALID")
        destination = item.get("destination")
        if not isinstance(destination, str):
            raise ValueError("INITIALIZATION_PLAN_INVALID")
        if target_state(target, destination) != item.get("preimage"):
            raise ValueError("PLAN_DRIFT")
        payload = item.get("payload_utf8")
        if not isinstance(payload, str) or sha256_bytes(payload.encode("utf-8")) != item.get(
            "payload_sha256"
        ):
            raise ValueError("INITIALIZATION_PLAN_INVALID")
    created: list[str] = []
    for item in plan["files"]:
        destination = item["destination"]
        if item["preimage"]["state"] == "FILE":
            continue
        path = resolve_bounded(target, destination, code="INITIALIZATION_PATH_INVALID")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["payload_utf8"], encoding="utf-8", newline="\n")
        created.append(destination)
    return {
        "schema": "delivery-harness.initialization-receipt",
        "schema_version": "1.0",
        "decision": "APPLIED",
        "plan_sha256": plan["plan_sha256"],
        "created": created,
        "rollback_inventory": {
            "created_paths": created,
            "preimage_hashes": {
                item["destination"]: item["preimage"]["sha256"]
                for item in plan["files"]
            },
            "automatic_rollback": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--root", type=Path, default=ROOT)
    check.add_argument("--format", choices=("json",), default="json")
    context = sub.add_parser("context")
    context.add_argument("--root", type=Path, default=ROOT)
    context.add_argument("--task-id", required=True)
    context.add_argument("--contract", required=True)
    context.add_argument("--route", required=True)
    context.add_argument("--write-receipt", action="store_true")
    context.add_argument("--format", choices=("json",), default="json")
    radar = sub.add_parser("radar")
    radar.add_argument("--root", type=Path, default=ROOT)
    radar.add_argument("--events", required=True)
    radar.add_argument("--format", choices=("json",), default="json")
    init = sub.add_parser("init")
    init.add_argument("--target", type=Path, required=True)
    init.add_argument("--profile", default="delivery-harness/templates/portable-project-profile.yaml")
    mode = init.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--apply", action="store_true")
    init.add_argument("--plan-sha256")
    init.add_argument("--format", choices=("json",), default="json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "check":
        result = check_harness(args.root.resolve())
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] == "PASS" else 2
    if args.command == "radar":
        events_path = resolve_bounded(
            args.root.resolve(), args.events, code="CAPABILITY_EVENTS_PATH_INVALID"
        )
        result = evaluate_capability_radar(
            load_mapping(args.root.resolve() / RADAR_PATH), load_mapping(events_path)
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result["decision"] != "RADAR_REPLAN_REQUIRED" else 2
    if args.command == "init":
        plan = plan_initialization(args.target, ROOT)
        if args.preview:
            result = plan
        else:
            if args.plan_sha256 != plan["plan_sha256"]:
                raise ValueError("PLAN_FINGERPRINT_REQUIRED_OR_STALE")
            result = apply_initialization(args.target, plan)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("decision") not in {"CONFLICT_REFUSAL"} else 2
    receipt = build_context_receipt(
        args.root,
        task_id=args.task_id,
        task_contract=args.contract,
        route=args.route,
    )
    if args.write_receipt:
        path = write_context_receipt(args.root, receipt)
        receipt = {**receipt, "local_receipt": path.relative_to(args.root.resolve()).as_posix()}
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
