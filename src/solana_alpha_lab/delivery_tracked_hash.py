"""SHA-256 of Git-normalized tracked bytes, not a Windows working-tree copy."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


class TrackedHashError(ValueError):
    """Raised when a tracked-file digest cannot be bound to Git bytes."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_tracked_path(root: Path, relative: str) -> str:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise TrackedHashError("TRACKED_PATH_UNSAFE")
    posix = Path(relative).as_posix()
    for spec in (f":{posix}", f"HEAD:{posix}"):
        completed = subprocess.run(
            ["git", "show", spec],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
        )
        if completed.returncode == 0:
            return sha256_bytes(completed.stdout)
    path = root / posix
    if not path.is_file():
        raise TrackedHashError("TRACKED_PATH_MISSING")
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
