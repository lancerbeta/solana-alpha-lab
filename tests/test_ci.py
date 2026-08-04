from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ci = load_module("validate_ci", "scripts/validate_ci.py")
secret_scan = load_module("secret_scan_for_ci", "scripts/secret_scan.py")
SKIP_CALL_TEXT = "self." + "skip" + "Test"


class CiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    def assert_invalid(self, text: str) -> None:
        with self.assertRaises(ci.CiValidationError):
            ci.validate_workflow_text(text)

    def test_exact_workflow_contract_passes(self) -> None:
        ci.validate_workflow_text(self.text)

    def test_action_pins_and_linux_checksum_are_exact(self) -> None:
        self.assertIn(ci.CHECKOUT_PIN, self.text)
        self.assertIn(ci.SETUP_UV_PIN, self.text)
        self.assertIn(ci.LINUX_UV_CHECKSUM, self.text)
        self.assertIn('version: "0.11.29"', self.text)

    def test_permissions_checkout_cache_trigger_and_limits_are_exact(self) -> None:
        document = yaml.load(self.text, Loader=yaml.BaseLoader)
        self.assertEqual(document["permissions"], {"contents": "read"})
        self.assertEqual(
            document["on"],
            {
                "pull_request": {"branches": ["main"]},
                "push": {"branches": ["main"]},
            },
        )
        job = document["jobs"]["validate"]
        self.assertEqual(job["timeout-minutes"], "10")
        self.assertEqual(job["concurrency"] if "concurrency" in job else None, None)
        self.assertEqual(document["concurrency"]["cancel-in-progress"], "true")
        self.assertEqual(
            job["steps"][0]["with"],
            {"persist-credentials": "false", "fetch-depth": "0"},
        )
        self.assertEqual(job["steps"][1]["with"]["enable-cache"], "false")
        self.assertEqual(
            job["steps"][2],
            {
                "name": "Configure local hooks",
                "run": "git config --local core.hooksPath .githooks",
            },
        )

    def test_tag_based_action_reference_fails(self) -> None:
        self.assert_invalid(self.text.replace(ci.CHECKOUT_PIN, "actions/checkout@v7"))

    def test_extra_action_fails(self) -> None:
        addition = "\n      - name: Extra\n        uses: example/action@" + ("a" * 40)
        self.assert_invalid(self.text + addition + "\n")

    def test_forbidden_secrets_permissions_and_triggers_fail(self) -> None:
        mutations = (
            self.text + "\n# " + "secr" + "ets.REPOSITORY_TOKEN\n",
            self.text.replace("contents: read", "contents: write"),
            self.text.replace("push:\n", "pull_request_target:\n"),
            self.text.replace("push:\n", "workflow_dispatch:\n"),
            self.text.replace("contents: read", "contents: read\n  id-token: write"),
        )
        for mutation in mutations:
            with self.subTest():
                self.assert_invalid(mutation)

    def test_checkout_cache_timeout_and_concurrency_drift_fail(self) -> None:
        mutations = (
            self.text.replace("persist-credentials: false", "persist-credentials: true"),
            self.text.replace("fetch-depth: 0", "fetch-depth: 1"),
            self.text.replace("enable-cache: false", "enable-cache: true"),
            self.text.replace(
                "git config --local core.hooksPath .githooks",
                "git config --global core.hooksPath .githooks",
            ),
            self.text.replace(
                "git config --local core.hooksPath .githooks\n",
                "",
            ),
            self.text.replace("timeout-minutes: 10\n", ""),
            self.text.replace("cancel-in-progress: true", "cancel-in-progress: false"),
        )
        for mutation in mutations:
            with self.subTest():
                self.assert_invalid(mutation)


