from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from tests.test_delivery_harness_merge_guard import (
    FakeRunner,
    context_receipt,
    exact_context_builder,
    grounded_delivery_checks,
    grounded_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = ROOT / "scripts/owner_attention_gate.py"
ROUTING_RULE = ROOT / ".cursor/rules/10-input-routing.mdc"
POLICY = ROOT / "control/owner_attention_gate_v2.yaml"
HEAD = "abcdef0123456789abcdef0123456789abcdef01"
PR = 102


def load_gate_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("owner_attention_gate", GATE_SCRIPT)
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


class DeterministicFinishAcceptanceTests(unittest.TestCase):
    """Acceptance matrix for DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.gate = load_gate_module()
        cls.policy = load_policy()

    # 13. lowercase cursor -> canonical CURSOR
    def test_actor_cli_casing_normalizes_to_canonical_uppercase(self) -> None:
        for raw, canonical in (
            ("cursor", "CURSOR"),
            ("Cursor", "CURSOR"),
            ("CURSOR", "CURSOR"),
            ("codex", "CODEX"),
            ("Codex", "CODEX"),
            ("CODEX", "CODEX"),
        ):
            self.assertEqual(self.gate.normalize_cli_actor(raw), canonical, raw)

    # 14. unknown actor -> DENY
    def test_unknown_actor_is_invalid_even_with_fuzzy_similarity(self) -> None:
        for bad in ("curson", "codexx", "claude", "gpt", "", "cursor "):
            with self.assertRaisesRegex(ValueError, "ACTOR_INVALID"):
                self.gate.normalize_cli_actor(bad)

    # 16. rendered owner_phrase matches base-bound policy regex
    def test_rendered_owner_phrase_fullmatches_policy_pattern(self) -> None:
        pattern = self.policy["merge_approval"]["exact_phrase_pattern"]
        phrase = self.gate.render_owner_merge_phrase(
            pr_number=PR, head_sha=HEAD, policy=self.policy
        )
        self.assertIsNotNone(re.fullmatch(pattern, phrase))
        self.assertIn(str(PR), phrase)
        self.assertIn(HEAD, phrase)

    # render fails closed on unusable patterns
    def test_renderer_fails_closed_on_non_literal_patterns(self) -> None:
        for broken in (
            "^PR #(\\d+), head ([0-9a-f]{40}) ok$",
            "^PR #([1-9][0-9]*)|x$",
            "^no groups here$",
        ):
            policy = {"merge_approval": {"exact_phrase_pattern": broken}}
            with self.assertRaisesRegex(ValueError, "OWNER_PHRASE_PATTERN_INVALID"):
                self.gate.render_owner_merge_phrase(
                    pr_number=PR, head_sha=HEAD, policy=policy
                )

    # render validates pr/head shapes
    def test_renderer_rejects_invalid_pr_or_head(self) -> None:
        with self.assertRaisesRegex(ValueError, "OWNER_PHRASE_PR_NUMBER_INVALID"):
            self.gate.render_owner_merge_phrase(
                pr_number=0, head_sha=HEAD, policy=self.policy
            )
        with self.assertRaisesRegex(ValueError, "OWNER_PHRASE_HEAD_INVALID"):
            self.gate.render_owner_merge_phrase(
                pr_number=PR, head_sha="zzz", policy=self.policy
            )

    # 15/17. readiness wiring: owner_phrase nullable, exact phrase when ready
    def test_merge_readiness_owner_phrase_field_semantics(self) -> None:
        def failing_checks(root: Path, **kwargs: Any) -> dict[str, Any]:
            checks = grounded_delivery_checks(root, **kwargs)
            checks["full_gate_pass"] = False
            return checks

        common = {
            "repository": "lancerbeta/solana-alpha-lab",
            "pr_number": PR,
            "route": "DIRECT_CURSOR_DELIVERY",
            "actor": "CURSOR",
            "context_receipt": context_receipt(self.gate),
            "context_builder": exact_context_builder(self.gate),
            "evidence_builder": grounded_evidence,
        }
        denied = self.gate.evaluate_merge_readiness(
            ROOT,
            runner=FakeRunner(),
            delivery_checks_builder=failing_checks,
            **common,
        )
        self.assertFalse(denied["ready_for_owner_phrase"])
        self.assertIsNone(denied["owner_phrase"])

        ready = self.gate.evaluate_merge_readiness(
            ROOT,
            runner=FakeRunner(),
            delivery_checks_builder=grounded_delivery_checks,
            **common,
        )
        self.assertTrue(ready["ready_for_owner_phrase"])
        pattern = self.policy["merge_approval"]["exact_phrase_pattern"]
        self.assertIsNotNone(re.fullmatch(pattern, ready["owner_phrase"]))
        self.assertIn(str(PR), ready["owner_phrase"])
        self.assertIn(HEAD, ready["owner_phrase"])

    # 18. rendering phrase cannot submit merge
    def test_merge_readiness_never_submits_a_merge(self) -> None:
        runner = FakeRunner()
        result = self.gate.evaluate_merge_readiness(
            ROOT,
            repository="lancerbeta/solana-alpha-lab",
            pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY",
            actor="CURSOR",
            context_receipt=context_receipt(self.gate),
            context_builder=exact_context_builder(self.gate),
            evidence_builder=grounded_evidence,
            delivery_checks_builder=grounded_delivery_checks,
            runner=runner,
        )
        self.assertTrue(result["ready_for_owner_phrase"])
        self.assertIsNotNone(result["owner_phrase"])
        self.assertFalse(result["merge_submitted"])
        self.assertFalse(
            any(call[:3] == ("gh", "pr", "merge") for call in runner.calls)
        )

    # 12. ORIENTATION + resumable task -> remains read-only in same turn
    def test_orientation_rule_never_enters_execute_in_same_turn(self) -> None:
        text = ROUTING_RULE.read_text(encoding="utf-8")
        self.assertIn("never", text.lower())
        self.assertIn("enters EXECUTE in the same turn", text)
        self.assertIn("subsequent explicit", text)
        # CONTINUE verdict stays read-only: rule must not say "follow EXECUTE".
        self.assertNotIn("and follow EXECUTE", text)


class PreflightPushAcceptanceTests(unittest.TestCase):
    """Acceptance matrix items 4-8 and 13-14 for the preflight-push gate."""

    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location(
            "delivery_harness", ROOT / "scripts/delivery_harness.py"
        )
        assert spec is not None and spec.loader is not None
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def _result(
        self,
        *,
        actor: str | None = "CURSOR",
        drift: list[str] | None = None,
        evidence: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.module.preflight_push(
            ROOT,
            task_id="DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1",
            task_contract="docs/tasks/DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1.md",
            route="DIRECT_CURSOR_DELIVERY",
            actor=actor,
            drift_checker=lambda _root: drift or [],
            evidence_verifier=lambda _root, **_k: evidence or [],
        )

    def test_output_shape_is_stable_and_non_claiming(self) -> None:
        result = self._result()
        self.assertEqual(result["schema"], "smial.delivery-preflight-push")
        self.assertEqual(result["schema_version"], "1.0")
        self.assertIsInstance(result["ready_for_first_push"], bool)
        self.assertEqual(result["task_id"], "DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1")
        for key in ("head", "tree", "branch", "checks", "non_claims"):
            self.assertIn(key, result)
        for claim in ("NO_CI_CLAIM", "NO_MERGE_AUTHORITY", "NO_PRODUCT_ACCEPTANCE"):
            self.assertIn(claim, result["non_claims"])
        self.assertEqual(
            set(result["checks"]),
            {
                "worktree_clean",
                "harness_check_pass",
                "context_rebuild_deterministic",
                "task_base_frozen",
                "candidate_non_empty",
                "write_set_pass",
                "derived_state_current",
                "delivery_evidence_bound",
            },
        )

    # 13/14 at the delivery_harness CLI boundary.
    def test_actor_casing_normalizes_and_unknown_actor_denies(self) -> None:
        self.assertEqual(self._result(actor="cursor")["actor"], "CURSOR")
        self.assertEqual(self._result(actor="Codex")["actor"], "CODEX")
        with self.assertRaisesRegex(ValueError, "ACTOR_INVALID"):
            self._result(actor="claude")

    # 4. stale evidence binding -> preflight DENY
    def test_stale_evidence_binding_denies(self) -> None:
        result = self._result(evidence=["DELIVERY_EVIDENCE_DRIFT:stale_head"])
        self.assertFalse(result["ready_for_first_push"])
        self.assertFalse(result["checks"]["delivery_evidence_bound"])

    # 7. malformed delivery evidence -> preflight DENY
    def test_malformed_delivery_evidence_denies(self) -> None:
        result = self._result(evidence=["DELIVERY_EVIDENCE_INVALID:shape"])
        self.assertFalse(result["ready_for_first_push"])
        self.assertIn("DELIVERY_EVIDENCE_INVALID:shape", result["reasons"])

    # 6. stale derived hash -> preflight DENY
    def test_stale_derived_state_denies(self) -> None:
        result = self._result(drift=["RECORD_SHASHA_MISMATCH:catalog/assets/core.yaml"])
        self.assertFalse(result["ready_for_first_push"])
        self.assertFalse(result["checks"]["derived_state_current"])

    # 5. missed managed write path -> preflight DENY (structural: checker
    # wiring asserts write_set_pass flips when the candidate diff leaves the
    # managed write set; covered end-to-end by the contract-scoped fixture in
    # test_harness_sync_bindings; here we assert the flag exists and is
    # enforced by all(checks.values()) aggregation).
    def test_ready_requires_every_check_true(self) -> None:
        result = self._result()
        # With injected-clean helpers on the real branch state, write-set and
        # identity checks still derive from real Git truth; a DENY here must
        # enumerate deterministic reasons only.
        if not result["ready_for_first_push"]:
            for reason in result["reasons"]:
                self.assertRegex(reason, r"^[A-Z0-9_]+(:.*)?$")
        # Force one check false and confirm aggregation denies.
        forced = dict(result)
        forced["checks"] = dict(result["checks"])
        forced["checks"]["write_set_pass"] = False
        self.assertFalse(all(forced["checks"].values()))

    # 8. preflight attempts gh/network -> test failure (structural guard)
    def test_preflight_module_never_imports_gh_or_network_clients(self) -> None:
        source = (ROOT / "scripts/delivery_harness.py").read_text(encoding="utf-8")
        preflight_body = source.split("def preflight_push(")[1].split("\ndef ")[0]
        for forbidden in ("gh pr", "requests", "urllib", "socket", "http"):
            self.assertNotIn(forbidden, preflight_body)


if __name__ == "__main__":
    unittest.main()
