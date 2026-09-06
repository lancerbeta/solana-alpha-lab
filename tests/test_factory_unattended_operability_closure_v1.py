"""Vertical proofs for FACTORY_UNATTENDED_OPERABILITY_CLOSURE_V1."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from solana_alpha_lab.factory.collector_operational_packet import (  # noqa: E402
    compose_health_classes,
)
from solana_alpha_lab.factory.collector_owner_pulse import (  # noqa: E402
    DAILY_PULSE_ON_CALENDAR,
    render_daily_owner_pulse,
)
from solana_alpha_lab.factory.external_heartbeat import (  # noqa: E402
    HEARTBEAT_ENV,
    HEARTBEAT_ON_CALENDAR,
    UNCONFIGURED,
    run_external_heartbeat,
)
from solana_alpha_lab.factory.hot90_activation import (  # noqa: E402
    STAGE_DURABILITY_CUTOVER,
    write_hot90_runtime_state,
)
from solana_alpha_lab.factory.hot90_archive import (  # noqa: E402
    list_closed_day_relative_paths,
    package_closed_day_archive,
)
from solana_alpha_lab.factory.hot90_closed_day_loop import (  # noqa: E402
    ARCHIVE_CATCH_UP_ON_CALENDAR,
    ARCHIVE_ON_CALENDAR,
    RECEIPTS_RELATIVE,
    STAGING_RELATIVE,
    archive_backlog,
    eligible_unverified_days,
    process_one_day,
    read_receipt,
    receipt_verified,
    run_closed_day_durability,
)
from solana_alpha_lab.factory.hot90_remote_verify import (  # noqa: E402
    REMOTE_CONTENT_SHA256_VERIFIED,
)
from solana_alpha_lab.factory.members_snapshot_delta import write_snapshot_unit  # noqa: E402
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.operability_watch import (  # noqa: E402
    WATCH_ON_CALENDAR,
    evaluate_operability,
)
from solana_alpha_lab.factory.remote_ops import RemoteOpsError, load_config_v1_1  # noqa: E402
from solana_alpha_lab.factory_semantic_operability import (  # noqa: E402
    load_semantic_projection,
    search_semantic_routes,
)

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def _member(entity_id: str) -> dict[str, object]:
    return {
        "schedule_sha256": "a" * 64,
        "activation_id": "ACT-1",
        "entity_id": entity_id,
        "membership_state": "INCLUDED",
        "event_time": "2026-09-01T00:05:00Z",
        "first_reliable_available_at": "2026-09-01T00:10:00Z",
        "field_values": [
            {
                "field_id": "F1",
                "value_kind": "STRING",
                "typed_value_or_null": "x",
                "state": "OBSERVED",
                "missing_reason": None,
            }
        ],
    }


class FakeRun:
    def __init__(self, code: int, stdout: str = "") -> None:
        self.returncode = code
        self.stdout = stdout
        self.stderr = ""


class FakeDrive:
    def __init__(self, *, fail_copy: bool = False, mismatch: bool = False, fail_hashsum: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.copy_count = 0
        self.fail_copy = fail_copy
        self.mismatch = mismatch
        self.fail_hashsum = fail_hashsum

    def runner(self, argv: list[str]) -> FakeRun:
        if "copyto" in argv:
            index = argv.index("copyto")
            src = Path(argv[index + 1])
            dest = argv[index + 2]
            if src.is_file():
                if self.fail_copy:
                    return FakeRun(1)
                self.objects[dest] = src.read_bytes()
                self.copy_count += 1
                return FakeRun(0)
            if self.mismatch:
                return FakeRun(1)
            payload = self.objects.get(argv[index + 1])
            if payload is not None:
                Path(dest).write_bytes(payload)
                return FakeRun(0)
            return FakeRun(1)
        if "hashsum" in argv:
            if self.fail_hashsum:
                return FakeRun(1)
            remote = argv[-1]
            payload = self.objects.get(remote)
            if payload is None:
                return FakeRun(1)
            digest = "0" * 64 if self.mismatch else hashlib.sha256(payload).hexdigest()
            return FakeRun(0, f"{digest} ARCHIVE.bin\n")
        return FakeRun(1)


def _ops_root(tmp: str) -> Path:
    root = Path(tmp)
    (root / "configs").mkdir()
    (root / "catalog" / "schemas").mkdir(parents=True)
    shutil.copy(
        ROOT / "configs/factory_remote_operations_v1_1.yaml",
        root / "configs/factory_remote_operations_v1_1.yaml",
    )
    shutil.copy(
        ROOT / "catalog/schemas/factory_remote_operations_v1_1.schema.json",
        root / "catalog/schemas/factory_remote_operations_v1_1.schema.json",
    )
    write_hot90_runtime_state(
        root,
        {
            "activation_stage": STAGE_DURABILITY_CUTOVER,
            "production_compaction_enabled": False,
            "production_eviction_enabled": False,
            "drive_writes_enabled": True,
        },
    )
    (root / "local/factory_v1/observation_rdp").mkdir(parents=True)
    return root


def _seed_day(rdp: Path, utc_day: str, entity: str) -> None:
    write_snapshot_unit(
        rdp,
        utc_day=utc_day,
        dataset_manifest_id=f"dataset-{utc_day}-{entity}",
        rows=[_member(entity)],
    )


class ClosedDayDurabilityLoopTests(unittest.TestCase):
    def test_vertical_archive_verify_idempotent_and_open_day_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _ops_root(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            closed = "20260905"
            _seed_day(rdp, closed, "MintA")
            _seed_day(rdp, "20260906", "MintOpen")
            source_before = {
                path.relative_to(rdp).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in rdp.rglob("*")
                if path.is_file()
            }
            first_paths = list_closed_day_relative_paths(rdp, closed)
            packed_a = package_closed_day_archive(
                rdp, utc_day=closed, relative_paths=first_paths, dest_dir=root / "tmp-a"
            )
            packed_b = package_closed_day_archive(
                rdp, utc_day=closed, relative_paths=first_paths, dest_dir=root / "tmp-b"
            )
            self.assertEqual(packed_a["sha256"], packed_b["sha256"])
            drive = FakeDrive()
            first = run_closed_day_durability(
                root, now=NOW, rclone_runner=drive.runner, allow_drive=True, max_days=3
            )
            self.assertEqual(first["processed"][0]["terminal"], REMOTE_CONTENT_SHA256_VERIFIED)
            self.assertTrue(first["processed"][0]["uploaded"])
            self.assertEqual(first["backlog_after"], 0)
            copies = drive.copy_count
            second = run_closed_day_durability(
                root, now=NOW, rclone_runner=drive.runner, allow_drive=True, max_days=3
            )
            self.assertTrue(second["processed"] == [] or second["processed"][0].get("idempotent"))
            self.assertEqual(drive.copy_count, copies)
            self.assertNotIn("20260906", eligible_unverified_days(root, now=NOW))
            receipt = read_receipt(root, closed)
            self.assertTrue(receipt_verified(receipt))
            fake = dict(receipt or {})
            fake["local_archive_sha256"] = "1" * 64
            self.assertFalse(receipt_verified(fake))
            after = {
                path.relative_to(rdp).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in rdp.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, source_before)
            self.assertEqual(list(drive.objects), list(drive.objects))

    def test_hash_mismatch_fail_closed_and_drive_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _ops_root(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            _seed_day(rdp, "20260905", "MintB")
            bad = FakeDrive(mismatch=True)
            failed = process_one_day(
                root, "20260905", now=NOW, rclone_runner=bad.runner, allow_drive=True
            )
            self.assertEqual(failed["terminal"], "HASH_MISMATCH")
            self.assertTrue((rdp / "datasets/members_snapshot_plus_delta/20260905/unit.json").is_file())
            self.assertEqual(len(bad.objects), 1)
            copies = bad.copy_count
            again = process_one_day(
                root, "20260905", now=NOW, rclone_runner=bad.runner, allow_drive=True
            )
            self.assertEqual(again["terminal"], "HASH_MISMATCH")
            self.assertTrue(again.get("overwrite_forbidden"))
            self.assertEqual(bad.copy_count, copies)
            _seed_day(rdp, "20260904", "MintC")
            down = FakeDrive(fail_copy=True)
            still_down = process_one_day(
                root, "20260904", now=NOW, rclone_runner=down.runner, allow_drive=True
            )
            self.assertEqual(still_down["terminal"], "DRIVE_WRITE_FAILED")
            self.assertFalse(receipt_verified(read_receipt(root, "20260904")))
            up = FakeDrive()
            recovered = process_one_day(
                root, "20260904", now=NOW, rclone_runner=up.runner, allow_drive=True
            )
            self.assertEqual(recovered["terminal"], REMOTE_CONTENT_SHA256_VERIFIED)

    def test_hash_mismatch_does_not_starve_younger_catch_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _ops_root(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            _seed_day(rdp, "20260904", "MintOld")
            _seed_day(rdp, "20260905", "MintNew")
            bad = FakeDrive(mismatch=True)
            failed = process_one_day(
                root, "20260904", now=NOW, rclone_runner=bad.runner, allow_drive=True
            )
            self.assertEqual(failed["terminal"], "HASH_MISMATCH")
            good = FakeDrive()
            result = run_closed_day_durability(
                root, now=NOW, rclone_runner=good.runner, allow_drive=True, max_days=1
            )
            self.assertEqual(result["processed"][0]["utc_day"], "20260905")
            self.assertEqual(result["processed"][0]["terminal"], REMOTE_CONTENT_SHA256_VERIFIED)
            self.assertEqual(read_receipt(root, "20260904")["terminal"], "HASH_MISMATCH")
            self.assertIn("20260904", archive_backlog(root, now=NOW)["stuck_hash_mismatch_days"])
            self.assertNotIn("20260904", eligible_unverified_days(root, now=NOW))

    def test_preexisting_remote_mismatch_does_not_copyto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _ops_root(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            _seed_day(rdp, "20260905", "MintP")
            from solana_alpha_lab.factory.offhost_backup import load_offhost_config

            paths = list_closed_day_relative_paths(rdp, "20260905")
            packed = package_closed_day_archive(
                rdp, utc_day="20260905", relative_paths=paths, dest_dir=root / "tmp-p"
            )
            offhost = load_offhost_config(root)
            assert offhost is not None
            remote = offhost.remote_object(Path(packed["path"]).name)
            drive = FakeDrive()
            drive.objects[remote] = b"not-the-archive"
            result = process_one_day(
                root, "20260905", now=NOW, rclone_runner=drive.runner, allow_drive=True
            )
            self.assertEqual(result["terminal"], "HASH_MISMATCH")
            self.assertTrue(result.get("overwrite_forbidden"))
            self.assertEqual(drive.copy_count, 0)
            self.assertEqual(drive.objects[remote], b"not-the-archive")

    def test_unreadable_native_hashsum_still_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _ops_root(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            _seed_day(rdp, "20260905", "MintQ")
            from solana_alpha_lab.factory.offhost_backup import load_offhost_config

            paths = list_closed_day_relative_paths(rdp, "20260905")
            packed = package_closed_day_archive(
                rdp, utc_day="20260905", relative_paths=paths, dest_dir=root / "tmp-q"
            )
            offhost = load_offhost_config(root)
            assert offhost is not None
            remote = offhost.remote_object(Path(packed["path"]).name)
            hashed = FakeDrive(fail_hashsum=True)
            hashed.objects[remote] = b"not-the-archive"
            hashed_result = process_one_day(
                root, "20260905", now=NOW, rclone_runner=hashed.runner, allow_drive=True
            )
            self.assertEqual(hashed_result["terminal"], "HASH_MISMATCH")
            self.assertTrue(hashed_result.get("overwrite_forbidden"))
            self.assertEqual(hashed.objects[remote], b"not-the-archive")
            self.assertEqual(hashed.copy_count, 0)

    def test_seven_day_backlog_oldest_first_catch_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _ops_root(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            days = [(NOW - timedelta(days=offset)).strftime("%Y%m%d") for offset in range(7, 0, -1)]
            for index, day in enumerate(days):
                _seed_day(rdp, day, f"Mint{index}")
            drive = FakeDrive()
            seen: list[str] = []
            for _ in range(3):
                result = run_closed_day_durability(
                    root, now=NOW, rclone_runner=drive.runner, allow_drive=True, max_days=3
                )
                seen.extend(item["utc_day"] for item in result["processed"])
            self.assertEqual(seen, days)
            self.assertEqual(archive_backlog(root, now=NOW)["backlog_days"], 0)
            receipts = list((root / RECEIPTS_RELATIVE).glob("*.json"))
            self.assertEqual(len(receipts), 7)
            zips = list((root / STAGING_RELATIVE).glob("ARCHIVE_*.zip"))
            self.assertEqual(len(zips), 1)

    def test_corrupt_member_unit_does_not_abort_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _ops_root(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            _seed_day(rdp, "20260903", "MintGood")
            _seed_day(rdp, "20260904", "MintBad")
            unit = rdp / "datasets/members_snapshot_plus_delta/20260904/unit.json"
            unit.write_text("{not-json", encoding="utf-8")
            days = eligible_unverified_days(root, now=NOW)
            self.assertIn("20260903", days)
            self.assertNotIn("20260904", days)

    def test_monotonic_budget_stops_before_second_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _ops_root(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            _seed_day(rdp, "20260904", "MintD")
            _seed_day(rdp, "20260905", "MintE")
            ticks = iter((0.0, 0.0, 901.0))
            drive = FakeDrive()
            result = run_closed_day_durability(
                root,
                now=NOW,
                rclone_runner=drive.runner,
                allow_drive=True,
                max_days=3,
                monotonic=lambda: next(ticks),
            )
            self.assertEqual(len(result["processed"]), 1)
            self.assertEqual(result["processed"][0]["utc_day"], "20260904")
            self.assertEqual(result["backlog_after"], 1)

    def test_watch_persist_false_does_not_write_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ObservationScheduleStore(root / "ops.sqlite")
            state_path = root / "local/factory_v1/operability_incident_state.json"
            try:
                evaluate_operability(
                    root=root,
                    store=store,
                    now=NOW,
                    unit_status={"factory-observation-schedule.timer": "inactive"},
                    emit=False,
                    persist=False,
                    environ={},
                )
                self.assertFalse(state_path.exists())
            finally:
                store.close()


class IncidentDailyHeartbeatUtcTests(unittest.TestCase):
    def test_incident_once_recovered_once_telegram_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ObservationScheduleStore(root / "ops.sqlite")
            units_bad = {"factory-observation-schedule.timer": "inactive"}
            units_ok = {"factory-observation-schedule.timer": "active"}
            t0 = NOW
            first = evaluate_operability(
                root=root,
                store=store,
                now=t0,
                unit_status=units_bad,
                emit=False,
                environ={},
            )
            try:
                self.assertEqual(first["messages"], [])
                later = evaluate_operability(
                    root=root,
                    store=store,
                    now=t0 + timedelta(seconds=901),
                    unit_status=units_bad,
                    emit=False,
                    environ={},
                )
                codes = {(item["kind"], item["code"]) for item in later["messages"]}
                self.assertIn(("INCIDENT", "REQUIRED_TIMER_FAILED"), codes)
                again = evaluate_operability(
                    root=root,
                    store=store,
                    now=t0 + timedelta(seconds=1800),
                    unit_status=units_bad,
                    emit=False,
                    environ={},
                )
                self.assertEqual(again["messages"], [])
                recovered = evaluate_operability(
                    root=root,
                    store=store,
                    now=t0 + timedelta(seconds=2000),
                    unit_status=units_ok,
                    emit=False,
                    environ={},
                )
                rec_codes = {(item["kind"], item["code"]) for item in recovered["messages"]}
                self.assertIn(("RECOVERED", "REQUIRED_TIMER_FAILED"), rec_codes)
            finally:
                store.close()

    def test_telegram_failure_keeps_pending_then_sends_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ObservationScheduleStore(root / "ops.sqlite")
            units_bad = {"factory-observation-schedule.timer": "inactive"}
            env = {
                "FACTORY_TELEGRAM_BOT_TOKEN": "pulse-token",
                "FACTORY_TELEGRAM_CHAT_ID": "42",
            }
            alert = {
                "alert": {
                    "token_env": "FACTORY_TELEGRAM_BOT_TOKEN",
                    "chat_id_env": "FACTORY_TELEGRAM_CHAT_ID",
                }
            }
            t0 = NOW

            def boom(_token: str, _chat: str, _text: str) -> None:
                raise RemoteOpsError("PULSE_TRANSPORT_FAILED")

            delivered: list[str] = []

            def ok(_token: str, _chat: str, text: str) -> None:
                delivered.append(text)

            try:
                evaluate_operability(
                    root=root,
                    store=store,
                    now=t0,
                    unit_status=units_bad,
                    emit=False,
                    environ={},
                )
                evaluate_operability(
                    root=root,
                    store=store,
                    now=t0 + timedelta(seconds=901),
                    unit_status=units_bad,
                    emit=False,
                    environ={},
                )
                failed = evaluate_operability(
                    root=root,
                    store=store,
                    now=t0 + timedelta(seconds=902),
                    unit_status=units_bad,
                    emit=True,
                    remote_config=alert,
                    environ=env,
                    transport=boom,
                )
                self.assertGreaterEqual(failed["pending_count"], 1)
                evaluate_operability(
                    root=root,
                    store=store,
                    now=t0 + timedelta(seconds=902),
                    unit_status=units_bad,
                    emit=True,
                    remote_config=alert,
                    environ=env,
                    transport=ok,
                )
                first = len(delivered)
                self.assertGreaterEqual(first, 1)
                evaluate_operability(
                    root=root,
                    store=store,
                    now=t0 + timedelta(seconds=903),
                    unit_status=units_bad,
                    emit=True,
                    remote_config=alert,
                    environ=env,
                    transport=ok,
                )
                self.assertEqual(len(delivered), first)
            finally:
                store.close()

    def test_daily_card_and_utc_literals(self) -> None:
        ok_packet = {
            "collector_verdict": "OK",
            "activation_state": "ACTIVE",
            "cohort_readiness_state": "COLLECTING",
            "health_classes": ["PROCESS_OK"],
            "filesystem_disk_used_pct": 8,
            "projected_97d_bytes": 1000,
            "projected_97d_status": "OK",
            "backup_age_seconds": 120,
            "mutable_backup_includes_full_observation_rdp": False,
            "immutable_archive_latest_verified_day": "20260905",
            "immutable_archive_backlog_days": 0,
        }
        text = render_daily_owner_pulse(ok_packet)
        self.assertIn("FACTORY / DAILY — OK", text)
        self.assertIn("OWNER_ACTION=NONE", text)
        self.assertIn("MESSAGE_TYPE=DAILY", text)
        degraded = dict(ok_packet)
        degraded["health_classes"] = ["PROCESS_OK", "IMMUTABLE_ARCHIVE_STALE"]
        degraded["collector_verdict"] = "DEGRADED"
        degraded["immutable_archive_backlog_days"] = 2
        action = render_daily_owner_pulse(degraded)
        self.assertIn("OWNER_ACTION=IMMUTABLE_ARCHIVE_STALE", action)
        self.assertEqual(action.count("OWNER_ACTION="), 1)
        timer = (ROOT / "configs/factory_remote_ops/factory-collector-owner-pulse.timer").read_text(
            encoding="utf-8"
        )
        self.assertIn(DAILY_PULSE_ON_CALENDAR, timer)
        docs = (ROOT / "docs/operator/FACTORY_UNATTENDED_OPERABILITY.md").read_text(encoding="utf-8")
        self.assertIn(DAILY_PULSE_ON_CALENDAR, docs)
        collector = (ROOT / "docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("OnCalendar=*-*-* 06:15:00 UTC", collector)
        archive_timer = (
            ROOT / "configs/factory_remote_ops/factory-hot90-closed-day-archive.timer"
        ).read_text(encoding="utf-8")
        for item in ARCHIVE_CATCH_UP_ON_CALENDAR:
            self.assertIn(item, archive_timer)
        self.assertEqual(ARCHIVE_ON_CALENDAR, "*-*-* 01:15:00 UTC")
        self.assertIn(
            "TimeoutStartSec=900",
            (ROOT / "configs/factory_remote_ops/factory-hot90-closed-day-archive.service").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual(WATCH_ON_CALENDAR, "*-*-* *:0/15:00 UTC")
        self.assertEqual(HEARTBEAT_ON_CALENDAR, "*-*-* *:0/5:00 UTC")

    def test_external_heartbeat_unconfigured_and_fake_transport(self) -> None:
        quiet = run_external_heartbeat(environ={})
        self.assertEqual(quiet["terminal"], UNCONFIGURED)
        self.assertEqual(quiet["network_calls"], 0)
        seen: list[str] = []

        def transport(url: str) -> int:
            seen.append(url)
            return 204

        sent = run_external_heartbeat(
            environ={HEARTBEAT_ENV: "https://example.invalid/hb"},
            transport=transport,
        )
        self.assertEqual(sent["terminal"], "HEARTBEAT_SENT")
        self.assertEqual(seen, ["https://example.invalid/hb"])
        self.assertFalse(sent["url_logged"])

    def test_month_horizon_bounded_staging_no_incident_spam(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _ops_root(tmp)
            rdp = root / "local/factory_v1/observation_rdp"
            drive = FakeDrive()
            clock = datetime(2026, 8, 1, 12, tzinfo=UTC)
            for offset in range(31):
                day = (clock + timedelta(days=offset)).strftime("%Y%m%d")
                _seed_day(rdp, day, f"MintM{offset}")
            end = datetime(2026, 9, 1, 12, tzinfo=UTC)
            remaining = 31
            while remaining:
                result = run_closed_day_durability(
                    root, now=end, rclone_runner=drive.runner, allow_drive=True, max_days=3
                )
                remaining = result["backlog_after"]
            self.assertEqual(len(list((root / STAGING_RELATIVE).glob("ARCHIVE_*.zip"))), 1)
            self.assertEqual(len(list((root / RECEIPTS_RELATIVE).glob("*.json"))), 31)
            store = ObservationScheduleStore(root / "ops.sqlite")
            units = {"factory-observation-schedule.timer": "active"}
            sink = root / "local/factory_v1_backup_sink"
            sink.mkdir(parents=True, exist_ok=True)
            bundle = sink / ("BACKUP_" + ("ab" * 32) + ".zip")
            bundle.write_bytes(b"backup")
            remote = load_config_v1_1(root)
            messages = 0
            try:
                for day in range(31):
                    clock = end + timedelta(days=day)
                    stamp = clock.timestamp()
                    os.utime(bundle, (stamp, stamp))
                    for path in rdp.rglob("*"):
                        if path.is_file():
                            os.utime(path, (stamp, stamp))
                    result = evaluate_operability(
                        root=root,
                        store=store,
                        now=clock,
                        unit_status=units,
                        emit=False,
                        observation_rdp=rdp,
                        remote_config=remote,
                        environ={"FACTORY_BACKUP_SINK": str(sink)},
                    )
                    messages += len(result["messages"])
                self.assertEqual(messages, 0)
            finally:
                store.close()

    def test_health_does_not_treat_open_jobs_as_incident(self) -> None:
        packet = {
            "activation_state": "ACTIVE",
            "health_classes": compose_health_classes(
                {
                    "activation_state": "ACTIVE",
                    "publication_jobs_open_count": 2,
                    "in_flight_indeterminate": 1,
                    "immutable_archive_backlog_days": 0,
                    "discovery_coverage_class": "UNKNOWN",
                    "backup_domain": "PARENT_INDEPENDENT_GIT_SIDE",
                    "backup_age_seconds": 60,
                    "last_backup_at": "2026-09-06T11:00:00Z",
                    "offhost_backup_state": "CURRENT",
                    "observation_rdp_last_publish_at": "2026-09-06T11:00:00Z",
                    "observed_at": "2026-09-06T12:00:00Z",
                }
            ),
        }
        from solana_alpha_lab.factory.operability_watch import classify_incidents

        found = classify_incidents(packet)
        self.assertNotIn("PUBLICATION_STUCK", found)
        timers = classify_incidents(
            packet,
            unit_status={"factory-hot90-closed-day-archive.timer": "inactive"},
        )
        self.assertIn("REQUIRED_TIMER_FAILED", timers)


class SemanticDiscoveryTests(unittest.TestCase):
    def test_owner_language_lands_on_remote_ops_route(self) -> None:
        import yaml

        projection = load_semantic_projection(ROOT)
        manifest = yaml.safe_load(
            (ROOT / "catalog/catalog_manifest.yaml").read_text(encoding="utf-8")
        )
        bindings = manifest.get("canonical_bindings") or {}
        assets = {
            "CONFIG-FACTORY-REMOTE-OPERATIONS-V1-1-001": {
                "asset_id": "CONFIG-FACTORY-REMOTE-OPERATIONS-V1-1-001"
            },
            "DOC-FACTORY-REMOTE-HOST-001": {"asset_id": "DOC-FACTORY-REMOTE-HOST-001"},
            "DOC-FACTORY-UNATTENDED-OPERABILITY-001": {
                "asset_id": "DOC-FACTORY-UNATTENDED-OPERABILITY-001"
            },
        }
        queries = [
            "бэкап VPS",
            "immutable archive Drive",
            "почему архив не загрузился",
            "Telegram алерт",
            "VPS недоступен",
            "host unreachable",
            "как восстановить Factory",
            "HOT90 runtime",
            "mutable backup",
        ]
        for query in queries:
            hits = search_semantic_routes(
                projection,
                query,
                assets=assets,
                bindings=bindings,
                limit=5,
            )
            assert isinstance(hits, list)
            self.assertEqual(hits[0]["semantic_route_id"], "SEM-REMOTE-OPS-RECOVERY", query)
        self.assertEqual(
            bindings.get("ACTIVE-FACTORY-REMOTE-OPERATIONS", {}).get("target_asset_id"),
            "CONFIG-FACTORY-REMOTE-OPERATIONS-V1-1-001",
        )


if __name__ == "__main__":
    unittest.main()
