"""Query 1.2 list scope on the temporal executor (D10/D11/D12/D16, direct level).

Literal oracle from the PRD fixture (section 17.1); the production-shaped
multi-process proof lives in test_hfic_list_aware_vertical_v1.
"""

from __future__ import annotations

import copy
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from solana_alpha_lab.factory import hfic_research_scope as rs  # noqa: E402
from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError  # noqa: E402
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    execute_temporal_discovery,
    validate_temporal_query,
)
from tests.test_opportunity_episodes_contract_v1 import (  # noqa: E402
    COHORT,
    HOLD,
    LIQ,
    PRICE,
    RELEASE,
    binding_item,
    obs_row,
)

SCHEDULE = {
    "nomination": {
        "primitive_id": "PRIM-JUPITER-TOKENS-V2-CATEGORY-NOMINATION-001",
        "sources": [
            {"source_id": "toporganicscore_5m", "category": "toporganicscore", "interval": "5m", "limit": 100},
            {"source_id": "toptraded_5m", "category": "toptraded", "interval": "5m", "limit": 100},
            {"source_id": "toptrending_5m", "category": "toptrending", "interval": "5m", "limit": 100},
        ],
    }
}
A, B, C = "JUPITER:toporganicscore:5m", "JUPITER:toptraded:5m", "JUPITER:toptrending:5m"
# episode -> (lists, numeric signal, target return or None)
FIXTURE = {
    "e1": ("A", True, 0.10),
    "e2": ("B", False, -0.20),
    "e3": ("C", True, 0.30),
    "e4": ("AB", True, 0.40),
    "e5": ("AC", False, -0.10),
    "e6": ("BC", True, None),
    "e7": ("ABC", True, 0.20),
}
T0 = "2026-10-05T00:02:10Z"
LIST_OF = {"A": A, "B": B, "C": C}


def corpus():
    census, rows = [], []
    for episode, (_lists, signal, target) in FIXTURE.items():
        mint = f"Mint{episode}".ljust(40, "x")
        census.append({"cohort_id": COHORT, "release_id": RELEASE, "episode_id": episode, "mint": mint, "t0": T0})
        holders300, holders1800 = (60, 75) if signal else (60, 55)
        for point, available, price, holders in (
            ("E300", "2026-10-05T00:10:04Z", 1.0, holders300),
            ("E1800", "2026-10-05T00:35:09Z", 1.0, holders1800),
            ("E14400", "2026-10-05T04:05:08Z", None if target is None else 1.0 + target, 80),
        ):
            for field, value in ((PRICE, price), (HOLD, holders), (LIQ, 12000)):
                if point == "E14400" and target is None:
                    rows.append(obs_row(episode, mint, point, field, None, available="2026-10-05T04:10:00Z", state="CENSORED"))
                else:
                    rows.append(obs_row(episode, mint, point, field, value, available=available))
    return census, rows


def evidence(unknown: dict[str, str] | None = None):
    ev = rs.MembershipEvidence()
    for definition in rs.jupiter_definitions(SCHEDULE).values():
        ev.add_definition(definition)
    for episode, (lists, _s, _t) in FIXTURE.items():
        ev.states[episode] = {LIST_OF[x]: (rs.TRUE if x in lists else rs.FALSE) for x in "ABC"}
        ev.t0[episode] = datetime(2026, 10, 5, 0, 2, 10, tzinfo=UTC)
    for episode, letter in (unknown or {}).items():
        ev.states[episode][LIST_OF[letter]] = rs.UNKNOWN
    ev.bindings.append({"adapter": "TEST", "note": "direct-level fixture"})
    return ev


