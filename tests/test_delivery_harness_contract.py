from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path
from typing import Any

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "delivery-harness" / "harness.yaml"
PROFILE = ROOT / "delivery-harness" / "project-profile.yaml"
CONTEXT_MAP = ROOT / "delivery-harness" / "context-map.yaml"
RADAR = ROOT / "delivery-harness" / "capability-radar.yaml"
ACCEPTANCE = ROOT / "docs/evidence/control/delivery_harness_acceptance_v1.json"
FACTORY_FIT = ROOT / "docs/evidence/control/delivery_harness_factory_fit_v1.json"
CORE_CATALOG = ROOT / "catalog/assets/core.yaml"
MANIFEST = ROOT / "catalog/catalog_manifest.yaml"
SCHEMAS = {
    HARNESS: ROOT / "catalog/schemas/delivery_harness.schema.json",
    PROFILE: ROOT / "catalog/schemas/delivery_harness_project_profile.schema.json",
    CONTEXT_MAP: ROOT / "catalog/schemas/delivery_harness_context_map.schema.json",
    RADAR: ROOT / "catalog/schemas/delivery_harness_capability_radar.schema.json",
}

EXPECTED_ROUTES = {
    "DIRECT_CODEX_DELIVERY",
    "DIRECT_CURSOR_DELIVERY",
    "DESIGN_ONLY",
    "LEGACY_GITHUB_BATON_DORMANT",
}
EXPECTED_ACTIVE_ROUTES = {
    "DIRECT_CODEX_DELIVERY",
    "DIRECT_CURSOR_DELIVERY",
    "DESIGN_ONLY",
}
EXPECTED_CONTEXT_LANES = {"L0", "L1", "L2", "L3"}
EXPECTED_BUDGETS = {
    "agents_max_bytes": 12 * 1024,
    "cursor_always_apply_max_bytes": 6 * 1024,
    "ordinary_receipt_max_bytes": 48 * 1024,
    "auto_inline_file_max_bytes": 100 * 1024,
}
EXPECTED_CONTEXT_ROLES = {
    "MISSION_AND_INVARIANTS",
    "PRODUCT_ROADMAP",
    "ACTIVE_BOUNDED_WORK",
    "IMPLEMENTATION_STATE",
    "STABLE_ASSETS_AND_RELATIONS",
    "LIFECYCLE",
    "EXTERNAL_ROUTE_KNOWLEDGE",
    "ARCHITECTURE_DECISIONS",
    "DELIVERY_EVIDENCE",
    "HISTORICAL_CONTEXT",
}
EXPECTED_RADAR_CANDIDATES = {
    "SENTRY_OR_EQUIVALENT",
    "POSTHOG_OR_EQUIVALENT",
    "CLICKHOUSE_OR_REMOTE_ANALYTICS",
    "CONTEXT7_OR_DOCS_MCP",
}
REQUIRED_CATALOG_ASSETS = {
    "CTRL-DELIVERY-HARNESS-001",
    "CONFIG-DELIVERY-HARNESS-001",
    "CONFIG-DELIVERY-PROJECT-PROFILE-001",
    "CONFIG-DELIVERY-CONTEXT-MAP-001",
    "CONFIG-DELIVERY-CAPABILITY-RADAR-001",
    "SCRIPT-DELIVERY-HARNESS-001",
    "SKILL-DELIVERY-HARNESS-001",
    "POLICY-OWNER-ATTENTION-GATE-002",
    "ADR-DIRECT-DELIVERY-HARNESS-005",
    "PROTOCOL-DELIVERY-HARNESS-001",
    "PROTOCOL-DELIVERY-CONTEXT-001",
    "EVIDENCE-DELIVERY-HARNESS-ACCEPTANCE-001",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"mapping required: {path}")
    return value


def load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"schema mapping required: {path}")
    return value