class CleanCloneDocumentationTests(unittest.TestCase):
    def test_clean_clone_is_attached_exact_and_hooks_configured(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        clone = (
            "git clone --branch main --single-branch "
            "<PRIVATE_REPOSITORY_URL> <BOUNDED_LOCAL_DIRECTORY>"
        )
        head_check = "git show -s --format=%H HEAD"
        hooks = "git config --local core.hooksPath .githooks"
        validation = ci.VALIDATION_COMMAND
        self.assertIn(clone, text)
        self.assertNotIn("git checkout --detach", text)
        self.assertLess(text.index(head_check), text.index(hooks))
        self.assertLess(text.index(hooks), text.index(validation, text.index(hooks)))
        self.assertIn(
            "must equal `<AUTHORIZED_COMMIT_SHA>` exactly",
            text,
        )
        self.assertIn("Keep `main` attached to `origin/main`", text)


class TrackedOnlyDeliveryPreflightTests(unittest.TestCase):
    def test_agents_contract_selects_one_delivery_only_gate(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## TRACKED_ONLY_DELIVERY_PREFLIGHT", text)
        self.assertIn(ci.DELIVERY_PREFLIGHT_COMMAND, text)
        self.assertIn("wall-time cap is 15 minutes", text)
        self.assertIn("copies no untracked or ignored inputs", text)
        self.assertIn("not an implementation-loop or per-atom hook", text)

    def test_new_skip_without_tracked_noncritical_proof_fails(self) -> None:
        diff = f"""\
diff --git a/tests/test_example.py b/tests/test_example.py
--- a/tests/test_example.py
+++ b/tests/test_example.py
@@ -1,2 +1,4 @@
 class Example:
+    def test_raw(self):
+        {SKIP_CALL_TEXT}("ignored local raw input is unavailable")
"""
        with self.assertRaisesRegex(
            ci.CiValidationError,
            "delivery_new_skip_policy_failed",
        ):
            ci.validate_new_test_skip_policy(
                diff,
                proof_exists=lambda _path: False,
            )

    def test_adjacent_tracked_noncritical_proof_is_explicit(self) -> None:
        proof = "docs/decisions/noncritical-clean-checkout.md"
        diff = f"""\
diff --git a/tests/test_example.py b/tests/test_example.py
--- a/tests/test_example.py
+++ b/tests/test_example.py
@@ -1,2 +1,5 @@
 class Example:
+    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: {proof}
+    def test_optional(self):
+        {SKIP_CALL_TEXT}("optional external observation")
"""
        self.assertEqual(
            ci.validate_new_test_skip_policy(
                diff,
                proof_exists=lambda path: path == proof,
            ),
            [{"test_path": "tests/test_example.py", "proof_path": proof}],
        )

    def test_invalid_or_untracked_skip_proof_fails_closed(self) -> None:
        diff = f"""\
diff --git a/tests/test_example.py b/tests/test_example.py
--- a/tests/test_example.py
+++ b/tests/test_example.py
@@ -1,2 +1,5 @@
 class Example:
+    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: ../../local/raw.md
+    def test_optional(self):
+        {SKIP_CALL_TEXT}("optional external observation")
"""
        with self.assertRaisesRegex(ci.CiValidationError, "invalid_skip_proof"):
            ci.validate_new_test_skip_policy(
                diff,
                proof_exists=lambda _path: True,
            )

    def test_validation_summary_preserves_skip_and_missing_input_evidence(self) -> None:
        summary = ci.parse_validation_summary(
            """\
REPOSITORY_POLICY: PASS
Ran 1626 tests in 4.2s
OK (skipped=61)
test_raw skipped 'ignored local A3 raw population is unavailable'
RESULT: PASS
"""
        )
        self.assertEqual(summary["tests_run"], 1626)
        self.assertEqual(summary["skipped"], 61)
        self.assertEqual(summary["pass_labels"], 2)
        self.assertEqual(
            summary["missing_local_inputs"],
            ["ignored local A3 raw population is unavailable"],
        )
        self.assertEqual(summary["failure_diagnostics"], [])

    def test_validation_summary_bounds_failure_diagnostics(self) -> None:
        summary = ci.parse_validation_summary(
            """\
FAIL: test_exact_contract (test_example.ExampleTests.test_exact_contract)
AssertionError: expected immutable receipt bytes
FAILED (failures=1)
"""
        )
        self.assertEqual(
            summary["failure_diagnostics"],
            [
                "FAIL: test_exact_contract (test_example.ExampleTests.test_exact_contract)",
                "AssertionError: expected immutable receipt bytes",
                "FAILED (failures=1)",
            ],
        )

    def test_delivery_mode_is_opt_in_and_base_ref_is_explicit(self) -> None:
        ordinary = ci.parse_args([])
        delivery = ci.parse_args(
            ["--tracked-only-delivery", "--base-ref", "origin/main"]
        )
        self.assertFalse(ordinary.tracked_only_delivery)
        self.assertTrue(delivery.tracked_only_delivery)
        self.assertEqual(delivery.base_ref, "origin/main")

    def test_tracked_only_clone_is_normalized_to_attached_main(self) -> None:
        calls: list[list[str]] = []
        original = ci.git_text

        def recorder(arguments: list[str], *, cwd: Path | None = None) -> str:
            self.assertEqual(cwd, Path("synthetic-checkout"))
            calls.append(arguments)
            if arguments == [
                "for-each-ref",
                "--format=%(refname)",
                "refs/remotes/origin",
            ]:
                return "\n".join(
                    [
                        "refs/remotes/origin/HEAD",
                        "refs/remotes/origin/main",
                        "refs/remotes/origin/owner-authority-packet-binding-impl",
                    ]
                )
            return ""

        ci.git_text = recorder
        try:
            ci.normalize_tracked_only_checkout(
                branch="owner-authority-packet-binding-impl",
                checkout=Path("synthetic-checkout"),
            )
        finally:
            ci.git_text = original

        self.assertEqual(
            calls,
            [
                [
                    "for-each-ref",
                    "--format=%(refname)",
                    "refs/remotes/origin",
                ],
                ["branch", "-m", "main"],
                ["branch", "--set-upstream-to=origin/main", "main"],
                ["update-ref", "-d", "refs/remotes/origin/HEAD"],
                [
                    "update-ref",
                    "-d",
                    "refs/remotes/origin/owner-authority-packet-binding-impl",
                ],
            ],
        )


class PlatformGateContractTests(unittest.TestCase):
    def test_python_and_uv_mismatch_fail(self) -> None:
        with self.assertRaises(ci.CiValidationError):
            ci.validate_python_version((3, 13, 13))
        with self.assertRaises(ci.CiValidationError):
            ci.validate_uv_version("uv 0.11.28")

    def test_uv_lock_mutation_fails(self) -> None:
        with self.assertRaises(ci.CiValidationError):
            ci.assert_lock_unchanged(b"before", b"after")

    def test_fake_secret_fixture_rejected_and_clean_fixture_passes(self) -> None:
        self.assertEqual(secret_scan.run_self_test(), [])
        self.assertEqual(secret_scan.findings_for_text("API_KEY=\n"), [])

    def test_gate_runs_required_catalog_generated_and_repository_checks(self) -> None:
        commands = {label: command for label, command in ci.child_commands()}
        self.assertIn("scripts/secret_scan.py", commands["SECRET_REJECTION"])
        self.assertIn("scripts/validate_catalog.py", commands["CATALOG_VALIDATION"])
        self.assertIn("scripts/generate_navigation.py", commands["GENERATED_NAVIGATION"])
        self.assertIn("--check", commands["GENERATED_NAVIGATION"])
        self.assertIn("scripts/validate_task04.py", commands["TASK04_ARCHITECTURE"])
        self.assertIn("scripts/validate_baseline.py", commands["REPOSITORY_POLICY"])

    def test_child_failure_is_propagated(self) -> None:
        def failing_runner(*_args, **_kwargs):
            return subprocess.CompletedProcess([], 7, "", "")

        with self.assertRaisesRegex(ci.CiValidationError, "synthetic_failed:7"):
            ci.run_checked("SYNTHETIC", ["synthetic"], runner=failing_runner)

    def test_project_contract_requires_exact_pins(self) -> None:
        document = {
            "tool": {
                "uv": {"required-version": "==0.11.29"},
                "solana-alpha-lab": {"exact_python_pin": "3.13.14"},
            }
        }
        ci.validate_project_contract(document)
        changed = copy.deepcopy(document)
        changed["tool"]["uv"]["required-version"] = "==0.11.28"
        with self.assertRaises(ci.CiValidationError):
            ci.validate_project_contract(changed)


if __name__ == "__main__":
    unittest.main()
