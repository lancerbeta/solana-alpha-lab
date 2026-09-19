"""HFIC_OPERATIONAL_PACKET_GUARD_SIMPLIFICATION_V1 behavioral regressions."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_memory_policy import (  # noqa: E402
    iter_search_memory_hypothesis_payloads,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    CONTROL_FORGE_MAX_PACKET_BYTES,
    FORGE_OPERATIONAL_PACKET_MAX_BYTES,
    FORGE_PACKET_GROWTH_WARNING_BYTES,
    HficPreflightError,
    MAX_PACKET_BYTES,
    MAX_RANKED_PRIORS,
    MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND,
    ORDINARY_FORGE_MAX_PACKET_BYTES,
    build_forge_context_packet,
    forge_context_packet_max_bytes,
)
from solana_alpha_lab.factory.hfic_representation_probe import (  # noqa: E402
    FORGE_OPERATIONAL_PACKET_MAX_BYTES as CHALLENGER_PACKET_CAP,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from solana_alpha_lab.factory.run_passport import canonical_json_bytes  # noqa: E402
from tests.test_hfic_forge_prior_context_capacity_repair_v1 import (  # noqa: E402
    FOCUS,
    _decision_event,
    _fat_hfic_candidate,
)


class OperationalPacketGuardSimplificationTests(unittest.TestCase):
    def test_one_operational_hard_cap_shared(self) -> None:
        self.assertEqual(FORGE_OPERATIONAL_PACKET_MAX_BYTES, 65536)
        self.assertEqual(FORGE_PACKET_GROWTH_WARNING_BYTES, 20480)
        self.assertEqual(MAX_PACKET_BYTES, FORGE_OPERATIONAL_PACKET_MAX_BYTES)
        self.assertEqual(ORDINARY_FORGE_MAX_PACKET_BYTES, FORGE_OPERATIONAL_PACKET_MAX_BYTES)
        self.assertEqual(CONTROL_FORGE_MAX_PACKET_BYTES, FORGE_OPERATIONAL_PACKET_MAX_BYTES)
        self.assertEqual(CHALLENGER_PACKET_CAP, FORGE_OPERATIONAL_PACKET_MAX_BYTES)
        self.assertEqual(forge_context_packet_max_bytes(None), 65536)
        self.assertEqual(
            forge_context_packet_max_bytes(CURRENT_REPRESENTATION_CONTROL_V1),
            65536,
        )
        self.assertEqual(MAX_RANKED_PRIORS, 8)

    def test_warning_does_not_drop_scientific_minimum(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-OPG-WARN"
            hyp = _fat_hfic_candidate(1, transaction_id=txn)
            store.append(
                [
                    hyp,
                    _decision_event(
                        "HFIC-CAND-FAT0001DEADBEEF",
                        decision_kind="REJECT",
                        reason_code="KILL_DATA_INFEASIBLE",
                        transaction_id=txn,
                    ),
                ],
                transaction_id=txn,
            )
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.FORGE_PACKET_GROWTH_WARNING_BYTES",
                100,
            ):
                packet, _digest = build_forge_context_packet(
                    ROOT,
                    Path(raw),
                    owner_focus=FOCUS,
                    evidence_epoch="aa" * 32,
                    search_key="bb" * 32,
                    commissioning_status="FAST_LANE_COMMISSIONED",
                    research_memory_as_of="2026-09-19T00:00:00Z",
                    store=store,
                    persist=False,
                    search_payloads=payloads,
                    evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
                )
            encoded = canonical_json_bytes(packet)
            receipt = packet["truncation_receipt"]
            self.assertGreater(len(encoded), 100)
            self.assertLess(len(encoded), FORGE_OPERATIONAL_PACKET_MAX_BYTES)
            self.assertTrue(receipt["growth_warning"])
            self.assertEqual(receipt["growth_warning_bytes"], 100)
            self.assertNotEqual(
                receipt.get("reason"),
                "MAX_PACKET_BYTES_DROP_FEATURE_GROUNDING",
            )
            entries = packet["ranked_prior_entries"]
            self.assertTrue(entries)
            hard = entries[0]
            self.assertTrue(hard.get("population"))
            self.assertTrue(hard.get("decision_timestamp"))
            self.assertTrue(hard.get("horizon_notional"))
            self.assertTrue(hard.get("negative_control"))
            self.assertTrue(packet.get("feature_grounding_entries"))
            self.assertEqual(
                packet["evidence_surface_mode"],
                CURRENT_REPRESENTATION_CONTROL_V1,
            )

    def test_operational_hard_cap_still_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-OPG-CAP"
            events = [_fat_hfic_candidate(i, transaction_id=txn) for i in range(1, 9)]
            events.append(
                _decision_event(
                    "HFIC-CAND-FAT0001DEADBEEF",
                    decision_kind="REJECT",
                    reason_code="KILL_DATA_INFEASIBLE",
                    transaction_id=txn,
                )
            )
            store.append(events, transaction_id=txn)
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.FORGE_OPERATIONAL_PACKET_MAX_BYTES",
                2000,
            ):
                with self.assertRaises(HficPreflightError) as raised:
                    build_forge_context_packet(
                        ROOT,
                        Path(raw),
                        owner_focus=FOCUS,
                        evidence_epoch="aa" * 32,
                        search_key="bb" * 32,
                        commissioning_status="FAST_LANE_COMMISSIONED",
                        research_memory_as_of="2026-09-19T00:00:00Z",
                        store=store,
                        persist=False,
                        search_payloads=payloads,
                        evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
                    )
            self.assertIn(
                str(raised.exception),
                {
                    MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND,
                    "FORGE_CONTEXT_PACKET_CAPACITY_EXCEEDED",
                },
            )

    def test_packet_above_old_16kib_can_pass(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-OPG-16K"
            events = [_fat_hfic_candidate(i, transaction_id=txn) for i in range(1, 9)]
            events.append(
                _decision_event(
                    "HFIC-CAND-FAT0001DEADBEEF",
                    decision_kind="REJECT",
                    reason_code="KILL_DATA_INFEASIBLE",
                    transaction_id=txn,
                )
            )
            store.append(events, transaction_id=txn)
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            packet, _digest = build_forge_context_packet(
                ROOT,
                Path(raw),
                owner_focus=FOCUS,
                evidence_epoch="aa" * 32,
                search_key="bb" * 32,
                commissioning_status="FAST_LANE_COMMISSIONED",
                research_memory_as_of="2026-09-19T00:00:00Z",
                store=store,
                persist=False,
                search_payloads=payloads,
                evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
            )
            encoded = canonical_json_bytes(packet)
            self.assertGreater(len(encoded), 16384)
            self.assertLess(len(encoded), 65536)
            self.assertEqual(
                packet["truncation_receipt"]["max_packet_bytes"],
                65536,
            )
            self.assertNotEqual(
                packet["truncation_receipt"].get("reason"),
                "MAX_PACKET_BYTES_DROP_FEATURE_GROUNDING",
            )
            self.assertEqual((packet.get("vision_integrity") or {}).get("status"), "PASS")


if __name__ == "__main__":
    unittest.main()
