from __future__ import annotations

import sys
import unittest
import unittest.mock
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.early_icp_freeze_acceptance import (  # noqa: E402
    ATOM_ID,
    EARLY_ONLY_ICP_CONFIRMED,
    IcpFreezeError,
    TOPTRADED_NOT_SAME_POPULATION,
    build_acceptance,
    canonical_candidate,
    load_config,
    project_cohort,
    project_seasoned_branch_close,
    reconcile,
    verify_local_pins,
)

DECISION_TIME = datetime(2026, 8, 21, 12, 23, 26, tzinfo=timezone.utc)
LIVE_EVIDENCE_ROOT = ROOT / "local/in_scope_population_live_supply_gate"
LIVE_EVIDENCE_PRESENT = (LIVE_EVIDENCE_ROOT / "probe_runtime_receipt_v1.json").is_file()


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "mint-a",
        "launchpad": "pump.fun",
        "liquidity": 2710.76,
        "firstPool": {"createdAt": "2026-08-21T12:18:16Z"},
    }
    base.update(overrides)
    return base


class EarlyIcpFreezeAcceptanceTests(unittest.TestCase):
    def test_factory_runner_unchanged(self) -> None:
        config = load_config(ROOT)
        from solana_alpha_lab.early_icp_freeze_acceptance import sha256_file

        self.assertEqual(
            sha256_file(ROOT / config["factory_runner"]),
            config["factory_runner_sha256"],
        )

    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/early_icp_freeze/a1_runtime_receipt_v1.json
    @unittest.skipUnless(LIVE_EVIDENCE_PRESENT, "LOCAL_A4_ABSENT")
    def test_pinned_local_evidence_replay_confirms_early_only_icp(self) -> None:
        config = load_config(ROOT)
        runtime = reconcile(ROOT, config)
        self.assertEqual(runtime["atom_id"], ATOM_ID)
        self.assertEqual(runtime["decision"]["terminal"], EARLY_ONLY_ICP_CONFIRMED)
        self.assertEqual(runtime["early_cohort"]["acquisition"], "WAIT_THEN_SEARCH")
        self.assertGreaterEqual(runtime["early_cohort"]["early_n"], 12)
        self.assertEqual(runtime["decision"]["seasoned_branch_terminal"], TOPTRADED_NOT_SAME_POPULATION)
        self.assertFalse(runtime["decision"]["maturity_on_critical_path"])
        self.assertEqual(runtime["provider_api_rpc_wss_calls"], 0)
        self.assertIn("NO_SECOND_TOPTRADED_ATTEMPT", runtime["non_claims"])

    def test_pump_fun_age_liq_is_product_early_with_membership_reason(self) -> None:
        candidate = canonical_candidate(
            mint="m1",
            source_channel="DISCOVERY:SEARCH_WAIT_THEN",
            observed_at="2026-08-21T12:23:26Z",
            decision_time=DECISION_TIME,
            row=_row(),
            liquidity_usd_min=Decimal(1000),
        )
        assert candidate is not None
        self.assertEqual(candidate["population_class"], "EARLY")
        self.assertEqual(candidate["source_channel"], "DISCOVERY:SEARCH_WAIT_THEN")
        self.assertNotEqual(candidate["source_channel"], candidate["population_class"])
        self.assertEqual(candidate["membership_reason"], "LAUNCHPAD_AGE_LIQUIDITY_AT_DECISION_TIME")

    def test_source_channel_never_grants_population_membership(self) -> None:
        candidate = canonical_candidate(
            mint="m2",
            source_channel="DISCOVERY:TRADED",
            observed_at="2026-08-21T12:23:26Z",
            decision_time=DECISION_TIME,
            row=_row(firstPool={"createdAt": "2026-08-21T10:00:00Z"}),
            liquidity_usd_min=Decimal(1000),
        )
        self.assertIsNone(candidate)

    def test_unknown_launchpad_excluded_not_zero(self) -> None:
        candidate = canonical_candidate(
            mint="m3",
            source_channel="DISCOVERY:TRADED",
            observed_at="2026-08-21T12:23:26Z",
            decision_time=DECISION_TIME,
            row=_row(launchpad=None),
            liquidity_usd_min=Decimal(1000),
        )
        self.assertIsNone(candidate)

    def test_below_liquidity_minimum_is_not_product(self) -> None:
        candidate = canonical_candidate(
            mint="m4",
            source_channel="DISCOVERY:SEARCH_WAIT_THEN",
            observed_at="2026-08-21T12:23:26Z",
            decision_time=DECISION_TIME,
            row=_row(liquidity=999.99),
            liquidity_usd_min=Decimal(1000),
        )
        self.assertIsNone(candidate)

    def test_non_finite_liquidity_rejected(self) -> None:
        candidate = canonical_candidate(
            mint="m5",
            source_channel="DISCOVERY:SEARCH_WAIT_THEN",
            observed_at="2026-08-21T12:23:26Z",
            decision_time=DECISION_TIME,
            row=_row(liquidity="Infinity"),
            liquidity_usd_min=Decimal(1000),
        )
        self.assertIsNone(candidate)

    def test_missing_first_pool_timestamp_is_not_product(self) -> None:
        candidate = canonical_candidate(
            mint="m6",
            source_channel="DISCOVERY:SEARCH_WAIT_THEN",
            observed_at="2026-08-21T12:23:26Z",
            decision_time=DECISION_TIME,
            row=_row(firstPool={}),
            liquidity_usd_min=Decimal(1000),
        )
        self.assertIsNone(candidate)

    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/early_icp_freeze/a1_runtime_receipt_v1.json
    @unittest.skipUnless(LIVE_EVIDENCE_PRESENT, "LOCAL_A4_ABSENT")
    def test_seasoned_branch_close_reports_toptraded_not_same_population(self) -> None:
        config = load_config(ROOT)
        close = project_seasoned_branch_close(ROOT, config)
        self.assertEqual(close["terminal"], TOPTRADED_NOT_SAME_POPULATION)
        self.assertGreater(close["rows_n"], 0)

    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/early_icp_freeze/a1_runtime_receipt_v1.json
    @unittest.skipUnless(LIVE_EVIDENCE_PRESENT, "LOCAL_A4_ABSENT")
    def test_cohort_projection_fails_closed_below_minimum(self) -> None:
        config = load_config(ROOT)
        weakened = dict(config)
        weakened["supply_thresholds"] = {"early_n_min": 28}
        with self.assertRaisesRegex(IcpFreezeError, "EARLY_N_BELOW_MINIMUM"):
            project_cohort(ROOT, weakened)

    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/early_icp_freeze/a1_runtime_receipt_v1.json
    @unittest.skipUnless(LIVE_EVIDENCE_PRESENT, "LOCAL_A4_ABSENT")
    def test_pin_hash_drift_detected(self) -> None:
        config = load_config(ROOT)
        pin_path = (ROOT / config["pins"]["live_search_body"]["path"]).resolve()
        real_read_bytes = Path.read_bytes

        def poisoned_read_bytes(path_self: Path, *args: object, **kwargs: object) -> bytes:
            if path_self.resolve() == pin_path:
                return b"tampered"
            return real_read_bytes(path_self)

        with unittest.mock.patch.object(Path, "read_bytes", poisoned_read_bytes):
            with self.assertRaisesRegex(IcpFreezeError, "PIN_HASH_MISMATCH:live_search_body"):
                verify_local_pins(ROOT, config)

    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/early_icp_freeze/a1_acceptance_v1.json
    @unittest.skipUnless(LIVE_EVIDENCE_PRESENT, "LOCAL_A4_ABSENT")
    def test_acceptance_builds_from_runtime(self) -> None:
        config = load_config(ROOT)
        runtime = reconcile(ROOT, config)
        acceptance = build_acceptance(runtime)
        self.assertEqual(acceptance["verdict"], EARLY_ONLY_ICP_CONFIRMED)
        self.assertEqual(acceptance["frozen_icp_id"], "ICP-EARLY-PUMPFUN-V1")
        self.assertFalse(acceptance["promotable"])
        self.assertEqual(acceptance["provider_api_rpc_wss_calls"], 0)


if __name__ == "__main__":
    unittest.main()
