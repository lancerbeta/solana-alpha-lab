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
from solana_alpha_lab.task21_event_triggered_followup_capture import (
    ATOM_ID,
    Task21FollowupAuthorityRequired,
    Task21FollowupError,
    Task21FollowupExecutionGate,
    run_event_triggered_followup_capture,
    validate_followup_config,
)


CONFIG = ROOT / "configs/task21_r2_p1_event_triggered_capture_v1.yaml"
ACCEPTANCE = (
    ROOT
    / "docs/evidence/task21/r2_p1_event_triggered_capture_offline_acceptance_v1.json"
)
FIXED_NOW = datetime(2026, 8, 1, 12, 20, tzinfo=UTC)
MEMBERS = [
    {
        "batch_id": "T21-R2",
        "entered_at": "2026-08-01T11:46:58.126216Z",
        "hypothesis_version_id": "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1",
        "member_id": "T21-WATCH-29e2b75994975253bd74",
        "mint": "2Ezm4w3gFdymRAyhx9KEsbJV9NA79Y7UoiNWeXNFpump",
        "mint_decimals": 6,
        "nomination_event_id": "T21-R2-NOM-26050ca18b538565aa6d",
    },
    {
        "batch_id": "T21-R2",
        "entered_at": "2026-08-01T11:46:58.126216Z",
        "hypothesis_version_id": "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1",
        "member_id": "T21-WATCH-6f21dec76d05f5831216",
        "mint": "2HU2VftbJ7Fp9P5pEbneNsRhax8boHhTVS1KLnYrpump",
        "mint_decimals": 6,
        "nomination_event_id": "T21-R2-NOM-8cec7d1e03ba1dadf98b",
    },
    {
        "batch_id": "T21-R2",
        "entered_at": "2026-08-01T11:46:58.126216Z",
        "hypothesis_version_id": "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1",
        "member_id": "T21-WATCH-61ce24fc3fa04e3eaba7",
        "mint": "2JdM5MHiXjsQz5QgnSQfbidZDTVXCLki74jMYgJapump",
        "mint_decimals": 6,
        "nomination_event_id": "T21-R2-NOM-bb5769dfb751cb4cfb37",
    },
]
P0_COMPLETED = [
    "2026-08-01T11:47:14.336241Z",
    "2026-08-01T11:47:32.739825Z",
    "2026-08-01T11:47:51.205696Z",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


class TickingNow:
    def __init__(self, start: datetime) -> None:
        self.start = start
        self.calls = 0

    def __call__(self) -> datetime:
        value = self.start + timedelta(seconds=self.calls)
        self.calls += 1
        return value


class FakeQuoteTransport:
    def __init__(self, *, stop_first: bool = False) -> None:
        self._attempts = 0
        self._received_bytes = 0
        self.stop_first = stop_first

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
                        "ammKey": f"task21-followup-test-amm-{sequence:03d}",
                        "label": "TASK21_FOLLOWUP_TEST",
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
            transport_stop_reason=(
                "INJECTED_TRANSPORT_STOP"
                if self.stop_first and sequence == 1
                else None
            ),
        )


class SyntheticRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config = copy.deepcopy(
            yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        )
        self.config_path = root / "configs/followup.yaml"
        self.output = root / "test-output"
        self._build()

    def _bind(self, role: str, relative: str, payload: bytes) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        item = next(
            value
            for value in self.config["protected_inputs"]
            if value["role"] == role
        )
        item["path"] = relative
        item["sha256"] = digest(path)
        return path

    def _build(self) -> None:
        event_path = ROOT / "configs/task21_event_triggered_final_cohort_runtime_v1.yaml"
        self._bind(
            "EVENT_TRIGGERED_RUNTIME_PLAN",
            "inputs/event_runtime.yaml",
            event_path.read_bytes(),
        )
        acceptance = {
            "status": "PASS",
            "admission": {
                "members": [
                    {"member_id": member["member_id"]} for member in MEMBERS
                ]
            },
        }
        self._bind(
            "R2_P0_RUNTIME_ACCEPTANCE",
            "inputs/r2_acceptance.json",
            (
                json.dumps(acceptance, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode(),
        )
        admission_payload = b"".join(
            (
                json.dumps(member, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode()
            for member in MEMBERS
        )
        self._bind(
            "R2_ADMISSION_EVENTS",
            "inputs/admissions.jsonl",
            admission_payload,
        )
        for index, (item, member, completed_at) in enumerate(
            zip(
                self.config["predecessor_receipts"],
                MEMBERS,
                P0_COMPLETED,
                strict=True,
            )
        ):
            relative = f"inputs/p0-{index}.json"
            receipt = {
                "task_id": "TASK-21",
                "batch_id": "T21-R2",
                "horizon_id": "P0",
                "member_id": member["member_id"],
                "status": "COMPLETE",
                "stop_reason": None,
                "completed_at": completed_at,
            }
            path = self.root / relative
            write_json(path, receipt)
            item["path"] = relative
            item["sha256"] = digest(path)
        recovery = {
            "task_id": "TASK-21",
            "verdict": "PASS",
            "provider_api_rpc_wss_calls": 0,
            "health": {
                "health_state": "HEALTHY",
                "last_successful_backup_at": "2026-07-31T14:28:15.051Z",
                "last_successful_restore_at": "2026-07-31T14:30:38.396037Z",
            },
        }
        recovery_path = self.root / "inputs/recovery.json"
        write_json(recovery_path, recovery)
        self.config["recovery"]["receipt_path"] = "inputs/recovery.json"
        self.config["recovery"]["receipt_sha256"] = digest(recovery_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            yaml.safe_dump(self.config, sort_keys=False), encoding="utf-8"
        )


class Task21EventTriggeredFollowupTests(unittest.TestCase):
    def test_live_config_is_exact_when_ignored_inputs_are_present(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        admission = ROOT / config["protected_inputs"][2]["path"]
        if not admission.is_file():
            self.skipTest("ignored R2 runtime evidence is not present")
        validate_followup_config(config, ROOT)
        self.assertEqual(
            Task21FollowupExecutionGate(ATOM_ID).authority_phrase, ATOM_ID
        )
        with self.assertRaises(Task21FollowupAuthorityRequired):
            Task21FollowupExecutionGate("WRONG")

    def test_happy_path_is_exact_three_members_and_twenty_four_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticRepository(Path(directory))
            factory_members: list[str] = []

            def factory(member):
                factory_members.append(member["member_id"])
                return FakeQuoteTransport()

            receipt = run_event_triggered_followup_capture(
                gate=Task21FollowupExecutionGate(ATOM_ID),
                repo_root=repo.root,
                config_path=repo.config_path,
                transport_factory=factory,
                now=TickingNow(FIXED_NOW),
                sleeper=lambda _seconds: None,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=repo.output,
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(factory_members, [item["member_id"] for item in MEMBERS])
            self.assertEqual(receipt["capture"]["panels_complete"], 3)
            self.assertEqual(receipt["actual_actions"]["jupiter_calls"], 24)
            self.assertEqual(receipt["actual_actions"]["candidate_nominations"], 0)
            self.assertEqual(receipt["actual_actions"]["candidate_admissions"], 0)
            self.assertFalse(receipt["population"]["changed"])
            self.assertFalse(receipt["population"]["outcome_or_route_selection_used"])
            self.assertLessEqual(receipt["local_evidence"]["stored_bytes"], 16_777_216)
            self.assertEqual(len(list(repo.output.rglob("raw_events.jsonl"))), 3)
            self.assertFalse(receipt["next_boundary"]["external_authority_granted"])

    def test_all_member_eligibility_blocks_before_provider_or_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticRepository(Path(directory))
            factory_called = False

            def factory(_member):
                nonlocal factory_called
                factory_called = True
                return FakeQuoteTransport()

            with self.assertRaisesRegex(
                Task21FollowupError, "followup_population_not_ready"
            ):
                run_event_triggered_followup_capture(
                    gate=Task21FollowupExecutionGate(ATOM_ID),
                    repo_root=repo.root,
                    config_path=repo.config_path,
                    transport_factory=factory,
                    now=lambda: datetime(2026, 8, 1, 12, 17, 40, tzinfo=UTC),
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=repo.output,
                )
            self.assertFalse(factory_called)
            self.assertFalse(repo.output.exists())

    def test_stale_recovery_blocks_before_provider_or_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticRepository(Path(directory))
            factory_called = False

            def factory(_member):
                nonlocal factory_called
                factory_called = True
                return FakeQuoteTransport()

            with self.assertRaisesRegex(Task21FollowupError, "recovery_backup_stale"):
                run_event_triggered_followup_capture(
                    gate=Task21FollowupExecutionGate(ATOM_ID),
                    repo_root=repo.root,
                    config_path=repo.config_path,
                    transport_factory=factory,
                    now=lambda: datetime(2026, 8, 1, 14, 29, tzinfo=UTC),
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=repo.output,
                )
            self.assertFalse(factory_called)
            self.assertFalse(repo.output.exists())

    def test_partial_failure_retains_one_panel_and_stops_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticRepository(Path(directory))
            factory_calls = 0

            def factory(_member):
                nonlocal factory_calls
                factory_calls += 1
                return FakeQuoteTransport(stop_first=True)

            receipt = run_event_triggered_followup_capture(
                gate=Task21FollowupExecutionGate(ATOM_ID),
                repo_root=repo.root,
                config_path=repo.config_path,
                transport_factory=factory,
                now=TickingNow(FIXED_NOW),
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=repo.output,
            )
            self.assertEqual(receipt["status"], "STOPPED")
            self.assertEqual(receipt["stop_reason"], "INJECTED_TRANSPORT_STOP")
            self.assertEqual(factory_calls, 1)
            self.assertEqual(receipt["actual_actions"]["jupiter_calls"], 1)
            self.assertEqual(receipt["actual_actions"]["retries"], 0)
            self.assertEqual(len(list(repo.output.rglob("receipt.json"))), 1)

    def test_authority_and_cap_drift_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticRepository(Path(directory))
            changed = copy.deepcopy(repo.config)
            changed["authority"]["jupiter_calls_max"] = 25
            with self.assertRaisesRegex(
                Task21FollowupError, "authority_boundary_drift"
            ):
                validate_followup_config(changed, repo.root)
            with self.assertRaises(Task21FollowupAuthorityRequired):
                run_event_triggered_followup_capture(
                    gate=None,
                    repo_root=repo.root,
                    config_path=repo.config_path,
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
