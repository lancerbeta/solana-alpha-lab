"""Owner-operability seams through public producer/capture entrypoints."""
from __future__ import annotations

import tempfile
import unittest
import os
import json
import time
from unittest.mock import patch
from collections import namedtuple
from datetime import UTC, datetime, timedelta
from pathlib import Path
from contextlib import closing

from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario, SyntheticJupiter, nominate, synth_mint, token_object
from solana_alpha_lab.factory.live_cohort_vanilla_path import capture_freeze_export
from solana_alpha_lab.factory.research_store import ResearchStore

START = datetime(2026, 10, 5, tzinfo=UTC)


class EpisodeOperabilityTests(unittest.TestCase):
    def scenario(self, **kwargs):
        keep = os.environ.get("OEP_OPERABILITY_WORK")
        if keep:
            root = Path(keep).resolve() / self._testMethodName / "rdp"
        else:
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            root = Path(temporary.name) / "rdp"
        ResearchStore(root).prepare_write_lookup()
        start = kwargs.pop("start", START)
        stops = kwargs.pop("stops", start + timedelta(hours=2))
        return EpisodeScenario(root, start=start, stops=stops, **kwargs)

    def test_tick_never_prepares_lookup_implicitly_even_in_legacy_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            sc = EpisodeScenario(Path(folder) / "rdp", start=START, stops=START + timedelta(hours=2))
            with patch.object(ResearchStore, "prepare_write_lookup", side_effect=AssertionError("AUTO_PREPARATION")):
                result = sc.tick(START + timedelta(seconds=5))
            self.assertEqual(result["_exit_code"], 0, result)
            self.assertFalse((sc.data_root / "research/write_lookup_v1").exists())

    def mature(self, sc):
        mint = synth_mint("MatureOperability")
        row = token_object(mint, price=1, liquidity=10000, holders=60)
        nominate(sc.market, START, {"toporganicscore": [row], "toptraded": [], "toptrending": []})
        sc.market.series[mint] = lambda now: row
        self.assertEqual(sc.tick(START + timedelta(seconds=5))["_exit_code"], 0)
        sc.operator(START + timedelta(minutes=11), "stop-intake")
        sc.tick(START + timedelta(hours=75))
        self.assertEqual(sc.activation_state(), "COMPLETE")

    def capture(self, sc, hours=80):
        return capture_freeze_export(observation_rdp=sc.data_root, ops_store=sc.ops_path,
                                     imported_cohort_ids=set(), as_of=START + timedelta(hours=hours),
                                     collection="OPPORTUNITY_EPISODES")

    def test_new_capture_invocation_new_as_of_reuses_frozen_closure_bytes(self):
        sc = self.scenario()
        self.mature(sc)
        first = self.capture(sc)
        second = self.capture(sc, 81)
        self.assertEqual(first["closure_receipt"], second["closure_receipt"])
        self.assertEqual(first["transfer_manifest"], second["transfer_manifest"])

    def test_malformed_frozen_closure_refuses_without_replacing_evidence(self):
        from solana_alpha_lab.factory.opportunity_episode_release import EpisodeReleaseError, CLOSURE_NAME
        sc = self.scenario()
        self.mature(sc)
        self.capture(sc)
        paths = list(sc.data_root.rglob(CLOSURE_NAME))
        self.assertEqual(len(paths), 1)
        from solana_alpha_lab.factory.observation_schedule import canonical_sha256
        invalid_time = json.loads(paths[0].read_bytes())
        invalid_time.pop("closure_receipt_sha256")
        invalid_time["as_of"] = "INVALID_TIMESTAMP"
        invalid_time["closure_receipt_sha256"] = canonical_sha256(invalid_time)
        for malformed in (b"[]", b'{"x":' + b'[' * 30000 + b'0' + b']' * 30000 + b'}',
                          json.dumps(invalid_time).encode()):
            paths[0].write_bytes(malformed)
            with self.assertRaises(EpisodeReleaseError) as caught:
                self.capture(sc, 81)
            self.assertEqual(caught.exception.code, "CLOSURE_FROZEN_UNREADABLE")
            self.assertEqual(paths[0].read_bytes(), malformed)

    def test_unverified_schedule_scope_keeps_collection_unknown(self):
        from solana_alpha_lab.factory.collector_read_model import build_collector_read_model
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        sc = self.scenario()
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            params = dict(store=store, now=START, schedule_sha256=sc.schedule["schedule_sha256"],
                          activation_id=sc.activation_id)
            self.assertEqual(build_collector_read_model(**params)["collection"], "OPPORTUNITY_EPISODES")
            with patch.object(store, "get_registered_schedule", return_value=None):
                unknown = build_collector_read_model(**params)
            self.assertEqual(unknown["collection"], "UNKNOWN")
            self.assertIsNone(unknown["episode_operability"])

    def test_two_real_activations_same_day_refuse_before_partial_capture(self):
        from tests.test_opportunity_episodes_harness_v1 import build_schedule, register_authorize_activate
        from solana_alpha_lab.factory.opportunity_episode_release import (
            EpisodeReleaseError, build_episode_closure_receipt)
        sc = self.scenario()
        mint = synth_mint("FragmentFirst")
        row = token_object(mint, price=1, liquidity=10000, holders=60)
        nominate(sc.market, START, {"toporganicscore": [row], "toptraded": [], "toptrending": []})
        sc.market.series[mint] = lambda now: row
        self.assertEqual(sc.tick(START + timedelta(seconds=5))["_exit_code"], 0)
        sc.tick(START + timedelta(hours=2, seconds=5))
        second_start = START + timedelta(hours=3)
        schedule = build_schedule(starts_at=second_start, stops_at=second_start + timedelta(hours=1),
            assignment=sc.assignment, schedule_key="OBS-OPPORTUNITY-EPISODES-FRAGMENT-V1")
        register_authorize_activate(sc.data_root, schedule, now=second_start, activation_id="ACT-FRAGMENT-SECOND")
        mint2 = synth_mint("FragmentSecond")
        row2 = token_object(mint2, price=2, liquidity=20000, holders=80)
        nominate(sc.market, second_start, {"toporganicscore": [row2], "toptraded": [], "toptrending": []})
        sc.market.series[mint2] = lambda now: row2
        from scripts.observation_schedule import main as cli_main
        from solana_alpha_lab.factory.observation_schedule_composition import TickPhysicalOverrides
        from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock
        from contextlib import redirect_stdout
        from io import StringIO
        at = second_start + timedelta(seconds=5)
        clock = AdvancingClock(at)
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["tick", "--once", "--data-root", str(sc.data_root),
                "--schedule-sha256", schedule["schedule_sha256"], "--activation-id", "ACT-FRAGMENT-SECOND"],
                physical_overrides=TickPhysicalOverrides(now=at, opener=SyntheticJupiter(sc.market, clock), pacing_clock=clock))
        self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(len(sc.admissions()), 2)
        cohort = sc.admissions()[0]["cohort_id"]
        for invoke in (lambda: self.capture(sc), lambda: build_episode_closure_receipt(
                ops_store=sc.ops_path, observation_rdp=sc.data_root,
                schedule_sha256=sc.schedule["schedule_sha256"], activation_id=sc.activation_id,
                cohort_id=cohort, as_of=START + timedelta(hours=80))):
            with self.assertRaises(EpisodeReleaseError) as caught:
                invoke()
            self.assertEqual(caught.exception.code, "EPISODE_COHORT_FRAGMENTED_UNSUPPORTED")

    def test_mixed_boundary_degradation_budget_restart_and_drain(self):
        started = time.perf_counter()
        start = datetime(2026, 10, 11, 23, 45, tzinfo=UTC)  # UTC day + Monday cycle boundary
        sc = self.scenario(start=start, observation_overrides={"availability_grace_seconds": 60})
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        store = ObservationScheduleStore(sc.ops_path)
        lease = store.acquire_lease("known-legacy-tail-fixture", clock=start)
        store.save_accounting(schedule_sha256="ee" * 32, activation_id="ACT-KNOWN-LEGACY-TAIL",
            utc_day="2026-10-11", values={"provider_calls": 1, "modeled_credits": 1,
             "candidates": 0, "members": 0, "raw_bytes": 1, "canonical_bytes": 1,
             "last_provider_call_at": "2026-10-11T23:45:05Z"}, clock=start)
        seeded_calls = int(sc.schedule["budgets"]["provider_calls_per_utc_day_max"]) - 7
        store.save_accounting(schedule_sha256=sc.schedule["schedule_sha256"], activation_id=sc.activation_id,
            utc_day="2026-10-12", values={"provider_calls": seeded_calls, "modeled_credits": seeded_calls,
             "candidates": 0, "members": 0, "raw_bytes": seeded_calls, "canonical_bytes": seeded_calls,
             "last_provider_call_at": None}, clock=start)
        store.release_lease(lease)
        store.close()
        mint = synth_mint("MixedBoundary")
        row = token_object(mint, price=1, liquidity=10000, holders=60)
        nominate(sc.market, start, {"toporganicscore": [row], "toptraded": [], "toptrending": []})
        sc.market.series[mint] = lambda now: token_object(mint, price=1 + now.minute / 1000,
                                                        liquidity=10000, holders=None if now.day == 11 else 60)
        first = sc.tick(start + timedelta(seconds=5))
        self.assertEqual(first["_calls"][0]["at"], "2026-10-11T23:45:08Z")
        self.assertEqual(len(sc.admissions()), 1)
        sc.tick(start + timedelta(minutes=10, seconds=2), fault="EPISODE_AFTER_CALL_COMPLETE")
        recovered = sc.tick(start + timedelta(minutes=10, seconds=40))
        self.assertEqual(recovered["_calls"], [])
        sc.tick(start + timedelta(minutes=15, seconds=2), fault="EPISODE_AFTER_CALL_START")
        ambiguous = sc.tick(start + timedelta(minutes=15, seconds=40))
        self.assertEqual([call["kind"] for call in ambiguous["_calls"]], ["category"] * 3)
        self.assertEqual(sc.slot_states(sc.admissions()[0]["episode_id"])["E600"], ("CENSORED", "ATTEMPT_OUTCOME_UNKNOWN"))
        sc.market.latency = lambda kind, now: 61 if kind == "search" and now.minute == 5 else 1
        sc.tick(start + timedelta(minutes=20, seconds=2))
        sc.market.search_failures[start + timedelta(minutes=25)] = 429
        sc.tick(start + timedelta(minutes=25, seconds=2))
        original = SyntheticJupiter.open
        def timeout(opener, url):
            if "/search?" in url:
                opener.calls.append({"kind": "search", "at": opener.clock.now().isoformat(), "status": "TIMEOUT"})
                raise TimeoutError("SYNTHETIC_TIMEOUT")
            return original(opener, url)
        with patch.object(SyntheticJupiter, "open", timeout):
            sc.tick(start + timedelta(minutes=30, seconds=2))
        exhausted = sc.tick(start + timedelta(minutes=35, seconds=2))
        repeated = sc.tick(start + timedelta(minutes=35, seconds=40))
        self.assertEqual(exhausted["stop_reason"], "BLOCKED_BUDGET")
        self.assertEqual(exhausted["_calls"], [])
        self.assertEqual(repeated["_calls"], [])
        counters = sc.query("SELECT utc_day, SUM(provider_calls) FROM accounting_counters GROUP BY utc_day ORDER BY utc_day")
        self.assertEqual(counters, [("2026-10-11", 5), ("2026-10-12", seeded_calls + 7)])
        states = sc.slot_states(sc.admissions()[0]["episode_id"])
        self.assertEqual(states["E900"][0], "CENSORED_LATE")
        self.assertIn("429", str(states["E1200"][1]))
        self.assertIn("TIMEOUT", str(states["E1500"][1]))
        self.assertEqual(len(sc.admissions()), 1)  # cycle change cannot reset an active mint
        status = sc.operator(start + timedelta(minutes=36), "status")["collector"]
        self.assertEqual(status["discovery_coverage_class"], "NOT_APPLICABLE_EPISODE_NOMINATION")
        self.assertIsNone(status["source_poll_age"])
        self.assertGreater(status["episode_operability"]["field_values_missing"], 0)
        stopped = sc.operator(start + timedelta(minutes=37), "stop-intake")
        self.assertEqual(stopped["state"], "DRAINING")
        self.assertNotEqual(sc.operator(start + timedelta(minutes=38), "pause")["_exit_code"], 0)
        self.assertNotEqual(sc.operator(start + timedelta(minutes=39), "resume")["_exit_code"], 0)
        final = sc.tick(start + timedelta(hours=75))
        self.assertEqual(final["activation_state"], "COMPLETE")
        self.assertEqual(final["_calls"], [])
        self.assertEqual(sc.unpublished(), 0)
        report = {"rehearsal": "R2", "entry": "observation_schedule.py tick --once", "wall_seconds": time.perf_counter()-started,
                  "admissions": len(sc.admissions()), "account_counters": counters, "known_legacy_tail_calls": 1,
                  "synthetic_seeded_budget_debit": seeded_calls,
                  "approved_live_account_envelope": "UNKNOWN", "stop": stopped["state"], "tail": final["activation_state"],
                  "ticks": [{"terminal": x.get("terminal"), "stop_reason": x.get("stop_reason"), "attempts": len(x["_calls"])} for x in sc.ticks],
                  "operator": status["episode_operability"],
                  "peak_rss_bytes": __import__("scripts.prove_opportunity_episode_operability", fromlist=["peak_rss"]).peak_rss(),
                  "boundary_slot_states": {key: states[key] for key in ("E300", "E600", "E900", "E1200", "E1500")}}
        (sc.data_root.parent / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    def test_pressure_stops_intake_stickily_and_keeps_committed_tail(self):
        sc = self.scenario()
        mint = synth_mint("Pressure")
        row = token_object(mint, price=1, liquidity=10000, holders=60)
        nominate(sc.market, START, {"toporganicscore": [row], "toptraded": [], "toptrending": []})
        sc.market.series[mint] = lambda now: row
        sc.tick(START + timedelta(seconds=5))
        disk = namedtuple("disk", "total used free")(100000000000, 99999999999, 1)
        with patch("solana_alpha_lab.factory.opportunity_episode_tick.shutil.disk_usage", return_value=disk):
            pressure = sc.tick(START + timedelta(minutes=15, seconds=5))
        self.assertEqual(pressure["stop_reason"], "DRAIN_RESERVE_PRESSURE")
        self.assertEqual(pressure["activation_state"], "DRAINING")
        after = sc.tick(START + timedelta(minutes=20, seconds=5))
        self.assertFalse(any(call["kind"] == "category" for call in after["_calls"]))
        self.assertEqual(len(sc.admissions()), 1)
        final = sc.tick(START + timedelta(hours=75))
        self.assertEqual(final["activation_state"], "COMPLETE")
        self.assertEqual(sc.unpublished(), 0)

    def test_pacing_round_boundary_reserves_the_actual_nomination_round(self):
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        sc = self.scenario(daily_ceiling=24, active_cap=48)
        at = START + timedelta(minutes=44, seconds=59)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            lease = store.acquire_lease("known-legacy-round-boundary-fixture", clock=at)
            self.assertIsNotNone(lease)
            store.save_accounting(schedule_sha256="ee" * 32, activation_id="ACT-KNOWN-LEGACY-TAIL",
                utc_day="2026-10-05", values={"provider_calls": 1, "modeled_credits": 1,
                "candidates": 0, "members": 0, "raw_bytes": 1, "canonical_bytes": 1,
                "last_provider_call_at": "2026-10-05T00:44:58Z"}, clock=at)
            store.release_lease(lease)
        row = token_object(synth_mint("RoundBoundaryReserve"), price=1, liquidity=10000, holders=60)
        nominate(sc.market, START + timedelta(minutes=45),
            {"toporganicscore": [row], "toptraded": [], "toptrending": []})
        free = 3 * 1024**3
        disk = namedtuple("disk", "total used free")(100 * 1024**3, 97 * 1024**3, free)
        with patch("solana_alpha_lab.factory.opportunity_episode_tick.shutil.disk_usage", return_value=disk):
            result = sc.tick(at)
        reserve = result["drain_headroom"]
        self.assertEqual(result["_exit_code"], 2, result)  # TICK_PARTIAL: reserve refuses intake
        self.assertEqual(reserve["decision_at"], "2026-10-05T00:45:01Z")
        self.assertEqual(reserve["round_started_at"], "2026-10-05T00:45:00Z")
        self.assertEqual(reserve["prospective_reserve_bytes"], 138 * (32 * 1024**2 + 128 * 1024))
        self.assertGreater(reserve["required_free_bytes"], free)
        self.assertEqual(result["stop_reason"], "DRAIN_RESERVE_PRESSURE")
        self.assertEqual(result["activation_state"], "COMPLETE")  # empty tail drains immediately
        self.assertEqual(sc.admissions(), [])
        self.assertEqual(result["_calls"], [])
        (sc.data_root.parent / "report.json").write_bytes((json.dumps({"status": "PASS",
            "initial_tick_at": "2026-10-05T00:44:59Z", "drain_headroom": reserve,
            "activation_state": result["activation_state"], "admissions": 0,
            "synthetic_provider_attempts": 0}, indent=2) + "\n").encode())

    def test_legacy_episode_storage_option_refuses_before_any_activation_write(self):
        from tests.test_observation_schedule_lifecycle import ROOT, NOW, GIT, _phrase
        from solana_alpha_lab.factory.observation_schedule import load_observation_schedule
        from solana_alpha_lab.factory.observation_schedule_lifecycle import (
            register_schedule, authorize_schedule, activate_schedule, ObservationLifecycleError)
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "rdp"
            root.mkdir()
            document = load_observation_schedule(ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml")
            with closing(ObservationScheduleStore(root / "ops.sqlite")) as store:
                common = dict(root=ROOT, data_root=root, store=store, now=NOW, producer_git_sha=GIT)
                registered = register_schedule(document=document, **common)
                digest = registered["schedule_sha256"]
                authorize_schedule(schedule_sha256=digest, phrase=_phrase(document), **common)
                before = {p.relative_to(root).as_posix(): p.read_bytes()
                          for p in (root / "research").rglob("*") if p.is_file()}
                with self.assertRaisesRegex(ObservationLifecycleError, "EPISODE_STORAGE_SCHEDULE_ONLY"):
                    activate_schedule(schedule_sha256=digest, activation_id="ACT-LEGACY-BAD-OPTION",
                                      storage_commissioning={}, **common)
                self.assertIsNone(store.get_activation(digest, "ACT-LEGACY-BAD-OPTION"))
                after = {p.relative_to(root).as_posix(): p.read_bytes()
                         for p in (root / "research").rglob("*") if p.is_file()}
                self.assertEqual(before, after)

    def test_factory_topology_unknown_refuses_before_activation(self):
        from tests.test_opportunity_episodes_harness_v1 import (
            ROOT, PRODUCER, authority_phrase, build_schedule, write_assignment, storage_commissioning_fixture)
        from solana_alpha_lab.factory.observation_schedule_lifecycle import (
            register_schedule, authorize_schedule, activate_schedule, ObservationLifecycleError)
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        from solana_alpha_lab.factory.observation_schedule import canonical_sha256
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "rdp"
            ResearchStore(root).prepare_write_lookup()
            schedule = build_schedule(starts_at=START, stops_at=START + timedelta(hours=48),
                                      assignment=write_assignment(root, []), daily_ceiling=24, active_cap=48)
            with closing(ObservationScheduleStore(root / "observation_schedule_state.sqlite")) as store:
                common = dict(root=ROOT, data_root=root, store=store, now=START, producer_git_sha=PRODUCER)
                register_schedule(document=schedule, **common)
                authorize_schedule(schedule_sha256=schedule["schedule_sha256"], phrase=authority_phrase(schedule), **common)
                scope = dict(schedule_sha256=schedule["schedule_sha256"], activation_id="ACT-STORAGE-GATE", **common)
                with self.assertRaisesRegex(ObservationLifecycleError, "EPISODE_STORAGE_COMMISSIONING_REQUIRED"):
                    activate_schedule(**scope)
                envelope = storage_commissioning_fixture(root, schedule, scope["activation_id"])
                envelope.pop("envelope_sha256")
                envelope["factory_storage_gate"] = "UNKNOWN"
                envelope["envelope_sha256"] = canonical_sha256(envelope)
                with self.assertRaisesRegex(ObservationLifecycleError, "FACTORY_STORAGE_COMMISSIONING_REQUIRED"):
                    activate_schedule(storage_commissioning=envelope, **scope)
                self.assertIsNone(store.get_activation(schedule["schedule_sha256"], scope["activation_id"]))

    def test_commissioned_storage_binding_is_immutable_and_unknown_does_not_drain(self):
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore, ObservationScheduleStoreError
        from solana_alpha_lab.factory.observation_schedule_lifecycle import activate_schedule, ObservationLifecycleError
        from tests.test_opportunity_episodes_harness_v1 import ROOT, PRODUCER
        sc = self.scenario()
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            row = store.get_activation(sc.schedule["schedule_sha256"], sc.activation_id)
            changed = dict(row["payload"]["storage_commissioning"])
            changed["fixed_local_reserve_bytes"] += 1
            with self.assertRaisesRegex(ObservationScheduleStoreError, "DENY_RETROACTIVE_MUTATION"):
                store.upsert_activation({**row, "payload": {**row["payload"], "storage_commissioning": changed}}, clock=START)
            with self.assertRaisesRegex(ObservationScheduleStoreError, "DENY_RETROACTIVE_MUTATION"):
                store.transition_activation(schedule_sha256=sc.schedule["schedule_sha256"], activation_id=sc.activation_id,
                    new_state="PAUSED_OPERATOR", payload={"storage_commissioning": changed}, clock=START)
            with self.assertRaisesRegex(ObservationLifecycleError, "EPISODE_STORAGE_REPLAY_CONFLICT"):
                activate_schedule(root=ROOT, data_root=sc.data_root, store=store, schedule_sha256=sc.schedule["schedule_sha256"],
                    activation_id=sc.activation_id, now=START, producer_git_sha=PRODUCER, storage_commissioning=changed)
            replay = activate_schedule(root=ROOT, data_root=sc.data_root, store=store, schedule_sha256=sc.schedule["schedule_sha256"],
                    activation_id=sc.activation_id, now=START, producer_git_sha=PRODUCER)
            self.assertEqual(replay["terminal"], "ACTIVATE_REPLAY")
            # Simulate a pre-upgrade activation without a bound local envelope.
            # Direct fixture SQL is neither a supported commissioning migration nor production work.
            payload = dict(row["payload"])
            payload.pop("storage_commissioning")
            store._conn.execute("UPDATE schedule_activations SET payload_json=? WHERE schedule_sha256=? AND activation_id=?",
                (json.dumps(payload), sc.schedule["schedule_sha256"], sc.activation_id))
            store._conn.commit()
        result = sc.tick(START + timedelta(seconds=5))
        self.assertEqual(result["stop_reason"], "PRODUCER_LOCAL_ENVELOPE_REQUIRED")
        self.assertEqual(result["drain_headroom"]["status"], "COMMISSIONING_REQUIRED")
        self.assertEqual(sc.activation_state(), "ACTIVE")
        self.assertEqual(len(sc.admissions()), 0)
        self.assertFalse(result["_calls"])

    def test_canary_24_per_day_48h_local_envelope_survives_model_proxy_and_unsafe_drains(self):
        from solana_alpha_lab.factory.hot90_storage_admission import episode_factory_storage_forecast
        from solana_alpha_lab.factory.opportunity_episodes import round_quota
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        from solana_alpha_lab.factory.observation_schedule import parse_utc
        sc = self.scenario(daily_ceiling=24, active_cap=48, stops=START + timedelta(hours=48))
        free = 78_746_222_592
        disk = namedtuple("disk", "total used free")(102_888_095_744, 102_888_095_744 - free, free)
        checkpoints = []
        mints = [synth_mint(f"Canary{index}Z") for index in range(192)]
        self.assertEqual(len(set(mints)), 192)
        with patch("solana_alpha_lab.factory.opportunity_episode_tick.shutil.disk_usage", return_value=disk):
            for index in range(192):
                at = START + timedelta(minutes=15 * index)
                mint = mints[index]
                row = token_object(mint, price=1, liquidity=10000, holders=60)
                nominate(sc.market, at, {"toporganicscore": [row] if round_quota(24, index % 96) else [],
                                         "toptraded": [], "toptrending": []})
                sc.market.series[mint] = lambda now, value=row: value
                # Day-two start stays inside the ordinary round/grace window,
                # after day-one call completion, so rolling-24h does not hold
                # an otherwise available ticket for a few seconds of IO jitter.
                result = sc.tick(at + timedelta(seconds=5 + 30 * (index // 96)))
                self.assertEqual(result["_exit_code"], 0, result)
                self.assertEqual(sc.activation_state(), "ACTIVE")
                reserve = result["drain_headroom"]
                self.assertEqual(reserve["status"], "LOCAL_HEADROOM")
                forecast = episode_factory_storage_forecast(
                    remaining_slots=reserve["remaining_slots"], prospective_slots=round_quota(24, index % 96) * 138,
                    response_cap_bytes=sc.schedule["budgets"]["response_decoded_bytes_max"], free_bytes=free)
                checkpoints.append({"round": index, "admitted_episodes": len(sc.admissions()),
                                    "local": reserve, "six_copy_advisory_status": forecast["status"]})
                if index == 95:
                    self.assertEqual(len(sc.admissions()), 24)
        self.assertEqual(len(sc.admissions()), 48)
        self.assertTrue(any(item["six_copy_advisory_status"] == "STOP_NEW_INTAKE" for item in checkpoints))
        unsafe = disk._replace(free=1)
        with patch("solana_alpha_lab.factory.opportunity_episode_tick.shutil.disk_usage", return_value=unsafe):
            pressure = sc.tick(START + timedelta(hours=47, minutes=50))
        self.assertEqual(pressure["activation_state"], "DRAINING")
        self.assertEqual(pressure["stop_reason"], "DRAIN_RESERVE_PRESSURE")
        self.assertEqual(len(sc.admissions()), 48)
        self.assertFalse(any(call["kind"] == "category" for call in pressure["_calls"]))
        deadline = sc.query("SELECT MAX(deadline_at) FROM due_observations")[0][0]
        tail = sc.tick(parse_utc(deadline) + timedelta(seconds=1))
        self.assertEqual(tail["activation_state"], "COMPLETE")
        self.assertEqual(sc.unpublished(), 0)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            projection = store.episode_operability_projection(schedule_sha256=sc.schedule["schedule_sha256"],
                activation_id=sc.activation_id, now=parse_utc(deadline) + timedelta(seconds=1))
        self.assertEqual((projection["admitted_episodes"], projection["open_episodes"], projection["terminal_episodes"]), (48, 0, 48))
        self.assertEqual(sum(projection["slot_states"].values()), 48 * 138)
        self.assertFalse(any(key.endswith("_obligations") for key in projection))
        report = {"status": "PASS", "evidence_class": "SYNTHETIC_LOCAL_CONTROL", "canary_days": 2,
                  "daily_ceiling": 24, "active_cap": 48, "free_bytes_order": free,
                  "response_cap_unchanged": sc.schedule["budgets"]["response_decoded_bytes_max"],
                  "checkpoints": checkpoints, "unsafe_pressure": pressure["drain_headroom"],
                  "tail": tail["activation_state"], "unpublished": sc.unpublished(), "operator": projection,
                  "factory_actual_topology": "UNKNOWN_NOT_LIVE_COMMISSIONING"}
        (sc.data_root.parent / "report.json").write_bytes((json.dumps(report, indent=2) + "\n").encode('utf-8'))

    def test_operational_packet_preserves_episode_scope_and_storage_history_writes(self):
        from solana_alpha_lab.factory.collector_operational_packet import (
            append_storage_history, build_collector_operational_packet)
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        sc = self.scenario()
        self.mature(sc)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            packet = build_collector_operational_packet(
                root=sc.data_root.parent, store=store, now=START + timedelta(hours=76),
                observation_rdp=sc.data_root, schedule_sha256=sc.schedule["schedule_sha256"],
                activation_id=sc.activation_id, remote_config={}, environ={})
        self.assertEqual(packet["collection"], "OPPORTUNITY_EPISODES")
        self.assertEqual(packet["episode_operability"]["open_episodes"], 0)
        self.assertEqual(packet["episode_operability"]["unpublished_backlog"], 0)
        path = append_storage_history(sc.data_root.parent, observed_at=packet["observed_at"],
            disk_used_pct=40, sqlite_bytes=123, rdp_bytes=456)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
            {"observed_at": packet["observed_at"], "disk_used_pct": 40,
             "sqlite_bytes": 123, "rdp_bytes": 456})

    def test_mixed_legacy_metadata_never_turns_unknown_missingness_into_zero(self):
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        sc = self.scenario()
        self.mature(sc)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            params = {"schedule_sha256": sc.schedule["schedule_sha256"],
                      "activation_id": sc.activation_id, "now": START + timedelta(hours=76)}
            # A known zero subset must not conceal one legacy unknown terminal row.
            store._conn.execute("UPDATE due_observations SET payload_json="
                                "json_set(payload_json, '$.field_value_missing_count', 0)")
            exact = store.episode_operability_projection(**params)
            self.assertEqual(exact["execution_metadata_status"], "EXACT")
            self.assertEqual(exact["field_values_missing"], 0)
            row = store._conn.execute("SELECT rowid, payload_json FROM due_observations LIMIT 1").fetchone()
            payload = json.loads(row[1])
            del payload["field_value_missing_count"]
            store._conn.execute("UPDATE due_observations SET payload_json=? WHERE rowid=?",
                                (json.dumps(payload), row[0]))
            missing = store.episode_operability_projection(**params)
            self.assertEqual(missing["execution_metadata_status"], "UNKNOWN_LEGACY_METADATA")
            self.assertIsNone(missing["field_values_missing"])
            self.assertIsNotNone(missing["attempted_slots"])
            store._conn.execute("UPDATE due_observations SET payload_json='{}' WHERE rowid=?", (row[0],))
            legacy = store.episode_operability_projection(**params)
            self.assertIsNone(legacy["field_values_missing"])
            self.assertIsNone(legacy["attempted_slots"])

    def test_call_reservation_covers_request_day_after_durable_start_delay(self):
        from tests.test_opportunity_episodes_harness_v1 import ROOT
        from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        from solana_alpha_lab.factory.opportunity_episode_tick import _EpisodeTick, SEARCH_PRIMITIVE
        from solana_alpha_lab.factory.observation_primitives import search_url
        start = datetime(2026, 10, 11, 23, 45, tzinfo=UTC)
        sc = self.scenario(start=start)
        at = start + timedelta(minutes=14, seconds=59)
        clock = AdvancingClock(at)
        mint = synth_mint("MidnightReservation")
        sc.market.series[mint] = lambda now: token_object(mint, price=1, liquidity=10000, holders=60)
        store = ObservationScheduleStore(sc.ops_path)
        self.addCleanup(store.close)
        lease = store.acquire_lease("reservation-boundary-unit", clock=at)
        activation = store.get_activation(sc.schedule["schedule_sha256"], sc.activation_id)
        tick = _EpisodeTick(root=ROOT, data_root=sc.data_root, store=store, schedule=sc.schedule,
            activation=activation, now=at, opener=SyntheticJupiter(sc.market, clock), credential_loader=None,
            producer_git_sha="a"*40, clock=clock, fault_after=None, provider_call_wall_seconds=None, redact_with=None)
        original = store.start_call
        def durable_delay(**kwargs):
            result = original(**kwargs)
            clock.sleep(2)
            return result
        with patch.object(store, "start_call", side_effect=durable_delay):
            terminal, result = tick._call(primitive_id=SEARCH_PRIMITIVE, url=search_url([mint]),
                occurrence="UTC-RESERVATION-UNIT", expected_entities=[mint], claim_identity=[mint])
        self.assertEqual(terminal, "CALLED")
        self.assertTrue(result["request_started_at"].startswith("2026-10-12T00:00:"))
        self.assertEqual(sc.query("SELECT utc_day, provider_calls FROM accounting_counters ORDER BY utc_day"),
                         [("2026-10-11", 1), ("2026-10-12", 1)])
        store.release_lease(lease)

    def test_credential_delay_to_exhausted_new_day_blocks_before_transport_and_start(self):
        from tests.test_opportunity_episodes_harness_v1 import ROOT
        from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        from solana_alpha_lab.factory.opportunity_episode_tick import _EpisodeTick, SEARCH_PRIMITIVE
        from solana_alpha_lab.factory.observation_primitives import search_url
        start = datetime(2026, 10, 11, 23, 45, tzinfo=UTC)
        sc = self.scenario(start=start)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            lease = store.acquire_lease("credential-midnight-budget-unit", clock=start)
            limit = sc.schedule["budgets"]["provider_calls_per_utc_day_max"]
            store.save_accounting(schedule_sha256=sc.schedule["schedule_sha256"], activation_id=sc.activation_id,
                utc_day="2026-10-12", values={"provider_calls":limit,"modeled_credits":limit,
                    "raw_bytes":limit,"canonical_bytes":limit,"candidates":0,"members":0,
                    "last_provider_call_at":None}, clock=start)
            store.release_lease(lease)
        at = start + timedelta(minutes=14, seconds=59)
        clock = AdvancingClock(at)
        opener = SyntheticJupiter(sc.market, clock)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            lease = store.acquire_lease("credential-midnight-call-unit", clock=at)
            tick = _EpisodeTick(root=ROOT, data_root=sc.data_root, store=store, schedule=sc.schedule,
                activation=store.get_activation(sc.schedule["schedule_sha256"], sc.activation_id),
                now=at, opener=opener, credential_loader=None, producer_git_sha="a"*40,
                clock=clock, fault_after=None, provider_call_wall_seconds=None, redact_with=None)
            with patch.object(tick, "_credential", side_effect=lambda: clock.sleep(2)):
                terminal, result = tick._call(primitive_id=SEARCH_PRIMITIVE,
                    url=search_url([synth_mint("CredentialMidnight")]), occurrence="CREDENTIAL-MIDNIGHT-UNIT",
                    expected_entities=None, claim_identity=[])
            self.assertEqual((terminal, result), ("BLOCKED_BUDGET", None))
            self.assertEqual(opener.calls, [])
            store.release_lease(lease)
        self.assertEqual(sc.query("SELECT COUNT(*) FROM call_ledger"), [(0,)])
        self.assertEqual(sc.query("SELECT utc_day,provider_calls FROM accounting_counters"),
                         [("2026-10-12", limit)])

    def test_started_delay_to_exhausted_new_day_preserves_old_debit_without_transport(self):
        from tests.test_opportunity_episodes_harness_v1 import ROOT
        from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        from solana_alpha_lab.factory.opportunity_episode_tick import _EpisodeTick, SEARCH_PRIMITIVE, EpisodeTickError
        from solana_alpha_lab.factory.observation_primitives import search_url
        start = datetime(2026, 10, 11, 23, 45, tzinfo=UTC)
        sc = self.scenario(start=start)
        at = start + timedelta(minutes=14, seconds=59)
        clock = AdvancingClock(at)
        opener = SyntheticJupiter(sc.market, clock)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            lease = store.acquire_lease("started-midnight-exhausted-unit", clock=at)
            limit = sc.schedule["budgets"]["provider_calls_per_utc_day_max"]
            store.save_accounting(schedule_sha256=sc.schedule["schedule_sha256"], activation_id=sc.activation_id,
                utc_day="2026-10-12", values={"provider_calls":limit,"modeled_credits":limit,
                    "raw_bytes":limit,"canonical_bytes":limit,"candidates":0,"members":0,
                    "last_provider_call_at":None}, clock=at)
            tick = _EpisodeTick(root=ROOT, data_root=sc.data_root, store=store, schedule=sc.schedule,
                activation=store.get_activation(sc.schedule["schedule_sha256"], sc.activation_id), now=at,
                opener=opener, credential_loader=None, producer_git_sha="a"*40, clock=clock,
                fault_after=None, provider_call_wall_seconds=None, redact_with=None)
            original = store.start_call
            def durable_delay(**kwargs):
                result = original(**kwargs)
                clock.sleep(2)
                return result
            with patch.object(store, "start_call", side_effect=durable_delay):
                with self.assertRaisesRegex(EpisodeTickError, "BLOCKED_BUDGET"):
                    tick._call(primitive_id=SEARCH_PRIMITIVE, url=search_url([synth_mint("StartedExhausted")]),
                        occurrence="STARTED-MIDNIGHT-EXHAUSTED", expected_entities=None, claim_identity=[])
            self.assertEqual(store.call_state("STARTED-MIDNIGHT-EXHAUSTED"), "STARTED")
            self.assertEqual(opener.calls, [])
            store.release_lease(lease)
        self.assertEqual(sc.query("SELECT utc_day,provider_calls FROM accounting_counters ORDER BY utc_day"),
                         [("2026-10-11", 1), ("2026-10-12", limit)])


if __name__ == "__main__":
    unittest.main()
