#!/usr/bin/env python3
"""Recompute derived catalog hashes and navigation projections idempotently."""

from __future__ import annotations

import argparse
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
    manifest = yaml.safe_load((ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
    counts = {
        "assets": 0,
        "asset_registries": len(manifest["root_resolver"]["asset_registries"]),
        "schemas": len(manifest["root_resolver"]["schemas"]),
        "queries": len(manifest["root_resolver"]["query_registries"]),
        "lifecycle_registries": len(manifest["root_resolver"]["lifecycle_registries"]),
        "lifecycle_records": 0,
    }
    for registry_relative in manifest["root_resolver"]["asset_registries"]:
        document = yaml.safe_load((ROOT / registry_relative).read_text(encoding="utf-8"))
        counts["assets"] += len(document.get("records", []))
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


def check_drift() -> list[str]:
    problems: list[str] = []
    records = collect_asset_records()
    for asset_id, info in sorted(records.items()):
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
    observed = observed_checkpoint()
    manifest = yaml.safe_load((ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
    if manifest.get("current_checkpoint") != observed:
        problems.append(
            "catalog_current_checkpoint_drift:"
            f"registered={json.dumps(manifest.get('current_checkpoint'), sort_keys=True)}:"
            f"observed={json.dumps(observed, sort_keys=True)}; run harness_sync.py --apply"
        )
    nav = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / "generate_navigation.py"), "--check"],
        capture_output=True,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="repair derived drift")
    mode.add_argument("--check", action="store_true", help="verify derived state only")
    args = parser.parse_args()

    if args.check:
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


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HarnessSyncError as exc:
        print(f"HARNESS_SYNC_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
