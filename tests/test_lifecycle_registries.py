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


class LifecycleRegistryTests(unittest.TestCase):
    def test_all_production_registries_are_valid_and_empty(self) -> None:
        for registry_type in REGISTRIES:
            with self.subTest(registry_type=registry_type):
                document = production_document(registry_type)
                self.assertFalse(list(VALIDATOR.iter_errors(document)))
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
        self.assertEqual(document["source_asset_ids"], ["PRE-GIT-TASK01-A024"])
        self.assertEqual(document["records"], [])


if __name__ == "__main__":
    unittest.main()
