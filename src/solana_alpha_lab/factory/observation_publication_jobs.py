"""Publication-job journal lifecycle for ObservationSchedule.

Routine tick repair reads only ``open/``. Proven terminals become compact
receipts in ``completed/``. Historical full JSON is moved byte-identical into
``legacy_full/`` and is never deleted by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc

JOBS_RELATIVE = "datasets/publication_jobs"
OPEN_DIRNAME = "open"
COMPLETED_DIRNAME = "completed"
LEGACY_FULL_DIRNAME = "legacy_full"
STAGE_MARKER = "MARKER"
STAGE_COMPLETE = "COMPLETE"
CLASS_OPEN = "OPEN"
CLASS_PROVEN_COMPLETED = "PROVEN_COMPLETED"
CLASS_AMBIGUOUS = "AMBIGUOUS"
HOT_PATH_FORBIDDEN = "PUBLICATION_HOT_PATH_READ_FORBIDDEN"
AMBIGUOUS_BLOCKS_APPLY = "PUBLICATION_JOB_MIGRATION_AMBIGUOUS"
OPEN_JOB_CONFLICT = "OPEN_JOB_CONFLICT"
COMPLETED_RECEIPT_CONFLICT = "COMPLETED_RECEIPT_CONFLICT"
LEGACY_FULL_BYTE_MISMATCH = "LEGACY_FULL_BYTE_MISMATCH"
COMPACT_RECEIPT_UNCONSTRUCTABLE = "COMPACT_RECEIPT_UNCONSTRUCTABLE"
CONTENT_SHA256_INVALID = "CONTENT_SHA256_INVALID"
CONTENT_IDENTITY_COLLISION = "CONTENT_IDENTITY_COLLISION"
SOURCE_CHANGED_AFTER_PLAN = "SOURCE_CHANGED_AFTER_PLAN"
COLLECTOR_NOT_PAUSED = "COLLECTOR_NOT_PAUSED"
COLLECTOR_STORE_MISSING = "COLLECTOR_STORE_MISSING"
LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION = (
    "LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION"
)
STAGE_ARTIFACTS = "ARTIFACTS"
FAT_RESUME_CAPTURE_MAX_BYTES = 512 * 1024
FAT_ARTIFACTS_RESUME_NOT_LEGACY_FAT = "FAT_ARTIFACTS_RESUME_NOT_LEGACY_FAT"
FAT_ARTIFACTS_RESUME_UNSUPPORTED_STAGE = "FAT_ARTIFACTS_RESUME_UNSUPPORTED_STAGE"
FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH = "FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH"
FAT_ARTIFACTS_RESUME_HASH_MISMATCH = "FAT_ARTIFACTS_RESUME_HASH_MISMATCH"
FAT_ARTIFACTS_RESUME_ARTIFACT_MISSING = "FAT_ARTIFACTS_RESUME_ARTIFACT_MISSING"
FAT_ARTIFACTS_RESUME_PAYLOAD_TOO_LARGE = "FAT_ARTIFACTS_RESUME_PAYLOAD_TOO_LARGE"
FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID = "FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID"
FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN = (
    "FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN"
)
FAT_ARTIFACTS_RESUME_SCHEDULE_MISSING = "FAT_ARTIFACTS_RESUME_SCHEDULE_MISSING"
FAT_ARTIFACTS_RESUME_CONTENT_REQUIRED = "FAT_ARTIFACTS_RESUME_CONTENT_REQUIRED"
FAT_ARTIFACTS_RESUME_OBSERVATION_INVALID = "FAT_ARTIFACTS_RESUME_OBSERVATION_INVALID"
FAT_ARTIFACTS_RESUME_CONFLICT = "FAT_ARTIFACTS_RESUME_CONFLICT"
FAT_ARTIFACTS_RESUME_REQUIRES_FLAG = "FAT_ARTIFACTS_RESUME_REQUIRES_FLAG"
FAT_ARTIFACTS_RESUME_READY = "FAT_ARTIFACTS_RESUME_READY"
FAT_ARTIFACTS_RESUME_READY_RETRY = "FAT_ARTIFACTS_RESUME_READY_RETRY"
FAT_ARTIFACTS_RESUME_COMPLETED = "FAT_ARTIFACTS_RESUME_COMPLETED"
FAT_RESUME_STRING_KEYS = frozenset(
    {
        "stage",
        "content_sha256",
        "schedule_sha256",
        "activation_id",
        "utc_day",
        "dataset_version",
        "dataset_manifest_id",
        "parquet_rel",
        "member_rel",
        "file_sha256",
        "member_sha256",
        "dataset_fingerprint",
        "created_at",
        "completed_at",
    }
)
FAT_RESUME_INT_KEYS = frozenset({"observation_count", "member_count"})
FAT_RESUME_JSON_KEYS = frozenset(
    {"sampling", "observations", "normalized_observations"}
)
CONTENT_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
STREAM_HASH_CHUNK = 1024 * 1024
# Ordinary collector/tick/status may full-parse only below this size. Larger open/
# files require bounded metadata classification and paused-collector migration.
ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES = 2 * 1024 * 1024
PLAN_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {"raw", "payload", "observations", "normalized_observations", "members"}
)
MIGRATION_PEAK_PAYLOAD_MEMORY = "O(max_job_bytes)"
ROUTINE_TICK_PUBLICATION_REPAIR = "O(open_job_metadata_or_compact_bytes)"
UNAVAILABLE_FILESYSTEM_TRUTH = "UNAVAILABLE_FILESYSTEM_TRUTH"
UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET = "UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET"
RoutineOpenKind = Literal["FULL_PARSE_OK", "LEGACY_FAT_REQUIRES_PAUSED_MIGRATION"]
COMPACT_IDENTITY_KEYS = (
    "content_sha256",
    "schedule_sha256",
    "activation_id",
    "utc_day",
    "dataset_version",
    "dataset_manifest_id",
    "parquet_rel",
    "member_rel",
    "file_sha256",
    "member_sha256",
)
APPLY_ACTIVE_STATES = frozenset({"ACTIVE", "DRAINING"})
COMPACT_FORBIDDEN_KEYS = frozenset(
    {"observations", "normalized_observations", "members"}
)
COMPACT_REQUIRED_KEYS = (
    "content_sha256",
    "schedule_sha256",
    "activation_id",
    "stage",
    "utc_day",
    "dataset_version",
    "dataset_manifest_id",
    "created_at",
    "completed_at",
    "parquet_rel",
    "member_rel",
    "file_sha256",
    "member_sha256",
    "observation_count",
    "member_count",
    "dataset_fingerprint",
)
DISK_WARNING_EARLY_PCT = 70


def collector_blocks_apply(activations: Sequence[Mapping[str, Any]]) -> bool:
    """APPLY is allowed only when no live ACTIVE/DRAINING collector remains."""

    return any(str(item.get("state") or "") in APPLY_ACTIVE_STATES for item in activations)


class PublicationJobError(ValueError):
    """Typed publication-job journal failure."""


def jobs_root(data_root: Path) -> Path:
    return Path(data_root) / JOBS_RELATIVE


def open_dir(data_root: Path) -> Path:
    return jobs_root(data_root) / OPEN_DIRNAME


def completed_dir(data_root: Path) -> Path:
    return jobs_root(data_root) / COMPLETED_DIRNAME


def legacy_full_dir(data_root: Path) -> Path:
    return jobs_root(data_root) / LEGACY_FULL_DIRNAME


def flat_legacy_path(data_root: Path, content: str) -> Path:
    return jobs_root(data_root) / f"{content}.json"


def open_job_path(data_root: Path, content: str) -> Path:
    return open_dir(data_root) / f"{content}.json"


def completed_job_path(data_root: Path, content: str) -> Path:
    return completed_dir(data_root) / f"{content}.json"


def legacy_full_path(data_root: Path, content: str) -> Path:
    return legacy_full_dir(data_root) / f"{content}.json"


def assert_routine_hot_path(path: Path) -> None:
    """Routine repair/has-open may only read ``open/`` job files."""

    parts = Path(path).parts
    if COMPLETED_DIRNAME in parts or LEGACY_FULL_DIRNAME in parts:
        raise PublicationJobError(HOT_PATH_FORBIDDEN)


@dataclass(frozen=True)
class OpenJobRoutineProbe:
    """Bounded classification of an ``open/`` job before any full-body parse."""

    kind: RoutineOpenKind
    size_bytes: int
    schedule_sha256: str | None = None
    activation_id: str | None = None
    has_members_array: bool = False


class _JsonByteReader:
    """Single-byte reader with a one-byte pushback; never materializes the file."""

    __slots__ = ("_handle", "_pending")

    def __init__(self, handle: Any) -> None:
        self._handle = handle
        self._pending: int | None = None

    def read(self) -> str:
        if self._pending is not None:
            code = self._pending
            self._pending = None
            return chr(code)
        chunk = self._handle.read(1)
        if not chunk:
            return ""
        return chunk

    def unread(self, char: str) -> None:
        if not char:
            return
        if self._pending is not None:
            raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
        self._pending = ord(char[0])
        if len(char) != 1:
            raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)


def _skip_ws(reader: _JsonByteReader) -> str:
    while True:
        char = reader.read()
        if not char:
            return ""
        if char not in " \t\r\n":
            return char


def _skip_string(reader: _JsonByteReader) -> None:
    while True:
        char = reader.read()
        if not char:
            raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
        if char == "\\":
            if not reader.read():
                raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
            continue
        if char == '"':
            return


def _read_string(reader: _JsonByteReader) -> str:
    chars: list[str] = []
    while True:
        char = reader.read()
        if not char:
            raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
        if char == "\\":
            escaped = reader.read()
            if not escaped:
                raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
            escapes = {
                '"': '"',
                "\\": "\\",
                "/": "/",
                "b": "\b",
                "f": "\f",
                "n": "\n",
                "r": "\r",
                "t": "\t",
            }
            if escaped == "u":
                hex_digits = "".join(reader.read() for _ in range(4))
                if len(hex_digits) != 4:
                    raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
                chars.append(chr(int(hex_digits, 16)))
                continue
            chars.append(escapes.get(escaped, escaped))
            continue
        if char == '"':
            return "".join(chars)
        chars.append(char)


def _skip_value(reader: _JsonByteReader, first: str) -> None:
    if first == '"':
        _skip_string(reader)
        return
    if first == "{":
        depth = 1
        in_string = False
        escape = False
        while depth:
            char = reader.read()
            if not char:
                raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
        return
    if first == "[":
        depth = 1
        in_string = False
        escape = False
        while depth:
            char = reader.read()
            if not char:
                raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
        return
    if first in "-0123456789":
        while True:
            char = reader.read()
            if not char:
                return
            if char in ",}] \t\r\n":
                reader.unread(char)
                return
        return
    literal = first
    while True:
        char = reader.read()
        if not char or char in ",}] \t\r\n":
            if char:
                reader.unread(char)
            break
        literal += char
    if literal not in {"true", "false", "null"}:
        raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)


def _stream_open_job_top_level_meta(path: Path) -> dict[str, Any]:
    """Extract identity scalars and whether a top-level ``members`` array exists.

    Nested values are skipped without materializing. Used only when the open job
    exceeds ``ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES``.
    """

    wanted = {"schedule_sha256", "activation_id", "content_sha256", "stage"}
    found: dict[str, Any] = {
        "schedule_sha256": None,
        "activation_id": None,
        "content_sha256": None,
        "stage": None,
        "has_members_array": False,
    }
    with path.open("r", encoding="utf-8", newline="") as raw:
        reader = _JsonByteReader(raw)
        first = _skip_ws(reader)
        if first != "{":
            raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
        while True:
            char = _skip_ws(reader)
            if char == "}":
                break
            if char == ",":
                continue
            if char != '"':
                raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
            key = _read_string(reader)
            sep = _skip_ws(reader)
            if sep != ":":
                raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
            value_first = _skip_ws(reader)
            if not value_first:
                raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
            if key == "members" and value_first == "[":
                found["has_members_array"] = True
                _skip_value(reader, value_first)
            elif key in wanted and value_first == '"':
                found[key] = _read_string(reader)
            elif key in wanted and value_first == "n":
                rest = "".join(reader.read() for _ in range(3))
                if rest != "ull":
                    raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
                found[key] = None
            else:
                _skip_value(reader, value_first)
    return found


class _CollectingReader:
    """Capture a small JSON value while reusing the skip walker."""

    __slots__ = ("_inner", "_parts", "_size", "_max")

    def __init__(
        self,
        inner: _JsonByteReader,
        *,
        max_bytes: int,
        initial: str,
    ) -> None:
        self._inner = inner
        self._parts = [initial]
        self._size = len(initial.encode("utf-8"))
        self._max = max_bytes
        if self._size > max_bytes:
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_PAYLOAD_TOO_LARGE)

    def read(self) -> str:
        char = self._inner.read()
        if not char:
            return ""
        encoded_len = len(char.encode("utf-8"))
        if self._size + encoded_len > self._max:
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_PAYLOAD_TOO_LARGE)
        self._parts.append(char)
        self._size += encoded_len
        return char

    def unread(self, char: str) -> None:
        if char and self._parts and self._parts[-1] == char:
            popped = self._parts.pop()
            self._size -= len(popped.encode("utf-8"))
        self._inner.unread(char)

    def raw(self) -> str:
        return "".join(self._parts)


def _read_bounded_json_value(
    reader: _JsonByteReader,
    first: str,
    *,
    max_bytes: int,
) -> Any:
    collector = _CollectingReader(reader, max_bytes=max_bytes, initial=first)
    _skip_value(collector, first)  # type: ignore[arg-type]
    try:
        return json.loads(collector.raw())
    except json.JSONDecodeError as exc:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID) from exc


def stream_legacy_fat_open_job_for_artifacts_resume(path: Path) -> dict[str, Any]:
    """Stream ARTIFACTS resume fields; skip ``members[]`` without materializing it.

    Memory is bounded by metadata plus the small observation/sampling payload.
    Never ``read_text`` / ``read_bytes`` / ``json.load`` of the whole job.
    """

    found: dict[str, Any] = {"has_members_array": False}
    with path.open("r", encoding="utf-8", newline="") as raw:
        reader = _JsonByteReader(raw)
        first = _skip_ws(reader)
        if first != "{":
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID)
        while True:
            char = _skip_ws(reader)
            if char == "}":
                break
            if char == ",":
                continue
            if char != '"':
                raise PublicationJobError(FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID)
            key = _read_string(reader)
            sep = _skip_ws(reader)
            if sep != ":":
                raise PublicationJobError(FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID)
            value_first = _skip_ws(reader)
            if not value_first:
                raise PublicationJobError(FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID)
            if key == "members":
                if value_first == "[":
                    found["has_members_array"] = True
                _skip_value(reader, value_first)
                continue
            if key in FAT_RESUME_STRING_KEYS and value_first == '"':
                found[key] = _read_string(reader)
            elif key in FAT_RESUME_STRING_KEYS and value_first == "n":
                rest = "".join(reader.read() for _ in range(3))
                if rest != "ull":
                    raise PublicationJobError(FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID)
                found[key] = None
            elif key in FAT_RESUME_INT_KEYS:
                found[key] = _read_bounded_json_value(
                    reader, value_first, max_bytes=64
                )
            elif key in FAT_RESUME_JSON_KEYS:
                found[key] = _read_bounded_json_value(
                    reader, value_first, max_bytes=FAT_RESUME_CAPTURE_MAX_BYTES
                )
            else:
                _skip_value(reader, value_first)
    if "members" in found:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID)
    return found


def prove_legacy_fat_open_artifacts_source(
    data_root: Path,
    content_sha256: str,
) -> dict[str, Any]:
    """Fail-closed filesystem proofs for one oversized ARTIFACTS open job."""

    if CONTENT_SHA256_RE.fullmatch(content_sha256) is None:
        raise PublicationJobError(CONTENT_SHA256_INVALID)
    path = open_job_path(data_root, content_sha256)
    if path.parent.name != OPEN_DIRNAME:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN)
    if not path.is_file() or path.is_symlink():
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN)
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN) from exc
    if resolved.name != f"{content_sha256}.json":
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN)
    assert_routine_hot_path(path)
    probe = probe_open_job_for_routine_path(path)
    if probe.kind != "LEGACY_FAT_REQUIRES_PAUSED_MIGRATION":
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_NOT_LEGACY_FAT)
    source_size, source_sha256 = _source_fingerprint(path)
    job = stream_legacy_fat_open_job_for_artifacts_resume(path)
    if str(job.get("stage") or "") != STAGE_ARTIFACTS:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_UNSUPPORTED_STAGE)
    if str(job.get("content_sha256") or "") != content_sha256:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH)
    if CONTENT_SHA256_RE.fullmatch(str(job.get("schedule_sha256") or "")) is None:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH)
    activation_id = str(job.get("activation_id") or "")
    if not activation_id.startswith("ACT-") or len(activation_id) < 8:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH)
    for key in (
        "utc_day",
        "dataset_version",
        "dataset_manifest_id",
        "parquet_rel",
        "member_rel",
        "file_sha256",
        "member_sha256",
        "created_at",
    ):
        if not str(job.get(key) or ""):
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH)
    if CONTENT_SHA256_RE.fullmatch(str(job.get("file_sha256") or "")) is None:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_HASH_MISMATCH)
    if CONTENT_SHA256_RE.fullmatch(str(job.get("member_sha256") or "")) is None:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_HASH_MISMATCH)
    try:
        observation_count = int(job.get("observation_count") or 0)
        member_count = int(job.get("member_count") or 0)
    except (TypeError, ValueError) as exc:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH) from exc
    if observation_count <= 0 or member_count <= 0:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH)
    observations = job.get("observations")
    if not isinstance(observations, list) or len(observations) != observation_count:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_OBSERVATION_INVALID)
    parquet_rel = str(job["parquet_rel"]).replace("\\", "/")
    member_rel = str(job["member_rel"]).replace("\\", "/")
    job["parquet_rel"] = parquet_rel
    job["member_rel"] = member_rel
    for rel, digest in (
        (parquet_rel, str(job["file_sha256"])),
        (member_rel, str(job["member_sha256"])),
    ):
        artifact = Path(data_root) / rel
        if not artifact.is_file() or artifact.is_symlink():
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_ARTIFACT_MISSING)
        if _sha256_file(artifact) != digest:
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_HASH_MISMATCH)
    completed = completed_job_path(data_root, content_sha256)
    if completed.is_file():
        try:
            existing = json.loads(completed.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_CONFLICT) from exc
        if not isinstance(existing, dict) or not is_compact_receipt(existing):
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_CONFLICT)
        if str(existing.get("dataset_manifest_id")) != str(job.get("dataset_manifest_id")):
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_CONFLICT)
        if str(existing.get("content_sha256") or "") != content_sha256:
            raise PublicationJobError(FAT_ARTIFACTS_RESUME_CONFLICT)
    return {
        "path": path,
        "job": job,
        "probe": probe,
        "source_size": source_size,
        "source_sha256": source_sha256,
    }


def probe_open_job_for_routine_path(path: Path) -> OpenJobRoutineProbe:
    """Classify an ``open/`` job using size + bounded metadata only when oversized."""

    assert_routine_hot_path(path)
    try:
        size = int(path.stat().st_size)
    except OSError as exc:
        raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION) from exc
    if size <= ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES:
        return OpenJobRoutineProbe(kind="FULL_PARSE_OK", size_bytes=size)
    meta = _stream_open_job_top_level_meta(path)
    return OpenJobRoutineProbe(
        kind="LEGACY_FAT_REQUIRES_PAUSED_MIGRATION",
        size_bytes=size,
        schedule_sha256=(
            str(meta["schedule_sha256"])
            if meta.get("schedule_sha256") is not None
            else None
        ),
        activation_id=(
            str(meta["activation_id"])
            if meta.get("activation_id") is not None
            else None
        ),
        has_members_array=bool(meta.get("has_members_array")),
    )


def load_open_job_for_routine_path(path: Path) -> dict[str, Any]:
    """Full-parse an ``open/`` job only after routine-path classification allows it."""

    probe = probe_open_job_for_routine_path(path)
    if probe.kind != "FULL_PARSE_OK":
        raise PublicationJobError(LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicationJobError("PUBLICATION_JOB_INVALID") from exc
    if not isinstance(loaded, dict):
        raise PublicationJobError("PUBLICATION_JOB_INVALID")
    return loaded


def open_job_probe_matches_activation(
    probe: OpenJobRoutineProbe,
    *,
    schedule_sha256: str,
    activation_id: str,
) -> bool:
    """Whether an oversized open job is in-scope for this activation.

    Mirrors ``has_open_publication_jobs`` identity rules using streamed scalars
    only. Unknown identity fails closed via the caller raising migration required.
    """

    if probe.schedule_sha256 is None:
        return True
    if str(probe.schedule_sha256) != str(schedule_sha256):
        return False
    if probe.activation_id is None:
        return True
    return str(probe.activation_id) == str(activation_id)


def _dir_file_stats(directory: Path) -> tuple[int, int]:
    if not directory.is_dir():
        return 0, 0
    count = 0
    total = 0
    for child in directory.glob("*.json"):
        if not child.is_file() or child.is_symlink():
            continue
        count += 1
        try:
            total += int(child.stat().st_size)
        except OSError:
            continue
    return count, total


def _flat_legacy_stats(root: Path) -> tuple[int, int]:
    if not root.is_dir():
        return 0, 0
    count = 0
    total = 0
    for child in root.glob("*.json"):
        if not child.is_file() or child.is_symlink():
            continue
        count += 1
        try:
            total += int(child.stat().st_size)
        except OSError:
            continue
    return count, total


def journal_stats(data_root: Path) -> dict[str, int]:
    """Metadata/stat path: counts and bytes, no JSON body reads."""

    root = jobs_root(data_root)
    open_count, open_bytes = _dir_file_stats(open_dir(data_root))
    completed_count, completed_bytes = _dir_file_stats(completed_dir(data_root))
    legacy_count, legacy_bytes = _dir_file_stats(legacy_full_dir(data_root))
    flat_count, flat_bytes = _flat_legacy_stats(root)
    return {
        "publication_jobs_open_count": open_count,
        "publication_jobs_open_bytes": open_bytes,
        "publication_jobs_completed_count": completed_count,
        "publication_jobs_completed_bytes": completed_bytes,
        "publication_jobs_legacy_full_count": legacy_count,
        "publication_jobs_legacy_full_bytes": legacy_bytes,
        "publication_jobs_unmigrated_flat_count": flat_count,
        "publication_jobs_unmigrated_flat_bytes": flat_bytes,
    }


def rdp_bytes_excluding_publication_jobs(data_root: Path) -> int:
    total = 0
    root = Path(data_root)
    jobs = jobs_root(data_root)
    if not root.exists():
        return 0
    for child in root.rglob("*"):
        if not child.is_file() or child.is_symlink():
            continue
        try:
            child.relative_to(jobs)
        except ValueError:
            try:
                total += int(child.stat().st_size)
            except OSError:
                continue
    return total


def is_compact_receipt(job: Mapping[str, Any]) -> bool:
    if str(job.get("stage") or "") != STAGE_COMPLETE:
        return False
    if any(key in job for key in COMPACT_FORBIDDEN_KEYS):
        return False
    return all(key in job for key in COMPACT_REQUIRED_KEYS)


def compact_receipt_from_job(
    job: Mapping[str, Any],
    *,
    completed_at: datetime,
    dataset_fingerprint: str | None = None,
) -> dict[str, Any]:
    try:
        content = str(job["content_sha256"])
        receipt = {
            "content_sha256": content,
            "schedule_sha256": str(job["schedule_sha256"]),
            "activation_id": str(job["activation_id"]),
            "stage": STAGE_COMPLETE,
            "utc_day": str(job["utc_day"]),
            "dataset_version": str(job["dataset_version"]),
            "dataset_manifest_id": str(job["dataset_manifest_id"]),
            "created_at": str(job["created_at"]),
            "completed_at": render_utc(completed_at.astimezone(UTC)),
            "parquet_rel": str(job["parquet_rel"]),
            "member_rel": str(job["member_rel"]),
            "file_sha256": str(job["file_sha256"]),
            "member_sha256": str(job["member_sha256"]),
            "observation_count": int(job.get("observation_count") or 0),
            "member_count": int(job.get("member_count") or 0),
            "dataset_fingerprint": str(
                dataset_fingerprint or job.get("dataset_fingerprint") or content
            ),
        }
    except (KeyError, TypeError, ValueError):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE) from None
    if any(not str(receipt.get(key) or "") for key in COMPACT_IDENTITY_KEYS):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE)
    if any(key in receipt for key in COMPACT_FORBIDDEN_KEYS):
        raise PublicationJobError("COMPACT_RECEIPT_CONTAINS_PAYLOAD")
    if not is_compact_receipt(receipt):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE)
    return receipt


def _same_publication_identity(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return all(str(left.get(key) or "") == str(right.get(key) or "") for key in COMPACT_IDENTITY_KEYS)


def _planned_compact_receipt(payload: Mapping[str, Any], content: str) -> dict[str, Any]:
    created = payload.get("created_at")
    try:
        completed_at = (
            parse_utc(str(payload.get("completed_at") or created))
            if (payload.get("completed_at") or created)
            else datetime.now(UTC)
        )
    except (TypeError, ValueError):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE) from None
    receipt = compact_receipt_from_job(
        payload,
        completed_at=completed_at,
        dataset_fingerprint=str(payload.get("dataset_fingerprint") or content),
    )
    if payload.get("completed_at"):
        receipt["completed_at"] = str(payload["completed_at"])
    if not is_compact_receipt(receipt):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE)
    return receipt


def _content_sha256(payload: Mapping[str, Any]) -> str:
    content = str(payload.get("content_sha256") or "")
    if CONTENT_SHA256_RE.fullmatch(content) is None:
        raise PublicationJobError(CONTENT_SHA256_INVALID)
    return content


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(STREAM_HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _source_fingerprint(path: Path) -> tuple[int, str]:
    return int(path.stat().st_size), _sha256_file(path)


def _revalidate_source(path: Path, size: int, digest: str) -> None:
    try:
        current = _source_fingerprint(path)
    except OSError:
        raise PublicationJobError(SOURCE_CHANGED_AFTER_PLAN) from None
    if current != (size, digest):
        raise PublicationJobError(SOURCE_CHANGED_AFTER_PLAN)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY)
    if not isinstance(payload, dict):
        raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY)
    return payload


def _dest_matches_hash(path: Path, digest: str) -> bool:
    try:
        return _sha256_file(path) == digest
    except OSError:
        return False


def _inspect_unmigrated_source(data_root: Path, path: Path) -> dict[str, Any]:
    try:
        size, digest = _source_fingerprint(path)
    except OSError:
        raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY) from None
    payload = _load_json_object(path)
    content = _content_sha256(payload)
    label = classify_legacy_payload(payload, data_root=data_root)
    if label == CLASS_AMBIGUOUS:
        raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY)
    receipt = None
    if label == CLASS_OPEN:
        destination = open_job_path(data_root, content)
        if destination.is_file() and not _dest_matches_hash(destination, digest):
            raise PublicationJobError(OPEN_JOB_CONFLICT)
    elif label == CLASS_PROVEN_COMPLETED:
        receipt = _planned_compact_receipt(payload, content)
        completed = completed_job_path(data_root, content)
        if completed.is_file():
            try:
                existing = json.loads(completed.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
            if not isinstance(existing, dict) or not is_compact_receipt(existing):
                raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
            if not _same_publication_identity(existing, receipt):
                raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
        legacy = legacy_full_path(data_root, content)
        if legacy.is_file() and not _dest_matches_hash(legacy, digest):
            raise PublicationJobError(LEGACY_FULL_BYTE_MISMATCH)
    else:
        raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY)
    return {
        "sources": [path],
        "source_size": size,
        "source_sha256": digest,
        "content": content,
        "label": label,
        "receipt": receipt,
    }


def _coalesce_plan_item(
    seen: dict[str, dict[str, Any]],
    item: dict[str, Any],
) -> None:
    previous = seen[item["content"]]
    same_identity = (
        previous["source_sha256"] == item["source_sha256"]
        and previous["source_size"] == item["source_size"]
        and previous["label"] == item["label"]
    )
    if same_identity and previous["label"] == CLASS_OPEN:
        previous["sources"].extend(item["sources"])
        return
    if (
        same_identity
        and previous["receipt"] is not None
        and item["receipt"] is not None
        and _same_publication_identity(previous["receipt"], item["receipt"])
    ):
        previous["sources"].extend(item["sources"])
        return
    raise PublicationJobError(CONTENT_IDENTITY_COLLISION)


def publication_artifacts_proven(
    data_root: Path,
    job: Mapping[str, Any],
) -> bool:
    """Durable scientific effects required before a job may leave ``open/``."""

    manifest_id = str(job.get("dataset_manifest_id") or "")
    if len(str(job.get("content_sha256") or "")) != 64 or not manifest_id:
        return False
    published = (
        Path(data_root) / "datasets" / "manifests" / f"{manifest_id}.published"
    )
    manifest = Path(data_root) / "datasets" / "manifests" / f"{manifest_id}.json"
    if not published.is_file() or not manifest.is_file():
        return False
    parquet_rel = str(job.get("parquet_rel") or "")
    member_rel = str(job.get("member_rel") or "")
    if not parquet_rel or not member_rel:
        return False
    parquet = Path(data_root) / parquet_rel
    member = Path(data_root) / member_rel
    return parquet.is_file() and member.is_file()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(dict(payload), sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def load_job_by_content(data_root: Path, content: str) -> dict[str, Any] | None:
    """Exact content_sha256 lookup: completed, then open, then unmigrated flat."""

    for path in (
        completed_job_path(data_root, content),
        open_job_path(data_root, content),
        flat_legacy_path(data_root, content),
    ):
        if not path.is_file():
            continue
        if OPEN_DIRNAME in Path(path).parts:
            return load_open_job_for_routine_path(path)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise PublicationJobError("PUBLICATION_JOB_INVALID")
        return loaded
    return None


def save_open_job(data_root: Path, content: str, payload: Mapping[str, Any]) -> None:
    if str(payload.get("stage") or "") == STAGE_COMPLETE:
        raise PublicationJobError("COMPACT_RECEIPT_IN_OPEN")
    path = open_job_path(data_root, content)
    if path.is_file():
        try:
            size = int(path.stat().st_size)
        except OSError as exc:
            raise PublicationJobError("PUBLICATION_JOB_INVALID") from exc
        if size > ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES:
            # Preserve oversized legacy source until canonical complete unlinks it.
            return
    _atomic_write_json(path, payload)


def complete_publication_job(
    data_root: Path,
    job: Mapping[str, Any],
    *,
    completed_at: datetime,
    dataset_fingerprint: str | None = None,
    expected_open_source: tuple[int, str] | None = None,
) -> dict[str, Any]:
    """Write compact receipt and remove the full open/flat job. Never rewrite RDP."""

    content = str(job["content_sha256"])
    destination = completed_job_path(data_root, content)
    if destination.is_file():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if not isinstance(existing, dict) or not is_compact_receipt(existing):
            raise PublicationJobError("COMPLETED_RECEIPT_INVALID")
        if str(existing.get("dataset_manifest_id")) != str(job.get("dataset_manifest_id")):
            raise PublicationJobError("CONTENT_IDENTITY_INVALID")
        for leftover in (
            open_job_path(data_root, content),
            flat_legacy_path(data_root, content),
        ):
            leftover.unlink(missing_ok=True)
        return existing
    if expected_open_source is not None:
        leftover = open_job_path(data_root, content)
        if leftover.is_file():
            _revalidate_source(
                leftover, expected_open_source[0], expected_open_source[1]
            )
    if not publication_artifacts_proven(data_root, job):
        raise PublicationJobError("PUBLICATION_NOT_PROVEN")
    receipt = compact_receipt_from_job(
        job,
        completed_at=completed_at,
        dataset_fingerprint=dataset_fingerprint,
    )
    _atomic_write_json(destination, receipt)
    for leftover in (
        open_job_path(data_root, content),
        flat_legacy_path(data_root, content),
    ):
        leftover.unlink(missing_ok=True)
    return receipt


def iter_open_job_paths(data_root: Path) -> list[Path]:
    directory = open_dir(data_root)
    if not directory.is_dir():
        return []
    paths = []
    for path in sorted(directory.glob("*.json")):
        if path.is_file() and not path.is_symlink():
            assert_routine_hot_path(path)
            paths.append(path)
    return paths


def classify_legacy_payload(
    payload: object,
    *,
    data_root: Path,
) -> str:
    if not isinstance(payload, dict):
        return CLASS_AMBIGUOUS
    content = str(payload.get("content_sha256") or "")
    if len(content) != 64:
        return CLASS_AMBIGUOUS
    if payload.get("activation_id") is None:
        return CLASS_AMBIGUOUS
    if not payload.get("schedule_sha256"):
        return CLASS_AMBIGUOUS
    if is_compact_receipt(payload) and publication_artifacts_proven(data_root, payload):
        return CLASS_PROVEN_COMPLETED
    if publication_artifacts_proven(data_root, payload):
        return CLASS_PROVEN_COMPLETED
    stage = str(payload.get("stage") or "")
    if stage in {STAGE_MARKER, STAGE_COMPLETE}:
        return CLASS_AMBIGUOUS
    members = payload.get("members")
    if isinstance(members, list) and members:
        return CLASS_OPEN
    # Memory-bounded open jobs retain hashes/counts/observations, not the census.
    if (
        stage
        and payload.get("member_count")
        and payload.get("file_sha256")
        and payload.get("member_sha256")
        and payload.get("parquet_rel")
        and payload.get("member_rel")
        and isinstance(payload.get("observations"), list)
    ):
        return CLASS_OPEN
    return CLASS_AMBIGUOUS


def _iter_unmigrated_paths(data_root: Path) -> list[Path]:
    root = jobs_root(data_root)
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.glob("*.json")
        if path.is_file() and not path.is_symlink()
    )


def dry_run_migration(data_root: Path) -> dict[str, Any]:
    stats = journal_stats(data_root)
    classified = {
        CLASS_OPEN: 0,
        CLASS_PROVEN_COMPLETED: 0,
        CLASS_AMBIGUOUS: 0,
    }
    ambiguous_names: list[str] = []
    open_bytes = 0
    for path in _iter_unmigrated_paths(data_root):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            classified[CLASS_AMBIGUOUS] += 1
            ambiguous_names.append(path.name)
            continue
        label = classify_legacy_payload(payload, data_root=data_root)
        classified[label] += 1
        if label == CLASS_AMBIGUOUS:
            ambiguous_names.append(path.name)
        elif label == CLASS_OPEN:
            open_bytes += int(path.stat().st_size)
    stats.update(
        {
            "old_unmigrated_count": sum(classified.values()),
            "classified_open": classified[CLASS_OPEN],
            "classified_proven_completed": classified[CLASS_PROVEN_COMPLETED],
            "classified_ambiguous": classified[CLASS_AMBIGUOUS],
            "projected_hot_path_bytes": stats["publication_jobs_open_bytes"] + open_bytes,
            "ambiguous_names": ambiguous_names,
            "provider_calls": 0,
            "scientific_writes": 0,
        }
    )
    return stats


def plan_migration(data_root: Path) -> list[dict[str, Any]]:
    """Inspect every unmigrated source. Fail before the caller mutates anything.

    Peak payload memory is O(max job bytes): the plan retains source metadata
    and compact receipts, never raw job bodies or scientific arrays.
    """

    seen: dict[str, dict[str, Any]] = {}
    order: list[dict[str, Any]] = []
    for path in _iter_unmigrated_paths(data_root):
        item = _inspect_unmigrated_source(data_root, path)
        if any(key in item for key in PLAN_FORBIDDEN_PAYLOAD_KEYS):
            raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY)
        content = item["content"]
        if content in seen:
            _coalesce_plan_item(seen, item)
            continue
        seen[content] = item
        order.append(item)
    return order


def apply_migration(data_root: Path) -> dict[str, Any]:
    """Move unmigrated flat jobs after a complete preflight. No RDP rewrite."""

    plan = plan_migration(data_root)
    report = dry_run_migration(data_root)
    moved_open = 0
    moved_completed = 0
    for item in plan:
        content = item["content"]
        digest = item["source_sha256"]
        size = item["source_size"]
        for path in item["sources"]:
            _revalidate_source(path, size, digest)
            if item["label"] == CLASS_OPEN:
                destination = open_job_path(data_root, content)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.is_file():
                    if not _dest_matches_hash(destination, digest):
                        raise PublicationJobError(OPEN_JOB_CONFLICT)
                    path.unlink()
                else:
                    os.replace(path, destination)
                    if not _dest_matches_hash(destination, digest):
                        raise PublicationJobError(OPEN_JOB_CONFLICT)
                moved_open += 1
                continue
            receipt = item["receipt"]
            completed = completed_job_path(data_root, content)
            if completed.is_file():
                existing = json.loads(completed.read_text(encoding="utf-8"))
                if not isinstance(existing, dict) or not is_compact_receipt(existing):
                    raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
                if not _same_publication_identity(existing, receipt):
                    raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
            else:
                _atomic_write_json(completed, receipt)
            legacy = legacy_full_path(data_root, content)
            legacy.parent.mkdir(parents=True, exist_ok=True)
            if legacy.is_file():
                if not _dest_matches_hash(legacy, digest):
                    raise PublicationJobError(LEGACY_FULL_BYTE_MISMATCH)
                path.unlink(missing_ok=True)
            else:
                os.replace(path, legacy)
                if not _dest_matches_hash(legacy, digest):
                    raise PublicationJobError(LEGACY_FULL_BYTE_MISMATCH)
            moved_completed += 1
    report["moved_open"] = moved_open
    report["moved_completed"] = moved_completed
    report["legacy_full_deleted"] = False
    report["migration_peak_payload_memory"] = MIGRATION_PEAK_PAYLOAD_MEMORY
    report["routine_tick_publication_repair"] = ROUTINE_TICK_PUBLICATION_REPAIR
    report.update(journal_stats(data_root))
    return report


def _measured_int(value: Any, *, allow_zero: bool) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if allow_zero:
        return value if value >= 0 else None
    return value if value > 0 else None


def project_7d_disk_used(
    *,
    disk_total_bytes: int | None,
    disk_used_bytes: int | None,
    sqlite_bytes: int | None,
    rdp_science_bytes: int | None,
    job_open_bytes: int,
    job_completed_bytes: int,
    job_legacy_bytes: int,
    elapsed_campaign_days: float | None,
    declared_raw_bytes_per_day: int | None,
    history_data_growth_24h_bytes: int | None,
) -> dict[str, Any]:
    """Conservative 7-day used-pct. UNKNOWN inputs cannot manufacture a PASS."""

    del elapsed_campaign_days
    sqlite = _measured_int(sqlite_bytes, allow_zero=True)
    science = _measured_int(rdp_science_bytes, allow_zero=True)
    live = (
        sqlite + science + int(job_open_bytes) + int(job_completed_bytes)
        if sqlite is not None and science is not None
        else None
    )
    total = _measured_int(disk_total_bytes, allow_zero=False)
    used = _measured_int(disk_used_bytes, allow_zero=True)
    daily_history = _measured_int(history_data_growth_24h_bytes, allow_zero=False)
    daily_declared = _measured_int(declared_raw_bytes_per_day, allow_zero=False)
    if daily_history is not None:
        daily = daily_history
        basis = "STORAGE_HISTORY_24H"
    elif daily_declared is not None:
        daily = daily_declared
        basis = "DECLARED_RAW_BYTES_PER_DAY"
    else:
        return {
            "projection_basis": UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET,
            "live_bytes": live,
            "legacy_full_bytes": job_legacy_bytes,
            "projected_7d_additional_bytes": None,
            "projected_7d_disk_used_bytes": None,
            "projected_7d_disk_used_pct": None,
            "projected_7d_disk_used_pass_70": False,
            "early_warning_pct": DISK_WARNING_EARLY_PCT,
        }
    if total is None or used is None:
        return {
            "projection_basis": UNAVAILABLE_FILESYSTEM_TRUTH,
            "live_bytes": live,
            "legacy_full_bytes": job_legacy_bytes,
            "projected_7d_additional_bytes": int(daily) * 7 * 2,
            "projected_7d_disk_used_bytes": None,
            "projected_7d_disk_used_pct": None,
            "projected_7d_disk_used_pass_70": False,
            "early_warning_pct": DISK_WARNING_EARLY_PCT,
        }
    extra_with_backup = int(daily) * 7 * 2
    projected_used = used + extra_with_backup
    projected_pct = 100.0 * projected_used / total
    return {
        "projection_basis": basis,
        "live_bytes": live,
        "legacy_full_bytes": job_legacy_bytes,
        "projected_7d_additional_bytes": extra_with_backup,
        "projected_7d_disk_used_bytes": projected_used,
        "projected_7d_disk_used_pct": round(projected_pct, 4),
        "projected_7d_disk_used_pass_70": projected_pct < DISK_WARNING_EARLY_PCT,
        "early_warning_pct": DISK_WARNING_EARLY_PCT,
    }


__all__ = [
    "AMBIGUOUS_BLOCKS_APPLY",
    "APPLY_ACTIVE_STATES",
    "CLASS_AMBIGUOUS",
    "CLASS_OPEN",
    "CLASS_PROVEN_COMPLETED",
    "COLLECTOR_NOT_PAUSED",
    "COLLECTOR_STORE_MISSING",
    "COMPACT_FORBIDDEN_KEYS",
    "COMPACT_RECEIPT_UNCONSTRUCTABLE",
    "COMPLETED_RECEIPT_CONFLICT",
    "CONTENT_IDENTITY_COLLISION",
    "CONTENT_SHA256_INVALID",
    "FAT_ARTIFACTS_RESUME_ARTIFACT_MISSING",
    "FAT_ARTIFACTS_RESUME_COMPLETED",
    "FAT_ARTIFACTS_RESUME_CONFLICT",
    "FAT_ARTIFACTS_RESUME_CONTENT_REQUIRED",
    "FAT_ARTIFACTS_RESUME_HASH_MISMATCH",
    "FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH",
    "FAT_ARTIFACTS_RESUME_NOT_LEGACY_FAT",
    "FAT_ARTIFACTS_RESUME_OBSERVATION_INVALID",
    "FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID",
    "FAT_ARTIFACTS_RESUME_PAYLOAD_TOO_LARGE",
    "FAT_ARTIFACTS_RESUME_READY",
    "FAT_ARTIFACTS_RESUME_READY_RETRY",
    "FAT_ARTIFACTS_RESUME_REQUIRES_FLAG",
    "FAT_ARTIFACTS_RESUME_SCHEDULE_MISSING",
    "FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN",
    "FAT_ARTIFACTS_RESUME_UNSUPPORTED_STAGE",
    "HOT_PATH_FORBIDDEN",
    "LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION",
    "LEGACY_FULL_BYTE_MISMATCH",
    "MIGRATION_PEAK_PAYLOAD_MEMORY",
    "OPEN_JOB_CONFLICT",
    "OpenJobRoutineProbe",
    "PLAN_FORBIDDEN_PAYLOAD_KEYS",
    "PublicationJobError",
    "ROUTINE_OPEN_JOB_FULL_PARSE_MAX_BYTES",
    "ROUTINE_TICK_PUBLICATION_REPAIR",
    "SOURCE_CHANGED_AFTER_PLAN",
    "STAGE_ARTIFACTS",
    "STAGE_COMPLETE",
    "STAGE_MARKER",
    "UNAVAILABLE_FILESYSTEM_TRUTH",
    "UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET",
    "apply_migration",
    "assert_routine_hot_path",
    "collector_blocks_apply",
    "compact_receipt_from_job",
    "complete_publication_job",
    "completed_dir",
    "dry_run_migration",
    "is_compact_receipt",
    "iter_open_job_paths",
    "journal_stats",
    "legacy_full_dir",
    "load_job_by_content",
    "load_open_job_for_routine_path",
    "open_job_probe_matches_activation",
    "probe_open_job_for_routine_path",
    "open_dir",
    "plan_migration",
    "project_7d_disk_used",
    "prove_legacy_fat_open_artifacts_source",
    "publication_artifacts_proven",
    "rdp_bytes_excluding_publication_jobs",
    "save_open_job",
    "stream_legacy_fat_open_job_for_artifacts_resume",
]
