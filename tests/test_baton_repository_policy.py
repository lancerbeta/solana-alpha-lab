from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

spec = importlib.util.spec_from_file_location(
    "validate_baseline_for_baton_policy",
    ROOT / "scripts/validate_baseline.py",
)
assert spec and spec.loader
baseline = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = baseline
spec.loader.exec_module(baseline)

H0 = baseline.CTRL_BATON_A62_COMMIT_OID
OLD_F = baseline.CTRL_BATON_A62_FEATURE_OID
F2 = baseline.CTRL_BATON_A612_FEATURE_OID
F3 = baseline.CTRL_BATON_A617_FEATURE_OID
F = "f" * 40
M = "e" * 40
INTERMEDIATE = "c" * 40
FEATURE_TREE = "d" * 40
MERGE_TREE_DRIFT = "b" * 40
EXPECTED_CHANGED = baseline.ctrl_baton_expected_changed()
EXPECTED_TRACKED = baseline.ctrl_baton_expected_tracked()


def local_github_context() -> baseline.CtrlBatonGithubContext:
    return baseline.empty_ctrl_baton_github_context()


def pr_github_context(**overrides: object) -> baseline.CtrlBatonGithubContext:
    context = baseline.CtrlBatonGithubContext(
        True,
        baseline.EXPECTED_GITHUB_REPOSITORY,
        "pull_request",
        "refs/pull/17/merge",
        M,
        "main",
        baseline.CTRL_BATON_FEATURE_BRANCH,
        17,
        None,
        "main",
        H0,
        baseline.CTRL_BATON_FEATURE_BRANCH,
        F,
        None,
        None,
    )
    return context._replace(**overrides)


def push_github_context(**overrides: object) -> baseline.CtrlBatonGithubContext:
    context = baseline.CtrlBatonGithubContext(
        True,
        baseline.EXPECTED_GITHUB_REPOSITORY,
        "push",
        "refs/heads/main",
        M,
        None,
        None,
        None,
        "refs/heads/main",
        None,
        None,
        None,
        None,
        H0,
        M,
    )
    return context._replace(**overrides)


def base_view(**overrides: object) -> baseline.CtrlBatonGitView:
    view = baseline.CtrlBatonGitView(
        baseline.CTRL_BATON_FEATURE_BRANCH,
        H0,
        (baseline.TASK08_BASE_COMMIT_OID,),
        (),
        baseline.CTRL_BATON_A62_TREE_OID,
        None,
        H0,
        H0,
        H0,
        None,
        None,
        frozenset({"origin"}),
        (baseline.EXPECTED_ORIGIN_URL,),
        (baseline.EXPECTED_ORIGIN_URL,),
        (baseline.EXPECTED_ORIGIN_FETCH_REFSPEC,),
        (),
        baseline.CTRL_BATON_FEATURE_LOCAL_REFS,
        EXPECTED_TRACKED,
        EXPECTED_CHANGED,
        baseline.CTRL_BATON_A62R_EXPECTED_UNTRACKED,
        baseline.CTRL_BATON_A62R_EXPECTED_MODIFIED,
        frozenset(),
        frozenset(),
        frozenset(),
        frozenset(),
    )
    return view._replace(**overrides)


def committed_view(**overrides: object) -> baseline.CtrlBatonGitView:
    view = base_view(
        head_oid=F,
        head_parents=(H0,),
        feature_parents=(H0,),
        head_tree_oid=FEATURE_TREE,
        feature_tree_oid=FEATURE_TREE,
        feature_local_oid=F,
        staged=frozenset(),
        staged_added=frozenset(),
        staged_modified=frozenset(),
        base_diff=EXPECTED_CHANGED,
        head_subject=baseline.CTRL_BATON_A62_COMMIT_SUBJECT,
        commits_after_base=1,
        index_base_diff=EXPECTED_CHANGED,
        index_catalog_version=baseline.CTRL_BATON_A62_EXPECTED_CATALOG_VERSION,
        head_tree_path_count=baseline.CTRL_BATON_EXPECTED_INDEX_PATH_COUNT,
        head_catalog_version=baseline.CTRL_BATON_A62_EXPECTED_CATALOG_VERSION,
    )
    return view._replace(**overrides)


def published_view(**overrides: object) -> baseline.CtrlBatonGitView:
    view = committed_view(
        feature_remote_oid=F,
        upstream=baseline.CTRL_BATON_FEATURE_UPSTREAM,
        all_refs=baseline.CTRL_BATON_FEATURE_PUBLISHED_REFS,
    )
    return view._replace(**overrides)


def repair_staged_view(**overrides: object) -> baseline.CtrlBatonGitView:
    view = published_view(
        head_oid=OLD_F,
        head_parents=(H0,),
        feature_parents=(H0,),
        head_tree_oid=baseline.CTRL_BATON_A62_FEATURE_TREE_OID,
        feature_tree_oid=baseline.CTRL_BATON_A62_FEATURE_TREE_OID,
        feature_local_oid=OLD_F,
        feature_remote_oid=OLD_F,
        staged=baseline.CTRL_BATON_A69_REPAIR_PATHS,
        staged_modified=baseline.CTRL_BATON_A69_REPAIR_PATHS,
        index_base_diff=EXPECTED_CHANGED,
        index_catalog_version=baseline.CTRL_BATON_A69_EXPECTED_CATALOG_VERSION,
        head_catalog_version="0.8.1",
    )
    return view._replace(**overrides)


def reconciliation_staged_view(
    **overrides: object,
) -> baseline.CtrlBatonGitView:
    view = published_view(
        head_oid=F2,
        head_parents=(H0,),
        feature_parents=(H0,),
        head_tree_oid=baseline.CTRL_BATON_A612_FEATURE_TREE_OID,
        feature_tree_oid=baseline.CTRL_BATON_A612_FEATURE_TREE_OID,
        feature_local_oid=F2,
        feature_remote_oid=F2,
        staged=baseline.CTRL_BATON_A613_RECONCILIATION_PATHS,
        staged_modified=baseline.CTRL_BATON_A613_RECONCILIATION_PATHS,
        index_base_diff=EXPECTED_CHANGED,
        index_catalog_version=baseline.CTRL_BATON_A613_EXPECTED_CATALOG_VERSION,
        head_catalog_version=baseline.CTRL_BATON_A69_EXPECTED_CATALOG_VERSION,
    )
    return view._replace(**overrides)


def local_main_repair_staged_view(
    **overrides: object,
) -> baseline.CtrlBatonGitView:
    view = published_view(
        head_oid=F3,
        head_parents=(H0,),
        feature_parents=(H0,),
        head_tree_oid=baseline.CTRL_BATON_A617_FEATURE_TREE_OID,
        feature_tree_oid=baseline.CTRL_BATON_A617_FEATURE_TREE_OID,
        feature_local_oid=F3,
        feature_remote_oid=F3,
        staged=baseline.CTRL_BATON_A618_LOCAL_MAIN_REPAIR_PATHS,
        staged_modified=baseline.CTRL_BATON_A618_LOCAL_MAIN_REPAIR_PATHS,
        index_base_diff=EXPECTED_CHANGED,
        index_catalog_version=baseline.CTRL_BATON_A62_EXPECTED_CATALOG_VERSION,
        head_catalog_version=baseline.CTRL_BATON_A613_EXPECTED_CATALOG_VERSION,
    )
    return view._replace(**overrides)


