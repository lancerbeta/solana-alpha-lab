from __future__ import annotations

import copy
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts import query_hypothesis_research_memory as memory
from solana_alpha_lab.factory.prior_work import (
    PriorWorkError,
    legacy_outcome_semantics,
    merge_plane_results,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task16"
    / "hypothesis_research_memory_v1.json"
)
SCRIPT_PATH = ROOT / "scripts" / "query_hypothesis_research_memory.py"
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

EXPECTED_FIXTURE_SHA256 = (
    "cce1829f0860e1553b89c4256b139b410151861af70796331459e041af396700"
)
EXPECTED_SCHEMA_SHA256 = (
    "92674d3aad07171534a614c7f89db01ab7ea7cda92feb24635fd4905fe359821"
)
EXPECTED_CONTRACT_SHA256 = (
    "fddf51222c710269c0b34cbc9ec48023e99de6d768fcf3c504e2fca5c5aa07d5"
)
EXPECTED_SCRIPT_SHA256 = (
    "19a4cbb370d5f054f785641953e07ab3d78bfcd942b69eacdfb469315d37eaf6"
)


def query(
    *,
    as_of: str = "2026-07-30T12:00:00Z",
    max_results: int = 20,
    **predicates: list[str],
) -> dict:
    return {
        "query_id": "PRIOR-WORK-QUERY-LIQUIDITY-001",
        "as_of": as_of,
        "max_results": max_results,
        "predicates": predicates,
    }


class Task16HypothesisResearchMemoryQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.document = json.loads(cls.fixture_bytes)
        cls.fixture_sha256 = hashlib.sha256(cls.fixture_bytes).hexdigest()

    def assert_validation_error(
        self,
        document: dict,
        marker: str,
    ) -> None:
        with self.assertRaisesRegex(memory.MemoryValidationError, marker):
            memory.validate_memory(document)

    def test_upstream_contract_and_fixture_fingerprints_are_exact(self) -> None:
        self.assertEqual(self.fixture_sha256, EXPECTED_FIXTURE_SHA256)
        self.assertEqual(
            hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(),
            EXPECTED_SCHEMA_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest(),
            EXPECTED_CONTRACT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(SCRIPT_PATH.read_bytes()).hexdigest(),
            EXPECTED_SCRIPT_SHA256,
        )

    def test_fixture_validates_and_reconstructs_append_only_chain(self) -> None:
        memory.validate_memory(self.document)
        self.assertEqual(len(self.document["hypothesis_families"]), 1)
        self.assertEqual(len(self.document["hypothesis_versions"]), 2)
        self.assertEqual(len(self.document["trials"]), 2)
        self.assertEqual(
            [row["outcome"] for row in self.document["trials"]],
            ["NEGATIVE", "POSITIVE"],
        )
        self.assertEqual(
            [
                row["decision_kind"]
                for row in self.document["decision_events"]
            ],
            ["PROMOTE", "MARK_DORMANT", "REACTIVATE"],
        )
        edge = self.document["derivation_edges"][0]
        self.assertEqual(
            edge["derivation_kind"],
            "REACTIVATION_REFORMULATION",
        )
        self.assertEqual(
            self.document["activation_epochs"][1][
                "previous_activation_epoch_id"
            ],
            self.document["activation_epochs"][0]["activation_epoch_id"],
        )

    def test_definition_hashes_reconcile_with_frozen_canonicalization(
        self,
    ) -> None:
        for version in self.document["hypothesis_versions"]:
            with self.subTest(version=version["hypothesis_version_id"]):
                self.assertEqual(
                    memory.canonical_definition_sha256(version),
                    version["definition_sha256"],
                )

    def test_pit_query_excludes_future_reformulation(self) -> None:
        result = memory.query_prior_work(
            self.document,
            query(
                as_of="2026-07-29T13:00:00Z",
                mechanism_terms=["liquidity"],
            ),
            memory_content_sha256=self.fixture_sha256,
        )
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(
            result["results"][0]["hypothesis_version_id"],
            "HYP-VERSION-LIQUIDITY-REVERSAL-V1",
        )
        self.assertEqual(
            result["results"][0]["current_state_as_of"],
            "DORMANT",
        )

    def test_final_query_returns_versions_in_deterministic_order(self) -> None:
        candidate = query(mechanism_terms=["liquidity"])
        first = memory.query_prior_work(
            self.document,
            candidate,
            memory_content_sha256=self.fixture_sha256,
        )
        second = memory.query_prior_work(
            self.document,
            candidate,
            memory_content_sha256=self.fixture_sha256,
        )
        self.assertEqual(first, second)
        self.assertEqual(
            [row["hypothesis_version_id"] for row in first["results"]],
            [
                "HYP-VERSION-LIQUIDITY-REVERSAL-V1",
                "HYP-VERSION-LIQUIDITY-REVERSAL-V2",
            ],
        )
        states = {
            row["hypothesis_version_id"]: row["current_state_as_of"]
            for row in first["results"]
        }
        self.assertEqual(
            states,
            {
                "HYP-VERSION-LIQUIDITY-REVERSAL-V1": "DORMANT",
                "HYP-VERSION-LIQUIDITY-REVERSAL-V2": "REACTIVATED",
            },
        )
        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )

    def test_dataset_and_tool_query_exposes_reuse(self) -> None:
        result = memory.query_prior_work(
            self.document,
            query(
                dataset_artifact_ids=[
                    "RESEARCH-ARTIFACT-LIQUIDITY-DATASET-001"
                ],
                tool_capability_ids=[
                    "TOOL-CAPABILITY-DUCKDB-PIT-001"
                ],
            ),
            memory_content_sha256=self.fixture_sha256,
        )
        self.assertEqual(result["result_count"], 2)
        for row in result["results"]:
            with self.subTest(version=row["hypothesis_version_id"]):
                self.assertIn("DATASET_ARTIFACT", row["matched_by"])
                self.assertIn("TOOL_CAPABILITY", row["matched_by"])
                self.assertIn(
                    "RESEARCH-ARTIFACT-LIQUIDITY-DATASET-001",
                    row["research_artifact_ids"],
                )
                self.assertTrue(row["artifact_content_sha256"])

    def test_negative_memory_and_derivation_evidence_are_retained(self) -> None:
        result = memory.query_prior_work(
            self.document,
            query(trial_outcomes=["NEGATIVE"]),
            memory_content_sha256=self.fixture_sha256,
        )
        self.assertEqual(result["result_count"], 1)
        row = result["results"][0]
        self.assertEqual(
            row["hypothesis_version_id"],
            "HYP-VERSION-LIQUIDITY-REVERSAL-V1",
        )
        self.assertEqual(row["trial_outcomes"], ["NEGATIVE"])
        self.assertEqual(
            row["derivation_edge_ids"],
            ["HYP-DERIVATION-LIQUIDITY-REACTIVATION-001"],
        )
        self.assertTrue(row["repeat_or_extension_requires_what_changed"])
        self.assertFalse(result["automatic_reject_or_promotion"])

    def test_query_bounds_and_predicates_fail_closed(self) -> None:
        invalid_queries = (
            query(max_results=0, mechanism_terms=["liquidity"]),
            query(max_results=51, mechanism_terms=["liquidity"]),
            query(as_of="2026-07-31T00:00:00Z", mechanism_terms=["x"]),
            query(),
            query(unknown_predicate=["x"]),
            query(trial_outcomes=["PASS"]),
            query(origin_kinds=["PERSUASIVE_AI"]),
            query(hypothesis_version_ids=["not-a-stable-id"]),
            query(
                as_of="2026-07-30T12:00:00",
                mechanism_terms=["liquidity"],
            ),
        )
        for candidate in invalid_queries:
            with self.subTest(candidate=candidate):
                with self.assertRaises(memory.MemoryValidationError):
                    memory.query_prior_work(self.document, candidate)

    def test_cross_plane_hash_conflict_fails_closed(self) -> None:
        legacy = {
            "results": [
                {
                    "hypothesis_version_id": (
                        "HYP-VERSION-LIQUIDITY-REVERSAL-V1"
                    ),
                    "definition_sha256": "a" * 64,
                    "score": 5,
                }
            ]
        }
        data_plane = {
            "results": [
                {
                    "hypothesis_version_id": (
                        "HYP-VERSION-LIQUIDITY-REVERSAL-V1"
                    ),
                    "definition_sha256": "b" * 64,
                    "score": 5,
                }
            ]
        }
        with self.assertRaisesRegex(
            PriorWorkError,
            "CROSS_PLANE_ID_CONFLICT",
        ):
            merge_plane_results(legacy, data_plane, max_results=20)

    def test_legacy_pass_and_fail_outcomes_remain_unresolved(self) -> None:
        for label in ("PASS", "FAIL"):
            with self.subTest(label=label):
                semantics = legacy_outcome_semantics(label)
                self.assertEqual(semantics["legacy_outcome"], label)
                self.assertIsNone(semantics["trial_outcome"])
                self.assertEqual(
                    semantics["diagnostic"],
                    "LEGACY_OUTCOME_UNRESOLVED",
                )

    def test_duplicate_and_missing_references_fail_closed(self) -> None:
        duplicate = copy.deepcopy(self.document)
        duplicate["hypothesis_origins"][1]["origin_id"] = duplicate[
            "hypothesis_origins"
        ][0]["origin_id"]
        self.assert_validation_error(duplicate, "duplicate_record_id")

        missing = copy.deepcopy(self.document)
        missing["trials"][0]["dataset_artifact_ids"] = [
            "RESEARCH-ARTIFACT-MISSING-001"
        ]
        self.assert_validation_error(missing, "missing_reference")

    def test_cross_record_backreferences_fail_closed(self) -> None:
        origin = copy.deepcopy(self.document)
        origin["hypothesis_origins"][0]["hypothesis_version_id"] = (
            "HYP-VERSION-LIQUIDITY-REVERSAL-V2"
        )
        self.assert_validation_error(
            origin,
            "hypothesis_origin_backreference_mismatch",
        )

        cycle = copy.deepcopy(self.document)
        cycle["trials"][0]["research_cycle_id"] = (
            "RESEARCH-CYCLE-LIQUIDITY-REVERSAL-002"
        )
        self.assert_validation_error(
            cycle,
            "trial_hypothesis_cycle_mismatch",
        )

        epoch = copy.deepcopy(self.document)
        epoch["activation_epochs"][0][
            "activation_basis_decision_event_id"
        ] = "DECISION-EVENT-LIQUIDITY-REACTIVATE-001"
        self.assert_validation_error(
            epoch,
            "epoch_basis_hypothesis_mismatch",
        )

    def test_loader_rejects_duplicate_keys_nonfinite_and_outside_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            outside = temporary_path / "memory.json"
            outside.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(
                memory.MemoryValidationError,
                "memory_path_outside_repository",
            ):
                memory.load_memory(outside)

        duplicate = (
            ROOT
            / "tests"
            / "fixtures"
            / "task16"
            / "_temporary_duplicate_key.json"
        )
        try:
            duplicate.write_text(
                '{"schema_version":"1.0","schema_version":"1.0"}\n',
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                memory.MemoryValidationError,
                "memory_json_duplicate_key",
            ):
                memory.load_memory(duplicate)
            duplicate.write_text(
                '{"value":NaN}\n',
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                memory.MemoryValidationError,
                "memory_json_nonfinite_number",
            ):
                memory.load_memory(duplicate)
        finally:
            duplicate.unlink(missing_ok=True)

    def test_definition_and_trial_pit_drift_fail_closed(self) -> None:
        definition = copy.deepcopy(self.document)
        definition["hypothesis_versions"][0]["mechanism"] += " changed"
        self.assert_validation_error(
            definition,
            "hypothesis_definition_sha256_mismatch",
        )

        budget = copy.deepcopy(self.document)
        budget["trials"][0]["search_budget"]["executed_variants"] = 4
        self.assert_validation_error(budget, "trial_search_budget_exceeded")

        future_artifact = copy.deepcopy(self.document)
        artifact = next(
            row
            for row in future_artifact["research_artifacts"]
            if row["research_artifact_id"]
            == "RESEARCH-ARTIFACT-LIQUIDITY-DATASET-001"
        )
        artifact["first_reliable_available_at"] = (
            "2026-07-29T10:00:00Z"
        )
        self.assert_validation_error(
            future_artifact,
            "trial_prerequisite_artifact_after_cutoff",
        )

    def test_derivation_cycle_and_invalid_reactivation_fail_closed(self) -> None:
        cycle = copy.deepcopy(self.document)
        reverse = copy.deepcopy(cycle["derivation_edges"][0])
        reverse["derivation_edge_id"] = (
            "HYP-DERIVATION-LIQUIDITY-CYCLE-001"
        )
        reverse["parent_hypothesis_version_ids"] = [
            "HYP-VERSION-LIQUIDITY-REVERSAL-V2"
        ]
        reverse["child_hypothesis_version_id"] = (
            "HYP-VERSION-LIQUIDITY-REVERSAL-V1"
        )
        cycle["derivation_edges"].append(reverse)
        self.assert_validation_error(cycle, "derivation_cycle")

        reactivation = copy.deepcopy(self.document)
        reactivation["decision_events"] = [
            row
            for row in reactivation["decision_events"]
            if row["decision_kind"] != "MARK_DORMANT"
        ]
        self.assert_validation_error(
            reactivation,
            "reactivation_without_prior_pause_or_dormancy",
        )

    def test_artifacts_are_local_sanitized_and_network_free(self) -> None:
        paths = (FIXTURE_PATH, SCRIPT_PATH, Path(__file__))
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
        script = SCRIPT_PATH.read_text(encoding="utf-8").lower()
        for prohibited in (
            "import requests",
            "import httpx",
            "import websocket",
            "urllib.request",
            "subprocess",
        ):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, script)


if __name__ == "__main__":
    unittest.main()
