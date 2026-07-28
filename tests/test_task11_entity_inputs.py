from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import (  # noqa: E402
    EntityInputSnapshot,
)
from solana_alpha_lab.entity_inputs import (  # noqa: E402
    CONTRACT_AS_OF,
    EXPECTED_EVIDENCE_CLASSES,
    EXPECTED_MANAGED_FILES,
    EXPECTED_METRICS,
    FROZEN_FIXTURE_SHA256,
    NETWORK_DISABLED_BY_DEFAULT,
    PRIMARY_METHODS,
    PRIMARY_PROVIDER,
    AvailabilityClass,
    ConfidenceLevel,
    EntityInputContractError,
    EvidenceClass,
    ExclusionAssessment,
    ExclusionDisposition,
    HolderAccountObservation,
    HolderSnapshotInput,
    OfflineBoundaryError,
    assert_atom2_offline_boundary,
    calculate_holder_metrics,
    compile_entity_contract,
    load_frozen_entity_contract,
    project_entity_snapshots,
    validate_durable_metadata,
)

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task11"
    / "entity_input_observation_contract_v1.json"
)
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "entity_input_observation_contract_v1.md"
)


def _account(
    suffix: str,
    amount_atomic: int,
    *,
    owner: str | None,
    slot: int = 101,
) -> HolderAccountObservation:
    return HolderAccountObservation(
        token_account=f"synthetic-account-{suffix}",
        owner=owner,
        amount_atomic=amount_atomic,
        context_slot=slot,
    )


def _snapshot(
    accounts: tuple[HolderAccountObservation, ...],
    *,
    supply_atomic: int = 1_000_000,
    observed_offset: int = 0,
) -> HolderSnapshotInput:
    start = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    observed = start + timedelta(seconds=observed_offset)
    return HolderSnapshotInput(
        snapshot_id="synthetic-snapshot-001",
        mint="synthetic-mint",
        decimals=6,
        supply_atomic=supply_atomic,
        supply_context_slot=100,
        largest_accounts_context_slot=101,
        owners_context_slot=102,
        accounts=accounts,
        event_time=observed,
        observed_at=observed,
        first_reliable_available_at=observed + timedelta(seconds=1),
        available_to_strategy_at=observed + timedelta(seconds=1),
        ingested_at=observed + timedelta(seconds=2),
        source=PRIMARY_PROVIDER,
        source_version="solana-rpc-observed-2026-07-28",
        revision_number=1,
        revision_of=None,
        raw_event_ids=(
            "raw-supply-001",
            "raw-largest-001",
            "raw-owners-001",
        ),
    )


def _include(account: HolderAccountObservation) -> ExclusionAssessment:
    return ExclusionAssessment(
        token_account=account.token_account,
        disposition=ExclusionDisposition.INCLUDE,
        reason=None,
        evidence_ref=None,
        evidence_class=EvidenceClass.RAW_ONCHAIN,
        confidence=ConfidenceLevel.HIGH,
    )


