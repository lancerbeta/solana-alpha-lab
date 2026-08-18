from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/validate_catalog.py"
spec = importlib.util.spec_from_file_location("validate_catalog", MODULE_PATH)
assert spec and spec.loader
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)


class CatalogImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = catalog.load_and_validate()

    def documents(self):
        return (
            copy.deepcopy(self.snapshot.manifest),
            copy.deepcopy(self.snapshot.assets_documents),
            copy.deepcopy(self.snapshot.queries_documents),
            copy.deepcopy(self.snapshot.lifecycle_documents),
        )

    def test_real_catalog_counts(self) -> None:
        checkpoint = self.snapshot.manifest["current_checkpoint"]
        self.assertEqual(
            catalog.observed_catalog_checkpoint(self.snapshot),
            checkpoint,
        )
        reuse = next(
            document for document in self.snapshot.lifecycle_documents
            if document["registry_type"] == "reuse_candidates"
        )
        self.assertEqual(len(reuse["records"]), 52)
        production_records = {
            document["registry_type"]: document["records"]
            for document in self.snapshot.lifecycle_documents
            if document["registry_type"] != "reuse_candidates"
        }
        self.assertEqual(
            [record["record_id"] for record in production_records["global_trial_ledger"]],
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
            [
                record["record_id"]
                for record in production_records["decisions_negative_results"]
            ],
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
        self.assertTrue(
            all(
                not records
                for registry_type, records in production_records.items()
                if registry_type
                not in {"global_trial_ledger", "decisions_negative_results"}
            )
        )

    def test_current_checkpoint_drift_fails_closed(self) -> None:
        snapshot = copy.deepcopy(self.snapshot)
        snapshot.manifest["current_checkpoint"]["assets"] += 1
        with self.assertRaisesRegex(
            catalog.CatalogValidationError,
            "catalog_current_checkpoint_drift",
        ):
            catalog.validate_current_checkpoint(snapshot)
        self.assertIn("ARCH-INTENT-001", self.snapshot.assets)

    def test_validated_ci_assets_and_query_contract(self) -> None:
        self.assertIn("CI-WORKFLOW-001", self.snapshot.assets)
        self.assertIn("CI-VALIDATOR-001", self.snapshot.assets)
        recipe = self.snapshot.queries["QUERY-CI-VALIDATE-001"]
        self.assertEqual(
            recipe["command"],
            [
                "uv",
                "run",
                "--locked",
                "--managed-python",
                "python",
                "-B",
                "scripts/validate_ci.py",
            ],
        )
        self.assertFalse(recipe["network_required"])
        self.assertEqual(recipe["write_effects"], "NONE")
        self.assertEqual(
            self.snapshot.manifest["deferred_capabilities"],
            ["GRAPH_DATABASE"],
        )
        for asset_id in ("CI-WORKFLOW-001", "CI-VALIDATOR-001"):
            asset = self.snapshot.assets[asset_id]
            self.assertEqual(len(asset["evidence"]), 1)
            self.assertEqual(asset["evidence"][0]["result"], "PASS")
            self.assertEqual(
                asset["evidence"][0]["reference"],
                "https://github.com/lancerbeta/solana-alpha-lab/actions/runs/29868825180",
            )

    def test_repository_catalog_and_registry_candidate_states_are_explicit(self) -> None:
        for asset_id in (
            "CTRL-AGENTS-001", "CTRL-PYPROJECT-001", "CTRL-UVLOCK-001",
            "CI-VALIDATOR-001", "CATALOG-ROOT-001",
            "CATALOG-ASSET-REGISTRY-CORE-001",
            "CATALOG-ASSET-REGISTRY-LIFECYCLE-001",
            "CATALOG-SCHEMA-LIFECYCLE-001",
            "REGISTRY-REUSE-CANDIDATES-001",
            "GENERATED-PROJECT-MAP-001", "GENERATED-EDGE-PROJECTION-001",
        ):
            self.assertEqual(
                self.snapshot.assets[asset_id]["status"],
                "IMPLEMENTED_UNVERIFIED",
            )
        self.assertEqual(
            self.snapshot.assets["CI-WORKFLOW-001"]["status"],
            "VALIDATED_ACTIVE",
        )
        self.assertEqual(
            self.snapshot.assets["ARCH-INTENT-001"]["status"],
            "ACCEPTED_DIRECTION_NOT_IMPLEMENTED",
        )

    def test_task04_mandatory_assets_are_registered(self) -> None:
        required = {
            "CTRL-TASK-04-001", "CTRL-HANDOFF-PROTOCOL-001",
            "ADR-MVP-STACK-002", "MATRIX-T04-MVP-STACK-001",
            "EVIDENCE-T04-RESEARCH-ACCEPTANCE-001",
            "PROTOTYPE-T04-CORE-NATIVE-STACK-001", "FIXTURE-T04-PIT-001",
            "EVIDENCE-T04-A4R-WORK-ACCEPTANCE-001",
            "SBOM-T04-CORE-STACK-001", "VALIDATOR-T04-ARCHITECTURE-001",
            "EVIDENCE-T04-A5A-CANDIDATE-001",
        }
        self.assertTrue(required.issubset(self.snapshot.assets))

    def test_task05_contract_and_task06_handoff_are_distinct(self) -> None:
        task = self.snapshot.assets["CTRL-TASK-05-001"]
        contract = self.snapshot.assets["CONTRACT-T05-DATA-001"]
        handoff = self.snapshot.assets["CTRL-LATEST-HANDOFF-001"]
        self.assertEqual(
            task["location"]["repository_path"],
            "docs/tasks/TASK-05.md",
        )
        self.assertEqual(
            contract["location"]["repository_path"],
            "docs/contracts/data_contract_v1.md",
        )
        self.assertEqual(handoff["truth_owner"], "TASK-06")
        self.assertEqual(
            {relation["target_asset_id"] for relation in handoff["relations"]},
            {
                "CTRL-TASK-06-001",
                "CONTRACT-T06-RAW-STORAGE-001",
                "CONTRACT-T06-DATASET-MANIFEST-001",
                "CONTRACT-T06-RAW-PARQUET-001",
                "CONTRACT-T06-STORAGE-BUDGET-001",
                "TEST-T06-CATALOG-001",
            },
        )

    def test_duplicate_across_registries_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        assets[1]["records"].append(copy.deepcopy(assets[0]["records"][0]))
        with self.assertRaisesRegex(catalog.CatalogValidationError, "duplicate_asset_ids"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_broken_relation_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        assets[1]["records"][0]["relations"].append({"relation_type":"depends_on","target_asset_id":"MISSING-ASSET-001"})
        with self.assertRaisesRegex(catalog.CatalogValidationError, "broken_asset_relation"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_missing_mandatory_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        assets[2]["records"] = []
        with self.assertRaisesRegex(catalog.CatalogValidationError, "catalog_gap_missing_mandatory"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_pre_git_available_before_bundle_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        target = next(r for d in assets for r in d["records"] if r["asset_id"] == "PRE-GIT-TASK02-ENV-REPORT-001")
        target["provenance"]["created_at"] = "2026-07-19"
        target["provenance"]["first_reliable_available_at"] = "2026-07-20"
        with self.assertRaisesRegex(catalog.CatalogValidationError, "pre_git_available_before_bundle"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_architecture_intent_cannot_claim_implemented(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        target = next(r for d in assets for r in d["records"] if r["asset_id"] == "ARCH-INTENT-001")
        target["status"] = "VALIDATED_ACTIVE"
        with self.assertRaisesRegex(catalog.CatalogValidationError, "architecture_intent_provenance_invalid"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_architecture_intent_implementation_requires_catalog_evidence(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        target = next(r for d in assets for r in d["records"] if r["asset_id"] == "ARCH-INTENT-004")
        target["relations"] = [
            relation
            for relation in target["relations"]
            if relation["relation_type"] != "evidenced_by"
        ]
        with self.assertRaisesRegex(catalog.CatalogValidationError, "architecture_intent_provenance_invalid"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_repository_origin_accepted_direction_intent_validates(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        target = next(r for d in assets for r in d["records"] if r["asset_id"] == "ARCH-INTENT-005")
        self.assertEqual(target["origin"], "REPOSITORY")
        self.assertEqual(target["status"], "ACCEPTED_DIRECTION_NOT_IMPLEMENTED")
        catalog.validate_semantics(manifest, assets, queries, lifecycle)
        target["origin"] = "PRE_GIT"
        with self.assertRaisesRegex(catalog.CatalogValidationError, "architecture_intent_provenance_invalid"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_external_bundle_requires_external_retention(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        target = next(r for d in assets for r in d["records"] if r["asset_id"] == "BUNDLE-TASK01-COMPLETION-001")
        target["provenance"]["retention"] = "TRACKED_REFERENCE"
        with self.assertRaisesRegex(catalog.CatalogValidationError, "external_bundle_provenance_invalid"):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_duplicate_lifecycle_record_ids_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        record = {
            "record_id": "SYNTHETIC-DUPLICATE-001",
            "evidence_asset_ids": [],
        }
        lifecycle[0]["records"] = [copy.deepcopy(record)]
        lifecycle[1]["records"] = [copy.deepcopy(record)]
        with self.assertRaisesRegex(
            catalog.CatalogValidationError,
            "duplicate_lifecycle_record_ids",
        ):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_broken_lifecycle_source_asset_rejected(self) -> None:
        manifest, assets, queries, lifecycle = self.documents()
        lifecycle[0]["source_asset_ids"] = ["MISSING-ASSET-001"]
        with self.assertRaisesRegex(
            catalog.CatalogValidationError,
            "broken_lifecycle_source_asset",
        ):
            catalog.validate_semantics(manifest, assets, queries, lifecycle)

    def test_import_query_readonly(self) -> None:
        recipe = self.snapshot.queries["QUERY-PRE-GIT-VERIFY-001"]
        self.assertTrue(recipe["read_only"])
        self.assertTrue(recipe["bounded"])
        self.assertEqual(recipe["write_effects"], "NONE")


if __name__ == "__main__": unittest.main()
