"""Behavioral tests for the bounded A4 PIT canonicalization projector."""

from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJECTOR_PATH = (
    ROOT / "src/solana_alpha_lab/factory/pit_data_truth_canonicalization.py"
)
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _projector_module():
    if not PROJECTOR_PATH.is_file():
        raise AssertionError("A4 PIT projector is not implemented yet")
    from solana_alpha_lab.factory import pit_data_truth_canonicalization as module

    return module


class FactoryV1PitDataTruthCanonicalizationTests(unittest.TestCase):
    def test_canonicalizes_frozen_atom1_into_bounded_pit_feature(self) -> None:
        module = _projector_module()

        acceptance = module.canonicalize_from_repository(ROOT)

        self.assertEqual(
            acceptance["terminal"],
            "FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_PASS",
        )
        self.assertEqual(
            acceptance["feature"]["feature_id"],
            "FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO",
        )
        self.assertEqual(acceptance["readiness"]["pit_lineage_ready"], True)
        self.assertEqual(
            acceptance["readiness"]["explicit_missingness_preserved"], True
        )
        self.assertEqual(
            acceptance["readiness"]["first_market_byte_within_one_preparatory_step"],
            True,
        )
        self.assertEqual(acceptance["projection"]["candidate_count"], 24)
        self.assertEqual(acceptance["projection"]["eligible_count"], 19)
        self.assertEqual(acceptance["projection"]["missing_count"], 5)
        self.assertEqual(
            acceptance["projection"]["search_observed_at"],
            acceptance["projection"]["decision_snapshot_at"],
        )
        self.assertEqual(
            len({row["mint"] for row in acceptance["projection"]["rows"]}),
            24,
        )
        self.assertTrue(
            all(row["mint"] == row["source_row_mint"] for row in acceptance["projection"]["rows"])
        )
        self.assertEqual(acceptance["scientific_family"]["terminal"], "CLOSED")
        self.assertFalse(acceptance["scientific_family"]["reopened"])
        self.assertFalse(acceptance["factory_runner_changed"])
        self.assertEqual(acceptance["side_effects"]["provider_calls"], 0)
        self.assertEqual(acceptance["side_effects"]["credential_reads"], 0)

    def test_future_updated_at_stays_typed_missing(self) -> None:
        module = _projector_module()
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/early_structural_backing_pit_commissioning/"
                "a1_window_a_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        row = deepcopy(runtime["candidate_observations"][0])
        row["x"] = None
        row["x_status"] = "MISSING"
        row["x_reason"] = "UPDATED_TIMESTAMP_IN_FUTURE"
        row["x_inputs"]["updatedAt"] = "2026-08-22T20:23:40Z"

        projected = module.project_candidate(row)

        self.assertEqual(projected["status"], "MISSING")
        self.assertIsNone(projected["value"])
        self.assertEqual(projected["reason"], "UPDATED_TIMESTAMP_IN_FUTURE")

    def test_fdv_substitution_remains_explicit_missing(self) -> None:
        module = _projector_module()
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/early_structural_backing_pit_commissioning/"
                "a1_window_a_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        row = next(
            item
            for item in runtime["candidate_observations"]
            if item["x_reason"] == "FDV_OR_SUBSTITUTE_REJECTED"
        )

        projected = module.project_candidate(row)

        self.assertEqual(projected["status"], "MISSING")
        self.assertEqual(projected["reason"], "FDV_OR_SUBSTITUTE_REJECTED")
        self.assertIsNone(projected["value"])

    def test_missing_mcap_or_liquidity_stays_typed_missing(self) -> None:
        module = _projector_module()
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/early_structural_backing_pit_commissioning/"
                "a1_window_a_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        row = deepcopy(
            next(
                item
                for item in runtime["candidate_observations"]
                if item["x_status"] == "ELIGIBLE"
            )
        )
        row["x_inputs"]["mcap"] = None
        row["x"] = None
        row["x_status"] = "MISSING"
        row["x_reason"] = "MCAP_OR_LIQUIDITY_MISSING"

        projected = module.project_candidate(row)

        self.assertEqual(projected["status"], "MISSING")
        self.assertEqual(projected["reason"], "MCAP_OR_LIQUIDITY_MISSING")
        self.assertIsNone(projected["value"])

    def test_non_positive_input_stays_typed_invalid(self) -> None:
        module = _projector_module()
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/early_structural_backing_pit_commissioning/"
                "a1_window_a_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        row = deepcopy(
            next(
                item
                for item in runtime["candidate_observations"]
                if item["x_status"] == "ELIGIBLE"
            )
        )
        row["x_inputs"]["liquidity"] = 0
        row["x"] = None
        row["x_status"] = "MISSING"
        row["x_reason"] = "INVALID_INPUT"

        projected = module.project_candidate(row)

        self.assertEqual(projected["status"], "MISSING")
        self.assertEqual(projected["reason"], "INVALID_INPUT")
        self.assertIsNone(projected["value"])

    def test_fdv_field_cannot_enter_the_canonical_input(self) -> None:
        module = _projector_module()
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/early_structural_backing_pit_commissioning/"
                "a1_window_a_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        row = deepcopy(
            next(
                item
                for item in runtime["candidate_observations"]
                if item["x_status"] == "ELIGIBLE"
            )
        )
        row["x_inputs"]["fdv"] = row["x_inputs"]["mcap"]

        with self.assertRaises(module.PitCanonicalizationError) as raised:
            module.project_candidate(row)

        self.assertEqual(str(raised.exception), "FDV_FIELD_NOT_ADMISSIBLE")

    def test_missing_reason_must_match_recomputed_reason(self) -> None:
        module = _projector_module()
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/early_structural_backing_pit_commissioning/"
                "a1_window_a_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        row = deepcopy(
            next(
                item
                for item in runtime["candidate_observations"]
                if item["x_reason"] == "UPDATED_TIMESTAMP_IN_FUTURE"
            )
        )
        row["x_reason"] = "MCAP_OR_LIQUIDITY_MISSING"

        with self.assertRaises(module.PitCanonicalizationError) as raised:
            module.project_candidate(row)

        self.assertEqual(str(raised.exception), "MISSING_REASON_MISMATCH")

    def test_entity_identity_must_be_bound_to_source_row(self) -> None:
        module = _projector_module()
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/early_structural_backing_pit_commissioning/"
                "a1_window_a_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        row = deepcopy(runtime["candidate_observations"][0])
        row["mint"] = "different-mint"

        with self.assertRaises(module.PitCanonicalizationError) as raised:
            module.project_candidate(row)

        self.assertEqual(str(raised.exception), "ROW_MINT_LINEAGE_MISMATCH")

    def test_duplicate_mint_decision_snapshot_keys_fail_closed(self) -> None:
        module = _projector_module()
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/early_structural_backing_pit_commissioning/"
                "a1_window_a_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        first = module.project_candidate(runtime["candidate_observations"][0])
        duplicate = deepcopy(first)

        with self.assertRaises(module.PitCanonicalizationError) as raised:
            module._validate_unique_entity_keys([first, duplicate])

        self.assertEqual(
            str(raised.exception), "DUPLICATE_MINT_DECISION_SNAPSHOT"
        )

    def test_recorded_ratio_mismatch_fails_closed(self) -> None:
        module = _projector_module()
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/early_structural_backing_pit_commissioning/"
                "a1_window_a_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        row = deepcopy(
            next(
                item
                for item in runtime["candidate_observations"]
                if item["x_status"] == "ELIGIBLE"
            )
        )
        row["x"] = float(row["x"]) + 0.01

        with self.assertRaises(module.PitCanonicalizationError) as raised:
            module.project_candidate(row)

        self.assertEqual(str(raised.exception), "RECORDED_RATIO_MISMATCH")

    def test_surface_registers_new_pit_identity_without_reusing_inverse(self) -> None:
        module = _projector_module()
        config_path = ROOT / "configs/factory_v1_common_market_feature_surface_v1.yaml"
        schema_path = ROOT / "catalog/schemas/factory_v1_common_market_feature_surface.schema.json"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(config, schema)

        by_id = {item["feature_id"]: item for item in config["features"]}
        pit = by_id[module.PIT_FEATURE_ID]
        inverse = by_id["FEAT-MCAP-TO-LIQUIDITY"]
        self.assertEqual(pit["availability_class"], "PIT_READY")
        self.assertEqual(pit["entity_scope"], "MINT_DECISION_SNAPSHOT")
        self.assertNotEqual(pit["feature_id"], inverse["feature_id"])
        self.assertEqual(inverse["availability_class"], "MISSING")

        from solana_alpha_lab.factory.market_feature_surface import resolve_feature_snapshot

        snapshot = resolve_feature_snapshot(
            {"required_feature_ids": [module.PIT_FEATURE_ID]},
            root=ROOT,
        )
        self.assertEqual(snapshot["pit_ready_count"], 1)
        self.assertEqual(snapshot["features"][0]["value_status"], "PIT_READY")
        self.assertIsNone(snapshot["features"][0]["value"])
        self.assertEqual(snapshot["features"][0]["pit_acceptance_id"], "FACTORY-V1-PIT-DATA-TRUTH-CANONICALIZATION-001")
        self.assertEqual(snapshot["features"][0]["pit_candidate_count"], 24)
        self.assertEqual(snapshot["features"][0]["pit_eligible_count"], 19)
        self.assertEqual(snapshot["features"][0]["pit_missing_count"], 5)


if __name__ == "__main__":
    unittest.main()
