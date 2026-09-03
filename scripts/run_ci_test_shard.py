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


STALE_UNPLANNED_COUNT = 8
STALE_UNPLANNED_FRACTION = 0.05
STALE_PROFILE_WARNING = "CI_SHARD_PROFILE_STALE_REBALANCE_RECOMMENDED"


class ShardError(ValueError):
    """Fail-closed shard runner error."""


def stale_profile_warning(
    current_modules: list[str],
    plan: dict,
) -> str | None:
    """Return an informational stale-plan hint, or None.

    Never changes coverage, assignment, or process exit semantics.
    """
    planned = {
        partition.posix(path)
        for shard in plan.get("shards") or []
        for path in shard
    }
    current = [partition.posix(path) for path in current_modules]
    unplanned_count = sum(1 for path in current if path not in planned)
    total = len(current)
    fraction = (unplanned_count / total) if total else 0.0
    if unplanned_count >= STALE_UNPLANNED_COUNT or fraction >= STALE_UNPLANNED_FRACTION:
        return STALE_PROFILE_WARNING
    return None


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


def ensure_repo_import_path(root: Path = ROOT) -> None:
    """Match `python -m unittest discover -s tests` launched from repo root.

    Script invocation (`python scripts/run_ci_test_shard.py`) puts `scripts/` on
    ``sys.path[0]`` instead of the repo root; without the root, discover can
    collapse whole modules into a single import-failure case while
    ``loadTestsFromModule`` (which inserts root) still expands them.
    """
    root_s = str(root.resolve())
    if root_s in sys.path:
        sys.path.remove(root_s)
    sys.path.insert(0, root_s)


def load_reserved_modules(manifest_path: Path, *, root: Path) -> set[str]:
    import validate_execution_domain as execution_domain

    manifest = execution_domain.load_execution_domain(manifest_path)
    if manifest.get("schema") != execution_domain.MANIFEST_SCHEMA:
        raise ShardError("RESERVED_MANIFEST_SCHEMA_INVALID")
    if manifest.get("domain_id") != execution_domain.EXPECTED_DOMAIN_ID:
        raise ShardError("RESERVED_MANIFEST_DOMAIN_INVALID")
    reserved_list = [
        partition.posix(path)
        for path in (manifest.get("required_fast_test_modules") or [])
    ]
    if not reserved_list:
        raise ShardError("RESERVED_MODULES_EMPTY")
    if len(reserved_list) != len(set(reserved_list)):
        raise ShardError("RESERVED_MODULES_DUPLICATE")
    return set(reserved_list)


def run_shard(
    *,
    index: int,
    count: int,
    plan_path: Path,
    reserved_manifest_path: Path | None = None,
    root: Path = ROOT,
) -> int:
    ensure_repo_import_path(root)
    plan = partition.load_plan(plan_path)
    current = [
        profiler.posix_relative(path, root)
        for path in profiler.discover_module_paths(root / "tests")
    ]
    full_hash = inventory_hash(current)
    canonical_count = profiler.count_cases(
        unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    )
    reserved: set[str] = set()
    if reserved_manifest_path is not None:
        reserved = load_reserved_modules(reserved_manifest_path, root=root)
        if len(reserved) != len(set(reserved)):
            raise ShardError("RESERVED_MODULES_DUPLICATE")
        overlap = sorted(reserved & set(current))
        if len(overlap) != len(reserved):
            missing_reserved = sorted(reserved - set(current))
            raise ShardError(
                "RESERVED_MODULE_NOT_IN_DISCOVERY:"
                + ",".join(missing_reserved[:20])
            )
    current_general = [path for path in current if path not in reserved]
    selected = partition.select_modules_for_shard(
        current_general,
        plan=plan,
        index=index,
        count=count,
    )
    if not selected:
        raise ShardError("EMPTY_SHARD_REFUSED")
    # Prove current inventory is fully covered exactly once across lanes.
    general_covered: list[str] = []
    for shard_index in range(count):
        general_covered.extend(
            partition.select_modules_for_shard(
                current_general,
                plan=plan,
                index=shard_index,
                count=count,
            )
        )
    execution_covered = sorted(reserved)
    if len(general_covered) != len(set(general_covered)):
        raise ShardError("GENERAL_SHARD_UNION_HAS_DUPLICATES")
    if execution_covered and len(execution_covered) != len(set(execution_covered)):
        raise ShardError("EXECUTION_RESERVED_HAS_DUPLICATES")
    if reserved and set(general_covered) & reserved:
        raise ShardError("EXECUTION_GENERAL_OVERLAP")
    covered = sorted(set(general_covered) | reserved)
    if set(covered) != set(current):
        missing = sorted(set(current) - set(covered))
        extra = sorted(set(covered) - set(current))
        raise ShardError(
            "SHARD_UNION_MISMATCH:"
            f"missing={len(missing)}:extra={len(extra)}"
        )
    # Live equivalence: module-path union is not enough — the cases loaded from
    # those modules must match unittest discover on the same tests root.
    loaded_union_count = profiler.count_cases(
        load_suite_for_paths(covered, root=root)
    )
    if loaded_union_count != canonical_count:
        raise ShardError(
            "SHARD_CASE_COUNT_MISMATCH:"
            f"loaded_union={loaded_union_count}:discover={canonical_count}"
        )
    if index == 0:
        warning = stale_profile_warning(current_general, plan)
        if warning is not None:
            print(warning)
    if index == 0 and reserved_manifest_path is not None:
        print(f"execution_reserved_modules={len(reserved)}")
        print(f"general_modules={len(current_general)}")
    suite = load_suite_for_paths(selected, root=root)
    case_count = profiler.count_cases(suite)
    if case_count < 1:
        raise ShardError("SHARD_ZERO_CASES")
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=1)
    started = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - started
    unexpected = list(getattr(result, "unexpectedSuccesses", []) or [])
    print(f"inventory_sha256={full_hash}")
    print(f"canonical_case_count={canonical_count}")
    print(f"loaded_union_case_count={loaded_union_count}")
    print(f"shard_index={index} shard_count={count}")
    print(f"selected_modules={len(selected)} selected_cases={case_count}")
    print(
        f"failures={len(result.failures)} errors={len(result.errors)} "
        f"skipped={len(result.skipped)} unexpected_successes={len(unexpected)} "
        f"elapsed_seconds={elapsed:.3f}"
    )
    if (
        (not result.wasSuccessful())
        or result.failures
        or result.errors
        or unexpected
    ):
        print(stream.getvalue())
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, type=int)
    parser.add_argument("--count", required=True, type=int)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--reserved-manifest", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_shard(
            index=args.index,
            count=args.count,
            plan_path=args.plan,
            reserved_manifest_path=args.reserved_manifest,
        )
    except (ShardError, partition.PartitionError) as exc:
        print(f"SHARD_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
