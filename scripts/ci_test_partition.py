#!/usr/bin/env python3
"""Deterministic module-level CI test partition planner and selector."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections.abc import Collection, Mapping
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


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
    if shard_count < 1 or shard_count > 4:
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
        index = min(range(shard_count), key=lambda i: (loads[i], i))
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


def choose_shard_count(module_seconds: dict[str, float]) -> int:
    for count in (3, 4):
        plan = plan_shards(
            module_seconds,
            shard_count=count,
            source_profile_sha256="probe",
        )
        if plan["projected_max_seconds"] <= 360.0:
            return count
    return 4


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


def main(argv: list[str] | None = None) -> int:
    import argparse
    import hashlib
    import json
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--reserved-manifest", required=True, type=Path)
    parser.add_argument("--shard-count", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        profile_bytes = args.profile.read_bytes()
        profile = json.loads(profile_bytes.decode("utf-8"))
        manifest = json.loads(args.reserved_manifest.read_text(encoding="utf-8"))
        reserved = manifest.get("required_fast_test_modules") or []
        general_modules = subtract_reserved_modules(
            modules_from_profile(profile),
            reserved,
        )
        if not general_modules:
            raise PartitionError("GENERAL_MODULE_INVENTORY_EMPTY")
        plan = plan_shards(
            general_modules,
            shard_count=args.shard_count,
            source_profile_sha256=hashlib.sha256(profile_bytes).hexdigest(),
        )
        write_plan(args.output, plan)
    except (PartitionError, json.JSONDecodeError) as exc:
        print(f"PARTITION_ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
