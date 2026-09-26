"""Synthetic grounded-discovery proof. No live typed values and no market Forge."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    CALCULATION_VERSION,
    ORDINARY_GROUNDED_DISCOVERY_V1,
    GroundedDiscoveryError,
    admit_discovery_binding,
    bind_prior_scope_evidence,
    classify_query_look,
    execute_discovery_from_rows,
    format_discovery_readout,
    prior_scope_relation,
    run_recorded_discovery_query,
    summarize_discovery_query,
    validate_query_spec,
)
from solana_alpha_lab.factory.hfic_identity import (  # noqa: E402
    canonical_candidate_definition,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    _enforce_ordinary_grounded_evidence,
    _ordinary_discovery_requested,
    freeze_draft,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402

PRICE = "FIELD-USD-PRICE-001"
LIQ = "FIELD-LIQUIDITY-USD-001"
SPEC = {
    "query_id": "X300_PRICE_LIQ_TO_Y1800",
    "decision_points": ["X300"],
    "decision_fields": [PRICE, LIQ],
    "target_point": "Y1800",
    "target_field": PRICE,
    "explanatory": ["liquidity_high"],
    "population": "BASE_X",
}


def _member(
    member_id: str,
    *,
    cohort: str,
    block: str,
    target: float | None,
    flag: bool,
    state: str = "OBSERVED",
    leaked: bool = False,
    in_base: bool = True,
    decision_ready: bool = True,
) -> dict:
    return {
        "member_id": member_id,
        "cohort_id": cohort,
        "calendar_block": block,
        "in_base_x": in_base,
        "decision_ready": decision_ready,
        "decision_at": "2026-09-03T00:00:00+00:00",
        "target_state": state,
        "target_at": (
            "2026-09-03T00:00:00+00:00"
            if leaked
            else "2026-09-03T00:30:00+00:00"
        ),
        "synthetic_target": target,
        "explanatory": {"liquidity_high": flag},
    }


class GroundedDiscoveryTests(unittest.TestCase):
    def test_spec_rejects_cohort_feature_and_early_target(self) -> None:
        with self.assertRaises(GroundedDiscoveryError) as cohort:
            validate_query_spec({**SPEC, "explanatory": ["cohort_id"]})
        self.assertEqual(cohort.exception.code, "COHORT_NOT_A_FEATURE")
        with self.assertRaises(GroundedDiscoveryError) as early:
            validate_query_spec({**SPEC, "target_point": "X300"})
        self.assertEqual(early.exception.code, "TARGET_NOT_AFTER_DECISION")

    def test_binding_stops_on_ambiguous_role_before_values(self) -> None:
        with self.assertRaises(GroundedDiscoveryError) as exc:
            admit_discovery_binding(
                [
                    {
                        "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
                        "evidence_role": "UNSPECIFIED",
                        "cohort_id": "REL-A",
                        "release_id": "ab" * 32,
                        "census_sha256": "cd" * 32,
                        "observations_sha256": "ef" * 32,
                    }
                ]
            )
        self.assertEqual(exc.exception.code, "DISCOVERY_ROLE_AMBIGUOUS")

    def test_pooled_hides_conditional_and_blocks_accumulate(self) -> None:
        members = [
            _member("a", cohort="C1", block="B1", target=1.0, flag=True),
            _member("b", cohort="C1", block="B1", target=-1.0, flag=False),
            _member("c", cohort="C2", block="B2", target=1.0, flag=True),
            _member("d", cohort="C2", block="B2", target=-1.0, flag=False),
            _member("noise", cohort="C1", block="B1", target=None, flag=True, in_base=False),
        ]
        result = summarize_discovery_query(members, SPEC, overlap_members=[])
        self.assertTrue(result["pooled"]["independent_replication"])
        self.assertFalse(result["engine_emits_alpha"])
        self.assertEqual(result["base_x_n"], 4)
        self.assertEqual(result["pooled"]["mean_synthetic_target"], 0.0)
        high = next(item for item in result["by_explanatory"] if item["view"] == "liquidity_high=True")
        low = next(item for item in result["by_explanatory"] if item["view"] == "liquidity_high=False")
        self.assertEqual(high["mean_synthetic_target"], 1.0)
        self.assertEqual(low["mean_synthetic_target"], -1.0)
        self.assertEqual(len(result["by_calendar_block"]), 2)
        self.assertEqual(
            sum(item["target_observed_after_decision"] for item in result["by_calendar_block"]),
            4,
        )

    def test_null_missing_and_leakage_do_not_become_a_positive(self) -> None:
        members = [
            _member("n1", cohort="C1", block="B1", target=0.0, flag=False),
            _member("n2", cohort="C1", block="B1", target=0.0, flag=False),
            _member("miss", cohort="C1", block="B1", target=99.0, flag=False, state="MISSING_TYPED"),
            _member("late", cohort="C1", block="B1", target=99.0, flag=False, state="CENSORED_LATE"),
            _member("leak", cohort="C1", block="B1", target=99.0, flag=False, leaked=True),
            _member("gone", cohort="C1", block="B1", target=99.0, flag=False, state="ABSENT"),
        ]
        result = summarize_discovery_query(members, SPEC)
        self.assertFalse(result["pooled"]["independent_replication"])
        self.assertEqual(result["pooled"]["mean_synthetic_target"], 0.0)
        self.assertEqual(result["pooled"]["target_observed_after_decision"], 2)
        self.assertEqual(result["missing"]["missing_typed"], 1)
        self.assertEqual(result["missing"]["censored_late"], 1)
        self.assertEqual(result["missing"]["leaked"], 1)
        self.assertEqual(result["missing"]["absent"], 1)
        self.assertTrue(result["missing_is_not_zero"])

    def test_price_liquidity_query_does_not_require_traders(self) -> None:
        bound = validate_query_spec(SPEC)
        self.assertNotIn("FIELD-STATS5M-NUM-TRADERS-001", bound["decision_fields"])
        result = summarize_discovery_query(
            [_member("p", cohort="C1", block="B1", target=0.2, flag=True)],
            SPEC,
        )
        self.assertEqual(result["pooled"]["target_observed_after_decision"], 1)

    def test_overlap_is_not_independent_replication(self) -> None:
        result = summarize_discovery_query(
            [_member("o", cohort="C3", block="OVERLAP", target=1.0, flag=True)],
            SPEC,
            overlap_members=["o"],
        )
        self.assertTrue(result["overlap_is_not_independent_replication"])
        self.assertEqual(result["overlap_exposed_base_x"], 1)
        self.assertFalse(result["by_calendar_block"][0]["independent_replication"])

    def test_control_scope_does_not_block_a_different_question(self) -> None:
        prior = {
            "question_id": "HFIC-CAND-2E0C5E5A8ABC",
            "population": "BASE_X",
            "decision_timestamp": "X300",
            "target": "Y1800_REPORTED_PRICE_PATH",
            "estimand": "ticket_asymmetry",
            "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
            "representation_scope": CURRENT_REPRESENTATION_CONTROL_V1,
            "explanatory_condition": "PRICE_GE_2",
            "memory_status": "HARD_CLOSE",
            "reason_code": "KILL_PREPARATORY_LOOP",
        }
        renamed = {**prior, "question_id": "RENAMED_ONLY"}
        self.assertEqual(prior_scope_relation(renamed, prior), "EXACT_VALID_CLOSE")
        richer = {
            **prior,
            "question_id": "PRICE_LIQ_STATE",
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            "representation_scope": "PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800",
            "target": "Y1800:FIELD-USD-PRICE-001",
            "estimand": "price_liquidity_prefix",
        }
        self.assertEqual(
            prior_scope_relation(richer, prior),
            "SCOPE_DISTINCT",
        )
        same_content_richer_surface = {
            **prior,
            "question_id": "SAME_CONTENT_RICHER",
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            "representation_scope": "PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800",
        }
        self.assertEqual(
            prior_scope_relation(same_content_richer_surface, prior),
            "SCOPED_CONTROL_DOES_NOT_BLOCK",
        )
        holder = {
            **prior,
            "question_id": "HFIC-CAND-3232D00BED03",
            "target": "Y3600_HOLDER_BREADTH",
            "estimand": "holder_breadth",
            "reason_code": "KILL_MECHANISM",
        }
        self.assertEqual(prior_scope_relation(richer, holder), "SCOPE_DISTINCT")
        self.assertEqual(prior_scope_relation(prior, prior), "EXACT_VALID_CLOSE")
        with self.assertRaises(GroundedDiscoveryError) as exact:
            bind_prior_scope_evidence(
                {"candidate_scope": renamed, "priors": [prior]}
            )
        self.assertEqual(exact.exception.code, "EXACT_PRIOR_SCOPE_MATCH")
        bound = bind_prior_scope_evidence(
            {"candidate_scope": same_content_richer_surface, "priors": [prior]}
        )
        self.assertEqual(
            bound["prior_scope_relations"][0]["relation"],
            "SCOPED_CONTROL_DOES_NOT_BLOCK",
        )
        incomplete = {key: prior[key] for key in prior if key != "estimand"}
        self.assertEqual(
            prior_scope_relation(incomplete, prior),
            "UNKNOWN_SCOPE_NEEDS_RESOLUTION",
        )
        with self.assertRaises(GroundedDiscoveryError) as unknown:
            bind_prior_scope_evidence(
                {"candidate_scope": incomplete, "priors": [prior]}
            )
        self.assertEqual(unknown.exception.code, "UNKNOWN_PRIOR_SCOPE")

    def test_same_bytes_are_not_a_new_look_and_budget_is_finite(self) -> None:
        first = classify_query_look([], SPEC)
        self.assertTrue(first["new_look"])
        retry = classify_query_look([first], SPEC)
        self.assertFalse(retry["new_look"])
        self.assertEqual(retry["look_class"], "RETRY_SAME_BYTES")
        changed = {**SPEC, "target_point": "Y3600"}
        adaptive = classify_query_look([first], changed)
        self.assertEqual(adaptive["look_class"], "ADAPTIVE")
        previous = [first, adaptive]
        for index in range(5):
            previous.append(
                classify_query_look(
                    previous,
                    {**SPEC, "query_id": f"Q{index}", "target_point": "Y3600"},
                )
            )
        with self.assertRaises(GroundedDiscoveryError) as exc:
            classify_query_look(
                previous,
                {**SPEC, "query_id": "Q-EXTRA", "target_point": "Y900"},
            )
        self.assertEqual(exc.exception.code, "QUERY_MAIN_BUDGET_EXHAUSTED")


ROOT = Path(__file__).resolve().parents[1]
GIT_SHA = "ab" * 20
ANCHOR = "2026-09-03T00:00:00Z"
DECISION_AT = "2026-09-03T00:10:00Z"
TARGET_AT = "2026-09-03T00:20:00Z"


def _binding() -> list[dict]:
    return [
        {
            "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
            "evidence_role": "EXPLORATORY_REUSE",
            "holdout": False,
            "cohort_id": "REL-20260902T111900Z-20260909T111900Z",
            "release_id": "aa" * 32,
            "census_sha256": "bb" * 32,
            "observations_sha256": "cc" * 32,
            "window_start": "2026-09-02T11:19:00Z",
            "window_end": "2026-09-09T11:19:00Z",
        },
        {
            "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
            "evidence_role": "EXPLORATORY_REUSE",
            "holdout": False,
            "cohort_id": "C-EMPTY",
            "release_id": "dd" * 32,
            "census_sha256": "ee" * 32,
            "observations_sha256": "ff" * 32,
            "window_start": "2026-09-10T00:00:00Z",
            "window_end": "2026-09-11T00:00:00Z",
        },
        {
            "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
            "evidence_role": "EXPLORATORY_REUSE",
            "holdout": False,
            "cohort_id": "REL-20260914T173510Z-20260921T173510Z",
            "release_id": "11" * 32,
            "census_sha256": "22" * 32,
            "observations_sha256": "33" * 32,
            "window_start": "2026-09-08T00:00:00Z",
            "window_end": "2026-09-16T00:00:00Z",
        },
    ]


def _release_for(cohort: str) -> str:
    for item in _binding():
        if item["cohort_id"] == cohort:
            return str(item["release_id"])
    raise KeyError(cohort)


def _census(
    mint: str,
    cohort: str,
    state: str = "X_ELIGIBLE",
    anchor: str = ANCHOR,
) -> dict:
    return {
        "mint": mint,
        "cohort_id": cohort,
        "release_id": _release_for(cohort),
        "candidate_state": state,
        "authoritative_anchor": anchor,
    }


def _obs(
    mint: str,
    point: str,
    field: str,
    value: float | None,
    *,
    at: str,
    cohort: str,
    state: str = "OBSERVED",
) -> dict:
    return {
        "mint": mint,
        "cohort_id": cohort,
        "release_id": _release_for(cohort),
        "point_id": point,
        "field_id": field,
        "state": state,
        "first_reliable_available_at": at,
        "typed_value": None if value is None else value,
    }


def _rows():
    c1 = "REL-20260902T111900Z-20260909T111900Z"
    c3 = "REL-20260914T173510Z-20260921T173510Z"
    later_anchor = "2026-09-15T00:00:00Z"
    later_decision = "2026-09-15T00:10:00Z"
    later_target = "2026-09-15T00:20:00Z"
    census = [
        _census("high", c1),
        _census("low", c1),
        _census("high2", c3, anchor=later_anchor),
        _census("low2", c3, anchor=later_anchor),
        _census("late", c1),
        _census("nofeat", c1),
        _census("out", c1, "ADMITTED"),
    ]
    plan = (
        ("high", 5.0, 1.0, DECISION_AT, TARGET_AT, "OBSERVED"),
        ("low", 1.0, -1.0, DECISION_AT, TARGET_AT, "OBSERVED"),
        ("high2", 5.0, 1.0, later_decision, later_target, "OBSERVED"),
        ("low2", 1.0, -1.0, later_decision, later_target, "OBSERVED"),
        ("late", 5.0, 99.0, DECISION_AT, DECISION_AT, "OBSERVED"),
        ("nofeat", None, None, DECISION_AT, TARGET_AT, "MISSING_TYPED"),
        ("out", 5.0, 99.0, DECISION_AT, TARGET_AT, "OBSERVED"),
    )
    observations = []
    for mint, price, target, decision_at, target_at, target_state in plan:
        cohort = c3 if mint in {"high2", "low2"} else c1
        if price is not None:
            observations.append(_obs(mint, "X300", PRICE, price, at=decision_at, cohort=cohort))
        observations.append(_obs(mint, "X300", LIQ, 100.0, at=decision_at, cohort=cohort))
        observations.append(
            _obs(mint, "Y1800", PRICE, target, at=target_at, state=target_state, cohort=cohort)
        )
    return census, observations


def _spec() -> dict:
    return {
        **SPEC,
        "explanatory": ["price_high"],
        "explanatory_rules": [
            {
                "name": "price_high",
                "field_id": PRICE,
                "point_id": "X300",
                "op": "gte",
                "threshold": 2,
            }
        ],
    }


def _cohort_partitions(directory: Path, census: list, observations: list):
    """Write one census/observation pair per cohort and keep each file hash."""

    grouped: dict[str, dict[str, list]] = {}
    for row in census:
        grouped.setdefault(str(row["cohort_id"]), {"census": [], "observations": []})[
            "census"
        ].append(row)
    for row in observations:
        grouped.setdefault(str(row["cohort_id"]), {"census": [], "observations": []})[
            "observations"
        ].append(row)
    template = {item["cohort_id"]: item for item in _binding()}
    cohorts: list[dict] = []
    argv: list[str] = []
    files: dict[str, tuple[Path, Path]] = {}
    for cohort_id, payload in grouped.items():
        if not payload["census"] or not payload["observations"]:
            continue
        census_path = directory / f"census-{cohort_id}.parquet"
        obs_path = directory / f"obs-{cohort_id}.parquet"
        pq.write_table(pa.Table.from_pylist(payload["census"]), census_path)
        pq.write_table(pa.Table.from_pylist(payload["observations"]), obs_path)
        copied = dict(template[cohort_id])
        copied["census_sha256"] = hashlib.sha256(census_path.read_bytes()).hexdigest()
        copied["observations_sha256"] = hashlib.sha256(obs_path.read_bytes()).hexdigest()
        cohorts.append(copied)
        files[cohort_id] = (census_path, obs_path)
        argv.extend(
            ["--cohort-partition", cohort_id, str(census_path), str(obs_path)]
        )
    return argv, cohorts, files


def _discovery_execute(store: Path, binding: Path, spec: Path, scope: Path, journal: str, extra: list[str]):
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/hypothesis_forge.py",
            "--root",
            str(ROOT),
            "discovery-execute",
            "--store",
            str(store),
            *extra,
            "--binding",
            str(binding),
            "--spec",
            str(spec),
            "--candidate-scope",
            str(scope),
            "--journal-scope",
            journal,
            "--format",
            "json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _scope() -> dict:
    return {
        "question_id": "PRICE_LIQ_PREFIX",
        "population": "BASE_X",
        "decision_timestamp": "X300",
        "target": "Y1800:FIELD-USD-PRICE-001",
        "estimand": "price_liquidity_prefix",
        "evidence_surface_mode": ORDINARY_GROUNDED_DISCOVERY_V1,
        "representation_scope": "PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800",
    }


class ProductionRowRecipeTests(unittest.TestCase):
    def test_rows_show_conditional_effect_empty_strata_and_leakage(self) -> None:
        census, observations = _rows()
        computed = execute_discovery_from_rows(census, observations, _spec(), _binding())
        summary = computed["summary"]
        self.assertFalse(summary["engine_emits_alpha"])
        self.assertFalse(summary["eligibility_uses_target"])
        self.assertFalse(summary["traders_complete_required"])
        self.assertEqual(summary["base_x_n"], 6)
        self.assertAlmostEqual(summary["pooled"]["mean_target"], 0.0)
        self.assertGreaterEqual(len(summary["by_calendar_block"]), 2)
        self.assertFalse(summary["mint_overlap_known"])
        self.assertFalse(summary["pooled"]["independent_replication"])
        high = next(item for item in summary["by_explanatory"] if "price_high=True" in item["view"])
        low = next(item for item in summary["by_explanatory"] if "price_high=False" in item["view"])
        missing = next(item for item in summary["by_explanatory"] if "price_high=MISSING" in item["view"])
        self.assertEqual(high["mean_target"], 1.0)
        self.assertEqual(low["mean_target"], -1.0)
        self.assertIsNone(missing["mean_target"])
        self.assertGreater(missing["denominator_base_x"], 0)
        empty = next(item for item in summary["by_cohort"] if item["view"] == "C-EMPTY")
        self.assertEqual(empty["denominator_base_x"], 0)
        self.assertEqual(empty["target_observed_after_decision"], 0)
        self.assertTrue(summary["calendar_overlap_is_not_independent_replication"])
        self.assertFalse(summary["pooled"]["independent_replication"])
        self.assertGreaterEqual(summary["missing"]["leaked"], 1)
        self.assertGreaterEqual(summary["exclusion_reasons"].get("DECISION_NOT_READY", 0), 1)
        self.assertEqual(summary["exclusion_reasons"].get("NOT_X_ELIGIBLE"), 1)

    def test_ambiguous_role_stops_before_a_result(self) -> None:
        census, observations = _rows()
        binding = _binding()
        binding[0]["evidence_role"] = "UNSPECIFIED"
        with self.assertRaises(GroundedDiscoveryError) as exc:
            execute_discovery_from_rows(census, observations, _spec(), binding)
        self.assertEqual(exc.exception.code, "DISCOVERY_ROLE_AMBIGUOUS")

    def test_journal_retries_resume_and_counts_a_changed_binding(self) -> None:
        census, observations = _rows()
        scope = _scope()
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            clock = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
            first = run_recorded_discovery_query(
                store,
                census=census,
                observations=observations,
                spec=_spec(),
                binding=_binding(),
                journal_scope="SYNTH-ACCEPT",
                candidate_scope=scope,
                git_sha=GIT_SHA,
                clock=clock,
            )
            self.assertTrue(first["queries"][0]["new_look"])
            self.assertEqual(first["budget"]["main_count"], 1)
            resumed = ResearchStore(Path(raw))
            second = run_recorded_discovery_query(
                resumed,
                census=census,
                observations=observations,
                spec=_spec(),
                binding=_binding(),
                journal_scope="SYNTH-ACCEPT",
                candidate_scope=scope,
                git_sha=GIT_SHA,
                clock=clock,
            )
            self.assertFalse(second["queries"][0]["new_look"])
            self.assertEqual(second["result_refs"], first["result_refs"])
            self.assertEqual(second["budget"]["main_count"], 1)
            changed = [dict(row) for row in observations]
            changed.append(
                _obs(
                    "extra",
                    "X300",
                    PRICE,
                    1.0,
                    at=DECISION_AT,
                    cohort="REL-20260902T111900Z-20260909T111900Z",
                )
            )
            third = run_recorded_discovery_query(
                resumed,
                census=census,
                observations=changed,
                spec=_spec(),
                binding=_binding(),
                journal_scope="SYNTH-ACCEPT",
                candidate_scope=scope,
                git_sha=GIT_SHA,
                clock=clock,
            )
            self.assertTrue(third["queries"][0]["new_look"])
            self.assertNotEqual(third["result_refs"], first["result_refs"])
            self.assertEqual(third["calculation_version"], CALCULATION_VERSION)
            readout = format_discovery_readout(third)
            self.assertIn("NO_ALPHA", readout["non_claims"])
            self.assertEqual(readout["result_refs"], third["result_refs"])
            tampered = json.loads(json.dumps(third))
            tampered["result"]["pooled"]["mean_target"] = 99.0
            draft = {
                "packet_version": "1.1",
                "discovery_contract_version": "FORGE_GROUNDED_DISCOVERY_V1",
                "candidates": [],
                "grounded_evidence": tampered,
            }
            with self.assertRaises(HficSessionError) as mismatch:
                freeze_draft(draft, store=resumed)
            self.assertEqual(mismatch.exception.code, "GROUNDED_RESULT_MISMATCH")
            draft["grounded_evidence"] = third
            with self.assertRaises(HficSessionError) as accepted:
                freeze_draft(draft, store=resumed)
            self.assertEqual(accepted.exception.code, "TRUTH_ROOTS_REQUIRED")

    def test_ordinary_freeze_requires_computed_evidence(self) -> None:
        draft = {
            "packet_version": "1.1",
            "discovery_contract_version": "FORGE_GROUNDED_DISCOVERY_V1",
            "candidates": [],
        }
        with self.assertRaises(HficSessionError) as exc:
            freeze_draft(draft, store=object())
        self.assertEqual(exc.exception.code, "GROUNDED_EVIDENCE_REQUIRED")


    def test_explanatory_after_decision_and_censored_target_are_refused(self) -> None:
        census, observations = _rows()
        late_spec = _spec()
        late_spec["explanatory_rules"][0]["point_id"] = "Y900"
        with self.assertRaises(GroundedDiscoveryError) as late_rule:
            execute_discovery_from_rows(census, observations, late_spec, _binding())
        self.assertEqual(late_rule.exception.code, "EXPLANATORY_AFTER_DECISION")
        censored = [
            _census("slow", "REL-20260902T111900Z-20260909T111900Z"),
        ]
        slow_cohort = "REL-20260902T111900Z-20260909T111900Z"
        rows = [
            _obs("slow", "X300", PRICE, 5.0, at=DECISION_AT, cohort=slow_cohort),
            _obs("slow", "X300", LIQ, 100.0, at=DECISION_AT, cohort=slow_cohort),
            _obs("slow", "Y1800", PRICE, 99.0, at="2026-09-03T00:50:00Z", cohort=slow_cohort),
        ]
        binding = [_binding()[0]]
        summary = execute_discovery_from_rows(censored, rows, _spec(), binding)["summary"]
        self.assertEqual(summary["missing"]["censored_late"], 1)
        self.assertEqual(summary["later_target_observed_n"], 0)

    def test_predictive_identity_does_not_require_an_actor(self) -> None:
        definition = canonical_candidate_definition(
            {
                "claim_form": "PREDICTIVE",
                "claim": "X300 price predicts Y1800 price",
                "population": "BASE_X",
                "decision_timestamp": "X300",
                "primary_x_family": "FIELD-USD-PRICE-001",
                "primary_y": "FIELD-USD-PRICE-001",
                "horizon_notional": "Y1800",
                "negative_control": "flat price path",
                "cheapest_falsifier": "pooled mean stays near the conditional split",
            }
        )
        self.assertEqual(definition["actor_counterparty"], "")
        self.assertEqual(definition["mechanism"], "")

    def test_r2_boundaries_do_not_admit_foreign_or_late_rows(self) -> None:
        from solana_alpha_lab.factory.hfic_session import _ordinary_discovery_requested

        census, observations = _rows()
        foreign = [dict(row) for row in observations]
        for row in foreign:
            row["cohort_id"] = "PROTECTED_COHORT"
            row["release_id"] = "99" * 32
        foreign_summary = execute_discovery_from_rows(census, foreign, _spec(), _binding())["summary"]
        self.assertEqual(foreign_summary["base_x_n"], 0)
        unresolved = _binding()
        unresolved[0]["holdout"] = None
        with self.assertRaises(GroundedDiscoveryError) as holdout:
            execute_discovery_from_rows(census, observations, _spec(), unresolved)
        self.assertEqual(holdout.exception.code, "HOLDOUT_UNRESOLVED")
        forbidden = _spec()
        forbidden["explanatory_rules"][0]["field_id"] = "FIELD-HOLDER-COUNT-001"
        with self.assertRaises(GroundedDiscoveryError) as field:
            execute_discovery_from_rows(census, observations, forbidden, _binding())
        self.assertEqual(field.exception.code, "FIELD_NOT_IN_ALLOWLIST")
        c1 = "REL-20260902T111900Z-20260909T111900Z"
        early = [
            _census("keep", c1),
        ]
        early_rows = [
            _obs("keep", "X300", PRICE, 5.0, at=DECISION_AT, cohort=c1),
            _obs("keep", "X300", LIQ, 100.0, at=DECISION_AT, cohort=c1),
            _obs("keep", "X300", LIQ, 1.0, at="2026-09-03T00:20:00Z", cohort=c1, state="ABSENT"),
            _obs("keep", "Y1800", PRICE, 1.0, at=TARGET_AT, cohort=c1),
        ]
        kept = execute_discovery_from_rows(early, early_rows, _spec(), [_binding()[0]])["summary"]
        self.assertEqual(kept["base_x_n"], 1)
        late_only = [_census("lateonly", c1)]
        late_rows = [
            _obs("lateonly", "X300", PRICE, 5.0, at="2026-09-03T00:20:00Z", cohort=c1),
            _obs("lateonly", "X300", LIQ, 100.0, at="2026-09-03T00:20:00Z", cohort=c1),
            _obs("lateonly", "Y1800", PRICE, 1.0, at=TARGET_AT, cohort=c1),
        ]
        erased = execute_discovery_from_rows(late_only, late_rows, _spec(), [_binding()[0]])["summary"]
        self.assertEqual(erased["base_x_n"], 0)
        self.assertEqual(erased["exclusion_reasons"].get("PIT_LIQUIDITY_MISSING"), 1)
        price = {
            "question_id": "PRICE_RULE",
            "population": "BASE_X",
            "decision_timestamp": "X300",
            "target": "Y1800:FIELD-USD-PRICE-001",
            "estimand": "later_price",
            "explanatory_condition": "PRICE_GE_2",
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            "representation_scope": "PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800",
            "memory_status": "HARD_CLOSE",
            "reason_code": "KILL_MECHANISM",
        }
        liquidity = {**price, "question_id": "LIQ_RULE", "explanatory_condition": "LIQUIDITY_LT_100"}
        self.assertEqual(prior_scope_relation(liquidity, price), "SCOPE_DISTINCT")
        label_only = {
            **price,
            "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
            "representation_scope": price["representation_scope"],
        }
        self.assertEqual(prior_scope_relation(price, label_only), "EXACT_VALID_CLOSE")
        receipt = {
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            "discovery_contract_version": "FORGE_GROUNDED_DISCOVERY_V1",
        }
        self.assertTrue(_ordinary_discovery_requested({}, receipt))
        self.assertFalse(_ordinary_discovery_requested({}, {"evidence_surface_mode": None}))
        for count in (0, 1, 4, 6):
            counted = {"candidates": [{}] * count}
            self.assertTrue(_ordinary_discovery_requested(counted, receipt))
            with self.assertRaises(HficSessionError) as missing:
                _enforce_ordinary_grounded_evidence(
                    counted,
                    preflight_receipt=receipt,
                    store=object(),
                )
            self.assertEqual(str(missing.exception), "GROUNDED_EVIDENCE_REQUIRED")
        historical = {"candidates": [{}] * 6}
        self.assertFalse(
            _ordinary_discovery_requested(historical, {"action": "START_NEW_SESSION"})
        )
        _enforce_ordinary_grounded_evidence(
            historical,
            preflight_receipt={"action": "START_NEW_SESSION"},
            store=object(),
        )


class DiscoveryExecuteCliTests(unittest.TestCase):
    def test_public_cli_computes_without_a_handwritten_summary(self) -> None:
        census, observations = _rows()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = root / "store"
            argv, cohorts, _files = _cohort_partitions(root, census, observations)
            hashes = {item["census_sha256"] for item in cohorts}
            self.assertEqual(len(cohorts), 2)
            self.assertEqual(len(hashes), 2)
            binding_path = root / "binding.json"
            spec_path = root / "spec.json"
            scope_path = root / "scope.json"
            binding_path.write_text(
                json.dumps({"cohorts": cohorts, "priors": []}),
                encoding="utf-8",
            )
            spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
            scope_path.write_text(json.dumps(_scope()), encoding="utf-8")
            completed = _discovery_execute(
                store, binding_path, spec_path, scope_path, "SYNTH-CLI", argv
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["scientific_writes"], 0)
            self.assertFalse(payload["scientific_slot_reserved"])
            self.assertEqual(payload["result"]["pooled"]["mean_target"], 0.0)
            self.assertTrue(payload["result_refs"])
            self.assertNotIn("typed_value", json.dumps(payload["result"]))
            self.assertIn("spec", json.dumps(payload))


class OrdinaryOwnerPathTests(unittest.TestCase):
    def test_stamped_preflight_freezes_zero_candidates_with_computed_evidence(self) -> None:
        from tests.test_hfic_cli import bind_draft, populate_real_c1_c2, run_cli

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            populate_real_c1_c2(data_root, workspace)
            raw_preflight = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "scripts/hypothesis_forge.py",
                    "--root",
                    str(ROOT),
                    "--data-root",
                    str(data_root),
                    "preflight",
                    "--owner-focus",
                    "ORDINARY-DISCOVERY-SYNTH",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(raw_preflight.returncode, 0, raw_preflight.stderr)
            stamped = json.loads(raw_preflight.stdout)
            self.assertEqual(
                stamped.get("discovery_contract_version"),
                "FORGE_GROUNDED_DISCOVERY_V1",
            )
            from solana_alpha_lab.factory.hfic_session import (
                canonical_preflight_receipt_sha256,
            )

            self.assertEqual(
                stamped.get("preflight_receipt_sha256"),
                canonical_preflight_receipt_sha256(stamped),
            )
            preflight = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "ORDINARY-DISCOVERY-SYNTH",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            self.assertNotIn("evidence_surface_mode", receipt)
            self.assertEqual(receipt.get("discovery_contract_version"), "FORGE_GROUNDED_DISCOVERY_V1")
            census, observations = _rows()
            argv, cohorts, _files = _cohort_partitions(workspace, census, observations)
            self.assertEqual(len({item["census_sha256"] for item in cohorts}), 2)
            binding_path = workspace / "binding.json"
            spec_path = workspace / "spec.json"
            scope_path = workspace / "scope.json"
            binding_path.write_text(json.dumps({"cohorts": cohorts}), encoding="utf-8")
            spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
            scope_path.write_text(json.dumps(_scope()), encoding="utf-8")
            journal = str(receipt["search_key_sha256"])
            completed = _discovery_execute(
                data_root, binding_path, spec_path, scope_path, journal, argv
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(completed.stdout)
            restarted = _discovery_execute(
                data_root, binding_path, spec_path, scope_path, journal, argv
            )
            self.assertEqual(restarted.returncode, 0, restarted.stderr)
            self.assertFalse(json.loads(restarted.stdout)["queries"][0]["new_look"])
            self.assertEqual(json.loads(restarted.stdout)["result_refs"], evidence["result_refs"])
            preflight_after = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "ORDINARY-DISCOVERY-SYNTH",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight_after.returncode, 0, preflight_after.stderr)
            receipt = json.loads(preflight_after.stdout)
            self.assertEqual(receipt.get("search_key_sha256"), evidence["journal_scope"])
            draft = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json").read_text(encoding="utf-8")
            )
            draft["candidates"] = []
            draft.pop("selected_candidate_ref", None)
            draft.pop("runner_up_candidate_ref", None)
            draft.pop("strongest_rejected_alternative", None)
            draft = bind_draft(draft, receipt)
            draft["grounded_evidence"] = evidence
            frozen = freeze_draft(
                draft,
                preflight_receipt=receipt,
                store=ResearchStore(data_root),
                repo_root=ROOT,
            )
            self.assertEqual(frozen["critic_terminal"], "NO_WORTHY_HYPOTHESIS")
            self.assertFalse(frozen["grounded_evidence"]["raw_corpus_negative"])
            self.assertEqual(
                frozen["grounded_evidence"]["result_refs"],
                evidence["result_refs"],
            )

    def test_two_partitions_persist_one_selected_and_block_tamper(self) -> None:
        from tests.test_hfic_cli import bind_draft, populate_real_c1_c2, run_cli

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            populate_real_c1_c2(data_root, workspace)
            preflight = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "ORDINARY-SINGLETON-SYNTH",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            self.assertEqual(
                receipt.get("discovery_contract_version"),
                "FORGE_GROUNDED_DISCOVERY_V1",
            )
            source = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(
                    encoding="utf-8"
                )
            )
            card = source["candidates"][0]

            def without_evidence(candidates: list[dict]) -> dict:
                draft = bind_draft({**source, "candidates": candidates}, receipt)
                draft.pop("grounded_evidence", None)
                if len(candidates) < 2:
                    draft.pop("runner_up_candidate_ref", None)
                    draft.pop("strongest_rejected_alternative", None)
                    if candidates:
                        draft["selected_candidate_ref"] = candidates[0]["label"]
                    else:
                        draft.pop("selected_candidate_ref", None)
                return draft

            six = []
            for index in range(6):
                copied = dict(card)
                copied["label"] = f"HFIC-V12-C{index + 1}-COUNT"
                copied["display_ordinal"] = index + 1
                copied["claim"] = f"{card['claim']} count {index}"
                six.append(copied)
            four = without_evidence(source["candidates"])
            one = without_evidence([card])
            zero = without_evidence([])
            six_draft = without_evidence(six)
            six_draft["runner_up_candidate_ref"] = six[1]["label"]
            six_draft["strongest_rejected_alternative"] = six[2]["label"]
            six_draft["selected_candidate_ref"] = six[0]["label"]
            for draft in (zero, one, four, six_draft):
                with self.assertRaises(HficSessionError) as missing:
                    freeze_draft(
                        draft,
                        preflight_receipt=receipt,
                        store=ResearchStore(data_root),
                        repo_root=ROOT,
                    )
                self.assertEqual(str(missing.exception), "GROUNDED_EVIDENCE_REQUIRED")

            census, observations = _rows()
            argv, cohorts, files = _cohort_partitions(workspace, census, observations)
            self.assertEqual(len({item["census_sha256"] for item in cohorts}), 2)
            binding_path = workspace / "binding.json"
            spec_path = workspace / "spec.json"
            scope_path = workspace / "scope.json"
            binding_path.write_text(json.dumps({"cohorts": cohorts}), encoding="utf-8")
            spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
            scope_path.write_text(json.dumps(_scope()), encoding="utf-8")
            journal = str(receipt["search_key_sha256"])
            cohort_ids = list(files)
            swapped = []
            for cohort_id in cohort_ids:
                other = cohort_ids[1] if cohort_id == cohort_ids[0] else cohort_ids[0]
                swapped.extend(
                    [
                        "--cohort-partition",
                        cohort_id,
                        str(files[other][0]),
                        str(files[cohort_id][1]),
                    ]
                )
            blocked = _discovery_execute(
                data_root, binding_path, spec_path, scope_path, journal, swapped
            )
            self.assertNotEqual(blocked.returncode, 0, blocked.stdout)
            self.assertIn("BINDING_HASH_MISMATCH", blocked.stderr)
            census_path = files[cohort_ids[0]][0]
            original = census_path.read_bytes()
            census_path.write_bytes(original + b"\x00")
            tampered = _discovery_execute(
                data_root, binding_path, spec_path, scope_path, journal, argv
            )
            self.assertNotEqual(tampered.returncode, 0, tampered.stdout)
            self.assertIn("BINDING_HASH_MISMATCH", tampered.stderr)
            census_path.write_bytes(original)
            completed = _discovery_execute(
                data_root, binding_path, spec_path, scope_path, journal, argv
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(completed.stdout)
            readout = format_discovery_readout(evidence)
            self.assertFalse(readout["engine_emits_alpha"])
            self.assertEqual(readout["result_refs"], evidence["result_refs"])
            preflight_after = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "ORDINARY-SINGLETON-SYNTH",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight_after.returncode, 0, preflight_after.stderr)
            source_receipt = json.loads(preflight_after.stdout)
            self.assertEqual(source_receipt.get("action"), "START_NEW_SESSION")
            self.assertEqual(source_receipt.get("search_key_sha256"), evidence["journal_scope"])
            selected = dict(card)
            draft = bind_draft({**source, "candidates": [selected]}, source_receipt)
            draft.pop("runner_up_candidate_ref", None)
            draft.pop("strongest_rejected_alternative", None)
            draft["selected_candidate_ref"] = selected["label"]
            draft["grounded_evidence"] = evidence
            draft_path = workspace / "draft.json"
            receipt_path = workspace / "preflight.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(source_receipt), encoding="utf-8")
            persisted = run_cli(
                "persist-draft",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--representation-id",
                "BASE",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(persisted.returncode, 0, persisted.stderr)
            resumed = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "ORDINARY-SINGLETON-SYNTH",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            resume_receipt = json.loads(resumed.stdout)
            self.assertEqual(resume_receipt.get("action"), "RESUME_EXISTING_SESSION")
            resume_path = workspace / "resume.json"
            resume_path.write_text(json.dumps(resume_receipt), encoding="utf-8")
            frozen_run = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(resume_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr)
            frozen = json.loads(frozen_run.stdout)
            packet = frozen.get("critic_input_packet")
            self.assertIsInstance(packet, dict)
            self.assertEqual(packet.get("strongest_rejected_alternative"), "NONE")
            self.assertIsNone(frozen.get("runner_up_critic_input_packet"))
            handed = packet.get("grounded_evidence")
            self.assertIsInstance(handed, dict)
            self.assertEqual(handed.get("result_refs"), evidence["result_refs"])
            session_id = str(frozen["session_id"])
            critic = {
                "schema": "smial.hypothesis-critic-result",
                "schema_version": "1.1",
                "session_id": session_id,
                "critic_input_packet_sha256": frozen["critic_input_packet_sha256"],
                "selected_candidate_id": frozen["selected_candidate_id"],
                "selected_definition_sha256": frozen["selected_definition_sha256"],
                "critic_prompt_version": "HFIC-V1.1",
                "isolated_context_attestation": "NEW_CONTEXT_REQUIRED",
                "critic_terminal": "KILL_PREPARATORY_LOOP",
                "next": "STOP",
                "authority": {
                    "git_mutation": 0,
                    "experiment_execution": 0,
                    "provider_api_rpc_wss_calls": 0,
                },
                "non_claims": ["NO_ALPHA", "FIXTURE_CRITIC"],
            }
            critic_path = workspace / "critic.json"
            critic_path.write_text(json.dumps(critic), encoding="utf-8")
            finalized = run_cli(
                "finalize",
                "--session-id",
                session_id,
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            shown = run_cli(
                "show-session",
                "--session-id",
                session_id,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(shown.returncode, 0, shown.stderr)
            shown_payload = json.loads(shown.stdout)
            self.assertIn("owner_readout", shown_payload)
            self.assertEqual(shown_payload.get("session_id"), session_id)
            restarted = _discovery_execute(
                data_root, binding_path, spec_path, scope_path, journal, argv
            )
            self.assertEqual(restarted.returncode, 0, restarted.stderr)
            restarted_payload = json.loads(restarted.stdout)
            self.assertFalse(restarted_payload["queries"][0]["new_look"])
            self.assertEqual(restarted_payload["result_refs"], evidence["result_refs"])


if __name__ == "__main__":
    unittest.main()
