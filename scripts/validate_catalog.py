#!/usr/bin/env python3
"""Validate the SMIAL Project Asset Catalog and provenance contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class CatalogValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CatalogSnapshot:
    manifest: dict[str, Any]
    assets_documents: list[dict[str, Any]]
    queries_documents: list[dict[str, Any]]
    lifecycle_documents: list[dict[str, Any]]
    assets: dict[str, dict[str, Any]]
    queries: dict[str, dict[str, Any]]
    lifecycle_records: dict[str, dict[str, Any]]


def observed_catalog_checkpoint(snapshot: CatalogSnapshot) -> dict[str, int]:
    return {
        "assets": len(snapshot.assets),
        "asset_registries": len(snapshot.assets_documents),
        "schemas": len(snapshot.manifest["root_resolver"]["schemas"]),
        "queries": len(snapshot.queries),
        "lifecycle_registries": len(snapshot.lifecycle_documents),
        "lifecycle_records": len(snapshot.lifecycle_records),
    }


def validate_current_checkpoint(snapshot: CatalogSnapshot) -> None:
    expected = snapshot.manifest["current_checkpoint"]
    observed = observed_catalog_checkpoint(snapshot)
    if expected != observed:
        raise CatalogValidationError(
            "catalog_current_checkpoint_drift:"
            f"expected={json.dumps(expected, sort_keys=True)}:"
            f"observed={json.dumps(observed, sort_keys=True)}"
        )


EXPECTED_LIFECYCLE_REGISTRIES = {
    "registries/research_cycles.yaml": "research_cycles",
    "registries/hypotheses.yaml": "hypotheses",
    "registries/global_trial_ledger.yaml": "global_trial_ledger",
    "registries/feature_catalog.yaml": "feature_catalog",
    "registries/holdout_consumption.yaml": "holdout_consumption",
    "registries/strategies.yaml": "strategies",
    "registries/bot_instances.yaml": "bot_instances",
    "registries/reuse_candidates.yaml": "reuse_candidates",
    "registries/decisions_negative_results.yaml": "decisions_negative_results",
}


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
    return not any(part in {"", ".", ".."} for part in parts)


def resolve_repository_path(relative: str, root: Path = ROOT) -> Path:
    if not is_safe_relative_path(relative):
        raise CatalogValidationError(f"unsafe_relative_path:{relative}")
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise CatalogValidationError(f"path_escapes_repository:{relative}")
    return candidate


def validate_schema_instance(schema: dict[str, Any], instance: dict[str, Any], label: str) -> None:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}:{error.message}")
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


def parse_available(value: str) -> datetime:
    normalized = value
    if len(value) == 10:
        normalized = value + "T00:00:00+00:00"
    elif value.endswith("Z"):
        normalized = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CatalogValidationError(f"invalid_availability_timestamp:{value}") from exc


def validate_provenance(asset_id: str, asset: dict[str, Any], assets: dict[str, dict[str, Any]]) -> None:
    asset_type = asset["asset_type"]
    if asset_type not in {"pre_git_artifact", "external_bundle", "architecture_intent"}:
        return
    provenance = asset.get("provenance")
    if not isinstance(provenance, dict):
        raise CatalogValidationError(f"provenance_required:{asset_id}")
    if parse_available(provenance["first_reliable_available_at"]) < parse_available(provenance["created_at"]):
        raise CatalogValidationError(f"availability_before_creation:{asset_id}")

    if asset_type == "external_bundle":
        required = (
            asset["origin"] == "EXTERNAL"
            and asset["location"]["kind"] == "external_bundle"
            and provenance["import_mode"] == "BUNDLE_ONLY"
            and provenance["retention"] == "EXTERNAL_IMMUTABLE_BUNDLE"
            and provenance["canonicality"] == "EXTERNAL_BUNDLE"
            and provenance["past_availability_claim"] == "PRESERVED"
        )
        if not required:
            raise CatalogValidationError(f"external_bundle_provenance_invalid:{asset_id}")
        return

    if asset_type == "architecture_intent":
        status = asset["status"]
        implementation_statuses = {"IMPLEMENTED_UNVERIFIED", "VALIDATED_ACTIVE"}
        status_rank = {"IMPLEMENTED_UNVERIFIED": 1, "VALIDATED_ACTIVE": 2}
        evidence_targets = [
            assets[relation["target_asset_id"]]
            for relation in asset["relations"]
            if relation["relation_type"] == "evidenced_by"
            and relation["target_asset_id"] in assets
            and assets[relation["target_asset_id"]]["asset_type"] == "evidence"
        ]
        implementation_evidenced = status not in implementation_statuses or any(
            status_rank.get(evidence["status"], 0) >= status_rank[status]
            for evidence in evidence_targets
        )
        required = (
            asset["origin"] in {"PROJECT_SOURCE", "REPOSITORY"}
            and status in {"ACCEPTED_DIRECTION_NOT_IMPLEMENTED", *implementation_statuses}
            and implementation_evidenced
            and provenance["import_mode"] == "REGISTERED_CURRENT_INTENT"
            and provenance["canonicality"] == "CURRENT_INTENT"
            and provenance["past_availability_claim"] == "NO_PAST_AVAILABILITY_CLAIM"
            and "source_bundle_asset_id" not in provenance
        )
        if not required:
            raise CatalogValidationError(f"architecture_intent_provenance_invalid:{asset_id}")
        return

    if asset["origin"] != "PRE_GIT" or provenance["canonicality"] != "HISTORICAL_REFERENCE":
        raise CatalogValidationError(f"pre_git_origin_invalid:{asset_id}")
    if provenance["past_availability_claim"] != "PRESERVED":
        raise CatalogValidationError(f"pre_git_availability_not_preserved:{asset_id}")
    bundle_id = provenance.get("source_bundle_asset_id")
    bundle_sha = provenance.get("source_bundle_sha256")
    source_path = provenance.get("source_path")
    if not bundle_id or bundle_id not in assets:
        raise CatalogValidationError(f"pre_git_bundle_missing:{asset_id}")
    bundle = assets[bundle_id]
    if bundle["asset_type"] != "external_bundle" or bundle["integrity"].get("sha256") != bundle_sha:
        raise CatalogValidationError(f"pre_git_bundle_fingerprint_mismatch:{asset_id}")
    if not isinstance(source_path, str) or not is_safe_relative_path(source_path):
        raise CatalogValidationError(f"pre_git_source_path_invalid:{asset_id}")
    if parse_available(provenance["first_reliable_available_at"]) < parse_available(bundle["provenance"]["first_reliable_available_at"]):
        raise CatalogValidationError(f"pre_git_available_before_bundle:{asset_id}")
    if provenance["import_mode"] == "EXACT_BYTES":
        if asset["location"]["kind"] != "git_path" or provenance["retention"] != "TRACKED_REFERENCE":
            raise CatalogValidationError(f"pre_git_exact_mode_invalid:{asset_id}")
    elif provenance["import_mode"] == "BUNDLE_ONLY":
        if asset["location"]["kind"] != "logical_only" or provenance["retention"] != "BUNDLE_ONLY":
            raise CatalogValidationError(f"pre_git_bundle_only_mode_invalid:{asset_id}")
    else:
        raise CatalogValidationError(f"pre_git_import_mode_invalid:{asset_id}")


def validate_semantics(
    manifest: dict[str, Any],
    assets_documents: list[dict[str, Any]],
    queries_documents: list[dict[str, Any]],
    lifecycle_documents: list[dict[str, Any]],
    *,
    root: Path = ROOT,
    allow_generated_drift: bool = False,
) -> CatalogSnapshot:
    assets = index_unique(
        [record for document in assets_documents for record in document["records"]],
        "asset_id", "asset",
    )
    queries = index_unique(
        [record for document in queries_documents for record in document["recipes"]],
        "recipe_id", "query",
    )
    lifecycle_records = index_unique(
        [record for document in lifecycle_documents for record in document["records"]],
        "record_id", "lifecycle_record",
    )

    missing_mandatory = set(manifest["mandatory_asset_ids"]) - set(assets)
    if missing_mandatory:
        raise CatalogValidationError("catalog_gap_missing_mandatory:" + ",".join(sorted(missing_mandatory)))

    all_registry_paths = (
        manifest["root_resolver"]["asset_registries"]
        + manifest["root_resolver"]["query_registries"]
        + manifest["root_resolver"]["lifecycle_registries"]
        + manifest["root_resolver"]["schemas"]
    )
    for relative in all_registry_paths:
        if not resolve_repository_path(relative, root).is_file():
            raise CatalogValidationError(f"manifest_path_missing:{relative}")

    registry_paths = set(manifest["root_resolver"]["asset_registries"])
    registered_registry_paths = {
        record["location"].get("repository_path")
        for record in assets.values()
        if record["asset_type"] == "catalog_registry"
    }
    if not registry_paths.issubset(registered_registry_paths):
        raise CatalogValidationError("asset_registry_path_not_registered")

    lifecycle_paths = set(manifest["root_resolver"]["lifecycle_registries"])
    if lifecycle_paths != set(EXPECTED_LIFECYCLE_REGISTRIES):
        raise CatalogValidationError("lifecycle_registry_inventory_mismatch")
    observed_lifecycle_types = {
        path: document["registry_type"]
        for path, document in zip(
            manifest["root_resolver"]["lifecycle_registries"],
            lifecycle_documents,
            strict=True,
        )
    }
    if observed_lifecycle_types != EXPECTED_LIFECYCLE_REGISTRIES:
        raise CatalogValidationError("lifecycle_registry_type_mismatch")
    registered_lifecycle_paths = {
        record["location"].get("repository_path")
        for record in assets.values()
        if record["asset_type"] == "lifecycle_registry"
    }
    if registered_lifecycle_paths != lifecycle_paths:
        raise CatalogValidationError("lifecycle_registry_path_not_registered")

    for document in lifecycle_documents:
        registry_id = document["registry_id"]
        for source_asset_id in document["source_asset_ids"]:
            if source_asset_id not in assets:
                raise CatalogValidationError(
                    f"broken_lifecycle_source_asset:{registry_id}:{source_asset_id}"
                )
        for record in document["records"]:
            for evidence_asset_id in record["evidence_asset_ids"]:
                if evidence_asset_id not in assets:
                    raise CatalogValidationError(
                        f"broken_lifecycle_evidence_asset:{record['record_id']}:{evidence_asset_id}"
                    )

    for asset_id, asset in assets.items():
        location = asset["location"]
        repository_path = location.get("repository_path")
        if repository_path is not None:
            path = resolve_repository_path(repository_path, root)
            if location["kind"] == "git_path" and not path.is_file():
                if not (allow_generated_drift and asset["asset_type"] == "generated_view"):
                    raise CatalogValidationError(f"asset_path_missing:{asset_id}:{repository_path}")

        integrity = asset["integrity"]
        if integrity["kind"] == "sha256":
            if location["kind"] == "git_path":
                if repository_path is None:
                    raise CatalogValidationError(f"sha256_without_repository_path:{asset_id}")
                path = resolve_repository_path(repository_path, root)
                if path.is_file():
                    observed = sha256(path)
                else:
                    observed = None
                if observed != integrity["sha256"] and not (
                    allow_generated_drift and asset["asset_type"] == "generated_view"
                ):
                    raise CatalogValidationError(f"sha256_mismatch:{asset_id}")
            elif location["kind"] not in {"external_bundle", "logical_only"}:
                raise CatalogValidationError(f"external_sha256_location_invalid:{asset_id}")

        if integrity["kind"] == "catalog_commit" and asset["status"] not in {"IMPLEMENTED_UNVERIFIED", "VALIDATED_ACTIVE"}:
            raise CatalogValidationError(f"catalog_commit_status_invalid:{asset_id}")

        for relation in asset["relations"]:
            if relation["target_asset_id"] not in assets:
                raise CatalogValidationError(f"broken_asset_relation:{asset_id}:{relation['target_asset_id']}")

        recipe_id = asset["access"].get("recipe_id")
        if recipe_id is not None and recipe_id not in queries:
            raise CatalogValidationError(f"broken_access_recipe:{asset_id}:{recipe_id}")

        if asset["classification"]["contains_secrets"]:
            raise CatalogValidationError(f"secret_classification_forbidden:{asset_id}")
        if asset["classification"]["contains_raw_data"]:
            raise CatalogValidationError(f"raw_data_classification_forbidden:{asset_id}")

        validate_provenance(asset_id, asset, assets)

        if not asset["relations"] and not asset["consumers"] and asset_id != "CATALOG-ROOT-001":
            raise CatalogValidationError(f"orphan_asset:{asset_id}")

    placeholder_pattern = re.compile(r"\{([a-z][a-z0-9_]*)\}")
    for recipe_id, recipe in queries.items():
        if not recipe["read_only"] or not recipe["bounded"]:
            raise CatalogValidationError(f"query_not_readonly_bounded:{recipe_id}")
        if recipe["write_effects"] != "NONE":
            raise CatalogValidationError(f"query_write_effects:{recipe_id}")
        if recipe["network_required"]:
            raise CatalogValidationError(f"query_network_forbidden:{recipe_id}")
        for target in recipe["target_asset_ids"]:
            if target not in assets:
                raise CatalogValidationError(f"broken_query_target:{recipe_id}:{target}")
        parameters = {item["name"] for item in recipe["parameters"]}
        placeholders = set(placeholder_pattern.findall(" ".join(recipe["command"])))
        if placeholders != parameters:
            raise CatalogValidationError(
                f"query_parameter_mismatch:{recipe_id}:placeholders={sorted(placeholders)}:parameters={sorted(parameters)}"
            )

    if ".." in json.dumps(manifest["root_resolver"]["commands"], ensure_ascii=False):
        raise CatalogValidationError("manifest_command_parent_traversal")
    if "PRE_GIT_IMPORT" in manifest["deferred_capabilities"]:
        raise CatalogValidationError("pre_git_import_still_deferred")

    return CatalogSnapshot(
        manifest,
        assets_documents,
        queries_documents,
        lifecycle_documents,
        assets,
        queries,
        lifecycle_records,
    )


def load_and_validate(
    root: Path = ROOT,
    *,
    allow_generated_drift: bool = False,
) -> CatalogSnapshot:
    manifest = load_yaml(root / "catalog/catalog_manifest.yaml")
    manifest_schema = load_json(root / "catalog/schemas/catalog_manifest.schema.json")
    asset_schema = load_json(root / "catalog/schemas/asset_catalog.schema.json")
    query_schema = load_json(root / "catalog/schemas/query_recipe.schema.json")
    lifecycle_schema = load_json(
        root / "catalog/schemas/lifecycle_registry.schema.json"
    )

    validate_schema_instance(manifest_schema, manifest, "manifest")
    asset_documents = []
    for relative in manifest["root_resolver"]["asset_registries"]:
        document = load_yaml(resolve_repository_path(relative, root))
        validate_schema_instance(asset_schema, document, f"assets:{relative}")
        asset_documents.append(document)
    query_documents = []
    for relative in manifest["root_resolver"]["query_registries"]:
        document = load_yaml(resolve_repository_path(relative, root))
        validate_schema_instance(query_schema, document, f"queries:{relative}")
        query_documents.append(document)
    lifecycle_documents = []
    for relative in manifest["root_resolver"]["lifecycle_registries"]:
        document = load_yaml(resolve_repository_path(relative, root))
        validate_schema_instance(
            lifecycle_schema,
            document,
            f"lifecycle:{relative}",
        )
        lifecycle_documents.append(document)
    snapshot = validate_semantics(
        manifest,
        asset_documents,
        query_documents,
        lifecycle_documents,
        root=root,
        allow_generated_drift=allow_generated_drift,
    )
    validate_current_checkpoint(snapshot)
    return snapshot


def main() -> int:
    print("=== SMIAL CATALOG VALIDATION ===")
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
    print("lifecycle_schema: PASS")
    print("multi_registry_merge: PASS")
    print("path_policy: PASS")
    print("duplicate_ids: PASS")
    print("mandatory_assets: PASS")
    print("relations: PASS")
    print("integrity: PASS")
    print("provenance: PASS")
    print("first_reliable_available_at: PASS")
    print("query_readonly_bounded: PASS")
    print(f"asset_registry_count: {len(snapshot.assets_documents)}")
    print(f"asset_count: {len(snapshot.assets)}")
    print(f"query_count: {len(snapshot.queries)}")
    print(f"lifecycle_registry_count: {len(snapshot.lifecycle_documents)}")
    reuse_records = sum(
        len(document["records"])
        for document in snapshot.lifecycle_documents
        if document["registry_type"] == "reuse_candidates"
    )
    production_records = len(snapshot.lifecycle_records) - reuse_records
    print(f"reuse_decision_record_count: {reuse_records}")
    print(f"production_lifecycle_record_count: {production_records}")
    print(f"lifecycle_record_count: {len(snapshot.lifecycle_records)}")
    print("CATALOG_RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
