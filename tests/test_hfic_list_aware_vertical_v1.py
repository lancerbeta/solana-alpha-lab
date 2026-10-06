"""List-aware Forge vertical (PRD V2, D01-D24 subset) on production owners.

Only transport, clock and authored market bytes are synthetic. Registration,
activation, ticks, admission, frames, export, release, import, preflight,
scope resolution, discovery and every artifact in between are production
owners. Expected numbers are literals from the PRD fixture (section 17.1).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from tests.test_opportunity_episodes_vertical_v1 import (  # noqa: E402
    AS_OF,
    DAY_A,
    DAY_B,
    END,
    STOPS,
    _consume,
    _discovery,
    _forge_call,
)

PRICE, LIQ, HOLD = "FIELD-USD-PRICE-001", "FIELD-LIQUIDITY-USD-001", "FIELD-HOLDER-COUNT-001"
CATEGORY = {"A": "toporganicscore", "B": "toptraded", "C": "toptrending"}
LIST_ID = {"A": "JUPITER:toporganicscore:5m", "B": "JUPITER:toptraded:5m", "C": "JUPITER:toptrending:5m"}
# label -> (lists, numeric signal, target return or None)  [PRD 17.1]
COHORT_A = {
    "e1": ("A", True, 0.10),
    "e2": ("B", False, -0.20),
    "e3": ("C", True, 0.30),
    "e4": ("AB", True, 0.40),
    "e5": ("AC", False, -0.10),
    "e6": ("BC", True, None),
    "e7": ("ABC", True, 0.20),
}
# next weekly cycle: e1 re-enters but only in C; its old A membership must not be inherited.
COHORT_B = {
    "e1": ("C", True, 0.05),
    "n1": ("AC", True, 0.30),
    "n2": ("B", True, -0.10),
}


def mint_of(label: str) -> str:
    from tests.test_opportunity_episodes_harness_v1 import synth_mint

    return synth_mint(f"LAV{label}x")


def rounds() -> list[tuple[str, str, datetime, tuple[str, bool, float | None]]]:
    out = []
    for index, (label, spec) in enumerate(COHORT_A.items()):
        out.append(("A", label, DAY_A + timedelta(minutes=15 * index), spec))
    for index, (label, spec) in enumerate(COHORT_B.items()):
        out.append(("B", label, DAY_B + timedelta(minutes=15 * index), spec))
    return out


def market_row(mint: str, now: datetime, start: datetime, signal: bool, target: float | None):
    from tests.test_opportunity_episodes_harness_v1 import token_object

    offset = (now - start).total_seconds()
    if offset < 1500:
        price, holders = 1.0, 60
    elif offset < 10000:
        price, holders = 1.0, (75 if signal else 55)
    else:
        if target is None:
            return None  # the mint vanishes before the exit: a gap, never a zero
        price, holders = 1.0 + target, 80
    return token_object(mint, price=price, liquidity=12000, holders=holders)


def build_market():
    from tests.test_opportunity_episodes_harness_v1 import SyntheticMarket, token_object

    market = SyntheticMarket()
    entries: dict[str, list[tuple[datetime, bool, float | None]]] = {}
    for _cohort, label, start, (lists, signal, target) in rounds():
        mint = mint_of(label)
        body = {CATEGORY[x]: [] for x in "ABC"}
        for letter in lists:
            body[CATEGORY[letter]].append(token_object(mint, price=1.0, liquidity=12000, holders=60))
        market.nominations[start] = body
        entries.setdefault(mint, []).append((start, signal, target))
    for mint, items in entries.items():
        items.sort()

        def series(now, items=items, mint=mint):
            latest = [item for item in items if item[0] <= now]
            if not latest:
                return None
            start, signal, target = latest[-1]
            return market_row(mint, now, start, signal, target)

        market.series[mint] = series
    return market


def tick_times() -> list[datetime]:
    times: set[datetime] = set()
    for _cohort, _label, start, _spec in rounds():
        times.add(start + timedelta(seconds=5))
        for offset in (300, 1800, 14400):
            times.add(start + timedelta(seconds=offset + 300 + 5))
    cursor = DAY_A + timedelta(hours=12, seconds=5)
    while cursor < END:
        times.add(cursor)
        cursor += timedelta(hours=12)
    times.add(END)
    return sorted(times)


def capture(work: Path) -> tuple[Path, list[str]]:
    from solana_alpha_lab.factory.live_cohort_vanilla_path import capture_freeze_export
    from tests.test_opportunity_episodes_harness_v1 import (
        build_schedule,
        cli_tick,
        register_authorize_activate,
        synth_mint,
        write_assignment,
    )
    from solana_alpha_lab.factory.research_store import ResearchStore

    data_root = work / "capture" / "rdp"
    data_root.mkdir(parents=True)
    assignment = write_assignment(
        data_root,
        [{"identity_kind": "MINT", "identity": synth_mint("KnownProtected"), "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}}],
    )
    schedule = build_schedule(starts_at=DAY_A, stops_at=STOPS, assignment=assignment)
    register_authorize_activate(data_root, schedule, now=DAY_A)
    ResearchStore(data_root).prepare_write_lookup()
    market = build_market()
    for at in tick_times():
        result = cli_tick(data_root, market, at)
        if result.get("terminal") == "TICK_REFUSED_NO_LIVE_DEFAULT":
            break
        if result.get("_exit_code") != 0:
            raise AssertionError(f"tick failed at {at}: {result}")
    imported: set[str] = set()
    packets = []
    for index in range(2):
        packet = capture_freeze_export(
            observation_rdp=data_root,
            ops_store=data_root / "observation_schedule_state.sqlite",
            imported_cohort_ids=set(imported),
            as_of=AS_OF,
            collection="OPPORTUNITY_EPISODES",
        )
        path = work / "capture" / f"packet-{index}.json"
        path.write_text(json.dumps(packet, default=str), encoding="utf-8")
        packets.append(str(path))
        imported.add(str(packet["cohort_id"]))
    return data_root, packets


def draft(kind: str, **parts: Any) -> dict[str, Any]:
    body = {
        "schema": "smial.hfic-temporal-query",
        "schema_version": "1.2",
        "query_id": f"LAV-{kind}",
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
        # Display aliases only: the first-class identity is the definition.
        "list_aliases": {"A": LIST_ID["A"], "B": LIST_ID["B"], "C": LIST_ID["C"]},
    }
    body.update(parts)
    return body


NUMERIC = {
    "features": [{"name": "d_holders", "op": "delta", "field_id": HOLD, "start": "E300", "end": "E1800"}],
    "all": [{"feature": "d_holders", "op": "gt", "value": 0}],
}
AC = {"clauses": [{"all_of": ["A", "C"]}]}


class ListAwareVerticalTests(unittest.TestCase):
    """One captured fixture, several production-owner proofs. The last test imports cohort B."""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        from solana_alpha_lab.factory.hfic_research_universe_policy import apply_universe_policy, preview_universe_policy
        from solana_alpha_lab.factory.research_store import ResearchStore

        cls._tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls._tmp.name)
        cls.source, cls.packets = capture(cls.work)
        cls.plane, cls.mirror = cls.work / "plane", cls.work / "mirror"
        cls.plane.mkdir()
        ResearchStore(cls.plane).prepare_write_lookup()
        first = _consume(cls.packets[:1], source=cls.source, mirror=cls.mirror, plane=cls.plane)
        assert first["_exit_code"] == 0, first
        store = ResearchStore(cls.plane)
        proposal = preview_universe_policy(store, min_holders=50, min_liquidity_usd=5000)["proposal"]
        apply_universe_policy(store, repo_root=ROOT, proposal=proposal, confirm_append_only=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _resolve(self, tag: str, query: dict[str, Any]) -> dict[str, Any]:
        path = self.work / f"{tag}-draft.json"
        path.write_text(json.dumps(query), encoding="utf-8")
        return _forge_call("research-scope-resolve", "--spec", str(path), data_root=self.plane)

    def _run(self, tag: str, query: dict[str, Any], *, focus: str) -> dict[str, Any]:
        from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation

        canonical = self._resolve(tag, query)["canonical_query"]
        pre = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", focus, data_root=self.plane)
        scope = {
            "population": "OPPORTUNITY_EPISODES",
            "decision_timestamp": "E1800",
            "target": temporal.temporal_target_label(canonical),
            "estimand": "price_relative_proxy",
            "explanatory_condition": canonical["hypothesis_kind"],
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
        }
        operation = _operation(
            canonical,
            focus=pre["owner_focus"],
            journal=pre["search_key_sha256"],
            market=pre["market_evidence_epoch_sha256"],
            text=f"List-aware vertical {tag}",
            cap={"main": 1, "adaptive": 0, "preview": 0},
            completion="LIMITED_RESULT",
        )
        evidence = _discovery(self.plane, self.work, tag=tag, spec=canonical, scope=scope, operation=operation)
        evidence["_preflight"] = pre
        evidence["_scope"] = scope
        return evidence

    def test_a_context_and_literal_results(self) -> None:
        # D09: the axis is in the emitted Prompt-A packet before any candidate exists.
        pre = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "LAV_CONTEXT", data_root=self.plane)
        context = pre["forge_context_packet"]["list_dimension_context"]
        self.assertEqual(context["admitted_episodes_n"], 7)
        by_id = {item["list_id"]: item for item in context["definitions"]}
        self.assertEqual({k: v["episodes_true_n"] for k, v in by_id.items()}, {LIST_ID["A"]: 4, LIST_ID["B"]: 4, LIST_ID["C"]: 4})
        self.assertEqual(sum(item["episodes_unknown_n"] for item in by_id.values()), 0)
        signatures = {tuple(item["member_list_ids"]): item["episodes_n"] for item in context["overlap_signatures"]}
        self.assertEqual(signatures[(LIST_ID["A"], LIST_ID["B"], LIST_ID["C"])], 1)
        self.assertEqual(signatures[(LIST_ID["A"], LIST_ID["C"])], 1)
        self.assertNotIn("mean_target", json.dumps(context))
        (self.work / "emitted-context.json").write_text(json.dumps(context, indent=1), encoding="utf-8")

        # D10: list membership is the whole signal; no fake numeric predicate.
        contrast = self._run("contrast", draft("LIST_CONTRAST", list_condition=AC), focus="LAV_CONTRAST")
        self.assertEqual(contrast["_exit_code"], 0, contrast)
        result = contrast["result"]
        scope = result["research_scope"]
        self.assertEqual(scope["base_admitted_n"], 7)
        self.assertEqual(scope["matched"]["n"], 2)
        self.assertAlmostEqual(scope["matched"]["mean_target"], 0.05, places=6)
        comp = scope["contrast"]["comparator"]
        self.assertEqual((comp["n"], comp["target_observed_n"], comp["target_missing_n"]), (5, 4, 1))
        self.assertAlmostEqual(comp["mean_target"], 0.15, places=6)
        self.assertAlmostEqual(scope["contrast"]["observed_target_difference"], -0.10, places=6)
        self.assertTrue(result["missing_is_not_zero"])

        # D11: a numeric mechanism inside A and C.
        numeric = self._run("numeric", draft("NUMERIC_IN_SCOPE", research_scope={"universe_selector": AC}, **NUMERIC), focus="LAV_NUMERIC")
        self.assertEqual(numeric["_exit_code"], 0, numeric)
        n_result = numeric["result"]
        self.assertEqual(n_result["research_scope"]["universe_pass_n"], 2)
        self.assertEqual(n_result["matched_n"], 1)
        self.assertAlmostEqual(n_result["mean_target"], 0.20, places=6)
        self.assertAlmostEqual(n_result["baseline"]["mean_target"], 0.05, places=6)

        # D16: an unknown list is a refusal before any value.
        bad = self._resolve_expect_failure("unknown", draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A", "Z"]}]}))
        self.assertIn("LIST_REF_UNKNOWN", bad)

    def test_b_candidate_lifecycle_binds_the_scope(self) -> None:
        from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
        from tests.test_hfic_cli import bind_draft, critic_result_from_packet_only, run_cli

        evidence = self._run("lifecycle", draft("LIST_CONTRAST", list_condition=AC), focus="LAV_LIFECYCLE")
        self.assertEqual(evidence["_exit_code"], 0, evidence)
        pre = evidence["_preflight"]
        identity = temporal.temporal_holder_claim_identity(evidence["result"])
        self.assertEqual(set(identity), {"research_scope_rule_sha256", "research_scope_statement"})
        self.assertIn("KIND=LIST_CONTRAST", identity["research_scope_statement"])
        template = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8"))
        card = {
            **template["candidates"][0],
            **evidence["_scope"],
            **identity,
            "label": "LAV_LIST_ONLY",
            "claim_form": "PREDICTIVE",
            "novelty_class": "NEW_MEASUREMENT",
            "claim": "Membership in both trending and organic lists may by itself separate later E14400 price-relative proxy among admitted episodes; synthetic acceptance only.",
            "mechanism": "Vendor ranking overlap may mark attention that precedes price drift; selection into lists and activity remain confounders, causality UNKNOWN.",
            "mundane_alternative": "Larger or more active tokens enter both lists and move differently without any information in membership.",
            "actor_counterparty": "Attention flows around ranked tokens; no causal actor identification.",
            "state_transition": "membership at episode T0 -> fixed E14400 price mark, no execution claim.",
            "proposed_method": "One frozen list-only recipe against the eligible complement, no retuning, PRICE_RELATIVE_PROXY only.",
            "negative_control": "Eligible complement of the same decision base; observational association only.",
            "confounders": ["size", "activity", "vendor selection"],
            "required_capability_ids": [temporal.TEMPORAL_CAPABILITY_ID],
            "required_feature_ids": [],
            "primary_x_family": identity["research_scope_statement"],
            "primary_y": "PRICE_RELATIVE_PROXY E1800 -> E14400",
            "horizon_notional": "E1800 -> E14400; PRICE_RELATIVE_PROXY; no executable notional",
            "cheapest_falsifier": "One frozen contrast of the matched group against the eligible complement; no threshold or list sweep.",
            "disconfirming_prediction": "The matched group shows no supported contrast against the complement.",
            "decision_unlocked": "Whether a separately authorized validation is justified; synthetic acceptance grants no science permission.",
            "kill_if": ["PIT lineage fails", "No supported contrast"],
            "prior_work_refs": [],
            "material_difference_from_prior": "First list-scoped question on this corpus.",
            "unresolved_requirements": [],
        }
        fresh = _forge_call("preflight", "--discovery-contract", "--owner-focus", pre["owner_focus"], data_root=self.plane)
        draft_doc = bind_draft({**template, "owner_focus": pre["owner_focus"], "candidates": [card]}, fresh)
        draft_doc.pop("runner_up_candidate_ref", None)
        draft_doc.pop("strongest_rejected_alternative", None)
        draft_doc["selected_candidate_ref"] = card["label"]
        draft_doc["grounded_evidence"] = evidence
        draft_path, receipt_path = self.work / "lc-draft.json", self.work / "lc-receipt.json"
        draft_path.write_text(json.dumps(draft_doc), encoding="utf-8")
        receipt_path.write_text(json.dumps(fresh), encoding="utf-8")
        _forge_call("persist-draft", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path), "--representation-id", "BASE", data_root=self.plane)
        resume = _forge_call("preflight", "--discovery-contract", "--owner-focus", pre["owner_focus"], data_root=self.plane)
        receipt_path.write_text(json.dumps(resume), encoding="utf-8")

        # A card that misses or misstates the computed rule hash is refused (text cannot widen the scope).
        from solana_alpha_lab.factory.hfic_session import HficSessionError, _bind_selected_look

        for bad in ({**card, "research_scope_rule_sha256": "0" * 64}, {k: v for k, v in card.items() if k != "research_scope_rule_sha256"},
                    {**card, "research_scope_statement": "KIND=LIST_CONTRAST; UNIVERSE=(ALL); SIGNAL=NONE"}):
            with self.assertRaises(HficSessionError) as caught:
                _bind_selected_look(evidence, bad, store=None)
            self.assertEqual(str(caught.exception), "LOOK_SCOPE_CONTRADICTION")
        self.assertEqual(_bind_selected_look(evidence, card, store=None)["look_confirms_selected"], True)

        frozen = _forge_call("freeze", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path), data_root=self.plane)
        packet = frozen["critic_input_packet"]
        packet_text = json.dumps(packet)
        self.assertIn(identity["research_scope_rule_sha256"], packet_text)
        self.assertIn("KIND=LIST_CONTRAST", packet_text)
        self.assertIn("observed_target_difference", packet_text)
        critic = critic_result_from_packet_only(packet, terminal="KILL_STATISTICALLY_UNIDENTIFIABLE")
        critic["non_claims"].append("SCRIPTED_CRITIC_MECHANICAL")
        critic_path = self.work / "lc-critic.json"
        critic_path.write_text(json.dumps(critic), encoding="utf-8")
        finished = _forge_call("finalize", "--session-id", frozen["session_id"], "--critic-result", str(critic_path), data_root=self.plane)
        self.assertIn("session_state", finished)
        _forge_call("forge-run", "--owner-focus", pre["owner_focus"], "--persist", data_root=self.plane)

    def test_c_real_experiment_spec_and_document_runner(self) -> None:
        import copy

        from solana_alpha_lab.factory.document_runner import DocumentRunner, RunContext
        from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
        from solana_alpha_lab.factory.hfic_session import HficSessionError, _require_recipe_preserves_research_scope
        from solana_alpha_lab.factory.hfic_temporal_discovery import run_temporal_fixed_time_from_spec
        from solana_alpha_lab.factory.lane_classifier import classify_lane
        from solana_alpha_lab.factory.operational_store import OperationalStore
        from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
        from tests.test_fast_lane_classifier import HYPOTHESIS_DEFINITION_SHA256
        from tests.test_hfic_temporal_production_runner_v1 import _bind_experiment

        evidence = self._run("runner", draft("LIST_CONTRAST", list_condition=AC), focus="LAV_RUNNER")
        self.assertEqual(evidence["_exit_code"], 0, evidence)
        recipe = evidence["result"]["experiment_recipe"]
        self.assertEqual(len(recipe["research_scope_rule_sha256"]), 64)
        experiment = _bind_experiment(recipe, self.plane)
        experiment["as_of"] = experiment["availability_cutoff"] = "2026-10-16T00:00:00Z"
        as_of = datetime(2026, 10, 16, tzinfo=UTC)
        decision = classify_lane(
            {"experiment_spec": experiment, "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256},
            root=ROOT,
            data_root=self.plane,
            as_of=as_of,
        )
        self.assertEqual(decision.terminal, "FAST_LANE_READY", decision.reason_codes)
        ops = OperationalStore(self.plane / "ops" / "operational_state.sqlite")
        try:
            result = DocumentRunner(root=ROOT, store=ops).start_document(
                experiment,
                spec_sha256=experiment_spec_sha256(experiment),
                run_context=RunContext(
                    data_root=self.plane,
                    hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                    lane_decision=decision,
                ),
            )
        finally:
            ops.close()
        self.assertEqual(result["status"], "COMPLETE", result)
        run_id = str(result["run_id_or_null"])
        artifact = self.plane / "research" / "artifacts" / "results" / f"RESULT-ARTIFACT-{run_id.removeprefix('RUN-')}.json"
        saved = json.loads(artifact.read_text(encoding="utf-8"))["capability_result"]["summary"]
        saved_scope = saved["research_scope"]
        original = evidence["result"]["research_scope"]
        self.assertEqual(saved_scope["applied_sha256"], original["applied_sha256"])
        self.assertAlmostEqual(saved_scope["contrast"]["observed_target_difference"], -0.10, places=6)
        self.assertEqual(saved_scope["matched"]["n"], 2)

        # Negatives: the runner checks the scope contract before any value is read.
        def attempt(mutator) -> str:
            changed = copy.deepcopy(experiment)
            mutator(changed["parameters"]["temporal_recipe"])
            try:
                run_temporal_fixed_time_from_spec(changed, root=ROOT, capture_hooks={"data_root": self.plane})
            except GroundedDiscoveryError as exc:
                return exc.code
            return "NOT_REFUSED"

        def drop_evidence(r):
            r.pop("research_scope_evidence")

        def corrupt_digest(r):
            r["research_scope_evidence"] = dict(r["research_scope_evidence"], evidence_sha256="0" * 64)

        def widen_universe(r):
            body = r["spec"]["scientific_body"]
            body["research_scope"] = dict(body["research_scope"], coverage_policy="SOMETHING_ELSE")

        self.assertEqual(attempt(drop_evidence), "EXPERIMENT_RECIPE_INVALID")
        self.assertEqual(attempt(corrupt_digest), "RESEARCH_SCOPE_EVIDENCE_DRIFT")
        self.assertNotEqual(attempt(widen_universe), "NOT_REFUSED")
        # Classification refuses a pooled/unscoped experiment for a scoped candidate and vice versa.
        scoped_view = {"critic_input_packet": {"selected_candidate": {"research_scope_rule_sha256": recipe["research_scope_rule_sha256"]}}}
        _require_recipe_preserves_research_scope(scoped_view, {"parameters": {"temporal_recipe": recipe}})
        with self.assertRaises(HficSessionError):
            _require_recipe_preserves_research_scope(scoped_view, {"parameters": {"temporal_recipe": {k: v for k, v in recipe.items() if k != "research_scope_rule_sha256"}}})
        with self.assertRaises(HficSessionError):
            _require_recipe_preserves_research_scope({"critic_input_packet": {"selected_candidate": {}}}, {"parameters": {"temporal_recipe": recipe}})

    def test_z_next_period_same_rule_new_memberships(self) -> None:
        # D21: the next weekly cycle, same rule, new memberships; e1 does not inherit A.
        before = self._run("period1", draft("LIST_CONTRAST", list_condition=AC), focus="LAV_PERIOD_1")
        second = _consume(self.packets[1:], source=self.source, mirror=self.mirror, plane=self.plane)
        self.assertEqual(second["_exit_code"], 0, second)
        pre2 = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "LAV_NEXT", data_root=self.plane)
        context2 = pre2["forge_context_packet"]["list_dimension_context"]
        self.assertEqual(context2["admitted_episodes_n"], 10)
        next_run = self._run("next", draft("LIST_CONTRAST", list_condition=AC), focus="LAV_NEXT")
        self.assertEqual(next_run["_exit_code"], 0, next_run)
        matched = next_run["result"]["research_scope"]["matched"]
        # cohort A {e5,e7} + cohort B {n1}; e1 (C only) is not in A and C
        self.assertEqual(matched["n"], 3)
        self.assertEqual(matched["distinct_mint_n"], 3)
        self.assertEqual(next_run["result"]["research_scope"]["rule_sha256"], before["result"]["research_scope"]["rule_sha256"])
        self.assertNotEqual(next_run["result"]["research_scope"]["applied_sha256"], before["result"]["research_scope"]["applied_sha256"])

    def _resolve_expect_failure(self, tag: str, query: dict[str, Any]) -> str:
        from tests.test_hfic_cli import run_cli

        path = self.work / f"{tag}-draft.json"
        path.write_text(json.dumps(query), encoding="utf-8")
        done = run_cli("research-scope-resolve", "--spec", str(path), "--format", "json", data_root=self.plane)
        self.assertNotEqual(done.returncode, 0)
        return done.stdout + done.stderr


if __name__ == "__main__":
    unittest.main()
