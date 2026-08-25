"""Deterministic Catalog binding resolution, ranked search and related-asset BFS."""

from __future__ import annotations

import hashlib
import re
import subprocess
import unicodedata
from typing import Any

STABLE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
INACTIVE_STATUSES = frozenset(
    {"DEPRECATED", "BUNDLE_ONLY_SUPERSEDED", "DECIDED_NOT_IMPLEMENTED"}
)
UNVERIFIED_STATUS = "IMPLEMENTED_UNVERIFIED"
IDENTITY_ASSET_ID = 100000
IDENTITY_BINDING_ID = 99000
IDENTITY_PATH = 98000
BINDING_TARGET_BONUS = 8000
EXACT_SEARCH_TERM = 7000
EXACT_PURPOSE = 6500
ALL_TOKENS_ONE_TERM = 5000
ALL_TOKENS_ID_PATH_TERMS = 4500
ALL_TOKENS_INDEX = 3000
EXACT_PHRASE = 500
TOKEN_COVERAGE_SCALE = 1000
INACTIVE_PENALTY = 2000
DEFAULT_SEARCH_LIMIT = 20
MAX_LIMIT = 50
MAX_RELATED_DEPTH = 2
PLACEHOLDER_RE = re.compile(r"[<>]|replace with|TODO|TBD", re.IGNORECASE)


class CatalogDiscoveryError(ValueError):
    """Typed discovery/CLI contract error; `args[0]` is the stable code."""


class BindingValidationError(ValueError):
    """Catalog binding semantic failure; converted to CatalogValidationError by the validator."""


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def phrase_form(normalized: str) -> str:
    return " ".join(tokenize(normalized))


def tokenize(normalized: str) -> list[str]:
    tokens: list[str] = []
    buf: list[str] = []
    for char in normalized:
        if char.isalnum():
            buf.append(char)
            continue
        if buf:
            tokens.append("".join(buf))
            buf = []
    if buf:
        tokens.append("".join(buf))
    return tokens


