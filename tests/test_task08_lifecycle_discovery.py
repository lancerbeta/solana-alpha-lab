from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import LifecycleState  # noqa: E402
from solana_alpha_lab.lifecycle_discovery import (  # noqa: E402
    CONTRACT_AS_OF,
    EXPECTED_CATALOG_IDS,
    EXPECTED_CONSUMERS,
    FROZEN_FIXTURE_SHA256,
    NETWORK_DISABLED_BY_DEFAULT,
    OFFICIAL_PUMP_IDL_BLOB_SHA,
    OFFICIAL_PUMP_IDL_PATH,
    OFFICIAL_PUMP_PROGRAM_ID,
    PUMP_EVENT_SUBSET_FIXTURE,
    BudgetInvariantError,
    CoverageInvariantError,
    DiscoveryContractError,
    ExternalActionDisabledError,
    assert_atom2_offline_boundary,
    classify_protocol_event,
    cohort_eligible,
    compile_discovery_contract,
    derive_quiet_state,
    load_frozen_discovery_plan,
    projected_helius_credits,
    validate_durable_metadata,
    validate_pilot_usage,
    validate_probe_usage,
    validate_timestamp_order,
)

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task08"
    / "lifecycle_discovery_contract_v1.json"
)
CONTRACT_PATH = ROOT / "docs" / "contracts" / "lifecycle_discovery_contract_v1.md"
MODULE_PATH = SRC / "solana_alpha_lab" / "lifecycle_discovery.py"


