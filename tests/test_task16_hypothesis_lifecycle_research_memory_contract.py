from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "hypothesis_lifecycle_research_memory.schema.json"
)
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "hypothesis_lifecycle_research_memory_contract_v1.md"
)

EXPECTED_MANAGED_FILES = [
    "docs/contracts/hypothesis_lifecycle_research_memory.schema.json",
    "docs/contracts/hypothesis_lifecycle_research_memory_contract_v1.md",
    "tests/test_task16_hypothesis_lifecycle_research_memory_contract.py",
]
EXPECTED_SCHEMA_SHA256 = (
    "92674d3aad07171534a614c7f89db01ab7ea7cda92feb24635fd4905fe359821"
)
EXPECTED_CONTRACT_SHA256 = (
    "fddf51222c710269c0b34cbc9ec48023e99de6d768fcf3c504e2fca5c5aa07d5"
)


def minimal_document() -> dict:
    timestamp = "2026-07-29T12:00:00Z"
    hypothesis_version_id = "HYP-VERSION-BOUNDED-LIQUIDITY-V1"
    research_cycle_id = "RESEARCH-CYCLE-BOUNDED-LIQUIDITY-001"
    artifact_id = "RESEARCH-ARTIFACT-BOUNDED-LIQUIDITY-001"
    trial_id = "TRIAL-BOUNDED-LIQUIDITY-001"
    decision_event_id = "DECISION-EVENT-BOUNDED-LIQUIDITY-001"
    return {
        "schema_version": "1.0",
        "memory_id": "SMIAL-HYPOTHESIS-RESEARCH-MEMORY",
        "as_of": timestamp,
        "truth_owner": "TASK-16",
        "append_only": True,
        "history_rewrite_policy": (
            "CORRECT_WITH_NEW_RECORD_AND_SUPERSEDES_LINK"
        ),
        "current_state_is_projection": True,
        "hypothesis_families": [
            {
                "family_id": "HYP-FAMILY-BOUNDED-LIQUIDITY",
                "title": "Bounded liquidity response",
                "mechanism_class": "temporary liquidity imbalance",
                "created_at": timestamp,
                "first_reliable_available_at": timestamp,
                "record_owner": "TASK-16",
                "evidence_asset_ids": ["ARCH-INTENT-002"],
            }
        ],
        "hypothesis_origins": [
            {
                "origin_id": "HYP-ORIGIN-BOUNDED-LIQUIDITY-001",
                "hypothesis_version_id": hypothesis_version_id,
                "origin_kind": "OWNER_OBSERVATION",
                "originator": "owner",
                "observed_at": timestamp,
                "recorded_at": timestamp,
                "first_reliable_available_at": timestamp,
                "initial_observation": (
                    "Short-lived liquidity changes may alter bounded returns."
                ),
                "source_reference_asset_ids": ["ARCH-INTENT-002"],
                "artifact_ids": [artifact_id],
                "record_owner": "TASK-16",
            }
        ],
        "research_cycles": [
            {
                "research_cycle_id": research_cycle_id,
                "question": "Does the named liquidity condition alter return?",
                "estimand": "Net return difference versus explicit controls.",
                "population_and_controls": (
                    "Named candidates and a point-in-time control cohort."
                ),
                "available_data_asset_ids": ["ARCH-INTENT-002"],
                "required_output": "One bounded decision memo.",
                "error_cost": "False promotion costs later research capacity.",
                "time_cap_minutes": 60,
                "cash_cap_usd": 0,
                "privacy_boundary": "Repository evidence without raw chat.",
                "validation_owner": "TASK-16",
                "opened_at": timestamp,
                "first_reliable_available_at": timestamp,
                "hypothesis_version_ids": [hypothesis_version_id],
                "record_owner": "TASK-16",
            }
        ],
        "hypothesis_versions": [
            {
                "hypothesis_version_id": hypothesis_version_id,
                "family_id": "HYP-FAMILY-BOUNDED-LIQUIDITY",
                "version_ordinal": 1,
                "research_cycle_id": research_cycle_id,
                "origin_id": "HYP-ORIGIN-BOUNDED-LIQUIDITY-001",
                "definition_state": "FROZEN",
                "statement": (
                    "The named liquidity condition changes bounded net return."
                ),
                "mechanism": (
                    "Temporary imbalance changes executable price impact."
                ),
                "falsifier": (
                    "No robust net-of-cost difference versus controls."
                ),
                "expected_regime_terms": ["temporary-liquidity-imbalance"],
                "feature_definition_asset_ids": ["FEATURE-T05-EXAMPLE-001"],
                "label_definition_asset_ids": ["LABEL-T16-NET-RETURN-001"],
                "named_consumer_ids": ["TASK-17"],
                "created_at": timestamp,
                "first_reliable_available_at": timestamp,
                "definition_sha256": (
                    "54cc82d77842f6130f5b7aec1826417b0"
                    "cd114adb4209d315359d27abe313138"
                ),
                "evidence_asset_ids": ["ARCH-INTENT-002"],
                "record_owner": "TASK-16",
            }
        ],
        "research_artifacts": [
            {
                "research_artifact_id": artifact_id,
                "hypothesis_version_ids": [hypothesis_version_id],
                "artifact_kind": "REPORT",
                "logical_uri": "evidence://task16/bounded-liquidity-report",
                "content_sha256": "2" * 64,
                "created_at": timestamp,
                "first_reliable_available_at": timestamp,
                "tool_name": "offline-test",
                "tool_version": "1.0",
                "contains_sensitive_raw_conversation": False,
                "record_owner": "TASK-16",
            }
        ],
        "trials": [
            {
                "trial_id": trial_id,
                "hypothesis_version_id": hypothesis_version_id,
                "research_cycle_id": research_cycle_id,
                "trial_kind": "RETROSPECTIVE",
                "estimand": "Net return difference versus controls.",
                "population_artifact_id": artifact_id,
                "control_artifact_ids": [artifact_id],
                "dataset_artifact_ids": [artifact_id],
                "method_artifact_ids": [artifact_id],
                "result_artifact_ids": [artifact_id],
                "dataset_as_of": timestamp,
                "availability_cutoff": timestamp,
                "split_id": "SPLIT-BOUNDED-LIQUIDITY-001",
                "holdout_consumption_ids": [],
                "search_budget": {
                    "planned_variants": 1,
                    "executed_variants": 1,
                    "holdout_looks": 0,
                },
                "cost_assumptions_artifact_id": artifact_id,
                "outcome": "INCONCLUSIVE",
                "conclusion": "The bounded evidence is insufficient.",
                "limitation_codes": ["SMALL_SAMPLE"],
                "completed_at": timestamp,
                "first_reliable_available_at": timestamp,
                "evidence_asset_ids": ["ARCH-INTENT-002"],
                "record_owner": "TASK-16",
            }
        ],
        "decision_events": [
            {
                "decision_event_id": decision_event_id,
                "hypothesis_version_id": hypothesis_version_id,
                "decision_kind": "PROMOTE",
                "rationale": "Open one bounded research epoch.",
                "decision_owner": "owner",
                "decided_at": timestamp,
                "effective_at": timestamp,
                "first_reliable_available_at": timestamp,
                "trial_ids": [trial_id],
                "next_condition": "Reassess after the bounded research epoch.",
                "evidence_asset_ids": ["ARCH-INTENT-002"],
                "record_owner": "TASK-16",
            }
        ],
        "derivation_edges": [],
        "activation_epochs": [
            {
                "activation_epoch_id": (
                    "ACTIVATION-EPOCH-BOUNDED-LIQUIDITY-001"
                ),
                "hypothesis_version_id": hypothesis_version_id,
                "epoch_ordinal": 1,
                "mode": "RESEARCH",
                "opened_at": timestamp,
                "first_reliable_available_at": timestamp,
                "activation_basis_decision_event_id": decision_event_id,
                "regime_evidence_asset_ids": ["ARCH-INTENT-002"],
                "authority_receipt_asset_ids": [],
                "record_owner": "TASK-16",
            }
        ],
    }


