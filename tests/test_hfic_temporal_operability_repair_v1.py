"""FORGE_TEMPORAL_OPERABILITY_REPAIR_V1 acceptance probes."""

from __future__ import annotations

import json
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
    build_repair_continuation_draft,
    close_repair_continuation,
    disposition_identity,
    enrich_parent_for_repair_draft,
    list_repair_continuation_dispositions,
    plan_repair_continuation,
    validate_disposition_draft,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
    TEMPORAL_CALCULATION_VERSION,
    TEMPORAL_CALCULATION_VERSION_V2,
    _clock,
    _public_query_from_recipe,
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
    bind_snapshot: bool = False,
    source_price_event_time: str | None = "UNKNOWN",
    primitive_id: str | None = None,
    call_occurrence_id: str | None = None,
    request_sha256: str | None = None,
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
        "source_price_event_time": source_price_event_time,
    }
    if request is not None:
        row["request_started_at"] = request
    if response is not None:
        row["response_received_at"] = response
    if bind_snapshot or (request is not None and point.startswith("Y")):
        row["primitive_id"] = primitive_id or "PRIM-JUPITER-PRICE-V3-001"
        row["call_occurrence_id"] = call_occurrence_id or f"occ-{mint}-{point}"
        row["request_sha256"] = request_sha256 or ("dd" * 32)
        row["observation_clock_policy"] = OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1
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

    def test_apply_owner_readout_is_done_not_ready(self) -> None:
        draft = self._draft()
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "selected_candidate_id": None,
            "scientific_slot_sha256": "11" * 32,
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            applied = apply_repair_continuation(
                store, draft, parent_session=parent, git_sha=GIT_SHA
            )
            self.assertEqual(applied["status"], "APPLIED")
            self.assertEqual(applied["owner_status"], "DONE")
            self.assertEqual(applied["owner_readout"]["status"], "DONE")
            self.assertTrue(applied["owner_readout"]["writes"])

    def test_draft_builder_requires_no_worthy_fields(self) -> None:
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "scientific_slot_sha256": "11" * 32,
            "run_id": "FORGE-RUN-SYNTHETIC",
            "critic_result_sha256": "22" * 32,
            "search_key_sha256": "33" * 32,
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
        }
        draft = build_repair_continuation_draft(
            parent,
            owner_authorization_id="OWNER-AUTH-SYNTHETIC-001",
            technical_gap_code="PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
            spent_main_looks=2,
            spent_adaptive_looks=0,
            spent_preview_looks=0,
        )
        self.assertEqual(draft["parent_terminal"], "NO_WORTHY_HYPOTHESIS")
        self.assertEqual(draft["spent_main_looks"], 2)
        plan = plan_repair_continuation(draft, parent_session=parent)
        self.assertEqual(plan["status"], "READY")

    def test_enrich_parent_fills_receipt_and_spent_from_show_fields(self) -> None:
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "scientific_slot_sha256": "11" * 32,
            "session_receipt_sha256": "22" * 32,
            "terminal_receipt_sha256": "22" * 32,
            "search_key_sha256": "33" * 32,
            "journal_scope": "33" * 32,
            "run_id": "FORGE-RUN-SYNTHETIC",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "spent_main_looks": 3,
            "spent_adaptive_looks": 1,
            "spent_preview_looks": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            enriched = enrich_parent_for_repair_draft(store, parent)
            draft = build_repair_continuation_draft(
                enriched,
                owner_authorization_id="OWNER-AUTH-SYNTHETIC-001",
                technical_gap_code="PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
            )
        self.assertEqual(draft["terminal_receipt_sha256"], "22" * 32)
        self.assertEqual(draft["spent_main_looks"], 3)
        self.assertEqual(draft["parent_run_id"], "FORGE-RUN-SYNTHETIC")

    def test_completed_without_no_worthy_is_blocked(self) -> None:
        draft = self._draft()
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "critic_terminal": "WORTHY_CANDIDATE",
            "selected_candidate_id": None,
        }
        plan = plan_repair_continuation(draft, parent_session=parent)
        self.assertEqual(plan["status"], "NOT_APPLICABLE")
        self.assertEqual(plan["reason_code"], "PARENT_NOT_COMPLETED_NO_WORTHY")

    def test_recipe_replay_preserves_snapshot_policy(self) -> None:
        validated = validate_temporal_query(_spec_snapshot())
        body = validated["scientific_body"]
        recipe = {
            "capability_id": "CAP-HFIC-TEMPORAL-DISCOVERY-001",
            "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
            "spec": {
                "query_id": validated["query_id"],
                "search_tier": validated["search_tier"],
                "budget_allocation": validated["budget_allocation"],
                "scientific_body": body,
            },
        }
        public = _public_query_from_recipe(recipe)
        self.assertEqual(
            public["schedule"]["observation_clock_policy"],
            OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        )


