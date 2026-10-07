"""FORGE_RESEARCH_POLICY_RUNTIME_V1: the mandatory micro-vertical and its branches.

Everything here goes through the public CLI and the production gates on a
disposable synthetic root: no provider call, no production data.

    fresh root, shipped defaults -> 5 pre-declared MAIN -> the active defaults
    are raised to 10 (the open run does NOT move) -> an explicit extension of
    exactly that run -> remaining 5, the old result replays with no value load
    -> MAIN 6..10 really execute, the 11th is refused with zero writes ->
    10 real candidates (primary ordinal 9, runner-up ordinal 10) through
    persist -> freeze -> two-stage Critic -> finalize -> a moved root under a
    different active policy still reads the saved result with zero value loads.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
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
from solana_alpha_lab.factory import hfic_research_policy as rp  # noqa: E402
from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label  # noqa: E402
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402


def _json(done) -> dict:
    return json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {}


def _inventory(data_root: Path) -> str:
    return ResearchStore(data_root, create_if_missing=False).diagnostics().committed_inventory_sha256


def _attempt(
    i: int,
    workspace: Path,
    focus: str,
    journal: str,
    market: str,
    data_root: Path,
    *,
    cap_main: int = 10,
    cycle_index: int | None = None,
    accounting_root: str | None = None,
    parent_operation_sha256: str | None = None,
    tag: str = "rpv",
) -> tuple[int, dict]:
    spec = _compound_spec(
        query_id=f"{tag}-main-{i}",
        schedule={"lateness_seconds": DOCUMENT_LATENESS},
        all=[
            {"feature": "impulse", "op": "between", "lower": 0.25, "upper": 2.0, "closed": "left"},
            {"feature": "pullback", "op": "between", "lower": -0.40, "upper": -0.10, "closed": "left"},
            {"feature": "retention", "op": "gte", "value": 0.10 + i * 0.01},
        ],
    )
    spec_path = workspace / f"{tag}-spec-{i}.json"
    scope_path = workspace / f"{tag}-scope-{i}.json"
    op_path = workspace / f"{tag}-op-{i}.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    scope_path.write_text(
        json.dumps(
            {
                "population": "BASE_X",
                "decision_timestamp": "Y3600",
                "target": temporal_target_label(spec),
                "estimand": "price_relative_proxy",
                "explanatory_condition": "compound",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                "representation_scope": "TEMPORAL_PRICE_LIQUIDITY",
            }
        ),
        encoding="utf-8",
    )
    operation = _operation(
        spec,
        focus=focus,
        journal=journal,
        market=market,
        text=f"research-policy vertical {tag} attempt {i}",
        cap={"main": cap_main, "adaptive": 0, "preview": 0},
    )
    if cycle_index:
        operation["cycle_index"] = cycle_index
        operation["accounting_root"] = accounting_root
        operation["parent_operation_sha256"] = parent_operation_sha256
    op_path.write_text(json.dumps(operation), encoding="utf-8")
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
    body = _json(done)
    if not body.get("reason_code") and done.returncode != 0:
        body = {**body, "stderr": done.stderr[-400:], "stdout": done.stdout[-400:]}
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


def _preflight(data_root: Path, focus: str, *extra: str) -> dict:
    done = run_cli("preflight", "--discovery-contract", "--owner-focus", focus, *extra, "--format", "json", data_root=data_root)
    return _json(done)


def _draft(resume: dict, cards: list, selected: str, runner_up: str, rejected: str, evidence: dict) -> dict:
    grounded = dict(evidence)
    grounded.pop("search_exhausted", None)
    context = resume.get("forge_context_packet") or {}
    return {
        "packet_schema": "smial.hypothesis-forge-draft",
        "packet_version": "1.3" if len(cards) > 6 else "1.2",
        "generator_prompt_version": "HFIC-V1.2",
        "owner_focus": resume["owner_focus"],
        "preflight_receipt_id": resume["receipt_id"],
        "preflight_receipt_sha256": resume["preflight_receipt_sha256"],
        "research_memory_as_of": resume.get("research_memory_as_of") or "2026-10-07T00:00:00Z",
        "truth_roots_used": context.get("truth_roots_used") or ["catalog/catalog_manifest.yaml"],
        "prior_work_receipts": context.get("prior_work_receipts") or ["QUERY-HFIC-SESSION-BY-SEARCH-KEY-001"],
        "authority": {"git_mutation": 0, "experiment_execution": 0, "provider_api_rpc_wss_calls": 0},
        "candidates": cards,
        "selected_candidate_ref": selected,
        "runner_up_candidate_ref": runner_up,
        "strongest_rejected_alternative": rejected,
        "pareto_factors": ["grounding", "falsifiability", "novelty"],
        "non_claims": ["NO_ALPHA"],
        "grounded_evidence": grounded,
    }


def _freeze_and_finalize(workspace: Path, data_root: Path, focus: str, build_draft, store: ResearchStore, *flags: str, tag: str) -> dict:
    resume = _preflight(data_root, focus, *flags)
    draft = build_draft(resume)
    draft_path = workspace / f"{tag}-draft.json"
    receipt_path = workspace / f"{tag}-receipt.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    receipt_path.write_text(json.dumps(resume), encoding="utf-8")
    persisted = run_cli(
        "persist-draft", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path),
        "--representation-id", "BASE", "--format", "json", data_root=data_root,
    )
    assert persisted.returncode == 0, persisted.stderr
    again = _preflight(data_root, focus, *flags)
    again_path = workspace / f"{tag}-receipt2.json"
    again_path.write_text(json.dumps(again), encoding="utf-8")
    frozen_run = run_cli(
        "freeze", "--draft", str(draft_path), "--preflight-receipt", str(again_path), "--format", "json",
        data_root=data_root,
    )
    assert frozen_run.returncode == 0, frozen_run.stderr + frozen_run.stdout
    frozen = json.loads(frozen_run.stdout)
    critic = critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM")
    done = finalize_kill_complete(frozen, critic, store, repo_root=ROOT)
    return {"frozen": frozen, "final": done}


class ResearchPolicyMicroVerticalTests(unittest.TestCase):
    def test_prd_15_micro_vertical(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            focus = "RPV_MICRO_VERTICAL"
            data_root, receipt0 = _publish_focus(workspace, focus)
            journal = str(receipt0["search_key_sha256"])
            market = str(receipt0["market_evidence_epoch_sha256"])
            store = ResearchStore(data_root, create_if_missing=False)

            # B02: show reads zero market values and writes nothing; the root is the canonical one.
            before = _inventory(data_root)
            shown = _json(run_cli("research-policy-status", "--format", "json", data_root=data_root))
            self.assertEqual(shown["active_policy_for_new_runs"]["source"], rp.SOURCE_DEFAULTS)
            self.assertEqual((shown["market_values_read"], shown["writes"]), (0, {"research_store": 0}))
            self.assertEqual(_inventory(data_root), before)

            # 5 pre-declared MAIN through the production gate at the shipped defaults.
            bodies = []
            for i in range(5):
                code, body = _attempt(i, workspace, focus, journal, market, data_root)
                self.assertEqual(code, 0, body)
                self.assertTrue(body["values_loaded"])
                bodies.append(body)
            operation = str(bodies[0]["operation_sha256"])
            run = _json(run_cli("research-policy-status", "--for-operation", operation, "--format", "json", data_root=data_root))
            main = run["occupancy"][journal]["main"]
            self.assertEqual((main["limit"], main["completed"], main["remaining"]), (6, 5, 1))

            # B06: the active defaults are raised while this run is open. The open run keeps its snapshot.
            active_preview = _json(
                run_cli("research-policy-preview", "--main-total", "10", "--max-generated", "10", "--format", "json", data_root=data_root)
            )
            self.assertEqual(active_preview["applies_to"], "NEW_SCOPES_ONLY")
            active_file = workspace / "active.json"
            active_file.write_text(json.dumps(active_preview), encoding="utf-8")
            applied = _json(
                run_cli("research-policy-apply", "--proposal", str(active_file), "--confirm-append-only", "--format", "json", data_root=data_root)
            )
            self.assertEqual(applied["status"], "APPENDED")
            self.assertEqual(applied["applies_to"], "NEW_SCOPES_ONLY")
            run = _json(run_cli("research-policy-status", "--for-operation", operation, "--format", "json", data_root=data_root))
            frozen_row = run["frozen_policy"][journal]
            self.assertEqual(frozen_row["limits"]["main_total"], 6)
            self.assertEqual(run["active_policy_for_new_runs"]["limits"]["main_total"], 10)
            self.assertTrue(frozen_row["differs"])
            # The raise alone grants this open run nothing: the 7th would still be refused. Prove it with remaining.
            self.assertEqual(run["occupancy"][journal]["main"]["remaining"], 1)

            # An explicit extension of exactly this run's scopes (same accounting domain).
            ext_preview = _json(
                run_cli(
                    "research-policy-preview", "--for-operation", operation, "--main-total", "10", "--max-generated", "10",
                    "--format", "json", data_root=data_root,
                )
            )
            self.assertEqual(ext_preview["applies_to"], "THESE_SCOPES_ONLY")
            self.assertEqual(ext_preview["proposals"][0]["before"]["main_total"], 6)
            self.assertEqual(ext_preview["proposals"][0]["after"]["main_total"], 10)
            ext_file = workspace / "ext.json"
            ext_file.write_text(json.dumps(ext_preview), encoding="utf-8")
            ext_applied = _json(
                run_cli("research-policy-apply", "--proposal", str(ext_file), "--confirm-append-only", "--format", "json", data_root=data_root)
            )
            self.assertEqual(ext_applied["status"], "APPENDED")
            self.assertEqual(ext_applied["before_limits"]["main_total"], 6)
            # Idempotent after a lost reply: the same proposal is the exact existing receipt.
            inventory = _inventory(data_root)
            repeated = _json(
                run_cli("research-policy-apply", "--proposal", str(ext_file), "--confirm-append-only", "--format", "json", data_root=data_root)
            )
            self.assertEqual(repeated["status"], rp.ALREADY_APPLIED)
            self.assertEqual(_inventory(data_root), inventory)

            # A fresh process shows remaining 5 (B05) and the old result replays with no value load.
            run = _json(run_cli("research-policy-status", "--for-operation", operation, "--format", "json", data_root=data_root))
            main = run["occupancy"][journal]["main"]
            self.assertEqual((main["limit"], main["completed"], main["remaining"]), (10, 5, 5))
            code0, replay = _attempt(0, workspace, focus, journal, market, data_root)
            self.assertEqual(code0, 0)
            self.assertFalse(replay["values_loaded"])
            self.assertFalse(replay["writes"])
            self.assertEqual(replay["result_sha256"], bodies[0]["result_sha256"])

            # B04: MAIN 6..10 really execute; the 11th is refused with zero writes.
            for i in range(5, 10):
                code, body = _attempt(i, workspace, focus, journal, market, data_root)
                self.assertEqual(code, 0, body)
                self.assertTrue(body["values_loaded"])
                bodies.append(body)
            from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
            from solana_alpha_lab.factory.hfic_ordinary_operation import RESERVATION_KIND, _iter_kind, journal_occupancy

            spend_before = (
                len(list_discovery_looks(store, journal)),
                len(_iter_kind(store, RESERVATION_KIND)),
                journal_occupancy(store, journal),
            )
            code11, body11 = _attempt(10, workspace, focus, journal, market, data_root)
            self.assertNotEqual(code11, 0)
            self.assertEqual(body11.get("reason_code"), "QUERY_MAIN_BUDGET_EXHAUSTED")
            self.assertFalse(body11.get("values_loaded", False))
            # The owner request is recorded, but nothing is spent: no look, no reservation, no value.
            spend_after = (
                len(list_discovery_looks(store, journal)),
                len(_iter_kind(store, RESERVATION_KIND)),
                journal_occupancy(store, journal),
            )
            self.assertEqual(spend_after, spend_before)
            self.assertEqual(spend_after[2]["main"]["remaining"], 0)

            # B11: ten real candidates, primary ordinal 9, runner-up ordinal 10, through the ordinary lifecycle.
            cards = [_card(n, f"Claim for candidate {n}.") for n in range(1, 11)]
            result = _freeze_and_finalize(
                workspace,
                data_root,
                focus,
                lambda resume: _draft(resume, cards, "RPV-C9", "RPV-C10", "RPV-C1", bodies[8]),
                store,
                tag="micro",
            )
            frozen = result["frozen"]
            self.assertEqual(frozen["selected_display_ordinal"], 9)
            self.assertEqual(len(frozen["candidate_ids"]), 10)
            self.assertEqual(result["final"].get("session_state"), "SYNTHESIS_COMPLETE")

            # B17/B18: a moved root under a DIFFERENT active policy still reads saved results with zero value loads.
            moved_parent = workspace / "moved"
            moved_parent.mkdir()
            moved = moved_parent / "rdp"
            shutil.copytree(data_root, moved)
            other = _json(run_cli("research-policy-preview", "--main-total", "3", "--simple-before-compound", "3", "--format", "json", data_root=moved))
            other_file = workspace / "other.json"
            other_file.write_text(json.dumps(other), encoding="utf-8")
            run_cli("research-policy-apply", "--proposal", str(other_file), "--confirm-append-only", "--format", "json", data_root=moved)
            code_m, body_m = _attempt(0, workspace, focus, journal, market, moved, tag="rpv")
            self.assertEqual(code_m, 0, body_m)
            self.assertFalse(body_m["values_loaded"])
            self.assertEqual(body_m["result_sha256"], bodies[0]["result_sha256"])
            status_m = _json(run_cli("research-policy-status", "--for-operation", operation, "--format", "json", data_root=moved))
            self.assertEqual(status_m["frozen_policy"][journal]["limits"]["main_total"], 10)
            self.assertEqual(status_m["active_policy_for_new_runs"]["limits"]["main_total"], 3)


class ResearchPolicyBranchTests(unittest.TestCase):
    def test_malformed_policy_is_refused_before_any_write_with_the_failing_field(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_root, _receipt = _publish_focus(Path(raw), "RPV_MALFORMED")
            before = _inventory(data_root)
            done = run_cli("research-policy-preview", "--main-total", "99", "--format", "json", data_root=data_root)
            self.assertNotEqual(done.returncode, 0)
            body = _json(done)
            self.assertEqual(body["reason_code"], "RESEARCH_POLICY_LIMIT_OUT_OF_RANGE")
            self.assertEqual((body["field"], body["hard_fuse"]), ("main_total", 32))
            empty = run_cli("research-policy-preview", "--format", "json", data_root=data_root)
            self.assertEqual(_json(empty)["reason_code"], "RESEARCH_POLICY_CHANGE_EMPTY")
            self.assertEqual(_inventory(data_root), before)

    def test_apply_refuses_a_tampered_proposal_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, _receipt = _publish_focus(workspace, "RPV_TAMPER")
            preview = _json(run_cli("research-policy-preview", "--main-total", "8", "--format", "json", data_root=data_root))
            preview["proposal"]["limits"]["main_total"] = 32
            proposal_file = workspace / "tampered.json"
            proposal_file.write_text(json.dumps(preview), encoding="utf-8")
            before = _inventory(data_root)
            done = run_cli("research-policy-apply", "--proposal", str(proposal_file), "--confirm-append-only", "--format", "json", data_root=data_root)
            self.assertNotEqual(done.returncode, 0)
            self.assertEqual(_json(done)["reason_code"], "RESEARCH_POLICY_INVALID")
            self.assertEqual(_inventory(data_root), before)
            unconfirmed = run_cli("research-policy-apply", "--proposal", str(proposal_file), "--format", "json", data_root=data_root)
            self.assertEqual(_json(unconfirmed)["reason_code"], "RESEARCH_POLICY_CONFIRM_REQUIRED")
            self.assertEqual(_inventory(data_root), before)

    def test_an_unknown_or_unfrozen_operation_cannot_be_extended(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_root, _receipt = _publish_focus(Path(raw), "RPV_NO_PARENT")
            before = _inventory(data_root)
            done = run_cli(
                "research-policy-preview", "--for-operation", "b" * 64, "--main-total", "10", "--format", "json", data_root=data_root
            )
            body = _json(done)
            self.assertEqual(body["reason_code"], "ORDINARY_OPERATION_NOT_FOUND")
            self.assertIn("research-policy-status", body["next_action"])
            self.assertEqual(_inventory(data_root), before)

    def test_an_ordinary_journal_freezes_at_exactly_the_shipped_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_root, receipt = _publish_focus(Path(raw), "RPV_LEGACY_GOLDEN")
            store = ResearchStore(data_root, create_if_missing=False)
            journal = str(receipt["search_key_sha256"])
            self.assertEqual(rp.limits_or_defaults(store, journal), rp.DEFAULT_LIMITS)
            # preflight froze the market epoch's AUTO/focus pool at the shipped defaults
            pool = rp.epoch_limits(store, str(receipt["market_evidence_epoch_sha256"]))
            self.assertEqual((pool["auto_cycles_per_market"], pool["distinct_focuses_per_market"]), (1, 3))

    def test_read_only_preflight_writes_no_policy_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, _receipt = _publish_focus(workspace, "RPV_READ_ONLY")
            snapshots = len(rp._iter_artifacts(ResearchStore(data_root, create_if_missing=False), rp.SNAPSHOT_KIND))
            inventory = _inventory(data_root)
            run_cli("preflight", "--no-auto-commission", "--owner-focus", "RPV_READ_ONLY_OTHER", "--format", "json", data_root=data_root)
            self.assertEqual(
                len(rp._iter_artifacts(ResearchStore(data_root, create_if_missing=False), rp.SNAPSHOT_KIND)), snapshots
            )
            self.assertEqual(_inventory(data_root), inventory)

    def test_two_os_processes_racing_the_last_slot_produce_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            focus = "RPV_LAST_SLOT"
            data_root, receipt = _publish_focus(workspace, focus)
            journal = str(receipt["search_key_sha256"])
            market = str(receipt["market_evidence_epoch_sha256"])
            for i in range(5):
                code, body = _attempt(i, workspace, focus, journal, market, data_root, tag="race")
                self.assertEqual(code, 0, body)
            results: dict[int, tuple[int, dict]] = {}

            def _run(index: int) -> None:
                results[index] = _attempt(5 + index, workspace, focus, journal, market, data_root, tag="race")

            threads = [threading.Thread(target=_run, args=(i,)) for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            codes = sorted(code for code, _body in results.values())
            self.assertEqual(codes[0], 0, results)
            self.assertNotEqual(codes[1], 0, results)
            loser = next(body for code, body in results.values() if code != 0)
            self.assertIn(loser.get("reason_code"), {"OWNER_CAP_EXHAUSTED", "QUERY_MAIN_BUDGET_EXHAUSTED"})
            self.assertFalse(loser.get("values_loaded", False))
            from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy

            store = ResearchStore(data_root, create_if_missing=False)
            main = journal_occupancy(store, journal)["main"]
            self.assertEqual((main["completed"], main["pending"], main["remaining"]), (6, 0, 0))


class ResearchPolicyWideNoWorthyTests(unittest.TestCase):
    """P1-D: 10 candidates and no selected one end as NO_WORTHY with all 10 identities preserved."""

    def test_ten_cards_without_a_selection_finish_negative_and_read_back_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            focus = "RPV_WIDE_NO_WORTHY"
            data_root, receipt0 = _publish_focus(workspace, focus)
            journal = str(receipt0["search_key_sha256"])
            market = str(receipt0["market_evidence_epoch_sha256"])
            store = ResearchStore(data_root, create_if_missing=False)
            raised = _json(run_cli("research-policy-preview", "--max-generated", "10", "--format", "json", data_root=data_root))
            raised_file = workspace / "nw-policy.json"
            raised_file.write_text(json.dumps(raised), encoding="utf-8")
            self.assertEqual(_json(run_cli("research-policy-apply", "--proposal", str(raised_file), "--confirm-append-only", "--format", "json", data_root=data_root))["status"], "APPENDED")
            code, look = _attempt(0, workspace, focus, journal, market, data_root, cap_main=1, tag="nw")
            self.assertEqual(code, 0, look)
            cards = [_card(n, f"Negative-portfolio claim {n}.") for n in range(1, 11)]
            resume = _preflight(data_root, focus)
            draft = _draft(resume, cards, "RPV-C9", "RPV-C10", "RPV-C1", look)
            draft.pop("selected_candidate_ref")
            draft["non_claims"] = ["NO_ALPHA", "NO_WORTHY_HYPOTHESIS"]
            draft_path = workspace / "nw-draft.json"
            receipt_path = workspace / "nw-receipt.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(resume), encoding="utf-8")
            persisted = run_cli("persist-draft", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path), "--representation-id", "BASE", "--format", "json", data_root=data_root)
            self.assertEqual(persisted.returncode, 0, persisted.stderr + persisted.stdout)
            again = _preflight(data_root, focus)
            receipt_path.write_text(json.dumps(again), encoding="utf-8")
            frozen_run = run_cli("freeze", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path), "--format", "json", data_root=data_root)
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr + frozen_run.stdout)
            frozen = json.loads(frozen_run.stdout)
            self.assertEqual(frozen["critic_terminal"], "NO_WORTHY_HYPOTHESIS")
            self.assertIsNone(frozen["selected_candidate_id"])
            self.assertEqual(len(frozen["candidate_ids"]), 10)

            # A fresh process reads the negative terminal back with every identity and no invented selection.
            shown = run_cli("show-session", "--session-id", str(frozen["session_id"]), "--format", "json", data_root=data_root)
            self.assertEqual(shown.returncode, 0, shown.stderr + shown.stdout)
            body = json.loads(shown.stdout)
            session = body.get("session", body)
            self.assertEqual(session["critic_terminal"], "NO_WORTHY_HYPOTHESIS")
            self.assertIsNone(session.get("selected_candidate_id"))
            self.assertEqual(session["candidate_ids"], frozen["candidate_ids"])
            from solana_alpha_lab.factory.hfic_session import load_session_bundle

            bundle = load_session_bundle(ResearchStore(data_root, create_if_missing=False), str(frozen["session_id"]))
            self.assertEqual(len(bundle["candidate_ids"]), 10)
            self.assertEqual(bundle["critic_terminal"], "NO_WORTHY_HYPOTHESIS")


class ResearchPolicyAutoCycleVerticalTests(unittest.TestCase):
    """B08: AUTO 1 -> 2 through the production preflight/freeze path; the third is denied."""

    def test_auto_one_to_two_exact_additional_cycle_and_third_denied(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            focus = "AUTO"
            data_root, receipt0 = _publish_focus(workspace, focus)
            store = ResearchStore(data_root, create_if_missing=False)
            journal1 = str(receipt0["search_key_sha256"])
            market = str(receipt0["market_evidence_epoch_sha256"])
            cards = [_card(n, f"Claim for candidate {n}.") for n in range(1, 4)]

            # Cycle 1 to completion through the ordinary lifecycle.
            code, first = _attempt(0, workspace, focus, journal1, market, data_root, tag="c1")
            self.assertEqual(code, 0, first)
            operation = str(first["operation_sha256"])
            done1 = _freeze_and_finalize(
                workspace, data_root, focus,
                lambda resume: _draft(resume, cards, "RPV-C1", "RPV-C2", "RPV-C3", first),
                store, tag="cycle1",
            )
            self.assertEqual(done1["final"].get("session_state"), "SYNTHESIS_COMPLETE")
            session1 = str(done1["frozen"]["session_id"])

            # A plain repeat returns the saved session; it never starts a cycle, whatever the cap.
            plain = _preflight(data_root, focus)
            self.assertEqual((plain["action"], plain["session_id"]), ("RETURN_EXISTING_SESSION", session1))

            # Cap 1: an explicit additional cycle is refused with its own typed terminal.
            denied = _preflight(data_root, focus, "--additional-cycle")
            self.assertEqual((denied["action"], denied["terminal"]), ("STOP", "SEARCH_BUDGET_EXHAUSTED"))

            # A bare raise of the active defaults does not widen an epoch pool that is already frozen.
            bare = _json(run_cli("research-policy-preview", "--auto-cycles-per-market", "2", "--format", "json", data_root=data_root))
            bare_file = workspace / "bare.json"
            bare_file.write_text(json.dumps(bare), encoding="utf-8")
            run_cli("research-policy-apply", "--proposal", str(bare_file), "--confirm-append-only", "--format", "json", data_root=data_root)
            still = _preflight(data_root, focus, "--additional-cycle")
            self.assertEqual((still["action"], still["terminal"]), ("STOP", "SEARCH_BUDGET_EXHAUSTED"))
            self.assertEqual(_preflight(data_root, focus)["action"], "RETURN_EXISTING_SESSION")

            # The explicit extension of this market epoch's pool is what authorizes exactly one more cycle.
            ext = _json(
                run_cli("research-policy-preview", "--for-operation", operation, "--auto-cycles-per-market", "2", "--format", "json", data_root=data_root)
            )
            self.assertEqual(ext["proposals"][0]["scope_kind"], "EPOCH")
            ext_file = workspace / "epoch-ext.json"
            ext_file.write_text(json.dumps(ext), encoding="utf-8")
            applied = _json(run_cli("research-policy-apply", "--proposal", str(ext_file), "--confirm-append-only", "--format", "json", data_root=data_root))
            self.assertEqual(applied["status"], "APPENDED")
            self.assertEqual(_preflight(data_root, focus)["action"], "RETURN_EXISTING_SESSION")

            # Cycle 2: its own slot and journal, the same ordinary lifecycle.
            start = _preflight(data_root, focus, "--additional-cycle")
            self.assertEqual(start["action"], "START_NEW_SESSION")
            self.assertEqual(start["cycle_index"], 2)
            journal2 = str(start["search_key_sha256"])
            self.assertNotEqual(journal2, journal1)
            # A second cycle must bring materially different candidates: identical definitions are
            # already recorded hypotheses of cycle 1 and are refused as duplicates.
            cards2 = [_card(n, f"Cycle two claim for candidate {n}, a different question.") for n in range(1, 4)]
            self.assertEqual(start["accounting_root"], journal1)  # the lineage root travels in the receipt
            lineage = dict(cycle_index=2, accounting_root=journal1, parent_operation_sha256=operation)
            code2, second = _attempt(1, workspace, focus, journal2, market, data_root, tag="c2", **lineage)
            self.assertEqual(code2, 0, second)
            from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy

            shared = journal_occupancy(ResearchStore(data_root, create_if_missing=False), journal2)["main"]
            self.assertEqual((shared["limit"], shared["completed"]), (6, 2))  # cycle 1's look plus cycle 2's, one budget
            # The exact query cycle 1 already saved is a replay, never a new attempt in cycle 2.
            code_r, replay = _attempt(0, workspace, focus, journal2, market, data_root, tag="c1", **lineage)
            self.assertEqual(code_r, 0, replay)
            self.assertFalse(replay.get("values_loaded", False))
            self.assertEqual(
                journal_occupancy(ResearchStore(data_root, create_if_missing=False), journal2)["main"]["completed"], 2
            )
            done2 = _freeze_and_finalize(
                workspace, data_root, focus,
                lambda resume: _draft(resume, cards2, "RPV-C1", "RPV-C2", "RPV-C3", second),
                store, "--additional-cycle", tag="cycle2",
            )
            self.assertEqual(done2["final"].get("session_state"), "SYNTHESIS_COMPLETE")
            self.assertNotEqual(str(done2["frozen"]["session_id"]), session1)

            # The episode representation of the cycle-2 BASE session climbs the ordinary ladder: its journal is keyed
            # from that parent's own search key, it is its own accounting domain and it is not an AUTO cycle.
            from solana_alpha_lab.factory import hfic_ordinary_operation as oo
            from solana_alpha_lab.factory.hfic_representation_ladder import load_ladder_registry
            from solana_alpha_lab.factory.normalized_trajectory_episodes_v1 import REPRESENTATION_ID, representation_search_key

            version = next(
                row["version"] for row in load_ladder_registry(ROOT / "configs" / "hfic_representation_ladder_v1.yaml")["representations"]
                if row["id"] == REPRESENTATION_ID
            )
            live = ResearchStore(data_root, create_if_missing=False)
            payload_sha, scope_sha = "ab" * 32, "cd" * 32
            for parent_session, parent_key in ((session1, journal1), (str(done2["frozen"]["session_id"]), journal2)):
                child_journal = representation_search_key(parent_key, parent_session, payload_sha, scope_sha)
                child = oo.record_operation(
                    live,
                    {
                        "owner_request_text": f"episode profile of {parent_session}",
                        "owner_focus": focus,
                        "journal_scope": child_journal,
                        "market_evidence_epoch_sha256": market,
                        "owner_cap": {"main": None, "adaptive": None, "preview": None},
                        "requested_completion": oo.LIMITED_RESULT,
                        "representation": {
                            "representation_id": REPRESENTATION_ID,
                            "representation_semantic_version": str(version),
                            "parent_session_id": parent_session,
                            "representation_payload_sha256": payload_sha,
                            "scope_applied_sha256": scope_sha,
                        },
                    },
                )
                oo._assert_preflight_journal(live, child, child_journal, repo_root=ROOT, data_root=data_root)
                self.assertEqual(oo.accounting_root_of(live, child_journal), child_journal)  # its own domain
                self.assertEqual(oo.journal_occupancy(live, child_journal)["main"]["completed"], 0)
            self.assertEqual(oo.journal_occupancy(live, journal2)["main"]["completed"], 2)  # BASE lineage untouched

            # A parent of another focus, or a child posing as a BASE parent, cannot anchor an episode journal.
            wrong = oo.record_operation(
                live,
                {
                    "owner_request_text": "episode profile of a foreign-focus parent",
                    "owner_focus": "SOME_OTHER_FOCUS",
                    "journal_scope": representation_search_key(journal2, str(done2["frozen"]["session_id"]), payload_sha, scope_sha),
                    "market_evidence_epoch_sha256": market,
                    "owner_cap": {"main": None, "adaptive": None, "preview": None},
                    "requested_completion": oo.LIMITED_RESULT,
                    "representation": {
                        "representation_id": REPRESENTATION_ID,
                        "representation_semantic_version": str(version),
                        "parent_session_id": str(done2["frozen"]["session_id"]),
                        "representation_payload_sha256": payload_sha,
                        "scope_applied_sha256": scope_sha,
                    },
                },
            )
            with self.assertRaises(oo.OrdinaryOperationError) as foreign:
                oo._assert_preflight_journal(live, wrong, str(wrong["journal_scope"]), repo_root=ROOT, data_root=data_root)
            self.assertEqual(foreign.exception.code, "ORDINARY_OPERATION_PARENT_FOCUS_MISMATCH")

            # The third attempt is denied; the saved first cycle is untouched.
            third = _preflight(data_root, focus, "--additional-cycle")
            self.assertEqual((third["action"], third["terminal"]), ("STOP", "SEARCH_BUDGET_EXHAUSTED"))
            self.assertEqual(_preflight(data_root, focus)["session_id"], session1)


if __name__ == "__main__":
    unittest.main()
