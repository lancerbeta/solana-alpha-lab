"""FORGE_TEMPORAL_OPERABILITY_REPAIR_V1 acceptance probes."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from collections.abc import Mapping
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
    req = request if request is not None else available
    resp = response if response is not None else available
    occurrence = call_occurrence_id or hashlib.sha256(
        f"{mint}:{point}:{field}".encode("utf-8")
    ).hexdigest()
    row = {
        "mint": mint,
        "cohort_id": COHORT,
        "release_id": RELEASE,
        "point_id": point,
        "field_id": field,
        "state": "OBSERVED",
        "first_reliable_available_at": available,
        "request_started_at": req,
        "response_received_at": resp,
        "event_time": event_time or "2026-09-03T00:00:00Z",
        "typed_value": value,
        "source_price_event_time": source_price_event_time,
        "primitive_id": primitive_id or "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
        "call_occurrence_id": occurrence,
        "request_sha256": request_sha256 or ("dd" * 32),
        "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
    }
    if not bind_snapshot and request is None and not point.startswith("Y"):
        # Legacy EVENT_TIME rows may omit explicit snapshot binding intent.
        pass
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
            "terminal_receipt_sha256": "22" * 32,
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
            "terminal_receipt_sha256": "22" * 32,
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
            "terminal_receipt_sha256": "22" * 32,
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
            "terminal_receipt_sha256": "22" * 32,
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
            "terminal_receipt_sha256": "22" * 32,
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
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            RepairContinuationError,
        )

        draft = self._draft()
        orphan_parent = {
            "session_id": "HFIC-SESS-SYNTHETIC-001",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "terminal_receipt_sha256": "22" * 32,
            "selected_candidate_id": None,
            "scientific_slot_sha256": "11" * 32,
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp) / "store")
            orphan = apply_repair_continuation(
                store, draft, parent_session=orphan_parent, git_sha=GIT_SHA
            )
            with self.assertRaises(RepairContinuationError) as raised:
                close_repair_continuation(
                    store,
                    orphan["disposition"]["disposition_sha256"],
                    git_sha=GIT_SHA,
                )
            self.assertEqual(raised.exception.code, "REPAIR_EXECUTION_NOT_COMPLETE")
            # Successful close → reuse blocked is covered by the post-close
            # owner-readback vertical (MetadataStopAndPostCloseReadbackTests).

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
            "terminal_receipt_sha256": "22" * 32,
            "run_id": "FORGE-RUN-SYNTHETIC-001",
            "selected_candidate_id": None,
            "scientific_slot_sha256": "11" * 32,
            "journal_scope": "aa" * 32,
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
    """Production path: publish → bind → snapshot query → journal → DocumentRunner."""

    def _run_snapshot_vertical(self, *, snapshot_transport: str) -> dict:
        import hashlib

        from solana_alpha_lab.factory.document_runner import (
            DocumentRunner,
            RunContext,
            repository_git_snapshot,
        )
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            execute_discovery_from_rows,
            list_discovery_looks,
            load_admitted_partition_rows,
            resolve_published_discovery_binding,
            run_recorded_discovery_query,
        )
        from solana_alpha_lab.factory.lane_classifier import classify_lane
        from solana_alpha_lab.factory.operational_store import OperationalStore
        from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
        from tests.test_fast_lane_classifier import AS_OF, HYPOTHESIS_DEFINITION_SHA256
        from tests.test_hfic_temporal_discovery_v1 import _spec as _base_spec
        from tests.test_hfic_temporal_production_runner_v1 import (
            DOCUMENT_LATENESS,
            _bind_experiment,
            _publish,
        )

        workspace = Path(tempfile.mkdtemp())
        try:
            data_root = workspace / "rdp"
            _publish(data_root, workspace, snapshot_transport=snapshot_transport)
            binding = resolve_published_discovery_binding(data_root)
            self.assertTrue(binding["cohorts"])
            loaded = load_admitted_partition_rows(
                data_root=data_root,
                binding_doc=binding,
                partitions=None,
                census_path=None,
                observations_path=None,
            )
            # No post-load rewrite: journal and DocumentRunner share published bytes.
            if snapshot_transport == "new":
                self.assertTrue(
                    any(
                        row.get("observation_clock_policy")
                        == OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1
                        for row in loaded["observations"]
                    )
                )
            else:
                self.assertTrue(
                    all(
                        row.get("observation_clock_policy") in (None, "")
                        for row in loaded["observations"]
                    )
                )
            snapshot_spec = _base_spec(
                cost_profile=None,
                query_id=f"vert-a-{snapshot_transport}",
                schedule={
                    "lateness_seconds": DOCUMENT_LATENESS,
                    "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
                },
            )
            cohort_binding = [dict(item) for item in loaded["cohorts"]]
            for item in cohort_binding:
                item.setdefault("holdout", False)
                item.setdefault("evidence_role", "EXPLORATORY_REUSE")
                item["schedule_lateness_seconds"] = DOCUMENT_LATENESS
            store = ResearchStore(data_root)
            journal = "aa" * 32
            git = repository_git_snapshot(ROOT)
            evidence = run_recorded_discovery_query(
                store,
                census=loaded["census"],
                observations=loaded["observations"],
                spec=snapshot_spec,
                binding=cohort_binding,
                journal_scope=journal,
                candidate_scope={"schema": "test", "target": snapshot_spec["target"]},
                git_sha=git.head_sha,
            )
            summary = evidence["result"]
            self.assertEqual(
                summary.get("observation_clock_policy"),
                OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
            )
            self.assertEqual(
                summary.get("calculation_version"), TEMPORAL_CALCULATION_VERSION
            )
            self.assertEqual(int(summary.get("observed_target_n") or 0), 1)
            self.assertIsNotNone(summary.get("mean_target"))
            self.assertTrue(
                any(
                    item.get("look_class") == "MAIN"
                    and item.get("new_look") is not False
                    for item in list_discovery_looks(store, journal)
                )
            )
            experiment = _bind_experiment(summary["experiment_recipe"], data_root)
            decision = classify_lane(
                {
                    "experiment_spec": experiment,
                    "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
                },
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF,
            )
            self.assertEqual(decision.terminal, "FAST_LANE_READY", decision.reason_codes)
            ops = OperationalStore(data_root / "ops" / "operational_state.sqlite")
            try:
                result = DocumentRunner(root=ROOT, store=ops).start_document(
                    experiment,
                    spec_sha256=experiment_spec_sha256(experiment),
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=decision,
                    ),
                )
            finally:
                ops.close()
            self.assertEqual(result["status"], "COMPLETE", result)
            self.assertEqual(result["provider_calls_actual"], 0)
            import json as _json

            run_id = str(result["run_id_or_null"])
            artifact = (
                data_root
                / "research"
                / "artifacts"
                / "results"
                / f"RESULT-ARTIFACT-{run_id.removeprefix('RUN-')}.json"
            )
            saved = _json.loads(artifact.read_text(encoding="utf-8"))
            consumer = saved["capability_result"]["summary"]
            self.assertEqual(
                consumer.get("observation_clock_policy"),
                summary.get("observation_clock_policy"),
            )
            self.assertEqual(
                int(consumer.get("observed_target_n") or 0),
                int(summary.get("observed_target_n") or 0),
            )
            self.assertAlmostEqual(
                float(consumer.get("mean_target")),
                float(summary.get("mean_target")),
                places=9,
            )
            self.assertEqual(
                consumer.get("calculation_version"),
                summary.get("calculation_version"),
            )
            self.assertEqual(
                consumer.get("spec_sha256"),
                summary.get("spec_sha256"),
            )
            journal_pooled = (summary.get("target_exclusion_reasons") or {}).get(
                "pooled"
            ) or {}
            consumer_pooled = (consumer.get("target_exclusion_reasons") or {}).get(
                "pooled"
            ) or {}
            self.assertEqual(consumer_pooled, journal_pooled)
            return {
                "summary": summary,
                "consumer": consumer,
                "loaded": loaded,
                "snapshot_spec": snapshot_spec,
                "cohort_binding": cohort_binding,
            }
        finally:
            import shutil

            shutil.rmtree(workspace, ignore_errors=True)

    def test_new_and_legacy_published_bytes_match_journal_and_consumer(self) -> None:
        new_path = self._run_snapshot_vertical(snapshot_transport="new")
        legacy_path = self._run_snapshot_vertical(snapshot_transport="legacy")
        self.assertEqual(
            new_path["summary"]["observed_target_n"],
            legacy_path["summary"]["observed_target_n"],
        )
        self.assertEqual(
            new_path["summary"]["mean_target"],
            legacy_path["summary"]["mean_target"],
        )

    def test_insufficient_legacy_lineage_is_metadata_blocker(self) -> None:
        rows = SnapshotNegativeControlsTests()._rows_legal()
        stripped = []
        for row in rows:
            body = dict(row)
            body.pop("observation_clock_policy", None)
            body.pop("call_occurrence_id", None)
            body.pop("request_sha256", None)
            body.pop("primitive_id", None)
            stripped.append(body)
        bad = execute_temporal_discovery(
            [_census()], stripped, _spec_snapshot(query_id="vert-a-insufficient"), _binding_mixed()
        )["summary"]
        self.assertEqual(int(bad.get("observed_target_n") or 0), 0)
        pooled = (bad.get("target_exclusion_reasons") or {}).get("pooled") or {}
        membership = (bad.get("membership_exclusion_reasons") or {}).get("pooled") or {}
        text = json.dumps(bad, sort_keys=True, default=str)
        self.assertTrue(
            "SNAPSHOT_LINEAGE_UNINTERPRETABLE" in pooled
            or "SNAPSHOT_OCCURRENCE_UNBOUND" in pooled
            or "SNAPSHOT_LINEAGE_UNINTERPRETABLE" in membership
            or "SNAPSHOT_OCCURRENCE_UNBOUND" in membership
            or "SNAPSHOT_LINEAGE_UNINTERPRETABLE" in text
            or "SNAPSHOT_OCCURRENCE_UNBOUND" in text,
            bad,
        )

    def test_published_snapshot_negatives_and_schema(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            execute_discovery_from_rows,
            load_admitted_partition_rows,
            resolve_published_discovery_binding,
        )
        from solana_alpha_lab.factory.live_cohort_discovery_release import (
            _observation_release_row,
        )
        from solana_alpha_lab.factory.live_cohort_source_bundle import (
            OBSERVATION_COLUMNS,
            OBS_RELEASE_SCHEMA,
            row_for_observation_parquet,
        )
        from tests.test_hfic_temporal_discovery_v1 import _spec as _base_spec
        from tests.test_hfic_temporal_production_runner_v1 import (
            DOCUMENT_LATENESS,
            _publish,
        )

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            _publish(data_root, workspace, snapshot_transport="new")
            binding = resolve_published_discovery_binding(data_root)
            loaded = load_admitted_partition_rows(
                data_root=data_root,
                binding_doc=binding,
                partitions=None,
                census_path=None,
                observations_path=None,
            )
            snapshot_spec = _base_spec(
                cost_profile=None,
                query_id="vert-a-neg",
                schedule={
                    "lateness_seconds": DOCUMENT_LATENESS,
                    "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
                },
            )
            cohort_binding = [dict(item) for item in loaded["cohorts"]]
            for item in cohort_binding:
                item.setdefault("holdout", False)
                item.setdefault("evidence_role", "EXPLORATORY_REUSE")
                item["schedule_lateness_seconds"] = DOCUMENT_LATENESS
            poisoned = [dict(row) for row in loaded["observations"]]
            for row in poisoned:
                if row.get("point_id") == "Y7200" and row.get("field_id") == PRICE:
                    row["primitive_id"] = "PRIM-NOT-REGISTERED-001"
                    row["request_sha256"] = "bogus"
                    row["call_occurrence_id"] = "foreign-occurrence"
            bad = execute_discovery_from_rows(
                loaded["census"], poisoned, snapshot_spec, cohort_binding
            )["summary"]
            self.assertEqual(int(bad.get("observed_target_n") or 0), 0)
            pooled = (bad.get("target_exclusion_reasons") or {}).get("pooled") or {}
            self.assertIn("SNAPSHOT_OCCURRENCE_UNBOUND", pooled)
            mismatched = [dict(row) for row in loaded["observations"]]
            for row in mismatched:
                if row.get("point_id") == "Y7200" and row.get("field_id") == PRICE:
                    row["observation_clock_policy"] = "EVENT_TIME_V1"
            mismatch = execute_discovery_from_rows(
                loaded["census"], mismatched, snapshot_spec, cohort_binding
            )["summary"]
            self.assertEqual(int(mismatch.get("observed_target_n") or 0), 0)
            mismatch_pooled = (
                mismatch.get("target_exclusion_reasons") or {}
            ).get("pooled") or {}
            self.assertIn("SNAPSHOT_POLICY_MISMATCH", mismatch_pooled)

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
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "field_id": PRICE,
                "state": "OBSERVED",
                "typed_value": 1.5,
                "request_started_at": "2026-09-03T02:01:00Z",
                "response_received_at": "2026-09-03T02:01:30Z",
                "first_reliable_available_at": "2026-09-03T02:02:00Z",
                "request_sha256": "dd" * 32,
                "call_occurrence_id": "ab" * 32,
                "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
                "source_price_event_time": "UNKNOWN",
                "member_anchor": "2026-09-03T00:00:00Z",
            }
        )
        self.assertEqual(
            packed["observation_clock_policy"],
            OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        )
        row = _observation_release_row(
            {
                "mint": "m",
                "point_id": "Y7200",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "field_id": PRICE,
                "state": "OBSERVED",
                "typed_value": 1.5,
                "request_sha256": "dd" * 32,
                "call_occurrence_id": "ab" * 32,
                "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
                "source_price_event_time": "2026-09-03T02:01:20Z",
                "member_anchor": "2026-09-03T00:00:00Z",
            },
            cohort_id=COHORT,
            release_id=RELEASE,
        )
        self.assertEqual(row["source_price_event_time"], "2026-09-03T02:01:20Z")


def _is_hex64_local(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


class AcceptanceVerticalBContinuationTests(unittest.TestCase):
    """Production path: historical parent → repair → selected or NO_WORTHY → replay."""

    def test_completed_parent_third_look_new_terminal_and_close(self) -> None:
        import hashlib
        import json as _json

        from solana_alpha_lab.factory.document_runner import repository_git_snapshot
        from solana_alpha_lab.factory.hfic_clock import FrozenClock
        from solana_alpha_lab.factory.hfic_evidence_identity import (
            resolve_scientific_admission,
        )
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            list_discovery_looks,
            run_recorded_discovery_query,
        )
        from solana_alpha_lab.factory.hfic_identity import (
            assign_portfolio_ids,
            normalize_text,
        )
        from solana_alpha_lab.factory.hfic_preflight import persist_forge_context_packet
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            RepairContinuationError,
            spent_looks_from_journal,
        )
        from solana_alpha_lab.factory.hfic_session import (
            _assert_scientific_admission,
            freeze_draft,
            list_hfic_sessions,
            persist_no_worthy_session,
            show_session,
        )
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            persist_feature_preview,
        )
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

        git = repository_git_snapshot(ROOT)
        draft = _json.loads(
            (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json").read_text(
                encoding="utf-8"
            )
        )
        focus = hashlib.sha256(normalize_text("AUTO").encode("utf-8")).hexdigest()
        started = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
        started_text = "2026-08-27T12:00:00Z"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            packet = {
                "schema": "smial.forge-context-packet",
                "owner_focus": "AUTO",
                "evidence_epoch_sha256": "11" * 32,
                "market_evidence_epoch_sha256": "11" * 32,
            }
            ctx = persist_forge_context_packet(
                data_root,
                packet,
                store=store,
                repo_root=ROOT,
                clock=FrozenClock(started),
            )
            receipt = {
                "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
                "evidence_epoch_sha256": "11" * 32,
                "market_evidence_epoch_sha256": "11" * 32,
                "focus_key_sha256": focus,
                "search_key_sha256": "33" * 32,
                "owner_focus": "AUTO",
                "session_started_at": started_text,
                "live_git_head": git.head_sha.lower(),
                "git_composite_sha256": git.composite_sha256,
                "forge_context_packet_sha256": ctx,
                "store_inventory_digest": "ee" * 32,
            }
            frozen = freeze_draft(draft, preflight_receipt=receipt)
            persist_no_worthy_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
                preflight_receipt=receipt,
            )
            shown = show_session(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(shown.get("session_state"), "SYNTHESIS_COMPLETE")
            self.assertEqual(shown.get("critic_terminal"), "NO_WORTHY_HYPOTHESIS")
            journal = str(shown["search_key_sha256"])
            rows = SnapshotTargetTests()._rows_legal()
            census = [_census()]
            binding = _binding_mixed()
            for spec in (
                _spec_snapshot(
                    query_id="prior-1",
                    all=[{"feature": "mark", "op": "gte", "value": 0.0}],
                ),
                _spec_snapshot(
                    query_id="prior-2",
                    all=[{"feature": "mark", "op": "gte", "value": 0.1}],
                ),
            ):
                run_recorded_discovery_query(
                    store,
                    census=census,
                    observations=rows,
                    spec=spec,
                    binding=binding,
                    journal_scope=journal,
                    candidate_scope={"schema": "test", "target": spec["target"]},
                    git_sha=git.head_sha,
                )
            persist_feature_preview(
                store,
                journal_scope=journal,
                preview={"preview_sha256": "ab" * 32},
                git_sha=git.head_sha,
            )
            spent = spent_looks_from_journal(store, journal)
            self.assertEqual(spent["spent_main_looks"], 2)
            self.assertEqual(spent["spent_preview_looks"], 1)
            run_id = "FORGE-RUN-VERT-B-001"
            run_payload = {
                "run_id": run_id,
                "session_id": shown["session_id"],
                "scientific_slot_sha256": shown["scientific_slot_sha256"],
                "owner_final": "NO_WORTHY_HYPOTHESIS",
            }
            run_json = _json.dumps(run_payload, sort_keys=True, separators=(",", ":"))
            wrapper = {
                "artifact_kind": "FORGE_RUN_RECEIPT",
                "payload_canonical": run_json,
                "payload_sha256": hashlib.sha256(run_json.encode("utf-8")).hexdigest(),
            }
            wrapper_json = _json.dumps(wrapper, sort_keys=True, separators=(",", ":"))
            store.append(
                [
                    ResearchEvent(
                        record_id=f"HFIC-ART-FORGE-RUN-{run_id}",
                        record_kind=RecordKind.RESEARCH_ARTIFACT,
                        entity_id=run_id,
                        hypothesis_version_id=None,
                        run_id=run_id,
                        transaction_id="RESEARCH-TXN-FORGE-RUN",
                        effective_at=started,
                        first_reliable_available_at=started,
                        supersedes_record_id=None,
                        payload_json=wrapper_json,
                        payload_sha256=hashlib.sha256(
                            wrapper_json.encode("utf-8")
                        ).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-TEST",
                        producer_git_sha=git.head_sha,
                        created_at=started,
                    )
                ],
                transaction_id="RESEARCH-TXN-FORGE-RUN",
            )
            parent = {
                "session_id": shown["session_id"],
                "session_state": shown["session_state"],
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "selected_candidate_id": None,
                "scientific_slot_sha256": shown["scientific_slot_sha256"],
                "terminal_receipt_sha256": shown["session_receipt_sha256"],
                "run_id": run_id,
                "journal_scope": journal,
                "search_key_sha256": journal,
            }
            draft_r = {
                "parent_run_id": run_id,
                "parent_session_id": parent["session_id"],
                "scientific_slot_sha256": parent["scientific_slot_sha256"],
                "terminal_receipt_sha256": parent["terminal_receipt_sha256"],
                "journal_scope": journal,
                "technical_gap_code": "PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
                "repair_capability_id": REPAIR_CAPABILITY_ID,
                "allowed_look_ids": [],
                "spent_main_looks": spent["spent_main_looks"],
                "spent_adaptive_looks": spent["spent_adaptive_looks"],
                "spent_preview_looks": spent["spent_preview_looks"],
                "owner_authorization_id": "OWNER-AUTH-VERT-B-001",
                "parent_terminal": "NO_WORTHY_HYPOTHESIS",
                "evidence_mapping": {"repair": "snapshot_clocks"},
            }
            blocked = resolve_scientific_admission(
                list_hfic_sessions(store),
                reservations=[],
                market_evidence_epoch="11" * 32,
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
                repair_continuations=[],
            )
            self.assertEqual(blocked["action"], "RETURN_EXISTING_SESSION")
            plan = plan_repair_continuation(
                draft_r, parent_session=parent, store=store
            )
            self.assertEqual(plan["status"], "READY", plan)
            self.assertEqual(plan["remaining_main_looks"], 4)
            applied = apply_repair_continuation(
                store, draft_r, parent_session=parent, git_sha=git.head_sha
            )
            self.assertTrue(applied["applied"])
            self.assertEqual(applied["disposition"]["spent_preview_looks"], 1)
            replay = apply_repair_continuation(
                store, draft_r, parent_session=parent, git_sha=git.head_sha
            )
            self.assertEqual(replay.get("status"), "ALREADY_APPLIED")
            self.assertTrue(replay.get("idempotent"))
            competing = dict(draft_r)
            competing["owner_authorization_id"] = "OWNER-AUTH-VERT-B-COMPETE"
            with self.assertRaises(RepairContinuationError) as raised:
                apply_repair_continuation(
                    store, competing, parent_session=parent, git_sha=git.head_sha
                )
            self.assertIn(
                str(raised.exception),
                {"COMPETING_ACTIVE_DISPOSITION", "COMPETING_DISPOSITION_APPLIED"},
            )
            resumed = _assert_scientific_admission(
                store, {**frozen, **receipt}, repo_root=ROOT
            )
            self.assertEqual(resumed["action"], ACTION_RESUME_REPAIR_CONTINUATION)
            third = _spec_snapshot(
                query_id="cont-3",
                all=[{"feature": "mark", "op": "gte", "value": 0.2}],
            )
            run_recorded_discovery_query(
                store,
                census=census,
                observations=rows,
                spec=third,
                binding=binding,
                journal_scope=journal,
                candidate_scope={"schema": "test", "target": third["target"]},
                git_sha=git.head_sha,
            )
            mains = [
                item
                for item in list_discovery_looks(store, journal)
                if item.get("look_class") == "MAIN" and item.get("new_look") is not False
            ]
            self.assertEqual(len(mains), 3)
            persist_no_worthy_session(
                store,
                {**frozen, **receipt},
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
                preflight_receipt=receipt,
            )
            repair_disp = applied["disposition"]["disposition_sha256"]
            cycles = []
            for record in store.iter_committed_records():
                kind = getattr(record.record_kind, "value", record.record_kind)
                if kind != "RESEARCH_CYCLE":
                    continue
                payload = _json.loads(record.payload_json)
                if payload.get("session_id") == shown["session_id"]:
                    cycles.append(payload)
            self.assertTrue(
                any(
                    item.get("repair_continuation_disposition_sha256") == repair_disp
                    for item in cycles
                ),
                cycles,
            )
            closed = close_repair_continuation(store, repair_disp, git_sha=git.head_sha)
            self.assertEqual(closed["status"], "CLOSED")
            after = _assert_scientific_admission(
                store, {**frozen, **receipt}, repo_root=ROOT
            )
            self.assertEqual(after["action"], "RETURN_EXISTING_SESSION")
            blocked_again = plan_repair_continuation(
                {
                    **draft_r,
                    "spent_main_looks": applied["disposition"]["spent_main_looks"],
                    "spent_adaptive_looks": applied["disposition"][
                        "spent_adaptive_looks"
                    ],
                    "spent_preview_looks": applied["disposition"][
                        "spent_preview_looks"
                    ],
                    "allowed_look_ids": list(
                        applied["disposition"].get("allowed_look_ids") or []
                    ),
                    "evidence_mapping": dict(
                        applied["disposition"].get("evidence_mapping") or {}
                    ),
                },
                parent_session=parent,
                existing_dispositions=list_repair_continuation_dispositions(store),
                store=store,
            )
            self.assertEqual(blocked_again["reason_code"], "DISPOSITION_ALREADY_CLOSED")

    def test_selected_repair_with_new_execution_binding_finalize_and_replay(self) -> None:
        """Historical parent → repair → selected freeze/finalize under new capability."""

        import hashlib
        import json as _json

        from solana_alpha_lab.factory.document_runner import repository_git_snapshot
        from solana_alpha_lab.factory.hfic_clock import FrozenClock
        from solana_alpha_lab.factory.hfic_identity import (
            assign_portfolio_ids,
            normalize_text,
        )
        from solana_alpha_lab.factory.hfic_preflight import persist_forge_context_packet
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            spent_looks_from_journal,
        )
        from solana_alpha_lab.factory.hfic_session import (
            _assert_scientific_admission,
            finalize_session,
            freeze_draft,
            list_hfic_sessions,
            load_session_bundle,
            persist_frozen_session,
            persist_no_worthy_session,
            show_session,
        )
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            persist_feature_preview,
        )
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            list_discovery_looks,
            run_recorded_discovery_query,
        )
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent
        from tests.test_hfic_session import finalize_kill_complete, _critic_result, valid_draft

        git = repository_git_snapshot(ROOT)
        draft = _json.loads(
            (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json").read_text(
                encoding="utf-8"
            )
        )
        focus = hashlib.sha256(normalize_text("AUTO").encode("utf-8")).hexdigest()
        started = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
        started_text = "2026-08-27T12:00:00Z"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            packet = {
                "schema": "smial.forge-context-packet",
                "owner_focus": "AUTO",
                "evidence_epoch_sha256": "11" * 32,
                "market_evidence_epoch_sha256": "11" * 32,
            }
            ctx = persist_forge_context_packet(
                data_root,
                packet,
                store=store,
                repo_root=ROOT,
                clock=FrozenClock(started),
            )
            receipt = {
                "receipt_id": "HFIC-PREFLIGHT-FIXTURE-SEL-001",
                "evidence_epoch_sha256": "11" * 32,
                "market_evidence_epoch_sha256": "11" * 32,
                "focus_key_sha256": focus,
                "search_key_sha256": "33" * 32,
                "owner_focus": "AUTO",
                "session_started_at": started_text,
                "live_git_head": git.head_sha.lower(),
                "git_composite_sha256": git.composite_sha256,
                "forge_context_packet_sha256": ctx,
                "store_inventory_digest": "ee" * 32,
            }
            frozen = freeze_draft(draft, preflight_receipt=receipt)
            persist_no_worthy_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
                preflight_receipt=receipt,
            )
            shown = show_session(store, str(frozen["session_id"]), repo_root=ROOT)
            journal = str(shown["search_key_sha256"])
            rows = SnapshotTargetTests()._rows_legal()
            census = [_census()]
            binding = _binding_mixed()
            for spec in (
                _spec_snapshot(query_id="sel-prior-1"),
                _spec_snapshot(
                    query_id="sel-prior-2",
                    all=[{"feature": "mark", "op": "gte", "value": 0.1}],
                ),
            ):
                run_recorded_discovery_query(
                    store,
                    census=census,
                    observations=rows,
                    spec=spec,
                    binding=binding,
                    journal_scope=journal,
                    candidate_scope={"schema": "test", "target": spec["target"]},
                    git_sha=git.head_sha,
                )
            persist_feature_preview(
                store,
                journal_scope=journal,
                preview={"preview_sha256": "cd" * 32},
                git_sha=git.head_sha,
            )
            spent = spent_looks_from_journal(store, journal)
            run_id = "FORGE-RUN-VERT-B-SEL-001"
            run_payload = {
                "run_id": run_id,
                "session_id": shown["session_id"],
                "scientific_slot_sha256": shown["scientific_slot_sha256"],
                "owner_final": "NO_WORTHY_HYPOTHESIS",
            }
            run_json = _json.dumps(run_payload, sort_keys=True, separators=(",", ":"))
            wrapper = {
                "artifact_kind": "FORGE_RUN_RECEIPT",
                "payload_canonical": run_json,
                "payload_sha256": hashlib.sha256(run_json.encode("utf-8")).hexdigest(),
            }
            wrapper_json = _json.dumps(wrapper, sort_keys=True, separators=(",", ":"))
            store.append(
                [
                    ResearchEvent(
                        record_id=f"HFIC-ART-FORGE-RUN-{run_id}",
                        record_kind=RecordKind.RESEARCH_ARTIFACT,
                        entity_id=run_id,
                        hypothesis_version_id=None,
                        run_id=run_id,
                        transaction_id="RESEARCH-TXN-FORGE-RUN-SEL",
                        effective_at=started,
                        first_reliable_available_at=started,
                        supersedes_record_id=None,
                        payload_json=wrapper_json,
                        payload_sha256=hashlib.sha256(
                            wrapper_json.encode("utf-8")
                        ).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-TEST",
                        producer_git_sha=git.head_sha,
                        created_at=started,
                    )
                ],
                transaction_id="RESEARCH-TXN-FORGE-RUN-SEL",
            )
            # Immutable parent snapshot: repair continues from sealed store bytes
            # with 86b24-stable (non-REPAIR) artifact ids — not a live tip rewrite.
            import shutil

            parent_snapshot = Path(tmp) / "parent_snapshot_86b24_shape"
            shutil.copytree(data_root, parent_snapshot)
            store = ResearchStore(parent_snapshot)
            data_root = parent_snapshot
            shown = show_session(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(shown.get("critic_terminal"), "NO_WORTHY_HYPOTHESIS")
            parent_ids = {
                str(getattr(record, "record_id", "") or "")
                for record in store.iter_committed_records()
            }
            self.assertIn(f"HFIC-ART-FORGE-DRAFT-{shown['session_id']}", parent_ids)
            self.assertIn(
                f"HFIC-ART-SESSION-RECEIPT-{shown['session_id']}-NO-WORTHY",
                parent_ids,
            )
            self.assertFalse(any("REPAIR-" in rid for rid in parent_ids))
            journal = str(shown["search_key_sha256"])
            spent = spent_looks_from_journal(store, journal)
            parent = {
                "session_id": shown["session_id"],
                "session_state": shown["session_state"],
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "selected_candidate_id": None,
                "scientific_slot_sha256": shown["scientific_slot_sha256"],
                "terminal_receipt_sha256": shown["session_receipt_sha256"],
                "run_id": run_id,
                "journal_scope": journal,
                "search_key_sha256": journal,
            }
            draft_r = {
                "parent_run_id": run_id,
                "parent_session_id": parent["session_id"],
                "scientific_slot_sha256": parent["scientific_slot_sha256"],
                "terminal_receipt_sha256": parent["terminal_receipt_sha256"],
                "journal_scope": journal,
                "technical_gap_code": "PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
                "repair_capability_id": REPAIR_CAPABILITY_ID,
                "allowed_look_ids": [],
                "spent_main_looks": spent["spent_main_looks"],
                "spent_adaptive_looks": spent["spent_adaptive_looks"],
                "spent_preview_looks": spent["spent_preview_looks"],
                "owner_authorization_id": "OWNER-AUTH-VERT-B-SEL-001",
                "parent_terminal": "NO_WORTHY_HYPOTHESIS",
                "evidence_mapping": {"repair": "selected_continuation"},
            }
            applied = apply_repair_continuation(
                store, draft_r, parent_session=parent, git_sha=git.head_sha
            )
            self.assertTrue(applied["applied"])
            third = _spec_snapshot(
                query_id="sel-cont-3",
                all=[{"feature": "mark", "op": "gte", "value": 0.2}],
            )
            run_recorded_discovery_query(
                store,
                census=census,
                observations=rows,
                spec=third,
                binding=binding,
                journal_scope=journal,
                candidate_scope={"schema": "test", "target": third["target"]},
                git_sha=git.head_sha,
            )
            self.assertEqual(
                len(
                    [
                        item
                        for item in list_discovery_looks(store, journal)
                        if item.get("look_class") == "MAIN"
                        and item.get("new_look") is not False
                    ]
                ),
                3,
            )
            selected_source = valid_draft()
            selected_source["selected_candidate_ref"] = selected_source["candidates"][0][
                "label"
            ]
            selected_source["runner_up_candidate_ref"] = selected_source["candidates"][1][
                "label"
            ]
            selected_source["strongest_rejected_alternative"] = selected_source[
                "candidates"
            ][2]["label"]
            new_capability = "ab" * 32
            repair_receipt = {
                **receipt,
                "capability_epoch_sha256": new_capability,
            }
            selected_frozen = freeze_draft(
                selected_source, preflight_receipt=repair_receipt, repo_root=ROOT
            )
            self.assertEqual(selected_frozen["session_id"], shown["session_id"])
            selected_frozen["capability_epoch_sha256"] = new_capability
            admission = _assert_scientific_admission(
                store, {**selected_frozen, **repair_receipt}, repo_root=ROOT
            )
            self.assertEqual(admission["action"], ACTION_RESUME_REPAIR_CONTINUATION)
            persist_frozen_session(
                store,
                {**selected_frozen, **repair_receipt},
                repo_root=ROOT,
                identities=assign_portfolio_ids(selected_source["candidates"]),
                draft=selected_source,
            )
            bundle = load_session_bundle(store, shown["session_id"])
            self.assertEqual(bundle["session_state"], "FROZEN_AWAITING_CRITIC")
            self.assertEqual(
                bundle.get("repair_continuation_disposition_sha256"),
                applied["disposition"]["disposition_sha256"],
            )
            listed = [
                item
                for item in list_hfic_sessions(store)
                if item["session_id"] == shown["session_id"]
            ][0]
            self.assertEqual(
                listed.get("repair_continuation_disposition_sha256"),
                applied["disposition"]["disposition_sha256"],
            )
            shown_frozen = show_session(store, shown["session_id"], repo_root=ROOT)
            self.assertEqual(
                shown_frozen.get("repair_continuation_disposition_sha256"),
                applied["disposition"]["disposition_sha256"],
            )
            # Parent artifacts must keep pre-repair (86b24-stable) identities;
            # repair freeze appends disposition-scoped ids alongside them.
            parent_draft_id = f"HFIC-ART-FORGE-DRAFT-{shown['session_id']}"
            parent_receipt_id = (
                f"HFIC-ART-SESSION-RECEIPT-{shown['session_id']}-NO-WORTHY"
            )
            committed_ids = {
                str(getattr(record, "record_id", "") or "")
                for record in store.iter_committed_records()
            }
            self.assertIn(parent_draft_id, committed_ids)
            self.assertIn(parent_receipt_id, committed_ids)
            self.assertTrue(
                any(
                    "REPAIR-" in rid
                    and (
                        rid.startswith(f"HFIC-ART-FORGE-DRAFT-{shown['session_id']}-")
                        or rid.startswith(
                            f"HFIC-ART-SESSION-RECEIPT-{shown['session_id']}-"
                        )
                    )
                    for rid in committed_ids
                ),
                committed_ids,
            )
            critic = _critic_result(selected_frozen, "KILL_PREPARATORY_LOOP")
            done = finalize_kill_complete(
                {**selected_frozen, **repair_receipt},
                critic,
                store,
                repo_root=ROOT,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(done["critic_terminal"], "KILL_PREPARATORY_LOOP")
            shown_after = show_session(store, shown["session_id"], repo_root=ROOT)
            self.assertEqual(shown_after["critic_terminal"], "KILL_PREPARATORY_LOOP")
            self.assertNotEqual(shown_after["critic_terminal"], "NO_WORTHY_HYPOTHESIS")
            self.assertEqual(
                shown_after.get("repair_continuation_disposition_sha256"),
                applied["disposition"]["disposition_sha256"],
            )
            # forge-run --no-write readback must see the new terminal, not parent NO_WORTHY.
            from unittest.mock import patch

            from solana_alpha_lab.factory.hfic_representation_ladder import (
                evaluate_forge_run,
            )

            listed_after = [
                item
                for item in list_hfic_sessions(store)
                if item["session_id"] == shown["session_id"]
            ][0]
            self.assertEqual(
                listed_after.get("critic_terminal"), "KILL_PREPARATORY_LOOP"
            )
            self.assertEqual(listed_after.get("session_state"), "SYNTHESIS_COMPLETE")
            forge_input = {
                "schema": "smial.forge-input-receipt",
                "owner_class": "SEARCH",
                "market_evidence_epoch_sha256": "11" * 32,
                "capability_epoch_sha256": "ab" * 32,
                "active_evidence_set": {"visible_cohort_ids": []},
            }
            with patch(
                "solana_alpha_lab.factory.hfic_representation_ladder.build_forge_input_receipt",
                return_value=forge_input,
            ), patch(
                # Disposable store has no cohort lineage; allow same-market
                # discovery so forge-run can bind the preferred session from
                # sealed store bytes (not an injected stages echo).
                "solana_alpha_lab.factory.hfic_representation_ladder._session_applicable_to_current_market",
                return_value=True,
            ):
                forge_readback = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    preferred_control_session_id=str(shown["session_id"]),
                )
            discovered = [
                stage
                for stage in list(forge_readback.get("stages") or [])
                if stage.get("session_id") == shown["session_id"]
            ]
            self.assertTrue(discovered, forge_readback.get("stages"))
            self.assertEqual(
                discovered[0].get("effective_terminal"),
                "KILL_PREPARATORY_LOOP",
            )
            self.assertNotEqual(
                discovered[0].get("effective_terminal"),
                "NO_WORTHY_HYPOTHESIS",
            )
            self.assertEqual(forge_readback["writes"]["research_store"], 0)
            self.assertEqual(forge_readback["writes"]["forge_run"], 0)
            self.assertIsNotNone(forge_readback.get("owner_final"))
            listed_replay = [
                item
                for item in list_hfic_sessions(store)
                if item["session_id"] == shown["session_id"]
            ][0]
            self.assertEqual(
                listed_replay.get("critic_terminal"),
                listed_after.get("critic_terminal"),
            )
            self.assertEqual(
                listed_replay.get("repair_continuation_disposition_sha256"),
                applied["disposition"]["disposition_sha256"],
            )
            # Sticky query replay: same third look bytes → no evaluator, no new MAIN.
            replay_third = run_recorded_discovery_query(
                store,
                census=census,
                observations=rows,
                spec=third,
                binding=binding,
                journal_scope=journal,
                candidate_scope={"schema": "test", "target": third["target"]},
                git_sha=git.head_sha,
            )
            self.assertEqual(replay_third["queries"][0]["new_look"], False)
            self.assertEqual(replay_third["queries"][0]["look_class"], "RETRY_SAME_BYTES")
            self.assertEqual(
                len(
                    [
                        item
                        for item in list_discovery_looks(store, journal)
                        if item.get("look_class") == "MAIN"
                        and item.get("new_look") is not False
                    ]
                ),
                3,
            )
            # Restart against the completed terminal stays sticky; no second
            # active execution and no return to the parent NO_WORTHY DONE.
            sticky = load_session_bundle(store, shown["session_id"])
            self.assertEqual(sticky["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(sticky["critic_terminal"], "KILL_PREPARATORY_LOOP")
            mains_after = [
                item
                for item in list_discovery_looks(store, journal)
                if item.get("look_class") == "MAIN" and item.get("new_look") is not False
            ]
            self.assertEqual(len(mains_after), 3)
            closed = close_repair_continuation(
                store,
                shown_after["repair_continuation_disposition_sha256"],
                git_sha=git.head_sha,
            )
            self.assertEqual(closed["status"], "CLOSED")

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
                        payload_sha256=hashlib.sha256(
                            body.encode("utf-8")
                        ).hexdigest(),
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
                        payload_sha256=hashlib.sha256(
                            receipt_body.encode("utf-8")
                        ).hexdigest(),
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
                "spent_main_looks": 0,
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
                    "run_id": "FORGE-RUN-LIST-PROJ",
                },
                git_sha=GIT_SHA,
            )
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


class MetadataStopAndPostCloseReadbackTests(unittest.TestCase):
    """P1 residual: metadata technical stop; post-close owner result lineage."""

    def test_wholly_uninterpretable_input_blocks_scientific_exhaustion(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            assert_search_exhaustion_claim,
            assess_tier_progress,
            execute_temporal_discovery,
        )

        rows = SnapshotNegativeControlsTests()._rows_legal()
        stripped = []
        for row in rows:
            body = dict(row)
            for key in (
                "observation_clock_policy",
                "call_occurrence_id",
                "request_sha256",
                "primitive_id",
            ):
                body.pop(key, None)
            stripped.append(body)
        summary = execute_temporal_discovery(
            [_census()],
            stripped,
            _spec_snapshot(query_id="p11-tech-stop", search_tier="COMPOUND_SCREEN"),
            _binding_mixed(),
        )["summary"]
        self.assertTrue(summary.get("technical_failure"))
        self.assertEqual(
            (summary.get("technical_stop") or {}).get("reason_code"),
            "SNAPSHOT_LINEAGE_UNINTERPRETABLE",
        )
        looks = [
            {
                "new_look": True,
                "search_tier": "SIMPLE_SCREEN",
                "look_class": "MAIN",
                "result": summary,
            },
            {
                "new_look": True,
                "search_tier": "COMPOUND_SCREEN",
                "look_class": "MAIN",
                "result": summary,
            },
        ]
        progress = assess_tier_progress(looks, freeze_worthy=False)
        self.assertFalse(progress.get("search_exhausted_allowed"))
        self.assertNotEqual(progress.get("action"), "READY_TO_FREEZE")
        with self.assertRaises(GroundedDiscoveryError) as raised:
            assert_search_exhaustion_claim(progress, claim_search_exhausted=True)
        self.assertEqual(str(raised.exception), "SEARCH_EXHAUSTED_WITHOUT_COMPOUND")
        # Compound-inapplicable shortcut must not launder technical looks into
        # SEARCH_EXHAUSTED / READY_TO_FREEZE either.
        inapplicable = assess_tier_progress(
            looks, freeze_worthy=False, compound_applicable=False
        )
        self.assertFalse(inapplicable.get("search_exhausted_allowed"))
        self.assertNotEqual(inapplicable.get("action"), "READY_TO_FREEZE")
        self.assertEqual(inapplicable.get("compound_status"), "TECHNICAL_BLOCKED")
        with self.assertRaises(GroundedDiscoveryError):
            assert_search_exhaustion_claim(inapplicable, claim_search_exhausted=True)
        # Interpretable positive path is unchanged.
        legal = SnapshotTargetTests()._rows_legal()
        ok = execute_temporal_discovery(
            [_census()], legal, _spec_snapshot(query_id="p11-ok"), _binding_mixed()
        )["summary"]
        self.assertGreaterEqual(int(ok.get("observed_target_n") or 0), 1)
        self.assertIsNone(ok.get("technical_stop"))

    def test_post_close_forge_run_prefers_repair_terminal_over_parent(self) -> None:
        """Historical SEARCH_EXHAUSTED receipt must not overshadow repair KILL after close."""

        import hashlib
        import json as _json
        import shutil
        from unittest.mock import patch

        from solana_alpha_lab.factory.document_runner import repository_git_snapshot
        from solana_alpha_lab.factory.hfic_clock import FrozenClock
        from solana_alpha_lab.factory.hfic_evidence_identity import forge_run_identity_sha256
        from solana_alpha_lab.factory.hfic_identity import (
            assign_portfolio_ids,
            normalize_text,
        )
        from solana_alpha_lab.factory.hfic_preflight import persist_forge_context_packet
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            close_repair_continuation,
            spent_looks_from_journal,
        )
        from solana_alpha_lab.factory.hfic_representation_ladder import (
            ACTION_NON_SCIENTIFIC_STOP,
            ACTION_SEARCH_EXHAUSTED,
            _lookup_run_artifact,
            evaluate_forge_run,
        )
        from solana_alpha_lab.factory.hfic_session import (
            _assert_scientific_admission,
            freeze_draft,
            list_hfic_sessions,
            persist_frozen_session,
            persist_no_worthy_session,
            show_session,
        )
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            persist_feature_preview,
        )
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            list_discovery_looks,
            run_recorded_discovery_query,
        )
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent
        from tests.test_hfic_session import finalize_kill_complete, _critic_result, valid_draft

        git = repository_git_snapshot(ROOT)
        draft = _json.loads(
            (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json").read_text(
                encoding="utf-8"
            )
        )
        focus = hashlib.sha256(normalize_text("AUTO").encode("utf-8")).hexdigest()
        started = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
        started_text = "2026-08-27T12:00:00Z"
        market = "11" * 32
        run_identity = forge_run_identity_sha256(
            market_evidence_epoch_sha256=market,
            frozen_representation_ids=["BASE"],
            owner_focus="AUTO",
            frozen_representation_versions=["BASE@HFIC-V1.2"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            packet = {
                "schema": "smial.forge-context-packet",
                "owner_focus": "AUTO",
                "evidence_epoch_sha256": market,
                "market_evidence_epoch_sha256": market,
            }
            ctx = persist_forge_context_packet(
                data_root,
                packet,
                store=store,
                repo_root=ROOT,
                clock=FrozenClock(started),
            )
            receipt = {
                "receipt_id": "HFIC-PREFLIGHT-P12-001",
                "evidence_epoch_sha256": market,
                "market_evidence_epoch_sha256": market,
                "focus_key_sha256": focus,
                "search_key_sha256": "33" * 32,
                "owner_focus": "AUTO",
                "session_started_at": started_text,
                "live_git_head": git.head_sha.lower(),
                "git_composite_sha256": git.composite_sha256,
                "forge_context_packet_sha256": ctx,
                "store_inventory_digest": "ee" * 32,
            }
            frozen = freeze_draft(draft, preflight_receipt=receipt)
            persist_no_worthy_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
                preflight_receipt=receipt,
            )
            shown = show_session(store, str(frozen["session_id"]), repo_root=ROOT)
            journal = str(shown["search_key_sha256"])
            rows = SnapshotTargetTests()._rows_legal()
            census = [_census()]
            binding = _binding_mixed()
            for spec in (
                _spec_snapshot(query_id="p12-prior-1"),
                _spec_snapshot(
                    query_id="p12-prior-2",
                    all=[{"feature": "mark", "op": "gte", "value": 0.1}],
                ),
            ):
                run_recorded_discovery_query(
                    store,
                    census=census,
                    observations=rows,
                    spec=spec,
                    binding=binding,
                    journal_scope=journal,
                    candidate_scope={"schema": "test", "target": spec["target"]},
                    git_sha=git.head_sha,
                )
            persist_feature_preview(
                store,
                journal_scope=journal,
                preview={"preview_sha256": "cd" * 32},
                git_sha=git.head_sha,
            )
            spent = spent_looks_from_journal(store, journal)
            run_id = "FORGE-RUN-P12-PARENT"
            run_payload = {
                "schema": "smial.forge-run-receipt",
                "schema_version": "1.0",
                "run_id": run_id,
                "run_identity_sha256": run_identity,
                "session_id": shown["session_id"],
                "scientific_slot_sha256": shown["scientific_slot_sha256"],
                "owner_focus": "AUTO",
                "owner_final": ACTION_SEARCH_EXHAUSTED,
                "next_action": "RETURN_EXISTING",
                "market_evidence_epoch_sha256": market,
                "capability_epoch_sha256": "aa" * 32,
                "stages": [
                    {
                        "representation_id": "BASE",
                        "session_id": shown["session_id"],
                        "effective_terminal": "NO_WORTHY_HYPOTHESIS",
                        "execution_status": "EXECUTED",
                        "capability_epoch_sha256": "aa" * 32,
                    }
                ],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "visible_cohort_ids": [],
                "used_cohort_ids": [],
                "frozen_representation_ids": ["BASE"],
                "frozen_representation_versions": ["BASE@HFIC-V1.2"],
            }
            run_json = _json.dumps(run_payload, sort_keys=True, separators=(",", ":"))
            wrapper = {
                "artifact_kind": "FORGE_RUN_RECEIPT",
                "payload_canonical": run_json,
                "payload_sha256": hashlib.sha256(run_json.encode("utf-8")).hexdigest(),
            }
            wrapper_json = _json.dumps(wrapper, sort_keys=True, separators=(",", ":"))
            store.append(
                [
                    ResearchEvent(
                        record_id=f"HFIC-ART-FORGE-RUN-{run_id}",
                        record_kind=RecordKind.RESEARCH_ARTIFACT,
                        entity_id=run_id,
                        hypothesis_version_id=None,
                        run_id=run_id,
                        transaction_id="RESEARCH-TXN-FORGE-RUN-P12",
                        effective_at=started,
                        first_reliable_available_at=started,
                        supersedes_record_id=None,
                        payload_json=wrapper_json,
                        payload_sha256=hashlib.sha256(
                            wrapper_json.encode("utf-8")
                        ).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-TEST",
                        producer_git_sha=git.head_sha,
                        created_at=started,
                    )
                ],
                transaction_id="RESEARCH-TXN-FORGE-RUN-P12",
            )
            found = _lookup_run_artifact(store, run_identity)
            self.assertIsNotNone(found)
            self.assertEqual(found.get("owner_final"), ACTION_SEARCH_EXHAUSTED)
            parent_snapshot = Path(tmp) / "parent_snap"
            shutil.copytree(data_root, parent_snapshot)
            store = ResearchStore(parent_snapshot)
            data_root = parent_snapshot
            shown = show_session(store, str(frozen["session_id"]), repo_root=ROOT)
            journal = str(shown["search_key_sha256"])
            spent = spent_looks_from_journal(store, journal)
            parent = {
                "session_id": shown["session_id"],
                "session_state": shown["session_state"],
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "selected_candidate_id": None,
                "scientific_slot_sha256": shown["scientific_slot_sha256"],
                "terminal_receipt_sha256": shown["session_receipt_sha256"],
                "run_id": run_id,
                "journal_scope": journal,
                "search_key_sha256": journal,
            }
            draft_r = {
                "parent_run_id": run_id,
                "parent_session_id": parent["session_id"],
                "scientific_slot_sha256": parent["scientific_slot_sha256"],
                "terminal_receipt_sha256": parent["terminal_receipt_sha256"],
                "journal_scope": journal,
                "technical_gap_code": "PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
                "repair_capability_id": REPAIR_CAPABILITY_ID,
                "allowed_look_ids": [],
                "spent_main_looks": spent["spent_main_looks"],
                "spent_adaptive_looks": spent["spent_adaptive_looks"],
                "spent_preview_looks": spent["spent_preview_looks"],
                "owner_authorization_id": "OWNER-AUTH-P12-001",
                "parent_terminal": "NO_WORTHY_HYPOTHESIS",
                "evidence_mapping": {"repair": "post_close_readback"},
            }
            applied = apply_repair_continuation(
                store, draft_r, parent_session=parent, git_sha=git.head_sha
            )
            third = _spec_snapshot(
                query_id="p12-cont-3",
                all=[{"feature": "mark", "op": "gte", "value": 0.2}],
            )
            run_recorded_discovery_query(
                store,
                census=census,
                observations=rows,
                spec=third,
                binding=binding,
                journal_scope=journal,
                candidate_scope={"schema": "test", "target": third["target"]},
                git_sha=git.head_sha,
            )
            self.assertEqual(
                len(
                    [
                        item
                        for item in list_discovery_looks(store, journal)
                        if item.get("look_class") == "MAIN"
                        and item.get("new_look") is not False
                    ]
                ),
                3,
            )
            selected_source = valid_draft()
            selected_source["selected_candidate_ref"] = selected_source["candidates"][0][
                "label"
            ]
            selected_source["runner_up_candidate_ref"] = selected_source["candidates"][1][
                "label"
            ]
            selected_source["strongest_rejected_alternative"] = selected_source[
                "candidates"
            ][2]["label"]
            new_capability = "ab" * 32
            repair_receipt = {
                **receipt,
                "capability_epoch_sha256": new_capability,
            }
            selected_frozen = freeze_draft(
                selected_source, preflight_receipt=repair_receipt, repo_root=ROOT
            )
            selected_frozen["capability_epoch_sha256"] = new_capability
            admission = _assert_scientific_admission(
                store, {**selected_frozen, **repair_receipt}, repo_root=ROOT
            )
            self.assertEqual(admission["action"], ACTION_RESUME_REPAIR_CONTINUATION)
            persist_frozen_session(
                store,
                {**selected_frozen, **repair_receipt},
                repo_root=ROOT,
                identities=assign_portfolio_ids(selected_source["candidates"]),
                draft=selected_source,
            )
            critic = _critic_result(selected_frozen, "KILL_PREPARATORY_LOOP")
            done = finalize_kill_complete(
                {**selected_frozen, **repair_receipt},
                critic,
                store,
                repo_root=ROOT,
            )
            self.assertEqual(done["critic_terminal"], "KILL_PREPARATORY_LOOP")
            closed = close_repair_continuation(
                store,
                applied["disposition"]["disposition_sha256"],
                git_sha=git.head_sha,
            )
            self.assertEqual(closed["status"], "CLOSED")
            self.assertIsNotNone(closed.get("forge_run_receipt_sha256"))
            after = _lookup_run_artifact(store, run_identity)
            self.assertIsNotNone(after)
            self.assertEqual(
                after.get("repair_continuation_disposition_sha256"),
                applied["disposition"]["disposition_sha256"],
            )
            self.assertEqual(after.get("owner_final"), ACTION_NON_SCIENTIFIC_STOP)
            self.assertNotEqual(after.get("owner_final"), ACTION_SEARCH_EXHAUSTED)
            forge_input = {
                "schema": "smial.forge-input-receipt",
                "owner_class": "SEARCH",
                "market_evidence_epoch_sha256": market,
                "capability_epoch_sha256": new_capability,
                "active_evidence_set": {"visible_cohort_ids": []},
            }
            with patch(
                "solana_alpha_lab.factory.hfic_representation_ladder.build_forge_input_receipt",
                return_value=forge_input,
            ), patch(
                "solana_alpha_lab.factory.hfic_representation_ladder._session_applicable_to_current_market",
                return_value=True,
            ):
                readback = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    preferred_control_session_id=str(shown["session_id"]),
                )
            self.assertEqual(readback.get("owner_final"), ACTION_NON_SCIENTIFIC_STOP)
            self.assertNotEqual(readback.get("owner_final"), ACTION_SEARCH_EXHAUSTED)
            self.assertNotEqual(
                readback.get("blocking_reason_codes"),
                ["SCIENTIFIC_IDENTITY_CONFLICT"],
            )
            stages = list(readback.get("stages") or [])
            matched = [
                row
                for row in stages
                if row.get("session_id") == shown["session_id"]
                or row.get("effective_terminal") == "KILL_PREPARATORY_LOOP"
            ]
            self.assertTrue(matched, stages)
            self.assertEqual(readback["writes"]["research_store"], 0)
            # Restart / reopen store: repair terminal still current.
            reopened = ResearchStore(data_root)
            again = _lookup_run_artifact(reopened, run_identity)
            self.assertEqual(
                again.get("repair_continuation_disposition_sha256"),
                applied["disposition"]["disposition_sha256"],
            )
            self.assertEqual(again.get("owner_final"), ACTION_NON_SCIENTIFIC_STOP)
            replay = close_repair_continuation(
                reopened,
                applied["disposition"]["disposition_sha256"],
                git_sha=git.head_sha,
            )
            self.assertEqual(replay["status"], "ALREADY_CLOSED")


class FinishOutcomeMatrixTests(unittest.TestCase):
    """PR350 finish matrix: input fitness scope + repair canonical terminal."""

    def _strip_lineage(self, rows: list[dict]) -> list[dict]:
        out = []
        for row in rows:
            body = dict(row)
            for key in (
                "observation_clock_policy",
                "call_occurrence_id",
                "request_sha256",
                "primitive_id",
            ):
                body.pop(key, None)
            out.append(body)
        return out

    def test_census_not_x_eligible_does_not_cancel_technical_stop(self) -> None:
        from solana_alpha_lab.factory.hfic_temporal_discovery import assess_tier_progress

        legal = SnapshotNegativeControlsTests()._rows_legal()
        stripped = self._strip_lineage(legal)
        alone = execute_temporal_discovery(
            [_census()], stripped, _spec_snapshot(query_id="mx-alone"), _binding_mixed()
        )["summary"]
        mixed = execute_temporal_discovery(
            [_census(), {**_census("mint-b"), "candidate_state": "NOT_ELIGIBLE"}],
            stripped,
            _spec_snapshot(query_id="mx-mixed"),
            _binding_mixed(),
        )["summary"]
        self.assertEqual(
            (alone.get("technical_stop") or {}).get("reason_code"),
            "SNAPSHOT_LINEAGE_UNINTERPRETABLE",
        )
        self.assertEqual(
            (mixed.get("technical_stop") or {}).get("reason_code"),
            "SNAPSHOT_LINEAGE_UNINTERPRETABLE",
        )
        self.assertIn("NOT_X_ELIGIBLE", mixed.get("exclusion_reasons") or {})
        looks = [
            {
                "new_look": True,
                "search_tier": "SIMPLE_SCREEN",
                "look_class": "MAIN",
                "result": mixed,
            },
            {
                "new_look": True,
                "search_tier": "COMPOUND_SCREEN",
                "look_class": "MAIN",
                "result": mixed,
            },
        ]
        progress = assess_tier_progress(
            looks, freeze_worthy=False, compound_applicable=True
        )
        self.assertEqual(progress["action"], "STOP_TECHNICAL_INPUT")
        self.assertFalse(progress["search_exhausted_allowed"])

    def test_decision_lineage_absence_preserves_reason_and_blocks_exhaustion(self) -> None:
        from solana_alpha_lab.factory.hfic_temporal_discovery import assess_tier_progress

        legal = SnapshotNegativeControlsTests()._rows_legal()
        rows = []
        for row in legal:
            body = dict(row)
            if body["point_id"] == "Y3600":
                for key in (
                    "observation_clock_policy",
                    "call_occurrence_id",
                    "request_sha256",
                    "primitive_id",
                ):
                    body.pop(key, None)
            rows.append(body)
        summary = execute_temporal_discovery(
            [_census()], rows, _spec_snapshot(query_id="mx-dec"), _binding_mixed()
        )["summary"]
        self.assertEqual(int(summary.get("population_n") or 0), 1)
        self.assertEqual(int(summary.get("decision_eligible_n") or 0), 0)
        self.assertEqual(
            (summary.get("technical_stop") or {}).get("reason_code"),
            "SNAPSHOT_LINEAGE_UNINTERPRETABLE",
        )
        self.assertIn(
            "SNAPSHOT_LINEAGE_UNINTERPRETABLE",
            summary.get("exclusion_reasons") or {},
        )
        looks = [
            {
                "new_look": True,
                "search_tier": "SIMPLE_SCREEN",
                "look_class": "MAIN",
                "result": summary,
            },
            {
                "new_look": True,
                "search_tier": "COMPOUND_SCREEN",
                "look_class": "MAIN",
                "result": summary,
            },
        ]
        progress = assess_tier_progress(
            looks, freeze_worthy=False, compound_applicable=True
        )
        self.assertFalse(progress["search_exhausted_allowed"])

    def test_reference_lineage_absence_visible_on_target_exclusions(self) -> None:
        # Decision observed; reference Y3600 stripped of lineage (same cell as
        # decision in this fixture) — use exit-only strip + separate reference
        # via a second mint path is heavy; strip Y3600 and keep X300/Y7200.
        legal = SnapshotNegativeControlsTests()._rows_legal()
        rows = []
        for row in legal:
            body = dict(row)
            if body["point_id"] == "Y3600":
                for key in (
                    "observation_clock_policy",
                    "call_occurrence_id",
                    "request_sha256",
                    "primitive_id",
                ):
                    body.pop(key, None)
            rows.append(body)
        summary = execute_temporal_discovery(
            [_census()], rows, _spec_snapshot(query_id="mx-ref"), _binding_mixed()
        )["summary"]
        pooled = (summary.get("target_exclusion_reasons") or {}).get("pooled") or {}
        self.assertIn("SNAPSHOT_LINEAGE_UNINTERPRETABLE", pooled)
        self.assertIsNotNone(summary.get("technical_stop"))

    def test_valid_zero_match_remains_scientific(self) -> None:
        from solana_alpha_lab.factory.hfic_temporal_discovery import assess_tier_progress

        legal = SnapshotNegativeControlsTests()._rows_legal()
        summary = execute_temporal_discovery(
            [_census()],
            legal,
            _spec_snapshot(
                query_id="mx-zero",
                all=[{"feature": "mark", "op": "gte", "value": 9.0}],
            ),
            _binding_mixed(),
        )["summary"]
        self.assertIsNone(summary.get("technical_stop"))
        self.assertEqual(int(summary.get("population_n") or 0), 1)
        self.assertEqual(int(summary.get("matched_n") or 0), 0)
        looks = [
            {
                "new_look": True,
                "search_tier": "SIMPLE_SCREEN",
                "look_class": "MAIN",
                "result": summary,
            },
            {
                "new_look": True,
                "search_tier": "COMPOUND_SCREEN",
                "look_class": "MAIN",
                "result": summary,
            },
        ]
        progress = assess_tier_progress(
            looks, freeze_worthy=False, compound_applicable=True
        )
        self.assertNotEqual(progress.get("action"), "STOP_TECHNICAL_INPUT")

    def test_repair_completion_prefers_final_session_terminal(self) -> None:
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            _repair_completion_from_session,
        )
        from solana_alpha_lab.factory.hfic_representation_ladder import (
            ACTION_NON_SCIENTIFIC_STOP,
            ACTION_OWNER_CANDIDATE,
            ACTION_SEARCH_EXHAUSTED,
        )

        failover = _repair_completion_from_session(
            {
                "session_state": "SYNTHESIS_COMPLETE",
                "critic_terminal": "KILL_DATA_INFEASIBLE",
                "final_session_terminal": "PASS_FAST_LANE_READY",
            }
        )
        self.assertEqual(failover, ("PASS_FAST_LANE_READY", ACTION_OWNER_CANDIDATE))
        primary_kill = _repair_completion_from_session(
            {
                "session_state": "SYNTHESIS_COMPLETE",
                "critic_terminal": "KILL_DATA_INFEASIBLE",
                "final_session_terminal": "KILL_DATA_INFEASIBLE",
            }
        )
        self.assertEqual(
            primary_kill, ("KILL_DATA_INFEASIBLE", ACTION_NON_SCIENTIFIC_STOP)
        )
        scientific = _repair_completion_from_session(
            {
                "session_state": "SYNTHESIS_COMPLETE",
                "critic_terminal": "KILL_MECHANISM",
                "final_session_terminal": "KILL_MECHANISM",
            }
        )
        self.assertEqual(scientific, ("KILL_MECHANISM", ACTION_SEARCH_EXHAUSTED))
        no_worthy = _repair_completion_from_session(
            {
                "session_state": "SYNTHESIS_COMPLETE",
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "final_session_terminal": "NO_WORTHY_HYPOTHESIS",
            }
        )
        self.assertEqual(no_worthy, ("NO_WORTHY_HYPOTHESIS", ACTION_SEARCH_EXHAUSTED))

    def test_repair_completion_refuses_incomplete_states(self) -> None:
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            RepairContinuationError,
            _repair_completion_from_session,
            apply_repair_continuation,
            close_repair_continuation,
        )

        self.assertIsNone(
            _repair_completion_from_session(
                {
                    "session_state": "AWAITING_CLASSIFICATION",
                    "critic_terminal": "PASS_TO_CLASSIFICATION",
                    "final_session_terminal": "",
                }
            )
        )
        self.assertIsNone(
            _repair_completion_from_session(
                {
                    "session_state": "RUNNER_UP_AWAITING_CRITIC",
                    "critic_terminal": "KILL_DATA_INFEASIBLE",
                    "final_session_terminal": "",
                    "runner_up_candidate_id": "HFIC-CAND-RUNNER",
                }
            )
        )
        draft = {
            "parent_run_id": "FORGE-RUN-INCOMPLETE",
            "parent_session_id": "HFIC-SESS-INCOMPLETE",
            "scientific_slot_sha256": "11" * 32,
            "terminal_receipt_sha256": "22" * 32,
            "journal_scope": "aa" * 32,
            "technical_gap_code": "PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
            "repair_capability_id": REPAIR_CAPABILITY_ID,
            "allowed_look_ids": [],
            "spent_main_looks": 2,
            "spent_adaptive_looks": 0,
            "spent_preview_looks": 0,
            "owner_authorization_id": "OWNER-AUTH-INCOMPLETE",
            "parent_terminal": "NO_WORTHY_HYPOTHESIS",
        }
        parent = {
            "session_id": "HFIC-SESS-INCOMPLETE",
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "terminal_receipt_sha256": "22" * 32,
            "selected_candidate_id": None,
            "scientific_slot_sha256": "11" * 32,
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            applied = apply_repair_continuation(
                store, draft, parent_session=parent, git_sha=GIT_SHA
            )
            with self.assertRaises(RepairContinuationError) as raised:
                close_repair_continuation(
                    store,
                    applied["disposition"]["disposition_sha256"],
                    git_sha=GIT_SHA,
                )
            self.assertEqual(raised.exception.code, "REPAIR_EXECUTION_NOT_COMPLETE")


class OwnerDataScenarioTechnicalAndScientificTests(unittest.TestCase):
    """Production data entrypoints: technical stop vs scientific freeze/readout."""

    def test_technical_stop_journal_blocks_scientific_exhaustion_readout(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            list_discovery_looks,
            run_recorded_discovery_query,
        )
        from solana_alpha_lab.factory.document_runner import repository_git_snapshot
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            assess_tier_progress,
            assert_search_exhaustion_claim,
        )

        legal = SnapshotNegativeControlsTests()._rows_legal()
        stripped = []
        for row in legal:
            body = dict(row)
            for key in (
                "observation_clock_policy",
                "call_occurrence_id",
                "request_sha256",
                "primitive_id",
            ):
                body.pop(key, None)
            stripped.append(body)
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            journal = "aa" * 32
            git = repository_git_snapshot(ROOT)
            evidence = run_recorded_discovery_query(
                store,
                census=[
                    _census(),
                    {**_census("mint-b"), "candidate_state": "NOT_ELIGIBLE"},
                ],
                observations=stripped,
                spec=_spec_snapshot(query_id="owner-data-tech"),
                binding=_binding_mixed(),
                journal_scope=journal,
                candidate_scope={
                    "schema": "test",
                    "target": _spec_snapshot()["target"],
                },
                git_sha=git.head_sha,
            )
            summary = evidence["result"]
            self.assertTrue(summary.get("technical_failure"))
            self.assertEqual(
                (summary.get("technical_stop") or {}).get("reason_code"),
                "SNAPSHOT_LINEAGE_UNINTERPRETABLE",
            )
            looks = list_discovery_looks(store, journal)
            self.assertTrue(looks)
            readout = format_discovery_readout(evidence)
            text = json.dumps(readout, ensure_ascii=False).upper()
            self.assertTrue(
                "TECHNICAL" in text or summary.get("technical_failure") is True,
                readout,
            )
            progress = assess_tier_progress(
                [
                    {
                        "new_look": True,
                        "search_tier": "SIMPLE_SCREEN",
                        "look_class": "MAIN",
                        "result": summary,
                    },
                    {
                        "new_look": True,
                        "search_tier": "COMPOUND_SCREEN",
                        "look_class": "MAIN",
                        "result": summary,
                    },
                ],
                freeze_worthy=False,
                compound_applicable=True,
            )
            with self.assertRaises(GroundedDiscoveryError):
                assert_search_exhaustion_claim(progress, claim_search_exhausted=True)

    def test_scientific_positive_and_zero_match_remain_distinct(self) -> None:
        legal = SnapshotNegativeControlsTests()._rows_legal()
        positive = execute_temporal_discovery(
            [_census()], legal, _spec_snapshot(query_id="owner-pos"), _binding_mixed()
        )["summary"]
        zero = execute_temporal_discovery(
            [_census()],
            legal,
            _spec_snapshot(
                query_id="owner-zero",
                all=[{"feature": "mark", "op": "gte", "value": 9.0}],
            ),
            _binding_mixed(),
        )["summary"]
        self.assertGreaterEqual(int(positive.get("observed_target_n") or 0), 1)
        self.assertIsNone(positive.get("technical_stop"))
        self.assertEqual(int(zero.get("matched_n") or 0), 0)
        self.assertIsNone(zero.get("technical_stop"))
        self.assertNotEqual(
            format_discovery_readout({"result": positive, "result_refs": []}),
            format_discovery_readout({"result": zero, "result_refs": []}),
        )


class OwnerContinuationRunnerUpPassTests(unittest.TestCase):
    """Primary KILL → runner-up PASS close keeps OWNER_CANDIDATE + survivor id."""

    def test_close_after_runner_up_pass_keeps_owner_candidate(self) -> None:
        from solana_alpha_lab.factory.hfic_control_integrity import (
            effective_control_terminal,
        )
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            RepairContinuationError,
            _persist_repair_completion_forge_run,
            apply_repair_continuation,
            close_repair_continuation,
        )
        from solana_alpha_lab.factory.hfic_representation_ladder import (
            ACTION_OWNER_CANDIDATE,
        )
        from solana_alpha_lab.factory.hfic_session import (
            apply_classification,
            finalize_session,
            freeze_draft,
            load_session_bundle,
        )
        from solana_alpha_lab.factory.document_runner import repository_git_snapshot
        from tests.test_fast_lane_classifier import submission
        from tests.test_hfic_cli import critic_result_from_packet_only
        from tests.test_hfic_one_frozen_runner_up_failover_v1 import (
            _happy_with_pit_runner_up,
            _with_selected_feats,
        )
        from tests import test_hfic_session as session_tests
        from solana_alpha_lab.factory.run_passport import (
            canonical_json_bytes,
            canonical_sha256,
        )
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

        session_tests._CACHED_GIT = None
        git = repository_git_snapshot(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = _happy_with_pit_runner_up()
            frozen = freeze_draft(
                draft,
                preflight_receipt=session_tests._preflight_receipt(),
                repo_root=ROOT,
            )
            # Parent forge-run identity so close can supersede.
            run_identity = "ab" * 32
            parent_run = {
                "schema": "smial.forge-run-receipt",
                "schema_version": "1.0",
                "run_id": "FORGE-RUN-RUNNERUP-PASS",
                "run_identity_sha256": run_identity,
                "owner_focus": "AUTO",
                "owner_class": "SEARCH",
                "next_action": "RETURN_EXISTING",
                "owner_final": "SEARCH_EXHAUSTED_CURRENT_EVIDENCE",
                "session_id": frozen["session_id"],
                "scientific_slot_sha256": frozen.get("scientific_slot_sha256")
                or ("11" * 32),
                "market_evidence_epoch_sha256": "11" * 32,
                "stages": [],
                "writes": {"research_store": 0},
            }
            parent_run["receipt_sha256"] = canonical_sha256(parent_run)
            body = canonical_json_bytes(parent_run).decode("utf-8")
            artifact = {
                "research_artifact_id": "HFIC-ART-FORGE-RUN-PARENTPASS",
                "hfic_protocol": "HFIC-V1.2",
                "artifact_kind": "FORGE_RUN_RECEIPT",
                "payload_canonical": body,
                "payload_sha256": parent_run["receipt_sha256"],
            }
            payload_json = json.dumps(
                artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            now = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
            store.append(
                [
                    ResearchEvent(
                        record_id="HFIC-ART-FORGE-RUN-PARENTPASS",
                        record_kind=RecordKind.RESEARCH_ARTIFACT,
                        entity_id="HFIC-ART-FORGE-RUN-PARENTPASS",
                        hypothesis_version_id=None,
                        run_id=parent_run["run_id"],
                        transaction_id="RESEARCH-TXN-PARENTPASS",
                        effective_at=now,
                        first_reliable_available_at=now,
                        supersedes_record_id=None,
                        payload_json=payload_json,
                        payload_sha256=hashlib.sha256(
                            payload_json.encode("utf-8")
                        ).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id=REPAIR_CAPABILITY_ID,
                        producer_git_sha=git.head_sha,
                        created_at=now,
                    )
                ],
                transaction_id="RESEARCH-TXN-PARENTPASS",
            )
            repair_draft = {
                "parent_run_id": parent_run["run_id"],
                "parent_session_id": frozen["session_id"],
                "scientific_slot_sha256": parent_run["scientific_slot_sha256"],
                "terminal_receipt_sha256": "22" * 32,
                "journal_scope": "aa" * 32,
                "technical_gap_code": "PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
                "repair_capability_id": REPAIR_CAPABILITY_ID,
                "allowed_look_ids": [],
                "spent_main_looks": 2,
                "spent_adaptive_looks": 0,
                "spent_preview_looks": 0,
                "owner_authorization_id": "OWNER-AUTH-RUNNERUP-PASS",
                "parent_terminal": "NO_WORTHY_HYPOTHESIS",
            }
            parent = {
                "session_id": frozen["session_id"],
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "terminal_receipt_sha256": "22" * 32,
                "selected_candidate_id": None,
                "scientific_slot_sha256": parent_run["scientific_slot_sha256"],
                "run_id": parent_run["run_id"],
                "journal_scope": "aa" * 32,
            }
            applied = apply_repair_continuation(
                store, repair_draft, parent_session=parent, git_sha=git.head_sha
            )
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(
                    frozen["critic_input_packet"], "KILL_DATA_INFEASIBLE"
                ),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(pending["session_state"], "RUNNER_UP_AWAITING_CRITIC")
            with self.assertRaises(RepairContinuationError) as raised:
                close_repair_continuation(
                    store,
                    applied["disposition"]["disposition_sha256"],
                    git_sha=git.head_sha,
                )
            self.assertEqual(raised.exception.code, "REPAIR_EXECUTION_NOT_COMPLETE")
            waiting = finalize_session(
                pending,
                critic_result_from_packet_only(
                    pending["critic_input_packet"], "PASS_TO_CLASSIFICATION"
                ),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(waiting["session_state"], "AWAITING_CLASSIFICATION")
            packet = _with_selected_feats(
                submission(),
                frozen["runner_up_critic_input_packet"],
            )
            packet["hypothesis_definition_sha256"] = frozen["runner_up_definition_sha256"]
            done = apply_classification(
                waiting,
                packet,
                store=store,
                repo_root=ROOT,
                data_root=Path(tmp),
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            bundle = load_session_bundle(store, frozen["session_id"])
            assert bundle is not None
            self.assertEqual(bundle.get("critic_terminal"), "KILL_DATA_INFEASIBLE")
            self.assertEqual(
                effective_control_terminal(bundle),
                bundle.get("final_session_terminal"),
            )
            self.assertNotEqual(
                bundle.get("critic_terminal"),
                effective_control_terminal(bundle),
            )
            survivor = (
                bundle.get("final_survivor_candidate_id")
                or done.get("final_survivor_candidate_id")
                or frozen["runner_up_candidate_id"]
            )
            self.assertEqual(survivor, frozen["runner_up_candidate_id"])
            self.assertNotEqual(survivor, frozen["selected_candidate_id"])
            closed = close_repair_continuation(
                store,
                applied["disposition"]["disposition_sha256"],
                git_sha=git.head_sha,
            )
            self.assertEqual(closed["status"], "CLOSED")
            repair_receipt = _persist_repair_completion_forge_run(
                store,
                disposition={
                    **applied["disposition"],
                    "status": "CLOSED",
                    "disposition_sha256": applied["disposition"]["disposition_sha256"],
                },
                git_sha=git.head_sha,
                now=now,
            )
            self.assertIsNotNone(repair_receipt)
            assert repair_receipt is not None
            self.assertEqual(repair_receipt.get("owner_final"), ACTION_OWNER_CANDIDATE)
            stage = (repair_receipt.get("stages") or [{}])[0]
            self.assertEqual(stage.get("effective_terminal"), effective_control_terminal(bundle))
            self.assertEqual(stage.get("critic_terminal"), "KILL_DATA_INFEASIBLE")
            self.assertEqual(
                stage.get("selected_candidate_id"),
                frozen["runner_up_candidate_id"],
            )


if __name__ == "__main__":
    unittest.main()
