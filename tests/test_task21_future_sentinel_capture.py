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
from solana_alpha_lab.task21_future_sentinel_capture import (
    FutureSentinelExecutionGate,
    Task21FutureSentinelAuthorityRequired,
    Task21FutureSentinelError,
    load_profiles,
    run_future_sentinel_capture,
    sha256_file,
    validate_runtime_config,
)


CORE_CONFIG_PATH = (
    ROOT / "configs" / "task21_future_sentinel_capture_core_v1.yaml"
)
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "task21_future_sentinel_capture_core_contract_v1.md"
)
ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "future_sentinel_capture_core_offline_acceptance_v1.json"
)
ANCHOR = datetime(2026, 7, 31, 7, 50, 34, 414367, tzinfo=UTC)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


class FakeTransport:
    def __init__(self, observed_at: datetime) -> None:
        self.observed_at = observed_at
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
        requested = self.observed_at + timedelta(milliseconds=sequence * 20)
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
                        "ammKey": f"future-sentinel-test-{sequence}",
                        "label": "TASK21_FUTURE_SENTINEL_TEST",
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
            "contextSlot": 430_000_000 + sequence,
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


class Task21FutureSentinelCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profiles = load_profiles(CORE_CONFIG_PATH)

    def _fixture(
        self, directory: str, horizon_id: str
    ) -> tuple[Path, Path, Path, datetime]:
        root = Path(directory) / "repo"
        root.mkdir(parents=True)
        profile = self.profiles[horizon_id]
        h0_path = root / "evidence" / "h0.json"
        events_path = root / "evidence" / "admissions.jsonl"
        predecessor_path = root / "evidence" / "predecessor.json"
        marker_path = root / "control" / "active_time_gates.json"
        h0 = {
            "task_id": "TASK-21",
            "status": "PASS",
            "h0": {
                "windows": [
                    {"triggered_at": "2026-07-31T07:49:54.431372Z"},
                    {"triggered_at": "2026-07-31T07:50:15.761730Z"},
                    {"triggered_at": "2026-07-31T07:50:34.414367Z"},
                ]
            },
        }
        _write_json(h0_path, h0)
        members = [
            {
                "member_id": f"member-{index}",
                "mint": f"TokenMint{index}11111111111111111111111111111111",
                "mint_decimals": 6,
                "hypothesis_version_id": "HYP-TEST-V1",
                "nomination_event_id": f"nomination-{index}",
                "exited_at": None,
            }
            for index in range(1, 4)
        ]
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in members),
            encoding="utf-8",
        )
        _write_json(
            predecessor_path,
            {
                "task_id": "TASK-21",
                "status": "PASS",
                "horizon_id": profile.predecessor_horizon_id,
                "atom_id": profile.predecessor_runtime_atom_id,
                "disposition": "CAPTURE_OR_GAP_ACCEPTED",
            },
        )
        earliest = ANCHOR + timedelta(
            seconds=profile.offset_seconds_from_latest_h0
        )
        latest = earliest + timedelta(minutes=10)
        gate_id = f"{profile.gate_id_prefix}TEST"
        marker = {
            "schema": "smial.active-time-gates",
            "schema_version": "1.0",
            "gates": [
                {
                    "gate_id": gate_id,
                    "task_id": "TASK-21",
                    "status": "ACTIVE_WAITING",
                    "earliest_at": earliest.isoformat().replace("+00:00", "Z"),
                    "latest_at": latest.isoformat().replace("+00:00", "Z"),
                    "required_next_atom": profile.runtime_atom_id,
                    "authority_granted_by_marker": {
                        "local_writes": 0,
                        "provider_api_rpc_wss_calls": 0,
                        "drive_actions": 0,
                        "cash_spend_usd_cents": 0,
                        "wallet_signer_transaction_actions": 0,
                    },
                }
            ],
        }
        _write_json(marker_path, marker)
        protected = [
            ("H0_TRACKED_ACCEPTANCE", h0_path),
            ("H0_ADMISSION_EVENTS", events_path),
            ("PREDECESSOR_TRACKED_ACCEPTANCE", predecessor_path),
        ]
        config = {
            "schema": "smial.task21_future_sentinel_runtime",
            "schema_version": "1.0",
            "task_id": "TASK-21",
            "atom_id": profile.runtime_atom_id,
            "horizon_id": profile.horizon_id,
            "predecessor_horizon_id": profile.predecessor_horizon_id,
            "status": "FROZEN_FORWARD_ONLY",
            "protected_inputs": [
                {
                    "role": role,
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_file(path),
                }
                for role, path in protected
            ],
            "dynamic_control": {
                "role": "ACTIVE_TIME_GATES",
                "path": "control/active_time_gates.json",
                "gate_id": gate_id,
                "allowed_statuses": ["ACTIVE_WAITING"],
            },
            "time_gate": {
                "gate_id": gate_id,
                "earliest_at": earliest.isoformat().replace("+00:00", "Z"),
                "latest_at": latest.isoformat().replace("+00:00", "Z"),
                "after_latest": "WRITE_EXPLICIT_GAP_NO_PROVIDER_NO_BACKFILL",
            },
            "population": {
                "member_ids": [item["member_id"] for item in members]
            },
            "sentinel": {
                "panels_max": 3,
                "provider_calls_per_panel_max": 8,
                "provider_calls_total_max": 24,
                "modeled_provider_credits_max": 24,
                "wall_seconds_max": 300,
                "received_response_bytes_max": 3145728,
                "durable_local_bytes_max": 16777216,
                "minimum_interval_seconds": 2.2,
                "notionals_usd": [10, 25, 50, 100],
                "local_output_root": profile.output_relative_root,
                "write_behavior": "CREATE_ONLY_CONTENT_ADDRESSED_RUN",
            },
            "recovery": {
                "required_health": "HEALTHY",
                "backup_age_hours_max_at_start": 24,
                "restore_age_hours_max_at_start": 168,
                "drive_actions": 0,
            },
            "authority": {
                "exact_phrase": profile.runtime_atom_id,
                "provider_api_rpc_wss_calls_max": 24,
                "drive_reads": 0,
                "drive_writes": 0,
                "credentials": 0,
                "cash_spend_usd_cents": 0,
                "wallet_signer_transaction_actions": 0,
                "scheduler_or_background_process": False,
                "deployment": False,
            },
        }
        config_path = root / "runtime.yaml"
        config_path.write_text(
            yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
        )
        recovery_path = root / "recovery.json"
        _write_json(
            recovery_path,
            {
                "task_id": "TASK-21",
                "verdict": "PASS",
                "provider_api_rpc_wss_calls": 0,
                "health": {
                    "health_state": "HEALTHY",
                    "last_successful_backup_at": (
                        earliest - timedelta(minutes=15)
                    ).isoformat().replace("+00:00", "Z"),
                    "last_successful_restore_at": (
                        earliest - timedelta(minutes=10)
                    ).isoformat().replace("+00:00", "Z"),
                },
            },
        )
        return root, config_path, recovery_path, earliest

    def test_core_config_has_exact_two_profiles_and_zero_authority(self) -> None:
        self.assertEqual(set(self.profiles), {"H72", "H168"})
        self.assertEqual(
            self.profiles["H72"].next_horizon_id,
            "H168",
        )
        self.assertIsNone(self.profiles["H168"].next_horizon_id)
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("WRAP_EXISTING_PRIMITIVES_THEN_BUILD_THIN_CORE", contract)
        self.assertIn("zero network/provider/API/RPC/WSS calls", contract)

    def test_h72_full_capture_uses_one_core_and_projects_h168(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config_path, recovery_path, earliest = self._fixture(
                directory, "H72"
            )
            profile = self.profiles["H72"]
            within = earliest + timedelta(minutes=5)
            receipt = run_future_sentinel_capture(
                profile=profile,
                gate=FutureSentinelExecutionGate(
                    "H72", profile.runtime_atom_id
                ),
                repo_root=root,
                config_path=config_path,
                recovery_receipt_path=recovery_path,
                transport_factory=lambda _member: FakeTransport(within),
                now=lambda: within,
                sleeper=lambda _seconds: None,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=Path(directory) / "output",
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["horizon_id"], "H72")
            self.assertEqual(receipt["sentinel"]["panels_complete"], 3)
            self.assertEqual(
                receipt["actual_actions"]["provider_api_rpc_wss_calls"], 24
            )
            self.assertEqual(receipt["next_boundary"]["horizon_id"], "H168")
            self.assertEqual(
                receipt["next_boundary"]["earliest_at"],
                "2026-08-07T07:50:34.414367Z",
            )
            self.assertEqual(
                len(list((Path(directory) / "output").rglob("raw_events.jsonl"))),
                3,
            )

    def test_h168_full_capture_does_not_invent_a7_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config_path, recovery_path, earliest = self._fixture(
                directory, "H168"
            )
            profile = self.profiles["H168"]
            within = earliest + timedelta(minutes=5)
            receipt = run_future_sentinel_capture(
                profile=profile,
                gate=FutureSentinelExecutionGate(
                    "H168", profile.runtime_atom_id
                ),
                repo_root=root,
                config_path=config_path,
                recovery_receipt_path=recovery_path,
                transport_factory=lambda _member: FakeTransport(within),
                now=lambda: within,
                sleeper=lambda _seconds: None,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=Path(directory) / "output",
            )
            boundary = receipt["next_boundary"]
            self.assertEqual(
                boundary["status"],
                "FOLLOWUP_SELECTION_REQUIRED_NOT_AUTHORIZED",
            )
            self.assertFalse(boundary["task21_acceptance_or_a7_eligible"])
            self.assertNotIn("atom_id", boundary)

    def test_before_window_blocks_without_transport_or_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config_path, recovery_path, earliest = self._fixture(
                directory, "H72"
            )
            called = False

            def factory(_member):
                nonlocal called
                called = True
                return FakeTransport(earliest)

            output = Path(directory) / "output"
            with self.assertRaisesRegex(
                Task21FutureSentinelError, "future_sentinel_window_not_open"
            ):
                run_future_sentinel_capture(
                    profile=self.profiles["H72"],
                    gate=None,
                    repo_root=root,
                    config_path=config_path,
                    recovery_receipt_path=recovery_path,
                    transport_factory=factory,
                    now=lambda: earliest - timedelta(microseconds=1),
                    output_root_override=output,
                )
            self.assertFalse(called)
            self.assertFalse(output.exists())

    def test_after_window_records_gap_without_transport_or_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config_path, recovery_path, earliest = self._fixture(
                directory, "H72"
            )
            called = False

            def factory(_member):
                nonlocal called
                called = True
                return FakeTransport(earliest)

            receipt = run_future_sentinel_capture(
                profile=self.profiles["H72"],
                gate=None,
                repo_root=root,
                config_path=config_path,
                recovery_receipt_path=recovery_path,
                transport_factory=factory,
                now=lambda: earliest + timedelta(minutes=10, microseconds=1),
                output_root_override=Path(directory) / "output",
            )
            self.assertEqual(receipt["status"], "GAP")
            self.assertFalse(called)
            self.assertFalse(receipt["backfill"])
            self.assertFalse(receipt["rescheduled"])
            self.assertEqual(
                receipt["actual_actions"]["provider_api_rpc_wss_calls"], 0
            )

    def test_wrong_authority_and_stale_recovery_fail_closed(self) -> None:
        with self.assertRaises(Task21FutureSentinelAuthorityRequired):
            FutureSentinelExecutionGate("H72", "WRONG")
        with tempfile.TemporaryDirectory() as directory:
            root, config_path, recovery_path, earliest = self._fixture(
                directory, "H72"
            )
            recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
            recovery["health"]["last_successful_backup_at"] = (
                earliest - timedelta(hours=25)
            ).isoformat().replace("+00:00", "Z")
            _write_json(recovery_path, recovery)
            called = False

            def factory(_member):
                nonlocal called
                called = True
                return FakeTransport(earliest)

            profile = self.profiles["H72"]
            with self.assertRaisesRegex(
                Task21FutureSentinelError, "recovery_backup_stale"
            ):
                run_future_sentinel_capture(
                    profile=profile,
                    gate=FutureSentinelExecutionGate(
                        "H72", profile.runtime_atom_id
                    ),
                    repo_root=root,
                    config_path=config_path,
                    recovery_receipt_path=recovery_path,
                    transport_factory=factory,
                    now=lambda: earliest + timedelta(minutes=5),
                    output_root_override=Path(directory) / "output",
                )
            self.assertFalse(called)

    def test_runtime_drift_and_path_escape_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config_path, _recovery_path, _earliest = self._fixture(
                directory, "H72"
            )
            profile = self.profiles["H72"]
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            changed = copy.deepcopy(config)
            changed["sentinel"]["provider_calls_total_max"] = 25
            with self.assertRaisesRegex(
                Task21FutureSentinelError, "future_sentinel_cap_drift"
            ):
                validate_runtime_config(changed, root, profile)
            changed = copy.deepcopy(config)
            changed["time_gate"]["latest_at"] = (
                ANCHOR
                + timedelta(seconds=profile.offset_seconds_from_latest_h0)
                + timedelta(minutes=10, microseconds=1)
            ).isoformat().replace("+00:00", "Z")
            with self.assertRaisesRegex(
                Task21FutureSentinelError, "future_sentinel_time_gate_drift"
            ):
                validate_runtime_config(changed, root, profile)
            changed = copy.deepcopy(config)
            changed["protected_inputs"][0]["path"] = "../escape.json"
            with self.assertRaisesRegex(
                Task21FutureSentinelError, "repository_relative_path_invalid"
            ):
                validate_runtime_config(changed, root, profile)
            changed = copy.deepcopy(config)
            predecessor_path = root / "evidence" / "predecessor.json"
            predecessor = json.loads(
                predecessor_path.read_text(encoding="utf-8")
            )
            predecessor["status"] = "FAIL"
            _write_json(predecessor_path, predecessor)
            for item in changed["protected_inputs"]:
                if item["role"] == "PREDECESSOR_TRACKED_ACCEPTANCE":
                    item["sha256"] = sha256_file(predecessor_path)
            with self.assertRaisesRegex(
                Task21FutureSentinelError,
                "future_sentinel_predecessor_acceptance_drift",
            ):
                validate_runtime_config(changed, root, profile)

    def test_create_only_rejects_same_run_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config_path, recovery_path, earliest = self._fixture(
                directory, "H72"
            )
            profile = self.profiles["H72"]
            within = earliest + timedelta(minutes=5)
            kwargs = {
                "profile": profile,
                "gate": FutureSentinelExecutionGate(
                    "H72", profile.runtime_atom_id
                ),
                "repo_root": root,
                "config_path": config_path,
                "recovery_receipt_path": recovery_path,
                "transport_factory": lambda _member: FakeTransport(within),
                "now": lambda: within,
                "sleeper": lambda _seconds: None,
                "available_disk_bytes": 10 * 1024 * 1024 * 1024,
                "output_root_override": Path(directory) / "output",
            }
            run_future_sentinel_capture(**kwargs)
            with self.assertRaisesRegex(
                Task21FutureSentinelError,
                "future_sentinel_run_output_already_exists",
            ):
                run_future_sentinel_capture(**kwargs)

    def test_historical_acceptance_is_audit_only_after_value_rebase(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            _sha(ACCEPTANCE_PATH),
            "f17303df8658b53ea36ee5672d8e993ba874f2dbaf983997c981475b02804bab",
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["targeted_validation"], "9_OF_9_PASS")
        for artifact in receipt["artifacts"][:3]:
            self.assertEqual(_sha(ROOT / artifact["path"]), artifact["sha256"])
        rebase = yaml.safe_load(
            (
                ROOT
                / "configs"
                / "task21_post_h6_gap_sentinel_value_rebase_v1.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            rebase["protected_history"]["historical_future_core"]["disposition"],
            "OFFLINE_HISTORICAL_NOT_RUNTIME_BOUND",
        )
        self.assertEqual(rebase["future_horizons"]["mandatory"], [])
        actions = receipt["actual_actions"]
        for key, value in actions.items():
            if isinstance(value, bool):
                self.assertFalse(value, key)
            else:
                self.assertEqual(value, 0, key)


if __name__ == "__main__":
    unittest.main()
