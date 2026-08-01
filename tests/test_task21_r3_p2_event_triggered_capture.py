from __future__ import annotations

import tempfile
import unittest
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_r2_p2_event_triggered_capture import (  # noqa: E402
    R3_P2_ATOM_ID,
    Task21P2AuthorityRequired,
    Task21P2Error,
    Task21P2ExecutionGate,
    run_event_triggered_p2_capture,
)
from tests.test_task21_event_triggered_followup_capture import (  # noqa: E402
    FakeQuoteTransport,
    TickingNow,
)
from tests.test_task21_r2_p2_event_triggered_capture import (  # noqa: E402
    SyntheticP2Repository,
)


CONFIG = ROOT / "configs/task21_r3_p2_event_triggered_capture_v1.yaml"
FIXED_NOW = datetime(2026, 8, 1, 14, 51, tzinfo=UTC)
MEMBERS = [
    {
        "batch_id": "T21-R3",
        "entered_at": "2026-08-01T13:40:15.366598Z",
        "hypothesis_version_id": "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1",
        "member_id": "T21-WATCH-7a678b1052ac10b7d492",
        "mint": "CWfuB1HDEp9W3xT3prBX8EPa1TQWKh1PmWFot3Gkpump",
        "mint_decimals": 6,
        "nomination_event_id": "T21-R3-NOM-0d8cbfac225007f093cb",
        "panel_deadline_at": "2026-08-02T13:40:15.366598Z",
        "panel_status": {"P0": "PENDING", "P1": "BLOCKED_ON_P0", "P2": "BLOCKED_ON_P1"},
        "policy_version": "1.0",
    },
    {
        "batch_id": "T21-R3",
        "entered_at": "2026-08-01T13:40:15.366598Z",
        "hypothesis_version_id": "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1",
        "member_id": "T21-WATCH-2c5632a2ba71c8e44637",
        "mint": "8LRXPgAdhFktQzXjRVWgqWBWnMZTexjxsMrtQTQ6pump",
        "mint_decimals": 6,
        "nomination_event_id": "T21-R3-NOM-924c8d05d1001c080722",
        "panel_deadline_at": "2026-08-02T13:40:15.366598Z",
        "panel_status": {"P0": "PENDING", "P1": "BLOCKED_ON_P0", "P2": "BLOCKED_ON_P1"},
        "policy_version": "1.0",
    },
]
P0_COMPLETED = ["2026-08-01T13:40:31.564666Z", "2026-08-01T13:40:50.040339Z"]
P1_COMPLETED = ["2026-08-01T14:20:33.971358Z", "2026-08-01T14:20:52.407346Z"]


def synthetic(root: Path) -> SyntheticP2Repository:
    return SyntheticP2Repository(
        root,
        config_path=CONFIG,
        members=MEMBERS,
        p0_completed=P0_COMPLETED,
        p1_completed=P1_COMPLETED,
        recovery_backup_at="2026-08-01T14:42:18.558Z",
        recovery_restore_at="2026-08-01T14:44:13.3237604Z",
    )


class Task21R3P2CaptureTests(unittest.TestCase):
    def test_happy_path_captures_two_panels_and_sixteen_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = synthetic(Path(directory))
            receipt = run_event_triggered_p2_capture(
                gate=Task21P2ExecutionGate(R3_P2_ATOM_ID),
                repo_root=repo.root,
                config_path=repo.config_path,
                transport_factory=lambda _member: FakeQuoteTransport(),
                now=TickingNow(FIXED_NOW),
                sleeper=lambda _seconds: None,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
                output_root_override=repo.output,
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["batch_id"], "T21-R3")
            self.assertEqual(receipt["p2"]["panels_complete"], 2)
            self.assertEqual(receipt["actual_actions"]["jupiter_calls"], 16)
            self.assertEqual(
                receipt["next_boundary"]["status"],
                "R3_COMPLETE_FINAL_COHORT_REVIEW_AND_FREEZE_REQUIRED",
            )

    def test_minimum_separation_blocks_entire_population_before_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = synthetic(Path(directory))
            called = False

            def factory(_member):
                nonlocal called
                called = True
                return FakeQuoteTransport()

            with self.assertRaisesRegex(Task21P2Error, "p2_population_not_ready"):
                run_event_triggered_p2_capture(
                    gate=Task21P2ExecutionGate(R3_P2_ATOM_ID),
                    repo_root=repo.root,
                    config_path=repo.config_path,
                    transport_factory=factory,
                    now=lambda: datetime(2026, 8, 1, 14, 50, 52, tzinfo=UTC),
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                    output_root_override=repo.output,
                )
            self.assertFalse(called)
            self.assertFalse(repo.output.exists())

    def test_wrong_authority_phrase_fails_closed(self) -> None:
        with self.assertRaises(Task21P2AuthorityRequired):
            Task21P2ExecutionGate("T21-A6S_R3_P2_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1")


if __name__ == "__main__":
    unittest.main()
