from __future__ import annotations

import copy
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_panel_coverage import (  # noqa: E402
    CoverageIndex,
    compute_evidence_role,
    schedule_covers,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    schedule_sha256,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (  # noqa: E402
    compile_observation_request,
    compile_schedule_document,
)


def _fixture(name: str) -> dict:
    return yaml.safe_load(
        (ROOT / "tests/fixtures/observation_schedule" / name).read_text(encoding="utf-8")
    )


class ObservationScheduleCompilerTests(unittest.TestCase):
    def test_common_panel_compiles_to_activation_required(self) -> None:
        result = compile_schedule_document(_fixture("common_panel.yaml"), root=ROOT)
        self.assertEqual(result.terminal, "SCHEDULE_ACTIVATION_REQUIRED")
        self.assertIsNotNone(result.schedule_sha256)
        self.assertEqual(result.budget.min_raw_retention_days, 10)
        self.assertLessEqual(result.budget.provider_calls_per_tick_max, 60)

    def test_two_schedule_keys_share_collection_hash(self) -> None:
        first = _fixture("common_panel.yaml")
        second = copy.deepcopy(first)
        second["schedule_key"] = "OBS-SECOND-HYPOTHESIS-SAME-COLLECTION-001"
        self.assertEqual(schedule_sha256(first), schedule_sha256(second))
        first_result = compile_schedule_document(first, root=ROOT)
        second_result = compile_schedule_document(second, root=ROOT)
        self.assertEqual(first_result.schedule_sha256, second_result.schedule_sha256)

    def test_yaml_only_successor_horizon_is_new_immutable_version(self) -> None:
        base = compile_schedule_document(_fixture("x300_y900.yaml"), root=ROOT)
        successor = compile_schedule_document(_fixture("successor_y259200.yaml"), root=ROOT)
        self.assertNotEqual(base.schedule_sha256, successor.schedule_sha256)
        self.assertEqual(successor.terminal, "SCHEDULE_ACTIVATION_REQUIRED")

    def test_covering_common_panel_reuses_narrower_request(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        requested = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        self.assertTrue(schedule_covers(requested, covering))
        index = CoverageIndex()
        index.add_snapshot(
            snapshot_sha256="b" * 64,
            schedule=covering,
            availability_cutoff=datetime(2026, 9, 1, tzinfo=UTC),
            first_y_available_at=datetime(2026, 8, 15, tzinfo=UTC),
        )
        spec = {
            "observation_request": {
                **requested,
                "collection_mode": "REUSE_OR_SCHEDULE",
                "requested_evidence_role": "EXPLORATORY_REUSE",
            },
            "availability_cutoff": "2026-09-01T12:00:00Z",
            "as_of": "2026-09-01T12:00:00Z",
        }
        result = compile_observation_request(spec, root=ROOT, coverage=index)
        self.assertEqual(result.terminal, "PANEL_REUSE_READY")
        self.assertEqual(result.snapshot_sha256, "b" * 64)
        self.assertEqual(result.covering_schedule_sha256, covering["schedule_sha256"])
        self.assertEqual(result.evidence_role, "EXPLORATORY_REUSE")

    def test_narrower_request_attaches_to_covering_active_schedule(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        requested = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        index = CoverageIndex()
        index.add_active_schedule(covering)
        attached = compile_observation_request(
            {
                "observation_request": {
                    **requested,
                    "collection_mode": "SCHEDULE_ONLY",
                    "requested_evidence_role": "PROSPECTIVE_OOS",
                },
                "availability_cutoff": requested["activation"]["starts_at"],
                "as_of": requested["activation"]["starts_at"],
            },
            root=ROOT,
            coverage=index,
        )
        self.assertEqual(attached.terminal, "ATTACHED_TO_ACTIVE_SCHEDULE")
        self.assertEqual(attached.covering_schedule_sha256, covering["schedule_sha256"])

    def test_active_identical_schedule_attaches(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        index = CoverageIndex()
        index.add_active_schedule(document)
        result = compile_schedule_document(document, root=ROOT)
        attached = compile_observation_request(
            {
                "observation_request": {
                    **document,
                    "collection_mode": "SCHEDULE_ONLY",
                    "requested_evidence_role": "PROSPECTIVE_OOS",
                },
                "availability_cutoff": document["activation"]["starts_at"],
                "as_of": document["activation"]["starts_at"],
            },
            root=ROOT,
            coverage=index,
        )
        self.assertEqual(result.terminal, "SCHEDULE_ACTIVATION_REQUIRED")
        self.assertEqual(attached.terminal, "ATTACHED_TO_ACTIVE_SCHEDULE")

    def test_successor_with_admission_overlap_requires_new_version(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        successor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
        )
        index = CoverageIndex()
        index.add_active_schedule(predecessor)
        result = compile_observation_request(
            {
                "observation_request": {
                    **successor,
                    "collection_mode": "SCHEDULE_ONLY",
                    "requested_evidence_role": "PROSPECTIVE_OOS",
                },
                "availability_cutoff": successor["activation"]["starts_at"],
                "as_of": successor["activation"]["starts_at"],
            },
            root=ROOT,
            coverage=index,
        )
        self.assertEqual(result.terminal, "NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED")
        self.assertEqual(result.covering_schedule_sha256, predecessor["schedule_sha256"])

    def test_unknown_primitive_is_change_lane(self) -> None:
        document = _fixture("common_panel.yaml")
        document["source_poll"]["primitive_id"] = "PRIM-UNKNOWN-ROUTE-001"
        result = compile_schedule_document(document, root=ROOT)
        self.assertEqual(result.terminal, "CHANGE_LANE_PRIMITIVE_GAP")

    def test_estimator_id_is_change_lane(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        result = compile_observation_request(
            {
                "observation_request": {
                    **document,
                    "collection_mode": "SCHEDULE_ONLY",
                    "requested_evidence_role": "PROSPECTIVE_OOS",
                    "estimator_id": "EST-NOT-RUNTIME-001",
                },
                "availability_cutoff": document["activation"]["starts_at"],
                "as_of": document["activation"]["starts_at"],
            },
            root=ROOT,
        )
        self.assertEqual(result.terminal, "CHANGE_LANE_ESTIMATOR_GAP")

    def test_y_field_in_population_is_outcome_leakage(self) -> None:
        document = _fixture("common_panel.yaml")
        document["population"]["source_predicates"].append(
            {
                "field_id": "FIELD-QUOTE-SELL-OUT-AMOUNT-001",
                "operator": "GTE",
                "value_decimal": "1",
            }
        )
        result = compile_schedule_document(document, root=ROOT)
        self.assertEqual(result.terminal, "DENY_OUTCOME_LEAKAGE")

    def test_url_in_request_is_unsafe(self) -> None:
        document = _fixture("common_panel.yaml")
        document["population"]["source_predicates"][0]["value_text"] = "https://evil.example"
        result = compile_schedule_document(document, root=ROOT)
        self.assertEqual(result.terminal, "DENY_UNSAFE_RUNTIME_CODE")

    def test_understated_tick_budget_is_blocked(self) -> None:
        document = _fixture("common_panel.yaml")
        document["budgets"]["provider_calls_per_tick_max"] = 1
        result = compile_schedule_document(document, root=ROOT)
        self.assertEqual(result.terminal, "BLOCKED_BUDGET")

    def test_unknown_authority_is_blocked(self) -> None:
        document = _fixture("common_panel.yaml")
        document["authority"]["profile_id"] = "AUTH-UNKNOWN-001"
        result = compile_schedule_document(document, root=ROOT)
        self.assertEqual(result.terminal, "BLOCKED_AUTHORITY")

    def test_evidence_roles(self) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        y_ready = datetime(2026, 9, 2, tzinfo=UTC)
        self.assertEqual(
            compute_evidence_role(
                hypothesis_registered_at=datetime(2026, 8, 1, tzinfo=UTC),
                first_admission_at=start,
                first_y_available_at=None,
                closed_or_consumed=False,
            ),
            "PROSPECTIVE_OOS",
        )
        self.assertEqual(
            compute_evidence_role(
                hypothesis_registered_at=datetime(2026, 8, 1, tzinfo=UTC),
                first_admission_at=start,
                first_y_available_at=y_ready,
                closed_or_consumed=False,
                y_availability_proven=False,
            ),
            "EXPLORATORY_REUSE",
        )
        self.assertEqual(
            compute_evidence_role(
                hypothesis_registered_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
                first_admission_at=start,
                first_y_available_at=None,
                closed_or_consumed=False,
            ),
            "PROSPECTIVE_OUTCOME_BLIND_CONDITIONAL",
        )
        self.assertEqual(
            compute_evidence_role(
                hypothesis_registered_at=datetime(2026, 9, 3, tzinfo=UTC),
                first_admission_at=start,
                first_y_available_at=y_ready,
                closed_or_consumed=False,
            ),
            "EXPLORATORY_REUSE",
        )
        self.assertEqual(
            compute_evidence_role(
                hypothesis_registered_at=start,
                first_admission_at=start,
                first_y_available_at=None,
                closed_or_consumed=True,
            ),
            "CONSUMED_PRIOR_EVIDENCE",
        )

    def test_hundred_members_fit_one_search_batch(self) -> None:
        from solana_alpha_lab.factory.observation_primitive_registry import (
            load_observation_primitive_registry,
        )
        from solana_alpha_lab.factory.observation_schedule_compiler import _compute_budget

        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        mutated = dict(schedule)
        mutated["sampling"] = dict(schedule["sampling"])
        mutated["sampling"]["max_members_per_utc_day"] = 100
        envelope = _compute_budget(mutated, load_observation_primitive_registry(ROOT))
        self.assertEqual(envelope.batch_snapshot_calls, 1)


if __name__ == "__main__":
    unittest.main()
