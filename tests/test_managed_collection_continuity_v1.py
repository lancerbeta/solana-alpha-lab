"""I3_MANAGED_COLLECTION_CONTINUITY_V1: one approved profile, automatic lawful children.

Production owners only: the public ``scripts/observation_schedule.py`` entry, the
lifecycle/authority/activation owners, the episode tick, the shared-account gate and
the ResearchStore events. Only transport, the clock and authored market bytes are
synthetic. Expected sets and totals are authored literals or raw SQL, never the
managed helpers under test.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from collections import namedtuple
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from tests.test_observation_shared_account_budget_v1 import SharedWallClock
from tests.test_opportunity_episodes_harness_v1 import (
    EpisodeScenario,
    cli_command,
    cli_tick,
    nominate,
    synth_mint,
    token_object,
)
from solana_alpha_lab.factory import managed_collection as mc
from solana_alpha_lab.factory.hot90_storage_admission import (
    EpisodeStorageError,
    validate_episode_storage_commissioning,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.research_store import RecordKind

SCOPE = "JUPITER-MANAGED-ACCOUNT-1"
D0 = datetime(2026, 10, 17, 0, 0, tzinfo=UTC)
D1 = D0 + timedelta(days=1)
D2 = D0 + timedelta(days=2)
D3 = D0 + timedelta(days=3)
ARTIFACT = "a1" * 32
LIMIT_ARGS = ["--provider-calls-per-utc-day-max", "1200", "--modeled-credits-per-utc-day-max", "1200",
              "--provider-calls-lifetime-max", "2000000"]
Usage = namedtuple("Usage", "total used free")


def sql(path: Path, query: str, params: tuple = ()) -> list[tuple]:
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
        return list(conn.execute(query, params).fetchall())


class ManagedScenario(EpisodeScenario):
    """Seed activation X (the protected bridge) plus the managed profile on top of it."""

    def __init__(self, root: Path, **kwargs) -> None:
        super().__init__(root, start=D0, stops=D1, **kwargs)
        self.proposal: dict | None = None

    def cmd(self, at: datetime, *argv: str) -> dict:
        return cli_command(self.data_root, at, *argv)

    def tick(self, at: datetime, *, fault: str | None = None) -> dict:
        # Several activations share one physical clock, as the production WallClock does.
        result = cli_tick(self.data_root, self.market, at, env_fault=fault, pacing_clock=SharedWallClock(at))
        self.ticks.append(result)
        return result

    def commission_account(self, at: datetime = D0) -> None:
        plan = self.cmd(at, "account-budget-prepare", "--account-scope-id", SCOPE, *LIMIT_ARGS)
        self.assertion_ok(plan["terminal"] == "ACCOUNT_BUDGET_PLAN_READY", plan)
        applied = self.cmd(at, "account-budget-apply", "--account-scope-id", SCOPE, *LIMIT_ARGS,
                           "--expected-plan-sha256", plan["plan_sha256"])
        self.assertion_ok(applied["terminal"] == "ACCOUNT_BUDGET_APPLIED", applied)

    @staticmethod
    def assertion_ok(condition: bool, detail: object) -> None:
        if not condition:
            raise AssertionError(detail)

    def profile_args(self, *extra: str, not_before: datetime | None = D1) -> list[str]:
        args = ["--template-schedule-sha256", self.schedule["schedule_sha256"],
                "--account-scope-id", SCOPE, "--storage-basis-activation-id", self.activation_id,
                "--protected-bridge-activation-id", self.activation_id]
        if not_before is not None:
            args += ["--bootstrap-not-before", mc.render_utc(not_before)]
        return args + list(extra)

    def plan(self, at: datetime, *extra: str, **kwargs) -> dict:
        return self.cmd(at, "collection-plan", *self.profile_args(*extra, **kwargs))

    def apply(self, at: datetime, *extra: str, **kwargs) -> dict:
        plan = self.plan(at, *extra, **kwargs)
        self.assertion_ok(plan["terminal"] == "MANAGED_PLAN_READY", plan)
        self.proposal = plan
        return self.cmd(at, "collection-apply", *self.profile_args(*extra, **kwargs),
                        "--expected-proposal-sha256", plan["proposal_sha256"], "--phrase", plan["exact_owner_phrase"])

    def backup(self, at: datetime) -> dict:
        return self.cmd(at, "collection-record-backup", "--checkpoint-at", mc.render_utc(at - timedelta(minutes=5)),
                        "--artifact-sha256", ARTIFACT, "--coverage", "FULL_OPS_STORE")

    def status(self, at: datetime) -> dict:
        return self.cmd(at, "collection-status")

    def nominate_round(self, at: datetime, label: str, count: int = 1) -> list[str]:
        mints = [synth_mint(f"{label}{index}") for index in range(count)]
        rows = [token_object(mint, price=1, liquidity=10000, holders=60) for mint in mints]
        nominate(self.market, at, {"toporganicscore": rows, "toptraded": [], "toptrending": []})
        for mint, row in zip(mints, rows):
            self.market.series[mint] = lambda _now, row=row: row
        return mints

    def admissions_by_activation(self) -> dict[str, int]:
        return dict(sql(self.ops_path, "SELECT activation_id, COUNT(*) FROM episode_admissions GROUP BY activation_id"))

    def children(self) -> list[tuple]:
        return sql(self.ops_path, "SELECT utc_day, state, activation_id, profile_revision FROM managed_children "
                                  "ORDER BY utc_day")

    def derived_receipts(self) -> list[tuple]:
        return sql(self.ops_path, "SELECT authority_id, json_extract(payload_json,'$.authority_basis'), "
                                  "json_extract(payload_json,'$.standing_grant_sha256') FROM authority_receipts "
                                  "WHERE json_extract(payload_json,'$.authority_basis') = 'STANDING_GRANT' "
                                  "ORDER BY created_at")


class ManagedBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sc = ManagedScenario(Path(self.tmp.name) / "rdp")
        self.sc.commission_account()

    def commission_profile(self, *extra: str, at: datetime = D0 + timedelta(hours=1), **kwargs) -> dict:
        applied = self.sc.apply(at, *extra, **kwargs)
        self.assertEqual(applied["terminal"], "MANAGED_APPLIED", applied)
        self.assertEqual(self.sc.backup(at)["terminal"], "MANAGED_BACKUP_RECEIPT_RECORDED")
        return applied


class ManagedVerticalTests(ManagedBase):
    def test_three_utc_days_one_owner_phrase_no_manual_child(self) -> None:
        sc = self.sc
        seed_authority = sql(sc.ops_path, "SELECT receipt_sha256, payload_json FROM authority_receipts")
        self.commission_profile()
        tails: dict[str, list[str]] = {}
        # Day 0: X is the protected bridge; the controller waits and never competes.
        first_round = D0 + timedelta(minutes=30)
        sc.nominate_round(first_round, "X0")
        idle = sc.tick(first_round + timedelta(seconds=5))
        self.assertEqual(idle["managed"]["terminal"], "RECONCILE_WAIT_BOOTSTRAP_NOT_BEFORE", idle)
        self.assertEqual(sc.children(), [])
        # Day 1: X closes naturally and the first child opens in the same public tick.
        for day, label in ((D1, "C1"), (D2, "C2"), (D3, "C3")):
            sc.backup(day - timedelta(hours=1))
            sc.nominate_round(day, label, count=2)
            result = sc.tick(day + timedelta(seconds=5))
            self.assertEqual(result["managed"]["terminal"], "RECONCILE_CHILD_ACTIVATED", result)
            self.assertEqual(result["terminal"] in {"TICK_COMPLETE", "TICK_PARTIAL"}, True, result)
            tails[day.date().isoformat()] = [item["activation_id"] for item in result["activations"]]
            # A second tick in the same day does not create or reactivate anything.
            again = sc.tick(day + timedelta(minutes=20))
            self.assertEqual(again["managed"]["terminal"], "RECONCILE_INTAKE_OK", again)
        rows = sc.children()
        self.assertEqual([row[0] for row in rows], ["2026-10-18", "2026-10-19", "2026-10-20"])
        self.assertEqual({row[1] for row in rows[:2]}, {"INTAKE_COMPLETE"})
        self.assertEqual(rows[2][1], "ACTIVATED")
        self.assertEqual({row[3] for row in rows}, {1})
        # One approval for the profile; every child authority is derived from that one grant.
        derived = sc.derived_receipts()
        self.assertEqual(len(derived), 3)
        self.assertEqual(len({row[2] for row in derived}), 1)
        grant = derived[0][2]
        self.assertEqual(grant, sc.proposal["proposal_sha256"])
        # A and the seed authority are byte-identical to before the profile existed.
        after_seed = [row for row in sql(sc.ops_path, "SELECT receipt_sha256, payload_json FROM authority_receipts")
                      if row[0] in {item[0] for item in seed_authority}]
        self.assertEqual(sorted(after_seed), sorted(seed_authority))
        # Every admission belongs to exactly the day-owner of its UTC day; no fragmented day.
        per_day = sql(sc.ops_path, "SELECT substr(t0,1,10), COUNT(DISTINCT activation_id), COUNT(*) "
                                   "FROM episode_admissions GROUP BY 1 ORDER BY 1")
        self.assertEqual([(day, owners) for day, owners, _n in per_day],
                         [("2026-10-17", 1), ("2026-10-18", 1), ("2026-10-19", 1), ("2026-10-20", 1)])
        owner_by_day = {row[0]: row[2] for row in rows}
        for day, activation_id in sql(sc.ops_path, "SELECT DISTINCT substr(t0,1,10), activation_id FROM episode_admissions"):
            if day in owner_by_day:
                self.assertEqual(owner_by_day[day], activation_id)
        # The default tick serves older committed tails together with the new intake.
        self.assertGreaterEqual(len(tails["2026-10-20"]), 3, tails)
        # One shared account: members are X plus the three children and every debit is counted once.
        members = sql(sc.ops_path, "SELECT activation_id FROM account_budget_members ORDER BY activation_id")
        self.assertEqual(len(members), 4)
        total = sql(sc.ops_path, "SELECT COALESCE(SUM(provider_calls),0) FROM lifetime_counters")[0][0]
        status = sc.cmd(D3 + timedelta(hours=1), "account-budget-status")
        self.assertEqual(status["shared_usage"]["lifetime_provider_calls"], total)
        # No incident during the ordinary path.
        self.assertEqual(sql(sc.ops_path, "SELECT COUNT(*) FROM managed_incidents WHERE state='OPEN'")[0][0], 0)
        # Downstream: the release selector accepts one scope per UTC-day cohort across children
        # (it refuses only a day owned by two scopes), so daily children stay exportable.
        from solana_alpha_lab.factory.opportunity_episode_release import select_next_mature_episode_cohort

        selected = select_next_mature_episode_cohort(
            ops_store=sc.ops_path, observation_rdp=sc.data_root, imported=set(), as_of=D3 + timedelta(days=1))
        pending_days = {item["cohort_id"][4:12] for item in selected["pending"]}
        self.assertEqual(pending_days, {"20261017", "20261018", "20261019", "20261020"}, selected)

    def test_weekly_mint_dedup_and_lineage_continue_across_children_and_the_bridge(self) -> None:
        sc = self.sc
        self.commission_profile()
        # One mint nominated on the bridge day and again on every managed day while its episode
        # is still active: exactly one admission, by the bridge. One lineage serves all children.
        mint = synth_mint("WeeklyDup")
        row = token_object(mint, price=1, liquidity=10000, holders=60)
        sc.market.series[mint] = lambda _now, row=row: row
        for at in (D0 + timedelta(minutes=15), D1, D2):
            nominate(sc.market, at, {"toporganicscore": [row], "toptraded": [], "toptrending": []})
        sc.tick(D0 + timedelta(minutes=15, seconds=5))
        for day in (D1, D2):
            sc.backup(day - timedelta(hours=1))
            sc.tick(day + timedelta(seconds=5))
        rows = sql(sc.ops_path, "SELECT substr(t0,1,10), activation_id FROM episode_admissions ORDER BY t0")
        self.assertEqual([day for day, _activation in rows], ["2026-10-17"], rows)
        self.assertEqual(len(sc.children()), 2)
        seeds = {value for (value,) in sql(
            sc.ops_path, "SELECT DISTINCT json_extract(document_json,'$.sampling.seed') FROM registered_schedules")}
        self.assertEqual(len(seeds), 1)

    def test_missed_days_resume_forward_without_fictional_children_or_old_calls(self) -> None:
        sc = self.sc
        self.commission_profile()
        late = D3 + timedelta(hours=10, minutes=3, seconds=7)
        sc.backup(late)
        sc.nominate_round(D3 + timedelta(hours=10), "Late")
        result = sc.tick(late)
        self.assertEqual(result["managed"]["terminal"], "RECONCILE_CHILD_ACTIVATED", result)
        rows = sc.children()
        self.assertEqual([row[0] for row in rows], ["2026-10-20"])
        window = sql(sc.ops_path, "SELECT starts_at, stops_admitting_at FROM schedule_activations "
                                  "WHERE activation_id=?", (rows[0][2],))[0]
        self.assertEqual(window, ("2026-10-20T10:03:07Z", "2026-10-21T00:00:00Z"))
        # No provider request carries a past slot: every call is at or after the resume instant.
        self.assertTrue(all(call["at"] >= "2026-10-20T10:00:00" for call in result["_calls"]), result["_calls"])

    def test_reconcile_is_idempotent_across_process_restarts_and_writes_nothing_when_steady(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        sc.tick(D1 + timedelta(seconds=5))
        before = {table: sql(sc.ops_path, f"SELECT COUNT(*) FROM {table}")[0][0]
                  for table in ("managed_children", "managed_incidents", "runtime_events", "authority_receipts",
                                "registered_schedules", "schedule_activations")}
        stamp = sql(sc.ops_path, "SELECT updated_at FROM managed_children")
        for index in range(5):
            result = sc.cmd(D1 + timedelta(minutes=1 + index), "collection-reconcile", "--once")
            self.assertEqual(result["terminal"], "RECONCILE_INTAKE_OK", result)
        after = {table: sql(sc.ops_path, f"SELECT COUNT(*) FROM {table}")[0][0] for table in before}
        self.assertEqual(before, after)
        self.assertEqual(stamp, sql(sc.ops_path, "SELECT updated_at FROM managed_children"))


class ManagedRestoreTests(ManagedBase):
    def test_unresolved_restore_marker_blocks_the_controller_and_the_tick(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        store = ObservationScheduleStore(sc.ops_path)
        try:
            store.set_restore_marker("RESTORE-EPOCH-TEST")
        finally:
            store.close()
        blocked = sc.cmd(D1 + timedelta(seconds=5), "collection-reconcile", "--once")
        self.assertEqual(blocked["terminal"], "RECONCILE_RESTORE_MARKER_UNRESOLVED", blocked)
        self.assertEqual(sc.tick(D1 + timedelta(seconds=6))["terminal"], "RESTORE_MARKER_UNRESOLVED")
        self.assertEqual(sc.children(), [])


class ManagedPlanRefusalTests(ManagedBase):
    def test_plan_guards_handover_account_and_exact_phrase(self) -> None:
        sc = self.sc
        early = sc.plan(D0 + timedelta(hours=1), not_before=D0 + timedelta(hours=12))
        self.assertEqual(early["terminal"], "MANAGED_PLAN_REFUSED")
        self.assertEqual([item["axis"] for item in early["refusals"]], ["HANDOVER_BEFORE_PEER_STOPS"])
        self.assertIsNone(early["exact_owner_phrase"])
        missing = sc.plan(D0 + timedelta(hours=1), not_before=None)
        self.assertEqual([item["axis"] for item in missing["refusals"]], ["HANDOVER_BEFORE_PEER_STOPS"])
        ready = sc.plan(D0 + timedelta(hours=1))
        self.assertEqual(ready["terminal"], "MANAGED_PLAN_READY", ready)
        self.assertEqual(ready["authority_status"], "PROPOSED_NOT_AUTHORITY")
        bad_phrase = sc.cmd(D0 + timedelta(hours=1), "collection-apply", *sc.profile_args(),
                            "--expected-proposal-sha256", ready["proposal_sha256"], "--phrase", "AUTHORIZE ME")
        self.assertEqual(bad_phrase["terminal"], "BLOCKED_AUTHORITY")
        bad_proposal = sc.cmd(D0 + timedelta(hours=1), "collection-apply", *sc.profile_args(),
                              "--expected-proposal-sha256", "0" * 64, "--phrase", ready["exact_owner_phrase"])
        self.assertEqual(bad_proposal["terminal"], "MANAGED_PROPOSAL_MISMATCH")
        self.assertEqual(sql(sc.ops_path, "SELECT COUNT(*) FROM managed_profiles")[0][0], 0)
        # Re-applying after the revision moved is a conflict, never a second approval of the same bytes.
        first = sc.cmd(D0 + timedelta(hours=1), "collection-apply", *sc.profile_args(),
                       "--expected-proposal-sha256", ready["proposal_sha256"], "--phrase", ready["exact_owner_phrase"])
        self.assertEqual(first["terminal"], "MANAGED_APPLIED")
        stale = sc.cmd(D0 + timedelta(hours=2), "collection-plan", *sc.profile_args("--expected-revision", "0"))
        self.assertEqual(stale["terminal"], "MANAGED_REVISION_CONFLICT")

    def test_unactivated_registered_bridge_is_the_template_and_sets_the_handover(self) -> None:
        sc = self.sc
        from tests.test_opportunity_episodes_harness_v1 import PRODUCER, ROOT, build_schedule
        from solana_alpha_lab.factory.observation_schedule_lifecycle import register_schedule

        bridge = build_schedule(starts_at=D1 + timedelta(minutes=15), stops_at=D2, assignment=sc.assignment)
        store = ObservationScheduleStore(sc.ops_path)
        try:
            register_schedule(root=ROOT, data_root=sc.data_root, store=store, document=bridge,
                              now=D0 + timedelta(hours=1), producer_git_sha=PRODUCER)
        finally:
            store.close()
        base = ["--template-schedule-sha256", bridge["schedule_sha256"], "--account-scope-id", SCOPE,
                "--storage-basis-activation-id", sc.activation_id]
        early = sc.cmd(D0 + timedelta(hours=2), "collection-plan", *base, "--bootstrap-not-before", mc.render_utc(D1))
        self.assertEqual([item["axis"] for item in early["refusals"]], ["HANDOVER_BEFORE_PEER_STOPS"])
        self.assertEqual(early["refusals"][0]["peer_schedule_sha256"], bridge["schedule_sha256"])
        ready = sc.cmd(D0 + timedelta(hours=2), "collection-plan", *base, "--bootstrap-not-before", mc.render_utc(D2))
        self.assertEqual(ready["terminal"], "MANAGED_PLAN_READY", ready)
        self.assertTrue(ready["profile"]["resource_policy"]["storage_basis"]["source_ref"].startswith(
            "ACTIVATION:" + sc.activation_id))

    def test_plan_without_shared_account_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bare = ManagedScenario(Path(tmp) / "rdp")
            plan = bare.plan(D0 + timedelta(hours=1))
            self.assertEqual([item["axis"] for item in plan["refusals"]], ["SHARED_ACCOUNT_BUDGET_NOT_COMMISSIONED"])

    def test_rate_above_v1_ceiling_is_refused_with_numeric_axes_not_clipped(self) -> None:
        table = {100: (300, 13800, 426), 200: (600, 27600, 564), 500: (1500, 69000, 978),
                 1000: (3000, 138000, 1668), 2000: (6000, 276000, 3048)}
        template = self.sc.schedule
        limits = {"provider_calls_per_utc_day": 1200, "modeled_credits_per_utc_day": 1200, "cumulative_calls": 2000000,
                  "active_episode_cap": 400}
        for rate, (active, points, calls) in table.items():
            geometry = mc.capacity_geometry(template, {**limits, "admissions_per_utc_day": rate})
            self.assertEqual((geometry["steady_state_active_episodes"], geometry["post_t0_points_per_day"],
                              geometry["provider_calls_per_day_lower_bound"]), (active, points, calls), rate)
        axes = lambda rate: {r["axis"] for r in mc.capacity_geometry(  # noqa: E731
            template, {**limits, "admissions_per_utc_day": rate})["refusals"]}
        self.assertEqual(axes(100), set())
        self.assertEqual(axes(500), {"MANAGED_ADAPTER_V1_ADMISSION_CEILING"})
        self.assertEqual(axes(2000), {"MANAGED_ADAPTER_V1_ADMISSION_CEILING", "PROVIDER_CALLS_PER_UTC_DAY",
                                      "MODELED_CREDITS_PER_UTC_DAY", "PACE_DISPATCH_WINDOW"})
        # Through the public plan the same rate never becomes a proposal or a phrase.
        plan = self.sc.plan(D0 + timedelta(hours=1), "--admissions-per-utc-day", "500")
        self.assertEqual((plan["terminal"], plan["exact_owner_phrase"], plan["proposal_sha256"]),
                         ("MANAGED_PLAN_REFUSED", None, None))
        self.assertEqual([item["axis"] for item in plan["refusals"]], ["MANAGED_ADAPTER_V1_ADMISSION_CEILING"])
        self.assertEqual(plan["capacity"]["provider_calls_per_day_lower_bound"], 978)


class ManagedReadOnlyTests(unittest.TestCase):
    def test_status_and_plan_never_create_or_change_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            out = cli_command(root, D0, "collection-status")
            self.assertEqual(out["terminal"], "SOURCE_NOT_PRESENT")
            self.assertEqual(list(root.iterdir()), [])
        with tempfile.TemporaryDirectory() as tmp:
            sc = ManagedScenario(Path(tmp) / "rdp")
            sc.commission_account()
            before = sql(sc.ops_path, "SELECT COUNT(*) FROM runtime_events")[0][0], sc.ops_path.read_bytes()[:4096]
            self.assertEqual(sc.status(D0 + timedelta(hours=1))["terminal"], "MANAGED_UNMANAGED")
            sc.plan(D0 + timedelta(hours=1))
            after = sql(sc.ops_path, "SELECT COUNT(*) FROM runtime_events")[0][0], sc.ops_path.read_bytes()[:4096]
            self.assertEqual(before, after)
            self.assertEqual(sql(sc.ops_path, "SELECT COUNT(*) FROM managed_profiles")[0][0], 0)


class ManagedCrashRecoveryTests(ManagedBase):
    def test_crash_after_activation_commit_before_event_is_repaired_without_second_owner(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        from solana_alpha_lab.factory import observation_schedule_lifecycle as lifecycle

        original = lifecycle._append_or_replay
        crashed = {"done": False}

        def crash_on_first_active_event(data_root, event):
            if (not crashed["done"] and str(event.record_kind) == str(RecordKind.OBSERVATION_SCHEDULE_STATE)
                    and '"state":"ACTIVE"' in event.payload_json):
                crashed["done"] = True
                raise RuntimeError("SIMULATED_PROCESS_KILL")
            return original(data_root, event)

        with patch.object(lifecycle, "_append_or_replay", side_effect=crash_on_first_active_event):
            first = sc.tick(D1 + timedelta(seconds=5))
        self.assertTrue(crashed["done"])
        self.assertEqual(first["managed"]["terminal"], "RECONCILE_UNEXPECTED_ERROR", first)
        rows = sc.children()
        self.assertEqual(len(rows), 1)
        activation_id = rows[0][2]
        self.assertEqual(sql(sc.ops_path, "SELECT state FROM schedule_activations WHERE activation_id=?", (activation_id,)),
                         [("ACTIVE",)])
        self.assertEqual(rows[0][1], "AUTHORIZED_DERIVED")
        # The next ordinary tick resumes from the same intent and repairs the missing event.
        sc.nominate_round(D1 + timedelta(seconds=10), "Crash")
        repaired = sc.tick(D1 + timedelta(seconds=20))
        self.assertEqual(repaired["managed"]["terminal"], "RECONCILE_INTAKE_OK", repaired)
        self.assertTrue(repaired["managed"]["lineages"][0]["event_repaired"], repaired)
        # The repaired child is ticked in the same invocation, not one timer period later.
        self.assertEqual([item["activation_id"] for item in repaired["activations"]][-1], activation_id)
        self.assertEqual(repaired["activations"][-1]["terminal"], "TICK_COMPLETE", repaired)
        again = sc.tick(D1 + timedelta(seconds=45))
        self.assertEqual(again["managed"]["terminal"], "RECONCILE_INTAKE_OK", again)
        self.assertEqual(len(sc.children()), 1)
        self.assertEqual(sc.children()[0][2], activation_id)
        self.assertEqual(len(sc.derived_receipts()), 1)
        self.assertEqual(sql(sc.ops_path, "SELECT COUNT(*) FROM schedule_activations WHERE activation_id=?",
                             (activation_id,))[0][0], 1)
        self.assertEqual(sql(sc.ops_path, "SELECT state FROM managed_incidents"), [("RECOVERED",)])

    def test_crash_between_register_and_authorize_resumes_same_intent(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        boom = {"n": 0}
        real = mc.authorize_schedule_from_standing_grant

        def once_then_ok(**kwargs):
            boom["n"] += 1
            if boom["n"] == 1:
                raise RuntimeError("SIMULATED_PROCESS_KILL")
            return real(**kwargs)

        with patch.object(mc, "authorize_schedule_from_standing_grant", side_effect=once_then_ok):
            first = sc.tick(D1 + timedelta(seconds=5))
        self.assertEqual(first["managed"]["terminal"], "RECONCILE_UNEXPECTED_ERROR", first)
        self.assertEqual(sc.children()[0][1], "REGISTERED")
        schedule_sha = sql(sc.ops_path, "SELECT schedule_sha256 FROM managed_children")[0][0]
        second = sc.tick(D1 + timedelta(minutes=2))
        self.assertEqual(second["managed"]["terminal"], "RECONCILE_CHILD_ACTIVATED", second)
        self.assertEqual(sc.children()[0][1], "ACTIVATED")
        self.assertEqual(sql(sc.ops_path, "SELECT schedule_sha256 FROM managed_children")[0][0], schedule_sha)
        self.assertEqual(sql(sc.ops_path, "SELECT COUNT(*) FROM registered_schedules WHERE schedule_sha256=?",
                             (schedule_sha,))[0][0], 1)
        self.assertEqual(len(sc.derived_receipts()), 1)

    def test_competing_reconciler_defers_and_creates_no_second_owner(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        other = ObservationScheduleStore(sc.ops_path)
        try:
            token = other.acquire_lease("competing-process", clock=D1 + timedelta(seconds=4))
            result = sc.cmd(D1 + timedelta(seconds=5), "collection-reconcile", "--once")
            other.release_lease(token)
        finally:
            other.close()
        self.assertEqual(result["terminal"], "RECONCILE_DEFERRED_WRITER_BUSY")
        self.assertEqual(sc.children(), [])


def mc_root() -> Path:
    return Path(__file__).resolve().parents[1]


class ManagedAuthorityTests(ManagedBase):
    def test_child_must_fit_inside_the_grant_and_tampering_blocks_new_intake(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        # A child schedule that asks for more admissions than the grant is refused at derivation.
        from tests.test_opportunity_episodes_harness_v1 import PRODUCER, ROOT, build_schedule
        from solana_alpha_lab.factory.observation_schedule_lifecycle import (
            ObservationLifecycleError, authorize_schedule_from_standing_grant, register_schedule,
        )
        greedy = build_schedule(starts_at=D1, stops_at=D2, assignment=sc.assignment, daily_ceiling=100)
        store = ObservationScheduleStore(sc.ops_path)
        try:
            register_schedule(root=ROOT, data_root=sc.data_root, store=store, document=greedy,
                              now=D1, producer_git_sha=PRODUCER)
            with self.assertRaises(ObservationLifecycleError) as caught:
                authorize_schedule_from_standing_grant(
                    root=ROOT, data_root=sc.data_root, store=store, schedule_sha256=greedy["schedule_sha256"],
                    standing_grant_sha256=sc.proposal["proposal_sha256"], standing_grant_revision=1,
                    now=D1, producer_git_sha=PRODUCER)
            self.assertEqual(str(caught.exception), "MANAGED_CHILD_EXCEEDS_GRANT")
        finally:
            store.close()
        self.assertEqual(sc.derived_receipts(), [])
        # Same limits but a weaker approved semantic (no asset exclusion): not the frozen template.
        import copy

        from solana_alpha_lab.factory.observation_schedule import validate_observation_schedule

        weaker = copy.deepcopy(build_schedule(starts_at=D1, stops_at=D2, assignment=sc.assignment, daily_ceiling=96))
        weaker.pop("schedule_sha256")
        weaker["asset_exclusion"]["excluded_tags"] = []
        weaker = validate_observation_schedule(weaker, root=ROOT)
        store = ObservationScheduleStore(sc.ops_path)
        try:
            register_schedule(root=ROOT, data_root=sc.data_root, store=store, document=weaker,
                              now=D1, producer_git_sha=PRODUCER)
            with self.assertRaises(ObservationLifecycleError) as caught:
                authorize_schedule_from_standing_grant(
                    root=ROOT, data_root=sc.data_root, store=store, schedule_sha256=weaker["schedule_sha256"],
                    standing_grant_sha256=sc.proposal["proposal_sha256"], standing_grant_revision=1,
                    now=D1, producer_git_sha=PRODUCER)
            self.assertEqual(str(caught.exception), "MANAGED_CHILD_SEMANTICS_MISMATCH")
        finally:
            store.close()
        self.assertEqual(sc.derived_receipts(), [])
        # Tamper with the stored grant: derivation and ticks fail closed, tails of earlier children stay.
        with closing(sqlite3.connect(sc.ops_path)) as conn:
            conn.execute("UPDATE managed_profiles SET payload_json = replace(payload_json, '\"UNTIL_REVOKED\"', '\"UNTIL_DATE\"')")
            conn.commit()
        result = sc.cmd(D1 + timedelta(seconds=5), "collection-reconcile", "--once")
        self.assertEqual(result["terminal"], "RECONCILE_BLOCKED_MANAGED_GRANT_TAMPERED", result)
        self.assertEqual(sc.children(), [])
        incidents = sql(sc.ops_path, "SELECT incident_key, state FROM managed_incidents")
        self.assertEqual([state for _key, state in incidents], ["OPEN"])

    def test_tampered_grant_fails_closed_for_the_issued_child_at_tick_time_too(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        sc.tick(D1 + timedelta(seconds=5))
        child = sc.children()[0]
        with closing(sqlite3.connect(sc.ops_path)) as conn:
            conn.execute("UPDATE managed_profiles SET payload_json = replace(payload_json, '\"admissions_per_utc_day\": 96', "
                         "'\"admissions_per_utc_day\": 95')")
            conn.commit()
        result = sc.tick(D1 + timedelta(minutes=5))
        by_id = {item["activation_id"]: item for item in result["activations"]}
        self.assertEqual(by_id[child[2]]["terminal"], "AUTHORITY_MISMATCH", result)

    def test_stop_intake_blocks_new_children_but_issued_tail_authority_stays_live(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        sc.nominate_round(D1, "Stop", count=2)
        sc.tick(D1 + timedelta(seconds=5))
        rows = sc.children()
        self.assertEqual(rows[0][1], "ACTIVATED")
        stopped = sc.cmd(D1 + timedelta(hours=3), "collection-stop-intake", "--expected-revision", "1")
        self.assertEqual(stopped["terminal"], "MANAGED_INTAKE_STOPPED", stopped)
        self.assertEqual(stopped["children_stopped"], [rows[0][2]])
        self.assertEqual(sql(sc.ops_path, "SELECT state FROM schedule_activations WHERE activation_id=?", (rows[0][2],)),
                         [("DRAINING",)])
        # The same UTC day is never fragmented and the next day creates nothing while stopped.
        same_day = sc.tick(D1 + timedelta(hours=4))
        self.assertEqual(same_day["managed"]["terminal"], "RECONCILE_INTAKE_STOPPED", same_day)
        self.assertTrue(all(item.get("terminal") in {"TICK_COMPLETE", "TICK_PARTIAL"} for item in same_day["activations"]), same_day)
        next_day = sc.tick(D2 + timedelta(seconds=5))
        self.assertEqual(next_day["managed"]["terminal"], "RECONCILE_INTAKE_STOPPED", next_day)
        self.assertEqual(len(sc.children()), 1)
        # Re-applying a profile resumes intake at the next lawful boundary; the old tail is untouched.
        resumed = sc.apply(D2 + timedelta(hours=1))
        self.assertEqual(resumed["terminal"], "MANAGED_APPLIED", resumed)
        self.assertEqual(resumed["revision"], 2)
        sc.backup(D2 + timedelta(hours=1))
        sc.nominate_round(D2 + timedelta(hours=2), "Resumed")
        back = sc.tick(D2 + timedelta(hours=2, seconds=5))
        self.assertEqual(back["managed"]["terminal"], "RECONCILE_CHILD_ACTIVATED", back)
        self.assertEqual([row[0] for row in sc.children()], ["2026-10-18", "2026-10-19"])

    def test_day_owner_closed_mid_day_raises_one_incident_and_next_boundary_recovers(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        sc.tick(D1 + timedelta(seconds=5))
        child = sc.children()[0]
        sc.operator  # operator-style stop outside the managed controller (e.g. pressure drain)
        cli = sc.cmd(D1 + timedelta(hours=2), "stop-intake", "--schedule-sha256",
                     sql(sc.ops_path, "SELECT schedule_sha256 FROM managed_children")[0][0], "--activation-id", child[2])
        self.assertEqual(cli["terminal"], "STOP_INTAKE_COMMITTED", cli)
        closed = sc.tick(D1 + timedelta(hours=3))
        self.assertEqual(closed["managed"]["terminal"], "RECONCILE_DAY_OWNER_CLOSED", closed)
        self.assertEqual(len(sc.children()), 1)
        opened = sql(sc.ops_path, "SELECT incident_key, state FROM managed_incidents")
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0][1], "OPEN")
        stamp = sql(sc.ops_path, "SELECT updated_at, notified_at FROM managed_incidents")
        sc.tick(D1 + timedelta(hours=4))
        self.assertEqual(stamp, sql(sc.ops_path, "SELECT updated_at, notified_at FROM managed_incidents"))
        sc.backup(D2 - timedelta(hours=1))
        sc.nominate_round(D2, "Next")
        nxt = sc.tick(D2 + timedelta(seconds=5))
        self.assertEqual(nxt["managed"]["terminal"], "RECONCILE_CHILD_ACTIVATED", nxt)
        self.assertEqual(sql(sc.ops_path, "SELECT state FROM managed_incidents"), [("RECOVERED",)])

    def test_finite_validity_stops_new_intake_but_keeps_the_tail(self) -> None:
        sc = self.sc
        until = D2 + timedelta(hours=12)
        self.commission_profile("--validity", "UNTIL_DATE", "--intake-until", mc.render_utc(until))
        for day, label in ((D1, "F1"), (D2, "F2")):
            sc.backup(day - timedelta(hours=1))
            sc.nominate_round(day, label)
            self.assertEqual(sc.tick(day + timedelta(seconds=5))["managed"]["terminal"], "RECONCILE_CHILD_ACTIVATED")
        windows = sql(sc.ops_path, "SELECT starts_at, stops_admitting_at FROM schedule_activations "
                                   "WHERE activation_id IN (SELECT activation_id FROM managed_children) ORDER BY starts_at")
        self.assertEqual(windows[-1][1], "2026-10-19T12:00:00Z")
        after = sc.tick(until + timedelta(minutes=5))
        self.assertEqual(after["managed"]["terminal"], "RECONCILE_VALIDITY_ENDED", after)
        tail = sc.tick(D3 + timedelta(hours=1))
        self.assertEqual(tail["managed"]["terminal"], "RECONCILE_VALIDITY_ENDED", tail)
        self.assertEqual(len(sc.children()), 2)
        self.assertEqual(sql(sc.ops_path, "SELECT COUNT(*) FROM managed_incidents WHERE state='OPEN'")[0][0], 0)


class ManagedRollbackTests(ManagedBase):
    def test_rollback_to_restrictive_approved_revision_needs_no_phrase_and_keeps_history(self) -> None:
        sc = self.sc
        self.commission_profile("--admissions-per-utc-day", "50")
        looser = sc.apply(D0 + timedelta(hours=2), "--admissions-per-utc-day", "96")
        self.assertEqual((looser["terminal"], looser["revision"]), ("MANAGED_APPLIED", 2), looser)
        # Loosening back needs the exact phrase again.
        denied = sc.cmd(D0 + timedelta(hours=3), "collection-rollback", "--expected-revision", "2", "--to-revision", "1")
        self.assertEqual(denied["terminal"], "MANAGED_ROLLED_BACK", denied)
        status = sc.status(D0 + timedelta(hours=4))
        lineage = status["lineages"][0]
        self.assertEqual((lineage["revision"], lineage["limits"]["admissions_per_utc_day"]), (3, 50))
        revisions = sql(sc.ops_path, "SELECT revision, previous_revision FROM managed_profiles ORDER BY revision")
        self.assertEqual(revisions, [(1, None), (2, 1), (3, 2)])
        sc.backup(D1 - timedelta(hours=1))
        sc.nominate_round(D1, "Rb")
        sc.tick(D1 + timedelta(seconds=5))
        ceiling = sql(sc.ops_path, "SELECT json_extract(document_json,'$.sampling.daily_normal_ceiling') "
                                   "FROM registered_schedules WHERE schedule_sha256 IN "
                                   "(SELECT schedule_sha256 FROM managed_children)")
        self.assertEqual(ceiling, [(50,)])
        # Going from the restricted settings back up is not a rollback: it requires the phrase.
        again = sc.cmd(D1 + timedelta(hours=1), "collection-rollback", "--expected-revision", "3", "--to-revision", "2")
        self.assertEqual(again["terminal"], "ROLLBACK_NOT_RESTRICTIVE_PHRASE_REQUIRED", again)


class ManagedResourceTests(ManagedBase):
    def body_and_store(self):
        store = ObservationScheduleStore(self.sc.ops_path)
        self.addCleanup(store.close)
        self.commission_profile()
        return store.managed_profile(next(iter(store.managed_lineages())), 1)["payload"]["profile"], store

    def decide(self, body, store, *, free, factory, at=D1):
        return mc.managed_storage_decision(store=store, body=body, data_root=self.sc.data_root, now=at,
                                           free_bytes=free, factory_bytes=factory)

    def test_decision_matrix_never_forges_pass_and_keeps_independent_checks(self) -> None:
        body, store = self.body_and_store()
        self.sc.backup(D1 - timedelta(hours=1))
        gib = 1024 ** 3
        # Owner TARGET lowered for the fixture so that TARGET and HARD are separable axes; the
        # approved local byte bounds make the fixture's physical tail reserve about 15.3 GiB.
        body = json.loads(json.dumps(body))
        body["resource_policy"]["target_bytes"] = 20 * gib
        ok = self.decide(body, store, free=100 * gib, factory=10 * gib)
        self.assertEqual((ok["decision"], ok["storage_health"], ok["reasons"]), ("ALLOW", "OK", []))
        self.assertEqual(self.decide(body, store, free=100 * gib, factory=36 * gib)["reasons"],
                         ["HARD_BYTES", "TARGET_EXCEEDED_UNACCEPTED"])
        self.assertEqual(self.decide(body, store, free=1 * gib, factory=10 * gib)["reasons"], ["PHYSICAL_TAIL_RESERVE"])
        self.assertEqual(self.decide(body, store, free=None, factory=10 * gib)["reasons"], ["PHYSICAL_TAIL_RESERVE"])
        target_only = self.decide(body, store, free=100 * gib, factory=25 * gib)
        self.assertEqual((target_only["decision"], target_only["reasons"]), ("BLOCK", ["TARGET_EXCEEDED_UNACCEPTED"]))
        stale = self.decide(body, store, free=100 * gib, factory=10 * gib, at=D1 + timedelta(days=3))
        self.assertEqual(stale["reasons"], ["BACKUP_STALE"])
        # A forged, too-small or hard-exceeding acceptance never converts a block into an allow.
        for acceptance in ({"acceptance_sha256": "nothex", "max_projected_bytes": 45 * gib},
                           {"acceptance_sha256": "b" * 64, "max_projected_bytes": 30 * gib},
                           {"acceptance_sha256": "b" * 64, "max_projected_bytes": 60 * gib}):
            tuned = json.loads(json.dumps(body))
            tuned["resource_policy"]["target_acceptance"] = acceptance
            factory = 36 * gib if acceptance["max_projected_bytes"] == 60 * gib else 25 * gib
            self.assertEqual(self.decide(tuned, store, free=100 * gib, factory=factory)["decision"], "BLOCK", acceptance)
        accepted = json.loads(json.dumps(body))
        accepted["resource_policy"]["target_acceptance"] = {"acceptance_sha256": "b" * 64, "max_projected_bytes": 45 * gib}
        degraded = self.decide(accepted, store, free=100 * gib, factory=25 * gib)
        self.assertEqual((degraded["decision"], degraded["storage_health"], degraded["hard_constraints"]),
                         ("ALLOW_WITH_ACCEPTED_TARGET_RISK", "DEGRADED_TARGET", "PASS"))
        self.assertEqual(self.decide(accepted, store, free=100 * gib, factory=32 * gib)["decision"], "BLOCK")
        # The V2 envelope validates in the owner validator and carries no PASS gate.
        env = mc.build_child_storage_commissioning(
            accepted, data_root=self.sc.data_root, schedule_sha256="c" * 64, activation_id="ACT-X", decision=degraded)
        self.assertNotIn("factory_storage_gate", env)
        validate_episode_storage_commissioning(env, data_root=self.sc.data_root, schedule_sha256="c" * 64,
                                               activation_id="ACT-X")
        for tamper in ({"storage_decision": {**env["storage_decision"], "decision": "ALLOW"}},
                       {"storage_decision": {**env["storage_decision"], "hard_constraints": "FAIL"}},
                       {"storage_decision": {**env["storage_decision"], "target_acceptance": None}}):
            bad = {**env, **tamper}
            bad["envelope_sha256"] = mc.canonical_sha256({k: v for k, v in bad.items() if k != "envelope_sha256"})
            with self.assertRaises(EpisodeStorageError):
                validate_episode_storage_commissioning(bad, data_root=self.sc.data_root, schedule_sha256="c" * 64,
                                                       activation_id="ACT-X")

    def test_blocked_intake_opens_one_incident_keeps_tails_and_recovers_when_resource_returns(self) -> None:
        sc = self.sc
        self.commission_profile("--backup-max-age-seconds", "3600")
        # The backup receipt is older than the approved age at the first boundary: new intake stops, X's tail runs.
        sc.nominate_round(D1, "Blocked")
        blocked = sc.tick(D1 + timedelta(seconds=5))
        self.assertEqual(blocked["managed"]["terminal"], "RECONCILE_BLOCKED_NEW_INTAKE", blocked)
        self.assertEqual(blocked["managed"]["lineages"][0]["reasons"], ["BACKUP_STALE"])
        self.assertTrue(blocked["activations"][0]["activation_id"] == sc.activation_id)
        self.assertEqual(sc.children(), [])
        key_rows = sql(sc.ops_path, "SELECT incident_key, state, json_extract(payload_json,'$.scope') FROM managed_incidents")
        self.assertEqual([(row[1], row[2]) for row in key_rows], [("OPEN", "NEW_INTAKE_ONLY")])
        sc.backup(D1 + timedelta(minutes=20))
        cached = sc.tick(D1 + timedelta(minutes=2))
        self.assertEqual(cached["managed"]["terminal"], "RECONCILE_BLOCKED_NEW_INTAKE")
        self.assertTrue(cached["managed"]["lineages"][0].get("cached"))
        ok = sc.tick(D1 + timedelta(minutes=21))
        self.assertEqual(ok["managed"]["terminal"], "RECONCILE_CHILD_ACTIVATED", ok)
        self.assertEqual(sql(sc.ops_path, "SELECT state FROM managed_incidents"), [("RECOVERED",)])
        window = sql(sc.ops_path, "SELECT starts_at FROM schedule_activations WHERE activation_id=?", (sc.children()[0][2],))
        self.assertEqual(window, [("2026-10-18T00:21:00Z",)])


class ManagedBudgetTailTests(ManagedBase):
    def test_new_intake_waits_when_committed_tail_would_not_be_covered(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        used = sql(sc.ops_path, "SELECT COALESCE(SUM(provider_calls),0) FROM lifetime_counters")[0][0]
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            from solana_alpha_lab.factory.observation_account_budget import revise_account_budget_policy

            revise_account_budget_policy(
                store, expected_revision=1, reason="TAIL_RISK_TEST", now=D0 + timedelta(hours=2),
                limits={"provider_calls_per_utc_day_max": 1200, "modeled_credits_per_utc_day_max": 1200,
                        "provider_calls_lifetime_max": int(used) + 100})
        sc.nominate_round(D1, "Tail")
        blocked = sc.tick(D1 + timedelta(seconds=5))
        self.assertEqual(blocked["managed"]["terminal"], "RECONCILE_BLOCKED_NEW_INTAKE", blocked)
        self.assertEqual(blocked["managed"]["lineages"][0]["reasons"], ["BUDGET_TAIL_RISK"])
        self.assertEqual(sc.children(), [])
        # The committed tail of the bridge is still served in the same invocation.
        self.assertEqual(blocked["activations"][0]["activation_id"], sc.activation_id)


class ManagedHoldTests(ManagedBase):
    def test_pressure_holds_a_managed_child_but_still_drains_an_unmanaged_one(self) -> None:
        sc = self.sc
        self.commission_profile()
        sc.backup(D1 - timedelta(hours=1))
        sc.tick(D1 + timedelta(seconds=5))
        child = sc.children()[0]
        tiny = Usage(10 ** 12, 10 ** 12 - 1024, 1024)
        sc.nominate_round(D1 + timedelta(minutes=15), "Hold")
        with patch("solana_alpha_lab.factory.opportunity_episode_tick.shutil.disk_usage", return_value=tiny):
            held = sc.tick(D1 + timedelta(minutes=15, seconds=5))
        by_id = {item["activation_id"]: item for item in held["activations"]}
        self.assertEqual(by_id[child[2]]["stop_reason"], "DRAIN_RESERVE_PRESSURE_HOLD")
        self.assertEqual(sql(sc.ops_path, "SELECT state FROM schedule_activations WHERE activation_id=?", (child[2],)),
                         [("ACTIVE",)])
        # A hold is never silent: one durable incident, scoped to this round of the same child.
        held_rows = sql(sc.ops_path, "SELECT incident_key, state, json_extract(payload_json,'$.scope') FROM managed_incidents")
        self.assertEqual([(row[0].split(":")[0], row[1], row[2]) for row in held_rows],
                         [("INTAKE_HELD", "OPEN", "NEW_INTAKE_THIS_ROUND_SAME_CHILD")])
        sc.nominate_round(D1 + timedelta(minutes=30), "Back")
        back = sc.tick(D1 + timedelta(minutes=30, seconds=5))
        self.assertIsNone({item["activation_id"]: item for item in back["activations"]}[child[2]].get("stop_reason"))
        self.assertEqual(sql(sc.ops_path, "SELECT state FROM managed_incidents"), [("RECOVERED",)])
        self.assertEqual(sql(sc.ops_path, "SELECT COUNT(*) FROM managed_children")[0][0], 1)
        # An ordinary unmanaged activation keeps the original sticky drain.
        with tempfile.TemporaryDirectory() as tmp:
            plain = EpisodeScenario(Path(tmp) / "rdp", start=D0, stops=D1)
            nominate(plain.market, D0 + timedelta(minutes=15), {"toporganicscore": [], "toptraded": [], "toptrending": []})
            with patch("solana_alpha_lab.factory.opportunity_episode_tick.shutil.disk_usage", return_value=tiny):
                closed = plain.tick(D0 + timedelta(minutes=15, seconds=5))
            self.assertEqual(closed["stop_reason"], "DRAIN_RESERVE_PRESSURE")
            self.assertIn(plain.activation_state(), {"DRAINING", "COMPLETE"})


class ManagedAlertTests(ManagedBase):
    """Existing watch owner: one incident, one recovery, no daily false successor alarm."""

    UNITS = {unit: "active" for unit in (
        "factory-observation-schedule.timer", "factory-remote-backup.timer",
        "factory-collector-owner-pulse.timer", "factory-hot90-closed-day-archive.timer",
        "factory-operability-watch.timer", "factory-v1-workbench.service")}

    def watch(self, at: datetime, watch_root: Path) -> dict:
        from solana_alpha_lab.factory.operability_watch import evaluate_operability

        store = ObservationScheduleStore(self.sc.ops_path)
        try:
            return evaluate_operability(root=watch_root, store=store, now=at, unit_status=self.UNITS,
                                        observation_rdp=self.sc.data_root, emit=False, environ={})
        finally:
            store.close()

    def test_blocked_intake_is_one_incident_then_one_recovery_and_no_successor_false_alarm(self) -> None:
        sc = self.sc
        watch_root = Path(self.tmp.name) / "watch"
        watch_root.mkdir()
        self.commission_profile("--backup-max-age-seconds", "3600")
        sc.nominate_round(D1, "Alert")
        sc.tick(D1 + timedelta(seconds=5))
        first = self.watch(D1 + timedelta(seconds=30), watch_root)
        self.assertIn(("INCIDENT", "MANAGED_INTAKE_BLOCKED"),
                      {(item["kind"], item["code"]) for item in first["messages"]}, first)
        text = " ".join(first["preview_messages"])
        self.assertIn("BACKUP_STALE", text)
        self.assertIn("продолжают наблюдаться", text)
        repeat = self.watch(D1 + timedelta(seconds=900), watch_root)
        self.assertEqual(repeat["messages"], [])
        sc.backup(D1 + timedelta(minutes=20))
        sc.tick(D1 + timedelta(minutes=21))
        recovered = self.watch(D1 + timedelta(minutes=22), watch_root)
        self.assertIn(("RECOVERED", "MANAGED_INTAKE_BLOCKED"),
                      {(item["kind"], item["code"]) for item in recovered["messages"]}, recovered)
        # A managed day ending at midnight is not a missing owner-registered successor.
        near_end = self.watch(D2 - timedelta(minutes=10), watch_root)
        self.assertNotIn("CAMPAIGN_SUCCESSOR_REQUIRED", near_end["present"])

    def test_unmanaged_expiring_campaign_still_alarms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plain = ManagedScenario(Path(tmp) / "rdp")
            store = ObservationScheduleStore(plain.ops_path)
            try:
                from solana_alpha_lab.factory.operability_watch import evaluate_operability

                result = evaluate_operability(
                    root=Path(tmp), store=store, now=D1 - timedelta(minutes=10), unit_status=self.UNITS,
                    observation_rdp=plain.data_root, emit=False, persist=False, environ={})
            finally:
                store.close()
            self.assertIn("CAMPAIGN_SUCCESSOR_REQUIRED", result["present"])


if __name__ == "__main__":
    unittest.main()
