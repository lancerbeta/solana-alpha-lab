"""Synthetic proofs for HORIZON_SCOPED_SCIENTIFIC_ELIGIBILITY_V1."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.experiment_spec import (
    ExperimentSpecError,
    validate_experiment_document,
)
from solana_alpha_lab.factory.hfic_selection_robustness_gate import (
    BLOCK_FORGE_SELECTION_RISK,
    FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
    apply_selection_gate_to_preflight,
    interpret_selection_gate_receipt,
)
from solana_alpha_lab.factory.scientific_eligibility_projection import (
    C1_EXPECTED,
    ELIGIBILITY_SCOPE_FULL_LIFECYCLE,
    MIN_USABLE_BASE_X_POPULATION,
    READINESS_COMPLETE,
    READINESS_MISSINGNESS_UNRESOLVED,
    READINESS_UNSPECIFIED,
    ScientificEligibilityError,
    X_ALLOWED_LATENESS_SECONDS,
    X_DUE_OFFSET_SECONDS,
    X_FIELD_ID,
    X_POINT_ID,
    assert_c1_shape,
    bound_schedule_y_point_ids,
    full_lifecycle_scope_equivalent,
    project_scientific_eligibility,
    y_columns_forbidden,
)

ANCHOR = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _census(mint: str, denom: str, *, candidate: str = "X_ELIGIBLE") -> dict[str, str]:
    return {
        "mint": mint,
        "candidate_state": candidate,
        "denominator_state": denom,
        "authoritative_anchor": ANCHOR.isoformat().replace("+00:00", "Z"),
    }


def _x300(mint: str, *, late: bool = False, state: str = "OBSERVED") -> dict[str, str]:
    available = ANCHOR + timedelta(seconds=X_DUE_OFFSET_SECONDS)
    if late:
        available = available + timedelta(seconds=X_ALLOWED_LATENESS_SECONDS + 1)
    return {
        "mint": mint,
        "point_id": X_POINT_ID,
        "field_id": X_FIELD_ID,
        "state": state,
        "first_reliable_available_at": available.isoformat().replace("+00:00", "Z"),
    }


def _y(mint: str, point_id: str, field_id: str, state: str) -> dict[str, str]:
    return {
        "mint": mint,
        "point_id": point_id,
        "field_id": field_id,
        "state": state,
    }


def _c1_shape() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    census: list[dict[str, str]] = []
    obs: list[dict[str, str]] = []
    for index in range(C1_EXPECTED["base_x_n"]):
        mint = f"mint{index:04d}"
        denom = (
            "observed"
            if index < C1_EXPECTED["lifecycle_observed_n"]
            else "censored_late"
        )
        census.append(_census(mint, denom))
        obs.append(_x300(mint))
        if denom == "censored_late":
            obs.append(_y(mint, "Y86400", "FIELD-USD-PRICE-001", "CENSORED_LATE"))
        else:
            obs.append(_y(mint, "Y86400", "FIELD-USD-PRICE-001", "OBSERVED"))
    return census, obs


class ScientificEligibilityProjectionTests(unittest.TestCase):
    def test_c1_shape_base_x_is_denominator(self) -> None:
        census, obs = _c1_shape()
        projected = project_scientific_eligibility(census, obs)
        assert_c1_shape(projected)
        self.assertEqual(projected["outcome_readiness"], READINESS_UNSPECIFIED)
        self.assertEqual(projected["lifecycle_coverage"]["denominator_n"], 475)
        self.assertEqual(
            projected["lifecycle_coverage"]["n_observed"]
            + projected["lifecycle_coverage"]["n_censored_late"],
            475,
        )

    def test_late_x300_excluded_from_base_x(self) -> None:
        census = [_census("a", "observed"), _census("b", "observed")]
        obs = [_x300("a"), _x300("b", late=True)]
        projected = project_scientific_eligibility(census, obs)
        self.assertEqual(projected["base_x_population"]["n"], 1)

    def test_y_late_does_not_shrink_base_x(self) -> None:
        census = [_census("a", "censored_late")]
        obs = [
            _x300("a"),
            _y("a", "Y900", "FIELD-USD-PRICE-001", "CENSORED_LATE"),
        ]
        projected = project_scientific_eligibility(
            census,
            obs,
            spec={
                "schema_version": "1.3",
                "required_outcomes": [
                    {
                        "point_id": "Y900",
                        "field_ids": ["FIELD-USD-PRICE-001"],
                        "role": "PRIMARY",
                    }
                ],
            },
        )
        self.assertEqual(projected["base_x_population"]["n"], 1)
        self.assertEqual(projected["outcome_readiness"], READINESS_COMPLETE)
        self.assertEqual(projected["outcome_coverage"][0]["n_censored_late"], 1)
        self.assertEqual(projected["outcome_coverage"][0]["denominator_n"], 1)

    def test_absent_required_outcome_is_unresolved_not_smaller_n(self) -> None:
        census = [_census("a", "observed")]
        obs = [_x300("a")]
        projected = project_scientific_eligibility(
            census,
            obs,
            spec={
                "schema_version": "1.3",
                "required_outcomes": [
                    {
                        "point_id": "Y900",
                        "field_ids": ["FIELD-USD-PRICE-001"],
                        "role": "PRIMARY",
                    }
                ],
            },
        )
        self.assertEqual(projected["base_x_population"]["n"], 1)
        self.assertEqual(projected["outcome_readiness"], READINESS_MISSINGNESS_UNRESOLVED)
        self.assertEqual(projected["outcome_coverage"][0]["n_absent"], 1)

    def test_y_typed_value_guard(self) -> None:
        with self.assertRaises(ScientificEligibilityError) as raised:
            y_columns_forbidden(
                {"point_id": "Y900", "typed_value": "1.23", "state": "OBSERVED"}
            )
        self.assertEqual(str(raised.exception), "Y_TYPED_VALUE_READ")

    def test_full_lifecycle_equivalence_is_exact_set(self) -> None:
        schedule = ["Y900", "Y1800", "Y86400"]
        self.assertFalse(full_lifecycle_scope_equivalent(["Y900"], schedule))
        self.assertFalse(full_lifecycle_scope_equivalent(None, schedule))
        self.assertTrue(full_lifecycle_scope_equivalent(schedule, schedule))

    def test_selection_receipt_is_caveat_not_global_stop(self) -> None:
        receipt = {
            "router_decision": BLOCK_FORGE_SELECTION_RISK,
            "receipt_sha256": "a" * 64,
        }
        scoped = interpret_selection_gate_receipt(receipt)
        self.assertEqual(scoped["eligibility_scope"], ELIGIBILITY_SCOPE_FULL_LIFECYCLE)
        view = apply_selection_gate_to_preflight("START_NEW_SESSION", receipt)
        self.assertEqual(view["action"], "START_NEW_SESSION")
        self.assertTrue(view["caveat"])
        self.assertEqual(view["eligibility_scope"], ELIGIBILITY_SCOPE_FULL_LIFECYCLE)
        veto = apply_selection_gate_to_preflight(
            "START_NEW_SESSION",
            receipt,
            required_outcome_point_ids=("Y900", "Y1800"),
            schedule_y_point_ids=("Y900", "Y1800"),
        )
        self.assertEqual(veto["action"], "STOP")
        self.assertEqual(veto["router_decision"], BLOCK_FORGE_SELECTION_RISK)

    def test_caveat_pass_through(self) -> None:
        receipt = {
            "router_decision": FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
            "receipt_sha256": "b" * 64,
        }
        view = apply_selection_gate_to_preflight("START_NEW_SESSION", receipt)
        self.assertEqual(view["action"], "START_NEW_SESSION")
        self.assertTrue(view["caveat"])

    def test_min_usable_base_x_is_owned_here(self) -> None:
        self.assertEqual(MIN_USABLE_BASE_X_POPULATION, 10)

    def test_1_3_missing_readiness_is_unresolved(self) -> None:
        from solana_alpha_lab.factory.lane_classifier import (
            _submission_outcome_readiness,
        )
        from solana_alpha_lab.factory.run_passport import canonical_sha256

        spec = {
            "schema_version": "1.3",
            "required_outcomes": [
                {
                    "point_id": "Y900",
                    "field_ids": ["FIELD-USD-PRICE-001"],
                    "role": "PRIMARY",
                }
            ],
        }
        self.assertEqual(
            _submission_outcome_readiness(spec, {}),
            READINESS_MISSINGNESS_UNRESOLVED,
        )
        self.assertEqual(
            _submission_outcome_readiness(
                spec,
                {"outcome_readiness": READINESS_COMPLETE},
            ),
            READINESS_MISSINGNESS_UNRESOLVED,
        )
        bound = project_scientific_eligibility(
            [_census("a", "observed")],
            [
                _x300("a"),
                _y("a", "Y900", "FIELD-USD-PRICE-001", "OBSERVED"),
            ],
            spec=spec,
        )
        self.assertEqual(bound["experiment_spec_sha256"], canonical_sha256(spec))
        self.assertEqual(
            _submission_outcome_readiness(
                spec,
                {"scientific_eligibility_projection": bound},
            ),
            READINESS_COMPLETE,
        )
        self.assertEqual(
            _submission_outcome_readiness({"schema_version": "1.2"}, {}),
            READINESS_UNSPECIFIED,
        )

    def test_duplicate_census_does_not_inflate_lifecycle(self) -> None:
        census = [_census("a", "observed"), _census("a", "censored_late")]
        obs = [_x300("a"), _x300("a")]
        projected = project_scientific_eligibility(census, obs)
        self.assertEqual(projected["base_x_population"]["n"], 1)
        self.assertEqual(projected["lifecycle_coverage"]["n_observed"], 1)
        self.assertEqual(projected["lifecycle_coverage"]["n_censored_late"], 0)

    def test_later_x300_observed_wins(self) -> None:
        census = [_census("a", "observed")]
        late_ok = _x300("a")
        earlier_missing = _x300("a")
        earlier_missing["state"] = "MISSING_TYPED"
        earlier_missing["first_reliable_available_at"] = ANCHOR.isoformat().replace(
            "+00:00", "Z"
        )
        projected = project_scientific_eligibility(
            census, [earlier_missing, late_ok]
        )
        self.assertEqual(projected["base_x_population"]["n"], 1)

    def test_control_yield_projects_rows_without_label(self) -> None:
        from solana_alpha_lab.factory.hfic_control_integrity import (
            resolve_control_corpus_yield,
        )
        from solana_alpha_lab.factory.live_cohort_discovery_release import (
            CORPUS_DATASET_ID,
        )

        census = [_census(f"m{i}", "observed") for i in range(10)]
        obs = [_x300(f"m{i}") for i in range(10)]
        gate, observed = resolve_control_corpus_yield(
            [
                {
                    "dataset_id": CORPUS_DATASET_ID,
                    "yield_eligible": 99,
                    "census_rows": census,
                    "observation_rows": obs,
                }
            ],
            corpus_dataset_id=CORPUS_DATASET_ID,
            min_usable_yield_eligible=MIN_USABLE_BASE_X_POPULATION,
        )
        self.assertEqual(gate, "OK")
        self.assertEqual(observed, 10)

    def test_caller_offset_kwargs_cannot_widen_factory_pit(self) -> None:
        census = [_census("a", "observed")]
        projected = project_scientific_eligibility(
            census,
            [_x300("a", late=True)],
            x_due_offset_seconds=300,
            x_allowed_lateness_seconds=10_000,
        )
        self.assertEqual(projected["base_x_population"]["n"], 0)

    def test_late_x300_duplicate_does_not_evict_timely_observed(self) -> None:
        census = [_census("a", "observed")]
        timely = _x300("a")
        late_missing = _x300("a", late=True)
        late_missing["state"] = "MISSING_TYPED"
        projected = project_scientific_eligibility(
            census, [timely, late_missing]
        )
        self.assertEqual(projected["base_x_population"]["n"], 1)
        reversed_order = project_scientific_eligibility(
            census, [late_missing, timely]
        )
        self.assertEqual(reversed_order["base_x_population"]["n"], 1)

    def test_experiment_x300_offsets_do_not_widen_factory_pit(self) -> None:
        census = [_census("a", "observed")]
        projected = project_scientific_eligibility(
            census,
            [_x300("a", late=True)],
            schedule={
                "x_point": {
                    "point_id": X_POINT_ID,
                    "due_offset_seconds": 300,
                    "allowed_lateness_seconds": 10_000,
                }
            },
        )
        self.assertEqual(projected["base_x_population"]["n"], 0)
        self.assertEqual(
            projected["base_x_population"]["x_allowed_lateness_seconds"],
            X_ALLOWED_LATENESS_SECONDS,
        )

    def test_non_x300_schedule_does_not_move_pit(self) -> None:
        census = [_census("a", "observed")]
        obs = [_x300("a")]
        projected = project_scientific_eligibility(
            census,
            obs,
            schedule={
                "x_point": {
                    "point_id": "X900",
                    "due_offset_seconds": 1,
                    "allowed_lateness_seconds": 0,
                }
            },
        )
        self.assertEqual(projected["base_x_population"]["n"], 1)
        self.assertEqual(
            projected["base_x_population"]["x_due_offset_seconds"],
            X_DUE_OFFSET_SECONDS,
        )

    def test_equivalent_evidence_gap_is_scoped_stop(self) -> None:
        from solana_alpha_lab.factory.hfic_selection_robustness_gate import (
            BLOCK_FORGE_EVIDENCE_GAP,
        )

        receipt = {
            "router_decision": BLOCK_FORGE_EVIDENCE_GAP,
            "receipt_sha256": "c" * 64,
        }
        view = apply_selection_gate_to_preflight(
            "START_NEW_SESSION",
            receipt,
            required_outcome_point_ids=("Y900", "Y1800"),
            schedule_y_point_ids=("Y900", "Y1800"),
        )
        self.assertEqual(view["action"], "STOP")
        self.assertEqual(view["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)

    def test_forged_complete_stamp_is_unresolved(self) -> None:
        from solana_alpha_lab.factory.lane_classifier import (
            _submission_outcome_readiness,
        )

        spec = {
            "schema_version": "1.3",
            "required_outcomes": [
                {
                    "point_id": "Y900",
                    "field_ids": ["FIELD-USD-PRICE-001"],
                    "role": "PRIMARY",
                }
            ],
        }
        fake = {
            "schema": "smial.scientific-eligibility-projection",
            "schema_version": "1.0",
            "rule_id": "BASE_X_X300_VALID_X_ELIGIBLE_V1",
            "experiment_spec_sha256": "0" * 64,
            "outcome_readiness": READINESS_COMPLETE,
            "projection_sha256": "0" * 64,
        }
        self.assertEqual(
            _submission_outcome_readiness(
                spec, {"scientific_eligibility_projection": fake}
            ),
            READINESS_MISSINGNESS_UNRESOLVED,
        )

    def test_empty_base_x_is_not_complete(self) -> None:
        projected = project_scientific_eligibility(
            [_census("a", "observed", candidate="NOT_ELIGIBLE")],
            [_x300("a")],
            spec={
                "schema_version": "1.3",
                "required_outcomes": [
                    {
                        "point_id": "Y900",
                        "field_ids": ["FIELD-USD-PRICE-001"],
                        "role": "PRIMARY",
                    }
                ],
            },
        )
        self.assertEqual(projected["base_x_population"]["n"], 0)
        self.assertEqual(projected["outcome_readiness"], READINESS_MISSINGNESS_UNRESOLVED)

    def test_control_prefers_live_rows_over_stamp(self) -> None:
        from solana_alpha_lab.factory.hfic_control_integrity import (
            CONTROL_YIELD_BELOW_MIN,
            resolve_control_corpus_yield,
        )
        from solana_alpha_lab.factory.live_cohort_discovery_release import (
            CORPUS_DATASET_ID,
        )

        census = [_census("a", "observed")]
        obs = [_x300("a")]
        gate, observed = resolve_control_corpus_yield(
            [
                {
                    "dataset_id": CORPUS_DATASET_ID,
                    "base_x_population_n": 99,
                    "labels": {"base_x_population_n": 99},
                    "census_rows": census,
                    "observation_rows": obs,
                }
            ],
            corpus_dataset_id=CORPUS_DATASET_ID,
            min_usable_yield_eligible=MIN_USABLE_BASE_X_POPULATION,
        )
        self.assertEqual(gate, CONTROL_YIELD_BELOW_MIN)
        self.assertEqual(observed, 1)

    def test_experiment_own_y_points_do_not_make_full_lifecycle(self) -> None:
        bound = bound_schedule_y_point_ids(ROOT)
        self.assertIn("Y900", bound)
        self.assertIn("Y86400", bound)
        self.assertFalse(full_lifecycle_scope_equivalent(("Y900",), bound))
        view = apply_selection_gate_to_preflight(
            "START_NEW_SESSION",
            {
                "router_decision": BLOCK_FORGE_SELECTION_RISK,
                "receipt_sha256": "a" * 64,
            },
            required_outcome_point_ids=("Y900",),
            schedule_y_point_ids=bound,
        )
        self.assertEqual(view["action"], "START_NEW_SESSION")
        self.assertTrue(view["caveat"])
        self.assertFalse(view.get("full_lifecycle_equivalent"))

    def test_later_y_state_wins_regardless_of_file_order(self) -> None:
        census = [_census("a", "observed")]
        earlier = _y("a", "Y900", "FIELD-USD-PRICE-001", "OBSERVED")
        earlier["first_reliable_available_at"] = ANCHOR.isoformat().replace(
            "+00:00", "Z"
        )
        later = _y("a", "Y900", "FIELD-USD-PRICE-001", "CENSORED_LATE")
        later["first_reliable_available_at"] = (
            ANCHOR + timedelta(seconds=900)
        ).isoformat().replace("+00:00", "Z")
        spec = {
            "schema_version": "1.3",
            "required_outcomes": [
                {
                    "point_id": "Y900",
                    "field_ids": ["FIELD-USD-PRICE-001"],
                    "role": "PRIMARY",
                }
            ],
        }
        first = project_scientific_eligibility(
            census, [_x300("a"), later, earlier], spec=spec
        )
        second = project_scientific_eligibility(
            census, [_x300("a"), earlier, later], spec=spec
        )
        self.assertEqual(first["outcome_coverage"][0]["n_censored_late"], 1)
        self.assertEqual(second["outcome_coverage"][0]["n_censored_late"], 1)
        self.assertEqual(first["outcome_coverage"][0]["n_observed"], 0)

    def test_horizon_spec_is_not_auto_vetoed(self) -> None:
        receipt = {
            "router_decision": BLOCK_FORGE_SELECTION_RISK,
            "receipt_sha256": "a" * 64,
        }
        view = apply_selection_gate_to_preflight(
            "START_NEW_SESSION",
            receipt,
            required_outcome_point_ids=("Y900",),
            schedule_y_point_ids=("Y900", "Y1800", "Y86400"),
        )
        self.assertEqual(view["action"], "START_NEW_SESSION")
        self.assertTrue(view["caveat"])

    def test_control_yield_requires_base_x_field(self) -> None:
        from solana_alpha_lab.factory.hfic_control_integrity import (
            CONTROL_CORPUS_UNRESOLVABLE,
            resolve_control_corpus_yield,
        )
        from solana_alpha_lab.factory.live_cohort_discovery_release import (
            CORPUS_DATASET_ID,
        )

        gate, observed = resolve_control_corpus_yield(
            [
                {
                    "dataset_id": CORPUS_DATASET_ID,
                    "yield_eligible": 99,
                    "labels": {"yield_eligible": 99},
                }
            ],
            corpus_dataset_id=CORPUS_DATASET_ID,
            min_usable_yield_eligible=MIN_USABLE_BASE_X_POPULATION,
        )
        self.assertEqual(gate, CONTROL_CORPUS_UNRESOLVABLE)
        self.assertIsNone(observed)

    def test_experiment_spec_1_3_requires_required_outcomes(self) -> None:
        with self.assertRaises(ExperimentSpecError):
            validate_experiment_document(
                {
                    "schema": "smial.experiment-spec",
                    "schema_version": "1.3",
                    "experiment_id": "EXP-HORIZON-SCOPED-Y900-001",
                    "hypothesis_version": "HYP-HORIZON-SCOPED-Y900-V1",
                    "question": "Does X300 liquidity predict Y900 price coverage?",
                    "estimand": "Y900 price coverage on X300-valid X_ELIGIBLE",
                    "population": "X300_VALID_X_ELIGIBLE",
                    "data_requirements": [
                        {
                            "requirement_id": "LIVE_CORPUS",
                            "kind": "CATALOG_ASSET",
                            "path": "configs/scientific_eligibility_projection_v1.yaml",
                            "sha256": "0" * 64,
                        }
                    ],
                    "capabilities": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
                    "falsifier": "Y900 rows absent or readiness unresolved.",
                    "method": "coverage_count",
                    "parameters": {},
                    "evidence_budget": {"provider_api_rpc_wss_calls": 0},
                    "holdout_policy": "No holdout is opened in this fixture.",
                    "terminal_outcomes": ["OUTCOME_COVERAGE_COMPLETE"],
                },
                root=ROOT,
            )


if __name__ == "__main__":
    unittest.main()
