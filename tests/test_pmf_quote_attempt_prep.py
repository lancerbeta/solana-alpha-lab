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

from solana_alpha_lab.pmf_quote_attempt_prep import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    EXPECTED_FORK_ACCEPTANCE_SHA256,
    EXPECTED_FORK_RUNTIME_SHA256,
    EXPECTED_INPUT_MINT,
    EXPECTED_NOTIONAL,
    EXPECTED_OUTPUT_MINT,
    EXPECTED_ROUTE_ID,
    EXPECTED_TASK26_CONTRACT_SHA256,
    FORBIDDEN_FOLLOW_ONS,
    FORK_TERMINAL,
    TERMINAL_OUTCOMES,
    UNPAID_OWNER_PHRASES,
    bind_pmf_quote_attempt_prep,
    decide_attempt_prep_terminal,
    format_owner_readout,
)

CONTRACT_PATH = ROOT / "docs/tasks/PMF-QUOTE-ATTEMPT-PREP-V1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/pmf_quote_attempt_prep.py"
ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/pmf_quote_slice/a1_pmf_quote_attempt_prep_acceptance_v1.json"
)
READOUT_PATH = ROOT / "docs/reports/pmf_quote_slice/a1_attempt_prep_owner_readout_v1.md"
V6 = ROOT / "configs/provider_route_capability_registry_v6.yaml"
V7 = ROOT / "configs/provider_route_capability_registry_v7.yaml"
RC001_FREEZE = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
TRIAL_LEDGER = ROOT / "registries/global_trial_ledger.yaml"


class PmfQuoteAttemptPrepTests(unittest.TestCase):
    def test_contract_names_caps_and_stops(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: PMF-QUOTE-ATTEMPT-PREP-V1", text)
        self.assertIn("network: false", text)
        self.assertIn("credentials: false", text)
        self.assertIn("QUOTE_ATTEMPT_PREP_BOUND_NOT_ATTEMPTED", text)
        self.assertIn(
            "OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-ATTEMPT-PREP: offline attempt contract only, no wallet, no execute, no provider",
            text,
        )
        self.assertIn("WRAP_TASK26_ATTEMPT_AND_JUPITER_ORDER_EXECUTE_SPLIT", text)
        self.assertIn("FROZEN_QUOTE_USED_AS_ATTEMPT_QUOTE", text)
        self.assertIn("SEED_OR_PRIVATE_KEY_IN_GIT", text)
        self.assertIn("EXECUTE_PHRASE_OFFERED_AS_AUTHORIZED", text)
        self.assertIn("DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK", text)
        self.assertNotIn("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", text)
        self.assertEqual(AUTHORITY_PHRASE, (
            "OK PMF-QUOTE-ATTEMPT-PREP: offline attempt contract only, no wallet, "
            "no execute, no provider"
        ))
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "QUOTE_ATTEMPT_PREP_BOUND_NOT_ATTEMPTED",
                "QUOTE_ATTEMPT_PREP_PREREQUISITES_DRIFT",
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
            ["EVIDENCE-PMF-QUOTE-OWNER-FORK-ACCEPTANCE-001"],
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
        self.assertIn('"attempt_status": "NOT_ATTEMPTED"', source)

    def test_git_prerequisites_bind_attempt_prep(self) -> None:
        result = bind_pmf_quote_attempt_prep(ROOT)
        self.assertEqual(result["terminal"], "QUOTE_ATTEMPT_PREP_BOUND_NOT_ATTEMPTED")
        self.assertEqual(result["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(result["route_id"], EXPECTED_ROUTE_ID)
        self.assertEqual(result["output_mint"], EXPECTED_OUTPUT_MINT)
        self.assertEqual(result["input_mint"], EXPECTED_INPUT_MINT)
        self.assertEqual(result["notional_atomic"], EXPECTED_NOTIONAL)
        self.assertEqual(
            result["owner_fork_runtime_sha256"], EXPECTED_FORK_RUNTIME_SHA256
        )
        self.assertEqual(
            result["owner_fork_acceptance_sha256"], EXPECTED_FORK_ACCEPTANCE_SHA256
        )
        self.assertEqual(
            result["task26_contract_sha256"], EXPECTED_TASK26_CONTRACT_SHA256
        )
        self.assertEqual(result["owner_fork_terminal"], FORK_TERMINAL)
        self.assertEqual(result["attempt_status"], "NOT_ATTEMPTED")
        self.assertEqual(result["attempt_id"], "RESERVED_NOT_ISSUED")
        self.assertFalse(result["frozen_quote_is_attempt_quote"])
        self.assertEqual(result["taker"], "OMITTED_QUOTE_ONLY")
        self.assertEqual(result["execute"], "FORBIDDEN")
        self.assertEqual(result["execute_phrase_status"], "INELIGIBLE")
        self.assertEqual(result["provider_requests"], 0)
        self.assertFalse(result["later_credential_read"])
        self.assertEqual(result["unpaid_owner_phrases"], list(UNPAID_OWNER_PHRASES))
        self.assertEqual(result["forbidden_follow_ons"], list(FORBIDDEN_FOLLOW_ONS))
        drifted = dict(result)
        drifted["frozen_quote_is_attempt_quote"] = True
        self.assertEqual(
            decide_attempt_prep_terminal(drifted),
            "QUOTE_ATTEMPT_PREP_PREREQUISITES_DRIFT",
        )
        offered = dict(result)
        offered["unpaid_owner_phrases"] = [
            "OK PMF-QUOTE-EXECUTE: authorize /execute"
        ]
        self.assertEqual(
            decide_attempt_prep_terminal(offered),
            "QUOTE_ATTEMPT_PREP_PREREQUISITES_DRIFT",
        )

    def test_acceptance_and_readout_match_binder(self) -> None:
        result = bind_pmf_quote_attempt_prep(ROOT)
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["terminal"], result["terminal"])
        self.assertEqual(acceptance["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(acceptance["attempt_status"], "NOT_ATTEMPTED")
        self.assertFalse(acceptance["frozen_quote_is_attempt_quote"])
        self.assertEqual(acceptance["execute_phrase_status"], "INELIGIBLE")
        self.assertFalse(acceptance["execution_claim"])
        readout = READOUT_PATH.read_text(encoding="utf-8")
        self.assertEqual(readout, format_owner_readout(result))
        self.assertIn("QUOTE_ATTEMPT_PREP_BOUND_NOT_ATTEMPTED", readout)
        self.assertIn(AUTHORITY_PHRASE, readout)
        self.assertIn("NOT_ATTEMPTED", readout)
        self.assertIn("не seed", readout)
        self.assertIn("OK PMF-QUOTE-ATTEMPT", readout)
        self.assertNotIn("POPCAT", readout)
