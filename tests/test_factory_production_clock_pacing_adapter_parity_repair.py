"""Production clock / pacing adapter parity repair for ObservationSchedule."""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_schedulability_oracle import (  # noqa: E402
    evaluate_schedulability,
)
from solana_alpha_lab.factory.observation_provider_pacing import (  # noqa: E402
    AdvancingClock,
    ClockSleepRequiredError,
    FREE_TIER_MIN_PACE_SECONDS,
    ProviderTickContext,
    WallClock,
    clock_has_sleep,
    legacy_bare_callable_pace_starvation_terminal,
    require_sleep_capable_clock,
    usable_due_calls_per_tick,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    canonical_sha256,
    load_observation_schedule,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    _authority_policy,
    _minimum_expiry,
    _used_provider_route_ids,
    activate_schedule,
    authorize_schedule,
    expected_authority_phrase,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    ObservationSchedulerError,
    _Accounting,
    tick_once,
)

GIT_SHA = "e" * 40
MINT = "Mint222222222222222222222222222222222222222"
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)


class _Opener:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def open(self, url: str) -> dict:
        self.urls.append(url)
        if "/tokens/v2/search" in url:
            return {"http_status": 200, "body": [{"id": MINT, "liquidity": "2000"}]}
        return {"http_status": 200, "body": [{"id": MINT, "launchpad": "pump.fun"}]}


def _activate(store: ObservationScheduleStore, schedule: dict) -> str:
    data_root = store.path.parent / "rdp"
    data_root.mkdir(parents=True, exist_ok=True)
    activation_id = "ACT-CLOCK-PARITY"
    store.persist_registered_schedule(
        schedule_sha256=schedule["schedule_sha256"],
        schedule_key=schedule["schedule_key"],
        document=schedule,
        clock=NOW,
    )
    expires_at = render_utc(_minimum_expiry(schedule))
    _, routes = _used_provider_route_ids(ROOT, schedule)
    policy = _authority_policy(
        root=ROOT,
        document=schedule,
        schedule_key=schedule["schedule_key"],
        expires_at=expires_at,
    )
    phrase = expected_authority_phrase(
        schedule_sha256=schedule["schedule_sha256"],
        schedule_key=schedule["schedule_key"],
        activation_starts_at=schedule["activation"]["starts_at"],
        activation_stops_admitting_at=schedule["activation"]["stops_admitting_at"],
        provider_route_ids=routes,
        expires_at=expires_at,
        policy_digest=canonical_sha256(policy),
    )
    authorize_schedule(
        root=ROOT,
        data_root=data_root,
        store=store,
        schedule_sha256=schedule["schedule_sha256"],
        phrase=phrase,
        now=NOW,
        producer_git_sha=GIT_SHA,
    )
    activate_schedule(
        root=ROOT,
        data_root=data_root,
        store=store,
        schedule_sha256=schedule["schedule_sha256"],
        activation_id=activation_id,
        now=NOW,
        producer_git_sha=GIT_SHA,
    )
    return activation_id


def _insert_dues(store: ObservationScheduleStore, schedule: dict, activation_id: str, n: int) -> None:
    for index in range(n):
        store.insert_due(
            {
                "schedule_sha256": schedule["schedule_sha256"],
                "activation_id": activation_id,
                "entity_id": f"Mint{index:03d}222222222222222222222222222222222",
                "point_id": "X300",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "state": "DUE",
                "due_at": render_utc(NOW),
                "deadline_at": render_utc(NOW + timedelta(seconds=300)),
                "request_sha256": None,
                "call_occurrence_id": None,
                "payload": {},
            },
            clock=NOW,
        )


