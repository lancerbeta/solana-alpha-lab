"""Regression: inclusion probability follows applied member cap, not capacity ceiling."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.collector_campaign_preflight import (  # noqa: E402
    run_campaign_preflight,
)
from solana_alpha_lab.factory.collector_schedulability_oracle import (  # noqa: E402
    evaluate_schedulability,
    recommended_inclusion_probability,
)
from solana_alpha_lab.factory.observation_schedule import validate_observation_schedule  # noqa: E402
from solana_alpha_lab.factory.collector_campaign_preflight import (  # noqa: E402
    build_campaign_schedule_document,
)

BROKEN_SCHEDULE_SHA256 = (
    "490c21b69a1f8f8f878eb9d909f3fce62e3ffa9891c73d2e85ade9790949f7d8"
)
INVALID_PROPOSAL_SHA256 = (
    "02152e3136ad5318d7bb6134f2f6d6e0080f8e1c1b0ee1a18a69cdec3d37ea57"
)
COMMISSIONING_STARTS_AT = datetime(2026, 9, 1, 21, 50, tzinfo=UTC)


def _probe_schedule(*, max_members: int) -> dict:
    document = build_campaign_schedule_document(
        starts_at=COMMISSIONING_STARTS_AT,
        max_members_per_utc_day=max_members,
        max_candidates_per_utc_day=2000,
    )
    return validate_observation_schedule(document, root=ROOT)


class CollectorSamplingOracleAppliedProbabilityRepairTests(unittest.TestCase):
    def test_applied_cap_clamped_to_executable_oracle_envelope(self) -> None:
        result = evaluate_schedulability(
            root=ROOT,
            schedule=_probe_schedule(max_members=114),
            candidate_launches_per_utc_day=2000,
        )
        self.assertEqual(result.max_supported_members_per_day, 456)
        self.assertEqual(result.recommended_max_members_per_utc_day, 102)
        self.assertEqual(result.recommended_inclusion_probability, "0.051")
        self.assertEqual(
            recommended_inclusion_probability(
                recommended_members=102,
                candidate_launches_per_utc_day=2000,
            ),
            "0.051",
        )

    def test_capacity_ceiling_member_cap_yields_p_228(self) -> None:
        self.assertEqual(
            recommended_inclusion_probability(
                recommended_members=456,
                candidate_launches_per_utc_day=2000,
            ),
            "0.228",
        )
        result = evaluate_schedulability(
            root=ROOT,
            schedule=_probe_schedule(max_members=114),
            candidate_launches_per_utc_day=2000,
        )
        self.assertEqual(result.max_supported_members_per_day, 456)
        self.assertEqual(
            recommended_inclusion_probability(
                recommended_members=min(500, result.max_supported_members_per_day),
                candidate_launches_per_utc_day=2000,
            ),
            "0.228",
        )

    def test_commissioning_preflight_frozen_envelope(self) -> None:
        preflight = run_campaign_preflight(
            root=ROOT,
            starts_at=COMMISSIONING_STARTS_AT,
            max_members_per_utc_day=114,
            candidate_launches_per_utc_day=2000,
        )
        oracle = preflight["schedulability"]
        schedule = preflight["schedule"]
        self.assertEqual(preflight["terminal"], "CAMPAIGN_PREFLIGHT_PROPOSED")
        self.assertEqual(oracle["terminal"], "SCHEDULABLE_WITH_HEADROOM")
        self.assertEqual(oracle["recommended_max_members_per_utc_day"], 102)
        self.assertEqual(oracle["recommended_inclusion_probability"], "0.051")
        self.assertEqual(oracle["predicted_provider_calls_per_day"], 2256)
        self.assertEqual(oracle["headroom_pct"], 92)
        self.assertEqual(
            int(schedule["budgets"]["provider_calls_per_utc_day_max"]),
            2820,
        )
        self.assertEqual(
            int(schedule["budgets"]["provider_calls_lifetime_max"]),
            59220,
        )
        self.assertEqual(
            schedule["population"]["source_predicates"][0],
            {
                "field_id": "FIELD-LAUNCHPAD-001",
                "operator": "EQ",
                "value_text": "pump.fun",
            },
        )
        self.assertEqual(schedule["sampling"]["max_members_per_utc_day"], 102)
        self.assertEqual(schedule["sampling"]["inclusion_probability"], "0.051")

    def test_repaired_schedule_identity_differs_from_broken_and_invalid(self) -> None:
        preflight = run_campaign_preflight(
            root=ROOT,
            starts_at=COMMISSIONING_STARTS_AT,
            max_members_per_utc_day=114,
            candidate_launches_per_utc_day=2000,
        )
        repaired_sha = preflight["schedule_sha256"]
        self.assertNotEqual(repaired_sha, BROKEN_SCHEDULE_SHA256)
        self.assertNotEqual(repaired_sha, INVALID_PROPOSAL_SHA256)


if __name__ == "__main__":
    unittest.main()
