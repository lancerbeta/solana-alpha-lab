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

def _preflight_receipt() -> dict[str, object]:
    return {
        "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "owner_focus": "AUTO",
        "live_git_head": "b" * 40,
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
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(
                valid_draft(),
                preflight_receipt=_preflight_receipt(),
                store=store,
                repo_root=ROOT,
            )
            kinds = [
                getattr(record.record_kind, "value", record.record_kind)
                for record in store.iter_committed_records()
            ]
            self.assertIn(RecordKind.RESEARCH_CYCLE.value, kinds)
            self.assertGreaterEqual(kinds.count(RecordKind.HYPOTHESIS_VERSION.value), 4)
            self.assertIn(RecordKind.RESEARCH_ARTIFACT.value, kinds)
            rendered = json.dumps(frozen, sort_keys=True)
            self.assertNotIn(str(Path(tmp)), rendered)
            self.assertTrue(frozen["session_id"].startswith("HFIC-SESS-"))

    def test_finalize_maps_kill_to_reject_and_never_promotes(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(
                valid_draft(),
                preflight_receipt=_preflight_receipt(),
                store=store,
                repo_root=ROOT,
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
            self.assertEqual(str(raised.exception), "PREFLIGHT_RECEIPT_REQUIRED")

    def test_same_epoch_focus_does_not_create_second_session(self) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            first = freeze_draft(
                valid_draft(),
                preflight_receipt=_preflight_receipt(),
                store=store,
                repo_root=ROOT,
            )
            other = valid_draft()
            other["candidates"][0]["claim"] = "A different causal claim."
            second = freeze_draft(
                other,
                preflight_receipt=_preflight_receipt(),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(first["session_id"], second["session_id"])
            self.assertEqual(first["critic_input_packet_sha256"], second["critic_input_packet_sha256"])

    def test_finalize_without_packet_hash_is_rejected(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            frozen = freeze_draft(
                valid_draft(),
                preflight_receipt=_preflight_receipt(),
                store=store,
                repo_root=ROOT,
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
