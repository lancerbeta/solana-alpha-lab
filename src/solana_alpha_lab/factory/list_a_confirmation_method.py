"""Frozen List A crossed bootstrap. Pure arithmetic; no execution authority."""
from __future__ import annotations

import hashlib
import json
import math
import platform
import random
import sys
from collections import Counter
from datetime import UTC, datetime

CORE_SHA = "3b62c8ccdc797c8f378aef831c2b5cad45bdc1e9c336ba94417bf54ccbd7e252"
B = 4096
PARTITIONS = (86400, 172800)
NUMERIC_REFUSALS = frozenset({"TEMPORAL_TARGET_NONFINITE", "TEMPORAL_TARGET_UNREPRESENTABLE"})


def finite_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(finite_bytes(value)).hexdigest()


def qualify_runtime() -> dict:
    if platform.python_implementation() != "CPython" or sys.version_info[:3] != (3, 13, 14):
        raise ValueError("NUMERIC_RUNTIME_UNQUALIFIED")
    if sys.float_info.mant_dig != 53 or sys.float_info.radix != 2:
        raise ValueError("NUMERIC_RUNTIME_UNQUALIFIED")
    return {"implementation": "CPython", "version": "3.13.14", "mant_dig": 53,
            "serialization": "FINITE_JSON_SHORTEST_ROUNDTRIP",
            "core_sha256": CORE_SHA, "replicates": B,
            "seeds": {str(h): seed_for(h) for h in PARTITIONS}}


def seed_for(h: int) -> int:
    if h not in PARTITIONS:
        raise ValueError("PARTITION_NOT_FROZEN")
    return int(hashlib.sha256(f"{CORE_SHA}:{h}".encode()).hexdigest()[:16], 16)


def block_for(instant: datetime, h: int) -> int:
    if instant.tzinfo is None:
        raise ValueError("TIMESTAMP_INVALID")
    delta = instant.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) // h


def weighted_contrast(rows: list[dict], weights: list[int]) -> tuple[float, float, float] | None:
    means = []
    for group in ("A", "C"):
        selected = [(w, row["r"]) for row, w in zip(rows, weights, strict=True)
                    if row["group"] == group and w]
        denominator = math.fsum(w for w, _ in selected)
        if not denominator:
            return None
        try:
            mean = math.fsum(w * r for w, r in selected) / denominator
        except (OverflowError, ValueError):
            return None
        if not math.isfinite(mean):
            return None
        means.append(mean)
    contrast = means[0] - means[1]
    return (*means, contrast) if math.isfinite(contrast) else None


def draw_weights(rows: list[dict], mints: list[str], blocks: list[int], h: int,
                 rng: random.Random) -> list[int]:
    """M draws before T draws; pooled axes, shared A/C multiplicities."""
    mm = Counter(mints[rng.randrange(len(mints))] for _ in mints)
    tt = Counter(blocks[rng.randrange(len(blocks))] for _ in blocks)
    return [mm[row["mint"]] * tt[row["blocks"][str(h)]] for row in rows]


def nearest_rank_interval(contrasts: list[float]) -> list[float]:
    if len(contrasts) != B or any(not math.isfinite(v) for v in contrasts):
        raise ValueError("INVALID_REPLICATE_VECTOR")
    ordered = sorted(contrasts)
    return [ordered[102], ordered[3993]]


