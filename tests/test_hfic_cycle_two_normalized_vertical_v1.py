"""Owner review P1-A: a second AUTO cycle and its real episode-normalized child on the list-aware fixture.

One complete micro-vertical, in its own module so the CI shard planner can place it separately from the heavy
list-aware class: cycle 1 BASE and a real normalized child (2 of 6), the explicit second AUTO cycle, its real view,
payload, scope and ladder receipt, the evaluator, freeze, Critic and final, replay, stop. Only transport, clock and
authored market bytes are synthetic; the fixture capture is the one the list-aware vertical uses.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import tests.test_hfic_list_aware_vertical_v1 as lav  # noqa: E402
from tests.test_hfic_list_aware_vertical_v1 import _discovery, _forge_call, draft  # noqa: E402


class CycleTwoNormalizedVerticalTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        lav.ListAwareVerticalTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls) -> None:
        lav.ListAwareVerticalTests.tearDownClass.__func__(cls)

    _resolve = lav.ListAwareVerticalTests._resolve
    _run = lav.ListAwareVerticalTests._run

    # ------------------------------------------------------------------ owner review: cycle 2 -> normalized
    def _list_query(self, clauses: list[list[str]]) -> dict[str, Any]:
        return draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": item} for item in clauses]})

    def _attempt(self, tag: str, query: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
        """One ordinary discovery-execute through the real evaluator under the given operation request."""

        from solana_alpha_lab.factory import hfic_temporal_discovery as temporal

        canonical = self._resolve(tag, query)["canonical_query"]
        scope = {
            "population": "OPPORTUNITY_EPISODES",
            "decision_timestamp": "E1800",
            "target": temporal.temporal_target_label(canonical),
            "estimand": "price_relative_proxy",
            "explanatory_condition": canonical["hypothesis_kind"],
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
        }
        evidence = _discovery(self.plane, self.work, tag=tag, spec=canonical, scope=scope, operation={**operation, "spec": canonical})
        evidence["_scope"] = scope
        evidence["_canonical"] = canonical
        return evidence

    def _negative_base(self, tag: str, evidence: dict[str, Any], receipt: dict[str, Any], *flags: str) -> dict[str, Any]:
        """BASE terminal NO_WORTHY with a real scoped look as its evidence (the existing production shape)."""

        from tests.test_hfic_cli import bind_draft

        template = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json").read_text(encoding="utf-8"))
        template["candidates"] = []
        for key in ("runner_up_candidate_ref", "strongest_rejected_alternative", "selected_candidate_ref"):
            template.pop(key, None)
        fresh = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "AUTO", *flags, data_root=self.plane)
        body = bind_draft({**template, "owner_focus": fresh["owner_focus"]}, fresh)
        body["grounded_evidence"] = {key: value for key, value in evidence.items() if not key.startswith("_")}
        draft_path, receipt_path = self.work / f"{tag}-nw-draft.json", self.work / f"{tag}-nw-receipt.json"
        draft_path.write_text(json.dumps(body), encoding="utf-8")
        receipt_path.write_text(json.dumps(fresh), encoding="utf-8")
        _forge_call("persist-draft", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path), "--representation-id", "BASE", data_root=self.plane)
        resume = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "AUTO", *flags, data_root=self.plane)
        receipt_path.write_text(json.dumps(resume), encoding="utf-8")
        return _forge_call("freeze", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path), data_root=self.plane)

    def _finish_child(self, tag: str, ladder: dict[str, Any], evidence: dict[str, Any], label: str) -> dict[str, Any]:
        """The ordinary persist/freeze -> Critic -> finalize of one episode child (what test_d does for its child)."""

        from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
        from tests.test_hfic_cli import bind_draft, critic_result_from_packet_only

        card_template = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8"))
        scope = evidence["_scope"]
        identity = temporal.temporal_holder_claim_identity(evidence["result"])
        # The view is read-only; explicitly commit its derived context before writers (the grounded handoff contract).
        from solana_alpha_lab.factory.hfic_preflight import persist_forge_context_packet
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.run_passport import canonical_sha256

        ladder = dict(ladder)
        ladder["forge_context_packet_sha256"] = persist_forge_context_packet(
            self.plane, ladder["forge_context_packet"], store=ResearchStore(self.plane), repo_root=ROOT,
        )
        ladder.pop("preflight_receipt_sha256", None)
        ladder["preflight_receipt_sha256"] = canonical_sha256(ladder)
        card = {
            **card_template["candidates"][0],
            **scope,
            **identity,
            "label": label,
            "claim_form": "PREDICTIVE",
            "novelty_class": "NEW_MEASUREMENT",
            "claim": f"A shared prefix motif of price, liquidity and holders may accompany a later E14400 proxy difference ({label}); synthetic acceptance only.",
            "mechanism": "Co-moving participation and liquidity after a price dip may precede drift; confounders remain and causality is UNKNOWN.",
            "mundane_alternative": "Activity alone produces the same motif.",
            "actor_counterparty": "Participants around ranked tokens; no causal identification.",
            "state_transition": "prefix motif at E1800 -> fixed E14400 mark",
            "proposed_method": "One frozen list-scoped recipe; the motif only guides which scope to test.",
            "negative_control": "Eligible complement of the same decision base.",
            "confounders": ["activity"],
            "required_capability_ids": [temporal.TEMPORAL_CAPABILITY_ID],
            "required_feature_ids": [],
            "primary_x_family": identity["research_scope_statement"],
            "primary_y": "PRICE_RELATIVE_PROXY E1800 -> E14400",
            "horizon_notional": "E1800 -> E14400; PRICE_RELATIVE_PROXY; no executable notional",
            "cheapest_falsifier": "One frozen contrast against the eligible complement.",
            "disconfirming_prediction": "No supported contrast.",
            "decision_unlocked": "Whether to authorise a separate validation; none is granted.",
            "kill_if": ["PIT lineage fails"],
            "prior_work_refs": [],
            "material_difference_from_prior": f"Episode profile stage {label}.",
            "unresolved_requirements": [],
        }
        stage_draft = bind_draft({**card_template, "owner_focus": ladder["owner_focus"], "candidates": [card]}, ladder)
        stage_draft.pop("runner_up_candidate_ref", None)
        stage_draft.pop("strongest_rejected_alternative", None)
        stage_draft["selected_candidate_ref"] = label
        stage_draft["grounded_evidence"] = {key: value for key, value in evidence.items() if not key.startswith("_")}
        sd, sr = self.work / f"{tag}-draft.json", self.work / f"{tag}-receipt.json"
        sd.write_text(json.dumps(stage_draft), encoding="utf-8")
        sr.write_text(json.dumps(ladder), encoding="utf-8")
        _forge_call("persist-draft", "--draft", str(sd), "--preflight-receipt", str(sr), "--representation-id", "NORMALIZED_TRAJECTORY_EPISODES_V1", data_root=self.plane)
        frozen = _forge_call("freeze", "--draft", str(sd), "--preflight-receipt", str(sr), data_root=self.plane)
        critic = critic_result_from_packet_only(frozen["critic_input_packet"], terminal="KILL_STATISTICALLY_UNIDENTIFIABLE")
        critic["non_claims"].append("SCRIPTED_CRITIC_MECHANICAL")
        critic_path = self.work / f"{tag}-critic.json"
        critic_path.write_text(json.dumps(critic), encoding="utf-8")
        finished = _forge_call("finalize", "--session-id", frozen["session_id"], "--critic-result", str(critic_path), data_root=self.plane)
        self.assertEqual(finished["session_state"], "SYNTHESIS_COMPLETE")
        return {"frozen": frozen, "finished": finished}

    def _child_operation(self, view: dict[str, Any], text: str, cap: dict[str, int]) -> dict[str, Any]:
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation

        ladder = view["ladder_freeze_preflight"]
        payload = view["representation_payload"]
        operation = _operation(
            self._resolve("shape", self._list_query([["A", "C"]]))["canonical_query"],
            focus=ladder["owner_focus"],
            journal=ladder["search_key_sha256"],
            market=ladder["market_evidence_epoch_sha256"],
            text=text,
            cap=cap,
            completion="LIMITED_RESULT",
        )
        operation.pop("spec", None)
        operation["representation"] = {
            "representation_id": "NORMALIZED_TRAJECTORY_EPISODES_V1",
            "representation_semantic_version": "1.0",
            "parent_session_id": ladder["control_session_id"],
            "representation_payload_sha256": payload["representation_payload_sha256"],
            "scope_applied_sha256": payload["scope_applied_sha256"],
        }
        return operation

    def test_cycle_two_normalized_child_continues_the_representation_spend(self) -> None:
        """Owner review P1-A: a second AUTO cycle and its real episode-normalized child keep spending the
        representation's budget; BASE and normalized stay separate; replay, changed input and STOP behave."""

        from solana_alpha_lab.factory.hfic_ordinary_operation import accounting_root_of, journal_occupancy
        from solana_alpha_lab.factory.hfic_session import list_hfic_sessions, load_session_bundle
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_hfic_cli import run_cli

        plane = self.plane

        def occupancy(journal: str) -> dict[str, Any]:
            return journal_occupancy(ResearchStore(plane, create_if_missing=False), journal)["main"]

        # ---------------- cycle 1: BASE terminal and a real episode child that spends 2 of 6 ----------------
        one = {"main": 1, "adaptive": 0, "preview": 4}
        base1 = self._run("c1base", self._list_query([["A", "C"]]), focus="AUTO", cap=one)
        self.assertEqual(base1["_exit_code"], 0, base1)
        pre1 = base1["_preflight"]
        self.assertEqual(pre1["owner_focus"], "OPPORTUNITY_EPISODES:AUTO")
        frozen1 = self._negative_base("c1", base1, pre1)
        spec_path = self.work / "c1-view-spec.json"
        spec_path.write_text(json.dumps(self._list_query([["A", "C"]])), encoding="utf-8")
        view1 = _forge_call(
            "episode-normalized-view", "--spec", str(spec_path), "--parent-session-id", frozen1["session_id"],
            "--operation-sha256", str(base1["operation_sha256"]), data_root=plane,
        )
        child_cap = {"main": 6, "adaptive": 0, "preview": 0}
        child1_op = self._child_operation(view1, "episode child, cycle 1", child_cap)
        child1_journal = child1_op["journal_scope"]
        first = self._attempt("c1child-a", self._list_query([["A", "C"]]), child1_op)
        self.assertEqual(first["_exit_code"], 0, first)
        second = self._attempt("c1child-b", self._list_query([["B"]]), child1_op)
        self.assertEqual(second["_exit_code"], 0, second)
        spent = occupancy(child1_journal)
        self.assertEqual((spent["limit"], spent["completed"], spent["remaining"]), (6, 2, 4))
        done1 = self._finish_child("c1child", view1["ladder_freeze_preflight"], first, "LAV_EP_C1")
        bundle1_before = load_session_bundle(ResearchStore(plane, create_if_missing=False), frozen1["session_id"])
        child1_before = load_session_bundle(ResearchStore(plane, create_if_missing=False), done1["frozen"]["session_id"])

        # ---------------- the explicit second AUTO cycle ----------------
        denied = json.loads(run_cli("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "AUTO", "--additional-cycle", "--format", "json", data_root=plane).stdout.strip().splitlines()[-1])
        self.assertEqual((denied["action"], denied["terminal"]), ("STOP", "SEARCH_BUDGET_EXHAUSTED"))
        ext = _forge_call("research-policy-preview", "--for-operation", str(base1["operation_sha256"]), "--auto-cycles-per-market", "2", data_root=plane)
        ext_file = self.work / "c2-pool.json"
        ext_file.write_text(json.dumps(ext), encoding="utf-8")
        self.assertEqual(_forge_call("research-policy-apply", "--proposal", str(ext_file), "--confirm-append-only", data_root=plane)["status"], "APPENDED")
        pre2 = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "AUTO", "--additional-cycle", data_root=plane)
        self.assertEqual((pre2["action"], pre2["cycle_index"]), ("START_NEW_SESSION", 2))
        self.assertNotEqual(pre2["search_key_sha256"], pre1["search_key_sha256"])
        self.assertEqual(pre2["accounting_root"], pre1["search_key_sha256"])

        # BASE cycle 2: its own look is charged to the BASE lineage, not to the normalized one.
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation

        canonical2 = self._resolve("c2base-shape", self._list_query([["A"]]))["canonical_query"]
        base2_op = _operation(
            canonical2, focus=pre2["owner_focus"], journal=pre2["search_key_sha256"], market=pre2["market_evidence_epoch_sha256"],
            text="BASE cycle 2", cap=one, completion="LIMITED_RESULT",
        )
        base2_op.update(cycle_index=2, accounting_root=pre2["accounting_root"], parent_operation_sha256=str(base1["operation_sha256"]))
        base2 = self._attempt("c2base", self._list_query([["A"]]), base2_op)
        self.assertEqual(base2["_exit_code"], 0, base2)
        frozen2 = self._negative_base("c2", base2, pre2, "--additional-cycle")
        self.assertNotEqual(frozen2["session_id"], frozen1["session_id"])
        base_budget = occupancy(pre2["search_key_sha256"])
        self.assertEqual(base_budget["completed"], 2)  # BASE lineage: cycle 1's look plus cycle 2's, nothing of the child's

        # ---------------- cycle-2 episode child: real view, real payload, real ladder receipt ----------------
        spec2 = self.work / "c2-view-spec.json"
        spec2.write_text(json.dumps(self._list_query([["A"]])), encoding="utf-8")
        view2 = _forge_call(
            "episode-normalized-view", "--spec", str(spec2), "--parent-session-id", frozen2["session_id"],
            "--operation-sha256", str(base2["operation_sha256"]), data_root=plane,
        )
        self.assertEqual(view2["ladder_freeze_preflight"]["control_session_id"], frozen2["session_id"])
        child2_op = self._child_operation(view2, "episode child, cycle 2", child_cap)
        child2_journal = child2_op["journal_scope"]
        self.assertNotEqual(child2_journal, child1_journal)  # its own execution identity
        # The very first request: continuing, so 2 of 6 are already spent, not a fresh 6.
        replay = self._attempt("c2child-replay", self._list_query([["A", "C"]]), child2_op)
        self.assertEqual(replay["_exit_code"], 0, replay)
        store = ResearchStore(plane, create_if_missing=False)
        self.assertEqual(accounting_root_of(store, child2_journal), child1_journal)
        self.assertEqual(accounting_root_of(store, child1_journal), child1_journal)
        carried = occupancy(child2_journal)
        self.assertEqual((carried["limit"], carried["completed"], carried["remaining"]), (6, 2, 4))
        self.assertFalse(replay.get("new_look", False))  # the exact saved query is a replay, not a third attempt

        # An explicit normalized total of 10 raises that representation only: 8 left, BASE untouched.
        raise_total = _forge_call("research-policy-preview", "--for-operation", self._operation_sha(child2_journal), "--main-total", "10", data_root=plane)
        raise_file = self.work / "c2-total10.json"
        raise_file.write_text(json.dumps(raise_total), encoding="utf-8")
        self.assertEqual(_forge_call("research-policy-apply", "--proposal", str(raise_file), "--confirm-append-only", data_root=plane)["status"], "APPENDED")
        raised = occupancy(child2_journal)
        self.assertEqual((raised["limit"], raised["completed"], raised["remaining"]), (10, 2, 8))
        self.assertEqual(occupancy(pre2["search_key_sha256"])["limit"], 6)  # BASE keeps its own budget

        # A changed query is a new attempt and is counted.
        changed = self._attempt("c2child-changed", self._list_query([["A"]]), child2_op)
        self.assertEqual(changed["_exit_code"], 0, changed)
        counted = occupancy(child2_journal)
        self.assertEqual((counted["completed"], counted["remaining"]), (3, 7))
        self.assertEqual(occupancy(child1_journal), counted)  # one representation lineage, one budget

        # Bindings: scope, market, focus, parent and representation are preserved on the operation.
        operations = {row["journal_scope"]: row for row in __import__("solana_alpha_lab.factory.hfic_ordinary_operation", fromlist=["x"]).list_operations(store)}
        stored = operations[child2_journal]
        self.assertEqual(stored["owner_focus"], "OPPORTUNITY_EPISODES:AUTO")
        self.assertEqual(stored["market_evidence_epoch_sha256"], pre2["market_evidence_epoch_sha256"])
        self.assertEqual(stored["representation"]["parent_session_id"], frozen2["session_id"])
        self.assertEqual(stored["accounting_root"], child1_journal)

        # The child completes the ordinary lifecycle, and the third AUTO is still refused.
        done2 = self._finish_child("c2child", view2["ladder_freeze_preflight"], changed, "LAV_EP_C2")
        self.assertNotEqual(done2["frozen"]["session_id"], done1["frozen"]["session_id"])
        third = json.loads(run_cli("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "AUTO", "--additional-cycle", "--format", "json", data_root=plane).stdout.strip().splitlines()[-1])
        self.assertEqual((third["action"], third["terminal"]), ("STOP", "SEARCH_BUDGET_EXHAUSTED"))
        sessions = [row for row in list_hfic_sessions(ResearchStore(plane, create_if_missing=False)) if row.get("owner_focus") == "OPPORTUNITY_EPISODES:AUTO"]
        base_rows = [row for row in sessions if row.get("ladder_representation_id") in (None, "", "BASE")]
        self.assertEqual(len(base_rows), 2)  # exactly two AUTO cycles; the children are not a third

        # Fresh process: the exact saved query replays with no new look, and the parents' terminals are unchanged.
        fresh = run_cli(
            "discovery-execute", "--store", str(plane), "--spec", str(self.work / "c2child-replay-spec.json"),
            "--candidate-scope", str(self.work / "c2child-replay-scope.json"), "--journal-scope", child2_journal,
            "--operation", str(self.work / "c2child-replay-op.json"), "--format", "json", data_root=plane,
        )
        self.assertEqual(fresh.returncode, 0, fresh.stderr + fresh.stdout)
        self.assertEqual(occupancy(child2_journal), counted)
        reopened = ResearchStore(plane, create_if_missing=False)
        after1 = load_session_bundle(reopened, frozen1["session_id"])
        for key in ("critic_terminal", "session_state", "selected_candidate_id", "candidate_ids"):
            self.assertEqual(after1.get(key), bundle1_before.get(key), key)
        child1_after = load_session_bundle(reopened, done1["frozen"]["session_id"])
        for key in ("critic_terminal", "session_state", "selected_candidate_id"):
            self.assertEqual(child1_after.get(key), child1_before.get(key), key)

        # An earlier cycle's child cannot arrive after a later cycle's (that would be a second, independent budget).
        more_preview = _forge_call("research-policy-preview", "--for-operation", str(base2["operation_sha256"]), "--preview-total", "4", data_root=plane)
        more_file = self.work / "c2-preview4.json"
        more_file.write_text(json.dumps(more_preview), encoding="utf-8")
        self.assertEqual(_forge_call("research-policy-apply", "--proposal", str(more_file), "--confirm-append-only", data_root=plane)["status"], "APPENDED")
        spec_early = self.work / "c1-view-spec-late.json"
        spec_early.write_text(json.dumps(self._list_query([["C"]])), encoding="utf-8")
        view_early = _forge_call(
            "episode-normalized-view", "--spec", str(spec_early), "--parent-session-id", frozen1["session_id"],
            "--operation-sha256", str(base1["operation_sha256"]), data_root=plane,
        )
        late = self._attempt("c1child-late", self._list_query([["C"]]), self._child_operation(view_early, "late cycle-1 child", child_cap))
        self.assertNotEqual(late["_exit_code"], 0, late)
        self.assertEqual(late.get("reason_code"), "ORDINARY_OPERATION_LINEAGE_OUT_OF_ORDER", late)

        # A stopped member of the lineage cannot be bypassed by a new segment.
        from solana_alpha_lab.factory.hfic_ordinary_operation import apply_operation_stop, preview_operation_stop

        stop = preview_operation_stop(reopened, operation_sha256=self._operation_sha(child1_journal), owner_request_text="stop the cycle-1 child")
        apply_operation_stop(reopened, proposal=stop["proposal"], confirm_append_only=True)
        bypass = self._attempt(
            "c2child-bypass", self._list_query([["B"]]),
            self._child_operation(view2, "episode child, a new segment after a stop", child_cap),
        )
        self.assertNotEqual(bypass["_exit_code"], 0, bypass)
        self.assertEqual(bypass.get("reason_code"), "ORDINARY_OPERATION_STOPPED", bypass)

        # Leave the shared plane clean for the later tests of this class: no open operation of this flow remains.
        from solana_alpha_lab.factory.hfic_ordinary_operation import list_operations

        from solana_alpha_lab.factory.hfic_ordinary_operation import get_operation

        for digest in sorted({str(row["operation_sha256"]) for row in list_operations(reopened) if row.get("owner_focus") == "OPPORTUNITY_EPISODES:AUTO"}):
            if get_operation(reopened, digest).get("status") == "STOPPED":
                continue
            closing = preview_operation_stop(reopened, operation_sha256=digest, owner_request_text="close the cycle-two vertical")
            apply_operation_stop(reopened, proposal=closing["proposal"], confirm_append_only=True)

    def _operation_sha(self, journal: str) -> str:
        from solana_alpha_lab.factory.hfic_ordinary_operation import list_operations
        from solana_alpha_lab.factory.research_store import ResearchStore

        rows = [row for row in list_operations(ResearchStore(self.plane, create_if_missing=False)) if row.get("journal_scope") == journal]
        return str(rows[0]["operation_sha256"])


if __name__ == "__main__":
    unittest.main()
