# tests/test_baton_scope.py
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from baton_contract import BatonContractError, path_in_managed_write_set  # noqa: E402
from baton_scope import (  # noqa: E402
    BatonScopeError,
    assert_path_contained,
    evaluate_scope,
    parse_porcelain_z,
    resolved_path_is_inside_root,
)


class BatonScopeTests(unittest.TestCase):
    def test_prefix_sibling_and_terminal_boundary(self) -> None:
        managed = ["docs/evidence/baton/**"]
        self.assertTrue(
            path_in_managed_write_set("docs/evidence/baton/x.json", managed)
        )
        self.assertFalse(
            path_in_managed_write_set("docs/evidence/baton_evil.txt", managed)
        )

    def test_case_bypass_forbidden(self) -> None:
        self.assertFalse(path_in_managed_write_set(".GIT/config", ["docs/**"]))
        self.assertFalse(path_in_managed_write_set("Wallet/seed.txt", ["docs/**"]))
        self.assertFalse(path_in_managed_write_set("Secrets/x", ["docs/**"]))

    def test_spaces_and_unicode_paths(self) -> None:
        managed = ["docs/evidence/baton/my file.json", "docs/evidence/baton/тест.json"]
        self.assertTrue(
            path_in_managed_write_set("docs/evidence/baton/my file.json", managed)
        )
        self.assertTrue(
            path_in_managed_write_set("docs/evidence/baton/тест.json", managed)
        )

    def test_rename_and_conflict_fail_closed(self) -> None:
        with self.assertRaises(BatonScopeError) as rename_ctx:
            parse_porcelain_z(b"R  new.txt\0old.txt\0")
        self.assertEqual(rename_ctx.exception.code, "rename_or_copy_forbidden")
        with self.assertRaises(BatonScopeError) as conflict_ctx:
            parse_porcelain_z(b"UU conflict.txt\0")
        self.assertEqual(conflict_ctx.exception.code, "conflict_status_forbidden")

    def test_pure_containment_helper(self) -> None:
        root = Path("/repo")
        self.assertTrue(resolved_path_is_inside_root(Path("/repo"), root))
        self.assertTrue(resolved_path_is_inside_root(Path("/repo/docs/a.txt"), root))
        self.assertFalse(resolved_path_is_inside_root(Path("/outside.txt"), root))
        self.assertFalse(resolved_path_is_inside_root(Path("/repo_evil/x"), root))

    def test_symlink_escape_via_injectable_resolution_boundary(self) -> None:
        """Critical coverage: no OS symlink privilege required (Ubuntu PASS)."""
        root = Path("/repo")
        outside = Path("/tmp/sibling_outside.txt")

        def resolve_escape(path: Path) -> Path:
            if path.as_posix().endswith("/docs/escape.txt"):
                return outside
            return path

        with self.assertRaises(BatonScopeError) as ctx:
            assert_path_contained(
                "docs/escape.txt",
                root=root,
                resolve_path=resolve_escape,
            )
        self.assertEqual(ctx.exception.code, "symlink_escape")

        with self.assertRaises(BatonScopeError) as porcelain_ctx:
            parse_porcelain_z(
                b"?? docs/escape.txt\0",
                root=root,
                resolve_path=resolve_escape,
            )
        self.assertEqual(porcelain_ctx.exception.code, "symlink_escape")

    def test_contained_resolved_path_allowed_via_injectable_boundary(self) -> None:
        root = Path("/repo")

        def resolve_inside(path: Path) -> Path:
            if path.as_posix().endswith("/docs/inside.txt"):
                return root / "docs" / "real.txt"
            return path

        assert_path_contained(
            "docs/inside.txt",
            root=root,
            resolve_path=resolve_inside,
        )
        result = parse_porcelain_z(
            b"?? docs/inside.txt\0",
            root=root,
            resolve_path=resolve_inside,
        )
        self.assertEqual(result["untracked_files"], ["docs/inside.txt"])

    def test_symlink_escape_integration_sibling_outside_repo(self) -> None:
        """When OS symlinks work: temporary root/repo + sibling outside.txt."""
        with tempfile.TemporaryDirectory() as temporary:
            outer = Path(temporary)
            outside = outer / "outside.txt"
            outside.write_text("x", encoding="utf-8")
            repo = outer / "repo"
            repo.mkdir()
            docs = repo / "docs"
            docs.mkdir()
            nested = docs / "escape.txt"
            try:
                nested.symlink_to(outside)
            except OSError:
                # Critical coverage already proven by injectable boundary tests.
                # Integration remains best-effort when privilege is unavailable.
                return
            with self.assertRaises(BatonScopeError) as ctx:
                parse_porcelain_z(b"?? docs/escape.txt\0", root=repo)
            self.assertEqual(ctx.exception.code, "symlink_escape")

            # Contained symlink (target stays inside repo) must be allowed.
            inside_target = docs / "real.txt"
            inside_target.write_text("ok", encoding="utf-8")
            contained = docs / "link.txt"
            try:
                contained.symlink_to(inside_target)
            except OSError:
                return
            allowed = parse_porcelain_z(b"?? docs/link.txt\0", root=repo)
            self.assertEqual(allowed["untracked_files"], ["docs/link.txt"])

    def test_evaluate_scope_detects_outside(self) -> None:
        inventory = {
            "changed_files": ["AGENTS.md"],
            "staged_files": [],
            "untracked_files": ["docs/evidence/baton/x.json"],
        }
        result = evaluate_scope(
            ["docs/evidence/baton/**"],
            inventory=inventory,
        )
        self.assertEqual(result["files_outside_managed_write_set"], ["AGENTS.md"])
        self.assertFalse(result["in_scope"])

    def test_invalid_managed_entry_raises_before_match(self) -> None:
        with self.assertRaises(BatonContractError):
            evaluate_scope(
                ["docs/**/*.md"],
                inventory={
                    "changed_files": [],
                    "staged_files": [],
                    "untracked_files": [],
                },
            )


if __name__ == "__main__":
    unittest.main()
