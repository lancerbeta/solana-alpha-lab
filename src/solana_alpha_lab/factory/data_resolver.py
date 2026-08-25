"""Stable-ID evidence resolution for Fast Lane submissions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml
from pydantic import ValidationError

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest
from solana_alpha_lab.factory.run_passport import canonical_sha256, normalize_timestamp


CATALOG_MANIFEST_RELATIVE = "catalog/catalog_manifest.yaml"
QUERY_RECIPES_RELATIVE = "catalog/query_recipes.yaml"
_HASH64_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_STABLE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
_BINDING_KEYS = frozenset(
    {
        "binding_id",
        "source_kind",
        "stable_id",
        "expected_content_sha256_or_dataset_fingerprint",
    }
)


class EvidenceResolutionError(ValueError):
    """Typed fail-closed resolver failure; ``code`` is safe for decisions."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ResolvedEvidence:
    """One stable input bound to process-local bytes and durable identifiers."""

    binding_id: str
    source_kind: str
    stable_id: str
    logical_uri: str
    content_sha256: str | None
    dataset_fingerprint: str | None
    first_reliable_available_at: datetime
    physical_path: Path

    def to_payload(self) -> dict[str, object]:
        """Return the durable path-free representation for a run event."""

        return {
            "binding_id": self.binding_id,
            "content_sha256": self.content_sha256,
            "dataset_fingerprint": self.dataset_fingerprint,
            "first_reliable_available_at": (
                self.first_reliable_available_at.astimezone(UTC)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            ),
            "logical_uri": self.logical_uri,
            "source_kind": self.source_kind,
            "stable_id": self.stable_id,
        }


def _stable_id(name: str, value: object) -> str:
    if not isinstance(value, str) or _STABLE_ID_RE.fullmatch(value) is None:
        raise EvidenceResolutionError(f"{name.upper()}_INVALID")
    return value


def _hash64(name: str, value: object) -> str:
    if not isinstance(value, str) or _HASH64_RE.fullmatch(value) is None:
        raise EvidenceResolutionError(f"{name.upper()}_INVALID")
    return value


def _safe_relative_path(value: object) -> str:
    if not isinstance(value, str) or "\\" in value:
        raise EvidenceResolutionError("CATALOG_LOCATION_INVALID")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or bool(windows.root)
        or not posix.parts
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise EvidenceResolutionError("CATALOG_LOCATION_INVALID")
    return posix.as_posix()


