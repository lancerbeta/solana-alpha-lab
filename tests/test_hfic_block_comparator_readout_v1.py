"""Block-local matched/comparator pairs on the native episode executor.

The oracle is hand arithmetic over a two-day fixture, independent of the
implementation: the pooled comparison and each day's comparison point in
opposite directions because the groups are weighted differently per day.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from solana_alpha_lab.factory import hfic_research_scope as rs  # noqa: E402
from solana_alpha_lab.factory import hfic_temporal_discovery as temporal  # noqa: E402
from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    block_comparator_readout,
    descriptive_return_readout,
    format_discovery_readout,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    execute_temporal_discovery,
    temporal_result_coherence,
    validate_temporal_query,
)
from tests.test_hfic_list_scope_executor_v1 import ALIASES, NUMERIC, SCHEDULE, spec  # noqa: E402
from tests.test_opportunity_episodes_contract_v1 import (  # noqa: E402
    COHORT,
    HOLD,
    LIQ,
    PRICE,
    RELEASE,
    binding_item,
    obs_row,
)

A, B = "JUPITER:toporganicscore:5m", "JUPITER:toptraded:5m"
LIST_OF = {"A": A, "B": B}
# episode -> (list letter, holders rise, target return or None, day offset)
TWO_DAYS = {
    "m1": ("A", True, 0.10, 0),
    "n1": ("B", False, 0.08, 0),
    "n2": ("B", False, 0.08, 0),
    "n3": ("B", False, 0.08, 0),
    "m2": ("A", True, -0.10, 1),
    "m3": ("A", True, -0.10, 1),
    "m4": ("A", True, -0.10, 1),
    "n4": ("B", False, -0.12, 1),
}
BASE_DAY = datetime(2026, 10, 5, tzinfo=UTC)


def _stamp(day: int, clock: str) -> str:
    moment = BASE_DAY + timedelta(days=day)
    hours, minutes, seconds = (int(part) for part in clock.split(":"))
    return (moment + timedelta(hours=hours, minutes=minutes, seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def corpus(fixture, *, drop_e300_holders=()):
    census, rows = [], []
    for episode, (_letter, signal, target, day) in fixture.items():
        mint = f"Mint{episode}".ljust(40, "x")
        census.append({"cohort_id": COHORT, "release_id": RELEASE, "episode_id": episode, "mint": mint, "t0": _stamp(day, "00:02:10")})
        before, after = (60, 75) if signal else (60, 55)
        for point, clock, price, holders in (
            ("E300", "00:10:04", 1.0, before),
            ("E1800", "00:35:09", 1.0, after),
            ("E14400", "04:05:08", None if target is None else 1.0 + target, 80),
        ):
            available = _stamp(day, clock)
            for field, value in ((PRICE, price), (HOLD, holders), (LIQ, 12000)):
                if point == "E14400" and target is None:
                    rows.append(obs_row(episode, mint, point, field, None, available=_stamp(day, "04:10:00"), state="CENSORED"))
                elif point == "E300" and field == HOLD and episode in drop_e300_holders:
                    rows.append(obs_row(episode, mint, point, field, None, available=available, state="MISSING_TYPED"))
                else:
                    rows.append(obs_row(episode, mint, point, field, value, available=available))
    return census, rows


def evidence(fixture):
    ev = rs.MembershipEvidence()
    for definition in rs.jupiter_definitions(SCHEDULE).values():
        ev.add_definition(definition)
    for episode, (letter, _signal, _target, day) in fixture.items():
        ev.states[episode] = {
            LIST_OF["A"]: rs.TRUE if letter == "A" else rs.FALSE,
            LIST_OF["B"]: rs.TRUE if letter == "B" else rs.FALSE,
            "JUPITER:toptrending:5m": rs.FALSE,
        }
        ev.t0[episode] = datetime.fromisoformat(_stamp(day, "00:02:10").replace("Z", "+00:00"))
    ev.bindings.append({"adapter": "TEST", "note": "direct-level fixture"})
    return ev


def run(draft, fixture=TWO_DAYS, **corpus_options):
    ev = evidence(fixture)
    draft = dict(draft, list_aliases={"A": A, "B": B, "C": "JUPITER:toptrending:5m"})
    query = rs.canonicalize_query_scope(draft, ev)
    bound = validate_temporal_query(query)["scientific_body"]
    census, rows = corpus(fixture, **corpus_options)
    resolved = rs.ResolvedScope(
        scope=bound["research_scope"],
        list_condition=bound.get("list_condition"),
        evidence=ev,
        episode_ids=[row["episode_id"] for row in census],
        slices=bound.get("diagnostic_slices") or [],
    )
    return execute_temporal_discovery(census, rows, query, [binding_item()], research_scope=resolved)["summary"]


NUMERIC_DRAFT = spec("NUMERIC_IN_SCOPE", **NUMERIC)
LIST_DRAFT = spec("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A"]}]})
DAY1, DAY2 = "2026-10-05", "2026-10-06"


def by_view(rows):
    return {row["view"]: row for row in rows}


class HandOracleTests(unittest.TestCase):
    def test_baseline_pairs_point_the_opposite_way_to_the_pooled_comparison(self) -> None:
        out = run(NUMERIC_DRAFT)
        # Pooled: matched mean -0.05 against a baseline of -0.01.
        self.assertAlmostEqual(out["mean_target"], -0.05, places=9)
        self.assertAlmostEqual(out["baseline"]["mean_target"], -0.01, places=9)
        block = out["block_comparator"]
        self.assertEqual(block["reference_kind"], "SAME_DECISION_ELIGIBLE")
        self.assertTrue(block["reference_includes_matched"])
        days = by_view(block["by_calendar_block"])
        d1, d2 = days[DAY1], days[DAY2]
        self.assertEqual((d1["matched"]["observed_n"], d1["reference"]["observed_n"]), (1, 4))
        self.assertAlmostEqual(d1["matched"]["mean_target"], 0.10, places=9)
        self.assertAlmostEqual(d1["reference"]["mean_target"], 0.085, places=9)
        self.assertAlmostEqual(d1["matched_minus_reference_mean"], 0.015, places=9)
        self.assertEqual((d2["matched"]["observed_n"], d2["reference"]["observed_n"]), (3, 4))
        self.assertAlmostEqual(d2["matched"]["mean_target"], -0.10, places=9)
        self.assertAlmostEqual(d2["reference"]["mean_target"], -0.105, places=9)
        self.assertAlmostEqual(d2["matched_minus_reference_mean"], 0.005, places=9)
        # Pooled relative sign (-0.04) is opposite to both block-local signs (+0.015, +0.005).
        self.assertLess(out["mean_target"] - out["baseline"]["mean_target"], 0)
        self.assertGreater(d1["matched_minus_reference_mean"], 0)
        self.assertGreater(d2["matched_minus_reference_mean"], 0)
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")
        # Each side's own downside profile; never the pooled one.
        self.assertEqual(d2["matched"]["downside"]["le_minus_20_n"], 0)
        self.assertAlmostEqual(d2["reference"]["downside"]["negative_mass"], 0.42, places=9)

    def test_complement_pairs_are_not_the_baseline(self) -> None:
        out = run(LIST_DRAFT)
        block = out["block_comparator"]
        self.assertEqual(block["reference_kind"], "MATCHED_VS_ELIGIBLE_COMPLEMENT")
        self.assertFalse(block["reference_includes_matched"])
        days = by_view(block["by_calendar_block"])
        self.assertEqual((days[DAY1]["reference"]["eligible_n"], days[DAY2]["reference"]["eligible_n"]), (3, 1))
        self.assertAlmostEqual(days[DAY1]["reference"]["mean_target"], 0.08, places=9)
        self.assertAlmostEqual(days[DAY2]["reference"]["mean_target"], -0.12, places=9)
        self.assertAlmostEqual(days[DAY1]["matched_minus_reference_mean"], 0.02, places=9)
        self.assertAlmostEqual(days[DAY2]["matched_minus_reference_mean"], 0.02, places=9)
        # Pooled complement difference is -0.08 while every block-local difference is +0.02.
        contrast = out["research_scope"]["contrast"]
        self.assertAlmostEqual(contrast["observed_target_difference"], -0.08, places=9)
        # The pooled baseline includes matched; the pair reference does not.
        self.assertEqual(out["baseline"]["observed_n"], 8)
        self.assertEqual(sum(row["reference"]["observed_n"] for row in block["by_calendar_block"]), 4)
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")

    def test_scalar_aggregates_and_version(self) -> None:
        out = run(NUMERIC_DRAFT)
        self.assertEqual(out["calculation_version"], temporal.TEMPORAL_CALCULATION_VERSION_EPISODES_V4)
        self.assertIn(temporal.TEMPORAL_CALCULATION_VERSION_EPISODES_V4, temporal.TEMPORAL_CURRENT_CALCULATION_VERSIONS)
        self.assertIn(temporal.TEMPORAL_CALCULATION_VERSION_EPISODES_V3, temporal.TEMPORAL_CURRENT_CALCULATION_VERSIONS)
        self.assertEqual((out["matched_n"], out["observed_target_n"], out["missing_target_n"]), (4, 4, 0))
        self.assertEqual(out["block_count"], 2)
        # The saved matched-block count and rows are not redefined by the pairs.
        self.assertEqual([row["view"] for row in out["by_calendar_block"]], [DAY1, DAY2])


class BoundaryTests(unittest.TestCase):
    def test_day_without_matched_and_day_without_reference_are_typed_not_zero(self) -> None:
        fixture = dict(TWO_DAYS)
        fixture["n5"] = ("B", False, 0.03, 2)  # a third day with nobody matched
        out = run(NUMERIC_DRAFT, fixture)
        day3 = by_view(out["block_comparator"]["by_calendar_block"])["2026-10-07"]
        self.assertEqual(day3["comparison_state"], "EMPTY_MATCHED")
        self.assertEqual(day3["matched"]["eligible_n"], 0)
        self.assertIsNone(day3["matched"]["mean_target"])
        self.assertIsNone(day3["matched_minus_reference_mean"])
        self.assertEqual(day3["reference"]["observed_n"], 1)
        # The saved matched-block rows and block_count still count only matched days.
        self.assertEqual(out["block_count"], 2)
        self.assertNotIn("2026-10-07", [row["view"] for row in out["by_calendar_block"]])
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")
        # Under a complement, a day where everyone is matched has an empty reference.
        fixture = dict(TWO_DAYS)
        fixture["m5"] = ("A", True, 0.02, 2)
        out = run(LIST_DRAFT, fixture)
        day3 = by_view(out["block_comparator"]["by_calendar_block"])["2026-10-07"]
        self.assertEqual(day3["comparison_state"], "EMPTY_REFERENCE")
        self.assertEqual(day3["reference"]["eligible_n"], 0)
        self.assertIsNone(day3["reference"]["mean_target"])
        self.assertIsNone(day3["matched_minus_reference_mean"])
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")

    def test_missing_target_is_a_count_not_a_zero_on_both_sides(self) -> None:
        fixture = dict(TWO_DAYS)
        fixture["m5"] = ("A", True, None, 0)  # matched, exit censored
        fixture["n5"] = ("B", False, None, 0)  # unmatched, exit censored
        out = run(NUMERIC_DRAFT, fixture)
        d1 = by_view(out["block_comparator"]["by_calendar_block"])[DAY1]
        self.assertEqual((d1["matched"]["eligible_n"], d1["matched"]["observed_n"], d1["matched"]["missing_n"]), (2, 1, 1))
        self.assertEqual((d1["reference"]["eligible_n"], d1["reference"]["observed_n"], d1["reference"]["missing_n"]), (6, 4, 2))
        self.assertAlmostEqual(d1["matched"]["mean_target"], 0.10, places=9)
        self.assertAlmostEqual(d1["reference"]["mean_target"], 0.085, places=9)
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")

    def test_feature_unknown_stays_in_the_native_reference(self) -> None:
        out = run(NUMERIC_DRAFT, drop_e300_holders=("n1",))
        self.assertEqual(out["feature_unknown_n"], 1)
        d1 = by_view(out["block_comparator"]["by_calendar_block"])[DAY1]
        # n1 is decision-eligible with an unknown feature: not matched, still in the baseline reference.
        self.assertEqual(d1["matched"]["eligible_n"], 1)
        self.assertEqual(d1["reference"]["eligible_n"], 4)
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")

    def test_cohort_pairs_follow_the_saved_cohort_rows(self) -> None:
        out = run(NUMERIC_DRAFT)
        cohorts = out["block_comparator"]["by_cohort"]
        self.assertEqual([row["view"] for row in cohorts], [COHORT])
        row = cohorts[0]
        self.assertEqual(row["shared_decision_n"], 0)
        self.assertFalse(out["block_comparator"]["cohort_rows_overlap"])
        saved = out["by_cohort"][0]
        self.assertEqual(row["matched"]["observed_n"], saved["observed_target_n"])
        self.assertAlmostEqual(row["matched"]["mean_target"], saved["mean_target"], places=12)
        self.assertEqual(row["reference"]["eligible_n"], saved["decision_eligible_n"])

    def test_a_contradicting_pair_is_incoherent(self) -> None:
        out = run(NUMERIC_DRAFT)
        for mutate in (
            lambda b: b["by_calendar_block"][0]["reference"].__setitem__("observed_n", 3),
            lambda b: b["by_calendar_block"][0]["matched"].__setitem__("mean_target", 0.5),
            lambda b: b["by_calendar_block"][1].__setitem__("matched_minus_reference_mean", 0.4),
            lambda b: b["by_calendar_block"][1].__setitem__("comparison_state", "EMPTY_BOTH"),
            lambda b: b["by_cohort"][0]["reference"].__setitem__("eligible_n", 7),
            lambda b: b.__setitem__("reference_kind", "MATCHED_VS_ELIGIBLE_COMPLEMENT"),
            lambda b: b["by_calendar_block"].pop(),
        ):
            broken = copy.deepcopy(out)
            mutate(broken["block_comparator"])
            self.assertEqual(temporal_result_coherence(broken)["status"], "INCOHERENT", mutate)
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")

    def test_older_version_result_without_the_block_stays_coherent_and_unprojected(self) -> None:
        out = run(NUMERIC_DRAFT)
        legacy = {k: v for k, v in out.items() if k != "block_comparator"}
        legacy["calculation_version"] = temporal.TEMPORAL_CALCULATION_VERSION_EPISODES_V3
        self.assertEqual(temporal_result_coherence(legacy)["status"], "COHERENT")
        self.assertNotIn("block_comparator", descriptive_return_readout(legacy))

    def test_inclusive_reference_without_unmatched_observation_is_not_zero_difference(self) -> None:
        fixture = dict(TWO_DAYS)
        fixture["m6"] = ("A", True, 0.30, 2)  # the only eligible member of day 3 is matched
        out = run(NUMERIC_DRAFT, fixture)
        day3 = by_view(out["block_comparator"]["by_calendar_block"])["2026-10-07"]
        self.assertEqual(day3["comparison_state"], "NO_UNMATCHED_OBSERVED")
        self.assertEqual(day3["matched"]["observed_n"], day3["reference"]["observed_n"])
        self.assertIsNone(day3["matched_minus_reference_mean"])
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")
        # Under a complement the same day has no reference at all.
        out = run(LIST_DRAFT, fixture)
        self.assertEqual(by_view(out["block_comparator"]["by_calendar_block"])["2026-10-07"]["comparison_state"], "EMPTY_REFERENCE")

    def test_integrity_excluded_member_never_enters_a_block_group(self) -> None:
        """Defensive: the executor already drops excluded members from decision_members."""

        injected = {
            "block": "2026-10-05", "matched": True, "target": 0.5, "target_is_observed": True,
            "integrity_excluded": True, "decision_eligible": False,
        }
        kept = {"block": "2026-10-05", "matched": True, "target": 0.1, "target_is_observed": True}
        out = temporal.block_comparator_summary([injected, kept], {}, [], contrast=None, calendar_key="UTC_DAY_OF_DECISION")
        pair = out["by_calendar_block"][0]
        self.assertEqual((pair["matched"]["eligible_n"], pair["reference"]["eligible_n"]), (1, 1))
        self.assertEqual(pair["comparison_state"], "NO_UNMATCHED_OBSERVED")

    def test_shared_decisions_are_counted_by_one_helper_for_rows_and_pairs(self) -> None:
        """The episode path never seats a decision in two cohorts, so exercise the shared branch on the seats directly."""

        def seat(target, matched=True):
            return {
                "in_base": True, "decision_eligible": True, "matched": matched, "target_is_observed": True,
                "target": target, "feature_unknown": False, "exclusion": None, "integrity_excluded": False,
            }

        slots = {
            "C1": {("m", "d1"): seat(0.1), ("n", "d1"): seat(0.2, matched=False)},
            "C2": {("m", "d1"): seat(0.1), ("p", "d2"): seat(0.3, matched=False)},
        }
        rows = temporal._cohort_rows(slots, ["C1", "C2"])
        pairs = temporal.block_comparator_summary([], slots, ["C1", "C2"], contrast=None, calendar_key="UTC_DAY_OF_DECISION")
        self.assertEqual([row["shared_decision_n"] for row in rows], [1, 1])
        self.assertEqual([row["shared_decision_n"] for row in pairs["by_cohort"]], [1, 1])
        self.assertTrue(pairs["cohort_rows_overlap"])
        # A legitimately overlapping result: saved rows and pairs agree, so no false INCOHERENT.
        summary = {
            "calculation_version": temporal.TEMPORAL_CALCULATION_VERSION_EPISODES_V4,
            "by_cohort": rows, "block_comparator": pairs, "by_calendar_block": [],
        }
        self.assertEqual([i for i in temporal._block_comparator_issues(summary) if "shared" in i["field"] or "overlap" in i["field"]], [])

    def test_contrast_kinds_follow_the_scope_owner_and_mixed_kind_is_coherent(self) -> None:
        self.assertEqual(temporal._BLOCK_REFERENCE_KINDS, rs.CONTRAST_KINDS | {"SAME_DECISION_ELIGIBLE"})
        mixed = spec("MIXED_LIST_NUMERIC", list_condition={"clauses": [{"all_of": ["A"]}]}, **NUMERIC)
        out = run(mixed)
        self.assertEqual(out["research_scope"]["contrast"]["kind"], "MATCHED_VS_DECISION_ELIGIBLE")
        self.assertEqual(out["block_comparator"]["reference_kind"], "MATCHED_VS_DECISION_ELIGIBLE")
        self.assertTrue(out["block_comparator"]["reference_includes_matched"])
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")

    def test_same_query_retry_of_a_saved_v3_look_is_not_a_new_look(self) -> None:
        query = rs.canonicalize_query_scope(
            dict(NUMERIC_DRAFT, list_aliases={"A": A, "B": B, "C": "JUPITER:toptrending:5m"}), evidence(TWO_DAYS)
        )
        saved = {
            "spec_sha256": validate_temporal_query(query)["spec_sha256"], "look_class": "MAIN", "new_look": True,
            "search_tier": "COMPOUND_SCREEN", "calculation_version": temporal.TEMPORAL_CALCULATION_VERSION_EPISODES_V3,
        }
        decision = temporal.classify_temporal_look([saved], query)
        self.assertEqual((decision["look_class"], decision["new_look"]), ("RETRY_SAME_BYTES", False))

    def test_integrity_conflict_leaves_both_paths_on_the_same_population(self) -> None:
        import copy as _copy

        c2, r2 = "REL-20261006T000000Z-20261007T000000Z", "cd" * 32
        ev = evidence(TWO_DAYS)
        draft = dict(NUMERIC_DRAFT, list_aliases={"A": A, "B": B, "C": "JUPITER:toptrending:5m"})
        query = rs.canonicalize_query_scope(draft, ev)
        bound = validate_temporal_query(query)["scientific_body"]
        census, rows = corpus(TWO_DAYS)
        census.append(dict(census[0], cohort_id=c2, release_id=r2))
        for row in [x for x in rows if x["episode_id"] == "m1"]:
            copy_row = dict(row, cohort_id=c2, release_id=r2)
            if copy_row["point_id"] == "E1800" and copy_row["field_id"] == PRICE:
                copy_row["typed_value"] = "1.5"  # the second delivery disagrees: INTEGRITY_CONFLICT
            rows.append(copy_row)
        resolved = rs.ResolvedScope(
            scope=bound["research_scope"], list_condition=bound.get("list_condition"), evidence=ev,
            episode_ids=[x["episode_id"] for x in census], slices=[],
        )
        out = execute_temporal_discovery(
            census, rows, query, [binding_item(), binding_item(cohort_id=c2, release_id=r2)], research_scope=resolved
        )["summary"]
        self.assertEqual(out["integrity_conflict_count"], 1)
        self.assertEqual((out["decision_eligible_n"], out["matched_n"]), (7, 3))
        block = out["block_comparator"]
        day1 = by_view(block["by_calendar_block"])[DAY1]
        # The excluded decision is gone from the matched AND the reference side of its day.
        self.assertEqual((day1["matched"]["eligible_n"], day1["reference"]["eligible_n"]), (0, 3))
        self.assertEqual(block["by_cohort"][0]["reference"]["eligible_n"], 7)
        self.assertEqual(sum(r["reference"]["observed_n"] for r in block["by_calendar_block"]), out["baseline"]["observed_n"])
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")
        broken = _copy.deepcopy(out)
        broken["block_comparator"]["by_calendar_block"][0]["reference"]["eligible_n"] = 4
        broken["block_comparator"]["by_calendar_block"][0]["reference"]["missing_n"] = 1
        self.assertEqual(temporal_result_coherence(broken)["status"], "INCOHERENT")

    def test_complement_kind_and_overlap_mutations_are_incoherent(self) -> None:
        out = run(LIST_DRAFT)
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")
        for mutate in (
            lambda r: r["block_comparator"]["by_calendar_block"][0]["reference"].__setitem__("observed_n", 5),
            lambda r: r["block_comparator"]["by_calendar_block"][1].__setitem__("matched_minus_reference_mean", 0.9),
            lambda r: r["block_comparator"].__setitem__("reference_kind", "MATCHED_VS_DECISION_ELIGIBLE"),
            lambda r: r["block_comparator"]["by_cohort"][0].__setitem__("shared_decision_n", 1),
            lambda r: r["block_comparator"].__setitem__("cohort_rows_overlap", True),
            lambda r: r.pop("research_scope"),
            lambda r: r.pop("block_comparator"),
        ):
            broken = copy.deepcopy(out)
            mutate(broken)
            self.assertEqual(temporal_result_coherence(broken)["status"], "INCOHERENT", mutate)
        numeric = run(NUMERIC_DRAFT)
        wrong_kind = copy.deepcopy(numeric)
        wrong_kind["block_comparator"]["reference_kind"] = "MATCHED_VS_DECISION_ELIGIBLE"
        self.assertEqual(temporal_result_coherence(wrong_kind)["status"], "INCOHERENT")
        with self.assertRaises(Exception) as caught:
            temporal.block_comparator_summary([], {}, [], contrast="SOMETHING_ELSE", calendar_key="UTC_DAY_OF_DECISION")
        self.assertEqual(getattr(caught.exception, "code", None), "BLOCK_COMPARATOR_CONTRAST_UNSUPPORTED")


class ConsumerPathTests(unittest.TestCase):
    def test_compact_readout_keeps_pairs_together_and_honest_truncation(self) -> None:
        fixture = dict(TWO_DAYS)
        for index in range(5):
            fixture[f"x{index}"] = ("B", False, 0.01, 2 + index)
        out = run(NUMERIC_DRAFT, fixture)
        readout = descriptive_return_readout(out)
        compact = readout["block_comparator"]
        rows = compact["details"]["by_calendar_block"]
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertIn("matched", row)
            self.assertIn("reference", row)
        truncation = compact["detail_truncation"]["by_calendar_block"]
        self.assertEqual(truncation["total"], 7)
        self.assertEqual((truncation["included"], truncation["truncated"]), (4, True))
        self.assertEqual(truncation["comparison_states"], {"EMPTY_MATCHED": 5, "EVALUATED": 2})
        self.assertEqual(len(out["block_comparator"]["by_calendar_block"]), 7)
        self.assertIn("discovery-show", compact["full_detail"])
        # Same rows as the saved result, in the same canonical order (prefix), compact downside subset.
        saved = out["block_comparator"]["by_calendar_block"][:4]
        self.assertEqual([row["view"] for row in rows], [row["view"] for row in saved])
        for compact_row, saved_row in zip(rows, saved):
            for side in ("matched", "reference"):
                self.assertEqual(compact_row[side]["observed_n"], saved_row[side]["observed_n"])
                self.assertEqual(compact_row[side]["mean_target"], saved_row[side]["mean_target"])
                self.assertEqual(compact_row[side]["downside"]["le_minus_20_n"], saved_row[side]["downside"]["le_minus_20_n"])
                self.assertEqual(compact_row[side]["downside"]["es10_return"], saved_row[side]["downside"]["es10_return"])
                self.assertNotIn("p05", compact_row[side]["downside"])
            self.assertEqual(compact_row["matched_minus_reference_mean"], saved_row["matched_minus_reference_mean"])
        self.assertIn("FULL_PROFILE_IN_SAVED_RESULT", compact["downside_projection"])
        self.assertEqual(block_comparator_readout(out["block_comparator"])["details"], compact["details"])

    def test_full_size_compact_readout_stays_bounded(self) -> None:
        fixture = dict(TWO_DAYS)
        for index in range(6):
            fixture[f"y{index}"] = ("A", True, 0.05 * (index - 2), 2 + index)
            fixture[f"z{index}"] = ("B", False, -0.02 * index, 2 + index)
        out = run(NUMERIC_DRAFT, fixture)
        self.assertEqual(len(out["block_comparator"]["by_calendar_block"]), 8)
        compact = descriptive_return_readout(out)["block_comparator"]
        self.assertEqual(compact["detail_truncation"]["by_calendar_block"]["included"], 4)
        # 4 day pairs + 1 cohort pair, each with two compact sides.
        self.assertLess(len(json.dumps(compact, sort_keys=True)), 9000)
        self.assertLess(len(json.dumps(out["block_comparator"], sort_keys=True)), 30000)

    def test_owner_readout_and_fragment_summary_carry_the_block(self) -> None:
        from solana_alpha_lab.factory.research_fragments import _summary

        out = run(NUMERIC_DRAFT)
        evidence_view = format_discovery_readout({"result": out, "result_refs": ["X"], "calculation_version": out["calculation_version"]})
        self.assertEqual(evidence_view["block_comparator"], out["block_comparator"])
        self.assertIn("block_comparator", evidence_view["descriptive_readout"])
        summary = _summary(out)
        self.assertEqual(summary["block_comparator"], descriptive_return_readout(out)["block_comparator"])
        self.assertLess(len(json.dumps(summary["block_comparator"], sort_keys=True)), 6000)

    def test_older_results_are_byte_identical_through_every_consumer(self) -> None:
        from solana_alpha_lab.factory.hfic_discovery_detail import _block_comparator_detail
        from solana_alpha_lab.factory.research_fragments import _summary

        legacy_path = ROOT / "tests/fixtures/forge_native_lifecycle_closure_v1/legacy-unscoped-episode-result-v1.json"
        legacy = json.loads(legacy_path.read_bytes())
        before = json.dumps(legacy, sort_keys=True)
        readout = descriptive_return_readout(legacy)
        self.assertNotIn("block_comparator", readout)
        self.assertNotIn("block_comparator", _summary(legacy))
        self.assertNotIn("block_comparator", format_discovery_readout({"result": legacy, "result_refs": ["X"]}))
        self.assertEqual(json.dumps(legacy, sort_keys=True), before)
        self.assertEqual(temporal_result_coherence(legacy)["status"], "COHERENT")
        # The runtime hint is separate from every hashed capsule.
        self.assertEqual(
            _block_comparator_detail({"result": legacy}),
            {"block_comparator_status": "NOT_SAVED_BY_THIS_CALCULATION_VERSION"},
        )
        v4_without_block = {k: v for k, v in run(NUMERIC_DRAFT).items() if k != "block_comparator"}
        self.assertEqual(_block_comparator_detail({"result": v4_without_block})["block_comparator_status"], "MISSING_IN_BLOCK_VERSION")
        v3_like = dict(v4_without_block, calculation_version=temporal.TEMPORAL_CALCULATION_VERSION_EPISODES_V3)
        v3_like.pop("population")
        self.assertEqual(_block_comparator_detail({"result": v3_like})["block_comparator_status"], "NOT_SAVED_BY_THIS_CALCULATION_VERSION")
        fresh_result = run(NUMERIC_DRAFT)
        fresh = _block_comparator_detail({"result": fresh_result})
        self.assertEqual(fresh["block_comparator_status"], "SAVED")
        self.assertEqual(len(fresh["block_comparator"]["by_calendar_block"]), 2)
        self.assertIsNot(fresh["block_comparator"]["by_calendar_block"], fresh_result["block_comparator"]["by_calendar_block"])
        self.assertEqual(_block_comparator_detail({"result": dict(fresh_result, population="BASE_X", block_comparator=None, calculation_version=temporal.TEMPORAL_CALCULATION_VERSION_V5)})["block_comparator_status"], "NOT_APPLICABLE_NON_EPISODE")
        self.assertEqual(_block_comparator_detail({"result": dict(fresh_result, block_comparator="x")})["block_comparator_status"], "INVALID")
        self.assertEqual(_block_comparator_detail({})["block_comparator_status"], "NO_RESULT")


if __name__ == "__main__":
    unittest.main()
