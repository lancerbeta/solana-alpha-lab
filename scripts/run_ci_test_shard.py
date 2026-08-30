#!/usr/bin/env python3
"""Run one isolated CI test shard against the current inventory."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ci_test_partition as partition  # noqa: E402
import profile_test_wall_clock as profiler  # noqa: E402


class ShardError(ValueError):
    """Fail-closed shard runner error."""


def load_suite_for_paths(paths: list[str], *, root: Path = ROOT) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    for relative in paths:
        module_path = root / relative
        if not module_path.is_file():
            raise ShardError(f"MODULE_MISSING:{relative}")
        suite.addTests(profiler.load_module_suite(module_path, root=root))
    return suite


def inventory_hash(paths: list[str]) -> str:
    joined = "\n".join(paths)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def run_shard(
    *,
    index: int,
    count: int,
    plan_path: Path,
    root: Path = ROOT,
) -> int:
    plan = partition.load_plan(plan_path)
    current = [
        profiler.posix_relative(path, root)
        for path in profiler.discover_module_paths(root / "tests")
    ]
    full_hash = inventory_hash(current)
    selected = partition.select_modules_for_shard(
        current,
        plan=plan,
        index=index,
        count=count,
    )
    if not selected:
        raise ShardError("EMPTY_SHARD_REFUSED")
    suite = load_suite_for_paths(selected, root=root)
    case_count = profiler.count_cases(suite)
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=1)
    started = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - started
    print(f"inventory_sha256={full_hash}")
    print(f"shard_index={index} shard_count={count}")
    print(f"selected_modules={len(selected)} selected_cases={case_count}")
    print(
        f"failures={len(result.failures)} errors={len(result.errors)} "
        f"skipped={len(result.skipped)} elapsed_seconds={elapsed:.3f}"
    )
    if result.failures or result.errors:
        print(stream.getvalue())
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, type=int)
    parser.add_argument("--count", required=True, type=int)
    parser.add_argument("--plan", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_shard(index=args.index, count=args.count, plan_path=args.plan)
    except (ShardError, partition.PartitionError) as exc:
        print(f"SHARD_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
