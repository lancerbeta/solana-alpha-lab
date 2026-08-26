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

from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    backfill_legacy,
    evidence_epoch_sha256,
    freeze_draft,
    map_critic_terminal_to_decision,
    related_prior_matches,
    search_key_sha256,
)

_CACHED_GIT = None


def _preflight_receipt() -> dict[str, object]:
    global _CACHED_GIT
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot

    if _CACHED_GIT is None:
        _CACHED_GIT = repository_git_snapshot(ROOT)
    git = _CACHED_GIT
    return {
        "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "owner_focus": "AUTO",
        "live_git_head": git.head_sha.lower(),
        "git_composite_sha256": git.composite_sha256,
    }


def _critic_result(frozen: dict[str, object], terminal: str = "KILL_PREPARATORY_LOOP") -> dict[str, object]:
    return {
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
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "non_claims": ["NO_ALPHA"],
    }


C3_C4_FIXTURE = ROOT / "tests/fixtures/hypothesis_forge/draft_c3_c4_mismatch_v1.json"


def _card(ordinal: int, family: str, claim: str) -> dict[str, object]:
    return {
        "display_ordinal": ordinal,
        "label": f"label-{ordinal}",
        "claim": claim,
        "mechanism": f"mechanism-{family}",
        "actor_counterparty": "cohort versus later buyers",
        "population": "ICP-EARLY-PUMPFUN-V1 age 300-899s",
        "decision_timestamp": "frozen T+5",
        "primary_x_family": family,
        "primary_y": "MARKET_EXECUTION_UNAVAILABLE",
        "horizon_notional": "H900 / 0.01 SOL quote-only reverse sell",
        "negative_control": "service-signer-only links",
        "cheapest_falsifier": f"falsifier-{family}",
    }


def valid_draft() -> dict[str, object]:
    cards = [
        _card(1, "CORROBORATED_EARLY_COHORT_SUPPLY_SHARE", "Claim one."),
        _card(2, "RAW_TOP_HOLDERS_PERCENTAGE", "Claim two."),
        _card(3, "ROUTE_FRAGMENTATION", "Claim three."),
        _card(4, "CREATOR_LINKED_OUTFLOW", "Claim four."),
    ]
    return {
        "packet_schema": "smial.hypothesis-forge-draft",
        "packet_version": "1.1",
        "generator_prompt_version": "HFIC-V1.1",
        "owner_focus": "AUTO",
        "preflight_receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
        "preflight_receipt_sha256": "aa" * 32,
        "research_memory_as_of": "2026-08-25T00:00:00Z",
        "truth_roots_used": ["catalog/catalog_manifest.yaml"],
        "prior_work_receipts": ["QUERY-HFIC-SESSION-BY-SEARCH-KEY-001"],
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "candidates": cards,
        "selected_candidate_ref": "label-1",
        "runner_up_candidate_ref": "label-3",
        "strongest_rejected_alternative": "label-2",
        "pareto_factors": ["mechanistic orthogonality"],
        "non_claims": ["NO_ALPHA"],
    }


class HficCrossReferenceTests(unittest.TestCase):
    def test_c3_c4_free_text_mismatch_fails_before_critic(self) -> None:
        draft = json.loads(C3_C4_FIXTURE.read_text(encoding="utf-8"))
        with self.assertRaises(HficSessionError) as raised:
            freeze_draft(
                draft,
                preflight_receipt={"receipt_id": "HFIC-PREFLIGHT-FIXTURE-001"},
            )
        self.assertEqual(str(raised.exception), "CROSS_REFERENCE_MISMATCH")

    def test_selected_equals_runner_up_is_rejected(self) -> None:
        draft = valid_draft()
        draft["selected_candidate_ref"] = draft["runner_up_candidate_ref"]
        with self.assertRaises(HficSessionError) as raised:
            freeze_draft(
                draft,
                preflight_receipt={"receipt_id": "HFIC-PREFLIGHT-FIXTURE-001"},
            )
        self.assertEqual(str(raised.exception), "SELECTED_EQUALS_RUNNER_UP")

    def test_malformed_draft_is_rejected(self) -> None:
        draft = valid_draft()
        draft.pop("candidates")
        with self.assertRaises(HficSessionError) as raised:
            freeze_draft(draft, preflight_receipt=_preflight_receipt(), repo_root=ROOT)
        self.assertEqual(str(raised.exception), "HFIC_PROTOCOL_INVALID")


