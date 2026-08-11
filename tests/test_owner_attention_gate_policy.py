from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "control" / "owner_attention_gate_v1.yaml"
SCRIPT_PATH = ROOT / "scripts" / "owner_attention_gate.py"


def load_module() -> ModuleType:
    if not SCRIPT_PATH.is_file():
        raise AssertionError(f"missing gate evaluator: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("owner_attention_gate", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("owner_attention_gate module is not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_policy() -> dict[str, Any]:
    if not POLICY_PATH.is_file():
        raise AssertionError(f"missing owner attention policy: {POLICY_PATH}")
    document = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError("owner attention policy must be a mapping")
    return document


def base_request(
    *,
    route: str = "LOCAL_WORK_CODEX",
    actor: str = "CODEX",
    action_class: str = "ROUTINE_ENGINEERING",
) -> dict[str, Any]:
    return {
        "schema": "smial.owner-attention-request",
        "schema_version": "1.0",
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
        "merge_checks": None,
    }


def passing_merge_request(
    *,
    route: str = "LOCAL_WORK_CODEX",
    actor: str = "CODEX",
) -> dict[str, Any]:
    request = base_request(
        route=route,
        actor=actor,
        action_class="MERGE_PULL_REQUEST",
    )
    request["merge_checks"] = {
        "exact_pr_head_bound": True,
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
    return request


class OwnerAttentionGatePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.policy = load_policy()

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.module.evaluate(request, self.policy)

    def test_policy_contract_and_route_authority_are_explicit(self) -> None:
        self.assertEqual(self.policy["schema"], "smial.owner-attention-gate")
        self.assertEqual(self.policy["schema_version"], "1.0")
        self.assertEqual(
            self.policy["route_authority"]["LOCAL_WORK_CODEX"]["ordinary_merge"],
            "AUTONOMOUS_AFTER_MACHINE_GATE",
        )
        self.assertEqual(
            self.policy["route_authority"][
                "PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR"
            ]["cursor_merge"],
            "FORBIDDEN",
        )
        self.assertTrue(self.policy["post_merge"]["exact_main_readback_required"])
        self.assertTrue(self.policy["post_merge"]["main_ci_required"])

    def test_bounded_routine_engineering_is_autonomous(self) -> None:
        result = self.evaluate(base_request())
        self.assertEqual(result["decision"], "AUTONOMOUS")
        self.assertEqual(result["reasons"], ["ROUTINE_IN_ENVELOPE"])

    def test_local_codex_merge_is_autonomous_after_all_machine_checks(self) -> None:
        result = self.evaluate(passing_merge_request())
        self.assertEqual(result["decision"], "AUTONOMOUS")
        self.assertEqual(result["reasons"], ["LOCAL_CODEX_MERGE_GATE_PASS"])

    def test_cursor_merge_is_always_denied(self) -> None:
        result = self.evaluate(
            passing_merge_request(
                route="PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR",
                actor="CURSOR",
            )
        )
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(result["reasons"], ["CURSOR_MERGE_FORBIDDEN"])

    def test_non_local_codex_merge_requires_owner_attention(self) -> None:
        result = self.evaluate(
            passing_merge_request(route="PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR")
        )
        self.assertEqual(result["decision"], "OWNER_ATTENTION_REQUIRED")
        self.assertEqual(result["reasons"], ["ROUTE_HAS_NO_CODEX_AUTO_MERGE"])

    def test_failed_merge_check_denies_merge_without_human_override(self) -> None:
        request = passing_merge_request()
        request["merge_checks"]["ci_exact_head_pass"] = False
        result = self.evaluate(request)
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(result["reasons"], ["MERGE_CHECK_FAILED:ci_exact_head_pass"])

    def test_each_material_trigger_requests_owner_attention(self) -> None:
        expected = {
            "auth_or_access_recovery": "AUTH_OR_ACCESS_RECOVERY",
            "material_owner_decision": "MATERIAL_OWNER_DECISION",
            "user_only_activation": "USER_ONLY_ACTIVATION",
            "external_material_action": "EXTERNAL_MATERIAL_ACTION",
            "unresolved_safety_or_truth_conflict": (
                "UNRESOLVED_SAFETY_OR_TRUTH_CONFLICT"
            ),
        }
        for trigger, reason in expected.items():
            with self.subTest(trigger=trigger):
                request = base_request()
                request["triggers"][trigger] = True
                result = self.evaluate(request)
                self.assertEqual(result["decision"], "OWNER_ATTENTION_REQUIRED")
                self.assertEqual(result["reasons"], [reason])

    def test_unbound_scope_is_denied(self) -> None:
        request = base_request()
        request["scope_bound"] = False
        result = self.evaluate(request)
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(result["reasons"], ["SCOPE_NOT_BOUND"])

    def test_stricter_stop_preempts_standing_autonomy(self) -> None:
        request = base_request()
        request["stricter_stop_active"] = True
        result = self.evaluate(request)
        self.assertEqual(result["decision"], "OWNER_ATTENTION_REQUIRED")
        self.assertEqual(result["reasons"], ["STRICTER_STOP_ACTIVE"])

    def test_active_policy_surfaces_cannot_restore_per_pr_approval_loop(self) -> None:
        active_paths = (
            "AGENTS.md",
            ".cursor/rules/00-authority.mdc",
            ".cursor/rules/50-github-baton.mdc",
            ".github/pull_request_template.md",
            "docs/agent/EXECUTION_ROUTER_PROTOCOL.md",
            "docs/agent/GITHUB_BATON_PROTOCOL.md",
        )
        forbidden = (
            "exact per-PR confirmation",
            "exact per-PR user confirmation",
            "explicit confirmation for that exact PR",
        )
        for relative in active_paths:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("OWNER_ATTENTION_GATE", text, relative)
            for phrase in forbidden:
                self.assertNotIn(phrase, text, relative)

    def test_project_instruction_candidate_is_ui_safe_and_policy_aligned(self) -> None:
        path = ROOT / "docs" / "agent" / "PROJECT_INSTRUCTION_V3_5.md"
        text = path.read_text(encoding="utf-8")
        self.assertTrue(
            text.startswith(
                "PROJECT INSTRUCTION — SOLANA MEMECOIN INTRADAY ALPHA LAB v3.5"
            )
        )
        self.assertLessEqual(len(text), 8000)
        self.assertIn("OWNER_ATTENTION_GATE", text)
        self.assertIn("LOCAL_WORK_CODEX: Codex сам merge", text)
        self.assertIn("Cursor не merge", text)
        self.assertIn("dormant", text)
        self.assertNotIn("Final merge — после подтверждения exact PR", text)

    def test_model_effort_router_is_present_on_active_policy_surfaces(self) -> None:
        required = (
            "MODEL_EFFORT_RECOMMENDATION",
            "NEXT_MODEL_EFFORT",
            "LUNA_MAX",
            "SOL_XHIGH",
            "SOL_MAX",
            "TERRA_XHIGH",
            "ROUTINE_NO_SWITCH",
            "hardest material segment",
        )
        for relative in ("AGENTS.md", "docs/agent/PROJECT_INSTRUCTION_V3_5.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for marker in required:
                self.assertIn(marker, text, f"{relative}: missing {marker}")


if __name__ == "__main__":
    unittest.main()
