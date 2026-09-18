"""Exact ObservationSchedule artifact for self-contained LIVE cohort releases.

Semantic identity is schedule_sha256(document). Transport identity is the
SHA-256 of the canonical JSON artifact bytes. Do not conflate them.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.observation_schedule import (
    ObservationScheduleError,
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)

OBSERVATION_SCHEDULE_ARTIFACT_NAME = "observation_schedule.json"
RELEASE_SCHEMA_VERSION_LEGACY = "1.0"
RELEASE_SCHEMA_VERSION_SELF_CONTAINED = "1.1"
SOURCE_BUNDLE_SCHEMA_VERSION_SELF_CONTAINED = "1.1"

SCHEDULE_DOCUMENT_MISSING = "SEAL_SCHEDULE_DOCUMENT_MISSING"
SCHEDULE_DOCUMENT_CONFLICT = "SCHEDULE_DOCUMENT_CONFLICT"
SCHEDULE_ARTIFACT_MISSING = "SCHEDULE_ARTIFACT_MISSING"
SCHEDULE_ARTIFACT_HASH_MISMATCH = "SCHEDULE_ARTIFACT_HASH_MISMATCH"
SCHEDULE_SEMANTIC_SHA_MISMATCH = "SCHEDULE_SEMANTIC_SHA_MISMATCH"
SCHEDULE_PARSER_INVALID = "SCHEDULE_PARSER_INVALID"
SCHEDULE_PRODUCER_UNBOUND = "SCHEDULE_PRODUCER_UNBOUND"
CENSUS_SCHEDULE_SHA_MISMATCH = "CENSUS_SCHEDULE_SHA_MISMATCH"


def factory_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def artifact_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def encode_schedule_artifact(
    document: Mapping[str, Any],
    *,
    wanted_sha: str,
    root: Path | None = None,
) -> tuple[dict[str, Any], bytes, str]:
    """Validate, require semantic SHA, return (document, bytes, byte_sha256)."""

    repo = Path(root) if root is not None else factory_repo_root()
    if not isinstance(document, Mapping):
        raise ValueError(SCHEDULE_DOCUMENT_MISSING)
    try:
        validated = validate_observation_schedule(dict(document), root=repo)
    except ObservationScheduleError as exc:
        raise ValueError(SCHEDULE_PARSER_INVALID) from exc
    digest = schedule_sha256(validated)
    if digest != wanted_sha:
        raise ValueError(SCHEDULE_SEMANTIC_SHA_MISMATCH)
    payload = json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return validated, payload, artifact_sha256(payload)


def decode_schedule_artifact(
    payload: bytes,
    *,
    wanted_sha: str,
    expected_byte_sha256: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    byte_sha = artifact_sha256(payload)
    if expected_byte_sha256 is not None and byte_sha != expected_byte_sha256:
        raise ValueError(SCHEDULE_ARTIFACT_HASH_MISMATCH)
    try:
        loaded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(SCHEDULE_PARSER_INVALID) from exc
    validated, _, _ = encode_schedule_artifact(
        loaded, wanted_sha=wanted_sha, root=root
    )
    return validated


def load_ops_schedule_document(
    ops_store: Path, wanted_sha: str
) -> dict[str, Any] | None:
    """Return registered document when ops exposes it; else None."""

    path = Path(ops_store)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        store = ObservationScheduleStore(path.resolve(), readonly=True, immutable=False)
    except ObservationScheduleStoreError:
        return None
    try:
        row = store.get_registered_schedule(wanted_sha)
    except (ObservationScheduleStoreError, sqlite3.Error):
        return None
    finally:
        store.close()
    if not isinstance(row, Mapping):
        return None
    document = row.get("document")
    if not isinstance(document, Mapping):
        return None
    return dict(document)


def agree_schedule_documents(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    wanted_sha: str,
    root: Path | None = None,
) -> dict[str, Any]:
    first, _, _ = encode_schedule_artifact(left, wanted_sha=wanted_sha, root=root)
    try:
        second, _, _ = encode_schedule_artifact(
            right, wanted_sha=wanted_sha, root=root
        )
    except ValueError as exc:
        raise ValueError(SCHEDULE_DOCUMENT_CONFLICT) from exc
    if schedule_sha256(first) != schedule_sha256(second):
        raise ValueError(SCHEDULE_DOCUMENT_CONFLICT)
    return first
