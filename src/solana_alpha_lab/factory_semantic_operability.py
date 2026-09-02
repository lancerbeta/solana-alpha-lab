"""Bounded semantic-operability routing over Catalog references only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from solana_alpha_lab.catalog_discovery import (
    CatalogDiscoveryError,
    INACTIVE_STATUSES,
    asset_path,
    normalize_query,
    normalize_text,
)

PROJECTION_RELATIVE = "configs/factory_semantic_operability_v1.yaml"
SCHEMA_RELATIVE = "catalog/schemas/factory_semantic_operability.schema.json"
MANIFEST_RELATIVE = "catalog/catalog_manifest.yaml"
DEFAULT_ROUTE_LIMIT = 5
MAX_ROUTE_LIMIT = 20
FORBIDDEN_CURRENT_ROOT_PREFIXES = (
    "docs/tasks/",
    "docs/evidence/",
    "docs/reports/",
    "docs/project_sources/",
)
IDENTITY_ROUTE_ID = 100000
EXACT_SEARCH_TERM = 7000
EXACT_PURPOSE = 6500
ALL_TOKENS_FIELDS = 5000
EXACT_PHRASE = 500
TOKEN_COVERAGE_SCALE = 1000
OWNER_QUESTION_HIT = 4000
ROUTE_EXISTS_NE_AUTHORIZED = "ROUTE_EXISTS != CALL_AUTHORIZED"
MAX_FORGE_SEMANTIC_BYTES = 3072
QUERY_STOPWORDS = frozenset(
    {
        "a",
        "am",
        "an",
        "and",
        "come",
        "comes",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "into",
        "is",
        "of",
        "or",
        "the",
        "this",
        "to",
        "what",
        "where",
    }
)

_RUNTIME_FABRICATION_TOKENS = frozenset(
    {
        "currently active",
        "currently healthy",
        "current activation sha",
        "current backup age",
        "activation sha",
        "backup age",
    }
)


class SemanticOperabilityError(CatalogDiscoveryError):
    """Typed semantic-route contract error."""


def load_semantic_projection(root: Path) -> dict[str, Any]:
    path = Path(root) / PROJECTION_RELATIVE
    if not path.is_file():
        raise SemanticOperabilityError("SEMANTIC_PROJECTION_MISSING")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SemanticOperabilityError("SEMANTIC_PROJECTION_INVALID") from exc
    if not isinstance(payload, dict):
        raise SemanticOperabilityError("SEMANTIC_PROJECTION_INVALID")
    schema_path = Path(root) / SCHEMA_RELATIVE
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)
    except (OSError, json.JSONDecodeError, Exception) as exc:
        # jsonschema.ValidationError and IO map to typed contract error for CLI.
        raise SemanticOperabilityError("SEMANTIC_PROJECTION_INVALID") from exc
    if payload.get("authority_granted") is not False:
        raise SemanticOperabilityError("SEMANTIC_AUTHORITY_MUST_BE_FALSE")
    return payload


def load_semantic_catalog_views(
    root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Load assets/bindings/queries for semantic routing without full Catalog validation."""

    root = Path(root)
    manifest = yaml.safe_load((root / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise SemanticOperabilityError("SEMANTIC_MANIFEST_INVALID")
    assets: dict[str, dict[str, Any]] = {}
    for relative in (manifest.get("root_resolver") or {}).get("asset_registries") or []:
        document = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        for record in (document or {}).get("records") or []:
            asset_id = record.get("asset_id")
            if isinstance(asset_id, str):
                assets[asset_id] = record
    queries: dict[str, Any] = {}
    for relative in (manifest.get("root_resolver") or {}).get("query_registries") or []:
        document = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        records = []
        if isinstance(document, dict):
            records = document.get("recipes") or document.get("records") or []
        elif isinstance(document, list):
            records = document
        for record in records:
            recipe_id = (record or {}).get("recipe_id")
            if isinstance(recipe_id, str):
                queries[recipe_id] = record
    bindings = manifest.get("canonical_bindings") or {}
    if not isinstance(bindings, dict):
        bindings = {}
    return assets, bindings, queries


def _route_index(projection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    for route in projection.get("routes") or []:
        route_id = str(route.get("semantic_route_id") or "")
        if not route_id:
            raise SemanticOperabilityError("SEMANTIC_ROUTE_ID_REQUIRED")
        if route_id in routes:
            raise SemanticOperabilityError("SEMANTIC_ROUTE_ID_DUPLICATE")
        routes[route_id] = route
    return routes


def _asset_integrity_sha(record: dict[str, Any]) -> str | None:
    integrity = record.get("integrity") or {}
    if integrity.get("kind") != "sha256":
        return None
    value = integrity.get("sha256")
    return str(value) if isinstance(value, str) and len(value) == 64 else None


def validate_semantic_projection(
    projection: dict[str, Any],
    *,
    assets: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
    queries: dict[str, Any],
) -> list[str]:
    """Return machine-readable violation codes; empty means PASS."""

    errors: list[str] = []
    if projection.get("authority_granted") is not False:
        errors.append("authority_granted_not_false")
    limits = projection.get("limits") or {}
    routes = list(projection.get("routes") or [])
    if len(routes) > int(limits.get("max_routes") or 12):
        errors.append("max_routes_exceeded")
    seen: set[str] = set()
    forge_count = 0
    for route in routes:
        route_id = str(route.get("semantic_route_id") or "")
        if route_id in seen:
            errors.append(f"duplicate_route:{route_id}")
        seen.add(route_id)
        if route.get("forge_visibility") == "INCLUDE":
            forge_count += 1
        for binding_id in route.get("root_binding_ids") or []:
            if binding_id not in bindings:
                errors.append(f"binding_unresolved:{route_id}:{binding_id}")
                continue
            target = bindings[binding_id].get("target_asset_id")
            if target not in assets:
                errors.append(f"binding_target_missing:{route_id}:{binding_id}:{target}")
                continue
            record = assets[str(target)]
            status = str(record.get("status") or "")
            if status in INACTIVE_STATUSES:
                errors.append(f"inactive_binding_root:{route_id}:{target}:{status}")
            path = asset_path(record)
            if any(path.startswith(prefix) for prefix in FORBIDDEN_CURRENT_ROOT_PREFIXES):
                errors.append(f"forbidden_current_root_path:{route_id}:{path}")
            if record.get("asset_type") == "architecture_intent":
                errors.append(f"arch_intent_as_implementation_root:{route_id}:{target}")
        for asset_id in list(route.get("root_asset_ids") or []) + list(
            (route.get("runtime_resolution") or {}).get("operator_asset_ids") or []
        ):
            if asset_id not in assets:
                errors.append(f"asset_unresolved:{route_id}:{asset_id}")
                continue
            record = assets[str(asset_id)]
            status = str(record.get("status") or "")
            if status in INACTIVE_STATUSES:
                errors.append(f"inactive_root_asset:{route_id}:{asset_id}:{status}")
            path = asset_path(record)
            if asset_id in (route.get("root_asset_ids") or []) and any(
                path.startswith(prefix) for prefix in FORBIDDEN_CURRENT_ROOT_PREFIXES
            ):
                errors.append(f"forbidden_current_root_path:{route_id}:{path}")
            if (
                asset_id in (route.get("root_asset_ids") or [])
                and record.get("asset_type") == "architecture_intent"
            ):
                errors.append(f"arch_intent_as_root_asset:{route_id}:{asset_id}")
        for recipe_id in route.get("query_recipe_ids") or []:
            if recipe_id not in queries:
                errors.append(f"query_unresolved:{route_id}:{recipe_id}")
        blob = " ".join(
            [
                str(route.get("purpose") or ""),
                " ".join(str(item) for item in route.get("owner_questions") or []),
                " ".join(str(item) for item in route.get("search_terms") or []),
            ]
        ).casefold()
        for token in _RUNTIME_FABRICATION_TOKENS:
            if token in blob:
                errors.append(f"runtime_state_cached_in_projection:{route_id}:{token}")
    route_ids = {str(item.get("semantic_route_id") or "") for item in routes}
    for route in routes:
        route_id = str(route.get("semantic_route_id") or "")
        for related in route.get("related_route_ids") or []:
            if related not in route_ids:
                errors.append(f"related_route_missing:{route_id}:{related}")
    if forge_count > int(limits.get("max_forge_routes") or 6):
        errors.append("max_forge_routes_exceeded")
    return sorted(set(errors))


def _score_route(
    query: dict[str, Any], route: dict[str, Any]
) -> tuple[int, list[dict[str, Any]]] | None:
    route_id = str(route.get("semantic_route_id") or "")
    purpose = str(route.get("purpose") or "")
    search_terms = [str(item) for item in route.get("search_terms") or []]
    owner_questions = [str(item) for item in route.get("owner_questions") or []]
    normalized_id = normalize_text(route_id)
    if query["normalized"] == normalized_id:
        return IDENTITY_ROUTE_ID, [{"component": "EXACT_ROUTE_ID"}]

    score = 0
    matched_by: list[dict[str, Any]] = []
    normalized_terms = [normalize_text(term) for term in search_terms]
    if query["normalized"] in normalized_terms:
        score += EXACT_SEARCH_TERM
        matched_by.append({"component": "EXACT_SEARCH_TERM"})
    if query["normalized"] == normalize_text(purpose):
        score += EXACT_PURPOSE
        matched_by.append({"component": "EXACT_PURPOSE"})

    field_blobs = [
        normalize_text(purpose),
        " ".join(normalized_terms),
        " ".join(normalize_text(item) for item in owner_questions),
        normalized_id,
    ]
    tokens = [token for token in query["tokens"] if token not in QUERY_STOPWORDS]
    if not tokens:
        tokens = list(query["tokens"])
    if tokens:
        coverage_hits = 0
        for token in tokens:
            variants = {token}
            if token.endswith("es") and len(token) > 3:
                variants.add(token[:-2])
            if token.endswith("s") and len(token) > 3:
                variants.add(token[:-1])
            if any(
                any(variant in blob for variant in variants) for blob in field_blobs
            ):
                coverage_hits += 1
        if coverage_hits == len(tokens):
            score += ALL_TOKENS_FIELDS
            matched_by.append({"component": "ALL_TOKENS_FIELDS"})
        elif coverage_hits:
            coverage = int(TOKEN_COVERAGE_SCALE * coverage_hits / len(tokens))
            score += coverage
            matched_by.append({"component": "TOKEN_COVERAGE", "value": coverage})
        else:
            return None
    phrase = query["phrase"]
    if phrase and any(phrase in blob for blob in field_blobs):
        score += EXACT_PHRASE
        matched_by.append({"component": "EXACT_PHRASE"})
    for question in owner_questions:
        qn = normalize_text(question)
        if phrase and phrase in qn:
            score += OWNER_QUESTION_HIT
            matched_by.append({"component": "OWNER_QUESTION"})
            break
        if tokens and all(
            token in qn or (token.endswith("s") and token[:-1] in qn)
            for token in tokens
        ):
            score += OWNER_QUESTION_HIT
            matched_by.append({"component": "OWNER_QUESTION"})
            break
    if score <= 0:
        return None
    return score, matched_by


def _resolved_roots(
    route: dict[str, Any],
    *,
    assets: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root_bindings: list[dict[str, Any]] = []
    for binding_id in route.get("root_binding_ids") or []:
        spec = bindings.get(binding_id) or {}
        target = spec.get("target_asset_id")
        record = assets.get(str(target)) if target else None
        root_bindings.append(
            {
                "binding_id": binding_id,
                "target_asset_id": target,
                "path": asset_path(record) if record else None,
                "catalog_record_status": (record or {}).get("status"),
                "catalog_record_status_note": (
                    "Catalog asset lifecycle only; not product DONE, runtime health, "
                    "or authority"
                ),
            }
        )
    root_assets: list[dict[str, Any]] = []
    for asset_id in route.get("root_asset_ids") or []:
        record = assets.get(str(asset_id))
        root_assets.append(
            {
                "asset_id": asset_id,
                "path": asset_path(record) if record else None,
                "catalog_record_status": (record or {}).get("status"),
                "catalog_record_status_note": (
                    "Catalog asset lifecycle only; not product DONE, runtime health, "
                    "or authority"
                ),
            }
        )
    return root_bindings, root_assets


def serialize_route(
    route: dict[str, Any],
    *,
    assets: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
    score: int | None = None,
    matched_by: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root_bindings, root_assets = _resolved_roots(route, assets=assets, bindings=bindings)
    payload: dict[str, Any] = {
        "semantic_route_id": route["semantic_route_id"],
        "purpose": route["purpose"],
        "status_plane": route["status_plane"],
        "root_bindings": root_bindings,
        "root_assets": root_assets,
        "query_recipe_ids": list(route.get("query_recipe_ids") or []),
        "runtime_resolution": route.get("runtime_resolution")
        or {"mode": "NONE", "operator_asset_ids": []},
        "forge_visibility": route.get("forge_visibility"),
        "related_route_ids": list(route.get("related_route_ids") or []),
        "authority_granted": False,
    }
    if route["semantic_route_id"] == "SEM-PROVIDER-ROUTES":
        payload["authority_boundary"] = ROUTE_EXISTS_NE_AUTHORIZED
    if score is not None:
        payload["score"] = score
    if matched_by is not None:
        payload["matched_by"] = matched_by
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(encoded) > 8 * 1024:
        raise SemanticOperabilityError("SEMANTIC_ROUTE_RESULT_TOO_LARGE")
    return payload


def list_semantic_routes(
    projection: dict[str, Any],
    *,
    assets: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
) -> list[dict[str, Any]]:
    routes = sorted(
        projection.get("routes") or [],
        key=lambda item: str(item.get("semantic_route_id") or ""),
    )
    return [serialize_route(route, assets=assets, bindings=bindings) for route in routes]


def resolve_semantic_route(
    projection: dict[str, Any],
    route_id: str,
    *,
    assets: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(route_id, str) or not route_id.strip():
        raise SemanticOperabilityError("SEMANTIC_ROUTE_ID_REQUIRED")
    routes = _route_index(projection)
    route = routes.get(route_id.strip())
    if route is None:
        raise SemanticOperabilityError("SEMANTIC_ROUTE_NOT_FOUND")
    return serialize_route(route, assets=assets, bindings=bindings)


def search_semantic_routes(
    projection: dict[str, Any],
    text: str,
    *,
    assets: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
    limit: int = DEFAULT_ROUTE_LIMIT,
    explain: bool = False,
) -> list[dict[str, Any]] | dict[str, Any]:
    if not isinstance(limit, int) or limit < 1 or limit > MAX_ROUTE_LIMIT:
        raise SemanticOperabilityError("LIMIT_OUT_OF_RANGE")
    query = normalize_query(text)
    hits: list[dict[str, Any]] = []
    for route in projection.get("routes") or []:
        ranked = _score_route(query, route)
        if ranked is None:
            continue
        score, matched_by = ranked
        hits.append(
            serialize_route(
                route,
                assets=assets,
                bindings=bindings,
                score=score,
                matched_by=matched_by,
            )
        )
    hits.sort(key=lambda item: (-int(item["score"]), str(item["semantic_route_id"])))
    truncated = len(hits) > limit
    results = hits[:limit]
    if explain:
        return {
            "query": {
                "raw": query["raw"],
                "normalized": query["normalized"],
                "phrase": query["phrase"],
                "tokens": query["tokens"],
            },
            "limit": limit,
            "truncated": truncated,
            "results": results,
            "authority_granted": False,
        }
    return results


def semantic_capability_digest_material(
    projection: dict[str, Any],
    *,
    assets: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
) -> list[str]:
    lines: list[str] = []
    forge_routes = [
        route
        for route in projection.get("routes") or []
        if route.get("forge_visibility") == "INCLUDE"
    ]
    forge_routes.sort(key=lambda item: str(item.get("semantic_route_id") or ""))
    for route in forge_routes:
        route_id = str(route["semantic_route_id"])
        lines.append(f"route:{route_id}")
        for binding_id in sorted(str(item) for item in route.get("root_binding_ids") or []):
            target = (bindings.get(binding_id) or {}).get("target_asset_id")
            lines.append(f"binding:{binding_id}:{target}")
            if target and target in assets:
                digest = _asset_integrity_sha(assets[str(target)]) or "missing"
                lines.append(f"asset:{target}:{digest}")
        for asset_id in sorted(str(item) for item in route.get("root_asset_ids") or []):
            digest = (
                _asset_integrity_sha(assets[asset_id])
                if asset_id in assets
                else "missing"
            )
            lines.append(f"asset:{asset_id}:{digest}")
        for recipe_id in sorted(str(item) for item in route.get("query_recipe_ids") or []):
            lines.append(f"query:{recipe_id}")
    return lines


def semantic_capability_digest_sha256(
    projection: dict[str, Any],
    *,
    assets: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
) -> str:
    material = "\n".join(
        semantic_capability_digest_material(
            projection, assets=assets, bindings=bindings
        )
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def semantic_capability_digest_for_repo(repo_root: Path) -> str:
    projection = load_semantic_projection(repo_root)
    assets, bindings, queries = load_semantic_catalog_views(repo_root)
    violations = validate_semantic_projection(
        projection, assets=assets, bindings=bindings, queries=queries
    )
    if violations:
        raise SemanticOperabilityError(
            "SEMANTIC_PROJECTION_INVALID:" + ",".join(violations)
        )
    return semantic_capability_digest_sha256(
        projection, assets=assets, bindings=bindings
    )


def _forge_semantic_payload_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def build_forge_semantic_capability_projection(
    projection: dict[str, Any],
    *,
    assets: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
    max_bytes: int | None = None,
) -> dict[str, Any]:
    limits = projection.get("limits") or {}
    budget = int(
        max_bytes
        if max_bytes is not None
        else limits.get("max_forge_projection_bytes") or MAX_FORGE_SEMANTIC_BYTES
    )
    max_routes = int(limits.get("max_forge_routes") or 6)
    forge_routes = [
        route
        for route in projection.get("routes") or []
        if route.get("forge_visibility") == "INCLUDE"
    ]
    forge_routes.sort(key=lambda item: str(item.get("semantic_route_id") or ""))
    forge_routes = forge_routes[:max_routes]
    digest = semantic_capability_digest_sha256(
        projection, assets=assets, bindings=bindings
    )
    entries: list[dict[str, Any]] = []
    for route in forge_routes:
        entry = {
            "semantic_route_id": route["semantic_route_id"],
            "root_asset_ids": [],
            "query_recipe_ids": list(route.get("query_recipe_ids") or []),
            "status_plane": route["status_plane"],
            "authority_granted": False,
        }
        for binding_id in route.get("root_binding_ids") or []:
            target = (bindings.get(binding_id) or {}).get("target_asset_id")
            if target:
                entry["root_asset_ids"].append(str(target))
        for asset_id in route.get("root_asset_ids") or []:
            entry["root_asset_ids"].append(str(asset_id))
        entry["root_asset_ids"] = sorted(set(entry["root_asset_ids"]))
        entries.append(entry)

    dropped: list[str] = []

    def _payload(kept: list[dict[str, Any]], dropped_ids: list[str]) -> dict[str, Any]:
        return {
            "semantic_capability_entries": kept,
            "semantic_capability_digest_sha256": digest,
            "kept_semantic_routes": [item["semantic_route_id"] for item in kept],
            "dropped_semantic_routes": list(dropped_ids),
            "semantic_projection_truncated": bool(dropped_ids),
            "authority_granted": False,
        }

    while True:
        payload = _payload(entries, dropped)
        if len(_forge_semantic_payload_bytes(payload)) <= budget:
            return payload
        if not entries:
            return _payload([], dropped)
        removed = entries.pop()
        dropped.insert(0, str(removed["semantic_route_id"]))


def forge_semantic_slice_for_repo(repo_root: Path) -> dict[str, Any]:
    projection = load_semantic_projection(repo_root)
    assets, bindings, queries = load_semantic_catalog_views(repo_root)
    violations = validate_semantic_projection(
        projection, assets=assets, bindings=bindings, queries=queries
    )
    if violations:
        raise SemanticOperabilityError(
            "SEMANTIC_PROJECTION_INVALID:" + ",".join(violations)
        )
    return build_forge_semantic_capability_projection(
        projection, assets=assets, bindings=bindings
    )
