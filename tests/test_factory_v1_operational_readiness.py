from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INTENT_PATH = (
    ROOT
    / "docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md"
)
CONFIG_PATH = ROOT / "configs/factory_v1_operational_readiness_v1.yaml"
CONTRACT_PATH = ROOT / "docs/tasks/FACTORY-V1-OPERATIONAL-READINESS-V1.md"
ARCHITECTURE_CATALOG_PATH = ROOT / "catalog/assets/architecture.yaml"
CORE_CATALOG_PATH = ROOT / "catalog/assets/core.yaml"
MANIFEST_PATH = ROOT / "catalog/catalog_manifest.yaml"
PROJECT_MAP_PATH = ROOT / "docs/PROJECT_MAP.md"
EDGE_PATH = ROOT / "catalog/generated/asset_edges.json"
DOMAIN_POLICY_PATH = ROOT / "delivery-harness/policies/solana-alpha-lab.md"
HISTORICAL_SOURCES_ROADMAPS = (
    ROOT / "docs/project_sources/releases/PSR-0001-T27-A0-A5/roadmap.md",
    ROOT / "docs/project_sources/releases/PSR-0002-T27-CLOSE/roadmap.md",
    ROOT / "docs/project_sources/releases/PSR-0003-T28-RC001-FREEZE/roadmap.md",
)
INTENT_ID = "ARCH-INTENT-005"
CONFIG_ID = "CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001"
CTRL_ID = "CTRL-FACTORY-V1-OPERATIONAL-READINESS-001"
TEST_ID = "TEST-FACTORY-V1-OPERATIONAL-READINESS-001"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontmatter(path: Path) -> dict:
    parts = path.read_text(encoding="utf-8").split("---", 2)
    if len(parts) != 3:
        raise AssertionError("frontmatter_missing")
    return yaml.safe_load(parts[1])


def load_records(path: Path) -> dict[str, dict]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {record["asset_id"]: record for record in document["records"]}


