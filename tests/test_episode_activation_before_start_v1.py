"""An activation committed before ``starts_at`` keeps a reachable transition proof."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario, nominate, synth_mint, token_object
from solana_alpha_lab.factory.observation_schedule_lifecycle import activation_transition_research_event_proven
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.research_store import ResearchStore

START = datetime(2026, 10, 7, tzinfo=UTC)
ACTIVATED = START - timedelta(hours=6)
REFUSED = "TICK_REFUSED_ACTIVE_TRANSITION_PROOF_UNAVAILABLE"


class ActivationBeforeStartTests(unittest.TestCase):
    def scenario(self, *, activated_at: datetime = ACTIVATED) -> EpisodeScenario:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "rdp"
        ResearchStore(root).prepare_write_lookup()
        return EpisodeScenario(
            root, start=START, stops=START + timedelta(hours=2), activated_at=activated_at
        )

    def activation(self, sc: EpisodeScenario) -> dict:
        store = ObservationScheduleStore(sc.ops_path, readonly=True)
        try:
            return store.get_activation(sc.schedule["schedule_sha256"], sc.activation_id)
        finally:
            store.close()

    def test_pre_start_ticks_have_transition_proof_and_make_no_provider_call(self):
        sc = self.scenario()
        activation = self.activation(sc)
        self.assertEqual(activation["state"], "ACTIVE")
        self.assertGreater(activation["starts_at"], activation["created_at"])
        for offset in (timedelta(hours=-5), timedelta(hours=-1), timedelta(seconds=-1)):
            at = START + offset
            self.assertTrue(
                activation_transition_research_event_proven(sc.data_root, activation, now=at), offset
            )
            result = sc.tick(at)
            self.assertNotEqual(result["terminal"], REFUSED, (offset, result))
            self.assertEqual(result["_exit_code"], 0, (offset, result))
            self.assertEqual(result["_calls"], [], (offset, result))
        self.assertEqual(sc.admissions(), [])

    def test_ordinary_tick_continues_at_the_boundary_without_pause_or_resume(self):
        sc = self.scenario()
        mint = synth_mint("BeforeStartBoundary")
        row = token_object(mint, price=1, liquidity=10000, holders=60)
        nominate(sc.market, START, {"toporganicscore": [row], "toptraded": [], "toptrending": []})
        sc.market.series[mint] = lambda now: row
        self.assertEqual(sc.tick(START - timedelta(minutes=1))["_calls"], [])
        result = sc.tick(START + timedelta(seconds=5))
        self.assertEqual(result["_exit_code"], 0, result)
        self.assertNotEqual(result["terminal"], REFUSED, result)
        self.assertEqual(len(sc.admissions()), 1)
        self.assertEqual(self.activation(sc)["transition_sequence"], 1)

    def test_pause_then_resume_after_boundary_still_proves(self):
        sc = self.scenario()
        self.assertEqual(sc.operator(START - timedelta(hours=1), "pause")["terminal"], "PAUSED")
        self.assertEqual(sc.operator(START + timedelta(minutes=1), "resume")["terminal"], "RESUMED")
        result = sc.tick(START + timedelta(minutes=2))
        self.assertNotEqual(result["terminal"], REFUSED, result)
        self.assertEqual(result["_exit_code"], 0, result)

    def test_operator_stop_intake_before_the_boundary_keeps_its_drain_proof(self):
        sc = self.scenario()
        committed = sc.operator(START - timedelta(hours=1), "stop-intake")
        self.assertEqual(committed["terminal"], "STOP_INTAKE_COMMITTED", committed)
        result = sc.tick(START - timedelta(minutes=30))
        self.assertNotEqual(result["terminal"], "TICK_REFUSED_DRAINING_TRANSITION_PROOF_UNAVAILABLE", result)
        self.assertEqual(result["_calls"], [])

    def test_activation_at_the_boundary_is_unchanged(self):
        sc = self.scenario(activated_at=START)
        activation = self.activation(sc)
        self.assertTrue(activation_transition_research_event_proven(sc.data_root, activation, now=START))
        self.assertNotEqual(sc.tick(START + timedelta(seconds=5))["terminal"], REFUSED)

    def test_missing_or_foreign_transition_event_still_refuses(self):
        sc = self.scenario()
        connection = sqlite3.connect(sc.ops_path)
        try:
            connection.execute(
                "UPDATE schedule_activations SET last_transition_event_id = ?",
                ("OBS-TRANS-" + "0" * 64,),
            )
            connection.commit()
        finally:
            connection.close()
        activation = self.activation(sc)
        self.assertFalse(
            activation_transition_research_event_proven(sc.data_root, activation, now=START - timedelta(hours=1))
        )
        result = sc.tick(START - timedelta(hours=1))
        self.assertEqual(result["terminal"], REFUSED, result)
        self.assertEqual(result["_calls"], [])

    def test_activation_created_after_the_event_window_cannot_borrow_a_later_start(self):
        sc = self.scenario()
        activation = dict(self.activation(sc))
        activation["created_at"] = (START + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        # A row claiming a later creation than its own committed event gains nothing:
        # the proof still has to find the exact event, never infer one from the window.
        self.assertTrue(
            activation_transition_research_event_proven(sc.data_root, activation, now=START - timedelta(hours=1))
            is False
        )


if __name__ == "__main__":
    unittest.main()
