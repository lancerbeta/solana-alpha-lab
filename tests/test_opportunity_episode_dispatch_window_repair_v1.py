"""Dispatch coverage proofs using the production CLI, store, ledger and publication."""
from __future__ import annotations

import unittest
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from tests.test_opportunity_episodes_harness_v1 import cli_tick, nominate, synth_mint, SyntheticJupiter
from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock
from solana_alpha_lab.factory.observation_schedule import parse_utc
from solana_alpha_lab.factory import opportunity_episode_tick as owner
from tests.test_opportunity_episodes_producer_v1 import S, ScenarioCase, obj, steady, search_calls


class EntryCrossingClock(AdvancingClock):
    """Physical binding sees entry; real owner work consumes the injected delay."""
    def __init__(self, entry, reached):
        super().__init__(entry)
        self.reached = reached
        self.bound = False

    def __call__(self):
        value = super().__call__()
        if not self.bound:
            self.bound = True
            self._current = self.reached
        return value


class DispatchWindowTests(ScenarioCase):
    def admitted(self, **kwargs):
        sc = self.scenario(**kwargs)
        mint = synth_mint("Dispatch")
        nominate(sc.market, S, {"toporganicscore": [obj(mint)], "toptraded": [], "toptrending": []})
        sc.market.series[mint] = steady(mint)
        result = sc.tick(S + timedelta(seconds=5))
        self.assertEqual(result["round"]["state"], "CLOSED", result)
        self.assertEqual(len(sc.admissions()), 1)
        episode = sc.admissions()[0]["episode_id"]
        assigned = S + timedelta(minutes=10)
        return sc, episode, assigned

    def test_production_pre_window_entry_crossing_then_late_wake(self):
        sc, episode, assigned = self.admitted()
        # Same offsets as the live incident: entry before assigned, dispatch
        # owner reached after assigned, ordinary next pass after deadline.
        entry = assigned - timedelta(seconds=1.372118)
        reached = assigned + timedelta(seconds=0.178825)
        result = cli_tick(sc.data_root, sc.market, entry, pacing_clock=EntryCrossingClock(entry, reached))
        calls = search_calls(result)
        self.assertEqual(len(calls), 1, result)
        self.assertGreaterEqual(parse_utc(calls[0]["at"]), assigned)
        self.assertLess(parse_utc(calls[0]["at"]), assigned + timedelta(seconds=60))
        later = sc.tick(assigned + timedelta(seconds=60.389428))
        self.assertEqual(search_calls(later), [])
        self.assertEqual(sc.slot_states(episode)["E300"], ("OBSERVED", None))
        self.assertEqual(sc.unpublished(), 0)

    def test_initial_scan_before_due_then_normal_headroom_work_crosses_boundary(self):
        sc, episode, assigned = self.admitted()
        entry = assigned - timedelta(seconds=1.372118)
        clock = AdvancingClock(entry)
        disk_usage = owner.shutil.disk_usage
        def work(path):
            actual = disk_usage(path)
            clock.sleep(1.550943)
            return actual
        with patch.object(owner.shutil, "disk_usage", side_effect=work):
            result = cli_tick(sc.data_root, sc.market, entry, pacing_clock=clock)
        self.assertEqual(len(search_calls(result)), 1, result)
        self.assertEqual(sc.slot_states(episode)["E300"], ("OBSERVED", None))
        # Even the historical late external wake cannot replay the call.
        self.assertEqual(search_calls(sc.tick(assigned + timedelta(seconds=60.389428))), [])
        self.assertEqual(sc.unpublished(), 0)

    def test_deadline_equality_late_and_early_never_send_or_backfill(self):
        for offset in (-0.001, 60, 60.389428):
            with self.subTest(offset=offset):
                sc, episode, assigned = self.admitted()
                result = sc.tick(assigned + timedelta(seconds=offset))
                self.assertEqual(search_calls(result), [])
                expected = ("PENDING", None) if offset < 0 else ("CENSORED", "SLOT_NOT_EXECUTED")
                self.assertEqual(sc.slot_states(episode)["E300"], expected)
                if offset >= 60:
                    sc.tick(assigned + timedelta(seconds=65))
                    self.assertEqual(sc.slot_states(episode)["E300"], expected)

    def test_inside_window_restart_after_recorded_intent_never_duplicates(self):
        for fault in (None, "EPISODE_AFTER_CALL_START", "EPISODE_AFTER_CALL_COMPLETE"):
            with self.subTest(fault=fault):
                sc, episode, assigned = self.admitted()
                first = sc.tick(assigned + timedelta(seconds=2), fault=fault)
                second = sc.tick(assigned + timedelta(seconds=20))
                self.assertEqual(len(search_calls(first)) + len(search_calls(second)), 0 if fault == "EPISODE_AFTER_CALL_START" else 1)
                expected = ("CENSORED", "ATTEMPT_OUTCOME_UNKNOWN") if fault == "EPISODE_AFTER_CALL_START" else ("OBSERVED", None)
                self.assertEqual(sc.slot_states(episode)["E300"], expected)
                self.assertEqual(sc.unpublished(), 0)

    def test_nomination_call_crossing_due_gets_interleaved_dispatch(self):
        sc, episode, assigned = self.admitted()
        # The existing E600 aligns with the next 15m round. A delayed boundary
        # in physical storage work is followed by category work and live sweeps.
        assigned = S + timedelta(minutes=15)
        entry = assigned - timedelta(seconds=2)
        clock = AdvancingClock(entry)
        recover = owner._EpisodeTick.recover_unresolved_rounds
        def work(tick):
            actual = recover(tick)
            clock.sleep(2.1)
            return actual
        nominate(sc.market, assigned, {"toporganicscore": [], "toptraded": [], "toptrending": []})
        with patch.object(owner._EpisodeTick, "recover_unresolved_rounds", work):
            result = cli_tick(sc.data_root, sc.market, entry, pacing_clock=clock)
        self.assertEqual(len(search_calls(result)), 1, result)
        self.assertEqual(sc.slot_states(episode)["E600"], ("OBSERVED", None))
        self.assertEqual(result["round"]["state"], "CLOSED", result)
        self.assertEqual(sum(c["kind"] == "category" for c in result["_calls"]), 3)

    def test_canonical_timer_worst_phase_drives_real_claim_and_next_wake(self):
        import configparser
        root = Path(__file__).resolve().parents[1]
        unit = configparser.ConfigParser()
        unit.read(root / "configs/factory_remote_ops/factory-observation-schedule.timer")
        interval = float(unit["Timer"]["OnUnitInactiveSec"].rstrip("s"))
        jitter = float(unit["Timer"]["AccuracySec"].rstrip("s"))
        sc, episode, assigned = self.admitted()
        pre = sc.tick(assigned - timedelta(seconds=0.001))
        self.assertEqual(search_calls(pre), [])
        # Worst phase: service ends just before due, local cleanup+preflight+
        # owner prelude each use all 5s, timer uses its full accuracy allowance.
        next_entry = assigned - timedelta(seconds=0.001) + timedelta(seconds=interval + jitter + 5)
        next_owner = next_entry + timedelta(seconds=10)
        result = cli_tick(sc.data_root, sc.market, next_entry,
                          pacing_clock=EntryCrossingClock(next_entry, next_owner))
        calls = search_calls(result)
        self.assertEqual(len(calls), 1, result)
        self.assertLess(parse_utc(calls[0]["at"]), assigned + timedelta(seconds=60))
        self.assertEqual(sc.slot_states(episode)["E300"], ("OBSERVED", None))
        self.assertEqual(search_calls(sc.tick(next_owner + timedelta(seconds=interval + jitter + 5))), [])
        self.assertEqual(sc.unpublished(), 0)

    def test_pace_crossing_deadline_never_calls_transport(self):
        sc, episode, assigned = self.admitted()
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        store = ObservationScheduleStore(sc.ops_path)
        token = store.acquire_lease("synthetic-other-call", clock=assigned + timedelta(seconds=58))
        store.save_accounting(schedule_sha256="ee" * 32, activation_id="ACT-SYNTHETIC-OTHER-LANE",
                              utc_day=S.strftime("%Y-%m-%d"),
                              values={"provider_calls": 1, "modeled_credits": 1, "raw_bytes": 1,
                                      "canonical_bytes": 1, "last_provider_call_at": (assigned + timedelta(seconds=58)).isoformat().replace("+00:00", "Z")},
                              clock=assigned + timedelta(seconds=58))
        store.release_lease(token)
        store.close()
        result = sc.tick(assigned + timedelta(seconds=58.5))
        self.assertEqual(search_calls(result), [])
        self.assertEqual(sc.slot_states(episode)["E300"], ("CENSORED", "SLOT_NOT_EXECUTED"))

    def test_worker_delayed_to_deadline_is_proven_no_request_not_unknown(self):
        sc, episode, assigned = self.admitted()
        entry = assigned + timedelta(seconds=2)
        clock = AdvancingClock(entry)
        guard_open = owner._WindowGuardedOpener.open
        def delayed(inner, url):
            clock.sleep(58)
            return guard_open(inner, url)
        with patch.object(owner._WindowGuardedOpener, "open", delayed):
            result = cli_tick(sc.data_root, sc.market, entry, pacing_clock=clock)
        self.assertEqual(search_calls(result), [], result)
        state, reason = sc.slot_states(episode)["E300"]
        self.assertEqual(state, "CENSORED")
        self.assertEqual(reason, "SLOT_NOT_EXECUTED:DISPATCH_WINDOW_CLOSED")
        rows = sc.query("SELECT state,payload_json FROM call_ledger WHERE primitive_id=?", (owner.SEARCH_PRIMITIVE,))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "COMPLETED")
        self.assertEqual(json.loads(rows[0][1])["status"], "NO_REQUEST")
        self.assertEqual(search_calls(sc.tick(assigned + timedelta(seconds=65))), [])

    def test_no_request_completion_crash_preserves_published_gap_bytes(self):
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        import pyarrow.parquet as pq
        published = []
        for crash in (False, True):
            sc, episode, assigned = self.admitted()
            entry = assigned + timedelta(seconds=2)
            clock = AdvancingClock(entry)
            guard_open = owner._WindowGuardedOpener.open
            complete = ObservationScheduleStore.complete_call
            def delayed(inner, url):
                clock.sleep(58)
                return guard_open(inner, url)
            def physical_crash(store, **kwargs):
                result = complete(store, **kwargs)
                if crash and kwargs['payload'].get('status') == 'NO_REQUEST':
                    raise owner.EpisodeTickError('FAULT_INJECTED:AFTER_NO_REQUEST_COMPLETE')
                return result
            with patch.object(owner._WindowGuardedOpener, 'open', delayed), \
                 patch.object(ObservationScheduleStore, 'complete_call', physical_crash):
                result = cli_tick(sc.data_root, sc.market, entry, pacing_clock=clock)
            self.assertEqual(search_calls(result), [])
            if crash:
                self.assertEqual(sc.slot_states(episode)['E300'][0], 'CLAIMED')
            restarted = sc.tick(assigned + timedelta(seconds=65))
            self.assertEqual(search_calls(restarted), [])
            self.assertEqual(sc.slot_states(episode)['E300'], ('CENSORED', 'SLOT_NOT_EXECUTED:DISPATCH_WINDOW_CLOSED'))
            self.assertEqual(sc.unpublished(), 0)
            rows = [row for path in (sc.data_root/'datasets').rglob('*.parquet')
                    for row in pq.read_table(path).to_pylist()
                    if row.get('point_id') == 'E300']
            self.assertEqual(len(rows), 1)
            published.append(rows[0])
            self.assertEqual(search_calls(sc.tick(assigned + timedelta(seconds=80))), [])
        self.assertEqual(published[0], published[1])

    def test_same_assigned_slots_follow_configured_batching(self):
        for batch_size, count in ((1, 2), (100, 1)):
            with self.subTest(batch_size=batch_size):
                round_at = S + timedelta(minutes=345)  # quota=2 under real 100/day rule
                sc = self.scenario(start=round_at, stops=round_at + timedelta(hours=1),
                                   daily_ceiling=100, observation_overrides={"max_batch_size": batch_size},
                                   budgets={"provider_calls_per_utc_day_max": 100000,
                                            "modeled_provider_credits_per_utc_day_max": 100000})
                mints = [synth_mint("BatchA"), synth_mint("BatchB")]
                nominate(sc.market, round_at, {"toporganicscore": [obj(m) for m in mints], "toptraded": [], "toptrending": []})
                for mint in mints:
                    sc.market.series[mint] = steady(mint)
                admission = sc.tick(round_at + timedelta(seconds=5))
                self.assertEqual(len(sc.admissions()), 2, admission)
                assigned = round_at + timedelta(minutes=10)
                result = sc.tick(assigned + timedelta(seconds=1))
                calls = search_calls(result)
                self.assertEqual(len(calls), count, result)
                sizes = [len(parse_qs(urlsplit(c["url"]).query)["query"][0].split(",")) for c in calls]
                self.assertTrue(all(size <= batch_size for size in sizes))
                self.assertEqual(sum(sizes), 2)
                self.assertEqual(search_calls(sc.tick(assigned + timedelta(seconds=30))), [])

    def test_transport_and_absent_mint_stay_typed(self):
        for failure in (500, "ABSENT", "TIMEOUT"):
            with self.subTest(failure=failure):
                sc, episode, assigned = self.admitted()
                if failure == "ABSENT":
                    sc.market.series.clear()
                elif failure == "TIMEOUT":
                    # Physical transport exception, not a fabricated observation.
                    sc.market.search_failures[assigned] = failure
                else:
                    sc.market.search_failures[assigned] = failure
                result = sc.tick(assigned + timedelta(seconds=2))
                self.assertEqual(len(search_calls(result)), 1, result)
                self.assertNotEqual(sc.slot_states(episode)["E300"][0], "OBSERVED")
                self.assertEqual(sc.unpublished(), 0)

    def test_search_budget_gate_is_explicit_no_request_gap(self):
        sc, episode, assigned = self.admitted()
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        store = ObservationScheduleStore(sc.ops_path)
        values = store.load_accounting(schedule_sha256=sc.schedule["schedule_sha256"],
                                       activation_id=sc.activation_id, utc_day=S.strftime("%Y-%m-%d"))
        values["provider_calls"] = sc.schedule["budgets"]["provider_calls_per_utc_day_max"]
        token = store.acquire_lease("synthetic-exhausted-account", clock=assigned)
        store.save_accounting(schedule_sha256=sc.schedule["schedule_sha256"], activation_id=sc.activation_id,
                              utc_day=S.strftime("%Y-%m-%d"), values=values, clock=assigned)
        store.release_lease(token)
        store.close()
        result = sc.tick(assigned + timedelta(seconds=2))
        self.assertEqual(search_calls(result), [])
        self.assertEqual(result["stop_reason"], "BLOCKED_BUDGET")
        self.assertEqual(sc.slot_states(episode)["E300"], ("CENSORED", "SLOT_NOT_EXECUTED:BLOCKED_BUDGET"))
        self.assertEqual(sc.unpublished(), 0)

    def test_runtime_exceeding_model_is_visible_typed_gap(self):
        sc, episode, assigned = self.admitted()
        entry = assigned - timedelta(seconds=2)
        clock = EntryCrossingClock(entry, assigned + timedelta(seconds=61))
        result = cli_tick(sc.data_root, sc.market, entry, pacing_clock=clock)
        self.assertEqual(search_calls(result), [])
        self.assertGreaterEqual(result["max_dispatch_checkpoint_gap_seconds"], 60)
        self.assertEqual(sc.slot_states(episode)["E300"], ("CENSORED", "SLOT_NOT_EXECUTED"))

    def test_four_real_admissions_worst_phase_slow_batches_get_four_fair_sends(self):
        # Four reachable admissions through four ordinary nomination rounds;
        # no inserted/rewritten slot rows. Different E-points share the grid.
        sc = self.scenario(observation_overrides={"max_batch_size": 1},
                           budgets={"provider_calls_per_utc_day_max": 100000,
                                    "modeled_provider_credits_per_utc_day_max": 100000})
        for i in range(4):
            at = S + timedelta(minutes=15*i)
            mint = synth_mint(f"Four{i}")
            nominate(sc.market, at, {"toporganicscore": [obj(mint)], "toptraded": [], "toptrending": []})
            sc.market.series[mint] = steady(mint)
            sc.tick(at + timedelta(seconds=5))
        self.assertEqual(len(sc.admissions()), 4)
        assigned = S + timedelta(minutes=55)
        entry = assigned + timedelta(seconds=21)
        clock = EntryCrossingClock(entry, assigned + timedelta(seconds=31))
        allowance = [15.0]
        offered = []
        real_wrap = owner.wrap_opener_with_wall_deadline
        def physical_waiter(opener, *, wall_seconds, heartbeat=None):
            if isinstance(opener, owner._WindowGuardedOpener):
                allowance[0] = wall_seconds
                offered.append(wall_seconds)
            return real_wrap(opener, wall_seconds=wall_seconds, heartbeat=heartbeat)
        # Transport-authored slow responses consume the real allowance passed
        # by production. First three report TIMEOUT, final one returns HTTP200.
        sc.market.latency = lambda kind, now: allowance[0] if kind == "search" else 1
        original_open = SyntheticJupiter.open
        def physical_response(transport, url):
            if urlsplit(url).path == "/tokens/v2/search" and len(offered) < 4:
                transport.market.search_failures[assigned] = "TIMEOUT"
            else:
                transport.market.search_failures.pop(assigned, None)
            return original_open(transport, url)
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        complete = ObservationScheduleStore.complete_call
        def bookkeeping(store, **kwargs):
            result = complete(store, **kwargs)
            clock.sleep(1)  # full supported local bookkeeping bound
            return result
        with patch.object(owner, "wrap_opener_with_wall_deadline", physical_waiter), \
             patch.object(SyntheticJupiter, "open", physical_response), \
             patch.object(ObservationScheduleStore, "complete_call", bookkeeping):
            result = cli_tick(sc.data_root, sc.market, entry, pacing_clock=clock)
        calls = search_calls(result)
        self.assertEqual(len(calls), 4, result)
        starts = [(parse_utc(c["at"])-assigned).total_seconds() for c in calls]
        self.assertEqual(starts, [31, 39, 47, 55])
        self.assertTrue(all(0 <= at < 60 for at in starts))
        self.assertTrue(all(b-a >= 3 for a,b in zip(starts, starts[1:])))
        self.assertEqual(offered, [4, 4, 4, 4])
        self.assertEqual([c["status"] for c in calls], ["TIMEOUT"]*3 + [200])
        self.assertEqual(sc.unpublished(), 0)
        terminal = sc.query("SELECT state FROM due_observations WHERE due_at=?",
                            (assigned.isoformat().replace("+00:00", "Z"),))
        self.assertEqual(sorted(r[0] for r in terminal), ["CENSORED"]*3 + ["OBSERVED"])
        self.assertEqual(sc.query("SELECT COUNT(*) FROM call_ledger WHERE primitive_id=? AND state='COMPLETED' AND created_at>=?", (owner.SEARCH_PRIMITIVE, assigned.isoformat().replace("+00:00", "Z")))[0][0], 4)
        self.assertEqual(search_calls(sc.tick(assigned + timedelta(seconds=76))), [])

    def test_conservative_capacity_estimate_never_closes_an_open_fast_batch(self):
        sc = self.scenario(stops=S + timedelta(hours=4),
                           observation_overrides={"max_batch_size": 1},
                           budgets={"provider_calls_per_utc_day_max": 100000,
                                    "modeled_provider_credits_per_utc_day_max": 100000})
        for i in range(9):
            at = S + timedelta(minutes=15*i)
            mint = synth_mint(f"FastNine{i}")
            nominate(sc.market, at, {"toporganicscore": [obj(mint)], "toptraded": [], "toptrending": []})
            sc.market.series[mint] = steady(mint)
            sc.tick(at + timedelta(seconds=5))
        self.assertEqual(len(sc.admissions()), 9)
        assigned = S + timedelta(minutes=130)
        entry = assigned + timedelta(seconds=21)
        clock = EntryCrossingClock(entry, assigned + timedelta(seconds=30.999))
        sc.market.latency = lambda kind, now: 0.1
        result = cli_tick(sc.data_root, sc.market, entry, pacing_clock=clock)
        calls = search_calls(result)
        self.assertEqual(len(calls), 9, result)
        self.assertTrue(all(assigned <= parse_utc(c["at"]) < assigned + timedelta(seconds=60) for c in calls))
        states = sc.query("SELECT state FROM due_observations WHERE due_at=?", (assigned.isoformat().replace("+00:00", "Z"),))
        self.assertEqual([row[0] for row in states], ["OBSERVED"]*9)
        self.assertEqual(sc.unpublished(), 0)
        self.assertEqual(search_calls(sc.tick(assigned + timedelta(seconds=80))), [])


