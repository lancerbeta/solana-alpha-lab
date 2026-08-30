from __future__ import annotations

import copy
import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/owner_attention_gate.py"
POLICY = yaml.safe_load((ROOT / "control/owner_attention_gate_v2.yaml").read_text(encoding="utf-8"))
HEAD = "abcdef0123456789abcdef0123456789abcdef01"
MAIN = "1234567890abcdef1234567890abcdef12345678"
BASE = "e78a08ec7ce5687c89b39fa19d8503ca206c6d9e"
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
    def __init__(
        self,
        *,
        head: str = HEAD,
        check_state: str = "SUCCESS",
        unresolved_review: bool = False,
        review_decision: str | None = "APPROVED",
        delete_branch_on_merge: bool = False,
        origin: str = "git@github.com:lancerbeta/solana-alpha-lab.git",
        base_ref_name: str = "main",
        pr_number: int = PR,
        head_branch_preserved: bool = True,
        ci_head: str | None = None,
        upstream_oid: str = BASE,
        include_older_success: bool = False,
        postmerge_latest_failure: bool = False,
        flip_head_after_policy_reads: int | None = None,
        default_branch: str = "main",
        base_mismatch_path: str | None = None,
        postmerge_default_oid: str | None = None,
    ) -> None:
        self.head = head
        self.check_state = check_state
        self.unresolved_review = unresolved_review
        self.review_decision = review_decision
        self.delete_branch_on_merge = delete_branch_on_merge
        self.origin = origin
        self.base_ref_name = base_ref_name
        self.pr_number = pr_number
        self.head_branch_preserved = head_branch_preserved
        self.ci_head = head if ci_head is None else ci_head
        self.upstream_oid = upstream_oid
        self.include_older_success = include_older_success
        self.postmerge_latest_failure = postmerge_latest_failure
        self.flip_head_after_policy_reads = flip_head_after_policy_reads
        self.default_branch = default_branch
        self.base_mismatch_path = base_mismatch_path
        self.postmerge_default_oid = MAIN if postmerge_default_oid is None else postmerge_default_oid
        self.policy_reads = 0
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args: list[str], cwd: Path) -> bytes:
        self.calls.append(tuple(args))
        command = tuple(args)
        if command[:3] == ("git", "remote", "get-url"):
            return (self.origin + "\n").encode()
        if command[:3] == ("git", "rev-parse", "HEAD"):
            return (self.head + "\n").encode()
        if command[:3] == ("git", "rev-parse", f"origin/{self.default_branch}"):
            return (self.upstream_oid + "\n").encode()
        if command[:4] == ("git", "merge-base", "HEAD", f"origin/{self.default_branch}"):
            return (self.upstream_oid + "\n").encode()
        if command[:3] == ("git", "rev-parse", "HEAD^{tree}"):
            return (TREE + "\n").encode()
        if command[:3] == ("git", "status", "--porcelain=v1"):
            return b""
        if command[:2] == ("git", "show"):
            relative = command[2].split(":", 1)[1]
            if relative == self.base_mismatch_path:
                return b"base-mismatch\n"
            payload = (ROOT / relative).read_bytes()
            if relative == "control/owner_attention_gate_v2.yaml":
                self.policy_reads += 1
                if self.flip_head_after_policy_reads == self.policy_reads:
                    self.head = "0" * 40
            return payload
        if command[:3] == ("gh", "pr", "view"):
            if any("mergedAt" in item for item in command):
                return json.dumps({
                    "number": self.pr_number, "state": "MERGED",
                    "mergedAt": "2026-08-14T12:00:00Z",
                    "headRefOid": self.head, "headRefName": "candidate",
                    "baseRefName": self.base_ref_name,
                    "mergeCommit": {"oid": MAIN},
                }).encode()
            return json.dumps({
                "number": self.pr_number, "headRefOid": self.head,
                "headRefName": "candidate", "baseRefName": self.base_ref_name,
                "mergeable": "MERGEABLE",
                "reviewDecision": self.review_decision, "state": "OPEN", "isDraft": False,
            }).encode()
        if command[:3] == ("gh", "pr", "checks"):
            bucket = "pass" if self.check_state == "SUCCESS" else ("skipping" if self.check_state == "SKIPPED" else "fail")
            return json.dumps([{
                "name": "validate", "workflow": "Repository validation",
                "state": self.check_state, "bucket": bucket,
            }]).encode()
        if command[:3] == ("gh", "api", "graphql"):
            blob = " ".join(command)
            if "checkRuns" in blob:
                oid = next(
                    (item[4:] for item in command if item.startswith("oid=")),
                    "",
                )
                conclusion = "SUCCESS" if self.check_state == "SUCCESS" else "FAILURE"
                suites: list[dict[str, object]] = []
                if oid in {self.head, self.ci_head, HEAD}:
                    suites.append({
                        "workflowRun": {"databaseId": 76},
                        "checkRuns": {
                            "pageInfo": {"hasNextPage": False},
                            "nodes": [{
                                "name": "validate",
                                "status": "COMPLETED",
                                "conclusion": conclusion,
                            }],
                        },
                    })
                if oid == MAIN:
                    if self.postmerge_latest_failure:
                        suites.append({
                            "workflowRun": {"databaseId": 78},
                            "checkRuns": {
                                "pageInfo": {"hasNextPage": False},
                                "nodes": [{
                                    "name": "validate",
                                    "status": "COMPLETED",
                                    "conclusion": "FAILURE",
                                }],
                            },
                        })
                    suites.append({
                        "workflowRun": {"databaseId": 77},
                        "checkRuns": {
                            "pageInfo": {"hasNextPage": False},
                            "nodes": [{
                                "name": "validate",
                                "status": "COMPLETED",
                                "conclusion": "SUCCESS",
                            }],
                        },
                    })
                return json.dumps({
                    "data": {
                        "repository": {
                            "object": {
                                "checkSuites": {
                                    "pageInfo": {"hasNextPage": False},
                                    "nodes": suites,
                                }
                            }
                        }
                    }
                }).encode()
            return json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"isResolved": not self.unresolved_review}], "pageInfo": {"hasNextPage": False}}}}}}).encode()
        if command[:2] == ("gh", "api") and command[2] == "repos/lancerbeta/solana-alpha-lab":
            return json.dumps({"delete_branch_on_merge": self.delete_branch_on_merge}).encode()
        if command[:3] == ("gh", "pr", "merge"):
            return b""
        if command[:3] == ("git", "ls-remote", "--heads"):
            return f"{self.upstream_oid}\trefs/heads/{self.default_branch}\n".encode()
        if command[:2] == ("git", "ls-remote"):
            if command[-1] == f"refs/heads/{self.default_branch}":
                return (
                    f"{self.postmerge_default_oid}\t"
                    f"refs/heads/{self.default_branch}\n"
                ).encode()
            if command[-1] == "refs/heads/candidate" and self.head_branch_preserved:
                return f"{HEAD}\trefs/heads/candidate\n".encode()
            return b""
        if command[:2] == ("git", "fetch"):
            return b""
        if command[:5] == ("git", "--no-replace-objects", "rev-list", "--parents", "-n"):
            return f"{MAIN} {self.upstream_oid} {HEAD}\n".encode()
        if command[:3] == ("gh", "run", "list"):
            if self.head in command:
                runs = [{
                    "headSha": self.ci_head,
                    "status": "completed",
                    "conclusion": "success" if self.check_state == "SUCCESS" else "failure",
                    "databaseId": 76,
                    "event": "pull_request",
                    "workflowName": "Repository validation",
                }]
                if self.include_older_success:
                    runs.append({
                        "headSha": self.ci_head,
                        "status": "completed",
                        "conclusion": "success",
                        "databaseId": 75,
                        "event": "pull_request",
                        "workflowName": "Repository validation",
                    })
                return json.dumps(runs).encode()
            runs = [{
                "headSha": MAIN, "status": "completed", "conclusion": "success",
                "databaseId": 77, "event": "push", "workflowName": "Repository validation",
            }]
            if self.postmerge_latest_failure:
                runs.insert(0, {
                    "headSha": MAIN, "status": "completed", "conclusion": "failure",
                    "databaseId": 78, "event": "push", "workflowName": "Repository validation",
                })
            return json.dumps(runs).encode()
        if command[:3] == ("gh", "run", "view"):
            if command[3] == "78":
                return json.dumps({
                    "headSha": MAIN,
                    "status": "completed",
                    "conclusion": "failure",
                    "event": "push",
                    "workflowName": "Repository validation",
                    "jobs": [{
                        "name": "validate",
                        "status": "completed",
                        "conclusion": "failure",
                        "databaseId": 703,
                    }],
                }).encode()
            if command[3] == "77":
                return json.dumps({
                    "headSha": MAIN,
                    "status": "completed",
                    "conclusion": "success",
                    "event": "push",
                    "workflowName": "Repository validation",
                    "jobs": [{
                        "name": "validate",
                        "status": "completed",
                        "conclusion": "success",
                        "databaseId": 702,
                    }],
                }).encode()
            conclusion = "success" if self.check_state == "SUCCESS" else "failure"
            return json.dumps({
                "headSha": self.ci_head,
                "status": "completed",
                "conclusion": conclusion,
                "event": "pull_request",
                "workflowName": "Repository validation",
                "jobs": [{
                    "name": "validate",
                    "status": "completed",
                    "conclusion": conclusion,
                    "databaseId": 701,
                }],
            }).encode()
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