class Task08LifecycleDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.plan = load_frozen_discovery_plan(FIXTURE_PATH)

    def test_frozen_fixture_hash_and_inventory_compile_exactly(self) -> None:
        self.assertEqual(self.plan.fixture_sha256, FROZEN_FIXTURE_SHA256)
        self.assertEqual(self.document["as_of"], CONTRACT_AS_OF)
        self.assertEqual(self.document["atom_id"], "T08-A3")
        self.assertEqual(
            self.document["protocol"]["idl_blob_sha"],
            OFFICIAL_PUMP_IDL_BLOB_SHA,
        )
        self.assertEqual(
            self.document["protocol"]["idl_path"],
            OFFICIAL_PUMP_IDL_PATH,
        )
        self.assertEqual(
            self.document["protocol"]["event_subset_fixture"],
            PUMP_EVENT_SUBSET_FIXTURE,
        )
        self.assertEqual(
            [rule.source_event for rule in self.plan.event_rules],
            [
                "CreateEvent",
                "TradeEvent",
                "CompleteEvent",
                "CompletePumpAmmMigrationEvent",
            ],
        )
        self.assertEqual(self.plan.catalog_ids, EXPECTED_CATALOG_IDS)
        self.assertEqual(self.plan.named_consumers, EXPECTED_CONSUMERS)

    def test_compiler_rejects_contract_and_event_drift(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["task_id"] = "TASK-09"
        with self.assertRaisesRegex(DiscoveryContractError, "task_id_drift"):
            compile_discovery_contract(changed)

        changed = copy.deepcopy(self.document)
        changed["event_vocabulary"][0]["lifecycle_state"] = "DISCOVERED"
        with self.assertRaisesRegex(
            DiscoveryContractError,
            "event_state_CreateEvent_drift",
        ):
            compile_discovery_contract(changed)

        changed = copy.deepcopy(self.document)
        changed["event_vocabulary"].reverse()
        with self.assertRaisesRegex(
            DiscoveryContractError,
            "event_vocabulary_order_or_inventory_drift",
        ):
            compile_discovery_contract(changed)

    def test_outcome_dependent_launch_filters_fail_closed(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["universes"]["launch"]["selection_fields"] = ["price_return"]
        with self.assertRaisesRegex(
            DiscoveryContractError,
            "universe_contract_drift",
        ):
            compile_discovery_contract(changed)

        changed = copy.deepcopy(self.document)
        changed["universes"]["right_censoring"] = "DROP"
        with self.assertRaisesRegex(
            DiscoveryContractError,
            "universe_contract_drift",
        ):
            compile_discovery_contract(changed)

    def test_protocol_events_map_without_future_inference(self) -> None:
        self.assertEqual(
            classify_protocol_event(
                self.plan,
                source_event="CreateEvent",
                transaction_succeeded=True,
            ),
            LifecycleState.CREATED,
        )
        self.assertEqual(
            classify_protocol_event(
                self.plan,
                source_event="TradeEvent",
                transaction_succeeded=True,
            ),
            LifecycleState.ACTIVE,
        )
        self.assertEqual(
            classify_protocol_event(
                self.plan,
                source_event="CompleteEvent",
                transaction_succeeded=True,
            ),
            LifecycleState.MIGRATION_STARTED,
        )
        self.assertEqual(
            classify_protocol_event(
                self.plan,
                source_event="CompletePumpAmmMigrationEvent",
                transaction_succeeded=True,
                destination_program="synthetic-pump-amm",
                destination_pool="synthetic-pool",
            ),
            LifecycleState.MIGRATED,
        )

    def test_failed_and_incomplete_migration_events_are_not_promoted(self) -> None:
        self.assertIsNone(
            classify_protocol_event(
                self.plan,
                source_event="CreateEvent",
                transaction_succeeded=False,
            )
        )
        with self.assertRaisesRegex(
            CoverageInvariantError,
            "migration_destination_required",
        ):
            classify_protocol_event(
                self.plan,
                source_event="CompletePumpAmmMigrationEvent",
                transaction_succeeded=True,
            )
        with self.assertRaisesRegex(
            CoverageInvariantError,
            "unrecognized_protocol_event",
        ):
            classify_protocol_event(
                self.plan,
                source_event="GuessedMigrationEvent",
                transaction_succeeded=True,
            )

    def test_launch_cohort_has_one_pre_outcome_rule(self) -> None:
        self.assertTrue(
            cohort_eligible(
                self.plan,
                provider_role="HELIUS_CHAIN_PRIMARY",
                source_event="CreateEvent",
                transaction_succeeded=True,
                seconds_since_intake_start=7_199,
            )
        )
        for kwargs in (
            {"provider_role": "SOLANA_TRACKER_REST_FALLBACK"},
            {"source_event": "TradeEvent"},
            {"transaction_succeeded": False},
            {"seconds_since_intake_start": 7_200},
        ):
            values = {
                "provider_role": "HELIUS_CHAIN_PRIMARY",
                "source_event": "CreateEvent",
                "transaction_succeeded": True,
                "seconds_since_intake_start": 1,
            }
            values.update(kwargs)
            with self.subTest(values=values):
                self.assertFalse(cohort_eligible(self.plan, **values))

    def test_inactive_requires_complete_coverage_and_six_hours(self) -> None:
        self.assertEqual(
            derive_quiet_state(
                self.plan,
                complete_coverage=False,
                followup_seconds=30_000,
                quiet_seconds=30_000,
            ),
            LifecycleState.UNKNOWN,
        )
        self.assertEqual(
            derive_quiet_state(
                self.plan,
                complete_coverage=True,
                followup_seconds=21_599,
                quiet_seconds=21_599,
            ),
            LifecycleState.UNKNOWN,
        )
        self.assertEqual(
            derive_quiet_state(
                self.plan,
                complete_coverage=True,
                followup_seconds=21_600,
                quiet_seconds=21_600,
            ),
            LifecycleState.INACTIVE,
        )
        self.assertIsNone(
            derive_quiet_state(
                self.plan,
                complete_coverage=True,
                followup_seconds=30_000,
                quiet_seconds=3_600,
            )
        )

    def test_timestamp_order_is_aware_and_point_in_time_safe(self) -> None:
        start = datetime(2026, 7, 25, tzinfo=UTC)
        validate_timestamp_order(
            event_at=start,
            observed_at=start + timedelta(seconds=1),
            first_reliable_available_at=start + timedelta(seconds=2),
            available_at=start + timedelta(seconds=3),
            ingested_at=start + timedelta(seconds=4),
        )
        with self.assertRaisesRegex(
            CoverageInvariantError,
            "timestamp_order_invalid",
        ):
            validate_timestamp_order(
                event_at=start,
                observed_at=start + timedelta(seconds=3),
                first_reliable_available_at=start + timedelta(seconds=2),
                available_at=start + timedelta(seconds=4),
                ingested_at=start + timedelta(seconds=5),
            )
        with self.assertRaisesRegex(
            CoverageInvariantError,
            "timestamp_must_be_timezone_aware",
        ):
            validate_timestamp_order(
                event_at=datetime(2026, 7, 25),
                observed_at=start,
                first_reliable_available_at=start,
                available_at=start,
                ingested_at=start,
            )

    def test_provider_roles_are_asymmetric_and_current(self) -> None:
        primary = self.plan.provider_role_by_id["HELIUS_CHAIN_PRIMARY"]
        fallback = self.plan.provider_role_by_id[
            "SOLANA_TRACKER_REST_FALLBACK"
        ]
        self.assertTrue(primary.event_owner)
        self.assertEqual(primary.method, "logsSubscribe")
        self.assertEqual(primary.commitment, "confirmed")
        self.assertEqual(
            self.document["provider_roles"]["HELIUS_CHAIN_PRIMARY"]["mentions"],
            [OFFICIAL_PUMP_PROGRAM_ID],
        )
        self.assertFalse(fallback.event_owner)
        self.assertEqual(
            fallback.paths,
            (
                "/tokens/latest",
                "/tokens/multi/graduating",
                "/tokens/multi/graduated",
            ),
        )
        self.assertFalse(
            self.document["provider_roles"][
                "SOLANA_TRACKER_REST_FALLBACK"
            ]["premium_datastream_allowed"]
        )

    def test_quota_conflict_is_preserved_conservatively(self) -> None:
        facts = self.document["provider_facts"]
        self.assertEqual(facts["solana_tracker_documented_free_requests"], 10_000)
        self.assertEqual(
            facts["solana_tracker_product_page_free_requests"],
            2_500,
        )
        self.assertEqual(facts["solana_tracker_conservative_allowance"], 2_500)
        self.assertTrue(facts["dashboard_readback_required"])
        self.assertEqual(
            self.plan.pilot_budget["solana_tracker_requests"]
            + self.plan.pilot_budget["solana_tracker_allowance_reserve"],
            2_500,
        )

    def test_credit_models_and_probe_caps_fail_closed(self) -> None:
        self.assertEqual(
            projected_helius_credits(
                stream_bytes=1_000_000,
                rpc_calls=20,
                connections=1,
            ),
            41,
        )
        receipt = validate_probe_usage(
            self.plan,
            elapsed_seconds=600,
            wss_connections=1,
            wss_subscriptions=1,
            notifications=500,
            stream_bytes=1_000_000,
            rpc_followups=20,
            solana_tracker_requests=8,
            received_and_stored_bytes=5_000_000,
            concurrency=1,
            retries=0,
            cash_spend_usd_cents=0,
        )
        self.assertEqual(receipt["helius_credits"], 41)
        with self.assertRaisesRegex(
            BudgetInvariantError,
            "probe_stream_bytes_exceeded",
        ):
            validate_probe_usage(
                self.plan,
                elapsed_seconds=1,
                wss_connections=1,
                wss_subscriptions=1,
                notifications=1,
                stream_bytes=1_000_001,
                rpc_followups=0,
                solana_tracker_requests=0,
                received_and_stored_bytes=1,
                concurrency=1,
                retries=0,
                cash_spend_usd_cents=0,
            )

    def test_pilot_outer_envelope_and_disk_reserve_fail_closed(self) -> None:
        receipt = validate_pilot_usage(
            self.plan,
            elapsed_hours=24,
            wss_initial_connections=1,
            wss_reconnects=6,
            stream_bytes=500_000_000,
            rpc_followups=5_000,
            solana_tracker_requests=1_200,
            dataset_bytes=1_073_741_824,
            largest_partition_bytes=67_108_864,
            free_bytes_after_write=21_474_836_480,
            concurrency=1,
            cash_spend_usd_cents=0,
        )
        self.assertEqual(receipt["helius_credits"], 15_007)
        with self.assertRaisesRegex(
            BudgetInvariantError,
            "pilot_free_space_reserve_breached",
        ):
            validate_pilot_usage(
                self.plan,
                elapsed_hours=1,
                wss_initial_connections=1,
                wss_reconnects=0,
                stream_bytes=1,
                rpc_followups=0,
                solana_tracker_requests=0,
                dataset_bytes=1,
                largest_partition_bytes=1,
                free_bytes_after_write=21_474_836_479,
                concurrency=1,
                cash_spend_usd_cents=0,
            )

    def test_durable_metadata_rejects_secrets_and_machine_paths(self) -> None:
        safe = validate_durable_metadata(
            {
                "mint": "synthetic-mint",
                "status": "UNKNOWN",
                "logical_location": "raw/task08/run-001",
            }
        )
        self.assertIn(b'"status":"UNKNOWN"', safe)

        with self.assertRaisesRegex(
            DiscoveryContractError,
            "forbidden_durable_auth_field",
        ):
            validate_durable_metadata({"authorization": "synthetic"})
        with self.assertRaisesRegex(
            DiscoveryContractError,
            "absolute_machine_path_forbidden",
        ):
            validate_durable_metadata({"location": "C:\\private\\run"})
        with self.assertRaisesRegex(
            DiscoveryContractError,
            "explicit_sensitive_value_detected",
        ):
            validate_durable_metadata(
                {"value": "prefix-SYNTHETIC-SENSITIVE-suffix"},
                explicit_sensitive_values=("SYNTHETIC-SENSITIVE",),
            )

    def test_atom2_boundary_and_source_contain_no_transport(self) -> None:
        self.assertTrue(NETWORK_DISABLED_BY_DEFAULT)
        assert_atom2_offline_boundary()
        for name, kwargs in (
            ("network", {"network_requested": True}),
            ("credential_use", {"credential_use_requested": True}),
            ("local_data_write", {"local_data_write_requested": True}),
            ("dependency_change", {"dependency_change_requested": True}),
        ):
            with self.subTest(name=name), self.assertRaisesRegex(
                ExternalActionDisabledError,
                f"atom2_{name}_disabled",
            ):
                assert_atom2_offline_boundary(**kwargs)

        source = MODULE_PATH.read_text(encoding="utf-8")
        for marker in (
            "import httpx",
            "import requests",
            "import urllib",
            "import websockets",
            "ClientSession",
            "socket.",
            "os.environ",
            "getenv(",
        ):
            self.assertNotIn(marker, source)

    def test_contract_records_exact_nonclaims_and_protocol_pin(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        for marker in (
            "PINNED_OFFICIAL_IDL_BLOB",
            OFFICIAL_PUMP_IDL_BLOB_SHA,
            "It is not alpha",
            "Premium Datastream is excluded",
            "does not update Catalog",
            "USD 0",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
