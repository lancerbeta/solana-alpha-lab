from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml

from scripts import query_hypothesis_research_memory as memory
from scripts import validate_catalog as catalog

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17"
    / "first_bounded_hypothesis_cycle_acceptance_v1.json"
)
MEMORY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17"
    / "first_bounded_hypothesis_cycle_v1.json"
)
QUERY_RECIPES_PATH = ROOT / "catalog" / "query_recipes.yaml"
PROJECT_MAP_PATH = ROOT / "docs" / "PROJECT_MAP.md"
EDGE_PROJECTION_PATH = (
    ROOT / "catalog" / "generated" / "asset_edges.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class Task17FirstBoundedHypothesisCycleAcceptanceTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.snapshot = catalog.load_and_validate()
        cls.query_recipes = yaml.safe_load(
            QUERY_RECIPES_PATH.read_text(encoding="utf-8")
        )

    def test_a2_artifact_fingerprints_are_exact(self) -> None:
        for artifact in self.receipt["accepted_artifacts"]:
            with self.subTest(path=artifact["path"]):
                self.assertEqual(
                    sha256(ROOT / artifact["path"]),
                    artifact["sha256"],
                )

    def test_memory_and_production_query_acceptance_are_reproducible(
        self,
    ) -> None:
        document, content_sha256 = memory.load_memory(MEMORY_PATH)
        memory.validate_memory(document)
        acceptance = self.receipt["deterministic_query_acceptance"]
        result = memory.query_prior_work(
            document,
            {
                "query_id": acceptance["query_id"],
                "as_of": acceptance["as_of"],
                "max_results": acceptance["max_results"],
                "predicates": acceptance["predicates"],
            },
            memory_content_sha256=content_sha256,
        )
        self.assertEqual(
            canonical_sha256(result),
            acceptance["canonical_result_sha256"],
        )
        self.assertEqual(
            [
                row["hypothesis_version_id"]
                for row in result["results"]
            ],
            acceptance["ordered_hypothesis_version_ids"],
        )
        self.assertEqual(result["results"][0]["current_state_as_of"], "PAUSED")
        self.assertEqual(result["results"][0]["trial_ids"], [])
        self.assertEqual(result["results"][0]["activation_epoch_ids"], [])
        self.assertTrue(
            result["results"][0][
                "repeat_or_extension_requires_what_changed"
            ]
        )
        self.assertFalse(result["automatic_reject_or_promotion"])

    def test_query_recipe_is_bounded_to_fixture_and_production_memory(
        self,
    ) -> None:
        recipes = {
            row["recipe_id"]: row
            for row in self.query_recipes["recipes"]
        }
        recipe = recipes["QUERY-T16-PRIOR-WORK-001"]
        acceptance = self.receipt["deterministic_query_acceptance"]
        self.assertEqual(recipe["record_version"], "2.0")
        self.assertTrue(recipe["read_only"])
        self.assertTrue(recipe["bounded"])
        self.assertFalse(recipe["network_required"])
        self.assertEqual(recipe["write_effects"], "NONE")

        parameters = {
            row["name"]: row["pattern"]
            for row in recipe["parameters"]
        }
        memory_pattern = re.compile(parameters["memory_path"])
        for allowed in self.receipt["production_memory_route"][
            "allowed_paths"
        ]:
            with self.subTest(allowed=allowed):
                self.assertIsNotNone(memory_pattern.fullmatch(allowed))
        for rejected in (
            "../first_bounded_hypothesis_cycle_v1.json",
            "docs/evidence/task17/other.json",
            "tests/fixtures/task16/other.json",
            "docs/evidence/task17/first_bounded_hypothesis_cycle_v1.json.tmp",
        ):
            with self.subTest(rejected=rejected):
                self.assertIsNone(memory_pattern.fullmatch(rejected))

        self.assertIsNotNone(
            re.fullmatch(
                parameters["query_id"],
                acceptance["query_id"],
            )
        )
        self.assertIn(
            "DATA-T17-HYPOTHESIS-RESEARCH-MEMORY-001",
            recipe["target_asset_ids"],
        )

    def test_catalog_checkpoint_and_task17_assets_are_exact(self) -> None:
        checkpoint = self.receipt["catalog_checkpoint"]
        self.assertEqual(
            catalog.observed_catalog_checkpoint(self.snapshot),
            {
                "assets": checkpoint["assets"],
                "asset_registries": checkpoint["asset_registries"],
                "schemas": checkpoint["schemas"],
                "queries": checkpoint["queries"],
                "lifecycle_registries": checkpoint[
                    "lifecycle_registries"
                ],
                "lifecycle_records": checkpoint["lifecycle_records"],
            },
        )
        self.assertEqual(
            self.snapshot.manifest["catalog_version"],
            checkpoint["catalog_version"],
        )
        self.assertEqual(
            set(checkpoint["registered_asset_ids"]),
            set(checkpoint["registered_asset_ids"])
            & set(self.snapshot.assets),
        )
        for asset_id in checkpoint["registered_asset_ids"]:
            with self.subTest(asset_id=asset_id):
                asset = self.snapshot.assets[asset_id]
                repository_path = asset["location"]["repository_path"]
                self.assertEqual(
                    sha256(ROOT / repository_path),
                    asset["integrity"]["sha256"],
                )

    def test_data_requirement_is_a_non_authorizing_decision_view(self) -> None:
        requirement = self.snapshot.assets[
            "DATA-REQUIREMENT-T17-EXECUTION-CAPACITY-001"
        ]
        evidence = self.snapshot.assets[
            "EVIDENCE-T17-FIRST-BOUNDED-HYPOTHESIS-CYCLE-001"
        ]
        self.assertEqual(requirement["asset_type"], "decision")
        self.assertEqual(
            requirement["location"],
            evidence["location"],
        )
        self.assertEqual(
            requirement["integrity"],
            evidence["integrity"],
        )
        decision = self.receipt["data_decision"]
        self.assertEqual(
            decision["verdict"],
            "LIVE_NON_RECONSTRUCTABLE_NEED",
        )
        self.assertEqual(decision["live_capture_authority"], "NOT_AUTHORIZED")
        self.assertEqual(
            decision["max_provider_calls_if_separately_authorized"],
            192,
        )
        self.assertEqual(decision["cash_cap_usd"], 0)

    def test_generated_navigation_exposes_task17_relations(self) -> None:
        project_map = PROJECT_MAP_PATH.read_text(encoding="utf-8")
        edges = json.loads(EDGE_PROJECTION_PATH.read_text(encoding="utf-8"))[
            "edges"
        ]
        for asset_id in self.receipt["catalog_checkpoint"][
            "registered_asset_ids"
        ]:
            with self.subTest(asset_id=asset_id):
                self.assertIn(f"| {asset_id} |", project_map)
        self.assertIn(
            {
                "source_asset_id":
                    "DATA-T17-HYPOTHESIS-RESEARCH-MEMORY-001",
                "relation": "derived_from",
                "target_asset_id": "EVIDENCE-T10-JUPITER-QUOTE-SUMMARY-002",
            },
            edges,
        )

    def test_authority_remains_zero(self) -> None:
        self.assertEqual(
            self.receipt["authority"],
            {
                "provider_api_rpc_wss_calls": 0,
                "cash_spend_usd": 0,
                "wallet_actions": 0,
                "signer_actions": 0,
                "transaction_actions": 0,
                "commit_actions": 0,
                "push_actions": 0,
                "pull_request_actions": 0,
                "merge_actions": 0,
            },
        )
        self.assertEqual(
            self.receipt["state_change"],
            "LOCAL_CANDIDATE_REQUIRES_REPOSITORY_DELIVERY",
        )
        self.assertEqual(
            self.receipt["next_atom"],
            "T17-A4_REPOSITORY_DELIVERY_V1",
        )


if __name__ == "__main__":
    unittest.main()