def live_pr_head_receipt(
    module: ModuleType,
    route: str = "DIRECT_CURSOR_DELIVERY",
    *,
    pr_number: int = PR,
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema": "smial.delivery-context-receipt",
        "schema_version": "1.0",
        "harness_id": "DELIVERY_HARNESS_V1",
        "route": route,
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "repository": {
            "name": "lancerbeta/solana-alpha-lab",
            "head": HEAD,
            "tree": TREE,
            "branch": "candidate",
            "dirty": False,
        },
        "control_pr": {"pr_number": pr_number, "identity_mode": "LIVE_PR_HEAD"},
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


def exact_live_pr_builder(module: ModuleType, receipt: dict[str, object]):
    def build(root: Path, *, task_id: str, task_contract: str, route: str) -> dict[str, object]:
        assert task_id == "CONTROL-PR"
        assert task_contract == f"pr/{receipt['control_pr']['pr_number']}"
        self = dict(receipt)
        self["route"] = route
        unsigned = dict(self)
        unsigned.pop("receipt_sha256", None)
        self["receipt_sha256"] = module.sha256_bytes(module.canonical_json_bytes(unsigned))
        return self

    return build


def guarded_submission_receipt(
    module: ModuleType,
    *,
    route: str = "DIRECT_CURSOR_DELIVERY",
    repository: str = "lancerbeta/solana-alpha-lab",
    pr_number: int = PR,
    approved_head: str = HEAD,
    merge_commit: str = MAIN,
) -> dict[str, object]:
    context = context_receipt(module, route=route)
    receipt: dict[str, object] = {
        "schema": "smial.guarded-merge-submission",
        "schema_version": "1.0",
        "decision": "AUTONOMOUS",
        "reasons": ["OWNER_APPROVAL_MATCHED"],
        "repository": repository,
        "pr_number": pr_number,
        "approved_head": approved_head,
        "context_receipt_sha256": context["receipt_sha256"],
        "route": route,
        "merge_submitted": True,
        "merge_commit": merge_commit,
        "post_merge_ci": "PENDING_EXACT_MAIN_READBACK",
        "branch_deleted": False,
        "settings_changed": False,
    }
    receipt["receipt_sha256"] = module.sha256_bytes(
        module.canonical_json_bytes(receipt)
    )
    return receipt


def exact_context_builder(module: ModuleType):
    def build(root: Path, *, task_id: str, task_contract: str, route: str) -> dict[str, object]:
        self = context_receipt(module, route)
        assert self["task"]["task_id"] == task_id
        assert self["task"]["path"] == task_contract
        return self

    return build


def grounded_evidence(
    root: Path, receipt: dict[str, object], **_kwargs: object
) -> dict[str, object]:
    return {
        "factory_fit_pass": True,
        "active_stop_conditions": [],
        "triggers": {
            "auth_or_access_recovery": False,
            "material_owner_decision": False,
            "user_only_activation": False,
            "external_material_action": False,
            "unresolved_safety_or_truth_conflict": False,
        },
    }


def write_delivery_evidence_fixture(
    module: ModuleType,
    root: Path,
    *,
    mutate_review: object | None = None,
    mutate_fit: object | None = None,
    mutate_acceptance: object | None = None,
) -> dict[str, object]:
    implementation = root / "impl.txt"
    implementation.write_text("implementation\n", encoding="utf-8")
    evidence_dir = root / "docs/evidence"
    evidence_dir.mkdir(parents=True)
    bindings = {"impl.txt": hashlib.sha256(implementation.read_bytes()).hexdigest()}
    bindings_sha = module.sha256_bytes(module.canonical_json_bytes(bindings))
    inventory_sha = "1" * 64
    review = {
        "schema": "smial.delivery-independent-review-evidence",
        "schema_version": "1.0",
        "review_id": "REVIEW-1",
        "as_of": "2026-08-14",
        "task_id": "TEST-TASK",
        "reviewed_bindings_sha256": bindings_sha,
        "reviewed_inventory_sha256": inventory_sha,
        "required_roles": [
            "CODE_REVIEWER", "GOAL_DOD_CRITIC", "ARCHITECTURE_CRITIC"
        ],
        "reviews": [
            {"role": "CODE_REVIEWER", "verdict": "PASS", "findings": []},
            {"role": "GOAL_DOD_CRITIC", "verdict": "PASS", "findings": []},
            {"role": "ARCHITECTURE_CRITIC", "verdict": "PASS", "findings": []},
        ],
        "verdict": "PASS",
        "non_claims": ["NO_CRYPTOGRAPHIC_REVIEWER_IDENTITY"],
    }
    if callable(mutate_review):
        mutate_review(review)
    review_path = evidence_dir / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    fit = {
        "schema": "smial.delivery-harness-factory-fit",
        "schema_version": "1.0",
        "review_id": "FIT-1",
        "as_of": "2026-08-14",
        "task_id": "TEST-TASK",
        "mode": "FULL_REVIEW",
        "verdict": "PASS",
        "reviewed_bindings_sha256": bindings_sha,
        "reviewed_inventory_sha256": inventory_sha,
        "dimensions": {
            "mission": "PASS", "flexibility_and_history": "PASS",
            "context_efficiency": "PASS", "research_truth": "PASS",
            "owner_operability": "PASS", "execution_to_cashflow": "PASS",
            "monitoring_and_recovery": "PASS", "build_vs_buy": "PASS",
            "security": "PASS", "red_team": "PASS",
        },
        "capability_radar": {"now": "NONE", "watch": "TRIGGER"},
        "recovery": "REVERT",
        "limits": ["NO_PRODUCT_ACCEPTANCE"],
    }
    if callable(mutate_fit):
        mutate_fit(fit)
    fit_path = evidence_dir / "fit.json"
    fit_path.write_text(json.dumps(fit), encoding="utf-8")
    acceptance = {
        "schema": "smial.delivery-completion-evidence",
        "schema_version": "1.0",
        "acceptance_id": "ACCEPTANCE-1",
        "as_of": "2026-08-14",
        "task_id": "TEST-TASK",
        "state_change": "IMPLEMENTED_UNVERIFIED",
        "base_main": BASE,
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "cloud_bundle_required_by_harness": False,
        "cloud_bundle_smoke_required": False,
        "implementation_bindings": bindings,
        "active_stop_conditions": [],
        "owner_attention_triggers": {
            "auth_or_access_recovery": False,
            "material_owner_decision": False,
            "user_only_activation": False,
            "external_material_action": False,
            "unresolved_safety_or_truth_conflict": False,
        },
        "factory_fit": {
            "path": "docs/evidence/fit.json",
            "sha256": hashlib.sha256(fit_path.read_bytes()).hexdigest(),
            "verdict": "PASS",
        },
        "validation": {
            "targeted": "PASS_TARGETED",
            "independent_review": {
                "path": "docs/evidence/review.json",
                "sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
                "verdict": "PASS",
            },
            "full_gate": "ENFORCED_BY_PROJECT_BOUND_VALIDATION",
            "github_ci": "ENFORCED_LIVE_AT_GUARDED_MERGE",
            "project_checks": ["PASS_PROJECT"],
        },
        "non_claims": ["NO_PRODUCT_ACCEPTANCE"],
        "side_effects": {},
    }
    if callable(mutate_acceptance):
        mutate_acceptance(acceptance)
    acceptance_path = evidence_dir / "acceptance.json"
    acceptance_path.write_text(json.dumps(acceptance), encoding="utf-8")
    return {
        "task": {"task_id": "TEST-TASK"},
        "selected": [{
            "semantic_role": "DELIVERY_EVIDENCE",
            "path": "docs/evidence/acceptance.json",
            "sha256": hashlib.sha256(acceptance_path.read_bytes()).hexdigest(),
        }],
    }


def grounded_delivery_checks(
    root: Path,
    *,
    context_receipt: dict[str, object],
    local_head: str,
    local_tree: str,
    ci_pass: bool,
    runner: object,
) -> dict[str, bool]:
    return {
        "required_tests_pass": True,
        "full_gate_pass": True,
        "write_set_pass": True,
        "secret_scan_pass": True,
    }


def write_validation_profile(
    root: Path,
    *,
    primary: dict[str, object] | None,
    fallback: dict[str, object] | None,
    credential_scan: dict[str, object] | None,
) -> None:
    path = root / "delivery-harness/project-profile.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "repository": {
                    "name": "lancerbeta/solana-alpha-lab",
                    "default_branch": "main",
                },
                "validation": {
                    "github_ci_bound": True,
                    "primary": primary,
                    "fallback": fallback,
                    "credential_scan": credential_scan,
                }
            }
        ),
        encoding="utf-8",
    )
    for command in (primary, fallback, credential_scan):
        if command is None:
            continue
        for relative in command["trusted_paths"]:
            trusted = root / str(relative)
            trusted.parent.mkdir(parents=True, exist_ok=True)
            trusted.write_text("trusted validation bytes\n", encoding="utf-8")