class ProductionClockPacingAdapterParityTests(unittest.TestCase):
    def test_legacy_bare_callable_clock_starvation_trace(self) -> None:
        result = legacy_bare_callable_pace_starvation_terminal()
        self.assertEqual(result["terminal"], "PACE_WAIT")
        self.assertEqual(result["pace_waits"], 20)
        self.assertFalse(result["injectable_advanced"])
        self.assertIn("SEARCH_PROVIDER_CALL_NEVER", result["trace"])

    def test_bare_callable_rejected_by_require_and_context(self) -> None:
        bare = lambda: datetime.now(UTC)  # noqa: E731
        self.assertFalse(clock_has_sleep(bare))
        with self.assertRaises(ClockSleepRequiredError):
            require_sleep_capable_clock(bare)
        with self.assertRaises(ClockSleepRequiredError):
            ProviderTickContext(tick_start=NOW, pace_seconds=3, injectable_clock=bare)

    def test_production_cli_uses_wall_clock_not_bare_lambda(self) -> None:
        cli_src = (ROOT / "scripts" / "observation_schedule.py").read_text(encoding="utf-8")
        seam_src = (
            ROOT
            / "src"
            / "solana_alpha_lab"
            / "factory"
            / "observation_schedule_composition.py"
        ).read_text(encoding="utf-8")
        self.assertIn("materialize_tick_physical_dependencies", cli_src)
        self.assertNotIn("lambda: datetime.now(UTC)", cli_src)
        self.assertNotIn("lambda: datetime.now(UTC)", seam_src)
        self.assertIn("WallClock()", seam_src)
        tree = ast.parse(seam_src)
        found_wall = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "WallClock":
                    found_wall = True
        self.assertTrue(found_wall)

    def test_wall_clock_has_now_and_sleep(self) -> None:
        clock = WallClock()
        self.assertTrue(clock_has_sleep(clock))
        self.assertIsNotNone(clock.now().tzinfo)
        # sleep(0) must be a no-op (no real wait in suite)
        clock.sleep(0)

    def test_recent_and_search_same_tick_with_advancing_clock(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            _insert_dues(store, schedule, activation_id, 1)
            opener = _Opener()
            clock = AdvancingClock(NOW)
            result = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
                clock=clock,
                max_claims=5,
            )
            joined = "".join(opener.urls)
            self.assertIn("/tokens/v2/recent", joined)
            self.assertIn("/tokens/v2/search", joined, msg=f"urls={opener.urls} terminal={result}")
            self.assertEqual(result["terminal"], "TICK_COMPLETE")
            self.assertNotEqual(result.get("terminal"), "PACE_WAIT")
            store.close()

    def test_four_search_dues_progress_same_tick_with_spacing(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            _insert_dues(store, schedule, activation_id, 4)
            clock = AdvancingClock(NOW)
            completion_times: list[datetime] = []

            class _TimedOpener(_Opener):
                def open(self, url: str) -> dict:
                    completion_times.append(clock())
                    return super().open(url)

            timed = _TimedOpener()
            result = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=timed,
                producer_git_sha=GIT_SHA,
                clock=clock,
                max_claims=10,
            )
            self.assertIn("/tokens/v2/recent", "".join(timed.urls))
            self.assertTrue(any("/tokens/v2/search" in u for u in timed.urls), timed.urls)
            self.assertEqual(result["terminal"], "TICK_COMPLETE")
            # Batched SEARCH may collapse dues into fewer HTTP calls; claims must progress.
            self.assertGreaterEqual(int(result.get("provider_calls", 0)), 2)
            dues = [
                row[0]
                for row in store._conn.execute(
                    "SELECT state FROM due_observations WHERE activation_id=? AND point_id='X300'",
                    (activation_id,),
                ).fetchall()
            ]
            self.assertEqual(len(dues), 4)
            allowed = {"OBSERVED", "MISSING_TYPED", "DISAPPEARED"}
            self.assertTrue(
                all(state in allowed for state in dues),
                msg=f"dues={dues} terminal={result}",
            )
            self.assertGreaterEqual(len(completion_times), 2)
            for earlier, later in zip(completion_times, completion_times[1:]):
                self.assertGreaterEqual(
                    (later - earlier).total_seconds(),
                    FREE_TIER_MIN_PACE_SECONDS,
                )
            store.close()

    def test_tick_once_rejects_bare_callable_clock(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            with self.assertRaises(ObservationSchedulerError):
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    opener=_Opener(),
                    producer_git_sha=GIT_SHA,
                    clock=(lambda: datetime.now(UTC)),
                )
            store.close()

    def test_pace_wait_defers_without_scientific_missingness(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            accounts = _Accounting(store, schedule, activation_id, NOW)
            accounts.note(completed_at=NOW)
            clock = AdvancingClock(NOW)
            ctx = ProviderTickContext(
                tick_start=NOW,
                pace_seconds=3,
                injectable_clock=clock,
                tick_wall_budget_seconds=0,
            )
            blocked = ctx.wait_for_provider_slot(accounts)
            self.assertEqual(blocked, "PACE_WAIT")
            self.assertEqual(ctx.provider_completions, 0)
            store.close()

    def test_oracle_geometry_unchanged_seventeen_due_slots(self) -> None:
        self.assertEqual(
            usable_due_calls_per_tick(
                pace_seconds=3,
                poll_period_seconds=60,
                max_claims_per_tick=60,
            ),
            17,
        )
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        self.assertEqual(int(schedule["budgets"]["min_provider_pace_seconds"]), 3)
        self.assertFalse(bool(schedule["budgets"].get("allow_retry", False)))
        self.assertFalse(bool(schedule["budgets"].get("allow_fallback", False)))
        oracle = evaluate_schedulability(
            root=ROOT,
            schedule=schedule,
            candidate_launches_per_utc_day=2000,
        ).as_dict()
        self.assertIn(
            oracle["terminal"],
            {"SCHEDULABLE_WITH_HEADROOM", "STOP_FREE_TIER_CAPACITY_NOT_PROVEN"},
        )


if __name__ == "__main__":
    unittest.main()