def spec(kind, **parts):
    base = {
        "schema": "smial.hfic-temporal-query",
        "schema_version": "1.2",
        "query_id": "Q",
        "population": "OPPORTUNITY_EPISODES",
        "anchor_kind": "NOMINATION_T0",
        "time_contract": {"schedule_contract": "OPPORTUNITY_EPISODE_SCHEDULE_V1", "time_feature_clock": "FIRST_RELIABLE_AVAILABLE_AT"},
        "search_tier": "COMPOUND_SCREEN",
        "budget_allocation": "COMPOUND_FIRST",
        "decision": {"point_id": "E1800"},
        "features": [],
        "all": [],
        "target": {"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E1800", "exit_point": "E14400", "field_id": PRICE},
        "entry_model": {"kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT", "assumed_latency_seconds": 0},
        "hypothesis_kind": kind,
        "research_scope": {},
    }
    base.update(parts)
    return base


NUMERIC = {
    "features": [{"name": "d_holders", "op": "delta", "field_id": HOLD, "start": "E300", "end": "E1800"}],
    "all": [{"feature": "d_holders", "op": "gt", "value": 0}],
}
AC = {"clauses": [{"all_of": ["A", "C"]}]}
ALIASES = {"A": A, "B": B, "C": C}


def run(draft, ev=None, *, resolved_override=None):
    ev = ev or evidence()
    draft = dict(draft, list_aliases=ALIASES)
    query = rs.canonicalize_query_scope(draft, ev)
    bound = validate_temporal_query(query)["scientific_body"]
    census, rows = corpus()
    resolved = rs.ResolvedScope(
        scope=bound["research_scope"],
        list_condition=bound.get("list_condition"),
        evidence=ev,
        episode_ids=[row["episode_id"] for row in census],
        slices=bound.get("diagnostic_slices") or [],
    )
    return execute_temporal_discovery(
        census, rows, query, [binding_item()], research_scope=resolved_override or resolved
    )["summary"]


