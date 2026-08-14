from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
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
            check = self.module.check_harness(target)
            self.assertEqual(check["status"], "PASS", check)

    def test_profile_is_consumed_and_missing_profile_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "PORTABLE_PROFILE_NOT_FOUND"):
                self.module.plan_initialization(
                    target, ROOT, profile_path="delivery-harness/templates/missing.yaml"
                )

    def test_installed_portable_cli_runs_check_and_exact_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Harness Test"], cwd=target, check=True)
            subprocess.run(["git", "config", "user.email", "harness@example.invalid"], cwd=target, check=True)
            marker = target / "README.md"
            marker.write_text("portable target\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=target, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=target, check=True, capture_output=True)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=target, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=target, check=True,
                capture_output=True, text=True,
            ).stdout.strip()

            plan = self.module.plan_initialization(target, ROOT)
            self.module.apply_initialization(target, plan)
            task = target / "docs/tasks/PORTABLE-TEST.md"
            task.parent.mkdir(parents=True)
            task.write_text(
                "---\n"
                "task_id: PORTABLE-TEST\n"
                "task_version: '1.0'\n"
                "status: READY\n"
                "as_of: '2026-08-14'\n"
                "owner: GOAL_OWNER\n"
                "allowed_routes: [DIRECT_CURSOR_DELIVERY, DIRECT_CODEX_DELIVERY]\n"
                "expected_repository: example/project\n"
                "git_binding:\n"
                f"  expected_base: {head}\n"
                "  expected_upstream: HEAD\n"
                f"  expected_upstream_oid: {head}\n"
                f"  expected_branch: {branch}\n"
                "  dirty_mode: ALLOW_REPORTED\n"
                "objective: Prove the installed portable harness runs from exact Git task context.\n"
                "managed_write_set: [docs/tasks/PORTABLE-TEST.md]\n"
                "external_caps: {network: false, credentials: false, external_system: false, signing_or_financial_action: false, cash_spend: false, deployment: false}\n"
                "stop_conditions: [TASK_SCOPE_DRIFT]\n"
                "context_requirements: {catalog_asset_ids: [], l2_roles: [], l3_roles: [], roadmap_path: null, exact_evidence_paths: [], exact_registry_paths: []}\n"
                "---\n\n# Portable test\n",
                encoding="utf-8",
            )
            script = target / "scripts/delivery_harness.py"
            checked = subprocess.run(
                [sys.executable, str(script), "check", "--root", str(target)],
                cwd=target, check=True, capture_output=True, text=True,
            )
            self.assertEqual(json.loads(checked.stdout)["status"], "PASS")
            projected = subprocess.run(
                [
                    sys.executable, str(script), "context", "--root", str(target),
                    "--task-id", "PORTABLE-TEST", "--contract", "docs/tasks/PORTABLE-TEST.md",
                    "--route", "DIRECT_CURSOR_DELIVERY",
                ],
                cwd=target, check=True, capture_output=True, text=True,
            )
            receipt = json.loads(projected.stdout)
            self.assertEqual(receipt["task"]["task_id"], "PORTABLE-TEST")
            self.assertEqual(receipt["repository"]["head"], head)
            self.assertEqual(receipt["cloud_bundle_mode"], "OWNER_MANAGED_OPTIONAL_EXPORT")
            self.assertRegex(receipt["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_plan_is_bound_to_target_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first"
            second = Path(directory) / "second"
            first.mkdir()
            second.mkdir()
            for target in (first, second):
                subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
            plan = self.module.plan_initialization(first, ROOT)
            with self.assertRaisesRegex(ValueError, "INITIALIZATION_TARGET_MISMATCH"):
                self.module.apply_initialization(second, plan)

    def test_nested_cursor_or_agent_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "project"
            nested = repo / ".cursor/rules"
            nested.mkdir(parents=True)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "GLOBAL_CONFIG_TARGET_FORBIDDEN"):
                self.module.plan_initialization(nested, ROOT)

    def test_conflicting_target_refuses_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
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
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
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
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
            plan = self.module.plan_initialization(target, ROOT)
            self.module.apply_initialization(target, plan)
            text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in target.rglob("*")
                if path.is_file() and ".git" not in path.relative_to(target).parts
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
