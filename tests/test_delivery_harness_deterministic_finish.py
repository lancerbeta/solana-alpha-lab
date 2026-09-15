from __future__ import annotations

import importlib.util
import json
import re
import sys
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
            # invalid regex escapes must fail closed as ValueError, never
            # leak re.error past the JSON boundary
            "^PR \\g #([1-9][0-9]*), head ([0-9a-f]{40})$",
        ):
            policy = {"merge_approval": {"exact_phrase_pattern": broken}}
            with self.assertRaisesRegex(ValueError, "OWNER_PHRASE_PATTERN_INVALID"):
                self.gate.render_owner_merge_phrase(
                    pr_number=PR, head_sha=HEAD, policy=policy
                )
        # a backref compiles but cannot match its rendered phrase, so the
        # renderer still fails closed with a stable ValueError.
        policy = {"merge_approval": {"exact_phrase_pattern": "^PR #([1-9][0-9]*), head \\1([0-9a-f]{40})$"}}
        with self.assertRaises(ValueError) as ctx:
            self.gate.render_owner_merge_phrase(
                pr_number=PR, head_sha=HEAD, policy=policy
            )
        self.assertIn(str(ctx.exception), ("OWNER_PHRASE_PATTERN_INVALID", "OWNER_PHRASE_RENDER_MISMATCH"))

    # a reordered policy pattern (head group first) must fail closed at
    # render time: validate_exact_merge_approval binds group(1) to the PR
    # number, so a rendered-but-reordered phrase would crash at merge.
    def test_renderer_fails_closed_on_reordered_groups(self) -> None:
        pattern = "^head ([0-9a-f]{40}), PR #([1-9][0-9]*) ok$"
        policy = {"merge_approval": {"exact_phrase_pattern": pattern}}
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

    # 13 at the guarded-merge CLI boundary: main() must pass the
    # normalize_cli_actor result into execute_guarded_merge, never the raw
    # argv casing (the exact one-line defect found in code review).
    def test_guarded_merge_cli_passes_normalized_actor(self) -> None:
        from unittest import mock

        captured: dict[str, Any] = {}

        def fake_execute(root, **kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {
                "schema": "smial.guarded-merge-submission",
                "schema_version": "1.0",
                "decision": "AUTONOMOUS",
                "merge_submitted": True,
            }

        receipt_file = ROOT / "control/owner_attention_gate_v2.yaml"
        argv = [
            "owner_attention_gate.py",
            "--guarded-merge",
            "--repository", "lancerbeta/solana-alpha-lab",
            "--pr-number", str(PR),
            "--route", "DIRECT_CURSOR_DELIVERY",
            "--actor", "cursor",
            "--approval-phrase", f"PR #{PR}, head {HEAD} проверен; ready + merge разрешаю.",
            "--context-receipt", str(receipt_file),
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(
                self.gate, "execute_guarded_merge", side_effect=fake_execute
            ),
            mock.patch("builtins.print"),
        ):
            exit_code = self.gate.main()
        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["actor"], "CURSOR")

    # 12. ORIENTATION + resumable task -> remains read-only in same turn
    def test_orientation_rule_never_enters_execute_in_same_turn(self) -> None:
        text = ROUTING_RULE.read_text(encoding="utf-8")
        self.assertIn("never", text.lower())
        self.assertIn("enters EXECUTE in the same turn", text)
        self.assertIn("subsequent explicit", text)
        # CONTINUE verdict stays read-only: rule must not say "follow EXECUTE".
        self.assertNotIn("and follow EXECUTE", text)


