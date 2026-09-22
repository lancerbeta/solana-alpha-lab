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
    select_current_activation,
)


class CollectorContinuityBoundaryTests(unittest.TestCase):
    def test_active_selection_prefers_freshest_peer(self) -> None:
        now = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
        rows = [
            {
                "activation_id": "ACT-OLD",
                "state": "ACTIVE",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-NEW",
                "state": "ACTIVE",
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
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-08-31T23:00:00Z",
            },
            {
                "activation_id": "ACT-DRAIN-NEW",
                "state": "DRAINING",
                "updated_at": "2026-09-01T00:05:00Z",
                "created_at": "2026-09-01T00:01:00Z",
            },
        ]
        self.assertEqual(
            select_current_activation(rows, now=now)["activation_id"],
            "ACT-DRAIN-NEW",
        )

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
