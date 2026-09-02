from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_grounding import (  # noqa: E402
    HficGroundingError,
    aggregate_diagnostics,
    build_feature_grounding_projection,
    ground_candidate,
    structural_signature_v1_sha256,
)
from solana_alpha_lab.factory.hfic_identity import (  # noqa: E402
    IDENTITY_FIELDS,
    candidate_identity,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    _canonical_json_hash,
    freeze_draft,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_hfic_forge_context_and_no_worthy import bind_draft, run_cli  # noqa: E402
from tests.test_hfic_session import critic_result_from_packet_only  # noqa: E402

CLI = ROOT / "scripts/hypothesis_forge.py"
DRAFT_V12 = ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"
DRAFT_V11 = ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
CONTEXT_SHA = "ab" * 32


def _load_draft() -> dict:
    return json.loads(DRAFT_V12.read_text(encoding="utf-8"))


def _card_from_draft(ordinal: int) -> dict:
    draft = _load_draft()
    for card in draft["candidates"]:
        if card["display_ordinal"] == ordinal:
            return dict(card)
    raise AssertionError(f"missing ordinal {ordinal}")


class FeatureGroundingProjectionTests(unittest.TestCase):
    def test_projection_deterministic_and_sorted(self) -> None:
        first = build_feature_grounding_projection(ROOT)
        second = build_feature_grounding_projection(ROOT)
        self.assertEqual(first, second)
        entries = first["feature_grounding_entries"]
        ids = [item["feature_id"] for item in entries]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(first["feature_grounding_source_digest_sha256"]), 64)
        self.assertFalse(first["feature_grounding_truncated"])
        for item in entries:
            self.assertEqual(
                set(item),
                {
                    "feature_id",
                    "availability_class",
                    "available_to_strategy_semantics",
                    "entity_scope",
                    "units",
                },
            )


