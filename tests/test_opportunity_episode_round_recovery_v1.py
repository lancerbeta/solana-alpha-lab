"""OPPORTUNITY_EPISODE_ROUND_CRASH_RECOVERY_V1 adversarial proofs.

A process crash inside a nomination round must never let timing change the
scientific sample. Only the transport, clock and vendor bytes are synthetic;
every transition goes through the production tick entry, the store owner and
the release maturity gate.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from solana_alpha_lab.factory.live_cohort_discovery_release import LiveCohortReleaseError  # noqa: E402
from solana_alpha_lab.factory.observation_schedule import canonical_sha256  # noqa: E402
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.opportunity_episode_release import (  # noqa: E402
    _cohort_status,
    assert_episode_closure_ready,
    build_episode_closure_receipt,
    capture_freeze_export_episodes,
    select_next_mature_episode_cohort,
)
from solana_alpha_lab.factory.opportunity_episodes import (  # noqa: E402
    classify_round_recovery,
    round_id as episode_round_id,
)
from tests.test_opportunity_episodes_harness_v1 import (  # noqa: E402
    EpisodeScenario,
    nominate,
    synth_mint,
    token_object,
)

S = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
# Round index 23 of a 100/day ceiling has quota 2 (k_j = floor(100(j+1)/96) - floor(100j/96)).
R = S + timedelta(hours=5, minutes=45)
AFTER_SLACK = R + timedelta(seconds=300)
PASS = dict(price=1.0, liquidity=10000, holders=60)


def obj(mint: str):
    return token_object(mint, **PASS)


def category_calls(result: dict) -> list[dict]:
    return [call for call in result["_calls"] if call["kind"] == "category"]


class RoundRecoveryCase(unittest.TestCase):
    def scenario(self, *, ceiling: int = 100, round_start: datetime = R, labels=("A", "B", "C")):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sc = EpisodeScenario(Path(tmp.name) / "rdp", start=S, stops=S + timedelta(days=3), daily_ceiling=ceiling)
        self.mints = [synth_mint(label) for label in labels]
        self.round_start = round_start
        nominate(sc.market, round_start, {"toporganicscore": [obj(m) for m in self.mints], "toptraded": [], "toptrending": []})
        for mint in self.mints:
            sc.market.series[mint] = lambda _now, mint=mint: obj(mint)
        return sc

    def rid(self, sc) -> str:
        return episode_round_id(sc.activation_id, self.round_start)

    def round_row(self, sc, rid: str | None = None) -> dict:
        wanted = rid or self.rid(sc)
        return next(item for item in sc.rounds() if item["round_id"] == wanted)

    def write(self, sc, sql: str, params: tuple = ()) -> None:
        connection = sqlite3.connect(sc.ops_path)
        try:
            connection.execute(sql, params)
            connection.commit()
        finally:
            connection.close()

    def drain_slots(self, sc) -> None:
        self.write(sc, "UPDATE due_observations SET state='CENSORED' WHERE state IN ('PENDING','DUE','CLAIMED')")

    def cohort_status(self, sc, cohort_id: str | None = None) -> dict:
        store = ObservationScheduleStore(sc.ops_path)
        try:
            activation = store.list_activations()[0]
            return _cohort_status(
                store,
                data_root=sc.data_root,
                schedule_sha256=str(activation["schedule_sha256"]),
                activation_id=str(activation["activation_id"]),
                cohort_id=cohort_id or sc.admissions()[0]["cohort_id"],
                as_of=S + timedelta(days=2),
            )
        finally:
            store.close()

    def crash_after_first_admission(self, sc) -> dict:
        crashed = sc.tick(R + timedelta(seconds=5), fault="EPISODE_AFTER_ADMISSION_COMMIT")
        self.assertNotEqual(crashed["_exit_code"], 0)
        self.assertEqual(len(sc.admissions()), 1)
        self.assertEqual(self.round_row(sc)["state"], "STARTED")
        return self.round_row(sc)["frame"]["recovery_plan"]


class RoundPlanBeforeAdmissionTests(RoundRecoveryCase):
    def test_plan_is_durable_before_the_first_admission_and_pins_the_winners(self) -> None:
        sc = self.scenario()
        crashed = sc.tick(R + timedelta(seconds=5), fault="EPISODE_BEFORE_ADMISSION_COMMIT")
        self.assertNotEqual(crashed["_exit_code"], 0)
        self.assertEqual(sc.admissions(), [])
        plan = self.round_row(sc)["frame"]["recovery_plan"]
        self.assertEqual(len(plan["winners"]), 2)
        self.assertEqual(plan["basis"]["quota"], 2)
        self.assertEqual(plan["basis"]["round_quota"], 2)
        self.assertEqual(plan["frame_sha256"], plan["frame_receipt"]["frame_sha256"])
        self.assertEqual(plan["plan_sha256"], canonical_sha256({k: v for k, v in plan.items() if k != "plan_sha256"}))
        self.assertEqual(len(plan["not_selected"]), 1)
        self.assertEqual(sorted([item["mint"] for item in plan["winners"]] + plan["not_selected"]), sorted(self.mints))

    def test_normal_round_is_unchanged_and_names_its_plan(self) -> None:
        sc = self.scenario()
        sc.tick(R + timedelta(seconds=5))
        row = self.round_row(sc)
        self.assertEqual(row["state"], "CLOSED")
        frame = row["frame"]
        self.assertEqual(len(frame["selection"]["admitted_episode_ids"]), 2)
        self.assertEqual(frame["selection"]["committed_in_round_before"], 0)
        self.assertEqual(frame["selection"]["dropped_planned"], [])
        self.assertEqual(frame["selection"]["committed_episode_ids"], frame["selection"]["admitted_episode_ids"])
        self.assertFalse(frame["recovery"]["resumed"])
        self.assertEqual(frame["recovery"]["planned_episode_ids"], frame["selection"]["admitted_episode_ids"])
        self.assertNotIn("recovery_plan", frame)
        self.drain_slots(sc)
        status = self.cohort_status(sc)
        self.assertEqual((status["mature"], status["blocking_reasons"], status["round_gaps"]), (True, [], []))


class RestartInsideSlackTests(RoundRecoveryCase):
    def test_resume_inside_slack_completes_exactly_the_planned_winners(self) -> None:
        sc = self.scenario()
        plan = self.crash_after_first_admission(sc)
        first = sc.admissions()[0]
        resumed = sc.tick(R + timedelta(seconds=40))
        self.assertEqual(category_calls(resumed), [])
        row = self.round_row(sc)
        self.assertEqual(row["state"], "CLOSED")
        admitted = sorted(item["episode_id"] for item in sc.admissions())
        self.assertEqual(admitted, sorted(item["episode_id"] for item in plan["winners"]))
        self.assertEqual(sc.admissions()[0]["episode_id"], first["episode_id"])
        self.assertEqual(row["frame"]["recovery"]["plan_sha256"], plan["plan_sha256"])
        self.assertTrue(row["frame"]["recovery"]["resumed"])
        self.assertEqual(row["frame"]["selection"]["committed_in_round_before"], 1)
        self.assertEqual(len(row["frame"]["selection"]["admitted_episode_ids"]), 1)  # this run's commits
        self.assertEqual(
            row["frame"]["selection"]["committed_episode_ids"], [item["episode_id"] for item in plan["winners"]]
        )
        self.assertEqual(row["frame"]["selection"]["dropped_planned"], [])
        self.drain_slots(sc)
        self.assertTrue(self.cohort_status(sc)["mature"])

    def test_resume_from_a_durable_plan_with_no_committed_admission_completes_it(self) -> None:
        sc = self.scenario()
        sc.tick(R + timedelta(seconds=5), fault="EPISODE_BEFORE_ADMISSION_COMMIT")
        plan = self.round_row(sc)["frame"]["recovery_plan"]
        resumed = sc.tick(R + timedelta(seconds=40))
        self.assertEqual(category_calls(resumed), [])
        row = self.round_row(sc)
        self.assertEqual(row["state"], "CLOSED")
        self.assertEqual(
            sorted(item["episode_id"] for item in sc.admissions()), sorted(item["episode_id"] for item in plan["winners"])
        )
        self.assertEqual(row["frame"]["selection"]["committed_in_round_before"], 0)

    def test_resume_that_drops_a_planned_winner_is_a_partial_admission_with_the_reason(self) -> None:
        sc = self.scenario()
        plan = self.crash_after_first_admission(sc)
        first = sc.admissions()[0]
        dropped = next(item for item in plan["winners"] if item["episode_id"] != first["episode_id"])
        # Another round already holds the second planned mint this cycle: the commit refuses it.
        self.write(
            sc,
            "INSERT INTO episode_admissions SELECT 'EP-OTHER', schedule_sha256, activation_id, lineage_id, cycle_start, ?, "
            "t0, cohort_id, final_deadline_at, ?, record_json, 'OTHER-ROUND', created_at FROM episode_admissions WHERE episode_id = ?",
            (dropped["mint"], "9" * 64, first["episode_id"]),
        )
        sc.tick(R + timedelta(seconds=40))
        row = self.round_row(sc)
        self.assertEqual((row["state"], row["frame"]["terminal"]), ("INCOMPLETE", "ROUND_RECOVERY_PARTIAL_ADMISSION"))
        self.assertEqual(
            row["frame"]["recovery"]["dropped_planned"],
            [{"episode_id": dropped["episode_id"], "mint": dropped["mint"], "reason": "MINT_BLOCKED"}],
        )
        self.assertEqual(
            [r[0] for r in sc.query("SELECT episode_id FROM episode_admissions WHERE round_id = ?", (self.rid(sc),))],
            [first["episode_id"]],
        )
        self.drain_slots(sc)
        status = self.cohort_status(sc, first["cohort_id"])
        self.assertIn("ROUND_PARTIAL_ADMISSION", status["blocking_reasons"])

    def test_resume_follows_the_plan_even_when_the_market_would_choose_differently(self) -> None:
        sc = self.scenario()
        plan = self.crash_after_first_admission(sc)
        # A recomputing resume would see a different frame; the plan is followed or refused, never replaced.
        sc.market.nominations[R] = {"toporganicscore": [obj(synth_mint("Z1")), obj(synth_mint("Z2"))], "toptraded": [], "toptrending": []}
        sc.tick(R + timedelta(seconds=40))
        self.assertEqual(
            sorted(item["episode_id"] for item in sc.admissions()),
            sorted(item["episode_id"] for item in plan["winners"]),
        )


class RestartAfterSlackTests(RoundRecoveryCase):
    def test_crash_before_any_admission_terminalizes_without_calls_or_late_admissions(self) -> None:
        sc = self.scenario()
        sc.tick(R + timedelta(seconds=5), fault="EPISODE_BEFORE_ADMISSION_COMMIT")
        plan = self.round_row(sc)["frame"]["recovery_plan"]
        late = sc.tick(AFTER_SLACK)
        self.assertEqual(category_calls(late), [])
        self.assertEqual(sc.admissions(), [])
        row = self.round_row(sc)
        self.assertEqual(row["state"], "INCOMPLETE")
        self.assertEqual(row["frame"]["terminal"], "ROUND_RECOVERY_NO_ADMISSION")
        self.assertEqual(row["frame"]["recovery"]["reason_code"], "ROUND_CRASH_BEFORE_ADMISSION")
        self.assertEqual(row["frame"]["recovery"]["missing_episode_ids"], [item["episode_id"] for item in plan["winners"]])
        self.assertEqual(row["frame"]["recovery_plan"], plan)
        self.assertEqual(row["frame"]["frame_sha256"], plan["frame_sha256"])
        again = sc.tick(AFTER_SLACK + timedelta(seconds=60))
        self.assertEqual((category_calls(again), sc.admissions()), ([], []))
        self.assertEqual(self.round_row(sc), row)

    def test_crash_before_the_plan_exists_is_an_honest_gap(self) -> None:
        sc = self.scenario()
        crashed = sc.tick(R + timedelta(seconds=2), fault="EPISODE_AFTER_CALL_COMPLETE")
        self.assertNotEqual(crashed["_exit_code"], 0)
        row = self.round_row(sc)
        self.assertEqual((row["state"], "recovery_plan" in row["frame"]), ("STARTED", False))
        sc.tick(AFTER_SLACK)
        row = self.round_row(sc)
        self.assertEqual((row["state"], row["frame"]["terminal"]), ("INCOMPLETE", "ROUND_RECOVERY_NO_ADMISSION"))
        self.assertEqual(row["frame"]["recovery"]["reason_code"], "ROUND_PLAN_NOT_WRITTEN")
        self.assertEqual(sc.admissions(), [])

    def test_zero_admission_gap_does_not_kill_a_cohort_with_unambiguous_provenance(self) -> None:
        sc = self.scenario()
        sc.tick(R + timedelta(seconds=5), fault="EPISODE_BEFORE_ADMISSION_COMMIT")
        sc.tick(AFTER_SLACK)
        later = R + timedelta(minutes=15)
        nominate(sc.market, later, {"toporganicscore": [obj(m) for m in self.mints], "toptraded": [], "toptrending": []})
        sc.tick(later + timedelta(seconds=5))
        self.assertEqual(len(sc.admissions()), 1)  # the next round's own quota, never the lost round's
        self.drain_slots(sc)
        status = self.cohort_status(sc)
        self.assertEqual((status["mature"], status["blocking_reasons"], status["round_gaps"]), (True, [], []))
        receipt = build_episode_closure_receipt(
            ops_store=sc.ops_path,
            observation_rdp=sc.data_root,
            schedule_sha256=sc.schedule["schedule_sha256"],
            activation_id=sc.activation_id,
            cohort_id=sc.admissions()[0]["cohort_id"],
            as_of=S + timedelta(days=2),
        )
        assert_episode_closure_ready(receipt)
        states = {item["round_id"][-16:]: item["state"] for item in receipt["rounds"]}
        self.assertEqual(sorted(states.values()), ["CLOSED", "INCOMPLETE"])

    def test_partial_admission_preserves_committed_and_never_admits_late(self) -> None:
        sc = self.scenario()
        plan = self.crash_after_first_admission(sc)
        committed = sc.admissions()[0]
        late = sc.tick(AFTER_SLACK)
        self.assertEqual(category_calls(late), [])
        self.assertEqual(sc.admissions(), [committed])
        row = self.round_row(sc)
        self.assertEqual((row["state"], row["frame"]["terminal"]), ("INCOMPLETE", "ROUND_RECOVERY_PARTIAL_ADMISSION"))
        recovery = row["frame"]["recovery"]
        self.assertEqual(recovery["reason_code"], "ROUND_PARTIAL_ADMISSION")
        self.assertEqual(recovery["committed_episode_ids"], [committed["episode_id"]])
        self.assertEqual(recovery["missing_episode_ids"], [item["episode_id"] for item in plan["winners"] if item["episode_id"] != committed["episode_id"]])
        self.assertEqual(row["frame"]["recovery_plan"], plan)
        self.drain_slots(sc)
        status = self.cohort_status(sc)
        self.assertFalse(status["mature"])
        self.assertEqual(status["blocking_reasons"], ["ROUND_PARTIAL_ADMISSION"])
        self.assertEqual([gap["round_id"] for gap in status["round_gaps"]], [self.rid(sc)])
        # Capture and closure refuse; no later round can clean the gap away.
        later = R + timedelta(minutes=15)
        nominate(sc.market, later, {"toporganicscore": [obj(m) for m in self.mints], "toptraded": [], "toptrending": []})
        sc.tick(later + timedelta(seconds=5))
        self.drain_slots(sc)
        self.assertFalse(self.cohort_status(sc)["mature"])
        chosen = select_next_mature_episode_cohort(
            ops_store=sc.ops_path, observation_rdp=sc.data_root, imported=set(), as_of=S + timedelta(days=2)
        )
        self.assertEqual(chosen["terminal"], "NO_MATURE_UNIMPORTED_COHORT")
        self.assertIn("ROUND_PARTIAL_ADMISSION", chosen["pending"][0]["blocking_reasons"])
        with self.assertRaises(LiveCohortReleaseError) as raised:
            capture_freeze_export_episodes(
                observation_rdp=sc.data_root, ops_store=sc.ops_path, imported_cohort_ids=set(), as_of=S + timedelta(days=2)
            )
        self.assertIn("NO_MATURE_UNIMPORTED_COHORT", str(raised.exception))
        receipt = build_episode_closure_receipt(
            ops_store=sc.ops_path, observation_rdp=sc.data_root, schedule_sha256=sc.schedule["schedule_sha256"],
            activation_id=sc.activation_id, cohort_id=committed["cohort_id"], as_of=S + timedelta(days=2),
        )
        self.assertFalse(receipt["closure_ready"])
        with self.assertRaises(Exception) as refused:
            assert_episode_closure_ready(receipt)
        self.assertIn("ROUND_PARTIAL_ADMISSION", str(refused.exception))

    def test_crash_after_every_planned_admission_closes_the_exact_round(self) -> None:
        sc = self.scenario(ceiling=96)  # quota 1: the single planned winner commits, then the process dies
        plan = self.crash_after_first_admission(sc)
        self.assertEqual(len(plan["winners"]), 1)
        committed = sc.admissions()[0]
        late = sc.tick(AFTER_SLACK)
        self.assertEqual(category_calls(late), [])
        self.assertEqual(sc.admissions(), [committed])
        row = self.round_row(sc)
        self.assertEqual(row["state"], "CLOSED")
        recovery = row["frame"]["recovery"]
        self.assertEqual((recovery["outcome"], recovery["reconciled_after_slack"]), ("CLOSED", True))
        self.assertEqual(recovery["plan_sha256"], plan["plan_sha256"])
        self.assertEqual(row["frame"]["frame_sha256"], plan["frame_sha256"])
        self.assertEqual(row["frame"]["selection"]["admitted_episode_ids"], [])
        self.assertEqual(row["frame"]["selection"]["committed_episode_ids"], [committed["episode_id"]])
        self.assertEqual(row["frame"]["recovery"]["basis"], plan["basis"])
        self.drain_slots(sc)
        self.assertTrue(self.cohort_status(sc)["mature"])

    def test_unresolved_started_round_is_never_mature(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        self.drain_slots(sc)
        status = self.cohort_status(sc)
        self.assertFalse(status["mature"])
        self.assertIn("ROUND_STARTED_UNRESOLVED", status["blocking_reasons"])
        self.assertEqual(status["round_gaps"][0]["state"], "STARTED")


class RefusedEvidenceTests(RoundRecoveryCase):
    def refused(self, sc, code: str) -> dict:
        late = sc.tick(AFTER_SLACK)
        self.assertEqual(category_calls(late), [])
        row = self.round_row(sc)
        self.assertEqual((row["state"], row["frame"]["terminal"]), ("INCOMPLETE", "ROUND_RECOVERY_REFUSED"))
        self.assertEqual(row["frame"]["recovery"]["reason_code"], code)
        self.drain_slots(sc)
        status = self.cohort_status(sc)
        self.assertFalse(status["mature"])
        self.assertEqual(status["blocking_reasons"], ["ROUND_RECOVERY_REFUSED"])
        return row

    def tamper_plan(self, sc, mutate, *, rehash: bool) -> dict:
        row = self.round_row(sc)
        frame = row["frame"]
        mutate(frame["recovery_plan"])
        if rehash:
            plan = frame["recovery_plan"]
            plan["plan_sha256"] = canonical_sha256({k: v for k, v in plan.items() if k != "plan_sha256"})
        self.write(sc, "UPDATE episode_rounds SET frame_json = ? WHERE round_id = ?", (json.dumps(frame, sort_keys=True), row["round_id"]))
        return frame["recovery_plan"]

    def test_corrupt_plan_hash_is_refused_and_committed_admissions_stay(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        committed = sc.admissions()
        tampered = self.tamper_plan(sc, lambda plan: plan["winners"].reverse(), rehash=False)
        row = self.refused(sc, "ROUND_PLAN_HASH_MISMATCH")
        self.assertEqual(sc.admissions(), committed)
        self.assertEqual(row["frame"]["recovery_plan"], tampered)  # retained verbatim, never healed

    def test_self_consistent_but_wrong_selection_is_refused(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        self.tamper_plan(sc, lambda plan: plan["winners"].reverse(), rehash=True)
        self.refused(sc, "ROUND_PLAN_SELECTION_MISMATCH")

    def test_frame_identity_conflict_is_refused(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        self.tamper_plan(sc, lambda plan: plan["frame_receipt"]["counts"].update(received=999), rehash=True)
        self.refused(sc, "ROUND_PLAN_FRAME_IDENTITY_MISMATCH")

    def test_plan_removed_while_admissions_exist_is_refused(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        rid = self.rid(sc)
        self.write(sc, "UPDATE episode_rounds SET frame_json = ? WHERE round_id = ?", (json.dumps({"round_id": rid}), rid))
        self.refused(sc, "ROUND_PLAN_MISSING_WITH_ADMISSIONS")
        self.assertEqual(len(sc.admissions()), 1)

    def test_unreadable_round_frame_is_refused_with_its_digest(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        self.write(sc, "UPDATE episode_rounds SET frame_json = ? WHERE round_id = ?", ("{not json", self.rid(sc)))
        row = self.refused(sc, "ROUND_FRAME_CORRUPT")
        self.assertEqual(len(row["frame"]["prior_frame_json_sha256"]), 64)

    def test_missing_call_evidence_is_refused(self) -> None:
        sc = self.scenario()
        plan = self.crash_after_first_admission(sc)
        occurrence = plan["frame_receipt"]["sources"][0]["call_occurrence_id"]
        self.write(sc, "DELETE FROM call_ledger WHERE call_occurrence_id = ?", (occurrence,))
        self.refused(sc, "ROUND_CALL_EVIDENCE_MISSING")

    def test_admission_that_does_not_match_the_plan_is_refused(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        record = sc.admissions()[0]
        record["frame_sha256"] = "0" * 64
        self.write(sc, "UPDATE episode_admissions SET record_json = ?", (json.dumps(record, sort_keys=True),))
        self.refused(sc, "ROUND_ADMISSION_PLAN_CONFLICT")

    def test_corrupt_plan_inside_slack_is_refused_before_any_admission(self) -> None:
        sc = self.scenario()
        sc.tick(R + timedelta(seconds=5), fault="EPISODE_BEFORE_ADMISSION_COMMIT")
        self.tamper_plan(sc, lambda plan: plan["winners"].reverse(), rehash=False)
        resumed = sc.tick(R + timedelta(seconds=40))
        self.assertEqual(category_calls(resumed), [])
        self.assertEqual(sc.admissions(), [])
        row = self.round_row(sc)
        self.assertEqual((row["state"], row["frame"]["recovery"]["reason_code"]), ("INCOMPLETE", "ROUND_PLAN_HASH_MISMATCH"))


class UnreadableOwnerEvidenceTests(RoundRecoveryCase):
    def test_corrupt_terminal_round_frame_blocks_the_cohort_and_closure(self) -> None:
        for terminal_setup in ("CLOSED", "PARTIAL"):
            with self.subTest(terminal_setup):
                sc = self.scenario()
                if terminal_setup == "CLOSED":
                    sc.tick(R + timedelta(seconds=5))
                else:
                    self.crash_after_first_admission(sc)
                    sc.tick(AFTER_SLACK)
                self.write(sc, "UPDATE episode_rounds SET frame_json = ? WHERE round_id = ?", ("{not json", self.rid(sc)))
                self.drain_slots(sc)
                status = self.cohort_status(sc)
                self.assertFalse(status["mature"])
                self.assertIn("ROUND_FRAME_CORRUPT", status["blocking_reasons"])
                receipt = build_episode_closure_receipt(
                    ops_store=sc.ops_path, observation_rdp=sc.data_root, schedule_sha256=sc.schedule["schedule_sha256"],
                    activation_id=sc.activation_id, cohort_id=sc.admissions()[0]["cohort_id"], as_of=S + timedelta(days=2),
                )
                self.assertFalse(receipt["closure_ready"])

    def test_admission_without_its_round_owner_row_blocks_the_cohort(self) -> None:
        sc = self.scenario()
        sc.tick(R + timedelta(seconds=5))
        self.write(sc, "DELETE FROM episode_rounds WHERE round_id = ?", (self.rid(sc),))
        self.drain_slots(sc)
        status = self.cohort_status(sc)
        self.assertFalse(status["mature"])
        self.assertEqual(status["blocking_reasons"], ["ROUND_ROW_MISSING"])

    def test_missing_call_evidence_inside_slack_is_refused_before_any_admission(self) -> None:
        sc = self.scenario()
        sc.tick(R + timedelta(seconds=5), fault="EPISODE_BEFORE_ADMISSION_COMMIT")
        plan = self.round_row(sc)["frame"]["recovery_plan"]
        self.write(sc, "DELETE FROM call_ledger WHERE call_occurrence_id = ?", (plan["frame_receipt"]["sources"][0]["call_occurrence_id"],))
        resumed = sc.tick(R + timedelta(seconds=40))
        self.assertEqual((category_calls(resumed), sc.admissions()), ([], []))
        row = self.round_row(sc)
        self.assertEqual(row["frame"]["recovery"]["reason_code"], "ROUND_CALL_EVIDENCE_MISSING")

    def test_unreadable_call_ledger_payload_is_a_typed_refusal_not_a_tick_abort(self) -> None:
        sc = self.scenario()
        plan = self.crash_after_first_admission(sc)
        occurrence = plan["frame_receipt"]["sources"][0]["call_occurrence_id"]
        self.write(sc, "UPDATE call_ledger SET payload_json = ? WHERE call_occurrence_id = ?", ("{not json", occurrence))
        late = sc.tick(AFTER_SLACK)
        self.assertEqual(late["_exit_code"], 0)
        self.assertEqual(self.round_row(sc)["frame"]["recovery"]["reason_code"], "ROUND_CALL_EVIDENCE_MISSING")


class StoreOwnerGuardTests(RoundRecoveryCase):
    def open_store(self, sc):
        store = ObservationScheduleStore(sc.ops_path)
        self.addCleanup(store.close)
        store.acquire_lease("guard-test", clock=R + timedelta(seconds=60))
        return store

    def attempt(self, store, episode_id: str, round_id: str):
        record = {
            "episode_id": episode_id, "schedule_sha256": "aa" * 32, "activation_id": "ACT",
            "collection_lineage_id": "LIN", "cycle_start": "2026-10-05T00:00:00Z", "mint": "M",
            "t0": "2026-10-05T05:46:00Z", "cohort_id": "REL-X", "round_id": round_id,
        }
        return store.commit_episode_admission(
            record=record, content_sha256="1" * 64, final_deadline_at="2026-10-06T00:00:00Z",
            due_rows=[], outbox_rows=[], clock=R + timedelta(seconds=60),
        )

    def test_terminal_round_refuses_any_late_admission(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        sc.tick(AFTER_SLACK)
        store = self.open_store(sc)
        with self.assertRaises(ObservationScheduleStoreError) as raised:
            self.attempt(store, "EP-LATE", self.rid(sc))
        self.assertEqual(str(raised.exception), "EPISODE_ADMISSION_ROUND_NOT_OPEN")
        self.assertEqual(len(sc.admissions()), 1)

    def test_started_round_refuses_an_unplanned_episode(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        store = self.open_store(sc)
        with self.assertRaises(ObservationScheduleStoreError) as raised:
            self.attempt(store, "EP-NOT-IN-PLAN", self.rid(sc))
        self.assertEqual(str(raised.exception), "EPISODE_ADMISSION_NOT_PLANNED")

    def test_started_round_without_a_plan_refuses_any_admission(self) -> None:
        sc = self.scenario()
        sc.tick(R + timedelta(seconds=2), fault="EPISODE_AFTER_CALL_COMPLETE")
        store = self.open_store(sc)
        with self.assertRaises(ObservationScheduleStoreError) as raised:
            self.attempt(store, "EP-NO-PLAN", self.rid(sc))
        self.assertEqual(str(raised.exception), "EPISODE_ADMISSION_ROUND_PLAN_MISSING")

    def test_a_written_plan_cannot_be_replaced_or_dropped(self) -> None:
        sc = self.scenario()
        self.crash_after_first_admission(sc)
        store = self.open_store(sc)
        row = store.get_episode_round(self.rid(sc))
        common = dict(
            round_id=row["round_id"], schedule_sha256=row["schedule_sha256"], activation_id=row["activation_id"],
            lineage_id=row["lineage_id"], round_started_at=row["round_started_at"], clock=R + timedelta(seconds=60),
        )
        for frame in ({"round_id": row["round_id"]}, {"round_id": row["round_id"], "recovery_plan": {"plan_sha256": "x"}}):
            with self.assertRaises(ObservationScheduleStoreError) as raised:
                store.record_episode_round(state="CLOSED", frame=frame, **common)
            self.assertEqual(str(raised.exception), "EPISODE_ROUND_PLAN_IMMUTABLE")


class ClassifierTests(unittest.TestCase):
    def test_classifier_is_pure_and_total(self) -> None:
        plan = {"winners": [{"episode_id": "E1", "mint": "M1", "ticket_priority": "p1"}, {"episode_id": "E2", "mint": "M2", "ticket_priority": "p2"}],
                "frame_sha256": "f", "protection_fingerprint": "p", "round_id": "R"}

        def committed(*ids):
            return [{"episode_id": i, "record": {"mint": "M" + i[1:], "ticket_priority": "p" + i[1:], "frame_sha256": "f",
                                                 "protection_fingerprint": "p", "round_id": "R"}} for i in ids]

        self.assertEqual(classify_round_recovery(plan=plan, committed=committed())["outcome"], "NO_ADMISSION")
        self.assertEqual(classify_round_recovery(plan=plan, committed=committed("E1"))["outcome"], "PARTIAL_ADMISSION")
        self.assertEqual(classify_round_recovery(plan=plan, committed=committed("E2", "E1"))["outcome"], "CLOSED")
        self.assertEqual(classify_round_recovery(plan={"winners": []}, committed=[])["outcome"], "NO_ADMISSION")
        self.assertEqual(classify_round_recovery(plan=plan, committed=committed("E9"))["reason_code"], "ROUND_ADMISSION_NOT_PLANNED")
        self.assertEqual(classify_round_recovery(plan=None, committed=committed("E1"))["reason_code"], "ROUND_PLAN_MISSING_WITH_ADMISSIONS")
        self.assertEqual(classify_round_recovery(plan=plan, committed=[], call_evidence_missing=True)["reason_code"], "ROUND_CALL_EVIDENCE_MISSING")


if __name__ == "__main__":
    unittest.main()
