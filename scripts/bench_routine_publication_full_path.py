#!/usr/bin/env python3
"""Full post-provider publication benchmark for FACTORY_ROUTINE_PUBLICATION_WALLCLOCK_V1.

Offline, deterministic, synthetic ~205k members. No provider calls, no network.
Measures the production-shaped ``publish_observation_batch`` path END TO END on
an already-open SNAPSHOT_PLUS_DELTA day:

- member spill of the full ~205k population
- canonical content hashing over the spilled member census (full pass)
- SNAPSHOT_PLUS_DELTA delta append (cache-hit hot path)
- canonical observations.parquet write + artifact hash verification
- partition/dataset manifests, RDP events, marker, receipt finalization

Writes a JSON receipt with full wall time, stage timings, peak RSS, cache
bytes, full-population pass count and provider_calls=0.

Diagnostic only: does not replace unittest discovery as canonical validation.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.members_snapshot_delta import (  # noqa: E402
    operational_latest_cache_bytes,
)

N = 205_847
OBS_BATCH = 32
NOW = datetime(2026, 9, 12, 17, 0, tzinfo=UTC)
GIT_SHA = "c" * 40
BENCH_RUNTIME_STAGE = "WRITE_ONLY_SHADOW"


def _member(i: int, *, schedule_digest: str, state: str = "INCLUDED") -> dict[str, object]:
    return {
        "schedule_sha256": schedule_digest,
        "entity_id": f"M{i:06d}" + "x" * 36,
        "membership_state": state,
    }


def _observation(
    i: int, *, schedule_digest: str, now: datetime, entity: str
) -> dict[str, object]:
    event = now.replace(minute=5, second=0, microsecond=0)
    available = now.replace(minute=10, second=0, microsecond=0)
    return {
        "schedule_sha256": schedule_digest,
        "entity_id": entity,
        "point_id": "X300",
        "state": "OBSERVED",
        "event_time": event.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_reliable_available_at": available.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _stage_markers(stdout_text: str) -> list[dict[str, object]]:
    markers: list[dict[str, object]] = []
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("schema") == "smial.publication-stage-timing":
            markers.append(payload)
    return markers


def _worker(payload_path: Path, result_path: Path) -> int:
    """Run anchor (unmeasured) then the measured full post-provider publication."""

    import time as _time

    from solana_alpha_lab.factory.live_cohort_source_bundle import peak_rss_bytes
    from solana_alpha_lab.factory.members_snapshot_delta import (
        publication_stage_stats,
        reset_fingerprint_work,
    )
    from solana_alpha_lab.factory.observation_schedule import load_observation_schedule
    from solana_alpha_lab.factory import observation_panel_publisher as opp

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    data_root = Path(payload["data_root"])
    schedule = load_observation_schedule(
        ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
    )
    digest = str(schedule["schedule_sha256"])

    timings: dict[str, float] = {}
    counts: dict[str, int] = {}

    def _timed(name: str, fn):
        def wrapper(*args, **kwargs):
            t0 = _time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                timings[name] = timings.get(name, 0.0) + (_time.perf_counter() - t0)
                counts[name] = counts.get(name, 0) + 1

        return wrapper

    # Read-only timing wrappers around the real production stages.
    opp._spill_member_sequence = _timed("member_spill_full_population", opp._spill_member_sequence)
    opp.canonical_sha256_members_observations = _timed(
        "canonical_content_hashing", opp.canonical_sha256_members_observations
    )
    opp._write_selected_zstd_parquet = _timed(
        "observations_parquet_write", opp._write_selected_zstd_parquet
    )
    opp.append_delta_publication = _timed("snapshot_plus_delta_append", opp.append_delta_publication)
    opp._write_snapshot_unit_from_conn = _timed(
        "snapshot_anchor_write", opp._write_snapshot_unit_from_conn
    )
    opp._append_event = _timed("rdp_event_commit", opp._append_event)
    opp.persist_observation_schedule = _timed(
        "schedule_persist", opp.persist_observation_schedule
    )
    opp.build_partition_manifest = _timed("partition_manifests", opp.build_partition_manifest)
    opp.build_dataset_manifest = _timed("dataset_manifest", opp.build_dataset_manifest)
    opp._complete_job = _timed("receipt_finalize", opp._complete_job)

    anchor_members = [_member(i, schedule_digest=digest) for i in range(N)]
    anchor_entity = anchor_members[42]["entity_id"]
    reset_fingerprint_work()

    # Pre-phase (unmeasured): open the day with the anchor publication.
    t_anchor = _time.perf_counter()
    opp.publish_observation_batch(
        data_root=data_root,
        root=ROOT,
        schedule=schedule,
        activation_id="ACT-WALLCLOCK-BENCH",
        now=NOW,
        producer_git_sha=GIT_SHA,
        members=anchor_members,
        observations=[
            _observation(42, schedule_digest=digest, now=NOW, entity=anchor_entity)
        ],
    )
    anchor_wall = _time.perf_counter() - t_anchor

    # Measured phase: production-shaped second batch on the open day.
    measured_members = [
        _member(i, schedule_digest=digest, state="EXCLUDED" if i == 7 else "INCLUDED")
        for i in range(N)
    ]
    measured_observations = [
        _observation(
            i, schedule_digest=digest, now=NOW, entity=anchor_members[i * 1000]["entity_id"]
        )
        for i in range(OBS_BATCH)
    ]
    reset_fingerprint_work()
    t0 = _time.perf_counter()
    result = opp.publish_observation_batch(
        data_root=data_root,
        root=ROOT,
        schedule=schedule,
        activation_id="ACT-WALLCLOCK-BENCH",
        now=NOW,
        producer_git_sha=GIT_SHA,
        members=measured_members,
        observations=measured_observations,
    )
    measured_wall = _time.perf_counter() - t0

    result_path.write_text(
        json.dumps(
            {
                "result": {
                    "dataset_manifest_id": result["dataset_manifest_id"],
                    "member_count": result["member_count"],
                    "observation_count": result["observation_count"],
                    "replay": result["replay"],
                },
                "anchor_wall_s": anchor_wall,
                "measured_publish_wall_s": measured_wall,
                "stage_timings_s": {k: round(v, 4) for k, v in sorted(timings.items())},
                "stage_call_counts": dict(sorted(counts.items())),
                "publication_stage_stats": publication_stage_stats(),
                "max_rss_bytes": peak_rss_bytes(),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return 0


def _runtime_state_path() -> Path:
    return ROOT / "local" / "factory_v1" / "hot90_activation_runtime.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "local" / "wallclock_bench")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    data_root = args.data_root
    data_root.mkdir(parents=True, exist_ok=True)

    # Activation: production-shaped WRITE_ONLY_SHADOW members layout for the
    # benchmark process only. Existing runtime state is backed up and restored.
    runtime_path = _runtime_state_path()
    backup = None
    had_runtime = runtime_path.is_file()
    if had_runtime:
        backup = runtime_path.read_bytes()
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(
        "schema: smial.factory-hot90-archive-activation\n"
        "schema_version: '1.0'\n"
        "activation_stage: WRITE_ONLY_SHADOW\n"
        "production_compaction_enabled: false\n"
        "production_eviction_enabled: false\n"
        "drive_writes_enabled: false\n"
        "note: TEMPORARY BENCHMARK RUNTIME STATE (local only, not Git policy).\n",
        encoding="utf-8",
    )

    try:
        tmp = data_root / "payload.tmp.json"
        result_path = data_root / "bench_result.tmp.json"
        tmp.write_text(json.dumps({"data_root": str(data_root)}), encoding="utf-8")

        env = {**os.environ, "SMIAL_PUBLICATION_STAGE_TIMING": "1"}
        t_total0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-B", __file__, str(tmp), str(result_path)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=env,
        )
        process_wall = time.perf_counter() - t_total0
        if proc.returncode != 0:
            print(proc.stderr[-4000:] or proc.stdout[-4000:], file=sys.stderr)
            tmp.unlink(missing_ok=True)
            return proc.returncode or 1
        tmp.unlink(missing_ok=True)
    finally:
        # Restore exact prior runtime state; remove the temporary file otherwise.
        if backup is not None:
            runtime_path.write_bytes(backup)
        else:
            runtime_path.unlink(missing_ok=True)

    worker = json.loads(result_path.read_text(encoding="utf-8"))
    result_path.unlink(missing_ok=True)
    unit_dir = data_root / "datasets/members_snapshot_plus_delta" / NOW.strftime("%Y%m%d")
    cache_bytes = operational_latest_cache_bytes(unit_dir)
    stage_markers = _stage_markers(proc.stdout)

    measured = float(worker["measured_publish_wall_s"])
    rss_mib = round(int(worker["max_rss_bytes"]) / (1024 * 1024), 1)

    receipt = {
        "schema": "smial.factory-routine-publication-wallclock-full-path-benchmark",
        "schema_version": "1.0",
        "at": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "n_members": N,
        "observation_rows_measured_batch": OBS_BATCH,
        "provider_calls": 0,
        "provider_gate": "offline deterministic synthetic members; no network",
        "anchor_phase_unmeasured_wall_s": round(float(worker["anchor_wall_s"]), 3),
        "measured_publish_wall_s": round(measured, 3),
        "process_wall_s_incl_python_startup": round(process_wall, 3),
        "stage_timings_s": worker["stage_timings_s"],
        "stage_call_counts": worker["stage_call_counts"],
        "stage_markers": stage_markers,
        "peak_rss_bytes": int(worker["max_rss_bytes"]),
        "peak_rss_mib": rss_mib,
        "cache_bytes": cache_bytes,
        "cache_total_bytes": cache_bytes["cache_db_bytes"] + cache_bytes["cache_meta_bytes"],
        "full_population_passes": int(
            worker["publication_stage_stats"]["full_population_passes"]
        ),
        "operational_latest_hits": int(
            worker["publication_stage_stats"]["operational_latest_hits"]
        ),
        "operational_latest_misses": int(
            worker["publication_stage_stats"]["operational_latest_misses"]
        ),
        "reconstruct_calls_hot": int(
            worker["publication_stage_stats"]["reconstruct_calls_hot"]
        ),
        "publish_result": worker["result"],
        "acceptance": {
            "target_full_path_wall_s": 45.0,
            "fence_full_path_wall_s": 60.0,
            "target_rss_mib": 512.0,
            "fence_rss_mib": 768.0,
        },
    }
    receipt["envelope_pass_wall_le_45s"] = measured <= 45.0
    receipt["envelope_pass_wall_le_60s_fence"] = measured <= 60.0
    receipt["envelope_pass_rss_le_512mib"] = rss_mib <= 512.0
    receipt["envelope_pass_rss_below_768mib_fence"] = rss_mib < 768.0

    output = args.output
    if output is None:
        output = ROOT / "local" / "wallclock_bench" / "full_path_benchmark_v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                k: receipt[k]
                for k in (
                    "n_members",
                    "measured_publish_wall_s",
                    "peak_rss_mib",
                    "cache_total_bytes",
                    "full_population_passes",
                    "provider_calls",
                    "envelope_pass_wall_le_45s",
                    "envelope_pass_rss_le_512mib",
                )
            },
            indent=2,
        )
    )
    print(json.dumps(receipt["stage_timings_s"], indent=2, sort_keys=True))
    print(f"wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1].endswith("payload.tmp.json"):
        raise SystemExit(_worker(Path(sys.argv[1]), Path(sys.argv[2])))
    raise SystemExit(main())
