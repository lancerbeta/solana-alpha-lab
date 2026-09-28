"""FORGE_TEMPORAL_OPERABILITY_REPAIR_V1 acceptance probes."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    GroundedDiscoveryError,
    format_discovery_readout,
)
from solana_alpha_lab.factory.hfic_repair_continuation import (  # noqa: E402
    ACTION_RESUME_REPAIR_CONTINUATION,
    REPAIR_CAPABILITY_ID,
    admission_with_repair_continuation,
    apply_repair_continuation,
    plan_repair_continuation,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
    _clock,
    classify_temporal_look,
    execute_temporal_discovery,
    validate_temporal_query,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402

PRICE = "FIELD-USD-PRICE-001"
LIQ = "FIELD-LIQUIDITY-USD-001"
COHORT = "REL-20260902T111900Z-20260909T111900Z"
RELEASE = "aa" * 32
ANCHOR = datetime(2026, 9, 3, tzinfo=UTC)
OFFSETS = {"X300": 300, "Y3600": 3600, "Y7200": 7200}
GIT_SHA = "ab" * 20


def _stamp(point: str, *, lateness: int = 0, extra: int = 0) -> str:
    moment = ANCHOR + timedelta(seconds=OFFSETS[point] + lateness + extra)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _binding_mixed() -> list[dict]:
    return [
        {
            "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
            "evidence_role": "EXPLORATORY_REUSE",
            "holdout": False,
            "cohort_id": COHORT,
            "release_id": RELEASE,
            "census_sha256": "bb" * 32,
            "observations_sha256": "cc" * 32,
            "schedule_lateness_seconds": 300,
            "schedule_point_lateness": {"X300": 300, "Y3600": 120, "Y7200": 240},
            "schedule_point_due_offset_seconds": {
                "X300": 300,
                "Y3600": 3600,
                "Y7200": 7200,
            },
            "window_start": "2026-09-02T11:19:00Z",
            "window_end": "2026-09-09T11:19:00Z",
        }
    ]


def _census(mint: str = "mint-a") -> dict:
    return {
        "mint": mint,
        "cohort_id": COHORT,
        "release_id": RELEASE,
        "candidate_state": "X_ELIGIBLE",
        "authoritative_anchor": "2026-09-03T00:00:00Z",
    }


def _obs(
    mint: str,
    point: str,
    field: str,
    value: float,
    *,
    available: str,
    request: str | None = None,
    response: str | None = None,
    event_time: str | None = None,
) -> dict:
    row = {
        "mint": mint,
        "cohort_id": COHORT,
        "release_id": RELEASE,
        "point_id": point,
        "field_id": field,
        "state": "OBSERVED",
        "first_reliable_available_at": available,
        "event_time": event_time or "2026-09-03T00:00:00Z",
        "typed_value": value,
        "source_price_event_time": "UNKNOWN",
    }
    if request is not None:
        row["request_started_at"] = request
    if response is not None:
        row["response_received_at"] = response
    return row


def _spec_snapshot(**overrides: object) -> dict:
    spec = {
        "schema": "smial.hfic-temporal-query",
        "schema_version": "1.0",
        "query_id": "operability_repair_probe",
        "population": "BASE_X",
        "search_tier": "SIMPLE_SCREEN",
        "budget_allocation": "AUTO",
        "decision": {"point_id": "Y3600", "time_policy": "BOUND_SCHEDULE_CUTOFF"},
        "schedule": {
            "lateness_seconds": 300,
            "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        },
        "features": [
            {"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"},
        ],
        "all": [{"feature": "mark", "op": "gte", "value": 0.0}],
        "target": {
            "kind": "PRICE_RELATIVE_PROXY",
            "reference_point": "Y3600",
            "exit_point": "Y7200",
            "field_id": PRICE,
        },
        "entry_model": {
            "kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT",
            "assumed_latency_seconds": 30,
        },
        "evaluation": {
            "calendar_block": "UTC_DAY_OF_DECISION",
            "baseline": "SAME_DECISION_ELIGIBLE",
            "ablations": "DROP_ONE_CONDITION",
        },
        "cost_profile": None,
    }
    spec.update(overrides)
    return spec


class MixedClockTests(unittest.TestCase):
    def test_mixed_point_lateness_passes_without_scalar_equality(self) -> None:
        item = _binding_mixed()[0]
        self.assertEqual(_clock(item, "X300", 300), (300, 300))
        self.assertEqual(_clock(item, "Y3600", 300), (3600, 120))
        self.assertEqual(_clock(item, "Y7200", 300), (7200, 240))

    def test_legacy_uniform_scalar_still_enforces_equality(self) -> None:
        item = {
            "schedule_lateness_seconds": 100,
        }
        with self.assertRaises(GroundedDiscoveryError) as exc:
            _clock(item, "X300", 300)
        self.assertEqual(exc.exception.code, "SCHEDULE_LATENESS_MISMATCH")

    def test_snapshot_policy_changes_identity_legacy_default_stable(self) -> None:
        legacy = _spec_snapshot()
        legacy["schedule"] = {"lateness_seconds": 300}
        digest_legacy = validate_temporal_query(legacy)["spec_sha256"]
        digest_default = validate_temporal_query(
            _spec_snapshot(
                schedule={
                    "lateness_seconds": 300,
                    "observation_clock_policy": "EVENT_TIME_V1",
                }
            )
        )["spec_sha256"]
        digest_snapshot = validate_temporal_query(_spec_snapshot())["spec_sha256"]
        self.assertEqual(digest_legacy, digest_default)
        self.assertNotEqual(digest_legacy, digest_snapshot)


class SnapshotTargetTests(unittest.TestCase):
    def _rows_legal(self, mint: str = "mint-a") -> list[dict]:
        # Decision Y3600 deadline = anchor + 3600 + 120 = +3720s
        # Entry = deadline + 30 = +3750s
        # Exit due = +7200; deadline = +7200+240 = +7440
        decision_available = _stamp("Y3600", lateness=120)
        exit_request = _stamp("Y7200", lateness=0, extra=60)  # after due and entry
        exit_response = _stamp("Y7200", lateness=0, extra=90)
        exit_available = _stamp("Y7200", lateness=0, extra=120)
        return [
            _obs(mint, "X300", LIQ, 1000.0, available=_stamp("X300", lateness=300)),
            _obs(mint, "Y3600", PRICE, 1.0, available=decision_available),
            _obs(
                mint,
                "Y7200",
                PRICE,
                1.5,
                available=exit_available,
                request=exit_request,
                response=exit_response,
                event_time="2026-09-03T00:00:00Z",  # anchor must not block snapshot
            ),
        ]

    def test_provider_snapshot_exit_observes_known_proxy(self) -> None:
        summary = execute_temporal_discovery(
            [_census()],
            self._rows_legal(),
            _spec_snapshot(),
            _binding_mixed(),
        )["summary"]
        self.assertEqual(summary["observation_clock_policy"], OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1)
        self.assertEqual(summary["observed_target_n"], 1)
        self.assertAlmostEqual(summary["mean_target"], 0.5)
        self.assertEqual(summary["source_price_event_time"], "UNKNOWN")
        readout = format_discovery_readout({"result": summary, "result_refs": []})
        self.assertEqual(readout["observation_clock_policy"], OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1)
        self.assertEqual(readout["target_exclusion_reasons"]["pooled"], {})

    def test_anchor_event_time_no_longer_kills_snapshot_exit(self) -> None:
        # Same rows; under EVENT_TIME_V1 the anchor event would fail after-entry.
        rows = self._rows_legal()
        legacy = _spec_snapshot(
            schedule={"lateness_seconds": 300, "observation_clock_policy": "EVENT_TIME_V1"}
        )
        legacy_summary = execute_temporal_discovery(
            [_census()], rows, legacy, _binding_mixed()
        )["summary"]
        self.assertEqual(legacy_summary["observed_target_n"], 0)
        self.assertIn(
            "EVENT_NOT_AFTER_ENTRY",
            legacy_summary["target_exclusion_reasons"]["pooled"],
        )

    def test_acquisition_before_point_due_is_excluded(self) -> None:
        rows = self._rows_legal()
        for row in rows:
            if row["point_id"] == "Y7200":
                row["request_started_at"] = _stamp("Y3600", lateness=0)  # before Y7200 due
                row["response_received_at"] = _stamp("Y7200", lateness=0, extra=90)
                row["first_reliable_available_at"] = _stamp("Y7200", lateness=0, extra=120)
        summary = execute_temporal_discovery(
            [_census()], rows, _spec_snapshot(), _binding_mixed()
        )["summary"]
        self.assertEqual(summary["observed_target_n"], 0)
        self.assertIn(
            "ACQUISITION_BEFORE_POINT_DUE",
            summary["target_exclusion_reasons"]["pooled"],
        )

    def test_request_not_after_entry_is_excluded(self) -> None:
        # Decision deadline Y3600+120=+3720; latency 4000 → entry=+7720 > exit due 7200.
        rows = self._rows_legal()
        for row in rows:
            if row["point_id"] == "Y7200":
                row["request_started_at"] = _stamp("Y7200", lateness=0, extra=10)
                row["response_received_at"] = _stamp("Y7200", lateness=0, extra=20)
                row["first_reliable_available_at"] = _stamp("Y7200", lateness=0, extra=30)
        spec = _spec_snapshot(
            entry_model={
                "kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT",
                "assumed_latency_seconds": 4000,
            }
        )
        summary = execute_temporal_discovery(
            [_census()], rows, spec, _binding_mixed()
        )["summary"]
        self.assertEqual(summary["observed_target_n"], 0)
        self.assertIn(
            "REQUEST_NOT_AFTER_ENTRY",
            summary["target_exclusion_reasons"]["pooled"],
        )


class RepairContinuationTests(unittest.TestCase):
    def _draft(self) -> dict:
        return {
            "parent_run_id": "FORGE-RUN-SYNTHETIC-001",
            "parent_session_id": "HFIC-SESS-SYNTHETIC-001",
            "scientific_slot_sha256": "11" * 32,
            "terminal_receipt_sha256": "22" * 32,
            "journal_scope": "synthetic-journal",
            "technical_gap_code": "PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
            "repair_capability_id": REPAIR_CAPABILITY_ID,
            "allowed_look_ids": ["look-a", "look-b"],
            "spent_main_looks": 2,
            "spent_adaptive_looks": 0,
            "spent_preview_looks": 0,
            "owner_authorization_id": "OWNER-AUTH-SYNTHETIC-001",
            "parent_terminal": "NO_WORTHY_HYPOTHESIS",
        }

    def test_plan_is_no_write_and_apply_is_idempotent(self) -> None:
        draft = self._draft()
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "selected_candidate_id": None,
        }
        plan = plan_repair_continuation(draft, parent_session=parent)
        self.assertEqual(plan["status"], "READY")
        self.assertFalse(plan["writes"])
        self.assertEqual(plan["owner_status"], "READY")
        self.assertEqual(plan["remaining_main_looks"], 4)
        self.assertEqual(
            plan["next_step"], "APPLY_WITH_EXPLICIT_CONFIRM_APPEND_ONLY"
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            first = apply_repair_continuation(
                store, draft, parent_session=parent, git_sha=GIT_SHA
            )
            self.assertTrue(first["applied"])
            second = apply_repair_continuation(
                store, draft, parent_session=parent, git_sha=GIT_SHA
            )
            self.assertFalse(second["applied"])
            self.assertTrue(second["idempotent"])

    def test_admission_overlay_resumes_completed_slot(self) -> None:
        draft = self._draft()
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            applied = apply_repair_continuation(
                store, draft, parent_session=parent, git_sha=GIT_SHA
            )
            disposition = applied["disposition"]
            overlay = admission_with_repair_continuation(
                {
                    "action": "RETURN_EXISTING_SESSION",
                    "reason_code": "NO_WORTHY_HYPOTHESIS",
                    "session_id": "HFIC-SESS-SYNTHETIC-001",
                    "scientific_slot_sha256": "11" * 32,
                    "occupancy": "OCCUPIED",
                },
                dispositions=[disposition],
                parent_terminal="NO_WORTHY_HYPOTHESIS",
            )
            self.assertEqual(overlay["action"], ACTION_RESUME_REPAIR_CONTINUATION)
            self.assertEqual(overlay["spent_main_looks"], 2)

    def test_spent_budget_counts_toward_shared_main_limit(self) -> None:
        previous = [
            {"look_class": "MAIN", "new_look": True, "spec_sha256": "a" * 64, "search_tier": "SIMPLE_SCREEN"},
            {"look_class": "MAIN", "new_look": True, "spec_sha256": "b" * 64, "search_tier": "SIMPLE_SCREEN"},
        ]
        third = classify_temporal_look(previous, _spec_snapshot())
        self.assertTrue(third["new_look"])
        self.assertEqual(third["main_count"], 3)
        exhausted_prev = [
            {
                "look_class": "MAIN",
                "new_look": True,
                "spec_sha256": f"{i:064x}",
                "search_tier": "COMPOUND_SCREEN",
            }
            for i in range(6)
        ]
        with self.assertRaises(GroundedDiscoveryError) as exc:
            classify_temporal_look(exhausted_prev, _spec_snapshot(query_id="other"))
        self.assertEqual(exc.exception.code, "QUERY_MAIN_BUDGET_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
