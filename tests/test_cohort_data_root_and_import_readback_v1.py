from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.cohort_import_readback import (  # noqa: E402
    PASS_ALREADY_PRESENT_EXACT,
    STOP_IDENTITY_CONFLICT,
    build_cohort_import_readback,
    owner_import_terminal,
)
from solana_alpha_lab.factory.data_root import (  # noqa: E402
    DEFAULT_DATA_PLANE_RELATIVE,
    DataRootError,
    resolve_data_root,
    resolve_existing_data_root,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "a2@test")
    _git(path, "config", "user.name", "a2")
    (path / "README.md").write_text("a2\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")


class CanonicalDataRootTests(unittest.TestCase):
    def test_linked_worktree_resolves_principal_data_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            principal = Path(tmp) / "principal"
            linked = Path(tmp) / "linked"
            _init_repo(principal)
            _git(principal, "worktree", "add", str(linked), "-b", "linked-a2")
            try:
                from_principal = resolve_data_root(principal, env={})
                from_linked = resolve_data_root(linked, env={})
                expected = (principal / DEFAULT_DATA_PLANE_RELATIVE).resolve()
                self.assertEqual(from_principal, expected)
                self.assertEqual(from_linked, expected)
                self.assertEqual(from_principal, from_linked)
            finally:
                _git(principal, "worktree", "remove", "--force", str(linked))

    def test_non_git_without_explicit_or_env_is_typed_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "not-git"
            repo.mkdir()
            with self.assertRaises(DataRootError) as raised:
                resolve_data_root(repo, env={})
            self.assertEqual(raised.exception.code, "DATA_ROOT_NON_GIT_CONTEXT")
            discovered = resolve_existing_data_root(repo, env={})
            self.assertEqual(discovered.status, "UNAVAILABLE")
            self.assertEqual(discovered.error, "DATA_ROOT_NON_GIT_CONTEXT")


class CohortImportReadbackTests(unittest.TestCase):
    def test_readback_counts_c1_c2_once_without_absolute_path(self) -> None:
        lineage = {
            "corpus_dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
            "current_corpus_version": 2,
            "current_dataset_manifest_id": "MID-CURRENT",
            "cohorts": [
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1",
                    "content_sha256": "a" * 64,
                    "schedule_sha256": "b" * 64,
                    "source_sha256": "c" * 64,
                },
                {
                    "cohort_id": "REL-C2",
                    "release_id": "rel-c2",
                    "content_sha256": "d" * 64,
                    "schedule_sha256": "e" * 64,
                    "source_sha256": "f" * 64,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            data_root.mkdir()
            payload = build_cohort_import_readback(
                data_root,
                lineage=lineage,
                fingerprint="ab" * 32,
            )
        self.assertEqual(payload["schema"], "smial.cohort-import-readback")
        self.assertEqual(payload["corpus_version"], 2)
        self.assertEqual(len(payload["visible_cohorts"]), 2)
        self.assertEqual(payload["duplicate_cohort_count"], 0)
        self.assertEqual(payload["lineage_integrity"], "PASS")
        rendered = json.dumps(payload)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn(str(data_root), rendered)
        counts = {item["cohort_id"]: item["lineage_count"] for item in payload["visible_cohorts"]}
        self.assertEqual(counts["REL-C1"], 1)
        self.assertEqual(counts["REL-C2"], 1)
        self.assertTrue(all(item["status"] == "PRESENT_ONCE" for item in payload["visible_cohorts"]))

    def test_owner_terminals_for_reimport_and_conflict(self) -> None:
        self.assertEqual(
            owner_import_terminal("IDEMPOTENT_REIMPORT"),
            PASS_ALREADY_PRESENT_EXACT,
        )
        self.assertEqual(
            owner_import_terminal("COHORT_ALREADY_IMPORTED"),
            STOP_IDENTITY_CONFLICT,
        )
        self.assertEqual(
            owner_import_terminal("CANONICAL_TARGET_CONFLICT"),
            STOP_IDENTITY_CONFLICT,
        )
        self.assertEqual(
            owner_import_terminal("IDENTITY_CONFLICT"),
            STOP_IDENTITY_CONFLICT,
        )


class ImportLiveCliReadbackTests(unittest.TestCase):
    def test_cli_omitted_data_root_uses_canonical_default(self) -> None:
        parser_src = (ROOT / "scripts" / "discovery_evidence_release.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('import_live.add_argument("--data-root"', parser_src)
        self.assertNotRegex(
            parser_src,
            r'import_live.add_argument\(\s*"--data-root", type=Path, required=True',
        )
        self.assertIn('publish.add_argument("--data-root"', parser_src)
        self.assertNotRegex(
            parser_src,
            r'publish.add_argument\(\s*"--data-root", type=Path, required=True',
        )


if __name__ == "__main__":
    unittest.main()
