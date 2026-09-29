"""Published-corpus acceptance C–E for one ordinary operation.

The critic in C is scripted mechanical input, marked SCRIPTED_CRITIC_MECHANICAL.
It is not an independent scientific critic.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    list_discovery_looks,
    resolve_published_discovery_binding,
)
from solana_alpha_lab.factory.hfic_ordinary_operation import (  # noqa: E402
    OrdinaryOperationError,
    _reservations,
    gate_before_values,
    record_operation,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    execute_temporal_discovery,
    temporal_target_label,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_fast_lane_classifier import experiment_spec  # noqa: E402
from tests.test_hfic_cli import bind_draft, run_cli  # noqa: E402
from tests.test_hfic_temporal_discovery_v1 import LIQ, PRICE, _spec as temporal_spec  # noqa: E402
from tests.test_hfic_temporal_production_runner_v1 import DOCUMENT_LATENESS, _publish  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _forge():
    path = ROOT / "scripts" / "hypothesis_forge.py"
    spec = importlib.util.spec_from_file_location("hfic_forge_cli_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _mains(store: Path, journal: str) -> list[dict]:
    return [
        item
        for item in list_discovery_looks(ResearchStore(store, create_if_missing=False), journal)
        if item.get("look_class") == "MAIN" and item.get("new_look") is True
    ]


def _inventory(store: Path) -> str:
    return ResearchStore(store, create_if_missing=False).diagnostics().committed_inventory_sha256


def _simple(query_id: str, *, value: float = 0.0, point: str = "Y3600") -> dict:
    return temporal_spec(
        "SIMPLE_SCREEN",
        query_id=query_id,
        features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": point}],
        all=[{"feature": "mark", "op": "gte", "value": value}],
        cost_profile=None,
        schedule={"lateness_seconds": DOCUMENT_LATENESS},
    )


def _publish_focus(workspace: Path, focus: str, *, exit_price: str = "1.44") -> tuple[Path, dict]:
    data_root = workspace / "rdp"
    _publish(data_root, workspace, exit_price=exit_price)
    preflight = run_cli(
        "preflight",
        "--discovery-contract",
        "--owner-focus",
        focus,
        "--format",
        "json",
        data_root=data_root,
    )
    if preflight.returncode != 0:
        raise AssertionError(preflight.stderr + preflight.stdout)
    return data_root, json.loads(preflight.stdout)


def _operation(
    spec: dict,
    *,
    focus: str,
    journal: str,
    market: str,
    text: str,
    cap: dict,
    completion: str = "LIMITED_RESULT",
) -> dict:
    return {
        "owner_request_text": text,
        "owner_focus": focus,
        "journal_scope": journal,
        "market_evidence_epoch_sha256": market,
        "spec": spec,
        "question_text": text,
        "owner_cap": cap,
        "requested_completion": completion,
    }


class OrdinaryAcceptanceTests(unittest.TestCase):
    def test_c_positive_candidate_reaches_scripted_classification_without_a_new_look(self) -> None:
        focus = "PUBLISHED_ORDINARY_CANDIDATE"
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, receipt = _publish_focus(workspace, focus)
            journal = str(receipt["search_key_sha256"])
            market = str(receipt["market_evidence_epoch_sha256"])
            simple = _simple("published-positive-simple")
            spec_path = workspace / "spec.json"
            scope_path = workspace / "scope.json"
            op_path = workspace / "op.json"
            spec_path.write_text(json.dumps(simple), encoding="utf-8")
            scope_path.write_text(
                json.dumps(
                    {
                        "population": "BASE_X",
                        "decision_timestamp": "Y3600",
                        "target": temporal_target_label(simple),
                        "estimand": "price_relative_proxy",
                        "explanatory_condition": "mark",
                        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                    }
                ),
                encoding="utf-8",
            )
            op_path.write_text(
                json.dumps(
                    _operation(
                        simple,
                        focus=focus,
                        journal=journal,
                        market=market,
                        text="one positive simple on this published corpus",
                        cap={"main": 1, "adaptive": 0, "preview": 0},
                    )
                ),
                encoding="utf-8",
            )
            completed = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(op_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            evidence = json.loads(completed.stdout)
            self.assertGreater(float(evidence["result"]["mean_target"]), 0.0)
            self.assertEqual(len(_mains(data_root, journal)), 1)
            source = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8")
            )
            card = dict(source["candidates"][0])
            card.update(
                {
                    "population": "BASE_X",
                    "decision_timestamp": "Y3600",
                    "target": temporal_target_label(simple),
                    "estimand": "price_relative_proxy",
                    "explanatory_condition": "mark",
                }
            )
            draft = bind_draft({**source, "candidates": [card]}, receipt)
            draft.pop("runner_up_candidate_ref", None)
            draft.pop("strongest_rejected_alternative", None)
            draft["selected_candidate_ref"] = card["label"]
            draft["grounded_evidence"] = evidence
            draft["owner_focus"] = focus
            draft_path = workspace / "draft.json"
            receipt_path = workspace / "receipt.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            persisted = run_cli(
                "persist-draft",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--representation-id",
                "BASE",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(persisted.returncode, 0, persisted.stderr + persisted.stdout)
            persisted_body = json.loads(persisted.stdout)
            cold = run_cli(
                "forge-run",
                "--owner-focus",
                focus,
                "--no-write",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertIn(cold.returncode, {0, 2}, cold.stderr + cold.stdout)
            cold_body = json.loads(cold.stdout)
            self.assertNotEqual(cold_body.get("next_action"), "AUTHORIZE_ADDITIONAL_LOOKS", cold_body)
            cold_op = cold_body.get("ordinary_operation") or {}
            self.assertEqual(cold_op.get("result_refs"), evidence["result_refs"])
            self.assertEqual(cold_op.get("status"), "PAUSED_CAP")
            draft_sha = str(persisted_body.get("payload_sha256") or "")
            self.assertTrue(draft_sha)
            stage_drafts = {
                str(item.get("draft_sha256") or "")
                for item in (cold_body.get("stages") or [])
                if isinstance(item, dict)
            }
            if stage_drafts:
                self.assertIn(draft_sha, stage_drafts, cold_body)
            open_work = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                focus,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(open_work.returncode, 0, open_work.stderr + open_work.stdout)
            opened = json.loads(open_work.stdout)
            self.assertEqual(opened.get("draft_lifecycle"), "GENERATED_BEFORE_FREEZE", opened)
            resume_path = workspace / "resume.json"
            resume_path.write_text(json.dumps(opened), encoding="utf-8")
            frozen_run = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(resume_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr + frozen_run.stdout)
            frozen = json.loads(frozen_run.stdout)
            self.assertTrue(frozen.get("critic_input_packet_sha256"), frozen)
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
                "authority": {
                    "git_mutation": 0,
                    "experiment_execution": 0,
                    "provider_api_rpc_wss_calls": 0,
                },
                "non_claims": ["NO_ALPHA", "SCRIPTED_CRITIC_MECHANICAL"],
            }
            critic_path = workspace / "critic.json"
            critic_path.write_text(json.dumps(critic), encoding="utf-8")
            awaiting = run_cli(
                "finalize",
                "--session-id",
                str(frozen["session_id"]),
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(awaiting.returncode, 0, awaiting.stderr + awaiting.stdout)
            waiting = json.loads(awaiting.stdout)
            self.assertEqual(waiting.get("session_state"), "AWAITING_CLASSIFICATION", waiting)
            self.assertEqual(waiting.get("critic_terminal"), "PASS_TO_CLASSIFICATION")
            self.assertIn("SCRIPTED_CRITIC_MECHANICAL", waiting.get("non_claims") or critic["non_claims"])
            packet = {
                "experiment_spec": experiment_spec(),
                "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
            }
            packet["experiment_spec"]["required_feature_ids"] = list(card.get("required_feature_ids") or [])
            packet_path = workspace / "classify.json"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            classified = run_cli(
                "classify",
                "--session-id",
                str(frozen["session_id"]),
                "--experiment-spec",
                str(packet_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(classified.returncode, 0, classified.stderr + classified.stdout)
            done = json.loads(classified.stdout)
            self.assertEqual(done.get("session_state"), "SYNTHESIS_COMPLETE", done)
            self.assertEqual(done.get("session_id"), frozen["session_id"])
            self.assertEqual(done.get("selected_candidate_id"), frozen["selected_candidate_id"])
            self.assertEqual(done.get("critic_input_packet_sha256"), frozen["critic_input_packet_sha256"])
            self.assertEqual(done.get("critic_terminal"), "PASS_FAST_LANE_READY")
            self.assertEqual(done.get("lane_classifier_terminal"), "FAST_LANE_READY")
            self.assertEqual(len(_mains(data_root, journal)), 1)
            readback = run_cli(
                "forge-run",
                "--owner-focus",
                focus,
                "--no-write",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(readback.returncode, 0, readback.stderr + readback.stdout)
            shown = json.loads(readback.stdout)
            self.assertNotEqual(shown.get("next_action"), "AUTHORIZE_ADDITIONAL_LOOKS", shown)
            operation = shown.get("ordinary_operation") or {}
            self.assertEqual(operation.get("result_refs"), evidence["result_refs"])
            self.assertEqual(len(_mains(data_root, journal)), 1)

    def test_d_faults_resume_and_last_unit_do_not_double_spend(self) -> None:
        focus = "PUBLISHED_ORDINARY_RECOVERY"
        forge = _forge()
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, receipt = _publish_focus(workspace, focus)
            journal = str(receipt["search_key_sha256"])
            market = str(receipt["market_evidence_epoch_sha256"])
            spec_a = _simple("recovery-a")
            spec_b = _simple("recovery-b", value=0.1)
            spec_c = _simple("recovery-c", value=0.2)
            scope = {
                "population": "BASE_X",
                "decision_timestamp": "Y3600",
                "target": temporal_target_label(spec_a),
                "estimand": "price_relative_proxy",
                "explanatory_condition": "mark",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            }
            scope_path = workspace / "scope.json"
            scope_path.write_text(json.dumps(scope), encoding="utf-8")
            op_path = workspace / "op.json"
            op_path.write_text(
                json.dumps(
                    _operation(
                        spec_a,
                        focus=focus,
                        journal=journal,
                        market=market,
                        text="recovery of three saved attempts",
                        cap={"main": 3, "adaptive": 0, "preview": 0},
                    )
                ),
                encoding="utf-8",
            )
            calls = {"n": 0}
            real_eval = execute_temporal_discovery

            def counting_eval(*args, **kwargs):
                calls["n"] += 1
                if calls.get("raise_before"):
                    calls["raise_before"] = False
                    calls["n"] -= 1
                    raise RuntimeError("crash-after-reserve")
                return real_eval(*args, **kwargs)

            def run(spec: dict) -> int:
                path = workspace / f"{spec['query_id']}.json"
                path.write_text(json.dumps(spec), encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    return forge.cmd_discovery_execute(
                        ROOT,
                        store_root=data_root,
                        census_path=None,
                        observations_path=None,
                        binding_path=None,
                        spec_path=path,
                        journal_scope=journal,
                        candidate_scope_path=scope_path,
                        explicit_data_root=data_root,
                        operation_path=op_path,
                    )

            with mock.patch(
                "solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery",
                counting_eval,
            ):
                with mock.patch.object(
                    forge,
                    "emit",
                    side_effect=RuntimeError("reply-lost"),
                ):
                    with self.assertRaises(RuntimeError):
                        run(spec_a)
                self.assertEqual(calls["n"], 1)
                self.assertEqual(len(_mains(data_root, journal)), 1)
                replay = run(spec_a)
            self.assertEqual(replay, 0)
            self.assertEqual(calls["n"], 1, "committed result was recomputed")
            with mock.patch(
                "solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery",
                counting_eval,
            ), mock.patch(
                "solana_alpha_lab.factory.hfic_ordinary_operation.note_look_landed",
                side_effect=RuntimeError("transition-lost"),
            ):
                with self.assertRaises(RuntimeError):
                    run(spec_b)
            self.assertEqual(calls["n"], 2)
            self.assertEqual(len(_mains(data_root, journal)), 2)
            with mock.patch(
                "solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery",
                counting_eval,
            ):
                resumed = run(spec_b)
                self.assertEqual(resumed, 0)
                self.assertEqual(calls["n"], 2, "pending transition recomputed the look")
                calls["raise_before"] = True
                pending = record_operation(
                    ResearchStore(data_root, create_if_missing=False),
                    json.loads(op_path.read_text(encoding="utf-8")),
                )
                reserved_before = len(
                    _reservations(ResearchStore(data_root), pending["operation_sha256"])
                )
                with self.assertRaises(RuntimeError):
                    run(spec_c)
                self.assertEqual(calls["n"], 2)
                self.assertEqual(len(_mains(data_root, journal)), 2)
                self.assertEqual(
                    len(_reservations(ResearchStore(data_root), pending["operation_sha256"])),
                    reserved_before + 1,
                )
                continued = run(spec_c)
                self.assertEqual(continued, 0)
                self.assertEqual(calls["n"], 3)
                again = run(spec_c)
                self.assertEqual(again, 0)
                self.assertEqual(calls["n"], 3)
            self.assertEqual(len(_mains(data_root, journal)), 3)

            race_focus = "PUBLISHED_ORDINARY_RACE"
            race_preflight = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                race_focus,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(race_preflight.returncode, 0, race_preflight.stderr)
            race_receipt = json.loads(race_preflight.stdout)
            race_journal = str(race_receipt["search_key_sha256"])
            held = _simple("race-held", value=0.5)
            race_spec_1 = _simple("race-1", value=1.0)
            race_spec_2 = _simple("race-2", value=2.0)
            raced = record_operation(
                ResearchStore(data_root, create_if_missing=False),
                _operation(
                    held,
                    focus=race_focus,
                    journal=race_journal,
                    market=market,
                    text="two callers one remaining main",
                    cap={"main": 2, "adaptive": 0, "preview": 0},
                ),
            )
            cohorts = list(resolve_published_discovery_binding(data_root).get("cohorts") or [])
            held_gate = gate_before_values(
                ResearchStore(data_root, create_if_missing=False),
                operation_sha256=raced["operation_sha256"],
                spec=held,
                journal_scope=race_journal,
                binding_cohorts=cohorts,
                verified_market=market,
            )
            self.assertEqual(held_gate.get("disposition"), "RESERVED")
            barrier = threading.Barrier(2)
            outcomes: list[str] = []

            def spend(spec: dict) -> None:
                barrier.wait()
                try:
                    gate = gate_before_values(
                        ResearchStore(data_root, create_if_missing=False),
                        operation_sha256=raced["operation_sha256"],
                        spec=spec,
                        journal_scope=race_journal,
                        binding_cohorts=cohorts,
                        verified_market=market,
                    )
                    outcomes.append(str(gate.get("disposition")))
                except OrdinaryOperationError as exc:
                    outcomes.append(exc.code)

            threads = [threading.Thread(target=spend, args=(spec,)) for spec in (race_spec_1, race_spec_2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertCountEqual(outcomes, ["RESERVED", "OWNER_CAP_EXHAUSTED"])
            self.assertEqual(len(_reservations(ResearchStore(data_root), raced["operation_sha256"])), 2)
            self.assertEqual(_mains(data_root, race_journal), [])
            self.assertEqual(len(_mains(data_root, journal)), 3)

    def test_e_foreign_inputs_and_exhausted_caps_do_not_load(self) -> None:
        focus = "PUBLISHED_ORDINARY_BOUNDARY"
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, receipt = _publish_focus(workspace, focus)
            journal = str(receipt["search_key_sha256"])
            market = str(receipt["market_evidence_epoch_sha256"])
            simple = _simple("boundary-simple")
            scope = {
                "population": "BASE_X",
                "decision_timestamp": "Y3600",
                "target": temporal_target_label(simple),
                "estimand": "price_relative_proxy",
                "explanatory_condition": "mark",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            }
            scope_path = workspace / "scope.json"
            spec_path = workspace / "spec.json"
            scope_path.write_text(json.dumps(scope), encoding="utf-8")
            spec_path.write_text(json.dumps(simple), encoding="utf-8")
            before = _inventory(data_root)
            missing_operation = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(missing_operation.returncode, 0)
            self.assertIn("ORDINARY_OPERATION_REQUIRED", missing_operation.stdout)
            self.assertEqual(_inventory(data_root), before)
            self.assertEqual(_mains(data_root, journal), [])
            naked_preview = run_cli(
                "discovery-preview",
                "--spec",
                str(spec_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(naked_preview.returncode, 0)
            self.assertIn("ORDINARY_OPERATION_REQUIRED", naked_preview.stdout)
            self.assertEqual(_inventory(data_root), before)
            invalid = dict(simple)
            invalid.pop("target")
            invalid_path = workspace / "invalid.json"
            invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
            (workspace / "unused.json").write_text(
                json.dumps(
                    _operation(
                        simple,
                        focus=focus,
                        journal=journal,
                        market=market,
                        text="invalid spec must not record",
                        cap={"main": 1, "adaptive": 0, "preview": 0},
                    )
                ),
                encoding="utf-8",
            )
            invalid_run = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(invalid_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(workspace / "unused.json"),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertIn("QUERY_SPEC_INVALID", invalid_run.stdout + invalid_run.stderr)
            self.assertEqual(_inventory(data_root), before)

            foreign_market = _operation(
                simple,
                focus=focus,
                journal=journal,
                market="ab" * 32,
                text="foreign market",
                cap={"main": 1, "adaptive": 0, "preview": 0},
            )
            foreign_market_path = workspace / "foreign-market.json"
            foreign_market_path.write_text(json.dumps(foreign_market), encoding="utf-8")
            market_run = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(foreign_market_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertIn("ORDINARY_OPERATION_MARKET_MISMATCH", market_run.stdout)
            self.assertNotIn("BINDING_HASH_MISMATCH", market_run.stderr)
            self.assertEqual(_inventory(data_root), before)

            foreign_journal = _operation(
                simple,
                focus=focus,
                journal="cd" * 32,
                market=market,
                text="foreign journal",
                cap={"main": 1, "adaptive": 0, "preview": 0},
            )
            foreign_journal_path = workspace / "foreign-journal.json"
            foreign_journal_path.write_text(json.dumps(foreign_journal), encoding="utf-8")
            journal_run = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(foreign_journal_path),
                "--format",
                "json",
                data_root=data_root,
            )
            journal_payload = json.loads(journal_run.stdout)
            self.assertEqual(journal_payload.get("reason_code"), "ORDINARY_OPERATION_JOURNAL_MISMATCH")
            self.assertTrue(journal_payload.get("writes"), journal_payload)
            self.assertFalse(journal_payload.get("values_loaded"))
            self.assertEqual(_mains(data_root, journal), [])

            other = workspace / "other"
            _publish(other / "rdp", other)
            foreign_corpus = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(foreign_journal_path),
                "--format",
                "json",
                data_root=other / "rdp",
            )
            self.assertIn("ORDINARY_OPERATION_MARKET_MISMATCH", foreign_corpus.stdout + foreign_corpus.stderr)
            self.assertEqual(_mains(data_root, journal), [])

            zero = _simple("boundary-zero", value=999.0)
            thin = temporal_spec(
                "SIMPLE_SCREEN",
                query_id="boundary-thin",
                features=[
                    {
                        "name": "retention",
                        "op": "ratio",
                        "field_id": LIQ,
                        "numerator": "Y900",
                        "denominator": "X300",
                    }
                ],
                all=[{"feature": "retention", "op": "gte", "value": 1.0}],
                cost_profile=None,
                schedule={"lateness_seconds": DOCUMENT_LATENESS},
            )
            adaptive = _simple("boundary-adaptive")
            adaptive["adaptation_of"] = "ee" * 32
            home = _operation(
                zero,
                focus=focus,
                journal=journal,
                market=market,
                text="boundary distinctions",
                cap={"main": 2, "adaptive": 0, "preview": 0},
            )
            home_path = workspace / "home.json"
            home_path.write_text(json.dumps(home), encoding="utf-8")

            def execute(spec: dict, name: str):
                path = workspace / f"{name}.json"
                path.write_text(json.dumps(spec), encoding="utf-8")
                return run_cli(
                    "discovery-execute",
                    "--store",
                    str(data_root),
                    "--spec",
                    str(path),
                    "--candidate-scope",
                    str(scope_path),
                    "--journal-scope",
                    journal,
                    "--operation",
                    str(home_path),
                    "--format",
                    "json",
                    data_root=data_root,
                )

            zero_run = execute(zero, "zero")
            self.assertEqual(zero_run.returncode, 0, zero_run.stderr + zero_run.stdout)
            zero_body = json.loads(zero_run.stdout)
            summary = zero_body["result"]["summary"] if "summary" in zero_body["result"] else zero_body["result"]
            self.assertFalse(summary.get("technical_failure"))
            self.assertEqual(summary.get("matched_n"), 0)
            self.assertEqual(summary.get("feature_unknown_n"), 0)
            self.assertGreater(int(summary.get("decision_eligible_n") or 0), 0)
            thin_run = execute(thin, "thin")
            adaptive_run = execute(adaptive, "adaptive")
            self.assertIn("OWNER_CAP_EXHAUSTED", adaptive_run.stdout + adaptive_run.stderr)
            self.assertFalse(json.loads(adaptive_run.stdout).get("values_loaded"))
            preview_path = workspace / "preview-spec.json"
            preview_path.write_text(json.dumps(_simple("boundary-preview")), encoding="utf-8")
            preview_run = run_cli(
                "discovery-preview",
                "--spec",
                str(preview_path),
                "--store",
                str(data_root),
                "--journal-scope",
                journal,
                "--operation",
                str(home_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertIn("OWNER_CAP_EXHAUSTED", preview_run.stdout + preview_run.stderr)
            self.assertFalse(json.loads(preview_run.stdout).get("values_loaded"))
            mains_after = _mains(data_root, journal)
            self.assertLessEqual(len(mains_after), 2)
            direct = execute_temporal_discovery
            self.assertTrue(callable(direct))
            self.assertEqual(thin_run.returncode, 0, thin_run.stderr + thin_run.stdout)
            thin_body = json.loads(thin_run.stdout)["result"]
            thin_summary = thin_body.get("summary") or thin_body
            self.assertFalse(thin_summary.get("technical_failure"))
            self.assertGreater(int(thin_summary.get("feature_unknown_n") or 0), 0)
            self.assertEqual(thin_summary.get("matched_n"), 0)
            stopped = _operation(
                simple,
                focus=focus,
                journal=journal,
                market=market,
                text="main allowance already zero",
                cap={"main": 0, "adaptive": 0, "preview": 0},
            )
            stopped_path = workspace / "main-zero.json"
            stopped_path.write_text(json.dumps(stopped), encoding="utf-8")
            mains_before_zero_cap = len(_mains(data_root, journal))
            main_zero = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(stopped_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertIn("OWNER_CAP_EXHAUSTED", main_zero.stdout + main_zero.stderr)
            self.assertFalse(json.loads(main_zero.stdout).get("values_loaded"))
            self.assertEqual(len(_mains(data_root, journal)), mains_before_zero_cap)

    def test_recorded_query_requires_operation_and_independent_market(self) -> None:
        from unittest import mock

        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            GroundedDiscoveryError,
            load_admitted_partition_rows,
            run_recorded_discovery_query,
        )
        from solana_alpha_lab.factory.hfic_ordinary_operation import record_operation

        focus = "PUBLISHED_ORDINARY_RECORDED"
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, receipt = _publish_focus(workspace, focus)
            journal = str(receipt["search_key_sha256"])
            market = str(receipt["market_evidence_epoch_sha256"])
            simple = _simple("recorded-gate")
            scope = {
                "population": "BASE_X",
                "decision_timestamp": "Y3600",
                "target": temporal_target_label(simple),
                "estimand": "price_relative_proxy",
                "explanatory_condition": "mark",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            }
            loaded = load_admitted_partition_rows(
                data_root=data_root,
                binding_doc=None,
                partitions=None,
                census_path=None,
                observations_path=None,
            )
            store = ResearchStore(data_root, create_if_missing=False)
            before = _inventory(data_root)
            git_sha = "a" * 40
            for missing in (None, ""):
                with mock.patch(
                    "solana_alpha_lab.factory.hfic_grounded_discovery.execute_discovery_from_rows"
                ) as evaluator:
                    with self.assertRaises(GroundedDiscoveryError) as caught:
                        run_recorded_discovery_query(
                            store,
                            census=loaded["census"],
                            observations=loaded["observations"],
                            spec=simple,
                            binding=loaded["cohorts"],
                            journal_scope=journal,
                            candidate_scope=scope,
                            git_sha=git_sha,
                            operation_sha256=missing,
                            verified_market=market,
                        )
                    self.assertEqual(caught.exception.code, "ORDINARY_OPERATION_REQUIRED")
                    evaluator.assert_not_called()
            self.assertEqual(_inventory(data_root), before)
            self.assertEqual(_mains(data_root, journal), [])
            with mock.patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.execute_discovery_from_rows"
            ) as evaluator:
                with self.assertRaises(GroundedDiscoveryError) as caught:
                    run_recorded_discovery_query(
                        store,
                        census=loaded["census"],
                        observations=loaded["observations"],
                        spec=simple,
                        binding=loaded["cohorts"],
                        journal_scope=journal,
                        candidate_scope=scope,
                        git_sha=git_sha,
                        operation_sha256="ab" * 32,
                        verified_market=market,
                    )
                self.assertEqual(caught.exception.code, "ORDINARY_OPERATION_NOT_FOUND")
                evaluator.assert_not_called()
            with mock.patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.execute_discovery_from_rows"
            ) as evaluator:
                with self.assertRaises(GroundedDiscoveryError) as caught:
                    run_recorded_discovery_query(
                        store,
                        census=loaded["census"],
                        observations=loaded["observations"],
                        spec=simple,
                        binding=loaded["cohorts"],
                        journal_scope=journal,
                        candidate_scope=scope,
                        git_sha=git_sha,
                        operation_sha256="cd" * 32,
                        verified_market=None,
                    )
                self.assertEqual(caught.exception.code, "ORDINARY_OPERATION_MARKET_UNVERIFIED")
                evaluator.assert_not_called()
            self.assertEqual(_inventory(data_root), before)
            zero = record_operation(
                store,
                _operation(
                    simple,
                    focus=focus,
                    journal=journal,
                    market=market,
                    text="cap zero recorded",
                    cap={"main": 0, "adaptive": 0, "preview": 0},
                ),
            )
            after_op = _inventory(data_root)
            with mock.patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.execute_discovery_from_rows"
            ) as evaluator:
                with self.assertRaises(GroundedDiscoveryError) as caught:
                    run_recorded_discovery_query(
                        store,
                        census=loaded["census"],
                        observations=loaded["observations"],
                        spec=simple,
                        binding=loaded["cohorts"],
                        journal_scope=journal,
                        candidate_scope=scope,
                        git_sha=git_sha,
                        operation_sha256=str(zero["operation_sha256"]),
                        verified_market=market,
                    )
                self.assertEqual(caught.exception.code, "OWNER_CAP_EXHAUSTED")
                evaluator.assert_not_called()
            self.assertEqual(_inventory(data_root), after_op)
            self.assertEqual(_mains(data_root, journal), [])
            allowed = record_operation(
                store,
                _operation(
                    simple,
                    focus=focus,
                    journal=journal,
                    market=market,
                    text="one recorded look",
                    cap={"main": 1, "adaptive": 0, "preview": 0},
                ),
            )
            first = run_recorded_discovery_query(
                store,
                census=loaded["census"],
                observations=loaded["observations"],
                spec=simple,
                binding=loaded["cohorts"],
                journal_scope=journal,
                candidate_scope=scope,
                git_sha=git_sha,
                operation_sha256=str(allowed["operation_sha256"]),
                verified_market=market,
            )
            self.assertTrue(first["queries"][0]["new_look"])
            self.assertEqual(len(_mains(data_root, journal)), 1)
            with mock.patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.execute_discovery_from_rows"
            ) as evaluator:
                second = run_recorded_discovery_query(
                    store,
                    census=loaded["census"],
                    observations=loaded["observations"],
                    spec=simple,
                    binding=loaded["cohorts"],
                    journal_scope=journal,
                    candidate_scope=scope,
                    git_sha=git_sha,
                    operation_sha256=str(allowed["operation_sha256"]),
                    verified_market=market,
                )
                evaluator.assert_not_called()
            self.assertFalse(second["queries"][0]["new_look"])
            self.assertEqual(second["result_refs"], first["result_refs"])
            self.assertEqual(len(_mains(data_root, journal)), 1)
            foreign_market = "ef" * 32
            with mock.patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.execute_discovery_from_rows"
            ) as evaluator:
                with self.assertRaises(GroundedDiscoveryError) as caught:
                    run_recorded_discovery_query(
                        store,
                        census=loaded["census"],
                        observations=loaded["observations"],
                        spec=simple,
                        binding=loaded["cohorts"],
                        journal_scope=journal,
                        candidate_scope=scope,
                        git_sha=git_sha,
                        operation_sha256=str(allowed["operation_sha256"]),
                        verified_market=foreign_market,
                    )
                self.assertEqual(caught.exception.code, "ORDINARY_OPERATION_MARKET_MISMATCH")
                evaluator.assert_not_called()
            self.assertEqual(len(_mains(data_root, journal)), 1)
