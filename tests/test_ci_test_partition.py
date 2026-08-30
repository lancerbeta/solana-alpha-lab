from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_partition():
    spec = importlib.util.spec_from_file_location(
        "ci_test_partition",
        ROOT / "scripts/ci_test_partition.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


partition = load_partition()


class CiTestPartitionTests(unittest.TestCase):
    def test_longest_processing_time_is_deterministic(self) -> None:
        modules = {
            "tests/test_a.py": 100.0,
            "tests/test_b.py": 90.0,
            "tests/test_c.py": 80.0,
            "tests/test_d.py": 10.0,
            "tests/test_e.py": 10.0,
        }
        first = partition.plan_shards(
            modules, shard_count=3, source_profile_sha256="abc"
        )
        second = partition.plan_shards(
            modules, shard_count=3, source_profile_sha256="abc"
        )
        self.assertEqual(first, second)
        union, duplicates = partition.union_and_duplicates(first)
        self.assertEqual(duplicates, set())
        self.assertEqual(union, set(modules))
        self.assertEqual(sum(len(s) for s in first["shards"]), len(modules))

    def test_same_module_cannot_appear_in_two_shards(self) -> None:
        plan = partition.plan_shards(
            {f"tests/test_{i}.py": float(i) for i in range(20)},
            shard_count=4,
            source_profile_sha256="x",
        )
        _, duplicates = partition.union_and_duplicates(plan)
        self.assertEqual(duplicates, set())

    def test_load_plan_rejects_duplicate_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            bad = {
                "schema": "smial.ci-test-shards.v1",
                "shard_count": 2,
                "source_profile_sha256": "x",
                "projected_seconds": [1.0, 1.0],
                "projected_max_seconds": 1.0,
                "shards": [
                    ["tests/test_a.py", "tests/test_dup.py"],
                    ["tests/test_dup.py"],
                ],
            }
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(partition.PartitionError):
                partition.load_plan(path)

    def test_committed_plan_covers_current_inventory_once(self) -> None:
        plan = partition.load_plan(ROOT / "configs/ci_test_shards_v1.json")
        current = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "tests").glob("test_*.py")
            if path.is_file()
        )
        union, duplicates = partition.union_and_duplicates(plan)
        self.assertEqual(duplicates, set())
        # Stale plan paths are allowed as warnings; current modules must all map.
        covered: list[str] = []
        for index in range(plan["shard_count"]):
            covered.extend(
                partition.select_modules_for_shard(
                    current,
                    plan=plan,
                    index=index,
                    count=plan["shard_count"],
                )
            )
        self.assertEqual(sorted(covered), current)
        self.assertEqual(len(covered), len(set(covered)))

    def test_new_module_absent_from_plan_is_assigned(self) -> None:
        plan = partition.plan_shards(
            {"tests/test_old.py": 5.0},
            shard_count=3,
            source_profile_sha256="x",
        )
        current = ["tests/test_old.py", "tests/test_new.py"]
        assigned = []
        for index in range(3):
            selected = partition.select_modules_for_shard(
                current, plan=plan, index=index, count=3
            )
            assigned.extend(selected)
        self.assertEqual(sorted(assigned), sorted(current))
        self.assertEqual(len(assigned), 2)

    def test_stale_plan_entry_cannot_remove_current_module(self) -> None:
        plan = partition.plan_shards(
            {"tests/test_alive.py": 1.0, "tests/test_gone.py": 50.0},
            shard_count=2,
            source_profile_sha256="x",
        )
        current = ["tests/test_alive.py", "tests/test_brand_new.py"]
        selected = []
        for index in range(2):
            selected.extend(
                partition.select_modules_for_shard(
                    current, plan=plan, index=index, count=2
                )
            )
        self.assertIn("tests/test_alive.py", selected)
        self.assertIn("tests/test_brand_new.py", selected)
        self.assertNotIn("tests/test_gone.py", selected)

    def test_choose_shard_count_prefers_three_when_possible(self) -> None:
        modules = {f"tests/test_{i}.py": 100.0 for i in range(9)}
        self.assertEqual(partition.choose_shard_count(modules), 3)
        heavy = {f"tests/test_{i}.py": 200.0 for i in range(8)}
        self.assertEqual(partition.choose_shard_count(heavy), 4)


if __name__ == "__main__":
    unittest.main()