class ScopedExecutorTests(unittest.TestCase):
    def test_list_only_contrast_literal(self) -> None:
        out = run(spec("LIST_CONTRAST", list_condition=AC))
        scope = out["research_scope"]
        self.assertEqual(out["research_scope"]["hypothesis_kind"], "LIST_CONTRAST")
        self.assertEqual(scope["base_admitted_n"], 7)
        self.assertEqual(scope["matched"]["n"], 2)
        self.assertEqual(scope["matched"]["target_observed_n"], 2)
        self.assertAlmostEqual(scope["matched"]["mean_target"], 0.05, places=9)
        comp = scope["contrast"]["comparator"]
        self.assertEqual((comp["n"], comp["target_observed_n"], comp["target_missing_n"]), (5, 4, 1))
        self.assertAlmostEqual(comp["mean_target"], 0.15, places=9)
        self.assertEqual(scope["contrast"]["status"], "EVALUATED")
        self.assertAlmostEqual(scope["contrast"]["observed_target_difference"], -0.10, places=9)
        self.assertEqual(out["feature_unknown_n"], 0)

    def test_numeric_mechanism_inside_scope_literal(self) -> None:
        draft = spec("NUMERIC_IN_SCOPE", research_scope={"universe_selector": AC}, **NUMERIC)
        out = run(draft)
        scope = out["research_scope"]
        self.assertEqual(scope["universe_pass_n"], 2)
        self.assertEqual(out["decision_eligible_n"], 2)
        self.assertEqual(out["matched_n"], 1)
        self.assertAlmostEqual(out["mean_target"], 0.20, places=9)
        self.assertAlmostEqual(out["baseline"]["mean_target"], 0.05, places=9)
        self.assertNotIn("contrast", scope)

    def test_mixed_list_numeric(self) -> None:
        out = run(spec("MIXED_LIST_NUMERIC", list_condition=AC, **NUMERIC))
        scope = out["research_scope"]
        # A&C with a rising holder count: only e7 (e5 has falling holders)
        self.assertEqual(scope["matched"]["n"], 1)
        self.assertAlmostEqual(scope["matched"]["mean_target"], 0.20, places=9)
        self.assertEqual(scope["contrast"]["comparator"]["n"], 7)

    def test_intersection_minus_b_and_pooled_control(self) -> None:
        out = run(spec("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A", "C"], "none_of": ["B"]}]}))
        self.assertEqual(out["research_scope"]["matched"]["n"], 1)  # e5 only
        # missing e6 stays in the comparator denominator
        self.assertEqual(out["research_scope"]["contrast"]["comparator"]["n"], 6)

    def test_slices_are_overlapping_and_reported(self) -> None:
        slices = [
            {"slice_id": "A", "selector": {"clauses": [{"all_of": ["A"]}]}},
            {"slice_id": "two_plus", "selector": {"clauses": [{"count": {"of": ["A", "B", "C"], "min": 2, "max": 3}}]}},
        ]
        out = run(spec("LIST_CONTRAST", list_condition=AC, diagnostic_slices=slices))
        by = {item["slice_id"]: item for item in out["research_scope"]["diagnostic_slices"]}
        self.assertEqual(by["A"]["decision_eligible"]["n"], 4)
        self.assertEqual(by["two_plus"]["decision_eligible"]["n"], 4)
        self.assertEqual(by["two_plus"]["decision_eligible"]["target_missing_n"], 1)
        self.assertTrue(out["research_scope"]["slices_overlap_not_additive"])

    def test_degenerate_groups_are_typed_not_alpha(self) -> None:
        empty = run(spec("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A", "B", "C"], "none_of": []}, ]}), evidence())
        self.assertEqual(empty["research_scope"]["matched"]["n"], 1)
        every = run(spec("LIST_CONTRAST", list_condition={"clauses": [{"count": {"of": ["A", "B", "C"], "min": 0, "max": 3}}]}))
        self.assertEqual(every["research_scope"]["contrast"]["status"], "EMPTY_COMPARATOR")
        self.assertIsNone(every["research_scope"]["contrast"]["observed_target_difference"])

    def test_unknown_membership_refuses_before_values(self) -> None:
        with self.assertRaises(GroundedDiscoveryError) as caught:
            run(spec("LIST_CONTRAST", list_condition=AC), evidence({"e3": "A"}))
        self.assertEqual(caught.exception.code, "SCOPE_COVERAGE_UNRESOLVED")

    def test_identical_universe_and_signal_is_non_discriminating(self) -> None:
        with self.assertRaises(GroundedDiscoveryError) as caught:
            run(spec("LIST_CONTRAST", research_scope={"universe_selector": AC}, list_condition=AC))
        self.assertEqual(caught.exception.code, "NON_DISCRIMINATING_CONDITION")

    def test_scope_cannot_be_dropped_or_swapped(self) -> None:
        ev = evidence()
        draft = spec("LIST_CONTRAST", list_condition=AC, list_aliases=ALIASES)
        query = rs.canonicalize_query_scope(draft, ev)
        census, rows = corpus()
        # legacy 1.1 cannot carry scope fields
        legacy = copy.deepcopy(query)
        legacy["schema_version"] = "1.1"
        with self.assertRaises(GroundedDiscoveryError) as caught:
            validate_temporal_query(legacy)
        self.assertEqual(caught.exception.code, "SCOPE_FIELDS_REQUIRE_QUERY_1_2")
        # 1.2 without a scope
        missing = {k: v for k, v in query.items() if k != "research_scope"}
        with self.assertRaises(GroundedDiscoveryError):
            validate_temporal_query(missing)
        # executor without masks / with masks of another rule
        with self.assertRaises(GroundedDiscoveryError) as caught:
            execute_temporal_discovery(census, rows, query, [binding_item()])
        self.assertEqual(caught.exception.code, "RESEARCH_SCOPE_BINDING_MISMATCH")
        other = rs.canonicalize_query_scope(spec("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A"]}]}, list_aliases=ALIASES), ev)
        body = validate_temporal_query(other)["scientific_body"]
        wrong = rs.ResolvedScope(scope=body["research_scope"], list_condition=body["list_condition"], evidence=ev, episode_ids=[r["episode_id"] for r in census])
        with self.assertRaises(GroundedDiscoveryError) as caught:
            execute_temporal_discovery(census, rows, query, [binding_item()], research_scope=wrong)
        self.assertEqual(caught.exception.code, "RESEARCH_SCOPE_BINDING_MISMATCH")
        # legacy unscoped query refuses injected masks
        legacy_query = {k: v for k, v in query.items() if k not in rs_fields()}
        legacy_query["schema_version"] = "1.1"
        legacy_query.update(NUMERIC)
        with self.assertRaises(GroundedDiscoveryError) as caught:
            execute_temporal_discovery(census, rows, legacy_query, [binding_item()], research_scope=wrong)
        self.assertEqual(caught.exception.code, "RESEARCH_SCOPE_BINDING_MISMATCH")

    def test_identity_depends_on_rule_not_on_aliases_or_evidence(self) -> None:
        ev = evidence()
        one = validate_temporal_query(rs.canonicalize_query_scope(spec("LIST_CONTRAST", list_condition=AC, list_aliases=ALIASES), ev))
        renamed = {"X": A, "Y": B, "Z": C}
        two = validate_temporal_query(
            rs.canonicalize_query_scope(
                spec("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["Z", "X"]}]}, list_aliases=renamed), ev
            )
        )
        self.assertEqual(one["spec_sha256"], two["spec_sha256"])
        scope_only = validate_temporal_query(
            rs.canonicalize_query_scope(spec("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A", "B"]}]}, list_aliases=ALIASES), ev)
        )
        self.assertNotEqual(one["spec_sha256"], scope_only["spec_sha256"])


