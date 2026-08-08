from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from solana_alpha_lab.task28_rc001_registry_freeze import (
        evaluate_admissibility,
    )
except ModuleNotFoundError:
    evaluate_admissibility = None

try:
    from solana_alpha_lab.task28_rc001_registry_freeze import (
        canonical_definition_hash,
        validate_rc001_snapshot,
    )
except ImportError:
    canonical_definition_hash = None
    validate_rc001_snapshot = None


CONFIG_PATH = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task28_rc001_registry_freeze.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task28/rc001_registry_freeze_v1.json"
CONTRACT_PATH = ROOT / "docs/contracts/task28_rc001_registry_freeze_contract_v1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/task28_rc001_registry_freeze.py"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task28/a1_rc001_registry_freeze_acceptance_v1.json"
CATALOG_CORE_PATH = ROOT / "catalog/assets/core.yaml"
FACTORY_FIT_PATH = ROOT / "docs/evidence/task28/a2_catalog_factory_fit_v1.json"
REGISTRY_PATHS = {
    "research_cycles": ROOT / "registries/research_cycles.yaml",
    "hypotheses": ROOT / "registries/hypotheses.yaml",
    "feature_catalog": ROOT / "registries/feature_catalog.yaml",
    "global_trial_ledger": ROOT / "registries/global_trial_ledger.yaml",
}
KNOWN_EVIDENCE_PATHS = {
    "task24_stop": ROOT / "docs/evidence/task24/a6_bounded_data_redesign_or_stop_decision_v1.json",
    "task25_factory_fit": ROOT / "docs/evidence/task25/a6_catalog_factory_fit_v1.json",
    "task26b_route": ROOT / "docs/evidence/task26b/a1_execution_witness_route_decision_v1.json",
    "task27_route_close": ROOT / "docs/evidence/task27/a1s4_owner_route_close_and_task_outcome_acceptance_v1.json",
}
TASK28_REQUIRED_ASSET_PATHS = {
    "DOC-T28-RC001-REGISTRY-FREEZE-001": ROOT / "docs/tasks/TASK-28-rc001-registry-freeze.md",
    "CONTRACT-T28-RC001-REGISTRY-FREEZE-001": CONTRACT_PATH,
    "CONFIG-T28-RC001-REGISTRY-FREEZE-001": CONFIG_PATH,
    "SCHEMA-T28-RC001-REGISTRY-FREEZE-001": SCHEMA_PATH,
    "FIXTURE-T28-RC001-REGISTRY-FREEZE-001": FIXTURE_PATH,
    "MODULE-T28-RC001-REGISTRY-FREEZE-001": MODULE_PATH,
    "TEST-T28-RC001-REGISTRY-FREEZE-001": ROOT / "tests/test_task28_rc001_registry_freeze.py",
    "EVIDENCE-T28-A1-RC001-REGISTRY-FREEZE-001": ACCEPTANCE_PATH,
    "EVIDENCE-T28-A2-CATALOG-FACTORY-FIT-001": FACTORY_FIT_PATH,
}


