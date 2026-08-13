from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/delivery_harness.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("delivery_harness_bootstrap", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("delivery harness script is not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeliveryHarnessBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_preview_is_zero_write_and_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            before = list(target.rglob("*"))
            plan = self.module.plan_initialization(target, ROOT)
            self.assertEqual(list(target.rglob("*")), before)
            self.assertEqual(plan["decision"], "APPLY_ALLOWED")
            self.assertTrue(plan["plan_sha256"])
            self.assertTrue(plan["creates"])
            receipt = self.module.apply_initialization(target, plan)
            self.assertEqual(receipt["decision"], "APPLIED")
            self.assertEqual(receipt["plan_sha256"], plan["plan_sha256"])
            second = self.module.plan_initialization(target, ROOT)
            self.assertTrue(second["idempotent"])
            self.assertEqual(second["creates"], [])
            self.assertEqual(second["replaces"], [])
            self.assertEqual(second["removes"], [])

    def test_conflicting_target_refuses_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            conflict = target / "delivery-harness/project-profile.yaml"
            conflict.parent.mkdir(parents=True)
            conflict.write_text("user-owned: true\n", encoding="utf-8")
            before = conflict.read_bytes()
            plan = self.module.plan_initialization(target, ROOT)
            self.assertEqual(plan["decision"], "CONFLICT_REFUSAL")
            with self.assertRaisesRegex(ValueError, "INITIALIZATION_NOT_ALLOWED"):
                self.module.apply_initialization(target, plan)
            self.assertEqual(conflict.read_bytes(), before)

    def test_plan_drift_refuses_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            plan = self.module.plan_initialization(target, ROOT)
            drift = target / "delivery-harness/project-profile.yaml"
            drift.parent.mkdir(parents=True)
            drift.write_text("drift: true\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PLAN_DRIFT"):
                self.module.apply_initialization(target, plan)

    def test_global_or_unsafe_target_is_rejected(self) -> None:
        for relative in (".cursor", ".codex", ".agents"):
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / relative
                target.mkdir()
                with self.assertRaisesRegex(ValueError, "GLOBAL_CONFIG_TARGET_FORBIDDEN"):
                    self.module.plan_initialization(target, ROOT)

    def test_portable_output_has_no_solana_specific_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            plan = self.module.plan_initialization(target, ROOT)
            self.module.apply_initialization(target, plan)
            text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in target.rglob("*")
                if path.is_file()
            ).casefold()
            for forbidden in (
                "solana",
                "lancerbeta",
                "task-30",
                "helius",
                "wallet",
            ):
                self.assertNotIn(forbidden, text)

    def test_bootstrap_prompt_is_exact_current_repo_entrypoint(self) -> None:
        prompt = (
            ROOT / "delivery-harness/templates/bootstrap-prompt.md"
        ).read_text(encoding="utf-8")
        self.assertIn("https://github.com/lancerbeta/solana-alpha-lab", prompt)
        self.assertIn("DELIVERY_HARNESS_BOOTSTRAP=PASS", prompt)
        self.assertIn("DELIVERY_HARNESS_BOOTSTRAP=BLOCKED:", prompt)
        self.assertIn("one repository or worktree root", prompt)
        self.assertNotIn("search latest", prompt.casefold())
        self.assertNotIn("install plugin", prompt.casefold())


if __name__ == "__main__":
    unittest.main()
