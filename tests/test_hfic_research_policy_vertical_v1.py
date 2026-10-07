"""FORGE_RESEARCH_POLICY_RUNTIME_V1: the mandatory micro-vertical.

Fresh synthetic root -> 6 pre-declared MAIN through the real production
gates at the shipped default -> owner raises the active policy and
explicitly extends this exact journal to 10, without resetting what is
already spent -> a fresh ResearchStore handle on the same root sees the
raised limit -> the old result exact-replays with zero evaluator reads ->
a real 7th-10th MAIN execute -> an 11th is denied before any value load ->
10 real candidates (primary ordinal 9, runner-up ordinal 10) through the
ordinary persist -> freeze -> two-stage Critic -> finalize lifecycle.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation, _publish_focus  # noqa: E402
from tests.test_hfic_temporal_discovery_v1 import _spec as _compound_spec  # noqa: E402
from tests.test_hfic_temporal_production_runner_v1 import DOCUMENT_LATENESS  # noqa: E402
from tests.test_hfic_cli import run_cli  # noqa: E402
from tests.test_hfic_session import critic_result_from_packet_only, finalize_kill_complete  # noqa: E402
from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label  # noqa: E402
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from solana_alpha_lab.factory import hfic_research_policy as rp  # noqa: E402
from solana_alpha_lab.factory.hfic_ordinary_operation import list_operations  # noqa: E402


def _attempt(i: int, workspace: Path, focus: str, journal: str, market: str, op_path: Path, data_root: Path) -> tuple[int, dict]:
    spec = _compound_spec(
        query_id=f"rpv-main-{i}",
        schedule={"lateness_seconds": DOCUMENT_LATENESS},
        all=[
            {"feature": "impulse", "op": "between", "lower": 0.25, "upper": 2.0, "closed": "left"},
            {"feature": "pullback", "op": "between", "lower": -0.40, "upper": -0.10, "closed": "left"},
            {"feature": "retention", "op": "gte", "value": 0.10 + i * 0.01},
        ],
    )
    spec_path = workspace / f"spec-{i}.json"
    scope_path = workspace / f"scope-{i}.json"
    scope_body = {
        "population": "BASE_X",
        "decision_timestamp": "Y3600",
        "target": temporal_target_label(spec),
        "estimand": "price_relative_proxy",
        "explanatory_condition": "compound",
        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
        "representation_scope": "TEMPORAL_PRICE_LIQUIDITY",
    }
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    scope_path.write_text(json.dumps(scope_body), encoding="utf-8")
    op_path.write_text(
        json.dumps(
            _operation(
                spec,
                focus=focus,
                journal=journal,
                market=market,
                text=f"research-policy vertical attempt {i}",
                cap={"main": 10, "adaptive": 0, "preview": 0},
            )
        ),
        encoding="utf-8",
    )
    done = run_cli(
        "discovery-execute",
        "--store", str(data_root),
        "--spec", str(spec_path),
        "--candidate-scope", str(scope_path),
        "--journal-scope", journal,
        "--operation", str(op_path),
        "--format", "json",
        data_root=data_root,
    )
    body = json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {}
    return done.returncode, body


def _card(ordinal: int, claim: str) -> dict:
    return {
        "display_ordinal": ordinal,
        "label": f"RPV-C{ordinal}",
        "claim": claim,
        "novelty_class": "NEW_MEASUREMENT",
        "claim_form": "PREDICTIVE",
        "mundane_alternative": f"mundane-{ordinal}",
        "actor_counterparty": f"counterparty-{ordinal}",
        "mechanism": f"mechanism-{ordinal}",
        "population": "BASE_X",
        "decision_timestamp": "Y3600",
        "estimand": "price_relative_proxy",
        "state_transition": None,
        "primary_x_family": f"FAMILY_{ordinal}",
        "primary_y": "price_relative_proxy",
        "horizon_notional": "Y7200 fixed-time proxy",
        "required_feature_ids": [],
        "required_capability_ids": [],
        "unresolved_requirements": [f"decision-time research input {ordinal}"],
        "prior_work_refs": [],
        "material_difference_from_prior": f"Candidate {ordinal} is its own distinct question.",
        "disconfirming_prediction": f"No lift for candidate {ordinal} cohort.",
        "negative_control": "matched cohort outside the scope list",
        "cheapest_falsifier": f"offline stratified table for candidate {ordinal}",
        "kill_if": [f"candidate {ordinal} input is not available"],
        "decision_unlocked": f"whether candidate {ordinal} lane is worth a Fast Lane experiment",
    }


class ResearchPolicyMicroVerticalTests(unittest.TestCase):
    def test_six_to_ten_through_the_real_production_path_and_ten_candidates_to_finalize(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            focus = "RPV_MICRO_VERTICAL"
            data_root, receipt0 = _publish_focus(workspace, focus)
            journal = str(receipt0["search_key_sha256"])
            market = str(receipt0["market_evidence_epoch_sha256"])
            op_path = workspace / "op.json"
            store = ResearchStore(data_root, create_if_missing=False)

            bodies = []
            for i in range(6):
                code, body = _attempt(i, workspace, focus, journal, market, op_path, data_root)
                self.assertEqual(code, 0, body)
                bodies.append(body)

            denied_code, denied_body = _attempt(6, workspace, focus, journal, market, op_path, data_root)
            self.assertNotEqual(denied_code, 0)
            self.assertEqual(denied_body.get("reason_code"), "QUERY_MAIN_BUDGET_EXHAUSTED")

            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10, "max_generated": 10})
            applied = rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            self.assertEqual(applied["status"], "APPENDED")
            parent_op = next(op for op in list_operations(store) if op.get("journal_scope") == journal)
            ext_proposal = rp.propose_run_extension(
                store,
                journal_scope=journal,
                parent_operation_sha256=str(parent_op["operation_sha256"]),
                limits_delta={"main_total": 10, "max_generated": 10},
            )
            ext_applied = rp.apply_run_extension(store, proposal=ext_proposal, confirm_append_only=True)
            self.assertEqual(ext_applied["status"], "APPENDED")

            # A fresh ResearchStore handle on the same root reads the raised limit
            # from durable state, not from anything held in this process's memory.
            reread = ResearchStore(data_root, create_if_missing=False)
            self.assertEqual(rp.limits_for_frozen_run(reread, journal)["main_total"], 10)

            # The old result exact-replays: same bytes, zero evaluator reads.
            code0b, body0b = _attempt(0, workspace, focus, journal, market, op_path, data_root)
            self.assertEqual(code0b, 0)
            self.assertEqual(body0b.get("result_sha256"), bodies[0].get("result_sha256"))

            for i in range(6, 10):
                code, body = _attempt(i, workspace, focus, journal, market, op_path, data_root)
                self.assertEqual(code, 0, body)
                bodies.append(body)

            code11, body11 = _attempt(10, workspace, focus, journal, market, op_path, data_root)
            self.assertNotEqual(code11, 0)
            self.assertEqual(body11.get("reason_code"), "QUERY_MAIN_BUDGET_EXHAUSTED")

            resume = json.loads(
                run_cli(
                    "preflight", "--discovery-contract", "--owner-focus", focus, "--format", "json",
                    data_root=data_root,
                ).stdout
            )
            cards = [_card(n, f"Claim for candidate {n}.") for n in range(1, 11)]
            grounded_evidence = dict(bodies[8])
            grounded_evidence.pop("search_exhausted", None)
            draft = {
                "packet_schema": "smial.hypothesis-forge-draft",
                "packet_version": "1.3",
                "generator_prompt_version": "HFIC-V1.2",
                "owner_focus": resume["owner_focus"],
                "preflight_receipt_id": resume["receipt_id"],
                "preflight_receipt_sha256": resume["preflight_receipt_sha256"],
                "research_memory_as_of": resume.get("research_memory_as_of") or "2026-10-07T00:00:00Z",
                "truth_roots_used": (resume.get("forge_context_packet") or {}).get("truth_roots_used")
                or ["catalog/catalog_manifest.yaml"],
                "prior_work_receipts": (resume.get("forge_context_packet") or {}).get("prior_work_receipts")
                or ["QUERY-HFIC-SESSION-BY-SEARCH-KEY-001"],
                "authority": {"git_mutation": 0, "experiment_execution": 0, "provider_api_rpc_wss_calls": 0},
                "candidates": cards,
                "selected_candidate_ref": "RPV-C9",
                "runner_up_candidate_ref": "RPV-C10",
                "strongest_rejected_alternative": "RPV-C1",
                "pareto_factors": ["grounding", "falsifiability", "novelty"],
                "non_claims": ["NO_ALPHA"],
                "grounded_evidence": grounded_evidence,
            }
            draft_path = workspace / "draft.json"
            receipt_path = workspace / "receipt.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(resume), encoding="utf-8")
            persisted = run_cli(
                "persist-draft",
                "--draft", str(draft_path),
                "--preflight-receipt", str(receipt_path),
                "--representation-id", "BASE",
                "--format", "json",
                data_root=data_root,
            )
            self.assertEqual(persisted.returncode, 0, persisted.stderr)

            resume2 = json.loads(
                run_cli(
                    "preflight", "--discovery-contract", "--owner-focus", focus, "--format", "json",
                    data_root=data_root,
                ).stdout
            )
            receipt2_path = workspace / "receipt2.json"
            receipt2_path.write_text(json.dumps(resume2), encoding="utf-8")
            frozen_run = run_cli(
                "freeze",
                "--draft", str(draft_path),
                "--preflight-receipt", str(receipt2_path),
                "--format", "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr)
            frozen = json.loads(frozen_run.stdout)
            self.assertEqual(frozen["selected_display_ordinal"], 9)
            self.assertEqual(len(frozen["candidate_ids"]), 10)

            critic = critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM")
            done = finalize_kill_complete(frozen, critic, store, repo_root=ROOT)
            self.assertEqual(done.get("session_state"), "SYNTHESIS_COMPLETE")


class MalformedPolicyTests(unittest.TestCase):
    def test_cli_rejects_a_malformed_policy_delta_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, _receipt = _publish_focus(workspace, "RPV_MALFORMED")
            before = ResearchStore(data_root, create_if_missing=False).diagnostics().committed_inventory_sha256
            done = run_cli(
                "research-policy-preview",
                "--main-total", str(rp.HARD_FUSES["main_total"] + 1),
                "--format", "json",
                data_root=data_root,
            )
            self.assertNotEqual(done.returncode, 0)
            body = json.loads(done.stdout.strip().splitlines()[-1])
            self.assertEqual(body.get("reason_code"), "RESEARCH_POLICY_LIMIT_OUT_OF_RANGE")
            after = ResearchStore(data_root, create_if_missing=False).diagnostics().committed_inventory_sha256
            self.assertEqual(before, after)


class LegacyGoldenUnchangedTests(unittest.TestCase):
    def test_a_journal_never_touched_by_research_policy_still_sees_6_2_2(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, receipt = _publish_focus(workspace, "RPV_LEGACY_GOLDEN")
            journal = str(receipt["search_key_sha256"])
            store = ResearchStore(data_root, create_if_missing=False)
            limits = rp.limits_for_frozen_run(store, journal)
            self.assertEqual(limits["main_total"], 6)
            self.assertEqual(limits["adaptive_total"], 2)
            self.assertEqual(limits["preview_total"], 2)
            self.assertEqual(limits["simple_before_compound"], 3)
            self.assertEqual(limits["max_generated"], 6)
            self.assertIsNone(rp.read_run_snapshot(store, journal))


if __name__ == "__main__":
    unittest.main()
