"""Create-only retention boundary for one future TASK-30 stream attempt."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .task30_forward_stream_runtime import (
    CONNECTION_CREDITS,
    MAX_FRAME_BYTES,
    MAX_NOTIFICATIONS,
    MAX_OPEN_SECONDS,
    MAX_STREAM_BYTES,
    OWNER_EXECUTION_PHRASE,
    ForwardStreamRuntimeError,
    RuntimeCapture,
    bind_transaction_subscribe,
    classify_forward_stream_capture,
    evaluate_forward_stream_runtime,
)
from .lifecycle_discovery_transport import WssCapture


LOGICAL_ROOT = "local/task30_forward_stream"
_NONCE_RE = re.compile(r"^[0-9a-f]{8}$")
_RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
_ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,79}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_STATES = frozenset(
    {
        "CONNECTION_OR_AUTH_REJECTED",
        "NO_OBSERVED_TX_NO_EMPTY_CLAIM",
        "OBSERVATION_RETAINED_TECHNICAL_ONLY",
        "RETENTION_FAILED_STOP",
        "SUBSCRIPTION_REJECTED",
        "TRANSPORT_LOST_UNKNOWN",
    }
)
_TERMINAL_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "run_id",
        "logical_run_root",
        "started_at",
        "terminal_at",
        "state",
        "terminal_state",
        "notifications",
        "stream_bytes",
        "estimated_credits",
        "unknown",
        "retry",
        "reconnect",
        "interval_projectable",
        "zero_volume",
        "empty_interval",
        "task30_trial",
        "raw_retention",
        "raw_manifest",
    }
)

_EXPECTED_EXECUTION_POLICY: dict[str, object] = {
    "schema": "smial.task30.forward-stream-execution-adapter.policy",
    "schema_version": "1.0",
    "task_id": "TASK-30",
    "atom_id": "T30-A14P_FORWARD_STREAM_EXECUTION_ADAPTER_V1",
    "consumer": "EXACT_OWNER_FORWARD_STREAM_EXTERNAL_GATE",
    "runtime_policy": "configs/task30_forward_stream_runtime_harness_v1.yaml",
    "retention": {
        "class": "A4",
        "logical_root": LOGICAL_ROOT,
        "started_receipt": "attempt_started.json",
        "manifest": "raw_manifest.json",
        "terminal_receipt": "terminal_receipt.json",
        "create_only": True,
    },
    "credential": {
        "environment_variable": "HELIUS_API_KEY",
        "read_after_started_receipt": True,
    },
    "execution": {
        "max_attempts": 1,
        "retry": False,
        "reconnect": False,
        "fallback": False,
        "scheduler": False,
    },
    "authority": {
        "provider_api_rpc_wss_calls": 0,
        "credential_read": False,
        "raw_external_data_write": False,
    },
    "decision": "OFFLINE_EXECUTION_ADAPTER_PENDING_IMPLEMENTATION",
    "project_sources_disposition": "NO_CHANGE",
}


class ForwardStreamExecutionError(RuntimeError):
    """A sanitized, stable failure at the A14P execution boundary."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or _ERROR_CODE_RE.fullmatch(code) is None:
            code = "UNCLASSIFIED_LOCAL_FAILURE"
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"ForwardStreamExecutionError(code={self.code!r})"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ForwardStreamExecutionError(code)


def _same_exact(value: object, expected: object) -> bool:
    if isinstance(expected, Mapping):
        if not isinstance(value, Mapping):
            return False
        if set(value) != set(expected):
            return False
        return all(_same_exact(value[key], expected[key]) for key in expected)
    return type(value) is type(expected) and value == expected


def _canonical_json(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ForwardStreamExecutionError("RECEIPT_JSON_INVALID") from exc


def _closed_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _closed_json_loads(body: str) -> object:
    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(
        body,
        object_pairs_hook=_closed_json_object,
        parse_constant=reject_constant,
    )


def _utc_text(value: datetime) -> str:
    _require(
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
        and value.utcoffset().total_seconds() == 0,
        "START_TIME_UTC_REQUIRED",
    )
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _receipt_utc(value: object) -> datetime | None:
    if type(value) is not str or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        return None
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset().total_seconds() != 0
    ):
        return None
    if parsed.astimezone(UTC).isoformat().replace("+00:00", "Z") != value:
        return None
    return parsed


