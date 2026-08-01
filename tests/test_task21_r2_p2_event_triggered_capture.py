from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_r2_p2_event_triggered_capture import (
    ATOM_ID,
    Task21P2AuthorityRequired,
    Task21P2Error,
    Task21P2ExecutionGate,
    run_r2_p2_capture,
    validate_p2_config,
)
from tests.test_task21_event_triggered_followup_capture import (
    FakeQuoteTransport,
    MEMBERS,
    P0_COMPLETED,
    TickingNow,
    write_json,
)


CONFIG = ROOT / "configs/task21_r2_p2_event_triggered_capture_v1.yaml"
ACCEPTANCE = (
    ROOT
    / "docs/evidence/task21/r2_p2_event_triggered_capture_offline_acceptance_v1.json"
)
COMPATIBILITY = (
    ROOT / "docs/evidence/task21/p2_multi_batch_compatibility_v1.json"
)
FIXED_NOW = datetime(2026, 8, 1, 13, 0, tzinfo=UTC)
P1_COMPLETED = [
    "2026-08-01T12:26:22.220156Z",
    "2026-08-01T12:26:40.700638Z",
    "2026-08-01T12:26:59.213587Z",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SyntheticP2Repository:
    def __init__(
        self,
        root: Path,
        *,
        config_path: Path = CONFIG,
        members: list[dict] = MEMBERS,
        p0_completed: list[str] = P0_COMPLETED,
        p1_completed: list[str] = P1_COMPLETED,
        recovery_backup_at: str = "2026-07-31T14:28:15.051Z",
        recovery_restore_at: str = "2026-07-31T14:30:38.396037Z",
    ) -> None:
        self.root = root
        self.config = copy.deepcopy(
            yaml.safe_load(config_path.read_text(encoding="utf-8"))
        )
        self.members = members
        self.p0_completed = p0_completed
        self.p1_completed = p1_completed
        self.recovery_backup_at = recovery_backup_at
        self.recovery_restore_at = recovery_restore_at
        self.config_path = root / "configs/p2.yaml"
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
        roles = [item["role"] for item in self.config["protected_inputs"]]
        p0_role = next(role for role in roles if role.endswith("P0_RUNTIME_ACCEPTANCE"))
        p1_role = next(role for role in roles if role.endswith("P1_RUNTIME_ACCEPTANCE"))
        admission_role = next(role for role in roles if role.endswith("ADMISSION_EVENTS"))
        event_path = (
            ROOT / "configs/task21_event_triggered_final_cohort_runtime_v1.yaml"
        )
        self._bind(
            "EVENT_TRIGGERED_RUNTIME_PLAN",
            "inputs/event_runtime.yaml",
            event_path.read_bytes(),
        )
        p0_acceptance = {
            "status": "PASS",
            "p0": {
                "windows": [
                    {
                        "member_id": member["member_id"],
                        "completed_at": completed_at,
                    }
                    for member, completed_at in zip(
                        self.members, self.p0_completed, strict=True
                    )
                ]
            },
        }
        self._bind(
            p0_role,
            "inputs/p0_acceptance.json",
            (
                json.dumps(
                    p0_acceptance, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            ).encode(),
        )
        p1_acceptance = {
            "status": "PASS",
            "population": {
                "member_ids": [item["member_id"] for item in self.members]
            },
            "p1": {"panels_complete": len(self.members), "panels_stopped": 0},
        }
        self._bind(
            p1_role,
            "inputs/p1_acceptance.json",
            (
                json.dumps(
                    p1_acceptance, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            ).encode(),
        )
        admission_payload = b"".join(
            (
                json.dumps(member, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode()
            for member in self.members
        )
        self._bind(
            admission_role,
            "inputs/admissions.jsonl",
            admission_payload,
        )
        for index, (item, member, completed_at) in enumerate(
            zip(
                self.config["predecessor_receipts"],
                self.members,
                self.p1_completed,
                strict=True,
            )
        ):
            relative = f"inputs/p1-{index}.json"
            receipt = {
                "task_id": "TASK-21",
                "batch_id": self.config["panel"]["batch_id"],
                "horizon_id": "P1",
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
                "last_successful_backup_at": self.recovery_backup_at,
                "last_successful_restore_at": self.recovery_restore_at,
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


class Task21R2P2CaptureTests(unittest.TestCase):
    def test_live_config_is_exact_when_ignored_inputs_are_present(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        predecessor = ROOT / config["predecessor_receipts"][0]["path"]
        if not predecessor.is_file():
            self.skipTest("ignored P1 runtime evidence is not present")
        validate_p2_config(config, ROOT)
        self.assertEqual(Task21P2ExecutionGate(ATOM_ID).authority_phrase, ATOM_ID)
        with self.assertRaises(Task21P2AuthorityRequired):
            Task21P2ExecutionGate("WRONG")

    def test_happy_path_captures_three_final_panels_and_twenty_four_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticP2Repository(Path(directory))
            factory_members: list[str] = []

            def factory(member):
                factory_members.append(member["member_id"])
                return FakeQuoteTransport()

            receipt = run_r2_p2_capture(
                gate=Task21P2ExecutionGate(ATOM_ID),
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
            self.assertEqual(receipt["p2"]["panels_complete"], 3)
            self.assertEqual(receipt["actual_actions"]["jupiter_calls"], 24)
            self.assertEqual(receipt["actual_actions"]["candidate_nominations"], 0)
            self.assertEqual(receipt["actual_actions"]["candidate_admissions"], 0)
            self.assertFalse(receipt["population"]["changed"])
            self.assertFalse(receipt["population"]["outcome_or_route_selection_used"])
            self.assertLessEqual(receipt["local_evidence"]["stored_bytes"], 16_777_216)
            self.assertEqual(len(list(repo.output.rglob("raw_events.jsonl"))), 3)
            self.assertEqual(
                receipt["next_boundary"]["status"],
                "R2_COMPLETE_REVIEW_REQUIRED_FOR_R3_SOURCE_P0",
            )
            self.assertIsNone(receipt["next_boundary"]["atom_id"])
            self.assertFalse(
                receipt["next_boundary"]["r3_source_or_admission_authorized"]
            )

    def test_all_member_eligibility_blocks_before_provider_or_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticP2Repository(Path(directory))
            factory_called = False

            def factory(_member):
                nonlocal factory_called
                factory_called = True
                return FakeQuoteTransport()

            with self.assertRaisesRegex(Task21P2Error, "p2_population_not_ready"):
                run_r2_p2_capture(
                    gate=Task21P2ExecutionGate(ATOM_ID),
                    repo_root=repo.root,
                    config_path=repo.config_path,
                    transport_factory=factory,
                    now=lambda: datetime(2026, 8, 1, 12, 56, 50, tzinfo=UTC),
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=repo.output,
                )
            self.assertFalse(factory_called)
            self.assertFalse(repo.output.exists())

    def test_stale_recovery_blocks_before_provider_or_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticP2Repository(Path(directory))
            factory_called = False

            def factory(_member):
                nonlocal factory_called
                factory_called = True
                return FakeQuoteTransport()

            with self.assertRaisesRegex(Task21P2Error, "recovery_backup_stale"):
                run_r2_p2_capture(
                    gate=Task21P2ExecutionGate(ATOM_ID),
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
            repo = SyntheticP2Repository(Path(directory))
            factory_calls = 0

            def factory(_member):
                nonlocal factory_calls
                factory_calls += 1
                return FakeQuoteTransport(stop_first=True)

            receipt = run_r2_p2_capture(
                gate=Task21P2ExecutionGate(ATOM_ID),
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

    def test_authority_and_budget_drift_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticP2Repository(Path(directory))
            changed = copy.deepcopy(repo.config)
            changed["authority"]["jupiter_calls_max"] = 25
            with self.assertRaisesRegex(Task21P2Error, "authority_boundary_drift"):
                validate_p2_config(changed, repo.root)
            changed = copy.deepcopy(repo.config)
            changed["budget"]["used_before_p2"]["quote_requests"] = 105
            with self.assertRaisesRegex(Task21P2Error, "budget_contract_drift"):
                validate_p2_config(changed, repo.root)
            with self.assertRaises(Task21P2AuthorityRequired):
                run_r2_p2_capture(
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
        evolving = {
            "src/solana_alpha_lab/task21_r2_p2_event_triggered_capture.py",
            "tests/test_task21_r2_p2_event_triggered_capture.py",
        }
        for item in receipt["artifacts"]:
            if item["path"] not in evolving:
                self.assertEqual(digest(ROOT / item["path"]), item["sha256"])
        compatibility = json.loads(COMPATIBILITY.read_text(encoding="utf-8"))
        self.assertEqual(compatibility["status"], "PASS")
        module = compatibility["module"]
        self.assertEqual(
            module["historical_r2_sha256"],
            next(
                item["sha256"]
                for item in receipt["artifacts"]
                if item["path"]
                == "src/solana_alpha_lab/task21_r2_p2_event_triggered_capture.py"
            ),
        )
        self.assertEqual(digest(ROOT / module["path"]), module["delivered_sha256"])


if __name__ == "__main__":
    unittest.main()
