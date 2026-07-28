from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pilot_supervisor import (  # noqa: E402
    AtomicDuplicateLock,
    ChildSpec,
    PilotSupervisor,
    PilotSupervisorError,
    SupervisorLimits,
    build_run_identity,
    canonical_json_bytes,
    make_task11_offline_spec,
    safe_subprocess_environment,
)

WINDOW = "2026-07-28T12:00:00Z"
DISK_OK = 4_000_000_000


def _synthetic_factory(source: str) -> Callable[
    [ChildSpec, Path, Mapping[str, str]],
    subprocess.Popen[bytes],
]:
    def factory(
        _spec: ChildSpec,
        repo_root: Path,
        environment: Mapping[str, str],
    ) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            (sys.executable, "-B", "-c", source),
            cwd=repo_root,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )

    return factory


def _limits(**overrides: object) -> SupervisorLimits:
    values: dict[str, object] = {
        "spawn_grace_seconds": 1.0,
        "silence_seconds_max": 1.0,
        "child_wall_seconds_max": 2.0,
        "poll_interval_seconds": 0.2,
        "graceful_stop_seconds": 1.0,
        "line_bytes_max": 16_384,
        "child_output_bytes_max": 262_144,
        "predicted_child_write_bytes_max": 0,
        "start_reserve_fixed_bytes": 536_870_912,
        "runtime_reserve_fixed_bytes": 268_435_456,
    }
    values.update(overrides)
    return SupervisorLimits(**values)  # type: ignore[arg-type]


