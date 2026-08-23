from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/delivery_harness.py"
PROFILE = ROOT / "delivery-harness/project-profile.yaml"
SCHEMA = ROOT / "catalog/schemas/delivery_harness_project_profile.schema.json"
TASK_CONTRACT = "docs/tasks/CTRL-DELIVERY-HARNESS-V1.md"
TASK_ID = "CTRL-DELIVERY-HARNESS-V1"
READINESS = "configs/factory_v1_operational_readiness_v1.yaml"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "delivery_harness_readiness_bind", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise AssertionError("delivery harness script is not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FactoryV1ReadinessProfileBindTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))

    def frozen_task_git_text(self):
        metadata = self.module.parse_task_contract(ROOT, TASK_CONTRACT, TASK_ID)
        binding = metadata["git_binding"]
        values = {
            ("rev-parse", "HEAD"): "a" * 40,
            ("rev-parse", "HEAD^{tree}"): "b" * 40,
            ("branch", "--show-current"): binding["expected_branch"],
            ("status", "--porcelain=v1"): "",
            ("remote", "get-url", "origin"): (
                f"git@github.com:{metadata['expected_repository']}.git"
            ),
            ("merge-base", "HEAD", binding["expected_upstream"]): binding[
                "expected_base"
            ],
            ("rev-parse", binding["expected_upstream"]): binding[
                "expected_upstream_oid"
            ],
        }

        def respond(_root: Path, *args: str) -> str:
            if args not in values:
                raise AssertionError(f"unexpected git fixture call: {args!r}")
            return values[args]

        return metadata, respond

    def test_schema_admits_exact_binding_and_rejects_other_paths(self) -> None:
        live = copy.deepcopy(self.profile)
        jsonschema.validate(live, self.schema)
        live["factory_v1_readiness_contract"] = "configs/other.yaml"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(live, self.schema)

    def test_bound_profile_names_readiness_contract(self) -> None:
        self.assertEqual(self.profile["factory_v1_readiness_contract"], READINESS)

    def test_live_check_passes_with_bound_readiness_contract(self) -> None:
        readiness = yaml.safe_load(
            (ROOT / READINESS).read_text(encoding="utf-8")
        )
        self.assertTrue(
            readiness["domain_policy_integration"]["entry_gate_resolves_this_file"]
        )
        self.assertEqual(
            readiness["domain_policy_integration"]["live_invariant_owner"],
            "scripts/delivery_harness.py",
        )
        result = self.module.check_harness(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["delivery_gate_ready"])
        self.assertNotIn("FACTORY_V1_READINESS_CONTRACT_UNRESOLVED", result["errors"])
        self.assertNotIn("FACTORY_V1_READINESS_CONTRACT_MISSING", result["errors"])
        self.assertNotIn("FACTORY_V1_READINESS_CONTRACT_OWNER_MISMATCH", result["errors"])

    def test_unbound_profile_is_not_required(self) -> None:
        self.assertEqual(
            self.module.factory_v1_readiness_contract_errors(ROOT, {}),
            [],
        )
        self.assertEqual(
            self.module.factory_v1_readiness_contract_errors(
                ROOT, {"factory_v1_readiness_contract": None}
            ),
            [],
        )

    def test_wrong_path_missing_file_and_invalid_mapping_fail_closed(self) -> None:
        self.assertEqual(
            self.module.factory_v1_readiness_contract_errors(
                ROOT, {"factory_v1_readiness_contract": "configs/other.yaml"}
            ),
            ["FACTORY_V1_READINESS_CONTRACT_PATH_MISMATCH"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = self.module.factory_v1_readiness_contract_errors(
                root, {"factory_v1_readiness_contract": READINESS}
            )
            self.assertEqual(missing, ["FACTORY_V1_READINESS_CONTRACT_MISSING"])
            yaml_path = root / READINESS
            yaml_path.parent.mkdir(parents=True)
            yaml_path.write_text("- not-a-mapping\n", encoding="utf-8")
            invalid = self.module.factory_v1_readiness_contract_errors(
                root, {"factory_v1_readiness_contract": READINESS}
            )
            self.assertEqual(invalid, ["FACTORY_V1_READINESS_CONTRACT_INVALID"])
            yaml_path.write_text("schema: only\n", encoding="utf-8")
            unresolved = self.module.factory_v1_readiness_contract_errors(
                root, {"factory_v1_readiness_contract": READINESS}
            )
            self.assertEqual(unresolved, ["FACTORY_V1_READINESS_CONTRACT_UNRESOLVED"])

    def test_present_wrong_owner_fails_and_false_flag_does_not(self) -> None:
        profile = {"factory_v1_readiness_contract": READINESS}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            yaml_path = root / READINESS
            yaml_path.parent.mkdir(parents=True)
            yaml_path.write_text(
                "domain_policy_integration:\n"
                "  entry_gate_resolves_this_file: false\n"
                "  live_invariant_owner: scripts/other.py\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module.factory_v1_readiness_contract_errors(root, profile),
                ["FACTORY_V1_READINESS_CONTRACT_OWNER_MISMATCH"],
            )
            yaml_path.write_text(
                "domain_policy_integration:\n"
                "  entry_gate_resolves_this_file: false\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module.factory_v1_readiness_contract_errors(root, profile),
                [],
            )

    def test_check_harness_propagates_helper_errors(self) -> None:
        with mock.patch.object(
            self.module,
            "factory_v1_readiness_contract_errors",
            return_value=["FACTORY_V1_READINESS_CONTRACT_MISSING"],
        ) as helper:
            result = self.module.check_harness(ROOT)
        helper.assert_called()
        self.assertIn("FACTORY_V1_READINESS_CONTRACT_MISSING", result["errors"])
        self.assertNotEqual(result["status"], "PASS")

    def test_task_context_selects_bound_readiness_file(self) -> None:
        _metadata, git_text = self.frozen_task_git_text()
        with mock.patch.object(self.module, "git_text", side_effect=git_text):
            receipt = self.module.build_context_receipt(
                ROOT,
                task_id=TASK_ID,
                task_contract=TASK_CONTRACT,
                route="DIRECT_CURSOR_DELIVERY",
            )
        paths = [
            item.get("path")
            for item in receipt.get("selected", [])
            if isinstance(item, dict)
        ]
        self.assertIn(READINESS, paths)
        selected = next(
            item
            for item in receipt["selected"]
            if item.get("path") == READINESS
        )
        self.assertEqual(selected["semantic_role"], "MISSION_AND_INVARIANTS")
        self.assertEqual(selected["stable_id"], "CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001")


if __name__ == "__main__":
    unittest.main()
