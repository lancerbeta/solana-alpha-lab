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


if __name__ == "__main__":
    unittest.main()