class Task12PilotSupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = make_task11_offline_spec(
            ROOT,
            python_executable=Path(sys.executable),
        )

    def _run_synthetic(
        self,
        source: str,
        *,
        limits: SupervisorLimits | None = None,
        disk_free: Callable[[Path], int] | None = None,
        stop_requested: Callable[[], bool] | None = None,
    ):
        with tempfile.TemporaryDirectory() as directory:
            supervisor = PilotSupervisor(
                repo_root=ROOT,
                lock_root=Path(directory) / "locks",
                limits=limits or _limits(),
                disk_free_bytes=disk_free or (lambda _path: DISK_OK),
                process_factory=_synthetic_factory(source),
            )
            return supervisor.run(
                self.spec,
                utc_window_start=WINDOW,
                attempt_sequence=1,
                stop_requested=stop_requested,
            )

    def test_run_identity_is_deterministic_and_restart_changes_only_attempt(
        self,
    ) -> None:
        first = build_run_identity(
            self.spec,
            utc_window_start=WINDOW,
            attempt_sequence=1,
        )
        repeated = build_run_identity(
            self.spec,
            utc_window_start=WINDOW,
            attempt_sequence=1,
        )
        restart = build_run_identity(
            self.spec,
            utc_window_start=WINDOW,
            attempt_sequence=2,
        )
        self.assertEqual(first, repeated)
        self.assertNotEqual(first.run_id, restart.run_id)
        self.assertEqual(first.duplicate_key, restart.duplicate_key)
        self.assertTrue(first.run_id.startswith("t12-"))
        self.assertEqual(len(first.duplicate_key), 64)

    def test_offline_spec_preserves_virtual_environment_launcher(self) -> None:
        expected = Path(sys.executable).absolute()
        self.assertEqual(self.spec.python_executable, expected)
        self.assertEqual(self.spec.actual_argv(ROOT)[0], str(expected))

    def test_identity_rejects_non_utc_window_and_zero_attempt(self) -> None:
        with self.assertRaisesRegex(
            PilotSupervisorError,
            "utc_window_start_invalid",
        ):
            build_run_identity(
                self.spec,
                utc_window_start="2026-07-28T12:00:00+03:00",
                attempt_sequence=1,
            )
        with self.assertRaisesRegex(
            PilotSupervisorError,
            "attempt_sequence_invalid",
        ):
            build_run_identity(
                self.spec,
                utc_window_start=WINDOW,
                attempt_sequence=0,
            )

    def test_safe_environment_is_allowlisted_and_drops_credentials(self) -> None:
        source = {
            "PATH": "synthetic-path",
            "SYSTEMROOT": "synthetic-root",
            "EXTERNAL_CREDENTIAL": "must-not-cross-process-boundary",
        }
        safe = safe_subprocess_environment(source)
        self.assertEqual(safe["PATH"], "synthetic-path")
        self.assertEqual(safe["SYSTEMROOT"], "synthetic-root")
        self.assertNotIn("EXTERNAL_CREDENTIAL", safe)
        self.assertEqual(safe["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(safe["PYTHONUTF8"], "1")

    def test_success_requires_zero_exit_and_exact_marker(self) -> None:
        result = self._run_synthetic(
            "print('TASK11_ENTITY_PROBE_PREFLIGHT: PASS')"
        )
        self.assertEqual(result.state, "SUCCEEDED")
        self.assertIsNone(result.reason)
        self.assertEqual(result.child_exit_code, 0)
        self.assertEqual(result.child_spawn_count, 1)
        self.assertTrue(result.success_marker_observed)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(result.raw_data_writes, 0)
        self.assertEqual(result.cash_spend_usd_cents, 0)
        lineage = result.to_receipt()["lineage"]
        self.assertEqual(lineage["parent_run_id"], result.run_id)
        self.assertTrue(str(lineage["child_run_id"]).startswith("t12-child-"))
        self.assertEqual(
            lineage["launcher_repository_path"],
            "scripts/run_task11_entity_input_probe.py",
        )
        self.assertEqual(lineage["child_plan_sha256"], self.spec.plan_sha256)
        self.assertEqual(
            lineage["sanitized_argv"],
            [
                "{python}",
                "-B",
                "scripts/run_task11_entity_input_probe.py",
            ],
        )
        self.assertIsNotNone(lineage["child_start_timestamp"])
        self.assertIsNotNone(lineage["child_observation_timestamp"])
        self.assertIsNotNone(lineage["child_availability_timestamp"])
        self.assertFalse(lineage["restart_backdates_availability"])

    def test_zero_exit_without_marker_fails_closed(self) -> None:
        result = self._run_synthetic("print('synthetic-complete')")
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(result.reason, "EXPECTED_MARKER_MISSING")
        self.assertEqual(result.child_exit_code, 0)
        self.assertFalse(result.success_marker_observed)

    def test_nonzero_exit_is_not_empty_or_success(self) -> None:
        result = self._run_synthetic(
            "import sys; print('typed-failure'); sys.exit(2)"
        )
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(result.reason, "CHILD_EXIT_NONZERO")
        self.assertEqual(result.child_exit_code, 2)
        self.assertFalse(result.success_marker_observed)

    def test_active_duplicate_blocks_without_spawning_child(self) -> None:
        identity = build_run_identity(
            self.spec,
            utc_window_start=WINDOW,
            attempt_sequence=1,
        )
        with tempfile.TemporaryDirectory() as directory:
            lock_root = Path(directory) / "locks"
            lock = AtomicDuplicateLock(
                lock_root,
                duplicate_key=identity.duplicate_key,
                run_id=identity.run_id,
                process_start_token="a" * 64,
            )
            self.assertTrue(lock.acquire())
            spawn_count = 0

            def must_not_spawn(
                _spec: ChildSpec,
                _root: Path,
                _environment: Mapping[str, str],
            ) -> subprocess.Popen[bytes]:
                nonlocal spawn_count
                spawn_count += 1
                raise AssertionError("duplicate_spawned_child")

            result = PilotSupervisor(
                repo_root=ROOT,
                lock_root=lock_root,
                limits=_limits(),
                disk_free_bytes=lambda _path: DISK_OK,
                process_factory=must_not_spawn,
            ).run(
                self.spec,
                utc_window_start=WINDOW,
                attempt_sequence=1,
            )
            self.assertEqual(result.state, "BLOCKED_DUPLICATE")
            self.assertEqual(result.reason, "ACTIVE_DUPLICATE")
            self.assertEqual(result.child_spawn_count, 0)
            self.assertEqual(spawn_count, 0)
            self.assertTrue(lock.release())

    def test_insufficient_disk_blocks_before_spawn(self) -> None:
        result = self._run_synthetic(
            "raise AssertionError('must-not-run')",
            disk_free=lambda _path: 100,
        )
        self.assertEqual(result.state, "BLOCKED_DISK")
        self.assertEqual(result.reason, "INSUFFICIENT_DISK_BEFORE_START")
        self.assertEqual(result.child_spawn_count, 0)

    def test_missing_disk_telemetry_fails_closed_before_spawn(self) -> None:
        def unavailable(_path: Path) -> int:
            raise OSError("synthetic-disk-unavailable")

        result = self._run_synthetic(
            "raise AssertionError('must-not-run')",
            disk_free=unavailable,
        )
        self.assertEqual(result.state, "BLOCKED_DISK")
        self.assertEqual(result.reason, "INSUFFICIENT_DISK_BEFORE_START")
        self.assertEqual(result.child_spawn_count, 0)

    def test_runtime_disk_breach_stops_child(self) -> None:
        readings = iter((DISK_OK, 0, 0))

        def disk_free(_path: Path) -> int:
            return next(readings, 0)

        result = self._run_synthetic(
            "import time; time.sleep(5)",
            disk_free=disk_free,
        )
        self.assertEqual(result.state, "BLOCKED_DISK")
        self.assertEqual(result.reason, "DISK_GUARD_BREACHED")
        self.assertEqual(result.child_spawn_count, 1)

    def test_wall_timeout_stops_child_without_retry(self) -> None:
        result = self._run_synthetic(
            "import time; time.sleep(5)",
            limits=_limits(
                silence_seconds_max=0.2,
                child_wall_seconds_max=0.4,
            ),
        )
        self.assertEqual(result.state, "TIMED_OUT")
        self.assertEqual(result.reason, "CHILD_WALL_TIMEOUT")
        receipt = result.to_receipt()
        self.assertEqual(receipt["retry_count"], 0)
        self.assertEqual(result.child_spawn_count, 1)

    def test_stop_request_uses_bounded_stop_state(self) -> None:
        calls = 0

        def stop_requested() -> bool:
            nonlocal calls
            calls += 1
            return calls >= 3

        result = self._run_synthetic(
            "import time; time.sleep(5)",
            stop_requested=stop_requested,
        )
        self.assertEqual(result.state, "STOPPED")
        self.assertEqual(result.reason, "STOP_REQUESTED")
        self.assertEqual(result.child_spawn_count, 1)

    def test_total_output_cap_terminates_noisy_child(self) -> None:
        result = self._run_synthetic(
            "print('x' * 4096)",
            limits=_limits(
                line_bytes_max=16_384,
                child_output_bytes_max=128,
            ),
        )
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(result.reason, "CHILD_OUTPUT_LIMIT_EXCEEDED")
        self.assertGreater(result.stdout_bytes, 128)
        self.assertEqual(result.stdout_sha256_scope, "RETAINED_PREFIX")

    def test_line_cap_is_distinct_from_total_output_cap(self) -> None:
        result = self._run_synthetic(
            "print('x' * 256)",
            limits=_limits(
                line_bytes_max=64,
                child_output_bytes_max=1024,
            ),
        )
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(result.reason, "CHILD_LINE_LIMIT_EXCEEDED")
        self.assertLess(result.stdout_bytes, 1024)
        self.assertEqual(result.stdout_sha256_scope, "FULL_BYTES")

    def test_invalid_utf8_is_typed_failure_and_body_is_not_in_receipt(
        self,
    ) -> None:
        result = self._run_synthetic(
            "import sys; sys.stdout.buffer.write(bytes([255, 254]))"
        )
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(result.reason, "INVALID_CHILD_OUTPUT")
        receipt_text = json.dumps(result.to_receipt(), sort_keys=True)
        self.assertNotIn("\\u00ff", receipt_text)
        self.assertNotIn("stdout_body", receipt_text)
        self.assertIn("stdout_sha256", receipt_text)

    def test_events_have_required_sanitized_fields(self) -> None:
        result = self._run_synthetic(
            "print('TASK11_ENTITY_PROBE_PREFLIGHT: PASS')"
        )
        required = {
            "schema_version",
            "event_type",
            "run_id",
            "consumer_asset_id",
            "attempt_sequence",
            "state",
            "observed_at",
            "monotonic_elapsed_ms",
            "reason",
            "child_exit_code",
            "stdout_bytes",
            "stderr_bytes",
            "disk_free_bytes",
            "provider_calls",
            "cash_spend_usd_cents",
        }
        event_types = set()
        for event in result.events:
            self.assertTrue(required.issubset(event))
            self.assertEqual(event["provider_calls"], 0)
            self.assertEqual(event["cash_spend_usd_cents"], 0)
            event_types.add(event["event_type"])
            encoded = canonical_json_bytes(event).decode("utf-8")
            self.assertNotIn(str(ROOT), encoded)
        self.assertTrue(
            {
                "SUPERVISOR_STARTED",
                "CHILD_STARTED",
                "CHILD_ACTIVITY",
                "HEALTH_CHANGED",
                "CHILD_EXITED",
                "SUPERVISOR_FINISHED",
            }.issubset(event_types)
        )

    def test_real_task11_consumer_runs_only_its_offline_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = PilotSupervisor(
                repo_root=ROOT,
                lock_root=Path(directory) / "locks",
                limits=_limits(child_wall_seconds_max=10.0),
                disk_free_bytes=lambda _path: DISK_OK,
            ).run(
                self.spec,
                utc_window_start=WINDOW,
                attempt_sequence=1,
            )
        self.assertEqual(result.state, "SUCCEEDED")
        self.assertTrue(result.success_marker_observed)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(result.raw_data_writes, 0)
        self.assertEqual(result.cash_spend_usd_cents, 0)

    def test_limits_cannot_weaken_frozen_caps(self) -> None:
        invalid = (
            SupervisorLimits(poll_interval_seconds=0.1),
            SupervisorLimits(child_wall_seconds_max=61),
            SupervisorLimits(silence_seconds_max=31),
            SupervisorLimits(graceful_stop_seconds=6),
            SupervisorLimits(line_bytes_max=16_385),
            SupervisorLimits(child_output_bytes_max=262_145),
            SupervisorLimits(start_reserve_fixed_bytes=536_870_911),
            SupervisorLimits(runtime_reserve_fixed_bytes=268_435_455),
        )
        for limits in invalid:
            with self.subTest(limits=limits):
                with self.assertRaises(PilotSupervisorError):
                    limits.validate()


if __name__ == "__main__":
    unittest.main()
