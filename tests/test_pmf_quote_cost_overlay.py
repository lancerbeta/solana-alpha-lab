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

from solana_alpha_lab.pmf_quote_cost_overlay import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    EXPECTED_ACCEPTANCE_SHA256,
    EXPECTED_INPUT_MINT,
    EXPECTED_NOTIONAL,
    EXPECTED_OUTPUT_MINT,
    EXPECTED_RECEIPT_SHA256,
    EXPECTED_ROUTE_ID,
    EXPECTED_TASK26_CONTRACT_SHA256,
    FORBIDDEN_FOLLOW_ONS,
    TERMINAL_OUTCOMES,
    bind_pmf_quote_cost_overlay,
    decide_overlay_terminal,
    format_owner_readout,
)

CONTRACT_PATH = ROOT / "docs/tasks/PMF-QUOTE-COST-OVERLAY-V1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/pmf_quote_cost_overlay.py"
CONFIG_PATH = ROOT / "configs/pmf_quote_cost_overlay_v1.yaml"
ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/pmf_quote_slice/a1_pmf_quote_cost_overlay_acceptance_v1.json"
)
READOUT_PATH = ROOT / "docs/reports/pmf_quote_slice/a1_cost_overlay_owner_readout_v1.md"
V6 = ROOT / "configs/provider_route_capability_registry_v6.yaml"
V7 = ROOT / "configs/provider_route_capability_registry_v7.yaml"
RC001_FREEZE = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
TRIAL_LEDGER = ROOT / "registries/global_trial_ledger.yaml"


class PmfQuoteCostOverlayTests(unittest.TestCase):
    def test_contract_names_caps_and_stops(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: PMF-QUOTE-COST-OVERLAY-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("credentials: false", text)
        self.assertIn("QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED", text)
        self.assertIn(
            "OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-COST-OVERLAY: consume one-shot receipt only, no execute",
            text,
        )
        self.assertIn("WRAP_TASK26_LAYER_VOCABULARY_OVER_ONE_SHOT_RECEIPT", text)
        self.assertIn("PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE", text)
        self.assertIn("MISSING_FEE_TREATED_AS_ZERO", text)
        self.assertIn("JUPITER_EXECUTE_OR_BUILD", text)
        self.assertIn("DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK", text)
        self.assertNotIn("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", text)
        self.assertEqual(AUTHORITY_PHRASE, (
            "OK PMF-QUOTE-COST-OVERLAY: consume one-shot receipt only, no execute"
        ))
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED",
                "QUOTE_COST_OVERLAY_PREREQUISITES_DRIFT",
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
            ["EVIDENCE-PMF-QUOTE-SLICE-ONE-SHOT-001"],
        )

    def test_module_does_not_open_network_or_execute(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import urllib", source)
        self.assertNotIn("import http.client", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("import ssl", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("JUPITER_API_KEY", source)
        self.assertNotIn("local/pmf_quote_slice_one_shot", source)
        self.assertIn('"execute": "FORBIDDEN"', source)

    def test_git_prerequisites_bind_overlay(self) -> None:
        result = bind_pmf_quote_cost_overlay(ROOT)
        self.assertEqual(
            result["terminal"],
            "QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED",
        )
        self.assertEqual(result["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(result["route_id"], EXPECTED_ROUTE_ID)
        self.assertEqual(result["output_mint"], EXPECTED_OUTPUT_MINT)
        self.assertEqual(result["input_mint"], EXPECTED_INPUT_MINT)
        self.assertEqual(result["notional_atomic"], EXPECTED_NOTIONAL)
        self.assertEqual(result["one_shot_receipt_sha256"], EXPECTED_RECEIPT_SHA256)
        self.assertEqual(
            result["one_shot_acceptance_sha256"], EXPECTED_ACCEPTANCE_SHA256
        )
        self.assertEqual(
            result["task26_contract_sha256"], EXPECTED_TASK26_CONTRACT_SHA256
        )
        self.assertEqual(result["layers"]["quote"]["state"], "OBSERVED")
        self.assertEqual(result["layers"]["touch"]["state"], "NOT_EVIDENCED")
        self.assertEqual(result["layers"]["fillable"]["state"], "NOT_EVIDENCED")
        self.assertEqual(result["layers"]["realized_vwap"]["state"], "NOT_EVIDENCED")
        self.assertEqual(result["layers"]["fees"]["state"], "NOT_COMPUTABLE")
        self.assertTrue(result["layers"]["fees"]["missing_is_not_zero"])
        self.assertEqual(result["layers"]["netreturn"]["state"], "NOT_COMPUTABLE")
        self.assertEqual(result["execute"], "FORBIDDEN")
        self.assertEqual(result["provider_requests"], 0)
        self.assertEqual(result["credential_reads"], 0)
        self.assertFalse(result["local_raw_used_as_git_truth"])
        self.assertFalse(result["transaction_present"])
        self.assertEqual(result["observed_out_amount"], "9010943976")
        self.assertEqual(result["observed_at"], "2026-08-17T02:38:46Z")
        self.assertEqual(result["slippage_bps"], 100)
        self.assertEqual(result["forbidden_follow_ons"], list(FORBIDDEN_FOLLOW_ONS))
        self.assertFalse(result["h13_or_h02_started"])
        self.assertFalse(result["h11_unparked"])
        drifted = dict(result)
        drifted["layers"] = dict(result["layers"])
        drifted["layers"]["fillable"] = {
            "state": "EVIDENCED",
            "reason": "PROMOTED_FROM_QUOTE",
        }
        self.assertEqual(
            decide_overlay_terminal(drifted),
            "QUOTE_COST_OVERLAY_PREREQUISITES_DRIFT",
        )
        zero_fees = dict(result)
        zero_fees["layers"] = dict(result["layers"])
        zero_fees["layers"]["fees"] = {
            "state": "NOT_COMPUTABLE",
            "reason": "SANITIZED_RECEIPT_HAS_NO_FEE_COMPONENTS",
            "missing_is_not_zero": False,
        }
        self.assertEqual(
            decide_overlay_terminal(zero_fees),
            "QUOTE_COST_OVERLAY_PREREQUISITES_DRIFT",
        )

    def test_acceptance_and_readout_match_binder(self) -> None:
        result = bind_pmf_quote_cost_overlay(ROOT)
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["terminal"], result["terminal"])
        self.assertEqual(acceptance["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(acceptance["layers"]["fillable"]["state"], "NOT_EVIDENCED")
        self.assertTrue(acceptance["layers"]["fees"]["missing_is_not_zero"])
        self.assertFalse(acceptance["execution_claim"])
        self.assertFalse(acceptance["live_PIT_claim"])
        self.assertEqual(acceptance["observed_at"], "2026-08-17T02:38:46Z")
        readout = READOUT_PATH.read_text(encoding="utf-8")
        self.assertEqual(readout, format_owner_readout(result))
        self.assertIn("QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED", readout)
        self.assertIn(AUTHORITY_PHRASE, readout)
        self.assertIn("Fillable", readout)
        self.assertIn("отсутствие не есть ноль", readout)
        self.assertIn("observed_at", readout)
        self.assertIn("Можно ли execute?", readout)
        self.assertNotIn("POPCAT", readout)
