from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pmf_quote_stay_overlay import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    CONFIRMATORY_TERMINAL,
    EXPECTED_CONFIRMATORY_ACCEPTANCE_SHA256,
    EXPECTED_HOP1,
    EXPECTED_OWNER_FORK_ACCEPTANCE_SHA256,
    EXPECTED_OUTPUT_MINT,
    EXPECTED_ROUTE_ID,
    FORBIDDEN_FOLLOW_ONS,
    OWNER_FORK_TERMINAL,
    REMAINING_UNPAID_OWNER_PHRASES,
    TERMINAL_OUTCOMES,
    bind_pmf_quote_stay_overlay,
    decide_stay_overlay_terminal,
    format_owner_readout,
)

CONTRACT_PATH = ROOT / "docs/tasks/PMF-QUOTE-STAY-OVERLAY-V1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/pmf_quote_stay_overlay.py"
CONFIG_PATH = ROOT / "configs/pmf_quote_stay_overlay_v1.yaml"
ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/pmf_quote_slice/a1_pmf_quote_stay_overlay_acceptance_v1.json"
)
READOUT_PATH = ROOT / "docs/reports/pmf_quote_slice/a1_stay_overlay_owner_readout_v1.md"
V6 = ROOT / "configs/provider_route_capability_registry_v6.yaml"
V7 = ROOT / "configs/provider_route_capability_registry_v7.yaml"
RC001_FREEZE = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
TRIAL_LEDGER = ROOT / "registries/global_trial_ledger.yaml"