class GroundCandidateTests(unittest.TestCase):
    def test_pit_ready_resolves_exact_source_semantics(self) -> None:
        card = _card_from_draft(1)
        grounding = ground_candidate(
            card,
            repo_root=ROOT,
            context_packet_sha256=CONTEXT_SHA,
            accepted_capability_ids=["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
        )
        binding = grounding["feature_bindings"][0]
        self.assertEqual(binding["feature_id"], "FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO")
        self.assertEqual(binding["availability_class"], "PIT_READY")
        self.assertEqual(
            binding["available_to_strategy_semantics"],
            "BOUNDED_PIT_READY_EXPLICIT_SCOPE",
        )
        self.assertEqual(binding["value_status"], "PIT_READY")
        self.assertEqual(grounding["terminal"], "GROUNDED")
        self.assertEqual(
            grounding["capability_bindings"][0]["authority_granted"],
            False,
        )

    def test_historical_not_upgraded_to_pit(self) -> None:
        card = _card_from_draft(2)
        grounding = ground_candidate(
            card,
            repo_root=ROOT,
            context_packet_sha256=CONTEXT_SHA,
            accepted_capability_ids=[],
        )
        binding = grounding["feature_bindings"][0]
        self.assertEqual(binding["availability_class"], "HISTORICAL_RECONSTRUCTIBLE")
        self.assertNotEqual(binding["availability_class"], "PIT_READY")
        self.assertEqual(binding["value_status"], "UNKNOWN")

    def test_forward_only_stays(self) -> None:
        card = _card_from_draft(3)
        grounding = ground_candidate(
            card,
            repo_root=ROOT,
            context_packet_sha256=CONTEXT_SHA,
            accepted_capability_ids=[],
        )
        binding = grounding["feature_bindings"][0]
        self.assertEqual(binding["availability_class"], "FORWARD_ONLY")

    def test_missing_typed(self) -> None:
        card = _card_from_draft(1)
        card["required_feature_ids"] = ["FEAT-CREATOR-CLUSTER-SHARE"]
        card["required_capability_ids"] = []
        grounding = ground_candidate(
            card,
            repo_root=ROOT,
            context_packet_sha256=CONTEXT_SHA,
            accepted_capability_ids=[],
        )
        binding = grounding["feature_bindings"][0]
        self.assertEqual(binding["availability_class"], "MISSING_CAPABILITY")
        self.assertEqual(binding["value_status"], "MISSING_CAPABILITY")

    def test_unknown_feature_fail_closed(self) -> None:
        card = _card_from_draft(1)
        card["required_feature_ids"] = ["FEAT-DOES-NOT-EXIST"]
        with self.assertRaises(HficGroundingError) as raised:
            ground_candidate(
                card,
                repo_root=ROOT,
                context_packet_sha256=CONTEXT_SHA,
                accepted_capability_ids=[],
            )
        self.assertEqual(str(raised.exception), "FORGE_CANDIDATE_UNKNOWN_FEATURE_ID")

    def test_unknown_capability_fail_closed(self) -> None:
        card = _card_from_draft(1)
        card["required_capability_ids"] = ["CAP-DOES-NOT-EXIST"]
        with self.assertRaises(HficGroundingError) as raised:
            ground_candidate(
                card,
                repo_root=ROOT,
                context_packet_sha256=CONTEXT_SHA,
                accepted_capability_ids=["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
            )
        self.assertEqual(str(raised.exception), "FORGE_CANDIDATE_UNKNOWN_CAPABILITY_ID")

    def test_unresolved_requirements_allowed(self) -> None:
        card = _card_from_draft(4)
        grounding = ground_candidate(
            card,
            repo_root=ROOT,
            context_packet_sha256=CONTEXT_SHA,
            accepted_capability_ids=[],
        )
        self.assertEqual(grounding["terminal"], "GROUNDED_WITH_GAPS")
        self.assertEqual(
            grounding["unresolved_requirements"],
            ["decision-time creator-cluster attribution"],
        )

    def test_state_transition_null_ok_for_signature(self) -> None:
        card = _card_from_draft(2)
        self.assertIsNone(card["state_transition"])
        first = structural_signature_v1_sha256(card)
        second = structural_signature_v1_sha256(card)
        self.assertEqual(first, second)


class StructuralSignatureTests(unittest.TestCase):
    def test_deterministic_and_label_invariant(self) -> None:
        card = _card_from_draft(1)
        base = structural_signature_v1_sha256(card)
        mutated = dict(card)
        mutated["label"] = "TOTALLY-DIFFERENT-LABEL"
        mutated["display_ordinal"] = 6
        mutated["claim"] = "Different claim wording that must not affect signature."
        self.assertEqual(base, structural_signature_v1_sha256(mutated))
        changed = dict(card)
        changed["mechanism"] = "Completely different mechanism text."
        self.assertNotEqual(base, structural_signature_v1_sha256(changed))

    def test_signature_not_identity(self) -> None:
        card = _card_from_draft(1)
        identity = candidate_identity(card)
        signature = structural_signature_v1_sha256(card)
        self.assertNotEqual(identity.full_sha256, signature)
        self.assertEqual(IDENTITY_FIELDS, (
            "claim",
            "mechanism",
            "actor_counterparty",
            "population",
            "decision_timestamp",
            "primary_x_family",
            "primary_y",
            "horizon_notional",
            "negative_control",
            "cheapest_falsifier",
        ))


class CompatibilityAndSchemaTests(unittest.TestCase):
    def test_v11_fixture_still_readable(self) -> None:
        draft = json.loads(DRAFT_V11.read_text(encoding="utf-8"))
        frozen = freeze_draft(
            draft,
            preflight_receipt={"receipt_id": "HFIC-PREFLIGHT-FIXTURE-001"},
            repo_root=ROOT,
        )
        self.assertEqual(frozen["prompt_version"], "HFIC-V1.1")
        packet = frozen["critic_input_packet"]
        self.assertEqual(packet["packet_version"], "1.1")
        self.assertEqual(packet["generator_prompt_version"], "HFIC-V1.1")

    def test_v12_draft_schema_and_freeze_grounding(self) -> None:
        draft = _load_draft()
        frozen = freeze_draft(
            draft,
            preflight_receipt={
                "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
                "forge_context_packet_sha256": CONTEXT_SHA,
                "forge_context_packet": {
                    "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"]
                },
            },
            repo_root=ROOT,
        )
        self.assertEqual(frozen["prompt_version"], "HFIC-V1.2")
        grounded = frozen["grounded_candidates"]
        self.assertEqual(len(grounded), 4)
        by_label = {item["label"]: item for item in grounded}
        self.assertEqual(
            by_label["HFIC-V12-C1-PIT-LIQUIDITY-RATIO"]["grounding"]["feature_bindings"][0][
                "availability_class"
            ],
            "PIT_READY",
        )
        self.assertEqual(
            by_label["HFIC-V12-C2-HISTORICAL-RETURN"]["grounding"]["feature_bindings"][0][
                "availability_class"
            ],
            "HISTORICAL_RECONSTRUCTIBLE",
        )
        self.assertEqual(
            by_label["HFIC-V12-C3-FORWARD-QUOTE"]["grounding"]["feature_bindings"][0][
                "availability_class"
            ],
            "FORWARD_ONLY",
        )
        self.assertEqual(
            by_label["HFIC-V12-C4-UNRESOLVED-CREATOR-CLUSTER"]["grounding"]["terminal"],
            "GROUNDED_WITH_GAPS",
        )
        packet = frozen["critic_input_packet"]
        self.assertEqual(packet["packet_version"], "1.2")
        self.assertEqual(
            packet["provisional_lane"]["required_capability_ids"],
            ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
        )
        self.assertEqual(
            packet["selected_candidate"]["decision_unlocked"],
            draft["candidates"][0]["decision_unlocked"],
        )

    def test_unknown_feature_at_freeze_fail_closed(self) -> None:
        draft = _load_draft()
        draft["candidates"][0]["required_feature_ids"] = ["FEAT-MAGIC-NEW"]
        with self.assertRaises(HficSessionError) as raised:
            freeze_draft(
                draft,
                preflight_receipt={
                    "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
                    "forge_context_packet_sha256": CONTEXT_SHA,
                    "forge_context_packet": {
                        "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"]
                    },
                },
                repo_root=ROOT,
            )
        self.assertEqual(str(raised.exception), "FORGE_CANDIDATE_UNKNOWN_FEATURE_ID")