class FactoryV1OperationalReadinessTests(unittest.TestCase):
    def test_intent_is_accepted_direction_not_implemented(self) -> None:
        document = frontmatter(INTENT_PATH)
        self.assertEqual(document["intent_id"], INTENT_ID)
        self.assertEqual(document["intent_version"], "1.0")
        self.assertEqual(document["status"], "ACCEPTED_DIRECTION_NOT_IMPLEMENTED")
        self.assertEqual(document["implementation"], "NOT_IMPLEMENTED")
        self.assertEqual(document["milestone_id"], "FACTORY_V1_OPERATIONAL_READY")
        self.assertEqual(document["milestone_status"], "TRIGGERED")
        self.assertEqual(
            document["extends"],
            ["ARCH-INTENT-002", "ARCH-INTENT-003", "ARCH-INTENT-004", "DELIVERY_HARNESS_V1"],
        )
        self.assertFalse(document["authority"]["provider_read"])
        self.assertFalse(document["authority"]["wallet_signer_transaction"])
        self.assertFalse(document["authority"]["cash_spend"])
        self.assertFalse(document["authority"]["project_source_mutation"])
        self.assertFalse(document["authority"]["ui_framework_selection"])
        self.assertFalse(document["authority"]["deployment"])
        text = INTENT_PATH.read_text(encoding="utf-8")
        self.assertIn("Owner Cockpit", text)
        self.assertIn("ExperimentSpec", text)
        self.assertIn("derived read model", text)
        self.assertIn("must not preempt", text.lower())
        self.assertIn("WATCH, not Factory v1 PASS inventory", text)
        self.assertIn("`FACTORY_V1_OPERATIONAL_READY` PASS checklist", text)
        self.assertIn("TASK-35A", text)
        self.assertNotIn("Kubernetes is required", text)

    def test_yaml_contract_is_triggered_milestone_not_task_chain(self) -> None:
        contract = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema"], "smial.factory-v1-operational-readiness")
        self.assertEqual(contract["intent_id"], INTENT_ID)
        self.assertEqual(contract["status"], "ACCEPTED_DIRECTION_NOT_IMPLEMENTED")
        self.assertEqual(contract["implementation"], "NOT_IMPLEMENTED")
        self.assertEqual(contract["mode"], "DESIGN_ONLY")
        self.assertEqual(contract["milestone"]["milestone_id"], "FACTORY_V1_OPERATIONAL_READY")
        self.assertEqual(contract["milestone"]["status"], "TRIGGERED")
        self.assertEqual(
            contract["milestone"]["triggered_by"],
            "OWNER_EXPLICITLY_SELECTS_FACTORY_PRODUCTIZATION",
        )
        self.assertEqual(
            contract["milestone"]["kernel_atom"],
            "FACTORY_V1_PRODUCT_KERNEL_LOCAL_VERTICAL_SLICE_V1",
        )
        self.assertFalse(contract["live_roadmap_binding"]["numbered_task_chain_inserted"])
        self.assertEqual(
            contract["live_roadmap_binding"]["historical_project_sources_roadmaps"],
            "DO_NOT_MODIFY",
        )
        self.assertEqual(
            contract["live_roadmap_binding"]["this_contract_path"],
            "configs/factory_v1_operational_readiness_v1.yaml",
        )
        self.assertEqual(
            contract["domain_policy_integration"]["patch_status"],
            "NOT_APPLIED_HASH_BOUND_HISTORICAL_RECEIPTS",
        )
        self.assertFalse(contract["domain_policy_integration"]["entry_gate_resolves_this_file"])
        self.assertEqual(
            contract["domain_policy_integration"]["deferred_invariant_record"],
            "configs/factory_v1_operational_readiness_v1.yaml",
        )
        self.assertNotIn("live_invariant_owner", contract["domain_policy_integration"])
        self.assertFalse(contract["milestone"]["start_task35a_as_parallel_chain"])
        self.assertEqual(
            contract["milestone"]["historical_numbered_cockpit_candidate"],
            "ROADMAP-PATCH-T21-PRODUCT-VISION-001",
        )
        self.assertTrue(contract["owner_experience_map"]["not_factory_v1_pass_inventory"])
        self.assertTrue(contract["commissioning_pass_checklist"]["forbids_methods_inventory_substitution"])
        self.assertIn(
            "commissioning run",
            contract["domain_policy_integration"]["invariant"],
        )
        self.assertEqual(contract["gate"]["factory_leverage"]["commissioning_hypothesis_core_product_code_changes"], 0)
        self.assertEqual(contract["truth_owners"]["owner_cockpit"], "NOTHING")
        self.assertEqual(contract["capability_radar"]["now"], "NONE")
        self.assertFalse(contract["capability_radar"]["grants_install_credential_network_deploy_or_spend"])
        self.assertFalse(contract["authority"]["repository_product_mutation"])
        self.assertNotIn("TASK-42", yaml.dump(contract))
        self.assertNotIn("TASK-43", yaml.dump(contract))

    def test_task_contract_binds_yaml_as_live_roadmap(self) -> None:
        metadata = frontmatter(CONTRACT_PATH)
        self.assertEqual(metadata["task_id"], "FACTORY-V1-OPERATIONAL-READINESS-V1")
        self.assertIn("DESIGN_ONLY", metadata["allowed_routes"])
        self.assertEqual(
            metadata["context_requirements"]["roadmap_path"],
            "configs/factory_v1_operational_readiness_v1.yaml",
        )
        self.assertIn("HISTORICAL_PROJECT_SOURCES_ROADMAP_MUTATION", metadata["stop_conditions"])
        self.assertIn("DOMAIN_POLICY_HASH_BOUND_MUTATION", metadata["stop_conditions"])
        self.assertNotIn(
            "delivery-harness/policies/solana-alpha-lab.md",
            metadata["managed_write_set"],
        )

    def test_catalog_binds_intent_config_and_generated_discovery(self) -> None:
        architecture = load_records(ARCHITECTURE_CATALOG_PATH)
        core = load_records(CORE_CATALOG_PATH)
        intent = architecture[INTENT_ID]
        self.assertEqual(intent["status"], "ACCEPTED_DIRECTION_NOT_IMPLEMENTED")
        self.assertEqual(intent["integrity"]["sha256"], sha256(INTENT_PATH))
        self.assertEqual(intent["origin"], "REPOSITORY")
        self.assertEqual(
            intent["provenance"]["imported_by_task"],
            "FACTORY-V1-OPERATIONAL-READINESS-V1",
        )
        self.assertEqual(intent["evidence"], [])
        self.assertEqual(
            {item["target_asset_id"] for item in intent["relations"]},
            {
                "ARCH-INTENT-002",
                "ARCH-INTENT-004",
                "ARCH-INTENT-T21-PRODUCT-VISION-001",
                CONFIG_ID,
                "ROADMAP-PATCH-T21-PRODUCT-VISION-001",
            },
        )
        config = core[CONFIG_ID]
        self.assertEqual(config["integrity"]["sha256"], sha256(CONFIG_PATH))
        self.assertEqual(core[CTRL_ID]["integrity"]["sha256"], sha256(CONTRACT_PATH))
        self.assertEqual(core[TEST_ID]["integrity"]["sha256"], sha256(Path(__file__)))
        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        for asset_id in (INTENT_ID, CONFIG_ID, CTRL_ID, TEST_ID):
            self.assertIn(asset_id, manifest["mandatory_asset_ids"])
            self.assertIn(asset_id, PROJECT_MAP_PATH.read_text(encoding="utf-8"))
            self.assertIn(asset_id, EDGE_PATH.read_text(encoding="utf-8"))

    def test_historical_sources_and_domain_policy_bytes_are_untouched(self) -> None:
        policy = DOMAIN_POLICY_PATH.read_text(encoding="utf-8")
        self.assertIn("## FACTORY_LEVERAGE_INVARIANT", policy)
        self.assertNotIn("FACTORY_V1_OPERATIONAL_READY", policy)
        for path in HISTORICAL_SOURCES_ROADMAPS:
            self.assertTrue(path.is_file(), path)
            self.assertNotIn("FACTORY_V1_OPERATIONAL_READY", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
