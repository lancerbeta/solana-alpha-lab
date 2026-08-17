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

from solana_alpha_lab.pmf_quote_slice import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    EXPECTED_A24_SHA256,
    EXPECTED_A26_SHA256,
    EXPECTED_ENDPOINT,
    EXPECTED_H11_PARK_SHA256,
    EXPECTED_INPUT_MINT,
    EXPECTED_LIVE_REGISTRY_SHA256,
    EXPECTED_NOTIONAL,
    EXPECTED_OUTPUT_MINT,
    EXPECTED_POOL,
    FORBIDDEN_FOLLOW_ONS,
    INTENDED_ROUTE_ID,
    NEXT_OWNER_PHRASE,
    TERMINAL_OUTCOMES,
    bind_pmf_quote_slice,
    decide_slice_terminal,
    format_owner_readout,
)
from solana_alpha_lab.provider_route_capability_registry import (  # noqa: E402
    ProviderRouteRegistryError,
)
from solana_alpha_lab.provider_route_capability_registry_v6 import (  # noqa: E402
    resolve_provider_route_v6,
)

CONTRACT_PATH = ROOT / "docs/tasks/PMF-QUOTE-SLICE-OFFLINE-V1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/pmf_quote_slice.py"
CONFIG_PATH = ROOT / "configs/pmf_quote_slice_v1.yaml"
ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_acceptance_v1.json"
)
READOUT_PATH = ROOT / "docs/reports/pmf_quote_slice/a1_owner_readout_v1.md"
REGISTRY_PATH = ROOT / "configs/provider_route_capability_registry_v6.yaml"
A26_PATH = ROOT / (
    "docs/evidence/task30/a26_h07_h01_owner_fork_packet_acceptance_v1.json"
)
METIS_LOGGER = ROOT / "src/solana_alpha_lab/jupiter_quote_logger.py"
RC001_FREEZE = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
TRIAL_LEDGER = ROOT / "registries/global_trial_ledger.yaml"