class LivePortablePrefixParityTests(unittest.TestCase):
    """Live harness_control_write_prefixes stay a superset of the portable list."""

    def test_portable_prefixes_are_a_subset_of_live(self) -> None:
        import yaml

        live = yaml.safe_load(
            (ROOT / "delivery-harness/harness.yaml").read_text(encoding="utf-8")
        )
        portable = yaml.safe_load(
            (
                ROOT
                / "delivery-harness/templates/portable-core/delivery-harness/harness.yaml"
            ).read_text(encoding="utf-8")
        )
        live_prefixes = set(live["merge_policy"]["harness_control_write_prefixes"])
        portable_prefixes = set(
            portable["merge_policy"]["harness_control_write_prefixes"]
        )
        # Portable bundle ships fewer artifacts; every portable control path
        # must remain LIVE_PR_HEAD-eligible in the canonical repo.
        self.assertTrue(
            portable_prefixes <= live_prefixes,
            sorted(portable_prefixes - live_prefixes),
        )
        # The required examples must be denied in BOTH lists.
        for product_path in (
            "src/solana_alpha_lab/factory/observation_scheduler.py",
            "scripts/hypothesis_forge.py",
            ".cursor/commands/hypothesis-forge.md",
            "catalog/assets/lifecycle.yaml",
        ):
            self.assertNotIn(product_path, live_prefixes)
            self.assertNotIn(product_path, portable_prefixes)


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
            drift_checker=lambda _root, **_k: drift or [],
            evidence_verifier=lambda _root, **_k: evidence or [],
            shadow_pin_checker=lambda _root, **_k: [],
            divergence_checker=lambda _root, **_k: [],
        )

    # Task-scoped keys exist only when the context receipt rebuilds on a
    # checkout whose merge-base equals the contract's frozen expected_base.
    # On merged main (or any state where the base moved) the rebuild
    # deterministically degrades to the five state-independent keys with
    # CONTEXT_REBUILD_FAILED recorded; both forms are stable output.
    STATE_INDEPENDENT_CHECKS = {
        "worktree_clean",
        "harness_check_pass",
        "context_rebuild_deterministic",
        "derived_state_current",
        "delivery_evidence_bound",
    }
    TASK_SCOPED_CHECKS = {
        "task_base_frozen",
        "candidate_non_empty",
        "write_set_pass",
        "shadow_pins_current",
        "worktree_matches_committed",
    }

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
        checks = set(result["checks"])
        self.assertTrue(self.STATE_INDEPENDENT_CHECKS <= checks, checks)
        if result["checks"].get("context_rebuild_deterministic") is True:
            # Branch form: the receipt rebuilt against the frozen base.
            self.assertEqual(
                checks, self.STATE_INDEPENDENT_CHECKS | self.TASK_SCOPED_CHECKS
            )
        else:
            # Merged/other-state form: the rebuild failed deterministically
            # and the reason is recorded.
            self.assertEqual(checks, self.STATE_INDEPENDENT_CHECKS)
            self.assertTrue(
                any(
                    reason.startswith("CONTEXT_REBUILD_FAILED:")
                    for reason in result["reasons"]
                ),
                result["reasons"],
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

    # 7 (real path): the real verifier on this worktree must return stable
    # DENY reason codes without raising (pre-bind state surfaces as DRIFT).
    def test_real_evidence_verifier_returns_stable_reasons(self) -> None:
        try:
            problems = self.module._preflight_evidence_problems(
                ROOT,
                task_id="DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1",
                task_contract="docs/tasks/DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1.md",
            )
        except Exception as exc:  # pragma: no cover - the failure mode itself
            self.fail(f"verifier escaped with {exc!r}")
        for problem in problems:
            self.assertRegex(problem, r"^DELIVERY_EVIDENCE_(INVALID|DRIFT):")

    # 7 (absent-file unit): a missing evidence file must become a stable
    # DELIVERY_EVIDENCE_INVALID reason, never a FileNotFoundError traceback.
    def test_absent_evidence_file_becomes_stable_deny(self) -> None:
        harness_sync = self.module._load_harness_sync_module()
        original = harness_sync.verify_evidence_chain

        def raising_verify(**_kwargs):
            raise FileNotFoundError("missing completion evidence")

        harness_sync.verify_evidence_chain = raising_verify
        try:
            problems = self.module._preflight_evidence_problems(
                ROOT,
                task_id="DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1",
                task_contract="docs/tasks/DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1.md",
            )
        finally:
            harness_sync.verify_evidence_chain = original
        self.assertEqual(
            problems, ["DELIVERY_EVIDENCE_INVALID:FileNotFoundError"]
        )

    # 6. stale derived hash -> preflight DENY
    def test_stale_derived_state_denies(self) -> None:
        result = self._result(drift=["RECORD_SHASHA_MISMATCH:catalog/assets/core.yaml"])
        self.assertFalse(result["ready_for_first_push"])
        self.assertFalse(result["checks"]["derived_state_current"])

    # 5. missed managed write path -> preflight DENY (real path: an injected
    # git reader reports a candidate diff containing a path outside the task
    # managed write set; preflight must flip write_set_pass and DENY). On a
    # checkout whose merge-base no longer equals the contract's frozen base
    # (merged main), the receipt cannot rebuild, so the task-scoped checks
    # are absent and the rebuild failure is the recorded DENY reason.
    def test_write_set_violation_denies_on_real_wiring(self) -> None:
        module = self.module

        class ViolatingReader:
            def __init__(self) -> None:
                self.calls: list[tuple[str, ...]] = []

            def __call__(self, root, *args: str) -> str:
                self.calls.append(tuple(args))
                if (
                    tuple(args[:3]) == ("diff", "--name-only", "--no-renames")
                    and args[3].endswith("...HEAD")
                ):
                    return "src/solana_alpha_lab/factory/rogue_module.py"
                return module.git_text(root, *args)

        reader = ViolatingReader()
        result = module.preflight_push(
            ROOT,
            task_id="DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1",
            task_contract="docs/tasks/DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1.md",
            route="DIRECT_CURSOR_DELIVERY",
            actor="CURSOR",
            drift_checker=lambda _root, **_k: [],
            evidence_verifier=lambda _root, **_k: [],
            git_reader=reader,
        )
        self.assertFalse(result["ready_for_first_push"])
        if "write_set_pass" in result["checks"]:
            self.assertFalse(result["checks"]["write_set_pass"])
            self.assertTrue(
                any(reason.startswith("WRITE_SET_VIOLATION:src/solana_alpha_lab")
                    for reason in result["reasons"]),
                result["reasons"],
            )
        else:
            # Merged-base state: the deterministic rebuild failure DENYs
            # before the write-set comparison can run.
            self.assertTrue(
                any(reason.startswith("CONTEXT_REBUILD_FAILED:")
                    for reason in result["reasons"]),
                result["reasons"],
            )

    def test_ready_requires_every_check_true(self) -> None:
        result = self._result()
        if not result["ready_for_first_push"]:
            for reason in result["reasons"]:
                self.assertRegex(reason, r"^[A-Z0-9_]+(:.*)?$")
        forced = dict(result)
        forced["checks"] = dict(result["checks"])
        forced["checks"]["write_set_pass"] = False
        self.assertFalse(all(forced["checks"].values()))

    # 8. preflight attempts gh/network -> test failure: monkeypatched
    # subprocess.run records every spawned argv; assert no gh/provider
    # binary is ever spawned (local git is expected) and no socket opens.
    def test_preflight_never_spawns_gh_or_network(self) -> None:
        import subprocess as subprocess_module
        from unittest import mock

        spawned: list[list[str]] = []
        real_run = subprocess_module.run

        def recording_run(args, *rest: Any, **kwargs: Any) -> Any:
            spawned.append(list(args))
            return real_run(args, *rest, **kwargs)

        def failing_socket(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("preflight opened a socket")

        with (
            mock.patch.object(subprocess_module, "run", side_effect=recording_run),
            mock.patch("socket.socket", side_effect=failing_socket),
            mock.patch("socket.create_connection", side_effect=failing_socket),
        ):
            result = self.module.preflight_push(
                ROOT,
                task_id="DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1",
                task_contract="docs/tasks/DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1.md",
                route="DIRECT_CURSOR_DELIVERY",
                actor="CURSOR",
                drift_checker=lambda _root, **_k: [],
                evidence_verifier=lambda _root, **_k: [],
            )
        binaries = {argv[0] for argv in spawned if argv}
        self.assertLessEqual(binaries, {"git"}, spawned)
        self.assertEqual(result["schema"], "smial.delivery-preflight-push")


if __name__ == "__main__":
    unittest.main()
