from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from solana_alpha_lab.task30_ohlcv_boundary_semantics import (
        BoundarySemanticsError,
        evaluate_boundary_semantics,
    )
except ModuleNotFoundError:
    BoundarySemanticsError = None
    evaluate_boundary_semantics = None


SYNTHETIC_A0_BOUNDARY_RECORD = {
    "authority": {
        "provider_api_rpc_wss_calls": 0,
        "credential_use": False,
        "r2_r3_access": False,
        "dependency_changes": False,
        "wallet_signer_transaction_actions": False,
        "cash_spend": False,
        "task30_trial_or_acceptance": False,
        "project_sources_changes": False,
    },
    "raw_binding": {
        "raw_sha256": "cce29d4e175bc81a474c699e3bb465daf8cb864f3cb195a9812bd0d3c0ca4163",
        "git_tracking": "OUTSIDE_GIT",
    },
    "observed_response": {
        "interval_seconds": 900,
        "record_count": 96,
        "requested_window": {"start": 1786100400, "end_exclusive": 1786186800},
        "returned_grid": {"first_timestamp": 1786101300, "last_timestamp": 1786186800},
        "zero_volume_record_count": 67,
        "zero_volume_semantics": "OBSERVED_ZERO_VOLUME_NOT_PROVEN_NO_TRADE",
    },
    "candidate_models": [
        {
            "model_id": "START_LABELED",
            "interval_mapping": "[timestamp,timestamp_plus_interval)",
            "implied_window": {"start": 1786101300, "end_exclusive": 1786187700},
        },
        {
            "model_id": "END_LABELED",
            "interval_mapping": "[timestamp_minus_interval,timestamp)",
            "implied_window": {"start": 1786100400, "end_exclusive": 1786186800},
        },
    ],
    "decision": "UNRESOLVED_INTERVAL_LABEL_SEMANTICS",
    "continuous_panel_claim": False,
    "pit_admissible_claim": False,
    "selected_model": None,
    "required_next_evidence": "INDEPENDENT_EXACT_TIMESTAMP_SEMANTICS_PROOF",
    "project_sources_disposition": "NO_CHANGE",
}