class PmfQuoteSliceTests(unittest.TestCase):
    def test_contract_names_caps_and_stops(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: PMF-QUOTE-SLICE-OFFLINE-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("credentials: false", text)
        self.assertIn("PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED", text)
        self.assertIn("OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-SLICE", text)
        self.assertIn("ADOPT_JUPITER_SWAP_V2_ORDER_QUOTE_ONLY", text)
        self.assertIn("FAKE_OBSERVED_REGISTRY_ROW", text)
        self.assertIn("JUPITER_EXECUTE_OR_BUILD", text)
        self.assertIn("H13_OR_H02_TRIAL_STARTED", text)
        self.assertIn("H11_UNPARK_OR_SAMPLE_CAMPAIGN", text)
        self.assertIn("DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK", text)
        self.assertNotIn("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", text)
        self.assertEqual(AUTHORITY_PHRASE, "OK PMF-QUOTE-SLICE")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED",
                "PMF_QUOTE_SLICE_PREREQUISITES_DRIFT",
            ),
        )
        write_set = text.split("managed_write_set:")[1].split("external_caps:")[0]
        self.assertNotIn("provider_route_capability_registry_v6.yaml", write_set)
        self.assertNotIn("task28_rc001_registry_freeze_v1.yaml", write_set)
        self.assertNotIn("global_trial_ledger.yaml", write_set)
        self.assertNotIn("jupiter_quote_logger.py", write_set)
        self.assertTrue(RC001_FREEZE.is_file())
        self.assertTrue(TRIAL_LEDGER.is_file())
        front_matter = text.split("---", 2)[1]
        parsed = yaml.safe_load(front_matter)
        self.assertEqual(parsed["task_id"], ATOM_ID)
        self.assertEqual(
            parsed["context_requirements"]["catalog_asset_ids"],
            ["EVIDENCE-PMF-QUOTE-SLICE-001"],
        )

    def test_module_does_not_open_network_or_execute(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import urllib", source)
        self.assertNotIn("import http.client", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("/execute", source)
        self.assertNotIn("JUPITER_API_KEY", source)
        logger = METIS_LOGGER.read_text(encoding="utf-8")
        self.assertIn('PROVIDER = "JUPITER_METIS"', logger)
        self.assertIn("NETWORK_ENABLED = False", logger)

    def test_live_registry_keeps_jupiter_as_gap(self) -> None:
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ProviderRouteRegistryError, "REGISTRY_GAP"):
            resolve_provider_route_v6(registry, INTENDED_ROUTE_ID)
        a26 = json.loads(A26_PATH.read_text(encoding="utf-8"))
        self.assertFalse(a26["registries"]["jupiter_or_quote_route_present"])
        self.assertEqual(
            a26["registries"]["route_feasibility_registry_status"],
            "REGISTRY_GAP",
        )

    def test_git_prerequisites_bind_quote_slice(self) -> None:
        result = bind_pmf_quote_slice(ROOT)
        self.assertEqual(
            result["terminal"], "PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED"
        )
        self.assertEqual(result["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(result["intended_route_id"], INTENDED_ROUTE_ID)
        self.assertEqual(result["live_registry_status"], "REGISTRY_GAP")
        self.assertEqual(
            result["live_registry_sha256"], EXPECTED_LIVE_REGISTRY_SHA256
        )
        self.assertEqual(result["a26_acceptance_sha256"], EXPECTED_A26_SHA256)
        self.assertFalse(result["a26_jupiter_or_quote_route_present"])
        self.assertEqual(result["output_mint"], EXPECTED_OUTPUT_MINT)
        self.assertEqual(result["input_mint"], EXPECTED_INPUT_MINT)
        self.assertEqual(result["pool_address"], EXPECTED_POOL)
        self.assertEqual(result["pair"], "SOL_TO_A24_BASE_MINT")
        self.assertEqual(result["notional_atomic"], EXPECTED_NOTIONAL)
        self.assertEqual(
            result["notional_parameter_id"], "PMF_QUOTE_SLICE_NOTIONAL_V1"
        )
        self.assertEqual(result["taker"], "OMITTED_QUOTE_ONLY")
        self.assertEqual(result["execute"], "FORBIDDEN")
        self.assertEqual(result["build"], "FORBIDDEN")
        self.assertFalse(result["persist_transaction_bytes"])
        self.assertEqual(result["endpoint"], EXPECTED_ENDPOINT)
        self.assertEqual(result["method"], "GET")
        self.assertFalse(result["call_authorized"])
        self.assertFalse(result["authority_granted"])
        self.assertTrue(result["metis_logger_rejected"])
        self.assertEqual(result["task26_layer"], "QUOTE")
        self.assertEqual(result["next_owner_phrase"], NEXT_OWNER_PHRASE)
        self.assertEqual(result["forbidden_follow_ons"], list(FORBIDDEN_FOLLOW_ONS))
        self.assertEqual(
            result["h11_park_terminal"],
            "H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
        )
        self.assertEqual(
            result["h07_park_terminal"],
            "RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
        )
        self.assertEqual(result["h11_park_sha256"], EXPECTED_H11_PARK_SHA256)
        self.assertEqual(result["a24_config_sha256"], EXPECTED_A24_SHA256)
        self.assertFalse(result["h13_or_h02_started"])
        self.assertFalse(result["h11_unparked"])
        drifted = dict(result)
        drifted["call_authorized"] = True
        self.assertEqual(
            decide_slice_terminal(drifted),
            "PMF_QUOTE_SLICE_PREREQUISITES_DRIFT",
        )

    def test_acceptance_and_readout_match_binder(self) -> None:
        result = bind_pmf_quote_slice(ROOT)
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["terminal"], result["terminal"])
        self.assertEqual(acceptance["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(acceptance["intended_route_id"], INTENDED_ROUTE_ID)
        self.assertFalse(acceptance["call_authorized"])
        self.assertEqual(acceptance["notional_atomic"], EXPECTED_NOTIONAL)
        readout = READOUT_PATH.read_text(encoding="utf-8")
        self.assertEqual(readout, format_owner_readout(result))
        self.assertIn("PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED", readout)
        self.assertIn("OK PMF-QUOTE-SLICE", readout)
        self.assertIn("REGISTRY_GAP", readout)
        self.assertIn("без `taker`", readout)
        self.assertIn("TASK-10 Metis logger отвергнут", readout)
        self.assertIn("H11 остаётся parked", readout)
        self.assertIn("H07/H01 остаётся parked", readout)
        self.assertIn("A24 base mint", readout)
        self.assertNotIn("POPCAT", readout)
        self.assertIn(NEXT_OWNER_PHRASE, readout)


if __name__ == "__main__":
    unittest.main()
