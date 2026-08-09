from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs/project_sources/release_registry_v1.yaml"
CATEGORY_CORE_PATH = ROOT / "catalog/assets/core.yaml"
CATALOG_MANIFEST_PATH = ROOT / "catalog/catalog_manifest.yaml"
RELEASE_ID = "PSR-0003-T28-RC001-FREEZE"
RELEASE_ROOT = ROOT / "docs/project_sources/releases" / RELEASE_ID
RECEIPT_PATH = ROOT / "docs/evidence/task28/a3_permanent_sources_release_candidate_acceptance_v1.json"
CATALOG_ASSET_ID = "EVIDENCE-T28-A3-PERMANENT-SOURCES-RELEASE-001"
ACTIVATION_RECEIPT_PATH = ROOT / "docs/evidence/task28/a3r1_project_sources_activation_receipt_v1.json"
ACTIVATION_CATALOG_ASSET_ID = "EVIDENCE-T28-A3R1-SOURCE-ACTIVATION-001"
IMMUTABLE_HASHES = {
    "operating_system": "187aa5d1405c55868d7147a7cdf9e0605a9a51f613ab5597ae44682fcbc67c84",
    "research_blueprint": "ec756d5be0196dd8207ac08512af5e3a9a5032eb5b0b40e3f8fcca2beb170ba1",
}
MUTABLE_FILES = {
    "canonical_manifest": "canonical_manifest.yaml",
    "roadmap": "roadmap.md",
    "current_system_state": "current_system_state.md",
    "phase_archive": "task_archive_P0_P1_v39.md",
    "active_task": "task_28_rc001_registry_freeze.md",
}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def release_by_id(registry: dict, release_id: str) -> dict:
    return next(release for release in registry["releases"] if release["release_id"] == release_id)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checksum_entries(path: Path) -> dict[str, str]:
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, filename = line.split("  ", maxsplit=1)
        entries[filename] = digest
    return entries


