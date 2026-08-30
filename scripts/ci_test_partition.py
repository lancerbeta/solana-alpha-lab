#!/usr/bin/env python3
"""Deterministic module-level CI test partition planner and selector."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
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


def module_fallback_index(path: str, shard_count: int) -> int:
    digest = hashlib.sha256(posix(path).encode("utf-8")).hexdigest()
    return int(digest, 16) % shard_count


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
        # New module absent from plan: deterministic fallback.
        if path not in {posix(p) for shard in plan["shards"] for p in shard}:
            if module_fallback_index(path, count) == index:
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
    return document


def write_plan(path: Path, plan: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
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
