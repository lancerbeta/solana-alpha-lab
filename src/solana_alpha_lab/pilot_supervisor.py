"""Bounded offline process supervisor for the TASK-12 cheapest falsifier."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

CONTRACT_VERSION: Final = "1.0"
CONSUMER_ASSET_ID: Final = "SCRIPT-T11-ENTITY-INPUT-PROBE-001"
LAUNCHER_REPOSITORY_PATH: Final = "scripts/run_task11_entity_input_probe.py"
PLAN_REPOSITORY_PATH: Final = (
    "tests/fixtures/task11/entity_input_pilot_plan_v1.json"
)
EXPECTED_SUCCESS_MARKER: Final = "TASK11_ENTITY_PROBE_PREFLIGHT: PASS"
LOGICAL_TARGET_SCOPE: Final = "TASK11_ENTITY_INPUT_OFFLINE_PREFLIGHT"
FORBIDDEN_ARGUMENTS: Final = frozenset({"--execute", "--replay-run"})
TERMINAL_STATES: Final = frozenset(
    {
        "SUCCEEDED",
        "FAILED",
        "TIMED_OUT",
        "STOPPED",
        "BLOCKED_DUPLICATE",
        "BLOCKED_DISK",
    }
)
_UTC_WINDOW_RE: Final = re.compile(
    r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
_SAFE_ENV_KEYS: Final = (
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
)


class PilotSupervisorError(ValueError):
    """Raised when a caller violates the frozen offline contract."""


@dataclass(frozen=True)
class SupervisorLimits:
    """Runtime caps that may only tighten the frozen contract."""

    spawn_grace_seconds: float = 5.0
    silence_seconds_max: float = 30.0
    child_wall_seconds_max: float = 60.0
    poll_interval_seconds: float = 0.2
    graceful_stop_seconds: float = 5.0
    line_bytes_max: int = 16_384
    child_output_bytes_max: int = 262_144
    predicted_child_write_bytes_max: int = 0
    start_reserve_fixed_bytes: int = 536_870_912
    runtime_reserve_fixed_bytes: int = 268_435_456

    def validate(self) -> None:
        numeric_caps = (
            self.spawn_grace_seconds,
            self.silence_seconds_max,
            self.child_wall_seconds_max,
            self.poll_interval_seconds,
            self.graceful_stop_seconds,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value <= 0
            for value in numeric_caps
        ):
            raise PilotSupervisorError("invalid_time_limit")
        if self.spawn_grace_seconds > 5:
            raise PilotSupervisorError("spawn_grace_exceeds_contract")
        if self.silence_seconds_max > 30:
            raise PilotSupervisorError("silence_limit_exceeds_contract")
        if self.child_wall_seconds_max > 60:
            raise PilotSupervisorError("wall_limit_exceeds_contract")
        if self.poll_interval_seconds < 0.2:
            raise PilotSupervisorError("poll_interval_below_contract")
        if self.graceful_stop_seconds > 5:
            raise PilotSupervisorError("stop_grace_exceeds_contract")
        integer_caps = (
            self.line_bytes_max,
            self.child_output_bytes_max,
            self.predicted_child_write_bytes_max,
            self.start_reserve_fixed_bytes,
            self.runtime_reserve_fixed_bytes,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in integer_caps
        ):
            raise PilotSupervisorError("invalid_byte_limit")
        if not 0 < self.line_bytes_max <= 16_384:
            raise PilotSupervisorError("line_limit_exceeds_contract")
        if not 0 < self.child_output_bytes_max <= 262_144:
            raise PilotSupervisorError("output_limit_exceeds_contract")
        if self.start_reserve_fixed_bytes < 536_870_912:
            raise PilotSupervisorError("start_reserve_below_contract")
        if self.runtime_reserve_fixed_bytes < 268_435_456:
            raise PilotSupervisorError("runtime_reserve_below_contract")

    @property
    def start_required_bytes(self) -> int:
        return (
            2 * self.predicted_child_write_bytes_max
            + self.start_reserve_fixed_bytes
        )

    @property
    def runtime_required_bytes(self) -> int:
        return (
            self.predicted_child_write_bytes_max
            + self.runtime_reserve_fixed_bytes
        )


@dataclass(frozen=True)
class ChildSpec:
    """Fixed offline TASK-11 consumer definition."""

    consumer_asset_id: str
    launcher_repository_path: str
    plan_sha256: str
    logical_target_scope: str
    expected_success_marker: str
    python_executable: Path

    @property
    def sanitized_argv(self) -> tuple[str, ...]:
        return (
            "{python}",
            "-B",
            self.launcher_repository_path,
        )

    def actual_argv(self, repo_root: Path) -> tuple[str, ...]:
        launcher = _contained_repository_path(
            repo_root,
            self.launcher_repository_path,
        )
        return (str(self.python_executable), "-B", str(launcher))

    def validate(self, repo_root: Path) -> None:
        if self.consumer_asset_id != CONSUMER_ASSET_ID:
            raise PilotSupervisorError("consumer_not_allowlisted")
        if self.launcher_repository_path != LAUNCHER_REPOSITORY_PATH:
            raise PilotSupervisorError("launcher_not_allowlisted")
        if self.logical_target_scope != LOGICAL_TARGET_SCOPE:
            raise PilotSupervisorError("target_scope_not_allowlisted")
        if self.expected_success_marker != EXPECTED_SUCCESS_MARKER:
            raise PilotSupervisorError("success_marker_mismatch")
        if re.fullmatch(r"[0-9a-f]{64}", self.plan_sha256) is None:
            raise PilotSupervisorError("plan_sha256_invalid")
        if not self.python_executable.is_file():
            raise PilotSupervisorError("python_executable_missing")
        argv = self.actual_argv(repo_root)
        if any(value in FORBIDDEN_ARGUMENTS for value in argv):
            raise PilotSupervisorError("external_argument_forbidden")


@dataclass(frozen=True)
class RunIdentity:
    run_id: str
    duplicate_key: str
    canonical_inputs: Mapping[str, object]


@dataclass(frozen=True)
class SupervisorResult:
    run_id: str
    duplicate_key: str
    child_run_id: str | None
    consumer_asset_id: str
    launcher_repository_path: str
    child_plan_sha256: str
    sanitized_argv: tuple[str, ...]
    attempt_sequence: int
    state: str
    reason: str | None
    child_exit_code: int | None
    child_spawn_count: int
    stdout_bytes: int
    stderr_bytes: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_sha256_scope: str
    stderr_sha256_scope: str
    success_marker_observed: bool
    provider_calls: int
    raw_data_writes: int
    cash_spend_usd_cents: int
    child_start_timestamp: str | None
    child_observation_timestamp: str | None
    child_availability_timestamp: str
    events: tuple[Mapping[str, object], ...]

    def to_receipt(self) -> dict[str, object]:
        return {
            "schema": "solana_alpha_lab.pilot_supervisor_receipt",
            "schema_version": "1.0",
            "run_id": self.run_id,
            "duplicate_key": self.duplicate_key,
            "consumer_asset_id": self.consumer_asset_id,
            "attempt_sequence": self.attempt_sequence,
            "state": self.state,
            "reason": self.reason,
            "child_exit_code": self.child_exit_code,
            "child_spawn_count": self.child_spawn_count,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "stdout_sha256_scope": self.stdout_sha256_scope,
            "stderr_sha256_scope": self.stderr_sha256_scope,
            "success_marker_observed": self.success_marker_observed,
            "provider_calls": self.provider_calls,
            "raw_data_writes": self.raw_data_writes,
            "cash_spend_usd_cents": self.cash_spend_usd_cents,
            "retry_count": 0,
            "lineage": {
                "parent_run_id": self.run_id,
                "child_run_id": self.child_run_id,
                "consumer_asset_id": self.consumer_asset_id,
                "launcher_repository_path": self.launcher_repository_path,
                "child_plan_sha256": self.child_plan_sha256,
                "sanitized_argv": list(self.sanitized_argv),
                "child_start_timestamp": self.child_start_timestamp,
                "child_observation_timestamp": (
                    self.child_observation_timestamp
                ),
                "child_availability_timestamp": (
                    self.child_availability_timestamp
                ),
                "accepted_child_receipt_sha256": None,
                "accepted_child_manifest_sha256": None,
                "restart_backdates_availability": False,
            },
            "events": [dict(event) for event in self.events],
        }


ProcessFactory = Callable[
    [ChildSpec, Path, Mapping[str, str]],
    subprocess.Popen[bytes],
]


def canonical_json_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PilotSupervisorError("canonical_json_invalid") from exc
    return text.encode("utf-8")


def build_run_identity(
    spec: ChildSpec,
    *,
    utc_window_start: str,
    attempt_sequence: int,
) -> RunIdentity:
    if _UTC_WINDOW_RE.fullmatch(utc_window_start) is None:
        raise PilotSupervisorError("utc_window_start_invalid")
    if (
        isinstance(attempt_sequence, bool)
        or not isinstance(attempt_sequence, int)
        or attempt_sequence < 1
    ):
        raise PilotSupervisorError("attempt_sequence_invalid")
    duplicate_inputs = {
        "consumer_asset_id": spec.consumer_asset_id,
        "child_plan_sha256": spec.plan_sha256,
        "logical_target_scope": spec.logical_target_scope,
        "utc_window_start": utc_window_start,
    }
    duplicate_key = hashlib.sha256(
        canonical_json_bytes(duplicate_inputs)
    ).hexdigest()
    run_inputs: dict[str, object] = {
        "contract_version": CONTRACT_VERSION,
        **duplicate_inputs,
        "attempt_sequence": attempt_sequence,
    }
    run_id = "t12-" + hashlib.sha256(
        canonical_json_bytes(run_inputs)
    ).hexdigest()
    return RunIdentity(
        run_id=run_id,
        duplicate_key=duplicate_key,
        canonical_inputs=run_inputs,
    )


def make_task11_offline_spec(
    repo_root: Path,
    *,
    python_executable: Path,
) -> ChildSpec:
    root = repo_root.resolve()
    plan = _contained_repository_path(root, PLAN_REPOSITORY_PATH)
    spec = ChildSpec(
        consumer_asset_id=CONSUMER_ASSET_ID,
        launcher_repository_path=LAUNCHER_REPOSITORY_PATH,
        plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
        logical_target_scope=LOGICAL_TARGET_SCOPE,
        expected_success_marker=EXPECTED_SUCCESS_MARKER,
        # Preserve the virtual-environment launcher path. On POSIX,
        # resolving its symlink selects the base interpreter and loses the
        # environment's installed packages.
        python_executable=python_executable.absolute(),
    )
    spec.validate(root)
    return spec


def safe_subprocess_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    candidate = os.environ if source is None else source
    result = {
        key: candidate[key]
        for key in _SAFE_ENV_KEYS
        if key in candidate and isinstance(candidate[key], str)
    }
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    result["PYTHONUTF8"] = "1"
    return result


def _contained_repository_path(repo_root: Path, relative: str) -> Path:
    if (
        not relative
        or Path(relative).is_absolute()
        or "\\" in relative
        or ".." in Path(relative).parts
    ):
        raise PilotSupervisorError("repository_path_invalid")
    root = repo_root.resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise PilotSupervisorError("repository_path_not_contained")
    return candidate


def _utc_timestamp(now: datetime) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise PilotSupervisorError("timestamp_must_be_timezone_aware")
    return now.astimezone(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


class AtomicDuplicateLock:
    """Atomic fail-closed lock; stale locks are never stolen by age."""

    def __init__(
        self,
        root: Path,
        *,
        duplicate_key: str,
        run_id: str,
        process_start_token: str,
    ) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", duplicate_key) is None:
            raise PilotSupervisorError("duplicate_key_invalid")
        if re.fullmatch(r"t12-[0-9a-f]{64}", run_id) is None:
            raise PilotSupervisorError("run_id_invalid")
        if re.fullmatch(r"[0-9a-f]{64}", process_start_token) is None:
            raise PilotSupervisorError("process_start_token_invalid")
        self.root = root
        self.path = root / f"{duplicate_key}.lock"
        self.run_id = run_id
        self.process_start_token = process_start_token
        self.acquired = False

    def acquire(self) -> bool:
        self.root.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except FileExistsError:
            return False
        record = {
            "schema_version": "1.0",
            "lock_owner_run_id": self.run_id,
            "recorded_process_identity": os.getpid(),
            "recorded_process_start_token": self.process_start_token,
        }
        try:
            os.write(descriptor, canonical_json_bytes(record) + b"\n")
        except BaseException:
            os.close(descriptor)
            self.path.unlink(missing_ok=True)
            raise
        os.close(descriptor)
        self.acquired = True
        return True

    def release(self) -> bool:
        if not self.acquired:
            return False
        try:
            record = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if (
            record.get("lock_owner_run_id") != self.run_id
            or record.get("recorded_process_start_token")
            != self.process_start_token
        ):
            return False
        self.path.unlink(missing_ok=True)
        self.acquired = False
        return True


class _BoundedOutputCapture:
    def __init__(
        self,
        *,
        total_limit: int,
        line_limit: int,
        monotonic: Callable[[], float],
    ) -> None:
        self.total_limit = total_limit
        self.line_limit = line_limit
        self.monotonic = monotonic
        self._buffers = {"stdout": bytearray(), "stderr": bytearray()}
        self._seen = {"stdout": 0, "stderr": 0}
        self._line_lengths = {"stdout": 0, "stderr": 0}
        self._stored_total = 0
        self._reason: str | None = None
        self._last_activity = monotonic()
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self._streams: list[Any] = []

    def start(self, process: subprocess.Popen[bytes]) -> None:
        if process.stdout is None or process.stderr is None:
            raise PilotSupervisorError("child_pipes_required")
        for name, stream in (
            ("stdout", process.stdout),
            ("stderr", process.stderr),
        ):
            self._streams.append(stream)
            thread = threading.Thread(
                target=self._read_stream,
                args=(name, stream),
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def _read_stream(self, name: str, stream: Any) -> None:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                return
            with self._lock:
                self._last_activity = self.monotonic()
                self._seen[name] += len(chunk)
                self._check_line_limit(name, chunk)
                if (
                    sum(self._seen.values()) > self.total_limit
                    and self._reason is None
                ):
                    self._reason = "CHILD_OUTPUT_LIMIT_EXCEEDED"
                remaining = max(0, self.total_limit - self._stored_total)
                retained = chunk[:remaining]
                self._buffers[name].extend(retained)
                self._stored_total += len(retained)

    def _check_line_limit(self, name: str, chunk: bytes) -> None:
        parts = chunk.split(b"\n")
        if len(parts) == 1:
            self._line_lengths[name] += len(parts[0])
        else:
            self._line_lengths[name] += len(parts[0])
            if self._line_lengths[name] > self.line_limit:
                self._reason = self._reason or "CHILD_LINE_LIMIT_EXCEEDED"
            for part in parts[1:-1]:
                if len(part) > self.line_limit:
                    self._reason = (
                        self._reason or "CHILD_LINE_LIMIT_EXCEEDED"
                    )
            self._line_lengths[name] = len(parts[-1])
        if self._line_lengths[name] > self.line_limit:
            self._reason = self._reason or "CHILD_LINE_LIMIT_EXCEEDED"

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason

    @property
    def last_activity(self) -> float:
        with self._lock:
            return self._last_activity

    def counts(self) -> tuple[int, int]:
        with self._lock:
            return self._seen["stdout"], self._seen["stderr"]

    def finish(self) -> tuple[bytes, bytes, int, int]:
        for thread in self._threads:
            thread.join(timeout=1.0)
        for stream in self._streams:
            stream.close()
        with self._lock:
            return (
                bytes(self._buffers["stdout"]),
                bytes(self._buffers["stderr"]),
                self._seen["stdout"],
                self._seen["stderr"],
            )


class PilotSupervisor:
    """Run exactly one offline child under the frozen TASK-12 controls."""

    def __init__(
        self,
        *,
        repo_root: Path,
        lock_root: Path,
        limits: SupervisorLimits | None = None,
        disk_free_bytes: Callable[[Path], int] | None = None,
        process_factory: ProcessFactory | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        if not self.repo_root.is_dir():
            raise PilotSupervisorError("repo_root_missing")
        self.lock_root = lock_root
        self.limits = limits or SupervisorLimits()
        self.limits.validate()
        self.disk_free_bytes = disk_free_bytes or (
            lambda path: shutil.disk_usage(path).free
        )
        self.process_factory = process_factory or self._spawn_child
        self.now = now or (lambda: datetime.now(UTC))
        self.monotonic = monotonic or time.monotonic
        self.sleep = sleep or time.sleep

    def run(
        self,
        spec: ChildSpec,
        *,
        utc_window_start: str,
        attempt_sequence: int,
        stop_requested: Callable[[], bool] | None = None,
    ) -> SupervisorResult:
        spec.validate(self.repo_root)
        identity = build_run_identity(
            spec,
            utc_window_start=utc_window_start,
            attempt_sequence=attempt_sequence,
        )
        should_stop = stop_requested or (lambda: False)
        started_at = self.monotonic()
        events: list[Mapping[str, object]] = []
        child_spawn_count = 0
        process: subprocess.Popen[bytes] | None = None
        capture: _BoundedOutputCapture | None = None
        child_exit_code: int | None = None
        stdout = b""
        stderr = b""
        stdout_seen = 0
        stderr_seen = 0
        marker_observed = False
        state = "CREATED"
        reason: str | None = None
        disk_free = self._read_disk_free()

        def emit(
            event_type: str,
            event_state: str,
            *,
            event_reason: str | None = None,
            health_state: str | None = None,
        ) -> None:
            out_count, err_count = (
                capture.counts() if capture is not None else (0, 0)
            )
            events.append(
                {
                    "schema_version": "1.0",
                    "event_type": event_type,
                    "run_id": identity.run_id,
                    "consumer_asset_id": spec.consumer_asset_id,
                    "attempt_sequence": attempt_sequence,
                    "state": event_state,
                    "health_state": health_state,
                    "observed_at": _utc_timestamp(self.now()),
                    "monotonic_elapsed_ms": max(
                        0,
                        int((self.monotonic() - started_at) * 1000),
                    ),
                    "reason": event_reason,
                    "child_exit_code": (
                        process.poll() if process is not None else None
                    ),
                    "stdout_bytes": out_count,
                    "stderr_bytes": err_count,
                    "disk_free_bytes": disk_free,
                    "provider_calls": 0,
                    "cash_spend_usd_cents": 0,
                }
            )

        emit("SUPERVISOR_STARTED", state, health_state="STARTING")
        if should_stop():
            state = "STOPPED"
            reason = "STOP_REQUESTED"
            emit("STOP_REQUESTED", state, event_reason=reason)
            emit("SUPERVISOR_FINISHED", state, event_reason=reason)
            return self._result(
                identity,
                spec,
                attempt_sequence,
                state,
                reason,
                child_exit_code,
                child_spawn_count,
                stdout,
                stderr,
                stdout_seen,
                stderr_seen,
                marker_observed,
                events,
            )
        if (
            disk_free is None
            or disk_free < self.limits.start_required_bytes
        ):
            state = "BLOCKED_DISK"
            reason = "INSUFFICIENT_DISK_BEFORE_START"
            emit("SUPERVISOR_FINISHED", state, event_reason=reason)
            return self._result(
                identity,
                spec,
                attempt_sequence,
                state,
                reason,
                child_exit_code,
                child_spawn_count,
                stdout,
                stderr,
                stdout_seen,
                stderr_seen,
                marker_observed,
                events,
            )

        process_start_token = hashlib.sha256(
            canonical_json_bytes(
                {
                    "run_id": identity.run_id,
                    "process_identity": os.getpid(),
                    "monotonic_start": started_at,
                }
            )
        ).hexdigest()
        duplicate_lock = AtomicDuplicateLock(
            self.lock_root,
            duplicate_key=identity.duplicate_key,
            run_id=identity.run_id,
            process_start_token=process_start_token,
        )
        if not duplicate_lock.acquire():
            state = "BLOCKED_DUPLICATE"
            reason = "ACTIVE_DUPLICATE"
            emit("SUPERVISOR_FINISHED", state, event_reason=reason)
            return self._result(
                identity,
                spec,
                attempt_sequence,
                state,
                reason,
                child_exit_code,
                child_spawn_count,
                stdout,
                stderr,
                stdout_seen,
                stderr_seen,
                marker_observed,
                events,
            )

        try:
            state = "STARTING"
            emit("HEALTH_CHANGED", state, health_state="STARTING")
            try:
                process = self.process_factory(
                    spec,
                    self.repo_root,
                    safe_subprocess_environment(),
                )
            except (OSError, ValueError, subprocess.SubprocessError):
                state = "FAILED"
                reason = "CHILD_SPAWN_FAILED"
                emit("SUPERVISOR_FINISHED", state, event_reason=reason)
                return self._result(
                    identity,
                    spec,
                    attempt_sequence,
                    state,
                    reason,
                    child_exit_code,
                    child_spawn_count,
                    stdout,
                    stderr,
                    stdout_seen,
                    stderr_seen,
                    marker_observed,
                    events,
                )
            child_spawn_count = 1
            capture = _BoundedOutputCapture(
                total_limit=self.limits.child_output_bytes_max,
                line_limit=self.limits.line_bytes_max,
                monotonic=self.monotonic,
            )
            capture.start(process)
            state = "RUNNING"
            emit("CHILD_STARTED", state, health_state="HEALTHY")
            emit("HEALTH_CHANGED", state, health_state="HEALTHY")
            degraded_emitted = False
            forced_state: str | None = None
            forced_reason: str | None = None

            while process.poll() is None:
                elapsed = self.monotonic() - started_at
                output_reason = capture.reason
                if should_stop():
                    forced_state = "STOPPED"
                    forced_reason = "STOP_REQUESTED"
                elif output_reason is not None:
                    forced_state = "FAILED"
                    forced_reason = output_reason
                elif elapsed >= self.limits.child_wall_seconds_max:
                    forced_state = "TIMED_OUT"
                    forced_reason = "CHILD_WALL_TIMEOUT"
                else:
                    disk_free = self._read_disk_free()
                    if (
                        disk_free is None
                        or disk_free < self.limits.runtime_required_bytes
                    ):
                        forced_state = "BLOCKED_DISK"
                        forced_reason = "DISK_GUARD_BREACHED"
                if forced_state is not None:
                    emit(
                        "STOP_REQUESTED",
                        state,
                        event_reason=forced_reason,
                        health_state="UNHEALTHY",
                    )
                    self._stop_child(process)
                    break
                if (
                    not degraded_emitted
                    and self.monotonic() - capture.last_activity
                    >= self.limits.silence_seconds_max
                ):
                    degraded_emitted = True
                    emit(
                        "HEALTH_CHANGED",
                        state,
                        event_reason="SILENCE_THRESHOLD_EXCEEDED",
                        health_state="DEGRADED",
                    )
                self.sleep(self.limits.poll_interval_seconds)

            child_exit_code = process.wait()
            stdout, stderr, stdout_seen, stderr_seen = capture.finish()
            emit("CHILD_ACTIVITY", state)
            if forced_state is None and capture.reason is not None:
                forced_state = "FAILED"
                forced_reason = capture.reason
            try:
                stdout_text = stdout.decode("utf-8")
                stderr.decode("utf-8")
            except UnicodeDecodeError:
                forced_state = "FAILED"
                forced_reason = "INVALID_CHILD_OUTPUT"
                stdout_text = ""
            marker_observed = spec.expected_success_marker in stdout_text
            if forced_state is not None:
                state, reason = forced_state, forced_reason
            elif child_exit_code != 0:
                state, reason = "FAILED", "CHILD_EXIT_NONZERO"
            elif not marker_observed:
                state, reason = "FAILED", "EXPECTED_MARKER_MISSING"
            else:
                state, reason = "SUCCEEDED", None
            emit(
                "CHILD_EXITED",
                state,
                event_reason=reason,
                health_state=(
                    "STOPPED" if state in TERMINAL_STATES else "UNHEALTHY"
                ),
            )
            emit(
                "SUPERVISOR_FINISHED",
                state,
                event_reason=reason,
                health_state="STOPPED",
            )
            return self._result(
                identity,
                spec,
                attempt_sequence,
                state,
                reason,
                child_exit_code,
                child_spawn_count,
                stdout,
                stderr,
                stdout_seen,
                stderr_seen,
                marker_observed,
                events,
            )
        finally:
            duplicate_lock.release()

    def _read_disk_free(self) -> int | None:
        try:
            value = self.disk_free_bytes(self.repo_root)
        except (OSError, ValueError):
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    def _spawn_child(
        self,
        spec: ChildSpec,
        repo_root: Path,
        environment: Mapping[str, str],
    ) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            spec.actual_argv(repo_root),
            cwd=repo_root,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )

    def _stop_child(self, process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=self.limits.graceful_stop_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=self.limits.graceful_stop_seconds)

    @staticmethod
    def _result(
        identity: RunIdentity,
        spec: ChildSpec,
        attempt_sequence: int,
        state: str,
        reason: str | None,
        child_exit_code: int | None,
        child_spawn_count: int,
        stdout: bytes,
        stderr: bytes,
        stdout_seen: int,
        stderr_seen: int,
        marker_observed: bool,
        events: Sequence[Mapping[str, object]],
    ) -> SupervisorResult:
        if state not in TERMINAL_STATES:
            raise PilotSupervisorError("result_not_terminal")
        child_run_id = (
            "t12-child-"
            + hashlib.sha256(
                canonical_json_bytes(
                    {
                        "parent_run_id": identity.run_id,
                        "child_index": 1,
                    }
                )
            ).hexdigest()
            if child_spawn_count == 1
            else None
        )
        child_start_timestamp = next(
            (
                str(event["observed_at"])
                for event in events
                if event["event_type"] == "CHILD_STARTED"
            ),
            None,
        )
        child_observation_timestamp = next(
            (
                str(event["observed_at"])
                for event in reversed(events)
                if event["event_type"] == "CHILD_EXITED"
            ),
            None,
        )
        child_availability_timestamp = next(
            str(event["observed_at"])
            for event in reversed(events)
            if event["event_type"] == "SUPERVISOR_FINISHED"
        )
        return SupervisorResult(
            run_id=identity.run_id,
            duplicate_key=identity.duplicate_key,
            child_run_id=child_run_id,
            consumer_asset_id=spec.consumer_asset_id,
            launcher_repository_path=spec.launcher_repository_path,
            child_plan_sha256=spec.plan_sha256,
            sanitized_argv=spec.sanitized_argv,
            attempt_sequence=attempt_sequence,
            state=state,
            reason=reason,
            child_exit_code=child_exit_code,
            child_spawn_count=child_spawn_count,
            stdout_bytes=stdout_seen,
            stderr_bytes=stderr_seen,
            stdout_sha256=hashlib.sha256(stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(stderr).hexdigest(),
            stdout_sha256_scope=(
                "FULL_BYTES"
                if stdout_seen == len(stdout)
                else "RETAINED_PREFIX"
            ),
            stderr_sha256_scope=(
                "FULL_BYTES"
                if stderr_seen == len(stderr)
                else "RETAINED_PREFIX"
            ),
            success_marker_observed=marker_observed,
            provider_calls=0,
            raw_data_writes=0,
            cash_spend_usd_cents=0,
            child_start_timestamp=child_start_timestamp,
            child_observation_timestamp=child_observation_timestamp,
            child_availability_timestamp=child_availability_timestamp,
            events=tuple(dict(event) for event in events),
        )
