from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task20"
    / "acceptance_catalog_factory_fit_v1.json"
)
POLICY_PATH = ROOT / "configs" / "task20_retention_recovery_policy_v1.yaml"
EXPECTED_RECEIPT_SHA256 = (
    "23ce57e4a65aa37a8bbcb662077d14e3f6827da76ead3cae3ff339ad0fecc886"
)
EXPECTED_IDS = {
    "CONTRACT-T20-COLLECTION-SPEC-001",
    "CONFIG-T20-COLLECTION-SPEC-001",
    "TEST-T20-COLLECTION-SPEC-CONTRACT-001",
    "CONTRACT-T20-COVERAGE-RETENTION-RECOVERY-001",
    "ARCH-T20-HYPOTHESIS-DATA-COVERAGE-MATRIX-001",
    "CONFIG-T20-RETENTION-RECOVERY-POLICY-001",
    "TEST-T20-COVERAGE-RETENTION-RECOVERY-001",
    "EVIDENCE-T20-ACCEPTANCE-CATALOG-FACTORY-FIT-001",
    "TEST-T20-ACCEPTANCE-CATALOG-FACTORY-FIT-001",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_catalog() -> tuple[dict, dict[str, dict]]:
    manifest = yaml.safe_load(
        (ROOT / "catalog" / "catalog_manifest.yaml").read_bytes()
    )
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


def policy_errors(policy: dict) -> set[str]:
    errors: set[str] = set()
    fields = policy["coverage_matrix"]
    if len(fields) != 40:
        errors.add("FIELD_SET_DRIFT_REQUIRES_NEW_SPEC_VERSION")
    if any(not field["named_consumers"] for field in fields):
        errors.add("UNNAMED_CONSUMER")
    scope = policy["scope"]
    if (
        scope["global_solana_universe_authorized"]
        or scope["market_wide_tick_capture_authorized"]
    ):
        errors.add("BROAD_CAPTURE_AUTHORITY")
    if any(
        rules["automatic_expiry"]
        for rules in policy["retention_classes"].values()
    ):
        errors.add("AUTOMATIC_EXPIRY")
    if policy["immutable_storage"]["accepted_bytes_overwrite_allowed"]:
        errors.add("ACCEPTED_BYTES_OVERWRITE")
    if policy["backup"]["maximum_age_hours"] > 24:
        errors.add("BACKUP_DEADLINE_TOO_SLOW")
    required_before = policy["restore_proof"]["full_restore"]["required_before"]
    if "DATASET_FREEZE" not in required_before:
        errors.add("FREEZE_WITHOUT_FULL_RESTORE")
    authority = policy["authority"]
    if (
        authority["network_calls"] != 0
        or authority["provider_api_rpc_wss_calls"] != 0
        or authority["drive_writes"] != 0
        or policy["next_atom"]["forward_collection_authorized"]
    ):
        errors.add("EXTERNAL_AUTHORITY_LEAK")
    return errors


class Task20AcceptanceCatalogFactoryFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt_bytes = RECEIPT_PATH.read_bytes()
        cls.receipt = json.loads(cls.receipt_bytes)
        cls.policy = yaml.safe_load(POLICY_PATH.read_bytes())

    def test_receipt_accepts_exact_frozen_candidate_with_limitations(
        self,
    ) -> None:
        self.assertEqual(sha256(RECEIPT_PATH), EXPECTED_RECEIPT_SHA256)
        self.assertEqual(self.receipt["status"], "PASS")
        accepted = self.receipt["accepted_result"]
        self.assertEqual(
            accepted["owner_verdict"],
            "SPEC_READY_WITH_LIMITATIONS",
        )
        self.assertTrue(accepted["collection_plan_input_eligible"])
        self.assertFalse(accepted["forward_collection_authorized"])
        self.assertFalse(accepted["collector_or_scheduler_implemented"])
        self.assertFalse(accepted["provider_selected"])
        self.assertFalse(accepted["dataset_recovery_proven"])
        self.assertEqual(accepted["field_count"], 40)
        self.assertEqual(accepted["tier_counts"], {"T0": 17, "T1": 11, "T2": 12})
        self.assertEqual(
            (accepted["adversarial_vectors_passed"], accepted["adversarial_vectors_total"]),
            (8, 8),
        )
        artifacts = self.receipt["frozen_artifacts"]
        self.assertEqual(len(artifacts), 7)
        for artifact in artifacts:
            with self.subTest(asset_id=artifact["asset_id"]):
                self.assertEqual(
                    sha256(ROOT / artifact["path"]),
                    artifact["sha256"],
                )

    def test_eight_adversarial_policy_vectors_fail_closed(self) -> None:
        vectors: list[tuple[str, str, object]] = []

        candidate = copy.deepcopy(self.policy)
        candidate["coverage_matrix"].append(copy.deepcopy(candidate["coverage_matrix"][0]))
        candidate["coverage_matrix"][-1]["field_id"] = "silent_new_field"
        vectors.append(("unversioned_field", "FIELD_SET_DRIFT_REQUIRES_NEW_SPEC_VERSION", candidate))

        candidate = copy.deepcopy(self.policy)
        candidate["coverage_matrix"][0]["named_consumers"] = []
        vectors.append(("unnamed_consumer", "UNNAMED_CONSUMER", candidate))

        candidate = copy.deepcopy(self.policy)
        candidate["scope"]["market_wide_tick_capture_authorized"] = True
        vectors.append(("broad_capture", "BROAD_CAPTURE_AUTHORITY", candidate))

        candidate = copy.deepcopy(self.policy)
        candidate["retention_classes"]["UNIQUE_RAW_EVIDENCE"]["automatic_expiry"] = True
        vectors.append(("automatic_expiry", "AUTOMATIC_EXPIRY", candidate))

        candidate = copy.deepcopy(self.policy)
        candidate["immutable_storage"]["accepted_bytes_overwrite_allowed"] = True
        vectors.append(("overwrite", "ACCEPTED_BYTES_OVERWRITE", candidate))

        candidate = copy.deepcopy(self.policy)
        candidate["backup"]["maximum_age_hours"] = 25
        vectors.append(("late_backup", "BACKUP_DEADLINE_TOO_SLOW", candidate))

        candidate = copy.deepcopy(self.policy)
        candidate["restore_proof"]["full_restore"]["required_before"].remove(
            "DATASET_FREEZE"
        )
        vectors.append(("no_full_restore", "FREEZE_WITHOUT_FULL_RESTORE", candidate))

        candidate = copy.deepcopy(self.policy)
        candidate["authority"]["provider_api_rpc_wss_calls"] = 1
        vectors.append(("authority_leak", "EXTERNAL_AUTHORITY_LEAK", candidate))

        self.assertEqual(policy_errors(self.policy), set())
        self.assertEqual(len(vectors), 8)
        for vector_id, expected_error, candidate in vectors:
            with self.subTest(vector=vector_id):
                self.assertIn(expected_error, policy_errors(candidate))

    def test_catalog_transaction_is_exact_hash_bound_and_complete(self) -> None:
        manifest, records = load_catalog()
        version = tuple(int(part) for part in manifest["catalog_version"].split("."))
        self.assertGreaterEqual(version, (0, 25, 0))
        checkpoint = manifest["current_checkpoint"]
        self.assertGreaterEqual(checkpoint["assets"], 340)
        self.assertEqual(checkpoint["asset_registries"], 4)
        self.assertEqual(checkpoint["schemas"], 4)
        self.assertEqual(checkpoint["queries"], 8)
        self.assertEqual(checkpoint["lifecycle_registries"], 9)
        self.assertEqual(checkpoint["lifecycle_records"], 52)
        self.assertEqual(len(records), checkpoint["assets"])
        self.assertEqual(self.receipt["catalog"]["catalog_version"], "0.25.0")
        self.assertEqual(self.receipt["catalog"]["assets"], 340)
        self.assertEqual(
            set(self.receipt["catalog"]["registered_asset_ids"]),
            EXPECTED_IDS,
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

    def test_factory_fit_is_complete_and_runtime_followup_is_durable(
        self,
    ) -> None:
        critic = self.receipt["factory_fit"]
        self.assertEqual(critic["mode"], "FULL_REVIEW")
        self.assertEqual(critic["verdict"], "PASS_WITH_DURABLE_FOLLOWUP")
        self.assertEqual(critic["bounded_correction"], "NONE")
        self.assertEqual(len(critic["checks"]), 15)
        self.assertTrue(
            all(
                check["status"] in {"PASS", "NOT_APPLICABLE"}
                for check in critic["checks"]
            )
        )
        previous = critic["previous_durable_followup"]
        self.assertEqual(
            previous["status"],
            "POLICY_SATISFIED_RUNTIME_TRIGGER_PRESERVED",
        )
        self.assertEqual(previous["evidence"], "RETENTION-RECOVERY-T20-001")
        followup = critic["new_followup"]
        self.assertEqual(
            followup["followup_id"],
            "TASK21_PRE_COLLECTION_RUNTIME_RECOVERY_GATE",
        )
        self.assertEqual(
            followup["activation_trigger"],
            "BEFORE_FIRST_FORWARD_COLLECTION_WRITE",
        )
        self.assertEqual(len(followup["minimum_evidence"]), 6)

    def test_navigation_authority_nonclaims_and_hygiene_are_exact(self) -> None:
        project_map = (ROOT / "docs" / "PROJECT_MAP.md").read_text(
            encoding="utf-8"
        )
        edges = json.loads(
            (ROOT / "catalog" / "generated" / "asset_edges.json").read_bytes()
        )
        edge_ids = {edge["source_asset_id"] for edge in edges["edges"]}
        for asset_id in EXPECTED_IDS:
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, project_map)
                self.assertIn(asset_id, edge_ids)

        authority = self.receipt["authority"]
        self.assertTrue(authority["local_write_only"])
        for field, value in authority.items():
            if field != "local_write_only":
                with self.subTest(field=field):
                    self.assertIn(value, (0, False))
        self.assertIn(
            "NOT_FORWARD_COLLECTION_AUTHORITY",
            self.receipt["nonclaims"],
        )
        self.assertEqual(
            self.receipt["next_gate"],
            {
                "atom_id": "T20-A5_REPOSITORY_DELIVERY_V1",
                "authority": "COMMIT_AND_NON_FORCE_TASK_BRANCH_PUSH_DRAFT_PR_CI",
                "authorized_by_t20_a4": False,
            },
        )

        candidates = {
            "receipt": self.receipt_bytes,
            "test": Path(__file__).read_bytes(),
        }
        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\b[a-z]:[\\/]"),
            "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            "credential_assignment": re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)"
                r"\s*[:=]\s*[\"'][^\"']+[\"']"
            ),
        }
        for label, candidate in candidates.items():
            with self.subTest(file=label):
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
                for pattern_name, pattern in prohibited.items():
                    with self.subTest(pattern=pattern_name):
                        self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