class DiagnosticsAggregateTests(unittest.TestCase):
    def test_last_21_fails(self) -> None:
        with self.assertRaises(HficGroundingError) as raised:
            aggregate_diagnostics([], 21)
        self.assertEqual(str(raised.exception), "DIAGNOSTICS_LAST_N_OUT_OF_BOUNDS")

    def test_legacy_receipt_diagnostics_compat(self) -> None:
        receipts = [
            {
                "prompt_version": "HFIC-V1.1",
                "created_at": "2026-08-25T00:00:00Z",
                "search_key_sha256": "aa" * 32,
                "critic_terminal": "KILL_MECHANISM",
            }
        ]
        out = aggregate_diagnostics(receipts, 1)
        self.assertEqual(out["sessions_count"], 1)
        self.assertEqual(out["prompt_versions"], ["HFIC-V1.1"])


class VerticalE2ETests(unittest.TestCase):
    def test_offline_preflight_freeze_finalize_diagnostics(self) -> None:
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
            packet = receipt["forge_context_packet"]
            self.assertIn("feature_grounding_entries", packet)
            self.assertTrue(packet["feature_grounding_entries"])
            self.assertEqual(len(packet["feature_grounding_source_digest_sha256"]), 64)
            self.assertEqual(packet["prompt_version"], "HFIC-V1.2")
            self.assertEqual(receipt["commissioning"]["provider_calls_actual"], 0)

            draft = bind_draft(_load_draft(), receipt)
            draft_path = Path(tmp) / "draft_v1_2.json"
            receipt_path = Path(tmp) / "preflight.json"
            draft_path.write_text(
                json.dumps(draft, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            receipt_path.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            freeze = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(freeze.returncode, 0, freeze.stderr + freeze.stdout)
            frozen = json.loads(freeze.stdout)
            self.assertEqual(frozen["prompt_version"], "HFIC-V1.2")
            self.assertEqual(len(frozen["grounded_candidates"]), 4)
            packet = frozen["critic_input_packet"]
            critic = critic_result_from_packet_only(packet, "KILL_MECHANISM")
            critic_path = Path(tmp) / "critic.json"
            critic_path.write_text(
                json.dumps(critic, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            finalize = run_cli(
                "finalize",
                "--session-id",
                frozen["session_id"],
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(finalize.returncode, 0, finalize.stderr + finalize.stdout)
            session_receipt = json.loads(finalize.stdout)
            self.assertEqual(session_receipt["prompt_version"], "HFIC-V1.2")
            diagnostics = session_receipt["diagnostics"]
            self.assertEqual(diagnostics["candidate_count"], 4)
            self.assertEqual(diagnostics["known_feature_reference_count"], 3)
            self.assertEqual(
                diagnostics["candidate_with_unresolved_requirement_count"],
                1,
            )
            self.assertEqual(diagnostics["candidate_with_pit_ready_dependency_count"], 1)
            self.assertEqual(
                diagnostics["candidate_with_historical_only_dependency_count"],
                1,
            )
            self.assertEqual(
                diagnostics["candidate_with_forward_only_dependency_count"],
                1,
            )
            self.assertTrue(diagnostics["selected_candidate_present"])
            self.assertFalse(diagnostics["no_worthy_hypothesis"])

            diag = run_cli(
                "diagnostics",
                "--last",
                "1",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(diag.returncode, 0, diag.stderr + diag.stdout)
            aggregate = json.loads(diag.stdout)
            self.assertEqual(aggregate["sessions_count"], 1)
            self.assertEqual(aggregate["candidate_count"], 4)
            self.assertIn("HFIC-V1.2", aggregate["prompt_versions"])

            bad = run_cli(
                "diagnostics",
                "--last",
                "21",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("DIAGNOSTICS_LAST_N_OUT_OF_BOUNDS", bad.stderr)

            store = ResearchStore(data_root)
            replay = run_cli(
                "show-session",
                "--session-id",
                frozen["session_id"],
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            shown = json.loads(replay.stdout)
            self.assertEqual(shown["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(
                shown["session_receipt"]["diagnostics"]["candidate_count"],
                4,
            )
            # Replay must not append a second scientific result.
            cycles = [
                json.loads(record.payload_json)
                for record in store.iter_committed_records()
                if getattr(record.record_kind, "value", record.record_kind)
                == "RESEARCH_CYCLE"
                and json.loads(record.payload_json).get("phase") == "SYNTHESIS_COMPLETE"
            ]
            self.assertEqual(len(cycles), 1)


if __name__ == "__main__":
    unittest.main()
