#!/usr/bin/env python3
"""Deterministic Git-native Delivery Harness context and control CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:  # init must remain stdlib-only in a clean target environment.
    import jsonschema  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - exercised by isolated subprocess.
    jsonschema = None  # type: ignore[assignment]

try:  # init consumes JSON-compatible templates and does not need PyYAML.
    import yaml  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - exercised by isolated subprocess.
    yaml = None  # type: ignore[assignment]


class _DependencyValidationError(Exception):
    """Stable exception type when optional project dependencies are absent."""


JSONSCHEMA_VALIDATION_ERROR = (
    jsonschema.ValidationError if jsonschema is not None else _DependencyValidationError
)
YAML_ERROR = yaml.YAMLError if yaml is not None else _DependencyValidationError


def load_json_unique(text: str, *, code: str = "JSON_MAPPING_INVALID") -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(code)
            result[key] = value
        return result

    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError(code)),
        )
    except (json.JSONDecodeError, ValueError):
        raise ValueError(code) from None


if yaml is not None:
    class UniqueKeySafeLoader(yaml.SafeLoader):
        pass


    def _construct_unique_mapping(
        loader: Any, node: Any, deep: bool = False
    ) -> dict[Any, Any]:
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    "found an unhashable key", key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    f"found duplicate key {key!r}", key_node.start_mark,
                )
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping


    UniqueKeySafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _construct_unique_mapping,
    )


def load_yaml_unique(text: str) -> Any:
    if yaml is None:
        return load_json_unique(text, code="PROJECT_RUNTIME_DEPENDENCY_MISSING")
    return yaml.load(text, Loader=UniqueKeySafeLoader)


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = "delivery-harness/harness.yaml"
PROFILE_PATH = "delivery-harness/project-profile.yaml"
CONTEXT_MAP_PATH = "delivery-harness/context-map.yaml"
RADAR_PATH = "delivery-harness/capability-radar.yaml"
CONTEXT_RECEIPT_SCHEMA = "catalog/schemas/delivery_harness_context_receipt.schema.json"
TASK_CONTRACT_SCHEMA = "catalog/schemas/delivery_harness_task_contract.schema.json"
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
PORTABLE_MANIFEST_PATH = "delivery-harness/templates/portable-bundle-manifest.json"
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
    value = load_yaml_unique(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("MAPPING_REQUIRED")
    return value


def load_closed_document(path: Path, schema_path: Path) -> dict[str, Any]:
    if jsonschema is None:
        raise ValueError("PROJECT_RUNTIME_DEPENDENCY_MISSING")
    document = load_mapping(path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ValueError("SCHEMA_MAPPING_REQUIRED")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(document, schema)
    return document


def validate_portable_profile_for_init(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != {
        "schema", "schema_version", "profile_id", "harness_id", "mode",
        "repository", "bindings", "working_memory", "context_budgets",
        "validation", "authority",
    }:
        raise ValueError("PORTABLE_PROFILE_INVALID")
    if not (
        document["schema"] == "smial.delivery-harness-project-profile"
        and document["schema_version"] == "1.0"
        and document["harness_id"] == "DELIVERY_HARNESS_V1"
        and document["mode"] in {"BOUND_PROJECT", "PORTABLE_PROJECT"}
        and isinstance(document["profile_id"], str)
        and re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,127}", document["profile_id"])
    ):
        raise ValueError("PORTABLE_PROFILE_INVALID")
    repository = document["repository"]
    if not isinstance(repository, dict) or set(repository) != {"name", "default_branch"}:
        raise ValueError("PORTABLE_PROFILE_INVALID")
    if not (
        isinstance(repository["name"], str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository["name"])
        and isinstance(repository["default_branch"], str)
        and re.fullmatch(r"[A-Za-z0-9._/-]+", repository["default_branch"])
    ):
        raise ValueError("PORTABLE_PROFILE_INVALID")
    bindings = document["bindings"]
    if not isinstance(bindings, dict) or set(bindings) != {
        "catalog_manifest", "owner_attention_policy", "context_map",
        "domain_policy", "historical_cloud_bundle_registry",
    }:
        raise ValueError("PORTABLE_PROFILE_INVALID")
    if not all(
        bindings[key] is None or isinstance(bindings[key], str)
        for key in {"catalog_manifest", "domain_policy", "historical_cloud_bundle_registry"}
    ) or not all(
        isinstance(bindings[key], str) and bool(bindings[key])
        for key in {"owner_attention_policy", "context_map"}
    ):
        raise ValueError("PORTABLE_PROFILE_INVALID")
    if document["working_memory"] != {
        "truth_owner": "GIT",
        "task_resolution": "EXACT_TASK_CONTRACT",
        "cloud_bundle": "OWNER_MANAGED_OPTIONAL_EXPORT",
    } or document["context_budgets"] != {
        "agents_max_bytes": 12288,
        "cursor_always_apply_max_bytes": 6144,
        "ordinary_receipt_max_bytes": 49152,
        "auto_inline_file_max_bytes": 102400,
    }:
        raise ValueError("PORTABLE_PROFILE_INVALID")
    validation = document["validation"]
    if not isinstance(validation, dict) or set(validation) != {
        "github_ci_bound", "primary", "fallback", "credential_scan"
    } or type(validation["github_ci_bound"]) is not bool:
        raise ValueError("PORTABLE_PROFILE_INVALID")

    def command_ok(value: Any, *, result_owner: bool) -> bool:
        if value is None:
            return True
        keys = {"argv", "trusted_paths"} | ({"result_owner"} if result_owner else set())
        return (
            isinstance(value, dict)
            and set(value) == keys
            and isinstance(value.get("argv"), list)
            and bool(value["argv"])
            and all(isinstance(item, str) and bool(item) for item in value["argv"])
            and isinstance(value.get("trusted_paths"), list)
            and bool(value["trusted_paths"])
            and all(isinstance(item, str) and bool(item) for item in value["trusted_paths"])
            and (
                not result_owner
                or value.get("result_owner") in {"FOCUSED_PLUS_EXACT_PR_CI", "FULL_EXACT_HEAD"}
            )
        )

    if not (
        command_ok(validation["primary"], result_owner=True)
        and command_ok(validation["fallback"], result_owner=True)
        and command_ok(validation["credential_scan"], result_owner=False)
    ):
        raise ValueError("PORTABLE_PROFILE_INVALID")
    authority = document["authority"]
    if not isinstance(authority, dict) or set(authority) != {
        "external_system", "signing_or_financial_action", "cash_spend",
        "cloud_export_mutation",
    } or any(value is not False for value in authority.values()):
        raise ValueError("PORTABLE_PROFILE_INVALID")
    return document


def load_portable_bundle_manifest(template_root: Path) -> list[dict[str, str]]:
    manifest_path = resolve_bounded(
        template_root, PORTABLE_MANIFEST_PATH, code="PORTABLE_MANIFEST_PATH_INVALID"
    )
    try:
        manifest = load_json_unique(
            manifest_path.read_text(encoding="utf-8"), code="PORTABLE_MANIFEST_INVALID"
        )
    except (OSError, UnicodeDecodeError):
        raise ValueError("PORTABLE_MANIFEST_INVALID") from None
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema", "schema_version", "harness_id", "files"
    } or not (
        manifest["schema"] == "delivery-harness.portable-bundle-manifest"
        and manifest["schema_version"] == "1.0"
        and manifest["harness_id"] == "DELIVERY_HARNESS_V1"
        and isinstance(manifest["files"], list)
        and bool(manifest["files"])
    ):
        raise ValueError("PORTABLE_MANIFEST_INVALID")
    records: list[dict[str, str]] = []
    sources: set[str] = set()
    destinations: set[str] = set()
    for item in manifest["files"]:
        if not isinstance(item, dict) or set(item) != {"source", "destination", "sha256"}:
            raise ValueError("PORTABLE_MANIFEST_INVALID")
        source = safe_relative_path(item["source"], code="PORTABLE_MANIFEST_INVALID")
        destination = safe_relative_path(item["destination"], code="PORTABLE_MANIFEST_INVALID")
        digest = item["sha256"]
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("PORTABLE_MANIFEST_INVALID")
        if source in sources or destination in destinations:
            raise ValueError("PORTABLE_MANIFEST_INVALID")
        source_path = resolve_bounded(
            template_root, source, code="PORTABLE_MANIFEST_INVALID"
        )
        if not source_path.is_file() or sha256_file(source_path) != digest:
            raise ValueError("PORTABLE_TEMPLATE_HASH_MISMATCH")
        sources.add(source)
        destinations.add(destination)
        records.append({"source": source, "destination": destination, "sha256": digest})
    return records


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
    branch = git_text(root, "branch", "--show-current")
    github_head_ref = os.environ.get("GITHUB_HEAD_REF", "")
    if not branch and os.environ.get("GITHUB_ACTIONS") == "true" and re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}", github_head_ref
    ):
        branch = github_head_ref
    branch = branch or "DETACHED"
    dirty = bool(git_text(root, "status", "--porcelain=v1"))
    if not re.fullmatch(r"[0-9a-f]{40}", head) or not re.fullmatch(
        r"[0-9a-f]{40}", tree
    ):
        raise ValueError("GIT_IDENTITY_UNKNOWN")
    return {"head": head, "tree": tree, "branch": branch, "dirty": dirty}


def github_repository_from_origin(value: str) -> str:
    patterns = (
        r"git@github\.com:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$",
        r"ssh://git@github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
        r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, value)
        if match is not None:
            return match.group(1)
    raise ValueError("TASK_REPOSITORY_ORIGIN_MISMATCH")


def validate_repository_origin(root: Path, expected_repository: str) -> None:
    origin = git_text(root, "remote", "get-url", "origin")
    if github_repository_from_origin(origin) != expected_repository:
        raise ValueError("TASK_REPOSITORY_ORIGIN_MISMATCH")


def validate_task_git_binding(root: Path, metadata: dict[str, Any], identity: dict[str, Any]) -> None:
    binding = metadata["git_binding"]
    expected_base = binding["expected_base"]
    expected_upstream = binding["expected_upstream"]
    if git_text(root, "merge-base", "HEAD", expected_upstream) != expected_base:
        raise ValueError("TASK_EXPECTED_BASE_MISMATCH")
    if git_text(root, "rev-parse", expected_upstream) != binding["expected_upstream_oid"]:
        raise ValueError("TASK_UPSTREAM_OID_MISMATCH")
    if identity["branch"] != binding["expected_branch"]:
        raise ValueError("TASK_BRANCH_MISMATCH")
    if identity["dirty"] is True and binding["dirty_mode"] == "FORBIDDEN":
        raise ValueError("TASK_DIRTY_STATE_FORBIDDEN")


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
    if normalized.startswith("docs/project_sources/") and not (
        semantic_role == "HISTORICAL_CONTEXT" and lane == "L3"
    ):
        raise ValueError("SOURCE_HISTORY_ROLE_MISMATCH")
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


def parse_task_contract(root: Path, relative: str, task_id: str) -> dict[str, Any]:
    path = resolve_bounded(root, relative, code="TASK_CONTRACT_UNSAFE_PATH")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("TASK_CONTRACT_NOT_FOUND") from exc
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if match is None:
        raise ValueError("TASK_CONTRACT_SCHEMA_INVALID")
    try:
        metadata = load_yaml_unique(match.group(1))
        schema = json.loads((root / TASK_CONTRACT_SCHEMA).read_text(encoding="utf-8"))
        jsonschema.validate(metadata, schema)
    except (OSError, json.JSONDecodeError, YAML_ERROR, JSONSCHEMA_VALIDATION_ERROR):
        raise ValueError("TASK_CONTRACT_SCHEMA_INVALID") from None
    if not isinstance(metadata, dict):
        raise ValueError("TASK_CONTRACT_SCHEMA_INVALID")
    if metadata["task_id"] != task_id:
        raise ValueError("TASK_ID_CONTRACT_MISMATCH")
    return metadata


def load_catalog_records(root: Path, manifest_relative: str | None) -> dict[str, dict[str, Any]]:
    if manifest_relative is None:
        return {}
    manifest = load_mapping(resolve_bounded(root, manifest_relative, code="CATALOG_MANIFEST_PATH_INVALID"))
    registries = manifest.get("root_resolver", {}).get("asset_registries", [])
    if not isinstance(registries, list):
        raise ValueError("CATALOG_QUERY_FAILED")
    records: dict[str, dict[str, Any]] = {}
    for registry in registries:
        if not isinstance(registry, str):
            raise ValueError("CATALOG_QUERY_FAILED")
        document = load_mapping(resolve_bounded(root, registry, code="CATALOG_REGISTRY_PATH_INVALID"))
        for record in document.get("records", []):
            if isinstance(record, dict) and isinstance(record.get("asset_id"), str):
                records[record["asset_id"]] = record
    return records


def catalog_relation_references(
    root: Path,
    records: dict[str, dict[str, Any]],
    asset_ids: list[str],
    *,
    max_inline_bytes: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for asset_id in sorted(asset_ids):
        record = records.get(asset_id)
        location = record.get("location") if isinstance(record, dict) else None
        relative = location.get("repository_path") if isinstance(location, dict) else None
        if not isinstance(relative, str):
            gaps.append({"semantic_role": "STABLE_ASSETS_AND_RELATIONS", "lane": "L1", "truth_owner": "CATALOG", "state": "EXPLICIT_GAP", "reason_code": "CATALOG_ASSET_NOT_RESOLVED"})
            continue
        selected.append(reference_for_path(root, relative, semantic_role="STABLE_ASSETS_AND_RELATIONS", lane="L1", truth_owner="CATALOG", stable_id=asset_id, max_inline_bytes=max_inline_bytes))
    return selected, gaps


def resolve_required_context(
    root: Path,
    task_metadata: dict[str, Any],
    context_map: dict[str, Any],
    *,
    max_inline_bytes: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    role_by_id = {role["semantic_role"]: role for role in context_map["roles"]}
    requirements = task_metadata["context_requirements"]
    required = set(requirements["l2_roles"]) | set(requirements["l3_roles"])
    paths_by_role = requirements["exact_role_paths"]
    for role_id in (
        "LIFECYCLE",
        "EXTERNAL_ROUTE_KNOWLEDGE",
        "ARCHITECTURE_DECISIONS",
        "DELIVERY_EVIDENCE",
        "HISTORICAL_CONTEXT",
    ):
        role = role_by_id[role_id]
        if role_id not in required:
            gaps.append(explicit_gap(role, "DEFERRED_ON_DEMAND"))
            continue
        paths = paths_by_role[role_id]
        if not paths:
            raise ValueError(f"REQUIRED_CONTEXT_REFERENCE_NOT_BOUND:{role_id}")
        for relative in paths:
            selected.append(
                reference_for_path(
                    root,
                    relative,
                    semantic_role=role_id,
                    lane=role["lane"],
                    truth_owner=role["truth_owner"],
                    stable_id=None,
                    max_inline_bytes=max_inline_bytes,
                )
            )
    return selected, gaps


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
    task_metadata = parse_task_contract(root, contract_relative, task_id)

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
    if profile["repository"]["name"] != task_metadata["expected_repository"]:
        raise ValueError("TASK_REPOSITORY_MISMATCH")
    validate_repository_origin(root, task_metadata["expected_repository"])
    if route not in task_metadata["allowed_routes"]:
        raise ValueError("TASK_ROUTE_NOT_ALLOWED")
    context_map = load_closed_document(
        root / profile["bindings"]["context_map"],
        root / "catalog/schemas/delivery_harness_context_map.schema.json",
    )
    validate_context_role_set(context_map)
    budgets = profile["context_budgets"]
    max_inline = budgets["auto_inline_file_max_bytes"]
    identity = git_identity(root)
    validate_task_git_binding(root, task_metadata, identity)
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

    roadmap = task_metadata["context_requirements"]["roadmap_path"]
    if roadmap is None:
        gaps.append(explicit_gap(role_by_id["PRODUCT_ROADMAP"], "NO_EXACT_GIT_ROADMAP_BOUND"))
    else:
        selected.append(reference_for_path(root, roadmap, semantic_role="PRODUCT_ROADMAP", lane="L1", truth_owner="EXACT_GIT_ROADMAP_BINDING", stable_id=None, max_inline_bytes=max_inline))
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
    records = load_catalog_records(root, profile["bindings"]["catalog_manifest"])
    catalog_selected, catalog_gaps = catalog_relation_references(root, records, task_metadata["context_requirements"]["catalog_asset_ids"], max_inline_bytes=max_inline)
    if catalog_gaps:
        raise ValueError("REQUIRED_CATALOG_ASSET_NOT_RESOLVED")
    selected.extend(catalog_selected)
    required_selected, required_gaps = resolve_required_context(
        root, task_metadata, context_map, max_inline_bytes=max_inline
    )
    selected.extend(required_selected)
    gaps.extend(required_gaps)

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


def build_live_pr_head_receipt(
    root: Path,
    *,
    pr_number: int,
    route: str,
    profile_path: str = PROFILE_PATH,
) -> dict[str, Any]:
    root = root.resolve()
    if type(pr_number) is not int or pr_number < 1:
        raise ValueError("PR_NUMBER_INVALID")
    harness = load_closed_document(
        root / HARNESS_PATH,
        root / "catalog/schemas/delivery_harness.schema.json",
    )
    if route not in harness["active_routes"]:
        raise ValueError("ACTIVE_ROUTE_UNKNOWN")
    merge_policy = harness["merge_policy"]
    if "LIVE_PR_HEAD" not in merge_policy["identity_modes"]:
        raise ValueError("LIVE_PR_HEAD_NOT_ENABLED")
    profile_relative = safe_relative_path(profile_path)
    profile = load_closed_document(
        root / profile_relative,
        root / "catalog/schemas/delivery_harness_project_profile.schema.json",
    )
    validate_repository_origin(root, profile["repository"]["name"])
    context_map = load_closed_document(
        root / profile["bindings"]["context_map"],
        root / "catalog/schemas/delivery_harness_context_map.schema.json",
    )
    validate_context_role_set(context_map)
    budgets = profile["context_budgets"]
    max_inline = budgets["auto_inline_file_max_bytes"]
    identity = git_identity(root)
    role_by_id = {role["semantic_role"]: role for role in context_map["roles"]}
    selected: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
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
    gaps.append(explicit_gap(role_by_id["PRODUCT_ROADMAP"], "NO_EXACT_GIT_ROADMAP_BOUND"))
    control_payload = {
        "pr_number": pr_number,
        "identity_mode": "LIVE_PR_HEAD",
        "head": identity["head"],
    }
    selected.append(
        metadata_reference(
            semantic_role="ACTIVE_BOUNDED_WORK",
            lane="L1",
            truth_owner="LIVE_PR_HEAD",
            path=f"github/pull/{pr_number}",
            stable_id="CONTROL-PR",
            payload=control_payload,
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
    for role_id in (
        "LIFECYCLE",
        "EXTERNAL_ROUTE_KNOWLEDGE",
        "ARCHITECTURE_DECISIONS",
        "DELIVERY_EVIDENCE",
        "HISTORICAL_CONTEXT",
    ):
        gaps.append(explicit_gap(role_by_id[role_id], "DEFERRED_ON_DEMAND"))
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
        "control_pr": {"pr_number": pr_number, "identity_mode": "LIVE_PR_HEAD"},
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
    except (OSError, json.JSONDecodeError, JSONSCHEMA_VALIDATION_ERROR):
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
    control_pr = receipt.get("control_pr")
    if isinstance(control_pr, dict) and control_pr.get("identity_mode") == "LIVE_PR_HEAD":
        label = f"control-pr-{control_pr['pr_number']}"
    else:
        task_id = receipt["task"]["task_id"]
        if not SAFE_TASK_ID.fullmatch(task_id):
            raise ValueError("TASK_ID_INVALID")
        label = task_id.lower()
    directory = root.resolve() / "local/delivery_harness/context"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{label}-{receipt['receipt_sha256'][:12]}.json"
    path.write_bytes(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
    return path


def validate_route_continuity(
    prior_receipt: dict[str, Any], requested_route: str
) -> list[str]:
    if not isinstance(prior_receipt, dict):
        return ["PRIOR_CONTEXT_RECEIPT_INVALID"]
    prior_route = prior_receipt.get("route")
    if not isinstance(prior_route, str):
        return ["PRIOR_CONTEXT_RECEIPT_INVALID"]
    if prior_route != requested_route:
        return ["ACTIVE_ROUTE_CHANGED"]
    return []


def detect_multi_root_context_duplication(roots: list[Path]) -> list[str]:
    resolved: list[Path] = []
    for root in roots:
        if not isinstance(root, Path):
            return ["WORKSPACE_ROOTS_INVALID"]
        resolved.append(root.resolve())
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            if left in right.parents or right in left.parents:
                return ["MULTI_ROOT_CONTEXT_DUPLICATION_WARNING"]
    return []


def cursor_rule_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if match is None:
        raise ValueError("CURSOR_RULE_FRONTMATTER_INVALID")
    value = load_yaml_unique(match.group(1))
    if not isinstance(value, dict) or set(value) != {
        "description",
        "globs",
        "alwaysApply",
    }:
        raise ValueError("CURSOR_RULE_FRONTMATTER_INVALID")
    if not isinstance(value["description"], str):
        raise ValueError("CURSOR_RULE_FRONTMATTER_INVALID")
    if not isinstance(value["globs"], list) or any(
        not isinstance(item, str) for item in value["globs"]
    ):
        raise ValueError("CURSOR_RULE_FRONTMATTER_INVALID")
    if type(value["alwaysApply"]) is not bool:
        raise ValueError("CURSOR_RULE_FRONTMATTER_INVALID")
    return value


def check_harness(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    profile: dict[str, Any] | None = None
    delivery_gate_ready = False
    documents = (
        (HARNESS_PATH, "catalog/schemas/delivery_harness.schema.json"),
        (PROFILE_PATH, "catalog/schemas/delivery_harness_project_profile.schema.json"),
        (CONTEXT_MAP_PATH, "catalog/schemas/delivery_harness_context_map.schema.json"),
        (RADAR_PATH, "catalog/schemas/delivery_harness_capability_radar.schema.json"),
        (
            "control/owner_attention_gate_v2.yaml",
            "catalog/schemas/owner_attention_gate_v2.schema.json",
        ),
    )
    for document, schema in documents:
        try:
            loaded = load_closed_document(root / document, root / schema)
            if document == PROFILE_PATH:
                profile = loaded
            elif document == CONTEXT_MAP_PATH:
                validate_context_role_set(loaded)
        except (OSError, ValueError, JSONSCHEMA_VALIDATION_ERROR):
            errors.append(f"CONTRACT_INVALID:{document}")
    if profile is not None:
        validation = profile["validation"]
        delivery_gate_ready = (
            validation["github_ci_bound"] is True
            and
            (validation["primary"] is not None or validation["fallback"] is not None)
            and validation["credential_scan"] is not None
        )
        try:
            validate_repository_origin(root, profile["repository"]["name"])
        except ValueError:
            errors.append("REPOSITORY_IDENTITY_DIVERGENCE")
    active_baton_paths = [
        ".cursor/rules/50-github-baton.mdc",
        ".cursor/commands/baton-preflight.md",
    ]
    if any((root / path).exists() for path in active_baton_paths):
        errors.append("ACTIVE_ADAPTER_MIGRATION_PENDING")
    required_active_paths = [
        "AGENTS.md",
        ".agents/skills/delivery-harness/SKILL.md",
        ".cursor/commands/delivery-start.md",
        ".cursor/commands/delivery-status.md",
        ".cursor/commands/delivery-review.md",
        ".cursor/commands/delivery-finish.md",
    ]
    if any(not (root / path).is_file() for path in required_active_paths):
        errors.append("ACTIVE_ADAPTER_MISSING")
    if profile is not None and profile.get("mode") == "BOUND_PROJECT":
        historical_paths = [
            "scripts/baton_preflight.py",
            "scripts/baton_receipt.py",
            "tests/test_baton_contract.py",
            "docs/agent/GITHUB_BATON_PROTOCOL.md",
        ]
        if any(not (root / path).is_file() for path in historical_paths):
            errors.append("HISTORICAL_BATON_MISSING")
    active_adapter_roots = (
        root / ".cursor/rules",
        root / ".cursor/commands",
        root / ".cursor/agents",
        root / ".agents/skills/delivery-harness",
    )
    active_baton_patterns = (
        re.compile(r"GITHUB_BATON\s+as\s+an\s+active", re.IGNORECASE),
        re.compile(r"route\s*[:=]\s*GITHUB_BATON", re.IGNORECASE),
        re.compile(r"use\s+GITHUB_BATON", re.IGNORECASE),
        re.compile(
            r"\bbaton[_-](?:preflight|receipt|contract|scope)\b",
            re.IGNORECASE,
        ),
    )
    active_adapter_files = [root / "AGENTS.md"]
    for adapter_root in active_adapter_roots:
        if not adapter_root.is_dir():
            continue
        active_adapter_files.extend(
            path for path in adapter_root.rglob("*") if path.is_file()
        )
    for path in active_adapter_files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            errors.append("ACTIVE_ADAPTER_INVALID")
            continue
        if any(pattern.search(text) for pattern in active_baton_patterns):
            errors.append("ACTIVE_BATON_REFERENCE")
    try:
        agents_bytes = (root / "AGENTS.md").stat().st_size
        if agents_bytes > 12 * 1024:
            errors.append("AGENTS_CONTEXT_BUDGET_EXCEEDED")
        always_bytes = 0
        for path in sorted((root / ".cursor/rules").glob("*.mdc")):
            metadata = cursor_rule_frontmatter(path)
            if metadata["alwaysApply"] is True:
                always_bytes += path.stat().st_size
        if always_bytes > 6 * 1024:
            errors.append("CURSOR_ALWAYS_CONTEXT_BUDGET_EXCEEDED")
    except (OSError, ValueError, YAML_ERROR):
        errors.append("ACTIVE_ADAPTER_INVALID")
    return {
        "schema": "smial.delivery-harness-check",
        "schema_version": "1.0",
        "harness_id": "DELIVERY_HARNESS_V1",
        "status": "PASS" if not errors else "PENDING",
        "delivery_gate_ready": delivery_gate_ready,
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


def portable_template_bytes(
    source_relative: str,
    destination: str,
    template_root: Path,
    *,
    repository: str,
    default_branch: str,
) -> bytes:
    source = resolve_bounded(
        template_root, source_relative, code="PORTABLE_TEMPLATE_PATH_INVALID"
    )
    value = source.read_bytes()
    if destination == "delivery-harness/project-profile.yaml":
        document = load_json_unique(
            value.decode("utf-8", errors="strict"), code="PORTABLE_PROFILE_INVALID"
        )
        if not isinstance(document, dict) or not isinstance(
            document.get("repository"), dict
        ):
            raise ValueError("PORTABLE_PROFILE_INVALID")
        document["repository"]["name"] = repository
        document["repository"]["default_branch"] = default_branch
        value = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
    elif destination == "control/owner_attention_gate_v2.yaml":
        document = load_json_unique(
            value.decode("utf-8", errors="strict"), code="PORTABLE_POLICY_INVALID"
        )
        if not isinstance(document, dict):
            raise ValueError("PORTABLE_POLICY_INVALID")
        document["repository"] = repository
        value = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
    elif destination == RADAR_PATH:
        document = load_json_unique(
            value.decode("utf-8", errors="strict"), code="PORTABLE_RADAR_INVALID"
        )
        if not isinstance(document, dict):
            raise ValueError("PORTABLE_RADAR_INVALID")
        value = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
    elif destination == "delivery-harness/bootstrap-prompt.md":
        value = re.sub(
            rb"(?m)^Repository: .+$",
            f"Repository: https://github.com/{repository}".encode("utf-8"),
            value,
        )
        value = value.replace(
            b"`main`", f"`{default_branch}`".encode("utf-8")
        )
    return value


def is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


def destination_ancestor_conflict(target: Path, destination: str) -> bool:
    normalized = safe_relative_path(destination, code="INITIALIZATION_PATH_INVALID")
    current = target.resolve()
    for part in PurePosixPath(normalized).parts[:-1]:
        current = current / part
        if current.is_symlink() or is_reparse_point(current):
            return True
        if current.exists() and not current.is_dir():
            return True
    return False


def target_state(target: Path, destination: str) -> dict[str, Any]:
    normalized = safe_relative_path(destination, code="INITIALIZATION_PATH_INVALID")
    lexical = target.resolve() / normalized
    if destination_ancestor_conflict(target, destination):
        return {"state": "CONFLICT", "sha256": None}
    if lexical.is_symlink() or is_reparse_point(lexical):
        return {"state": "CONFLICT", "sha256": None}
    path = resolve_bounded(target, destination, code="INITIALIZATION_PATH_INVALID")
    if not path.exists():
        return {"state": "MISSING", "sha256": None}
    if not path.is_file() or path.is_symlink():
        return {"state": "CONFLICT", "sha256": None}
    return {"state": "FILE", "sha256": sha256_file(path)}


def has_reparse_boundary(target: Path) -> bool:
    lexical = target.absolute()
    for candidate in (lexical, *lexical.parents):
        if candidate.is_symlink() or is_reparse_point(candidate):
            return True
    return False


def validate_initialization_target(target: Path) -> Path:
    forbidden = {".cursor", ".codex", ".agents"}
    if any(part.casefold() in forbidden for part in target.parts):
        raise ValueError("GLOBAL_CONFIG_TARGET_FORBIDDEN")
    if has_reparse_boundary(target):
        raise ValueError("INITIALIZATION_REPARSE_TARGET_FORBIDDEN")
    resolved = target.resolve()
    if resolved == Path.home().resolve():
        raise ValueError("GLOBAL_CONFIG_TARGET_FORBIDDEN")
    if not resolved.is_dir():
        raise ValueError("INITIALIZATION_TARGET_DIRECTORY_REQUIRED")
    if not (resolved / ".git").exists():
        raise ValueError("INITIALIZATION_REPOSITORY_ROOT_REQUIRED")
    try:
        toplevel = Path(
            git_text(resolved, "rev-parse", "--show-toplevel")
        ).resolve()
    except (OSError, ValueError):
        raise ValueError("INITIALIZATION_REPOSITORY_ROOT_REQUIRED") from None
    if toplevel != resolved:
        raise ValueError("INITIALIZATION_REPOSITORY_ROOT_REQUIRED")
    return resolved


def validate_initialization_repository(
    target: Path, repository: str | None
) -> str:
    try:
        origin = git_text(target, "remote", "get-url", "origin")
        origin_repository = github_repository_from_origin(origin)
    except ValueError:
        raise ValueError("INITIALIZATION_REPOSITORY_REQUIRED") from None
    if repository is None:
        repository = origin_repository
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None:
        raise ValueError("INITIALIZATION_REPOSITORY_INVALID")
    if origin_repository != repository:
        raise ValueError("INITIALIZATION_REPOSITORY_MISMATCH")
    return repository


def validate_initialization_default_branch(
    target: Path, default_branch: str | None
) -> str:
    discovered: str | None = None
    try:
        remote_head = git_text(
            target, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"
        )
        if remote_head.startswith("origin/"):
            discovered = remote_head.removeprefix("origin/")
    except ValueError:
        pass
    branch = default_branch if default_branch is not None else discovered
    if not isinstance(branch, str) or not (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", branch)
        and ".." not in branch
        and "//" not in branch
        and not branch.endswith(("/", "."))
    ):
        raise ValueError("INITIALIZATION_DEFAULT_BRANCH_REQUIRED")
    if discovered is not None and branch != discovered:
        raise ValueError("INITIALIZATION_DEFAULT_BRANCH_MISMATCH")
    return branch


def initialization_plan_hash(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("plan_sha256", None)
    return sha256_bytes(canonical_json_bytes(unsigned))


def target_fingerprint(target: Path) -> str:
    return sha256_bytes(str(target.resolve()).casefold().encode("utf-8"))


def plan_initialization(
    target: Path,
    template_root: Path,
    *,
    repository: str | None = None,
    default_branch: str | None = None,
    profile_path: str = "delivery-harness/templates/portable-project-profile.yaml",
) -> dict[str, Any]:
    target = validate_initialization_target(target)
    repository = validate_initialization_repository(target, repository)
    default_branch = validate_initialization_default_branch(target, default_branch)
    template_root = template_root.resolve()
    profile_relative = safe_relative_path(profile_path, code="PORTABLE_PROFILE_PATH_INVALID")
    profile_source = resolve_bounded(template_root, profile_relative, code="PORTABLE_PROFILE_PATH_INVALID")
    if not profile_source.is_file():
        raise ValueError("PORTABLE_PROFILE_NOT_FOUND")
    try:
        profile_document = load_json_unique(
            profile_source.read_text(encoding="utf-8"), code="PORTABLE_PROFILE_INVALID"
        )
        validate_portable_profile_for_init(profile_document)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("PORTABLE_PROFILE_INVALID") from exc
    manifest_records = load_portable_bundle_manifest(template_root)
    profile_records = [
        item for item in manifest_records
        if item["destination"] == "delivery-harness/project-profile.yaml"
    ]
    if len(profile_records) != 1 or profile_records[0]["source"] != profile_relative:
        raise ValueError("PORTABLE_PROFILE_NOT_IN_MANIFEST")
    files: list[dict[str, Any]] = []
    creates: list[str] = []
    conflicts: list[str] = []
    for record in sorted(manifest_records, key=lambda item: item["destination"]):
        source = record["source"]
        destination = record["destination"]
        payload = portable_template_bytes(
            source,
            destination,
            template_root,
            repository=repository,
            default_branch=default_branch,
        )
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
        "target_fingerprint": target_fingerprint(target),
        "repository": repository,
        "default_branch": default_branch,
        "profile_sha256": sha256_file(profile_source),
        "files": files,
    }
    plan["plan_sha256"] = initialization_plan_hash(plan)
    return plan


def apply_initialization(target: Path, plan: dict[str, Any]) -> dict[str, Any]:
    target = validate_initialization_target(target)
    validate_initialization_repository(target, plan.get("repository"))
    validate_initialization_default_branch(target, plan.get("default_branch"))
    if plan.get("target_fingerprint") != target_fingerprint(target):
        raise ValueError("INITIALIZATION_TARGET_MISMATCH")
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
    context.add_argument("--task-id")
    context.add_argument("--contract")
    context.add_argument("--pr", type=int)
    context.add_argument("--route", required=True)
    context.add_argument("--write-receipt", action="store_true")
    context.add_argument("--format", choices=("json",), default="json")
    radar = sub.add_parser("radar")
    radar.add_argument("--root", type=Path, default=ROOT)
    radar.add_argument("--events", required=True)
    radar.add_argument("--format", choices=("json",), default="json")
    init = sub.add_parser("init")
    init.add_argument("--target", type=Path, required=True)
    init.add_argument("--repository")
    init.add_argument("--default-branch")
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
        plan = plan_initialization(
            args.target,
            ROOT,
            repository=args.repository,
            default_branch=args.default_branch,
            profile_path=args.profile,
        )
        if args.preview:
            result = plan
        else:
            if args.plan_sha256 != plan["plan_sha256"]:
                raise ValueError("PLAN_FINGERPRINT_REQUIRED_OR_STALE")
            result = apply_initialization(args.target, plan)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("decision") not in {"CONFLICT_REFUSAL"} else 2
    if args.pr is not None:
        if args.task_id is not None or args.contract is not None:
            raise ValueError("CONTEXT_IDENTITY_MODE_CONFLICT")
        receipt = build_live_pr_head_receipt(
            args.root, pr_number=args.pr, route=args.route
        )
    else:
        if not args.task_id or not args.contract:
            raise ValueError("TASK_CONTRACT_EXACT_PATH_REQUIRED")
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