def calculate_list_a(observed_rows: list[dict], denominators: dict[str, int], *,
                     qualified_protocol_core: str = CORE_SHA) -> dict:
    if qualified_protocol_core != CORE_SHA:
        raise ValueError("PROTOCOL_CORE_MISMATCH")
    qualify_runtime()
    rows = sorted(observed_rows, key=lambda r: r["episode_id"])
    if len({r["episode_id"] for r in rows}) != len(rows):
        raise ValueError("DUPLICATE_EPISODE")
    if any(r["group"] not in {"A", "C"} or
           (r["r"] is None and r.get("numeric_refusal") not in NUMERIC_REFUSALS) or
           (r["r"] is not None and (not math.isfinite(r["r"]) or "numeric_refusal" in r)) for r in rows):
        raise ValueError("INVALID_OBSERVED_ROW")
    count = Counter(r["group"] for r in rows)
    if any(type(denominators.get(g)) is not int or denominators[g] < count[g]
           or denominators[g] < 0 for g in ("A", "C")):
        raise ValueError("DENOMINATOR_INVALID")
    coverage = {g: count[g] / denominators[g] if denominators[g] else None for g in ("A", "C")}
    mints = sorted({r["mint"] for r in rows})
    axes = {str(h): sorted({r["blocks"][str(h)] for r in rows}) for h in PARTITIONS}
    support = {g: {"observed": count[g], "decision_denominator": denominators[g],
                   "mints": len({r["mint"] for r in rows if r["group"] == g}),
                   "blocks": {str(h): len({r["blocks"][str(h)] for r in rows if r["group"] == g})
                              for h in PARTITIONS}}
               for g in ("A", "C")}
    reasons = sorted({r["numeric_refusal"] for r in rows if r["r"] is None})
    if any(denominators[g] == 0 for g in ("A", "C")):
        reasons.append("EMPTY_DECISION_GROUP")
    if len(mints) < 30 or any(len(v) < 30 for v in axes.values()) or any(
            s["mints"] < 30 or any(v < 30 for v in s["blocks"].values()) for s in support.values()):
        reasons.append("INSUFFICIENT_ACTUAL_SUPPORT")
    # Integer predicates preserve the accepted decimal boundaries exactly.
    if any(count[g] * 100 < denominators[g] * 95 for g in ("A", "C")):
        reasons.append("TARGET_COVERAGE_BELOW_95_PERCENT")
    if abs(count["A"] * denominators["C"] - count["C"] * denominators["A"]) * 100 > (
            5 * denominators["A"] * denominators["C"]):
        reasons.append("MISSING_RATE_GAP_ABOVE_5_PERCENT")
    point = None if any(r["r"] is None for r in rows) else weighted_contrast(rows, [1] * len(rows))
    if point is None:
        reasons.append("NONFINITE_OR_EMPTY_GROUP")
    result = {"protocol_core_sha256": CORE_SHA, "replicates_per_partition": B,
              "support": support, "coverage": coverage, "pooled_mints": len(mints),
              "pooled_blocks": {k: len(v) for k, v in axes.items()},
              "means": {"A": point[0], "C": point[1]} if point else None,
              "contrast": point[2] if point else None, "partitions": {},
              "leave_one": {}, "reason_codes": reasons,
              "terminal": "INSUFFICIENT", "numeric_order": "CANONICAL_EPISODE_ID_MATH_FSUM",
              "quantile_indices": [102, 3993], "observed_mask_sha256": digest(rows)}
    if reasons:
        return result
    leave_one = []
    for h in PARTITIONS:
        key = str(h)
        rng = random.Random(seed_for(h))
        contrasts = []
        invalid = 0
        for _ in range(B):
            estimate = weighted_contrast(rows, draw_weights(rows, mints, axes[key], h, rng))
            if estimate is None:
                invalid += 1
            else:
                contrasts.append(estimate[2])
        result["partitions"][key] = {
            "seed": seed_for(h), "valid_replicates": len(contrasts), "invalid_replicates": invalid,
            "replicate_digest_sha256": digest(contrasts),
            "interval": nearest_rank_interval(contrasts) if not invalid else None}
        if invalid:
            reasons.append("EMPTY_OR_NONFINITE_REPLICATE")
        for block in axes[key]:
            estimate = weighted_contrast(rows, [int(r["blocks"][key] != block) for r in rows])
            leave_one.append({"axis": "BLOCK", "partition": h, "label": block,
                              "contrast": estimate[2] if estimate else None})
    for mint in mints:
        estimate = weighted_contrast(rows, [int(r["mint"] != mint) for r in rows])
        leave_one.append({"axis": "MINT", "label": mint,
                          "contrast": estimate[2] if estimate else None})
    ds = [item["contrast"] for item in leave_one if item["contrast"] is not None]
    result["leave_one"] = {"count": len(leave_one), "valid_count": len(ds),
                           "min": min(ds) if ds else None, "max": max(ds) if ds else None,
                           "digest_sha256": digest(leave_one),
                           "min_labels": [d for d in leave_one if ds and d["contrast"] == min(ds)],
                           "max_labels": [d for d in leave_one if ds and d["contrast"] == max(ds)]}
    if len(ds) != len(leave_one):
        reasons.append("EMPTY_OR_NONFINITE_LEAVE_ONE")
    if reasons:
        return result
    intervals = [result["partitions"][str(h)]["interval"] for h in PARTITIONS]
    if all(v[0] > 0 for v in intervals) and min(ds) > 0:
        result["terminal"] = "ASSOCIATION_SUPPORTED_CONDITIONAL"
    elif all(v[1] <= 0 for v in intervals) and max(ds) <= 0:
        result["terminal"] = "ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY"
    else:
        result["terminal"] = "INCONCLUSIVE_DEPENDENCE_OR_CONCENTRATION"
    return result
