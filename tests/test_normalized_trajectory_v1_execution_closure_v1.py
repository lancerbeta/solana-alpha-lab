"""A1 regressions: NO_WORTHY BASE context transport and prefix-through-T input.

Does not execute the scientific representation probe.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_released_trajectory_projection import (  # noqa: E402
    resolve_release_projection_input,
)
from solana_alpha_lab.factory.hfic_representation_probe import (  # noqa: E402
    CONTROL_CONTEXT_KIND_FORGE,
    RepresentationProbeError,
    cohort_readiness_receipt_from_release_manifest,
    control_baseline_from_receipt,
)
from solana_alpha_lab.factory.normalized_trajectory_v1 import (  # noqa: E402
    project_normalized_trajectory,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256  # noqa: E402

from tests.test_hfic_released_trajectory_projection_v1 import (  # noqa: E402
    _write_release,
)
from tests.test_hfic_representation_probe import (  # noqa: E402
    _cohort_readiness_receipt,
    _representation_fixture,
    build_challenger_packet,
)
from tests.test_normalized_trajectory_v1 import _row, _series  # noqa: E402


def _no_worthy_forge_receipt() -> dict[str, object]:
    """Completed NO_WORTHY CONTROL: critic packet absent, BASE context exact."""

    forge_context = {
        "prompt_version": "HFIC-V1.2",
        "owner_focus": "AUTO",
        "evidence_epoch_sha256": "aa" * 32,
        "search_key_sha256": "cc" * 32,
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        "research_memory_as_of": "2026-09-16T12:00:00Z",
        "dataset_manifest_ids": ["DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"],
        "vision_integrity": {"status": "PASS"},
    }
    digest = canonical_sha256(forge_context)
    session_receipt = {
        "session_id": "HFIC-SESS-NO-WORTHY-BASE",
        "session_state": "SYNTHESIS_COMPLETE",
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "prompt_version": "HFIC-V1.2",
        "critic_input_packet_sha256": None,
        "forge_context_packet_sha256": digest,
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        "final_session_terminal": "NO_WORTHY_HYPOTHESIS",
        "critic_terminal": "NO_WORTHY_HYPOTHESIS",
    }
    receipt: dict[str, object] = {
        "session_id": "HFIC-SESS-NO-WORTHY-BASE",
        "critic_input_packet": None,
        "critic_input_packet_sha256": None,
        "forge_context_packet": forge_context,
        "forge_context_packet_sha256": digest,
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "prompt_version": "HFIC-V1.2",
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        "final_session_terminal": "NO_WORTHY_HYPOTHESIS",
        "critic_terminal": "NO_WORTHY_HYPOTHESIS",
        "session_receipt": session_receipt,
    }
    from solana_alpha_lab.factory.hfic_representation_probe import (
        control_memory_baseline_sha256,
    )

    receipt["memory_baseline_sha256"] = control_memory_baseline_sha256(receipt)
    return receipt


class NoWorthyBaseContextTransport(unittest.TestCase):
    def test_completed_no_worthy_uses_exact_forge_context_not_fake_critic(self) -> None:
        receipt = _no_worthy_forge_receipt()
        baseline = control_baseline_from_receipt(receipt)
        self.assertEqual(baseline.context_kind, CONTROL_CONTEXT_KIND_FORGE)
        self.assertEqual(baseline.terminal, "NO_WORTHY_HYPOTHESIS")
        self.assertEqual(
            baseline.packet_sha256, receipt["forge_context_packet_sha256"]
        )
        self.assertEqual(baseline.packet, receipt["forge_context_packet"])
        self.assertNotIn("selected_candidate", baseline.packet)

        readiness = _cohort_readiness_receipt()
        challenger = build_challenger_packet(
            baseline,
            _representation_fixture(),
            cohort_readiness_receipt=readiness,
        )
        self.assertEqual(challenger["control_context_kind"], CONTROL_CONTEXT_KIND_FORGE)
        self.assertEqual(
            challenger["control_packet_sha256"], receipt["forge_context_packet_sha256"]
        )
        self.assertEqual(challenger["control_context"], receipt["forge_context_packet"])
        self.assertIsNone(challenger.get("critic_input_packet"))
        self.assertNotIn("selected_candidate", json.dumps(challenger))

    def test_no_worthy_session_may_omit_mode_when_forge_context_carries_it(self) -> None:
        receipt = _no_worthy_forge_receipt()
        del receipt["evidence_surface_mode"]
        session = receipt["session_receipt"]
        assert isinstance(session, dict)
        del session["evidence_surface_mode"]
        del session["final_session_terminal"]
        baseline = control_baseline_from_receipt(receipt)
        self.assertEqual(baseline.context_kind, CONTROL_CONTEXT_KIND_FORGE)
        self.assertEqual(baseline.terminal, "NO_WORTHY_HYPOTHESIS")

    def test_no_worthy_hash_drift_fails_closed(self) -> None:
        receipt = _no_worthy_forge_receipt()
        receipt["forge_context_packet_sha256"] = "ff" * 32
        session = receipt["session_receipt"]
        assert isinstance(session, dict)
        session["forge_context_packet_sha256"] = "ff" * 32
        with self.assertRaises(RepresentationProbeError) as raised:
            control_baseline_from_receipt(receipt)
        self.assertEqual(str(raised.exception), "INVALID_CONTROL_PACKET_HASH")


class PrefixThroughTInput(unittest.TestCase):
    def test_future_only_member_does_not_fail_the_cohort(self) -> None:
        rows = []
        rows.extend(_series("known-member", "PRICE", (1.0, 2.0, 3.0)))
        rows.extend(_series("known-member", "LIQUIDITY", (1.0, 1.0, 1.0)))
        rows.extend(_series("known-member", "TRADERS", (1.0, 1.0, 1.0)))
        rows.append(_row("future-only-member", 3600, "PRICE", 999.0))
        projected = project_normalized_trajectory(rows)
        self.assertEqual(projected.payload["eligible_member_count"], 1)
        self.assertEqual(
            projected.payload["pit"]["cutoff"], "member_anchor_plus_Y1800"
        )

    def test_release_projection_skips_future_only_members(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            release_root = _write_release(
                Path(raw),
                anchor=datetime(2026, 9, 1, tzinfo=UTC),
                extra_future_only_members=1,
                with_candidate_state=True,
            )
            result = resolve_release_projection_input(release_root)
            self.assertEqual(result["eligible_member_count"], 10)
            payload = result["representation"].payload
            self.assertNotIn(
                "base_x_population_n", result["projection_input_receipt"]
            )
            self.assertEqual(
                result["projection_input_receipt"]["x_allowed_lateness_seconds"],
                300,
            )
            self.assertEqual(payload["schedule"]["prefix_due_offset_seconds"], [300, 900, 1800])
            self.assertEqual(payload["schedule"]["x_allowed_lateness_seconds"], 300)
            self.assertEqual(
                payload["pit"]["x_eligibility_lateness_seconds_used"], 300
            )
            self.assertNotIn("MINT", json.dumps(payload))
            # 1.0 fixture has no schedule artifact: scientific n stays absent.
            # Do not occupy the scientific denominator with yield_eligible.

    def test_readiness_helper_admits_schema_version_1_1_identity_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            release_root = _write_release(
                Path(raw),
                anchor=datetime(2026, 9, 1, tzinfo=UTC),
            )
            written = json.loads(
                (release_root / "release_manifest.json").read_text(encoding="utf-8")
            )
            written["schema_version"] = "1.1"
            written["schedule_producer_git_sha"] = written["producer_git_sha"]
            written["observation_schedule_sha256"] = "dd" * 32
            readiness = cohort_readiness_receipt_from_release_manifest(written)
            self.assertEqual(
                readiness["release_manifest"]["schema_version"], "1.1"
            )
            self.assertNotIn(
                "observation_schedule_sha256", readiness["release_manifest"]
            )
            self.assertEqual(
                readiness["release_manifest"]["producer_git_sha"],
                written["producer_git_sha"],
            )


if __name__ == "__main__":
    unittest.main()
