"""Hermetic A/B vertical slice for HORIZON_SCOPED_SCIENTIFIC_ELIGIBILITY_V1."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_selection_robustness_gate import (
    BLOCK_FORGE_SELECTION_RISK,
    apply_selection_gate_to_preflight,
    load_applicable_gate_receipt,
    persist_gate_receipt,
)
from solana_alpha_lab.factory.hfic_session import _classifier_to_hfic_terminal
from solana_alpha_lab.factory.lane_classifier import Lane, classify_lane
from solana_alpha_lab.factory.observation_schedule import load_observation_schedule
from solana_alpha_lab.factory.scientific_eligibility_projection import (
    CANONICAL_RELEASE_IDENTITY_UNBOUND,
    CANONICAL_X300_SCHEDULE_INCOMPATIBLE,
    READINESS_COMPLETE,
    READINESS_MISSINGNESS_UNRESOLVED,
    ScientificEligibilityError,
    X_ALLOWED_LATENESS_SECONDS,
    X_DUE_OFFSET_SECONDS,
    X_FIELD_ID,
    X_POINT_ID,
    bound_schedule_y_point_ids,
    project_scientific_eligibility,
    try_project_scientific_eligibility_from_data_root,
    y_columns_forbidden,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (
    CENSUS_RELEASE_SCHEMA,
    OBS_RELEASE_SCHEMA,
)
from tests.test_hfic_censoring_ignorability_diagnostic_v1 import (
    FROZEN_COHORT,
    FROZEN_DATASET,
    FROZEN_RELEASE,
    PRICE,
    _census_row,
    _obs_row,
    _partition_rels,
    _publish_dataset,
    _write_lineage,
    _write_parquet,
    sha256_file_streaming,
)
from tests.test_hfic_selection_robustness_gate_v1 import (
    _hashed_gate_receipt,
    _identity_fields,
)
from tests.test_observation_fast_lane_routing_closure import (
    AS_OF_START,
    HYPOTHESIS_DEFINITION_SHA256,
    packet_for,
    persist_active_schedule,
    v1_2_spec,
)
from tests.test_scientific_eligibility_projection_v1 import ANCHOR, _x300, _y

MINT = "mint-vertical-001"
PRICE_FIELD = PRICE


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _member_rows(schedule_sha256: str, activation_id: str) -> tuple[list[dict], list[dict]]:
    x_at = ANCHOR + timedelta(seconds=X_DUE_OFFSET_SECONDS)
    census = [
        _census_row(
            mint=MINT,
            candidate_state="X_ELIGIBLE",
            denominator_state="censored_late",
            authoritative_anchor=_iso(ANCHOR),
            discovery_first_reliable_available_at=_iso(ANCHOR),
            inclusion_probability="1.0",
            cohort_id=FROZEN_COHORT,
            release_id=FROZEN_RELEASE,
            source_schedule_sha256=schedule_sha256,
            activation_id=activation_id,
        )
    ]
    obs = [
        _obs_row(
            mint=MINT,
            field_id=X_FIELD_ID,
            typed_value="1000",
            state="OBSERVED",
            point_id=X_POINT_ID,
            value_kind="DECIMAL",
            first_reliable_available_at=_iso(x_at),
            cohort_id=FROZEN_COHORT,
            release_id=FROZEN_RELEASE,
        ),
        _obs_row(
            mint=MINT,
            field_id=PRICE_FIELD,
            typed_value="0.01",
            state="OBSERVED",
            point_id="Y900",
            value_kind="DECIMAL",
            first_reliable_available_at=_iso(ANCHOR + timedelta(seconds=900)),
            cohort_id=FROZEN_COHORT,
            release_id=FROZEN_RELEASE,
        ),
        _obs_row(
            mint=MINT,
            field_id=PRICE_FIELD,
            typed_value=None,
            state="CENSORED_LATE",
            point_id="Y86400",
            value_kind="DECIMAL",
            first_reliable_available_at=_iso(ANCHOR + timedelta(seconds=90000)),
            cohort_id=FROZEN_COHORT,
            release_id=FROZEN_RELEASE,
        ),
    ]
    return census, obs


def _install_vertical_corpus(
    data_root: Path,
    *,
    schedule_sha256: str,
    activation_id: str,
) -> dict[str, str]:
    census_rows, obs_rows = _member_rows(schedule_sha256, activation_id)
    staging = data_root / "_fixture"
    staging.mkdir(parents=True, exist_ok=True)
    census_src = staging / "census.parquet"
    obs_src = staging / "observations.parquet"
    _write_parquet(census_src, census_rows, CENSUS_RELEASE_SCHEMA)
    _write_parquet(obs_src, obs_rows, OBS_RELEASE_SCHEMA)
    census_rel, obs_rel = _partition_rels(FROZEN_COHORT, FROZEN_RELEASE)
    census_path = data_root / census_rel
    obs_path = data_root / obs_rel
    census_path.parent.mkdir(parents=True, exist_ok=True)
    census_path.write_bytes(census_src.read_bytes())
    obs_path.write_bytes(obs_src.read_bytes())
    census_sha = sha256_file_streaming(census_path)
    obs_sha = sha256_file_streaming(obs_path)
    dataset_version = f"corpus-v1-{FROZEN_COHORT}"
    manifest_id = _publish_dataset(
        data_root,
        dataset_id=FROZEN_DATASET,
        dataset_version=dataset_version,
        census_rel=census_rel,
        obs_rel=obs_rel,
        census_sha=census_sha,
        obs_sha=obs_sha,
        census_n=1,
        obs_n=3,
        cohort_id=FROZEN_COHORT,
    )
    _write_lineage(
        data_root,
        dataset_id=FROZEN_DATASET,
        current_mid=manifest_id,
        cohorts=[
            {
                "cohort_id": FROZEN_COHORT,
                "release_id": FROZEN_RELEASE,
                "census_rel": census_rel,
                "obs_rel": obs_rel,
                "census_sha256": census_sha,
                "observations_sha256": obs_sha,
                "corpus_version": 1,
                "dataset_manifest_id": manifest_id,
                "dataset_version": dataset_version,
            }
        ],
    )
    return {
        "census_sha256": census_sha,
        "observations_sha256": obs_sha,
        "dataset_manifest_id": manifest_id,
        "census_path": str(census_path),
        "obs_path": str(obs_path),
    }


def _v1_3_spec(point_id: str, *, widen_x_lateness: bool = False) -> dict:
    spec = v1_2_spec(fixture="common_panel.yaml")
    spec["schema_version"] = "1.3"
    spec["required_outcomes"] = [
        {
            "point_id": point_id,
            "field_ids": [PRICE_FIELD],
            "role": "PRIMARY",
        }
    ]
    if widen_x_lateness:
        request = dict(spec["observation_request"])
        x_point = dict(request["x_point"])
        x_point["allowed_lateness_seconds"] = 10_000
        request["x_point"] = x_point
        spec["observation_request"] = request
    return spec


def _persist_valid_receipt(data_root: Path, installed: dict[str, str]) -> dict:
    receipt = _hashed_gate_receipt(
        BLOCK_FORGE_SELECTION_RISK,
        **_identity_fields(installed),
    )
    persist_gate_receipt(data_root, receipt)
    return receipt


class HorizonEligibilityVerticalSliceTests(unittest.TestCase):
    def test_case_a_unrelated_future_y_does_not_block(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, covering)
            installed = _install_vertical_corpus(
                data_root,
                schedule_sha256=str(covering["schedule_sha256"]),
                activation_id="ACT-OBS-ROUTING-001",
            )
            _persist_valid_receipt(data_root, installed)
            spec = _v1_3_spec("Y900", widen_x_lateness=True)
            projected = try_project_scientific_eligibility_from_data_root(
                data_root, repo_root=ROOT, spec=spec, schedule=spec["observation_request"]
            )
            self.assertIsNotNone(projected)
            assert projected is not None
            self.assertEqual(projected["base_x_population"]["n"], 1)
            self.assertEqual(projected["outcome_readiness"], READINESS_COMPLETE)
            self.assertEqual(projected["outcome_coverage"][0]["n_observed"], 1)
            self.assertEqual(projected["lifecycle_coverage"]["n_censored_late"], 1)
            self.assertEqual(
                projected["base_x_population"]["x_allowed_lateness_seconds"],
                X_ALLOWED_LATENESS_SECONDS,
            )
            selection = apply_selection_gate_to_preflight(
                "START_NEW_SESSION",
                load_applicable_gate_receipt(data_root, root=ROOT),
                required_outcome_point_ids=("Y900",),
                schedule_y_point_ids=bound_schedule_y_point_ids(ROOT),
            )
            self.assertEqual(selection["action"], "START_NEW_SESSION")
            self.assertTrue(selection["caveat"])
            self.assertFalse(selection.get("full_lifecycle_equivalent"))
            decision = classify_lane(
                packet_for(spec),
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF_START,
            )
            self.assertNotEqual(decision.terminal, "FAST_LANE_READY")
            self.assertNotEqual(decision.reason_codes, ("OUTCOME_MISSINGNESS_UNRESOLVED",))
            self.assertNotEqual(decision.next_action, "REPORT_OUTCOME_COVERAGE_KEEP_BASE_X")
            late = project_scientific_eligibility(
                [
                    {
                        "mint": MINT,
                        "candidate_state": "X_ELIGIBLE",
                        "denominator_state": "censored_late",
                        "authoritative_anchor": _iso(ANCHOR),
                    }
                ],
                [_x300(MINT, late=True), _y(MINT, "Y900", PRICE_FIELD, "OBSERVED")],
                spec=spec,
                schedule=spec["observation_request"],
            )
            self.assertEqual(late["base_x_population"]["n"], 0)

    def test_case_b_required_y_missing_fail_closes_keep_n(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, covering)
            installed = _install_vertical_corpus(
                data_root,
                schedule_sha256=str(covering["schedule_sha256"]),
                activation_id="ACT-OBS-ROUTING-001",
            )
            _persist_valid_receipt(data_root, installed)
            spec = _v1_3_spec("Y86400")
            projected = try_project_scientific_eligibility_from_data_root(
                data_root, repo_root=ROOT, spec=spec
            )
            self.assertIsNotNone(projected)
            assert projected is not None
            coverage = projected["outcome_coverage"][0]
            self.assertEqual(projected["base_x_population"]["n"], 1)
            self.assertEqual(coverage["denominator_n"], 1)
            self.assertEqual(coverage["n_censored_late"], 1)
            self.assertEqual(projected["outcome_readiness"], READINESS_MISSINGNESS_UNRESOLVED)
            decision = classify_lane(
                packet_for(spec),
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF_START,
            )
            self.assertNotEqual(decision.terminal, "FAST_LANE_READY")
            self.assertEqual(decision.lane, Lane.FAST_LANE)
            self.assertEqual(decision.terminal, "BLOCKED_DATA")
            self.assertEqual(decision.reason_codes, ("OUTCOME_MISSINGNESS_UNRESOLVED",))
            self.assertEqual(decision.next_action, "REPORT_OUTCOME_COVERAGE_KEEP_BASE_X")
            self.assertEqual(
                _classifier_to_hfic_terminal(
                    {"lane_classifier_terminal": decision.terminal}
                ),
                "PASS_DATA_OPTION_REQUIRED",
            )

    def test_negative_canonical_schedule_mismatch_and_selection_rules(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        mismatched = dict(covering)
        mismatched["x_point"] = dict(covering["x_point"])
        mismatched["x_point"]["allowed_lateness_seconds"] = 10_000
        from solana_alpha_lab.factory.observation_schedule import schedule_sha256

        mismatched.pop("schedule_sha256", None)
        mismatched["schedule_sha256"] = schedule_sha256(mismatched)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, mismatched)
            _install_vertical_corpus(
                data_root,
                schedule_sha256=str(mismatched["schedule_sha256"]),
                activation_id="ACT-OBS-ROUTING-001",
            )
            with self.assertRaises(ScientificEligibilityError) as raised:
                try_project_scientific_eligibility_from_data_root(
                    data_root, repo_root=ROOT
                )
            self.assertEqual(str(raised.exception), CANONICAL_X300_SCHEDULE_INCOMPATIBLE)

        bound = bound_schedule_y_point_ids(ROOT)
        view = apply_selection_gate_to_preflight(
            "START_NEW_SESSION",
            {
                "router_decision": BLOCK_FORGE_SELECTION_RISK,
                "receipt_sha256": "a" * 64,
            },
            required_outcome_point_ids=bound,
            schedule_y_point_ids=bound,
        )
        self.assertEqual(view["action"], "START_NEW_SESSION")
        self.assertTrue(view["caveat"])
        self.assertFalse(view.get("full_lifecycle_equivalent"))

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, covering)
            installed = _install_vertical_corpus(
                data_root,
                schedule_sha256=str(covering["schedule_sha256"]),
                activation_id="ACT-OBS-ROUTING-001",
            )
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    BLOCK_FORGE_SELECTION_RISK,
                    **_identity_fields(installed, census_sha256="ab" * 32),
                ),
            )
            loaded = load_applicable_gate_receipt(data_root, root=ROOT)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded.get("integrity_invalid"))
            spec = _v1_3_spec("Y900")
            decision = classify_lane(
                packet_for(spec),
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF_START,
            )
            self.assertEqual(decision.terminal, "BLOCKED_DATA")
            self.assertEqual(
                decision.reason_codes, ("SELECTION_RECEIPT_INTEGRITY_INVALID",)
            )

        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, covering)
            spec = _v1_3_spec("Y900")
            self.assertIsNone(
                try_project_scientific_eligibility_from_data_root(
                    data_root, repo_root=ROOT, spec=spec
                )
            )
            decision = classify_lane(
                packet_for(spec),
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF_START,
            )
            self.assertEqual(decision.terminal, "BLOCKED_DATA")
            self.assertEqual(
                decision.reason_codes, (CANONICAL_RELEASE_IDENTITY_UNBOUND,)
            )
            self.assertEqual(decision.next_action, "RESOLVE_IMMUTABLE_DATA_BINDINGS")

    def test_projection_never_selects_y_typed_values(self) -> None:
        with self.assertRaises(ScientificEligibilityError):
            y_columns_forbidden(
                {"point_id": "Y900", "typed_value": "1.23", "state": "OBSERVED"}
            )


if __name__ == "__main__":
    unittest.main()
