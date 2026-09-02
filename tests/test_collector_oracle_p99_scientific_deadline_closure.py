"""p99 must fit inside allowed X lateness for recommended envelopes."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.collector_campaign_preflight import (  # noqa: E402
    build_campaign_schedule_document,
    run_campaign_preflight,
)
from solana_alpha_lab.factory.collector_schedulability_oracle import (  # noqa: E402
    _simulate_due_lateness,
    evaluate_schedulability,
)
from solana_alpha_lab.factory.observation_provider_pacing import (  # noqa: E402
    usable_due_calls_per_tick,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    validate_observation_schedule,
)

COMMISSIONING_STARTS_AT = datetime(2026, 9, 1, 21, 50, tzinfo=UTC)
FORBIDDEN_PROPOSAL_SHA256 = (
    "50b2d070361b04be0f983c4bb801be5bf3b01e06783e45b9e0a9fb04a9facc19"
)


def _probe(*, max_members: int) -> dict:
    document = build_campaign_schedule_document(
        starts_at=COMMISSIONING_STARTS_AT,
        max_members_per_utc_day=max_members,
        max_candidates_per_utc_day=2000,
    )
    return validate_observation_schedule(document, root=ROOT)


class CollectorOracleP99ScientificDeadlineClosureTests(unittest.TestCase):
    def test_usable_due_calls_remain_seventeen(self) -> None:
        self.assertEqual(
            usable_due_calls_per_tick(
                pace_seconds=3,
                poll_period_seconds=60,
                max_claims_per_tick=60,
            ),
            17,
        )

    def test_legacy_102_geometry_has_p99_outside_x_window(self) -> None:
        p95, p99, _ = _simulate_due_lateness(
            members=102,
            point_count=8,
            batch_size=100,
            pace_seconds=3,
            timer_cadence_seconds=60,
            max_claims=60,
            poll_period_seconds=60,
            worst_case_unbatched=True,
        )
        self.assertEqual(p95, 300)
        self.assertEqual(p99, 360)
        self.assertGreater(p99, 300)

    def test_oracle_rejects_102_as_recommended_envelope(self) -> None:
        result = evaluate_schedulability(
            root=ROOT,
            schedule=_probe(max_members=114),
            candidate_launches_per_utc_day=2000,
        )
        self.assertEqual(result.terminal, "SCHEDULABLE_WITH_HEADROOM")
        self.assertLessEqual(result.p99_due_lateness_seconds, 300)
        self.assertNotEqual(result.recommended_max_members_per_utc_day, 102)
        self.assertEqual(result.recommended_max_members_per_utc_day, 85)
        self.assertEqual(result.recommended_inclusion_probability, "0.0425")
        self.assertGreaterEqual(result.x_deadline_headroom_seconds, 0)
        self.assertEqual(result.p95_due_lateness_seconds, 240)
        self.assertEqual(result.p99_due_lateness_seconds, 300)

    def test_boundary_85_accepted_86_not_as_recommended(self) -> None:
        at_bound = evaluate_schedulability(
            root=ROOT,
            schedule=_probe(max_members=85),
            candidate_launches_per_utc_day=2000,
        )
        self.assertEqual(at_bound.recommended_max_members_per_utc_day, 85)
        self.assertEqual(at_bound.p99_due_lateness_seconds, 300)
        self.assertEqual(at_bound.x_deadline_headroom_seconds, 0)
        beyond = evaluate_schedulability(
            root=ROOT,
            schedule=_probe(max_members=86),
            candidate_launches_per_utc_day=2000,
        )
        self.assertEqual(beyond.recommended_max_members_per_utc_day, 85)
        self.assertLessEqual(beyond.p99_due_lateness_seconds, 300)

    def test_preflight_applies_p99_safe_envelope(self) -> None:
        preflight = run_campaign_preflight(
            root=ROOT,
            starts_at=COMMISSIONING_STARTS_AT,
            max_members_per_utc_day=114,
            candidate_launches_per_utc_day=2000,
        )
        oracle = preflight["schedulability"]
        schedule = preflight["schedule"]
        self.assertEqual(preflight["terminal"], "CAMPAIGN_PREFLIGHT_PROPOSED")
        self.assertEqual(oracle["recommended_max_members_per_utc_day"], 85)
        self.assertEqual(oracle["recommended_inclusion_probability"], "0.0425")
        self.assertEqual(oracle["p95_due_lateness_seconds"], 240)
        self.assertEqual(oracle["p99_due_lateness_seconds"], 300)
        self.assertGreaterEqual(oracle["x_deadline_headroom_seconds"], 0)
        self.assertEqual(schedule["sampling"]["max_members_per_utc_day"], 85)
        self.assertEqual(schedule["sampling"]["inclusion_probability"], "0.0425")
        self.assertEqual(oracle["predicted_provider_calls_per_day"], 2120)
        self.assertNotEqual(preflight["schedule_sha256"], FORBIDDEN_PROPOSAL_SHA256)
        self.assertEqual(
            int(schedule["budgets"]["provider_calls_per_utc_day_max"]),
            2650,
        )
        self.assertEqual(
            int(schedule["budgets"]["provider_calls_lifetime_max"]),
            55650,
        )


if __name__ == "__main__":
    unittest.main()
