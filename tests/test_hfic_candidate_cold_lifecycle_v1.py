"""Candidate cold lifecycle: a completed session is found by a new process; proof is by reference.

Two owner-path defects are pinned here:

* a completed ordinary ``KILL_MECHANISM`` session was not selected by ordinary
  completed-session discovery, so a fresh process projected a stale frozen
  draft and blocked;
* ``candidates_retrievable`` asked "did this session produce at least four
  candidates?" instead of "do the candidate references this session claims
  durably resolve?".

Critic inputs are scripted mechanical routing inputs, marked
SCRIPTED_CRITIC_MECHANICAL. They are not scientific model acceptance.
No market or frozen scientific experiment runs here.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    list_discovery_looks,
)
from solana_alpha_lab.factory.hfic_representation_ladder import (  # noqa: E402
    KNOWN_SCIENTIFIC_NEGATIVES,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    temporal_target_label,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    _bundle_candidate_reference_gaps,
    freeze_draft,
    _verify_store_reference_resolution,
    candidate_reference_gaps,
    load_session_bundle,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_fast_lane_classifier import experiment_spec  # noqa: E402
from tests.test_hfic_cli import bind_draft, run_cli  # noqa: E402
from tests.test_hfic_ordinary_operation_acceptance_v1 import (  # noqa: E402
    _operation,
    _publish_focus,
    _simple,
)

ROOT = Path(__file__).resolve().parents[1]
DRAFT_FIXTURE = ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"

SCRIPTED = ["NO_ALPHA", "SCRIPTED_CRITIC_MECHANICAL"]


def _mains(data_root: Path, journal: str) -> int:
    looks = list_discovery_looks(ResearchStore(data_root, create_if_missing=False), journal)
    return sum(1 for item in looks if item.get("look_class") == "MAIN" and item.get("new_look") is True)


def _candidate_records(data_root: Path) -> int:
    store = ResearchStore(data_root, create_if_missing=False)
    return sum(
        1
        for record in store.iter_committed_records()
        if getattr(record.record_kind, "value", record.record_kind) == "HYPOTHESIS_VERSION"
    )


class _Saved:
    """One durable ordinary session with exactly one candidate, frozen and finalized."""

    def __init__(self, workspace: Path, focus: str, *, candidate_count: int = 1) -> None:
        self.workspace = workspace
        self.focus = focus
        self.candidate_count = candidate_count
        self.data_root, self.receipt = _publish_focus(workspace, focus)
        self.journal = str(self.receipt["search_key_sha256"])
        self.market = str(self.receipt["market_evidence_epoch_sha256"])
        self.spec = _simple(f"cold-{focus.lower()}")
        self.scope = {
            "population": "BASE_X",
            "decision_timestamp": "Y3600",
            "target": temporal_target_label(self.spec),
            "estimand": "price_relative_proxy",
            "explanatory_condition": "mark",
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
        }
        self.evidence = self._execute()
        self.cards, self.draft_path, self.receipt_path = self._persist()
        self.card = self.cards[0]

    def _write(self, name: str, payload: object) -> Path:
        path = self.workspace / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _execute(self) -> dict:
        spec_path = self._write("spec.json", self.spec)
        scope_path = self._write("scope.json", self.scope)
        op_path = self._write(
            "op.json",
            _operation(
                self.spec,
                focus=self.focus,
                journal=self.journal,
                market=self.market,
                text="one simple look for the cold lifecycle",
                cap={"main": 1, "adaptive": 0, "preview": 0},
            ),
        )
        self.scope_path = scope_path
        done = run_cli(
            "discovery-execute",
            "--store", str(self.data_root),
            "--spec", str(spec_path),
            "--candidate-scope", str(scope_path),
            "--journal-scope", self.journal,
            "--operation", str(op_path),
            "--format", "json",
            data_root=self.data_root,
        )
        assert done.returncode == 0, done.stderr + done.stdout
        return json.loads(done.stdout)

    def _persist(self) -> tuple[list[dict], Path, Path]:
        source = json.loads(DRAFT_FIXTURE.read_text(encoding="utf-8"))
        cards = [dict(item) for item in source["candidates"][: self.candidate_count]]
        cards[0].update({key: self.scope[key] for key in ("population", "decision_timestamp", "target", "estimand", "explanatory_condition")})
        draft = bind_draft({**source, "candidates": cards}, self.receipt)
        if len(cards) < 2:
            draft.pop("runner_up_candidate_ref", None)
            draft.pop("strongest_rejected_alternative", None)
        draft["selected_candidate_ref"] = cards[0]["label"]
        draft["grounded_evidence"] = self.evidence
        draft["owner_focus"] = self.focus
        draft_path = self._write("draft.json", draft)
        receipt_path = self._write("preflight.json", self.receipt)
        done = run_cli(
            "persist-draft",
            "--draft", str(draft_path),
            "--preflight-receipt", str(receipt_path),
            "--representation-id", "BASE",
            "--format", "json",
            data_root=self.data_root,
        )
        assert done.returncode == 0, done.stderr + done.stdout
        return cards, draft_path, receipt_path

    def freeze(self) -> dict:
        opened = run_cli(
            "preflight", "--discovery-contract", "--owner-focus", self.focus,
            "--format", "json", data_root=self.data_root,
        )
        assert opened.returncode == 0, opened.stderr + opened.stdout
        resume_path = self._write("resume.json", json.loads(opened.stdout))
        done = run_cli(
            "freeze",
            "--draft", str(self.draft_path),
            "--preflight-receipt", str(resume_path),
            "--format", "json",
            data_root=self.data_root,
        )
        assert done.returncode == 0, done.stderr + done.stdout
        return json.loads(done.stdout)

    def finalize(self, frozen: dict, terminal: str) -> dict:
        critic = {
            "schema": "smial.hypothesis-critic-result",
            "schema_version": "1.1",
            "session_id": frozen["session_id"],
            "critic_input_packet_sha256": frozen["critic_input_packet_sha256"],
            "selected_candidate_id": frozen["selected_candidate_id"],
            "selected_definition_sha256": frozen["selected_definition_sha256"],
            "critic_prompt_version": "HFIC-V1.1",
            "isolated_context_attestation": "NEW_CONTEXT_REQUIRED",
            "critic_terminal": terminal,
            "next": "STOP",
            "authority": {"git_mutation": 0, "experiment_execution": 0, "provider_api_rpc_wss_calls": 0},
            "non_claims": SCRIPTED,
        }
        critic_path = self._write("critic.json", critic)
        done = run_cli(
            "finalize",
            "--session-id", str(frozen["session_id"]),
            "--critic-result", str(critic_path),
            "--format", "json",
            data_root=self.data_root,
        )
        assert done.returncode == 0, done.stderr + done.stdout
        return json.loads(done.stdout)

    def classify(self, frozen: dict) -> dict:
        packet = {
            "experiment_spec": experiment_spec(),
            "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
        }
        packet["experiment_spec"]["required_feature_ids"] = list(self.card.get("required_feature_ids") or [])
        packet_path = self._write("classify.json", packet)
        done = run_cli(
            "classify",
            "--session-id", str(frozen["session_id"]),
            "--experiment-spec", str(packet_path),
            "--format", "json",
            data_root=self.data_root,
        )
        assert done.returncode == 0, done.stderr + done.stdout
        return json.loads(done.stdout)

    # --- cold reads, each in a new process -------------------------------------------

    def cold_show(self, session_id: str) -> dict:
        done = run_cli("show-session", "--session-id", session_id, "--format", "json", data_root=self.data_root)
        assert done.returncode == 0, done.stderr + done.stdout
        return json.loads(done.stdout)

    def cold_run(self) -> tuple[int, dict]:
        done = run_cli("forge-run", "--owner-focus", self.focus, "--no-write", "--format", "json", data_root=self.data_root)
        return done.returncode, json.loads(done.stdout)

    def cold_prove(self, session_id: str) -> tuple[int, dict, str]:
        done = run_cli("prove-runtime", "--session-id", session_id, "--format", "json", data_root=self.data_root)
        body = json.loads(done.stdout) if done.stdout.strip().startswith("{") else {}
        return done.returncode, body, done.stderr


class CandidateReferenceGapTests(unittest.TestCase):
    """Reference completeness, not portfolio size."""

    def test_quantity_is_not_a_reference_property(self) -> None:
        for claimed in ([], ["A"], ["A", "B", "C", "D"], ["A", "B", "C", "D", "E", "F"]):
            self.assertEqual(
                candidate_reference_gaps(
                    claimed_ids=claimed,
                    durable_ids=set(claimed),
                    selected_candidate_id=claimed[0] if claimed else None,
                    runner_up_candidate_id=claimed[1] if len(claimed) > 1 else None,
                ),
                [],
                claimed,
            )

    def test_absent_selection_and_runner_up_are_valid(self) -> None:
        self.assertEqual(
            candidate_reference_gaps(
                claimed_ids=["A"], durable_ids={"A"},
                selected_candidate_id="A", runner_up_candidate_id=None,
            ),
            [],
        )
        self.assertEqual(
            candidate_reference_gaps(
                claimed_ids=[], durable_ids=set(),
                selected_candidate_id=None, runner_up_candidate_id=None,
            ),
            [],
        )

    def test_a_vanished_single_card_is_a_gap_not_an_empty_claim(self) -> None:
        # The one-candidate lifecycle this atom enables must not become
        # provable by losing its only durable card.
        self.assertEqual(
            candidate_reference_gaps(
                claimed_ids=["A"], durable_ids=set(),
                selected_candidate_id="A", runner_up_candidate_id=None,
            ),
            ["CANDIDATE:A", "SELECTED:A"],
        )

    def test_named_but_unresolvable_references_fail_closed(self) -> None:
        cases = {
            "CANDIDATE:B": dict(claimed_ids=["A", "B"], durable_ids={"A"}, selected_candidate_id="A", runner_up_candidate_id=None),
            "SELECTED:Z": dict(claimed_ids=["A"], durable_ids={"A"}, selected_candidate_id="Z", runner_up_candidate_id=None),
            "RUNNER_UP:Y": dict(claimed_ids=["A"], durable_ids={"A"}, selected_candidate_id="A", runner_up_candidate_id="Y"),
        }
        for expected, kwargs in cases.items():
            gaps = candidate_reference_gaps(**kwargs)
            self.assertIn(expected, gaps, expected)


class OrdinaryTerminalFamilyTests(unittest.TestCase):
    def test_kill_mechanism_is_in_the_canonical_scientific_negative_family(self) -> None:
        self.assertIn("KILL_MECHANISM", KNOWN_SCIENTIFIC_NEGATIVES)
        self.assertIn("NO_WORTHY_HYPOTHESIS", KNOWN_SCIENTIFIC_NEGATIVES)
        self.assertIn("KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED", KNOWN_SCIENTIFIC_NEGATIVES)


class ColdLifecycleVerticalTests(unittest.TestCase):
    def test_a1_one_candidate_kill_is_found_cold(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            saved = _Saved(Path(raw), "COLD_KILL")
            frozen = saved.freeze()
            done = saved.finalize(frozen, "KILL_MECHANISM")
            self.assertEqual(done.get("session_state"), "SYNTHESIS_COMPLETE", done)
            self.assertEqual(done.get("critic_terminal"), "KILL_MECHANISM", done)
            # A7 baseline: the committed lifecycle is complete; cold reads add nothing.
            mains_before = _mains(saved.data_root, saved.journal)
            cards_before = _candidate_records(saved.data_root)

            shown = saved.cold_show(str(frozen["session_id"]))
            self.assertEqual(shown["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(shown["critic_terminal"], "KILL_MECHANISM")

            code, run = saved.cold_run()
            self.assertEqual(code, 0, run)
            self.assertNotEqual(run.get("owner_class"), "OBSERVABILITY_BLOCKED", run)
            self.assertNotIn(
                "SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING",
                run.get("blocking_reason_codes") or [],
            )
            stage_reasons = {str(s.get("reason_code") or "") for s in (run.get("stages") or [])}
            self.assertNotIn("SAVED_DRAFT_PRESENT", stage_reasons, run)
            stage_sessions = {str(s.get("session_id") or "") for s in (run.get("stages") or [])}
            self.assertIn(str(frozen["session_id"]), stage_sessions, run)

            self.assertEqual(run.get("owner_final"), "SEARCH_EXHAUSTED_CURRENT_EVIDENCE", run)

            code, proof, stderr = saved.cold_prove(str(frozen["session_id"]))
            self.assertEqual(code, 0, stderr)
            self.assertEqual(proof.get("proof_status"), "PROVEN", proof)
            self.assertEqual(proof.get("critic_terminal"), "KILL_MECHANISM", proof)
            self.assertTrue(proof.get("candidates_retrievable"), proof)
            self.assertEqual(proof.get("provider_calls_actual"), 0)
            self.assertTrue(proof.get("git_composite_unchanged"))

            self.assertEqual(_mains(saved.data_root, saved.journal), mains_before)
            self.assertEqual(_candidate_records(saved.data_root), cards_before)

    def test_a2_one_candidate_pass_proves_cold(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            saved = _Saved(Path(raw), "COLD_PASS")
            frozen = saved.freeze()
            saved.finalize(frozen, "PASS_TO_CLASSIFICATION")
            done = saved.classify(frozen)
            self.assertEqual(done.get("session_state"), "SYNTHESIS_COMPLETE", done)
            mains_before = _mains(saved.data_root, saved.journal)
            cards_before = _candidate_records(saved.data_root)

            code, run = saved.cold_run()
            self.assertEqual(code, 0, run)
            self.assertEqual(run.get("owner_final"), "OWNER_CANDIDATE", run)

            code, proof, stderr = saved.cold_prove(str(frozen["session_id"]))
            self.assertEqual(code, 0, stderr)
            self.assertEqual(proof.get("proof_status"), "PROVEN", proof)
            self.assertTrue(proof.get("candidates_retrievable"), proof)
            self.assertTrue(proof.get("artifacts_retrievable"), proof)
            self.assertEqual(proof.get("provider_calls_actual"), 0)
            self.assertTrue(proof.get("git_composite_unchanged"))
            self.assertEqual(_mains(saved.data_root, saved.journal), mains_before)
            self.assertEqual(_candidate_records(saved.data_root), cards_before)

            # A6: identities are stable across the fresh process.
            shown = saved.cold_show(str(frozen["session_id"]))
            for key in (
                "session_id",
                "selected_candidate_id",
                "selected_definition_sha256",
                "critic_input_packet_sha256",
                "critic_result_sha256",
                "critic_terminal",
            ):
                self.assertEqual(shown.get(key), proof.get(key), key)
            self.assertEqual(shown["selected_candidate_id"], frozen["selected_candidate_id"])

    def test_a5_broken_candidate_references_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            saved = _Saved(Path(raw), "COLD_NEGATIVE")
            frozen = saved.freeze()
            saved.finalize(frozen, "PASS_TO_CLASSIFICATION")
            saved.classify(frozen)
            store = ResearchStore(saved.data_root, create_if_missing=False)
            bundle = load_session_bundle(store, str(frozen["session_id"]))
            assert bundle is not None
            _verify_store_reference_resolution(store, bundle)
            real = str(frozen["selected_candidate_id"])
            broken = {
                "listed": {**bundle, "candidate_ids": [real, "HFIC-CAND-000000000000"]},
                "selected": {**bundle, "selected_candidate_id": "HFIC-CAND-000000000000"},
                "runner_up": {**bundle, "runner_up_candidate_id": "HFIC-CAND-000000000000"},
            }
            broken["vanished_card"] = {**bundle, "candidates": []}
            for name, candidate_bundle in broken.items():
                with self.subTest(reference=name):
                    if name == "vanished_card":
                        # The store still holds the card, so the store gate
                        # passes; the proof gate is what must refuse here.
                        self.assertTrue(_bundle_candidate_reference_gaps(candidate_bundle))
                        continue
                    with self.assertRaises(HficSessionError) as refused:
                        _verify_store_reference_resolution(store, candidate_bundle)
                    self.assertEqual(str(refused.exception), "CANDIDATE_REFERENCE_UNRESOLVED")


class CardlessStoreIsReadableButUnprovableTests(unittest.TestCase):
    """The one behaviour this delta newly permits, driven through production entries."""

    def test_a_store_without_candidate_cards_loads_shows_false_and_refuses_to_prove(self) -> None:
        from solana_alpha_lab.factory.hfic_session import prove_runtime, show_session
        from tests.test_forge_representation_ladder_v1 import (
            _control_preflight,
            _write_lineage,
            finalize_kill_complete,
            valid_draft,
        )
        from tests.test_hfic_session import critic_result_from_packet_only

        with tempfile.TemporaryDirectory() as raw:
            data_root = Path(raw)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            frozen = freeze_draft(
                valid_draft(),
                preflight_receipt=_control_preflight(data_root, store),
                repo_root=ROOT,
            )
            done = finalize_kill_complete(
                frozen,
                critic_result_from_packet_only(frozen["critic_input_packet"], "KILL_MECHANISM"),
                store,
                repo_root=ROOT,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            session_id = str(frozen["session_id"])

            # This route records the claim but persists no candidate card.
            bundle = load_session_bundle(store, session_id)
            assert bundle is not None
            self.assertEqual(bundle.get("candidates"), [])
            self.assertTrue(bundle.get("candidate_ids"))
            self.assertTrue(bundle.get("selected_candidate_id"))

            # Readable: the store gate tolerates a store that never persisted cards.
            shown = show_session(store, session_id, repo_root=ROOT)
            self.assertEqual(shown["session_state"], "SYNTHESIS_COMPLETE")
            self.assertFalse(shown["candidates_retrievable"], shown)

            # Not provable: the proof gate keeps no such tolerance.
            with self.assertRaises(HficSessionError) as refused:
                prove_runtime(store, session_id, repo_root=ROOT)
            self.assertEqual(str(refused.exception), "SESSION_ARTIFACT_MISSING")


class ZeroAndHistoricalPortfolioTests(unittest.TestCase):
    """A3 and A4: zero and 4-6 candidate portfolios keep their meaning."""

    def test_a3_zero_candidates_are_not_missing_artifacts(self) -> None:
        # A no-worthy session claims no candidate and selects none, so it has
        # no unresolved reference. The retired rule called this "missing"
        # only because 0 < 4.
        no_worthy = {
            "session_id": "HFIC-SESS-NOWORTHY",
            "candidates": [],
            "candidate_ids": [],
            "selected_candidate_id": None,
            "runner_up_candidate_id": None,
        }
        self.assertEqual(_bundle_candidate_reference_gaps(no_worthy), [])
        # A no-worthy shape that still names a selection is not the same thing.
        self.assertTrue(
            _bundle_candidate_reference_gaps({**no_worthy, "selected_candidate_id": "HFIC-CAND-000000000000"})
        )

    def test_a4_historical_four_candidate_portfolio_still_proves(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            saved = _Saved(Path(raw), "COLD_HISTORICAL", candidate_count=4)
            self.assertEqual(len(saved.cards), 4)
            frozen = saved.freeze()
            saved.finalize(frozen, "PASS_TO_CLASSIFICATION")
            saved.classify(frozen)
            store = ResearchStore(saved.data_root, create_if_missing=False)
            bundle = load_session_bundle(store, str(frozen["session_id"]))
            assert bundle is not None
            self.assertGreaterEqual(len(bundle.get("candidate_ids") or []), 4)
            code, proof, stderr = saved.cold_prove(str(frozen["session_id"]))
            self.assertEqual(code, 0, stderr)
            self.assertEqual(proof.get("proof_status"), "PROVEN", proof)
            self.assertTrue(proof.get("candidates_retrievable"), proof)
            shown = saved.cold_show(str(frozen["session_id"]))
            self.assertEqual(shown["selected_candidate_id"], frozen["selected_candidate_id"])


class DurableClosedPairTests(unittest.TestCase):
    """The adjacent NOT_PROVEN pair: one unmocked CLI replay/new-spec pair on a closed slot."""

    def test_closed_slot_replays_the_same_spec_and_refuses_a_distinct_one(self) -> None:
        from tests.test_hfic_cli import seed_minimal_market_basis
        from tests.test_hfic_ordinary_operation_v1 import (
            _cli,
            _compound_spec,
            _simple_spec,
            _write_partition,
        )
        from tests.test_hfic_ordinary_operation_v1 import _operation as _ordinary_operation

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data_root = root / "rdp"
            seed_minimal_market_basis(data_root)
            focus = "CLOSED_PAIR_COLD_LIFECYCLE"
            preflight = _cli(
                data_root, "--data-root", str(data_root), "preflight",
                "--owner-focus", focus, "--format", "json",
            )
            self.assertEqual(preflight.get("_exit"), 0, preflight)
            journal = str(preflight["search_key_sha256"])
            market = str(preflight["market_evidence_epoch_sha256"])
            census, observations, binding = _write_partition(root)
            simple = _simple_spec()
            distinct = _compound_spec()
            paths = {}
            for name, body in (("simple", simple), ("distinct", distinct)):
                path = root / f"{name}.json"
                path.write_text(json.dumps(body), encoding="utf-8")
                paths[name] = path
            scope_path = root / "scope.json"
            scope_path.write_text(
                json.dumps(
                    {
                        "population": "BASE_X",
                        "decision_timestamp": "Y3600",
                        "target": "PRICE_RELATIVE_PROXY:Y3600:Y7200:FIELD-USD-PRICE-001",
                        "estimand": "price_relative_proxy",
                        "explanatory_condition": "retention",
                        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                    }
                ),
                encoding="utf-8",
            )

            def _op(spec: dict, name: str, cap: int) -> Path:
                body = _ordinary_operation(spec, completion="LIMITED_RESULT", cap_main=cap)
                body["owner_focus"] = focus
                body["journal_scope"] = journal
                body["market_evidence_epoch_sha256"] = market
                path = root / f"{name}.op.json"
                path.write_text(json.dumps(body), encoding="utf-8")
                return path

            def _execute(spec_name: str, op_path: Path) -> dict:
                return _cli(
                    data_root,
                    "discovery-execute",
                    "--store", str(data_root),
                    "--census", str(census),
                    "--observations", str(observations),
                    "--binding", str(binding),
                    "--spec", str(paths[spec_name]),
                    "--candidate-scope", str(scope_path),
                    "--journal-scope", journal,
                    "--operation", str(op_path),
                    "--format", "json",
                )

            simple_op = _op(simple, "simple", 1)
            first = _execute("simple", simple_op)
            self.assertEqual(first.get("_exit"), 0, first)

            # Close the slot through the production no-worthy freeze route.
            closed = _cli(
                data_root, "--data-root", str(data_root), "preflight",
                "--owner-focus", focus, "--format", "json",
            )
            self.assertEqual(closed.get("_exit"), 0, closed)
            from tests.test_hfic_cli import bind_draft as _bind

            source = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json").read_text(encoding="utf-8")
            )
            evidence = {key: value for key, value in first.items() if not str(key).startswith("_")}
            evidence["tier_decision"] = "COMPOUND_INAPPLICABLE"
            source["grounded_evidence"] = evidence
            source["owner_focus"] = focus
            receipt = {key: value for key, value in closed.items() if not str(key).startswith("_")}
            draft_path = root / "no_worthy_draft.json"
            receipt_path = root / "no_worthy_receipt.json"
            draft_path.write_text(json.dumps(_bind(source, receipt)), encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            frozen = _cli(
                data_root, "--data-root", str(data_root), "freeze",
                "--draft", str(draft_path), "--preflight-receipt", str(receipt_path),
                "--format", "json",
            )
            self.assertEqual(frozen.get("_exit"), 0, frozen)
            self.assertEqual(frozen.get("critic_terminal"), "NO_WORTHY_HYPOTHESIS", frozen)

            # Exact replay of the closed question stays readable, loads no values.
            replay = _execute("simple", simple_op)
            self.assertEqual(replay.get("_exit"), 0, replay)
            self.assertFalse(replay.get("values_loaded"), replay)
            self.assertFalse(replay.get("writes"), replay)
            self.assertEqual(replay.get("result_refs"), first.get("result_refs"), replay)

            # A distinct new question on the closed slot is refused before values.
            distinct_op = _op(distinct, "distinct", 1)
            refused = _execute("distinct", distinct_op)
            self.assertEqual(refused.get("_exit"), 2, refused)
            self.assertEqual(refused.get("reason_code"), "ORDINARY_OPERATION_SLOT_CLOSED", refused)
            self.assertFalse(refused.get("values_loaded"), refused)


if __name__ == "__main__":
    unittest.main()
