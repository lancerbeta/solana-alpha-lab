#!/usr/bin/env python3
"""Recompute derived catalog hashes and navigation projections idempotently."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (str(SCRIPTS), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from validate_baseline import (  # noqa: E402
    CanonicalRepositoryBytesError,
    canonical_repository_content,
)

MANIFEST_RELATIVE = "catalog/catalog_manifest.yaml"
ASSET_REGISTRIES = (
    "catalog/assets/core.yaml",
    "catalog/assets/lifecycle.yaml",
)
NAV_OUTPUTS = (
    "docs/PROJECT_MAP.md",
    "catalog/generated/asset_edges.json",
    "docs/OPERATOR_NAVIGATION.md",
)


class HarnessSyncError(RuntimeError):
    """Bounded derived-hash sync cannot be satisfied."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise HarnessSyncError(code)


def _rewrite_block(text: str, asset_id: str, new_sha: str) -> str:
    """Rewrite the sha256 inside the exact asset block; fail closed on ambiguity."""
    block_pattern = re.compile(
        r"(^- asset_id: "
        + re.escape(asset_id)
        + r"(?:\n(?!- asset_id: ).*)*?\n)(  integrity:(?: \{kind: sha256, sha256: [0-9a-f]{64}\}|\n    kind: sha256\n    sha256: [0-9a-f]{64}))",
        re.MULTILINE,
    )
    matches = list(block_pattern.finditer(text))
    _require(len(matches) == 1, f"ASSET_BLOCK_NOT_UNIQUE:{asset_id}")
    match = matches[0]
    old_field = match.group(2)
    if old_field.startswith("  integrity: {"):
        new_field = f"  integrity: {{kind: sha256, sha256: {new_sha}}}"
    else:
        new_field = "  integrity:\n    kind: sha256\n    sha256: " + new_sha
    return text[: match.start(2)] + new_field + text[match.end(2) :]


def _current_block_sha(text: str, asset_id: str) -> str | None:
    block_pattern = re.compile(
        r"^- asset_id: "
        + re.escape(asset_id)
        + r"(?:\n(?!- asset_id: ).*)*?\n  integrity:(?: \{kind: sha256, sha256: ([0-9a-f]{64})\}|\n    kind: sha256\n    sha256: ([0-9a-f]{64}))",
        re.MULTILINE,
    )
    matches = list(block_pattern.finditer(text))
    _require(len(matches) == 1, f"ASSET_BLOCK_NOT_UNIQUE:{asset_id}")
    return matches[0].group(1) or matches[0].group(2)


def collect_asset_records() -> dict[str, dict[str, Any]]:
    """Map asset_id -> {registry, repository_path} for sha256 git_path assets."""
    out: dict[str, dict[str, Any]] = {}
    for registry_relative in ASSET_REGISTRIES:
        registry_file = ROOT / registry_relative
        if not registry_file.is_file():
            continue
        document = yaml.safe_load(registry_file.read_text(encoding="utf-8"))
        for record in document.get("records", []):
            integrity = record.get("integrity") or {}
            location = record.get("location") or {}
            if integrity.get("kind") != "sha256":
                continue
            if location.get("kind") != "git_path":
                continue
            asset_id = record["asset_id"]
            relative = location.get("repository_path")
            _require(
                isinstance(relative, str) and bool(relative),
                f"ASSET_PATH_MISSING:{asset_id}",
            )
            out[asset_id] = {
                "registry": registry_relative,
                "repository_path": relative,
            }
    return out


def desired_sha256(repository_path: str) -> str:
    """Hash exactly the bytes the integrity guard reads for this path."""
    try:
        resolved = canonical_repository_content(
            repository_path,
            allow_worktree_candidate=True,
        )
    except CanonicalRepositoryBytesError as exc:
        raise HarnessSyncError(f"CANONICAL_READ_FAILED:{repository_path}:{exc}") from exc
    return resolved.sha256


