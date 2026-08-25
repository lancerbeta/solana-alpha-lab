"""Git repository snapshot helpers for the Fast Lane no-Git write fence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


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


def _run_git(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return completed.stdout


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _porcelain_sha256(root: Path) -> str:
    return _sha256_bytes(_run_git(root, "status", "--porcelain=v1", "-z"))


def _head_sha(root: Path) -> str:
    value = _run_git(root, "rev-parse", "HEAD").decode("ascii", errors="ignore").strip()
    if len(value) != 40:
        raise ValueError("GIT_HEAD_UNAVAILABLE")
    return value


def _symbolic_ref(root: Path) -> str:
    symbolic = _run_git(root, "symbolic-ref", "-q", "HEAD").decode(
        "ascii",
        errors="ignore",
    ).strip()
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
    git_dir = root / ".git"
    entries: list[dict[str, str]] = []
    candidates: list[Path] = []
    packed = git_dir / "packed-refs"
    if packed.is_file() and not packed.is_symlink():
        candidates.append(packed)
    refs_root = git_dir / "refs"
    if refs_root.is_dir() and not refs_root.is_symlink():
        candidates.extend(
            sorted(
                path
                for path in refs_root.rglob("*")
                if path.is_file() and not path.is_symlink()
            )
        )
    for path in candidates:
        relative = path.relative_to(git_dir).as_posix()
        entries.append(
            {
                "path": relative,
                "sha256": _sha256_bytes(path.read_bytes()),
            }
        )
    canonical = json.dumps(
        entries,
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
    "RepositoryGitSnapshot",
    "repository_git_snapshot",
    "repository_status_bytes",
]
