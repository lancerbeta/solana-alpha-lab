from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "catalog/schemas/lifecycle_registry.schema.json").read_text(
        encoding="utf-8"
    )
)
VALIDATOR = Draft202012Validator(SCHEMA)

REGISTRIES = {
    "research_cycles": ("research_cycles.yaml", "SMIAL-REGISTRY-RESEARCH-CYCLES"),
    "hypotheses": ("hypotheses.yaml", "SMIAL-REGISTRY-HYPOTHESES"),
    "global_trial_ledger": (
        "global_trial_ledger.yaml",
        "SMIAL-REGISTRY-GLOBAL-TRIAL-LEDGER",
    ),
    "feature_catalog": ("feature_catalog.yaml", "SMIAL-REGISTRY-FEATURE-CATALOG"),
    "holdout_consumption": (
        "holdout_consumption.yaml",
        "SMIAL-REGISTRY-HOLDOUT-CONSUMPTION",
    ),
    "strategies": ("strategies.yaml", "SMIAL-REGISTRY-STRATEGIES"),
    "bot_instances": ("bot_instances.yaml", "SMIAL-REGISTRY-BOT-INSTANCES"),
    "reuse_candidates": (
        "reuse_candidates.yaml",
        "SMIAL-REGISTRY-REUSE-CANDIDATES",
    ),
    "decisions_negative_results": (
        "decisions_negative_results.yaml",
        "SMIAL-REGISTRY-DECISIONS-NEGATIVE-RESULTS",
    ),
}

BASE_RECORD = {
    "record_id": "SYNTHETIC-TEST-001",
    "status": "PROPOSED",
    "created_at": "2026-07-21T00:00:00Z",
    "evidence_asset_ids": [],
}

RECORDS = {
    "research_cycles": {"record_kind": "research_cycle", "title": "Synthetic cycle"},
    "hypotheses": {
        "record_kind": "hypothesis",
        "research_cycle_id": "SYNTHETIC-CYCLE-001",
        "statement": "Synthetic hypothesis statement",
    },
    "global_trial_ledger": {
        "record_kind": "trial",
        "hypothesis_id": "SYNTHETIC-HYPOTHESIS-001",
        "outcome": "PENDING",
    },
    "feature_catalog": {
        "record_kind": "feature",
        "definition": "Synthetic feature definition",
        "first_reliable_available_at": "2026-07-21T00:00:00Z",
    },
    "holdout_consumption": {
        "record_kind": "holdout_consumption",
        "research_cycle_id": "SYNTHETIC-CYCLE-001",
        "consumed_at": "2026-07-21T00:00:00Z",
    },
    "strategies": {
        "record_kind": "strategy",
        "hypothesis_ids": ["SYNTHETIC-HYPOTHESIS-001"],
    },
    "bot_instances": {
        "record_kind": "bot_instance",
        "strategy_id": "SYNTHETIC-STRATEGY-001",
    },
    "reuse_candidates": {
        "record_kind": "reuse_candidate",
        "derived_from": "PRE-GIT-TASK01-A024",
    },
    "decisions_negative_results": {
        "record_kind": "negative_result",
        "summary": "Synthetic negative result",
    },
}


def production_document(registry_type: str) -> dict:
    filename, _ = REGISTRIES[registry_type]
    return yaml.safe_load((ROOT / "registries" / filename).read_text(encoding="utf-8"))


def synthetic_document(registry_type: str) -> dict:
    _, registry_id = REGISTRIES[registry_type]
    record = copy.deepcopy(BASE_RECORD)
    record.update(RECORDS[registry_type])
    return {
        "schema_version": "1.0",
        "registry_id": registry_id,
        "registry_type": registry_type,
        "as_of": "2026-07-21",
        "truth_owner": "TASK-03",
        "source_asset_ids": [],
        "records": [record],
    }


def synthetic_reuse_v11_document() -> dict:
    document = synthetic_document("reuse_candidates")
    document["schema_version"] = "1.1"
    document["records"][0].update(
        {
            "component_area": "A0_RUNTIME",
            "candidate_name": "Synthetic candidate",
            "verdict": "ADOPT",
            "decision_status": "ACCEPTED",
            "pin": "1.2.3",
            "decision_owner": "TASK-04_ARCHITECTURE_OWNER",
            "named_consumers": ["TASK-05"],
            "matrix_asset_id": "MATRIX-T04-MVP-STACK-001",
            "next_validation": "TASK-05_CONTRACT_FIXTURE_VALIDATION",
        }
    )
    return document


