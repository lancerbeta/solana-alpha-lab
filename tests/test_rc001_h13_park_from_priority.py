from __future__ import annotations

import shutil
import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import solana_alpha_lab.rc001_h13_park_from_priority as h13_park  # noqa: E402
from solana_alpha_lab.rc001_h13_park_from_priority import (  # noqa: E402
    ATOM_ID,
    FORBIDDEN_FOLLOW_ONS,
    H13ParkError,
    RETURN_TRIGGER,
    TERMINAL_OUTCOMES,
    bind_h13_park_from_priority,
    decide_park_terminal,
    format_owner_readout,
)

CONTRACT_PATH = ROOT / "docs/tasks/RC001-H13-PARK-FROM-PRIORITY-OFFLINE-V1.md"
ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/rc001_h13_park_from_priority/"
    "a1_h13_park_from_priority_acceptance_v1.json"
)
READOUT_PATH = ROOT / (
    "docs/reports/rc001_h13_park_from_priority/a1_owner_readout_v1.md"
)
REGISTRY_PATH = ROOT / "registries/decisions_negative_results.yaml"
TRIAL_LEDGER_PATH = ROOT / "registries/global_trial_ledger.yaml"
CORE_CATALOG_PATH = ROOT / "catalog/assets/core.yaml"
MODULE_PATH = ROOT / "src/solana_alpha_lab/rc001_h13_park_from_priority.py"
RUNNER_PATH = ROOT / "scripts/run_rc001_h13_park_from_priority.py"


