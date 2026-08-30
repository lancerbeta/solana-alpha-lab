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

from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    enumerate_closed_park_terminals,
    evidence_epoch_material,
    select_closed_family_ledger_for_packet,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    evidence_epoch_sha256,
    freeze_draft,
)
from solana_alpha_lab.factory.hfic_suppression_semantics import (  # noqa: E402
    AMBIGUOUS_REQUIRES_OWNER,
    LEGACY_MEASUREMENT_LIMITED,
    OWNER_PRIORITY_PARK,
    REBASE_RECORD_ID,
    SCIENTIFIC_CLOSE_VALID,
    SCOPE_LIMITED_CLOSE,
    candidate_matches_hard_close,
    classify_source_payload,
    dedupe_suppression_ledger,
    family_hard_close_terminals,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_hfic_cli import bind_draft, critic_result_from_packet_only, run_cli  # noqa: E402
from tests.test_hfic_epistemic_memory_semantics import (  # noqa: E402
    TAKER_FAMILY,
    TAKER_MANIFEST_ID,
    _append_hfic_untagged_candidate,
    _authoritative_taker_decision,
    _publish_labeled_dataset,
)

HAPPY = ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
H900_RULE = "HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_V1"
H900_TERMINAL = "REPLICATED_RELATION_NOT_ACTIONABLE_AS_TOP_QUARTILE_VETO"


def _park_payload() -> dict[str, object]:
    return {
        "priority_disposition": "PARKED_FROM_PRIORITY",
        "science_disposition": "RETAINED",
        "hypothesis_verdict": "NOT_REFUTED_NOT_SUPPORTED",
        "hypothesis_id": "HYP-RC002-H11-LIFECYCLE-CLOCK-V1",
        "owner_decision": "PARK_H11_FROM_PRIORITY",
    }


def _h900_legacy_payload() -> dict[str, object]:
    return {
        "rule_id": H900_RULE,
        "survived": False,
        "terminal": H900_TERMINAL,
    }


class LegacyScienceRebaseTests(unittest.TestCase):
    def test_t1_priority_park_is_not_scientific_hard_close(self) -> None:
        item = classify_source_payload(
            _park_payload(),
            terminal="PARK_H11_FROM_PRIORITY",
            source_receipt="docs/evidence/rc002_h11_park_from_priority/a1_h11_park_from_priority_acceptance_v1.json",
        )
        self.assertEqual(item["suppression_class"], OWNER_PRIORITY_PARK)
        self.assertFalse(item["reopen_forbidden"])
        self.assertTrue(item["visible_as_prior_work"])
        card = {
            "primary_x_family": "H11_FROM_PRIORITY",
            "claim": "H11 parked from priority remains scientifically retained.",
            "mechanism": "priority park is not a refutation",
        }
        self.assertIsNone(candidate_matches_hard_close(card, [item]))
        self.assertEqual(family_hard_close_terminals([item]), [])

    def test_t1_priority_parks_survive_consumer_packet_cap(self) -> None:
        hard = [
            classify_source_payload(
                {"scientific_terminal": f"CLOSE_SYNTHETIC_FAMILY_{index:02d}_FAMILY", "family_close": True},
                terminal=f"CLOSE_SYNTHETIC_FAMILY_{index:02d}_FAMILY",
                source_receipt=f"docs/evidence/synthetic/a1_family_{index:02d}.json",
            )
            for index in range(8)
        ]
        parks = [
            classify_source_payload(
                _park_payload(),
                terminal="PARK_H11_FROM_PRIORITY",
                source_receipt="docs/evidence/rc002_h11_park_from_priority/a1_h11_park_from_priority_acceptance_v1.json",
            ),
            classify_source_payload(
                {
                    "priority_disposition": "PARKED_FROM_PRIORITY",
                    "science_disposition": "RETAINED",
                    "hypothesis_verdict": "NOT_REFUTED_NOT_SUPPORTED",
                    "owner_decision": "PARK_H13_FROM_PRIORITY",
                },
                terminal="PARK_H13_FROM_PRIORITY",
                source_receipt="docs/evidence/rc001_h13_park_from_priority/a1_h13_park_from_priority_acceptance_v1.json",
            ),
        ]
        packet = select_closed_family_ledger_for_packet([*hard, *parks], limit=8)
        terminals = [item["terminal"] for item in packet]
        self.assertIn("PARK_H11_FROM_PRIORITY", terminals)
        self.assertIn("PARK_H13_FROM_PRIORITY", terminals)
        self.assertEqual(sum(1 for item in packet if item.get("reopen_forbidden") is True), 8)
        self.assertTrue(
            all(item.get("reopen_forbidden") is False for item in packet if item["terminal"].startswith("PARK_"))
        )

    def test_t2_typed_scientific_close_remains_reopen_forbidden(self) -> None:
        item = classify_source_payload(
            {
                "scientific_terminal": TAKER_FAMILY,
                "family_close": True,
                "schema": "smial.early-icp-first-hit-mix-falsifier.runtime-receipt",
                "outcome_consumed": True,
            },
            terminal=TAKER_FAMILY,
            source_receipt=f"datasets/manifests/{TAKER_MANIFEST_ID}.decision.json",
        )
        self.assertEqual(item["suppression_class"], SCIENTIFIC_CLOSE_VALID)
        self.assertTrue(item["reopen_forbidden"])
        card = {
            "primary_x_family": "R0_TAKER_VOLUME_MIX",
            "claim": "Early taker volume mix predicts H900 MEU.",
            "mechanism": "mix composition",
        }
        self.assertEqual(candidate_matches_hard_close(card, [item]), TAKER_FAMILY)

    def test_t3_route_specific_close_does_not_close_broader_family(self) -> None:
        item = classify_source_payload(
            {
                "owner_decision": "CLOSE_EARLY_PATH_CANDIDATE",
                "atom_id": "ORDINARY_RECENT_EARLY_PATH_H900_FAILED_QUOTES_MEU_REPROJECT_V1",
                "runtime_terminal": "CLOSE_EARLY_PATH_CANDIDATE",
            },
            terminal="CLOSE_EARLY_PATH_CANDIDATE",
            source_receipt="docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/a1_acceptance_v1.json",
        )
        self.assertEqual(item["suppression_class"], SCOPE_LIMITED_CLOSE)
        self.assertTrue(item["reopen_forbidden"])
        broader = {
            "primary_x_family": "EARLY_PATH_CANDIDATE",
            "claim": "A broader early path candidate family remains scientifically open.",
            "mechanism": "path candidate family is wider than the closed atom",
        }
        self.assertIsNone(candidate_matches_hard_close(broader, [item]))
        exact = {
            "primary_x_family": "CLOSE_EARLY_PATH_CANDIDATE",
            "claim": "Reopen CLOSE_EARLY_PATH_CANDIDATE exactly.",
            "mechanism": "same atom",
        }
        self.assertEqual(
            candidate_matches_hard_close(exact, [item]),
            "CLOSE_EARLY_PATH_CANDIDATE",
        )

    def test_t4_legacy_h900_actionability_does_not_block_paired_estimand(self) -> None:
        item = classify_source_payload(
            _h900_legacy_payload(),
            terminal=H900_TERMINAL,
            source_receipt="docs/evidence/early_holder_concentration_actionability_rule_oos/a1_acceptance_v1.json",
        )
        self.assertEqual(item["suppression_class"], LEGACY_MEASUREMENT_LIMITED)
        self.assertFalse(item["reopen_forbidden"])
        self.assertTrue(item["visible_as_prior_work"])
        paired = {
            "primary_x_family": "HOLDER_CONCENTRATION_PAIRED_T0_RELATIVE",
            "claim": "Paired T0-relative liquidation vs same-lot H900, not raw Y_RAW veto.",
            "mechanism": "paired estimand is not the old top-quartile raw actionability",
        }
        self.assertIsNone(candidate_matches_hard_close(paired, [item]))
        self.assertEqual(item["scope_id"], H900_RULE)

    def test_t5_killed_hfic_prior_remains_after_rebase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
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
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            draft_path = Path(tmp) / "draft.json"
            draft_path.write_text(
                json.dumps(bind_draft(json.loads(HAPPY.read_text(encoding="utf-8")), receipt)),
                encoding="utf-8",
            )
            frozen_run = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr)
            frozen = json.loads(frozen_run.stdout)
            critic_path = Path(tmp) / "critic.json"
            critic_path.write_text(
                json.dumps(
                    critic_result_from_packet_only(
                        frozen["critic_input_packet"],
                        "KILL_MECHANISM",
                    )
                ),
                encoding="utf-8",
            )
            finalized = run_cli(
                "finalize",
                "--session-id",
                frozen["session_id"],
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            prior_before = run_cli(
                "prior",
                "--query",
                "ROUTE_FRAGMENTATION",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(prior_before.returncode, 0, prior_before.stderr)
            before = json.loads(prior_before.stdout)
            self.assertGreaterEqual(before["match_count"], 1)
            rebase = run_cli(
                "rebase-science-memory",
                "--confirm-append-only",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(rebase.returncode, 0, rebase.stderr)
            prior_after = run_cli(
                "prior",
                "--query",
                "ROUTE_FRAGMENTATION",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(prior_after.returncode, 0, prior_after.stderr)
            after = json.loads(prior_after.stdout)
            self.assertGreaterEqual(after["match_count"], 1)
            self.assertEqual(before["match_count"], after["match_count"])

    def test_t6_later_authoritative_source_wins_dedupe(self) -> None:
        ambiguous = classify_source_payload(
            {"summary": "owner selection PARK_H13_FROM_PRIORITY parks RC001"},
            terminal="PARK_H13_FROM_PRIORITY",
            source_receipt="registries/decisions_negative_results.yaml",
        )
        typed = classify_source_payload(
            {
                "priority_disposition": "PARKED_FROM_PRIORITY",
                "science_disposition": "RETAINED",
                "hypothesis_verdict": "NOT_REFUTED_NOT_SUPPORTED",
                "owner_decision": "PARK_H13_FROM_PRIORITY",
            },
            terminal="PARK_H13_FROM_PRIORITY",
            source_receipt="docs/evidence/rc001_h13_park_from_priority/a1_h13_park_from_priority_acceptance_v1.json",
        )
        self.assertEqual(ambiguous["suppression_class"], AMBIGUOUS_REQUIRES_OWNER)
        ledger = dedupe_suppression_ledger([ambiguous, typed])
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["suppression_class"], OWNER_PRIORITY_PARK)
        self.assertFalse(ledger[0]["reopen_forbidden"])
        self.assertTrue(
            str(ledger[0]["source_receipt"]).startswith("docs/")
        )

    def test_t7_free_form_park_is_ambiguous_fail_closed(self) -> None:
        item = classify_source_payload(
            {"owner_decision": "PARK_SOMETHING_UNTYPED"},
            terminal="PARK_SOMETHING_UNTYPED",
            source_receipt="docs/evidence/synthetic/untyped_park.json",
        )
        self.assertEqual(item["suppression_class"], AMBIGUOUS_REQUIRES_OWNER)
        self.assertTrue(item["reopen_forbidden"])
        self.assertIn("PARK_SOMETHING_UNTYPED", family_hard_close_terminals([item]))

    def test_t8_projection_rebuild_keeps_suppression_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            ResearchStore(data_root)
            before = enumerate_closed_park_terminals(ROOT, data_root)
            self.assertGreaterEqual(len(before), 8)
            store = ResearchStore(data_root)
            store.rebuild_projection()
            after = enumerate_closed_park_terminals(ROOT, data_root)
            self.assertEqual(before, after)

    def test_t9_hfic_self_memory_does_not_advance_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            before = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            _append_hfic_untagged_candidate(store)
            after = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            self.assertEqual(before, after)

    def test_t10_science_rebase_decision_advances_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            before = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            first = run_cli(
                "rebase-science-memory",
                "--confirm-append-only",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            payload = json.loads(first.stdout)
            self.assertEqual(payload["status"], "APPENDED")
            self.assertEqual(payload["record_id"], REBASE_RECORD_ID)
            after = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            self.assertNotEqual(before, after)
            self.assertEqual(payload["evidence_epoch_before"], before)
            self.assertEqual(payload["evidence_epoch_after"], after)
            replay = run_cli(
                "rebase-science-memory",
                "--confirm-append-only",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            replayed = json.loads(replay.stdout)
            self.assertEqual(replayed["status"], "REPLAY_IDENTICAL")
            self.assertEqual(
                evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root)),
                after,
            )

    def test_t2_freeze_rejects_scientific_family_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            fingerprint = "66" * 32
            _publish_labeled_dataset(
                data_root,
                manifest_id=TAKER_MANIFEST_ID,
                fingerprint=fingerprint,
                labels={
                    "evidence_role": "PRIMARY_FORWARD_FALSIFIER",
                    "scientific_terminal": TAKER_FAMILY,
                },
                decision=_authoritative_taker_decision(fingerprint),
            )
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
            happy = bind_draft(json.loads(HAPPY.read_text(encoding="utf-8")), receipt)
            reopening = dict(happy)
            reopening["candidates"] = [
                {
                    **candidate,
                    "primary_x_family": "R0_TAKER_VOLUME_MIX",
                    "claim": "Early taker volume mix predicts H900 MEU.",
                }
                if candidate.get("display_ordinal") == 1
                else candidate
                for candidate in happy["candidates"]
            ]
            with self.assertRaises(HficSessionError) as raised:
                freeze_draft(
                    reopening,
                    preflight_receipt=receipt,
                    store=ResearchStore(data_root),
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "CLOSED_FAMILY_REOPEN")

    def test_t3_freeze_allows_broader_path_family_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
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
            happy = bind_draft(json.loads(HAPPY.read_text(encoding="utf-8")), receipt)
            broader = dict(happy)
            broader["candidates"] = [
                {
                    **candidate,
                    "primary_x_family": "EARLY_PATH_CANDIDATE",
                    "claim": "A broader early path candidate family remains open.",
                    "mechanism": "path candidate family is wider than the closed atom",
                }
                if candidate.get("display_ordinal") == 1
                else candidate
                for candidate in happy["candidates"]
            ]
            frozen = freeze_draft(
                broader,
                preflight_receipt=receipt,
                store=ResearchStore(data_root),
                repo_root=ROOT,
            )
            self.assertEqual(frozen["session_state"], "FROZEN_AWAITING_CRITIC")

    def test_live_git_parks_are_not_hard_closed(self) -> None:
        ledger = enumerate_closed_park_terminals(ROOT, None)
        parks = [
            item
            for item in ledger
            if item.get("suppression_class") == OWNER_PRIORITY_PARK
        ]
        self.assertGreaterEqual(len(parks), 2)
        self.assertTrue(all(item.get("reopen_forbidden") is False for item in parks))
        packet = select_closed_family_ledger_for_packet(ledger)
        packet_terminals = {item["terminal"] for item in packet}
        self.assertIn("PARK_H11_FROM_PRIORITY", packet_terminals)
        self.assertIn("PARK_H13_FROM_PRIORITY", packet_terminals)
        self.assertTrue(
            all(
                item.get("reopen_forbidden") is False
                for item in packet
                if item.get("suppression_class") == OWNER_PRIORITY_PARK
            )
        )


if __name__ == "__main__":
    unittest.main()