class SchedulerModelTests(unittest.TestCase):
    def test_canonical_effective_wake_and_blocking_model_strictly_covers_window(self):
        import configparser
        root = Path(__file__).resolve().parents[1]
        unit = configparser.ConfigParser()
        unit.read(root / "configs/factory_remote_ops/factory-observation-schedule.timer")
        timer = unit["Timer"]
        cadence = float(timer["OnUnitInactiveSec"].rstrip("s"))
        jitter = float(timer["AccuracySec"].rstrip("s"))
        self.assertEqual(float(timer["RandomizedDelaySec"]), 0)
        self.assertNotIn("OnUnitActiveSec", timer)
        # Includes cleanup, service preflight, first owner prelude. No overlap
        # assumption: next wake is measured from the previous service's exit.
        idle_gap = cadence + jitter + 3 * 5
        active_gap = owner.EPISODE_CALL_WALL_SECONDS + 3 + 5
        effective_gap = max(idle_gap, active_gap)
        self.assertLess(effective_gap, 60, "wake/runtime can consume the entire dispatch window")
        self.assertLess(owner.EPISODE_CALL_WALL_SECONDS, 60)
        # Worst-phase model across all 400 active episodes / max100 batches.
        now = effective_gap
        starts = []
        for remaining in (4, 3, 2, 1):
            if starts:
                now += 3
            starts.append(now)
            allowance = (60 - now - remaining * owner.DISPATCH_LOCAL_MARGIN_SECONDS - (remaining - 1) * 3) / remaining
            self.assertGreater(allowance, 0)
            now += min(owner.EPISODE_CALL_WALL_SECONDS, allowance) + 1
        self.assertTrue(all(0 <= at < 60 for at in starts), starts)



if __name__ == "__main__":
    unittest.main()
