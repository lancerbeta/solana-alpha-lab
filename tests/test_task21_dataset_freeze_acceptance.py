from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_dataset_freeze_acceptance import (
    build_artifact_index,
    build_dataset_freeze_manifest,
    build_effective_sample_summary,
    load_yaml,
    validate_frozen_inputs,
    verify_hash_bindings,
)
from solana_alpha_lab.task21_forward_recovery import (
    canonical_json_bytes,
    sha256_bytes,
)


PLAN_PATH = ROOT / "configs/task21_dataset_freeze_acceptance_v1.yaml"
FREEZE_PATH = ROOT / "docs/evidence/task21/final_dataset_freeze_manifest_v1.json"
SAMPLE_PATH = ROOT / "docs/evidence/task21/effective_sample_summary_v1.json"
INDEX_PATH = ROOT / "docs/evidence/task21/task21_artifact_index_v1.json"
RECEIPT_PATH = ROOT / "docs/evidence/task21/a7_acceptance_catalog_factory_fit_v1.json"
RECOVERY_CONFIG_PATH = ROOT / "configs/task21_final_dataset_recovery_v1.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def load_catalog() -> tuple[dict, dict[str, dict]]:
    manifest = yaml.safe_load((ROOT / "catalog/catalog_manifest.yaml").read_bytes())
    documents = [
        yaml.safe_load((ROOT / relative).read_bytes())
        for relative in manifest["root_resolver"]["asset_registries"]
    ]
    records = {
        record["asset_id"]: record
        for document in documents
        for record in document["records"]
    }
    return manifest, records


