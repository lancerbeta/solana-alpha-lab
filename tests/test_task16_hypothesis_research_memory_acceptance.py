from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml

from scripts import query_hypothesis_research_memory as memory

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task16"
    / "hypothesis_research_memory_acceptance_v1.json"
)
MEMORY_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task16"
    / "hypothesis_research_memory_v1.json"
)
MANIFEST_PATH = ROOT / "catalog" / "catalog_manifest.yaml"
ASSET_REGISTRY_PATH = ROOT / "catalog" / "assets" / "core.yaml"
QUERY_REGISTRY_PATH = ROOT / "catalog" / "query_recipes.yaml"
PROJECT_MAP_PATH = ROOT / "docs" / "PROJECT_MAP.md"
EDGE_PROJECTION_PATH = (
    ROOT / "catalog" / "generated" / "asset_edges.json"
)

EXPECTED_RECEIPT_SHA256 = (
    "b3d8af79086562aa756b6d57e55aac4ee37384f96ae277ff969ccea13970722a"
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


class Task16HypothesisResearchMemoryAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.manifest = yaml.safe_load(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )
        cls.asset_registry = yaml.safe_load(
            ASSET_REGISTRY_PATH.read_text(encoding="utf-8")
        )
        cls.query_registry = yaml.safe_load(
            QUERY_REGISTRY_PATH.read_text(encoding="utf-8")
        )

    def test_acceptance_receipt_and_upstream_artifacts_are_exact(self) -> None:
        self.assertEqual(sha256(RECEIPT_PATH), EXPECTED_RECEIPT_SHA256)
        for artifact in self.receipt["accepted_artifacts"]:
            with self.subTest(path=artifact["path"]):
                self.assertEqual(
                    sha256(ROOT / artifact["path"]),
                    artifact["sha256"],
                )

    def test_legacy_sources_are_preserved_empty_without_synthetic_history(
        self,
    ) -> None:
        migration = self.receipt["migration"]
        self.assertEqual(
            migration["mode"],
            "FORWARD_ONLY_NO_HISTORICAL_REWRITE",
        )
        self.assertEqual(
            migration["disposition"],
            "PRESERVED_AS_V1_EMPTY_NO_SYNTHETIC_HISTORY",
        )
        self.assertEqual(migration["source_records_total"], 0)
        self.assertEqual(migration["created_records_from_legacy"], 0)
        self.assertFalse(migration["synthetic_history_created"])
        self.assertFalse(migration["historical_receipts_rewritten"])
        for source in migration["sources"]:
            with self.subTest(path=source["path"]):
                path = ROOT / source["path"]
                document = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertEqual(document["schema_version"], "1.0")
                self.assertEqual(source["records"], 0)
                if source["path"] == "registries/global_trial_ledger.yaml":
                    records = document["records"]
                    self.assertTrue(
                        all(
                            record["record_kind"] == "trial"
                            and record["status"] == "RECORDED"
                            and record["created_at"] > "2026-07-29T00:00:00Z"
                            for record in records
                        )
                    )
                elif source["path"] == "registries/decisions_negative_results.yaml":
                    records = document["records"]
                    self.assertTrue(
                        all(
                            record["record_kind"] in {"decision", "negative_result"}
                            and record["status"] == "RECORDED"
                            and record["created_at"] > "2026-07-29T00:00:00Z"
                            and bool(record["evidence_asset_ids"])
                            for record in records
                        )
                    )
                else:
                    self.assertEqual(sha256(path), source["sha256"])
                    self.assertEqual(document["records"], [])

    def test_bounded_query_reproduces_evidence_bearing_result(self) -> None:
        document, content_sha256 = memory.load_memory(MEMORY_PATH)
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
            [row["hypothesis_version_id"] for row in result["results"]],
            acceptance["ordered_hypothesis_version_ids"],
        )
        self.assertEqual(
            {
                row["hypothesis_version_id"]: row["current_state_as_of"]
                for row in result["results"]
            },
            acceptance["current_states"],
        )
        self.assertEqual(
            {
                row["hypothesis_version_id"]: row["trial_outcomes"]
                for row in result["results"]
            },
            acceptance["trial_outcomes"],
        )
        self.assertEqual(result["result_count"], acceptance["result_count"])
        self.assertFalse(result["automatic_reject_or_promotion"])

    def test_catalog_checkpoint_is_preserved_as_a_minimum(self) -> None:
        expected = self.receipt["catalog_checkpoint"]
        self.assertGreaterEqual(
            tuple(
                int(part)
                for part in self.manifest["catalog_version"].split(".")
            ),
            tuple(
                int(part)
                for part in expected["catalog_version"].split(".")
            ),
        )
        checkpoint = self.manifest["current_checkpoint"]
        self.assertGreaterEqual(checkpoint["assets"], expected["assets"])
        self.assertEqual(
            checkpoint["asset_registries"],
            expected["asset_registries"],
        )
        self.assertGreaterEqual(checkpoint["schemas"], expected["schemas"])
        self.assertGreaterEqual(checkpoint["queries"], expected["queries"])
        self.assertEqual(
            checkpoint["lifecycle_registries"],
            expected["lifecycle_registries"],
        )
        self.assertGreaterEqual(
            checkpoint["lifecycle_records"],
            expected["lifecycle_records"],
        )
        assets = {
            record["asset_id"]: record
            for record in self.asset_registry["records"]
        }
        self.assertTrue(
            set(expected["registered_asset_ids"]).issubset(assets)
        )
        self.assertTrue(
            set(expected["registered_asset_ids"]).issubset(
                self.manifest["mandatory_asset_ids"]
            )
        )
        recipes = {
            recipe["recipe_id"]: recipe
            for recipe in self.query_registry["recipes"]
        }
        self.assertEqual(
            set(expected["registered_query_recipe_ids"]),
            set(recipes) & set(expected["registered_query_recipe_ids"]),
        )
        recipe = recipes["QUERY-T16-PRIOR-WORK-001"]
        self.assertTrue(recipe["read_only"])
        self.assertTrue(recipe["bounded"])
        self.assertFalse(recipe["network_required"])
        self.assertEqual(recipe["write_effects"], "NONE")
        self.assertLessEqual(recipe["output_contract"]["max_records"], 50)

    def test_generated_navigation_exposes_task16_assets_and_query(
        self,
    ) -> None:
        project_map = PROJECT_MAP_PATH.read_text(encoding="utf-8")
        for asset_id in self.receipt["catalog_checkpoint"][
            "registered_asset_ids"
        ]:
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, project_map)
        edge_projection = json.loads(
            EDGE_PROJECTION_PATH.read_text(encoding="utf-8")
        )
        edge_sources = {
            edge["source_asset_id"]
            for edge in edge_projection["edges"]
        }
        self.assertIn(
            "CONTRACT-T16-HYPOTHESIS-LIFECYCLE-RESEARCH-MEMORY-001",
            edge_sources,
        )

    def test_authority_and_repository_hygiene_are_zero(self) -> None:
        self.assertEqual(
            self.receipt["authority"],
            {
                "provider_api_rpc_calls": 0,
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
        paths = (
            RECEIPT_PATH,
            Path(__file__),
            MEMORY_PATH,
            ROOT / "scripts" / "query_hypothesis_research_memory.py",
        )
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


if __name__ == "__main__":
    unittest.main()
