"""Executor-route admission, legacy policy reads, and scoped policy delivery.

GitHub responses in the journey test are SIMULATION_ONLY. The local Git
fixture uses real commits and ``git show`` readback.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = ROOT / "scripts/owner_attention_gate.py"
HARNESS_SCRIPT = ROOT / "scripts/delivery_harness.py"
POLICY_PATH = ROOT / "control/owner_attention_gate_v2.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/owner_attention_gate_v2.schema.json"
HARNESS_SCHEMA = ROOT / "catalog/schemas/delivery_harness.schema.json"
TASK_SCHEMA = ROOT / "catalog/schemas/delivery_harness_task_contract.schema.json"
PORTABLE_POLICY = (
    ROOT
    / "delivery-harness/templates/portable-core/control/owner_attention_gate_v2.yaml"
)
PORTABLE_HARNESS = (
    ROOT
    / "delivery-harness/templates/portable-core/delivery-harness/harness.yaml"
)


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"not loadable: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", "user.email=factory@example.com", "-c", "user.name=factory", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr.decode("utf-8", errors="replace"))
    return completed.stdout.decode("utf-8").strip()


def task_text(*, expected_base: str, managed: list[str]) -> str:
    metadata = {
        "task_id": "HARNESS_EXECUTOR_FIXTURE_V1",
        "task_version": "1.0",
        "status": "READY",
        "as_of": "2026-09-29",
        "owner": "GOAL_OWNER",
        "allowed_routes": ["DIRECT_CURSOR_DELIVERY"],
        "expected_repository": "example/fixture",
        "git_binding": {
            "expected_base": expected_base,
            "expected_upstream": "origin/main",
            "expected_upstream_oid": expected_base,
            "expected_branch": "fixture/executor",
            "dirty_mode": "FORBIDDEN",
        },
        "objective": "Disposable fixture for scoped policy transition admission.",
        "managed_write_set": managed,
        "external_caps": {
            "network": False,
            "credentials": False,
            "external_system": False,
            "signing_or_financial_action": False,
            "cash_spend": False,
            "deployment": False,
        },
        "stop_conditions": ["UNSCOPED_POLICY_DRIFT"],
        "context_requirements": {
            "catalog_asset_ids": [],
            "l2_roles": [],
            "l3_roles": [],
            "roadmap_path": None,
            "exact_role_paths": {
                "LIFECYCLE": [],
                "EXTERNAL_ROUTE_KNOWLEDGE": [],
                "ARCHITECTURE_DECISIONS": [],
                "DELIVERY_EVIDENCE": [],
                "HISTORICAL_CONTEXT": [],
            },
        },
    }
    return (
        "---\n"
        + json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        + "\n---\n\n# Fixture\n"
    )


def receipt_for(module: ModuleType, root: Path, relative: str) -> dict:
    head = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    task_bytes = (root / relative).read_bytes()
    receipt: dict = {
        "schema": "smial.delivery-context-receipt",
        "schema_version": "1.0",
        "harness_id": "DELIVERY_HARNESS_V1",
        "route": "DIRECT_CURSOR_DELIVERY",
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "repository": {
            "name": "example/fixture",
            "head": head,
            "tree": tree,
            "branch": "fixture/executor",
            "dirty": False,
        },
        "task": {
            "task_id": "HARNESS_EXECUTOR_FIXTURE_V1",
            "path": relative,
            "sha256": hashlib.sha256(task_bytes).hexdigest(),
        },
        "selected": [],
        "gaps": [],
        "budgets": {
            "agents_max_bytes": 12288,
            "cursor_always_apply_max_bytes": 6144,
            "ordinary_receipt_max_bytes": 49152,
            "auto_inline_file_max_bytes": 102400,
        },
    }
    receipt["receipt_sha256"] = module.sha256_bytes(module.canonical_json_bytes(receipt))
    return receipt


class ExecutorExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gate = load_module(GATE_SCRIPT, "executor_extension_gate")
        cls.harness = load_module(HARNESS_SCRIPT, "executor_extension_harness")
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.old_policy = json.loads(
            subprocess.run(
                ["git", "show", "origin/main:control/owner_attention_gate_v2.yaml"],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                shell=False,
            ).stdout.decode("utf-8")
        )

    def test_p1_unknown_and_wrong_pair_are_not_other(self) -> None:
        for bad in ("kimi", "glm", "claude", "", "otherish"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "ACTOR_INVALID"):
                    self.gate.normalize_cli_actor(bad)
        self.assertEqual(self.gate.normalize_cli_actor("claude_code"), "CLAUDE_CODE")
        self.assertEqual(self.gate.normalize_cli_actor("Other"), "OTHER")
        with self.assertRaisesRegex(ValueError, "ACTOR_NOT_ALLOWED_FOR_ROUTE"):
            self.gate.admit_transport_actor(
                self.policy, "DIRECT_CURSOR_DELIVERY", "OTHER"
            )
        with self.assertRaisesRegex(ValueError, "UNKNOWN_ROUTE"):
            self.gate.admit_transport_actor(self.old_policy, "DIRECT_OTHER_DELIVERY", "OTHER")
        with self.assertRaisesRegex(ValueError, "ROUTE_MERGE_FORBIDDEN"):
            self.gate.admit_transport_actor(self.policy, "DESIGN_ONLY", "CURSOR")
        with self.assertRaisesRegex(ValueError, "ROUTE_MERGE_FORBIDDEN"):
            self.gate.admit_transport_actor(
                self.policy, "LEGACY_GITHUB_BATON_DORMANT", "CURSOR"
            )
        self.assertEqual(
            self.gate.admit_transport_actor(
                self.policy, "DIRECT_CLAUDE_CODE_DELIVERY", None
            ),
            "CLAUDE_CODE",
        )

    def test_p2_legacy_and_new_policy_share_schema_and_python_verdicts(self) -> None:
        jsonschema.validate(self.old_policy, self.schema)
        jsonschema.validate(self.policy, self.schema)
        self.assertTrue(self.gate._policy_v2_is_closed(self.old_policy))
        self.assertTrue(self.gate._policy_v2_is_closed(self.policy))
        self.assertNotIn("DIRECT_CLAUDE_CODE_DELIVERY", self.old_policy["route_authority"])
        self.assertIn("DIRECT_OTHER_DELIVERY", self.policy["route_authority"])
        extra = json.loads(json.dumps(self.old_policy))
        extra["route_authority"]["KIMI"] = extra["route_authority"]["DIRECT_CURSOR_DELIVERY"]
        self.assertFalse(self.gate._policy_v2_is_closed(extra))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(extra, self.schema)
        portable = json.loads(PORTABLE_POLICY.read_text(encoding="utf-8"))
        jsonschema.validate(portable, self.schema)
        self.assertTrue(self.gate._policy_v2_is_closed(portable))
        portable_harness = json.loads(PORTABLE_HARNESS.read_text(encoding="utf-8"))
        jsonschema.validate(portable_harness, json.loads(HARNESS_SCHEMA.read_text(encoding="utf-8")))
        self.assertNotIn("DIRECT_CLAUDE_CODE_DELIVERY", portable_harness["active_routes"])

    def test_p4_p3_real_git_transition_returns_base_and_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "-b", "main")
            script_dir = root / "scripts"
            schema_dir = root / "catalog/schemas"
            script_dir.mkdir(parents=True)
            schema_dir.mkdir(parents=True)
            shutil.copy(HARNESS_SCRIPT, script_dir / "delivery_harness.py")
            shutil.copy(TASK_SCHEMA, schema_dir / "delivery_harness_task_contract.schema.json")
            policy_relative = "control/owner_attention_gate_v2.yaml"
            (root / "control").mkdir()
            (root / policy_relative).write_text(
                json.dumps(self.old_policy, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (root / "marker.txt").write_text("base\n", encoding="utf-8", newline="\n")
            relative = "docs/tasks/HARNESS_EXECUTOR_FIXTURE_V1.md"
            (root / "docs/tasks").mkdir(parents=True)
            (root / relative).write_text(
                task_text(expected_base="a" * 40, managed=[policy_relative]),
                encoding="utf-8",
                newline="\n",
            )
            git(root, "add", ".")
            git(root, "commit", "-m", "base")
            base = git(root, "rev-parse", "HEAD")
            candidate = json.loads(json.dumps(self.policy))
            candidate["merge_approval"] = dict(candidate["merge_approval"])
            candidate["merge_approval"]["exact_phrase_pattern"] = "^WEAK$"
            candidate["merge_preconditions"] = ["mergeable"]
            (root / policy_relative).write_text(
                json.dumps(candidate, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (root / relative).write_text(
                task_text(expected_base=base, managed=[policy_relative]),
                encoding="utf-8",
                newline="\n",
            )
            (root / "marker.txt").write_text("changed\n", encoding="utf-8", newline="\n")
            git(root, "add", ".")
            git(root, "commit", "-m", "candidate")
            self.assertEqual(
                git(root, "show", "HEAD:marker.txt"),
                "changed",
            )
            loaded = self.gate.load_base_bound_policy(
                root,
                expected_base=base,
                context_receipt=receipt_for(self.gate, root, relative),
            )
            self.assertEqual(
                self.gate.canonical_json_bytes(loaded),
                self.gate.canonical_json_bytes(self.old_policy),
            )
            self.assertNotEqual(loaded["merge_approval"]["exact_phrase_pattern"], "^WEAK$")
            self.assertIn("ci_exact_head_pass", loaded["merge_preconditions"])
            with self.assertRaisesRegex(ValueError, "UNKNOWN_ROUTE"):
                self.gate.admit_transport_actor(
                    loaded, "DIRECT_CLAUDE_CODE_DELIVERY", "CLAUDE_CODE"
                )
            self.assertEqual(
                self.gate.admit_transport_actor(loaded, "DIRECT_CURSOR_DELIVERY", "CURSOR"),
                "CURSOR",
            )
            self.assertEqual(
                self.gate.admit_transport_actor(
                    candidate, "DIRECT_OTHER_DELIVERY", "other"
                ),
                "OTHER",
            )
            with self.assertRaisesRegex(ValueError, "OWNER_POLICY_BASE_BINDING_INVALID"):
                self.gate.load_base_bound_policy(root, expected_base=base)
            (root / relative).write_text(
                task_text(expected_base=base, managed=["control/**"]),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(ValueError, "OWNER_POLICY_BASE_BINDING_INVALID"):
                self.gate.load_base_bound_policy(
                    root,
                    expected_base=base,
                    context_receipt=receipt_for(self.gate, root, relative),
                )

    def test_p3_p5_simulated_github_journey_for_new_routes(self) -> None:
        """SIMULATION_ONLY GitHub. Frozen base bytes are the candidate policy."""

        from tests.test_delivery_harness_merge_guard import (
            PR,
            PHRASE,
            FakeRunner,
            exact_context_builder,
            grounded_delivery_checks,
            grounded_evidence,
        )

        for route, actor in (
            ("DIRECT_CLAUDE_CODE_DELIVERY", "CLAUDE_CODE"),
            ("DIRECT_OTHER_DELIVERY", "OTHER"),
        ):
            with self.subTest(route=route):
                runner = FakeRunner()
                readiness = self.gate.evaluate_merge_readiness(
                    ROOT,
                    repository="lancerbeta/solana-alpha-lab",
                    pr_number=PR,
                    route=route,
                    actor=actor,
                    context_receipt=exact_context_builder(self.gate)(
                        ROOT,
                        task_id="CTRL-DELIVERY-HARNESS-V1",
                        task_contract="docs/tasks/CTRL-DELIVERY-HARNESS-V1.md",
                        route=route,
                    ),
                    runner=runner,
                    context_builder=exact_context_builder(self.gate),
                    evidence_builder=grounded_evidence,
                    delivery_checks_builder=grounded_delivery_checks,
                )
                self.assertTrue(readiness["ready_for_owner_phrase"])
                self.assertFalse(readiness["merge_submitted"])
                self.assertFalse(any(call[:3] == ("gh", "pr", "merge") for call in runner.calls))
                denied = self.gate.execute_guarded_merge(
                    ROOT,
                    repository="lancerbeta/solana-alpha-lab",
                    pr_number=PR,
                    route=route,
                    actor=actor,
                    approval_phrase="not the phrase",
                    context_receipt=exact_context_builder(self.gate)(
                        ROOT,
                        task_id="CTRL-DELIVERY-HARNESS-V1",
                        task_contract="docs/tasks/CTRL-DELIVERY-HARNESS-V1.md",
                        route=route,
                    ),
                    runner=FakeRunner(),
                    context_builder=exact_context_builder(self.gate),
                    evidence_builder=grounded_evidence,
                    delivery_checks_builder=grounded_delivery_checks,
                )
                self.assertFalse(denied["merge_submitted"])
                submitter = FakeRunner()
                submitted = self.gate.execute_guarded_merge(
                    ROOT,
                    repository="lancerbeta/solana-alpha-lab",
                    pr_number=PR,
                    route=route,
                    actor=actor,
                    approval_phrase=PHRASE,
                    context_receipt=exact_context_builder(self.gate)(
                        ROOT,
                        task_id="CTRL-DELIVERY-HARNESS-V1",
                        task_contract="docs/tasks/CTRL-DELIVERY-HARNESS-V1.md",
                        route=route,
                    ),
                    runner=submitter,
                    context_builder=exact_context_builder(self.gate),
                    evidence_builder=grounded_evidence,
                    delivery_checks_builder=grounded_delivery_checks,
                )
                self.assertTrue(submitted["merge_submitted"])
                self.assertEqual(
                    [call for call in submitter.calls if call[:3] == ("gh", "pr", "merge")],
                    [(
                        "gh", "pr", "merge", str(PR), "--repo", "lancerbeta/solana-alpha-lab",
                        "--merge", "--match-head-commit", submitted["approved_head"],
                    )],
                )
                failed = FakeRunner(postmerge_latest_failure=True)
                with self.assertRaisesRegex(ValueError, "POST_MERGE_READBACK_FAILED"):
                    self.gate.build_post_merge_receipt(
                        ROOT,
                        repository="lancerbeta/solana-alpha-lab",
                        pr_number=PR,
                        route=route,
                        context_receipt=exact_context_builder(self.gate)(
                            ROOT,
                            task_id="CTRL-DELIVERY-HARNESS-V1",
                            task_contract="docs/tasks/CTRL-DELIVERY-HARNESS-V1.md",
                            route=route,
                        ),
                        submission_receipt=submitted,
                        runner=failed,
                        context_builder=exact_context_builder(self.gate),
                    )
                self.assertFalse(any(call[:3] == ("gh", "pr", "merge") for call in failed.calls))

    def test_p5_p6_route_swap_and_phrase_stop(self) -> None:
        prior = {"route": "DIRECT_CURSOR_DELIVERY"}
        self.assertEqual(
            self.harness.validate_route_continuity(prior, "DIRECT_CLAUDE_CODE_DELIVERY"),
            ["ACTIVE_ROUTE_CHANGED"],
        )
        self.assertEqual(
            self.harness.validate_route_continuity(prior, "DIRECT_CURSOR_DELIVERY"),
            [],
        )
        provenance = self.harness.format_executor_provenance(
            coding_client="Kimi Code CLI",
            model=None,
            route="DIRECT_OTHER_DELIVERY",
            actor="OTHER",
        )
        self.assertEqual(provenance["coding_client"], "Kimi Code CLI")
        self.assertEqual(provenance["model"], "UNKNOWN")
        self.assertEqual(provenance["grant"], "NONE")
        with self.assertRaisesRegex(ValueError, "EXECUTOR_CLIENT_UNDECLARED"):
            self.harness.format_executor_provenance(
                coding_client="OTHER",
                model="glm",
                route="DIRECT_OTHER_DELIVERY",
                actor="OTHER",
            )

    def test_p7_shim_and_starter_prompt(self) -> None:
        shim = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertNotIn("```", shim)
        self.assertEqual(shim.strip(), "@AGENTS.md")
        protocol = (ROOT / "docs/agent/DELIVERY_HARNESS_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("DIRECT_OTHER_DELIVERY", protocol)
        self.assertIn("docs/tasks/<TASK>.md", protocol)
        self.assertIn(".agents/skills/delivery-harness/SKILL.md", protocol)
        self.assertLessEqual((ROOT / "AGENTS.md").stat().st_size, 12288)


if __name__ == "__main__":
    unittest.main()
