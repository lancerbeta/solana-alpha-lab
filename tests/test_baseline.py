from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_baseline.py"

spec = importlib.util.spec_from_file_location(
    "validate_baseline",
    MODULE_PATH,
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CommitStatePolicyTests(unittest.TestCase):
    def expected(self) -> set[str]:
        return set(module.EXPECTED_FILES)

    def test_commit_ready_staged_is_accepted(self) -> None:
        expected = self.expected()
        state = module.classify_repository_state(
            head_exists=False,
            commit_count=0,
            tracked=expected,
            staged=expected,
            untracked=set(),
            unstaged=set(),
        )
        self.assertEqual(state, "COMMIT_READY_STAGED")

    def test_committed_baseline_is_accepted(self) -> None:
        expected = self.expected()
        state = module.classify_repository_state(
            head_exists=True,
            commit_count=1,
            tracked=expected,
            staged=set(),
            untracked=set(),
            unstaged=set(),
        )
        self.assertEqual(state, "COMMITTED_BASELINE")

    def test_second_commit_is_rejected(self) -> None:
        expected = self.expected()
        state = module.classify_repository_state(
            head_exists=True,
            commit_count=2,
            tracked=expected,
            staged=set(),
            untracked=set(),
            unstaged=set(),
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_partial_staging_is_rejected(self) -> None:
        expected = self.expected()
        one = next(iter(expected))
        state = module.classify_repository_state(
            head_exists=False,
            commit_count=0,
            tracked=expected,
            staged={one},
            untracked=set(),
            unstaged=set(),
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_unstaged_drift_is_rejected(self) -> None:
        expected = self.expected()
        state = module.classify_repository_state(
            head_exists=False,
            commit_count=0,
            tracked=expected,
            staged=expected,
            untracked=set(),
            unstaged={"README.md"},
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_extra_file_is_rejected(self) -> None:
        expected = self.expected()
        state = module.classify_repository_state(
            head_exists=False,
            commit_count=0,
            tracked=expected | {"unexpected.txt"},
            staged=expected | {"unexpected.txt"},
            untracked=set(),
            unstaged=set(),
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_index_record_parser(self) -> None:
        raw = (
            b"100644 "
            + (b"a" * 40)
            + b" 0\tREADME.md\0"
        )
        parsed = module.parse_index_entries(raw)
        self.assertEqual(
            parsed["README.md"],
            ("100644", "a" * 40),
        )

    def test_tree_record_parser(self) -> None:
        raw = (
            b"100755 blob "
            + (b"b" * 40)
            + b"\t.githooks/pre-commit\0"
        )
        parsed = module.parse_tree_entries(raw)
        self.assertEqual(
            parsed[".githooks/pre-commit"],
            ("100755", "b" * 40),
        )

    def test_empty_env_values_are_allowed(self) -> None:
        self.assertEqual(
            module.validate_env_example("API_KEY=\nOTHER_VALUE=\n"),
            [],
        )

    def test_non_empty_env_value_is_rejected(self) -> None:
        candidate = (
            ("API" + "_KEY")
            + "="
            + ("not-" + "a-real-" + "secret")
            + "\n"
        )
        findings = module.validate_env_example(candidate)
        self.assertIn("line_1_non_empty_value", findings)

    def test_windows_user_path_is_rejected(self) -> None:
        separator = chr(92)
        candidate = (
            "C:"
            + separator
            + "Users"
            + separator
            + "Example"
            + separator
            + "project"
        )
        self.assertTrue(
            module.contains_forbidden_absolute_user_path(candidate)
        )

    def test_unix_home_path_is_rejected(self) -> None:
        slash = chr(47)
        candidate = (
            slash
            + "home"
            + slash
            + "example"
            + slash
            + "project"
        )
        self.assertTrue(
            module.contains_forbidden_absolute_user_path(candidate)
        )

    def test_logical_alias_is_allowed(self) -> None:
        self.assertFalse(
            module.contains_forbidden_absolute_user_path(
                "USERPROFILE_PROJECTS/solana-alpha-lab"
            )
        )

    def test_pre_commit_uses_process_scoped_bypass(self) -> None:
        hook = (
            ROOT / ".githooks/pre-commit"
        ).read_text(encoding="utf-8")
        self.assertIn("-ExecutionPolicy Bypass", hook)

    def test_runtime_constants(self) -> None:
        self.assertEqual(module.EXPECTED_PYTHON, (3, 13, 14))
        self.assertEqual(module.EXPECTED_POWERSHELL, "7.6.3")
        self.assertEqual(
            module.EXPECTED_REQUIRES_PYTHON,
            ">=3.13,<3.14",
        )
        self.assertEqual(
            module.RECOMMENDED_COMMIT_MESSAGE,
            "chore: establish local repository baseline",
        )


if __name__ == "__main__":
    unittest.main()