CONFIG_PATH = ROOT / "configs/task30_ohlcv_boundary_semantics_decision_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_ohlcv_boundary_semantics_decision.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/ohlcv_boundary_semantics_decision_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a1_ohlcv_boundary_semantics_decision_acceptance_v1.json"
FACTORY_FIT_PATH = ROOT / "docs/evidence/task30/a2_catalog_factory_fit_v1.json"
CATALOG_CORE_PATH = ROOT / "catalog/assets/core.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task30OhlcvBoundarySemanticsTests(unittest.TestCase):
    def test_versioned_policy_and_fixture_bind_the_fail_closed_result(self) -> None:
        """Catches a task artifact that drifts away from the evaluated boundary rule."""
        self.assertIsNotNone(evaluate_boundary_semantics)
        assert evaluate_boundary_semantics is not None

        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertFalse(list(Draft202012Validator(schema).iter_errors(config)))
        result = evaluate_boundary_semantics(config)
        self.assertEqual(result["decision"], fixture["expected_decision"])
        self.assertEqual(
            result["candidate_models"], fixture["expected_candidate_models"]
        )
        self.assertEqual(
            result["required_next_evidence"],
            fixture["expected_required_next_evidence"],
        )
        self.assertEqual(config["raw_binding"]["raw_sha256"], fixture["bound_raw_sha256"])

    def test_receipts_bind_the_decision_and_keep_factory_fit_full(self) -> None:
        """Catches a delivered semantic guardrail without its evidence or full review."""
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        factory_fit = json.loads(FACTORY_FIT_PATH.read_text(encoding="utf-8"))
        catalog = yaml.safe_load(CATALOG_CORE_PATH.read_text(encoding="utf-8"))

        bindings = acceptance["artifact_bindings"]
        self.assertEqual(bindings["contract"]["sha256"], sha256(ROOT / bindings["contract"]["path"]))
        self.assertEqual(bindings["config"]["sha256"], sha256(ROOT / bindings["config"]["path"]))
        self.assertEqual(bindings["schema"]["sha256"], sha256(ROOT / bindings["schema"]["path"]))
        self.assertEqual(bindings["fixture"]["sha256"], sha256(ROOT / bindings["fixture"]["path"]))
        self.assertEqual(bindings["evaluator"]["sha256"], sha256(ROOT / bindings["evaluator"]["path"]))
        self.assertEqual(acceptance["project_sources_disposition"]["kind"], "NO_CHANGE")
        self.assertTrue(all(value == 0 for value in acceptance["side_effect_counters"].values()))
        self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
        self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(
            factory_fit["product_horizon"]["watch"]["trigger"],
            "INDEPENDENT_EXACT_TIMESTAMP_SEMANTICS_PROOF_AVAILABLE",
        )

        assets = {asset["asset_id"] for asset in catalog["records"]}
        self.assertTrue(
            {
                "CONTRACT-T30-OHLCV-BOUNDARY-SEMANTICS-001",
                "CONFIG-T30-OHLCV-BOUNDARY-SEMANTICS-001",
                "SCHEMA-T30-OHLCV-BOUNDARY-SEMANTICS-001",
                "FIXTURE-T30-OHLCV-BOUNDARY-SEMANTICS-001",
                "MODULE-T30-OHLCV-BOUNDARY-SEMANTICS-001",
                "TEST-T30-OHLCV-BOUNDARY-SEMANTICS-001",
                "EVIDENCE-T30-A1-BOUNDARY-SEMANTICS-001",
                "EVIDENCE-T30-A2-CATALOG-FACTORY-FIT-001",
            }.issubset(assets)
        )

    def test_observed_boundary_keeps_both_models_and_blocks_panel_acceptance(self) -> None:
        """Catches a one-response timestamp observation being promoted to a panel."""
        self.assertIsNotNone(
            evaluate_boundary_semantics,
            "T30 must expose an offline boundary-semantics evaluator",
        )
        assert evaluate_boundary_semantics is not None

        result = evaluate_boundary_semantics(SYNTHETIC_A0_BOUNDARY_RECORD)

        self.assertEqual(result["decision"], "UNRESOLVED_INTERVAL_LABEL_SEMANTICS")
        self.assertEqual(
            result["candidate_models"], ["START_LABELED", "END_LABELED"]
        )
        self.assertEqual(
            result["required_next_evidence"],
            "INDEPENDENT_EXACT_TIMESTAMP_SEMANTICS_PROOF",
        )

    def test_unsafe_boundary_promotions_are_rejected(self) -> None:
        """Catches silent label selection, zero-to-no-trade, authority, and panel claims."""
        self.assertIsNotNone(BoundarySemanticsError)
        self.assertIsNotNone(evaluate_boundary_semantics)
        assert BoundarySemanticsError is not None
        assert evaluate_boundary_semantics is not None

        cases = (
            ("selected_model", "END_LABELED", "SELECTED_MODEL_FORBIDDEN"),
            ("continuous_panel_claim", True, "CONTINUOUS_PANEL_CLAIM_FORBIDDEN"),
            ("pit_admissible_claim", True, "PIT_ADMISSIBLE_CLAIM_FORBIDDEN"),
            (
                "observed_response.zero_volume_semantics",
                "EXPLICIT_NO_TRADE",
                "ZERO_VOLUME_PROMOTION_FORBIDDEN",
            ),
            ("authority.provider_api_rpc_wss_calls", 1, "EXTERNAL_AUTHORITY_FORBIDDEN"),
        )
        for pointer, replacement, expected_error in cases:
            with self.subTest(pointer=pointer):
                candidate = copy.deepcopy(SYNTHETIC_A0_BOUNDARY_RECORD)
                target = candidate
                parts = pointer.split(".")
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = replacement

                with self.assertRaisesRegex(BoundarySemanticsError, expected_error):
                    evaluate_boundary_semantics(candidate)
