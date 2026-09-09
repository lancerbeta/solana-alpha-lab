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

from jsonschema import Draft202012Validator

from solana_alpha_lab.factory.hfic_preflight import decide_preflight_action
from solana_alpha_lab.factory.hfic_session import (
    HficSessionError,
    RUNNER_UP_AWAITING_CRITIC,
    RUNNER_UP_REVISION_REQUIRED,
    _canonical_json_hash,
    _verify_failover_receipt_identity,
    apply_revision,
    finalize_session,
    freeze_draft,
    load_session_bundle,
    phase_rank,
    prove_runtime,
)
from solana_alpha_lab.factory.research_store import ResearchStore
from tests.test_hfic_cli import bind_draft, critic_result_from_packet_only, run_cli
from tests.test_hfic_session import _persist_frozen_portfolio, _preflight_receipt, valid_draft

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_V12 = ROOT / "catalog/schemas/hypothesis_forge_session_receipt_v1_2.schema.json"
RECEIPT_V13 = ROOT / "catalog/schemas/hypothesis_forge_session_receipt_v1_3.schema.json"
HAPPY = ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"


class HficOneFrozenRunnerUpFailoverTests(unittest.TestCase):
    def test_t1_pre_frozen_c2_packet_before_critic(self) -> None:
        frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt(), repo_root=ROOT)
        primary = frozen["critic_input_packet"]
        runner = frozen["runner_up_critic_input_packet"]
        self.assertNotEqual(frozen["selected_candidate_id"], frozen["runner_up_candidate_id"])
        self.assertEqual(primary["session_id"], runner["session_id"])
        self.assertEqual(primary["session_id"], frozen["session_id"])
        self.assertEqual(primary["selected_candidate"]["candidate_id"], frozen["selected_candidate_id"])
        self.assertEqual(runner["selected_candidate"]["candidate_id"], frozen["runner_up_candidate_id"])
        self.assertNotIn("critic_result", runner)
        self.assertNotIn("critic_terminal", runner)
        self.assertEqual(frozen["critic_input_packet_sha256"], _canonical_json_hash(primary))
        self.assertEqual(
            frozen["runner_up_critic_input_packet_sha256"],
            _canonical_json_hash(runner),
        )
        self.assertNotEqual(
            frozen["critic_input_packet_sha256"],
            frozen["runner_up_critic_input_packet_sha256"],
        )
        self.assertEqual(
            frozen["runner_up_definition_sha256"],
            _identity_sha(runner["selected_candidate"]),
        )

    def test_t10_same_prior_memory_snapshot(self) -> None:
        draft = json.loads(HAPPY.read_text(encoding="utf-8"))
        frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
        primary = frozen["critic_input_packet"]
        runner = frozen["runner_up_critic_input_packet"]
        self.assertEqual(primary["packet_version"], "1.3")
        self.assertEqual(
            primary["prior_memory"]["snapshot_sha256"],
            runner["prior_memory"]["snapshot_sha256"],
        )
        self.assertIs(primary["prior_memory"], runner["prior_memory"])

    def test_t2_primary_kill_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(pending["session_state"], RUNNER_UP_AWAITING_CRITIC)
            self.assertIsNone(pending.get("session_receipt"))
            decisions = pending["decisions"]
            self.assertEqual(
                decisions[frozen["selected_candidate_id"]]["reason_code"],
                "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED",
            )
            self.assertNotEqual(
                decisions.get(frozen["runner_up_candidate_id"], {}).get("reason_code"),
                "NOT_SELECTED_IN_SESSION",
            )
            bundle = load_session_bundle(store, frozen["session_id"])
            assert bundle is not None
            self.assertEqual(bundle["session_state"], RUNNER_UP_AWAITING_CRITIC)
            self.assertIsNone(bundle.get("session_receipt"))
            self.assertEqual(
                bundle["critic_input_packet_sha256"],
                frozen["runner_up_critic_input_packet_sha256"],
            )

    def test_t5_t7_double_kill_and_no_shopping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_PIT_OR_LEAKAGE"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(pending["session_state"], RUNNER_UP_AWAITING_CRITIC)
            with self.assertRaises(HficSessionError) as replay:
                finalize_session(
                    pending,
                    critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_PIT_OR_LEAKAGE"),
                    store=store,
                    repo_root=ROOT,
                )
            self.assertIn(
                str(replay.exception),
                {"CRITIC_PACKET_HASH_MISMATCH", "CRITIC_SELECTED_MISMATCH", "CRITIC_DEFINITION_HASH_MISMATCH"},
            )
            mutated = dict(pending["critic_input_packet"])
            selected = dict(mutated["selected_candidate"])
            selected["claim"] = "altered runner-up claim after C1 kill"
            mutated["selected_candidate"] = selected
            with self.assertRaises(HficSessionError) as altered:
                finalize_session(
                    pending,
                    critic_result_from_packet_only(mutated, "KILL_MECHANISM"),
                    store=store,
                    repo_root=ROOT,
                )
            self.assertIn(
                str(altered.exception),
                {"CRITIC_PACKET_HASH_MISMATCH", "CRITIC_DEFINITION_HASH_MISMATCH"},
            )
            done = finalize_session(
                pending,
                critic_result_from_packet_only(pending["critic_input_packet"], "KILL_MECHANISM"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(done["decisions"][frozen["selected_candidate_id"]]["reason_code"], "KILL_PIT_OR_LEAKAGE")
            self.assertEqual(done["decisions"][frozen["runner_up_candidate_id"]]["reason_code"], "KILL_MECHANISM")
            self.assertIsNone(done.get("final_survivor_candidate_id"))
            self.assertEqual(done.get("critic_screen_count"), 2)
            self.assertTrue(done.get("runner_up_failover_used") or done["prompt_version"] != "HFIC-V1.2")

    def test_t6_no_failover_on_non_kill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            critic = critic_result_from_packet_only(
                frozen["critic_input_packet"],
                "OWNER_DECISION_REQUIRED",
            )
            done = finalize_session(frozen, critic, store=store, repo_root=ROOT)
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(
                done["decisions"][frozen["runner_up_candidate_id"]]["reason_code"],
                "NOT_SELECTED_IN_SESSION",
            )
            self.assertEqual(done["prompt_version"], "HFIC-V1.2")
            self.assertFalse(done["runner_up_failover_used"])
            self.assertEqual(done["critic_screen_count"], 1)
            self.assertIsNone(done.get("runner_up_critic_terminal"))
            self.assertIsNone(done.get("runner_up_critic_result_sha256"))
            self.assertEqual(done.get("final_session_terminal"), "OWNER_DECISION_REQUIRED")
            self.assertEqual(done.get("critic_terminal"), "OWNER_DECISION_REQUIRED")
            replay = finalize_session(frozen, critic, store=store, repo_root=ROOT)
            self.assertEqual(replay["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(
                replay["decisions"][frozen["runner_up_candidate_id"]]["reason_code"],
                "NOT_SELECTED_IN_SESSION",
            )

    def test_t8_runner_up_revise_pauses_without_revision(self) -> None:
        from solana_alpha_lab.factory.hfic_session import show_session

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM"),
                store=store,
                repo_root=ROOT,
            )
            revise = critic_result_from_packet_only(pending["critic_input_packet"], "REVISE_ONCE")
            revise["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            revise["next"] = "RESUME_REVISE"
            done = finalize_session(pending, revise, store=store, repo_root=ROOT)
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(done.get("next"), "STOP")
            self.assertEqual(
                done["decisions"][frozen["runner_up_candidate_id"]]["reason_code"],
                RUNNER_UP_REVISION_REQUIRED,
            )
            self.assertEqual(
                done["decisions"][frozen["runner_up_candidate_id"]]["decision_kind"],
                "PAUSE",
            )
            self.assertIsNone(done.get("final_survivor_candidate_id"))
            bundle = load_session_bundle(store, frozen["session_id"])
            assert bundle is not None
            self.assertNotEqual(bundle["session_state"], "REVISION_REQUIRED")
            self.assertEqual((bundle.get("critic_result") or {}).get("critic_terminal"), "KILL_MECHANISM")
            self.assertEqual(done.get("critic_terminal"), "KILL_MECHANISM")
            self.assertEqual(done.get("final_session_terminal"), RUNNER_UP_REVISION_REQUIRED)
            self.assertEqual(done.get("runner_up_critic_terminal"), "REVISE_ONCE")
            self.assertEqual(done.get("primary_critic_terminal"), "KILL_MECHANISM")
            shown = show_session(store, frozen["session_id"], repo_root=ROOT)
            self.assertEqual(shown.get("critic_terminal"), "KILL_MECHANISM")
            self.assertEqual(shown.get("final_session_terminal"), RUNNER_UP_REVISION_REQUIRED)
            self.assertEqual(shown.get("runner_up_critic_terminal"), "REVISE_ONCE")
            self.assertTrue(shown.get("runner_up_failover_used"))
            self.assertIsNone(shown.get("lane_classifier_terminal"))
            replay = finalize_session(pending, revise, store=store, repo_root=ROOT)
            self.assertEqual(replay["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(replay.get("final_session_terminal"), RUNNER_UP_REVISION_REQUIRED)

    def test_t4_runner_up_owner_pause_survivor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED"),
                store=store,
                repo_root=ROOT,
            )
            done = finalize_session(
                pending,
                critic_result_from_packet_only(pending["critic_input_packet"], "OWNER_DECISION_REQUIRED"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(
                done["decisions"][frozen["runner_up_candidate_id"]]["reason_code"],
                "OWNER_DECISION_REQUIRED",
            )
            self.assertEqual(done["selected_candidate_id"], frozen["selected_candidate_id"])
            self.assertNotEqual(done["selected_candidate_id"], frozen["runner_up_candidate_id"])
            self.assertEqual(done["final_survivor_candidate_id"], frozen["runner_up_candidate_id"])
            self.assertTrue(done["runner_up_failover_used"])
            self.assertEqual(done["critic_screen_count"], 2)

    def test_classifier_mapped_c1_kill_keeps_c1_classifier_receipt_while_parked(self) -> None:
        from tests.test_observation_fast_lane_routing_closure import (
            AS_OF_START,
            forge_classify,
            packet_for,
            v1_2_spec,
        )

        spec = v1_2_spec(as_of="2026-09-01T12:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            forged = forge_classify(packet_for(spec), data_root, AS_OF_START)
            self.assertEqual(forged["session_state"], RUNNER_UP_AWAITING_CRITIC)
            self.assertEqual(forged["classifier_terminal"], "DENY_INVALID_SPEC")
            self.assertEqual(forged["hfic_terminal"], "KILL_UNBOUND_EVIDENCE")

    def test_classifier_mapped_c1_kill_then_c2_classify(self) -> None:
        from solana_alpha_lab.factory.hfic_session import apply_classification
        from tests.test_fast_lane_classifier import submission
        from tests.test_observation_fast_lane_routing_closure import packet_for, v1_2_spec

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(
                    frozen["critic_input_packet"], "PASS_TO_CLASSIFICATION"
                ),
                store=store,
                repo_root=ROOT,
            )
            future = packet_for(v1_2_spec(as_of="2026-09-01T12:00:00Z"))
            future["hypothesis_definition_sha256"] = frozen["selected_definition_sha256"]
            future["classifier_evaluated_at"] = "2026-09-01T00:00:00Z"
            parked = apply_classification(
                pending,
                future,
                store=store,
                repo_root=ROOT,
                data_root=Path(tmp),
            )
            self.assertEqual(parked["session_state"], RUNNER_UP_AWAITING_CRITIC)
            parked_receipt = parked.get("classifier_receipt") or {}
            self.assertEqual(parked_receipt.get("lane_classifier_terminal"), "DENY_INVALID_SPEC")
            waiting = finalize_session(
                parked,
                critic_result_from_packet_only(
                    parked["critic_input_packet"], "PASS_TO_CLASSIFICATION"
                ),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(waiting["session_state"], "AWAITING_CLASSIFICATION")
            packet = submission()
            packet["hypothesis_definition_sha256"] = frozen["runner_up_definition_sha256"]
            done = apply_classification(
                waiting,
                packet,
                store=store,
                repo_root=ROOT,
                data_root=Path(tmp),
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertTrue(done["runner_up_failover_used"])
            bundle = load_session_bundle(store, frozen["session_id"])
            assert bundle is not None
            classifier = bundle.get("classifier_receipt") or {}
            self.assertEqual(
                classifier.get("selected_candidate_id"),
                frozen["runner_up_candidate_id"],
            )
            self.assertIsNone(bundle.get("lane_classifier_terminal"))
            self.assertIsNone((bundle.get("session_receipt") or {}).get("lane_classifier_terminal"))

    def test_t4_classifier_acts_on_c2_spec(self) -> None:
        from solana_alpha_lab.factory.hfic_session import apply_classification
        from tests.test_fast_lane_classifier import submission

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM"),
                store=store,
                repo_root=ROOT,
            )
            waiting = finalize_session(
                pending,
                critic_result_from_packet_only(pending["critic_input_packet"], "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(waiting["session_state"], "AWAITING_CLASSIFICATION")
            c2 = pending["critic_input_packet"]["selected_candidate"]
            self.assertEqual(c2["candidate_id"], frozen["runner_up_candidate_id"])
            packet = submission()
            packet["hypothesis_definition_sha256"] = frozen["runner_up_definition_sha256"]
            done = apply_classification(
                waiting,
                packet,
                store=store,
                repo_root=ROOT,
                data_root=Path(tmp),
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(done["final_survivor_candidate_id"], frozen["runner_up_candidate_id"])
            self.assertNotEqual(done["final_survivor_candidate_id"], frozen["selected_candidate_id"])
            bundle = load_session_bundle(store, frozen["session_id"])
            assert bundle is not None
            receipt = bundle.get("classifier_receipt") or {}
            self.assertEqual(receipt.get("selected_candidate_id"), frozen["runner_up_candidate_id"])
            self.assertEqual(
                receipt.get("selected_definition_sha256"),
                frozen["runner_up_definition_sha256"],
            )
            session_receipt = bundle.get("session_receipt") or {}
            self.assertIsNone(session_receipt.get("lane_classifier_terminal"))
            self.assertIsNone(bundle.get("lane_classifier_terminal"))

    def test_t11_historical_v12_receipt_schema_still_validates(self) -> None:
        schema = json.loads(RECEIPT_V12.read_text(encoding="utf-8"))
        historical = {
            "session_id": "HFIC-SESS-HISTORICAL0001",
            "session_state": "SYNTHESIS_COMPLETE",
            "evidence_epoch_sha256": "ab" * 32,
            "focus_key_sha256": "cd" * 32,
            "search_key_sha256": "ef" * 32,
            "prompt_version": "HFIC-V1.2",
            "live_git_head": "a" * 40,
            "store_inventory_digest": "11" * 32,
            "candidate_ids": [
                "HFIC-CAND-" + "A" * 12,
                "HFIC-CAND-" + "B" * 12,
                "HFIC-CAND-" + "C" * 12,
                "HFIC-CAND-" + "D" * 12,
            ],
            "selected_candidate_id": "HFIC-CAND-" + "A" * 12,
            "runner_up_candidate_id": "HFIC-CAND-" + "B" * 12,
            "critic_input_packet_sha256": "22" * 32,
            "critic_result_sha256": "33" * 32,
            "critic_terminal": "KILL_MECHANISM",
            "lane_classifier_terminal": None,
            "decision_event_ids": ["HFIC-DEC-1"],
            "next": "STOP",
            "authority": {
                "git_mutation": 0,
                "experiment_execution": 0,
                "provider_api_rpc_wss_calls": 0,
            },
            "no_git_fence_receipt": {},
            "created_at": "2026-09-01T00:00:00Z",
            "diagnostics": {
                "candidate_count": 4,
                "known_feature_reference_count": 0,
                "known_capability_reference_count": 0,
                "candidate_with_unresolved_requirement_count": 0,
                "unresolved_requirement_count": 0,
                "unique_structural_signature_count": 1,
                "structural_repetition_count": 0,
                "structural_repetition_ratio": 0,
                "critic_terminal": "KILL_MECHANISM",
                "selected_candidate_present": True,
                "no_worthy_hypothesis": False,
            },
        }
        errors = list(Draft202012Validator(schema).iter_errors(historical))
        self.assertEqual(errors, [])
        v13 = json.loads(RECEIPT_V13.read_text(encoding="utf-8"))
        self.assertTrue(list(Draft202012Validator(v13).iter_errors(historical)))

    def test_t3_t9_cli_resume_same_auto_session(self) -> None:
        draft = json.loads(HAPPY.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            preflight = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            self.assertEqual(receipt["action"], "START_NEW_SESSION")
            search_key = receipt["search_key_sha256"]
            bound = bind_draft(draft, receipt)
            draft_path = data_root / "draft.json"
            preflight_path = data_root / "preflight.json"
            draft_path.write_text(json.dumps(bound), encoding="utf-8")
            preflight_path.write_text(json.dumps(receipt), encoding="utf-8")
            frozen_proc = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(preflight_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_proc.returncode, 0, frozen_proc.stderr)
            frozen = json.loads(frozen_proc.stdout)
            session_id = frozen["session_id"]
            primary_sha = frozen["critic_input_packet_sha256"]
            runner_sha = frozen["runner_up_critic_input_packet_sha256"]
            self.assertNotEqual(primary_sha, runner_sha)
            critic_path = data_root / "c1.json"
            critic_path.write_text(
                json.dumps(
                    critic_result_from_packet_only(
                        frozen["critic_input_packet"],
                        "KILL_MECHANISM",
                    )
                ),
                encoding="utf-8",
            )
            first = run_cli(
                "finalize",
                "--session-id",
                session_id,
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            pending = json.loads(first.stdout)
            self.assertEqual(pending["session_state"], RUNNER_UP_AWAITING_CRITIC)
            resume = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(resume.returncode, 0, resume.stderr)
            resume_payload = json.loads(resume.stdout)
            self.assertEqual(resume_payload["action"], "RESUME_CRITIC")
            self.assertEqual(resume_payload["session_id"], session_id)
            self.assertEqual(resume_payload["search_key_sha256"], search_key)
            self.assertEqual(resume_payload["critic_input_packet_sha256"], runner_sha)
            self.assertNotEqual(resume_payload["critic_input_packet_sha256"], primary_sha)
            sessions = [
                {
                    "session_id": session_id,
                    "session_state": RUNNER_UP_AWAITING_CRITIC,
                    "evidence_epoch_sha256": resume_payload["evidence_epoch_sha256"],
                    "focus_key_sha256": resume_payload["focus_key_sha256"],
                    "search_key_sha256": search_key,
                    "owner_focus": "AUTO",
                }
            ]
            action, bound_id = decide_preflight_action(
                sessions,
                search_key=search_key,
                evidence_epoch=str(resume_payload["evidence_epoch_sha256"]),
                focus_key=str(resume_payload["focus_key_sha256"]),
                owner_focus="AUTO",
            )
            self.assertEqual(action, "RESUME_CRITIC")
            self.assertEqual(bound_id, session_id)
            c2_path = data_root / "c2.json"
            c2_path.write_text(
                json.dumps(
                    critic_result_from_packet_only(
                        resume_payload["critic_input_packet"],
                        "KILL_DATA_INFEASIBLE",
                    )
                ),
                encoding="utf-8",
            )
            second = run_cli(
                "finalize",
                "--session-id",
                session_id,
                "--critic-result",
                str(c2_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            done = json.loads(second.stdout)
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(done["critic_screen_count"], 2)
            self.assertTrue(done["runner_up_failover_used"])
            after = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(after.returncode, 0, after.stderr)
            after_payload = json.loads(after.stdout)
            self.assertEqual(after_payload["action"], "RETURN_EXISTING_SESSION")
            self.assertEqual(after_payload["session_id"], session_id)
            self.assertEqual(after_payload["search_key_sha256"], search_key)

    def test_classifier_kill_on_primary_parks_runner_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            waiting = finalize_session(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(waiting["session_state"], "AWAITING_CLASSIFICATION")
            parked = finalize_session(
                waiting,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_UNBOUND_EVIDENCE"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(parked["session_state"], RUNNER_UP_AWAITING_CRITIC)
            self.assertIsNone(parked.get("session_receipt"))

    def test_declared_c2_sha_without_packet_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            mutated = dict(frozen)
            mutated.pop("runner_up_critic_input_packet")
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(
                    mutated,
                    critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM"),
                    store=store,
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "RUNNER_UP_PACKET_MISSING")

    def test_declared_c2_sha_without_packet_fail_closed_on_non_kill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            mutated = dict(frozen)
            mutated.pop("runner_up_critic_input_packet")
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(
                    mutated,
                    critic_result_from_packet_only(
                        frozen["critic_input_packet"],
                        "OWNER_DECISION_REQUIRED",
                    ),
                    store=store,
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "RUNNER_UP_PACKET_MISSING")

    def test_historical_v12_without_c2_sha_one_shot_kill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            mutated = dict(frozen)
            mutated.pop("runner_up_critic_input_packet")
            mutated.pop("runner_up_critic_input_packet_sha256")
            with self.assertRaises(HficSessionError) as fresh:
                finalize_session(
                    mutated,
                    critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM"),
                    store=store,
                    repo_root=ROOT,
                )
            self.assertEqual(str(fresh.exception), "RUNNER_UP_PACKET_MISSING")
            _persist_frozen_portfolio(store, mutated, draft)
            done = finalize_session(
                mutated,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertFalse(done.get("runner_up_failover_used"))
            self.assertEqual(done.get("critic_screen_count"), 1)

    def test_stored_identity_wins_over_caller_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM"),
                store=store,
                repo_root=ROOT,
            )
            tampered = dict(frozen)
            tampered["runner_up_critic_input_packet_sha256"] = "0" * 64
            done = finalize_session(
                tampered,
                critic_result_from_packet_only(pending["critic_input_packet"], "OWNER_DECISION_REQUIRED"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertTrue(done["runner_up_failover_used"])

    def test_synthesis_complete_replay_does_not_bind_c2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            critic = critic_result_from_packet_only(
                frozen["critic_input_packet"],
                "OWNER_DECISION_REQUIRED",
            )
            done = finalize_session(frozen, critic, store=store, repo_root=ROOT)
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            c2 = critic_result_from_packet_only(
                frozen["runner_up_critic_input_packet"],
                "PASS_TO_CLASSIFICATION",
            )
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(frozen, c2, store=store, repo_root=ROOT)
            self.assertEqual(str(raised.exception), "SESSION_CONFLICT")

    def test_failover_complete_replay_binds_c2_not_c1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            c1 = critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM")
            pending = finalize_session(frozen, c1, store=store, repo_root=ROOT)
            c2 = critic_result_from_packet_only(
                pending["critic_input_packet"],
                "KILL_UNBOUND_EVIDENCE",
            )
            done = finalize_session(pending, c2, store=store, repo_root=ROOT)
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            replay = finalize_session(pending, c2, store=store, repo_root=ROOT)
            self.assertEqual(replay["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(
                replay.get("runner_up_critic_result_sha256"),
                done.get("runner_up_critic_result_sha256"),
            )
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(frozen, c1, store=store, repo_root=ROOT)
            self.assertEqual(str(raised.exception), "SESSION_CONFLICT")

    def test_phase_rank_and_revise_then_kill_parks_c2(self) -> None:
        self.assertEqual(phase_rank("AWAITING_CLASSIFICATION"), phase_rank(RUNNER_UP_AWAITING_CRITIC))
        self.assertLess(phase_rank(RUNNER_UP_AWAITING_CRITIC), phase_rank("REVISED_AWAITING_CRITIC"))
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            revise = critic_result_from_packet_only(frozen["critic_input_packet"], "REVISE_ONCE")
            revise["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            finalize_session(frozen, revise, store=store, repo_root=ROOT)
            draft = valid_draft()
            draft["candidates"][0]["claim"] = "Claim one, revised wording."
            revised = apply_revision(
                load_session_bundle(store, frozen["session_id"]),
                draft,
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(revised["session_state"], "REVISED_AWAITING_CRITIC")
            kill = critic_result_from_packet_only(revised["critic_input_packet"], "KILL_PREPARATORY_LOOP")
            parked = finalize_session(revised, kill, store=store, repo_root=ROOT)
            self.assertEqual(parked["session_state"], RUNNER_UP_AWAITING_CRITIC)
            self.assertEqual(
                parked.get("primary_critic_input_packet_sha256"),
                kill["critic_input_packet_sha256"],
            )
            self.assertNotEqual(
                parked.get("primary_critic_input_packet_sha256"),
                frozen["critic_input_packet_sha256"],
            )
            bundle = load_session_bundle(store, frozen["session_id"])
            assert bundle is not None
            self.assertEqual(bundle["session_state"], RUNNER_UP_AWAITING_CRITIC)

    def test_missing_c2_result_artifact_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            _persist_frozen_portfolio(store, frozen, draft)
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM"),
                store=store,
                repo_root=ROOT,
            )
            done = finalize_session(
                pending,
                critic_result_from_packet_only(
                    pending["critic_input_packet"],
                    "KILL_UNBOUND_EVIDENCE",
                ),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            prove_runtime(store, frozen["session_id"], repo_root=ROOT)
            bundle = load_session_bundle(store, frozen["session_id"])
            assert bundle is not None
            drop_sha = str(bundle["runner_up_critic_result_sha256"])
            self.assertEqual(len(drop_sha), 64)
            self.assertIsNotNone(bundle.get("runner_up_critic_result"))
            receipt = dict(bundle["session_receipt"])
            _verify_failover_receipt_identity(receipt)
            swapped = dict(receipt)
            swapped["selected_candidate_id"] = frozen["runner_up_candidate_id"]
            with self.assertRaises(HficSessionError) as identity:
                _verify_failover_receipt_identity(swapped)
            self.assertEqual(str(identity.exception), "HFIC_PROTOCOL_INVALID")
            collided = dict(receipt)
            collided["runner_up_critic_result_sha256"] = receipt["critic_result_sha256"]
            with self.assertRaises(HficSessionError) as same_hash:
                _verify_failover_receipt_identity(collided)
            self.assertEqual(str(same_hash.exception), "HFIC_PROTOCOL_INVALID")

            class _DropC2Result:
                def __init__(self, inner: ResearchStore, sha: str) -> None:
                    self._inner = inner
                    self._sha = sha

                def iter_committed_records(self):
                    for record in self._inner.iter_committed_records():
                        payload = json.loads(record.payload_json)
                        if (
                            payload.get("artifact_kind") == "CRITIC_RESULT"
                            and payload.get("payload_sha256") == self._sha
                        ):
                            continue
                        yield record

            with self.assertRaises(HficSessionError) as missing:
                prove_runtime(
                    _DropC2Result(store, drop_sha),
                    frozen["session_id"],
                    repo_root=ROOT,
                )
            self.assertEqual(str(missing.exception), "CRITIC_RESULT_ARTIFACT_MISSING")

    def test_missing_c2_input_artifact_fail_closed_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = json.loads(HAPPY.read_text(encoding="utf-8"))
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
            _persist_frozen_portfolio(store, frozen, draft)
            pending = finalize_session(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM"),
                store=store,
                repo_root=ROOT,
            )
            finalize_session(
                pending,
                critic_result_from_packet_only(
                    pending["critic_input_packet"],
                    "KILL_UNBOUND_EVIDENCE",
                ),
                store=store,
                repo_root=ROOT,
            )
            bundle = load_session_bundle(store, frozen["session_id"])
            assert bundle is not None
            drop_sha = str(bundle["runner_up_critic_input_packet_sha256"])
            self.assertEqual(len(drop_sha), 64)

            class _DropC2Input:
                def __init__(self, inner: ResearchStore, sha: str) -> None:
                    self._inner = inner
                    self._sha = sha

                def iter_committed_records(self):
                    for record in self._inner.iter_committed_records():
                        payload = json.loads(record.payload_json)
                        if (
                            payload.get("artifact_kind") == "CRITIC_INPUT_PACKET"
                            and payload.get("payload_sha256") == self._sha
                        ):
                            continue
                        yield record

            dropped = _DropC2Input(store, drop_sha)
            with self.assertRaises(HficSessionError) as missing:
                load_session_bundle(dropped, frozen["session_id"])
            self.assertEqual(str(missing.exception), "CRITIC_INPUT_ARTIFACT_MISSING")
            with self.assertRaises(HficSessionError) as proved:
                prove_runtime(dropped, frozen["session_id"], repo_root=ROOT)
            self.assertEqual(str(proved.exception), "CRITIC_INPUT_ARTIFACT_MISSING")


def _identity_sha(selected: dict) -> str:
    from solana_alpha_lab.factory.hfic_identity import candidate_identity

    return candidate_identity(
        {
            "claim": selected["claim"],
            "mechanism": selected["mechanism"],
            "actor_counterparty": selected["actor_counterparty"],
            "population": selected["population"],
            "decision_timestamp": selected["decision_timestamp"],
            "primary_x_family": selected["primary_x"],
            "primary_y": selected["primary_y"],
            "horizon_notional": selected["horizon_notional"],
            "negative_control": selected["negative_control"],
            "cheapest_falsifier": selected["cheapest_falsifier"],
        }
    ).full_sha256


if __name__ == "__main__":
    unittest.main()
