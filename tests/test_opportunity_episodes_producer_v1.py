"""OPPORTUNITY_EPISODES producer proofs through scripts/observation_schedule.py::main.

D1 protection, D2 frame/sample, D3 crash/recovery, D5 decline/gaps and D11
resource gates. Only the transport, clock and authored vendor bytes are
synthetic; every state transition is produced by the production entry.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from tests.test_opportunity_episodes_harness_v1 import (  # noqa: E402
    EpisodeScenario,
    nominate,
    synth_mint,
    token_object,
)

S = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
PASS = dict(price=1.0, liquidity=10000, holders=60)


def obj(mint: str, **kw):
    values = dict(PASS)
    values.update(kw)
    return token_object(mint, **values)


def steady(mint: str, **kw):
    return lambda _now: obj(mint, **kw)


def search_calls(result: dict) -> list[dict]:
    return [call for call in result["_calls"] if call["kind"] == "search"]


class ScenarioCase(unittest.TestCase):
    def scenario(self, **kwargs) -> EpisodeScenario:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        kwargs.setdefault("start", S)
        kwargs.setdefault("stops", S + timedelta(hours=1))
        return EpisodeScenario(Path(tmp.name) / "rdp", **kwargs)


class ProducerProtectionTests(ScenarioCase):
    def test_protected_and_unknown_scope_never_admitted_or_published(self) -> None:
        protected, unknown, allowed = synth_mint("Prot"), synth_mint("Unknown"), synth_mint("Allowed")
        sc = self.scenario(
            assignment_entries=[
                {"identity_kind": "MINT", "identity": protected, "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}},
                {"identity_kind": "MINT", "identity": unknown, "role": "SPLIT_MEMBER", "scope": {"kind": "UNKNOWN"}},
            ]
        )
        nominate(sc.market, S, {
            "toporganicscore": [obj(protected, holders=999999), obj(allowed)],
            "toptraded": [obj(unknown)],
            "toptrending": [],
        })
        result = sc.tick(S + timedelta(seconds=5))
        self.assertEqual(result["terminal"], "TICK_COMPLETE", result)
        self.assertEqual([item["mint"] for item in sc.admissions()], [allowed])
        frame = sc.rounds()[0]["frame"]
        self.assertEqual((frame["counts"]["protected"], frame["counts"]["protection_unresolved"]), (1, 1))
        published = sc.published_text()
        self.assertIn(allowed, published)
        self.assertNotIn(protected, published)
        self.assertNotIn(unknown, published)
        self.assertNotIn("999999", published)
        # The E0 dependency is the admitted object's extract, not the nomination body.
        self.assertTrue(any("/witness/" in rel for rel in sc.named_raw_bodies), sc.named_raw_bodies)
        admission = sc.admissions()[0]
        self.assertEqual(admission["anchor_kind"], "NOMINATION_T0")
        self.assertEqual(admission["population"], "OPPORTUNITY_EPISODES")

    def test_missing_registered_source_blocks_every_admission(self) -> None:
        sc = self.scenario()
        (sc.data_root / "protection" / "assignments" / f"{sc.assignment['assignment_id']}.json").unlink()
        nominate(sc.market, S, {"toporganicscore": [obj(synth_mint("A"))], "toptraded": [], "toptrending": []})
        sc.tick(S + timedelta(seconds=5))
        self.assertEqual(sc.admissions(), [])
        frame = sc.rounds()[0]["frame"]
        self.assertEqual(frame["counts"]["protection_unresolved"], 1)


class ProducerFrameTests(ScenarioCase):
    def test_fresh_fail_is_not_healed_and_later_pass_gets_real_t0(self) -> None:
        mint = synth_mint("Later")
        sc = self.scenario()
        nominate(sc.market, S, {
            "toporganicscore": [obj(mint)],
            "toptraded": [obj(mint)],
            "toptrending": [obj(mint, holders=10)],
        })
        sc.tick(S + timedelta(seconds=5))
        self.assertEqual(sc.admissions(), [])
        candidate = sc.rounds()[0]["frame"]["candidates"][0]
        self.assertEqual((candidate["status"], candidate["reason"]), ("CORE_UNUSABLE", "HOLDERS_BELOW_FLOOR"))
        nominate(sc.market, S + timedelta(minutes=15), {"toporganicscore": [obj(mint)], "toptraded": [], "toptrending": []})
        sc.tick(S + timedelta(minutes=15, seconds=5))
        admissions = sc.admissions()
        self.assertEqual(len(admissions), 1)
        self.assertGreater(admissions[0]["t0"], "2026-10-05T00:15:05Z")
        self.assertEqual(admissions[0]["round_id"].split("-")[-1], "20261005T001500Z")

    def test_source_order_and_duplicates_do_not_change_lottery(self) -> None:
        mints = [synth_mint(f"Lot{i}") for i in range(5)]
        outcomes = []
        for reverse in (False, True):
            sc = self.scenario()
            rows = [obj(mint) for mint in mints]
            if reverse:
                rows = list(reversed(rows))
            nominate(sc.market, S, {
                "toporganicscore": rows[:3],
                "toptraded": rows[2:] + rows[:1],
                "toptrending": list(reversed(rows)),
            })
            sc.tick(S + timedelta(seconds=5))
            outcomes.append([(item["mint"], item["episode_id"], item["ticket_priority"]) for item in sc.admissions()])
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(len(outcomes[0]), 1)

    def test_incomplete_round_admits_nothing_then_next_round_admits(self) -> None:
        sc = self.scenario()
        mint = synth_mint("Inc")
        nominate(sc.market, S, {"toporganicscore": [obj(mint)], "toptraded": [], "toptrending": []})
        sc.market.category_failures[(S, "toptraded")] = 500
        sc.tick(S + timedelta(seconds=5))
        self.assertEqual(sc.admissions(), [])
        self.assertEqual(sc.rounds()[0]["state"], "INCOMPLETE")
        nominate(sc.market, S + timedelta(minutes=15), {"toporganicscore": [obj(mint)], "toptraded": [], "toptrending": []})
        sc.tick(S + timedelta(minutes=15, seconds=5))
        self.assertEqual(len(sc.admissions()), 1)

    def test_quota_edge_leaves_ticket_pending_for_next_round(self) -> None:
        sc = self.scenario()
        a, b = synth_mint("EdgeA"), synth_mint("EdgeB")
        nominate(sc.market, S, {"toporganicscore": [obj(a), obj(b)], "toptraded": [], "toptrending": []})
        sc.tick(S + timedelta(seconds=5))
        first = sc.admissions()
        self.assertEqual(len(first), 1)
        frame = sc.rounds()[0]["frame"]
        self.assertEqual(frame["selection"]["not_selected"], [m for m in (a, b) if m != first[0]["mint"]])
        nominate(sc.market, S + timedelta(minutes=15), {"toporganicscore": [obj(a), obj(b)], "toptraded": [], "toptrending": []})
        sc.tick(S + timedelta(minutes=15, seconds=5))
        self.assertEqual(sorted(item["mint"] for item in sc.admissions()), sorted([a, b]))


class ProducerCrashTests(ScenarioCase):
    def _admit(self, sc, mint, *, fault=None):
        nominate(sc.market, S, {"toporganicscore": [obj(mint)], "toptraded": [], "toptrending": []})
        sc.market.series[mint] = steady(mint)
        return sc.tick(S + timedelta(seconds=5), fault=fault)

    def test_crash_before_commit_has_no_member_and_no_backdated_t0(self) -> None:
        sc = self.scenario()
        mint = synth_mint("Pre")
        crashed = self._admit(sc, mint, fault="EPISODE_BEFORE_ADMISSION_COMMIT")
        self.assertNotEqual(crashed["_exit_code"], 0)
        self.assertEqual(sc.admissions(), [])
        self.assertEqual(sc.rounds()[0]["state"], "STARTED")
        resumed = sc.tick(S + timedelta(seconds=40))
        self.assertEqual([c["kind"] for c in resumed["_calls"]], [])
        admissions = sc.admissions()
        self.assertEqual(len(admissions), 1)
        self.assertGreaterEqual(admissions[0]["t0"], "2026-10-05T00:00:40Z")
        self.assertEqual(admissions[0]["witness_request_started_at"], "2026-10-05T00:00:05Z")

    def test_crash_after_commit_recovers_same_episode_and_quota(self) -> None:
        sc = self.scenario()
        mint = synth_mint("Post")
        self._admit(sc, mint, fault="EPISODE_AFTER_ADMISSION_COMMIT")
        before = sc.admissions()
        self.assertEqual(len(before), 1)
        self.assertGreater(sc.unpublished(), 0)
        nominate(sc.market, S, {"toporganicscore": [obj(mint), obj(synth_mint("Other"))], "toptraded": [], "toptrending": []})
        sc.tick(S + timedelta(seconds=40))
        self.assertEqual(sc.unpublished(), 0)
        self.assertEqual(sc.admissions(), before)
        selection = sc.rounds()[0]["frame"]["selection"]
        self.assertEqual((selection["committed_in_round_before"], selection["admitted_episode_ids"]), (1, []))

    def test_send_without_durable_result_is_an_explicit_unknown_gap(self) -> None:
        sc = self.scenario()
        mint = synth_mint("Send")
        self._admit(sc, mint)
        episode = sc.admissions()[0]["episode_id"]
        sc.tick(datetime(2026, 10, 5, 0, 10, 2, tzinfo=UTC), fault="EPISODE_AFTER_CALL_START")
        self.assertEqual(sc.slot_states(episode)["E300"][0], "CLAIMED")
        resumed = sc.tick(datetime(2026, 10, 5, 0, 10, 40, tzinfo=UTC))
        self.assertEqual(search_calls(resumed), [])
        self.assertEqual(sc.slot_states(episode)["E300"], ("CENSORED", "ATTEMPT_OUTCOME_UNKNOWN"))

    def test_completed_call_is_recovered_without_a_new_request(self) -> None:
        sc = self.scenario()
        mint = synth_mint("Done")
        self._admit(sc, mint)
        episode = sc.admissions()[0]["episode_id"]
        sc.tick(datetime(2026, 10, 5, 0, 10, 2, tzinfo=UTC), fault="EPISODE_AFTER_CALL_COMPLETE")
        resumed = sc.tick(datetime(2026, 10, 5, 0, 12, 0, tzinfo=UTC))
        self.assertEqual(search_calls(resumed), [])
        self.assertEqual(sc.slot_states(episode)["E300"][0], "OBSERVED")

    def test_publication_crash_replays_the_exact_publication(self) -> None:
        sc = self.scenario()
        mint = synth_mint("Pub")
        self._admit(sc, mint, fault="EPISODE_AFTER_PUBLISH_BEFORE_MARK")
        self.assertGreater(sc.unpublished(), 0)
        completed = sorted((sc.data_root / "datasets" / "publication_jobs" / "completed").glob("*.json"))
        self.assertEqual(len(completed), 1)
        resumed = sc.tick(S + timedelta(seconds=40))
        self.assertTrue(resumed["publications"][0]["replay"], resumed)
        self.assertEqual(resumed["publications"][0]["content_sha256"], completed[0].stem)
        self.assertEqual(sc.unpublished(), 0)

    def test_publisher_stage_fault_is_repaired_next_tick(self) -> None:
        sc = self.scenario()
        mint = synth_mint("Stage")
        crashed = self._admit(sc, mint, fault="AFTER_ARTIFACTS")
        self.assertNotEqual(crashed["_exit_code"], 0)
        sc.tick(S + timedelta(seconds=40))
        self.assertEqual(sc.unpublished(), 0)
        self.assertEqual(list((sc.data_root / "datasets" / "publication_jobs" / "open").glob("*.json")), [])


class ProducerGapTests(ScenarioCase):
    def test_decline_and_gap_states_stay_explicit(self) -> None:
        sc = self.scenario(observation_overrides={"availability_grace_seconds": 60})
        mint = synth_mint("Gaps")
        nominate(sc.market, S, {"toporganicscore": [obj(mint)], "toptraded": [], "toptrending": []})

        def series(now):
            slot = sc.market.slot_for(now)
            minute = slot.minute
            if minute == 15:
                return None
            if minute == 20:
                return obj(mint, holders=None)
            if minute == 40:
                return obj(mint, liquidity=100.0)
            return obj(mint)

        sc.market.series[mint] = series
        sc.market.search_failures[datetime(2026, 10, 5, 0, 25, tzinfo=UTC)] = 500
        # A 61 s response after a 60 s availability grace is late but inside
        # the writer lease and wall deadline of the same tick.
        sc.market.latency = lambda kind, now: 61.0 if kind == "search" and sc.market.slot_for(now).minute == 30 else 1.0
        sc.tick(S + timedelta(seconds=5))
        episode = sc.admissions()[0]["episode_id"]
        for minute in (10, 15, 20, 25, 30, 40):
            sc.tick(datetime(2026, 10, 5, 0, minute, 2, tzinfo=UTC))
        states = sc.slot_states(episode)
        self.assertEqual(states["E300"][0], "OBSERVED")
        self.assertEqual(states["E600"], ("DISAPPEARED", "MINT_ABSENT_IN_RESPONSE"))
        self.assertEqual(states["E900"][0], "OBSERVED")
        self.assertEqual(states["E1200"][0], "CENSORED")
        self.assertIn("HTTP", str(states["E1200"][1]))
        self.assertEqual(states["E1500"], ("CENSORED_LATE", "CENSORED_LATE"))
        self.assertEqual(states["E1800"], ("CENSORED", "SLOT_NOT_EXECUTED"))
        self.assertEqual(states["E2100"][0], "OBSERVED")
        self.assertEqual(len(sc.admissions()), 1)
        published = [json.loads(line) for line in []]
        del published
        import pyarrow.parquet as pq

        rows = []
        for path in (sc.data_root / "datasets" / "parquet").rglob("observations.parquet"):
            rows.extend(pq.read_table(path).to_pylist())
        holders_e900 = [
            value
            for row in rows
            if row.get("episode_id") == episode and row.get("point_id") == "E900"
            for value in row["field_values"]
            if value["field_id"] == "FIELD-HOLDER-COUNT-001"
        ]
        self.assertEqual(len(holders_e900), 1)
        self.assertEqual((holders_e900[0]["state"], holders_e900[0]["typed_value_or_null"]), ("MISSING_TYPED", None))
        self.assertEqual(holders_e900[0]["missing_reason"], "FIELD_ABSENT")


class ProducerResourceTests(ScenarioCase):
    def test_tick_call_budget_stops_intake(self) -> None:
        sc = self.scenario(budgets={"provider_calls_per_tick_max": 2})
        nominate(sc.market, S, {"toporganicscore": [obj(synth_mint("Bud"))], "toptraded": [], "toptrending": []})
        result = sc.tick(S + timedelta(seconds=5))
        self.assertEqual(result["terminal"], "TICK_PARTIAL")
        self.assertEqual(result["stop_reason"], "BLOCKED_BUDGET")
        self.assertEqual(sc.admissions(), [])
        self.assertEqual(sc.rounds()[0]["state"], "INCOMPLETE")

    def test_oversized_response_is_bounded_and_blocks_round(self) -> None:
        sc = self.scenario(budgets={"response_decoded_bytes_max": 1024})
        big = [obj(synth_mint(f"Big{i}")) for i in range(20)]
        nominate(sc.market, S, {"toporganicscore": big, "toptraded": [], "toptrending": []})
        sc.tick(S + timedelta(seconds=5))
        self.assertEqual(sc.admissions(), [])
        sources = sc.rounds()[0]["frame"]["sources"]
        self.assertEqual(sources[0]["missing_reason"], "RESPONSE_BODY_TOO_LARGE")

    def test_active_cap_stops_new_intake_without_dropping_obligations(self) -> None:
        sc = self.scenario(active_cap=1)
        a, b = synth_mint("CapA"), synth_mint("CapB")
        nominate(sc.market, S, {"toporganicscore": [obj(a)], "toptraded": [], "toptrending": []})
        sc.market.series[a] = steady(a)
        sc.tick(S + timedelta(seconds=5))
        sc.tick(S + timedelta(minutes=10, seconds=2))
        nominate(sc.market, S + timedelta(minutes=15), {"toporganicscore": [obj(b)], "toptraded": [], "toptrending": []})
        sc.tick(S + timedelta(minutes=15, seconds=5))
        self.assertEqual([item["mint"] for item in sc.admissions()], [a])
        selection = sc.rounds()[1]["frame"]["selection"]
        self.assertEqual((selection["quota"], selection["active_before"]), (0, 1))
        self.assertEqual(sc.slot_states(sc.admissions()[0]["episode_id"])["E300"][0], "OBSERVED")

    def test_account_level_pace_spans_lanes(self) -> None:
        sc = self.scenario()
        store = ObservationScheduleStore(sc.ops_path)
        token = store.acquire_lease("test-other-lane", clock=S)
        store.save_accounting(
            schedule_sha256="ee" * 32,
            activation_id="ACT-OTHER-LANE",
            utc_day="2026-10-05",
            values={
                "provider_calls": 1,
                "modeled_credits": 1,
                "candidates": 0,
                "members": 0,
                "raw_bytes": 1,
                "canonical_bytes": 1,
                "last_provider_call_at": "2026-10-05T00:00:05Z",
            },
            clock=S,
        )
        store.release_lease(token)
        store.close()
        nominate(sc.market, S, {"toporganicscore": [obj(synth_mint("Pace"))], "toptraded": [], "toptrending": []})
        result = sc.tick(S + timedelta(seconds=5))
        self.assertEqual(result["_calls"][0]["at"], "2026-10-05T00:00:08Z")


class AdmissionQuotaTests(unittest.TestCase):
    def test_day_rolling_and_round_quota(self) -> None:
        from solana_alpha_lab.factory.opportunity_episode_tick import admission_quota

        raw = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(raw, ignore_errors=True))
        store = ObservationScheduleStore(Path(raw) / "ops.sqlite")
        self.addCleanup(store.close)
        if True:
            token = store.acquire_lease("test", clock=S)
            sampling = {"daily_normal_ceiling": 2, "rolling_24h_max": 2, "active_episode_cap": 400}

            def commit(index: int, t0: str, round_id: str) -> None:
                store.commit_episode_admission(
                    record={
                        "episode_id": f"EP-{index}",
                        "schedule_sha256": "aa" * 32,
                        "activation_id": "ACT",
                        "collection_lineage_id": "LIN",
                        "cycle_start": "2026-10-05T00:00:00Z",
                        "mint": f"M{index}",
                        "t0": t0,
                        "cohort_id": "REL-X",
                        "round_id": round_id,
                    },
                    content_sha256=f"{index:064d}",
                    final_deadline_at="2026-10-05T00:00:00Z",
                    due_rows=[],
                    outbox_rows=[],
                    clock=S,
                )

            evening = datetime(2026, 10, 5, 23, 45, tzinfo=UTC)
            commit(1, "2026-10-05T11:45:10Z", "R47")
            commit(2, "2026-10-05T23:45:10Z", "R95")
            self.assertEqual(
                admission_quota(store, lineage_id="LIN", sampling=sampling, round_started_at=evening,
                                round_period_seconds=900, round_id_value="R95", now=evening + timedelta(seconds=20))["quota"],
                0,
            )
            next_morning = datetime(2026, 10, 6, 11, 45, tzinfo=UTC)
            state = admission_quota(store, lineage_id="LIN", sampling=sampling, round_started_at=next_morning,
                                    round_period_seconds=900, round_id_value="R47-2", now=next_morning + timedelta(seconds=15))
            self.assertEqual((state["day_used"], state["rolling_used"], state["quota"]), (0, 1, 1))
            midnight = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)
            boundary = admission_quota(store, lineage_id="LIN", sampling=dict(sampling, daily_normal_ceiling=96, rolling_24h_max=2),
                                       round_started_at=midnight, round_period_seconds=900, round_id_value="R0-2", now=midnight + timedelta(seconds=5))
            self.assertEqual((boundary["day_used"], boundary["rolling_used"], boundary["quota"]), (0, 2, 0))
            store.release_lease(token)


if __name__ == "__main__":
    unittest.main()
