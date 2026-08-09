"""Fail-closed Project Sources release binding for TASK-34A navigation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


ACTIVE_STATUS = "ACTIVATED_BY_OWNER_SMOKE"
MIRROR_MATCHES = "MIRROR_MATCHES_ACTIVE_RELEASE"
MIRROR_STALE = "STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED"
MIRROR_UNAVAILABLE = "MIRROR_UNAVAILABLE"
MIRROR_CONFLICT = "MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW"
ROLE_ORDER = (
    "canonical_manifest",
    "operating_system",
    "research_blueprint",
    "roadmap",
    "current_system_state",
    "phase_archive",
    "active_task",
)


class ContextBindingError(ValueError):
    """Raised when an activated Project Sources release cannot be proven."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ContextBindingError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _load_yaml(path: Path, code: str) -> Mapping[str, Any]:
    _require(path.is_file(), code)
    return _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), code)


def _load_json(path: Path, code: str) -> Mapping[str, Any]:
    _require(path.is_file(), code)
    return _mapping(json.loads(path.read_text(encoding="utf-8")), code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_active_release(repository_root: Path) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    registry = _load_yaml(
        repository_root / "docs/project_sources/release_registry_v1.yaml",
        "RELEASE_REGISTRY_REQUIRED",
    )
    active_release_id = registry.get("active_ui_release_id")
    releases = registry.get("releases")
    _require(isinstance(active_release_id, str), "ACTIVE_RELEASE_POINTER_REQUIRED")
    _require(isinstance(releases, list), "RELEASE_LIST_REQUIRED")
    active_releases = [
        _mapping(release, "RELEASE_RECORD_INVALID")
        for release in releases
        if isinstance(release, Mapping) and release.get("status") == ACTIVE_STATUS
    ]
    _require(len(active_releases) == 1, "ACTIVE_RELEASE_EXACTLY_ONE_REQUIRED")
    release = active_releases[0]
    _require(release.get("release_id") == active_release_id, "ACTIVE_RELEASE_POINTER_MISMATCH")
    _require(
        registry.get("active_ui_state") == "REGISTRY_ACTIVATION_CONFIRMED",
        "ACTIVE_RELEASE_STATE_MISMATCH",
    )

    bindings = _mapping(release.get("artifact_bindings"), "RELEASE_BINDINGS_REQUIRED")
    manifest_binding = _mapping(
        bindings.get("canonical_manifest"), "MANIFEST_BINDING_REQUIRED"
    )
    manifest_relative_path = manifest_binding.get("path")
    manifest_hash = manifest_binding.get("sha256")
    _require(isinstance(manifest_relative_path, str), "MANIFEST_BINDING_PATH_REQUIRED")
    _require(isinstance(manifest_hash, str), "MANIFEST_BINDING_HASH_REQUIRED")
    manifest_path = repository_root / manifest_relative_path
    _require(manifest_path.is_file(), "MANIFEST_BINDING_FILE_REQUIRED")
    _require(_sha256(manifest_path) == manifest_hash, "MANIFEST_BINDING_HASH_MISMATCH")
    manifest = _load_yaml(manifest_path, "MANIFEST_INVALID")
    _require(
        manifest.get("schema") == "solana_alpha_lab.canonical_manifest",
        "MANIFEST_SCHEMA_MISMATCH",
    )

    activation_receipt_path = release.get("activation_receipt")
    _require(
        isinstance(activation_receipt_path, str), "ACTIVATION_RECEIPT_PATH_REQUIRED"
    )
    receipt = _load_json(
        repository_root / activation_receipt_path, "ACTIVATION_RECEIPT_REQUIRED"
    )
    _require(
        receipt.get("schema") == "smial.project_sources.activation.receipt",
        "ACTIVATION_RECEIPT_SCHEMA_MISMATCH",
    )
    _require(
        receipt.get("release_id") == active_release_id,
        "ACTIVATION_RECEIPT_RELEASE_MISMATCH",
    )
    evidence = _mapping(
        receipt.get("activation_evidence"), "ACTIVATION_RECEIPT_EVIDENCE_REQUIRED"
    )
    _require(
        evidence.get("class") == "OWNER_ATTESTATION",
        "ACTIVATION_RECEIPT_EVIDENCE_CLASS_MISMATCH",
    )
    _require(
        evidence.get("smoke_outcome") == "PASS",
        "ACTIVATION_RECEIPT_SMOKE_NOT_PASS",
    )
    _require(
        receipt.get("manifest_binding") == manifest_binding,
        "ACTIVATION_RECEIPT_MANIFEST_BINDING_MISMATCH",
    )
    return release, manifest, receipt


def _expected_roles(
    manifest: Mapping[str, Any], release: Mapping[str, Any]
) -> dict[str, dict[str, str]]:
    canonical = _mapping(manifest.get("canonical"), "CANONICAL_ROLE_SET_REQUIRED")
    manifest_binding = _mapping(
        _mapping(release.get("artifact_bindings"), "RELEASE_BINDINGS_REQUIRED").get(
            "canonical_manifest"
        ),
        "MANIFEST_BINDING_REQUIRED",
    )
    expected: dict[str, dict[str, str]] = {}
    for role in ROLE_ORDER:
        definition = _mapping(canonical.get(role), f"ROLE_{role.upper()}_REQUIRED")
        filename = definition.get("current_filename")
        _require(isinstance(filename, str), f"ROLE_{role.upper()}_FILENAME_REQUIRED")
        header = definition.get("required_header")
        header_kind = "exact"
        if header is None:
            header = definition.get("required_header_contains")
            header_kind = "contains"
        _require(isinstance(header, str), f"ROLE_{role.upper()}_HEADER_REQUIRED")
        expected_hash = (
            manifest_binding.get("sha256")
            if role == "canonical_manifest"
            else definition.get("sha256")
        )
        _require(
            isinstance(expected_hash, str), f"ROLE_{role.upper()}_HASH_REQUIRED"
        )
        expected[role] = {
            "filename": filename,
            "header": header,
            "header_kind": header_kind,
            "sha256": expected_hash,
        }
    return expected


def _matches_header(path: Path, header: str, header_kind: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    if header_kind == "exact":
        return bool(text.splitlines()) and text.splitlines()[0].strip() == header
    return header in text


def _classify_mirror(
    sources_dir: Path | None, expected_roles: Mapping[str, Mapping[str, str]]
) -> tuple[str, dict[str, str]]:
    if sources_dir is None or not sources_dir.is_dir():
        return MIRROR_UNAVAILABLE, {role: "UNAVAILABLE" for role in expected_roles}

    files = [path for path in sources_dir.iterdir() if path.is_file()]
    role_status: dict[str, str] = {}
    has_stale_role = False
    for role, requirement in expected_roles.items():
        header_matches = [
            path
            for path in files
            if _matches_header(path, requirement["header"], requirement["header_kind"])
        ]
        hash_matches = [
            path for path in header_matches if _sha256(path) == requirement["sha256"]
        ]
        # A manifest can contain a role's header as metadata.  Semantic
        # selection reaches SHA-256 before physical filename, so only two
        # exact source copies are genuinely ambiguous.
        if len(hash_matches) > 1:
            role_status[role] = "CONFLICT"
            continue
        if len(hash_matches) == 1:
            role_status[role] = "MATCH"
            continue
        role_status[role] = "STALE_OR_MISSING"
        has_stale_role = True

    if any(status == "CONFLICT" for status in role_status.values()):
        return MIRROR_CONFLICT, role_status
    if has_stale_role:
        return MIRROR_STALE, role_status
    return MIRROR_MATCHES, role_status


def evaluate_context(
    repository_root: Path, sources_dir: Path | None = None
) -> dict[str, object]:
    """Resolve an active release and classify an optional read-only mirror."""
    release, manifest, _receipt = _resolve_active_release(repository_root)
    expected_roles = _expected_roles(manifest, release)
    mirror_state, mirror_role_status = _classify_mirror(sources_dir, expected_roles)
    active_task = _mapping(
        _mapping(manifest.get("canonical"), "CANONICAL_ROLE_SET_REQUIRED").get(
            "active_task"
        ),
        "ROLE_ACTIVE_TASK_REQUIRED",
    )
    active_release_id = release.get("release_id")
    activation_receipt = release.get("activation_receipt")
    _require(isinstance(active_release_id, str), "ACTIVE_RELEASE_ID_REQUIRED")
    _require(isinstance(activation_receipt, str), "ACTIVATION_RECEIPT_PATH_REQUIRED")
    _require(isinstance(active_task.get("task_id"), str), "ACTIVE_TASK_ID_REQUIRED")
    return {
        "active_release_id": active_release_id,
        "activation_receipt": activation_receipt,
        "active_task_id": active_task["task_id"],
        "active_task_semantic_version": active_task.get("semantic_version"),
        "source_role_count": len(expected_roles),
        "mirror_state": mirror_state,
        "mirror_role_status": mirror_role_status,
        "task_selection_allowed": mirror_state != MIRROR_CONFLICT,
    }


def render_context_text(result: Mapping[str, object]) -> str:
    """Render a path-redacted context card from a resolved context result."""
    lines = [
        "TASK34A_CONTEXT: PASS",
        f"active_release_id={result['active_release_id']}",
        f"activation_receipt={result['activation_receipt']}",
        f"active_task_id={result['active_task_id']}",
        f"source_role_count={result['source_role_count']}",
        f"mirror_state={result['mirror_state']}",
        f"task_selection_allowed={str(result['task_selection_allowed']).lower()}",
    ]
    statuses = _mapping(result["mirror_role_status"], "MIRROR_ROLE_STATUS_REQUIRED")
    for role in ROLE_ORDER:
        lines.append(f"mirror_role.{role}={statuses[role]}")
    return "\n".join(lines) + "\n"