class BinderMixedLatenessTests(unittest.TestCase):
    def test_attach_verified_schedule_allows_mixed_non_x300(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            _attach_verified_schedule,
        )
        from unittest.mock import patch

        cohorts = [
            {
                "census_rel": "datasets/fake/census.parquet",
                "schedule_lateness_seconds": 300,
            }
        ]
        projected = {
            "schedule_point_lateness": {"X300": 300, "Y3600": 120, "Y7200": 240},
            "schedule_point_due_offset_seconds": {
                "X300": 300,
                "Y3600": 3600,
                "Y7200": 7200,
            },
        }
        with patch(
            "solana_alpha_lab.factory.hfic_grounded_discovery.schedule_projection_for_census",
            return_value=projected,
        ):
            _attach_verified_schedule(Path("."), cohorts)
        self.assertNotEqual(
            cohorts[0].get("schedule_context_gap"), "SCHEDULE_LATENESS_MISMATCH"
        )
        self.assertEqual(cohorts[0]["schedule_point_lateness"]["Y3600"], 120)

    def test_attach_verified_schedule_rejects_x300_drift(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            _attach_verified_schedule,
        )
        from unittest.mock import patch

        cohorts = [
            {
                "census_rel": "datasets/fake/census.parquet",
                "schedule_lateness_seconds": 300,
            }
        ]
        projected = {
            "schedule_point_lateness": {"X300": 120, "Y3600": 120},
            "schedule_point_due_offset_seconds": {"X300": 300, "Y3600": 3600},
        }
        with patch(
            "solana_alpha_lab.factory.hfic_grounded_discovery.schedule_projection_for_census",
            return_value=projected,
        ):
            _attach_verified_schedule(Path("."), cohorts)
        self.assertEqual(
            cohorts[0].get("schedule_context_gap"), "SCHEDULE_LATENESS_MISMATCH"
        )


