"""Conditional temporal views read one sample; a wrong saved look is revised, not re-spent.

No live store and no provider. The critic in the candidate branch is scripted
mechanical input, marked SCRIPTED_CRITIC_MECHANICAL; it is not a scientific PASS.
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory import hfic_temporal_discovery as temporal  # noqa: E402
from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    LIQUIDITY,
    PRICE,
    GroundedDiscoveryError,
    format_discovery_readout,
    list_discovery_looks,
    load_admitted_partition_rows,
    resolve_published_discovery_binding,
    result_sha256,
    run_recorded_discovery_query,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    TEMPORAL_CALCULATION_VERSION,
    TEMPORAL_CALCULATION_VERSION_V3,
    assess_tier_progress,
    execute_temporal_discovery,
    temporal_result_coherence,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    cohort_id_for_admission,
    import_live_cohort,
    seal_live_cohort,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_hfic_temporal_discovery_v1 import (  # noqa: E402
    ANCHOR,
    COHORT,
    COHORT_B,
    COHORT_C,
    COHORT_EMPTY,
    RELEASE,
    RELEASE_B,
    RELEASE_C,
    RELEASE_EMPTY,
    _bind,
    _census,
    _move,
    _obs,
    _spec,
)
from tests.test_hfic_temporal_production_runner_v1 import (  # noqa: E402
    DOCUMENT_LATENESS,
    OFFSETS,
    _schedule,
)
from tests.test_live_cohort_discovery_release_series import (  # noqa: E402
    ACTIVATION,
    CAMPAIGN_STARTS,
    CAMPAIGN_STOPS,
    PRODUCER,
    _member,
)
from tests.test_live_cohort_discovery_release_series import _obs as _series_obs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GIT_SHA = "ef" * 20
POINTS = ("X300", "Y900", "Y1800", "Y3600")


def _v3_cohort_rows(slots, admitted_ids):
    """HFIC_TEMPORAL_DISCOVERY_CALC_V3 ``_cohort_rows`` at 6b11fb78, verbatim.

    The old writer: observed is taken from every active seat, matched or not.
    """

    owners = defaultdict(set)
    for cohort_id, bucket in slots.items():
        for identity, view in bucket.items():
            if view.get("integrity_excluded"):
                continue
            owners[identity].add(cohort_id)
    rows = []
    for cohort_id in admitted_ids:
        bucket = slots.get(cohort_id, {})
        views = list(bucket.values())
        active = [item for item in views if not item.get("integrity_excluded")]
        observed = [
            float(item["target"])
            for item in active
            if item.get("target_is_observed") and item.get("target") is not None
        ]
        matched = [item for item in active if item.get("matched")]
        missing = [item for item in matched if not item.get("target_is_observed")]
        exclusions = defaultdict(int)
        for item in views:
            if item.get("integrity_excluded"):
                exclusions["INTEGRITY_CONFLICT"] += 1
                continue
            reason = item.get("exclusion")
            if isinstance(reason, str) and reason:
                exclusions[reason] += 1
        shared = sum(
            1
            for identity, view in bucket.items()
            if not view.get("integrity_excluded") and len(owners.get(identity, ())) > 1
        )
        target_exclusions = defaultdict(int)
        for item in matched:
            reason = item.get("target_exclusion")
            if isinstance(reason, str) and reason and not item.get("target_is_observed"):
                target_exclusions[reason] += 1
        rows.append(
            {
                "view": cohort_id,
                "cohort_id": cohort_id,
                "population_n": sum(1 for item in active if item.get("in_base")),
                "base_x_n": sum(1 for item in active if item.get("in_base")),
                "decision_eligible_n": sum(1 for item in active if item.get("decision_eligible")),
                "matched_n": len(matched),
                "observed_target_n": len(observed),
                "missing_target_n": len(missing),
                "feature_unknown_n": sum(1 for item in active if item.get("feature_unknown")),
                "denominator_base_x": sum(1 for item in active if item.get("in_base")),
                "feature_admissible": sum(1 for item in active if item.get("decision_eligible")),
                "target_observed_after_decision": len(observed),
                "mean_target": temporal._mean(observed),
                "mean_target_kind": "PRICE_RELATIVE_PROXY",
                "exclusion_reasons": dict(sorted(exclusions.items())),
                "target_exclusion_reasons": dict(sorted(target_exclusions.items())),
                "independent_replication": False,
                "shared_decision_n": shared,
                "membership": "DESCRIPTIVE_NOT_INDEPENDENT",
            }
        )
    return rows


def old_writer():
    """Run the real pipeline with the V3 cohort aggregation and V3 stamp.

    The V3 code had no coherence guard, so it is off for this writer only.
    """

    return mock.patch.multiple(
        temporal,
        _cohort_rows=_v3_cohort_rows,
        TEMPORAL_CALCULATION_VERSION=TEMPORAL_CALCULATION_VERSION_V3,
        require_coherent_temporal_result=lambda summary: None,
    )


# --- in-memory fixture on the unit binder -------------------------------------------------

FEATURE_POINT = "Y1800"


def _query(query_id: str = "coherence-simple", threshold: float = 1.1) -> dict:
    """Decision Y3600; predicate on the Y1800 mark; target Y3600 -> Y7200."""

    return _spec(
        "SIMPLE_SCREEN",
        query_id=query_id,
        features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": FEATURE_POINT}],
        all=[{"feature": "mark", "op": "gte", "value": threshold}],
        cost_profile=None,
    )


def _stamp(anchor, point: str) -> str:
    return (anchor + timedelta(seconds=OFFSETS[point] + 300)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _member_rows(
    mint: str,
    cohort: str,
    release: str,
    *,
    mark: float | None,
    exit_price: float | None,
    anchor=ANCHOR,
    reference: float = 1.0,
) -> tuple[dict, list[dict]]:
    """One decision. mark=None leaves the feature unknown; exit=None leaves the target missing."""

    census = _move(_census(mint), cohort, release)
    census["authoritative_anchor"] = anchor.strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [_move(_obs(mint, "X300", LIQUIDITY, 1000.0, at=_stamp(anchor, "X300")), cohort, release)]
    prices = {"X300": 1.0, "Y900": 1.0, "Y1800": mark, "Y3600": reference}
    for point in POINTS:
        if prices[point] is None:
            continue
        rows.append(_move(_obs(mint, point, PRICE, prices[point], at=_stamp(anchor, point)), cohort, release))
    if exit_price is not None:
        rows.append(_move(_obs(mint, "Y7200", PRICE, exit_price, at=_stamp(anchor, "Y7200")), cohort, release))
    return census, rows


def _rows(parts: list[tuple[dict, list[dict]]]) -> tuple[list[dict], list[dict]]:
    return [item[0] for item in parts], [row for item in parts for row in item[1]]


def _cohort(summary: dict, cohort: str) -> dict:
    return next(item for item in summary["by_cohort"] if item["cohort_id"] == cohort)


MATCH = 1.2
MISS = 1.0

# Declared members: (mint, cohort, mark, exit). Oracle facts are written by hand below.
DISJOINT = [
    ("pos", COHORT, MATCH, 1.2),      # matched, target +0.20
    ("neg", COHORT, MATCH, 0.9),      # matched, target -0.10
    ("far", COHORT, MISS, 3.0),       # unmatched, target +2.00
    ("gap", COHORT, MATCH, None),     # matched, target missing
    ("unk", COHORT_B, None, 2.5),     # feature unknown, target +1.50
    ("mid", COHORT_B, MATCH, 1.05),   # matched, target +0.05
    ("hi", COHORT_C, MISS, 2.5),      # zero-match cohort: unmatched +1.50
    ("lo", COHORT_C, MISS, 0.5),      # zero-match cohort: unmatched -0.50
]
DISJOINT_BINDING = [
    _bind(COHORT, RELEASE),
    _bind(COHORT_B, RELEASE_B),
    _bind(COHORT_C, RELEASE_C),
    _bind(COHORT_EMPTY, RELEASE_EMPTY),
]
RELEASES = {COHORT: RELEASE, COHORT_B: RELEASE_B, COHORT_C: RELEASE_C, COHORT_EMPTY: RELEASE_EMPTY}

# Oracle, independent of production aggregation.
ORACLE = {
    COHORT: {"matched_n": 3, "observed_target_n": 2, "missing_target_n": 1, "mean_target": (0.2 - 0.1) / 2},
    COHORT_B: {"matched_n": 1, "observed_target_n": 1, "missing_target_n": 0, "mean_target": 0.05},
    COHORT_C: {"matched_n": 0, "observed_target_n": 0, "missing_target_n": 0, "mean_target": None},
    COHORT_EMPTY: {"matched_n": 0, "observed_target_n": 0, "missing_target_n": 0, "mean_target": None},
}
ORACLE_POOLED = {"matched_n": 4, "observed_target_n": 3, "missing_target_n": 1, "mean_target": (0.2 - 0.1 + 0.05) / 3}
# Baseline is every decision-eligible observed target, feature-unknown included.
ORACLE_BASELINE = {"observed_n": 7, "mean_target": (0.2 - 0.1 + 2.0 + 1.5 + 0.05 + 1.5 - 0.5) / 7}


def _disjoint(overrides: dict[str, float | None] | None = None):
    parts = []
    for mint, cohort, mark, exit_price in DISJOINT:
        if overrides and mint in overrides:
            exit_price = overrides[mint]
        parts.append(_member_rows(mint, cohort, RELEASES[cohort], mark=mark, exit_price=exit_price))
    return _rows(parts)


def _conditional(summary: dict) -> dict:
    return {
        "pooled": (summary["observed_target_n"], summary["matched_n"], summary["missing_target_n"], summary["mean_target"]),
        "calendar": [(item["view"], item["observed_n"], item["mean_target"]) for item in summary["by_calendar_block"]],
        "cohorts": {
            row["cohort_id"]: (row["matched_n"], row["observed_target_n"], row["missing_target_n"], row["mean_target"])
            for row in summary["by_cohort"]
        },
    }


class CounterexampleTests(unittest.TestCase):
    """Minimal RED cases. The old writer is the verbatim V3 aggregation."""

    def _pair(self, parts, binding):
        census, observations = _rows(parts)
        with old_writer():
            old = execute_temporal_discovery(census, observations, _query(), binding)["summary"]
        new = execute_temporal_discovery(census, observations, _query(), binding)["summary"]
        return old, new

    def test_matched_plus_unmatched(self) -> None:
        parts = [
            _member_rows("m", COHORT, RELEASE, mark=MATCH, exit_price=1.2),
            _member_rows("u", COHORT, RELEASE, mark=MISS, exit_price=3.0),
        ]
        old, new = self._pair(parts, [_bind(COHORT, RELEASE)])
        self.assertEqual(old["calculation_version"], TEMPORAL_CALCULATION_VERSION_V3)
        self.assertEqual(_cohort(old, COHORT)["observed_target_n"], 2)
        self.assertAlmostEqual(_cohort(old, COHORT)["mean_target"], 1.10, places=12)
        self.assertEqual(temporal_result_coherence(old)["status"], "INCOHERENT")
        row = _cohort(new, COHORT)
        self.assertEqual(new["calculation_version"], TEMPORAL_CALCULATION_VERSION)
        self.assertEqual((row["matched_n"], row["observed_target_n"], row["missing_target_n"]), (1, 1, 0))
        self.assertAlmostEqual(row["mean_target"], 0.20, places=12)
        self.assertEqual(row["target_observed_after_decision"], 1)
        self.assertAlmostEqual(new["mean_target"], 0.20, places=12)
        self.assertEqual(new["baseline"]["observed_n"], 2)
        self.assertAlmostEqual(new["baseline"]["mean_target"], 1.10, places=12)
        self.assertEqual(temporal_result_coherence(new)["status"], "COHERENT")

    def test_zero_match_with_observed_unmatched(self) -> None:
        parts = [_member_rows("u", COHORT, RELEASE, mark=MISS, exit_price=3.0)]
        old, new = self._pair(parts, [_bind(COHORT, RELEASE)])
        self.assertEqual(_cohort(old, COHORT)["observed_target_n"], 1)
        self.assertIsNotNone(_cohort(old, COHORT)["mean_target"])
        row = _cohort(new, COHORT)
        self.assertEqual((row["matched_n"], row["observed_target_n"], row["missing_target_n"]), (0, 0, 0))
        self.assertIsNone(row["mean_target"])
        self.assertIsNone(new["mean_target"])
        self.assertIsNone(new.get("technical_stop"))

    def test_matched_missing_with_observed_unmatched(self) -> None:
        parts = [
            _member_rows("m", COHORT, RELEASE, mark=MATCH, exit_price=None),
            _member_rows("u", COHORT, RELEASE, mark=MISS, exit_price=3.0),
        ]
        old, new = self._pair(parts, [_bind(COHORT, RELEASE)])
        self.assertEqual(_cohort(old, COHORT)["observed_target_n"], 1)
        self.assertEqual(_cohort(old, COHORT)["missing_target_n"], 1)
        row = _cohort(new, COHORT)
        self.assertEqual((row["matched_n"], row["observed_target_n"], row["missing_target_n"]), (1, 0, 1))
        self.assertIsNone(row["mean_target"])
        self.assertEqual(row["target_exclusion_reasons"], {"EXIT_ABSENT": 1})

    def test_all_matched_control_is_unchanged(self) -> None:
        parts = [
            _member_rows("a", COHORT, RELEASE, mark=MATCH, exit_price=1.2),
            _member_rows("b", COHORT, RELEASE, mark=MATCH, exit_price=0.9),
        ]
        old, new = self._pair(parts, [_bind(COHORT, RELEASE)])
        self.assertEqual(old["by_cohort"], new["by_cohort"])
        self.assertEqual(temporal_result_coherence(old)["status"], "COHERENT")


class ConditionalSampleContractTests(unittest.TestCase):
    def setUp(self) -> None:
        census, observations = _disjoint()
        self.summary = execute_temporal_discovery(census, observations, _query(), DISJOINT_BINDING)["summary"]

    def test_oracle_matches_every_conditional_view(self) -> None:
        summary = self.summary
        for cohort, expected in ORACLE.items():
            row = _cohort(summary, cohort)
            for key in ("matched_n", "observed_target_n", "missing_target_n"):
                self.assertEqual(row[key], expected[key], (cohort, key))
            if expected["mean_target"] is None:
                self.assertIsNone(row["mean_target"], cohort)
            else:
                self.assertAlmostEqual(row["mean_target"], expected["mean_target"], places=12)
            self.assertEqual(row["observed_target_n"] + row["missing_target_n"], row["matched_n"])
            self.assertEqual(row["target_observed_after_decision"], row["observed_target_n"])
        for key in ("matched_n", "observed_target_n", "missing_target_n"):
            self.assertEqual(summary[key], ORACLE_POOLED[key])
        self.assertAlmostEqual(summary["mean_target"], ORACLE_POOLED["mean_target"], places=12)
        self.assertAlmostEqual(summary["pooled"]["mean_target"], ORACLE_POOLED["mean_target"], places=12)
        self.assertEqual(summary["pooled"]["target_observed_after_decision"], summary["observed_target_n"])
        self.assertEqual(summary["baseline"]["observed_n"], ORACLE_BASELINE["observed_n"])
        self.assertAlmostEqual(summary["baseline"]["mean_target"], ORACLE_BASELINE["mean_target"], places=12)
        self.assertEqual(summary["feature_unknown_n"], 1)
        self.assertEqual(_cohort(summary, COHORT_B)["feature_unknown_n"], 1)
        self.assertEqual(_cohort(summary, COHORT_EMPTY)["population_n"], 0)
        self.assertEqual(_cohort(summary, COHORT)["missing_target_n"], 1)
        self.assertEqual(temporal_result_coherence(summary)["status"], "COHERENT")

    def test_disjoint_sums_and_weighted_mean_equal_pooled(self) -> None:
        rows = self.summary["by_cohort"]
        self.assertTrue(all(row["shared_decision_n"] == 0 for row in rows))
        for key in ("matched_n", "observed_target_n", "missing_target_n"):
            self.assertEqual(sum(row[key] for row in rows), self.summary[key])
        weighted = sum(row["mean_target"] * row["observed_target_n"] for row in rows if row["observed_target_n"])
        self.assertAlmostEqual(weighted / self.summary["observed_target_n"], self.summary["mean_target"], places=12)
        blocks = self.summary["by_calendar_block"]
        self.assertEqual(sum(item["observed_n"] for item in blocks), self.summary["observed_target_n"])

    def test_permutation_does_not_change_the_result(self) -> None:
        census, observations = _disjoint()
        rng = random.Random(20260930)
        for _ in range(5):
            shuffled_census = list(census)
            shuffled_obs = list(observations)
            rng.shuffle(shuffled_census)
            rng.shuffle(shuffled_obs)
            again = execute_temporal_discovery(shuffled_census, shuffled_obs, _query(), DISJOINT_BINDING)["summary"]
            self.assertEqual(result_sha256(again), result_sha256(self.summary))
        reordered = list(reversed(DISJOINT_BINDING))
        again = execute_temporal_discovery(census, observations, _query(), reordered)["summary"]
        self.assertEqual(_conditional(again)["pooled"], _conditional(self.summary)["pooled"])
        self.assertEqual(_conditional(again)["cohorts"], _conditional(self.summary)["cohorts"])

    def test_unmatched_outcome_moves_baseline_only(self) -> None:
        census, observations = _disjoint({"far": 9.0, "hi": 0.1, "lo": 4.0, "unk": 0.2})
        moved = execute_temporal_discovery(census, observations, _query(), DISJOINT_BINDING)["summary"]
        self.assertEqual(_conditional(moved), _conditional(self.summary))
        self.assertNotAlmostEqual(moved["baseline"]["mean_target"], self.summary["baseline"]["mean_target"], places=6)

    def test_matched_outcome_moves_its_conditional_views(self) -> None:
        census, observations = _disjoint({"pos": 2.0})
        moved = execute_temporal_discovery(census, observations, _query(), DISJOINT_BINDING)["summary"]
        self.assertNotAlmostEqual(_cohort(moved, COHORT)["mean_target"], _cohort(self.summary, COHORT)["mean_target"], places=6)
        self.assertNotAlmostEqual(moved["mean_target"], self.summary["mean_target"], places=6)
        self.assertNotEqual(_conditional(moved)["calendar"], _conditional(self.summary)["calendar"])
        self.assertEqual(_cohort(moved, COHORT_B), _cohort(self.summary, COHORT_B))

    def test_missing_is_not_zero_and_unknown_is_not_matched(self) -> None:
        census, observations = _disjoint({"gap": 1.0})
        filled = execute_temporal_discovery(census, observations, _query(), DISJOINT_BINDING)["summary"]
        # A real zero return differs from a missing target.
        self.assertEqual(_cohort(filled, COHORT)["observed_target_n"], 3)
        self.assertNotAlmostEqual(_cohort(filled, COHORT)["mean_target"], _cohort(self.summary, COHORT)["mean_target"], places=6)
        self.assertEqual(_cohort(self.summary, COHORT)["observed_target_n"], 2)
        row = _cohort(self.summary, COHORT_B)
        self.assertEqual((row["decision_eligible_n"], row["feature_unknown_n"], row["matched_n"]), (2, 1, 1))

    def test_overlap_counts_a_decision_once_in_pooled(self) -> None:
        shared_a = _member_rows("shared", COHORT, RELEASE, mark=MATCH, exit_price=1.3)
        shared_b = _member_rows("shared", COHORT_B, RELEASE_B, mark=MATCH, exit_price=1.3)
        own_a = _member_rows("own-a", COHORT, RELEASE, mark=MATCH, exit_price=1.1)
        own_b = _member_rows("own-b", COHORT_B, RELEASE_B, mark=MISS, exit_price=5.0)
        census, observations = _rows([shared_a, shared_b, own_a, own_b])
        binding = [_bind(COHORT, RELEASE), _bind(COHORT_B, RELEASE_B)]
        summary = execute_temporal_discovery(census, observations, _query(), binding)["summary"]
        self.assertEqual(summary["observed_target_n"], 2)
        self.assertEqual(_cohort(summary, COHORT)["observed_target_n"], 2)
        self.assertEqual(_cohort(summary, COHORT_B)["observed_target_n"], 1)
        self.assertEqual(_cohort(summary, COHORT)["shared_decision_n"], 1)
        self.assertGreater(
            sum(row["observed_target_n"] for row in summary["by_cohort"]), summary["observed_target_n"]
        )
        self.assertAlmostEqual(_cohort(summary, COHORT_B)["mean_target"], 0.3, places=12)
        self.assertEqual(temporal_result_coherence(summary)["status"], "COHERENT")

    def test_conflicted_identity_stays_out_after_a_later_copy(self) -> None:
        first = _member_rows("dup", COHORT, RELEASE, mark=MATCH, exit_price=1.2)
        twin = _member_rows("dup", COHORT_B, RELEASE_B, mark=MATCH, exit_price=9.0)
        clean = _member_rows("clean", COHORT, RELEASE, mark=MATCH, exit_price=1.1)
        binding = [_bind(COHORT, RELEASE), _bind(COHORT_B, RELEASE_B)]
        for order in ((first, twin, first), (twin, first, first), (first, first, twin)):
            census, observations = _rows([*order, clean])
            census = [item[0] for item in order] + [clean[0]]
            observations = first[1] + twin[1] + clean[1]
            summary = execute_temporal_discovery(census, observations, _query(), binding)["summary"]
            self.assertEqual(summary["integrity_conflict_count"], 1)
            self.assertEqual(summary["observed_target_n"], 1)
            self.assertEqual(_cohort(summary, COHORT)["observed_target_n"], 1)
            self.assertEqual(_cohort(summary, COHORT_B)["observed_target_n"], 0)
            self.assertIsNone(_cohort(summary, COHORT_B)["mean_target"])
            self.assertAlmostEqual(_cohort(summary, COHORT)["mean_target"], 0.1, places=12)
            self.assertEqual(temporal_result_coherence(summary)["status"], "COHERENT")


class CoherenceCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        census, observations = _disjoint()
        self.summary = execute_temporal_discovery(census, observations, _query(), DISJOINT_BINDING)["summary"]

    def _broken(self, mutate) -> dict:
        body = json.loads(json.dumps(self.summary))
        mutate(body)
        return temporal_result_coherence(body)

    def test_detects_each_broken_invariant_by_field(self) -> None:
        def cohort(body):
            return next(row for row in body["by_cohort"] if row["cohort_id"] == COHORT)

        cases = {
            "observed_target_n+missing_target_n": lambda b: cohort(b).update(observed_target_n=3),
            "target_observed_after_decision": lambda b: cohort(b).update(target_observed_after_decision=7),
            "mean_target": lambda b: next(r for r in b["by_cohort"] if r["cohort_id"] == COHORT_C).update(mean_target=0.5),
            "observed_n_sum": lambda b: b["by_calendar_block"][0].update(observed_n=99),
            "weighted_mean_target": lambda b: cohort(b).update(mean_target=0.9),
        }
        for field, mutate in cases.items():
            result = self._broken(mutate)
            self.assertEqual(result["status"], "INCOHERENT", field)
            self.assertEqual(result["repair_action"], "CALCULATION_REVISION")
            self.assertIn(field, {item["field"] for item in result["issues"]}, field)

    def test_compact_older_summaries_are_read_as_they_are(self) -> None:
        self.assertEqual(temporal_result_coherence({"calculation_version": "V1"})["status"], "COHERENT")
        legacy = dict(self.summary)
        legacy.pop("by_cohort")
        self.assertEqual(temporal_result_coherence(legacy)["status"], "COHERENT")

    def test_readout_marks_an_incoherent_result_not_science_ready(self) -> None:
        parts = [
            _member_rows("m", COHORT, RELEASE, mark=MATCH, exit_price=1.2),
            _member_rows("u", COHORT, RELEASE, mark=MISS, exit_price=3.0),
        ]
        census, observations = _rows(parts)
        with old_writer():
            old = execute_temporal_discovery(census, observations, _query(), [_bind(COHORT, RELEASE)])["summary"]
        shown = format_discovery_readout({"result": old, "result_refs": ["HFIC-ART-DISCOVERY-OLD"]})
        self.assertEqual(shown["result_coherence"], "INCOHERENT")
        self.assertFalse(shown["science_ready"])
        self.assertEqual(shown["repair_action"], "CALCULATION_REVISION")
        fields = {(item["view"], item["field"]) for item in shown["incoherent_fields"]}
        self.assertIn((f"by_cohort:{COHORT}", "observed_target_n+missing_target_n"), fields)


class TierProgressFitnessTests(unittest.TestCase):
    def _look(self, record: str, summary: dict, **extra) -> dict:
        return {
            "record_id": record,
            "new_look": True,
            "look_class": "MAIN",
            "search_tier": "SIMPLE_SCREEN",
            "calculation_version": summary["calculation_version"],
            "result": summary,
            **extra,
        }

    def test_spent_simple_stays_spent_but_wrong_summary_is_no_terminal(self) -> None:
        parts = [
            _member_rows("m", COHORT, RELEASE, mark=MATCH, exit_price=1.2),
            _member_rows("u", COHORT, RELEASE, mark=MISS, exit_price=3.0),
        ]
        census, observations = _rows(parts)
        with old_writer():
            old = execute_temporal_discovery(census, observations, _query(), [_bind(COHORT, RELEASE)])["summary"]
        new = execute_temporal_discovery(census, observations, _query(), [_bind(COHORT, RELEASE)])["summary"]
        source = self._look("L-V3", old)
        for worthy, applicable in ((False, False), (True, True), (False, True)):
            progress = assess_tier_progress([source], freeze_worthy=worthy, compound_applicable=applicable)
            self.assertTrue(progress["simple_executed"])
            self.assertFalse(progress["search_exhausted_allowed"])
            self.assertEqual(progress["action"], "CORRECT_CALCULATION_REVISION")
            self.assertTrue(progress["evidence_revision_required"])
        revision = {
            "record_id": "L-V4",
            "new_look": False,
            "look_class": "CALCULATION_REVISION",
            "search_tier": "SIMPLE_SCREEN",
            "calculation_version": TEMPORAL_CALCULATION_VERSION,
            "result": new,
            "revision_of": {"record_id": "L-V3", "root_record_id": "L-V3"},
        }
        fixed = assess_tier_progress([source, revision], freeze_worthy=False, compound_applicable=False)
        self.assertEqual(fixed["compound_status"], "SKIPPED_INAPPLICABLE")
        self.assertTrue(fixed["search_exhausted_allowed"])
        open_search = assess_tier_progress([source, revision], freeze_worthy=False, compound_applicable=True)
        self.assertEqual(open_search["action"], "ESCALATE_COMPOUND")
        self.assertFalse(open_search["compound_executed"])
        self.assertFalse(open_search["search_exhausted_allowed"])

    def test_one_coherent_sibling_does_not_hide_an_unfit_look(self) -> None:
        parts = [
            _member_rows("m", COHORT, RELEASE, mark=MATCH, exit_price=1.2),
            _member_rows("u", COHORT, RELEASE, mark=MISS, exit_price=3.0),
        ]
        census, observations = _rows(parts)
        with old_writer():
            old = execute_temporal_discovery(census, observations, _query(), [_bind(COHORT, RELEASE)])["summary"]
        new = execute_temporal_discovery(census, observations, _query(), [_bind(COHORT, RELEASE)])["summary"]
        wrong = self._look("L-OLD", old)
        good_simple = self._look("L-SIMPLE", new)
        good_compound = self._look("L-COMPOUND", new, search_tier="COMPOUND_SCREEN")
        for looks, applicable in (([wrong, good_compound], True), ([wrong, good_simple], False)):
            progress = assess_tier_progress(looks, freeze_worthy=False, compound_applicable=applicable)
            self.assertEqual(progress["action"], "CORRECT_CALCULATION_REVISION")
            self.assertFalse(progress["search_exhausted_allowed"])
            self.assertTrue(progress["evidence_revision_required"])


# --- published corpus through the production publisher and binder ---------------------------

CAMPAIGN_B = CAMPAIGN_STARTS + timedelta(days=3)
SHARED_HOURS = 100  # inside [A, A+7d) and [A+3d, A+10d)
TWIN_HOURS = 110

# (mint, hours after the cohort start, Y1800 mark or None, Y7200 exit or None); reference 1.0
PUBLISHED = [
    (CAMPAIGN_STARTS, 0, [
        ("MintPos", 1, "1.2", "1.2"),
        ("MintNeg", 2, "1.2", "0.9"),
        ("MintFar", 3, "1.0", "3.0"),
        ("MintGap", 4, "1.2", None),
        ("MintShared", SHARED_HOURS, "1.2", "1.3"),
        ("MintTwin", TWIN_HOURS, "1.2", "1.1"),
    ]),
    (CAMPAIGN_STARTS, 1, [
        ("MintUnk", 1, None, "2.5"),
        ("MintMid", 30, "1.2", "1.05"),
    ]),
    (CAMPAIGN_STARTS, 2, [
        ("MintHi", 1, "1.0", "2.5"),
        ("MintLo", 2, "1.0", "0.5"),
    ]),
    (CAMPAIGN_STARTS, 3, [
        ("MintIdle", 1, "1.2", "1.2", "NOT_ELIGIBLE"),
    ]),
    (CAMPAIGN_B, 0, [
        ("MintShared", SHARED_HOURS - 72, "1.2", "1.3"),
        ("MintTwin", TWIN_HOURS - 72, "1.2", "9.0"),
        ("MintOwnB", 50, "1.0", "5.0"),
    ]),
]
# Hand-written oracle for the published corpus (reference 1.0 at Y3600).
PUBLISHED_ORACLE = {
    "pooled": {"matched_n": 5, "observed_target_n": 4, "missing_target_n": 1, "mean_target": (0.2 - 0.1 + 0.3 + 0.05) / 4},
    "cohorts": [
        {"matched_n": 4, "observed_target_n": 3, "missing_target_n": 1, "mean_target": (0.2 - 0.1 + 0.3) / 3},
        {"matched_n": 1, "observed_target_n": 1, "missing_target_n": 0, "mean_target": 0.05},
        {"matched_n": 0, "observed_target_n": 0, "missing_target_n": 0, "mean_target": None},
        {"matched_n": 0, "observed_target_n": 0, "missing_target_n": 0, "mean_target": None},
        {"matched_n": 1, "observed_target_n": 1, "missing_target_n": 0, "mean_target": 0.3},
    ],
    "baseline_n": 9,
}


def _published_cohort_ids() -> list[str]:
    ids = []
    for start, week, _members in PUBLISHED:
        cohort = cohort_id_for_admission(
            start + timedelta(days=7 * week),
            starts_at=start,
            stops_admitting_at=start + timedelta(days=84),
        )
        assert cohort is not None
        ids.append(cohort)
    return ids


def _timed(mint: str, point: str, field: str, value: str, anchor) -> dict:
    row = _series_obs(mint, point, anchor.strftime("%Y-%m-%dT%H:%M:%SZ"))
    stamp = (anchor + timedelta(seconds=OFFSETS[point] + DOCUMENT_LATENESS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row.update(
        {
            "field_id": field,
            "typed_value": value,
            "state": "OBSERVED",
            "missing_reason": None,
            "event_time": stamp,
            "first_reliable_available_at": stamp,
            "request_started_at": stamp,
            "response_received_at": stamp,
        }
    )
    return row


def publish_mixed(data_root: Path, workspace: Path) -> list[str]:
    """Several cohorts, overlapping windows, one integrity conflict. Real publisher and import."""

    data_root.mkdir(parents=True, exist_ok=True)
    schedule = _schedule()
    first_as_of = None
    last_import = None
    ids = []
    for index, (start, week, spec) in enumerate(PUBLISHED):
        admission = start + timedelta(days=7 * week)
        stops = start + timedelta(days=84)
        cohort_id = cohort_id_for_admission(admission, starts_at=start, stops_admitting_at=stops)
        assert cohort_id is not None
        ids.append(cohort_id)
        members = []
        observations = []
        for entry in spec:
            mint, hours, mark, exit_price = entry[:4]
            anchor = admission + timedelta(hours=hours)
            member = _member(mint, anchor.strftime("%Y-%m-%dT%H:%M:%SZ"))
            member["candidate_state"] = "X_ELIGIBLE" if len(entry) < 5 else "ADMITTED"
            members.append(member)
            observations.append(_timed(mint, "X300", LIQUIDITY, "10000", anchor))
            for point, value in (("X300", "1.0"), ("Y900", "1.0"), ("Y1800", mark), ("Y3600", "1.0")):
                if value is not None:
                    observations.append(_timed(mint, point, PRICE, value, anchor))
            if exit_price is not None:
                observations.append(_timed(mint, "Y7200", PRICE, exit_price, anchor))
        for filler in range(2):
            # Not X-eligible; keeps the release above the low-yield floor.
            members.append(_member(f"Fill{index}{filler}", (admission + timedelta(hours=filler)).strftime("%Y-%m-%dT%H:%M:%SZ")))
        as_of = admission + timedelta(days=10)
        first_as_of = first_as_of or as_of
        snapshot = {
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": ACTIVATION,
            "producer_git_sha": PRODUCER,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stops_admitting_at": stops.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "discovery_coverage_class": "EMPIRICAL_OVERLAP_ONLY",
            "open_publication": False,
            "unresolved_due": False,
            "in_flight": False,
            "budget_blocked": False,
            "closure_receipt_sha256": "c" * 64,
            "as_of": as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "members": members,
            "observations": observations,
        }
        source = workspace / f"observation-rdp-{index}"
        release = workspace / f"release-{index}"
        write_observation_rdp_source(source, snapshot, cohort_id=cohort_id)
        seal_live_cohort(
            observation_rdp_root=source,
            cohort_id=cohort_id,
            release_root=release,
            sealed_at=as_of,
            as_of=as_of,
        )
        # Imports are append-only in time: a later import never predates earlier content.
        last_import = max(as_of, last_import or as_of) + timedelta(hours=1)
        imported = import_live_cohort(release_root=release, data_root=data_root, import_time=last_import)
        assert imported["status"] == "IMPORTED", imported
    from solana_alpha_lab.factory.observation_panel_publisher import persist_observation_schedule

    persist_observation_schedule(
        data_root=data_root,
        schedule=schedule,
        now=first_as_of,
        producer_git_sha=PRODUCER,
        activation_id=ACTIVATION,
    )
    return ids


def published_query(query_id: str = "published-coherence", threshold: float = 1.1) -> dict:
    return _spec(
        "SIMPLE_SCREEN",
        query_id=query_id,
        features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": FEATURE_POINT}],
        all=[{"feature": "mark", "op": "gte", "value": threshold}],
        cost_profile=None,
        schedule={"lateness_seconds": DOCUMENT_LATENESS},
    )


class PublishedCorpusOracleTests(unittest.TestCase):
    def test_binder_rows_match_the_oracle_and_old_writer_is_wrong(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            ids = publish_mixed(data_root, workspace)
            loaded = load_admitted_partition_rows(
                data_root=data_root, binding_doc=None, partitions=None, census_path=None, observations_path=None
            )
            self.assertEqual(sorted(item["cohort_id"] for item in loaded["cohorts"]), sorted(ids))
            spec = published_query()
            summary = execute_temporal_discovery(loaded["census"], loaded["observations"], spec, loaded["cohorts"])[
                "summary"
            ]
            with old_writer():
                old = execute_temporal_discovery(loaded["census"], loaded["observations"], spec, loaded["cohorts"])[
                    "summary"
                ]
            pooled = PUBLISHED_ORACLE["pooled"]
            for key in ("matched_n", "observed_target_n", "missing_target_n"):
                self.assertEqual(summary[key], pooled[key], key)
            self.assertAlmostEqual(summary["mean_target"], pooled["mean_target"], places=12)
            self.assertEqual(summary["integrity_conflict_count"], 1)
            self.assertEqual(summary["baseline"]["observed_n"], PUBLISHED_ORACLE["baseline_n"])
            for cohort_id, expected in zip(ids, PUBLISHED_ORACLE["cohorts"], strict=True):
                row = _cohort(summary, cohort_id)
                for key in ("matched_n", "observed_target_n", "missing_target_n"):
                    self.assertEqual(row[key], expected[key], (cohort_id, key))
                if expected["mean_target"] is None:
                    self.assertIsNone(row["mean_target"])
                else:
                    self.assertAlmostEqual(row["mean_target"], expected["mean_target"], places=12)
            self.assertEqual(_cohort(summary, ids[0])["shared_decision_n"], 1)
            self.assertEqual(_cohort(summary, ids[1])["feature_unknown_n"], 1)
            self.assertEqual(_cohort(summary, ids[3])["population_n"], 0)
            self.assertGreater(
                sum(row["observed_target_n"] for row in summary["by_cohort"]), summary["observed_target_n"]
            )
            self.assertEqual(temporal_result_coherence(summary)["status"], "COHERENT")
            # Only the cohort view moved between the writers.
            for key in ("baseline", "pooled", "by_calendar_block", "exclusion_reasons", "ablations"):
                self.assertEqual(old[key], summary[key], key)
            self.assertEqual(_cohort(old, ids[2])["observed_target_n"], 2)
            self.assertEqual(temporal_result_coherence(old)["status"], "INCOHERENT")
            shuffled = execute_temporal_discovery(
                list(reversed(loaded["census"])), list(reversed(loaded["observations"])), spec, list(reversed(loaded["cohorts"]))
            )["summary"]
            self.assertEqual(_conditional(shuffled)["cohorts"], _conditional(summary)["cohorts"])
            self.assertEqual(_conditional(shuffled)["pooled"], _conditional(summary)["pooled"])


FOCUS = "COHERENCE_REVISION_VERTICAL"


def _inventory(root: Path) -> str:
    return ResearchStore(root, create_if_missing=False).diagnostics().committed_inventory_sha256


def _journal_looks(root: Path, journal: str) -> list[dict]:
    return list_discovery_looks(ResearchStore(root, create_if_missing=False), journal)


class SavedResultRevisionVerticalTests(unittest.TestCase):
    """Old writer -> PAUSED_CAP -> explicit revision -> readback, on the published corpus."""

    def _open(self, workspace: Path, data_root: Path) -> dict:
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation

        preflight = run_cli(
            "preflight", "--discovery-contract", "--owner-focus", FOCUS, "--format", "json", data_root=data_root
        )
        self.assertEqual(preflight.returncode, 0, preflight.stderr + preflight.stdout)
        receipt = json.loads(preflight.stdout)
        spec = published_query()
        ctx = {
            "workspace": workspace,
            "data_root": data_root,
            "receipt": receipt,
            "journal": str(receipt["search_key_sha256"]),
            "market": str(receipt["market_evidence_epoch_sha256"]),
            "spec": spec,
            "spec_path": workspace / "spec.json",
            "scope_path": workspace / "scope.json",
            "op_path": workspace / "op.json",
            "scope": {
                "population": "BASE_X",
                "decision_timestamp": "Y3600",
                "target": temporal.temporal_target_label(spec),
                "estimand": "price_relative_proxy",
                "explanatory_condition": "mark",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            },
        }
        ctx["spec_path"].write_text(json.dumps(spec), encoding="utf-8")
        ctx["scope_path"].write_text(json.dumps(ctx["scope"]), encoding="utf-8")
        ctx["op_path"].write_text(
            json.dumps(
                _operation(
                    spec,
                    focus=FOCUS,
                    journal=ctx["journal"],
                    market=ctx["market"],
                    text="one SIMPLE on the mixed corpus",
                    cap={"main": 1, "adaptive": 0, "preview": 0},
                )
            ),
            encoding="utf-8",
        )
        return ctx

    def _execute(self, forge, ctx: dict, *, data_root: Path | None = None, spec_path=None, binding_path=None, correction=None):
        import contextlib
        import io

        root = data_root or ctx["data_root"]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = forge.cmd_discovery_execute(
                ROOT,
                store_root=root,
                census_path=None,
                observations_path=None,
                binding_path=binding_path,
                spec_path=spec_path or ctx["spec_path"],
                journal_scope=ctx["journal"],
                candidate_scope_path=ctx["scope_path"],
                explicit_data_root=root,
                operation_path=ctx["op_path"],
                correct_result_ref=(correction or (None, None))[0],
                correct_result_sha256=(correction or (None, None))[1],
            )
        lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
        return code, (json.loads(lines[-1]) if lines else {})

    def test_saved_wrong_simple_is_revised_without_a_new_main(self) -> None:
        import shutil

        from solana_alpha_lab.factory.hfic_ordinary_operation import (
            _reservations,
            get_operation,
            list_operations,
            owner_allowance,
        )
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge

        forge = _forge()
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            ids = publish_mixed(data_root, workspace)
            ctx = self._open(workspace, data_root)
            journal = ctx["journal"]
            calls = {"n": 0}
            real = temporal.execute_temporal_discovery

            def counting(*args, **kwargs):
                calls["n"] += 1
                return real(*args, **kwargs)

            # 1. The old writer saves a genuinely wrong SIMPLE look and pauses on the cap.
            with old_writer():
                code, first = self._execute(forge, ctx)
            self.assertEqual(code, 0, first)
            v3_ref = first["result_refs"][0]
            v3_sha = first["result_sha256"]
            self.assertEqual(first["calculation_version"], TEMPORAL_CALCULATION_VERSION_V3)
            self.assertEqual(first["queries"][0]["look_class"], "MAIN")
            self.assertEqual(first["ordinary_operation"], "PAUSED_CAP")
            self.assertEqual(temporal_result_coherence(first["result"])["status"], "INCOHERENT")
            self.assertEqual(_cohort(first["result"], ids[2])["observed_target_n"], 2)
            store = ResearchStore(data_root, create_if_missing=False)
            op_sha = next(
                str(item["operation_sha256"])
                for item in list_operations(store)
                if item.get("journal_scope") == journal
            )
            reserved = len(_reservations(store, op_sha))
            self.assertEqual(reserved, 1)
            v3_payload = next(r.payload_json for r in store.iter_committed_records() if r.record_id == v3_ref)

            # 2. Ordinary readback of the wrong result: exact bytes, a technical stop, no evaluator.
            before = _inventory(data_root)
            with mock.patch.object(temporal, "execute_temporal_discovery", counting):
                code, stop = self._execute(forge, ctx)
            self.assertEqual(code, 2, stop)
            self.assertEqual(stop["reason_code"], "TEMPORAL_RESULT_INCOHERENT")
            self.assertEqual(stop["result_refs"], [v3_ref])
            self.assertEqual(stop["next_action"], "CORRECT_CALCULATION_REVISION")
            self.assertEqual(stop["repair_action"], "CALCULATION_REVISION")
            self.assertFalse(stop["values_loaded"])
            self.assertFalse(stop["writes"])
            self.assertFalse(stop["scientific_negative"])
            self.assertIn(f"by_cohort:{ids[0]}", {item["view"] for item in stop["incoherent_fields"]})
            self.assertEqual(calls["n"], 0)
            self.assertEqual(_inventory(data_root), before)
            cold = run_cli("forge-run", "--owner-focus", FOCUS, "--no-write", "--format", "json", data_root=data_root)
            self.assertEqual(cold.returncode, 0, cold.stderr + cold.stdout)
            shown = json.loads(cold.stdout)
            self.assertEqual(shown["next_action"], "CORRECT_CALCULATION_REVISION", shown)
            self.assertNotEqual(shown["next_action"], "AUTHORIZE_ADDITIONAL_LOOKS")
            self.assertEqual(shown["ordinary_operation"]["result"]["result_coherence"], "INCOHERENT")
            self.assertIn(v3_ref, shown["owner_readout"])
            self.assertIn("no new look", shown["owner_readout"])

            # 3. Refusals before any write: wrong hash, changed spec, changed input.
            code, refused = self._execute(forge, ctx, correction=(v3_ref, "0" * 64))
            self.assertEqual((code, refused["reason_code"]), (2, "CALCULATION_REVISION_SOURCE_HASH_MISMATCH"))
            changed_spec = workspace / "changed-spec.json"
            changed_spec.write_text(json.dumps(published_query(threshold=1.15)), encoding="utf-8")
            code, refused = self._execute(forge, ctx, spec_path=changed_spec, correction=(v3_ref, v3_sha))
            self.assertEqual((code, refused["reason_code"]), (2, "ORDINARY_OPERATION_SPEC_MISMATCH"))
            narrowed = resolve_published_discovery_binding(data_root)
            narrowed["cohorts"] = list(narrowed["cohorts"])[:-1]
            narrowed_path = workspace / "narrowed-binding.json"
            narrowed_path.write_text(json.dumps(narrowed), encoding="utf-8")
            code, refused = self._execute(forge, ctx, binding_path=narrowed_path, correction=(v3_ref, v3_sha))
            self.assertEqual(code, 2, refused)
            self.assertIn(
                refused["reason_code"],
                {"ORDINARY_OPERATION_BINDING_MISMATCH", "CALCULATION_REVISION_INPUT_MISMATCH"},
            )
            self.assertFalse(refused["writes"])
            self.assertEqual(_inventory(data_root), before)

            # Isolated copy for the candidate branch, taken before any revision.
            candidate_root = workspace / "candidate-rdp"
            shutil.copytree(data_root, candidate_root)

            # 4. Faults: crash before the append, then reply lost after the commit.
            from solana_alpha_lab.factory import hfic_grounded_discovery as grounded

            with mock.patch.object(temporal, "execute_temporal_discovery", counting), mock.patch.object(
                grounded, "_append_discovery_look", side_effect=RuntimeError("crash-before-append")
            ):
                with self.assertRaises(RuntimeError):
                    self._execute(forge, ctx, correction=(v3_ref, v3_sha))
            self.assertEqual(calls["n"], 1)
            self.assertEqual(_inventory(data_root), before)
            with mock.patch.object(temporal, "execute_temporal_discovery", counting), mock.patch.object(
                forge, "emit", side_effect=RuntimeError("reply-lost")
            ):
                with self.assertRaises(RuntimeError):
                    self._execute(forge, ctx, correction=(v3_ref, v3_sha))
            self.assertEqual(calls["n"], 2)
            looks = _journal_looks(data_root, journal)
            self.assertEqual(len(looks), 2)
            with mock.patch.object(temporal, "execute_temporal_discovery", counting):
                code, again = self._execute(forge, ctx, correction=(v3_ref, v3_sha))
            self.assertEqual(code, 0, again)
            self.assertEqual(calls["n"], 2, "a committed revision was recomputed")
            self.assertTrue(again["correction_already_applied"])
            self.assertFalse(again["writes"])
            self.assertEqual(len(_journal_looks(data_root, journal)), 2)

            # 5. The revision: same question, same input, lineage, no new MAIN.
            looks = _journal_looks(data_root, journal)
            source, revision = looks
            self.assertEqual(source["record_id"], v3_ref)
            self.assertEqual(revision["calculation_version"], TEMPORAL_CALCULATION_VERSION)
            self.assertEqual(revision["look_class"], "CALCULATION_REVISION")
            self.assertFalse(revision["new_look"])
            self.assertEqual(revision["spec_sha256"], source["spec_sha256"])
            self.assertEqual(revision["data_binding_sha256"], source["data_binding_sha256"])
            self.assertEqual(revision["operation_sha256"], op_sha)
            self.assertEqual(revision["candidate_scope"], source["candidate_scope"])
            self.assertEqual(revision["revision_of"]["record_id"], v3_ref)
            self.assertEqual(revision["revision_of"]["result_sha256"], v3_sha)
            self.assertEqual(revision["revision_of"]["reason"]["code"], "COHORT_CONDITIONAL_SAMPLE_V4")
            self.assertEqual(again["result_refs"], [revision["record_id"]])
            corrected = revision["result"]
            for cohort_id, expected in zip(ids, PUBLISHED_ORACLE["cohorts"], strict=True):
                row = _cohort(corrected, cohort_id)
                self.assertEqual(
                    (row["matched_n"], row["observed_target_n"], row["missing_target_n"]),
                    (expected["matched_n"], expected["observed_target_n"], expected["missing_target_n"]),
                )
            for key in ("baseline", "pooled", "by_calendar_block", "exclusion_reasons", "ablations", "experiment_recipe"):
                self.assertEqual(corrected[key], source["result"][key], key)
            store = ResearchStore(data_root, create_if_missing=False)
            self.assertEqual(
                sum(1 for item in looks if item.get("look_class") == "MAIN" and item.get("new_look") is True), 1
            )
            self.assertEqual(len(_reservations(store, op_sha)), reserved)
            self.assertEqual(owner_allowance(store, get_operation(store, op_sha), "main"), 0)
            self.assertEqual(get_operation(store, op_sha)["status"], "PAUSED_CAP")
            self.assertEqual(
                next(r.payload_json for r in store.iter_committed_records() if r.record_id == v3_ref), v3_payload
            )
            # The earliest stored row would shadow the revision under first-match selection.
            first_match = next(
                item for item in looks if item.get("operation_sha256") == op_sha and item.get("spec_sha256") == source["spec_sha256"]
            )
            self.assertEqual(first_match["record_id"], v3_ref)

            # 6. Ordinary replay returns the revision without the evaluator, here and in a new process.
            with mock.patch.object(temporal, "execute_temporal_discovery", counting):
                code, replay = self._execute(forge, ctx)
            self.assertEqual(code, 0, replay)
            self.assertEqual(replay["result_refs"], [revision["record_id"]])
            self.assertEqual(replay["calculation_version"], TEMPORAL_CALCULATION_VERSION)
            self.assertFalse(replay["values_loaded"])
            self.assertEqual(calls["n"], 2)
            fresh = run_cli(
                "discovery-execute",
                "--store", str(data_root),
                "--spec", str(ctx["spec_path"]),
                "--candidate-scope", str(ctx["scope_path"]),
                "--journal-scope", journal,
                "--operation-sha256", op_sha,
                "--format", "json",
                data_root=data_root,
            )
            self.assertEqual(fresh.returncode, 0, fresh.stderr + fresh.stdout)
            fresh_body = json.loads(fresh.stdout)
            self.assertEqual(fresh_body["result_refs"], [revision["record_id"]])
            self.assertFalse(fresh_body["writes"])
            with self.assertRaises(GroundedDiscoveryError) as stale:
                from solana_alpha_lab.factory.hfic_grounded_discovery import assert_computed_grounded_evidence

                assert_computed_grounded_evidence(ResearchStore(data_root, create_if_missing=False), first)
            self.assertEqual(stale.exception.code, "TEMPORAL_RESULT_INCOHERENT")

            # 7. Non-candidate branch: a limited, paused result. No NO_WORTHY, no automatic compound.
            readback = run_cli("forge-run", "--owner-focus", FOCUS, "--no-write", "--format", "json", data_root=data_root)
            self.assertEqual(readback.returncode, 0, readback.stderr + readback.stdout)
            shown = json.loads(readback.stdout)
            op = shown["ordinary_operation"]
            self.assertEqual(op["result_refs"], [revision["record_id"]])
            self.assertEqual(op["result"]["calculation_version"], TEMPORAL_CALCULATION_VERSION)
            self.assertEqual(op["result"]["result_coherence"], "COHERENT")
            self.assertEqual(op["status"], "PAUSED_CAP")
            self.assertEqual(op["protocol_main_used"], 1)
            self.assertEqual(op["owner_main_remaining"], 0)
            self.assertTrue(op["search_open"])
            self.assertEqual(shown["next_action"], "AUTHORIZE_ADDITIONAL_LOOKS")
            self.assertNotIn("NO_WORTHY", json.dumps(shown.get("owner_final")))
            self.assertEqual(op["compound_status"], "NOT_STARTED")
            self.assertEqual(
                sum(1 for item in _journal_looks(data_root, journal) if item.get("search_tier") == "COMPOUND_SCREEN"), 0
            )

            # 8. Candidate branch on the isolated copy: revision -> card -> freeze -> Critic -> cold readback.
            self._candidate_branch(forge, ctx, candidate_root, v3_ref, v3_sha, ids)

    def _candidate_branch(self, forge, ctx, root: Path, v3_ref: str, v3_sha: str, ids: list[str]) -> None:
        from tests.test_fast_lane_classifier import experiment_spec
        from tests.test_hfic_cli import bind_draft, run_cli

        code, evidence = self._execute(forge, ctx, data_root=root, correction=(v3_ref, v3_sha))
        self.assertEqual(code, 0, evidence)
        self.assertEqual(evidence["queries"][0]["look_class"], "CALCULATION_REVISION")
        self.assertFalse(evidence["queries"][0]["new_look"])
        self.assertEqual(evidence["record_delta"], {"discovery_look_records": 1})
        self.assertEqual(evidence["scientific_look_delta"], {"main": 0, "adaptive": 0})
        self.assertEqual(evidence["revision_of"]["record_id"], v3_ref)
        self.assertEqual(evidence["look_scope_relation"], "LOOK_SCOPE_MATCH")
        self.assertGreater(evidence["result"]["mean_target"], 0.0)
        workspace = ctx["workspace"]
        source = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8"))
        card = dict(source["candidates"][0])
        card.update({key: ctx["scope"][key] for key in ("population", "decision_timestamp", "target", "estimand", "explanatory_condition")})
        receipt = ctx["receipt"]
        draft = bind_draft({**source, "candidates": [card]}, receipt)
        draft.pop("runner_up_candidate_ref", None)
        draft.pop("strongest_rejected_alternative", None)
        draft["selected_candidate_ref"] = card["label"]
        draft["grounded_evidence"] = evidence
        draft["owner_focus"] = FOCUS
        draft_path = workspace / "candidate-draft.json"
        receipt_path = workspace / "candidate-receipt.json"
        draft_path.write_text(json.dumps(draft), encoding="utf-8")
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        persisted = run_cli(
            "persist-draft", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path),
            "--representation-id", "BASE", "--format", "json", data_root=root,
        )
        self.assertEqual(persisted.returncode, 0, persisted.stderr + persisted.stdout)
        opened = run_cli("preflight", "--discovery-contract", "--owner-focus", FOCUS, "--format", "json", data_root=root)
        self.assertEqual(opened.returncode, 0, opened.stderr + opened.stdout)
        resume_path = workspace / "candidate-resume.json"
        resume_path.write_text(opened.stdout, encoding="utf-8")
        frozen_run = run_cli(
            "freeze", "--draft", str(draft_path), "--preflight-receipt", str(resume_path), "--format", "json", data_root=root
        )
        self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr + frozen_run.stdout)
        frozen = json.loads(frozen_run.stdout)
        handed = frozen["critic_input_packet"]["grounded_evidence"]
        self.assertEqual(handed["result_refs"], evidence["result_refs"])
        self.assertEqual(handed["result"]["calculation_version"], TEMPORAL_CALCULATION_VERSION)
        self.assertEqual(handed["result"]["by_cohort"], evidence["result"]["by_cohort"])
        self.assertEqual(_cohort(handed["result"], ids[2])["observed_target_n"], 0)
        self.assertEqual(temporal_result_coherence(handed["result"])["status"], "COHERENT")
        critic = {
            "schema": "smial.hypothesis-critic-result",
            "schema_version": "1.1",
            "session_id": frozen["session_id"],
            "critic_input_packet_sha256": frozen["critic_input_packet_sha256"],
            "selected_candidate_id": frozen["selected_candidate_id"],
            "selected_definition_sha256": frozen["selected_definition_sha256"],
            "critic_prompt_version": "HFIC-V1.1",
            "isolated_context_attestation": "NEW_CONTEXT_REQUIRED",
            "critic_terminal": "PASS_TO_CLASSIFICATION",
            "next": "STOP",
            "authority": {"git_mutation": 0, "experiment_execution": 0, "provider_api_rpc_wss_calls": 0},
            "non_claims": ["NO_ALPHA", "SCRIPTED_CRITIC_MECHANICAL"],
        }
        critic_path = workspace / "candidate-critic.json"
        critic_path.write_text(json.dumps(critic), encoding="utf-8")
        waiting = run_cli(
            "finalize", "--session-id", str(frozen["session_id"]), "--critic-result", str(critic_path),
            "--format", "json", data_root=root,
        )
        self.assertEqual(waiting.returncode, 0, waiting.stderr + waiting.stdout)
        self.assertEqual(json.loads(waiting.stdout).get("session_state"), "AWAITING_CLASSIFICATION")
        packet = {
            "experiment_spec": experiment_spec(),
            "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
        }
        packet["experiment_spec"]["required_feature_ids"] = list(card.get("required_feature_ids") or [])
        packet_path = workspace / "candidate-classify.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        classified = run_cli(
            "classify", "--session-id", str(frozen["session_id"]), "--experiment-spec", str(packet_path),
            "--format", "json", data_root=root,
        )
        self.assertEqual(classified.returncode, 0, classified.stderr + classified.stdout)
        done = json.loads(classified.stdout)
        self.assertEqual(done.get("session_state"), "SYNTHESIS_COMPLETE", done)
        self.assertEqual(done.get("critic_input_packet_sha256"), frozen["critic_input_packet_sha256"])
        cold = run_cli("forge-run", "--owner-focus", FOCUS, "--no-write", "--format", "json", data_root=root)
        self.assertEqual(cold.returncode, 0, cold.stderr + cold.stdout)
        shown = json.loads(cold.stdout)
        self.assertEqual(shown["ordinary_operation"]["result_refs"], evidence["result_refs"])
        self.assertEqual(shown["ordinary_operation"]["protocol_main_used"], 1)
        self.assertNotEqual(shown["next_action"], "CORRECT_CALCULATION_REVISION")
        self._consumer(root, evidence)

    def _consumer(self, root: Path, evidence: dict) -> None:
        from solana_alpha_lab.factory.document_runner import DocumentRunner, RunContext
        from solana_alpha_lab.factory.lane_classifier import classify_lane
        from solana_alpha_lab.factory.operational_store import OperationalStore
        from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
        from tests.test_fast_lane_classifier import AS_OF, HYPOTHESIS_DEFINITION_SHA256
        from tests.test_hfic_temporal_production_runner_v1 import _bind_experiment

        recipe = evidence["result"]["experiment_recipe"]
        experiment = _bind_experiment(recipe, root)
        decision = classify_lane(
            {"experiment_spec": experiment, "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256},
            root=ROOT,
            data_root=root,
            as_of=AS_OF,
        )
        self.assertEqual(decision.terminal, "FAST_LANE_READY", decision.reason_codes)
        ops = OperationalStore(root / "ops" / "operational_state.sqlite")
        try:
            result = DocumentRunner(root=ROOT, store=ops).start_document(
                experiment,
                spec_sha256=experiment_spec_sha256(experiment),
                run_context=RunContext(
                    data_root=root,
                    hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                    lane_decision=decision,
                ),
            )
        finally:
            ops.close()
        self.assertEqual(result["status"], "COMPLETE", result)
        run_id = str(result["run_id_or_null"])
        artifact = root / "research" / "artifacts" / "results" / f"RESULT-ARTIFACT-{run_id.removeprefix('RUN-')}.json"
        saved = json.loads(artifact.read_text(encoding="utf-8"))["capability_result"]["summary"]
        # Same recipe and input: the consumer reproduces the corrected revision byte for byte.
        self.assertEqual(saved["calculation_version"], TEMPORAL_CALCULATION_VERSION)
        self.assertEqual(saved["by_cohort"], evidence["result"]["by_cohort"])
        self.assertEqual(result_sha256(saved), evidence["result_sha256"])


class RevisionGateTests(unittest.TestCase):
    """Unit binder: explicit correction, cap 0, clocks, closed slots."""

    def _stored_v3(self, raw: Path, parts, *, cap_main):
        from solana_alpha_lab.factory.hfic_ordinary_operation import record_operation

        census, observations = _rows(parts)
        binding = [_bind(COHORT, RELEASE)]
        journal = "44" * 32
        market = "ab" * 32
        spec = _query("gate-revision")
        store = ResearchStore(raw)
        operation = record_operation(
            store,
            {
                "owner_request_text": "revision gate",
                "owner_focus": "REVISION_GATE",
                "journal_scope": journal,
                "market_evidence_epoch_sha256": market,
                "spec": spec,
                "owner_cap": {"main": cap_main, "adaptive": 0, "preview": 0},
                "requested_completion": "LIMITED_RESULT",
            },
        )
        kwargs = dict(
            census=census,
            observations=observations,
            spec=spec,
            binding=binding,
            journal_scope=journal,
            candidate_scope={},
            git_sha=GIT_SHA,
            operation_sha256=operation["operation_sha256"],
            verified_market=market,
        )
        with old_writer():
            evidence = run_recorded_discovery_query(ResearchStore(raw), **kwargs)
        return evidence, kwargs

    def test_revision_needs_no_cap_and_never_reserves(self) -> None:
        from solana_alpha_lab.factory.hfic_ordinary_operation import _reservations, gate_before_values

        parts = [
            _member_rows("m", COHORT, RELEASE, mark=MATCH, exit_price=1.2),
            _member_rows("u", COHORT, RELEASE, mark=MISS, exit_price=3.0),
        ]
        with tempfile.TemporaryDirectory() as raw:
            evidence, kwargs = self._stored_v3(Path(raw), parts, cap_main=1)
            op_sha = kwargs["operation_sha256"]
            store = ResearchStore(Path(raw))
            gate_args = dict(
                operation_sha256=op_sha,
                spec=kwargs["spec"],
                journal_scope=kwargs["journal_scope"],
                binding_cohorts=kwargs["binding"],
                verified_market=kwargs["verified_market"],
            )
            plain = gate_before_values(store, **gate_args)
            self.assertEqual(plain["disposition"], "REPLAY")
            self.assertEqual(plain["result_readout"]["result_coherence"], "INCOHERENT")
            self.assertEqual(plain["result_readout"]["next_action"], "CORRECT_CALCULATION_REVISION")
            correction = {
                "source_result_ref": evidence["result_refs"][0],
                "source_result_sha256": evidence["result_sha256"],
            }
            gate = gate_before_values(store, correction=correction, **gate_args)
            self.assertEqual(gate["disposition"], "CORRECTION")
            self.assertFalse(gate["writes"])
            self.assertEqual(len(_reservations(store, op_sha)), 1)
            with mock.patch(
                "solana_alpha_lab.factory.hfic_ordinary_operation._closed_slot", return_value=True
            ):
                with self.assertRaises(Exception) as closed:
                    gate_before_values(store, correction=correction, **gate_args)
            self.assertEqual(getattr(closed.exception, "code", None), "ORDINARY_OPERATION_SLOT_CLOSED")
            revised = run_recorded_discovery_query(ResearchStore(Path(raw)), correction=correction, **kwargs)
            self.assertEqual(revised["queries"][0]["look_class"], "CALCULATION_REVISION")
            self.assertEqual(revised["budget"]["main_count"], 1)
            self.assertEqual(len(_reservations(ResearchStore(Path(raw)), op_sha)), 1)
            # A repeat of the same correction reads the saved revision, no evaluator, no duplicate.
            with mock.patch.object(temporal, "execute_temporal_discovery", side_effect=AssertionError("rerun")):
                again = run_recorded_discovery_query(ResearchStore(Path(raw)), correction=correction, **kwargs)
            self.assertEqual(again["result_refs"], revised["result_refs"])
            self.assertEqual(again["revision_of"]["record_id"], correction["source_result_ref"])
            self.assertEqual(len(list_discovery_looks(ResearchStore(Path(raw)), kwargs["journal_scope"])), 2)
            wrong = {**correction, "source_result_sha256": "0" * 64}
            with self.assertRaises(Exception) as garbage:
                gate_before_values(ResearchStore(Path(raw)), correction=wrong, **gate_args)
            self.assertEqual(getattr(garbage.exception, "code", None), "CALCULATION_REVISION_SOURCE_HASH_MISMATCH")

    def test_changed_clock_is_not_a_free_revision(self) -> None:
        parts = [
            _member_rows("m", COHORT, RELEASE, mark=MATCH, exit_price=1.2),
            _member_rows("u", COHORT, RELEASE, mark=MISS, exit_price=3.0),
        ]
        with tempfile.TemporaryDirectory() as raw:
            evidence, kwargs = self._stored_v3(Path(raw), parts, cap_main=1)
            before = _inventory(Path(raw))
            correction = {
                "source_result_ref": evidence["result_refs"][0],
                "source_result_sha256": evidence["result_sha256"],
            }
            moved = [dict(item, schedule_lateness_seconds=600) for item in kwargs["binding"]]
            with self.assertRaises(GroundedDiscoveryError) as refused:
                run_recorded_discovery_query(ResearchStore(Path(raw)), correction=correction, **{**kwargs, "binding": moved})
            self.assertEqual(refused.exception.code, "CALCULATION_REVISION_INPUT_MISMATCH")
            self.assertEqual(_inventory(Path(raw)), before)
            with self.assertRaises(GroundedDiscoveryError) as bare:
                run_recorded_discovery_query(
                    ResearchStore(Path(raw)),
                    correction={"source_result_ref": evidence["result_refs"][0]},
                    **kwargs,
                )
            self.assertEqual(bare.exception.code, "CALCULATION_REVISION_SOURCE_REQUIRED")

    def test_coherent_old_version_is_superseded_explicitly(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import assert_computed_grounded_evidence

        parts = [
            _member_rows("a", COHORT, RELEASE, mark=MATCH, exit_price=1.2),
            _member_rows("b", COHORT, RELEASE, mark=MATCH, exit_price=0.9),
        ]
        with tempfile.TemporaryDirectory() as raw:
            evidence, kwargs = self._stored_v3(Path(raw), parts, cap_main=1)
            self.assertEqual(temporal_result_coherence(evidence["result"])["status"], "COHERENT")
            assert_computed_grounded_evidence(ResearchStore(Path(raw)), evidence)
            correction = {
                "source_result_ref": evidence["result_refs"][0],
                "source_result_sha256": evidence["result_sha256"],
            }
            revised = run_recorded_discovery_query(ResearchStore(Path(raw)), correction=correction, **kwargs)
            self.assertEqual(revised["revision_of"]["reason"]["code"], "CALCULATION_VERSION_SUPERSEDED")
            self.assertEqual(revised["result"]["by_cohort"], evidence["result"]["by_cohort"])
            with self.assertRaises(GroundedDiscoveryError) as superseded:
                assert_computed_grounded_evidence(ResearchStore(Path(raw)), evidence)
            self.assertEqual(superseded.exception.code, "GROUNDED_RESULT_SUPERSEDED")
            assert_computed_grounded_evidence(ResearchStore(Path(raw)), revised)

    def test_revision_without_explicit_correction_is_refused_not_spent(self) -> None:
        from solana_alpha_lab.factory.hfic_ordinary_operation import (
            OrdinaryOperationError,
            gate_before_values,
            record_operation,
        )

        parts = [_member_rows("m", COHORT, RELEASE, mark=MATCH, exit_price=1.2)]
        with tempfile.TemporaryDirectory() as raw:
            evidence, kwargs = self._stored_v3(Path(raw), parts, cap_main=1)
            store = ResearchStore(Path(raw))
            other = record_operation(
                store,
                {
                    "owner_request_text": "another request, cap zero",
                    "owner_focus": "REVISION_GATE",
                    "journal_scope": kwargs["journal_scope"],
                    "market_evidence_epoch_sha256": kwargs["verified_market"],
                    "spec": kwargs["spec"],
                    "owner_cap": {"main": 0, "adaptive": 0, "preview": 0},
                    "requested_completion": "LIMITED_RESULT",
                },
            )
            with self.assertRaises(OrdinaryOperationError) as refused:
                gate_before_values(
                    store,
                    operation_sha256=other["operation_sha256"],
                    spec=kwargs["spec"],
                    journal_scope=kwargs["journal_scope"],
                    binding_cohorts=kwargs["binding"],
                    verified_market=kwargs["verified_market"],
                )
            self.assertEqual(refused.exception.code, "CALCULATION_REVISION_REQUIRES_EXPLICIT_CORRECTION")
            with self.assertRaises(OrdinaryOperationError) as foreign:
                gate_before_values(
                    store,
                    operation_sha256=other["operation_sha256"],
                    spec=kwargs["spec"],
                    journal_scope=kwargs["journal_scope"],
                    binding_cohorts=kwargs["binding"],
                    verified_market=kwargs["verified_market"],
                    correction={
                        "source_result_ref": evidence["result_refs"][0],
                        "source_result_sha256": evidence["result_sha256"],
                    },
                )
            self.assertEqual(foreign.exception.code, "CALCULATION_REVISION_OPERATION_MISMATCH")


if __name__ == "__main__":
    unittest.main()
