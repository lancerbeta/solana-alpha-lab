"""Native driver proofs: tests feed source bytes and clocks, never trade stages."""
from __future__ import annotations

import json
import os
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import shutil
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import unittest
from decimal import Decimal
from datetime import UTC, datetime, timedelta
from pathlib import Path

import test_trading_continuity_v1 as continuity_fixture
ROOT = continuity_fixture.ROOT
from solana_alpha_lab.factory.trading_coordinator import TradingCoordinator
from solana_alpha_lab.factory.trading_coordinator import restore_native_backup
from solana_alpha_lab.factory.trading_runner import TradingContinuityRunner
from solana_alpha_lab.factory.paper_plane import PaperPlaneStore
from solana_alpha_lab.factory.hfic_research_scope import sha256_of
from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario, nominate, token_object, synth_mint


class OperatingDriverTests(unittest.TestCase):
    setUp = continuity_fixture.OrdinarySourceTests.setUp
    tearDown = continuity_fixture.OrdinarySourceTests.tearDown
    prepare = continuity_fixture.OrdinarySourceTests.prepare

    def test_C06_C19_frozen_base_episode_replay_preserves_identity_and_payload(self):
        from solana_alpha_lab.factory import episode_decision
        from solana_alpha_lab.factory.experiment_spec import validate_experiment_document

        # The oracle is the exact released producer, not expectations derived
        # from the upgraded implementation. CI retains this ancestor's object.
        base = "ba87f8e339d5cc3aa55322801ae56e3f92369446"
        relative = "src/solana_alpha_lab/factory/episode_decision.py"
        frozen = subprocess.check_output(["git", "show", base + ":" + relative],
                                         cwd=ROOT, timeout=10)
        self.assertEqual(hashlib.sha256(frozen).hexdigest(),
                         "e0f70efc50247fe9ccc9cde48104113ed30baa2f92d29e70e83259b03beed5a0")
        baseline = {"__name__": "frozen_legacy_episode_decision", "__file__": str(ROOT / relative)}
        exec(compile(frozen, "frozen-base:episode_decision.py", "exec"), baseline)

        def original_producer(root, **kwargs):
            kwargs.pop("frozen_recipe", None)
            return baseline["produce_episode_decision"](root, **kwargs)

        metrics = []
        owned_roots = []
        for variant in ("absent", "explicit-null", "operating"):
            with self.subTest(runtime_execution=variant):
                if owned_roots:
                    self.tearDown()
                    self.assertFalse(owned_roots[-1].exists())
                    self.setUp()
                owned_roots.append(self.root.parent)
                if variant == "operating":
                    self.start_operating()
                    self.coordinator.tick()
                    store = PaperPlaneStore(self.runner.store_path)
                    try:
                        packets = store.filtered_execution_events(event_type="SOURCE_DECISION_PRODUCED")
                        self.assertEqual(len(packets), 1)
                        self.assertEqual(packets[0]["payload"]["provenance"]["origin_admission"], self.admission)
                        self.assertEqual(self.runner.recipe["executable_exit"],
                                         {"kind": "FROZEN_TIME_EXIT", "exit_point": "E3600"})
                        self.assertEqual(store.positions()[0]["state"], "OPEN")
                    finally:
                        store.close()
                    metrics.append({"runtime_execution": variant, "origin_retained": True,
                                    "executable_exit_retained": True})
                    continue

                dump = continuity_fixture.yaml.safe_dump

                def dump_spec(document, *args, **kwargs):
                    if (variant == "explicit-null" and isinstance(document, dict)
                        and document.get("experiment_id") == "EXP-CONTINUITY-SYNTH-001"):
                        document = {**document, "parameters": {**document["parameters"], "runtime_execution": None}}
                    return dump(document, *args, **kwargs)

                # Author explicit null through the ordinary fixture's spec
                # writer before Git freeze, science, promotion and activation.
                with patch.object(continuity_fixture.yaml, "safe_dump", dump_spec):
                    self.prepare(operating=False)
                document = continuity_fixture.yaml.safe_load((self.root / self.spec_rel).read_text(encoding="utf-8"))
                validate_experiment_document(document, root=self.root)
                if variant == "absent":
                    self.assertNotIn("runtime_execution", document["parameters"])
                else:
                    self.assertIsNone(document["parameters"]["runtime_execution"])
                original_recipe = baseline["load_bound_recipe"](
                    self.root, strategy=self.runner.strategy, manifest=self.manifest, execution_binding=self.binding)
                episode = {"source_relative": "source/observation_schedule_state.sqlite",
                           "episode_id": self.admission["episode_id"], "epoch_id": self.epoch,
                           "mode": "PAPER", "as_of": "2026-10-05T12:40:00Z"}
                # Only the producer is the baseline implementation; native
                # source, admission and persistence use the current owners.
                with patch("solana_alpha_lab.factory.trading_runner.produce_episode_decision", original_producer):
                    original = self.runner.episode(**episode)
                store = PaperPlaneStore(self.runner.store_path)
                try:
                    positions_before = store.positions()
                    journal_before = store.execution_events()
                finally:
                    store.close()
                self.assertEqual(len(positions_before), 1)

                self.runner = TradingContinuityRunner(self.root, data_root=self.data, strategy_relative=self.strategy_rel)
                replay = self.runner.episode(**episode)
                self.assertEqual(self.runner.recipe, original_recipe)
                self.assertNotIn("executable_exit", self.runner.recipe)
                self.assertNotIn("origin_admission", replay["provenance"])
                for field in ("decision", "provenance", "provenance_sha256"):
                    self.assertEqual(replay[field], original[field])
                store = PaperPlaneStore(self.runner.store_path)
                try:
                    self.assertEqual(store.positions(), positions_before)
                    self.assertEqual(store.execution_events(), journal_before)
                    self.assertEqual(store.get_execution_event("SRC-" + original["decision"]["signal_decision_id"])["payload"],
                                     {field: original[field] for field in ("decision", "provenance", "provenance_sha256")})
                finally:
                    store.close()
                metrics.append({"runtime_execution": variant, "decision_sha256": sha256_of(replay["decision"]),
                                "provenance_sha256": replay["provenance_sha256"], "position_count": 1,
                                "journal_count": len(journal_before), "replay_new_journal_events": 0})
        self.metrics = {"baseline_commit": base, "scope": "BASE_PRODUCER_CURRENT_NATIVE_STORE",
                        "cases": metrics, "owned_cleanup_verified_by_teardown": True}

    def start_operating(self, *, mode="PAPER", suffix="", negative=False, exit_cap=None, list_only=False, clock_at=None, batch_size=2,
                        envelope_limits=None):
        if mode == "SHADOW" and not suffix:
            suffix = "-S"
        self.prepare(operating=True, suffix=suffix, negative=negative, exit_point="E3600", list_only=list_only)
        self.now = clock_at or datetime(2026, 10, 5, 12, 40, tzinfo=UTC)
        self.profile = {"schema_version": "1.0", "mode": mode,
            "source": {"root": str(self.source.data_root), "file": "observation_schedule_state.sqlite",
                "schedule_sha256": self.admission["schedule_sha256"], "activation_id": self.admission["activation_id"]},
            "batch_size": batch_size, "poll_seconds": 0.02, "source_max_age_seconds": 900,
            "progress_max_age_seconds": 60, "observation_max_age_seconds": 900,
            "envelope": {"schema_version": "1.0", "mode": mode, "basis": "OUTSTANDING_OBLIGATIONS_V1",
                "max_outstanding_positions": 1, "max_outstanding_cost_basis_usd": "30", **(envelope_limits or {})},
            "model": {"version": "TIMELY_OBSERVATION_MODEL_V1", "missing_input": "UNKNOWN",
                "latency_seconds": 0, "additional_cost_usd": "0.01"},
            "quote": {"timeout_seconds": 1, "max_response_bytes": 8192,
                "funding_mint": "So11111111111111111111111111111111111111112",
                "asset_metadata_file": "assets.json", "funding_observation_file": "funding.json", "max_exit_input_raw": exit_cap},
            "network_authorized": False}
        self.coordinator = TradingCoordinator(self.runner, mode=mode, clock=lambda: self.now)
        if mode=="SHADOW":
            self.quote_inputs(at=self.now.isoformat().replace("+00:00","Z"))
        return self.coordinator.activate(epoch_id=self.epoch, at=self.manifest["decision_effective_at"],
            profile=self.profile, switch_key="INITIAL" + suffix)

    def quote_inputs(self, *, at="2026-10-05T12:40:00Z"):
        source = self.source.data_root
        funding = self.profile["quote"]["funding_mint"]
        (source / "assets.json").write_text(json.dumps({self.mint: {"mint": self.mint, "decimals": 6,
            "observed_at": at, "available_at": at}}), encoding="utf-8")
        (source / "funding.json").write_text(json.dumps({"mint": funding, "decimals": 9,
            "unit_price_usd": "100", "observed_at": at, "available_at": at}), encoding="utf-8")

    def child(self, *, mode="PAPER", fault=None, as_of="2026-10-05T12:40:00Z", ledger=None, plan=None):
        argv = [sys.executable, "-B", str(ROOT / "scripts/prove_trading_core_operational_closure.py"),
            "--repository-root", str(self.root), "--data-root", str(self.data), "--mode", mode, "--as-of", as_of]
        if fault:
            argv += ["--fault", fault]
        if ledger:
            argv += ["--ledger", str(ledger), "--plan", str(plan)]
        return subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def kill_at(self, point, *, while_blocked=None, **kwargs):
        sentinel = self.data / "fault-reached.json"
        if sentinel.exists():
            sentinel.unlink()
        child = self.child(fault=point, **kwargs)
        try:
            until = time.monotonic() + 20
            while not sentinel.exists() and child.poll() is None and time.monotonic() < until:
                time.sleep(.03)
            self.assertTrue(sentinel.exists(), child.communicate(timeout=1) if child.poll() is not None else "FAULT_NOT_REACHED")
            self.assertEqual(json.loads(sentinel.read_text())["point"], point)
            if while_blocked is not None:
                while_blocked()
            child.kill()
            child.communicate(timeout=5)
            self.assertNotEqual(child.returncode, 0)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=5)

    def wire_files(self, plan=None):
        self.quote_inputs()
        ledger = self.root / "local/independent-effects.sqlite"
        plan_path = self.root / "local/wire-plan.json"
        plan_path.write_text(json.dumps(plan or [{"outAmount": "10000000000000"}]), encoding="utf-8")
        return ledger, plan_path

    def ledger_receipts(self, ledger):
        with closing(sqlite3.connect(ledger.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            return [json.loads(row[0]) for row in connection.execute("SELECT receipt_json FROM calls ORDER BY call_id")]

    def recovery_cut(self,ledger,backup):
        from solana_alpha_lab.factory.trading_runtime_policy import operating_configuration_snapshot
        store=PaperPlaneStore(self.runner.store_path,readonly=True)
        try:
            state=store._conn.execute("SELECT * FROM ordinary_state WHERE mode='SHADOW'").fetchone()
            cut={"schema":"smial.operating-external-recovery-cut","schema_version":"1.0","mode":"SHADOW",
                "backup_sha256":hashlib.sha256(backup.read_bytes()).hexdigest(),"external_cut_id":"INDEPENDENT-SYNTHETIC-CUT",
                "as_of":self.now.isoformat().replace("+00:00","Z"),"completeness":"COMPLETE_AFTER_BACKUP",
                "operating_configuration":operating_configuration_snapshot(store,mode="SHADOW",
                    as_of=self.now.isoformat().replace("+00:00","Z")),
                "effects":self.ledger_receipts(ledger),"current_entry":{"epoch_id":state["epoch_id"],"generation":state["generation"]},
                "result_observations":[event for event in store.filtered_execution_events(event_type="MODELED_RESULT_ACCEPTED")
                    if event["payload"]["result"]["attempt_id"] in {receipt["attempt"]["attempt_id"] for receipt in self.ledger_receipts(ledger)}],
                "quote_claims":store.filtered_execution_events(event_type="QUOTE_CALL_CLAIMED"),
                "pending_attempts":[{"attempt":event["payload"],"request":store.get_execution_event("REQUEST-"+event["event_id"])["payload"]}
                    for event in store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED")
                    if store.get_execution_event("FINAL-"+event["event_id"]) is None and event["event_id"] not in {row["attempt"]["attempt_id"] for row in self.ledger_receipts(ledger)}],
                "operating_bindings":[{"activation":store.get_execution_event(bot["activation_epoch_id"]),
                    "binding":store.get_execution_event("OPERATING-"+bot["activation_epoch_id"]),
                    "profile":store.get_execution_event("PROFILE-"+bot["activation_epoch_id"])} for bot in store.bots() if bot["mode"]=="SHADOW"],
                "controls":[{"bot_instance_id":bot["bot_instance_id"],"status":bot["status"],"entries_paused":bool(bot["entries_paused"])}
                    for bot in store.bots() if bot["mode"]=="SHADOW"]}
            return {**cut,"cut_sha256":sha256_of(cut)}
        finally:
            store.close()

    def invoke(self, command, *, strategy=False, expect=0, **fields):
        argv = [sys.executable, "-B", str(ROOT / "scripts/trading_continuity.py"), command,
            "--repository-root", str(self.root), "--data-root", str(self.data)]
        if strategy:
            argv += ["--strategy", self.strategy_rel]
        for key, value in fields.items():
            argv += ["--" + key.replace("_", "-"), str(value)]
        completed = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, expect, completed.stderr.decode(errors="replace") + completed.stdout.decode(errors="replace"))
        return json.loads(completed.stdout)

    def test_C01_C02_C03_C05_C06_native_loop_full_money_oracle(self):
        self.start_operating()
        result = self.invoke("run", ticks=2, as_of="2026-10-05T12:40:00Z")
        self.assertEqual(result["status"], "GRACEFUL_SHUTDOWN")
        observer = self.invoke("readback")
        self.assertEqual({row["mint"] for row in observer["positions"]}, {self.mint}, self.invoke("status", as_of="2026-10-05T12:40:00Z"))
        self.assertEqual(observer["positions"][0]["state"], "OPEN")
        self.assertEqual(observer["positions"][0]["qty_dec"], "10000000.00000000")
        self.assertEqual(len(observer["modeled_attempts"]), 1)
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.invoke("run", ticks=2, as_of="2026-10-05T13:10:00Z")
        observer = self.invoke("readback")
        self.assertEqual(observer["positions"][0]["state"], "RECONCILED")
        # E3600 fixture current price is explicitly .000003, not future 16:05.
        self.assertEqual(observer["positions"][0]["realized_net_pnl_usd_dec"], "-0.12")
        self.assertEqual(observer["modeled_net_after_additional_costs_usd"], "-0.14")
        self.assertEqual(len(observer["modeled_attempts"]), 2)
        self.assertEqual(len(observer["modeled_results"]), 2)

    def test_C10_C14_C15_C17_frozen_controls_and_observer_without_research(self):
        self.start_operating()
        self.coordinator.tick()
        shutil.rmtree(self.data / "research-data")
        (self.root / self.strategy_rel).unlink()
        (self.root / self.spec_rel).unlink()
        cold = TradingContinuityRunner(self.root, data_root=self.data)
        view = TradingCoordinator(cold, mode="PAPER", clock=lambda: self.now).status()
        self.assertTrue(view["integrity_verified"])
        bot = view["instances"][0]
        (self.data / "pause.json").write_text(json.dumps({"command_type": "PAUSE_NEW_ENTRIES",
            "idempotency_key": "COLD-PAUSE", "bot_instance_id": bot["bot_instance_id"]}), encoding="utf-8")
        self.invoke("operator", input="pause.json")
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.invoke("run", ticks=2, as_of="2026-10-05T13:10:00Z")
        readback = self.invoke("readback")
        self.assertEqual(readback["positions"][0]["state"], "RECONCILED")
        self.assertTrue(self.invoke("status", as_of="2026-10-05T13:10:00Z")["instances"][0]["entries_paused"])

    def managed_successor(self, *, envelope_limits=None):
        """The original C07 A-to-B source fixture, shared by ingress proofs."""
        self.start_operating(envelope_limits=envelope_limits)
        self.coordinator.tick()
        old_epoch, old_mint = self.epoch, self.mint
        old_runner, old_profile = self.runner, self.profile
        self.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
        self.assertNotEqual(self.runner.strategy["strategy_id"], old_runner.strategy["strategy_id"])
        self.assertNotEqual(self.runner.recipe["predicates"] if "predicates" in self.runner.recipe else self.runner.recipe,
                            old_runner.recipe["predicates"] if "predicates" in old_runner.recipe else old_runner.recipe)
        start = datetime(2026, 10, 5, 12, 16, 6, tzinfo=UTC)
        feed = EpisodeScenario(self.data / "successor-source", start=start, stops=start + timedelta(hours=3))
        blocked_mint = synth_mint("DeniedB")
        obj = token_object(blocked_mint, price=.000003, liquidity=10000, holders=66)
        nominate(feed.market, start, {"toptraded": [obj], "toptrending": [obj]})
        feed.market.series[blocked_mint] = lambda now: token_object(blocked_mint, price=.000003, liquidity=10000,
            holders=60 if now >= datetime(2026,10,5,12,50,tzinfo=UTC) else 66)
        feed.tick(start)
        feed.tick(datetime(2026, 10, 5, 12, 25, tzinfo=UTC))
        profile = {**old_profile, "source": {"root": str(feed.data_root), "file": "observation_schedule_state.sqlite",
            "schedule_sha256": feed.schedule["schedule_sha256"], "activation_id": feed.activation_id}}
        now = [datetime(2026, 10, 5, 12, 41, tzinfo=UTC)]
        coordinator = TradingCoordinator(self.runner, mode="PAPER", clock=lambda: now[0])
        with self.assertRaisesRegex(ValueError, "OPERATING_SWITCH_STALE_CURRENT"):
            coordinator.activate(epoch_id=self.epoch, at="2026-10-05T12:41:00Z", profile=profile,
                switch_key="STALE-B", expected_current_epoch="ACTIVATION-EPOCH-WRONG")
        self.assertEqual(old_runner.readback()["positions"][0]["state"], "OPEN")
        switched = coordinator.activate(epoch_id=self.epoch, at="2026-10-05T12:41:00Z", profile=profile,
            switch_key="SWITCH-B", expected_current_epoch=old_epoch)
        self.assertEqual(switched["generation"], 2)
        self.assertTrue(coordinator.activate(epoch_id=self.epoch, at="2026-10-05T12:41:00Z", profile=profile,
            switch_key="SWITCH-B", expected_current_epoch=old_epoch)["idempotent"])
        feed.tick(datetime(2026, 10, 5, 12, 50, tzinfo=UTC))
        now[0] = datetime(2026, 10, 5, 12, 55, tzinfo=UTC)
        coordinator.tick()
        return old_epoch, old_mint, old_runner, coordinator, feed, now

    def test_C07_C08_C09_positive_successor_and_old_exit(self):
        old_epoch, old_mint, old_runner, coordinator, feed, now = self.managed_successor()
        new_mint = synth_mint("NewB")
        view = self.invoke("readback")
        self.assertEqual({p["mint"] for p in view["positions"]}, {old_mint})
        refusals = view["admission_refusals"]
        self.assertEqual({e["payload"]["reason_code"] for e in refusals}, {"OUTSTANDING_POSITION_LIMIT"})
        # Remove research and latest A strategy; frozen origin remains usable.
        shutil.rmtree(self.data / "research-data")
        self.source.market.nominations.clear()
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        now[0] = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        cold = TradingCoordinator(TradingContinuityRunner(self.root, data_root=self.data), mode="PAPER", clock=lambda: now[0])
        cold.tick()
        self.assertEqual(cold.status()["inventory"]["position_count"], 0)
        self.assertTrue(cold.status()["exit_reconciliation_healthy"])
        self.assertEqual({p["state"] for p in self.invoke("readback")["positions"]}, {"RECONCILED"})
        later = datetime(2026, 10, 5, 13, 16, 6, tzinfo=UTC)
        obj2 = token_object(new_mint, price=.000003, liquidity=10000, holders=66)
        nominate(feed.market, later, {"toptraded": [obj2], "toptrending": [obj2]})
        feed.market.series[new_mint] = lambda now: token_object(new_mint, price=.000003, liquidity=10000,
            holders=60 if now >= datetime(2026,10,5,13,50,tzinfo=UTC) else 66)
        feed.tick(later)
        feed.tick(datetime(2026, 10, 5, 13, 25, tzinfo=UTC))
        feed.tick(datetime(2026, 10, 5, 13, 50, tzinfo=UTC))
        now[0] = datetime(2026, 10, 5, 13, 55, tzinfo=UTC)
        cold.tick()
        final = self.invoke("readback")
        self.assertEqual({(p["mint"], p["state"]) for p in final["positions"]}, {(old_mint, "RECONCILED"), (new_mint, "OPEN")})
        self.assertEqual({p["activation_epoch_id"] for p in final["positions"]}, {old_epoch, self.epoch})
        self.assertEqual(Decimal(cold.status()["inventory"]["outstanding_cost_basis_usd"]), Decimal("30"))

    def test_C05_C06_C15_real_loss_after_admission(self):
        self.start_operating()
        self.kill_at("AFTER_DECISION_COMMIT")
        before = self.invoke("readback")
        self.assertEqual({p["state"] for p in before["positions"]}, {"WATCHED"})
        self.invoke("run", ticks=2, as_of="2026-10-05T12:40:00Z")
        after = self.invoke("readback")
        self.assertEqual({p["position_id"] for p in before["positions"]}, {p["position_id"] for p in after["positions"]})
        self.assertEqual(len(after["modeled_attempts"]), 1)
        self.assertEqual(after["positions"][0]["state"], "OPEN")

    def test_patch_A1_A2_default_false_shared_admission_uses_managed_envelope(self):
        from solana_alpha_lab.factory.paper_plane import accept_signal_decision_outcome
        for index, (count, money, reason) in enumerate(((1, "60", "OUTSTANDING_POSITION_LIMIT"),
                                                      (2, "30", "OUTSTANDING_COST_BASIS_LIMIT"))):
            if index:
                self.tearDown()
                self.setUp()
            with self.subTest(count=count, money=money):
                old_epoch, _, old_runner, _, feed, _ = self.managed_successor(envelope_limits={
                    "max_outstanding_positions": count, "max_outstanding_cost_basis_usd": money})
                before = self.invoke("readback")
                packet = self.runner.episode(source_relative="successor-source/observation_schedule_state.sqlite",
                    episode_id=feed.admissions()[0]["episode_id"], epoch_id=self.epoch, mode="PAPER",
                    as_of="2026-10-05T12:55:00Z")
                self.assertEqual(packet["decision"]["action"], "ENTER")
                self.assertEqual(packet["admission"]["reason_code"], reason)
                self.assertEqual(packet["admission"]["source_reason_code"], packet["decision"]["reason_code"])
                store = PaperPlaneStore(self.runner.store_path)
                try:
                    direct = accept_signal_decision_outcome(self.root, store, strategy=self.runner.strategy,
                        signal_decision=packet["decision"], known_activation_epochs={self.epoch},
                        mode="PAPER", as_of="2026-10-05T12:55:00Z", skip_fill=True, ordinary_operating=False)
                    self.assertEqual(direct["reason_code"], reason)
                    self.assertTrue(direct["idempotent"])
                finally:
                    store.close()
                after = self.invoke("readback")
                self.assertEqual(after["positions"], before["positions"])
                self.assertEqual(after["modeled_attempts"], before["modeled_attempts"])
                self.assertEqual({p["activation_epoch_id"] for p in after["positions"]}, {old_epoch})
                self.assertEqual(sum(Decimal(p["admitted_entry_notional_usd_dec"]) for p in after["positions"]), Decimal("30"))
                with closing(sqlite3.connect(self.runner.store_path.resolve().as_uri() + "?mode=ro", uri=True)) as observer:
                    self.assertEqual(observer.execute("SELECT COUNT(*) FROM positions").fetchone()[0], 1)
                    self.assertEqual(observer.execute("SELECT COUNT(*) FROM execution_events WHERE event_type IN ('ADAPTER_REQUEST_BOUND','QUOTE_CALL_CLAIMED')").fetchone()[0], 1)
                self.assertEqual(old_runner.readback()["positions"], before["positions"])

    def test_patch_A3_native_restore_fences_new_both_sides_preserves_replay_ack_exit(self):
        from solana_alpha_lab.factory.paper_plane import begin_modeled_attempt
        from scripts.prove_trading_core_operational_closure import RecordingQuoteAdapter
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        original = self.invoke("readback")
        receipt = self.ledger_receipts(ledger)[0]
        backup = self.data / "backups/patch-open.sqlite"
        self.coordinator.backup(destination_relative="backups/patch-open.sqlite")
        restored = self.root / "local/patch-native-restored"
        restored.mkdir()
        shutil.copyfile(self.data / "offline_runtime.json", restored / "offline_runtime.json")
        runner = TradingContinuityRunner(self.root, data_root=restored)
        restore_native_backup(backup_path=backup, destination_runner=runner)
        position = runner.readback()["positions"][0]
        with closing(sqlite3.connect(runner.store_path.resolve().as_uri() + "?mode=ro", uri=True)) as observer:
            self.assertEqual(observer.execute("SELECT restore_guard FROM ordinary_state WHERE mode='SHADOW'").fetchone()[0], 1)
            self.assertEqual(observer.execute("SELECT entries_paused FROM bot_instances").fetchone()[0], 1)
        runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "PATCH-CLOSE",
                        "position_id": position["position_id"]})
        before = runner.readback()
        for side in ("ENTRY", "EXIT"):
            with self.subTest(side=side):
                outcome = runner.attempt(position_id=position["position_id"], side=side,
                    attempt_key="PATCH-LEGACY-" + side, as_of="2026-10-05T12:41:00Z")
                self.assertEqual(outcome["reason_code"], "RESTORE_NEW_EFFECTS_FORBIDDEN")
                self.assertFalse(outcome["send_permitted"])
                store = PaperPlaneStore(runner.store_path)
                try:
                    direct = begin_modeled_attempt(store, position_id=position["position_id"], side=side,
                        mode="SHADOW", attempt_key="PATCH-DIRECT-" + side, decision_at="2026-10-05T12:40:00Z",
                        max_age_seconds=900, as_of="2026-10-05T12:41:00Z", ordinary_operating=False)
                    self.assertEqual(direct["reason_code"], outcome["reason_code"])
                finally:
                    store.close()
        original_attempt = original["modeled_attempts"][0]["payload"]
        replay = runner.attempt(position_id=position["position_id"], side="ENTRY",
            attempt_key=original_attempt["attempt_key"], as_of="2026-10-05T12:40:00Z")
        self.assertTrue(replay["idempotent"])
        self.assertFalse(replay["send_permitted"])
        self.assertEqual(replay["as_of"], original_attempt["as_of"])
        self.assertTrue(runner.result(receipt["result"])["idempotent"])
        after = runner.readback()
        for field in ("positions", "modeled_attempts", "modeled_results"):
            self.assertEqual(after[field], before[field])
        cut = self.recovery_cut(ledger, backup)
        coordinator = TradingCoordinator(runner, mode="SHADOW", clock=lambda: self.now)
        coordinator.reconcile_cut(cut)
        inventory = coordinator.status()["inventory"]
        coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(inventory), as_of=cut["as_of"], cut=cut)
        self.assertFalse(coordinator.status()["restore_guard"])
        self.assertTrue(coordinator.status()["instances"][0]["entries_paused"])
        permitted = runner.attempt(position_id=position["position_id"], side="EXIT",
            attempt_key="PATCH-ACK-EXIT", as_of="2026-10-05T12:41:00Z")
        self.assertTrue(permitted["send_permitted"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)

    def test_patch_A4_missing_corrupt_state_and_legacy_activation_cannot_downgrade(self):
        from solana_alpha_lab.factory.paper_plane import accept_signal_decision_outcome
        _, _, _, _, feed, _ = self.managed_successor()
        packet = self.runner.episode(source_relative="successor-source/observation_schedule_state.sqlite",
            episode_id=feed.admissions()[0]["episode_id"], epoch_id=self.epoch, mode="PAPER", as_of="2026-10-05T12:55:00Z")
        store = PaperPlaneStore(self.runner.store_path)
        try:
            original_state = dict(store._conn.execute("SELECT * FROM ordinary_state WHERE mode='PAPER'").fetchone())
            for sql, reason in (("DELETE FROM ordinary_state WHERE mode='PAPER'", "OPERATING_STATE_REQUIRED"),
                                ("UPDATE ordinary_state SET restore_guard=2 WHERE mode='PAPER'", "OPERATING_STATE_INVALID"),
                                ("UPDATE ordinary_state SET epoch_id='ACTIVATION-EPOCH-STALE' WHERE mode='PAPER'", "OPERATING_ENTRY_SCOPE_NOT_CURRENT")):
                with self.subTest(reason=reason):
                    with store.immediate_write():
                        store._conn.execute(sql)
                        before = store.positions()
                        result = accept_signal_decision_outcome(self.root, store, strategy=self.runner.strategy,
                            signal_decision=packet["decision"], known_activation_epochs={self.epoch}, mode="PAPER",
                            as_of="2026-10-05T12:55:00Z", skip_fill=True)
                        self.assertEqual(result["reason_code"], reason)
                        self.assertEqual(store.positions(), before)
                    if "DELETE" in sql:
                        columns = list(original_state)
                        store._conn.execute("INSERT INTO ordinary_state(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", list(original_state.values()))
                    else:
                        store._conn.execute("UPDATE ordinary_state SET epoch_id=?,restore_guard=? WHERE mode='PAPER'", (original_state["epoch_id"], original_state["restore_guard"]))
            bot_before = store.bots()
            events_before = store.execution_events()
            with self.assertRaisesRegex(ValueError, "OPERATING_ENTRY_SCOPE_NOT_CURRENT"):
                store.start_bot(self.runner.strategy, mode="PAPER", activation_epoch_id="ACTIVATION-EPOCH-PATCH-LEGACY")
            self.assertEqual(store.bots(), bot_before)
            self.assertEqual(store.execution_events(), events_before)
        finally:
            store.close()
        before = self.runner.readback()
        with self.assertRaisesRegex(ValueError, "OPERATING_ENTRY_SCOPE_NOT_CURRENT"):
            self.runner.activate(epoch_id="ACTIVATION-EPOCH-PATCH-LEGACY", mode="PAPER", at="2026-10-05T12:55:00Z")
        self.assertEqual(self.runner.readback(), before)

    def test_patch_A4_binding_profile_envelope_corruption_fails_closed_at_direct_owner(self):
        from solana_alpha_lab.factory.paper_plane import accept_signal_decision_outcome
        _, _, _, _, feed, _ = self.managed_successor()
        packet = self.runner.episode(source_relative="successor-source/observation_schedule_state.sqlite",
            episode_id=feed.admissions()[0]["episode_id"], epoch_id=self.epoch, mode="PAPER", as_of="2026-10-05T12:55:00Z")
        store = PaperPlaneStore(self.runner.store_path)
        try:
            for prefix, missing, corrupt in (("OPERATING-", "OPERATING_BINDING_MISSING", "OPERATING_BINDING_INTEGRITY_CONFLICT"),
                                              ("PROFILE-", "OPERATING_PROFILE_REQUIRED", "OPERATING_PROFILE_INTEGRITY_CONFLICT"),
                                              ("", "OPERATING_ACTIVATION_BINDING_INCOMPLETE", "OPERATING_BINDING_INTEGRITY_CONFLICT")):
                event_id = prefix + self.epoch
                original = dict(store._conn.execute("SELECT * FROM execution_events WHERE event_id=?", (event_id,)).fetchone())
                for alteration, reason in (("DELETE", missing), ("CORRUPT", corrupt)):
                    with self.subTest(owner=prefix, alteration=alteration):
                        with store.immediate_write():
                            if alteration == "DELETE":
                                store._conn.execute("DELETE FROM execution_events WHERE event_id=?", (event_id,))
                            else:
                                store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_id=?", (event_id,))
                            positions = store.positions()
                            direct = accept_signal_decision_outcome(self.root, store, strategy=self.runner.strategy,
                                signal_decision=packet["decision"], known_activation_epochs={self.epoch},
                                mode="PAPER", as_of="2026-10-05T12:55:00Z", skip_fill=True)
                            self.assertEqual(direct["reason_code"], reason)
                            self.assertEqual(store.positions(), positions)
                        if alteration == "DELETE":
                            columns = list(original)
                            store._conn.execute("INSERT INTO execution_events(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", list(original.values()))
                        else:
                            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (original["payload_json"], event_id))
            event_id = "OPERATING-ENVELOPE-PAPER-1"
            original = dict(store._conn.execute("SELECT * FROM execution_events WHERE event_id=?", (event_id,)).fetchone())
            for alteration, reason in (("DELETE", "CONFIGURATION_REQUIRED"), ("CORRUPT", "OPERATING_ENVELOPE_INVALID")):
                with self.subTest(owner="envelope", alteration=alteration):
                    if alteration == "DELETE":
                        store._conn.execute("DELETE FROM execution_events WHERE event_id=?", (event_id,))
                    else:
                        store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_id=?", (event_id,))
                    positions = store.positions()
                    direct = accept_signal_decision_outcome(self.root, store, strategy=self.runner.strategy,
                        signal_decision=packet["decision"], known_activation_epochs={self.epoch},
                        mode="PAPER", as_of="2026-10-05T12:55:00Z", skip_fill=True)
                    self.assertEqual(direct["reason_code"], reason)
                    self.assertEqual(store.positions(), positions)
                    if alteration == "DELETE":
                        columns = list(original)
                        store._conn.execute("INSERT INTO execution_events(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", list(original.values()))
                    else:
                        store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (original["payload_json"], event_id))
        finally:
            store.close()

    def test_patch_A4_observed_physical_clock_guard_at_cli_and_direct_owner(self):
        from solana_alpha_lab.factory.paper_plane import accept_signal_decision_outcome, begin_modeled_attempt
        # Author OBSERVED at original activation; do not relabel retained bindings.
        self.prepare(operating=True, suffix="-OBSERVED", exit_point="E3600")
        scope = self.root / "local/observed-scope"
        observed = scope / "native"
        observed.mkdir(parents=True)
        (observed / "operating_runtime.json").write_text(json.dumps({"schema": "smial.operating-runtime",
            "schema_version": "1.0", "evidence_class": "OBSERVED"}), encoding="utf-8")
        shutil.copytree(self.data / "research-data", observed / "research-data")
        shutil.copytree(self.source.data_root, observed / "source")
        runner = TradingContinuityRunner(self.root, data_root=observed, strategy_relative=self.strategy_rel, scope_root=scope)
        self.profile = {"schema_version": "1.0", "mode": "PAPER",
            "source": {"root": str(self.source.data_root), "file": "observation_schedule_state.sqlite",
                "schedule_sha256": self.admission["schedule_sha256"], "activation_id": self.admission["activation_id"]},
            "batch_size": 2, "poll_seconds": .02, "source_max_age_seconds": 900,
            "progress_max_age_seconds": 60, "observation_max_age_seconds": 900,
            "envelope": {"schema_version": "1.0", "mode": "PAPER", "basis": "OUTSTANDING_OBLIGATIONS_V1",
                "max_outstanding_positions": 1, "max_outstanding_cost_basis_usd": "30"},
            "model": {"version": "TIMELY_OBSERVATION_MODEL_V1", "missing_input": "UNKNOWN", "latency_seconds": 0, "additional_cost_usd": "0.01"},
            "quote": {"timeout_seconds": 1, "max_response_bytes": 8192,
                "funding_mint": "So11111111111111111111111111111111111111112",
                "asset_metadata_file": "assets.json", "funding_observation_file": "funding.json", "max_exit_input_raw": None},
            "network_authorized": False}
        coordinator = TradingCoordinator(runner, mode="PAPER", clock=lambda: datetime(2026, 10, 5, 12, 40, tzinfo=UTC))
        coordinator.activate(epoch_id=self.epoch, at=self.manifest["decision_effective_at"], profile=self.profile, switch_key="OBSERVED-INITIAL")
        from solana_alpha_lab.factory.episode_decision import produce_episode_decision
        packet = produce_episode_decision(self.root, source_path=self.source.ops_path, strategy=runner.strategy,
            manifest=runner.manifest, execution_binding=runner.binding, epoch_id=self.epoch,
            episode_id=self.admission["episode_id"], as_of="2026-10-05T12:40:00Z", frozen_recipe=runner.recipe)
        store = PaperPlaneStore(runner.store_path)
        try:
            outcome = accept_signal_decision_outcome(self.root, store, strategy=runner.strategy,
                signal_decision=packet["decision"], known_activation_epochs={self.epoch}, mode="PAPER",
                as_of="2026-10-05T12:40:00Z", skip_fill=True)
            self.assertEqual(outcome["reason_code"], "OBSERVED_RUNTIME_REQUIRES_PHYSICAL_CLOCK")
            self.assertEqual(store.positions(), [])
        finally:
            store.close()
        child = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/trading_continuity.py"), "episode",
            "--repository-root", str(self.root), "--data-root", str(observed), "--scope-root", str(scope),
            "--strategy", self.strategy_rel, "--epoch", self.epoch, "--episode-id", self.admission["episode_id"],
            "--source", "source/observation_schedule_state.sqlite", "--as-of", "2026-10-05T12:40:00Z"],
            cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual(child.returncode, 0, child.stderr.decode(errors="replace"))
        self.assertEqual(json.loads(child.stdout)["admission"]["reason_code"], "OBSERVED_RUNTIME_REQUIRES_PHYSICAL_CLOCK")
        class FixturePhysicalClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, 5, 12, 40, tzinfo=UTC)
        # A native positive neighbour changes only the test-owned physical
        # clock. The OBSERVED binding, position and attempts are real owners.
        with patch("solana_alpha_lab.factory.paper_plane.datetime", FixturePhysicalClock):
            coordinator.tick()
        view = runner.readback()
        self.assertEqual(view["positions"][0]["state"], "OPEN")
        original_attempt = view["modeled_attempts"][0]["payload"]
        pid = view["positions"][0]["position_id"]
        runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "OBSERVED-CLOSE", "position_id": pid})
        attempts_before = runner.readback()["modeled_attempts"]
        for side in ("ENTRY", "EXIT"):
            refusal = runner.attempt(position_id=pid, side=side, attempt_key="OBSERVED-HISTORICAL-" + side,
                as_of="2026-10-05T12:40:00Z")
            self.assertEqual(refusal["reason_code"], "OBSERVED_RUNTIME_REQUIRES_PHYSICAL_CLOCK")
            self.assertFalse(refusal["send_permitted"])
        replay = runner.attempt(position_id=pid, side="ENTRY", attempt_key=original_attempt["attempt_key"],
            as_of="2026-10-05T12:40:00Z")
        self.assertFalse(replay["send_permitted"])
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["as_of"], original_attempt["as_of"])
        self.assertEqual(runner.readback()["modeled_attempts"], attempts_before)

    def test_patch_A4_native_switch_failure_rolls_back_all_staged_scope(self):
        self.start_operating()
        old_epoch, old_profile = self.epoch, self.profile
        self.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
        before = self.runner.readback()
        store = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            events, state = store.execution_events(), dict(store._conn.execute("SELECT * FROM ordinary_state WHERE mode='PAPER'").fetchone())
        finally:
            store.close()
        coordinator = TradingCoordinator(self.runner, mode="PAPER", clock=lambda: datetime(2026, 10, 5, 12, 41, tzinfo=UTC))
        with patch.object(PaperPlaneStore, "start_bot", side_effect=RuntimeError("NATIVE_ACTIVATION_FAILURE")):
            with self.assertRaisesRegex(RuntimeError, "NATIVE_ACTIVATION_FAILURE"):
                coordinator.activate(epoch_id=self.epoch, at="2026-10-05T12:41:00Z", profile=old_profile,
                    switch_key="ROLLBACK-PATCH", expected_current_epoch=old_epoch)
        self.assertEqual(self.runner.readback(), before)
        store = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            self.assertEqual(store.execution_events(), events)
            self.assertEqual(dict(store._conn.execute("SELECT * FROM ordinary_state WHERE mode='PAPER'").fetchone()), state)
        finally:
            store.close()

    def test_patch_A4_genuine_legacy_binding_and_exact_attempt_replay_remain_compatible(self):
        self.prepare(operating=False)
        packet = continuity_fixture.OrdinarySourceTests.decision(self)
        self.assertEqual(packet["decision"]["action"], "ENTER")
        self.assertIsNotNone(packet["admission"]["position_id"])
        positions = self.runner.readback()["positions"]
        self.assertIsNone(positions[0]["ordinary_operating"])
        self.assertEqual(continuity_fixture.OrdinarySourceTests.decision(self)["decision"], packet["decision"])
        claim = self.runner.attempt(position_id=positions[0]["position_id"], side="ENTRY",
            attempt_key="LEGACY-COMPATIBLE", as_of="2026-10-05T12:40:00Z")
        self.assertTrue(claim["send_permitted"])
        replay = self.runner.attempt(position_id=positions[0]["position_id"], side="ENTRY",
            attempt_key="LEGACY-COMPATIBLE", as_of="2026-10-05T12:40:00Z")
        self.assertFalse(replay["send_permitted"])
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["attempt_id"], claim["attempt_id"])
        legacy = self.runner.activate(epoch_id="ACTIVATION-EPOCH-LEGACY-NEIGHBOR", mode="PAPER", at="2026-10-05T12:40:00Z")
        self.assertFalse(legacy["idempotent"])

    def test_C05_C06_real_loss_after_claim_paper_reconciles(self):
        self.start_operating()
        self.kill_at("AFTER_ATTEMPT_COMMIT")
        before = self.invoke("readback")
        self.assertEqual(before["positions"][0]["state"], "ATTEMPTING")
        self.invoke("run", ticks=2, as_of="2026-10-05T12:40:00Z")
        after = self.invoke("readback")
        self.assertEqual({e["event_id"] for e in after["modeled_attempts"]}, {e["event_id"] for e in before["modeled_attempts"]})
        self.assertEqual(after["positions"][0]["state"], "OPEN")

    def test_C05_C12_real_loss_after_quote_effect_no_resend(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        self.kill_at("AFTER_ADAPTER_EFFECT", mode="SHADOW", ledger=ledger, plan=plan)
        receipts = self.ledger_receipts(ledger)
        self.assertEqual(len(receipts), 1)
        child = self.child(mode="SHADOW", ledger=ledger, plan=plan)
        stdout, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        status = self.invoke("status", mode="SHADOW", as_of="2026-10-05T12:40:00Z")
        self.assertEqual(status["pending_attempts"], 1)
        inbox = self.data / "result-inbox"
        inbox.mkdir()
        receipt = receipts[0]
        (inbox / (receipt["attempt"]["attempt_id"] + ".json")).write_text(json.dumps(receipt["result"]), encoding="utf-8")
        child = self.child(mode="SHADOW", ledger=ledger, plan=plan)
        child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0)
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        view = self.invoke("readback")
        self.assertEqual(view["positions"][0]["state"], "OPEN")

    def test_C05_C06_real_loss_after_capture_no_duplicate_effect(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        self.kill_at("AFTER_RESULT_CAPTURE", mode="SHADOW", ledger=ledger, plan=plan)
        self.assertEqual(self.invoke("readback")["positions"][0]["state"], "ATTEMPTING")
        child = self.child(mode="SHADOW", ledger=ledger, plan=plan)
        child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0)
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        self.assertEqual(self.invoke("readback")["positions"][0]["state"], "OPEN")

    def test_C18_C19_native_restore_before_effect_independent_ledger(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        self.kill_at("AFTER_DECISION_COMMIT", mode="SHADOW", ledger=ledger, plan=plan)
        self.coordinator.backup(destination_relative="backups/pre-effect.sqlite")
        self.kill_at("AFTER_ADAPTER_EFFECT", mode="SHADOW", ledger=ledger, plan=plan)
        receipt = self.ledger_receipts(ledger)[0]
        restored = self.root / "local/fresh-restored"
        restored.mkdir()
        shutil.copyfile(self.data / "offline_runtime.json", restored / "offline_runtime.json")
        runner = TradingContinuityRunner(self.root, data_root=restored)
        outcome = restore_native_backup(backup_path=self.data / "backups/pre-effect.sqlite", destination_runner=runner)
        self.assertFalse(outcome["new_effects_enabled"])
        coordinator = TradingCoordinator(runner, mode="SHADOW", clock=lambda: self.now)
        self.assertTrue(coordinator.status()["restore_guard"])
        self.assertEqual(coordinator.status()["next_safe_action"], "RECONCILE_SAME_ATTEMPT_OR_RESTORE_EXACT_BINDING")
        accepted = coordinator.reconcile_restored_effect(receipt)
        self.assertFalse(accepted["send_permitted"])
        self.assertTrue(coordinator.reconcile_restored_effect(receipt)["idempotent"])
        summary = coordinator.status()["inventory"]
        self.assertEqual(summary["position_count"], 1)
        self.assertEqual(Decimal(summary["outstanding_cost_basis_usd"]), Decimal("30"))
        cut=self.recovery_cut(ledger,self.data / "backups/pre-effect.sqlite")
        coordinator.reconcile_cut(cut)
        after_cut = coordinator.status()
        self.assertEqual(after_cut["next_safe_action"], "ACKNOWLEDGE_RESTORED_INVENTORY")
        self.assertTrue(after_cut["next_safe_command"].startswith("ack-restore --mode SHADOW "))
        coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(summary), as_of="2026-10-05T12:40:00Z",cut=cut)
        self.assertFalse(coordinator.status()["restore_guard"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)

    def test_C18_pre_admission_snapshot_complete_cut_no_duplicate(self):
        from scripts.prove_trading_core_operational_closure import RecordingQuoteAdapter
        self.start_operating(mode="SHADOW")
        backup=self.data/"backups/pre-admission.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-admission.sqlite")
        ledger,plan=self.wire_files()
        self.coordinator.quote_adapter=RecordingQuoteAdapter(ledger,json.loads(plan.read_text()))
        self.coordinator.tick()
        cut=self.recovery_cut(ledger,backup)
        restored=self.root/"local/pre-admission-restored"
        restored.mkdir()
        shutil.copyfile(self.data/"offline_runtime.json",restored/"offline_runtime.json")
        runner=TradingContinuityRunner(self.root,data_root=restored)
        restore_native_backup(backup_path=backup,destination_runner=runner)
        coordinator=TradingCoordinator(runner,mode="SHADOW",clock=lambda:self.now,
            quote_adapter=RecordingQuoteAdapter(ledger,json.loads(plan.read_text())))
        with self.assertRaisesRegex(ValueError,"RESTORE_COMPLETE_EXTERNAL_CUT_REQUIRED"):
            coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(coordinator.status()["inventory"]),as_of=cut["as_of"])
        coordinator.reconcile_cut(cut)
        coordinator.reconcile_cut(cut)
        summary=coordinator.status()["inventory"]
        self.assertEqual(summary["position_count"],1)
        self.assertEqual(Decimal(summary["outstanding_cost_basis_usd"]),Decimal("30"))
        coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(summary),as_of=cut["as_of"],cut=cut)
        coordinator.tick()
        self.assertTrue(coordinator.status()["instances"][0]["entries_paused"])
        self.assertEqual(len(self.ledger_receipts(ledger)),1)
        self.assertEqual(runner.readback()["positions"][0]["state"],"OPEN")

    def test_C14_nondivisible_raw_funding_adapter_accepts_partial(self):
        from scripts.prove_trading_core_operational_closure import RecordingQuoteAdapter
        self.start_operating(mode="SHADOW")
        ledger,plan=self.wire_files()
        path=self.source.data_root/"funding.json"
        funding=json.loads(path.read_text())
        funding["unit_price_usd"]="137.12"
        path.write_text(json.dumps(funding),encoding="utf-8")
        self.coordinator.quote_adapter=RecordingQuoteAdapter(ledger,json.loads(plan.read_text()))
        self.coordinator.tick()
        view=self.invoke("readback")
        self.assertEqual(view["positions"][0]["state"],"PARTIAL")
        result=view["modeled_results"][0]["payload"]["result"]
        self.assertEqual(result["outcome"],"PARTIAL")
        self.assertEqual(Decimal(result["filled_notional_usd"]),Decimal("29.99999994368"))
        self.assertEqual(Decimal(view["positions"][0]["qty_dec"]),Decimal("10000000"))

    def test_C18_backup_before_due_exit_imports_original_exit_no_repeat(self):
        from scripts.prove_trading_core_operational_closure import RecordingQuoteAdapter
        self.start_operating(mode="SHADOW")
        ledger,plan=self.wire_files([{"outAmount":"10000000000000"},{"outAmount":"330000000"}])
        self.coordinator.quote_adapter=RecordingQuoteAdapter(ledger,json.loads(plan.read_text()))
        self.coordinator.tick()
        backup=self.data/"backups/pre-exit.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-exit.sqlite")
        self.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
        self.now=datetime(2026,10,5,13,10,tzinfo=UTC)
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        self.coordinator.tick()
        cut=self.recovery_cut(ledger,backup)
        restored=self.root/"local/pre-exit-restored"
        restored.mkdir()
        shutil.copyfile(self.data/"offline_runtime.json",restored/"offline_runtime.json")
        runner=TradingContinuityRunner(self.root,data_root=restored)
        restore_native_backup(backup_path=backup,destination_runner=runner)
        coordinator=TradingCoordinator(runner,mode="SHADOW",clock=lambda:self.now,
            quote_adapter=RecordingQuoteAdapter(ledger,json.loads(plan.read_text())))
        coordinator.reconcile_cut(cut)
        summary=coordinator.status()["inventory"]
        self.assertEqual(summary["position_count"],0)
        coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(summary),as_of="2026-10-05T13:10:00Z",cut=cut)
        coordinator.tick()
        self.assertEqual(len(self.ledger_receipts(ledger)),2)
        self.assertEqual(runner.readback()["positions"][0]["state"],"RECONCILED")

    def test_C09_cached_tick_clock_cannot_authorize_expired_entry(self):
        self.start_operating()
        original=self.coordinator._recover
        def delayed(store,at):
            result=original(store,at)
            self.now=datetime(2026,10,5,13,0,tzinfo=UTC)
            return result
        self.coordinator._recover=delayed
        self.coordinator.tick()
        self.assertEqual(self.invoke("readback")["modeled_attempts"],[])

    def test_C09_C11_C12_shadow_failure_unknown_partial_remainder_drain(self):
        from scripts.prove_trading_core_operational_closure import RecordingQuoteAdapter
        from solana_alpha_lab.factory.trading_adapters import JupiterQuoteAdapter, ENDPOINT
        from urllib.parse import urlencode
        self.start_operating(mode="SHADOW", exit_cap="4000000000000")
        ledger, plan_path = self.wire_files()
        plan = [{"outAmount": "10000000000000"}, {"status": 400}, {"status": 504},
                {"outAmount": "120000000"}, {"outAmount": "60000000"}]
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, plan)
        self.coordinator.tick()
        position = self.invoke("readback")["positions"][0]
        self.runner.command({"command_type": "STOP_BOT", "idempotency_key": "DRAIN-SHADOW", "bot_instance_id": position["bot_instance_id"]})
        self.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
        self.now = datetime(2026,10,5,13,10,tzinfo=UTC)
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        self.coordinator.tick()  # definitive model refusal keeps inventory
        self.assertEqual(self.invoke("readback")["positions"][0]["state"], "UNRESOLVED")
        self.coordinator.tick()  # original new attempt, unknown
        self.coordinator.tick()  # no repeat HTTP
        receipts = self.ledger_receipts(ledger)
        self.assertEqual(len(receipts), 3)
        request, attempt = receipts[-1]["request"], receipts[-1]["attempt"]
        raw = {key: request[key] for key in ("inputMint", "outputMint", "amount")}
        response = {"status": 200, "url": ENDPOINT + "?" + urlencode(raw), "body": json.dumps({
            "transaction": None, "inputMint": raw["inputMint"], "outputMint": raw["outputMint"],
            "inAmount": raw["amount"], "outAmount": "132000000", "router": "metis", "mode": "ultra",
            "feeBps": 20, "feeMint": raw["outputMint"], "requestId": "ORIGINAL-DELAYED-QUOTE"}).encode()}
        delayed, _ = JupiterQuoteAdapter(timeout_seconds=1,max_response_bytes=8192).project_response(attempt, request, response, as_of="2026-10-05T13:10:00Z")
        delayed["result_id"] += "-FINAL"
        inbox = self.data / "result-inbox"
        inbox.mkdir()
        (inbox / (attempt["attempt_id"] + ".json")).write_text(json.dumps(delayed), encoding="utf-8")
        self.coordinator.tick()  # reconcile 4m, then execute next bounded 4m
        remaining = self.invoke("readback")["positions"][0]
        self.assertEqual(Decimal(remaining["remaining_qty_dec"]), Decimal("2000000"))
        self.coordinator.tick()  # final 2m, drain
        final = self.invoke("readback")
        self.assertEqual(final["positions"][0]["state"], "RECONCILED")
        self.assertEqual(Decimal(final["positions"][0]["realized_net_pnl_usd_dec"]), Decimal("1.20"))
        self.assertEqual(self.coordinator.status()["instances"][0]["status"], "STOPPED")
        self.assertEqual(len(self.ledger_receipts(ledger)), 5)
        self.assertEqual({r["attempt"]["side"] for r in self.ledger_receipts(ledger)}, {"ENTRY", "EXIT"})

    def test_C04_exact_stream_sets_equal_timestamps_pagination(self):
        flat, unknown, other = synth_mint("Zero"), synth_mint("Unknown"), synth_mint("Extra")
        self.stream_cases = {flat: {"start":60,"end":70}, unknown: {"start":60,"end":70}, other: {"start":60,"end":70}}
        self.start = datetime(2026,10,5,11,46,6,tzinfo=UTC)
        self.source = EpisodeScenario(self.data / "many-source", start=self.start, stops=self.start + timedelta(minutes=1), daily_ceiling=100)
        self.start_operating(clock_at=datetime(2026,10,5,12,25,tzinfo=UTC), batch_size=1)
        with closing(sqlite3.connect(self.source.ops_path.resolve().as_uri()+"?mode=ro", uri=True)) as observer:
            inputs = observer.execute("SELECT episode_id,mint,t0 FROM episode_admissions ORDER BY rowid").fetchall()
        # Native quota at round 47 is two; unsampled vendor candidates are
        # not source identities, so they cannot be counted as dropped work.
        self.assertEqual(len(inputs), 2)
        expected_actions = {row[1]: "ENTER" for row in inputs}
        self.assertEqual(len({r[2] for r in inputs}), 1)
        expected_admitted = next(row[1] for row in inputs if expected_actions[row[1]] == "ENTER")
        for _ in range(4):
            self.coordinator.tick()
        store = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            decisions = store.filtered_execution_events(event_type="SOURCE_DECISION_PRODUCED")
            self.assertEqual({e["payload"]["decision"]["mint"]:e["payload"]["decision"]["action"] for e in decisions}, expected_actions)
            self.assertEqual(len(decisions), 2)
            self.assertEqual({p["mint"] for p in store.positions()}, {expected_admitted})
            self.assertEqual(len(store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED")), 1)
            work = store._conn.execute("SELECT episode_id,status FROM ordinary_work").fetchall()
            self.assertEqual({row[0] for row in work}, {row[0] for row in inputs})
            self.assertEqual(len(work), 2)
        finally:
            store.close()

    def test_C03_list_only_same_driver(self):
        self.start_operating(list_only=True)
        self.coordinator.tick()
        self.assertEqual(self.invoke("readback")["positions"][0]["state"], "OPEN")

    def test_C03_late_input_unknown_is_not_healed_by_publication(self):
        self.late = True
        self.start_operating()
        self.coordinator.tick()
        self.assertEqual(self.invoke("readback")["positions"], [])
        store = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            before = store.filtered_execution_events(event_type="SOURCE_DECISION_PRODUCED")
            self.assertEqual(len(before), 1)
            self.assertEqual(before[0]["payload"]["decision"]["action"], "UNKNOWN")
        finally:
            store.close()
        self.source.tick(datetime(2026,10,5,12,41,tzinfo=UTC))
        self.now = datetime(2026,10,5,12,41,tzinfo=UTC)
        self.coordinator.tick()
        store = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            self.assertEqual(store.filtered_execution_events(event_type="SOURCE_DECISION_PRODUCED"), before)
            self.assertEqual(store.positions(), [])
        finally:
            store.close()

    def test_C04_late_physical_source_insert_survives_restart(self):
        self.start_operating()
        with closing(sqlite3.connect(self.source.ops_path)) as connection:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(episode_admissions)")]
            original = connection.execute("SELECT * FROM episode_admissions").fetchone()
            connection.execute("DELETE FROM episode_admissions")
            connection.commit()
        self.now = datetime(2026,10,5,12,39,59,tzinfo=UTC)
        self.coordinator.tick()
        self.assertEqual(self.invoke("readback")["positions"], [])
        with closing(sqlite3.connect(self.source.ops_path)) as connection:
            connection.execute("INSERT INTO episode_admissions ("+",".join(columns)+") VALUES ("+",".join("?" for _ in columns)+")", original)
            connection.commit()
        self.invoke("run",ticks=2,as_of="2026-10-05T12:40:00Z")
        view = self.invoke("readback")
        self.assertEqual({row["mint"] for row in view["positions"]},{self.mint})
        self.assertEqual(len(view["modeled_attempts"]),1)

    def test_C17_readonly_current_wal_snapshot_writes_nothing(self):
        self.start_operating()
        self.coordinator.tick()
        writer = PaperPlaneStore(self.runner.store_path)
        try:
            writer._conn.execute("PRAGMA wal_autocheckpoint=0")
            writer._conn.execute("UPDATE ordinary_state SET last_work_id='WAL-CURRENT' WHERE mode='PAPER'")
            # WAL readers update ephemeral shared-memory read marks. Business
            # DB/WAL bytes must stay exact; SHM locking is not a data mutation.
            files = [self.runner.store_path,Path(str(self.runner.store_path)+"-wal")]
            before = {path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            self.assertEqual(self.invoke("status",as_of="2026-10-05T12:40:00Z")["last_completed_work"],"WAL-CURRENT")
            after = {path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            self.assertEqual(after,before)
        finally:
            writer.close()

    def test_C17_current_runtime_policy_health_preserves_known_inventory_and_old_exit(self):
        from solana_alpha_lab.factory import trading_runtime_policy as policy_owner
        self.start_operating()
        self.coordinator.run(ticks=1)
        cold = TradingCoordinator(TradingContinuityRunner(self.root, data_root=self.data),
            mode="PAPER", clock=lambda: self.now)
        absent = cold.status()
        self.assertEqual(absent["status"], "READY")
        self.assertEqual(absent["runtime_policy_status"], "NOT_CONFIGURED_STRATEGY_ONLY")
        self.assertIsNone(absent["runtime_policy_revision"])
        self.assertEqual(absent["runtime_policy_sha256"], "0" * 64)
        self.assertTrue(absent["runtime_policy_verified"])
        self.assertEqual(absent["inventory"]["inventory_status"], "KNOWN")
        writer = PaperPlaneStore(self.runner.store_path)
        try:
            with patch.object(policy_owner, "_now", return_value="2026-10-05T12:40:00Z"):
                applied = policy_owner.apply_policy(ROOT, writer, mode="PAPER",
                    candidate_raw={"new_entries_enabled": True}, expected_current_sha256="0" * 64,
                    idempotency_key="READBACK-POLICY", owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY",
                    reason="SYNTHETIC_CURRENT_POLICY_READBACK")
            valid = cold.status()
            self.assertEqual(valid["status"], "READY")
            self.assertEqual(valid["runtime_policy_status"], "VALID")
            self.assertEqual(valid["runtime_policy_revision"], 1)
            self.assertEqual(valid["runtime_policy_sha256"], applied["policy_sha256"])
            writer._conn.execute("PRAGMA wal_autocheckpoint=0")
            writer._conn.execute("UPDATE trading_runtime_policy_revisions SET policy_json='{}' WHERE mode='PAPER'")
            files = [self.runner.store_path, Path(str(self.runner.store_path) + "-wal")]
            before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            original_position = writer.positions()[0]
            owner = policy_owner.resolve_current_policy(writer, "PAPER")
            self.assertEqual(owner["status"], "RUNTIME_POLICY_INVALID")
            native = cold.status()
            cli = self.invoke("status", as_of="2026-10-05T12:40:00Z")
            for view in (native, cli):
                self.assertEqual(view["status"], "ACTION_REQUIRED")
                self.assertEqual(view["runtime_policy_status"], owner["status"])
                self.assertEqual(view["runtime_policy_revision"], owner["revision"])
                self.assertEqual(view["runtime_policy_sha256"], owner["policy_sha256"])
                self.assertFalse(view["runtime_policy_verified"])
                self.assertFalse(view["integrity_verified"])
                self.assertEqual(view["operating_configuration_status"], "RUNTIME_POLICY_INVALID")
                self.assertEqual(view["next_safe_action"], "VERIFY_RUNTIME_POLICY")
                self.assertEqual(view["next_safe_command"], "readback --mode PAPER")
                self.assertEqual(view["inventory"], valid["inventory"])
                self.assertTrue(view["exit_reconciliation_healthy"])
            human = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/trading_continuity.py"),
                "status", "--repository-root", str(self.root), "--data-root", str(self.data),
                "--as-of", "2026-10-05T12:40:00Z", "--format", "human"], capture_output=True, timeout=30)
            self.assertEqual(human.returncode, 0)
            text = human.stdout.decode("utf-8")
            self.assertIn("PAPER · ACTION_REQUIRED", text)
            self.assertIn("Политика входов: RUNTIME_POLICY_INVALID · revision: 1 · SHA256: " + owner["policy_sha256"], text)
            self.assertNotIn("PAPER · READY", text)
            after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            self.assertEqual(after, before)
            self.assertEqual(writer.positions(), [original_position])
        finally:
            writer.close()
        # The current policy is still damaged; original A's bound EXIT remains
        # independently executable and must not be converted into UNKNOWN.
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        self.coordinator.run(ticks=2)
        after_exit = cold.status()
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "RECONCILED")
        self.assertEqual(after_exit["inventory"]["position_count"], 0)
        self.assertEqual(after_exit["inventory"]["inventory_status"], "KNOWN")
        self.assertEqual(after_exit["pending_attempts"], 0)
        self.assertTrue(after_exit["exit_reconciliation_healthy"])
        self.assertEqual(after_exit["runtime_policy_status"], "RUNTIME_POLICY_INVALID")
        self.assertEqual(after_exit["status"], "ACTION_REQUIRED")
        self.metrics = {"optional_absent_policy": "READY_STRATEGY_ONLY", "valid_policy": "READY",
            "corrupt_policy": "ACTION_REQUIRED", "original_inventory_status": "KNOWN",
            "db_wal_bytes_unchanged_by_native_json_human_readback": True,
            "old_exit_after_policy_corruption": "RECONCILED", "pending_attempts": 0}

    def test_C03_C17_observed_current_health_denies_virtual_clocks_readonly(self):
        from scripts.prove_trading_core_operational_closure import RecordingQuoteAdapter
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.run(ticks=1)
        (self.data / "probe-profile.json").write_text(json.dumps(self.profile), encoding="utf-8")
        (self.data / "virtual-clock.json").write_text(json.dumps({"as_of": "2026-10-05T12:40:00Z"}), encoding="utf-8")

        def cli(command, *, observed=False, **fields):
            argv = [sys.executable, "-B", str(ROOT / "scripts/trading_continuity.py"), command,
                "--repository-root", str(self.root), "--data-root", str(self.data), "--mode", "SHADOW"]
            if observed:
                argv += ["--scope-root", str(self.root / "local")]
            if command == "check":
                argv += ["--strategy", self.strategy_rel, "--profile", "probe-profile.json"]
            for key, value in fields.items():
                argv += ["--" + key.replace("_", "-"), str(value)]
            result = subprocess.run(argv, capture_output=True, timeout=30)
            return result.returncode, result.stdout.decode("utf-8")

        # Both virtual forms remain supported for synthetic input fixtures.
        for command, expected in (("status", "READY"), ("check", "PROFILE_VERIFIED")):
            for fields in ({"as_of": "2026-10-05T12:40:00Z"}, {"clock_file": "virtual-clock.json"}):
                code, output = cli(command, **fields)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output)["status"], expected)
        # This is a synthetic disposable OBSERVED-boundary fixture. The old
        # offline marker deliberately remains to prove it cannot authorize a
        # virtual clock after the runner selected the OBSERVED evidence class.
        (self.data / "operating_runtime.json").write_text(json.dumps({"schema": "smial.operating-runtime",
            "schema_version": "1.0", "evidence_class": "OBSERVED"}), encoding="utf-8")
        writer = PaperPlaneStore(self.runner.store_path)
        try:
            writer._conn.execute("PRAGMA wal_autocheckpoint=0")
            files = [self.runner.store_path, Path(str(self.runner.store_path) + "-wal")]
            before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            original = writer.execution_events()
            for command in ("status", "check", "tick", "run"):
                for fields in ({"as_of": "2026-10-05T12:40:00Z"}, {"clock_file": "virtual-clock.json"}):
                    code, output = cli(command, observed=True, **fields)
                    self.assertEqual(code, 2)
                    result = json.loads(output)
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertEqual(result["reason_code"], "OBSERVED_RUNTIME_REQUIRES_PHYSICAL_CLOCK")
            physical_before = datetime.now(UTC)
            code, output = cli("status", observed=True)
            physical_after = datetime.now(UTC)
            physical = json.loads(output)
            self.assertEqual(code, 0)
            self.assertEqual(physical["status"], "ACTION_REQUIRED")
            self.assertLessEqual(physical_before, datetime.fromisoformat(physical["as_of"].replace("Z", "+00:00")))
            self.assertLessEqual(datetime.fromisoformat(physical["as_of"].replace("Z", "+00:00")), physical_after)
            code, output = cli("check", observed=True)
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output)["reason_code"], "EXECUTION_OBSERVATION_STALE_OR_FUTURE")
            code, output = cli("status", observed=True, as_of="2026-10-05T12:40:00Z", format="human")
            self.assertEqual(code, 2)
            self.assertIn("OBSERVED_RUNTIME_REQUIRES_PHYSICAL_CLOCK", output)
            self.assertEqual(writer.execution_events(), original)
            self.assertEqual({path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}, before)
        finally:
            writer.close()
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        self.metrics = {"synthetic_virtual_forms_retained": ["as_of", "clock_file"],
            "observed_virtual_current_health_denials": 8, "physical_status": "ACTION_REQUIRED",
            "physical_check": "EXECUTION_OBSERVATION_STALE_OR_FUTURE", "db_wal_bytes_unchanged": True,
            "new_quote_effects": 0}

    def test_C03_observed_activation_timestamp_does_not_override_freshness_clock(self):
        self.start_operating(mode="SHADOW")
        (self.data / "probe-profile.json").write_text(json.dumps(self.profile), encoding="utf-8")
        (self.data / "operating_runtime.json").write_text(json.dumps({"schema": "smial.operating-runtime",
            "schema_version": "1.0", "evidence_class": "OBSERVED"}), encoding="utf-8")

        def activate(command, epoch, key):
            completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/trading_continuity.py"), command,
                "--repository-root", str(self.root), "--data-root", str(self.data), "--scope-root", str(self.root / "local"),
                "--mode", "SHADOW", "--strategy", self.strategy_rel, "--profile", "probe-profile.json",
                "--epoch", epoch, "--as-of", "2026-10-05T12:40:00Z", "--switch-key", key,
                "--expected-current-epoch", self.epoch], capture_output=True, timeout=30)
            return completed.returncode, json.loads(completed.stdout)

        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            before = store.execution_events()
        for command in ("operating-activate", "switch"):
            code, result = activate(command, self.epoch + "-OBSERVED", command)
            self.assertEqual(code, 2)
            self.assertEqual(result["reason_code"], "EXECUTION_OBSERVATION_STALE_OR_FUTURE")
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            self.assertEqual(store.execution_events(), before)
        # Authored disposable funding is fresh at the physical clock. The
        # explicit historical activation timestamp remains metadata, not the
        # input-freshness clock; this activation has no quote/provider effect.
        self.quote_inputs(at=datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        new_epoch = self.epoch + "-OBSERVED"
        code, result = activate("switch", new_epoch, "FRESH-PHYSICAL-INPUT")
        self.assertEqual(code, 0)
        self.assertEqual(result["epoch_id"], new_epoch)
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            activation = store.get_execution_event(new_epoch)
            self.assertEqual(activation["created_at"], "2026-10-05T12:40:00Z")
            self.assertEqual(store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED"), [])
        self.metrics = {"observed_stale_activation_denials": 2, "fresh_physical_input_switch": "PASS",
            "original_activation_timestamp_retained": "2026-10-05T12:40:00Z", "quote_effects": 0}

    def test_C07_invalid_and_concurrent_successor_preserve_atomic_pointer(self):
        self.start_operating()
        self.coordinator.tick()
        old_epoch=self.epoch
        old_bot=self.coordinator.status()["instances"][0]["bot_instance_id"]
        self.prepare(operating=True,suffix="-B",negative=True,exit_point="E3600")
        candidate=TradingCoordinator(self.runner,mode="PAPER",clock=lambda:self.now)
        invalid={**self.profile,"network_authorized":True}
        with self.assertRaisesRegex(ValueError,"PROFILE_CANNOT_GRANT_NETWORK_AUTHORITY"):
            candidate.activate(epoch_id=self.epoch,at="2026-10-05T12:40:00Z",profile=invalid,
                switch_key="INVALID-B",expected_current_epoch=old_epoch)
        before=self.invoke("status",as_of="2026-10-05T12:40:00Z")
        self.assertEqual(before["activation_epoch_id"],old_epoch)
        self.assertEqual(next(bot for bot in before["instances"] if bot["bot_instance_id"]==old_bot)["status"],"RUNNING")
        def switch(number):
            try:
                candidate.activate(epoch_id=self.epoch+str(number),at="2026-10-05T12:40:00Z",profile=self.profile,
                    switch_key="RACE-B-"+str(number),expected_current_epoch=old_epoch)
                return "SWITCHED"
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(switch,(1,2)))
        self.assertEqual(sorted(results),["OPERATING_SWITCH_STALE_CURRENT","SWITCHED"])
        after=self.invoke("status",as_of="2026-10-05T12:40:00Z")
        self.assertEqual(len([bot for bot in after["instances"] if bot["status"]=="RUNNING" and not bot["entries_paused"]]),1)
        self.assertEqual(next(bot for bot in after["instances"] if bot["bot_instance_id"]==old_bot)["status"],"DRAINING")
        self.assertEqual(after["inventory"]["position_count"],1)

    def test_C23_actual_egress_secret_and_non_target_canaries(self):
        self.start_operating(mode="SHADOW")
        self.quote_inputs()
        hits=[]
        class Canary(BaseHTTPRequestHandler):
            def do_CONNECT(self):
                hits.append(self.path)
                self.send_error(502)
            def do_GET(self):
                hits.append(self.path)
                self.send_error(502)
            def log_message(self,*args):
                pass
        server=ThreadingHTTPServer(("127.0.0.1",0),Canary)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        non_target=self.root/"non-target-canary.bin"
        non_target.write_bytes(b"unowned product sentinel")
        before=hashlib.sha256(non_target.read_bytes()).hexdigest()
        canary="SYNTHETIC_SECRET_CANARY_C23_73b55b"
        try:
            proxy="http://127.0.0.1:"+str(server.server_port)
            with patch.dict(os.environ,{"HTTPS_PROXY":proxy,"HTTP_PROXY":proxy,"NO_PROXY":"", "JUPITER_API_KEY":canary}):
                blocked=self.invoke("run",mode="SHADOW",ticks=1,as_of="2026-10-05T12:40:00Z")
                self.assertEqual(blocked["status"],"GRACEFUL_SHUTDOWN")
                self.assertEqual(blocked["ticks"],1)
                observer=self.invoke("status",mode="SHADOW",as_of="2026-10-05T12:40:00Z")
                self.assertFalse(observer["entries_enabled"])
                self.assertTrue(any(row["reason"]=="QUOTE_EXTERNAL_AUTHORITY_REQUIRED" for row in observer["entry_blockers"]))
                self.assertTrue(observer["exit_reconciliation_healthy"])
                with closing(sqlite3.connect(self.runner.store_path.resolve().as_uri()+"?mode=ro",uri=True)) as native:
                    for kind in ("MODELED_ATTEMPT_STARTED","ADAPTER_REQUEST_BOUND","QUOTE_CALL_CLAIMED"):
                        self.assertEqual(native.execute("SELECT COUNT(*) FROM execution_events WHERE event_type=?",(kind,)).fetchone()[0],0)
                live=self.invoke("run",mode="LIVE",ticks=1,expect=2)
                self.assertEqual(live["reason_code"],"LIVE_ROUTE_FORBIDDEN")
            self.assertEqual(hits,[])
            self.assertEqual(hashlib.sha256(non_target.read_bytes()).hexdigest(),before)
            for path in self.data.rglob("*"):
                if path.is_file():
                    self.assertNotIn(canary.encode(),path.read_bytes())
            self.metrics={"actual_loopback_egress_hits":0,"secret_canary_absent":True,"non_target_sha256_unchanged":True,
                "new_attempts_requests_quota":0,"scoped_missing_grant_retained":True,"exit_reconciliation_healthy":True}
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_C03_C04_deadline_and_stale_do_not_backdate(self):
        self.start_operating()
        self.now = datetime(2026,10,5,12,39,59,tzinfo=UTC)
        self.coordinator.tick()
        self.assertEqual(self.invoke("readback")["positions"], [])
        self.now = datetime(2026,10,5,12,40,31,tzinfo=UTC)
        self.coordinator.tick()
        self.assertEqual(self.invoke("readback")["modeled_attempts"], [])
        with closing(sqlite3.connect(self.runner.store_path.resolve().as_uri()+"?mode=ro",uri=True)) as observer:
            self.assertEqual(observer.execute("SELECT status FROM ordinary_work").fetchone()[0], "SKIPPED_STALE")

    def test_C01_check_rejects_missing_or_invalid_operating_limits_readonly(self):
        self.start_operating(negative=True)
        original = self.profile["envelope"]
        target = self.data / "bad-profile.json"
        with closing(sqlite3.connect(self.runner.store_path)) as writer:
            writer.execute("SELECT COUNT(*) FROM positions").fetchone()
            files = [self.runner.store_path, Path(str(self.runner.store_path) + "-wal")]
            before = [hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None for path in files]
            for kind in ("NULL", "MISSING_COUNT", "MISSING_MONEY", "BOOLEAN_COUNT", "WRONG_MODE"):
                with self.subTest(kind=kind):
                    envelope = None if kind == "NULL" else dict(original)
                    if kind == "MISSING_COUNT":
                        envelope.pop("max_outstanding_positions")
                    elif kind == "MISSING_MONEY":
                        envelope.pop("max_outstanding_cost_basis_usd")
                    elif kind == "BOOLEAN_COUNT":
                        envelope["max_outstanding_positions"] = True
                    elif kind == "WRONG_MODE":
                        envelope["mode"] = "SHADOW"
                    target.write_text(json.dumps({**self.profile, "envelope": envelope}), encoding="utf-8")
                    result = self.invoke("check", strategy=True, expect=2, profile="bad-profile.json",
                        mode="PAPER", as_of="2026-10-05T12:40:00Z")
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertNotEqual(result["reason_code"], "OFFLINE_INPUT_SHAPE_INVALID")
            self.assertEqual(before, [hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None for path in files])

    def test_C16_missing_or_corrupt_envelope_never_ready(self):
        self.start_operating(negative=True)
        self.coordinator.tick()
        self.assertEqual(self.coordinator.status()["status"], "READY")
        with closing(sqlite3.connect(self.runner.store_path)) as writer:
            original = writer.execute("SELECT event_id,payload_json FROM execution_events WHERE event_type='ORDINARY_OPERATING_ENVELOPE_CONFIGURED'").fetchone()
            for variant, reason in (("CORRUPT", "OPERATING_ENVELOPE_INVALID"), ("MISSING", "CONFIGURATION_REQUIRED")):
                with self.subTest(variant=variant):
                    if variant == "CORRUPT":
                        writer.execute("UPDATE execution_events SET payload_json='{}' WHERE event_id=?", (original[0],))
                    else:
                        writer.execute("DELETE FROM execution_events WHERE event_id=?", (original[0],))
                    writer.commit()
                    paths = [self.runner.store_path, Path(str(self.runner.store_path)+"-wal")]
                    before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}
                    fresh = TradingCoordinator(TradingContinuityRunner(self.root,data_root=self.data), mode="PAPER", clock=lambda:self.now)
                    view = fresh.status()
                    self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}, before)
                    self.assertEqual(view["envelope"]["status"], reason)
                    self.assertEqual(view["status"], "ACTION_REQUIRED")
                    self.assertEqual(view["operating_configuration_status"], reason)
                    self.assertEqual(view["next_safe_action"], "VERIFY_OPERATING_ENVELOPE")
                    self.assertEqual(view["next_safe_command"], "readback --mode PAPER")
                    self.assertTrue(view["exit_reconciliation_healthy"])

    def test_C16_shadow_quote_inputs_are_current_readonly_health(self):
        self.start_operating(mode="SHADOW",negative=True)
        self.coordinator.tick()
        self.assertEqual(self.coordinator.status()["status"], "READY")
        funding = Path(self.profile["source"]["root"])/self.profile["quote"]["funding_observation_file"]
        original = json.loads(funding.read_text(encoding="utf-8"))
        with closing(sqlite3.connect(self.runner.store_path)) as writer:
            writer.execute("SELECT COUNT(*) FROM execution_events").fetchone()
            for variant, reason in (("MISSING", "EXECUTION_QUOTE_INPUT_NOT_PRESENT"), ("STALE", "EXECUTION_OBSERVATION_STALE_OR_FUTURE"), ("FUTURE", "EXECUTION_OBSERVATION_STALE_OR_FUTURE"), ("CORRUPT", "EXECUTION_ASSET_IDENTITY_INVALID")):
                with self.subTest(variant=variant):
                    if variant == "MISSING":
                        funding.unlink()
                    elif variant == "CORRUPT":
                        funding.write_text("null",encoding="utf-8")
                    else:
                        body = dict(original)
                        body["observed_at"] = body["available_at"] = "2026-10-05T11:00:00Z" if variant == "STALE" else "2026-10-05T12:41:00Z"
                        funding.write_text(json.dumps(body),encoding="utf-8")
                    paths = [self.runner.store_path, Path(str(self.runner.store_path)+"-wal")]
                    before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}
                    fresh = TradingCoordinator(TradingContinuityRunner(self.root,data_root=self.data), mode="SHADOW", clock=lambda:self.now)
                    view = fresh.status()
                    self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}, before)
                    self.assertEqual(view["status"], "ACTION_REQUIRED")
                    self.assertEqual(view["execution_input_status"], reason)
                    self.assertEqual(view["input_reason"], reason)
                    self.assertFalse(view["input_fresh"])
                    self.assertTrue(view["source_fresh"])
                    self.assertTrue(view["exit_reconciliation_healthy"])
                    self.assertEqual(view["next_safe_action"], "CHECK_EXECUTION_QUOTE_INPUTS")
                    self.assertEqual(view["next_safe_command"], "readback --mode SHADOW")
                    funding.write_text(json.dumps(original),encoding="utf-8")

    def test_C09_C15_C16_pause_during_live_lock_survives_restart(self):
        self.start_operating()
        def pause_and_contend():
            contention = self.invoke("run", ticks=1, as_of="2026-10-05T12:40:00Z", expect=2)
            self.assertEqual(contention["reason_code"], "ORDINARY_WRITER_ALREADY_OWNED")
            bot = self.invoke("status", as_of="2026-10-05T12:40:00Z")["instances"][0]
            (self.data / "pause-live.json").write_text(json.dumps({"command_type":"PAUSE_NEW_ENTRIES",
                "idempotency_key":"PAUSE-BEFORE-SEND", "bot_instance_id":bot["bot_instance_id"]}), encoding="utf-8")
            self.invoke("operator", input="pause-live.json")
        self.kill_at("AFTER_DECISION_COMMIT", while_blocked=pause_and_contend)
        self.invoke("run", ticks=1, as_of="2026-10-05T12:40:00Z")
        view = self.invoke("readback")
        self.assertEqual(view["positions"][0]["state"], "CANCELLED")
        self.assertEqual(view["modeled_attempts"], [])
        observer = self.invoke("status", as_of="2026-10-05T12:42:00Z")
        self.assertFalse(observer["process_alive"])
        self.assertTrue(observer["instances"][0]["entries_paused"])
        self.assertEqual(observer["status"], "ACTION_REQUIRED")

    def test_C13_captured_body_corruption_retains_unknown_no_effect(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        self.kill_at("AFTER_RESULT_CAPTURE", mode="SHADOW", ledger=ledger, plan=plan)
        store = PaperPlaneStore(self.runner.store_path)
        try:
            event = store.filtered_execution_events(event_type="ADAPTER_RESULT_CAPTURED")[0]
            body = event["payload"]
            body["result"]["unit_price_usd"] = "1"
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(body),event["event_id"]))
        finally:
            store.close()
        child = self.child(mode="SHADOW", ledger=ledger, plan=plan)
        stdout, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode,0,stderr)
        view = self.invoke("readback")
        self.assertEqual(view["positions"][0]["state"], "ATTEMPTING")
        self.assertIsNone(view["positions"][0]["qty_dec"])
        self.assertEqual(view["modeled_results"], [])
        self.assertEqual(len(self.ledger_receipts(ledger)),1)
        self.assertIn("ADAPTER_CAPTURE_INTEGRITY_CONFLICT", {incident["reason"] for incident in self.coordinator.status()["incidents"]})

    def test_C21_virtual_two_weeks_history_sizes_and_incident_bound(self):
        self.start_operating()
        self.coordinator.tick()
        self.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
        self.now = datetime(2026,10,5,13,10,tzinfo=UTC)
        self.coordinator.tick()
        store = PaperPlaneStore(self.runner.store_path)
        try:
            baseline_events = len(store.execution_events())
            measurements = []
            previous = 0
            for size in (0, 1000, 4000):
                with store.immediate_write():
                    store._conn.executemany("INSERT INTO execution_events(event_id,event_type,created_at,payload_json) VALUES (?,'SYNTHETIC_SCALE_HISTORY',?,'{}')",
                        [(f"SCALE-{number}","2026-10-01T00:00:00Z") for number in range(previous,size)])
                previous = size
                elapsed = []
                for _ in range(3):
                    before=time.perf_counter()
                    self.coordinator.tick()
                    elapsed.append(time.perf_counter()-before)
                measurements.append({"history_events":size,"tick_seconds_min":min(elapsed),
                    "tick_seconds_max":max(elapsed),"database_bytes":self.runner.store_path.stat().st_size})
            for days in range(1,15):
                self.now = datetime(2026,10,5,13,10,tzinfo=UTC) + timedelta(days=days)
                self.coordinator.tick()
            self.assertEqual(len(store.execution_events()),baseline_events+4000)
            self.assertEqual(store._conn.execute("SELECT COUNT(*) FROM ordinary_incidents WHERE incident_key='SOURCE-PAPER'").fetchone()[0],1)
            self.assertEqual(len(store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED")),2)
            self.assertLess(measurements[-1]["tick_seconds_min"],measurements[0]["tick_seconds_min"]*4+.1)
            slope=(measurements[-1]["database_bytes"]-measurements[0]["database_bytes"])/4000
            self.metrics={"virtual_days":14,"history_measurements":measurements,
                "historical_journal_bytes_per_event":slope,"owned_cleanup_verified_by_teardown":True,
                "primary_attempt_count":2,"bounded_incident_rows":1}
        finally:
            store.close()

    def test_C21_source_capacity_guard_stops_before_nomination(self):
        source = EpisodeScenario(self.data / "fortnight-capacity-stop", start=self.start,
            stops=self.start + timedelta(days=14), daily_ceiling=96)
        row = token_object(self.mint, price=.000003, liquidity=10000, holders=60)
        nominate(source.market, self.start, {"toptraded": [row], "toptrending": [row]})
        usage = shutil.disk_usage(self.data)
        disk = type(usage)(64 * 1024**3, 32 * 1024**3, 32 * 1024**3)
        with patch("solana_alpha_lab.factory.opportunity_episode_tick.shutil.disk_usage", return_value=disk):
            result = source.tick(self.start)
        self.assertEqual(result["stop_reason"], "DRAIN_RESERVE_PRESSURE")
        self.assertEqual(result["drain_headroom"]["status"], "STOP_NEW_INTAKE")
        self.assertGreater(result["drain_headroom"]["required_free_bytes"], disk.free)
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(source.admissions(), [])
        self.metrics = {"physical_capacity_fixture_free_bytes": disk.free,
            "required_free_bytes": result["drain_headroom"]["required_free_bytes"],
            "native_headroom_guard_preserved": True, "nomination_calls": 0}

    def test_C21_native_source_stream_over_virtual_two_weeks(self):
        # The source's conservative fourteen-day reserve exceeds CI disks.
        # Model only physical capacity; admission and its guard stay native.
        usage = shutil.disk_usage(self.data)
        disk = type(usage)(2 * 1024**4, 1024**4, 1024**4)
        capacity = patch("solana_alpha_lab.factory.opportunity_episode_tick.shutil.disk_usage", return_value=disk)
        capacity.start()
        self.addCleanup(capacity.stop)
        self.source = EpisodeScenario(self.data / "fortnight-source", start=self.start,
            stops=self.start + timedelta(days=14), daily_ceiling=96)
        self.start_operating()
        self.coordinator.tick()
        self.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
        self.now = datetime(2026,10,5,13,10,tzinfo=UTC)
        self.coordinator.tick()
        expected_mints={self.mint}
        durations=[]
        alphabet="abcdefghijkmnopqrstuvwxyz"
        for day in range(1,14):
            start=self.start+timedelta(days=day)
            mint=synth_mint("Day"+alphabet[day])
            expected_mints.add(mint)
            row=token_object(mint,price=.000003,liquidity=10000,holders=60)
            nominate(self.source.market,start,{"toptraded":[row],"toptrending":[row]})
            self.source.market.series[mint]=lambda now,mint=mint,start=start: token_object(mint,
                price=.0000033 if now>=start+timedelta(hours=1) else .000003,liquidity=10000,
                holders=66 if now>=start+timedelta(minutes=30) else 60)
            self.source.tick(start)
            self.source.tick(datetime(2026,10,5,12,10,tzinfo=UTC)+timedelta(days=day))
            self.source.tick(datetime(2026,10,5,12,35,tzinfo=UTC)+timedelta(days=day))
            self.now=datetime(2026,10,5,12,40,tzinfo=UTC)+timedelta(days=day)
            before=time.perf_counter()
            self.coordinator.tick()
            durations.append(time.perf_counter()-before)
            self.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC)+timedelta(days=day))
            self.now=datetime(2026,10,5,13,10,tzinfo=UTC)+timedelta(days=day)
            self.coordinator.tick()
        observer=self.invoke("readback")
        self.assertEqual({p["mint"] for p in observer["positions"]},expected_mints)
        self.assertEqual(len(observer["positions"]),14)
        self.assertEqual({p["state"] for p in observer["positions"]},{"RECONCILED"})
        self.assertEqual(len(observer["modeled_attempts"]),28)
        self.assertEqual(len({e["event_id"] for e in observer["modeled_attempts"]}),28)
        self.assertEqual(Decimal(observer["modeled_net_after_additional_costs_usd"]),Decimal("36.91"))
        disk=sum(path.stat().st_size for path in self.data.rglob("*") if path.is_file())
        self.assertLess(disk,64*1024**2)
        self.metrics={"native_stream_virtual_days":14,"source_identities":14,"stable_attempts":28,
            "source_plus_runtime_bytes":disk,"entry_tick_seconds_min":min(durations),
            "entry_tick_seconds_max":max(durations),"modeled_net_literal_oracle_usd":"36.91",
            "physical_capacity_fixture_free_bytes":1024**4,
            "native_headroom_guard_preserved":True}


if __name__ == "__main__":
    unittest.main()
