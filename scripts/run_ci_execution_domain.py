#!/usr/bin/env python3
"""Run the reserved fast execution-domain CI test lane exactly once."""

from __future__ import annotations

import argparse
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import profile_test_wall_clock as profiler  # noqa: E402
import validate_execution_domain as execution_domain  # noqa: E402


class ExecutionDomainRunError(ValueError):
    """Fail-closed execution-domain runner error."""


def load_suite_for_paths(paths: list[str], *, root: Path) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    for relative in paths:
        module_path = root / relative
        if not module_path.is_file():
            raise ExecutionDomainRunError(f"MODULE_MISSING:{relative}")
        suite.addTests(profiler.load_module_suite(module_path, root=root))
    return suite


def ensure_repo_import_path(root: Path = ROOT) -> None:
    root_s = str(root.resolve())
    if root_s in sys.path:
        sys.path.remove(root_s)
    sys.path.insert(0, root_s)


def run_execution_domain(*, manifest_path: Path, root: Path = ROOT) -> int:
    ensure_repo_import_path(root)
    manifest = execution_domain.load_execution_domain(manifest_path)
    execution_domain.validate_execution_domain(manifest, root=root)
    reserved = [
        execution_domain.posix(path)
        for path in manifest["required_fast_test_modules"]
    ]
    if len(reserved) != len(set(reserved)):
        raise ExecutionDomainRunError("RESERVED_MODULES_DUPLICATE")

    current = {
        profiler.posix_relative(path, root)
        for path in profiler.discover_module_paths(root / "tests")
    }
    missing = sorted(set(reserved) - current)
    if missing:
        raise ExecutionDomainRunError(
            "RESERVED_MODULE_NOT_IN_DISCOVERY:" + ",".join(missing[:20])
        )

    canonical_count = profiler.count_cases(
        unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    )
    suite = load_suite_for_paths(sorted(reserved), root=root)
    case_count = profiler.count_cases(suite)
    print(f"selected_modules={len(reserved)} selected_cases={case_count}")
    print(f"canonical_case_count={canonical_count}")
    runner = unittest.TextTestRunner(verbosity=1)
    started = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - started
    unexpected = list(getattr(result, "unexpectedSuccesses", []) or [])
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
        return 1
    print("EXECUTION_DOMAIN_FAST_TESTS: PASS")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "configs/execution_domain_v1.json",
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_execution_domain(manifest_path=args.manifest, root=args.root)
    except (ExecutionDomainRunError, execution_domain.ExecutionDomainError) as exc:
        print(f"EXECUTION_DOMAIN_RUN_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