def rs_fields():
    return {"research_scope", "list_condition", "hypothesis_kind", "contrast", "diagnostic_slices"}


class LegacyGoldenTests(unittest.TestCase):
    """D28: the unscoped 1.1 path is byte-identical to base 77eb427a (values pinned on base)."""

    def test_unscoped_query_and_result_are_unchanged(self) -> None:
        import hashlib
        import json

        from solana_alpha_lab.factory.hfic_temporal_discovery import canonical_temporal_spec
        from tests.test_opportunity_episodes_contract_v1 import episode_spec, prd_vector

        self.assertEqual(validate_temporal_query(episode_spec())["spec_sha256"], "d552ad67a882557915222aaac5b25692c368eae4e3dbd69cbf5d76515499b002")
        canonical = json.dumps(canonical_temporal_spec(episode_spec()), sort_keys=True).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), "d6d9bf1cc1067b1af61f1be511bf5c75b8c9053c7570bac33fef4023e91602b0")
        census, rows = prd_vector()
        summary = execute_temporal_discovery(census, rows, episode_spec(), [binding_item()])["summary"]
        digest = hashlib.sha256(json.dumps(summary, sort_keys=True, default=str).encode()).hexdigest()
        self.assertEqual(digest, "ea362e98ea083068408c6dad94671e04a9a91e2a121331a8ee539dc557a4461d")
        self.assertNotIn("research_scope", summary)


class SliceCoverageTests(unittest.TestCase):
    def test_unknown_membership_in_a_slice_is_not_out_of_the_slice(self) -> None:
        ev = evidence()
        for definition in [{"list_id": "OWNER:D", "definition_version": "1", "provider_or_owner": "OWNER", "kind": "MANUAL_SET", "semantics": {}, "adapter": rs.LOCAL_ADAPTER}]:
            ev.add_definition({**definition, "aliases": [], "definition_sha256": rs.sha256_of(definition)})
        for episode in FIXTURE:
            ev.states[episode]["OWNER:D"] = rs.TRUE if episode in {"e1", "e2"} else rs.UNKNOWN
        draft = spec("LIST_CONTRAST", list_condition=AC, diagnostic_slices=[{"slice_id": "D", "selector": {"clauses": [{"all_of": ["D"]}]}}])
        query = rs.canonicalize_query_scope(dict(draft, list_aliases={**ALIASES, "D": "OWNER:D"}), ev)
        body = validate_temporal_query(query)["scientific_body"]
        resolved = rs.ResolvedScope(scope=body["research_scope"], list_condition=body["list_condition"], evidence=ev,
                                    episode_ids=list(FIXTURE), slices=body["diagnostic_slices"])
        census, rows = corpus()
        with self.assertRaises(GroundedDiscoveryError) as caught:
            execute_temporal_discovery(census, rows, query, [binding_item()], research_scope=resolved)
        self.assertEqual(caught.exception.code, "SCOPE_COVERAGE_UNRESOLVED")
        self.assertEqual(resolved.coverage()["slice_D_unknown_n"], 5)
        with self.assertRaises(rs.ResearchScopeError) as refused:
            resolved.require_covered()
        self.assertIn("next_action", refused.exception.detail)