def ahead_of_published_view(**overrides: object) -> baseline.CtrlBatonGitView:
    view = published_view(feature_remote_oid=F3)
    return view._replace(**overrides)


def pr_view(**overrides: object) -> baseline.CtrlBatonGitView:
    refs = frozenset(
        {
            "refs/remotes/origin/main",
            f"refs/remotes/origin/{baseline.CTRL_BATON_FEATURE_BRANCH}",
            "refs/remotes/pull/17/merge",
        }
    )
    view = committed_view(
        branch=None,
        head_oid=M,
        head_parents=(H0, F),
        main_oid=None,
        feature_local_oid=None,
        feature_remote_oid=F,
        fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
        push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
        all_refs=refs,
    )
    return view._replace(**overrides)


def main_merge_view(**overrides: object) -> baseline.CtrlBatonGitView:
    refs = frozenset(
        {
            "refs/heads/main",
            "refs/remotes/origin/main",
            f"refs/remotes/origin/{baseline.CTRL_BATON_FEATURE_BRANCH}",
        }
    )
    view = pr_view(
        branch="main",
        main_oid=M,
        origin_main_oid=M,
        feature_remote_oid=F,
        all_refs=refs,
    )
    return view._replace(**overrides)


def local_main_merge_view(**overrides: object) -> baseline.CtrlBatonGitView:
    view = committed_view(
        branch="main",
        head_oid=M,
        head_parents=(H0, F),
        feature_parents=(H0,),
        head_tree_oid=FEATURE_TREE,
        feature_tree_oid=FEATURE_TREE,
        main_oid=M,
        origin_main_oid=M,
        feature_local_oid=F,
        feature_remote_oid=F,
        upstream="origin/main",
        all_refs=baseline.CTRL_BATON_FEATURE_PUBLISHED_REFS,
    )
    return view._replace(**overrides)


def dirty_view(**overrides: object) -> baseline.CtrlBatonGitView:
    view = base_view(
        branch="main",
        feature_local_oid=None,
        upstream="origin/main",
        all_refs=baseline.CTRL_BATON_DIRTY_REFS,
        tracked=frozenset(baseline.task08_repository_files()),
        staged=frozenset(),
        staged_added=frozenset(),
        staged_modified=frozenset(),
        unstaged=baseline.CTRL_BATON_A62R_EXPECTED_MODIFIED,
        untracked=baseline.CTRL_BATON_A62R_EXPECTED_UNTRACKED,
    )
    return view._replace(**overrides)


def classify(
    view: baseline.CtrlBatonGitView,
    context: baseline.CtrlBatonGithubContext | None = None,
) -> tuple[str, str]:
    return baseline.classify_ctrl_baton_state_machine(
        view,
        context or local_github_context(),
    )


def run_temp_git(
    root: Path,
    *args: str,
    input_bytes: bytes | None = None,
) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"temp_git_failed:{args}:{result.stderr.decode('utf-8', errors='replace')}"
        )
    return result.stdout


class CanonicalRepositoryBytesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(
            prefix="smial_canonical_blob_test_"
        )
        self.root = Path(self.temporary.name)
        run_temp_git(self.root, "init", "--quiet")
        run_temp_git(self.root, "config", "core.autocrlf", "false")
        (self.root / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
        self.lf = b"alpha\nbeta\n"
        (self.root / "sample.txt").write_bytes(self.lf)
        run_temp_git(self.root, "add", "--", ".gitattributes", "sample.txt")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def resolve(
        self,
        relative: str,
        *,
        allow_worktree_candidate: bool = False,
    ) -> baseline.CanonicalRepositoryContent:
        with mock.patch.object(baseline, "ROOT", self.root):
            return baseline.canonical_repository_content(
                relative,
                allow_worktree_candidate=allow_worktree_candidate,
            )

    def test_index_blob_sha256_uses_index_content(self) -> None:
        result = self.resolve("sample.txt")
        self.assertEqual(result.source, "INDEX_BLOB")
        self.assertEqual(result.content, self.lf)
        self.assertEqual(result.sha256, hashlib.sha256(self.lf).hexdigest())
        self.assertEqual(
            result.git_oid,
            run_temp_git(self.root, "rev-parse", ":sample.txt")
            .decode("ascii")
            .strip(),
        )

    def test_committed_blob_sha256_uses_index_blob(self) -> None:
        run_temp_git(
            self.root,
            "-c",
            "user.name=SMIAL Test",
            "-c",
            "user.email=smial-test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        )
        result = self.resolve("sample.txt")
        committed = run_temp_git(
            self.root, "cat-file", "blob", "HEAD:sample.txt"
        )
        self.assertEqual(result.source, "INDEX_BLOB")
        self.assertEqual(result.content, committed)
        self.assertEqual(result.sha256, hashlib.sha256(committed).hexdigest())

    def test_crlf_worktree_resolves_to_lf_and_proves_hash_object_parity(self) -> None:
        crlf = self.lf.replace(b"\n", b"\r\n")
        (self.root / "sample.txt").write_bytes(crlf)
        result = self.resolve(
            "sample.txt",
            allow_worktree_candidate=True,
        )
        oracle = run_temp_git(
            self.root,
            "hash-object",
            "--path=sample.txt",
            "--stdin",
            input_bytes=crlf,
        ).decode("ascii").strip()
        self.assertEqual(result.source, "WORKTREE_CLEAN_CANDIDATE")
        self.assertEqual(result.content, self.lf)
        self.assertEqual(result.git_oid, oracle)
        self.assertEqual(result.sha256, hashlib.sha256(self.lf).hexdigest())
        self.assertNotEqual(
            hashlib.sha256(crlf).hexdigest(),
            result.sha256,
        )

    def test_missing_index_entry_fails_closed(self) -> None:
        (self.root / "untracked.txt").write_bytes(b"untracked\n")
        with self.assertRaisesRegex(
            baseline.CanonicalRepositoryBytesError,
            "canonical_index_entry_missing",
        ):
            self.resolve("untracked.txt")

    def test_untracked_candidate_requires_explicit_candidate_authority(self) -> None:
        content = b"untracked\n"
        (self.root / "untracked.txt").write_bytes(content)
        result = self.resolve(
            "untracked.txt",
            allow_worktree_candidate=True,
        )
        self.assertEqual(result.source, "WORKTREE_CLEAN_CANDIDATE")
        self.assertEqual(result.content, content)
        self.assertEqual(result.sha256, hashlib.sha256(content).hexdigest())

    def test_non_blob_index_mode_fails_closed(self) -> None:
        run_temp_git(
            self.root,
            "-c",
            "user.name=SMIAL Test",
            "-c",
            "user.email=smial-test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        )
        commit_oid = run_temp_git(self.root, "rev-parse", "HEAD").decode().strip()
        run_temp_git(
            self.root,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{commit_oid},gitlink",
        )
        with self.assertRaisesRegex(
            baseline.CanonicalRepositoryBytesError,
            "canonical_index_mode_not_blob",
        ):
            self.resolve("gitlink")

    def test_custom_filter_fails_closed(self) -> None:
        (self.root / ".gitattributes").write_bytes(
            b"*.txt filter=custom text eol=lf\n"
        )
        (self.root / "sample.txt").write_bytes(b"changed\n")
        with self.assertRaisesRegex(
            baseline.CanonicalRepositoryBytesError,
            "canonical_custom_filter_unsupported",
        ):
            self.resolve("sample.txt", allow_worktree_candidate=True)

    def test_working_tree_encoding_fails_closed(self) -> None:
        (self.root / ".gitattributes").write_bytes(
            b"*.txt text working-tree-encoding=UTF-16 eol=lf\n"
        )
        (self.root / "sample.txt").write_bytes(b"changed\n")
        with self.assertRaisesRegex(
            baseline.CanonicalRepositoryBytesError,
            "canonical_working_tree_encoding_unsupported",
        ):
            self.resolve("sample.txt", allow_worktree_candidate=True)

    def test_ambiguous_eol_policy_fails_closed(self) -> None:
        (self.root / ".gitattributes").write_bytes(b"*.txt text=auto\n")
        (self.root / "sample.txt").write_bytes(b"changed\n")
        with self.assertRaisesRegex(
            baseline.CanonicalRepositoryBytesError,
            "canonical_eol_policy_ambiguous",
        ):
            self.resolve("sample.txt", allow_worktree_candidate=True)

    def test_unsafe_repository_relative_path_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            baseline.CanonicalRepositoryBytesError,
            "canonical_path_unsafe",
        ):
            self.resolve("../sample.txt", allow_worktree_candidate=True)

    def test_synthetic_bare_cr_fails_closed(self) -> None:
        (self.root / "sample.txt").write_bytes(b"alpha\rbeta\n")
        with self.assertRaisesRegex(
            baseline.CanonicalRepositoryBytesError,
            "canonical_bare_cr_unsupported",
        ):
            self.resolve("sample.txt", allow_worktree_candidate=True)


class FixtureManifestCanonicalIntegrityTests(unittest.TestCase):
    MANIFEST = "tests/fixtures/baton/fixture_manifest.json"
    REPAIRED = {
        "file_outside_managed_write_set": (
            "b0f59b2c5527fb8d48bb931b0df3e8a6d96cd93aa2c02e86fd27b5c6992cee3d"
        ),
        "receipt_pass_full_not_run": (
            "6a90eda9767964b1f7adfdad48e5bed6e946257553547cab33e3b86df38b12f0"
        ),
        "receipt_pass_targeted_skipped": (
            "ecb7b84aabd7a4b5fab88d3db5124190f68118df33892ec86424f8fb3ba49f1a"
        ),
        "receipt_embedded_windows_path": (
            "82f900ef66204eb98569aac93a734c7c1214219eff9598b4742471ae40fc21c1"
        ),
        "receipt_embedded_posix_home": (
            "a236dab93910971da4625cc31952c318dc3f87d3258a38e071390282259a2ed6"
        ),
        "receipt_password_assignment": (
            "0deb4cc3f2993bd0bfca7337a8c5e6615d696f5e172027d9206e1cb49bd95f7e"
        ),
        "receipt_token_assignment": (
            "8ddd0167a6e5b8af66cccebd533c51c98c66de1e099e5e666cf8ba1d57136f8f"
        ),
        "receipt_no_change_with_files": (
            "5ead9723ec9df138a9692ff29691b55ea82943954bc4a7a77dc95d7be983cb86"
        ),
        "issue_body_crlf": (
            "658ce00e470510de2151b67cfa45684023ba25357f44bace39dcd73ad970417e"
        ),
    }

    @classmethod
    def current_manifest(cls) -> dict:
        return json.loads((ROOT / cls.MANIFEST).read_text(encoding="utf-8"))

    def test_manifest_keeps_exact_schema_order_and_semantics(self) -> None:
        current = self.current_manifest()
        committed = json.loads(
            run_temp_git(ROOT, "show", f"HEAD:{self.MANIFEST}").decode("utf-8")
        )
        self.assertEqual(current["manifest_schema"], committed["manifest_schema"])
        self.assertEqual(current["schema_version"], committed["schema_version"])
        self.assertEqual(len(current["fixtures"]), 37)
        self.assertEqual(
            [
                {key: value for key, value in entry.items() if key != "sha256"}
                for entry in current["fixtures"]
            ],
            [
                {key: value for key, value in entry.items() if key != "sha256"}
                for entry in committed["fixtures"]
            ],
        )

    def test_all_37_fixture_hashes_use_canonical_git_content(self) -> None:
        manifest = self.current_manifest()
        for entry in manifest["fixtures"]:
            with self.subTest(fixture=entry["id"]):
                resolved = baseline.canonical_repository_content(
                    entry["path"],
                    allow_worktree_candidate=True,
                )
                self.assertEqual(entry["sha256"], resolved.sha256)

    def test_all_nine_prior_windows_drift_cases_are_repaired(self) -> None:
        observed = {
            entry["id"]: entry["sha256"]
            for entry in self.current_manifest()["fixtures"]
            if entry["id"] in self.REPAIRED
        }
        self.assertEqual(observed, self.REPAIRED)

    def test_fixture_payload_files_are_unchanged_from_feature_commit(self) -> None:
        paths = sorted(
            {entry["path"] for entry in self.current_manifest()["fixtures"]}
        )
        result = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *paths],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_all_190_catalog_assets_have_canonical_integrity(self) -> None:
        sweep = baseline.canonical_catalog_integrity_sweep(
            allow_worktree_candidate=True
        )
        self.assertEqual(sweep.asset_count, 190)
        self.assertGreater(sweep.checked_sha256, 0)
        self.assertEqual(sweep.mismatches, ())


class LocalStagedStateTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A62R_CANDIDATE_STAGED",
        "BATON_FEATURE_LOCAL",
    )

    def test_exact_current_staged_state_passes(self) -> None:
        self.assertEqual(classify(base_view()), self.EXPECTED)
        self.assertEqual(len(base_view().staged), 84)
        self.assertEqual(len(base_view().tracked), 225)

    def test_missing_path_fails(self) -> None:
        missing = frozenset(set(EXPECTED_CHANGED) - {next(iter(EXPECTED_CHANGED))})
        self.assertNotEqual(classify(base_view(staged=missing)), self.EXPECTED)

    def test_extra_path_fails(self) -> None:
        extra = EXPECTED_CHANGED | {"unexpected.txt"}
        self.assertNotEqual(classify(base_view(staged=extra)), self.EXPECTED)

    def test_wrong_branch_fails(self) -> None:
        self.assertNotEqual(classify(base_view(branch="main")), self.EXPECTED)

    def test_wrong_main_or_origin_main_oid_fails(self) -> None:
        for field in ("main_oid", "origin_main_oid"):
            with self.subTest(field=field):
                self.assertNotEqual(
                    classify(base_view(**{field: "a" * 40})),
                    self.EXPECTED,
                )

    def test_unstaged_path_fails(self) -> None:
        self.assertNotEqual(
            classify(base_view(unstaged=frozenset({"AGENTS.md"}))),
            self.EXPECTED,
        )

    def test_conflict_fails(self) -> None:
        self.assertNotEqual(
            classify(base_view(conflicts=frozenset({"AGENTS.md"}))),
            self.EXPECTED,
        )

    def test_published_remote_ref_fails(self) -> None:
        self.assertNotEqual(
            classify(
                base_view(
                    feature_remote_oid=H0,
                    all_refs=baseline.CTRL_BATON_FEATURE_PUBLISHED_REFS,
                )
            ),
            self.EXPECTED,
        )


class RepairStagedStateTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A69_PR_CI_REPAIR_STAGED",
        "BATON_FEATURE_PUBLISHED_REPAIR_STAGED",
    )

    def test_exact_a69_repair_staged_state_passes(self) -> None:
        view = repair_staged_view()
        self.assertEqual(classify(view), self.EXPECTED)
        self.assertEqual(len(view.staged), 15)
        self.assertEqual(len(view.index_base_diff), 84)
        self.assertEqual(len(view.tracked), 225)

    def test_missing_or_extra_repair_path_fails(self) -> None:
        missing = frozenset(
            set(baseline.CTRL_BATON_A69_REPAIR_PATHS)
            - {next(iter(baseline.CTRL_BATON_A69_REPAIR_PATHS))}
        )
        extra = baseline.CTRL_BATON_A69_REPAIR_PATHS | {"unexpected.txt"}
        for inventory in (missing, extra):
            with self.subTest(inventory_count=len(inventory)):
                self.assertNotEqual(
                    classify(
                        repair_staged_view(
                            staged=inventory,
                            staged_modified=inventory,
                        )
                    ),
                    self.EXPECTED,
                )

    def test_unstaged_untracked_or_conflict_fails(self) -> None:
        for field in ("unstaged", "untracked", "conflicts"):
            with self.subTest(field=field):
                self.assertNotEqual(
                    classify(
                        repair_staged_view(
                            **{field: frozenset({"unexpected.txt"})}
                        )
                    ),
                    self.EXPECTED,
                )

    def test_wrong_branch_or_upstream_fails(self) -> None:
        for field, value in (
            ("branch", "main"),
            ("upstream", None),
            ("upstream", "origin/main"),
        ):
            with self.subTest(field=field, value=value):
                self.assertNotEqual(
                    classify(repair_staged_view(**{field: value})),
                    self.EXPECTED,
                )

    def test_remote_or_main_oid_drift_fails(self) -> None:
        for field in ("feature_remote_oid", "main_oid", "origin_main_oid"):
            with self.subTest(field=field):
                self.assertNotEqual(
                    classify(repair_staged_view(**{field: "a" * 40})),
                    self.EXPECTED,
                )

    def test_h0_to_index_inventory_drift_fails(self) -> None:
        missing = frozenset(
            set(EXPECTED_CHANGED) - {next(iter(EXPECTED_CHANGED))}
        )
        extra = EXPECTED_CHANGED | {"unexpected.txt"}
        for inventory in (missing, extra):
            with self.subTest(inventory_count=len(inventory)):
                self.assertNotEqual(
                    classify(
                        repair_staged_view(index_base_diff=inventory)
                    ),
                    self.EXPECTED,
                )

    def test_wrong_staged_catalog_version_fails(self) -> None:
        self.assertNotEqual(
            classify(repair_staged_view(index_catalog_version="0.8.1")),
            self.EXPECTED,
        )


class FinalReconciliationStagedStateTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A613_FINAL_RECONCILIATION_STAGED",
        "BATON_FEATURE_PUBLISHED_RECONCILIATION_STAGED",
    )

    def test_exact_a613_reconciliation_staged_state_passes(self) -> None:
        view = reconciliation_staged_view()
        self.assertEqual(classify(view), self.EXPECTED)
        self.assertEqual(len(view.staged), 12)
        self.assertEqual(len(view.index_base_diff), 84)
        self.assertEqual(len(view.tracked), 225)

    def test_missing_or_extra_reconciliation_path_fails(self) -> None:
        missing = frozenset(
            set(baseline.CTRL_BATON_A613_RECONCILIATION_PATHS)
            - {next(iter(baseline.CTRL_BATON_A613_RECONCILIATION_PATHS))}
        )
        extra = (
            baseline.CTRL_BATON_A613_RECONCILIATION_PATHS
            | {"unexpected.txt"}
        )
        for inventory in (missing, extra):
            with self.subTest(inventory_count=len(inventory)):
                self.assertNotEqual(
                    classify(
                        reconciliation_staged_view(
                            staged=inventory,
                            staged_modified=inventory,
                        )
                    ),
                    self.EXPECTED,
                )

    def test_eighty_fifth_base_to_index_path_fails(self) -> None:
        inventory = EXPECTED_CHANGED | {"unexpected.txt"}
        self.assertNotEqual(
            classify(
                reconciliation_staged_view(index_base_diff=inventory)
            ),
            self.EXPECTED,
        )

    def test_unstaged_untracked_or_conflict_fails(self) -> None:
        for field in ("unstaged", "untracked", "conflicts"):
            with self.subTest(field=field):
                self.assertNotEqual(
                    classify(
                        reconciliation_staged_view(
                            **{field: frozenset({"unexpected.txt"})}
                        )
                    ),
                    self.EXPECTED,
                )

    def test_wrong_branch_or_upstream_fails(self) -> None:
        for field, value in (
            ("branch", "main"),
            ("upstream", None),
            ("upstream", "origin/main"),
        ):
            with self.subTest(field=field, value=value):
                self.assertNotEqual(
                    classify(
                        reconciliation_staged_view(**{field: value})
                    ),
                    self.EXPECTED,
                )

    def test_local_remote_or_main_ref_drift_fails(self) -> None:
        for field in (
            "feature_local_oid",
            "feature_remote_oid",
            "main_oid",
            "origin_main_oid",
        ):
            with self.subTest(field=field):
                self.assertNotEqual(
                    classify(
                        reconciliation_staged_view(**{field: "a" * 40})
                    ),
                    self.EXPECTED,
                )

    def test_wrong_catalog_version_fails(self) -> None:
        self.assertNotEqual(
            classify(
                reconciliation_staged_view(index_catalog_version="0.8.2")
            ),
            self.EXPECTED,
        )


class LocalMainRepairStagedStateTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A618_LOCAL_MAIN_REPAIR_STAGED",
        "BATON_FEATURE_PUBLISHED_LOCAL_MAIN_REPAIR_STAGED",
    )

    def test_exact_local_main_repair_stage_passes(self) -> None:
        view = local_main_repair_staged_view()
        self.assertEqual(classify(view), self.EXPECTED)
        self.assertEqual(len(view.staged), 12)
        self.assertEqual(len(view.index_base_diff), 84)
        self.assertEqual(len(view.tracked), 225)

    def test_mixed_inventory_or_catalog_checkpoint_fails(self) -> None:
        missing = frozenset(
            set(baseline.CTRL_BATON_A618_LOCAL_MAIN_REPAIR_PATHS)
            - {next(iter(baseline.CTRL_BATON_A618_LOCAL_MAIN_REPAIR_PATHS))}
        )
        mutations = (
            {"staged": missing, "staged_modified": missing},
            {"index_base_diff": EXPECTED_CHANGED | {"unexpected.txt"}},
            {"index_catalog_version": "0.8.3"},
            {"head_catalog_version": "0.8.2"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotEqual(
                    classify(local_main_repair_staged_view(**mutation)),
                    self.EXPECTED,
                )

    def test_ref_context_or_worktree_drift_fails(self) -> None:
        mutations = (
            {"feature_local_oid": "a" * 40},
            {"feature_remote_oid": "a" * 40},
            {"main_oid": "a" * 40},
            {"origin_main_oid": "a" * 40},
            {"upstream": "origin/main"},
            {"unstaged": frozenset({"unexpected.txt"})},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotEqual(
                    classify(local_main_repair_staged_view(**mutation)),
                    self.EXPECTED,
                )
        self.assertNotEqual(
            classify(local_main_repair_staged_view(), pr_github_context()),
            self.EXPECTED,
        )


class LocalCommittedStateTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A62_FEATURE_COMMITTED",
        "BATON_FEATURE_LOCAL",
    )

    def test_exact_single_feature_commit_passes(self) -> None:
        self.assertEqual(classify(committed_view()), self.EXPECTED)

    def test_wrong_parent_fails(self) -> None:
        self.assertNotEqual(
            classify(committed_view(head_parents=(INTERMEDIATE,))),
            self.EXPECTED,
        )

    def test_multiple_commits_after_base_fail(self) -> None:
        self.assertNotEqual(
            classify(
                committed_view(
                    head_parents=(INTERMEDIATE,),
                    feature_parents=(INTERMEDIATE,),
                )
            ),
            self.EXPECTED,
        )

    def test_partial_or_extra_inventory_fails(self) -> None:
        missing = frozenset(set(EXPECTED_CHANGED) - {next(iter(EXPECTED_CHANGED))})
        extra = EXPECTED_CHANGED | {"unexpected.txt"}
        for inventory in (missing, extra):
            with self.subTest(inventory_count=len(inventory)):
                self.assertNotEqual(
                    classify(committed_view(base_diff=inventory)),
                    self.EXPECTED,
                )

    def test_dirty_worktree_fails(self) -> None:
        self.assertNotEqual(
            classify(committed_view(unstaged=frozenset({"AGENTS.md"}))),
            self.EXPECTED,
        )

    def test_tree_path_or_catalog_version_drift_fails(self) -> None:
        for field, value in (
            ("head_tree_path_count", 224),
            ("head_tree_path_count", 226),
            ("head_catalog_version", "0.8.2"),
        ):
            with self.subTest(field=field, value=value):
                self.assertNotEqual(
                    classify(committed_view(**{field: value})),
                    self.EXPECTED,
                )


class PublishedFeatureStateTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A62_FEATURE_COMMITTED",
        "BATON_FEATURE_PUBLISHED",
    )

    def test_exact_upstream_and_matching_remote_oid_pass(self) -> None:
        self.assertEqual(classify(published_view()), self.EXPECTED)
        self.assertNotEqual(published_view().head_oid, F2)

    def test_missing_upstream_fails(self) -> None:
        self.assertNotEqual(
            classify(published_view(upstream=None)),
            self.EXPECTED,
        )

    def test_stale_remote_oid_fails(self) -> None:
        self.assertNotEqual(
            classify(published_view(feature_remote_oid="a" * 40)),
            self.EXPECTED,
        )

    def test_main_ref_drift_fails(self) -> None:
        self.assertNotEqual(
            classify(published_view(main_oid="a" * 40)),
            self.EXPECTED,
        )

    def test_unexpected_ref_fails(self) -> None:
        refs = published_view().all_refs | {"refs/heads/unexpected"}
        self.assertNotEqual(
            classify(published_view(all_refs=refs)),
            self.EXPECTED,
        )


class AheadOfPublishedFeatureStateTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A62_FEATURE_COMMITTED",
        "BATON_FEATURE_AHEAD_OF_PUBLISHED",
    )

    def test_exact_amended_commit_ahead_of_old_remote_passes(self) -> None:
        self.assertEqual(classify(ahead_of_published_view()), self.EXPECTED)

    def test_local_head_equal_to_f3_fails(self) -> None:
        self.assertNotEqual(
            classify(
                ahead_of_published_view(
                    head_oid=F3,
                    feature_local_oid=F3,
                )
            ),
            self.EXPECTED,
        )

    def test_multiple_commits_after_base_fail(self) -> None:
        self.assertNotEqual(
            classify(
                ahead_of_published_view(
                    head_parents=(INTERMEDIATE,),
                    feature_parents=(INTERMEDIATE,),
                    commits_after_base=2,
                )
            ),
            self.EXPECTED,
        )

    def test_wrong_parent_fails(self) -> None:
        self.assertNotEqual(
            classify(
                ahead_of_published_view(
                    head_parents=(INTERMEDIATE,),
                    feature_parents=(INTERMEDIATE,),
                )
            ),
            self.EXPECTED,
        )

    def test_wrong_subject_fails(self) -> None:
        self.assertNotEqual(
            classify(ahead_of_published_view(head_subject="wrong")),
            self.EXPECTED,
        )

    def test_partial_or_extra_original_inventory_fails(self) -> None:
        missing = frozenset(
            set(EXPECTED_CHANGED) - {next(iter(EXPECTED_CHANGED))}
        )
        extra = EXPECTED_CHANGED | {"unexpected.txt"}
        for inventory in (missing, extra):
            with self.subTest(inventory_count=len(inventory)):
                self.assertNotEqual(
                    classify(ahead_of_published_view(base_diff=inventory)),
                    self.EXPECTED,
                )

    def test_tree_path_drift_fails(self) -> None:
        for count in (224, 226):
            with self.subTest(count=count):
                self.assertNotEqual(
                    classify(
                        ahead_of_published_view(
                            head_tree_path_count=count
                        )
                    ),
                    self.EXPECTED,
                )

    def test_committed_catalog_version_drift_fails(self) -> None:
        self.assertNotEqual(
            classify(
                ahead_of_published_view(head_catalog_version="0.8.2")
            ),
            self.EXPECTED,
        )

    def test_remote_oid_must_be_exact_f3(self) -> None:
        for remote in (None, "a" * 40, OLD_F, F2, F):
            with self.subTest(remote=remote):
                self.assertNotEqual(
                    classify(ahead_of_published_view(feature_remote_oid=remote)),
                    self.EXPECTED,
                )

    def test_dirty_tree_fails(self) -> None:
        self.assertNotEqual(
            classify(
                ahead_of_published_view(
                    unstaged=frozenset({"unexpected.txt"})
                )
            ),
            self.EXPECTED,
        )

    def test_main_drift_fails(self) -> None:
        self.assertNotEqual(
            classify(ahead_of_published_view(main_oid="a" * 40)),
            self.EXPECTED,
        )


class PullRequestMergeCheckoutTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A62_PR_MERGE_CHECKOUT",
        "GITHUB_PR_MERGE_CHECKOUT",
    )

    def test_exact_synthetic_merge_checkout_passes(self) -> None:
        self.assertEqual(classify(pr_view(), pr_github_context()), self.EXPECTED)

    def test_wrong_event_ref_base_or_head_fails(self) -> None:
        mutations = (
            {"event_name": "push"},
            {"ref": "refs/heads/main"},
            {"base_ref": "other"},
            {"head_ref": "other"},
            {"event_base_ref": "other"},
            {"event_head_ref": "other"},
            {"event_base_sha": "a" * 40},
            {"event_head_sha": "a" * 40},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotEqual(
                    classify(pr_view(), pr_github_context(**mutation)),
                    self.EXPECTED,
                )

    def test_attached_branch_fails(self) -> None:
        self.assertNotEqual(
            classify(
                pr_view(branch=baseline.CTRL_BATON_FEATURE_BRANCH),
                pr_github_context(),
            ),
            self.EXPECTED,
        )

    def test_wrong_parent_order_fails(self) -> None:
        self.assertNotEqual(
            classify(pr_view(head_parents=(F, H0)), pr_github_context()),
            self.EXPECTED,
        )

    def test_missing_feature_parent_fails(self) -> None:
        self.assertNotEqual(
            classify(pr_view(feature_parents=()), pr_github_context()),
            self.EXPECTED,
        )

    def test_merge_tree_drift_fails(self) -> None:
        self.assertNotEqual(
            classify(
                pr_view(head_tree_oid=MERGE_TREE_DRIFT),
                pr_github_context(),
            ),
            self.EXPECTED,
        )

    def test_diff_inventory_drift_fails(self) -> None:
        partial = frozenset(
            set(EXPECTED_CHANGED) - {next(iter(EXPECTED_CHANGED))}
        )
        self.assertNotEqual(
            classify(pr_view(base_diff=partial), pr_github_context()),
            self.EXPECTED,
        )


class MainMergeCheckoutTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A62_MAIN_MERGE_COMMITTED",
        "GITHUB_MAIN_PUSH_CHECKOUT",
    )

    def test_exact_two_parent_merge_passes(self) -> None:
        self.assertEqual(
            classify(main_merge_view(), push_github_context()),
            self.EXPECTED,
        )

    def test_direct_main_single_parent_commit_fails(self) -> None:
        self.assertNotEqual(
            classify(
                main_merge_view(
                    head_parents=(H0,),
                    feature_parents=(),
                ),
                push_github_context(),
            ),
            self.EXPECTED,
        )

    def test_squash_merge_fails(self) -> None:
        self.assertNotEqual(
            classify(
                main_merge_view(
                    head_parents=(H0,),
                    feature_parents=(),
                    feature_remote_oid=None,
                ),
                push_github_context(),
            ),
            self.EXPECTED,
        )

    def test_fast_forward_merge_fails(self) -> None:
        self.assertNotEqual(
            classify(
                main_merge_view(
                    head_oid=F,
                    head_parents=(H0,),
                    main_oid=F,
                    origin_main_oid=F,
                ),
                push_github_context(sha=F, event_after_sha=F),
            ),
            self.EXPECTED,
        )

    def test_swapped_parents_fail(self) -> None:
        self.assertNotEqual(
            classify(
                main_merge_view(head_parents=(F, H0)),
                push_github_context(),
            ),
            self.EXPECTED,
        )

    def test_hidden_merge_content_changes_fail(self) -> None:
        self.assertNotEqual(
            classify(
                main_merge_view(head_tree_oid=MERGE_TREE_DRIFT),
                push_github_context(),
            ),
            self.EXPECTED,
        )


class LocalMainPostMergeTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_BATON_A62_MAIN_MERGE_COMMITTED",
        "BATON_MAIN_LOCAL_POST_MERGE",
    )

    def test_exact_local_main_with_preserved_feature_refs_passes(self) -> None:
        self.assertEqual(classify(local_main_merge_view()), self.EXPECTED)

    def test_merge_shape_and_content_drift_fail_closed(self) -> None:
        mutations = (
            {"head_parents": (H0,), "feature_parents": ()},
            {
                "head_oid": F,
                "head_parents": (H0,),
                "main_oid": F,
                "origin_main_oid": F,
            },
            {"head_parents": (F, H0)},
            {"head_tree_oid": MERGE_TREE_DRIFT},
            {"base_diff": EXPECTED_CHANGED | {"unexpected.txt"}},
            {"head_catalog_version": "0.8.3"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotEqual(
                    classify(local_main_merge_view(**mutation)),
                    self.EXPECTED,
                )

    def test_preserved_refs_upstream_context_and_cleanliness_are_exact(
        self,
    ) -> None:
        mutations = (
            {"feature_local_oid": None},
            {"feature_remote_oid": None},
            {"feature_remote_oid": "a" * 40},
            {"upstream": None},
            {
                "all_refs": frozenset(
                    {"refs/heads/main", "refs/remotes/origin/main"}
                )
            },
            {"unstaged": frozenset({"unexpected.txt"})},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotEqual(
                    classify(local_main_merge_view(**mutation)),
                    self.EXPECTED,
                )
        self.assertNotEqual(
            classify(local_main_merge_view(), push_github_context()),
            self.EXPECTED,
        )


class LegacyRegressionTests(unittest.TestCase):
    def test_exact_dirty_main_candidate_is_preserved(self) -> None:
        self.assertEqual(
            classify(dirty_view()),
            ("CTRL_BATON_A62R_CANDIDATE_DIRTY", "PUBLISHED_LOCAL"),
        )
        self.assertEqual(len(dirty_view().unstaged), 17)
        self.assertEqual(len(dirty_view().untracked), 67)

    def test_legacy_main_and_clean_clone_topologies_are_preserved(self) -> None:
        common = {
            "branch": "main",
            "head_oid": H0,
            "remotes": {"origin"},
            "fetch_urls": (baseline.EXPECTED_ORIGIN_URL,),
            "push_urls": (baseline.EXPECTED_ORIGIN_URL,),
            "fetch_refspecs": (baseline.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            "push_refspecs": (),
            "upstream": "origin/main",
            "local_branches": {"main"},
            "remote_tracking_refs": {"origin/main"},
            "tags": set(),
            "all_refs": {"refs/heads/main", "refs/remotes/origin/main"},
            "github_actions": False,
            "github_repository": None,
            "github_ref": None,
            "github_sha": None,
            "remote_head_target": None,
        }
        self.assertEqual(
            baseline.classify_git_topology(**common),
            "PUBLISHED_LOCAL",
        )
        clean = common | {
            "remote_tracking_refs": {"origin/HEAD", "origin/main"},
            "all_refs": {
                "refs/heads/main",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/main",
            },
            "remote_head_target": "refs/remotes/origin/main",
        }
        self.assertEqual(
            baseline.classify_git_topology(**clean),
            "CLEAN_CLONE",
        )

    def test_task08_committed_state_is_preserved(self) -> None:
        state = baseline.classify_state(
            head_oid="a" * 40,
            commit_count=baseline.TASK08_COMMIT_COUNT,
            parent_oid=baseline.TASK08_BASE_COMMIT_OID,
            tracked=baseline.task08_repository_files(),
            staged=set(),
            untracked=set(),
            unstaged=set(),
            commit_subject=baseline.TASK08_COMMIT_SUBJECT,
            commit_changed=set(baseline.TASK08_CHANGED_FILES),
        )
        self.assertEqual(state, "TASK08_ATOM8B_CANDIDATE_COMMITTED")

    def test_state_topology_combinations_are_exact(self) -> None:
        self.assertEqual(
            len(baseline.CTRL_BATON_A62_LIFECYCLE_COMBINATIONS),
            11,
        )
        self.assertEqual(
            baseline.CTRL_BATON_A62_LIFECYCLE_COMBINATIONS,
            {
                ("CTRL_BATON_A62R_CANDIDATE_DIRTY", "PUBLISHED_LOCAL"),
                (
                    "CTRL_BATON_A62R_CANDIDATE_STAGED",
                    "BATON_FEATURE_LOCAL",
                ),
                (
                    "CTRL_BATON_A69_PR_CI_REPAIR_STAGED",
                    "BATON_FEATURE_PUBLISHED_REPAIR_STAGED",
                ),
                (
                    "CTRL_BATON_A613_FINAL_RECONCILIATION_STAGED",
                    "BATON_FEATURE_PUBLISHED_RECONCILIATION_STAGED",
                ),
                (
                    "CTRL_BATON_A618_LOCAL_MAIN_REPAIR_STAGED",
                    "BATON_FEATURE_PUBLISHED_LOCAL_MAIN_REPAIR_STAGED",
                ),
                (
                    "CTRL_BATON_A62_FEATURE_COMMITTED",
                    "BATON_FEATURE_LOCAL",
                ),
                (
                    "CTRL_BATON_A62_FEATURE_COMMITTED",
                    "BATON_FEATURE_AHEAD_OF_PUBLISHED",
                ),
                (
                    "CTRL_BATON_A62_FEATURE_COMMITTED",
                    "BATON_FEATURE_PUBLISHED",
                ),
                (
                    "CTRL_BATON_A62_PR_MERGE_CHECKOUT",
                    "GITHUB_PR_MERGE_CHECKOUT",
                ),
                (
                    "CTRL_BATON_A62_MAIN_MERGE_COMMITTED",
                    "GITHUB_MAIN_PUSH_CHECKOUT",
                ),
                (
                    "CTRL_BATON_A62_MAIN_MERGE_COMMITTED",
                    "BATON_MAIN_LOCAL_POST_MERGE",
                ),
            },
        )
        self.assertEqual(
            len(baseline.CTRL_GENERIC_LIFECYCLE_COMBINATIONS),
            4,
        )
        self.assertEqual(
            baseline.CTRL_GENERIC_LIFECYCLE_COMBINATIONS,
            {
                (
                    "CTRL_GENERIC_CONTROL_FEATURE_COMMITTED",
                    "CTRL_GENERIC_FEATURE_LOCAL",
                ),
                (
                    "CTRL_GENERIC_CONTROL_FEATURE_COMMITTED",
                    "CTRL_GENERIC_FEATURE_AHEAD_OF_PUBLISHED",
                ),
                (
                    "CTRL_GENERIC_CONTROL_FEATURE_COMMITTED",
                    "CTRL_GENERIC_FEATURE_PUBLISHED",
                ),
                (
                    "CTRL_GENERIC_CONTROL_PR_MERGE_CHECKOUT",
                    "CTRL_GENERIC_PR_MERGE_CHECKOUT",
                ),
            },
        )


GENERIC_BRANCH = "ctrl/cursor-workplace-validation"
GENERIC_BASE = "a" * 40
GENERIC_HEAD = "b" * 40
GENERIC_TREE = "c" * 40
GENERIC_MERGE = "d" * 40


def generic_feature_view(**overrides: object) -> baseline.CtrlBatonGitView:
    refs = frozenset(
        {
            "refs/heads/main",
            "refs/remotes/origin/main",
            f"refs/heads/{GENERIC_BRANCH}",
        }
    )
    view = baseline.CtrlBatonGitView(
        GENERIC_BRANCH,
        GENERIC_HEAD,
        (GENERIC_BASE,),
        (GENERIC_BASE,),
        GENERIC_TREE,
        GENERIC_TREE,
        GENERIC_BASE,
        GENERIC_BASE,
        GENERIC_HEAD,
        None,
        None,
        frozenset({"origin"}),
        (baseline.EXPECTED_ORIGIN_URL,),
        (baseline.EXPECTED_ORIGIN_URL,),
        (baseline.EXPECTED_ORIGIN_FETCH_REFSPEC,),
        (),
        refs,
        EXPECTED_TRACKED,
        frozenset(),
        frozenset(),
        frozenset(),
        frozenset(),
        frozenset(),
        frozenset(),
        frozenset({"scripts/validate_baseline.py"}),
        "fix(control): isolate lifecycle skills in Cursor",
        1,
        frozenset(),
        None,
        len(EXPECTED_TRACKED),
        "0.8.4",
    )
    return view._replace(**overrides)


def generic_feature_published_view(**overrides: object) -> baseline.CtrlBatonGitView:
    view = generic_feature_view(
        feature_remote_oid=GENERIC_HEAD,
        upstream=f"origin/{GENERIC_BRANCH}",
        all_refs=frozenset(
            {
                "refs/heads/main",
                "refs/remotes/origin/main",
                f"refs/heads/{GENERIC_BRANCH}",
                f"refs/remotes/origin/{GENERIC_BRANCH}",
            }
        ),
    )
    return view._replace(**overrides)


GENERIC_REMOTE_TIP = "1" * 40
GENERIC_AHEAD_HEAD = "2" * 40
GENERIC_AHEAD_TREE = "3" * 40


def generic_feature_ahead_view(
    *,
    ahead_count: int = 1,
    **overrides: object,
) -> baseline.CtrlBatonGitView:
    view = generic_feature_published_view(
        head_oid=GENERIC_AHEAD_HEAD,
        head_parents=(GENERIC_REMOTE_TIP,),
        feature_parents=(GENERIC_REMOTE_TIP,),
        head_tree_oid=GENERIC_AHEAD_TREE,
        feature_tree_oid=GENERIC_AHEAD_TREE,
        feature_local_oid=GENERIC_AHEAD_HEAD,
        feature_remote_oid=GENERIC_REMOTE_TIP,
        feature_ahead_count=ahead_count,
        feature_remote_ancestor_ok=True,
        feature_ahead_linear_ok=True,
        feature_based_on_main_ok=True,
    )
    return view._replace(**overrides)


def generic_pr_view(**overrides: object) -> baseline.CtrlBatonGitView:
    refs = frozenset(
        {
            "refs/remotes/origin/main",
            f"refs/remotes/origin/{GENERIC_BRANCH}",
            "refs/remotes/pull/2/merge",
        }
    )
    view = generic_feature_view(
        branch=None,
        head_oid=GENERIC_MERGE,
        head_parents=(GENERIC_BASE, GENERIC_HEAD),
        main_oid=None,
        origin_main_oid=None,
        feature_local_oid=None,
        feature_remote_oid=GENERIC_HEAD,
        fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
        push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
        all_refs=refs,
        upstream=None,
    )
    return view._replace(**overrides)


def generic_pr_github_context(**overrides: object) -> baseline.CtrlBatonGithubContext:
    context = baseline.CtrlBatonGithubContext(
        True,
        baseline.EXPECTED_GITHUB_REPOSITORY,
        "pull_request",
        "refs/pull/2/merge",
        GENERIC_MERGE,
        "main",
        GENERIC_BRANCH,
        2,
        None,
        "main",
        GENERIC_BASE,
        GENERIC_BRANCH,
        GENERIC_HEAD,
        None,
        None,
    )
    return context._replace(**overrides)


class GenericControlFeatureCommittedTests(unittest.TestCase):
    LOCAL = (
        "CTRL_GENERIC_CONTROL_FEATURE_COMMITTED",
        "CTRL_GENERIC_FEATURE_LOCAL",
    )
    PUBLISHED = (
        "CTRL_GENERIC_CONTROL_FEATURE_COMMITTED",
        "CTRL_GENERIC_FEATURE_PUBLISHED",
    )
    AHEAD = (
        "CTRL_GENERIC_CONTROL_FEATURE_COMMITTED",
        "CTRL_GENERIC_FEATURE_AHEAD_OF_PUBLISHED",
    )

    def test_exact_local_generic_control_branch_passes(self) -> None:
        self.assertEqual(classify(generic_feature_view()), self.LOCAL)

    def test_exact_published_generic_control_branch_passes(self) -> None:
        self.assertEqual(
            classify(generic_feature_published_view()),
            self.PUBLISHED,
        )

    def test_exact_ahead_of_published_generic_control_branch_passes(self) -> None:
        for ahead_count in (1, 2, 3, baseline.CTRL_GENERIC_FEATURE_AHEAD_MAX):
            with self.subTest(ahead_count=ahead_count):
                self.assertEqual(
                    classify(generic_feature_ahead_view(ahead_count=ahead_count)),
                    self.AHEAD,
                )

    def test_ahead_over_max_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_feature_ahead_view(
                    ahead_count=baseline.CTRL_GENERIC_FEATURE_AHEAD_MAX + 1
                )
            ),
            self.AHEAD,
        )

    def test_ahead_remote_not_ancestor_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_feature_ahead_view(
                    feature_remote_ancestor_ok=False,
                    feature_ahead_linear_ok=False,
                )
            ),
            self.AHEAD,
        )

    def test_ahead_merge_in_range_fails(self) -> None:
        self.assertNotEqual(
            classify(generic_feature_ahead_view(feature_ahead_linear_ok=False)),
            self.AHEAD,
        )

    def test_ahead_wrong_upstream_fails(self) -> None:
        self.assertNotEqual(
            classify(generic_feature_ahead_view(upstream="origin/main")),
            self.AHEAD,
        )

    def test_ahead_main_drift_fails(self) -> None:
        self.assertNotEqual(
            classify(generic_feature_ahead_view(origin_main_oid=INTERMEDIATE)),
            self.AHEAD,
        )
        self.assertNotEqual(
            classify(generic_feature_ahead_view(feature_based_on_main_ok=False)),
            self.AHEAD,
        )

    def test_ahead_dirty_worktree_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_feature_ahead_view(
                    unstaged=frozenset({"scripts/validate_baseline.py"})
                )
            ),
            self.AHEAD,
        )

    def test_ahead_historical_baton_branch_is_not_generic(self) -> None:
        self.assertNotEqual(
            classify(
                generic_feature_ahead_view(
                    branch=baseline.CTRL_BATON_FEATURE_BRANCH
                )
            ),
            self.AHEAD,
        )

    def test_ahead_extra_ref_fails(self) -> None:
        refs = frozenset(
            {
                "refs/heads/main",
                "refs/remotes/origin/main",
                f"refs/heads/{GENERIC_BRANCH}",
                f"refs/remotes/origin/{GENERIC_BRANCH}",
                "refs/heads/feature/other",
            }
        )
        self.assertNotEqual(
            classify(generic_feature_ahead_view(all_refs=refs)),
            self.AHEAD,
        )

    def test_historical_baton_branch_is_not_generic(self) -> None:
        self.assertNotEqual(
            classify(
                generic_feature_view(branch=baseline.CTRL_BATON_FEATURE_BRANCH)
            ),
            self.LOCAL,
        )

    def test_direct_main_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_feature_view(
                    branch="main",
                    head_oid=GENERIC_BASE,
                    head_parents=(INTERMEDIATE,),
                    feature_local_oid=GENERIC_BASE,
                )
            ),
            self.LOCAL,
        )

    def test_wrong_base_or_head_fails(self) -> None:
        self.assertNotEqual(
            classify(generic_feature_view(head_parents=(INTERMEDIATE,))),
            self.LOCAL,
        )
        self.assertNotEqual(
            classify(generic_feature_view(main_oid=INTERMEDIATE)),
            self.LOCAL,
        )
        self.assertNotEqual(
            classify(generic_feature_view(origin_main_oid=INTERMEDIATE)),
            self.LOCAL,
        )

    def test_dirty_worktree_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_feature_view(
                    unstaged=frozenset({"scripts/validate_baseline.py"})
                )
            ),
            self.LOCAL,
        )

    def test_merge_commit_on_feature_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_feature_view(head_parents=(GENERIC_BASE, GENERIC_HEAD))
            ),
            self.LOCAL,
        )

    def test_non_control_branch_fails(self) -> None:
        self.assertNotEqual(
            classify(generic_feature_view(branch="feature/other")),
            self.LOCAL,
        )