def apply_asset_hashes(changed_files: set[str]) -> list[str]:
    updates: list[str] = []
    records = collect_asset_records()
    by_registry: dict[str, dict[str, str]] = {}
    for asset_id, info in sorted(records.items()):
        target = ROOT / info["repository_path"]
        if not target.is_file():
            # Generated views may legitimately not exist before the first nav
            # run; the navigation generator below creates them.
            continue
        by_registry.setdefault(info["registry"], {})[asset_id] = desired_sha256(
            info["repository_path"]
        )
    for registry_relative, desired_map in sorted(by_registry.items()):
        registry_file = ROOT / registry_relative
        text = registry_file.read_text(encoding="utf-8")
        original_text = text
        touched: list[str] = []
        for asset_id in sorted(desired_map):
            current = _current_block_sha(text, asset_id)
            desired = desired_map[asset_id]
            if current != desired:
                text = _rewrite_block(text, asset_id, desired)
                touched.append(f"{asset_id}:{current[:8]}->{desired[:8]}")
        if text != original_text:
            registry_file.write_bytes(text.encode("utf-8"))
            changed_files.add(registry_relative)
            preview = "; ".join(touched[:4])
            suffix = "..." if len(touched) > 4 else ""
            updates.append(
                f"{registry_relative}: updated {len(touched)} hash(es) [{preview}{suffix}]"
            )
    return updates


def observed_checkpoint() -> dict[str, int]:
    """Mirror validate_catalog.observed_catalog_checkpoint semantics exactly."""
    manifest = yaml.safe_load((ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
    counts = {
        "assets": 0,
        "asset_registries": len(manifest["root_resolver"]["asset_registries"]),
        "schemas": len(manifest["root_resolver"]["schemas"]),
        "queries": 0,
        "lifecycle_registries": len(manifest["root_resolver"]["lifecycle_registries"]),
        "lifecycle_records": 0,
    }
    for registry_relative in manifest["root_resolver"]["asset_registries"]:
        document = yaml.safe_load((ROOT / registry_relative).read_text(encoding="utf-8"))
        counts["assets"] += len(document.get("records", []))
    for query_relative in manifest["root_resolver"]["query_registries"]:
        document = yaml.safe_load((ROOT / query_relative).read_text(encoding="utf-8"))
        counts["queries"] += len(document.get("recipes", []))
    for registry_relative in manifest["root_resolver"]["lifecycle_registries"]:
        document = yaml.safe_load((ROOT / registry_relative).read_text(encoding="utf-8"))
        counts["lifecycle_records"] += len(document.get("records", []))
    return counts


def update_manifest_checkpoint(changed_files: set[str]) -> list[str]:
    observed = observed_checkpoint()
    manifest_file = ROOT / MANIFEST_RELATIVE
    manifest_text = manifest_file.read_text(encoding="utf-8")
    manifest = yaml.safe_load(manifest_text)
    current = manifest.get("current_checkpoint") or {}
    if current == observed:
        return []
    lines = manifest_text.splitlines()
    out_lines: list[str] = []
    in_checkpoint = False
    checkpoint_indent = ""
    replaced: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not in_checkpoint and stripped == "current_checkpoint:":
            in_checkpoint = True
            checkpoint_indent = line[: len(line) - len(line.lstrip())]
            out_lines.append(line)
            continue
        if in_checkpoint:
            match = re.match(r"^(\s+)([a-z_]+): (\d+)\s*$", line)
            if match and len(match.group(1)) > len(checkpoint_indent) and match.group(2) in observed:
                out_lines.append(f"{match.group(1)}{match.group(2)}: {observed[match.group(2)]}")
                replaced.add(match.group(2))
                continue
            in_checkpoint = False
        out_lines.append(line)
    _require(
        set(observed).issubset(replaced),
        f"CHECKPOINT_KEYS_NOT_FOUND:{sorted(set(observed) - replaced)}",
    )
    manifest_file.write_bytes(("\n".join(out_lines) + "\n").encode("utf-8"))
    changed_files.add(MANIFEST_RELATIVE)
    changed = {
        key: {"from": current.get(key), "to": value}
        for key, value in observed.items()
        if current.get(key) != value
    }
    return [f"{MANIFEST_RELATIVE}: counters changed {json.dumps(changed, sort_keys=True)}"]


def run_nav_generator() -> list[str]:
    env_copy = {**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / "generate_navigation.py"), "--write"],
        capture_output=True,
        cwd=str(ROOT),
        env=env_copy,
    )
    output = result.stdout.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
        raise HarnessSyncError(
            "NAV_GENERATOR_FAILED: catalog itself does not validate; "
            "fix primary records before syncing derived hashes"
        )
    return [f"navigation generator: {output}"]


