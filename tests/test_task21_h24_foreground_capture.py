from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.jupiter_quote_logger import TransportObservation
from solana_alpha_lab.jupiter_quote_transport import HttpCapture
from solana_alpha_lab.task21_h24_foreground_capture import (
    ATOM_ID,
    Task21H24AuthorityRequired,
    Task21H24Error,
    Task21H24ExecutionGate,
    run_h24_foreground_capture,
    validate_config,
)


WITHIN_WINDOW = datetime(2026, 8, 1, 7, 55, tzinfo=UTC)
CONFIG_PATH = ROOT / "configs/task21_h24_foreground_capture_v1.yaml"
ACCEPTANCE_PATH = (
    ROOT
    / "docs/evidence/task21/h24_minimum_age_sentinel_offline_acceptance_v2.json"
)
H0_ACCEPTANCE = "docs/evidence/task21/h0_admission_capture_runtime_acceptance_v1.json"
H0_EVENTS = (
    "local/task21_forward/h0_capture/"
    "run=h0-20260731T074954402486Z-78d2d1b62d99/admission_events.jsonl"
)
H6_ACCEPTANCE = "docs/evidence/task21/h6_foreground_capture_runtime_acceptance_v1.json"
H6_GAP = (
    "local/task21_forward/h6_capture/"
    "run=h6-gap-44fc071623e5ed6c/gap_receipt.json"
)

LOCAL_PROTECTED_INPUT_TESTS = {
    "test_config_and_frozen_h6_gap_are_exact",
    "test_before_window_fails_without_output_or_transport",
    "test_h24_is_one_outcome_blind_sentinel_and_eight_calls",
    "test_late_capture_remains_eligible_and_records_actual_elapsed",
    "test_wrong_authority_and_stale_recovery_fail_closed",
    "test_authority_boundary_drift_fails",
}


def _sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _local_protected_inputs_exact(config: dict) -> bool:
    for item in config["protected_inputs"]:
        if not item["path"].startswith("local/"):
            continue
        path = ROOT / item["path"]
        if not path.is_file() or _sha(item["path"]) != item["sha256"]:
            return False
    return True


def _config() -> dict:
    value = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("h24_test_config_invalid")
    return value


def _recovery(backup_at: str = "2026-08-01T07:40:00.000Z") -> dict:
    return {
        "task_id": "TASK-21",
        "verdict": "PASS",
        "provider_api_rpc_wss_calls": 0,
        "health": {
            "health_state": "HEALTHY",
            "last_successful_backup_at": backup_at,
            "last_successful_restore_at": "2026-08-01T07:41:00.000Z",
        },
    }


