"""Exact remote content SHA256 verification. Size/mtime/upload are never enough."""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable

from solana_alpha_lab.factory.hot90_activation import (
    Hot90ActivationError,
    load_hot90_activation,
    require_drive_writes_enabled,
)
from solana_alpha_lab.factory.offhost_backup import (
    OffhostBackupError,
    OffhostConfig,
    build_rclone_argv,
)

RcloneRunner = Callable[[Sequence[str]], Any]
REMOTE_CONTENT_SHA256_VERIFIED = "REMOTE_CONTENT_SHA256_VERIFIED"


def verify_remote_content_sha256(
    *,
    config: OffhostConfig,
    remote_object: str,
    local_sha256: str,
    runner: RcloneRunner,
    root: Path,
    allow_drive: bool = False,
) -> dict[str, Any]:
    if len(local_sha256) != 64:
        raise OffhostBackupError("LOCAL_SHA256_INVALID")
    activation = load_hot90_activation(root)
    if allow_drive is not True:
        try:
            require_drive_writes_enabled(activation)
        except Hot90ActivationError as exc:
            raise OffhostBackupError("HOT90_DRIVE_WRITES_DISABLED") from exc
    native = _hashsum(config, remote_object, runner, download=False)
    if native == local_sha256:
        return {"terminal": REMOTE_CONTENT_SHA256_VERIFIED, "method": "NATIVE_HASHSUM", "sha256": native}
    downloaded = _hashsum(config, remote_object, runner, download=True)
    if downloaded == local_sha256:
        return {
            "terminal": REMOTE_CONTENT_SHA256_VERIFIED,
            "method": "HASHSUM_DOWNLOAD",
            "sha256": downloaded,
        }
    fallback = _copyto_hash(config, remote_object, runner)
    if fallback == local_sha256:
        return {
            "terminal": REMOTE_CONTENT_SHA256_VERIFIED,
            "method": "COPYTO_HASH_FALLBACK",
            "sha256": fallback,
        }
    raise OffhostBackupError("REMOTE_CONTENT_SHA256_MISMATCH")


def size_or_mtime_never_authorizes_delete() -> str:
    return "SIZE_MTIME_UPLOAD_INSUFFICIENT_FOR_DELETE"


def _hashsum(
    config: OffhostConfig,
    remote_object: str,
    runner: RcloneRunner,
    *,
    download: bool,
) -> str | None:
    extra = ("--download",) if download else ()
    argv = build_rclone_argv(config, "hashsum", "sha256", *extra, remote_object)
    completed = runner(argv)
    if getattr(completed, "returncode", 1) != 0:
        return None
    stdout = getattr(completed, "stdout", "") or ""
    for line in stdout.splitlines():
        token = line.strip().split()
        if token and len(token[0]) == 64 and all(ch in "0123456789abcdef" for ch in token[0]):
            return token[0]
    return None


def _copyto_hash(
    config: OffhostConfig,
    remote_object: str,
    runner: RcloneRunner,
) -> str | None:
    with tempfile.TemporaryDirectory(prefix="hot90-hash-") as tmp:
        local = Path(tmp) / "object.bin"
        argv = build_rclone_argv(config, "copyto", remote_object, str(local))
        completed = runner(argv)
        if getattr(completed, "returncode", 1) != 0 or local.is_file() is False:
            return None
        return hashlib.sha256(local.read_bytes()).hexdigest()