class GenericControlPullRequestCheckoutTests(unittest.TestCase):
    EXPECTED = (
        "CTRL_GENERIC_CONTROL_PR_MERGE_CHECKOUT",
        "CTRL_GENERIC_PR_MERGE_CHECKOUT",
    )

    def test_exact_generic_pr_merge_checkout_passes(self) -> None:
        self.assertEqual(
            classify(generic_pr_view(), generic_pr_github_context()),
            self.EXPECTED,
        )

    def test_squash_or_fast_forward_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_pr_view(head_parents=(GENERIC_BASE,)),
                generic_pr_github_context(),
            ),
            self.EXPECTED,
        )
        self.assertNotEqual(
            classify(
                generic_pr_view(head_parents=(GENERIC_HEAD,)),
                generic_pr_github_context(event_head_sha=GENERIC_HEAD),
            ),
            self.EXPECTED,
        )

    def test_wrong_event_base_or_head_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_pr_view(),
                generic_pr_github_context(event_base_sha=INTERMEDIATE),
            ),
            self.EXPECTED,
        )
        self.assertNotEqual(
            classify(
                generic_pr_view(),
                generic_pr_github_context(event_head_sha=INTERMEDIATE),
            ),
            self.EXPECTED,
        )
        self.assertNotEqual(
            classify(
                generic_pr_view(),
                generic_pr_github_context(head_ref="feature/other"),
            ),
            self.EXPECTED,
        )

    def test_attached_branch_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_pr_view(branch=GENERIC_BRANCH),
                generic_pr_github_context(),
            ),
            self.EXPECTED,
        )

    def test_swapped_parents_fail(self) -> None:
        self.assertNotEqual(
            classify(
                generic_pr_view(head_parents=(GENERIC_HEAD, GENERIC_BASE)),
                generic_pr_github_context(),
            ),
            self.EXPECTED,
        )

    def test_merge_tree_drift_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_pr_view(head_tree_oid=MERGE_TREE_DRIFT),
                generic_pr_github_context(),
            ),
            self.EXPECTED,
        )

    def test_dirty_worktree_fails(self) -> None:
        self.assertNotEqual(
            classify(
                generic_pr_view(unstaged=frozenset({"README.md"})),
                generic_pr_github_context(),
            ),
            self.EXPECTED,
        )

    def test_historical_baton_head_ref_is_not_generic(self) -> None:
        self.assertNotEqual(
            classify(
                generic_pr_view(),
                generic_pr_github_context(
                    head_ref=baseline.CTRL_BATON_FEATURE_BRANCH,
                    event_head_ref=baseline.CTRL_BATON_FEATURE_BRANCH,
                ),
            ),
            self.EXPECTED,
        )


if __name__ == "__main__":
    unittest.main()
