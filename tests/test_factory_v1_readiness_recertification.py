from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.operational_readiness_closeout import (  # noqa: E402
    evaluate_closeout,
)

SCRIPT = ROOT / "scripts/delivery_harness.py"
READINESS = ROOT / "configs/factory_v1_operational_readiness_v1.yaml"
PROFILE = ROOT / "delivery-harness/project-profile.yaml"


def load_harness():
    spec = importlib.util.spec_from_file_location("delivery_harness", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("delivery harness import unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FactoryV1ReadinessRecertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_harness()

    def test_bound_profile_names_readiness_contract(self) -> None:
        profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(
            profile["factory_v1_readiness_contract"],
            "configs/factory_v1_operational_readiness_v1.yaml",
        )

    def test_check_harness_resolves_live_readiness_contract(self) -> None:
        result = self.module.check_harness(ROOT)
        self.assertTrue(result["delivery_gate_ready"])
        self.assertNotIn("FACTORY_V1_READINESS_CONTRACT_UNRESOLVED", result["errors"])
        self.assertNotIn("FACTORY_V1_READINESS_CONTRACT_MISSING", result["errors"])
        self.assertNotIn("FACTORY_V1_READINESS_CONTRACT_OWNER_MISMATCH", result["errors"])

    def test_check_harness_propagates_false_flag_from_readiness_helper(self) -> None:
        with mock.patch.object(
            self.module,
            "factory_v1_readiness_contract_errors",
            return_value=["FACTORY_V1_READINESS_CONTRACT_UNRESOLVED"],
        ) as helper:
            result = self.module.check_harness(ROOT)
        helper.assert_called()
        self.assertIn("FACTORY_V1_READINESS_CONTRACT_UNRESOLVED", result["errors"])
        self.assertNotEqual(result["status"], "PASS")

    def test_live_context_selects_bound_readiness_contract(self) -> None:
        receipt = self.module.build_context_receipt(
            ROOT,
            task_id="FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1",
            task_contract="docs/tasks/FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1.md",
            route="DIRECT_CURSOR_DELIVERY",
        )
        paths = [
            item.get("path")
            for item in receipt.get("selected", [])
            if isinstance(item, dict)
        ]
        self.assertIn("configs/factory_v1_operational_readiness_v1.yaml", paths)

    def test_false_flag_fails_check_independently_of_closeout_yaml(self) -> None:
        profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            yaml_path = root / "configs/factory_v1_operational_readiness_v1.yaml"
            yaml_path.parent.mkdir(parents=True)
            yaml_path.write_text(
                "domain_policy_integration:\n"
                "  entry_gate_resolves_this_file: false\n"
                "  live_invariant_owner: scripts/delivery_harness.py\n",
                encoding="utf-8",
            )
            errors = self.module.factory_v1_readiness_contract_errors(root, profile)
            self.assertIn("FACTORY_V1_READINESS_CONTRACT_UNRESOLVED", errors)

    def test_true_flag_without_owner_fails_check(self) -> None:
        profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            yaml_path = root / "configs/factory_v1_operational_readiness_v1.yaml"
            yaml_path.parent.mkdir(parents=True)
            yaml_path.write_text(
                "domain_policy_integration:\n"
                "  entry_gate_resolves_this_file: true\n",
                encoding="utf-8",
            )
            errors = self.module.factory_v1_readiness_contract_errors(root, profile)
            self.assertIn("FACTORY_V1_READINESS_CONTRACT_OWNER_MISMATCH", errors)

    def test_portable_profile_without_binding_is_not_required(self) -> None:
        errors = self.module.factory_v1_readiness_contract_errors(
            ROOT, {"bindings": {}}
        )
        self.assertEqual(errors, [])

    def test_live_closeout_is_ready_and_frozen(self) -> None:
        gate = evaluate_closeout(ROOT)
        self.assertEqual(gate["terminal"], "FACTORY_V1_OPERATIONAL_READY")
        self.assertTrue(gate["factory_v1_operational_ready"])
        self.assertEqual(gate["foundation_freeze"], "ACTIVE")
        self.assertEqual(gate["named_gaps"], [])


if __name__ == "__main__":
    unittest.main()
