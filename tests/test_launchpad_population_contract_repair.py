"""Launchpad population contract repair — Jupiter live shape regression proofs."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_campaign_preflight import (  # noqa: E402
    build_campaign_schedule_document,
    run_campaign_preflight,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    _population_eligible,
    tick_once,
)
from solana_alpha_lab.factory.tokens_v2_typed_projection import (  # noqa: E402
    STATE_MISSING,
    STATE_OBSERVED,
    project_tokens_v2_field,
    sanitize_tokens_v2_source_row,
)
from tests.test_observation_scheduler import GIT_SHA, NOW, _Opener, _activate  # noqa: E402

BROKEN_SCHEDULE_SHA256 = (
    "490c21b69a1f8f8f878eb9d909f3fce62e3ffa9891c73d2e85ade9790949f7d8"
)

LIVE_ROW = {
    "id": "MintLiveShape111111111111111111111111111111",
    "launchpad": "pump.fun",
    "firstPool": {"createdAt": "2026-09-01T20:09:38Z"},
}

NON_PUMP_ROW = {
    "id": "MintOtherLaunchpad111111111111111111111111111",
    "launchpad": "met-dbc",
    "firstPool": {"createdAt": "2026-09-01T20:09:38Z"},
}

MISSING_LAUNCHPAD_ROW = {
    "id": "MintMissingLaunchpad11111111111111111111111",
    "firstPool": {"createdAt": "2026-09-01T20:09:38Z"},
}


class LaunchpadPopulationContractRepairTests(unittest.TestCase):
    def test_launchpad_projection_observed_on_live_shape(self) -> None:
        value, state, missing = project_tokens_v2_field(LIVE_ROW, "FIELD-LAUNCHPAD-001")
        self.assertEqual(state, STATE_OBSERVED)
        self.assertEqual(value, "pump.fun")
        self.assertIsNone(missing)

    def test_first_pool_source_remains_missing_on_live_shape(self) -> None:
        value, state, missing = project_tokens_v2_field(
            LIVE_ROW, "FIELD-FIRST-POOL-SOURCE-001"
        )
        self.assertIsNone(value)
        self.assertEqual(state, STATE_MISSING)
        self.assertEqual(missing, "FIELD_ABSENT")

    def test_sanitizer_retains_launchpad(self) -> None:
        sanitized = sanitize_tokens_v2_source_row(LIVE_ROW)
        self.assertEqual(sanitized.get("launchpad"), "pump.fun")
        self.assertNotIn("source", sanitized)

    def test_campaign_predicate_passes_pump_fun_launchpad(self) -> None:
        schedule = validate_observation_schedule(
            build_campaign_schedule_document(
                starts_at=datetime(2026, 9, 2, 0, 0, tzinfo=UTC)
            ),
            root=ROOT,
        )
        self.assertTrue(_population_eligible(schedule, LIVE_ROW))

    def test_campaign_predicate_rejects_non_pump_fun(self) -> None:
        schedule = validate_observation_schedule(
            build_campaign_schedule_document(
                starts_at=datetime(2026, 9, 2, 0, 0, tzinfo=UTC)
            ),
            root=ROOT,
        )
        self.assertFalse(_population_eligible(schedule, NON_PUMP_ROW))

    def test_campaign_predicate_fails_closed_without_launchpad(self) -> None:
        schedule = validate_observation_schedule(
            build_campaign_schedule_document(
                starts_at=datetime(2026, 9, 2, 0, 0, tzinfo=UTC)
            ),
            root=ROOT,
        )
        self.assertFalse(_population_eligible(schedule, MISSING_LAUNCHPAD_ROW))

    def test_preflight_schedule_uses_launchpad_field(self) -> None:
        result = run_campaign_preflight(
            root=ROOT,
            starts_at=datetime(2026, 9, 2, 0, 0, tzinfo=UTC),
        )
        predicate = result["schedule"]["population"]["source_predicates"][0]
        self.assertEqual(predicate["field_id"], "FIELD-LAUNCHPAD-001")
        self.assertEqual(predicate["value_text"], "pump.fun")

    def test_repaired_schedule_identity_differs_from_broken_schedule(self) -> None:
        starts = datetime(2026, 9, 1, 20, 5, tzinfo=UTC)
        repaired_sha = run_campaign_preflight(
            root=ROOT,
            starts_at=starts,
            max_members_per_utc_day=114,
            candidate_launches_per_utc_day=2000,
        )["schedule_sha256"]
        self.assertNotEqual(repaired_sha, BROKEN_SCHEDULE_SHA256)
        old_predicate_doc = validate_observation_schedule(
            {
                **build_campaign_schedule_document(
                    starts_at=starts,
                    inclusion_probability="0.057",
                    max_members_per_utc_day=114,
                    max_candidates_per_utc_day=2000,
                ),
                "population": {
                    **build_campaign_schedule_document(
                        starts_at=starts,
                        inclusion_probability="0.057",
                        max_members_per_utc_day=114,
                        max_candidates_per_utc_day=2000,
                    )["population"],
                    "source_predicates": [
                        {
                            "field_id": "FIELD-FIRST-POOL-SOURCE-001",
                            "operator": "EQ",
                            "value_text": "pump.fun",
                        }
                    ],
                },
            },
            root=ROOT,
        )
        new_predicate_doc = validate_observation_schedule(
            build_campaign_schedule_document(
                starts_at=starts,
                inclusion_probability="0.057",
                max_members_per_utc_day=114,
                max_candidates_per_utc_day=2000,
            ),
            root=ROOT,
        )
        self.assertNotEqual(
            schedule_sha256(old_predicate_doc),
            schedule_sha256(new_predicate_doc),
        )

    def test_bernoulli_sampling_reachable_after_predicate_pass(self) -> None:
        schedule = validate_observation_schedule(
            build_campaign_schedule_document(
                starts_at=datetime(2026, 9, 1, 0, 0, tzinfo=UTC),
            ),
            root=ROOT,
        )
        schedule["sampling"]["inclusion_probability"] = "1.0"
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            try:
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    opener=_Opener(),
                    producer_git_sha=GIT_SHA,
                    discovery_rows=[LIVE_ROW],
                )
                candidate = store.list_candidates(
                    schedule_sha256=schedule["schedule_sha256"],
                    activation_id=activation_id,
                )[0]
                self.assertNotEqual(candidate["state"], "NOT_SELECTED_PREDICATE")
                self.assertIn(
                    candidate["state"],
                    {"SAMPLED_MEMBER", "ADMITTED", "NOT_SELECTED_HASH_SAMPLE", "CANDIDATE"},
                )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
