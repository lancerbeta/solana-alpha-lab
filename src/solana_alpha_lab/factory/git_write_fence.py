"""Git repository snapshot helpers for the Fast Lane no-Git write fence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitFenceError(ValueError):
    """Fail-closed Git metadata error for the no-Git write fence."""


@dataclass(frozen=True, slots=True)
class RepositoryGitSnapshot:
    head_sha: str
    symbolic_ref: str
    porcelain_sha256: str
    index_worktree_sha256: str
    refs_digest_sha256: str
    composite_sha256: str

    def unchanged(self, other: RepositoryGitSnapshot) -> bool:
        return self.composite_sha256 == other.composite_sha256


_DIFF_COMMANDS = frozenset({"diff", "diff-index", "diff-files"})


def _run_git(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
    )
    allowed = {0}
    if args and args[0] in _DIFF_COMMANDS:
        allowed.add(1)
    if args[:2] == ("symbolic-ref", "-q"):
        allowed.add(1)
    if completed.returncode not in allowed:
        raise GitFenceError(f"GIT_COMMAND_FAILED:{args[0]}")
    return completed.stdout


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_dir(root: Path) -> Path:
    value = _run_git(root, "rev-parse", "--git-dir").decode("utf-8", errors="ignore").strip()
    if not value:
        raise GitFenceError("GIT_DIR_UNAVAILABLE")
    path = Path(value)
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    if not path.exists():
        raise GitFenceError("GIT_DIR_UNAVAILABLE")
    return path


def _git_common_dir(root: Path) -> Path:
    value = (
        _run_git(root, "rev-parse", "--git-common-dir")
        .decode("utf-8", errors="ignore")
        .strip()
    )
    if not value:
        raise GitFenceError("GIT_COMMON_DIR_UNAVAILABLE")
    path = Path(value)
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    if not path.exists():
        raise GitFenceError("GIT_COMMON_DIR_UNAVAILABLE")
    return path


def _porcelain_sha256(root: Path) -> str:
    return _sha256_bytes(_run_git(root, "status", "--porcelain=v1", "-z"))


def _head_sha(root: Path) -> str:
    value = _run_git(root, "rev-parse", "HEAD").decode("ascii", errors="ignore").strip()
    if len(value) != 40:
        raise GitFenceError("GIT_HEAD_UNAVAILABLE")
    return value


def _symbolic_ref(root: Path) -> str:
    completed = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        raise GitFenceError("GIT_COMMAND_FAILED:symbolic-ref")
    symbolic = completed.stdout.decode("ascii", errors="ignore").strip()
    if symbolic:
        return symbolic
    abbreviated = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD").decode(
        "ascii",
        errors="ignore",
    ).strip()
    return abbreviated or "HEAD"


def _index_worktree_sha256(root: Path) -> str:
    diff_index = _run_git(root, "diff-index", "HEAD", "--")
    diff_worktree = _run_git(root, "diff", "HEAD")
    diff_cached = _run_git(root, "diff", "--cached", "HEAD")
    combined = b"\0".join((diff_index, diff_worktree, diff_cached))
    return _sha256_bytes(combined)


def _refs_digest_sha256(root: Path) -> str:
    git_dir = _git_dir(root)
    common_dir = _git_common_dir(root)
    refs = _run_git(
        root,
        "for-each-ref",
        "--format=%(objectname) %(refname) %(objecttype)",
    )
    if not refs.strip():
        raise GitFenceError("GIT_REFS_UNAVAILABLE")
    payload = {
        "common_dir_kind": "dir" if common_dir.is_dir() else "other",
        "git_dir_kind": "dir" if git_dir.is_dir() else "file",
        "refs": refs.decode("utf-8", errors="replace").splitlines(),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def repository_git_snapshot(root: Path) -> RepositoryGitSnapshot:
    porcelain_sha256 = _porcelain_sha256(root)
    head_sha = _head_sha(root)
    symbolic_ref = _symbolic_ref(root)
    index_worktree_sha256 = _index_worktree_sha256(root)
    refs_digest_sha256 = _refs_digest_sha256(root)
    composite_payload = {
        "head_sha": head_sha,
        "index_worktree_sha256": index_worktree_sha256,
        "porcelain_sha256": porcelain_sha256,
        "refs_digest_sha256": refs_digest_sha256,
        "symbolic_ref": symbolic_ref,
    }
    composite_sha256 = _sha256_bytes(
        json.dumps(
            composite_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return RepositoryGitSnapshot(
        head_sha=head_sha,
        symbolic_ref=symbolic_ref,
        porcelain_sha256=porcelain_sha256,
        index_worktree_sha256=index_worktree_sha256,
        refs_digest_sha256=refs_digest_sha256,
        composite_sha256=composite_sha256,
    )


def repository_status_bytes(root: Path) -> bytes:
    """Backward-compatible porcelain status bytes for legacy callers."""

    return _run_git(root, "status", "--porcelain=v1", "-z")


__all__ = [
    "GitFenceError",
    "RepositoryGitSnapshot",
    "repository_git_snapshot",
    "repository_status_bytes",
]
