"""Zero-secret tests for stage-2 Google Drive off-host backup copy."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_operational_packet import (  # noqa: E402
    compose_health_classes,
)
from solana_alpha_lab.factory.offhost_backup import (  # noqa: E402
    FORBIDDEN_RCLONE_SUBCOMMANDS,
    INTERNAL_PAYLOAD_PLANNING_BUDGET_30D,
    OWNER_BACKUP_TRAFFIC_TARGET_30D,
    PLANNING_FIXTURE_PAYLOAD_30D,
    OffhostBackupError,
    OffhostConfig,
    agent_durability_classification,
    build_rclone_argv,
    conservative_full_pressure_bytes,
    copy_offhost_backup,
    load_offhost_config,
    newest_checkpoint_filename,
    offhost_health_snapshot,
    offhost_recovery_readout,
    planning_fixture_payload_30d,
    read_offhost_receipt,
    restore_from_recovery_checkpoint,
    run_offhost_checkpoint,
    validate_rclone_argv,
    validate_recovery_checkpoint,
    verify_backup_bundle,
    write_offhost_receipt,
)
from solana_alpha_lab.factory.remote_ops import (  # noqa: E402
    backup_plane_lock,
    load_config_v1_1,
    package_backup,
    project_health,
    resolve_backup_sink,
    RemoteOpsError,
)

from tests.test_factory_remote_operations import COPY_RELATIVES as REMOTE_OPS_COPY_RELATIVES

OFFHOST_RELATIVES = list(REMOTE_OPS_COPY_RELATIVES) + [
    "catalog/schemas/factory_remote_operations_v1_1.schema.json",
    "configs/factory_remote_operations_v1_1.yaml",
    "configs/factory_remote_ops/factory-remote-backup-gdrive.service",
    "configs/factory_remote_ops/factory-remote-backup-gdrive.timer",
    "configs/factory_remote_ops/factory-remote-backup-gdrive-delta.service",
    "configs/factory_remote_ops/factory-remote-backup-gdrive-delta.timer",
    "configs/factory_remote_ops/factory-observation-schedule.service",
    "configs/factory_remote_ops/factory-observation-schedule.timer",
]


def _seed_tree(dst: Path) -> Path:
    for relative in OFFHOST_RELATIVES:
        source = ROOT / relative
        target = dst / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    ops = dst / "local/factory_v1/operational_state.sqlite"
    paper = dst / "local/factory_v1/paper_plane_state.sqlite"
    obs = dst / "local/factory_v1/observation_schedule_state.sqlite"
    ops.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ops)
    conn.execute("CREATE TABLE IF NOT EXISTS ops_marker (k TEXT PRIMARY KEY, v TEXT)")
    conn.commit()
    conn.close()
    conn = sqlite3.connect(obs)
    conn.execute("CREATE TABLE IF NOT EXISTS activations (activation_id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()
    conn = sqlite3.connect(paper)
    conn.execute(
        "CREATE TABLE bot_instances (bot_instance_id TEXT PRIMARY KEY, strategy_id TEXT, strategy_version TEXT, mode TEXT, status TEXT, started_at TEXT, stopped_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE positions (position_id TEXT PRIMARY KEY, bot_instance_id TEXT, mint TEXT, state TEXT, signal_kind TEXT, entered_notional_usd REAL, exit_notional_usd REAL, opened_at TEXT, closed_at TEXT)"
    )
    conn.execute(
        "INSERT INTO bot_instances VALUES ('BOT-1','S','v1','PAPER','RUNNING','2026-08-22T00:00:00Z',NULL)"
    )
    conn.execute(
        "INSERT INTO positions VALUES ('P-1','BOT-1','M','RECONCILED','SIM',1,1,'2026-08-22T00:00:00Z',NULL)"
    )
    conn.commit()
    conn.close()
    (dst / "local/factory_v1/observation_rdp").mkdir(parents=True, exist_ok=True)
    return dst


class FakeRcloneRunner:
    def __init__(self) -> None:
        self.objects: dict[str, int] = {}
        self.payloads: dict[str, bytes] = {}
        self.calls: list[list[str]] = []
        self.fail_next_copy = False
        self.fail_copy_count = 0

    @staticmethod
    def _subcommand(argv: list[str]) -> str:
        for index, token in enumerate(argv):
            if token == "--config" and index + 2 < len(argv):
                return argv[index + 2]
        raise AssertionError(f"could not find rclone subcommand in {argv}")

    def __call__(self, argv: list[str]) -> Any:
        self.calls.append(list(argv))
        validate_rclone_argv(argv)
        sub = self._subcommand(argv)
        if sub == "lsjson":
            remote = argv[-1]
            if remote not in self.objects:
                return type("R", (), {"returncode": 1, "stdout": "[]", "stderr": "object not found"})()
            payload = [{"Path": Path(remote).name, "Size": self.objects[remote]}]
            return type("R", (), {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""})()
        if sub == "copyto":
            if self.fail_next_copy or self.fail_copy_count > 0:
                if self.fail_copy_count > 0:
                    self.fail_copy_count -= 1
                return type("R", (), {"returncode": 1, "stdout": "", "stderr": "copy failed"})()
            source = Path(argv[-2])
            remote = argv[-1]
            data = source.read_bytes()
            self.objects[remote] = len(data)
            self.payloads[remote] = data
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        raise AssertionError(f"unexpected subcommand {sub}")


class FactoryOffhostBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = _seed_tree(Path(self.tmp.name))
        self.config = load_offhost_config(self.root)
        assert self.config is not None
        self.rclone_conf = Path(self.tmp.name) / "rclone.conf"
        self.rclone_conf.write_text("[factory-gdrive]\ntype = drive\n", encoding="utf-8")
        self.rclone_conf.chmod(0o600)
        self.config = OffhostConfig(
            remote_name=self.config.remote_name,
            destination_root=self.config.destination_root,
            rclone_config_absolute=self.rclone_conf,
            rclone_bin=self.config.rclone_bin,
            receipt_relative=self.config.receipt_relative,
            freshness_current_max_seconds=self.config.freshness_current_max_seconds,
            freshness_degraded_max_seconds=self.config.freshness_degraded_max_seconds,
        )
        self.runner = FakeRcloneRunner()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _pack(self) -> Path:
        loaded = load_config_v1_1(self.root)
        packed = package_backup(self.root, config=loaded)
        sink = resolve_backup_sink(self.root, loaded, {})
        return sink / packed["bundle"]

    def test_a_valid_backup_triggers_one_copy(self) -> None:
        bundle = self._pack()
        receipt = copy_offhost_backup(
            self.root,
            config=self.config,
            runner=self.runner,
            deploy_git_sha="a" * 40,
        )
        self.assertEqual(receipt["terminal"], "COPIED_VERIFIED")
        copy_calls = [c for c in self.runner.calls if c[3] == "copyto"]
        self.assertEqual(len(copy_calls), 1)
        self.assertEqual(copy_calls[0][-2], str(bundle))

    def test_b_already_present_is_idempotent(self) -> None:
        bundle = self._pack()
        remote = self.config.remote_object(bundle.name)
        self.runner.objects[remote] = bundle.stat().st_size
        receipt = copy_offhost_backup(
            self.root,
            config=self.config,
            runner=self.runner,
            deploy_git_sha="b" * 40,
        )
        self.assertEqual(receipt["terminal"], "ALREADY_PRESENT_VERIFIED")
        self.assertEqual([c for c in self.runner.calls if FakeRcloneRunner._subcommand(c) == "copyto"], [])

    def test_c_filename_sha_mismatch_fails_closed(self) -> None:
        bundle = self._pack()
        wrong_name = bundle.parent / f"BACKUP_{'0' * 64}.zip"
        wrong_name.write_bytes(bundle.read_bytes())
        import os

        os.utime(wrong_name, (bundle.stat().st_mtime + 10, bundle.stat().st_mtime + 10))
        bundle.unlink()
        with self.assertRaises(OffhostBackupError):
            copy_offhost_backup(self.root, config=self.config, runner=self.runner)
        self.assertEqual([c for c in self.runner.calls if FakeRcloneRunner._subcommand(c) == "copyto"], [])

    def test_d_remote_size_conflict_never_overwrites(self) -> None:
        bundle = self._pack()
        remote = self.config.remote_object(bundle.name)
        self.runner.objects[remote] = bundle.stat().st_size + 1
        with self.assertRaises(OffhostBackupError):
            copy_offhost_backup(self.root, config=self.config, runner=self.runner)
        self.assertEqual([c for c in self.runner.calls if FakeRcloneRunner._subcommand(c) == "copyto"], [])

    def test_e_rclone_failure_writes_failed_receipt(self) -> None:
        self._pack()
        self.runner.fail_next_copy = True
        with self.assertRaises(OffhostBackupError):
            copy_offhost_backup(self.root, config=self.config, runner=self.runner)
        receipt = read_offhost_receipt(self.root, self.config)
        assert receipt is not None
        self.assertEqual(receipt["terminal"], "COPY_FAILED")
        health = offhost_health_snapshot(self.root, config=self.config)
        self.assertEqual(health["offhost_backup_state"], "FAILED")

    def test_f_no_delete_or_sync_commands_constructible(self) -> None:
        for forbidden in FORBIDDEN_RCLONE_SUBCOMMANDS:
            with self.assertRaises(OffhostBackupError):
                build_rclone_argv(self.config, forbidden, "a", "b")

    def test_g_receipt_has_no_credentials(self) -> None:
        self._pack()
        copy_offhost_backup(self.root, config=self.config, runner=self.runner)
        receipt = read_offhost_receipt(self.root, self.config)
        assert receipt is not None
        dumped = json.dumps(receipt)
        self.assertNotIn("access_token", dumped)
        self.assertNotIn("refresh_token", dumped)
        self.assertNotIn("client_secret", dumped)

    def test_h_health_distinguishes_local_and_offhost_freshness(self) -> None:
        loaded = load_config_v1_1(self.root)
        sink = resolve_backup_sink(self.root, loaded, {})
        now = datetime.now(UTC)
        bundle = self._pack()

        write_offhost_receipt(
            self.root,
            self.config,
            {
                "uploaded_at": (now - timedelta(hours=49)).isoformat().replace("+00:00", "Z"),
                "verified_at": (now - timedelta(hours=49)).isoformat().replace("+00:00", "Z"),
                "source_backup_filename": bundle.name,
                "source_sha256": bundle.stem.removeprefix("BACKUP_"),
                "source_bytes": bundle.stat().st_size,
                "remote_logical_path": self.config.remote_object(bundle.name),
                "remote_bytes": bundle.stat().st_size,
                "terminal": "COPIED_VERIFIED",
                "deploy_git_sha": "c" * 40,
            },
        )
        stale = offhost_health_snapshot(self.root, config=self.config, now=now)
        self.assertEqual(stale["offhost_backup_state"], "HARD_ATTENTION")

        with patch(
            "solana_alpha_lab.factory.offhost_backup.offhost_health_snapshot",
            return_value=stale,
        ):
            health = project_health(
                root=self.root, process_alive=True, config=loaded, now=now, environ={}
            )
        self.assertEqual(health["dimensions"]["backup_age"], "OK")
        self.assertEqual(health["verdict"], "DEGRADED_OFFHOST_BACKUP_STALE")

        write_offhost_receipt(
            self.root,
            self.config,
            {
                "uploaded_at": now.isoformat().replace("+00:00", "Z"),
                "verified_at": now.isoformat().replace("+00:00", "Z"),
                "source_backup_filename": bundle.name,
                "source_sha256": bundle.stem.removeprefix("BACKUP_"),
                "source_bytes": bundle.stat().st_size,
                "remote_logical_path": self.config.remote_object(bundle.name),
                "remote_bytes": bundle.stat().st_size,
                "terminal": "ALREADY_PRESENT_VERIFIED",
                "deploy_git_sha": "d" * 40,
            },
        )
        current = offhost_health_snapshot(self.root, config=self.config, now=now)
        self.assertEqual(current["offhost_backup_state"], "CURRENT")
        self.assertEqual(current["durability_domain"], "OFF_HOST_INDEPENDENT")

        old = now - timedelta(hours=30)
        for path in sink.glob("BACKUP_*.zip"):
            os.utime(path, (old.timestamp(), old.timestamp()))
        local_stale = project_health(
            root=self.root,
            process_alive=True,
            config=loaded,
            now=now,
            environ={
                "FACTORY_TELEGRAM_BOT_TOKEN": "test",
                "FACTORY_TELEGRAM_CHAT_ID": "1",
            },
        )
        with patch(
            "solana_alpha_lab.factory.offhost_backup.offhost_health_snapshot",
            return_value=current,
        ):
            local_stale = project_health(
                root=self.root,
                process_alive=True,
                config=loaded,
                now=now,
                environ={
                    "FACTORY_TELEGRAM_BOT_TOKEN": "test",
                    "FACTORY_TELEGRAM_CHAT_ID": "1",
                },
            )
        self.assertEqual(local_stale["dimensions"]["backup_age"], "STALE")
        self.assertEqual(local_stale["offhost_backup_state"], "CURRENT")

    def test_compose_health_classes_offhost_stale_without_local_stale(self) -> None:
        packet = {
            "backup_domain": "PARENT_INDEPENDENT_GIT_SIDE",
            "backup_age_seconds": 120,
            "last_backup_at": "2026-09-01T00:00:00Z",
            "restore_marker_unresolved": False,
            "offhost_backup_state": "HARD_ATTENTION",
        }
        classes = compose_health_classes(packet)
        self.assertIn("OFFHOST_BACKUP_STALE", classes)
        self.assertNotIn("BACKUP_DEGRADED", classes)

    def test_config_v1_1_proven_offhost_semantics(self) -> None:
        cfg = load_config_v1_1(ROOT)
        self.assertEqual(cfg["backup"]["google_drive_role"], "PROVEN_OFFHOST_DURABILITY")
        self.assertEqual(cfg["backup"]["google_drive_role_prior"], "OPTIONAL_COLD_COPY_NOT_DOD")
        self.assertEqual(
            cfg["backup"]["google_drive_role_provenance"]["unproven_follow_up"],
            "LIVE_FACTORY_INCREMENTAL_RESTORE_COMMISSIONING",
        )

    def test_enabled_offhost_with_unready_rclone_is_failed_not_silent(self) -> None:
        broken = OffhostConfig(
            remote_name=self.config.remote_name,
            destination_root=self.config.destination_root,
            rclone_config_absolute=Path(self.tmp.name) / "missing-rclone.conf",
            rclone_bin=self.config.rclone_bin,
            receipt_relative=self.config.receipt_relative,
            freshness_current_max_seconds=self.config.freshness_current_max_seconds,
            freshness_degraded_max_seconds=self.config.freshness_degraded_max_seconds,
        )
        health = offhost_health_snapshot(self.root, config=broken)
        self.assertTrue(health["configured"])
        self.assertEqual(health["offhost_backup_state"], "FAILED")
        classes = compose_health_classes(
            {
                "backup_domain": "PARENT_INDEPENDENT_GIT_SIDE",
                "backup_age_seconds": 60,
                "last_backup_at": "2026-09-01T00:00:00Z",
                "restore_marker_unresolved": False,
                "offhost_backup_state": "FAILED",
            }
        )
        self.assertIn("OFFHOST_BACKUP_FAILED", classes)
        labels = agent_durability_classification(
            local_backup_state="OK", offhost_backup_state="FAILED"
        )
        self.assertTrue(labels["OFFHOST_BACKUP_STALE"])
        self.assertFalse(labels["OFFHOST_NOT_CONFIGURED"])

    def test_agent_classification_fresh_agent_labels(self) -> None:
        self.assertEqual(
            agent_durability_classification(
                local_backup_state="OK", offhost_backup_state="CURRENT"
            ),
            {
                "LOCAL_BACKUP_OK": True,
                "OFFHOST_BACKUP_OK": True,
                "OFFHOST_BACKUP_STALE": False,
                "OFFHOST_NOT_CONFIGURED": False,
            },
        )
        self.assertTrue(
            agent_durability_classification(
                local_backup_state="OK", offhost_backup_state="HARD_ATTENTION"
            )["OFFHOST_BACKUP_STALE"]
        )
        self.assertTrue(
            agent_durability_classification(
                local_backup_state="STALE", offhost_backup_state="UNCONFIGURED"
            )["OFFHOST_NOT_CONFIGURED"]
        )

    def test_offhost_recovery_readout_exposes_architecture(self) -> None:
        bundle = self._pack()
        write_offhost_receipt(
            self.root,
            self.config,
            {
                "uploaded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "verified_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "source_backup_filename": bundle.name,
                "source_sha256": bundle.stem.removeprefix("BACKUP_"),
                "source_bytes": bundle.stat().st_size,
                "remote_logical_path": self.config.remote_object(bundle.name),
                "remote_bytes": bundle.stat().st_size,
                "terminal": "COPIED_VERIFIED",
                "deploy_git_sha": "e" * 40,
            },
        )
        readout = offhost_recovery_readout(self.root, deploy_git_sha="e" * 40)
        self.assertEqual(readout["schema"], "smial.factory-offhost-recovery-readout")
        self.assertTrue(readout["agent_classification"]["LOCAL_BACKUP_OK"])
        self.assertIn("stage_2_offhost", readout["architecture"])
        self.assertEqual(
            readout["architecture"]["stage_2_offhost"]["unproven_follow_up"],
            "LIVE_FACTORY_INCREMENTAL_RESTORE_COMMISSIONING",
        )
        self.assertEqual(
            readout["architecture"]["stage_2_offhost"]["discovery"],
            "RECOVERY_CHECKPOINT_FILENAME_TIMESTAMP_THEN_CONTENT_HASH",
        )
        self.assertEqual(
            readout["required_acceptance_terminal"],
            "FACTORY_DAILY_DELTA_WEEKLY_FULL_OFFHOST_BACKUP_PASS",
        )
        dumped = json.dumps(readout)
        self.assertNotIn("access_token", dumped)

    @unittest.skipUnless(os.name == "posix", "symlink proof requires POSIX")
    def test_verify_backup_bundle_rejects_symlink(self) -> None:
        bundle = self._pack()
        link = bundle.parent / "linked.zip"
        link.symlink_to(bundle)
        with self.assertRaises(OffhostBackupError):
            verify_backup_bundle(link)

    def test_streaming_package_is_not_memory_proportional(self) -> None:
        import inspect

        from solana_alpha_lab.factory import remote_ops as remote_ops_mod

        source = inspect.getsource(remote_ops_mod.package_backup)
        delta_source = inspect.getsource(remote_ops_mod.package_delta_backup)
        self.assertNotIn("BytesIO", source)
        self.assertNotIn("BytesIO", delta_source)
        self.assertNotIn("read_bytes()", source)
        self.assertIn("_stream_zip_entry", source)
        self.assertIn("_stream_zip_entry", delta_source)
        service = (ROOT / "configs/factory_remote_ops/factory-remote-backup.service").read_text(
            encoding="utf-8"
        )
        timer = (ROOT / "configs/factory_remote_ops/factory-remote-backup.timer").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("OnSuccess=", service)
        self.assertIn("00:15:00 UTC", timer)
        self.assertIn("12:15:00 UTC", timer)
        cfg = load_config_v1_1(ROOT)
        self.assertEqual(cfg["backup"]["local_full_schedule"], "12h")
        self.assertEqual(cfg["backup"]["local_verified_bundle_retention"], 1)

    def test_retain_one_verified_local_full(self) -> None:
        loaded = load_config_v1_1(self.root)
        first = package_backup(self.root, config=loaded)
        sink = resolve_backup_sink(self.root, loaded, {})
        (self.root / "local/factory_v1/observation_rdp/a.bin").write_bytes(b"alpha")
        second = package_backup(self.root, config=loaded)
        names = sorted(path.name for path in sink.glob("BACKUP_*.zip"))
        self.assertEqual(names, [second["bundle"]])
        self.assertNotEqual(first["sha256"], second["sha256"])
        self.assertEqual(second["pruned"], [first["bundle"]])

    def test_planning_fixture_payload_under_internal_budget(self) -> None:
        self.assertEqual(planning_fixture_payload_30d(), 202_000_000_000)
        self.assertEqual(PLANNING_FIXTURE_PAYLOAD_30D, 202_000_000_000)
        self.assertLess(planning_fixture_payload_30d(), INTERNAL_PAYLOAD_PLANNING_BUDGET_30D)
        self.assertEqual(OWNER_BACKUP_TRAFFIC_TARGET_30D, 300_000_000_000)
        pressure = conservative_full_pressure_bytes(
            current_full_payload_size=40 * 1_000_000_000,
            projected_non_full_delta_payload=52 * 1_000_000_000,
        )
        self.assertGreater(pressure, INTERNAL_PAYLOAD_PLANNING_BUDGET_30D)
        health = offhost_health_snapshot(self.root, config=self.config)
        self.assertFalse(health["application_payload_is_billing_truth"])
        self.assertNotIn("offhost_backup_egress_bytes_30d", health)
        self.assertIsNone(health["offhost_backup_payload_bytes_30d"])
        self.assertEqual(health["budget_class"], "UNKNOWN")

    def test_weekly_full_precedes_same_day_delta(self) -> None:
        sunday = datetime(2026, 9, 6, 0, 30, tzinfo=UTC)
        (self.root / "local/factory_v1/observation_rdp/seed.bin").write_bytes(b"rdp-one")
        weekly = run_offhost_checkpoint(
            self.root,
            mode="weekly",
            config=self.config,
            runner=self.runner,
            now=sunday,
            deploy_git_sha="f" * 40,
        )
        self.assertEqual(weekly["terminal"], "WEEKLY_FULL_VERIFIED")
        backup_copies = [
            call[-1]
            for call in self.runner.calls
            if FakeRcloneRunner._subcommand(call) == "copyto" and "BACKUP_" in call[-1]
        ]
        self.assertEqual(len(backup_copies), 1)
        daily = run_offhost_checkpoint(
            self.root,
            mode="daily",
            config=self.config,
            runner=self.runner,
            now=sunday.replace(hour=0, minute=45),
            deploy_git_sha="f" * 40,
        )
        self.assertEqual(daily["terminal"], "NO_CHANGES_VERIFIED")
        backup_copies_after = [
            call[-1]
            for call in self.runner.calls
            if FakeRcloneRunner._subcommand(call) == "copyto" and "BACKUP_" in call[-1]
        ]
        delta_copies = [
            call[-1]
            for call in self.runner.calls
            if FakeRcloneRunner._subcommand(call) == "copyto" and "DELTA_" in call[-1]
        ]
        self.assertEqual(backup_copies_after, backup_copies)
        self.assertEqual(delta_copies, [])
        checkpoints = [
            Path(call[-1]).name
            for call in self.runner.calls
            if FakeRcloneRunner._subcommand(call) == "copyto"
            and "RECOVERY_CHECKPOINT_" in call[-1]
        ]
        self.assertEqual(len(checkpoints), 2)
        newest = newest_checkpoint_filename(checkpoints)
        self.assertEqual(newest, checkpoints[-1])
        local_checkpoint = (
            resolve_backup_sink(self.root, load_config_v1_1(self.root), {}) / newest
        )
        payload = validate_recovery_checkpoint(local_checkpoint)
        self.assertEqual(payload["checkpoint_terminal"], "NO_CHANGES_VERIFIED")

    def test_weekly_no_change_does_not_reupload_full(self) -> None:
        sunday = datetime(2026, 9, 6, 0, 30, tzinfo=UTC)
        run_offhost_checkpoint(
            self.root,
            mode="weekly",
            config=self.config,
            runner=self.runner,
            now=sunday,
        )
        later = run_offhost_checkpoint(
            self.root,
            mode="weekly",
            config=self.config,
            runner=self.runner,
            now=sunday.replace(minute=40),
        )
        self.assertEqual(later["terminal"], "FULL_COVERAGE_RECONFIRMED_NO_CHANGE")
        backup_copies = [
            call
            for call in self.runner.calls
            if FakeRcloneRunner._subcommand(call) == "copyto" and "BACKUP_" in call[-1]
        ]
        self.assertEqual(len(backup_copies), 1)

    def test_failed_copy_counts_attempted_payload(self) -> None:
        self.runner.fail_copy_count = 1
        with self.assertRaises(OffhostBackupError):
            run_offhost_checkpoint(
                self.root,
                mode="daily",
                config=self.config,
                runner=self.runner,
                now=datetime(2026, 9, 2, 0, 45, tzinfo=UTC),
            )
        ledger_path = self.root / "local/factory_v1/offhost_traffic_ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        attempted = sum(int(event["attempted_payload_bytes"]) for event in ledger["events"])
        self.assertGreater(attempted, 0)
        self.assertEqual(ledger["offhost_backup_payload_bytes_30d"], attempted)

    def test_weekly_fail_allows_daily_delta_from_previous_base(self) -> None:
        wednesday = datetime(2026, 9, 2, 0, 45, tzinfo=UTC)
        (self.root / "local/factory_v1/observation_rdp/seed.bin").write_bytes(b"before")
        first = run_offhost_checkpoint(
            self.root,
            mode="daily",
            config=self.config,
            runner=self.runner,
            now=wednesday,
        )
        self.assertEqual(first["terminal"], "WEEKLY_FULL_VERIFIED")
        (self.root / "local/factory_v1/observation_rdp/seed.bin").write_bytes(b"after-change")
        self.runner.fail_copy_count = 1
        sunday = datetime(2026, 9, 6, 0, 45, tzinfo=UTC)
        daily = run_offhost_checkpoint(
            self.root,
            mode="daily",
            config=self.config,
            runner=self.runner,
            now=sunday,
        )
        self.assertEqual(daily["terminal"], "DAILY_DELTA_VERIFIED")
        self.assertEqual(daily["weekly_full_state"], "DEGRADED")

    def test_nonempty_rdp_incremental_restore_proof(self) -> None:
        rdp = self.root / "local/factory_v1/observation_rdp/live.bin"
        rdp.write_bytes(b"epoch-1")
        wednesday = datetime(2026, 9, 2, 0, 45, tzinfo=UTC)
        first = run_offhost_checkpoint(
            self.root,
            mode="daily",
            config=self.config,
            runner=self.runner,
            now=wednesday,
        )
        rdp.write_bytes(b"epoch-2-nonempty")
        thursday = datetime(2026, 9, 3, 0, 45, tzinfo=UTC)
        second = run_offhost_checkpoint(
            self.root,
            mode="daily",
            config=self.config,
            runner=self.runner,
            now=thursday,
        )
        self.assertEqual(second["terminal"], "DAILY_DELTA_VERIFIED")
        isolated = Path(self.tmp.name) / "isolated-restore"
        objects = isolated / "objects"
        objects.mkdir(parents=True)
        dest = isolated / "dest"
        for remote, data in self.runner.payloads.items():
            (objects / Path(remote).name).write_bytes(data)
        decoy = objects / f"RECOVERY_CHECKPOINT_20200101T000000Z_{'a' * 64}.json"
        # older timestamp must not win
        decoy.write_text("{}", encoding="utf-8")
        names = [path.name for path in objects.iterdir()]
        newest = newest_checkpoint_filename(names)
        self.assertIsNotNone(newest)
        self.assertTrue(str(newest).startswith("RECOVERY_CHECKPOINT_20260903"))
        checkpoint_path = objects / newest
        restored = restore_from_recovery_checkpoint(
            checkpoint_path=checkpoint_path,
            objects_dir=objects,
            dest_root=dest,
        )
        self.assertEqual(
            restored["terminal"],
            "NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF_PASS",
        )
        self.assertEqual(
            restored["discovery"],
            "RECOVERY_CHECKPOINT_FILENAME_TIMESTAMP_THEN_CONTENT_HASH",
        )
        self.assertEqual(
            (dest / "local/factory_v1/observation_rdp/live.bin").read_bytes(),
            b"epoch-2-nonempty",
        )
        self.assertTrue(restored["sqlite_integrity"])
        checkpoint = validate_recovery_checkpoint(checkpoint_path)
        self.assertTrue(str(checkpoint["base_full"]["filename"]).startswith("BACKUP_"))
        self.assertEqual(len(checkpoint["ordered_deltas"]), 1)

    def test_retain_one_local_full_still_emits_daily_delta(self) -> None:
        sunday = datetime(2026, 9, 6, 0, 30, tzinfo=UTC)
        (self.root / "local/factory_v1/observation_rdp/seed.bin").write_bytes(b"week-base")
        weekly = run_offhost_checkpoint(
            self.root,
            mode="weekly",
            config=self.config,
            runner=self.runner,
            now=sunday,
        )
        self.assertEqual(weekly["terminal"], "WEEKLY_FULL_VERIFIED")
        loaded = load_config_v1_1(self.root)
        package_backup(self.root, config=loaded)
        (self.root / "local/factory_v1/observation_rdp/seed.bin").write_bytes(b"monday-growth")
        package_backup(self.root, config=loaded)
        monday = datetime(2026, 9, 7, 0, 45, tzinfo=UTC)
        daily = run_offhost_checkpoint(
            self.root,
            mode="daily",
            config=self.config,
            runner=self.runner,
            now=monday,
        )
        self.assertEqual(daily["terminal"], "DAILY_DELTA_VERIFIED")
        delta_copies = [
            call[-1]
            for call in self.runner.calls
            if FakeRcloneRunner._subcommand(call) == "copyto" and "DELTA_" in call[-1]
        ]
        self.assertEqual(len(delta_copies), 1)
        backup_copies = [
            call[-1]
            for call in self.runner.calls
            if FakeRcloneRunner._subcommand(call) == "copyto" and "BACKUP_" in call[-1]
        ]
        self.assertEqual(len(backup_copies), 1)

    def test_shared_lock_rejects_concurrent_writer(self) -> None:
        with backup_plane_lock(self.root):
            with self.assertRaises(RemoteOpsError):
                with backup_plane_lock(self.root, timeout_seconds=0.2):
                    pass


if __name__ == "__main__":
    unittest.main()
