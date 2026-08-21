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

from solana_alpha_lab.ordinary_recent_early_path_h900_audition import CLOSE_TERMINAL  # noqa: E402
from solana_alpha_lab.ordinary_recent_early_path_h900_failed_quotes_meu_reproject import (  # noqa: E402
    ATOM_ID,
    FailedQuotesMeuError,
    build_acceptance,
    reproject,
    validate_policy,
)
from solana_alpha_lab.quote_native_evidence_fit_panel import project_quote  # noqa: E402

CONFIG_PATH = ROOT / "configs/ordinary_recent_early_path_h900_failed_quotes_meu_reproject_v1.yaml"


class FailedQuotesMeuReprojectTests(unittest.TestCase):
    def test_policy_binds_frozen_hashes(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        validate_policy(policy, root=ROOT)
        self.assertEqual(policy["atom_id"], ATOM_ID)
        self.assertIs(policy["external_authority"]["capture_authorized"], False)

    def test_failed_quotes_body_is_meu(self) -> None:
        body = (
            ROOT
            / "docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject"
            / "fixtures"
            / "50ef83cfc5f72edd191f39c4a3ce5a6b7a90ec48456a82d92af35c976c0ba3b1.body"
        ).read_bytes()
        quote = project_quote(body)
        self.assertEqual(quote["terminal_class"], "MARKET_EXECUTION_UNAVAILABLE")

    def test_reproject_closes_early_path_without_provider(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        runtime = reproject(root=ROOT, policy=policy)
        acceptance = build_acceptance(runtime)

        self.assertEqual(runtime["score"]["terminal"], CLOSE_TERMINAL)
        self.assertEqual(runtime["failed_quotes_remapped_to_meu"], 4)
        self.assertEqual(runtime["provider_requests"], 0)
        self.assertIs(runtime["score"]["selected_market_execution_unavailable"], True)
        self.assertEqual(acceptance["owner_decision"], CLOSE_TERMINAL)
        self.assertEqual(
            acceptance["historical_source_owner_decision_preserved"],
            "INVALID_EVIDENCE_REPLAN",
        )

    def test_receipt_hash_drift_fails_closed(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        policy["bindings"]["expected_hashes"]["source_runtime_receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(FailedQuotesMeuError, "SOURCE_RECEIPT_HASH_DRIFT"):
            validate_policy(policy, root=ROOT)


if __name__ == "__main__":
    unittest.main()
