"""M1 execution reality calibration essential tests (§27, combined cases).

All tests are zero-network: the only openers used are injected fixtures.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_read_model import build_m1_progress_projection
from solana_alpha_lab.factory.m1_calibration_report import (
    M1CalibrationReportError,
    build_m1_calibration_report,
)
from solana_alpha_lab.factory.m1_execution_reality import (
    M1ExecutionRealityError,
    NOTIONAL_10_USD,
    NOTIONAL_100_USD,
    NOTIONAL_ATOMIC,
    OUTCOME_ENTRY_ONLY,
    OUTCOME_NO_ENTRY,
    OUTCOME_TWO_WAY,
    OUTCOME_UNKNOWN,
    classify_execution_outcome,
    classify_member_outcomes,
    cross_notional_transition,
    cross_notional_transition_counts,
    friction_summary,
    leg_class,
    normalized_entry_size_linearity,
    notional_outcome_counts,
    quote_implied_roundtrip_friction,
    verify_denominatorInvariant,
)
from solana_alpha_lab.factory.m1_successor_preflight import (
    run_m1_successor_preflight,
)
from solana_alpha_lab.factory.observation_primitive_registry import (
    load_observation_primitive_registry,
)
from solana_alpha_lab.factory.observation_primitives import (
    USDC_DECIMALS,
    USDC_MINT,
    classify_jupiter_quote_error_body,
    execute_primitive,
    quote_url,
)
from solana_alpha_lab.factory.observation_schedule import (
    load_observation_schedule,
    schedule_sha256 as compute_schedule_sha256,
)
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
)

NOW = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
FIXTURE = "tests/fixtures/observation_schedule/m1_quote_surface.yaml"
TOKEN = "TestMint111111111111111111111111111111111111111"


class _Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value


class _Opener:
    def __init__(self, result: object) -> None:
        self.result = result

    def open(self, url: str) -> object:
        return self.result


QUOTE_URL = quote_url(input_mint=USDC_MINT, output_mint=TOKEN, amount="10000000")


def _run_quote_primitive(body: object, status: int) -> dict:
    return execute_primitive(
        primitive_id="PRIM-JUPITER-SWAP-V2-QUOTE-BUY-USDC10-001",
        primitive_version="1.0",
        method="GET",
        url=QUOTE_URL,
        opener=_Opener({"http_status": status, "body": body, "url_has_api_key": False}),
        clock=_Clock(),
        schema_required_keys=("outAmount",),
    )


class TypedNoRouteParityTests(unittest.TestCase):
    """§9: typed NO_ROUTE parity — tests 17-22."""

    def test_typed_known_route_codes_classified_no_route(self) -> None:
        for code in (
            "NO_ROUTES_FOUND",
            "COULD_NOT_FIND_ANY_ROUTE",
            "TOKEN_NOT_TRADABLE",
            "MARKET_NOT_FOUND",
            "FAILED TO GET QUOTES",
        ):
            result = _run_quote_primitive({"errorCode": code, "error": "x"}, 400)
            self.assertEqual(result["status"], "MISSING_TYPED")
            self.assertEqual(result["missing_reason"], "NO_ROUTE", code)
            # Also on 404 (17) and 200 (Jupiter explicit-no-route under 200).
            for status in (404, 200):
                outcome = _run_quote_primitive(
                    {"errorCode": code, "error": "x"}, status
                )
                self.assertEqual(outcome["missing_reason"], "NO_ROUTE", (code, status))

    def test_notional_route_code_is_typed_notional_no_route(self) -> None:
        result = _run_quote_primitive(
            {"errorCode": "ROUTE_PLAN_DOES_NOT_CONSUME_ALL_THE_AMOUNT", "error": "x"},
            400,
        )
        self.assertEqual(result["missing_reason"], "NOTIONAL_NO_ROUTE")

    def test_unrecognized_provider_error_not_no_route(self) -> None:
        # 22: generic provider failure is NOT NO_ROUTE.
        result = _run_quote_primitive({"errorCode": "SOMETHING_ELSE", "error": "x"}, 400)
        self.assertEqual(result["missing_reason"], "UNKNOWN_PROVIDER_ERROR")

    def test_timeout_transport_5xx_schema_unknown(self) -> None:
        # 20: timeout/transport/5xx/schema → UNKNOWN at leg level.
        self.assertEqual(
            leg_class(state="MISSING_TYPED", missing_reason="HTTP_ERROR"),
            "UNKNOWN",
        )
        self.assertEqual(
            leg_class(state="MISSING_TYPED", missing_reason="TIMEOUT"), "UNKNOWN"
        )
        self.assertEqual(
            leg_class(state="MISSING_TYPED", missing_reason="PROVIDER_SCHEMA_DRIFT"),
            "UNKNOWN",
        )
        self.assertEqual(
            leg_class(state="MISSING_TYPED", missing_reason="UNKNOWN_PROVIDER_ERROR"),
            "UNKNOWN",
        )
        self.assertEqual(
            leg_class(state="MISSING_TYPED", missing_reason=None), "UNKNOWN"
        )

    def test_no_substring_heuristic(self) -> None:
        # A code containing ROUTE as substring but not exactly equal must not
        # become NO_ROUTE.
        result = _run_quote_primitive(
            {"errorCode": "NO_ROUTES_FOUND_IN_CACHE_EXPIRED_VARIANT", "error": "x"},
            400,
        )
        self.assertNotEqual(result["missing_reason"], "NO_ROUTE")

    def test_search_surface_404_keeps_generic_semantics(self) -> None:
        # Typed quote codes are swap/v2/order semantics only.
        result = execute_primitive(
            primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
            primitive_version="1.0",
            method="GET",
            url="https://api.jup.ag/tokens/v2/search?query=X",
            opener=_Opener({"http_status": 404, "body": {"error": "not found"}, "url_has_api_key": False}),
            clock=_Clock(),
            schema_required_keys=("id",),
        )
        self.assertEqual(result["missing_reason"], "NO_ROUTE")


class OutcomeClassificationTests(unittest.TestCase):
    """§9 mapping + §10 denominator — tests 17-19, 23."""

    def test_outcome_matrix(self) -> None:
        O, NR, U = "QUOTE_OBSERVED", "NO_ROUTE", "UNKNOWN"
        self.assertEqual(classify_execution_outcome(NR, None), OUTCOME_NO_ENTRY)
        self.assertEqual(classify_execution_outcome(NR, NR), OUTCOME_NO_ENTRY)
        self.assertEqual(classify_execution_outcome(O, NR), OUTCOME_ENTRY_ONLY)
        self.assertEqual(classify_execution_outcome(O, O), OUTCOME_TWO_WAY)
        self.assertEqual(classify_execution_outcome(O, U), OUTCOME_UNKNOWN)
        self.assertEqual(classify_execution_outcome(U, O), OUTCOME_UNKNOWN)
        self.assertEqual(classify_execution_outcome(O, None), OUTCOME_UNKNOWN)
        self.assertEqual(classify_execution_outcome("NOTIONAL_NO_ROUTE", None), OUTCOME_NO_ENTRY)
        self.assertEqual(classify_execution_outcome(O, "NOTIONAL_NO_ROUTE"), OUTCOME_ENTRY_ONLY)

    def test_denominator_invariant(self) -> None:
        outcomes = [
            OUTCOME_TWO_WAY,
            OUTCOME_TWO_WAY,
            OUTCOME_ENTRY_ONLY,
            OUTCOME_NO_ENTRY,
            OUTCOME_UNKNOWN,
        ]
        counts = notional_outcome_counts(outcomes)
        verify_denominatorInvariant(population_n=5, counts=counts)
        with self.assertRaises(M1ExecutionRealityError):
            verify_denominatorInvariant(population_n=4, counts=counts)

    def test_missingness_never_deletes_member(self) -> None:
        # 26: an all-UNKNOWN member still counts in the denominator.
        outcomes = [OUTCOME_UNKNOWN, OUTCOME_UNKNOWN]
        counts = notional_outcome_counts(outcomes)
        self.assertEqual(counts[OUTCOME_UNKNOWN], 2)
        verify_denominatorInvariant(population_n=2, counts=counts)

    def test_member_classification_both_notionals(self) -> None:
        evidence = {
            NOTIONAL_10_USD: {
                "entry": {"state": "OBSERVED", "missing_reason": None},
                "reverse": {"state": "OBSERVED", "missing_reason": None},
            },
            NOTIONAL_100_USD: {
                "entry": {"state": "OBSERVED", "missing_reason": None},
                "reverse": {"state": "MISSING_TYPED", "missing_reason": "NO_ROUTE"},
            },
        }
        outcomes = classify_member_outcomes(evidence)
        self.assertEqual(outcomes[NOTIONAL_10_USD], OUTCOME_TWO_WAY)
        self.assertEqual(outcomes[NOTIONAL_100_USD], OUTCOME_ENTRY_ONLY)


class FrictionAndDiagnosticsTests(unittest.TestCase):
    """§18-§19."""

    def test_friction_pairing_and_summary(self) -> None:
        friction = quote_implied_roundtrip_friction(
            entry_notional_atomic="10000000",
            entry_out_amount="123456789",
            reverse_out_amount="9800000",
        )
        self.assertEqual(Decimal(friction), Decimal("0.02"))
        summary = friction_summary([friction, "0.03", "0.01"])
        self.assertEqual(summary["n"], 3)
        self.assertEqual(Decimal(summary["median"]), Decimal("0.02"))
        self.assertEqual(Decimal(summary["min"]), Decimal("0.01"))
        self.assertEqual(Decimal(summary["max"]), Decimal("0.03"))

    def test_friction_separate_per_notional(self) -> None:
        # 35: regimes stay separate (identity, not merged).
        f10 = quote_implied_roundtrip_friction(
            entry_notional_atomic=NOTIONAL_ATOMIC[NOTIONAL_10_USD],
            entry_out_amount="1000",
            reverse_out_amount="9900000",
        )
        f100 = quote_implied_roundtrip_friction(
            entry_notional_atomic=NOTIONAL_ATOMIC[NOTIONAL_100_USD],
            entry_out_amount="1000",
            reverse_out_amount="98000000",
        )
        self.assertNotEqual(f10, f100)

    def test_size_linearity(self) -> None:
        value = normalized_entry_size_linearity(
            entry_out_10="1000", entry_out_100="9500"
        )
        self.assertEqual(Decimal(value), Decimal("0.95"))

    def test_transitions(self) -> None:
        counts = cross_notional_transition_counts(
            [
                cross_notional_transition(
                    outcome_10=OUTCOME_TWO_WAY, outcome_100=OUTCOME_TWO_WAY
                ),
                cross_notional_transition(
                    outcome_10=OUTCOME_TWO_WAY, outcome_100=OUTCOME_ENTRY_ONLY
                ),
                cross_notional_transition(
                    outcome_10=OUTCOME_ENTRY_ONLY, outcome_100=OUTCOME_TWO_WAY
                ),
                cross_notional_transition(
                    outcome_10=OUTCOME_ENTRY_ONLY, outcome_100=OUTCOME_ENTRY_ONLY
                ),
                cross_notional_transition(
                    outcome_10=OUTCOME_NO_ENTRY, outcome_100=OUTCOME_UNKNOWN
                ),
            ]
        )
        self.assertEqual(counts["TWO_WAY__TWO_WAY"], 1)
        self.assertEqual(counts["TWO_WAY__ENTRY_ONLY"], 1)
        self.assertEqual(counts["ENTRY_ONLY__TWO_WAY"], 1)
        self.assertEqual(counts["ENTRY_ONLY__ENTRY_ONLY"], 1)
        self.assertEqual(counts["NO_ENTRY__UNKNOWN"], 1)


class UsdcCapabilityTests(unittest.TestCase):
    """§6-§7 — tests 4-9, safety 10-15."""

    def test_canonical_usdc_identity(self) -> None:
        self.assertEqual(
            USDC_MINT, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        )
        self.assertEqual(USDC_DECIMALS, 6)
        self.assertEqual(NOTIONAL_ATOMIC[NOTIONAL_10_USD], "10000000")
        self.assertEqual(NOTIONAL_ATOMIC[NOTIONAL_100_USD], "100000000")

    def test_entry_url_is_usdc_to_token(self) -> None:
        url = quote_url(input_mint=USDC_MINT, output_mint=TOKEN, amount="10000000")
        self.assertIn("inputMint=EPjFWdd5", url)
        self.assertIn(f"outputMint={TOKEN}", url)
        self.assertIn("amount=10000000", url)
        self.assertNotIn("taker", url)
        self.assertNotIn("/build", url)
        self.assertNotIn("/execute", url)
        self.assertNotIn("transaction", url)

    def test_registry_contains_usdc_primitives_with_dependency_binding(self) -> None:
        registry = load_observation_primitive_registry(ROOT)
        entry10 = registry.require_primitive(
            "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-USDC10-001"
        )
        reverse10 = registry.require_primitive(
            "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-USDC10-001"
        )
        self.assertIsNone(entry10["dependency_contract"])
        self.assertEqual(
            reverse10["dependency_contract"]["requires_bundle_id"],
            "BUNDLE-JUPITER-QUOTE-BUY-USDC10-001",
        )
        reverse100 = registry.require_primitive(
            "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-USDC100-001"
        )
        self.assertEqual(
            reverse100["dependency_contract"]["requires_bundle_id"],
            "BUNDLE-JUPITER-QUOTE-BUY-USDC100-001",
        )
        # Reverse legs bind to their own notional (9: cross-wire impossible).
        self.assertNotEqual(
            reverse10["dependency_contract"]["requires_bundle_id"],
            reverse100["dependency_contract"]["requires_bundle_id"],
        )
        # Safety: no retry/fallback/cash, zero-cash authority.
        for primitive in (
            entry10,
            reverse10,
            registry.require_primitive("PRIM-JUPITER-SWAP-V2-QUOTE-BUY-USDC100-001"),
            reverse100,
        ):
            self.assertFalse(primitive["retry"])
            self.assertFalse(primitive["fallback"])
            self.assertEqual(primitive["provider_route_ids"], ["JUPITER-SOLANA-SWAP-V2-ORDER-FREE-API-KEY-001"])
        registry.verify_implementation_hashes()

    def test_sol_primitives_unchanged(self) -> None:
        # 1: existing SOL quote primitives unchanged.
        registry = load_observation_primitive_registry(ROOT)
        sol_buy = registry.require_primitive("PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001")
        self.assertEqual(sol_buy["kind"], "POINT_OBSERVATION")
        self.assertIsNone(sol_buy["dependency_contract"])
        sol_reverse = registry.require_primitive(
            "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
        )
        self.assertEqual(
            sol_reverse["dependency_contract"]["requires_bundle_id"],
            "BUNDLE-JUPITER-QUOTE-BUY-001",
        )
        # 2: existing schedule fixtures still validate (timer/store/recovery
        # path exercised through scheduler store tests elsewhere).
        for fixture in (
            "tests/fixtures/observation_schedule/x300_y900.yaml",
            "tests/fixtures/observation_schedule/pathrisk_calibration.yaml",
            FIXTURE,
        ):
            schedule = load_observation_schedule(ROOT, fixture)
            self.assertTrue(schedule["schedule_sha256"])

    def test_scheduler_wiring_usdc_urls(self) -> None:
        from solana_alpha_lab.factory import observation_scheduler as scheduler

        claim10 = {"primitive_id": "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-USDC10-001", "entity_id": TOKEN}
        url10, _version = scheduler._url_for_claim({}, claim10)
        self.assertIn("inputMint=EPjFWdd5", url10)
        claim100 = {"primitive_id": "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-USDC100-001", "entity_id": TOKEN}
        url100, _version = scheduler._url_for_claim({}, claim100)
        self.assertIn("amount=100000000", url100)
        # Reverse legs consume the exact entry outAmount payload (8) and
        # return to USDC.
        reverse10 = {
            "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-USDC10-001",
            "entity_id": TOKEN,
            "payload": {"buy_out_amount": "555000"},
        }
        rurl, _version = scheduler._url_for_claim({}, reverse10)
        self.assertIn("inputMint=" + TOKEN, rurl)
        self.assertIn("outputMint=EPjFWdd5", rurl)
        self.assertIn("amount=555000", rurl)
        # SOL reverse unchanged: token → wrapped SOL.
        sol_reverse = {
            "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
            "entity_id": TOKEN,
            "payload": {"buy_out_amount": "777"},
        }
        surl, _version = scheduler._url_for_claim({}, sol_reverse)
        self.assertIn("outputMint=So11111111111111111111111111111111111111112", surl)


class SuccessorPreflightTests(unittest.TestCase):
    """§14-§16, §29 — tests 27-32."""

    def _predecessor(self) -> dict:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/m1_quote_surface.yaml"
        )
        # Model a minimal search-only predecessor by stripping M1 bundles.
        predecessor = copy.deepcopy(schedule)
        predecessor["x_point"]["bundle_ids"] = ["BUNDLE-JUPITER-TOKEN-SEARCH-SNAPSHOT-001"]
        predecessor.pop("schedule_sha256", None)
        return predecessor

    def _readback(self, schedule: dict) -> dict:
        return {
            "activation_state": "ACTIVE",
            "activation_id": "ACT-PRED-1",
            "schedule_sha256": compute_schedule_sha256(schedule),
        }

    def test_compatible_successor_preserves_predecessor(self) -> None:
        predecessor = self._predecessor()
        result = run_m1_successor_preflight(
            root=ROOT,
            predecessor_readback=self._readback(predecessor),
            predecessor_schedule=predecessor,
            m1_campaign_request={"target_members": 100, "campaign_days": 7},
            now=NOW,
        )
        self.assertTrue(result["compatible"], result)
        successor = result["proposed_successor"]["document"]
        # 29: unrelated predecessor semantics preserved.
        self.assertEqual(
            successor["population"], predecessor["population"]
        )
        self.assertEqual(successor["source_poll"], predecessor["source_poll"])
        self.assertEqual(
            successor["y_points"][0]["bundle_ids"],
            predecessor["y_points"][0]["bundle_ids"],
        )
        # M1 bundles added to X point.
        self.assertIn("BUNDLE-JUPITER-QUOTE-BUY-USDC10-001", successor["x_point"]["bundle_ids"])
        self.assertIn("BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-USDC100-001", successor["x_point"]["bundle_ids"])
        # 30: no second discovery loop — same source poll primitive.
        self.assertEqual(
            successor["source_poll"]["primitive_id"],
            predecessor["source_poll"]["primitive_id"],
        )
        self.assertEqual(result["network_calls"], 0)
        self.assertEqual(result["runtime_mutations"], 0)
        # Authority material present for owner review.
        self.assertIsNotNone(result["authority_request_material"])

    def test_not_active_predecessor_fails_closed(self) -> None:
        predecessor = self._predecessor()
        result = run_m1_successor_preflight(
            root=ROOT,
            predecessor_readback={"activation_state": "DRAINING", "activation_id": "A"},
            predecessor_schedule=predecessor,
            m1_campaign_request={"target_members": 10, "campaign_days": 3},
            now=NOW,
        )
        self.assertFalse(result["compatible"])
        self.assertEqual(result["blocked_reason"], "PREDECESSOR_READBACK_NOT_ACTIVE")

    def test_bundle_capacity_gap_fails_closed(self) -> None:
        predecessor = self._predecessor()
        # 5 existing + 4 M1 = 9 > 8 bundle cap → explicit gap, no silent
        # schema widening.
        predecessor["x_point"]["bundle_ids"] = [
            "BUNDLE-JUPITER-TOKEN-SEARCH-SNAPSHOT-001",
            "BUNDLE-JUPITER-QUOTE-BUY-001",
            "BUNDLE-JUPITER-QUOTE-BUY-1M-001",
            "BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001",
            "BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-1M-001",
        ]
        result = run_m1_successor_preflight(
            root=ROOT,
            predecessor_readback=self._readback(predecessor),
            predecessor_schedule=predecessor,
            m1_campaign_request={"target_members": 10, "campaign_days": 3},
            now=NOW,
        )
        self.assertFalse(result["compatible"])
        self.assertEqual(result["blocked_reason"], "M1_BUNDLE_CAPACITY_GAP")

    def test_budget_gap_fails_closed(self) -> None:
        predecessor = self._predecessor()
        predecessor["budgets"]["provider_calls_per_utc_day_max"] = 10
        predecessor["budgets"]["provider_calls_lifetime_max"] = 10
        result = run_m1_successor_preflight(
            root=ROOT,
            predecessor_readback=self._readback(predecessor),
            predecessor_schedule=predecessor,
            m1_campaign_request={"target_members": 100, "campaign_days": 7},
            now=NOW,
        )
        self.assertFalse(result["compatible"])
        self.assertIn(
            result["blocked_reason"],
            {"M1_PROVIDER_BUDGET_GAP", "SUCCESSOR_COMPILE_FAILED"},
        )

    def test_identity_mismatch_fails_closed(self) -> None:
        predecessor = self._predecessor()
        result = run_m1_successor_preflight(
            root=ROOT,
            predecessor_readback={
                "activation_state": "ACTIVE",
                "activation_id": "A",
                "schedule_sha256": "0" * 64,
            },
            predecessor_schedule=predecessor,
            m1_campaign_request={"target_members": 10, "campaign_days": 3},
            now=NOW,
        )
        self.assertFalse(result["compatible"])
        self.assertEqual(result["blocked_reason"], "PREDECESSOR_IDENTITY_MISMATCH")

    def test_identityless_readback_fails_closed(self) -> None:
        # An ACTIVE readback without schedule_sha256 cannot prove which
        # schedule runs; the preflight must not propose a successor anyway.
        predecessor = self._predecessor()
        result = run_m1_successor_preflight(
            root=ROOT,
            predecessor_readback={
                "activation_state": "ACTIVE",
                "activation_id": "A",
                "schedule_sha256": None,
            },
            predecessor_schedule=predecessor,
            m1_campaign_request={"target_members": 10, "campaign_days": 3},
            now=NOW,
        )
        self.assertFalse(result["compatible"])
        self.assertEqual(
            result["blocked_reason"], "PREDECESSOR_READBACK_IDENTITY_MISSING"
        )


class CalibrationReportTests(unittest.TestCase):
    """§21-§22 — tests 33-38."""

    def _panel_root(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="m1-rdp-"))

    def test_moving_sqlite_rejected(self) -> None:
        root = self._panel_root()
        with self.assertRaises(M1CalibrationReportError) as ctx:
            build_m1_calibration_report(
                data_root=root,
                schedule_sha256="a" * 64,
                activation_id="ACT-1",
                availability_cutoff=NOW,
                population_ref="EARLY_ICP_V1",
                sampling_identity={"policy": "DETERMINISTIC_HASH_BERNOULLI"},
                source_lineage={"ops_path": "local/factory_v1/state.sqlite"},
            )
        self.assertIn("MOVING_SQLITE", str(ctx.exception))

    def test_empty_panel_yields_zero_denominator_report(self) -> None:
        root = self._panel_root()
        report = build_m1_calibration_report(
            data_root=root,
            schedule_sha256="a" * 64,
            activation_id="ACT-1",
            availability_cutoff=NOW,
            population_ref="EARLY_ICP_V1",
            sampling_identity={"policy": "DETERMINISTIC_HASH_BERNOULLI"},
            source_lineage={
                "dataset_manifest_ids": ["DATASET-1"],
                "dataset_fingerprints": ["f" * 64],
            },
        )
        self.assertEqual(report["sample_accounting"]["primary_members_n"], 0)
        self.assertEqual(
            report["regime_counts"]["notional_10_usd"]["TWO_WAY"], 0
        )
        self.assertIn("NO_ALPHA", report["limitations_non_claims"])
        self.assertTrue(report["report_sha256"])
        # 37: no automatic binding; no fabricated experiment identity.
        text = json.dumps(report)
        self.assertNotIn("experiment_id", text)
        self.assertNotIn("ExecutionEvidenceBinding", text)

    def test_denominator_closes_on_synthetic_panel(self) -> None:
        root = self._panel_root()
        report = build_m1_calibration_report(
            data_root=root,
            schedule_sha256="a" * 64,
            activation_id="ACT-1",
            availability_cutoff=NOW,
            population_ref="EARLY_ICP_V1",
            sampling_identity={},
            source_lineage={
                "dataset_manifest_ids": ["DATASET-1"],
                "dataset_fingerprints": ["f" * 64],
            },
        )
        counts10 = report["regime_counts"]["notional_10_usd"]
        counts100 = report["regime_counts"]["notional_100_usd"]
        total = sum(counts10.values())
        self.assertEqual(total, report["sample_accounting"]["primary_members_n"])
        self.assertEqual(
            sum(counts100.values()), report["sample_accounting"]["primary_members_n"]
        )

    def test_empty_lineage_fails_closed(self) -> None:
        # An empty lineage must not silently produce a zero-science report;
        # immutable dataset manifests/fingerprints are mandatory evidence.
        root = self._panel_root()
        with self.assertRaises(M1CalibrationReportError) as ctx:
            build_m1_calibration_report(
                data_root=root,
                schedule_sha256="a" * 64,
                activation_id="ACT-1",
                availability_cutoff=NOW,
                population_ref="EARLY_ICP_V1",
                sampling_identity={},
                source_lineage={},
            )
        self.assertIn("SOURCE_LINEAGE_MISSING", str(ctx.exception))


class OperabilityProjectionTests(unittest.TestCase):
    """§23, §25 — tests 39-40."""

    def test_projection_shape_on_empty_store(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="m1-ops-") as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                projection = build_m1_progress_projection(
                    store,
                    schedule_sha256="a" * 64,
                    activation_id="ACT-1",
                    now=NOW,
                )
            finally:
                store.close()
        self.assertEqual(projection["projection"], "M1_PROGRESS_PROVISIONAL")
        self.assertFalse(projection["m1_active"])
        self.assertEqual(projection["sampled_member_count"], 0)
        self.assertEqual(projection["blocker"], "ACTIVATION_NONE")
        self.assertEqual(
            projection["final_result_source"], "FROZEN_M1_CALIBRATION_REPORT_ONLY"
        )


class XGateM1IsolationTests(unittest.TestCase):
    """Regression: M1 USDC execution primitives must never flip the scientific
    X-eligibility gate (review BLOCKER). A typed NO_ROUTE on the M1 entry at
    the X point keeps the member eligible, so NO_ENTRY stays observable."""

    def test_no_route_entry_keeps_member_in_primary_denominator(self) -> None:
        import tempfile

        from solana_alpha_lab.factory.observation_scheduler import tick_once
        from tests.test_observation_scheduler import _activate as _sched_activate
        from tests.test_observation_scheduler import NOW as SCHED_NOW
        from tests.test_observation_scheduler import GIT_SHA as SCHED_GIT_SHA

        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/m1_quote_surface.yaml"
        )

        class _NoRouteOpener:
            """Search succeeds; every swap/v2/order quote returns a typed
            Jupiter NO_ROUTES_FOUND body (HTTP 461) — the M1 entry fails."""

            def __init__(self) -> None:
                self.quote_urls: list[str] = []

            def open(self, url: str) -> dict:
                if "/tokens/v2/search" in url:
                    return {
                        "http_status": 200,
                        "body": [{"id": TOKEN, "liquidity": "2000"}],
                    }
                if "/swap/v2/order" in url:
                    self.quote_urls.append(url)
                    return {
                        "http_status": 461,
                        "body": {
                            "code": 6000,
                            "errorCode": "NO_ROUTES_FOUND",
                            "message": "No routes found",
                        },
                        "url_has_api_key": False,
                    }
                return {"http_status": 200, "body": [{"id": TOKEN}]}

        opener = _NoRouteOpener()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _sched_activate(store, schedule)
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=SCHED_NOW,
                    opener=opener,
                    producer_git_sha=SCHED_GIT_SHA,
                    discovery_rows=[
                        {
                            "id": TOKEN,
                            "liquidity": "2000",
                            "launchpad": "pump.fun",
                            "firstPool": {
                                "createdAt": "2026-09-01T00:00:00Z",
                                "source": "pump.fun",
                            },
                        }
                    ],
                )
                candidates = store.list_candidates(
                    schedule_sha256=schedule["schedule_sha256"],
                    activation_id=activation_id,
                )
                self.assertTrue(candidates, "member must exist after X tick")
                self.assertEqual(candidates[0]["state"], "X_ELIGIBLE")
                # The M1 entry legs landed as typed MISSING (NO_ROUTE) but the
                # member is NOT X_POPULATION_INELIGIBLE: M1 stays measurement,
                # not a population gate.
                dues = store.list_due_in_states_scoped(
                    ("MISSING_TYPED",),
                    schedule_sha256=schedule["schedule_sha256"],
                    activation_id=activation_id,
                    entity_id=TOKEN,
                    point_id="X300",
                )
                m1_missing = {
                    str(item["primitive_id"]) for item in dues
                }
                self.assertIn(
                    "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-USDC10-001", m1_missing
                )
                self.assertTrue(opener.quote_urls, "M1 entry quotes were issued")
            finally:
                store.close()


class ZeroNetworkTests(unittest.TestCase):
    """15/16: tests never open real provider sockets."""

    def test_quote_url_only_canonical_readonly_endpoint(self) -> None:
        url = quote_url(input_mint=USDC_MINT, output_mint=TOKEN, amount="1")
        self.assertTrue(url.startswith("https://api.jup.ag/swap/v2/order?"))
        self.assertNotIn("taker", url)


if __name__ == "__main__":
    unittest.main()
