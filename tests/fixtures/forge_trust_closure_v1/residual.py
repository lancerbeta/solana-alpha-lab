"""Candidate-only material obligation witnesses; never imports baseline verdicts."""
import argparse
import json
import sys
import unittest
from pathlib import Path

sys.path[:0] = ["/repo", "/repo/src", "/kit"]
from safety_preflight import check
from run_campaign import Observer, Result, scrub

SELECTORS = [
    "tests.test_forge_trust_closure_v1",
    "tests.test_factory_operational_store_readonly_schema_compat_v1",
    "tests.test_experiment_evidence_decision_v1",
    "tests.test_fast_lane_classifier",
    "tests.test_fast_lane_semantic_dod",
    "tests.test_hfic_classification_outcome_integrity_v1",
    "tests.test_hfic_market_evidence_epoch_decision_basis_v2",
    "tests.test_hfic_identity",
    "tests.test_hfic_temporal_result_coherence_v1.SavedResultRevisionVerticalTests",
    "tests.test_hfic_grounded_discovery_v1.OrdinaryOwnerPathTests",
    "tests.test_hfic_grounded_discovery_v1.ProductionRowRecipeTests",
    "tests.test_forge_ordinary_operation_lifecycle_v1",
    "tests.test_hfic_temporal_discovery_v1.TemporalArithmeticTests",
    "tests.test_hfic_ordinary_operation_v1.OrdinaryOperationTests.test_published_negative_simple_pauses_on_one_corpus",
    "tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_new_admitted_cohort_changes_evidence_while_identical_import_does_not",
    "tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_public_prefix_is_invariant_to_produced_future_poison_but_authorized_numeric_changes",
    "tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_os_reply_loss_then_moved_root_resume_uses_original_draft_and_charge",
    "tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_direct_owner_mutation_changes_only_capability_not_market_or_charges",
    "tests.test_science_to_strategy_handoff_v1",
]

CLOSURE_SELECTORS = [
    "tests.test_forge_trust_closure_v1",
    "tests.test_experiment_evidence_decision_v1",
    "tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_trust_closure_new_evidence_preserves_pending_reservation_and_safe_stop_recovery",
    "tests.test_science_to_strategy_handoff_v1",
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["residual"], required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--group", choices=["all", "closure"], default="all")
    a = p.parse_args()
    if not check()["pass"]:
        return 2
    a.output.mkdir(parents=True, exist_ok=False)
    observer = Observer(a.output, "residual")
    observer.retain_tempdirs()
    selectors = CLOSURE_SELECTORS if a.group == "closure" else SELECTORS
    observer.emit("HEADER", selectors=selectors, baseline_verdicts_imported=False,
                  full_product_path_claim=False, genuine_actor=False)
    result = Result(observer)
    sys.setprofile(observer.profile)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(s) for s in selectors)
    suite.run(result)
    sys.setprofile(None)
    seen = {row["test_id"] for row in result.rows}
    omitted = [{"test_id": test.id(), "status": "ERROR", "detail": detail}
               for test, detail in result.errors if test.id() not in seen]
    observer.emit("TERMINAL", tests_run=result.testsRun, omitted_errors=omitted)
    observer.trace.close()
    summary = scrub(dict(rows=result.rows + omitted, tests_run=result.testsRun,
                         unittest_success=result.wasSuccessful(), baseline_verdicts_imported=False,
                         genuine_actor=False, full_product_path_claim=False))
    (a.output / "residual-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
