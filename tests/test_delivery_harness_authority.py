from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/owner_attention_gate.py"
POLICY = ROOT / "control/owner_attention_gate_v2.yaml"
HEAD = "abcdef0123456789abcdef0123456789abcdef01"
OTHER_HEAD = "1234567890abcdef1234567890abcdef12345678"
PR = 102
APPROVAL = f"PR #{PR}, head {HEAD} проверен; ready + merge разрешаю."


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("owner_attention_gate", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("owner attention gate is not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_policy() -> dict[str, Any]:
    value = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("policy mapping required")
    return value


def base_request(
    *,
    route: str = "DIRECT_CODEX_DELIVERY",
    actor: str = "CODEX",
    action_class: str = "ROUTINE_ENGINEERING",
) -> dict[str, Any]:
    return {
        "schema": "smial.owner-attention-request",
        "schema_version": "2.0",
        "repository": "lancerbeta/solana-alpha-lab",
        "route": route,
        "actor": actor,
        "action_class": action_class,
        "scope_bound": True,
        "stricter_stop_active": False,
        "triggers": {
            "auth_or_access_recovery": False,
            "material_owner_decision": False,
            "user_only_activation": False,
            "external_material_action": False,
            "unresolved_safety_or_truth_conflict": False,
        },
        "owner_approval": None,
        "merge_checks": None,
    }


def passing_merge_request(
    *,
    route: str = "DIRECT_CODEX_DELIVERY",
    actor: str = "CODEX",
) -> dict[str, Any]:
    value = base_request(route=route, actor=actor, action_class="MERGE_PULL_REQUEST")
    value["owner_approval"] = {
        "phrase": APPROVAL,
        "pr_number": PR,
        "head_sha": HEAD,
        "context_receipt_sha256": "a" * 64,
        "context_route": (
            route
            if route in {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY"}
            else "DIRECT_CURSOR_DELIVERY"
        ),
    }
    value["merge_checks"] = {
        "pr_number": PR,
        "observed_head_sha": HEAD,
        "observed_tree_sha": "fedcba9876543210fedcba9876543210fedcba98",
        "context_receipt_sha256": "a" * 64,
        "context_route": (
            route
            if route in {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY"}
            else "DIRECT_CURSOR_DELIVERY"
        ),
        "exact_pr_head_bound": True,
        "context_receipt_bound": True,
        "required_tests_pass": True,
        "ci_exact_head_pass": True,
        "full_gate_pass": True,
        "factory_fit_pass": True,
        "write_set_pass": True,
        "secret_scan_pass": True,
        "mergeable": True,
        "no_unresolved_reviews": True,
        "standard_merge": True,
        "branch_preserved": True,
        "settings_unchanged": True,
    }
    return value


class DeliveryHarnessAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.policy = load_policy()

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.module.evaluate(request, self.policy)

    def test_direct_agents_run_bounded_routine_work(self) -> None:
        for route, actor in (
            ("DIRECT_CODEX_DELIVERY", "CODEX"),
            ("DIRECT_CURSOR_DELIVERY", "CURSOR"),
        ):
            with self.subTest(route=route):
                result = self.evaluate(base_request(route=route, actor=actor))
                self.assertEqual(result["decision"], "AUTONOMOUS")
                self.assertEqual(result["reasons"], ["ROUTINE_IN_ENVELOPE"])

    def test_material_triggers_stop_both_direct_agents(self) -> None:
        for route, actor in (
            ("DIRECT_CODEX_DELIVERY", "CODEX"),
            ("DIRECT_CURSOR_DELIVERY", "CURSOR"),
        ):
            for trigger in base_request()["triggers"]:
                with self.subTest(route=route, trigger=trigger):
                    request = base_request(route=route, actor=actor)
                    request["triggers"][trigger] = True
                    self.assertEqual(
                        self.evaluate(request)["decision"],
                        "OWNER_ATTENTION_REQUIRED",
                    )

    def test_direct_merge_requires_exact_owner_phrase(self) -> None:
        for route, actor in (
            ("DIRECT_CODEX_DELIVERY", "CODEX"),
            ("DIRECT_CURSOR_DELIVERY", "CURSOR"),
        ):
            with self.subTest(route=route):
                request = passing_merge_request(route=route, actor=actor)
                request["owner_approval"] = None
                result = self.evaluate(request)
                self.assertEqual(result["decision"], "OWNER_ATTENTION_REQUIRED")
                self.assertEqual(result["reasons"], ["EXACT_MERGE_APPROVAL_REQUIRED"])

    def test_direct_merge_is_autonomous_only_after_exact_gate(self) -> None:
        for route, actor in (
            ("DIRECT_CODEX_DELIVERY", "CODEX"),
            ("DIRECT_CURSOR_DELIVERY", "CURSOR"),
        ):
            with self.subTest(route=route):
                result = self.evaluate(passing_merge_request(route=route, actor=actor))
                self.assertEqual(result["decision"], "AUTONOMOUS")
                self.assertEqual(
                    result["reasons"],
                    ["DIRECT_AGENT_EXACT_MERGE_GATE_PASS"],
                )

    def test_stale_or_mismatched_merge_identity_is_denied(self) -> None:
        mutations = (
            lambda value: value["merge_checks"].__setitem__("observed_head_sha", OTHER_HEAD),
            lambda value: value["owner_approval"].__setitem__("head_sha", OTHER_HEAD),
            lambda value: value["owner_approval"].__setitem__("pr_number", PR + 1),
            lambda value: value["owner_approval"].__setitem__("context_receipt_sha256", "b" * 64),
            lambda value: value["owner_approval"].__setitem__("context_route", "DIRECT_CURSOR_DELIVERY"),
            lambda value: value["owner_approval"].__setitem__("phrase", APPROVAL.replace(str(PR), str(PR + 1))),
            lambda value: value.__setitem__("repository", "other/repository"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                request = passing_merge_request()
                mutate(request)
                self.assertEqual(self.evaluate(request)["decision"], "DENY")

    def test_failed_machine_check_cannot_be_overridden(self) -> None:
        request = passing_merge_request()
        request["merge_checks"]["ci_exact_head_pass"] = False
        result = self.evaluate(request)
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(result["reasons"], ["MERGE_CHECK_FAILED:ci_exact_head_pass"])

    def test_failed_machine_check_beats_owner_attention_trigger(self) -> None:
        request = passing_merge_request()
        request["merge_checks"]["ci_exact_head_pass"] = False
        request["triggers"]["material_owner_decision"] = True
        result = self.evaluate(request)
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(result["reasons"], ["MERGE_CHECK_FAILED:ci_exact_head_pass"])

    def test_dormant_baton_cursor_merge_remains_forbidden(self) -> None:
        request = passing_merge_request(
            route="LEGACY_GITHUB_BATON_DORMANT", actor="CURSOR"
        )
        result = self.evaluate(request)
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(result["reasons"], ["ROUTE_MERGE_FORBIDDEN"])

    def test_dormant_route_denial_beats_owner_attention_trigger(self) -> None:
        request = passing_merge_request(
            route="LEGACY_GITHUB_BATON_DORMANT", actor="CURSOR"
        )
        request["triggers"]["material_owner_decision"] = True
        result = self.evaluate(request)
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(result["reasons"], ["ROUTE_MERGE_FORBIDDEN"])

    def test_closed_schema_and_type_strictness_fail_closed(self) -> None:
        mutations = (
            lambda value: value.__setitem__("unexpected", True),
            lambda value: value.__setitem__("scope_bound", 1),
            lambda value: value["merge_checks"].__setitem__("pr_number", True),
            lambda value: value["merge_checks"].__setitem__("pr_number", float(PR)),
            lambda value: value["merge_checks"].__setitem__("mergeable", 1),
            lambda value: value["owner_approval"].__setitem__("head_sha", HEAD.upper()),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                request = passing_merge_request()
                mutate(request)
                result = self.evaluate(request)
                self.assertEqual(result["decision"], "DENY")
                self.assertIn("INVALID_REQUEST_SCHEMA", result["reasons"])

    def test_actor_route_switch_is_denied(self) -> None:
        request = base_request(route="DIRECT_CURSOR_DELIVERY", actor="CODEX")
        self.assertEqual(self.evaluate(request)["decision"], "DENY")

    def test_policy_contract_is_v2_and_default(self) -> None:
        self.assertEqual(self.policy["schema_version"], "2.0")
        self.assertEqual(self.policy["policy_id"], "OWNER_ATTENTION_GATE_V2")
        self.assertEqual(self.module.DEFAULT_POLICY, POLICY)
        self.assertTrue(self.policy["post_merge"]["exact_main_readback_required"])
        self.assertTrue(self.policy["post_merge"]["main_ci_required"])

    def test_harness_merge_policy_forbids_owner_github_merge_click(self) -> None:
        harness = yaml.safe_load(
            (ROOT / "delivery-harness/harness.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(harness["merge_policy"]["executor"], "DIRECT_AGENT")
        self.assertEqual(harness["merge_policy"]["owner_github_merge_click"], "FORBIDDEN")
        self.assertEqual(harness["merge_policy"]["owner_role"], "EXACT_PHRASE_AFTER_CI")


if __name__ == "__main__":
    unittest.main()
