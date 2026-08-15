"""Create-only byte writes for live raw evidence.

Adopted from TASK-30 `open(..., "xb")`. Identical existing bytes are a
replay; different existing bytes are a hard conflict and leave the file
unchanged.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CREATED = "CREATED"
REPLAY_IDENTICAL = "REPLAY_IDENTICAL"


class ExclusiveWriteError(ValueError):
    """Create-only write could not complete."""


class ExclusiveWriteConflict(ExclusiveWriteError):
    """Path already holds different bytes; the existing file is unchanged."""


def sha256_bytes(body: bytes) -> str:
    if type(body) is not bytes:
        raise ExclusiveWriteError("BODY_NOT_BYTES")
    return hashlib.sha256(body).hexdigest()


def write_exclusive_bytes(path: Path, body: bytes) -> tuple[str, str]:
    """Write `body` creating `path`.

    Returns `(sha256, CREATED | REPLAY_IDENTICAL)`.
    """

    if not isinstance(path, Path):
        raise ExclusiveWriteError("PATH_INVALID")
    if type(body) is not bytes:
        raise ExclusiveWriteError("BODY_NOT_BYTES")
    digest = sha256_bytes(body)
    try:
        with path.open("xb") as handle:
            handle.write(body)
        return digest, CREATED
    except FileExistsError:
        existing = path.read_bytes()
        if existing == body:
            return digest, REPLAY_IDENTICAL
        raise ExclusiveWriteConflict("EXCLUSIVE_WRITE_CONFLICT") from None


def write_exclusive_text(path: Path, text: str, *, encoding: str = "utf-8") -> tuple[str, str]:
    if type(text) is not str:
        raise ExclusiveWriteError("TEXT_NOT_STR")
    return write_exclusive_bytes(path, text.encode(encoding))