class SnapshotNegativeControlsTests(unittest.TestCase):
    def _rows_legal(self) -> list[dict]:
        decision_available = _stamp("Y3600", lateness=120)
        exit_request = _stamp("Y7200", lateness=0, extra=60)
        exit_response = _stamp("Y7200", lateness=0, extra=90)
        exit_available = _stamp("Y7200", lateness=0, extra=120)
        return [
            _obs("mint-a", "X300", LIQ, 1000.0, available=_stamp("X300", lateness=300)),
            _obs("mint-a", "Y3600", PRICE, 1.0, available=decision_available),
            _obs(
                "mint-a",
                "Y7200",
                PRICE,
                1.5,
                available=exit_available,
                request=exit_request,
                response=exit_response,
                bind_snapshot=True,
            ),
        ]

    def test_malformed_source_event_excludes(self) -> None:
        rows = self._rows_legal()
        for row in rows:
            if row["point_id"] == "Y7200":
                row["source_price_event_time"] = "invalid"
        summary = execute_temporal_discovery(
            [_census()], rows, _spec_snapshot(), _binding_mixed()
        )["summary"]
        self.assertEqual(summary["observed_target_n"], 0)
        self.assertIn(
            "SOURCE_PRICE_EVENT_MALFORMED",
            summary["target_exclusion_reasons"]["pooled"],
        )

    def test_unbound_occurrence_excludes(self) -> None:
        rows = self._rows_legal()
        for row in rows:
            if row["point_id"] == "Y7200":
                row["primitive_id"] = "UNREGISTERED-PRIMITIVE"
                row["call_occurrence_id"] = None
                row["request_sha256"] = None
        summary = execute_temporal_discovery(
            [_census()], rows, _spec_snapshot(), _binding_mixed()
        )["summary"]
        self.assertEqual(summary["observed_target_n"], 0)
        self.assertIn(
            "SNAPSHOT_OCCURRENCE_UNBOUND",
            summary["target_exclusion_reasons"]["pooled"],
        )

    def test_known_source_event_propagates_to_summary(self) -> None:
        rows = self._rows_legal()
        known = _stamp("Y7200", lateness=0, extra=80)
        for row in rows:
            if row["point_id"] == "Y7200":
                row["source_price_event_time"] = known
        summary = execute_temporal_discovery(
            [_census()], rows, _spec_snapshot(), _binding_mixed()
        )["summary"]
        self.assertEqual(summary["observed_target_n"], 1)
        self.assertEqual(summary["source_price_event_time"], known)

    def test_new_runs_emit_calc_v3(self) -> None:
        summary = execute_temporal_discovery(
            [_census()], self._rows_legal(), _spec_snapshot(), _binding_mixed()
        )["summary"]
        self.assertEqual(summary["calculation_version"], TEMPORAL_CALCULATION_VERSION)
        self.assertNotEqual(summary["calculation_version"], TEMPORAL_CALCULATION_VERSION_V2)

    def test_event_time_keeps_decision_deadline_reference_parity(self) -> None:
        # Uniform schedule; reference late vs own point but available before decision.
        # EVENT_TIME must keep decision-deadline cutoff (V1/V2 parity).
        anchor = ANCHOR
        offsets = {"Y7200": 7200, "Y3600": 3600, "Y14400": 14400}
        census = {
            "mint": "mint-u",
            "cohort_id": COHORT,
            "release_id": RELEASE,
            "candidate_state": "X_ELIGIBLE",
            "authoritative_anchor": anchor.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        binding = [
            {
                "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
                "evidence_role": "EXPLORATORY_REUSE",
                "holdout": False,
                "cohort_id": COHORT,
                "release_id": RELEASE,
                "census_sha256": "bb" * 32,
                "observations_sha256": "cc" * 32,
                "schedule_lateness_seconds": 300,
                "schedule_point_lateness": {
                    "X300": 300,
                    "Y7200": 300,
                    "Y3600": 300,
                    "Y14400": 300,
                },
                "schedule_point_due_offset_seconds": {
                    "X300": 300,
                    "Y7200": 7200,
                    "Y3600": 3600,
                    "Y14400": 14400,
                },
                "window_start": "2026-09-02T11:19:00Z",
                "window_end": "2026-09-09T11:19:00Z",
            }
        ]

        def avail(point: str, extra: int) -> str:
            return (anchor + timedelta(seconds=offsets[point] + extra)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        rows = [
            {
                "mint": "mint-u",
                "cohort_id": COHORT,
                "release_id": RELEASE,
                "point_id": "X300",
                "field_id": LIQ,
                "state": "OBSERVED",
                "typed_value": 1000.0,
                "first_reliable_available_at": (
                    anchor + timedelta(seconds=600)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event_time": "2026-09-03T00:00:00Z",
                "source_price_event_time": "UNKNOWN",
            },
            {
                "mint": "mint-u",
                "cohort_id": COHORT,
                "release_id": RELEASE,
                "point_id": "Y3600",
                "field_id": PRICE,
                "state": "OBSERVED",
                "typed_value": 1.0,
                "first_reliable_available_at": avail("Y3600", 600),  # after own deadline
                "event_time": avail("Y3600", 0),
                "source_price_event_time": "UNKNOWN",
            },
            {
                "mint": "mint-u",
                "cohort_id": COHORT,
                "release_id": RELEASE,
                "point_id": "Y7200",
                "field_id": PRICE,
                "state": "OBSERVED",
                "typed_value": 2.0,
                "first_reliable_available_at": avail("Y7200", 100),
                "event_time": avail("Y7200", 100),
                "source_price_event_time": "UNKNOWN",
            },
            {
                "mint": "mint-u",
                "cohort_id": COHORT,
                "release_id": RELEASE,
                "point_id": "Y14400",
                "field_id": PRICE,
                "state": "OBSERVED",
                "typed_value": 3.0,
                "first_reliable_available_at": avail("Y14400", 100),
                "event_time": avail("Y14400", 0),
                "source_price_event_time": "UNKNOWN",
            },
        ]
        spec = {
            "schema": "smial.hfic-temporal-query",
            "schema_version": "1.0",
            "query_id": "event_time_parity",
            "population": "BASE_X",
            "search_tier": "SIMPLE_SCREEN",
            "budget_allocation": "AUTO",
            "decision": {"point_id": "Y7200", "time_policy": "BOUND_SCHEDULE_CUTOFF"},
            "schedule": {"lateness_seconds": 300},
            "features": [
                {"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y7200"},
            ],
            "all": [{"feature": "mark", "op": "gte", "value": 0.0}],
            "target": {
                "kind": "PRICE_RELATIVE_PROXY",
                "reference_point": "Y3600",
                "exit_point": "Y14400",
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
        summary = execute_temporal_discovery([census], rows, spec, binding)["summary"]
        # Reference available at +4200; decision deadline +7500. EVENT_TIME uses
        # decision cutoff so reference is observed → mean 2.0.
        self.assertEqual(summary["observed_target_n"], 1)
        self.assertAlmostEqual(summary["mean_target"], 2.0)
        self.assertEqual(summary["calculation_version"], TEMPORAL_CALCULATION_VERSION)


class RepairLifecycleP1Tests(unittest.TestCase):
    def _draft(self, **overrides: object) -> dict:
        draft = {
            "parent_run_id": "FORGE-RUN-SYNTHETIC-001",
            "parent_session_id": "HFIC-SESS-SYNTHETIC-001",
            "scientific_slot_sha256": "11" * 32,
            "terminal_receipt_sha256": "22" * 32,
            "journal_scope": "aa" * 32,
            "technical_gap_code": "PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
            "repair_capability_id": REPAIR_CAPABILITY_ID,
            "allowed_look_ids": ["look-a", "look-b"],
            "spent_main_looks": 2,
            "spent_adaptive_looks": 0,
            "spent_preview_looks": 0,
            "owner_authorization_id": "OWNER-AUTH-SYNTHETIC-001",
            "parent_terminal": "NO_WORTHY_HYPOTHESIS",
            "evidence_mapping": {"clock_policy": "PROVIDER_REPORTED_SNAPSHOT_V1"},
        }
        draft.update(overrides)
        return draft

    def test_evidence_mapping_changes_disposition_digest(self) -> None:
        a = validate_disposition_draft(self._draft())
        b = validate_disposition_draft(
            self._draft(evidence_mapping={"clock_policy": "OTHER"})
        )
        self.assertNotEqual(a["disposition_sha256"], b["disposition_sha256"])
        self.assertEqual(
            a["disposition_sha256"],
            disposition_identity(a),
        )

    def test_synthesis_complete_overlay_with_no_worthy_disposition(self) -> None:
        draft = self._draft()
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "session_state": "SYNTHESIS_COMPLETE",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "selected_candidate_id": None,
        }
        plan = plan_repair_continuation(draft, parent_session=parent)
        self.assertEqual(plan["status"], "READY")
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            applied = apply_repair_continuation(
                store, draft, parent_session=parent, git_sha=GIT_SHA
            )
            overlay = admission_with_repair_continuation(
                {
                    "action": "RETURN_EXISTING_SESSION",
                    "reason_code": "SYNTHESIS_COMPLETE",
                    "session_id": "HFIC-SESS-SYNTHETIC-001",
                    "scientific_slot_sha256": "11" * 32,
                    "occupancy": "OCCUPIED",
                },
                dispositions=[applied["disposition"]],
                parent_terminal="SYNTHESIS_COMPLETE",
            )
            self.assertEqual(overlay["action"], ACTION_RESUME_REPAIR_CONTINUATION)

    def test_close_blocks_reuse(self) -> None:
        draft = self._draft()
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "selected_candidate_id": None,
            "scientific_slot_sha256": "11" * 32,
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            applied = apply_repair_continuation(
                store, draft, parent_session=parent, git_sha=GIT_SHA
            )
            digest = applied["disposition"]["disposition_sha256"]
            closed = close_repair_continuation(
                store, digest, git_sha=GIT_SHA, reason_code="CONTINUATION_TERMINAL_REACHED"
            )
            self.assertEqual(closed["status"], "CLOSED")
            # Store round-trip: CLOSED must dominate AUTHORIZED regardless of
            # ResearchStore iteration order.
            listed = list_repair_continuation_dispositions(store)
            listed_one = next(
                item for item in listed if item.get("disposition_sha256") == digest
            )
            self.assertEqual(listed_one.get("status"), "CLOSED")
            replay = plan_repair_continuation(
                draft,
                parent_session=parent,
                existing_dispositions=listed,
                store=store,
            )
            self.assertEqual(replay["status"], "NOT_APPLICABLE")
            self.assertEqual(replay["reason_code"], "DISPOSITION_ALREADY_CLOSED")
            overlay = admission_with_repair_continuation(
                {
                    "action": "RETURN_EXISTING_SESSION",
                    "reason_code": "SYNTHESIS_COMPLETE",
                    "session_id": "HFIC-SESS-SYNTHETIC-001",
                    "scientific_slot_sha256": "11" * 32,
                    "occupancy": "OCCUPIED",
                },
                dispositions=listed,
                parent_terminal="SYNTHESIS_COMPLETE",
            )
            self.assertNotEqual(overlay["action"], ACTION_RESUME_REPAIR_CONTINUATION)

    def test_empty_critic_synthesis_complete_is_blocked(self) -> None:
        draft = self._draft()
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "session_state": "SYNTHESIS_COMPLETE",
            "selected_candidate_id": None,
        }
        plan = plan_repair_continuation(draft, parent_session=parent)
        self.assertEqual(plan["status"], "NOT_APPLICABLE")
        self.assertEqual(plan["reason_code"], "PARENT_NOT_COMPLETED_NO_WORTHY")

    def test_journal_spent_rejects_caller_zero(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import _append_discovery_look

        draft = self._draft(spent_main_looks=0)
        parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "selected_candidate_id": None,
            "scientific_slot_sha256": "11" * 32,
        }
        scope = "aa" * 32
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            clock = datetime(2026, 9, 28, tzinfo=UTC)
            for i in range(2):
                _append_discovery_look(
                    store,
                    record_id=f"HFIC-ART-DISCOVERY-SYNTH{i:02d}-" + ("0" * 20),
                    journal_scope=scope,
                    spec={"query_id": f"q{i}"},
                    spec_sha256=f"{i:064x}",
                    binding_sha="bb" * 32,
                    data_refs=[],
                    digest=f"{i+10:064x}",
                    identity=f"{i+1:02x}" + ("a" * 62),
                    summary={"calculation_version": TEMPORAL_CALCULATION_VERSION},
                    look={
                        "look_class": "MAIN",
                        "new_look": True,
                        "search_tier": "SIMPLE_SCREEN",
                        "main_count": i + 1,
                        "adaptive_count": 0,
                        "simple_main_count": i + 1,
                        "compound_main_count": 0,
                    },
                    git_sha=GIT_SHA,
                    clock=clock,
                    candidate_scope={"schema": "test"},
                )
            plan = plan_repair_continuation(
                draft, parent_session=parent, store=store
            )
            self.assertEqual(plan["status"], "NOT_APPLICABLE")
            self.assertEqual(plan["reason_code"], "SPENT_BUDGET_MISMATCH")
            ok = plan_repair_continuation(
                self._draft(spent_main_looks=2),
                parent_session=parent,
                store=store,
            )
            self.assertEqual(ok["status"], "READY")
            self.assertEqual(ok["remaining_main_looks"], 4)


class AcceptanceVerticalADataPathTests(unittest.TestCase):
    """P1-2/P1-3: producer clocks → binding → snapshot query → policy identity."""

    def test_parquet_schema_carries_clock_and_occurrence_fields(self) -> None:
        from solana_alpha_lab.factory.live_cohort_source_bundle import (
            OBSERVATION_COLUMNS,
            OBS_RELEASE_SCHEMA,
            row_for_observation_parquet,
        )

        for name in (
            "observation_clock_policy",
            "source_price_event_time",
            "call_occurrence_id",
            "request_sha256",
            "member_anchor",
        ):
            self.assertIn(name, OBSERVATION_COLUMNS)
            self.assertIn(name, {field.name for field in OBS_RELEASE_SCHEMA})
        packed = row_for_observation_parquet(
            {
                "mint": "m",
                "point_id": "Y7200",
                "primitive_id": "PRIM-JUPITER-PRICE-V3-001",
                "field_id": PRICE,
                "state": "OBSERVED",
                "typed_value": 1.5,
                "request_started_at": "2026-09-03T02:01:00Z",
                "response_received_at": "2026-09-03T02:01:30Z",
                "first_reliable_available_at": "2026-09-03T02:02:00Z",
                "request_sha256": "dd" * 32,
                "call_occurrence_id": "occ-1",
                "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
                "source_price_event_time": "UNKNOWN",
                "member_anchor": "2026-09-03T00:00:00Z",
            }
        )
        self.assertEqual(
            packed["observation_clock_policy"],
            OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        )
        self.assertEqual(packed["call_occurrence_id"], "occ-1")

    def test_release_row_preserves_clock_fields(self) -> None:
        from solana_alpha_lab.factory.live_cohort_discovery_release import (
            _observation_release_row,
        )

        row = _observation_release_row(
            {
                "mint": "m",
                "point_id": "Y7200",
                "primitive_id": "PRIM-JUPITER-PRICE-V3-001",
                "field_id": PRICE,
                "state": "OBSERVED",
                "typed_value": 1.5,
                "request_sha256": "dd" * 32,
                "call_occurrence_id": "occ-1",
                "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
                "source_price_event_time": "2026-09-03T02:01:20Z",
                "member_anchor": "2026-09-03T00:00:00Z",
            },
            cohort_id=COHORT,
            release_id=RELEASE,
        )
        self.assertEqual(
            row["observation_clock_policy"],
            OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        )
        self.assertEqual(row["source_price_event_time"], "2026-09-03T02:01:20Z")
        self.assertEqual(row["call_occurrence_id"], "occ-1")

    def test_mixed_clock_snapshot_end_to_end_with_negatives(self) -> None:
        good = SnapshotNegativeControlsTests()._rows_legal()
        good_summary = execute_temporal_discovery(
            [_census()], good, _spec_snapshot(), _binding_mixed()
        )["summary"]
        self.assertEqual(good_summary["observed_target_n"], 1)
        self.assertAlmostEqual(good_summary["mean_target"], 0.5)
        self.assertEqual(
            good_summary["observation_clock_policy"],
            OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        )
        self.assertEqual(good_summary["calculation_version"], TEMPORAL_CALCULATION_VERSION)
        validated = validate_temporal_query(_spec_snapshot())
        self.assertEqual(
            validated["scientific_body"]["observation_clock_policy"],
            OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        )
        # All-missing slice: strip exit → EXIT_ABSENT / TARGET_UNOBSERVED family.
        missing = [row for row in good if row["point_id"] != "Y7200"]
        missing_summary = execute_temporal_discovery(
            [_census()], missing, _spec_snapshot(), _binding_mixed()
        )["summary"]
        self.assertEqual(missing_summary["observed_target_n"], 0)
        pooled = missing_summary["target_exclusion_reasons"]["pooled"]
        self.assertTrue(pooled)


class AcceptanceVerticalBContinuationTests(unittest.TestCase):
    """P1-4/P1-5: completed parent → plan/apply → resume → close → no reopen."""

    def test_completed_parent_through_close(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import _append_discovery_look

        slot = "11" * 32
        scope = "aa" * 32
        session_id = "HFIC-SESS-SYNTHETIC-001"
        draft = {
            "parent_run_id": "FORGE-RUN-SYNTHETIC-001",
            "parent_session_id": session_id,
            "scientific_slot_sha256": slot,
            "terminal_receipt_sha256": "22" * 32,
            "journal_scope": scope,
            "technical_gap_code": "PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
            "repair_capability_id": REPAIR_CAPABILITY_ID,
            "allowed_look_ids": [],
            "spent_main_looks": 2,
            "spent_adaptive_looks": 0,
            "spent_preview_looks": 0,
            "owner_authorization_id": "OWNER-AUTH-SYNTHETIC-001",
            "parent_terminal": "NO_WORTHY_HYPOTHESIS",
            "evidence_mapping": {"repair": "snapshot_clocks"},
        }
        parent = {
            "session_id": session_id,
            "session_state": "SYNTHESIS_COMPLETE",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "selected_candidate_id": None,
            "scientific_slot_sha256": slot,
            "terminal_receipt_sha256": "22" * 32,
            "journal_scope": scope,
            "search_key_sha256": scope,
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            clock = datetime(2026, 9, 28, tzinfo=UTC)
            for i in range(2):
                _append_discovery_look(
                    store,
                    record_id=f"HFIC-ART-DISCOVERY-VERT{i:02d}-" + ("1" * 20),
                    journal_scope=scope,
                    spec={"query_id": f"prior-{i}"},
                    spec_sha256=f"{i+1:064x}",
                    binding_sha="bb" * 32,
                    data_refs=[],
                    digest=f"{i+30:064x}",
                    identity=f"{i+3:02x}" + ("b" * 62),
                    summary={"calculation_version": TEMPORAL_CALCULATION_VERSION},
                    look={
                        "look_class": "MAIN",
                        "new_look": True,
                        "search_tier": "SIMPLE_SCREEN",
                        "main_count": i + 1,
                        "adaptive_count": 0,
                        "simple_main_count": i + 1,
                        "compound_main_count": 0,
                    },
                    git_sha=GIT_SHA,
                    clock=clock,
                    candidate_scope={"schema": "test"},
                )
            bare = admission_with_repair_continuation(
                {
                    "action": "RETURN_EXISTING_SESSION",
                    "reason_code": "SYNTHESIS_COMPLETE",
                    "session_id": session_id,
                    "scientific_slot_sha256": slot,
                    "occupancy": "OCCUPIED",
                },
                dispositions=[],
                parent_terminal="SYNTHESIS_COMPLETE",
            )
            self.assertEqual(bare["action"], "RETURN_EXISTING_SESSION")
            plan = plan_repair_continuation(
                draft, parent_session=parent, store=store
            )
            self.assertEqual(plan["status"], "READY")
            self.assertEqual(plan["remaining_main_looks"], 4)
            applied = apply_repair_continuation(
                store, draft, parent_session=parent, git_sha=GIT_SHA
            )
            self.assertTrue(applied["applied"])
            resumed = admission_with_repair_continuation(
                {
                    "action": "RETURN_EXISTING_SESSION",
                    "reason_code": "SYNTHESIS_COMPLETE",
                    "session_id": session_id,
                    "scientific_slot_sha256": slot,
                    "occupancy": "OCCUPIED",
                },
                dispositions=[applied["disposition"]],
                parent_terminal="SYNTHESIS_COMPLETE",
            )
            self.assertEqual(resumed["action"], ACTION_RESUME_REPAIR_CONTINUATION)
            self.assertEqual(resumed["spent_main_looks"], 2)
            third = classify_temporal_look(
                [
                    {
                        "look_class": "MAIN",
                        "new_look": True,
                        "spec_sha256": f"{i:064x}",
                        "search_tier": "SIMPLE_SCREEN",
                    }
                    for i in range(2)
                ],
                _spec_snapshot(query_id="continuation-main-3"),
            )
            self.assertTrue(third["new_look"])
            self.assertEqual(third["main_count"], 3)
            closed = close_repair_continuation(
                store,
                applied["disposition"]["disposition_sha256"],
                git_sha=GIT_SHA,
            )
            self.assertEqual(closed["status"], "CLOSED")
            listed = list_repair_continuation_dispositions(store)
            after = admission_with_repair_continuation(
                {
                    "action": "RETURN_EXISTING_SESSION",
                    "reason_code": "SYNTHESIS_COMPLETE",
                    "session_id": session_id,
                    "scientific_slot_sha256": slot,
                    "occupancy": "OCCUPIED",
                },
                dispositions=listed,
                parent_terminal="SYNTHESIS_COMPLETE",
            )
            self.assertEqual(after["action"], "RETURN_EXISTING_SESSION")
            blocked = plan_repair_continuation(
                draft,
                parent_session=parent,
                existing_dispositions=listed,
                store=store,
            )
            self.assertEqual(blocked["reason_code"], "DISPOSITION_ALREADY_CLOSED")

    def test_list_sessions_projects_critic_terminal_into_admission(self) -> None:
        """Production occupancy rows must carry critic_terminal for overlay."""

        from datetime import timezone

        from solana_alpha_lab.factory.hfic_session import list_hfic_sessions
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

        session_id = "HFIC-SESS-LIST-PROJ-001"
        moment = datetime(2026, 9, 28, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            cycle_payload = {
                "research_cycle_id": f"{session_id}-NO-WORTHY",
                "session_id": session_id,
                "phase": "SYNTHESIS_COMPLETE",
                "hfic_protocol": "HFIC-V1.2",
                "prompt_version": "HFIC-V1.2",
                "owner_focus": "AUTO",
                "evidence_epoch_sha256": "ab" * 32,
                "focus_key_sha256": "22" * 32,
                "search_key_sha256": "aa" * 32,
                "selected_candidate_id": None,
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "scientific_slot_sha256": "11" * 32,
            }
            body = json.dumps(cycle_payload, sort_keys=True, separators=(",", ":"))
            receipt_body = json.dumps(
                {
                    "artifact_kind": "SESSION_RECEIPT",
                    "session_id": session_id,
                    "session_state": "SYNTHESIS_COMPLETE",
                    "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            txn = f"RESEARCH-TXN-LIST-PROJ-{session_id[-8:].upper()}"
            store.append(
                [
                    ResearchEvent(
                        record_id=f"HFIC-CYCLE-{session_id}-NO-WORTHY",
                        record_kind=RecordKind.RESEARCH_CYCLE,
                        entity_id=session_id,
                        hypothesis_version_id=None,
                        run_id=None,
                        transaction_id=txn,
                        effective_at=moment,
                        first_reliable_available_at=moment,
                        supersedes_record_id=None,
                        payload_json=body,
                        payload_sha256=__import__("hashlib")
                        .sha256(body.encode("utf-8"))
                        .hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-TEST",
                        producer_git_sha=GIT_SHA,
                        created_at=moment,
                    ),
                    ResearchEvent(
                        record_id=f"HFIC-ART-RECEIPT-{session_id}",
                        record_kind=RecordKind.RESEARCH_ARTIFACT,
                        entity_id=session_id,
                        hypothesis_version_id=None,
                        run_id=None,
                        transaction_id=txn,
                        effective_at=moment,
                        first_reliable_available_at=moment,
                        supersedes_record_id=None,
                        payload_json=receipt_body,
                        payload_sha256=__import__("hashlib")
                        .sha256(receipt_body.encode("utf-8"))
                        .hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-TEST",
                        producer_git_sha=GIT_SHA,
                        created_at=moment,
                    ),
                ],
                transaction_id=txn,
            )
            listed = list_hfic_sessions(store)
            row = next(item for item in listed if item["session_id"] == session_id)
            self.assertEqual(row["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(row["critic_terminal"], "NO_WORTHY_HYPOTHESIS")
            draft = {
                "parent_run_id": "FORGE-RUN-LIST-PROJ",
                "parent_session_id": session_id,
                "scientific_slot_sha256": "11" * 32,
                "terminal_receipt_sha256": "22" * 32,
                "journal_scope": "aa" * 32,
                "technical_gap_code": "PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
                "repair_capability_id": REPAIR_CAPABILITY_ID,
                "allowed_look_ids": [],
                "spent_main_looks": 2,
                "spent_adaptive_looks": 0,
                "spent_preview_looks": 0,
                "owner_authorization_id": "OWNER-AUTH-LIST-PROJ",
                "parent_terminal": "NO_WORTHY_HYPOTHESIS",
            }
            applied = apply_repair_continuation(
                store,
                draft,
                parent_session={
                    **row,
                    "terminal_receipt_sha256": "22" * 32,
                    "journal_scope": "aa" * 32,
                },
                git_sha=GIT_SHA,
            )
            # Mimic resolve_scientific_admission parent_terminal selection from
            # the list projection (not raw session_state alone).
            parent_terminal = (
                str(row.get("critic_terminal") or "")
                or str(row.get("final_session_terminal") or "")
                or str(row.get("session_state") or "")
            )
            overlay = admission_with_repair_continuation(
                {
                    "action": "RETURN_EXISTING_SESSION",
                    "reason_code": row["session_state"],
                    "session_id": session_id,
                    "scientific_slot_sha256": "11" * 32,
                    "occupancy": "OCCUPIED",
                },
                dispositions=[applied["disposition"]],
                parent_terminal=parent_terminal,
            )
            self.assertEqual(parent_terminal, "NO_WORTHY_HYPOTHESIS")
            self.assertEqual(overlay["action"], ACTION_RESUME_REPAIR_CONTINUATION)
            self.assertEqual(overlay["spent_main_looks"], 2)


if __name__ == "__main__":
    unittest.main()
