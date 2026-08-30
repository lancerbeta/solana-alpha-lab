from __future__ import annotations

import importlib.util
import json
import os
import subprocess
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


if __name__ == "__main__":
    unittest.main()