class MixedAblationTests(unittest.TestCase):
    """P1-B: dropping the numeric condition of A∩C + holders↑ yields A∩C, never all decision-eligible episodes."""

    def test_numeric_ablation_keeps_the_list_signal(self) -> None:
        out = run(spec("MIXED_LIST_NUMERIC", list_condition=AC, **NUMERIC))
        self.assertEqual(out["research_scope"]["matched"]["n"], 1)  # e7
        (ablation,) = out["ablations"]
        # A∩C = e5 (-0.10) and e7 (+0.20); the widened (wrong) set would be 6 observed with mean 7/60.
        self.assertEqual(ablation["observed_n"], 2)
        self.assertAlmostEqual(ablation["mean_target"], 0.05, places=9)
        self.assertTrue(ablation["list_condition_preserved"])

    def test_widened_ablation_is_incoherent(self) -> None:
        import copy

        from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_result_coherence

        out = run(spec("MIXED_LIST_NUMERIC", list_condition=AC, **NUMERIC))
        self.assertEqual(temporal_result_coherence(out)["status"], "COHERENT")
        widened = copy.deepcopy(out)
        widened["ablations"][0]["list_condition_preserved"] = False
        self.assertEqual(temporal_result_coherence(widened)["status"], "INCOHERENT")
        dropped = copy.deepcopy(out)
        dropped["ablations"][0].pop("list_condition_preserved")
        self.assertEqual(temporal_result_coherence(dropped)["status"], "INCOHERENT")

    def test_list_only_has_no_numeric_ablation(self) -> None:
        out = run(spec("LIST_CONTRAST", list_condition=AC))
        self.assertEqual(out["ablations"], [])


class ScopedPolicyShiftBindingTests(unittest.TestCase):
    """F1: a scoped look is "the same rows" only under the CURRENT applied masks."""

    def test_same_rows_under_policy_is_scope_aware(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            data_binding_sha256,
            same_rows_under_policy,
            scoped_binding_sha256,
        )

        census, rows = corpus()
        admitted = {"population": "OPPORTUNITY_EPISODES", "cohorts": [COHORT]}
        stamped = dict(admitted, universe_policy_semantic_sha256="p" * 64)
        raw = data_binding_sha256(stamped, census, rows)
        scoped_look = {"data_binding_sha256": scoped_binding_sha256(raw, "a" * 64), "result": {"research_scope": {"hypothesis_kind": "LIST_CONTRAST"}}}
        legacy_look = {"data_binding_sha256": raw, "result": {}}
        kwargs = dict(admitted=admitted, census=census, observations=rows, policy_sha="p" * 64)
        self.assertTrue(same_rows_under_policy(scoped_look, scope_applied_sha256="a" * 64, **kwargs))
        self.assertFalse(same_rows_under_policy(scoped_look, scope_applied_sha256="b" * 64, **kwargs))  # changed list evidence
        self.assertFalse(same_rows_under_policy(scoped_look, **kwargs))  # no current masks: not provable
        self.assertTrue(same_rows_under_policy(legacy_look, **kwargs))  # unscoped behaviour unchanged


if __name__ == "__main__":
    unittest.main()
