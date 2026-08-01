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
from solana_alpha_lab.task21_r2_event_triggered_capture import SourceHttpCapture
from solana_alpha_lab.task21_r3_event_triggered_capture import (
    ATOM_ID,
    Task21R3AuthorityRequired,
    Task21R3Error,
    Task21R3ExecutionGate,
    _replay_r2_state,
    run_r3_source_p0_capture,
    validate_config,
)
from solana_alpha_lab.task21_r2_event_triggered_capture import _load_yaml


CONFIG = ROOT / "configs/task21_r3_event_triggered_source_p0_v1.yaml"
FIXTURE = ROOT / "tests/fixtures/task21/geckoterminal_new_pools_offline_v1.json"
ACCEPTANCE = ROOT / "docs/evidence/task21/r3_event_triggered_source_p0_offline_acceptance_v1.json"
FIXED_NOW = datetime(2026, 8, 1, 13, 30, tzinfo=UTC)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeSourceTransport:
    def __init__(self, *, fail_first: bool = False) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self._responses = [
            json.dumps(fixture["dexscreener_response"], sort_keys=True).encode(),
            json.dumps(fixture["solana_rpc_response"], sort_keys=True).encode(),
        ]
        self._attempts = 0
        self._received_bytes = 0
        self._fail_first = fail_first

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def received_bytes(self) -> int:
        return self._received_bytes

    def execute(
        self, *, request_kind, method, url, request_body, response_bytes_max
    ):
        index = self._attempts
        self._attempts += 1
        moment = FIXED_NOW + timedelta(milliseconds=self._attempts * 10)
        if self._fail_first and index == 0:
            body = b""
            status = None
            error = "DNS_TLS_OR_TRANSPORT_FAILURE"
            stop = "SOURCE_TRANSPORT_FAILURE"
        else:
            body = self._responses[index]
            status = 200
            error = None
            stop = None
        self._received_bytes += len(body)
        return SourceHttpCapture(
            request_kind=request_kind,
            method=method,
            url=url,
            request_body=request_body,
            status=status,
            response_body=body,
            requested_at=moment,
            response_at=moment + timedelta(milliseconds=1),
            error_class=error,
            stop_reason=stop,
        )


class FakeQuoteTransport:
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
        output_atomic = max(1, request.input_requested_atomic // 2 + sequence)
        requested_at = FIXED_NOW + timedelta(milliseconds=sequence * 20)
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
                        "ammKey": f"task21-r3-test-amm-{sequence:03d}",
                        "label": "TASK21_R3_TEST",
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
            "contextSlot": 420_000_000 + sequence,
            "timeTaken": 0.01,
        }
        payload = json.dumps(body, sort_keys=True).encode()
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


