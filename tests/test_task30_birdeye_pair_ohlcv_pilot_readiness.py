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

from solana_alpha_lab.task30_birdeye_pair_ohlcv_pilot_readiness import (
    PilotReadinessError,
    evaluate_pilot_readiness,
)


CONFIG_PATH = ROOT / "configs/task30_birdeye_pair_ohlcv_pilot_readiness_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_birdeye_pair_ohlcv_pilot_readiness.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/birdeye_pair_ohlcv_pilot_readiness_v1.json"
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task30/a3_birdeye_pair_ohlcv_pilot_readiness_acceptance_v1.json"
)
FACTORY_FIT_PATH = (
    ROOT / "docs/evidence/task30/a4_birdeye_pair_ohlcv_pilot_readiness_factory_fit_v1.json"
)
CATALOG_CORE_PATH = ROOT / "catalog/assets/core.yaml"


def replace_pointer(record: dict[str, object], pointer: str, replacement: object) -> None:
    target: dict[str, object] = record
    parts = pointer.split(".")
    for part in parts[:-1]:
        target = target[part]  # type: ignore[assignment,index]
    target[parts[-1]] = replacement


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task30BirdeyePairOhlcvPilotReadinessTests(unittest.TestCase):
    def test_exposes_fail_closed_offline_evaluator(self) -> None:
        """Catches a missing readiness guardrail before a provider call is considered."""
        self.assertIsNotNone(
            evaluate_pilot_readiness,
            "T30-A3 must expose an offline Birdeye pilot-readiness evaluator",
        )

    def test_unresolved_policy_is_schema_valid_and_not_ready(self) -> None:
        """Catches any change that promotes the unresolved state to a pilot."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertFalse(list(Draft202012Validator(schema).iter_errors(config)))
        self.assertEqual(evaluate_pilot_readiness(config), fixture["expected_result"])

    def test_shortcuts_and_external_authority_are_rejected(self) -> None:
        """Catches REST/WebSocket conflation, hidden credentials, and scope widening."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cases = (
            ("evidence.rest_15m_enum", "PROVEN", "REST_15M_ENUM_UNPROVEN"),
            (
                "evidence.websocket_15m",
                "REST_ADMISSIBLE",
                "WEBSOCKET_NOT_REST_EVIDENCE",
            ),
            ("pair_identity.status", "PROVEN", "PAIR_IDENTITY_UNPROVEN"),
            (
                "authority.provider_api_rpc_wss_calls",
                1,
                "EXTERNAL_AUTHORITY_FORBIDDEN",
            ),
            ("authority.credential_use", True, "EXTERNAL_AUTHORITY_FORBIDDEN"),
            (
                "decision",
                "SURFACE_FEASIBLE_NOT_ACCEPTED",
                "DECISION_PROMOTION_FORBIDDEN",
            ),
            (
                "credential_probe.api_key",
                "not-a-real-key",
                "CREDENTIAL_DISCLOSURE_FORBIDDEN",
            ),
            ("request_shape.raw_data_path", "local/raw.json", "RAW_DATA_FORBIDDEN"),
            ("request_shape.retry_count", 1, "RETRY_OR_FALLBACK_FORBIDDEN"),
            (
                "request_shape.fallback_provider",
                "SOLANA_TRACKER",
                "RETRY_OR_FALLBACK_FORBIDDEN",
            ),
            (
                "project_sources_disposition",
                "RELEASE_CANDIDATE",
                "SOURCE_DISPOSITION_DRIFT",
            ),
            (
                "non_claims.continuous_panel_claim",
                True,
                "PROMOTION_CLAIM_FORBIDDEN",
            ),
            (
                "non_claims.pit_admissible_claim",
                True,
                "PROMOTION_CLAIM_FORBIDDEN",
            ),
            (
                "non_claims.task30_trial_claim",
                True,
                "PROMOTION_CLAIM_FORBIDDEN",
            ),
            (
                "non_claims.numeric_netreturn_claim",
                True,
                "PROMOTION_CLAIM_FORBIDDEN",
            ),
        )
        for pointer, replacement, expected_error in cases:
            with self.subTest(pointer=pointer):
                candidate = copy.deepcopy(config)
                replace_pointer(candidate, pointer, replacement)
                with self.assertRaisesRegex(PilotReadinessError, expected_error):
                    evaluate_pilot_readiness(candidate)

    def test_receipts_bind_the_offline_boundary_and_catalog(self) -> None:
        """Catches an evaluator delivered without evidence, review, or discovery."""
        self.assertTrue(
            ACCEPTANCE_PATH.exists(),
            "T30-A3 must include a hash-bound acceptance receipt",
        )
        self.assertTrue(
            FACTORY_FIT_PATH.exists(),
            "T30-A3 must include a FULL_REVIEW Factory Fit receipt",
        )
        if not ACCEPTANCE_PATH.exists() or not FACTORY_FIT_PATH.exists():
            return

        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        factory_fit = json.loads(FACTORY_FIT_PATH.read_text(encoding="utf-8"))
        catalog = yaml.safe_load(CATALOG_CORE_PATH.read_text(encoding="utf-8"))

        for binding in acceptance["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertEqual(binding["sha256"], sha256(path))
        self.assertTrue(
            all(value == 0 for value in acceptance["side_effect_counters"].values())
        )
        self.assertEqual(
            acceptance["project_sources_disposition"]["kind"], "NO_CHANGE"
        )
        self.assertEqual(
            acceptance["decision"]["value"], "NOT_READY_FOR_PROVIDER_PILOT"
        )
        self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
        self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(factory_fit["reuse_first"]["outcome"], "STOP")
        self.assertEqual(
            factory_fit["product_horizon"]["now"]["candidate"],
            "NO_PROVIDER_PILOT_UNTIL_EXACT_PROOFS",
        )

        assets = {asset["asset_id"] for asset in catalog["records"]}
        self.assertTrue(
            {
                "CONTRACT-T30-BIRDEYE-PILOT-READINESS-001",
                "CONFIG-T30-BIRDEYE-PILOT-READINESS-001",
                "SCHEMA-T30-BIRDEYE-PILOT-READINESS-001",
                "FIXTURE-T30-BIRDEYE-PILOT-READINESS-001",
                "MODULE-T30-BIRDEYE-PILOT-READINESS-001",
                "TEST-T30-BIRDEYE-PILOT-READINESS-001",
                "EVIDENCE-T30-A3-BIRDEYE-PILOT-READINESS-001",
                "EVIDENCE-T30-A4-BIRDEYE-PILOT-FACTORY-FIT-001",
            }.issubset(assets)
        )
