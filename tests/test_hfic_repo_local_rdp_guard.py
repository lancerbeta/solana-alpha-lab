from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_root import DEFAULT_DATA_PLANE_RELATIVE
from solana_alpha_lab.factory.early_market_panel_importer import (
    EarlyMarketPanelImportError,
    PUBLISHED_RELATIVE,
    import_early_market_panel,
    inspect_canonical_targets,
)
from tests.test_early_market_panel_importer import FIXTURE, write_temp_capture


def _run(repo: Path, args: list[str]) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace"))


def _init_worktree(root: Path, gitignore: str = "local/\n") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _run(root, ["init", "--quiet"])
    (root / ".gitignore").write_text(gitignore, encoding="utf-8")
    return root


def _canonical_plane(worktree: Path) -> Path:
    path = worktree / DEFAULT_DATA_PLANE_RELATIVE
    path.mkdir(parents=True, exist_ok=True)
    return path


class RepoLocalRdpGuardTests(unittest.TestCase):
    def test_canonical_ignored_data_plane_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = _init_worktree(Path(tmp) / "repo")
            source = Path(tmp) / "source"
            shutil.copytree(FIXTURE, source)
            data_root = _canonical_plane(worktree)
            result = import_early_market_panel(
                source_root=source,
                data_root=data_root,
                source_receipt_path=source / "source_receipt.json",
                repo_root=worktree,
            )
            self.assertEqual(result["status"], "IMPORTED")
            self.assertEqual(result["provider_calls_actual"], 0)
            self.assertTrue((data_root / PUBLISHED_RELATIVE).is_file())

    def test_non_ignored_repository_descendant_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = _init_worktree(Path(tmp) / "repo")
            source = Path(tmp) / "source"
            shutil.copytree(FIXTURE, source)
            data_root = worktree / "tmp-not-ignored-rdp"
            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=source,
                    data_root=data_root,
                    source_receipt_path=source / "source_receipt.json",
                    repo_root=worktree,
                )
            self.assertEqual(str(raised.exception), "DATA_ROOT_INSIDE_GIT")
            self.assertFalse(data_root.exists())

    def test_ignored_but_non_canonical_local_descendant_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = _init_worktree(Path(tmp) / "repo")
            source = Path(tmp) / "source"
            shutil.copytree(FIXTURE, source)
            data_root = worktree / "local" / "other-plane"
            data_root.mkdir(parents=True)
            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=source,
                    data_root=data_root,
                    source_receipt_path=source / "source_receipt.json",
                    repo_root=worktree,
                )
            self.assertEqual(str(raised.exception), "DATA_ROOT_INSIDE_GIT")
            self.assertEqual(inspect_canonical_targets(data_root)["state"], "ABSENT")

    def test_tracked_or_staged_canonical_target_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = _init_worktree(Path(tmp) / "repo")
            source = Path(tmp) / "source"
            shutil.copytree(FIXTURE, source)
            data_root = _canonical_plane(worktree)
            planted = data_root / "tracked.txt"
            planted.write_text("planted", encoding="utf-8")
            _run(worktree, ["add", "-f", "--", "local/factory_v1/data_plane/tracked.txt"])
            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=source,
                    data_root=data_root,
                    source_receipt_path=source / "source_receipt.json",
                    repo_root=worktree,
                )
            self.assertEqual(str(raised.exception), "DATA_ROOT_INSIDE_GIT")
            self.assertEqual(planted.read_text(encoding="utf-8"), "planted")
            self.assertEqual(inspect_canonical_targets(data_root)["state"], "ABSENT")

    def test_git_descendant_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = _init_worktree(Path(tmp) / "repo")
            source = Path(tmp) / "source"
            shutil.copytree(FIXTURE, source)
            data_root = worktree / ".git" / "objects" / "panel-root"
            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=source,
                    data_root=data_root,
                    source_receipt_path=source / "source_receipt.json",
                    repo_root=worktree,
                )
            self.assertEqual(str(raised.exception), "DATA_ROOT_INSIDE_GIT")
            self.assertFalse(data_root.exists())

    def test_symlink_ancestor_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = _init_worktree(Path(tmp) / "repo")
            source = Path(tmp) / "source"
            shutil.copytree(FIXTURE, source)
            data_root = _canonical_plane(worktree)
            local_dir = worktree / "local"
            original_is_symlink = Path.is_symlink

            def synthetic_symlink(path: Path) -> bool:
                try:
                    if path.resolve() == local_dir.resolve():
                        return True
                except OSError:
                    pass
                return original_is_symlink(path)

            with patch.object(Path, "is_symlink", synthetic_symlink):
                with self.assertRaises(EarlyMarketPanelImportError) as raised:
                    import_early_market_panel(
                        source_root=source,
                        data_root=data_root,
                        source_receipt_path=source / "source_receipt.json",
                        repo_root=worktree,
                    )
                self.assertEqual(str(raised.exception), "DATA_ROOT_SYMLINK")
            self.assertEqual(inspect_canonical_targets(data_root)["state"], "ABSENT")

    def test_external_temp_data_root_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            result = import_early_market_panel(
                source_root=FIXTURE,
                data_root=data_root,
                source_receipt_path=FIXTURE / "source_receipt.json",
            )
            self.assertEqual(result["status"], "IMPORTED")
            self.assertEqual(result["provider_calls_actual"], 0)

    def test_git_command_failure_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = _init_worktree(Path(tmp) / "repo")
            source = Path(tmp) / "source"
            shutil.copytree(FIXTURE, source)
            data_root = _canonical_plane(worktree)

            def failing_runner(_repo: Path, _args: list[str]) -> tuple[int, bytes]:
                return 128, b""

            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=source,
                    data_root=data_root,
                    source_receipt_path=source / "source_receipt.json",
                    repo_root=worktree,
                    git_runner=failing_runner,
                )
            self.assertEqual(str(raised.exception), "GIT_GUARD_UNAVAILABLE")
            self.assertEqual(inspect_canonical_targets(data_root)["state"], "ABSENT")

    def test_production_shaped_dataset_is_idempotent_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_temp_capture(source, eligible=10, extra_missing=5)
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = import_early_market_panel(
                source_root=source,
                data_root=data_root,
                source_receipt_path=source / "source_receipt.json",
            )
            fingerprint = first["dataset_fingerprint"]
            published = (data_root / PUBLISHED_RELATIVE).read_bytes()
            second = import_early_market_panel(
                source_root=source,
                data_root=data_root,
                source_receipt_path=source / "source_receipt.json",
            )
            self.assertEqual(first["status"], "IMPORTED")
            self.assertEqual(second["status"], "IDEMPOTENT_REUSE")
            self.assertEqual(second["dataset_fingerprint"], fingerprint)
            self.assertEqual(second["epoch_material_changed"], False)
            self.assertEqual((data_root / PUBLISHED_RELATIVE).read_bytes(), published)
            self.assertEqual(first["provider_calls_actual"], 0)
            self.assertEqual(second["provider_calls_actual"], 0)


if __name__ == "__main__":
    unittest.main()
