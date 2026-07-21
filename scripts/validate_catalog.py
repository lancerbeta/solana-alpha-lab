#!/usr/bin/env python3
"""Validate the SMIAL Project Asset Catalog foundation."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "catalog/catalog_manifest.yaml"
MANIFEST_SCHEMA_PATH = ROOT / "catalog/schemas/catalog_manifest.schema.json"
ASSET_SCHEMA_PATH = ROOT / "catalog/schemas/asset_catalog.schema.json"
QUERY_SCHEMA_PATH = ROOT / "catalog/schemas/query_recipe.schema.json"


class CatalogValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CatalogSnapshot:
    manifest: dict[str, Any]
    assets_document: dict[str, Any]
    queries_document: dict[str, Any]
    assets: dict[str, dict[str, Any]]
    queries: dict[str, dict[str, Any]]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CatalogValidationError(f"yaml_root_not_object:{path.relative_to(ROOT)}")
    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CatalogValidationError(f"json_root_not_object:{path.relative_to(ROOT)}")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_safe_relative_path(value: str) -> bool:
    if not value or "\x00" in value:
        return False
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute():
        return False
    parts = value.replace("\\", "/").split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    return True


def resolve_repository_path(relative: str, root: Path = ROOT) -> Path:
    if not is_safe_relative_path(relative):
        raise CatalogValidationError(f"unsafe_relative_path:{relative}")
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise CatalogValidationError(f"path_escapes_repository:{relative}")
    return candidate


def format_schema_errors(validator: Draft202012Validator, instance: Any) -> list[str]:
    errors: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}:{error.message}")
    return errors


def validate_schema_instance(schema: dict[str, Any], instance: dict[str, Any], label: str) -> None:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = format_schema_errors(validator, instance)
    if errors:
        raise CatalogValidationError(f"schema_invalid:{label}:" + "|".join(errors))


def index_unique(records: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for record in records:
        identifier = str(record[key])
        if identifier in result:
            duplicates.append(identifier)
        result[identifier] = record
    if duplicates:
        raise CatalogValidationError(f"duplicate_{label}_ids:" + ",".join(sorted(set(duplicates))))
    return result


def validate_semantics(
    manifest: dict[str, Any],
    assets_document: dict[str, Any],
    queries_document: dict[str, Any],
    *,
    root: Path = ROOT,
) -> CatalogSnapshot:
    assets = index_unique(assets_document["records"], "asset_id", "asset")
    queries = index_unique(queries_document["recipes"], "recipe_id", "query")

    mandatory = set(manifest["mandatory_asset_ids"])
    missing_mandatory = mandatory - set(assets)
    if missing_mandatory:
        raise CatalogValidationError(
            "catalog_gap_missing_mandatory:" + ",".join(sorted(missing_mandatory))
        )

    all_registry_paths = (
        manifest["root_resolver"]["asset_registries"]
        + manifest["root_resolver"]["query_registries"]
        + manifest["root_resolver"]["schemas"]
    )
    for relative in all_registry_paths:
        path = resolve_repository_path(relative, root)
        if not path.is_file():
            raise CatalogValidationError(f"manifest_path_missing:{relative}")

    for asset_id, asset in assets.items():
        location = asset["location"]
        repository_path = location.get("repository_path")
        if repository_path is not None:
            path = resolve_repository_path(repository_path, root)
            if location["kind"] == "git_path" and not path.is_file():
                raise CatalogValidationError(f"asset_path_missing:{asset_id}:{repository_path}")

        integrity = asset["integrity"]
        if integrity["kind"] == "sha256":
            if repository_path is None:
                raise CatalogValidationError(f"sha256_without_repository_path:{asset_id}")
            observed = sha256(resolve_repository_path(repository_path, root))
            if observed != integrity["sha256"]:
                raise CatalogValidationError(f"sha256_mismatch:{asset_id}")

        if integrity["kind"] == "catalog_commit":
            if asset["status"] != "IMPLEMENTED_UNVERIFIED":
                raise CatalogValidationError(f"catalog_commit_status_invalid:{asset_id}")

        for relation in asset["relations"]:
            target = relation["target_asset_id"]
            if target not in assets:
                raise CatalogValidationError(f"broken_asset_relation:{asset_id}:{target}")

        recipe_id = asset["access"].get("recipe_id")
        if recipe_id is not None and recipe_id not in queries:
            raise CatalogValidationError(f"broken_access_recipe:{asset_id}:{recipe_id}")

        if asset["classification"]["contains_secrets"]:
            raise CatalogValidationError(f"secret_classification_forbidden:{asset_id}")
        if asset["classification"]["contains_raw_data"]:
            raise CatalogValidationError(f"raw_data_classification_forbidden:{asset_id}")

        if not asset["relations"] and not asset["consumers"] and asset_id != "CATALOG-ROOT-001":
            raise CatalogValidationError(f"orphan_asset:{asset_id}")

    placeholder_pattern = re.compile(r"\{([a-z][a-z0-9_]*)\}")
    for recipe_id, recipe in queries.items():
        if not recipe["read_only"] or not recipe["bounded"]:
            raise CatalogValidationError(f"query_not_readonly_bounded:{recipe_id}")
        if recipe["write_effects"] != "NONE":
            raise CatalogValidationError(f"query_write_effects:{recipe_id}")
        if recipe["network_required"]:
            raise CatalogValidationError(f"query_network_forbidden_foundation:{recipe_id}")

        for target in recipe["target_asset_ids"]:
            if target not in assets:
                raise CatalogValidationError(f"broken_query_target:{recipe_id}:{target}")

        parameters = {item["name"] for item in recipe["parameters"]}
        placeholders = set(placeholder_pattern.findall(" ".join(recipe["command"])))
        if placeholders != parameters:
            raise CatalogValidationError(
                f"query_parameter_mismatch:{recipe_id}:"
                f"placeholders={sorted(placeholders)}:parameters={sorted(parameters)}"
            )

    command_text = json.dumps(manifest["root_resolver"]["commands"], ensure_ascii=False)
    if ".." in command_text:
        raise CatalogValidationError("manifest_command_parent_traversal")

    return CatalogSnapshot(
        manifest=manifest,
        assets_document=assets_document,
        queries_document=queries_document,
        assets=assets,
        queries=queries,
    )


def load_and_validate(root: Path = ROOT) -> CatalogSnapshot:
    manifest_path = root / "catalog/catalog_manifest.yaml"
    manifest_schema_path = root / "catalog/schemas/catalog_manifest.schema.json"
    asset_schema_path = root / "catalog/schemas/asset_catalog.schema.json"
    query_schema_path = root / "catalog/schemas/query_recipe.schema.json"

    manifest = load_yaml(manifest_path)
    manifest_schema = load_json(manifest_schema_path)
    asset_schema = load_json(asset_schema_path)
    query_schema = load_json(query_schema_path)

    validate_schema_instance(manifest_schema, manifest, "manifest")

    asset_paths = manifest["root_resolver"]["asset_registries"]
    query_paths = manifest["root_resolver"]["query_registries"]
    if len(asset_paths) != 1 or len(query_paths) != 1:
        raise CatalogValidationError("foundation_requires_single_asset_and_query_registry")

    assets_document = load_yaml(resolve_repository_path(asset_paths[0], root))
    queries_document = load_yaml(resolve_repository_path(query_paths[0], root))

    validate_schema_instance(asset_schema, assets_document, "assets")
    validate_schema_instance(query_schema, queries_document, "queries")

    return validate_semantics(
        manifest,
        assets_document,
        queries_document,
        root=root,
    )


def main() -> int:
    print("=== TASK-03 ATOM 3A CATALOG VALIDATION ===")
    try:
        snapshot = load_and_validate()
    except Exception as exc:
        print("CATALOG_RESULT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR: {exc}")
        return 1

    print("manifest_schema: PASS")
    print("asset_schema: PASS")
    print("query_schema: PASS")
    print("path_policy: PASS")
    print("duplicate_ids: PASS")
    print("mandatory_assets: PASS")
    print("relations: PASS")
    print("integrity: PASS")
    print("query_readonly_bounded: PASS")
    print(f"asset_count: {len(snapshot.assets)}")
    print(f"query_count: {len(snapshot.queries)}")
    print("CATALOG_RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
