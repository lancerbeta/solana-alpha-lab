#!/usr/bin/env python3
"""Deterministic module-level CI test partition planner and selector."""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path
from collections.abc import Collection, Mapping
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# CI contract range for general test shards (validate_ci.load_shard_plan reads
# the same bounds). The planner itself accepts any count up to the maximum.
SHARD_COUNT_MIN = 4
SHARD_COUNT_MAX = 6
SHARD_TARGET_MAX_SECONDS = 15 * 60.0
SHARD_TARGET_MAX_MIN_RATIO = 1.25
MODULE_DONE_LINE = re.compile(
    r"module_done seconds=(?P<seconds>[0-9.]+) cases=(?P<cases>[0-9]+) "
    r"module=(?P<module>\S+)"
)


class PartitionError(ValueError):
    """Fail-closed partition contract error."""


def posix(path: str | Path) -> str:
    return Path(path).as_posix()


def plan_shards(
    module_seconds: dict[str, float],
    *,
    shard_count: int,
    source_profile_sha256: str,
) -> dict[str, Any]:
    if shard_count < 1 or shard_count > SHARD_COUNT_MAX:
        raise PartitionError("SHARD_COUNT_OUT_OF_RANGE")
    if not module_seconds:
        raise PartitionError("EMPTY_MODULE_INVENTORY")
    ordered = sorted(
        ((posix(path), float(seconds)) for path, seconds in module_seconds.items()),
        key=lambda item: (-item[1], item[0]),
    )
    loads = [0.0] * shard_count
    shards: list[list[str]] = [[] for _ in range(shard_count)]
    for path, seconds in ordered:
        # Equal loads (the long tail of near-zero modules) fall back to the
        # emptier shard so module counts stay balanced too.
        index = min(
            range(shard_count),
            key=lambda i: (loads[i], len(shards[i]), i),
        )
        shards[index].append(path)
        loads[index] += seconds
    for shard in shards:
        shard.sort()
    return {
        "schema": "smial.ci-test-shards.v1",
        "shard_count": shard_count,
        "source_profile_sha256": source_profile_sha256,
        "projected_seconds": [round(value, 6) for value in loads],
        "projected_max_seconds": round(max(loads), 6),
        "shards": shards,
    }


def load_balance_ratio(plan: Mapping[str, Any]) -> float:
    loads = [float(value) for value in plan["projected_seconds"]]
    smallest = min(loads)
    return float("inf") if smallest <= 0.0 else max(loads) / smallest


def choose_shard_count(module_seconds: dict[str, float]) -> int:
    """Minimal CI shard count that meets the projected wall-clock target.

    Never maximises parallelism: the first count in the CI range whose
    projected slowest shard fits the target with a balanced load wins.
    """
    for count in range(SHARD_COUNT_MIN, SHARD_COUNT_MAX + 1):
        plan = plan_shards(
            module_seconds,
            shard_count=count,
            source_profile_sha256="probe",
        )
        if (
            plan["projected_max_seconds"] <= SHARD_TARGET_MAX_SECONDS
            and load_balance_ratio(plan) <= SHARD_TARGET_MAX_MIN_RATIO
        ):
            return count
    return SHARD_COUNT_MAX


SAFE_UNSEEN_FALLBACK_SECONDS = 1.0


def module_fallback_index(path: str, shard_count: int) -> int:
    digest = hashlib.sha256(posix(path).encode("utf-8")).hexdigest()
    return int(digest, 16) % shard_count


def _planned_union(plan: dict[str, Any]) -> set[str]:
    union: set[str] = set()
    for shard in plan.get("shards") or []:
        for path in shard:
            union.add(posix(path))
    return union


def _estimated_unseen_loads(
    plan: dict[str, Any],
    count: int,
) -> tuple[list[float], float]:
    """Initial shard loads plus equal estimated weight for one unseen module.

    Fail closed to a simple positive fallback when the committed plan cannot
    produce a usable estimate. Never profiles at runtime.
    """
    planned_n = sum(len(shard) for shard in (plan.get("shards") or []))
    raw = plan.get("projected_seconds")
    try:
        loads = [float(value) for value in raw]
    except (TypeError, ValueError):
        return [0.0] * count, SAFE_UNSEEN_FALLBACK_SECONDS
    if len(loads) != count:
        return [0.0] * count, SAFE_UNSEEN_FALLBACK_SECONDS
    if planned_n < 1:
        return list(loads), SAFE_UNSEEN_FALLBACK_SECONDS
    total = sum(loads)
    if total <= 0.0:
        return list(loads), SAFE_UNSEEN_FALLBACK_SECONDS
    estimated = total / planned_n
    if estimated <= 0.0:
        return list(loads), SAFE_UNSEEN_FALLBACK_SECONDS
    return list(loads), estimated


