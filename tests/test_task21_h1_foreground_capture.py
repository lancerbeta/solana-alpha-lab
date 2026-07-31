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
from solana_alpha_lab.task21_h1_foreground_capture import (
    ATOM_ID,
    Task21H1AuthorityRequired,
    Task21H1Error,
    Task21H1ExecutionGate,
    run_h1_foreground_capture,
    validate_config,
)


CONFIG_PATH = ROOT / "configs/task21_h1_foreground_capture_v1.yaml"
RECOVERY_PATH = ROOT / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
ACCEPTANCE_PATH = (
    ROOT
    / "docs/evidence/task21/h1_foreground_capture_offline_acceptance_v1.json"
)
WITHIN_WINDOW = datetime(2026, 7, 31, 8, 55, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
                        "ammKey": f"h1-test-{sequence}",
                        "label": "TASK21_H1_TEST",
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
            "contextSlot": 410_000_000 + sequence,
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


class Task21H1ForegroundCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    def _effective_config(self):
        changed = copy.deepcopy(self.config)
        marker = next(
            item
            for item in changed["protected_inputs"]
            if item["role"] == "ACTIVE_TIME_GATES"
        )
        marker["sha256"] = _sha256(ROOT / marker["path"])
        return changed

    def _write_effective_config(self, directory: str) -> Path:
        path = Path(directory) / "effective_h1_config.yaml"
        path.write_text(
            yaml.safe_dump(self._effective_config(), sort_keys=False),
            encoding="utf-8",
        )
        return path

    def test_config_and_all_frozen_inputs_are_exact(self) -> None:
        validate_config(self._effective_config(), ROOT)
        for item in self.config["protected_inputs"]:
            if item["role"] == "ACTIVE_TIME_GATES":
                marker = json.loads(
                    (ROOT / item["path"]).read_text(encoding="utf-8")
                )
                h1_gate = marker["gates"][1]
                self.assertEqual(h1_gate["status"], "RESOLVED_WITH_EVIDENCE")
                self.assertEqual(
                    h1_gate["resolution"]["result_receipt"]["path"],
                    "docs/evidence/task21/"
                    "h1_foreground_capture_runtime_acceptance_v1.json",
                )
            else:
                self.assertEqual(_sha256(ROOT / item["path"]), item["sha256"])

    def test_before_window_fails_before_transport_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            called = False
            output_root = Path(directory) / "output"
            config_path = self._write_effective_config(directory)

            def factory(_member):
                nonlocal called
                called = True
                return FakeTransport()

            with self.assertRaisesRegex(Task21H1Error, "h1_window_not_open"):
                run_h1_foreground_capture(
                    gate=Task21H1ExecutionGate(ATOM_ID),
                    repo_root=ROOT,
                    config_path=config_path,
                    recovery_receipt_path=RECOVERY_PATH,
                    transport_factory=factory,
                    now=lambda: datetime(2026, 7, 31, 8, 49, tzinfo=UTC),
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=output_root,
                )
            self.assertFalse(called)
            self.assertFalse(output_root.exists())

    def test_full_h1_is_three_panels_and_twenty_four_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = self._write_effective_config(directory)
            receipt = run_h1_foreground_capture(
                gate=Task21H1ExecutionGate(ATOM_ID),
                repo_root=ROOT,
                config_path=config_path,
                recovery_receipt_path=RECOVERY_PATH,
                transport_factory=lambda _member: FakeTransport(),
                now=lambda: WITHIN_WINDOW,
                sleeper=lambda _seconds: None,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=Path(directory) / "output",
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["h1"]["panels_complete"], 3)
            self.assertEqual(
                receipt["actual_actions"]["provider_api_rpc_wss_calls"], 24
            )
            self.assertFalse(receipt["population"]["changed"])
            self.assertEqual(
                receipt["next_boundary"]["atom_id"],
                "T21-A6S_H6_FOREGROUND_CAPTURE_V1",
            )
            self.assertEqual(
                receipt["next_boundary"]["earliest_at"],
                "2026-07-31T13:50:34.414367Z",
            )
            self.assertEqual(len(list(Path(directory).rglob("raw_events.jsonl"))), 3)

    def test_after_window_writes_explicit_gap_with_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            called = False
            config_path = self._write_effective_config(directory)

            def factory(_member):
                nonlocal called
                called = True
                return FakeTransport()

            receipt = run_h1_foreground_capture(
                gate=Task21H1ExecutionGate(ATOM_ID),
                repo_root=ROOT,
                config_path=config_path,
                recovery_receipt_path=RECOVERY_PATH,
                transport_factory=factory,
                now=lambda: datetime(2026, 7, 31, 9, 1, tzinfo=UTC),
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=Path(directory) / "output",
            )
            self.assertEqual(receipt["status"], "GAP")
            self.assertFalse(called)
            self.assertEqual(
                receipt["actual_actions"]["provider_api_rpc_wss_calls"], 0
            )
            self.assertFalse(receipt["backfill"])
            self.assertFalse(receipt["rescheduled"])

    def test_wrong_or_missing_authority_fails_closed(self) -> None:
        with self.assertRaises(Task21H1AuthorityRequired):
            Task21H1ExecutionGate("WRONG")
        with tempfile.TemporaryDirectory() as directory:
            config_path = self._write_effective_config(directory)
            output_root = Path(directory) / "output"
            with self.assertRaises(Task21H1AuthorityRequired):
                run_h1_foreground_capture(
                    gate=object(),  # type: ignore[arg-type]
                    repo_root=ROOT,
                    config_path=config_path,
                    recovery_receipt_path=RECOVERY_PATH,
                    transport_factory=lambda _member: FakeTransport(),
                    now=lambda: WITHIN_WINDOW,
                    output_root_override=output_root,
                )
            self.assertFalse(output_root.exists())

    def test_stale_recovery_blocks_before_transport(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            called = False
            config_path = self._write_effective_config(directory)
            stale_recovery = json.loads(
                RECOVERY_PATH.read_text(encoding="utf-8")
            )
            stale_recovery["health"]["last_successful_backup_at"] = (
                "2026-07-29T08:00:00.000Z"
            )
            stale_path = Path(directory) / "stale_recovery.json"
            stale_path.write_text(
                json.dumps(stale_recovery),
                encoding="utf-8",
            )

            def factory(_member):
                nonlocal called
                called = True
                return FakeTransport()

            with self.assertRaisesRegex(Task21H1Error, "recovery_backup_stale"):
                run_h1_foreground_capture(
                    gate=Task21H1ExecutionGate(ATOM_ID),
                    repo_root=ROOT,
                    config_path=config_path,
                    recovery_receipt_path=stale_path,
                    transport_factory=factory,
                    now=lambda: datetime(2026, 7, 31, 8, 59, tzinfo=UTC),
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=Path(directory) / "output",
                )
            self.assertFalse(called)

    def test_cap_and_external_boundary_drift_fail(self) -> None:
        changed = self._effective_config()
        changed["h1"]["provider_calls_total_max"] = 25
        with self.assertRaisesRegex(Task21H1Error, "h1_cap_drift"):
            validate_config(changed, ROOT)
        changed = self._effective_config()
        changed["authority"]["drive_writes"] = 1
        with self.assertRaisesRegex(
            Task21H1Error, "h1_authority_boundary_drift"
        ):
            validate_config(changed, ROOT)

    def test_offline_acceptance_binds_exact_candidate(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["targeted_validation"], "8_OF_8_PASS")
        for artifact in receipt["artifacts"]:
            self.assertEqual(
                _sha256(ROOT / artifact["path"]),
                artifact["sha256"],
                artifact["path"],
            )
        self.assertEqual(
            receipt["actual_actions"]["provider_api_rpc_wss_calls"], 0
        )


if __name__ == "__main__":
    unittest.main()
