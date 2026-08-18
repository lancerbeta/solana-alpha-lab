"""Recover bounded timing evidence from retained quote-native raw payloads."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any


ATOM_ID = "QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1"
TIMESTAMP_SEMANTICS = (
    "LOCAL_RAW_WRITE_COMPLETE_UPPER_BOUND_NOT_REMOTE_OBSERVED_AT"
)


class TimingRecoveryError(ValueError):
    """Raised when retained raw metadata cannot prove the declared time bound."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise TimingRecoveryError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _parse_utc(value: object) -> datetime:
    _require(isinstance(value, str) and bool(value), "TIMESTAMP_INVALID")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise TimingRecoveryError("TIMESTAMP_INVALID") from exc


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _resolve_raw_path(raw_root: Path, relative: object) -> Path:
    _require(isinstance(relative, str) and bool(relative), "RAW_PATH_INVALID")
    normalized = relative.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    _require(
        not candidate.is_absolute() and all(part not in {"", ".", ".."} for part in candidate.parts),
        "RAW_PATH_INVALID",
    )
    root = raw_root.resolve()
    resolved = (root / Path(*candidate.parts)).resolve()
    _require(resolved != root and root in resolved.parents, "RAW_PATH_INVALID")
    return resolved


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recover_timing(
    runtime_receipt: Mapping[str, Any],
    *,
    raw_root: Path,
) -> dict[str, object]:
    _require(runtime_receipt.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    retention = _mapping(runtime_receipt.get("raw_retention"), "RAW_RETENTION_INVALID")
    manifests = retention.get("manifests")
    observations = runtime_receipt.get("observations")
    _require(isinstance(manifests, list), "RAW_MANIFESTS_INVALID")
    _require(isinstance(observations, list), "OBSERVATIONS_INVALID")

    manifest_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_manifest in manifests:
        manifest = _mapping(raw_manifest, "RAW_MANIFEST_INVALID")
        observation_id = manifest.get("observation_id")
        _require(
            isinstance(observation_id, str) and observation_id not in manifest_by_id,
            "RAW_MANIFEST_ID_INVALID",
        )
        manifest_by_id[observation_id] = manifest

    recovered_rows: list[dict[str, object]] = []
    horizon_counts: dict[str, int] = {"900": 0, "3600": 0}
    for raw_observation in observations:
        observation = _mapping(raw_observation, "OBSERVATION_INVALID")
        horizon = observation.get("horizon_seconds")
        if horizon not in {900, 3600} or observation.get("consumed_call") is not True:
            continue
        observation_id = observation.get("observation_id")
        _require(isinstance(observation_id, str), "OBSERVATION_ID_INVALID")
        manifest = manifest_by_id.get(observation_id)
        _require(manifest is not None, "RAW_MANIFEST_MISSING")
        path = _resolve_raw_path(raw_root, manifest.get("path"))
        _require(path.is_file(), "RAW_FILE_MISSING")
        expected_bytes = manifest.get("bytes")
        expected_sha = manifest.get("sha256")
        _require(path.stat().st_size == expected_bytes, "RAW_BYTES_DRIFT")
        _require(_sha256(path) == expected_sha, "RAW_SHA256_DRIFT")

        due_at = _parse_utc(observation.get("due_at"))
        slack = observation.get("lateness_slack_seconds")
        _require(isinstance(slack, int) and slack >= 0, "SLACK_INVALID")
        raw_write_at = datetime.fromtimestamp(
            path.stat().st_mtime_ns / 1_000_000_000,
            tz=UTC,
        )
        _require(raw_write_at >= due_at, "RAW_WRITE_BEFORE_DUE")
        _require(
            raw_write_at <= due_at + timedelta(seconds=slack),
            "RAW_WRITE_OUTSIDE_SLACK",
        )
        horizon_key = str(horizon)
        horizon_counts[horizon_key] += 1
        recovered_rows.append(
            {
                "observation_id": observation_id,
                "horizon_seconds": horizon,
                "due_at": _format_utc(due_at),
                "lateness_slack_seconds": slack,
                "raw_path": str(manifest["path"]),
                "raw_sha256": expected_sha,
                "raw_write_complete_at": _format_utc(raw_write_at),
                "within_slack": True,
            }
        )

    _require(bool(recovered_rows), "NO_RECOVERABLE_HORIZON_ROWS")
    return {
        "schema": "smial.quote-native-evidence-channel-qualification.timing-recovery",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "timestamp_semantics": TIMESTAMP_SEMANTICS,
        "verdict": "RECOVERED_RAW_WRITE_UPPER_BOUND_WITHIN_SLACK",
        "horizon_counts": horizon_counts,
        "recovered_rows": recovered_rows,
    }
