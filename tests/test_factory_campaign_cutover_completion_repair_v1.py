"""Zero-network lifecycle -> real CLI/tick -> committed completion loop."""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_observation_schedule_lifecycle import ROOT, NOW, GIT, _phrase
from solana_alpha_lab.factory.collector_read_model import project_activation_as_of
from solana_alpha_lab.factory.observation_schedule import load_observation_schedule, render_utc
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    register_schedule, authorize_schedule, activate_schedule, rollover_schedule,
    complete_draining_schedule, pause_schedule,
    _draining_transition_evidence,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.research_store import ResearchStore
from scripts.observation_schedule import main as cli_main, _tick_candidates_as_of


class _Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += timedelta(seconds=seconds)


class _EmptyProvider:
    def __init__(self, clock, crossing=None):
        self.clock = clock
        self.crossing = crossing
        self.calls = 0

    def open(self, url):
        self.calls += 1
        if self.crossing is not None:
            self.clock.now = self.crossing
        return {"http_status": 200, "body": []}


class CutoverRepairLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "rdp"
        self.data.mkdir()
        self.db = Path(self.tmp.name) / "ops.sqlite"
        self.store = ObservationScheduleStore(self.db)
        self.addCleanup(lambda: self.store.close())
        self.pred = load_observation_schedule(ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml")
        self.succ = load_observation_schedule(ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml")
        self.cutover = NOW + timedelta(minutes=10)
        for doc in (self.pred, self.succ):
            register_schedule(root=ROOT, data_root=self.data, store=self.store,
                              document=doc, now=NOW, producer_git_sha=GIT)
            authorize_schedule(root=ROOT, data_root=self.data, store=self.store,
                               schedule_sha256=doc["schedule_sha256"], phrase=_phrase(doc),
                               now=NOW, producer_git_sha=GIT)
        activate_schedule(root=ROOT, data_root=self.data, store=self.store,
                          schedule_sha256=self.pred["schedule_sha256"], activation_id="ACT-PRE",
                          now=NOW, producer_git_sha=GIT)
        rollover_schedule(root=ROOT, data_root=self.data, store=self.store,
                          predecessor_schedule_sha256=self.pred["schedule_sha256"],
                          predecessor_activation_id="ACT-PRE",
                          successor_schedule_sha256=self.succ["schedule_sha256"],
                          successor_activation_id="ACT-SUC", cutover_at=render_utc(self.cutover),
                          now=NOW, producer_git_sha=GIT)

    def row(self):
        return self.store.get_activation(self.pred["schedule_sha256"], "ACT-PRE")

    def complete(self, now):
        return complete_draining_schedule(data_root=self.data, store=self.store,
            schedule_sha256=self.pred["schedule_sha256"], activation_id="ACT-PRE",
            now=now, producer_git_sha=GIT)

    def cli_tick(self, now, crossing=None):
        # Only physical dependencies are substituted. Selection, immutable proof,
        # authority, tick, source accounting and persistence are production code.
        clock = _Clock(now)
        provider = _EmptyProvider(clock, crossing)
        config = {"producer_git_sha": GIT}
        output = StringIO()
        with (
            patch("scripts.observation_schedule.load_runtime_config", return_value=config),
            patch("scripts.observation_schedule.resolve_clock", return_value=now),
            patch("scripts.observation_schedule._bind_runtime", return_value=(config, self.data, self.store)),
            patch("scripts.observation_schedule.git_sha", return_value=GIT),
            patch("scripts.observation_schedule.materialize_tick_physical_dependencies",
                  return_value=SimpleNamespace(opener=provider, credential_loader=lambda: "fixture-only",
                                               pacing_clock=clock)),
            redirect_stdout(output),
        ):
            code = cli_main(["tick", "--once"])
        # CLI closes its own store; reopen to model a fresh process each tick.
        self.store = ObservationScheduleStore(self.db)
        self.assertEqual(code, 0, output.getvalue())
        return json.loads(output.getvalue()), provider

    def test_empty_queue_cannot_complete_before_future_cutover(self):
        before = self.row()
        self.assertEqual(project_activation_as_of(before, NOW)["state"], "ACTIVE")
        result = self.complete(NOW)
        self.assertEqual(result["terminal"], "DRAINING_PENDING")
        self.assertEqual(self.row(), before)

    def test_real_cli_source_poll_restart_and_spanning_tick(self):
        for offset in (0, 60, 120):
            result, provider = self.cli_tick(NOW + timedelta(seconds=offset))
            self.assertGreater(provider.calls, 0)
            self.assertEqual(result["activation_id"], "ACT-PRE")
            self.assertEqual(self.row()["state"], "DRAINING")
            self.assertEqual(project_activation_as_of(self.row(), NOW)["state"], "ACTIVE")
        seq = self.row()["transition_sequence"]
        result, provider = self.cli_tick(self.cutover - timedelta(seconds=1),
                                         self.cutover + timedelta(seconds=10))
        self.assertGreater(provider.calls, 0)
        self.assertEqual(result["activation_id"], "ACT-PRE")
        self.assertEqual(self.row()["transition_sequence"], seq)
        candidates = _tick_candidates_as_of(self.store.list_activations(), self.cutover)
        self.assertIn((self.succ["schedule_sha256"], "ACT-SUC"), candidates)
        self.assertEqual(sum(project_activation_as_of(r, self.cutover)["state"] == "ACTIVE"
                             for r in self.store.list_activations()), 1)
        result, provider = self.cli_tick(self.cutover)
        self.assertGreater(provider.calls, 0)
        successor_result = next(r for r in result["activations"] if r["activation_id"] == "ACT-SUC")
        self.assertEqual(successor_result["activation_state"], "ACTIVE")

    def test_effective_early_cutover_obligations_and_single_committed_complete(self):
        # The cutover is hours earlier than the original admission stop.
        due = dict(schedule_sha256=self.pred["schedule_sha256"], activation_id="ACT-PRE",
                   entity_id="MintFixture", point_id="X300",
                   primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001", state="PENDING",
                   due_at=render_utc(self.cutover), deadline_at=render_utc(self.cutover + timedelta(minutes=5)),
                   payload={})
        for state in ("PENDING", "DUE", "CLAIMED"):
            self.store.insert_due({**due, "state": state}, clock=self.cutover)
            self.assertEqual(self.complete(self.cutover)["terminal"], "DRAINING_PENDING")
        self.store.insert_due({**due, "state": "CENSORED"}, clock=self.cutover)
        with patch("solana_alpha_lab.factory.observation_schedule_lifecycle.has_open_publication_jobs", return_value=True):
            self.assertEqual(self.complete(self.cutover)["terminal"], "DRAINING_PENDING")
        seq = self.row()["transition_sequence"]
        completed = self.complete(self.cutover)
        self.assertEqual(completed["terminal"], "COMPLETED")
        self.assertEqual(self.row()["transition_sequence"], seq + 1)
        self.assertEqual(self.complete(self.cutover)["terminal"], "COMPLETE_REPLAY")
        self.assertEqual(self.row()["transition_sequence"], seq + 1)
        records = ResearchStore(self.data).iter_committed_records()
        events = [r for r in records if r.record_id == completed["transition_event_id"]]
        self.assertEqual(len(events), 1)
        self.assertEqual(json.loads(events[0].payload_json)["state"], "COMPLETE")

    def test_missing_or_uncommitted_proof_never_mutates(self):
        # Corrupt only the temporary mutable projection: this event is absent
        # from the immutable store, even though the raw row claims DRAINING.
        self.store._conn.execute("UPDATE schedule_activations SET last_transition_event_id=? WHERE activation_id=?",
                                 ("OBS-TRANS-" + "0" * 64, "ACT-PRE"))
        self.store._conn.commit()
        before = self.row()
        self.assertEqual(self.complete(self.cutover)["terminal"], "DRAINING_PROOF_UNKNOWN")
        self.assertEqual(self.row(), before)

    def test_unresolved_due_and_restore_marker_hold_completion(self):
        for state in ("IN_FLIGHT_CALL_INDETERMINATE", "BLOCKED_BUDGET"):
            with self.subTest(state=state):
                self.store.insert_due(dict(schedule_sha256=self.pred["schedule_sha256"],
                    activation_id="ACT-PRE", entity_id=state, point_id="X300",
                    primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001", state=state,
                    due_at=render_utc(self.cutover), deadline_at=render_utc(self.cutover + timedelta(minutes=5)),
                    payload={}), clock=self.cutover)
                before = self.row()
                self.assertEqual(self.complete(self.cutover)["terminal"], "DRAINING_PENDING")
                self.assertEqual(self.row(), before)

    def test_restore_marker_holds_empty_queue(self):
        self.store.set_restore_marker("FIXTURE-UNRESOLVED", clock=self.cutover)
        before = self.row()
        self.assertEqual(self.complete(self.cutover)["terminal"], "DRAINING_PENDING")
        self.assertEqual(self.row(), before)

    def test_coherent_sequence_drift_is_unknown(self):
        row = self.row()
        self.store._conn.execute("UPDATE schedule_activations SET transition_sequence=?, payload_json=? WHERE activation_id=?",
            (999, json.dumps({**row["payload"], "transition_sequence": 999}), "ACT-PRE"))
        self.store._conn.commit()
        before = self.row()
        self.assertEqual(self.complete(self.cutover)["terminal"], "DRAINING_PROOF_UNKNOWN")
        self.assertEqual(self.row(), before)

    def test_coherent_authority_drift_is_unknown(self):
        row = self.row()
        self.store._conn.execute("UPDATE schedule_activations SET authority_receipt_sha256=?, payload_json=? WHERE activation_id=?",
            ("0" * 64, json.dumps({**row["payload"], "authority_receipt_sha256": "0" * 64}), "ACT-PRE"))
        self.store._conn.commit()
        before = self.row()
        self.assertEqual(self.complete(self.cutover)["terminal"], "DRAINING_PROOF_UNKNOWN")
        self.assertEqual(self.row(), before)

    def test_completion_proof_never_opens_growing_member_history(self):
        manifests = ResearchStore(self.data)._committed_manifests()
        event_id = self.row()["last_transition_event_id"]
        expected = "RESEARCH-TXN-" + event_id.upper()
        verify = ResearchStore._verify_partition
        for size in (10, 200):
            opened = []
            history = [manifests[0].model_copy(update={"partition_id": "RESEARCH-TXN-OBS-MEMB-" + str(i)})
                       for i in range(size)]
            def guarded_verify(research, manifest):
                opened.append(manifest.partition_id)
                self.assertEqual(manifest.partition_id, expected)
                return verify(research, manifest)
            with (
                patch.object(ResearchStore, "_committed_manifests", return_value=tuple(manifests) + tuple(history)),
                patch.object(ResearchStore, "_verify_partition", guarded_verify),
            ):
                self.assertIsNotNone(_draining_transition_evidence(self.data, self.row(),
                                      now=self.cutover, exact_transition=True))
            self.assertEqual(opened, [expected])

    def test_malformed_proof_never_mutates(self):
        original = self.row()["payload"]
        for field, value in (("transition_effective_at", "invalid"),
                             ("transition_sequence", 999)):
            with self.subTest(field=field):
                self.store._conn.execute("UPDATE schedule_activations SET payload_json=? WHERE activation_id=?",
                    (json.dumps({**original, field: value}), "ACT-PRE"))
                self.store._conn.commit()
                before = self.row()
                self.assertEqual(self.complete(self.cutover)["terminal"], "DRAINING_PROOF_UNKNOWN")
                self.assertEqual(self.row(), before)

    def test_paused_future_successor_stays_paused_at_boundary(self):
        pause_schedule(data_root=self.data, store=self.store,
            schedule_sha256=self.succ["schedule_sha256"], activation_id="ACT-SUC",
            now=NOW, producer_git_sha=GIT)
        candidates = _tick_candidates_as_of(self.store.list_activations(), self.cutover)
        self.assertNotIn((self.succ["schedule_sha256"], "ACT-SUC"), candidates)
        self.assertEqual(self.store.get_activation(self.succ["schedule_sha256"], "ACT-SUC")["state"], "PAUSED_OPERATOR")


if __name__ == "__main__":
    unittest.main()
