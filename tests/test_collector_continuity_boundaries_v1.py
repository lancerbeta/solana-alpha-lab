"""Regression tests for continuity selection and lightweight monitor imports."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_read_model import (  # noqa: E402
    classify_doctor_current_activation,
    select_current_activation,
)


class CollectorContinuityBoundaryTests(unittest.TestCase):
    def test_active_selection_prefers_freshest_peer(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-OLD",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-NEW",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
        ]
        self.assertEqual(
            select_current_activation(rows, now=now)["activation_id"],
            "ACT-NEW",
        )

    def test_draining_selection_prefers_freshest_peer(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-DRAIN-OLD",
                "state": "DRAINING",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-DRAIN-NEW",
                "state": "DRAINING",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
        ]
        self.assertEqual(
            select_current_activation(rows, now=now)["activation_id"],
            "ACT-DRAIN-NEW",
        )

    def test_current_selection_does_not_cross_family_without_scope(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-FAMILY-A-DRAINING",
                "state": "DRAINING",
                "cohort_family_key": "FAMILY-A",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-FAMILY-B-ACTIVE",
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-B",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
        ]
        self.assertIsNone(select_current_activation(rows, now=now))
        self.assertEqual(
            select_current_activation(rows, now=now, family_key="FAMILY-A")[
                "activation_id"
            ],
            "ACT-FAMILY-A-DRAINING",
        )

    def test_current_selection_fails_closed_without_family_identity(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-UNSCOPED",
                "state": "ACTIVE",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            }
        ]
        self.assertIsNone(select_current_activation(rows, now=now))
        report = classify_doctor_current_activation(rows, now=now)
        self.assertEqual(report["terminal"], "DOCTOR_ACTIVATION_SCOPE_AMBIGUOUS")
        self.assertEqual(report["next_action"], "RECONCILE_ACTIVATION_FAMILY_SCOPE")

    def test_exact_scope_resolves_selection_before_ambiguity_gate(self) -> None:
        rows = [
            {
                "activation_id": "ACT-FAMILY-A",
                "schedule_sha256": "a" * 64,
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-A",
            },
            {
                "activation_id": "ACT-FAMILY-B",
                "schedule_sha256": "b" * 64,
                "state": "ACTIVE",
                "cohort_family_key": "FAMILY-B",
            },
        ]
        report = classify_doctor_current_activation(
            [rows[0]],
            explicit_scope=True,
        )
        self.assertEqual(report["terminal"], "DOCTOR_CURRENT_OK")
        self.assertEqual(report["current_activation_id"], "ACT-FAMILY-A")

    def test_operability_watch_import_does_not_eagerly_load_research_dependencies(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        code = (
            "import sys; "
            "import solana_alpha_lab.factory.operability_watch; "
            "print('lifecycle=' + str('solana_alpha_lab.factory.observation_schedule_lifecycle' in sys.modules)); "
            "print('research=' + str('solana_alpha_lab.factory.research_store' in sys.modules)); "
            "print('duckdb=' + str('duckdb' in sys.modules))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            result.stdout.splitlines(),
            ["lifecycle=False", "research=False", "duckdb=False"],
        )


if __name__ == "__main__":
    unittest.main()
