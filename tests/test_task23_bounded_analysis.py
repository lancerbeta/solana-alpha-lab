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

from solana_alpha_lab.task23_bounded_analysis import (
    EXPECTED_MANIFEST_SHA256,
    OWNER_DECISION,
    Task23AnalysisError,
    _validate_manifest,
    build_analysis,
    canonical_json_bytes,
    evaluate_adversarial_acceptance,
    load_a3_bundle,
    render_owner_report,
    sha256_bytes,
    sha256_file,
)


PROJECTION = ROOT / "docs/evidence/task23/a3_projection_v1_attempt_02"
ANALYSIS_PATH = ROOT / "docs/evidence/task23/a4_bounded_analysis_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task23/a4_adversarial_acceptance_v1.json"
REPORT_PATH = ROOT / "docs/reports/task23_cohort_diagnostics_v1.md"


class Task23BoundedAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.tables = load_a3_bundle(PROJECTION)
        cls.analysis = build_analysis(cls.manifest, cls.tables)

    def test_a3_bundle_is_exactly_content_addressed(self) -> None:
        self.assertEqual(
            sha256_file(PROJECTION / "projection_manifest_v1.json"),
            EXPECTED_MANIFEST_SHA256,
        )
        self.assertEqual(len(self.tables["panel_inventory_v1.csv"]), 9)
        self.assertEqual(len(self.tables["quote_pair_availability_v1.csv"]), 36)

    def test_analysis_is_deterministic_and_owner_decision_is_single(self) -> None:
        again = build_analysis(copy.deepcopy(self.manifest), copy.deepcopy(self.tables))
        self.assertEqual(canonical_json_bytes(self.analysis), canonical_json_bytes(again))
        self.assertEqual(self.analysis["claims"], [OWNER_DECISION])
        self.assertEqual(self.analysis["owner_decision"]["decision"], OWNER_DECISION)

    def test_generated_artifacts_bind_analysis_and_report(self) -> None:
        analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(analysis, self.analysis)
        self.assertEqual(acceptance["status"], "PASS_WITH_DECLARED_LIMITATIONS")
        self.assertEqual(
            acceptance["output_bindings"]["analysis_sha256"],
            sha256_file(ANALYSIS_PATH),
        )
        self.assertEqual(
            acceptance["output_bindings"]["owner_report_sha256"],
            sha256_file(REPORT_PATH),
        )

    def test_owner_report_contains_decision_and_material_limitations(self) -> None:
        report = render_owner_report(self.analysis)
        self.assertEqual(report, REPORT_PATH.read_text(encoding="utf-8"))
        for phrase in (
            OWNER_DECISION,
            "effective independent cluster count is at most 1",
            "zero observed failures does not mean zero future failure probability",
            "right-censored",
            "no route-continuity claim",
            "R3 path discovery/read = 0",
            "full Catalog-integrity validation must fail closed",
        ):
            self.assertIn(phrase, report)

    def test_r3_counter_mutation_fails_closed(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["summary"]["r3_paths_discovered"] = 1
        with self.assertRaisesRegex(Task23AnalysisError, "r3_paths_discovered"):
            _validate_manifest(manifest)

    def test_dropped_pair_fails_closed(self) -> None:
        tables = copy.deepcopy(self.tables)
        tables["quote_pair_availability_v1.csv"].pop()
        with self.assertRaisesRegex(Task23AnalysisError, "quote_pair_population_mismatch"):
            build_analysis(self.manifest, tables)

    def test_duplicate_pair_fails_closed(self) -> None:
        tables = copy.deepcopy(self.tables)
        tables["quote_pair_availability_v1.csv"][-1] = copy.deepcopy(
            tables["quote_pair_availability_v1.csv"][0]
        )
        with self.assertRaisesRegex(Task23AnalysisError, "duplicate_rows:quote_pairs"):
            build_analysis(self.manifest, tables)

    def test_nominal_or_negative_elapsed_substitution_fails_closed(self) -> None:
        tables = copy.deepcopy(self.tables)
        p1 = next(
            row for row in tables["panel_diagnostics_v1.csv"] if row["panel_id"] == "P1"
        )
        p1["actual_elapsed_from_member_p0_seconds"] = "-2400"
        with self.assertRaisesRegex(Task23AnalysisError, "negative_actual_elapsed"):
            build_analysis(self.manifest, tables)

    def test_missingness_coercion_fails_adversarial_acceptance(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["denominators"]["observed_missing"]["missing_is_zero"] = True
        with self.assertRaisesRegex(Task23AnalysisError, "MISSING_NOT_ZERO"):
            evaluate_adversarial_acceptance(analysis)

    def test_alpha_claim_fails_adversarial_acceptance(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["claims"].append("ALPHA_CONFIRMED")
        with self.assertRaisesRegex(Task23AnalysisError, "NO_EXECUTION_ALPHA_CLAIM"):
            evaluate_adversarial_acceptance(analysis)

    def test_route_continuity_overclaim_fails_adversarial_acceptance(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["limitations"].remove(
            "ROUTE_ID_CONTINUITY_NOT_MATERIALIZED_NO_CLAIM"
        )
        with self.assertRaisesRegex(Task23AnalysisError, "ROUTE_CONTINUITY_NO_CLAIM"):
            evaluate_adversarial_acceptance(analysis)

    def test_no_invented_precision_or_self_authorization(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["population_and_dependence"]["inference_mode"] = "INFERENTIAL"
        analysis["next_boundary"]["authorized_by_a4"] = True
        with self.assertRaisesRegex(Task23AnalysisError, "NO_INVENTED_PRECISION"):
            evaluate_adversarial_acceptance(analysis)

    def test_acceptance_bytes_are_reproducible_before_output_binding(self) -> None:
        first = evaluate_adversarial_acceptance(copy.deepcopy(self.analysis))
        second = evaluate_adversarial_acceptance(copy.deepcopy(self.analysis))
        self.assertEqual(sha256_bytes(canonical_json_bytes(first)), sha256_bytes(canonical_json_bytes(second)))


if __name__ == "__main__":
    unittest.main()