class LifecycleRegistryTests(unittest.TestCase):
    def test_all_production_registries_are_valid(self) -> None:
        for registry_type in REGISTRIES:
            with self.subTest(registry_type=registry_type):
                document = production_document(registry_type)
                self.assertFalse(list(VALIDATOR.iter_errors(document)))
                if registry_type == "reuse_candidates":
                    self.assertEqual(document["schema_version"], "1.1")
                    self.assertEqual(len(document["records"]), 52)
                elif registry_type == "global_trial_ledger":
                    self.assertEqual(
                        [record["record_id"] for record in document["records"]],
                        [
                            "TRIAL-T23-R2-DIAGNOSTIC-PROJECTION-ATTEMPT-01",
                            "TRIAL-T23-R2-DIAGNOSTIC-PROJECTION-ATTEMPT-02",
                            "TRIAL-T23-BOUNDED-ANALYSIS-ADVERSARIAL-ACCEPTANCE-001",
                            "TRIAL-RC002-H11-LIFECYCLE-CLOCK-SCREEN-001",
                            "TRIAL-RC002-H11-MIGRATION-CLOCK-CAPTURE-001",
                            "TRIAL-RC002-H11-NEXT-GTA-TARGET-001",
                            "TRIAL-RC002-H11-NAMED-MINT-GTA-001",
                            "TRIAL-RC002-H11-BONDING-CURVE-PDA-GTA-001",
                        ],
                    )
                    self.assertEqual(
                        [record["outcome"] for record in document["records"]],
                        ["FAIL", "INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE", "PASS", "INCONCLUSIVE", "INCONCLUSIVE"],
                    )
                elif registry_type == "decisions_negative_results":
                    self.assertEqual(
                        [record["record_id"] for record in document["records"]],
                        [
                            "NEGATIVE-T24-ENTITY-SIGNAL-V1-001",
                            "DECISION-OWNER-AUTHORITY-PACKET-001",
                            "DECISION-CANARY-SPECIFICATION-ONLY-001",
                            "NEGATIVE-T27-PUBLIC-HISTORY-ROUTE-V1-001",
                            "DECISION-T30-A9-NAMED-PARTIAL-CAPTURE-001",
                            "NEGATIVE-T30-CURRENT-DATA-ROUTE-001",
                            "NEGATIVE-T30-BITQUERY-PIT-ROUTE-001",
                            "NEGATIVE-T30-HELIUS-GTA-ONE-SHOT-001",
                            "DECISION-T30-HELIUS-COMPLETE-RAW-BATCH-001",
                            "DECISION-T30-A24-RAW-TO-PIT-001",
                            "DECISION-T30-A25-H07-H01-MEASURABILITY-001",
                            "DECISION-DELIVERY-PREFLIGHT-SKIP-PROOF-001",
                            "DECISION-T30-A26-FIVE-DOLLAR-CANNOT-FALSIFY-001",
                            "DECISION-T30-A27-H07-H01-PARK-001",
                            "DECISION-T36-RC002-H11-LIFECYCLE-CLOCK-001",
                            "DECISION-T37-RC002-H11-CLOCK-CAPTURE-001",
                            "DECISION-T38-RC002-H11-NEXT-GTA-001",
                            "DECISION-T39-RC002-H11-NAMED-MINT-GTA-001",
                            "DECISION-T40-RC002-H11-BONDING-CURVE-PDA-GTA-001",
                            "DECISION-RC002-H11-PARK-FROM-PRIORITY-001",
                            "DECISION-RC001-H13-PARK-FROM-PRIORITY-001",
                            "DECISION-QUOTE-NATIVE-EVIDENCE-CHANNEL-INVALID-CAPTURE-001",
                        ],
                    )
                    self.assertEqual(
                        [record["record_kind"] for record in document["records"]],
                        [
                            "negative_result",
                            "decision",
                            "decision",
                            "negative_result",
                            "decision",
                            "negative_result",
                            "negative_result",
                            "negative_result",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                            "decision",
                        ],
                    )
                else:
                    self.assertEqual(document["schema_version"], "1.0")
                    self.assertEqual(document["records"], [])

    def test_every_discriminator_accepts_its_minimal_record(self) -> None:
        for registry_type in REGISTRIES:
            with self.subTest(registry_type=registry_type):
                self.assertFalse(
                    list(VALIDATOR.iter_errors(synthetic_document(registry_type)))
                )

    def test_every_discriminator_rejects_wrong_record_kind(self) -> None:
        for registry_type in REGISTRIES:
            with self.subTest(registry_type=registry_type):
                document = synthetic_document(registry_type)
                document["records"][0]["record_kind"] = "wrong_kind"
                self.assertTrue(list(VALIDATOR.iter_errors(document)))

    def test_every_discriminator_rejects_wrong_record_shape(self) -> None:
        for registry_type in REGISTRIES:
            with self.subTest(registry_type=registry_type):
                document = synthetic_document(registry_type)
                document["records"][0]["unexpected"] = True
                self.assertTrue(list(VALIDATOR.iter_errors(document)))

    def test_reuse_registry_references_history_without_copying_truth(self) -> None:
        document = production_document("reuse_candidates")
        self.assertIn("PRE-GIT-TASK01-A024", document["source_asset_ids"])
        self.assertEqual(len(document["records"]), 52)
        self.assertTrue(all(record["derived_from"] == "PRE-GIT-TASK01-A024" for record in document["records"]))

    def test_historical_reuse_v10_remains_valid(self) -> None:
        self.assertFalse(list(VALIDATOR.iter_errors(synthetic_document("reuse_candidates"))))

    def test_reuse_v11_requires_compact_decision_contract(self) -> None:
        document = synthetic_reuse_v11_document()
        self.assertFalse(list(VALIDATOR.iter_errors(document)))
        del document["records"][0]["matrix_asset_id"]
        self.assertTrue(list(VALIDATOR.iter_errors(document)))

    def test_non_reuse_registry_cannot_claim_schema_v11(self) -> None:
        document = synthetic_document("hypotheses")
        document["schema_version"] = "1.1"
        self.assertTrue(list(VALIDATOR.iter_errors(document)))


if __name__ == "__main__":
    unittest.main()