class Task11EntityInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.document = json.loads(cls.fixture_bytes)
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")

    def test_frozen_contract_identity_and_inventory_are_exact(self) -> None:
        loaded = load_frozen_entity_contract(FIXTURE_PATH)
        self.assertEqual(loaded, self.document)
        self.assertEqual(self.document["as_of"], CONTRACT_AS_OF)
        self.assertEqual(
            tuple(item["class"] for item in self.document["evidence_classes"]),
            EXPECTED_EVIDENCE_CLASSES,
        )
        self.assertEqual(
            self.document["primary_provider"]["provider_id"],
            PRIMARY_PROVIDER,
        )
        self.assertEqual(
            tuple(self.document["primary_provider"]["methods"]),
            PRIMARY_METHODS,
        )
        self.assertEqual(
            tuple(self.document["projection_metrics"]),
            EXPECTED_METRICS,
        )
        self.assertEqual(
            tuple(self.document["authority"]["managed_files"]),
            EXPECTED_MANAGED_FILES,
        )
        self.assertEqual(
            FROZEN_FIXTURE_SHA256,
            "b5fe517e3ddd6d0668edc35762108820"
            "82203edbf1f3bfca92b38a9164a1c686",
        )

    def test_contract_compiler_rejects_semantic_drift(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["task_id"] = "TASK-12"
        with self.assertRaisesRegex(EntityInputContractError, "task_id_drift"):
            compile_entity_contract(changed)

        changed = copy.deepcopy(self.document)
        changed["evidence_classes"].reverse()
        with self.assertRaisesRegex(
            EntityInputContractError,
            "evidence_class_inventory_or_order_drift",
        ):
            compile_entity_contract(changed)

        changed = copy.deepcopy(self.document)
        changed["authority"]["provider_api_rpc_wss_calls"] = 1
        with self.assertRaisesRegex(
            EntityInputContractError,
            "offline_authority_drift",
        ):
            compile_entity_contract(changed)

    def test_partial_exclusions_keep_adjusted_null(self) -> None:
        first = _account("a", 400_000, owner="synthetic-owner-a")
        second = _account("b", 200_000, owner="synthetic-owner-b")
        third = _account("c", 100_000, owner=None, slot=102)
        snapshot = _snapshot((first, second, third))
        assessments = (
            _include(first),
            ExclusionAssessment(
                token_account=second.token_account,
                disposition=ExclusionDisposition.EXCLUDE,
                reason="known_pool_vault",
                evidence_ref="synthetic-evidence-pool-001",
                evidence_class=EvidenceClass.PROJECT_INFERENCE,
                confidence=ConfidenceLevel.MEDIUM,
            ),
            ExclusionAssessment(
                token_account=third.token_account,
                disposition=ExclusionDisposition.UNRESOLVED,
                reason="owner_unresolved",
                evidence_ref=None,
                evidence_class=EvidenceClass.RAW_ONCHAIN,
                confidence=ConfidenceLevel.UNKNOWN,
            ),
        )
        metrics = calculate_holder_metrics(
            snapshot,
            assessments,
            exclusion_inventory_complete=False,
            excluded_supply_atomic_total=None,
            exclusion_inventory_evidence_ref=None,
        )
        self.assertEqual(metrics.raw_top_accounts_amount_atomic, 700_000)
        self.assertEqual(
            metrics.raw_top_accounts_supply_share,
            Decimal("0.7"),
        )
        self.assertIsNone(metrics.adjusted_top_accounts_supply_share)
        self.assertEqual(metrics.excluded_top_accounts_amount_atomic, 200_000)
        self.assertEqual(metrics.unresolved_owner_account_count, 1)
        self.assertEqual(metrics.unresolved_exclusion_account_count, 1)
        self.assertEqual(metrics.context_slot_spread, 2)
        self.assertEqual(
            metrics.availability_class,
            AvailabilityClass.PARTIAL_CURRENT_SNAPSHOT,
        )
        self.assertIn(
            "ADJUSTED_CONCENTRATION_UNAVAILABLE",
            metrics.quality_flags,
        )

    def test_complete_exclusions_enable_adjusted_metric(self) -> None:
        first = _account("a", 400_000, owner="synthetic-owner-a")
        second = _account("b", 200_000, owner="synthetic-owner-b")
        third = _account(
            "c",
            100_000,
            owner="synthetic-owner-c",
            slot=102,
        )
        snapshot = _snapshot((first, second, third))
        assessments = (
            _include(first),
            ExclusionAssessment(
                token_account=second.token_account,
                disposition=ExclusionDisposition.EXCLUDE,
                reason="raw_program_owned_pool_vault",
                evidence_ref="raw-account-owner-001",
                evidence_class=EvidenceClass.RAW_ONCHAIN,
                confidence=ConfidenceLevel.HIGH,
            ),
            _include(third),
        )
        metrics = calculate_holder_metrics(
            snapshot,
            assessments,
            exclusion_inventory_complete=True,
            excluded_supply_atomic_total=200_000,
            exclusion_inventory_evidence_ref=(
                "synthetic-exclusion-inventory-001"
            ),
        )
        self.assertEqual(
            metrics.adjusted_top_accounts_supply_share,
            Decimal("0.625"),
        )
        self.assertEqual(metrics.unresolved_owner_account_count, 0)
        self.assertEqual(metrics.unresolved_exclusion_account_count, 0)
        self.assertEqual(
            metrics.exclusion_inventory_evidence_ref,
            "synthetic-exclusion-inventory-001",
        )
        self.assertEqual(
            metrics.availability_class,
            AvailabilityClass.RECONSTRUCTIBLE_CURRENT_SNAPSHOT,
        )

    def test_vendor_label_cannot_drive_exclusion(self) -> None:
        with self.assertRaisesRegex(
            EntityInputContractError,
            "vendor_label_cannot_exclude_account",
        ):
            ExclusionAssessment(
                token_account="synthetic-account-a",
                disposition=ExclusionDisposition.EXCLUDE,
                reason="vendor_says_bundler",
                evidence_ref="vendor-label-001",
                evidence_class=EvidenceClass.VENDOR_LABEL,
                confidence=ConfidenceLevel.HIGH,
            )

    def test_missing_owner_and_zero_supply_are_not_zero_metrics(self) -> None:
        account = _account("zero", 0, owner=None)
        snapshot = _snapshot((account,), supply_atomic=0)
        metrics = calculate_holder_metrics(
            snapshot,
            (
                ExclusionAssessment(
                    token_account=account.token_account,
                    disposition=ExclusionDisposition.UNRESOLVED,
                    reason="owner_missing",
                    evidence_ref=None,
                    evidence_class=EvidenceClass.RAW_ONCHAIN,
                    confidence=ConfidenceLevel.UNKNOWN,
                ),
            ),
            exclusion_inventory_complete=False,
            excluded_supply_atomic_total=None,
            exclusion_inventory_evidence_ref=None,
        )
        self.assertIsNone(metrics.raw_top_accounts_supply_share)
        self.assertIsNone(metrics.adjusted_top_accounts_supply_share)
        self.assertEqual(metrics.unresolved_owner_account_count, 1)
        self.assertIn("ZERO_SUPPLY_SHARE_UNDEFINED", metrics.quality_flags)

    def test_incomplete_or_incoherent_exclusion_inventory_fails_closed(
        self,
    ) -> None:
        account = _account("a", 100, owner="synthetic-owner-a")
        snapshot = _snapshot((account,))
        unresolved = ExclusionAssessment(
            token_account=account.token_account,
            disposition=ExclusionDisposition.UNRESOLVED,
            reason="classification_pending",
            evidence_ref=None,
            evidence_class=EvidenceClass.PROJECT_INFERENCE,
            confidence=ConfidenceLevel.UNKNOWN,
        )
        with self.assertRaisesRegex(
            EntityInputContractError,
            "complete_exclusion_inventory_has_unresolved",
        ):
            calculate_holder_metrics(
                snapshot,
                (unresolved,),
                exclusion_inventory_complete=True,
                excluded_supply_atomic_total=0,
                exclusion_inventory_evidence_ref=(
                    "synthetic-exclusion-inventory-002"
                ),
            )
        with self.assertRaisesRegex(
            EntityInputContractError,
            "partial_exclusion_inventory_cannot_claim_total",
        ):
            calculate_holder_metrics(
                snapshot,
                (_include(account),),
                exclusion_inventory_complete=False,
                excluded_supply_atomic_total=0,
                exclusion_inventory_evidence_ref=None,
            )
        with self.assertRaisesRegex(
            EntityInputContractError,
            "complete_exclusion_inventory_requires_evidence_ref",
        ):
            calculate_holder_metrics(
                snapshot,
                (_include(account),),
                exclusion_inventory_complete=True,
                excluded_supply_atomic_total=0,
                exclusion_inventory_evidence_ref=None,
            )

    def test_snapshot_rejects_duplicate_accounts_and_timestamp_drift(
        self,
    ) -> None:
        account = _account("a", 100, owner="synthetic-owner-a")
        with self.assertRaisesRegex(
            EntityInputContractError,
            "duplicate_token_account",
        ):
            _snapshot((account, account))

        start = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
        values = {
            "snapshot_id": "synthetic-snapshot-002",
            "mint": "synthetic-mint",
            "decimals": 6,
            "supply_atomic": 1_000,
            "supply_context_slot": 100,
            "largest_accounts_context_slot": 101,
            "owners_context_slot": 102,
            "accounts": (account,),
            "event_time": start,
            "observed_at": start,
            "first_reliable_available_at": start + timedelta(seconds=2),
            "available_to_strategy_at": start + timedelta(seconds=1),
            "ingested_at": start + timedelta(seconds=3),
            "source": PRIMARY_PROVIDER,
            "source_version": "synthetic",
            "revision_number": 1,
            "revision_of": None,
            "raw_event_ids": ("raw-a", "raw-b", "raw-c"),
        }
        with self.assertRaisesRegex(
            EntityInputContractError,
            "timestamp_order_violation",
        ):
            HolderSnapshotInput(**values)

    def test_projection_is_deterministic_and_task05_compatible(self) -> None:
        first = _account("a", 400_000, owner="synthetic-owner-a")
        second = _account("b", 200_000, owner="synthetic-owner-b")
        snapshot = _snapshot((first, second))
        metrics = calculate_holder_metrics(
            snapshot,
            (_include(first), _include(second)),
            exclusion_inventory_complete=True,
            excluded_supply_atomic_total=0,
            exclusion_inventory_evidence_ref=(
                "synthetic-exclusion-inventory-003"
            ),
        )
        rows = project_entity_snapshots(snapshot, metrics)
        repeated = project_entity_snapshots(snapshot, metrics)
        shifted_rows = project_entity_snapshots(
            _snapshot((first, second), observed_offset=1),
            metrics,
        )
        self.assertEqual(rows, repeated)
        self.assertNotEqual(
            rows[0].content_sha256,
            shifted_rows[0].content_sha256,
        )
        self.assertEqual(len(rows), len(EXPECTED_METRICS))
        self.assertTrue(
            all(isinstance(row, EntityInputSnapshot) for row in rows)
        )
        self.assertEqual(
            tuple(row.metric_name for row in rows),
            EXPECTED_METRICS,
        )
        adjusted = next(
            row
            for row in rows
            if row.metric_name == "adjusted_top_accounts_supply_share"
        )
        self.assertEqual(adjusted.metric_value_decimal, Decimal("0.6"))
        self.assertIn(
            "EVIDENCE_CLASS=DERIVED_ADJUSTED",
            adjusted.quality_flags or "",
        )
        self.assertIn(
            "EVENT_TIME_PROXY_OBSERVED_AT_NO_BLOCK_TIME",
            adjusted.quality_flags or "",
        )

    def test_offline_boundary_and_durable_metadata_fail_closed(self) -> None:
        self.assertTrue(NETWORK_DISABLED_BY_DEFAULT)
        assert_atom2_offline_boundary(
            provider_calls=0,
            credentials_used=0,
            cash_spend_usd_cents=0,
            wallet_signer_transaction_actions=0,
        )
        for changed in (
            {"provider_calls": 1},
            {"credentials_used": 1},
            {"cash_spend_usd_cents": 1},
            {"wallet_signer_transaction_actions": 1},
        ):
            values = {
                "provider_calls": 0,
                "credentials_used": 0,
                "cash_spend_usd_cents": 0,
                "wallet_signer_transaction_actions": 0,
            }
            values.update(changed)
            with self.subTest(values=values):
                with self.assertRaises(OfflineBoundaryError):
                    assert_atom2_offline_boundary(**values)

        with self.assertRaisesRegex(
            EntityInputContractError,
            "sensitive_key_forbidden",
        ):
            validate_durable_metadata({"api_key": "forbidden"})
        with self.assertRaisesRegex(
            EntityInputContractError,
            "absolute_machine_path_forbidden",
        ):
            validate_durable_metadata(
                {"path": "C:" + "/Users/example/raw.json"}
            )
        validate_durable_metadata(
            {
                "token_mint": "synthetic-mint",
                "source": "SOLANA_STANDARD_RPC",
            }
        )

    def test_markdown_contract_freezes_critical_boundaries(self) -> None:
        required_phrases = (
            "RAW_TOP_ACCOUNT_CONCENTRATION_FEASIBILITY",
            "`RAW_ONCHAIN`",
            "`DERIVED_ADJUSTED`",
            "`VENDOR_LABEL`",
            "`PROJECT_INFERENCE`",
            "missing owner is not zero",
            "zero supply makes the share undefined (`null`)",
            "vendor labels cannot drive exclusions",
            "separate exact authority envelope",
        )
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.contract)


if __name__ == "__main__":
    unittest.main()