class H13ParkFromPriorityTests(unittest.TestCase):
    def test_contract_binds_offline_park_scope(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: RC001-H13-PARK-FROM-PRIORITY-OFFLINE-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("H13_PARKED_FROM_PRIORITY_SCIENCE_RETAINED", text)
        self.assertIn("H13_PARK_PREREQUISITES_DRIFT", text)
        self.assertIn("OWNER_CAPTURE=PARK_H13_FROM_PRIORITY", text)
        self.assertIn("H02/H10/H14 remains `BLOCKED_DATA`", text)
        self.assertEqual(ATOM_ID, "RC001-H13-PARK-FROM-PRIORITY-OFFLINE-V1")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "H13_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
                "H13_PARK_PREREQUISITES_DRIFT",
            ),
        )

    def test_binder_parks_h13_and_does_not_start_h02(self) -> None:
        result = bind_h13_park_from_priority(ROOT)
        self.assertEqual(result["terminal"], "H13_PARKED_FROM_PRIORITY_SCIENCE_RETAINED")
        self.assertEqual(result["owner_decision"], "PARK_H13_FROM_PRIORITY")
        self.assertEqual(result["priority_disposition"], "PARKED_FROM_PRIORITY")
        self.assertEqual(result["science_disposition"], "RETAINED")
        self.assertFalse(result["deletion"])
        self.assertEqual(result["hypothesis_verdict"], "NOT_REFUTED_NOT_SUPPORTED")
        self.assertEqual(result["h13_state"], "BLOCKED_DATA")
        self.assertEqual(
            result["h13_blocker_codes"],
            [
                "ENTITY_ROUTE_NOT_ADMISSIBLE",
                "CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE",
                "SETTLED_EXECUTION_TRUTH_UNAVAILABLE",
            ],
        )
        self.assertEqual(
            result["h07_h01_park_decision"],
            "RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
        )
        self.assertEqual(result["h02_state"], "BLOCKED_DATA")
        self.assertFalse(result["h02_started"])
        self.assertEqual(result["next_family_selection"], "NONE_THIS_ATOM")
        self.assertEqual(result["trial_ledger"]["rc001_trial_record_ids"], [])
        self.assertEqual(
            result["trial_ledger"]["sha256"],
            hashlib.sha256(TRIAL_LEDGER_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(result["trial_ledger"]["as_of"], "2026-08-15")
        self.assertEqual(
            result["return_prerequisites"]["group_id"],
            "RC001-H13-COMPOSITE-VETO",
        )
        self.assertEqual(
            result["return_prerequisites"]["definition_sha256"],
            "f1f020f4fa79acd2f2de667d71b8002d5821f45e9070a0f259c63210b23a16d0",
        )
        self.assertEqual(
            result["return_prerequisites"]["unresolved_blocker_codes"],
            [
                "ENTITY_ROUTE_NOT_ADMISSIBLE",
                "CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE",
                "SETTLED_EXECUTION_TRUTH_UNAVAILABLE",
            ],
        )
        self.assertEqual(result["return_trigger"], RETURN_TRIGGER)
        self.assertEqual(result["forbidden_follow_ons"], list(FORBIDDEN_FOLLOW_ONS))
        self.assertEqual(result["side_effects"]["provider_requests"], 0)
        self.assertEqual(result["side_effects"]["credential_reads"], 0)
        self.assertEqual(result["side_effects"]["cash_spend_usd_cents"], 0)
        self.assertEqual(result["side_effects"]["network_requests"], 0)
        self.assertEqual(result["side_effects"]["wallet_signer_transaction_actions"], 0)
        self.assertEqual(result["side_effects"]["execution_attempts"], 0)

    def test_decision_drift_fails_closed(self) -> None:
        result = dict(bind_h13_park_from_priority(ROOT))
        result["h13_blocker_codes"] = []
        self.assertEqual(
            decide_park_terminal(result),
            "H13_PARK_PREREQUISITES_DRIFT",
        )
        result = dict(bind_h13_park_from_priority(ROOT))
        result["side_effects"] = dict(result["side_effects"], network_requests=1)
        self.assertEqual(
            decide_park_terminal(result),
            "H13_PARK_PREREQUISITES_DRIFT",
        )

    def test_pinned_task24_hash_drift_fails_closed(self) -> None:
        original = h13_park.TASK24_STOP_SHA256
        try:
            h13_park.TASK24_STOP_SHA256 = "0" * 64
            with self.assertRaisesRegex(H13ParkError, "TASK24_STOP_RECEIPT_DRIFT"):
                bind_h13_park_from_priority(ROOT)
        finally:
            h13_park.TASK24_STOP_SHA256 = original

    def test_current_rc001_trial_fails_closed(self) -> None:
        source_paths = (
            ROOT / h13_park.TASK24_STOP_RELATIVE,
            ROOT / h13_park.TASK28_ACCEPTANCE_RELATIVE,
            ROOT / h13_park.TASK28_FREEZE_RELATIVE,
            ROOT / h13_park.H07_H01_PARK_RELATIVE,
            TRIAL_LEDGER_PATH,
        )
        with tempfile.TemporaryDirectory() as directory:
            copied_root = Path(directory)
            for source in source_paths:
                target = copied_root / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            ledger_path = copied_root / TRIAL_LEDGER_PATH.relative_to(ROOT)
            ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
            ledger["records"].append(
                {
                    "record_kind": "trial",
                    "record_id": "TRIAL-RC001-H13-SYNTHETIC-001",
                    "status": "RECORDED",
                    "created_at": "2026-08-18T00:00:00Z",
                    "evidence_asset_ids": [],
                    "hypothesis_id": "DEF-RC001-H13-COMPOSITE-VETO-V1",
                    "outcome": "INCONCLUSIVE",
                }
            )
            ledger_path.write_text(
                yaml.safe_dump(ledger, sort_keys=False),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(H13ParkError, "RC001_TRIAL_RECORD_FORBIDDEN"):
                bind_h13_park_from_priority(copied_root)

    def test_owner_readout_preserves_park_boundary(self) -> None:
        result = bind_h13_park_from_priority(ROOT)
        readout = format_owner_readout(result)
        self.assertIn("H13 паркуем", readout)
        self.assertIn("H13_PARKED_FROM_PRIORITY_SCIENCE_RETAINED", readout)
        self.assertIn("не опровержение гипотезы", readout)
        self.assertIn("H02/H10/H14 автоматически не стартует", readout)
        self.assertIn("BLOCKED_DATA", readout)
        self.assertIn("ENTITY_ROUTE_NOT_ADMISSIBLE", readout)
        self.assertNotIn("None", readout)

    def test_module_and_runner_have_static_offline_boundary(self) -> None:
        source = (
            MODULE_PATH.read_text(encoding="utf-8")
            + "\n"
            + RUNNER_PATH.read_text(encoding="utf-8")
        )
        for forbidden in (
            "import urllib.request",
            "import httpx",
            "import requests",
            "socket.create_connection",
            "from solana.rpc",
        ):
            self.assertNotIn(forbidden, source)

    def test_generated_acceptance_and_readout_match_binder(self) -> None:
        result = bind_h13_park_from_priority(ROOT)
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        for key, value in result.items():
            self.assertEqual(acceptance[key], value)
        self.assertEqual(
            acceptance["non_claims"],
            [
                "NO_RC001_FREEZE_MUTATION",
                "NO_H13_OR_H02_TRIAL",
                "NO_ENTITY_ROUTE_REDESIGN_OR_CAPTURE",
                "NO_CONTINUOUS_PIT_OR_EXECUTION_CAPTURE",
                "NO_H07_H01_UNPARK",
                "NO_HYPOTHESIS_NEGATIVE_OR_POSITIVE_INFERENCE",
                "NO_ALPHA_NETRETURN_OR_CASHFLOW",
                "NO_CANONICAL_DONE",
            ],
        )
        self.assertEqual(acceptance["terminal"], result["terminal"])
        self.assertEqual(acceptance["owner_decision"], "PARK_H13_FROM_PRIORITY")
        self.assertEqual(
            acceptance["h07_h01_park_decision"],
            "RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
        )
        self.assertEqual(acceptance["next_family_selection"], "NONE_THIS_ATOM")
        self.assertEqual(acceptance["return_trigger"], RETURN_TRIGGER)
        self.assertEqual(
            acceptance["return_prerequisites"], result["return_prerequisites"]
        )
        self.assertEqual(
            acceptance["forbidden_follow_ons"], list(FORBIDDEN_FOLLOW_ONS)
        )
        self.assertEqual(acceptance["trial_ledger"], result["trial_ledger"])
        self.assertEqual(acceptance["side_effects"], result["side_effects"])
        self.assertEqual(READOUT_PATH.read_text(encoding="utf-8"), format_owner_readout(result))

    def test_registry_and_catalog_register_the_park_decision(self) -> None:
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        record = next(
            item
            for item in registry["records"]
            if item["record_id"] == "DECISION-RC001-H13-PARK-FROM-PRIORITY-001"
        )
        self.assertEqual(record["record_kind"], "decision")
        self.assertEqual(
            record["evidence_asset_ids"],
            ["EVIDENCE-RC001-H13-PARK-FROM-PRIORITY-001"],
        )
        core_catalog = CORE_CATALOG_PATH.read_text(encoding="utf-8")
        for asset_id in (
            "EVIDENCE-RC001-H13-PARK-FROM-PRIORITY-001",
            "REPORT-RC001-H13-PARK-FROM-PRIORITY-001",
            "CTRL-RC001-H13-PARK-FROM-PRIORITY-001",
            "MODULE-RC001-H13-PARK-FROM-PRIORITY-001",
            "SCRIPT-RC001-H13-PARK-FROM-PRIORITY-001",
            "TEST-RC001-H13-PARK-FROM-PRIORITY-001",
        ):
            self.assertIn(f"asset_id: {asset_id}", core_catalog)


if __name__ == "__main__":
    unittest.main()
