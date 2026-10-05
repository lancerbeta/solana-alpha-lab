"""OPPORTUNITY_EPISODES contract proofs on owner boundaries (D1, D2, D4, D10).

Expected values are literals written from the contract, never recomputed by
the helper under test. Legacy pins were computed on base de20465e.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from solana_alpha_lab.factory import opportunity_episodes as oe  # noqa: E402
from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    GroundedDiscoveryError,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    POINT_OFFSET,
    canonical_temporal_spec,
    execute_temporal_discovery,
    temporal_frozen_input,
    validate_temporal_query,
)
from tests.test_opportunity_episodes_harness_v1 import (  # noqa: E402
    build_schedule,
    synth_mint,
    token_object,
    write_assignment,
)

PRICE, LIQ, HOLD = "FIELD-USD-PRICE-001", "FIELD-LIQUIDITY-USD-001", "FIELD-HOLDER-COUNT-001"
COHORT = "REL-20261005T000000Z-20261006T000000Z"
RELEASE = "ab" * 32
BINDING = {
    "schedule_contract": "OPPORTUNITY_EPISODE_SCHEDULE_V1",
    "schedule_sha256": "cd" * 32,
    "dense_step_seconds": 300,
    "dense_until_seconds": 21600,
    "hourly_step_seconds": 3600,
    "horizon_seconds": 259200,
    "dispatch_window_seconds": 60,
    "availability_grace_seconds": 300,
    "witness_max_age_seconds": 120,
}


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def episode_spec(**overrides):
    spec = {
        "schema": "smial.hfic-temporal-query",
        "schema_version": "1.1",
        "query_id": "EP-CONTRACT",
        "population": "OPPORTUNITY_EPISODES",
        "anchor_kind": "NOMINATION_T0",
        "time_contract": {
            "schedule_contract": "OPPORTUNITY_EPISODE_SCHEDULE_V1",
            "time_feature_clock": "FIRST_RELIABLE_AVAILABLE_AT",
        },
        "search_tier": "COMPOUND_SCREEN",
        "budget_allocation": "COMPOUND_FIRST",
        "decision": {"point_id": "E1800"},
        "features": [
            {"name": "holders", "op": "point_value", "field_id": HOLD, "point": "E1800"},
            {"name": "d_holders", "op": "delta", "field_id": HOLD, "start": "E300", "end": "E1800"},
            {"name": "r_holders", "op": "return_ratio", "field_id": HOLD, "start": "E300", "end": "E1800"},
            {"name": "liq", "op": "point_value", "field_id": LIQ, "point": "E1800"},
            {"name": "pret", "op": "return_ratio", "field_id": PRICE, "start": "E300", "end": "E1800"},
            {"name": "elapsed", "op": "elapsed_seconds", "start": "E300", "end": "E1800"},
        ],
        "all": [
            {"feature": "d_holders", "op": "gt", "value": 0},
            {"feature": "pret", "op": "gte", "value": 0},
            {"feature": "liq", "op": "lte", "value": 1000000},
        ],
        "target": {"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E1800", "exit_point": "E14400", "field_id": PRICE},
        "entry_model": {"kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT", "assumed_latency_seconds": 0},
    }
    spec.update(overrides)
    return spec


def binding_item(**overrides):
    item = {
        "dataset_id": "DATASET-OPPORTUNITY-EPISODES-DISCOVERY-CORPUS-001",
        "population": "OPPORTUNITY_EPISODES",
        "evidence_role": "EXPLORATORY_REUSE",
        "holdout": False,
        "cohort_id": COHORT,
        "release_id": RELEASE,
        "census_sha256": "11" * 32,
        "observations_sha256": "22" * 32,
        "schedule_binding": dict(BINDING),
    }
    item.update(overrides)
    return item


def obs_row(episode, mint, point, field, value, *, available, state="OBSERVED", lag=(4, 1)):
    request = utc(available) - timedelta(seconds=lag[0])
    response = utc(available) - timedelta(seconds=lag[1])
    return {
        "cohort_id": COHORT,
        "release_id": RELEASE,
        "episode_id": episode,
        "mint": mint,
        "point_id": point,
        "field_id": field,
        "typed_value": None if value is None else str(value),
        "state": state,
        "request_started_at": iso(request),
        "response_received_at": iso(response),
        "first_reliable_available_at": available,
        "request_sha256": "33" * 32,
        "call_occurrence_id": ("44" * 31) + point[-2:].rjust(2, "0").replace("E", "0")[:2],
        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
        "observation_clock_policy": "PROVIDER_REPORTED_SNAPSHOT_V1",
        "source_price_event_time": "UNKNOWN",
    }


def prd_vector():
    """PRD 18.1a literal vector: one full episode and one gap episode."""

    t0 = "2026-10-05T00:02:10Z"
    census = []
    rows = []
    for episode, mint, exit_present in (("EP-FULL", synth_mint("Full"), True), ("EP-GAP", synth_mint("Gap"), False)):
        census.append({"cohort_id": COHORT, "release_id": RELEASE, "episode_id": episode, "mint": mint, "t0": t0})
        for point, available, values in (
            ("E300", "2026-10-05T00:10:04Z", (1.00, 60, 10000)),
            ("E1800", "2026-10-05T00:35:09Z", (1.02, 75, 12000)),
            ("E14400", "2026-10-05T04:05:08Z", (1.122, 80, 12500)),
        ):
            for field, value in zip((PRICE, HOLD, LIQ), values):
                if point == "E14400" and not exit_present:
                    rows.append(obs_row(episode, mint, point, field, None, available="2026-10-05T04:10:00Z", state="CENSORED"))
                else:
                    rows.append(obs_row(episode, mint, point, field, value, available=available))
    return census, rows


class ResolverLiteralTests(unittest.TestCase):
    def test_prd_vector_clocks_are_literal(self) -> None:
        t0 = utc("2026-10-05T00:02:10Z")
        expected = {
            "E300": ("2026-10-05T00:07:10Z", "2026-10-05T00:10:00Z", "2026-10-05T00:15:00Z"),
            "E1800": ("2026-10-05T00:32:10Z", "2026-10-05T00:35:00Z", "2026-10-05T00:40:00Z"),
            "E14400": ("2026-10-05T04:02:10Z", "2026-10-05T04:05:00Z", "2026-10-05T04:10:00Z"),
            "E21600": ("2026-10-05T06:02:10Z", "2026-10-05T06:05:00Z", "2026-10-05T06:10:00Z"),
            "E25200": ("2026-10-05T07:02:10Z", "2026-10-05T08:00:00Z", "2026-10-05T08:05:00Z"),
            "E259200": ("2026-10-08T00:02:10Z", "2026-10-08T01:00:00Z", "2026-10-08T01:05:00Z"),
        }
        for point, (nominal, assigned, deadline) in expected.items():
            window = oe.resolve_point(BINDING, t0, point)
            self.assertEqual(iso(window.nominal_due), nominal, point)
            self.assertEqual(iso(window.assigned_at), assigned, point)
            self.assertEqual(iso(window.availability_deadline), deadline, point)
            self.assertEqual(iso(window.dispatch_deadline), iso(utc(assigned) + timedelta(seconds=60)), point)
        witness = oe.resolve_point(BINDING, t0, "E0")
        self.assertIsNone(witness.assigned_at)
        self.assertEqual(iso(witness.request_not_before), "2026-10-05T00:00:10Z")
        self.assertEqual(iso(witness.availability_deadline), "2026-10-05T00:02:10Z")
        # Last availability vs T0 vs nominal 72h horizon (literal).
        last = utc("2026-10-08T01:00:04Z")
        self.assertEqual(int((last - t0).total_seconds()), 262674)
        self.assertEqual(259200, 72 * 3600)

    def test_grid_shape_and_on_grid_instant(self) -> None:
        points = oe.episode_point_ids()
        self.assertEqual(len(points), 139)
        self.assertEqual(points[:3], ("E0", "E300", "E600"))
        self.assertIn("E21600", points)
        self.assertNotIn("E21900", points)
        self.assertEqual(points[73], "E25200")
        self.assertEqual(points[-1], "E259200")
        on_grid = utc("2026-10-05T00:00:00Z")
        self.assertEqual(iso(oe.resolve_point(BINDING, on_grid, "E300").assigned_at), "2026-10-05T00:05:00Z")
        self.assertEqual(iso(oe.resolve_point(BINDING, on_grid, "E25200").assigned_at), "2026-10-05T07:00:00Z")
        for bad in ("X300", "E301", "E21900", "E0300", "E", "E-300"):
            with self.assertRaises(oe.OpportunityEpisodeError):
                oe.resolve_point(BINDING, on_grid, bad)

    def test_unknown_binding_is_refused_before_values(self) -> None:
        for key, value in (("schedule_contract", "X"), ("dense_step_seconds", 600), ("horizon_seconds", 1)):
            broken = dict(BINDING, **{key: value})
            with self.assertRaises(oe.OpportunityEpisodeError):
                oe.resolve_point(broken, utc("2026-10-05T00:00:00Z"), "E300")


class EvaluatorLiteralTests(unittest.TestCase):
    def test_prd_numeric_witness(self) -> None:
        census, rows = prd_vector()
        result = execute_temporal_discovery(census, rows, episode_spec(), [binding_item()])
        summary = result["summary"]
        self.assertEqual(summary["population"], "OPPORTUNITY_EPISODES")
        self.assertEqual(summary["episode_counts"]["n_admitted"], 2)
        self.assertEqual(summary["episode_counts"]["n_decision_eligible"], 2)
        self.assertEqual(summary["episode_counts"]["n_matched"], 2)
        self.assertEqual(summary["episode_counts"]["n_target_available"], 1)
        self.assertEqual(summary["missing_target_n"], 1)
        means = summary["matched_feature_means"]
        self.assertAlmostEqual(means["d_holders"], 15.0, places=9)
        self.assertAlmostEqual(means["r_holders"], 0.25, places=9)
        self.assertAlmostEqual(means["pret"], 0.02, places=9)
        # Actual availability 00:10:04 -> 00:35:09, never nominal 1500 s.
        self.assertEqual(means["elapsed"], 1505.0)
        self.assertAlmostEqual(summary["mean_target"], 0.10, places=9)
        self.assertNotEqual(summary["mean_target"], 0.0)

    def test_gap_never_becomes_zero_and_stays_in_base(self) -> None:
        census, rows = prd_vector()
        summary = execute_temporal_discovery(census, rows, episode_spec(), [binding_item()])["summary"]
        self.assertEqual(summary["population_n"], 2)
        self.assertEqual(summary["target_exclusion_reasons"]["pooled"], {"EXIT_NOT_OBSERVED": 1})

    def test_late_feature_value_is_not_timely(self) -> None:
        census, rows = prd_vector()
        late = copy.deepcopy(rows)
        for row in late:
            if row["episode_id"] == "EP-FULL" and row["point_id"] == "E300":
                row["first_reliable_available_at"] = "2026-10-05T00:15:01Z"
                row["response_received_at"] = "2026-10-05T00:15:00Z"
        summary = execute_temporal_discovery(census, late, episode_spec(), [binding_item()])["summary"]
        self.assertEqual(summary["episode_counts"]["n_joint_feature_supported"], 1)

    def test_witness_e0_and_long_points_through_reader(self) -> None:
        t0 = "2026-10-05T00:02:10Z"
        mint = synth_mint("Wit")
        census = [{"cohort_id": COHORT, "release_id": RELEASE, "episode_id": "EP-W", "mint": mint, "t0": t0}]
        rows = []
        for point, available, price in (
            ("E0", "2026-10-05T00:02:00Z", 1.0),
            ("E21600", "2026-10-05T06:05:04Z", 2.0),
            ("E259200", "2026-10-08T01:00:04Z", 3.0),
        ):
            for field, value in ((PRICE, price), (HOLD, 70), (LIQ, 20000)):
                rows.append(obs_row("EP-W", mint, point, field, value, available=available))
        spec = episode_spec(
            decision={"point_id": "E21600"},
            features=[
                {"name": "w_holders", "op": "point_value", "field_id": HOLD, "point": "E0"},
                {"name": "ret", "op": "return_ratio", "field_id": PRICE, "start": "E0", "end": "E21600"},
            ],
            all=[{"feature": "ret", "op": "gt", "value": 0}],
            target={"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E21600", "exit_point": "E259200", "field_id": PRICE},
        )
        summary = execute_temporal_discovery(census, rows, spec, [binding_item()])["summary"]
        self.assertEqual(summary["matched_n"], 1)
        self.assertAlmostEqual(summary["matched_feature_means"]["ret"], 1.0, places=9)
        self.assertAlmostEqual(summary["mean_target"], 0.5, places=9)
        stale = copy.deepcopy(rows)
        for row in stale:
            if row["point_id"] == "E0":
                row["request_started_at"] = "2026-10-05T00:00:05Z"
        stale_summary = execute_temporal_discovery(census, stale, spec, [binding_item()])["summary"]
        self.assertEqual(stale_summary["matched_n"], 0)
        self.assertEqual(stale_summary["episode_counts"]["n_joint_feature_supported"], 0)


class QueryGuardTests(unittest.TestCase):
    def test_more_than_eight_points_refused(self) -> None:
        features = [
            {"name": f"p{i}", "op": "point_value", "field_id": PRICE, "point": f"E{300 * i}"} for i in range(1, 8)
        ]
        spec = episode_spec(
            features=features,
            all=[{"feature": "p1", "op": "gt", "value": 0}],
            decision={"point_id": "E2400"},
            target={"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E2400", "exit_point": "E14400", "field_id": PRICE},
        )
        with self.assertRaisesRegex(GroundedDiscoveryError, "QUERY_TOO_WIDE"):
            validate_temporal_query(spec)

    def test_exit_must_follow_decision_cutoff_and_features_precede(self) -> None:
        for target, code in (
            ({"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E1800", "exit_point": "E2100", "field_id": PRICE}, "TARGET_NOT_AFTER_DECISION_CUTOFF"),
            ({"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E3600", "exit_point": "E14400", "field_id": PRICE}, "TARGET_NOT_AFTER_DECISION"),
        ):
            with self.assertRaisesRegex(GroundedDiscoveryError, code):
                validate_temporal_query(episode_spec(target=target))
        future = episode_spec()
        future["features"] = future["features"] + [{"name": "fut", "op": "point_value", "field_id": PRICE, "point": "E3600"}]
        with self.assertRaisesRegex(GroundedDiscoveryError, "FEATURE_AFTER_DECISION"):
            validate_temporal_query(future)

    def test_population_anchor_and_namespace_refusals(self) -> None:
        for override, code in (
            ({"population": "BASE_X"}, "POPULATION_CONTRACT_UNKNOWN"),
            ({"anchor_kind": "BIRTH"}, "ANCHOR_KIND_UNKNOWN"),
            ({"decision": {"point_id": "Y900"}}, "POINT_NOT_IN_ALLOWLIST"),
            ({"time_contract": {"schedule_contract": "OPPORTUNITY_EPISODE_SCHEDULE_V1", "time_feature_clock": "SCHEDULED"}}, "TIME_CONTRACT_INVALID"),
        ):
            with self.assertRaisesRegex(GroundedDiscoveryError, code):
                validate_temporal_query(episode_spec(**override))
        legacy_with_e = episode_spec(schema_version="1.0", population="BASE_X", schedule={"lateness_seconds": 300})
        with self.assertRaises(GroundedDiscoveryError):
            validate_temporal_query(legacy_with_e)

    def test_wrong_binding_population_refused_before_values(self) -> None:
        census, rows = prd_vector()
        legacy_binding = binding_item(dataset_id="DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001")
        legacy_binding.pop("population")
        with self.assertRaises(GroundedDiscoveryError):
            execute_temporal_discovery(census, rows, episode_spec(), [legacy_binding])
        with self.assertRaisesRegex(GroundedDiscoveryError, "DISCOVERY_ROLE_AMBIGUOUS"):
            execute_temporal_discovery(census, rows, episode_spec(), [binding_item(), legacy_binding])


    def test_focus_population_guard_both_directions(self) -> None:
        from solana_alpha_lab.factory.hfic_ordinary_operation import (
            OrdinaryOperationError,
            require_focus_population,
        )

        episode = episode_spec()
        legacy = {**episode, "population": "BASE_X"}
        require_focus_population("OPPORTUNITY_EPISODES:Q", episode)
        require_focus_population("AUTO", legacy)
        for focus, spec in (("AUTO", episode), ("OPPORTUNITY_EPISODES:Q", legacy)):
            with self.assertRaisesRegex(OrdinaryOperationError, "FOCUS_POPULATION_MISMATCH"):
                require_focus_population(focus, spec)

    def test_mixed_schedule_clocks_refused_in_evaluator(self) -> None:
        census, rows = prd_vector()
        first = binding_item()
        second = copy.deepcopy(first)
        second["cohort_id"] = "REL-20261012T000000Z-20261013T000000Z"
        second["schedule_binding"] = {**second["schedule_binding"], "availability_grace_seconds": 600}
        with self.assertRaisesRegex(GroundedDiscoveryError, "SCHEDULE_CLOCK_MIXED"):
            execute_temporal_discovery(census, rows, episode_spec(), [first, second])


class FrozenProtectionPinTests(unittest.TestCase):
    """The admission-time assignment is the only policy a release may carry."""

    def setUp(self) -> None:
        import os

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pin = write_assignment(self.root, [])
        self.directory = self.root / oe.ASSIGNMENT_DIR
        self.path = self.directory / f"{self.pin['assignment_id']}.json"
        self.original = self.path.read_bytes()
        self.os = os

    def load(self):
        from solana_alpha_lab.factory.opportunity_episode_release import load_pinned_assignment

        return load_pinned_assignment(self.directory, self.pin)

    def refused(self, code: str) -> None:
        from solana_alpha_lab.factory.opportunity_episode_release import EpisodeReleaseError

        with self.assertRaisesRegex(EpisodeReleaseError, code):
            self.load()

    def test_exact_pin_loads_its_exact_bytes(self) -> None:
        document, raw = self.load()
        self.assertEqual(raw, self.original)
        self.assertEqual(oe.assignment_document_sha256(document), self.pin["sha256"])

    def test_missing_is_refused(self) -> None:
        self.path.unlink()
        self.refused("FROZEN_PROTECTION_MISSING")

    def test_symlink_is_refused(self) -> None:
        target = self.root / "elsewhere.json"
        target.write_bytes(self.original)
        self.path.unlink()
        try:
            self.os.symlink(target, self.path)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.refused("FROZEN_PROTECTION_MISSING")

    def test_unreadable_is_refused(self) -> None:
        self.path.write_bytes(b"{not json")
        self.refused("FROZEN_PROTECTION_UNREADABLE")

    def test_substituted_valid_assignment_is_refused(self) -> None:
        # A different but schema-valid, complete assignment under the same id.
        replacement = json.loads(self.original)
        replacement["entries"] = [
            {"identity_kind": "MINT", "identity": synth_mint("Late"), "role": "SPLIT_MEMBER", "scope": {"kind": "ALL_TIME"}}
        ]
        self.path.write_bytes(json.dumps(replacement, sort_keys=True).encode("utf-8"))
        self.refused("FROZEN_PROTECTION_HASH_MISMATCH")

    def test_wrong_identity_is_refused(self) -> None:
        other = json.loads(self.original)
        other["assignment_id"] = "ASSIGNMENT-OTHER"
        self.path.write_bytes(json.dumps(other, sort_keys=True).encode("utf-8"))
        self.pin = {"assignment_id": self.pin["assignment_id"], "sha256": oe.assignment_document_sha256(other)}
        self.refused("FROZEN_PROTECTION_IDENTITY_MISMATCH")

    def test_pins_must_be_non_empty_unique_and_well_formed(self) -> None:
        from solana_alpha_lab.factory.opportunity_episode_release import (
            EpisodeReleaseError,
            pinned_protection_sources,
        )

        good = {"assignment_id": "A", "sha256": "a" * 64}
        self.assertEqual(pinned_protection_sources([good]), [good])
        for bad in ([], [good, good], [{"assignment_id": "../A", "sha256": "a" * 64}], [{"assignment_id": "A", "sha256": "short"}]):
            with self.assertRaises(EpisodeReleaseError):
                pinned_protection_sources(bad)


class ProtectionAndFrameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.start = utc("2026-10-05T00:00:00Z")
        self.protected = synth_mint("Prot")
        self.unknown = synth_mint("Unk")
        self.interval = synth_mint("Intv")
        self.source = write_assignment(
            self.root,
            [
                {"identity_kind": "MINT", "identity": self.protected, "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}},
                {"identity_kind": "MINT", "identity": self.unknown, "role": "SPLIT_MEMBER", "scope": {"kind": "UNKNOWN"}},
                {"identity_kind": "MINT", "identity": self.interval, "role": "SPLIT_MEMBER", "scope": {"kind": "INTERVAL", "start": "2025-01-01T00:00:00Z", "end": "2025-02-01T00:00:00Z"}},
            ],
        )
        self.schedule = build_schedule(starts_at=self.start, stops_at=self.start + timedelta(days=1), assignment=self.source)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _result(self, source_id, rows, received, *, status="OBSERVED"):
        return {
            "source_id": source_id,
            "status": status,
            "body": rows,
            "response_received_at": iso(received),
            "request_started_at": iso(received - timedelta(seconds=1)),
            "first_reliable_available_at": iso(received),
            "response_sha256": "55" * 32,
            "request_sha256": "66" * 32,
            "call_occurrence_id": "77" * 32,
        }

    def test_inventory_fail_closed(self) -> None:
        good = oe.load_protection_inventory(self.root, [self.source])
        self.assertEqual(good.status, oe.ALLOW)
        for sources, reason in (
            ([], "PROTECTION_SOURCES_EMPTY"),
            ([{"assignment_id": "MISSING-SOURCE-0001", "sha256": "0" * 64}], "PROTECTION_SOURCE_MISSING"),
            ([{**self.source, "sha256": "f" * 64}], "PROTECTION_SOURCE_HASH_MISMATCH"),
        ):
            inventory = oe.load_protection_inventory(self.root, sources)
            self.assertEqual((inventory.status, inventory.reason), (oe.UNRESOLVED_SCOPE, reason))
        incomplete = write_assignment(self.root, [], complete=False)
        self.assertEqual(oe.load_protection_inventory(self.root, [incomplete]).reason, "PROTECTION_COMPLETENESS_UNPROVEN")

    def test_decisions_per_identity_and_interval(self) -> None:
        inventory = oe.load_protection_inventory(self.root, [self.source])
        window = dict(interval_start=self.start, interval_end=self.start + timedelta(days=4))
        self.assertEqual(oe.protection_decision(inventory, self.protected, **window)[0], oe.DENY_PROTECTED)
        self.assertEqual(oe.protection_decision(inventory, self.unknown, **window)[0], oe.UNRESOLVED_SCOPE)
        self.assertEqual(oe.protection_decision(inventory, self.interval, **window)[0], oe.ALLOW)
        self.assertEqual(oe.protection_decision(inventory, synth_mint("Free"), **window)[0], oe.ALLOW)
        overlapping = dict(interval_start=utc("2025-01-15T00:00:00Z"), interval_end=utc("2025-01-20T00:00:00Z"))
        self.assertEqual(oe.protection_decision(inventory, self.interval, **overlapping)[0], oe.DENY_PROTECTED)

    def test_protected_values_never_reach_value_projection(self) -> None:
        inventory = oe.load_protection_inventory(self.root, [self.source])
        allowed = synth_mint("Allowed")
        trap = token_object(self.protected, price=1.0, liquidity=10000, holders=99)
        received = self.start + timedelta(seconds=5)
        sources = [
            self._result("toporganicscore_5m", [trap, token_object(allowed, price=1.0, liquidity=10000, holders=60)], received),
            self._result("toptraded_5m", [token_object(self.unknown, price=1.0, liquidity=10000, holders=60)], received + timedelta(seconds=3)),
            self._result("toptrending_5m", [], received + timedelta(seconds=6)),
        ]
        projected: list[tuple[str, str]] = []
        real = oe.project_tokens_v2_field

        def spy(row, field_id):
            projected.append((str(row.get("id")), field_id))
            return real(row, field_id)

        with mock.patch.object(oe, "project_tokens_v2_field", side_effect=spy):
            frame = oe.build_frame(document=self.schedule, activation_id="ACT", round_started_at=self.start, source_results=sources, inventory=inventory)
        value_reads = {(mint, field) for mint, field in projected if field != oe.MINT_FIELD}
        self.assertFalse(any(mint == self.protected for mint, _field in value_reads))
        self.assertFalse(any(mint == self.unknown for mint, _field in value_reads))
        self.assertEqual(frame["counts"]["protected"], 1)
        self.assertEqual(frame["counts"]["protection_unresolved"], 1)
        self.assertEqual([item["mint"] for item in frame["candidates"]], [allowed])
        receipt = oe.frame_receipt(frame)
        encoded = json.dumps(receipt)
        self.assertNotIn(self.protected, encoded)
        self.assertNotIn(self.unknown, encoded)
        self.assertEqual(sorted(receipt["overlap"]), [allowed])
        self.assertTrue(all(item.get("object") is None or item["mint"] == allowed for item in frame["candidates"]))

    def test_dedupe_fresh_fail_and_incomplete_round(self) -> None:
        inventory = oe.load_protection_inventory(self.root, [self.source])
        mint = synth_mint("Dup")
        received = self.start + timedelta(seconds=5)
        old_pass = token_object(mint, price=1.0, liquidity=10000, holders=60)
        new_fail = token_object(mint, price=1.0, liquidity=10000, holders=10)
        sources = [
            self._result("toporganicscore_5m", [old_pass], received),
            self._result("toptraded_5m", [old_pass], received + timedelta(seconds=3)),
            self._result("toptrending_5m", [new_fail], received + timedelta(seconds=6)),
        ]
        frame = oe.build_frame(document=self.schedule, activation_id="ACT", round_started_at=self.start, source_results=sources, inventory=inventory)
        self.assertEqual(len(frame["candidates"]), 1)
        candidate = frame["candidates"][0]
        self.assertEqual((candidate["status"], candidate["reason"]), (oe.FRAME_CORE_UNUSABLE, "HOLDERS_BELOW_FLOOR"))
        self.assertEqual(candidate["selected_source_id"], "toptrending_5m")
        self.assertEqual(frame["counts"]["deduplicated"], 2)
        self.assertEqual(frame["overlap"][mint], ["toporganicscore_5m", "toptraded_5m", "toptrending_5m"])
        missing = sources[:2] + [self._result("toptrending_5m", None, received, status="MISSING_TYPED")]
        incomplete = oe.build_frame(document=self.schedule, activation_id="ACT", round_started_at=self.start, source_results=missing, inventory=inventory)
        self.assertEqual((incomplete["complete"], incomplete["terminal"], incomplete["candidates"]), (False, "ROUND_INCOMPLETE", []))
        late = sources[:2] + [self._result("toptrending_5m", [], self.start + timedelta(seconds=121))]
        outside = oe.build_frame(document=self.schedule, activation_id="ACT", round_started_at=self.start, source_results=late, inventory=inventory)
        self.assertEqual(outside["sources"][2]["status"], "OUTSIDE_ROUND")

    def test_capture_floor_and_asset_exclusion(self) -> None:
        inventory = oe.load_protection_inventory(self.root, [self.source])
        cases = {
            synth_mint("LowLiq"): (token_object(synth_mint("LowLiq"), price=1.0, liquidity=4999.99, holders=60), "LIQUIDITY_BELOW_FLOOR"),
            synth_mint("HighLiq"): (token_object(synth_mint("HighLiq"), price=1.0, liquidity=1000000.01, holders=60), "LIQUIDITY_ABOVE_CEILING"),
            synth_mint("Edge"): (token_object(synth_mint("Edge"), price=1.0, liquidity=1000000, holders=50), None),
            synth_mint("NoPrice"): (token_object(synth_mint("NoPrice"), price=None, liquidity=10000, holders=60), "FIELD-USD-PRICE-001:FIELD_ABSENT"),
            synth_mint("Stable"): (token_object(synth_mint("Stable"), price=1.0, liquidity=10000, holders=60, tags=["stablecoin"]), "EXCLUDED_TAG:stablecoin"),
        }
        received = self.start + timedelta(seconds=5)
        sources = [
            self._result("toporganicscore_5m", [row for row, _ in cases.values()], received),
            self._result("toptraded_5m", [], received + timedelta(seconds=3)),
            self._result("toptrending_5m", [], received + timedelta(seconds=6)),
        ]
        frame = oe.build_frame(document=self.schedule, activation_id="ACT", round_started_at=self.start, source_results=sources, inventory=inventory)
        by_mint = {item["mint"]: item for item in frame["candidates"]}
        for mint, (_row, reason) in cases.items():
            self.assertEqual(by_mint[mint]["reason"], reason, mint)
        self.assertEqual(by_mint[synth_mint("Edge")]["status"], oe.FRAME_PASS)


class TicketAndQuotaTests(unittest.TestCase):
    def test_round_quota_sums_without_carry(self) -> None:
        for ceiling in (1, 12, 96, 100):
            quotas = [oe.round_quota(ceiling, index) for index in range(96)]
            self.assertEqual(sum(quotas), ceiling)
            self.assertTrue(all(q in (0, 1, 2) for q in quotas))
        self.assertEqual([oe.round_quota(12, index) for index in range(8)], [0, 0, 0, 0, 0, 0, 0, 1])

    def test_tickets_stable_and_cycle_scoped(self) -> None:
        monday = utc("2026-10-05T00:00:00Z")
        self.assertEqual(oe.cycle_start(utc("2026-10-11T23:59:59Z")), monday)
        self.assertEqual(oe.cycle_start(utc("2026-10-12T00:00:00Z")), monday + timedelta(days=7))
        mint = synth_mint("Tick")
        first = oe.ticket_priority(seed="S1-SEED-VALUE", cycle=monday, mint=mint)
        self.assertEqual(first, oe.ticket_priority(seed="S1-SEED-VALUE", cycle=monday, mint=mint))
        self.assertNotEqual(first, oe.ticket_priority(seed="S1-SEED-VALUE", cycle=monday + timedelta(days=7), mint=mint))
        episode = oe.episode_id_for(lineage_id="L", cycle=monday, mint=mint)
        self.assertEqual(episode, oe.episode_id_for(lineage_id="L", cycle=monday, mint=mint))
        self.assertNotEqual(episode, oe.episode_id_for(lineage_id="L", cycle=monday + timedelta(days=7), mint=mint))
        self.assertTrue(episode.startswith("EP-") and len(episode) == 35)

    def test_selection_invariant_to_source_order_and_blocks(self) -> None:
        mints = [synth_mint(f"S{i}") for i in range(6)]
        candidates = [{"mint": m, "status": oe.FRAME_PASS} for m in mints]
        monday = utc("2026-10-05T00:00:00Z")
        a = oe.select_admissions(frame={"candidates": candidates}, seed="SEED-SEED-1", cycle=monday, quota=2, blocked_mints=[])
        b = oe.select_admissions(frame={"candidates": list(reversed(candidates))}, seed="SEED-SEED-1", cycle=monday, quota=2, blocked_mints=[])
        self.assertEqual([w["mint"] for w in a["winners"]], [w["mint"] for w in b["winners"]])
        blocked = a["winners"][0]["mint"]
        c = oe.select_admissions(frame={"candidates": candidates}, seed="SEED-SEED-1", cycle=monday, quota=1, blocked_mints=[blocked])
        self.assertEqual(c["winners"][0]["mint"], a["winners"][1]["mint"])


class LegacyInvariantTests(unittest.TestCase):
    """Pins computed on base de20465e. Episode additions change none of them."""

    def test_grounded_base_x_refuses_episode_points_and_episode_binding(self) -> None:
        from solana_alpha_lab.factory import hfic_grounded_discovery as grounded

        spec = {
            "query_id": "LEGACY_PIN",
            "decision_points": ["X300"],
            "decision_fields": ["FIELD-USD-PRICE-001"],
            "target_point": "Y1800",
            "target_field": "FIELD-USD-PRICE-001",
            "explanatory": [],
            "population": "BASE_X",
        }
        grounded.validate_query_spec(spec)
        for change in ({"decision_points": ["E300"]}, {"target_point": "E14400"}):
            with self.assertRaisesRegex(grounded.GroundedDiscoveryError, "POINT_NOT_IN_ALLOWLIST"):
                grounded.validate_query_spec({**spec, **change})
        episode_binding = [{
            "dataset_id": grounded.EPISODE_DATASET_ID, "population": grounded.EPISODE_POPULATION,
            "evidence_role": grounded.LIVE_EVIDENCE_ROLE, "holdout": False, "cohort_id": "C",
            "release_id": "R", "census_sha256": "a", "observations_sha256": "b", "schedule_binding": {},
        }]
        with self.assertRaisesRegex(grounded.GroundedDiscoveryError, "POPULATION_BINDING_MISMATCH"):
            grounded.execute_discovery_from_rows([], [], spec, episode_binding)

    def test_legacy_query_identity_and_point_grid_unchanged(self) -> None:
        import hashlib

        from tests.test_forge_composite_feature_recipes_v1 import mixed_spec
        from tests.test_hfic_temporal_discovery_v1 import COHORT as LCOHORT
        from tests.test_hfic_temporal_discovery_v1 import RELEASE as LRELEASE
        from tests.test_hfic_temporal_discovery_v1 import _bind, _simple, _spec

        self.assertEqual(validate_temporal_query(_simple())["spec_sha256"], "711d8afa1901c6b37b1a4d367667c5ab9ff9cd74a6a3369ce8811627cb15804a")
        self.assertEqual(validate_temporal_query(_spec())["spec_sha256"], "5c69e07b3aa9b71341001ba039c52b81e3de2e994af832002383c696ee612407")
        self.assertEqual(validate_temporal_query(mixed_spec())["spec_sha256"], "daea9a32edceaad22c681919f021bba37fa3d687f2f1dd1beb5f94ae296e5853")
        canonical = hashlib.sha256(json.dumps(canonical_temporal_spec(_simple()), sort_keys=True).encode()).hexdigest()
        self.assertEqual(canonical, "6cd3562206ab592653ac08d4229227063305b2177fb094ee88318033f5cd0c31")
        frozen = hashlib.sha256(json.dumps(temporal_frozen_input([_bind(LCOHORT, LRELEASE)]), sort_keys=True).encode()).hexdigest()
        self.assertEqual(frozen, "e04fbc8bed373a35cf2c7e8898f4bf766aab9ae71523a56db97601c3fd1234a3")
        self.assertEqual(
            POINT_OFFSET,
            {"X300": 300, "Y14400": 14400, "Y1800": 1800, "Y3600": 3600, "Y43200": 43200, "Y7200": 7200, "Y86400": 86400, "Y900": 900},
        )

    def test_legacy_schedule_identity_unchanged(self) -> None:
        from scripts.observation_runtime_composition_parity import build_parity_schedule
        from solana_alpha_lab.factory.observation_schedule import schedule_sha256

        digest = schedule_sha256(build_parity_schedule(starts_at=utc("2026-09-03T12:00:00Z")))
        self.assertEqual(digest, "adf39bffd9dd846e2f27b4c42a57851a73da9c42b6e2c02a24b01c00036f616c")

    def test_episode_schedule_is_not_a_legacy_document(self) -> None:
        from solana_alpha_lab.factory.observation_schedule import ObservationScheduleError, validate_schedule_semantics

        with tempfile.TemporaryDirectory() as raw:
            source = write_assignment(Path(raw), [])
            schedule = build_schedule(starts_at=utc("2026-10-05T00:00:00Z"), stops_at=utc("2026-10-06T00:00:00Z"), assignment=source)
        self.assertEqual(schedule["schema"], "smial.opportunity-episode-schedule")
        with self.assertRaises((KeyError, ObservationScheduleError)):
            validate_schedule_semantics(schedule)
        for key in ("x_point", "y_points", "source_poll"):
            self.assertNotIn(key, schedule)

    def test_template_is_not_activatable_without_commissioning(self) -> None:
        import yaml

        document = yaml.safe_load((ROOT / "configs/opportunity_episodes_jupiter_core_v1.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as raw:
            inventory = oe.load_protection_inventory(Path(raw), document["protection"]["assignment_sources"])
        self.assertEqual(inventory.status, oe.UNRESOLVED_SCOPE)
        self.assertGreater(utc(document["activation"]["starts_at"]), utc("2099-01-01T00:00:00Z"))


if __name__ == "__main__":
    unittest.main()