def normalize_query(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise CatalogDiscoveryError("SEARCH_TEXT_REQUIRED")
    if any(ord(char) < 32 or char == "\x7f" for char in text):
        raise CatalogDiscoveryError("SEARCH_CONTROL_CHARACTERS")
    normalized = normalize_text(text)
    if not normalized:
        raise CatalogDiscoveryError("SEARCH_TEXT_REQUIRED")
    tokens = tokenize(normalized)
    return {
        "raw": text,
        "normalized": normalized,
        "phrase": phrase_form(normalized),
        "tokens": tokens,
    }


def asset_path(record: dict[str, Any]) -> str:
    location = record.get("location") or {}
    return str(location.get("repository_path") or "")


def asset_logical_uri(record: dict[str, Any]) -> str:
    location = record.get("location") or {}
    return str(location.get("logical_uri") or "")


def binding_targets(bindings: dict[str, Any] | None) -> dict[str, list[str]]:
    targets: dict[str, list[str]] = {}
    for binding_id, spec in (bindings or {}).items():
        target = spec.get("target_asset_id")
        if not target:
            continue
        targets.setdefault(str(target), []).append(str(binding_id))
    for asset_id in targets:
        targets[asset_id] = sorted(set(targets[asset_id]))
    return targets


def _field_blob(values: list[str]) -> str:
    return " ".join(normalize_text(value) for value in values if value)


def indexed_document(
    asset_id: str,
    record: dict[str, Any],
    canonical_binding_ids: list[str],
) -> dict[str, Any]:
    path = asset_path(record)
    logical_uri = asset_logical_uri(record)
    purpose = str(record.get("purpose") or "")
    search_terms = [str(item) for item in record.get("search_terms") or []]
    consumers = [str(item) for item in record.get("consumers") or []]
    relation_parts: list[str] = []
    for relation in record.get("relations") or []:
        relation_parts.append(
            f"{relation.get('relation_type', '')} {relation.get('target_asset_id', '')}"
        )
    evidence_parts: list[str] = []
    for item in record.get("evidence") or []:
        if isinstance(item, dict):
            evidence_parts.extend(str(value) for value in item.values() if value)
        elif item:
            evidence_parts.append(str(item))
    fields = {
        "asset_id": asset_id,
        "path": path,
        "logical_uri": logical_uri,
        "purpose": purpose,
        "search_terms": search_terms,
        "consumers": consumers,
        "relations": relation_parts,
        "evidence": evidence_parts,
        "binding_ids": canonical_binding_ids,
    }
    normalized_terms = [normalize_text(term) for term in search_terms]
    id_path_terms = _field_blob([asset_id, path, logical_uri, *search_terms])
    all_indexed = _field_blob(
        [
            asset_id,
            path,
            logical_uri,
            purpose,
            *search_terms,
            *consumers,
            *relation_parts,
            *evidence_parts,
            *canonical_binding_ids,
        ]
    )
    return {
        "fields": fields,
        "normalized_id": normalize_text(asset_id),
        "normalized_path": normalize_text(path),
        "normalized_logical_uri": normalize_text(logical_uri),
        "normalized_purpose": normalize_text(purpose),
        "normalized_terms": normalized_terms,
        "id_path_terms": id_path_terms,
        "all_indexed": all_indexed,
        "phrase_fields": [
            phrase_form(normalize_text(value))
            for value in [asset_id, path, logical_uri, purpose, *search_terms, *consumers, *relation_parts, *evidence_parts, *canonical_binding_ids]
            if value
        ],
    }


def _unique_token_coverage(tokens: list[str], blob: str) -> int:
    unique = list(dict.fromkeys(tokens))
    if not unique:
        return 0
    blob_tokens = set(tokenize(blob))
    matched = sum(1 for token in unique if token in blob_tokens)
    return (matched * TOKEN_COVERAGE_SCALE) // len(unique)


def _passes_filters(
    record: dict[str, Any],
    *,
    asset_type: str | None,
    consumer: str | None,
    status: str | None,
    relation: str | None,
) -> bool:
    if asset_type is not None and record.get("asset_type") != asset_type:
        return False
    if consumer is not None and consumer not in (record.get("consumers") or []):
        return False
    if status is not None and record.get("status") != status:
        return False
    if relation is not None:
        types = {item.get("relation_type") for item in record.get("relations") or []}
        if relation not in types:
            return False
    return True


def _score_non_identity(
    query: dict[str, Any],
    document: dict[str, Any],
    canonical_binding_ids: list[str],
    match: str,
) -> tuple[int, list[dict[str, Any]]] | None:
    tokens = query["tokens"]
    blob_tokens = set(tokenize(document["all_indexed"]))
    if match == "all":
        if tokens and not all(token in blob_tokens for token in tokens):
            return None
    elif match == "any":
        if tokens and not any(token in blob_tokens for token in tokens):
            return None
    else:
        raise CatalogDiscoveryError("MATCH_MODE_INVALID")

    score = 0
    matched_by: list[dict[str, Any]] = []
    if canonical_binding_ids:
        score += BINDING_TARGET_BONUS
        matched_by.append(
            {"component": "CANONICAL_BINDING_TARGET", "binding_ids": list(canonical_binding_ids)}
        )
    if query["normalized"] in document["normalized_terms"]:
        score += EXACT_SEARCH_TERM
        matched_by.append({"component": "EXACT_SEARCH_TERM", "value": query["normalized"]})
    if query["normalized"] == document["normalized_purpose"] and document["normalized_purpose"]:
        score += EXACT_PURPOSE
        matched_by.append({"component": "EXACT_PURPOSE"})
    if tokens:
        for term in document["normalized_terms"]:
            term_tokens = set(tokenize(term))
            if all(token in term_tokens for token in tokens):
                score += ALL_TOKENS_ONE_TERM
                matched_by.append({"component": "ALL_TOKENS_ONE_SEARCH_TERM", "value": term})
                break
        id_path_tokens = set(tokenize(document["id_path_terms"]))
        if all(token in id_path_tokens for token in tokens):
            score += ALL_TOKENS_ID_PATH_TERMS
            matched_by.append({"component": "ALL_TOKENS_ID_PATH_TERMS"})
        index_tokens = set(tokenize(document["all_indexed"]))
        if all(token in index_tokens for token in tokens):
            score += ALL_TOKENS_INDEX
            matched_by.append({"component": "ALL_TOKENS_INDEX"})
        coverage = _unique_token_coverage(tokens, document["all_indexed"])
        if coverage:
            score += coverage
            matched_by.append({"component": "TOKEN_COVERAGE", "value": coverage})
    phrase = query["phrase"]
    if phrase and any(phrase in field for field in document["phrase_fields"]):
        score += EXACT_PHRASE
        matched_by.append({"component": "EXACT_PHRASE"})
    return score, matched_by


def search_catalog_assets(
    assets: dict[str, dict[str, Any]],
    text: str,
    *,
    bindings: dict[str, Any] | None = None,
    asset_type: str | None = None,
    consumer: str | None = None,
    status: str | None = None,
    relation: str | None = None,
    match: str = "all",
    limit: int = DEFAULT_SEARCH_LIMIT,
    explain: bool = False,
) -> list[dict[str, Any]] | dict[str, Any]:
    if match not in {"all", "any"}:
        raise CatalogDiscoveryError("MATCH_MODE_INVALID")
    if not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise CatalogDiscoveryError("LIMIT_OUT_OF_RANGE")
    query = normalize_query(text)
    targets = binding_targets(bindings)
    binding_ids_by_norm = {
        normalize_text(binding_id): binding_id for binding_id in (bindings or {})
    }

    hits: list[dict[str, Any]] = []
    exact_binding = binding_ids_by_norm.get(query["normalized"])
    for asset_id, record in assets.items():
        if not _passes_filters(
            record,
            asset_type=asset_type,
            consumer=consumer,
            status=status,
            relation=relation,
        ):
            continue
        canonical_ids = targets.get(asset_id, [])
        document = indexed_document(asset_id, record, canonical_ids)
        identity_score: int | None = None
        matched_by: list[dict[str, Any]] = []
        if document["normalized_id"] == query["normalized"]:
            identity_score = IDENTITY_ASSET_ID
            matched_by = [{"component": "EXACT_ASSET_ID"}]
        elif exact_binding and (bindings or {})[exact_binding].get("target_asset_id") == asset_id:
            identity_score = IDENTITY_BINDING_ID
            matched_by = [{"component": "EXACT_BINDING_ID", "binding_ids": [exact_binding]}]
        elif document["normalized_path"] and document["normalized_path"] == query["normalized"]:
            identity_score = IDENTITY_PATH
            matched_by = [{"component": "EXACT_PATH", "value": asset_path(record)}]
        elif document["normalized_logical_uri"] and document["normalized_logical_uri"] == query["normalized"]:
            identity_score = IDENTITY_PATH
            matched_by = [{"component": "EXACT_LOGICAL_URI", "value": asset_logical_uri(record)}]
        if identity_score is None:
            ranked = _score_non_identity(query, document, canonical_ids, match)
            if ranked is None:
                continue
            score, matched_by = ranked
        else:
            score = identity_score
        lifecycle = str(record.get("status") or "")
        if lifecycle in INACTIVE_STATUSES:
            score -= INACTIVE_PENALTY
            matched_by.append({"component": "INACTIVE_PENALTY", "value": INACTIVE_PENALTY})
        hits.append(
            {
                "asset_id": asset_id,
                "asset_type": record.get("asset_type"),
                "status": record.get("status"),
                "purpose": record.get("purpose"),
                "location": record.get("location"),
                "consumers": record.get("consumers", []),
                "relations": record.get("relations", []),
                "evidence": record.get("evidence", []),
                "search_terms": record.get("search_terms", []),
                "path": asset_path(record),
                "score": score,
                "matched_by": matched_by,
                "lifecycle": lifecycle,
                "canonical_binding_ids": canonical_ids,
            }
        )

    hits.sort(key=lambda item: (-int(item["score"]), str(item["asset_id"])))
    truncated = len(hits) > limit
    results = hits[:limit]
    if explain:
        return {
            "query": {
                "raw": query["raw"],
                "normalized": query["normalized"],
                "phrase": query["phrase"],
                "tokens": query["tokens"],
                "match": match,
            },
            "limit": limit,
            "truncated": truncated,
            "results": results,
        }
    return results


def _edges(
    assets: dict[str, dict[str, Any]],
    direction: str,
    relation_filter: frozenset[str] | None,
) -> dict[str, list[tuple[str, str, str]]]:
    outgoing: dict[str, list[tuple[str, str, str]]] = {asset_id: [] for asset_id in assets}
    incoming: dict[str, list[tuple[str, str, str]]] = {asset_id: [] for asset_id in assets}
    for source_id, record in assets.items():
        for relation in record.get("relations") or []:
            rel = str(relation.get("relation_type") or "")
            target = str(relation.get("target_asset_id") or "")
            if not rel or not target or target not in assets:
                continue
            if relation_filter is not None and rel not in relation_filter:
                continue
            outgoing[source_id].append((rel, target, "out"))
            incoming[target].append((rel, source_id, "in"))
    combined: dict[str, list[tuple[str, str, str]]] = {}
    for asset_id in assets:
        rows: list[tuple[str, str, str]] = []
        if direction in {"out", "both"}:
            rows.extend(outgoing[asset_id])
        if direction in {"in", "both"}:
            rows.extend(incoming[asset_id])
        rows.sort(key=lambda item: (item[0], item[1], item[2]))
        combined[asset_id] = rows
    return combined


def related_catalog_assets(
    assets: dict[str, dict[str, Any]],
    asset_id: str,
    *,
    depth: int = 1,
    direction: str = "both",
    relation: str | None = None,
    relations: list[str] | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> dict[str, Any]:
    if asset_id not in assets:
        raise CatalogDiscoveryError("ASSET_NOT_FOUND")
    if direction not in {"out", "in", "both"}:
        raise CatalogDiscoveryError("DIRECTION_INVALID")
    if not isinstance(depth, int) or depth < 1 or depth > MAX_RELATED_DEPTH:
        raise CatalogDiscoveryError("DEPTH_OUT_OF_RANGE")
    if not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise CatalogDiscoveryError("LIMIT_OUT_OF_RANGE")
    filters = [item for item in ([relation] if relation else []) + (relations or []) if item]
    relation_filter = frozenset(filters) if filters else None
    edges = _edges(assets, direction, relation_filter)
    start = assets[asset_id]
    best: dict[str, tuple[int, tuple[tuple[str, str, str], ...]]] = {
        asset_id: (0, ())
    }
    layer: dict[str, tuple[tuple[str, str, str], ...]] = {asset_id: ()}
    for current_depth in range(1, depth + 1):
        candidates: dict[str, tuple[tuple[str, str, str], ...]] = {}
        for node, path in layer.items():
            for rel, neighbor, hop_direction in edges[node]:
                if neighbor == asset_id:
                    continue
                new_path = path + ((rel, neighbor, hop_direction),)
                previous = best.get(neighbor)
                if previous is not None and previous[0] < current_depth:
                    continue
                current = candidates.get(neighbor)
                if current is None or new_path < current:
                    candidates[neighbor] = new_path
        layer = {}
        for neighbor, path in candidates.items():
            best[neighbor] = (current_depth, path)
            layer[neighbor] = path

    ordered = sorted(
        (
            (neighbor, depth_value, path)
            for neighbor, (depth_value, path) in best.items()
            if neighbor != asset_id
        ),
        key=lambda item: (item[1], item[0]),
    )
    truncated = len(ordered) > limit
    results = []
    for neighbor, depth_value, path in ordered[:limit]:
        record = assets[neighbor]
        results.append(
            {
                "asset_id": neighbor,
                "depth": depth_value,
                "direction": path[-1][2] if path else direction,
                "path": [
                    {
                        "relation_type": rel,
                        "asset_id": hop_id,
                        "direction": hop_direction,
                    }
                    for rel, hop_id, hop_direction in path
                ],
                "lifecycle": record.get("status"),
                "path_repository": asset_path(record),
            }
        )
    return {
        "start": {
            "asset_id": asset_id,
            "lifecycle": start.get("status"),
            "path": asset_path(start),
        },
        "results": results,
        "truncated": truncated,
        "limit": limit,
        "authority_inferred": False,
    }


def git_head(root: Any) -> str:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CatalogDiscoveryError("BINDING_GIT_UNAVAILABLE") from exc
    return output.strip()


def dirty_paths(root: Any, paths: list[str]) -> list[str]:
    if not paths:
        return []
    try:
        output = subprocess.check_output(
            ["git", "status", "--porcelain", "-uall", "--", *paths],
            cwd=str(root),
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CatalogDiscoveryError("BINDING_GIT_UNAVAILABLE") from exc
    dirty: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        rel = line[3:].strip().replace("\\", "/")
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        dirty.append(rel)
    return sorted(set(dirty))


def file_sha256(path: Any) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_canonical_bindings(
    manifest: dict[str, Any],
    assets: dict[str, dict[str, Any]],
) -> None:
    if manifest.get("schema_version") != "1.1":
        if "canonical_bindings" in manifest:
            raise BindingValidationError("canonical_bindings_forbidden_on_manifest_1_0")
        return
    bindings = manifest.get("canonical_bindings")
    if not isinstance(bindings, dict) or not bindings:
        raise BindingValidationError("canonical_bindings_required")
    seen_ids: set[str] = set()
    for binding_id, spec in bindings.items():
        if not STABLE_ID_RE.match(str(binding_id)):
            raise BindingValidationError(f"binding_id_invalid:{binding_id}")
        if binding_id in seen_ids:
            raise BindingValidationError(f"binding_id_duplicate:{binding_id}")
        seen_ids.add(binding_id)
        if not isinstance(spec, dict):
            raise BindingValidationError(f"binding_spec_invalid:{binding_id}")
        target = spec.get("target_asset_id")
        if target not in assets:
            raise BindingValidationError(f"binding_target_not_found:{binding_id}:{target}")
        if target in bindings:
            raise BindingValidationError(f"binding_target_is_binding:{binding_id}")
        record = assets[target]
        expected_type = spec.get("expected_asset_type")
        if expected_type is not None and record.get("asset_type") != expected_type:
            raise BindingValidationError(f"binding_type_mismatch:{binding_id}")
        status = record.get("status")
        if status in INACTIVE_STATUSES:
            raise BindingValidationError(f"binding_target_inactive:{binding_id}:{status}")
        evidence_ids = spec.get("current_use_evidence_asset_ids") or []
        if not isinstance(evidence_ids, list):
            raise BindingValidationError(f"binding_evidence_invalid:{binding_id}")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise BindingValidationError(f"binding_evidence_duplicate:{binding_id}")
        for evidence_id in evidence_ids:
            if evidence_id not in assets:
                raise BindingValidationError(
                    f"binding_evidence_missing:{binding_id}:{evidence_id}"
                )
            if PLACEHOLDER_RE.search(str(evidence_id)):
                raise BindingValidationError(f"binding_evidence_placeholder:{binding_id}")
        if status == UNVERIFIED_STATUS and not evidence_ids:
            raise BindingValidationError(
                f"binding_unverified_evidence_missing:{binding_id}"
            )
        if spec.get("semantics") != "CURRENT_AT_COMMIT":
            raise BindingValidationError(f"binding_semantics_invalid:{binding_id}")


def resolve_canonical_binding(
    snapshot: Any,
    binding_id: str,
    *,
    root: Any,
    shard_paths: list[str],
) -> dict[str, Any]:
    bindings = (snapshot.manifest or {}).get("canonical_bindings") or {}
    if binding_id not in bindings:
        raise CatalogDiscoveryError("BINDING_NOT_FOUND")
    spec = bindings[binding_id]
    target = spec.get("target_asset_id")
    record = snapshot.assets.get(target)
    if record is None:
        raise CatalogDiscoveryError("BINDING_TARGET_NOT_FOUND")
    expected_type = spec.get("expected_asset_type")
    if expected_type is not None and record.get("asset_type") != expected_type:
        raise CatalogDiscoveryError("BINDING_TYPE_MISMATCH")
    status = record.get("status")
    if status in INACTIVE_STATUSES:
        raise CatalogDiscoveryError("BINDING_TARGET_INACTIVE")
    evidence_ids = spec.get("current_use_evidence_asset_ids") or []
    if status == UNVERIFIED_STATUS and not evidence_ids:
        raise CatalogDiscoveryError("BINDING_UNVERIFIED_EVIDENCE_MISSING")
    path = asset_path(record)
    target_file = root / path
    if not path or not target_file.is_file():
        raise CatalogDiscoveryError("BINDING_TARGET_PATH_MISSING")
    relevant = ["catalog/catalog_manifest.yaml", path, *shard_paths]
    dirty = dirty_paths(root, relevant)
    relevant_clean = not dirty
    if not relevant_clean:
        raise CatalogDiscoveryError("BINDING_RELEVANT_BYTES_DIRTY")
    payload = {
        "binding_id": binding_id,
        "semantics": spec.get("semantics"),
        "asset_id": target,
        "path": path,
        "content_sha256": file_sha256(target_file),
        "catalog_version": snapshot.manifest.get("catalog_version"),
        "repository_commit": git_head(root),
        "relevant_bytes_clean": True,
        "lifecycle": status,
        "followed_superseded_by": False,
    }
    if status == UNVERIFIED_STATUS:
        payload["verification_warning"] = (
            "IMPLEMENTED_UNVERIFIED_CURRENT_USE_EVIDENCE_PRESENT"
        )
        payload["current_use_evidence_asset_ids"] = list(evidence_ids)
    return payload
