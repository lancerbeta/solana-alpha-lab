from __future__ import annotations

import copy
import contextlib
import importlib.util
import io
import os
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

    def test_parameterless_manual_dispatch_is_admitted(self) -> None:
        candidate = self.text.replace(
            "  pull_request:\n",
            "  workflow_dispatch:\n  pull_request:\n",
        )
        ci.validate_workflow_text(candidate)

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
                "workflow_dispatch": "",
                "pull_request": {"branches": ["main"]},
                "push": {"branches": ["main"]},
            },
        )
        self.assertEqual(
            set(document["jobs"]),
            {"validate-core", "validate-execution", "validate-tests", "validate"},
        )
        core = document["jobs"]["validate-core"]
        execution = document["jobs"]["validate-execution"]
        tests = document["jobs"]["validate-tests"]
        final = document["jobs"]["validate"]
        self.assertEqual(
            core["timeout-minutes"],
            str(ci.GITHUB_VALIDATE_TIMEOUT_MINUTES),
        )
        self.assertEqual(
            tests["timeout-minutes"],
            str(ci.GITHUB_VALIDATE_TIMEOUT_MINUTES),
        )
        self.assertEqual(
            final["timeout-minutes"],
            str(ci.GITHUB_AGGREGATOR_TIMEOUT_MINUTES),
        )
        self.assertEqual(
            ci.DELIVERY_PREFLIGHT_TIMEOUT_SECONDS,
            ci.DELIVERY_PREFLIGHT_TIMEOUT_MINUTES * 60,
        )
        self.assertEqual(core.get("concurrency"), None)
        self.assertEqual(document["concurrency"]["cancel-in-progress"], "true")
        self.assertEqual(tests["strategy"]["fail-fast"], "false")
        self.assertEqual(final["if"], "${{ always() }}")
        self.assertEqual(
            final["needs"],
            ["validate-core", "validate-execution", "validate-tests"],
        )
        self.assertEqual(execution["needs"], ["validate-core"])
        self.assertNotIn("needs", tests)
        self.assertEqual(
            core["steps"][0]["with"],
            {"persist-credentials": "false", "fetch-depth": "0"},
        )
        self.assertEqual(core["steps"][1]["with"]["enable-cache"], "false")
        self.assertEqual(
            core["steps"][2],
            {
                "name": "Configure local hooks",
                "run": "git config --local core.hooksPath .githooks",
            },
        )
        self.assertIn("--core-only", core["steps"][3]["run"])
        self.assertIn("run_ci_execution_domain.py", execution["steps"][3]["run"])
        self.assertIn("run_ci_test_shard.py", tests["steps"][3]["run"])
        self.assertIn("--reserved-manifest", tests["steps"][3]["run"])
        self.assertIn("AGGREGATOR_DENY", final["steps"][0]["run"])

    def test_tag_based_action_reference_fails(self) -> None:
        self.assert_invalid(self.text.replace(ci.CHECKOUT_PIN, "actions/checkout@v7"))

    def test_extra_action_fails(self) -> None:
        addition = "\n      - name: Extra\n        uses: example/action@" + ("a" * 40)
        self.assert_invalid(self.text + addition + "\n")

    def test_forbidden_secrets_permissions_and_triggers_fail(self) -> None:
        mutations = (
            self.text + "\n# " + "secr" + "ets.REPOSITORY_TOKEN\n",
            self.text.replace("contents: read", "contents: write", 1),
            self.text.replace("push:\n", "pull_request_target:\n", 1),
            self.text.replace(
                "  workflow_dispatch:\n",
                "  workflow_dispatch:\n    inputs:\n      branch:\n        description: forbidden\n",
                1,
            ),
            self.text.replace(
                "contents: read\n",
                "contents: read\n  id-token: write\n",
                1,
            ),
        )
        for mutation in mutations:
            with self.subTest():
                self.assert_invalid(mutation)

    def test_checkout_cache_timeout_and_concurrency_drift_fail(self) -> None:
        mutations = (
            self.text.replace(
                "persist-credentials: false",
                "persist-credentials: true",
                1,
            ),
            self.text.replace("fetch-depth: 0", "fetch-depth: 1", 1),
            self.text.replace("enable-cache: false", "enable-cache: true", 1),
            self.text.replace(
                "git config --local core.hooksPath .githooks",
                "git config --global core.hooksPath .githooks",
                1,
            ),
            self.text.replace(
                "git config --local core.hooksPath .githooks\n",
                "",
                1,
            ),
            self.text.replace(
                f"timeout-minutes: {ci.GITHUB_VALIDATE_TIMEOUT_MINUTES}\n",
                "timeout-minutes: 99\n",
                1,
            ),
            self.text.replace("cancel-in-progress: true", "cancel-in-progress: false", 1),
            self.text.replace("fail-fast: false", "fail-fast: true", 1),
            self.text.replace("if: ${{ always() }}", "if: success()", 1),
        )
        for mutation in mutations:
            with self.subTest():
                self.assert_invalid(mutation)

    def _aggregator_script_body(self) -> str:
        return ci.AGGREGATOR_DENY_SCRIPT.split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]

    def test_aggregator_denies_non_success_dependency_results(self) -> None:
        script = self._aggregator_script_body()
        self.assertIn('value != "success"', script)
        self.assertIn("AGGREGATOR_DENY", script)
        self.assertIn("validate-core", script)
        self.assertIn("validate-execution", script)
        self.assertIn("validate-tests", script)

    def test_aggregator_denies_failed_or_skipped_execution(self) -> None:
        body = self._aggregator_script_body()
        for execution_result in ("failure", "skipped", "cancelled"):
            with self.subTest(execution_result=execution_result):
                env = {
                    **os.environ,
                    "CORE_RESULT": "success",
                    "EXECUTION_RESULT": execution_result,
                    "TESTS_RESULT": "success",
                }
                completed = subprocess.run(
                    [sys.executable, "-c", body],
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("AGGREGATOR_DENY", completed.stdout)


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
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("delivery-harness/policies/solana-alpha-lab.md", agents)
        text = (ROOT / "delivery-harness/policies/solana-alpha-lab.md").read_text(encoding="utf-8")
        self.assertIn("## TRACKED_ONLY_DELIVERY_PREFLIGHT", text)
        self.assertIn(ci.DELIVERY_PREFLIGHT_COMMAND, text)
        self.assertIn(
            f"wall-time cap is {ci.DELIVERY_PREFLIGHT_TIMEOUT_MINUTES} minutes",
            text,
        )
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

    def test_delivery_output_decoder_retains_summary_after_invalid_utf8(self) -> None:
        raw = (
            b"Ran 42 tests in 1.000s\nOK\nRESULT: PASS\n"
            b"diagnostic:\xefinvalid\n"
        )
        decoded = ci.decode_delivery_output(raw)
        self.assertIn("\ufffd", decoded)
        summary = ci.parse_validation_summary(decoded)
        self.assertEqual(summary["tests_run"], 42)
        self.assertEqual(summary["pass_labels"], 1)
        self.assertEqual(summary["failure_diagnostics"], [])

    def test_delivery_output_emitter_is_safe_for_cp1251_console(self) -> None:
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1251", errors="strict")
        decoded = ci.decode_delivery_output(b"RESULT: PASS\ndiagnostic:\xefinvalid\n")
        ci.emit_delivery_output(decoded, stream=stream)
        stream.flush()
        rendered = buffer.getvalue().decode("cp1251")
        self.assertIn("RESULT: PASS", rendered)
        self.assertIn("\\ufffd", rendered)

    def test_delivery_mode_is_opt_in_and_base_ref_is_explicit(self) -> None:
        ordinary = ci.parse_args([])
        delivery = ci.parse_args(
            ["--tracked-only-delivery", "--base-ref", "origin/main"]
        )
        self.assertFalse(ordinary.tracked_only_delivery)
        self.assertFalse(ordinary.control_only_task_close)
        self.assertFalse(ordinary.ci_owned_delivery)
        self.assertTrue(delivery.tracked_only_delivery)
        self.assertFalse(delivery.ci_owned_delivery)
        self.assertEqual(delivery.base_ref, "origin/main")

    def test_control_only_close_mode_is_exclusive_and_explicit(self) -> None:
        fast_path = ci.parse_args(
            ["--control-only-task-close", "--base-ref", "origin/main"]
        )
        self.assertTrue(fast_path.control_only_task_close)
        self.assertFalse(fast_path.tracked_only_delivery)
        self.assertFalse(fast_path.ci_owned_delivery)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ci.parse_args(
                    ["--tracked-only-delivery", "--control-only-task-close"]
                )

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


class CiOwnedDeliveryPilotTests(unittest.TestCase):
    def test_mode_is_explicit_and_exclusive(self) -> None:
        candidate = ci.parse_args(
            ["--ci-owned-delivery", "--base-ref", "origin/main"]
        )
        self.assertTrue(candidate.ci_owned_delivery)
        self.assertFalse(candidate.tracked_only_delivery)
        self.assertFalse(candidate.control_only_task_close)
        self.assertEqual(candidate.base_ref, "origin/main")
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ci.parse_args(
                    ["--ci-owned-delivery", "--tracked-only-delivery"]
                )

    def test_ordinary_offline_candidate_paths_are_eligible(self) -> None:
        changed_paths = [
            "src/solana_alpha_lab/task30_example.py",
            "tests/test_task30_example.py",
            "configs/task30_example_v1.yaml",
            "docs/contracts/task30_example_v1.md",
            "catalog/assets/core.yaml",
            "catalog/generated/asset_edges.json",
            "docs/PROJECT_MAP.md",
        ]
        self.assertEqual(
            ci.validate_ci_owned_delivery_eligibility(changed_paths),
            changed_paths,
        )

    def test_validation_dependency_schema_and_control_changes_fail_closed(self) -> None:
        forbidden = (
            ".github/workflows/ci.yml",
            ".github/pull_request_template.md",
            ".githooks/pre-commit",
            ".cursor/rules/20-validation.mdc",
            ".python-version",
            "pyproject.toml",
            "uv.lock",
            "AGENTS.md",
            "docs/agent/EXECUTION_ROUTER_PROTOCOL.md",
            "docs/agent/GITHUB_BATON_PROTOCOL.md",
            "scripts/validate_ci.py",
            "scripts/validate_baseline.py",
            "scripts/validate_baton.py",
            "scripts/validate_catalog.py",
            "scripts/secret_scan.py",
            "scripts/baton_contract.py",
            "control/owner_attention_gate_v1.yaml",
            "schemas/schema_v1.sql",
            "migrations/0001_canonical_schema_v1.sql",
            "catalog/schemas/asset_catalog.schema.json",
            "catalog/schemas/catalog_manifest.schema.json",
            "catalog/schemas/lifecycle_registry.schema.json",
            "catalog/schemas/delivery_harness.schema.json",
            "catalog/schemas/delivery_harness_task_contract.schema.json",
            "catalog/schemas/owner_attention_gate_v2.schema.json",
            "catalog/schemas/project_sources_release_registry.schema.json",
            "catalog/schemas/query_recipe.schema.json",
            "src/solana_alpha_lab/contracts/schema_v1.py",
            "src/solana_alpha_lab/contracts/migration_ledger.py",
            "tests/test_ci.py",
            "tests/test_generate_navigation.py",
            "tests/test_pre_git_import.py",
            "tests/test_project_sources_release_registry.py",
            "tests/test_secret_scan.py",
            "tests/test_task04_core_stack.py",
            "tests/test_baton_contract.py",
            "tests/test_baton_repository_policy.py",
            "C:/outside/repository.py",
        )
        for path in forbidden:
            with self.subTest(path=path):
                with self.assertRaisesRegex(
                    ci.CiValidationError,
                    "ci_owned_delivery_ineligible_paths",
                ):
                    ci.validate_ci_owned_delivery_eligibility([path])

    def test_product_task_schema_and_catalog_inventory_are_eligible(self) -> None:
        changed_paths = [
            "src/solana_alpha_lab/task30_example.py",
            "tests/test_task30_example.py",
            "tests/test_catalog.py",
            "catalog/schemas/task30_a25_h07_h01_limited_diagnostic.schema.json",
            "catalog/schemas/provider_route_capability_registry_v6.schema.json",
            "configs/task30_example_v1.yaml",
            "docs/contracts/task30_example_v1.md",
            "catalog/assets/core.yaml",
            "catalog/generated/asset_edges.json",
            "docs/PROJECT_MAP.md",
        ]
        self.assertEqual(
            ci.validate_ci_owned_delivery_eligibility(changed_paths),
            changed_paths,
        )

    def test_product_research_memory_projection_ddl_is_eligible(self) -> None:
        changed_paths = [
            "src/solana_alpha_lab/factory/research_memory.py",
            "tests/test_fast_lane_semantic_dod.py",
            "schemas/research_memory_projection_v1.sql",
        ]
        self.assertEqual(
            ci.validate_ci_owned_delivery_eligibility(changed_paths),
            changed_paths,
        )

    def test_product_hypothesis_forge_cursor_commands_are_eligible(self) -> None:
        changed_paths = [
            ".cursor/commands/hypothesis-forge.md",
            ".cursor/commands/independent-hypothesis-critic.md",
            ".agents/skills/hypothesis-forge/SKILL.md",
            "docs/tasks/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_V1.md",
        ]
        self.assertEqual(
            ci.validate_ci_owned_delivery_eligibility(changed_paths),
            changed_paths,
        )

    def test_unnamed_repo_root_schema_sql_stays_ineligible(self) -> None:
        for path in (
            "schemas/schema_v1.sql",
            "schemas/research_memory_projection_v2.sql",
            "schemas/other_product.sql",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(
                    ci.CiValidationError,
                    "ci_owned_delivery_ineligible_paths",
                ):
                    ci.validate_ci_owned_delivery_eligibility([path])

    def test_tracked_only_clone_env_uses_hardlink_and_drops_sandbox_cache(
        self,
    ) -> None:
        source = {
            "PATH": "/bin",
            "UV_CACHE_DIR": (
                r"C:\Users\someone\AppData\Local\Temp\cursor-sandbox-cache\uv"
            ),
            "VIRTUAL_ENV": r"C:\venv",
            "UV_LINK_MODE": "symlink",
        }
        environment = ci.tracked_only_clone_environment(source)
        self.assertEqual(environment["UV_LINK_MODE"], "hardlink")
        self.assertNotIn("UV_CACHE_DIR", environment)
        self.assertNotIn("VIRTUAL_ENV", environment)
        self.assertEqual(environment["UV_OFFLINE"], "1")
        self.assertEqual(environment["UV_NO_ENV_FILE"], "1")
        self.assertEqual(environment["SMIAL_TRACKED_ONLY_DELIVERY"], "1")

    def test_tracked_only_clone_env_keeps_non_sandbox_cache(self) -> None:
        cache = r"C:\Users\someone\AppData\Local\uv\cache"
        environment = ci.tracked_only_clone_environment({"UV_CACHE_DIR": cache})
        self.assertEqual(environment["UV_CACHE_DIR"], cache)
        self.assertEqual(environment["UV_LINK_MODE"], "hardlink")

    def test_focused_gate_retains_controls_without_full_repository_suite(self) -> None:
        commands = {label: command for label, command in ci.ci_owned_child_commands()}
        self.assertEqual(
            set(commands),
            {
                "SECRET_REJECTION",
                "BATON_VALIDATION",
                "CATALOG_VALIDATION",
                "FACTORY_STATIC",
                "CATALOG_RESOLUTION",
                "GENERATED_NAVIGATION",
                "PRE_GIT_IMPORT_VALIDATION",
                "TASK04_ARCHITECTURE",
                "PRE_COMMIT_HOOK",
            },
        )
        flattened = " ".join(
            part for command in commands.values() for part in command
        )
        self.assertNotIn("scripts/validate_baseline.py", flattened)
        self.assertIn("--focused", commands["BATON_VALIDATION"])

    def test_focused_child_execution_is_forced_offline(self) -> None:
        observed: dict[str, str] = {}

        def runner(*_args, **kwargs):
            observed.update(kwargs["env"])
            return subprocess.CompletedProcess([], 0, "", "")

        ci.run_checked(
            "SYNTHETIC",
            ["synthetic"],
            runner=runner,
            offline=True,
        )
        self.assertEqual(observed["UV_OFFLINE"], "1")
        self.assertEqual(observed["UV_NO_ENV_FILE"], "1")

    def test_policy_names_owner_pilot_success_and_rollback(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("delivery-harness/policies/solana-alpha-lab.md", agents)
        domain = (ROOT / "delivery-harness/policies/solana-alpha-lab.md").read_text(
            encoding="utf-8"
        )
        router = (ROOT / "docs/agent/EXECUTION_ROUTER_PROTOCOL.md").read_text(
            encoding="utf-8"
        )
        for text in (domain, router):
            normalized = " ".join(text.split())
            with self.subTest(owner="policy"):
                self.assertIn("CI_OWNED_DELIVERY_PILOT", normalized)
                self.assertIn(ci.CI_OWNED_DELIVERY_COMMAND, normalized)
                self.assertIn("GITHUB_PR_EXACT_HEAD_CI", normalized)
                self.assertIn("next three eligible", normalized)
                self.assertIn("120 seconds", normalized)
                self.assertIn("3/3", normalized)
                self.assertIn("seven minutes", normalized)
                self.assertIn("--tracked-only-delivery", normalized)
                self.assertIn("missed clean-checkout", normalized)
                self.assertIn("observation N/3", normalized)
                self.assertIn("do not admit a fourth", normalized)


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
        self.assertIn("scripts/validate_factory_static.py", commands["FACTORY_STATIC"])
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


class ReuseFirstRecoveryTriggerTests(unittest.TestCase):
    def test_agents_contract_requires_reuse_first_after_material_blocker(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("delivery-harness/policies/solana-alpha-lab.md", agents)
        text = (ROOT / "delivery-harness/policies/solana-alpha-lab.md").read_text(
            encoding="utf-8"
        )
        normalized_text = " ".join(text.split())
        required_fragments = (
            "## REUSE_FIRST_RECOVERY_TRIGGER",
            "first material, evidence-backed blocker",
            "no hidden retry or fallback",
            "`registries/reuse_candidates.yaml`",
            "`ADR-002`",
            "`ADOPT`, `WRAP`, `FORK`, `BUILD`, or `STOP`",
            "cheapest falsifier",
            "current atom's decision or acceptance receipt",
            "not a registry row, permanent Source, or generic scan artifact",
            "provider, dependency, cost, security, or owner-boundary change",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, normalized_text)
        self.assertIn("routine deterministic test failure", normalized_text)
        self.assertIn("already-known limitation", normalized_text)
        self.assertLess(
            text.index("## REUSE_FIRST_RECOVERY_TRIGGER"),
            text.index("## VALIDATION_ECONOMY"),
        )


class ControlOnlyTaskCloseDocumentationTests(unittest.TestCase):
    def test_agents_makes_fast_path_and_fallback_unavoidable(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("delivery-harness/policies/solana-alpha-lab.md", agents)
        text = (ROOT / "delivery-harness/policies/solana-alpha-lab.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## CONTROL_ONLY_TASK_CLOSE_FAST_PATH", text)
        self.assertIn("--control-only-task-close", text)
        self.assertIn("GITHUB_PR_EXACT_HEAD_CI", text)
        self.assertIn("--tracked-only-delivery", text)
        self.assertIn("three eligible task closes", text)

    def test_release_protocol_keeps_smoke_and_done_separate(self) -> None:
        text = (ROOT / "docs/project_sources/RELEASES.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "TASK<NN>_SOURCE_SMOKE=PASS; OWNER_DONE_ACCEPTANCE", text
        )
        self.assertIn("a smoke PASS never implies task DONE", text)
        self.assertIn("one combined activation-and-close receipt", text)


if __name__ == "__main__":
    unittest.main()
