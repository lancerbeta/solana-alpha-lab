"""OwnerReviewCursorV1: viewing checkpoint only. Owns no Factory truth."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "smial.owner-review-cursor"
SCHEMA_VERSION = "1.0"
LOCAL_FACTORY_RELATIVE = "local/factory_v1"
CURSOR_FILENAME = "owner_review_cursor_v1.json"
SOURCE_DOMAINS = ("RESEARCH", "OPERATIONS", "SYSTEM")
WATERMARK_KEYS = ("change_available_at", "native_identity")


class ReviewCursorError(ValueError):
    """Fail-closed cursor error. Never used to suppress attention."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def cursor_path(root: Path) -> Path:
    return root / LOCAL_FACTORY_RELATIVE / CURSOR_FILENAME


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def empty_watermark() -> dict[str, str | None]:
    return {"change_available_at": None, "native_identity": None}


def canonical_snapshot_bytes(snapshot: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def snapshot_sha256(snapshot: Mapping[str, Any]) -> str:
    import hashlib

    return hashlib.sha256(canonical_snapshot_bytes(snapshot)).hexdigest()


def _watermark(row: Mapping[str, Any] | None) -> dict[str, str | None]:
    if not isinstance(row, Mapping):
        return empty_watermark()
    available = _text(row.get("change_available_at")) or None
    identity = _text(row.get("native_identity")) or None
    return {"change_available_at": available, "native_identity": identity}


def load_cursor(root: Path) -> dict[str, Any]:
    """Read-only. Missing/corrupt never creates bytes."""

    path = cursor_path(root)
    if not path.is_file():
        return {
            "status": "MISSING",
            "code": "REVIEW_BASELINE_NOT_ESTABLISHED",
            "cursor": None,
        }
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "INVALID", "code": "REVIEW_CURSOR_INVALID", "cursor": None}
    if not isinstance(loaded, dict):
        return {"status": "INVALID", "code": "REVIEW_CURSOR_INVALID", "cursor": None}
    if loaded.get("schema") != SCHEMA or str(loaded.get("schema_version")) != SCHEMA_VERSION:
        return {"status": "INVALID", "code": "REVIEW_CURSOR_INVALID", "cursor": None}
    sources = loaded.get("sources")
    if not isinstance(sources, dict):
        return {"status": "INVALID", "code": "REVIEW_CURSOR_INVALID", "cursor": None}
    normalized: dict[str, dict[str, str | None]] = {}
    for domain in SOURCE_DOMAINS:
        normalized[domain] = _watermark(sources.get(domain) if isinstance(sources.get(domain), dict) else None)
    reviewed_at = _text(loaded.get("reviewed_at")) or None
    digest = _text(loaded.get("review_snapshot_sha256"))
    if not reviewed_at or len(digest) != 64:
        return {"status": "INVALID", "code": "REVIEW_CURSOR_INVALID", "cursor": None}
    return {
        "status": "VALID",
        "code": None,
        "cursor": {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "reviewed_at": reviewed_at,
            "sources": normalized,
            "review_snapshot_sha256": digest,
        },
    }


def persist_cursor(root: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Atomic replace. Creates local/factory_v1 only for this JSON."""

    body = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "reviewed_at": _text(payload.get("reviewed_at")),
        "sources": {
            domain: _watermark((payload.get("sources") or {}).get(domain))
            for domain in SOURCE_DOMAINS
        },
        "review_snapshot_sha256": _text(payload.get("review_snapshot_sha256")),
    }
    if not body["reviewed_at"] or len(body["review_snapshot_sha256"]) != 64:
        raise ReviewCursorError("REVIEW_CURSOR_INVALID")
    directory = root / LOCAL_FACTORY_RELATIVE
    directory.mkdir(parents=True, exist_ok=True)
    path = cursor_path(root)
    encoded = json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp = path.with_name(f".{CURSOR_FILENAME}.{os.getpid()}.tmp")
    try:
        tmp.write_text(encoded, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise ReviewCursorError("REVIEW_CURSOR_UNAVAILABLE") from exc
    return dict(body)


def server_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