class FakeTransport:
    def __init__(self) -> None:
        self._attempts = 0
        self._received_bytes = 0

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def received_bytes(self) -> int:
        return self._received_bytes

    def execute(self, request) -> HttpCapture:
        self._attempts += 1
        sequence = self._attempts
        output = max(1, request.input_requested_atomic // 2 + sequence)
        requested = WITHIN_WINDOW + timedelta(milliseconds=sequence * 20)
        response = requested + timedelta(milliseconds=10)
        body = {
            "inputMint": request.input_mint,
            "inAmount": str(request.input_requested_atomic),
            "outputMint": request.output_mint,
            "outAmount": str(output),
            "otherAmountThreshold": str(max(0, output - 1)),
            "swapMode": "ExactIn",
            "slippageBps": request.slippage_bps,
            "platformFee": None,
            "priceImpactPct": "0.001",
            "routePlan": [
                {
                    "swapInfo": {
                        "ammKey": f"h24-test-{sequence}",
                        "label": "TASK21_H24_TEST",
                        "inputMint": request.input_mint,
                        "outputMint": request.output_mint,
                        "inAmount": str(request.input_requested_atomic),
                        "outAmount": str(output),
                        "feeAmount": "0",
                        "feeMint": request.input_mint,
                    },
                    "percent": 100,
                    "bps": 10000,
                }
            ],
            "contextSlot": 420_000_000 + sequence,
            "timeTaken": 0.01,
        }
        payload = json.dumps(body, sort_keys=True).encode("utf-8")
        self._received_bytes += len(payload)
        return HttpCapture(
            observation=TransportObservation(
                requested_at=requested,
                response_at=response,
                first_reliable_available_at=response,
                available_to_strategy_at=response,
                ingested_at=response,
                http_status_code=200,
                response_body=body,
                timed_out=False,
                stale=False,
            ),
            received_bytes=len(payload),
            transport_stop_reason=None,
        )


class Task21H24ForegroundCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        if (
            self._testMethodName in LOCAL_PROTECTED_INPUT_TESTS
            and not _local_protected_inputs_exact(_config())
        ):
            self.skipTest("requires excluded exact local TASK-21 evidence")

    def _files(self, directory: str, recovery: dict | None = None) -> tuple[Path, Path]:
        root = Path(directory)
        config_path = root / "h24.yaml"
        config_path.write_text(
            yaml.safe_dump(_config(), sort_keys=False), encoding="utf-8"
        )
        recovery_path = root / "recovery.json"
        recovery_path.write_text(
            json.dumps(_recovery() if recovery is None else recovery),
            encoding="utf-8",
        )
        return config_path, recovery_path

    def test_config_and_frozen_h6_gap_are_exact(self) -> None:
        config = _config()
        validate_config(config, ROOT)
        self.assertEqual(_sha(H6_GAP), "c3b8ecef288cbce2f7bdf26e937ea1907087d8ac05c64102c6600ae94f1e2fbb")

    def test_before_window_fails_without_output_or_transport(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path, recovery_path = self._files(directory)
            called = False

            def factory(_member):
                nonlocal called
                called = True
                return FakeTransport()

            output = Path(directory) / "output"
            with self.assertRaisesRegex(
                Task21H24Error, "h24_minimum_age_not_reached"
            ):
                run_h24_foreground_capture(
                    gate=None,
                    repo_root=ROOT,
                    config_path=config_path,
                    recovery_receipt_path=recovery_path,
                    transport_factory=factory,
                    now=lambda: datetime(2026, 8, 1, 7, 49, tzinfo=UTC),
                    output_root_override=output,
                )
            self.assertFalse(called)
            self.assertFalse(output.exists())

    def test_h24_is_one_outcome_blind_sentinel_and_eight_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path, recovery_path = self._files(directory)
            receipt = run_h24_foreground_capture(
                gate=Task21H24ExecutionGate(ATOM_ID),
                repo_root=ROOT,
                config_path=config_path,
                recovery_receipt_path=recovery_path,
                transport_factory=lambda _member: FakeTransport(),
                now=lambda: WITHIN_WINDOW,
                sleeper=lambda _seconds: None,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=Path(directory) / "output",
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["h24"]["panels_complete"], 1)
            self.assertEqual(
                receipt["actual_actions"]["provider_api_rpc_wss_calls"], 8
            )
            self.assertEqual(receipt["population"]["source_population_count"], 3)
            self.assertEqual(len(receipt["population"]["member_ids"]), 1)
            self.assertEqual(
                receipt["timing"]["semantics"], "MINIMUM_AGE_24H_PLUS"
            )
            self.assertEqual(
                receipt["next_boundary"]["status"], "DEFERRED_TRIGGER_ONLY"
            )
            self.assertEqual(len(list(Path(directory).rglob("raw_events.jsonl"))), 1)

    def test_late_capture_remains_eligible_and_records_actual_elapsed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path, recovery_path = self._files(directory)
            late = datetime(2026, 8, 2, 8, 1, tzinfo=UTC)
            recovery_path.write_text(
                json.dumps(_recovery("2026-08-02T07:40:00.000Z")),
                encoding="utf-8",
            )
            receipt = run_h24_foreground_capture(
                gate=Task21H24ExecutionGate(ATOM_ID),
                repo_root=ROOT,
                config_path=config_path,
                recovery_receipt_path=recovery_path,
                transport_factory=lambda _member: FakeTransport(),
                now=lambda: late,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=Path(directory) / "output",
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertGreater(receipt["timing"]["actual_elapsed_seconds"], 86_400)
            self.assertTrue(receipt["timing"]["late_capture_allowed"])
            self.assertFalse(receipt["timing"]["narrow_expiry_window_used"])

    def test_wrong_authority_and_stale_recovery_fail_closed(self) -> None:
        with self.assertRaises(Task21H24AuthorityRequired):
            Task21H24ExecutionGate("WRONG")
        with tempfile.TemporaryDirectory() as directory:
            stale = _recovery("2026-07-30T07:00:00.000Z")
            config_path, recovery_path = self._files(directory, stale)
            called = False

            def factory(_member):
                nonlocal called
                called = True
                return FakeTransport()

            with self.assertRaisesRegex(Task21H24Error, "recovery_backup_stale"):
                run_h24_foreground_capture(
                    gate=Task21H24ExecutionGate(ATOM_ID),
                    repo_root=ROOT,
                    config_path=config_path,
                    recovery_receipt_path=recovery_path,
                    transport_factory=factory,
                    now=lambda: WITHIN_WINDOW,
                    output_root_override=Path(directory) / "output",
                )
            self.assertFalse(called)

    def test_authority_boundary_drift_fails(self) -> None:
        changed = copy.deepcopy(_config())
        changed["authority"]["drive_writes"] = 1
        with self.assertRaisesRegex(Task21H24Error, "h24_authority_boundary_drift"):
            validate_config(changed, ROOT)

    def test_offline_acceptance_binds_exact_candidate(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["targeted_validation"], "7_OF_7_PASS")
        for artifact in receipt["artifacts"]:
            if artifact["path"] == "tests/test_task21_h24_foreground_capture.py":
                continue
            self.assertEqual(_sha(artifact["path"]), artifact["sha256"])
        for artifact in receipt["protected_inputs"]:
            self.assertEqual(_sha(artifact["path"]), artifact["sha256"])
        marker = json.loads(
            (ROOT / receipt["dynamic_control"]["path"]).read_text(
                encoding="utf-8"
            )
        )
        gate = next(
            item
            for item in marker["gates"]
            if item["gate_id"] == receipt["dynamic_control"]["gate_id"]
        )
        self.assertEqual(gate["status"], "ACTIVE_WAITING")
        self.assertIsNone(gate["latest_at"])
        self.assertEqual(
            gate["capture_prep"]["acceptance"]["sha256"],
            _sha(ACCEPTANCE_PATH.relative_to(ROOT).as_posix()),
        )
        self.assertEqual(
            gate["capture_prep"]["config"]["sha256"],
            _sha("configs/task21_h24_foreground_capture_v1.yaml"),
        )
        self.assertFalse(receipt["accepted_behavior"]["h24_executed"])
        self.assertEqual(
            receipt["actual_actions"]["provider_api_rpc_wss_calls"], 0
        )


if __name__ == "__main__":
    unittest.main()
