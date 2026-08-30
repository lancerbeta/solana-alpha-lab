from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
