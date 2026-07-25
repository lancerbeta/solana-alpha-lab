#!/usr/bin/env python3
"""Compare repository dirty paths against a managed write set. Never mutates Git."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from baton_contract import (  # noqa: E402
    BatonContractError,
    path_in_managed_write_set,
    validate_managed_write_entry,
    validate_repository_relative_path,
)


class BatonScopeError(RuntimeError):
    """Fail-closed dirty-inventory / scope error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def resolved_path_is_inside_root(resolved: Path, root: Path) -> bool:
    """Pure containment: ``resolved`` equals ``root`` or is under it."""
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    return True


def _default_resolve(path: Path) -> Path:
    return path.resolve()


def assert_path_contained(
    path: str,
    *,
    root: Path,
    resolve_path: Callable[[Path], Path] | None = None,
) -> None:
    """Fail closed when ``path`` escapes ``root`` via symlink or resolve.

    ``resolve_path`` is an injectable resolution boundary so containment can be
    proven on any OS without requiring real symlink privileges.
    """
    validate_repository_relative_path(path, allow_terminal_dir_glob=False)
    resolver = resolve_path or _default_resolve
    # When using the real filesystem resolver, normalize root; injectable
    # boundaries keep the caller-supplied root object identity/path.
    repo_root = root.resolve() if resolve_path is None else root
    current = root
    for part in Path(path).parts:
        current = current / part
        check_symlink = resolve_path is not None or current.is_symlink()
        if check_symlink:
            target = resolver(current)
            if not resolved_path_is_inside_root(target, repo_root):
                raise BatonScopeError("symlink_escape", path)
    joined = root / Path(path)
    exists_or_link = resolve_path is not None or joined.exists() or joined.is_symlink()
    if exists_or_link:
        resolved = resolver(joined)
        if not resolved_path_is_inside_root(resolved, repo_root):
            if resolve_path is not None or joined.is_symlink():
                raise BatonScopeError("symlink_escape", path)
            raise BatonScopeError("path_outside_repository", path)


def _assert_path_contained(
    path: str,
    *,
    root: Path,
    resolve_path: Callable[[Path], Path] | None = None,
) -> None:
    assert_path_contained(path, root=root, resolve_path=resolve_path)


def _nul_parts(data: bytes) -> list[bytes]:
    if not data:
        return []
    parts = data.split(b"\0")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    return parts


def _decode_path(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BatonScopeError("path_not_utf8") from exc
    return text.replace("\\", "/")


def parse_porcelain_z(
    data: bytes,
    *,
    root: Path | None = None,
    resolve_path: Callable[[Path], Path] | None = None,
) -> dict[str, list[str]]:
    """Parse ``git status --porcelain=v1 -z -uall`` fail-closed."""
    repo_root = (root or ROOT).resolve() if resolve_path is None else (root or ROOT)
    changed: list[str] = []
    staged: list[str] = []
    untracked: list[str] = []
    raw = _nul_parts(data)
    i = 0
    while i < len(raw):
        entry = raw[i]
        if len(entry) < 3:
            raise BatonScopeError("porcelain_entry_too_short")
        try:
            xy = entry[:2].decode("ascii")
        except UnicodeDecodeError as exc:
            raise BatonScopeError("status_not_ascii") from exc
        path = _decode_path(entry[3:])

        if "R" in xy or "C" in xy:
            # Rename/copy always has a second path field; consume and fail.
            if i + 1 < len(raw):
                _ = _decode_path(raw[i + 1])
                i += 1
            raise BatonScopeError("rename_or_copy_forbidden", f"{xy}:{path}")

        if (
            xy[0] == "U"
            or xy[1] == "U"
            or xy in {"DD", "AA", "AU", "UA", "DU", "UD"}
        ):
            raise BatonScopeError("conflict_status_forbidden", f"{xy}:{path}")

        known = set(" MTADRCU?!")
        if xy[0] not in known or xy[1] not in known:
            raise BatonScopeError("unknown_status", f"{xy}:{path}")

        if xy == "!!":
            i += 1
            continue

        assert_path_contained(path, root=repo_root, resolve_path=resolve_path)

        if xy == "??":
            untracked.append(path)
        else:
            index_status, worktree_status = xy[0], xy[1]
            if index_status not in {" ", "?"}:
                staged.append(path)
            if index_status in {"M", "A", "D", "T"} or worktree_status in {
                "M",
                "A",
                "D",
                "T",
            }:
                changed.append(path)
            elif index_status not in {" ", "?"} or worktree_status not in {" ", "?"}:
                # Any other tracked dirty signal is still a changed path.
                changed.append(path)
        i += 1

    return {
        "changed_files": sorted(set(changed)),
        "staged_files": sorted(set(staged)),
        "untracked_files": sorted(set(untracked)),
    }


def list_dirty_paths(
    *,
    root: Path | None = None,
    porcelain_bytes: bytes | None = None,
) -> dict[str, list[str]]:
    """Return dirty inventory. Never mutates Git or the filesystem."""
    repo_root = (root or ROOT).resolve()
    if porcelain_bytes is None:
        completed = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "-uall"],
            cwd=repo_root,
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            raise BatonScopeError("git_status_failed", str(completed.returncode))
        porcelain_bytes = completed.stdout
    return parse_porcelain_z(porcelain_bytes, root=repo_root)


def evaluate_scope(
    managed_write_set: list[str],
    *,
    root: Path | None = None,
    porcelain_bytes: bytes | None = None,
    inventory: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    for entry in managed_write_set:
        validate_managed_write_entry(entry)
    inv = inventory or list_dirty_paths(root=root, porcelain_bytes=porcelain_bytes)
    all_paths = sorted(
        set(inv["changed_files"])
        | set(inv["staged_files"])
        | set(inv["untracked_files"])
    )
    outside = [
        path
        for path in all_paths
        if not path_in_managed_write_set(path, managed_write_set)
    ]
    return {
        **inv,
        "files_outside_managed_write_set": outside,
        "in_scope": not outside and not inv["staged_files"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--managed-write-set-json", required=True)
    args = parser.parse_args(argv)
    managed = json.loads(Path(args.managed_write_set_json).read_text(encoding="utf-8"))
    if not isinstance(managed, list):
        raise SystemExit("managed_write_set_not_list")
    try:
        result = evaluate_scope(managed)
    except (BatonScopeError, BatonContractError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["in_scope"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