class HficFreezeFinalizeTests(unittest.TestCase):
    def test_freeze_assigns_stable_ids_and_rewrites_refs(self) -> None:
        frozen = freeze_draft(
            valid_draft(),
            preflight_receipt={"receipt_id": "HFIC-PREFLIGHT-FIXTURE-001"},
        )
        self.assertEqual(frozen["session_state"], "FROZEN_AWAITING_CRITIC")
        selected = frozen["selected_candidate_id"]
        runner_up = frozen["runner_up_candidate_id"]
        self.assertTrue(selected.startswith("HFIC-CAND-"))
        self.assertTrue(runner_up.startswith("HFIC-CAND-"))
        self.assertNotEqual(selected, runner_up)
        packet = frozen["critic_input_packet"]
        self.assertEqual(packet["selected_candidate"]["candidate_id"], selected)
        self.assertEqual(packet["generator_prompt_version"], "HFIC-V1.1")
        self.assertEqual(packet["strongest_rejected_alternative"], frozen["rejected_alternative_id"])
        self.assertEqual(packet["truth_roots_used"], ["catalog/catalog_manifest.yaml"])
        self.assertFalse(packet["research_memory_as_of"].startswith("1970-01-01"))

    def test_selected_missing_is_rejected(self) -> None:
        draft = valid_draft()
        draft["selected_candidate_ref"] = "missing-label"
        with self.assertRaises(HficSessionError) as raised:
            freeze_draft(draft, preflight_receipt={"receipt_id": "HFIC-PREFLIGHT-FIXTURE-001"})
        self.assertEqual(str(raised.exception), "SELECTED_CANDIDATE_MISSING")

    def test_pass_terminals_map_to_pause_never_promote(self) -> None:
        self.assertEqual(
            map_critic_terminal_to_decision("KILL_PREPARATORY_LOOP"),
            ("REJECT", "KILL_PREPARATORY_LOOP"),
        )
        self.assertEqual(
            map_critic_terminal_to_decision("NO_WORTHY_HYPOTHESIS"),
            ("REJECT", "NO_WORTHY_HYPOTHESIS"),
        )
        self.assertEqual(
            map_critic_terminal_to_decision("REVISE_ONCE"),
            ("REVISE", "REVISE_ONCE"),
        )
        for terminal in (
            "PASS_FAST_LANE_READY",
            "PASS_CHANGE_LANE_REQUIRED",
            "PASS_DATA_OPTION_REQUIRED",
        ):
            kind, reason = map_critic_terminal_to_decision(terminal)
            self.assertEqual(kind, "PAUSE")
            self.assertEqual(reason, terminal)
        with self.assertRaises(HficSessionError):
            map_critic_terminal_to_decision("PROMOTE")
        with self.assertRaises(HficSessionError):
            map_critic_terminal_to_decision("KILL_MADE_UP")

    def test_legacy_partial_cannot_emit_fake_critic_receipt(self) -> None:
        packet = {
            "phase": "LEGACY_PARTIAL",
            "source": "OWNER_SUPPLIED_TRANSCRIPT",
            "backfilled": True,
            "missing_fields": ["critic_input_packet", "critic_result"],
            "candidates": valid_draft()["candidates"],
            "selected_label": "label-1",
            "selected_terminal": "KILL_PREPARATORY_LOOP",
            "legacy_aliases": {
                "label-3": ["HFIC-C3-PREDECISION-ROUTE-FRAGMENTATION-RECOVERY",
                            "HFIC-C4-PREDECISION-ROUTE-FRAGMENTATION-RECOVERY"],
            },
        }
        result = backfill_legacy(packet, persist=False)
        self.assertEqual(result["session_state"], "LEGACY_PARTIAL")
        self.assertTrue(result["backfilled"])
        self.assertIsNone(result.get("critic_result_sha256"))
        self.assertNotIn("critic_input_packet", result)

    def test_related_prior_is_overlap_not_title_equality(self) -> None:
        left = _card(1, "ROUTE_FRAGMENTATION", "Claim three.")
        right = _card(2, "ROUTE_FRAGMENTATION", "Slightly different claim.")
        right["mechanism"] = "mechanism-ROUTE_FRAGMENTATION"
        matches = related_prior_matches(left, [right])
        self.assertEqual(matches[0]["match_kind"], "RELATED_PRIOR")
        self.assertNotEqual(matches[0]["match_kind"], "EXACT")

    def test_evidence_epoch_excludes_session_writes_and_clock(self) -> None:
        material = {
            "catalog_root_hashes": ["aa" * 32],
            "dataset_manifest_ids": ["DATASET-MANIFEST-FAST-LANE-COMMISSIONING-001"],
            "prior_work_digest": "bb" * 32,
        }
        first = evidence_epoch_sha256(material)
        second = evidence_epoch_sha256(
            {
                **material,
                "created_at": "2026-08-26T18:00:00Z",
                "hfic_session_ids": ["HFIC-SESS-1"],
                "model": "unused",
            }
        )
        self.assertEqual(first, second)
        changed = evidence_epoch_sha256(
            {**material, "catalog_root_hashes": ["cc" * 32]}
        )
        self.assertNotEqual(first, changed)

    def test_same_search_key_is_stable(self) -> None:
        epoch = "ab" * 32
        first = search_key_sha256(epoch, "AUTO", "HFIC-V1.1")
        second = search_key_sha256(epoch, " auto ", "HFIC-V1.1")
        self.assertEqual(first, second)
        self.assertNotEqual(first, search_key_sha256(epoch, "insiders", "HFIC-V1.1"))

    def test_freeze_persists_cycle_and_all_candidates(self) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            with self.assertRaises(HficSessionError) as raised:
                freeze_draft(
                    valid_draft(),
                    preflight_receipt=_preflight_receipt(),
                    store=store,
                    repo_root=ROOT,
                )
            self.assertIn(
                str(raised.exception),
                {
                    "PREFLIGHT_ACTION_INVALID",
                    "PREFLIGHT_RECEIPT_HASH_MISMATCH",
                    "PREFLIGHT_PROMPT_VERSION_INVALID",
                    "COMMISSIONING_PROOF_REQUIRED",
                },
            )
            self.assertEqual(list(store.iter_committed_records()), [])

    def test_finalize_maps_kill_to_reject_and_never_promotes(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(
                valid_draft(),
                preflight_receipt=_preflight_receipt(),
            )
            receipt = finalize_session(
                frozen,
                _critic_result(frozen),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(receipt["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(receipt["critic_terminal"], "KILL_PREPARATORY_LOOP")
            kinds = [
                getattr(record.record_kind, "value", record.record_kind)
                for record in store.iter_committed_records()
            ]
            self.assertIn(RecordKind.DECISION_EVENT.value, kinds)
            self.assertNotIn("PROMOTE", json.dumps(receipt))
            self.assertTrue(
                any(
                    json.loads(record.payload_json).get("artifact_kind") == "SESSION_RECEIPT"
                    for record in store.iter_committed_records()
                    if getattr(record.record_kind, "value", record.record_kind)
                    == RecordKind.RESEARCH_ARTIFACT.value
                )
            )

    def test_persist_requires_preflight_search_key(self) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            with self.assertRaises(HficSessionError) as raised:
                freeze_draft(
                    valid_draft(),
                    preflight_receipt={"receipt_id": "HFIC-PREFLIGHT-FIXTURE-001"},
                    store=store,
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "PREFLIGHT_ACTION_INVALID")

    def test_same_epoch_focus_does_not_create_second_session(self) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            first = freeze_draft(
                valid_draft(),
                preflight_receipt=_preflight_receipt(),
            )
            other = valid_draft()
            other["candidates"][0]["claim"] = "A different causal claim."
            second = freeze_draft(
                other,
                preflight_receipt=_preflight_receipt(),
            )
            self.assertEqual(first["session_id"], second["session_id"])

    def test_finalize_without_packet_hash_is_rejected(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(
                valid_draft(),
                preflight_receipt=_preflight_receipt(),
            )
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(
                    frozen,
                    {
                        "session_id": frozen["session_id"],
                        "selected_candidate_id": frozen["selected_candidate_id"],
                        "critic_terminal": "KILL_PREPARATORY_LOOP",
                        "next": "STOP",
                    },
                    store=store,
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "CRITIC_PACKET_HASH_MISMATCH")

    def test_wrong_selected_definition_hash_is_rejected(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            critic = _critic_result(frozen)
            critic["selected_definition_sha256"] = "ab" * 32
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(frozen, critic, store=store, repo_root=ROOT)
            self.assertEqual(str(raised.exception), "CRITIC_DEFINITION_HASH_MISMATCH")

    def test_pass_to_classification_is_not_complete(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            finalize_session,
            load_session_bundle,
            prove_runtime,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            receipt = finalize_session(
                frozen,
                _critic_result(frozen, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(receipt["session_state"], "AWAITING_CLASSIFICATION")
            bundle = load_session_bundle(store, frozen["session_id"])
            self.assertEqual(bundle["session_state"], "AWAITING_CLASSIFICATION")
            with self.assertRaises(HficSessionError) as raised:
                prove_runtime(store, frozen["session_id"], repo_root=ROOT)
            self.assertEqual(str(raised.exception), "SESSION_RECEIPT_MISSING")

    def test_fake_classifier_on_pass_to_classification_is_rejected(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            critic = _critic_result(frozen, "PASS_TO_CLASSIFICATION")
            critic["classifier_receipt"] = {"lane": "FAST_LANE", "ok": True}
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(frozen, critic, store=store, repo_root=ROOT)
            self.assertIn(
                str(raised.exception),
                {"HFIC_PROTOCOL_INVALID", "CLASSIFIER_RECEIPT_INVALID"},
            )

    def test_pass_to_classification_then_live_classifier_completes(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            apply_classification,
            finalize_session,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_fast_lane_classifier import submission

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            finalize_session(
                frozen,
                _critic_result(frozen, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            packet = submission()
            packet["hypothesis_definition_sha256"] = frozen["selected_definition_sha256"]
            done = apply_classification(
                frozen,
                packet,
                store=store,
                repo_root=ROOT,
                data_root=Path(tmp),
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertIn(
                done["critic_terminal"],
                {
                    "PASS_FAST_LANE_READY",
                    "PASS_CHANGE_LANE_REQUIRED",
                    "PASS_DATA_OPTION_REQUIRED",
                    "OWNER_DECISION_REQUIRED",
                    "KILL_UNBOUND_EVIDENCE",
                },
            )
            self.assertNotEqual(done["critic_terminal"], "PASS_TO_CLASSIFICATION")
            fence = done.get("no_git_fence_receipt") or (
                done.get("session_receipt") or {}
            ).get("no_git_fence_receipt")
            self.assertTrue(fence["git_composite_unchanged"])

    def test_fake_classifier_receipt_is_rejected(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            critic = _critic_result(frozen, "PASS_FAST_LANE_READY")
            critic["classifier_receipt"] = {"lane": "FAST_LANE", "ok": True}
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(frozen, critic, store=store, repo_root=ROOT)
            self.assertEqual(str(raised.exception), "HFIC_PROTOCOL_INVALID")

    def test_crash_before_session_receipt_is_resumable(self) -> None:
        import duckdb

        from solana_alpha_lab.factory.hfic_session import load_session_bundle, prove_runtime
        from solana_alpha_lab.factory.research_store import (
            RESEARCH_PROJECTION_LOCATION,
            RecordKind,
            ResearchEvent,
            ResearchStore,
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            git = _CACHED_GIT
            assert git is not None
            now = __import__("datetime").datetime(1970, 1, 1, tzinfo=__import__("datetime").UTC)
            payload = {
                "research_cycle_id": f"{frozen['session_id']}-COMPLETE",
                "session_id": frozen["session_id"],
                "phase": "SYNTHESIS_COMPLETE",
                "hfic_protocol": "HFIC-V1.1",
                "prompt_version": "HFIC-V1.1",
            }
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            store.append(
                [
                    ResearchEvent(
                        record_id=f"HFIC-CYCLE-{frozen['session_id']}-COMPLETE",
                        record_kind=RecordKind.RESEARCH_CYCLE,
                        entity_id=frozen["session_id"],
                        hypothesis_version_id=None,
                        run_id=None,
                        transaction_id="RESEARCH-TXN-HFICCRASH-001",
                        effective_at=now,
                        first_reliable_available_at=now,
                        supersedes_record_id=None,
                        payload_json=encoded,
                        payload_sha256=__import__("hashlib").sha256(encoded.encode()).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                        producer_git_sha=git.head_sha,
                        created_at=now,
                    )
                ],
                transaction_id="RESEARCH-TXN-HFICCRASH-001",
            )
            bundle = load_session_bundle(store, frozen["session_id"])
            self.assertNotEqual(bundle["session_state"], "SYNTHESIS_COMPLETE")
            from solana_alpha_lab.factory.hfic_session import PENDING_STATES, list_hfic_sessions

            listed = list_hfic_sessions(store)
            self.assertEqual(listed[0]["session_state"], "FROZEN_AWAITING_CRITIC")
            self.assertEqual(bundle["session_state"], listed[0]["session_state"])
            self.assertIn(listed[0]["session_state"], PENDING_STATES)
            with self.assertRaises(HficSessionError) as raised:
                prove_runtime(store, frozen["session_id"], repo_root=ROOT)
            self.assertEqual(str(raised.exception), "SESSION_RECEIPT_MISSING")
            store.rebuild_projection()
            projection = Path(tmp) / RESEARCH_PROJECTION_LOCATION
            connection = duckdb.connect(str(projection), read_only=True)
            try:
                row = connection.execute(
                    """
                    SELECT session_state
                    FROM hfic_sessions
                    WHERE session_id = ?
                    """,
                    [frozen["session_id"]],
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(row[0], "FROZEN_AWAITING_CRITIC")

    def test_revise_once_is_intermediate_and_second_revise_is_blocked(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            critic = _critic_result(frozen, "REVISE_ONCE")
            critic["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            first = finalize_session(frozen, critic, store=store, repo_root=ROOT)
            self.assertEqual(first["session_state"], "REVISION_REQUIRED")
            frozen = {**frozen, "revision_count": 1}
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(frozen, critic, store=store, repo_root=ROOT)
            self.assertEqual(str(raised.exception), "REVISION_BUDGET_EXHAUSTED")

    def test_revise_once_then_second_critic_can_complete(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            apply_revision,
            finalize_session,
            load_session_bundle,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            critic = _critic_result(frozen, "REVISE_ONCE")
            critic["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            finalize_session(frozen, critic, store=store, repo_root=ROOT)
            revised = apply_revision(
                load_session_bundle(store, frozen["session_id"]),
                valid_draft(),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(revised["session_state"], "REVISED_AWAITING_CRITIC")
            self.assertEqual(revised["revision_count"], 1)
            kill = _critic_result(revised, "KILL_PREPARATORY_LOOP")
            done = finalize_session(revised, kill, store=store, repo_root=ROOT)
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(done["critic_terminal"], "KILL_PREPARATORY_LOOP")

    def test_revise_once_can_repair_selected_definition(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            apply_revision,
            finalize_session,
            load_session_bundle,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            critic = _critic_result(frozen, "REVISE_ONCE")
            critic["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            finalize_session(frozen, critic, store=store, repo_root=ROOT)
            draft = valid_draft()
            draft["candidates"][0]["claim"] = "Claim one, revised wording."
            revised = apply_revision(
                load_session_bundle(store, frozen["session_id"]),
                draft,
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(revised["session_state"], "REVISED_AWAITING_CRITIC")
            self.assertNotEqual(
                revised["selected_definition_sha256"],
                frozen["selected_definition_sha256"],
            )
            self.assertEqual(
                revised.get("selected_display_ordinal"),
                frozen.get("selected_display_ordinal"),
            )
            kill = _critic_result(revised, "KILL_PREPARATORY_LOOP")
            done = finalize_session(revised, kill, store=store, repo_root=ROOT)
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")

    def test_revise_once_rejects_mechanism_change(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            apply_revision,
            finalize_session,
            load_session_bundle,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
            critic = _critic_result(frozen, "REVISE_ONCE")
            critic["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            finalize_session(frozen, critic, store=store, repo_root=ROOT)
            draft = valid_draft()
            draft["candidates"][0]["mechanism"] = "a different mechanism entirely"
            with self.assertRaises(HficSessionError) as raised:
                apply_revision(
                    load_session_bundle(store, frozen["session_id"]),
                    draft,
                    store=store,
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "REVISION_MECHANISM_CHANGED")

    def test_finalize_rejects_mismatched_git_composite(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            receipt = _preflight_receipt()
            receipt["git_composite_sha256"] = "ab" * 32
            frozen = freeze_draft(valid_draft(), preflight_receipt=receipt)
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(
                    frozen,
                    _critic_result(frozen, "KILL_PREPARATORY_LOOP"),
                    store=store,
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "GIT_COMPOSITE_CHANGED")


def _persist_frozen_portfolio(
    store: object,
    frozen: dict[str, object],
    draft: dict[str, object],
) -> None:
    from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids
    from solana_alpha_lab.factory.hfic_session import persist_frozen_session

    identities = assign_portfolio_ids(draft["candidates"])
    persist_frozen_session(
        store,
        frozen,
        repo_root=ROOT,
        identities=identities,
        draft=draft,
    )
    store.rebuild_projection()


class HficHashBoundAndRevisionClosureTests(unittest.TestCase):
    def test_pass_to_classification_reload_prove_runtime_is_identical(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            apply_classification,
            finalize_session,
            load_session_bundle,
            prove_runtime,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_fast_lane_classifier import submission

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = valid_draft()
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt())
            _persist_frozen_portfolio(store, frozen, draft)
            finalize_session(
                frozen,
                _critic_result(frozen, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            packet = submission()
            packet["hypothesis_definition_sha256"] = frozen["selected_definition_sha256"]
            apply_classification(
                frozen,
                packet,
                store=store,
                repo_root=ROOT,
                data_root=Path(tmp),
            )
            reloaded = load_session_bundle(store, str(frozen["session_id"]))
            self.assertEqual(reloaded["session_state"], "SYNTHESIS_COMPLETE")
            first = prove_runtime(store, str(frozen["session_id"]), repo_root=ROOT)
            second = prove_runtime(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(first, second)

    def test_revise_once_reload_prove_runtime_is_identical(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            apply_revision,
            finalize_session,
            load_session_bundle,
            prove_runtime,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = valid_draft()
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt())
            _persist_frozen_portfolio(store, frozen, draft)
            critic = _critic_result(frozen, "REVISE_ONCE")
            critic["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            finalize_session(frozen, critic, store=store, repo_root=ROOT)
            revised_draft = valid_draft()
            revised_draft["candidates"][0]["claim"] = "Claim one, revised wording."
            revised = apply_revision(
                load_session_bundle(store, str(frozen["session_id"])),
                revised_draft,
                store=store,
                repo_root=ROOT,
            )
            done = finalize_session(
                revised,
                _critic_result(revised, "KILL_PREPARATORY_LOOP"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            reloaded = load_session_bundle(store, str(frozen["session_id"]))
            self.assertEqual(reloaded["session_state"], "SYNTHESIS_COMPLETE")
            first = prove_runtime(store, str(frozen["session_id"]), repo_root=ROOT)
            second = prove_runtime(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(first, second)

    def test_after_revision_all_candidate_and_decision_ids_resolve(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            apply_revision,
            finalize_session,
            load_session_bundle,
            prove_runtime,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = valid_draft()
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt())
            _persist_frozen_portfolio(store, frozen, draft)
            critic = _critic_result(frozen, "REVISE_ONCE")
            critic["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            finalize_session(frozen, critic, store=store, repo_root=ROOT)
            revised_draft = valid_draft()
            revised_draft["candidates"][0]["claim"] = "Claim one, revised wording."
            revised = apply_revision(
                load_session_bundle(store, str(frozen["session_id"])),
                revised_draft,
                store=store,
                repo_root=ROOT,
            )
            finalize_session(
                revised,
                _critic_result(revised, "KILL_PREPARATORY_LOOP"),
                store=store,
                repo_root=ROOT,
            )
            bundle = load_session_bundle(store, str(frozen["session_id"]))
            prove_runtime(store, str(frozen["session_id"]), repo_root=ROOT)
            known_hypothesis = {
                str(record.entity_id)
                for record in store.iter_committed_records()
                if getattr(record.record_kind, "value", record.record_kind)
                == "HYPOTHESIS_VERSION"
            }
            known_decisions = {
                str(record.entity_id)
                for record in store.iter_committed_records()
                if getattr(record.record_kind, "value", record.record_kind)
                == "DECISION_EVENT"
            }
            for candidate_id in bundle["candidate_ids"]:
                self.assertIn(str(candidate_id), known_hypothesis)
            for decision_id in bundle["decision_event_ids"]:
                self.assertIn(str(decision_id), known_decisions)

    def test_revision_context_drift_is_denied(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            apply_revision,
            finalize_session,
            load_session_bundle,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = valid_draft()
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt())
            _persist_frozen_portfolio(store, frozen, draft)
            critic = _critic_result(frozen, "REVISE_ONCE")
            critic["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            finalize_session(frozen, critic, store=store, repo_root=ROOT)
            drift = valid_draft()
            drift["research_memory_as_of"] = "2026-08-26T00:00:00Z"
            with self.assertRaises(HficSessionError) as raised:
                apply_revision(
                    load_session_bundle(store, str(frozen["session_id"])),
                    drift,
                    store=store,
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "RESEARCH_MEMORY_AS_OF_MISMATCH")

    def test_draft_forge_context_binding_rejects_truth_roots_drift(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            HficSessionError,
            _validate_draft_forge_context_binding,
        )

        draft = valid_draft()
        bound = {
            "owner_focus": "AUTO",
            "evidence_epoch_sha256": "aa" * 32,
            "search_key_sha256": "cc" * 32,
            "research_memory_as_of": draft["research_memory_as_of"],
        }
        receipt = {
            "forge_context_packet": {
                "truth_roots_used": ["catalog/other.yaml"],
                "prior_work_receipts": draft["prior_work_receipts"],
                "research_memory_as_of": draft["research_memory_as_of"],
                "evidence_epoch_sha256": bound["evidence_epoch_sha256"],
                "search_key_sha256": bound["search_key_sha256"],
                "owner_focus": "AUTO",
            }
        }
        with self.assertRaises(HficSessionError) as raised:
            _validate_draft_forge_context_binding(draft, receipt, bound)
        self.assertEqual(str(raised.exception), "TRUTH_ROOTS_MISMATCH")

    def test_stale_intermediate_critic_result_is_not_selected(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session, load_session_bundle
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = valid_draft()
            frozen = freeze_draft(draft, preflight_receipt=_preflight_receipt())
            _persist_frozen_portfolio(store, frozen, draft)
            revise = _critic_result(frozen, "REVISE_ONCE")
            revise["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
            finalize_session(frozen, revise, store=store, repo_root=ROOT)
            revised_draft = valid_draft()
            revised_draft["candidates"][0]["claim"] = "Claim one, revised wording."
            from solana_alpha_lab.factory.hfic_session import apply_revision

            apply_revision(
                load_session_bundle(store, str(frozen["session_id"])),
                revised_draft,
                store=store,
                repo_root=ROOT,
            )
            bundle = load_session_bundle(store, str(frozen["session_id"]))
            self.assertEqual(bundle["session_state"], "REVISED_AWAITING_CRITIC")
            self.assertIsNone(bundle.get("critic_result"))
            self.assertNotEqual(
                str(bundle.get("critic_terminal") or ""),
                "REVISE_ONCE",
            )
