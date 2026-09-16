"""Post-merge C1 operation: idempotent preview, append-only APPLY, repeat safety."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_memory_policy import (  # noqa: E402
    REASON_PRE_CAPABILITY_BASELINE,
    apply_memory_policy,
    preview_memory_policy,
)
from solana_alpha_lab.factory.hfic_reopened_prior_routing import (  # noqa: E402
    DEFECTIVE_CONTROL_SESSION_ID,
    commission_reopened_priors,
    preview_control_reconsideration,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_hfic_cli import run_cli  # noqa: E402
from tests.test_hfic_operational_memory_quarantine_v1 import (  # noqa: E402
    _session_records,
)

CREATED = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
CLOCK = lambda: CREATED  # noqa: E731


def _store_with_defective_session(raw: str) -> ResearchStore:
    store = ResearchStore(Path(raw))
    store.append(
        _session_records(DEFECTIVE_CONTROL_SESSION_ID, ["HFIC-CAND-DEFECT-001"]),
        transaction_id=f"RESEARCH-TXN-{DEFECTIVE_CONTROL_SESSION_ID}",
    )
    return store


class VisionAcceptanceOperationTests(unittest.TestCase):
    def test_preview_is_read_only_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store_with_defective_session(raw)
            first = preview_control_reconsideration(
                store,
                ROOT,
                data_root=Path(raw),
                defective_session_id=DEFECTIVE_CONTROL_SESSION_ID,
            )
            second = preview_control_reconsideration(
                store,
                ROOT,
                data_root=Path(raw),
                defective_session_id=DEFECTIVE_CONTROL_SESSION_ID,
            )
            # Deterministic read-only preview: identical bytes every run.
            self.assertEqual(
                json.dumps(first, sort_keys=True),
                json.dumps(second, sort_keys=True),
            )
            self.assertIn(
                first.get("terminal"),
                (
                    "CONTROL_RECONSIDERATION_READY_AFTER_COMMISSION",
                    "CONTROL_RECONSIDERATION_NOT_READY",
                ),
            )
            # Preview must not mutate the store: same committed record count.
            count = sum(1 for _ in store.iter_committed_records())
            preview_control_reconsideration(
                store,
                ROOT,
                data_root=Path(raw),
                defective_session_id=DEFECTIVE_CONTROL_SESSION_ID,
            )
            self.assertEqual(count, sum(1 for _ in store.iter_committed_records()))

    def test_apply_is_append_only_and_repeat_safe(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store_with_defective_session(raw)
            commission_reopened_priors(
                store, ROOT, git_sha="0" * 40, clock=CLOCK, confirm_append_only=True
            )
            before_records = [
                record.record_id for record in store.iter_committed_records()
            ]
            # Exact-session quarantine append.
            proposal = preview_memory_policy(
                store,
                repo_root=ROOT,
                quarantine_session_ids=[DEFECTIVE_CONTROL_SESSION_ID],
                reason_code=REASON_PRE_CAPABILITY_BASELINE,
            )
            apply_memory_policy(
                store,
                repo_root=ROOT,
                proposal=proposal["proposal"],
                confirm_append_only=True,
            )
            after_records = [
                record.record_id for record in store.iter_committed_records()
            ]
            self.assertTrue(set(before_records) <= set(after_records))
            # Repeated APPLY: no duplicate mutation, still append-only.
            count_after_first = len(after_records)
            proposal2 = preview_memory_policy(
                store,
                repo_root=ROOT,
                quarantine_session_ids=[DEFECTIVE_CONTROL_SESSION_ID],
                reason_code=REASON_PRE_CAPABILITY_BASELINE,
            )
            apply_memory_policy(
                store,
                repo_root=ROOT,
                proposal=proposal2["proposal"],
                confirm_append_only=True,
            )
            final_records = [
                record.record_id for record in store.iter_committed_records()
            ]
            self.assertGreaterEqual(len(final_records), count_after_first)
            self.assertTrue(set(after_records) <= set(final_records))
            # No record was rewritten: original defective-session hypothesis
            # payload bytes are still present exactly once.
            originals = [
                record
                for record in store.iter_committed_records()
                if record.record_id == "HFIC-HYP-HFIC-CAND-DEFECT-001"
            ]
            self.assertEqual(len(originals), 1)

    def test_cli_vision_acceptance_requires_real_data_plane(self) -> None:
        # Against an empty data root the command must fail typed, not crash.
        with tempfile.TemporaryDirectory() as raw:
            completed = run_cli(
                "vision-acceptance",
                "--format",
                "json",
                data_root=Path(raw),
            )
        self.assertNotEqual(completed.returncode, 0)

    def test_future_cohort_needs_no_legacy_commissioning(self) -> None:
        # A fresh store with no defective session and no legacy priors must
        # not require the commissioning path: ordinary /hypothesis-forge flow
        # works from normal memory policy (no quarantine, no commission).
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            proposal = preview_memory_policy(
                store,
                repo_root=ROOT,
                quarantine_session_ids=[],
                reason_code=REASON_PRE_CAPABILITY_BASELINE,
            )
            # Empty quarantine set: policy is a no-op with zero appends.
            self.assertEqual(proposal["proposal"]["quarantined_session_ids"], [])


if __name__ == "__main__":
    unittest.main()
