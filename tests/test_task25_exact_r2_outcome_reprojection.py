from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from src.solana_alpha_lab import task25_exact_r2_outcome_reprojection as engine


REPO_ROOT = Path(__file__).resolve().parents[1]


class Task25ExactR2OutcomeReprojectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.surface = json.loads(
            (REPO_ROOT / engine.SURFACE_PATH).read_text(encoding="utf-8")
        )
        engine.validate_surface(cls.surface)
        cls.acceptance = engine.build_acceptance(REPO_ROOT, cls.surface)

    def test_01_pre_read_manifest_is_exact_and_sealed(self) -> None:
        manifest = engine.validate_pre_read_manifest(REPO_ROOT)
        self.assertEqual(
            manifest["status"], "SEALED_BEFORE_EXACT_R2_VALUE_REOPEN"
        )
        self.assertEqual(
            engine.sha256_file(REPO_ROOT / engine.PRE_READ_PATH),
            engine.PRE_READ_SHA256,
        )
        self.assertTrue(
            manifest["seal_assertions"]["receipt_written_before_raw_value_reopen"]
        )

    def test_02_pre_read_caps_exactly_nine_files_and_72_lines(self) -> None:
        manifest = engine.validate_pre_read_manifest(REPO_ROOT)
        self.assertEqual(len(manifest["raw_inputs"]), 9)
        self.assertEqual(sum(row["bytes"] for row in manifest["raw_inputs"]), 392234)
        self.assertEqual(sum(row["line_count"] for row in manifest["raw_inputs"]), 72)
        self.assertEqual(manifest["authority"]["r3_value_read"], False)

    def test_03_synthetic_classifier_fixture_is_complete(self) -> None:
        self.assertEqual(
            engine.validate_synthetic_fixture(REPO_ROOT),
            {"classification_cases": 12, "pair_identity_cases": 2},
        )

    def test_04_frozen_limits_are_inclusive(self) -> None:
        self.assertEqual(
            engine.classify_quote(
                status="QUOTE_AVAILABLE",
                quote_age_ms=5000,
                provider_latency_ms=1000,
                exact_identity=True,
                pit_valid=True,
            ),
            ("SUPPORTED", "EXACT_QUOTE_WITHIN_FROZEN_LIMITS"),
        )

    def test_05_latency_breach_fails_closed(self) -> None:
        self.assertEqual(
            engine.classify_quote(
                status="QUOTE_AVAILABLE",
                quote_age_ms=0,
                provider_latency_ms=1001,
                exact_identity=True,
                pit_valid=True,
            ),
            ("UNKNOWN", "PROVIDER_LATENCY_LIMIT_EXCEEDED"),
        )

    def test_06_provider_failure_is_not_no_route(self) -> None:
        for status in ("PROVIDER_ERROR", "INVALID_RESPONSE", "TIMEOUT"):
            self.assertEqual(
                engine.classify_quote(
                    status=status,
                    quote_age_ms=None,
                    provider_latency_ms=None,
                    exact_identity=True,
                    pit_valid=True,
                ),
                ("UNKNOWN", "PROVIDER_FAILURE_NOT_NO_ROUTE"),
            )

    def test_07_exact_pair_identity_rejects_atomic_drift(self) -> None:
        self.assertTrue(
            engine.exact_dependent_sell_identity(
                buy_input_mint="USDC",
                buy_output_mint="TOKEN",
                buy_output_atomic=10,
                buy_output_decimals=6,
                sell_input_mint="TOKEN",
                sell_input_atomic=10,
                sell_input_decimals=6,
                sell_output_mint="USDC",
            )
        )
        self.assertFalse(
            engine.exact_dependent_sell_identity(
                buy_input_mint="USDC",
                buy_output_mint="TOKEN",
                buy_output_atomic=10,
                buy_output_decimals=6,
                sell_input_mint="TOKEN",
                sell_input_atomic=9,
                sell_input_decimals=6,
                sell_output_mint="USDC",
            )
        )

    def test_08_surface_denominators_are_exact(self) -> None:
        summary = self.surface["summary"]
        self.assertEqual(summary["quote_attempts"], 72)
        self.assertEqual(summary["quote_pairs"], 36)
        self.assertEqual(summary["outcomes_input"], 108)
        self.assertEqual(summary["outcomes_output"], 108)
        self.assertEqual(summary["outcomes_dropped"], 0)

    def test_09_all_quote_and_pair_identities_are_unique(self) -> None:
        attempts = self.surface["quote_attempts"]
        pairs = self.surface["quote_pairs"]
        self.assertEqual(len({row["quote_attempt_id"] for row in attempts}), 72)
        self.assertEqual(len({row["pair_id"] for row in pairs}), 36)
        self.assertTrue(all(row["exact_dependent_sell_identity"] for row in pairs))

    def test_10_exact_atomic_inventory_is_retained(self) -> None:
        attempts = {
            row["quote_attempt_id"]: row for row in self.surface["quote_attempts"]
        }
        for pair in self.surface["quote_pairs"]:
            buy = attempts[pair["buy_quote_attempt_id"]]
            sell = attempts[pair["sell_quote_attempt_id"]]
            self.assertEqual(buy["output_mint"], sell["input_mint"])
            self.assertEqual(buy["output_quoted_atomic"], sell["input_requested_atomic"])
            self.assertEqual(buy["input_mint"], sell["output_mint"])

    def test_11_all_attempts_are_pit_ordered_before_cutoff(self) -> None:
        cutoff = engine._parse_time(self.surface["evaluation_cutoff_at"])
        for row in self.surface["quote_attempts"]:
            times = [
                engine._parse_time(row[key])
                for key in (
                    "raw_observed_at",
                    "first_reliable_available_at",
                    "available_to_strategy_at",
                    "ingested_at",
                )
            ]
            self.assertEqual(times, sorted(times))
            self.assertLessEqual(times[2], cutoff)

    def test_12_fillable_has_35_supported_and_one_latency_unknown(self) -> None:
        rows = [row for row in self.surface["outcomes"] if row["label"] == "FILLABLE"]
        self.assertEqual(Counter(row["assessment"] for row in rows), Counter({"SUPPORTED": 35, "UNKNOWN": 1}))
        unknown = [row for row in rows if row["assessment"] == "UNKNOWN"]
        self.assertEqual(unknown[0]["assessment_reason"], "PROVIDER_LATENCY_LIMIT_EXCEEDED")
        self.assertEqual(unknown[0]["notional"]["observed_provider_latency_ms"], 1030)

    def test_13_quote_exit_has_36_supported_but_inventory_is_open(self) -> None:
        rows = [row for row in self.surface["outcomes"] if row["label"] == "QUOTE_EXIT"]
        self.assertEqual(len(rows), 36)
        self.assertTrue(all(row["assessment"] == "SUPPORTED" for row in rows))
        self.assertTrue(all(row["inventory"]["state"] == "OPEN" for row in rows))
        self.assertTrue(all(row["fill_state"] == "ACTUAL_FILLS_NOT_OBSERVED" for row in rows))

    def test_14_touch_realized_vwap_and_net_remain_unknown(self) -> None:
        rows = [
            row
            for row in self.surface["outcomes"]
            if row["label"] in {"TOUCH", "REALIZED_VWAP", "NET"}
        ]
        self.assertEqual(len(rows), 27)
        self.assertTrue(all(row["assessment"] == "UNKNOWN" for row in rows))
        self.assertTrue(all(row["value_decimal"] is None for row in rows))
        self.assertTrue(all(row["unit"] is None for row in rows))

    def test_15_path_risk_is_supported_only_on_discrete_grid(self) -> None:
        rows = [row for row in self.surface["outcomes"] if row["label"] == "PATH_RISK"]
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(row["assessment"] == "SUPPORTED" for row in rows))
        self.assertTrue(all(row["claim_scope"] == "DISCRETE_PATH_GRID" for row in rows))
        self.assertTrue(all(row["path_state"] == "SPARSE_DISCRETE" for row in rows))

    def test_16_unknown_values_are_never_coerced_to_zero(self) -> None:
        unknown = [row for row in self.surface["outcomes"] if row["assessment"] == "UNKNOWN"]
        self.assertEqual(len(unknown), 28)
        self.assertTrue(all(row["value_decimal"] is None and row["unit"] is None for row in unknown))
        self.assertEqual(self.surface["summary"]["unknown_values_coerced_to_zero"], 0)

    def test_17_raw_bodies_are_not_copied_to_tracked_surface(self) -> None:
        serialized = engine.canonical_json_bytes(self.surface)
        self.assertNotIn(b'"raw_body"', serialized)
        self.assertNotIn(b'"redacted_body"', serialized)

    def test_18_r3_and_external_side_effects_remain_zero(self) -> None:
        self.assertEqual(self.surface["summary"]["r3_paths_or_values_read"], 0)
        side_effects = self.acceptance["side_effects"]
        self.assertEqual(side_effects["r3_paths_or_values_read"], 0)
        self.assertEqual(side_effects["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(side_effects["wallet_signer_transaction_actions"], 0)
        self.assertEqual(side_effects["new_collection"], 0)

    def test_19_delivery_gate_has_no_local_raw_dependency_or_skip(self) -> None:
        delivery = self.acceptance["synthetic_delivery_fixture"]
        self.assertFalse(delivery["raw_local_dependency_required_by_ci"])
        self.assertEqual(delivery["decision_critical_skip_count"], 0)
        self.assertEqual(delivery["classification_cases"], 12)
        with mock.patch.object(
            engine,
            "_regular_file_metadata",
            side_effect=AssertionError("CI path touched local raw metadata"),
        ):
            rebuilt = engine.build_acceptance(REPO_ROOT, self.surface)
        self.assertEqual(rebuilt["status"], self.acceptance["status"])

    def test_20_acceptance_checks_all_pass(self) -> None:
        self.assertEqual(
            self.acceptance["status"],
            "PASS_EXACT_R2_OUTCOME_SURFACE_WITH_BOUNDED_DEVELOPMENT_LABELS",
        )
        self.assertTrue(
            all(row["status"] == "PASS" for row in self.acceptance["acceptance_checks"])
        )

    def test_21_stored_outputs_are_content_exact(self) -> None:
        hashes = engine.check_stored_outputs(REPO_ROOT)
        self.assertEqual(
            set(hashes),
            {engine.SURFACE_PATH.as_posix(), engine.ACCEPTANCE_PATH.as_posix()},
        )

    def test_22_next_atom_and_r3_are_not_self_authorized(self) -> None:
        boundary = self.surface["next_boundary"]
        self.assertEqual(
            boundary["candidate_atom"],
            "T25-A6_REGISTER_ASSETS_UPDATE_CATALOG_AND_FULL_FACTORY_FIT_REVIEW_V1",
        )
        self.assertFalse(boundary["authorized_by_a5r1"])
        self.assertEqual(boundary["r3_access"], "DENY")


if __name__ == "__main__":
    unittest.main()
