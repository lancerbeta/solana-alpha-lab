from __future__ import annotations

import importlib.util
import hashlib
import json
import unittest
from pathlib import Path
from types import ModuleType

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/owner_attention_gate.py"
POLICY = yaml.safe_load((ROOT / "control/owner_attention_gate_v2.yaml").read_text(encoding="utf-8"))
HEAD = "abcdef0123456789abcdef0123456789abcdef01"
MAIN = "1234567890abcdef1234567890abcdef12345678"
TREE = "fedcba9876543210fedcba9876543210fedcba98"
PR = 102
PHRASE = f"PR #{PR}, head {HEAD} проверен; ready + merge разрешаю."


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("delivery_merge_guard", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("merge guard not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self, *, head: str = HEAD, failed_check: bool = False, unresolved_review: bool = False) -> None:
        self.head = head
        self.failed_check = failed_check
        self.unresolved_review = unresolved_review
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args: list[str], cwd: Path) -> bytes:
        self.calls.append(tuple(args))
        command = tuple(args)
        if command[:3] == ("git", "remote", "get-url"):
            return b"git@github.com:lancerbeta/solana-alpha-lab.git\n"
        if command[:3] == ("git", "rev-parse", "HEAD"):
            return (self.head + "\n").encode()
        if command[:3] == ("git", "rev-parse", "HEAD^{tree}"):
            return (TREE + "\n").encode()
        if command[:3] == ("git", "status", "--porcelain=v1"):
            return b""
        if command[:3] == ("gh", "pr", "view"):
            if "state,mergedAt,mergeCommit" in command:
                return json.dumps({"state": "MERGED", "mergedAt": "2026-08-14T12:00:00Z", "mergeCommit": {"oid": MAIN}}).encode()
            return json.dumps({
                "number": PR, "headRefOid": self.head, "mergeable": "MERGEABLE",
                "reviewDecision": "APPROVED", "state": "OPEN", "isDraft": False,
            }).encode()
        if command[:3] == ("gh", "pr", "checks"):
            state = "FAILURE" if self.failed_check else "SUCCESS"
            bucket = "fail" if self.failed_check else "pass"
            return json.dumps([{"name": "Repository validation", "state": state, "bucket": bucket}]).encode()
        if command[:3] == ("gh", "api", "graphql"):
            return json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"isResolved": not self.unresolved_review}], "pageInfo": {"hasNextPage": False}}}}}}).encode()
        if command[:3] == ("gh", "pr", "merge"):
            return b""
        raise AssertionError(command)


def context_receipt(module: ModuleType, route: str = "DIRECT_CURSOR_DELIVERY") -> dict[str, object]:
    task_path = ROOT / "docs/tasks/CTRL-DELIVERY-HARNESS-V1.md"
    evidence_path = ROOT / "docs/evidence/control/delivery_harness_acceptance_v1.json"
    receipt: dict[str, object] = {
        "schema": "smial.delivery-context-receipt",
        "schema_version": "1.0",
        "harness_id": "DELIVERY_HARNESS_V1",
        "route": route,
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "repository": {"name": "lancerbeta/solana-alpha-lab", "head": HEAD, "tree": TREE, "branch": "candidate", "dirty": False},
        "task": {"task_id": "CTRL-DELIVERY-HARNESS-V1", "path": "docs/tasks/CTRL-DELIVERY-HARNESS-V1.md", "sha256": hashlib.sha256(task_path.read_bytes()).hexdigest()},
        "selected": [{
            "semantic_role": "DELIVERY_EVIDENCE", "lane": "L2", "truth_owner": "EXACT_CANDIDATE_EVIDENCE",
            "path": "docs/evidence/control/delivery_harness_acceptance_v1.json", "stable_id": None,
            "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(), "state": "RESOLVED", "inclusion": "METADATA_ONLY",
        }],
        "gaps": [],
        "budgets": {"agents_max_bytes": 12288, "cursor_always_apply_max_bytes": 6144, "ordinary_receipt_max_bytes": 49152, "auto_inline_file_max_bytes": 102400},
    }
    receipt["receipt_sha256"] = module.sha256_bytes(module.canonical_json_bytes(receipt))
    return receipt


class DeliveryHarnessMergeGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_live_readback_builds_closed_request_bound_to_route_and_context(self) -> None:
        runner = FakeRunner()
        result = self.module.build_grounded_merge_request(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
            context_receipt=context_receipt(self.module),
            runner=runner,
        )
        self.assertEqual(result["merge_checks"]["observed_head_sha"], HEAD)
        self.assertEqual(result["merge_checks"]["context_receipt_sha256"], result["owner_approval"]["context_receipt_sha256"])
        self.assertEqual(result["merge_checks"]["context_route"], "DIRECT_CURSOR_DELIVERY")
        self.assertTrue(result["merge_checks"]["factory_fit_pass"])
        self.assertEqual(self.module.evaluate(result, POLICY)["decision"], "AUTONOMOUS")
        self.assertTrue(any(call[:3] == ("gh", "pr", "view") for call in runner.calls))

    def test_stale_context_or_failed_live_ci_is_denied(self) -> None:
        for runner, receipt in (
            (FakeRunner(failed_check=True), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
            (FakeRunner(), context_receipt(self.module, "DIRECT_CURSOR_DELIVERY")),
            (FakeRunner(unresolved_review=True), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
        ):
            with self.subTest(runner=runner):
                request = self.module.build_grounded_merge_request(
                    ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                    route="DIRECT_CODEX_DELIVERY", actor="CODEX", approval_phrase=PHRASE,
                    context_receipt=receipt,
                    runner=runner,
                )
                self.assertEqual(self.module.evaluate(request, POLICY)["decision"], "DENY")

    def test_tampered_context_receipt_is_rejected_before_github_merge_decision(self) -> None:
        receipt = context_receipt(self.module)
        receipt["repository"]["branch"] = "tampered"
        with self.assertRaisesRegex(ValueError, "CONTEXT_RECEIPT_HASH_MISMATCH"):
            self.module.build_grounded_merge_request(
                ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
                context_receipt=receipt, runner=FakeRunner(),
            )

    def test_executable_guard_submits_one_standard_merge_after_live_gate(self) -> None:
        runner = FakeRunner()
        result = self.module.execute_guarded_merge(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
            context_receipt=context_receipt(self.module), runner=runner,
        )
        self.assertTrue(result["merge_submitted"])
        self.assertEqual(result["merge_commit"], MAIN)
        merge_calls = [call for call in runner.calls if call[:3] == ("gh", "pr", "merge")]
        self.assertEqual(merge_calls, [("gh", "pr", "merge", str(PR), "--repo", "lancerbeta/solana-alpha-lab", "--merge")])
        self.assertNotIn("--delete-branch", merge_calls[0])

    def test_executable_guard_does_not_call_merge_when_live_gate_denies(self) -> None:
        runner = FakeRunner(failed_check=True)
        result = self.module.execute_guarded_merge(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
            context_receipt=context_receipt(self.module), runner=runner,
        )
        self.assertFalse(result["merge_submitted"])
        self.assertFalse(any(call[:3] == ("gh", "pr", "merge") for call in runner.calls))

    def test_post_merge_receipt_is_hash_bound_to_live_main_and_ci(self) -> None:
        runner = FakeRunner()
        receipt = self.module.build_post_merge_receipt(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            approved_head=HEAD, expected_main=MAIN,
            runner=lambda args, cwd: (
                (MAIN + "\n").encode() if args[:3] == ["git", "rev-parse", "origin/main"]
                else json.dumps([{"headSha": MAIN, "status": "completed", "conclusion": "success", "databaseId": 77}]).encode()
            ),
        )
        unsigned = dict(receipt); observed = unsigned.pop("receipt_sha256")
        self.assertEqual(observed, self.module.sha256_bytes(self.module.canonical_json_bytes(unsigned)))
        self.assertEqual(receipt["main_ci"]["conclusion"], "success")


if __name__ == "__main__":
    unittest.main()
