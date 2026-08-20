from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.ordinary_market_pit_primary_x import (
    AVAILABILITY_CLASS,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    PRIMARY_X_BOUND,
    PRIMARY_X_UNKNOWN,
    PRODUCT_TERMINAL,
    bind_git_retained_cells,
    bind_primary_x,
    load_bind_config,
)

SCRIPT = ROOT / "scripts/run_ordinary_market_pit_primary_x_bind.py"
FEATURE_CATALOG = ROOT / "registries/feature_catalog.yaml"
HYPOTHESES = ROOT / "registries/hypotheses.yaml"
RESEARCH_CYCLES = ROOT / "registries/research_cycles.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OrdinaryMarketPitPrimaryXBindTests(unittest.TestCase):
    def test_git_retained_cells_cannot_bind_mcap(self) -> None:
        config = load_bind_config(ROOT)
        result = bind_git_retained_cells(ROOT, config)
        self.assertEqual(result["product_terminal"], PRODUCT_TERMINAL)
        self.assertGreater(result["cell_count"], 0)
        self.assertEqual(result["primary_x_bound_count"], 0)
        self.assertEqual(result["primary_x_unknown_count"], result["cell_count"])
        self.assertEqual(result["mcap_key_count"], 0)
        self.assertEqual(result["pit_ready_count"], 0)
        self.assertEqual(result["next_safe_action"], "OWNER_BOUNDED_JUPITER_CAPTURE_WITH_RAW_RETENTION")

    def test_fixture_with_mcap_binds_ratio(self) -> None:
        row = bind_primary_x(
            {"id": "Mint111111111111111111111111111111111111111", "liquidity": 2000.0, "mcap": 10000.0},
            observed_at="2026-08-20T12:00:00Z",
        )
        self.assertEqual(row["status"], PRIMARY_X_BOUND)
        self.assertAlmostEqual(row["value"], 0.2)
        self.assertEqual(row["availability_class"], AVAILABILITY_CLASS)
        self.assertEqual(row["observed_at"], "2026-08-20T12:00:00Z")
        self.assertEqual(row["available_to_strategy_at"], "2026-08-20T12:00:00Z")
        self.assertFalse(row["pit_ready"])

    def test_missing_mcap_is_unknown_not_zero(self) -> None:
        row = bind_primary_x({"id": "Mint", "liquidity": 2287.13}, observed_at=None)
        self.assertEqual(row["status"], PRIMARY_X_UNKNOWN)
        self.assertIsNone(row["value"])
        self.assertNotEqual(row["value"], 0)
        self.assertFalse(row["pit_ready"])

    def test_fdv_is_not_a_mcap_substitute(self) -> None:
        row = bind_primary_x(
            {"id": "Mint", "liquidity": 2000.0, "fdv": 50000.0},
            observed_at=None,
        )
        self.assertEqual(row["status"], PRIMARY_X_UNKNOWN)
        self.assertIsNone(row["value"])
        self.assertTrue(row["substitute_rejected"])

    def test_zero_mcap_is_unknown_not_infinity(self) -> None:
        row = bind_primary_x({"id": "Mint", "liquidity": 2000.0, "mcap": 0}, observed_at=None)
        self.assertEqual(row["status"], PRIMARY_X_UNKNOWN)
        self.assertIsNone(row["value"])

    def test_factory_runner_unchanged(self) -> None:
        self.assertEqual(sha256(ROOT / FACTORY_RUNNER), FACTORY_RUNNER_SHA256)

    def test_cli_reports_cannot_bind_without_network(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["product_terminal"], PRODUCT_TERMINAL)
        self.assertEqual(payload["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(payload["pit_ready_count"], 0)
        self.assertEqual(payload["mcap_key_count"], 0)

    def test_task28_skeletons_stay_empty(self) -> None:
        import yaml

        for path in (FEATURE_CATALOG, HYPOTHESES, RESEARCH_CYCLES):
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["records"], [])


if __name__ == "__main__":
    unittest.main()