def read_staged_paths() -> set[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    _require(completed.returncode == 0, "STAGED_PATHS_UNAVAILABLE")
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def drift_scopes_for_paths(paths: set[str]) -> dict[str, bool]:
    if not paths:
        return {"assets": False, "checkpoint": False, "navigation": False}
    records = collect_asset_records()
    repository_paths = {info["repository_path"] for info in records.values()}
    registries = set(ASSET_REGISTRIES)
    nav_outputs = set(NAV_OUTPUTS)
    return {
        "assets": bool(paths & (registries | repository_paths)),
        "checkpoint": bool(paths & (registries | {MANIFEST_RELATIVE})),
        "navigation": bool(paths & (nav_outputs | registries | repository_paths)),
    }


def check_drift(*, scoped_paths: set[str] | None = None) -> list[str]:
    scopes = (
        {"assets": True, "checkpoint": True, "navigation": True}
        if scoped_paths is None
        else drift_scopes_for_paths(scoped_paths)
    )
    if not any(scopes.values()):
        return []

    problems: list[str] = []
    records = collect_asset_records()
    if scopes["assets"]:
        for asset_id, info in sorted(records.items()):
            if scoped_paths is not None:
                if info["registry"] not in scoped_paths and info["repository_path"] not in scoped_paths:
                    continue
            try:
                desired = desired_sha256(info["repository_path"])
            except HarnessSyncError as exc:
                problems.append(str(exc))
                continue
            registry_file = ROOT / info["registry"]
            current = _current_block_sha(registry_file.read_text(encoding="utf-8"), asset_id)
            if current != desired:
                problems.append(
                    f"sha256_mismatch:{asset_id}:{info['registry']}; run harness_sync.py --apply"
                )
    if scopes["checkpoint"]:
        observed = observed_checkpoint()
        manifest = yaml.safe_load((ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
        if manifest.get("current_checkpoint") != observed:
            problems.append(
                "catalog_current_checkpoint_drift:"
                f"registered={json.dumps(manifest.get('current_checkpoint'), sort_keys=True)}:"
                f"observed={json.dumps(observed, sort_keys=True)}; run harness_sync.py --apply"
            )
    if scopes["navigation"]:
        nav = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "generate_navigation.py"), "--check"],
            capture_output=True,
            env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if nav.returncode != 0:
            detail = nav.stdout.decode("utf-8", errors="replace").strip().splitlines()[-1:]
            problems.append(
                "navigation_projection_stale"
                + (f":{detail[0]}" if detail else "")
                + "; run harness_sync.py --apply"
            )
    return problems


def apply_sync() -> dict[str, Any]:
    changed_files: set[str] = set()
    updates: list[str] = []
    # Pass 1: fix asset hashes, then regenerate views, then re-fix the view
    # hashes that the regeneration itself changed.
    updates += apply_asset_hashes(changed_files)
    updates += update_manifest_checkpoint(changed_files)
    updates += run_nav_generator()
    updates += apply_asset_hashes(changed_files)
    updates += run_nav_generator()
    changed_files.update(NAV_OUTPUTS)

    # Idempotency proof: a second full pass must be a byte-level no-op.
    second_changed: set[str] = set()
    second_before = {
        relative: (ROOT / relative).read_bytes()
        for relative in ("catalog/catalog_manifest.yaml", *NAV_OUTPUTS)
    }
    second_updates = apply_asset_hashes(second_changed)
    second_updates += update_manifest_checkpoint(second_changed)
    second_updates += run_nav_generator()
    # The generator prints UNCHANGED on a stable pass; only treat actual
    # rewrites as drift. Compare bytes instead of parsing its output.
    _require(not second_changed, "NON_IDEMPOTENT_APPLY:" + "; ".join(second_updates))
    for relative, before in second_before.items():
        _require(
            (ROOT / relative).read_bytes() == before,
            f"NON_IDEMPOTENT_APPLY:{relative}",
        )

    return {
        "mode": "apply",
        "updates": updates,
        "changed_files": sorted(changed_files),
        "idempotency": "PASS_SECOND_PASS_NOOP",
    }


def _run_git(args: list[str], root: Path | None = None) -> bytes:
    completed = subprocess.run(
        args,
        cwd=str(root or ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise HarnessSyncError("GIT_READ_FAILED")
    return completed.stdout


def _parse_task_frontmatter(path: Path, task_id: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HarnessSyncError("TASK_NOT_FOUND") from exc
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if match is None:
        raise HarnessSyncError("TASK_NOT_FOUND")
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict) or metadata.get("task_id") != task_id:
        raise HarnessSyncError("TASK_NOT_FOUND")
    return metadata


def resolve_task_contract(task_id: str, *, contract: str | None = None) -> tuple[str, dict[str, Any]]:
    if contract is not None:
        relative = contract.replace("\\", "/")
        metadata = _parse_task_frontmatter(ROOT / relative, task_id)
        return relative, metadata
    matches: list[tuple[str, dict[str, Any]]] = []
    tasks_dir = ROOT / "docs/tasks"
    if not tasks_dir.is_dir():
        raise HarnessSyncError("TASK_NOT_FOUND")
    for path in sorted(tasks_dir.glob("*.md")):
        try:
            metadata = _parse_task_frontmatter(path, task_id)
        except HarnessSyncError:
            continue
        matches.append((path.relative_to(ROOT).as_posix(), metadata))
    if len(matches) != 1:
        raise HarnessSyncError("TASK_NOT_FOUND")
    return matches[0]


def _managed_write_set(metadata: dict[str, Any]) -> list[str]:
    managed = metadata.get("managed_write_set")
    if not isinstance(managed, list) or not managed:
        raise HarnessSyncError("MANAGED_WRITE_SET_INVALID")
    normalized: list[str] = []
    for item in managed:
        if not isinstance(item, str) or not item:
            raise HarnessSyncError("MANAGED_WRITE_SET_INVALID")
        normalized.append(item.replace("\\", "/"))
    if len(set(normalized)) != len(normalized):
        raise HarnessSyncError("MANAGED_WRITE_SET_INVALID")
    return normalized


def _delivery_evidence_paths(metadata: dict[str, Any]) -> tuple[str, str, str]:
    requirements = metadata.get("context_requirements")
    if not isinstance(requirements, dict):
        raise HarnessSyncError("DELIVERY_EVIDENCE_PATHS_INCOMPLETE")
    paths_by_role = requirements.get("exact_role_paths")
    if not isinstance(paths_by_role, dict):
        raise HarnessSyncError("DELIVERY_EVIDENCE_PATHS_INCOMPLETE")
    delivery_paths = paths_by_role.get("DELIVERY_EVIDENCE")
    if not isinstance(delivery_paths, list) or len(delivery_paths) != 3:
        raise HarnessSyncError("DELIVERY_EVIDENCE_PATHS_INCOMPLETE")
    completion = review = fit = None
    for relative in delivery_paths:
        if not isinstance(relative, str):
            raise HarnessSyncError("DELIVERY_EVIDENCE_PATHS_INCOMPLETE")
        path = ROOT / relative.replace("\\", "/")
        if not path.is_file():
            raise HarnessSyncError("DELIVERY_EVIDENCE_PATHS_INCOMPLETE")
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema = payload.get("schema")
        if schema == "smial.delivery-completion-evidence":
            completion = relative.replace("\\", "/")
        elif schema == "smial.delivery-independent-review-evidence":
            review = relative.replace("\\", "/")
        elif schema == "smial.delivery-harness-factory-fit":
            fit = relative.replace("\\", "/")
    if not (completion and review and fit):
        raise HarnessSyncError("DELIVERY_EVIDENCE_PATHS_INCOMPLETE")
    return completion, review, fit


def _git_binding(metadata: dict[str, Any]) -> tuple[str, str]:
    binding = metadata.get("git_binding")
    if not isinstance(binding, dict):
        raise HarnessSyncError("GIT_BINDING_INVALID")
    expected_base = binding.get("expected_base")
    expected_branch = binding.get("expected_branch")
    if not (
        isinstance(expected_base, str)
        and re.fullmatch(r"[0-9a-f]{40}", expected_base)
        and isinstance(expected_branch, str)
        and expected_branch
    ):
        raise HarnessSyncError("GIT_BINDING_INVALID")
    return expected_base, expected_branch


def _path_in_managed_write_set(path: str, managed: list[str]) -> bool:
    from owner_attention_gate import path_in_managed_write_set

    return path_in_managed_write_set(path, managed)


def _decode_git_name_status(value: bytes) -> list[tuple[str, str]]:
    from owner_attention_gate import decode_git_name_status

    return decode_git_name_status(value)


def _canonical_json_bytes(value: Any) -> bytes:
    from owner_attention_gate import canonical_json_bytes

    return canonical_json_bytes(value)


def _sha256_bytes(value: bytes) -> str:
    from owner_attention_gate import sha256_bytes

    return sha256_bytes(value)


def _delivery_inventory_sha256(
    *,
    expected_base: str,
    head: str,
    excluded_paths: set[str],
) -> str:
    from owner_attention_gate import delivery_inventory_sha256

    return delivery_inventory_sha256(
        ROOT,
        expected_base=expected_base,
        head=head,
        excluded_paths=excluded_paths,
        runner=_run_git,
    )


def build_implementation_bindings(
    *,
    expected_base: str,
    head: str,
    managed: list[str],
    excluded: set[str],
) -> dict[str, str]:
    output = _run_git(
        ["git", "diff", "--name-status", "--no-renames", "-z", f"{expected_base}...{head}"]
    )
    bindings: dict[str, str] = {}
    for status, path in _decode_git_name_status(output):
        if path in excluded:
            continue
        if status == "D":
            continue
        if not _path_in_managed_write_set(path, managed):
            raise HarnessSyncError(f"BINDING_SCOPE_VIOLATION:{path}")
        candidate = ROOT / path
        if candidate.is_file():
            payload = candidate.read_bytes()
        else:
            payload = _run_git(["git", "show", f"{head}:{path}"])
        bindings[path] = hashlib.sha256(payload).hexdigest()
    if not bindings:
        raise HarnessSyncError("BINDING_INVENTORY_EMPTY")
    return dict(sorted(bindings.items()))


def _assert_bind_allowed(completion_path: str) -> None:
    try:
        ahead = int(_run_git(["git", "rev-list", "--count", f"origin/main..HEAD"]).decode("ascii").strip())
    except ValueError as exc:
        raise HarnessSyncError("EVIDENCE_FROZEN") from exc
    if ahead == 0:
        raise HarnessSyncError("EVIDENCE_FROZEN")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarnessSyncError("DELIVERY_EVIDENCE_INVALID")
    return payload


def compute_evidence_chain(
    *,
    task_id: str,
    contract: str | None = None,
    head: str | None = None,
) -> dict[str, Any]:
    _, metadata = resolve_task_contract(task_id, contract=contract)
    expected_base, _branch = _git_binding(metadata)
    if head is None:
        head = _run_git(["git", "rev-parse", "HEAD"]).decode("ascii").strip()
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise HarnessSyncError("HEAD_INVALID")
    managed = _managed_write_set(metadata)
    completion_path, review_path, fit_path = _delivery_evidence_paths(metadata)
    excluded = {completion_path, review_path, fit_path}
    bindings = build_implementation_bindings(
        expected_base=expected_base,
        head=head,
        managed=managed,
        excluded=excluded,
    )
    bindings_sha = _sha256_bytes(_canonical_json_bytes(bindings))
    inventory_sha = _delivery_inventory_sha256(
        expected_base=expected_base,
        head=head,
        excluded_paths=excluded,
    )
    return {
        "task_id": task_id,
        "expected_base": expected_base,
        "head": head,
        "completion_path": completion_path,
        "review_path": review_path,
        "fit_path": fit_path,
        "implementation_bindings": bindings,
        "reviewed_bindings_sha256": bindings_sha,
        "reviewed_inventory_sha256": inventory_sha,
    }


def verify_evidence_chain(*, task_id: str, contract: str | None = None, head: str | None = None) -> list[str]:
    expected = compute_evidence_chain(task_id=task_id, contract=contract, head=head)
    problems: list[str] = []
    completion = _load_json(ROOT / expected["completion_path"])
    review = _load_json(ROOT / expected["review_path"])
    fit = _load_json(ROOT / expected["fit_path"])
    if completion.get("implementation_bindings") != expected["implementation_bindings"]:
        problems.append("implementation_bindings_mismatch")
    if completion.get("base_main") != expected["expected_base"]:
        problems.append("base_main_mismatch")
    if review.get("reviewed_bindings_sha256") != expected["reviewed_bindings_sha256"]:
        problems.append("review_bindings_sha_mismatch")
    if review.get("reviewed_inventory_sha256") != expected["reviewed_inventory_sha256"]:
        problems.append("review_inventory_sha_mismatch")
    if fit.get("reviewed_bindings_sha256") != expected["reviewed_bindings_sha256"]:
        problems.append("fit_bindings_sha_mismatch")
    if fit.get("reviewed_inventory_sha256") != expected["reviewed_inventory_sha256"]:
        problems.append("fit_inventory_sha_mismatch")
    problems.extend(
        _verify_nested_evidence_hashes(
            completion=completion,
            review_path=expected["review_path"],
            fit_path=expected["fit_path"],
        )
    )
    return problems


def _verify_nested_evidence_hashes(
    *,
    completion: dict[str, Any],
    review_path: str,
    fit_path: str,
) -> list[str]:
    problems: list[str] = []
    review_sha = hashlib.sha256((ROOT / review_path).read_bytes()).hexdigest()
    fit_sha = hashlib.sha256((ROOT / fit_path).read_bytes()).hexdigest()
    review_binding = completion.get("validation", {}).get("independent_review", {})
    fit_binding = completion.get("factory_fit", {})
    if not isinstance(review_binding, dict) or review_binding.get("sha256") != review_sha:
        problems.append("completion_review_sha_mismatch")
    if not isinstance(fit_binding, dict) or fit_binding.get("sha256") != fit_sha:
        problems.append("completion_fit_sha_mismatch")
    return problems


def verify_evidence_chain_internal(completion_path: str) -> list[str]:
    completion = _load_json(ROOT / completion_path)
    bindings = completion.get("implementation_bindings")
    if not isinstance(bindings, dict) or not bindings:
        return ["implementation_bindings_missing"]
    bindings_sha = _sha256_bytes(_canonical_json_bytes(dict(sorted(bindings.items()))))
    review_binding = completion.get("validation", {}).get("independent_review", {})
    fit_binding = completion.get("factory_fit", {})
    if not isinstance(review_binding, dict) or not isinstance(review_binding.get("path"), str):
        return ["completion_review_path_missing"]
    if not isinstance(fit_binding, dict) or not isinstance(fit_binding.get("path"), str):
        return ["completion_fit_path_missing"]
    review_path = review_binding["path"].replace("\\", "/")
    fit_path = fit_binding["path"].replace("\\", "/")
    review = _load_json(ROOT / review_path)
    fit = _load_json(ROOT / fit_path)
    problems: list[str] = []
    if review.get("reviewed_bindings_sha256") != bindings_sha:
        problems.append("review_bindings_sha_mismatch")
    if fit.get("reviewed_bindings_sha256") != bindings_sha:
        problems.append("fit_bindings_sha_mismatch")
    if review.get("reviewed_inventory_sha256") != fit.get("reviewed_inventory_sha256"):
        problems.append("review_fit_inventory_sha_mismatch")
    for path, expected_sha in bindings.items():
        if not isinstance(path, str) or not isinstance(expected_sha, str):
            problems.append("implementation_binding_invalid")
            continue
        candidate = ROOT / path
        if not candidate.is_file():
            problems.append(f"binding_target_missing:{path}")
            continue
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_sha:
            problems.append(f"binding_target_hash_mismatch:{path}")
    problems.extend(
        _verify_nested_evidence_hashes(
            completion=completion,
            review_path=review_path,
            fit_path=fit_path,
        )
    )
    return problems


def apply_evidence_chain(*, task_id: str, contract: str | None = None, head: str | None = None) -> dict[str, Any]:
    expected = compute_evidence_chain(task_id=task_id, contract=contract, head=head)
    _assert_bind_allowed(expected["completion_path"])
    review_path = ROOT / expected["review_path"]
    fit_path = ROOT / expected["fit_path"]
    completion_path = ROOT / expected["completion_path"]
    review = _load_json(review_path)
    fit = _load_json(fit_path)
    completion = _load_json(completion_path)
    review["reviewed_bindings_sha256"] = expected["reviewed_bindings_sha256"]
    review["reviewed_inventory_sha256"] = expected["reviewed_inventory_sha256"]
    fit["reviewed_bindings_sha256"] = expected["reviewed_bindings_sha256"]
    fit["reviewed_inventory_sha256"] = expected["reviewed_inventory_sha256"]
    _write_json(review_path, review)
    _write_json(fit_path, fit)
    review_sha = hashlib.sha256(review_path.read_bytes()).hexdigest()
    fit_sha = hashlib.sha256(fit_path.read_bytes()).hexdigest()
    completion["implementation_bindings"] = expected["implementation_bindings"]
    completion["base_main"] = expected["expected_base"]
    if not isinstance(completion.get("factory_fit"), dict):
        raise HarnessSyncError("DELIVERY_EVIDENCE_INVALID")
    if not isinstance(completion.get("validation"), dict):
        raise HarnessSyncError("DELIVERY_EVIDENCE_INVALID")
    if not isinstance(completion["validation"].get("independent_review"), dict):
        raise HarnessSyncError("DELIVERY_EVIDENCE_INVALID")
    completion["factory_fit"]["sha256"] = fit_sha
    completion["validation"]["independent_review"]["sha256"] = review_sha
    _write_json(completion_path, completion)
    return {
        "mode": "bind-evidence-apply",
        "task_id": task_id,
        "head": expected["head"],
        "expected_base": expected["expected_base"],
        "changed_files": sorted(
            {expected["completion_path"], expected["review_path"], expected["fit_path"]}
        ),
        "binding_count": len(expected["implementation_bindings"]),
        "reviewed_bindings_sha256": expected["reviewed_bindings_sha256"],
        "reviewed_inventory_sha256": expected["reviewed_inventory_sha256"],
    }


def verify_all_delivered_evidence() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for completion_file in sorted((ROOT / "docs/evidence").glob("**/a1_delivery_completion_evidence_v1.json")):
        relative = completion_file.relative_to(ROOT).as_posix()
        payload = _load_json(completion_file)
        task_id = payload.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            results.append({"path": relative, "status": "SKIP", "reason": "missing_task_id"})
            continue
        try:
            problems = verify_evidence_chain_internal(relative)
        except HarnessSyncError as exc:
            results.append({"path": relative, "task_id": task_id, "status": "ERROR", "reason": str(exc)})
            continue
        results.append(
            {
                "path": relative,
                "task_id": task_id,
                "status": "PASS" if not problems else "MISMATCH",
                "problems": problems,
            }
        )
    passed = sum(1 for item in results if item.get("status") == "PASS")
    mismatched = sum(1 for item in results if item.get("status") == "MISMATCH")
    return {
        "mode": "bind-evidence-verify-all-delivered",
        "total": len(results),
        "passed": passed,
        "mismatched": mismatched,
        "results": results,
    }


def bind_evidence_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Bind delivery-evidence hash chains for task closure.")
    parser.add_argument("--task-id", help="Exact task_id from the task contract")
    parser.add_argument("--contract", help="Optional task contract path under the repository root")
    parser.add_argument("--head", help="Optional explicit head OID (defaults to HEAD)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="write bound delivery-evidence chain")
    mode.add_argument("--verify", action="store_true", help="verify bound delivery-evidence chain")
    mode.add_argument(
        "--verify-all-delivered",
        action="store_true",
        help="read-only audit of historical delivery completion chains",
    )
    args = parser.parse_args(argv)
    if args.verify_all_delivered:
        print(json.dumps(verify_all_delivered_evidence(), indent=2))
        return 0
    if not args.task_id:
        print("HARNESS_SYNC_ERROR: --task-id is required", file=sys.stderr)
        return 2
    if args.verify:
        problems = verify_evidence_chain(
            task_id=args.task_id, contract=args.contract, head=args.head
        )
        if problems:
            for problem in problems:
                print(f"BIND_EVIDENCE_DRIFT: {problem}", file=sys.stderr)
            return 1
        print("HARNESS_SYNC_BIND_EVIDENCE: PASS")
        return 0
    result = apply_evidence_chain(task_id=args.task_id, contract=args.contract, head=args.head)
    print(json.dumps(result, indent=2))
    return 0


def sync_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="repair derived drift")
    mode.add_argument("--check", action="store_true", help="verify derived state only")
    parser.add_argument(
        "--paths-from-staging",
        action="store_true",
        help="with --check, verify drift only for git-staged paths",
    )
    args = parser.parse_args(argv)

    if args.check:
        if args.paths_from_staging:
            problems = check_drift(scoped_paths=read_staged_paths())
        else:
            problems = check_drift()
        if problems:
            for problem in problems:
                print(f"DERIVED_HASH_DRIFT: {problem}", file=sys.stderr)
            return 1
        print("HARNESS_SYNC_CHECK: PASS")
        return 0

    result = apply_sync()
    print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "bind-evidence":
        return bind_evidence_main(argv[1:])
    return sync_main(argv)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HarnessSyncError as exc:
        print(f"HARNESS_SYNC_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