def validation_git_read(args: list[str], root: Path) -> bytes | None:
    if args[:2] == ["git", "show"]:
        relative = args[2].split(":", 1)[1]
        return (root / relative).read_bytes()
    if args[:3] == ["git", "rev-parse", "HEAD"]:
        return (HEAD + "\n").encode()
    if args[:3] == ["git", "rev-parse", "HEAD^{tree}"]:
        return (TREE + "\n").encode()
    if args[:3] == ["git", "status", "--porcelain=v1"]:
        return b""
    return None


class DeliveryHarnessMergeGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_live_readback_builds_closed_request_bound_to_route_and_context(self) -> None:
        runner = FakeRunner(
            origin="ssh://git@github.com/lancerbeta/solana-alpha-lab.git"
        )
        result = self.module.build_grounded_merge_request(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
            context_receipt=context_receipt(self.module),
            runner=runner, context_builder=exact_context_builder(self.module),
            evidence_builder=grounded_evidence,
            delivery_checks_builder=grounded_delivery_checks,
        )
        self.assertEqual(result["merge_checks"]["observed_head_sha"], HEAD)
        self.assertEqual(result["merge_checks"]["context_receipt_sha256"], result["owner_approval"]["context_receipt_sha256"])
        self.assertEqual(result["merge_checks"]["context_route"], "DIRECT_CURSOR_DELIVERY")
        self.assertTrue(result["merge_checks"]["factory_fit_pass"])
        self.assertEqual(self.module.evaluate(result, POLICY)["decision"], "AUTONOMOUS")
        self.assertTrue(any(call[:3] == ("gh", "pr", "view") for call in runner.calls))

    def test_stale_context_or_failed_live_ci_is_denied(self) -> None:
        for runner, receipt in (
            (FakeRunner(check_state="FAILURE"), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
            (FakeRunner(check_state="SKIPPED"), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
            (FakeRunner(review_decision="CHANGES_REQUESTED"), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
            (FakeRunner(delete_branch_on_merge=True), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
            (FakeRunner(unresolved_review=True), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
            (FakeRunner(base_ref_name="release"), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
            (FakeRunner(ci_head="0" * 40), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
            (FakeRunner(check_state="FAILURE", include_older_success=True), context_receipt(self.module, "DIRECT_CODEX_DELIVERY")),
        ):
            with self.subTest(runner=runner):
                request = self.module.build_grounded_merge_request(
                    ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                    route="DIRECT_CODEX_DELIVERY", actor="CODEX", approval_phrase=PHRASE,
                    context_receipt=receipt,
                    runner=runner, context_builder=exact_context_builder(self.module),
                    evidence_builder=grounded_evidence,
                    delivery_checks_builder=grounded_delivery_checks,
                )
                self.assertEqual(self.module.evaluate(request, POLICY)["decision"], "DENY")
        with self.assertRaisesRegex(ValueError, "FROZEN_BASE_MISMATCH"):
            self.module.build_grounded_merge_request(
                ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                route="DIRECT_CODEX_DELIVERY", actor="CODEX", approval_phrase=PHRASE,
                context_receipt=context_receipt(self.module, "DIRECT_CODEX_DELIVERY"),
                runner=FakeRunner(upstream_oid="0" * 40),
                context_builder=exact_context_builder(self.module),
                evidence_builder=grounded_evidence,
                delivery_checks_builder=grounded_delivery_checks,
            )
        with self.assertRaisesRegex(ValueError, "CONTEXT_RECEIPT_LIVE_MISMATCH"):
            self.module.build_grounded_merge_request(
                ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                route="DIRECT_CODEX_DELIVERY", actor="CODEX", approval_phrase=PHRASE,
                context_receipt=context_receipt(self.module, "DIRECT_CURSOR_DELIVERY"),
                runner=FakeRunner(),
                context_builder=exact_context_builder(self.module),
                evidence_builder=grounded_evidence,
                delivery_checks_builder=grounded_delivery_checks,
            )

    def test_tampered_context_receipt_is_rejected_before_github_merge_decision(self) -> None:
        receipt = copy.deepcopy(context_receipt(self.module))
        receipt["task"]["sha256"] = "0" * 64
        for selected in receipt["selected"]:
            if selected["semantic_role"] == "DELIVERY_EVIDENCE":
                selected["sha256"] = "0" * 64
        unsigned = dict(receipt)
        unsigned.pop("receipt_sha256")
        receipt["receipt_sha256"] = self.module.sha256_bytes(
            self.module.canonical_json_bytes(unsigned)
        )
        with self.assertRaisesRegex(ValueError, "CONTEXT_RECEIPT_LIVE_MISMATCH"):
            self.module.build_grounded_merge_request(
                ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
                context_receipt=receipt, runner=FakeRunner(),
                context_builder=exact_context_builder(self.module),
                evidence_builder=grounded_evidence,
                delivery_checks_builder=grounded_delivery_checks,
            )

    def test_green_ci_cannot_substitute_for_independent_delivery_checks(self) -> None:
        for failed_key in (
            "required_tests_pass",
            "full_gate_pass",
            "write_set_pass",
            "secret_scan_pass",
        ):
            with self.subTest(failed_key=failed_key):
                def failed_delivery_checks(*args: object, **kwargs: object) -> dict[str, bool]:
                    checks = grounded_delivery_checks(*args, **kwargs)
                    checks[failed_key] = False
                    return checks

                request = self.module.build_grounded_merge_request(
                    ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                    route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
                    context_receipt=context_receipt(self.module), runner=FakeRunner(),
                    context_builder=exact_context_builder(self.module),
                    evidence_builder=grounded_evidence,
                    delivery_checks_builder=failed_delivery_checks,
                )
                self.assertTrue(request["merge_checks"]["ci_exact_head_pass"])
                self.assertFalse(request["merge_checks"][failed_key])
                self.assertEqual(self.module.evaluate(request, POLICY)["decision"], "DENY")

    def test_delivery_evidence_is_bound_to_review_quorum_fit_and_cloud_constants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = write_delivery_evidence_fixture(self.module, root)
            evidence_args = {
                "expected_base": BASE,
                "head": HEAD,
                "inventory_builder": lambda *args, **kwargs: "1" * 64,
            }
            self.assertTrue(
                self.module.bound_delivery_evidence(
                    root, receipt, **evidence_args
                )["factory_fit_pass"]
            )
            duplicate = root / "docs/evidence/acceptance-duplicate.json"
            duplicate.write_bytes((root / "docs/evidence/acceptance.json").read_bytes())
            receipt["selected"].append({
                "semantic_role": "DELIVERY_EVIDENCE",
                "path": "docs/evidence/acceptance-duplicate.json",
                "sha256": hashlib.sha256(duplicate.read_bytes()).hexdigest(),
            })
            self.assertFalse(
                self.module.bound_delivery_evidence(
                    root, receipt, **evidence_args
                )["factory_fit_pass"]
            )

        mutations = (
            {
                "mutate_review": lambda value: value.update({
                    "required_roles": ["SELF"],
                    "reviews": [{"role": "SELF", "verdict": "PASS", "findings": []}],
                })
            },
            {
                "mutate_review": lambda value: value["reviews"].append({
                    "role": "REFACTOR_CRITIC",
                    "verdict": "NOT_READY",
                    "findings": ["UNRESOLVED"],
                })
            },
            {
                "mutate_review": lambda value: value["non_claims"].append(
                    "SINGLE_AGENT_REVIEW_FALLBACK"
                )
            },
            {
                "mutate_review": lambda value: value["reviews"][2]["findings"].append(
                    "SINGLE_AGENT_REVIEW_FALLBACK_WITHOUT_ISOLATED_CONTEXT_CRITICS"
                )
            },
            {
                "mutate_fit": lambda value: value.__setitem__(
                    "reviewed_bindings_sha256", "0" * 64
                )
            },
            {
                "mutate_acceptance": lambda value: value.__setitem__(
                    "cloud_bundle_smoke_required", True
                )
            },
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = write_delivery_evidence_fixture(
                    self.module, root, **mutation
                )
                result = self.module.bound_delivery_evidence(
                    root,
                    receipt,
                    expected_base=BASE,
                    head=HEAD,
                    inventory_builder=lambda *args, **kwargs: "1" * 64,
                )
                self.assertFalse(result["factory_fit_pass"])
                self.assertEqual(
                    result["active_stop_conditions"],
                    ["DELIVERY_EVIDENCE_NOT_GROUNDED"],
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = write_delivery_evidence_fixture(self.module, root)
            fit_path = root / "docs/evidence/fit.json"
            fit_path.write_text(
                fit_path.read_text(encoding="utf-8").replace(
                    '"verdict": "PASS"',
                    '"verdict": "PASS", "verdict": "PASS"',
                    1,
                ),
                encoding="utf-8",
            )
            acceptance_path = root / "docs/evidence/acceptance.json"
            acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
            acceptance["factory_fit"]["sha256"] = hashlib.sha256(
                fit_path.read_bytes()
            ).hexdigest()
            acceptance_path.write_text(json.dumps(acceptance), encoding="utf-8")
            receipt["selected"][0]["sha256"] = hashlib.sha256(
                acceptance_path.read_bytes()
            ).hexdigest()
            self.assertFalse(
                self.module.bound_delivery_evidence(
                    root,
                    receipt,
                    expected_base=BASE,
                    head=HEAD,
                    inventory_builder=lambda *args, **kwargs: "1" * 64,
                )["factory_fit_pass"]
            )

    def test_delivery_inventory_binds_all_non_evidence_changes_and_deletions(self) -> None:
        excluded = {"acceptance.json", "review.json", "fit.json"}
        payloads = {
            "impl.py": b"print('ok')\n",
            "docs/тест.md": "данные\n".encode("utf-8"),
        }

        def runner(args: list[str], cwd: Path, impl_status: str = "A") -> bytes:
            if args[:5] == ["git", "diff", "--name-status", "--no-renames", "-z"]:
                return (
                    f"{impl_status}\0impl.py\0M\0docs/тест.md\0D\0legacy.md\0"
                    "A\0acceptance.json\0A\0review.json\0A\0fit.json\0"
                ).encode("utf-8")
            if args[:2] == ["git", "show"]:
                return payloads[args[2].split(":", 1)[1]]
            raise AssertionError(args)

        observed = self.module.delivery_inventory_sha256(
            Path("."), expected_base=BASE, head=HEAD,
            excluded_paths=excluded, runner=runner,
        )
        expected = self.module.sha256_bytes(self.module.canonical_json_bytes({
            "expected_base": BASE,
            "entries": [
                {
                    "status": "M",
                    "path": "docs/тест.md",
                    "sha256": hashlib.sha256(payloads["docs/тест.md"]).hexdigest(),
                },
                {
                    "status": "A",
                    "path": "impl.py",
                    "sha256": hashlib.sha256(payloads["impl.py"]).hexdigest(),
                },
                {"status": "D", "path": "legacy.md", "sha256": None},
            ],
            "excluded_evidence": [
                {"status": "A", "path": "acceptance.json"},
                {"status": "A", "path": "fit.json"},
                {"status": "A", "path": "review.json"},
            ],
        }))
        self.assertEqual(observed, expected)
        modified_status = self.module.delivery_inventory_sha256(
            Path("."), expected_base=BASE, head=HEAD,
            excluded_paths=excluded,
            runner=lambda args, cwd: runner(args, cwd, "M"),
        )
        other_base = self.module.delivery_inventory_sha256(
            Path("."), expected_base=MAIN, head=HEAD,
            excluded_paths=excluded, runner=runner,
        )
        self.assertNotEqual(observed, modified_status)
        self.assertNotEqual(observed, other_base)

        with self.assertRaisesRegex(ValueError, "DELIVERY_INVENTORY_INVALID"):
            self.module.delivery_inventory_sha256(
                Path("."), expected_base=BASE, head=HEAD,
                excluded_paths=excluded | {"missing.json"}, runner=runner,
            )

    def test_local_receipt_cannot_replace_execution_of_project_bound_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = root / "local/delivery_preflight" / f"{HEAD}.json"
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text("{\"status\":\"PASS\"}", encoding="utf-8")
            write_validation_profile(
                root,
                primary={
                    "argv": ["project-primary", "{expected_base}"],
                    "result_owner": "FOCUSED_PLUS_EXACT_PR_CI",
                    "trusted_paths": ["validator.txt"],
                },
                fallback={
                    "argv": ["project-fallback", "{expected_base}"],
                    "result_owner": "FULL_EXACT_HEAD",
                    "trusted_paths": ["validator.txt"],
                },
                credential_scan={
                    "argv": ["project-secret-scan"],
                    "trusted_paths": ["scanner.txt"],
                },
            )
            calls: list[tuple[str, ...]] = []

            def failed_runner(args: list[str], cwd: Path) -> bytes:
                calls.append(tuple(args))
                if args[:5] == ["git", "diff", "--name-only", "--no-renames", "-z"]:
                    return b"allowed.txt\0"
                git_result = validation_git_read(args, root)
                if git_result is not None:
                    return git_result
                raise ValueError("LIVE_READBACK_FAILED")

            with mock.patch.object(
                self.module, "task_delivery_scope", return_value=(MAIN, "origin/main", MAIN, ["allowed.txt"])
            ):
                denied = self.module.build_delivery_checks(
                    root, context_receipt={}, local_head=HEAD, local_tree=TREE,
                    ci_pass=True, runner=failed_runner,
                )
            self.assertFalse(denied["required_tests_pass"])
            self.assertFalse(denied["full_gate_pass"])

            def passing_runner(args: list[str], cwd: Path) -> bytes:
                calls.append(tuple(args))
                if args[:5] == ["git", "diff", "--name-only", "--no-renames", "-z"]:
                    return b"allowed.txt\0"
                git_result = validation_git_read(args, root)
                if git_result is not None:
                    return git_result
                if args[0] == "project-primary":
                    raise ValueError("INELIGIBLE")
                if args[0] in {"project-fallback", "project-secret-scan"}:
                    return b"PASS\n"
                raise AssertionError(args)

            with mock.patch.object(
                self.module, "task_delivery_scope", return_value=(MAIN, "origin/main", MAIN, ["allowed.txt"])
            ):
                passed = self.module.build_delivery_checks(
                    root, context_receipt={}, local_head=HEAD, local_tree=TREE,
                    ci_pass=True, runner=passing_runner,
                )
            self.assertTrue(passed["required_tests_pass"])
            self.assertTrue(passed["full_gate_pass"])
            self.assertTrue(any(call[0] == "project-fallback" for call in calls))
            self.assertNotIn(str(receipt_path), " ".join(" ".join(call) for call in calls))

    def test_project_validation_binding_is_closed_and_ci_owned_result_needs_ci(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_validation_profile(
                root,
                primary={
                    "argv": ["project-primary", "{expected_base}"],
                    "result_owner": "FOCUSED_PLUS_EXACT_PR_CI",
                    "trusted_paths": ["validator.txt"],
                },
                fallback=None,
                credential_scan={
                    "argv": ["project-secret-scan"],
                    "trusted_paths": ["scanner.txt"],
                },
            )

            def runner(args: list[str], cwd: Path) -> bytes:
                if args[:5] == ["git", "diff", "--name-only", "--no-renames", "-z"]:
                    return "docs/тест.md\0".encode("utf-8")
                git_result = validation_git_read(args, root)
                if git_result is not None:
                    return git_result
                if args[0] in {"project-primary", "project-secret-scan"}:
                    return b"PASS\n"
                raise AssertionError(args)

            with mock.patch.object(
                self.module, "task_delivery_scope", return_value=(MAIN, "origin/main", MAIN, ["docs/**"])
            ):
                denied = self.module.build_delivery_checks(
                    root, context_receipt={}, local_head=HEAD, local_tree=TREE,
                    ci_pass=False, runner=runner,
                )
            self.assertFalse(denied["required_tests_pass"])
            self.assertFalse(denied["full_gate_pass"])
            self.assertTrue(denied["write_set_pass"])
            self.assertTrue(denied["secret_scan_pass"])

            profile = json.loads(
                (root / "delivery-harness/project-profile.yaml").read_text(
                    encoding="utf-8"
                )
            )
            profile["validation"]["unexpected"] = True
            (root / "delivery-harness/project-profile.yaml").write_text(
                json.dumps(profile), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "PROJECT_VALIDATION_BINDING_INVALID"):
                self.module.load_validation_bindings(
                    root, expected_base=MAIN, runner=runner
                )

    def test_base_bound_profile_allows_additive_top_level_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_validation_profile(
                root,
                primary={
                    "argv": ["project-primary"],
                    "result_owner": "FOCUSED_PLUS_EXACT_PR_CI",
                    "trusted_paths": ["validator.txt"],
                },
                fallback=None,
                credential_scan={
                    "argv": ["project-secret-scan"],
                    "trusted_paths": ["scanner.txt"],
                },
            )
            base_bytes = (root / "delivery-harness/project-profile.yaml").read_bytes()
            live = json.loads(base_bytes.decode("utf-8"))
            live["factory_v1_readiness_contract"] = (
                "configs/factory_v1_operational_readiness_v1.yaml"
            )
            (root / "delivery-harness/project-profile.yaml").write_text(
                json.dumps(live), encoding="utf-8"
            )

            def runner(args: list[str], cwd: Path) -> bytes:
                if args[:2] == ["git", "show"] and str(args[2]).endswith(
                    "delivery-harness/project-profile.yaml"
                ):
                    return base_bytes
                raise AssertionError(args)

            profile = self.module.load_base_bound_profile(
                root, expected_base=MAIN, runner=runner
            )
            self.assertEqual(
                profile["factory_v1_readiness_contract"],
                "configs/factory_v1_operational_readiness_v1.yaml",
            )

    def test_base_bound_profile_rejects_existing_non_validation_key_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_validation_profile(
                root,
                primary={
                    "argv": ["project-primary"],
                    "result_owner": "FOCUSED_PLUS_EXACT_PR_CI",
                    "trusted_paths": ["validator.txt"],
                },
                fallback=None,
                credential_scan={
                    "argv": ["project-secret-scan"],
                    "trusted_paths": ["scanner.txt"],
                },
            )
            shared = json.loads(
                (root / "delivery-harness/project-profile.yaml").read_text(
                    encoding="utf-8"
                )
            )
            shared["bindings"] = {"context_map": "delivery-harness/context-map.yaml"}
            base_bytes = json.dumps(shared).encode("utf-8")
            (root / "delivery-harness/project-profile.yaml").write_bytes(base_bytes)
            live = json.loads(base_bytes.decode("utf-8"))
            live["bindings"] = {"context_map": "delivery-harness/other-map.yaml"}
            (root / "delivery-harness/project-profile.yaml").write_text(
                json.dumps(live), encoding="utf-8"
            )

            def runner(args: list[str], cwd: Path) -> bytes:
                if args[:2] == ["git", "show"] and str(args[2]).endswith(
                    "delivery-harness/project-profile.yaml"
                ):
                    return base_bytes
                raise AssertionError(args)

            with self.assertRaisesRegex(
                ValueError, "PROJECT_PROFILE_BASE_BINDING_INVALID"
            ):
                self.module.load_base_bound_profile(
                    root, expected_base=MAIN, runner=runner
                )

    def test_base_bound_profile_rejects_validation_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_validation_profile(
                root,
                primary={
                    "argv": ["project-primary"],
                    "result_owner": "FOCUSED_PLUS_EXACT_PR_CI",
                    "trusted_paths": ["validator.txt"],
                },
                fallback=None,
                credential_scan={
                    "argv": ["project-secret-scan"],
                    "trusted_paths": ["scanner.txt"],
                },
            )
            base_bytes = (root / "delivery-harness/project-profile.yaml").read_bytes()
            live = json.loads(base_bytes.decode("utf-8"))
            live["validation"]["github_ci_bound"] = False
            (root / "delivery-harness/project-profile.yaml").write_text(
                json.dumps(live), encoding="utf-8"
            )

            def runner(args: list[str], cwd: Path) -> bytes:
                if args[:2] == ["git", "show"] and str(args[2]).endswith(
                    "delivery-harness/project-profile.yaml"
                ):
                    return base_bytes
                raise AssertionError(args)

            with self.assertRaisesRegex(
                ValueError, "PROJECT_PROFILE_BASE_BINDING_INVALID"
            ):
                self.module.load_base_bound_profile(
                    root, expected_base=MAIN, runner=runner
                )

    def test_base_bound_profile_rejects_repository_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_validation_profile(
                root,
                primary={
                    "argv": ["project-primary"],
                    "result_owner": "FOCUSED_PLUS_EXACT_PR_CI",
                    "trusted_paths": ["validator.txt"],
                },
                fallback=None,
                credential_scan={
                    "argv": ["project-secret-scan"],
                    "trusted_paths": ["scanner.txt"],
                },
            )
            base_bytes = (root / "delivery-harness/project-profile.yaml").read_bytes()
            live = json.loads(base_bytes.decode("utf-8"))
            live["repository"]["default_branch"] = "trunk"
            (root / "delivery-harness/project-profile.yaml").write_text(
                json.dumps(live), encoding="utf-8"
            )

            def runner(args: list[str], cwd: Path) -> bytes:
                if args[:2] == ["git", "show"] and str(args[2]).endswith(
                    "delivery-harness/project-profile.yaml"
                ):
                    return base_bytes
                raise AssertionError(args)

            with self.assertRaisesRegex(
                ValueError, "PROJECT_PROFILE_BASE_BINDING_INVALID"
            ):
                self.module.load_base_bound_profile(
                    root, expected_base=MAIN, runner=runner
                )

    def test_ci_owned_gate_rejects_changed_workflow_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_validation_profile(
                root,
                primary={
                    "argv": ["project-primary", "{expected_base}"],
                    "result_owner": "FOCUSED_PLUS_EXACT_PR_CI",
                    "trusted_paths": ["validator.txt", ".github/workflows/ci.yml"],
                },
                fallback=None,
                credential_scan={
                    "argv": ["project-secret-scan"],
                    "trusted_paths": ["scanner.txt"],
                },
            )

            def runner(args: list[str], cwd: Path) -> bytes:
                if args[:2] == ["git", "show"]:
                    relative = args[2].split(":", 1)[1]
                    if relative == ".github/workflows/ci.yml":
                        return b"base workflow bytes\n"
                    return (root / relative).read_bytes()
                raise AssertionError(args)

            bindings = self.module.load_validation_bindings(
                root, expected_base=MAIN, runner=runner
            )
            self.assertIsNone(bindings["primary"])
            self.assertIsNone(bindings["fallback"])
            self.assertIsNotNone(bindings["credential_scan"])

    def test_credential_scan_survives_primary_trusted_path_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_validation_profile(
                root,
                primary={
                    "argv": ["project-primary", "{expected_base}"],
                    "result_owner": "FOCUSED_PLUS_EXACT_PR_CI",
                    "trusted_paths": ["validator.txt"],
                },
                fallback={
                    "argv": ["project-fallback", "{expected_base}"],
                    "result_owner": "FULL_EXACT_HEAD",
                    "trusted_paths": ["validator.txt"],
                },
                credential_scan={
                    "argv": ["project-secret-scan"],
                    "trusted_paths": ["scanner.txt"],
                },
            )
            calls: list[tuple[str, ...]] = []

            def runner(args: list[str], cwd: Path) -> bytes:
                calls.append(tuple(args))
                if args[:5] == ["git", "diff", "--name-only", "--no-renames", "-z"]:
                    return b"delivery-harness/harness.yaml\0"
                if args[:2] == ["git", "show"]:
                    relative = args[2].split(":", 1)[1]
                    if relative == "validator.txt":
                        return b"base validator bytes\n"
                    return (root / relative).read_bytes()
                git_result = validation_git_read(args, root)
                if git_result is not None:
                    return git_result
                if args[0] == "project-secret-scan":
                    return b"PASS\n"
                raise AssertionError(args)

            bindings = self.module.load_validation_bindings(
                root, expected_base=MAIN, runner=runner
            )
            self.assertIsNone(bindings["primary"])
            self.assertIsNone(bindings["fallback"])
            self.assertIsNotNone(bindings["credential_scan"])

            receipt = live_pr_head_receipt(self.module)
            with mock.patch.object(
                self.module,
                "task_delivery_scope",
                return_value=(MAIN, "origin/main", MAIN, ["delivery-harness/**"]),
            ):
                checks = self.module.build_delivery_checks(
                    root,
                    context_receipt=receipt,
                    local_head=HEAD,
                    local_tree=TREE,
                    ci_pass=True,
                    runner=runner,
                )
            self.assertTrue(checks["required_tests_pass"])
            self.assertTrue(checks["full_gate_pass"])
            self.assertTrue(checks["secret_scan_pass"])
            self.assertTrue(any(call[0] == "project-secret-scan" for call in calls))
            self.assertFalse(any(call[0] == "project-primary" for call in calls))
            self.assertFalse(any(call[0] == "project-fallback" for call in calls))

    def test_credential_scan_is_null_when_its_trusted_paths_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_validation_profile(
                root,
                primary={
                    "argv": ["project-primary", "{expected_base}"],
                    "result_owner": "FOCUSED_PLUS_EXACT_PR_CI",
                    "trusted_paths": ["validator.txt"],
                },
                fallback=None,
                credential_scan={
                    "argv": ["project-secret-scan"],
                    "trusted_paths": ["scanner.txt"],
                },
            )

            def runner(args: list[str], cwd: Path) -> bytes:
                if args[:2] == ["git", "show"]:
                    relative = args[2].split(":", 1)[1]
                    if relative == "scanner.txt":
                        return b"base scanner bytes\n"
                    return (root / relative).read_bytes()
                raise AssertionError(args)

            bindings = self.module.load_validation_bindings(
                root, expected_base=MAIN, runner=runner
            )
            self.assertIsNotNone(bindings["primary"])
            self.assertIsNone(bindings["credential_scan"])

    def test_managed_write_set_parser_preserves_exact_paths_and_prefixes(self) -> None:
        plan = """\n## Managed write set\n\n```text\nAGENTS.md\ndelivery-harness/templates/portable-core/** # portable subtree\n```\n\n## Next\n"""
        managed = self.module.parse_managed_write_set(plan, "Managed write set")
        self.assertEqual(
            managed,
            ["AGENTS.md", "delivery-harness/templates/portable-core/**"],
        )
        self.assertTrue(self.module.path_in_managed_write_set("AGENTS.md", managed))
        self.assertTrue(self.module.path_in_managed_write_set(
            "delivery-harness/templates/portable-core/AGENTS.md", managed
        ))
        self.assertFalse(self.module.path_in_managed_write_set(".github/workflows/ci.yml", managed))

    def test_executable_guard_submits_one_standard_merge_after_live_gate(self) -> None:
        runner = FakeRunner()
        result = self.module.execute_guarded_merge(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
            context_receipt=context_receipt(self.module), runner=runner,
            context_builder=exact_context_builder(self.module),
            evidence_builder=grounded_evidence,
            delivery_checks_builder=grounded_delivery_checks,
        )
        self.assertTrue(result["merge_submitted"])
        self.assertEqual(result["merge_commit"], MAIN)
        merge_calls = [call for call in runner.calls if call[:3] == ("gh", "pr", "merge")]
        self.assertEqual(merge_calls, [(
            "gh", "pr", "merge", str(PR), "--repo", "lancerbeta/solana-alpha-lab",
            "--merge", "--match-head-commit", HEAD,
        )])
        self.assertNotIn("--delete-branch", merge_calls[0])

    def test_executable_guard_does_not_call_merge_when_live_gate_denies(self) -> None:
        runner = FakeRunner(check_state="FAILURE")
        result = self.module.execute_guarded_merge(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
            context_receipt=context_receipt(self.module), runner=runner,
            context_builder=exact_context_builder(self.module),
            evidence_builder=grounded_evidence,
            delivery_checks_builder=grounded_delivery_checks,
        )
        self.assertFalse(result["merge_submitted"])
        self.assertFalse(any(call[:3] == ("gh", "pr", "merge") for call in runner.calls))

    def test_candidate_change_between_readback_and_merge_is_denied(self) -> None:
        runner = FakeRunner(flip_head_after_policy_reads=2)
        result = self.module.execute_guarded_merge(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
            context_receipt=context_receipt(self.module), runner=runner,
            context_builder=exact_context_builder(self.module),
            evidence_builder=grounded_evidence,
            delivery_checks_builder=grounded_delivery_checks,
        )
        self.assertFalse(result["merge_submitted"])
        self.assertEqual(result["reasons"], ["CANDIDATE_OR_BASE_CHANGED_BEFORE_MERGE"])
        self.assertFalse(any(call[:3] == ("gh", "pr", "merge") for call in runner.calls))

    def test_candidate_control_runtime_change_is_denied(self) -> None:
        with self.assertRaisesRegex(ValueError, "CONTROL_RUNTIME_CHANGED"):
            self.module.build_grounded_merge_request(
                ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
                context_receipt=context_receipt(self.module),
                runner=FakeRunner(base_mismatch_path="scripts/owner_attention_gate.py"),
                context_builder=exact_context_builder(self.module),
                evidence_builder=grounded_evidence,
                delivery_checks_builder=grounded_delivery_checks,
            )

    def test_live_pr_head_merge_submits_after_exact_phrase_and_ci(self) -> None:
        receipt = live_pr_head_receipt(self.module)
        runner = FakeRunner()
        result = self.module.execute_guarded_merge(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
            context_receipt=receipt, runner=runner,
            context_builder=exact_live_pr_builder(self.module, receipt),
            evidence_builder=grounded_evidence,
            delivery_checks_builder=grounded_delivery_checks,
        )
        self.assertTrue(result["merge_submitted"])
        merge_calls = [call for call in runner.calls if call[:3] == ("gh", "pr", "merge")]
        self.assertEqual(merge_calls, [(
            "gh", "pr", "merge", str(PR), "--repo", "lancerbeta/solana-alpha-lab",
            "--merge", "--match-head-commit", HEAD,
        )])
        self.assertNotIn("--delete-branch", merge_calls[0])

    def test_live_pr_head_control_runtime_landing_is_allowed(self) -> None:
        receipt = live_pr_head_receipt(self.module)
        result = self.module.build_grounded_merge_request(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
            context_receipt=receipt,
            runner=FakeRunner(base_mismatch_path="scripts/owner_attention_gate.py"),
            context_builder=exact_live_pr_builder(self.module, receipt),
            evidence_builder=grounded_evidence,
            delivery_checks_builder=grounded_delivery_checks,
        )
        self.assertTrue(result["merge_checks"]["context_receipt_bound"])
        self.assertEqual(
            self.module.evaluate(result, POLICY)["decision"], "AUTONOMOUS"
        )

    def test_live_pr_head_write_set_rejects_product_paths(self) -> None:
        receipt = live_pr_head_receipt(self.module)
        runner = FakeRunner()

        def product_diff(args: list[str], cwd: Path) -> bytes:
            if tuple(args[:3]) == ("git", "diff", "--name-only"):
                return b"src/solana_alpha_lab/alpha.py\0"
            if args and args[0] == "uv":
                return b""
            return runner(args, cwd)

        checks = self.module.build_delivery_checks(
            ROOT,
            context_receipt=receipt,
            local_head=HEAD,
            local_tree=TREE,
            ci_pass=True,
            runner=product_diff,
        )
        self.assertFalse(checks["write_set_pass"])

    def test_live_pr_head_write_set_allows_exact_atom_b_paths(self) -> None:
        atom_b_paths = (
            "catalog/assets/lifecycle.yaml",
            "catalog/generated/asset_edges.json",
            "docs/PROJECT_MAP.md",
            "docs/evidence/kcdn_atom_b/a1_delivery_completion_evidence_v1.json",
            "docs/evidence/kcdn_atom_b/a1_delivery_factory_fit_v1.json",
            "docs/evidence/kcdn_atom_b/a1_delivery_independent_review_v1.json",
            "docs/tasks/KCDN_ATOM_B_STABLE_DELIVERY_CONTEXT_REFERENCES_V1.md",
            "tests/test_delivery_harness_stable_asset_references.py",
        )
        live = yaml.safe_load(
            (ROOT / "delivery-harness/harness.yaml").read_text(encoding="utf-8")
        )
        portable = json.loads(
            (ROOT / "delivery-harness/templates/portable-core/delivery-harness/harness.yaml").read_text(
                encoding="utf-8"
            )
        )
        live_prefixes = live["merge_policy"]["harness_control_write_prefixes"]
        portable_prefixes = portable["merge_policy"]["harness_control_write_prefixes"]
        for path in atom_b_paths:
            self.assertNotIn("/**", path)
            self.assertIn(path, live_prefixes)
            self.assertIn(path, portable_prefixes)
            self.assertTrue(self.module.path_in_managed_write_set(path, live_prefixes))
            self.assertTrue(self.module.path_in_managed_write_set(path, portable_prefixes))
        sibling = "docs/evidence/kcdn_atom_a/a1_delivery_completion_evidence_v1.json"
        self.assertNotIn(sibling, live_prefixes)
        self.assertFalse(self.module.path_in_managed_write_set(sibling, live_prefixes))

        receipt = live_pr_head_receipt(self.module)
        runner = FakeRunner()
        payload = "".join(f"{path}\0" for path in atom_b_paths).encode()

        def atom_b_diff(args: list[str], cwd: Path) -> bytes:
            if tuple(args[:3]) == ("git", "diff", "--name-only"):
                return payload
            if args and args[0] == "uv":
                return b""
            return runner(args, cwd)

        checks = self.module.build_delivery_checks(
            ROOT,
            context_receipt=receipt,
            local_head=HEAD,
            local_tree=TREE,
            ci_pass=True,
            runner=atom_b_diff,
        )
        self.assertTrue(checks["write_set_pass"])

    def test_live_pr_head_write_set_allows_observation_fast_lane_paths(self) -> None:
        observation_paths = (
            "docs/evidence/observation_fast_lane_routing_closure/a1_delivery_completion_evidence_v1.json",
            "docs/evidence/observation_fast_lane_routing_closure/a1_delivery_factory_fit_v1.json",
            "docs/evidence/observation_fast_lane_routing_closure/a1_delivery_independent_review_v1.json",
            "docs/tasks/OBSERVATION_FAST_LANE_ROUTING_CLOSURE_V1.md",
            "src/solana_alpha_lab/factory/lane_classifier.py",
            "src/solana_alpha_lab/factory/observation_fast_lane_terminals.py",
            "src/solana_alpha_lab/factory/observation_panel_coverage.py",
            "src/solana_alpha_lab/factory/observation_panel_publisher.py",
            "src/solana_alpha_lab/factory/observation_schedule_capability.py",
            "src/solana_alpha_lab/factory/observation_schedule_compiler.py",
            "src/solana_alpha_lab/factory/observation_schedule_lifecycle.py",
            "src/solana_alpha_lab/factory/observation_scheduler.py",
            "tests/test_observation_fast_lane_p0_addendum.py",
            "tests/test_observation_fast_lane_routing_closure.py",
        )
        live = yaml.safe_load(
            (ROOT / "delivery-harness/harness.yaml").read_text(encoding="utf-8")
        )
        live_prefixes = live["merge_policy"]["harness_control_write_prefixes"]
        for path in observation_paths:
            self.assertNotIn("/**", path)
            self.assertIn(path, live_prefixes)
            self.assertTrue(
                self.module.path_in_managed_write_set(path, live_prefixes),
                path,
            )

        receipt = live_pr_head_receipt(self.module)
        runner = FakeRunner()
        payload = "".join(f"{path}\0" for path in observation_paths).encode()

        def observation_diff(args: list[str], cwd: Path) -> bytes:
            if tuple(args[:3]) == ("git", "diff", "--name-only"):
                return payload
            if args and args[0] == "uv":
                return b""
            return runner(args, cwd)

        checks = self.module.build_delivery_checks(
            ROOT,
            context_receipt=receipt,
            local_head=HEAD,
            local_tree=TREE,
            ci_pass=True,
            runner=observation_diff,
        )
        self.assertTrue(checks["write_set_pass"])

    def test_live_pr_head_write_set_rejects_sibling_kcdn_atom_a_evidence(self) -> None:
        receipt = live_pr_head_receipt(self.module)
        runner = FakeRunner()

        def sibling_diff(args: list[str], cwd: Path) -> bytes:
            if tuple(args[:3]) == ("git", "diff", "--name-only"):
                return b"docs/evidence/kcdn_atom_a/a1_delivery_completion_evidence_v1.json\0"
            if args and args[0] == "uv":
                return b""
            return runner(args, cwd)

        checks = self.module.build_delivery_checks(
            ROOT,
            context_receipt=receipt,
            local_head=HEAD,
            local_tree=TREE,
            ci_pass=True,
            runner=sibling_diff,
        )
        self.assertFalse(checks["write_set_pass"])

    def test_live_pr_head_consumes_exact_head_ci_when_local_gates_fail(self) -> None:
        receipt = live_pr_head_receipt(self.module)
        runner = FakeRunner()

        def failing_local_gates(args: list[str], cwd: Path) -> bytes:
            if tuple(args[:3]) == ("git", "diff", "--name-only"):
                return b"delivery-harness/harness.yaml\0"
            if args and args[0] == "uv":
                raise ValueError("LIVE_READBACK_FAILED")
            return runner(args, cwd)

        checks = self.module.build_delivery_checks(
            ROOT,
            context_receipt=receipt,
            local_head=HEAD,
            local_tree=TREE,
            ci_pass=True,
            runner=failing_local_gates,
        )
        self.assertTrue(checks["required_tests_pass"])
        self.assertTrue(checks["full_gate_pass"])
        self.assertTrue(checks["write_set_pass"])

    def test_guarded_scope_rejects_stale_merge_base_before_control_import(self) -> None:
        runner = FakeRunner()
        with mock.patch.object(
            self.module,
            "task_delivery_scope",
            return_value=(BASE, "origin/main", MAIN, ["allowed.txt"]),
        ):
            with self.assertRaisesRegex(ValueError, "STALE_BASE_CONTROL_PLANE"):
                self.module.guarded_delivery_scope(
                    ROOT,
                    context_receipt(self.module),
                    repository="lancerbeta/solana-alpha-lab",
                    runner=runner,
                )
        self.assertFalse(any(call[:2] == ("git", "show") for call in runner.calls))

    def test_configured_default_branch_drives_pr_and_remote_readback(self) -> None:
        runner = FakeRunner(default_branch="trunk", base_ref_name="trunk")
        with mock.patch.object(
            self.module,
            "guarded_delivery_scope",
            return_value=(BASE, BASE, [], "trunk"),
        ):
            request = self.module.build_grounded_merge_request(
                ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
                context_receipt=context_receipt(self.module), runner=runner,
                context_builder=exact_context_builder(self.module),
                evidence_builder=grounded_evidence,
                delivery_checks_builder=grounded_delivery_checks,
            )
        self.assertTrue(request["merge_checks"]["exact_pr_head_bound"])
        self.assertIn(
            ("git", "ls-remote", "--heads", "origin", "refs/heads/trunk"),
            runner.calls,
        )
        self.assertFalse(
            any("git/ref/heads/" in item for call in runner.calls for item in call)
        )
        self.assertFalse(
            any(
                call[:3] == ("gh", "run", "view")
                and any("jobs" in item for item in call)
                for call in runner.calls
            )
        )
        self.assertTrue(
            any(
                call[:3] == ("gh", "api", "graphql")
                and any("checkRuns" in item for item in call)
                for call in runner.calls
            )
        )
        with mock.patch.object(
            self.module,
            "guarded_delivery_scope",
            return_value=(BASE, BASE, [], "trunk"),
        ):
            post = self.module.build_post_merge_receipt(
                ROOT,
                repository="lancerbeta/solana-alpha-lab",
                pr_number=PR,
                route="DIRECT_CURSOR_DELIVERY",
                context_receipt=context_receipt(self.module),
                submission_receipt=guarded_submission_receipt(self.module),
                runner=runner,
                context_builder=exact_context_builder(self.module),
            )
        self.assertEqual(post["base_branch"], "trunk")

        runner = FakeRunner(default_branch="trunk", base_ref_name="main")
        with mock.patch.object(
            self.module,
            "guarded_delivery_scope",
            return_value=(BASE, BASE, [], "trunk"),
        ):
            request = self.module.build_grounded_merge_request(
                ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                route="DIRECT_CURSOR_DELIVERY", actor="CURSOR", approval_phrase=PHRASE,
                context_receipt=context_receipt(self.module), runner=runner,
                context_builder=exact_context_builder(self.module),
                evidence_builder=grounded_evidence,
                delivery_checks_builder=grounded_delivery_checks,
            )
        self.assertFalse(request["merge_checks"]["exact_pr_head_bound"])

    def test_post_merge_receipt_is_hash_bound_to_live_main_and_ci(self) -> None:
        runner = FakeRunner()
        receipt = self.module.build_post_merge_receipt(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY",
            context_receipt=context_receipt(self.module),
            submission_receipt=guarded_submission_receipt(self.module),
            runner=runner,
            context_builder=exact_context_builder(self.module),
        )
        unsigned = dict(receipt); observed = unsigned.pop("receipt_sha256")
        self.assertEqual(observed, self.module.sha256_bytes(self.module.canonical_json_bytes(unsigned)))
        self.assertEqual(receipt["default_branch_ci"]["conclusion"], "success")
        self.assertEqual(receipt["base_branch"], "main")
        self.assertEqual(receipt["base_head"], BASE)
        self.assertEqual(receipt["head_branch"], "candidate")
        self.assertIn(
            ("git", "fetch", "--no-tags", "origin", "--", MAIN),
            runner.calls,
        )
        self.assertIn(
            (
                "git", "--no-replace-objects", "rev-list",
                "--parents", "-n", "1", MAIN,
            ),
            runner.calls,
        )

    def test_github_workflow_jobs_accepts_null_conclusion_and_rejects_unmatched_run(self) -> None:
        payload = json.dumps({
            "data": {
                "repository": {
                    "object": {
                        "checkSuites": {
                            "pageInfo": {"hasNextPage": False},
                            "nodes": [{
                                "workflowRun": {"databaseId": 76},
                                "checkRuns": {
                                    "pageInfo": {"hasNextPage": False},
                                    "nodes": [{
                                        "name": "validate",
                                        "status": "IN_PROGRESS",
                                        "conclusion": None,
                                    }],
                                },
                            }],
                        }
                    }
                }
            }
        }).encode()

        def runner(args: list[str], cwd: Path) -> bytes:
            return payload

        jobs = self.module.github_workflow_jobs(
            "lancerbeta/solana-alpha-lab",
            commit_oid=HEAD,
            run_id=76,
            root=ROOT,
            runner=runner,
            invalid_code="PR_CI_READBACK_INVALID",
        )
        self.assertEqual(
            jobs,
            [{"name": "validate", "status": "in_progress", "conclusion": None}],
        )
        with self.assertRaisesRegex(ValueError, "PR_CI_READBACK_INVALID"):
            self.module.github_workflow_jobs(
                "lancerbeta/solana-alpha-lab",
                commit_oid=HEAD,
                run_id=99,
                root=ROOT,
                runner=runner,
                invalid_code="PR_CI_READBACK_INVALID",
            )

    def test_live_default_branch_oid_rejects_malformed_ls_remote(self) -> None:
        class Runner:
            def __init__(self) -> None:
                self.calls: list[tuple[str, ...]] = []

            def __call__(self, args: list[str], cwd: Path) -> bytes:
                self.calls.append(tuple(args))
                return b"+refs/heads/main:refs/remotes/origin/main\trefs/heads/main\n"

        runner = Runner()
        with self.assertRaisesRegex(ValueError, "DEFAULT_BRANCH_READBACK_INVALID"):
            self.module.live_default_branch_oid(
                ROOT,
                repository="lancerbeta/solana-alpha-lab",
                branch="main",
                runner=runner,
            )
        self.assertEqual(
            runner.calls,
            [("git", "ls-remote", "--heads", "origin", "refs/heads/main")],
        )

    def test_post_merge_rejects_non_oid_default_head_before_fetch(self) -> None:
        runner = FakeRunner(
            postmerge_default_oid="+refs/heads/main:refs/remotes/origin/main",
        )
        with self.assertRaisesRegex(ValueError, "POST_MERGE_READBACK_FAILED"):
            self.module.build_post_merge_receipt(
                ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                route="DIRECT_CURSOR_DELIVERY",
                context_receipt=context_receipt(self.module),
                submission_receipt=guarded_submission_receipt(self.module),
                runner=runner,
                context_builder=exact_context_builder(self.module),
            )
        self.assertFalse(any(call[:2] == ("git", "fetch") for call in runner.calls))
        self.assertFalse(any("rev-list" in call for call in runner.calls))

    def test_post_merge_receipt_rejects_wrong_pr_or_deleted_head_branch(self) -> None:
        for runner in (
            FakeRunner(pr_number=PR + 1),
            FakeRunner(head_branch_preserved=False),
            FakeRunner(base_ref_name="release"),
            FakeRunner(origin="git@github.com:acme/other.git"),
            FakeRunner(postmerge_latest_failure=True),
            FakeRunner(upstream_oid="0" * 40),
        ):
            with self.subTest(runner=runner):
                with self.assertRaisesRegex(ValueError, "POST_MERGE_READBACK_FAILED"):
                    self.module.build_post_merge_receipt(
                        ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
                        route="DIRECT_CURSOR_DELIVERY",
                        context_receipt=context_receipt(self.module),
                        submission_receipt=guarded_submission_receipt(self.module),
                        runner=runner,
                        context_builder=exact_context_builder(self.module),
                    )

    def test_post_merge_requires_grounded_submission_and_base_owned_policy(self) -> None:
        runner = FakeRunner()
        self.module.build_post_merge_receipt(
            ROOT, repository="lancerbeta/solana-alpha-lab", pr_number=PR,
            route="DIRECT_CURSOR_DELIVERY",
            context_receipt=context_receipt(self.module),
            submission_receipt=guarded_submission_receipt(self.module),
            runner=runner,
            context_builder=exact_context_builder(self.module),
        )
        self.assertIn(
            ("git", "show", f"{BASE}:control/owner_attention_gate_v2.yaml"),
            runner.calls,
        )
        invalid = guarded_submission_receipt(self.module)
        invalid["receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "GUARDED_SUBMISSION_INVALID"):
            self.module.build_post_merge_receipt(
                ROOT,
                repository="lancerbeta/solana-alpha-lab",
                pr_number=PR,
                route="DIRECT_CURSOR_DELIVERY",
                context_receipt=context_receipt(self.module),
                submission_receipt=invalid,
                runner=FakeRunner(),
                context_builder=exact_context_builder(self.module),
            )
        with self.assertRaisesRegex(ValueError, "POST_MERGE_READBACK_FAILED"):
            self.module.build_post_merge_receipt(
                ROOT,
                repository="lancerbeta/solana-alpha-lab",
                pr_number=PR,
                route="DIRECT_CURSOR_DELIVERY",
                context_receipt=context_receipt(self.module),
                submission_receipt=guarded_submission_receipt(self.module),
                runner=FakeRunner(
                    base_mismatch_path="control/owner_attention_gate_v2.yaml"
                ),
                context_builder=exact_context_builder(self.module),
            )


if __name__ == "__main__":
    unittest.main()
