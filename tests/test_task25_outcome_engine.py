from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task25_outcome_engine import (  # noqa: E402
    ACCEPTANCE_PATH,
    ATOM_ID,
    EVALUATION_CUTOFF_AT,
    FROZEN_INPUTS,
    PROJECTION_PATH,
    Task25OutcomeEngineError,
    _load_frozen_inputs,
    _parse_time,
    _validate_record,
    build_acceptance,
    build_outputs,
    build_projection,
    canonical_json_bytes,
    check_stored_outputs,
    sha256_bytes,
    sha256_file,
)


class Task25OutcomeEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema, cls.fixture = _load_frozen_inputs(ROOT)
        cls.records = {
            record["record_id"]: record for record in cls.fixture["records"]
        }
        cls.projection = build_projection(ROOT)
        cls.acceptance = build_acceptance(ROOT, cls.projection)

    def validate_mutation(self, record: dict) -> None:
        _validate_record(record, _parse_time(EVALUATION_CUTOFF_AT))

    def test_frozen_a2_inputs_are_exact_and_only_declared_inputs(self) -> None:
        self.assertEqual(
            set(FROZEN_INPUTS),
            {"contract", "config", "schema", "fixture"},
        )
        for role, binding in FROZEN_INPUTS.items():
            with self.subTest(role=role):
                self.assertEqual(sha256_file(ROOT / binding["path"]), binding["sha256"])

    def test_projection_is_deterministic_and_stored_bytes_are_exact(self) -> None:
        first_projection, first_acceptance = build_outputs(ROOT)
        second_projection, second_acceptance = build_outputs(ROOT)
        self.assertEqual(first_projection, second_projection)
        self.assertEqual(first_acceptance, second_acceptance)
        self.assertEqual((ROOT / PROJECTION_PATH).read_bytes(), first_projection)
        self.assertEqual((ROOT / ACCEPTANCE_PATH).read_bytes(), first_acceptance)
        self.assertEqual(
            check_stored_outputs(ROOT),
            {
                PROJECTION_PATH.as_posix(): sha256_bytes(first_projection),
                ACCEPTANCE_PATH.as_posix(): sha256_bytes(first_acceptance),
            },
        )

    def test_projection_retains_all_rows_and_all_label_families(self) -> None:
        summary = self.projection["summary"]
        self.assertEqual(summary["records_input"], 14)
        self.assertEqual(summary["records_output"], 14)
        self.assertEqual(summary["records_dropped"], 0)
        self.assertEqual(
            set(summary["labels"]),
            {"TOUCH", "FILLABLE", "QUOTE_EXIT", "REALIZED_VWAP", "NET", "PATH_RISK"},
        )
        self.assertEqual(len(self.projection["outcomes"]), 14)

    def test_missing_route_stale_and_provider_error_are_retained(self) -> None:
        route_states = self.projection["summary"]["route_states"]
        self.assertGreater(route_states["NO_ROUTE"], 0)
        self.assertGreater(route_states["PROVIDER_ERROR"], 0)
        self.assertGreater(route_states["STALE_QUOTE"], 0)
        by_id = {row["record_id"]: row for row in self.projection["outcomes"]}
        self.assertEqual(by_id["T25-GOLDEN-006"]["assessment"], "REFUTED")
        self.assertEqual(by_id["T25-GOLDEN-007"]["assessment"], "UNKNOWN")
        self.assertEqual(by_id["T25-GOLDEN-008"]["assessment"], "UNKNOWN")

    def test_future_row_for_cutoff_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            Task25OutcomeEngineError,
            "future_row_for_cutoff:T25-GOLDEN-014",
        ):
            build_projection(
                ROOT,
                evaluation_cutoff_at="2026-01-01T00:14:02Z",
            )

    def test_touch_cannot_be_promoted_to_fillable(self) -> None:
        record = copy.deepcopy(self.records["T25-GOLDEN-001"])
        record["label"] = "FILLABLE"
        with self.assertRaisesRegex(Task25OutcomeEngineError, "quote_basis_required"):
            self.validate_mutation(record)

    def test_quote_cannot_be_promoted_to_realized_settlement(self) -> None:
        record = copy.deepcopy(self.records["T25-GOLDEN-005"])
        record["label"] = "REALIZED_VWAP"
        with self.assertRaisesRegex(
            Task25OutcomeEngineError,
            "assessment_mismatch:.*expected_UNKNOWN",
        ):
            self.validate_mutation(record)

    def test_provider_error_cannot_be_relabelled_no_route(self) -> None:
        record = copy.deepcopy(self.records["T25-GOLDEN-007"])
        record["assessment"] = "REFUTED"
        with self.assertRaisesRegex(
            Task25OutcomeEngineError,
            "assessment_mismatch:.*expected_UNKNOWN",
        ):
            self.validate_mutation(record)

    def test_fee_double_counting_fails_closed(self) -> None:
        record = copy.deepcopy(self.records["T25-GOLDEN-012"])
        record["quality_flags"].append("FEE_SUBTRACTED_TWICE")
        with self.assertRaisesRegex(
            Task25OutcomeEngineError,
            "fee_double_counting_forbidden",
        ):
            self.validate_mutation(record)

    def test_unbounded_or_inverted_recovery_fails_closed(self) -> None:
        record = copy.deepcopy(self.records["T25-GOLDEN-014"])
        record["inventory"]["recovery_lower_bound_decimal"] = "0.100000"
        record["inventory"]["recovery_upper_bound_decimal"] = "0.000000"
        with self.assertRaisesRegex(
            Task25OutcomeEngineError,
            "recovery_bounds_invalid",
        ):
            self.validate_mutation(record)

    def test_unsupported_realized_vwap_fails_closed(self) -> None:
        record = copy.deepcopy(self.records["T25-GOLDEN-009"])
        record["assessment"] = "SUPPORTED"
        record["value_decimal"] = "0.100000"
        record["unit"] = "RETURN_DECIMAL"
        with self.assertRaisesRegex(
            Task25OutcomeEngineError,
            "assessment_mismatch:.*expected_UNKNOWN",
        ):
            self.validate_mutation(record)

    def test_unsupported_net_fails_closed(self) -> None:
        record = copy.deepcopy(self.records["T25-GOLDEN-011"])
        record["assessment"] = "SUPPORTED"
        record["value_decimal"] = "0.010000"
        record["unit"] = "RETURN_DECIMAL"
        with self.assertRaisesRegex(
            Task25OutcomeEngineError,
            "assessment_mismatch:.*expected_UNKNOWN",
        ):
            self.validate_mutation(record)

    def test_unknown_value_cannot_be_coerced_to_zero(self) -> None:
        record = copy.deepcopy(self.records["T25-GOLDEN-011"])
        record["value_decimal"] = "0"
        with self.assertRaisesRegex(Task25OutcomeEngineError, "missing_is_not_zero"):
            self.validate_mutation(record)

    def test_acceptance_is_single_synthetic_claim_with_zero_side_effects(self) -> None:
        self.assertEqual(self.acceptance["atom_id"], ATOM_ID)
        self.assertEqual(
            self.acceptance["status"],
            "PASS_SYNTHETIC_ENGINE_WITH_LIMITATIONS",
        )
        self.assertEqual(
            self.projection["claims"],
            ["SYNTHETIC_OUTCOME_ENGINE_CONTRACT_ACCEPTED"],
        )
        measured = self.acceptance["measured_boundary"]
        for key in (
            "r2_values_or_paths_read",
            "r3_values_or_paths_read",
            "holdout_consumption_records_added",
            "provider_api_rpc_wss_calls",
            "dependency_changes",
            "project_source_changes",
            "entity_graph_values_read",
            "catalog_or_registry_mutations",
            "wallet_signer_transaction_actions",
            "cash_spend_usd_cents",
        ):
            self.assertEqual(measured[key], 0, key)

    def test_acceptance_binds_projection_module_and_test(self) -> None:
        self.assertEqual(
            self.acceptance["output_binding"]["sha256"],
            sha256_bytes(canonical_json_bytes(self.projection)),
        )
        for binding in self.acceptance["code_bindings"].values():
            path = ROOT / binding["path"]
            self.assertEqual(path.stat().st_size, binding["bytes"])
            self.assertEqual(sha256_file(path), binding["sha256"])

    def test_next_boundary_is_a4_and_not_self_authorized(self) -> None:
        boundary = self.acceptance["next_boundary"]
        self.assertEqual(
            boundary["atom"],
            "T25-A4_BOUNDED_R2_OUTCOME_PROJECTION_AND_READ_RECEIPT_V1",
        )
        self.assertFalse(boundary["authorized_by_a3"])
        self.assertTrue(boundary["requires_exact_pre_read_receipt"])
        self.assertEqual(boundary["r3_access"], "DENY")

    def test_stored_json_is_normalized_and_contains_no_machine_path(self) -> None:
        for relative in (PROJECTION_PATH, ACCEPTANCE_PATH):
            payload = (ROOT / relative).read_bytes()
            self.assertTrue(payload.endswith(b"\n"))
            self.assertNotIn(b"\r\n", payload)
            self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))
            text = payload.decode("utf-8").lower()
            self.assertNotRegex(text, r"\b[a-z]:[\\/]")
            self.assertNotIn("local/", text)


if __name__ == "__main__":
    unittest.main()
