from __future__ import annotations

import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

BASE = "c795952e166a2c5f0f5c967b84ee6457c3b0dc80"
PINNED = (
    "src/solana_alpha_lab/factory/early_icp_first_hit_mix_falsifier.py",
    "configs/early_icp_first_hit_mix_falsifier_v1.yaml",
    "scripts/run_early_icp_first_hit_mix_falsifier.py",
    "src/solana_alpha_lab/factory/forward_h900_quote_capture.py",
    "configs/forward_h900_quote_capture_v1.yaml",
    "configs/provider_route_capability_registry_v10.yaml",
    "configs/factory_remote_operations_v1.yaml",
    "catalog/schemas/factory_remote_operations.schema.json",
    "configs/experiment_capability_registry_v1.yaml",
)


class ObservationScheduleArtifactPinTests(unittest.TestCase):
    def test_completed_v2_sleep_and_pr211_bytes_unchanged(self) -> None:
        for relative in PINNED:
            expected = subprocess.check_output(
                ["git", "show", f"{BASE}:{relative}"],
                cwd=ROOT,
            )
            actual = (ROOT / relative).read_bytes()
            self.assertEqual(
                hashlib.sha256(actual).hexdigest(),
                hashlib.sha256(expected).hexdigest(),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