def _nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _normalized_path(value: Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def _existing_components(path: Path, stop: Path) -> tuple[Path, ...]:
    components: list[Path] = []
    current = path
    while True:
        components.append(current)
        if _normalized_path(current) == _normalized_path(stop):
            break
        parent = current.parent
        _require(parent != current, "RAW_ROOT_IDENTITY_DRIFT")
        current = parent
    return tuple(reversed(components))


def _require_ignored_local_root(repository_root: Path) -> None:
    ignore_path = repository_root / ".gitignore"
    _require(ignore_path.is_file() and not ignore_path.is_symlink(), "RAW_ROOT_NOT_IGNORED")
    entries = {
        line.strip()
        for line in ignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    _require(bool(entries & {"local/", "/local/", "local/**"}), "RAW_ROOT_NOT_IGNORED")


def _raw_manifest_valid(
    run_root: Path,
    run_id: str,
    reference: object,
    *,
    notifications: int,
    stream_bytes: int,
) -> bool:
    if not isinstance(reference, Mapping) or set(reference) != {
        "path",
        "bytes",
        "sha256",
    }:
        return False
    if (
        type(reference.get("path")) is not str
        or reference.get("path") != "raw_manifest.json"
        or not _nonnegative_int(reference.get("bytes"))
        or type(reference.get("sha256")) is not str
        or _SHA256_RE.fullmatch(reference["sha256"]) is None
    ):
        return False
    manifest_path = run_root / "raw_manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return False
    try:
        manifest_body = manifest_path.read_bytes()
        manifest = _closed_json_loads(manifest_body.decode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        return False
    if (
        len(manifest_body) != reference["bytes"]
        or hashlib.sha256(manifest_body).hexdigest() != reference["sha256"]
        or not isinstance(manifest, Mapping)
        or set(manifest)
        != {
            "schema",
            "schema_version",
            "run_id",
            "logical_run_root",
            "retention_class",
            "raw_objects",
            "notifications",
            "stream_bytes",
        }
        or manifest.get("schema") != "smial.task30.forward-stream-raw-manifest"
        or manifest.get("schema_version") != "1.0"
        or manifest.get("run_id") != run_id
        or manifest.get("logical_run_root") != f"{LOGICAL_ROOT}/run={run_id}"
        or manifest.get("retention_class") != "A4"
        or type(manifest.get("notifications")) is not int
        or manifest.get("notifications") != notifications
        or type(manifest.get("stream_bytes")) is not int
        or manifest.get("stream_bytes") != stream_bytes
    ):
        return False
    raw_objects = manifest.get("raw_objects")
    if type(raw_objects) is not list or len(raw_objects) != notifications + 1:
        return False
    expected_paths = ["acknowledgement.json"] + [
        f"notifications/{ordinal:06d}.json"
        for ordinal in range(1, notifications + 1)
    ]
    retained_bytes = 0
    for item, expected_path in zip(raw_objects, expected_paths):
        if (
            not isinstance(item, Mapping)
            or set(item) != {"path", "bytes", "sha256", "observed_at"}
            or type(item.get("path")) is not str
            or item.get("path") != expected_path
            or not _nonnegative_int(item.get("bytes"))
            or type(item.get("sha256")) is not str
            or _SHA256_RE.fullmatch(item["sha256"]) is None
        ):
            return False
        observed_at = item.get("observed_at")
        if observed_at is None:
            if item["bytes"] != 0:
                return False
        else:
            observed = _receipt_utc(observed_at)
            if observed is None:
                return False
        object_path = run_root / Path(expected_path)
        if not object_path.is_file() or object_path.is_symlink():
            return False
        try:
            body = object_path.read_bytes()
        except OSError:
            return False
        if (
            len(body) != item["bytes"]
            or hashlib.sha256(body).hexdigest() != item["sha256"]
        ):
            return False
        retained_bytes += len(body)
    return retained_bytes == stream_bytes


def _terminal_receipt_valid(run_root: Path, run_id: str) -> bool:
    path = run_root / "terminal_receipt.json"
    if not path.is_file() or path.is_symlink():
        return False
    try:
        value = _closed_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return False
    if (
        not isinstance(value, Mapping)
        or set(value) != _TERMINAL_RECEIPT_FIELDS
        or type(run_id) is not str
        or _RUN_ID_RE.fullmatch(run_id) is None
    ):
        return False
    started_at = _receipt_utc(value.get("started_at"))
    terminal_at = _receipt_utc(value.get("terminal_at"))
    terminal_state = value.get("terminal_state")
    if not (
        value.get("schema") == "smial.task30.forward-stream-terminal-receipt"
        and value.get("schema_version") == "1.0"
        and value.get("run_id") == run_id
        and value.get("logical_run_root") == f"{LOGICAL_ROOT}/run={run_id}"
        and value.get("state") == "TERMINAL"
        and type(terminal_state) is str
        and terminal_state in _TERMINAL_STATES
        and started_at is not None
        and terminal_at is not None
        and terminal_at >= started_at
        and _nonnegative_int(value.get("notifications"))
        and _nonnegative_int(value.get("stream_bytes"))
        and _nonnegative_int(value.get("estimated_credits"))
        and type(value.get("unknown")) is bool
        and value.get("unknown") == (terminal_state == "TRANSPORT_LOST_UNKNOWN")
        and type(value.get("retry")) is bool
        and value.get("retry") is False
        and type(value.get("reconnect")) is bool
        and value.get("reconnect") is False
        and type(value.get("interval_projectable")) is bool
        and value.get("interval_projectable") is False
        and type(value.get("zero_volume")) is bool
        and value.get("zero_volume") is False
        and type(value.get("empty_interval")) is bool
        and value.get("empty_interval") is False
        and type(value.get("task30_trial")) is bool
        and value.get("task30_trial") is False
    ):
        return False
    raw_retention = value.get("raw_retention")
    raw_manifest = value.get("raw_manifest")
    if raw_retention == "A4_EXACT_RETAINED":
        return _raw_manifest_valid(
            run_root,
            run_id,
            raw_manifest,
            notifications=value["notifications"],
            stream_bytes=value["stream_bytes"],
        )
    if raw_retention == "FAILED":
        return terminal_state == "RETENTION_FAILED_STOP" and raw_manifest is None
    if raw_retention == "NO_CAPTURE_RETURNED":
        return (
            terminal_state
            in {"CONNECTION_OR_AUTH_REJECTED", "TRANSPORT_LOST_UNKNOWN"}
            and raw_manifest is None
        )
    return False


def find_unresolved_attempts(raw_root: Path) -> tuple[str, ...]:
    """Return create-only runs whose durable terminal truth is absent or invalid."""

    _require(isinstance(raw_root, Path), "RAW_ROOT_PATH_REQUIRED")
    if not raw_root.exists():
        return ()
    _require(raw_root.is_dir() and not raw_root.is_symlink(), "RAW_ROOT_SYMLINK_FORBIDDEN")
    unresolved: list[str] = []
    for run_root in sorted(raw_root.glob("run=*"), key=lambda item: item.name):
        _require(run_root.is_dir() and not run_root.is_symlink(), "RUN_ROOT_INVALID")
        run_id = run_root.name.removeprefix("run=")
        marker = run_root / "attempt_started.json"
        if marker.exists() and not _terminal_receipt_valid(run_root, run_id):
            unresolved.append(run_id)
    return tuple(unresolved)


def _prior_attempt_ids(raw_root: Path) -> tuple[str, ...]:
    if not raw_root.exists():
        return ()
    _require(raw_root.is_dir() and not raw_root.is_symlink(), "RAW_ROOT_SYMLINK_FORBIDDEN")
    attempts: list[str] = []
    for run_root in sorted(raw_root.glob("run=*"), key=lambda item: item.name):
        _require(run_root.is_dir() and not run_root.is_symlink(), "RUN_ROOT_INVALID")
        attempts.append(run_root.name.removeprefix("run="))
    return tuple(attempts)


def validate_forward_stream_preflight(
    execution_config: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    *,
    authority_phrase: str,
    repository_root: Path,
    raw_root: Path,
) -> dict[str, object]:
    """Validate all non-secret conditions without creating output or reading a key."""

    _require(
        _same_exact(execution_config, _EXPECTED_EXECUTION_POLICY),
        "EXECUTION_POLICY_DRIFT",
    )
    try:
        evaluate_forward_stream_runtime(runtime_config)
    except ForwardStreamRuntimeError as exc:
        raise ForwardStreamExecutionError(str(exc)) from exc
    _require(
        type(authority_phrase) is str and authority_phrase == OWNER_EXECUTION_PHRASE,
        "PILOT_NOT_AUTHORIZED",
    )
    _require(
        isinstance(repository_root, Path) and repository_root.is_absolute(),
        "REPOSITORY_ROOT_ABSOLUTE_REQUIRED",
    )
    _require(
        repository_root.is_dir() and not repository_root.is_symlink(),
        "REPOSITORY_ROOT_INVALID",
    )
    _require(
        isinstance(raw_root, Path) and raw_root.is_absolute(),
        "RAW_ROOT_ABSOLUTE_REQUIRED",
    )
    expected_raw_root = repository_root / Path(LOGICAL_ROOT)
    _require(
        _normalized_path(raw_root) == _normalized_path(expected_raw_root),
        "RAW_ROOT_IDENTITY_DRIFT",
    )
    for component in _existing_components(raw_root, repository_root):
        if component.exists() or component.is_symlink():
            _require(not component.is_symlink(), "RAW_ROOT_SYMLINK_FORBIDDEN")
    _require_ignored_local_root(repository_root)
    _require(not find_unresolved_attempts(raw_root), "UNRESOLVED_PRIOR_ATTEMPT")
    _require(not _prior_attempt_ids(raw_root), "PRIOR_ATTEMPT_REQUIRES_NEW_GATE")
    planned_request = bind_transaction_subscribe("offline-preflight-sentinel")
    return {
        "result": "PREFLIGHT_PASS",
        "logical_root": LOGICAL_ROOT,
        "credential_read": False,
        "network_calls": 0,
        "output_created": False,
        "planned_request": planned_request.safe_receipt(),
    }


@dataclass(frozen=True, slots=True, repr=False)
class StartedAttempt:
    """Sanitized durable identity published before any credential lookup."""

    run_id: str
    run_root: Path = field(repr=False)
    logical_run_root: str
    started_at: datetime
    planned_request_receipt: Mapping[str, object]

    def __repr__(self) -> str:
        return (
            "StartedAttempt("
            f"run_id={self.run_id!r}, "
            f"logical_run_root={self.logical_run_root!r}, "
            f"started_at={_utc_text(self.started_at)!r}, "
            "planned_request_receipt=<sanitized>)"
        )


def _publish_new(path: Path, body: bytes) -> None:
    _require(isinstance(body, bytes), "RECEIPT_BYTES_INVALID")
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except (FileExistsError, OSError) as exc:
        raise ForwardStreamExecutionError("CREATE_ONLY_PUBLICATION_FAILED") from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def prepare_forward_stream_attempt(
    execution_config: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    *,
    authority_phrase: str,
    repository_root: Path,
    raw_root: Path,
    now: datetime,
    nonce: str,
) -> StartedAttempt:
    """Publish one unresolved marker before any credential or transport action."""

    preflight = validate_forward_stream_preflight(
        execution_config,
        runtime_config,
        authority_phrase=authority_phrase,
        repository_root=repository_root,
        raw_root=raw_root,
    )
    started_text = _utc_text(now)
    _require(type(nonce) is str and _NONCE_RE.fullmatch(nonce) is not None, "NONCE_INVALID")
    run_id = f"{now.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}-{nonce}"
    logical_run_root = f"{LOGICAL_ROOT}/run={run_id}"

    try:
        raw_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ForwardStreamExecutionError("RAW_ROOT_CREATE_FAILED") from exc
    for component in _existing_components(raw_root, repository_root):
        _require(not component.is_symlink(), "RAW_ROOT_SYMLINK_FORBIDDEN")
    run_root = raw_root / f"run={run_id}"
    try:
        run_root.mkdir()
    except FileExistsError as exc:
        raise ForwardStreamExecutionError("RUN_ID_COLLISION") from exc
    except OSError as exc:
        raise ForwardStreamExecutionError("RUN_ROOT_CREATE_FAILED") from exc

    planned_request = preflight["planned_request"]
    _require(isinstance(planned_request, Mapping), "PLANNED_REQUEST_INVALID")
    marker = {
        "schema": "smial.task30.forward-stream-attempt-started",
        "schema_version": "1.0",
        "run_id": run_id,
        "logical_run_root": logical_run_root,
        "started_at": started_text,
        "state": "UNRESOLVED_EXTERNAL_ATTEMPT",
        "target": dict(runtime_config["target"]),
        "runtime_limits": dict(runtime_config["runtime_limits"]),
        "planned_request": dict(planned_request),
    }
    _publish_new(run_root / "attempt_started.json", _canonical_json(marker))
    return StartedAttempt(
        run_id=run_id,
        run_root=run_root,
        logical_run_root=logical_run_root,
        started_at=now,
        planned_request_receipt=MappingProxyType(dict(planned_request)),
    )


def _capture_metrics(
    runtime_config: Mapping[str, Any], capture: WssCapture
) -> tuple[int, int]:
    try:
        evaluate_forward_stream_runtime(runtime_config)
    except ForwardStreamRuntimeError as exc:
        raise ForwardStreamExecutionError(str(exc)) from exc
    _require(type(capture) is WssCapture, "WSS_CAPTURE_TYPE_INVALID")
    limits = runtime_config["runtime_limits"]
    _require(isinstance(limits, Mapping), "RUNTIME_LIMITS_REQUIRED")
    stream_bytes = len(capture.acknowledgement) + sum(
        len(item) for item in capture.notifications
    )
    _require(stream_bytes <= limits["max_stream_bytes"], "STREAM_BYTE_CAP_EXCEEDED")
    _require(
        len(capture.notifications) <= limits["max_notifications"],
        "NOTIFICATION_CAP_EXCEEDED",
    )
    _require(
        len(capture.acknowledgement) <= limits["max_frame_bytes"],
        "ACK_FRAME_CAP_EXCEEDED",
    )
    _require(
        all(len(item) <= limits["max_frame_bytes"] for item in capture.notifications),
        "NOTIFICATION_FRAME_CAP_EXCEEDED",
    )
    estimated_credits = CONNECTION_CREDITS + math.ceil(
        stream_bytes / limits["credit_bytes_per_unit"]
    ) * limits["credits_per_unit"]
    _require(
        estimated_credits <= limits["estimated_credit_cap"],
        "CREDIT_CAP_EXCEEDED",
    )
    return stream_bytes, estimated_credits


def _closed_classification(
    terminal_state: str,
    *,
    notifications: int,
    stream_bytes: int,
    estimated_credits: int,
    unknown: bool,
) -> dict[str, object]:
    return {
        "terminal_state": terminal_state,
        "notifications": notifications,
        "stream_bytes": stream_bytes,
        "estimated_credits": estimated_credits,
        "unknown": unknown,
        "retry": False,
        "reconnect": False,
        "interval_projectable": False,
        "zero_volume": False,
        "empty_interval": False,
        "task30_trial": False,
    }


def classify_task08_capture(
    runtime_config: Mapping[str, Any], capture: WssCapture
) -> dict[str, object]:
    """Map TASK-08 transport truth into the accepted A14 terminal vocabulary."""

    stream_bytes, estimated_credits = _capture_metrics(runtime_config, capture)
    if capture.terminal_class != "BOUND_REACHED":
        return _closed_classification(
            "TRANSPORT_LOST_UNKNOWN",
            notifications=len(capture.notifications),
            stream_bytes=stream_bytes,
            estimated_credits=estimated_credits,
            unknown=True,
        )
    runtime_capture = RuntimeCapture(
        acknowledgement=capture.acknowledgement,
        notifications=capture.notifications,
        terminal_class="BOUND_REACHED",
        error_class=None,
    )
    try:
        result = classify_forward_stream_capture(runtime_config, runtime_capture)
    except ForwardStreamRuntimeError as exc:
        if str(exc) == "SUBSCRIPTION_REJECTED":
            return _closed_classification(
                "SUBSCRIPTION_REJECTED",
                notifications=len(capture.notifications),
                stream_bytes=stream_bytes,
                estimated_credits=estimated_credits,
                unknown=False,
            )
        raise ForwardStreamExecutionError(str(exc)) from exc
    return dict(result)


def _raw_object(path: Path, *, relative_path: str, observed_at: datetime | None) -> dict[str, object]:
    try:
        body = path.read_bytes()
    except OSError as exc:
        raise ForwardStreamExecutionError("RAW_OBJECT_VERIFY_FAILED") from exc
    return {
        "path": relative_path,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "observed_at": None if observed_at is None else _utc_text(observed_at),
    }


def _retain_exact_capture(attempt: StartedAttempt, capture: WssCapture) -> dict[str, object]:
    acknowledgement_path = attempt.run_root / "acknowledgement.json"
    _publish_new(acknowledgement_path, capture.acknowledgement)
    raw_objects = [
        _raw_object(
            acknowledgement_path,
            relative_path="acknowledgement.json",
            observed_at=capture.acknowledgement_observed_at,
        )
    ]

    notification_root = attempt.run_root / "notifications"
    try:
        notification_root.mkdir()
    except OSError as exc:
        raise ForwardStreamExecutionError("NOTIFICATION_ROOT_CREATE_FAILED") from exc
    for ordinal, (body, observed_at) in enumerate(
        zip(capture.notifications, capture.notification_observed_at), start=1
    ):
        relative_path = f"notifications/{ordinal:06d}.json"
        path = attempt.run_root / Path(relative_path)
        _publish_new(path, body)
        raw_objects.append(
            _raw_object(path, relative_path=relative_path, observed_at=observed_at)
        )

    manifest = {
        "schema": "smial.task30.forward-stream-raw-manifest",
        "schema_version": "1.0",
        "run_id": attempt.run_id,
        "logical_run_root": attempt.logical_run_root,
        "retention_class": "A4",
        "raw_objects": raw_objects,
        "notifications": len(capture.notifications),
        "stream_bytes": len(capture.acknowledgement)
        + sum(len(item) for item in capture.notifications),
    }
    manifest_body = _canonical_json(manifest)
    manifest_path = attempt.run_root / "raw_manifest.json"
    _publish_new(manifest_path, manifest_body)
    try:
        retained_manifest = manifest_path.read_bytes()
    except OSError as exc:
        raise ForwardStreamExecutionError("RAW_MANIFEST_VERIFY_FAILED") from exc
    _require(retained_manifest == manifest_body, "RAW_MANIFEST_VERIFY_FAILED")
    return {
        "document": manifest,
        "path": "raw_manifest.json",
        "bytes": len(retained_manifest),
        "sha256": hashlib.sha256(retained_manifest).hexdigest(),
    }


def _publish_terminal_receipt(
    attempt: StartedAttempt,
    classification: Mapping[str, object],
    *,
    terminal_at: datetime,
    manifest: Mapping[str, object] | None,
) -> dict[str, object]:
    terminal_text = _utc_text(terminal_at)
    terminal_state = classification.get("terminal_state")
    _require(terminal_state in _TERMINAL_STATES, "TERMINAL_STATE_INVALID")
    receipt: dict[str, object] = {
        "schema": "smial.task30.forward-stream-terminal-receipt",
        "schema_version": "1.0",
        "run_id": attempt.run_id,
        "logical_run_root": attempt.logical_run_root,
        "started_at": _utc_text(attempt.started_at),
        "terminal_at": terminal_text,
        "state": "TERMINAL",
        "terminal_state": terminal_state,
        "notifications": classification.get("notifications", 0),
        "stream_bytes": classification.get("stream_bytes", 0),
        "estimated_credits": classification.get("estimated_credits", 0),
        "unknown": classification.get("unknown", False),
        "retry": False,
        "reconnect": False,
        "interval_projectable": False,
        "zero_volume": False,
        "empty_interval": False,
        "task30_trial": False,
        "raw_retention": (
            "A4_EXACT_RETAINED"
            if manifest is not None
            else (
                "FAILED"
                if terminal_state == "RETENTION_FAILED_STOP"
                else "NO_CAPTURE_RETURNED"
            )
        ),
        "raw_manifest": (
            None
            if manifest is None
            else {
                "path": manifest["path"],
                "bytes": manifest["bytes"],
                "sha256": manifest["sha256"],
            }
        ),
    }
    try:
        _publish_new(
            attempt.run_root / "terminal_receipt.json", _canonical_json(receipt)
        )
    except ForwardStreamExecutionError as exc:
        raise ForwardStreamExecutionError("UNRESOLVED_EXTERNAL_ATTEMPT") from exc
    if not _terminal_receipt_valid(attempt.run_root, attempt.run_id):
        raise ForwardStreamExecutionError("UNRESOLVED_EXTERNAL_ATTEMPT")
    return receipt


def execute_forward_stream_attempt(
    execution_config: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    *,
    authority_phrase: str,
    repository_root: Path,
    raw_root: Path,
    credential_loader: Callable[[str], str],
    wss_exchange: Callable[..., object],
    clock: Callable[[], datetime],
    nonce_factory: Callable[[], str],
) -> dict[str, object]:
    """Execute exactly one injected exchange after publishing durable intent."""

    attempt = prepare_forward_stream_attempt(
        execution_config,
        runtime_config,
        authority_phrase=authority_phrase,
        repository_root=repository_root,
        raw_root=raw_root,
        now=clock(),
        nonce=nonce_factory(),
    )
    try:
        credential_value = credential_loader("HELIUS_API_KEY")
        request = bind_transaction_subscribe(credential_value)
    except (KeyError, ForwardStreamRuntimeError):
        return _publish_terminal_receipt(
            attempt,
            _closed_classification(
                "CONNECTION_OR_AUTH_REJECTED",
                notifications=0,
                stream_bytes=0,
                estimated_credits=0,
                unknown=False,
            ),
            terminal_at=clock(),
            manifest=None,
        )
    except Exception:
        raise ForwardStreamExecutionError("UNCLASSIFIED_LOCAL_FAILURE") from None

    _require(
        request.safe_receipt() == dict(attempt.planned_request_receipt),
        "REQUEST_RECEIPT_DRIFT",
    )
    try:
        capture = wss_exchange(
            request,
            max_open_seconds=MAX_OPEN_SECONDS,
            max_stream_bytes=MAX_STREAM_BYTES,
            max_notifications=MAX_NOTIFICATIONS,
        )
    except Exception:
        return _publish_terminal_receipt(
            attempt,
            _closed_classification(
                "TRANSPORT_LOST_UNKNOWN",
                notifications=0,
                stream_bytes=0,
                estimated_credits=CONNECTION_CREDITS,
                unknown=True,
            ),
            terminal_at=clock(),
            manifest=None,
        )
    _require(type(capture) is WssCapture, "WSS_CAPTURE_TYPE_INVALID")
    _capture_metrics(runtime_config, capture)

    try:
        manifest = _retain_exact_capture(attempt, capture)
    except ForwardStreamExecutionError:
        return _publish_terminal_receipt(
            attempt,
            _closed_classification(
                "RETENTION_FAILED_STOP",
                notifications=0,
                stream_bytes=0,
                estimated_credits=CONNECTION_CREDITS,
                unknown=False,
            ),
            terminal_at=clock(),
            manifest=None,
        )
    except Exception:
        raise ForwardStreamExecutionError("UNCLASSIFIED_LOCAL_FAILURE") from None
    classification = classify_task08_capture(runtime_config, capture)
    return _publish_terminal_receipt(
        attempt,
        classification,
        terminal_at=clock(),
        manifest=manifest,
    )
