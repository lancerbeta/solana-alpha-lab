"""Machine vision integrity for the bounded FORGE_CONTEXT_PACKET.

Bounded != silently blind: every omitted feature/grounding/semantic item must
be deterministically accounted for; material/unknown omission raises
FORGE_VISION_INTEGRITY_BLOCKED instead of reaching Prompt A, and
NO_WORTHY_HYPOTHESIS cannot be persisted when vision integrity != PASS.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from solana_alpha_lab.factory.hfic_preflight import (
    MAX_PACKET_BYTES,
    build_forge_context_packet,
)
from solana_alpha_lab.factory.hfic_vision_integrity import (
    FORGE_VISION_INTEGRITY_BLOCKED,
    REDUNDANT_WITH_RETAINED_INFORMATION,
    INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION,
    classify_feature_omission,
    compute_vision_integrity,
)

ROOT = Path(__file__).resolve().parents[1]


class OmissionClassification(unittest.TestCase):
    def test_distinct_material_feature_concept_cannot_be_silent(self) -> None:
        omitted = {
            "feature_id": "FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO",
            "availability_class": "PIT_READY",
        }
        retained_concepts = {"VALUATION"}
        retained_availability = {"HISTORICAL_RECONSTRUCTIBLE", "MISSING"}
        verdict = classify_feature_omission(
            omitted, retained_concepts=retained_concepts, retained_availability=retained_availability
        )
        self.assertEqual(verdict["omission_class"], "MATERIAL_CANDIDATE_GENERATION_INFORMATION_LOSS")

    def test_redundant_detail_is_redundant(self) -> None:
        omitted = {
            "feature_id": "FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO",
            "availability_class": "PIT_READY",
        }
        verdict = classify_feature_omission(
            omitted,
            retained_concepts={"FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO"},
            retained_availability={"PIT_READY"},
        )
        self.assertEqual(
            verdict["omission_class"], REDUNDANT_WITH_RETAINED_INFORMATION
        )

    def test_unavailable_feature_outside_control_surface(self) -> None:
        omitted = {
            "feature_id": "FEAT-CREATOR-DIRECT-SHARE",
            "availability_class": "MISSING",
        }
        verdict = classify_feature_omission(
            omitted, retained_concepts=set(), retained_availability=set()
        )
        self.assertEqual(
            verdict["omission_class"], INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION
        )


class PacketVisionReceipt(unittest.TestCase):
    def _packet(self) -> dict:
        with tempfile.TemporaryDirectory() as raw:
            from tests.test_hfic_reopened_prior_search_routing_v1 import (
                H11,
                H13,
                DEFECTIVE_CONTROL_SESSION_ID,
                _hyp,
            )
            from solana_alpha_lab.factory.hfic_reopened_prior_routing import (
                overlay_search_payloads,
                resolve_all_reopened_priors,
            )
            from solana_alpha_lab.factory.research_store import ResearchStore

            data_root = Path(raw)
            store = ResearchStore(data_root)
            store.append(
                [
                    _hyp("HYP-EARLY-TAKER-VOLUME-MIX-H900-V1", "taker volume mix"),
                    _hyp(
                        "HFIC-CAND-DEFECT-001",
                        "defective control",
                        hfic=True,
                    ),
                ],
                transaction_id="RESEARCH-TXN-REOPEN-TEST",
            )
            extras = [item["payload"] for item in resolve_all_reopened_priors(ROOT)]
            planned = overlay_search_payloads(
                store, extras, [DEFECTIVE_CONTROL_SESSION_ID]
            )
            from solana_alpha_lab.factory.hfic_control_integrity import (
                CURRENT_REPRESENTATION_CONTROL_V1,
            )

            packet, _digest = build_forge_context_packet(
                ROOT,
                data_root,
                owner_focus="AUTO",
                evidence_epoch="aa" * 32,
                search_key="bb" * 32,
                commissioning_status="FAST_LANE_COMMISSIONED",
                research_memory_as_of="2026-09-15T00:00:00Z",
                store=store,
                persist=False,
                search_payloads=planned,
                evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
            )
            return packet

    def test_packet_carries_vision_integrity_receipt(self) -> None:
        packet = self._packet()
        receipt = packet.get("vision_integrity")
        self.assertIsInstance(receipt, dict)
        self.assertEqual(receipt.get("status"), "PASS")
        self.assertEqual(receipt.get("material_information_loss"), 0)
        self.assertEqual(receipt.get("unknown_omission"), 0)
        # Compact availability index preserved PIT_READY distinction.
        availability = {
            str(entry.get("availability_class"))
            for entry in packet["feature_grounding_entries"]
        }
        self.assertIn("PIT_READY", availability)

    def test_packet_compact_grounding_stays_within_budget(self) -> None:
        packet = self._packet()
        encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
        self.assertLessEqual(len(encoded), MAX_PACKET_BYTES)


class NoWorthyTrustGate(unittest.TestCase):
    def _draft(self) -> dict:
        return json.loads(
            (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json").read_text(
                encoding="utf-8"
            )
        )

    def _receipt(self, status: str) -> dict:
        return {
            "action": "START_NEW_SESSION",
            "prompt_version": "HFIC-V1.1",
            "forge_context_packet": {
                "vision_integrity": {
                    "status": status,
                    **({"reason": FORGE_VISION_INTEGRITY_BLOCKED} if status != "PASS" else {}),
                }
            },
        }

    def test_no_worthy_cannot_persist_with_vision_blocked(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            HficSessionError,
            freeze_draft,
        )

        with self.assertRaises(HficSessionError) as raised:
            freeze_draft(
                self._draft(),
                preflight_receipt=self._receipt("BLOCKED"),
                store=None,
                repo_root=None,
            )
        self.assertEqual(str(raised.exception), "FORGE_VISION_INTEGRITY_BLOCKED")

    def test_no_worthy_persists_with_vision_pass(self) -> None:
        from solana_alpha_lab.factory.hfic_session import freeze_draft

        frozen = freeze_draft(
            self._draft(),
            preflight_receipt=self._receipt("PASS"),
            store=None,
            repo_root=None,
        )
        self.assertEqual(frozen["critic_terminal"], "NO_WORTHY_HYPOTHESIS")

    def test_material_truncation_blocks_instead_of_no_worthy(self) -> None:
        receipt = compute_vision_integrity(
            grounding_entries=[
                {
                    "feature_id": "FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO",
                    "availability_class": "PIT_READY",
                }
            ],
            retained_feature_ids=[],
            retained_families=["VALUATION"],
            retained_availability_classes=["HISTORICAL_RECONSTRUCTIBLE"],
        )
        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertEqual(receipt["reason"], FORGE_VISION_INTEGRITY_BLOCKED)


if __name__ == "__main__":
    unittest.main()