def iter_items(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield path + (str(key),), item
            yield from iter_items(item, path + (str(key),))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield path + (str(index),), item
            yield from iter_items(item, path + (str(index),))


class DeliveryHarnessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = {path: load_yaml(path) for path in SCHEMAS}
        cls.schemas = {path: load_schema(schema) for path, schema in SCHEMAS.items()}

    def test_contracts_validate_against_closed_schemas(self) -> None:
        for path, document in self.documents.items():
            schema = self.schemas[path]
            with self.subTest(path=path):
                jsonschema.Draft202012Validator.check_schema(schema)
                jsonschema.validate(instance=document, schema=schema)
                mutated = copy.deepcopy(document)
                mutated["unexpected_field"] = True
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(instance=mutated, schema=schema)

    def test_harness_routes_budgets_and_dormant_baton_are_exact(self) -> None:
        harness = self.documents[HARNESS]
        self.assertEqual(harness["harness_id"], "DELIVERY_HARNESS_V1")
        self.assertEqual(set(harness["routes"]), EXPECTED_ROUTES)
        self.assertEqual(set(harness["active_routes"]), EXPECTED_ACTIVE_ROUTES)
        self.assertEqual(set(harness["context_lanes"]), EXPECTED_CONTEXT_LANES)
        self.assertEqual(harness["context_budgets"], EXPECTED_BUDGETS)
        dormant = harness["routes"]["LEGACY_GITHUB_BATON_DORMANT"]
        self.assertFalse(dormant["active"])
        self.assertFalse(dormant["task_selection"])
        self.assertEqual(dormant["merge"], "FORBIDDEN")
        self.assertEqual(harness["forbidden_active_input_routes"], ["GITHUB_BATON"])
        self.assertFalse(harness["external_authority"]["external_system"])
        self.assertFalse(harness["external_authority"]["signing_or_financial_action"])
        self.assertFalse(harness["external_authority"]["cash_spend"])
        self.assertFalse(harness["external_authority"]["cloud_activation"])
        self.assertEqual(
            harness["cloud_bundle"]["mode"],
            "OWNER_MANAGED_OPTIONAL_EXPORT",
        )
        self.assertFalse(harness["cloud_bundle"]["execution_gate"])
        self.assertFalse(harness["cloud_bundle"]["done_gate"])
        self.assertFalse(harness["cloud_bundle"]["smoke_required_by_harness"])
        self.assertFalse(harness["cloud_bundle"]["reminders"])
        self.assertFalse(harness["cloud_bundle"]["working_context_truth_owner"])
        self.assertTrue(harness["cloud_bundle"]["historical_registry_preserved"])

    def test_project_profile_binds_current_truth_owners(self) -> None:
        profile = self.documents[PROFILE]
        self.assertEqual(profile["profile_id"], "SOLANA_ALPHA_LAB_V1")
        self.assertEqual(profile["mode"], "BOUND_PROJECT")
        self.assertEqual(profile["repository"]["name"], "lancerbeta/solana-alpha-lab")
        self.assertEqual(profile["repository"]["default_branch"], "main")
        self.assertEqual(
            profile["bindings"],
            {
                "catalog_manifest": "catalog/catalog_manifest.yaml",
                "owner_attention_policy": "control/owner_attention_gate_v2.yaml",
                "context_map": "delivery-harness/context-map.yaml",
                "domain_policy": "delivery-harness/policies/solana-alpha-lab.md",
                "historical_cloud_bundle_registry": "docs/project_sources/release_registry_v1.yaml",
            },
        )
        self.assertEqual(profile["context_budgets"], EXPECTED_BUDGETS)
        self.assertFalse(profile["authority"]["external_system"])
        self.assertFalse(profile["authority"]["signing_or_financial_action"])
        self.assertFalse(profile["authority"]["cash_spend"])
        self.assertFalse(profile["authority"]["cloud_export_mutation"])
        self.assertEqual(profile["working_memory"]["truth_owner"], "GIT")
        self.assertEqual(
            profile["working_memory"]["task_resolution"],
            "EXACT_TASK_CONTRACT",
        )
        self.assertEqual(
            profile["working_memory"]["cloud_bundle"],
            "OWNER_MANAGED_OPTIONAL_EXPORT",
        )

    def test_context_map_has_exact_roles_and_explicit_missingness(self) -> None:
        context = self.documents[CONTEXT_MAP]
        roles = context["roles"]
        self.assertEqual({role["semantic_role"] for role in roles}, EXPECTED_CONTEXT_ROLES)
        for role in roles:
            with self.subTest(role=role["semantic_role"]):
                self.assertIn(role["lane"], EXPECTED_CONTEXT_LANES)
                self.assertIn(role["missingness"], {"ERROR", "EXPLICIT_GAP"})
                self.assertTrue(role["truth_owner"])
                self.assertIn(role["resolver"]["kind"], {
                    "EXACT_PATHS",
                    "EXACT_INPUT",
                    "GIT_IDENTITY",
                    "CATALOG_QUERY",
                    "SOURCE_RELEASE_REGISTRY",
                })
        active = next(
            role for role in roles if role["semantic_role"] == "ACTIVE_BOUNDED_WORK"
        )
        self.assertEqual(active["resolver"]["kind"], "EXACT_INPUT")
        self.assertEqual(active["missingness"], "ERROR")

    def test_capability_radar_is_one_candidate_fail_closed_and_non_authorizing(self) -> None:
        radar = self.documents[RADAR]
        self.assertEqual(radar["default_decision"], "NONE")
        self.assertEqual(radar["max_candidates"], 1)
        self.assertFalse(radar["authority"]["install"])
        self.assertFalse(radar["authority"]["credentials"])
        self.assertFalse(radar["authority"]["network"])
        self.assertFalse(radar["authority"]["paid_plan"])
        candidates = radar["candidates"]
        self.assertEqual(
            {candidate["candidate_id"] for candidate in candidates},
            EXPECTED_RADAR_CANDIDATES,
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate["candidate_id"]):
                self.assertTrue(candidate["conditions_all"])
                self.assertTrue(candidate["named_consumer_required"])
                for field in ("owner_decision", "measurable_value_test", "minimum_permissions", "data_exposure", "why_now"):
                    self.assertTrue(candidate[field])
                self.assertEqual(candidate["security_license_maintenance_cost_check"], "required_before_install")
                self.assertEqual(candidate["adoption_order"], ["ADOPT", "WRAP", "FORK", "BUILD"])
                self.assertTrue(candidate["fallback_without_tool"])
                self.assertTrue(candidate["exit_path"])

    def test_documents_have_no_machine_paths_or_secret_like_values(self) -> None:
        secret_key = re.compile(r"(?i)(api[_-]?key|private[_-]?key|seed|secret|token)")
        absolute_windows = re.compile(r"^[A-Za-z]:[\\/]")
        for document_path, document in self.documents.items():
            for path, value in iter_items(document):
                with self.subTest(document=document_path, path=path):
                    if isinstance(value, str):
                        self.assertIsNone(absolute_windows.match(value))
                        if secret_key.search(".".join(path)):
                            self.assertIn(value, {"REDACTED", "NONE", "NOT_REQUIRED"})

    def test_local_runtime_receipts_are_ignored(self) -> None:
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("local/delivery_harness/", lines)

    def test_acceptance_binds_final_implementation_and_non_claims(self) -> None:
        receipt = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(receipt["state_change"], "IMPLEMENTED_UNVERIFIED")
        self.assertEqual(receipt["cloud_bundle_mode"], "OWNER_MANAGED_OPTIONAL_EXPORT")
        self.assertFalse(receipt["cloud_bundle_required_by_harness"])
        self.assertFalse(receipt["cloud_bundle_smoke_required"])
        self.assertEqual(receipt["capability_radar_now"], "NONE")
        self.assertEqual(receipt["side_effects"], {
            "provider_calls": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd": 0,
        })
        bound = receipt["implementation_bindings"]
        required_paths = {
            "docs/superpowers/specs/2026-08-13-delivery-harness-design.md",
            "docs/superpowers/plans/2026-08-13-delivery-harness-v1.md",
            "delivery-harness/harness.yaml",
            "delivery-harness/project-profile.yaml",
            "delivery-harness/context-map.yaml",
            "delivery-harness/capability-radar.yaml",
            "scripts/delivery_harness.py",
            "control/owner_attention_gate_v2.yaml",
            "AGENTS.md",
            ".agents/skills/delivery-harness/SKILL.md",
            "docs/agent/DELIVERY_HARNESS_PROTOCOL.md",
            "docs/agent/DELIVERY_CONTEXT_PROTOCOL.md",
            "tests/test_delivery_harness_contract.py",
            "tests/test_delivery_harness_adapters.py",
        }
        self.assertTrue(required_paths.issubset(bound))
        for relative, observed in bound.items():
            self.assertEqual(observed, sha256(ROOT / relative), relative)
        self.assertEqual(receipt["factory_fit"]["sha256"], sha256(FACTORY_FIT))

    def test_catalog_registers_harness_and_schemas(self) -> None:
        catalog = load_yaml(CORE_CATALOG)
        records = {item["asset_id"]: item for item in catalog["records"]}
        self.assertTrue(REQUIRED_CATALOG_ASSETS.issubset(records))
        for asset_id in REQUIRED_CATALOG_ASSETS:
            record = records[asset_id]
            if record["location"]["kind"] == "git_path":
                self.assertEqual(
                    record["integrity"]["sha256"],
                    sha256(ROOT / record["location"]["repository_path"]),
                    asset_id,
                )
        manifest = load_yaml(MANIFEST)
        for relative in (
            "catalog/schemas/delivery_harness.schema.json",
            "catalog/schemas/delivery_harness_project_profile.schema.json",
            "catalog/schemas/delivery_harness_context_map.schema.json",
            "catalog/schemas/delivery_harness_context_receipt.schema.json",
            "catalog/schemas/delivery_harness_capability_radar.schema.json",
            "catalog/schemas/owner_attention_gate_v2.schema.json",
        ):
            self.assertIn(relative, manifest["root_resolver"]["schemas"])


if __name__ == "__main__":
    unittest.main()