class PmfQuoteStayOverlayTests(unittest.TestCase):
    def test_contract_names_caps_and_stops(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: PMF-QUOTE-STAY-OVERLAY-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("credentials: false", text)
        self.assertIn("QUOTE_STAY_OVERLAY_BOUND_SCREENING_EXHAUSTED", text)
        self.assertIn(
            "OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-STAY-OVERLAY: accept Touch/Fillable/fees not evidenced",
            text,
        )
        self.assertIn("WRAP_OWNER_FORK_AND_CONFIRMATORY_CLOSE_NO_PROVIDER", text)
        self.assertIn("FILLABLE_NAMED_KEEP_ON_QUOTE_ONLY", text)
        self.assertIn("QUOTE_ONLY_KEEP_SCREENING_REOPENED", text)
        self.assertIn("PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE", text)
        self.assertIn("ROADMAP_VERDICT=REBASE", text)
        self.assertIn("SPEC_ROUTE=BOTH", text)
        self.assertIn("DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK", text)
        self.assertNotIn("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", text)
        self.assertEqual(AUTHORITY_PHRASE, (
            "OK PMF-QUOTE-STAY-OVERLAY: accept Touch/Fillable/fees not evidenced"
        ))
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "QUOTE_STAY_OVERLAY_BOUND_SCREENING_EXHAUSTED",
                "QUOTE_STAY_OVERLAY_PREREQUISITES_DRIFT",
            ),
        )
        write_set = text.split("managed_write_set:")[1].split("external_caps:")[0]
        self.assertNotIn("provider_route_capability_registry_v6.yaml", write_set)
        self.assertNotIn("provider_route_capability_registry_v7.yaml", write_set)
        self.assertNotIn("task28_rc001_registry_freeze_v1.yaml", write_set)
        self.assertNotIn("global_trial_ledger.yaml", write_set)
        self.assertTrue(V6.is_file())
        self.assertTrue(V7.is_file())
        self.assertTrue(RC001_FREEZE.is_file())
        self.assertTrue(TRIAL_LEDGER.is_file())
        front_matter = text.split("---", 2)[1]
        parsed = yaml.safe_load(front_matter)
        self.assertEqual(parsed["task_id"], ATOM_ID)
        self.assertEqual(
            parsed["context_requirements"]["catalog_asset_ids"],
            [
                "EVIDENCE-PMF-QUOTE-OWNER-FORK-ACCEPTANCE-001",
                "EVIDENCE-QUOTE-SURFACE-RETENTION-CONFIRMATORY-ACCEPTANCE-001",
            ],
        )

    def test_module_does_not_open_network_or_execute(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import urllib", source)
        self.assertNotIn("import http.client", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("import ssl", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("JUPITER_API_KEY", source)
        self.assertIn('"execute": "FORBIDDEN"', source)
        self.assertIn('"execute_phrase_status": "INELIGIBLE"', source)
        self.assertIn("FILLABLE_NAMED_KEEP_ON_QUOTE_ONLY", source)

    def test_git_prerequisites_bind_stay_overlay(self) -> None:
        result = bind_pmf_quote_stay_overlay(ROOT)
        self.assertEqual(result["terminal"], "QUOTE_STAY_OVERLAY_BOUND_SCREENING_EXHAUSTED")
        self.assertEqual(result["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(result["route_id"], EXPECTED_ROUTE_ID)
        self.assertEqual(result["output_mint"], EXPECTED_OUTPUT_MINT)
        self.assertEqual(
            result["owner_fork_acceptance_sha256"],
            EXPECTED_OWNER_FORK_ACCEPTANCE_SHA256,
        )
        self.assertEqual(
            result["confirmatory_acceptance_sha256"],
            EXPECTED_CONFIRMATORY_ACCEPTANCE_SHA256,
        )
        self.assertEqual(result["owner_fork_terminal"], OWNER_FORK_TERMINAL)
        self.assertEqual(
            result["confirmatory_scientific_terminal"], CONFIRMATORY_TERMINAL
        )
        self.assertEqual(result["quote_only_keep_screening"], "EXHAUSTED")
        self.assertEqual(result["fillable_named_keep_on_quote_only"], "FORBIDDEN")
        self.assertEqual(result["quoted_path_quality_6_plus_6"], "NOT_AUTHORIZED")
        self.assertEqual(result["touch_fact_status"], "UNPAID_NOT_STARTED")
        self.assertFalse(result["factory_v1_operational_ready"])
        self.assertFalse(result["atom_2"])
        self.assertEqual(result["missing_facts"]["touch"]["state"], "NOT_EVIDENCED")
        self.assertEqual(result["missing_facts"]["fillable"]["state"], "NOT_EVIDENCED")
        self.assertEqual(result["missing_facts"]["fees"]["state"], "NOT_COMPUTABLE")
        self.assertEqual(result["design_probe"]["buy_h900_hop_count_eq_1"], EXPECTED_HOP1)
        self.assertEqual(result["design_probe"]["y_path_risk_true_n"], 0)
        self.assertFalse(result["design_probe"]["science"])
        self.assertEqual(result["execute"], "FORBIDDEN")
        self.assertEqual(result["provider_requests"], 0)
        self.assertEqual(
            result["remaining_unpaid_owner_phrases"],
            list(REMAINING_UNPAID_OWNER_PHRASES),
        )
        self.assertNotIn(AUTHORITY_PHRASE, result["remaining_unpaid_owner_phrases"])
        self.assertEqual(result["forbidden_follow_ons"], list(FORBIDDEN_FOLLOW_ONS))
        drifted = dict(result)
        drifted["fillable_named_keep_on_quote_only"] = "ALLOWED"
        self.assertEqual(
            decide_stay_overlay_terminal(drifted),
            "QUOTE_STAY_OVERLAY_PREREQUISITES_DRIFT",
        )
        offered = dict(result)
        offered["remaining_unpaid_owner_phrases"] = [
            "OK PMF-QUOTE-EXECUTE: authorize /execute"
        ]
        self.assertEqual(
            decide_stay_overlay_terminal(offered),
            "QUOTE_STAY_OVERLAY_PREREQUISITES_DRIFT",
        )

    def test_acceptance_and_readout_match_binder(self) -> None:
        result = bind_pmf_quote_stay_overlay(ROOT)
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["terminal"], result["terminal"])
        self.assertEqual(acceptance["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(acceptance["quote_only_keep_screening"], "EXHAUSTED")
        self.assertEqual(
            acceptance["missing_facts"]["fillable"]["state"], "NOT_EVIDENCED"
        )
        self.assertFalse(acceptance["execution_claim"])
        self.assertFalse(acceptance["factory_v1_operational_ready"])
        readout = READOUT_PATH.read_text(encoding="utf-8")
        self.assertEqual(readout, format_owner_readout(result))
        self.assertIn("QUOTE_STAY_OVERLAY_BOUND_SCREENING_EXHAUSTED", readout)
        self.assertIn(AUTHORITY_PHRASE, readout)
        self.assertIn("Fillable", readout)
        self.assertIn("EXHAUSTED", readout)
        self.assertIn("OK PMF-QUOTE-TOUCH-FACT", readout)
        self.assertNotIn("POPCAT", readout)


if __name__ == "__main__":
    unittest.main()
