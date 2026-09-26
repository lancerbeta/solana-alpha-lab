"""Synthetic grounded-discovery proof. No live typed values and no market Forge."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    GroundedDiscoveryError,
    admit_discovery_binding,
    bind_prior_scope_evidence,
    classify_query_look,
    prior_scope_relation,
    summarize_discovery_query,
    validate_query_spec,
)

PRICE = "FIELD-USD-PRICE-001"
LIQ = "FIELD-LIQUIDITY-USD-001"
SPEC = {
    "query_id": "X300_PRICE_LIQ_TO_Y1800",
    "decision_points": ["X300"],
    "decision_fields": [PRICE, LIQ],
    "target_point": "Y1800",
    "target_field": PRICE,
    "explanatory": ["liquidity_high"],
    "population": "BASE_X",
}


def _member(
    member_id: str,
    *,
    cohort: str,
    block: str,
    target: float | None,
    flag: bool,
    state: str = "OBSERVED",
    leaked: bool = False,
    in_base: bool = True,
    decision_ready: bool = True,
) -> dict:
    return {
        "member_id": member_id,
        "cohort_id": cohort,
        "calendar_block": block,
        "in_base_x": in_base,
        "decision_ready": decision_ready,
        "decision_at": "2026-09-03T00:00:00+00:00",
        "target_state": state,
        "target_at": (
            "2026-09-03T00:00:00+00:00"
            if leaked
            else "2026-09-03T00:30:00+00:00"
        ),
        "synthetic_target": target,
        "explanatory": {"liquidity_high": flag},
    }


class GroundedDiscoveryTests(unittest.TestCase):
    def test_spec_rejects_cohort_feature_and_early_target(self) -> None:
        with self.assertRaises(GroundedDiscoveryError) as cohort:
            validate_query_spec({**SPEC, "explanatory": ["cohort_id"]})
        self.assertEqual(cohort.exception.code, "COHORT_NOT_A_FEATURE")
        with self.assertRaises(GroundedDiscoveryError) as early:
            validate_query_spec({**SPEC, "target_point": "X300"})
        self.assertEqual(early.exception.code, "TARGET_NOT_AFTER_DECISION")

    def test_binding_stops_on_ambiguous_role_before_values(self) -> None:
        with self.assertRaises(GroundedDiscoveryError) as exc:
            admit_discovery_binding(
                [
                    {
                        "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
                        "evidence_role": "UNSPECIFIED",
                        "cohort_id": "REL-A",
                        "release_id": "ab" * 32,
                        "census_sha256": "cd" * 32,
                        "observations_sha256": "ef" * 32,
                    }
                ]
            )
        self.assertEqual(exc.exception.code, "DISCOVERY_ROLE_AMBIGUOUS")

    def test_pooled_hides_conditional_and_blocks_accumulate(self) -> None:
        members = [
            _member("a", cohort="C1", block="B1", target=1.0, flag=True),
            _member("b", cohort="C1", block="B1", target=-1.0, flag=False),
            _member("c", cohort="C2", block="B2", target=1.0, flag=True),
            _member("d", cohort="C2", block="B2", target=-1.0, flag=False),
            _member("noise", cohort="C1", block="B1", target=None, flag=True, in_base=False),
        ]
        result = summarize_discovery_query(members, SPEC, overlap_members=[])
        self.assertTrue(result["pooled"]["independent_replication"])
        self.assertFalse(result["engine_emits_alpha"])
        self.assertEqual(result["base_x_n"], 4)
        self.assertEqual(result["pooled"]["mean_synthetic_target"], 0.0)
        high = next(item for item in result["by_explanatory"] if item["view"] == "liquidity_high=True")
        low = next(item for item in result["by_explanatory"] if item["view"] == "liquidity_high=False")
        self.assertEqual(high["mean_synthetic_target"], 1.0)
        self.assertEqual(low["mean_synthetic_target"], -1.0)
        self.assertEqual(len(result["by_calendar_block"]), 2)
        self.assertEqual(
            sum(item["target_observed_after_decision"] for item in result["by_calendar_block"]),
            4,
        )

    def test_null_missing_and_leakage_do_not_become_a_positive(self) -> None:
        members = [
            _member("n1", cohort="C1", block="B1", target=0.0, flag=False),
            _member("n2", cohort="C1", block="B1", target=0.0, flag=False),
            _member("miss", cohort="C1", block="B1", target=99.0, flag=False, state="MISSING_TYPED"),
            _member("late", cohort="C1", block="B1", target=99.0, flag=False, state="CENSORED_LATE"),
            _member("leak", cohort="C1", block="B1", target=99.0, flag=False, leaked=True),
            _member("gone", cohort="C1", block="B1", target=99.0, flag=False, state="ABSENT"),
        ]
        result = summarize_discovery_query(members, SPEC)
        self.assertFalse(result["pooled"]["independent_replication"])
        self.assertEqual(result["pooled"]["mean_synthetic_target"], 0.0)
        self.assertEqual(result["pooled"]["target_observed_after_decision"], 2)
        self.assertEqual(result["missing"]["missing_typed"], 1)
        self.assertEqual(result["missing"]["censored_late"], 1)
        self.assertEqual(result["missing"]["leaked"], 1)
        self.assertEqual(result["missing"]["absent"], 1)
        self.assertTrue(result["missing_is_not_zero"])

    def test_price_liquidity_query_does_not_require_traders(self) -> None:
        bound = validate_query_spec(SPEC)
        self.assertNotIn("FIELD-STATS5M-NUM-TRADERS-001", bound["decision_fields"])
        result = summarize_discovery_query(
            [_member("p", cohort="C1", block="B1", target=0.2, flag=True)],
            SPEC,
        )
        self.assertEqual(result["pooled"]["target_observed_after_decision"], 1)

    def test_overlap_is_not_independent_replication(self) -> None:
        result = summarize_discovery_query(
            [_member("o", cohort="C3", block="OVERLAP", target=1.0, flag=True)],
            SPEC,
            overlap_members=["o"],
        )
        self.assertTrue(result["overlap_is_not_independent_replication"])
        self.assertEqual(result["overlap_exposed_base_x"], 1)
        self.assertFalse(result["by_calendar_block"][0]["independent_replication"])

    def test_control_scope_does_not_block_a_different_question(self) -> None:
        prior = {
            "question_id": "TICKET_ASYMMETRY",
            "population": "BASE_X",
            "decision_timestamp": "X300",
            "target": "Y1800_PRICE",
            "estimand": "reported_path",
            "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        }
        candidate = {**prior, "question_id": "PRICE_LIQ_STATE"}
        self.assertEqual(
            prior_scope_relation(candidate, prior),
            "SCOPED_CONTROL_DOES_NOT_BLOCK",
        )
        self.assertEqual(prior_scope_relation(prior, prior), "EXACT_SCOPE_MATCH")
        bound = bind_prior_scope_evidence(
            {"candidate_scope": candidate, "priors": [prior]}
        )
        self.assertEqual(
            bound["prior_scope_relations"][0]["relation"],
            "SCOPED_CONTROL_DOES_NOT_BLOCK",
        )
        with self.assertRaises(GroundedDiscoveryError) as exact:
            bind_prior_scope_evidence(
                {"candidate_scope": prior, "priors": [prior]}
            )
        self.assertEqual(exact.exception.code, "EXACT_PRIOR_SCOPE_MATCH")

    def test_same_bytes_are_not_a_new_look_and_budget_is_finite(self) -> None:
        first = classify_query_look([], SPEC)
        self.assertTrue(first["new_look"])
        retry = classify_query_look([first], SPEC)
        self.assertFalse(retry["new_look"])
        self.assertEqual(retry["look_class"], "RETRY_SAME_BYTES")
        changed = {**SPEC, "target_point": "Y3600"}
        adaptive = classify_query_look([first], changed)
        self.assertEqual(adaptive["look_class"], "ADAPTIVE")
        previous = [first, adaptive]
        for index in range(5):
            previous.append(
                classify_query_look(
                    previous,
                    {**SPEC, "query_id": f"Q{index}", "target_point": "Y3600"},
                )
            )
        with self.assertRaises(GroundedDiscoveryError) as exc:
            classify_query_look(
                previous,
                {**SPEC, "query_id": "Q-EXTRA", "target_point": "Y900"},
            )
        self.assertEqual(exc.exception.code, "QUERY_MAIN_BUDGET_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