def load_yaml(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_registries() -> dict[str, dict]:
    return {
        registry_type: yaml.safe_load(path.read_text(encoding="utf-8"))
        for registry_type, path in REGISTRY_PATHS.items()
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task28Rc001ContractTests(unittest.TestCase):
    def load_contract_artifacts(self) -> tuple[dict, dict, dict]:
        config = load_yaml(CONFIG_PATH)
        schema = load_json(SCHEMA_PATH)
        fixture = load_json(FIXTURE_PATH)
        self.assertIsNotNone(config, "RC-001 must have a versioned configuration")
        self.assertIsNotNone(schema, "RC-001 must have a versioned schema")
        self.assertIsNotNone(fixture, "RC-001 must have a golden fixture")
        assert config is not None
        assert schema is not None
        assert fixture is not None
        return config, schema, fixture

    def test_rc001_freeze_is_a_schema_valid_three_group_contract(self) -> None:
        """Catches a missing or broadened RC-001 experiment-family freeze."""
        config, schema, fixture = self.load_contract_artifacts()

        validator = Draft202012Validator(schema)
        self.assertFalse(list(validator.iter_errors(config)))
        self.assertEqual(
            [group["group_id"] for group in config["hypothesis_groups"]],
            fixture["expected_group_ids"],
        )
        self.assertEqual(
            config["global_search_policy"]["trial_record_creation"], "FORBIDDEN"
        )
        self.assertEqual(
            config["research_cycle"]["register_kind"],
            "TASK_OWNED_CONFIG_EVIDENCE",
        )

    def test_contract_rejects_promoted_authority_and_missingness_claims(self) -> None:
        """Catches removal of the no-authority and missingness guardrails."""
        config, schema, fixture = self.load_contract_artifacts()
        validator = Draft202012Validator(schema)
        cases = fixture["adversarial_cases"]
        self.assertEqual(len(cases), 4)

        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                candidate = copy.deepcopy(config)
                section, field = case["pointer"].lstrip("/").split("/")
                candidate[section][field] = case["replacement"]
                errors = list(validator.iter_errors(candidate))
                self.assertTrue(errors)
                self.assertTrue(
                    any(case["expected_error"] in error.json_path for error in errors),
                    errors,
                )


class Task28Rc001AdmissibilityTests(unittest.TestCase):
    def test_missing_history_blocks_liquidity_retention_before_any_trial(self) -> None:
        """Catches promotion of TASK-27's sparse panel into usable history."""
        config = load_yaml(CONFIG_PATH)
        self.assertIsNotNone(config)
        assert config is not None
        self.assertIsNotNone(
            evaluate_admissibility,
            "RC-001 must expose a deterministic offline admissibility evaluator",
        )
        assert evaluate_admissibility is not None

        result = evaluate_admissibility(config["hypothesis_groups"][1])

        self.assertEqual(result["state"], "BLOCKED_DATA")
        self.assertIn(
            "CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE", result["blocker_codes"]
        )


class Task28Rc001RegistryTests(unittest.TestCase):
    def test_task_owned_snapshot_preserves_legacy_skeletons_without_creating_a_trial(self) -> None:
        """Catches a TASK-28 freeze that rewrites TASK-16 history or starts research."""
        config = load_yaml(CONFIG_PATH)
        fixture = load_json(FIXTURE_PATH)
        self.assertIsNotNone(config)
        self.assertIsNotNone(fixture)
        assert config is not None
        assert fixture is not None
        assert validate_rc001_snapshot is not None
        registries = load_registries()

        validate_rc001_snapshot(config, registries)

        self.assertEqual(
            len(registries["global_trial_ledger"]["records"]),
            fixture["initial_global_trial_record_count"],
        )
        for registry_type in ("research_cycles", "hypotheses", "feature_catalog"):
            with self.subTest(registry_type=registry_type):
                self.assertEqual(registries[registry_type]["records"], [])
        self.assertFalse(config["research_cycle"]["trial_record_created"])
        self.assertFalse(config["research_cycle"]["holdout_consumed"])

    def test_ready_entity_veto_is_rejected_when_its_route_is_not_admissible(self) -> None:
        """Catches an unsafe READY promotion based on TASK-24's partial graph."""
        config = load_yaml(CONFIG_PATH)
        self.assertIsNotNone(config)
        assert config is not None
        self.assertIsNotNone(
            validate_rc001_snapshot,
            "RC-001 must validate the task-owned freeze against preserved lifecycle history",
        )
        assert validate_rc001_snapshot is not None

        candidate = copy.deepcopy(config)
        candidate["hypothesis_groups"][0]["expected_admissibility"]["state"] = "READY"

        with self.assertRaisesRegex(ValueError, "ENTITY_ROUTE_NOT_ADMISSIBLE"):
            validate_rc001_snapshot(candidate, load_registries())

    def test_definition_hash_changes_when_a_frozen_parameter_is_added(self) -> None:
        """Catches unversioned parameter expansion hidden inside a group definition."""
        config = load_yaml(CONFIG_PATH)
        self.assertIsNotNone(config)
        assert config is not None
        self.assertIsNotNone(canonical_definition_hash)
        assert canonical_definition_hash is not None

        original = config["hypothesis_groups"][1]
        expanded = copy.deepcopy(original)
        expanded["parameter_policy"]["allowed_parameter_ids"].append(
            "UNREGISTERED_POST_VALUE_PARAMETER"
        )

        self.assertNotEqual(
            canonical_definition_hash(original), canonical_definition_hash(expanded)
        )

    def test_unregistered_parameter_is_rejected_before_it_expands_a_group(self) -> None:
        """Catches a post-freeze parameter added without a registered definition."""
        config = load_yaml(CONFIG_PATH)
        self.assertIsNotNone(config)
        assert config is not None
        assert validate_rc001_snapshot is not None
        candidate = copy.deepcopy(config)
        candidate["hypothesis_groups"][1]["parameter_policy"][
            "allowed_parameter_ids"
        ].append("UNREGISTERED_POST_VALUE_PARAMETER")

        with self.assertRaisesRegex(ValueError, "UNREGISTERED_PARAMETER"):
            validate_rc001_snapshot(candidate, load_registries())

    def test_foreign_feature_is_rejected_without_a_versioned_registry_link(self) -> None:
        """Catches a new feature name smuggled into the task-owned frozen index."""
        config = load_yaml(CONFIG_PATH)
        self.assertIsNotNone(config)
        assert config is not None
        assert validate_rc001_snapshot is not None
        candidate = copy.deepcopy(config)
        candidate["hypothesis_groups"][2]["feature_id"] = "FEATURE-FOREIGN-UNBOUND-V1"

        with self.assertRaisesRegex(
            ValueError, "FOREIGN_FEATURE_WITHOUT_VERSIONED_LINK"
        ):
            validate_rc001_snapshot(candidate, load_registries())

    def test_trial_like_rc001_record_is_rejected_before_research_opens(self) -> None:
        """Catches a trial ledger entry created by a definition-only task."""
        config = load_yaml(CONFIG_PATH)
        self.assertIsNotNone(config)
        assert config is not None
        assert validate_rc001_snapshot is not None
        registries = load_registries()
        registries["global_trial_ledger"] = copy.deepcopy(
            registries["global_trial_ledger"]
        )
        registries["global_trial_ledger"]["records"].append(
            {
                "record_kind": "trial",
                "record_id": "TRIAL-RC001-FORBIDDEN-001",
                "status": "RECORDED",
                "created_at": "2026-08-09T00:00:00Z",
                "evidence_asset_ids": [],
                "hypothesis_id": config["hypothesis_groups"][0]["frozen_definition_id"],
                "outcome": "PENDING",
            }
        )

        with self.assertRaisesRegex(ValueError, "RC001_TRIAL_RECORD_FORBIDDEN"):
            validate_rc001_snapshot(config, registries)

    def test_duplicate_immutable_definition_id_is_rejected(self) -> None:
        """Catches two groups accidentally sharing one frozen task-owned identity."""
        config = load_yaml(CONFIG_PATH)
        self.assertIsNotNone(config)
        assert config is not None
        assert validate_rc001_snapshot is not None
        candidate = copy.deepcopy(config)
        candidate["hypothesis_groups"][2]["frozen_definition_id"] = candidate[
            "hypothesis_groups"
        ][1]["frozen_definition_id"]

        with self.assertRaisesRegex(ValueError, "DUPLICATE_IMMUTABLE_DEFINITION_ID"):
            validate_rc001_snapshot(candidate, load_registries())

    def test_legacy_skeleton_rewrite_is_rejected(self) -> None:
        """Catches synthetic RC-001 history added to TASK-16 skeletons."""
        config = load_yaml(CONFIG_PATH)
        self.assertIsNotNone(config)
        assert config is not None
        assert validate_rc001_snapshot is not None
        registries = load_registries()
        registries["hypotheses"] = copy.deepcopy(registries["hypotheses"])
        registries["hypotheses"]["records"].append(
            {"record_id": "HYP-RC001-SYNTHETIC-FORBIDDEN-001"}
        )

        with self.assertRaisesRegex(
            ValueError, "LEGACY_LIFECYCLE_SKELETON_REWRITE_FORBIDDEN"
        ):
            validate_rc001_snapshot(config, registries)


class Task28Rc001AcceptanceTests(unittest.TestCase):
    def test_acceptance_receipt_binds_frozen_artifacts_and_zero_external_actions(self) -> None:
        """Catches an unbound RC-001 freeze or a receipt that hides side effects."""
        receipt = load_json(ACCEPTANCE_PATH)
        self.assertIsNotNone(receipt, "RC-001 must retain an acceptance receipt")
        assert receipt is not None

        expected_bindings = {
            "contract": CONTRACT_PATH,
            "config": CONFIG_PATH,
            "schema": SCHEMA_PATH,
            "fixture": FIXTURE_PATH,
            "validator": MODULE_PATH,
            **{f"registry:{name}": path for name, path in REGISTRY_PATHS.items()},
            **{f"known_evidence:{name}": path for name, path in KNOWN_EVIDENCE_PATHS.items()},
        }
        self.assertEqual(receipt["schema"], "smial.task28.rc001-registry-freeze.acceptance")
        self.assertEqual(receipt["task_id"], "TASK-28")
        self.assertEqual(
            receipt["artifact_bindings"],
            {
                name: {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                }
                for name, path in expected_bindings.items()
            },
        )
        self.assertEqual(receipt["decision"]["trial_record_created"], False)
        self.assertEqual(receipt["decision"]["holdout_consumed"], False)
        self.assertEqual(receipt["side_effect_counters"], {
            "provider_api_rpc_wss_calls": 0,
            "credential_uses": 0,
            "r2_r3_reads": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd_cents": 0,
            "dependency_changes": 0,
            "project_sources_changes": 0,
        })


class Task28CatalogFactoryFitTests(unittest.TestCase):
    def test_catalog_registers_task28_outputs_and_factory_fit_remains_offline(self) -> None:
        """Catches unregistered control artifacts or a Factory Fit receipt with side effects."""
        core = load_yaml(CATALOG_CORE_PATH)
        receipt = load_json(FACTORY_FIT_PATH)
        self.assertIsNotNone(core)
        self.assertIsNotNone(receipt, "TASK-28 must retain a Factory Fit receipt")
        assert core is not None
        assert receipt is not None
        assets = {record["asset_id"]: record for record in core["records"]}

        self.assertTrue(set(TASK28_REQUIRED_ASSET_PATHS).issubset(assets))
        for asset_id, path in TASK28_REQUIRED_ASSET_PATHS.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(
                    assets[asset_id]["location"]["repository_path"],
                    path.relative_to(ROOT).as_posix(),
                )
                self.assertEqual(assets[asset_id]["integrity"]["sha256"], sha256(path))

        self.assertEqual(receipt["factory_fit"]["mode"], "FULL_REVIEW")
        self.assertEqual(receipt["factory_fit"]["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(receipt["side_effect_counters"]["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(receipt["side_effect_counters"]["wallet_signer_transaction_actions"], 0)


if __name__ == "__main__":
    unittest.main()
