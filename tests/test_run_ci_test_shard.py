from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("run_ci_test_shard", "scripts/run_ci_test_shard.py")
partition = load("ci_test_partition", "scripts/ci_test_partition.py")


class RunCiTestShardTests(unittest.TestCase):
    def test_invalid_plan_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.json"
            plan.write_text("{}", encoding="utf-8")
            code = runner.main(
                ["--index", "0", "--count", "3", "--plan", str(plan)]
            )
            self.assertEqual(code, 2)

    def test_index_count_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "plan.json"
            plan = partition.plan_shards(
                {"tests/test_a.py": 1.0},
                shard_count=2,
                source_profile_sha256="x",
            )
            partition.write_plan(plan_path, plan)
            code = runner.main(
                ["--index", "0", "--count", "3", "--plan", str(plan_path)]
            )
            self.assertEqual(code, 2)

    def test_test_failure_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_ok.py").write_text(
                textwrap.dedent(
                    """\
                    import unittest
                    class Ok(unittest.TestCase):
                        def test_pass(self):
                            self.assertTrue(True)
                    """
                ),
                encoding="utf-8",
            )
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
            plan = partition.plan_shards(
                {
                    "tests/test_ok.py": 1.0,
                    "tests/test_bad.py": 2.0,
                },
                shard_count=2,
                source_profile_sha256="x",
            )
            plan_path = root / "plan.json"
            partition.write_plan(plan_path, plan)
            codes = [
                runner.run_shard(
                    index=index,
                    count=2,
                    plan_path=plan_path,
                    root=root,
                )
                for index in (0, 1)
            ]
            self.assertIn(1, codes)

    def test_union_mismatch_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_union_a.py").write_text(
                textwrap.dedent(
                    """\
                    import unittest
                    class T(unittest.TestCase):
                        def test_ok(self):
                            self.assertTrue(True)
                    """
                ),
                encoding="utf-8",
            )
            (tests / "test_union_b.py").write_text(
                textwrap.dedent(
                    """\
                    import unittest
                    class T(unittest.TestCase):
                        def test_ok(self):
                            self.assertTrue(True)
                    """
                ),
                encoding="utf-8",
            )
            plan = partition.plan_shards(
                {
                    "tests/test_union_a.py": 1.0,
                    "tests/test_union_b.py": 1.0,
                },
                shard_count=1,
                source_profile_sha256="x",
            )
            plan_path = root / "plan.json"
            partition.write_plan(plan_path, plan)
            original = runner.partition.select_modules_for_shard

            def incomplete(current_modules, *, plan, index, count):
                selected = original(
                    current_modules, plan=plan, index=index, count=count
                )
                # Keep shard non-empty but omit one inventory module from the union.
                return selected[:1]

            runner.partition.select_modules_for_shard = incomplete  # type: ignore[assignment]
            try:
                with self.assertRaises(runner.ShardError) as ctx:
                    runner.run_shard(
                        index=0,
                        count=1,
                        plan_path=plan_path,
                        root=root,
                    )
                self.assertIn("SHARD_UNION_MISMATCH", str(ctx.exception))
            finally:
                runner.partition.select_modules_for_shard = original  # type: ignore[assignment]

    def test_ensure_repo_import_path_puts_root_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other = str((root / "other").resolve())
            root_s = str(root.resolve())
            saved_path = list(sys.path)
            try:
                sys.path[:] = [other, root_s, other]
                runner.ensure_repo_import_path(root)
                self.assertEqual(sys.path[0], root_s)
                self.assertEqual(sys.path.count(root_s), 1)
            finally:
                # This test shares a process with later shard modules in CI.
                sys.path[:] = saved_path

    def test_case_count_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_a.py").write_text(
                textwrap.dedent(
                    """\
                    import unittest
                    class T(unittest.TestCase):
                        def test_ok(self):
                            self.assertTrue(True)
                    """
                ),
                encoding="utf-8",
            )
            plan = partition.plan_shards(
                {"tests/test_a.py": 1.0},
                shard_count=1,
                source_profile_sha256="x",
            )
            plan_path = root / "plan.json"
            partition.write_plan(plan_path, plan)
            real_count = runner.profiler.count_cases

            def skewed(suite: unittest.TestSuite) -> int:
                # First call is discover canonical; inflate it so union load diverges.
                if not getattr(skewed, "_inflated", False):
                    skewed._inflated = True  # type: ignore[attr-defined]
                    return real_count(suite) + 7
                return real_count(suite)

            original = runner.profiler.count_cases
            runner.profiler.count_cases = skewed  # type: ignore[assignment]
            try:
                with self.assertRaises(runner.ShardError) as ctx:
                    runner.run_shard(
                        index=0,
                        count=1,
                        plan_path=plan_path,
                        root=root,
                    )
                self.assertIn("SHARD_CASE_COUNT_MISMATCH", str(ctx.exception))
            finally:
                runner.profiler.count_cases = original  # type: ignore[assignment]

    def test_unexpected_success_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_xfail_pass.py").write_text(
                textwrap.dedent(
                    """\
                    import unittest
                    class X(unittest.TestCase):
                        @unittest.expectedFailure
                        def test_should_fail_but_passes(self):
                            self.assertTrue(True)
                    """
                ),
                encoding="utf-8",
            )
            plan = partition.plan_shards(
                {"tests/test_xfail_pass.py": 1.0},
                shard_count=1,
                source_profile_sha256="x",
            )
            plan_path = root / "plan.json"
            partition.write_plan(plan_path, plan)
            code = runner.run_shard(
                index=0,
                count=1,
                plan_path=plan_path,
                root=root,
            )
            self.assertEqual(code, 1)


    def test_stale_profile_warning_threshold_and_non_blocking(self) -> None:
        plan = partition.plan_shards(
            {f"tests/test_old_{index}.py": 1.0 for index in range(4)},
            shard_count=4,
            source_profile_sha256="x",
        )
        current_fresh = [f"tests/test_old_{index}.py" for index in range(4)]
        self.assertIsNone(runner.stale_profile_warning(current_fresh, plan))
        current_stale_fraction = current_fresh + ["tests/test_new.py"]
        self.assertEqual(
            runner.stale_profile_warning(current_stale_fraction, plan),
            runner.STALE_PROFILE_WARNING,
        )
        current_stale_count = current_fresh + [
            f"tests/test_new_{index}.py" for index in range(8)
        ]
        self.assertEqual(
            runner.stale_profile_warning(current_stale_count, plan),
            runner.STALE_PROFILE_WARNING,
        )

    def test_stale_warning_prints_once_from_shard_zero_and_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            for name in ("test_stale_warn_ok.py", "test_stale_warn_extra.py"):
                (tests / name).write_text(
                    textwrap.dedent(
                        """\
                        import unittest
                        class T(unittest.TestCase):
                            def test_ok(self):
                                self.assertTrue(True)
                        """
                    ),
                    encoding="utf-8",
                )
            plan = partition.plan_shards(
                {"tests/test_stale_warn_ok.py": 1.0},
                shard_count=1,
                source_profile_sha256="x",
            )
            plan_path = root / "plan.json"
            partition.write_plan(plan_path, plan)
            capture = io.StringIO()
            tests_dir = str(tests.resolve())
            try:
                with contextlib.redirect_stdout(capture):
                    code = runner.run_shard(
                        index=0,
                        count=1,
                        plan_path=plan_path,
                        root=root,
                    )
            finally:
                while tests_dir in sys.path:
                    sys.path.remove(tests_dir)
                for name in ("test_stale_warn_ok", "test_stale_warn_extra"):
                    sys.modules.pop(name, None)
            self.assertEqual(code, 0)
            self.assertIn(runner.STALE_PROFILE_WARNING, capture.getvalue())
            self.assertEqual(
                capture.getvalue().count(runner.STALE_PROFILE_WARNING),
                1,
            )


if __name__ == "__main__":
    unittest.main()
