#!/usr/bin/env python3
"""Stdlib-only portable Git-native Delivery Harness context CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


ROUTES = {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY", "DESIGN_ONLY"}
L2_ROLES = {
    "LIFECYCLE",
    "EXTERNAL_ROUTE_KNOWLEDGE",
    "ARCHITECTURE_DECISIONS",
    "DELIVERY_EVIDENCE",
}
L3_ROLES = {"HISTORICAL_CONTEXT"}
CONTEXT_ROLE_ORDER = (
    "MISSION_AND_INVARIANTS",
    "PRODUCT_ROADMAP",
    "ACTIVE_BOUNDED_WORK",
    "IMPLEMENTATION_STATE",
    "STABLE_ASSETS_AND_RELATIONS",
    "LIFECYCLE",
    "EXTERNAL_ROUTE_KNOWLEDGE",
    "ARCHITECTURE_DECISIONS",
    "DELIVERY_EVIDENCE",
    "HISTORICAL_CONTEXT",
)
ON_DEMAND_ROLE_ORDER = (
    "LIFECYCLE",
    "EXTERNAL_ROUTE_KNOWLEDGE",
    "ARCHITECTURE_DECISIONS",
    "DELIVERY_EVIDENCE",
    "HISTORICAL_CONTEXT",
)


def validate_context_role_set(context_map: dict[str, Any]) -> None:
    roles = context_map.get("roles")
    if not isinstance(roles, list) or len(roles) != len(CONTEXT_ROLE_ORDER):
        raise ValueError("CONTEXT_ROLE_SET_INVALID")
    role_ids = [
        role.get("semantic_role") if isinstance(role, dict) else None
        for role in roles
    ]
    if len(set(role_ids)) != len(role_ids) or set(role_ids) != set(CONTEXT_ROLE_ORDER):
        raise ValueError("CONTEXT_ROLE_SET_INVALID")


def historical_cloud_boundaries(profile: dict[str, Any]) -> tuple[str, ...]:
    registry = profile["bindings"]["historical_cloud_bundle_registry"]
    if registry is None:
        return ()
    normalized = safe_relative(registry)
    parent = PurePosixPath(normalized).parent.as_posix()
    return (
        (normalized,)
        if parent in {"", "."}
        else (normalized, parent + "/")
    )


def is_historical_cloud_path(relative: str, boundaries: tuple[str, ...]) -> bool:
    return any(
        relative.startswith(boundary) if boundary.endswith("/") else relative == boundary
        for boundary in boundaries
    )


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


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


def decode_json_mapping(text: str, code: str = "MAPPING_REQUIRED") -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(code)
            result[key] = item
        return result

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError(code)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ValueError(code) from None
    if not isinstance(value, dict):
        raise ValueError(code)
    return value


def load_json_mapping(path: Path, code: str = "MAPPING_REQUIRED") -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ValueError(code) from None
    return decode_json_mapping(text, code)


def exact_keys(value: dict[str, Any], required: set[str], code: str) -> None:
    if set(value) != required:
        raise ValueError(code)


def unique_strings(value: Any, *, minimum: int = 0) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= minimum
        and all(isinstance(item, str) and bool(item) for item in value)
        and len(set(value)) == len(value)
    )


def json_schema_type_matches(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "number": type(value) in {int, float},
        "null": value is None,
    }.get(expected, False)


def json_schema_equal(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)


def validate_schema_subset(
    value: Any, schema: dict[str, Any], *, root_schema: dict[str, Any] | None = None
) -> None:
    root_schema = schema if root_schema is None else root_schema
    reference = schema.get("$ref")
    if reference is not None:
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            raise ValueError("SCHEMA_UNSUPPORTED")
        name = reference.removeprefix("#/$defs/")
        definitions = root_schema.get("$defs")
        if not isinstance(definitions, dict) or not isinstance(definitions.get(name), dict):
            raise ValueError("SCHEMA_UNSUPPORTED")
        validate_schema_subset(value, definitions[name], root_schema=root_schema)
        return
    alternatives = schema.get("oneOf")
    if alternatives is not None:
        if not isinstance(alternatives, list):
            raise ValueError("SCHEMA_UNSUPPORTED")
        matches = 0
        for alternative in alternatives:
            if not isinstance(alternative, dict):
                raise ValueError("SCHEMA_UNSUPPORTED")
            try:
                validate_schema_subset(value, alternative, root_schema=root_schema)
                matches += 1
            except ValueError:
                pass
        if matches != 1:
            raise ValueError("SCHEMA_VALIDATION_FAILED")
        return
    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not all(isinstance(item, str) for item in expected_types) or not any(
            json_schema_type_matches(value, item) for item in expected_types
        ):
            raise ValueError("SCHEMA_VALIDATION_FAILED")
    if "const" in schema and not json_schema_equal(value, schema["const"]):
        raise ValueError("SCHEMA_VALIDATION_FAILED")
    if "enum" in schema:
        choices = schema["enum"]
        if not isinstance(choices, list) or not any(
            json_schema_equal(value, item) for item in choices
        ):
            raise ValueError("SCHEMA_VALIDATION_FAILED")
    if isinstance(value, str):
        if type(schema.get("minLength")) is int and len(value) < schema["minLength"]:
            raise ValueError("SCHEMA_VALIDATION_FAILED")
        pattern = schema.get("pattern")
        if pattern is not None and (
            not isinstance(pattern, str) or re.search(pattern, value) is None
        ):
            raise ValueError("SCHEMA_VALIDATION_FAILED")
    if isinstance(value, dict):
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        if not isinstance(required, list) or not isinstance(properties, dict):
            raise ValueError("SCHEMA_UNSUPPORTED")
        if any(not isinstance(item, str) for item in required) or not set(required) <= set(value):
            raise ValueError("SCHEMA_VALIDATION_FAILED")
        if schema.get("additionalProperties") is False and not set(value) <= set(properties):
            raise ValueError("SCHEMA_VALIDATION_FAILED")
        for key, item in value.items():
            child = properties.get(key)
            if child is not None:
                if not isinstance(child, dict):
                    raise ValueError("SCHEMA_UNSUPPORTED")
                validate_schema_subset(item, child, root_schema=root_schema)
    if isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if type(minimum) is int and len(value) < minimum:
            raise ValueError("SCHEMA_VALIDATION_FAILED")
        if type(maximum) is int and len(value) > maximum:
            raise ValueError("SCHEMA_VALIDATION_FAILED")
        if schema.get("uniqueItems") is True:
            fingerprints = [canonical_json(item) for item in value]
            if len(set(fingerprints)) != len(fingerprints):
                raise ValueError("SCHEMA_VALIDATION_FAILED")
        prefix_items = schema.get("prefixItems", [])
        if not isinstance(prefix_items, list):
            raise ValueError("SCHEMA_UNSUPPORTED")
        for index, child in enumerate(prefix_items):
            if index >= len(value):
                break
            if not isinstance(child, dict):
                raise ValueError("SCHEMA_UNSUPPORTED")
            validate_schema_subset(value[index], child, root_schema=root_schema)
        items = schema.get("items")
        if items is False and len(value) > len(prefix_items):
            raise ValueError("SCHEMA_VALIDATION_FAILED")
        if isinstance(items, dict):
            start = len(prefix_items) if prefix_items else 0
            for item in value[start:]:
                validate_schema_subset(item, items, root_schema=root_schema)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=False, shell=False
    )
    if result.returncode != 0:
        raise ValueError("GIT_IDENTITY_UNKNOWN")
    return result.stdout.decode("utf-8", errors="strict").strip()


def github_repository_from_origin(value: str) -> str:
    for pattern in (
        r"git@github\.com:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$",
        r"ssh://git@github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
        r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    ):
        match = re.fullmatch(pattern, value)
        if match is not None:
            return match.group(1)
    raise ValueError("TASK_REPOSITORY_ORIGIN_MISMATCH")


def load_core(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contracts = (
        (
            "delivery-harness/harness.yaml",
            "catalog/schemas/delivery_harness.schema.json",
            "HARNESS_CONTRACT_INVALID",
        ),
        (
            "delivery-harness/project-profile.yaml",
            "catalog/schemas/delivery_harness_project_profile.schema.json",
            "PROFILE_CONTRACT_INVALID",
        ),
        (
            "delivery-harness/context-map.yaml",
            "catalog/schemas/delivery_harness_context_map.schema.json",
            "CONTEXT_MAP_INVALID",
        ),
    )
    documents: list[dict[str, Any]] = []
    for relative, schema_relative, code in contracts:
        document = load_json_mapping(bounded(root, relative), code)
        schema = load_json_mapping(bounded(root, schema_relative), code)
        try:
            validate_schema_subset(document, schema)
        except ValueError:
            raise ValueError(code) from None
        documents.append(document)
    harness, profile, context_map = documents
    validate_context_role_set(context_map)
    return harness, profile, context_map


def check(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    delivery_gate_ready = False
    try:
        _, profile, _ = load_core(root)
        validation = profile["validation"]
        delivery_gate_ready = (
            validation["github_ci_bound"] is True
            and
            (validation["primary"] is not None or validation["fallback"] is not None)
            and validation["credential_scan"] is not None
        )
        policy = load_json_mapping(
            bounded(root, "control/owner_attention_gate_v2.yaml"),
            "OWNER_POLICY_INVALID",
        )
        policy_schema = load_json_mapping(
            bounded(root, "catalog/schemas/owner_attention_gate_v2.schema.json"),
            "OWNER_POLICY_INVALID",
        )
        radar = load_json_mapping(
            bounded(root, "delivery-harness/capability-radar.yaml"),
            "CAPABILITY_RADAR_INVALID",
        )
        radar_schema = load_json_mapping(
            bounded(root, "catalog/schemas/delivery_harness_capability_radar.schema.json"),
            "CAPABILITY_RADAR_INVALID",
        )
        validate_schema_subset(policy, policy_schema)
        validate_schema_subset(radar, radar_schema)
        repository = profile["repository"]["name"]
        if policy.get("repository") != repository:
            errors.append("REPOSITORY_IDENTITY_DIVERGENCE")
        if (
            github_repository_from_origin(git(root, "remote", "get-url", "origin"))
            != repository
        ):
            errors.append("REPOSITORY_IDENTITY_DIVERGENCE")
    except (KeyError, TypeError, ValueError):
        errors.append("CORE_CONTRACT_INVALID")
    required = (
        "AGENTS.md",
        ".agents/skills/delivery-harness/SKILL.md",
        ".cursor/commands/delivery-start.md",
        ".cursor/commands/delivery-status.md",
        ".cursor/commands/delivery-review.md",
        ".cursor/commands/delivery-finish.md",
        "delivery-harness/runtime-requirements.txt",
        "catalog/schemas/delivery_harness_context_receipt.schema.json",
        "catalog/schemas/delivery_harness_task_contract.schema.json",
        "catalog/schemas/delivery_harness_completion_evidence.schema.json",
        "catalog/schemas/delivery_harness_independent_review_evidence.schema.json",
    )
    for relative in required:
        try:
            if not bounded(root, relative).is_file():
                errors.append("ACTIVE_ADAPTER_MISSING:" + relative)
        except ValueError:
            errors.append("ACTIVE_ADAPTER_MISSING:" + relative)
    baton = re.compile(
        r"\bbaton[_-](?:preflight|receipt|contract|scope)\b|"
        r"route\s*[:=]\s*GITHUB_BATON|use\s+GITHUB_BATON",
        re.IGNORECASE,
    )
    active_files = [root / "AGENTS.md"]
    for relative in (
        ".cursor/rules",
        ".cursor/commands",
        ".cursor/agents",
        ".agents/skills/delivery-harness",
    ):
        directory = root / relative
        if not directory.is_dir():
            continue
        active_files.extend(path for path in directory.rglob("*") if path.is_file())
    for path in active_files:
        try:
            if baton.search(path.read_text(encoding="utf-8")):
                errors.append("ACTIVE_BATON_REFERENCE")
        except (OSError, UnicodeDecodeError):
            errors.append("ACTIVE_ADAPTER_INVALID")
    return {
        "schema": "delivery-harness.check",
        "status": "PASS" if not errors else "PENDING",
        "delivery_gate_ready": delivery_gate_ready,
        "errors": sorted(set(errors)),
        "side_effects": {"writes": 0, "network": 0},
    }


def validate_task(metadata: dict[str, Any], task_id: str) -> None:
    code = "TASK_CONTRACT_SCHEMA_INVALID"
    exact_keys(
        metadata,
        {
            "task_id", "task_version", "status", "as_of", "owner",
            "allowed_routes", "expected_repository", "git_binding", "objective",
            "managed_write_set", "external_caps", "stop_conditions",
            "context_requirements",
        },
        code,
    )
    if metadata.get("task_id") != task_id:
        raise ValueError("TASK_CONTRACT_MISMATCH")
    if not (
        isinstance(metadata.get("task_id"), str)
        and re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,127}", metadata["task_id"])
        and isinstance(metadata.get("task_version"), str)
        and re.fullmatch(r"[0-9]+\.[0-9]+", metadata["task_version"])
        and metadata.get("status")
        in {"READY", "IN_PROGRESS", "IMPLEMENTED_UNVERIFIED", "VALIDATED", "DONE"}
        and isinstance(metadata.get("as_of"), str)
        and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", metadata["as_of"])
        and isinstance(metadata.get("owner"), str)
        and bool(metadata["owner"])
        and unique_strings(metadata.get("allowed_routes"), minimum=1)
        and set(metadata["allowed_routes"]) <= ROUTES
        and isinstance(metadata.get("expected_repository"), str)
        and re.fullmatch(
            r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
            metadata["expected_repository"],
        )
        and isinstance(metadata.get("objective"), str)
        and len(metadata["objective"]) >= 20
        and unique_strings(metadata.get("stop_conditions"), minimum=1)
    ):
        raise ValueError(code)
    binding = metadata.get("git_binding")
    requirements = metadata.get("context_requirements")
    caps = metadata.get("external_caps")
    managed = metadata.get("managed_write_set")
    if not (
        isinstance(binding, dict)
        and isinstance(requirements, dict)
        and isinstance(caps, dict)
    ):
        raise ValueError(code)
    exact_keys(
        binding,
        {"expected_base", "expected_upstream", "expected_upstream_oid", "expected_branch", "dirty_mode"},
        code,
    )
    if not (
        isinstance(binding.get("expected_base"), str)
        and re.fullmatch(r"[0-9a-f]{40}", binding["expected_base"])
        and isinstance(binding.get("expected_upstream"), str)
        and bool(binding["expected_upstream"])
        and isinstance(binding.get("expected_upstream_oid"), str)
        and re.fullmatch(r"[0-9a-f]{40}", binding["expected_upstream_oid"])
        and isinstance(binding.get("expected_branch"), str)
        and re.fullmatch(r"[A-Za-z0-9._/-]+", binding["expected_branch"])
        and binding.get("dirty_mode") in {"FORBIDDEN", "ALLOW_REPORTED"}
    ):
        raise ValueError(code)
    exact_keys(
        caps,
        {
            "network", "credentials", "external_system",
            "signing_or_financial_action", "cash_spend", "deployment",
        },
        code,
    )
    if any(type(value) is not bool for value in caps.values()):
        raise ValueError(code)
    if isinstance(managed, list):
        if not unique_strings(managed, minimum=1):
            raise ValueError(code)
    elif isinstance(managed, dict):
        exact_keys(managed, {"path", "heading"}, code)
        if not (
            isinstance(managed.get("path"), str)
            and bool(managed["path"])
            and managed.get("heading") == "Managed write set"
        ):
            raise ValueError(code)
    else:
        raise ValueError(code)
    required_requirement_keys = {
        "catalog_asset_ids",
        "l2_roles",
        "l3_roles",
        "roadmap_path",
        "exact_role_paths",
    }
    allowed_requirement_keys = required_requirement_keys | {"exact_role_asset_ids"}
    if not required_requirement_keys <= set(requirements) <= allowed_requirement_keys:
        raise ValueError(code)
    paths = requirements.get("exact_role_paths")
    if not isinstance(paths, dict) or set(paths) != L2_ROLES | L3_ROLES:
        raise ValueError(code)
    if not (
        unique_strings(requirements.get("catalog_asset_ids"))
        and unique_strings(requirements.get("l2_roles"))
        and set(requirements["l2_roles"]) <= L2_ROLES
        and unique_strings(requirements.get("l3_roles"))
        and set(requirements["l3_roles"]) <= L3_ROLES
        and (
            requirements.get("roadmap_path") is None
            or (
                isinstance(requirements.get("roadmap_path"), str)
                and bool(requirements["roadmap_path"])
            )
        )
        and all(unique_strings(value) for value in paths.values())
    ):
        raise ValueError(code)
    asset_ids = requirements.get("exact_role_asset_ids")
    if asset_ids is not None:
        if not isinstance(asset_ids, dict) or set(asset_ids) != L2_ROLES | L3_ROLES:
            raise ValueError(code)
        if not all(unique_strings(value) for value in asset_ids.values()):
            raise ValueError(code)
        if any(asset_ids[role] for role in asset_ids):
            raise ValueError("REQUIRED_CATALOG_ASSET_NOT_RESOLVED")


def parse_task(root: Path, task_id: str, relative: str) -> tuple[dict[str, Any], Path]:
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,127}", task_id):
        raise ValueError("TASK_ID_INVALID")
    path = bounded(root, relative)
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if match is None:
        raise ValueError("TASK_CONTRACT_SCHEMA_INVALID")
    try:
        metadata = decode_json_mapping(
            match.group(1), "TASK_CONTRACT_JSON_FRONTMATTER_REQUIRED"
        )
    except ValueError:
        raise ValueError("TASK_CONTRACT_JSON_FRONTMATTER_REQUIRED") from None
    if not isinstance(metadata, dict):
        raise ValueError("TASK_CONTRACT_SCHEMA_INVALID")
    validate_task(metadata, task_id)
    return metadata, path


def selected(
    root: Path,
    relative: str,
    *,
    role: str,
    lane: str,
    owner: str,
    stable_id: str | None = None,
    historical_boundaries: tuple[str, ...] = (),
) -> dict[str, Any]:
    normalized = safe_relative(relative)
    if is_historical_cloud_path(normalized, historical_boundaries) and not (
        role == "HISTORICAL_CONTEXT" and lane == "L3"
    ):
        raise ValueError("SOURCE_HISTORY_ROLE_MISMATCH")
    path = bounded(root, relative)
    if not path.is_file():
        raise ValueError("REQUIRED_CONTEXT_MISSING")
    return {
        "semantic_role": role,
        "lane": lane,
        "truth_owner": owner,
        "path": normalized,
        "stable_id": stable_id,
        "sha256": sha256(path),
        "state": "RESOLVED",
        "inclusion": (
            "METADATA_ONLY" if path.stat().st_size <= 102400 else "REFERENCE_ONLY"
        ),
        "resolution_method": "EXACT_PATH",
    }


def metadata_selected(
    *,
    role: str,
    lane: str,
    owner: str,
    path: str,
    stable_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "semantic_role": role,
        "lane": lane,
        "truth_owner": owner,
        "path": path,
        "stable_id": stable_id,
        "sha256": hashlib.sha256(canonical_json(payload)).hexdigest(),
        "state": "RESOLVED",
        "inclusion": "METADATA_ONLY",
    }


def build_context_receipt(
    root: Path, *, task_id: str, task_contract: str, route: str
) -> dict[str, Any]:
    root = root.resolve()
    if route not in ROUTES:
        raise ValueError("ACTIVE_ROUTE_UNKNOWN")
    harness, profile, context_map = load_core(root)
    metadata, task_path = parse_task(root, task_id, task_contract)
    if route not in harness["active_routes"] or route not in metadata["allowed_routes"]:
        raise ValueError("TASK_ROUTE_NOT_ALLOWED")
    repository = profile["repository"]["name"]
    cloud_boundaries = historical_cloud_boundaries(profile)
    if repository != metadata["expected_repository"]:
        raise ValueError("TASK_REPOSITORY_MISMATCH")
    if github_repository_from_origin(git(root, "remote", "get-url", "origin")) != repository:
        raise ValueError("TASK_REPOSITORY_ORIGIN_MISMATCH")
    head = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    branch = git(root, "branch", "--show-current")
    github_head_ref = os.environ.get("GITHUB_HEAD_REF", "")
    if not branch and os.environ.get("GITHUB_ACTIONS") == "true" and re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}", github_head_ref
    ):
        branch = github_head_ref
    branch = branch or "DETACHED"
    dirty = bool(git(root, "status", "--porcelain=v1"))
    binding = metadata["git_binding"]
    if git(root, "merge-base", "HEAD", binding["expected_upstream"]) != binding["expected_base"]:
        raise ValueError("TASK_EXPECTED_BASE_MISMATCH")
    if git(root, "rev-parse", binding["expected_upstream"]) != binding["expected_upstream_oid"]:
        raise ValueError("TASK_UPSTREAM_OID_MISMATCH")
    if branch != binding["expected_branch"]:
        raise ValueError("TASK_BRANCH_MISMATCH")
    if dirty and binding["dirty_mode"] == "FORBIDDEN":
        raise ValueError("TASK_DIRTY_STATE_FORBIDDEN")
    refs = [
        selected(root, "AGENTS.md", role="MISSION_AND_INVARIANTS", lane="L0", owner="REPOSITORY_POLICY", historical_boundaries=cloud_boundaries),
        selected(root, "delivery-harness/project-profile.yaml", role="MISSION_AND_INVARIANTS", lane="L0", owner="REPOSITORY_POLICY", historical_boundaries=cloud_boundaries),
        selected(root, safe_relative(task_contract), role="ACTIVE_BOUNDED_WORK", lane="L1", owner="EXACT_TASK_CONTRACT", stable_id=task_id, historical_boundaries=cloud_boundaries),
        metadata_selected(
            role="IMPLEMENTATION_STATE", lane="L1", owner="GIT", path="git/HEAD",
            stable_id=head, payload={"head": head, "tree": tree, "branch": branch, "dirty": dirty},
        ),
    ]
    roles = {item["semantic_role"]: item for item in context_map["roles"]}
    requirements = metadata["context_requirements"]
    gaps: list[dict[str, Any]] = []
    roadmap = requirements["roadmap_path"]
    if roadmap is None:
        role = roles["PRODUCT_ROADMAP"]
        gaps.append({"semantic_role": "PRODUCT_ROADMAP", "lane": role["lane"], "truth_owner": role["truth_owner"], "state": "EXPLICIT_GAP", "reason_code": "NO_EXACT_GIT_ROADMAP_BOUND"})
    else:
        role = roles["PRODUCT_ROADMAP"]
        refs.append(selected(root, roadmap, role="PRODUCT_ROADMAP", lane=role["lane"], owner=role["truth_owner"], historical_boundaries=cloud_boundaries))
    if requirements["catalog_asset_ids"]:
        raise ValueError("REQUIRED_CATALOG_ASSET_NOT_RESOLVED")
    required_roles = set(requirements["l2_roles"]) | set(requirements["l3_roles"])
    for role_id in ON_DEMAND_ROLE_ORDER:
        role = roles[role_id]
        if role_id not in required_roles:
            gaps.append({"semantic_role": role_id, "lane": role["lane"], "truth_owner": role["truth_owner"], "state": "EXPLICIT_GAP", "reason_code": "DEFERRED_ON_DEMAND"})
            continue
        paths = requirements["exact_role_paths"][role_id]
        if not paths:
            raise ValueError("REQUIRED_CONTEXT_REFERENCE_NOT_BOUND:" + role_id)
        for relative in paths:
            refs.append(selected(root, relative, role=role_id, lane=role["lane"], owner=role["truth_owner"], historical_boundaries=cloud_boundaries))
    refs.sort(key=lambda item: (item["lane"], item["semantic_role"], item["stable_id"] or "", item["path"]))
    gaps.sort(key=lambda item: (item["lane"], item["semantic_role"]))
    receipt: dict[str, Any] = {
        "schema": "smial.delivery-context-receipt",
        "schema_version": "1.0",
        "harness_id": "DELIVERY_HARNESS_V1",
        "route": route,
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "repository": {"name": repository, "head": head, "tree": tree, "branch": branch, "dirty": dirty},
        "task": {"task_id": task_id, "path": safe_relative(task_contract), "sha256": sha256(task_path)},
        "selected": refs,
        "gaps": gaps,
        "budgets": profile["context_budgets"],
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical_json(receipt)).hexdigest()
    if len(canonical_json(receipt)) > profile["context_budgets"]["ordinary_receipt_max_bytes"]:
        raise ValueError("CONTEXT_RECEIPT_BUDGET_EXCEEDED")
    receipt_schema = load_json_mapping(
        bounded(root, "catalog/schemas/delivery_harness_context_receipt.schema.json"),
        "CONTEXT_RECEIPT_SCHEMA_INVALID",
    )
    validate_schema_subset(receipt, receipt_schema)
    return receipt


def build_live_pr_head_receipt(
    root: Path, *, pr_number: int, route: str
) -> dict[str, Any]:
    root = root.resolve()
    if type(pr_number) is not int or pr_number < 1:
        raise ValueError("PR_NUMBER_INVALID")
    if route not in ROUTES:
        raise ValueError("ACTIVE_ROUTE_UNKNOWN")
    harness, profile, context_map = load_core(root)
    merge_policy = harness.get("merge_policy")
    if not isinstance(merge_policy, dict) or "LIVE_PR_HEAD" not in merge_policy.get("identity_modes", []):
        raise ValueError("LIVE_PR_HEAD_NOT_ENABLED")
    if route not in harness["active_routes"]:
        raise ValueError("TASK_ROUTE_NOT_ALLOWED")
    repository = profile["repository"]["name"]
    cloud_boundaries = historical_cloud_boundaries(profile)
    if github_repository_from_origin(git(root, "remote", "get-url", "origin")) != repository:
        raise ValueError("TASK_REPOSITORY_ORIGIN_MISMATCH")
    head = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    branch = git(root, "branch", "--show-current") or "DETACHED"
    dirty = bool(git(root, "status", "--porcelain=v1"))
    identity = {"head": head, "tree": tree, "branch": branch, "dirty": dirty}
    roles = {item["semantic_role"]: item for item in context_map["roles"]}
    refs = [
        selected(root, "AGENTS.md", role="MISSION_AND_INVARIANTS", lane="L0", owner="REPOSITORY_POLICY", historical_boundaries=cloud_boundaries),
        selected(root, "delivery-harness/project-profile.yaml", role="MISSION_AND_INVARIANTS", lane="L0", owner="REPOSITORY_POLICY", historical_boundaries=cloud_boundaries),
        metadata_selected(
            role="ACTIVE_BOUNDED_WORK", lane="L1", owner="LIVE_PR_HEAD",
            path=f"github/pull/{pr_number}", stable_id="CONTROL-PR",
            payload={"pr_number": pr_number, "identity_mode": "LIVE_PR_HEAD", "head": head},
        ),
        metadata_selected(
            role="IMPLEMENTATION_STATE", lane="L1", owner="GIT", path="git/HEAD",
            stable_id=head, payload=identity,
        ),
    ]
    gaps: list[dict[str, Any]] = []
    role = roles["PRODUCT_ROADMAP"]
    gaps.append({"semantic_role": "PRODUCT_ROADMAP", "lane": role["lane"], "truth_owner": role["truth_owner"], "state": "EXPLICIT_GAP", "reason_code": "NO_EXACT_GIT_ROADMAP_BOUND"})
    for role_id in ON_DEMAND_ROLE_ORDER:
        role = roles[role_id]
        gaps.append({"semantic_role": role_id, "lane": role["lane"], "truth_owner": role["truth_owner"], "state": "EXPLICIT_GAP", "reason_code": "DEFERRED_ON_DEMAND"})
    refs.sort(key=lambda item: (item["lane"], item["semantic_role"], item["stable_id"] or "", item["path"]))
    gaps.sort(key=lambda item: (item["lane"], item["semantic_role"]))
    receipt: dict[str, Any] = {
        "schema": "smial.delivery-context-receipt",
        "schema_version": "1.0",
        "harness_id": "DELIVERY_HARNESS_V1",
        "route": route,
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "repository": {"name": repository, **identity},
        "control_pr": {"pr_number": pr_number, "identity_mode": "LIVE_PR_HEAD"},
        "selected": refs,
        "gaps": gaps,
        "budgets": profile["context_budgets"],
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical_json(receipt)).hexdigest()
    if len(canonical_json(receipt)) > profile["context_budgets"]["ordinary_receipt_max_bytes"]:
        raise ValueError("CONTEXT_RECEIPT_BUDGET_EXCEEDED")
    receipt_schema = load_json_mapping(
        bounded(root, "catalog/schemas/delivery_harness_context_receipt.schema.json"),
        "CONTEXT_RECEIPT_SCHEMA_INVALID",
    )
    validate_schema_subset(receipt, receipt_schema)
    return receipt


def context(root: Path, task_id: str, contract: str, route: str) -> dict[str, Any]:
    return build_context_receipt(
        root, task_id=task_id, task_contract=contract, route=route
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--root", type=Path, default=Path.cwd())
    context_parser = sub.add_parser("context")
    context_parser.add_argument("--root", type=Path, default=Path.cwd())
    context_parser.add_argument("--task-id")
    context_parser.add_argument("--contract")
    context_parser.add_argument("--pr", type=int)
    context_parser.add_argument("--route", required=True)
    args = parser.parse_args()
    try:
        if args.command == "check":
            result = check(args.root)
        elif args.pr is not None:
            if args.task_id is not None or args.contract is not None:
                raise ValueError("CONTEXT_IDENTITY_MODE_CONFLICT")
            result = build_live_pr_head_receipt(
                args.root, pr_number=args.pr, route=args.route
            )
        else:
            if not args.task_id or not args.contract:
                raise ValueError("TASK_CONTRACT_EXACT_PATH_REQUIRED")
            result = context(args.root, args.task_id, args.contract, args.route)
    except Exception as exc:
        result = {
            "schema": "delivery-harness.error",
            "status": "BLOCKED",
            "reason": str(exc) if str(exc).isupper() else "STABLE_VALIDATION_ERROR",
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") not in {"PENDING", "BLOCKED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