def assign_unplanned_modules(
    current_modules: list[str],
    plan: dict[str, Any],
    count: int,
) -> dict[str, int]:
    """Deterministic load-aware shard map for modules absent from the plan."""
    if count != plan.get("shard_count"):
        raise PartitionError("SHARD_COUNT_MISMATCH")
    if count < 1:
        raise PartitionError("SHARD_COUNT_OUT_OF_RANGE")
    planned = _planned_union(plan)
    unplanned = sorted(
        {
            posix(path)
            for path in current_modules
            if posix(path) not in planned
        }
    )
    assignment: dict[str, int] = {}
    if not unplanned:
        return assignment
    loads, estimated = _estimated_unseen_loads(plan, count)
    for path in unplanned:
        index = min(range(count), key=lambda i: (loads[i], i))
        assignment[path] = index
        loads[index] += estimated
    return assignment


def select_modules_for_shard(
    current_modules: list[str],
    *,
    plan: dict[str, Any],
    index: int,
    count: int,
) -> list[str]:
    if count != plan.get("shard_count"):
        raise PartitionError("SHARD_COUNT_MISMATCH")
    if index < 0 or index >= count:
        raise PartitionError("SHARD_INDEX_OUT_OF_RANGE")
    planned = {posix(path) for path in plan["shards"][index]}
    unplanned_assignment = assign_unplanned_modules(current_modules, plan, count)
    selected: list[str] = []
    seen: set[str] = set()
    for raw in current_modules:
        path = posix(raw)
        if path in seen:
            raise PartitionError(f"DUPLICATE_CURRENT_MODULE:{path}")
        seen.add(path)
        if path in planned:
            selected.append(path)
            continue
        if unplanned_assignment.get(path) == index:
            selected.append(path)
    selected.sort()
    return selected


def union_and_duplicates(plan: dict[str, Any]) -> tuple[set[str], set[str]]:
    union: set[str] = set()
    duplicates: set[str] = set()
    for shard in plan["shards"]:
        for path in shard:
            key = posix(path)
            if key in union:
                duplicates.add(key)
            union.add(key)
    return union, duplicates