class Task16HypothesisLifecycleResearchMemoryContractTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema_bytes = SCHEMA_PATH.read_bytes()
        cls.schema = json.loads(cls.schema_bytes)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)
        cls.contract_bytes = CONTRACT_PATH.read_bytes()
        cls.contract = cls.contract_bytes.decode("utf-8")

    def assert_invalid(self, document: dict) -> None:
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_schema_identity_and_minimal_document(self) -> None:
        self.assertEqual(
            self.schema["$id"],
            (
                "repo://docs/contracts/"
                "hypothesis_lifecycle_research_memory.schema.json"
            ),
        )
        self.assertEqual(
            self.schema["properties"]["schema_version"]["const"],
            "1.0",
        )
        self.assertFalse(
            list(self.validator.iter_errors(minimal_document()))
        )

    def test_root_is_append_only_and_state_is_projection(self) -> None:
        for key, value in (
            ("append_only", False),
            ("current_state_is_projection", False),
            ("history_rewrite_policy", "MUTATE_IN_PLACE"),
        ):
            with self.subTest(key=key):
                document = minimal_document()
                document[key] = value
                self.assert_invalid(document)

    def test_hypothesis_definition_is_frozen_and_requires_falsifier(self) -> None:
        document = minimal_document()
        document["hypothesis_versions"][0]["definition_state"] = "DRAFT"
        self.assert_invalid(document)

        document = minimal_document()
        del document["hypothesis_versions"][0]["falsifier"]
        self.assert_invalid(document)

        document = minimal_document()
        document["hypothesis_versions"][0]["mutable_status"] = "ACTIVE"
        self.assert_invalid(document)

    def test_definition_hash_has_frozen_canonicalization(self) -> None:
        hypothesis = minimal_document()["hypothesis_versions"][0]
        fields = (
            "family_id",
            "version_ordinal",
            "research_cycle_id",
            "origin_id",
            "statement",
            "mechanism",
            "falsifier",
            "expected_regime_terms",
            "feature_definition_asset_ids",
            "label_definition_asset_ids",
            "named_consumer_ids",
        )
        payload = {
            key: (
                sorted(hypothesis[key])
                if isinstance(hypothesis[key], list)
                else hypothesis[key]
            )
            for key in fields
        }
        candidate = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        self.assertEqual(
            hashlib.sha256(candidate).hexdigest(),
            hypothesis["definition_sha256"],
        )

    def test_trial_outcome_is_completed_and_typed(self) -> None:
        for prohibited in ("PENDING", "PASS", "FAIL"):
            with self.subTest(outcome=prohibited):
                document = minimal_document()
                document["trials"][0]["outcome"] = prohibited
                self.assert_invalid(document)

        for accepted in (
            "POSITIVE",
            "NEGATIVE",
            "INCONCLUSIVE",
            "INVALID",
        ):
            with self.subTest(outcome=accepted):
                document = minimal_document()
                document["trials"][0]["outcome"] = accepted
                self.assertFalse(
                    list(self.validator.iter_errors(document))
                )

    def test_trial_requires_reproducible_inputs_and_outputs(self) -> None:
        for field in (
            "control_artifact_ids",
            "dataset_artifact_ids",
            "method_artifact_ids",
            "result_artifact_ids",
        ):
            with self.subTest(field=field):
                document = minimal_document()
                document["trials"][0][field] = []
                self.assert_invalid(document)

    def test_raw_conversation_is_rejected(self) -> None:
        document = minimal_document()
        document["research_artifacts"][0][
            "contains_sensitive_raw_conversation"
        ] = True
        self.assert_invalid(document)

    def test_live_epoch_requires_explicit_authority_evidence(self) -> None:
        document = minimal_document()
        document["activation_epochs"][0]["mode"] = "LIVE"
        self.assert_invalid(document)

        document["activation_epochs"][0]["authority_receipt_asset_ids"] = [
            "EVIDENCE-FUTURE-LIVE-AUTHORITY-001"
        ]
        self.assertFalse(list(self.validator.iter_errors(document)))

    def test_contract_freezes_query_migration_and_non_authority(self) -> None:
        for marker in (
            "CONTRACT-T16-HYPOTHESIS-LIFECYCLE-RESEARCH-MEMORY-001",
            "current_state_is_projection = true",
            "Object keys are lexicographically sorted",
            "decision_event_id)` order",
            "POSITIVE",
            "NEGATIVE",
            "INCONCLUSIVE",
            "INVALID",
            "first_reliable_available_at > as_of",
            "what_changed",
            "Existing bytes and historical receipts are not rewritten.",
            "Similarity is advisory.",
            "T16-A4_DETERMINISTIC_PRIOR_WORK_QUERY_AND_FIXTURE_V1",
            "provider/API/RPC/WSS",
            "wallet, signer, transaction or real-money action",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)

    def test_contract_artifacts_are_sanitized_and_repository_clean(self) -> None:
        paths = [ROOT / path for path in EXPECTED_MANAGED_FILES]
        for path in paths:
            with self.subTest(path=path.name):
                candidate = path.read_bytes()
                self.assertFalse(candidate.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", candidate)
                self.assertTrue(candidate.endswith(b"\n"))
                text = candidate.decode("utf-8")
                self.assertTrue(
                    all(
                        line.rstrip(" \t") == line
                        for line in text.splitlines()
                    )
                )
                self.assertIsNone(re.search(r"(?i)\b[a-z]:[\\/]", text))
                self.assertIsNone(
                    re.search(
                        r"(?i)\b(?:api[_-]?key|access[_-]?token|password)"
                        r"\s*[:=]\s*[\"'][^\"']+[\"']",
                        text,
                    )
                )

    def test_contract_fingerprints_are_frozen(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.schema_bytes).hexdigest(),
            EXPECTED_SCHEMA_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(self.contract_bytes).hexdigest(),
            EXPECTED_CONTRACT_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