class Task21DatasetFreezeAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_yaml(PLAN_PATH)
        cls.freeze = load_json(FREEZE_PATH)
        cls.sample = load_json(SAMPLE_PATH)
        cls.index = load_json(INDEX_PATH)
        cls.receipt = load_json(RECEIPT_PATH)

    def test_frozen_inputs_and_exact_dataset_identity_are_stable(self) -> None:
        validate_frozen_inputs(ROOT, self.plan)
        rows = self.freeze["files"]
        self.assertEqual(len(rows), self.freeze["file_count"])
        self.assertEqual(
            sum(int(row["bytes"]) for row in rows),
            self.freeze["stored_bytes"],
        )
        self.assertEqual(
            sha256_bytes(canonical_json_bytes(rows)),
            self.freeze["source_inventory_sha256"],
        )
        recovery = load_yaml(RECOVERY_CONFIG_PATH)
        source_roots = [
            relative
            for component in recovery["components"]
            for relative in component["source_roots"]
        ]
        if all((ROOT / relative).is_dir() for relative in source_roots):
            rebuilt = build_dataset_freeze_manifest(
                repository_root=ROOT,
                plan=self.plan,
            )
            self.assertEqual(rebuilt, self.freeze)
        self.assertEqual(self.freeze["root_count"], 13)
        self.assertEqual(self.freeze["file_count"], 91)
        self.assertEqual(self.freeze["stored_bytes"], 1263895)
        self.assertEqual(
            self.freeze["source_inventory_sha256"],
            "aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae",
        )
        self.assertTrue(self.freeze["remote_recovery"]["exact_raw_readback"])
        self.assertTrue(self.freeze["remote_recovery"]["isolated_restore"])
        self.assertFalse(self.freeze["outcome_values_read"])
        self.assertFalse(self.freeze["freeze_policy"]["accepted_bytes_mutable"])

    def test_effective_sample_is_exact_and_claims_remain_narrow(self) -> None:
        self.assertEqual(build_effective_sample_summary(self.plan), self.sample)
        self.assertEqual(self.sample["population"]["complete_members"], 5)
        self.assertEqual(self.sample["population"]["complete_member_clusters"], 2)
        self.assertEqual(self.sample["totals"]["observed_panels"], 22)
        self.assertEqual(self.sample["totals"]["quote_pairs"], 88)
        self.assertEqual(self.sample["totals"]["quote_attempts"], 176)
        self.assertEqual(self.sample["totals"]["explicit_missing_panels"], 3)
        self.assertFalse(
            self.sample["selection_and_dependence"]["member_iid_assumption_allowed"]
        )
        self.assertTrue(
            self.sample["task22_eligibility"]["split_before_outcome_required"]
        )
        self.assertFalse(self.sample["task22_eligibility"]["alpha_claim_allowed"])

    def test_pre_a7_index_preserves_files_and_reconciles_planned_ids(self) -> None:
        rebuilt = build_artifact_index(repository_root=ROOT, plan=self.plan)
        self.assertEqual(rebuilt, self.index)
        self.assertEqual(self.index["file_count"], 198)
        reconciliation = self.index["planned_asset_id_reconciliation"]
        self.assertEqual(reconciliation["planned_id_count"], 69)
        self.assertEqual(len(reconciliation["registered_as_stable_assets"]), 10)
        self.assertEqual(len(reconciliation["superseded_by_this_index"]), 59)
        self.assertFalse(self.index["local_raw_included"])
        for row in self.index["files"]:
            with self.subTest(path=row["path"]):
                path = ROOT / row["path"]
                self.assertEqual(path.stat().st_size, row["bytes"])
                self.assertEqual(sha256(path), row["sha256"])

    def test_factory_fit_usage_authority_and_product_gate_are_exact(self) -> None:
        self.assertEqual(self.receipt["status"], "PASS")
        self.assertEqual(
            self.receipt["owner_verdict"],
            "DATASET_READY_FOR_NARROW_CONDITIONAL_ANALYSIS_WITH_LIMITATIONS",
        )
        verify_hash_bindings(ROOT, self.receipt["frozen_artifacts"])
        usage = self.receipt["usage"]
        self.assertEqual(usage["collection_external_requests"], 184)
        self.assertEqual(usage["live_shakedown_requests_separate_authority"], 8)
        self.assertEqual(usage["task21_provider_api_rpc_wss_calls_total"], 192)
        self.assertEqual(usage["drive_reads"], 34)
        self.assertEqual(usage["drive_writes"], 6)
        self.assertEqual(usage["cash_spend_usd_cents"], 0)
        critic = self.receipt["factory_fit"]
        self.assertEqual(critic["mode"], "FULL_REVIEW")
        self.assertEqual(critic["verdict"], "PASS_WITH_DURABLE_FOLLOWUPS")
        self.assertEqual(len(critic["checks"]), 15)
        self.assertTrue(
            all(check["status"] in {"PASS", "NOT_APPLICABLE"} for check in critic["checks"])
        )
        self.assertEqual(
            self.receipt["product_vision_reconciliation"]["terminal_result"],
            "CANONICALIZED_WITH_PATCH",
        )
        self.assertEqual(
            self.receipt["validation"],
            {
                "a7_targeted_suite": "PASS_10_OF_10",
                "catalog_validation": "PASS_0_26_0_369_ASSETS",
                "diff_check": "PASS",
                "full_repository_unit_suite": "PASS_1431_OF_1431",
                "generated_navigation": "PASS",
                "repository_state_validator": "DEFERRED_TO_A8_EXACT_STAGED_OR_CI_CHECKPOINT_CURRENT_DIRTY_TASK_BRANCH_IS_OUTSIDE_ACCEPTED_TOPOLOGY",
                "secret_scan": "PASS",
                "task21_combined_suite": "PASS_297_OF_297",
            },
        )
        actions = self.receipt["actual_actions"]
        self.assertTrue(actions["local_write_only"])
        self.assertTrue(
            all(value in (0, False) for key, value in actions.items() if key != "local_write_only")
        )

    def test_catalog_transaction_registers_only_stable_assets(self) -> None:
        manifest, records = load_catalog()
        expected_ids = set(self.plan["catalog_transaction"]["registered_asset_ids"])
        self.assertEqual(len(expected_ids), 29)
        self.assertEqual(manifest["catalog_version"], "0.26.0")
        self.assertEqual(
            manifest["current_checkpoint"],
            {
                "assets": 369,
                "asset_registries": 4,
                "schemas": 4,
                "queries": 8,
                "lifecycle_registries": 9,
                "lifecycle_records": 52,
            },
        )
        self.assertEqual(len(records), 369)
        self.assertTrue(expected_ids.issubset(records))
        for asset_id in expected_ids:
            record = records[asset_id]
            if record["location"]["kind"] == "git_path":
                relative = record["location"]["repository_path"]
                self.assertEqual(sha256(ROOT / relative), record["integrity"]["sha256"])
        self.assertEqual(
            set(self.receipt["catalog"]["registered_asset_ids"]), expected_ids
        )

    def test_resume_route_next_boundary_and_hygiene_fail_closed(self) -> None:
        marker = load_json(ROOT / "control/active_time_gates.json")
        router = marker["resume_router"]
        self.assertEqual(router["status"], "A7_ACCEPTED_PENDING_REPOSITORY_DELIVERY")
        self.assertEqual(
            router["read_only_command"][-2:],
            ["scripts/show_task21_final_owner_pulse.py", "--json"],
        )
        resolution = router["a7_resolution"]
        self.assertEqual(resolution["status"], "PASS_LOCAL_CANDIDATE")
        self.assertEqual(resolution["next_atom"], "T21-A8_REPOSITORY_DELIVERY_V1")
        self.assertFalse(resolution["next_atom_authorized"])
        self.assertFalse(resolution["task22_started"])
        self.assertEqual(
            self.receipt["next_boundary"]["status"], "NOT_AUTHORIZED"
        )

        candidates = [
            PLAN_PATH,
            RECEIPT_PATH,
            ROOT / "docs/handoffs/task21_to_task22_v1.md",
            ROOT / "docs/architecture/intents/ARCH-INTENT-003-product-owner-operating-topology.md",
        ]
        prohibited = [
            re.compile(r"(?i)\b[a-z]:[\\/]"),
            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[\"'][^\"']+[\"']"),
        ]
        for path in candidates:
            value = path.read_bytes()
            self.assertFalse(value.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r", value)
            self.assertTrue(value.endswith(b"\n"))
            text = value.decode("utf-8")
            self.assertTrue(all(line.rstrip(" \t") == line for line in text.splitlines()))
            for pattern in prohibited:
                self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
