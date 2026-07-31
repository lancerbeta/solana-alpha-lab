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
from solana_alpha_lab.task21_multi_horizon_capture import (
    ATOM_ID,
    Task21H0ExecutionGate,
    Task21MultiHorizonAuthorityRequired,
    Task21MultiHorizonError,
    build_admissions,
    run_h0_capture,
    validate_config,
)


CONFIG_PATH = (
    ROOT / "configs/task21_bounded_admission_multi_horizon_capture_v1.yaml"
)
RECOVERY_PATH = (
    ROOT / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT
    / "docs/evidence/task21/"
    "bounded_admission_multi_horizon_capture_offline_acceptance_v1.json"
)
FIXED_NOW = datetime(2026, 7, 31, 7, 30, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeQuoteTransport:
    def __init__(self, *, base_time: datetime = FIXED_NOW) -> None:
        self._attempts = 0
        self._received_bytes = 0
        self._base_time = base_time

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def received_bytes(self) -> int:
        return self._received_bytes

    def execute(self, request) -> HttpCapture:
        self._attempts += 1
        sequence = self._attempts
        output_atomic = max(1, request.input_requested_atomic // 2 + sequence)
        requested_at = self._base_time + timedelta(milliseconds=sequence * 20)
        response_at = requested_at + timedelta(milliseconds=10)
        body = {
            "inputMint": request.input_mint,
            "inAmount": str(request.input_requested_atomic),
            "outputMint": request.output_mint,
            "outAmount": str(output_atomic),
            "otherAmountThreshold": str(max(0, output_atomic - 1)),
            "swapMode": "ExactIn",
            "slippageBps": request.slippage_bps,
            "platformFee": None,
            "priceImpactPct": "0.001",
            "routePlan": [
                {
                    "swapInfo": {
                        "ammKey": f"task21-h0-test-amm-{sequence:03d}",
                        "label": "TASK21_H0_TEST",
                        "inputMint": request.input_mint,
                        "outputMint": request.output_mint,
                        "inAmount": str(request.input_requested_atomic),
                        "outAmount": str(output_atomic),
                        "feeAmount": "0",
                        "feeMint": request.input_mint,
                    },
                    "percent": 100,
                    "bps": 10000,
                }
            ],
            "contextSlot": 400_000_000 + sequence,
            "timeTaken": 0.01,
        }
        payload = json.dumps(body, sort_keys=True).encode("utf-8")
        self._received_bytes += len(payload)
        return HttpCapture(
            observation=TransportObservation(
                requested_at=requested_at,
                response_at=response_at,
                first_reliable_available_at=response_at,
                available_to_strategy_at=response_at,
                ingested_at=response_at,
                http_status_code=200,
                response_body=body,
                timed_out=False,
                stale=False,
            ),
            received_bytes=len(payload),
            transport_stop_reason=None,
        )


class Task21MultiHorizonCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_config_and_protected_inputs_are_exact(self) -> None:
        validate_config(self.config, ROOT)
        for item in self.config["protected_inputs"]:
            path = ROOT / item["path"]
            self.assertEqual(_sha256(path), item["sha256"], item["path"])
            if "bytes" in item:
                self.assertEqual(path.stat().st_size, item["bytes"])

    def test_exact_frozen_t1_set_admits_three_before_outcomes(self) -> None:
        members, receipt = build_admissions(
            repo_root=ROOT,
            config=self.config,
            admitted_at=FIXED_NOW,
        )
        self.assertEqual(len(members), 3)
        self.assertEqual(receipt["real_candidate_admissions"], 3)
        self.assertFalse(receipt["outcome_or_route_input_used"])
        self.assertFalse(receipt["original_future_close_used_as_entered_at"])
        self.assertTrue(
            all(member["entered_at"] == "2026-07-31T07:30:00.000000Z" for member in members)
        )
        self.assertTrue(
            all(
                member["first_reliable_available_at"]
                == "2026-07-30T16:28:59.084Z"
                for member in members
            )
        )

    def test_full_h0_run_is_three_panels_twenty_four_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            factory_calls = 0

            def factory(_member):
                nonlocal factory_calls
                factory_calls += 1
                self.assertTrue(list(output_root.rglob("admission_events.jsonl")))
                return FakeQuoteTransport()

            receipt = run_h0_capture(
                gate=Task21H0ExecutionGate(ATOM_ID),
                repo_root=ROOT,
                config_path=CONFIG_PATH,
                recovery_receipt_path=RECOVERY_PATH,
                transport_factory=factory,
                now=lambda: FIXED_NOW,
                sleeper=lambda _seconds: None,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=output_root,
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(factory_calls, 3)
            self.assertEqual(
                receipt["actual_actions"]["provider_api_rpc_wss_calls"], 24
            )
            self.assertEqual(
                receipt["actual_actions"]["real_candidate_admissions"], 3
            )
            self.assertEqual(receipt["h0"]["panels_complete"], 3)
            self.assertEqual(
                receipt["next_boundary"]["atom_id"],
                "T21-A6S_H1_FOREGROUND_CAPTURE_V1",
            )
            self.assertEqual(
                receipt["next_boundary"]["earliest_at"],
                "2026-07-31T08:30:00.000000Z",
            )
            self.assertEqual(
                receipt["next_boundary"]["latest_at"],
                "2026-07-31T08:40:00.000000Z",
            )
            self.assertFalse(
                receipt["next_boundary"][
                    "provider_api_rpc_wss_calls_authorized"
                ]
            )
            self.assertEqual(receipt["actual_actions"]["drive_writes"], 0)
            self.assertLessEqual(
                receipt["local_evidence"]["stored_bytes"], 16_777_216
            )
            self.assertEqual(
                len(list(output_root.rglob("raw_events.jsonl"))), 3
            )

    def test_wrong_or_missing_exact_authority_fails_before_output(self) -> None:
        with self.assertRaises(Task21MultiHorizonAuthorityRequired):
            Task21H0ExecutionGate("WRONG")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(Task21MultiHorizonAuthorityRequired):
                run_h0_capture(
                    gate=object(),  # type: ignore[arg-type]
                    repo_root=ROOT,
                    config_path=CONFIG_PATH,
                    recovery_receipt_path=RECOVERY_PATH,
                    transport_factory=lambda _member: FakeQuoteTransport(),
                    now=lambda: FIXED_NOW,
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=Path(directory),
                )
            self.assertEqual(list(Path(directory).rglob("*")), [])

    def test_stale_recovery_blocks_before_transport_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            called = False

            def factory(_member):
                nonlocal called
                called = True
                return FakeQuoteTransport()

            with self.assertRaisesRegex(
                Task21MultiHorizonError,
                "recovery_backup_stale",
            ):
                run_h0_capture(
                    gate=Task21H0ExecutionGate(ATOM_ID),
                    repo_root=ROOT,
                    config_path=CONFIG_PATH,
                    recovery_receipt_path=RECOVERY_PATH,
                    transport_factory=factory,
                    now=lambda: datetime(2026, 7, 31, 10, 0, tzinfo=UTC),
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=Path(directory),
                )
            self.assertFalse(called)
            self.assertEqual(list(Path(directory).rglob("*")), [])

    def test_outcome_exposed_nomination_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            replay = json.loads(
                (
                    ROOT
                    / self.config["protected_inputs"][3]["path"]
                ).read_text(encoding="utf-8")
            )
            replay["nomination_events"][0]["exact_rule_input_values"][
                "uses_task21_quote_route_or_price_outcome"
            ] = True
            path = Path(directory) / "replay.json"
            path.write_text(json.dumps(replay), encoding="utf-8")
            changed = copy.deepcopy(self.config)
            for item in changed["protected_inputs"]:
                if item["role"] == "FROZEN_T1_REPLAY":
                    item["path"] = str(path)
                    item["sha256"] = _sha256(path)
                    item["bytes"] = path.stat().st_size
            with self.assertRaisesRegex(
                Task21MultiHorizonError,
                "frozen_nomination_scope_drift",
            ):
                build_admissions(
                    repo_root=ROOT,
                    config=changed,
                    admitted_at=FIXED_NOW,
                )

    def test_adversarial_cap_or_drive_authority_drift_fails(self) -> None:
        changed = copy.deepcopy(self.config)
        changed["h0"]["provider_calls_total_max"] = 25
        with self.assertRaisesRegex(Task21MultiHorizonError, "h0_cap_drift"):
            validate_config(changed, ROOT)
        changed = copy.deepcopy(self.config)
        changed["authority"]["drive_writes"] = 1
        with self.assertRaisesRegex(
            Task21MultiHorizonError, "authority_boundary_drift"
        ):
            validate_config(changed, ROOT)

    def test_output_override_cannot_use_real_transport(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                Task21MultiHorizonError,
                "output_override_requires_injected_transport",
            ):
                run_h0_capture(
                    gate=Task21H0ExecutionGate(ATOM_ID),
                    repo_root=ROOT,
                    config_path=CONFIG_PATH,
                    recovery_receipt_path=RECOVERY_PATH,
                    now=lambda: FIXED_NOW,
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=Path(directory),
                )

    def test_offline_acceptance_binds_exact_artifacts(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            _sha256(ACCEPTANCE_PATH),
            "aab546d1d5924ad30297036fc7a039a0daa9832538d63721597409fa7cfda1bb",
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "H0_ADMISSION_AND_CAPTURE_CONTRACT_READY_FOR_EXACT_EXECUTION",
        )
        forward_evolved = {
            "docs/contracts/task21_bounded_admission_multi_horizon_capture_contract_v1.md",
            "configs/task21_bounded_admission_multi_horizon_capture_v1.yaml",
            "scripts/run_task21_h0_capture.py",
            "tests/test_task21_multi_horizon_capture.py",
        }
        for artifact in receipt["artifacts"]:
            if artifact["path"] in forward_evolved:
                continue
            self.assertEqual(
                _sha256(ROOT / artifact["path"]),
                artifact["sha256"],
                artifact["path"],
            )
        self.assertEqual(
            receipt["actual_actions"]["provider_api_rpc_wss_calls"], 0
        )
        self.assertEqual(receipt["actual_actions"]["real_candidate_admissions"], 0)
        self.assertEqual(receipt["actual_actions"]["drive_writes"], 0)


if __name__ == "__main__":
    unittest.main()