def load_plan(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise PartitionError("PLAN_NOT_OBJECT")
    if document.get("schema") != "smial.ci-test-shards.v1":
        raise PartitionError("PLAN_SCHEMA_INVALID")
    if not isinstance(document.get("shard_count"), int):
        raise PartitionError("PLAN_SCHEMA_INVALID")
    if not isinstance(document.get("shards"), list):
        raise PartitionError("PLAN_SCHEMA_INVALID")
    if len(document["shards"]) != document["shard_count"]:
        raise PartitionError("PLAN_SHARD_LENGTH_MISMATCH")
    union, duplicates = union_and_duplicates(document)
    if duplicates:
        raise PartitionError(
            "PLAN_DUPLICATE_MODULES:" + ",".join(sorted(duplicates)[:20])
        )
    if not union:
        raise PartitionError("PLAN_EMPTY_UNION")
    return document


def write_plan(path: Path, plan: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def modules_from_profile(profile: dict[str, Any]) -> dict[str, float]:
    rows = profile.get("modules")
    if not isinstance(rows, list) or not rows:
        raise PartitionError("PROFILE_MODULES_MISSING")
    out: dict[str, float] = {}
    for row in rows:
        path = posix(row["path"])
        out[path] = float(row["seconds"])
    return out


def subtract_reserved_modules(
    module_seconds: Mapping[str, float],
    reserved_modules: Collection[str],
) -> dict[str, float]:
    normalized = {posix(path): float(seconds) for path, seconds in module_seconds.items()}
    reserved = {posix(path) for path in reserved_modules}
    missing = sorted(reserved - set(normalized))
    if missing:
        raise PartitionError(
            "RESERVED_MODULE_MISSING_FROM_PROFILE:" + ",".join(missing[:20])
        )
    return {
        path: seconds
        for path, seconds in normalized.items()
        if path not in reserved
    }


def module_path_from_module_done(module: str) -> str:
    """Map a module_done module name to its flat tests/ path."""
    name = module[len("tests.") :] if module.startswith("tests.") else module
    return f"tests/{name}.py"


def module_seconds_from_logs(
    log_texts: list[str],
    inventory: Collection[str],
) -> tuple[dict[str, float], dict[str, Any]]:
    """Median per-module seconds from CI shard logs, limited to the inventory.

    Names that are not current inventory modules (modules created by tests at
    run time) are ignored. A module's samples are its per-log totals, so the
    bare and dotted import names of one file add up inside one log.
    """
    wanted = {posix(path) for path in inventory}
    samples: dict[str, list[float]] = {}
    for text in log_texts:
        per_log: dict[str, float] = {}
        for match in MODULE_DONE_LINE.finditer(text):
            path = module_path_from_module_done(match.group("module"))
            if path in wanted:
                per_log[path] = per_log.get(path, 0.0) + float(match.group("seconds"))
        for path, seconds in per_log.items():
            samples.setdefault(path, []).append(seconds)
    if not samples:
        raise PartitionError("MODULE_DONE_TELEMETRY_MISSING")
    medians = {
        path: round(statistics.median(values), 3)
        for path, values in sorted(samples.items())
    }
    provenance = {
        "kind": "CI_MODULE_DONE_MEDIAN",
        "log_count": len(log_texts),
        "module_count": len(medians),
        "min_samples_per_module": min(len(values) for values in samples.values()),
        "unprofiled_inventory_modules": sorted(wanted - set(medians)),
    }
    return medians, provenance


def compare_shard_counts(
    module_seconds: Mapping[str, float],
    counts: Collection[int],
) -> list[dict[str, Any]]:
    rows = []
    for count in sorted(counts):
        plan = plan_shards(
            dict(module_seconds), shard_count=count, source_profile_sha256="probe"
        )
        rows.append(
            {
                "shard_count": count,
                "projected_max_seconds": plan["projected_max_seconds"],
                "projected_min_seconds": min(plan["projected_seconds"]),
                "max_min_ratio": round(load_balance_ratio(plan), 4),
            }
        )
    return rows


def canonical_json_sha256(document: Any) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--profile", type=Path)
    source.add_argument(
        "--module-done-log",
        type=Path,
        action="append",
        help="CI shard log with module_done telemetry; repeat for the median",
    )
    parser.add_argument("--reserved-manifest", required=True, type=Path)
    parser.add_argument("--shard-count", type=int)
    parser.add_argument("--compare-counts", help="comma list, e.g. 4,5,6; no write")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--source-run",
        action="append",
        default=[],
        help="exact-head CI run id that produced a --module-done-log",
    )
    parser.add_argument("--tests-root", type=Path, default=ROOT / "tests")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.reserved_manifest.read_text(encoding="utf-8"))
        reserved = {
            posix(path) for path in (manifest.get("required_fast_test_modules") or [])
        }
        profile_note: dict[str, Any]
        if args.module_done_log:
            inventory = {
                posix(path.resolve().relative_to(ROOT.resolve()))
                for path in args.tests_root.glob("test_*.py")
                if path.is_file()
            }
            general_modules, profile_note = module_seconds_from_logs(
                [
                    path.read_text(encoding="utf-8", errors="replace")
                    for path in args.module_done_log
                ],
                inventory - reserved,
            )
            profile_sha256 = canonical_json_sha256(general_modules)
            profile_note["source_runs"] = sorted(args.source_run)
        else:
            profile_bytes = args.profile.read_bytes()
            profile = json.loads(profile_bytes.decode("utf-8"))
            general_modules = subtract_reserved_modules(
                modules_from_profile(profile),
                reserved,
            )
            profile_sha256 = hashlib.sha256(profile_bytes).hexdigest()
            profile_note = {"kind": "SEQUENTIAL_PROFILE_FILE"}
        if not general_modules:
            raise PartitionError("GENERAL_MODULE_INVENTORY_EMPTY")
        if args.compare_counts:
            counts = [int(value) for value in args.compare_counts.split(",")]
            for row in compare_shard_counts(general_modules, counts):
                print(json.dumps(row, sort_keys=True))
            print(f"chosen_by_target={choose_shard_count(general_modules)}")
            if args.output is None:
                return 0
        if args.shard_count is None or args.output is None:
            raise PartitionError("SHARD_COUNT_AND_OUTPUT_REQUIRED")
        plan = plan_shards(
            general_modules,
            shard_count=args.shard_count,
            source_profile_sha256=profile_sha256,
        )
        plan["profile"] = profile_note
        plan["module_seconds"] = {
            path: round(float(seconds), 3)
            for path, seconds in sorted(general_modules.items())
        }
        write_plan(args.output, plan)
    except (PartitionError, json.JSONDecodeError) as exc:
        print(f"PARTITION_ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