class Task21R3EventTriggeredCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        cls.event_config = _load_yaml(
            ROOT / "configs/task21_event_triggered_final_cohort_runtime_v1.yaml"
        )

    def test_config_replay_seed_and_authority_are_exact(self) -> None:
        validate_config(self.config, ROOT)
        state = _replay_r2_state(
            config=self.config,
            event_config=self.event_config,
            repo_root=ROOT,
        )
        self.assertEqual(len(state["admitted_members"]), 3)
        self.assertEqual(len(state["seen_mints"]), 6)
        self.assertEqual(Task21R3ExecutionGate(ATOM_ID).authority_phrase, ATOM_ID)
        with self.assertRaises(Task21R3AuthorityRequired):
            Task21R3ExecutionGate("WRONG")

    def test_happy_path_persists_two_admissions_before_sixteen_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            factory_calls = 0

            def factory(_member):
                nonlocal factory_calls
                factory_calls += 1
                self.assertTrue(list(output.rglob("admission_events.jsonl")))
                return FakeQuoteTransport()

            receipt = run_r3_source_p0_capture(
                gate=Task21R3ExecutionGate(ATOM_ID),
                repo_root=ROOT,
                config_path=CONFIG,
                source_transport=FakeSourceTransport(),
                quote_transport_factory=factory,
                now=lambda: FIXED_NOW,
                sleeper=lambda _seconds: None,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=output,
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(factory_calls, 2)
            self.assertEqual(receipt["actual_actions"]["provider_api_rpc_wss_calls"], 18)
            self.assertEqual(receipt["actual_actions"]["jupiter_calls"], 16)
            self.assertEqual(receipt["actual_actions"]["nominations"], 2)
            self.assertEqual(receipt["actual_actions"]["admissions"], 2)
            self.assertEqual(receipt["p0"]["panels_complete"], 2)
            self.assertTrue(receipt["admission"]["persisted_before_first_jupiter_call"])
            self.assertFalse(receipt["admission"]["outcome_or_route_input_used"])
            self.assertEqual(
                receipt["next_boundary"]["atom_id"],
                "T21-A6S_R3_P1_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1",
            )

    def test_source_failure_retains_evidence_without_quote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            quote_called = False

            def factory(_member):
                nonlocal quote_called
                quote_called = True
                return FakeQuoteTransport()

            receipt = run_r3_source_p0_capture(
                gate=Task21R3ExecutionGate(ATOM_ID),
                repo_root=ROOT,
                config_path=CONFIG,
                source_transport=FakeSourceTransport(fail_first=True),
                quote_transport_factory=factory,
                now=lambda: FIXED_NOW,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=Path(directory),
            )
            self.assertEqual(receipt["status"], "STOPPED_NO_ADMISSION")
            self.assertEqual(receipt["stop_reason"], "SOURCE_TRANSPORT_FAILURE")
            self.assertEqual(receipt["actual_actions"]["provider_api_rpc_wss_calls"], 1)
            self.assertFalse(quote_called)
            self.assertTrue(list(Path(directory).rglob("source_partition.json")))

    def test_stale_recovery_blocks_before_source_or_output(self) -> None:
        source = FakeSourceTransport()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(Task21R3Error, "recovery_backup_stale"):
                run_r3_source_p0_capture(
                    gate=Task21R3ExecutionGate(ATOM_ID),
                    repo_root=ROOT,
                    config_path=CONFIG,
                    source_transport=source,
                    quote_transport_factory=lambda _member: FakeQuoteTransport(),
                    now=lambda: datetime(2026, 8, 2, 15, 0, tzinfo=UTC),
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=Path(directory),
                )
            self.assertEqual(source.attempts, 0)
            self.assertEqual(list(Path(directory).rglob("*")), [])

    def test_authority_budget_or_prior_population_drift_fails_closed(self) -> None:
        changed = copy.deepcopy(self.config)
        changed["authority"]["jupiter_calls_max"] = 17
        with self.assertRaisesRegex(Task21R3Error, "authority_boundary_drift"):
            validate_config(changed, ROOT)
        changed = copy.deepcopy(self.config)
        changed["budget"]["used_before_r3"]["quote_requests"] = 129
        with self.assertRaisesRegex(Task21R3Error, "budget_contract_drift"):
            validate_config(changed, ROOT)
        changed = copy.deepcopy(self.config)
        changed["cohort"]["prior_seen_mints"][0] = "WRONG"
        with self.assertRaisesRegex(Task21R3Error, "cohort_contract_drift"):
            validate_config(changed, ROOT)

    def test_missing_authority_blocks_before_execution(self) -> None:
        with self.assertRaises(Task21R3AuthorityRequired):
            run_r3_source_p0_capture(
                gate=None,
                repo_root=ROOT,
                config_path=CONFIG,
            )

    def test_offline_acceptance_binds_exact_non_runtime_artifacts(self) -> None:
        if not ACCEPTANCE.is_file():
            self.skipTest("offline acceptance is generated after implementation")
        receipt = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["actual_actions"]["provider_api_rpc_wss_calls"], 0)
        for item in receipt["artifacts"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])


if __name__ == "__main__":
    unittest.main()