class Task28PermanentSourcesReleaseTests(unittest.TestCase):
    def test_task28_owner_smoke_activates_psr0003_without_rewriting_bundle_bytes(self) -> None:
        """Catches an activation overlay that is missing the exact owner smoke binding."""
        registry = load_yaml(REGISTRY_PATH)

        release = release_by_id(registry, RELEASE_ID)

        self.assertEqual(registry["active_ui_release_id"], RELEASE_ID)
        self.assertIsNone(registry["latest_candidate_release_id"])
        self.assertEqual(release["status"], "ACTIVATED_BY_OWNER_SMOKE")
        self.assertEqual(release["activation_receipt"], ACTIVATION_RECEIPT_PATH.relative_to(ROOT).as_posix())

        prior_active = release_by_id(registry, "PSR-0002-T27-CLOSE")
        self.assertEqual(prior_active["status"], "SUPERSEDED")
        self.assertEqual(prior_active["superseded_by_release_id"], RELEASE_ID)
        self.assertEqual(release["supersedes_release_id"], prior_active["release_id"])

        activation_receipt = json.loads(ACTIVATION_RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(activation_receipt["release_id"], RELEASE_ID)
        self.assertEqual(activation_receipt["activation_evidence"]["class"], "OWNER_ATTESTATION")
        self.assertEqual(activation_receipt["activation_evidence"]["reported_terminal"], "TASK28_SOURCE_SMOKE=PASS")
        self.assertEqual(
            activation_receipt["manifest_binding"],
            release["artifact_bindings"]["canonical_manifest"],
        )
        self.assertFalse(activation_receipt["decision"]["canonical_task28_done"])

    def test_candidate_bundle_is_a_complete_hash_bound_five_role_replacement(self) -> None:
        """Rejects a stale or partial source package before it can reach cloud UI."""
        registry = load_yaml(REGISTRY_PATH)
        candidate = release_by_id(registry, RELEASE_ID)
        manifest = load_yaml(RELEASE_ROOT / "canonical_manifest.yaml")
        checksums = checksum_entries(RELEASE_ROOT / "CHECKSUMS_SHA256.txt")

        self.assertEqual(
            {path.name for path in RELEASE_ROOT.iterdir()},
            set(MUTABLE_FILES.values()) | {"CHECKSUMS_SHA256.txt", "FRESH_CHAT_SMOKE.md"},
        )
        self.assertEqual(manifest["schema_version"], "4.9")
        self.assertEqual(manifest["activation_map"]["replace_source_roles"], list(MUTABLE_FILES))
        self.assertEqual(manifest["activation_map"]["keep_byte_for_byte"], list(IMMUTABLE_HASHES))
        self.assertEqual(manifest["canonical"]["operating_system"]["sha256"], IMMUTABLE_HASHES["operating_system"])
        self.assertEqual(manifest["canonical"]["research_blueprint"]["sha256"], IMMUTABLE_HASHES["research_blueprint"])

        self.assertEqual(set(checksums), {"canonical_manifest.yaml", *MUTABLE_FILES.values()})
        for role, filename in MUTABLE_FILES.items():
            if role != "canonical_manifest":
                self.assertEqual(manifest["canonical"][role]["sha256"], sha256(RELEASE_ROOT / filename))
            self.assertEqual(checksums[filename], sha256(RELEASE_ROOT / filename))
        self.assertEqual(checksums["canonical_manifest.yaml"], sha256(RELEASE_ROOT / "canonical_manifest.yaml"))
        self.assertEqual(
            candidate["artifact_bindings"]["canonical_manifest"]["sha256"],
            sha256(RELEASE_ROOT / "canonical_manifest.yaml"),
        )
        self.assertEqual(
            candidate["artifact_bindings"]["checksums"]["sha256"],
            sha256(RELEASE_ROOT / "CHECKSUMS_SHA256.txt"),
        )
        smoke = (RELEASE_ROOT / "FRESH_CHAT_SMOKE.md").read_text(encoding="utf-8")
        self.assertIn("TASK28_SOURCE_SMOKE=PASS|FAIL", smoke)
        for filename, digest in checksums.items():
            self.assertIn(digest, smoke)

    def test_candidate_receipt_retains_blocked_research_and_owner_activation_boundary(self) -> None:
        """Rejects a release that could be mistaken for task completion or trial authority."""
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

        self.assertEqual(receipt["source_release"]["release_id"], RELEASE_ID)
        self.assertEqual(receipt["source_release"]["prior_active_release_id"], "PSR-0002-T27-CLOSE")
        self.assertEqual(receipt["source_release"]["mutable_roles"], list(MUTABLE_FILES))
        self.assertEqual(receipt["source_release"]["immutable_roles"], IMMUTABLE_HASHES)
        for role, filename in MUTABLE_FILES.items():
            binding = receipt["artifact_bindings"][role]
            self.assertEqual(binding["path"], (RELEASE_ROOT / filename).relative_to(ROOT).as_posix())
            self.assertEqual(binding["sha256"], sha256(RELEASE_ROOT / filename))
        self.assertEqual(receipt["decision"]["task28_acceptance"], False)
        self.assertEqual(receipt["decision"]["source_activation"], False)
        self.assertEqual(receipt["decision"]["next_task_selected"], False)
        self.assertEqual(receipt["side_effect_counters"]["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(receipt["side_effect_counters"]["wallet_signer_transaction_actions"], 0)

    def test_candidate_and_activation_receipts_are_discoverable_in_catalog_without_task_done_claim(self) -> None:
        """Prevents a durable Source candidate from becoming an untracked Git island."""
        core = load_yaml(CATEGORY_CORE_PATH)
        catalog_manifest = load_yaml(CATALOG_MANIFEST_PATH)
        record = next(item for item in core["records"] if item["asset_id"] == CATALOG_ASSET_ID)

        self.assertEqual(record["location"]["repository_path"], RECEIPT_PATH.relative_to(ROOT).as_posix())
        self.assertEqual(record["integrity"]["sha256"], sha256(RECEIPT_PATH))
        self.assertIn(
            {"relation_type": "derived_from", "target_asset_id": "EVIDENCE-T28-A2-CATALOG-FACTORY-FIT-001"},
            record["relations"],
        )
        activation_record = next(item for item in core["records"] if item["asset_id"] == ACTIVATION_CATALOG_ASSET_ID)
        self.assertEqual(activation_record["location"]["repository_path"], ACTIVATION_RECEIPT_PATH.relative_to(ROOT).as_posix())
        self.assertEqual(activation_record["integrity"]["sha256"], sha256(ACTIVATION_RECEIPT_PATH))
        self.assertIn(
            {"relation_type": "derived_from", "target_asset_id": CATALOG_ASSET_ID},
            activation_record["relations"],
        )
        self.assertEqual(catalog_manifest["catalog_version"], "0.42.0")
        self.assertEqual(catalog_manifest["current_checkpoint"]["assets"], 580)
        self.assertIn(CATALOG_ASSET_ID, catalog_manifest["mandatory_asset_ids"])
        self.assertIn(ACTIVATION_CATALOG_ASSET_ID, catalog_manifest["mandatory_asset_ids"])
