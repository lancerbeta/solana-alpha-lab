from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import validate_catalog as catalog

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task17a_execution_capacity_audit import (  # noqa: E402
    Task17AAuditError,
    audit_panel,
    audit_repaired_panel,
)

CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "bounded_execution_capacity_quote_panel_contract_v1.json"
)
RAW_ROOT = (ROOT / "data" / "raw").resolve()
REPAIR_CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "one_window_timing_repair_contract_v1.json"
)
AUDIT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17a"
    / "execution_capacity_quote_panel_audit_v1.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17a"
    / "execution_capacity_quote_panel_summary_v1.md"
)


class Task17AExecutionCapacityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repaired = audit_repaired_panel(
            raw_root=RAW_ROOT,
            contract_path=CONTRACT_PATH,
            repair_contract_path=REPAIR_CONTRACT_PATH,
        )
        cls.accepted = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

    def test_original_panel_fails_closed_on_exact_timing_shortfall(self) -> None:
        with self.assertRaisesRegex(
            Task17AAuditError, "window_separation_below_minimum"
        ):
            audit_panel(
                raw_root=RAW_ROOT,
                contract_path=CONTRACT_PATH,
            )

    def test_tampered_raw_bytes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            source = (
                RAW_ROOT
                / "task17a_execution_capacity_quote_panel_v1"
            )
            target = raw_root / source.name
            shutil.copytree(source, target)
            raw_path = (
                target
                / "window=T17A-WINDOW-01"
                / "raw_events.jsonl"
            )
            lines = raw_path.read_text(encoding="utf-8").splitlines()
            record = json.loads(lines[0])
            record["member_id"] = "tampered"
            lines[0] = json.dumps(
                record, sort_keys=True, separators=(",", ":")
            )
            raw_path.write_text(
                "\n".join(lines) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                Task17AAuditError, "raw_receipt_hash_mismatch"
            ):
                audit_panel(
                    raw_root=raw_root,
                    contract_path=CONTRACT_PATH,
                )

    def test_repaired_window_set_passes_without_post_hoc_tolerance(self) -> None:
        self.assertEqual(self.repaired["verdict"], "PASS")
        self.assertEqual(
            [window["window_id"] for window in self.repaired["windows"]],
            [
                "T17A-WINDOW-01",
                "T17A-WINDOW-03",
                "T17A-WINDOW-04-REPAIR-01",
            ],
        )
        self.assertEqual(self.repaired["coverage"]["provider_calls"], 24)
        self.assertEqual(
            self.repaired["coverage"]["excluded_provider_calls"], 8
        )
        self.assertEqual(
            self.repaired["authority"]["provider_api_calls"], 32
        )
        self.assertFalse(
            self.repaired["repair"]["post_hoc_tolerance_allowed"]
        )
        self.assertEqual(
            self.repaired["repair"]["excluded_but_retained_window"][
                "trigger_separation_shortfall_seconds"
            ],
            "0.007854",
        )

    def test_repaired_panel_preserves_nonclaims_and_zero_effects(self) -> None:
        claims = self.repaired["claims"]
        self.assertTrue(claims["quote_only_temporal_replication"])
        for name in (
            "cross_token_generalization",
            "data_quality",
            "fillable",
            "realized_vwap",
            "net_return",
            "alpha",
            "signal_or_strategy",
        ):
            self.assertFalse(claims[name])
        authority = self.repaired["authority"]
        self.assertEqual(authority["api_keys"], 0)
        self.assertEqual(authority["accounts"], 0)
        self.assertEqual(authority["cash_spend_usd_cents"], 0)
        self.assertEqual(authority["wallet_signer_transaction_actions"], 0)

    def test_tracked_audit_is_exact_replay_and_summary_is_bounded(self) -> None:
        self.assertEqual(self.accepted, self.repaired)
        summary = SUMMARY_PATH.read_text(encoding="utf-8")
        for value in (
            "PASS_BOUNDED_QUOTE_ONLY_TEMPORAL_REPLICATION",
            "832.5706 bps",
            "0.007854",
            "total provider calls: `32`",
            "data quality",
            "NetReturn",
        ):
            self.assertIn(value, summary)

    def test_catalog_checkpoint_and_actual_assets_are_exact(self) -> None:
        snapshot = catalog.load_and_validate()
        self.assertEqual(snapshot.manifest["catalog_version"], "0.22.0")
        checkpoint = catalog.observed_catalog_checkpoint(snapshot)
        self.assertEqual(checkpoint["assets"], 303)
        self.assertEqual(checkpoint["asset_registries"], 4)
        self.assertEqual(checkpoint["schemas"], 4)
        self.assertEqual(checkpoint["queries"], 8)
        expected = {
            "CONTRACT-T17A-TIMING-REPAIR-001":
                "docs/contracts/task17a_one_window_timing_repair_contract_v1.md",
            "FIXTURE-T17A-TIMING-REPAIR-001":
                "tests/fixtures/task17a/one_window_timing_repair_contract_v1.json",
            "MODULE-T17A-EXECUTION-CAPACITY-PANEL-001":
                "src/solana_alpha_lab/task17a_execution_capacity_panel.py",
            "SCRIPT-T17A-EXECUTION-CAPACITY-PANEL-001":
                "scripts/run_task17a_execution_capacity_panel.py",
            "TEST-T17A-EXECUTION-CAPACITY-PANEL-001":
                "tests/test_task17a_execution_capacity_panel.py",
            "MODULE-T17A-TIMING-REPAIR-001":
                "src/solana_alpha_lab/task17a_timing_repair.py",
            "SCRIPT-T17A-TIMING-REPAIR-001":
                "scripts/run_task17a_timing_repair.py",
            "TEST-T17A-TIMING-REPAIR-001":
                "tests/test_task17a_timing_repair_contract.py",
            "MODULE-T17A-EXECUTION-CAPACITY-AUDIT-001":
                "src/solana_alpha_lab/task17a_execution_capacity_audit.py",
            "SCRIPT-T17A-EXECUTION-CAPACITY-AUDIT-001":
                "scripts/audit_task17a_execution_capacity_panel.py",
            "EVIDENCE-T17A-EXECUTION-CAPACITY-AUDIT-001":
                "docs/evidence/task17a/execution_capacity_quote_panel_audit_v1.json",
            "EVIDENCE-T17A-EXECUTION-CAPACITY-SUMMARY-001":
                "docs/evidence/task17a/execution_capacity_quote_panel_summary_v1.md",
            "TEST-T17A-EXECUTION-CAPACITY-AUDIT-001":
                "tests/test_task17a_execution_capacity_audit.py",
        }
        for asset_id, relative in expected.items():
            with self.subTest(asset_id=asset_id):
                asset = snapshot.assets[asset_id]
                self.assertEqual(
                    asset["location"]["repository_path"], relative
                )
                self.assertEqual(
                    asset["integrity"]["sha256"],
                    __import__("hashlib").sha256(
                        (ROOT / relative).read_bytes()
                    ).hexdigest(),
                )
        raw = snapshot.assets[
            "DATA-T17A-EXECUTION-CAPACITY-RAW-001"
        ]
        self.assertEqual(raw["location"]["kind"], "logical_only")
        self.assertEqual(
            raw["integrity"]["sha256"],
            __import__("hashlib").sha256(AUDIT_PATH.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
