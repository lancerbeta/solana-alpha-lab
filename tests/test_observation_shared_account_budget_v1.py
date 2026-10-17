"""I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1: one managed account, no reset A->B.

Production owners only: ObservationScheduleStore, _Accounting, _EpisodeTick._call
and the public ``scripts/observation_schedule.py`` entry. Transport and clocks
are synthetic. Every expected total is computed from an authored trace or raw
SQL, never from the production aggregation helper.
"""

from __future__ import annotations

import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import yaml

from tests.test_opportunity_episodes_harness_v1 import (
    ROOT,
    EpisodeScenario,
    SyntheticJupiter,
    build_schedule,
    cli_command,
    cli_tick,
    nominate,
    register_authorize_activate,
    synth_mint,
    token_object,
)
from solana_alpha_lab.factory.observation_account_budget import (
    AccountBudgetError,
    account_budget_status,
    apply_account_budget,
    prepare_account_budget,
    revise_account_budget_policy,
)
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.observation_scheduler import _Accounting

BUDGETS = yaml.safe_load((ROOT / "configs" / "opportunity_episodes_jupiter_core_v1.yaml").read_text(encoding="utf-8"))["budgets"]
DAY_CAP = 1200
LIFE_CAP = 2000000
LIMITS = {"provider_calls_per_utc_day_max": DAY_CAP, "modeled_credits_per_utc_day_max": DAY_CAP,
          "provider_calls_lifetime_max": LIFE_CAP}
T0 = datetime(2026, 10, 17, 0, 30, tzinfo=UTC)
DAY = T0.strftime("%Y-%m-%d")
A = ("a" * 64, "ACT-PREDECESSOR-A")
B = ("b" * 64, "ACT-SUCCESSOR-B")
C = ("c" * 64, "ACT-SUCCESSOR-C")
SCOPE = "JUPITER-MANAGED-ACCOUNT-1"


def schedule(identity: tuple[str, str], **budget_overrides) -> dict:
    return {"schedule_sha256": identity[0], "budgets": {**BUDGETS, **budget_overrides}}


def raw_shared(path: Path, utc_day: str) -> tuple[int, int, int]:
    """Independent SQL oracle over primary per-activation rows + membership."""

    with closing(sqlite3.connect(path)) as conn:
        members = conn.execute("SELECT schedule_sha256, activation_id FROM account_budget_members").fetchall()
        day = credits = life = 0
        for digest, activation in members:
            row = conn.execute("SELECT provider_calls, modeled_credits FROM accounting_counters "
                               "WHERE schedule_sha256=? AND activation_id=? AND utc_day=?",
                               (digest, activation, utc_day)).fetchone()
            if row:
                day += row[0]
                credits += row[1]
            row = conn.execute("SELECT provider_calls FROM lifetime_counters WHERE schedule_sha256=? "
                               "AND activation_id=?", (digest, activation)).fetchone()
            life += row[0] if row else 0
    return day, credits, life


class SharedWallClock:
    """WallClock-shaped shared clock: the second lane sees time spent by the first."""

    def __init__(self, at):
        from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock
        self.inner = AdvancingClock(at)

    def __call__(self):
        return self.inner.now()

    def now(self):
        return self.inner.now()

    def sleep(self, seconds):
        self.inner.sleep(seconds)


def wall_tick(sc, at):
    result = cli_tick(sc.data_root, sc.market, at, pacing_clock=SharedWallClock(at))
    sc.ticks.append(result)
    return result


class StoreFixture:
    def __init__(self, root: Path, name: str = "observation_schedule_state.sqlite") -> None:
        self.path = root / name
        self.store = ObservationScheduleStore(self.path)

    def activation(self, identity, state="ACTIVE", clock=T0):
        lease = self.store.acquire_lease("fixture-activation", clock=clock)
        self.store.upsert_activation({"schedule_sha256": identity[0], "activation_id": identity[1],
                                      "schedule_key": "OBS-" + identity[1], "state": state,
                                      "starts_at": "2026-10-13T00:00:00Z",
                                      "stops_admitting_at": "2026-10-17T00:00:00Z"}, clock=clock)
        self.store.release_lease(lease)

    def debit(self, identity, *, day=DAY, calls=0, credits=None, life=None, clock=T0):
        lease = self.store.acquire_lease("fixture-debit", clock=clock)
        self.store.save_call_debit(
            schedule_sha256=identity[0], activation_id=identity[1], utc_day=day,
            values={"provider_calls": calls, "modeled_credits": calls if credits is None else credits,
                    "raw_bytes": 0, "canonical_bytes": 0, "candidates": 0, "members": 0,
                    "last_provider_call_at": None},
            lifetime_provider_calls=calls if life is None else life, lifetime_canonical_bytes=0, clock=clock)
        self.store.release_lease(lease)

    def commission(self, limits=LIMITS, now=T0):
        plan = prepare_account_budget(self.store, account_scope_id=SCOPE,
                                      credential_locator="JUPITER_FREE_API_KEY", limits=limits, now=now)
        return plan, apply_account_budget(self.store, account_scope_id=SCOPE,
                                          credential_locator="JUPITER_FREE_API_KEY", limits=limits,
                                          expected_plan_sha256=plan["plan_sha256"], now=now)

    def accounting(self, identity, now=T0, **budget_overrides):
        return _Accounting(self.store, schedule(identity, **budget_overrides), identity[1], now,
                           credit_costs={"COST3": 3})

    def gate(self, identity, now=T0, **kwargs):
        lease = self.store.acquire_lease("fixture-gate", clock=now)
        try:
            accounts = self.accounting(identity, now)
            return accounts.gate(now=now, **kwargs), accounts.last_denial
        finally:
            self.store.release_lease(lease)


class SharedAccountBudgetStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = StoreFixture(Path(self.tmp.name))
        self.addCleanup(self.fx.store.close)
        self.fx.activation(A)
        self.fx.activation(B)

    def test_original_falsifier_unmanaged_reset_then_managed_refusal(self):
        # Exact preflight numbers: A exhausted 1200/day and 2000000 lifetime, B has 4.
        self.fx.debit(A, calls=DAY_CAP, life=LIFE_CAP)
        self.fx.debit(B, calls=4)
        self.assertEqual(self.fx.gate(A)[0], "BLOCKED_BUDGET")
        # Default-off: before commissioning the activation-local defect is unchanged.
        self.assertIsNone(self.fx.gate(B)[0])
        self.fx.commission()
        blocked, denial = self.fx.gate(B)
        self.assertEqual(blocked, "BLOCKED_BUDGET")
        self.assertEqual((denial["budget_scope"], denial["budget_dimension"], denial["used"],
                          denial["requested_debit"], denial["limit"], denial["policy_revision"]),
                         ("SHARED_ACCOUNT", "SHARED_DAY_PROVIDER_CALLS", DAY_CAP + 4, 1, DAY_CAP, 1))
        self.assertEqual(self.fx.gate(A)[1]["budget_scope"], "ACTIVATION")
        self.assertEqual(raw_shared(self.fx.path, DAY), (DAY_CAP + 4, DAY_CAP + 4, LIFE_CAP + 4))

    def test_daily_boundary_exactly_one_more_call_from_any_identity(self):
        self.fx.debit(A, calls=DAY_CAP - 1)
        self.fx.commission()
        lease = self.fx.store.acquire_lease("daily-boundary", clock=T0)
        b = self.fx.accounting(B)
        self.assertIsNone(b.reserve_call(credits=1, now=T0))
        self.assertEqual(b.reserve_call(credits=1, now=T0 + timedelta(seconds=5)), "BLOCKED_BUDGET")
        self.assertEqual(b.last_denial["budget_dimension"], "SHARED_DAY_PROVIDER_CALLS")
        self.fx.store.release_lease(lease)
        self.assertEqual(self.fx.gate(A, now=T0 + timedelta(seconds=10))[1]["budget_dimension"],
                         "SHARED_DAY_PROVIDER_CALLS")
        self.assertEqual(raw_shared(self.fx.path, DAY)[0], DAY_CAP)

    def test_lifetime_debt_survives_utc_day_activation_and_revision(self):
        self.fx.debit(A, calls=10, life=LIFE_CAP - 3)
        self.fx.commission()
        next_day = T0 + timedelta(days=1)
        self.fx.activation(C, clock=next_day)
        for identity in (A, B, C):
            blocked, denial = self.fx.gate(identity, now=next_day)
            self.assertIsNone(blocked, identity)
        self.fx.debit(C, day=next_day.strftime("%Y-%m-%d"), calls=3, clock=next_day)
        revise_account_budget_policy(self.fx.store, expected_revision=1, limits=dict(LIMITS),
                                     reason="ROLLBACK_SAME_LIMITS", now=next_day)
        for identity in (A, B, C):
            blocked, denial = self.fx.gate(identity, now=next_day + timedelta(seconds=10))
            self.assertEqual((blocked, denial["budget_dimension"], denial["next_action"]),
                             ("BLOCKED_BUDGET", "SHARED_LIFETIME_PROVIDER_CALLS", "OWNER_DECISION_REQUIRED"))
        self.assertEqual(raw_shared(self.fx.path, next_day.strftime("%Y-%m-%d"))[2], LIFE_CAP)

    def test_credits_exhaust_separately_with_registry_cost(self):
        self.fx.debit(A, calls=10, credits=DAY_CAP - 2)
        self.fx.commission()
        lease = self.fx.store.acquire_lease("credits", clock=T0)
        b = self.fx.accounting(B)
        cost = max(1, int(b.credit_costs["COST3"]))
        self.assertEqual(b.reserve_call(credits=cost, now=T0), "BLOCKED_BUDGET")
        self.assertEqual(b.last_denial["budget_dimension"], "SHARED_DAY_MODELED_CREDITS")
        self.assertIsNone(b.reserve_call(credits=2, now=T0))
        self.fx.store.release_lease(lease)
        self.assertEqual(raw_shared(self.fx.path, DAY)[:2], (11, DAY_CAP))

    def test_second_account_store_is_independent_and_scope_cannot_be_replaced(self):
        self.fx.debit(A, calls=DAY_CAP)
        plan, applied = self.fx.commission()
        other = StoreFixture(Path(self.tmp.name), "other_account.sqlite")
        self.addCleanup(other.store.close)
        other.activation(B)
        other.commission()
        self.assertIsNone(other.gate(B)[0])
        replay = apply_account_budget(self.fx.store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                      limits=LIMITS, expected_plan_sha256=plan["plan_sha256"], now=T0)
        self.assertEqual((replay["terminal"], replay["replayed"]), ("ACCOUNT_BUDGET_ALREADY_APPLIED", True))
        with self.assertRaisesRegex(AccountBudgetError, "ACCOUNT_BUDGET_ALREADY_COMMISSIONED"):
            apply_account_budget(self.fx.store, account_scope_id="JUPITER-FRESH-ACCOUNT", limits=LIMITS,
                                 credential_locator="JUPITER_FREE_API_KEY", expected_plan_sha256="0" * 64, now=T0)
        for scope_id, limits in (("JUPITER-TYPO-ACCOUNT", LIMITS),
                                 (SCOPE, {**LIMITS, "provider_calls_per_utc_day_max": 1300})):
            with self.assertRaisesRegex(AccountBudgetError, "ACCOUNT_BUDGET_REPLAY_MISMATCH"):
                apply_account_budget(self.fx.store, account_scope_id=scope_id, limits=limits,
                                     credential_locator="JUPITER_FREE_API_KEY",
                                     expected_plan_sha256=plan["plan_sha256"], now=T0)
        with self.assertRaisesRegex(AccountBudgetError, "ACCOUNT_SCOPE_ID_INVALID"):
            prepare_account_budget(self.fx.store, account_scope_id=A[1], credential_locator="JUPITER_FREE_API_KEY",
                                   limits=LIMITS, now=T0)

    def test_new_native_activation_inherits_and_binding_loss_fails_closed(self):
        self.fx.debit(A, calls=700)
        self.fx.commission()
        lease = self.fx.store.acquire_lease("complete-a", clock=T0)
        self.fx.store._conn.execute("UPDATE schedule_activations SET state='COMPLETE' WHERE activation_id=?", (A[1],))
        self.fx.store._conn.commit()
        self.fx.store.release_lease(lease)
        self.fx.activation(C)
        rows = dict(self.fx.store._conn.execute(
            "SELECT activation_id, binding_source FROM account_budget_members").fetchall())
        self.assertEqual(rows, {A[1]: "COMMISSIONING", B[1]: "COMMISSIONING", C[1]: "NATIVE_ACTIVATION"})
        self.fx.debit(C, calls=500)
        self.assertEqual(self.fx.gate(C)[1]["used"], DAY_CAP)
        # Removing C's membership cannot reopen activation-local caps.
        self.fx.store._conn.execute("DELETE FROM account_budget_members WHERE activation_id=?", (C[1],))
        self.fx.store._conn.commit()
        blocked, denial = self.fx.gate(C)
        self.assertEqual((blocked, denial["budget_dimension"], denial["reason"]),
                         ("BLOCKED_BUDGET", "ACCOUNT_BINDING", "ACCOUNT_BUDGET_MEMBERSHIP_REQUIRED"))
        self.assertEqual(account_budget_status(self.fx.store, now=T0)["mode"], "CORRUPT")
        self.fx.store._conn.execute("DELETE FROM account_budget_scopes")
        self.fx.store._conn.commit()
        self.assertEqual(self.fx.gate(A)[1]["reason"], "ACCOUNT_BUDGET_SCOPE_MISSING")
        with self.assertRaisesRegex(AccountBudgetError, "ACCOUNT_BUDGET_SCOPE_MISSING"):
            self.fx.commission()

    def test_two_handles_last_debit_at_most_one_allowance_and_no_stale_snapshot(self):
        self.fx.debit(A, calls=DAY_CAP - 1)
        self.fx.commission()
        second = ObservationScheduleStore(self.fx.path)
        self.addCleanup(second.close)
        # B's accounting object is built before A's last debit: stale snapshot.
        stale_b = _Accounting(second, schedule(B), B[1], T0)
        lease = self.fx.store.acquire_lease("handle-a", clock=T0)
        self.assertIsNone(second.acquire_lease("handle-b", clock=T0))
        self.assertIsNone(self.fx.accounting(A).reserve_call(credits=1, now=T0))
        self.fx.store.release_lease(lease)
        lease_b = second.acquire_lease("handle-b", clock=T0 + timedelta(seconds=1))
        self.assertEqual(stale_b.reserve_call(credits=1, now=T0 + timedelta(seconds=1)), "BLOCKED_BUDGET")
        second.release_lease(lease_b)
        second.close()
        reopened = StoreFixture(Path(self.tmp.name))
        self.addCleanup(reopened.store.close)
        self.assertEqual(reopened.gate(B, now=T0 + timedelta(seconds=9))[0], "BLOCKED_BUDGET")
        self.assertEqual(raw_shared(self.fx.path, DAY)[0], DAY_CAP)

    def test_day_and_lifetime_debit_commit_together(self):
        self.fx.commission()
        lease = self.fx.store.acquire_lease("atomic", clock=T0)
        accounts = self.fx.accounting(B)
        with patch.object(self.fx.store, "_write_lifetime", side_effect=sqlite3.OperationalError("crash")):
            with self.assertRaises(sqlite3.OperationalError):
                accounts.reserve_call(credits=1, now=T0)
        self.fx.store.release_lease(lease)
        self.assertEqual(raw_shared(self.fx.path, DAY), (0, 0, 0))
        lease = self.fx.store.acquire_lease("atomic", clock=T0)
        self.assertIsNone(self.fx.accounting(B).reserve_call(credits=1, now=T0))
        self.fx.store.release_lease(lease)
        self.fx.store.close()
        self.fx = StoreFixture(Path(self.tmp.name))
        self.addCleanup(self.fx.store.close)
        self.assertEqual(raw_shared(self.fx.path, DAY), (1, 1, 1))

    def test_policy_lower_raise_keeps_debt_and_local_grant_bound(self):
        self.fx.debit(A, calls=900)
        self.fx.commission()
        lowered = revise_account_budget_policy(self.fx.store, expected_revision=1, now=T0, reason="LOWER_TEST",
                                               limits={**LIMITS, "provider_calls_per_utc_day_max": 800})
        self.assertEqual((lowered["shared_usage"]["day_provider_calls"], lowered["remaining"]["day_provider_calls"],
                          lowered["over_limit"]), (900, 0, ["day_provider_calls"]))
        self.assertEqual(self.fx.gate(B)[1]["policy_revision"], 2)
        replay = revise_account_budget_policy(self.fx.store, expected_revision=1, now=T0, reason="LOWER_TEST",
                                              limits={**LIMITS, "provider_calls_per_utc_day_max": 800})
        self.assertEqual((replay["replayed"], replay["revision"]), (True, 2))
        with self.assertRaisesRegex(AccountBudgetError, "ACCOUNT_BUDGET_REVISION_STALE"):
            revise_account_budget_policy(self.fx.store, expected_revision=1, now=T0, reason="RAISE_TEST",
                                         limits={**LIMITS, "provider_calls_per_utc_day_max": 5000})
        revise_account_budget_policy(self.fx.store, expected_revision=2, now=T0, reason="RAISE_TEST",
                                     limits={**LIMITS, "provider_calls_per_utc_day_max": 5000,
                                             "modeled_credits_per_utc_day_max": 5000})
        self.fx.debit(B, calls=DAY_CAP)
        blocked, denial = self.fx.gate(B)
        self.assertEqual((blocked, denial["budget_scope"], denial["budget_dimension"]),
                         ("BLOCKED_BUDGET", "ACTIVATION", "DAY_PROVIDER_CALLS"))
        self.assertIsNone(self.fx.gate(A)[0])
        self.assertEqual(raw_shared(self.fx.path, DAY)[0], 900 + DAY_CAP)

    def test_commissioning_includes_spend_after_prepare_and_refuses_stale_or_restore(self):
        self.fx.debit(A, calls=100)
        plan = prepare_account_budget(self.fx.store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                      limits=LIMITS, now=T0)
        self.assertEqual((plan["terminal"], plan["shared_usage_at_prepare"]["day_provider_calls"]),
                         ("ACCOUNT_BUDGET_PLAN_READY", 100))
        self.fx.debit(A, calls=130)  # A-tail spend between rehearsal and APPLY
        self.fx.activation(C)
        with self.assertRaisesRegex(AccountBudgetError, "ACCOUNT_BUDGET_PLAN_STALE"):
            apply_account_budget(self.fx.store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                 limits=LIMITS, expected_plan_sha256=plan["plan_sha256"], now=T0)
        lease = self.fx.store.acquire_lease("restore", clock=T0)
        self.fx.store.set_restore_marker("RESTORE-EPOCH-1", clock=T0)
        self.fx.store.release_lease(lease)
        self.assertTrue(self.fx.store.restore_marker_unresolved())
        with self.assertRaisesRegex(AccountBudgetError, "RESTORE_MARKER_UNRESOLVED"):
            apply_account_budget(self.fx.store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                 limits=LIMITS, expected_plan_sha256="0" * 64, now=T0)
        if True:
            self.assertEqual(prepare_account_budget(self.fx.store, account_scope_id=SCOPE, limits=LIMITS,
                             credential_locator="JUPITER_FREE_API_KEY", now=T0)["terminal"],
                             "RESTORE_MARKER_UNRESOLVED")
        lease = self.fx.store.acquire_lease("resolve")  # resolve_restore_marker uses the wall clock
        self.fx.store.resolve_restore_marker()
        self.fx.store.release_lease(lease)
        _, applied = self.fx.commission()
        self.assertEqual(applied["baseline_at_apply"]["day_provider_calls"], 130)
        self.assertEqual(applied["member_count"], 3)

    def test_backup_copy_restores_same_debt_and_refuses_bypass(self):
        self.fx.debit(A, calls=DAY_CAP)
        self.fx.commission()
        copy_path = Path(self.tmp.name) / "restored" / "observation_schedule_state.sqlite"
        copy_path.parent.mkdir()
        with closing(sqlite3.connect(copy_path)) as target:
            self.fx.store._conn.backup(target)
        restored = ObservationScheduleStore(copy_path)
        self.addCleanup(restored.close)
        status = account_budget_status(restored, now=T0)
        self.assertEqual((status["mode"], status["shared_usage"]["day_provider_calls"]), ("MANAGED", DAY_CAP))
        lease = restored.acquire_lease("restored", clock=T0)
        self.assertEqual(_Accounting(restored, schedule(B), B[1], T0).gate(now=T0), "BLOCKED_BUDGET")
        restored.release_lease(lease)

    def test_accounting_built_before_commissioning_obeys_shared_gate(self):
        self.fx.debit(A, calls=DAY_CAP)
        lease = self.fx.store.acquire_lease("long-lived", clock=T0)
        early_b = self.fx.accounting(B)
        self.assertIsNone(early_b.gate(now=T0))
        self.fx.store.release_lease(lease)
        self.fx.commission()
        lease = self.fx.store.acquire_lease("long-lived", clock=T0)
        self.assertEqual(early_b.reserve_call(credits=1, now=T0), "BLOCKED_BUDGET")
        self.assertEqual(early_b.last_denial["budget_scope"], "SHARED_ACCOUNT")
        self.fx.store.release_lease(lease)

    def test_partial_account_schema_fails_closed(self):
        self.fx.store._conn.execute("DROP TABLE account_budget_policies")
        self.fx.store._conn.commit()
        self.assertEqual(self.fx.store.account_budget_binding(schedule_sha256=A[0], activation_id=A[1])["reason"],
                         "ACCOUNT_BUDGET_SCHEMA_PARTIAL")
        self.assertEqual(self.fx.gate(A)[1]["budget_dimension"], "ACCOUNT_BINDING")

    def test_readonly_pre_bridge_schema_reads_as_unmanaged(self):
        for table in ("account_budget_members", "account_budget_policies", "account_budget_scopes"):
            self.fx.store._conn.execute(f"DROP TABLE {table}")
        self.fx.store._conn.commit()
        self.fx.store.close()
        old = ObservationScheduleStore(self.fx.path, readonly=True, immutable=False)
        self.addCleanup(old.close)
        self.assertEqual(old.account_budget_binding(schedule_sha256=A[0], activation_id=A[1]), {"mode": "UNMANAGED"})
        self.assertIsNone(old.account_budget_scope())
        self.assertEqual(old._account_envelope(A, T0)["status"], "UNKNOWN")
        self.fx = StoreFixture(Path(self.tmp.name))
        self.addCleanup(self.fx.store.close)

    def test_shared_gate_cost_is_bounded_index_reads(self):
        self.fx.commission()
        for index in range(60):
            identity = (f"{index:064x}", f"ACT-HISTORY-{index:03d}")
            self.fx.activation(identity)
            for day in range(30):
                self.fx.debit(identity, day=(T0 - timedelta(days=day)).strftime("%Y-%m-%d"), calls=1)
        lease = self.fx.store.acquire_lease("perf", clock=T0)
        accounts = self.fx.accounting(B)
        started = time.perf_counter()
        for _ in range(200):
            self.assertIsNone(accounts.gate(now=T0))
        elapsed = (time.perf_counter() - started) / 200
        self.fx.store.release_lease(lease)
        plan = "\n".join(str(row[3]) for row in self.fx.store._conn.execute(
            "EXPLAIN QUERY PLAN SELECT COALESCE(SUM(c.provider_calls),0) FROM account_budget_members AS m "
            "JOIN accounting_counters AS c ON c.schedule_sha256=m.schedule_sha256 AND "
            "c.activation_id=m.activation_id AND c.utc_day=? WHERE m.account_scope_id=?", (DAY, SCOPE)))
        self.assertNotIn("SCAN c", plan)
        self.assertLess(elapsed, 0.02, elapsed)


class SharedAccountBudgetEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _tick(self, store, sc, schedule_doc, activation_id, at, clock, opener):
        from solana_alpha_lab.factory.opportunity_episode_tick import _EpisodeTick
        return _EpisodeTick(root=ROOT, data_root=sc.data_root, store=store, schedule=schedule_doc,
                            activation=store.get_activation(schedule_doc["schedule_sha256"], activation_id), now=at,
                            opener=opener, credential_loader=None, producer_git_sha="a" * 40, clock=clock,
                            fault_after=None, provider_call_wall_seconds=None, redact_with=None)

    def _second_activation(self, sc, store, at):
        doc = build_schedule(starts_at=at, stops_at=at + timedelta(days=1), assignment=sc.assignment,
                             schedule_key="OBS-OPPORTUNITY-EPISODES-SYNTH-SHARED-B-V1")
        lease = store.acquire_lease("successor-row", clock=at)
        store.upsert_activation({"schedule_sha256": doc["schedule_sha256"], "activation_id": "ACT-SHARED-B",
                                 "schedule_key": doc["schedule_key"], "state": "ACTIVE",
                                 "starts_at": doc["activation"]["starts_at"],
                                 "stops_admitting_at": doc["activation"]["stops_admitting_at"]}, clock=at)
        store.release_lease(lease)
        return doc

    def test_replay_and_new_occurrence_and_midnight_across_two_activations(self):
        from solana_alpha_lab.factory.observation_primitives import search_url
        from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock
        from solana_alpha_lab.factory.opportunity_episode_tick import SEARCH_PRIMITIVE
        start = datetime(2026, 10, 11, 23, 45, tzinfo=UTC)
        sc = EpisodeScenario(Path(self.tmp.name) / "rdp", start=start, stops=start + timedelta(hours=2))
        at = start + timedelta(minutes=14, seconds=40)
        mint = synth_mint("SharedReplay")
        sc.market.series[mint] = lambda now: token_object(mint, price=1, liquidity=10000, holders=60)
        clock = AdvancingClock(at)
        opener = SyntheticJupiter(sc.market, clock)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            plan = prepare_account_budget(store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                          limits=LIMITS, now=at)
            apply_account_budget(store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                 limits=LIMITS, expected_plan_sha256=plan["plan_sha256"], now=at)
            doc_b = self._second_activation(sc, store, at)
            lease = store.acquire_lease("episode-calls", clock=at)
            tick_a = self._tick(store, sc, sc.schedule, sc.activation_id, at, clock, opener)
            url = search_url([mint])
            trace = []
            self.assertEqual(tick_a._call(primitive_id=SEARCH_PRIMITIVE, url=url, occurrence="OCC-1",
                                          expected_entities=[mint], claim_identity=[mint])[0], "CALLED")
            trace.append(("A", "2026-10-11"))
            self.assertEqual(tick_a._call(primitive_id=SEARCH_PRIMITIVE, url=url, occurrence="OCC-1",
                                          expected_entities=[mint], claim_identity=[mint])[0], "RECOVERED")
            tick_b = self._tick(store, sc, doc_b, "ACT-SHARED-B", clock.now(), clock, opener)
            self.assertEqual(tick_b._call(primitive_id=SEARCH_PRIMITIVE, url=url, occurrence="OCC-2",
                                          expected_entities=[mint], claim_identity=[mint])[0], "CALLED")
            trace.append(("B", "2026-10-11"))
            clock.sleep((datetime(2026, 10, 11, 23, 59, 58, tzinfo=UTC) - clock.now()).total_seconds())
            original = store.start_call

            def durable_delay(**kwargs):
                result = original(**kwargs)
                clock.sleep(3)
                return result
            with patch.object(store, "start_call", side_effect=durable_delay):
                terminal, result = tick_b._call(primitive_id=SEARCH_PRIMITIVE, url=url, occurrence="OCC-3",
                                                expected_entities=[mint], claim_identity=[mint])
            self.assertEqual(terminal, "CALLED")
            self.assertTrue(result["request_started_at"].startswith("2026-10-12T00:00:"))
            trace += [("B", "2026-10-11"), ("B", "2026-10-12")]
            store.release_lease(lease)
        sends = [call for call in opener.calls if call["kind"] == "search"]
        self.assertEqual(len(sends), 3)  # replay made no HTTP; same URL new occurrence did
        for utc_day in ("2026-10-11", "2026-10-12"):
            expected_day = sum(1 for _, day in trace if day == utc_day)
            self.assertEqual(raw_shared(sc.ops_path, utc_day)[:2], (expected_day, expected_day))
        self.assertEqual(raw_shared(sc.ops_path, "2026-10-12")[2], len(trace))

    def test_shared_exhaustion_blocks_successor_before_transport_and_start(self):
        from solana_alpha_lab.factory.observation_primitives import search_url
        from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock
        from solana_alpha_lab.factory.opportunity_episode_tick import SEARCH_PRIMITIVE
        start = datetime(2026, 10, 12, 1, 0, tzinfo=UTC)
        sc = EpisodeScenario(Path(self.tmp.name) / "rdp", start=start, stops=start + timedelta(hours=2))
        at = start + timedelta(minutes=5)
        clock = AdvancingClock(at)
        opener = SyntheticJupiter(sc.market, clock)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            lease = store.acquire_lease("exhaust-a", clock=at)
            store.save_call_debit(schedule_sha256=sc.schedule["schedule_sha256"], activation_id=sc.activation_id,
                                  utc_day="2026-10-12", values={"provider_calls": DAY_CAP, "modeled_credits": DAY_CAP},
                                  lifetime_provider_calls=LIFE_CAP, lifetime_canonical_bytes=0, clock=at)
            store.release_lease(lease)
            plan = prepare_account_budget(store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                          limits=LIMITS, now=at)
            apply_account_budget(store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                 limits=LIMITS, expected_plan_sha256=plan["plan_sha256"], now=at)
            doc_b = self._second_activation(sc, store, at)
            lease = store.acquire_lease("successor-call", clock=at)
            tick_b = self._tick(store, sc, doc_b, "ACT-SHARED-B", at, clock, opener)
            terminal, result = tick_b._call(primitive_id=SEARCH_PRIMITIVE, url=search_url([synth_mint("X")]),
                                            occurrence="OCC-B", expected_entities=None, claim_identity=[])
            store.release_lease(lease)
            self.assertEqual((terminal, result), ("BLOCKED_BUDGET", None))
            self.assertEqual(tick_b.report["budget_denial"]["budget_scope"], "SHARED_ACCOUNT")
            self.assertIsNone(store.call_state("OCC-B"))
        self.assertEqual(opener.calls, [])

    def test_crash_after_reserve_before_started_keeps_debit_without_send(self):
        from solana_alpha_lab.factory.observation_primitives import search_url
        from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock
        from solana_alpha_lab.factory.opportunity_episode_tick import SEARCH_PRIMITIVE
        start = datetime(2026, 10, 12, 1, 0, tzinfo=UTC)
        sc = EpisodeScenario(Path(self.tmp.name) / "rdp", start=start, stops=start + timedelta(hours=2))
        at = start + timedelta(minutes=5)
        clock = AdvancingClock(at)
        opener = SyntheticJupiter(sc.market, clock)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            plan = prepare_account_budget(store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                          limits=LIMITS, now=at)
            apply_account_budget(store, account_scope_id=SCOPE, credential_locator="JUPITER_FREE_API_KEY",
                                 limits=LIMITS, expected_plan_sha256=plan["plan_sha256"], now=at)
            lease = store.acquire_lease("crash-before-started", clock=at)
            tick = self._tick(store, sc, sc.schedule, sc.activation_id, at, clock, opener)
            with patch.object(store, "start_call", side_effect=RuntimeError("process died")):
                with self.assertRaises(RuntimeError):
                    tick._call(primitive_id=SEARCH_PRIMITIVE, url=search_url([synth_mint("Crash")]),
                               occurrence="OCC-CRASH", expected_entities=None, claim_identity=[])
            store.release_lease(lease)
            self.assertIsNone(store.call_state("OCC-CRASH"))
        self.assertEqual(opener.calls, [])
        # The committed reservation survives the crash; nothing is refunded.
        self.assertEqual(raw_shared(sc.ops_path, "2026-10-12"), (1, 1, 1))

    def test_native_late_successor_on_public_tick_shares_one_account(self):
        start = datetime(2026, 10, 16, 23, 0, tzinfo=UTC)
        cut = start + timedelta(hours=1)
        sc = EpisodeScenario(Path(self.tmp.name) / "rdp", start=start, stops=cut)
        args = ["--provider-calls-per-utc-day-max", str(DAY_CAP), "--modeled-credits-per-utc-day-max", str(DAY_CAP),
                "--provider-calls-lifetime-max", str(LIFE_CAP)]
        plan = cli_command(sc.data_root, start, "account-budget-prepare", "--account-scope-id", SCOPE, *args)
        self.assertEqual((plan["terminal"], plan["credential_locator"]), ("ACCOUNT_BUDGET_PLAN_READY", "JUPITER_FREE_API_KEY"))
        applied = cli_command(sc.data_root, start, "account-budget-apply", "--account-scope-id", SCOPE, *args,
                              "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(applied["terminal"], "ACCOUNT_BUDGET_APPLIED")
        last_round = cut - timedelta(minutes=15)
        tail_mint = synth_mint("SharedLateTail")
        tail_row = token_object(tail_mint, price=1, liquidity=10000, holders=60)
        nominate(sc.market, last_round, {"toporganicscore": [tail_row], "toptraded": [], "toptrending": []})
        sc.market.series[tail_mint] = lambda _now: tail_row
        calls = []
        for at in (last_round + timedelta(seconds=5), cut + timedelta(seconds=5)):
            calls += sc.tick(at)["_calls"]
        self.assertEqual(sc.query("SELECT state FROM schedule_activations"), [("DRAINING",)])
        # Late successor through the native lifecycle; B digest sorts before A so
        # the default tick ordering, not hash luck, serves the tail first.
        b_start = cut + timedelta(minutes=15)
        for suffix in range(64):
            doc_b = build_schedule(starts_at=b_start, stops_at=cut + timedelta(days=1), assignment=sc.assignment,
                                   schedule_key=f"OBS-OPPORTUNITY-EPISODES-SYNTH-LATE-B-{suffix}-V1")
            if doc_b["schedule_sha256"] < sc.schedule["schedule_sha256"]:
                break
        register_authorize_activate(sc.data_root, doc_b, now=b_start, activation_id="ACT-LATE-B")
        members = dict(sc.query("SELECT activation_id, binding_source FROM account_budget_members"))
        self.assertEqual(members, {sc.activation_id: "COMMISSIONING", "ACT-LATE-B": "NATIVE_ACTIVATION"})
        new_mint = synth_mint("SharedLateIntake")
        new_row = token_object(new_mint, price=1, liquidity=10000, holders=60)
        nominate(sc.market, b_start, {"toporganicscore": [new_row], "toptraded": [], "toptrending": []})
        sc.market.series[new_mint] = lambda _now: new_row
        mixed = wall_tick(sc, b_start + timedelta(seconds=5))
        calls += mixed["_calls"]
        self.assertEqual(mixed["terminal"], "TICK_COMPLETE", mixed)
        self.assertEqual([item["activation_id"] for item in mixed["activations"]], [sc.activation_id, "ACT-LATE-B"])
        day = "2026-10-17"
        sends_today = sum(1 for call in calls if call["at"].startswith(day))
        self.assertEqual(raw_shared(sc.ops_path, day)[0], sends_today)
        self.assertEqual(raw_shared(sc.ops_path, day)[2], len(calls))
        # Near exhaustion: one shared call left. A's due tail is served first;
        # B's optional nomination gets a typed shared denial and no send.
        pending = sc.query("SELECT MIN(due_at) FROM due_observations WHERE activation_id=? AND state='PENDING' "
                           "AND due_at > ?", (sc.activation_id, "2026-10-17T00:20:00Z"))[0][0]
        due = datetime.fromisoformat(pending.replace("Z", "+00:00"))
        used = raw_shared(sc.ops_path, day)[0]
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            revise_account_budget_policy(store, expected_revision=1, now=due, reason="NEAR_EXHAUSTION_TEST",
                                         limits={**LIMITS, "provider_calls_per_utc_day_max": used + 1})
        nominate(sc.market, due, {"toporganicscore": [token_object(synth_mint("Starved"), price=1, liquidity=10000,
                                                                   holders=60)], "toptraded": [], "toptrending": []})
        tight = wall_tick(sc, due + timedelta(seconds=5))
        by_activation = {item["activation_id"]: item for item in tight["activations"]}
        self.assertEqual([call["kind"] for call in tight["_calls"]], ["search"], tight)
        self.assertEqual(by_activation[sc.activation_id]["provider_calls"], 1)
        self.assertEqual(by_activation["ACT-LATE-B"]["provider_calls"], 0)
        self.assertEqual(by_activation["ACT-LATE-B"]["budget_denial"]["budget_dimension"], "SHARED_DAY_PROVIDER_CALLS")
        self.assertEqual(raw_shared(sc.ops_path, day)[0], used + 1)
        status = cli_command(sc.data_root, due + timedelta(minutes=1), "account-budget-status")
        self.assertEqual((status["mode"], status["remaining"]["day_provider_calls"], status["policy_revision"]),
                         ("MANAGED", 0, 2))
        # Exhausted: the next due A batch gets the typed no-request gap, yet the
        # later tail stays PENDING and is observed once allocation returns.
        later = sc.query("SELECT DISTINCT due_at FROM due_observations WHERE activation_id=? AND state='PENDING' "
                         "ORDER BY due_at LIMIT 2", (sc.activation_id,))
        blocked_at, resumed_at = (datetime.fromisoformat(row[0].replace("Z", "+00:00")) for row in later)
        self.assertEqual(blocked_at.date(), due.date())
        blocked = wall_tick(sc, blocked_at + timedelta(seconds=5))
        self.assertEqual([call for call in blocked["_calls"] if call["kind"] == "search"], [])
        reasons = {row[0] for row in sc.query(
            "SELECT json_extract(payload_json,'$.missing_reason') FROM due_observations WHERE activation_id=? "
            "AND due_at=?", (sc.activation_id, later[0][0]))}
        self.assertEqual(reasons, {"SLOT_NOT_EXECUTED:BLOCKED_BUDGET"})
        pending_after_block = sc.query("SELECT COUNT(*) FROM due_observations WHERE activation_id=? AND "
                                       "state='PENDING'", (sc.activation_id,))[0][0]
        self.assertGreater(pending_after_block, 0)
        with closing(ObservationScheduleStore(sc.ops_path)) as store:
            revise_account_budget_policy(store, expected_revision=2, now=resumed_at, reason="RESTORE_TEST_LIMITS",
                                         limits=dict(LIMITS))
        resumed = wall_tick(sc, resumed_at + timedelta(seconds=5))
        self.assertTrue(any(call["kind"] == "search" for call in resumed["_calls"]), resumed)
        observed = sc.query("SELECT state FROM due_observations WHERE activation_id=? AND due_at=?",
                            (sc.activation_id, later[1][0]))
        self.assertEqual({row[0] for row in observed}, {"OBSERVED"})


if __name__ == "__main__":
    unittest.main()
