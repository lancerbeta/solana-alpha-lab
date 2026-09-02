"""Regression proofs for ObservationSchedule pacing / due-pressure closure V2."""

from __future__ import annotations

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
from solana_alpha_lab.factory.due_pressure import (  # noqa: E402
    backlog_risk_from_due_pressure,
    build_due_pressure_projection,
)
from solana_alpha_lab.factory.observation_provider_pacing import (  # noqa: E402
    AdvancingClock,
    ProviderTickContext,
    usable_due_calls_per_tick,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    ObservationLifecycleError,
    _authority_policy,
    _minimum_expiry,
    _used_provider_route_ids,
    abort_schedule,
    activate_schedule,
    authorize_schedule,
    expected_authority_phrase,
    resume_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    ObservationSchedulerError,
    _Accounting,
    tick_once,
)

GIT_SHA = "d" * 40
MINT = "Mint111111111111111111111111111111111111111"
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
    activation_id = "ACT-PACING-V2"
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
    from solana_alpha_lab.factory.observation_schedule import canonical_sha256

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


class ObservationRuntimePacingClosureTests(unittest.TestCase):
    def test_legacy_starvation_falsifier_frozen_tick_clock(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            accounts = _Accounting(
                store,
                schedule,
                activation_id,
                NOW,
            )
            accounts.note(completed_at=NOW)
            self.assertEqual(accounts.gate(now=NOW), "PACE_WAIT")
            store.close()

    def test_repaired_runtime_executes_recent_and_search_same_tick(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            store.insert_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
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
            opener = _Opener()
            result = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
                max_claims=5,
            )
            joined = "".join(opener.urls)
            self.assertIn("/tokens/v2/recent", joined)
            self.assertIn("/tokens/v2/search", joined, msg=f"urls={opener.urls} terminal={result}")
            self.assertEqual(result["terminal"], "TICK_COMPLETE")
            store.close()

    def test_future_not_due_alone_does_not_trigger_backlog_risk(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            for index in range(150):
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": f"Mint{index:03d}111111111111111111111111111111111",
                        "point_id": "X300",
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "state": "PENDING",
                        "due_at": render_utc(NOW + timedelta(hours=2)),
                        "deadline_at": render_utc(NOW + timedelta(hours=2, seconds=300)),
                        "request_sha256": None,
                        "call_occurrence_id": None,
                        "payload": {},
                    },
                    clock=NOW,
                )
            projection = build_due_pressure_projection(
                store,
                now=NOW,
                schedule_sha256=schedule["schedule_sha256"],
                activation_id=activation_id,
            )
            self.assertEqual(projection["future_not_due_count"], 150)
            self.assertFalse(backlog_risk_from_due_pressure(projection))
            store.close()

    def test_genuine_deadline_pressure_triggers_backlog_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            store.insert_due(
                {
                    "schedule_sha256": "a" * 64,
                    "activation_id": "ACT-X",
                    "entity_id": MINT,
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "state": "PENDING",
                    "due_at": render_utc(NOW - timedelta(minutes=5)),
                    "deadline_at": render_utc(NOW + timedelta(seconds=30)),
                    "request_sha256": None,
                    "call_occurrence_id": None,
                    "payload": {},
                },
                clock=NOW,
            )
            projection = build_due_pressure_projection(
                store,
                now=NOW,
                schedule_sha256="a" * 64,
                activation_id="ACT-X",
            )
            self.assertTrue(backlog_risk_from_due_pressure(projection))
            store.close()

    def test_oracle_matches_runtime_tick_budget(self) -> None:
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
        oracle = evaluate_schedulability(
            root=ROOT,
            schedule=schedule,
            candidate_launches_per_utc_day=2000,
        ).as_dict()
        self.assertIn(
            oracle["terminal"],
            {"SCHEDULABLE_WITH_HEADROOM", "STOP_FREE_TIER_CAPACITY_NOT_PROVEN"},
        )

    def test_abort_schedule_blocks_resume(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            store.transition_activation(
                schedule_sha256=schedule["schedule_sha256"],
                activation_id=activation_id,
                new_state="PAUSED_OPERATOR",
                authority_receipt_sha256="r" * 64,
                effective_at=render_utc(NOW),
                payload={"paused": True},
                clock=NOW,
            )
            result = abort_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=schedule["schedule_sha256"],
                activation_id=activation_id,
                reason="SEARCH_STARVATION_RUNTIME_ORACLE_MISMATCH",
                now=NOW,
                producer_git_sha=GIT_SHA,
            )
            self.assertEqual(result["state"], "ABORTED_SAFETY")
            with self.assertRaises(ObservationLifecycleError):
                resume_schedule(
                    data_root=data_root,
                    store=store,
                    schedule_sha256=schedule["schedule_sha256"],
                    activation_id=activation_id,
                    now=NOW + timedelta(minutes=1),
                    producer_git_sha=GIT_SHA,
                )
            store.close()


if __name__ == "__main__":
    unittest.main()
