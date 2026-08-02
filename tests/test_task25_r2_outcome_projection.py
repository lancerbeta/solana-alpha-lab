from __future__ import annotations

import copy
import json
import unittest
from collections import Counter
from pathlib import Path

from src.solana_alpha_lab import task25_r2_outcome_projection as engine


REPO_ROOT = Path(__file__).resolve().parents[1]


class Task25R2OutcomeProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.rows = engine.load_exact_inputs(REPO_ROOT)
        cls.projection = engine.build_projection_from_rows(cls.manifest, cls.rows)

    def test_01_pre_read_manifest_is_exact_and_sealed(self) -> None:
        manifest = engine.validate_pre_read_manifest(REPO_ROOT)
        self.assertEqual(manifest["status"], "SEALED_BEFORE_R2_DERIVED_VALUE_READ")
        self.assertTrue(manifest["seal_assertions"]["receipt_written_before_value_open"])
        self.assertEqual(
            engine.sha256_file(REPO_ROOT / engine.PRE_READ_PATH),
            engine.PRE_READ_SHA256,
        )

    def test_02_exact_three_file_read_surface(self) -> None:
        self.assertEqual(set(self.rows), set(engine.EXPECTED_INPUTS))
        self.assertEqual(
            {name: len(rows) for name, rows in self.rows.items()},
            {
                "panel_inventory_v1.csv": 9,
                "quote_pair_availability_v1.csv": 36,
                "panel_diagnostics_v1.csv": 9,
            },
        )

    def test_03_projection_denominators_are_exact(self) -> None:
        summary = self.projection["summary"]
        self.assertEqual(summary["outcomes_input"], 108)
        self.assertEqual(summary["outcomes_output"], 108)
        self.assertEqual(summary["outcomes_dropped"], 0)
        self.assertEqual(
            summary["labels"],
            {
                "FILLABLE": 36,
                "NET": 9,
                "PATH_RISK": 9,
                "QUOTE_EXIT": 36,
                "REALIZED_VWAP": 9,
                "TOUCH": 9,
            },
        )

    def test_04_quote_available_is_not_upgraded_without_exact_identity(self) -> None:
        quote_rows = [
            row
            for row in self.projection["outcomes"]
            if row["label"] in {"FILLABLE", "QUOTE_EXIT"}
        ]
        self.assertEqual(len(quote_rows), 72)
        self.assertEqual(Counter(row["route_state_observed"] for row in quote_rows), Counter({"QUOTE_AVAILABLE": 72}))
        self.assertTrue(all(row["assessment"] == "UNKNOWN" for row in quote_rows))
        self.assertTrue(all(row["fill_state"] == "ACTUAL_FILLS_NOT_OBSERVED" for row in quote_rows))

    def test_05_quote_available_classifier_fails_closed(self) -> None:
        self.assertEqual(engine._route_assessment("QUOTE_AVAILABLE"), "UNKNOWN")
        self.assertEqual(engine._route_assessment("NO_ROUTE"), "REFUTED")
        for state in ("PROVIDER_ERROR", "INVALID_RESPONSE", "TIMEOUT"):
            self.assertEqual(engine._route_assessment(state), "UNKNOWN")

    def test_06_realized_vwap_and_net_are_unknown(self) -> None:
        rows = [
            row
            for row in self.projection["outcomes"]
            if row["label"] in {"REALIZED_VWAP", "NET"}
        ]
        self.assertEqual(len(rows), 18)
        self.assertTrue(all(row["assessment"] == "UNKNOWN" for row in rows))
        self.assertTrue(all(row["value_decimal"] is None for row in rows))
        self.assertTrue(all(row["unit"] is None for row in rows))

    def test_07_touch_stays_unknown_without_threshold(self) -> None:
        rows = [row for row in self.projection["outcomes"] if row["label"] == "TOUCH"]
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(row["assessment"] == "UNKNOWN" for row in rows))
        self.assertTrue(
            all(
                "NO_FROZEN_REFERENCE_THRESHOLD_IN_TRACKED_PROJECTION"
                in row["quality_flags"]
                for row in rows
            )
        )

    def test_08_path_risk_is_discrete_only(self) -> None:
        rows = [row for row in self.projection["outcomes"] if row["label"] == "PATH_RISK"]
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(row["assessment"] == "SUPPORTED" for row in rows))
        self.assertTrue(all(row["claim_scope"] == "DISCRETE_PATH_GRID" for row in rows))
        self.assertTrue(all(row["path_state"] == "SPARSE_DISCRETE" for row in rows))
        self.assertTrue(all(float(row["value_decimal"]) >= 0 for row in rows))
        self.assertTrue(
            all("CONTINUOUS_MAE_MFE_FORBIDDEN" in row["quality_flags"] for row in rows)
        )

    def test_09_unknown_is_never_coerced_to_zero(self) -> None:
        unknown = [row for row in self.projection["outcomes"] if row["assessment"] == "UNKNOWN"]
        self.assertEqual(len(unknown), 99)
        self.assertTrue(all(row["value_decimal"] is None and row["unit"] is None for row in unknown))
        self.assertEqual(self.projection["summary"]["unknown_values_coerced_to_zero"], 0)

    def test_10_record_ids_are_unique_and_complete(self) -> None:
        ids = [row["record_id"] for row in self.projection["outcomes"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "T25-R2-0001")
        self.assertEqual(ids[-1], "T25-R2-0108")

    def test_11_future_panel_row_is_rejected(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows["panel_inventory_v1.csv"][0]["last_reliable_available_at"] = "2026-08-01T13:11:55Z"
        with self.assertRaisesRegex(engine.Task25R2ProjectionError, "future_panel_row_for_cutoff"):
            engine.build_projection_from_rows(self.manifest, rows)

    def test_12_future_quote_row_is_rejected(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows["quote_pair_availability_v1.csv"][0]["buy_first_reliable_available_at"] = "2026-08-01T13:11:55Z"
        with self.assertRaisesRegex(engine.Task25R2ProjectionError, "future_buy_quote_for_cutoff"):
            engine.build_projection_from_rows(self.manifest, rows)

    def test_13_missing_retention_is_not_zero(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows["quote_pair_availability_v1.csv"][0]["roundtrip_quote_retention_bps"] = ""
        with self.assertRaisesRegex(engine.Task25R2ProjectionError, "pair_retention_missing"):
            engine.build_projection_from_rows(self.manifest, rows)

    def test_14_duplicate_pair_is_rejected(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows["quote_pair_availability_v1.csv"].append(
            copy.deepcopy(rows["quote_pair_availability_v1.csv"][0])
        )
        with self.assertRaisesRegex(engine.Task25R2ProjectionError, "duplicate_quote_pair_row"):
            engine.build_projection_from_rows(self.manifest, rows)

    def test_15_atomic_notional_mismatch_is_rejected(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows["quote_pair_availability_v1.csv"][0]["buy_input_atomic"] = "0"
        with self.assertRaisesRegex(engine.Task25R2ProjectionError, "buy_atomic_notional_mismatch"):
            engine.build_projection_from_rows(self.manifest, rows)

    def test_16_inference_broadening_is_rejected(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows["panel_diagnostics_v1.csv"][0]["inference_mode"] = "GENERALIZABLE"
        with self.assertRaisesRegex(engine.Task25R2ProjectionError, "inference_mode_broadened"):
            engine.build_projection_from_rows(self.manifest, rows)

    def test_17_projection_is_deterministic(self) -> None:
        again = engine.build_projection_from_rows(self.manifest, self.rows)
        self.assertEqual(
            engine.canonical_json_bytes(self.projection),
            engine.canonical_json_bytes(again),
        )

    def test_18_r3_and_raw_r2_remain_zero(self) -> None:
        summary = self.projection["summary"]
        self.assertEqual(summary["raw_r2_value_files_reopened"], 0)
        self.assertEqual(summary["r3_paths_or_values_read"], 0)
        self.assertEqual(self.projection["next_boundary"]["r3_access"], "DENY")

    def test_19_receipt_is_fail_closed_and_content_addressed(self) -> None:
        receipt = engine.build_receipt(REPO_ROOT, self.projection)
        self.assertEqual(receipt["status"], "PASS_WITH_EXPLICIT_PROJECTION_LIMITATIONS")
        self.assertTrue(all(item["status"] == "PASS" for item in receipt["checks"]))
        self.assertEqual(receipt["holdout_boundary"]["records"], 0)
        self.assertEqual(
            receipt["projection"]["sha256"],
            engine.sha256_bytes(engine.canonical_json_bytes(self.projection)),
        )

    def test_20_stored_outputs_are_exact(self) -> None:
        hashes = engine.check_stored_outputs(REPO_ROOT)
        self.assertEqual(set(hashes), {engine.PROJECTION_PATH.as_posix(), engine.RECEIPT_PATH.as_posix()})


if __name__ == "__main__":
    unittest.main()
