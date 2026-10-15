"""Immutable publication, recovery clocks and reference closure on disposable roots."""

from __future__ import annotations

import json
import hashlib
import io
from contextlib import closing, redirect_stdout
import os
import subprocess
import sys
import sqlite3
import tempfile
import time
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from tests.test_factory_offhost_backup import FakeRcloneRunner, _seed_tree
from solana_alpha_lab.factory import offhost_backup as owner
from solana_alpha_lab.factory.remote_ops import backup_plane_lock


class I2OffhostCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = _seed_tree(Path(self.temporary.name) / "factory")
        repository = Path(__file__).resolve().parents[1]
        for relative in ("configs/observation_schedule_runtime_v1.yaml",
                         "catalog/schemas/observation_schedule_runtime_v1.schema.json"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((repository / relative).read_bytes())
        credentials = self.root / "rclone-fixture.conf"
        credentials.write_text("[fixture]\ntype = drive\n", encoding="utf-8")
        credentials.chmod(0o600)
        self.config = replace(owner.load_offhost_config(self.root), rclone_config_absolute=credentials)
        self.runner = FakeRcloneRunner()
        self.clock = datetime(2026, 10, 14, 0, 45, tzinfo=UTC)
        self.source = self.root / "local/factory_v1/observation_rdp/source.bin"
        self.source.write_bytes(b"capture-one")
        self.scheduled_processes = []
        self.native_stores = []

    def tearDown(self) -> None:
        for process in self.scheduled_processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
        for store in self.native_stores:
            store.close()
        self.temporary.cleanup()

    def run_checkpoint(self, **kwargs):
        return owner.run_offhost_checkpoint(self.root, mode="daily", config=self.config,
            runner=kwargs.pop("runner", self.runner), now=kwargs.pop("now", self.clock), **kwargs)

    def pending(self):
        return json.loads((self.root / self.config.pending_relative).read_text(encoding="utf-8"))["operation"]

    def test_retry_never_recaptures_even_after_live_source_changes(self) -> None:
        self.runner.fail_copy_count = 1
        with self.assertRaisesRegex(owner.OffhostBackupError, "OFFHOST_COPY_FAILED"):
            self.run_checkpoint()
        pending_bytes = (self.root / self.config.pending_relative).read_bytes()
        operation = self.pending()
        self.source.write_bytes(b"a completely different later market")
        with patch.object(owner, "backup_payload_snapshot", side_effect=AssertionError("recapture")):
            receipt = self.run_checkpoint(now=self.clock + timedelta(hours=25))
        self.assertEqual(receipt["checkpoint_filename"], operation["checkpoint"]["filename"])
        self.assertEqual(receipt["snapshot_data_as_of"], self.clock.isoformat().replace("+00:00", "Z"))
        self.assertFalse((self.root / self.config.pending_relative).exists())
        self.assertIn(operation["checkpoint"]["sha256"].encode(), pending_bytes)
        health = owner.offhost_health_snapshot(self.root, config=self.config, now=self.clock + timedelta(hours=25))
        self.assertEqual(health["offhost_backup_state"], "DEGRADED")
        self.assertEqual(health["offhost_backup_age_seconds"], 25 * 3600)

    def test_weekly_reconfirmed_base_discards_obsolete_deltas_after_a_b_a(self) -> None:
        first = self.run_checkpoint()
        self.source.write_bytes(b"state B")
        second = self.run_checkpoint(now=self.clock + timedelta(days=1))
        self.assertEqual(second["terminal"], "DAILY_DELTA_VERIFIED")
        self.source.write_bytes(b"capture-one")
        third = owner.run_offhost_checkpoint(self.root, mode="weekly", config=self.config,
            runner=self.runner, now=self.clock + timedelta(days=2))
        self.assertEqual(third["terminal"], "FULL_COVERAGE_RECONFIRMED_NO_CHANGE")
        chain = owner.read_chain_state(self.root, self.config)
        self.assertEqual(chain["ordered_deltas"], [])
        self.assertEqual(chain["base_full"]["filename"], first["source_backup_filename"])
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1, resolve_backup_sink
        sink = resolve_backup_sink(self.root, load_config_v1_1(self.root), {})
        proof = owner.verify_remote_checkpoint_restore(checkpoint_path=sink / third["checkpoint_filename"],
            isolated_root=Path(self.temporary.name) / "a-b-a-independent", config=self.config,
            runner=self.independent_transport)
        self.assertEqual(proof["restore"]["raw_inventory_sha256"], chain["tip_inventory_sha256"])
        self.assertEqual((Path(self.temporary.name) / "a-b-a-independent/restored/local/factory_v1/observation_rdp/source.bin").read_bytes(), b"capture-one")

    def test_timeout_after_remote_commit_reconciles_same_content(self) -> None:
        timed_out = False

        def transport(argv):
            nonlocal timed_out
            result = self.runner(argv)
            if self.runner._subcommand(argv) == "copyto" and not timed_out:
                timed_out = True
                raise TimeoutError("connection lost after remote commit")
            return result

        receipt = self.run_checkpoint(runner=transport)
        self.assertEqual(receipt["terminal"], "WEEKLY_FULL_VERIFIED")
        self.assertEqual(len([call for call in self.runner.calls if self.runner._subcommand(call) == "copyto"]), 2)
        self.assertEqual(receipt["verification"], "REMOTE_MD5_AND_SIZE_LOCAL_SHA256")

    def test_remote_checkpoint_before_pointer_interruption_resumes_exact_intent(self) -> None:
        with patch.object(owner, "write_chain_state", side_effect=RuntimeError("process interruption")):
            with self.assertRaises(RuntimeError):
                self.run_checkpoint()
        pending = self.pending()
        checkpoint = pending["checkpoint"]["filename"]
        self.assertIn(self.config.remote_object(checkpoint), self.runner.payloads)
        self.assertFalse((self.root / self.config.chain_relative).exists())
        before_copies = sum(self.runner._subcommand(call) == "copyto" for call in self.runner.calls)
        with patch.object(owner, "backup_payload_snapshot", side_effect=AssertionError("recapture")):
            receipt = self.run_checkpoint(now=self.clock + timedelta(hours=1))
        self.assertEqual(receipt["checkpoint_filename"], checkpoint)
        self.assertEqual(sum(self.runner._subcommand(call) == "copyto" for call in self.runner.calls), before_copies)

    def test_pointer_before_receipt_interruption_keeps_recovery_intent(self) -> None:
        with patch.object(owner, "write_offhost_receipt", side_effect=RuntimeError("interruption")):
            with self.assertRaises(RuntimeError):
                self.run_checkpoint()
        pending = self.pending()
        self.assertTrue((self.root / self.config.chain_relative).exists())
        with patch.object(owner, "backup_payload_snapshot", side_effect=AssertionError("recapture")):
            receipt = self.run_checkpoint()
        self.assertEqual(receipt["checkpoint_filename"], pending["checkpoint"]["filename"])

    def test_fresh_process_finishes_remote_commit_without_recapture(self) -> None:
        transport_dir = Path(self.temporary.name) / "independent-remote"
        transport_dir.mkdir()
        program = r'''
import hashlib, json, os, shutil, subprocess, sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from solana_alpha_lab.factory import offhost_backup as owner
root, remote, phase = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
config = replace(owner.load_offhost_config(root), rclone_config_absolute=root/'rclone-fixture.conf')
def runner(argv):
    command = argv[3]
    target = remote / Path(argv[-1]).name
    if command == 'copyto':
        shutil.copyfile(Path(argv[-2]), target)
        return subprocess.CompletedProcess(argv, 0, '', '')
    if not target.is_file():
        return subprocess.CompletedProcess(argv, 1, '[]', 'object not found')
    if command == 'lsjson':
        return subprocess.CompletedProcess(argv, 0, json.dumps([{'Path':target.name,'Size':target.stat().st_size}]), '')
    if command == 'hashsum':
        digest = hashlib.md5(target.read_bytes(), usedforsecurity=False).hexdigest()
        return subprocess.CompletedProcess(argv, 0, digest+'  '+target.name+'\n', '')
    raise AssertionError(command)
if phase == 'interrupt':
    owner.write_chain_state = lambda *args, **kwargs: os._exit(23)
else:
    def forbidden_capture(*args, **kwargs):
        raise AssertionError('fresh process recaptured pending operation')
    owner.backup_payload_snapshot = forbidden_capture
receipt = owner.run_offhost_checkpoint(root, mode='daily', config=config, runner=runner,
    now=datetime(2026,10,15,0,45,tzinfo=UTC))
print(json.dumps(receipt))
'''
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        def execute(phase):
            output = self.root / (phase + ".process-output.txt")
            with output.open("w", encoding="utf-8") as stream:
                result = subprocess.run([sys.executable, "-B", "-c", program, str(self.root),
                    str(transport_dir), phase], stdout=stream, stderr=subprocess.STDOUT,
                    text=True, env=env, timeout=30)
            result.stdout = output.read_text(encoding="utf-8")
            result.stderr = result.stdout
            return result
        first = execute("interrupt")
        self.assertEqual(first.returncode, 23, first.stderr)
        checkpoint = self.pending()["checkpoint"]["filename"]
        self.source.write_bytes(b"changed after process death")
        before = {path.name: path.read_bytes() for path in transport_dir.iterdir()}
        second = execute("resume")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)["checkpoint_filename"], checkpoint)
        self.assertEqual({path.name: path.read_bytes() for path in transport_dir.iterdir()}, before)

    def test_failure_keeps_last_good_and_exposes_latest_attempt(self) -> None:
        first = self.run_checkpoint()
        self.source.write_bytes(b"new source")
        self.runner.fail_copy_count = 1
        with self.assertRaises(owner.OffhostBackupError):
            self.run_checkpoint(now=self.clock + timedelta(hours=1))
        last_good = owner.read_offhost_receipt(self.root, self.config)
        self.assertEqual(last_good["checkpoint_filename"], first["checkpoint_filename"])
        health = owner.offhost_health_snapshot(self.root, config=self.config, now=self.clock + timedelta(hours=1))
        self.assertEqual(health["offhost_backup_state"], "CURRENT")
        self.assertEqual(health["offhost_last_attempt_terminal"], "COPY_FAILED")
        self.assertEqual(health["offhost_backup_age_seconds"], 3600)

    def test_corrupt_existing_chain_is_not_bootstrap(self) -> None:
        state = self.root / self.config.chain_relative
        state.write_text("{", encoding="utf-8")
        with patch.object(owner, "backup_payload_snapshot", side_effect=AssertionError("capture")):
            with self.assertRaisesRegex(owner.OffhostBackupError, "OFFHOST_CHAIN_STATE_CORRUPT"):
                self.run_checkpoint()
        self.assertEqual(state.read_text(encoding="utf-8"), "{")
        self.assertEqual(self.runner.calls, [])

    def test_existing_missing_null_base_or_tip_refuses_without_recapture_or_network(self) -> None:
        self.run_checkpoint()
        original = owner.read_chain_state(self.root, self.config)
        state = self.root / self.config.chain_relative
        malformed = [{"ordered_deltas": []}]
        for field in ("base_full", "tip_entries", "tip_inventory_sha256", "last_weekly_date"):
            candidate = dict(original)
            candidate.pop(field)
            malformed.append(candidate)
        malformed.append({**original, "base_full": None})
        for candidate in malformed:
            with self.subTest(keys=sorted(candidate), null_base=candidate.get("base_full") is None):
                owner._atomic_write_json(state, candidate)
                before = state.read_bytes()
                self.runner.calls.clear()
                with patch.object(owner, "backup_payload_snapshot", side_effect=AssertionError("recapture")):
                    with self.assertRaisesRegex(owner.OffhostBackupError, "OFFHOST_CHAIN_STATE_CORRUPT"):
                        self.run_checkpoint(now=self.clock + timedelta(days=1))
                self.assertEqual(state.read_bytes(), before)
                self.assertEqual(self.runner.calls, [])

    def test_persisted_legacy_proven_chain_without_new_pointer_fields_is_accepted(self) -> None:
        self.run_checkpoint()
        chain = owner.read_chain_state(self.root, self.config)
        chain.pop("last_checkpoint")
        chain.pop("last_good_receipt")
        owner.write_chain_state(self.root, self.config, chain)
        self.assertEqual(owner.read_chain_state(self.root, self.config), chain)

    def test_corrupt_pending_is_not_discarded_or_recaptured(self) -> None:
        pending = self.root / self.config.pending_relative
        pending.write_text("{}", encoding="utf-8")
        with patch.object(owner, "backup_payload_snapshot", side_effect=AssertionError("capture")):
            with self.assertRaisesRegex(owner.OffhostBackupError, "OFFHOST_PENDING_OPERATION_CORRUPT"):
                self.run_checkpoint()
        self.assertEqual(pending.read_text(encoding="utf-8"), "{}")

    def test_backup_plane_collision_defers_without_new_work(self) -> None:
        with backup_plane_lock(self.root):
            receipt = self.run_checkpoint()
        self.assertEqual(receipt, {"terminal": "DEFERRED", "reason": "WRITER_BUSY"})
        self.assertEqual(self.runner.calls, [])
        self.assertFalse((self.root / self.config.pending_relative).exists())

    def scheduled_process(self, remote: Path, *, mode: str = "daily", budget: float = 3,
                          hold_upload: bool = False, forbid_capture: bool = False):
        """Actual CLI main in another process; only transport and test time scale differ."""
        remote.mkdir(exist_ok=True)
        program = r'''
import hashlib, json, shutil, subprocess, sys, time
from dataclasses import replace
from pathlib import Path
from scripts import factory_offhost_backup_copy as cli
from solana_alpha_lab.factory import offhost_backup as owner
root, remote = Path(sys.argv[1]), Path(sys.argv[2])
mode, budget, hold, forbid = sys.argv[3], float(sys.argv[4]), sys.argv[5]=='1', sys.argv[6]=='1'
owner.SCHEDULED_BUSY_RETRY_BUDGET_SECONDS = budget
owner.SCHEDULED_BUSY_RETRY_INTERVAL_SECONDS = .05
load = owner.load_offhost_config
owner.load_offhost_config = lambda root: replace(load(root), rclone_config_absolute=root/'rclone-fixture.conf')
def event(kind, **values):
    with (remote/(mode+'.events')).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'kind':kind, **values})+'\n')
original = owner.run_offhost_checkpoint
def checkpoint(*args, **kwargs):
    result = original(*args, **kwargs)
    event('attempt', terminal=result['terminal'])
    return result
owner.run_offhost_checkpoint = checkpoint
capture = owner.backup_payload_snapshot
def snapshot(*args, **kwargs):
    event('capture')
    if forbid:
        raise AssertionError('scheduled retry recaptured immutable pending')
    return capture(*args, **kwargs)
owner.backup_payload_snapshot = snapshot
def runner(argv):
    command = argv[3]
    target = remote/Path(argv[-1]).name
    if command == 'copyto':
        if hold and not (remote/'upload-held').exists():
            (remote/'upload-held').write_text('held')
            deadline = time.monotonic()+15
            while not (remote/'release-upload').exists():
                if time.monotonic()>deadline:
                    raise AssertionError('fixture upload release not received')
                time.sleep(.02)
        shutil.copyfile(argv[-2],target)
        event('copy', filename=target.name)
        return subprocess.CompletedProcess(argv,0,'','')
    if not target.is_file():
        return subprocess.CompletedProcess(argv,1,'[]','object not found')
    if command == 'lsjson':
        return subprocess.CompletedProcess(argv,0,json.dumps([{'Path':target.name,'Size':target.stat().st_size}]),'')
    if command == 'hashsum':
        return subprocess.CompletedProcess(argv,0,hashlib.md5(target.read_bytes(),usedforsecurity=False).hexdigest()+'  '+target.name+'\n','')
    raise AssertionError(command)
owner.default_rclone_runner = runner
cli._git_sha = lambda root: 'a'*40
sys.argv = ['factory_offhost_backup_copy.py','--root',str(root),'--mode',mode]
raise SystemExit(cli.main())
'''
        env = dict(os.environ)
        repository = Path(__file__).resolve().parents[1]
        env["PYTHONPATH"] = os.pathsep.join((str(repository), str(repository / "src")))
        output = self.root / (mode + ".scheduled-output.txt")
        stream = output.open("w", encoding="utf-8")
        process = subprocess.Popen([sys.executable, "-B", "-c", program, str(self.root), str(remote),
            mode, str(budget), str(int(hold_upload)), str(int(forbid_capture))],
            stdout=stream, stderr=subprocess.STDOUT, env=env)
        stream.close()
        self.scheduled_processes.append(process)
        return process, output

    def wait_scheduled_event(self, remote: Path, *, mode: str = "daily", terminal: str = "DEFERRED"):
        deadline = time.monotonic() + 10
        path = remote / (mode + ".events")
        while time.monotonic() < deadline:
            events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            if any(event.get("terminal") == terminal for event in events):
                return events
            time.sleep(.02)
        self.fail("scheduled caller did not reach native contention")

    def test_scheduled_caller_automatically_finishes_after_native_lease_release(self) -> None:
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        path = self.root / "local/factory_v1/observation_schedule_state.sqlite"
        path.unlink()
        store = ObservationScheduleStore(path)
        self.native_stores.append(store)
        token = store.acquire_lease("real-fixture-collector")
        self.assertIsNotNone(token)
        with closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)) as independent:
            before = independent.execute("SELECT lease_token FROM scheduler_leases").fetchone()[0]
        self.assertEqual(before, token)
        remote = Path(self.temporary.name) / "scheduled-remote"
        process, output = self.scheduled_process(remote)
        self.wait_scheduled_event(remote)
        time.sleep(.1)
        store.release_lease(token)
        code = process.wait(timeout=15)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(code, 0, result)
        self.assertIn(result["terminal"], owner.CHECKPOINT_TERMINALS)
        with closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)) as independent:
            self.assertEqual(independent.execute("SELECT COUNT(*) FROM scheduler_leases").fetchone()[0], 0)
        receipt = json.loads((self.root / self.config.receipt_relative).read_text())
        checkpoint = remote / receipt["checkpoint_filename"]
        self.assertEqual(hashlib.sha256(checkpoint.read_bytes()).hexdigest(), receipt["checkpoint_sha256"])
        self.assertFalse((self.root / self.config.pending_relative).exists())

    def test_scheduled_backup_lock_retry_resumes_exact_pending_without_capture(self) -> None:
        self.runner.fail_copy_count = 1
        with self.assertRaises(owner.OffhostBackupError):
            self.run_checkpoint()
        pending_path = self.root / self.config.pending_relative
        pending_bytes = pending_path.read_bytes()
        operation = self.pending()
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1, resolve_backup_sink
        sink = resolve_backup_sink(self.root, load_config_v1_1(self.root), {})
        expected = {item["filename"]: (sink / item["filename"]).read_bytes()
                    for item in [*operation["objects"], operation["checkpoint"]]}
        remote = Path(self.temporary.name) / "locked-pending-remote"
        with backup_plane_lock(self.root):
            process, output = self.scheduled_process(remote, forbid_capture=True)
            self.wait_scheduled_event(remote)
            self.source.write_bytes(b"later source must not replace immutable pending")
            time.sleep(.1)
            self.assertEqual(pending_path.read_bytes(), pending_bytes)
            self.assertFalse(any(remote.glob("RECOVERY_CHECKPOINT*")))
        self.assertEqual(process.wait(timeout=15), 0, output.read_text())
        result = json.loads(output.read_text())
        self.assertEqual(result["checkpoint_filename"], operation["checkpoint"]["filename"])
        self.assertEqual(result["snapshot_data_as_of"], operation["snapshot_data_as_of"])
        self.assertEqual({name: (remote / name).read_bytes() for name in expected}, expected)
        self.assertFalse(pending_path.exists())
        events = [json.loads(line) for line in (remote / "daily.events").read_text().splitlines()]
        self.assertFalse(any(event["kind"] == "capture" for event in events))

    def wait_upload(self, remote: Path) -> None:
        deadline = time.monotonic() + 10
        while not (remote / "upload-held").exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue((remote / "upload-held").exists(), "weekly never held real backup lock")

    def test_weekly_daily_scheduled_overlap_coalesces_one_capture_and_publication(self) -> None:
        remote = Path(self.temporary.name) / "overlap-remote"
        weekly, weekly_output = self.scheduled_process(remote, mode="weekly", hold_upload=True)
        self.wait_upload(remote)
        pending = self.pending()
        daily, daily_output = self.scheduled_process(remote)
        self.wait_scheduled_event(remote)
        (remote / "release-upload").write_text("release")
        self.assertEqual(weekly.wait(timeout=15), 0, weekly_output.read_text())
        self.assertEqual(daily.wait(timeout=15), 0, daily_output.read_text())
        w = json.loads(weekly_output.read_text())
        d = json.loads(daily_output.read_text())
        self.assertTrue(d["scheduled_coalesced"])
        self.assertEqual(d["checkpoint_filename"], w["checkpoint_filename"])
        self.assertEqual(d["snapshot_data_as_of"], pending["snapshot_data_as_of"])
        self.assertNotIn("maintenance", d)
        self.assertEqual(len(list(remote.glob("RECOVERY_CHECKPOINT_*.json"))), 1)
        self.assertEqual(len(list(remote.glob("BACKUP_*.zip"))), 1)
        daily_events = [json.loads(line) for line in (remote / "daily.events").read_text().splitlines()]
        self.assertFalse(any(event["kind"] in {"capture", "copy"} for event in daily_events))
        receipt = json.loads((self.root / self.config.receipt_relative).read_text())
        self.assertEqual(receipt["checkpoint_sha256"], hashlib.sha256(
            (remote / w["checkpoint_filename"]).read_bytes()).hexdigest())
        import zipfile
        with zipfile.ZipFile(next(remote.glob("BACKUP_*.zip"))) as archive:
            self.assertEqual(archive.read("local/factory_v1/observation_rdp/source.bin"), b"capture-one")

    def test_exhausted_scheduled_wait_is_incident_then_active_owner_success_resolves_it(self) -> None:
        first = self.run_checkpoint()
        first_bytes = (self.root / self.config.receipt_relative).read_bytes()
        self.source.write_bytes(b"weekly source state two")
        remote = Path(self.temporary.name) / "exhausted-remote"
        weekly, weekly_output = self.scheduled_process(remote, mode="weekly", hold_upload=True)
        self.wait_upload(remote)
        pending_bytes = (self.root / self.config.pending_relative).read_bytes()
        pending = self.pending()
        daily, daily_output = self.scheduled_process(remote, budget=.2)
        self.wait_scheduled_event(remote)
        self.assertEqual(daily.wait(timeout=10), 2, daily_output.read_text())
        failure = json.loads(daily_output.read_text())
        self.assertEqual(failure["terminal"], "COPY_FAILED")
        self.assertEqual(failure["failure_code"], "OFFHOST_BUSY_RETRY_EXHAUSTED")
        self.assertEqual(failure["resume"]["action"], "RETRY_SAME_PENDING_OPERATION")
        self.assertEqual(failure["resume"]["argv"][-2:], ["--mode", "daily"])
        self.assertEqual(failure["checkpoint_filename"], pending["checkpoint"]["filename"])
        self.assertEqual(failure["resume"]["pending_operation_sha256"], hashlib.sha256(
            owner._checkpoint_canonical(pending)).hexdigest())
        self.assertEqual((self.root / self.config.receipt_relative).read_bytes(), first_bytes)
        self.assertEqual((self.root / self.config.pending_relative).read_bytes(), pending_bytes)
        self.assertEqual(owner.read_offhost_attempt(self.root, self.config)["failure_code"],
            "OFFHOST_BUSY_RETRY_EXHAUSTED")
        self.assertEqual(owner.read_offhost_receipt(self.root, self.config)["checkpoint_filename"],
            first["checkpoint_filename"])
        (remote / "release-upload").write_text("release")
        self.assertEqual(weekly.wait(timeout=15), 0, weekly_output.read_text())
        last = owner.read_offhost_attempt(self.root, self.config)
        self.assertEqual(last["terminal"], "WEEKLY_FULL_VERIFIED")
        self.assertEqual(last["checkpoint_filename"], pending["checkpoint"]["filename"])
        self.assertFalse((self.root / self.config.pending_relative).exists())

    def test_default_busy_budget_covers_110_minute_weekly_without_changing_24h_age(self) -> None:
        # Real retry policy, virtual elapsed time; no tiny-store timing claim.
        elapsed = [0.0]
        def sleep(seconds):
            elapsed[0] += seconds
        def attempt(*args, **kwargs):
            if elapsed[0] < 110 * 60:
                return {"terminal": "DEFERRED", "reason": "WRITER_BUSY"}
            return {"terminal": "WEEKLY_FULL_VERIFIED", "snapshot_data_as_of": "2026-10-14T00:30:00Z"}
        with patch.object(owner, "run_offhost_checkpoint", side_effect=attempt):
            result = owner.run_scheduled_offhost_checkpoint(self.root, mode="daily", config=self.config,
                now=self.clock, monotonic_clock=lambda: elapsed[0], sleeper=sleep)
        self.assertEqual(result["scheduled_retry"]["busy_wait_seconds"], 110 * 60)
        self.assertEqual(result["scheduled_retry"]["busy_retry_budget_seconds"], 120 * 60)
        self.assertEqual(self.config.freshness_current_max_seconds, 86400)
        self.assertEqual(result["snapshot_data_as_of"], "2026-10-14T00:30:00Z")

    def test_default_long_busy_exhausts_after_120_minutes_without_capture_or_last_good_change(self) -> None:
        first = self.run_checkpoint()
        before = (self.root / self.config.receipt_relative).read_bytes()
        elapsed = [0.0]
        def sleep(seconds):
            elapsed[0] += seconds
        with backup_plane_lock(self.root), patch.object(owner, "backup_payload_snapshot",
                side_effect=AssertionError("busy capture")):
            result = owner.run_scheduled_offhost_checkpoint(self.root, mode="daily", config=self.config,
                runner=self.runner, monotonic_clock=lambda: elapsed[0], sleeper=sleep,
                wall_clock=lambda: self.clock + timedelta(seconds=elapsed[0]))
        self.assertEqual(result["failure_code"], "OFFHOST_BUSY_RETRY_EXHAUSTED")
        self.assertEqual(result["busy_wait_seconds"], 120 * 60)
        self.assertEqual(result["deferred_attempts"], 241)
        self.assertEqual(result["resume"]["action"], "RETRY_SCHEDULED_CHECKPOINT")
        self.assertIsNone(result["resume"]["pending_operation_sha256"])
        self.assertEqual((self.root / self.config.receipt_relative).read_bytes(), before)
        self.assertEqual(owner.read_offhost_receipt(self.root, self.config)["checkpoint_filename"],
                         first["checkpoint_filename"])

    def test_coalescing_refuses_stale_future_or_corrupt_published_bytes(self) -> None:
        first = self.run_checkpoint()
        for observed in (self.clock + timedelta(hours=25), self.clock - timedelta(seconds=1)):
            with self.subTest(observed=observed), patch.object(owner, "backup_payload_snapshot",
                    side_effect=AssertionError("ordinary capture required")):
                with self.assertRaisesRegex(AssertionError, "ordinary capture required"):
                    self.run_checkpoint(now=observed, scheduled_requested_at=self.clock - timedelta(minutes=1))
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1, resolve_backup_sink
        sink = resolve_backup_sink(self.root, load_config_v1_1(self.root), {})
        (sink / first["source_backup_filename"]).write_bytes(b"corrupt published full")
        before = len(self.runner.calls)
        with patch.object(owner, "backup_payload_snapshot", side_effect=AssertionError("recapture")):
            with self.assertRaisesRegex(owner.OffhostBackupError, "OFFHOST_COALESCED_CHECKPOINT_INTEGRITY_FAILED"):
                self.run_checkpoint(scheduled_requested_at=self.clock - timedelta(minutes=1))
        self.assertEqual(len(self.runner.calls), before)

    def test_exact_checkpoint_success_resolves_incident_persisted_after_commit(self) -> None:
        receipt = self.run_checkpoint()
        incident = {"terminal": "COPY_FAILED", "failure_code": "OFFHOST_BUSY_RETRY_EXHAUSTED",
                    "failed_at": owner._stamp(self.clock + timedelta(seconds=2)),
                    "checkpoint_filename": receipt["checkpoint_filename"]}
        # Models incident IO delayed after its final lock-busy observation.
        owner._atomic_write_json(owner._scheduled_incident_path(self.root, self.config, "daily"), incident)
        self.assertEqual(owner.read_offhost_attempt(self.root, self.config)["terminal"], "WEEKLY_FULL_VERIFIED")

    def test_same_size_remote_corruption_is_not_accepted(self) -> None:
        self.runner.fail_copy_count = 1
        with self.assertRaises(owner.OffhostBackupError):
            self.run_checkpoint()
        operation = self.pending()
        artifact = operation["objects"][0]
        remote = self.config.remote_object(artifact["filename"])
        self.runner.objects[remote] = artifact["bytes"]
        self.runner.payloads[remote] = b"x" * artifact["bytes"]
        before = len(self.runner.calls)
        with self.assertRaisesRegex(owner.OffhostBackupError, "OFFHOST_REMOTE_IDENTITY_CONFLICT"):
            self.run_checkpoint()
        self.assertFalse(any(self.runner._subcommand(call) == "copyto" for call in self.runner.calls[before:]))

    def test_actual_completion_clocks_and_unchanged_24h_data_age(self) -> None:
        for minutes in (20, 110):
            with self.subTest(minutes=minutes):
                clocks = [self.clock]
                advanced = False
                transport = self.runner

                def slow(argv):
                    nonlocal advanced
                    result = transport(argv)
                    if transport._subcommand(argv) == "copyto" and not advanced:
                        advanced = True
                        clocks[0] += timedelta(minutes=minutes)
                    return result

                # Each subcase uses the same source, a distinct observation date.
                self.clock += timedelta(days=1)
                clocks[0] = self.clock
                receipt = self.run_checkpoint(runner=slow, wall_clock=lambda: clocks[0])
                self.assertEqual(receipt["snapshot_data_as_of"], self.clock.isoformat().replace("+00:00", "Z"))
                self.assertEqual(receipt["verified_at"], (self.clock + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z"))
                self.assertEqual(receipt["uploaded_at"], receipt["verified_at"])
                health = owner.offhost_health_snapshot(self.root, config=self.config, now=self.clock + timedelta(hours=24, seconds=1))
                self.assertEqual(health["offhost_backup_state"], "DEGRADED")
                self.assertEqual(health["offhost_current_max_age_seconds"], 24 * 3600)

    def test_future_and_invalid_snapshot_clocks_never_look_current(self) -> None:
        for value in ("not-a-date", "2027-01-01T00:00:00Z"):
            owner.write_offhost_receipt(self.root, self.config, {
                "terminal": "WEEKLY_FULL_VERIFIED", "clock_semantics": "SNAPSHOT_DATA_AGE_V2",
                "snapshot_data_as_of": value, "verified_at": self.clock.isoformat(),
            })
            health = owner.offhost_health_snapshot(self.root, config=self.config, now=self.clock)
            self.assertIsNone(health["offhost_backup_age_seconds"])
            self.assertEqual(health["offhost_backup_state"], "DEGRADED")

    def test_legacy_receipt_has_explicit_start_clock_compatibility(self) -> None:
        owner.write_offhost_receipt(self.root, self.config, {
            "terminal": "COPIED_VERIFIED", "verified_at": self.clock.isoformat(),
        })
        health = owner.offhost_health_snapshot(self.root, config=self.config, now=self.clock)
        self.assertEqual(health["offhost_clock_semantics"], "LEGACY_START_CLOCK_LOWER_BOUND")
        self.assertEqual(health["offhost_backup_age_seconds"], 0)

    def test_prune_union_retained_science_and_pending_refs(self) -> None:
        full, delta, pending, pin, orphan = [prefix + str(index) * 64 + ".zip"
            for index, prefix in enumerate(("BACKUP_", "DELTA_", "BACKUP_", "BACKUP_", "BACKUP_"), 1)]
        plan = owner.plan_backup_prune([full, delta, pending, pin, orphan],
            [{"base_full": {"filename": full}, "ordered_deltas": [{"filename": delta}]}],
            scientific_pins=[pin], pending_operations=[{"objects": [{"filename": pending}]}])
        self.assertEqual(plan["removable"], [orphan])
        self.assertEqual(plan["missing_references"], [])
        self.assertFalse(plan["remote_delete_enabled"])

    def independent_transport(self, argv):
        command = self.runner._subcommand(argv)
        if command == "copyto" and argv[-2].startswith(self.config.remote_prefix):
            self.runner.calls.append(list(argv))
            payload = self.runner.payloads.get(argv[-2])
            if payload is None:
                return subprocess.CompletedProcess(argv, 1, "", "object not found")
            Path(argv[-1]).write_bytes(payload)
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command == "deletefile":
            self.runner.calls.append(list(argv))
            self.runner.payloads.pop(argv[-1], None)
            self.runner.objects.pop(argv[-1], None)
            return subprocess.CompletedProcess(argv, 0, "", "")
        return self.runner(argv)

    def test_prune_requires_exact_approval_and_independent_restore_then_keeps_pins(self) -> None:
        receipt = self.run_checkpoint()
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1, resolve_backup_sink
        sink = resolve_backup_sink(self.root, load_config_v1_1(self.root), {})
        proof_root = Path(self.temporary.name) / "independent-proof"
        proof = owner.verify_remote_checkpoint_restore(checkpoint_path=sink / receipt["checkpoint_filename"],
            isolated_root=proof_root, config=self.config,
            runner=self.independent_transport)
        artifact = proof_root / ".remote-restore-proof.json"
        self.assertEqual(proof["terminal"], "REMOTE_CHECKPOINT_RESTORE_VERIFIED")
        self.assertTrue(proof["restore"]["sqlite_integrity"])
        orphan_payloads = [b"obsolete generation", b"scientific frozen archive"]
        names = []
        for data in orphan_payloads:
            name = "BACKUP_" + hashlib.sha256(data).hexdigest() + ".zip"
            names.append(name)
            remote = self.config.remote_object(name)
            self.runner.objects[remote] = len(data)
            self.runner.payloads[remote] = data
        chain = owner.read_chain_state(self.root, self.config)
        chain["scientific_pins"] = [names[1]]
        owner.write_chain_state(self.root, self.config, chain)
        objects = [Path(remote).name for remote in self.runner.objects]
        plan = owner.plan_checkpoint_prune(self.root, objects=objects, config=self.config,
            restore_proof_artifacts=[artifact])
        self.assertEqual(plan["removable"], [names[0]])
        disabled = owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
            runner=self.independent_transport)
        self.assertEqual(disabled["status"], "DISABLED")
        with self.assertRaisesRegex(owner.OffhostBackupError, "EXACT_PLAN_APPROVAL"):
            owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
                runner=self.independent_transport, remote_delete_authorized=True,
                approved_plan_sha256="0" * 64, restore_proofs=[proof])
        with self.assertRaisesRegex(owner.OffhostBackupError, "RESTORE_PROOF_ARTIFACT_CONFLICT"):
            owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
                runner=self.independent_transport, remote_delete_authorized=True,
                approved_plan_sha256=plan["plan_sha256"])
        result = owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
            runner=self.independent_transport, remote_delete_authorized=True,
            approved_plan_sha256=plan["plan_sha256"], restore_proofs=[proof],
            restore_proof_artifacts=[artifact])
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["deleted"], [names[0]])
        self.assertIn(self.config.remote_object(names[1]), self.runner.objects)
        self.assertIn(self.config.remote_object(receipt["checkpoint_filename"]), self.runner.objects)
        repeated = owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
            runner=self.independent_transport, remote_delete_authorized=True,
            approved_plan_sha256=plan["plan_sha256"], restore_proofs=[proof],
            restore_proof_artifacts=[artifact])
        self.assertEqual(repeated["status"], "COMPLETE")
        self.assertEqual(repeated["deleted"], [])

    def test_prune_missing_reference_has_no_removable_and_changed_source_refuses(self) -> None:
        missing = "BACKUP_" + "a" * 64 + ".zip"
        orphan = "BACKUP_" + "b" * 64 + ".zip"
        plan = owner.plan_backup_prune([orphan], [{"filename": missing}])
        self.assertEqual(plan["removable"], [])
        self.assertEqual(plan["missing_references"], [missing])
        receipt = self.run_checkpoint()
        objects = [Path(remote).name for remote in self.runner.objects]
        plan = owner.plan_checkpoint_prune(self.root, objects=objects, config=self.config)
        chain = owner.read_chain_state(self.root, self.config)
        chain["scientific_pins"] = [orphan]
        owner.write_chain_state(self.root, self.config, chain)
        with self.assertRaisesRegex(owner.OffhostBackupError, "PRUNE_REFERENCE_CONFLICT"):
            owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
                runner=self.independent_transport, remote_delete_authorized=True,
                approved_plan_sha256=plan["plan_sha256"])
        self.assertIn(self.config.remote_object(receipt["checkpoint_filename"]), self.runner.objects)

    def test_prune_rejects_fabricated_assertions_and_revalidates_bound_actual_oracle(self) -> None:
        receipt = self.run_checkpoint()
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1, resolve_backup_sink
        sink = resolve_backup_sink(self.root, load_config_v1_1(self.root), {})
        checkpoint = owner.validate_recovery_checkpoint(sink / receipt["checkpoint_filename"])
        orphan = "BACKUP_" + hashlib.sha256(b"obsolete").hexdigest() + ".zip"
        self.runner.payloads[self.config.remote_object(orphan)] = b"obsolete"
        self.runner.objects[self.config.remote_object(orphan)] = len(b"obsolete")
        objects = [Path(remote).name for remote in self.runner.objects]
        plan = owner.plan_checkpoint_prune(self.root, objects=objects, config=self.config)
        fabricated = {"terminal": "REMOTE_CHECKPOINT_RESTORE_VERIFIED",
            "checkpoint_filename": receipt["checkpoint_filename"], "checkpoint_sha256": receipt["checkpoint_sha256"],
            "result_inventory_sha256": checkpoint["result_inventory_sha256"],
            "verified_objects": [{"filename": Path(remote).name, "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "md5": hashlib.md5(data, usedforsecurity=False).hexdigest()}
                for remote, data in self.runner.payloads.items() if Path(remote).name != orphan],
            "restore": {"raw_inventory_sha256": checkpoint["result_inventory_sha256"],
                        "sqlite_integrity": [{"result": "invented"}]}}
        with self.assertRaisesRegex(owner.OffhostBackupError, "RESTORE_PROOF_ARTIFACT_REQUIRED"):
            owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
                runner=self.independent_transport, remote_delete_authorized=True,
                approved_plan_sha256=plan["plan_sha256"], restore_proofs=[fabricated])
        cache = Path(self.temporary.name) / "durable-proof"
        proof = owner.verify_remote_checkpoint_restore(checkpoint_path=sink / receipt["checkpoint_filename"],
            isolated_root=cache, config=self.config, runner=self.independent_transport)
        artifact = cache / ".remote-restore-proof.json"
        original = artifact.read_bytes()
        plan = owner.plan_checkpoint_prune(self.root, objects=objects, config=self.config,
            restore_proof_artifacts=[artifact])
        self.assertEqual(plan["restore_proof_artifact_sha256"], {receipt["checkpoint_filename"]: hashlib.sha256(original).hexdigest()})
        proof["restore"]["sqlite_integrity"] = [{"result": "invented"}]
        owner._atomic_write_json(artifact, proof)
        with self.assertRaisesRegex(owner.OffhostBackupError, "PROOF_ARTIFACT_CONFLICT"):
            owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
                runner=self.independent_transport, remote_delete_authorized=True,
                approved_plan_sha256=plan["plan_sha256"], restore_proof_artifacts=[artifact])
        rebound = owner.plan_checkpoint_prune(self.root, objects=objects, config=self.config,
            restore_proof_artifacts=[artifact])
        with self.assertRaisesRegex(owner.OffhostBackupError, "PROOF_ORACLE_FAILED"):
            owner.apply_remote_backup_prune(self.root, plan=rebound, config=self.config,
                runner=self.independent_transport, remote_delete_authorized=True,
                approved_plan_sha256=rebound["plan_sha256"], restore_proof_artifacts=[artifact])
        artifact.write_bytes(original)
        rogue = cache / "restored/unexpected.txt"
        rogue.write_bytes(b"outside declared reconstruction")
        with self.assertRaisesRegex(owner.OffhostBackupError, "PROOF_OPERATIONAL_CONFLICT"):
            owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
                runner=self.independent_transport, remote_delete_authorized=True,
                approved_plan_sha256=plan["plan_sha256"], restore_proof_artifacts=[artifact])
        self.assertIn(self.config.remote_object(orphan), self.runner.objects)
        self.assertFalse(any(self.runner._subcommand(call) == "deletefile" for call in self.runner.calls))
        self.assertFalse((cache / ".prune-verify").exists())

    def test_prune_partial_repeat_uses_unchanged_approved_proof_and_plan(self) -> None:
        receipt = self.run_checkpoint()
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1, resolve_backup_sink
        sink = resolve_backup_sink(self.root, load_config_v1_1(self.root), {})
        cache = Path(self.temporary.name) / "partial-proof"
        owner.verify_remote_checkpoint_restore(checkpoint_path=sink / receipt["checkpoint_filename"],
            isolated_root=cache, config=self.config, runner=self.independent_transport)
        artifact = cache / ".remote-restore-proof.json"
        for data in (b"obsolete-one", b"obsolete-two"):
            name = "BACKUP_" + hashlib.sha256(data).hexdigest() + ".zip"
            self.runner.payloads[self.config.remote_object(name)] = data
            self.runner.objects[self.config.remote_object(name)] = len(data)
        plan = owner.plan_checkpoint_prune(self.root, objects=[Path(remote).name for remote in self.runner.objects],
            config=self.config, restore_proof_artifacts=[artifact])
        first = owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
            runner=self.independent_transport, remote_delete_authorized=True,
            approved_plan_sha256=plan["plan_sha256"], restore_proof_artifacts=[artifact], max_delete_objects=1)
        self.assertEqual(first["status"], "PROGRESS")
        second = owner.apply_remote_backup_prune(self.root, plan=plan, config=self.config,
            runner=self.independent_transport, remote_delete_authorized=True,
            approved_plan_sha256=plan["plan_sha256"], restore_proof_artifacts=[artifact], max_delete_objects=1)
        self.assertEqual(second["status"], "COMPLETE")
        self.assertEqual(set(first["deleted"] + second["deleted"]), set(plan["removable"]))
        self.assertFalse((cache / ".prune-verify").exists())

    def test_opt_in_revision_two_has_30h_data_limit_with_old_policy_unchanged(self) -> None:
        self.run_checkpoint()
        revision_two = replace(self.config, freshness_policy_revision=2, freshness_current_max_seconds=30 * 3600)
        for hours, expected in ((24.5, "CURRENT"), (29.9, "CURRENT"), (30.1, "DEGRADED"), (49, "HARD_ATTENTION")):
            health = owner.offhost_health_snapshot(self.root, config=revision_two, now=self.clock + timedelta(hours=hours))
            self.assertEqual(health["offhost_backup_state"], expected)
            self.assertEqual(health["offhost_freshness_policy_revision"], 2)
        old = owner.offhost_health_snapshot(self.root, config=self.config, now=self.clock + timedelta(hours=24.5))
        self.assertEqual(old["offhost_backup_state"], "DEGRADED")

    def test_independent_restore_retry_reuses_one_cache_and_same_downloaded_objects(self) -> None:
        receipt = self.run_checkpoint()
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1, resolve_backup_sink
        sink = resolve_backup_sink(self.root, load_config_v1_1(self.root), {})
        cache = Path(self.temporary.name) / "accounted-cold" / receipt["checkpoint_sha256"]
        attempts = []
        failures = 1

        def intermittent(argv):
            nonlocal failures
            if self.runner._subcommand(argv) == "copyto" and argv[-2].startswith(self.config.remote_prefix):
                attempts.append(argv[-2])
                if "BACKUP_" in argv[-2] and failures:
                    failures -= 1
                    return subprocess.CompletedProcess(argv, 1, "", "fixture failure")
            return self.independent_transport(argv)

        with self.assertRaisesRegex(owner.OffhostBackupError, "CONTENT_READBACK_FAILED"):
            owner.verify_remote_checkpoint_restore(checkpoint_path=sink / receipt["checkpoint_filename"],
                isolated_root=cache, config=self.config, runner=intermittent)
        first_checkpoint_downloads = sum("RECOVERY_CHECKPOINT_" in name for name in attempts)
        proof = owner.verify_remote_checkpoint_restore(checkpoint_path=sink / receipt["checkpoint_filename"],
            isolated_root=cache, config=self.config, runner=intermittent)
        self.assertEqual(proof["terminal"], "REMOTE_CHECKPOINT_RESTORE_VERIFIED")
        self.assertEqual(sum("RECOVERY_CHECKPOINT_" in name for name in attempts), first_checkpoint_downloads)
        self.assertEqual(list(cache.parent.iterdir()), [cache])
        before = len(attempts)
        repeated = owner.verify_remote_checkpoint_restore(checkpoint_path=sink / receipt["checkpoint_filename"],
            isolated_root=cache, config=self.config, runner=intermittent)
        self.assertEqual(repeated, proof)
        self.assertEqual(len(attempts), before)
        data = cache / "restored/local/factory_v1/observation_rdp/source.bin"
        data.write_bytes(b"tampered cold source")
        with self.assertRaisesRegex(owner.OffhostBackupError, "PROOF_CACHE_CONFLICT"):
            owner.verify_remote_checkpoint_restore(checkpoint_path=sink / receipt["checkpoint_filename"],
                isolated_root=cache, config=self.config, runner=intermittent)

    def test_native_indexed_cold_pins_are_in_graph_and_missing_pin_blocks_prune(self) -> None:
        import sqlite3
        receipt = self.run_checkpoint()
        path = self.root / "local/factory_v1/observation_schedule_state.sqlite"
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE retention_archive_pins(object_name TEXT PRIMARY KEY, archive_sha256 TEXT NOT NULL)")
            name = "BACKUP_" + "c" * 64 + ".zip"
            connection.execute("INSERT INTO retention_archive_pins VALUES (?,?)", (name, "d" * 64))
            connection.commit()
        finally:
            connection.close()
        objects = [Path(remote).name for remote in self.runner.objects]
        plan = owner.plan_checkpoint_prune(self.root, objects=objects, config=self.config)
        self.assertIn("NATIVE_COLD_PINS_MISSING_COUNT:1", plan["missing_references"])
        self.assertEqual(plan["removable"], [])
        objects.append(name)
        plan = owner.plan_checkpoint_prune(self.root, objects=objects, config=self.config)
        self.assertIn(name, plan["reachable"])
        self.assertIn(receipt["checkpoint_filename"], plan["reachable"])
        self.assertEqual(plan["missing_references"], [])

    def test_mutable_checkpoint_can_wrap_exact_existing_closed_day_raw_archive(self) -> None:
        receipt = self.run_checkpoint()
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1, resolve_backup_sink
        from solana_alpha_lab.factory.hot90_archive import package_closed_day_archive
        sink = resolve_backup_sink(self.root, load_config_v1_1(self.root), {})
        source = Path(self.temporary.name) / "source-owned-closed-day"
        relative = "datasets/raw_evidence/20261001/body.json"
        payload = b'{"independent":"historical provider body"}'
        raw = source / relative
        raw.parent.mkdir(parents=True)
        raw.write_bytes(payload)
        packed = package_closed_day_archive(source, utc_day="20261001",
            relative_paths=[relative], dest_dir=Path(self.temporary.name) / "archive-staging")
        remote = self.config.remote_object(packed["filename"])
        self.runner.payloads[remote] = packed["path"].read_bytes()
        self.runner.objects[remote] = packed["path"].stat().st_size
        descriptor = {key: packed[key] for key in ("filename", "sha256", "inventory_sha256")}
        descriptor.update(remote_object=remote, raw_entries=packed["entries"])
        cache = Path(self.temporary.name) / "accounted-cold-with-source"
        proof = owner.verify_remote_checkpoint_restore(checkpoint_path=sink / receipt["checkpoint_filename"],
            isolated_root=cache, config=self.config, runner=self.independent_transport,
            supplemental_archives=[descriptor])
        full_path = "local/factory_v1/observation_rdp/" + relative
        self.assertEqual((cache / "restored" / full_path).read_bytes(), payload)
        self.assertEqual(proof["supplemental_raw_inventory"], [{"path": full_path,
            "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}])
        self.assertNotIn(full_path, {entry["path"] for entry in proof["restore"]["restored"]})
        self.assertIn(packed["filename"], {entry["filename"] for entry in proof["verified_objects"]})
        self.assertEqual(proof["restore"]["raw_inventory_sha256"],
            owner.validate_recovery_checkpoint(sink / receipt["checkpoint_filename"])["result_inventory_sha256"])

    def test_default_off_maintenance_never_migrates_source_or_uses_transport(self) -> None:
        path = self.root / "local/factory_v1/observation_schedule_state.sqlite"
        before = path.read_bytes()
        result = owner.run_checkpoint_maintenance(self.root, {}, now=self.clock,
            runner=lambda argv: self.fail("default-off used external transport"))
        self.assertEqual(result["status"], "DISABLED")
        self.assertEqual(path.read_bytes(), before)

    def test_existing_caller_optional_maintenance_failure_keeps_success(self) -> None:
        from scripts import factory_offhost_backup_copy as cli
        output = io.StringIO()
        with patch.object(sys, "argv", ["factory_offhost_backup_copy.py", "--root", str(self.root)]), \
                patch.object(cli, "_git_sha", return_value="a" * 40), \
                patch.object(owner, "run_offhost_checkpoint", return_value={"terminal": "NO_CHANGES_VERIFIED"}), \
                patch.object(owner, "run_checkpoint_maintenance", side_effect=RuntimeError("optional fixture failure")), \
                redirect_stdout(output):
            code = cli.main()
        self.assertEqual(code, 0)
        body = json.loads(output.getvalue())
        self.assertEqual(body["terminal"], "NO_CHANGES_VERIFIED")
        self.assertEqual(body["maintenance"], {"status": "FAILED", "reason": "OPTIONAL_MAINTENANCE_FAILED"})
        self.assertNotIn("optional fixture failure", output.getvalue())


if __name__ == "__main__":
    unittest.main()
