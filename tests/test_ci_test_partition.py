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

    def test_subtract_reserved_modules_removes_exact_declared_modules(self) -> None:
        modules = {
            "tests/test_a.py": 10.0,
            "tests/test_b.py": 20.0,
            "tests/test_c.py": 30.0,
        }
        result = partition.subtract_reserved_modules(
            modules,
            ["tests/test_b.py"],
        )
        self.assertEqual(
            result,
            {"tests/test_a.py": 10.0, "tests/test_c.py": 30.0},
        )

    def test_subtract_reserved_modules_fails_when_profile_missing_entry(self) -> None:
        with self.assertRaises(partition.PartitionError):
            partition.subtract_reserved_modules(
                {"tests/test_a.py": 1.0},
                ["tests/test_missing.py"],
            )

    def test_committed_plan_covers_current_inventory_once(self) -> None:
        plan = partition.load_plan(ROOT / "configs/ci_test_shards_v1.json")
        current = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "tests").glob("test_*.py")
            if path.is_file()
        )
        union, duplicates = partition.union_and_duplicates(plan)
        self.assertEqual(duplicates, set())
        # With execution reservation, ordinary plan may omit reserved modules.
        # Current modules must still map exactly once across general selection.
        reserved = set(
            __import__("json").loads(
                (ROOT / "configs/execution_domain_v1.json").read_text(encoding="utf-8")
            )["required_fast_test_modules"]
        )
        current_general = [path for path in current if path not in reserved]
        covered: list[str] = []
        for index in range(plan["shard_count"]):
            covered.extend(
                partition.select_modules_for_shard(
                    current_general,
                    plan=plan,
                    index=index,
                    count=plan["shard_count"],
                )
            )
        self.assertEqual(sorted(covered), current_general)
        self.assertEqual(len(covered), len(set(covered)))
        self.assertFalse(set(covered) & reserved)
        self.assertEqual(set(covered) | reserved, set(current))

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

    def _cover(
        self, current: list[str], plan: dict
    ) -> list[list[str]]:
        count = plan["shard_count"]
        return [
            partition.select_modules_for_shard(
                current, plan=plan, index=index, count=count
            )
            for index in range(count)
        ]

    def test_ad1_four_unknown_modules_do_not_all_land_on_one_shard(self) -> None:
        plan = partition.plan_shards(
            {f"tests/test_old_{index}.py": 50.0 for index in range(8)},
            shard_count=4,
            source_profile_sha256="x",
        )
        current = [f"tests/test_old_{index}.py" for index in range(8)] + [
            "tests/test_new_a.py",
            "tests/test_new_b.py",
            "tests/test_new_c.py",
            "tests/test_new_d.py",
        ]
        shards = self._cover(current, plan)
        new_counts = [
            sum(1 for path in shard if path.startswith("tests/test_new_"))
            for shard in shards
        ]
        self.assertNotEqual(max(new_counts), 4)
        self.assertEqual(sorted(new_counts), [1, 1, 1, 1])

    def test_ad2_repeated_unplanned_assignment_is_identical(self) -> None:
        plan = partition.plan_shards(
            {"tests/test_old.py": 5.0},
            shard_count=4,
            source_profile_sha256="x",
        )
        current = [
            "tests/test_old.py",
            "tests/test_new_a.py",
            "tests/test_new_b.py",
        ]
        first = partition.assign_unplanned_modules(current, plan, 4)
        second = partition.assign_unplanned_modules(current, plan, 4)
        self.assertEqual(first, second)

    def test_ad3_planned_modules_stay_on_committed_shards(self) -> None:
        plan = partition.plan_shards(
            {
                "tests/test_a.py": 40.0,
                "tests/test_b.py": 10.0,
                "tests/test_c.py": 10.0,
                "tests/test_d.py": 10.0,
            },
            shard_count=4,
            source_profile_sha256="x",
        )
        committed = {
            path: index
            for index, shard in enumerate(plan["shards"])
            for path in shard
        }
        current = list(committed) + ["tests/test_new.py"]
        shards = self._cover(current, plan)
        for index, shard in enumerate(shards):
            for path in shard:
                if path in committed:
                    self.assertEqual(committed[path], index)

    def test_ad4_and_ad5_current_modules_selected_exactly_once(self) -> None:
        plan = partition.plan_shards(
            {f"tests/test_old_{index}.py": float(index + 1) for index in range(6)},
            shard_count=4,
            source_profile_sha256="x",
        )
        current = [f"tests/test_old_{index}.py" for index in range(6)] + [
            "tests/test_new_a.py",
            "tests/test_new_b.py",
        ]
        covered = [path for shard in self._cover(current, plan) for path in shard]
        self.assertEqual(sorted(covered), sorted(current))
        self.assertEqual(len(covered), len(set(covered)))

    def test_ad6_first_unplanned_module_prefers_lightest_shard(self) -> None:
        plan = {
            "schema": "smial.ci-test-shards.v1",
            "shard_count": 3,
            "source_profile_sha256": "x",
            "projected_seconds": [100.0, 10.0, 50.0],
            "projected_max_seconds": 100.0,
            "shards": [
                ["tests/test_a.py"],
                ["tests/test_b.py"],
                ["tests/test_c.py"],
            ],
        }
        current = [
            "tests/test_a.py",
            "tests/test_b.py",
            "tests/test_c.py",
            "tests/test_new.py",
        ]
        assignment = partition.assign_unplanned_modules(current, plan, 3)
        self.assertEqual(assignment["tests/test_new.py"], 1)

    def test_ad7_tie_breaks_by_lowest_shard_index(self) -> None:
        plan = {
            "schema": "smial.ci-test-shards.v1",
            "shard_count": 3,
            "source_profile_sha256": "x",
            "projected_seconds": [10.0, 10.0, 10.0],
            "projected_max_seconds": 10.0,
            "shards": [
                ["tests/test_a.py"],
                ["tests/test_b.py"],
                ["tests/test_c.py"],
            ],
        }
        current = [
            "tests/test_a.py",
            "tests/test_b.py",
            "tests/test_c.py",
            "tests/test_new.py",
        ]
        assignment = partition.assign_unplanned_modules(current, plan, 3)
        self.assertEqual(assignment["tests/test_new.py"], 0)

    def test_ad8_estimated_load_updates_after_each_assignment(self) -> None:
        plan = {
            "schema": "smial.ci-test-shards.v1",
            "shard_count": 3,
            "source_profile_sha256": "x",
            "projected_seconds": [5.0, 6.0, 100.0],
            "projected_max_seconds": 100.0,
            "shards": [
                ["tests/test_a.py"],
                ["tests/test_b.py"],
                ["tests/test_c.py"],
            ],
        }
        current = [
            "tests/test_a.py",
            "tests/test_b.py",
            "tests/test_c.py",
            "tests/test_z_a.py",
            "tests/test_z_b.py",
        ]
        assignment = partition.assign_unplanned_modules(current, plan, 3)
        self.assertEqual(assignment["tests/test_z_a.py"], 0)
        self.assertEqual(assignment["tests/test_z_b.py"], 1)

    def test_ad9_stale_removed_entry_cannot_drop_or_duplicate_current(self) -> None:
        plan = partition.plan_shards(
            {"tests/test_alive.py": 1.0, "tests/test_gone.py": 50.0},
            shard_count=2,
            source_profile_sha256="x",
        )
        current = ["tests/test_alive.py", "tests/test_brand_new.py"]
        covered = [path for shard in self._cover(current, plan) for path in shard]
        self.assertEqual(sorted(covered), sorted(current))
        self.assertEqual(len(covered), len(set(covered)))
        self.assertNotIn("tests/test_gone.py", covered)


if __name__ == "__main__":
    unittest.main()
