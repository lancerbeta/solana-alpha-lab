from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def load_profiler():
    spec = importlib.util.spec_from_file_location(
        "profile_test_wall_clock",
        ROOT / "scripts/profile_test_wall_clock.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profiler = load_profiler()


class ProfileTestWallClockTests(unittest.TestCase):
    def _write_tree(self, root: Path) -> Path:
        tests = root / "tests"
        tests.mkdir(parents=True)
        (root / "uv.lock").write_text("lock\n", encoding="utf-8")
        (tests / "test_alpha.py").write_text(
            textwrap.dedent(
                """\
                import time
                import unittest

                class Alpha(unittest.TestCase):
                    @classmethod
                    def setUpClass(cls):
                        time.sleep(0.05)
                        cls.marker = "prepared"

                    def test_one(self):
                        self.assertEqual(self.marker, "prepared")

                    def test_two(self):
                        self.assertEqual(self.marker, "prepared")
                """
            ),
            encoding="utf-8",
        )
        (tests / "test_beta.py").write_text(
            textwrap.dedent(
                """\
                import unittest

                class Beta(unittest.TestCase):
                    def test_fast(self):
                        self.assertTrue(True)

                    @unittest.skip("fixture")
                    def test_skipped(self):
                        self.fail("should skip")
                """
            ),
            encoding="utf-8",
        )
        (tests / "test_gamma.py").write_text(
            textwrap.dedent(
                """\
                import unittest

                class Gamma(unittest.TestCase):
                    def test_other(self):
                        self.assertEqual(1, 1)
                """
            ),
            encoding="utf-8",
        )
        return tests

    def test_inventory_order_and_hash_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = self._write_tree(root)
            first = profiler.discover_module_paths(tests)
            second = profiler.discover_module_paths(tests)
            self.assertEqual(
                [profiler.posix_relative(p, root) for p in first],
                [
                    "tests/test_alpha.py",
                    "tests/test_beta.py",
                    "tests/test_gamma.py",
                ],
            )
            self.assertEqual(
                [profiler.posix_relative(p, root) for p in first],
                [profiler.posix_relative(p, root) for p in second],
            )
            self.assertEqual(
                profiler.inventory_repo_sha256(first, root=root),
                profiler.inventory_repo_sha256(second, root=root),
            )

    def test_fixture_time_is_attributed_and_modules_run_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = self._write_tree(root)
            # Initialize a fake git HEAD for receipt fields.
            import subprocess

            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", "seed"],
                cwd=root,
                check=True,
                capture_output=True,
                env={
                    **dict(**{k: v for k, v in __import__("os").environ.items()}),
                    "GIT_AUTHOR_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@example.com",
                    "GIT_COMMITTER_NAME": "t",
                    "GIT_COMMITTER_EMAIL": "t@example.com",
                },
            )
            receipt = profiler.profile_modules(root=root, tests_root=tests)
            by_path = {row["path"]: row for row in receipt["modules"]}
            self.assertEqual(receipt["module_count"], 3)
            self.assertEqual(receipt["test_case_count"], 5)
            self.assertEqual(receipt["skipped_count"], 1)
            self.assertGreaterEqual(by_path["tests/test_alpha.py"]["seconds"], 0.04)
            self.assertEqual(by_path["tests/test_alpha.py"]["tests"], 2)
            self.assertEqual(by_path["tests/test_beta.py"]["skipped"], 1)
            self.assertLess(by_path["tests/test_beta.py"]["seconds"], by_path["tests/test_alpha.py"]["seconds"])
            self.assertNotIn(str(root.resolve()), json.dumps(receipt))

    def test_output_path_cannot_overwrite_truth_artifacts(self) -> None:
        with self.assertRaises(profiler.ProfileError):
            profiler.assert_safe_output_path(ROOT / "docs/evidence/x.json")
        with self.assertRaises(profiler.ProfileError):
            profiler.assert_safe_output_path(ROOT / "scripts/out.json")
        allowed = profiler.assert_safe_output_path(
            ROOT / "local/ci_headroom/profile.json"
        )
        self.assertTrue(str(allowed).endswith("profile.json"))

    def test_failure_is_nonzero_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (root / "uv.lock").write_text("lock\n", encoding="utf-8")
            (tests / "test_bad.py").write_text(
                textwrap.dedent(
                    """\
                    import unittest
                    class Bad(unittest.TestCase):
                        def test_fail(self):
                            self.fail("boom")
                    """
                ),
                encoding="utf-8",
            )
            import subprocess
            import os

            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", "seed"],
                cwd=root,
                check=True,
                capture_output=True,
                env={
                    **os.environ,
                    "GIT_AUTHOR_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@example.com",
                    "GIT_COMMITTER_NAME": "t",
                    "GIT_COMMITTER_EMAIL": "t@example.com",
                },
            )
            with self.assertRaises(profiler.ProfileError):
                profiler.profile_modules(root=root, tests_root=tests)


if __name__ == "__main__":
    unittest.main()