def _repository_file(root: Path, relative: object) -> Path:
    normalized = _safe_relative_path(relative)
    repository_root = root.resolve()
    candidate = repository_root.joinpath(*PurePosixPath(normalized).parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise EvidenceResolutionError("CATALOG_ASSET_UNAVAILABLE") from exc
    if (
        candidate.is_symlink()
        or not resolved.is_file()
        or repository_root not in resolved.parents
    ):
        raise EvidenceResolutionError("CATALOG_LOCATION_INVALID")
    return resolved


def _parse_available_at(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise EvidenceResolutionError("EVIDENCE_AVAILABILITY_INVALID")
        return value.astimezone(UTC)
    if isinstance(value, str) and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value):
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
    try:
        normalized = normalize_timestamp(value)
        return datetime.fromisoformat(normalized[:-1] + "+00:00").astimezone(UTC)
    except ValueError as exc:
        raise EvidenceResolutionError("EVIDENCE_AVAILABILITY_INVALID") from exc


@lru_cache(maxsize=8)
def _catalog_records(root: Path) -> dict[str, Mapping[str, Any]]:
    manifest_path = _repository_file(root, CATALOG_MANIFEST_RELATIVE)
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise EvidenceResolutionError("CATALOG_UNAVAILABLE") from exc
    registries = (
        manifest.get("root_resolver", {}).get("asset_registries")
        if isinstance(manifest, Mapping)
        else None
    )
    if not isinstance(registries, list):
        raise EvidenceResolutionError("CATALOG_INVALID")
    records: dict[str, Mapping[str, Any]] = {}
    for registry in registries:
        registry_path = _repository_file(root, registry)
        try:
            document = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise EvidenceResolutionError("CATALOG_UNAVAILABLE") from exc
        candidates = document.get("records") if isinstance(document, Mapping) else None
        if not isinstance(candidates, list):
            raise EvidenceResolutionError("CATALOG_INVALID")
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise EvidenceResolutionError("CATALOG_INVALID")
            asset_id = candidate.get("asset_id")
            if not isinstance(asset_id, str):
                raise EvidenceResolutionError("CATALOG_INVALID")
            if asset_id in records:
                raise EvidenceResolutionError("CATALOG_DUPLICATE_ASSET_ID")
            records[asset_id] = candidate
    return records


def _catalog_asset(
    root: Path,
    stable_id: str,
    *,
    expected_content_sha256: str | None = None,
) -> ResolvedEvidence:
    record = _catalog_records(root.resolve()).get(stable_id)
    if record is None:
        raise EvidenceResolutionError("CATALOG_ASSET_UNAVAILABLE")
    location = record.get("location")
    integrity = record.get("integrity")
    if not isinstance(location, Mapping) or not isinstance(integrity, Mapping):
        raise EvidenceResolutionError("CATALOG_ASSET_INVALID")
    if location.get("kind") != "git_path" or integrity.get("kind") != "sha256":
        raise EvidenceResolutionError("CATALOG_ASSET_INVALID")
    physical_path = _repository_file(root, location.get("repository_path"))
    content_sha256 = _hash64("catalog_asset_integrity", integrity.get("sha256"))
    observed_sha256 = hashlib.sha256(physical_path.read_bytes()).hexdigest()
    if observed_sha256 != content_sha256:
        raise EvidenceResolutionError("CATALOG_ASSET_INTEGRITY_MISMATCH")
    if (
        expected_content_sha256 is not None
        and content_sha256 != expected_content_sha256
    ):
        raise EvidenceResolutionError("EVIDENCE_HASH_MISMATCH")
    logical_uri = location.get("logical_uri")
    if not isinstance(logical_uri, str) or not logical_uri.startswith("repo://"):
        raise EvidenceResolutionError("CATALOG_LOCATION_INVALID")
    return ResolvedEvidence(
        binding_id="",
        source_kind="CATALOG_ASSET",
        stable_id=stable_id,
        logical_uri=logical_uri,
        content_sha256=content_sha256,
        dataset_fingerprint=None,
        first_reliable_available_at=_parse_available_at(
            record.get("first_reliable_available_at", record.get("as_of"))
        ),
        physical_path=physical_path,
    )


def resolve_catalog_asset(root: Path, stable_id: str) -> ResolvedEvidence:
    """Resolve and integrity-check a Catalog asset by immutable ID."""

    return _catalog_asset(root, _stable_id("stable_id", stable_id))


def _data_root(data_root: Path) -> Path:
    if not isinstance(data_root, Path) or not data_root.is_absolute():
        raise EvidenceResolutionError("DATA_ROOT_INVALID")
    if data_root.is_symlink():
        raise EvidenceResolutionError("DATA_ROOT_INVALID")
    try:
        return data_root.resolve()
    except OSError as exc:
        raise EvidenceResolutionError("DATA_ROOT_INVALID") from exc


def _existing_data_file(root: Path, candidates: Sequence[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise EvidenceResolutionError("DATA_BINDING_UNAVAILABLE") from exc
        if root not in resolved.parents:
            raise EvidenceResolutionError("DATA_BINDING_INVALID")
        return resolved
    return None


def _dataset_manifest(
    *,
    binding_id: str,
    stable_id: str,
    expected_fingerprint: str,
    data_root: Path,
) -> ResolvedEvidence:
    root = _data_root(data_root)
    physical_path = _existing_data_file(
        root,
        (
            root / "datasets" / "manifests" / f"{stable_id}.json",
            root / "datasets" / f"{stable_id}.json",
            root / f"{stable_id}.json",
        ),
    )
    if physical_path is None:
        raise EvidenceResolutionError("DATA_BINDING_UNAVAILABLE")
    try:
        manifest = DatasetManifest.model_validate_json(physical_path.read_bytes())
    except (OSError, ValidationError, ValueError) as exc:
        raise EvidenceResolutionError("DATASET_MANIFEST_INVALID") from exc
    if manifest.dataset_manifest_id != stable_id:
        raise EvidenceResolutionError("DATASET_MANIFEST_INVALID")
    if manifest.dataset_fingerprint != expected_fingerprint:
        raise EvidenceResolutionError("EVIDENCE_HASH_MISMATCH")
    return ResolvedEvidence(
        binding_id=binding_id,
        source_kind="DATASET_MANIFEST",
        stable_id=stable_id,
        logical_uri=f"smial-data://datasets/manifests/{stable_id}.json",
        content_sha256=None,
        dataset_fingerprint=manifest.dataset_fingerprint,
        first_reliable_available_at=manifest.first_reliable_available_at.astimezone(
            UTC
        ),
        physical_path=physical_path,
    )


def _research_artifact(
    *,
    binding_id: str,
    stable_id: str,
    expected_content_sha256: str,
    data_root: Path,
) -> ResolvedEvidence:
    root = _data_root(data_root)
    physical_path = _existing_data_file(
        root,
        (
            root / "research" / "artifacts" / f"{stable_id}.json",
            root / "artifacts" / f"{stable_id}.json",
        ),
    )
    if physical_path is None:
        raise EvidenceResolutionError("DATA_BINDING_UNAVAILABLE")
    try:
        artifact = json.loads(physical_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise EvidenceResolutionError("RESEARCH_ARTIFACT_INVALID") from exc
    if not isinstance(artifact, Mapping):
        raise EvidenceResolutionError("RESEARCH_ARTIFACT_INVALID")
    if artifact.get("research_artifact_id") != stable_id:
        raise EvidenceResolutionError("RESEARCH_ARTIFACT_INVALID")
    content_sha256 = _hash64(
        "research_artifact_content_sha256",
        artifact.get("content_sha256"),
    )
    if content_sha256 != expected_content_sha256:
        raise EvidenceResolutionError("EVIDENCE_HASH_MISMATCH")
    logical_uri = artifact.get("logical_uri")
    if not isinstance(logical_uri, str) or not logical_uri.startswith("smial-data://"):
        raise EvidenceResolutionError("RESEARCH_ARTIFACT_INVALID")
    return ResolvedEvidence(
        binding_id=binding_id,
        source_kind="RESEARCH_ARTIFACT",
        stable_id=stable_id,
        logical_uri=logical_uri,
        content_sha256=content_sha256,
        dataset_fingerprint=None,
        first_reliable_available_at=_parse_available_at(
            artifact.get("first_reliable_available_at")
        ),
        physical_path=physical_path,
    )


def _availability_cutoff(spec: Mapping[str, Any]) -> datetime:
    try:
        return _parse_available_at(spec["availability_cutoff"])
    except KeyError as exc:
        raise EvidenceResolutionError("EVIDENCE_AVAILABILITY_INVALID") from exc


def resolve_evidence_bindings(
    spec: Mapping[str, Any],
    *,
    root: Path,
    data_root: Path,
) -> tuple[ResolvedEvidence, ...]:
    """Resolve only stable Catalog/data-plane bindings and verify their hashes."""

    bindings = spec.get("data_bindings") if isinstance(spec, Mapping) else None
    if not isinstance(bindings, (list, tuple)):
        raise EvidenceResolutionError("DATA_BINDINGS_INVALID")
    cutoff = _availability_cutoff(spec)
    resolved: list[ResolvedEvidence] = []
    seen_binding_ids: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, Mapping) or set(binding) != _BINDING_KEYS:
            raise EvidenceResolutionError("DATA_BINDING_INVALID")
        binding_id = _stable_id("binding_id", binding.get("binding_id"))
        stable_id = _stable_id("stable_id", binding.get("stable_id"))
        if binding_id in seen_binding_ids:
            raise EvidenceResolutionError("DATA_BINDING_DUPLICATE")
        seen_binding_ids.add(binding_id)
        source_kind = binding.get("source_kind")
        expected = _hash64(
            "expected_content_sha256_or_dataset_fingerprint",
            binding.get("expected_content_sha256_or_dataset_fingerprint"),
        )
        if source_kind == "CATALOG_ASSET":
            catalog_evidence = _catalog_asset(
                root,
                stable_id,
                expected_content_sha256=expected,
            )
            evidence = ResolvedEvidence(
                binding_id=binding_id,
                source_kind="CATALOG_ASSET",
                stable_id=stable_id,
                logical_uri=catalog_evidence.logical_uri,
                content_sha256=catalog_evidence.content_sha256,
                dataset_fingerprint=None,
                first_reliable_available_at=(
                    catalog_evidence.first_reliable_available_at
                ),
                physical_path=catalog_evidence.physical_path,
            )
        elif source_kind == "DATASET_MANIFEST":
            evidence = _dataset_manifest(
                binding_id=binding_id,
                stable_id=stable_id,
                expected_fingerprint=expected,
                data_root=data_root,
            )
        elif source_kind == "RESEARCH_ARTIFACT":
            evidence = _research_artifact(
                binding_id=binding_id,
                stable_id=stable_id,
                expected_content_sha256=expected,
                data_root=data_root,
            )
        else:
            raise EvidenceResolutionError("DATA_BINDING_SOURCE_KIND_INVALID")
        if evidence.first_reliable_available_at > cutoff:
            raise EvidenceResolutionError("EVIDENCE_UNAVAILABLE_AT_CUTOFF")
        resolved.append(evidence)
    return tuple(resolved)


@lru_cache(maxsize=8)
def _query_recipes(root: Path) -> dict[str, Mapping[str, Any]]:
    path = _repository_file(root, QUERY_RECIPES_RELATIVE)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise EvidenceResolutionError("QUERY_RECIPE_REGISTRY_UNAVAILABLE") from exc
    recipes = document.get("recipes") if isinstance(document, Mapping) else None
    if not isinstance(recipes, list):
        raise EvidenceResolutionError("QUERY_RECIPE_REGISTRY_INVALID")
    indexed: dict[str, Mapping[str, Any]] = {}
    for recipe in recipes:
        if not isinstance(recipe, Mapping):
            raise EvidenceResolutionError("QUERY_RECIPE_REGISTRY_INVALID")
        recipe_id = recipe.get("recipe_id")
        if not isinstance(recipe_id, str) or recipe_id in indexed:
            raise EvidenceResolutionError("QUERY_RECIPE_REGISTRY_INVALID")
        indexed[recipe_id] = recipe
    return indexed


def resolve_query_recipe_hashes(
    recipe_ids: Sequence[str],
    *,
    root: Path,
) -> tuple[tuple[str, str], ...]:
    """Resolve bounded read-only recipe IDs to their canonical content hashes."""

    if isinstance(recipe_ids, (str, bytes, bytearray)):
        raise EvidenceResolutionError("QUERY_IMPLEMENTATION_MISSING")
    recipes = _query_recipes(root.resolve())
    resolved: list[tuple[str, str]] = []
    seen: set[str] = set()
    for recipe_id in recipe_ids:
        stable_id = _stable_id("query_recipe_id", recipe_id)
        if stable_id in seen:
            raise EvidenceResolutionError("QUERY_IMPLEMENTATION_MISSING")
        seen.add(stable_id)
        recipe = recipes.get(stable_id)
        if recipe is None:
            raise EvidenceResolutionError("QUERY_IMPLEMENTATION_MISSING")
        if (
            recipe.get("read_only") is not True
            or recipe.get("bounded") is not True
            or recipe.get("write_effects") != "NONE"
        ):
            raise EvidenceResolutionError("ARBITRARY_CODE_OR_SQL_REQUESTED")
        resolved.append((stable_id, canonical_sha256(recipe)))
    return tuple(resolved)


def verify_implementation_assets(
    descriptor: Mapping[str, Any],
    *,
    root: Path,
    runner_git_sha: str,
    git_show_bytes: Callable[[Path, str, str], bytes | None],
) -> tuple[tuple[str, str], ...]:
    """Verify Catalog implementation assets at both Git and working bytes."""

    if _GIT_SHA_RE.fullmatch(runner_git_sha) is None:
        raise EvidenceResolutionError("IMPLEMENTATION_HASH_MISMATCH")
    asset_ids = descriptor.get("implementation_asset_ids")
    if not isinstance(asset_ids, list) or not asset_ids:
        raise EvidenceResolutionError("IMPLEMENTATION_HASH_MISMATCH")
    observed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for candidate in asset_ids:
        asset_id = _stable_id("implementation_asset_id", candidate)
        if asset_id in seen:
            raise EvidenceResolutionError("IMPLEMENTATION_HASH_MISMATCH")
        seen.add(asset_id)
        evidence = _catalog_asset(root, asset_id)
        if evidence.content_sha256 is None:
            raise EvidenceResolutionError("IMPLEMENTATION_HASH_MISMATCH")
        record = _catalog_records(root.resolve()).get(asset_id)
        if not isinstance(record, Mapping):
            raise EvidenceResolutionError("IMPLEMENTATION_HASH_MISMATCH")
        location = record.get("location")
        if not isinstance(location, Mapping):
            raise EvidenceResolutionError("IMPLEMENTATION_HASH_MISMATCH")
        relative = _safe_relative_path(location.get("repository_path"))
        committed_bytes = git_show_bytes(root, runner_git_sha, relative)
        if committed_bytes is None:
            raise EvidenceResolutionError("IMPLEMENTATION_HASH_MISMATCH")
        if hashlib.sha256(committed_bytes).hexdigest() != evidence.content_sha256:
            raise EvidenceResolutionError("IMPLEMENTATION_HASH_MISMATCH")
        if hashlib.sha256(evidence.physical_path.read_bytes()).hexdigest() != (
            evidence.content_sha256
        ):
            raise EvidenceResolutionError("IMPLEMENTATION_HASH_MISMATCH")
        observed.append((asset_id, evidence.content_sha256))
    return tuple(sorted(observed))


__all__ = [
    "ResolvedEvidence",
    "resolve_evidence_bindings",
]
