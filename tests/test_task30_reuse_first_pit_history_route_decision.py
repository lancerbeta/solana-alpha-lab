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

from solana_alpha_lab.task30_reuse_first_pit_history_route import (  # noqa: E402
    ReuseFirstHistoryRouteError,
    evaluate_reuse_first_history_route,
)


CONFIG_PATH = ROOT / "configs/task30_reuse_first_pit_history_route_decision_v1.yaml"
SCHEMA_PATH = (
    ROOT / "catalog/schemas/task30_reuse_first_pit_history_route_decision.schema.json"
)
FIXTURE_PATH = (
    ROOT / "tests/fixtures/task30/reuse_first_pit_history_route_decision_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task30/a4_reuse_first_pit_history_route_decision_acceptance_v1.json"
)
CATALOG_CORE_PATH = ROOT / "catalog/assets/core.yaml"

EXPECTED_ASSET_IDS = {
    "CONTRACT-T30-REUSE-FIRST-HISTORY-ROUTE-001",
    "CONFIG-T30-REUSE-FIRST-HISTORY-ROUTE-001",
    "SCHEMA-T30-REUSE-FIRST-HISTORY-ROUTE-001",
    "FIXTURE-T30-REUSE-FIRST-HISTORY-ROUTE-001",
    "MODULE-T30-REUSE-FIRST-HISTORY-ROUTE-001",
    "TEST-T30-REUSE-FIRST-HISTORY-ROUTE-001",
    "EVIDENCE-T30-A4-REUSE-FIRST-HISTORY-ROUTE-001",
}


def replace_pointer(record: dict[str, object], pointer: str, replacement: object) -> None:
    target: dict[str, object] = record
    parts = pointer.split(".")
    for part in parts[:-1]:
        target = target[part]  # type: ignore[assignment,index]
    target[parts[-1]] = replacement


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task30ReuseFirstPitHistoryRouteDecisionTests(unittest.TestCase):
    def test_evaluates_only_the_closed_no_pilot_result(self) -> None:
        """Catches removal of the bounded no-pilot decision after a route conflict."""
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertFalse(list(Draft202012Validator(schema).iter_errors(policy)))
        self.assertEqual(
            evaluate_reuse_first_history_route(policy), fixture["expected_result"]
        )

    def test_rejects_promoting_documented_empty_intervals_to_pit_history(self) -> None:
        """Catches a documentation fact being promoted to a continuous panel."""
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        policy["non_claims"]["continuous_panel_claim"] = True
        with self.assertRaisesRegex(
            ReuseFirstHistoryRouteError, "PROMOTION_CLAIM_FORBIDDEN"
        ):
            evaluate_reuse_first_history_route(policy)

    def test_rejects_route_shortcuts_and_authority_widening(self) -> None:
        """Catches route-state rewrites, implicit access, and future-call promotion."""
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cases = (
            (
                "routes.GECKO_T30_A0.observed_response.boundary_conflict",
                "NO_CONFLICT",
                "GECKO_BOUNDARY_CONFLICT_REQUIRED",
            ),
            (
                "routes.SOLANA_TRACKER_PAIR.observed_bars",
                96,
                "SOLANA_TRACKER_INSUFFICIENT_SAMPLE_REQUIRED",
            ),
            (
                "routes.BIRDEYE_V3_PAIR.pair_identity",
                "PROVEN",
                "BIRDEYE_CANDIDATE_PROMOTION_FORBIDDEN",
            ),
            (
                "authority.provider_api_rpc_wss_calls",
                1,
                "EXTERNAL_AUTHORITY_FORBIDDEN",
            ),
            ("authority.credential_use", True, "EXTERNAL_AUTHORITY_FORBIDDEN"),
            (
                "decision",
                "EXACT_OWNER_PROOF_CALL_REQUIRED",
                "DECISION_PROMOTION_FORBIDDEN",
            ),
            (
                "next_boundary",
                "PROVIDER_CALL_NOW",
                "NEXT_BOUNDARY_PROMOTION_FORBIDDEN",
            ),
            (
                "project_sources_disposition",
                "RELEASE_CANDIDATE",
                "SOURCE_DISPOSITION_DRIFT",
            ),
        )
        for pointer, replacement, expected_error in cases:
            with self.subTest(pointer=pointer):
                candidate = copy.deepcopy(policy)
                replace_pointer(candidate, pointer, replacement)
                with self.assertRaisesRegex(ReuseFirstHistoryRouteError, expected_error):
                    evaluate_reuse_first_history_route(candidate)

    def test_rejects_credential_like_keys_anywhere_in_the_policy(self) -> None:
        """Catches a key-like field hidden in a nominally offline policy."""
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        policy["routes"]["BIRDEYE_V3_PAIR"]["api_key"] = "synthetic-only"
        with self.assertRaisesRegex(
            ReuseFirstHistoryRouteError, "CREDENTIAL_DISCLOSURE_FORBIDDEN"
        ):
            evaluate_reuse_first_history_route(policy)

    def test_acceptance_binds_artifacts_and_reports_zero_external_effects(self) -> None:
        """Catches delivery without hash-bound evidence or a full factory review."""
        self.assertTrue(
            ACCEPTANCE_PATH.exists(),
            "T30-A4 must include one hash-bound acceptance receipt",
        )
        if not ACCEPTANCE_PATH.exists():
            return

        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        for binding in receipt["artifact_bindings"].values():
            self.assertEqual(binding["sha256"], sha256(ROOT / binding["path"]))
        self.assertTrue(
            all(value == 0 for value in receipt["side_effect_counters"].values())
        )
        self.assertEqual(
            receipt["decision"]["value"], "T30_A0_REUSE_CLOSED_NO_PROVIDER_PILOT"
        )
        self.assertEqual(receipt["factory_fit"]["review_scope"], "FULL_REVIEW")
        self.assertEqual(
            receipt["project_sources_disposition"]["kind"], "NO_CHANGE"
        )

    def test_catalog_registers_each_t30_a4_output(self) -> None:
        """Catches an accepted decision that future entry gates cannot discover."""
        catalog = yaml.safe_load(CATALOG_CORE_PATH.read_text(encoding="utf-8"))
        asset_ids = {record["asset_id"] for record in catalog["records"]}
        self.assertTrue(EXPECTED_ASSET_IDS.issubset(asset_ids))
