"""Real A/H/M Git history; only remote Git/GitHub readback is simulated."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "lancerbeta/solana-alpha-lab"
ROUTE = "DIRECT_CODEX_DELIVERY"
TASK = "TEST-FROZEN-POST-MERGE"
CONTRACT = f"docs/tasks/{TASK}.md"


def load_gate():
    spec = importlib.util.spec_from_file_location("post_merge_frozen_gate", ROOT / "scripts/owner_attention_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrozenContextPostMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = load_gate()
        cls.temporary = tempfile.TemporaryDirectory(prefix="smial-post-merge-test-")
        cls.root = Path(cls.temporary.name)
        files = set(cls.gate.CONTROL_RUNTIME_PATHS) | {
            "AGENTS.md", "delivery-harness/project-profile.yaml",
            "control/owner_attention_gate_v2.yaml",
            "configs/factory_v1_operational_readiness_v1.yaml",
            "catalog/catalog_manifest.yaml",
        }
        manifest = yaml.safe_load((ROOT / "catalog/catalog_manifest.yaml").read_text(encoding="utf-8"))
        files.update(manifest["root_resolver"]["asset_registries"])
        for relative in files:
            destination = cls.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        cls.git("init", "--initial-branch=main")
        for key, value in (("user.name", "Scratch Fixture"), ("user.email", "fixture@example.invalid"),
                           ("core.autocrlf", "false"), ("core.hooksPath", str(cls.root / ".git/no-hooks"))):
            cls.git("config", "--local", key, value)
        cls.git("remote", "add", "origin", f"git@github.com:{REPOSITORY}.git")
        cls.git("add", ".")
        cls.git("commit", "-m", "Frozen base A")
        cls.base = cls.git("rev-parse", "HEAD").decode().strip()
        cls.git("checkout", "-b", "candidate")
        metadata = {
            "task_id": TASK, "task_version": "1.0", "status": "READY", "as_of": "2026-10-02",
            "owner": "GOAL_OWNER", "allowed_routes": [ROUTE],
            "expected_repository": REPOSITORY,
            "git_binding": {"expected_base": cls.base, "expected_upstream": "origin/main",
                            "expected_upstream_oid": cls.base, "expected_branch": "candidate",
                            "dirty_mode": "FORBIDDEN"},
            "objective": "Prove frozen task context separately from exact post-merge reality.",
            "managed_write_set": [CONTRACT, "docs/selected.md"],
            "external_caps": dict.fromkeys(["network", "credentials", "external_system",
                                            "signing_or_financial_action", "cash_spend", "deployment"], False),
            "stop_conditions": ["MERGE_WITHOUT_EXACT_OWNER_PHRASE"],
            "context_requirements": {"catalog_asset_ids": [], "l2_roles": ["ARCHITECTURE_DECISIONS"],
                                     "l3_roles": [], "roadmap_path": None, "exact_role_paths": {
                                         "LIFECYCLE": [], "EXTERNAL_ROUTE_KNOWLEDGE": [],
                                         "ARCHITECTURE_DECISIONS": ["docs/selected.md"],
                                         "DELIVERY_EVIDENCE": [], "HISTORICAL_CONTEXT": []}},
        }
        cls.metadata = metadata
        (cls.root / CONTRACT).parent.mkdir(parents=True, exist_ok=True)
        (cls.root / CONTRACT).write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n\n# Frozen task\n", encoding="utf-8", newline="\n")
        (cls.root / "docs/selected.md").write_bytes(b"Frozen selected candidate context.\n")
        cls.git("add", ".")
        cls.git("commit", "-m", "Approved task head H")
        cls.head = cls.git("rev-parse", "HEAD").decode().strip()
        cls.tree = cls.git("rev-parse", "HEAD^{tree}").decode().strip()
        cls.git("update-ref", "refs/remotes/origin/main", cls.base)
        cls.context = cls.gate.rebuild_context_receipt(cls.root, task_id=TASK, task_contract=CONTRACT, route=ROUTE)
        cls.merge = cls.git("commit-tree", cls.tree, "-p", cls.base, "-p", cls.head, "-m", "Ordinary merge M").decode().strip()
        cls.git("update-ref", "refs/remotes/origin/main", cls.merge)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @classmethod
    def git(cls, *args):
        result = subprocess.run(["git", "-c", f"safe.directory={cls.root}", *args], cwd=cls.root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout

    def setUp(self):
        self.context = copy.deepcopy(type(self).context)
        self.main = self.merge
        self.pr_head = self.head
        self.pr_number = 17
        self.pr_state = "MERGED"
        self.pr_head_branch = "candidate"
        self.branch_preserved = True
        self.ci_sha = self.merge
        self.ci_conclusion = "success"
        self.ci_missing = False

    def signed(self, value):
        value.pop("receipt_sha256", None)
        value["receipt_sha256"] = self.gate.sha256_bytes(self.gate.canonical_json_bytes(value))
        return value

    def submission(self):
        return self.signed({
            "schema": "smial.guarded-merge-submission", "schema_version": "1.0",
            "decision": "AUTONOMOUS", "reasons": ["OWNER_APPROVAL_MATCHED"],
            "repository": REPOSITORY, "pr_number": 17, "approved_head": self.head,
            "context_receipt_sha256": self.context["receipt_sha256"], "route": ROUTE,
            "merge_submitted": True, "merge_commit": self.merge,
            "post_merge_ci": "PENDING_EXACT_MAIN_READBACK", "branch_deleted": False,
            "settings_changed": False,
        })

    def remote_runner(self, args, cwd):
        if args[:2] == ["git", "ls-remote"]:
            if args[-1] == "refs/heads/main":
                return f"{self.main}\trefs/heads/main\n".encode()
            return f"{self.head}\trefs/heads/{self.pr_head_branch}\n".encode() if self.branch_preserved else b""
        if args[:2] == ["git", "fetch"]:
            return b""  # M is already a real local Git object.
        if args[:3] == ["gh", "pr", "view"]:
            value = {"number": self.pr_number, "state": self.pr_state, "mergedAt": "2026-10-02T00:00:00Z",
                     "headRefOid": self.pr_head, "headRefName": self.pr_head_branch, "baseRefName": "main",
                     "mergeCommit": {"oid": self.merge}}
        elif args[:3] == ["gh", "run", "list"]:
            value = [] if self.ci_missing else [{"headSha": self.ci_sha, "status": "completed",
                                               "conclusion": self.ci_conclusion, "databaseId": 71,
                                               "event": "push", "workflowName": "Repository validation"}]
        elif args[:3] == ["gh", "run", "view"]:
            value = {"headSha": self.ci_sha, "status": "completed", "conclusion": self.ci_conclusion,
                     "event": "push", "workflowName": "Repository validation"}
        elif args[:3] == ["gh", "api", "graphql"]:
            value = {"data": {"repository": {"object": {"checkSuites": {
                "pageInfo": {"hasNextPage": False}, "nodes": [{"workflowRun": {"databaseId": 71},
                    "checkRuns": {"pageInfo": {"hasNextPage": False}, "nodes": [
                        {"name": "validate", "status": "COMPLETED", "conclusion": self.ci_conclusion.upper()}]}}]}}}}}
        else:
            return self.gate.run_read(args, cwd)
        return json.dumps(value).encode()

    def post(self, **overrides):
        kwargs = dict(repository=REPOSITORY, pr_number=17, route=ROUTE,
                      context_receipt=self.context, submission_receipt=self.submission(),
                      runner=self.remote_runner)
        kwargs.update(overrides)
        return self.gate.build_post_merge_receipt(self.root, **kwargs)

    def test_real_advanced_upstream_lifecycle(self):
        self.assertEqual(self.git("rev-list", "--parents", "-n", "1", self.merge).decode().split(),
                         [self.merge, self.base, self.head])
        with self.assertRaisesRegex(ValueError, "TASK_EXPECTED_BASE_MISMATCH"):
            self.gate.verify_live_context_receipt(self.root, self.context, route=ROUTE)
        before = self.git("show-ref") + self.git("status", "--porcelain=v1") + (self.root / ".git/config").read_bytes()
        index_before = (self.root / ".git/index").read_bytes()
        result = self.post()
        self.assertEqual((self.root / ".git/index").read_bytes(), index_before)
        self.assertEqual(result["base_head"], self.base)
        self.assertEqual(result["approved_head"], self.head)
        self.assertEqual(result["default_branch_head"], self.merge)
        self.assertEqual(result["default_branch_ci"]["conclusion"], "success")
        self.assertEqual(before, self.git("show-ref") + self.git("status", "--porcelain=v1") + (self.root / ".git/config").read_bytes())

    def test_pre_merge_readiness_still_denies_stale_base(self):
        with self.assertRaisesRegex(ValueError, "TASK_EXPECTED_BASE_MISMATCH"):
            self.gate.evaluate_merge_readiness(self.root, repository=REPOSITORY, pr_number=17,
                                              route=ROUTE, actor="CODEX", context_receipt=self.context,
                                              runner=self.remote_runner)

    def test_tampered_and_rehashed_context_substitutions_deny(self):
        mutations = {
            "self_hash": lambda value: value.update(receipt_sha256="0" * 64),
            "head": lambda value: value["repository"].update(head=self.base),
            "tree": lambda value: value["repository"].update(tree="0" * 40),
            "task_hash": lambda value: value["task"].update(sha256="0" * 64),
            "selected_hash": lambda value: value["selected"][0].update(sha256="0" * 64),
            "omitted_selected": lambda value: value["selected"].pop(),
            "branch": lambda value: value["repository"].update(branch="other"),
            "dirty": lambda value: value["repository"].update(dirty=True),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self.context = copy.deepcopy(type(self).context)
                mutate(self.context)
                if name != "self_hash":
                    self.signed(self.context)
                with self.assertRaises(ValueError):
                    self.post()

    def test_wrong_approved_head_and_wrong_repo_or_pr_deny(self):
        bad_submission = self.submission()
        bad_submission["approved_head"] = self.base
        self.signed(bad_submission)
        with self.assertRaisesRegex(ValueError, "GUARDED_SUBMISSION_INVALID"):
            self.post(submission_receipt=bad_submission)
        for kwargs in ({"repository": "acme/other"}, {"pr_number": 18}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.post(**kwargs)
        self.pr_head = self.base
        with self.assertRaisesRegex(ValueError, "POST_MERGE_READBACK_FAILED"):
            self.post()

    def test_reversed_and_extra_real_merge_parents_deny(self):
        extra = self.git("commit-tree", self.tree, "-m", "Unrelated parent").decode().strip()
        for parents in ([self.head, self.base], [self.base, self.head, extra], [self.base]):
            with self.subTest(parents=parents):
                flags = [item for parent in parents for item in ("-p", parent)]
                bad_merge = self.git("commit-tree", self.tree, *flags, "-m", "Wrong topology").decode().strip()
                original = self.merge
                self.merge = self.main = self.ci_sha = bad_merge
                try:
                    with self.assertRaisesRegex(ValueError, "POST_MERGE_READBACK_FAILED"):
                        self.post()
                finally:
                    self.merge = self.main = self.ci_sha = original

    def test_branch_pr_state_exact_main_and_ci_fail_closed(self):
        for field, value in (("branch_preserved", False), ("pr_state", "OPEN"),
                             ("pr_number", 18), ("pr_head_branch", "other-same-head"), ("main", self.head),
                             ("ci_missing", True), ("ci_conclusion", "failure"),
                             ("ci_sha", self.head)):
            with self.subTest(field=field):
                original = getattr(self, field)
                setattr(self, field, value)
                try:
                    with self.assertRaisesRegex(ValueError, "POST_MERGE_READBACK_FAILED"):
                        self.post()
                finally:
                    setattr(self, field, original)

    def test_frozen_proof_ignores_post_merge_checkout_and_uncommitted_bytes(self):
        self.git("checkout", "--detach", self.merge)
        selected = self.root / "docs/selected.md"
        original = selected.read_bytes()
        selected.write_bytes(b"Uncommitted later checkout bytes.\n")
        try:
            result = self.post()
            self.assertEqual(result["approved_head"], self.head)
            self.assertEqual(selected.read_bytes(), b"Uncommitted later checkout bytes.\n")
        finally:
            selected.write_bytes(original)
            self.git("checkout", "candidate")

    def test_wrong_frozen_contract_base_is_denied_from_real_git_bytes(self):
        contract = self.root / CONTRACT
        original = contract.read_bytes()
        bad_metadata = copy.deepcopy(self.metadata)
        bad_metadata["git_binding"]["expected_base"] = self.head
        contract.write_text("---\n" + yaml.safe_dump(bad_metadata, sort_keys=False) + "---\n", encoding="utf-8", newline="\n")
        try:
            self.git("add", CONTRACT)
            self.git("commit", "-m", "Malformed frozen base binding")
            bad_head = self.git("rev-parse", "HEAD").decode().strip()
            self.context["repository"]["head"] = bad_head
            self.context["repository"]["tree"] = self.git("rev-parse", "HEAD^{tree}").decode().strip()
            self.context["task"]["sha256"] = self.gate.sha256_bytes(contract.read_bytes())
            self.signed(self.context)
            with self.assertRaisesRegex(ValueError, "TASK_EXPECTED_BASE_MISMATCH"):
                self.post()
        finally:
            # Reset only the self-created scratch fixture, never the project.
            self.git("reset", "--hard", self.head)
            self.assertEqual(contract.read_bytes(), original)

    def test_git_environment_cannot_redirect_snapshot_into_source(self):
        index = self.root / ".git/index"
        before = index.read_bytes()
        for key, value in (("GIT_INDEX_FILE", str(index)), ("GIT_DIR", str(self.root / ".git")),
                           ("GIT_WORK_TREE", str(self.root)), ("GIT_CONFIG_PARAMETERS", "'core.hooksPath=unsafe'")):
            with self.subTest(key=key), mock.patch.dict(os.environ, {key: value}):
                with self.assertRaisesRegex(ValueError, "CONTEXT_RECEIPT_INVALID"):
                    self.post()
            self.assertEqual(index.read_bytes(), before)
        with mock.patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "unsafe"}):
            with self.assertRaisesRegex(ValueError, "CONTEXT_RECEIPT_INVALID"):
                self.post()
        self.assertEqual(index.read_bytes(), before)

    def test_windows_drive_relative_and_alias_git_paths_fail_before_snapshot_writes(self):
        with tempfile.TemporaryDirectory(prefix="smial-external-sentinel-") as temporary:
            sentinel = Path(temporary) / "outside"
            sentinel.write_bytes(b"External owner bytes stay unchanged.\n")
            blob = self.git("rev-parse", f"{self.head}:docs/selected.md").decode().strip()
            for path in ("C:../outside", "D:escaped", "sentinel:ads", ".git.", "trailing ",
                         "NUL", "CON.txt", "COM1.log", "LPT9", "AUX", "PRN", "CONIN$", "COM¹.txt"):
                with self.subTest(path=path):
                    if "/" in path:
                        parent, name = path.split("/", 1)
                        subtree = subprocess.run(["git", "mktree"], cwd=self.root,
                            input=f"100644 blob {blob}\t{name}\n".encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout.decode().strip()
                        additional = f"040000 tree {subtree}\t{parent}\n".encode()
                    else:
                        additional = f"100644 blob {blob}\t{path}\n".encode()
                    listing = self.git("ls-tree", self.head) + additional
                    result = subprocess.run(["git", "mktree"], cwd=self.root, input=listing,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    tree = result.stdout.decode().strip()
                    head = self.git("commit-tree", tree, "-p", self.head, "-m", "Unsupported tracked name").decode().strip()
                    self.context = copy.deepcopy(type(self).context)
                    self.context["repository"].update(head=head, tree=tree)
                    self.signed(self.context)
                    # Default production verifier must reject the real Git tree
                    # before allocating a scratch filesystem at all.
                    with mock.patch.object(self.gate.tempfile, "TemporaryDirectory", side_effect=AssertionError("snapshot writes started")):
                        with self.assertRaisesRegex(ValueError, "CONTEXT_RECEIPT_INVALID"):
                            self.post()
                    self.assertEqual(sentinel.read_bytes(), b"External owner bytes stay unchanged.\n")

    def test_global_git_hooks_and_fsmonitor_are_not_executed_in_snapshot(self):
        with tempfile.TemporaryDirectory(prefix="smial-global-hooks-test-") as temporary:
            directory = Path(temporary)
            marker = directory / "hook-ran"
            hooks = directory / "hooks"
            hooks.mkdir()
            hook = "#!/bin/sh\nprintf executed >> '" + marker.as_posix() + "'\n"
            for name in ("reference-transaction", "fsmonitor", "clean"):
                path = hooks / name
                path.write_text(hook + ("cat\n" if name == "clean" else ""), encoding="utf-8", newline="\n")
                path.chmod(0o755)
            attributes = directory / "global-attributes"
            attributes.write_text("* filter=probe\n", encoding="utf-8", newline="\n")
            config = directory / "global-config"
            config.write_text('[core]\n hooksPath = "' + hooks.as_posix() + '"\n fsmonitor = "' + (hooks / "fsmonitor").as_posix() + '"\n attributesFile = "' + attributes.as_posix() + '"\n[filter "probe"]\n clean = "' + (hooks / "clean").as_posix() + '"\n', encoding="utf-8", newline="\n")
            with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(config)}):
                self.assertEqual(self.post()["approved_head"], self.head)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
