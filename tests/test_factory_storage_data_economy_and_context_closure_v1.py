"""Semantic closure proofs for storage/data-economy and Collector runbook."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "delivery-harness" / "policies" / "solana-alpha-lab.md"
RUNBOOK = ROOT / "docs" / "operator" / "FACTORY_LIFECYCLE_COLLECTOR.md"
BASELINE = (
    ROOT
    / "docs"
    / "evidence"
    / "factory_storage_data_economy_and_context_closure_v1"
    / "a1_storage_baseline_v1.json"
)
UNIT = ROOT / "configs" / "factory_remote_ops" / "factory-observation-schedule.service"


class FactoryStorageDataEconomyClosureTests(unittest.TestCase):
    def test_data_resolution_economy_is_policy_not_granularity_ban(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        self.assertIn("## DATA_AND_RESEARCH_TRUTH", policy)
        self.assertIn("Historical/reusable cache first", policy)
        self.assertIn("DATA_RESOLUTION_ECONOMY", policy)
        self.assertIn("minimum temporal and detail", policy)
        self.assertIn("tick, quote, or microstructure", policy)
        self.assertIn("PIT availability", policy)
        self.assertIn("executable quote truth", policy)
        self.assertNotIn("1m candles only", policy)
        self.assertNotIn("1-minute candles only", policy)
        self.assertNotRegex(policy, r"(?i)candles only")

    def test_runbook_does_not_auto_route_restore_or_reclaim(self) -> None:
        runbook = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("LEGACY_FULL_RECLAIM_FAIL", runbook)
        self.assertIn(
            "RECLAIM_EFFECTIVE / ACCEPTANCE_FALSE_NEGATIVE_CONCURRENT_PUBLICATION",
            runbook,
        )
        self.assertIn(
            "OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_LIVE_PASS",
            runbook,
        )
        self.assertIn("NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF_PASS", runbook)
        self.assertIn("EnvironmentFile=-/etc/solana-alpha-lab/secrets.env", runbook)
        self.assertIn("CREDENTIAL_ENV_MISSING", runbook)
        self.assertIn("sudo systemctl start factory-observation-schedule.service", runbook)
        self.assertNotIn(
            "Next separate atom after live PASS: NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF",
            runbook,
        )
        self.assertNotIn(
            "Required live proof terminal: `NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF_PASS`.",
            runbook,
        )
        self.assertIn("historically proven", runbook)
        self.assertIn("never a default NEXT", runbook)

    def test_production_unit_still_carries_environmentfile(self) -> None:
        unit = UNIT.read_text(encoding="utf-8")
        self.assertIn("EnvironmentFile=-/etc/solana-alpha-lab/secrets.env", unit)
        self.assertNotIn("User=", unit)

    def test_storage_baseline_is_compact_and_honest(self) -> None:
        payload = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(payload["reclaim_disposition"]["machine_terminal"], "LEGACY_FULL_RECLAIM_FAIL")
        self.assertFalse(payload["reclaim_repeated"])
        self.assertFalse(payload["retention_apply"])
        self.assertEqual(payload["retention"]["decision"], "RETENTION_NO_ACTION_YET")
        self.assertEqual(
            payload["storage_architecture_terminal"],
            "NO_STORAGE_ARCHITECTURE_CHANGE_REQUIRED",
        )
        self.assertEqual(payload["projections"]["30d"]["status"], "UNKNOWN")
        self.assertEqual(payload["projections"]["90d"]["status"], "UNKNOWN")
        self.assertEqual(payload["collector_storage_history"]["status"], "HISTORY_ABSENT")
        self.assertEqual(payload["publication_jobs"]["legacy_full_count"], 0)
        self.assertEqual(payload["publication_jobs"]["legacy_full_bytes"], 0)
        self.assertNotIn("secrets", json.dumps(payload).lower())


if __name__ == "__main__":
    unittest.main()
