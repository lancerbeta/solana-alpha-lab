#!/usr/bin/env python3
"""Deterministic offline benchmark for local mature-cohort materialization.

The benchmark exercises the production source-builder against synthetic
SNAPSHOT_PLUS_DELTA RDP data. It reports cold replay, unchanged warm reuse,
one-step tail advancement, and deep-history warm reuse. It never contacts a
provider, touches VPS/runtime state, or runs seal/import/Forge operations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from solana_alpha_lab.factory import live_cohort_discovery_release as release  # noqa: E402
from solana_alpha_lab.factory.live_cohort_source_bundle import (  # noqa: E402
    extraction_counters,
    reset_extraction_counters,
)
from solana_alpha_lab.factory.live_cohort_to_forge import (  # noqa: E402
    synthetic_closed_receipt,
)
from solana_alpha_lab.factory.members_snapshot_delta import (  # noqa: E402
    _invalidate_operational_latest,
    _operational_latest_paths,
    append_delta_publication,
    operational_latest_cache_bytes,
    reconstruct_stats,
    reset_fingerprint_work,
    write_snapshot_unit,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    persist_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from solana_alpha_lab.storage.manifests import compute_dataset_manifest_id  # noqa: E402


ACTIVATION_ID = "ACT-LOCAL-COHORT-INCREMENTAL-V1"
COHORT_ID = "REL-20260902T111900Z-20260909T111900Z"
WINDOW_START = datetime(2026, 9, 2, 11, 19, tzinfo=UTC)
WINDOW_END = WINDOW_START + timedelta(days=7)
AS_OF = datetime(2026, 9, 10, 16, 58, tzinfo=UTC)
PRODUCER_A = "a" * 40
PRODUCER_B = "b" * 40


def _schedule() -> dict[str, Any]:
    schedule = load_observation_schedule(
        ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
    )
    schedule = dict(schedule)
    schedule.pop("schedule_sha256", None)
    schedule["activation"] = {
        **dict(schedule.get("activation") or {}),
        "starts_at": "2026-09-02T11:19:00Z",
        "stops_admitting_at": "2026-09-23T11:19:00Z",
        "cadence_alignment": "UTC_EPOCH",
    }
    validated = validate_observation_schedule(schedule, root=ROOT)
    digest = schedule_sha256(validated)
    validated["schedule_sha256"] = digest
    return validated


def _member(digest: str, index: int, *, tag: str = "A") -> dict[str, str]:
    entity = f"BenchMint{index:06d}{'p' * 32}"
    stamp = "2026-09-03T00:00:00Z"
    return {
        "schedule_sha256": digest,
        "activation_id": ACTIVATION_ID,
        "entity_id": entity,
        "membership_state": "OBSERVED",
        "candidate_state": "ADMITTED",
        "authoritative_anchor": stamp,
        "inclusion_probability": "0.0425",
        "sampling_seed": "LOCAL-MATERIALIZATION-BENCH-V1",
        "discovery_available_at": stamp,
        "first_reliable_available_at": stamp,
        "request_sha256": "a" * 64,
        "response_sha256": hashlib.sha256(tag.encode("utf-8")).hexdigest(),
    }


def _observation(digest: str, index: int, *, available_at: datetime) -> dict[str, Any]:
    entity = f"BenchMint{index:06d}{'p' * 32}"
    event_at = WINDOW_START + timedelta(hours=1)
    return {
        "schedule_sha256": digest,
        "activation_id": ACTIVATION_ID,
        "entity_id": entity,
        "point_id": "X300",
        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
        "event_time": event_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_reliable_available_at": available_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "request_sha256": "c" * 64,
        "response_sha256": "d" * 64,
        "call_occurrence_id": f"{index:064x}",
        "http_status": 200,
        "http_class": "HTTP_OK",
        "field_values": [
            {
                "field_id": "FIELD-LIQUIDITY-USD-001",
                "value_kind": "DECIMAL",
                "typed_value": "1.25",
                "state": "OBSERVED",
            }
        ],
    }


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd")


def _append_event(
    data_root: Path,
    *,
    record_id: str,
    kind: RecordKind,
    digest: str,
    payload: dict[str, Any],
    effective_at: datetime,
    producer: str,
) -> None:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    event = ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=digest,
        hypothesis_version_id=None,
        run_id=ACTIVATION_ID,
        transaction_id=f"RESEARCH-TXN-{record_id.upper()}",
        effective_at=effective_at,
        first_reliable_available_at=effective_at,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001",
        producer_git_sha=producer,
        created_at=effective_at,
    )
    ResearchStore(data_root).append([event], transaction_id=event.transaction_id)


def _publish_observation_panel(
    data_root: Path,
    *,
    digest: str,
    effective_at: datetime,
    member_location: str,
    observation_location: str,
    member_count: int,
    observation_count: int,
    tag: str,
) -> None:
    utc_day = effective_at.strftime("%Y%m%d")
    dataset_key = f"observation-panel-{tag}-{digest[:12]}"
    dataset_id = compute_dataset_manifest_id(dataset_key, utc_day)
    member_rel = member_location.replace("\\", "/")
    observation_rel = observation_location.replace("\\", "/")
    created = effective_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    manifests = data_root / "datasets" / "manifests"
    partitions = manifests / "partitions"
    manifests.mkdir(parents=True, exist_ok=True)
    partitions.mkdir(parents=True, exist_ok=True)
    member_part = {
        "partition_manifest_id": f"partition-{tag}-members",
        "dataset_manifest_id": dataset_id,
        "partition_id": f"utc-day-{utc_day}-members",
        "logical_location": member_rel,
    }
    observation_part = {
        "partition_manifest_id": f"partition-{tag}-observations",
        "dataset_manifest_id": dataset_id,
        "partition_id": f"utc-day-{utc_day}",
        "logical_location": observation_rel,
    }
    for partition in (member_part, observation_part):
        (partitions / f"{partition['partition_manifest_id']}.json").write_text(
            json.dumps(partition, sort_keys=True), encoding="utf-8"
        )
    manifest = {
        "dataset_manifest_id": dataset_id,
        "dataset_id": dataset_key,
        "dataset_version": utc_day,
        "created_at": created,
        "first_reliable_available_at": created,
        "partitions": [observation_part, member_part],
    }
    (manifests / f"{dataset_id}.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    (manifests / f"{dataset_id}.published").write_text(
        json.dumps(
            {"dataset_manifest_id": dataset_id, "dataset_fingerprint": tag},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _append_event(
        data_root,
        record_id=f"BENCH-MEM-{tag}",
        kind=RecordKind.OBSERVATION_MEMBER_BATCH,
        digest=digest,
        payload={
            "schedule_sha256": digest,
            "activation_id": ACTIVATION_ID,
            "dataset_manifest_id": dataset_id,
            "member_location": member_rel,
            "row_count": member_count,
            "discovery_coverage_class": "GAP_SUSPECTED",
        },
        effective_at=effective_at,
        producer=PRODUCER_A,
    )
    _append_event(
        data_root,
        record_id=f"BENCH-OBS-{tag}",
        kind=RecordKind.OBSERVATION_BATCH,
        digest=digest,
        payload={
            "schedule_sha256": digest,
            "activation_id": ACTIVATION_ID,
            "dataset_manifest_id": dataset_id,
            "observation_location": observation_rel,
            "row_count": observation_count,
            "discovery_coverage_class": "GAP_SUSPECTED",
        },
        effective_at=effective_at,
        producer=PRODUCER_B,
    )


def _rows_for_depth(digest: str, count: int, depth: int) -> list[dict[str, str]]:
    return [_member(digest, index, tag=f"D{depth}") for index in range(count)]


def _fixture(data_root: Path, *, depth: int, member_count: int, tag: str) -> dict[str, Any]:
    schedule = _schedule()
    digest = str(schedule["schedule_sha256"])
    persist_observation_schedule(
        data_root=data_root,
        schedule=schedule,
        now=WINDOW_START,
        producer_git_sha=PRODUCER_A,
        activation_id=ACTIVATION_ID,
    )
    unit = write_snapshot_unit(
        data_root,
        utc_day="20260902",
        dataset_manifest_id=f"bench-{tag}-anchor",
        rows=_rows_for_depth(digest, member_count, 0),
    )
    for sequence in range(1, depth + 1):
        unit = append_delta_publication(
            data_root,
            utc_day="20260902",
            dataset_manifest_id=f"bench-{tag}-delta-{sequence:03d}",
            rows=_rows_for_depth(digest, member_count, sequence),
        )
    tail_location = str(unit["publications"][-1]["rel"])
    observation_rows = [
        _observation(
            digest,
            index,
            available_at=WINDOW_START + timedelta(hours=2),
        )
        for index in range(min(member_count, 64))
    ]
    for panel_index in range(max(1, depth)):
        observation_path = (
            data_root
            / "datasets"
            / "parquet"
            / f"bench-{tag}"
            / f"observations-{panel_index:03d}.parquet"
        )
        _write_parquet(observation_path, observation_rows)
        _publish_observation_panel(
            data_root,
            digest=digest,
            effective_at=WINDOW_START + timedelta(minutes=depth + panel_index + 1),
            member_location=tail_location,
            observation_location=observation_path.relative_to(data_root).as_posix(),
            member_count=member_count,
            observation_count=len(observation_rows),
            tag=f"{tag}-{panel_index:03d}",
        )
    return {
        "data_root": data_root,
        "schedule": schedule,
        "digest": digest,
        "unit": unit,
        "unit_dir": data_root / "datasets" / "members_snapshot_plus_delta" / "20260902",
        "tail_location": tail_location,
        "member_count": member_count,
    }


def _wrap_timing(
    timings: dict[str, float],
    name: str,
    fn: Callable[..., Any],
) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            timings[name] = timings.get(name, 0.0) + time.perf_counter() - started

    return wrapped


def _build(fixture: dict[str, Any], *, label: str) -> dict[str, Any]:
    reset_extraction_counters()
    reset_fingerprint_work()
    timings: dict[str, float] = {}
    targets: list[str] = []
    originals: dict[str, Any] = {
        "members": release._cohort_members_into_sqlite,
        "selection": release._cohort_contributing_lineage,
        "observations": release._cohort_observations_into_sqlite,
        "parquet": release.write_parquet_from_row_batches,
        "hash": release.sha256_file_streaming,
        "reconstruct": release._reconstruct_to_sqlite,
    }

    def timed_reconstruct(*args: Any, **kwargs: Any) -> Any:
        if len(args) >= 3:
            targets.append(str(args[2]))
        elif "dataset_manifest_id" in kwargs:
            targets.append(str(kwargs["dataset_manifest_id"]))
        started = time.perf_counter()
        try:
            return originals["reconstruct"](*args, **kwargs)
        finally:
            timings["member_reconstruction_wall_s"] = timings.get(
                "member_reconstruction_wall_s", 0.0
            ) + time.perf_counter() - started

    release._cohort_members_into_sqlite = _wrap_timing(
        timings, "member_materialization_wall_s", originals["members"]
    )
    release._cohort_contributing_lineage = _wrap_timing(
        timings, "cohort_selection_wall_s", originals["selection"]
    )
    release._cohort_observations_into_sqlite = _wrap_timing(
        timings, "observation_extraction_wall_s", originals["observations"]
    )
    release.write_parquet_from_row_batches = _wrap_timing(
        timings, "parquet_write_wall_s", originals["parquet"]
    )
    release.sha256_file_streaming = _wrap_timing(
        timings, "parquet_hash_wall_s", originals["hash"]
    )
    release._reconstruct_to_sqlite = timed_reconstruct
    started = time.perf_counter()
    try:
        source = release.build_live_observation_source_from_rdp(
            observation_rdp_root=fixture["data_root"],
            schedule_sha256=fixture["digest"],
            activation_id=ACTIVATION_ID,
            cohort_id=COHORT_ID,
            as_of=AS_OF,
            closure_receipt=synthetic_closed_receipt(
                schedule_sha256=fixture["digest"],
                activation_id=ACTIVATION_ID,
                cohort_id=COHORT_ID,
                as_of=AS_OF,
                members_total=fixture["member_count"],
            ),
            discovery_coverage_class="GAP_SUSPECTED",
        )
    finally:
        release._cohort_members_into_sqlite = originals["members"]
        release._cohort_contributing_lineage = originals["selection"]
        release._cohort_observations_into_sqlite = originals["observations"]
        release.write_parquet_from_row_batches = originals["parquet"]
        release.sha256_file_streaming = originals["hash"]
        release._reconstruct_to_sqlite = originals["reconstruct"]
    timings["build_wall_s"] = time.perf_counter() - started
    counters = extraction_counters()
    stats = reconstruct_stats()
    cache = operational_latest_cache_bytes(fixture["unit_dir"])
    _db_path, cache_meta_path = _operational_latest_paths(fixture["unit_dir"])
    cache_meta = {}
    if cache_meta_path.is_file():
        cache_meta = json.loads(cache_meta_path.read_text(encoding="utf-8"))
    tail_delta_counts = fixture["unit"]["publications"][-1].get("delta_counts")
    scratch_bytes = sum(
        path.stat().st_size
        for path in fixture["data_root"].rglob(".build-*")
        if path.is_file()
    )
    return {
        "label": label,
        "source_sha256": source["source_sha256"],
        "member_count": source["member_count"],
        "observation_count": source["observation_count"],
        "wall_s": round(timings["build_wall_s"], 6),
        "stage_timings_s": {key: round(value, 6) for key, value in sorted(timings.items())},
        "anchor_loads": stats["anchor_loads"],
        "reconstruct_calls": stats["reconstruct_calls"],
        "reconstruct_targets": targets,
        "delta_files_applied": stats["delta_files_applied"],
        "incremental_extensions": stats["incremental_extensions"],
        "tail_delta_counts": tail_delta_counts,
        "cache_dataset_manifest_id": cache_meta.get("dataset_manifest_id"),
        "cache_seq": cache_meta.get("seq"),
        "repeated_exact_publication_reconstruction_count": sum(
            count - 1 for count in Counter(targets).values() if count > 1
        ),
        "checkpoint_hits": counters["member_checkpoint_hits"],
        "checkpoint_misses": counters["member_checkpoint_misses"],
        "target_cache_hits": counters["member_target_cache_hits"],
        "full_member_row_materializations": counters["full_member_row_materializations"],
        "member_snapshot_full_column_scans": counters["member_snapshot_full_column_scans"],
        "member_snapshot_admission_probes": counters["member_snapshot_admission_probes"],
        "observation_panel_rows_decoded": counters["observation_panel_rows_decoded"],
        "cache_bytes": cache,
        "scratch_bytes_after": scratch_bytes,
        "non_claims": [
            "NOT_LIVE_HOST_MEASUREMENT",
            "NO_PROVIDER_CALLS",
            "NO_VPS",
            "NO_SEAL_VERIFY_IMPORT",
            "NO_FORGE_EXECUTION",
        ],
    }


def _one_step(fixture: dict[str, Any]) -> None:
    sequence = len(fixture["unit"]["publications"])
    db_path, meta_path = _operational_latest_paths(fixture["unit_dir"])
    previous_cache = (db_path.read_bytes(), meta_path.read_bytes())
    rows = _rows_for_depth(fixture["digest"], fixture["member_count"], sequence - 1)
    rows[0] = dict(rows[0])
    rows[0]["response_sha256"] = hashlib.sha256(
        b"one-step-single-changed-member"
    ).hexdigest()
    unit = append_delta_publication(
        fixture["data_root"],
        utc_day="20260902",
        dataset_manifest_id="bench-one-step-delta",
        rows=rows,
    )
    observation_path = (
        fixture["data_root"] / "datasets" / "parquet" / "bench-one-step" / "observations.parquet"
    )
    rows = [
        _observation(
            fixture["digest"],
            index,
            available_at=WINDOW_START + timedelta(hours=3),
        )
        for index in range(min(fixture["member_count"], 64))
    ]
    _write_parquet(observation_path, rows)
    _publish_observation_panel(
        fixture["data_root"],
        digest=fixture["digest"],
        effective_at=WINDOW_START + timedelta(hours=1),
        member_location=str(unit["publications"][-1]["rel"]),
        observation_location=observation_path.relative_to(fixture["data_root"]).as_posix(),
        member_count=fixture["member_count"],
        observation_count=len(rows),
        tag="one-step",
    )
    # The publication writer may already refresh the latest cache.  Preserve
    # the prior tail here to exercise the source-builder's one-delta extension
    # path, which is the production case when canonical append and source
    # materialization are decoupled.
    db_path.write_bytes(previous_cache[0])
    meta_path.write_bytes(previous_cache[1])
    fixture["unit"] = unit


def run_benchmark() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="smial-local-materialization-") as tmp:
        root = Path(tmp)
        cold_fixture = _fixture(root / "cold", depth=10, member_count=512, tag="cold")
        _invalidate_operational_latest(cold_fixture["unit_dir"])
        cold = _build(cold_fixture, label="cold_depth_10")
        warm = _build(cold_fixture, label="warm_unchanged_depth_10")

        one_step_fixture = _fixture(root / "one-step", depth=10, member_count=512, tag="step")
        _build(one_step_fixture, label="one_step_seed_depth_10")
        _one_step(one_step_fixture)
        one_step = _build(one_step_fixture, label="one_step_incremental_depth_11")
        _invalidate_operational_latest(one_step_fixture["unit_dir"])
        one_step_cold = _build(one_step_fixture, label="one_step_cold_depth_11")

        deep_fixture = _fixture(root / "deep", depth=100, member_count=512, tag="deep")
        deep = _build(deep_fixture, label="warm_deep_depth_100")

        parity = cold["source_sha256"] == warm["source_sha256"]
        acceptance = {
            "cold_replays_once": cold["reconstruct_calls"] == 1,
            "warm_reuses_tail": (
                warm["reconstruct_calls"] == 0
                and warm["checkpoint_hits"] == 1
                and warm["member_snapshot_full_column_scans"] == 0
            ),
            "one_step_reuses_new_tail": (
                one_step["reconstruct_calls"] == 0
                and one_step["checkpoint_hits"] == 2
                and one_step["target_cache_hits"] == 10
                and one_step["member_snapshot_full_column_scans"] == 0
                and one_step["incremental_extensions"] == 1
                and one_step["delta_files_applied"] == 1
                and one_step["cache_dataset_manifest_id"] == "bench-one-step-delta"
                and one_step["cache_seq"] == 11
                and one_step["tail_delta_counts"]["added"] == 0
                and one_step["tail_delta_counts"]["changed"] == 1
                and one_step["tail_delta_counts"]["removed"] == 0
            ),
            "one_step_source_parity": (
                one_step["source_sha256"] == one_step_cold["source_sha256"]
                and one_step["incremental_extensions"] == 1
                and one_step["delta_files_applied"] == 1
                and one_step_cold["reconstruct_calls"] == 2
                and one_step_cold["anchor_loads"] == 2
            ),
            "deep_history_same_warm_class": (
                deep["reconstruct_calls"] == warm["reconstruct_calls"]
                and deep["anchor_loads"] == warm["anchor_loads"]
                and deep["delta_files_applied"] == warm["delta_files_applied"]
                and deep["member_snapshot_full_column_scans"]
                == warm["member_snapshot_full_column_scans"]
            ),
            "unchanged_source_parity": parity,
            "no_repeated_exact_publication_reconstruction": all(
                item["repeated_exact_publication_reconstruction_count"] == 0
                for item in (cold, warm, one_step, one_step_cold, deep)
            ),
            "scratch_clean_after_warm_paths": (
                warm["scratch_bytes_after"] == 0
                and one_step["scratch_bytes_after"] == 0
                and deep["scratch_bytes_after"] == 0
            ),
        }
        return {
            "schema": "smial.local-cohort-incremental-materialization-benchmark",
            "schema_version": "1.0",
            "task_id": "LOCAL_COHORT_INCREMENTAL_MATERIALIZATION_V1",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "member_count": 512,
            "scenarios": [cold, warm, one_step, one_step_cold, deep],
            "acceptance": acceptance,
            "observation_history": {
                "cold_decoded_rows": cold["observation_panel_rows_decoded"],
                "one_step_decoded_rows": one_step["observation_panel_rows_decoded"],
                "deep_decoded_rows": deep["observation_panel_rows_decoded"],
                "deep_to_one_step_decoded_row_ratio": round(
                    deep["observation_panel_rows_decoded"]
                    / max(one_step["observation_panel_rows_decoded"], 1),
                    3,
                ),
                "status": "LINEAR_WITH_CONSIDERED_OBSERVATION_PANEL_INPUT",
                "note": (
                    "The patch removes the duplicate lineage pass; an index for "
                    "historical observation panels is outside this atom."
                ),
            },
            "all_acceptance_pass": all(acceptance.values()),
            "seal_verify_import": "NOT_RUN_OFFLINE",
            "provider_calls": 0,
            "network": "NONE",
            "scientific_claim": "NONE",
            "non_claims": [
                "NOT_LIVE_C1",
                "NOT_LIVE_HOST_SLO",
                "NO_PROVIDER_BEHAVIOR",
                "NO_VPS_RUNTIME_CHANGE",
                "NO_SEAL_VERIFY_IMPORT",
                "NO_FORGE_EXECUTION",
            ],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    previous_stage_timing = os.environ.get("SMIAL_PUBLICATION_STAGE_TIMING")
    os.environ["SMIAL_PUBLICATION_STAGE_TIMING"] = "0"
    try:
        receipt = run_benchmark()
    finally:
        if previous_stage_timing is None:
            os.environ.pop("SMIAL_PUBLICATION_STAGE_TIMING", None)
        else:
            os.environ["SMIAL_PUBLICATION_STAGE_TIMING"] = previous_stage_timing
    encoded = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if receipt["all_acceptance_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
