from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task19"
    / "point_in_time_replay_v1.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task19"
    / "acceptance_catalog_factory_fit_v1.json"
)

EXPECTED_IDS = {
    "CONTRACT-T19-POINT-IN-TIME-REPLAY-001",
    "FIXTURE-T19-POINT-IN-TIME-REPLAY-001",
    "TEST-T19-POINT-IN-TIME-REPLAY-CONTRACT-001",
    "MODULE-T19-POINT-IN-TIME-REPLAY-001",
    "SCRIPT-T19-POINT-IN-TIME-REPLAY-001",
    "EVIDENCE-T19-POINT-IN-TIME-REPLAY-001",
    "EVIDENCE-T19-POINT-IN-TIME-REPLAY-SUMMARY-001",
    "TEST-T19-POINT-IN-TIME-REPLAY-001",
    "EVIDENCE-T19-ACCEPTANCE-CATALOG-FACTORY-FIT-001",
    "TEST-T19-ACCEPTANCE-CATALOG-FACTORY-FIT-001",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog() -> tuple[dict, dict[str, dict]]:
    manifest = yaml.safe_load(
        (ROOT / "catalog" / "catalog_manifest.yaml").read_text(
            encoding="utf-8"
        )
    )
    documents = [
        yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
        for relative in manifest["root_resolver"]["asset_registries"]
    ]
    records = {
        record["asset_id"]: record
        for document in documents
        for record in document["records"]
    }
    return manifest, records


class Task19AcceptanceCatalogFactoryFitTests(unittest.TestCase):
    def test_catalog_transaction_is_exact_and_hash_bound(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        manifest, records = catalog()
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            set(receipt["catalog"]["registered_asset_ids"]),
            EXPECTED_IDS,
        )
        historical = receipt["catalog"]
        self.assertEqual(historical["catalog_version"], "0.24.0")
        self.assertEqual(historical["assets"], 331)
        self.assertGreaterEqual(
            tuple(map(int, manifest["catalog_version"].split("."))),
            tuple(map(int, historical["catalog_version"].split("."))),
        )
        checkpoint = manifest["current_checkpoint"]
        self.assertGreaterEqual(checkpoint["assets"], historical["assets"])
        for field in ("asset_registries", "schemas", "queries"):
            with self.subTest(field=field):
                self.assertEqual(checkpoint[field], historical[field])
        self.assertEqual(
            len(records),
            checkpoint["assets"],
        )
        self.assertTrue(EXPECTED_IDS.issubset(records))
        for asset_id in EXPECTED_IDS:
            with self.subTest(asset_id=asset_id):
                record = records[asset_id]
                self.assertEqual(record["location"]["kind"], "git_path")
                relative = record["location"]["repository_path"]
                self.assertEqual(
                    sha256(ROOT / relative),
                    record["integrity"]["sha256"],
                )

    def test_replay_lineage_and_bounded_claims_reconcile(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        replay = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
        accepted = receipt["accepted_result"]
        self.assertEqual(sha256(REPLAY_PATH), accepted["a3_receipt_sha256"])
        self.assertEqual(replay["verdict"], "REPLAY_SAFE")
        self.assertEqual(
            replay["replay_output_sha256"],
            accepted["replay_output_sha256"],
        )
        self.assertEqual(
            replay["lineage_projection_sha256"],
            accepted["lineage_projection_sha256"],
        )
        self.assertEqual(len(replay["lineage_projection"]["attempts"]), 32)
        self.assertEqual(
            (accepted["accepted_rows"], accepted["excluded_retained_rows"]),
            (24, 8),
        )
        self.assertFalse(accepted["promotion_authorized"])
        self.assertIn("NOT_NET_RETURN", receipt["nonclaims"])
        self.assertIn("NOT_ALPHA", receipt["nonclaims"])
        self.assertIn("NOT_TASK20_COLLECTION_AUTHORITY", receipt["nonclaims"])

    def test_full_factory_fit_passes_after_bounded_lineage_repair(
        self,
    ) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        critic = receipt["factory_fit"]
        self.assertEqual(critic["mode"], "FULL_REVIEW")
        self.assertEqual(critic["verdict"], "PASS")
        self.assertFalse(critic["bounded_correction"]["scope_change"])
        self.assertFalse(critic["bounded_correction"]["estimand_change"])
        self.assertEqual(critic["bounded_correction"]["validation"], "PASS")
        self.assertTrue(
            all(
                row["status"] in {"PASS", "NOT_APPLICABLE"}
                for row in critic["checks"]
            )
        )
        self.assertEqual(
            critic["previous_durable_followup"],
            {
                "followup_id": (
                    "TASK20_FUTURE_COLLECTION_BACKUP_RESTORE_AUTOMATION_POLICY"
                ),
                "status": "ROUTED_UNCHANGED",
                "owner": "TASK-20",
                "activation_trigger": "BEFORE_ANY_FORWARD_COLLECTION",
                "reason": (
                    "TASK-19 replays one immutable snapshot and does not "
                    "widen future collection durability."
                ),
            },
        )
        self.assertEqual(critic["new_followup"], "NONE")

    def test_generated_navigation_and_authority_are_bounded(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        project_map = (ROOT / "docs" / "PROJECT_MAP.md").read_text(
            encoding="utf-8"
        )
        edges = json.loads(
            (
                ROOT / "catalog" / "generated" / "asset_edges.json"
            ).read_text(encoding="utf-8")
        )
        edge_ids = {edge["source_asset_id"] for edge in edges["edges"]}
        self.assertTrue(EXPECTED_IDS.issubset(edge_ids))
        for asset_id in EXPECTED_IDS:
            self.assertIn(asset_id, project_map)
        authority = receipt["authority"]
        self.assertTrue(authority["local_write_only"])
        for field, value in authority.items():
            if field != "local_write_only":
                with self.subTest(field=field):
                    self.assertIn(value, (0, False))
        self.assertEqual(
            receipt["next_gate"],
            {
                "atom_id": "T19-A5_REPOSITORY_DELIVERY_V1",
                "authority": (
                    "COMMIT_AND_NON_FORCE_TASK_BRANCH_PUSH_DRAFT_PR_CI"
                ),
                "authorized_by_t19_a4": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
