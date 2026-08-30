#!/usr/bin/env python3
"""Deterministic sequential per-module wall-clock profiler for CI headroom work.

Diagnostic only: does not replace unittest discover as canonical validation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = ROOT / "tests"
PATTERN = "test_*.py"


class ProfileError(ValueError):
    """Fail-closed profiler contract error."""

    def __init__(self, message: str, receipt: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.receipt = receipt


def posix_relative(path: Path, root: Path = ROOT) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def discover_module_paths(tests_root: Path = TESTS_ROOT) -> list[Path]:
    # Match `unittest discover -s tests -p test_*.py` inventory used by CI:
    # current repository keeps all modules flat under tests/.
    return sorted(
        (path for path in tests_root.glob(PATTERN) if path.is_file()),
        key=lambda path: path.name,
    )


def inventory_paths_sha256(module_paths: list[Path], *, tests_root: Path) -> str:
    joined = "\n".join(
        path.resolve().relative_to(tests_root.resolve()).as_posix()
        for path in module_paths
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def inventory_repo_sha256(module_paths: list[Path], root: Path = ROOT) -> str:
    joined = "\n".join(posix_relative(path, root) for path in module_paths)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def count_cases(suite: unittest.TestSuite | unittest.TestCase) -> int:
    if isinstance(suite, unittest.TestCase):
        return 1
    total = 0
    for item in suite:
        total += count_cases(item)
    return total


def load_module_suite(module_path: Path, *, root: Path = ROOT) -> unittest.TestSuite:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    tests_dir = str((root / "tests").resolve())
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    relative = posix_relative(module_path, root)
    # Prefer the same import name unittest discover uses so cross-module
    # fixtures like `import test_foo` resolve.
    module_name = module_path.stem
    if module_name in sys.modules:
        module = sys.modules[module_name]
    else:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ProfileError(f"MODULE_LOAD_FAILED:{relative}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return unittest.defaultTestLoader.loadTestsFromModule(module)


def canonical_discovery_count(tests_root: Path = TESTS_ROOT) -> int:
    suite = unittest.defaultTestLoader.discover(str(tests_root), pattern=PATTERN)
    return count_cases(suite)


def git_sha(ref: str = "HEAD", *, root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_safe_output_path(output: Path, root: Path = ROOT) -> Path:
    resolved_root = root.resolve()
    resolved = output if output.is_absolute() else (root / output)
    resolved = resolved.resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise ProfileError("OUTPUT_PATH_OUTSIDE_REPO")
    relative = resolved.relative_to(resolved_root).as_posix()
    if relative.startswith(("docs/", "catalog/", ".github/", "control/", "scripts/", "tests/")):
        raise ProfileError("OUTPUT_PATH_OVERWRITES_TRUTH_ARTIFACT")
    if not relative.startswith("local/"):
        raise ProfileError("OUTPUT_PATH_MUST_BE_UNDER_LOCAL")
    return resolved


def run_module(module_path: Path, *, root: Path = ROOT) -> dict[str, Any]:
    suite = load_module_suite(module_path, root=root)
    case_count = count_cases(suite)
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=0)
    started = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - started
    return {
        "path": posix_relative(module_path, root),
        "seconds": round(elapsed, 6),
        "tests": case_count,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }


def profile_modules(
    module_paths: list[Path] | None = None,
    *,
    root: Path = ROOT,
    tests_root: Path | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    tests_root = tests_root or (root / "tests")
    modules = (
        list(module_paths)
        if module_paths is not None
        else discover_module_paths(tests_root)
    )
    if progress:
        print(f"PROFILE_PROGRESS modules={len(modules)}", flush=True)
    inventory_hash = inventory_repo_sha256(modules, root=root)
    profiled_suites = []
    for index, path in enumerate(modules):
        if progress and index % 25 == 0:
            print(f"PROFILE_PROGRESS load_index={index} path={path.name}", flush=True)
        profiled_suites.append(load_module_suite(path, root=root))
    profiled_count = sum(count_cases(suite) for suite in profiled_suites)
    # Canonical discover counts from the same tests_root.
    if progress:
        print("PROFILE_PROGRESS reconcile_canonical", flush=True)
    canonical_count = count_cases(
        unittest.defaultTestLoader.discover(str(tests_root), pattern=PATTERN)
    )
    if profiled_count != canonical_count:
        raise ProfileError(
            f"INVENTORY_COUNT_MISMATCH:profiled={profiled_count}:canonical={canonical_count}"
        )
    if progress:
        print(
            f"PROFILE_PROGRESS reconciled cases={profiled_count} start_run",
            flush=True,
        )

    rows: list[dict[str, Any]] = []
    for index, (path, suite) in enumerate(zip(modules, profiled_suites, strict=True)):
        if progress:
            print(
                f"PROFILE_PROGRESS run_index={index} path={posix_relative(path, root)}",
                flush=True,
            )
        case_count = count_cases(suite)
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=0)
        started = time.perf_counter()
        result = runner.run(suite)
        elapsed = time.perf_counter() - started
        rows.append(
            {
                "path": posix_relative(path, root),
                "seconds": round(elapsed, 6),
                "tests": case_count,
                "failures": len(result.failures),
                "errors": len(result.errors),
                "skipped": len(result.skipped),
            }
        )

    failures = sum(row["failures"] + row["errors"] for row in rows)
    total_seconds = round(sum(row["seconds"] for row in rows), 6)
    ordered = sorted(rows, key=lambda row: (-row["seconds"], row["path"]))
    top_1 = ordered[0]["seconds"] if ordered else 0.0
    top_5 = sum(row["seconds"] for row in ordered[:5])
    top_20 = sum(row["seconds"] for row in ordered[:20])
    receipt = {
        "schema": "smial.profile-test-wall-clock.v1",
        "base_commit_sha": git_sha("HEAD", root=root),
        "head_commit_sha": git_sha("HEAD", root=root),
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "uv_lock_sha256": file_sha256(root / "uv.lock") if (root / "uv.lock").is_file() else None,
        "module_count": len(modules),
        "test_case_count": profiled_count,
        "skipped_count": sum(row["skipped"] for row in rows),
        "failure_count": failures,
        "canonical_module_inventory_sha256": inventory_hash,
        "profile_total_seconds": total_seconds,
        "top_1_share": round(top_1 / total_seconds, 6) if total_seconds else 0.0,
        "top_5_share": round(top_5 / total_seconds, 6) if total_seconds else 0.0,
        "top_20_share": round(top_20 / total_seconds, 6) if total_seconds else 0.0,
        "modules": rows,
        "top_20": ordered[:20],
    }
    _assert_receipt_privacy(receipt, root=root)
    if failures:
        raise ProfileError(f"PROFILE_TESTS_FAILED:{failures}", receipt=receipt)
    return receipt


def _assert_receipt_privacy(receipt: dict[str, Any], *, root: Path) -> None:
    blob = json.dumps(receipt, ensure_ascii=False)
    absolute = str(root.resolve())
    posix_abs = root.resolve().as_posix()
    if absolute in blob or posix_abs in blob:
        raise ProfileError("PROFILE_RECEIPT_CONTAINS_ABSOLUTE_PATH")


def format_top_table(receipt: dict[str, Any]) -> str:
    lines = [
        f"modules={receipt['module_count']} cases={receipt['test_case_count']} "
        f"total_s={receipt['profile_total_seconds']:.3f} "
        f"top1={receipt['top_1_share']:.4f} top5={receipt['top_5_share']:.4f}"
    ]
    lines.append(f"{'seconds':>10}  {'tests':>5}  path")
    for row in receipt["top_20"]:
        lines.append(f"{row['seconds']:10.3f}  {row['tests']:5d}  {row['path']}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--progress", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output: Path | None = None
    try:
        output = assert_safe_output_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        receipt = profile_modules(progress=args.progress)
    except ProfileError as exc:
        print(f"PROFILE_ERROR: {exc}", file=sys.stderr)
        if exc.receipt is not None and output is not None:
            output.write_text(
                json.dumps(exc.receipt, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            print(format_top_table(exc.receipt))
            print(f"wrote_partial {posix_relative(output)}")
        return 2
    output.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(format_top_table(receipt))
    print(f"wrote {posix_relative(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
